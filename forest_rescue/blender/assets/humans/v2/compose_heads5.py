"""Duplicate-feature check sheets: per character, head at 5 angles (front, 3/4 L/R, profile L/R):
row 1 Blender LOD0 (textured, albedo), rows 2-3 Godot 4.6.3 (game painted-light material) LOD0 / LOD1.
    python3 compose_heads5.py <godot_shots_dir>   -> qa/compare/<id>/v2_iterNN_heads5.png (latest iter)"""
import glob
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
QA = os.path.join(REPO, "forest_rescue", "qa", "compare")
IDS = ["lf_civilian_miller", "lf_civilian_herbalist", "lf_civilian_ferryman", "lf_civilian_courier",
       "lf_civilian_cooper", "lf_civilian_quarry_worker", "lf_squad_captain", "lf_squad_scout",
       "lf_squad_shield_guard"]
ANG = [0, -45, 45, -90, 90]
TW, TH = 300, 330


def lab(im, t):
    d = ImageDraw.Draw(im)
    d.rectangle([2, 2, 8 + 6 * len(t), 16], fill=(20, 20, 20))
    d.text((5, 4), t, fill=(255, 240, 200))
    return im


def main(gdir):
    for aid in IDS:
        bl = sorted(glob.glob(os.path.join(QA, aid, "v2_iter*_heads5_blender.png")),
                    key=lambda p: int(re.search(r"iter(\d+)", p).group(1)))
        if not bl:
            continue
        it = re.search(r"iter(\d+)", bl[-1]).group(1)
        rows = []
        b = Image.open(bl[-1]).convert("RGB")
        w = b.size[0] // 5
        rows.append([lab(b.crop((i * w, 0, (i + 1) * w, b.size[1])).resize((TW, TH)), f"Blender LOD0 {a}deg")
                     for i, a in enumerate(ANG)])
        for lod in (0, 1):
            r = []
            for a in ANG:
                p = os.path.join(gdir, f"{aid}_LOD{lod}_{a}.png")
                if os.path.exists(p):
                    g = Image.open(p).convert("RGB")
                    W, H = g.size
                    side = min(W, H)
                    g = g.crop(((W - side) // 2, (H - side) // 2, (W + side) // 2, (H + side) // 2)).resize((TW, TH))
                else:
                    g = Image.new("RGB", (TW, TH), (40, 40, 40))
                r.append(lab(g, f"Godot LOD{lod} {a}deg"))
            rows.append(r)
        S = Image.new("RGB", (TW * 5, TH * len(rows) + 22), (28, 28, 28))
        ImageDraw.Draw(S).text((6, 5), f"{aid} v2 iter{it} heads5: duplicate-feature check (2 eyes, 1 nose, 1 mouth, 2 ears)",
                               fill=(255, 240, 200))
        for j, r in enumerate(rows):
            for i, t in enumerate(r):
                S.paste(t, (i * TW, 22 + j * TH))
        out = os.path.join(QA, aid, f"v2_iter{it}_heads5.png")
        S.save(out)
        print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1])
