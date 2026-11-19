"""Explicit low-poly hands with five fingers (relaxed, slightly curled), skinned to the shared
finger bones.  Geometry: palm = superellipse loft (wrist -> knuckles), fingers/thumb = tubes with
a rounded tip.  Returns vertices, faces, per-vertex {bone: w} and the finger bone joints."""
import math

import numpy as np


def _unit(v):
    v = np.asarray(v, float)
    return v / max(np.linalg.norm(v), 1e-12)


def _rot(v, axis, deg):
    axis = _unit(axis)
    th = math.radians(deg)
    return v * math.cos(th) + np.cross(axis, v) * math.sin(th) + axis * (axis @ v) * (1 - math.cos(th))


class MeshAcc:
    def __init__(self):
        self.v, self.f, self.w = [], [], []

    def add_v(self, p, w):
        self.v.append(np.asarray(p, float))
        self.w.append(dict(w))
        return len(self.v) - 1

    def arrays(self):
        return np.array(self.v), self.f, self.w


def tube(acc, pts, radii, weights, sides=8, ref=None, tip=True, flat=1.0, base_cap=False):
    """pts: (m,3); radii (m,); weights: list of {bone:w} per ring; returns ring indices."""
    pts = np.asarray(pts, float)
    m = len(pts)
    tdir = [_unit(pts[min(i + 1, m - 1)] - pts[max(i - 1, 0)]) for i in range(m)]
    ref = _unit(ref if ref is not None else np.cross(tdir[0], [0.3, 0.2, 0.9]))
    rings = []
    nprev = None
    for i in range(m):
        t = tdir[i]
        n = ref - (ref @ t) * t if nprev is None else nprev - (nprev @ t) * t
        n = _unit(n)
        b = np.cross(t, n)
        nprev = n
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides
            off = n * math.cos(a) * radii[i] * flat + b * math.sin(a) * radii[i]
            ring.append(acc.add_v(pts[i] + off, weights[i]))
        rings.append(ring)
    for i in range(m - 1):
        r0, r1 = rings[i], rings[i + 1]
        for k in range(sides):
            k2 = (k + 1) % sides
            acc.f.append([r0[k], r0[k2], r1[k2], r1[k]])
    if tip:
        t = tdir[-1]
        mid = []
        for k in range(sides):
            p = acc.v[rings[-1][k]]
            c = pts[-1]
            mid.append(acc.add_v(c + (p - c) * 0.62 + t * radii[-1] * 0.62, weights[-1]))
        rr = rings[-1]
        for k in range(sides):
            k2 = (k + 1) % sides
            acc.f.append([rr[k], rr[k2], mid[k2], mid[k]])
        apex = acc.add_v(pts[-1] + t * radii[-1] * 0.95, weights[-1])
        for k in range(sides):
            k2 = (k + 1) % sides
            acc.f.append([mid[k], mid[k2], apex])
    if base_cap:
        t = tdir[0]
        apex = acc.add_v(pts[0] - t * radii[0] * 0.5, weights[0])
        r0 = rings[0]
        for k in range(sides):
            k2 = (k + 1) % sides
            acc.f.append([r0[k2], r0[k], apex])
    return rings


FINGERS = {  # name: (knuckle offset along d, along t), segments, radius, spread deg, bones
    "Index": (1.00, 0.36, (0.043, 0.026, 0.021), 0.0092, 5.0),
    "Middle": (1.03, 0.11, (0.047, 0.029, 0.022), 0.0095, 1.0),
    "Ring": (0.99, -0.14, (0.044, 0.027, 0.021), 0.0090, -3.5),
    "Pinky": (0.90, -0.37, (0.035, 0.021, 0.019), 0.0080, -8.0),
}


def build_hand(side, wrist, d, palm_n, thumb_t, scale=1.0, palm_len=0.090, curl=(16, 24, 16),
               thumb_curl=14.0, female=False):
    """side: 'Left'/'Right'.  d = wrist->middle knuckle direction, palm_n = palm normal (out of
    the palm), thumb_t = thumb-side direction.  Returns (acc, bones) with bones = joint table."""
    S = side
    d = _unit(d)
    t = _unit(thumb_t - (thumb_t @ d) * d)
    n = _unit(np.cross(d, t))
    if n @ palm_n < 0:
        n = -n
    acc = MeshAcc()
    s = scale
    w_half = (0.041 if not female else 0.037) * s
    th = (0.015 if not female else 0.013) * s
    pl = palm_len * s
    wr = np.asarray(wrist, float)
    hand_w = {f"{S}Hand": 1.0}
    # ---- palm loft: rings from the wrist to the knuckles (superellipse, 12 sides)
    sides = 12
    stations = [(-0.20, 0.62, 0.95), (0.0, 0.80, 1.0), (0.35, 0.97, 1.05), (0.70, 1.0, 1.0), (0.94, 0.96, 0.85)]
    rings = []
    for u, wf, tf in stations:
        c = wr + d * (u * pl) - n * 0.002 * s
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides
            ca, sa = math.cos(a), math.sin(a)
            # superellipse (p~3) cross-section: across t (width) and n (thickness)
            px = np.sign(ca) * abs(ca) ** (2 / 3.0)
            py = np.sign(sa) * abs(sa) ** (2 / 3.0)
            off = t * px * w_half * wf + n * py * th * tf
            if py < 0:          # palm side slightly fuller
                off = off + n * py * th * 0.15
            wgt = hand_w if u > 0.05 else ({f"{S}Hand": 0.6, f"{S}LowerArm": 0.4} if u > -0.1 else {f"{S}LowerArm": 0.85, f"{S}Hand": 0.15})
            ring.append(acc.add_v(c + off, wgt))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            acc.f.append([rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]])
    # distal cap of the palm
    cap_c = acc.add_v(wr + d * (0.99 * pl), hand_w)
    for k in range(sides):
        k2 = (k + 1) % sides
        acc.f.append([rings[-1][k], rings[-1][k2], cap_c])
    bones = {}
    # ---- fingers
    for name, (od, ot, segs, rad, spread) in FINGERS.items():
        rad = rad * s * (0.92 if female else 1.0)
        base = wr + d * (od * pl * 0.93) + t * (ot * w_half * 1.02)
        # spread: rotate within the palm plane away from the middle finger (sign by t side)
        fdir = _rot(d, n, spread)
        if (np.sign(ot) != 0) and ((fdir - d) @ t) * np.sign(ot) < 0:
            fdir = _rot(d, n, -spread)
        flex_axis = _unit(np.cross(fdir, n))           # +angle bends toward the palm (+n)
        pts = [base - fdir * 0.014 * s, base]
        p = base.copy()
        dirv = fdir.copy()
        for k, Lk in enumerate(segs):
            dirv = _rot(dirv, _unit(np.cross(dirv, n)), curl[k])
            p = p + dirv * Lk * s
            pts.append(p.copy())
        pts = np.array(pts)
        b1 = f"{S}{name}1"
        b2 = f"{S}{name}2" if name in ("Index", "Middle") else b1
        w = [hand_w, {b1: 0.7, f"{S}Hand": 0.3}, {b1: 0.5, b2: 0.5} if b2 != b1 else {b1: 1.0},
             {b2: 1.0}, {b2: 1.0}]
        radii = [rad * 1.05, rad * 1.04, rad * 0.97, rad * 0.88, rad * 0.80]
        tube(acc, pts, radii, w, sides=8, ref=n)
        bones[b1] = (pts[1], pts[2])
        if b2 != b1:
            bones[b2] = (pts[2], pts[4])
        bones[f"_{name}tip"] = pts[-1]
    # ---- thumb: from the palm's thumb side near the wrist, toward t and forward along d
    cmc = wr + d * (0.16 * pl) + t * (w_half * 0.60) + n * (th * 0.30)
    tdir = _unit(0.72 * d + 0.56 * t + 0.36 * n)
    tpts = [cmc]
    p = cmc.copy()
    dv = tdir.copy()
    for k, Lk in enumerate((0.046, 0.033, 0.027)):
        if k:
            dv = _rot(dv, _unit(np.cross(dv, n)), thumb_curl)
        p = p + dv * Lk * s
        tpts.append(p.copy())
    tpts = np.array(tpts)
    tr = 0.0115 * s * (0.92 if female else 1.0)
    tw = [{f"{S}Hand": 0.6, f"{S}Thumb1": 0.4}, {f"{S}Thumb1": 1.0}, {f"{S}Thumb1": 0.4, f"{S}Thumb2": 0.6},
          {f"{S}Thumb2": 1.0}]
    tube(acc, tpts, [tr * 1.25, tr * 1.05, tr * 0.95, tr * 0.82], tw, sides=8, ref=n)
    bones[f"{S}Thumb1"] = (tpts[0], tpts[1])
    bones[f"{S}Thumb2"] = (tpts[1], tpts[3])
    bones[f"{S}Hand"] = (wr, wr + d * pl)
    bones["_grip"] = wr + d * (0.75 * pl) - n * (th * 2.2) + t * (w_half * 0.2)
    bones["_frame"] = (d, t, n)
    return acc, bones
