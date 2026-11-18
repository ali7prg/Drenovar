"""City-camera view (exact landscape.gd city camera/light) of one landmark GLB at zoom 40 and 68, next to its
art/01 counterpart crop at matched scale. Usage: godot_city_landmark.py <asset> <art01_box x0,y0,x1,y1> <out_png>"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
LM = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "landmarks")
ART = os.path.join(REPO, "forest_rescue", "delivery", "art")


def main(asset, box, out_png, nodes=None):
    work = tempfile.mkdtemp(prefix="frcitylm.")
    shutil.copytree(os.path.join(HERE, "godot_city_viewer"), work, dirs_exist_ok=True)
    os.makedirs(os.path.join(work, "models"), exist_ok=True)
    for f in os.listdir(LM):
        if f.startswith("lm_") or f == f"{asset}.glb":
            shutil.copy(os.path.join(LM, f), os.path.join(work, "models", f))
    meta = json.load(open(os.path.join(LM, f"{asset}.meta.json")))
    nodes = nodes or meta["nodes"]["LOD0"]
    spec = dict(instances=[dict(glb=f"{asset}.glb", node=n, x=0.0, z=0.0, yaw=0.0, s=1.0, tag="lm") for n in nodes],
                ground=[0.40, 0.42, 0.24], target=[0, 1.0, 0])
    json.dump(spec, open(os.path.join(work, "spec.json"), "w"))
    subprocess.run(["timeout", "600", "godot", "--headless", "--path", work, "--import"], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    od = os.path.join(work, "out")
    r = subprocess.run(["timeout", "600", "xvfb-run", "-a", "-s", "-screen 0 1280x720x24", "godot", "--path", work,
                        "--rendering-driver", "vulkan", "--", "--spec=res://spec.json", "--zooms=68,40", f"--out={od}",
                        "--k=0.35", "--k_vol=0.5"], capture_output=True, text=True)
    shots = {}
    for z in ("68", "40"):
        p = os.path.join(od, f"city_zoom{z}.png")
        if os.path.exists(p):
            shots[z] = np.asarray(Image.open(p).convert("RGB"))
    art = np.asarray(Image.open(os.path.join(ART, "01_world_masterplan.png")).convert("RGB"))
    x0, y0, x1, y1 = box
    panels, labels = [], []
    for z, sc in (("68", 1.0), ("40", 68 / 40)):
        crop = Image.fromarray(art[y0:y1, x0:x1]).resize((int((x1 - x0) * sc), int((y1 - y0) * sc)), Image.LANCZOS)
        panels.append(np.asarray(crop))
        labels.append(f"art/01 crop (scale-matched to zoom {z})")
        if z in shots:
            g = shots[z]
            h, w = g.shape[:2]
            cw, ch = min(w, int(crop.size[0] * 1.6)), min(h, int(crop.size[1] * 1.6))
            g = g[(h - ch) // 2:(h + ch) // 2, (w - cw) // 2:(w + cw) // 2]
            panels.append(g)
            labels.append(f"Godot city camera zoom {z}: {asset}")
    H = 420
    row = []
    for im, lab in zip(panels, labels):
        pil = Image.fromarray(im).resize((max(1, int(im.shape[1] * H / im.shape[0])), H), Image.LANCZOS)
        d = ImageDraw.Draw(pil)
        d.rectangle([4, 4, 12 + 6 * len(lab), 20], fill=(20, 20, 20))
        d.text((8, 6), lab, fill=(255, 240, 200))
        row.append(np.asarray(pil))
    Image.fromarray(np.concatenate(row, 1)).save(out_png)
    shutil.rmtree(work, ignore_errors=True)
    print("wrote", out_png)


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], tuple(int(v) for v in a[1].split(",")), a[2])
