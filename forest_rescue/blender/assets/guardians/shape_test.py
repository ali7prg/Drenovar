"""Fast silhouette check of a species body (no Blender): python shape_test.py <spec_module> <out_dir> [voxel]."""
import importlib
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

import gbody  # noqa: E402
from frlib import core  # noqa: E402


def main():
    spec = importlib.import_module(sys.argv[1])
    out = sys.argv[2]
    voxel = float(sys.argv[3]) if len(sys.argv) > 3 else 0.02
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    pans = spec.panels()
    sk = spec.skeleton()
    parts = spec.body_parts(sk)
    poses = {"bind": None}
    if hasattr(spec, "side_stance"):
        poses["side"] = spec.side_stance(sk)
    meshes = {}
    for pn, pose in poses.items():
        F = gbody.build_field(parts, voxel, pose=pose, sk=sk)
        v, f = F.mesh()
        meshes[pn] = (v, f)
        print(pn, "mesh", len(v), len(f), f"{time.time() - t0:.1f}s")
    extra = getattr(spec, "shape_test_extra", None)
    rows = []
    for name, pan in pans.items():
        pose_key = "side" if (name == "side" and "side" in meshes) else "bind"
        v, f = meshes[pose_key]
        if extra is not None:
            ev, ef = extra(sk, pose_key, name)
            if ev is not None and len(ev):
                f = np.vstack([f, ef + len(v)])
                v = np.vstack([v, ev])
        m = gbody.silhouette(v, f, pan.view)
        s = gbody.iou(pan.mask, m)
        d = gbody.diff_image(pan.view, m)
        img = np.concatenate([pan.view.image, d], axis=1)
        core.save_rgba(os.path.join(out, f"shape_{name}.png"), img)
        rows.append((name, s))
        print(f"IoU {name}: {s:.3f}")
    np.savez_compressed(os.path.join(out, "bind_mesh.npz"), v=meshes["bind"][0], f=meshes["bind"][1])


if __name__ == "__main__":
    main()
