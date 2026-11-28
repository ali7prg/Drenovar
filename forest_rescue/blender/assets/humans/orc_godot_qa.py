#!/usr/bin/env python3
"""In-engine QA for lf_orc_warden (Godot 4.6.3, private temp projects only - never godot/project).

    python3 forest_rescue/blender/assets/humans/orc_godot_qa.py [all|city|shots|clip|tree]

city : exact city camera / sun / painted shader of the v2 human viewer (v2/godot_humans_viewer, copied to a
       temp dir; *_glow surfaces keep their emissive StandardMaterial3D as ActorRig does): the orc in several
       clip poses next to lf_squad_captain, at ortho 24 and 40 scaled to the game's 1170 px screen height.
shots: forest_rescue/tools/godot_view.sh shots (6 yaws, LOD0) ; clip: godot_view.sh clip, all clips.
tree : node paths of Skeleton3D / AnimationPlayer / meshes / animations as Godot imports the GLB.
Outputs in forest_rescue/qa/compare/lf_orc_warden/godot/ and forest_rescue/qa/video/lf_orc_warden/."""
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
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
HUM = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "humans")
VIEWER = os.path.join(HERE, "v2", "godot_humans_viewer")
OUT = os.path.join(REPO, "forest_rescue", "qa", "compare", "lf_orc_warden", "godot")
VID = os.path.join(REPO, "forest_rescue", "qa", "video", "lf_orc_warden")
TOOLS = os.path.join(REPO, "forest_rescue", "tools")
ID = "lf_orc_warden"
SCREEN_H, VIEW_H = 1170, 720          # game screen height vs. the viewer's xvfb window height


def run_city(spec, prefix):
    work = tempfile.mkdtemp(prefix="frorc.")
    shutil.copytree(VIEWER, work, dirs_exist_ok=True)
    gd = os.path.join(work, "humans.gd")
    src = open(gd).read()
    key = "\t\t\t\t\tif sm == null:\n\t\t\t\t\t\tcontinue\n"
    assert key in src, "viewer layout changed"
    src = src.replace(key, key + "\t\t\t\t\tif String(sm.resource_name).ends_with(\"_glow\"):\n\t\t\t\t\t\tcontinue\n", 1)
    open(gd, "w").write(src)
    os.makedirs(os.path.join(work, "models"), exist_ok=True)
    for inst in spec["instances"]:
        dst = os.path.join(work, "models", inst["glb"])
        if not os.path.exists(dst):
            shutil.copy(os.path.join(HUM, inst["glb"]), dst)
    spec["out_prefix"] = prefix
    json.dump(spec, open(os.path.join(work, "spec.json"), "w"))
    subprocess.run(["timeout", "900", "godot", "--headless", "--path", work, "--import"], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    r = subprocess.run(["timeout", "900", "xvfb-run", "-a", "-s", "-screen 0 1280x720x24", "godot", "--path", work,
                        "--rendering-driver", "vulkan", "--", "--spec=res://spec.json", f"--out={OUT}"],
                       capture_output=True, text=True)
    for line in (r.stdout + r.stderr).splitlines():
        if "VIEWER" in line or "ERROR" in line:
            print(line)
    shutil.rmtree(work, ignore_errors=True)


def city():
    os.makedirs(OUT, exist_ok=True)
    yaw = math.pi / 4                                   # face the camera (camera offset (75, 83, 75))
    perp = np.array([1.0, -1.0]) / math.sqrt(2)
    row = [("lf_squad_captain.glb", "lf_soldier_idle", 0.0, 0.4),
           (f"{ID}.glb", "lf_orc_idle", 0.0, 0.4),
           (f"{ID}.glb", "lf_orc_walk", 0.3, 0.4),
           (f"{ID}.glb", "lf_orc_drain", 1.9, 0.4),
           (f"{ID}.glb", "lf_orc_order_point", 1.5, 0.4),
           (f"{ID}.glb", "lf_orc_roar", 0.9, 0.4)]
    inst = []
    d = 1.9
    for i, (glb, anim, t, k) in enumerate(row):
        x, z = perp * (i - (len(row) - 1) / 2) * d
        inst.append(dict(glb=glb, x=float(x), z=float(z), yaw=yaw, painted=True, k=k, anim=anim, t=t, lod=0))
    zooms = [24.0 * VIEW_H / SCREEN_H, 40.0 * VIEW_H / SCREEN_H]
    spec = dict(instances=inst, target=[0.0, 1.0, 0.0], ground=[0.40, 0.42, 0.24],
                zooms=",".join(f"{z:.3f}" for z in zooms), close=dict(size=7.2, target=[0.0, 1.0, 0.0]))
    run_city(spec, "city")
    panels = []
    for z, game in zip(zooms, (24, 40)):
        p = os.path.join(OUT, f"city_zoom{z:.3f}.png")
        if not os.path.exists(p):
            continue
        g = Image.open(p).convert("RGB")
        w, h = g.size
        cw = int(w * (11.0 / (z * w / h)))
        ch = int(cw * 0.42)
        crop = g.crop((w // 2 - cw // 2, h // 2 - ch // 2 - int(0.02 * h), w // 2 + cw // 2, h // 2 + ch // 2 - int(0.02 * h)))
        scale = 4 if game == 24 else 6
        crop = crop.resize((crop.size[0] * scale, crop.size[1] * scale), Image.NEAREST)
        lab = (f"game camera ortho {game} on a 1170 px screen (pixels x{scale}): captain idle | orc idle, walk, "
               "drain peak, order_point, roar")
        panels.append(label(crop, lab))
        os.replace(p, os.path.join(OUT, f"city_ortho{game}.png"))
    p = os.path.join(OUT, "city_close.png")
    if os.path.exists(p):
        g = Image.open(p).convert("RGB")
        panels.append(label(g, "same camera direction, ortho 7.2 (detail)"))
    if panels:
        W = max(pp.size[0] for pp in panels)
        S = Image.new("RGB", (W, sum(pp.size[1] for pp in panels)), (30, 30, 30))
        y = 0
        for pp in panels:
            S.paste(pp, (0, y))
            y += pp.size[1]
        S.save(os.path.join(OUT, "..", "game_camera_vs_captain.png"))
        print("wrote game_camera_vs_captain.png")


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle([4, 4, 12 + 6 * len(text), 20], fill=(20, 20, 20))
    d.text((8, 6), text, fill=(255, 240, 200))
    return im


def godot_view(mode, out, anim="all", secs=6.0, extra=()):
    """forest_rescue/tools/godot_view.sh, step for step (private temp copy of tools/godot_viewer); the template
    checkout lacks the empty models/ folder the shell script copies into, so it is created here."""
    work = tempfile.mkdtemp(prefix="frorcview.")
    shutil.copytree(os.path.join(TOOLS, "godot_viewer"), work, dirs_exist_ok=True)
    os.makedirs(os.path.join(work, "models"), exist_ok=True)
    shutil.copy(os.path.join(HUM, f"{ID}.glb"), os.path.join(work, "models"))
    subprocess.run(["timeout", "600", "godot", "--headless", "--path", work, "--import"], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    xv = ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24"]
    user = [f"--model=res://models/{ID}.glb", f"--mode={mode}", f"--anim={anim}"] + list(extra)
    if mode == "shots":
        os.makedirs(out, exist_ok=True)
        subprocess.run(["timeout", "600"] + xv + ["godot", "--path", work, "--rendering-driver", "vulkan", "--",
                                                  f"--out={out}"] + user, capture_output=True, text=True)
    else:
        fr = int(secs * 30)
        r = subprocess.run(["timeout", "1500"] + xv + ["godot", "--path", work, "--rendering-driver", "vulkan",
                                                       "--write-movie", os.path.join(work, "frames.png"), "--fixed-fps",
                                                       "30", "--quit-after", str(fr), "--"] + user,
                           capture_output=True, text=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i",
                        os.path.join(work, "frames%08d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21",
                        out], check=False)
    shutil.rmtree(work, ignore_errors=True)


def shots():
    out = os.path.join(OUT, "viewer_shots")
    godot_view("shots", out, "lf_orc_idle", extra=("--lod=0",))
    files = sorted(f for f in os.listdir(out) if f.endswith(".png")) if os.path.isdir(out) else []
    if files:
        ims = [Image.open(os.path.join(out, f)).convert("RGB") for f in files]
        ims = [im.resize((im.size[0] // 2, im.size[1] // 2)) for im in ims]
        W, H = ims[0].size
        S = Image.new("RGB", (W * 3, H * 2))
        for i, im in enumerate(ims[:6]):
            S.paste(label(im, files[i][:-4]), ((i % 3) * W, (i // 3) * H))
        S.save(os.path.join(OUT, "..", "godot_viewer_shots.png"))
        print("wrote godot_viewer_shots.png")


def clip():
    os.makedirs(VID, exist_ok=True)
    mp4 = os.path.join(VID, "godot_all_clips.mp4")
    meta = json.load(open(os.path.join(HUM, f"{ID}.meta.json")))
    secs = sum(c["seconds"] for c in meta["clips"].values()) + 1.0
    godot_view("clip", mp4, "all", secs, extra=("--lod=0",))
    if os.path.exists(mp4):
        subprocess.run(["python3", os.path.join(TOOLS, "contact_sheet.py"), mp4, "--cols", "6", "--rows", "4"], check=False)
        cs = mp4.replace(".mp4", "_contact.png")
        if os.path.exists(cs):
            shutil.copy(cs, os.path.join(OUT, "..", "godot_all_clips_contact.png"))


TREE_GD = """extends SceneTree
func _init() -> void:
	var ps: PackedScene = load("res://models/%s.glb")
	var root := ps.instantiate()
	get_root().add_child(root)
	_walk(root, root)
	for ap: AnimationPlayer in root.find_children("*", "AnimationPlayer", true, false):
		for a in ap.get_animation_list():
			print("TREE_ANIM ", a, " ", ap.get_animation(a).length)
	for sk: Skeleton3D in root.find_children("*", "Skeleton3D", true, false):
		print("TREE_BONES ", sk.get_bone_count())
		var names := []
		for i in sk.get_bone_count():
			names.append(sk.get_bone_name(i) + "<" + (sk.get_bone_name(sk.get_bone_parent(i)) if sk.get_bone_parent(i) >= 0 else "-"))
		print("TREE_BONELIST ", ",".join(names))
	quit()
func _walk(n: Node, root: Node) -> void:
	var extra := ""
	if n is MeshInstance3D and n.mesh:
		var mats := []
		for s in n.mesh.get_surface_count():
			var m: Material = n.get_active_material(s)
			mats.append(String(m.resource_name) if m else "-")
		extra = " surfaces=" + str(mats)
	print("TREE ", root.get_path_to(n), " [", n.get_class(), "]", extra)
	for c in n.get_children():
		_walk(c, root)
"""


def tree():
    work = tempfile.mkdtemp(prefix="frorctree.")
    os.makedirs(os.path.join(work, "models"))
    shutil.copy(os.path.join(HUM, f"{ID}.glb"), os.path.join(work, "models"))
    open(os.path.join(work, "project.godot"), "w").write('config_version=5\n[application]\nconfig/name="orc_tree"\n')
    open(os.path.join(work, "tree.gd"), "w").write(TREE_GD % ID)
    subprocess.run(["timeout", "600", "godot", "--headless", "--path", work, "--import"], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    r = subprocess.run(["timeout", "600", "godot", "--headless", "--path", work, "--script", "res://tree.gd"],
                       capture_output=True, text=True)
    lines = [l for l in (r.stdout + r.stderr).splitlines() if l.startswith("TREE")]
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "godot_tree.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(l for l in lines if not l.startswith("TREE_BONELIST")))
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("tree", "all"):
        tree()
    if mode in ("city", "all"):
        city()
    if mode in ("shots", "all"):
        shots()
    if mode in ("clip", "all"):
        clip()
