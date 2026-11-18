"""Reference views (art/02 forest kit) for silhouette comparison: crops, scale, masks.

Scale: grey 1.8 m human figures on the sheet measure 51-56 px in the top row (≈30 px/m) and
72-74 px in the bottom row (≈40.5 px/m).  Ground row = feet line; the painted ground patch
(grass/leaf litter disc and shadow) is clipped at `clip` (both in the reference and the render).
"""
import numpy as np
from scipy import ndimage as ndi

import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from frlib import refs  # noqa: E402

SHEET = "02_forest_modular_kit.png"
PPM_TOP = 54.0 / 1.8
PPM_BOTTOM = 73.0 / 1.8

# name: crop box (x0,y0,x1,y1) full-sheet px, ground row, clip row, human box, ppm, centre col (None=auto)
KIT = {
    "golden_oak": dict(box=(0, 0, 440, 445), ground=422, clip=412, human=(286, 362, 318, 430), ppm=PPM_TOP),
    "dark_pine": dict(box=(418, 0, 646, 445), ground=422, clip=412, human=(580, 362, 612, 430), ppm=PPM_TOP),
    "birch": dict(box=(620, 28, 886, 445), ground=422, clip=413, human=(811, 362, 843, 430), ppm=PPM_TOP),
    "hollow_oak": dict(box=(845, 0, 1272, 445), ground=424, clip=418, human=(1174, 362, 1206, 432), ppm=PPM_TOP),
    "willow": dict(box=(1190, 80, 1536, 445), ground=420, clip=410, human=(1381, 362, 1412, 430), ppm=PPM_TOP),
    "fallen_trunk": dict(box=(0, 520, 470, 740), ground=700, clip=668, human=(6, 588, 44, 676), ppm=PPM_BOTTOM),
    "moss_rock": dict(box=(470, 480, 892, 728), ground=712, clip=700, human=(472, 602, 508, 688), ppm=PPM_BOTTOM),
    "bramble": dict(box=(893, 492, 1228, 728), ground=712, clip=700, human=None, ppm=None),
    "reed_fern": dict(box=(1228, 478, 1532, 728), ground=712, clip=700, human=None, ppm=None),
}


def kit_view(name, ppm=None, centre_col=None, thresh=0.10, keep="largest", fill_holes=60, extra_excl=None):
    """refs.View for a kit element (front view: camera looks +Y, image right = +X, up = +Z).

    Pixel coords are crop-relative.  `ppm` overrides the sheet scale (bramble / reeds have no human)."""
    k = KIT[name]
    img = refs.load(SHEET)
    x0, y0, x1, y1 = k["box"]
    crop = refs.crop(img, k["box"])
    bg = refs.border_color(img)
    excl = []
    if k["human"]:
        hx0, hy0, hx1, hy1 = k["human"]
        excl.append((hx0 - x0, hy0 - y0, hx1 - x0, hy1 - y0))
    if extra_excl:
        excl += extra_excl
    m = refs.silhouette(crop, bg=bg, thresh=thresh, keep=keep, min_area=200, fill_holes=fill_holes,
                        exclude=excl, clip_below=k["clip"] - y0)
    ppm = ppm or k["ppm"]
    ground = k["ground"] - y0
    if centre_col is None:
        # trunk centre: median column of mask pixels in the 10 rows above the clip line
        rows = m[max(0, k["clip"] - y0 - 12):k["clip"] - y0 - 2]
        cols = np.nonzero(rows.any(axis=0))[0]
        centre_col = float(np.median(np.nonzero(rows)[1])) if len(cols) else crop.shape[1] / 2
    v = refs.View(name=name, image=crop, mask=m, d=refs.VIEW_DIRS["front"], ppm=ppm, ax=centre_col, ay=ground)
    v.clip_row = k["clip"] - y0
    return v


def closed(mask, r=4):
    return ndi.binary_closing(mask, structure=np.ones((2 * r + 1, 2 * r + 1)), iterations=1, border_value=0)


def iou(a, b):
    return float(np.logical_and(a, b).sum()) / max(1.0, float(np.logical_or(a, b).sum()))
