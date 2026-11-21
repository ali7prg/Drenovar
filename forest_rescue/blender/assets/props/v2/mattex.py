"""Seamless painted-style material tiles for the material-based props path (numpy only, deterministic).

Every tile is built from periodic structure fields (FFT-filtered noise, periodic Voronoi, integer-frequency
stripes), so it repeats without seams; its colours come from a ramp measured on the painting's own pixels of that
material (pixels sorted by luminance -> mean RGB per quantile, smoothed), so the value / hue distribution matches
the painting while the structure stays clean (no tiled painting fragments, no per-pixel noise).

    tiles = build_tiles(sheet_rgb, SPEC)   # {class: HxWx3 float sRGB}

Classes: wood (grain along u), iron (forged, hammered, rust), rope (twisted strands, rows of turns along v),
stone (dressed / rough block face, lichen), brass (cast, patina), ground (dirt, pebbles, fallen leaves, grass
sprigs), grass (blade gradient: v = 0 root .. 1 tip).
"""
import math

import numpy as np
from scipy import ndimage as ndi

LUMA = np.array([0.299, 0.587, 0.114])


# ----------------------------------------------------------------------------- periodic fields
def pnoise(H, W, sx, sy, rng):
    """Periodic Gaussian-correlated noise (correlation lengths sx along u / x, sy along v / y, in px), unit std."""
    w = np.fft.fft2(rng.normal(size=(H, W)))
    fy = np.fft.fftfreq(H)[:, None]
    fx = np.fft.fftfreq(W)[None, :]
    g = np.exp(-2.0 * math.pi ** 2 * ((fx * sx) ** 2 + (fy * sy) ** 2))
    n = np.real(np.fft.ifft2(w * g))
    return (n - n.mean()) / (n.std() + 1e-9)


def fbm(H, W, sx, sy, rng, octaves=4, gain=0.5):
    out = np.zeros((H, W))
    amp = 1.0
    for _ in range(octaves):
        out += amp * pnoise(H, W, max(sx, 0.6), max(sy, 0.6), rng)
        amp *= gain
        sx, sy = sx / 2.0, sy / 2.0
    return (out - out.mean()) / (out.std() + 1e-9)


def voronoi(H, W, n, rng, aniso=(1.0, 1.0)):
    """Periodic Voronoi: (F1, F2, cell id) per pixel for n random seeds (distances in px)."""
    pts = rng.uniform(0, 1, (n, 2)) * np.array([W, H])
    tiles = np.concatenate([pts + np.array([dx * W, dy * H]) for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
    ids = np.tile(np.arange(n), 9)
    from scipy.spatial import cKDTree
    tree = cKDTree(tiles * np.array([1.0 / aniso[0], 1.0 / aniso[1]]))
    yy, xx = np.mgrid[0:H, 0:W]
    q = np.stack([xx.ravel() + 0.5, yy.ravel() + 0.5], 1) * np.array([1.0 / aniso[0], 1.0 / aniso[1]])
    d, i = tree.query(q, k=2)
    return d[:, 0].reshape(H, W), d[:, 1].reshape(H, W), ids[i[:, 0]].reshape(H, W)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def rank01(x):
    """Values -> their quantile in [0, 1] (uniform histogram, order kept)."""
    flat = x.ravel()
    order = np.argsort(flat, kind="stable")
    r = np.empty(len(flat))
    r[order] = (np.arange(len(flat)) + 0.5) / len(flat)
    return r.reshape(x.shape)


def blur_wrap(img, sigma):
    return ndi.gaussian_filter(img, sigma=(sigma, sigma) + ((0,) if img.ndim == 3 else ()), mode="wrap")


# ----------------------------------------------------------------------------- painting colour ramps
def pixels(sheet, boxes, gate=None):
    out = []
    for (x0, y0, x1, y1) in boxes:
        p = sheet[y0:y1, x0:x1].reshape(-1, 3)
        if gate is not None:
            p = p[gate(p)]
        out.append(p)
    return np.concatenate(out) if out else np.zeros((0, 3))


def ramp(px, n=256, smooth=6.0, lo=0.02, hi=0.98):
    """Luminance-sorted colour ramp (n, 3) of the painted pixels (trimmed tails, smoothed along the ramp)."""
    px = np.asarray(px, float)
    order = np.argsort(px @ LUMA)
    px = px[order]
    m = len(px)
    a, b = int(m * lo), max(int(m * lo) + 1, int(m * hi))
    px = px[a:b]
    edges = np.linspace(0, len(px), n + 1).astype(int)
    lut = np.array([px[edges[i]:max(edges[i] + 1, edges[i + 1])].mean(0) for i in range(n)])
    return ndi.gaussian_filter1d(lut, smooth, axis=0, mode="nearest")


def apply_ramp(t, lut):
    t = np.clip(t, 0.0, 1.0) * (len(lut) - 1)
    i0 = np.floor(t).astype(int)
    i1 = np.minimum(i0 + 1, len(lut) - 1)
    f = (t - i0)[..., None]
    return lut[i0] * (1 - f) + lut[i1] * f


def stretch(t, lo, hi):
    """Remap a [0,1] rank field onto [lo, hi] of the ramp (contrast of the material)."""
    return lo + (hi - lo) * t


# ----------------------------------------------------------------------------- materials
def wood(size, lut, rng, lines=16):
    """Weathered oak, grain along u (x): long warped latewood lines, fibre streaks, a few seasoning checks and
    knots, silvery weathered streaks."""
    H = W = size
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    warp = pnoise(H, W, W * 0.35, H * 0.10, rng) * 0.55 + pnoise(H, W, W * 0.08, H * 0.03, rng) * 0.12
    ph = 2 * math.pi * (lines * yy / H + warp)
    late = (0.5 + 0.5 * np.sin(ph)) ** 7                                   # narrow dark latewood lines
    ph2 = 2 * math.pi * ((lines * 2 + 3) * yy / H + warp * 1.6 + 0.3)
    late2 = (0.5 + 0.5 * np.sin(ph2)) ** 9
    fade = smoothstep(-0.6, 0.9, pnoise(H, W, W * 0.25, H * 0.05, rng))    # lines come and go along the grain
    fibre = pnoise(H, W, W * 0.06, 1.3, rng)
    fibre2 = pnoise(H, W, W * 0.025, 0.8, rng)
    low = pnoise(H, W, W * 0.30, H * 0.12, rng)
    chk = pnoise(H, W, W * 0.45, 1.6, rng)
    checks = smoothstep(2.3, 2.9, chk) * smoothstep(0.2, 1.0, pnoise(H, W, W * 0.2, H * 0.2, rng))
    weather = smoothstep(0.8, 2.0, pnoise(H, W, W * 0.10, 2.5, rng))
    # knots: a few dark lens-shaped spots (periodic placement), lines darkened round them
    knots = np.zeros((H, W))
    for _ in range(2):
        cx, cy = rng.uniform(0, W), rng.uniform(0, H)
        rx, ry = rng.uniform(0.025, 0.04) * W, rng.uniform(0.012, 0.02) * H
        dx = (xx - cx + W / 2) % W - W / 2
        dy = (yy - cy + H / 2) % H - H / 2
        r = np.sqrt((dx / rx) ** 2 + (dy / ry) ** 2)
        knots = np.maximum(knots, 1.0 - smoothstep(0.55, 1.0, r))
        knots = np.maximum(knots, 0.35 * (1.0 - smoothstep(1.0, 2.6, r)))
    t = (0.55 * low + 0.45 * fibre + 0.18 * fibre2 - 1.25 * late * fade - 0.55 * late2 * (1 - fade)
         - 2.4 * checks - 1.9 * knots + 0.55 * weather)
    t = blur_wrap(t, 0.6)
    return apply_ramp(stretch(rank01(t), 0.03, 0.97), lut)


def iron(size, lut, rust_col, rng, rust_amount=0.12):
    """Forged iron: hammered facets (periodic Voronoi with lighter rims), soft mottling, pits, rust blooms."""
    H = W = size
    f1, f2, cid = voronoi(H, W, 60, rng)
    rim = smoothstep(0.0, 6.0, f2 - f1)                                    # 0 on the facet ridges
    facet_tone = (rng.uniform(-1, 1, 60))[cid]
    mott = fbm(H, W, W * 0.10, H * 0.10, rng, 4, 0.55)
    pits = smoothstep(1.7, 2.6, -pnoise(H, W, 1.6, 1.6, rng))
    t = 0.55 * mott + 0.35 * facet_tone + 0.35 * (1.0 - rim) - 1.2 * pits
    t = blur_wrap(t, 0.7)
    col = apply_ramp(stretch(rank01(t), 0.04, 0.96), lut)
    rmask = smoothstep(0.9, 1.7, fbm(H, W, W * 0.07, H * 0.07, rng, 3, 0.6) + 0.6 * pnoise(H, W, 5, 5, rng))
    rmask *= rust_amount / max(rmask.mean(), 1e-6) if rmask.mean() > rust_amount else 1.0
    rmask = np.clip(rmask, 0, 1)
    shade = (col @ LUMA)[..., None] / max(float(np.asarray(rust_col) @ LUMA), 1e-3)
    rust = np.clip(np.asarray(rust_col)[None, None] * (0.75 + 0.5 * np.clip(shade, 0.4, 1.6)), 0, 1)
    return col * (1 - 0.8 * rmask[..., None]) + rust * (0.8 * rmask[..., None])


def rope(size, lut, rng, rows=4, strands_per_tile=6):
    """Rows of twisted three-strand rope along v (one row = one rope diameter); u along the rope."""
    H = W = size
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    rh = H / rows
    row = np.floor(yy / rh)
    vr = (yy - row * rh) / rh                                             # 0..1 across one rope
    off = rng.uniform(0, 1, rows)[row.astype(int)]
    across = np.sin(math.pi * np.clip(vr, 0, 1)) ** 0.55                 # round section: dark grooves between turns
    # strands: diagonal lay (integer strand count per tile width -> seamless along u)
    ph = 2 * math.pi * (strands_per_tile * xx / W + 1.15 * vr + off)
    s = 0.5 + 0.5 * np.cos(ph)
    strand_edge = (1.0 - s) ** 6                                          # dark line between strands
    strand_body = np.sin(math.pi * ((ph / (2 * math.pi)) % 1.0)) ** 0.8   # each strand round
    fib = pnoise(H, W, 2.2, 0.7, rng) * 0.5 + pnoise(H, W, 6.0, 1.5, rng) * 0.5
    t = 1.25 * across + 0.45 * strand_body - 1.1 * strand_edge + 0.22 * fib
    t = blur_wrap(t, 0.6)
    return apply_ramp(stretch(rank01(t), 0.03, 0.97), lut)


def stone(size, lut, moss_col, rng, moss=0.10):
    """Grey dressed stone: mottled mineral tone, fine speckle, a few hairline cracks, lichen / moss spots."""
    H = W = size
    mott = fbm(H, W, W * 0.12, H * 0.12, rng, 5, 0.55)
    speck = pnoise(H, W, 1.2, 1.2, rng)
    f1, f2, _ = voronoi(H, W, 14, rng)
    crack = (1.0 - smoothstep(0.0, 2.2, f2 - f1)) * smoothstep(0.0, 1.2, pnoise(H, W, W * 0.1, H * 0.1, rng))
    t = 0.8 * mott + 0.18 * speck - 1.1 * crack
    t = blur_wrap(t, 0.6)
    col = apply_ramp(stretch(rank01(t), 0.04, 0.96), lut)
    m = smoothstep(1.1, 1.9, fbm(H, W, W * 0.06, H * 0.06, rng, 3, 0.6) + 0.5 * pnoise(H, W, 3, 3, rng))
    m = np.clip(m * (moss / max(m.mean(), 1e-6)), 0, 1) if m.mean() > moss else m
    shade = np.clip((col @ LUMA)[..., None] / max(float(np.asarray(moss_col) @ LUMA), 1e-3), 0.5, 1.4)
    mc = np.clip(np.asarray(moss_col)[None, None] * shade, 0, 1)
    return col * (1 - 0.75 * m[..., None]) + mc * (0.75 * m[..., None])


def brass(size, lut, rng):
    """Cast brass / bronze: soft broad tone, faint brushed streaks, darker patina in blotches."""
    H = W = size
    low = fbm(H, W, W * 0.25, H * 0.25, rng, 3, 0.5)
    brush = pnoise(H, W, W * 0.2, 1.5, rng)
    pat = smoothstep(0.8, 1.8, fbm(H, W, W * 0.08, H * 0.08, rng, 3, 0.6))
    t = 0.8 * low + 0.25 * brush - 1.0 * pat
    t = blur_wrap(t, 0.8)
    return apply_ramp(stretch(rank01(t), 0.05, 0.95), lut)


def ground(size, dirt_lut, leaf_cols, grass_col, pebble_lut, rng, leaves=0.16, grass=0.10, pebbles=0.06):
    """Forest-floor dirt: mottled soil, scattered pebbles, fallen leaves (rotated lens shapes), short grass sprigs."""
    H = W = size
    soil = fbm(H, W, W * 0.06, H * 0.06, rng, 5, 0.55)
    col = apply_ramp(stretch(rank01(blur_wrap(soil, 0.8)), 0.05, 0.95), dirt_lut)
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    # pebbles: periodic Voronoi cells, a share of them filled as rounded stones
    f1, f2, cid = voronoi(H, W, 220, rng)
    keep = rng.uniform(0, 1, 220) < pebbles * 3.0
    r = rng.uniform(4.0, 9.0, 220)[cid]
    peb = keep[cid] & (f1 < r)
    ptone = rng.uniform(0.2, 0.9, 220)[cid] + 0.25 * (1.0 - f1 / np.maximum(r, 1e-6))
    pc = apply_ramp(np.clip(ptone, 0, 1), pebble_lut)
    col = np.where(peb[..., None], pc, col)
    # leaves: lens shapes with a darker midrib, random orientation, periodic placement
    n_leaf = int(leaves * W * H / (14.0 * 7.0 * 2.2))
    for _ in range(n_leaf):
        cx, cy = rng.uniform(0, W), rng.uniform(0, H)
        L, Wd = rng.uniform(9, 17), rng.uniform(4, 7.5)
        a = rng.uniform(0, math.pi)
        c, s_ = math.cos(a), math.sin(a)
        x0, x1 = int(cx - L - 2), int(cx + L + 3)
        y0, y1 = int(cy - L - 2), int(cy + L + 3)
        ys = np.arange(y0, y1) % H
        xs = np.arange(x0, x1) % W
        gy, gx = np.meshgrid(np.arange(y0, y1) - cy, np.arange(x0, x1) - cx, indexing="ij")
        lu = gx * c + gy * s_
        lv = -gx * s_ + gy * c
        prof = Wd * np.sqrt(np.clip(1 - (lu / L) ** 2, 0, 1))
        inside = np.abs(lv) < prof
        if not inside.any():
            continue
        base = np.asarray(leaf_cols[rng.integers(len(leaf_cols))], float) * rng.uniform(0.8, 1.15)
        shade = 1.0 - 0.35 * (np.abs(lv) < 0.8) * (np.abs(lu) < L * 0.85) - 0.18 * (lv / np.maximum(prof, 1e-3))
        leafc = np.clip(base[None, None] * shade[..., None], 0, 1)
        sub = col[np.ix_(ys, xs)]
        sub[inside] = leafc[inside]
        col[np.ix_(ys, xs)] = sub
    # grass sprigs: short strokes, mostly upright in v
    n_spr = int(grass * W * H / 60.0)
    gcol = np.asarray(grass_col, float)
    for _ in range(n_spr):
        cx, cy = rng.uniform(0, W), rng.uniform(0, H)
        L = rng.uniform(5, 12)
        a = rng.uniform(-0.9, 0.9) - math.pi / 2
        k = np.linspace(0, 1, int(L * 2) + 2)
        px_ = (cx + np.cos(a) * L * k).astype(int) % W
        py_ = (cy + np.sin(a) * L * k).astype(int) % H
        tone = gcol * rng.uniform(0.7, 1.25) * (0.75 + 0.35 * k)[:, None]
        col[py_, px_] = np.clip(tone, 0, 1)
    return np.clip(blur_wrap(col, 0.5), 0, 1)


def grass(size, root_col, mid_col, tip_col):
    """Blade texture (u across the blade, v = 0 root .. 1 tip): root dark -> olive -> dry yellow tips, a midrib."""
    H, W = size, max(8, size // 4)
    v = (np.arange(H)[::-1] + 0.5) / H                                     # image row 0 = tip (v = 1)
    v = v[:, None] * np.ones((1, W))
    u = (np.arange(W) + 0.5) / W
    u = np.ones((H, 1)) * u[None, :]
    a = smoothstep(0.0, 0.55, v)[..., None]
    b = smoothstep(0.55, 1.0, v)[..., None]
    col = np.asarray(root_col)[None, None] * (1 - a) + np.asarray(mid_col)[None, None] * a
    col = col * (1 - b) + np.asarray(tip_col)[None, None] * b
    rib = 1.0 + 0.12 * (1.0 - smoothstep(0.0, 0.18, np.abs(u - 0.5)))[..., None]
    edge = 1.0 - 0.18 * smoothstep(0.32, 0.5, np.abs(u - 0.5))[..., None]
    return np.clip(col * rib * edge, 0, 1)
