"""Blockout preview: extracts every part at a coarse resolution and writes an
unrigged GLB with flat per-material colours, for silhouette checks in Godot.
Usage: python -I preview.py <species> <out.glb> [voxel_m]
"""
import importlib
import sys
import time
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sdf import extract, largest_component  # noqa: E402
from gltf import GLB  # noqa: E402

COLORS = {"base": (0.45, 0.40, 0.33, 1), "fur_long": (0.52, 0.47, 0.38, 1), "skin": (0.25, 0.2, 0.19, 1),
          "nose": (0.08, 0.07, 0.07, 1), "hoof": (0.12, 0.11, 0.10, 1), "antler": (0.80, 0.74, 0.60, 1),
          "moss": (0.35, 0.45, 0.12, 1), "bark": (0.33, 0.24, 0.16, 1), "stone": (0.42, 0.42, 0.44, 1),
          "tusk": (0.86, 0.80, 0.66, 1), "claw": (0.75, 0.70, 0.60, 1), "eye": (0.3, 0.9, 0.5, 1)}


def vertex_normals(v, f):
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    n = np.zeros_like(v)
    for k in range(3):
        np.add.at(n, f[:, k], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)


def main():
    sp = importlib.import_module("species." + sys.argv[1])
    out = sys.argv[2]
    h = float(sys.argv[3]) if len(sys.argv) > 3 else 0.03
    sk, parts = sp.build_cached() if hasattr(sp, "build_cached") else sp.build()
    g = GLB()
    mats = {}
    root = g.node("Preview")
    tris = 0
    for part in parts:
        t = time.time()
        hh = h if part["rigid"] is None else min(h, part.get("voxel", 0.008) * 2)
        v, f = extract(part["part"], hh)
        if len(f) == 0:
            continue
        v, f = largest_component(v, f, 0.02)
        d, D = part["part"].eval(v, keep=True)
        owner = np.argmin(D, axis=1)
        matnames = [part["part"].prims[o].mat for o in owner]
        prims = []
        for mname in sorted(set(matnames)):
            sel = np.array([m == mname for m in matnames])
            fsel = f[np.all(sel[f], axis=1) | (sel[f].sum(1) >= 2)]
            if len(fsel) == 0:
                continue
            if mname not in mats:
                col = COLORS.get(mname, (0.5, 0.5, 0.5, 1))
                mats[mname] = g.material(mname, base_color=[c ** 2.2 for c in col[:3]] + [1.0], roughness=0.8)
            used = np.unique(fsel)
            remap = -np.ones(len(v), np.int64)
            remap[used] = np.arange(len(used))
            vv = v[used]
            ff = remap[fsel]
            prims.append({"pos": vv, "nrm": vertex_normals(vv, ff), "idx": ff, "material": mats[mname]})
            tris += len(ff)
        mi = g.mesh(part["name"], prims)
        g.node(part["name"], root, mesh=mi)
        print(f"{part['name']}: {len(v)} v {len(f)} f  {time.time() - t:.1f}s", flush=True)
    # bones as tiny markers for checking the skeleton fit
    g.save(out)
    print("tris", tris, "->", out)


if __name__ == "__main__":
    main()
