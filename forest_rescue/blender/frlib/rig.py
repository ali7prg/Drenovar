"""Armatures, skinning and clip authoring helpers (bpy 5.x, slotted actions).

Clip authoring model: compute a pose per frame (FK, or IK constraints evaluated by Blender),
capture local bone bases with `capture_pose`, then write dense keys with `write_action`.
Loops must have identical first/last frames; clips are in place (root motion = 0).
"""
import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector, Euler

from . import core


def armature(name, bones, col=None):
    """bones: [{name, head, tail, parent=None, roll=0.0, deform=True, connect=False}]"""
    arm = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, arm)
    core.link(obj, col)
    arm.display_type = "OCTAHEDRAL"
    core.select_only([obj])
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = {}
    for b in bones:
        eb = arm.edit_bones.new(b["name"])
        eb.head = Vector(b["head"])
        eb.tail = Vector(b["tail"])
        eb.roll = b.get("roll", 0.0)
        eb.use_deform = b.get("deform", True)
        ebs[b["name"]] = eb
    for b in bones:
        if b.get("parent"):
            ebs[b["name"]].parent = ebs[b["parent"]]
            ebs[b["name"]].use_connect = b.get("connect", False)
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in obj.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return obj


def bind(mesh_obj, arm_obj, bone_names, W):
    """Create vertex groups from weights W (N,B) and add an Armature modifier."""
    mesh_obj.vertex_groups.clear()
    groups = [mesh_obj.vertex_groups.new(name=b) for b in bone_names]
    for j, vg in enumerate(groups):
        col = W[:, j]
        nz = np.nonzero(col > 0)[0]
        if len(nz) == 0:
            continue
        # group identical weights to reduce API calls
        vals = np.round(col[nz], 4)
        order = np.argsort(vals)
        nz, vals = nz[order], vals[order]
        splits = np.nonzero(np.diff(vals))[0] + 1
        for idx, val in zip(np.split(nz, splits), np.split(vals, splits)):
            vg.add(idx.tolist(), float(val[0]), "REPLACE")
    mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm_obj
    mesh_obj.parent = arm_obj
    mesh_obj.matrix_parent_inverse = arm_obj.matrix_world.inverted()
    return mod


def bind_rigid(obj, arm_obj, bone_name):
    """Skin a whole prop mesh (halter, ribbon, weapon) to one bone with weight 1."""
    vg = obj.vertex_groups.new(name=bone_name)
    vg.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm_obj
    obj.parent = arm_obj
    obj.matrix_parent_inverse = arm_obj.matrix_world.inverted()


def copy_weights_nearest(src_obj, dst_obj, max_dist=0.05):
    """Data-transfer vertex weights from body to clothing/accessories (applied)."""
    mod = dst_obj.modifiers.new("wt", "DATA_TRANSFER")
    mod.object = src_obj
    mod.use_vert_data = True
    mod.data_types_verts = {"VGROUP_WEIGHTS"}
    mod.vert_mapping = "POLYINTERP_NEAREST"
    mod.layers_vgroup_select_src = "ALL"
    mod.layers_vgroup_select_dst = "NAME"
    core.select_only([dst_obj])
    bpy.ops.object.datalayout_transfer(modifier="wt")
    bpy.ops.object.modifier_apply(modifier="wt")


# --------------------------------------------------------------------------- posing

def rest_pose(arm_obj):
    for pb in arm_obj.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)


def rot(axis, deg):
    return Quaternion(Vector(axis).normalized(), math.radians(deg))


def euler_q(x=0.0, y=0.0, z=0.0):
    return Euler((math.radians(x), math.radians(y), math.radians(z)), "XYZ").to_quaternion()


def set_local(arm_obj, bone, q=None, loc=None):
    pb = arm_obj.pose.bones[bone]
    if q is not None:
        pb.rotation_quaternion = q
    if loc is not None:
        pb.location = loc


def add_ik(arm_obj, bone, target, chain, pole=None, pole_angle=-90.0, weight=1.0, use_tail=True):
    """IK constraint whose target/pole are empties (returned) driven by the clip code."""
    pb = arm_obj.pose.bones[bone]
    con = pb.constraints.new("IK")
    con.target = target
    con.chain_count = chain
    con.use_tail = use_tail
    con.weight = weight
    if pole is not None:
        con.pole_target = pole
        con.pole_angle = math.radians(pole_angle)
    return con


def empty(name, loc, size=0.1, col=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = size
    e.location = loc
    core.link(e, col)
    return e


def clear_constraints(arm_obj):
    for pb in arm_obj.pose.bones:
        for c in list(pb.constraints):
            pb.constraints.remove(c)


def capture_pose(arm_obj, bones=None):
    """Visual (constraint-evaluated) local bases of the current frame: {bone: (loc, quat)}."""
    bpy.context.view_layer.update()
    out = {}
    for pb in arm_obj.pose.bones:
        if bones is not None and pb.name not in bones:
            continue
        m = arm_obj.convert_space(pose_bone=pb, matrix=pb.matrix, from_space="POSE", to_space="LOCAL")
        loc, q, _s = m.decompose()
        out[pb.name] = (Vector(loc), Quaternion(q))
    return out


def write_action(arm_obj, name, frames, loop=False, keep_location=("root",)):
    """frames: list of {bone: (loc, quat)} sampled at consecutive integer frames from 0.

    Writes dense keys into a new action (fake user) and leaves it assigned.
    keep_location: bones whose translation is keyed (others rotation only).
    """
    act = bpy.data.actions.get(name)
    if act is not None:
        bpy.data.actions.remove(act)
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()
    arm_obj.animation_data.action = act
    prev = {}
    for f, pose in enumerate(frames):
        for bone, (loc, q) in pose.items():
            pb = arm_obj.pose.bones[bone]
            # keep quaternion hemisphere continuous
            if bone in prev and prev[bone].dot(q) < 0:
                q = -q
            prev[bone] = q
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=f, group=bone)
            if bone in keep_location or loc.length > 1e-6:
                pb.location = loc
                pb.keyframe_insert("location", frame=f, group=bone)
    act.use_frame_range = True
    act.frame_start = 0
    act.frame_end = len(frames) - 1
    act.use_cyclic = bool(loop)
    act["loop"] = bool(loop)
    return act


def unassign(arm_obj):
    if arm_obj.animation_data:
        arm_obj.animation_data.action = None
    rest_pose(arm_obj)


# --------------------------------------------------------------------------- gait math helpers

def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def foot_cycle(phase, stride, lift, duty=0.6):
    """Foot offset (forward, up) for a cyclic gait. phase in [0,1); stance first (duty fraction).

    In stance the foot slides backward linearly (+stride/2 -> -stride/2) = no slip in place;
    in swing it returns forward on an eased arc with height `lift`.
    """
    phase = phase % 1.0
    if phase < duty:
        s = phase / duty
        return stride * (0.5 - s), 0.0
    s = (phase - duty) / (1 - duty)
    e = smoothstep(s)
    return stride * (-0.5 + e), lift * math.sin(math.pi * s) ** 0.9


def spring_chain(values, stiffness=0.3, damping=0.7):
    """Delayed follow-through for secondary motion (tails, ears, manes): returns smoothed copy."""
    out = []
    pos = values[0]
    vel = 0.0
    for v in list(values) * 2:  # two passes so loops settle
        acc = (v - pos) * stiffness
        vel = vel * damping + acc
        pos = pos + vel
        out.append(pos)
    return out[len(values):]
