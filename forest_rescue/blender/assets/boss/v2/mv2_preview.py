"""Quick grey/textured previews of the current stage .blend (Workbench), for modelling iterations.

blender-python mv2_preview.py <stage_blend> <out_png> [pose]
pose: rest | test  (test = jaw open 30 deg, neck turned, left leg raised, tail bent, blink)
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mv2_common as C  # noqa: E402
from frlib import core, render  # noqa: E402


def setup_workbench(color="MATERIAL"):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = color
    sh.single_color = (0.55, 0.5, 0.42)
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.show_shadows = False
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"


def test_pose(arm):
    def r(b, axis, deg):
        pb = arm.pose.bones.get(b)
        if pb:
            pb.rotation_quaternion = Quaternion(Vector(axis), math.radians(deg)) @ pb.rotation_quaternion
    r("jaw", (1, 0, 0), 30)
    r("neck_01", (0, 0, 1), 10)
    r("neck_02", (0, 0, 1), 10)
    r("thigh_L", (1, 0, 0), 35)
    r("shin_L", (1, 0, 0), -50)
    for i in range(1, 13):
        r(f"tail_{i:02d}", (0, 0, 1), 5)
    r("lid_up_L", (1, 0, 0), 40)
    r("lid_lo_L", (1, 0, 0), -25)


def shots(out_png, pose="rest", size=640):
    setup_workbench()
    arm = bpy.data.objects.get(C.ASSET_ID + "_rig")
    if arm and pose == "test":
        test_pose(arm)
    bpy.context.view_layer.update()
    for o in bpy.data.objects:
        if o.name in ("maw_high", "maw_bake_src"):
            o.hide_render = True
    cams = [("left", (12, 0.3, 2.0), (0, 0.3, 1.8), 11.0), ("front", (0, -14, 2.0), (0, 0, 1.8), 5.0),
            ("rear34", (8, 12, 6), (0, 0.3, 1.6), 11.0), ("front34", (7, -9, 4.2), (0, -0.6, 1.8), 10.0),
            ("head", (2.6, -5.6, 3.6), (0, -3.85, 3.0), 2.4), ("top", (0, 0.3, 25), (0, 0.3, 0), 11.0)]
    imgs = []
    for name, loc, tgt, osz in cams:
        render.perspective_camera(loc, tgt, name="prev_cam", res=(size, int(size * 0.62)), ortho_scale=osz)
        imgs.append(render.render_rgba())
    render.side_by_side(imgs[:3], [c[0] for c in cams[:3]], out_png.replace(".png", "_a.png"), height=int(size * 0.62))
    render.side_by_side(imgs[3:], [c[0] for c in cams[3:]], out_png.replace(".png", "_b.png"), height=int(size * 0.62))


if __name__ == "__main__":
    blend, out = sys.argv[-3], sys.argv[-2]
    pose = sys.argv[-1]
    bpy.ops.wm.open_mainfile(filepath=blend)
    shots(out, pose)
