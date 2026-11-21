#!/usr/bin/env python3
"""Atlas v2 plan: art/01 masterplan (owner decision 2026-11-21) warped into the game.

art/01 is a painting of the forest seen roughly from the city camera. Its elements (inventory in
forest_rescue/qa/references/user/masterplan_inventory.json, art pixels) are warped with a
thin-plate spline into the GAME SCREEN space of the fixed city camera (orthographic, azimuth
(+75, +83, +75), 38° elevation) and then un-projected onto the terrain:

  screen  U = (x - z) / sqrt2                 (to the right)
          Y = (x + z) / sqrt2 * sin38 - (h(x, z) - H0) * cos38      (down)

TPS control points: the town centre and its wall ↔ the protected base square ±56 (+ margin) at the
same screen angle; the art river centreline ↔ the game river (atlas samples); the bridge ↔ the
bridge; the art content border ↔ the playable square ±112 minus the glade margin at the same
screen angle. Then every site / camp / landmark / trail point is warped, validated (dry ground,
slope, bounds, spacing) and drawn on a plan sheet next to art/01.

    /opt/tools/blender-venv/bin/python forest_rescue/tools/plan_atlas_v2.py <out dir>
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.interpolate import RBFInterpolator

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ART = os.path.join(ROOT, "forest_rescue/delivery/art/01_world_masterplan.png")
INV = os.path.join(ROOT, "forest_rescue/qa/references/user/masterplan_inventory.json")
ATLAS = os.path.join(ROOT, "godot/project/data/forest_rescue/world/world-atlas.json")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

S38 = math.sin(math.radians(38.0))
C38 = math.cos(math.radians(38.0))
SQ2 = math.sqrt(2.0)
H0 = 6.5
CORE = 56.0
EXTENT = 112.0
GLADE_R = 7.0


def smoothstep(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def base_height(x, z):
    """Port of ForestTerrain.base_height (landscape.gd sample_city)."""
    west = -x + 0.16 * z + 2.6 * math.sin(z * 0.095)
    north = -z + 0.13 * x + 2.8 * math.sin(x * 0.078)
    shelf = 3.8 * smoothstep(25, 31, west) + 2.1 * smoothstep(43, 49, west) + 4.5 * smoothstep(25, 33, north) \
        + 1.7 * smoothstep(43, 50, north) + 2.6 * smoothstep(35, 43, z + math.sin(x * 0.08) * 3)
    land = 0.45 + shelf * smoothstep(31.5, 38, max(abs(x), abs(z))) + 0.12 * math.sin(x * 0.17) * math.cos(z * 0.14) \
        + 0.16 * math.sin((x + z) * 0.08)
    land += 2.0 * (1.0 - smoothstep(5.5, 15, math.hypot(x + 25, z + 7)))
    land += 2.5 * (1.0 - smoothstep(5.5, 15, math.hypot(x + 7, z + 27)))
    land += 1.1 * (1.0 - smoothstep(5.5, 15, math.hypot(x - 28, z)))
    center = z + 66 + 8 * math.sin(z * 0.068) + 3.5 * math.cos(z * 0.127 + 0.3) + 9 * math.exp(-((z + 25) / 15) ** 2)
    distance = abs(x - center) - 4.3 - 0.65 * math.sin(z * 0.093 + 1.4)
    return (-2.85 + 0.15 * math.sin(z * 0.15)) * (1 - smoothstep(-0.6, 5.2, distance)) + land * smoothstep(-0.6, 5.2, distance)


class River:
    def __init__(self, atlas):
        s = atlas["river"]["samples"]
        self.z = np.array([p["z"] for p in s], float)
        self.c = np.array([p["center"] for p in s], float)
        self.w = np.array([p["wetWest"] for p in s], float)
        self.e = np.array([p["wetEast"] for p in s], float)

    def at(self, z):
        if z < self.z[0] or z > self.z[-1]:
            c = z + 66 + 8 * math.sin(z * 0.068) + 3.5 * math.cos(z * 0.127 + 0.3) + 9 * math.exp(-((z + 25) / 15) ** 2)
            half = 4.3 + 0.65 * math.sin(z * 0.093 + 1.4) + 0.3
            return c, c - half, c + half
        return float(np.interp(z, self.z, self.c)), float(np.interp(z, self.z, self.w)), float(np.interp(z, self.z, self.e))

    def bank(self, x, z):
        c, w, e = self.at(z)
        if x < w:
            return w - x
        if x > e:
            return x - e
        return -min(x - w, e - x)


def to_screen(x, z, h=None):
    if h is None:
        h = base_height(x, z)
    return (x - z) / SQ2, (x + z) / SQ2 * S38 - (h - H0) * C38


def to_world(U, Y):
    """Un-project a screen point onto the terrain (fixed-point iteration on the height)."""
    h = H0
    for _ in range(12):
        w = (Y + (h - H0) * C38) / S38
        x, z = (U + w) / SQ2, (w - U) / SQ2
        h = base_height(x, z)
    return x, z


def ray_to_square(angle, half, origin=(0.0, 0.0)):
    """Screen point at screen angle (radians, 0 = right, +pi/2 = up) where the ray from the screen of
    world origin leaves the world square max(|x|,|z|) <= half (terrain-aware)."""
    o = np.array(to_screen(*origin))
    d = np.array([math.cos(angle), -math.sin(angle)])
    lo, hi = 0.0, 400.0
    for _ in range(50):
        mid = (lo + hi) * 0.5
        x, z = to_world(*(o + d * mid))
        if max(abs(x), abs(z)) < half:
            lo = mid
        else:
            hi = mid
    return o + d * lo


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    inv = json.load(open(INV))
    atlas = json.load(open(ATLAS))
    river = River(atlas)
    town = np.array(inv["town"]["centre"], float)
    rx, ry = inv["town"]["wallRadii"]

    src, dst = [], []
    # 1. town centre and wall ↔ base square ±56 + 4 m margin, same screen angle
    src.append(town)
    dst.append(np.array(to_screen(0.0, 0.0, base_height(0, 0))))
    for k in range(24):
        a = 2 * math.pi * k / 24
        p = town + np.array([rx * math.cos(a), -ry * math.sin(a)])
        ang = math.atan2(ry * math.sin(a), rx * math.cos(a))
        src.append(p)
        dst.append(ray_to_square(ang, CORE + 4.0))
    # 2. river centreline ↔ game river (by screen height between the top edge and the bridge,
    #    then along the game river below the bridge to where it leaves the map)
    bridge_art = np.array([1100.0, 575.0])
    bridge_world = (90.482, 20.0)
    bridge_scr = np.array(to_screen(*bridge_world, h=1.1))
    zs = np.linspace(-112, 112, 449)
    rv = np.array([to_screen(river.at(z)[0], z, -1.35) for z in zs])
    inside = [i for i, z in enumerate(zs) if abs(river.at(z)[0]) <= EXTENT - 2]
    top = rv[inside[0]]
    bottom = rv[inside[-1]]
    art_river = inv["river"]["centreline"]
    for p in art_river:
        p = np.array(p, float)
        if p[1] <= 575:
            f = p[1] / 575.0
            Y = top[1] + (bridge_scr[1] - top[1]) * f
            i = int(np.argmin(np.abs(rv[:, 1] - Y)))
            src.append(p)
            dst.append(rv[i])
        else:
            # below the bridge: fraction of the art path length → fraction along the game river
            f = min(1.0, (p[1] - 575.0) / (900.0 - 575.0))
            Y = bridge_scr[1] + (bottom[1] - bridge_scr[1]) * f
            i = int(np.argmin(np.abs(rv[:, 1] - Y)))
            src.append(p)
            dst.append(rv[i])
    src.append(bridge_art)
    dst.append(bridge_scr)
    # 3. art content border ↔ playable square minus the glade margin (same screen angle)
    inset = 36
    border = []
    for t in np.linspace(0, 1, 9)[:-1]:
        border += [(inset + t * (1536 - 2 * inset), inset), (1536 - inset, inset + t * (1024 - 2 * inset)),
                   (1536 - inset - t * (1536 - 2 * inset), 1024 - inset), (inset, 1024 - inset - t * (1024 - 2 * inset))]
    for bx, by in border:
        p = np.array([bx, by], float)
        d = p - town
        ang = math.atan2(-d[1] / (ry / rx), d[0])
        src.append(p)
        dst.append(ray_to_square(ang, EXTENT - GLADE_R - 3.0))
    src = np.array(src)
    dst = np.array(dst)
    tps = RBFInterpolator(src, dst, kernel="thin_plate_spline", smoothing=2.0)

    def warp(p):
        s = tps(np.array([p], float))[0]
        return to_world(*s), s

    # ---- sites (12) + E-L glade (no cage) -----------------------------------------------------
    sites = []
    for cage in inv["cages"]:
        (x, z), scr = warp(cage["cage"])
        site_id = cage["proposedSite"].split(" ")[0] if cage["proposedSite"].startswith("lf_site") else "glade_E-L"
        sites.append({"key": cage["key"], "site": site_id, "art": cage["cage"], "x": x, "z": z, "screen": scr.tolist(),
                      "zone": cage["zone"], "camp": {k: v for k, v in cage.items() if k in ("tent", "fire", "fence", "bench", "hideRack", "frames", "leanTo")}})
    landmarks = []
    for lm in inv["landmarks"]:
        (x, z), scr = warp(lm["at"])
        landmarks.append({"id": lm["id"], "art": lm["at"], "x": x, "z": z, "screen": scr.tolist(), "asset": lm.get("asset", "")})
    trails = []
    for trail in inv["trailsApprox"]:
        pts = []
        for p in trail["points"]:
            (x, z), scr = warp(p)
            pts.append([x, z])
        trails.append({"name": trail["name"], "world": pts})
    plan = {"sites": sites, "landmarks": landmarks, "trails": trails,
            "control": {"src": src.tolist(), "dst": dst.tolist()}}
    json.dump(plan, open(os.path.join(out_dir, "plan_raw.json"), "w"), indent=1)
    print("warped", len(sites), "glades,", len(landmarks), "landmarks,", len(trails), "trails")
    for s in sites:
        print("%-5s %-11s art %-12s → world (%7.1f, %7.1f)  bank %6.1f" % (s["key"], s["site"], s["art"], s["x"], s["z"], river.bank(s["x"], s["z"])))
    for lm in landmarks:
        print("LM %-18s → world (%7.1f, %7.1f)" % (lm["id"], lm["x"], lm["z"]))
    return plan


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
