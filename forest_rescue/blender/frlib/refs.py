"""Reference sheets: crops, background removal, silhouette masks, orthographic view mapping.

Pixel convention: arrays are (H, W, C) float in [0,1], row 0 = top.
World convention (Blender): Z up, metres, character forward = -Y.
"""
from dataclasses import dataclass, field

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

from . import paths

# Canonical view directions (camera looks along `d`; image-up is world +Z unless noted)
VIEW_DIRS = {
    "left": np.array([-1.0, 0.0, 0.0]),    # camera at +X: subject's LEFT side, head to image-left
    "right": np.array([1.0, 0.0, 0.0]),    # camera at -X: subject's RIGHT side, head to image-right
    "front": np.array([0.0, 1.0, 0.0]),    # camera at -Y looking +Y: subject faces the camera
    "rear": np.array([0.0, -1.0, 0.0]),    # camera at +Y looking -Y
    "top": np.array([0.0, 0.0, -1.0]),     # camera above; image-up = world -Y (forward)
}


def load(name_or_path):
    path = name_or_path if "/" in name_or_path else paths.art(name_or_path)
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float64) / 255.0


def crop(img, box):
    x0, y0, x1, y1 = box
    return img[y0:y1, x0:x1].copy()


def border_color(img, width=3):
    b = np.concatenate([img[:width].reshape(-1, 3), img[-width:].reshape(-1, 3),
                        img[:, :width].reshape(-1, 3), img[:, -width:].reshape(-1, 3)])
    return np.median(b, axis=0)


def silhouette(img, bg=None, thresh=0.10, blur=1.2, open_px=1, close_px=2, fill_holes=400,
               keep="largest", min_area=150, exclude=None, sat_weight=1.5, clip_below=None,
               shadow_luma_drop=None):
    """Foreground mask of a painted subject on a near-uniform background.

    thresh: colour distance (0..1.7) from the background colour.
    sat_weight: extra weight on chroma difference (helps against grey ground shadows).
    exclude: list of (x0,y0,x1,y1) boxes forced to background (labels, arrows, callouts).
    clip_below: row index below which everything is background (ground line).
    shadow_luma_drop: if set, pixels darker than bg by < this and low chroma count as shadow.
    """
    if bg is None:
        bg = border_color(img)
    im = ndi.gaussian_filter(img, sigma=(blur, blur, 0)) if blur else img
    diff = im - bg[None, None, :]
    luma = diff @ np.array([0.299, 0.587, 0.114])
    chroma = diff - luma[..., None]
    dist = np.sqrt(luma ** 2 + sat_weight * (chroma ** 2).sum(axis=2))
    m = dist > thresh
    if shadow_luma_drop is not None:
        shadow = (luma < 0) & (luma > -shadow_luma_drop) & ((chroma ** 2).sum(axis=2) < (0.6 * thresh) ** 2)
        m &= ~shadow
    if exclude:
        for x0, y0, x1, y1 in exclude:
            m[y0:y1, x0:x1] = False
    if clip_below is not None:
        m[clip_below:] = False
    if open_px:
        m = ndi.binary_opening(m, iterations=open_px)
    if close_px:
        m = ndi.binary_closing(m, iterations=close_px)
    if fill_holes is True:
        m = ndi.binary_fill_holes(m)
    elif fill_holes:  # int: fill only holes up to this many pixels (keeps gaps between legs)
        holes = ndi.binary_fill_holes(m) & ~m
        hl, hn = ndi.label(holes)
        if hn:
            hs = ndi.sum(holes, hl, index=np.arange(1, hn + 1))
            m = m | np.isin(hl, np.nonzero(hs <= fill_holes)[0] + 1)
    lab, n = ndi.label(m)
    if n:
        sizes = ndi.sum(m, lab, index=np.arange(1, n + 1))
        if keep == "largest":
            m = lab == (int(np.argmax(sizes)) + 1)
        else:
            m = np.isin(lab, np.nonzero(sizes >= min_area)[0] + 1)
    return m


def bbox(mask):
    ys, xs = np.nonzero(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


@dataclass
class View:
    """Orthographic mapping between world space and a reference crop.

    u = ax + dot(P - anchor, right) * ppm ; v = ay - dot(P - anchor, up) * ppm
    """
    name: str
    image: np.ndarray            # crop (H,W,3)
    mask: np.ndarray             # bool (H,W)
    d: np.ndarray                # view direction (camera looks along d)
    ppm: float                   # pixels per metre
    ax: float                    # pixel x of anchor
    ay: float                    # pixel y of anchor
    anchor: np.ndarray = field(default_factory=lambda: np.zeros(3))
    up: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 1.0]))
    weight: float = 1.0

    def __post_init__(self):
        self.d = np.asarray(self.d, float)
        self.d /= np.linalg.norm(self.d)
        if abs(np.dot(self.d, self.up)) > 0.99:
            self.up = np.array([0.0, -1.0, 0.0])  # top view: image up = forward (-Y)
        r = np.cross(self.d, self.up)
        self.right = r / np.linalg.norm(r)
        self.up = np.cross(self.right, self.d)
        self.up /= np.linalg.norm(self.up)

    @property
    def size(self):
        return self.image.shape[1], self.image.shape[0]

    def project(self, P):
        P = np.asarray(P, float) - self.anchor
        u = self.ax + (P @ self.right) * self.ppm
        v = self.ay - (P @ self.up) * self.ppm
        depth = P @ self.d
        return u, v, depth

    def world_of_pixel(self, u, v, depth=0.0):
        return (self.anchor + ((u - self.ax) / self.ppm) * self.right
                + ((self.ay - v) / self.ppm) * self.up + depth * self.d)


def fit_view(name, image, mask, direction, real_height=None, real_width=None, anchor_world=None,
             ground_row=None, center_col=None, ppm=None):
    """Create a View whose scale comes from a known real dimension of the subject.

    Anchor = world point `anchor_world` (default origin) placed at (center_col, ground_row)
    which default to the mask bbox horizontal centre and bottom row.
    """
    x0, y0, x1, y1 = bbox(mask)
    if ppm is None:
        if real_height is not None:
            ppm = (y1 - y0) / real_height
        elif real_width is not None:
            ppm = (x1 - x0) / real_width
        else:
            raise ValueError("need real_height, real_width or ppm")
    ax = (x0 + x1) / 2.0 if center_col is None else center_col
    ay = float(y1) if ground_row is None else ground_row
    return View(name=name, image=image, mask=mask, d=VIEW_DIRS[direction] if isinstance(direction, str)
                else direction, ppm=ppm, ax=ax, ay=ay,
                anchor=np.zeros(3) if anchor_world is None else np.asarray(anchor_world, float))


def mask_profile(mask, axis=0):
    """Per-column (axis=0) or per-row (axis=1) extents: returns (index, lo, hi) arrays of the mask."""
    if axis == 0:
        cols = np.nonzero(mask.any(axis=0))[0]
        lo = np.array([np.nonzero(mask[:, c])[0].min() for c in cols])
        hi = np.array([np.nonzero(mask[:, c])[0].max() for c in cols])
        return cols, lo, hi
    rows = np.nonzero(mask.any(axis=1))[0]
    lo = np.array([np.nonzero(mask[r])[0].min() for r in rows])
    hi = np.array([np.nonzero(mask[r])[0].max() for r in rows])
    return rows, lo, hi


def save_mask_preview(path, view):
    from .core import save_rgba
    img = view.image.copy()
    img[~view.mask] = img[~view.mask] * 0.35 + np.array([0.0, 0.0, 0.6]) * 0.65
    save_rgba(path, img)
