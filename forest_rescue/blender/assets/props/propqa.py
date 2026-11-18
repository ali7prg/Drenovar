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


def crop_and_mask(image, box, thresh=0.1, exclude=None, clip_below=None, shadow=None, keep="largest",
                  fill_holes=400, sat_weight=1.5, bg=None, open_px=1, close_px=2, blur=1.0):
    img = pk.ref_crop(image, box)
    m = refs.silhouette(img, bg=bg, thresh=thresh, exclude=exclude, clip_below=clip_below,
                        shadow_luma_drop=shadow, keep=keep, fill_holes=fill_holes, sat_weight=sat_weight,
                        open_px=open_px, close_px=close_px, blur=blur)
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
