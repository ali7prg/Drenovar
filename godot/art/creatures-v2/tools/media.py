"""Turns media.gd / capture_battle.gd frames into MP4 (H.264), WebP portraits and contact sheets.
Usage: python3 -I media.py <media-dir> <species> [capture-dir]"""
import glob
import os
import subprocess
import sys

from PIL import Image, ImageDraw


def mp4(pattern_dir, prefix, out, fps):
    frames = sorted(glob.glob(os.path.join(pattern_dir, prefix + "*.png")))
    if not frames:
        return None
    lst = out + ".txt"
    with open(lst, "w") as f:
        for fr in frames:
            f.write(f"file '{os.path.abspath(fr)}'\nduration {1.0 / fps:.5f}\n")
        f.write(f"file '{os.path.abspath(frames[-1])}'\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-vf",
                    "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p", "-c:v", "libx264", "-preset", "slow",
                    "-crf", "23", "-movflags", "+faststart", "-r", str(fps), out], check=True)
    os.remove(lst)
    return out


def sheet(files, out, cols, scale=1.0):
    ims = [Image.open(f).convert("RGB") for f in files]
    w, h = ims[0].size
    w2, h2 = int(w * scale), int(h * scale)
    rows = (len(ims) + cols - 1) // cols
    s = Image.new("RGB", (w2 * cols, h2 * rows), (30, 30, 30))
    for i, im in enumerate(ims):
        s.paste(im.resize((w2, h2), Image.LANCZOS), ((i % cols) * w2, (i // cols) * h2))
    s.save(out, quality=88)
    return out


def portrait(src, out):
    """Creature on a transparent background over the hunt panel gradient (#465647 -> #1a2d25)."""
    im = Image.open(src).convert("RGBA")
    w, h = im.size
    bg = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(bg)
    for y in range(h):
        t = y / (h - 1)
        c = tuple(int(a + (b - a) * t) for a, b in zip((0x46, 0x56, 0x47), (0x1a, 0x2d, 0x25)))
        d.line([(0, y), (w, y)], fill=c + (255,))
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([w * 0.18, h * 0.80, w * 0.86, h * 0.95], fill=(0, 0, 0, 90))
    bg = Image.alpha_composite(bg, sh)
    bg = Image.alpha_composite(bg, im)
    bg.convert("RGB").save(out, "WEBP", quality=88, method=6)
    return out


def main():
    media, sid = sys.argv[1], sys.argv[2]
    d = os.path.join(media, sid)
    made = []
    made.append(mp4(d, "turn_", os.path.join(d, f"{sid}_turntable.mp4"), 24))
    shorts = sorted({os.path.basename(f)[5:-8] for f in glob.glob(os.path.join(d, "clip_*_*.png"))})
    for short in shorts:
        made.append(mp4(d, f"clip_{short}_", os.path.join(d, f"{sid}_{short}.mp4"), 30))
        frames = sorted(glob.glob(os.path.join(d, f"clip_{short}_*.png")))
        pick = [frames[int(i * (len(frames) - 1) / 7)] for i in range(8)]
        made.append(sheet(pick, os.path.join(d, f"{sid}_{short}_sheet.jpg"), 4, 0.5))
    turns = sorted(glob.glob(os.path.join(d, "turn_*.png")))
    if turns:
        made.append(sheet([turns[int(i * len(turns) / 8)] for i in range(8)], os.path.join(d, f"{sid}_turntable_sheet.jpg"), 4, 0.5))
    for lv in (1, 2, 3):
        p = os.path.join(d, f"portrait_{lv}.png")
        if os.path.exists(p):
            made.append(portrait(p, os.path.join(d, f"{sid}_portrait_{lv}.webp")))
    if len(sys.argv) > 3:
        cap = os.path.join(sys.argv[3], sid)
        if os.path.isdir(cap):
            made.append(mp4(cap, "f_", os.path.join(d, f"{sid}_ingame_hunt.mp4"), 10))
    for m in made:
        if m:
            print(m, os.path.getsize(m))


if __name__ == "__main__":
    main()
