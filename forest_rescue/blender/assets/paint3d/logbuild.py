"""Straight painted log (no bpy): the art/02 fallen trunk unwrapped along its own painted centreline (moss on top,
bark sides), laid on the ground as a near-constant-radius tube with a gentle plan curve; root plate = jagged
disc (painted root mass on the rim, quilted root/soil on the faces); splintered break at the far end."""
import math

import cv2
import numpy as np
from scipy import ndimage as ndi

import geom
from frlib import texproj


def painted_log(img, mask, x_root, x_end):
    """Per-column painted centre row c(x) and radius r(x) (px) of the log body between x_root and x_end."""
    cs, rs, xs = [], [], []
    for x in range(int(x_root), int(x_end)):
        rows = np.nonzero(mask[:, x])[0]
        if len(rows) < 4:
            continue
        # largest run (the log), ignore detached grass below
        runs = np.split(rows, np.nonzero(np.diff(rows) > 2)[0] + 1)
        run = max(runs, key=len)
        xs.append(x)
        cs.append(0.5 * (run[0] + run[-1]))
        rs.append(0.5 * (run[-1] - run[0] + 1))
    xs, cs, rs = np.array(xs, float), np.array(cs), np.array(rs)
    cs = ndi.gaussian_filter1d(cs, 6)
    rs = ndi.gaussian_filter1d(rs, 8)
    return xs, cs, rs


def unwrap_strip(img, xs, cs, rs, out_w, out_h, mask=None):
    """Strip texture: u = along the log (xs), v = around (top at v = 0.5): row = c - r * cos(theta)."""
    u = np.linspace(xs[0], xs[-1], out_w)
    c = np.interp(u, xs, cs)
    r = np.interp(u, xs, rs)
    th = np.linspace(0.0, 2 * math.pi, out_h)            # row 0 = top of the log (moss), around the ring
    row = c[None, :] - (r[None, :] * 0.84) * np.cos(th)[:, None]
    col = np.repeat(u[None, :], out_h, 0)
    smp = texproj._bilinear(img.astype(np.float32), col.ravel(), row.ravel())[:, :3].reshape(out_h, out_w, 3)
    if mask is not None:
        # only painted log pixels: texels sampling background (log tips / under the arch) are filled from the bark
        H, W = mask.shape
        inside = mask[np.clip(np.round(row).astype(int), 0, H - 1), np.clip(np.round(col).astype(int), 0, W - 1)]
        inside = ndi.binary_erosion(inside, iterations=2)
        if inside.any() and not inside.all():
            smp = texproj.fill(smp.astype(np.float64), inside).astype(np.float32)
    return smp


def log_mesh(length, radius, uv_rect, segs_len=24, segs_rad=12, taper=0.85, curve=0.25, sink=0.06, seed=0,
             cap_uv=None):
    """Tube along +x from 0 to length, lying on the ground (z = r - sink), gentle plan curve (y)."""
    rng = np.random.default_rng(seed)
    s = np.linspace(0, 1, segs_len + 1)
    x = s * length
    y = curve * np.sin(np.pi * s) * rng.choice([-1, 1])
    r = radius * (1.0 - (1 - taper) * s) * (1 + 0.03 * np.sin(s * 9 + rng.uniform(0, 6)))
    z = r - sink
    P = np.stack([x, y, z], 1)
    V, T, UV, C, N = geom.tube(P, r, segs_rad, uv_rect, np.zeros(4), ref_side=np.array([0, 0, 1.0]))
    # end caps (fans) so the open tube ends never show the inside
    k = segs_rad + 1
    nV = len(V)
    capV, capT, capUV, capN = [], [], [], []
    for ring, sgn in ((0, -1.0), (len(P) - 1, 1.0)):
        ids = np.arange(ring * k, ring * k + segs_rad)
        cen = V[ids].mean(0)
        base = nV + len(capV)
        capV.append(cen)
        capN.append(np.array([sgn, 0, 0.0]))
        cu0, cv0, cu1, cv1 = cap_uv if cap_uv is not None else uv_rect
        capUV.append(((cu0 + cu1) / 2, (cv0 + cv1) / 2))
        for j, vid in enumerate(ids):
            capV.append(V[vid])
            capN.append(np.array([sgn, 0, 0.0]))
            a_ = 2 * math.pi * j / segs_rad
            capUV.append(((cu0 + cu1) / 2 + 0.35 * (cu1 - cu0) * math.cos(a_),
                          (cv0 + cv1) / 2 + 0.35 * (cv1 - cv0) * math.sin(a_)))
        for j in range(segs_rad):
            a_, b_ = base + 1 + j, base + 1 + (j + 1) % segs_rad
            capT.append([base, a_, b_] if sgn > 0 else [base, b_, a_])
    # geom.tube: u around, v along -> strip texture: u along the log, v around (top of the log at the strip top)
    u0, v0, u1, v1 = uv_rect
    fa = (UV[:, 0] - u0) / max(u1 - u0, 1e-9)
    fl = (UV[:, 1] - v0) / max(v1 - v0, 1e-9)
    UV = np.stack([u0 + fl * (u1 - u0), v1 - fa * (v1 - v0)], 1)
    V = np.vstack([V, np.array(capV)])
    T = np.vstack([T, np.array(capT)])
    UV = np.vstack([UV, np.array(capUV)])
    N = np.vstack([N, np.array(capN)])
    return V, T, UV, N, r


def root_plate(center, radius, thick, uv_rim, uv_face, n=18, seed=0):
    """Jagged disc facing +-x: rim quads (uv_rim, along the rim) + two fan faces (uv_face, planar)."""
    rng = np.random.default_rng(seed)
    ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
    rr = radius * (1 + rng.uniform(-0.18, 0.12, n))
    pts = []
    for side in (-0.5, 0.5):
        for a, r in zip(ang, rr):
            pts.append(center + np.array([side * thick + rng.normal(0, 0.05), r * math.cos(a), r * math.sin(a)]))
    pts = np.array(pts)
    pts[:, 2] = np.maximum(pts[:, 2], -0.25)
    V, T, UV, N = [], [], [], []
    u0, v0, u1, v1 = uv_rim
    for i in range(n):
        j = (i + 1) % n
        q = [pts[i], pts[j], pts[n + j], pts[n + i]]
        nn = geom.nrm(np.cross(q[1] - q[0], q[3] - q[0]))
        if np.dot(nn, q[0] - center) < 0:
            q = q[::-1]
            nn = -nn
        base = len(V)
        V += q
        ua, ub = u0 + (u1 - u0) * i / n, u0 + (u1 - u0) * (i + 1) / n
        UV += [(ua, v0), (ub, v0), (ub, v1), (ua, v1)]
        N += [nn] * 4
        T += [[base, base + 1, base + 2], [base, base + 2, base + 3]]
    fu0, fv0, fu1, fv1 = uv_face
    for side, k0 in ((-1, 0), (1, n)):
        cen = center + np.array([side * 0.5 * thick, 0, 0])
        base = len(V)
        V.append(cen)
        UV.append(((fu0 + fu1) / 2, (fv0 + fv1) / 2))
        N.append(np.array([side, 0, 0.0]))
        for i in range(n):
            p = pts[k0 + i]
            V.append(p)
            d = (p - cen) / (radius * 1.25)
            UV.append(((fu0 + fu1) / 2 + d[1] * (fu1 - fu0) / 2, (fv0 + fv1) / 2 + d[2] * (fv1 - fv0) / 2))
            N.append(np.array([side, 0, 0.0]))
        for i in range(n):
            a, b = base + 1 + i, base + 1 + (i + 1) % n
            T.append([base, a, b] if side > 0 else [base, b, a])
    return np.array(V), np.array(T), np.array(UV), np.array(N)


def splinters(end_center, radius, uv_rect, n=7, seed=0):
    rng = np.random.default_rng(seed)
    V, T, UV, N = [], [], [], []
    u0, v0, u1, v1 = uv_rect
    for k in range(n):
        a = 2 * math.pi * k / n + rng.normal(0, 0.2)
        rr = radius * rng.uniform(0.3, 0.95)
        b = end_center + np.array([0, rr * math.cos(a), rr * math.sin(a)])
        w = radius * rng.uniform(0.25, 0.45)
        side = np.array([0, -math.sin(a), math.cos(a)]) * w / 2
        tip = b + np.array([rng.uniform(0.25, 0.8) * radius * 2, 0, 0]) + rng.normal(0, 0.05, 3)
        base = len(V)
        V += [b - side, b + side, tip]
        nn = geom.nrm(np.cross(V[base + 1] - V[base], V[base + 2] - V[base]))
        N += [nn] * 3
        UV += [(u0, v0), (u1, v0), ((u0 + u1) / 2, v1)]
        T += [[base, base + 1, base + 2], [base, base + 2, base + 1]]
    return np.array(V), np.array(T), np.array(UV), np.array(N)
