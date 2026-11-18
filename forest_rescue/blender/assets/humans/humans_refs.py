"""Reference panels for the 9 human characters: crops, silhouette masks and orthographic views.

Sheets
------
civ  = delivery/art/civilian_survivors_turnaround_expressions.png (1536x1024, parchment bg)
sq   = delivery/art/04_expedition_squad_turnaround.png           (1536x1024, warm-grey bg)

Each character has a FRONT and a BACK full-body panel (free neutral A-pose drawings, not strict
orthographic technical drawings) plus a face inset (civilians: expression portrait; captain:
material close-up).  Back panels are used as drawn with the frlib "rear" View (camera at +Y,
image-right = world -X), so no manual mirroring is needed.

Pixel convention: (H,W,3) float [0,1], row 0 = top.  World: Blender Z up, metres, face -Y.
"""
import os

import numpy as np
from scipy import ndimage as ndi

from frlib import refs, paths

CIV = "civilian_survivors_turnaround_expressions.png"
SQ = "04_expedition_squad_turnaround.png"

# crop boxes (x0, y0, x1, y1) in sheet pixels; generous around each standing figure, inside the
# panel borders, excluding insets/labels.  ground: row (sheet coords) of the lowest boot sole.
PANELS = {
    "lf_civilian_miller": dict(sheet=CIV, front=(22, 62, 214, 500), back=(212, 62, 392, 500),
                               inset=(388, 97, 494, 247), height=1.78),
    "lf_civilian_herbalist": dict(sheet=CIV, front=(522, 62, 692, 500), back=(694, 62, 866, 500),
                                  inset=(872, 97, 990, 247), height=1.70),
    "lf_civilian_ferryman": dict(sheet=CIV, front=(1018, 62, 1202, 500), back=(1203, 62, 1378, 500),
                                 inset=(1383, 97, 1509, 247), height=1.82),
    "lf_civilian_courier": dict(sheet=CIV, front=(22, 518, 202, 992), back=(196, 518, 364, 992),
                                inset=(376, 548, 494, 702), height=1.69),
    "lf_civilian_cooper": dict(sheet=CIV, front=(520, 518, 700, 992), back=(698, 518, 868, 992),
                               inset=(869, 548, 990, 702), height=1.71),
    "lf_civilian_quarry_worker": dict(sheet=CIV, front=(1014, 518, 1206, 992), back=(1210, 518, 1382, 992),
                                      inset=(1381, 548, 1509, 702), height=1.71),
    "lf_squad_captain": dict(sheet=SQ, front=(2, 8, 238, 598), back=(240, 8, 470, 598),
                             inset=(8, 796, 194, 1010), height=1.74),
    "lf_squad_scout": dict(sheet=SQ, front=(474, 4, 722, 598), back=(724, 4, 960, 598),
                           inset=None, height=1.83),
    "lf_squad_shield_guard": dict(sheet=SQ, front=(956, 4, 1250, 598), back=(1252, 4, 1534, 598),
                                  inset=None, height=1.90),
}

# per-view silhouette tuning: thresh, clip_below offset, exclusion boxes (crop coords)
TUNE = {
    "civ": dict(thresh=0.085, sat_weight=2.2, blur=1.0, shadow=0.22),
    "sq": dict(thresh=0.060, sat_weight=2.0, blur=0.8, shadow=0.16),
}

_cache = {}


def sheet(name):
    if name not in _cache:
        _cache[name] = refs.load(name)
    return _cache[name]


def _local_bg(img, mask_guess, size=41):
    """Smooth per-pixel background colour estimated from pixels believed to be background."""
    bg = np.zeros_like(img)
    w = (~mask_guess).astype(np.float64)
    for c in range(3):
        num = ndi.uniform_filter(img[..., c] * w, size)
        den = ndi.uniform_filter(w, size)
        bg[..., c] = num / np.maximum(den, 1e-6)
    # pixels deep inside the figure get the nearest valid estimate
    bad = ndi.uniform_filter(w, size) < 0.02
    if bad.any():
        idx = ndi.distance_transform_edt(bad, return_distances=False, return_indices=True)
        bg = bg[idx[0], idx[1]]
    return bg


def figure_mask(img, kind, ground_row=None, extra_exclude=None):
    """Two-pass silhouette: global border colour, then spatially varying background + GrabCut."""
    import cv2
    t = TUNE[kind]
    m0 = refs.silhouette(img, thresh=t["thresh"] * 1.3, blur=t["blur"], sat_weight=t["sat_weight"],
                         fill_holes=True, keep="largest", clip_below=ground_row,
                         shadow_luma_drop=t["shadow"], exclude=extra_exclude, open_px=1, close_px=2)
    bg = _local_bg(img, ndi.binary_dilation(m0, iterations=6))
    diff = ndi.gaussian_filter(img, (t["blur"], t["blur"], 0)) - bg
    luma = diff @ np.array([0.299, 0.587, 0.114])
    chroma = diff - luma[..., None]
    dist = np.sqrt(luma ** 2 + t["sat_weight"] * (chroma ** 2).sum(-1))
    shadow = (luma < 0) & (luma > -t["shadow"]) & ((chroma ** 2).sum(-1) < (0.55 * t["thresh"]) ** 2)
    m1 = (dist > t["thresh"]) & ~shadow
    if ground_row is not None:
        m1[ground_row:] = False
    if extra_exclude:
        for x0, y0, x1, y1 in extra_exclude:
            m1[y0:y1, x0:x1] = False
    m1 = ndi.binary_opening(m1, iterations=1)
    m1 = ndi.binary_closing(m1, iterations=2)
    # GrabCut refinement seeded by the threshold masks
    gc = np.full(img.shape[:2], cv2.GC_PR_BGD, np.uint8)
    gc[m1] = cv2.GC_PR_FGD
    gc[ndi.binary_erosion(m1 & m0, iterations=3)] = cv2.GC_FGD
    gc[~ndi.binary_dilation(m0 | m1, iterations=6)] = cv2.GC_BGD
    if ground_row is not None:
        gc[ground_row:] = cv2.GC_BGD
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    u8 = (np.clip(img, 0, 1) * 255).astype(np.uint8)[..., ::-1].copy()
    try:
        cv2.grabCut(u8, gc, None, bgd, fgd, 4, cv2.GC_INIT_WITH_MASK)
        m = (gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)
    except cv2.error:
        m = m1
    if extra_exclude:
        for x0, y0, x1, y1 in extra_exclude:
            m[y0:y1, x0:x1] = False
    m = ndi.binary_opening(m, iterations=1)
    m = ndi.binary_fill_holes(m)
    lab, n = ndi.label(m)
    if n > 1:
        sizes = ndi.sum(m, lab, index=np.arange(1, n + 1))
        m = lab == (int(np.argmax(sizes)) + 1)
    return m


def panel(asset_id, which, ground=None, exclude=None):
    """Return (crop image, mask, box) for the front/back panel (as drawn)."""
    p = PANELS[asset_id]
    img = sheet(p["sheet"])
    box = p[which]
    kind = "civ" if p["sheet"] == CIV else "sq"
    crop = refs.crop(img, box)
    g = None if ground is None else ground - box[1]
    m = figure_mask(crop, kind, ground_row=g, extra_exclude=exclude)
    return crop, m, box


def make_view(asset_id, which, height=None, ground=None, exclude=None, ppm=None, center_col=None,
              weight=1.0):
    """Orthographic refs.View for a panel; scale from the character's real height (mask top)."""
    crop, m, box = panel(asset_id, which, ground=ground, exclude=exclude)
    h = height or PANELS[asset_id]["height"]
    x0, y0, x1, y1 = refs.bbox(m)
    if center_col is None:
        # centre between the two lowest foot blobs (robust to asymmetric arms/props)
        rows = np.nonzero(m.any(axis=1))[0]
        foot = m[max(y1 - 12, 0):y1]
        cols = np.nonzero(foot.any(axis=0))[0]
        center_col = 0.5 * (cols.min() + cols.max() + 1) if len(cols) else 0.5 * (x0 + x1)
    v = refs.fit_view(which, crop, m, "front" if which == "front" else "rear", real_height=h,
                      center_col=center_col, ppm=ppm)
    v.weight = weight
    v.box = box
    return v
