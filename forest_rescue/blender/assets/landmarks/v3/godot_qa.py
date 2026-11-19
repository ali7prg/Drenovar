"""Godot QA for v3 landmarks: (1) exact game city camera/light (paint3d/godot_city_viewer: ortho size = zoom,
position target + (75, 83, 75), sun (-48,-32,0) #ffe4b8 x1.85, ambient #d8e5ee x0.58, FILMIC, bg #8b9874) at zoom
68 and 40 next to the art/01 crop at matched scale; (2) painted-light viewer shots (front + 3/4).
Usage: godot_qa.py <asset_id> <art01_box x0,y0,x1,y1> <out_prefix> [yaw_deg_for_city]"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
P3D = os.path.abspath(os.path.join(HERE, "..", "..", "paint3d"))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
LM = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "landmarks")
ART = os.path.join(REPO, "forest_rescue", "delivery", "art")


def copy_assets(asset, dst):
    meta = json.load(open(os.path.join(LM, f"{asset}.meta.json")))
    os.makedirs(dst, exist_ok=True)
    for f in [f"{asset}.glb"] + [n for n in meta.get("glb_images", []) if not n.startswith("<")] + list(meta.get("textures", {})):
        p = os.path.join(LM, f)
        if os.path.exists(p):
            shutil.copy(p, os.path.join(dst, f))
    return meta


MOCK = """
	if spec.has("mock_river"):
		ground.position.y = -50.0
		var wm := StandardMaterial3D.new()
		wm.albedo_color = Color(0.17, 0.36, 0.37)
		wm.roughness = 0.15
		var water := MeshInstance3D.new()
		var wpm := PlaneMesh.new()
		wpm.size = Vector2(14.0, 140.0)
		water.mesh = wpm
		water.material_override = wm
		water.position = Vector3(0, -1.35, 0)
		add_child(water)
		for sgn in [-1.0, 1.0]:
			var bank := MeshInstance3D.new()
			var bm := BoxMesh.new()
			bm.size = Vector3(60.0, 4.0, 140.0)
			bank.mesh = bm
			var bmat := StandardMaterial3D.new()
			bmat.albedo_color = Color(0.43, 0.46, 0.25)
			bank.material_override = bmat
			bank.position = Vector3(sgn * (6.4 + 30.0), 0.45 - 2.0, 0)
			add_child(bank)
			var slope := MeshInstance3D.new()
			var sm := BoxMesh.new()
			sm.size = Vector3(2.6, 0.3, 140.0)
			slope.mesh = sm
			var smat := StandardMaterial3D.new()
			smat.albedo_color = Color(0.45, 0.38, 0.28)
			slope.material_override = smat
			slope.position = Vector3(sgn * 6.0, -0.45, 0)
			slope.rotation.z = sgn * 0.62
			add_child(slope)
"""


def city(asset, box, out_png, yaw=0.0, base=True, mock_river=False):
    work = tempfile.mkdtemp(prefix="frcity3.")
    shutil.copytree(os.path.join(P3D, "godot_city_viewer"), work, dirs_exist_ok=True)
    meta = copy_assets(asset, os.path.join(work, "models"))
    gy = float(os.environ.get("LM3_GROUND_Y", "0"))
    if gy != 0.0:
        src = open(os.path.join(work, "city.gd")).read()
        src = src.replace("\tadd_child(ground)", "\tground.position.y = %f\n\tadd_child(ground)" % gy)
        open(os.path.join(work, "city.gd"), "w").write(src)
    nodes = [n for n in meta["nodes"]["LOD0"] if base or not n.endswith("_base")]
    spec = dict(instances=[dict(glb=f"{asset}.glb", node=n, x=0.0, z=0.0, yaw=yaw, s=1.0, tag="lm") for n in nodes],
                ground=[0.40, 0.42, 0.24], target=[0, 1.0, 0])
    if mock_river:
        spec["mock_river"] = True
        src = open(os.path.join(work, "city.gd")).read()
        src = src.replace("\tadd_child(ground)\n", "\tadd_child(ground)\n" + MOCK, 1)
        open(os.path.join(work, "city.gd"), "w").write(src)
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
    if not shots:
        print(r.stdout[-2000:], r.stderr[-2000:])
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
            cw, ch = min(w, crop.size[0]), min(h, crop.size[1])
            panels.append(g[(h - ch) // 2:(h + ch) // 2, (w - cw) // 2:(w + cw) // 2])
            labels.append(f"Godot game camera zoom {z} (LOD0, base {'on' if base else 'OFF'}{', mock river' if mock_river else ''})")
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
    print("wrote", out_png, flush=True)


def viewer(asset, out_png):
    work = tempfile.mkdtemp(prefix="frview3.")
    copy_assets(asset, work)
    od = os.path.join(work, "shots")
    subprocess.run(["bash", os.path.join(P3D, "godot_paint_view.sh"), os.path.join(work, f"{asset}.glb"), od,
                    "--painted=0.35", "--pitches=8,32", "--yaws=0,35", "--ground=1"], capture_output=True, text=True)
    ims = sorted(f for f in os.listdir(od) if f.endswith(".png")) if os.path.isdir(od) else []
    if not ims:
        print("viewer produced no shots")
        return
    tiles = [np.asarray(Image.open(os.path.join(od, f)).convert("RGB")) for f in ims]
    H = 400
    row = [np.asarray(Image.fromarray(t).resize((int(t.shape[1] * H / t.shape[0]), H), Image.LANCZOS)) for t in tiles]
    Image.fromarray(np.concatenate(row, 1)).save(out_png)
    shutil.rmtree(work, ignore_errors=True)
    print("wrote", out_png, ims, flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    yaw = float(a[3]) if len(a) > 3 else 0.0
    box = tuple(int(v) for v in a[1].split(","))
    mock = os.environ.get("LM3_MOCK_RIVER") == "1"
    city(a[0], box, a[2] + "_city_baseoff.png", np.radians(yaw), base=False, mock_river=mock)
    city(a[0], box, a[2] + "_city_baseon.png", np.radians(yaw), base=True, mock_river=False)
    viewer(a[0], a[2] + "_viewer.png")
