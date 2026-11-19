"""Fast numpy silhouette check of the v2 SDF body against the side / front (/ rear) reference masks.

    /opt/tools/blender-venv/bin/python mv2_fit.py <out_dir> [voxel] [hull]
Writes sil_<view>.png ([reference | diff]) and prints IoU per view.
"""
import json
import os
import sys

import numpy as np
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mv2_body as B  # noqa: E402
import mv2_refs as R  # noqa: E402
from frlib import core  # noqa: E402


def ortho_mask(F, view, axis):
    occ = (F.d < 0).any(axis=axis).astype(np.float32)
    H, W = view.mask.shape
    vv, uu = np.mgrid[0:H, 0:W].astype(float)
    a = (uu - view.ax) / view.ppm
    Z = (view.ay - vv) / view.ppm
    if axis == 0:   # side: image u -> world -Y? left view: right vector = cross(d, up) = (0,-1,0)? handle sign
        Yw = view.anchor[1] + a * view.right[1]
        i0 = (Yw - F.lo[1]) / F.voxel
    else:
        Xw = view.anchor[0] + a * view.right[0]
        i0 = (Xw - F.lo[0]) / F.voxel
    i1 = (Z - F.lo[2]) / F.voxel
    s = ndi.map_coordinates(occ, [i0, i1], order=1, mode="constant", cval=0.0)
    return s > 0.5


def persp_mask(F, cam, shape, stride=1):
    """Silhouette of the occupied voxels through a perspective camera (point splat + closing)."""
    occ = F.d < 0
    idx = np.argwhere(occ)
    P = F.lo + idx * F.voxel
    u, v, _ = cam.project(P)
    H, W = shape
    m = np.zeros((H, W), bool)
    ui, vi = np.round(u).astype(int), np.round(v).astype(int)
    ok = (ui >= 0) & (ui < W) & (vi >= 0) & (vi < H)
    m[vi[ok], ui[ok]] = True
    r = max(1, int(np.ceil(cam.px_per_m_at(P.mean(0)) * F.voxel * 0.75)))
    m = ndi.binary_dilation(m, iterations=r)
    m = ndi.binary_erosion(m, iterations=max(0, r - 1))
    return ndi.binary_fill_holes(m)


def diff_image(ref, refmask, rmask):
    out = np.repeat(ref.mean(axis=2, keepdims=True) * 0.5 + 0.35, 3, axis=2)
    both = refmask & rmask
    out[both] = out[both] * 0.5 + np.array([0.15, 0.55, 0.15]) * 0.5
    out[refmask & ~rmask] = (0.85, 0.15, 0.15)
    out[~refmask & rmask] = (0.15, 0.3, 0.9)
    return out


def iou(a, b):
    return float((a & b).sum()) / max(float((a | b).sum()), 1.0)


def run(out_dir, voxel=0.03, hull=False):
    os.makedirs(out_dir, exist_ok=True)
    side = R.side_view(corrected=True, colour=False)
    front = R.front_view()
    F, add, sub = B.build_field(voxel=voxel, hull_views=[side, front] if hull else None)
    res = {}
    for v, axis in ((side, 0), (front, 1)):
        m = ortho_mask(F, v, axis)
        res[v.name] = round(iou(v.mask, m), 4)
        core.save_rgba(os.path.join(out_dir, f"sil_{v.name}.png"),
                       np.concatenate([v.image, diff_image(v.image, v.mask, m)], axis=1))
    print("IOU", json.dumps(res))
    np.savez_compressed(os.path.join(out_dir, "field.npz"), d=F.d, lo=F.lo, voxel=F.voxel)
    return res, F


if __name__ == "__main__":
    out = sys.argv[1]
    vox = float(sys.argv[2]) if len(sys.argv) > 2 else 0.03
    run(out, vox, len(sys.argv) > 3 and sys.argv[3] == "hull")
