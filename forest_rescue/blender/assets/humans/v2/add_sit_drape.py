"""Seated cloth for the civilians: Blender cloth simulation baked into a corrective morph `sit_drape`.

For one character's .blend (built by build_v2.py --stage full):
  1. cloth = LOD0 faces skinned to the skirt / apron / cloak chain (SkirtFront*, SkirtBack*, SkirtLeft/Right,
     Cloak1/2); pinned where those weights fade out (waist band, shoulders);
  2. the armature plays stand_up in reverse at half speed (standing -> seated on the cage floor, cloth bones
     neutral) and then holds the seated pose; the cloth simulates against the body (collision) and the floor
     plane (the seat), so it drapes over the thighs and hangs between / over the knees;
  3. the settled drape is converted to rest-space deltas through the seated skinning matrices and stored as
     the morph `sit_drape` on LOD0 (LOD1/LOD2 by nearest-vertex transfer);
  4. clips: cloth bones neutral in cage_sit and while the morph is on in stand_up; morph weight 1 in cage_sit,
     1 -> 0 in stand_up as the thighs come down (driven by the thigh angle), 0 in every other clip (the morph
     curves live in the same actions, KEY slot, exported as glTF morph-weight channels);
  5. QA: draped cloth renders (front / side / 3/4) to qa/video/<id>/sit_drape_*.png; GLB + meta re-exported.

    python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/humans/v2/add_sit_drape.py <asset_id>
        [--src <blend>] [--dry <out_dir>]
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

from frlib import core, paths, render  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
AID = ARGS[0]
SRC = ARGS[ARGS.index("--src") + 1] if "--src" in ARGS else None
DRY = ARGS[ARGS.index("--dry") + 1] if "--dry" in ARGS else None
CLOTH = ("SkirtFront1", "SkirtFront2", "SkirtBack1", "SkirtBack2", "SkirtLeft", "SkirtRight", "Cloak1", "Cloak2")
SLOW = 2                  # simulated sit-down runs at half the clip speed (collision robustness)
HOLD = 50                 # frames held in the seated pose to settle
OFF_ANGLE = 38.0          # stand_up: morph reaches 0 when the thighs are this many degrees from vertical
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


def slot_of(act, id_type):
    for s in act.slots:
        if s.target_id_type == id_type:
            return s
    return None


def fcurves(act, id_type="OBJECT"):
    from bpy_extras import anim_utils
    slot = slot_of(act, id_type)
    cb = anim_utils.action_get_channelbag_for_slot(act, slot) if slot else None
    return list(cb.fcurves) if cb else []


def cloth_curves(act):
    by_bone = {}
    for fc in fcurves(act):
        for b in CLOTH:
            if fc.data_path == f'pose.bones["{b}"].rotation_quaternion':
                by_bone.setdefault(b, {})[fc.array_index] = fc
    return {b: c for b, c in by_bone.items() if len(c) == 4}


def neutralize(act, t_of_frame):
    """Cloth-bone quaternion keys -> slerp(identity, original, t(frame))."""
    for b, comps in cloth_curves(act).items():
        for k in range(len(comps[0].keyframe_points)):
            f = comps[0].keyframe_points[k].co[0]
            q = Quaternion([comps[i].keyframe_points[k].co[1] for i in range(4)])
            qq = Quaternion((1, 0, 0, 0)).slerp(q, t_of_frame(f))
            for i in range(4):
                comps[i].keyframe_points[k].co[1] = qq[i]
                comps[i].keyframe_points[k].handle_left[1] = qq[i]
                comps[i].keyframe_points[k].handle_right[1] = qq[i]
        for fc in comps.values():
            fc.update()


def pose_at(arm, act, frame):
    arm.animation_data.action = act
    arm.animation_data.action_slot = slot_of(act, "OBJECT")
    bpy.context.scene.frame_set(int(frame))
    return {pb.name: pb.matrix_basis.copy() for pb in arm.pose.bones}


def thigh_angle(arm):
    a = []
    for S in ("Left", "Right"):
        pb = arm.pose.bones.get(f"{S}UpperLeg")
        d = np.array(pb.matrix)[:3, 1]
        d = d / np.linalg.norm(d)
        a.append(math.degrees(math.acos(float(np.clip(-d[2], -1, 1)))))
    return max(a)


def snapshots(objs, out_dir, label, colors):
    """Workbench renders (front / side / 3/4) of the given objects, joined into one PNG."""
    from PIL import Image
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "OBJECT"
    sh.show_shadows = False
    sh.show_cavity = False
    hidden = {o.name: o.hide_render for o in sc.objects}
    for o in sc.objects:
        o.hide_render = o not in objs
    for o, c in zip(objs, colors):
        o.color = c
    tiles = []
    tgt = (0.0, 0.12, 0.40)
    for nm, loc in (("front", (0.0, -4.0, 0.55)), ("side", (4.0, 0.12, 0.55)), ("q34", (2.6, -2.6, 1.6)),
                    ("back", (0.0, 4.2, 0.9))):
        render.perspective_camera(loc, tgt, res=(420, 420), ortho_scale=1.45)
        tiles.append(render.render_rgba())
    for o in sc.objects:
        if o.name in hidden:
            o.hide_render = hidden[o.name]
    img = np.concatenate(tiles, axis=1)
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, f"{label}.png")
    Image.fromarray((np.clip(img[..., :3], 0, 1) * 255).astype(np.uint8)).save(p)
    return p


def skin_matrices(arm):
    return {pb.name: np.array(pb.matrix) @ np.linalg.inv(np.array(arm.data.bones[pb.name].matrix_local))
            for pb in arm.pose.bones}


def lbs(o, gi, Bm, idx):
    M = np.zeros((4, 4))
    tot = 0.0
    for ge in o.data.vertices[int(idx)].groups:
        b = gi[ge.group]
        if b in Bm and ge.weight > 0:
            M += ge.weight * Bm[b]
            tot += ge.weight
    return M / tot if tot > 0 else np.eye(4)


def main():
    src = SRC or paths.source("humans", f"{AID}.blend")
    bpy.ops.wm.open_mainfile(filepath=src)
    sc = bpy.context.scene
    arm = bpy.data.objects[f"{AID}_rig"]
    lods = [bpy.data.objects[f"{AID}_LOD{k}"] for k in range(3)]
    lo0 = lods[0]
    acts = {a.name: a for a in bpy.data.actions}
    sit, up = acts["lf_civilian_cage_sit"], acts["lf_civilian_stand_up"]
    if arm.animation_data is None:
        arm.animation_data_create()
    qa_dir = DRY or os.path.join(paths.QA_VIDEO, AID)
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
    # ---- stand_up timing from the thigh angle (before any edits)
    n_up = int(round(up.frame_range[1]))
    ang = []
    for f in range(n_up + 1):
        pose_at(arm, up, f)
        ang.append(thigh_angle(arm))
    ang = np.array(ang)
    a0, a1 = ang[0], ang[-1] + OFF_ANGLE
    x = np.clip((ang - a1) / max(a0 - a1, 1e-3), 0, 1)
    x = np.minimum.accumulate(x)               # monotone: never re-applies once fading
    w_up = x * x * (3 - 2 * x)
    f_off = int(np.argmax(w_up <= 0.0)) if (w_up <= 0.0).any() else n_up
    log("stand_up thigh angle", round(float(a0), 1), "->", round(float(ang[-1]), 1), "deg; morph off at frame", f_off)
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
        pin.add([j], float(np.clip(1.0 - (cw[i] - 0.05) / 0.25, 0.0, 1.0)), "REPLACE")
    cm = sim.modifiers.new("Cloth", "CLOTH")
    st = cm.settings
    st.vertex_group_mass = "_pin"
    st.quality = 10
    st.mass = 0.3
    st.tension_stiffness = 15
    st.compression_stiffness = 15
    st.shear_stiffness = 8
    st.bending_stiffness = 1.0
    st.air_damping = 1.5
    cs = cm.collision_settings
    cs.use_collision = True
    cs.collision_quality = 4
    cs.distance_min = 0.008
    cs.impulse_clamp = 0.0
    cs.use_self_collision = False
    col.modifiers.new("Collision", "COLLISION")
    col.collision.thickness_outer = 0.010
    col.collision.cloth_friction = 6.0
    col.collision.damping = 0.5
    me = bpy.data.meshes.new("_floor")
    me.from_pydata([(-3, -3, 0), (3, -3, 0), (3, 3, 0), (-3, 3, 0)], [], [(0, 1, 2, 3)])
    floor = bpy.data.objects.new("_floor", me)
    sc.collection.objects.link(floor)
    floor.modifiers.new("Collision", "COLLISION")
    floor.collision.thickness_outer = 0.006
    floor.collision.cloth_friction = 12.0
    # ---- armature: standing -> seated (reverse stand_up at half speed, cloth bones neutral), then hold
    bases = [pose_at(arm, up, n_up - f) for f in range(n_up + 1)]
    seat = pose_at(arm, sit, 0)
    sim_act = bpy.data.actions.new("_sim_sitdown")
    arm.animation_data.action = sim_act
    seq = [(f * SLOW, B) for f, B in enumerate(bases)]
    last_motion = n_up * SLOW
    seq += [(last_motion + 6, seat), (last_motion + 6 + HOLD, seat)]
    for f, B in seq:
        for pb in arm.pose.bones:
            if pb.name not in B:
                continue
            pb.matrix_basis = Matrix.Identity(4) if pb.name in CLOTH else B[pb.name]
            pb.keyframe_insert("rotation_quaternion", frame=f, group=pb.name)
            pb.keyframe_insert("location", frame=f, group=pb.name)
    last = seq[-1][0]
    cm.point_cache.frame_start = 0
    cm.point_cache.frame_end = last
    sc.frame_start, sc.frame_end = 0, last
    mw = np.array(sim.matrix_world)
    snaps = {int(last_motion * 0.5), last_motion, last}
    for f in range(0, last + 1):
        sc.frame_set(f)
        if DRY and f in snaps:
            snapshots([sim, col, floor], DRY, f"{AID}_sim_f{f:03d}", [(0.25, 0.55, 0.95, 1), (0.8, 0.8, 0.8, 1),
                                                                      (0.35, 0.3, 0.25, 1)])
    deps = bpy.context.evaluated_depsgraph_get()
    ev = sim.evaluated_get(deps)
    draped = np.array([mw[:3, :3] @ np.array(v.co) + mw[:3, 3] for v in ev.data.vertices])
    log("simulated", len(draped), "cloth verts over", last, "frames; z range", round(float(draped[:, 2].min()), 3),
        round(float(draped[:, 2].max()), 3))
    # ---- seated skinning matrices (cloth bones neutral) -> rest-space morph deltas
    arm.animation_data.action = sim_act
    sc.frame_set(last)
    bpy.context.view_layer.update()
    Bm = skin_matrices(arm)
    amw = np.array(arm.matrix_world)
    omw = np.array(lo0.matrix_world)
    to_arm = np.linalg.inv(amw) @ omw          # mesh space -> armature space
    rest = np.array([v.co[:] for v in lo0.data.vertices])
    delta = np.zeros((nv, 3))
    posed = np.zeros((nv, 3))
    for j, i in enumerate(oi):
        M = np.linalg.inv(to_arm) @ lbs(lo0, gi, Bm, i) @ to_arm      # mesh-space skinning
        posed[int(i)] = (M @ np.append(rest[int(i)], 1.0))[:3]
        p = np.linalg.inv(omw) @ np.append(draped[j], 1.0)          # world -> mesh space
        q = np.linalg.inv(M) @ p
        delta[int(i)] = q[:3] - rest[int(i)]
    dn = np.linalg.norm(delta, axis=1)
    log("morph |delta| max", round(float(dn.max()), 3), "m, mean over cloth", round(float(dn[cloth_v].mean()), 3),
        "p95", round(float(np.percentile(dn[cloth_v], 95)), 3))
    if DRY:
        snapshots([sim, col, floor], DRY, f"{AID}_sim_final", [(0.25, 0.55, 0.95, 1), (0.8, 0.8, 0.8, 1),
                                                                (0.35, 0.3, 0.25, 1)])
        return
    # ---- clips: neutral cloth bones while seated / while the morph is on
    neutralize(sit, lambda f: 0.0)
    neutralize(up, lambda f: float(np.clip((f - f_off) / 8.0, 0, 1)) ** 2 * (3 - 2 * float(np.clip((f - f_off) / 8.0, 0, 1))))
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
                    if gio[ge.group] in CLOTH:
                        cwk[v.index] += ge.weight
            dist, idx = tree.query(co, k=3)
            w = 1.0 / np.maximum(dist, 1e-4)
            d = (dcl[idx] * w[..., None]).sum(1) / w.sum(1)[:, None]
            d[(cwk < 0.03) | (dist[:, 0] > 0.03)] = 0
        sk.data.foreach_set("co", (co + d).astype(np.float32).ravel())
        o.data.update()
    # ---- morph weight curves in every civilian clip (KEY slot of the same action) + NLA strips for export
    for o in lods:
        key = o.data.shape_keys
        if key.animation_data is None:
            key.animation_data_create()
    key_slot = {}
    for name, act in sorted(acts.items()):
        if not name.startswith("lf_civilian_"):
            continue
        n = int(round(act.frame_range[1]))
        if name == "lf_civilian_cage_sit":
            keys = [(0, 1.0), (n, 1.0)]
        elif name == "lf_civilian_stand_up":
            keys = [(f, float(w_up[f])) for f in range(0, min(f_off + 2, n) + 1, 2)] + [(n, 0.0)]
        else:
            keys = [(0, 0.0), (n, 0.0)]
        for o in lods:
            key = o.data.shape_keys
            key.animation_data.action = act
            if name in key_slot:
                key.animation_data.action_slot = key_slot[name]
            kb = key.key_blocks["sit_drape"]
            for f, val in keys:
                kb.value = val
                kb.keyframe_insert("value", frame=f)
            key_slot[name] = key.animation_data.action_slot
    for o in lods:
        ad = o.data.shape_keys.animation_data
        ad.action = None
        for tr in list(ad.nla_tracks):
            ad.nla_tracks.remove(tr)
        for name, act in sorted(acts.items()):
            if name not in key_slot:
                continue
            tr = ad.nla_tracks.new()
            tr.name = name
            stp = tr.strips.new(name, 0, act)
            stp.action_slot = key_slot[name]
            tr.mute = True       # Blender playback stays clean; the glTF exporter still reads single-strip tracks
        o.data.shape_keys.key_blocks["sit_drape"].value = 0.0
    # ---- verify: LOD0 with the morph at weight 1 in the seated pose reproduces the simulation
    arm.animation_data.action = sit
    arm.animation_data.action_slot = slot_of(sit, "OBJECT")
    lo0.data.shape_keys.key_blocks["sit_drape"].value = 1.0
    sc.frame_set(0)
    deps = bpy.context.evaluated_depsgraph_get()
    e0 = lo0.evaluated_get(deps)
    got = np.array([e0.data.vertices[int(i)].co[:] for i in oi])
    want = np.array([(np.linalg.inv(omw) @ np.append(p, 1.0))[:3] for p in draped])
    err = np.linalg.norm(got - want, axis=1)
    log("check: seated LOD0 + sit_drape vs simulation: mean", round(float(err.mean()) * 1000, 1), "mm, max",
        round(float(err.max()) * 1000, 1), "mm")
    lo0.data.shape_keys.key_blocks["sit_drape"].value = 0.0
    snapshots([sim, col, floor], qa_dir, "sit_drape_sim", [(0.25, 0.55, 0.95, 1), (0.8, 0.8, 0.8, 1), (0.35, 0.3, 0.25, 1)])
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
                               export_morph_animation=True, export_merge_animation="ACTION"))
    log("GLB", out_glb, os.path.getsize(out_glb) // 1024, "KB")
    mp = paths.runtime("humans", f"{AID}.meta.json")
    meta = json.load(open(mp))
    meta["morphs"] = {"sit_drape": {
        "kind": "corrective cloth drape baked from a Blender cloth simulation (pinned at the waist / shoulders, "
                "body + cage-floor collision), stored relative to the posed rest shape",
        "clips": {"lf_civilian_cage_sit": "1.0",
                  "lf_civilian_stand_up": f"1 -> 0 over 0-{f_off / 30.0:.2f} s as the thighs come down",
                  "other civilian clips": "0"},
        "cloth_bones": "neutral while the morph is on (cage_sit; stand_up until the morph is off, then blended back)",
        "mean_delta_m": round(float(dn[cloth_v].mean()), 3)}}
    core.write_json(mp, meta)
    blend = paths.source("humans", f"{AID}.blend")
    core.save_blend(blend)
    log("saved", blend)


if __name__ == "__main__":
    main()
