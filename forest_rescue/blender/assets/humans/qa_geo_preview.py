"""Geometry-only preview of a character (class colours): reference compares + 4 views.
Usage: run_limited.py qa_geo_preview.py <asset_id> <tag> [voxel]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

from frlib import core, paths

import humans_build as HBLD
import humans_qa as Q
import humans_sdf as H

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
asset, tag = argv[0], argv[1]
voxel = float(argv[2]) if len(argv) > 2 else 0.0045
ctx = HBLD.assemble(asset, voxel=voxel)
core.reset()
body = ctx.pieces[0]
cent = body.verts[np.array(body.faces)].mean(1)
idx, _ = H.owner([p for p in ctx.parts if getattr(p, "cls", None)], cent)
plist = [p for p in ctx.parts if getattr(p, "cls", None)]
cls = [plist[i].cls if i >= 0 else "body" for i in idx]
Q.preview_scene(ctx.pieces, body_cls=cls)
Q.workbench()
out = paths.ensure(paths.QA_COMPARE, asset)
m = Q.render_compares(ctx.views, out, f"{tag}_geo", f"{asset} {tag} geometry")
Q.render_views(os.path.join(out, f"{tag}_geo_views.png"))
tris = sum(p.ntris for p in ctx.pieces)
print("IOU", {k: v["iou"] for k, v in m.items()}, "tris_hi", tris)
