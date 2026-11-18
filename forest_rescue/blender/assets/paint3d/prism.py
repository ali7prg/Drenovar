"""Solid painted blocks (bpy): a block region of the painting is split into its FRONT face and the visible TOP band
(elevated reference camera sees the tops); depth D = top band height / sin(elevation) (>= 0.7 x width when the
top is not visible). The front-face outline is extruded back by D (back face tapered), so the elevated-camera
projection of the solid covers the painted region: front face <- painting, top cap <- painted top band."""
import math

import bmesh
import bpy
import cv2
import numpy as np
from scipy import ndimage as ndi

import geom


def top_band(region, top_like, min_cols_frac=0.3, lo_frac=0.08, hi_frac=0.45):
    """Median height (px) of the top-face band (top_like pixels contiguous from the region's top, per column)."""
    cols = np.nonzero(region.any(0))[0]
    ts = []
    for x in cols:
        ys = np.nonzero(region[:, x])[0]
        y0 = ys.min()
        n = 0
        for y in range(y0, ys.max() + 1):
            if region[y, x] and top_like[y, x]:
                n += 1
            else:
                break
        ts.append(n)
    ts = np.array(ts)
    hpx = np.ptp(np.nonzero(region.any(1))[0]) + 1
    if (ts > 1).mean() < min_cols_frac:
        return None
    t = float(np.median(ts[ts > 1]))
    return float(np.clip(t, lo_frac * hpx, hi_frac * hpx))


def block_solid(view, region, top_like, ppm, elev_deg, y0=0.0, eps_px=1.6, taper=0.86, min_depth_k=0.7,
                max_depth_k=1.5, rng=None):
    """Returns (verts (N,3), faces list) of the solid block in Blender world space, or None."""
    rng = rng or np.random.default_rng(0)
    ys, xs = np.nonzero(region)
    if len(ys) < 60:
        return None
    w_px = np.ptp(xs) + 1
    t = top_band(region, top_like)
    if t is not None:
        D = t / math.sin(math.radians(elev_deg)) / ppm
        front = region.copy()
        for x in np.unique(xs):
            col = np.nonzero(region[:, x])[0]
            front[col.min():col.min() + int(round(t)), x] = False
    else:
        D = min_depth_k * w_px / ppm
        front = region
    D = float(np.clip(D, min_depth_k * w_px / ppm, max_depth_k * w_px / ppm))
    front = ndi.binary_opening(front, iterations=1)
    lab, n = ndi.label(front)
    if n == 0:
        return None
    sizes = ndi.sum(front, lab, np.arange(1, n + 1))
    front = lab == (int(np.argmax(sizes)) + 1)
    cnts, _ = cv2.findContours(front.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    poly = cv2.approxPolyDP(c, eps_px, True)[:, 0, :].astype(float)
    if len(poly) < 3:
        return None
    # pixel -> world on the front plane (world y = y0): camera ray through (u, v) intersected with y = y0
    P = geom.world_at_y(view, poly[:, 0], poly[:, 1], np.full(len(poly), y0))
    bm = bmesh.new()
    vs = [bm.verts.new(tuple(p)) for p in P]
    try:
        f = bm.faces.new(vs)
    except ValueError:
        bm.free()
        return None
    bmesh.ops.recalc_face_normals(bm, faces=[f])
    if f.normal.y > 0:          # front face must face the camera (-y)
        f.normal_flip()
    ret = bmesh.ops.extrude_face_region(bm, geom=[f])
    ext = [e for e in ret["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0.0, D, 0.0), verts=ext)
    # tapered, slightly irregular back face (natural fracture), bottom kept on its plane
    cen = np.mean([v.co for v in ext], axis=0)
    zmin = min(v.co.z for v in ext)
    for v in ext:
        k = taper * rng.uniform(0.95, 1.03)
        v.co.x = cen[0] + (v.co.x - cen[0]) * k
        v.co.z = max(zmin, cen[2] + (v.co.z - cen[2]) * k)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    V = np.array([v.co[:] for v in bm.verts])
    F = [[v.index for v in fc.verts] for fc in bm.faces]
    bm.free()
    return V, np.array(F), dict(depth=D, top_px=t, width_m=w_px / ppm)
