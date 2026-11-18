"""Render the captive variants (captive_variants.json) of each civilian base as lineups.
python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/humans/qa_variants.py"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import numpy as np

from frlib import core, paths, render

import qa_clips as QC


def set_factor(mat, rgb):
    for n in mat.node_tree.nodes:
        if n.type == "MIX" and n.blend_type == "MULTIPLY":
            n.inputs[7].default_value = (*rgb, 1.0)
            return True
    return False


def main():
    data = json.load(open(paths.runtime("humans", "captive_variants.json"), encoding="utf-8"))
    outdir = paths.ensure(paths.QA_COMPARE, "humans_variants")
    by_base = {}
    for cid, c in data["captives"].items():
        by_base.setdefault(c["base"], []).append((cid, c))
    for base, items in by_base.items():
        asset = f"lf_civilian_{base}"
        arm = QC.open_master(asset)
        render.studio(engine="BLENDER_EEVEE", samples=24)
        acts = bpy.data.actions
        if "lf_civilian_cage_stand" in acts:
            QC.set_pose(arm, "lf_civilian_cage_stand", 0.0)
        imgs, labels = [], []
        mats = {m.name: m for m in bpy.data.materials}
        defaults = {m.name: tuple(m.get("tint_factor", (1, 1, 1))) for m in mats.values() if m.get("tint_factor")}
        for cid, c in items:
            for mn, f in defaults.items():
                set_factor(mats[mn], f)
            for mn, f in c["materials"].items():
                if mn in mats:
                    set_factor(mats[mn], f)
            for o in bpy.data.objects:
                if "_opt_" in o.name and o.name.endswith("_LOD0"):
                    part = o.name.split("_opt_")[1].rsplit("_LOD", 1)[0]
                    vis = c["parts"].get(part, bool(o.get("default_on", True)))
                    o.hide_render = not vis
            img = QC.render_rgba((1.3, -3.2, 1.25), (0, 0, 0.88), lens=50, res=(300, 480))
            imgs.append(img)
            labels.append(f"{cid[-4:]} {c['name']}")
        render.side_by_side(imgs, labels, os.path.join(outdir, f"{base}_variants.png"), height=420)
        print("VARIANTS", base, len(items), flush=True)


if __name__ == "__main__":
    main()
