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
    import cv2
    maps = []
    for v in views:
        m = v.mask
        if dilate_px:
            m = ndi.binary_dilation(m, iterations=int(dilate_px))
        dpos = ndi.distance_transform_edt(~m)
        dneg = ndi.distance_transform_edt(m)
        maps.append(((dpos - dneg) / v.ppm).astype(np.float32))

    def fn(x, z):
        x = np.asarray(x, float)
        z = np.asarray(z, float)
        shp = x.shape
        P = np.stack([x.ravel(), np.zeros(x.size), z.ravel()], -1)
        out = np.full(x.size, -1e3)
        for v, sd in zip(views, maps):
            u, vv, _ = v.project(P)
            s = cv2.remap(sd, u.astype(np.float32).reshape(-1, 1), vv.astype(np.float32).reshape(-1, 1),
                          cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0.5).ravel()
            out = np.maximum(out, s)
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
