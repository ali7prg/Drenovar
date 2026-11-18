"""Extra high-resolution clump tiles from a larger painting of the same species (e.g. the foreground oak of
art/07 panel 2: leaf rosettes drawn several times larger than on art/02), colour-matched in Lab to the
art/02 palette so front (art/02) and top (hi-res) cards agree. Used at native resolution (no upscale)."""
import cv2
import numpy as np
from scipy import ndimage as ndi
from skimage import color as skc

import p3atlas as atl
import seg


def extract(sheet, box, hue=(70, 100), cmin=38, lmin=40, min_area=120, max_area=6000, margin=1, close=1,
            rosette_px=260):
    S = seg.sheet(sheet)
    x0, y0, x1, y1 = box
    img = S[y0:y1, x0:x1].astype(np.float32)
    L = seg.lab(img)
    C = np.hypot(L[..., 1], L[..., 2])
    H = np.degrees(np.arctan2(L[..., 2], L[..., 1])) % 360
    m = (C > cmin) & (H > hue[0]) & (H < hue[1]) & (L[..., 0] > lmin)
    if close:
        m = ndi.binary_closing(m, iterations=close)
    m = ndi.binary_opening(m, iterations=1)
    lab_ = seg.clump_patches(img, m, n_target=max(4, int(m.sum() / rosette_px)), min_px=min_area // 2, compactness=0.02,
                             max_k=2.0)
    n = int(lab_.max())
    tiles = []
    for i in range(1, n + 1):
        comp = lab_ == i
        a = comp.sum()
        if a < min_area or a > max_area:
            continue
        ys, xs = np.nonzero(comp)
        bx0, bx1 = max(0, xs.min() - margin - 2), min(img.shape[1], xs.max() + margin + 3)
        by0, by1 = max(0, ys.min() - margin - 2), min(img.shape[0], ys.max() + margin + 3)
        c = comp[by0:by1, bx0:bx1]
        al = ndi.binary_dilation(c, iterations=margin).astype(np.float32) if margin else c.astype(np.float32)
        rgb = img[by0:by1, bx0:bx1]
        rgb = seg.bleed(rgb, c)
        al = cv2.GaussianBlur(al, (0, 0), 0.5)
        fill = c.mean() if c.size else 0
        if fill < 0.3:
            continue
        tiles.append(dict(rgba=np.concatenate([rgb, al[..., None]], 2), area=int(a), lum=float(L[..., 0][comp].mean())))
    return tiles


def match_palette(tiles, target_lab_pixels, l_shift=0.0):
    """Lab mean/std transfer of all tile pixels onto the target pixel statistics."""
    src = np.concatenate([seg.lab(t["rgba"][..., :3])[t["rgba"][..., 3] > 0.5] for t in tiles])
    ms, ss = src.mean(0), src.std(0) + 1e-6
    mt, st = target_lab_pixels.mean(0), target_lab_pixels.std(0) + 1e-6
    out = []
    for t in tiles:
        lab = seg.lab(t["rgba"][..., :3])
        lab = (lab - ms) / ss * st + mt
        # keep the source lightness contrast (crisp rosettes): only shift L, transfer chroma/hue
        lab[..., 0] = seg.lab(t["rgba"][..., :3])[..., 0] - ms[0] + mt[0]
        lab[..., 0] += l_shift
        rgb = np.clip(skc.lab2rgb(np.clip(lab, [0, -128, -128], [100, 127, 127])), 0, 1).astype(np.float32)
        t = dict(t)
        t["rgba"] = np.concatenate([rgb, t["rgba"][..., 3:4]], 2)
        out.append(t)
    return out


def pack(tiles, key):
    region = atl.REGIONS[key]
    sizes = [(t["rgba"].shape[1], t["rgba"].shape[0]) for t in tiles]
    pos, s = seg.pack_rects(sizes, (0, 0, region[2], region[3]), pad=3)
    img = np.zeros((region[3], region[2], 4), np.float32)
    uvs = []
    for t, p in zip(tiles, pos):
        r = t["rgba"]
        if s < 0.999:
            r = cv2.resize(r, (max(1, int(np.ceil(r.shape[1] * s))), max(1, int(np.ceil(r.shape[0] * s)))),
                           interpolation=cv2.INTER_AREA)
        h, w = r.shape[:2]
        img[p[1]:p[1] + h, p[0]:p[0] + w] = r
        ax0, ay0 = region[0] + p[0], region[1] + p[1]
        uvs.append(atl.uv_rect((ax0 + 0.5, ay0 + 0.5, ax0 + w - 0.5, ay0 + h - 0.5)))
    return img, uvs, s
