"""Stage 4: author the 13 manifest clips as Blender actions (dense keys at 60 fps), measure foot slip,
loop seams and IK overreach.  In: cache/maw2_tex.blend  Out: cache/maw2_anim.blend + cache/clip_report.json
"""
import json
import math
import os
import sys
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mv2_clips as CL  # noqa: E402
import mv2_common as C  # noqa: E402
from frlib import core  # noqa: E402

ARM = C.ASSET_ID + "_rig"


def write_action(arm, name, keys, loop):
    act = bpy.data.actions.get(name)
    if act is not None:
        bpy.data.actions.remove(act)
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act
    nf = len(keys)
    bones = list(keys[0].keys())
    prev = {}
    for b in bones:
        pb = arm.pose.bones[b]
        pb.rotation_mode = "QUATERNION"
        locs = np.array([keys[f][b][0] for f in range(nf)])
        qs = np.array([keys[f][b][1] for f in range(nf)])
        scs = np.array([keys[f][b][2] for f in range(nf)])
        for f in range(1, nf):
            if np.dot(qs[f], qs[f - 1]) < 0:
                qs[f] = -qs[f]
        moved_loc = np.abs(locs).max() > 1e-5
        moved_rot = np.abs(qs - np.array([1, 0, 0, 0])).max() > 1e-6
        moved_sc = np.abs(scs - 1).max() > 1e-5
        frames = np.arange(nf, dtype=np.float32)
        for path, data, n, flag in (("rotation_quaternion", qs, 4, moved_rot), ("location", locs, 3, moved_loc),
                                    ("scale", scs, 3, moved_sc)):
            if not flag and path != "rotation_quaternion":
                continue
            for i in range(n):
                fc = act.fcurves.new(f'pose.bones["{b}"].{path}', index=i, action_group=b) \
                    if hasattr(act, "fcurves") else None
                if fc is None:
                    break
                fc.keyframe_points.add(nf)
                co = np.empty(nf * 2, np.float32)
                co[0::2] = frames
                co[1::2] = data[:, i]
                fc.keyframe_points.foreach_set("co", co)
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
                fc.update()
    act.use_frame_range = True
    act.frame_start = 0
    act.frame_end = nf - 1
    act.use_cyclic = bool(loop)
    act["loop"] = bool(loop)
    return act


def write_action_slotted(arm, name, keys, loop):
    """bpy 5.x slotted actions: use keyframe_insert per frame when fcurves are not directly creatable."""
    act = bpy.data.actions.get(name)
    if act is not None:
        bpy.data.actions.remove(act)
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act
    nf = len(keys)
    prev = {}
    for f in range(nf):
        for b, (loc, q, sc) in keys[f].items():
            pb = arm.pose.bones[b]
            q = np.asarray(q)
            if b in prev and np.dot(prev[b], q) < 0:
                q = -q
            prev[b] = q
            pb.rotation_quaternion = q.tolist()
            pb.keyframe_insert("rotation_quaternion", frame=f, group=b)
            if np.abs(loc).max() > 1e-5 or b in ("pelvis",):
                pb.location = loc.tolist()
                pb.keyframe_insert("location", frame=f, group=b)
            if np.abs(np.asarray(sc) - 1).max() > 1e-5 or b == "breath":
                pb.scale = list(sc)
                pb.keyframe_insert("scale", frame=f, group=b)
    act.use_frame_range = True
    act.frame_start = 0
    act.frame_end = nf - 1
    act.use_cyclic = bool(loop)
    act["loop"] = bool(loop)
    return act


CLAW_TIPS = None


def claw_min_z(rig, cid):
    """Lowest foot-claw tip (world z) over the clip's planted frames (rest-pose tips carried by the toe bones)."""
    global CLAW_TIPS
    import mv2_details as D
    if CLAW_TIPS is None:
        CLAW_TIPS = []
        for p in D.claws():
            if p["bone"].startswith(("toe", "hallux")):
                CLAW_TIPS.append((p["bone"], p["verts"][-2]))
    D_, loop, fn, _m = CL.CLIPS[cid]
    fn = CL.with_overrides(cid, fn)
    best = 9.0
    for f in range(0, int(round(D_ * CL.FPS)) + 1, 3):
        ch = fn(f / CL.FPS)
        rig.build(ch)
        M = rig.ps.fk()
        for bone, tip in CLAW_TIPS:
            side = bone[-1]
            if not ch.get(f"contact_{side}", True):
                continue
            Mi = M[bone] @ np.linalg.inv(rig.sk.rest[bone])
            z = (Mi @ np.append(tip, 1.0))[2]
            best = min(best, z)
    return best


def main():
    t0 = time.time()
    bpy.ops.wm.open_mainfile(filepath=C.cache("maw2_tex.blend"))
    sc = bpy.context.scene
    sc.render.fps = CL.FPS
    sc.render.fps_base = 1.0
    arm = bpy.data.objects[ARM]
    fitted = CL.load_keypose_fit(C.cache("keypose_fit.json"))
    C.log(f"art/05 key-pose fit applied: {fitted}; walk speed {CL.WALK_SPEED} lift {CL.WALK_LIFT:.2f} pz {CL.WALK_PZ:.2f}")
    rig = CL.Rig(arm)
    report = {}
    for cid, (D, loop, _fn, markers) in CL.CLIPS.items():
        keys, feet, yaws, over = CL.frames(rig, cid)
        gs = CL.WALK_SPEED if cid == "lf_boss_walk" else 0.0
        if cid == "lf_boss_walk":
            CL.CLIPS[cid] = (CL.WALK_D, True, CL.clip_walk, {})
        slip = CL.foot_slip(cid, feet, yaws, ground_speed=gs)
        try:
            write_action_slotted(arm, cid, keys, loop)
        except Exception as e:  # pragma: no cover
            C.log("slotted write failed", e)
            raise
        seam = 0.0
        if loop:
            for b in keys[0]:
                q0, q1 = np.asarray(keys[0][b][1]), np.asarray(keys[-1][b][1])
                seam = max(seam, float(min(np.abs(q0 - q1).max(), np.abs(q0 + q1).max())))
        entry = {"seconds": D, "frames": len(keys) - 1, "fps": CL.FPS, "loop": loop, "markers": markers,
                 "footSlip_m": slip, "ikOverreach_m": round(max(0.0, over), 4)}
        if loop:
            entry["loopSeamMaxQuatDiff"] = seam
        if cid == "lf_boss_walk":
            entry["groundSpeed_mps"] = CL.WALK_SPEED
            entry["strideLength_m"] = round(CL.WALK_SPEED * CL.WALK_D, 3)
        if cid.startswith("lf_boss_turn"):
            entry["rootYawDeg"] = CL.TURN_YAW * (1 if cid.endswith("left") else -1)
            entry["yawCurve"] = (f"yaw(t) = rootYawDeg * smoothstep(t/{CL.TURN_D}) about the root origin (apply to the "
                                 "node while the clip plays; feet are planted in that frame)")
        entry["clawTipMinZ_planted_m"] = round(float(claw_min_z(rig, cid)), 4)
        report[cid] = entry
        C.log(f"{cid}: {D}s frames {len(keys) - 1} slip {slip} over {over:.3f} {time.time() - t0:.1f}s")
    arm.animation_data.action = bpy.data.actions["lf_boss_idle"]
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()
    with open(C.cache("clip_report.json"), "w") as fh:
        json.dump(report, fh, indent=2)
    bpy.ops.wm.save_as_mainfile(filepath=C.cache("maw2_anim.blend"), compress=True)
    C.log(f"stage anim done {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
