"""Generic clothed-body construction from a character spec (landmarks + shape tables).

A spec module provides:
  L      landmarks (metres, drawing pose)                 -> humans_skel.joints_from_landmarks
  FACE   face parameters                                  -> humans_sdf.head_parts
  body_parts(J, L) -> list of tagged Prims (torso/limb/boot/etc. lofts), on top of the
                      generic neck/head/hands provided here.
The body field is the smooth union of all parts, minus the subtractive face parts, smoothly
intersected with the silhouette hull of the registered front+back reference masks.
"""
import numpy as np

from frlib import sdf as fsdf

import humans_sdf as H
import humans_skel as SK


def generic_parts(J, L, fingers, face=None, neck_r=(0.060, 0.052), neck_cls="skin", hands=True):
    s = L["crown"] / 1.75
    P = []
    # neck: from inside the chest to under the skull
    nb = J["Neck"]
    hd = J["Head"]
    P.append(H.limb(nb + np.array([0, 0.0, -0.05 * s]), hd + np.array([0, 0.0, 0.02 * s]),
                    [(0.0, neck_r[0] * s, neck_r[0] * s * 0.95), (0.55, neck_r[1] * s, neck_r[1] * s * 0.98),
                     (1.0, neck_r[1] * s * 0.98, neck_r[1] * s * 1.02)],
                    cls=neck_cls, bone="Neck", k=0.02, name="neck", offsets=[(0, 0.0), (0, 0.004 * s), (0, 0.010 * s)]))
    hp, lm = H.head_parts(J, L, face)
    P += hp
    Sub = []
    if hands:
        for S_, side in SK.SIDES:
            P += H.hand_parts(J, S_, side, fingers[S_], L.get("hand_scale", 1.0) * s, female=L.get("female", False))
    return P, Sub, lm


def field_bounds(L, pad=0.03):
    s = L["crown"] / 1.75
    lo = np.array([-0.52 * s, -0.30 * s, -0.004])
    hi = np.array([0.52 * s, 0.30 * s, L.get("top", L["crown"] + 0.05)])
    return lo, hi


def build_field(parts, subs, lo, hi, voxel, hull=None, hull_k=0.012, views=None, smooth=0.0, hull_dilate=1.0):
    """Ordered CSG of the parts; parts flagged nohull (hands, boots) are added after the smooth
    intersection with the silhouette hull so the hull never slices them flat."""
    F = fsdf.Field(lo, hi, voxel)
    late = []
    for p in parts:
        if not getattr(p, "geom", True):
            continue
        if views is not None and getattr(p, "nohull", False):
            late.append(p)
            continue
        F.apply(p, op=getattr(p, "op", "union"), k=p.k)
    for p in subs:
        F.apply(p, op="subtract", k=p.k)
    if views is not None:
        hv = H.hull2d(F, views, dilate_px=hull_dilate)
        F.intersect(hv, k=hull_k)
    for p in late:
        F.apply(p, op=getattr(p, "op", "union"), k=p.k)
    F.smooth(smooth or 0.65)
    return F
