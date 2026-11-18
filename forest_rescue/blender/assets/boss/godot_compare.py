"""Compose Godot viewer shots next to the reference views (PIL only, no bpy).

python3 godot_compare.py <shots_dir> <out_png> <ref_png> <box x0,y0,x1,y1:yaw> [<box:yaw> ...]
"""
import sys

from PIL import Image, ImageDraw


def main():
    shots, out, ref = sys.argv[1], sys.argv[2], sys.argv[3]
    pairs = []
    R = Image.open(ref).convert("RGB")
    for spec in sys.argv[4:]:
        box, yaw = spec.split(":")
        x0, y0, x1, y1 = map(int, box.split(","))
        pairs.append((R.crop((x0, y0, x1, y1)), Image.open(f"{shots}/shot_yaw{int(yaw):03d}.png").convert("RGB"), yaw))
    H = 360
    rows = []
    for a, b, yaw in pairs:
        a = a.resize((int(a.size[0] * H / a.size[1]), H))
        b = b.resize((int(b.size[0] * H / b.size[1]), H))
        row = Image.new("RGB", (a.size[0] + b.size[0], H), (25, 25, 25))
        row.paste(a, (0, 0))
        row.paste(b, (a.size[0], 0))
        d = ImageDraw.Draw(row)
        d.rectangle([0, 0, 220, 16], fill=(20, 20, 20))
        d.text((4, 2), "reference", fill=(255, 235, 190))
        d.rectangle([a.size[0], 0, a.size[0] + 260, 16], fill=(20, 20, 20))
        d.text((a.size[0] + 4, 2), f"Godot 4.6 Mobile, yaw {yaw}", fill=(255, 235, 190))
        rows.append(row)
    W = max(r.size[0] for r in rows)
    sheet = Image.new("RGB", (W, H * len(rows)), (25, 25, 25))
    for i, r in enumerate(rows):
        sheet.paste(r, (0, i * H))
    sheet.save(out)
    print("saved", out)


if __name__ == "__main__":
    main()
