"""Reference analysis for art/02 kit elements: crop, background, classes, human scale, camera fit."""
import numpy as np
from scipy import ndimage as ndi
from scipy import optimize
from skimage import morphology

import seg

SHEET = "02_forest_modular_kit.png"


def human_scale(img, box, bg, real=1.8):
    """Pixel height of the grey 1.8 m human silhouette inside `box` (crop coords) -> px per metre."""
    x0, y0, x1, y1 = box
    sub = img[y0:y1, x0:x1]
    L = seg.lab(sub)
    C = np.hypot(L[..., 1], L[..., 2])
    Lb = seg.lab(np.asarray(bg, np.float32)[None, None])[0, 0]
    m = (C < 13.5) & (L[..., 0] < Lb[0] - 20)
    m = ndi.binary_opening(m, structure=np.ones((2, 2)))
    lab_, n = ndi.label(m)
    if n:
        sizes = ndi.sum(m, lab_, np.arange(1, n + 1))
        m = lab_ == (int(np.argmax(sizes)) + 1)
    ys, xs = np.nonzero(m)
    if not len(ys):
        return None, None
    h = ys.max() - ys.min() + 1
    return h / real, (x0 + xs.min(), y0 + ys.min(), x0 + xs.max() + 1, y0 + ys.max() + 1)


def fit_ground_ellipse(fg, row_min, cols=None):
    """Fit the lower half of the painted ground ellipse: bottom-most fg pixel per column below row_min.
    Returns (cx, cy, a, b, elevation_deg)."""
    H, W = fg.shape
    sub = fg.copy()
    sub[:row_min] = False
    xs, ys = [], []
    for x in range(W) if cols is None else cols:
        r = np.nonzero(sub[:, x])[0]
        if len(r):
            xs.append(x)
            ys.append(r.max())
    xs = np.array(xs, float)
    ys = np.array(ys, float)
    if len(xs) < 10:
        return None

    def resid(p):
        cx, cy, a, b = p
        q = np.clip(1 - ((xs - cx) / a) ** 2, 0, None)
        return (cy + b * np.sqrt(q)) - ys

    p0 = [xs.mean(), ys.min(), (xs.max() - xs.min()) / 2, max(4.0, ys.max() - ys.min())]
    r = optimize.least_squares(resid, p0, loss="soft_l1", f_scale=2.0)
    cx, cy, a, b = r.x
    e = float(np.degrees(np.arcsin(np.clip(b / a, 0, 1))))
    return dict(cx=float(cx), cy=float(cy), a=float(a), b=float(b), elev=e, n=len(xs))


def wood_mask(img, fg, ratio=0.85, Lmax=64, blur=1.2, min_area=150, Cmax=None, hue_rng=None, hue_max=None,
              white=None, mode="ratio"):
    """Bark pixels. mode 'ratio': low chroma relative to lightness (C/L < ratio), L < Lmax (warm foliage);
    mode 'hue': hue below hue_max (brown bark vs green foliage); white=(Lmin, Cmax): pale birch bark."""
    L = seg.lab(ndi.gaussian_filter(img, (blur, blur, 0)))
    C = np.hypot(L[..., 1], L[..., 2])
    if mode == "hue":
        H = np.degrees(np.arctan2(L[..., 2], L[..., 1])) % 360
        w = fg & (H < hue_max) & (L[..., 0] < Lmax)
        if white is not None:
            w |= fg & (L[..., 0] > white[0]) & (C < white[1])
    else:
        w = fg & (C / np.maximum(L[..., 0], 1) < ratio) & (L[..., 0] < Lmax)
    if Cmax is not None:
        w &= C < Cmax
    if hue_rng is not None:
        H = np.degrees(np.arctan2(L[..., 2], L[..., 1])) % 360
        w &= (H >= hue_rng[0]) & (H <= hue_rng[1])
    w = ndi.binary_opening(w, structure=morphology.disk(1))
    w = ndi.binary_closing(w, structure=morphology.disk(1))
    lab_, n = ndi.label(w)
    if n:
        sizes = ndi.sum(w, lab_, np.arange(1, n + 1))
        w = np.isin(lab_, np.nonzero(sizes > min_area)[0] + 1)
    return w


def keep_connected_to(mask, seed_mask, close_r=2):
    """Components of mask (after a small closing for linking) touching seed_mask."""
    linked = ndi.binary_closing(mask, structure=morphology.disk(close_r)) if close_r else mask
    lab_, n = ndi.label(linked)
    ids = np.unique(lab_[seed_mask & linked])
    ids = ids[ids > 0]
    return mask & np.isin(lab_, ids)
