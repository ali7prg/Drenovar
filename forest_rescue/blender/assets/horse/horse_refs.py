"""Reference views of the guide horse «Искра» (lf_horse_origin).

Pure numpy (no bpy): crops of `delivery/art/horse_guide_turnaround_motion.png`, cleaned
silhouette masks (ground shadow removed at the hoof line) and orthographic `refs.View`s that
share ONE world frame:

* Z = 0 at the painted hoof ground line (row 437.5 of every crop), common scale PPM = 206 px/m
  (pilot: ear-tip height 2.05 m).
* Y = 0 at the barrel middle of the left profile, X = 0 at the body symmetry axis of the front
  view.  The right/rear views are registered to left/front by the best mirrored overlap.
"""
import os
import sys

import numpy as np
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(os.path.dirname(HERE))
if BLENDER_DIR not in sys.path:
    sys.path.insert(0, BLENDER_DIR)

from frlib import refs  # noqa: E402

SHEET = "horse_guide_turnaround_motion.png"
CROPS = {
    "left": (20, 105, 560, 545),
    "front": (555, 105, 735, 545),
    "rear": (765, 105, 940, 545),
    "right": (965, 105, 1515, 545),
}
# pose drawings (bottom row) for the posed 3/4 comparisons
POSE_CROPS = {
    "walk": (20, 640, 400, 920),
    "trot": (390, 630, 770, 920),
    "look_back": (840, 620, 1130, 930),
}
DETAIL_CROPS = {"star": (1170, 660, 1335, 840), "halter": (1345, 660, 1515, 840),
                "swatches": (1180, 915, 1515, 970)}

PPM = 206.0
GROUND_ROW = 437.5
# column of world Y=0 (left), of X=0 (front); right/rear derived from mirrored registration
ANCHOR_COL = {"left": 329.5, "right": 208.5, "front": 93.0, "rear": 94.0}


def _clean_mask(img, band=418, hoof_thresh=0.40):
    """Silhouette (pilot settings) with the painted ground shadow removed below `band`."""
    bg = refs.border_color(img)
    m = refs.silhouette(img, thresh=0.13, blur=1.0)
    d = np.sqrt(((ndi.gaussian_filter(img, (0.8, 0.8, 0)) - bg) ** 2).sum(2))
    hb = ndi.binary_fill_holes(ndi.binary_closing(d > hoof_thresh, iterations=2))
    out = m.copy()
    out[band:] = hb[band:] & m[band:]
    # hooves may flare a little wider than the pastern above, but no wider: drop shadow strips
    row = out[band - 4]
    allowed = ndi.binary_dilation(row, iterations=7)
    out[band + 6:] &= allowed[None, :]
    out = ndi.binary_opening(out, iterations=1)
    lab, n = ndi.label(out)
    sizes = ndi.sum(out, lab, range(1, n + 1))
    out = lab == (int(np.argmax(sizes)) + 1)
    out[int(np.ceil(GROUND_ROW)) + 1:] = False
    return out


def load_views(weights=None):
    """Return {name: refs.View} for left/front/rear/right in the shared world frame."""
    sheet = refs.load(SHEET)
    views = {}
    for name, box in CROPS.items():
        img = refs.crop(sheet, box)
        mask = _clean_mask(img)
        v = refs.View(name=name, image=img, mask=mask, d=refs.VIEW_DIRS[name], ppm=PPM,
                      ax=ANCHOR_COL[name], ay=GROUND_ROW)
        if weights and name in weights:
            v.weight = weights[name]
        views[name] = v
    return views


def pose_images():
    sheet = refs.load(SHEET)
    return {k: refs.crop(sheet, b) for k, b in POSE_CROPS.items()}


def detail_images():
    sheet = refs.load(SHEET)
    return {k: refs.crop(sheet, b) for k, b in DETAIL_CROPS.items()}


def render_field_mask(view, sil2d, lo2, voxel):
    """Map a 2-D silhouette grid (axis0 = view-right coordinate, axis1 = up) into crop pixels.

    sil2d[i, j] is True if the model covers right-coordinate lo2[0]+i*voxel, up lo2[1]+j*voxel.
    """
    H, W = view.mask.shape
    u = np.arange(W) + 0.5 - 0.5
    v = np.arange(H) + 0.5 - 0.5
    rr = (u - view.ax) / view.ppm          # metres along view.right (relative to anchor)
    uu = (view.ay - v) / view.ppm          # metres along view.up
    i = np.round((rr - lo2[0]) / voxel).astype(int)
    j = np.round((uu - lo2[1]) / voxel).astype(int)
    okx = (i >= 0) & (i < sil2d.shape[0])
    oky = (j >= 0) & (j < sil2d.shape[1])
    out = np.zeros((H, W), bool)
    I, J = np.meshgrid(np.clip(i, 0, sil2d.shape[0] - 1), np.clip(j, 0, sil2d.shape[1] - 1))
    out[:] = sil2d[I, J]
    out &= okx[None, :] & oky[:, None]
    return out
