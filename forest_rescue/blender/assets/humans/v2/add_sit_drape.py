"""Seated cloth for the civilians: Blender cloth simulation baked into a corrective morph `sit_drape`.

For one character's .blend (built by build_v2.py --stage full):
  1. cloth = LOD0 faces skinned to the skirt / apron / cloak chain (SkirtFront*, SkirtBack*, SkirtLeft/Right,
     Cloak1/2); pinned where those weights fade out (waist band, shoulders);
  2. the armature plays stand_up in reverse (standing -> seated, cloth bones held neutral) and holds the
     seated pose; cloth simulates against the body (collision) and the floor plane, so it drapes over the
     thighs and hangs between / over the knees;
  3. the settled drape is converted to rest-space deltas through the seated skinning matrices and stored as
     the morph `sit_drape` on LOD0 (LOD1/LOD2 by nearest-vertex transfer);
  4. clips: cloth bones neutral in cage_sit and at the start of stand_up; morph weight 1 in cage_sit,
     1 -> 0 while rising in stand_up, 0 in every other clip; GLB + meta re-exported.

    python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/humans/v2/add_sit_drape.py <asset_id>
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))

import bpy  # noqa: E402
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Quaternion  # noqa: E402

from frlib import core, paths  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
AID = ARGS[0]
CLOTH = ("SkirtFront1", "SkirtFront2", "SkirtBack1", "SkirtBack2", "SkirtLeft", "SkirtRight", "Cloak1", "Cloak2")
FADE_FRAMES = 30          # stand_up: morph 1 -> 0 and cloth bones neutral -> secondary over the first second
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


def fcurves(act, arm):
    from bpy_extras import anim_utils
    slot = None
    for s in act.slots:
        if s.target_id_type == "OBJECT":
            slot = s
            break
    cb = anim_utils.action_get_channelbag_for_slot(act, slot) if slot else None
    return list(cb.fcurves) if cb else []


def neutralize(act, arm, frames_fade=None):
    """Cloth-bone quaternion keys -> identity (all frames), or blended to the original over frames_fade."""
    fcs = [fc for fc in fcurves(act, arm) if any(f'pose.bones["{b}"].rotation_quaternion' == fc.data_path for b in CLOTH)]
    by_bone = {}
    for fc in fcs:
        b = fc.data_path.split('"')[1]
        by_bone.setdefault(b, {})[fc.array_index] = fc
    for b, comps in by_bone.items():
        if len(comps) < 4:
            continue
        n = len(comps[0].keyframe_points)
        for k in range(n):
            f = comps[0].keyframe_points[k].co[0]
            q = Quaternion([comps[i].keyframe_points[k].co[1] for i in range(4)])
            if frames_fade is None:
                t = 0.0
            else:
                x = min(1.0, max(0.0, f / frames_fade))
                t = x * x * (3 - 2 * x)
            qq = Quaternion((1, 0, 0, 0)).slerp(q, t)
            for i in range(4):
                comps[i].keyframe_points[k].co[1] = qq[i]
        for fc in comps.values():
            fc.update()


def pose_at(arm, act, frame):
    arm.animation_data.action = act
    bpy.context.scene.frame_set(int(frame))
    return {pb.name: pb.matrix_basis.copy() for pb in arm.pose.bones}


def main():
    bpy.ops.wm.open_mainfile(filepath=paths.source("humans", f"{AID}.blend"))
    sc = bpy.context.scene
    arm = bpy.data.objects[f"{AID}_rig"]
    lods = [bpy.data.objects[f"{AID}_LOD{k}"] for k in range(3)]
    lo0 = lods[0]
    acts = {a.name: a for a in bpy.data.actions}
    sit, up = acts["lf_civilian_cage_sit"], acts["lf_civilian_stand_up"]
    if arm.animation_data is None:
        arm.animation_data_create()
    # ---- clips: neutral cloth bones while seated
    neutralize(sit, arm)
    neutralize(up, arm, FADE_FRAMES)
    # ---- cloth vertices of LOD0
    gi = {g.index: g.name for g in lo0.vertex_groups}
    nv = len(lo0.data.vertices)
    cw = np.zeros(nv)
    for v in lo0.data.vertices:
        for ge in v.groups:
            if gi[ge.group] in CLOTH:
                cw[v.index] += ge.weight
    cloth_v = cw > 0.03
    if cloth_v.sum() < 20:
        log("no cloth on", AID)
        return
    log("cloth vertices", int(cloth_v.sum()), "of", nv)
    # ---- sim object (cloth faces only) and collider (the rest)
    def dup(name):
        o = lo0.copy()
        o.data = lo0.data.copy()
        o.name = name
        sc.collection.objects.link(o)
        if o.data.shape_keys:
            o.shape_key_clear()
        return o
    sim = dup("_cloth_sim")
    col = dup("_cloth_collider")
    for o, keep_cloth in ((sim, True), (col, False)):
        a = o.data.attributes.new("orig_idx", "INT", "POINT")
        a.data.foreach_set("value", np.arange(nv, dtype=np.int32))
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.verts.ensure_lookup_table()
        kill = [f for f in bm.faces if all(cloth_v[v.index] for v in f.verts) != keep_cloth]
        bmesh.ops.delete(bm, geom=kill, context="FACES")
        bm.to_mesh(o.data)
        bm.free()
    oi = np.zeros(len(sim.data.vertices), np.int32)
    sim.data.attributes["orig_idx"].data.foreach_get("value", oi)
    pin = sim.vertex_groups.new(name="_pin")
    for j, i in enumerate(oi):
        pin.add([j], float(np.clip(1.0 - (cw[i] - 0.05) / 0.30, 0.0, 1.0)), "REPLACE")
    cm = sim.modifiers.new("Cloth", "CLOTH")
    st = cm.settings
    st.vertex_group_mass = "_pin"
    st.quality = 8
    st.mass = 0.25
    st.tension_stiffness = 14
    st.compression_stiffness = 14
    st.shear_stiffness = 6
    st.bending_stiffness = 0.6
    st.air_damping = 2.0
    cs = cm.collision_settings
    cs.use_collision = True
    cs.distance_min = 0.006
    cs.use_self_collision = False
    cm.point_cache.frame_start = 0
    cm.point_cache.frame_end = 110
    col.modifiers.new("Collision", "COLLISION")
    col.collision.thickness_outer = 0.006
    col.collision.cloth_friction = 8.0
    me = bpy.data.meshes.new("_floor")
    me.from_pydata([(-3, -3, 0), (3, -3, 0), (3, 3, 0), (-3, 3, 0)], [], [(0, 1, 2, 3)])
    floor = bpy.data.objects.new("_floor", me)
    sc.collection.objects.link(floor)
    floor.modifiers.new("Collision", "COLLISION")
    floor.collision.thickness_outer = 0.004
    floor.collision.cloth_friction = 10.0
    # ---- armature: standing -> seated (reverse stand_up, cloth bones neutral), then hold
    n_up = int(round(up.frame_range[1]))
    bases = [pose_at(arm, up, n_up - f) for f in range(n_up + 1)]
    seat = pose_at(arm, sit, 0)
    sim_act = bpy.data.actions.new("_sim_sitdown")
    arm.animation_data.action = sim_act
    seq = bases + [seat] * 45
    for f, B in enumerate(seq):
        for pb in arm.pose.bones:
            if pb.name not in B:
                continue
            m = Matrix.Identity(4) if pb.name in CLOTH else B[pb.name]
            pb.matrix_basis = m
            pb.keyframe_insert("rotation_quaternion", frame=f, group=pb.name)
            pb.keyframe_insert("location", frame=f, group=pb.name)
    last = len(seq) - 1
    cm.point_cache.frame_end = last
    sc.frame_start, sc.frame_end = 0, last
    for f in range(0, last + 1):
        sc.frame_set(f)
    deps = bpy.context.evaluated_depsgraph_get()
    ev = sim.evaluated_get(deps)
    mw = np.array(sim.matrix_world)
    draped = np.array([mw[:3, :3] @ np.array(v.co) + mw[:3, 3] for v in ev.data.vertices])
    log("simulated", len(draped), "cloth verts over", last, "frames")
    # ---- seated skinning matrices (cloth bones neutral) -> rest-space morph deltas
    arm.animation_data.action = sit
    sc.frame_set(0)
    bpy.context.view_layer.update()
    Bm = {}
    for pb in arm.pose.bones:
        Bm[pb.name] = np.array(pb.matrix) @ np.linalg.inv(np.array(arm.data.bones[pb.name].matrix_local))
    amw = np.array(arm.matrix_world)
    rest = np.array([v.co[:] for v in lo0.data.vertices])
    delta = np.zeros((nv, 3))
    for j, i in enumerate(oi):
        v = lo0.data.vertices[int(i)]
        M = np.zeros((4, 4))
        tot = 0.0
        for ge in v.groups:
            b = gi[ge.group]
            if b in Bm and ge.weight > 0:
                M += ge.weight * Bm[b]
                tot += ge.weight
        if tot <= 0:
            continue
        M /= tot
        M = amw @ M
        p = np.linalg.inv(M) @ np.append(draped[j], 1.0)
        d = p[:3] - rest[int(i)]
        n = np.linalg.norm(d)
        delta[int(i)] = d if n < 0.8 else d / n * 0.8
    log("morph |delta| max", round(float(np.linalg.norm(delta, axis=1).max()), 3), "m, mean over cloth",
        round(float(np.linalg.norm(delta[cloth_v], axis=1).mean()), 3))
    # ---- shape keys on all LODs
    from scipy.spatial import cKDTree
    tree = cKDTree(rest[cloth_v])
    dcl = delta[cloth_v]
    for k, o in enumerate(lods):
        if o.data.shape_keys is None:
            o.shape_key_add(name="Basis", from_mix=False)
        sk = o.data.shape_keys.key_blocks.get("sit_drape") or o.shape_key_add(name="sit_drape", from_mix=False)
        co = np.array([v.co[:] for v in o.data.vertices])
        if k == 0:
            d = delta
        else:
            gio = {g.index: g.name for g in o.vertex_groups}
            cwk = np.zeros(len(co))
            for v in o.data.vertices:
                for ge in v.groups:
                    if gio[ge.group] in CLOTH or gio[ge.group] in ("SkirtFront1", "SkirtBack1", "Cloak1"):
                        cwk[v.index] += ge.weight
            dist, idx = tree.query(co, k=3)
            w = 1.0 / np.maximum(dist, 1e-4)
            d = (dcl[idx] * w[..., None]).sum(1) / w.sum(1)[:, None]
            d[(cwk < 0.03) | (dist[:, 0] > 0.03)] = 0
        sk.data.foreach_set("co", (co + d).astype(np.float32).ravel())
        o.data.update()
    # ---- morph weight animation in every civilian clip
    for name, act in acts.items():
        if not name.startswith("lf_civilian_"):
            continue
        n = int(round(act.frame_range[1]))
        for o in lods:
            key = o.data.shape_keys
            if key.animation_data is None:
                key.animation_data_create()
            key.animation_data.action = act
            kb = key.key_blocks["sit_drape"]
            if name == "lf_civilian_cage_sit":
                keys = [(0, 1.0), (n, 1.0)]
            elif name == "lf_civilian_stand_up":
                keys = [(f, 1.0 - (lambda x: x * x * (3 - 2 * x))(min(1.0, f / FADE_FRAMES))) for f in range(0, FADE_FRAMES + 1, 3)] + [(n, 0.0)]
            else:
                keys = [(0, 0.0), (n, 0.0)]
            for f, val in keys:
                kb.value = val
                kb.keyframe_insert("value", frame=f)
    for o in lods:
        o.data.shape_keys.animation_data.action = None
        o.data.shape_keys.key_blocks["sit_drape"].value = 0.0
    # ---- clean up the simulation helpers
    for o in (sim, col, floor):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.actions.remove(sim_act)
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    # ---- re-export + meta
    out_glb = paths.runtime("humans", f"{AID}.glb")
    core.export_glb(out_glb, [arm] + lods,
                    extra=dict(export_force_sampling=True, export_optimize_animation_size=False,
                               export_image_format="AUTO", export_def_bones=True, export_animation_mode="ACTIONS",
                               export_bake_animation=False, export_morph=True, export_morph_normal=False,
                               export_morph_animation=True))
    log("GLB", out_glb, os.path.getsize(out_glb) // 1024, "KB")
    mp = paths.runtime("humans", f"{AID}.meta.json")
    meta = json.load(open(mp))
    meta["morphs"] = {"sit_drape": {
        "kind": "corrective cloth drape (Blender cloth sim: pinned waist/shoulders, body + floor collision)",
        "clips": {"lf_civilian_cage_sit": "1.0", "lf_civilian_stand_up": f"1 -> 0 over 0-{FADE_FRAMES / 30.0:.1f} s",
                  "other civilian clips": "0"},
        "note": "cloth bones are neutral while seated so bones and morph do not fight"}}
    core.write_json(mp, meta)
    blend = paths.source("humans", f"{AID}.blend")
    core.save_blend(blend)
    log("saved", blend)


if __name__ == "__main__":
    main()
