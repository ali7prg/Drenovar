"""Final reference-check sheets for the audit: the creature-references images next to the built model, one page per
creature (turnaround views, then the four attack poses), plus the measurements as JSON.

  python3 -I refsheet.py <rc dir> <glb renders dir> <out images dir> <out measurements dir> <species> [...]

Inputs come from tools/refcheck.py refs (rc dir), tools/proof.py glb (<id>_model_idle_0.jpg, IoU printed in its log)
and tools/proof.py glbposes (<id>_glbposes.jpg / .json), tools/foot_check.py (<id>_feet.json), tools/detail.py
(<id>_detail_<view or pose>.jpg close-ups -> images/closeup_<id>.jpg).
"""
import json
import os
import sys

from PIL import Image, ImageDraw

def _font(size=16):
    """A font with Cyrillic glyphs (the default bitmap font has none)."""
    from PIL import ImageFont
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation/"
                 "LiberationSans-Regular.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


FONT = _font()
TITLE = {"velkor": "Лесной Велькор (velkor)", "tenerys": "Тенерис (tenerys)", "kamneklyk": "Камнеклык (kamneklyk)",
         "dragor": "Горный Драгор (dragor)"}


def page(parts, width=1800):
    ims = []
    for title, path in parts:
        if not os.path.exists(path):
            continue
        im = Image.open(path).convert("RGB")
        s = width / im.size[0]
        im = im.resize((width, int(im.size[1] * s)), Image.LANCZOS)
        head = Image.new("RGB", (width, 34), (34, 38, 44))
        ImageDraw.Draw(head).text((12, 8), title, fill=(240, 240, 240), font=FONT)
        ims += [head, im]
    H = sum(i.size[1] for i in ims)
    out = Image.new("RGB", (width, H), (255, 255, 255))
    y = 0
    for i in ims:
        out.paste(i, (0, y))
        y += i.size[1]
    return out


def main():
    rc, renders, img_out, meas_out = sys.argv[1:5]
    os.makedirs(img_out, exist_ok=True)
    os.makedirs(meas_out, exist_ok=True)
    for sid in sys.argv[5:]:
        views = os.path.join(renders, f"{sid}_model_idle_0.jpg")
        poses = os.path.join(renders, f"{sid}_glbposes.jpg")
        cycles = os.path.join(renders, f"{sid}_glbcycles.jpg")
        p = page([(f"{TITLE[sid]}: creature-references model.png views | model (LOD0, idle frame 0, Cycles) | "
                   f"overlay (red: only the reference, cyan: only the model)", views),
                  (f"{TITLE[sid]}: attack poses 01-04 | model | overlay", poses)])
        p.save(os.path.join(img_out, f"refcheck_{sid}.jpg"), quality=86)
        if os.path.exists(cycles):
            page([(f"{TITLE[sid]}: idle / walk / run (LOD1, Cycles, the same 3/4 camera)", cycles)]).save(
                os.path.join(img_out, f"cycles_{sid}.jpg"), quality=84)
        # close-ups from tools/detail.py: heads, fur, feet and tails cut from the same frames, reference | model
        details = [(f"{TITLE[sid]}: {view} close-ups: reference | model", os.path.join(renders, f"{sid}_detail_{view}.jpg"))
                   for view in ("side", "front", "rear", "top", "preparation", "launch", "contact", "recovery")]
        if any(os.path.exists(p) for _t, p in details):
            page(details, width=1400).save(os.path.join(img_out, f"closeup_{sid}.jpg"), quality=80)
        before = os.path.join(renders, "..", "before", f"{sid}_model_idle_0.jpg")
        if os.path.exists(before):
            page([(f"{TITLE[sid]}: BEFORE (the 17.11 kit-sheet model) in the creature-references views", before),
                  (f"{TITLE[sid]}: AFTER", views)], width=1400).save(
                os.path.join(img_out, f"before_after_{sid}.jpg"), quality=80)
        m = {}
        for name in (f"{sid}_views.json", f"{sid}_glbposes.json", f"{sid}_feet.json"):
            q = os.path.join(renders, name)
            if os.path.exists(q):
                m[name.split("_", 1)[1][:-5]] = json.load(open(q))
        json.dump(m, open(os.path.join(meas_out, f"refcheck_{sid}.json"), "w"), ensure_ascii=False, indent=1)
        print(sid, os.path.getsize(os.path.join(img_out, f"refcheck_{sid}.jpg")))


if __name__ == "__main__":
    main()
