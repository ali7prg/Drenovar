"""Garment layers as real geometry: drape sheets (aprons, skirts, tails, cloaks, tabards, bibs,
hoods) built around the body field, and small explicit accessories (bands, belts, bows, straps,
pouches).  Every garment is an open sheet (solidified in Blender) whose cross-section follows the
convex hull of the body + clearance, hangs straight below its support (gravity rule) and whose
front-view extent is fitted to the painted silhouette."""
import math

import numpy as np
from scipy.ndimage import gaussian_filter, gaussian_filter1d

import hv2_fit as F


class Sheet:
    def __init__(self, name, V, label, material, thickness, weights, grid_shape, closed_u=False):
        self.name, self.V, self.label, self.material = name, V, label, material
        self.thickness, self.weights, self.shape, self.closed_u = thickness, weights, grid_shape, closed_u

    def faces(self):
        nv, nu = self.shape
        idx = np.arange(nv * nu).reshape(nv, nu)
        f = []
        last = nu if self.closed_u else nu - 1
        for i in range(nv - 1):
            for j in range(last):
                j2 = (j + 1) % nu
                f.append([idx[i, j], idx[i + 1, j], idx[i + 1, j2], idx[i, j2]])
        return f


def ray_radius(field, cx, cy, z, phis, rmax=0.62, step=0.002):
    """Outermost body radius along horizontal rays from (cx, cy, z) at angles phis.
    phi = 0 -> -Y (front), +90 deg -> +X (character's left)."""
    rs = np.arange(0.0, rmax, step)
    ph = np.asarray(phis, float)
    dx, dy = np.sin(ph), -np.cos(ph)
    P = np.stack([cx + rs[None, :] * dx[:, None], cy + rs[None, :] * dy[:, None],
                  np.full((len(ph), len(rs)), z)], -1)
    d = field.sample(P)
    inside = d < 0
    out = np.zeros(len(ph))
    for i in range(len(ph)):
        nz = np.nonzero(inside[i])[0]
        if len(nz):
            k = nz.max()
            # sub-voxel refine between k and k+1
            if k + 1 < len(rs):
                d0, d1 = d[i, k], d[i, k + 1]
                f = d0 / (d0 - d1) if d1 != d0 else 0.0
                out[i] = rs[k] + f * step
            else:
                out[i] = rs[k]
    return out


def hull_radius(rad, phis):
    """Convex hull of the polar cross-section, resampled at the same angles (spans leg gaps)."""
    from scipy.spatial import ConvexHull
    ph = np.asarray(phis)
    ok = rad > 1e-4
    if ok.sum() < 3:
        return rad.copy()
    pts = np.stack([rad * np.sin(ph), -rad * np.cos(ph)], 1)[ok]
    try:
        hull = ConvexHull(pts)
    except Exception:
        return rad.copy()
    poly = pts[hull.vertices]
    a = poly
    b = np.roll(poly, -1, 0)
    out = np.zeros(len(ph))
    for i, p in enumerate(ph):
        dvec = np.array([np.sin(p), -np.cos(p)])
        best = 0.0
        e = b - a
        den = dvec[0] * e[:, 1] - dvec[1] * e[:, 0]
        good = np.abs(den) > 1e-12
        tt = np.where(good, (a[:, 0] * e[:, 1] - a[:, 1] * e[:, 0]) / np.where(good, den, 1), -1)
        uu = np.where(good, (a[:, 0] * dvec[1] - a[:, 1] * dvec[0]) / np.where(good, den, 1), -1)
        hit = good & (tt > 0) & (uu >= -1e-9) & (uu <= 1 + 1e-9)
        if hit.any():
            best = tt[hit].max()
        out[i] = best
    return out


class BodyTable:
    """Polar radius table r(z, phi) of the body field around a vertical axis."""

    def __init__(self, field, cx, cy, z0, z1, dz=0.01, nphi=144):
        self.zs = np.arange(z0, z1 + 1e-9, dz)
        self.phis = np.linspace(-math.pi, math.pi, nphi, endpoint=False)
        self.cx, self.cy = cx, cy
        self.r = np.zeros((len(self.zs), nphi))
        self.h = np.zeros_like(self.r)
        for i, z in enumerate(self.zs):
            rr = ray_radius(field, cx, cy, z, self.phis)
            self.r[i] = rr
            self.h[i] = hull_radius(rr, self.phis)

    def hull(self, z, phi):
        """Bilinear (z, periodic phi) lookup of the hull radius."""
        z = np.asarray(z, float)
        phi = np.asarray(phi, float)
        fi = np.clip((z - self.zs[0]) / (self.zs[1] - self.zs[0]), 0, len(self.zs) - 1.001)
        i0 = np.floor(fi).astype(int)
        tz = fi - i0
        n = len(self.phis)
        fj = ((phi + math.pi) / (2 * math.pi) * n) % n
        j0 = np.floor(fj).astype(int) % n
        j1 = (j0 + 1) % n
        tp = fj - np.floor(fj)
        H = self.h
        a = H[i0, j0] * (1 - tp) + H[i0, j1] * tp
        b = H[i0 + 1, j0] * (1 - tp) + H[i0 + 1, j1] * tp
        return a * (1 - tz) + b * tz


def drape_skirt(name, T, R, z_top, hem_fn, phi0, phi1, offset=0.012, flare=0.03, fit="run",
                nu=44, nv=26, slope=0.12, label="garment", material="cloth", thickness=0.005,
                weights_fn=None, ragged=0.0, seed=0, fit_rows=None, fit_gain=1.0, closed=False):
    """Skirt-like sheet from z_top to hem_fn(phi) over angles [phi0, phi1] (radians)."""
    rng = np.random.default_rng(seed)
    phis = np.linspace(phi0, phi1, nu, endpoint=not closed)
    hem = np.array([hem_fn(p) for p in phis])
    if ragged:
        hem = hem + gaussian_filter1d(rng.normal(0, ragged, nu), 1.0, mode="wrap" if closed else "nearest")
    V = np.zeros((nv, nu, 3))
    vfrac = np.linspace(0, 1, nv)
    # gravity drape on a fine z grid per column
    zf = np.arange(z_top, hem.min() - 0.02, -0.005)
    rcol = np.zeros((len(zf), nu))
    for j, p in enumerate(phis):
        rh = T.hull(zf, np.full_like(zf, p)) + offset
        r = np.zeros_like(rh)
        cur = rh[0]
        for i in range(len(zf)):
            cur = max(rh[i], cur - slope * 0.005)
            r[i] = cur
        rcol[:, j] = r
    for i, v in enumerate(vfrac):
        for j, p in enumerate(phis):
            z = z_top - v * (z_top - hem[j])
            r = np.interp(-z, -zf, rcol[:, j])
            r += flare * v ** 1.5
            V[i, j] = (T.cx + r * math.sin(p), T.cy - r * math.cos(p), z)
    # fit the front-view extent of every row to the painted silhouette (left/right separately)
    if fit:
        for i in range(nv):
            zrow = V[i, :, 2].mean()
            if fit_rows is not None and not (fit_rows[0] <= zrow <= fit_rows[1]):
                continue
            run = R.central_run(zrow, x_hint=T.cx)
            if run is None:
                continue
            xs = V[i, :, 0] - T.cx
            for sgn, target in ((1, run[1] - T.cx), (-1, T.cx - run[0])):
                cur = (xs * sgn).max()
                if cur <= 1e-3 or target <= 0:
                    continue
                k = np.clip(target / cur, 0.90, 1.45)
                k = 1.0 + (k - 1.0) * fit_gain
                sel = xs * sgn > 0
                V[i, sel, 0] = T.cx + xs[sel] * k
        # smooth the fitted rows vertically
        V[..., 0] = gaussian_filter(V[..., 0], (1.0, 0.0), mode="nearest")
    W = weights_fn(V) if weights_fn else [{"Hips": 1.0}] * (nv * nu)
    return Sheet(name, V.reshape(-1, 3), label, material, thickness, W, (nv, nu), closed_u=closed)


def bib(name, T, z_top, z_bot, half_top, half_bot, offset=0.006, nu=16, nv=14, material="cloth",
        thickness=0.004, label="garment"):
    V = np.zeros((nv, nu, 3))
    for i in range(nv):
        z = z_top - (z_top - z_bot) * i / (nv - 1)
        f = (z_top - z) / (z_top - z_bot)
        ha = math.radians(half_top + (half_bot - half_top) * f ** 0.8)
        phis = np.linspace(-ha, ha, nu)
        r = T.hull(np.full(nu, z), phis) + offset
        V[i] = np.stack([T.cx + r * np.sin(phis), T.cy - r * np.cos(phis), np.full(nu, z)], 1)
    W = []
    for p in V.reshape(-1, 3):
        W.append({"Chest": 0.5, "UpperChest": 0.5} if p[2] > T.zs[0] + 0.25 else {"Spine": 0.6, "Chest": 0.4})
    return Sheet(name, V.reshape(-1, 3), label, material, thickness, W, (nv, nu))


def band_ring(name, field, center, axis, ref, rad_guess=0.08, width=0.05, offset=0.004, n=28, rows=3,
              thickness=0.004, material="cloth", weights=None, label="garment"):
    """Ring band hugging the body around an axis through `center` (armbands, belts, ties)."""
    axis = np.asarray(axis, float)
    axis = axis / np.linalg.norm(axis)
    ref = np.asarray(ref, float)
    e1 = ref - (ref @ axis) * axis
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(axis, e1)
    th = np.linspace(0, 2 * math.pi, n, endpoint=False)
    V = np.zeros((rows, n, 3))
    for i in range(rows):
        h = (i / (rows - 1) - 0.5) * width
        c = np.asarray(center, float) + axis * h
        rs = np.arange(0.0, rad_guess * 2.2, 0.0015)
        for j, a in enumerate(th):
            dvec = e1 * math.cos(a) + e2 * math.sin(a)
            P = c[None, :] + rs[:, None] * dvec[None, :]
            d = field.sample(P)
            ins = np.nonzero(d < 0)[0]
            r = rs[ins.max()] if len(ins) else rad_guess
            V[i, j] = c + dvec * (r + offset)
    # smooth around
    for i in range(rows):
        for k in range(3):
            V[i, :, k] = gaussian_filter1d(V[i, :, k], 1.0, mode="wrap")
    W = [dict(weights or {"Hips": 1.0})] * (rows * n)
    return Sheet(name, V.reshape(-1, 3), label, material, thickness, W, (rows, n), closed_u=True)


def strip(name, pts, normals, width, thickness=0.003, material="cloth", weights=None, label="garment"):
    """Flat ribbon along a polyline (normals = outward), as a 2-row sheet."""
    pts = np.asarray(pts, float)
    normals = np.asarray(normals, float)
    m = len(pts)
    V = np.zeros((m, 2, 3))
    for i in range(m):
        t = pts[min(i + 1, m - 1)] - pts[max(i - 1, 0)]
        t /= np.linalg.norm(t)
        side = np.cross(normals[i], t)
        side /= max(np.linalg.norm(side), 1e-9)
        V[i, 0] = pts[i] - side * width * 0.5
        V[i, 1] = pts[i] + side * width * 0.5
    W = weights if isinstance(weights, list) else [dict(weights or {"Hips": 1.0})] * (2 * m)
    return Sheet(name, V.reshape(-1, 3), label, material, thickness, W, (m, 2))


def box_mesh(center, half, R=None, bevel=0.3, nseg=2):
    """Rounded box (superellipsoid-ish) as a closed quad mesh: returns verts, faces."""
    import itertools
    n = 4 + 2 * nseg
    us = np.linspace(-1, 1, n)
    verts = {}
    V = []
    Fc = []

    def vid(key, p):
        if key not in verts:
            verts[key] = len(V)
            V.append(p)
        return verts[key]
    half = np.asarray(half, float)
    for axis in range(3):
        for sgn in (-1, 1):
            grid = np.zeros((n, n), int)
            for i, a in enumerate(us):
                for j, b in enumerate(us):
                    q = np.zeros(3)
                    q[axis] = sgn
                    o = [k for k in range(3) if k != axis]
                    q[o[0]] = a
                    q[o[1]] = b
                    key = tuple(np.round(q, 6))
                    # superellipse rounding
                    qq = np.sign(q) * np.abs(q) ** 1.0
                    nrm = (np.abs(qq) ** (2 / bevel)).sum() ** (bevel / 2) if bevel > 0 else np.abs(qq).max()
                    p = qq / max(nrm, 1e-9) * half
                    grid[i, j] = vid(key, p)
            for i in range(n - 1):
                for j in range(n - 1):
                    f = [grid[i, j], grid[i + 1, j], grid[i + 1, j + 1], grid[i, j + 1]]
                    Fc.append(f if sgn > 0 else f[::-1])
    V = np.array(V)
    if R is not None:
        V = V @ np.asarray(R).T
    V = V + np.asarray(center, float)
    # orient outward
    Fo = []
    c = V.mean(0)
    for f in Fc:
        a, b, cc = V[f[0]], V[f[1]], V[f[2]]
        nn = np.cross(b - a, cc - a)
        Fo.append(f if nn @ (a - c) > 0 else f[::-1])
    return V, Fo


def tube_mesh(pts, radius, sides=8, cap=True):
    pts = np.asarray(pts, float)
    m = len(pts)
    V = []
    Fc = []
    ref = np.array([0.3, 0.5, 0.8])
    for i in range(m):
        t = pts[min(i + 1, m - 1)] - pts[max(i - 1, 0)]
        t /= np.linalg.norm(t)
        nvec = ref - (ref @ t) * t
        nvec /= np.linalg.norm(nvec)
        ref = nvec
        b = np.cross(t, nvec)
        r = radius[i] if np.ndim(radius) else radius
        for k in range(sides):
            a = 2 * math.pi * k / sides
            V.append(pts[i] + (nvec * math.cos(a) + b * math.sin(a)) * r)
    for i in range(m - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            Fc.append([i * sides + k, i * sides + k2, (i + 1) * sides + k2, (i + 1) * sides + k])
    if cap:
        for end, sgn in ((0, -1), (m - 1, 1)):
            V.append(pts[end])
            ci = len(V) - 1
            for k in range(sides):
                k2 = (k + 1) % sides
                f = [end * sides + k, end * sides + k2, ci]
                Fc.append(f if sgn > 0 else f[::-1])
    return np.array(V), Fc
