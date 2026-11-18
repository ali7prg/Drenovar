"""Close-up comparison of appearance: the same regions cut from a reference image and from the model render that
tools/proof.py aligned to it (<species>_<tag>_<view>_aligned.png, or <species>_glbpose_<phase>_aligned.png),
shown side by side and enlarged - heads, fur, plates, feet and tails at the reference's own scale.

  python3 -I detail.py <rc dir> <render dir> <tag> <species> <out dir> [view,...]

Regions are fractions of the reference figure's bounding box (x0, y0, x1, y1); side views have the head on the left.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REGIONS = {
    "side": {"head": (0.00, 0.00, 0.34, 0.62), "back": (0.25, 0.00, 0.75, 0.45), "legs": (0.05, 0.50, 0.95, 1.00),
             "tail": (0.66, 0.10, 1.00, 0.95)},
    "front": {"head": (0.22, 0.00, 0.78, 0.55), "chest": (0.15, 0.35, 0.85, 0.80), "feet": (0.00, 0.70, 1.00, 1.00)},
    "rear": {"back": (0.10, 0.00, 0.90, 0.50), "hind": (0.00, 0.45, 1.00, 1.00)},
    "top": {"front half": (0.00, 0.00, 0.55, 1.00), "rear half": (0.45, 0.00, 1.00, 1.00)},
    "pose": {"head": None, "body": (0.15, 0.00, 0.85, 1.00)},
}
# heads on the attack-pose images: right side of the frame for every creature but Velkor (facing left)
POSE_HEAD = {"velkor": (0.00, 0.00, 0.40, 0.75), "tenerys": (0.62, 0.00, 1.00, 0.85),
             "kamneklyk": (0.55, 0.00, 1.00, 0.85), "dragor": (0.60, 0.00, 1.00, 0.85)}


def font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def crop_pair(ref, mdl, bbox, frac, h_out=360):
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    box = (int(x0 + frac[0] * w), int(y0 + frac[1] * h), int(x0 + frac[2] * w), int(y0 + frac[3] * h))
    a, b = ref.crop(box), mdl.crop(box)
    s = h_out / max(1, a.size[1])
    size = (max(1, int(a.size[0] * s)), h_out)
    return a.resize(size, Image.LANCZOS), b.resize(size, Image.LANCZOS)


def main():
    rc, rdir, tag, sid, out = sys.argv[1:6]
    views = sys.argv[6].split(",") if len(sys.argv) > 6 else None
    os.makedirs(out, exist_ok=True)
    refs = json.load(open(os.path.join(rc, "refs.json")))[sid]
    items = []
    for view, row in refs["views"].items():
        if views and view not in views:
            continue
        mp = os.path.join(rdir, f"{sid}_{tag}_{view}_aligned.png")
        if not os.path.exists(mp):
            continue
        items.append((view, Image.open(os.path.join(rc, f"{sid}_{view}_ref.png")).convert("RGB"),
                      Image.open(mp).convert("RGB"), row["bbox"], REGIONS.get(view, {})))
    for ph, row in refs.get("poses", {}).items():
        if views and "pose" not in views and ph not in views:
            continue
        mp = os.path.join(rdir, f"{sid}_glbpose_{ph}_aligned.png")
        if not os.path.exists(mp):
            continue
        reg = dict(REGIONS["pose"])
        reg["head"] = POSE_HEAD[sid]
        items.append((ph, Image.open(os.path.join(rc, f"{sid}_pose_{ph}_ref.png")).convert("RGB"),
                      Image.open(mp).convert("RGB"), row["bbox"], reg))
    f = font(15)
    for view, ref, mdl, bbox, regions in items:
        tiles = []
        for name, frac in regions.items():
            a, b = crop_pair(ref, mdl, bbox, frac)
            t = Image.new("RGB", (a.size[0] * 2 + 6, a.size[1] + 22), (255, 255, 255))
            t.paste(a, (0, 22))
            t.paste(b, (a.size[0] + 6, 22))
            ImageDraw.Draw(t).text((4, 2), f"{sid} {view} {name}: reference | model", fill=(20, 20, 20), font=f)
            tiles.append(t)
        W = max(t.size[0] for t in tiles)
        sheet = Image.new("RGB", (W, sum(t.size[1] + 6 for t in tiles)), (255, 255, 255))
        y = 0
        for t in tiles:
            sheet.paste(t, (0, y))
            y += t.size[1] + 6
        path = os.path.join(out, f"{sid}_detail_{view}.jpg")
        sheet.save(path, quality=86)
        print("DETAIL", path, sheet.size)


if __name__ == "__main__":
    main()
