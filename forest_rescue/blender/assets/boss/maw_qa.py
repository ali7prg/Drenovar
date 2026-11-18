"""QA renders for the Ancient Maw: ortho compares with IoU, head close-up, keyposes, clip videos.

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/boss/maw_qa.py \
    --blend <maw_tex|master .blend> --iter 01 [--what compare,head,keyposes,clips]
"""
import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maw_common as C  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from frlib import core, refs, render  # noqa: E402
import maw_refs as R  # noqa: E402
from maw_pose import Poser  # noqa: E402

AID = C.ASSET_ID
GREY = (0.78, 0.77, 0.775)


def log(*a):
    print("[maw_qa]", *a, flush=True)


def turnaround_pose(ps):
    """Bind pose + drawn stance: jaw closed, right leg stepped back, right arm forward (sheet left view)."""
    ps.reset()
    ps.rot("jaw", (1, 0, 0), -2.0)
    ps.leg_ik("R", (-0.66, 1.13, 0.78), (-0.66, 1.03, 0.14), pole_dir=(0.1, -1.0, 0.0))
    ps.rot("upperarm_R", (1, 0, 0), -18)
    ps.rot("forearm_R", (1, 0, 0), -14)
    ps.rot("forearm_L", (1, 0, 0), -8)
    ps.rot("hand_L", (1, 0, 0), 10)
    ps.leg_ik("L", (0.66, 0.0, 0.86), (0.66, -0.13, 0.18))


def setup_scene(samples=32):
    render.studio(bg=GREY, engine="CYCLES", samples=samples, key_dir=(-0.45, -0.55, 0.70), key_energy=3.4,
                  fill_energy=1.1, rim_energy=1.2, ambient=0.55)
    sc = bpy.context.scene
    sc.view_settings.view_transform = "Standard"
    for o in bpy.data.objects:
        if o.type == "MESH":
            vis = o.name.endswith("_LOD0")
            o.hide_render = not vis
    return sc


def compare(iter_tag):
    arm = bpy.data.objects[f"{AID}_rig"]
    ps = Poser(arm)
    turnaround_pose(ps)
    ps.apply()
    bpy.context.view_layer.update()
    setup_scene(32)
    out = {}
    for v in (R.side_view(corrected=True), R.side_view(corrected=False), R.front_view()):
        if v.name == "front":   # the front drawing stands symmetric: bind stance, jaw closed
            ps.reset()
            ps.rot("jaw", (1, 0, 0), -2.0)
            ps.apply()
            bpy.context.view_layer.update()
        render.camera_for_view(v)
        rgba = render.render_rgba()
        png = C.qa_compare(f"iter{iter_tag}_{v.name}.png")
        m = render.compare(v, rgba, png, title=f"{AID} iter{iter_tag} {v.name} (turnaround pose)")
        out[v.name] = m
        log(v.name, m["iou"], m["mean_abs_colour_error"])
    core.write_json(C.qa_compare(f"iter{iter_tag}_metrics.json"), out)
    return out


def head_closeup(iter_tag):
    arm = bpy.data.objects[f"{AID}_rig"]
    ps = Poser(arm)
    turnaround_pose(ps)
    ps.rot("jaw", (1, 0, 0), 31)
    ps.rot("head", (1, 0, 0), -4)
    ps.rot("tongue_01", (1, 0, 0), 4)
    ps.apply()
    bpy.context.view_layer.update()
    setup_scene(48)
    P = ps.matrices()
    hc = ps.head("head", P) + Vector((0, -0.55, -0.15))
    az, el, dist = math.radians(28), math.radians(9), 4.6
    loc = hc + Vector((math.cos(az), -math.sin(az), math.tan(el))) * dist
    render.perspective_camera(tuple(loc), tuple(hc + Vector((0, 0.15, 0))), lens=50, res=(840, 705))
    rgba = render.render_rgba()
    ref = R.head_closeup()
    png = C.qa_compare(f"iter{iter_tag}_head_closeup.png")
    render.side_by_side([ref, rgba], ["reference head close-up (art/03)", f"render iter{iter_tag}"], png,
                        height=560)
    log("head", png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", default=C.cache("maw_tex.blend"))
    ap.add_argument("--iter", default="01")
    ap.add_argument("--what", default="compare,head")
    args = ap.parse_args(sys.argv[1:])
    bpy.ops.wm.open_mainfile(filepath=args.blend)
    what = args.what.split(",")
    if "compare" in what:
        compare(args.iter)
    if "head" in what:
        head_closeup(args.iter)
    if "keyposes" in what:
        import maw_keyposes
        maw_keyposes.run(args.iter)


if __name__ == "__main__":
    main()
