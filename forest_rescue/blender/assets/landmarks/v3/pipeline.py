"""Landmarks v3 pipeline: blueprint -> camera solve -> geometry -> unique atlas -> painting projection +
swatch fill -> LOD textures -> GLB/meta export -> QA sheets.

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/landmarks/v3/pipeline.py <name> [--iter N]
names: bridge27m quarry_mine camp_props hunter_shelter ruined_watchpost standing_stones
"""
import importlib
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "paint3d")))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "forest")))
import bpy  # noqa: E402
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from scipy import ndimage as ndi  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

from frlib import core, paths, refs, texproj  # noqa: E402
import bl  # noqa: E402
import camsolve  # noqa: E402
import tex  # noqa: E402

SHEET06 = os.path.join(paths.ART, "06_environment_landmarks.png")
SHEET01 = os.path.join(paths.ART, "01_world_masterplan.png")
RT = paths.ensure(paths.RUNTIME, "landmarks")
MASTER = paths.ensure(paths.TEXTURE_SOURCES, "landmarks", "v3")
SRC = paths.ensure(paths.SOURCES, "landmarks")
_SHEETS = {}


def sheet(path=SHEET06):
    if path not in _SHEETS:
        _SHEETS[path] = np.asarray(Image.open(path).convert("RGB"), np.float64) / 255.0
    return _SHEETS[path]


def qa_path(asset, it, name, ext="png"):
    return paths.compare(asset, f"v3_iter{it:02d}_{name}.{ext}")


# ----------------------------------------------------------------------------- reference
def reference(L):
    img = sheet()
    x0, y0, x1, y1 = L.MAIN_BOX
    crop = img[y0:y1, x0:x1].copy()
    bg = refs.border_color(crop, width=2)
    m = refs.silhouette(crop, bg=bg, thresh=getattr(L, "MASK_THRESH", 0.10), keep="all", min_area=80,
                        fill_holes=getattr(L, "MASK_FILL", 300), exclude=getattr(L, "MASK_EXCLUDE", None), blur=1.0,
                        open_px=1, close_px=2)
    if hasattr(L, "mask_fix"):
        m = L.mask_fix(m, crop)
    return crop, m, bg


def solve_camera(L, asset, it, W, H):
    P3, p2, opts = L.camera_points()
    cam, rep = camsolve.solve(np.asarray(P3, float), np.asarray(p2, float), (W, H), **opts)
    rep["points"] = [dict(world=[round(float(a), 3) for a in P], pixel=[float(a) for a in q]) for P, q in zip(P3, p2)]
    core.write_json(qa_path(asset, it, "camera", "json"), dict(camera=cam.to_json(), report=rep))
    print(f"[{asset}] camera solve: rms {rep['rms_px']:.2f}px max {rep['max_px']:.2f}px f {rep['f']:.0f} "
          f"fov {rep['fov_deg']:.1f} k1 {rep['k1']:.3f} n={rep['n']}", flush=True)
    return cam, rep


def camera_overlay(L, asset, it, cam, crop, P3, p2, geo=None):
    """Painting with the solved projections of the correspondences (+ optional wireframe of the model)."""
    img = (np.clip(crop, 0, 1) * 255).astype(np.uint8).copy()
    S = 3
    big = cv2.resize(img, None, fx=S, fy=S, interpolation=cv2.INTER_CUBIC)
    if geo is not None:
        V, F, M, Tg, UV = geo.arrays()
        u, v, z = cam.project(V)
        for f in F[:: max(1, len(F) // 6000)]:
            pts = np.stack([u[f], v[f]], 1) * S
            if (z[f] <= 0).any():
                continue
            cv2.polylines(big, [pts.astype(np.int32)], True, (90, 200, 255), 1, cv2.LINE_AA)
    u, v, _ = cam.project(np.asarray(P3, float))
    for (a, b), (c, d) in zip(np.stack([u, v], 1), p2):
        cv2.circle(big, (int(c * S), int(d * S)), 5, (255, 40, 40), 2)
        cv2.line(big, (int(c * S), int(d * S)), (int(a * S), int(b * S)), (255, 255, 0), 1)
        cv2.circle(big, (int(a * S), int(b * S)), 3, (40, 255, 40), -1)
    Image.fromarray(big).save(qa_path(asset, it, "camera_overlay"))


# ----------------------------------------------------------------------------- cards atlas
def card_atlas(L, size=1024):
    """Vegetation sprites for alpha cards. CARD_KINDS (procedural fern/grass/weed/ivy in the painting palette)
    or CARD_SPRITES (cut from the art). Returns (rgba (size,size,4), rects {name: (u0,v0,u1,v1,aw,ah)})."""
    if getattr(L, "CARD_KINDS", None):
        import sprites
        x0, y0, x1, y1 = L.MAIN_BOX
        pal = sprites.palette_from(sheet()[y0:y1, x0:x1])
        return sprites.atlas(list(L.CARD_KINDS.items()), pal, size)
    sprites = getattr(L, "CARD_SPRITES", {})
    if not sprites:
        return None, {}
    img = sheet()
    n = len(sprites)
    cols = int(math.ceil(math.sqrt(n)))
    cell = size // cols
    atlas = np.zeros((size, size, 4), np.float32)
    rects = {}
    for i, (name, spec) in enumerate(sprites.items()):
        x0, y0, x1, y1 = spec["box"]
        crop = img[y0:y1, x0:x1]
        alpha = spec["mask"](crop).astype(np.float32)
        alpha = ndi.binary_opening(alpha > 0.5, iterations=1).astype(np.float32)
        h, w = crop.shape[:2]
        s = min((cell - 8) / w, (cell - 8) / h)
        nw, nh = max(1, int(w * s)), max(1, int(h * s))
        rgb = cv2.resize(crop.astype(np.float32), (nw, nh), interpolation=cv2.INTER_CUBIC)
        a = cv2.resize(alpha, (nw, nh), interpolation=cv2.INTER_LINEAR)
        known = a > 0.5
        rgb = texproj.fill(rgb, known)
        r, c = divmod(i, cols)
        ox = c * cell + (cell - nw) // 2
        oy = r * cell + (cell - nh)  # bottom aligned
        oy = r * cell + (cell - nh) - 4
        atlas[oy:oy + nh, ox:ox + nw, :3] = np.clip(rgb, 0, 1)
        atlas[oy:oy + nh, ox:ox + nw, 3] = (a > 0.5).astype(np.float32)
        rects[name] = (ox / size, 1 - (oy + nh) / size, (ox + nw) / size, 1 - oy / size, w / max(w, h), h / max(w, h))
    # bleed colour outside alpha for mip safety
    known = atlas[..., 3] > 0.5
    atlas[..., :3] = texproj.fill(atlas[..., :3], known)
    return atlas, rects


# ----------------------------------------------------------------------------- texturing
def rectify(cam, crop, origin, ex, ey, size_m, res=256):
    """Orthophoto of a painted planar patch: origin + u*ex + v*ey (u,v in [0,size_m]) -> painting pixels."""
    o = np.asarray(origin, float)
    ex = np.asarray(ex, float)
    ey = np.asarray(ey, float)
    t = (np.arange(res) + 0.5) / res * size_m
    U, Vv = np.meshgrid(t, t[::-1])
    P = o + U[..., None] * ex + Vv[..., None] * ey
    u, v, _ = cam.project(P.reshape(-1, 3))
    return np.clip(tex.bilinear(crop, u, v)[:, :3].reshape(res, res, 3), 0, 1)


def gather(objs):
    Vs, Ts, UVs, FNs, MIs, OB, PIs = [], [], [], [], [], [], []
    off = 0
    for oi, o in enumerate(objs):
        V, T, UV, FN, mi, pi = bl.mesh_tris(o)
        Vs.append(V)
        Ts.append(T + off)
        UVs.append(UV)
        FNs.append(FN)
        MIs.append(np.array([o.data.materials[i].name.rsplit("_", 1)[-1].split(".")[0] for i in mi], dtype=object))
        OB.append(np.full(len(T), oi))
        PIs.append(pi)
        off += len(V)
    return (np.concatenate(Vs), np.concatenate(Ts), np.concatenate(UVs), np.concatenate(FNs),
            np.concatenate(MIs), np.concatenate(OB), np.concatenate(PIs))


def texture_atlas(L, asset, it, objs, face_tags, cam, crop, ref_mask, W, H, size=2048, card_objs=()):
    """Albedo + normal atlas for objs (sharing one UV atlas). face_tags: per object list of polygon tags."""
    t0 = time.time()
    V, T, UV, FN, MC, OB, PI = gather(objs)
    TAG = np.array([face_tags[o][p] for o, p in zip(OB, PI)], dtype=object)
    opaque = MC != "card"
    # occluders for the painting-camera z-buffer: every opaque triangle (+ cards objects excluded)
    zb = tex.zbuffer(cam, W, H, V, T[opaque])
    sel = np.nonzero(opaque)[0]
    Tx = texproj.rasterize_uv(V, T[sel], UV[sel], size, flat_normals=True)
    valid = Tx.valid
    yy, xx = np.nonzero(valid)
    tri = sel[Tx.tri[yy, xx]]
    P = Tx.pos[yy, xx]
    N = FN[tri]
    mcls = MC[tri]
    tags = TAG[tri]
    print(f"[{asset}] atlas {size}: {len(P)} texels, raster {time.time() - t0:.1f}s", flush=True)
    # painting classes
    clf = tex.Classes()
    img06 = sheet()
    for cname, boxes in L.CLASS_TRAIN.items():
        px = np.concatenate([img06[b[1]:b[3], b[0]:b[2]].reshape(-1, 3) for b in boxes])
        clf.train(cname, px)
    pcls, _ = clf.classify(crop)
    col = np.zeros((len(P), 3))
    wgt = np.zeros(len(P))
    col_s = np.zeros((len(P), 3))      # lenient visibility: palette statistics only (no detail transfer)
    vis_s = np.zeros(len(P), bool)
    nop = np.array([any(str(t).startswith(pre) for pre in getattr(L, "NO_PROJECT_TAGS", ())) for t in tags])
    for mc, accepted in L.ACCEPT.items():
        k = (mcls == mc) & ~nop
        if not k.any():
            continue
        acc = np.isin(pcls, list(accepted)) & ref_mask
        c, w, facing = tex.project_painting(P[k], N[k], cam, crop, zb, W, H, accept=acc)
        col[k], wgt[k] = c, w
        c2, w2, _ = tex.project_painting(P[k], N[k], cam, crop, zb, W, H, accept=acc, min_facing=0.08, max_mag=1e9)
        col_s[k], vis_s[k] = c2, w2 > 0
    # de-light (painting key light) so the painted-light shader reproduces the painting
    shade = tex.lambert_shade(N, bl.PAINT_LIGHT_06)
    proj_alb = np.clip(col / shade[:, None], 0, 1)
    # swatch fill, colour matched per tag (fallback: per class, then swatch statistics)
    sw = {}
    for mc, spec in L.SWATCHES.items():
        if "plane" in spec:      # rectified from the painting through the solved camera
            sw[mc] = tex.Swatch(rectify(cam, crop, **spec["plane"]), spec["metres"], mc)
            core.save_rgba(qa_path(asset, it, f"swatch_{mc}"), sw[mc].img)
            continue
        b = spec["box"]
        src = sheet(spec.get("sheet", SHEET06))
        sw[mc] = tex.Swatch(src[b[1]:b[3], b[0]:b[2]], spec["metres"], mc, rotate=spec.get("rotate", False))
    tag_sw = getattr(L, "TAG_SWATCH", {})
    # painting class at each texel's projection (even where the colour is not projected) -> swatch choice
    u_all, v_all, _ = cam.project(P)
    ui = np.clip(np.floor(u_all).astype(int), 0, W - 1)
    vi = np.clip(np.floor(v_all).astype(int), 0, H - 1)
    texcls = pcls[vi, ui]
    class_sw = getattr(L, "CLASS_SWATCH", {})
    fill = np.zeros((len(P), 3))
    lab_proj = tex.to_lab(np.clip(col_s / shade[:, None], 0, 1))
    good = vis_s
    for mc in np.unique(mcls):
        k = mcls == mc
        s = sw.get(mc) or sw.get(L.SWATCH_FALLBACK.get(mc, "stone"))
        rng = np.random.default_rng(abs(hash(mc)) % 1000)
        f = np.zeros((k.sum(), 3))
        idx = np.nonzero(k)[0]
        for tg in np.unique(tags[k]):
            kk = tags[idx] == tg
            ii = idx[kk]
            off = rng.uniform(0, 7, 3)
            s_t = s
            for pre, swn in tag_sw.items():
                if str(tg).startswith(pre) and swn in sw:
                    s_t = sw[swn]
            raw = s_t.sample(P[ii], N[ii], off)
            if mc in class_sw:      # class-guided synthesis (e.g. ground base: water / grass / gravel)
                for pc, swn in class_sw[mc].items():
                    sel_c = texcls[ii] == pc if pc != "*" else np.zeros(len(ii), bool)
                    if pc.startswith("z<"):
                        sel_c = P[ii, 2] < float(pc[2:])
                    if sel_c.any() and swn in sw:
                        raw[sel_c] = sw[swn].sample(P[ii][sel_c], N[ii][sel_c], off)
            gk = good[ii]
            if mc in class_sw:
                # per painting-class palette inside the tag (water / grass / gravel keep their own colours)
                f_t = np.zeros((len(ii), 3))
                done = np.zeros(len(ii), bool)
                for pc in np.unique(texcls[ii]):
                    sel_c = (texcls[ii] == pc) & gk
                    msk = texcls[ii] == pc
                    if sel_c.sum() > 80:
                        mu_c, sd_c = lab_proj[ii][sel_c].mean(0), lab_proj[ii][sel_c].std(0)
                        sd_c = np.maximum(sd_c, s_t.sd * 0.5)
                        f_t[msk] = tex.colour_match(raw[msk], mu_c, sd_c, raw[msk].mean(0) * 0 + tex.to_lab(raw[msk]).mean(0),
                                                    tex.to_lab(raw[msk]).std(0) + 1e-3, 1.0)
                        done |= msk
                if done.any() and gk.sum() > 150:
                    mu, sd = lab_proj[ii][gk].mean(0), lab_proj[ii][gk].std(0)
                    rest = ~done
                    if rest.any():
                        f_t[rest] = tex.colour_match(raw[rest], mu, np.maximum(sd, s_t.sd * 0.6), s_t.mu, s_t.sd, 1.0)
                    f[kk] = f_t
                    continue
            if gk.sum() > 150:
                mu, sd = lab_proj[ii][gk].mean(0), lab_proj[ii][gk].std(0)
            else:
                gc = good & (mcls == mc)
                if gc.sum() > 150:
                    mu, sd = lab_proj[gc].mean(0), lab_proj[gc].std(0)
                else:
                    mu, sd = L.CLASS_LAB.get(mc, (s.mu, s.sd)) if hasattr(L, "CLASS_LAB") else (s.mu, s.sd)
            sd = np.maximum(sd, s_t.sd * 0.6)
            f[kk] = tex.colour_match(raw, np.asarray(mu), np.asarray(sd), s_t.mu, s_t.sd, 1.0)
        fill[k] = f
    # distinct blocks/planks: per-polygon brightness/warmth jitter; dark mortar backing
    pid = OB[tri] * 1000003 + PI[tri]
    h1 = ((pid * 2654435761) % 1000) / 1000.0
    h2 = ((pid * 40503 + 17) % 997) / 997.0
    jit = 1.0 + getattr(L, "POLY_JITTER", 0.08) * (h1 - 0.5) * 2
    fill = np.clip(fill * jit[:, None] * np.stack([1 + 0.03 * (h2 - 0.5), np.ones_like(h2), 1 - 0.03 * (h2 - 0.5)], 1), 0, 1)
    mort = np.array([str(t).endswith("_mortar") for t in tags])
    if mort.any():
        fill[mort] = np.asarray(getattr(L, "MORTAR_RGB", (0.24, 0.22, 0.19)))
    for pre, rgb in getattr(L, "TAG_RGB", {}).items():
        kk = np.array([str(t).startswith(pre) for t in tags])
        if kk.any():
            fill[kk] = fill[kk] * 0.35 + np.asarray(rgb) * 0.65
    # blend (feathered in texture space)
    a_img = np.zeros(valid.shape)
    a_img[yy, xx] = np.clip((wgt - 0.05) / 0.10, 0, 1)
    a_img = ndi.gaussian_filter(a_img, 1.2) * valid
    a = a_img[yy, xx]
    alb = proj_alb * a[:, None] + fill * (1 - a[:, None])
    out = np.zeros(valid.shape + (3,))
    out[yy, xx] = alb
    out = tex.dilate(out, valid, 8)
    # normal map: luminance high-pass + mortar/grain emphasis per class
    strength = np.zeros(valid.shape)
    st = getattr(L, "NORMAL_STRENGTH", {})
    sv = np.array([st.get(m, 2.0) for m in mcls])
    strength[yy, xx] = sv
    hgt = tex.height_from_albedo(out, valid, 5.0) * strength
    nrm = texproj.height_to_normal(hgt, valid, strength=1.0)
    nrm = tex.dilate(nrm, valid, 8)
    stats = dict(texels=int(len(P)), projected_frac=float((a > 0.5).mean()), seconds=round(time.time() - t0, 1))
    print(f"[{asset}] texture: projected {stats['projected_frac']:.2%} of texels ({stats['seconds']}s)", flush=True)
    texinfo = dict(P=P, alb=alb, valid=valid, yy=yy, xx=xx)
    return out, nrm, stats, texinfo


def transfer_atlas(texinfo, objs, size):
    """LOD1/LOD2 atlas: nearest LOD0 texel colour (KD-tree in world space)."""
    V, T, UV, FN, MC, OB, PI = gather(objs)
    sel = np.nonzero(MC != "card")[0]
    Tx = texproj.rasterize_uv(V, T[sel], UV[sel], size, flat_normals=True)
    yy, xx = np.nonzero(Tx.valid)
    P = Tx.pos[yy, xx] + FN[sel][Tx.tri[yy, xx]] * 0.02
    tree = cKDTree(texinfo["P"])
    d, i = tree.query(P, k=4)
    w = 1.0 / np.maximum(d, 1e-3)
    c = (texinfo["alb"][i] * w[..., None]).sum(1) / w.sum(1, keepdims=True)
    out = np.zeros((size, size, 3))
    out[yy, xx] = c
    return tex.dilate(out, Tx.valid, 6)


def save_jpg(path, arr, q=90):
    Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8)).save(path, quality=q, optimize=True)


def save_png(path, arr):
    a = (np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(a, "RGBA" if a.shape[2] == 4 else "RGB").save(path, optimize=True)


# ----------------------------------------------------------------------------- build
def build(name, it):
    L = importlib.import_module(f"lm_{name}")
    asset = L.ID
    t0 = time.time()
    core.reset()
    crop, ref_mask, bg = reference(L)
    H, W = crop.shape[:2]
    cam, cam_rep = solve_camera(L, asset, it, W, H)
    if hasattr(L, "attach"):
        L.attach(cam, crop, ref_mask)
    card_rgba, card_rects = card_atlas(L)
    geos = {lod: L.build(lod, cam=cam, crop=crop, mask=ref_mask, cards=card_rects) for lod in range(3)}
    P3, p2, _ = L.camera_points()
    camera_overlay(L, asset, it, cam, crop, P3, p2, geos[0]["struct"])
    # ---- materials (images filled after texturing)
    blank = bl.image_from_array(f"{asset}_c", np.full((8, 8, 3), 0.5))
    blank_n = bl.image_from_array(f"{asset}_n", np.full((8, 8, 3), (0.5, 0.5, 1.0)), "Non-Color")
    card_img = bl.image_from_array(f"{asset}_cards", card_rgba, alpha=True) if card_rgba is not None else None
    mats0 = bl.export_materials(asset, blank, blank_n, card_img)
    objs = {}
    tags = {}
    fixed = {}
    for lod in range(3):
        for part in PARTS:
            g = geos[lod].get(part)
            if g is None or not g.F:
                continue
            nm = {"struct": f"{asset}_LOD{lod}", "cloth": f"{asset}_cloth_LOD{lod}",
                  "base": f"{asset}_base" if lod == 0 else f"{asset}_base_LOD{lod}"}[part]
            o, fx, M, Tg = bl.object_from_geo(nm, g, mats0)
            objs[(lod, part)] = o
            tags[(lod, part)] = Tg
            fixed[(lod, part)] = fx
    tris = {}
    for lod in range(3):
        s = core.tri_count(objs[(lod, "struct")]) + (core.tri_count(objs[(lod, "cloth")]) if (lod, "cloth") in objs else 0)
        b = core.tri_count(objs[(lod, "base")]) if (lod, "base") in objs else 0
        tris[f"LOD{lod}"] = dict(structure=s, base=b, total=s + b)
    print(f"[{asset}] tris {tris}", flush=True)
    # ---- UV atlases per LOD (struct + base share one atlas)
    for lod in range(3):
        group = [objs[(lod, p)] for p in PARTS if (lod, p) in objs]
        bl.atlas_uv(group, [fixed[(lod, p)] for p in PARTS if (lod, p) in objs])
        for p in PARTS:
            if (lod, p) in objs:
                bl.restore_fixed_uv(objs[(lod, p)], geos[lod][p])
    # ---- LOD0 texture by projection + fill
    keys0 = [(0, p) for p in PARTS if (0, p) in objs]
    o0 = [objs[k] for k in keys0]
    ftags = [tags[k] for k in keys0]
    alb0, nrm0, tstats, texinfo = texture_atlas(L, asset, it, o0, ftags, cam, crop, ref_mask, W, H,
                                               size=getattr(L, "ATLAS", 2048))
    files = {}
    p_c0 = os.path.join(MASTER, f"{asset}_c.png")
    save_png(p_c0, alb0)
    save_png(os.path.join(MASTER, f"{asset}_n.png"), nrm0)
    files["c0"] = f"{asset}_c.jpg"
    files["n0"] = f"{asset}_n.png"
    save_jpg(os.path.join(RT, files["c0"]), alb0)
    n_small = cv2.resize(nrm0.astype(np.float32), (1024, 1024), interpolation=cv2.INTER_AREA)
    save_png(os.path.join(RT, files["n0"]), n_small)
    lod_tex = {}
    for lod, size in ((1, 1024), (2, 512)):
        keys = [(lod, p) for p in PARTS if (lod, p) in objs]
        a = transfer_atlas(texinfo, [objs[k] for k in keys], size)
        fn = f"{asset}_lod{lod}_c.jpg"
        save_jpg(os.path.join(RT, fn), a)
        save_png(os.path.join(MASTER, f"{asset}_lod{lod}_c.png"), a)
        lod_tex[lod] = a
        files[f"c{lod}"] = fn
    if card_rgba is not None:
        files["cards"] = f"{asset}_cards.png"
        save_png(os.path.join(RT, files["cards"]), card_rgba)
        save_png(os.path.join(MASTER, files["cards"]), card_rgba)
    # ---- real materials per LOD
    img_c0 = bl.image_from_array(f"{asset}_c", alb0)
    img_n0 = bl.image_from_array(f"{asset}_n", n_small, "Non-Color")
    lod_mats = {0: bl.export_materials(asset, img_c0, img_n0, card_img)}
    for lod in (1, 2):
        ic = bl.image_from_array(f"{asset}_lod{lod}_c", lod_tex[lod])
        lod_mats[lod] = bl.export_materials(f"{asset}_lod{lod}", ic, None, card_img)
    for (lod, part), o in objs.items():
        for i, s in enumerate(o.material_slots):
            cls = o.data.materials[i].name.rsplit("_", 1)[-1].split(".")[0]
            o.data.materials[i] = lod_mats[lod][cls]
    # ---- QA main view
    bl.setup_render(16)
    import pblend
    view_objs = [o for k, o in objs.items() if k[0] == 0]
    bl.use_qa(view_objs, 0.35)
    rgba = bl.render_painting_cam(cam, W, H, view_objs, ss=2)
    met = pblend.compare_sheet(crop, ref_mask, rgba, bg, qa_path(asset, it, "main"),
                               f"{asset} v3 iter {it}: art/06 main view, solved camera (rms {cam_rep['rms_px']:.1f}px), "
                               f"LOD0 + base, painted-light k=0.35", scale=2)
    rgba_s = bl.render_painting_cam(cam, W, H, [o for k, o in objs.items() if k[0] == 0 and k[1] != "base"], ss=2)
    met_s = dict(iou_structure_only=float(((rgba_s[..., 3] > 0.5) & ref_mask).sum() / max(1, ((rgba_s[..., 3] > 0.5) | ref_mask).sum())))
    met.update(met_s)
    print(f"[{asset}] MAIN VIEW: IoU {met['iou']:.3f} colour {met['colour_err']:.3f} SSIM {met['ssim']:.3f}", flush=True)
    # ---- insets
    insets = {}
    for key, spec in getattr(L, "INSETS", {}).items():
        sel_objs = [o for k, o in objs.items() if k[0] == 0 and k[1] != "base"] + ([objs[(0, "base")]] if spec.get("base") and (0, "base") in objs else [])
        insets[key] = inset_compare(asset, it, key, spec, sel_objs)
        print(f"[{asset}] inset {key}: IoU {insets[key]['iou']:.3f}", flush=True)
    bl.use_qa(view_objs, 0.35, on=False)
    # ---- wind clip on cloth (morph targets, seamless loop)
    clips = {}
    for lod in range(2):
        if (lod, "cloth") in objs:
            bl.cloth_wind(objs[(lod, "cloth")], getattr(L, "WIND", {}))
            clips["lf_banner_wind"] = {"seconds": 4.5, "loop": True, "type": "morph-target animation (shape keys billow/ripple) on the cloth node",
                                       "node": f"{asset}_cloth_LOD0"}
    # ---- export
    lod_files = {}
    nodes = {}
    for lod in range(3):
        keys = [(lod, p) for p in PARTS if (lod, p) in objs]
        path = os.path.join(RT, f"{asset}.glb" if lod == 0 else f"{asset}_LOD{lod}.glb")
        bl.export_glb(path, [objs[k] for k in keys], asset if lod == 0 else f"{asset}_lod{lod}",
                      anim=(lod, "cloth") in objs and lod < 2)
        ext = {f"{asset}_c": files["c0"], f"{asset}_n": files["n0"], f"{asset}_lod1_c": files["c1"],
               f"{asset}_lod2_c": files["c2"]}
        if "cards" in files:
            ext[f"{asset}_cards"] = files["cards"]
        import glbx
        glbx.externalize(path, ext)
        lod_files[f"LOD{lod}"] = os.path.basename(path)
        nodes[f"LOD{lod}"] = [objs[k].name for k in keys]
    import glbx
    gi = glbx.info(os.path.join(RT, f"{asset}.glb"))
    lo, hi = core.bounds([o for k, o in objs.items() if k[0] == 0 and k[1] != "base"])
    meta = dict(
        id=asset, generation="v3 (blueprint + solved art/06 camera + painting projection)",
        tris={k: v["structure"] for k, v in tris.items()}, tris_detail=tris,
        budget=dict(LOD0=getattr(L, "BUDGET0", 6000), LOD1=1500, LOD2=400,
                    note="structure meshes; the toggleable ground base is counted separately in tris_detail"),
        bones=0, materials=sorted(set(gi["materials"])), glb_images=gi["images"],
        textures={files["c0"]: 2048 if getattr(L, "ATLAS", 2048) == 2048 else getattr(L, "ATLAS"), files["n0"]: 1024,
                  files["c1"]: 1024, files["c2"]: 512, **({files["cards"]: 1024} if "cards" in files else {})},
        texture_mode="external per-asset files next to the GLB (relative URIs); LOD1/LOD2 have their own atlases",
        nodes=nodes, lod_files=lod_files,
        base_node=dict(LOD0=f"{asset}_base", LOD1=f"{asset}_base_LOD1", LOD2=f"{asset}_base_LOD2",
                       note="painted ground patch (dirt/gravel/grass/stones/water) as a separate node; the world may hide it"),
        bounds_m_gltf=[[round(lo[0], 3), round(lo[2], 3), round(-hi[1], 3)], [round(hi[0], 3), round(hi[2], 3), round(-lo[1], 3)]],
        collision=[to_gl_collider(c) for c in L.colliders()],
        collision_note="Godot axes (x, y=up, z), metres, relative to the asset origin; box size = full extents; "
                       "'ramp' = oriented box along the slope; 'cylinder' size = (diameter, height, diameter); yaw about +Y.",
        layout_note="Main GLB = LOD0 at the asset origin; LOD1/LOD2 in <id>_LOD1.glb / <id>_LOD2.glb (same origin).",
        paintedLightMix=0.35,
        paintedLightNote="Textures carry the painted light. Shade as albedo * mix(1, lambert, paintedLightMix) "
                         "(lambert = max(dot(N, L), 0)), as the nature kit (forest_kit.json 'shading').",
        build=f"python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/landmarks/v3/pipeline.py {name}",
        qa=dict(main_view=met, camera=dict(rms_px=round(cam_rep["rms_px"], 2), max_px=round(cam_rep["max_px"], 2),
                                           n_points=cam_rep["n"]), insets=insets, texture=tstats,
                sheets=f"forest_rescue/qa/compare/{asset}/v3_iter{it:02d}_*"),
    )
    if clips:
        meta["clips"] = clips
    meta.update(L.meta_extra())
    core.write_json(os.path.join(RT, f"{asset}.meta.json"), meta)
    core.write_json(qa_path(asset, it, "metrics", "json"), meta["qa"] | dict(tris=tris))
    # ---- LOD lineup + ortho views
    lod_sheet(asset, it, objs)
    for o in bpy.data.objects:
        o.hide_render = False
    core.save_blend(os.path.join(SRC, f"{asset}.blend"))
    print(f"[{asset}] done in {time.time() - t0:.0f}s", flush=True)
    return meta


PARTS = ("struct", "cloth", "base")


def to_gl_collider(c):
    x, y, z = c["centre"]
    sx, sy, sz = c["size"]
    return {"type": c["type"], "centre": [round(x, 3), round(z, 3), round(-y, 3)],
            "size": [round(sx, 3), round(sz, 3), round(sy, 3)], "yaw_deg": round(math.degrees(c.get("yaw", 0.0)), 1)}


def inset_compare(asset, it, key, spec, objs):
    import pblend
    img = sheet()
    x0, y0, x1, y1 = spec["box"]
    crop = img[y0:y1, x0:x1]
    bg = refs.border_color(crop, width=2)
    m = refs.silhouette(crop, bg=bg, thresh=spec.get("thresh", 0.10), keep="all", min_area=20,
                        fill_holes=spec.get("fill", 60), blur=0.8, open_px=0, close_px=1)
    rgba = bl.ortho_render(objs, spec["dir"], res=1200)
    ry, rx = np.nonzero(m)
    bx0, by0, bx1, by1 = rx.min(), ry.min(), rx.max() + 1, ry.max() + 1
    rw, rh = bx1 - bx0, by1 - by0
    S = 4
    canvas = np.zeros((crop.shape[0] * S, crop.shape[1] * S, 4), np.float32)
    if spec.get("fit", "width") == "width":
        s = rw * S / rgba.shape[1]
    else:
        s = rh * S / rgba.shape[0]
    nw, nh = max(1, int(round(rgba.shape[1] * s))), max(1, int(round(rgba.shape[0] * s)))
    sub = cv2.resize(rgba.astype(np.float32), (nw, nh), interpolation=cv2.INTER_AREA)
    ox = int(round((bx0 + bx1) / 2 * S - nw / 2))
    oy = int(round(by1 * S - nh))
    ys0, xs0 = max(0, oy), max(0, ox)
    ys1, xs1 = min(canvas.shape[0], oy + nh), min(canvas.shape[1], ox + nw)
    canvas[ys0:ys1, xs0:xs1] = sub[ys0 - oy:ys1 - oy, xs0 - ox:xs1 - ox]
    big = cv2.resize(crop.astype(np.float32), (crop.shape[1] * S, crop.shape[0] * S), interpolation=cv2.INTER_CUBIC)
    bm = cv2.resize(m.astype(np.uint8), (crop.shape[1] * S, crop.shape[0] * S), interpolation=cv2.INTER_NEAREST) > 0
    met = pblend.compare_sheet(big.astype(np.float64), bm, canvas.astype(np.float64), bg, qa_path(asset, it, f"inset_{key}"),
                               f"{asset} inset '{key}' vs art/06 (orthographic, scale fitted to the inset {spec.get('fit', 'width')})",
                               scale=1)
    return met


def lod_sheet(asset, it, objs):
    import pblend
    shots = []
    for lod in range(3):
        sel = [objs[(lod, p)] for p in PARTS if (lod, p) in objs]
        bl.use_qa(sel, 0.35)
        d = (math.sin(math.radians(225)) * math.cos(math.radians(38)), math.cos(math.radians(225)) * math.cos(math.radians(38)),
             -math.sin(math.radians(38)))
        rgba = bl.ortho_render(sel, (0.62, 0.55, -0.56), res=700)
        bl.use_qa(sel, 0.35, on=False)
        shots.append(rgba)
    H = 360
    panels = []
    for lod, r in enumerate(shots):
        r = cv2.resize(r.astype(np.float32), (max(1, int(r.shape[1] * H / r.shape[0])), H), interpolation=cv2.INTER_AREA)
        c = r[..., :3] * r[..., 3:4] + np.array([0.55, 0.6, 0.45]) * (1 - r[..., 3:4])
        u8 = (np.clip(c, 0, 1) * 255).astype(np.uint8)
        panels.append(pblend.label(u8, f"LOD{lod}"))
    Image.fromarray(np.concatenate(panels, 1)).save(qa_path(asset, it, "lods"))


if __name__ == "__main__":
    args = sys.argv[1:]
    it = int(args[args.index("--iter") + 1]) if "--iter" in args else 1
    for nm in args[0].split(","):
        build(nm, it)
