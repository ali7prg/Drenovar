#!/usr/bin/env python3
"""Contact sheets of capture_squad_set.sh output (real game frames + enlarged crops of the battle camera).

usage: python3 squad_sheets.py <capture_dir> <out_img_dir> [--tag=ДО] [--groups=U3_ENG-01,U3_ENG-02,U3_ENG-03,U3_ENG-04,U3_ENG-06,MIX]
writes <tag-slug>_<group>.jpg per group (march/battle x zoom 68 crop / zoom 15), world68_full_*.jpg,
city*_MIX_battle.jpg, armory_<tag-slug>.jpg and armory_ui_ENG-02.jpg (if present).
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
OPTS = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
SRC = ARGS[0]
DST = ARGS[1]
TAG = OPTS.get("tag", "ДО")
SLUG = {"ДО": "before", "ПОСЛЕ": "after"}.get(TAG, "set")
GROUPS = OPTS.get("groups", "U3_ENG-01,U3_ENG-02,U3_ENG-03,U3_ENG-04,U3_ENG-06,MIX").split(",")
os.makedirs(DST, exist_ok=True)
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17)
FONT_B = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
PW, PH = 683, 315
NAMES = {"ENG-01": "ENG-01 копейщик", "ENG-02": "ENG-02 мечник со щитом", "ENG-03": "ENG-03 длиннолучник",
         "ENG-04": "ENG-04 арбалетчик", "ENG-06": "ENG-06 конный рыцарь",
         "MIX": "смешанный отряд ENG-01, 02, 03, 04 ×3 + ENG-06 ×2"}


def group_title(group):
    base = group.split("_", 1)[1] if group.startswith("U") and "_" in group else group
    count = group.split("_", 1)[0][1:] if group.startswith("U") else ""
    return NAMES.get(base, base) + (f" ×{count}" if count else "")


def tele(name):
    return json.load(open(os.path.join(SRC, name, "telemetry.json")))


def frame_row(t, idx):
    for f in t["frames"]:
        if f["frame"] == idx:
            return f
    return None


def pick_battle_frame(t, saved):
    best, score = saved[0], -1
    for idx in saved:
        f = frame_row(t, idx)
        if not f:
            continue
        s = 0
        for u in f["units"]:
            if u.get("clip") == "attack":
                s += 2 - abs(u.get("phase", 0) - 0.49) * 2
            if u.get("arrow", {}).get("visible"):
                s += 3
        if s > score:
            best, score = idx, s
    return best


def crop_box(f, pad=40, aspect=PW / PH):
    xs, ys = [], []
    for u in f["units"]:
        for key in ("screen_ground", "screen_head_top"):
            if u.get(key):
                xs.append(u[key][0]); ys.append(u[key][1])
    for c in f.get("creatures", []):
        pass
    if not xs:
        return (0, 0, 1366, 630)
    x0, x1, y0, y1 = min(xs) - pad, max(xs) + pad, min(ys) - pad - 10, max(ys) + pad
    w, h = x1 - x0, y1 - y0
    # keep panel aspect, at least 228x105 (x3) region
    w = max(w, h * aspect, 228)
    h = w / aspect
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    x0, y0 = max(0, cx - w / 2), max(0, cy - h / 2)
    x0, y0 = min(x0, 1366 - w), min(y0, 630 - h)
    return (int(x0), int(y0), int(x0 + w), int(y0 + h))


def panel(img, label, crop=None):
    if crop:
        region = img.crop(crop)
        factor = max(1, min(PW // region.width, PH // region.height))
        region = region.resize((region.width * factor, region.height * factor), Image.NEAREST)
        region = region.resize((PW, PH), Image.LANCZOS) if region.size != (PW, PH) else region
        label += f" · фрагмент ×{(PW/(crop[2]-crop[0])):.1f}"
    else:
        region = img.resize((PW, PH), Image.LANCZOS)
    out = Image.new("RGB", (PW, PH + 26), (20, 24, 22))
    out.paste(region.convert("RGB"), (0, 26))
    d = ImageDraw.Draw(out)
    d.text((6, 3), label, font=FONT, fill=(235, 225, 200))
    return out


def sheet(group):
    rows = []
    marchinfo = "марш 1.2 м/с"
    for scen, scen_ru in (("march", marchinfo), ("battle", "бой")):
        cells = []
        for cam, cam_ru in (("battle", "мир zoom 68"), ("close", "мир zoom 15")):
            name = f"{group}_{scen}_{cam}"
            if not os.path.exists(os.path.join(SRC, name, "telemetry.json")):
                return None
            t = tele(name)
            saved = sorted(int(fn[2:7]) for fn in os.listdir(os.path.join(SRC, name, "frames")) if fn.startswith("f_"))
            idx = pick_battle_frame(t, saved) if scen == "battle" else (saved[1] if len(saved) > 1 else saved[0])
            img = Image.open(os.path.join(SRC, name, "frames", f"f_{idx:05d}.png"))
            f = frame_row(t, idx)
            tt = f["t"] if f else 0
            extra = f" · t={tt:.2f} с" + (f" (бой +{f.get('battle_elapsed_ms', 0)/1000:.2f} с)" if scen == "battle" and f and f.get("battle_elapsed_ms") is not None else "")
            label = f"{scen_ru} · {cam_ru}{extra}"
            cells.append(panel(img, label, crop_box(f) if (cam == "battle" and f) else None))
        row = Image.new("RGB", (PW * 2 + 4, cells[0].height), (10, 10, 10))
        row.paste(cells[0], (0, 0)); row.paste(cells[1], (PW + 4, 0))
        rows.append(row)
    title_h = 34
    out = Image.new("RGB", (rows[0].width, title_h + sum(r.height for r in rows) + 4), (10, 10, 10))
    d = ImageDraw.Draw(out)
    d.text((8, 6), f"{TAG} · {group_title(group)} · landscape.gd, Mobile, 1366×630", font=FONT_B, fill=(250, 240, 210))
    y = title_h
    for r in rows:
        out.paste(r, (0, y)); y += r.height + 4
    path = os.path.join(DST, f"{SLUG}_{group.split('_', 1)[1] if group.startswith('U') else group}.jpg")
    out.save(path, quality=86, optimize=True)
    return path, os.path.getsize(path)


for g in GROUPS:
    r = sheet(g)
    print(g, r)

# full-size real frames at the battle camera (true scale)
for name, out in (("MIX_battle_battle", "world68_full_MIX_battle.jpg"), ("MIX_march_battle", "world68_full_MIX_march.jpg")):
    p = os.path.join(SRC, name)
    if os.path.exists(os.path.join(p, "telemetry.json")):
        t = tele(name)
        saved = sorted(int(fn[2:7]) for fn in os.listdir(os.path.join(p, "frames")) if fn.startswith("f_"))
        idx = pick_battle_frame(t, saved) if "battle_battle" in name else saved[1]
        Image.open(os.path.join(p, "frames", f"f_{idx:05d}.png")).convert("RGB").save(os.path.join(DST, out), quality=88, optimize=True)
        print(out, os.path.getsize(os.path.join(DST, out)))

# city frames
for name, out in (("MIX_city_battle_battle", "city70_MIX_battle.jpg"), ("MIX_city_battle_close", "city24_MIX_battle.jpg")):
    p = os.path.join(SRC, name)
    if os.path.exists(os.path.join(p, "telemetry.json")):
        t = tele(name)
        saved = sorted(int(fn[2:7]) for fn in os.listdir(os.path.join(p, "frames")) if fn.startswith("f_"))
        idx = pick_battle_frame(t, saved)
        Image.open(os.path.join(p, "frames", f"f_{idx:05d}.png")).convert("RGB").save(os.path.join(DST, out), quality=88, optimize=True)
        print(out, os.path.getsize(os.path.join(DST, out)))

# armory
arm = os.path.join(SRC, "armory")
if os.path.exists(os.path.join(arm, "telemetry.json")):
    h = json.load(open(os.path.join(arm, "telemetry.json")))["header"]
    rows = []
    for uid in ("ENG-01", "ENG-02", "ENG-03", "ENG-04", "ENG-06"):
        info = h["armory"].get(uid)
        if not info:
            continue
        cells = []
        for fr in info["frames"]:
            v = Image.open(os.path.join(arm, fr["file"].replace(".png", "_view.png"))).convert("RGBA")
            bg = Image.new("RGBA", v.size, (48, 66, 62, 255))
            bg.alpha_composite(v)
            c = bg.convert("RGB")
            d = ImageDraw.Draw(c)
            d.text((6, 4), f"{uid} · {info['clip']} · фаза {fr['phase']:.2f}", font=FONT, fill=(240, 230, 205))
            cells.append(c)
        row = Image.new("RGB", (sum(c.width for c in cells) + 3 * (len(cells) - 1), cells[0].height), (10, 10, 10))
        x = 0
        for c in cells:
            row.paste(c, (x, 0)); x += c.width + 3
        rows.append(row)
    W = max(r.width for r in rows)
    out = Image.new("RGB", (W, 36 + sum(r.height + 3 for r in rows)), (10, 10, 10))
    d = ImageDraw.Draw(out)
    d.text((8, 7), f"{TAG} · оружейная: preview (lod1), SubViewport 442×258 из main.gd::load_unit_preview, кадры по фазам клипа", font=FONT_B, fill=(250, 240, 210))
    y = 36
    for r in rows:
        out.paste(r, (0, y)); y += r.height + 3
    out = out.resize((1366, int(out.height * 1366 / out.width)), Image.LANCZOS)
    path = os.path.join(DST, f"armory_{SLUG}.jpg")
    out.save(path, quality=86, optimize=True)
    print(path, os.path.getsize(path))
    # one full armory UI frame
    ui = os.path.join(arm, "frames", "armory_ENG-02_p000.png")
    if os.path.exists(ui):
        Image.open(ui).convert("RGB").save(os.path.join(DST, "armory_ui_ENG-02.jpg"), quality=88, optimize=True)
