"""Solid (opaque) hair volumes of «Искра»: mane, tail, forelock — pure numpy.

Hair mass is modelled as clumps (round-cone chains along wavy strand paths) smoothly unioned
into an SDF and meshed; only thin fringes are alpha cards (horse_hair.py).  The volume is
textured procedurally with strands that follow the clump direction (flow field from the clump
segments) in the body atlas, so most of the hair is opaque geometry (mobile friendly).

Every clump segment records (a, b, part) so the build can derive skin weights and the texture
flow direction for any surface point.
"""
import math

import numpy as np

from frlib import sdf
from frlib.sdf import round_cone

import horse_rig as HRig

V = lambda *a: np.array(a, float)  # noqa: E731

# mane bottom line (z) per neck position y: left side from the left profile of the sheet,
# the right side falls lower (front/rear views show the mane lying on the horse's right)
MANE_BOTTOM_L = ([-1.10, -0.95, -0.80, -0.62, -0.45, -0.36], [1.86, 1.68, 1.57, 1.51, 1.51, 1.53])
MANE_BOTTOM_R = ([-1.10, -0.95, -0.80, -0.62, -0.45, -0.36], [1.83, 1.62, 1.50, 1.45, 1.47, 1.51])


class Clumps:
    def __init__(self):
        self.prims = []
        self.segs = []          # (a, b, part)

    def chain(self, pts, radii, part, k=0.02):
        for i in range(len(pts) - 1):
            p = round_cone(pts[i], pts[i + 1], radii[i], radii[i + 1], name=part)
            p.k = k
            self.prims.append(p)
            self.segs.append((np.asarray(pts[i], float), np.asarray(pts[i + 1], float), part))


def _crest_top(guide, y, x=0.0):
    zs = np.arange(2.08, 1.30, -0.004)
    P = np.stack([np.full_like(zs, x), np.full_like(zs, y), zs], 1)
    d = guide.d(P)
    i = int(np.argmax(d <= 0)) if np.any(d <= 0) else len(zs) - 1
    return P[i]


def _march(guide, root, d0, length, segs, offset, off_gain, rng, stiff=0.5):
    """Strand path over the skin (kept `offset`..`offset+off_gain` above it), gravity down."""
    step = length / segs
    p = root.copy()
    d = d0 / np.linalg.norm(d0)
    pts = [p.copy()]
    ph = rng.uniform(0, 6.28)
    for i in range(segs):
        f = (i + 1) / segs
        g = V(0.0, 0.10, -1.0)
        d = stiff * d + (1 - stiff) * g / np.linalg.norm(g)
        d += V(0, math.sin(ph + i * 1.3) * 0.12, 0)
        d /= np.linalg.norm(d)
        q = p + d * step
        target = offset + off_gain * f
        dd = guide.d(q[None])[0] - target
        if dd < 0 or dd > 0.01:
            q = guide.project(q[None], target + min(max(dd, 0.0), 0.01) * 0.3)[0]
        d = (q - p) / max(np.linalg.norm(q - p), 1e-9)
        p = q
        pts.append(p.copy())
    return np.array(pts)


# --------------------------------------------------------------------------- mane

def mane_clumps(guide, seed=13):
    rng = np.random.default_rng(seed)
    C = Clumps()
    y0, y1 = -1.105, -0.37
    for side, sx, n, line, out in (("R", -1.0, 26, MANE_BOTTOM_R, 0.85), ("L", 1.0, 18, MANE_BOTTOM_L, 0.55)):
        for k in range(n):
            t = (k + rng.uniform(0.2, 0.8)) / n
            y = y0 + (y1 - y0) * t
            root = _crest_top(guide, y, 0.008 * sx) + V(0, 0, -0.004)
            bottom = float(np.interp(y, *line))
            length = max(0.10, (root[2] - bottom) * 1.25) * rng.uniform(0.9, 1.12)
            segs = max(3, int(length / 0.045))
            path = _march(guide, root, V(sx * out, rng.uniform(0.0, 0.12), 0.05), length, segs,
                          0.012, 0.016, rng)
            r0 = rng.uniform(0.022, 0.030)
            radii = np.linspace(r0, r0 * 0.55, len(path))
            # waviness: offset the inner points sideways a little along the neck
            C.chain(path, radii, f"mane_{side}", k=0.03)
    # crest ridge: the mane's mass on top of the neck (fuller crest silhouette, both views)
    ys = np.linspace(y0 + 0.005, y1 + 0.02, 14)
    pts = [_crest_top(guide, y) + V(-0.010, 0.0, 0.010 + 0.012 * math.sin(math.pi * (i / 13)))
           for i, y in enumerate(ys)]
    radii = [0.030 + 0.012 * math.sin(math.pi * i / 13) for i in range(len(pts))]
    C.chain(pts, radii, "mane_crest", k=0.035)
    return C


def forelock_clumps(guide, seed=17):
    rng = np.random.default_rng(seed)
    C = Clumps()
    for k, x in enumerate((-0.022, 0.0, 0.024)):
        root = guide.project(V(x, -1.205, 1.975)[None], 0.004)[0]
        length = (0.13, 0.15, 0.12)[k]
        path = _march(guide, root, V(x * 1.2, -0.80, -0.55), length, 4, 0.006, 0.006, rng, stiff=0.45)
        C.chain(path, np.linspace(0.020, 0.011, len(path)), "forelock", k=0.02)
    return C


# --------------------------------------------------------------------------- tail

TAIL_SPLINE = [V(0, 0.60, 1.425), V(0, 0.73, 1.425), V(0, 0.82, 1.27), V(0, 0.865, 1.02),
               V(0, 0.882, 0.76), V(0, 0.876, 0.50), V(0, 0.862, 0.30), V(0, 0.850, 0.20)]


def tail_center(t):
    P = np.array(TAIL_SPLINE)
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    s /= s[-1]
    t = np.atleast_1d(t)
    return np.stack([np.interp(t, s, P[:, i]) for i in range(3)], -1)


def _tail_section(t):
    """Half-width (X, rear view) and half-depth (Y, side view) of the tail mass along t."""
    ax = np.interp(t, [0.0, 0.12, 0.25, 0.50, 0.72, 0.88, 1.0], [0.040, 0.075, 0.110, 0.130, 0.118, 0.085, 0.040])
    ay = np.interp(t, [0.0, 0.12, 0.25, 0.50, 0.72, 0.88, 1.0], [0.040, 0.065, 0.085, 0.098, 0.090, 0.068, 0.035])
    return ax, ay


def tail_clumps(seed=19):
    rng = np.random.default_rng(seed)
    C = Clumps()
    t0 = 0.10
    # solid core: no see-through gaps anywhere along the mass
    ts = np.linspace(0.06, 0.93, 16)
    core = tail_center(ts)
    ax, ay = _tail_section(ts)
    C.chain(core, 0.62 * np.minimum(ax, ay * 1.15), "tail", k=0.04)
    # outer clumps: wavy strands around the ellipse, varied lengths -> wavy wispy edges
    n = 18
    for k in range(n):
        ang = 2 * math.pi * (k + rng.uniform(-0.3, 0.3)) / n
        rho = rng.uniform(0.55, 0.80)
        t1 = rng.uniform(0.84, 1.0)
        ts = np.linspace(t0 + rng.uniform(0, 0.08), t1, 12)
        c = tail_center(ts)
        ax, ay = _tail_section(ts)
        amp = rng.uniform(0.010, 0.022)
        ph = rng.uniform(0, 6.28)
        fr = rng.uniform(2.0, 3.5)
        wave = amp * np.sin(ph + fr * math.pi * ts) * np.clip(ts * 1.6, 0, 1)
        x = c[:, 0] + rho * math.cos(ang) * ax + wave * math.cos(ang + 1.2)
        y = c[:, 1] + rho * math.sin(ang) * ay + wave * math.sin(ang + 1.2)
        pts = np.stack([x, y, c[:, 2]], 1)
        r = 0.42 * np.minimum(ax, ay * 1.2) * np.interp(ts, [0, 0.8, 1.0], [1.0, 0.95, 0.45])
        C.chain(pts, r, "tail", k=0.03)
    return C


# --------------------------------------------------------------------------- meshing

def volume_field(clumps, lo, hi, voxel, body_guide=None, cut=0.003):
    F = sdf.Field(lo, hi, voxel)
    for p in clumps.prims:
        F.apply(p)
    if body_guide is not None:
        # keep only what lies outside the body (plus `cut` inside: no gap at the skin)
        X, Y, Z = np.meshgrid(*F.axes, indexing="ij")
        P = np.stack([X, Y, Z], -1).reshape(-1, 3)
        db = body_guide.d(P).reshape(F.d.shape).astype(np.float32)
        F.d = np.maximum(F.d, -(db + cut))
    return F


def drop_hidden(verts, faces, body_guide, inside=-0.0015):
    """Delete faces whose centroid lies inside the body (hidden inner shell)."""
    c = verts[faces].mean(1)
    keep = body_guide.d(c) > inside
    faces = faces[keep]
    used = np.unique(faces)
    remap = -np.ones(len(verts), int)
    remap[used] = np.arange(len(used))
    return verts[used], remap[faces]


# --------------------------------------------------------------------------- weights / flow

def nearest_segments(clumps, P):
    """Index of the nearest clump segment for each point, plus the parameter along it."""
    A = np.array([s[0] for s in clumps.segs])
    B = np.array([s[1] for s in clumps.segs])
    AB = B - A
    L2 = np.maximum((AB * AB).sum(1), 1e-12)
    best_d = np.full(len(P), np.inf)
    best_i = np.zeros(len(P), int)
    best_t = np.zeros(len(P))
    for i0 in range(0, len(A), 64):
        a, ab, l2 = A[i0:i0 + 64], AB[i0:i0 + 64], L2[i0:i0 + 64]
        rel = P[:, None, :] - a[None]
        t = np.clip((rel * ab[None]).sum(-1) / l2[None], 0, 1)
        d = np.linalg.norm(rel - ab[None] * t[..., None], axis=-1)
        j = np.argmin(d, 1)
        dj = d[np.arange(len(P)), j]
        better = dj < best_d
        best_d[better] = dj[better]
        best_i[better] = i0 + j[better]
        best_t[better] = t[np.arange(len(P)), j][better]
    return best_i, best_t


def flow_dirs(clumps, P):
    i, _ = nearest_segments(clumps, P)
    A = np.array([s[0] for s in clumps.segs])
    B = np.array([s[1] for s in clumps.segs])
    d = B[i] - A[i]
    return d / np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)


def volume_weights(clumps, verts, neck_bone_at, mane_bone_at, tail_weights, blend):
    """Per-vertex weight dicts from the clump each vertex belongs to."""
    i, t = nearest_segments(clumps, verts)
    parts = [clumps.segs[k][2] for k in i]
    crest = HRig.mane_roots()
    cy = np.array([p[1] for p in crest])[::-1]
    cz = np.array([p[2] for p in crest])[::-1]
    out = []
    for v, part in zip(verts, parts):
        if part.startswith("mane"):
            y = v[1]
            ztop = np.interp(y, cy, cz)
            f = float(np.clip((ztop + 0.02 - v[2]) / 0.22, 0.0, 1.0))
            side = "R" if v[0] < 0 else "L"
            if part == "mane_crest":
                f *= 0.4
            out.append(blend(neck_bone_at(y), mane_bone_at(y, side), f * 0.85))
        elif part == "forelock":
            f = float(np.clip((1.97 - v[2]) / 0.14, 0, 1))
            out.append(blend({"head": 1.0}, {"forelock": 1.0}, f))
        else:
            out.append(tail_weights(v))
    return out
