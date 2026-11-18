"""Procedural skin detail for the Ancient Maw (numpy): scales, scutes, region masks, keratin atlas.

Scale sizes follow the sheet call-outs: large 5-12 cm (neck/shoulders/head), medium 2-5 cm
(flanks/thighs/tail), fine 0.5-2 cm (belly/throat/inner limbs); transverse scutes on throat/belly,
tail underside and the front of the metatarsus/toes; osteoderms high-roughness knobs.
"""
import math

import numpy as np

import maw_body as B


def _hash3(ix, iy, iz, seed):
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    return (h & 0xFFFFFF).astype(np.float64) / float(0xFFFFFF)


def voronoi_full(P, cell, seed=0, jitter=0.85):
    """F1, F2 (metres), unit gradients of F1/F2, cell id hash in [0,1) — for points P (N,3)."""
    Q = P / cell
    i = np.floor(Q).astype(np.int64)
    n = len(P)
    f1 = np.full(n, 9.0)
    f2 = np.full(n, 9.0)
    c1 = np.zeros((n, 3))
    c2 = np.zeros((n, 3))
    id1 = np.zeros(n)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = i + np.array([dx, dy, dz])
                r = np.stack([_hash3(c[:, 0], c[:, 1], c[:, 2], seed + k) for k in range(3)], 1)
                fp = c + 0.5 + jitter * (r - 0.5)
                d = np.linalg.norm(Q - fp, axis=1)
                hid = _hash3(c[:, 0], c[:, 1], c[:, 2], seed + 7)
                m1 = d < f1
                m2 = (~m1) & (d < f2)
                f2 = np.where(m1, f1, np.where(m2, d, f2))
                c2 = np.where(m1[:, None], c1, np.where(m2[:, None], fp, c2))
                f1 = np.where(m1, d, f1)
                c1 = np.where(m1[:, None], fp, c1)
                id1 = np.where(m1, hid, id1)
    g1 = (Q - c1) / np.maximum(f1, 1e-6)[:, None]
    g2 = (Q - c2) / np.maximum(f2, 1e-6)[:, None]
    return f1 * cell, f2 * cell, g1, g2, id1


def scale_layer(P, cell, seed, depth, groove=0.22, dome=0.35, chunk=400000):
    """Height (m) + 3-D gradient of a reptile scale layer, and per-cell random id."""
    n = len(P)
    H = np.zeros(n)
    G = np.zeros((n, 3))
    ID = np.zeros(n)
    for s in range(0, n, chunk):
        e = slice(s, min(n, s + chunk))
        f1, f2, g1, g2, idc = voronoi_full(P[e], cell, seed)
        edge = (f2 - f1) / cell                     # 0 at the border
        ge = (g2 - g1)                              # gradient of edge (per cell units -> per metre below)
        t = np.clip(edge / groove, 0, 1)
        sm = t * t * (3 - 2 * t)
        dsm = np.where((edge > 0) & (edge < groove), 6 * t * (1 - t) / groove, 0.0)
        # dome: centre of the cell slightly raised
        r = np.clip(f1 / cell, 0, 1.2)
        domev = dome * (1 - r * r)
        gdome = -dome * 2 * r[:, None] * g1
        h = depth * (sm * (1 - dome) + domev)
        g = depth * ((1 - dome) * dsm[:, None] * ge + gdome) / cell
        H[e], G[e], ID[e] = h, g, idc
    return H, G, ID


def band_layer(coord, grad_dir, width, depth, sharp=0.18):
    """Transverse scutes: ridges along a scalar coordinate (metres) with direction grad_dir (N,3)."""
    ph = coord / width
    fr = ph - np.floor(ph)
    # rounded plate with a narrow groove at fr ~ 0
    t = np.clip(fr / sharp, 0, 1)
    t2 = np.clip((1 - fr) / sharp, 0, 1)
    prof = np.minimum(t * t * (3 - 2 * t), t2 * t2 * (3 - 2 * t2))
    d1 = np.where(fr < sharp, 6 * t * (1 - t) / sharp, 0.0)
    d2 = np.where(fr > 1 - sharp, -6 * t2 * (1 - t2) / sharp, 0.0)
    dprof = np.where(prof == t * t * (3 - 2 * t), d1, d2) / width
    return depth * prof, depth * dprof[:, None] * grad_dir


# ------------------------------------------------------------------------------- region masks
def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def regions(P, N):
    """Soft masks (0..1) per texel: ventral, head, neck_shoulder, limb_lower(foot), inner_limb, tail, dorsal."""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    prof = B.trunk_profile()
    zc = np.interp(y, prof["Y"], prof["zc"])
    hz = np.interp(y, prof["Y"], prof["hz"])
    t = (z - zc) / np.maximum(hz, 1e-3)
    on_trunk = (y > -3.3) & (z > 0.9) & (np.abs(x) < np.interp(y, prof["Y"], prof["hx"]) * 1.35 + 0.05)
    ventral = smoothstep(-0.5, -0.85, t) * on_trunk * smoothstep(-0.2, -0.7, N[:, 2])
    throat = smoothstep(-3.0, -3.45, -y) * 0  # placeholder (kept for clarity)
    head = smoothstep(-3.05, -3.35, y)
    neck_sh = smoothstep(-3.3, -2.9, y) * smoothstep(-1.2, -1.6, y) * (1 - ventral)
    dorsal = smoothstep(0.25, 0.7, t) * on_trunk
    tail = smoothstep(0.6, 1.0, y)
    foot = smoothstep(1.05, 0.75, z) * (np.abs(x) > 0.25)
    # inner side of the legs / arms (normal pointing to the midline)
    inner = smoothstep(0.1, 0.6, -np.sign(x) * N[:, 0]) * (z < 2.2) * (np.abs(x) > 0.3) * (y > -2.3) * (y < 0.8)
    return {"ventral": ventral, "head": head, "neck_sh": neck_sh, "dorsal": dorsal, "tail": tail,
            "foot": foot, "inner": inner, "t": t, "throat": throat}


def mouth_mask(P):
    cav = B.mouth_cavity()
    d = cav.fn(P)
    return smoothstep(0.03, -0.005, d) * (P[:, 1] < -3.2)


def scar_mask(P):
    pts = B.scar_points()
    best = np.full(len(P), 9.0)
    for a, b in zip(pts[:-1], pts[1:]):
        ab = b - a
        t = np.clip(((P - a) @ ab) / (ab @ ab), 0, 1)
        d = np.linalg.norm(P - (a + t[:, None] * ab), axis=1)
        best = np.minimum(best, d)
    return smoothstep(0.055, 0.016, best) * (P[:, 0] > 0.05), best


def knob_mask(P):
    """Osteoderm/knob/brow tips (for lighter bronze colour and high roughness)."""
    out = np.zeros(len(P))
    parts = B.osteoderms() + B.brow_knobs()
    for p in parts:
        lo, hi = p.lo - 0.02, p.hi + 0.02
        sel = np.all((P >= lo) & (P <= hi), axis=1)
        if not sel.any():
            continue
        d = p.fn(P[sel])
        out[sel] = np.maximum(out[sel], smoothstep(0.012, -0.01, d))
    return out


# ------------------------------------------------------------------------------- keratin atlas
def keratin_atlas(size=512, seed=5):
    rng = np.random.default_rng(seed)
    H = W = size
    col = np.zeros((H, W, 3))
    rough = np.full((H, W), 0.45)
    yy, xx = np.mgrid[0:H, 0:W]
    u = (xx + 0.5) / W
    v = 1.0 - (yy + 0.5) / H          # uv v (0 bottom)
    noise = np.repeat(rng.normal(0, 1, (1, W)), H, 0)
    from scipy import ndimage as ndi
    streak = ndi.gaussian_filter(rng.normal(0, 1, (H, W)), (6, 1.2))
    # teeth: u 0-0.5, v 0.25-1 ; t = 0 base -> 1 tip
    T = (v >= 0.25) & (u < 0.5)
    t = np.clip((v - 0.25) / 0.75, 0, 1)
    base = np.array([0.50, 0.40, 0.27])
    mid = np.array([0.86, 0.80, 0.66])
    tip = np.array([0.93, 0.89, 0.79])
    c = np.where((t < 0.3)[..., None], base + (mid - base) * (t / 0.3)[..., None],
                 mid + (tip - mid) * ((t - 0.3) / 0.7)[..., None])
    c = c * (1 + 0.05 * streak[..., None])
    col[T] = c[T]
    rough[T] = 0.32 + 0.1 * (1 - t[T])
    # claws: u 0.5-1, v 0.25-1
    Cm = (v >= 0.25) & (u >= 0.5)
    cb = np.array([0.20, 0.16, 0.11])
    cm = np.array([0.50, 0.40, 0.26])
    ct = np.array([0.84, 0.76, 0.58])
    c = np.where((t < 0.45)[..., None], cb + (cm - cb) * (t / 0.45)[..., None],
                 cm + (ct - cm) * ((t - 0.45) / 0.55)[..., None])
    c = c * (1 + 0.07 * streak[..., None])
    col[Cm] = c[Cm]
    rough[Cm] = 0.42 + 0.12 * (1 - t[Cm])
    # eye: u 0-0.25, v 0-0.25 : iris disc centred
    E = (v < 0.25) & (u < 0.25)
    ex = (u - 0.125) / 0.125
    ey = (v - 0.125) / 0.125
    r = np.sqrt(ex ** 2 + ey ** 2)
    ang = np.arctan2(ey, ex)
    amber = np.array([0.86, 0.55, 0.12])
    dark = np.array([0.35, 0.18, 0.04])
    radial = 0.85 + 0.15 * np.sin(ang * 23 + 3 * np.sin(ang * 7))
    ci = amber[None, None, :] * radial[..., None] * (1 - 0.35 * smoothstep(0.55, 0.95, r))[..., None]
    ci = np.where((r > 0.92)[..., None], dark, ci)
    pupil = (np.abs(ex) < 0.13 * np.sqrt(np.clip(1 - (ey / 0.75) ** 2, 0, 1))) & (np.abs(ey) < 0.75)
    ci = np.where(pupil[..., None], np.array([0.02, 0.015, 0.01]), ci)
    col[E] = ci[E]
    rough[E] = 0.08
    # tongue: u 0.5-1, v 0-0.25
    Tg = (v < 0.25) & (u >= 0.5)
    tx = (u - 0.75) / 0.25
    c = np.array([0.50, 0.22, 0.22]) * (1 - 0.25 * np.abs(tx))[..., None]
    c = c + np.array([0.08, 0.03, 0.03]) * np.exp(-(tx / 0.08) ** 2)[..., None] * -1
    c = c * (1 + 0.06 * streak[..., None])
    col[Tg] = c[Tg]
    rough[Tg] = 0.35
    # free corner
    F = (v < 0.25) & (u >= 0.25) & (u < 0.5)
    col[F] = [0.3, 0.2, 0.15]
    return np.clip(col, 0, 1), rough
