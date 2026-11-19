"""Finish stage of a v2 human: armature, skin weights (already on the parts), LOD1/2, the clip set,
foot-slip / loop checks, GLB + meta export, .blend master."""
import json
import math
import os

import bpy
import numpy as np
from mathutils import Matrix

from frlib import core, paths
import hv2_rig as HR
import hv2_anim as HA
import hv2_clips as HC

GROUP = "humans"
PAINTED_LIGHT_MIX = 0.40


def export_materials(aid, img_path):
    img = core.load_image(img_path)
    mats = []
    for nm, rough in (("body", 0.86), ("hair", 0.80), ("cloth", 0.90), ("gear", 0.72)):
        m = core.material(f"{aid}_{nm}", base_tex=img, rough=rough)
        bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        bsdf.inputs["Specular IOR Level"].default_value = 0.15
        mats.append(m)
    return mats


def parent_to(obj, arm):
    for m in list(obj.modifiers):
        if m.type == "ARMATURE":
            obj.modifiers.remove(m)
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    obj.parent = arm
    obj.matrix_parent_inverse = arm.matrix_world.inverted()


def lod_copy(src, target, keep, name):
    o = core.decimate_to(src, target, name=name)
    for m in list(o.modifiers):
        if m.type != "ARMATURE":
            o.modifiers.remove(m)
    names, M = HR.read_groups(o)
    names2, M2 = HR.remap(names, M, set(keep))
    HR.assign_groups(o, names2, M2)
    return o


def used_bones(obj):
    names, M = HR.read_groups(obj)
    return sorted(n for j, n in enumerate(names) if (M[:, j] > 0).any())


def write_action(arm, name, frames_basis, times, loop, ik_keys=None):
    act = bpy.data.actions.get(name)
    if act:
        bpy.data.actions.remove(act)
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act
    for fi, (t, fb) in enumerate(zip(times, frames_basis)):
        f = float(round(t * HA.FPS))
        for bname, (loc, q, sc) in fb.items():
            pb = arm.pose.bones.get(bname)
            if pb is None or bname == "Root":
                continue
            pb.rotation_quaternion = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
            pb.keyframe_insert("rotation_quaternion", frame=f, group=bname)
            if bname == "Hips" or np.abs(loc).max() > 1e-5:
                pb.location = tuple(float(x) for x in loc)
                pb.keyframe_insert("location", frame=f, group=bname)
            if bname in ("PropR", "PropL"):
                pb.scale = (float(sc),) * 3
                pb.keyframe_insert("scale", frame=f, group=bname)
        if ik_keys is not None:
            for bname, loc in ik_keys[fi].items():
                pb = arm.pose.bones.get(bname)
                if pb is None:
                    continue
                pb.location = tuple(float(x) for x in loc)
                pb.keyframe_insert("location", frame=f, group=bname)
    try:
        from bpy_extras import anim_utils
        cbag = anim_utils.action_get_channelbag_for_slot(act, arm.animation_data.action_slot)
        fcs = list(cbag.fcurves) if cbag else []
    except Exception:
        fcs = list(getattr(act, "fcurves", []))
    for fc in fcs:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    act.use_frame_range = True
    act.frame_start = 0.0
    act.frame_end = float(round(times[-1] * HA.FPS))
    act.use_cyclic = bool(loop)
    act["loop"] = bool(loop)
    act["seconds"] = float(times[-1])
    return act


def secondary(sk, params, Ms, loop, kind_info):
    """Cloth bones from the solved poses: skirts follow the thighs (front = forward-most thigh,
    back = rear-most), with lag; cloak/hood lag behind the torso; bag swings with the pelvis."""
    n = len(Ms)
    th = {S: np.zeros(n) for S in ("Left", "Right")}
    ab = {S: np.zeros(n) for S in ("Left", "Right")}
    hipv = np.zeros((n, 3))
    tor = np.zeros(n)
    for i, M in enumerate(Ms):
        for S, sx in (("Left", 1.0), ("Right", -1.0)):
            d = M[f"{S}UpperLeg"][:3, 1]
            d0 = sk.R[f"{S}UpperLeg"][:3, 1]
            th[S][i] = math.atan2(-d[1], -d[2]) - math.atan2(-d0[1], -d0[2])
            ab[S][i] = (math.atan2(d[0] * sx, -d[2]) - math.atan2(d0[0] * sx, -d0[2]))
        hipv[i] = M["Hips"][:3, 3]
        up = M["UpperChest"][:3, 1]
        tor[i] = math.atan2(-up[1], up[2])
    front = np.maximum(np.maximum(th["Left"], th["Right"]), 0)
    back = np.maximum(np.maximum(-th["Left"], -th["Right"]), 0)
    side_l = np.maximum(ab["Left"], 0)
    side_r = np.maximum(ab["Right"], 0)

    def lag(x, a=0.35):
        y = np.zeros_like(x)
        if loop:
            reps = np.concatenate([x, x, x])
            yy = np.zeros_like(reps)
            for i in range(1, len(reps)):
                yy[i] = yy[i - 1] + a * (reps[i] - yy[i - 1])
            return yy[len(x):2 * len(x)]
        y[0] = x[0]
        for i in range(1, len(x)):
            y[i] = y[i - 1] + a * (x[i] - y[i - 1])
        return y
    acc = np.gradient(np.gradient(hipv[:, 1])) * HA.FPS * HA.FPS
    out = []
    for i in range(n):
        out.append({})
    f1 = lag(front, 0.45) * 0.85
    f2 = lag(front, 0.25) * 0.25
    b1 = lag(back, 0.45) * 0.8
    b2 = lag(back, 0.25) * 0.25
    sl = lag(side_l, 0.4) * 0.8
    sr = lag(side_r, 0.4) * 0.8
    tl = lag(tor, 0.2) - tor
    bag = lag(np.clip(acc * 0.004, -0.4, 0.4), 0.2)
    for i in range(n):
        R = out[i]
        # +X rotation swings a hanging bone backward (+Y): front panels use -angle
        R["SkirtFront1"] = HA.rot(HA.X, -f1[i])
        R["SkirtFront2"] = HA.rot(HA.X, -f2[i])
        R["SkirtBack1"] = HA.rot(HA.X, b1[i])
        R["SkirtBack2"] = HA.rot(HA.X, b2[i])
        R["SkirtLeft"] = HA.rot(HA.X, -0.6 * max(th["Left"][i], 0.0)) @ HA.rot(HA.Y, -sl[i])
        R["SkirtRight"] = HA.rot(HA.X, -0.6 * max(th["Right"][i], 0.0)) @ HA.rot(HA.Y, sr[i])
        R["Cloak1"] = HA.rot(HA.X, -0.6 * tl[i] - 0.4 * b1[i] * 0.3)
        R["Cloak2"] = HA.rot(HA.X, -0.8 * tl[i] - 0.5 * b1[i] * 0.3)
        R["Hood"] = HA.rot(HA.X, -0.5 * tl[i])
        R["Bag"] = HA.rot(HA.X, bag[i])
    return out


def foot_slip(sk, cx, Ms, contacts, times, speed):
    res = {}
    for S in ("Left", "Right"):
        heel_l = np.linalg.inv(sk.R[f"{S}Foot"]) @ np.append(cx.heel[S], 1.0)
        ball_g = np.array([cx.ball[S][0], cx.ball[S][1], 0.0])
        ball_l = np.linalg.inv(sk.R[f"{S}Foot"]) @ np.append(ball_g, 1.0)
        segs, cur, kind = [], [], None
        for i, (M, c) in enumerate(zip(Ms, contacts)):
            planted, _, k = c.get(S, (False, None, None))
            if planted:
                travel = np.array([0, -speed * times[i], 0])
                pt = (M[f"{S}Foot"] @ (heel_l if k in ("heel", "flat") else ball_l))[:3] + travel
                if k != kind and cur:
                    segs.append(cur)
                    cur = []
                kind = k
                cur.append(pt[:2])
            elif cur:
                segs.append(cur)
                cur, kind = [], None
        if cur:
            segs.append(cur)
        slip = 0.0
        for sgm in segs:
            a = np.array(sgm)
            slip = max(slip, float(np.linalg.norm(a - a[0], axis=1).max()))
        res[S] = round(slip * 1000.0, 2)
    return res


def finish(AID, C, R, J, B, lo0, p_png, ITER, log):
    kind = C["kind"]
    # ---- armature
    T = B["T"]
    ginfo = B.get("ginfo", {})
    specs = HR.bone_specs(J, B["hand_bones"], T, ginfo)
    arm = HR.build_armature(f"{AID}_rig", specs)
    deform = [b["name"] for b in specs if b["deform"]]
    log("bones", len(arm.data.bones), "deform", len(deform))
    # ---- export materials
    mats = export_materials(AID, p_png.replace("_color_master.png", "_color.jpg") if os.path.exists(
        p_png.replace("_color_master.png", "_color.jpg")) else p_png)
    lo0.data.materials.clear()
    for m in mats:
        lo0.data.materials.append(m)
    lo0.name = f"{AID}_LOD0"
    lo0.data.name = f"{AID}_LOD0"
    names, M = HR.read_groups(lo0)
    keep0 = set(deform)
    n0, M0 = HR.remap(names, M, keep0)
    HR.assign_groups(lo0, n0, M0)
    # ---- hand-held weapons (squad): own small material, rigid on PropR / PropL
    weapon = C.get("weapon")
    if weapon:
        import hv2_props as HP
        atlas = paths.texture_master(GROUP, f"{AID}_props.jpg")
        HP.build_atlas(atlas)
        pm = core.material(f"{AID}_prop", base_tex=core.load_image(atlas), rough=0.6)
        kinds = {"sword": ["sword"], "spear": ["spear", "shield"], "bow": ["bow"]}[weapon]
        pobjs = []
        for kd in kinds:
            for nm, V, Fc, vuv, bone in HP.build(kd, B["hand_bones"], J):
                luv = HP._loops_uv(Fc, vuv)
                ob = core.mesh_object(f"{AID}_{nm}", V, Fc, uvs=luv)
                ob.data.materials.append(mats[0])
                ob.data.materials.append(mats[1])
                ob.data.materials.append(mats[2])
                ob.data.materials.append(mats[3])
                ob.data.materials.append(pm)
                ob.data.polygons.foreach_set("material_index", np.full(len(ob.data.polygons), 4, np.int32))
                HR.groups_from_dicts(ob, [{bone: 1.0}] * len(V))
                pobjs.append(ob)
        if pobjs:
            lo0.data.materials.append(pm)
            # UV map names must match for join
            for ob in pobjs:
                ob.data.uv_layers[0].name = lo0.data.uv_layers.active.name
            lo0 = core.join([lo0] + pobjs, name=f"{AID}_LOD0")
            mats.append(pm)
            log("props", kinds, core.tri_count(lo0), "tris with props")
    parent_to(lo0, arm)
    budget = {"civilian": (12000, 6000, 2200), "soldier": (14000, 7000, 2500)}[kind]
    lod1 = lod_copy(lo0, int(budget[1] * 0.97), HR.LOD1_KEEP, f"{AID}_LOD1")
    lod2 = lod_copy(lo0, int(budget[2] * 0.97), HR.LOD2_KEEP, f"{AID}_LOD2")
    for o in (lod1, lod2):
        parent_to(o, arm)
    lods = {0: lo0, 1: lod1, 2: lod2}
    for k, o in lods.items():
        log(f"LOD{k}", core.tri_count(o), "tris", len(used_bones(o)), "bones")
    # ---- clips
    sk = HA.Skel(arm)
    weapon = C.get("weapon")
    cx = HC.Ctx(sk, C, J, T, kind, weapon)
    clips = HC.build_clips(cx)
    meta_clips = {}
    ik_bones = {}
    for name, sec, loop, params, contacts, extra in clips:
        times = HC.frames_for(sec)
        HA.OVERREACH[0] = 0.0
        poses = [HC.make_pose(cx, p) for p in params]
        sol = [HA.solve(sk, P) for P in poses]
        Ms = [m for _, m in sol]
        sec_rots = secondary(sk, params, Ms, loop, ginfo)
        frames_basis = []
        final_M = []
        ikk = []
        for P, extra_r in zip(poses, sec_rots):
            for bn, Rr in extra_r.items():
                P.rot[bn] = Rr
            bb, MM = HA.solve(sk, P)
            # cloth never goes through the floor: swing skirt/cloak chains outward until the tail
            # clears z = 0.03 (seated / kneeling / fallen poses)
            fixed = False
            for bn, axis, sgn in (("SkirtFront1", HA.X, -1), ("SkirtBack1", HA.X, 1), ("SkirtLeft", HA.X, 1),
                                  ("SkirtRight", HA.X, 1), ("Cloak1", HA.X, 1)):
                head = MM[bn][:3, 3]
                tail = head + MM[bn][:3, 1] * sk.length[bn]
                if tail[2] < 0.03:
                    L = sk.length[bn]
                    need = math.acos(np.clip((head[2] - 0.03) / max(L, 1e-6), -1, 1))
                    cur = math.acos(np.clip(-(MM[bn][:3, 1])[2], -1, 1))
                    lift = max(0.0, need - cur) + 0.05
                    P.rot[bn] = HA.rot(axis, sgn * lift) @ P.rot.get(bn, np.eye(3))
                    fixed = True
            if fixed:
                bb, MM = HA.solve(sk, P)
            frames_basis.append(bb)
            final_M.append(MM)
            ikk.append({f"IK_Foot_{s}": MM[f"{S}Foot"][:3, 3] - sk.head(f"{S}Foot") for S, s in (("Left", "L"), ("Right", "R"))} |
                       {f"IK_Hand_{s}": MM[f"{S}Hand"][:3, 3] - sk.head(f"{S}Hand") for S, s in (("Left", "L"), ("Right", "R"))})
        if loop:
            frames_basis[-1] = frames_basis[0]
            final_M[-1] = final_M[0]
            ikk[-1] = ikk[0]
        write_action(arm, name, frames_basis, times, loop, ikk)
        speed = float(extra.get("groundSpeed_mps", 0.0)) if extra else 0.0
        m = {"seconds": round(float(sec), 4), "loop": bool(loop), "rootTranslation": "in_place"}
        if speed > 0:
            m["groundSpeed_mps"] = speed
            m["strideLength_m"] = float(extra.get("strideLength_m", speed * sec))
        if extra and extra.get("markers"):
            m["markers"] = extra["markers"]
        else:
            m["markers"] = {}
        if speed <= 0:
            # standing / acting clips: a foot counts as planted while its ankle target is still
            # (deliberate steps - lunge, recoil, death fall - are excluded from the slip figure)
            contacts = []
            for i in range(len(params)):
                c = {}
                for s_, S_ in (("l", "Left"), ("r", "Right")):
                    a0 = np.array([params[max(i - 1, 0)][f"{s_}_f{k}"] for k in "xyz"])
                    a1 = np.array([params[min(i + 1, len(params) - 1)][f"{s_}_f{k}"] for k in "xyz"])
                    still = np.linalg.norm(a1 - a0) * HA.FPS / 2 < 0.03 and params[i][f"{s_}_fz"] < 0.01
                    c[S_] = (bool(still), None, "flat")
                contacts.append(c)
        slip = foot_slip(sk, cx, final_M, contacts, times, speed)
        m["footSlip_mm"] = slip
        m["ikOverreach_m"] = round(max(HA.OVERREACH[0], 0.0), 4)
        if loop:
            q0 = np.concatenate([frames_basis[0][n][1] for n in sorted(frames_basis[0])])
            q1 = np.concatenate([frames_basis[-1][n][1] for n in sorted(frames_basis[-1])])
            m["loopSeamMaxQuatDiff"] = float(np.abs(q0 - q1).max())
        meta_clips[name] = m
        log(f"clip {name}: {sec}s loop={loop} slip(mm)={slip} overreach={m['ikOverreach_m']}")
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    # ---- export
    out_glb = paths.runtime(GROUP, f"{AID}.glb")
    core.export_glb(out_glb, [arm, lods[0], lods[1], lods[2]],
                    extra=dict(export_force_sampling=True, export_optimize_animation_size=False,
                               export_image_format="AUTO", export_def_bones=True,
                               export_animation_mode="ACTIONS", export_bake_animation=False))
    log("GLB", out_glb, os.path.getsize(out_glb) // 1024, "KB")
    mins, maxs = core.bounds([lods[0]])
    meta = {
        "id": AID,
        "generation": "v2 image-based (painted turnaround silhouettes + template depth, painting projection)",
        "rig": "human_shared",
        "tris": {f"LOD{k}": core.tri_count(o) for k, o in lods.items()},
        "budget": {"LOD0": budget[0], "LOD1": budget[1], "LOD2": budget[2]},
        "bones": {"deform": len(deform), "total": len(arm.data.bones),
                  "weightedByLOD": {f"LOD{k}": len(used_bones(o)) for k, o in lods.items()},
                  "maxInfluences": 4, "names": deform},
        "nodes": {f"LOD{k}": o.name for k, o in lods.items()},
        "materials": [m.name for m in mats],
        "paintedLightMix": PAINTED_LIGHT_MIX,
        "shading": "albedo * mix(1, lambert(sun), paintedLightMix): the atlas carries the painted light",
        "textures": {os.path.basename(p_png).replace("_color_master.png", "_color.jpg"): 2048},
        "bounds_m": {"min": [round(float(x), 3) for x in mins], "max": [round(float(x), 3) for x in maxs]},
        "clips": meta_clips,
        "sockets": {"hand_r": [round(float(x), 3) for x in sk.head("PropR")],
                    "hand_l": [round(float(x), 3) for x in sk.head("PropL")],
                    "head_top": [0.0, round(float(J["HeadTop"][2]), 3), 0.0]},
        "variants": B.get("variant_info", {}),
        "coordinateConvention": {"up": "+Y", "forward": "+Z", "unit": "metre",
                                 "note": "Blender -Y forward exported to glTF +Z; feet on y=0, root at the origin"},
        "notes": C.get("notes", ""),
    }
    # glTF sockets: Blender (x, y, z) -> glTF (x, z, -y)
    for k, v in list(meta["sockets"].items()):
        if k != "head_top":
            meta["sockets"][k] = [v[0], v[2], -v[1]]
    core.write_json(paths.runtime(GROUP, f"{AID}.meta.json"), meta)
    blend = paths.source(GROUP, f"{AID}.blend")
    core.save_blend(blend)
    log("saved", blend)
    return meta, arm, lods, cx, clips
