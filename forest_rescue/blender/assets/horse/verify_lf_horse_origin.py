"""Verification renders for lf_horse_origin (run after build_lf_horse_origin.py).

    python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/horse/verify_lf_horse_origin.py \
        [--iter N] [--compare] [--poses] [--clips] [--lods] [--samples 48]

--compare : 4 orthographic comparisons -> qa/compare/lf_horse_origin/<view>.png/.json (+ iterNN_ copies)
--poses   : posed 3/4 renders next to the walk / trot / stop-and-look-back drawings
--clips   : Workbench MP4 per clip + contact sheet -> qa/video/lf_horse_origin/
"""
import json
import math
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from frlib import core, paths, render  # noqa: E402
import horse_refs as HR  # noqa: E402

ASSET = "lf_horse_origin"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
ITER = int(ARGS[ARGS.index("--iter") + 1]) if "--iter" in ARGS else None
SAMPLES = int(ARGS[ARGS.index("--samples") + 1]) if "--samples" in ARGS else 40
ENGINE = ARGS[ARGS.index("--engine") + 1] if "--engine" in ARGS else "workbench"
ONLY = ARGS[ARGS.index("--only") + 1].split(",") if "--only" in ARGS else None
ALL = not any(a in ARGS for a in ("--compare", "--poses", "--clips", "--lods"))


def open_master():
    bpy.ops.wm.open_mainfile(filepath=paths.source("horse", f"{ASSET}.blend"))
    arm = bpy.data.objects[f"{ASSET}_rig"]
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = o.name != f"{ASSET}_LOD0"
    return arm


def set_lights(key_dir, key=3.0, fill=0.9, rim=1.2, bg=(0.86, 0.82, 0.74)):
    scene = render.studio(bg=bg, engine="CYCLES", samples=SAMPLES, key_dir=tuple(key_dir),
                          key_energy=key, fill_energy=fill, rim_energy=rim, ambient=0.62)
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "Standard"
    return scene


def view_key(view):
    L = -0.55 * view.right + 0.75 * view.up - 0.45 * view.d
    return L / np.linalg.norm(L)


def rest_pose(arm):
    if arm.animation_data:
        arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def save_iter(path):
    if ITER is None:
        return
    d, b = os.path.split(path)
    shutil.copy(path, os.path.join(d, f"iter{ITER:02d}_{b}"))


def do_compare(arm):
    rest_pose(arm)
    views = HR.load_views()
    results = {}
    for name in ("left", "front", "rear", "right"):
        v = views[name]
        set_lights(view_key(v))
        render.camera_for_view(v)
        rgba = render.render_rgba()
        out = paths.compare(ASSET, f"{name}.png")
        m = render.compare(v, rgba, out, title=f"{ASSET} {name} (LOD0, rest pose, Cycles)")
        results[name] = m
        save_iter(out)
        save_iter(out.replace(".png", ".json"))
        print("COMPARE", name, m)
    # 2x2 overview sheet
    from PIL import Image
    ims = [Image.open(paths.compare(ASSET, f"{n}.png")) for n in ("left", "front", "rear", "right")]
    W = max(i.width for i in ims)
    sheet = Image.new("RGB", (W, sum(i.height for i in ims)), (30, 30, 30))
    y = 0
    for im in ims:
        sheet.paste(im, (0, y))
        y += im.height
    sheet.save(paths.compare(ASSET, "overview.png"))
    save_iter(paths.compare(ASSET, "overview.png"))
    core.write_json(paths.compare(ASSET, "metrics.json"), results)
    save_iter(paths.compare(ASSET, "metrics.json"))
    return results


def pose_at(arm, action, t):
    arm.animation_data.action = bpy.data.actions[action]
    bpy.context.scene.frame_set(int(math.floor(t * 30)), subframe=(t * 30) % 1.0)
    bpy.context.view_layer.update()


def do_poses(arm):
    imgs = HR.pose_images()
    if arm.animation_data is None:
        arm.animation_data_create()
    # (action, time, camera location, look-at, lens, key light dir) chosen to match the drawings
    setups = {
        "walk": ("lf_horse_walk", 0.12, (-8.0, -1.6, 1.30), (0.0, -0.22, 0.98), 85, (-0.5, -0.7, 0.6)),
        "trot": ("lf_horse_trot", 0.13, (-8.0, -1.6, 1.35), (0.0, -0.22, 1.0), 85, (-0.5, -0.7, 0.6)),
        "look_back": ("lf_horse_look_back", 0.95, (-7.4, 2.9, 1.45), (0.0, 0.0, 0.98), 95,
                      (-0.6, 0.5, 0.7)),
    }
    from PIL import Image
    for key, (act, t, loc, look, lens, kd) in setups.items():
        pose_at(arm, act, t)
        set_lights(kd)
        ref = imgs[key]
        h, w = ref.shape[:2]
        render.perspective_camera(loc, look, lens=lens, res=(w * 2, h * 2))
        rgba = render.render_rgba()
        out = paths.compare(ASSET, f"pose_{key}.png")
        render.side_by_side([ref, rgba], [f"reference: {key}", f"model: {act} @ {t:.2f}s"], out,
                            height=560)
        save_iter(out)
        print("POSE", key, out)
    rest_pose(arm)


def do_clips(arm):
    if ENGINE == "eevee":
        scene = render.studio(engine="BLENDER_EEVEE", samples=8, transparent=False,
                              key_dir=(-0.55, -0.75, 0.75), key_energy=3.2, fill_energy=1.0,
                              rim_energy=1.2, ambient=0.6)
        eng = "BLENDER_EEVEE"
    else:
        scene = bpy.context.scene
        scene.render.engine = "BLENDER_WORKBENCH"
        sh = scene.display.shading
        sh.light = "STUDIO"
        sh.color_type = "TEXTURE"
        sh.show_shadows = True
        sh.shadow_intensity = 0.35
        sh.show_cavity = False
        sh.background_type = "VIEWPORT"
        sh.background_color = (0.78, 0.75, 0.69)
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.exposure = 0.9
        eng = "BLENDER_WORKBENCH"
    # ground plane
    me = bpy.data.meshes.new("qa_ground")
    me.from_pydata([(-8, -8, 0), (8, -8, 0), (8, 8, 0), (-8, 8, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new("qa_ground", me)
    core.link(g)
    gm = core.material("qa_ground_mat", base=(0.42, 0.38, 0.30, 1))
    core.assign(g, gm)
    cam = render.perspective_camera((-5.6, -3.5, 1.9), (0, -0.2, 0.98), lens=40, res=(960, 540))
    meta = json.load(open(paths.runtime("horse", f"{ASSET}.meta.json")))
    for act in sorted(a.name for a in bpy.data.actions if a.name.startswith("lf_horse_")):
        if ONLY and act not in ONLY:
            continue
        out = paths.video(ASSET, f"{act}.mp4")
        a = bpy.data.actions[act]
        cm = meta["clips"].get(act, {})
        yaw = cm.get("rootYawDeg", 0.0)
        n = int(round(a.frame_range[1]))
        # turn clips: preview with the documented root yaw applied (game-side behaviour)
        if yaw:
            arm.animation_data.action = a
            tmp = os.path.join(os.path.dirname(out), "_frames")
            os.makedirs(tmp, exist_ok=True)
            T = cm["seconds"]
            for i in range(n + 1):
                t = min(i / 30.0, T)
                u = t / T
                s = u * u * (3 - 2 * u)
                arm.rotation_euler = (0, 0, math.radians(yaw) * s)
                scene.frame_set(i)
                scene.render.filepath = os.path.join(tmp, f"f{i:05d}.png")
                bpy.ops.render.render(write_still=True)
            import subprocess
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i",
                            os.path.join(tmp, "f%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-crf", "20", out], check=True)
            shutil.rmtree(tmp, ignore_errors=True)
            arm.rotation_euler = (0, 0, 0)
        else:
            loops = 2 if a.get("loop") else 1
            render.render_clip(arm, a, out, camera_obj=cam, engine=eng, res=(960, 540),
                               loops=loops, samples=8)
        sheet = paths.video(ASSET, f"{act}_contact.png")
        render.contact_sheet_from_video(out, sheet, frames=8, width=1600)
        save_iter(sheet)
        print("CLIP", act, out)


def main():
    arm = open_master()
    if ALL or "--compare" in ARGS:
        do_compare(arm)
    if ALL or "--poses" in ARGS:
        do_poses(arm)
    if ALL or "--clips" in ARGS:
        do_clips(arm)


if __name__ == "__main__":
    main()
