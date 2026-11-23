#!/usr/bin/env python3
"""Evidence for build 1024 «Лес потерянных» (qa_forest_1024.gd): before / after videos, sheets, tables.

    python3 godot/tools/forest_1024_evidence.py BEFORE_SHOTS AFTER_SHOTS BEFORE_QA AFTER_QA OUT_DIR

BEFORE_SHOTS / AFTER_SHOTS: --shots folders of the rendered runs (one folder per segment with
f_00000.jpg ... at 15 fps of the movie clock, plus puzzle_*.png stills).
BEFORE_QA / AFTER_QA: folders with the headless reports qa_legacy_lat{0,300,700}.json and
qa_kingdom_all.json.

Writes into OUT_DIR, per segment (intro, fog, menace, fight, cage = the cage before and its release):
  <segment>_before_after.mp4  (H.264, before left / after right, real time)
  <segment>_before_after.gif  (640 px wide, 6 fps)
  <segment>_sheet.jpg         (contact sheet: rows of before / after, one frame per 0.5 s)
and puzzle_before_after.jpg, cage_before_before_after.jpg, intro_end_before_after.jpg, latency.tsv, cages.tsv, checks.tsv.
"""
import json
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

FPS = 15
SEGMENTS = ["intro", "fog", "menace", "fight", "cage"]
LATENCIES = [0, 300, 700]


def font(size):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def frames(folder):
    if not os.path.isdir(folder):
        return []
    return sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.startswith("f_") and f.endswith(".jpg"))


def label(image, text):
    d = ImageDraw.Draw(image)
    d.rectangle([0, 0, 18 + 13 * len(text), 30], fill=(0, 0, 0))
    d.text((8, 4), text, fill=(255, 255, 255), font=font(20))
    return image


def pair_video(before, after, name, out_dir):
    """Side by side (each half size), the shorter run holds its last frame."""
    count = max(len(before), len(after))
    if count == 0:
        return
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(count):
            a = Image.open(before[min(i, len(before) - 1)]).convert("RGB") if before else None
            b = Image.open(after[min(i, len(after) - 1)]).convert("RGB") if after else None
            ref = a or b
            w, h = ref.width // 4 * 2, ref.height // 4 * 2
            canvas = Image.new("RGB", (w * 2 + 8, h), (16, 16, 16))
            for k, (im, text) in enumerate([(a, "ДО (259de0a1)"), (b, "ПОСЛЕ")]):
                tile = im.resize((w, h), Image.LANCZOS) if im else Image.new("RGB", (w, h), (40, 40, 40))
                label(tile, "%s  %.2f s" % (text, min(i, (len(before) if k == 0 else len(after)) - 1) / FPS))
                canvas.paste(tile, (k * (w + 8), 0))
            canvas.save(os.path.join(tmp, "p_%05d.jpg" % i), quality=88)
        pattern = os.path.join(tmp, "p_%05d.jpg")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", pattern, "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-crf", "26", "-preset", "slow", os.path.join(out_dir, name + "_before_after.mp4")], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", pattern, "-vf",
                        "fps=6,scale=640:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer",
                        os.path.join(out_dir, name + "_before_after.gif")], check=True)


def sheet(before, after, name, out_dir, step_s=0.5, columns=8, scale=0.22):
    rows = []
    for title, seq in [("ДО", before), ("ПОСЛЕ", after)]:
        picks = seq[::max(1, int(step_s * FPS))][:columns * 2]
        rows.append((title, picks))
    ref = Image.open((before or after)[0])
    w, h = int(ref.width * scale), int(ref.height * scale)
    lines = sum(max(1, (len(p) + columns - 1) // columns) for _, p in rows)
    canvas = Image.new("RGB", (columns * w, lines * h + 34 * len(rows)), (20, 20, 20))
    d = ImageDraw.Draw(canvas)
    y = 0
    for title, picks in rows:
        d.text((8, y + 6), "%s — %s (кадр каждые %.1f с)" % (name, title, step_s), fill=(255, 220, 120), font=font(20))
        y += 34
        for i, path in enumerate(picks):
            tile = Image.open(path).convert("RGB").resize((w, h), Image.LANCZOS)
            ImageDraw.Draw(tile).text((4, 2), "%.1f" % (i * step_s), fill=(255, 255, 255), font=font(14))
            canvas.paste(tile, ((i % columns) * w, y + (i // columns) * h))
        y += max(1, (len(picks) + columns - 1) // columns) * h
    canvas.save(os.path.join(out_dir, name + "_sheet.jpg"), quality=82)


def stills(before_dir, after_dir, out_dir, prefix, out_name):
    names = sorted(f for f in os.listdir(after_dir) if f.startswith(prefix) and f.endswith(".png"))
    if not names:
        return
    tiles = []
    for name in names:
        for title, folder in [("ДО", before_dir), ("ПОСЛЕ", after_dir)]:
            path = os.path.join(folder, name)
            if os.path.exists(path):
                im = Image.open(path).convert("RGB")
                im = im.resize((im.width * 3 // 5, im.height * 3 // 5), Image.LANCZOS)
                tiles.append(label(im, "%s  %s" % (title, name[:-4])))
    w, h = tiles[0].width, tiles[0].height
    canvas = Image.new("RGB", (2 * w + 8, ((len(tiles) + 1) // 2) * (h + 8)), (16, 16, 16))
    for i, tile in enumerate(tiles):
        canvas.paste(tile, ((i % 2) * (w + 8), (i // 2) * (h + 8)))
    canvas.save(os.path.join(out_dir, out_name), quality=86)


def load(folder, name):
    path = os.path.join(folder, name)
    return json.load(open(path)) if os.path.exists(path) else {}


def tables(before_qa, after_qa, out_dir):
    rows = ["action\tlatency_ms\tbefore_first_visual_ms\tafter_first_visual_ms\tbefore_confirmed_ms\tafter_confirmed_ms\tn"]
    for lat in LATENCIES:
        b = load(before_qa, "qa_legacy_lat%d.json" % lat).get("latency", {}).get("actions", {})
        a = load(after_qa, "qa_legacy_lat%d.json" % lat).get("latency", {}).get("actions", {})
        for action in sorted(set(a) | set(b)):
            def cell(d, key):
                v = d.get(action, {}).get(key)
                return "—" if v is None or v < 0 else "%.0f" % v
            rows.append("\t".join([action, str(lat), cell(b, "first_visual_ms_max"), cell(a, "first_visual_ms_max"),
                                   cell(b, "confirmed_ms_max"), cell(a, "confirmed_ms_max"), str(a.get(action, {}).get("n", ""))]))
    open(os.path.join(out_dir, "latency.tsv"), "w").write("\n".join(rows) + "\n")
    cages = ["site\tname\tcage\tbefore_cage_shown\tbefore_captives_in_cage\tbefore_release_s\tafter_cage_shown\tafter_captives_in_cage\tafter_release_s\tafter_released\tresult"]
    b = load(before_qa, "qa_kingdom_all.json").get("cages", {})
    a = load(after_qa, "qa_kingdom_all.json").get("cages", {})
    for site in sorted(set(a) | set(b)):
        x, y = b.get(site, {}), a.get(site, {})
        ok = bool(y.get("cage_shown")) and int(y.get("captives_in_cage_shown", 0)) == int(y.get("captives", 3)) and bool(y.get("released"))
        cages.append("\t".join(str(v) for v in [site, y.get("name", x.get("name", "")), y.get("cage", x.get("cage", "")),
                                                 x.get("cage_shown", ""), x.get("captives_in_cage_shown", ""), x.get("release_scene_s", ""),
                                                 y.get("cage_shown", ""), y.get("captives_in_cage_shown", ""), y.get("release_scene_s", ""),
                                                 y.get("released", ""), "PASS" if ok else "FAIL"]))
    open(os.path.join(out_dir, "cages.tsv"), "w").write("\n".join(cages) + "\n")
    checks = ["run\tbefore_checks\tbefore_failures\tafter_checks\tafter_failures"]
    for name in ["qa_legacy_lat0.json", "qa_legacy_lat300.json", "qa_legacy_lat700.json", "qa_kingdom_all.json"]:
        x, y = load(before_qa, name), load(after_qa, name)
        checks.append("\t".join(str(v) for v in [name[:-5], x.get("checks", ""), len(x.get("failures", [])), y.get("checks", ""), len(y.get("failures", []))]))
    open(os.path.join(out_dir, "checks.tsv"), "w").write("\n".join(checks) + "\n")


def main():
    before_shots, after_shots, before_qa, after_qa, out_dir = sys.argv[1:6]
    os.makedirs(out_dir, exist_ok=True)
    for segment in SEGMENTS:
        b, a = frames(os.path.join(before_shots, segment)), frames(os.path.join(after_shots, segment))
        if not a and not b:
            continue
        pair_video(b, a, segment, out_dir)
        sheet(b, a, segment, out_dir)
    stills(before_shots, after_shots, out_dir, "puzzle_", "puzzle_before_after.jpg")
    stills(before_shots, after_shots, out_dir, "cage_before_", "cage_before_before_after.jpg")
    stills(before_shots, after_shots, out_dir, "intro_end", "intro_end_before_after.jpg")
    tables(before_qa, after_qa, out_dir)


if __name__ == "__main__":
    main()
