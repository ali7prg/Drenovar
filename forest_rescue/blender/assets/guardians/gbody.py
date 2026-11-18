"""Guardian body modelling: lofted torso, bone-attached SDF parts, tubes/clumps/claws/horns,
fast silhouette rasterisation for shape iterations (no bpy needed here).
"""
import math

import cv2
import numpy as np
from scipy.spatial import cKDTree

from frlib import sdf


# --------------------------------------------------------------------------- SDF parts

class Part:
    """An SDF primitive in bind-pose world coordinates owned by a bone (for posing/skinning)."""

    def __init__(self, prim, bone, k=0.04, op="union", tag=""):
        self.prim = prim
        self.bone = bone
        self.k = k
        self.op = op
        self.tag = tag


def loft(Y, zt, zb, w, bone=None, name="loft"):
    """Elliptic cross-sections along world Y: centre (0, y, (zt+zb)/2), half-height (zt-zb)/2,
    half-width w.  Arrays sorted by Y.  Outside the Y range the section is capped."""
    Y = np.asarray(Y, float)
    zt = np.asarray(zt, float)
    zb = np.asarray(zb, float)
    w = np.asarray(w, float)

    def fn(P):
        y = P[..., 1]
        yc = np.clip(y, Y[0], Y[-1])
        top = np.interp(yc, Y, zt)
        bot = np.interp(yc, Y, zb)
        ww = np.maximum(np.interp(yc, Y, w), 1e-3)
        zc = (top + bot) * 0.5
        hh = np.maximum((top - bot) * 0.5, 1e-3)
        x = P[..., 0]
        z = P[..., 2] - zc
        k0 = np.sqrt((x / ww) ** 2 + (z / hh) ** 2)
        k1 = np.sqrt((x / ww ** 2) ** 2 + (z / hh ** 2) ** 2)
        d2 = k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)
        dy = np.maximum(np.maximum(Y[0] - y, y - Y[-1]), 0.0)
        return np.where(dy > 0, np.where(d2 > 0, np.sqrt(d2 * d2 + dy * dy), dy), d2)

    lo = np.array([-w.max(), Y[0], zb.min()]) - 0.02
    hi = np.array([w.max(), Y[-1], zt.max()]) + 0.02
    return sdf.Prim(fn, lo, hi, bone=bone, name=name)


def stretch(prim, factor, axis=(1, 0, 0), center=None):
    """Scale a prim by `factor` along `axis` about `center` (approximate distance)."""
    ax = np.asarray(axis, float)
    ax = ax / np.linalg.norm(ax)
    c = (prim.lo + prim.hi) * 0.5 if center is None else np.asarray(center, float)
    f = float(factor)

    def fn(P):
        q = P - c
        h = q @ ax
        q2 = q + (h / f - h)[..., None] * ax
        return prim.fn(q2 + c) * min(f, 1.0)

    lo = c + (prim.lo - c) + np.minimum(0, (prim.lo - c) @ ax * (f - 1)) * np.abs(ax)
    hi = c + (prim.hi - c) + np.maximum(0, (prim.hi - c) @ ax * (f - 1)) * np.abs(ax)
    ext = (prim.hi - prim.lo) * 0.5 * max(f, 1.0)
    return sdf.Prim(fn, np.minimum(lo, c - ext), np.maximum(hi, c + ext), bone=prim.bone, name=prim.name,
                    k=prim.k, op=prim.op)


def transformed(prim, T):
    """Prim moved by 4x4 T (bind -> posed): fn'(P) = fn(T^-1 P)."""
    Ti = np.linalg.inv(T)
    R, t = Ti[:3, :3], Ti[:3, 3]

    def fn(P):
        return prim.fn(P @ R.T + t)

    corners = np.array([[x, y, z] for x in (prim.lo[0], prim.hi[0]) for y in (prim.lo[1], prim.hi[1])
                        for z in (prim.lo[2], prim.hi[2])])
    cw = corners @ T[:3, :3].T + T[:3, 3]
    return sdf.Prim(fn, cw.min(0), cw.max(0), bone=prim.bone, name=prim.name, k=prim.k, op=prim.op)


def build_field(parts, voxel, pose=None, sk=None, pad=0.08, smooth_sigma=0.0, bounds=None):
    """Union/subtract all parts into one Field.  With pose+sk, each part is moved rigidly by its
    owner bone (pose_b @ rest_b^-1) — used to rebuild the body in a reference stance."""
    prims = []
    for pt in parts:
        p = pt.prim
        if pose is not None and pt.bone is not None:
            T = pose[pt.bone] @ np.linalg.inv(sk.rest[pt.bone])
            if not np.allclose(T, np.eye(4), atol=1e-7):
                p = transformed(p, T)
        prims.append((p, pt))
    if bounds is None:
        lo = np.min([p.lo for p, _ in prims if True], axis=0) - pad
        hi = np.max([p.hi for p, _ in prims], axis=0) + pad
        lo[2] = max(lo[2], -0.05)
    else:
        lo, hi = bounds
    F = sdf.Field(lo, hi, voxel)
    for p, pt in prims:
        if pt.op == "union":
            F.apply(p, op="union", k=pt.k)
    for p, pt in prims:
        if pt.op == "subtract":
            F.apply(p, op="subtract", k=pt.k)
    if smooth_sigma:
        F.smooth(smooth_sigma)
    return F


# --------------------------------------------------------------------------- curves & tubes

def catmull(points, n):
    """Catmull-Rom resample of a polyline to n points (uniform in parameter)."""
    P = np.asarray(points, float)
    if len(P) == 2:
        t = np.linspace(0, 1, n)[:, None]
        return P[0] * (1 - t) + P[1] * t
    P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    segs = len(P) - 3
    out = []
    for i in range(n):
        u = i / (n - 1) * segs
        s = min(int(u), segs - 1)
        t = u - s
        p0, p1, p2, p3 = P[s], P[s + 1], P[s + 2], P[s + 3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                          (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    return np.array(out)


def resample_by_length(P, n):
    P = np.asarray(P, float)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, i]) for i in range(3)], 1)


def frames(P, up=(0, 0, 1)):
    """Parallel-transport frames (T, N, B) along a polyline."""
    P = np.asarray(P, float)
    T = np.gradient(P, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    up = np.asarray(up, float)
    N = np.zeros_like(P)
    n0 = up - np.dot(up, T[0]) * T[0]
    if np.linalg.norm(n0) < 1e-6:
        n0 = np.array([1.0, 0, 0]) - T[0][0] * T[0]
    N[0] = n0 / np.linalg.norm(n0)
    for i in range(1, len(P)):
        v = N[i - 1] - np.dot(N[i - 1], T[i]) * T[i]
        nv = np.linalg.norm(v)
        N[i] = v / nv if nv > 1e-9 else N[i - 1]
    B = np.cross(T, N)
    return T, N, B


def tube(points, rx, ry=None, sides=6, up=(0, 0, 1), tip=True, cap_base=False, twist=0.0,
         profile=None, metric=True):
    """Tube along a polyline.  rx/ry: per-point radii along N/B (ry=None -> round).

    Returns verts (V,3), faces (F,3) tris, uvs per loop (F,3,2) with u around / v along.
    tip=True: last point collapses to a single apex vertex.  profile: optional per-side radial
    multipliers (len sides) for ridged / angular cross-sections.
    """
    P = np.asarray(points, float)
    n = len(P)
    rx = np.broadcast_to(np.asarray(rx, float), (n,))
    ry = rx if ry is None else np.broadcast_to(np.asarray(ry, float), (n,))
    T, N, B = frames(P, up)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    vcoord = np.concatenate([[0], np.cumsum(seg)])
    vcoord = vcoord / max(vcoord[-1], 1e-9)
    ring_n = n - 1 if tip else n
    verts = []
    uvs_v = []
    for i in range(ring_n):
        for s in range(sides + 1):
            a = 2 * math.pi * s / sides + twist * vcoord[i]
            m = 1.0 if profile is None else profile[s % sides]
            verts.append(P[i] + (N[i] * math.cos(a) * rx[i] + B[i] * math.sin(a) * ry[i]) * m)
            uvs_v.append((s / sides, vcoord[i]))
    faces = []
    for i in range(ring_n - 1):
        for s in range(sides):
            a = i * (sides + 1) + s
            b = a + 1
            c = a + sides + 1
            d = c + 1
            faces.append((a, c, b))
            faces.append((b, c, d))
    if tip:
        apex = len(verts)
        verts.append(P[-1])
        uvs_v.append((0.5, 1.0))
        i = ring_n - 1
        for s in range(sides):
            a = i * (sides + 1) + s
            faces.append((a, apex, a + 1))
    if cap_base:
        cidx = len(verts)
        verts.append(P[0])
        uvs_v.append((0.5, 0.0))
        for s in range(sides):
            faces.append((cidx, s, s + 1))
    verts = np.array(verts)
    faces = np.array(faces, dtype=np.int64)
    uvv = np.array(uvs_v)
    if metric:   # UV units in metres (circumference x length) so island scaling is uniform
        circ = 2 * math.pi * float(np.mean(np.maximum(rx, ry)[: max(1, ring_n)]))
        length = float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())
        uvv = uvv * np.array([max(circ, 1e-4), max(length, 1e-4)])
    uvs = uvv[faces]
    return verts, faces, uvs


def merge(meshes):
    """Concatenate [(verts, faces, uvs[, extra dict])] -> verts, faces, uvs, part_ids."""
    V, F, U, ids = [], [], [], []
    off = 0
    for i, m in enumerate(meshes):
        v, f, u = m[0], m[1], m[2]
        V.append(v)
        F.append(f + off)
        U.append(u)
        ids.append(np.full(len(f), i))
        off += len(v)
    return np.vstack(V), np.vstack(F), np.vstack(U), np.concatenate(ids)


def uv_sphere(c, r, nu=8, nv=6, scale=(1, 1, 1)):
    verts, uv = [], []
    for j in range(nv + 1):
        th = math.pi * j / nv
        for i in range(nu + 1):
            ph = 2 * math.pi * i / nu
            d = np.array([math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)])
            verts.append(np.asarray(c) + d * r * np.asarray(scale))
            uv.append((i / nu, 1 - j / nv))
    faces = []
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            b, c2, d = a + 1, a + nu + 1, a + nu + 2
            if j > 0:
                faces.append((a, c2, b))
            if j < nv - 1:
                faces.append((b, c2, d))
    verts = np.array(verts)
    faces = np.array(faces)
    uvm = np.array(uv) * np.array([2 * math.pi * r, math.pi * r])
    return verts, faces, uvm[faces]


# --------------------------------------------------------------------------- silhouettes

def silhouette(verts, faces, view):
    """Binary silhouette of a mesh in a refs.View crop (OpenCV polygon fill)."""
    W, H = view.size
    u, v, _ = view.project(verts)
    pts = np.stack([u, v], 1)
    tri = pts[faces]
    m = np.zeros((H, W), np.uint8)
    polys = np.round(tri * 16).astype(np.int32)
    cv2.fillPoly(m, list(polys), 1, lineType=cv2.LINE_8, shift=4)
    return m.astype(bool)


def iou(a, b):
    return float(np.logical_and(a, b).sum()) / max(float(np.logical_or(a, b).sum()), 1.0)


def diff_image(view, rmask):
    ref = view.image
    diff = np.repeat((ref.mean(axis=2, keepdims=True) * 0.5 + 0.35), 3, axis=2)
    both = view.mask & rmask
    diff[both] = diff[both] * 0.5 + np.array([0.15, 0.55, 0.15]) * 0.5
    diff[view.mask & ~rmask] = (0.85, 0.15, 0.15)
    diff[~view.mask & rmask] = (0.15, 0.3, 0.9)
    return diff


# --------------------------------------------------------------------------- hull tests

def inside_masks(P, views, dilate=0):
    """Boolean: world points project inside every view mask."""
    ok = np.ones(len(P), bool)
    for v in views:
        m = v.mask
        H, W = m.shape
        u, vv, _ = v.project(P)
        ui = np.round(u).astype(int)
        vi = np.round(vv).astype(int)
        inb = (ui >= 0) & (ui < W) & (vi >= 0) & (vi < H)
        r = np.zeros(len(P), bool)
        r[inb] = m[vi[inb], ui[inb]]
        ok &= r
    return ok


def march_length(root, direction, views, max_len, step=0.01, bend=None):
    """Distance along direction (optionally bending) until the point leaves any view mask."""
    d = np.asarray(direction, float)
    d = d / np.linalg.norm(d)
    p = np.asarray(root, float).copy()
    L = 0.0
    while L < max_len:
        q = p + d * step
        if not inside_masks(q[None], views)[0]:
            break
        p = q
        L += step
        if bend is not None:
            d = d + np.asarray(bend) * step
            d /= np.linalg.norm(d)
    return L


# --------------------------------------------------------------------------- surface sampling

def sample_surface(verts, faces, n, rng, weight_fn=None, normals=None):
    """Area-weighted random surface samples: (points, normals, face_ids)."""
    v0, v1, v2 = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    cr = np.cross(v1 - v0, v2 - v0)
    area = 0.5 * np.linalg.norm(cr, axis=1)
    fn = cr / np.maximum(np.linalg.norm(cr, axis=1, keepdims=True), 1e-12)
    c = (v0 + v1 + v2) / 3
    w = area.copy()
    if weight_fn is not None:
        w *= np.maximum(weight_fn(c, fn), 0)
    if w.sum() <= 0:
        return np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0, int)
    p = w / w.sum()
    fid = rng.choice(len(faces), size=n, p=p)
    a = rng.random(n)
    b = rng.random(n)
    flip = a + b > 1
    a[flip], b[flip] = 1 - a[flip], 1 - b[flip]
    pts = v0[fid] + (v1[fid] - v0[fid]) * a[:, None] + (v2[fid] - v0[fid]) * b[:, None]
    return pts, fn[fid], fid


def poisson_thin(points, min_dist, rng=None):
    """Greedy dart-throw thinning: keep points at least min_dist apart (array or scalar)."""
    md = np.broadcast_to(np.asarray(min_dist, float), (len(points),))
    order = np.arange(len(points)) if rng is None else rng.permutation(len(points))
    keep = []
    tree_pts = []
    for i in order:
        p = points[i]
        if tree_pts:
            d = np.linalg.norm(np.asarray(tree_pts) - p, axis=1)
            if (d < md[i]).any():
                continue
        keep.append(i)
        tree_pts.append(p)
    return np.array(keep, dtype=int)
