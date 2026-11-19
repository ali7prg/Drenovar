"""Blender motion QA: every clip to MP4 (+ contact sheet) and the art/05 key-pose sheet.

blender-python mv2_videos.py <anim_blend> [--clips a,b] [--no-videos] [--no-keyposes]
"""
import math
import os
import shutil
import subprocess
import sys
import tempfile

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mv2_common as C  # noqa: E402
import mv2_clips as CL  # noqa: E402
import mv2_refs as R  # noqa: E402
from frlib import core, render  # noqa: E402

ARM = C.ASSET_ID + "_rig"


def scene_setup():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE"
    sh.show_shadows = True
    sh.shadow_intensity = 0.45
    sh.show_cavity = False
    sh.show_backface_culling = True
    sc.display.light_direction = (-0.45, -0.35, 0.82)
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "Standard"
    w = bpy.data.worlds.get("qa_world") or bpy.data.worlds.new("qa_world")
    sc.world = w
    for m in bpy.data.materials:
        if m.node_tree is None:
            continue
        for n in m.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image is not None and n.image.colorspace_settings.name == "sRGB":
                m.node_tree.nodes.active = n
    for o in bpy.data.objects:
        if o.type == "MESH":
            keep = (o.name.endswith("_LOD0") or o.name.startswith(("ground_qa", "ground_grid"))
                    or o.name in ("maw_body", "maw_teeth", "maw_claws", "maw_eyes", "maw_tongue", "maw_mouth"))
            o.hide_render = not keep
    if "ground_qa" not in bpy.data.objects:
        bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
        g = bpy.context.active_object
        g.name = "ground_qa"
        mat = bpy.data.materials.new("ground_qa_mat")
        mat.diffuse_color = (0.55, 0.52, 0.45, 1.0)
        g.data.materials.append(mat)
    # grid lines on the ground for slip reading: thin strips every 0.5 m
    if "ground_grid" not in bpy.data.objects:
        verts, faces = [], []
        for i in range(-12, 13):
            y = i * 0.5
            b = len(verts)
            verts += [(-8, y - 0.01, 0.002), (8, y - 0.01, 0.002), (8, y + 0.01, 0.002), (-8, y + 0.01, 0.002)]
            faces.append((b, b + 1, b + 2, b + 3))
        o = core.mesh_object("ground_grid", np.array(verts), faces, smooth=False)
        mat = bpy.data.materials.new("grid_mat")
        mat.diffuse_color = (0.35, 0.33, 0.28, 1.0)
        o.data.materials.append(mat)
    return sc


def cam_side(name="vid_cam", res=(640, 360), loc=(13.0, -5.5, 5.2), tgt=(0.0, -0.4, 1.7), lens=40.0):
    return render.perspective_camera(loc, tgt, name=name, res=res, lens=lens)


def render_clip(arm, cid, out_mp4, step=2, res=(640, 360), cam=None):
    sc = bpy.context.scene
    act = bpy.data.actions[cid]
    arm.animation_data.action = act
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    tmp = tempfile.mkdtemp()
    n = 0
    for f in range(f0, f1 + 1, step):
        sc.frame_set(f)
        sc.render.filepath = os.path.join(tmp, f"f{n:05d}.png")
        sc.render.image_settings.file_format = "PNG"
        bpy.ops.render.render(write_still=True)
        n += 1
    fps = int(round(CL.FPS / step))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(tmp, "f%05d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", out_mp4], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    render.contact_sheet_from_video(out_mp4, out_mp4.replace(".mp4", "_sheet.png"), frames=8, width=1600)


KEYPOSES = [  # (art/05 panel, clip, time s)
    ("walk_contact_L", "lf_boss_walk", 0.0), ("walk_passing_1", "lf_boss_walk", 0.4),
    ("walk_contact_R", "lf_boss_walk", 0.8), ("walk_passing_2", "lf_boss_walk", 1.2),
    ("turn_anticipation", "lf_boss_turn_left", 0.25), ("turn_planted", "lf_boss_turn_left", 0.9),
    ("bite_windup", "lf_boss_jaw_arc", 2.2), ("bite_strike", "lf_boss_jaw_arc", 2.6),
    ("roar", "lf_boss_phase_roar", 1.3), ("tail_coil", "lf_boss_tail_sweep", 2.8),
    ("tail_release", "lf_boss_tail_sweep", 3.5), ("death_rest", "lf_boss_death", 5.2),
]


def keypose_sheet(arm, out_png):
    sc = bpy.context.scene
    cam_side("kp_cam", res=(560, 360), loc=(14.0, -3.0, 4.2), tgt=(0.0, -0.2, 1.6), lens=42.0)
    rows = []
    row = []
    for i, (panel, cid, t) in enumerate(KEYPOSES):
        act = bpy.data.actions[cid]
        arm.animation_data.action = act
        sc.frame_set(int(round(t * CL.FPS)))
        img = render.render_rgba()
        ref = R.keypose_panel(panel)
        import cv2
        h = 300
        ref_r = cv2.resize(ref, (int(ref.shape[1] * h / ref.shape[0]), h), interpolation=cv2.INTER_AREA)
        ren = img[..., :3]
        ren_r = cv2.resize(ren, (int(ren.shape[1] * h / ren.shape[0]), h), interpolation=cv2.INTER_AREA)
        pair = np.concatenate([ref_r, np.full((h, 6, 3), 0.15), ren_r], axis=1)
        u8 = (np.clip(pair, 0, 1) * 255).astype(np.uint8)
        u8 = render._label(u8, f"art/05 {panel}  |  {cid} t={t:.2f}s", (8, 6))
        row.append(u8)
        if len(row) == 2:
            w = max(r.shape[1] for r in row)
            row = [np.pad(r, ((0, 0), (0, w - r.shape[1]), (0, 0)), constant_values=30) for r in row]
            rows.append(np.concatenate([row[0], np.full((h, 10, 3), 30, np.uint8), row[1]], axis=1))
            row = []
    w = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 8), (0, w - r.shape[1]), (0, 0)), constant_values=30) for r in rows]
    core.save_rgba(out_png, np.concatenate(rows, axis=0) / 255.0)


if __name__ == "__main__":
    args = sys.argv[1:]
    bpy.ops.wm.open_mainfile(filepath=args[0])
    sc = scene_setup()
    sc.render.fps = CL.FPS
    arm = bpy.data.objects[ARM]
    clips = args[args.index("--clips") + 1].split(",") if "--clips" in args else list(CL.CLIPS)
    if "--no-keyposes" not in args:
        keypose_sheet(arm, C.qa("keyposes.png"))
    if "--no-videos" not in args:
        cam_side()
        for cid in clips:
            render_clip(arm, cid, C.qa_video(f"{cid}.mp4"))
            print("VIDEO", cid, flush=True)
