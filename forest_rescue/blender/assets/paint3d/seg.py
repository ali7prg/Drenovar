"""Image-side reconstruction helpers (no bpy): crops, background masks, Lab k-means classes,
clump patches (watershed), RGBA tiles, atlas packing.

Pixel convention: float arrays (H,W,3) in [0,1], row 0 = top (same as frlib.refs).
"""
import os

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage import color as skcolor
from skimage import morphology, segmentation, measure

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
ART = os.path.join(REPO, "forest_rescue", "delivery", "art")

_SHEETS = {}


def sheet(name):
    if name not in _SHEETS:
        p = name if "/" in name else os.path.join(ART, name)
        _SHEETS[name] = np.asarray(Image.open(p).convert("RGB"), np.float32) / 255.0
    return _SHEETS[name]


def lab(img):
    return skcolor.rgb2lab(np.clip(img, 0, 1)).astype(np.float32)


def save(path, arr):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    a = np.clip(np.asarray(arr, np.float32), 0, 1)
    if a.ndim == 2:
        a = np.repeat(a[..., None], 3, 2)
    Image.fromarray((a * 255 + 0.5).astype(np.uint8), "RGBA" if a.shape[2] == 4 else "RGB").save(path)
    return path


def bg_colour(img, mask=None, width=4):
    if mask is not None:
        return np.median(img[~mask], axis=0)
    b = np.concatenate([img[:width].reshape(-1, 3), img[-width:].reshape(-1, 3),
                        img[:, :width].reshape(-1, 3), img[:, -width:].reshape(-1, 3)])
    return np.median(b, axis=0)


def fg_mask(img, bg=None, thresh=9.0, chroma_w=1.4, open_r=1, close_r=1, min_area=60, exclude=(),
            keep_largest=False, hole_area=0):
    """Foreground = Lab distance from the (flat) background colour > thresh (dE units)."""
    if bg is None:
        bg = bg_colour(img)
    L = lab(img)
    B = lab(np.asarray(bg, np.float32)[None, None])[0, 0]
    d = L - B
    dist = np.sqrt(d[..., 0] ** 2 + chroma_w * (d[..., 1] ** 2 + d[..., 2] ** 2))
    m = dist > thresh
    for x0, y0, x1, y1 in exclude:
        m[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] = False
    if open_r:
        m = ndi.binary_opening(m, structure=morphology.disk(open_r))
    if close_r:
        m = ndi.binary_closing(m, structure=morphology.disk(close_r))
    if hole_area:
        holes = ndi.binary_fill_holes(m) & ~m
        hl, hn = ndi.label(holes)
        if hn:
            hs = ndi.sum(holes, hl, np.arange(1, hn + 1))
            m |= np.isin(hl, np.nonzero(hs <= hole_area)[0] + 1)
    lab_, n = ndi.label(m)
    if n:
        sizes = ndi.sum(m, lab_, np.arange(1, n + 1))
        if keep_largest:
            m = lab_ == (int(np.argmax(sizes)) + 1)
        else:
            m = np.isin(lab_, np.nonzero(sizes >= min_area)[0] + 1)
    return m, dist


def kmeans_lab(img, mask, k=8, seed=1, attempts=3, weights=(0.6, 1.0, 1.0)):
    """k-means on Lab of masked pixels -> label image (-1 outside), centres (k,3) Lab."""
    L = lab(img)
    px = L[mask].reshape(-1, 3) * np.asarray(weights, np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 60, 0.2)
    cv2.setRNGSeed(seed)
    _, lbl, cen = cv2.kmeans(px.astype(np.float32), k, None, crit, attempts, cv2.KMEANS_PP_CENTERS)
    out = np.full(mask.shape, -1, np.int32)
    out[mask] = lbl.ravel()
    return out, cen / np.asarray(weights, np.float32)


def lab_hue(c):
    """Lab centre -> (L, chroma, hue degrees)."""
    return float(c[0]), float(np.hypot(c[1], c[2])), float(np.degrees(np.arctan2(c[2], c[1])) % 360)


def clean(mask, open_r=0, close_r=1, min_area=20):
    m = mask
    if close_r:
        m = ndi.binary_closing(m, structure=morphology.disk(close_r))
    if open_r:
        m = ndi.binary_opening(m, structure=morphology.disk(open_r))
    if min_area:
        m = morphology.remove_small_objects(m, min_area)
    return m


def overlay(img, masks_colours, alpha=0.55):
    out = img.copy()
    for m, c in masks_colours:
        out[m] = out[m] * (1 - alpha) + np.asarray(c, np.float32) * alpha
    return out


def label_preview(labels, img=None, alpha=0.5, seed=3):
    rng = np.random.default_rng(seed)
    n = labels.max() + 2
    pal = rng.uniform(0.15, 1.0, (n, 3)).astype(np.float32)
    pal[0] = 0
    col = pal[labels + 1]
    if img is None:
        return col
    b = segmentation.find_boundaries(labels, mode="inner")
    out = img * (1 - alpha) + col * alpha
    out[b] = (0.05, 0.05, 0.05)
    out[labels < 0] = img[labels < 0] * 0.4
    return out


# ------------------------------------------------------------------ clump patches

def clump_patches(img, mask, n_target=80, smooth=1.5, min_px=40, compact_merge=True, seed_footprint=None):
    """Cut a painted foliage mask into clump patches: watershed of luminance basins.

    Bright clump tops are seeds; the dark gaps between clumps become the boundaries.
    Returns int label image (0 = outside, 1..n patches)."""
    L = lab(img)[..., 0]
    Ls = ndi.gaussian_filter(L, smooth)
    area = mask.sum()
    # seed spacing from target count: average patch ~ area / n -> radius
    r = max(3, int(np.sqrt(area / max(n_target, 1) / np.pi) * 0.75))
    fp = morphology.disk(r) if seed_footprint is None else seed_footprint
    mx = ndi.maximum_filter(Ls, footprint=fp)
    seeds = (Ls >= mx - 1e-3) & mask
    # thin seeds: one per connected blob
    sl, ns = ndi.label(seeds)
    markers = np.zeros(mask.shape, np.int32)
    if ns:
        com = ndi.center_of_mass(seeds, sl, np.arange(1, ns + 1))
        for i, (cy, cx) in enumerate(com):
            markers[int(round(cy)), int(round(cx))] = i + 1
    # make sure every mask component has a marker
    cl, cn = ndi.label(mask)
    for i in range(1, cn + 1):
        comp = cl == i
        if not (markers[comp] > 0).any():
            ys, xs = np.nonzero(comp)
            j = len(ys) // 2
            markers[ys[j], xs[j]] = markers.max() + 1
    lbl = segmentation.watershed(-Ls, markers, mask=mask)
    # merge tiny patches into the neighbour sharing the longest border
    lbl = merge_small(lbl, min_px)
    return relabel(lbl)


def relabel(lbl):
    out = np.zeros_like(lbl)
    ids = np.unique(lbl[lbl > 0])
    for i, v in enumerate(ids):
        out[lbl == v] = i + 1
    return out


def merge_small(lbl, min_px, max_iter=8):
    for _ in range(max_iter):
        ids, counts = np.unique(lbl[lbl > 0], return_counts=True)
        small = ids[counts < min_px]
        if not len(small):
            break
        changed = False
        for s in small:
            m = lbl == s
            ring = ndi.binary_dilation(m, iterations=1) & ~m
            nb = lbl[ring]
            nb = nb[(nb > 0) & (nb != s)]
            if len(nb):
                vals, cnt = np.unique(nb, return_counts=True)
                lbl[m] = vals[np.argmax(cnt)]
                changed = True
        if not changed:
            break
    return lbl


def split_large(lbl, img, max_px, smooth=1.0):
    """Split patches larger than max_px by a second watershed pass with finer seeds."""
    out = lbl.copy()
    nxt = out.max() + 1
    L = ndi.gaussian_filter(lab(img)[..., 0], smooth)
    for v in np.unique(lbl[lbl > 0]):
        m = lbl == v
        a = m.sum()
        if a <= max_px:
            continue
        k = int(np.ceil(a / max_px))
        ys, xs = np.nonzero(m)
        pts = np.stack([xs, ys], 1).astype(np.float32)
        crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
        _, kl, cen = cv2.kmeans(pts, k, None, crit, 2, cv2.KMEANS_PP_CENTERS)
        markers = np.zeros(lbl.shape, np.int32)
        for i, (cx, cy) in enumerate(cen):
            markers[int(cy), int(cx)] = i + 1
        sub = segmentation.watershed(-L, markers, mask=m)
        for i in range(2, k + 1):
            out[sub == i] = nxt
            nxt += 1
    return relabel(out)


# ------------------------------------------------------------------ tiles

def bleed(rgb, known, iters=None):
    """Extend known colours outward (pull-push) so alpha edges never show background."""
    from frlib import texproj  # noqa
    return texproj.fill(rgb.astype(np.float64), known).astype(np.float32)


def make_tile(img, fg, patch, margin=3, scale=2, sharpen=0.6, alpha_erode=0.0, grow_fg=False):
    """RGBA tile of one patch: alpha = (patch dilated by `margin` px) & fg (true outer edge kept).

    RGB = painted pixels, bled outward from fg so edges carry foliage colour, Lanczos x`scale`
    plus a light unsharp mask. Returns tile (h*scale, w*scale, 4) float32 and the crop box."""
    ys, xs = np.nonzero(patch)
    pad = margin + 3
    x0, x1 = max(0, xs.min() - pad), min(img.shape[1], xs.max() + 1 + pad)
    y0, y1 = max(0, ys.min() - pad), min(img.shape[0], ys.max() + 1 + pad)
    p = patch[y0:y1, x0:x1]
    f = fg[y0:y1, x0:x1]
    grown = ndi.binary_dilation(p, structure=morphology.disk(margin)) if margin else p
    a = (grown & f) | p
    rgb = img[y0:y1, x0:x1].astype(np.float32)
    rgb = bleed(rgb, f)
    a_f = a.astype(np.float32)
    if scale != 1:
        h, w = a.shape
        rgb = cv2.resize(rgb, (w * scale, h * scale), interpolation=cv2.INTER_LANCZOS4)
        a_f = cv2.resize(a_f, (w * scale, h * scale), interpolation=cv2.INTER_LINEAR)
        a_f = cv2.GaussianBlur(a_f, (0, 0), 0.6 * scale / 2)
        if sharpen:
            bl = cv2.GaussianBlur(rgb, (0, 0), 1.2)
            rgb = rgb + sharpen * (rgb - bl)
    tile = np.concatenate([np.clip(rgb, 0, 1), np.clip(a_f, 0, 1)[..., None]], 2)
    return tile, (x0, y0, x1, y1)


class ShelfPacker:
    """Simple shelf packer of rectangles into a fixed region (x0,y0,w,h) of an atlas."""

    def __init__(self, region, pad=2):
        self.x0, self.y0, self.w, self.h = region
        self.pad = pad
        self.cx = 0
        self.cy = 0
        self.row_h = 0

    def place(self, w, h):
        w2, h2 = w + 2 * self.pad, h + 2 * self.pad
        if self.cx + w2 > self.w:
            self.cx = 0
            self.cy += self.row_h
            self.row_h = 0
        if self.cy + h2 > self.h or w2 > self.w:
            return None
        x, y = self.cx + self.pad, self.cy + self.pad
        self.cx += w2
        self.row_h = max(self.row_h, h2)
        return self.x0 + x, self.y0 + y


def pack_tiles(tiles, region, pad=2, scale_down_until_fit=True):
    """Pack tiles (list of (h,w,4)) into region; sorts by height. Returns positions list + scale used."""
    order = sorted(range(len(tiles)), key=lambda i: -tiles[i].shape[0])
    s = 1.0
    for _ in range(12):
        pk = ShelfPacker(region, pad)
        pos = [None] * len(tiles)
        ok = True
        for i in order:
            h, w = tiles[i].shape[:2]
            p = pk.place(int(np.ceil(w * s)), int(np.ceil(h * s)))
            if p is None:
                ok = False
                break
            pos[i] = p
        if ok:
            return pos, s
        if not scale_down_until_fit:
            raise RuntimeError("atlas region full")
        s *= 0.92
    raise RuntimeError("cannot pack tiles")


def pack_rects(sizes, region, pad=2, max_tries=14):
    """sizes: list of (w,h). Returns positions [(x,y)] (absolute) and the uniform scale used."""
    order = sorted(range(len(sizes)), key=lambda i: -sizes[i][1])
    s = 1.0
    for _ in range(max_tries):
        pk = ShelfPacker(region, pad)
        pos = [None] * len(sizes)
        ok = True
        for i in order:
            w, h = sizes[i]
            p = pk.place(max(1, int(np.ceil(w * s))), max(1, int(np.ceil(h * s))))
            if p is None:
                ok = False
                break
            pos[i] = p
        if ok:
            return pos, s
        s *= 0.92
    raise RuntimeError("cannot pack rects")
