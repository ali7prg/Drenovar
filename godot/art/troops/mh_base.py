"""MakeHuman (CC0) base body for DRENOVAR soldiers.

Builds an anatomically proportioned male body from the MakeHuman hm08 base
mesh and macro targets, a game skeleton derived from the MakeHuman default
skeleton (fingers and forearm/upper-arm twist kept, face bones folded into the
head) and the official CC0 skin weights, remapped onto the kept bones.

Coordinates: MakeHuman OBJ is Y-up in decimetres facing +Z. Blender objects
here are Z-up in metres facing -Y, which the glTF exporter turns into the
Y-up/+Z-forward convention the game already uses.
"""
import json
import math
import os

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

MH_DATA = os.environ.get("MAKEHUMAN_DATA", "/tmp/claude-0/ext/makehuman/makehuman/data")
SCALE = 0.1

# Bones kept in the game skeleton. Everything else is merged into the nearest
# kept ancestor (weights included).
SIDE_BONES = ["clavicle", "shoulder01", "upperarm01", "upperarm02", "lowerarm01", "lowerarm02", "wrist",
              "finger1-1", "finger1-2", "finger1-3", "finger2-1", "finger2-2", "finger2-3",
              "finger3-1", "finger3-2", "finger3-3", "finger4-1", "finger4-2", "finger4-3",
              "finger5-1", "finger5-2", "finger5-3",
              "pelvis", "upperleg01", "upperleg02", "lowerleg01", "lowerleg02", "foot", "toe1-1"]
KEEP = {"root", "spine05", "spine04", "spine03", "spine02", "spine01", "neck01", "neck02", "head"}
for _side in ("L", "R"):
    KEEP.update(f"{b}.{_side}" for b in SIDE_BONES)
# Toes are merged into one toe bone per foot; metacarpals into the wrist.
EXTRA_MERGE = {}
for _side in ("L", "R"):
    for t in range(1, 6):
        for k in range(1, 4):
            EXTRA_MERGE[f"toe{t}-{k}.{_side}"] = f"toe1-1.{_side}"
EXTRA_MERGE.pop("toe1-1.L")
EXTRA_MERGE.pop("toe1-1.R")


def to_blender(v):
    return Vector((v[0] * SCALE, -v[2] * SCALE, v[1] * SCALE))


def read_obj(path):
    verts, uvs, faces = [], [], []
    group = None
    with open(path) as handle:
        for line in handle:
            if line.startswith("v "):
                verts.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("vt "):
                uvs.append([float(x) for x in line.split()[1:3]])
            elif line.startswith("g "):
                group = line.split()[1]
            elif line.startswith("f "):
                vi, ti = [], []
                for token in line.split()[1:]:
                    parts = token.split("/")
                    vi.append(int(parts[0]) - 1)
                    ti.append(int(parts[1]) - 1 if len(parts) > 1 and parts[1] else -1)
                faces.append((vi, ti, group))
    return np.array(verts, dtype=np.float64), uvs, faces


def read_target(path):
    rows = []
    with open(path) as handle:
        for line in handle:
            if not line[:1].isdigit():
                continue
            parts = line.split()
            rows.append((int(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])))
    if not rows:
        return np.zeros(0, dtype=np.int64), np.zeros((0, 3))
    data = np.array(rows)
    return data[:, 0].astype(np.int64), data[:, 1:4]


def blend_levels(value):
    """MakeHuman macro interpolation: 0 -> min, 0.5 -> average, 1 -> max."""
    if value < 0.5:
        return {"min": (0.5 - value) * 2.0, "average": value * 2.0}
    return {"average": (1.0 - value) * 2.0, "max": (value - 0.5) * 2.0}


def macro_targets(muscle=0.6, weight=0.5, height=0.5, proportions=0.8, age="young"):
    targets = [(f"macrodetails/caucasian-male-{age}.target", 1.0)]
    for m, mw in blend_levels(muscle).items():
        for w, ww in blend_levels(weight).items():
            factor = mw * ww
            if factor <= 0:
                continue
            targets.append((f"macrodetails/universal-male-{age}-{m}muscle-{w}weight.target", factor))
            if height > 0.5:
                targets.append((f"macrodetails/height/male-{age}-{m}muscle-{w}weight-maxheight.target", factor * (height - 0.5) * 2))
            elif height < 0.5:
                targets.append((f"macrodetails/height/male-{age}-{m}muscle-{w}weight-minheight.target", factor * (0.5 - height) * 2))
            targets.append((f"macrodetails/proportions/male-{age}-{m}muscle-{w}weight-idealproportions.target", factor * proportions))
    return targets


def kept_parent(bones, name):
    while name not in KEEP:
        if name in EXTRA_MERGE:
            return EXTRA_MERGE[name]
        name = bones[name]["parent"]
        if name is None:
            return "root"
    return name


def build_body(name="Soldier", muscle=0.6, weight=0.5, height=0.5, proportions=0.8, age="young"):
    verts, uvs, faces = read_obj(os.path.join(MH_DATA, "3dobjs", "base.obj"))
    for target, factor in macro_targets(muscle, weight, height, proportions, age):
        path = os.path.join(MH_DATA, "targets", target)
        if not os.path.exists(path) or factor == 0:
            continue
        index, delta = read_target(path)
        verts[index] += delta * factor
    # Stand the soldier on the ground plane (soles at z = 0).
    body_index = sorted({i for f in faces if f[2] == "body" for i in f[0]})
    verts[:, 1] -= verts[body_index, 1].min()
    skeleton = json.load(open(os.path.join(MH_DATA, "rigs", "default.mhskel")))
    joints = {name: verts[idx].mean(axis=0) for name, idx in skeleton["joints"].items()}
    bones = skeleton["bones"]

    # Body mesh: only the skin group; keep original vertex indices through a map.
    body_faces = [f for f in faces if f[2] == "body"]
    used = sorted({i for f in body_faces for i in f[0]})
    remap = {old: new for new, old in enumerate(used)}
    mesh = bpy.data.meshes.new(name + "_body")
    mesh.from_pydata([to_blender(verts[i]) for i in used], [], [[remap[i] for i in f[0]] for f in body_faces])
    uv_layer = mesh.uv_layers.new(name="UVMap")
    loop = 0
    for f in body_faces:
        for t in f[1]:
            uv_layer.data[loop].uv = uvs[t] if t >= 0 else (0, 0)
            loop += 1
    mesh.validate()
    body = bpy.data.objects.new(name + "_Body", mesh)
    bpy.context.scene.collection.objects.link(body)
    for poly in mesh.polygons:
        poly.use_smooth = True

    # Armature.
    arm_data = bpy.data.armatures.new(name + "_Rig")
    rig = bpy.data.objects.new(name + "_Rig", arm_data)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    edit = {}
    order = [b for b in bones if b in KEEP]
    for bone_name in order:
        spec = bones[bone_name]
        eb = arm_data.edit_bones.new(bone_name)
        eb.head = to_blender(joints[spec["head"]])
        eb.tail = to_blender(joints[spec["tail"]])
        if (eb.tail - eb.head).length < 1e-4:
            eb.tail = eb.head + Vector((0, 0, 0.05))
        edit[bone_name] = eb
    for bone_name in order:
        parent = bones[bone_name]["parent"]
        while parent is not None and parent not in KEEP:
            parent = bones[parent]["parent"]
        if parent is not None:
            edit[bone_name].parent = edit[parent]
            if (edit[bone_name].head - edit[parent].tail).length < 1e-4:
                edit[bone_name].use_connect = True
    # Consistent rolls: limbs roll towards the front, spine towards the back.
    for eb in arm_data.edit_bones:
        if eb.name.startswith(("finger", "wrist", "lowerarm", "upperarm", "shoulder", "clavicle")):
            eb.align_roll(Vector((0, 0, 1)) if "finger1" not in eb.name else Vector((0, -1, 0)))
        else:
            eb.align_roll(Vector((0, -1, 0)))
    bpy.ops.object.mode_set(mode="OBJECT")

    # Weights remapped onto kept bones.
    weights = json.load(open(os.path.join(MH_DATA, "rigs", skeleton["weights_file"])))["weights"]
    acc = {}
    for bone_name, pairs in weights.items():
        target = kept_parent(bones, bone_name) if bone_name in bones else "head"
        for vi, w in pairs:
            if vi in remap:
                key = (remap[vi], target)
                acc[key] = acc.get(key, 0.0) + w
    groups = {}
    for (vi, bone_name), w in acc.items():
        group = groups.get(bone_name) or body.vertex_groups.new(name=bone_name)
        groups[bone_name] = group
        group.add([vi], w, "ADD")
    modifier = body.modifiers.new("Armature", "ARMATURE")
    modifier.object = rig
    body.parent = rig
    return rig, body, joints


def add_eyes(rig, joints, name="Soldier"):
    """CC0 MakeHuman low-poly eyes, rigidly bound to the head."""
    path = os.path.join(MH_DATA, "eyes", "low-poly", "low-poly.obj")
    verts, uvs, faces = read_obj(path)
    # The eye proxy is authored around the base mesh eye sockets; shift it to
    # the fitted joint positions so it follows the macro targets.
    base_verts, _, _ = read_obj(os.path.join(MH_DATA, "3dobjs", "base.obj"))
    skeleton = json.load(open(os.path.join(MH_DATA, "rigs", "default.mhskel")))
    base_joints = {n: base_verts[i].mean(axis=0) for n, i in skeleton["joints"].items() if "eye" in n}
    out = []
    for v in verts:
        side = "l" if v[0] > 0 else "r"
        key = f"eye.{side.upper()}____head"
        offset = joints[key] - base_joints[key] if key in joints and key in base_joints else 0
        out.append(to_blender(v + offset))
    mesh = bpy.data.meshes.new(name + "_eyes")
    mesh.from_pydata(out, [], [f[0] for f in faces])
    layer = mesh.uv_layers.new(name="UVMap")
    loop = 0
    for f in faces:
        for t in f[1]:
            layer.data[loop].uv = uvs[t] if t >= 0 else (0, 0)
            loop += 1
    obj = bpy.data.objects.new(name + "_Eyes", mesh)
    bpy.context.scene.collection.objects.link(obj)
    group = obj.vertex_groups.new(name="head")
    group.add(list(range(len(out))), 1.0, "REPLACE")
    obj.modifiers.new("Armature", "ARMATURE").object = rig
    obj.parent = rig
    for poly in mesh.polygons:
        poly.use_smooth = True
    return obj
