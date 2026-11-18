"""Stage 2: LOD0 body (decimate + UV), join detail meshes, armature, skin weights, LOD1/LOD2.

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/boss/maw_stage_rig.py [--preview DIR]
Reads cache maw_mesh.blend, writes maw_rig.blend
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

from frlib import core, render, rig  # noqa: E402
import maw_body as B  # noqa: E402
import maw_details as D  # noqa: E402
import maw_rig as MR  # noqa: E402

AID = C.ASSET_ID


def log(*a):
    print("[maw_rig]", *a, flush=True)


def set_rigid(obj, table, bones_of_vert=None):
    nv = len(obj.data.vertices)
    ids = np.full(nv, -1, np.int32) if bones_of_vert is None else np.array([table.index(b) for b in bones_of_vert], np.int32)
    at = obj.data.attributes.get("rigid_id") or obj.data.attributes.new("rigid_id", "INT", "POINT")
    at.data.foreach_set("value", ids)


def make_lod0(table):
    high = bpy.data.objects["maw_high"]
    t0 = time.time()
    body = core.decimate_to(high, C.BODY_TRIS_LOD0, name=f"{AID}_LOD0")
    log("body LOD0", core.tri_count(body), f"{time.time() - t0:.1f}s")
    import maw_uv
    names = [b["name"] for b in B.bone_table()]
    ns, nr = maw_uv.region_unwrap(body, names)
    log("region unwrap: seams", ns, "regions", nr)
    set_rigid(body, table)
    mats = materials()
    body.data.materials.clear()
    body.data.materials.append(mats[0])
    body.data.materials.append(mats[1])
    parts = []
    for key in ("teeth", "claws", "eyes", "tongue"):
        o = bpy.data.objects[f"maw_det_{key}"]
        bov = list(o["bones"])
        set_rigid(o, table, bov)
        o.data.materials.clear()
        o.data.materials.append(mats[0])
        o.data.materials.append(mats[1])
        for p in o.data.polygons:
            p.material_index = 1
        parts.append(o)
    obj = core.join([body] + parts, name=f"{AID}_LOD0")
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def materials():
    skin = bpy.data.materials.get("M_maw_skin") or core.material("M_maw_skin", base=(0.2, 0.19, 0.15, 1), rough=0.8)
    ker = bpy.data.materials.get("M_maw_keratin") or core.material("M_maw_keratin", base=(0.8, 0.72, 0.58, 1), rough=0.45)
    return skin, ker


def lod_copy(src, name, tris):
    o = core.decimate_to(src, tris, name=name)
    return o


def preview(arm, objs, out):
    os.makedirs(out, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "SINGLE"
    sh.show_cavity = True
    poses = {
        "rest": {},
        "test": {"jaw": ((1, 0, 0), -30), "neck_02": ((0, 0, 1), 18), "head": ((1, 0, 0), 12),
                 "thigh_L": ((1, 0, 0), 35), "shin_L": ((1, 0, 0), -50), "foot_L": ((1, 0, 0), 30),
                 "tail_03": ((0, 0, 1), 15), "tail_05": ((0, 0, 1), 15), "tail_07": ((0, 0, 1), 15),
                 "upperarm_R": ((1, 0, 0), 40), "spine_03": ((0, 0, 1), -10)},
    }
    for pname, pose in poses.items():
        rig.rest_pose(arm)
        for b, (ax, deg) in pose.items():
            arm.pose.bones[b].rotation_quaternion = MR.arm_rotation(arm, b, MR.axis_q(ax, deg))
        bpy.context.view_layer.update()
        for vname, (loc, look, lens) in {"q34": ((7.0, -9.5, 4.5), (0, -1, 2), 35),
                                         "head": ((2.8, -6.6, 3.4), (0, -3.9, 2.9), 50),
                                         "rear": ((-7.0, 8.0, 4.0), (0, 0.5, 1.8), 35)}.items():
            render.perspective_camera(loc, look, lens=lens, res=(800, 560))
            scene.render.filepath = os.path.join(out, f"{pname}_{vname}.png")
            bpy.ops.render.render(write_still=True)
    rig.rest_pose(arm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default="")
    args = ap.parse_args(sys.argv[1:])
    bpy.ops.wm.open_mainfile(filepath=C.cache("maw_mesh.blend"))
    table = sorted({b for k in ("teeth", "claws", "eyes", "tongue") for b in bpy.data.objects[f"maw_det_{k}"]["bones"]})
    lod0 = make_lod0(table)
    arm, bone_names = MR.build_armature(f"{AID}_rig")
    log("deform bones", len(bone_names))
    lods = [lod0, lod_copy(lod0, f"{AID}_LOD1", C.LOD_TRIS[1] * 0.97), lod_copy(lod0, f"{AID}_LOD2", C.LOD_TRIS[2] * 0.97)]
    used = {}
    for k, (o, merge) in enumerate(zip(lods, [None, MR.LOD1_MERGE, MR.LOD2_MERGE])):
        t0 = time.time()
        W, u = MR.bind_body(o, arm, bone_names, table, merge)
        used[o.name] = u
        log(o.name, core.tri_count(o), "tris; bones used", len(u), f"{time.time() - t0:.1f}s")
    arm["bones_used"] = {k: len(v) for k, v in used.items()}
    bpy.data.objects.remove(bpy.data.objects["maw_high"], do_unlink=True)
    for o in list(bpy.data.objects):
        if o.name.startswith("maw_det_"):
            bpy.data.objects.remove(o, do_unlink=True)
    for o in lods[1:]:
        o.hide_render = True
        o.hide_set(True)
    if args.preview:
        preview(arm, lods, args.preview)
    bpy.ops.wm.save_as_mainfile(filepath=C.cache("maw_rig.blend"), compress=True)
    log("saved")


if __name__ == "__main__":
    main()
