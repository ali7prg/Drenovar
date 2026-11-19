"""Compose the Godot-side QA sheets (plain Python + Pillow):
  v2_iterNN_heads5.png       rows: Blender albedo | Godot LOD0 (game painted look) | Godot LOD1; 5 angles, framed
  v2_iterNN_arena_game.png   art/08 crop (boss + squad) | Godot game camera zoom 40 | zoom 68, matched boss scale
  v2_iterNN_attacks_game.png Godot zoom-40 key frames of the four attacks (telegraph / active), roar, death
python3 compose_sheets.py <iter> <godot_dir>
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
QA = os.path.join(REPO, "forest_rescue", "qa", "compare", "lf_boss_ancient_maw")
ART = os.path.join(REPO, "forest_rescue", "delivery", "art")


def lab(im, t):
    d = ImageDraw.Draw(im)
    d.rectangle([3, 3, 10 + 6 * len(t), 18], fill=(20, 20, 20))
    d.text((6, 5), t, fill=(255, 240, 200))
    return im


def frame(im, size, border=5):
    im = im.resize(size, Image.LANCZOS)
    out = Image.new("RGB", (size[0] + 2 * border, size[1] + 2 * border), (35, 35, 35))
    out.paste(im, (border, border))
    return out


def heads5(it, gdir):
    names = ["front", "34L", "34R", "profL", "profR"]
    labels = ["front", "3/4 left (scar)", "3/4 right", "profile left (scar)", "profile right"]
    b = Image.open(os.path.join(QA, f"v2_iter{it}_heads5_blender.png")).convert("RGB")
    w = b.size[0] // 5
    rows = [[frame(b.crop((i * w + 6, 6, (i + 1) * w - 6, b.size[1] - 6)), (300, 280)) for i in range(5)]]
    for lvl in (0, 1):
        r = []
        for n in names:
            g = Image.open(os.path.join(gdir, f"heads5_lod{lvl}_{n}.png")).convert("RGB")
            W, H = g.size
            r.append(frame(g.crop((W // 2 - 330, H // 2 - 300, W // 2 + 330, H // 2 + 316)), (300, 280)))
        rows.append(r)
    pw, ph = rows[0][0].size
    sheet = Image.new("RGB", (pw * 5, ph * 3 + 3 * 22), (20, 20, 20))
    titles = ["Blender LOD0 (albedo)", "Godot 4.6.3 LOD0 (game painted look)", "Godot 4.6.3 LOD1"]
    y = 0
    for ri, r in enumerate(rows):
        lab_im = Image.new("RGB", (pw * 5, 22), (20, 20, 20))
        ImageDraw.Draw(lab_im).text((6, 5), titles[ri], fill=(255, 240, 200))
        sheet.paste(lab_im, (0, y))
        y += 22
        for i, p in enumerate(r):
            sheet.paste(lab(p.copy(), labels[i]), (i * pw, y))
        y += ph
    sheet.save(os.path.join(QA, f"v2_iter{it}_heads5.png"))


def arena(it, gdir):
    art = Image.open(os.path.join(ART, "08_final_boss_arena.png")).convert("RGB")
    a = art.crop((560, 180, 1110, 700))
    g40 = Image.open(os.path.join(gdir, "game_zoom40_idle.png")).convert("RGB")
    g68 = Image.open(os.path.join(gdir, "game_zoom68_idle.png")).convert("RGB")
    W, H = g40.size
    # boss ~ image centre-left in the game shots; matched crops (boss length ~ same fraction of the panel)
    c40 = g40.crop((W // 2 - 380, H // 2 - 260, W // 2 + 220, H // 2 + 290))
    c68 = g68.crop((W // 2 - 220, H // 2 - 150, W // 2 + 130, H // 2 + 170))
    ph = 520
    panels = []
    for im, t in ((a, "art/08 (boss + squad)"), (c40, "Godot game camera zoom 40 (LOD0)"),
                  (c68, "Godot game camera zoom 68 (LOD1, arena LOD1 assembly)")):
        s = ph / im.size[1]
        panels.append(lab(frame(im, (int(im.size[0] * s), ph)), t))
    sheet = Image.new("RGB", (sum(p.size[0] for p in panels), panels[0].size[1]), (20, 20, 20))
    x = 0
    for p in panels:
        sheet.paste(p, (x, 0))
        x += p.size[0]
    sheet.save(os.path.join(QA, f"v2_iter{it}_arena_game.png"))
    full = []
    for im, t in ((art.crop((0, 0, 1536, 720)), "art/08"), (g40, "Godot zoom 40"), (g68, "Godot zoom 68")):
        s = 400 / im.size[1]
        full.append(lab(frame(im, (int(im.size[0] * s), 400)), t))
    sheet = Image.new("RGB", (sum(p.size[0] for p in full), full[0].size[1]), (20, 20, 20))
    x = 0
    for p in full:
        sheet.paste(p, (x, 0))
        x += p.size[0]
    sheet.save(os.path.join(QA, f"v2_iter{it}_arena_game_full.png"))


def attacks(it, gdir):
    keys = ["jaw_arc_2.00", "jaw_arc_2.55", "tail_sweep_2.80", "tail_sweep_3.45", "lane_charge_2.20",
            "lane_charge_3.50", "stomp_waves_2.90", "stomp_waves_3.25", "phase_roar_1.20", "death_5.19"]
    tiles = []
    for k in keys:
        p = os.path.join(gdir, f"game_zoom40_{k}.png")
        if not os.path.exists(p):
            continue
        g = Image.open(p).convert("RGB")
        W, H = g.size
        tiles.append(lab(frame(g.crop((W // 2 - 330, H // 2 - 230, W // 2 + 150, H // 2 + 130)), (360, 270)), k))
    cols = 5
    rows = (len(tiles) + cols - 1) // cols
    tw, th = tiles[0].size
    sheet = Image.new("RGB", (tw * cols, th * rows), (20, 20, 20))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * tw, (i // cols) * th))
    sheet.save(os.path.join(QA, f"v2_iter{it}_attacks_game.png"))


if __name__ == "__main__":
    it, gdir = sys.argv[1], sys.argv[2]
    heads5(it, gdir)
    arena(it, gdir)
    attacks(it, gdir)
    print("COMPOSED", it)
