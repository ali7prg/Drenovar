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


def composite(tiles, n=12, size=(168, 132), per=(5, 9), seed=3):
    """Rosette-cluster tiles: several painted rosettes composited (over) inside an ellipse, random flips and
    small rotations -> large crisp top tiles built only from painting pixels (patch synthesis)."""
    rng = np.random.default_rng(seed)
    W, H = size
    out = []
    good = [t for t in tiles if t["rgba"].shape[0] >= 18 and t["rgba"].shape[1] >= 18]
    for k in range(n):
        canvas = np.zeros((H, W, 4), np.float32)
        m = rng.integers(per[0], per[1] + 1)
        cx, cy = W / 2, H / 2
        order = []
        for j in range(m):
            t = good[rng.integers(len(good))]["rgba"].copy()
            if rng.random() < 0.5:
                t = t[:, ::-1]
            ang = rng.normal(0, 18)
            sc = rng.uniform(0.9, 1.25)
            h, w = t.shape[:2]
            M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, sc)
            bw, bh = int(w * sc * 1.3) + 2, int(h * sc * 1.3) + 2
            M[0, 2] += (bw - w) / 2
            M[1, 2] += (bh - h) / 2
            t = cv2.warpAffine(t, M, (bw, bh), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
            a = rng.uniform(0, 2 * np.pi)
            r = np.sqrt(rng.random()) * 0.32
            px = int(cx + np.cos(a) * r * W - bw / 2)
            py = int(cy + np.sin(a) * r * H * 0.85 - bh / 2)
            order.append((py + bh, px, py, t))
        for _, px, py, t in sorted(order, key=lambda q: q[0]):     # lower rosettes in front
            bh, bw = t.shape[:2]
            x0, y0 = max(0, px), max(0, py)
            x1, y1 = min(W, px + bw), min(H, py + bh)
            if x1 <= x0 or y1 <= y0:
                continue
            src = t[y0 - py:y1 - py, x0 - px:x1 - px]
            al = src[..., 3:4]
            dst = canvas[y0:y1, x0:x1]
            dst[..., :3] = src[..., :3] * al + dst[..., :3] * (1 - al)
            dst[..., 3:4] = al + dst[..., 3:4] * (1 - al)
        ys, xs = np.nonzero(canvas[..., 3] > 0.05)
        if not len(ys):
            continue
        canvas = canvas[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        known = canvas[..., 3] > 0.5
        canvas[..., :3] = seg.bleed(canvas[..., :3], known)
        out.append(dict(rgba=canvas, area=int(known.sum()), lum=float(np.mean([g["lum"] for g in good]))))
    return out
