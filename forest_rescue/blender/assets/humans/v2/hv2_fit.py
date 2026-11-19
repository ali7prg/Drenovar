"""Image-based fitting for the 9 «Лес потерянных» humans (v2).

Reference views come from the painted turnaround sheets (front + back, free A-pose drawings).
Both masks are rasterised into one world X-Z grid (Blender: X = character's left, Z up, metres,
character faces -Y).  The *consensus* silhouette (signed-distance average of the front mask and
the registered back mask) drives every width measurement and the final visual-hull clip, so the
model's silhouette sits between the two paintings.

Depth (Y) is never invented freely: every part takes its in-plane half-width from the painted
silhouette and its depth from an anatomical ratio table (template), as asked for when the sheet
has no side view.
"""
import math
import os
import sys

import numpy as np
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))                    # humans/ (humans_refs)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))  # forest_rescue/blender

import humans_refs as HR  # noqa: E402

RES = 0.002          # world grid (m)
X0, X1 = -0.72, 0.72
Z0, Z1 = -0.02, 2.06


class Grid:
    def __init__(self, res=RES):
        self.res = res
        self.xs = np.arange(X0, X1 + 1e-9, res)
        self.zs = np.arange(Z0, Z1 + 1e-9, res)
        self.W = len(self.xs)
        self.H = len(self.zs)

    def ij(self, x, z):
        """grid indices (row=z index, col=x index) as floats."""
        return (np.asarray(z) - Z0) / self.res, (np.asarray(x) - X0) / self.res

    def raster(self, view, img=None):
        import cv2
        X, Z = np.meshgrid(self.xs, self.zs)
        P = np.stack([X, np.zeros_like(X), Z], -1).reshape(-1, 3)
        u, v, _ = view.project(P)
        src = view.mask.astype(np.float32) if img is None else img.astype(np.float32)
        out = cv2.remap(src, u.reshape(X.shape).astype(np.float32), v.reshape(X.shape).astype(np.float32),
                        interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        return out


def sdist(mask, res):
    """Signed distance (m), negative inside."""
    out = ndi.distance_transform_edt(~mask)
    ins = ndi.distance_transform_edt(mask)
    return (out - ins) * res


class Refs:
    """Front/back views + consensus silhouette for one character."""

    def __init__(self, aid):
        self.aid = aid
        self.front = HR.make_view(aid, "front")
        self.back = HR.make_view(aid, "back")
        self.g = Grid()
        self.Mf = self.g.raster(self.front) >= 0.5
        self.Mb = self.g.raster(self.back) >= 0.5
        self.Df = sdist(self.Mf, RES)
        self.Db = sdist(self.Mb, RES)
        self.D = 0.5 * (self.Df + self.Db)
        self.M = self.D < 0
        self.iou_fb = float((self.Mf & self.Mb).sum() / max((self.Mf | self.Mb).sum(), 1))

    # ------------------------------------------------------------------ queries
    def inside(self, x, z, which="c"):
        M = {"c": self.M, "f": self.Mf, "b": self.Mb}[which]
        r, c = self.g.ij(x, z)
        r = np.clip(np.round(r).astype(int), 0, self.g.H - 1)
        c = np.clip(np.round(c).astype(int), 0, self.g.W - 1)
        return M[r, c]

    def sdf2(self, x, z):
        """Bilinear consensus signed distance at world (x, z)."""
        r, c = self.g.ij(x, z)
        return ndi.map_coordinates(self.D, [np.ravel(r), np.ravel(c)], order=1, mode="nearest").reshape(np.shape(x))

    def row_runs(self, z, which="c"):
        M = {"c": self.M, "f": self.Mf, "b": self.Mb}[which]
        r = int(round((z - Z0) / RES))
        row = M[np.clip(r, 0, self.g.H - 1)]
        d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
        starts = np.nonzero(d == 1)[0]
        ends = np.nonzero(d == -1)[0]
        return [(self.g.xs[s], self.g.xs[e - 1]) for s, e in zip(starts, ends)]

    def central_run(self, z, x_hint=0.0, which="c"):
        runs = self.row_runs(z, which)
        if not runs:
            return None
        for a, b in runs:
            if a - 0.004 <= x_hint <= b + 0.004:
                return a, b
        best = min(runs, key=lambda ab: min(abs(ab[0] - x_hint), abs(ab[1] - x_hint)))
        return best

    def top_z(self):
        rows = np.nonzero(self.M.any(axis=1))[0]
        return float(self.g.zs[rows.max()])

    # ------------------------------------------------------------------ limb width profiles
    def profile(self, A, B, n=48, max_half=0.10, which="c", medial_limit=None, snap=0.045):
        """Perpendicular extents of the silhouette along the 2-D segment A->B (x,z).

        For each sample the painted run nearest to the axis (within `snap`) is taken, so a
        slightly off-centre landmark still measures its own limb.  Returns s, centre offset c,
        half-width a, ok (both ends found), and one-sided ends (lo/hi with flags)."""
        M = {"c": self.M, "f": self.Mf, "b": self.Mb}[which]
        A = np.asarray(A, float)
        B = np.asarray(B, float)
        d = B - A
        L = np.linalg.norm(d)
        t = d / L
        n1 = np.array([-t[1], t[0]])
        s = np.linspace(0, 1, n)
        ts = np.arange(-max_half, max_half + 1e-9, RES)
        K = len(ts)
        cs, as_, ok = np.zeros(n), np.zeros(n), np.zeros(n, bool)
        lo_v, hi_v = np.zeros(n), np.zeros(n)
        lo_ok, hi_ok = np.zeros(n, bool), np.zeros(n, bool)
        for i, si in enumerate(s):
            Q = A + si * d
            pts = Q[None, :] + ts[:, None] * n1[None, :]
            r, c = self.g.ij(pts[:, 0], pts[:, 1])
            r = np.clip(np.round(r).astype(int), 0, self.g.H - 1)
            c = np.clip(np.round(c).astype(int), 0, self.g.W - 1)
            inside = M[r, c].copy()
            blocked = medial_limit(pts[:, 0], pts[:, 1]) if medial_limit is not None else np.zeros(K, bool)
            free = inside & ~blocked
            dd = np.diff(np.concatenate([[0], free.astype(np.int8), [0]]))
            st = np.nonzero(dd == 1)[0]
            en = np.nonzero(dd == -1)[0] - 1
            if len(st) == 0:
                continue
            mid = K // 2
            dist = np.where((st <= mid) & (en >= mid), 0, np.minimum(np.abs(st - mid), np.abs(en - mid)))
            j = int(np.argmin(dist))
            if dist[j] * RES > snap:
                continue
            a0, a1 = st[j], en[j]
            # an end is genuine if the next sample outward is background (not blocked, not window edge)
            lo_good = a0 > 0 and not blocked[a0 - 1] and not inside[a0 - 1]
            hi_good = a1 < K - 1 and not blocked[a1 + 1] and not inside[a1 + 1]
            lo_v[i], hi_v[i] = ts[a0], ts[a1]
            lo_ok[i], hi_ok[i] = lo_good, hi_good
            if lo_good and hi_good:
                cs[i] = 0.5 * (ts[a0] + ts[a1])
                as_[i] = 0.5 * (ts[a1] - ts[a0])
                ok[i] = True
        return dict(s=s, c=cs, a=as_, ok=ok, lo=lo_v, hi=hi_v, lo_ok=lo_ok, hi_ok=hi_ok, n1=n1, t=t, L=L)


def fill_profile(s, vals, ok, template, smooth=2.0, scale_clip=(0.6, 1.8)):
    """Replace invalid samples by the template scaled to the valid ones; smooth."""
    vals = np.asarray(vals, float)
    tmpl = np.interp(s, template[0], template[1])
    if ok.sum() >= 3:
        k = np.median(vals[ok] / np.maximum(tmpl[ok], 1e-6))
        k = float(np.clip(k, *scale_clip))
    else:
        k = 1.0
    out = np.where(ok, vals, tmpl * k)
    # blend the seams between measured and template parts
    out = ndi.gaussian_filter1d(out, smooth, mode="nearest")
    return out, k


# --------------------------------------------------------------------------- SDF parts

class Part:
    """SDF part: fn(P[...,3]) -> distance (m, negative inside); AABB; bone owner; label."""

    def __init__(self, fn, lo, hi, bone=None, label="body", k=0.0, op="union", name=""):
        self.fn, self.lo, self.hi = fn, np.asarray(lo, float), np.asarray(hi, float)
        self.bone, self.label, self.k, self.op, self.name = bone, label, k, op, name


def tube(A, B, s, a, b, c=None, e=None, n1=None, bone=None, label="body", k=0.012, name="",
         cap_round=True, p=2.0):
    """Generalised cylinder A->B (3-D) with elliptic cross-sections a(s) (in-plane, along n1)
    and b(s) (depth, along n2 = n1 x t).  c, e: centre offsets along n1 / n2."""
    A = np.asarray(A, float)
    B = np.asarray(B, float)
    D = B - A
    L = float(np.linalg.norm(D))
    t = D / L
    if n1 is None:
        n1 = np.cross(t, np.array([0.0, 1.0, 0.0]))
        if np.linalg.norm(n1) < 1e-6:
            n1 = np.array([1.0, 0.0, 0.0])
    n1 = n1 - (n1 @ t) * t
    n1 /= np.linalg.norm(n1)
    n2 = np.cross(n1, t)
    if n2[1] < 0:
        n2 = -n2       # n2 points to +Y (back)
    s = np.asarray(s, float)
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    c = np.zeros_like(s) if c is None else np.asarray(c, float)
    e = np.zeros_like(s) if e is None else np.asarray(e, float)

    def fn(P):
        Q = P - A
        tr = (Q @ t) / L
        tc = np.clip(tr, 0.0, 1.0)
        aa = np.interp(tc, s, a)
        bb = np.interp(tc, s, b)
        cc = np.interp(tc, s, c)
        ee = np.interp(tc, s, e)
        R = Q - (tc * L)[..., None] * t
        u = R @ n1 - cc
        v = R @ n2 - ee
        if p == 2.0:
            rho = np.sqrt((u / aa) ** 2 + (v / bb) ** 2)
        else:
            rho = (np.abs(u / aa) ** p + np.abs(v / bb) ** p) ** (1.0 / p)
        m = np.minimum(aa, bb)
        dcs = (rho - 1.0) * m
        over = np.maximum(tr - 1.0, -tr) * L          # >0 beyond the ends
        if cap_round:
            out = np.where(over <= 0, np.maximum(dcs, over),
                           np.sqrt(np.maximum(dcs, 0) ** 2 + over ** 2))
        else:
            out = np.maximum(dcs, over)
        return out

    r = float(max(a.max(), b.max()) + max(np.abs(c).max(), np.abs(e).max()))
    lo = np.minimum(A, B) - r
    hi = np.maximum(A, B) + r
    return Part(fn, lo, hi, bone=bone, label=label, k=k, name=name)


def stack(zs, cx, al, ar, cy, bf, bb, pw, bone_fn=None, label="body", k=0.0, name="torso"):
    """Horizontal superellipse stack (torso): per row z: centre (cx, cy), half-widths left/right
    (al: +X side, ar: -X side), front/back half-depths (bf toward -Y, bb toward +Y), exponent."""
    zs = np.asarray(zs, float)
    arrs = [np.asarray(v, float) for v in (cx, al, ar, cy, bf, bb, pw)]
    z0, z1 = zs[0], zs[-1]

    def fn(P):
        z = np.clip(P[..., 2], z0, z1)
        cxx, a_l, a_r, cyy, b_f, b_b, pp = (np.interp(z, zs, v) for v in arrs)
        u = P[..., 0] - cxx
        v = P[..., 1] - cyy
        a = np.where(u > 0, a_l, a_r)
        b = np.where(v < 0, b_f, b_b)
        rho = (np.abs(u / a) ** pp + np.abs(v / b) ** pp) ** (1.0 / pp)
        d = (rho - 1.0) * np.minimum(a, b) * 0.92
        over = np.maximum(z0 - P[..., 2], P[..., 2] - z1)
        return np.where(over > 0, np.sqrt(np.maximum(d, 0) ** 2 + over ** 2), d)

    amax = max(arrs[1].max(), arrs[2].max())
    bmax = max(arrs[4].max(), arrs[5].max())
    lo = np.array([arrs[0].min() - amax, arrs[3].min() - bmax, z0])
    hi = np.array([arrs[0].max() + amax, arrs[3].max() + bmax, z1])
    return Part(fn, lo, hi, bone=None, label=label, k=k, name=name)


def ellipsoid(c, r, rot=None, **kw):
    from frlib import sdf
    p = sdf.ellipsoid(c, r, rot=rot)
    return Part(p.fn, p.lo, p.hi, **kw)


def rcone(a, b, ra, rb, **kw):
    from frlib import sdf
    p = sdf.round_cone(a, b, ra, rb)
    return Part(p.fn, p.lo, p.hi, **kw)


def sphere(c, r, **kw):
    from frlib import sdf
    p = sdf.sphere(c, r)
    return Part(p.fn, p.lo, p.hi, **kw)


def rbox(c, half, rot=None, rounding=0.0, **kw):
    from frlib import sdf
    p = sdf.box(c, half, rot=rot, rounding=rounding)
    return Part(p.fn, p.lo, p.hi, **kw)


def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def smax(a, b, k):
    return -smin(-a, -b, k)


class Field:
    """Dense SDF grid with block-local part evaluation and a per-voxel owner label."""

    def __init__(self, lo, hi, voxel):
        self.lo = np.asarray(lo, float)
        self.voxel = float(voxel)
        self.n = np.ceil((np.asarray(hi, float) - self.lo) / voxel).astype(int) + 1
        self.d = np.full(tuple(self.n), 1.0, np.float32)
        self.axes = [self.lo[i] + np.arange(self.n[i]) * voxel for i in range(3)]

    def block(self, lo, hi):
        i0 = np.clip(np.floor((np.asarray(lo) - self.lo) / self.voxel).astype(int), 0, self.n)
        i1 = np.clip(np.ceil((np.asarray(hi) - self.lo) / self.voxel).astype(int) + 1, 0, self.n)
        return i0, i1

    def points(self, i0, i1):
        X, Y, Z = np.meshgrid(self.axes[0][i0[0]:i1[0]], self.axes[1][i0[1]:i1[1]],
                              self.axes[2][i0[2]:i1[2]], indexing="ij")
        return np.stack([X, Y, Z], -1)

    def apply(self, part, op=None, k=None):
        op = op or part.op
        k = part.k if k is None else k
        pad = k + 3 * self.voxel
        i0, i1 = self.block(part.lo - pad, part.hi + pad)
        if np.any(i1 <= i0):
            return
        # evaluate in z-slabs to bound memory
        step = max(4, int(4_000_000 / max((i1[0] - i0[0]) * (i1[1] - i0[1]), 1)))
        for z0 in range(i0[2], i1[2], step):
            z1 = min(i1[2], z0 + step)
            a0 = np.array([i0[0], i0[1], z0])
            a1 = np.array([i1[0], i1[1], z1])
            P = self.points(a0, a1)
            dp = part.fn(P).astype(np.float32)
            sl = (slice(a0[0], a1[0]), slice(a0[1], a1[1]), slice(z0, z1))
            cur = self.d[sl]
            if op == "union":
                self.d[sl] = smin(cur, dp, k)
            elif op == "subtract":
                self.d[sl] = smax(cur, -dp, k)
            elif op == "intersect":
                self.d[sl] = smax(cur, dp, k)

    def intersect_xz(self, refs, k=0.004, dilate=0.0):
        """Smooth intersection with the consensus silhouette extruded along Y (visual hull)."""
        X, Z = np.meshgrid(self.axes[0], self.axes[2], indexing="ij")
        h = refs.sdf2(X, Z) - dilate
        self.d = smax(self.d, h[:, None, :].astype(np.float32), k).astype(np.float32)

    def clip_ground(self, z=0.0, k=0.003):
        Z = self.axes[2][None, None, :]
        self.d = smax(self.d, (z - Z).astype(np.float32), k).astype(np.float32)

    def mesh(self, level=0.0):
        from skimage import measure
        v, f, _n, _v = measure.marching_cubes(self.d, level=level, spacing=(self.voxel,) * 3,
                                              allow_degenerate=False)
        v = v + self.lo
        a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
        if np.einsum("ij,ij->i", a, np.cross(b, c)).sum() < 0:
            f = f[:, ::-1]
        return v, f

    def sample(self, P):
        idx = (np.asarray(P, float) - self.lo) / self.voxel
        return ndi.map_coordinates(self.d, idx.reshape(-1, 3).T, order=1, mode="nearest").reshape(np.shape(P)[:-1])


def nearest_part_labels(verts, parts, labels=None):
    """Per-vertex label/bone of the closest part (distance)."""
    best = np.full(len(verts), np.inf)
    who = np.full(len(verts), -1)
    for i, p in enumerate(parts):
        lo, hi = p.lo - 0.05, p.hi + 0.05
        sel = np.all((verts >= lo) & (verts <= hi), axis=1)
        if not sel.any():
            continue
        d = p.fn(verts[sel])
        idx = np.nonzero(sel)[0]
        better = d < best[idx]
        best[idx[better]] = d[better]
        who[idx[better]] = i
    return who, best
