#!/usr/bin/env python3
"""Top-down debug map of the townsfolk (build 1024) from qa_townsfolk.gd --dump=DIR:
building footprints (grey), yards (tan), solid ground of the buildings (dark), streets (paving),
the town square, standing trees (green dots, 0.9 m rings), water (blue), the wall, gate posts,
troop ground / parade / sites (red hatch), the walk graph (thin: live, red: cut) and every
person's trail over 120 simulated seconds (one colour per person).

    python3 godot/tools/townsfolk_map.py DIR/townsfolk_hall5.json OUT.png [--solids assets/city/town_solids.json]
"""
import base64
import json
import sys

from PIL import Image, ImageDraw, ImageFont

SCALE = 9.0  # pixels per metre
HALF = 64.0
COLOURS = [(230, 25, 75), (60, 180, 75), (255, 225, 25), (0, 130, 200), (245, 130, 48), (145, 30, 180),
           (70, 240, 240), (240, 50, 230), (210, 245, 60), (250, 190, 212), (0, 128, 128), (220, 190, 255),
           (170, 110, 40), (255, 250, 200), (128, 0, 0), (170, 255, 195)]


def px(x, z):
    return ((x + HALF) * SCALE, (z + HALF) * SCALE)


def main():
    src, out = sys.argv[1], sys.argv[2]
    solids_path = None
    if "--solids" in sys.argv:
        solids_path = sys.argv[sys.argv.index("--solids") + 1]
    d = json.load(open(src))
    size = int(HALF * 2 * SCALE)
    img = Image.new("RGB", (size, size), (120, 140, 96))
    draw = ImageDraw.Draw(img, "RGBA")
    for x, z in d["water"]:
        a = px(x - 0.5, z - 0.5)
        b = px(x + 0.5, z + 0.5)
        draw.rectangle([a, b], fill=(66, 119, 124))
    for lot in d["lots"]:
        r = lot["rect"]
        draw.rectangle([px(r[0], r[1]), px(r[0] + r[2], r[1] + r[3])], fill=(176, 150, 110), outline=(120, 100, 70))
    pl = d["plaza"]
    if pl[2] > 0:
        draw.rectangle([px(pl[0], pl[1]), px(pl[0] + pl[2], pl[1] + pl[3])], fill=(190, 190, 180))
    for s in d["segments"]:
        h = s[4] * 0.5
        x0, z0, x1, z1 = min(s[0], s[2]) - h, min(s[1], s[3]) - h, max(s[0], s[2]) + h, max(s[1], s[3]) + h
        colour = (200, 200, 190, 255) if not s[5] else (160, 160, 150, 160)
        if s[5]:
            draw.line([px(s[0], s[1]), px(s[2], s[3])], fill=colour, width=int(s[4] * SCALE))
        else:
            draw.rectangle([px(x0, z0), px(x1, z1)], fill=colour)
    for lot in d["lots"]:
        r = lot["body"]
        draw.rectangle([px(r[0], r[1]), px(r[0] + r[2], r[1] + r[3])], outline=(60, 60, 60, 255), width=2)
    if solids_path:
        table = json.load(open(solids_path))["types"]
        for lot, at in zip(d["lots"], d.get("lot_at", [])):
            entry = table.get(lot["type"], {}).get(str(max(1, min(5, int(lot["level"])))))
            if not entry or entry["w"] == 0:
                continue
            bits = base64.b64decode(entry["bits"])
            w, h = entry["w"], entry["h"]
            for cz in range(h):
                for cx in range(w):
                    i = cz * w + cx
                    if bits[i >> 3] >> (i & 7) & 1:
                        x = at[0] + (entry["x0"] + cx) * 0.25
                        z = at[1] + (entry["z0"] + cz) * 0.25
                        draw.rectangle([px(x, z), px(x + 0.25, z + 0.25)], fill=(50, 40, 35, 150))
    for r in d["blocked"]:
        draw.rectangle([px(r[0], r[1]), px(r[0] + r[2], r[1] + r[3])], outline=(220, 30, 30, 255), width=3, fill=(220, 30, 30, 40))
    if d["wall"]:
        pts = [px(x, z) for x, z in d["wall"]]
        draw.line(pts + [pts[0]], fill=(90, 70, 50, 255), width=7)
    for x, z in d["trees"]:
        c = px(x, z)
        r = 0.9 * SCALE
        draw.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], outline=(20, 70, 20, 200), width=1)
        draw.ellipse([c[0] - 3, c[1] - 3, c[0] + 3, c[1] + 3], fill=(20, 90, 20, 255))
    for x, z in d["posts"]:
        c = px(x, z)
        draw.rectangle([c[0] - 3, c[1] - 3, c[0] + 3, c[1] + 3], fill=(240, 240, 240, 255))
    for e in d["edges"]:
        colour = (40, 40, 40, 200) if e[5] else (255, 0, 0, 220)
        draw.line([px(e[0], e[1]), px(e[2], e[3])], fill=colour, width=1)
    for i, trail in enumerate(d["trails"]):
        colour = COLOURS[i % len(COLOURS)]
        if len(trail) > 1:
            draw.line([px(x, z) for x, z in trail], fill=colour + (230,), width=2)
        for x, z in trail[::12]:
            c = px(x, z)
            draw.ellipse([c[0] - 2, c[1] - 2, c[0] + 2, c[1] + 2], fill=colour + (255,))
    for x, z in d["doors"]:
        c = px(x, z)
        draw.ellipse([c[0] - 5, c[1] - 5, c[0] + 5, c[1] + 5], outline=(255, 255, 255, 255), width=2)
    for x, z in d["spots"]:
        c = px(x, z)
        draw.rectangle([c[0] - 5, c[1] - 5, c[0] + 5, c[1] + 5], outline=(255, 255, 0, 255), width=2)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
    except OSError:
        font = ImageFont.load_default()
    y = 8
    draw.rectangle([4, 4, 380, 26 + 18 * len(d["people"])], fill=(0, 0, 0, 150))
    draw.text((10, y), "hall %d: %d people, 120 s (north up, 1 m = %d px)" % (d["hall"], len(d["people"]), SCALE), fill=(255, 255, 255), font=font)
    for i, person in enumerate(d["people"]):
        y += 18
        draw.text((10, y), "%s  %s" % (person["key"].split("#")[0], person["visual"]), fill=COLOURS[i % len(COLOURS)], font=font)
    img.save(out)


if __name__ == "__main__":
    main()
