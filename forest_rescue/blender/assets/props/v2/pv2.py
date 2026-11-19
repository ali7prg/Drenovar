"""Props v2 pipeline core (cages, mechanisms, artifacts, supplies).

blueprint (metres, measured from the painting) -> joint camera + blueprint solve for every painted view
(cv2.solvePnP init over a focal scan, then least squares on all views / shared blueprint parameters) ->
node-structured geometry (parts = glTF nodes with pivots at the real axes, LOD0/1/2 meshes per part) ->
one UV atlas per LOD -> LOD0 colour = projection of the painting from every view (pose-aware z-buffer,
|n.v| >= 0.5 (>= 0.3 steep faces), magnification <= 2x) + swatch synthesis from the same object's painted
pixels for unseen texels -> LOD1/LOD2 atlases by nearest-texel transfer -> node animations (NLA clips) ->
GLB (+ external textures) + meta -> QA sheets per painted view: reference | render | IoU diff | colour error.

World: Blender Z-up metres, front (door / main face) = -Y (exports to glTF +Z).
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BLD = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
_V3 = os.path.join(BLD, "assets", "landmarks", "v3")
for _p in (BLD, os.path.join(BLD, "assets", "forest"), os.path.join(BLD, "assets", "paint3d"), _V3, HERE):
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

import bpy  # noqa: E402
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix  # noqa: E402
from PIL import Image  # noqa: E402
from scipy import ndimage as ndi  # noqa: E402
from scipy.optimize import least_squares  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

from frlib import core, paths, refs, texproj  # noqa: E402
import geo as G  # noqa: E402
import camsolve  # noqa: E402
import tex  # noqa: E402
import bl  # noqa: E402
import glbx  # noqa: E402

FPS = 30
RT = paths.ensure(paths.RUNTIME, "props")
SRC = paths.ensure(paths.SOURCES, "props")
TEXM = paths.ensure(paths.TEXTURE_SOURCES, "props", "v2")
PAINT_K = 0.38
_SH = {}


def log(*a):
    print(*a, flush=True)


def qa_path(aid, it, name, ext="png"):
    d = paths.ensure(paths.QA_COMPARE, aid)
    return os.path.join(d, f"v2_iter{it:02d}_{name}.{ext}")


def sheet(name):
    if name not in _SH:
        _SH[name] = np.asarray(Image.open(os.path.join(paths.ART, name)).convert("RGB"), np.float64) / 255.0
    return _SH[name]


# ============================================================================ math
def T4(t):
    M = np.eye(4)
    M[:3, 3] = np.asarray(t, float)
    return M


def R4(R):
    M = np.eye(4)
    M[:3, :3] = R
    return M


def euler_R(e):
    rx, ry, rz = e
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * x)


# ============================================================================ asset structure
class Part:
    def __init__(self, name, parent, pivot):
        self.name, self.parent, self.pivot = name, parent, np.asarray(pivot, float)
        self.geo = [G.Geo(seed=11 + i) for i in range(3)]


class Asset:
    """parts: glTF nodes (pivot = real rotation axis point, rest geometry authored in world coordinates).
    'root' has no node: its meshes are the top-level <id>_LOD<n> objects."""

    def __init__(self, aid, atlas=2048):
        self.id, self.atlas = aid, atlas
        self.parts = {}
        self.markers = {}
        self.clips = {}
        self.hidden = []        # nodes hidden by default (KHR_node_visibility)
        self.part("root")

    def part(self, name, parent=None, pivot=(0, 0, 0)):
        if name not in self.parts:
            self.parts[name] = Part(name, parent, pivot)
        return self.parts[name]

    def g(self, name, lod):
        return self.parts[name].geo[lod]

    def marker(self, name, pos, parent=None, rot=(0, 0, 0)):
        self.markers[name] = dict(pos=np.asarray(pos, float), parent=parent, rot=tuple(rot))

    def world_mats(self, pose=None):
        """{part: 4x4 world matrix of the posed rest geometry, or None when hidden}."""
        pose = pose or {}
        W = {}
        for name, p in self.parts.items():
            spec = pose.get(name, {})
            par = W.get(p.parent) if p.parent else np.eye(4)
            if (p.parent and par is None) or spec == "hide" or (isinstance(spec, dict) and spec.get("hide")):
                W[name] = None
                continue
            loc = np.asarray(spec.get("loc", (0, 0, 0)), float) if isinstance(spec, dict) else np.zeros(3)
            rot = spec.get("rot", (0, 0, 0)) if isinstance(spec, dict) else (0, 0, 0)
            L = T4(p.pivot + loc) @ R4(euler_R(rot)) @ T4(-p.pivot)
            W[name] = par @ L
        return W


class _GV:
    """Geo view with shifted vertices and slot-mapped material names (for bl.object_from_geo)."""

    def __init__(self, g, shift, slotmap):
        self.g, self.shift, self.slotmap = g, np.asarray(shift, float), slotmap

    def arrays(self):
        V, F, M, Tg, UV = self.g.arrays()
        return V - self.shift, F, [self.slotmap(m) for m in M], Tg, UV


def slot_of(m):
    if m == "glow":
        return "glow"
    if str(m).startswith("card"):
        return "card"
    return "atlas"


# ============================================================================ camera / blueprint solve
class ViewSpec:
    """A painted view: sheet crop + correspondences {key: (sheet_x, sheet_y)} + pose of the parts."""

    def __init__(self, name, sheet_name, box, points, pose=None, project=True, light=(-0.45, -0.55, 0.70),
                 thresh=0.10, fill_holes=40, exclude=(), clip_below=None, iou_ignore=None, weight=1.0,
                 shadow=None, solve_opts=None, hide_parts=(), title=""):
        self.name, self.sheet_name, self.box = name, sheet_name, tuple(box)
        self.points = dict(points)
        self.pose = dict(pose or {})
        for hp in hide_parts:
            self.pose[hp] = "hide"
        self.project, self.light, self.thresh, self.fill_holes = project, light, thresh, fill_holes
        self.exclude, self.clip_below, self.iou_ignore, self.weight = list(exclude), clip_below, iou_ignore, weight
        self.shadow = shadow
        self.solve_opts = solve_opts or {}
        self.title = title
        self.cam = None
        self.rep = None

    @property
    def crop(self):
        x0, y0, x1, y1 = self.box
        return sheet(self.sheet_name)[y0:y1, x0:x1]

    @property
    def size(self):
        x0, y0, x1, y1 = self.box
        return x1 - x0, y1 - y0

    def p2(self, keys):
        x0, y0 = self.box[:2]
        return np.array([[self.points[k][0] - x0, self.points[k][1] - y0] for k in keys], float)

    def mask(self):
        crop = self.crop
        bg = refs.border_color(crop, width=2)
        ex = [(a - self.box[0], b - self.box[1], c - self.box[0], d - self.box[1]) for (a, b, c, d) in self.exclude]
        m = refs.silhouette(crop, bg=bg, thresh=self.thresh, blur=0.7, open_px=0, close_px=1,
                            fill_holes=self.fill_holes, keep="all", min_area=25, exclude=ex,
                            clip_below=(self.clip_below - self.box[1]) if self.clip_below else None,
                            shadow_luma_drop=self.shadow)
        return m, bg


def solve_views(views, points_fn, params, free, prior_sigma=0.25, log_fn=log):
    """Joint least squares: per view (log f, rvec, tvec) + free blueprint params (soft prior: relative sigma).
    points_fn(params) -> {key: (x, y, z)}. Returns (params, per-view reports)."""
    params = dict(params)
    P = points_fn(params)
    for v in views:
        keys = [k for k in v.points if k in P]
        W, H = v.size
        cam, rep = camsolve.solve(np.array([P[k] for k in keys]), v.p2(keys), (W, H), **v.solve_opts)
        v.cam, v.rep = cam, rep
        log_fn(f"  [{v.name}] init solvePnP rms {rep['rms_px']:.2f}px (n={len(keys)}) f={cam.f:.0f}")
    free = [k for k in free if k in params]
    p0 = np.array([params[k] for k in free], float)
    scale0 = np.maximum(np.abs(p0), 0.05)

    def unpack(x):
        cams = []
        for i, v in enumerate(views):
            s = x[i * 7:(i + 1) * 7]
            cams.append(camsolve.Cam(math.exp(s[0]), v.size[0] / 2, v.size[1] / 2, s[1:4], s[4:7], size=v.size))
        pp = dict(params)
        for j, k in enumerate(free):
            pp[k] = x[len(views) * 7 + j]
        return cams, pp

    def resid(x):
        cams, pp = unpack(x)
        PP = points_fn(pp)
        r = []
        for c, v in zip(cams, views):
            keys = [k for k in v.points if k in PP]
            u, vv, z = c.project(np.array([PP[k] for k in keys]))
            q = v.p2(keys)
            r += list((u - q[:, 0]) * v.weight) + list((vv - q[:, 1]) * v.weight)
        for j, k in enumerate(free):
            r.append((pp[k] - p0[j]) / (prior_sigma * scale0[j]) * 0.6)
        return np.array(r)

    x0 = []
    for v in views:
        x0 += [math.log(v.cam.f), *v.cam.rvec, *v.cam.tvec]
    x0 += list(p0)
    sol = least_squares(resid, np.array(x0), method="trf", max_nfev=6000)
    cams, pp = unpack(sol.x)
    PP = points_fn(pp)
    for c, v in zip(cams, views):
        keys = [k for k in v.points if k in PP]
        u, vv, z = c.project(np.array([PP[k] for k in keys]))
        q = v.p2(keys)
        e = np.hypot(u - q[:, 0], vv - q[:, 1])
        v.cam = c
        v.rep = dict(rms_px=float(np.sqrt((e ** 2).mean())), max_px=float(e.max()), n=len(keys),
                     per_point_px={k: round(float(a), 2) for k, a in zip(keys, e)}, f=c.f,
                     fov_deg=float(2 * math.degrees(math.atan(max(v.size) / 2 / c.f))),
                     camera_centre=[round(float(a), 3) for a in c.centre])
        log_fn(f"  [{v.name}] joint solve rms {v.rep['rms_px']:.2f}px max {v.rep['max_px']:.2f}px n={len(keys)} "
               f"fov {v.rep['fov_deg']:.1f}")
    changed = {k: (round(params[k], 3), round(pp[k], 3)) for k in free}
    log_fn(f"  blueprint params (initial -> solved): {changed}")
    return pp, [v.rep for v in views]


def camera_overlay(v, P3named, out_png, geo_tris=None):
    crop = v.crop
    S = 3
    big = cv2.resize((np.clip(crop, 0, 1) * 255).astype(np.uint8), None, fx=S, fy=S, interpolation=cv2.INTER_CUBIC)
    if geo_tris is not None:
        V, T = geo_tris
        u, vv, z = v.cam.project(V)
        U = np.stack([u[T], vv[T]], 2)
        area = 0.5 * np.abs((U[:, 1, 0] - U[:, 0, 0]) * (U[:, 2, 1] - U[:, 0, 1]) - (U[:, 2, 0] - U[:, 0, 0]) * (U[:, 1, 1] - U[:, 0, 1]))
        sel = np.argsort(-area)[:2500]
        ov = big.copy()
        for t in T[sel]:
            if (z[t] <= 0).any():
                continue
            pts = (np.stack([u[t], vv[t]], 1) * S).astype(np.int32)
            cv2.polylines(ov, [pts], True, (90, 200, 255), 1, cv2.LINE_AA)
        big = cv2.addWeighted(big, 0.45, ov, 0.55, 0)
    keys = [k for k in v.points if k in P3named]
    u, vv, _ = v.cam.project(np.array([P3named[k] for k in keys]))
    q = v.p2(keys)
    for k, a, b, (c, d) in zip(keys, u, vv, q):
        cv2.circle(big, (int(c * S), int(d * S)), 6, (255, 40, 40), 2)
        cv2.line(big, (int(c * S), int(d * S)), (int(a * S), int(b * S)), (255, 255, 0), 1)
        cv2.circle(big, (int(a * S), int(b * S)), 3, (40, 255, 40), -1)
        cv2.putText(big, k, (int(c * S) + 6, int(d * S) - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
    Image.fromarray(big).save(out_png)


# ============================================================================ Blender objects
class Built:
    def __init__(self):
        self.empties = {}
        self.objs = {}      # (lod, part) -> obj
        self.finfo = {}     # (lod, part) -> dict(cls, tag) per polygon
        self.markers = {}
        self.mats = {}


def realize(asset, mats):
    """mats: {lod: {slot: material}}. Creates empties (parts), meshes and marker empties at rest."""
    B = Built()
    for name, p in asset.parts.items():
        if name == "root":
            continue
        e = bpy.data.objects.new(name, None)
        e.empty_display_size = 0.08
        core.link(e)
        par = p.parent if (p.parent and p.parent != "root") else None
        if par:
            e.parent = B.empties[par]
            e.location = tuple(p.pivot - asset.parts[par].pivot)
        else:
            e.location = tuple(p.pivot)
        e.rotation_mode = "XYZ"
        e["rest_loc"] = list(e.location)
        B.empties[name] = e
    for lod in range(3):
        for name, p in asset.parts.items():
            g = p.geo[lod]
            if not g.F:
                continue
            nm = f"{asset.id}_LOD{lod}" if name == "root" else f"{asset.id}_{name}_LOD{lod}"
            o, fixed, M, Tg = bl.object_from_geo(nm, _GV(g, p.pivot if name != "root" else (0, 0, 0), slot_of),
                                                 mats[lod], smooth_mats=())
            _, _, Mo, Tgo, _ = g.arrays()
            smooth_cls = {"rope", "root", "cloth", "bone", "crystal", "bread", "sack", "smooth"}
            sm = np.array([str(m) in smooth_cls or str(t).endswith("_sm") for m, t in zip(Mo, Tgo)])
            o.data.polygons.foreach_set("use_smooth", sm)
            o.data.update()
            if name != "root":
                o.parent = B.empties[name]
                o.location = (0, 0, 0)
            B.objs[(lod, name)] = o
            B.finfo[(lod, name)] = dict(cls=np.array([str(m) for m in Mo], dtype=object),
                                        tag=np.array([str(t) for t in Tgo], dtype=object), fixed=fixed)
    for mname, m in asset.markers.items():
        e = bpy.data.objects.new(mname, None)
        e.empty_display_type = "ARROWS"
        e.empty_display_size = 0.12
        core.link(e)
        par = m["parent"] if m["parent"] and m["parent"] != "root" else None
        if par:
            e.parent = B.empties[par]
            e.location = tuple(m["pos"] - asset.parts[par].pivot)
        else:
            e.location = tuple(m["pos"])
        e.rotation_euler = m["rot"]
        B.markers[mname] = e
    bpy.context.view_layer.update()
    return B


def set_pose(asset, B, pose):
    pose = pose or {}
    for name, e in B.empties.items():
        if e.animation_data:
            e.animation_data.action = None
            for tr in e.animation_data.nla_tracks:
                tr.mute = True
        spec = pose.get(name, {})
        spec = spec if isinstance(spec, dict) else {}
        e.location = tuple(np.asarray(e["rest_loc"], float) + np.asarray(spec.get("loc", (0, 0, 0)), float))
        e.rotation_euler = tuple(spec.get("rot", (0, 0, 0)))
        e.scale = (1, 1, 1)
    bpy.context.view_layer.update()


def rest(asset, B):
    set_pose(asset, B, {})
    for e in B.empties.values():
        if e.animation_data:
            for tr in e.animation_data.nla_tracks:
                tr.mute = False


def hidden_parts(asset, pose):
    W = asset.world_mats(pose)
    return {k for k, v in W.items() if v is None}


# ============================================================================ texturing
def gather(asset, B, lod):
    rows = [(name, B.objs[(lod, name)], B.finfo[(lod, name)]) for name in asset.parts if (lod, name) in B.objs]
    Vs, Ts, UVs, FNs, CL, TG, PT, OB = [], [], [], [], [], [], [], []
    off = 0
    pnames = list(asset.parts)
    for oi, (name, o, fi) in enumerate(rows):
        V, T, UV, FN, mi, pi = bl.mesh_tris(o)
        Vs.append(V)
        Ts.append(T + off)
        UVs.append(UV)
        FNs.append(FN)
        CL.append(fi["cls"][pi])
        TG.append(fi["tag"][pi])
        PT.append(np.full(len(T), pnames.index(name)))
        OB.append(np.full(len(T), oi))
        off += len(V)
    return dict(V=np.concatenate(Vs), T=np.concatenate(Ts), UV=np.concatenate(UVs), FN=np.concatenate(FNs),
                cls=np.concatenate(CL), tag=np.concatenate(TG), part=np.concatenate(PT), ob=np.concatenate(OB),
                pnames=pnames)


def posed(asset, D, pose):
    """Posed vertex positions (per triangle corner) and a per-triangle visibility flag."""
    W = asset.world_mats(pose)
    pn = D["pnames"]
    Vt = D["V"][D["T"]]                          # (nt, 3, 3)
    out = Vt.copy()
    vis = np.ones(len(D["T"]), bool)
    for i, nm in enumerate(pn):
        k = D["part"] == i
        if not k.any():
            continue
        M = W.get(nm)
        if M is None:
            vis[k] = False
            continue
        out[k] = Vt[k] @ M[:3, :3].T + M[:3, 3]
    return out, vis, W


def zbuf_tris(cam, W, H, Vt):
    V = Vt.reshape(-1, 3)
    T = np.arange(len(V)).reshape(-1, 3)
    return tex.zbuffer(cam, W, H, V, T)


class Swatches:
    """Material swatches from the painting (crops of the same object's painted pixels)."""

    def __init__(self, spec):
        self.sw = {}
        for cls, s in spec.items():
            img = sheet(s["sheet"])
            x0, y0, x1, y1 = s["box"]
            self.sw[cls] = tex.Swatch(img[y0:y1, x0:x1], s["metres"], cls, rotate=s.get("rotate", False))

    def get(self, cls):
        return self.sw.get(cls) or next(iter(self.sw.values()))


def texture_lod0(asset, B, views, swatch_spec, size, it, gate=None, tone_cell=0.25, edge=None, log_fn=log):
    """Albedo + normal atlas for LOD0 from all projecting views. Returns (alb_img, nrm_img, info, stats)."""
    t0 = time.time()
    rest(asset, B)
    bpy.context.view_layer.update()
    D = gather(asset, B, 0)
    V, T, UV, FN = D["V"], D["T"], D["UV"], D["FN"]
    Tx = texproj.rasterize_uv(V, T, UV, size, flat_normals=True)
    valid = Tx.valid
    yy, xx = np.nonzero(valid)
    tri = Tx.tri[yy, xx]
    P = Tx.pos[yy, xx]
    N = FN[tri]
    cls = D["cls"][tri]
    tags = D["tag"][tri]
    part = D["part"][tri]
    log_fn(f"  atlas {size}: {len(P)} texels ({time.time() - t0:.1f}s)")
    acc = np.zeros((len(P), 3))
    wsum = np.zeros(len(P))
    lenient = np.zeros((len(P), 3))
    lw = np.zeros(len(P))
    per_view = {}
    for v in views:
        if not v.project:
            continue
        W_, H_ = v.size
        Vt, tvis, Wm = posed(asset, D, v.pose)
        zb = zbuf_tris(v.cam, W_, H_, Vt[tvis])
        # posed texel positions / normals
        Pp = P.copy()
        Np = N.copy()
        hide = np.zeros(len(P), bool)
        for i, nm in enumerate(D["pnames"]):
            k = part == i
            if not k.any():
                continue
            M = Wm.get(nm)
            if M is None:
                hide[k] = True
                continue
            Pp[k] = P[k] @ M[:3, :3].T + M[:3, 3]
            Np[k] = N[k] @ M[:3, :3].T
        ref_m, _ = v.mask()
        crop = v.crop
        c = np.zeros((len(P), 3))
        w = np.zeros(len(P))
        for mc in np.unique(cls):
            k = (cls == mc) & ~hide
            if not k.any():
                continue
            accm = ref_m
            if gate and mc in gate:
                accm = ref_m & gate[mc](crop)
            ck, wk, fk = tex.project_painting(Pp[k], Np[k], v.cam, crop, zb, W_, H_, accept=accm, min_facing=0.5,
                                              max_mag=2.0)
            c[k], w[k] = ck, wk
            c2, w2, _ = tex.project_painting(Pp[k], Np[k], v.cam, crop, zb, W_, H_, accept=accm, min_facing=0.12,
                                             max_mag=1e9)
            shade2 = tex.lambert_shade(Np[k], v.light, PAINT_K)
            lenient[k] += (c2 / shade2[:, None]) * (w2 > 0)[:, None]
            lw[k] += (w2 > 0)
        shade = tex.lambert_shade(Np, v.light, PAINT_K)
        wp = w ** 4
        acc += (c / shade[:, None]) * wp[:, None]
        wsum += wp
        per_view[v.name] = float((w > 0).mean())
    proj = np.clip(acc / np.maximum(wsum, 1e-12)[:, None], 0, 1)
    wmax = wsum ** 0.25
    has_l = lw > 0
    len_col = np.clip(lenient / np.maximum(lw, 1)[:, None], 0, 1)
    # ---- swatch fill, colour matched (per tag -> per class -> swatch)
    sw = Swatches(swatch_spec)
    lab_p = tex.to_lab(proj)
    lab_l = tex.to_lab(len_col)
    good = wmax > 0.3
    fill = np.zeros((len(P), 3))
    rng = np.random.default_rng(7)
    for mc in np.unique(cls):
        km = cls == mc
        s = sw.get(mc)
        idx = np.nonzero(km)[0]
        for tg in np.unique(tags[km]):
            ii = idx[tags[idx] == tg]
            raw = s.sample(P[ii], N[ii], rng.uniform(0, 5, 3))
            gk = good[ii]
            lk = has_l[ii]
            if gk.sum() > 60:
                mu, sd = lab_p[ii][gk].mean(0), lab_p[ii][gk].std(0)
            elif lk.sum() > 60:
                mu, sd = lab_l[ii][lk].mean(0), lab_l[ii][lk].std(0)
            else:
                gc = good & km
                if gc.sum() > 60:
                    mu, sd = lab_p[gc].mean(0), lab_p[gc].std(0)
                else:
                    mu, sd = s.mu, s.sd
            sd = np.maximum(sd, s.sd * 0.5)
            fill[ii] = tex.colour_match(raw, mu, sd, s.mu, s.sd, 1.0)
    # low-frequency tone: shift the fill toward the painting's (lenient) local mean in 3-D cells
    if has_l.sum() > 100 and tone_cell:
        key = np.floor(P / tone_cell).astype(np.int64)
        kh = (key[:, 0] * 73856093) ^ (key[:, 1] * 19349663) ^ (key[:, 2] * 83492791) ^ (part * 2654435761)
        _, inv = np.unique(kh, return_inverse=True)
        nb = inv.max() + 1
        vi = np.nonzero(has_l)[0]
        cnt = np.bincount(inv[vi], minlength=nb).astype(float)
        sp = np.stack([np.bincount(inv[vi], weights=len_col[vi, c_], minlength=nb) for c_ in range(3)], 1)
        sf = np.stack([np.bincount(inv[vi], weights=fill[vi, c_], minlength=nb) for c_ in range(3)], 1)
        ok = cnt > 12
        shift = np.zeros((nb, 3))
        shift[ok] = (sp[ok] - sf[ok]) / cnt[ok, None]
        fill = np.clip(fill + np.clip(shift, -0.18, 0.18)[inv] * 0.85, 0, 1)
    a_img = np.zeros(valid.shape)
    a_img[yy, xx] = np.clip((wmax - 0.18) / 0.22, 0, 1)
    a_img = ndi.gaussian_filter(a_img, 1.0) * valid
    a = a_img[yy, xx]
    alb = proj * a[:, None] + fill * (1 - a[:, None])
    if edge:
        # island-border darkening (plank / block / beam edges) per class
        dist = ndi.distance_transform_edt(valid)
        d = dist[yy, xx]
        k = np.array([edge.get(c_, 0.0) for c_ in cls])
        alb = alb * (1 - k * np.exp(-d / 2.5))[:, None] * (1 - a[:, None] * 0) + 0
    out = np.zeros(valid.shape + (3,))
    out[yy, xx] = alb
    out = tex.dilate(out, valid, 8)
    hgt = tex.height_from_albedo(out, valid, 4.0) * 2.5
    nrm = texproj.height_to_normal(hgt, valid, strength=1.0)
    nrm = tex.dilate(nrm, valid, 8)
    stats = dict(texels=int(len(P)), projected_frac=round(float((a > 0.5).mean()), 4),
                 per_view_frac={k: round(x, 4) for k, x in per_view.items()}, seconds=round(time.time() - t0, 1))
    log_fn(f"  texture: projected {stats['projected_frac']:.1%} {stats['per_view_frac']} ({stats['seconds']}s)")
    info = dict(P=P, alb=alb, part=part)
    return out, nrm, info, stats


def transfer(asset, B, lod, info, size):
    rest(asset, B)
    D = gather(asset, B, lod)
    Tx = texproj.rasterize_uv(D["V"], D["T"], D["UV"], size, flat_normals=True)
    yy, xx = np.nonzero(Tx.valid)
    tri = Tx.tri[yy, xx]
    P = Tx.pos[yy, xx] + D["FN"][tri] * 0.004
    part = D["part"][tri]
    out_c = np.zeros((len(P), 3))
    for pi in np.unique(part):
        k = part == pi
        src = info["part"] == pi
        if not src.any():
            src = np.ones(len(info["part"]), bool)
        tree = cKDTree(info["P"][src])
        d, i = tree.query(P[k], k=4)
        w = 1.0 / np.maximum(d, 1e-4)
        out_c[k] = (info["alb"][src][i] * w[..., None]).sum(1) / w.sum(1, keepdims=True)
    out = np.zeros((size, size, 3))
    out[yy, xx] = out_c
    return tex.dilate(out, Tx.valid, 6)


# ============================================================================ QA renders / sheets
def qa_material(src, k=PAINT_K, light=(-0.45, -0.55, 0.70)):
    return bl.painted_qa_material(src, k, light)


def use_qa(objs, light, on=True):
    for o in objs:
        for i, s in enumerate(o.material_slots):
            if on:
                s.link = "OBJECT"
                m = o.data.materials[i]
                if m.name.endswith("_glow"):
                    s.material = m
                else:
                    s.material = bl.painted_qa_material(m, PAINT_K, light)
            else:
                s.link = "DATA"


def render_view(asset, B, v, ss=2, lod=0):
    set_pose(asset, B, v.pose)
    hid = hidden_parts(asset, v.pose)
    objs = [o for (l_, nm), o in B.objs.items() if l_ == lod and nm not in hid]
    use_qa(objs, v.light, True)
    rgba = bl.render_painting_cam(v.cam, v.size[0], v.size[1], objs, ss=ss)
    use_qa(objs, v.light, False)
    rest(asset, B)
    return rgba


def _label(img_u8, text, xy=(6, 4)):
    from PIL import ImageDraw
    im = Image.fromarray(img_u8)
    dr = ImageDraw.Draw(im)
    x, y = xy
    dr.rectangle([x - 3, y - 2, x + 6 * len(text) + 6, y + 12], fill=(20, 20, 20))
    dr.text((x, y), text, fill=(255, 240, 200))
    return np.asarray(im)


def compare(v, rgba, out_png, title, ignore=None, scale=2):
    ref = v.crop
    ref_mask, bg = v.mask()
    a = rgba[..., 3:4]
    comp = rgba[..., :3] * a + bg[None, None] * (1 - a)
    rm = rgba[..., 3] > 0.5
    use = np.ones(rm.shape, bool) if ignore is None else ~ignore
    inter = (ref_mask & rm & use).sum()
    union = ((ref_mask | rm) & use).sum()
    iou = inter / max(1, union)
    rf = ndi.binary_fill_holes(ref_mask)
    mf = ndi.binary_fill_holes(rm)
    iou_f = ((rf & mf & use).sum()) / max(1, ((rf | mf) & use).sum())
    both = ref_mask & rm & use
    err = np.abs(comp - ref).mean(2)
    cerr = float(err[both].mean()) if both.any() else 1.0
    core_m = ndi.binary_erosion(both, iterations=1)
    cerr_core = float(err[core_m].mean()) if core_m.any() else cerr
    diff = np.repeat(ref.mean(2, keepdims=True) * 0.5 + 0.35, 3, 2)
    diff[both] = diff[both] * 0.5 + np.array([0.15, 0.55, 0.15]) * 0.5
    diff[ref_mask & ~rm & use] = (0.85, 0.15, 0.15)
    diff[~ref_mask & rm & use] = (0.15, 0.3, 0.9)
    if ignore is not None:
        diff[~use] = diff[~use] * 0.4 + np.array([0.6, 0.6, 0.0]) * 0.6 * (ref_mask | rm)[~use][:, None]
    e = np.clip(err / 0.25, 0, 1)
    heat = np.zeros(ref.shape)
    heat[..., 0] = np.clip(e * 2, 0, 1)
    heat[..., 1] = np.clip(e * 2 - 1, 0, 1)
    heat[..., 2] = np.clip(1 - e * 3, 0, 1) * 0.35
    heat[~both] = 0.12
    panels = []
    for img, txt in ((ref, "reference (painting)"), (comp, "render (painted light)"),
                     (diff, f"IoU raw {iou:.3f} filled {iou_f:.3f}"), (heat, f"colour err {cerr:.3f} (core {cerr_core:.3f})")):
        u8 = (np.clip(img, 0, 1) * 255).astype(np.uint8)
        if scale != 1:
            u8 = cv2.resize(u8, (u8.shape[1] * scale, u8.shape[0] * scale), interpolation=cv2.INTER_CUBIC)
        panels.append(_label(u8, txt))
    sheet_ = np.concatenate(panels, 1)
    top = np.full((24, sheet_.shape[1], 3), 28, np.uint8)
    top = _label(top, title)
    Image.fromarray(np.concatenate([top, sheet_], 0)).save(out_png)
    m = dict(iou_raw=round(float(iou), 4), iou_filled=round(float(iou_f), 4), colour_err=round(cerr, 4),
             colour_err_core=round(cerr_core, 4), ref_px=int(ref_mask.sum()), render_px=int(rm.sum()),
             ignored_px=int((~use).sum()))
    core.write_json(out_png.replace(".png", ".json"), m)
    return m


def ignore_mask_from_parts(asset, B, v, parts, dilate=3):
    """Pixels covered by the given parts in this view (rendered silhouette) -> excluded from IoU."""
    set_pose(asset, B, v.pose)
    objs = [o for (l_, nm), o in B.objs.items() if l_ == 0 and nm in parts]
    if not objs:
        rest(asset, B)
        return None
    use_qa(objs, v.light, True)
    rgba = bl.render_painting_cam(v.cam, v.size[0], v.size[1], objs, ss=1)
    use_qa(objs, v.light, False)
    rest(asset, B)
    m = rgba[..., 3] > 0.3
    return ndi.binary_dilation(m, iterations=dilate)


# ============================================================================ animation
def _fcurves(act):
    try:
        return list(act.fcurves)
    except AttributeError:
        out = []
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    out += list(cb.fcurves)
        return out


def add_clip(asset, B, clip, seconds, tracks, markers=None, loop=False, note=""):
    """tracks: {node: fn(t_seconds) -> dict(loc=offset from rest, rot=euler)}; one NLA track per node named clip."""
    frames = max(1, int(round(seconds * FPS)))
    asset.clips[clip] = dict(seconds=round(frames / FPS, 4), loop=loop, frames=frames, markers=markers or {},
                             nodes=sorted(tracks), note=note)
    for node, fn in tracks.items():
        obj = B.empties[node]
        rl = np.asarray(obj["rest_loc"], float)
        if obj.animation_data is None:
            obj.animation_data_create()
        act = bpy.data.actions.new(f"{clip}|{node}")
        act.use_fake_user = True
        obj.animation_data.action = act
        for f in range(frames + 1):
            val = fn(f / FPS)
            obj.location = tuple(rl + np.asarray(val.get("loc", (0, 0, 0)), float))
            obj.rotation_euler = tuple(val.get("rot", (0, 0, 0)))
            obj.scale = tuple(val.get("scale", (1, 1, 1)))
            obj.keyframe_insert("location", frame=f)
            obj.keyframe_insert("rotation_euler", frame=f)
            obj.keyframe_insert("scale", frame=f)
        for fc in _fcurves(act):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        act.use_frame_range = True
        act.frame_start = 0
        act.frame_end = frames
        obj.animation_data.action = None
        tr = obj.animation_data.nla_tracks.new()
        tr.name = clip
        st = tr.strips.new(clip, 0, act)
        st.extrapolation = "NOTHING"
        obj.location = tuple(rl)
        obj.rotation_euler = (0, 0, 0)
        obj.scale = (1, 1, 1)


def pose_from_clip(asset, B, clip, t):
    """Evaluate the clip's track functions is not possible after keying; use actions directly."""
    for name, e in B.empties.items():
        if e.animation_data:
            for tr in e.animation_data.nla_tracks:
                tr.mute = True
            e.animation_data.action = None
            act = bpy.data.actions.get(f"{clip}|{name}")
            if act is not None:
                e.animation_data.action = act
    bpy.context.scene.frame_set(int(round(t * FPS)))
    bpy.context.view_layer.update()


def clear_actions(asset, B):
    for e in B.empties.values():
        if e.animation_data:
            e.animation_data.action = None
    rest(asset, B)


# ============================================================================ export
def export(asset, B, path, texfiles):
    rest(asset, B)
    for e in B.empties.values():
        if e.animation_data:
            e.animation_data.action = None
            for tr in e.animation_data.nla_tracks:
                tr.mute = False
    objs = list(B.empties.values()) + list(B.objs.values()) + list(B.markers.values())
    bpy.context.preferences.edit.use_negative_frames = True
    bpy.context.scene.frame_set(-10)
    core.export_glb(path, objs, animations=bool(asset.clips),
                    extra={"export_animation_mode": "NLA_TRACKS", "export_optimize_animation_size": False,
                           "export_def_bones": False, "export_skins": False, "export_current_frame": True,
                           "export_optimize_animation_keep_anim_object": True, "export_vertex_color": "NONE",
                           "export_image_format": "AUTO"})
    bpy.context.scene.frame_set(0)
    glbx.externalize(path, texfiles)
    # default-hidden nodes (LOD1/LOD2 meshes, alternative socket plates) via KHR_node_visibility
    js, bin_ = glbx.read_glb(path)
    hid = set(asset.hidden)
    for lod in (1, 2):
        for (l_, nm), o in B.objs.items():
            if l_ == lod:
                hid.add(o.name)
    n = 0
    for node in js.get("nodes", []):
        if node.get("name") in hid:
            node.setdefault("extensions", {})["KHR_node_visibility"] = {"visible": False}
            n += 1
    if n:
        used = js.setdefault("extensionsUsed", [])
        if "KHR_node_visibility" not in used:
            used.append("KHR_node_visibility")
    # sanity: no zero scale anywhere
    for node in js.get("nodes", []):
        s = node.get("scale")
        if s and min(abs(x) for x in s) < 1e-4:
            raise RuntimeError(f"zero scale on node {node.get('name')}")
    glbx.write_glb(path, js, bin_)
    return path


def glb_nodes(path):
    js, _ = glbx.read_glb(path)
    return [n.get("name") for n in js.get("nodes", [])], [a.get("name") for a in js.get("animations", [])]


def b2g(p):
    p = np.asarray(p, float)
    return [round(float(p[0]), 4), round(float(p[2]), 4), round(float(-p[1]), 4)]


def save_jpg(path, arr, q=90):
    Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8)).save(path, quality=q, optimize=True)


def save_png(path, arr):
    a = (np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(a, "RGBA" if a.shape[2] == 4 else "RGB").save(path, optimize=True)


# ============================================================================ Godot checks
GODOT = shutil.which("godot") or "/usr/local/bin/godot"
VIEWER = os.path.join(paths.FR_DIR, "tools", "godot_viewer")


def godot_import_check(glb, extra_files=()):
    """Import the GLB (+ sibling textures) into a private copy of the viewer project; returns error/warning lines."""
    work = tempfile.mkdtemp(prefix="pv2imp.")
    shutil.copytree(VIEWER, work, dirs_exist_ok=True)
    md = os.path.join(work, "models")
    os.makedirs(md, exist_ok=True)
    for f in os.listdir(md):
        os.remove(os.path.join(md, f))
    shutil.copy(glb, md)
    for f in extra_files:
        shutil.copy(f, md)
    r = subprocess.run(["timeout", "600", GODOT, "--headless", "--path", work, "--import"], capture_output=True,
                       text=True)
    out = (r.stdout or "") + (r.stderr or "")
    bad = [ln for ln in out.splitlines() if ("ERROR" in ln or "WARNING" in ln or "Basis" in ln)
           and "vulkan" not in ln.lower() and "Vulkan" not in ln]
    shutil.rmtree(work, ignore_errors=True)
    return bad, out
