"""Markdown tables for the QA reports (plain python): tris per LOD/variant and IoU per iteration."""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
QA = os.path.join(REPO, "forest_rescue", "qa", "compare")
RT = os.path.join(REPO, "godot", "project", "assets", "forest_rescue")


def tris_table(group, asset):
    p = os.path.join(RT, group, f"{asset}.meta.json")
    if not os.path.exists(p):
        return f"_{asset}: not exported_\n"
    m = json.load(open(p))
    if "variants" in m:
        rows = ["| variant | LOD0 | LOD1 | LOD2 | height m | canopy/footprint r m |", "|---|---|---|---|---|---|"]
        for vn, v in m["variants"].items():
            t = v["tris"]
            r = v.get("crown_radius_m", v.get("footprint_radius_m"))
            rows.append(f"| {vn} | {t['LOD0']} | {t['LOD1']} | {t['LOD2']} | {v.get('height_m')} | {r} |")
        return "\n".join(rows) + "\n"
    t = m["tris"]
    return f"| LOD0 | LOD1 | LOD2 |\n|---|---|---|\n| {t['LOD0']} | {t['LOD1']} | {t['LOD2']} |\n"


def iou_table(asset):
    rows = []
    for f in sorted(glob.glob(os.path.join(QA, asset, "iter*_*.json"))):
        name = os.path.basename(f)[:-5]
        if name.endswith("metrics"):
            continue
        d = json.load(open(f))
        if "iou" in d:
            rows.append(f"| {name} | {d['iou']:.3f} | {d.get('iou_closed_r4', float('nan')):.3f} | {d.get('mean_abs_colour_error', 0):.3f} |")
    if not rows:
        return "_no silhouette metrics_\n"
    return "| comparison | IoU | IoU closed r4 | mean abs colour err |\n|---|---|---|---|\n" + "\n".join(rows) + "\n"


if __name__ == "__main__":
    group, asset = sys.argv[1], sys.argv[2]
    print(tris_table(group, asset))
    print(iou_table(asset))
