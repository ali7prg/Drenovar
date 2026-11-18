"""Guardian reference sheets: panel crops, silhouette masks and calibrated orthographic views.

Sheets: art/09_tenerys_guardian_direction.png (Tenerys), art/11_other_guardians_direction.png
(Velkor / Kamneklyk / Dragor rows).  Panel boxes were measured on the sheets (pixel grid
overlays); every species spec lists its own boxes, ground rows and scale.
"""
import os

import numpy as np
from scipy import ndimage as ndi

from frlib import refs, paths, core

SHEETS = {
    "09": "09_tenerys_guardian_direction.png",
    "11": "11_other_guardians_direction.png",
}
_cache = {}


def sheet(key):
    if key not in _cache:
        _cache[key] = refs.load(SHEETS[key])
    return _cache[key]


class Panel:
    """A crop of a reference sheet with its silhouette mask and pixel<->world mapping."""

    def __init__(self, name, sheet_key, box, direction, ppm, ground_row, center_col,
                 thresh=0.10, exclude=None, clip_below=None, keep="largest", fill_holes=600,
                 open_px=1, close_px=2, blur=1.2, sat_weight=1.5, flip=False, weight=1.0,
                 anchor=(0.0, 0.0, 0.0), extra_mask_fn=None, bg=None):
        self.name = name
        self.sheet_key = sheet_key
        self.box = box
        x0, y0, x1, y1 = box
        img = refs.crop(sheet(sheet_key), box)
        if flip:
            img = img[:, ::-1].copy()
        self.image = img
        ex = []
        for (a, b, c, d) in (exclude or []):     # sheet coords -> crop coords
            if flip:
                ex.append((x1 - c, b - y0, x1 - a, d - y0))
            else:
                ex.append((a - x0, b - y0, c - x0, d - y0))
        cb = None if clip_below is None else clip_below - y0
        m = refs.silhouette(img, bg=bg, thresh=thresh, blur=blur, open_px=open_px, close_px=close_px,
                            fill_holes=fill_holes, keep=keep, exclude=ex, clip_below=cb,
                            sat_weight=sat_weight)
        if extra_mask_fn is not None:
            m = extra_mask_fn(m, img)
        self.mask = m
        cc = (x1 - center_col) if flip else (center_col - x0)
        self.view = refs.View(name=name, image=img, mask=m, d=refs.VIEW_DIRS[direction] if isinstance(direction, str)
                              else np.asarray(direction, float), ppm=ppm, ax=cc, ay=ground_row - y0,
                              anchor=np.asarray(anchor, float), weight=weight)
        self.flip = flip

    # sheet pixel -> world (on the view plane through the anchor)
    def world(self, sx, sy, depth=0.0):
        x0, y0, x1, y1 = self.box
        u = (x1 - sx) if self.flip else (sx - x0)
        return self.view.world_of_pixel(u, sy - y0, depth)

    def preview(self, path):
        refs.save_mask_preview(path, self.view)


def side_world(panel, sx, sy, x=0.0):
    """World point of a sheet pixel in a side panel (lateral coordinate X given in metres)."""
    p = panel.world(sx, sy)
    p[0] = x
    return p


def mask_rows(mask):
    """Top/bottom row of every column (nan where empty)."""
    H, W = mask.shape
    top = np.full(W, np.nan)
    bot = np.full(W, np.nan)
    cols = np.nonzero(mask.any(axis=0))[0]
    for c in cols:
        r = np.nonzero(mask[:, c])[0]
        top[c] = r.min()
        bot[c] = r.max()
    return top, bot


def save_panels_preview(panels, out_png):
    from frlib import render
    render.side_by_side([np.dstack([p.view.image * (0.4 + 0.6 * p.mask[..., None])]) for p in panels],
                        [p.name for p in panels], out_png, height=380)


def morph_view(view, px):
    """Copy of a refs.View with the mask dilated (px>0) or eroded (px<0)."""
    import copy
    v = copy.copy(view)
    if px > 0:
        v.mask = ndi.binary_dilation(view.mask, iterations=int(px))
    elif px < 0:
        v.mask = ndi.binary_erosion(view.mask, iterations=int(-px))
    return v
