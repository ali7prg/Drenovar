"""Stage 5: export the game GLB (LOD0/1/2 + rig + 13 clips), exact durations, meta sidecar, master .blend.

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/boss/maw_stage_export.py
Also writes a LOD0-only QA GLB to the cache for the Godot viewer.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maw_common as C  # noqa: E402
import bpy  # noqa: E402

from frlib import core, paths  # noqa: E402
import glbtool  # noqa: E402
import maw_anim as A  # noqa: E402
import maw_rig as MR  # noqa: E402

AID = C.ASSET_ID


def log(*a):
    print("[maw_export]", *a, flush=True)


def stage_actions(arm):
    ad = arm.animation_data or arm.animation_data_create()
    for tr in list(ad.nla_tracks):
        ad.nla_tracks.remove(tr)
    for cid in A.MANIFEST:
        act = bpy.data.actions[cid]
        tr = ad.nla_tracks.new()
        tr.name = cid
        st = tr.strips.new(cid, 0, act)
        st.action_frame_end = act.frame_end
        tr.mute = True
    ad.action = None


def export(path, objs):
    core.export_glb(path, objs, animations=True, image_format="AUTO", jpeg_quality=90,
                    extra={"export_nla_strips": True, "export_force_sampling": True, "export_frame_step": 1})


def sockets(arm):
    from maw_pose import Poser
    ps = Poser(arm)
    P = ps.matrices()
    g = lambda v: [round(float(c), 3) for c in v]  # noqa: E731
    return {"mouth": g(ps.tail("head", P) + (ps.head("jaw", P) - ps.head("head", P)) * 0.0),
            "jaw_tip": g(ps.tail("jaw", P)), "head": g(ps.head("head", P)), "chest": g(ps.head("spine_03", P)),
            "tail_tip": g(ps.tail("tail_10", P)), "foot_L": g(ps.tail("foot_L", P)), "foot_R": g(ps.tail("foot_R", P)),
            "hand_L": g(ps.tail("hand_L", P)), "hand_R": g(ps.tail("hand_R", P))}


def publish_textures():
    import shutil
    src = C.cache("tex")
    dst = paths.ensure(paths.TEXTURE_SOURCES, C.GROUP)
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        for f in files:
            os.makedirs(os.path.join(dst, rel), exist_ok=True)
            shutil.copy2(os.path.join(root, f), os.path.join(dst, rel, f))


def main():
    publish_textures()
    bpy.ops.wm.open_mainfile(filepath=C.cache("maw_anim.blend"))
    arm = bpy.data.objects[f"{AID}_rig"]
    lods = [bpy.data.objects[f"{AID}_LOD{i}"] for i in range(3)]
    for o in lods:
        o.hide_set(False)
        o.hide_render = False
    stage_actions(arm)
    from frlib import rig
    rig.rest_pose(arm)
    glb = paths.runtime(C.GROUP, f"{AID}.glb")
    export(glb, [arm] + lods)
    js, binc = glbtool.read(glb)
    dur = {cid: v[0] for cid, v in A.MANIFEST.items()}
    mk = {cid: v[2] for cid, v in A.MANIFEST.items()}
    rep = glbtool.fix_durations(js, binc, dur, mk)
    glbtool.write(glb, js, binc)
    st = glbtool.stats(js, binc)
    log("stats", st["meshes"], "skins", st["skins"], "anims", len(st["animations"]))
    log("durations", rep)
    # QA copy: LOD0 only (the viewer shows every mesh at once)
    qa_glb = C.cache(f"{AID}_LOD0_qa.glb")
    export(qa_glb, [arm, lods[0]])
    js2, b2 = glbtool.read(qa_glb)
    glbtool.fix_durations(js2, b2, dur, mk)
    glbtool.write(qa_glb, js2, b2)
    # ---- meta
    lo, hi = core.bounds([lods[0]])
    tex = {}
    for im in bpy.data.images:
        if im.users and im.size[0] > 0 and im.name.startswith(AID):
            tex[im.name] = list(im.size)
    used = dict(arm.get("bones_used", {}))
    clips = {}
    for cid, (D, loop, markers) in A.MANIFEST.items():
        c = {"seconds": D, "loop": loop, "rootTranslation": "in_place", "markers": markers,
             "exportedSeconds": rep.get(cid, {}).get("after")}
        if cid == "lf_boss_walk":
            c.update({"groundSpeed_mps": A.WALK_SPEED, "strideLength_m": round(A.WALK_SPEED * A.WALK_T, 3),
                      "stepLength_m": round(A.WALK_SPEED * A.WALK_T / 2, 3), "dutyFactor": A.WALK_DUTY,
                      "footContacts_s": {"left": 0.0, "right": A.WALK_T / 2}})
        if cid in ("lf_boss_turn_left", "lf_boss_turn_right"):
            c["clientRootYaw"] = {"degrees": 90 if cid.endswith("left") else -90, "curve": "smoothstep(t/1.3)",
                                  "note": "planted feet counter-rotate in root space; apply this yaw to the actor root "
                                          "over the clip (left = counter-clockwise seen from above)"}
        if cid == "lf_boss_lane_charge":
            c["clientRootTranslation"] = {"window_s": [A.CHARGE_T0, A.CHARGE_T1], "distance_m": A.CHARGE_DIST,
                                          "profile": "accelerate 25%, constant, ease-out last 15% (maw_anim.charge_d)",
                                          "note": "feet are planted in world space for this profile; the root stays "
                                                  "still in telegraph and recovery"}
        if cid == "lf_boss_death":
            c["endPose"] = "lying slumped on the right side (sheet 05 death keypose), stays on the ground"
        clips[cid] = c
    meta = {
        "id": AID, "speciesId": "ancient_maw", "displayName": "Пращур",
        "tris": {f"LOD{i}": st["meshes"].get(f"{AID}_LOD{i}") for i in range(3)},
        "bones": st["skins"][0] if st["skins"] else None,
        "bonesUsedPerLOD": used, "maxInfluences": 4,
        "materials": st["materials"], "textures": tex, "images": st["images"],
        "bounds_m": {"min": [round(float(v), 3) for v in lo], "max": [round(float(v), 3) for v in hi],
                     "size": [round(float(h - l), 3) for l, h in zip(lo, hi)]},
        "clips": clips, "sockets": sockets(arm),
        "notes": [
            "Blender Z-up, faces -Y; exported glTF +Y up, +Z forward; feet on the ground, root at origin under the hips.",
            "Scale: sheet vertical annotations kept (top of skull 3.6 m, back over hip 2.76 m, hip joint 2.41 m); "
            "the drawn body is 9.8 m snout->tail tip (8.4 m along the sheet's own 'body length' dimension line). "
            "The sheet is not self-consistent: 8.0 m length would require 2.9 m head height.",
            "LOD1/LOD2 use the same skeleton; small bones are merged into parents (bonesUsedPerLOD) to meet the "
            "manifest 80/50/28 deform-bone targets.",
            "Markers are presentation-only; the server owns attack windows.",
        ],
    }
    core.write_json(paths.runtime(C.GROUP, f"{AID}.meta.json"), meta)
    log("meta written", meta["tris"], meta["bones"])
    stage_actions(arm)
    arm.animation_data.action = bpy.data.actions["lf_boss_idle"]
    core.save_blend(paths.source(C.GROUP, f"{AID}.blend"))
    log("master saved")


if __name__ == "__main__":
    main()
