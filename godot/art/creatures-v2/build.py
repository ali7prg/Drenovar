"""DRENOVAR creatures-v2 build. Run with Blender 5.3 as a Python module:
    python -I build.py --species velkor --work <dir> [--stage geometry|textures|export|all]
Stages are cached in <dir>; deleting a cache file re-runs that step.
"""
import argparse
import importlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

TEX = {0: (2048, 1024), 1: (1024, 512), 2: (512, 256)}  # (BaseColor/Normal, ORM/Emissive)


def log(*a):
    print(*a, flush=True)


def stage_geometry(sp, work, lods):
    import bpy  # noqa: F401
    import blender_ops as bo
    import geometry
    sk, parts = sp.build_cached()
    hi = geometry.highres(parts, os.path.join(work, "hi"), sp.VOXEL_BODY, sp.VOXEL_RIGID, log)
    for lod in lods:
        out = os.path.join(work, f"lod{lod}")
        if os.path.exists(os.path.join(out, "done.json")):
            continue
        os.makedirs(out, exist_ok=True)
        bo.reset()
        lod_parts = [p for p in parts if p["faces"][lod] > 0]
        groups, hi_objs = geometry.build_lod_objects(bo, lod_parts, hi, lod, log)
        for mat, objs in groups.items():
            for o in objs:
                o["part_index"] = next(p["index"] for p in parts if p["name"] == o["part"])
            ob = geometry.join(bo, objs, f"L{lod}_{mat}")
            t = time.time()
            charts, util = bo.uv_xatlas(ob, TEX[lod][0], padding=4 if lod == 0 else 3)
            log(f"  uv {mat}: {charts} charts, {util:.2f} used, {time.time() - t:.1f}s")
            arrays = bo.mesh_arrays(ob)
            np.savez_compressed(os.path.join(out, f"{mat}_mesh.npz"), **arrays)
            size_n, size_o = TEX[lod]
            # Cycles bakes: tangent-space normal from every high-res part of this material, then AO
            img = bo.bake_image(f"N_{mat}", size_n, color=(0.5, 0.5, 1.0, 1.0))
            t = time.time()
            members = [p for p in lod_parts if p["material"] == mat]
            bo.bake_normal(ob, [hi_objs[p["name"]] for p in members], img, extrusion=sp.BAKE_EXTRUSION,
                           ray=sp.BAKE_RAY)
            np.save(os.path.join(out, f"{mat}_normal.npy"), bo.image_array(img)[..., :3].astype(np.float16))
            log(f"  bake normal {mat} {size_n}: {time.time() - t:.1f}s")
            # AO is baked on the low poly with every other low-poly part present as occluder
            img = bo.bake_image(f"AO_{mat}", size_o, color=(1, 1, 1, 1))
            t = time.time()
            for h in hi_objs.values():
                h.hide_render = True
            bo.bake_ao(ob, img, samples=sp.AO_SAMPLES, distance=sp.AO_DISTANCE)
            for h in hi_objs.values():
                h.hide_render = False
            np.save(os.path.join(out, f"{mat}_ao.npy"), bo.image_array(img)[..., 0].astype(np.float16))
            log(f"  bake ao {mat} {size_o}: {time.time() - t:.1f}s")
        with open(os.path.join(out, "done.json"), "w") as f:
            json.dump({"materials": sorted(groups)}, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--stage", default="all")
    ap.add_argument("--lods", default="0,1,2")
    a = ap.parse_args()
    sp = importlib.import_module("species." + a.species)
    lods = [int(x) for x in a.lods.split(",")]
    t = time.time()
    if a.stage in ("geometry", "all"):
        stage_geometry(sp, a.work, lods)
    if a.stage in ("textures", "all", "export"):
        import texturing
        import export
        for lod in lods:
            if a.stage in ("textures", "all"):
                texturing.run(sp, a.work, lod, TEX[lod], log)
        if a.stage in ("export", "all"):
            export.run(sp, a.work, lods, log)
    log(f"done in {time.time() - t:.0f}s")


if __name__ == "__main__":
    main()
