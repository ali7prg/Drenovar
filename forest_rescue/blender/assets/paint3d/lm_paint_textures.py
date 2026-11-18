"""Landmark textures from the art/06 painting (replaces the procedural lm_wood / lm_roof / lm_misc; lm_stone is
re-quilted from the masonry close-ups): every texel comes from painted art/06 pixels (close-up swatches and the
main views), background pixels inside a swatch are filled from the painted ones (pull-push), then quilted into a
seamless tile (wood/roof/stone) or placed into the lm_misc atlas regions (same layout as before, so the landmark
geometry UVs stay valid).

python3: /opt/tools/blender-venv/bin/python forest_rescue/blender/assets/paint3d/lm_paint_textures.py
"""
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "forest"))
sys.path.insert(0, os.path.join(HERE, "..", "landmarks"))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
import seg  # noqa: E402
import swatch  # noqa: E402
import ftex  # noqa: E402
import lm_textures as old  # noqa: E402
from frlib import texproj  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RT = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "landmarks")
MASTER = os.path.join(REPO, "forest_rescue", "blender", "textures", "landmarks", "v2")
QA = os.path.join(REPO, "forest_rescue", "qa", "compare", "landmarks_textures")
SHEET = "06_environment_landmarks.png"
S = 1024

SRC = {   # art/06 sheet boxes (x0, y0, x1, y1)
    "wood": [(544, 899, 586, 926), (544, 956, 586, 978)],
    "roof": [(1376, 104, 1508, 174)],
    "stone": [(626, 782, 700, 826), (72, 690, 124, 772)],
    "canvas": (1281, 717, 1387, 830),
    "rope": (632, 899, 742, 972),
    "lantern": (1402, 717, 1478, 830),
    "carved": (499, 717, 610, 828),
    "mossstone": (624, 717, 708, 828),
    "post_band": (1006, 897, 1063, 978),
    "crate": (1451, 904, 1523, 978),
    "ivy": (40, 330, 150, 470),
    "grass": (20, 735, 130, 790),
    "fire": (955, 770, 1010, 800),
    "net": (1025, 110, 1070, 190),
    "sign": (540, 897, 588, 978),
}


def sheet():
    return seg.sheet(SHEET).astype(np.float32)


def painted(box, bg_thresh=11.0):
    """Swatch crop with background-coloured pixels replaced by pull-push fill from the painted ones."""
    S6 = sheet()
    bg = seg.bg_colour(S6)
    x0, y0, x1, y1 = box
    img = S6[y0:y1, x0:x1]
    L = seg.lab(img)
    B = seg.lab(np.asarray(bg, np.float32)[None, None])[0, 0]
    d = L - B
    dist = np.sqrt(d[..., 0] ** 2 + 1.4 * (d[..., 1] ** 2 + d[..., 2] ** 2))
    known = dist > bg_thresh
    if known.mean() < 0.98:
        img = texproj.fill(img.astype(np.float64), known).astype(np.float32)
    return img, known


def quilt(boxes, size=S, patch=56, overlap=14, n=8, seed=3, scale=2.0, match=True):
    srcs = []
    for b in boxes:
        im, _ = painted(b)
        im = cv2.resize(im, (int(im.shape[1] * scale), int(im.shape[0] * scale)), interpolation=cv2.INTER_LANCZOS4)
        srcs.append(im)
    # stack sources side by side (same height)
    h = min(s.shape[0] for s in srcs)
    src = np.concatenate([cv2.resize(s, (int(s.shape[1] * h / s.shape[0]), h)) for s in srcs], 1)
    q = swatch.quilt_tileable(src.astype(np.float64), n=n, patch=patch, overlap=overlap, seed=seed)
    if match:
        q = ftex.match_to_reference(q, src, amount=1.0, contrast=1.0)
    return np.clip(swatch.upscale_wrap(q, size, sharpen=0.6), 0, 1)


def height_of(alb, sigma=10):
    lum = alb @ np.array([0.3, 0.55, 0.15])
    pad = 32
    lp = np.pad(lum, pad, mode="wrap").astype(np.float32)
    hp = lum - cv2.GaussianBlur(lp, (0, 0), sigma)[pad:-pad, pad:-pad].astype(np.float64)
    return np.clip(0.5 + 1.6 * hp, 0, 1), np.clip(0.95 - 0.25 * lum, 0.55, 1.0)


def fit_region(img, w, h, mirror=True):
    """Fill a w x h region with the swatch: aspect-preserving scale, mirrored tiling for the rest."""
    s = max(w / img.shape[1], h / img.shape[0]) if not mirror else min(1e9, h / img.shape[0])
    im = cv2.resize(img, (max(2, int(img.shape[1] * s)), max(2, int(img.shape[0] * s))), interpolation=cv2.INTER_LANCZOS4)
    if mirror:
        t2 = np.concatenate([im, im[:, ::-1]], 1)
        reps = w // t2.shape[1] + 2
        im = np.tile(t2, (1, reps, 1))
    return im[:h, :w]


def misc_atlas():
    A = np.zeros((S, S, 4), np.float32)
    H = np.full((S, S), 0.5)
    R = np.full((S, S), 0.85)

    def put(name, rgb, a=None, rough=0.85):
        x, y, w, h = old.MISC[name]
        im = fit_region(rgb, w, h)
        A[y:y + h, x:x + w, :3] = im
        A[y:y + h, x:x + w, 3] = 1.0 if a is None else a
        hh, rr = height_of(im)
        H[y:y + h, x:x + w] = hh
        R[y:y + h, x:x + w] = rough

    can, _ = painted(SRC["canvas"])
    put("canvas", can, rough=0.95)
    rope, _ = painted(SRC["rope"])
    put("rope", rope, rough=0.9)
    lan, _ = painted(SRC["lantern"])
    lh, lw = lan.shape[:2]
    put("iron", lan[: lh // 5, lw // 4: 3 * lw // 4], rough=0.55)          # dark iron cap
    put("bronze", lan[lh // 5: lh // 3, lw // 4: 3 * lw // 4], rough=0.45)
    put("glass", lan[int(lh * 0.42): int(lh * 0.72), int(lw * 0.3): int(lw * 0.7)], rough=0.2)
    fire, _ = painted(SRC["fire"])
    put("ash", fire, rough=0.95)
    put("charcoal", fire[::-1], rough=0.95)
    post, _ = painted(SRC["post_band"])
    put("rail", post[:, : post.shape[1] // 2], rough=0.6)
    put("sign", painted(SRC["sign"])[0], rough=0.85)
    # red banner cloth (art/01 bridge banners: Lab L 38, C 43, hue 51) = the painted canvas recoloured
    from skimage import color as skc
    lab_ = seg.lab(can)
    C_ = np.hypot(lab_[..., 1], lab_[..., 2])
    Cm, Lm = np.median(C_), np.median(lab_[..., 0])
    h_ = np.radians(51.0) + (np.arctan2(lab_[..., 2], lab_[..., 1]) - np.median(np.arctan2(lab_[..., 2], lab_[..., 1])))
    Cn = C_ / max(Cm, 1e-3) * 43.0
    Ln = lab_[..., 0] - Lm + 38.0
    banner = np.clip(skc.lab2rgb(np.stack([Ln, Cn * np.cos(h_), Cn * np.sin(h_)], -1)), 0, 1).astype(np.float32)
    put("cloth_dark", banner, rough=0.95)
    ms, _ = painted(SRC["mossstone"])
    put("moss", ms[: ms.shape[0] // 2], rough=0.95)
    gr, _ = painted(SRC["grass"])
    put("grass", gr, rough=0.95)
    put("plaster", painted(SRC["stone"][0])[0], rough=0.95)
    # carved knot panels: painted carved stone close-up, opaque inside a soft ellipse (decal on the menhirs)
    car, _ = painted(SRC["carved"])
    for nm in ("knot_a", "knot_b"):
        x, y, w, h = old.MISC[nm]
        im = cv2.resize(car if nm == "knot_a" else car[:, ::-1], (w, h), interpolation=cv2.INTER_LANCZOS4)
        yy, xx = np.mgrid[0:h, 0:w]
        e = ((xx - w / 2) / (w * 0.47)) ** 2 + ((yy - h / 2) / (h * 0.47)) ** 2
        a = np.clip((1.0 - e) * 6, 0, 1)
        A[y:y + h, x:x + w, :3] = im
        A[y:y + h, x:x + w, 3] = a
        H[y:y + h, x:x + w] = height_of(im)[0]
    # ivy (alpha from painted leaves: green hue, chroma)
    S6 = sheet()
    x0, y0, x1, y1 = SRC["ivy"]
    iv = S6[y0:y1, x0:x1]
    L = seg.lab(iv)
    C = np.hypot(L[..., 1], L[..., 2])
    Hu = np.degrees(np.arctan2(L[..., 2], L[..., 1])) % 360
    leaf = (Hu > 85) & (Hu < 150) & (C > 14)
    rgb = texproj.fill(iv.astype(np.float64), leaf).astype(np.float32)
    x, y, w, h = old.MISC["leaves"]
    A[y:y + h, x:x + w, :3] = cv2.resize(rgb, (w, h), interpolation=cv2.INTER_LANCZOS4)
    A[y:y + h, x:x + w, 3] = cv2.resize(leaf.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
    # net: painted net colour on the diamond-mesh alpha (the painted net is a dark interior with thin cords)
    x, y, w, h = old.MISC["net"]
    nt, _ = painted(SRC["net"])
    yy, xx = np.mgrid[0:h, 0:w]
    a1 = np.abs(((xx + yy) % 32) - 16) < 1.8
    a2 = np.abs(((xx - yy) % 32) - 16) < 1.8
    na = (a1 | a2).astype(np.float32)
    ncol = np.percentile(nt.reshape(-1, 3), 80, axis=0)
    A[y:y + h, x:x + w, :3] = ncol[None, None] * (0.85 + 0.3 * na[..., None])
    A[y:y + h, x:x + w, 3] = na
    return A, H, R


def planks(boxes, size=S, n_planks=8, seed=4):
    """Vertical-grain planks from the painted post close-ups: each plank = a painted strip stretched along its grain,
    random mirror / offset / slight tone per plank, dark joint between planks."""
    rng = np.random.default_rng(seed)
    strips = []
    for b in boxes:
        im, _ = painted(b)
        strips.append(im[2:-2, 2:-2])
    W = size // n_planks
    out = np.zeros((size, size, 3), np.float32)
    for k in range(n_planks):
        s = strips[k % len(strips)]
        if rng.random() < 0.5:
            s = s[:, ::-1]
        if rng.random() < 0.5:
            s = s[::-1]
        p = cv2.resize(s, (W, size // 2), interpolation=cv2.INTER_CUBIC)
        p = np.concatenate([p, p[::-1]], 0)
        p = np.roll(p, int(rng.integers(0, size)), axis=0)
        p = p * rng.uniform(0.9, 1.08)
        p[:, :2] *= 0.55
        p[:, -2:] *= 0.7
        out[:, k * W:(k + 1) * W] = p
    return np.clip(out, 0, 1)


def main():
    os.makedirs(MASTER, exist_ok=True)
    os.makedirs(QA, exist_ok=True)
    out = {}
    for name, boxes, kw in (("stone", SRC["stone"], dict(patch=56, overlap=14, n=6, scale=2.5)),
                            ("wood", SRC["wood"], None),
                            ("roof", SRC["roof"], dict(patch=64, overlap=16, n=7, scale=2.0))):
        alb = quilt(boxes, **kw) if kw is not None else planks(boxes)
        if name == "stone":
            # the painted landmark masonry (mine / ruin / bridge piers / menhirs) is light grey-beige: Lab-match the
            # jointless stone quilt to the measured painted block faces (L p50 ~ 63, chroma ~ 10)
            from skimage import color as skc
            lab_ = seg.lab(alb)
            lab_[..., 0] = (lab_[..., 0] - lab_[..., 0].mean()) * 0.9 + 61.0
            lab_[..., 1:] = (lab_[..., 1:] - lab_[..., 1:].mean((0, 1))) * 0.6 + np.array([2.2, 8.8])
            alb = np.clip(skc.lab2rgb(lab_), 0, 1).astype(np.float32)
        h, r = height_of(alb)
        nrm = ftex.height_to_normal_wrap(h, 4.0)
        rough = np.stack([np.ones_like(r), r, np.zeros_like(r)], -1)
        for d in (RT, MASTER):
            ftex.save_rgb(os.path.join(d, f"lm_{name}_c.jpg"), alb, 90)
            ftex.save_rgb(os.path.join(d, f"lm_{name}_n.png"), nrm)
            ftex.save_rgb(os.path.join(d, f"lm_{name}_r.png"), rough)
        out[name] = alb
    A, H, R = misc_atlas()
    nrm = ftex.height_to_normal_wrap(H, 3.0)
    rough = np.stack([np.ones_like(R), R, np.zeros_like(R)], -1)
    for d in (RT, MASTER):
        ftex.save_rgba(os.path.join(d, "lm_misc_c.png"), A)
        ftex.save_rgb(os.path.join(d, "lm_misc_n.png"), nrm)
        ftex.save_rgb(os.path.join(d, "lm_misc_r.png"), rough)
    tiles = [cv2.resize(out[k], (384, 384)) for k in ("stone", "wood", "roof")]
    m = A[..., :3] * A[..., 3:4] + 0.85 * (1 - A[..., 3:4])
    tiles.append(cv2.resize(m, (384, 384)))
    ftex.save_rgb(os.path.join(QA, "v2_iter01_painted_textures.png"), np.concatenate(tiles, 1))
    print("landmark textures written")


if __name__ == "__main__":
    main()
