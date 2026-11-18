"""Procedural, tileable texture generation for the «Лес потерянных» forest kit (pure numpy/cv2).

* tileable value-noise / fBm / domain warp / cellular (Voronoi) fields
* bark generators (oak, pine, birch, hollow oak, willow, deadwood) -> albedo, height, roughness
* limestone generator
* colour matching to the reference bark swatches (Lab histogram matching, partial)
* height -> tangent-space normal (wrap-around Sobel, OpenGL +Y like glTF)

Arrays: float64, (H, W[, C]) in [0,1], row 0 = top of the image.
"""
import numpy as np
import cv2
from scipy.spatial import cKDTree
from skimage import color as skcolor
from skimage import exposure

REF_SHEET = "02_forest_modular_kit.png"
# exact painted swatch rectangles on art/02 (x0, y0, x1, y1), inset by 3 px
BARK_SWATCH = {
    "oak": (21, 799, 317, 983),
    "pine": (357, 799, 611, 983),
    "birch": (651, 799, 844, 983),
    "hollow": (884, 799, 1222, 983),
    "willow": (1262, 799, 1516, 983),
}


# ----------------------------------------------------------------------------- basic fields

def rng(seed):
    return np.random.default_rng(seed)


def value_noise(H, W, cy, cx, seed, interp=cv2.INTER_CUBIC):
    """Periodic value noise: lattice cy x cx (H % cy == 0, W % cx == 0 recommended)."""
    r = rng(seed)
    lat = r.random((cy, cx)).astype(np.float32)
    p = 3
    lat = np.pad(lat, p, mode="wrap")
    sy, sx = H / cy, W / cx
    big = cv2.resize(lat, (int(round((cx + 2 * p) * sx)), int(round((cy + 2 * p) * sy))), interpolation=interp)
    oy, ox = int(round(p * sy)), int(round(p * sx))
    out = big[oy:oy + H, ox:ox + W].astype(np.float64)
    return out


def fbm(H, W, cy, cx, seed, octaves=5, gain=0.5, lac=2):
    tot = np.zeros((H, W))
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        ny, nx = cy * lac ** o, cx * lac ** o
        if ny > H or nx > W:
            break
        tot += amp * value_noise(H, W, ny, nx, seed + 101 * o)
        norm += amp
        amp *= gain
    return tot / norm


def ridged(H, W, cy, cx, seed, octaves=4, gain=0.55):
    tot = np.zeros((H, W))
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        n = value_noise(H, W, cy * 2 ** o, cx * 2 ** o, seed + 37 * o)
        tot += amp * (1.0 - np.abs(2 * n - 1))
        norm += amp
        amp *= gain
    return tot / norm


def warp(field, dx, dy):
    """Sample field at (x+dx, y+dy) pixels with wrap-around (keeps tileability)."""
    H, W = field.shape[:2]
    X, Y = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    return cv2.remap(field.astype(np.float32), (X + dx).astype(np.float32), (Y + dy).astype(np.float32),
                     interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP).astype(np.float64)


def cellular(H, W, n, seed, aniso=(1.0, 1.0), jitter=1.0):
    """Periodic Voronoi: returns F1, F2 (in units of the shorter cell spacing) and cell id.

    aniso=(sx, sy) stretches cells (sy>1 -> tall cells)."""
    r = rng(seed)
    pts = r.random((n, 2))
    offs = np.array([(i, j) for i in (-1, 0, 1) for j in (-1, 0, 1)], float)
    allp = (pts[None, :, :] + offs[:, None, :]).reshape(-1, 2)
    ids = np.tile(np.arange(n), 9)
    sx, sy = aniso
    tree = cKDTree(allp / np.array([sx, sy]))
    yy, xx = np.mgrid[0:H, 0:W]
    q = np.stack([(xx + 0.5) / W, (yy + 0.5) / H], -1).reshape(-1, 2) / np.array([sx, sy])
    d, i = tree.query(q, k=2)
    scale = np.sqrt(n)
    return (d[:, 0].reshape(H, W) * scale, d[:, 1].reshape(H, W) * scale, ids[i[:, 0]].reshape(H, W))


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a + 1e-12), 0, 1)
    return t * t * (3 - 2 * t)


def ramp(t, stops):
    """Colour ramp: stops = [(pos, (r,g,b)), ...] sorted by pos."""
    t = np.clip(t, 0, 1)
    pos = np.array([s[0] for s in stops])
    cols = np.array([s[1] for s in stops], float)
    out = np.zeros(t.shape + (3,))
    for c in range(3):
        out[..., c] = np.interp(t, pos, cols[:, c])
    return out


def normalize01(a, lo=0.5, hi=99.5):
    p0, p1 = np.percentile(a, [lo, hi])
    return np.clip((a - p0) / (p1 - p0 + 1e-9), 0, 1)


# ----------------------------------------------------------------------------- normal / colour matching

def height_to_normal_wrap(h, strength=4.0):
    """Tangent-space normal (OpenGL / glTF: +X right, +Y up in texture) from a tileable height map."""
    hf = h.astype(np.float64)
    # wrap-around Sobel (cv2 has no BORDER_WRAP for Sobel)
    sm = (np.roll(hf, 1, 0) + 2 * hf + np.roll(hf, -1, 0)) / 4.0
    gx = (np.roll(sm, -1, 1) - np.roll(sm, 1, 1)) / 2.0
    sm2 = (np.roll(hf, 1, 1) + 2 * hf + np.roll(hf, -1, 1)) / 4.0
    gy = (np.roll(sm2, -1, 0) - np.roll(sm2, 1, 0)) / 2.0
    n = np.stack([-gx * strength * h.shape[1] / 256.0, gy * strength * h.shape[0] / 256.0, np.ones_like(hf)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return (n * 0.5 + 0.5).astype(np.float64)


def load_swatch(kind):
    from PIL import Image
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    art = os.path.join(here, "..", "..", "..", "delivery", "art", REF_SHEET)
    im = np.asarray(Image.open(art).convert("RGB"), np.float64) / 255.0
    x0, y0, x1, y1 = BARK_SWATCH[kind]
    return im[y0:y1, x0:x1]


def match_to_reference(albedo, ref, amount=0.85, contrast=0.85):
    """Lab histogram matching of an albedo to a painted reference (partial; contrast<1 removes
    part of the painted lighting so in-engine shading does not double it)."""
    lab = skcolor.rgb2lab(np.clip(albedo, 0, 1))
    rlab = skcolor.rgb2lab(np.clip(ref, 0, 1))
    # reduce reference L contrast around its mean (painted key light + AO are baked into the swatch)
    m = rlab[..., 0].mean()
    rlab = rlab.copy()
    rlab[..., 0] = m + (rlab[..., 0] - m) * contrast
    matched = exposure.match_histograms(lab, rlab, channel_axis=-1)
    out = lab * (1 - amount) + matched * amount
    return np.clip(skcolor.lab2rgb(out), 0, 1)


def colour_stats(img):
    lab = skcolor.rgb2lab(np.clip(img[..., :3], 0, 1)).reshape(-1, 3)
    return lab.mean(0), lab.std(0)


def delta_e(a, b):
    return float(np.linalg.norm(np.asarray(a) - np.asarray(b)))


# ----------------------------------------------------------------------------- bark generators
# Each returns dict(albedo (H,W,3), height (H,W), rough (H,W)), tileable in both directions.

def _lichen(S, seed, n=60, cluster=None, rmin=3, rmax=12):
    """Pale lichen rosettes (lobed discs), optionally clustered around given centres."""
    r = rng(seed)
    m = np.zeros((S, S), np.float32)
    for i in range(n):
        if cluster is not None and r.random() < 0.8:
            c = cluster[r.integers(len(cluster))]
            cx, cy = (c[0] + r.normal(0, 0.07)) * S, (c[1] + r.normal(0, 0.09)) * S
        else:
            cx, cy = r.random() * S, r.random() * S
        rad = r.uniform(rmin, rmax)
        k = r.integers(5, 9)
        ang = np.linspace(0, 2 * np.pi, 40, endpoint=False)
        rr = rad * (1 + 0.25 * np.sin(k * ang + r.random() * 6) + 0.1 * r.standard_normal(40))
        for ox in (-S, 0, S):
            for oy in (-S, 0, S):
                pts = np.stack([cx + ox + rr * np.cos(ang), cy + oy + rr * np.sin(ang)], -1).astype(np.int32)
                cv2.fillPoly(m, [pts], 1.0, cv2.LINE_AA)
    return m


def _moss(S, seed, cells=10, cover=0.5, sharp=0.06):
    """Clumpy moss mask with fine granular breakup (no blur blobs)."""
    low = fbm(S, S, cells, cells, seed, 4)
    gran = fbm(S, S, cells * 24, cells * 24, seed + 1, 2)
    v = low + (gran - 0.5) * 0.22
    t = np.percentile(v, 100 * (1 - cover))
    return smoothstep(t - sharp * 0.4, t + sharp * 0.4, v)


def relief(h, amount=0.3, light=(-0.6, -0.5)):
    """Baked painterly relief: cavity darkening + soft directional term from the height field."""
    hf = cv2.GaussianBlur(h.astype(np.float32), (0, 0), 1.5).astype(np.float64)
    gx = (np.roll(hf, -1, 1) - np.roll(hf, 1, 1)) * h.shape[1] / 64.0
    gy = (np.roll(hf, -1, 0) - np.roll(hf, 1, 0)) * h.shape[0] / 64.0
    d = np.clip(1.0 - (gx * light[0] + gy * light[1]), 0.4, 1.6)
    cav = cv2.GaussianBlur(h.astype(np.float32), (0, 0), 6).astype(np.float64)
    cavity = np.clip(1.0 - 1.5 * np.maximum(cav - h, 0), 0.5, 1.0)
    return (1 - amount) + amount * d * cavity


def unsharp(img, amount=0.6, sigma=1.2):
    bl = cv2.GaussianBlur(img.astype(np.float32), (0, 0), sigma, borderType=cv2.BORDER_REFLECT).astype(np.float64)
    return np.clip(img + amount * (img - bl), 0, 1)


def bark_oak(S=1024, seed=11):
    """Long narrow vertical plates, deep furrows, horizontal breaks, moss in furrows, lichen rosettes."""
    wx = (fbm(S, S, 8, 4, seed + 1, 5) - 0.5) * S * 0.035
    wy = (fbm(S, S, 8, 4, seed + 2, 5) - 0.5) * S * 0.02
    jit = (fbm(S, S, 64, 32, seed + 9, 3) - 0.5) * 6.0                 # ragged plate edges (px)
    f1, f2, cid = cellular(S, S, 200, seed + 3, aniso=(0.42, 2.4))
    e = warp(f2 - f1, wx + jit, wy + jit)
    plates = smoothstep(0.03, 0.16, e)
    cid = warp(cid.astype(np.float64), wx, wy).round().astype(int)
    brk = value_noise(S, S, 64, 8, seed + 4)                             # horizontal breaks
    breaks = 1 - 0.5 * (1 - smoothstep(0.0, 0.012, np.abs(brk - 0.5))) * smoothstep(0.6, 0.7, value_noise(S, S, 16, 16, seed + 10))
    fine = fbm(S, S, 32, 64, seed + 5, 3)
    fiber = value_noise(S, S, 8, 128, seed + 6)
    tone = rng(seed + 7).random(cid.max() + 1)[np.clip(cid, 0, cid.max())]
    h = normalize01(0.72 * plates * breaks + 0.14 * fine + 0.10 * fiber + 0.04 * tone)
    furrow = 1 - smoothstep(0.12, 0.40, h)
    base = ramp(h, [(0.0, (0.09, 0.06, 0.04)), (0.25, (0.24, 0.16, 0.10)),
                    (0.5, (0.45, 0.33, 0.21)), (0.75, (0.60, 0.46, 0.31)), (1.0, (0.74, 0.62, 0.46))])
    base *= (0.86 + 0.24 * tone)[..., None]
    base *= relief(h, 0.35)[..., None]
    moss = _moss(S, seed + 8, cells=8, cover=0.20) * (0.35 + 0.65 * furrow)
    mcol = ramp(fbm(S, S, 96, 96, seed + 11, 2), [(0, (0.30, 0.33, 0.09)), (1, (0.62, 0.62, 0.20))])
    lich = _lichen(S, seed + 12, n=70, cluster=[(0.85, 0.6), (0.1, 0.8)], rmin=3, rmax=11) * (h > 0.35)
    alb = base * (1 - moss[..., None] * 0.9) + mcol * moss[..., None] * 0.9
    alb = alb * (1 - lich[..., None] * 0.75) + np.array([0.76, 0.78, 0.68]) * lich[..., None] * 0.75
    rough = 0.80 + 0.15 * furrow + 0.05 * moss
    return dict(albedo=unsharp(alb), height=normalize01(h + 0.06 * moss + 0.05 * lich), rough=np.clip(rough, 0, 1))


def bark_pine(S=1024, seed=21):
    """Tall irregular plates, orange-red flaked interiors, grey outer scales, black crevices."""
    wx = (fbm(S, S, 8, 4, seed + 1, 4) - 0.5) * S * 0.03
    wy = (fbm(S, S, 8, 4, seed + 2, 4) - 0.5) * S * 0.03
    jit = (fbm(S, S, 64, 64, seed + 9, 3) - 0.5) * 5.0
    f1, f2, cid = cellular(S, S, 240, seed + 3, aniso=(0.45, 2.3))
    e = warp(f2 - f1, wx + jit, wy + jit)
    cid = warp(cid.astype(np.float64), wx, wy).round().astype(int)
    plates = smoothstep(0.03, 0.14, e)
    tone = rng(seed + 5).random(cid.max() + 1)[np.clip(cid, 0, cid.max())]
    # flake layers inside each plate: stepped terraces
    lay = fbm(S, S, 8, 40, seed + 4, 4)
    terr = np.floor(lay * 4 + tone * 2) / 4.0
    flake_edge = smoothstep(0.0, 0.02, np.abs(np.gradient(terr)[0]) + np.abs(np.gradient(terr)[1]))
    fine = fbm(S, S, 48, 96, seed + 6, 2)
    h = normalize01(0.70 * plates + 0.15 * terr + 0.10 * fine + 0.05 * tone)
    crev = 1 - smoothstep(0.10, 0.35, h)
    base = ramp(h, [(0.0, (0.06, 0.04, 0.03)), (0.25, (0.20, 0.12, 0.08)), (0.55, (0.38, 0.25, 0.17)),
                    (1.0, (0.55, 0.40, 0.30))])
    orange = smoothstep(0.45, 0.65, lay + 0.3 * (tone - 0.5)) * plates
    red = ramp(fine, [(0, (0.55, 0.26, 0.12)), (1, (0.78, 0.42, 0.22))])
    alb = base * (1 - orange[..., None] * 0.7) + red * orange[..., None] * 0.7
    grey = smoothstep(0.62, 0.72, tone + 0.25 * (fine - 0.5)) * plates * (1 - orange)
    alb = alb * (1 - grey[..., None] * 0.5) + np.array([0.56, 0.52, 0.48]) * grey[..., None] * 0.5
    alb = alb * (1 - 0.35 * flake_edge[..., None])
    lich = _lichen(S, seed + 12, n=24, rmin=3, rmax=8) * (h > 0.4)
    alb = alb * (1 - lich[..., None] * 0.6) + np.array([0.72, 0.74, 0.66]) * lich[..., None] * 0.6
    alb *= relief(h, 0.3)[..., None]
    rough = 0.78 + 0.18 * crev
    return dict(albedo=unsharp(alb), height=h, rough=rough)


def bark_birch(S=1024, seed=31):
    """Cream papery bark, many thin horizontal lenticels, torn peels exposing brown inner bark."""
    r = rng(seed)
    band = fbm(S, S, 16, 2, seed + 1, 5)
    alb = ramp(band, [(0, (0.82, 0.76, 0.66)), (0.5, (0.91, 0.87, 0.79)), (1, (0.97, 0.94, 0.88))])
    h = 0.6 + 0.08 * (band - 0.5)
    lent = np.zeros((S, S), np.float32)
    for _ in range(900):
        cx, cy = r.random() * S, r.random() * S
        L = r.uniform(0.01, 0.07) * S * (1 + 2 * (r.random() < 0.1))
        t = r.uniform(0.6, 2.2)
        for ox in (-S, 0, S):
            for oy in (-S, 0, S):
                cv2.ellipse(lent, (int(cx + ox), int(cy + oy)), (int(L / 2), max(1, int(round(t)))),
                            r.uniform(-3, 3), 0, 360, float(r.uniform(0.55, 1.0)), -1, cv2.LINE_AA)
    # torn peels: ragged horizontal patches showing darker inner bark; bright curled upper edge
    peel = np.zeros((S, S), np.float32)
    rim = np.zeros((S, S), np.float32)
    for _ in range(46):
        cx, cy = r.random() * S, r.random() * S
        w, hh = r.uniform(0.05, 0.16) * S, r.uniform(0.012, 0.04) * S
        n = 48
        ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
        k = np.arange(1, 7)
        coef = r.normal(0, 0.18, (6, 2)) / k[:, None]
        rad = 1 + (coef[:, 0, None] * np.cos(k[:, None] * ang) + coef[:, 1, None] * np.sin(k[:, None] * ang)).sum(0)
        rad += 0.04 * r.standard_normal(n)
        xs = cx + w / 2 * np.cos(ang) * np.clip(rad, 0.5, 1.5)
        ys = cy + hh / 2 * np.sin(ang) * np.clip(rad, 0.5, 1.5)
        for ox in (-S, 0, S):
            for oy in (-S, 0, S):
                pts = np.stack([xs + ox, ys + oy], -1).astype(np.int32)
                cv2.fillPoly(peel, [pts], 1.0, cv2.LINE_AA)
                top = pts[np.sin(ang) < -0.2]
                if len(top) > 1:
                    cv2.polylines(rim, [top], False, 1.0, 2, cv2.LINE_AA)
    inner = ramp(fbm(S, S, 48, 8, seed + 3, 3), [(0, (0.35, 0.22, 0.14)), (1, (0.62, 0.42, 0.28))])
    scar = np.zeros((S, S), np.float32)
    for _ in range(26):
        cx, cy = r.random() * S, r.random() * S
        w, hh = r.uniform(0.03, 0.09) * S, r.uniform(0.02, 0.06) * S
        pts = np.array([[cx - w / 2, cy - hh * 0.3], [cx - w * 0.15, cy - hh * 0.45], [cx + w / 2, cy - hh * 0.25],
                        [cx + w * 0.08, cy + hh * 0.6 * r.uniform(0.6, 1.2)], [cx - w * 0.1, cy + hh * 0.2]])
        pts += r.normal(0, 0.12, pts.shape) * np.array([w, hh]) * 0.5
        for ox in (-S, 0, S):
            for oy in (-S, 0, S):
                cv2.fillPoly(scar, [(pts + [ox, oy]).astype(np.int32)], 1.0, cv2.LINE_AA)
    scar = np.clip(scar * (0.75 + 0.25 * value_noise(S, S, 64, 64, seed + 5)), 0, 1)
    alb = alb * (1 - peel[..., None]) + inner * peel[..., None]
    alb = alb * (1 - lent[..., None] * 0.92) + np.array([0.08, 0.07, 0.06]) * lent[..., None] * 0.92
    alb = alb * (1 - scar[..., None] * 0.85) + np.array([0.12, 0.10, 0.08]) * scar[..., None] * 0.85
    sh = np.roll(rim, 3, 0)
    alb = alb * (1 - 0.4 * sh[..., None])
    alb = alb * (1 - rim[..., None] * 0.8) + np.array([0.98, 0.96, 0.9]) * rim[..., None] * 0.8
    warm = smoothstep(0.65, 0.9, fbm(S, S, 8, 4, seed + 6, 3))
    alb = alb * (1 - 0.12 * warm[..., None]) + np.array([0.80, 0.66, 0.50]) * 0.12 * warm[..., None]
    h = h - 0.3 * lent - 0.25 * peel - 0.3 * scar + 0.3 * rim + 0.04 * fbm(S, S, 64, 32, seed + 7, 2)
    rough = 0.6 + 0.3 * np.clip(lent + scar + peel * 0.5, 0, 1)
    return dict(albedo=unsharp(np.clip(alb, 0, 1), 0.4), height=normalize01(h), rough=np.clip(rough, 0, 1))


def _swirl(S, cx, cy, radius, strength, seed):
    """Tileable rotational warp around a knot centre (fractions of S)."""
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float64)
    dx = (xx / S - cx + 0.5) % 1.0 - 0.5
    dy = (yy / S - cy + 0.5) % 1.0 - 0.5
    d = np.sqrt(dx * dx + dy * dy)
    a = strength * np.exp(-(d / radius) ** 2)
    ca, sa = np.cos(a), np.sin(a)
    nx = dx * ca - dy * sa
    ny = dx * sa + dy * ca
    return (nx - dx) * S, (ny - dy) * S


def bark_hollow(S=1024, seed=41):
    """Gnarled flowing ridges swirling around knots, heavy moss, lichen patches."""
    wx = (fbm(S, S, 4, 4, seed + 1, 4) - 0.5) * S * 0.12
    wy = (fbm(S, S, 4, 4, seed + 2, 4) - 0.5) * S * 0.06
    for i, (kx, ky) in enumerate([(0.62, 0.45), (0.18, 0.15), (0.35, 0.8)]):
        sx, sy = _swirl(S, kx, ky, 0.09 + 0.03 * i, 2.6 - 0.6 * i, seed)
        wx += sx
        wy += sy
    rid = warp(ridged(S, S, 4, 40, seed + 3, 4), wx, wy)
    f1, f2, cid = cellular(S, S, 300, seed + 4, aniso=(0.35, 2.6))
    blocks = warp(smoothstep(0.02, 0.18, f2 - f1), wx, wy)
    fine = fbm(S, S, 96, 64, seed + 5, 2)
    h = normalize01(0.45 * rid + 0.40 * blocks + 0.15 * fine)
    furrow = 1 - smoothstep(0.15, 0.45, h)
    base = ramp(h, [(0.0, (0.10, 0.07, 0.05)), (0.3, (0.30, 0.22, 0.13)), (0.65, (0.52, 0.41, 0.27)),
                    (1.0, (0.72, 0.62, 0.47))])
    moss = _moss(S, seed + 6, cells=5, cover=0.30) * (0.4 + 0.6 * furrow)
    mcol = ramp(fbm(S, S, 128, 128, seed + 7, 2), [(0, (0.30, 0.34, 0.08)), (1, (0.64, 0.64, 0.22))])
    lich = _lichen(S, seed + 8, n=90, cluster=[(0.15, 0.6), (0.7, 0.85)], rmin=3, rmax=10) * (h > 0.3)
    alb = base * (1 - moss[..., None] * 0.92) + mcol * moss[..., None] * 0.92
    alb = alb * (1 - lich[..., None] * 0.7) + np.array([0.75, 0.77, 0.67]) * lich[..., None] * 0.7
    alb *= relief(h, 0.3)[..., None]
    rough = 0.82 + 0.12 * furrow + 0.06 * moss
    return dict(albedo=unsharp(alb), height=normalize01(h + 0.08 * moss), rough=np.clip(rough, 0, 1))


def bark_willow(S=1024, seed=51):
    """Braided diagonal fibrous strands with dark gaps and olive moss (twisting willow trunk)."""
    yy, xx = np.mgrid[0:S, 0:S] / S
    wx = (fbm(S, S, 4, 4, seed + 1, 4) - 0.5) * S * 0.05
    strands = np.zeros((S, S))
    for k, (fx, fy, amp) in enumerate([(18, 3, 1.0), (26, 5, 0.8), (12, 2, 0.6)]):
        ph = xx * fx + yy * fy + (fbm(S, S, 3, 3, seed + 10 + k, 3) - 0.5) * 2.0
        s = np.abs(np.sin(np.pi * ph)) ** 0.35
        strands = np.maximum(strands, amp * s)
    strands = warp(strands, wx, 0)
    fine = fbm(S, S, 32, 128, seed + 4, 2)
    h = normalize01(0.8 * strands + 0.2 * fine)
    gap = 1 - smoothstep(0.15, 0.45, h)
    base = ramp(h, [(0.0, (0.10, 0.08, 0.05)), (0.35, (0.33, 0.27, 0.16)), (0.7, (0.55, 0.47, 0.32)),
                    (1.0, (0.72, 0.65, 0.50))])
    moss = _moss(S, seed + 5, cells=6, cover=0.30) * (0.3 + 0.7 * gap)
    mcol = ramp(fbm(S, S, 128, 64, seed + 6, 2), [(0, (0.30, 0.33, 0.10)), (1, (0.56, 0.58, 0.22))])
    alb = base * (1 - moss[..., None] * 0.85) + mcol * moss[..., None] * 0.85
    alb *= relief(h, 0.35)[..., None]
    rough = 0.8 + 0.15 * gap
    return dict(albedo=unsharp(alb), height=h, rough=rough)


def limestone(S=1024, seed=61):
    """Pale weathered limestone: blocky fractures, pits, lichen; tileable."""
    wx = (fbm(S, S, 8, 8, seed + 1, 4) - 0.5) * S * 0.03
    jit = (fbm(S, S, 64, 64, seed + 9, 3) - 0.5) * 4.0
    f1, f2, cid = cellular(S, S, 18, seed + 2)
    crack = 1 - smoothstep(0.0, 0.035, warp(f2 - f1, wx + jit, wx + jit))
    f1b, f2b, _ = cellular(S, S, 90, seed + 3)
    crack2 = 1 - smoothstep(0.0, 0.03, warp(f2b - f1b, wx * 0.5 + jit, wx * 0.5 + jit))
    crack2 *= smoothstep(0.45, 0.6, fbm(S, S, 6, 6, seed + 10, 3))
    n1 = fbm(S, S, 8, 8, seed + 4, 7)
    pits = smoothstep(0.74, 0.8, fbm(S, S, 96, 96, seed + 5, 2))
    tone = rng(seed + 6).random(cid.max() + 1)[cid]
    h = 0.8 - 0.55 * crack - 0.25 * crack2 + 0.22 * n1 - 0.1 * pits
    alb = ramp(n1 * 0.6 + tone * 0.4, [(0, (0.55, 0.51, 0.45)), (0.5, (0.70, 0.66, 0.58)), (1, (0.82, 0.79, 0.71))])
    alb = alb * (1 - 0.6 * crack[..., None] - 0.3 * crack2[..., None] - 0.25 * pits[..., None])
    stain = smoothstep(0.55, 0.8, fbm(S, S, 4, 4, seed + 7, 4))
    alb = alb * (1 - 0.22 * stain[..., None]) + np.array([0.58, 0.48, 0.33]) * 0.22 * stain[..., None]
    lich = _lichen(S, seed + 8, n=60, rmin=2, rmax=9)
    alb = alb * (1 - 0.45 * lich[..., None]) + np.array([0.70, 0.73, 0.56]) * 0.45 * lich[..., None]
    rough = 0.86 + 0.1 * crack
    return dict(albedo=unsharp(np.clip(alb, 0, 1), 0.5), height=normalize01(h), rough=np.clip(rough, 0, 1))


BARKS = {"oak": bark_oak, "pine": bark_pine, "birch": bark_birch, "hollow": bark_hollow, "willow": bark_willow}


def finish_bark(kind, d, match_amount=0.8, contrast=0.8, normal_strength=5.0):
    """Colour-match albedo to the art/02 swatch; build normal (RGB) and glTF roughness texture."""
    ref = load_swatch(kind)
    alb = match_to_reference(d["albedo"], ref, amount=match_amount, contrast=contrast)
    nrm = height_to_normal_wrap(d["height"], normal_strength)
    H, W = d["rough"].shape
    rough = np.zeros((H, W, 3))
    rough[..., 0] = 1.0                       # (unused / occlusion = 1)
    rough[..., 1] = d["rough"]                # glTF: G = roughness
    rough[..., 2] = 0.0                       # glTF: B = metallic
    return alb, nrm, rough


def save_rgb(path, arr, quality=90):
    from PIL import Image
    import os
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    a = (np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8)
    im = Image.fromarray(a[..., :3] if a.shape[-1] >= 3 else a)
    if path.lower().endswith(".jpg"):
        im.save(path, quality=quality, subsampling=0, optimize=True)
    else:
        im.save(path, optimize=True)
    return path


def save_rgba(path, arr):
    from PIL import Image
    import os
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    a = (np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(a, "RGBA").save(path, optimize=True)
    return path
