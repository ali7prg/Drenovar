#!/usr/bin/env python3
"""Layout pass 3 per-zone table, art/01 vs game: median crown diameter (m), canopy cover %, meadow share %,
meadow ground hue / saturation / value, vegetation saturation and luminance contrast.

* Cover / meadow / ground colour come from the same pixel classifier on both panels of a zone (art rect of
  zones_v3.json, game frame v3_zone_<name>.png), resampled to ~5 px/m: canopy = foliage (textured or dark
  green / golden), meadow = smooth light yellow-green grass, trail = light tan, water = blue, fog = blue-grey
  mist (excluded with water and trails from the land area). Shares are of the land pixels.
* Crown diameters: game from the layout (2 x Rules.CROWN_RADIUS x scale of every outer tree in the zone's
  frame); art from the coordinator's art/01 measurement (~5.9 px/m: oak crowns 60-100 px = 10-17 m, pine
  crowns 30-40 px = 5-7 m), weighted by the zone's art species mix.

    /opt/tools/blender-venv/bin/python forest_rescue/qa/ingame/integration/forest_metrics_v3.py <shots dir>
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../../../.."))
sys.path.insert(0, HERE)
import compose_v2 as C  # noqa: E402

LAYOUT = os.path.join(ROOT, "godot/project/data/forest_rescue/world/forest_layout_v2.json")
GAME_JSON = os.path.join(ROOT, "godot/project/assets/game.json")
CROWN_RADIUS = [7.0, 3.0, 3.8, 5.4, 6.4, 7.0]
ART_PX_PER_M = 5.9
# art/01 crown diameter medians (m) by zone, from the oak / pine crown sizes and the zone's art species mix
ART_CROWN = {"grove": 14.0, "stones": 12.5, "west": 12.0, "quarry": 8.5, "south_pines": 6.5, "lake": 7.0,
             "river_bridge": 10.0, "east": 10.5, "waterfall": 10.0, "arena": 8.0}


def classify(rgb):
    a = rgb.astype(float) / 255.0
    mx, mn = a.max(-1), a.min(-1)
    v = mx
    s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    hue = np.degrees(np.arctan2(np.sqrt(3) * (g - b), 2 * r - g - b)) % 360
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    tex = np.sqrt(np.maximum(ndi.uniform_filter(lum * lum, 5) - ndi.uniform_filter(lum, 5) ** 2, 0))
    fog = (s < 0.18) & (b >= r - 0.03) & (lum > 0.32)
    water = (hue > 165) & (hue < 230) & (s > 0.22) & ~fog
    trail = (hue > 18) & (hue < 52) & (s > 0.18) & (s < 0.62) & (v > 0.58) & (tex < 0.06)
    meadow = (hue >= 45) & (hue < 100) & (s > 0.28) & (v > 0.42) & (tex < 0.055) & ~trail
    canopy = ~(fog | water | trail | meadow) & (((hue >= 30) & (hue < 170) & (s > 0.18)) | (v < 0.33)) & ~fog
    land = ~(fog | water | trail)
    return dict(canopy=canopy, meadow=meadow, trail=trail, water=water, fog=fog, land=land, hue=hue, sat=s, val=v)


def resample(img, px_per_m, target=5.0):
    k = target / px_per_m
    return np.asarray(img.resize((max(8, int(img.width * k)), max(8, int(img.height * k))), Image.LANCZOS))


def stats(rgb):
    c = classify(rgb)
    land = max(1, int(c["land"].sum()))
    m = c["meadow"]
    return {"cover": float(c["canopy"].sum()) / land, "meadow": float(m.sum()) / land,
            "meadow_hsv": [float(np.median(c["hue"][m])) if m.any() else 0.0, float(np.median(c["sat"][m])) if m.any() else 0.0,
                           float(np.median(c["val"][m])) if m.any() else 0.0]}


def layout_crowns(zone):
    lay = json.load(open(LAYOUT))
    names = {t["id"]: t["name"] for t in json.load(open(GAME_JSON))["woods"]}
    uc, yc = C.P.to_screen(zone["target"][0], zone["target"][1], 0.0)
    half_u = zone["zoom"] * C.W / C.H / 2
    half_y = zone["zoom"] / 2
    diam = []
    for t in lay["trees"]:
        u, y = C.P.to_screen(t[0], t[1])
        if abs(u - uc) < half_u and abs(y - yc) < half_y:
            diam.append(2 * CROWN_RADIUS[int(t[2])] * float(t[5]))
    for tid, e in lay["resourceRemap"].items():
        u, y = C.P.to_screen(e[0], e[1])
        if abs(u - uc) < half_u and abs(y - yc) < half_y:
            sp = 0 if names.get(tid) == "Дуб" else 1
            diam.append(2 * CROWN_RADIUS[sp] * float(e[4]))
    return diam


def main():
    shots = sys.argv[1]
    zones = json.load(open(os.path.join(HERE, "zones_v3.json")))["zones"]
    art = Image.open(C.ART).convert("RGB")
    rows = {}
    for zone in zones:
        gpath = os.path.join(shots, "v3_zone_%s.png" % zone["name"])
        if not os.path.exists(gpath):
            continue
        x0, y0, x1, y1 = zone["art_rect"]
        a = stats(resample(art.crop((x0, y0, x1, y1)), ART_PX_PER_M))
        g = stats(resample(Image.open(gpath).convert("RGB"), C.H / float(zone["zoom"])))
        d = layout_crowns(zone)
        big = [x for x in d if x >= 4.0]
        row = {"art": a, "game": g, "art_crown_m": ART_CROWN.get(zone["name"], 10.0),
               "game_crown_m_median": float(np.median(d)) if d else 0.0,
               "game_crown_m_median_visible": float(np.median(big)) if big else 0.0, "game_trees": len(d)}
        rows[zone["name"]] = row
        print("%-13s cover art %4.0f%% game %4.0f%% | meadow art %4.0f%% game %4.0f%% | crown art %4.1f m game %4.1f m "
              "(visible %4.1f, n=%d) | meadow HSV art (%3.0f %.2f %.2f) game (%3.0f %.2f %.2f)" % (
                  zone["name"], a["cover"] * 100, g["cover"] * 100, a["meadow"] * 100, g["meadow"] * 100,
                  row["art_crown_m"], row["game_crown_m_median"], row["game_crown_m_median_visible"], len(d),
                  *a["meadow_hsv"], *g["meadow_hsv"]))
    json.dump(rows, open(os.path.join(shots, "v3_forest_metrics.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
