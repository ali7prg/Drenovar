"""Game-camera QA for the v2 humans in Godot 4.6.3 (Mobile, exact city camera/light).

    python3 godot_city_humans.py <out_dir> [row|group|both] [--anim-civ lf_civilian_wait] [--t 0.4]

row:   all 9 characters standing in a row next to the guide horse (scale check), zoom 40 / 68 + close.
group: 3 squad members escorting 3 captives (art/07 panel 3, art/18 panel 3 comparison).
Writes PNGs + a side-by-side sheet with the art crops into <out_dir>."""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
HUM = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "humans")
HORSE = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "horse", "lf_horse_origin.glb")
ART = os.path.join(REPO, "forest_rescue", "delivery", "art")
SQUAD = ["lf_squad_captain", "lf_squad_shield_guard", "lf_squad_scout"]
CIV = ["lf_civilian_miller", "lf_civilian_herbalist", "lf_civilian_ferryman", "lf_civilian_courier",
       "lf_civilian_cooper", "lf_civilian_quarry_worker"]


def k_of(aid):
    try:
        return float(json.load(open(os.path.join(HUM, f"{aid}.meta.json"))).get("paintedLightMix", 0.4))
    except Exception:
        return 0.4


def run(spec, out_dir, prefix):
    work = tempfile.mkdtemp(prefix="frhumans.")
    shutil.copytree(os.path.join(HERE, "godot_humans_viewer"), work, dirs_exist_ok=True)
    os.makedirs(os.path.join(work, "models"), exist_ok=True)
    for inst in spec["instances"]:
        src = HORSE if inst["glb"] == "lf_horse_origin.glb" else os.path.join(HUM, inst["glb"])
        dst = os.path.join(work, "models", inst["glb"])
        if not os.path.exists(dst):
            shutil.copy(src, dst)
    spec["out_prefix"] = prefix
    json.dump(spec, open(os.path.join(work, "spec.json"), "w"))
    subprocess.run(["timeout", "900", "godot", "--headless", "--path", work, "--import"], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    r = subprocess.run(["timeout", "900", "xvfb-run", "-a", "-s", "-screen 0 1280x720x24", "godot", "--path", work,
                        "--rendering-driver", "vulkan", "--", "--spec=res://spec.json", f"--out={out_dir}"],
                       capture_output=True, text=True)
    for line in (r.stdout + r.stderr).splitlines():
        if "VIEWER" in line or "ERROR" in line:
            print(line)
    shutil.rmtree(work, ignore_errors=True)


def row_spec(anim_civ="lf_civilian_wait", anim_sq="lf_soldier_idle", t=0.4):
    yaw = math.pi / 4
    perp = np.array([1.0, -1.0]) / math.sqrt(2)
    inst = []
    names = [a for a in SQUAD + CIV if os.path.exists(os.path.join(HUM, f"{a}.glb"))]
    d = 1.15
    for i, a in enumerate(names):
        x, z = perp * (i - (len(names) - 1) / 2) * d
        inst.append(dict(glb=f"{a}.glb", x=float(x), z=float(z), yaw=yaw, painted=True, k=k_of(a),
                         anim=anim_sq if a.startswith("lf_squad") else anim_civ, t=t, lod=0))
    x, z = perp * ((len(names) + 1.2) - (len(names) - 1) / 2) * d
    inst.append(dict(glb="lf_horse_origin.glb", x=float(x), z=float(z), yaw=yaw + math.pi / 2, painted=False,
                     anim="lf_horse_idle", t=0.5, lod=0))
    return dict(instances=inst, target=[0.0, 0.9, 0.0], ground=[0.40, 0.42, 0.24], zooms="40,68",
                close=dict(size=7.5, target=[0.0, 0.9, 0.0]))


def group_spec(t=0.3):
    """3 soldiers escorting 3 captives along a path (walk/follow clips), like art/07 / art/18."""
    inst = []
    heading = math.radians(200)          # walking toward the lower-left of the screen (toward the camera side)
    fwd = np.array([math.sin(heading), math.cos(heading)])
    side = np.array([fwd[1], -fwd[0]])
    order = [("lf_squad_captain", 0.0, 0.0, "lf_soldier_walk"),
             ("lf_civilian_cooper", -1.6, 0.5, "lf_civilian_follow"),
             ("lf_civilian_herbalist", -1.9, -0.5, "lf_civilian_follow"),
             ("lf_civilian_miller", -3.4, 0.0, "lf_civilian_follow_tired"),
             ("lf_squad_shield_guard", -4.9, -0.9, "lf_soldier_walk"),
             ("lf_squad_scout", -5.2, 0.9, "lf_soldier_walk")]
    for i, (a, back, lat, anim) in enumerate(order):
        if not os.path.exists(os.path.join(HUM, f"{a}.glb")):
            continue
        p = fwd * back + side * lat
        inst.append(dict(glb=f"{a}.glb", x=float(p[0]), z=float(p[1]), yaw=heading, painted=True, k=k_of(a),
                         anim=anim, t=t + 0.17 * i, lod=0))
    return dict(instances=inst, target=[-2.5 * fwd[0], 0.9, -2.5 * fwd[1]], ground=[0.40, 0.42, 0.24],
                zooms="40,68", close=dict(size=8.0, target=[float(-2.5 * fwd[0]), 0.9, float(-2.5 * fwd[1])]))


def heads_spec():
    """All 9 characters, LOD0 and LOD1 copies 3 m apart, idle pose frame 0; camera visits each head."""
    inst, heads = [], []
    names = [a for a in SQUAD + CIV if os.path.exists(os.path.join(HUM, f"{a}.glb"))]
    for i, a in enumerate(names):
        meta = json.load(open(os.path.join(HUM, f"{a}.meta.json")))
        head_y = float(meta["sockets"]["head_top"][1]) - 0.10
        idle = "lf_soldier_idle" if a.startswith("lf_squad") else "lf_civilian_wait"
        for lod in (0, 1):
            x = i * 3.0
            z = lod * 3.0
            inst.append(dict(glb=f"{a}.glb", x=x, z=z, yaw=0.0, painted=True, k=k_of(a), anim=idle, t=0.0, lod=lod))
            heads.append(dict(tag=f"{a}_LOD{lod}", x=x, y=head_y, z=z))
    return dict(instances=inst, heads=heads, target=[0, 1, 0], ground=[0.40, 0.42, 0.24])


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle([4, 4, 12 + 6 * len(text), 20], fill=(20, 20, 20))
    d.text((8, 6), text, fill=(255, 240, 200))
    return im


def sheet(out_dir, prefix, art_crops, out_png):
    panels = []
    for name, box in art_crops:
        a = Image.open(os.path.join(ART, name)).convert("RGB").crop(box)
        a = a.resize((int(a.size[0] * 420 / a.size[1]), 420), Image.LANCZOS)
        panels.append(label(a, f"art {name.split('_')[0]} crop"))
    for z in ("40", "68"):
        p = os.path.join(out_dir, f"{prefix}_zoom{z}.png")
        if os.path.exists(p):
            g = Image.open(p).convert("RGB")
            w, h = g.size
            cw = 300 if z == "40" else 180
            ch = int(cw * 0.66)
            g = g.crop((w // 2 - cw // 2, h // 2 - ch // 2, w // 2 + cw // 2, h // 2 + ch // 2)).resize((int(420 / 0.66), 420), Image.NEAREST)
            panels.append(label(g, f"Godot city camera zoom {z} (pixel-zoomed {420 / ch:.1f}x)"))
    p = os.path.join(out_dir, f"{prefix}_close.png")
    if os.path.exists(p):
        g = Image.open(p).convert("RGB")
        g = g.resize((int(g.size[0] * 420 / g.size[1]), 420))
        panels.append(label(g, "Godot same camera, ortho 7.5 (detail)"))
    W = sum(p.size[0] for p in panels)
    S = Image.new("RGB", (W, 420), (30, 30, 30))
    x = 0
    for p in panels:
        S.paste(p, (x, 0))
        x += p.size[0]
    S.save(out_png)
    print("wrote", out_png)


if __name__ == "__main__":
    out = os.path.abspath(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else "both"
    os.makedirs(out, exist_ok=True)
    if mode == "heads":
        run(heads_spec(), out, "heads")
        sys.exit(0)
    if mode in ("row", "both"):
        run(row_spec(), out, "row")
        sheet(out, "row", [("07_fog_exploration_interface.png", (520, 330, 1010, 690))], os.path.join(out, "row_sheet.png"))
    if mode in ("group", "both"):
        run(group_spec(), out, "group")
        sheet(out, "group", [("07_fog_exploration_interface.png", (520, 330, 1010, 690)),
                             ("18_hall3_unlock_intro.png", (520, 520, 1020, 1000))], os.path.join(out, "group_sheet.png"))
