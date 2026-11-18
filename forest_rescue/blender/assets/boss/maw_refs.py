"""Reference views of the Ancient Maw turnaround (art/03) and keypose sheet (art/05).

Scale decision (documented in REPORT.md):
  the sheet annotates head height 3.6 m, hip height 2.8 m and "body length 8.0 m", but the drawing is
  not self-consistent (snout->tail tip is 870 px while the 3.6 m head line is ~320 px).  We keep the
  drawn proportions (required for silhouette IoU) and take the vertical annotations as authority:
  top of skull/brow = 3.6 m  ->  88.75 px/m in the side view.  Resulting hip (back line) 2.76 m,
  sheet dimension line (brow->tail) 8.4 m, snout->tail tip 9.8 m.
  The front view is a separate drawing and gets its own scale from the same 3.6 m height.

Anatomical sheet error: the left view shows THREE legs (near left leg, plus a far leg stepping
forward and another far leg stepping back).  `side_view(corrected=True)` removes the forward far
leg (polygon below); raw IoU is always reported as well.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))  # forest_rescue/blender
from frlib import refs  # noqa: E402

SHEET = "03_boss_ancient_maw_turnaround.png"
KEYPOSES = "05_boss_motion_keyposes.png"
BG = np.array([199, 197, 198]) / 255.0

# ---- side (left) view -------------------------------------------------------------------------
SIDE_BOX = (0, 120, 935, 485)          # full-image crop
SIDE_GROUND = 465.5                    # full-image row of the ground line
SIDE_TOP = 146.0                       # full-image row of the highest skull point (brow knob)
SIDE_HIP_COL = 445.0                   # full-image column of the hip joint  -> world Y = 0
HEAD_HEIGHT = 3.6
SIDE_PPM = (SIDE_GROUND - SIDE_TOP) / HEAD_HEIGHT  # 88.75 px/m

SIDE_EXCLUDE_FULL = [
    (0, 0, 935, 140),        # 'Body length' dimension line + text
    (0, 140, 40, 485),       # head-height dimension line
    (0, 250, 64, 330),       # head-height text
    (40, 330, 170, 485),     # human scale figure + label
    (594, 300, 660, 375),    # hip-height text
    (581, 302, 590, 485),    # hip-height line below the tail
    (890, 380, 935, 485),    # front-view foot entering the crop
]
# extra (third) leg drawn stepping forward on the far side -> removed from the corrected mask
EXTRA_LEG_POLY_FULL = [(262, 470), (262, 448), (300, 440), (318, 420), (335, 395), (318, 350),
                       (312, 330), (335, 327), (360, 328), (368, 335), (378, 347), (388, 363),
                       (394, 381), (393, 396), (378, 425), (368, 452), (360, 470)]

# ---- front view --------------------------------------------------------------------------------
FRONT_BOX = (918, 95, 1192, 485)
FRONT_GROUND = 472.0
FRONT_TOP = 114.0
FRONT_AXIS_COL = 1028.5
FRONT_PPM = (FRONT_GROUND - FRONT_TOP) / HEAD_HEIGHT  # 99.44 px/m

# ---- head close-up (3/4 left, mouth open) ------------------------------------------------------
HEAD_BOX = (0, 530, 560, 960)


def _sheet():
    return refs.load(SHEET)


def _shift(boxes, x0, y0):
    return [(a - x0, b - y0, c - x0, d - y0) for a, b, c, d in boxes]


def side_mask(img=None, corrected=True):
    img = _sheet() if img is None else img
    x0, y0, x1, y1 = SIDE_BOX
    crop = refs.crop(img, SIDE_BOX)
    m = refs.silhouette(crop, bg=BG, thresh=0.085, blur=1.0, open_px=1, close_px=2, fill_holes=600,
                        exclude=_shift(SIDE_EXCLUDE_FULL, x0, y0), clip_below=int(SIDE_GROUND - y0),
                        shadow_luma_drop=0.10)
    if corrected:
        poly = Image.new("L", (x1 - x0, y1 - y0), 0)
        ImageDraw.Draw(poly).polygon([(x - x0, y - y0) for x, y in EXTRA_LEG_POLY_FULL], fill=255)
        m = m & ~(np.asarray(poly) > 0)
        lab, n = ndi.label(m)
        if n > 1:
            sizes = ndi.sum(m, lab, index=np.arange(1, n + 1))
            m = lab == (int(np.argmax(sizes)) + 1)
    return crop, m


def side_view(corrected=True, img=None):
    crop, m = side_mask(img, corrected)
    x0, y0 = SIDE_BOX[:2]
    return refs.View(name="left" if corrected else "left_raw", image=crop, mask=m,
                     d=refs.VIEW_DIRS["left"], ppm=SIDE_PPM, ax=SIDE_HIP_COL - x0, ay=SIDE_GROUND - y0)


def side_view_mirrored(img=None, scar_inpaint=True):
    """The left view mirrored, used as a stand-in 'right' view for colour projection (scar removed)."""
    v = side_view(corrected=True, img=img)
    im = v.image.copy()
    if scar_inpaint:
        im = remove_scar(im, SIDE_BOX[0], SIDE_BOX[1])
    im = im[:, ::-1].copy()
    m = v.mask[:, ::-1].copy()
    W = im.shape[1]
    return refs.View(name="right_mirror", image=im, mask=m, d=refs.VIEW_DIRS["right"], ppm=SIDE_PPM,
                     ax=W - v.ax, ay=v.ay)


# scar in the left view: a thin pale streak from above the eye down to the cheek (full-image coords)
SCAR_POLY_FULL = [(117, 156), (122, 153), (133, 172), (148, 198), (143, 202), (129, 176)]
# scar centre line (full-image side coords): brow top -> behind the eye -> cheek
SCAR_LINE_FULL = [(120, 155), (131, 174), (145, 200)]


def remove_scar(crop, x0, y0):
    """Inpaint the pale scar streak (so it is not mirrored to the right eye)."""
    import cv2
    H, W = crop.shape[:2]
    poly = Image.new("L", (W, H), 0)
    ImageDraw.Draw(poly).polygon([(x - x0, y - y0) for x, y in SCAR_POLY_FULL], fill=255)
    mk = ndi.binary_dilation(np.asarray(poly) > 0, iterations=2).astype(np.uint8) * 255
    u8 = (np.clip(crop, 0, 1) * 255).astype(np.uint8)
    out = cv2.inpaint(u8, mk, 5, cv2.INPAINT_TELEA)
    return out.astype(np.float64) / 255.0


def front_view(img=None):
    img = _sheet() if img is None else img
    x0, y0 = FRONT_BOX[:2]
    crop = refs.crop(img, FRONT_BOX)
    m = refs.silhouette(crop, bg=BG, thresh=0.085, blur=1.0, open_px=1, close_px=2, fill_holes=300,
                        clip_below=int(FRONT_GROUND - y0), shadow_luma_drop=0.10)
    return refs.View(name="front", image=crop, mask=m, d=refs.VIEW_DIRS["front"], ppm=FRONT_PPM,
                     ax=FRONT_AXIS_COL - x0, ay=FRONT_GROUND - y0)


def head_closeup(img=None):
    img = _sheet() if img is None else img
    return refs.crop(img, HEAD_BOX)


def side_to_world(u, row):
    """Full-image side-view pixel -> (Y, Z) metres."""
    return (np.asarray(u, float) - SIDE_HIP_COL) / SIDE_PPM, (SIDE_GROUND - np.asarray(row, float)) / SIDE_PPM


def front_to_world(u, row):
    return (np.asarray(u, float) - FRONT_AXIS_COL) / FRONT_PPM, (FRONT_GROUND - np.asarray(row, float)) / FRONT_PPM


# ---- keypose sheet (art/05): 4 x 3 panels ------------------------------------------------------
KEYPOSE_PANELS = {
    # name: (x0, y0, x1, y1) full-image box of the panel
    "walk_left_contact": (0, 70, 382, 305),
    "walk_down_passing": (382, 70, 758, 305),
    "walk_right_contact": (758, 70, 1134, 305),
    "walk_up_passing": (1134, 70, 1536, 305),
    "turn_anticipation": (0, 325, 388, 620),
    "turn_planted": (388, 325, 742, 620),
    "bite_windup": (742, 325, 1112, 620),
    "bite_forward": (1112, 325, 1536, 620),
    "roar": (0, 640, 376, 960),
    "tail_sweep_telegraph": (376, 640, 712, 960),
    "tail_sweep_active": (712, 640, 1108, 960),
    "death_rest": (1108, 640, 1536, 960),
}


def keypose_panel(name, img=None):
    img = refs.load(KEYPOSES) if img is None else img
    return refs.crop(img, KEYPOSE_PANELS[name])


def keypose_mask(panel):
    bg = refs.border_color(panel)
    return refs.silhouette(panel, bg=bg, thresh=0.10, blur=1.0, open_px=1, close_px=2, fill_holes=400,
                           shadow_luma_drop=0.12)
