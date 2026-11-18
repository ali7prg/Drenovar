"""Pair Godot viewer shots of lf_horse_origin with the turnaround views (in-game look check).

    python3 godot_side_by_side.py <shots_dir> <out.png>

godot_view.sh 'shots' yaws: 0 = front (glTF +Z = horse forward), 90 = left profile,
180 = rear, 270 = right profile (perspective camera, 18° pitch — not orthographic).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PAIRS = [("front", 0), ("left", 90), ("rear", 180), ("right", 270), (None, 45), (None, 135)]


def crop_subject(img, bg_tol=0.10):
    a = np.asarray(img.convert("RGB"), float) / 255.0
    H, W = a.shape[:2]
    bg = np.median(np.concatenate([a[:6].reshape(-1, 3), a[:, :6].reshape(-1, 3),
                                   a[:, -6:].reshape(-1, 3)]), axis=0)
    d = np.abs(a - bg).sum(2)
    m = d > bg_tol
    m[int(H * 0.93):] = False          # ignore the ground plane edge at the bottom
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return img
    x0, x1 = max(0, xs.min() - 12), min(W, xs.max() + 12)
    y0, y1 = max(0, ys.min() - 12), min(H, ys.max() + 12)
    return img.crop((x0, y0, x1, y1))


def main():
    shots, out = sys.argv[1], sys.argv[2]
    import horse_refs as HR
    from frlib import refs
    sheet = refs.load(HR.SHEET)
    panels = []
    H = 420
    for view, yaw in PAIRS:
        p = os.path.join(shots, f"shot_yaw{yaw:03d}.png")
        if not os.path.exists(p):
            continue
        g = crop_subject(Image.open(p))
        g = g.resize((int(g.width * H / g.height), H), Image.LANCZOS)
        if view:
            r = refs.crop(sheet, HR.CROPS[view])
            r = Image.fromarray((r * 255).astype(np.uint8))
            r = r.resize((int(r.width * H / r.height), H), Image.LANCZOS)
            pair = Image.new("RGB", (r.width + g.width + 6, H + 22), (28, 28, 28))
            pair.paste(r, (0, 22))
            pair.paste(g, (r.width + 6, 22))
            ImageDraw.Draw(pair).text((6, 5), f"sheet {view}  |  Godot 4.6 viewer yaw {yaw}",
                                      fill=(255, 235, 190))
        else:
            pair = Image.new("RGB", (g.width, H + 22), (28, 28, 28))
            pair.paste(g, (0, 22))
            ImageDraw.Draw(pair).text((6, 5), f"Godot yaw {yaw}", fill=(255, 235, 190))
        panels.append(pair)
    rows, row, wsum = [], [], 0
    for p in panels:
        if wsum + p.width > 2200 and row:
            rows.append(row)
            row, wsum = [], 0
        row.append(p)
        wsum += p.width + 8
    if row:
        rows.append(row)
    W = max(sum(p.width + 8 for p in r) for r in rows)
    canvas = Image.new("RGB", (W, len(rows) * (H + 30)), (20, 20, 20))
    y = 0
    for r in rows:
        x = 0
        for p in r:
            canvas.paste(p, (x, y))
            x += p.width + 8
        y += H + 30
    canvas.save(out)
    print("SIDE_BY_SIDE", out)


if __name__ == "__main__":
    main()
