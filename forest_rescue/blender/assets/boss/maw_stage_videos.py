"""Stage 6: clip videos (side + game camera), contact sheets and foot-slide report from maw_anim.blend.

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/boss/maw_stage_videos.py [--clips a,b] [--views side,game]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maw_common as C  # noqa: E402
import bpy  # noqa: E402

import maw_videos as MV  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--clips", default="")
ap.add_argument("--views", default="side,game")
ap.add_argument("--src", default=C.cache("maw_anim.blend"))
ap.add_argument("--tag", default="")
args = ap.parse_args(sys.argv[1:])
bpy.ops.wm.open_mainfile(filepath=args.src)
MV.run_all(args.tag, views=tuple(args.views.split(",")), clips=args.clips.split(",") if args.clips else None)
