"""Fast numpy silhouette check of the SDF body against the reference masks (no Blender needed).

Usage (development):  python3 forest_rescue/blender/run_limited.py \
    forest_rescue/blender/assets/boss/maw_silhouette.py <out_dir> [voxel]
"""
import os
import sys

import numpy as np
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import maw_body as B  # noqa: E402
import maw_refs as R  # noqa: E402
from frlib import core  # noqa: E402


def project_mask(F, view, axis):
    occ = (F.d < 0).any(axis=axis).astype(np.float32)
    H, W = view.mask.shape
    vv, uu = np.mgrid[0:H, 0:W].astype(float)
    if axis == 0:   # side: image u -> +Y, v -> -Z
        a = view.anchor + 0
        Y = (uu - view.ax) / view.ppm
        Z = (view.ay - vv) / view.ppm
        i0 = (Y - F.lo[1]) / F.voxel
        i1 = (Z - F.lo[2]) / F.voxel
    else:           # front: image u -> +X
        X = (uu - view.ax) / view.ppm
        Z = (view.ay - vv) / view.ppm
        i0 = (X - F.lo[0]) / F.voxel
        i1 = (Z - F.lo[2]) / F.voxel
    s = ndi.map_coordinates(occ, [i0, i1], order=1, mode="constant", cval=0.0)
    return s > 0.5


def diff_image(view, rmask):
    ref = view.image
    out = np.repeat(ref.mean(axis=2, keepdims=True) * 0.5 + 0.35, 3, axis=2)
    both = view.mask & rmask
    out[both] = out[both] * 0.5 + np.array([0.15, 0.55, 0.15]) * 0.5
    out[view.mask & ~rmask] = (0.85, 0.15, 0.15)
    out[~view.mask & rmask] = (0.15, 0.3, 0.9)
    return out


def iou(a, b):
    return float((a & b).sum()) / max(float((a | b).sum()), 1.0)


def main(out_dir, voxel=0.03, hull=False):
    os.makedirs(out_dir, exist_ok=True)
    side = R.side_view(corrected=True)
    side_raw = R.side_view(corrected=False)
    front = R.front_view()
    F, add, sub = B.build_field(voxel=voxel, detail=True, hull_views=[side, front] if hull else None)
    res = {}
    for v, axis in ((side, 0), (side_raw, 0), (front, 1)):
        m = project_mask(F, v, axis)
        res[v.name] = iou(v.mask, m)
        core.save_rgba(os.path.join(out_dir, f"sil_{v.name}.png"),
                       np.concatenate([v.image, diff_image(v, m)], axis=1))
    print("IOU", res)
    np.save(os.path.join(out_dir, "field_d.npy"), F.d)
    np.save(os.path.join(out_dir, "field_meta.npy"), np.array([*F.lo, F.voxel]))
    return res


if __name__ == "__main__":
    out = sys.argv[1]
    vox = float(sys.argv[2]) if len(sys.argv) > 2 else 0.03
    hull = len(sys.argv) > 3 and sys.argv[3] == "hull"
    main(out, vox, hull)
