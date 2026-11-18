"""Landmark textures (art/06 palette): limestone, weathered oak, mossy clay roof tiles, misc atlas.

Run via build_landmarks.py (--textures).  Outputs godot/project/assets/forest_rescue/landmarks/
lm_{stone,wood,roof}_{c.jpg,n.png,r.png} and lm_misc_{c.png (RGBA), n.png, r.png}; 1024².
"""
import os
import sys

import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "forest"))
import ftex  # noqa: E402
from ftex import fbm, value_noise, cellular, ridged, warp, smoothstep, ramp, normalize01, rng  # noqa: E402

S = 1024
MISC = {   # name: (x, y, w, h) px in lm_misc (1024²)
    "canvas": (0, 0, 512, 512), "rope": (512, 0, 256, 256), "iron": (768, 0, 128, 128), "bronze": (896, 0, 128, 128),
    "glass": (768, 128, 128, 128), "ash": (896, 128, 128, 128), "net": (512, 256, 256, 256),
    "knot_a": (768, 256, 256, 256), "moss": (0, 512, 256, 256), "grass": (256, 512, 256, 256),
    "knot_b": (512, 512, 256, 256), "cloth_dark": (768, 512, 256, 128), "rail": (768, 640, 256, 128),
    "charcoal": (0, 768, 256, 256), "plaster": (256, 768, 256, 256), "sign": (512, 768, 256, 256),
    "leaves": (768, 768, 256, 256),
}


def uv(name, pad=2.0):
    x, y, w, h = MISC[name]
    return ((x + pad) / S, 1 - (y + h - pad) / S, (x + w - pad) / S, 1 - (y + pad) / S)


def wood(seed=3):
    """Weathered grey-brown oak planks, grain along V (texture up)."""
    yy, xx = np.mgrid[0:S, 0:S] / S
    wx = (fbm(S, S, 4, 2, seed, 4) - 0.5) * S * 0.02
    grain = value_noise(S, S, 2, 96, seed + 1)
    grain = warp(grain, wx, 0)
    rings = 0.5 + 0.5 * np.sin((xx * 60 + 6 * fbm(S, S, 3, 6, seed + 2, 3)) * np.pi)
    fine = fbm(S, S, 128, 16, seed + 3, 2)
    cracks = smoothstep(0.88, 0.95, value_noise(S, S, 4, 64, seed + 4)) * smoothstep(0.5, 0.7, fbm(S, S, 6, 2, seed + 5, 2))
    h = normalize01(0.5 * grain + 0.25 * rings + 0.25 * fine - 0.6 * cracks)
    alb = ramp(h, [(0, (0.22, 0.16, 0.11)), (0.35, (0.38, 0.29, 0.20)), (0.7, (0.52, 0.42, 0.31)),
                   (1, (0.64, 0.56, 0.45))])
    grey = smoothstep(0.45, 0.75, fbm(S, S, 3, 3, seed + 6, 4))
    alb = alb * (1 - 0.3 * grey[..., None]) + np.array([0.55, 0.52, 0.47]) * 0.3 * grey[..., None]
    alb *= ftex.relief(h, 0.25)[..., None]
    rough = 0.8 + 0.15 * cracks
    return np.clip(alb, 0, 1), h, rough


MASONRY_SRC = (1363, 413, 1496, 487)     # art/06 ruin-wall close-up: grey limestone blocks, mortar joints, moss


def stone(seed=5):
    """Grey limestone masonry synthesised from the art/06 close-up inset: crop -> de-light -> 2x -> toroidal
    quilting (~4 courses per 1.6 m texture tile) -> 1024 + sharpen; height from luminance high-pass."""
    import swatch
    from frlib import refs
    img = refs.load("06_environment_landmarks.png")
    x0, y0, x1, y1 = MASONRY_SRC
    src = swatch.delight(img[y0:y1, x0:x1], sigma=14.0, k=0.8)
    src = cv2.resize(src.astype(np.float32), (src.shape[1] * 2, src.shape[0] * 2), interpolation=cv2.INTER_CUBIC)
    q = swatch.quilt_tileable(src.astype(np.float64), n=4, patch=64, overlap=16, seed=seed + 3)
    q = ftex.match_to_reference(q, img[y0:y1, x0:x1], amount=1.0, contrast=0.95)
    alb = swatch.upscale_wrap(q, S, sharpen=0.9)
    lum = alb @ np.array([0.3, 0.55, 0.15])
    pad = 64
    lp = np.pad(lum, pad, mode="wrap").astype(np.float32)
    hp = lum - cv2.GaussianBlur(lp, (0, 0), 14)[pad:-pad, pad:-pad].astype(np.float64)
    h = np.clip(0.5 + 1.8 * hp, 0, 1)
    rough = np.clip(0.95 - 0.25 * lum, 0.6, 1.0)
    return np.clip(alb, 0, 1), h, rough


def roof(seed=7):
    """Overlapping curved clay tiles (rows along U), weathered terracotta with moss tufts."""
    yy, xx = np.mgrid[0:S, 0:S] / S
    cols, rows = 8, 8
    u = xx * cols
    v = yy * rows
    row = np.floor(v)
    u2 = u + 0.5 * (row % 2)
    fu = u2 % 1.0
    fv = v % 1.0
    tile_curve = np.sin(np.pi * fu) ** 0.7                      # barrel of each tile
    overlap = smoothstep(0.0, 0.18, fv)                          # lower edge shadow from the next row
    tid = (np.floor(u2) + 37 * row).astype(int)
    tone = rng(seed).random(tid.max() + 2)[tid]
    h = normalize01(0.6 * tile_curve * overlap + 0.25 * (1 - fv) + 0.15 * fbm(S, S, 32, 32, seed + 1, 3))
    alb = ramp(tone * 0.6 + h * 0.4, [(0, (0.42, 0.20, 0.13)), (0.5, (0.56, 0.30, 0.19)), (1, (0.68, 0.42, 0.28))])
    alb *= (0.55 + 0.45 * overlap)[..., None]
    alb *= (0.8 + 0.2 * tile_curve)[..., None]
    moss = smoothstep(0.55, 0.7, fbm(S, S, 6, 6, seed + 2, 4)) * (0.5 + 0.5 * (1 - tile_curve))
    mcol = ramp(fbm(S, S, 96, 96, seed + 3, 2), [(0, (0.30, 0.34, 0.10)), (1, (0.55, 0.56, 0.18))])
    alb = alb * (1 - moss[..., None] * 0.85) + mcol * moss[..., None] * 0.85
    return np.clip(alb, 0, 1), h + moss * 0.05, 0.85 + 0.1 * moss


def knot_pattern(w, h, seed, strands=2):
    """Interlaced (celtic) knot as a height field: two sine strands crossing with over/under."""
    yy, xx = np.mgrid[0:h, 0:w] / np.array([h, w])[:, None, None]
    out = np.zeros((h, w))
    for k in range(strands):
        ph = k * np.pi
        cx = 0.5 + 0.28 * np.sin(yy * 2 * np.pi * 1.5 + ph)
        d = np.abs(xx - cx)
        band = smoothstep(0.075, 0.045, d)
        edge = smoothstep(0.09, 0.075, d) - band
        over = (np.sin(yy * 2 * np.pi * 3 + ph) > 0).astype(float)
        out = np.maximum(out, band * (0.7 + 0.3 * over) - edge * 0.2)
    return np.clip(out, 0, 1)


def misc(seed=9):
    A = np.zeros((S, S, 4))
    H = np.zeros((S, S))
    Rg = np.full((S, S), 0.85)

    def put(name, rgb, h=None, a=None, r=None):
        x, y, w, hh = MISC[name]
        A[y:y + hh, x:x + w, :3] = rgb[:hh, :w]
        A[y:y + hh, x:x + w, 3] = 1.0 if a is None else a[:hh, :w]
        if h is not None:
            H[y:y + hh, x:x + w] = h[:hh, :w]
        if r is not None:
            Rg[y:y + hh, x:x + w] = r

    def noise(w, h, c, s, o=4):
        return fbm(h, w, max(1, h // c), max(1, w // c), s, o)
    # canvas (russet, coarse weave, stains)
    w, h = 512, 512
    yy, xx = np.mgrid[0:h, 0:w]
    weave = 0.5 + 0.25 * np.sin(xx * 1.4) + 0.25 * np.sin(yy * 1.4)
    n = noise(w, h, 64, seed)
    can = ramp(n * 0.7 + 0.3 * weave, [(0, (0.36, 0.17, 0.10)), (0.5, (0.50, 0.26, 0.16)), (1, (0.62, 0.36, 0.24))])
    stain = smoothstep(0.6, 0.8, noise(w, h, 128, seed + 1))
    can *= (1 - 0.25 * stain)[..., None]
    put("canvas", can, h=weave * 0.3 + n * 0.2, r=0.95)
    # rope: twisted strands
    w, h = 256, 256
    yy, xx = np.mgrid[0:h, 0:w] / 256.0
    tw = 0.5 + 0.5 * np.sin((xx * 3 + yy * 10) * 2 * np.pi)
    rope = ramp(tw * 0.7 + 0.3 * noise(w, h, 16, seed + 2), [(0, (0.36, 0.27, 0.15)), (1, (0.70, 0.58, 0.38))])
    put("rope", rope, h=tw, r=0.9)
    for nm, col, rr in (("iron", (0.20, 0.19, 0.18), 0.6), ("bronze", (0.48, 0.34, 0.16), 0.45),
                        ("ash", (0.30, 0.28, 0.26), 0.95), ("rail", (0.24, 0.20, 0.17), 0.55)):
        x, y, w, h = MISC[nm]
        n = noise(w, h, 16, seed + len(nm))
        c = np.asarray(col)[None, None] * (0.8 + 0.4 * n[..., None])
        put(nm, c, h=n * 0.3, r=rr)
    x, y, w, h = MISC["glass"]
    yy, xx = np.mgrid[0:h, 0:w] / np.array([h, w])[:, None, None]
    glow = 1 - 0.5 * np.sqrt((xx - 0.5) ** 2 + (yy - 0.55) ** 2) * 2
    put("glass", ramp(glow, [(0, (0.80, 0.50, 0.18)), (1, (1.0, 0.86, 0.55))]), r=0.2)
    # net: diamond mesh with alpha
    w, h = 256, 256
    yy, xx = np.mgrid[0:h, 0:w]
    a1 = np.abs(((xx + yy) % 32) - 16) < 1.6
    a2 = np.abs(((xx - yy) % 32) - 16) < 1.6
    net_a = (a1 | a2).astype(float)
    put("net", np.ones((h, w, 3)) * np.array([0.55, 0.45, 0.30]), h=net_a, a=net_a, r=0.9)
    # knotwork carving (height only; albedo slightly darker in grooves)
    for nm, sd in (("knot_a", 1), ("knot_b", 2)):
        x, y, w, h = MISC[nm]
        k = knot_pattern(w, h, sd)
        edge = np.clip(cv2.dilate((k > 0.3).astype(np.float32), np.ones((5, 5))) - (k > 0.3), 0, 1)
        base = ramp(noise(w, h, 16, seed + sd), [(0, (0.40, 0.37, 0.32)), (1, (0.52, 0.49, 0.43))])
        groove = np.clip(edge + 0.6 * (k > 0.3), 0, 1)        # dark carved outline + slightly darker strands
        put(nm, base * (1 - 0.45 * edge[..., None]), h=1 - groove, a=np.clip(groove * 1.2, 0, 1), r=0.9)
    for nm, cols in (("moss", [(0, (0.28, 0.32, 0.09)), (1, (0.56, 0.58, 0.20))]),
                     ("grass", [(0, (0.40, 0.40, 0.16)), (1, (0.62, 0.58, 0.26))]),
                     ("charcoal", [(0, (0.06, 0.05, 0.05)), (1, (0.30, 0.18, 0.10))]),
                     ("plaster", [(0, (0.55, 0.50, 0.42)), (1, (0.72, 0.68, 0.60))]),
                     ("cloth_dark", [(0, (0.22, 0.18, 0.14)), (1, (0.38, 0.30, 0.22))]),
                    ):
        x, y, w, h = MISC[nm]
        n = noise(w, h, 24, seed + len(nm) * 3, 5)
        put(nm, ramp(n, cols), h=n, r=0.95)
    # ivy: hanging strands of dark-green/olive heart-shaped leaves (alpha) for ruin and mine walls
    x, y, w, h = MISC["leaves"]
    rr = np.random.default_rng(seed + 77)
    ivy_rgb = np.zeros((h, w, 3))
    ivy_a = np.zeros((h, w))
    yy, xx = np.mgrid[0:h, 0:w]
    for s in range(7):
        x0 = rr.uniform(20, w - 20)
        ln = rr.uniform(0.5, 1.0) * h
        ts = np.linspace(0, 1, 40)
        xs = x0 + 10 * np.sin(ts * rr.uniform(3, 7) + rr.uniform(0, 6))
        ys = ts * ln
        for k in range(int(ln / 9)):
            j = int(k * 9 / ln * 39)
            cx, cy = xs[j] + rr.normal(0, 4), ys[j] + rr.normal(0, 2)
            rad = rr.uniform(5, 9)
            m = ((xx - cx) ** 2 + ((yy - cy) * 1.2) ** 2) < rad ** 2
            col = np.array([0.20, 0.30, 0.10]) * rr.uniform(0.7, 1.3) + np.array([0.12, 0.08, 0]) * (rr.random() < 0.2)
            ivy_rgb[m] = np.clip(col * (0.85 + 0.3 * (yy[m] < cy)[..., None].squeeze()[:, None] if False else col), 0, 1)
            ivy_a[m] = 1.0
    put("leaves", ivy_rgb, h=ivy_a * 0.5, a=ivy_a, r=0.85)
    # sign board: wood with carved arrow-less plain board (no text)
    x, y, w, h = MISC["sign"]
    wa, wh, wr = wood(seed + 11)
    put("sign", cv2.resize(wa, (w, h)), h=cv2.resize(wh, (w, h)), r=0.85)
    return A, H, Rg


def build_all(out_dir, master_dir, qa_png=None):
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(master_dir, exist_ok=True)
    res = {}
    for name, fn in (("stone", stone), ("wood", wood), ("roof", roof)):
        alb, h, r = fn()
        nrm = ftex.height_to_normal_wrap(h, 4.0)
        rough = np.stack([np.ones_like(r), r, np.zeros_like(r)], -1)
        for d in (out_dir, master_dir):
            ftex.save_rgb(os.path.join(d, f"lm_{name}_c.jpg"), alb, 90)
            ftex.save_rgb(os.path.join(d, f"lm_{name}_n.png"), nrm)
            ftex.save_rgb(os.path.join(d, f"lm_{name}_r.png"), rough)
        res[name] = alb
    A, H, R = misc()
    nrm = ftex.height_to_normal_wrap(H, 3.0)
    rough = np.stack([np.ones_like(R), R, np.zeros_like(R)], -1)
    for d in (out_dir, master_dir):
        ftex.save_rgba(os.path.join(d, "lm_misc_c.png"), A)
        ftex.save_rgb(os.path.join(d, "lm_misc_n.png"), nrm)
        ftex.save_rgb(os.path.join(d, "lm_misc_r.png"), rough)
    if qa_png:
        tiles = [cv2.resize(res[k], (256, 256)) for k in ("stone", "wood", "roof")]
        m = A[..., :3] * A[..., 3:4] + 0.85 * (1 - A[..., 3:4])
        tiles.append(cv2.resize(m, (256, 256)))
        ftex.save_rgb(qa_png, np.concatenate(tiles, 1))
    return res
