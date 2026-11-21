#!/usr/bin/env python3
"""Before / after sheets for the checkpoint-2 P1 items, next to the reference painting.

  p1_4_arena.png      art/08 — fight framing, compact boss panel, thin orange arcs, arena rim clear
  p1_4_telegraphs.png each boss attack: telegraph (warn) and hit window (active), before | after
  p1_5_overview.png   art/01 — trail network, glades, landmarks, biomes, river (QA projection)
  p1_6_trail.png      art/07 — narrow worn trail, site 1 glade with cage + camp + artifact glow

Every game frame comes from the real client and the DRENOVAR city camera
(qa_forest_integration_shots.gd: fixtures through a stub transport); "before" frames were
rendered with the sources before the item, "after" frames with the current sources.

    python3 forest_rescue/qa/ingame/integration/compose_p1.py <item> <before dir> <after dir>
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.abspath(os.path.join(HERE, "..", "..", "..", "delivery", "art"))
OUT = os.path.join(HERE, "sheets", "p1")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def label(img, text, xy=(8, 6), size=16):
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, size)
    box = d.textbbox(xy, text, font=f)
    d.rectangle((box[0] - 5, box[1] - 3, box[2] + 5, box[3] + 4), fill=(18, 16, 14))
    d.text(xy, text, font=f, fill=(255, 236, 190))


def fit(img, height):
    return img.resize((int(img.width * height / img.height), height), Image.LANCZOS)


def sheet(name, title, reference, rows, before, after, height=330):
    """reference: (file, crop, caption) or None; rows: [(shot | (before shot, after shot), crop, caption)]
    → BEFORE | AFTER per row, the reference painting on the left spanning all rows."""
    tiles = []
    for shot, crop, caption in rows:
        pair = []
        names = shot if isinstance(shot, tuple) else (shot, shot)
        for folder, tag, shot_name in ((before, "BEFORE", names[0]), (after, "AFTER", names[1])):
            path = os.path.join(folder, shot_name + ".png")
            img = Image.open(path).convert("RGB")
            if crop:
                img = img.crop(crop)
            img = fit(img, height)
            label(img, "%s · %s" % (tag, caption), xy=(8, img.height - 26))
            pair.append(img)
        tiles.append(pair)
    row_w = tiles[0][0].width + tiles[0][1].width + 8
    ref_img = None
    if reference:
        ref_img = Image.open(os.path.join(ART, reference[0])).convert("RGB").crop(reference[1])
        ref_img = fit(ref_img, len(tiles) * (height + 8) - 8)
        label(ref_img, "REFERENCE · " + reference[2], xy=(8, ref_img.height - 26))
    width = row_w + (ref_img.width + 8 if ref_img else 0)
    out = Image.new("RGB", (width, 44 + len(tiles) * (height + 8)), (30, 27, 24))
    ImageDraw.Draw(out).text((10, 10), title, font=ImageFont.truetype(FONT, 19), fill=(250, 240, 220))
    x0 = 0
    if ref_img:
        out.paste(ref_img, (0, 44))
        x0 = ref_img.width + 8
    for i, (a, b) in enumerate(tiles):
        y = 44 + i * (height + 8)
        out.paste(a, (x0, y))
        out.paste(b, (x0 + a.width + 8, y))
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name + ".png")
    out.save(path)
    print("sheet", path, out.size)


def arena(before, after):
    sheet("p1_4_arena", "P1.4 art/08 — fight framing (zoom 32), compact boss panel above the boss, thin bright arcs, "
          "arena rim free of kit trees/rocks (arena opened by the squad's route only)",
          ("08_final_boss_arena.png", (0, 0, 1536, 760), "art/08"),
          [(("boss_35_z40", "boss_35_z32"), None, "boss fight at 35 % (game framing)"),
           (("boss_85_z40", "boss_85_z32"), None, "boss fight at 85 %"),
           ("tele_tail_sweep_active", None, "tail sweep — hit window")],
          before, after, height=300)


def telegraphs(before, after):
    rows = []
    for attack in ("jaw_arc", "tail_sweep", "lane_charge"):
        for state in ("warn", "active"):
            rows.append(("tele_%s_%s" % (attack, state), (183, 60, 1183, 560), "%s · %s" % (attack, "telegraph" if state == "warn" else "hit window")))
    sheet("p1_4_telegraphs", "P1.4 boss telegraphs — broad pale bands → 3–4 thin bright saturated orange arcs (zoom 34 → 32)",
          None, rows, before, after, height=250)


if __name__ == "__main__":
    item, before_dir, after_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    if item == "arena":
        arena(before_dir, after_dir)
        telegraphs(before_dir, after_dir)
