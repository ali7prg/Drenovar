"""Stage 2: armature `new_dinosaur_boss` (70 deform bones), skin weights (<= 4), detail binding,
IK control rig (muted constraints on the master), rest-pose sockets.

In:  cache/maw2_mesh.blend   Out: cache/maw2_rig.blend
"""
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mv2_common as C  # noqa: E402
import mv2_body as B  # noqa: E402
import mv2_rig as RG  # noqa: E402
from frlib import core, rig, sdf  # noqa: E402

ARM = C.ASSET_ID + "_rig"


def build_armature():
    table = RG.bone_table()
    arm = rig.armature(ARM, table)
    arm.data.name = "new_dinosaur_boss"
    arm["rig"] = "new_dinosaur_boss"
    # bone rolls: keep Z of every bone close to world +Z (sideways bones) for readable local axes
    core.select_only([arm])
    bpy.ops.object.mode_set(mode="EDIT")
    for eb in arm.data.edit_bones:
        eb.align_roll(Vector((0, 0, 1)) if abs((eb.tail - eb.head).normalized().z) < 0.9 else Vector((0, -1, 0)))
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm, [b["name"] for b in table]


def bind_body(body, arm, names):
    V, tris, _uv, _n = core.mesh_arrays(body, evaluated=False)
    adj = sdf.adjacency_matrix(len(V), tris)
    add, _sub = B.build_parts()
    W = RG.compute_weights(V, names, add, adjacency=adj, smooth_iters=3)
    rig.bind(body, arm, names, W)
    np.savez_compressed(C.cache("maw2_weights_lod0.npz"), W=W.astype(np.float32), names=np.array(names))
    return W


def bind_parts(obj, arm, bone_of_vertex):
    obj.vertex_groups.clear()
    groups = {}
    for i, b in enumerate(bone_of_vertex):
        if b not in groups:
            groups[b] = obj.vertex_groups.new(name=b)
        groups[b].add([i], 1.0, "REPLACE")
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    obj.parent = arm
    obj.matrix_parent_inverse = arm.matrix_world.inverted()


def detail_bones():
    import mv2_details as D
    parts = D.all_parts()
    out = {}
    for key, name in (("teeth", "maw_teeth"), ("claws", "maw_claws"), ("eyes", "maw_eyes")):
        bl = []
        for p in parts[key]:
            bl += [p["bone"]] * len(p["verts"])
        out[name] = bl
    return out


def bind_tongue(obj, arm):
    V = np.array([v.co[:] for v in obj.data.vertices])
    tb = {b["name"]: b for b in RG.bone_table()}
    chain = [tb["tongue_01"]["head"], tb["tongue_01"]["tail"], tb["tongue_02"]["tail"], tb["tongue_03"]["tail"]]
    cw, _ = RG.chain_weights(V, chain, ["tongue_01", "tongue_02", "tongue_03"])
    obj.vertex_groups.clear()
    for n, w in cw.items():
        vg = obj.vertex_groups.new(name=n)
        for i, x in enumerate(w):
            if x > 0.01:
                vg.add([i], float(x), "REPLACE")
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    obj.parent = arm
    obj.matrix_parent_inverse = arm.matrix_world.inverted()


def bind_mouth(obj, arm):
    import mv2_details as D
    wj = D.mouth_curtain()[0]["wjaw"]
    obj.vertex_groups.clear()
    vh = obj.vertex_groups.new(name="head")
    vj = obj.vertex_groups.new(name="jaw")
    for i, w in enumerate(wj):
        if w < 0.999:
            vh.add([i], float(1 - w), "REPLACE")
        if w > 0.001:
            vj.add([i], float(w), "REPLACE")
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    obj.parent = arm
    obj.matrix_parent_inverse = arm.matrix_world.inverted()


def ik_controls(arm):
    """Editable IK control rig on the master: foot/hand targets + knee/elbow poles (constraints muted,
    clips are baked FK; enable them to author new motion)."""
    col = core.collection("maw_ik_controls")
    tb = {b["name"]: b for b in RG.bone_table()}
    for side, sx in (("L", 1), ("R", -1)):
        tgt = rig.empty(f"ik_foot_{side}", tb[f"foot_{side}"]["tail"], 0.25, col)
        pole = rig.empty(f"pole_knee_{side}", (sx * 0.9, -2.0, 1.5), 0.15, col)
        con = rig.add_ik(arm, f"foot_{side}", tgt, 3, pole=pole, pole_angle=-90.0)
        con.enabled = False
        htgt = rig.empty(f"ik_hand_{side}", tb[f"hand_{side}"]["tail"], 0.12, col)
        hpole = rig.empty(f"pole_elbow_{side}", (sx * 1.2, -1.3, 1.9), 0.1, col)
        con = rig.add_ik(arm, f"hand_{side}", htgt, 3, pole=hpole, pole_angle=0.0)
        con.enabled = False


def main():
    t0 = time.time()
    bpy.ops.wm.open_mainfile(filepath=C.cache("maw2_mesh.blend"))
    arm, names = build_armature()
    body = bpy.data.objects["maw_body"]
    W = bind_body(body, arm, names)
    used = int((W.max(0) > 0).sum())
    C.log(f"body weights: {used} bones used, max influences {int((W > 0).sum(1).max())}")
    db = detail_bones()
    for name, bl in db.items():
        bind_parts(bpy.data.objects[name], arm, bl)
    bind_tongue(bpy.data.objects["maw_tongue"], arm)
    bind_mouth(bpy.data.objects["maw_mouth"], arm)
    ik_controls(arm)
    bpy.ops.wm.save_as_mainfile(filepath=C.cache("maw2_rig.blend"), compress=True)
    C.log(f"stage rig done {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
