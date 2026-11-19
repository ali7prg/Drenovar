"""Texture-space mask of the LOD0 atlas texels the painting actually shows (props v2 cages).

For every painting view of the asset (solved cameras, view pose), each atlas texel's 3D point is
projected into the painting; the texel is "seen" when it is inside the frame, faces the camera
(n . to_camera > 0.2) and is the nearest surface there (z-buffer of the posed LOD0 triangles).
Texture-only fixes (tools/fix_cage_top_textures.py) leave seen texels untouched so the painting
comparison cannot get worse; occluded / unseen fill is what they replace.

    python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/props/v2/cage_seen_mask.py cage_iron
"""
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pv2  # noqa: E402

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from frlib import core  # noqa: E402
import bl  # noqa: E402
import build_asset  # noqa: E402

OUT = os.path.join(pv2.TEXM, "pre_top_fix")


def main(modname):
    M = importlib.import_module(modname)
    aid = M.ID
    core.reset()
    views = M.views()
    params, _ = pv2.solve_views(views, M.points, M.PARAMS, M.FREE, prior_sigma=getattr(M, "PRIOR", 0.25))
    params["_cams"] = {v.name: v.cam for v in views}
    A = pv2.Asset(aid, M.ATLAS)
    for lod in range(3):
        M.build(A, params, lod)
    blank = bl.image_from_array(f"{aid}_c", np.full((8, 8, 3), 0.5))
    mats = {lod: build_asset.make_mats(aid, lod, blank, None, getattr(M, "GLOW", None)) for lod in range(3)}
    B = pv2.realize(A, mats)
    for lod in range(3):
        objs = [o for (l_, nm), o in B.objs.items() if l_ == lod]
        fixed = [B.finfo[(l_, nm)]["fixed"] for (l_, nm), o in B.objs.items() if l_ == lod]
        bl.atlas_uv(objs, fixed)
    D = pv2.gather(A, B, 0)
    size = M.ATLAS
    seen = np.zeros((size, size), bool)
    for v in views:
        Vt, vis, _ = pv2.posed(A, D, pv2.rpose(v))
        W, H = v.size
        zb = pv2.zbuf_tris(v.cam, W, H, Vt[vis])
        n = np.cross(Vt[:, 1] - Vt[:, 0], Vt[:, 2] - Vt[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        count = 0
        for t in np.nonzero(vis)[0]:
            uv = D["UV"][t]                                  # (3, 2) Blender UV, v up
            p = np.stack([uv[:, 0] * size, (1.0 - uv[:, 1]) * size], 1)
            x0, y0 = np.maximum(np.floor(p.min(0)).astype(int), 0)
            x1, y1 = np.minimum(np.ceil(p.max(0)).astype(int), size - 1)
            if x1 < x0 or y1 < y0:
                continue
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            (ax, ay), (bx, by), (cx, cy) = p
            det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(det) < 1e-12:
                continue
            w0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / det
            w1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / det
            w2 = 1.0 - w0 - w1
            inside = (w0 >= -0.05) & (w1 >= -0.05) & (w2 >= -0.05)
            if not inside.any():
                continue
            P = w0[inside, None] * Vt[t, 0] + w1[inside, None] * Vt[t, 1] + w2[inside, None] * Vt[t, 2]
            to_cam = v.cam.centre - P
            facing = (to_cam @ n[t]) / np.maximum(np.linalg.norm(to_cam, axis=1), 1e-9)
            u_, v_, dep = v.cam.project(P)
            ui, vi = np.floor(u_).astype(int), np.floor(v_).astype(int)
            ok = (np.abs(facing) > 0.2) & (ui >= 0) & (vi >= 0) & (ui < W) & (vi < H) & (dep > 0)
            if not ok.any():
                continue
            zz = np.full(len(P), -np.inf)
            zz[ok] = zb[vi[ok], ui[ok]]
            ok &= dep <= zz + 0.15
            ty = (ys[inside] - 0.5).astype(int)
            tx = (xs[inside] - 0.5).astype(int)
            seen[ty[ok], tx[ok]] = True
            count += int(ok.sum())
        pv2.log(f"[{aid}] seen texels from {v.name}: {count}")
    seen = cv2.dilate(seen.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    os.makedirs(OUT, exist_ok=True)
    cv2.imwrite(os.path.join(OUT, f"{aid}_seen_lod0.png"), (seen * 255).astype(np.uint8))
    pv2.log(f"[{aid}] seen fraction {seen.mean():.3f}")


if __name__ == "__main__":
    main(sys.argv[1])
