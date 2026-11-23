#!/usr/bin/env python3
"""Before/after evidence for the townsfolk (build 1024) from two qa_townsfolk.gd --dump=DIR runs.

    python3 godot/tools/townsfolk_evidence.py BEFORE_DIR AFTER_DIR OUT_DIR

Writes:
  coverage_hall{1,3,5}.png  where people walk in 120 s, before | after: each 1 m cell coloured
                            by how many different people crossed it (light blue 1 ... dark 6+),
                            with the share of the streets and the square they reached.
  visible_over_time.png     people on screen and not behind a building every 0.5 s for 120 s,
                            halls III and V, the default view (zoom 70) and the hall close up
                            (zoom 34), before (orange) and after (blue), min / mean in the legend.
Prints the numbers it draws.
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HALF = 64.0
CELL = 1.0
SCALE = 5.0  # pixels per metre on the coverage maps
SURFACE = (252, 252, 251)
TEXT = (11, 11, 11)
TEXT_2 = (82, 81, 78)
GRID = (226, 225, 221)
BEFORE = (235, 104, 52)  # categorical slot 2 (orange)
AFTER = (42, 120, 214)  # categorical slot 1 (blue)
# Sequential blue, light -> dark: 1, 2, 3, 4, 5, 6+ people.
RAMP = [(183, 211, 246), (134, 182, 239), (85, 152, 231), (42, 120, 214), (37, 106, 191), (16, 66, 129)]


def font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/" + name, size)
    except OSError:
        return ImageFont.load_default()


def cells_of_trail(trail):
    """The 1 m cells a trail crosses (straight between samples; a jump > 3 m is someone
    going in at one door and out at another, not walked)."""
    seen = set()
    for i, (x, z) in enumerate(trail):
        seen.add((math.floor(x / CELL), math.floor(z / CELL)))
        if i == 0:
            continue
        px, pz = trail[i - 1]
        d = math.hypot(x - px, z - pz)
        if d > 3.0:
            continue
        steps = int(d / (CELL * 0.25)) + 1
        for k in range(1, steps):
            t = k / steps
            seen.add((math.floor((px + (x - px) * t) / CELL), math.floor((pz + (z - pz) * t) / CELL)))
    return seen


def street_cells(d):
    """The 1 m cells of the paved streets and the square (centre inside)."""
    cells = set()
    for s in d["segments"]:
        h = s[4] * 0.5
        x0, z0, x1, z1 = min(s[0], s[2]) - h, min(s[1], s[3]) - h, max(s[0], s[2]) + h, max(s[1], s[3]) + h
        if s[5]:
            continue  # a gate's passage
        for cx in range(math.floor(x0), math.ceil(x1)):
            for cz in range(math.floor(z0), math.ceil(z1)):
                if x0 <= cx + 0.5 <= x1 and z0 <= cz + 0.5 <= z1 and abs(cx + 0.5) < HALF and abs(cz + 0.5) < HALF:
                    cells.add((cx, cz))
    pl = d["plaza"]
    if pl[2] > 0:
        for cx in range(math.floor(pl[0]), math.ceil(pl[0] + pl[2])):
            for cz in range(math.floor(pl[1]), math.ceil(pl[1] + pl[3])):
                if pl[0] <= cx + 0.5 <= pl[0] + pl[2] and pl[1] <= cz + 0.5 <= pl[1] + pl[3]:
                    cells.add((cx, cz))
    return cells


def coverage(d):
    counts = {}
    for trail in d["trails"]:
        for c in cells_of_trail(trail):
            counts[c] = counts.get(c, 0) + 1
    streets = street_cells(d)
    reached = sum(1 for c in streets if c in counts)
    return counts, streets, reached


def px(x, z, ox, oy):
    return (ox + (x + HALF) * SCALE, oy + (z + HALF) * SCALE)


def draw_panel(draw, d, counts, ox, oy):
    size = HALF * 2 * SCALE
    draw.rectangle([ox, oy, ox + size, oy + size], fill=(236, 236, 230))
    for x, z in d["water"]:
        draw.rectangle([px(x - 0.5, z - 0.5, ox, oy), px(x + 0.5, z + 0.5, ox, oy)], fill=(200, 214, 216))
    for lot in d["lots"]:
        r = lot["rect"]
        draw.rectangle([px(r[0], r[1], ox, oy), px(r[0] + r[2], r[1] + r[3], ox, oy)], fill=(228, 220, 204))
    for s in d["segments"]:
        h = s[4] * 0.5
        x0, z0, x1, z1 = min(s[0], s[2]) - h, min(s[1], s[3]) - h, max(s[0], s[2]) + h, max(s[1], s[3]) + h
        draw.rectangle([px(x0, z0, ox, oy), px(x1, z1, ox, oy)], fill=(250, 250, 246))
    pl = d["plaza"]
    if pl[2] > 0:
        draw.rectangle([px(pl[0], pl[1], ox, oy), px(pl[0] + pl[2], pl[1] + pl[3], ox, oy)], fill=(250, 250, 246))
    for lot in d["lots"]:
        r = lot["body"]
        draw.rectangle([px(r[0], r[1], ox, oy), px(r[0] + r[2], r[1] + r[3], ox, oy)], fill=(196, 192, 184))
    if d["wall"]:
        pts = [px(x, z, ox, oy) for x, z in d["wall"]]
        draw.line(pts + [pts[0]], fill=(150, 140, 125), width=3)
    for (cx, cz), n in counts.items():
        if abs(cx + 0.5) >= HALF or abs(cz + 0.5) >= HALF:
            continue
        colour = RAMP[min(n, len(RAMP)) - 1]
        a = px(cx * CELL, cz * CELL, ox, oy)
        b = px((cx + 1) * CELL, (cz + 1) * CELL, ox, oy)
        draw.rectangle([a[0], a[1], b[0] - 1, b[1] - 1], fill=colour)
    draw.rectangle([ox, oy, ox + size, oy + size], outline=GRID, width=1)


def coverage_sheet(before, after, hall, out):
    size = int(HALF * 2 * SCALE)
    pad = 16
    head = 64
    foot = 58
    img = Image.new("RGB", (pad * 3 + size * 2, head + size + foot), SURFACE)
    draw = ImageDraw.Draw(img)
    draw.text((pad, 10), "Hall %s: where people walk in 120 s" % ["", "I", "II", "III", "IV", "V"][hall], fill=TEXT, font=font(20, True))
    draw.text((pad, 36), "1 m cells by how many different people crossed them; north up, %d px = 1 m" % SCALE, fill=TEXT_2, font=font(14))
    numbers = {}
    for k, (tag, d) in enumerate((("before", before), ("after", after))):
        counts, streets, reached = coverage(d)
        ox = pad + k * (size + pad)
        draw_panel(draw, d, counts, ox, head)
        busy = sum(1 for n in counts.values() if n >= 3)
        share = 100.0 * reached / max(1, len(streets))
        numbers[tag] = (len(d["people"]), len(counts), share, busy)
        label = "%s: %d people, %d m² walked, %.0f%% of streets and square, %d m² by 3+ people" % (tag, len(d["people"]), len(counts), share, busy)
        draw.text((ox, head + size + 8), label, fill=TEXT, font=font(13, True) if tag == "after" else font(13))
    # The ramp's key.
    x = pad
    y = head + size + 32
    draw.text((x, y), "people per cell", fill=TEXT_2, font=font(12))
    x += 104
    for i, colour in enumerate(RAMP):
        draw.rectangle([x, y + 1, x + 22, y + 15], fill=colour)
        draw.text((x + 26, y), "%d%s" % (i + 1, "+" if i == len(RAMP) - 1 else ""), fill=TEXT_2, font=font(12))
        x += 54
    img.save(out)
    return numbers


def visible_plot(before, after, people, out):
    panels = [("hall 3 default z70", "Hall III, default view (zoom 70)", 3), ("hall 3 ECO-05 z34", "Hall III, at the hall (zoom 34)", 3),
              ("hall 5 default z70", "Hall V, default view (zoom 70)", 5), ("hall 5 ECO-05 z34", "Hall V, at the hall (zoom 34)", 5)]
    pw, ph = 560, 250
    left, top, gap = 44, 40, 34
    pad = 16
    head = 70
    img = Image.new("RGB", (pad * 2 + 2 * (left + pw) + gap + 24, head + 2 * (top + ph + 64)), SURFACE)
    draw = ImageDraw.Draw(img)
    draw.text((pad, 10), "People on screen, not behind a building", fill=TEXT, font=font(20, True))
    draw.text((pad, 36), "every 0.5 s over 120 s of town time; orange before, blue after", fill=TEXT_2, font=font(14))
    numbers = {}
    for i, (key, title, hall) in enumerate(panels):
        col, row = i % 2, i // 2
        ox = pad + col * (left + pw + gap) + left
        oy = head + row * (top + ph + 64) + top
        draw.text((ox - left, oy - top + 4), title, fill=TEXT, font=font(15, True))
        top_value = 20
        for v in range(0, top_value + 1, 5):
            y = oy + ph - ph * v / top_value
            draw.line([ox, y, ox + pw, y], fill=GRID, width=1)
            draw.text((ox - 26, y - 8), "%2d" % v, fill=TEXT_2, font=font(12))
        for s in range(0, 121, 30):
            x = ox + pw * s / 120.0
            draw.text((x - 10, oy + ph + 4), "%d s" % s, fill=TEXT_2, font=font(12))
        legend_y = oy + ph + 24
        legend_x = ox
        for tag, series_set, colour in (("before", before, BEFORE), ("after", after, AFTER)):
            series = series_set.get(key, [])
            if not series:
                continue
            pts = []
            for k, v in enumerate(series):
                x = ox + pw * (k * 0.5) / 120.0
                y = oy + ph - ph * v / top_value
                if pts:
                    pts.append((x, pts[-1][1]))
                pts.append((x, y))
            draw.line(pts, fill=colour, width=2)
            low, mean = min(series), sum(series) / len(series)
            near = series_set.get(key + " near", [])
            near_mean = sum(near) / len(near) if near else float("nan")
            numbers.setdefault(key, {})[tag] = (low, mean, max(series), near_mean)
            draw.rectangle([legend_x, legend_y + 4, legend_x + 18, legend_y + 6], fill=colour)
            label = "%s: min %d, mean %.1f of %d people" % (tag, low, mean, people[tag][hall])
            draw.text((legend_x + 24, legend_y - 3), label, fill=TEXT, font=font(13))
            legend_x += 300
        draw.line([ox, oy + ph, ox + pw, oy + ph], fill=TEXT_2, width=1)
    img.save(out)
    return numbers


def main():
    before_dir, after_dir, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out_dir, exist_ok=True)
    people = {"before": {}, "after": {}}
    for hall in (1, 3, 5):
        b = json.load(open(os.path.join(before_dir, "townsfolk_hall%d.json" % hall)))
        a = json.load(open(os.path.join(after_dir, "townsfolk_hall%d.json" % hall)))
        people["before"][hall] = len(b["people"])
        people["after"][hall] = len(a["people"])
        numbers = coverage_sheet(b, a, hall, os.path.join(out_dir, "coverage_hall%d.png" % hall))
        for tag, (count, cells, share, busy) in numbers.items():
            print("hall %d %-6s people %2d, %4d m2 walked, %5.1f%% of streets and square, %4d m2 by 3+ people" % (hall, tag, count, cells, share, busy))
    vb = json.load(open(os.path.join(before_dir, "townsfolk_visible.json")))
    va = json.load(open(os.path.join(after_dir, "townsfolk_visible.json")))
    numbers = visible_plot(vb, va, people, os.path.join(out_dir, "visible_over_time.png"))
    for key, tags in numbers.items():
        for tag, (low, mean, high, near) in tags.items():
            print("%-20s %-6s on screen min %2d mean %5.2f max %2d; within 15 m of the view's centre mean %.2f" % (key, tag, low, mean, high, near))


if __name__ == "__main__":
    main()
