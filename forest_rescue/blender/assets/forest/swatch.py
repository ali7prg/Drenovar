"""Bark textures synthesised from the painted swatches of art/02 (bottom row) + limestone v2.

crop -> partial de-lighting (remove the painted low-frequency light) -> toroidal image quilting with
min-error boundary cuts (tileable) -> wrap-aware 2x upscale + unsharp -> height from luminance high-pass
(+ a little procedural micro detail) -> tangent normal (OpenGL/glTF) and glTF roughness (G channel).
"""
import numpy as np
import cv2

import ftex

# painted rock face of the art/02 limestone outcrop (sheet px), used for limestone colour statistics
ROCK_FACE = [(672, 528, 748, 606), (552, 592, 668, 650), (772, 632, 846, 682)]


def delight(img, sigma=22.0, k=0.85):
    lab = cv2.cvtColor(img.astype(np.float32), cv2.COLOR_RGB2Lab)
    L = lab[..., 0]
    low = cv2.GaussianBlur(L, (0, 0), sigma, borderType=cv2.BORDER_REFLECT)
    lab[..., 0] = np.clip(L - k * (low - L.mean()), 0, 100)
    return np.clip(cv2.cvtColor(lab, cv2.COLOR_Lab2RGB), 0, 1).astype(np.float64)


def _cut_vertical(err):
    """Min-cost top-to-bottom path through err (h, w); returns column index per row."""
    h, w = err.shape
    E = err.copy()
    for i in range(1, h):
        prev = E[i - 1]
        left = np.concatenate([[np.inf], prev[:-1]])
        right = np.concatenate([prev[1:], [np.inf]])
        E[i] += np.minimum(np.minimum(left, prev), right)
    path = np.zeros(h, int)
    path[-1] = int(np.argmin(E[-1]))
    for i in range(h - 2, -1, -1):
        c = path[i + 1]
        lo, hi = max(0, c - 1), min(w, c + 2)
        path[i] = lo + int(np.argmin(E[i, lo:hi]))
    return path


def quilt_tileable(src, n=8, patch=80, overlap=16, seed=0, n_best=5):
    """Toroidal quilting: canvas n*(patch-overlap) square, every seam (including the wrap) min-cut."""
    rng = np.random.default_rng(seed)
    H, W = src.shape[:2]
    patch = min(patch, H - 2, W - 2)
    overlap = min(overlap, patch // 3)
    step = patch - overlap
    S = n * step
    src32 = src.astype(np.float32)
    out = np.zeros((S, S, 3), np.float32)
    filled = np.zeros((S, S), bool)
    for i in range(n):
        for j in range(n):
            ys = (np.arange(patch) + i * step) % S
            xs = (np.arange(patch) + j * step) % S
            tmpl = out[np.ix_(ys, xs)]
            fm = filled[np.ix_(ys, xs)]
            if not fm.any():
                y0, x0 = rng.integers(0, H - patch + 1), rng.integers(0, W - patch + 1)
            else:
                res = cv2.matchTemplate(src32, tmpl, cv2.TM_SQDIFF, mask=fm.astype(np.float32))
                flat = res.ravel()
                k = min(n_best, flat.size)
                cand = np.argpartition(flat, k - 1)[:k]
                pick = cand[rng.integers(k)]
                y0, x0 = np.unravel_index(pick, res.shape)
            P = src32[y0:y0 + patch, x0:x0 + patch]
            err = ((P - tmpl) ** 2).sum(-1)
            M = np.ones((patch, patch), np.float32)
            ov = overlap
            if fm[:, :ov].all():                         # left
                c = _cut_vertical(err[:, :ov])
                for r in range(patch):
                    M[r, :c[r]] = 0
            if fm[:, -ov:].all():                        # right (wrap)
                c = _cut_vertical(err[:, -ov:])
                for r in range(patch):
                    M[r, patch - ov + c[r] + 1:] = 0
            if fm[:ov, :].all():                         # top
                c = _cut_vertical(err[:ov, :].T)
                for col in range(patch):
                    M[:c[col], col] = 0
            if fm[-ov:, :].all():                        # bottom (wrap)
                c = _cut_vertical(err[-ov:, :].T)
                for col in range(patch):
                    M[patch - ov + c[col] + 1:, col] = 0
            M = cv2.GaussianBlur(M, (0, 0), 0.8)
            M[~fm] = 1.0
            out[np.ix_(ys, xs)] = tmpl * (1 - M[..., None]) + P * M[..., None]
            filled[np.ix_(ys, xs)] = True
    return out.astype(np.float64)


def upscale_wrap(img, size, sharpen=0.7):
    h, w = img.shape[:2]
    p = 8
    big = np.pad(img, ((p, p), (p, p), (0, 0)), mode="wrap")
    s = size / w
    up = cv2.resize(big.astype(np.float32), (int(round(big.shape[1] * s)), int(round(big.shape[0] * s))),
                    interpolation=cv2.INTER_LANCZOS4)
    o = int(round(p * s))
    up = up[o:o + size, o:o + size]
    bl = cv2.GaussianBlur(up, (0, 0), 1.6)
    return np.clip(up + sharpen * (up - bl), 0, 1).astype(np.float64)


def bark_from_swatch(kind, size=1024, seed=0, micro=0.25):
    ref = ftex.load_swatch(kind)
    ref = delight(ref)
    # quilt at native resolution, n x step ~ 2x the swatch height (repetition hidden by the cuts)
    q = quilt_tileable(ref, n=8, patch=72 if kind != "birch" else 64, overlap=16, seed=seed + 7)
    q = ftex.match_to_reference(q, ref, amount=1.0, contrast=0.95)     # restore the swatch tonal spread
    alb = upscale_wrap(q, size)
    lum = alb @ np.array([0.3, 0.55, 0.15])
    pad = 64
    lp = np.pad(lum, pad, mode="wrap").astype(np.float32)
    hp = lum - cv2.GaussianBlur(lp, (0, 0), 18)[pad:-pad, pad:-pad].astype(np.float64)
    h = np.clip(0.5 + 1.6 * hp, 0, 1)
    if micro:
        d = ftex.BARKS[kind](size, seed + 3)
        h = (1 - micro) * h + micro * d["height"]
    nrm = ftex.height_to_normal_wrap(h, 4.5)
    r = np.clip(0.93 - 0.35 * lum, 0.45, 1.0)
    rough = np.stack([np.ones_like(r), r, np.zeros_like(r)], -1)
    return alb, nrm, rough, h


# ----------------------------------------------------------------------------- limestone v2

def limestone2(S=1024, seed=61):
    """Weathered beige-grey limestone: tonal blotches, vertical weathering streaks, a few long sharp
    sub-vertical cracks and faint bedding lines, pits and lichen; colour matched to the painted rock."""
    r = ftex.rng(seed)
    tone = ftex.fbm(S, S, 4, 4, seed, 6)
    streak = ftex.warp(ftex.value_noise(S, S, 2, 10, seed + 1), (ftex.fbm(S, S, 4, 4, seed + 2, 3) - 0.5) * 40, 0)
    f1, f2, cid = ftex.cellular(S, S, 7, seed + 4, aniso=(1.0, 1.3))
    plate_tone = ftex.rng(seed + 6).random(cid.max() + 1)[cid]
    h = 0.55 + 0.25 * (tone - 0.5) + 0.06 * (streak - 0.5) + 0.08 * (plate_tone - 0.5)
    crack = np.zeros((S, S), np.float32)
    pcrack = (1 - ftex.smoothstep(0.0, 0.018, f2 - f1)) * ftex.smoothstep(0.45, 0.55, ftex.fbm(S, S, 6, 6, seed + 11, 3))
    for k in range(6):
        x, y = r.uniform(0, S), r.uniform(0, S)
        ang = np.pi / 2 + r.normal(0, 0.35)
        pts = []
        for s in range(60):
            pts.append((x, y))
            ang += r.normal(0, 0.12)
            x += 12 * np.cos(ang)
            y += 12 * np.sin(ang)
        pts = np.array(pts)
        for ox in (-S, 0, S):
            for oy in (-S, 0, S):
                cv2.polylines(crack, [(pts + [ox, oy]).astype(np.int32)], False, 1.0, int(r.integers(3, 6)), cv2.LINE_AA)
    crack = np.maximum(cv2.GaussianBlur(crack, (0, 0), 0.9), pcrack.astype(np.float32))
    pits = ftex.smoothstep(0.80, 0.85, ftex.fbm(S, S, 96, 96, seed + 5, 2))
    h = h - 0.45 * crack - 0.08 * pits
    alb = ftex.ramp(tone * 0.6 + plate_tone * 0.25 + streak * 0.15, [(0, (0.50, 0.46, 0.39)), (0.5, (0.66, 0.61, 0.52)),
                                                                   (1, (0.78, 0.74, 0.66))])
    alb *= (1 - 0.55 * crack[..., None]) * (1 - 0.18 * pits[..., None])
    lich = ftex._lichen(S, seed + 8, n=45, rmin=4, rmax=16)
    lich2 = ftex._lichen(S, seed + 9, n=25, rmin=3, rmax=10)
    alb = alb * (1 - 0.5 * lich[..., None]) + np.array([0.72, 0.74, 0.58]) * 0.5 * lich[..., None]
    alb = alb * (1 - 0.45 * lich2[..., None]) + np.array([0.80, 0.70, 0.40]) * 0.45 * lich2[..., None]
    alb = alb * ftex.relief(ftex.normalize01(h), 0.25)[..., None]
    from frlib import refs
    img = refs.load(ftex.REF_SHEET)
    ref = np.concatenate([img[y0:y1, x0:x1].reshape(-1, 3) for (x0, y0, x1, y1) in ROCK_FACE])[None]
    alb = ftex.match_to_reference(alb, ref, amount=0.85, contrast=0.85)
    nrm = ftex.height_to_normal_wrap(ftex.normalize01(h), 4.0)
    rr = np.clip(0.88 + 0.08 * crack - 0.05 * lich, 0, 1)
    rough = np.stack([np.ones_like(rr), rr, np.zeros_like(rr)], -1)
    return alb, nrm, rough, h
