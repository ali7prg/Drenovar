#!/usr/bin/env python3
"""Layout pass 3: same-region comparison frames. Each zone is defined by its art/01 rect; the game frame is
derived from that rect through the layout's own art -> game-screen mapping (plan_atlas_v2.art_warps, the
thin-plate spline the atlas v2 was built with), so both panels show the same content. Anchors (cages /
sites, landmarks) are listed with their art pixel and world position for markers on both panels.

    /opt/tools/blender-venv/bin/python forest_rescue/qa/ingame/integration/zone_frames.py
writes forest_rescue/qa/ingame/integration/zones_v3.json (read by qa_forest_integration_shots.gd --shots=v3
and compose_v2.py --v3).
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../../../.."))
sys.path.insert(0, os.path.join(ROOT, "forest_rescue/tools"))
import plan_atlas_v2 as P  # noqa: E402

FRAME = (1366, 630)
# art/01 rects (x0, y0, x1, y1) in the 1536 x 1024 painting, ~2.17:1 like the game frame
ZONES = [
    ("grove", (60, 60, 560, 290), "golden-oak grove, glade 01 (NW-A), hollow oak"),
    ("stones", (450, 50, 950, 280), "standing stones and the mare's trail above the town"),
    ("west", (60, 270, 560, 500), "west: golden + green oaks, glades 02 / 03, ruined arch"),
    ("quarry", (40, 600, 540, 830), "SW quarry: mine, crane, ledges, glade 05 (SW-E)"),
    ("south_pines", (470, 760, 970, 990), "dark pines: glade 07 (S-G), dead tree, marsh pools"),
    ("lake", (950, 600, 1450, 830), "reedy lake, glade 09 (SE-I), hunter shelter"),
    ("river_bridge", (850, 450, 1350, 680), "the bridge (four towers, red banners)"),
    ("east", (1036, 300, 1536, 530), "east bank willows: glades 10 / 11"),
    ("waterfall", (980, 330, 1480, 560), "waterfall into the lily pond below the arena"),
    ("arena", (950, 20, 1450, 250), "the arena on its outcrop, glade E-L, glade 12"),
]
GAME_ZOOM_RANGE = (40.0, 120.0)
ART_HEIGHT = 400          # px: the art rects are grown around their centre to ~zoom 68 (art/01 ~5.9 px/m)


def grown(rect):
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    h = ART_HEIGHT
    w = h * FRAME[0] / FRAME[1]
    cx = min(max(cx, w / 2), 1536 - w / 2)
    cy = min(max(cy, h / 2), 1024 - h / 2)
    return (int(round(cx - w / 2)), int(round(cy - h / 2)), int(round(cx + w / 2)), int(round(cy + h / 2)))


def rect_frame(fwd, rect):
    x0, y0, x1, y1 = rect
    pts = np.array([(x, y) for x in np.linspace(x0, x1, 5) for y in np.linspace(y0, y1, 5)], float)
    scr = fwd(pts)
    u0, u1 = scr[:, 0].min(), scr[:, 0].max()
    v0, v1 = scr[:, 1].min(), scr[:, 1].max()
    uc, vc = (u0 + u1) / 2, (v0 + v1) / 2
    aspect = FRAME[1] / FRAME[0]
    zoom = max(v1 - v0, (u1 - u0) * aspect)
    zoom = min(max(zoom, GAME_ZOOM_RANGE[0]), GAME_ZOOM_RANGE[1])
    x, z = P.to_world(uc, vc)
    return (float(x), float(z)), float(zoom), (float(uc), float(vc))


def anchors(inv, atlas_world, fwd, rect):
    x0, y0, x1, y1 = rect
    out = []
    for cage in inv["cages"]:
        site = cage["proposedSite"].split(" ")[0] if cage["proposedSite"].startswith("lf_site") else "lf_glade_el"
        a = cage["cage"]
        if x0 <= a[0] <= x1 and y0 <= a[1] <= y1 and site in atlas_world:
            out.append({"id": site, "label": cage["key"], "art": a, "world": atlas_world[site]})
    for lm in inv["landmarks"]:
        a = lm["at"]
        key = {"hollow_oak_giant": "lf_mark_hollow_oak_giant", "ruined_arch": "lf_mark_ruined_arch",
               "standing_stones": "lf_mark_standing_stones", "quarry_mine": "lf_mark_quarry_mine",
               "dead_tree": "lf_mark_dead_tree", "hunter_shelter": "lf_mark_hunter_shelter",
               "waterfall": "lf_junction_waterfall", "lake_marsh": "lf_mark_lake_marsh",
               "bridge": "lf_bridge_crossing", "boss_arena": "lf_boss_arena",
               "horse_and_squad": "lf_horse_origin"}.get(lm.get("id", lm.get("key")), "")
        if key and key in atlas_world and x0 <= a[0] <= x1 and y0 <= a[1] <= y1:
            out.append({"id": key, "label": lm.get("id", lm.get("key")), "art": a, "world": atlas_world[key]})
    return out


def main():
    inv = json.load(open(P.INV))
    atlas = json.load(open(os.path.join(ROOT, "godot/project/data/forest_rescue/world/world-atlas.json")))
    world = {s["id"]: [s["center"]["x"], s["center"]["z"]] for s in atlas["sites"]}
    for lm in atlas["landmarks"]:
        world[lm["id"]] = [lm["center"]["x"], lm["center"]["z"]]
    fwd, inv_w = P.art_warps()
    zones = []
    for name, rect0, caption in ZONES:
        rect = grown(rect0)
        target, zoom, uv = rect_frame(fwd, rect)
        anc = anchors(inv, world, fwd, rect)
        if len(anc) >= 2:
            # the layout's own placement: fit art px -> game screen (U, Y) on the zone's anchors (uniform scale +
            # translation), so every anchor lands at the same place in both panels
            A = np.array([a["art"] for a in anc], float)
            B = np.array([P.to_screen(a["world"][0], a["world"][1]) for a in anc], float)
            ac, bc = A.mean(0), B.mean(0)
            s = float(np.sum((A - ac) * (B - bc)) / max(np.sum((A - ac) ** 2), 1e-9))
            s = abs(s) if s != 0 else 0.25
            t = bc - s * ac
            x0, y0, x1, y1 = rect
            centre = s * np.array([(x0 + x1) / 2, (y0 + y1) / 2]) + t
            zoom = float(min(max(s * (y1 - y0) * max(1.0, (x1 - x0) / (y1 - y0) * FRAME[1] / FRAME[0]), GAME_ZOOM_RANGE[0]),
                             GAME_ZOOM_RANGE[1]))
            x, z = P.to_world(centre[0], centre[1])
            target, uv = (float(x), float(z)), (float(centre[0]), float(centre[1]))
        zones.append({"name": name, "caption": caption, "art_rect": list(rect), "target": [round(target[0], 2), round(target[1], 2)],
                      "zoom": round(zoom, 1), "screen_centre": [round(uv[0], 2), round(uv[1], 2)],
                      "anchors": anc})
        print("%-13s art %s -> target (%.1f, %.1f) zoom %.1f anchors %d" % (name, rect, target[0], target[1], zoom,
                                                                           len(zones[-1]["anchors"])))
    out = os.path.join(HERE, "zones_v3.json")
    json.dump({"frame": FRAME, "camera": "city ortho, offset (75, 83, 75), size = zoom (vertical metres)",
               "mapping": "plan_atlas_v2.art_warps (art px -> game screen U, Y metres; Y = (x+z)/sqrt2 sin38 - (h-6.5) cos38)",
               "zones": zones}, open(out, "w"), indent=1)
    print("->", out)


if __name__ == "__main__":
    main()
