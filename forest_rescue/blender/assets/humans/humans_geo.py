"""Geometry assembly helpers: pieces (numpy meshes with UVs, class, skin rule, budget) and
conversion to Blender objects, own solidify (inner shell on its own UV island), SDF shells for
hair/beard/headwear, and the per-character context passed to spec garment builders."""
import math

import numpy as np
from scipy import ndimage as ndi

from frlib import sdf as fsdf

import humans_cloth as C
import humans_sdf as H


class Piece:
    """A mesh part: verts (n,3), faces (list of index lists), uvs (per face list of (u,v)),
    cls (surface class), rule (skinning rule dict), name."""

    def __init__(self, name, verts, faces, uvs, cls, rule=None, tri_budget=None, smooth=True, meta=None):
        self.name = name
        self.verts = np.asarray(verts, float)
        self.faces = [list(map(int, f)) for f in faces]
        self.uvs = [list(u) for u in uvs]
        self.cls = cls
        self.rule = rule or {"type": "body"}
        self.tri_budget = tri_budget
        self.smooth = smooth
        self.meta = meta or {}

    @property
    def ntris(self):
        return sum(len(f) - 2 for f in self.faces)


def face_normals(V, faces):
    out = []
    for f in faces:
        p = V[f]
        n = np.zeros(3)
        for i in range(len(f)):
            n += np.cross(p[i], p[(i + 1) % len(f)])
        out.append(n / max(np.linalg.norm(n), 1e-12))
    return np.array(out)


def vertex_normals(V, faces):
    fn = face_normals(V, faces)
    vn = np.zeros_like(V)
    for f, n in zip(faces, fn):
        vn[f] += n
    return vn / np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)


def orient_outward(V, faces, uvs, center_fn):
    """Flip faces whose normal points toward center_fn(p) (axis/body centre)."""
    fn = face_normals(V, faces)
    out_f, out_u = [], []
    for f, u, n in zip(faces, uvs, fn):
        c = V[f].mean(0)
        if np.dot(n, c - center_fn(c)) < 0:
            out_f.append(f[::-1])
            out_u.append(u[::-1])
        else:
            out_f.append(f)
            out_u.append(u)
    return out_f, out_u


def solidify(V, faces, uvs, thickness, inner_uv_scale=0.5, rim=True, offset=1.0):
    """Shell from an oriented open sheet: outer = V + n*t*offset_frac, inner = V - n*t*(1-...),
    inner faces reversed with their own UV island (shifted, scaled), rim quads on boundary edges."""
    V = np.asarray(V, float)
    vn = vertex_normals(V, faces)
    a = thickness * (0.5 + 0.5 * offset)
    b = thickness - a
    Vo = V + vn * a
    Vi = V - vn * b
    n = len(V)
    Vall = np.concatenate([Vo, Vi])
    F, U = [], []
    umax = max(max(p[0] for p in u) for u in uvs) if uvs else 1.0
    umin = min(min(p[0] for p in u) for u in uvs) if uvs else 0.0
    for f, u in zip(faces, uvs):
        F.append(list(f))
        U.append(list(u))
        F.append([i + n for i in f[::-1]])
        U.append([((p[0] - umin) * inner_uv_scale + (umax - umin) + 0.05, p[1] * inner_uv_scale) for p in u[::-1]])
    if rim:
        edges = {}
        for f in faces:
            for i in range(len(f)):
                e = (f[i], f[(i + 1) % len(f)])
                key = tuple(sorted(e))
                edges.setdefault(key, []).append(e)
        L = 0.0
        for key, lst in edges.items():
            if len(lst) == 1:
                i0, i1 = lst[0]
                F.append([i1, i0, i0 + n, i1 + n])
                el = float(np.linalg.norm(V[i1] - V[i0]))
                U.append([(L, -2.0), (L + el, -2.0), (L + el, -2.0 - thickness), (L, -2.0 - thickness)])
                L += el
    return Vall, F, U


def piece_from_drape(name, D, cls, thickness, rule, center_fn, inner_uv_scale=0.5, rim=True):
    V, F, U = C.sheet_mesh(D)
    # drop unused vertices (masked grid)
    used = sorted({i for f in F for i in f})
    remap = {o: i for i, o in enumerate(used)}
    V = V[used]
    F = [[remap[i] for i in f] for f in F]
    F, U = orient_outward(V, F, U, center_fn)
    if thickness > 0:
        V, F, U = solidify(V, F, U, thickness, inner_uv_scale=inner_uv_scale, rim=rim)
    return Piece(name, V, F, U, cls, rule)


def merge_pieces(name, pieces, cls=None, rule=None):
    V, F, U = [], [], []
    base = 0
    uoff = 0.0
    for p in pieces:
        V.append(p.verts)
        for f, u in zip(p.faces, p.uvs):
            F.append([i + base for i in f])
            U.append([(a + uoff, b) for a, b in u])
        umax = max(max(q[0] for q in u) for u in p.uvs) if p.uvs else 0
        uoff += umax + 0.05
        base += len(p.verts)
    return Piece(name, np.concatenate(V), F, U, cls or pieces[0].cls, rule or pieces[0].rule)


# --------------------------------------------------------------------------- SDF shells (hair etc.)

def sdf_piece(name, prims, lo, hi, voxel, cls, rule, extra=None, smooth=0.6, level=0.0, intersect=None):
    """Mesh the smooth union of prims (+ optional callable extra(F) to post-process the field)."""
    F = fsdf.Field(lo, hi, voxel)
    for p in prims:
        if not getattr(p, "geom", True):
            continue
        F.apply(p, op=getattr(p, "op", "union"), k=p.k)
    if intersect is not None:
        F.intersect(intersect, k=0.0)
    if extra is not None:
        extra(F)
    if smooth:
        F.smooth(smooth)
    if (F.d < level).sum() == 0:
        return None
    v, f = F.mesh(level=level)
    return Piece(name, v, f.tolist(), [[(0, 0)] * 3 for _ in range(len(f))], cls, rule, meta={"sdf": True})


class FieldFn:
    """Callable SDF sampler from a dense Field (trilinear), safe outside (returns large)."""

    def __init__(self, F):
        self.F = F

    def __call__(self, P):
        P = np.asarray(P, float)
        shp = P.shape[:-1]
        Q = P.reshape(-1, 3)
        d = self.F.sample(Q)
        outside = np.any((Q < self.F.lo) | (Q > self.F.lo + (self.F.n - 1) * self.F.voxel), axis=1)
        d = np.where(outside, 1.0, d)
        return d.reshape(shp)


def parts_field(parts, lo, hi, voxel, names=None, exclude=None):
    F = fsdf.Field(lo, hi, voxel)
    for p in parts:
        if not getattr(p, "geom", True) or getattr(p, "op", "union") != "union":
            continue
        nm = getattr(p, "name", "")
        if names is not None and not any(nm.startswith(n) for n in names):
            continue
        if exclude is not None and any(nm.startswith(n) for n in exclude):
            continue
        F.apply(p, op="union", k=p.k)
    return F


def hull_xz_fn(views, dilate_px=0.0):
    """2-D signed distance (m) to the intersection of the views' silhouettes at (x, z)."""
    maps = [H.smooth_sdf_2d(v.mask, v.ppm, dilate_px=dilate_px) for v in views]

    def fn(x, z):
        x = np.asarray(x, float)
        z = np.asarray(z, float)
        shp = x.shape
        P = np.stack([x.ravel(), np.zeros(x.size), z.ravel()], -1)
        out = np.full(x.size, -1e3)
        for v, (sd, up) in zip(views, maps):
            u, vv, _ = v.project(P)
            out = np.maximum(out, H.sample_sdf_2d(sd, up, u, vv).ravel())
        return out.reshape(shp)
    return fn


def hull_edges(hull_fn, z, x_from=0.0, xmax=0.6, step=0.002):
    """Left(+x) and right(-x) boundary of the hull run containing x_from at height z."""
    xs = np.arange(0, xmax, step)
    out = []
    for sg in (1, -1):
        d = hull_fn(x_from + sg * xs, np.full_like(xs, z))
        ins = d < 0
        k = 0
        while k + 1 < len(xs) and ins[k + 1]:
            k += 1
        out.append(x_from + sg * xs[k])
    return out[0], out[1]


class Ctx:
    """Everything a spec's garment builder needs."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


# --------------------------------------------------------------------------- hair helpers

def head_frame_point(lm, x, y, z):
    return lm["origin"] + np.array([x, y, z]) * lm["scale"]


def curls(lm, head_fn, region_fn, count, rmin, rmax, lift, seed=0, bone="Head", cls="hair", jitter=1.0,
          lo=None, hi=None):
    """Spheres scattered on the scalp surface inside region_fn(P)<0 for curly/lumpy hair."""
    rng = np.random.default_rng(seed)
    s = lm["scale"]
    out = []
    tries = 0
    c0 = lm["origin"] + np.array([0, 0.085, 0.01]) * s
    while len(out) < count and tries < count * 60:
        tries += 1
        d = rng.normal(size=3)
        d[2] = abs(d[2]) * 1.2 + 0.1 * d[2]
        d /= np.linalg.norm(d)
        p = C.surface_point(head_fn, c0, d, rmax=0.25, step=0.002)
        if region_fn(p[None])[0] > 0:
            continue
        r = rng.uniform(rmin, rmax)
        out.append(H.tag(fsdf.sphere(p + d * (lift + r * 0.25) * jitter, r), cls=cls, bone=bone, k=0.006))
    return out


def ring_on_limb(fn, a, b, t, n=24, clearance=0.004, rmax=0.2):
    """Closed ring hugging a limb at parameter t along a->b; returns points, outward normals."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    e = (b - a) / np.linalg.norm(b - a)
    ref = np.array([0, 1.0, 0]) if abs(e[1]) < 0.9 else np.array([1.0, 0, 0])
    u = np.cross(e, ref)
    u /= np.linalg.norm(u)
    w = np.cross(e, u)
    c = a + (b - a) * t
    pts, nrm = [], []
    for k in range(n):
        ang = 2 * math.pi * k / n
        d = math.cos(ang) * u + math.sin(ang) * w
        p = C.surface_point(fn, c, d, rmax=rmax, step=0.0015, clearance=clearance)
        pts.append(p)
        nrm.append(d)
    return np.array(pts), np.array(nrm)


def band_piece(name, pts, nrm, width, thick, cls, rule, closed=False, segs_w=1, lift=0.0):
    P = np.asarray(pts, float) + np.asarray(nrm, float) * lift
    V, F, U = C.band(P, nrm, width, closed=closed, segs_w=segs_w)
    nn = np.asarray(nrm, float)
    nn_rep = np.tile(nn, (segs_w + 1, 1))
    cen = V - nn_rep * 0.05

    def cfn(c, V=V, cen=cen):
        i = int(np.argmin(np.linalg.norm(V - c, axis=1)))
        return cen[i]
    F, U = orient_outward(V, F, U, cfn)
    if thick > 0:
        V, F, U = solidify(V, F, U, thick, inner_uv_scale=0.6)
    return Piece(name, V, F, U, cls, rule)


def tube_piece(name, pts, radius, cls, rule, sides=8, closed=False, caps=True):
    V, F, U = C.tube(pts, radius, sides=sides, closed=closed, caps=caps)
    return Piece(name, V, F, U, cls, rule)


def box_piece(name, center, size, rot, cls, rule, bevel=0.35, segs=1):
    V, F, U = C.rbox(center, size, rot=rot, bevel=bevel, segs=segs)
    return Piece(name, V, F, U, cls, rule)


def lathe_piece(name, profile, origin, axis, cls, rule, sides=16, ref=None):
    V, F, U = C.lathe(profile, origin, axis, sides=sides, ref=ref)
    return Piece(name, V, F, U, cls, rule)


def rot_from(x_axis, z_axis):
    """3x3 rotation (columns = local x,y,z) from desired local x and z directions."""
    x = np.asarray(x_axis, float)
    x /= np.linalg.norm(x)
    z = np.asarray(z_axis, float)
    z = z - np.dot(z, x) * x
    z /= np.linalg.norm(z)
    y = np.cross(z, x)
    return np.stack([x, y, z], 1)


def curve_on_body(fn, center_xy, thetas, zs, clearance=0.004, smooth=1):
    """Polyline hugging the body along (theta, z) samples (rays from the vertical axis)."""
    th = np.asarray(thetas, float)
    zz = np.asarray(zs, float)
    r = C.ray_radius(fn, center_xy, th, zz, clearance=clearance)
    r = np.where(np.isfinite(r), r, np.nanmedian(r))
    if smooth:
        r = ndi.gaussian_filter1d(r, smooth, mode="nearest")
    P = np.stack([center_xy[0] + r * np.sin(th), center_xy[1] - r * np.cos(th), zz], -1)
    N = sdf_normals(fn, P)
    return P, N


def sdf_normals(fn, P, h=0.004):
    P = np.asarray(P, float)
    g = np.zeros_like(P)
    for k in range(3):
        d = np.zeros(3)
        d[k] = h
        g[:, k] = fn(P + d) - fn(P - d)
    n = np.linalg.norm(g, axis=1, keepdims=True)
    return g / np.maximum(n, 1e-9)


def hair_region(lm, front=0.064, temple_drop=0.30, side=0.018, back=-0.070, side_y=(0.03, 0.13), noise=0.0,
                seed=0, ear_clear=True):
    """Signed region function (negative inside hair) in head-frame units."""
    O = lm["origin"]
    s = lm["scale"]
    rng = np.random.default_rng(seed)
    ph = rng.uniform(0, 6.28, 6)

    def fn(P):
        Q = (np.asarray(P, float) - O) / s
        x, y, z = Q[..., 0], Q[..., 1], Q[..., 2]
        hz_front = front - temple_drop * np.maximum(np.abs(x) - 0.030, 0)
        t1 = np.clip((y - side_y[0]) / 0.03, 0, 1)
        t2 = np.clip((y - side_y[1]) / 0.03, 0, 1)
        hz = hz_front * (1 - t1) + side * t1
        hz = hz * (1 - t2) + back * t2
        if noise:
            hz = hz + noise * (np.sin(x * 140 + ph[0]) * np.sin(y * 120 + ph[1]) + 0.5 * np.sin(x * 260 + ph[2]))
        return (hz - z) * s
    return fn


def wraps_piece(name, fn, J, S_, z0, z1, turns=4, width=0.022, thick=0.003, cls="leather", cross=True, seed=0):
    """Leg wraps / bindings: helical bands (and a counter-helix for criss-cross) on the shin."""
    an = J[f"{S_}Foot"]
    kn = J[f"{S_}LowerLeg"]
    pieces = []
    for k, sg in enumerate((1, -1) if cross else (1,)):
        n = int(18 * turns)
        t = np.linspace(0, 1, n)
        z = z0 + (z1 - z0) * t
        a = sg * 2 * math.pi * turns * t + k * 1.3
        f = (z - an[2]) / max(kn[2] - an[2], 1e-3)
        cx = an[0] + (kn[0] - an[0]) * f
        cy = an[1] + (kn[1] - an[1]) * f
        pts, nrm = [], []
        for i in range(n):
            d = np.array([math.cos(a[i]), math.sin(a[i]), 0.0])
            c = np.array([cx[i], cy[i], z[i]])
            p = C.surface_point(fn, c, d, rmax=0.16, step=0.0015, clearance=0.002)
            pts.append(p)
            nrm.append(d)
        pieces.append(band_piece(f"{name}_{k}", np.array(pts), np.array(nrm), width, thick, cls,
                                 {"type": "body"}))
    return merge_pieces(name, pieces)


def laces_piece(name, fn, J, S_, z0, z1, n=6, half=0.022, r=0.0025, cls="leather"):
    """Criss-cross boot laces on the front of the shaft."""
    an = J[f"{S_}Foot"]
    kn = J[f"{S_}LowerLeg"]
    pts = []
    for i in range(n + 1):
        z = z0 + (z1 - z0) * i / n
        f = (z - an[2]) / max(kn[2] - an[2], 1e-3)
        c = an + (kn - an) * f
        for sx in ((-1, 1) if i % 2 == 0 else (1, -1)):
            d = np.array([sx * half * 8, -1.0, 0.0])
            d /= np.linalg.norm(d)
            p = C.surface_point(fn, np.array([c[0], c[1], z]), d, rmax=0.16, step=0.0015, clearance=0.001)
            pts.append(p)
    return tube_piece(name, np.array(pts), r, cls, {"type": "body"}, sides=5)
