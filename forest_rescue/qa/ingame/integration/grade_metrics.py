#!/usr/bin/env python3
"""Per-zone colour metrics of the in-game frames against the art/01 crops (pass 2 colour grade).

vegetation saturation = mean HSV saturation of vegetation pixels (hue 35°–170°, value > 0.12,
saturation > 0.12); luminance contrast = standard deviation of Rec.601 luma over the frame's forest
pixels (fog-shell / out-of-map pixels — low-saturation blue-grey — excluded). The art crop is the one
compose_v2.py puts beside each frame (warped centre, capped local scale).

    /opt/tools/blender-venv/bin/python forest_rescue/qa/ingame/integration/grade_metrics.py <shots dir> <prefix>
"""
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compose_v2 as C  # noqa: E402


def metrics(img):
    a = np.asarray(img.convert("RGB")).astype(float) / 255.0
    mx = a.max(-1)
    mn = a.min(-1)
    sat = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    hue = np.degrees(np.arctan2(np.sqrt(3) * (g - b), 2 * r - g - b)) % 360
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    fog = (sat < 0.16) & (b >= r - 0.02) & (luma > 0.3)
    forest = ~fog
    veg = forest & (hue > 35) & (hue < 170) & (mx > 0.12) & (sat > 0.12)
    return {"veg_sat": float(sat[veg].mean()) if veg.any() else 0.0,
            "contrast": float(luma[forest].std()) if forest.any() else 0.0,
            "luma": float(luma[forest].mean()) if forest.any() else 0.0,
            "veg_frac": float(veg.mean())}


def main():
    shots, prefix = sys.argv[1], sys.argv[2]
    art = Image.open(C.ART).convert("RGB")
    fwd, inv = C.P.art_warps()
    rows = {}
    for name, target, _caption in C.ZONES:
        path = os.path.join(shots, prefix + "full_%s_z68.png" % name)
        if not os.path.exists(path):
            continue
        game = Image.open(path)
        crop, _box = C.art_crop(art, inv, target, 68.0, (C.W, C.H))
        g = metrics(game)
        r = metrics(crop)
        rows[name] = {"game": g, "art": r, "sat_ratio": g["veg_sat"] / max(r["veg_sat"], 1e-6),
                      "contrast_ratio": g["contrast"] / max(r["contrast"], 1e-6)}
        print("%-13s sat game %.3f art %.3f ratio %.2f | contrast game %.3f art %.3f ratio %.2f | luma %.2f/%.2f"
              % (name, g["veg_sat"], r["veg_sat"], rows[name]["sat_ratio"], g["contrast"], r["contrast"],
                 rows[name]["contrast_ratio"], g["luma"], r["luma"]))
    if rows:
        sr = np.array([v["sat_ratio"] for v in rows.values()])
        cr = np.array([v["contrast_ratio"] for v in rows.values()])
        print("mean sat ratio %.2f (min %.2f max %.2f), mean contrast ratio %.2f (min %.2f max %.2f)"
              % (sr.mean(), sr.min(), sr.max(), cr.mean(), cr.min(), cr.max()))
    json.dump(rows, open(os.path.join(shots, prefix + "grade_metrics.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
