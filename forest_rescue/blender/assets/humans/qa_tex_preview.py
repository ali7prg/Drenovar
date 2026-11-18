"""Textured LOD0 preview (no rig): reference compares + views.  run_limited.py qa_tex_preview.py <asset> <tag>"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import numpy as np

from frlib import core, paths, render

import humans_build as HBLD
import humans_pipeline as PL
import humans_qa as Q

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
asset, tag = argv[0], argv[1]
ctx = HBLD.assemble(asset, voxel=0.0035)
core.reset()
spec = ctx.spec
budget = getattr(spec, "BUDGET", {"body": 6800, "beard": 450})
lod0, classes = PL.build_lod0(ctx, budget)
hi = [PL.obj_from_piece(p, "hi_" + p.name) for p in ctx.pieces if not p.meta.get("optional")]
tex = PL.texture_lod0(ctx, lod0, classes, size=2048, hi_objs=hi)
tp = PL.save_textures(asset, tex)
PL.make_materials(asset, lod0, classes, spec, tp, tex["factors"])
print("factors", tex["factors"], "tris", core.tri_count(lod0))
render.studio(engine="BLENDER_EEVEE", samples=32)
out = paths.ensure(paths.QA_COMPARE, asset)
m = Q.render_compares(ctx.views, out, f"{tag}", f"{asset} {tag}")
Q.render_views(os.path.join(out, f"{tag}_views.png"))
print("IOU", {k: v["iou"] for k, v in m.items()}, {k: v["mean_abs_colour_error"] for k, v in m.items()})
core.save_blend(os.path.join(paths.ensure(paths.SOURCES, "humans", "_wip"), f"{asset}_{tag}.blend"))
