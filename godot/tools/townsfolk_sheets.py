#!/usr/bin/env python3
"""Contact sheets and videos of the townsfolk renders (qa_townsfolk_shots.gd).

    python3 godot/tools/townsfolk_sheets.py SHOTS_DIR OUT_DIR

For every sequence folder (f0000.jpg ..., captured at 12 fps, or at 3 fps = one per 0.33 s when
it has at most 60 frames): OUT_DIR/<name>_sheet.jpg (one frame per 0.33 s, 5 columns, the time
in the corner), OUT_DIR/<name>.mp4 (H.264) and OUT_DIR/<name>.gif (half size), both in real time. The LOD and shadow comparisons become
OUT_DIR/lod_comparison.jpg and OUT_DIR/shadow_comparison.jpg.
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

FPS = 12


def font(size):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def sheet(frames, out, step, rate, columns=5, scale=0.42):
    images = [Image.open(f).convert("RGB") for f in frames]
    w, h = int(images[0].width * scale), int(images[0].height * scale)
    rows = (len(images) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * w, rows * h), (20, 20, 20))
    label = font(18)
    for i, im in enumerate(images):
        tile = im.resize((w, h), Image.LANCZOS)
        d = ImageDraw.Draw(tile)
        d.rectangle([0, 0, 92, 26], fill=(0, 0, 0))
        d.text((6, 3), "%.2f s" % (i * step / rate), fill=(255, 255, 255), font=label)
        canvas.paste(tile, ((i % columns) * w, (i // columns) * h))
    canvas.save(out, quality=80)


def video(folder, name, out_dir, rate):
    pattern = os.path.join(folder, "f%04d.jpg")
    mp4 = os.path.join(out_dir, name + ".mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(rate), "-i", pattern,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24", "-preset", "slow", mp4], check=True)
    gif = os.path.join(out_dir, name + ".gif")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(rate), "-i", pattern, "-vf",
                    "scale=683:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=160[p];[b][p]paletteuse=dither=bayer",
                    gif], check=True)


def grid(paths, labels, out, columns):
    images = [Image.open(p).convert("RGB") for p in paths]
    w = max(im.width for im in images)
    h = max(im.height for im in images)
    rows = (len(images) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * w, rows * (h + 28)), (24, 24, 24))
    d = ImageDraw.Draw(canvas)
    f = font(18)
    for i, (im, text) in enumerate(zip(images, labels)):
        x, y = (i % columns) * w, (i // columns) * (h + 28)
        canvas.paste(im, (x, y + 28))
        d.text((x + 6, y + 4), text, fill=(255, 255, 255), font=f)
    canvas.save(out, quality=85)


def main():
    src, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    for name in sorted(os.listdir(src)):
        folder = os.path.join(src, name)
        if not os.path.isdir(folder) or name in ("lod", "shadow"):
            continue
        frames = sorted(f for f in os.listdir(folder) if f.endswith(".jpg"))
        if not frames:
            continue
        # 12 fps sequences (video) or one capture per 0.33 s (3 fps); the sheet: one per 0.33 s.
        rate = FPS if len(frames) > 60 else 3
        step = 4 if rate == FPS else 1
        sheet([os.path.join(folder, f) for f in frames[::step]], os.path.join(out_dir, name + "_sheet.jpg"), step, rate)
        video(folder, name, out_dir, rate)
        print("sequence", name, len(frames), "frames")
    lod = os.path.join(src, "lod")
    if os.path.isdir(lod):
        paths, labels = [], []
        for zoom in (24, 40, 70):
            for level in range(3):
                p = os.path.join(lod, "lod%d_zoom%d.png" % (level, zoom))
                if os.path.exists(p):
                    paths.append(p)
                    labels.append("LOD%d (%s tris), zoom %d" % (level, ["12k", "5.9k", "2.1k"][level], zoom))
        if paths:
            # Same scale per row: every crop of a row covers the same world area.
            grid(paths, labels, os.path.join(out_dir, "lod_comparison.jpg"), 3)
    shadow = os.path.join(src, "shadow")
    if os.path.isdir(shadow):
        paths, labels = [], []
        for zoom in (34, 70):
            for kind in ("real", "blob"):
                p = os.path.join(shadow, "%s_zoom%d.jpg" % (kind, zoom))
                if os.path.exists(p):
                    im = Image.open(p)
                    crop = im.crop((383, 165, 983, 465))
                    cp = os.path.join(shadow, "%s_zoom%d_crop.jpg" % (kind, zoom))
                    crop.save(cp, quality=90)
                    paths.append(cp)
                    labels.append("%s, zoom %d" % ("sun shadow + contact blob" if kind == "real" else "contact blob only", zoom))
        if paths:
            grid(paths, labels, os.path.join(out_dir, "shadow_comparison.jpg"), 2)


if __name__ == "__main__":
    main()
