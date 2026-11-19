"""Ancient Maw v2 — reference views cut from art/03 (turnaround) and art/05 (key poses).

Pixel convention: arrays (H, W, C) float [0,1], row 0 = top.  World: Blender Z up, metres,
creature faces -Y, hip joint above the origin, feet on Z = 0.

Scale (documented in the report): the sheet's three annotations are not mutually consistent
(head-height tick 303 px, hip-height tick 243 px, length line 747 px for 3.6 / 2.8 / 8.0 m).  The two
vertical ones agree (87-88 px/m) and fix the build scale: SIDE_PPM = 88.3 px/m = skull top 3.60 m above
the ground line, hip line 2.75 m.  The drawn length line then measures 8.46 m (brow -> near tail tip) and
snout -> tail tip is 9.84 m; changing that would need a non-uniform scale (a stubbier creature than the
drawing), which the one-to-one requirement rules out.

Sheet errors handled explicitly (raw masks are always reported as well):
  * left view shows THREE legs (a far leg stepping forward, the near leg, a far leg stepping back):
    the forward far leg is cut from the corrected mask, the back far leg is matched by posing the right
    leg back for the side comparison;
  * front view shows a pale tail "triangle" hanging to 0.6 m between the legs, impossible with the side
    view (tail >= 2 m); cut from the corrected front mask.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if BLENDER_DIR not in sys.path:
    sys.path.insert(0, BLENDER_DIR)
from frlib import refs  # noqa: E402

SHEET = "03_boss_ancient_maw_turnaround.png"
KEYPOSES = "05_boss_motion_keyposes.png"
ARENA = "08_final_boss_arena.png"
BG = np.array([199, 197, 198]) / 255.0

# ---------------------------------------------------------------- left side (orthographic)
SIDE_BOX = (0, 112, 940, 482)
SIDE_GROUND = 465.0          # full-image row of the ground contact (claw/toe bottoms)
SIDE_PPM = 88.3              # px per metre (skull top row 147 -> 3.60 m)
SIDE_HIP_COL = 445.0         # full-image column of world Y = 0 (hip joint)
SIDE_EXCLUDE = [             # full-image boxes forced to background
    (0, 0, 940, 141),        # body-length line + text
    (0, 141, 30, 482),       # head-height line
    (0, 250, 62, 330),       # head-height text
    (30, 330, 175, 482),     # human scale figure + label
    (588, 300, 665, 380),    # hip-height text
    (578, 294, 593, 482),    # hip-height line + tick below the tail
    (888, 378, 940, 482),    # front-view foot entering the crop
]
# annotation strokes painted over the creature (inpainted before colour projection)
SIDE_INPAINT_LINES = [((585, 219), (585, 300), 3), ((578, 222), (592, 222), 2), ((577, 297), (592, 297), 2)]
# forward far leg (sheet error) polygon, full-image coords
EXTRA_LEG_POLY = [(262, 470), (262, 448), (300, 440), (318, 420), (335, 395), (322, 352), (318, 333),
                  (336, 327), (358, 330), (368, 337), (377, 349), (386, 364), (390, 381), (388, 397),
                  (376, 425), (366, 452), (358, 470)]
# healed scar over the LEFT eye in the side view (removed before mirroring to the right side)
SIDE_SCAR_POLY = [(117, 156), (123, 152), (134, 170), (149, 197), (143, 201), (129, 176)]

# ---------------------------------------------------------------- front (orthographic)
FRONT_BOX = (912, 100, 1162, 478)
FRONT_GROUND = 466.0
FRONT_TOP = 114.5            # head top row -> 3.60 m
FRONT_AXIS_COL = 1029.5      # symmetry axis column (mean of the left/right body extents)
FRONT_PPM = (FRONT_GROUND - FRONT_TOP) / 3.60
# pale tail "triangle" (sheet error) polygon
FRONT_TRIANGLE_POLY = [(1004, 333), (1060, 333), (1046, 360), (1036, 400), (1032, 410), (1027, 400),
                       (1018, 360)]

# ---------------------------------------------------------------- rear three-quarter (perspective)
REAR_BOX = (1150, 105, 1536, 482)
REAR_GROUND = 470.0

# ---------------------------------------------------------------- head close-up (perspective)
HEAD_BOX = (0, 528, 545, 1005)
HEAD_EXCLUDE = [(95, 955, 340, 1005)]   # caption text


def sheet():
    return refs.load(SHEET)


def _poly_mask(shape, poly, x0, y0):
    H, W = shape
    im = Image.new("L", (W, H), 0)
    ImageDraw.Draw(im).polygon([(x - x0, y - y0) for x, y in poly], fill=255)
    return np.asarray(im) > 0


def _shift(boxes, x0, y0):
    return [(a - x0, b - y0, c - x0, d - y0) for a, b, c, d in boxes]


def _largest(m):
    lab, n = ndi.label(m)
    if n <= 1:
        return m
    s = ndi.sum(m, lab, index=np.arange(1, n + 1))
    return lab == (int(np.argmax(s)) + 1)


def inpaint(img, mask, radius=4):
    import cv2
    u8 = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    mk = (ndi.binary_dilation(mask, iterations=1)).astype(np.uint8) * 255
    out = cv2.inpaint(u8, mk, radius, cv2.INPAINT_TELEA)
    return out.astype(np.float64) / 255.0


def side_mask(img=None, corrected=True):
    img = sheet() if img is None else img
    x0, y0, x1, y1 = SIDE_BOX
    crop = refs.crop(img, SIDE_BOX)
    m = refs.silhouette(crop, bg=BG, thresh=0.085, blur=1.0, open_px=1, close_px=2, fill_holes=600,
                        exclude=_shift(SIDE_EXCLUDE, x0, y0), clip_below=int(SIDE_GROUND - y0) + 1,
                        shadow_luma_drop=0.10, keep="largest")
    if corrected:
        m = _largest(m & ~_poly_mask(m.shape, EXTRA_LEG_POLY, x0, y0))
    return crop, m


def side_colour(img=None, remove_scar=False):
    """Side crop with annotation strokes inpainted (and optionally the scar) for colour projection."""
    import cv2
    img = sheet() if img is None else img
    x0, y0 = SIDE_BOX[:2]
    crop = refs.crop(img, SIDE_BOX)
    mk = np.zeros(crop.shape[:2], np.uint8)
    for (a, b), (c, d), w in SIDE_INPAINT_LINES:
        cv2.line(mk, (a - x0, b - y0), (c - x0, d - y0), 255, w)
    m = mk > 0
    if remove_scar:
        m |= ndi.binary_dilation(_poly_mask(m.shape, SIDE_SCAR_POLY, x0, y0), iterations=3)
        # plus every pale lilac pixel of the scar streak around the eye (colour detection)
        r, g, b = crop[..., 0], crop[..., 1], crop[..., 2]
        lum = crop @ np.array([0.3, 0.59, 0.11])
        loc = cv2.GaussianBlur(lum.astype(np.float32), (0, 0), 3)
        pink = ((r - g) + (b - g) > 0.06) & (lum - loc > 0.03)
        win = np.zeros_like(pink)
        win[140 - y0:215 - y0, 100 - x0:165 - x0] = True
        m |= ndi.binary_dilation(pink & win, iterations=1)
    return inpaint(crop, ndi.binary_dilation(m, iterations=1), 5)


def side_view(corrected=True, img=None, colour=True):
    crop, m = side_mask(img, corrected)
    if colour:
        crop = side_colour(img)
    x0, y0 = SIDE_BOX[:2]
    return refs.View(name="left" if corrected else "left_raw", image=crop, mask=m, d=refs.VIEW_DIRS["left"],
                     ppm=SIDE_PPM, ax=SIDE_HIP_COL - x0, ay=SIDE_GROUND - y0)


def front_mask(img=None, corrected=True):
    img = sheet() if img is None else img
    x0, y0 = FRONT_BOX[:2]
    crop = refs.crop(img, FRONT_BOX)
    m = refs.silhouette(crop, bg=BG, thresh=0.085, blur=1.0, open_px=1, close_px=2, fill_holes=300,
                        clip_below=int(FRONT_GROUND - y0) + 1, shadow_luma_drop=0.10)
    if corrected:
        m = _largest(m & ~_poly_mask(m.shape, FRONT_TRIANGLE_POLY, x0, y0))
    return crop, m


def front_view(corrected=True, img=None):
    crop, m = front_mask(img, corrected)
    x0, y0 = FRONT_BOX[:2]
    return refs.View(name="front" if corrected else "front_raw", image=crop, mask=m,
                     d=refs.VIEW_DIRS["front"], ppm=FRONT_PPM, ax=FRONT_AXIS_COL - x0, ay=FRONT_GROUND - y0)


def rear_mask(img=None):
    img = sheet() if img is None else img
    x0, y0 = REAR_BOX[:2]
    crop = refs.crop(img, REAR_BOX)
    m = refs.silhouette(crop, bg=BG, thresh=0.085, blur=1.0, open_px=1, close_px=2, fill_holes=300,
                        clip_below=int(REAR_GROUND - y0) + 1, shadow_luma_drop=0.10)
    return crop, m


def head_crop(img=None):
    img = sheet() if img is None else img
    x0, y0 = HEAD_BOX[:2]
    crop = refs.crop(img, HEAD_BOX)
    m = refs.silhouette(crop, bg=BG, thresh=0.07, blur=1.0, open_px=1, close_px=3, fill_holes=4000,
                        exclude=_shift(HEAD_EXCLUDE, x0, y0), shadow_luma_drop=0.06)
    return crop, m


# ---------------------------------------------------------------- key poses (art/05), 4 x 3 panels
KEYPOSE_PANELS = {
    "walk_contact_L": (0, 70, 382, 305),
    "walk_passing_1": (382, 70, 758, 305),
    "walk_contact_R": (758, 70, 1134, 305),
    "walk_passing_2": (1134, 70, 1536, 305),
    "turn_anticipation": (0, 325, 388, 620),
    "turn_planted": (388, 325, 742, 620),
    "bite_windup": (742, 325, 1112, 620),
    "bite_strike": (1112, 325, 1536, 620),
    "roar": (0, 640, 376, 960),
    "tail_coil": (376, 640, 712, 960),
    "tail_release": (712, 640, 1108, 960),
    "death_rest": (1108, 640, 1536, 960),
}


def keypose_panel(name, img=None):
    img = refs.load(KEYPOSES) if img is None else img
    return refs.crop(img, KEYPOSE_PANELS[name])


def keypose_mask(panel):
    bg = refs.border_color(panel)
    m = refs.silhouette(panel, bg=bg, thresh=0.10, blur=1.0, open_px=1, close_px=2, fill_holes=400,
                        shadow_luma_drop=0.12)
    return m


def side_px_to_world(u, row):
    """full-image side pixel -> (Y, Z) metres"""
    return (np.asarray(u, float) - SIDE_HIP_COL) / SIDE_PPM, (SIDE_GROUND - np.asarray(row, float)) / SIDE_PPM


def front_px_to_world(u, row):
    return (np.asarray(u, float) - FRONT_AXIS_COL) / FRONT_PPM, (FRONT_GROUND - np.asarray(row, float)) / FRONT_PPM
