"""QA helpers for props: reference crops/masks, matched cameras, iteration-numbered comparisons."""
import json
import math
import os
import sys

import bpy
import numpy as np
from scipy import ndimage as ndi

import propkit as pk
from frlib import core, paths, refs, render


def iteration():
    for i, a in enumerate(sys.argv):
        if a == "--iter" and i + 1 < len(sys.argv):
            return int(sys.argv[i + 1])
    return int(os.environ.get("FR_ITER", "1"))


def flag(name):
    return name in sys.argv


def out(asset_id, name):
    return paths.compare(asset_id, name)


def flood_mask(img, tol=3, step=4, blur=0.8, exclude=None, clip_below=None, keep="largest", fill=True, min_area=60,
               bg=None, seed_tol=0.07):
    """Foreground = everything not reachable from the crop border through smooth background
    (floating-range flood fill follows soft painted shadows but stops at object edges)."""
    import cv2
    im = (np.clip(ndi.gaussian_filter(img, (blur, blur, 0)), 0, 1) * 255).astype(np.uint8).copy()
    H, W = im.shape[:2]
    mask = np.zeros((H + 2, W + 2), np.uint8)
    flags = 4 | cv2.FLOODFILL_MASK_ONLY | (255 << 8)
    pts = [(x, 0) for x in range(0, W, step)] + [(x, H - 1) for x in range(0, W, step)] + \
          [(0, y) for y in range(0, H, step)] + [(W - 1, y) for y in range(0, H, step)]
    imf = ndi.gaussian_filter(img, (blur, blur, 0))
    if bg is None:
        border = np.concatenate([imf[0], imf[-1], imf[:, 0], imf[:, -1]])
        bg = np.median(border, axis=0)
    bg = np.asarray(bg, float)
    for x, y in pts:
        if np.linalg.norm(imf[y, x] - bg) > seed_tol:     # never seed on an object touching the crop edge
            continue
        if mask[y + 1, x + 1] == 0:
            cv2.floodFill(im, mask, (x, y), (0, 0, 0), (tol,) * 3, (tol,) * 3, flags)
    fg = mask[1:-1, 1:-1] == 0
    if exclude:
        for x0, y0, x1, y1 in exclude:
            fg[y0:y1, x0:x1] = False
    if clip_below is not None:
        fg[clip_below:] = False
    fg = ndi.binary_opening(fg, iterations=1)
    lab, n = ndi.label(fg)
    if n:
        sz = ndi.sum(fg, lab, range(1, n + 1))
        if keep == "largest":
            fg = lab == (int(np.argmax(sz)) + 1)
        else:
            fg = np.isin(lab, np.nonzero(sz >= min_area)[0] + 1)
    return ndi.binary_fill_holes(fg) if fill else fg


BG = {"10_artifact_mechanisms.png": (148 / 255, 131 / 255, 120 / 255)}


def crop_and_mask(image, box, method="flood", tol=3, exclude=None, clip_below=None, keep="largest", fill=True,
                  **kw):
    img = pk.ref_crop(image, box)
    if method == "flood":
        m = flood_mask(img, tol=tol, exclude=exclude, clip_below=clip_below, keep=keep, fill=fill, bg=BG.get(image))
    else:
        m = refs.silhouette(img, exclude=exclude, clip_below=clip_below, keep=keep, **kw)
    return img, m


def ortho_view_compare(asset_id, name, objs, img, mask, direction, real_width=None, real_height=None,
                       title="", up=None, extra=""):
    """Orthographic compare: scale from a real dimension of the subject (fit_view)."""
    view = refs.fit_view(name, img, mask, direction, real_width=real_width, real_height=real_height)
    # centre the model bbox on the mask bbox (both horizontally and vertically)
    tris = pk.world_triangles(objs)
    P = tris.reshape(-1, 3)
    u, v, _ = view.project(P)
    x0, y0, x1, y1 = refs.bbox(mask)
    du = (x0 + x1) / 2 - (u.min() + u.max()) / 2
    dv = (y0 + y1) / 2 - (v.min() + v.max()) / 2
    view.ax += du
    view.ay += dv
    cam = render.camera_for_view(view)
    rgba = pk.render_rgba(os.path.join(paths.ensure(paths.QA_COMPARE, asset_id), "_tmp.png"))
    met = pk.compare_panels(img, rgba, mask, out(asset_id, name + ".png"), title or name, extra_text=extra)
    return met


def persp_fit_compare(asset_id, name, objs, img, mask, x0, fixed=(2,), title="", extra="", fill=True, iters=2,
                      cam_store=None):
    H, W = mask.shape
    tris = pk.world_triangles(objs)
    key = f"{asset_id}:{name}"
    if cam_store is not None and key in cam_store and not flag("--refit"):
        x = np.array(cam_store[key])
        x, sc = pk.fit_camera(tris, mask, x, fixed=fixed, fill=fill, iters=1)
    else:
        x, sc = pk.fit_camera(tris, mask, x0, fixed=fixed, fill=fill, iters=iters)
    if cam_store is not None:
        cam_store[key] = [float(a) for a in x]
    cam = pk.cam_from_params(x, W, H)
    pk.blender_camera(cam)
    rgba = pk.render_rgba(os.path.join(paths.ensure(paths.QA_COMPARE, asset_id), "_tmp.png"))
    met = pk.compare_panels(img, rgba, mask, out(asset_id, name + ".png"), title or name, extra_text=extra,
                            mask_fill=fill)
    met["camera_params"] = [round(float(a), 5) for a in x]
    core.write_json(out(asset_id, name + ".json"), met)
    return met, cam


def load_cams(path):
    if os.path.exists(path):
        return json.load(open(path))
    return {}


def save_cams(path, cams):
    core.write_json(path, cams)
