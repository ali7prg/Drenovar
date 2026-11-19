"""Clip review videos for v2 humans (Blender Workbench, textured), one MP4 + contact sheet per clip,
optionally several characters side by side performing the same clip.

    python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/humans/v2/render_clips.py \
        <out_dir> <aid>[,<aid>...] [clip ...]
"""
import math
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from frlib import core, paths, render  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
OUT = ARGS[0]
AIDS = ARGS[1].split(",")
CLIPS = ARGS[2:]


def load_char(aid, offset_x):
    path = paths.source("humans", f"{aid}.blend")
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith(aid)]
        dst.actions = list(src.actions)
    arm = None
    for o in dst.objects:
        if o is None:
            continue
        bpy.context.scene.collection.objects.link(o)
        if o.type == "ARMATURE":
            arm = o
    for o in dst.objects:
        if o is not None and o.type == "MESH" and not o.name.endswith("_LOD0"):
            o.hide_render = True
    arm.location.x = offset_x
    arm["_meshes"] = [o.name for o in dst.objects if o is not None and o.type == "MESH"]
    import re as _re
    return arm, {_re.sub(r"\.\d{3}$", "", a.name): a for a in dst.actions if a is not None}


def set_clip(arm, act):
    """Armature action (OBJECT slot) + the sit_drape morph weight curve (KEY slot) of the same action."""
    arm.animation_data.action = act
    if act is None:
        return
    for s in act.slots:
        if s.target_id_type == "OBJECT":
            arm.animation_data.action_slot = s
    key_slot = next((s for s in act.slots if s.target_id_type == "KEY"), None)
    for name in arm.get("_meshes", []):
        o = bpy.data.objects.get(name)
        key = o.data.shape_keys if o is not None else None
        if key is None:
            continue
        if key.animation_data is None:
            key.animation_data_create()
        for tr in key.animation_data.nla_tracks:
            tr.mute = True
        if key_slot is not None:
            key.animation_data.action = act
            key.animation_data.action_slot = key_slot
        else:
            key.animation_data.action = None
            for kb in key.key_blocks[1:]:
                kb.value = 0.0


def main():
    core.reset(fps=30)
    os.makedirs(OUT, exist_ok=True)
    arms = []
    for i, aid in enumerate(AIDS):
        arm, acts = load_char(aid, (i - (len(AIDS) - 1) / 2) * 1.0)
        arms.append((aid, arm, acts))
    clip_names = CLIPS or sorted(n for n in arms[0][2] if n.startswith("lf_"))
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE"
    sh.show_shadows = False
    sh.show_cavity = False
    sc.render.film_transparent = False
    w = bpy.data.worlds.new("w")
    sc.world = w
    # ground plane
    me = bpy.data.meshes.new("ground")
    me.from_pydata([(-6, -6, 0), (6, -6, 0), (6, 6, 0), (-6, 6, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new("ground", me)
    sc.collection.objects.link(g)
    gm = bpy.data.materials.new("gm")
    gm.diffuse_color = (0.42, 0.44, 0.30, 1)
    me.materials.append(gm)
    width = max(1.6, len(AIDS) * 1.0 + 0.8)
    cam = render.perspective_camera((width * 0.9, -width * 2.0 - 2.0, 1.6), (0, 0, 0.85), lens=50,
                                    res=(2 * int(150 * max(1, len(AIDS) * 0.75)), 450), ortho_scale=max(2.3, width * 1.05))
    for clip in clip_names:
        tmp = tempfile.mkdtemp()
        n_fr = None
        for aid, arm, acts in arms:
            act = acts.get(clip)
            if arm.animation_data is None:
                arm.animation_data_create()
            set_clip(arm, act)
            if act is not None:
                n_fr = int(act.frame_range[1])
        if n_fr is None:
            continue
        loops = 2 if clip.endswith(("walk", "jog", "follow", "follow_tired")) else 1
        k = 0
        for _ in range(loops):
            for f in range(0, n_fr + 1):
                sc.frame_set(f)
                sc.render.filepath = os.path.join(tmp, f"f{k:05d}.png")
                bpy.ops.render.render(write_still=True)
                k += 1
        mp4 = os.path.join(OUT, f"{clip}.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i", os.path.join(tmp, "f%05d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", mp4], check=True)
        shutil.rmtree(tmp, ignore_errors=True)
        render.contact_sheet_from_video(mp4, os.path.join(OUT, f"{clip}_sheet.png"), frames=8, width=1600)
        print("clip", clip, n_fr, "frames ->", mp4, flush=True)


main()
