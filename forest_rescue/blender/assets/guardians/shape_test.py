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
    if "--full" in sys.argv:
        import gfur
        rng = np.random.default_rng(spec.SEED)
        hv, hf = meshes["bind"]
        clumps = spec.fur(sk, hv, hf, pans, rng)
        if spec.details.__code__.co_argcount >= 4:
            dets = spec.details(sk, hv, hf, pans)
        else:
            dets = spec.details(sk)
        segs = [(b, sk.head(b), sk.tail(b)) for b in sk.deform if b != "root"]

        def nearest(c):
            best, bb = 9.0, None
            for b, a, t in segs:
                ab = t - a
                u = np.clip(((c - a) @ ab) / (ab @ ab), 0, 1)
                d = np.linalg.norm(c - (a + u * ab))
                if d < best:
                    best, bb = d, b
            return bb
        pieces = [(gfur.clump_mesh(c), nearest(c.root)) for c in clumps]
        pieces += [(d["mesh"], d["bone"]) for d in dets]
        print("clumps", len(clumps), "details", len(dets))

        def extra(sk_, pose_key, name):
            pose = poses.get(pose_key)
            V, F = [], []
            off = 0
            for (v, f, _uv), b in pieces:
                if pose is not None and b is not None:
                    T = pose[b] @ np.linalg.inv(sk.rest[b])
                    v = v @ T[:3, :3].T + T[:3, 3]
                V.append(v)
                F.append(f + off)
                off += len(v)
            return np.vstack(V), np.vstack(F)
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
