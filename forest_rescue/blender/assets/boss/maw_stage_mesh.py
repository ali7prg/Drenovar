"""Stage 1: SDF body -> high-res mesh, LOD0 body (decimated), detail meshes; preview renders.

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/boss/maw_stage_mesh.py \
    [--voxel 0.016] [--preview DIR]
Writes cache: maw_high.npz, maw_mesh.blend
"""
import argparse
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maw_common as C  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from frlib import core, render  # noqa: E402
import maw_body as B  # noqa: E402
import maw_details as D  # noqa: E402
import maw_refs as R  # noqa: E402


def log(*a):
    print("[maw_mesh]", *a, flush=True)


def build_high(voxel):
    t0 = time.time()
    side = R.side_view(corrected=True)
    front = R.front_view()
    F, add, sub = B.build_field(voxel=voxel, detail=True, hull_views=[side, front], hull_k=0.03)
    F.smooth(0.6)
    log(f"field {F.n} built in {time.time() - t0:.1f}s")
    verts, faces = F.mesh()
    log(f"marching cubes: {len(verts)} verts {len(faces)} tris ({time.time() - t0:.1f}s)")
    return verts, faces


def detail_object(name, parts):
    V, Fc, UV, bone_of_vert, regions = [], [], [], [], []
    off = 0
    for p in parts:
        v = np.asarray(p["verts"], float)
        V.append(v)
        for f in p["faces"]:
            Fc.append([i + off for i in f])
        UV += p["uv"]
        bone_of_vert += [p["bone"]] * len(v)
        regions.append((p["region"], len(p["faces"])))
        off += len(v)
    V = np.concatenate(V)
    obj = core.mesh_object(name, V, Fc, uvs=np.array(UV), smooth=True)
    obj["bones"] = bone_of_vert
    return obj, bone_of_vert


def preview(objs, out_dir, tag=""):
    os.makedirs(out_dir, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "SINGLE"
    sh.single_color = (0.55, 0.52, 0.45)
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.show_shadows = False
    scene.render.film_transparent = False
    views = {
        "q34_front_left": ((7.0, -9.5, 4.5), (0.0, -1.0, 2.0), 35),
        "q34_rear_left": ((7.5, 8.5, 5.0), (0.0, 0.5, 2.0), 35),
        "left": ((14.0, 0.2, 2.0), (0.0, 0.2, 2.0), 35),
        "front": ((0.0, -14.0, 2.0), (0.0, 0.0, 2.0), 50),
        "top": ((0.0, 0.3, 16.0), (0.0, 0.3, 0.0), 35),
        "head34": ((2.6, -6.4, 3.6), (0.0, -3.9, 3.05), 50),
        "head_front": ((0.0, -7.5, 3.1), (0.0, -3.9, 3.05), 60),
        "feet": ((3.0, -3.0, 0.8), (0.6, -0.3, 0.4), 45),
    }
    for name, (loc, look, lens) in views.items():
        render.perspective_camera(loc, look, lens=lens, res=(960, 640))
        scene.render.filepath = os.path.join(out_dir, f"{tag}{name}.png")
        scene.render.image_settings.file_format = "PNG"
        bpy.ops.render.render(write_still=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voxel", type=float, default=C.HIGH_VOXEL)
    ap.add_argument("--preview", default="")
    ap.add_argument("--no-lod", action="store_true")
    args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    core.reset()
    verts, faces = build_high(args.voxel)
    np.savez_compressed(C.cache("maw_high.npz"), verts=verts.astype(np.float32), faces=faces.astype(np.int32))
    high = core.mesh_object("maw_high", verts, faces, smooth=True)
    objs = [high]
    if not args.no_lod:
        t0 = time.time()
        body = core.decimate_to(high, C.BODY_TRIS_LOD0, name="maw_body_LOD0")
        log(f"LOD0 body {core.tri_count(body)} tris ({time.time() - t0:.1f}s)")
        objs = [body]
    parts = D.all_parts()
    det_objs = []
    for key, plist in parts.items():
        o, _ = detail_object(f"maw_det_{key}", plist)
        det_objs.append(o)
        log(key, core.tri_count(o), "tris")
    if args.preview:
        high.hide_render = not args.no_lod
        preview(objs + det_objs, args.preview)
    bpy.ops.wm.save_as_mainfile(filepath=C.cache("maw_mesh.blend"), compress=True)
    log("saved", C.cache("maw_mesh.blend"))


if __name__ == "__main__":
    main()
