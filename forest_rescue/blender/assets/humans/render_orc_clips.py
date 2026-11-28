"""Clip review videos for lf_orc_warden from its .blend master (Blender Workbench, flat textured = the
painted albedo), one MP4 per clip in forest_rescue/qa/video/lf_orc_warden/ + a contact sheet
(forest_rescue/tools/contact_sheet.py) copied to forest_rescue/qa/compare/lf_orc_warden/.
Turn clips are rendered with the node yaw the director applies (rootYawDeg * smoothstep(t/T)).

    python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/humans/render_orc_clips.py [clip ...]
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

import bpy  # noqa: E402

from frlib import paths, render  # noqa: E402

ID = "lf_orc_warden"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def main():
    bpy.ops.wm.open_mainfile(filepath=paths.source("humans", f"{ID}.blend"))
    meta = json.load(open(paths.runtime("humans", f"{ID}.meta.json")))
    arm = bpy.data.objects[f"{ID}_rig"]
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = not o.name.endswith("_LOD0")
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "FLAT"
    sh.color_type = "TEXTURE"
    sh.show_shadows = False
    sh.show_cavity = False
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "Standard"
    w = sc.world or bpy.data.worlds.new("w")
    sc.world = w
    w.color = (0.56, 0.57, 0.52)
    me = bpy.data.meshes.new("qa_ground")
    me.from_pydata([(-5, -5, 0), (5, -5, 0), (5, 5, 0), (-5, 5, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new("qa_ground", me)
    sc.collection.objects.link(g)
    gm = bpy.data.materials.new("qa_gm")
    gm.diffuse_color = (0.36, 0.38, 0.27, 1)
    me.materials.append(gm)
    vdir = paths.ensure(paths.QA_VIDEO, ID)
    cdir = paths.ensure(paths.QA_COMPARE, ID)
    tool = os.path.join(paths.FR_DIR, "tools", "contact_sheet.py")
    clips = ARGS or list(meta["clips"])
    for name in clips:
        m = meta["clips"][name]
        act = bpy.data.actions[name]
        arm.animation_data.action = act
        if act.slots:
            arm.animation_data.action_slot = act.slots[0]
        n_fr = int(round(m["seconds"] * 30))
        yaw = m.get("rootYawDeg")
        if name == "lf_orc_walk":
            cam = ((4.6, -2.2, 1.7), (0, 0, 1.0))          # side-ish: stride and foot contacts
        elif yaw:
            cam = ((0.0, -4.4, 3.6), (0, 0, 0.9))          # high front: the turn reads from above
        else:
            cam = ((2.3, -4.2, 1.9), (0, -0.1, 1.05))
        render.perspective_camera(cam[0], cam[1], lens=40, res=(600, 680))
        tmp = tempfile.mkdtemp()
        loops = 2 if m["loop"] and m["seconds"] < 2.0 else 1
        k = 0
        sc.frame_set(1)
        for _ in range(loops):
            for f in range(n_fr + 1):
                sc.frame_set(f)
                arm.rotation_euler = (0.0, 0.0, math.radians(yaw * smooth(f / n_fr)) if yaw else 0.0)
                bpy.context.view_layer.update()
                sc.render.filepath = os.path.join(tmp, f"f{k:05d}.png")
                bpy.ops.render.render(write_still=True)
                k += 1
        arm.rotation_euler = (0.0, 0.0, 0.0)
        mp4 = os.path.join(vdir, f"{name}.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i", os.path.join(tmp, "f%05d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", mp4], check=True)
        shutil.rmtree(tmp, ignore_errors=True)
        subprocess.run(["python3", tool, mp4, "--cols", "6", "--rows", "2"], capture_output=True, text=True)
        cs = mp4.replace(".mp4", "_contact.png")
        if os.path.exists(cs):
            shutil.copy(cs, os.path.join(cdir, f"clip_{name}_contact.png"))
        print("VIDEO", mp4, n_fr + 1, "frames", flush=True)


main()
