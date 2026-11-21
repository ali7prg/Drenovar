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


# art/01 per-zone estimates (8 x 4 grid read on each zone's art rect, land = ground outside the town, the fog
# and the water): canopy cover and meadow share of the land
ART_ESTIMATE = {"grove": (0.65, 0.22), "stones": (0.52, 0.25), "west": (0.56, 0.22), "quarry": (0.45, 0.10),
                "south_pines": (0.76, 0.08), "lake": (0.60, 0.10), "river_bridge": (0.60, 0.12), "east": (0.65, 0.12),
                "waterfall": (0.62, 0.12), "arena": (0.55, 0.10)}


def geometric(zone, step=1.0):
    """Game canopy cover / meadow share of the frame's land from the layout: union of crown discs, trails
    (2.4 m), glade pads (8.5 m), water (lake / pond / marsh / river) excluded from the meadow."""
    lay = json.load(open(LAYOUT))
    atlas = json.load(open(os.path.join(ROOT, "godot/project/data/forest_rescue/world/world-atlas.json")))
    names = {t["id"]: t["name"] for t in json.load(open(GAME_JSON))["woods"]}
    uc, yc = C.P.to_screen(zone["target"][0], zone["target"][1], 0.0)
    half_u = zone["zoom"] * C.W / C.H / 2
    half_y = zone["zoom"] / 2
    # ground grid covering the frame
    xs = np.arange(-140, 140, step)
    X, Z = np.meshgrid(xs, xs)
    U = (X - Z) / math.sqrt(2)
    Y = (X + Z) / math.sqrt(2) * math.sin(math.radians(38)) + 6.5 * math.cos(math.radians(38)) * 0  # ground ~ datum
    inside = (np.abs(U - uc) < half_u) & (np.abs(Y - yc) < half_y)
    land = inside & ((np.abs(X) > 56) | (np.abs(Z) > 56)) & (np.abs(X) <= 112) & (np.abs(Z) <= 112)
    crowns = np.zeros_like(land)
    trees = [(t[0], t[1], CROWN_RADIUS[int(t[2])] * float(t[5])) for t in lay["trees"]]
    trees += [(e[0], e[1], CROWN_RADIUS[0 if names.get(k) == "Дуб" else 1] * float(e[4])) for k, e in lay["resourceRemap"].items()]
    for (x, z, r) in trees:
        i0, i1 = int((x - r + 140) / step), int((x + r + 140) / step) + 1
        j0, j1 = int((z - r + 140) / step), int((z + r + 140) / step) + 1
        sub = (X[j0:j1, i0:i1] - x) ** 2 + (Z[j0:j1, i0:i1] - z) ** 2 < r * r
        crowns[j0:j1, i0:i1] |= sub
    open_ground = np.zeros_like(land)
    for r in atlas["routes"]:
        for smp in r["samples"][::2]:
            i, j = int((smp["x"] + 140) / step), int((smp["z"] + 140) / step)
            open_ground[max(0, j - 1):j + 2, max(0, i - 1):i + 2] = True
    for s_ in atlas["sites"]:
        c = s_["center"]
        open_ground |= (X - c["x"]) ** 2 + (Z - c["z"]) ** 2 < 8.5 ** 2
    water = np.zeros_like(land)
    for smp in atlas["river"]["samples"]:
        j = int((smp["z"] + 140) / step)
        if 0 <= j < len(xs):
            water[j, (xs >= smp["wetWest"]) & (xs <= smp["wetEast"])] = True
    land &= ~water
    n = max(1, int(land.sum()))
    cover = float((crowns & land).sum()) / n
    meadow = float((land & ~crowns & ~open_ground).sum()) / n
    return cover, meadow


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
        big = [x for x in d if x >= 8.0]
        import grade_metrics as GM
        ga = GM.metrics(Image.open(gpath).convert("RGB"))
        aa = GM.metrics(art.crop((x0, y0, x1, y1)))
        gc, gm = geometric(zone)
        ae = ART_ESTIMATE.get(zone["name"], (0.6, 0.15))
        row = {"art": a, "game": g, "art_crown_m": ART_CROWN.get(zone["name"], 10.0),
               "art_cover_est": ae[0], "art_meadow_est": ae[1], "game_cover_geo": gc, "game_meadow_geo": gm,
               "veg_sat_ratio": ga["veg_sat"] / max(aa["veg_sat"], 1e-6), "contrast_ratio": ga["contrast"] / max(aa["contrast"], 1e-6),
               "game_crown_m_median": float(np.median(d)) if d else 0.0,
               "game_crown_m_median_visible": float(np.median(big)) if big else 0.0, "game_trees": len(d)}
        rows[zone["name"]] = row
        print("%-13s cover art %3.0f%% game %3.0f%% | meadow art %3.0f%% game %3.0f%% | crown art %4.1f m game %4.1f m "
              "(canopy trees %4.1f, n=%d) | meadow HSV art (%3.0f %.2f %.2f) game (%3.0f %.2f %.2f) | veg sat x%.2f contrast x%.2f" % (
                  zone["name"], ae[0] * 100, gc * 100, ae[1] * 100, gm * 100,
                  row["art_crown_m"], row["game_crown_m_median"], row["game_crown_m_median_visible"], len(d),
                  *a["meadow_hsv"], *g["meadow_hsv"], row["veg_sat_ratio"], row["contrast_ratio"]))
    json.dump(rows, open(os.path.join(shots, "v3_forest_metrics.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
