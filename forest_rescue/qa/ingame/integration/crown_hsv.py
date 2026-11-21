#!/usr/bin/env python3
"""Layout pass 4: crown colour per zone, art/01 vs game (same-region frames of zones_v3.json).

conifer crowns: blue-green / teal pixels (hue 95-215, S >= 0.10), open water (bright saturated cyan) and mist
(S < 0.10) excluded; deciduous crowns: textured yellow-green / golden pixels (hue 28-100, S >= 0.28, local luma
std >= 0.04, V <= 0.8). Reports mean H / S / V, the 10th-percentile V (the shaded side) and the pixel share.

    /opt/tools/blender-venv/bin/python forest_rescue/qa/ingame/integration/crown_hsv.py <shots dir> [zone ...]
"""
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compose_v2 as C  # noqa: E402


def hsv(a):
    a = a.astype(float) / 255.0
    mx, mn = a.max(-1), a.min(-1)
    s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    h = np.degrees(np.arctan2(np.sqrt(3) * (g - b), 2 * r - g - b)) % 360
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    tex = np.sqrt(np.maximum(ndi.uniform_filter(lum * lum, 5) - ndi.uniform_filter(lum, 5) ** 2, 0))
    return h, s, mx, tex


def classes(img):
    h, s, v, tex = hsv(np.asarray(img.convert("RGB")))
    water = (h > 172) & (h < 215) & (s > 0.32) & (v > 0.38)
    conifer = (h >= 95) & (h <= 215) & (s >= 0.10) & (v >= 0.04) & (v <= 0.85) & ~water
    decid = (h >= 28) & (h < 100) & (s >= 0.28) & (tex >= 0.04) & (v <= 0.8)
    return h, s, v, conifer, decid


def stats(h, s, v, m):
    if m.sum() < 50:
        return None
    return {"H": float(np.median(h[m])), "S": float(s[m].mean()), "V": float(v[m].mean()),
            "V10": float(np.percentile(v[m], 10)), "share": float(m.mean())}


def main():
    shots = sys.argv[1]
    want = sys.argv[2:]
    zones = json.load(open(os.path.join(HERE, "zones_v3.json")))["zones"]
    art = Image.open(C.ART).convert("RGB")
    out = {}
    for zone in zones:
        if want and zone["name"] not in want:
            continue
        p = os.path.join(shots, "v3_zone_%s.png" % zone["name"])
        if not os.path.exists(p):
            continue
        x0, y0, x1, y1 = zone["art_rect"]
        ah, as_, av, ac, ad = classes(art.crop((x0, y0, x1, y1)))
        gh, gs, gv, gc, gd = classes(Image.open(p))
        row = {"conifer": {"art": stats(ah, as_, av, ac), "game": stats(gh, gs, gv, gc)},
               "deciduous": {"art": stats(ah, as_, av, ad), "game": stats(gh, gs, gv, gd)}}
        out[zone["name"]] = row
        for cls in ("conifer", "deciduous"):
            a, g = row[cls]["art"], row[cls]["game"]
            if a and g:
                print("%-13s %-9s art H%3.0f S%.2f V%.2f V10 %.2f | game H%3.0f S%.2f V%.2f V10 %.2f | S x%.2f V x%.2f V10 x%.2f" % (
                    zone["name"], cls, a["H"], a["S"], a["V"], a["V10"], g["H"], g["S"], g["V"], g["V10"],
                    g["S"] / a["S"], g["V"] / a["V"], g["V10"] / max(a["V10"], 1e-3)))
    json.dump(out, open(os.path.join(shots, "crown_hsv.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
