"""Game-camera patch in Godot (exact city camera/light of landscape.gd): ~40 mixed instances of kit trees,
zoom 68 and 40, next to art/01 crops at matched scale (+ per-species colour stats vs art/01).

python3 godot_city_patch.py <out_prefix> [--n 40] [--species golden_oak:2,3,4 dark_pine:1,2,3,4 birch:1,2,3]
Plain python (PIL/numpy via the blender venv for stats)."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RT = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "forest")
ART = os.path.join(REPO, "forest_rescue", "delivery", "art")
sys.path.insert(0, HERE)

TAGS = {"golden_oak": "oak", "dark_pine": "pine", "birch": "birch", "willow": "willow", "hollow_oak": "hollow",
        "moss_rock": "rock", "fallen_trunk": "trunk", "bramble": "bramble", "reed_fern": "reed"}
# art/01 reference crops (native art/01 px ~= 10.6 px/m = city zoom 68 at 1280x720)
ART01 = {
    "grove": (0, 0, 640, 330),
    "south_pines": (430, 640, 960, 1000),
}
ART01_SETS = {
    "default": ["grove", "south_pines"],
    "hollow": ["grove"],
    "willow": ["east_river"],
    "rocks": ["sw_quarry"],
}
ART01.update({"east_river": (1000, 280, 1536, 700), "sw_quarry": (0, 620, 520, 1024)})
ART01_SPECIES = {   # single-species crops for colour stats
    "hollow": [(250, 120, 330, 200)],
    "rock": [(60, 800, 200, 900), (300, 860, 420, 960)],
    "willow": [(1290, 470, 1350, 540)],
    "oak": [(438, 126, 588, 228), (880, 290, 1000, 400)],
    "pine": [(0, 40, 120, 200), (560, 650, 700, 780)],
    "birch": [(1100, 560, 1200, 660)],
}


LAYOUT_KW = {}


def layout(species, n=40, area=64.0, spacing=8.5, seed=4):
    area = LAYOUT_KW.get("area", area)
    spacing = LAYOUT_KW.get("spacing", spacing)
    rng = np.random.default_rng(seed)
    pts = []
    tries = 0
    while len(pts) < n and tries < 40000:
        tries += 1
        p = rng.uniform(-area / 2, area / 2, 2)
        if all(np.linalg.norm(p - q) > spacing for q in pts):
            pts.append(p)
    inst = []
    keys = [(sp, v) for sp, vs in species for v in vs]
    order = rng.permutation(len(pts))
    for i, j in enumerate(order):
        sp, v = keys[i % len(keys)]
        x, z = pts[j]
        vname = v if isinstance(v, str) else f"v{v}"
        inst.append(dict(glb=f"lf_env_{sp}.glb", node=f"lf_env_{sp}_{vname}_LOD0", x=float(x), z=float(z),
                         yaw=float(rng.uniform(0, 2 * np.pi)), s=float(rng.uniform(0.85, 1.1)), tag=TAGS.get(sp, sp)))
    return inst


def run(out_prefix, species, n=40, k=0.3, k_vol=0.5, zooms="68,40", only_tags=()):
    work = tempfile.mkdtemp(prefix="frcity.")
    shutil.copytree(os.path.join(HERE, "godot_city_viewer"), work, dirs_exist_ok=True)
    os.makedirs(os.path.join(work, "models"), exist_ok=True)
    for f in os.listdir(RT):
        if f.endswith((".glb", ".png", ".jpg")) and not f.endswith(".import"):
            if f.endswith(".glb") and not any(f == f"lf_env_{sp}.glb" for sp, _ in species):
                continue
            shutil.copy(os.path.join(RT, f), os.path.join(work, "models", f))
    spec = dict(instances=layout(species, n), ground=[0.36, 0.40, 0.20], target=[0, 0, 0])
    with open(os.path.join(work, "spec.json"), "w") as fh:
        json.dump(spec, fh)
    subprocess.run(["timeout", "900", "godot", "--headless", "--path", work, "--import"], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    outdir = os.path.abspath(out_prefix + "_godot_city")
    os.makedirs(outdir, exist_ok=True)
    for only in ("",) + tuple(only_tags):
        cmd = ["timeout", "600", "xvfb-run", "-a", "-s", "-screen 0 1280x720x24", "godot", "--path", work,
               "--rendering-driver", "vulkan", "--", "--spec=res://spec.json", f"--zooms={zooms}", f"--out={outdir}",
               f"--k={k}", f"--k_vol={k_vol}"] + ([f"--only={only}"] if only else [])
        r = subprocess.run(cmd, capture_output=True, text=True)
        for line in (r.stdout + r.stderr).splitlines():
            if "VIEWER" in line or "ERROR" in line:
                print(line)
    shutil.rmtree(work, ignore_errors=True)
    return outdir


def lab_stats(img, mask):
    from skimage import color as skc
    px = np.clip(img[mask], 0, 1)
    if len(px) < 50:
        return None
    lab = skc.rgb2lab(px[None])[0]
    C = np.hypot(lab[:, 1], lab[:, 2])
    H = np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) % 360
    return {"L_p10_p50_p90": np.round(np.percentile(lab[:, 0], [10, 50, 90]), 1).tolist(),
            "C_med": round(float(np.median(C)), 1), "hue_med": round(float(np.median(H)), 1),
            "mean_rgb": np.round(px.mean(0), 3).tolist(), "n": int(len(px))}


def sheet(outdir, out_png, species_tags, art_set="default"):
    import cv2
    art01 = np.asarray(Image.open(os.path.join(ART, "01_world_masterplan.png")).convert("RGB"), np.float32) / 255
    panels = []
    labels = []
    for z, sc in (("68", 1.0), ("40", 68 / 40)):
        p = os.path.join(outdir, f"city_zoom{z}.png")
        if not os.path.exists(p):
            continue
        g = np.asarray(Image.open(p).convert("RGB"), np.float32) / 255
        for name in ART01_SETS.get(art_set, ART01_SETS["default"]):
            box = ART01[name]
            x0, y0, x1, y1 = box
            c = art01[y0:y1, x0:x1]
            c = cv2.resize(c, (int(c.shape[1] * sc), int(c.shape[0] * sc)), interpolation=cv2.INTER_CUBIC)
            c = c[:720, :640]
            panels.append(c)
            labels.append(f"art/01 {name} (scale-matched to zoom {z})")
        panels.append(g)
        labels.append(f"Godot city camera, zoom {z} (ortho 38deg, city sun/env)")
    H = 720
    row = []
    for im, lab in zip(panels, labels):
        s = H / im.shape[0]
        im = cv2.resize(im, (int(im.shape[1] * s), H), interpolation=cv2.INTER_AREA)
        u8 = (np.clip(im, 0, 1) * 255).astype(np.uint8)
        from PIL import ImageDraw
        pil = Image.fromarray(u8)
        d = ImageDraw.Draw(pil)
        d.rectangle([4, 4, 12 + 7 * len(lab), 22], fill=(20, 20, 20))
        d.text((8, 7), lab, fill=(255, 240, 200))
        row.append(np.asarray(pil))
    # two rows: zoom 68 (art crops + render), zoom 40
    half = len(row) // 2
    r1 = np.concatenate(row[:half], 1)
    r2 = np.concatenate(row[half:], 1)
    w = max(r1.shape[1], r2.shape[1])
    r1 = np.pad(r1, ((0, 0), (0, w - r1.shape[1]), (0, 0)))
    r2 = np.pad(r2, ((0, 0), (0, w - r2.shape[1]), (0, 0)))
    Image.fromarray(np.concatenate([r1, r2], 0)).save(out_png)
    # colour stats per species (single-species renders, zoom 68) vs art/01 crops
    stats = {}
    bg = np.array([0x8b, 0x98, 0x74]) / 255.0
    for tag in species_tags:
        p = os.path.join(outdir, f"city_zoom68_{tag}.png")
        if not os.path.exists(p):
            continue
        g = np.asarray(Image.open(p).convert("RGB"), np.float32) / 255
        ground = np.median(g.reshape(-1, 3), 0)
        m = np.abs(g - ground).sum(2) > 0.06
        # exclude cast shadows on the ground (darker ground, same hue)
        sh = (np.abs(g / np.maximum(g.sum(2, keepdims=True), 1e-3) - ground / ground.sum()).sum(2) < 0.03)
        m &= ~sh
        stats[tag] = {"model_zoom68": lab_stats(g, m)}
        refs_ = []
        for box in ART01_SPECIES.get(tag, []):
            x0, y0, x1, y1 = box
            c = art01[y0:y1, x0:x1].reshape(-1, 3)
            refs_.append(c)
        if refs_:
            c = np.concatenate(refs_)[None]
            from skimage import color as skc
            lab = skc.rgb2lab(c)[0]
            Cc = np.hypot(lab[:, 1], lab[:, 2])
            mm = Cc > 12
            stats[tag]["art01"] = lab_stats(c[0][None], mm[None])
    with open(out_png.replace(".png", "_colour.json"), "w") as fh:
        json.dump(stats, fh, indent=1)
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out_prefix")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--species", nargs="+", default=["golden_oak:2,3", "dark_pine:1,2,3,4", "birch:1,2,3"])
    ap.add_argument("--k", type=float, default=0.3)
    ap.add_argument("--k_vol", type=float, default=0.5)
    ap.add_argument("--art", default="default")
    ap.add_argument("--area", type=float, default=64.0)
    ap.add_argument("--spacing", type=float, default=8.5)
    a = ap.parse_args()
    species = []
    for s in a.species:
        name, vs = s.split(":")
        species.append((name, [int(v) if v.isdigit() else v for v in vs.split(",")]))
    tags = [TAGS.get(sp, sp) for sp, _ in species]
    LAYOUT_KW.update(area=a.area, spacing=a.spacing)
    od = run(a.out_prefix, species, a.n, a.k, a.k_vol, only_tags=tags)
    st = sheet(od, os.path.abspath(a.out_prefix) + "_city_patch.png", tags, a.art)
    print(json.dumps(st, indent=1))
