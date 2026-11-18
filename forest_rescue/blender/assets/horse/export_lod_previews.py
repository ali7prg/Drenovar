"""Export single-LOD preview GLBs of lf_horse_origin for the Godot viewer (QA only).

The game GLB carries LOD0/LOD1/LOD2 as three skinned meshes on one armature (the integrator
switches them); the viewer would draw all three at once, so QA uses one-LOD copies:
    qa/video/lf_horse_origin/preview/lf_horse_origin_LOD{0,1,2}.glb
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

import bpy  # noqa: E402

from frlib import core, paths  # noqa: E402

ASSET = "lf_horse_origin"


def main():
    bpy.ops.wm.open_mainfile(filepath=paths.source("horse", f"{ASSET}.blend"))
    arm = bpy.data.objects[f"{ASSET}_rig"]
    out_dir = paths.ensure(paths.QA_VIDEO, ASSET, "preview")
    for lod in (0, 1, 2):
        mesh = bpy.data.objects[f"{ASSET}_LOD{lod}"]
        out = os.path.join(out_dir, f"{ASSET}_LOD{lod}.glb")
        core.export_glb(out, [arm, mesh],
                        extra=dict(export_force_sampling=False, export_optimize_animation_size=False,
                                   export_image_format="AUTO", export_tangents=True))
        print("PREVIEW", out, os.path.getsize(out) // 1024, "KB")


if __name__ == "__main__":
    main()
