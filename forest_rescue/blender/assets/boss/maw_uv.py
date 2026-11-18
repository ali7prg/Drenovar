"""Region-seam UV unwrap for the Ancient Maw body: islands per body part (left/right halves for head,
trunk and tail; limb segments cut along their inner/back side), angle-based unwrap, head islands
up-scaled before packing (more texels for close-ups)."""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from frlib import core
import maw_body as B
import maw_rig as MR

TUBE_CUT = {  # region -> (bone for axis, cut direction in armature space; x sign flipped for right side)
    "thigh": ("thigh", (-0.6, 0.8, 0.0)), "shin": ("shin", (-0.5, 0.85, 0.0)), "foot": ("foot", (-0.3, 1.0, 0.0)),
    "toe2": ("toe2a", (0, 0, -1)), "toe3": ("toe3a", (0, 0, -1)), "toe4": ("toe4a", (0, 0, -1)),
    "uarm": ("upperarm", (-1.0, 0.3, 0.0)), "farm": ("forearm", (-1.0, 0.0, 0.0)), "hand": ("hand", (-1.0, 0.0, 0.0)),
    "finger1": ("finger1a", (0, 1, 0)), "finger2": ("finger2a", (0, 1, 0)), "finger3": ("finger3", (0, 1, 0)),
}


def bone_region(b):
    if b in ("head", "jaw") or b.startswith("tongue"):
        return "head", True
    if b.startswith(("neck", "spine")) or b in ("pelvis", "root"):
        return "trunk", True
    if b.startswith("tail_"):
        return ("tailA" if int(b[5:]) <= 5 else "tailB"), True
    side = b[-1]
    base = b[:-2]
    m = {"thigh": "thigh", "shin": "shin", "foot": "foot", "dewclaw": "foot", "toe2a": "toe2", "toe2b": "toe2",
         "toe3a": "toe3", "toe3b": "toe3", "toe4a": "toe4", "toe4b": "toe4", "upperarm": "uarm", "forearm": "farm",
         "hand": "hand", "finger1a": "finger1", "finger1b": "finger1", "finger2a": "finger2", "finger2b": "finger2",
         "finger3": "finger3"}
    return m[base] + "_" + side, False


def region_unwrap(obj, bone_names, head_scale=1.7, margin=0.0025):
    me = obj.data
    nv = len(me.vertices)
    V = np.empty(nv * 3)
    me.vertices.foreach_get("co", V)
    V = V.reshape(nv, 3)
    ne = len(me.edges)
    E = np.empty(ne * 2, np.int64)
    me.edges.foreach_get("vertices", E)
    W = MR.compute_weights(V, E.reshape(ne, 2), bone_names)
    dom = np.argmax(W, axis=1)
    sp = {b["name"]: (np.array(b["head"]), np.array(b["tail"])) for b in B.bone_table()}
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    flab, fang = [], []
    for f in bm.faces:
        idx = [v.index for v in f.verts]
        c = V[idx].mean(0)
        votes = np.bincount(dom[idx], minlength=len(bone_names))
        b = bone_names[int(np.argmax(votes))]
        reg, halves = bone_region(b)
        if halves:
            reg = reg + ("_L" if c[0] >= 0 else "_R")
        ang = 0.0
        key = reg.rsplit("_", 1)[0]
        if key in TUBE_CUT:
            side = reg[-1]
            bn, cut = TUBE_CUT[key]
            h, t = sp[f"{bn}_{side}"]
            ax = (t - h) / np.linalg.norm(t - h)
            cutv = np.array(cut, float)
            if side == "R":
                cutv[0] = -cutv[0]
            r1 = -(cutv - ax * (cutv @ ax))
            r1 /= max(np.linalg.norm(r1), 1e-9)
            r2 = np.cross(ax, r1)
            v = c - h
            ang = math.atan2(v @ r2, v @ r1)
        flab.append(reg)
        fang.append(ang)
    nseam = 0
    for e in bm.edges:
        e.seam = False
        if len(e.link_faces) != 2:
            continue
        f1, f2 = e.link_faces
        a, b = flab[f1.index], flab[f2.index]
        if a != b:
            e.seam = True
        elif a.rsplit("_", 1)[0] in TUBE_CUT:
            t1, t2 = fang[f1.index], fang[f2.index]
            if t1 * t2 < 0 and abs(t1) + abs(t2) > math.pi:
                e.seam = True
        nseam += e.seam
    bm.to_mesh(me)
    bm.free()
    core.select_only([obj])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.unwrap(method="ANGLE_BASED", fill_holes=True, correct_aspect=True, margin=margin)
    bpy.ops.object.mode_set(mode="OBJECT")
    # world-area normalisation per island is done by pack_islands(scale=True); boost the head islands
    uvl = me.uv_layers.active.data
    head_faces = [i for i, r in enumerate(flab) if r.startswith("head")]
    if head_scale != 1.0 and head_faces:
        loops = [li for fi in head_faces for li in me.polygons[fi].loop_indices]
        uv = np.array([uvl[li].uv[:] for li in loops])
        c = uv.mean(0)
        uv = c + (uv - c) * head_scale
        for li, u in zip(loops, uv):
            uvl[li].uv = u
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode="OBJECT")
    if head_scale != 1.0 and head_faces:
        uv = np.array([uvl[li].uv[:] for li in loops])
        c = uv.mean(0)
        uv = c + (uv - c) * head_scale
        for li, u in zip(loops, uv):
            uvl[li].uv = u
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, rotate_method="ANY", scale=True, margin_method="SCALED", margin=margin,
                            shape_method="CONCAVE")
    bpy.ops.object.mode_set(mode="OBJECT")
    return nseam, len(set(flab))
