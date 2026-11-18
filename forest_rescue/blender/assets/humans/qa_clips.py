"""Render every clip of a built human (.blend master) to MP4 + contact sheet, plus pose matches
against delivery/art/12_civilian_rescue_motion.png.

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/humans/qa_clips.py <asset> [<asset>...]
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import numpy as np

from frlib import core, paths, refs, render

MOTION = "12_civilian_rescue_motion.png"
PANELS12 = {
    "walk_contact": (60, 0, 400, 320), "walk_down": (440, 0, 780, 320), "walk_passing": (840, 0, 1180, 320),
    "walk_up": (1200, 0, 1536, 320),
    "sit": (40, 325, 400, 610), "lean_hands_knees": (440, 325, 780, 610), "rising": (840, 325, 1180, 610),
    "standing_relieved": (1200, 325, 1536, 610),
    "guard_offers_hand": (0, 620, 445, 1015), "cooper_through_door": (447, 620, 775, 1015),
    "supported_walk": (780, 620, 1162, 1015), "hand_on_heart": (1167, 620, 1536, 1015),
}


def open_master(asset):
    bpy.ops.wm.open_mainfile(filepath=paths.source("humans", f"{asset}.blend"))
    arm = bpy.data.objects[f"{asset}_rig"]
    for o in bpy.data.objects:
        if o.type == "MESH":
            nm = o.name
            show = nm.endswith("_LOD0")
            if "_opt_" in nm:
                show = show and bool(o.get("default_on", False))
            o.hide_render = not show
    return arm


def ground(size=8.0):
    if bpy.data.objects.get("qa_ground"):
        return bpy.data.objects["qa_ground"]
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, 0))
    g = bpy.context.active_object
    g.name = "qa_ground"
    m = core.material("qa_ground_mat", base=(0.45, 0.42, 0.36, 1.0), rough=1.0)
    core.assign(g, m)
    # 10 cm grid lines help judging foot sliding
    return g


def workbench_textured(res=(800, 450)):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE"
    sh.show_shadows = True
    sh.show_cavity = True
    sh.cavity_type = "WORLD"
    sc.render.film_transparent = False
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    world = bpy.data.worlds.get("qa_world") or bpy.data.worlds.new("qa_world")
    sc.world = world
    world.color = (0.62, 0.60, 0.56)
    return sc


def clip_camera(kind="side34", h=1.0):
    if kind == "side":
        return render.perspective_camera((-4.2, -0.6, 1.05), (0, -0.05, 0.85), lens=50, res=(800, 450))
    if kind == "front34":
        return render.perspective_camera((2.0, -3.6, 1.45), (0, -0.1, 0.80), lens=50, res=(800, 450))
    return render.perspective_camera((-2.9, -3.0, 1.35), (0, -0.1, 0.85), lens=50, res=(800, 450))


def render_all_clips(asset):
    arm = open_master(asset)
    ground()
    workbench_textured()
    out = {}
    acts = [a for a in bpy.data.actions if a.name.startswith("lf_")]
    for act in sorted(acts, key=lambda a: a.name):
        kind = "side" if any(k in act.name for k in ("walk", "jog", "follow")) else "side34"
        cam = clip_camera(kind)
        mp4 = paths.video(asset, f"{act.name}.mp4")
        loops = 2 if act.get("loop") else 1
        render.render_clip(arm, act, mp4, camera_obj=cam, engine="BLENDER_WORKBENCH", res=(800, 450), loops=loops)
        sheet = mp4.replace(".mp4", "_contact.png")
        render.contact_sheet_from_video(mp4, sheet, frames=8, width=1600)
        out[act.name] = {"mp4": mp4, "contact": sheet}
        print("CLIP", asset, act.name, flush=True)
    arm.animation_data.action = None
    return out


def set_pose(arm, action_name, t):
    act = bpy.data.actions[action_name]
    arm.animation_data.action = act
    bpy.context.scene.frame_set(int(round(t * 30)))


def render_rgba(cam_loc, target, lens=50, res=(512, 512)):
    render.perspective_camera(cam_loc, target, lens=lens, res=res)
    bpy.context.scene.render.film_transparent = True
    return render.render_rgba()


def pose_matches(asset_map):
    """asset_map: role -> asset id (miller, cooper, courier, guard, herbalist)."""
    ref = refs.load(MOTION)
    outdir = paths.ensure(paths.QA_COMPARE, "humans_motion12")
    results = {}

    def crop(name):
        return refs.crop(ref, PANELS12[name])

    jobs = []
    if "miller" in asset_map:
        a = asset_map["miller"]
        # walk: four phases of lf_civilian_follow (1.1 s): contact 0, down .12, passing .30, up .42
        for name, t in (("walk_contact", 0.0), ("walk_down", 0.12), ("walk_passing", 0.28), ("walk_up", 0.42)):
            jobs.append((a, name, "lf_civilian_follow", t, ((-4.4, -0.20, 1.0), (0, -0.20, 0.88), 50)))
        for name, t in (("sit", 0.0), ("lean_hands_knees", 1.05), ("rising", 1.5), ("standing_relieved", 1.95)):
            jobs.append((a, name, "lf_civilian_stand_up", t, ((1.6, -3.4, 1.15), (0, 0.0, 0.75), 50)))
    if "cooper" in asset_map:
        jobs.append((asset_map["cooper"], "cooper_through_door", "lf_civilian_exit", 1.35,
                     ((0.3, -3.8, 1.2), (0, -0.9, 0.85), 50)))
    if "courier" in asset_map:
        jobs.append((asset_map["courier"], "hand_on_heart", "lf_civilian_thank", 1.2,
                     ((0.4, -3.6, 1.15), (0, 0.0, 0.88), 50)))
    if "guard" in asset_map:
        jobs.append((asset_map["guard"], "guard_offers_hand", "lf_soldier_help", 1.0,
                     ((3.4, -2.2, 1.25), (0, -0.2, 0.95), 50)))
    if "herbalist" in asset_map:
        jobs.append((asset_map["herbalist"], "supported_walk", "lf_civilian_follow_tired", 0.3,
                     ((0.6, -3.8, 1.15), (0, 0.0, 0.85), 50)))
    cur = None
    for asset, name, act, t, (loc, tgt, lens) in jobs:
        if cur != asset:
            arm = open_master(asset)
            render.studio(engine="BLENDER_EEVEE", samples=24)
            cur = asset
        set_pose(arm, act, t)
        img = render_rgba(loc, tgt, lens=lens, res=(512, 512))
        out = os.path.join(outdir, f"{name}.png")
        render.side_by_side([crop(name), img], [f"12_motion: {name}", f"{asset} {act} t={t:.2f}s"], out, height=420)
        results[name] = {"asset": asset, "clip": act, "t": t, "png": out}
        print("POSE", name, flush=True)
    core.write_json(os.path.join(outdir, "pose_matches.json"), results)
    return results


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if argv and argv[0] == "poses":
        pose_matches({"miller": "lf_civilian_miller", "cooper": "lf_civilian_cooper", "courier": "lf_civilian_courier",
                      "guard": "lf_squad_shield_guard", "herbalist": "lf_civilian_herbalist"})
    else:
        for a in argv:
            r = render_all_clips(a)
            core.write_json(paths.video(a, "clips.json"), r)
