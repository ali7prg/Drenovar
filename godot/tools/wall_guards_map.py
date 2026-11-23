#!/usr/bin/env python3
"""Top-down maps of the wall guards (qa_wall_guards.gd --dump=DIR).

    python3 godot/tools/wall_guards_map.py DUMP_DIR OUT.png [LEVELS, default 1,3,5]
    python3 godot/tools/wall_guards_map.py --compare OURS.jpg REFERENCE.jpg OUT.jpg [x,y,w,h]


One panel per wall level: the wall line (gate openings in red), the towers (squares, gate towers
outlined in red), the walkable walkway stretches (grey), each patrol's beat (thick, its colour,
longbowmen orange / crossbowmen blue), the sentry posts on the towers (dots, a line between two
places of one sentry), the pair at the main gate, and the trails the guards walked in the QA run
(thin).
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

SIZE = 900
UNIT_COLOUR = {"ENG-03": (226, 132, 36), "ENG-04": (52, 112, 214)}


def font(size):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def panel(data):
    wall = data["wall"]
    xs = [p[0] for p in wall] or [0]
    zs = [p[1] for p in wall] or [0]
    cx, cz = (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2
    span = max(max(xs) - min(xs), max(zs) - min(zs), 40) + 16
    k = SIZE / span

    def at(x, z):
        return ((x - cx) * k + SIZE / 2, (z - cz) * k + SIZE / 2)

    im = Image.new("RGB", (SIZE, SIZE + 76), (238, 234, 222))
    d = ImageDraw.Draw(im)
    # wall line
    for i in range(len(wall)):
        a, b = wall[i], wall[(i + 1) % len(wall)]
        d.line([at(a[0], a[1]), at(b[0], b[1])], fill=(200, 40, 40) if a[2] else (90, 80, 70), width=3)
    for s in data["stretches"]:
        pts = [at(p[0], p[1]) for p in s["line"]]
        if len(pts) > 1:
            d.line(pts, fill=(170, 170, 170), width=5)
    for t in data["towers"]:
        half = t["size"] / 2
        ox, oz = t["out"]
        sx, sz = -oz, ox
        corners = []
        for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            corners.append(at(t["x"] + (sx * a + ox * b) * half, t["z"] + (sz * a + oz * b) * half))
        d.polygon(corners, fill=(150, 120, 90), outline=(200, 40, 40) if t["gate"] >= 0 else (60, 50, 40))
    g = data["gate"]
    gx, gz = at(g[0], g[1])
    d.rectangle([gx - 6, gz - 6, gx + 6, gz + 6], outline=(200, 40, 40), width=3)
    for i, trail in enumerate(data.get("trails", [])):
        if len(trail) > 1:
            d.line([at(p[0], p[1]) for p in trail], fill=(60, 60, 60), width=1)
    for guard in data["guards"]:
        colour = UNIT_COLOUR.get(guard["unit"], (0, 0, 0))
        beat = [at(p[0], p[1]) for p in guard["beat"]]
        if guard["role"] == "patrol" and len(beat) > 1:
            d.line(beat, fill=colour, width=6)
            for p in (beat[0], beat[-1]):
                d.ellipse([p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6], outline=colour, width=3)
        else:
            if len(beat) > 1:
                d.line(beat, fill=colour, width=2)
            for p in beat:
                r = 6 if guard["role"] == "tower" else 7
                d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=colour,
                          outline=(0, 0, 0) if guard["role"] == "gate" else colour)
    roles = {}
    units = {}
    for guard in data["guards"]:
        roles[guard["role"]] = roles.get(guard["role"], 0) + 1
        units[guard["unit"]] = units.get(guard["unit"], 0) + 1
    f = font(22)
    small = font(15)
    title = "Wall %s, hall %s: %d guards" % (["", "I", "II", "III", "IV", "V"][data["level"]],
                                              ["", "I", "II", "III", "IV", "V"][data["hall"]], len(data["guards"]))
    d.text((12, SIZE + 6), title, fill=(20, 20, 20), font=f)
    detail = "patrols %d, tower sentries %d, gate %d; longbow %d, crossbow %d" % (
        roles.get("patrol", 0), roles.get("tower", 0), roles.get("gate", 0), units.get("ENG-03", 0), units.get("ENG-04", 0))
    walkway = "walkway %s" % (
        ("top %.2f m, centre %+.2f m, free +-%.2f m" % (data["walk"]["top"], data["walk"]["offset"], data["walk"]["half"]))
        if data["walk"] else "none (towers only)")
    d.text((12, SIZE + 34), detail, fill=(40, 40, 40), font=small)
    d.text((12, SIZE + 52), walkway, fill=(40, 40, 40), font=small)
    return im


def compare(ours_path, ref_path, out, box=None):
    """Side by side at one height: our close wall shot, a crop of it round the guard (box
    "x,y,w,h" in the shot's pixels, scaled up as the reference's tiles are), and the reference."""
    ours = Image.open(ours_path).convert("RGB")
    ref = Image.open(ref_path).convert("RGB")
    h = 630
    panels = [("DRENOVAR build 1024: wall guards, zoom 28", ours)]
    if box:
        x, y, w, bh = [int(v) for v in box.split(",")]
        panels.append(("the same frame, %dx%d px round the patrol" % (w, bh), ours.crop((x, y, x + w, y + bh))))
    panels.append(("reference: " + os.path.basename(ref_path), ref))
    scaled = [(t, im.resize((round(im.width * h / im.height), h), Image.LANCZOS)) for t, im in panels]
    sheet = Image.new("RGB", (sum(im.width for _, im in scaled) + 10 * (len(scaled) - 1), h + 40), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    x = 0
    for title, im in scaled:
        sheet.paste(im, (x, 40))
        d.text((x + 10, 8), title, fill=(0, 0, 0), font=font(18))
        x += im.width + 10
    sheet.save(out, quality=88)
    print("compare", out, sheet.size)


def main():
    if sys.argv[1] == "--compare":
        compare(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else None)
        return
    src, out = sys.argv[1], sys.argv[2]
    levels = [int(v) for v in (sys.argv[3] if len(sys.argv) > 3 else "1,3,5").split(",")]
    panels = []
    for level in levels:
        path = os.path.join(src, "wall_guards_L%d.json" % level)
        if os.path.exists(path):
            with open(path) as fh:
                panels.append(panel(json.load(fh)))
    if not panels:
        sys.exit("no dumps in " + src)
    w = sum(p.width for p in panels) + 10 * (len(panels) - 1)
    sheet = Image.new("RGB", (w, panels[0].height + 40), (255, 255, 255))
    x = 0
    for p in panels:
        sheet.paste(p, (x, 40))
        x += p.width + 10
    d = ImageDraw.Draw(sheet)
    d.text((12, 8), "Wall guards: routes and posts (orange longbowmen, blue crossbowmen; thick = patrol beat, dots = posts, "
                    "grey = walkable walkway, red = gate openings / gate towers, thin = walked trails)",
           fill=(0, 0, 0), font=font(16))
    sheet.save(out)
    print("map", out, sheet.size)


if __name__ == "__main__":
    main()
