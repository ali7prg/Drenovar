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

# Registration of the separately drawn back figure onto the front one (pixel shift of the anchor
# column and ppm scale), found by maximising IoU(front, back) in world XZ (fb_align search).
BACK_REG = {
    "lf_civilian_miller": (2, 1.000), "lf_civilian_herbalist": (8, 1.000),
    "lf_civilian_ferryman": (2, 1.000), "lf_civilian_courier": (0, 0.990),
    "lf_civilian_cooper": (1, 1.000), "lf_civilian_quarry_worker": (-6, 0.980),
    "lf_squad_captain": (1, 1.000), "lf_squad_scout": (-4, 1.010),
    "lf_squad_shield_guard": (-5, 0.990),
}

# Light linen on parchment defeats colour segmentation in a few places: polygons (sheet coords)
# traced on 3-4x zoomed grids that are forced to foreground.
FG_FIX = {
    ("lf_civilian_cooper", "front"): [[(618, 586), (645, 594), (657, 600), (665, 609), (671, 622),
                                       (674, 640), (677, 660), (682, 680), (689, 691), (668, 700),
                                       (640, 700), (618, 650)]],
    ("lf_civilian_cooper", "back"): [[(788, 583), (815, 588), (832, 597), (843, 607), (848, 622),
                                      (849, 645), (830, 652), (800, 642), (788, 600)]],
    ("lf_civilian_quarry_worker", "front"): [
        [(1068, 597), (1052, 600), (1045, 610), (1040, 625), (1037, 645), (1060, 652), (1070, 620)],
        [(1148, 596), (1162, 598), (1171, 606), (1176, 620), (1180, 640), (1184, 656), (1189, 668),
         (1192, 681), (1170, 690), (1150, 660)]],
    ("lf_civilian_quarry_worker", "back"): [
        [(1316, 596), (1331, 598), (1340, 606), (1346, 620), (1350, 640), (1353, 656), (1356, 668),
         (1359, 681), (1338, 690), (1322, 650)]],
    ("lf_civilian_miller", "back"): [[(338, 330), (365, 332), (368, 360), (369, 388), (352, 392),
                                      (338, 392)]],
}

# forced background (gap between the legs that ends up enclosed by the boots' contact shadow)
BG_FIX = {
    ("lf_civilian_miller", "front"): [[(106, 413), (124, 413), (127, 450), (125, 484), (101, 484),
                                       (103, 450)]],
}

# white flour stains on the miller's apron read as parchment: fill enclosed holes up to N px
HOLE_FILL = {("lf_civilian_miller", "front"): 4000, ("lf_civilian_miller", "back"): 600}

# per-view silhouette tuning: thresh, clip_below offset, exclusion boxes (crop coords)
TUNE = {
    "civ": dict(thresh=0.085, sat_weight=2.2, blur=1.0, shadow=0.22, bg_dist=0.035, ground_strict=True),
    "sq": dict(thresh=0.060, sat_weight=2.0, blur=0.8, shadow=0.16, bg_dist=0.025, ground_strict=False),
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


def _poly_mask(shape, polys, offset):
    import cv2
    m = np.zeros(shape, np.uint8)
    for poly in polys:
        pts = np.array([(x - offset[0], y - offset[1]) for x, y in poly], np.int32)
        cv2.fillPoly(m, [pts], 1)
    return m.astype(bool)


def figure_mask(img, kind, ground_row=None, extra_exclude=None, force_fg=None, hole_fill=150,
                force_bg=None):
    """Two-pass silhouette: global border colour, then spatially varying background + GrabCut.

    Painted ground shadows are removed in the bottom 11% of the figure with a strict
    darkness/chroma test (boots, trousers and hems are much darker than the shadow), and the
    image is clipped at the detected sole line.
    """
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
    if force_fg is not None:
        m0 = m0 | force_fg
        m1 = m1 | force_fg
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
    if force_fg is not None:
        gc[force_fg] = cv2.GC_FGD
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
    if force_fg is not None:
        m |= force_fg
    # pixels that are plainly background colour (parchment seen between the legs, enclosed by
    # light aprons that GrabCut models as foreground); small specks are refilled below
    plain_bg = dist < t["bg_dist"]
    if force_fg is not None:
        plain_bg &= ~force_fg
    m &= ~plain_bg
    # strict test near the ground (painted contact shadows between and around the feet)
    rows = np.nonzero(m.any(axis=1))[0]
    if len(rows) and t["ground_strict"]:
        top, bot = rows.min(), rows.max()
        z0 = int(bot - 0.11 * (bot - top))
        strict = (luma < -0.24) | ((chroma ** 2).sum(-1) > 0.085 ** 2)
        strict = ndi.binary_opening(strict, iterations=1)
        zone = np.zeros_like(m)
        zone[z0:] = True
        m = np.where(zone, m & ndi.binary_closing(strict, iterations=2), m)
        dark = (luma < -0.28) & zone
        drows = np.nonzero(dark.sum(axis=1) >= 3)[0]
        if len(drows):
            m[drows.max() + 2:] = False
    if force_bg is not None:
        m &= ~force_bg
    m = ndi.binary_opening(m, iterations=1)
    holes = ndi.binary_fill_holes(m) & ~m
    hl, hn = ndi.label(holes)
    if hn:
        hs = ndi.sum(holes, hl, index=np.arange(1, hn + 1))
        m = m | np.isin(hl, np.nonzero(hs <= hole_fill)[0] + 1)
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
    fix = FG_FIX.get((asset_id, which))
    ff = _poly_mask(crop.shape[:2], fix, box[:2]) if fix else None
    bfix = BG_FIX.get((asset_id, which))
    fb = _poly_mask(crop.shape[:2], bfix, box[:2]) if bfix else None
    m = figure_mask(crop, kind, ground_row=g, extra_exclude=exclude, force_fg=ff,
                    hole_fill=HOLE_FILL.get((asset_id, which), 150), force_bg=fb)
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
    if which == "back" and asset_id in BACK_REG:
        dx, sc = BACK_REG[asset_id]
        v.ax += dx
        v.ppm *= sc
    v.weight = weight
    v.box = box
    return v


# Portrait insets: (right-eye px, left-eye px, mouth px) in sheet coordinates.  "right" = the
# character's right eye = image-left.  Read on 3x zoomed grids of the expression portraits.
PORTRAIT_LM = {
    "lf_civilian_miller": ((417, 147), (456, 147), (441, 171)),
    "lf_civilian_herbalist": ((912, 152), (952, 151), (936, 178)),
    "lf_civilian_ferryman": ((1418, 145), (1462, 143), (1447, 172)),
    "lf_civilian_courier": ((414, 601), (452, 600), (436, 626)),
    "lf_civilian_cooper": ((911, 603), (951, 601), (936, 628)),
    "lf_civilian_quarry_worker": ((1421, 601), (1459, 598), (1446, 626)),
}


class AffineView(refs.View):
    """Front-facing view whose pixel mapping is an affine map of world (x, z) (portrait insets)."""

    def __init__(self, name, image, mask, A, weight=1.0):
        super().__init__(name=name, image=image, mask=mask, d=np.array([0.0, 1.0, 0.0]), ppm=1.0, ax=0.0, ay=0.0,
                         weight=weight)
        self.A = np.asarray(A, float)       # 2x3: [u, v] = A @ [x, z, 1]

    def project(self, P):
        P = np.asarray(P, float)
        x, z = P[..., 0], P[..., 2]
        u = self.A[0, 0] * x + self.A[0, 1] * z + self.A[0, 2]
        v = self.A[1, 0] * x + self.A[1, 1] * z + self.A[1, 2]
        return u, v, P[..., 1]


def portrait_view(asset_id, lm, weight=6.0):
    """Affine-registered portrait (eyes + mouth) onto the model's 3-D face landmarks."""
    if asset_id not in PORTRAIT_LM:
        return None
    p = PANELS[asset_id]
    x0, y0, x1, y1 = p["inset"]
    img = refs.crop(sheet(p["sheet"]), p["inset"])
    (rx, ry), (lx, ly), (mx, my) = PORTRAIT_LM[asset_id]
    src = np.array([[lm["eye_r"][0], lm["eye_r"][2], 1.0], [lm["eye_l"][0], lm["eye_l"][2], 1.0],
                    [lm["mouth"][0], lm["mouth"][2], 1.0]])
    dst = np.array([[rx - x0, ry - y0], [lx - x0, ly - y0], [mx - x0, my - y0]], float)
    A = np.linalg.solve(src, dst).T     # 2x3
    mask = np.ones(img.shape[:2], bool)
    mask[:3] = mask[-3:] = False
    mask[:, :3] = mask[:, -3:] = False
    return AffineView("portrait", img, mask, A, weight=weight)
