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
# v1 geography (the delivered atlas, never modified): river, fog spec, sites' campaign fields.
ATLAS = os.path.join(ROOT, "forest_rescue/delivery/data/world-atlas.json")
SERVER_V2 = os.path.join(ROOT, "forest_rescue/server/data/world-atlas.v2.json")
CLIENT_V2 = os.path.join(ROOT, "godot/project/data/forest_rescue/world/world-atlas.json")
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


def art_control_points():
    """(src art px, dst game screen (u, Y)) control pairs of the art/01 → game warp (see main)."""
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
    return np.array(src), np.array(dst)


def art_warps():
    """(art px → game screen, game screen → art px) thin-plate splines."""
    src, dst = art_control_points()
    return (RBFInterpolator(src, dst, kernel="thin_plate_spline", smoothing=2.0),
            RBFInterpolator(dst, src, kernel="thin_plate_spline", smoothing=2.0))


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    inv = json.load(open(INV))
    atlas = json.load(open(ATLAS))
    river = River(atlas)
    town = np.array(inv["town"]["centre"], float)
    rx, ry = inv["town"]["wallRadii"]
    src, dst = art_control_points()
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


if __name__ == "__main__" and (len(sys.argv) < 3):
    main(sys.argv[1] if len(sys.argv) > 1 else ".")


# ============================================================================================
# Constraint-resolved v2 plan (authored from the TPS warp; see the plan sheet). Positions are
# world XZ; every entry keeps its art/01 screen direction around the town (θ, CCW from screen
# right) and its side of the river; the TPS output is shown next to it on the sheet.
PLAN = {
    "sites": [
        # id, art key, x, z, zone
        ["lf_site_01", "NW-A", -80.0, -14.0, "grove"],
        ["lf_site_02", "NW-B", -86.0, 40.0, "grove"],
        ["lf_site_03", "W-C", -72.0, 74.0, "mixed"],
        ["lf_site_04", "W-D", -40.0, 87.0, "mixed"],
        ["lf_site_05", "SW-E", 2.0, 92.0, "quarry"],
        ["lf_site_06", "SW-F", 30.0, 101.0, "pines"],
        ["lf_site_07", "S-G", 57.0, 90.0, "pines"],
        ["lf_site_08", "S-H", 98.0, 85.0, "pines"],
        ["lf_site_09", "SE-I", 84.0, 47.0, "lake"],
        ["lf_site_10", "SE-J", 96.0, -20.0, "willows"],
        ["lf_site_11", "E-K", 92.0, -52.0, "willows"],
        ["lf_site_12", "NE-M", 42.0, -70.0, "arena_rock"],
    ],
    "extra_glades": [["lf_glade_el", "E-L", 72.0, -86.0, "willows"]],
    "landmarks": [
        ["hollow_oak_giant", -95.0, -6.0],
        ["ruined_arch", -70.0, 16.0],
        ["standing_stones", -62.0, -80.0],
        ["quarry_mine", -15.0, 100.0],
        ["dead_tree", 64.0, 76.0],
        ["hunter_shelter", 102.0, 64.0],
        ["waterfall_pond", 15.0, -70.0],
        ["lake_marsh", 101.0, 38.0],
        ["bridge", 90.482, 20.0],
        ["boss_arena", 18.0, -92.0],
    ],
    # junctions (server nodes) and trails (way polylines between named nodes, world XZ)
    "junctions": {
        "lf_horse_origin": [-8.0, -55.0], "lf_junction_corridor": [-12.0, -60.0],
        "lf_junction_stones": [-58.0, -69.0], "lf_junction_grove": [-75.0, -40.0], "lf_junction_w": [-66.0, 2.0],
        "lf_junction_wsw": [-63.0, 36.0], "lf_junction_sw": [-61.0, 63.0], "lf_junction_ssw": [-42.0, 69.0],
        "lf_junction_s": [-18.0, 65.0],
        "lf_junction_quarry": [-20.0, 84.0], "lf_junction_sse": [28.0, 64.0], "lf_junction_south": [48.0, 72.0],
        "lf_junction_se": [64.0, 52.0], "lf_junction_e": [64.0, 24.0],
        "lf_bridge_west": [77.0, 20.0], "lf_bridge_east": [104.0, 20.0],
        "lf_junction_ese": [106.0, -2.0], "lf_junction_ene": [97.0, -38.0], "lf_junction_ne": [57.0, -80.0],
        "lf_junction_waterfall": [25.0, -69.0],
    },
    "trails": [
        # [from, to, [intermediate XZ points]] — north: the mare's trail past the standing stones
        ["lf_horse_origin", "lf_junction_corridor", []],
        ["lf_junction_corridor", "lf_junction_stones", [[-26, -66], [-42, -71]]],
        ["lf_junction_stones", "lf_junction_grove", [[-70, -56]]],
        ["lf_junction_grove", "lf_site_01", [[-80, -28]]],
        ["lf_site_01", "hollow_oak_giant", []],
        # the grove loop and the inner west trail
        ["lf_junction_grove", "lf_junction_w", [[-67, -20]]],
        ["lf_site_01", "ruined_arch", [[-76, 2]]],
        ["lf_junction_w", "ruined_arch", []],
        ["ruined_arch", "lf_site_02", [[-80, 26]]],
        ["lf_junction_w", "lf_junction_wsw", [[-62, 18]]],
        ["lf_site_02", "lf_junction_wsw", [[-74, 40]]],
        ["lf_junction_wsw", "lf_junction_sw", [[-66, 50]]],
        # west and quarry
        ["lf_junction_sw", "lf_site_03", []],
        ["lf_site_03", "lf_site_04", [[-58, 86]]],
        ["lf_junction_sw", "lf_junction_ssw", [[-52, 67]]],
        ["lf_junction_ssw", "lf_junction_s", [[-30, 68]]],
        ["lf_junction_ssw", "lf_site_04", [[-43, 78]]],
        ["lf_site_04", "lf_junction_quarry", [[-30, 88]]],
        ["lf_junction_s", "lf_junction_quarry", [[-16, 74]]],
        ["lf_junction_quarry", "quarry_mine", []],
        ["lf_junction_quarry", "lf_site_05", [[-8, 92]]],
        ["lf_site_05", "lf_site_06", [[16, 100]]],
        # south: dark pines, dead tree, marsh
        ["lf_junction_s", "lf_junction_sse", [[6, 66]]],
        ["lf_junction_sse", "lf_junction_south", []],
        ["lf_junction_sse", "lf_site_06", [[25, 84]]],
        ["lf_junction_south", "lf_site_07", [[50, 82]]],
        ["lf_site_06", "lf_site_07", [[44, 98]]],
        ["lf_site_07", "dead_tree", []],
        ["lf_junction_south", "lf_junction_se", [[58, 62]]],
        ["lf_junction_se", "lf_site_08", [[80, 68], [92, 76]]],
        ["lf_site_07", "lf_site_08", [[78, 94]]],
        ["lf_junction_se", "lf_site_09", [[74, 50]]],
        ["lf_site_08", "hunter_shelter", []],
        ["lf_site_09", "hunter_shelter", [[92, 56]]],
        # the bridge and the east bank up to the arena
        ["lf_junction_se", "lf_junction_e", [[67, 38]]],
        ["lf_junction_e", "lf_bridge_west", []],
        ["lf_bridge_west", "lf_bridge_east", []],
        ["lf_bridge_east", "lf_junction_ese", []],
        ["lf_junction_ese", "lf_site_10", [[101, -12]]],
        ["lf_junction_ese", "lf_junction_ene", [[104, -22]]],
        ["lf_junction_ene", "lf_site_11", []],
        ["lf_site_11", "lf_glade_el", [[84, -72]]],
        ["lf_junction_ene", "lf_glade_el", [[82, -62]]],
        ["lf_glade_el", "lf_junction_ne", []],
        ["lf_junction_ne", "lf_site_12", [[50, -74]]],
        ["lf_junction_ne", "boss_arena", [[44, -86]]],
        ["lf_site_12", "lf_junction_waterfall", [[33, -71]]],
    ],
}


def screen_theta(x, z):
    u, w = (x - z) / SQ2, (x + z) / SQ2
    return math.degrees(math.atan2(-w, u)) % 360.0


def art_theta(p, town, rx, ry):
    dx, dy = (p[0] - town[0]) / rx, -(p[1] - town[1]) / ry
    return math.degrees(math.atan2(dy, dx)) % 360.0, math.hypot(dx, dy)


def validate(plan, river):
    rows = []
    glades = [(s[0], s[1], s[2], s[3]) for s in plan["sites"]] + [(g[0], g[1], g[2], g[3]) for g in plan["extra_glades"]]
    arena = next(l for l in plan["landmarks"] if l[0] == "boss_arena")
    for gid, key, x, z in glades:
        hs = [base_height(x + r * math.cos(a), z + r * math.sin(a)) for r in (0, 3, 6, 9) for a in np.linspace(0, 2 * math.pi, 12, endpoint=False)]
        bank = river.bank(x, z)
        cheb = max(abs(x), abs(z))
        near = min(math.hypot(x - g[2], z - g[3]) for g in glades if g[0] != gid)
        lm = min(math.hypot(x - l[1], z - l[2]) for l in plan["landmarks"] if l[0] not in ("boss_arena", "lake_marsh", "bridge"))
        arena_d = math.hypot(x - arena[1], z - arena[2])
        ok = bank >= 10 and 65 <= cheb <= 103 and near >= 20 and arena_d >= 30 and max(hs) - min(hs) <= 4.5
        rows.append({"id": gid, "key": key, "x": x, "z": z, "theta": screen_theta(x, z), "y": base_height(x, z),
                     "relief": max(hs) - min(hs), "bank": bank, "cheb": cheb, "nearest_glade": near, "nearest_landmark": lm,
                     "arena": arena_d, "ok": ok})
    return rows


def trail_points(plan):
    nodes = {k: v for k, v in plan["junctions"].items()}
    for s in plan["sites"]:
        nodes[s[0]] = [s[2], s[3]]
    for g in plan["extra_glades"]:
        nodes[g[0]] = [g[2], g[3]]
    for l in plan["landmarks"]:
        nodes[l[0]] = [l[1], l[2]]
    out = []
    for a, b, mid in plan["trails"]:
        pts = [nodes[a]] + [list(p) for p in mid] + [nodes[b]]
        out.append((a, b, pts))
    return nodes, out


def check_trails(plan, river):
    nodes, trails = trail_points(plan)
    report = []
    deck = (77.0 - 0.5, 104.0 + 0.5)
    for a, b, pts in trails:
        wet = 0
        steep = 0.0
        length = 0.0
        inside_core = 0
        for k in range(len(pts) - 1):
            p, q = np.array(pts[k], float), np.array(pts[k + 1], float)
            L = np.linalg.norm(q - p)
            length += L
            n = max(1, int(L / 1.0))
            prev_h = None
            for i in range(n + 1):
                r = p + (q - p) * i / n
                on_deck = abs(r[1] - 20.0) < 2.5 and deck[0] <= r[0] <= deck[1]
                if river.bank(r[0], r[1]) < 2.0 and not on_deck:
                    wet += 1
                if max(abs(r[0]), abs(r[1])) < 55.0 and not (a == "lf_horse_origin" or b == "lf_horse_origin"):
                    inside_core += 1
                h = 1.1 if on_deck else base_height(r[0], r[1])
                if prev_h is not None and not on_deck:
                    steep = max(steep, math.degrees(math.atan(abs(h - prev_h) / (L / n))))
                prev_h = h
        report.append({"from": a, "to": b, "length": length, "wet_samples": wet, "max_slope": steep, "core_samples": inside_core})
    return report


ZONE_COLORS = {"grove": (214, 170, 40), "mixed": (150, 160, 60), "quarry": (175, 168, 150), "pines": (40, 80, 70),
               "lake": (70, 140, 130), "willows": (95, 150, 80), "arena_rock": (165, 150, 120), "town": (110, 150, 70)}


def zone_of(x, z, river):
    cheb = max(abs(x), abs(z))
    if cheb < 56:
        return "town"
    th = screen_theta(x, z)
    east = river.bank(x, z) > 0 and x > river.at(z)[0]
    if cheb < 66 and not east:
        return "town"
    if east:
        if 20 <= th <= 80:
            return "arena_rock"
        return "willows"
    if 75 <= th < 160:
        return "grove"
    if 160 <= th < 208:
        return "mixed"
    if 208 <= th < 245:
        return "quarry"
    if 245 <= th < 300:
        return "pines"
    if 300 <= th < 345:
        return "lake"
    return "willows"


def draw_sheet(out_dir, plan, rows, trail_report, raw):
    river = River(json.load(open(ATLAS)))
    art = Image.open(ART).convert("RGB")
    inv = json.load(open(INV))
    town = np.array(inv["town"]["centre"], float)
    rx, ry = inv["town"]["wallRadii"]
    d = ImageDraw.Draw(art)
    f = ImageFont.truetype(BOLD, 20)
    for c in inv["cages"]:
        x, y = c["cage"]
        d.ellipse((x - 14, y - 14, x + 14, y + 14), outline=(255, 40, 40), width=4)
        d.text((x + 16, y - 12), c["key"], font=f, fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0))
    for l in inv["landmarks"]:
        x, y = l["at"]
        d.rectangle((x - 9, y - 9, x + 9, y + 9), outline=(40, 160, 255), width=4)
    # game screen plan: U right, Y down (flat ground projection), 3.4 px per m
    k = 3.3
    W, H = int(330 * k), int(210 * k)
    cx, cy = W // 2, H // 2
    plan_img = Image.new("RGB", (W, H), (34, 40, 44))
    px = plan_img.load()
    for j in range(0, H, 2):
        for i in range(0, W, 2):
            U = (i - cx) / k
            Y = (j - cy) / k
            w = Y / S38
            x, z = (U + w) / SQ2, (w - U) / SQ2
            if max(abs(x), abs(z)) > EXTENT:
                continue
            col = ZONE_COLORS[zone_of(x, z, river)]
            if river.bank(x, z) < 0:
                col = (50, 110, 170)
            for a in (0, 1):
                for b in (0, 1):
                    if i + a < W and j + b < H:
                        px[i + a, j + b] = col
    d2 = ImageDraw.Draw(plan_img)

    def S(x, z):
        u, w = (x - z) / SQ2, (x + z) / SQ2
        return cx + u * k, cy + w * S38 * k

    for half, colr, wd in ((CORE, (240, 230, 200), 3), (EXTENT, (230, 230, 230), 2)):
        corners = [S(-half, -half), S(half, -half), S(half, half), S(-half, half), S(-half, -half)]
        d2.line(corners, fill=colr, width=wd)
    nodes, trails = trail_points(plan)
    for a, b, pts in trails:
        d2.line([S(*p) for p in pts], fill=(236, 205, 140), width=4)
    for name, (x, z) in plan["junctions"].items():
        sx, sy = S(x, z)
        d2.ellipse((sx - 4, sy - 4, sx + 4, sy + 4), fill=(255, 230, 160))
    f2 = ImageFont.truetype(BOLD, 15)
    for r in rows:
        sx, sy = S(r["x"], r["z"])
        rr = 7 * k
        d2.ellipse((sx - rr, sy - rr * S38, sx + rr, sy + rr * S38), outline=(255, 255, 255) if r["ok"] else (255, 60, 60), width=3)
        label = (r["id"].replace("lf_site_", "S") if r["id"].startswith("lf_site") else "E-L") + " " + r["key"]
        d2.text((sx + 10, sy - 18), label, font=f2, fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0))
    for l in plan["landmarks"]:
        sx, sy = S(l[1], l[2])
        if l[0] == "boss_arena":
            rr = 15 * k
            d2.ellipse((sx - rr, sy - rr * S38, sx + rr, sy + rr * S38), outline=(255, 140, 40), width=4)
        elif l[0] == "lake_marsh":
            rr = 11 * k
            d2.ellipse((sx - rr, sy - rr * S38, sx + rr, sy + rr * S38), fill=(60, 120, 175), outline=(120, 190, 120), width=3)
        else:
            d2.rectangle((sx - 6, sy - 6, sx + 6, sy + 6), fill=(60, 170, 255), outline=(0, 0, 0))
        d2.text((sx + 8, sy + 4), l[0].replace("_", " "), font=ImageFont.truetype(FONT, 13), fill=(220, 240, 255), stroke_width=2, stroke_fill=(0, 0, 0))
    # TPS raw positions (faint) for reference
    for s in raw["sites"]:
        sx, sy = S(s["x"], s["z"])
        d2.line((sx - 5, sy - 5, sx + 5, sy + 5), fill=(255, 120, 120), width=2)
        d2.line((sx - 5, sy + 5, sx + 5, sy - 5), fill=(255, 120, 120), width=2)
    hx, hy = S(-8, -55)
    d2.ellipse((hx - 7, hy - 7, hx + 7, hy + 7), fill=(200, 60, 40))
    d2.text((hx + 8, hy - 4), "horse origin / corridor", font=ImageFont.truetype(FONT, 13), fill=(255, 220, 200), stroke_width=2, stroke_fill=(0, 0, 0))
    # compose: art (scaled) | plan
    art_s = art.resize((int(art.width * H / art.height), H), Image.LANCZOS)
    sheet = Image.new("RGB", (art_s.width + W + 20, H + 60), (24, 22, 20))
    sheet.paste(art_s, (0, 60))
    sheet.paste(plan_img, (art_s.width + 20, 60))
    dd = ImageDraw.Draw(sheet)
    dd.text((10, 14), "art/01 (user zones; cages red, landmarks blue)", font=ImageFont.truetype(BOLD, 22), fill=(250, 240, 220))
    dd.text((art_s.width + 30, 14), "proposed atlas v2 in the game camera's screen space (38° ortho; red x = raw TPS warp)",
            font=ImageFont.truetype(BOLD, 22), fill=(250, 240, 220))
    path = os.path.join(out_dir, "atlas_v2_plan.png")
    sheet.save(path)
    return path


def report(out_dir, plan, raw):
    river = River(json.load(open(ATLAS)))
    rows = validate(plan, river)
    trails = check_trails(plan, river)
    inv = json.load(open(INV))
    town = np.array(inv["town"]["centre"], float)
    rx, ry = inv["town"]["wallRadii"]
    arts = {c["key"]: c["cage"] for c in inv["cages"]}
    print("\n%-11s %-5s %8s %8s %7s %7s %6s %6s %6s %6s %6s %s" % ("glade", "art", "x", "z", "θ game", "θ art", "y", "relief", "bank", "cheb", "near", "ok"))
    for r in rows:
        ta, _ = art_theta(arts[r["key"]], town, rx, ry)
        r["theta_art"] = ta
        print("%-11s %-5s %8.1f %8.1f %7.1f %7.1f %6.2f %6.2f %6.1f %6.1f %6.1f %s" % (r["id"], r["key"], r["x"], r["z"], r["theta"], ta, r["y"], r["relief"], r["bank"], r["cheb"], r["nearest_glade"], "OK" if r["ok"] else "CHECK"))
    print("\ntrails: total %.0f m in %d ways; wet samples %d; max slope %.1f°" % (sum(t["length"] for t in trails), len(trails),
          sum(t["wet_samples"] for t in trails), max(t["max_slope"] for t in trails)))
    for t in trails:
        if t["wet_samples"] or t["max_slope"] > 22 or t["core_samples"]:
            print("  CHECK", t)
    sheet = draw_sheet(out_dir, plan, rows, trails, raw)
    json.dump({"rows": rows, "trails": trails}, open(os.path.join(out_dir, "atlas_v2_plan_checks.json"), "w"), indent=1)
    print("sheet", sheet)


if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[2] == "--report":
    raw = json.load(open(os.path.join(sys.argv[1], "plan_raw.json")))
    report(sys.argv[1], PLAN, raw)


def path_lengths(plan):
    """Shortest walk (m) from the home reception (via the horse origin) to every glade."""
    import heapq
    nodes, trails = trail_points(plan)
    graph = {}
    for a, b, pts in trails:
        L = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)) * 1.06   # + meander
        graph.setdefault(a, []).append((b, L))
        graph.setdefault(b, []).append((a, L))
    dist = {"lf_horse_origin": 3.0}
    queue = [(3.0, "lf_horse_origin")]
    while queue:
        d, n = heapq.heappop(queue)
        if d > dist.get(n, 1e9):
            continue
        for m, L in graph.get(n, []):
            if d + L < dist.get(m, 1e9):
                dist[m] = d + L
                heapq.heappush(queue, (d + L, m))
    return dist


def profile_check(plan):
    """Grade-limited road profile (≤ 12°) over the natural ground: worst cut/fill per trail."""
    nodes, trails = trail_points(plan)
    worst = []
    for a, b, pts in trails:
        dense = []
        for k in range(len(pts) - 1):
            p, q = np.array(pts[k], float), np.array(pts[k + 1], float)
            n = max(1, int(math.dist(p, q) / 0.5))
            for i in range(n):
                dense.append(p + (q - p) * i / n)
        dense.append(np.array(pts[-1], float))
        on_deck = [abs(r[1] - 20) < 2.5 and 76.5 <= r[0] <= 104.5 for r in dense]
        g = np.array([1.1 if on_deck[i] else base_height(r[0], r[1]) for i, r in enumerate(dense)])
        k = 16
        sm = np.array([g[max(0, i - k):i + k + 1].mean() for i in range(len(g))])
        lim = math.tan(math.radians(12.0)) * 0.5
        prof = sm.copy()
        for _ in range(3):
            for i in range(1, len(prof)):
                prof[i] = min(max(prof[i], prof[i - 1] - lim), prof[i - 1] + lim)
            for i in range(len(prof) - 2, -1, -1):
                prof[i] = min(max(prof[i], prof[i + 1] - lim), prof[i + 1] + lim)
        worst.append((a, b, float(np.max(np.abs(prof - g)))))
    return worst


ACTS = {"lf_site_01": 1, "lf_site_02": 1, "lf_site_03": 1, "lf_site_04": 2, "lf_site_05": 2, "lf_site_06": 2,
        "lf_site_07": 3, "lf_site_08": 3, "lf_site_09": 3, "lf_site_10": 4, "lf_site_11": 4, "lf_site_12": 4}


def table_sheet(out_dir, plan):
    river = River(json.load(open(ATLAS)))
    rows = validate(plan, river)
    walk = path_lengths(plan)
    prof = {(a, b): c for a, b, c in profile_check(plan)}
    inv = json.load(open(INV))
    town = np.array(inv["town"]["centre"], float)
    rx, ry = inv["town"]["wallRadii"]
    arts = {c["key"]: c["cage"] for c in inv["cages"]}
    head = ["glade", "art", "act", "x", "z", "θ art", "θ game", "Cheb", "y", "relief r9", "river bank", "nearest", "walk from home", "check"]
    lines = []
    for r in rows:
        ta, _ = art_theta(arts[r["key"]], town, rx, ry)
        lines.append([r["id"], r["key"], str(ACTS.get(r["id"], "-")), "%.0f" % r["x"], "%.0f" % r["z"], "%.0f°" % ta, "%.0f°" % r["theta"],
                      "%.0f" % r["cheb"], "%.1f" % r["y"], "%.1f m" % r["relief"], "%.0f m dry" % r["bank"] if r["bank"] >= 10 else "%.0f m WET" % r["bank"],
                      "%.0f m" % r["nearest_glade"], "%.0f m / %.0f s" % (walk.get(r["id"], 0), walk.get(r["id"], 0) / 2.4), "OK" if r["ok"] else "CHECK"])
    lm_lines = [["%s" % l[0], "(%.0f, %.0f)" % (l[1], l[2]), "%.0f°" % screen_theta(l[1], l[2])] for l in plan["landmarks"]]
    f = ImageFont.truetype(FONT, 17)
    fb = ImageFont.truetype(BOLD, 17)
    widths = [130, 64, 44, 60, 60, 74, 86, 64, 56, 100, 120, 90, 175, 70]
    W = max(sum(widths) + 40, 1500)
    H = 60 + 28 * (len(lines) + 2) + 30 + 26 * (len(lm_lines) + 2) + 220
    img = Image.new("RGB", (W, H), (28, 26, 24))
    d = ImageDraw.Draw(img)
    d.text((14, 14), "atlas v2 plan — glade centres (world XZ), screen direction around the town (art → game), dry / slope / spacing checks",
           font=ImageFont.truetype(BOLD, 19), fill=(250, 240, 220))
    y = 52
    x = 14
    for h, w in zip(head, widths):
        d.text((x, y), h, font=fb, fill=(255, 220, 160))
        x += w
    y += 30
    for row in lines:
        x = 14
        for v, w in zip(row, widths):
            d.text((x, y), v, font=f, fill=(255, 110, 110) if v in ("CHECK",) or "WET" in v else (235, 235, 230))
            x += w
        y += 28
    y += 16
    d.text((14, y), "landmarks (world XZ, screen θ)", font=fb, fill=(255, 220, 160))
    y += 28
    for row in lm_lines:
        d.text((14, y), "%-20s %-14s %s" % tuple(row), font=f, fill=(235, 235, 230))
        y += 26
    total = sum(math.dist(*seg) for _, _, pts in trail_points(plan)[1] for seg in zip(pts[:-1], pts[1:]))
    worst = max(prof.items(), key=lambda kv: kv[1])
    notes = ["trails: %d ways, %.0f m, no wet sample except the bridge deck; grade-limited profiles (≤ 12°) need ≤ %.1f m cut/fill (%s → %s)" %
             (len(plan["trails"]), total, worst[1], worst[0][0], worst[0][1]),
             "relief r9 = max − min natural ground height within 9 m of the glade centre (the glade pad flattens r 7 + 2 m blend)",
             "walk = shortest path from the home reception through the horse origin (fixed) at the squad speed 2.4 m/s (+6 % meander)",
             "all trips start at the north gate (home spur, entrance corridor (-8,-55)→(-12,-60) unchanged): an inner trail along the",
             "west and south walls links the radial trails; no cage stands on it; sites 10–12, the E-L glade and the arena are across the bridge"]
    y += 14
    for n in notes:
        d.text((14, y), n, font=ImageFont.truetype(FONT, 16), fill=(210, 210, 200))
        y += 24
    path = os.path.join(out_dir, "atlas_v2_plan_table.png")
    img.save(path)
    return path


if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[2] == "--table":
    print(table_sheet(sys.argv[1], PLAN))


# ============================================================================================
# Atlas v2 writer (after the plan checkpoint): sites, junction / landmark nodes, the trail network
# as ways (samples ≤ 0.5 m, grade-limited targetRoadY), the river with the reedy-lake widening
# and the waterfall pond, everything else (fog, streaming, zones, reserve masks) from v1.

LAKE = {"center": [101.0, 38.0], "radius": 11.0}
POND = {"center": [15.0, -70.0], "radius": 6.5}
LANDMARK_ROLES = {
    "hollow_oak_giant": "art/01 grove hero tree (lf_env_hollow_oak, hero scale)",
    "ruined_arch": "art/01 ruined arch (lf_env_ruined_watchpost)",
    "standing_stones": "art/01 stone row above the town (lf_env_standing_stones)",
    "quarry_mine": "art/01 quarry: mine mouth, crane, rails (lf_env_quarry_mine)",
    "dead_tree": "art/01 bare white dead tree, stone pillars, bones",
    "hunter_shelter": "art/01 hunter shelter by the marsh (lf_env_hunter_shelter)",
    "waterfall_pond": "art/01 waterfall from the east cliff into a pond with reeds",
    "lake_marsh": "art/01 reedy lake: the river widening south of the bridge",
}


def catmull(points, step=0.49):
    """Centripetal-ish Catmull-Rom through the control points, resampled to ≤ step."""
    pts = [np.array(p, float) for p in points]
    if len(pts) == 2:
        dense = [pts[0] + (pts[1] - pts[0]) * t for t in np.linspace(0, 1, 200)]
    else:
        ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
        dense = []
        for i in range(1, len(ext) - 2):
            p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
            for t in np.linspace(0, 1, 60, endpoint=False):
                t2, t3 = t * t, t * t * t
                dense.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
        dense.append(pts[-1])
    # arc-length resample
    seg = [np.linalg.norm(dense[i + 1] - dense[i]) for i in range(len(dense) - 1)]
    total = float(sum(seg))
    n = max(1, int(math.ceil(total / step - 1e-9)))
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    out = []
    for k in range(n + 1):
        s = total * k / n
        i = min(int(np.searchsorted(cum, s, side="right") - 1), len(dense) - 2)
        f = 0.0 if seg[i] < 1e-9 else (s - cum[i]) / seg[i]
        out.append(dense[i] + (dense[i + 1] - dense[i]) * f)
    out[0] = pts[0]
    out[-1] = pts[-1]
    return out


def road_profile(samples, on_deck):
    g = np.array([1.1 if on_deck[i] else base_height(p[0], p[1]) for i, p in enumerate(samples)])
    k = 16
    sm = np.array([g[max(0, i - k):i + k + 1].mean() for i in range(len(g))])
    lim = math.tan(math.radians(12.0)) * 0.5
    prof = sm.copy()
    for i, d in enumerate(on_deck):
        if d:
            prof[i] = 1.1
    for _ in range(4):
        for i in range(1, len(prof)):
            if not on_deck[i]:
                prof[i] = min(max(prof[i], prof[i - 1] - lim), prof[i - 1] + lim)
        for i in range(len(prof) - 2, -1, -1):
            if not on_deck[i]:
                prof[i] = min(max(prof[i], prof[i + 1] - lim), prof[i + 1] + lim)
    return g, prof


def write_atlas(server_path, client_path):
    v1 = json.load(open(ATLAS))
    atlas = json.loads(json.dumps(v1))
    atlas["id"] = "lost_forest_atlas_v2"
    atlas["schemaVersion"] = 2
    atlas["derivedFrom"] = {"atlas": v1["id"], "masterplan": "forest_rescue/delivery/art/01_world_masterplan.png",
                            "decision": "owner 2026-11-21: the in-game layout follows art/01 (zones, glades with cages and camps, "
                                        "landmarks, a branching network of winding trails)",
                            "tool": "forest_rescue/tools/plan_atlas_v2.py"}
    nodes, trails = trail_points(PLAN)
    # sites: new centres (pad height = natural ground at the centre), chunk ids, offsets unchanged
    by_id = {s["id"]: s for s in atlas["sites"]}
    for sid, key, x, z, zone in PLAN["sites"]:
        site = by_id[sid]
        site["center"] = {"x": x, "y": round(base_height(x, z), 5), "z": z}
        site["chunkId"] = "lf_chunk_%d_%d" % (min(3, max(0, int((x + 112) // 56))), min(3, max(0, int((z + 112) // 56))))
        site["masterplanKey"] = key
        site["status"] = "atlas_v2_masterplan"
    # landmarks: horse origin, bridge kept; arena moved; junctions, glade E-L, art landmarks added
    keep = [l for l in atlas["landmarks"] if l["id"] in ("lf_horse_origin", "lf_bridge_crossing")]
    arena = next(l for l in atlas["landmarks"] if l["id"] == "lf_boss_arena")
    ax, az = next((l[1], l[2]) for l in PLAN["landmarks"] if l[0] == "boss_arena")
    arena["center"] = {"x": ax, "y": round(base_height(ax, az), 5), "z": az}
    entry = np.array(PLAN["junctions"]["lf_junction_ne"]) - np.array([ax, az])
    arena["entranceYawDeg"] = round(math.degrees(math.atan2(entry[0], entry[1])), 2)
    arena["status"] = "atlas_v2_masterplan"
    landmarks = keep + [arena]
    for jid, (x, z) in PLAN["junctions"].items():
        if jid == "lf_horse_origin":
            continue
        landmarks.append({"id": jid, "center": {"x": x, "y": round(base_height(x, z), 5), "z": z}, "role": "trail junction (nav node)"})
    for gid, key, x, z, zone in PLAN["extra_glades"]:
        landmarks.append({"id": gid, "center": {"x": x, "y": round(base_height(x, z), 5), "z": z}, "clearingRadius": 7,
                          "role": "glade with a camp, no cage (art/01 %s)" % key})
    for lid, x, z in PLAN["landmarks"]:
        if lid in ("bridge", "boss_arena"):
            continue
        landmarks.append({"id": "lf_mark_" + lid, "center": {"x": x, "y": round(base_height(x, z), 5), "z": z},
                          "role": LANDMARK_ROLES.get(lid, lid)})
    atlas["landmarks"] = landmarks
    # node ids used by the trails: art landmark names → lf_mark_*, bridge/arena → atlas ids
    def node_id(n):
        if n == "boss_arena":
            return "lf_boss_arena"
        if n in LANDMARK_ROLES:
            return "lf_mark_" + n
        return n
    routes = []
    deck_x = (77.0, 104.0)
    for a, b, pts in trails:
        rid = "lf_route_bridge" if {a, b} == {"lf_bridge_west", "lf_bridge_east"} else "lf_trail_%s__%s" % (node_id(a).replace("lf_", ""), node_id(b).replace("lf_", ""))
        if rid == "lf_route_bridge":
            n = int(math.ceil((deck_x[1] - deck_x[0]) / 0.49))
            samples = [np.array([deck_x[0] + (deck_x[1] - deck_x[0]) * i / n, 20.0]) for i in range(n + 1)]
            if a == "lf_bridge_east":
                samples.reverse()
        else:
            samples = catmull(pts)
        on_deck = [rid == "lf_route_bridge" for _ in samples]
        g, prof = road_profile(samples, on_deck)
        routes.append({"id": rid, "from": node_id(a), "to": node_id(b), "width": 2.4, "clearVegetationRadius": 3.0,
                       "controls": [{"x": round(float(p[0]), 3), "z": round(float(p[1]), 3)} for p in pts],
                       "geometry": "Catmull-Rom through the controls, resampled at <=0.5 units",
                       "traversal": "walk+bridge" if rid == "lf_route_bridge" else "walk",
                       "samples": [{"x": round(float(p[0]), 5), "y": round(float(g[i]), 5), "z": round(float(p[1]), 5),
                                    "targetRoadY": round(float(prof[i]), 5)} for i, p in enumerate(samples)]})
    atlas["routes"] = routes
    # river: reedy lake (widening south of the bridge) and the waterfall pond on the east bank
    river = River(v1)
    for s in atlas["river"]["samples"]:
        z = s["z"]
        for spec, side in ((LAKE, "west"), (POND, "east")):
            cx, cz = spec["center"]
            r = spec["radius"]
            if abs(z - cz) < r:
                half = math.sqrt(r * r - (z - cz) ** 2)
                if side == "west":
                    s["wetWest"] = round(min(s["wetWest"], cx - half), 5)
                else:
                    s["wetEast"] = round(max(s["wetEast"], cx + half), 5)
    atlas["river"]["features"] = {"lake": LAKE, "pond": POND,
                                  "note": "wet bounds widened for the reedy lake (west of the channel) and the waterfall pond (east bank)"}
    atlas["runtimeCopy"] = {"source": "forest_rescue/server/data/world-atlas.v2.json", "copiedBy": "integration agent 2026-11-21"}
    for path in (server_path, client_path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(atlas, open(path, "w"), ensure_ascii=False, indent=None, separators=(",", ":"))
    print("atlas v2:", len(atlas["sites"]), "sites,", len(atlas["landmarks"]), "landmarks,", len(routes), "routes,",
          sum(len(r["samples"]) for r in routes), "samples →", server_path, client_path)


if __name__ == "__main__" and len(sys.argv) > 3 and sys.argv[1] == "--write":
    write_atlas(sys.argv[2], sys.argv[3])
