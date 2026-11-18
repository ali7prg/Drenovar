"""Body field -> hull-locked SDF -> meshes (pure numpy part + optional bpy helpers)."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import horse_refs as HR  # noqa: E402
import horse_body as HB  # noqa: E402
import horse_fit as HF  # noqa: E402
from frlib import sdf  # noqa: E402


def body_field(voxel=0.007, hull_mode="all", hull_k=0.025, smooth=0.010, views=None, J=None):
    """Anatomical parts, smoothly intersected with the 4-view visual hull, ears + carves after."""
    views = views or HR.load_views()
    J = J or HB.skeleton()
    F = HF.build_field(voxel, HB.body_parts(J))
    if hull_mode and hull_mode != "none":
        F.intersect(hull_sdf_smooth(F, HF.hull_views(views, hull_mode)), k=hull_k)
    for p in HB.ear_parts(J):
        F.apply(p)
    for c in HB.carve_parts(J):
        F.apply(c, op="subtract")
    if smooth:
        F.smooth(smooth / voxel)      # smooth given in metres
    return F


def view_sdf2d(view, blur_px=2.0, smooth_px=3.0, close_px=4):
    """Signed 2-D distance (metres, negative inside) of a view mask, anti-aliased.

    A small closing removes hair-strand jaggedness (mane/tail/feather edges) first.
    """
    from scipy import ndimage as ndi
    m = view.mask
    if close_px:
        m = ndi.binary_closing(np.pad(m, close_px + 2), iterations=close_px)[close_px + 2:-close_px - 2,
                                                                               close_px + 2:-close_px - 2]
    m = ndi.gaussian_filter(m.astype(np.float32), blur_px) > 0.5
    d = (ndi.distance_transform_edt(~m) - ndi.distance_transform_edt(m)).astype(np.float32)
    if smooth_px:
        d = ndi.gaussian_filter(d, smooth_px)
    return d / view.ppm


def hull_sdf_smooth(F, views, dilate_m=0.004, front_zmax=1.47):
    """Visual-hull SDF as max over views of the projected 2-D mask SDF (no voxel terraces).

    Side views depend only on (Y, Z), front/rear only on (X, Z): each is sampled on its 2-D
    grid and broadcast over the third axis.
    """
    from scipy import ndimage as ndi
    xs, ys, zs = F.axes
    out = np.full(tuple(F.n), -10.0, np.float32)
    for v in views:
        d2 = view_sdf2d(v) - dilate_m
        if abs(v.d[0]) > 0.5:      # side view: right axis = +/-Y
            A, Zg = np.meshgrid(ys, zs, indexing="ij")
            P = np.stack([np.zeros_like(A), A, Zg], -1).reshape(-1, 3)
            u, vv, _ = v.project(P)
            s = ndi.map_coordinates(d2, [vv, u], order=1, mode="nearest").reshape(A.shape)
            out = np.maximum(out, s[None, :, :])
        else:                      # front/rear: right axis = +/-X
            A, Zg = np.meshgrid(xs, zs, indexing="ij")
            P = np.stack([A, np.zeros_like(A), Zg], -1).reshape(-1, 3)
            u, vv, _ = v.project(P)
            s = ndi.map_coordinates(d2, [vv, u], order=1, mode="nearest").reshape(A.shape)
            # neck/head region seen from the front is mane + head: never trim the neck by it
            fade = np.clip((front_zmax - Zg) / 0.06, 0.0, 1.0)
            s = np.where(fade > 0, s * fade + (fade - 1.0) * 0.5, -10.0)
            out = np.maximum(out, s[:, None, :])
    return out
