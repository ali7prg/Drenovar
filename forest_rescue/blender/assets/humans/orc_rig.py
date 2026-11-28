"""Finish stage of lf_orc_warden: `human_shared` armature (hv2_rig.bone_specs - identical names /
hierarchy / roll conventions to the v2 humans), skin weights, glow split, LOD1/LOD2, the 10 orc clips
(orc_clips, solved by hv2_anim with hv2_finish cloth secondaries), GLB + meta export, .blend master,
posed QA stills and clip videos with contact sheets."""
import json
import math
import os
import shutil
import subprocess
import tempfile

import bmesh
import bpy
import numpy as np
from mathutils import Matrix

import hv2_anim as HA
import hv2_clips as HC
import hv2_finish as HF
import hv2_rig as HR
import orc_build as OB
import orc_clips as OC
import orc_geo as G
import orc_qa as OQ
import spec_lf_orc_warden as SP
from frlib import core, paths

log = OB.log
ID = SP.ID


def extract(src, keep_faces, name):
    o = src.copy()
    o.data = src.data.copy()
    core.link(o)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f, k in zip(bm.faces, keep_faces) if not k], context="FACES")
    bm.to_mesh(o.data)
    bm.free()
    o.name = name
    o.data.name = name
    return o


def split_glow(lo0):
    gi = SP.MATERIALS.index("glow")
    mi = np.array([p.material_index for p in lo0.data.polygons])
    glow = extract(lo0, mi == gi, f"{ID}_glow_LOD0")
    body = extract(lo0, mi != gi, f"{ID}_LOD0")
    old_me = lo0.data
    bpy.data.objects.remove(lo0, do_unlink=True)
    bpy.data.meshes.remove(old_me)
    body.name = f"{ID}_LOD0"
    body.data.name = f"{ID}_LOD0"
    return body, glow


def copy_obj(src, name):
    names, M = HR.read_groups(src)
    o = src.copy()
    o.data = src.data.copy()
    core.link(o)
    o.name = name
    o.data.name = name
    log("copy", src.name, "->", name, "groups", len(names), "verts", len(o.data.vertices))
    if names:
        HR.assign_groups(o, names, M)
    return o


def remap_groups(o, keep):
    names, M = HR.read_groups(o)
    n2, M2 = HR.remap(names, M, set(keep))
    HR.assign_groups(o, n2, M2)


def world_slip(sk, M_list, contacts, times, yaw_fn):
    """Planted-foot drift (mm) in the yawed world frame (turn clips)."""
    res = {}
    for S in ("Left", "Right"):
        seg, worst = [], 0.0
        for M, c, t in zip(M_list, contacts, times):
            if c.get(S, (False,))[0]:
                Rz = HA.rot(HA.Z, math.radians(yaw_fn(t)))
                seg.append((Rz @ M[f"{S}Foot"][:3, 3])[:2])
            elif seg:
                a = np.array(seg)
                worst = max(worst, float(np.linalg.norm(a - a[0], axis=1).max()))
                seg = []
        if seg:
            a = np.array(seg)
            worst = max(worst, float(np.linalg.norm(a - a[0], axis=1).max()))
        res[S] = round(worst * 1000.0, 2)
    return res


def bake_clips(arm, cx, ginfo):
    sk = cx.sk
    clips = OC.build_clips(cx)
    meta = {}
    for name, sec, loop, params, contacts, extra in clips:
        times = HC.frames_for(sec)
        HA.OVERREACH[0] = 0.0
        HC._FKW.clear()
        poses = [OC.make_pose(cx, p) for p in params]
        Ms = [HA.solve(sk, P)[1] for P in poses]
        sec_rots = HF.secondary(sk, params, Ms, loop, ginfo)
        frames_basis, final_M, ikk = [], [], []
        for P, extra_r in zip(poses, sec_rots):
            for bn, Rr in extra_r.items():
                P.rot[bn] = Rr @ P.rot.get(bn, np.eye(3))
            bb, MM = HA.solve(sk, P)
            fixed = False
            for bn, axis, sgn in (("SkirtFront1", HA.X, -1), ("SkirtBack1", HA.X, 1), ("SkirtLeft", HA.X, 1),
                                  ("SkirtRight", HA.X, 1), ("Cloak1", HA.X, 1)):
                head = MM[bn][:3, 3]
                tail = head + MM[bn][:3, 1] * sk.length[bn]
                if tail[2] < 0.03:
                    L = sk.length[bn]
                    need = math.acos(np.clip((head[2] - 0.03) / max(L, 1e-6), -1, 1))
                    cur = math.acos(np.clip(-(MM[bn][:3, 1])[2], -1, 1))
                    P.rot[bn] = HA.rot(axis, sgn * (max(0.0, need - cur) + 0.05)) @ P.rot.get(bn, np.eye(3))
                    fixed = True
            if fixed:
                bb, MM = HA.solve(sk, P)
            frames_basis.append(bb)
            final_M.append(MM)
            ikk.append({f"IK_Foot_{s}": MM[f"{S}Foot"][:3, 3] - sk.head(f"{S}Foot") for S, s in (("Left", "L"), ("Right", "R"))}
                       | {f"IK_Hand_{s}": MM[f"{S}Hand"][:3, 3] - sk.head(f"{S}Hand") for S, s in (("Left", "L"), ("Right", "R"))})
        worst = {}
        for i, (P, MM) in enumerate(zip(poses, final_M)):
            for S_, A_ in P.arm.items():
                if A_.get("wrist") is None:
                    continue
                L_ = sk.length[f"{S_}UpperArm"] + sk.length[f"{S_}LowerArm"]
                ex = float(np.linalg.norm(np.asarray(A_["wrist"]) - MM[f"{S_}UpperArm"][:3, 3]) - L_)
                if ex > worst.get(S_, (-9, 0))[0]:
                    worst[S_] = (ex, i)
        if any(v[0] > 0.01 for v in worst.values()):
            log(f"  arm overreach {name}: " + ", ".join(f"{k} {v[0]:.3f} m at frame {v[1]}" for k, v in worst.items()))
        if loop:
            frames_basis[-1] = frames_basis[0]
            final_M[-1] = final_M[0]
            ikk[-1] = ikk[0]
        HF.write_action(arm, name, frames_basis, times, loop, ikk)
        speed = float(extra.get("groundSpeed_mps", 0.0))
        m = {"seconds": round(float(sec), 4), "loop": bool(loop), "rootTranslation": "in_place"}
        if speed > 0:
            m["groundSpeed_mps"] = speed
            m["strideLength_m"] = float(extra.get("strideLength_m", speed * sec))
        for k in ("rootYawDeg", "yawCurve"):
            if k in extra:
                m[k] = extra[k]
        m["markers"] = dict(extra.get("markers", {}))
        if "rootYawDeg" in extra:
            yaw = float(extra["rootYawDeg"])
            slip = world_slip(sk, final_M, contacts, times, lambda t: yaw * float(HA.smooth(t / sec)))
        else:
            if speed <= 0:
                contacts = []
                for i in range(len(params)):
                    c = {}
                    for s_, S_ in (("l", "Left"), ("r", "Right")):
                        a0 = np.array([params[max(i - 1, 0)][f"{s_}_f{k}"] for k in "xyz"])
                        a1 = np.array([params[min(i + 1, len(params) - 1)][f"{s_}_f{k}"] for k in "xyz"])
                        still = np.linalg.norm(a1 - a0) * HA.FPS / 2 < 0.03 and params[i][f"{s_}_fz"] < 0.01
                        c[S_] = (bool(still), None, "flat")
                    contacts.append(c)
            slip = HF.foot_slip(sk, cx, final_M, contacts, times, speed)
        m["footSlip_mm"] = slip
        m["ikOverreach_m"] = round(max(HA.OVERREACH[0], 0.0), 4)
        if loop:
            q0 = np.concatenate([frames_basis[0][n][1] for n in sorted(frames_basis[0])])
            q1 = np.concatenate([frames_basis[-1][n][1] for n in sorted(frames_basis[-1])])
            m["loopSeamMaxQuatDiff"] = float(np.abs(q0 - q1).max())
        # staff foot height (must stay above the ground) and planted-staff drift
        stf = cx.staff
        bottoms = []
        for MM in final_M:
            Mp = MM["PropR"] @ np.linalg.inv(stf.Mprop0)
            bottoms.append((Mp[:3, :3] @ (stf.g0 - stf.u0 * OC.GRIP) + Mp[:3, 3]))
        bottoms = np.array(bottoms)
        m["staffFootMinZ_m"] = round(float(bottoms[:, 2].min()), 4)
        i = int(np.argmin(bottoms[:, 2]))
        if bottoms[i, 2] < 0.0:
            p = params[i]
            exp = stf.apply(p, stf.g0 - stf.u0 * OC.GRIP) if p.get("st_r", 0) > 0 else None
            log(f"  staff low at frame {i}: bottom {np.round(bottoms[i], 3)} expected {None if exp is None else np.round(exp, 3)} "
                f"hand {np.round(final_M[i]['RightHand'][:3, 3], 3)} target {np.round(stf.right_target(p)[0], 3)} "
                f"st_r {p.get('st_r')} hz {round(p['hz'], 3)}")
        meta[name] = m
        log(f"clip {name}: {sec}s loop={loop} slip(mm)={slip} overreach={m['ikOverreach_m']} "
            f"staff foot z min={m['staffFootMinZ_m']}")
    return meta, clips


def finish(lo0, info, jpg, ITER, video=True):
    J, T, ginfo = info["J"], info["T"], info["ginfo"]
    lo0, glow0 = split_glow(lo0)
    log("glow LOD0 verts", len(glow0.data.vertices), "groups", len(glow0.vertex_groups))
    specs = HR.bone_specs(J, info["hand_bones"], T, ginfo)
    arm = HR.build_armature(f"{ID}_rig", specs)
    deform = [b["name"] for b in specs if b["deform"]]
    log("bones", len(arm.data.bones), "deform", len(deform))
    mats = OB.export_materials(jpg)
    for o in (lo0, glow0):
        OB.assign(o, mats)
        remap_groups(o, deform)
        HF.parent_to(o, arm)
    b0 = SP.BUDGET
    g_tris = core.tri_count(glow0)
    lod1 = HF.lod_copy(lo0, int(b0[1] * 0.97) - g_tris, HR.LOD1_KEEP, f"{ID}_LOD1")
    lod2 = HF.lod_copy(lo0, int(b0[2] * 0.96) - g_tris, HR.LOD2_KEEP, f"{ID}_LOD2")
    glow1 = copy_obj(glow0, f"{ID}_glow_LOD1")
    glow2 = copy_obj(glow0, f"{ID}_glow_LOD2")
    remap_groups(glow1, HR.LOD1_KEEP)
    remap_groups(glow2, HR.LOD2_KEEP)
    for o in (lod1, lod2, glow1, glow2):
        HF.parent_to(o, arm)
    lods = {0: [lo0, glow0], 1: [lod1, glow1], 2: [lod2, glow2]}
    tris = {f"LOD{k}": sum(core.tri_count(o) for o in v) for k, v in lods.items()}
    log("tris", tris)
    # ---- clips
    sk = HA.Skel(arm)
    cx = HC.Ctx(sk, {}, J, T, "soldier", None)
    cx.staff = OC.Staff(sk, info)
    clip_meta, clips = bake_clips(arm, cx, ginfo)
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    # ---- export
    out_glb = paths.runtime(SP.GROUP, f"{ID}.glb")
    objs = [arm] + lods[0] + lods[1] + lods[2]
    core.export_glb(out_glb, objs, extra=dict(export_force_sampling=True, export_optimize_animation_size=False,
                                              export_image_format="AUTO", export_def_bones=True,
                                              export_animation_mode="ACTIONS", export_bake_animation=False))
    log("GLB", out_glb, os.path.getsize(out_glb) // 1024, "KB")
    meta = write_meta(arm, lods, tris, deform, mats, clip_meta, info, sk)
    blend = paths.source(SP.GROUP, f"{ID}.blend")
    core.save_blend(blend)
    log("saved", blend)
    qa_posed(arm, lods, info, ITER, jpg)
    if video:
        clip_videos()
    return meta


def used_bones(objs):
    out = set()
    for o in objs:
        out |= set(HF.used_bones(o))
    return sorted(out)


def gl(v):
    """Blender (x, y, z) -> glTF (x, z, -y)."""
    return [round(float(v[0]), 4), round(float(v[2]), 4), round(float(-v[1]), 4)]


def write_meta(arm, lods, tris, deform, mats, clip_meta, info, sk):
    mins, maxs = core.bounds(lods[0])
    st = info["staff"]
    Mp = sk.R["PropR"]
    crystal_local = np.linalg.inv(Mp) @ np.append(st["crystal"], 1.0)
    top_local = np.linalg.inv(Mp) @ np.append(st["top"], 1.0)
    A_ = SP.AMULET
    amulet = np.asarray(info["ring"], float) + np.array([0.0, -0.012, -(0.036 + A_["len"] * 0.55)])
    amulet_local = np.linalg.inv(sk.R["UpperChest"]) @ np.append(amulet, 1.0)
    meta = {
        "id": ID,
        "generation": "v2 pipeline, authored (no reference art): SDF body + garment/gear meshes, hand-painted "
                      "procedural atlas (orc_tex), shared human_shared rig",
        "rig": "human_shared",
        "tris": tris,
        "budget": {"LOD0": SP.BUDGET[0], "LOD1": SP.BUDGET[1], "LOD2": SP.BUDGET[2]},
        "bones": {"deform": len(deform), "total": len(arm.data.bones),
                  "weightedByLOD": {f"LOD{k}": len(used_bones(v)) for k, v in lods.items()},
                  "maxInfluences": 4, "names": deform},
        "nodes": {f"LOD{k}": v[0].name for k, v in lods.items()} | {f"glow_LOD{k}": v[1].name for k, v in lods.items()},
        "materials": [m.name for m in mats],
        "glowMaterials": [f"{ID}_glow"],
        "glow": {"material": f"{ID}_glow", "color": list(SP.GLOW["color"]), "emissionStrength": SP.GLOW["strength"],
                 "meshes": "lf_orc_warden_glow_LOD0/1/2 (staff crystal on PropR + chest crystal on UpperChest); "
                           "ActorRig keeps *_glow emission, drive with set_glow(energy) during lf_orc_drain"},
        "paintedLightMix": SP.PAINTED_LIGHT_MIX,
        "shading": "albedo * mix(1, lambert(sun), paintedLightMix): the atlas carries the painted light",
        "textures": {f"{ID}_color.jpg": SP.TEX},
        "bounds_m": {"min": [round(float(x), 3) for x in mins], "max": [round(float(x), 3) for x in maxs]},
        "clips": clip_meta,
        "sockets": {"hand_r": gl(sk.head("PropR")), "hand_l": gl(sk.head("PropL")), "head": [abs(x) if abs(x) < 1e-9 else x for x in gl(sk.head("Head"))],
                    "head_top": [0.0, round(float(info["J"]["HeadTop"][2]), 3), 0.0],
                    "chest_crystal": gl(amulet), "staff_crystal_rest": gl(st["crystal"])},
        "socketBones": {"hand_r": {"bone": "PropR", "offset": [0, 0, 0]},
                        "hand_l": {"bone": "PropL", "offset": [0, 0, 0]},
                        "head": {"bone": "Head", "offset": [0, 0, 0]},
                        "staff_crystal": {"bone": "PropR", "offset": [round(float(x), 4) for x in crystal_local[:3]],
                                          "note": "bone-local offset (metres) of the staff crystal centre; the staff "
                                                  "is rigid on PropR in every clip"},
                        "staff_tip": {"bone": "PropR", "offset": [round(float(x), 4) for x in top_local[:3]]},
                        "chest_crystal": {"bone": "UpperChest",
                                          "offset": [round(float(x), 4) for x in amulet_local[:3]]}},
        "staff": {"length_m": SP.STAFF["length"], "gripFromBottom_m": SP.STAFF["grip_from_bottom"],
                  "bone": "PropR", "note": "held in the right fist; lf_orc_order_point hands it to the left fist "
                                           "(PropR keyed in world space meanwhile) and back"},
        "variants": {},
        "coordinateConvention": {"up": "+Y", "forward": "+Z", "unit": "metre",
                                 "note": "Blender -Y forward exported to glTF +Z; feet on y=0, root at the origin; "
                                         "bounds_m in Blender axes (as the v2 humans)"},
        "notes": "Orc captor of a forest cage (drains strength from caged people through the bars). Rest stance is "
                 "hunched (neck/head forward). Same skeleton as lf_squad_captain: human clips play on him, but their "
                 "Hips translation keys are the human hip height (0.89 m vs 1.06 m), so retarget positions or use "
                 "the orc clips. Turn clips: yaw the node by rootYawDeg along smoothstep(t/seconds).",
    }
    core.write_json(paths.runtime(SP.GROUP, f"{ID}.meta.json"), meta)
    return meta


# --------------------------------------------------------------------------- QA

def set_frame(arm, clip, frame):
    act = bpy.data.actions.get(clip)
    arm.animation_data.action = act
    if act is not None and act.slots:
        arm.animation_data.action_slot = act.slots[0]
    bpy.context.scene.frame_set(int(frame))


def qa_posed(arm, lods, info, ITER, jpg):
    master = jpg.replace("_color.jpg", "_color_master.png")
    qm = OB.qa_materials(master)
    saved = {}
    for k, objs in lods.items():
        for o in objs:
            saved[o.name] = list(o.data.materials)
            OB.assign(o, qm)
            o.hide_render = k != 0

    def q(n):
        return OQ.qa_path(f"iter{ITER:02d}_{n}.png")
    set_frame(arm, "lf_orc_idle", 0)
    OQ.turnaround(q("turnaround_idle"), f"{ID} iter{ITER:02d} idle pose (frame 0), painted look")
    tiles, labels = [], []
    import hv2_blender as HBL
    HBL.qa_scene(samples=8)
    for k in (0, 1, 2):
        for kk, objs in lods.items():
            for o in objs:
                o.hide_render = kk != k
        for yaw in (0, 40):
            a = math.radians(yaw)
            tiles.append(OQ.tile((math.sin(a) * 8.0, -math.cos(a) * 8.0, 1.75), (0, 0, 1.15), 2.7, (480, 900)))
            labels.append(f"LOD{k} {sum(core.tri_count(o) for o in lods[k])} tris, yaw {yaw}")
    for kk, objs in lods.items():
        for o in objs:
            o.hide_render = kk != 0
    OQ.sheet(tiles, labels, q("lods"), f"{ID} iter{ITER:02d} LOD0 / LOD1 / LOD2 (idle frame 0)")
    st = info["staff"]
    OQ.detail(q("staff_hand"), f"{ID} iter{ITER:02d} staff + right fist (idle)",
              center=tuple(np.array([-0.50, -0.31, 1.25])), ortho=0.9, up=0.2)
    for clip, fr, lab in (("lf_orc_drain", 57, "drain_peak"), ("lf_orc_roar", 26, "roar"),
                          ("lf_orc_order_point", 40, "point"), ("lf_orc_order_point_left", 40, "point_left")):
        set_frame(arm, clip, fr)
        OQ.turnaround(q(f"pose_{lab}"), f"{ID} iter{ITER:02d} {clip} frame {fr}",
                      views=((0, "front"), (45, "3/4 left"), (-45, "3/4 right"), (90, "side")), samples=8,
                      ortho=3.3, res=(700, 1040), zc=1.2)
    set_frame(arm, "lf_orc_idle", 0)
    OQ.game_view(q("game_cam_blender"), f"{ID} game camera direction (yaw 45, pitch 38), idle")
    arm.animation_data.action = None
    for k, objs in lods.items():
        for o in objs:
            for i, m in enumerate(saved[o.name]):
                o.data.materials[i] = m
            o.hide_render = k != 0


def clip_videos():
    """Clip MP4s + contact sheets from the saved .blend in a fresh Blender process (render_orc_clips.py)."""
    import sys
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + os.pathsep + \
        env.get("PYTHONPATH", "")
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_orc_clips.py")
    r = subprocess.run([sys.executable, "-u", script], env=env, capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.startswith("VIDEO") or "Error" in line:
            log(line)
    if r.returncode:
        log("clip videos failed", r.stderr[-800:])
