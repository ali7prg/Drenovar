#!/usr/bin/env python3
"""Frame strip of one attack window per unit type from a full-rate capture (qa_eng_squad_capture.gd, --every=1).

usage: python3 attack_strip.py <capture_dir> <out.jpg> [--units=ENG-01,ENG-02,ENG-03,ENG-04,ENG-06] [--phases=0,0.12,0.23,0.3,0.4,0.49,0.65,0.9] [--tag=ДО]
For every unit type it picks the first soldier_attack event whose whole window [at-490, at+510] lies inside the
capture and the member stayed in the attack clip, then crops the member on the frames nearest to the requested
window phases (0.23 = projectile release, 0.49 = impact/arrival). Labels show clip, clip phase and arrow state.
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
OPTS = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
SRC, OUT = ARGS[0], ARGS[1]
UNITS = OPTS.get("units", "ENG-01,ENG-02,ENG-03,ENG-04,ENG-06").split(",")
PHASES = [float(x) for x in OPTS.get("phases", "0,0.12,0.23,0.3,0.4,0.49,0.65,0.9").split(",")]
TAG = OPTS.get("tag", "ДО")
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
FONT_B = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 17)
CW, CH = 170, 190

t = json.load(open(os.path.join(SRC, "telemetry.json")))
h, frames = t["header"], t["frames"]
ext = "jpg" if os.path.exists(os.path.join(SRC, "frames", "f_00000.jpg")) else "png"
by_el = [(f.get("battle_elapsed_ms"), f) for f in frames if f.get("battle_elapsed_ms") is not None]


def member(f, name):
    for u in f["units"]:
        if u["name"] == name:
            return u
    return None


rows = []
for uid in UNITS:
    chosen = None
    for ev in h.get("events", []):
        if ev[1] != "soldier_attack" or ev[2] != uid:
            continue
        at, name = ev[0], f"{ev[2]}_{ev[3]}"
        window = [(el, f) for el, f in by_el if at - 490 <= el <= at + 510]
        if not window or window[0][0] > at - 450 or window[-1][0] < at + 480:
            continue
        if all((member(f, name) or {}).get("clip") == "attack" for el, f in window):
            chosen = (at, name, window)
            break
    if not chosen:
        print("no complete attack window for", uid)
        continue
    at, name, window = chosen
    cells = []
    for ph in PHASES:
        target = at - 490 + ph * 1000
        el, f = min(window, key=lambda w: abs(w[0] - target))
        u = member(f, name)
        img = Image.open(os.path.join(SRC, "frames", f"f_{f['frame']:05d}.{ext}")).convert("RGB")
        gx, gy = u["screen_ground"]
        tx, ty = u["screen_head_top"]
        cx, cy = gx, (gy + ty) / 2
        half_h = max(60, (gy - ty) * 0.9)
        half_w = half_h * CW / CH
        box = (int(cx - half_w), int(cy - half_h), int(cx + half_w), int(cy + half_h))
        crop = img.crop(box).resize((CW, CH), Image.LANCZOS)
        d = ImageDraw.Draw(crop)
        arrow = u.get("arrow", {}).get("visible", False)
        d.rectangle((0, 0, CW, 34), fill=(15, 18, 16))
        d.text((3, 1), f"окно {(el - at + 490) / 1000:.2f} · {u.get('animation', '')}", font=FONT, fill=(240, 230, 205))
        d.text((3, 17), f"фаза клипа {u.get('phase', 0):.2f}" + (" · стрела" if arrow else ""), font=FONT, fill=(255, 214, 128) if arrow else (200, 200, 190))
        cells.append(crop)
    row = Image.new("RGB", (len(cells) * (CW + 3), CH + 22), (8, 8, 8))
    d = ImageDraw.Draw(row)
    d.text((4, 3), f"{name}: удар/прилёт at = {at:.0f} мс от battleAt; окно [at−490, at+510]; 0.23 — выпуск, 0.49 — удар", font=FONT, fill=(250, 240, 210))
    for i, c in enumerate(cells):
        row.paste(c, (i * (CW + 3), 22))
    rows.append(row)
out = Image.new("RGB", (max(r.width for r in rows), 30 + sum(r.height + 4 for r in rows)), (8, 8, 8))
d = ImageDraw.Draw(out)
d.text((6, 5), f"{TAG} · одно окно атаки на тип бойца, кадры по фазам окна контроллера (телеметрия + кадры {os.path.basename(SRC)})", font=FONT_B, fill=(250, 240, 210))
y = 30
for r in rows:
    out.paste(r, (0, y)); y += r.height + 4
out.save(OUT, quality=88, optimize=True)
print(OUT, out.size, os.path.getsize(OUT))
