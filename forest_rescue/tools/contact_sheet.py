#!/usr/bin/env python3
"""Contact sheet (N evenly spaced frames, time-stamped) for each MP4 given.

    python3 forest_rescue/tools/contact_sheet.py <video.mp4>... [--cols 4 --rows 3]
Writes <video>_contact.png next to each video.
"""
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


def sheet(path, cols=4, rows=3, width=455):
    total = duration(path)
    n = cols * rows
    tmp = tempfile.mkdtemp()
    frames = []
    for i in range(n):
        t = total * (i + 0.5) / n
        out = os.path.join(tmp, f"f{i:02d}.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", out], check=True)
        frames.append((t, Image.open(out).convert("RGB")))
    w = width
    h = int(frames[0][1].height * w / frames[0][1].width)
    title_h = 30
    img = Image.new("RGB", (cols * w, title_h + rows * (h + 18)), (22, 20, 18))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 16)
    small = ImageFont.truetype(FONT, 13)
    d.text((8, 6), f"{os.path.basename(path)}  ·  {total:.1f} s  ·  30 fps  ·  DRENOVAR city camera (in-engine, local realm)",
           fill=(235, 205, 140), font=font)
    for i, (t, fr) in enumerate(frames):
        x = (i % cols) * w
        y = title_h + (i // cols) * (h + 18)
        img.paste(fr.resize((w, h), Image.LANCZOS), (x, y + 18))
        d.text((x + 4, y + 1), f"t = {t:5.1f} s", fill=(220, 210, 190), font=small)
    out = os.path.splitext(path)[0] + "_contact.png"
    img.save(out, optimize=True)
    print(out)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cols = int(sys.argv[sys.argv.index("--cols") + 1]) if "--cols" in sys.argv else 4
    rows = int(sys.argv[sys.argv.index("--rows") + 1]) if "--rows" in sys.argv else 3
    for p in args:
        if p.endswith(".mp4"):
            sheet(p, cols, rows)
