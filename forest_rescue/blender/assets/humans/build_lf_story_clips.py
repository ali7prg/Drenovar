#!/usr/bin/env python3
"""lf_story_clips: story-cutscene clip library on the shared human skeleton (`human_shared`).

Escape from the forest cage, the chase and the family taking the escapee in: 30 new clips authored
procedurally on the v2 human rig (same bone names / hierarchy / rolls as every lf_civilian_* and
lf_squad_* GLB), skinned to the miller's LOD0 body only so a viewer can show them.

    python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/humans/build_lf_story_clips.py
    python3 forest_rescue/blender/assets/humans/build_lf_story_clips.py --qa [clip ...]   # Godot MP4 + sheets

Outputs: godot/project/assets/forest_rescue/humans/lf_story_clips.glb (+ .meta.json),
forest_rescue/qa/compare/lf_story_clips/metrics.json (numeric QA), qa/video/lf_story_clips/*.mp4.

Pose model (v2/hv2_clips): semantic parameters (pelvis offset/rotation, spine/neck/head, FK or IK
arms, IK legs with foot pitch/yaw/toe), keyframed with smootherstep blends.  Additions here:
  * world-space hand orientation for IK arms (finger direction + palm normal, weight `hw`), with
    the hand's roll split between the forearm (pronation/supination, `ftw`) and the wrist, and the
    humeral rotation split between the upper arm (`utw`) and the elbow, so wrists never snap;
  * an IK gait with running heel recovery, correct pelvis/thorax counter-rotation and bob phase;
  * a world-space footstep planner (heel/ball rolls, yaw) for one-shots that step or travel.
Loops: identical first/last frames.  Locomotion in place, planted feet slide back at exactly the
ground speed.  Travel one-shots (halt, squeeze, stumble) are in place too; their root path is in the
meta (rootPath_m, planted feet move with it).  Short acting steps (catch, support, collapse, hide)
keep the root fixed and the body ends displaced (endOffset_m); their hold loops keep that offset.
"""
import json
import math
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
V2 = os.path.join(HERE, "v2")
BLENDER_DIR = os.path.dirname(os.path.dirname(HERE))
FR_DIR = os.path.dirname(BLENDER_DIR)
REPO = os.path.dirname(FR_DIR)
for _p in (V2, HERE, BLENDER_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

AID = "lf_story_clips"
SRC_AID = "lf_civilian_miller"
SRC_BLEND = os.path.join(BLENDER_DIR, "sources", "humans", f"{SRC_AID}.blend")
OUT_GLB = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "humans", f"{AID}.glb")
OUT_META = OUT_GLB.replace(".glb", ".meta.json")
QA_VIDEO = os.path.join(FR_DIR, "qa", "video", AID)
QA_DIR = os.path.join(FR_DIR, "qa", "compare", AID)
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:7.1f}s]", *a, flush=True)


# --------------------------------------------------------------------------- Godot QA (no bpy)

VIEW = {   # per-clip viewer camera (yaw deg, pitch deg, dist mult, look-at height or None)
    "default": (35, 14, 1.0, None),
}
LOW = ("lf_story_collapse", "lf_story_collapse_hold", "lf_story_hide", "lf_story_hide_hold", "lf_story_peek",
       "lf_story_sit", "lf_story_sit_down", "lf_story_drink", "lf_story_show_wrist", "lf_story_talk_seated",
       "lf_story_stumble")


SIDE_VIEWS = ("lf_story_run", "lf_story_halt", "lf_story_backstep", "lf_story_sneak", "lf_story_collapse",
              "lf_story_hide", "lf_story_peek", "lf_story_stumble", "lf_story_sit", "lf_story_drink",
              "lf_story_carry_cup", "lf_story_walk_lantern", "lf_story_latch_reach", "lf_story_take_lantern")


def run_qa(clips):
    import shutil
    import tempfile
    meta = json.load(open(OUT_META))
    names = clips or list(meta["clips"])
    os.makedirs(QA_VIDEO, exist_ok=True)
    # unmodified copy of tools/godot_view.sh next to a copy of its viewer template that has the
    # models/ folder the script copies the GLB into (the shared template lacks it)
    tdir = tempfile.mkdtemp(prefix="lfstory_view_")
    shutil.copytree(os.path.join(FR_DIR, "tools", "godot_viewer"), os.path.join(tdir, "godot_viewer"))
    os.makedirs(os.path.join(tdir, "godot_viewer", "models"), exist_ok=True)
    shutil.copy(os.path.join(FR_DIR, "tools", "godot_view.sh"), os.path.join(tdir, "godot_view.sh"))
    tool = os.path.join(tdir, "godot_view.sh")
    # stage the GLB with its embedded atlas pre-extracted as <glb>_<image>.jpg (what Godot extracts on
    # import; a single headless --import pass otherwise leaves the freshly extracted texture unloaded)
    import struct
    stage = os.path.join(tdir, "stage")
    os.makedirs(stage)
    glb = os.path.join(stage, os.path.basename(OUT_GLB))
    shutil.copy(OUT_GLB, glb)
    raw = open(OUT_GLB, "rb").read()
    jl = struct.unpack("<I", raw[12:16])[0]
    gj = json.loads(raw[20:20 + jl])
    b0 = 20 + jl + 8
    for im in gj.get("images", []):
        bv = gj["bufferViews"][im["bufferView"]]
        o = b0 + bv.get("byteOffset", 0)
        ext = ".jpg" if im.get("mimeType") == "image/jpeg" else ".png"
        open(os.path.join(stage, f"{AID}_{im['name']}{ext}"), "wb").write(raw[o:o + bv["byteLength"]])
    sheet = os.path.join(FR_DIR, "tools", "contact_sheet.py")
    for nm in names:
        c = meta["clips"][nm]
        sec = c["seconds"] * (2.0 if c["loop"] else 1.0) + (0.0 if c["loop"] else 0.4)
        sec = max(sec, 1.6)
        views = (("", 35), ("_side", 90)) if nm in SIDE_VIEWS else (("", 35),)
        for tag, yaw in views:
            out = os.path.join(QA_VIDEO, f"{nm}{tag}.mp4")
            extra = [f"--yaw={yaw}", "--pitch=12", "--dist=1.05", "--lod=0"]
            if nm in LOW:
                extra.append("--cy=0.62")
            t = time.time()
            subprocess.run(["bash", tool, glb, "clip", out, nm, f"{sec:.2f}"] + extra, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run([sys.executable, sheet, out, "--cols", "6", "--rows", "2"], check=False,
                           stdout=subprocess.DEVNULL)
            print(f"{nm}{tag}: {time.time() - t:.0f}s", flush=True)


CHECKS_GD = """extends Node3D
## Story-camera stills: actors (GLB scenes posed at clip times), the game's city camera
## (orthographic, position = target + (75, 83, 75), look_at target), saved at the window size.
var cfg := {}
var out := ""
var cam: Camera3D
var cache := {}

func _ready() -> void:
	var args := {}
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--") and a.contains("="):
			var kv := a.substr(2).split("=", true, 1)
			args[kv[0]] = kv[1]
	cfg = JSON.parse_string(FileAccess.get_file_as_string(args["config"]))
	out = args["out"]
	DirAccess.make_dir_recursive_absolute(out)
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.58, 0.62, 0.52)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.62, 0.64, 0.68)
	e.ambient_light_energy = 0.6
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.environment = e
	add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-52, 30, 0)
	sun.light_energy = 1.3
	sun.shadow_enabled = true
	add_child(sun)
	var g := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(80, 80)
	g.mesh = pm
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.40, 0.43, 0.31)
	gm.roughness = 1.0
	g.material_override = gm
	add_child(g)
	cam = Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.near = 1.0
	cam.far = 400.0
	add_child(cam)
	_run.call_deferred()

func _inst(key: String, path: String) -> Node3D:
	if cache.has(key):
		return cache[key]
	var n: Node3D
	if path.begins_with("box:"):
		var mi := MeshInstance3D.new()
		var bm := BoxMesh.new()
		mi.mesh = bm
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color(0.45, 0.32, 0.2)
		mi.material_override = mat
		n = mi
	else:
		n = (load(path) as PackedScene).instantiate()
	add_child(n)
	cache[key] = n
	return n

func _run() -> void:
	for shot in cfg["shots"]:
		for k in cache:
			(cache[k] as Node3D).visible = false
		for a in shot["actors"]:
			var n := _inst(a["key"], a["scene"])
			n.visible = true
			n.position = Vector3(a["pos"][0], a["pos"][1], a["pos"][2])
			n.rotation = Vector3(0, deg_to_rad(float(a.get("yaw", 0.0))), 0)
			if a.has("size"):
				((n as MeshInstance3D).mesh as BoxMesh).size = Vector3(a["size"][0], a["size"][1], a["size"][2])
			else:
				n.scale = Vector3.ONE * float(a.get("scale", 1.0))
			if a.has("anim"):
				var ap: AnimationPlayer = n.find_children("*", "AnimationPlayer", true, false)[0]
				ap.play(a["anim"])
				ap.seek(float(a["time"]), true)
				ap.pause()
		var tg := Vector3(shot["target"][0], shot["target"][1], shot["target"][2])
		cam.size = float(shot["size"])
		cam.position = tg + Vector3(75, 83, 75)
		cam.look_at(tg, Vector3.UP)
		for _f in 5:
			await get_tree().process_frame
		var img := get_viewport().get_texture().get_image()
		img.save_png(out.path_join(String(shot["name"]) + ".png"))
		print("SHOT ", shot["name"], " ", img.get_size())
	print("CHECKS_DONE")
	get_tree().quit()
"""

CAGE_GLB_RT = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "props", "lf_cage_wood.glb")


def check_shots(meta):
    """Story-camera stills for the reworked clips (positions/timings as in src/story/story_intro.gd)."""
    lib, cage = "res://models/lf_story_clips.glb", "res://models/lf_cage_wood.glb"
    shots = []
    c = meta["clips"]

    def cage_actor(anim, t):
        return {"key": "cage", "scene": cage, "pos": [0, 0, 0], "anim": anim, "time": t}

    def latch_cage(t):              # unlock under 0.9..1.6 (latch_clear at 'lift'), door opens from 'push'
        if t > 2.2:
            return cage_actor("lf_cage_gate_open", 0.7 * (t - 2.2))
        if t >= 0.9:
            return cage_actor("lf_cage_unlock", min(t - 0.9, 1.0))
        return cage_actor("lf_cage_gate_open", 0.0)
    root = [0.95, 0.12, 0.95]
    for size in (4.6, 9.5):
        for t in ((0.3, 0.55, 0.8, 1.0, 1.6, 2.0, 2.4, 2.7) if size == 4.6 else (0.55, 1.0, 1.6, 2.4)):
            shots.append({"name": f"latch_o{size:g}_t{t:.2f}", "size": size, "target": [0.95, 1.15, 1.45],
                          "actors": [latch_cage(t), {"key": "danko", "scene": lib, "pos": root, "yaw": 0,
                                                     "anim": "lf_story_latch_reach", "time": t}]})
    path = c["lf_story_squeeze"]["rootPathXYZ_m"]
    for t in (0.0, 0.3, 0.6, 0.9, 1.2, 1.5):
        o = path[min(int(round(t * 10)), len(path) - 1)]
        shots.append({"name": f"squeeze_o9.5_t{t:.2f}", "size": 9.5, "target": [0.8, 0.9, 2.0],
                      "actors": [cage_actor("lf_cage_gate_open", 0.55),
                                 {"key": "danko", "scene": lib, "pos": [root[0] + o[0], root[1] + o[1], root[2] + o[2]],
                                  "yaw": 0, "anim": "lf_story_squeeze", "time": t}]})
    # support: Tim at inside.tim (0.45, 0.45) facing Danko; Danko 0.6 m away on that line, facing Tim
    import math as _m
    for view, tyaw in (("", 45), ("_profile", 135)):
      tim = [0.45, 0.12, 0.45]
      dirv = [_m.sin(_m.radians(tyaw)), 0.0, _m.cos(_m.radians(tyaw))]
      dan = [tim[0] + 0.6 * dirv[0], 0.12, tim[2] + 0.6 * dirv[2]]
      for nm, anim_t, anim_d, ts, td in (("support", "lf_story_support", "lf_story_collapse", (0.0, 0.3, 0.5, 0.8, 1.15),
                                        None),
                                       ("support_hold", "lf_story_support_hold", "lf_story_collapse_hold",
                                        (0.0, 1.6), None)):
        for t in ts:
            tdk = min(t + 0.25, 1.4) if nm == "support" else t
            shots.append({"name": f"{nm}{view}_o10.5_t{t:.2f}", "size": 10.5,
                          "target": [(tim[0] + dan[0]) / 2, 0.8, (tim[2] + dan[2]) / 2],
                          "actors": [{"key": "tim", "scene": lib, "pos": tim, "yaw": tyaw, "anim": anim_t, "time": t},
                                     {"key": "danko", "scene": lib, "pos": dan, "yaw": tyaw + 180, "anim": anim_d,
                                      "time": tdk}]})
            shots.append(dict(shots[-1], name=f"{nm}{view}_close_o4.6_t{t:.2f}", size=4.6,
                              target=[(tim[0] + dan[0]) / 2, 0.8, (tim[2] + dan[2]) / 2]))
    # show wrist: Danko seated facing +Z, bench behind, the boy 1.05 m in front, 0.25 m to Danko's right
    for t in (0.0, 0.75, 1.1, 1.6):
        shots.append({"name": f"wrist_o7.2_t{t:.2f}", "size": 7.2, "target": [0.0, 0.0, 0.55],
                      "actors": [{"key": "bench", "scene": "box:", "pos": [0.0, 0.225, -0.38], "size": [1.0, 0.45, 0.36]},
                                 {"key": "danko", "scene": lib, "pos": [0, 0, 0], "yaw": 0, "anim": "lf_story_show_wrist",
                                  "time": t},
                                 {"key": "boy", "scene": lib, "pos": [-0.25, 0, 1.05], "yaw": 180, "scale": 0.8,
                                  "anim": "lf_story_point_low", "time": 0.6}]})
        shots.append(dict(shots[-1], name=f"wrist_close_o3_t{t:.2f}", size=3.0, target=[0.0, 0.9, 0.3]))
    # run: screen-right and screen-left headings at the chase zooms
    for size in (15.0, 26.0):
        for yaw, lab in ((135, "right"), (-45, "left")):
            for t in (0.0, 0.1667, 0.3333, 0.5):
                shots.append({"name": f"run_{lab}_o{size:g}_t{t:.2f}", "size": size, "target": [0.0, 0.9, 0.0],
                              "actors": [{"key": "runner", "scene": lib, "pos": [0, 0, 0], "yaw": yaw,
                                          "anim": "lf_story_run", "time": t}]})
    return shots


def run_godot_checks():
    import shutil
    import tempfile
    from PIL import Image, ImageDraw
    meta = json.load(open(OUT_META))
    work = tempfile.mkdtemp(prefix="lfstory_checks_")
    shutil.copytree(os.path.join(FR_DIR, "tools", "godot_viewer"), work, dirs_exist_ok=True)
    models = os.path.join(work, "models")
    os.makedirs(models, exist_ok=True)
    shutil.copy(OUT_GLB, models)
    cage_dir = os.path.dirname(CAGE_GLB_RT)
    for f in os.listdir(cage_dir):
        if f.startswith("lf_cage_wood") and f.endswith((".glb", ".jpg", ".png")):
            shutil.copy(os.path.join(cage_dir, f), models)
    open(os.path.join(work, "checks.gd"), "w").write(CHECKS_GD)
    open(os.path.join(work, "checks.tscn"), "w").write(
        '[gd_scene load_steps=2 format=3]\n\n[ext_resource type="Script" path="res://checks.gd" id="1"]\n\n'
        '[node name="Checks" type="Node3D"]\nscript = ExtResource("1")\n')
    cfg = os.path.join(work, "shots.json")
    shots = check_shots(meta)
    json.dump({"shots": shots}, open(cfg, "w"))
    out = os.path.join(QA_DIR, "godot_checks")
    os.makedirs(out, exist_ok=True)
    subprocess.run(["godot", "--headless", "--path", work, "--import"], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=900)
    r = subprocess.run(["xvfb-run", "-a", "-s", "-screen 0 2600x1300x24", "godot", "--path", work,
                        "--rendering-driver", "vulkan", "--resolution", "2532x1170", "res://checks.tscn", "--",
                        f"--config={cfg}", f"--out={out}"], capture_output=True, text=True, timeout=1800)
    print("\n".join(l for l in r.stdout.splitlines() if l.startswith(("SHOT", "CHECKS")))[-2000:])
    groups = {}
    for sh in shots:
        groups.setdefault(sh["name"].rsplit("_t", 1)[0], []).append(sh["name"])
    for g, names in groups.items():
        ims = [Image.open(os.path.join(out, n + ".png")).convert("RGB") for n in names
               if os.path.exists(os.path.join(out, n + ".png"))]
        if not ims:
            continue
        w, h = 844, 390
        cols = min(4, len(ims))
        rows = (len(ims) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * w, rows * (h + 20)), (20, 20, 20))
        dr = ImageDraw.Draw(sheet)
        for i, (n, im) in enumerate(zip(names, ims)):
            x, y = (i % cols) * w, (i // cols) * (h + 20)
            sheet.paste(im.resize((w, h), Image.LANCZOS), (x, y + 20))
            dr.text((x + 6, y + 4), n + "  (2532x1170, story camera)", fill=(240, 220, 160))
        sheet.save(os.path.join(out, f"sheet_{g}.png"))
    print("CHECK SHEETS", out)


if "--godot-checks" in ARGS:
    run_godot_checks()
    sys.exit(0)

if "--qa" in ARGS:
    run_qa([a for a in ARGS if not a.startswith("--")])
    sys.exit(0)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Quaternion  # noqa: E402
from scipy.ndimage import gaussian_filter1d, maximum_filter1d  # noqa: E402

from frlib import core  # noqa: E402
import hv2_anim as A  # noqa: E402
import hv2_clips as HC  # noqa: E402
import hv2_finish as FIN  # noqa: E402
from hv2_anim import DEG, Z, rot, smooth, smoother  # noqa: E402

FPS = 30.0
SIDES = (("l", "Left", 1.0), ("r", "Right", -1.0))
SEAT_H = 0.45          # bench / stool seat height (m)
SEAT_Y = 0.36          # hips this far behind the root when seated (Blender +Y = backward)
cx = None              # hv2_clips.Ctx of the display body (set in main)
SKIN = None            # Skin (numpy LBS) of the display body (set in main)
REL = {}               # forearm->hand rest relation per side


def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def frames(sec):
    return np.arange(int(round(sec * FPS)) + 1) / FPS


def env(t, keys):
    """Piecewise smootherstep through (time, value) keys."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys[:-1], keys[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * smoother((t - t0) / max(t1 - t0, 1e-9))
    return keys[-1][1]


def per(t, sec, cyc=1.0, ph=0.0):
    return math.sin(2 * math.pi * (cyc * t / sec + ph))


# --------------------------------------------------------------------------- body / context

class MeshTable:
    """Polar hull radius r(z, phi) of the display body (arm/hand vertices excluded), the same lookup
    interface as hv2_drape.BodyTable (used for the neutral arm adduction and chest/belly depth)."""

    def __init__(self, obj, cy=0.012, z0=0.05, z1=1.6, dz=0.01, nphi=144):
        me = obj.data
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        names = [g.name for g in obj.vertex_groups]
        dom = np.full(len(co), -1)
        best = np.zeros(len(co))
        for v in me.vertices:
            for g in v.groups:
                if g.weight > best[v.index]:
                    best[v.index] = g.weight
                    dom[v.index] = g.group
        armb = ("UpperArm", "LowerArm", "Hand", "Thumb", "Index", "Middle", "Ring", "Pinky", "Prop")
        keep = np.array([d >= 0 and not any(k in names[d] for k in armb) for d in dom])
        P = co[keep]
        self.cx, self.cy = 0.0, cy
        self.zs = np.arange(z0, z1 + 1e-9, dz)
        self.phis = np.linspace(-math.pi, math.pi, nphi, endpoint=False)
        self.h = np.zeros((len(self.zs), nphi))
        phi = np.arctan2(P[:, 0] - self.cx, -(P[:, 1] - cy))
        r = np.hypot(P[:, 0] - self.cx, P[:, 1] - cy)
        bins = ((phi + math.pi) / (2 * math.pi) * nphi).astype(int) % nphi
        for i, z in enumerate(self.zs):
            sel = np.abs(P[:, 2] - z) < dz * 1.2
            rr = np.zeros(nphi)
            np.maximum.at(rr, bins[sel], r[sel])
            if (rr > 0).sum() > 3:
                idx = np.where(rr > 0)[0]
                rr = np.interp(np.arange(nphi), idx, rr[idx], period=nphi)
            rr = maximum_filter1d(rr, 5, mode="wrap")
            self.h[i] = rr

    def hull(self, z, phi):
        z = np.asarray(z, float)
        phi = np.asarray(phi, float)
        fi = np.clip((z - self.zs[0]) / (self.zs[1] - self.zs[0]), 0, len(self.zs) - 1.001)
        i0 = np.floor(fi).astype(int)
        tz = fi - i0
        n = len(self.phis)
        fj = ((phi + math.pi) / (2 * math.pi) * n) % n
        j0 = np.floor(fj).astype(int) % n
        j1 = (j0 + 1) % n
        tp = fj - np.floor(fj)
        H = self.h
        a = H[i0, j0] * (1 - tp) + H[i0, j1] * tp
        b = H[i0 + 1, j0] * (1 - tp) + H[i0 + 1, j1] * tp
        return a * (1 - tz) + b * tz


def load_body():
    bpy.ops.wm.open_mainfile(filepath=SRC_BLEND)
    arm = bpy.data.objects[f"{SRC_AID}_rig"]
    lod0 = bpy.data.objects[f"{SRC_AID}_LOD0"]
    for o in list(bpy.data.objects):
        if o not in (arm, lod0):
            bpy.data.objects.remove(o, do_unlink=True)
    if lod0.data.shape_keys:          # sit_drape is the miller's cage-floor drape: not part of these clips
        lod0.shape_key_clear()
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    if arm.animation_data:
        arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
        for c in list(pb.constraints):      # muted IK helpers of the editable master: not needed here
            pb.constraints.remove(c)
    arm.name = f"{AID}_rig"
    arm.data.name = f"{AID}_rig"
    lod0.name = f"{AID}_LOD0"
    lod0.data.name = f"{AID}_LOD0"
    # preview body only: halve the atlas with PIL and embed that file as-is (an atlas re-encoded by
    # Blender's writer carries an APP1 segment Godot's JPEG decoder rejects -> untextured import)
    import io
    import tempfile
    from PIL import Image
    tdir = tempfile.mkdtemp(prefix="lfstory_tex_")
    for img in list(bpy.data.images):
        if img.size[0] > 1024 and img.packed_file is not None:
            im = Image.open(io.BytesIO(bytes(img.packed_file.data))).convert("RGB")
            path = os.path.join(tdir, f"{img.name.rsplit('.', 1)[0]}.jpg")
            im.resize((1024, 1024), Image.LANCZOS).save(path, quality=88, optimize=True)
            new = bpy.data.images.load(path)
            new.name = img.name.rsplit(".", 1)[0]
            for m in bpy.data.materials:
                if m.node_tree:
                    for nd in m.node_tree.nodes:
                        if nd.type == "TEX_IMAGE" and nd.image == img:
                            nd.image = new
            bpy.data.images.remove(img)
            new.pack()
    bpy.context.scene.render.fps = 30
    return arm, lod0


def make_ctx(arm, lod0):
    sk = A.Skel(arm)
    J = {}
    for S, sx in (("Left", 1.0), ("Right", -1.0)):
        an = sk.head(f"{S}Foot")
        yaw = math.radians(9.0) * sx                       # lf_civilian_miller toe_out_deg
        J[f"_{S}fwd"] = np.array([math.sin(yaw), -math.cos(yaw), 0.0])
        h = an + np.array([0.0, 0.062 * 0.275 / 0.26, 0.0])  # foot_len 0.275 (hv2_body.joints)
        J[f"{S}Heel"] = np.array([h[0], h[1], 0.0])
    T = MeshTable(lod0)
    c = HC.Ctx(sk, {}, J, T, "civilian")
    for S in ("Left", "Right"):
        REL[S] = sk.R[f"{S}LowerArm"][:3, :3].T @ sk.R[f"{S}Hand"][:3, :3]
    return c


def base():
    p = HC.base(cx)
    for s in "lr":
        p.update({f"{s}_hw": 0.0, f"{s}_hd": None, f"{s}_hn": None, f"{s}_idx": None, f"{s}_thb": None,
                  f"{s}_ftw": 0.5, f"{s}_utw": 1.0})
    return p


# --------------------------------------------------------------------------- params -> pose (extended)

def _signed_angle(a, b, axis):
    a = a - (a @ axis) * axis
    b = b - (b @ axis) * axis
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-6 or nb < 1e-6:
        return 0.0
    a, b = a / na, b / nb
    return math.atan2(float(np.cross(a, b) @ axis), float(a @ b))


def _bend(sh, el, wr, pole):
    ax = wr - sh
    L = np.linalg.norm(ax)
    pole = np.asarray(pole, float)
    if L < 1e-6:
        return unit(pole)
    ax = ax / L
    w = (el - sh) - ((el - sh) @ ax) * ax
    if np.linalg.norm(w) < 1e-4:
        w = pole - (pole @ ax) * ax
    return unit(w)


def _quat(m):
    return Matrix(np.asarray(m).tolist()).to_quaternion()


def slerp_m(Ra, Rb, w):
    qa, qb = _quat(Ra), _quat(Rb)
    if qa.dot(qb) < 0:
        qb = -qb
    return np.array(qa.slerp(qb, float(w)).to_matrix())


def rot_between(a, b, fallback):
    a, b = unit(a), unit(b)
    ax = np.cross(a, b)
    s, c = np.linalg.norm(ax), float(a @ b)
    if s < 1e-8:
        return np.eye(3) if c > 0 else rot(unit(fallback), math.pi)
    return rot(ax / s, math.atan2(s, c))


HINGE = {}     # side -> (bind-pose elbow hinge axis in upper-arm local coords, forearm-in-upper-arm rel)


def hinge_rest(S):
    """Anatomical elbow flexion axis (the FK flexion axis of hv2_clips: forearm x forward) in upper-arm
    local coordinates, and the bind-pose forearm relative to the upper arm."""
    if S not in HINGE:
        Ru = cx.sk.R[f"{S}UpperArm"][:3, :3]
        Rf = cx.sk.R[f"{S}LowerArm"][:3, :3]
        x = unit(np.cross(Rf[:, 1], np.array([0.0, -1.0, 0.0])))
        HINGE[S] = (Ru.T @ x, Ru.T @ Rf)
    return HINGE[S]


def _upper_fn(P, S, utw):
    """Upper arm frame for IK arms: Y along the arm, humeral rotation chosen so the bind-pose elbow
    hinge axis maps onto the normal of the posed shoulder-elbow-wrist plane (elbow pole side), i.e.
    the elbow bends as a clean hinge relative to the skin bind (no elbow candy-wrapping)."""
    def fn(M, Mn):
        Aa = P.arm[S]
        sh = Mn[:3, 3]
        u = unit(Aa["_el"] - sh)
        w = _bend(sh, Aa["_el"], Aa["_wr"], Aa["elbow"])
        xw = unit(np.cross(u, -w))
        xl, _ = hinge_rest(S)
        a = unit(xl - (xl @ np.array([0, 1.0, 0])) * np.array([0, 1.0, 0]))
        loc = np.stack([a, np.array([0, 1.0, 0]), np.cross(a, np.array([0, 1.0, 0]))], 1)
        xw = unit(xw - (xw @ u) * u)
        wor = np.stack([xw, u, np.cross(xw, u)], 1)
        Mn = Mn.copy()
        Mn[:3, :3] = wor @ loc.T
        return Mn
    return fn


def _lower_fn(P, S, ik, Fd, hw, ftw, hinge2=False):
    """Forearm: for IK arms the bind-relative forearm swung onto its new direction (pure hinge);
    then `ftw` of the hand's roll about the forearm (pronation/supination), the rest stays at the wrist."""
    def fn(M, Mn):
        f = unit(Mn[:3, 1])
        Mn = Mn.copy()
        if ik:
            _, rel = hinge_rest(S)
            Rc = M[f"{S}UpperArm"][:3, :3] @ rel
            if hinge2:
                # flex about the elbow hinge axis first (keeps the bind carrying angle out of the forearm roll),
                # then the small residual swing onto the target direction
                xl, _ = hinge_rest(S)
                xw = unit(M[f"{S}UpperArm"][:3, :3] @ xl)
                Rc = rot(xw, _signed_angle(Rc[:, 1], f, xw)) @ Rc
            Rf = rot_between(Rc[:, 1], f, Rc[:, 0]) @ Rc
        else:
            Rf = A.frame_from(f, Mn[:3, 2])
        if Fd is not None:
            q = A.matq(Fd @ (Rf @ REL[S]).T)          # world delta: hand following the forearm -> wanted
            beta = 2.0 * math.atan2(float(q[1:] @ f), float(q[0]))
            beta = (beta + math.pi) % (2 * math.pi) - math.pi
            Rf = rot(f, ftw * hw * beta) @ Rf
        Mn[:3, :3] = Rf
        return Mn
    return fn


def _hand_fn(Fd, hw):
    def fn(M, Mn):
        Mn = Mn.copy()
        Mn[:3, :3] = Fd if hw >= 0.999 else slerp_m(Mn[:3, :3], Fd, hw)
        return Mn
    return fn


def _leg_fn(P, S, part):
    """Thigh / shin frames from the hip-knee-ankle plane (Z = side the knee points to): stays defined
    when the knee pole lines up with the shin (running heel recovery, kneeling)."""
    def fn(M, Mn):
        L = P.leg[S]
        hip = M[f"{S}UpperLeg"][:3, 3] if part == "shin" else Mn[:3, 3]
        w = _bend(hip, L["_knee"], L["_ank"], L["knee"])
        u = unit(L["_knee"] - hip) if part == "thigh" else unit(L["_ank"] - L["_knee"])
        Mn = Mn.copy()
        Mn[:3, :3] = A.frame_from(u, w)
        return Mn
    return fn


def make_pose2(p):
    P = HC.make_pose(cx, p)
    sk = cx.sk
    # FK arms are re-expressed as IK (wrist + elbow pole of their FK solution) so that every arm
    # follows the same humeral-rotation / elbow-hinge rule: FK <-> IK blends cannot pop
    fk_sides = [S for s, S, sx in SIDES if p.get(f"{s}_ik") is None]
    if fk_sides:
        M0 = A.solve(sk, HC.make_pose(cx, p))[1]
        for S in fk_sides:
            sh, el, wr = (M0[f"{S}{b}"][:3, 3] for b in ("UpperArm", "LowerArm", "Hand"))
            pole = el - 0.5 * (sh + wr)
            pole = unit(pole) if np.linalg.norm(pole) > 1e-4 else np.array([0.0, 1.0, 0.0])
            P.arm[S] = dict(wrist=wr, elbow=pole, hand_rot=None, hand_local=True)
    for S in ("Left", "Right"):
        if S in P.leg:
            P.world[f"{S}UpperLeg"] = _leg_fn(P, S, "thigh")
            P.world[f"{S}LowerLeg"] = _leg_fn(P, S, "shin")
    for s, S, sx in SIDES:
        ci = p.get(f"{s}_idx")
        if ci is not None:
            for f, amt in (("Index1", 30), ("Index2", 45)):
                P.rot[S + f] = rot(sk.R[S + f][:3, 0], -float(ci) * amt * DEG)
        ct = p.get(f"{s}_thb")
        if ct is not None:
            for f, amt in (("Thumb1", 22), ("Thumb2", 40)):
                P.rot[S + f] = rot(sk.R[S + f][:3, 0], -float(ct) * amt * DEG)
        hw = float(p.get(f"{s}_hw") or 0.0)
        Fd = None
        if hw > 1e-4 and p.get(f"{s}_hd") is not None:
            Fd = A.frame_from(unit(p[f"{s}_hd"]), -unit(p[f"{s}_hn"]))
        ik = True
        if ik:
            P.world[f"{S}UpperArm"] = _upper_fn(P, S, float(p.get(f"{s}_utw", 1.0)))
        P.world[f"{S}LowerArm"] = _lower_fn(P, S, ik, Fd, hw, float(p.get(f"{s}_ftw", 0.5)),
                                            bool(p.get(f"{s}_hinge", False)))
        if Fd is not None:
            P.world[f"{S}Hand"] = _hand_fn(Fd, hw)
    return P


def solved(p):
    return A.solve(cx.sk, make_pose2(p))[1]


def pt_on(M, bone, rest_pt):
    """World position of a rest-space point rigidly attached to `bone` in the posed matrices M."""
    R = cx.sk.R[bone]
    return (M[bone] @ np.linalg.inv(R) @ np.append(np.asarray(rest_pt, float), 1.0))[:3]


_FK = {}       # id(params) -> (params, ik dict): the stored reference keeps the id unique


def fk_wrist(p, s):
    """IK dict reproducing the FK arm of params p (wrist + elbow pole from the solved FK pose)."""
    hit = _FK.get((id(p), s))
    if hit is not None and hit[0] is p:
        return hit[1]
    S = "Left" if s == "l" else "Right"
    q = dict(p)
    q[f"{s}_ik"] = None
    M = solved(q)
    sh, el, wr = (M[f"{S}{b}"][:3, 3] for b in ("UpperArm", "LowerArm", "Hand"))
    pole = el - 0.5 * (sh + wr)
    out = dict(wrist=wr, elbow=unit(pole) if np.linalg.norm(pole) > 1e-4 else np.array([0, 0.3, 0.0]))
    _FK[(id(p), s)] = (p, out)
    return out


def lerp2(a, b, t):
    out = {}
    for k in a:
        va, vb = a[k], b.get(k, a[k])
        if k.endswith("_ik") and (va is not None or vb is not None):
            s = k[0]
            va = fk_wrist(a, s) if va is None else va
            vb = fk_wrist(b, s) if vb is None else vb
            e = (1 - t) * np.asarray(va["elbow"], float) + t * np.asarray(vb["elbow"], float)
            out[k] = dict(wrist=(1 - t) * np.asarray(va["wrist"], float) + t * np.asarray(vb["wrist"], float),
                          elbow=unit(e))
        elif va is None or vb is None or isinstance(va, (dict, tuple, list, str)):
            out[k] = vb if t >= 0.5 else va
        else:
            out[k] = va + (vb - va) * t
    for s in "lr":
        wa, wb = float(a.get(f"{s}_hw") or 0.0), float(b.get(f"{s}_hw") or 0.0)
        ha = (a.get(f"{s}_hd"), a.get(f"{s}_hn")) if wa > 0 and a.get(f"{s}_hd") is not None else None
        hb = (b.get(f"{s}_hd"), b.get(f"{s}_hn")) if wb > 0 and b.get(f"{s}_hd") is not None else None
        if ha is None and hb is None:
            out[f"{s}_hd"], out[f"{s}_hn"] = None, None
        elif ha is None or hb is None:
            out[f"{s}_hd"], out[f"{s}_hn"] = (hb or ha)
        else:
            out[f"{s}_hd"] = ha[0] + (hb[0] - ha[0]) * t
            out[f"{s}_hn"] = ha[1] + (hb[1] - ha[1]) * t
        for k, f in (("idx", 1.0), ("thb", 0.5)):
            xa = a.get(f"{s}_{k}")
            xb = b.get(f"{s}_{k}")
            if xa is None and xb is None:
                out[f"{s}_{k}"] = None
                continue
            xa = a[f"{s}_curl"] * f if xa is None else xa
            xb = b[f"{s}_curl"] * f if xb is None else xb
            out[f"{s}_{k}"] = xa + (xb - xa) * t
    return out


def keyed2(keys, t):
    if t <= keys[0][0]:
        return dict(keys[0][1])
    for (t0, p0), (t1, p1) in zip(keys[:-1], keys[1:]):
        if t <= t1:
            return lerp2(p0, p1, float(smoother((t - t0) / max(t1 - t0, 1e-9))))
    return dict(keys[-1][1])


def chain(b, deltas):
    return HC.expand(b, deltas)


def put_arm(p, s, wrist, elbow, d=None, n=None, hw=1.0, curl=None, idx=None, thb=None, ftw=None, utw=None):
    p[f"{s}_ik"] = dict(wrist=np.asarray(wrist, float), elbow=unit(elbow))
    if d is not None:
        p[f"{s}_hd"] = unit(d)
        p[f"{s}_hn"] = unit(n)
        p[f"{s}_hw"] = hw
    else:
        p[f"{s}_hw"] = 0.0
    if curl is not None:
        p[f"{s}_curl"] = curl
    p[f"{s}_idx"] = idx
    p[f"{s}_thb"] = thb
    if ftw is not None:
        p[f"{s}_ftw"] = ftw
    if utw is not None:
        p[f"{s}_utw"] = utw
    return p


def fk_arm(p, s, fwd=None, add=None, elb=None, wr=None, tw=None, curl=None):
    S = "Left" if s == "l" else "Right"
    p[f"{s}_ik"] = None
    p[f"{s}_hw"] = 0.0
    p[f"{s}_idx"] = None
    p[f"{s}_thb"] = None
    for k, v in (("fwd", fwd), ("elb", elb), ("wr", wr), ("tw", tw), ("curl", curl)):
        if v is not None:
            p[f"{s}_{k}"] = v
    if add is not None:
        p[f"{s}_add"] = cx.add0[S] + add
    return p


def mirror(v):
    return np.array([-v[0], v[1], v[2]], float)


# --------------------------------------------------------------------------- gait

def gait2(t, T, v, beta=0.62, lift=0.09, step_w=0.095, heel=14.0, toeoff=30.0, y_c=0.0, kick=0.0, kick_pitch=0.0,
          drive=0.0):
    """In-place IK foot params (stance as hv2_clips.gait: heel strike -> flat -> ball roll, zero slip);
    swing with an optional running heel recovery (`kick`).  Left heel strike at phase 0."""
    out, contacts = {}, {}
    S_len = v * T
    travel = v * t
    for s, S, sx, ph0 in (("l", "Left", 1.0, 0.0), ("r", "Right", -1.0, 0.5)):
        ph = ((t / T) - ph0) % 1.0
        heel_r, ball_r, ank_r = cx.heel[S], cx.ball[S], cx.ank[S]
        foot_l = np.linalg.norm((ball_r - heel_r)[:2])
        x_off = sx * step_w - ank_r[0]
        fwd, lat = cx.fwd[S], cx.lat[S]
        ball0 = np.array([ball_r[0], ball_r[1], 0.0])
        if ph < beta:
            u = ph / beta
            y_heel = y_c - beta * S_len / 2 + v * ph * T
            if u < 0.12:
                pitch = -heel * (1 - smooth(u / 0.12))
            elif u < 0.68:
                pitch = 0.0
            else:
                pitch = toeoff * smooth((u - 0.68) / 0.32)
            if pitch <= 0:
                piv_rest, piv, kind = heel_r, np.array([heel_r[0] + x_off, y_heel, 0.0]), "heel"
            else:
                piv_rest = ball0
                piv, kind = np.array([ball_r[0] + x_off, y_heel - foot_l * (-fwd[1]), 0.0]), "ball"
            ank = piv + rot(lat, pitch * DEG) @ (ank_r - piv_rest)
            contacts[S] = (True, piv + np.array([0, -travel, 0]), kind)
            toe = -pitch if pitch > 0 else 0.0
        else:
            u = (ph - beta) / (1 - beta)
            y0 = y_c + beta * S_len / 2
            piv_b = np.array([ball_r[0] + x_off, y0 - foot_l * (-fwd[1]), 0.0])
            a0 = piv_b + rot(lat, toeoff * DEG) @ (ank_r - ball0)
            piv_h = np.array([heel_r[0] + x_off, y_c - beta * S_len / 2, 0.0])
            a1 = piv_h + rot(lat, -heel * DEG) @ (ank_r - heel_r)
            k = smoother(u)
            ank = a0 * (1 - k) + a1 * k
            ank[2] += lift * math.sin(math.pi * min(1.0, u * 1.08)) ** 1.2
            if kick:
                ank[2] += kick * math.sin(math.pi * min(1.0, u / 0.72)) ** 2
                ank[1] += 0.35 * kick * math.sin(math.pi * min(1.0, u / 0.5))
            if drive:            # knee drive: the swing foot reaches out ahead, then claws back to the strike
                ank[1] -= drive * math.sin(math.pi * float(np.clip((u - 0.45) / 0.55, 0.0, 1.0))) ** 1.5
            pitch = toeoff * (1 - smooth(u / 0.55)) - heel * smooth((u - 0.55) / 0.45)
            if kick_pitch:
                pitch += kick_pitch * math.sin(math.pi * min(1.0, u / 0.7))
            toe = -toeoff * (1 - smooth(u / 0.35)) + 8.0 * math.sin(math.pi * u)
            contacts[S] = (False, None, None)
        out[f"{s}_fx"] = ank[0] - ank_r[0]
        out[f"{s}_fy"] = ank[1] - ank_r[1]
        out[f"{s}_fz"] = ank[2] - ank_r[2]
        out[f"{s}_fp"] = pitch
        out[f"{s}_toe"] = toe
        out[f"{s}_fyaw"] = 0.0
    return out, contacts


def walk_upper(p, t, T, beta, lean=4.0, bob=0.02, sway=0.02, pyaw=5.0, cyaw=4.0, roll=2.0, arm=16.0,
               elb=(14.0, 10.0), run=False, ap=0.25):
    """Pelvis bob/sway/roll, pelvis-thorax counter-rotation (left hip forward at left heel strike),
    level gaze, arm swing opposite to the legs."""
    w = 2 * math.pi * t / T
    wl = w - math.pi * beta                     # left mid-stance
    if run:
        p["hz"] += -bob * (0.5 + 0.5 * math.cos(2 * wl))     # lowest at mid-stance (compression)
    else:
        p["hz"] += -bob * (0.5 - 0.5 * math.cos(2 * wl))     # highest at mid-stance
    p["hx"] += sway * math.cos(wl)
    p["hr"] += -roll * math.cos(wl)
    p["hyaw"] += -pyaw * math.cos(w)
    p["syaw"] += (pyaw + cyaw) * math.cos(w)
    p["nyaw"] += -0.4 * cyaw * math.cos(w)
    p["hdyaw"] += -0.6 * cyaw * math.cos(w)
    p["hp"] += lean * 0.4
    p["sp"] += lean * 0.6
    p["hdp"] -= lean * 0.7
    if arm:
        for s, sgn in (("l", -1.0), ("r", 1.0)):
            c = sgn * math.cos(w - ap)
            p[f"{s}_fwd"] += arm * c
            p[f"{s}_elb"] += elb[0] + elb[1] * max(0.0, c)
    return p


def reach_drop(params, loop, margin=0.006):
    need = np.array([HC.reach_fix(cx, p, margin) for p in params])
    if loop:
        rep = maximum_filter1d(np.concatenate([need, need, need]), 9)
        need = gaussian_filter1d(rep, 2.5)[len(need):2 * len(need)]
    else:
        need = gaussian_filter1d(maximum_filter1d(need, 9, mode="nearest"), 2.5, mode="nearest")
    need = np.maximum(need, 0) + (0.004 if loop else 0.0)
    for p, nd in zip(params, need):
        p["hz"] -= float(nd)
    return float(need.max())


def loco(T, v, gkw, upper, loop=True):
    times = frames(T)
    params, contacts = [], []
    for t in times:
        p = base()
        f, c = gait2(t, T, v, **gkw)
        p.update(f)
        upper(t, p)
        params.append(p)
        contacts.append(c)
    reach_drop(params, loop)
    return params, contacts


# --------------------------------------------------------------------------- footstep planner

class FootPlan:
    """World-space foot of one side: placements (flat-ankle x, y, yaw), steps with heel/ball rolls.
    pitch < 0 pivots on the heel, > 0 on the ball (toes stay down: toe = -pitch)."""

    def __init__(self, S, x=None, y=None, yaw=0.0, pitch=0.0, land_t0=None, land_pitch=0.0, land_dur=0.1, gz=0.0):
        self.S = S
        self.sx = 1.0 if S == "Left" else -1.0
        self.a_r = cx.ank[S]
        self.h_r = cx.heel[S]
        self.b_r = np.array([cx.ball[S][0], cx.ball[S][1], 0.0])
        self.lat0 = cx.lat[S]
        bp = base()
        s = "l" if S == "Left" else "r"
        x = self.a_r[0] + bp[f"{s}_fx"] if x is None else x
        y = self.a_r[1] if y is None else y
        self.segs = []      # planted: dict(x, y, yaw, t_land, land_pitch, land_dur, pitch)
        self.steps = []
        self.segs.append(dict(x=x, y=y, yaw=yaw, t_land=-9.0 if land_t0 is None else land_t0,
                              land_pitch=land_pitch, land_dur=land_dur, pitch=pitch, gz=gz))

    def step(self, t0, t1, x, y, yaw=None, lift=0.07, roll=18.0, roll_t=0.14, heel=10.0, land="heel",
             land_pitch=None, land_dur=0.12, pitch=0.0, kick=0.0, toe_swing=8.0, gz=None):
        prev = self.segs[-1]
        yaw = prev["yaw"] if yaw is None else yaw
        lp = {"heel": -heel, "flat": 0.0, "ball": 20.0}[land] if land_pitch is None else land_pitch
        self.steps.append(dict(t0=t0, t1=t1, lift=lift, roll=max(roll, prev["pitch"]), roll_t=roll_t, kick=kick,
                               toe_swing=toe_swing))
        self.segs.append(dict(x=x, y=y, yaw=yaw, t_land=t1, land_pitch=lp, land_dur=land_dur, pitch=pitch,
                              gz=prev["gz"] if gz is None else gz))
        return self

    def pose(self, x, y, yaw, pitch, gz=0.0):
        Rz = rot(Z, yaw * DEG)
        lat = Rz @ self.lat0
        R = rot(lat, pitch * DEG) @ Rz
        flat = np.array([x, y, self.a_r[2] + gz])
        if abs(pitch) < 1e-6:
            piv = flat + Rz @ (self.h_r - self.a_r)
            return flat, piv, "flat"
        piv_r = self.h_r if pitch < 0 else self.b_r + np.array([0, 0, cx.ball[self.S][2] * smooth(pitch / 45.0)])
        piv = flat + Rz @ (piv_r - self.a_r)
        return piv + R @ (self.a_r - piv_r), piv, ("heel" if pitch < 0 else "ball")

    def _planted_pitch(self, i, t):
        sg = self.segs[i]
        p = sg["pitch"]
        a = t - sg["t_land"]
        if 0 <= a < sg["land_dur"]:
            p = sg["land_pitch"] + (sg["pitch"] - sg["land_pitch"]) * smooth(a / sg["land_dur"])
        if i < len(self.steps):
            st = self.steps[i]
            b = st["t0"] - t
            if 0 <= b < st["roll_t"]:
                p = p + (st["roll"] - p) * smooth(1 - b / st["roll_t"])
        return p

    def at(self, t):
        """-> ankle (world), pitch, yaw, toe, contact (planted, pivot world, kind)."""
        for i, st in enumerate(self.steps):
            if t < st["t0"]:
                return self._planted(i, t)
            if t <= st["t1"]:
                a, b = self.segs[i], self.segs[i + 1]
                u = (t - st["t0"]) / max(st["t1"] - st["t0"], 1e-9)
                a0, _, _ = self.pose(a["x"], a["y"], a["yaw"], st["roll"], a["gz"])
                a1, _, _ = self.pose(b["x"], b["y"], b["yaw"], b["land_pitch"], b["gz"])
                k = smoother(u)
                ank = a0 * (1 - k) + a1 * k
                ank[2] += st["lift"] * math.sin(math.pi * u) ** 1.1
                if st["kick"]:
                    ank[2] += st["kick"] * math.sin(math.pi * min(1.0, u / 0.72)) ** 2
                    ank[1] += 0.35 * st["kick"] * math.sin(math.pi * min(1.0, u / 0.5))
                pitch = st["roll"] * (1 - smooth(u / 0.6)) + b["land_pitch"] * smooth((u - 0.4) / 0.6)
                yaw = a["yaw"] + (b["yaw"] - a["yaw"]) * smoother(u)
                toe = (-max(st["roll"], 0.0) * (1 - smooth(u / 0.35)) + st["toe_swing"] * math.sin(math.pi * u)
                       - max(b["land_pitch"], 0.0) * smooth((u - 0.65) / 0.35))
                return ank, pitch, yaw, toe, (False, None, None)
        return self._planted(len(self.steps), t)

    def _planted(self, i, t):
        sg = self.segs[i]
        pitch = self._planted_pitch(i, t)
        ank, piv, kind = self.pose(sg["x"], sg["y"], sg["yaw"], pitch, sg["gz"])
        toe = -pitch if pitch > 0 else 0.0
        return ank, pitch, sg["yaw"], toe, (True, piv, kind)


def planned(sec, feet, keys, root=None, src=None, src_t=0.15, reach=True, kfollow=0.85):
    """Frames of a stepping one-shot: upper body/pelvis from param keys (pelvis relative to the root),
    feet from FootPlans in world space, converted to in-place by subtracting root(t)."""
    times = frames(sec)
    params, contacts = [], []
    for t in times:
        p = keyed2(keys, t)
        r3 = tuple(root(t)) + (0.0,) if root else (0.0, 0.0, 0.0)
        rx, ry, rz = r3[0], r3[1], r3[2]
        c = {}
        for s, S, sx in SIDES:
            ank, pitch, yaw, toe, ct = feet[S].at(t)
            p[f"{s}_fx"] = ank[0] - rx - cx.ank[S][0]
            p[f"{s}_fy"] = ank[1] - ry - cx.ank[S][1]
            p[f"{s}_fz"] = ank[2] - rz - cx.ank[S][2]
            p[f"{s}_fp"] = pitch
            p[f"{s}_fyaw"] = yaw
            p[f"{s}_toe"] = toe
            p[f"{s}_kout"] = p[f"{s}_kout"] + sx * yaw * kfollow
            c[S] = ct
        if src is not None and t < src_t:
            p = lerp2(src(t), p, float(smooth(t / src_t)))
        params.append(p)
        contacts.append(c)
    if reach:
        reach_drop(params, False)
    return params, contacts


def fit_knee(p, S, z=0.072, lo=-0.85, hi=0.05):
    """Set p['hz'] so the knee joint of leg S sits at height z (kneeling)."""
    for _ in range(28):
        mid = 0.5 * (lo + hi)
        p["hz"] = mid
        k = solved(p)[f"{S}LowerLeg"][:3, 3][2]
        if k > z:
            hi = mid
        else:
            lo = mid
    p["hz"] = 0.5 * (lo + hi)
    return p


def foot_place(S, p):
    """Flat placement (x, y) of the foot in params p (for chaining FootPlans from a key pose)."""
    s = "l" if S == "Left" else "r"
    return cx.ank[S][0] + p[f"{s}_fx"], cx.ank[S][1] + p[f"{s}_fy"]


def root_from_speed(vkeys, sec):
    """Root path (x=0, y forward negative) integrated from a speed envelope [(t, m/s)]."""
    ts = np.arange(0, sec + 1e-9, 1 / 600.0)
    vs = np.array([env(t, vkeys) for t in ts])
    ys = -np.concatenate([[0.0], np.cumsum(0.5 * (vs[1:] + vs[:-1]) * np.diff(ts))])
    return lambda t: (0.0, float(np.interp(t, ts, ys))), float(-ys[-1])


def standing_contacts(params):
    out = []
    for i in range(len(params)):
        c = {}
        for s_, S_ in (("l", "Left"), ("r", "Right")):
            a0 = np.array([params[max(i - 1, 0)][f"{s_}_f{k}"] for k in "xyz"])
            a1 = np.array([params[min(i + 1, len(params) - 1)][f"{s_}_f{k}"] for k in "xyz"])
            still = np.linalg.norm(a1 - a0) * FPS / 2 < 0.03 and params[i][f"{s_}_fz"] < 0.01
            pit = params[i][f"{s_}_fp"]
            c[S_] = (bool(still), None, "ball" if pit > 0.5 else "flat")
        out.append(c)
    return out


# --------------------------------------------------------------------------- shared poses

def sit_pose(slump=1.0):
    """Seated on a 0.45 m bench/stool behind the root: hip joints ~0.12 above the seat."""
    p = base()
    p.update(hz=(SEAT_H + 0.12) - cx.hz, hy=SEAT_Y, hp=-8.0 - 6.0 * slump, sp=12.0 + 20.0 * slump,
             np_=4.0 + 6.0 * slump, hdp=4.0 + 10.0 * slump)
    for s, S, sx in SIDES:
        p[f"{s}_fx"] = -sx * max(0.0, abs(cx.ank[S][0]) - 0.13)
        p[f"{s}_fy"] = -0.05
        p[f"{s}_kup"] = 1.0
        p[f"{s}_kout"] = 8.0
    hands_on_knees(p)
    return p


def knee_top(p, S):
    """A point on top of the knee (rest-space point above the knee joint, carried by the thigh)."""
    M = solved(p)
    k = M[f"{S}LowerLeg"][:3, 3]
    th = unit(M[f"{S}LowerLeg"][:3, 3] - M[f"{S}UpperLeg"][:3, 3])
    up = unit(np.cross(np.cross(th, np.array([0, 0, 1.0])), th))
    if up[2] < 0:
        up = -up
    return k, th, up


def hands_on_knees(p, back=0.075, lift=0.085):
    """Hands on the knees, or as far down the thigh toward them as the arms reach."""
    M = solved(p)
    for s, S, sx in SIDES:
        k, th, up = knee_top(p, S)
        sh = M[f"{S}UpperArm"][:3, 3]
        reach = cx.sk.length[f"{S}UpperArm"] + cx.sk.length[f"{S}LowerArm"] - 0.03
        b = back
        while b < 0.32 and np.linalg.norm(k - th * b + up * lift - sh) > reach:
            b += 0.01
        wrist = k - th * b + up * lift + np.array([sx * 0.012, 0, 0])
        d = unit(th * 0.75 - up * 0.65)
        put_arm(p, s, wrist, (sx * 0.65, 0.55, -0.25), d=d, n=-up, curl=0.38, thb=0.25, ftw=0.5)
    return p


def stand_cup_pose(p, cup=np.array([0.0, -0.30, 1.10]), tilt=0.0, curl=0.55, elbow=(0.55, 0.55, -0.65)):
    """Both hands around a cup (centre `cup`), palms toward it, fingers forward and wrapping."""
    for s, S, sx in SIDES:
        d = unit(np.array([-sx * 0.30, -0.95, 0.10 + tilt]))
        n = unit(np.array([-sx * 1.0, 0.25, 0.0]))
        wrist = cup + np.array([sx * 0.075, 0.07, -0.025 - 0.03 * tilt])
        put_arm(p, s, wrist, (sx * elbow[0], elbow[1], elbow[2]), d=d, n=n, curl=curl, thb=0.55, ftw=0.5)
    return p


# --------------------------------------------------------------------------- clips

RUN_T, RUN_V, RUN_BETA = 20 / 30.0, 3.4, 0.32          # loop periods are whole frames
# Stance shifted back (y_c): the ankle lands ~0.22 m ahead of the hip joint and leaves ~0.43 m behind it,
# so the thigh sweeps from ~30 deg forward to ~20 deg back (lab frame) instead of staying under the body.
RUN_G = dict(beta=RUN_BETA, lift=0.12, step_w=0.075, heel=6.0, toeoff=38.0, y_c=0.18, kick=0.24, kick_pitch=26.0,
             drive=0.08)
STORE = {}


def stance_knee(u):
    """Running stance knee flexion (deg) over stance u in [0, 1]: ~20 at heel strike, ~42 at 40-45 % of
    stance (loading), back to ~20 at toe-off (push-off extension)."""
    return 19.0 + 23.0 * math.sin(math.pi * min(1.0, max(0.0, u)) ** 0.85)


def run_pelvis(params, T, beta, apex=0.016):
    """Pelvis height from the stance leg: the hip joint sits where the stance knee has its running flexion
    (stance_knee), so the leg loads and then extends through push-off; in flight the pelvis follows a
    ballistic arc (apex ~1.6 cm for a 0.12 s flight) between toe-off and the next strike."""
    n = len(params) - 1                       # loop: last frame == first
    L1, L2 = cx.sk.length["LeftUpperLeg"], cx.sk.length["LeftLowerLeg"]
    z = [None] * (n + 1)
    for i in range(n + 1):
        t = i / FPS
        for s, S, ph0 in (("l", "Left", 0.0), ("r", "Right", 0.5)):
            ph = ((t / T) - ph0) % 1.0
            if ph < beta:
                k = stance_knee(ph / beta) * DEG
                d = math.sqrt(L1 * L1 + L2 * L2 + 2 * L1 * L2 * math.cos(k))
                p = params[i]
                hip = solved(p)[f"{S}UpperLeg"][:3, 3]
                ank = cx.ank[S] + np.array([p[f"{s}_fx"], p[f"{s}_fy"], p[f"{s}_fz"]])
                r2 = float((hip[0] - ank[0]) ** 2 + (hip[1] - ank[1]) ** 2)
                z[i] = p["hz"] + (ank[2] + math.sqrt(max(d * d - r2, 0.04)) - hip[2])
    known = [i for i in range(n) if z[i] is not None]
    for j, i0 in enumerate(known):
        i1 = known[(j + 1) % len(known)]
        gap = (i1 - i0) % n
        for k in range(1, gap):
            u = k / gap
            z[(i0 + k) % n] = (1 - u) * z[i0] + u * z[i1] + 4 * apex * u * (1 - u)
    z[n] = z[0]
    for p, zz in zip(params, z):
        p["hz"] = zz


def run_upper(t, p):
    """Running for his life: ~7 deg trunk lean, pelvis/thorax counter-rotation, arms pumping from the
    shoulders close to the body: upper arm -44..+40 deg about the trunk, the hand passes the hip pocket
    behind the hips and rises to the chest ahead, toward the midline but not across it; the forearm
    stays ~35 deg above horizontal in front (elbow 74-88 deg), loose fists, knuckles leading."""
    T = RUN_T
    p["hp"], p["sp"], p["np_"], p["hdp"] = 6.0, 5.0, -2.0, -9.0
    walk_upper(p, t, T, RUN_BETA, lean=0.0, bob=0.0, sway=0.012, pyaw=8.0, cyaw=11.0, roll=3.0, run=True, arm=0.0)
    w = 2 * math.pi * t / T
    for s, S, sgn in (("l", "Left", -1.0), ("r", "Right", 1.0)):
        c = sgn * math.cos(w - 0.35)
        fk_arm(p, s, fwd=6.0 + 42.0 * c, add=23.0 + 9.0 * max(0.0, c),
               elb=80.0 + 8.0 * max(0.0, c) - 6.0 * max(0.0, -c), wr=-15.0, tw=-8.0, curl=1.0)
        p[f"{s}_clav"] = 2.0 + 2.0 * max(0.0, c)
        p[f"{s}_clavf"] = -5.0 * c
    return p


def clip_run():
    params, contacts = loco(RUN_T, RUN_V, RUN_G, run_upper)
    run_pelvis(params, RUN_T, RUN_BETA)
    reach_drop(params, True)
    STORE["run"] = params
    return dict(params=params, contacts=contacts, speed=RUN_V,
                extra=dict(groundSpeed_mps=RUN_V, strideLength_m=round(RUN_V * RUN_T, 4),
                           markers={"step_l": 0.0, "step_r": round(RUN_T / 2, 4)}))


def clip_halt():
    sec = 0.9
    T, v, beta = RUN_T, RUN_V, RUN_BETA
    Td = 0.55

    def ry(t):
        a = min(max(t / Td, 0.0), 1.0)
        return -v * Td * (a - a ** 3 + a ** 4 / 2)
    root = lambda t: (0.0, ry(t))  # noqa: E731
    S_len = v * T
    run = STORE["run"]
    src = lambda t: run[int(round(t * FPS)) % (len(run) - 1)]  # noqa: E731
    # left heel strikes at t=0 (run phase 0)
    yL = RUN_G["y_c"] - beta * S_len / 2 + (cx.ank["Left"][1] - cx.heel["Left"][1])
    L = FootPlan("Left", x=RUN_G["step_w"], y=yL, land_t0=0.0, land_pitch=-RUN_G["heel"], land_dur=0.05)
    yf = ry(sec)
    L.step(0.50, 0.74, 0.14, yf + 0.125, lift=0.05, roll=16.0, land="flat", land_dur=0.1)
    # right foot left the ground (toe-off) at t = -(1 - (0.5 + beta)) T
    t_off = -(1.0 - (0.5 + beta)) * T
    foot_l = np.linalg.norm((cx.ball["Right"] - cx.heel["Right"])[:2])
    ball_y = RUN_G["y_c"] + beta * S_len / 2 - foot_l * (-cx.fwd["Right"][1]) - v * t_off
    yR0 = ball_y + (cx.ank["Right"][1] - cx.ball["Right"][1])
    R = FootPlan("Right", x=-RUN_G["step_w"], y=yR0, pitch=RUN_G["toeoff"])
    R.step(t_off, 0.30, -0.10, ry(0.30) - 0.40, lift=0.06, roll=RUN_G["toeoff"], heel=16.0, land_dur=0.16,
           kick=0.16)
    r0 = run[0]
    b = base()
    k0 = dict(r0)
    k1 = dict(b, hy=0.05, hz=-0.10, hp=2.0, sp=0.0, np_=-2.0, hdp=-6.0, hyaw=-2.0, syaw=4.0)
    for s, S, sx in SIDES:
        fk_arm(k1, s, fwd=26.0, add=-34.0, elb=62.0, wr=-12.0, tw=0.0, curl=0.12)
        k1[f"{s}_clav"] = 10.0
        k1[f"{s}_clavf"] = 6.0
    k2 = dict(k1, hy=0.09, hz=-0.12, hp=-4.0, sp=-9.0, np_=-2.0, hdp=2.0, hyaw=0.0, syaw=0.0)
    for s, S, sx in SIDES:
        fk_arm(k2, s, fwd=30.0, add=-44.0, elb=74.0, wr=-18.0, curl=0.06)
        k2[f"{s}_clav"] = 13.0
        k2[f"{s}_clavf"] = 8.0
    k3 = dict(b, hy=0.07, hz=-0.06, hp=-3.0, sp=-6.0, np_=-2.0, hdp=0.0)
    for s, S, sx in SIDES:
        fk_arm(k3, s, fwd=40.0, add=-6.0, elb=95.0, wr=-6.0, curl=0.3)
        k3[f"{s}_clav"] = 8.0
    k4 = dict(k3, hy=0.06, hz=-0.045, hp=0.0, sp=-2.0, hdp=-2.0)
    for s, S, sx in SIDES:
        fk_arm(k4, s, fwd=34.0, add=0.0, elb=90.0, wr=-2.0, curl=0.3)
        k4[f"{s}_clav"] = 6.0
    keys = [(0.0, k0), (0.06, k0), (0.24, k1), (0.42, k2), (0.66, k3), (0.9, k4)]
    params, contacts = planned(sec, {"Left": L, "Right": R}, keys, root=root, src=src, src_t=0.16)
    dist = -ry(sec)
    return dict(params=params, contacts=contacts, root=root,
                extra=dict(groundSpeed_mps=round(dist / sec, 4), startSpeed_mps=v, rootDistance_m=round(dist, 4),
                           rootPath_m=[round(-ry(t), 4) for t in frames(sec)[::3]],
                           markers={"brake": 0.30, "stop": round(Td, 3)}))


def backstep_upper_fwd(t, p):
    walk_upper(p, t, 1.2, 0.64, lean=0.0, bob=0.012, sway=0.016, pyaw=3.0, cyaw=3.0, roll=1.5, arm=0.0)
    return p


def clip_backstep():
    T, v = 1.2, 0.9
    gk = dict(beta=0.64, lift=0.055, step_w=0.11, heel=8.0, toeoff=20.0)
    times = frames(T)
    fwd = []
    for t in times:
        p = base()
        f, c = gait2(t, T, v, **gk)
        p.update(f)
        backstep_upper_fwd(t, p)
        fwd.append((p, c))
    params, contacts = [], []
    for i, t in enumerate(times):
        p, c = fwd[len(times) - 1 - i]
        p = dict(p)
        w = 2 * math.pi * t / T
        p["hz"] += -0.05
        p["hp"] += 6.0
        p["sp"] = 9.0 + 1.0 * math.cos(2 * w)
        p["np_"] = -2.0
        p["hdp"] = -7.0
        for s, S, sx in SIDES:
            wr = np.array([sx * 0.19, -0.37, 1.12 + 0.008 * math.cos(2 * w + 0.6)])
            put_arm(p, s, wr, (sx * 0.65, 0.45, -0.6), d=np.array([-sx * 0.05, -0.50, 0.86]),
                    n=np.array([-sx * 0.55, -0.80, 0.25]), curl=0.22, idx=0.12, thb=0.15)
            p[f"{s}_clav"] = 5.0
        params.append(p)
        contacts.append(c)
    reach_drop(params, True)
    return dict(params=params, contacts=contacts, speed=-v,
                extra=dict(groundSpeed_mps=-v, strideLength_m=round(v * T, 4),
                           markers={"step_l": 0.0, "step_r": round(T / 2, 4)}))


def collapse_hold_pose():
    p = base()
    p.update(hy=0.09, hp=16.0, hr=2.0, sp=30.0, sr=-3.0, np_=14.0, hdp=30.0, hdr=-6.0)
    lx, ly = 0.15, -0.26
    p["l_fx"] = lx - cx.ank["Left"][0]
    p["l_fy"] = ly - cx.ank["Left"][1]
    p["l_kup"] = 0.9
    p["l_kout"] = 10.0
    # right foot: on the ball, heel up, knee on the ground
    R = FootPlan("Right", x=-0.15, y=0.37, pitch=62.0)
    ank, pitch, yaw, toe, _ = R.at(0.0)
    p["r_fx"], p["r_fy"], p["r_fz"] = ank - cx.ank["Right"]
    p["r_fp"], p["r_toe"] = pitch, toe
    p["r_kup"] = -0.1
    p["r_kout"] = 4.0
    fit_knee(p, "Right", 0.072)
    # left forearm on the left thigh, right arm hanging limp
    k, th, up = knee_top(p, "Left")
    wl = k - th * 0.16 + up * 0.10 + np.array([0.025, 0, 0])
    put_arm(p, "l", wl, (0.7, 0.45, -0.3), d=unit(th * 0.8 - up * 0.6), n=-up, curl=0.45, thb=0.3)
    fk_arm(p, "r", fwd=6.0, add=2.0, elb=14.0, wr=8.0, curl=0.5)
    p["l_clav"] = -2.0
    p["r_clav"] = -5.0
    return p


def clip_collapse():
    sec = 1.4
    hold = collapse_hold_pose()
    b = base()
    L = FootPlan("Left")
    L.step(0.30, 0.60, *foot_place("Left", hold), lift=0.05, roll=14.0, heel=8.0, land_dur=0.12)
    R = FootPlan("Right")
    R.step(0.36, 0.80, -0.15, 0.37, lift=0.035, roll=20.0, land="ball", land_pitch=62.0, pitch=62.0, toe_swing=0.0)
    k1 = dict(b, hz=-0.03, sp=10.0, np_=6.0, hdp=14.0, l_clav=-3.0, r_clav=-3.0)
    fk_arm(k1, "l", fwd=2.0, elb=6.0, curl=0.45)
    fk_arm(k1, "r", fwd=2.0, elb=6.0, curl=0.45)
    k2 = dict(k1, hz=-0.20, hy=0.03, hp=8.0, sp=18.0, np_=8.0, hdp=20.0)
    fk_arm(k2, "l", fwd=14.0, add=-6.0, elb=18.0)
    fk_arm(k2, "r", fwd=10.0, add=-4.0, elb=12.0)
    k3 = dict(hold, hz=hold["hz"] - 0.012, sp=hold["sp"] - 4.0, hdp=hold["hdp"] - 6.0)
    k4 = dict(hold, hz=hold["hz"] - 0.004, sp=hold["sp"] + 2.0)
    keys = [(0.0, b), (0.25, k1), (0.52, k2), (0.84, k3), (1.05, k4), (1.4, hold)]
    params, contacts = planned(sec, {"Left": L, "Right": R}, keys, reach=False)
    STORE["collapse_hold"] = hold
    STORE["collapse_params"] = params
    return dict(params=params, contacts=contacts, extra=dict(markers={"buckle": 0.36, "knee_down": 0.84}))


def clip_collapse_hold():
    sec = 3.2
    hold = STORE["collapse_hold"]
    params = []
    for t in frames(sec):
        p = dict(hold)
        br = per(t, sec, 2)                 # heavy, slow-ish breaths
        p["sp"] = hold["sp"] + 2.5 * br
        p["np_"] = hold["np_"] - 1.5 * br
        p["hdp"] = hold["hdp"] + 2.0 * per(t, sec, 1, 0.2)
        p["hdyaw"] = 3.0 * per(t, sec, 1, 0.6)
        p["l_clav"] = hold["l_clav"] + 2.5 * br
        p["r_clav"] = hold["r_clav"] + 2.5 * br
        p["sr"] = hold["sr"] + 1.0 * per(t, sec, 1)
        params.append(p)
    STORE["collapse_hold_params"] = params
    return dict(params=params, contacts=standing_contacts(params), extra=dict(markers={}))


SUP_DIST = 0.6      # Danko (lf_story_collapse) root this far in front of Tim's root, facing Tim
SUP_LAG = 0.25      # story_intro: lf_story_support starts 0.25 s after lf_story_collapse


def danko_to_tim(v, direction=False):
    """Danko-local point/direction (Blender) -> Tim-local: Danko is rotated 180 deg and 0.6 m in front."""
    return np.array([-v[0], -v[1], v[2]]) if direction else np.array([-v[0], -v[1] - SUP_DIST, v[2]])


def danko_grips(p):
    """Contact points on the sides of Danko's ribcage just under the armpits (Tim-local), with the palm normal
    (toward Danko's midline) and the finger direction (round toward his back, a little up)."""
    M = solved(p)
    out = {}
    for S, sx in (("Left", 1.0), ("Right", -1.0)):
        c = pt_on(M, "UpperChest", np.array([sx * 0.205, 0.035, 1.25]))
        mid = pt_on(M, "UpperChest", np.array([0.0, 0.035, 1.25]))
        back = pt_on(M, "UpperChest", np.array([sx * 0.205, 0.25, 1.25]))
        up = pt_on(M, "UpperChest", np.array([sx * 0.205, 0.035, 1.45]))
        n = unit(mid - c)
        d = unit(unit(back - c) + 0.35 * unit(up - c))
        out[S] = (danko_to_tim(c), danko_to_tim(n, True), danko_to_tim(d, True))
    return out


def tim_hands(p, grips, w=1.0, reach_short=0.0):
    """Tim's right hand on Danko's LEFT side, left hand on Danko's RIGHT side (Danko faces Tim); fingers run on
    along Tim's forearm into the armpit, palms toward Danko's ribs and a little up (lifting)."""
    q = dict(p)
    for s_ in "lr":
        q[f"{s_}_ik"] = None
    M = solved(q)
    for s_, S, sx, dS in (("r", "Right", -1.0, "Left"), ("l", "Left", 1.0, "Right")):
        c, n, dback = grips[dS]
        sh = M[f"{S}UpperArm"][:3, 3]
        d = unit(0.6 * unit(c - sh) + 0.4 * dback)
        n = unit(n + 0.45 * np.array([0.0, 0.0, 1.0]))
        wrist = c - d * 0.065 - n * 0.03 + np.array([0.0, reach_short, 0.0])
        put_arm(p, s_, wrist, (sx * 0.7, 0.35, -0.6), d=d, n=n, hw=w, curl=0.45, thb=0.35, ftw=0.5)
    return p


def support_body(b):
    """Tim's half squat: left foot stepped in, right foot braced back, pelvis down, leaning in."""
    p = dict(b, hz=-0.31, hy=-0.08, hp=26.0, sp=18.0, np_=6.0, hdp=14.0, sr=-2.0)
    p["l_fx"], p["l_fy"] = 0.19 - cx.ank["Left"][0], -0.15 - cx.ank["Left"][1]
    p["r_fx"], p["r_fy"] = -0.21 - cx.ank["Right"][0], 0.08 - cx.ank["Right"][1]
    p["l_kout"], p["r_kout"] = 10.0, 14.0
    p["l_clav"], p["r_clav"] = 4.0, 4.0
    return p


def clip_support():
    """Tim catches Danko, whose legs buckle 0.6 m in front of him (lf_story_collapse, started 0.25 s earlier):
    steps in, drops into a half squat, both hands under Danko's armpits; his hands track Danko's ribcage
    through the fall into the half-kneel (targets solved from the collapse clip's own poses)."""
    sec = 1.4
    col = STORE["collapse_params"]
    grip_at = lambda tc: danko_grips(col[min(int(round(tc * FPS)), len(col) - 1)])  # noqa: E731
    b = base()
    L = FootPlan("Left").step(0.10, 0.38, 0.19, -0.15, yaw=6.0, lift=0.06, roll=14.0, heel=10.0)
    R = FootPlan("Right").step(0.34, 0.58, -0.21, 0.08, yaw=-12.0, lift=0.04, roll=12.0, land="flat")
    k1 = dict(b, sp=6.0, hdp=12.0)
    fk_arm(k1, "l", fwd=32.0, elb=40.0, curl=0.2)
    fk_arm(k1, "r", fwd=32.0, elb=40.0, curl=0.2)
    hold = support_body(b)
    k2 = dict(hold, hz=-0.20, hy=-0.05, hp=20.0, sp=16.0)
    tim_hands(k2, grip_at(0.42 + SUP_LAG), w=0.6, reach_short=0.07)
    k3 = dict(hold, hz=-0.28, hp=24.0)
    keys = [(0.0, b), (0.18, k1), (0.42, k2), (0.70, k3), (1.15, hold), (1.4, hold)]
    for _, k in keys[3:]:
        tim_hands(k, grip_at(min(1.4, 1.15 + SUP_LAG)))
    params, contacts = planned(sec, {"Left": L, "Right": R}, keys, reach=False, kfollow=0.0)
    for i, t in enumerate(frames(sec)):         # hands ride Danko's ribcage from the catch on
        if t >= 0.30:
            g = grip_at(t + SUP_LAG)
            q = tim_hands(dict(params[i]), g)
            w = float(smooth((t - 0.30) / 0.20))
            for s_ in "lr":
                a_, b_ = params[i][f"{s_}_ik"], q[f"{s_}_ik"]
                params[i][f"{s_}_ik"] = dict(wrist=(1 - w) * np.asarray(a_["wrist"]) + w * b_["wrist"],
                                             elbow=unit((1 - w) * np.asarray(a_["elbow"]) + w * b_["elbow"]))
                for k in ("hd", "hn"):
                    params[i][f"{s_}_{k}"] = q[f"{s_}_{k}"]
                params[i][f"{s_}_hw"] = max(params[i][f"{s_}_hw"], w)
    STORE["support_hold"] = params[-1]
    return dict(params=params, contacts=contacts,
                extra=dict(markers={"step": 0.38, "catch": 0.5, "settle": 1.15},
                           partner={"clip": "lf_story_collapse -> lf_story_collapse_hold",
                                    "placement": "Danko's root 0.6 m in front of Tim's root (glTF +Z), facing Tim",
                                    "sync": "support starts 0.25 s after collapse; both holds start together"}))


def clip_support_hold():
    """Holds Danko (lf_story_collapse_hold, same 3.2 s period, started together) under the armpits: hands
    track his breathing ribcage, Tim breathes and steadies."""
    sec = 3.2
    hold = STORE["support_hold"]
    colh = STORE["collapse_hold_params"]
    params = []
    for i, t in enumerate(frames(sec)):
        p = dict(hold)
        br = per(t, sec, 2, 0.15)
        p["sp"] = hold["sp"] + 1.2 * br
        p["hz"] = hold["hz"] - 0.004 * (0.5 + 0.5 * per(t, sec, 1))
        p["hdyaw"] = hold["hdyaw"] + 4.0 * per(t, sec, 1, 0.3)
        p["l_clav"] = hold["l_clav"] + 1.2 * br
        p["r_clav"] = hold["r_clav"] + 1.2 * br
        tim_hands(p, danko_grips(colh[min(i, len(colh) - 1)]))
        params.append(p)
    return dict(params=params, contacts=standing_contacts(params),
                extra=dict(markers={}, partner={"clip": "lf_story_collapse_hold", "sync": "start together"}))


# ---- lf_cage_wood geometry (measured from godot/project/assets/forest_rescue/props/lf_cage_wood.glb, cage space,
# Blender axes: glTF = (x, z, -y)); Danko stands at glTF (0.95, 0.12, 0.95) facing +Z = Blender (0.95, -0.95, 0.12)
CAGE_ROOT = np.array([0.95, -0.95, 0.12])
KEY_SLOT = np.array([0.9465, -1.571, 1.2274])      # socket plate outer face ("the latch")
HINGE_XY = np.array([-0.3801, -1.5518])            # door hinge axis (vertical)
GAP_A = (0.756, 0.964)                             # clear gap between door bars (x), open above z 1.44 / below 1.02
BAR_Y = (-1.465, -1.496)                           # door bar inner / outer face (y)
PLATE_TOP = 1.44                                   # socket plate (y -1.521..-1.571) spans z 1.02..1.44, x 0.69..1.14
LATCH_SLIDE = np.array([-0.08, 0.0, 0.0])          # hand travel along the bolt axis (bolt: -X 0.12 m in unlock 0-0.7 s)
DOOR_T0, DOOR_RATE = 2.2, 0.7                      # story_intro: gate_open time = 0.7 * (t - 2.2), held at 0.55 s


def door_angle(door_t):
    """lf_cage_gate_open door yaw (deg, negative = outward): -95 * smoothstep(t / 1.6); measured -8.0 @0.3 s,
    -25.1 @0.55 s, -38.2 @0.7 s (fit within 1 deg)."""
    return -95.0 * float(smooth(door_t / 1.6))


def door_rot(pw, ang):
    """Rotate a cage-space point (Blender) with the door about the hinge axis by `ang` degrees."""
    c, s_ = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    d = pw[:2] - HINGE_XY
    return np.array([HINGE_XY[0] + c * d[0] - s_ * d[1], HINGE_XY[1] + s_ * d[0] + c * d[1], pw[2]])


def body_front(p, bones=("Head", "Neck", "UpperChest", "Chest", "Spine", "Hips", "LeftShoulder", "RightShoulder",
                         "Hood", "SkirtFront1", "LeftUpperArm")):
    """Most forward (min y) skinned vertex of the given bones in params p."""
    M = solved(p)
    sel = np.where(np.isin(SKIN.dom, bones))[0]
    V = SKIN.pose(M, sel)
    return float(V[:, 1].min())


def fit_hy_front(p, y_front, lo=-0.6, hi=0.2, **kw):
    """Set p['hy'] so the body's most forward vertex sits at y_front (pressing against the bars)."""
    for _ in range(22):
        mid = 0.5 * (lo + hi)
        p["hy"] = mid
        if body_front(p, **kw) < y_front:
            lo = mid
        else:
            hi = mid
    p["hy"] = 0.5 * (lo + hi)
    return p


GAP_B = (1.004, 1.184)                             # bar gap right of the plate (camera side), open above z 1.44


def clip_latch_reach():
    """Inside lf_cage_wood (root at glTF (0.95, 0.12, 0.95), facing the door +Z): steps up, presses his right
    shoulder and cheek to the door bars, pushes the LEFT arm (camera side of the story camera) out through the bar
    gap right of the socket plate, reaches over the plate's top edge and bends the wrist down onto key_slot,
    slides it toward the hinge (bolt axis), holds, then pushes the door outward with the same hand. His head is
    behind the open bars above the plate, so face, hand and latch all read from the city camera."""
    sec = 3.0
    loc = lambda w: np.asarray(w, float) - CAGE_ROOT  # noqa: E731
    key = loc(KEY_SLOT)                                 # (-0.0035, -0.621, 1.1074)
    gap_x = 0.5 * (GAP_B[0] + GAP_B[1]) - CAGE_ROOT[0]   # +0.144
    bar_in = BAR_Y[0] - CAGE_ROOT[1]                     # -0.515
    b = base()
    L = FootPlan("Left").step(0.10, 0.38, 0.10, -0.20, yaw=4.0, lift=0.05, roll=14.0, heel=8.0)
    R = FootPlan("Right").step(0.30, 0.56, -0.20, -0.16, yaw=-6.0, lift=0.05, roll=14.0, heel=8.0)
    lean = dict(b, hx=-0.06, hz=-0.012, hp=7.0, hyaw=-10.0, sp=10.0, syaw=-12.0, sr=4.0, np_=4.0, hdp=16.0,
                hdyaw=26.0, nyaw=10.0, hdr=8.0, l_clav=16.0, l_clavf=-14.0, r_clav=4.0)
    for s_, S in (("l", "Left"), ("r", "Right")):
        x, y = (0.10, -0.20) if S == "Left" else (-0.20, -0.16)
        lean[f"{s_}_fx"], lean[f"{s_}_fy"] = x - cx.ank[S][0], y - cx.ank[S][1]
    # right hand grips the door bar left of the plate (bar x -0.234..-0.194 local, inner face -0.515)
    put_arm(lean, "r", (-0.23, -0.46, 1.27), (-0.75, 0.45, -0.45), curl=0.85, thb=0.6)
    fit_hy_front(lean, bar_in + 0.012)
    sh = solved(lean)["LeftUpperArm"][:3, 3]
    log("latch: body hy", round(lean["hy"], 3), "left shoulder", np.round(sh, 3), "gap x", round(gap_x, 3))
    over_z = PLATE_TOP - CAGE_ROOT[2] + 0.11
    pre = dict(b, hx=-0.03, hy=-0.08, hp=4.0, sp=6.0, hyaw=-6.0, syaw=-6.0, hdp=10.0, hdyaw=14.0, l_clav=10.0,
               l_clavf=-8.0)
    for s_ in "lr":
        pre[f"{s_}_fx"], pre[f"{s_}_fy"] = lean[f"{s_}_fx"], lean[f"{s_}_fy"]
    put_arm(pre, "l", (gap_x, -0.60, over_z + 0.06), (0.6, 0.3, -0.7), d=(-0.05, -1.0, -0.05),
            n=(-0.2, 0.0, -1.0), hw=0.5, curl=0.25, thb=0.2)
    reach = dict(lean)
    put_arm(reach, "l", (gap_x - 0.04, -0.75, over_z + 0.07), (0.5, 0.1, -0.85), d=(-0.05, -1.0, -0.2),
            n=(-0.1, 0.2, -1.0), hw=0.8, curl=0.25, thb=0.2)
    out = dict(lean)
    put_arm(out, "l", (gap_x - 0.07, key[1] - 0.10, over_z - 0.03), (0.25, -0.35, 0.9), d=(-0.05, -0.4, -0.9),
            n=(0.0, 0.9, -0.4), curl=0.25, thb=0.2)
    touch = dict(lean)
    wt = key + np.array([0.01, -0.035, 0.085])
    put_arm(touch, "l", wt, (0.2, -0.45, 0.85), d=(-0.02, 0.18, -1.0), n=(0.0, 1.0, 0.18), curl=0.3, thb=0.25)
    press = dict(touch)
    put_arm(press, "l", wt + np.array([0.0, 0.008, 0.0]), (0.2, -0.45, 0.85), d=(-0.02, 0.18, -1.0),
            n=(0.0, 1.0, 0.18), curl=0.45, thb=0.35)
    lift = dict(touch, sp=lean["sp"] + 1.0)
    wl = wt + LATCH_SLIDE + np.array([0.0, 0.004, 0.02])
    put_arm(lift, "l", wl, (0.25, -0.45, 0.85), d=(-0.06, 0.18, -1.0), n=(0.0, 1.0, 0.18), curl=0.55, thb=0.4)
    hold = dict(lift, hdyaw=18.0, nyaw=6.0)
    glance = dict(hold, hdyaw=-6.0, nyaw=-2.0, hdp=8.0)
    keys = [(0.0, b), (0.30, pre), (0.55, reach), (0.80, out), (1.00, touch), (1.18, press), (1.60, lift),
            (1.80, hold), (2.00, glance), (2.20, hold)]
    t_rel = 2.56
    w_hold_w = wl + CAGE_ROOT
    push_end = dict(hold, sp=hold["sp"] + 3.0, hdyaw=12.0)
    w_rel = loc(door_rot(w_hold_w, door_angle(DOOR_RATE * (t_rel - DOOR_T0))))
    put_arm(push_end, "l", w_rel, (0.25, -0.45, 0.85), d=(-0.06, 0.18, -1.0), n=(0.0, 1.0, 0.18), curl=0.3, thb=0.3)
    put_arm(push_end, "r", (-0.22, -0.30, 1.05), (-0.75, 0.45, -0.45), curl=0.45)
    back = dict(b, hx=-0.03, hy=lean["hy"] + 0.02, hz=-0.02, hp=4.0, sp=6.0, hdp=4.0, hdyaw=6.0, hyaw=-4.0,
                syaw=-2.0, l_clav=4.0)
    for s_ in "lr":
        back[f"{s_}_fx"], back[f"{s_}_fy"] = lean[f"{s_}_fx"], lean[f"{s_}_fy"]
    put_arm(back, "l", (gap_x - 0.02, bar_in + 0.11, over_z - 0.02), (0.7, 0.3, -0.6), curl=0.4)
    fk_arm(back, "r", fwd=10.0, elb=30.0, curl=0.45)
    end = dict(back, hy=lean["hy"] + 0.04, sp=5.0, hdp=2.0, hdyaw=0.0)
    fk_arm(end, "l", fwd=14.0, elb=34.0, curl=0.45)
    fk_arm(end, "r", fwd=10.0, elb=28.0, curl=0.45)
    keys += [(t_rel, push_end), (2.74, back), (3.0, end)]
    params, contacts = planned(sec, {"Left": L, "Right": R}, keys, reach=False, kfollow=0.0)
    for i, t in enumerate(frames(sec)):     # the hand rides the plate as the door starts to swing, then lets go
        if DOOR_T0 <= t <= t_rel:
            p = params[i]
            ik = dict(p["l_ik"])
            ik["wrist"] = loc(door_rot(w_hold_w, door_angle(DOOR_RATE * (t - DOOR_T0))))
            p["l_ik"] = ik
    STORE["latch_end"] = params[-1]
    m = {"reach": 0.55, "touch": 1.0, "lift": 1.6, "hold": 1.8, "push": 2.2, "release": t_rel}
    return dict(params=params, contacts=contacts,
                extra=dict(markers=m,
                           cagePlacement={"root_in_cage_m": [0.95, 0.12, 0.95], "facing": "+Z (toward the door)",
                                          "cage": "lf_cage_wood at the origin, unrotated"},
                           propPoints={"key_slot_m": [0.9465, 1.2274, 1.5668], "hand": "LEFT",
                                       "barGap_m": {"x": [GAP_B[0], GAP_B[1]], "clearAbove_y": 1.44,
                                                    "barWidth": 0.04, "barFace_z": [1.465, 1.496]},
                                       "handSlide_m": [-0.08, 0.0, 0.0],
                                       "door": "push from 2.2 s assumes gate_open time = 0.7 * (t - 2.2)"}))


SQ_GAP = {"atGateOpen_s": 0.55, "doorYaw_deg": -25.1, "clear_m": 0.57,
          "between": "door free stile (1.085, 0.6, 2.144) and latch-side jamb corner (1.39, 0.6, 1.667), glTF cage space"}


SQ_START = [np.array([0.95, -1.15])]       # set from lf_story_latch_reach's end pose (pelvis over the root)


def sq_body(t):
    """Body (pelvis xy, cage space Blender) along the squeeze path: inside -> diagonal gap -> outside."""
    keys = [(0.0, SQ_START[0]), (0.35, np.array([1.08, -1.41])), (0.75, np.array([1.21, -1.89])),
            (1.05, np.array([1.34, -2.22])), (1.35, np.array([1.50, -2.50])), (1.6, np.array([1.55, -2.62]))]
    return env(t, keys)


def clip_squeeze():
    """Out through the door (held at gate_open 0.55 s, door yaw -25 deg): the clear passage is the diagonal gap
    between the door's free stile and the latch-side jamb (0.57 m). Turns 35 deg right so the LEFT shoulder
    leads along the passage (+X / outward), ducks the head, side-steps with the trailing right leg dragged,
    ends outside crouched in the sneak stance. In place: the node follows rootPathXZ_m (keep facing +Z)."""
    sec = 1.6
    start = STORE["latch_end"]
    off0 = np.array([start["hx"], start["hy"]])
    SQ_START[0] = CAGE_ROOT[:2] + off0           # path starts where latch_reach left the body: root = cage root
    def root_w(t):                       # world root (Blender xy): body path minus a decaying start offset
        return sq_body(t) - off0 * (1.0 - float(smooth(t / 0.7)))
    r0 = root_w(0.0)
    def floor_h(xy):                     # ground under a foot, relative to the cage floor (+0.12 world)
        if xy[1] > -1.70:
            return 0.0
        return -0.02 if (xy[1] > -2.05 and xy[0] < 1.45) else -0.12   # threshold slab, then the ground
    rz = lambda t: -0.12 * float(smooth((t - 1.0) / 0.35))  # noqa: E731
    rootf = lambda t: (*(root_w(t) - r0), rz(t))  # noqa: E731
    yawk = [(0.0, 0.0), (0.32, -35.0), (1.12, -35.0), (1.48, 0.0), (1.6, 0.0)]
    def place(t, side):
        """Foot placement (world xy) beside the body: along the body's left axis."""
        B = sq_body(t)
        ya = math.radians(env(t, yawk))
        left = np.array([math.cos(ya), math.sin(ya)])
        return B + left * side
    # feet (cage world), then converted to the root frame by planned()
    lw = lambda xy: (float(xy[0] - r0[0]), float(xy[1] - r0[1]))  # noqa: E731
    sL = np.array([start["l_fx"], start["l_fy"]]) + cx.ank["Left"][:2] + r0
    sR = np.array([start["r_fx"], start["r_fy"]]) + cx.ank["Right"][:2] + r0
    L = FootPlan("Left", *lw(sL))
    R = FootPlan("Right", *lw(sR))
    L.step(0.08, 0.34, *lw(place(0.40, 0.17)), yaw=-30.0, lift=0.06, roll=12.0, heel=8.0,
           gz=floor_h(place(0.40, 0.17)))
    R.step(0.30, 0.62, *lw(place(0.62, -0.11)), yaw=-34.0, lift=0.018, roll=26.0, heel=4.0, land="ball",
           gz=floor_h(place(0.62, -0.11)),
           land_pitch=14.0, toe_swing=0.0)
    L.step(0.56, 0.84, *lw(place(0.90, 0.17)), yaw=-35.0, lift=0.06, roll=12.0, heel=8.0,
           gz=floor_h(place(0.90, 0.17)))
    R.step(0.80, 1.12, *lw(place(1.10, -0.11)), yaw=-30.0, lift=0.018, roll=26.0, heel=4.0, land="ball",
           gz=floor_h(place(1.10, -0.11)),
           land_pitch=14.0, toe_swing=0.0)
    # end exactly on lf_story_sneak frame 0 (feet, pitch, upper body) so the sneak blends in cleanly
    sn0 = loco(SNEAK_T, 1.3, dict(beta=0.60, lift=0.07, step_w=0.11, heel=6.0, toeoff=24.0), sneak_upper)[0][0]
    e = sq_body(1.6)
    for F, s_, S, t0, t1 in ((L, "l", "Left", 1.10, 1.34), (R, "r", "Right", 1.28, 1.52)):
        xy = e + cx.ank[S][:2] + np.array([sn0[f"{s_}_fx"], sn0[f"{s_}_fy"]])
        fp = float(sn0[f"{s_}_fp"])
        F.step(t0, t1, *lw(xy), yaw=0.0, lift=0.05, roll=12.0, heel=8.0, gz=floor_h(xy),
               land="ball" if fp > 0 else "heel",
               land_pitch=fp if fp > 0 else -max(-fp, 1.0), pitch=fp if fp > 0 else 0.0)
    b = base()
    tuck = dict(b, hz=-0.07, hp=10.0, sp=16.0, np_=8.0, hdp=22.0, hdyaw=-8.0, sr=2.0, l_clav=6.0, r_clav=6.0)
    put_arm(tuck, "l", (0.03, -0.20, 1.18), (0.6, 0.4, -0.7), curl=0.6)
    put_arm(tuck, "r", (-0.09, -0.22, 1.12), (-0.6, 0.4, -0.7), curl=0.6)
    lead = dict(tuck, hz=-0.10, sp=20.0, hdp=26.0, hdyaw=10.0, nyaw=4.0, sr=4.0)
    put_arm(lead, "l", (0.10, -0.24, 1.10), (0.6, 0.3, -0.75), curl=0.55)
    crouch = dict(sn0)
    keys = [(0.0, start), (0.30, tuck), (0.75, lead), (1.05, lead), (1.40, crouch), (1.6, crouch)]
    params, contacts = planned(sec, {"Left": L, "Right": R}, keys, root=rootf, reach=True, kfollow=0.7)
    for i, t in enumerate(frames(sec)):  # body yaw + pelvis offset from the path (relative to the root)
        p = params[i]
        B = sq_body(t)
        rw = root_w(t)
        if t > 0.0:
            w = float(smooth(t / 0.3))
            p["hx"] = (1 - w) * p["hx"] + w * float(B[0] - rw[0])
            p["hy"] = (1 - w) * p["hy"] + w * float(B[1] - rw[1])
        p["hyaw"] = env(t, yawk) + (1 - float(smooth(t / 0.3))) * start["hyaw"]
    dist = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(np.array([root_w(t) for t in frames(sec)]),
                                                                       axis=0), axis=1))])
    xz = [[round(float(root_w(t)[0] - r0[0]), 4), round(rz(t), 4), round(float(-(root_w(t)[1] - r0[1])), 4)]
          for t in frames(sec)[::3]]
    return dict(params=params, contacts=contacts, root=rootf,
                extra=dict(groundSpeed_mps=round(float(dist[-1]) / sec, 4), rootDistance_m=round(float(dist[-1]), 4),
                           rootPath_m=[round(float(d), 4) for d in dist[::3]], rootPathXYZ_m=xz,
                           rootPathNote="node keeps facing +Z (cage door direction); glTF x/y/z offsets of the node "
                                        "from the start root (= latch_reach root on the cage floor, +0.12), every "
                                        "0.1 s; y drops 0.12 as he steps off the threshold onto the ground",
                           gapAssumed=SQ_GAP, markers={"turn": 0.3, "through": 0.85, "out": 1.35}))


SNEAK_T = 28 / 30.0


def sneak_upper(t, p):
    T = SNEAK_T
    p["hz"] = -0.13
    p["hp"], p["sp"], p["np_"], p["hdp"] = 18.0, 20.0, -4.0, -26.0
    walk_upper(p, t, T, 0.60, lean=0.0, bob=0.012, sway=0.014, pyaw=4.0, cyaw=3.0, roll=1.5, arm=0.0)
    w = 2 * math.pi * t / T
    for s, S, sgn in (("l", "Left", -1.0), ("r", "Right", 1.0)):
        c = sgn * math.cos(w - 0.3)
        fk_arm(p, s, fwd=22.0 + 9.0 * c, add=-2.0, elb=62.0 + 6.0 * max(c, 0.0), wr=6.0, curl=0.45)
        p[f"{s}_clav"] = 4.0
        p[f"{s}_kout"] = 6.0
    return p


def clip_sneak():
    T, v = SNEAK_T, 1.3
    params, contacts = loco(T, v, dict(beta=0.60, lift=0.07, step_w=0.11, heel=6.0, toeoff=24.0), sneak_upper)
    return dict(params=params, contacts=contacts, speed=v,
                extra=dict(groundSpeed_mps=v, strideLength_m=round(v * T, 4),
                           markers={"step_l": 0.0, "step_r": round(T / 2, 4)}))


def kneel_pose(hy, hp, sp, ball_y=0.16, pitch=68.0, kz=0.072):
    p = base()
    p.update(hy=hy, hp=hp, sp=sp)
    for s, S, sx in SIDES:
        F = FootPlan(S, x=sx * 0.125, y=ball_y + (cx.ank[S][1] - cx.ball[S][1]), pitch=pitch)
        ank, pit, yaw, toe, _ = F.at(0.0)
        p[f"{s}_fx"], p[f"{s}_fy"], p[f"{s}_fz"] = ank - cx.ank[S]
        p[f"{s}_fp"], p[f"{s}_toe"] = pit, toe
        p[f"{s}_kup"] = -0.15
        p[f"{s}_kout"] = 6.0
    fit_knee(p, "Left", kz)
    return p


def head_cover(p):
    """Hands clasped over the back of the head, elbows forward beside the face."""
    M = solved(p)
    for s, S, sx in SIDES:
        occ = pt_on(M, "Head", np.array([sx * 0.045, 0.085, 1.70]))
        Rh = M["Head"][:3, :3] @ cx.sk.R["Head"][:3, :3].T
        back = Rh @ np.array([0.0, 1.0, 0.0])
        up = Rh @ np.array([0.0, 0.0, 1.0])
        wrist = occ + back * 0.03 - up * 0.07 + Rh @ np.array([sx * 0.05, 0, 0])
        put_arm(p, s, wrist, Rh @ np.array([sx * 0.6, -0.7, -0.3]), d=unit(up * 0.6 - Rh @ np.array([sx * 0.8, 0, 0])),
                n=-back, curl=0.45, thb=0.3, ftw=0.45)
        p[f"{s}_clav"] = 10.0
        p[f"{s}_clavf"] = -6.0
    return p


def hide_hold_pose():
    p = kneel_pose(hy=0.07, hp=38.0, sp=34.0)
    p.update(np_=16.0, hdp=26.0)
    return head_cover(p)


def clip_hide():
    sec = 1.0
    hold = hide_hold_pose()
    b = base()
    feet = {}
    for s, S, sx in SIDES:
        F = FootPlan(S)
        x, y = foot_place(S, hold)
        F.step(0.12 + (0.04 if S == "Right" else 0.0), 0.50 + (0.04 if S == "Right" else 0.0), x, y,
               lift=0.04, roll=30.0, land="ball", land_pitch=hold[f"{s}_fp"], pitch=hold[f"{s}_fp"], toe_swing=0.0)
        feet[S] = F
    k1 = dict(b, hz=-0.06, sp=12.0, np_=10.0, hdp=18.0, l_clav=8.0, r_clav=8.0)
    fk_arm(k1, "l", fwd=40.0, add=-4.0, elb=90.0, curl=0.5)
    fk_arm(k1, "r", fwd=40.0, add=-4.0, elb=90.0, curl=0.5)
    k2 = dict(hold, hz=hold["hz"] + 0.18, hy=0.02, hp=20.0, sp=22.0, np_=12.0, hdp=20.0)
    k2 = head_cover(k2)
    k3 = dict(hold, hz=hold["hz"] - 0.012)
    k3 = head_cover(k3)
    keys = [(0.0, b), (0.16, k1), (0.50, k2), (0.80, k3), (1.0, hold)]
    params, contacts = planned(sec, feet, keys, reach=False, kfollow=0.0)
    STORE["hide_hold"] = hold
    return dict(params=params, contacts=contacts, extra=dict(markers={"down": 0.8}))


def clip_hide_hold():
    sec = 3.0
    hold = STORE["hide_hold"]
    params = []
    for t in frames(sec):
        p = dict(hold)
        br = per(t, sec, 5)          # fast shallow breaths
        tr = 0.5 * per(t, sec, 23, 0.1) + 0.35 * per(t, sec, 31, 0.4)     # trembling
        p["sp"] = hold["sp"] + 1.4 * br + 0.4 * tr
        p["np_"] = hold["np_"] - 0.6 * br
        p["hdp"] = hold["hdp"] + 0.6 * tr
        p["hdyaw"] = 0.5 * per(t, sec, 29, 0.7)
        for s in "lr":
            p[f"{s}_clav"] = hold[f"{s}_clav"] + 1.2 * br + 0.5 * tr
        params.append(p)
    return dict(params=params, contacts=standing_contacts(params), extra=dict(markers={}))


def fit_shoulders(p, z, lo=0.0, hi=80.0):
    """Set p['sp'] (spine flexion) so the shoulder joints sit at height z."""
    for _ in range(24):
        mid = 0.5 * (lo + hi)
        p["sp"] = mid
        M = solved(p)
        if 0.5 * (M["LeftUpperArm"][2, 3] + M["RightUpperArm"][2, 3]) > z:
            lo = mid
        else:
            hi = mid
    p["sp"] = 0.5 * (lo + hi)
    return p


def hands_on_ground(p, fwd=0.10, spread=0.95):
    M = solved(p)
    for s, S, sx in SIDES:
        sh = M[f"{S}UpperArm"][:3, 3]
        wrist = np.array([sh[0] * spread, sh[1] - fwd, 0.07])
        put_arm(p, s, wrist, (sx * 0.55, 0.8, 0.1), d=(-sx * 0.2, -0.98, 0.0), n=(0.0, 0.0, -1.0), curl=0.18,
                thb=0.12, ftw=0.5)
    return p


def clip_peek():
    sec = 2.2
    hold = STORE["hide_hold"]
    up1 = kneel_pose(hy=0.05, hp=34.0, sp=30.0)
    up1.update(np_=6.0, hdp=8.0)
    up1 = head_cover(up1)
    low = kneel_pose(hy=0.04, hp=36.0, sp=30.0)
    low.update(np_=-22.0, hdp=-30.0)
    fit_shoulders(low, 0.56)
    hands_on_ground(low, fwd=0.15)
    lk = dict(low, hdyaw=40.0, nyaw=14.0, hdr=4.0)
    rk = dict(low, hdyaw=-38.0, nyaw=-14.0, hdr=-4.0)
    keys = [(0.0, hold), (0.5, up1), (0.95, low), (1.3, lk), (1.45, lk), (1.8, rk), (1.92, rk), (2.2, low)]
    params = [keyed2(keys, t) for t in frames(sec)]
    for p in params:                 # knees stay on the ground while the hips rise
        fit_knee(p, "Left", 0.072)
    return dict(params=params, contacts=standing_contacts(params), extra=dict(markers={"look_left": 1.3,
                                                                                         "look_right": 1.8}))


def tired_walk_src():
    """lf_civilian_follow_tired (v2 civilian set) reproduced exactly: start pose of the stumble."""
    b = base()
    bt = dict(b)
    bt.update(sp=12.0, np_=8.0, hdp=10.0, l_clav=-3, r_clav=-3, l_elb=8, r_elb=8, l_curl=0.25, r_curl=0.25)
    params, contacts = HC.locomotion(cx, "follow_tired", 1.25, 0.95, beta=0.66, lift=0.055, lean=9.0,
                                     arm_swing=7.0, elbow=6.0, bob=0.03, sway=0.03, pelvis_yaw=4.0, heel=8.0,
                                     toeoff=24.0, base_p=bt)
    return params, contacts


def clip_stumble():
    sec = 1.2
    src_p, src_c = tired_walk_src()
    src = lambda t: src_p[int(round(t * FPS)) % (len(src_p) - 1)]  # noqa: E731
    v0 = 0.95
    root, dist = root_from_speed([(0.0, v0), (0.35, 1.30), (0.75, 0.70), (1.12, 0.0), (1.2, 0.0)], sec)
    T, beta = 1.25, 0.66
    S_len = v0 * T
    yL = -beta * S_len / 2 + (cx.ank["Left"][1] - cx.heel["Left"][1])
    xL = 0.095
    L = FootPlan("Left", x=xL, y=yL, land_t0=0.0, land_pitch=-8.0, land_dur=0.06)
    # right foot: heel already off at t=0 (stance u=0.76 of follow_tired), toe-off at 0.2 s
    p0 = src(0.0)
    aR = cx.ank["Right"] + np.array([p0["r_fx"], p0["r_fy"], p0["r_fz"]])
    foot_l = np.linalg.norm((cx.ball["Right"] - cx.heel["Right"])[:2])
    ball_y = -beta * S_len / 2 + v0 * (0.76 * beta * T) - foot_l * (-cx.fwd["Right"][1])
    yR = ball_y + (cx.ank["Right"][1] - cx.ball["Right"][1])
    R = FootPlan("Right", x=-0.095, y=yR, pitch=p0["r_fp"])
    _, ry62 = root(0.62)
    R.step(0.20, 0.64, -0.12, ry62 - 0.30, lift=0.03, roll=24.0, heel=6.0, land="heel", land_dur=0.1)
    _, ry98 = root(1.0)
    L.step(0.60, 0.98, 0.13, ry98 + 0.10, lift=0.04, roll=26.0, land="ball", land_pitch=22.0, pitch=18.0,
           land_dur=0.12, toe_swing=0.0)
    b = base()
    k0 = dict(p0)
    k1 = dict(p0, sp=16.0, hdp=16.0, hz=p0["hz"] - 0.02)
    k2 = dict(b, hz=-0.10, hy=-0.04, hp=16.0, sp=22.0, np_=10.0, hdp=18.0)
    fk_arm(k2, "l", fwd=45.0, add=-12.0, elb=40.0, wr=-10.0, curl=0.2)
    fk_arm(k2, "r", fwd=55.0, add=-8.0, elb=30.0, wr=-10.0, curl=0.2)
    k3 = dict(k2, hz=-0.22, hy=-0.08, hp=24.0, sp=28.0, np_=10.0, hdp=16.0, hr=-3.0)
    fk_arm(k3, "l", fwd=70.0, add=-10.0, elb=30.0, wr=-14.0, curl=0.15)
    fk_arm(k3, "r", fwd=74.0, add=-6.0, elb=26.0, wr=-14.0, curl=0.15)
    for s in "lr":
        k3[f"{s}_kup"] = 0.5
        k3[f"{s}_kout"] = 10.0
    k4 = dict(k3, hz=-0.30, hy=-0.10, hp=28.0, sp=30.0, hdp=20.0)
    keys = [(0.0, k0), (0.18, k1), (0.55, k2), (0.95, k3), (1.2, k4)]
    params, contacts = planned(sec, {"Left": L, "Right": R}, keys, root=root, src=src, src_t=0.18)
    return dict(params=params, contacts=contacts, root=root,
                extra=dict(groundSpeed_mps=round(dist / sec, 4), startSpeed_mps=v0, rootDistance_m=round(dist, 4),
                           rootPath_m=[round(-root(t)[1], 4) for t in frames(sec)[::3]],
                           startsFrom="lf_civilian_follow_tired (frame 0, left heel strike)",
                           markers={"trip": 0.3, "fall": 0.75}))


def clip_catch():
    sec = 1.2
    b = base()
    R = FootPlan("Right")
    R.step(0.14, 0.44, -0.15, -0.28, lift=0.06, roll=16.0, heel=12.0)
    L = FootPlan("Left")
    L.step(0.62, 0.82, 0.15, 0.05, lift=0.025, roll=10.0, land="flat", land_dur=0.08)
    k1 = dict(b, sp=6.0, hdp=6.0, hy=-0.02)
    put_arm(k1, "l", (0.30, -0.36, 1.10), (0.6, 0.6, -0.5), d=(0.15, -0.95, 0.2), n=(-0.6, 0.0, 0.8), curl=0.15)
    put_arm(k1, "r", (-0.30, -0.36, 1.10), (-0.6, 0.6, -0.5), d=(-0.15, -0.95, 0.2), n=(0.6, 0.0, 0.8), curl=0.15)
    k2 = dict(b, sp=12.0, hp=6.0, hdp=10.0, hy=-0.10, hz=-0.04)
    put_arm(k2, "l", (0.26, -0.52, 1.12), (0.6, 0.6, -0.5), d=(0.0, -0.9, 0.35), n=(-0.65, 0.0, 0.75), curl=0.12)
    put_arm(k2, "r", (-0.26, -0.52, 1.12), (-0.6, 0.6, -0.5), d=(0.0, -0.9, 0.35), n=(0.65, 0.0, 0.75), curl=0.12)
    k3 = dict(k2, sp=14.0, hp=10.0, hy=-0.08, hz=-0.12, hdp=14.0)
    put_arm(k3, "l", (0.21, -0.44, 1.03), (0.6, 0.5, -0.6), d=(-0.35, -0.75, 0.55), n=(-0.75, 0.2, 0.6), curl=0.4)
    put_arm(k3, "r", (-0.21, -0.44, 1.03), (-0.6, 0.5, -0.6), d=(0.35, -0.75, 0.55), n=(0.75, 0.2, 0.6), curl=0.4)
    k4 = dict(k3, sp=10.0, hp=6.0, hy=-0.09, hz=-0.10, hdp=12.0)
    put_arm(k4, "l", (0.20, -0.42, 1.06), (0.6, 0.5, -0.6), d=(-0.35, -0.75, 0.55), n=(-0.75, 0.2, 0.6), curl=0.45)
    put_arm(k4, "r", (-0.20, -0.42, 1.06), (-0.6, 0.5, -0.6), d=(0.35, -0.75, 0.55), n=(0.75, 0.2, 0.6), curl=0.45)
    keys = [(0.0, b), (0.22, k1), (0.55, k2), (0.78, k3), (1.2, k4)]
    params, contacts = planned(sec, {"Left": L, "Right": R}, keys, reach=True)
    return dict(params=params, contacts=contacts, extra=dict(markers={"catch": 0.6}))


def sit_loop_pose():
    return sit_pose(1.0)


def clip_sit():
    sec = 4.0
    s0 = sit_loop_pose()
    params = []
    for t in frames(sec):
        p = dict(s0)
        br = per(t, sec, 2)
        look = 0.5 - 0.5 * math.cos(2 * math.pi * t / sec)
        p["sp"] = s0["sp"] + 2.0 * br
        p["np_"] = s0["np_"] - 1.0 * br - 3.0 * look ** 2
        p["hdp"] = s0["hdp"] - 8.0 * look ** 2
        p["hdyaw"] = 8.0 * per(t, sec, 1) * look
        p["l_clav"] = s0["l_clav"] + 1.5 * br
        p["r_clav"] = s0["r_clav"] + 1.5 * br
        params.append(p)
    STORE["sit"] = s0
    return dict(params=params, contacts=standing_contacts(params), extra=dict(markers={}))


def clip_sit_down():
    sec = 1.4
    b = base()
    s_end = STORE["sit"]
    k1 = dict(b, hz=-0.06, hy=0.04, hp=14.0, sp=14.0, hdp=8.0)
    fk_arm(k1, "l", fwd=22.0, elb=24.0)
    fk_arm(k1, "r", fwd=22.0, elb=24.0)
    k2 = dict(b, hz=-0.26, hy=0.24, hp=26.0, sp=26.0, np_=2.0, hdp=2.0)
    for s in "lr":
        k2[f"{s}_fx"], k2[f"{s}_fy"] = s_end[f"{s}_fx"], s_end[f"{s}_fy"] * 0.5
        k2[f"{s}_kup"], k2[f"{s}_kout"] = 0.6, 8.0
    fk_arm(k2, "l", fwd=36.0, elb=36.0, curl=0.3)
    fk_arm(k2, "r", fwd=36.0, elb=36.0, curl=0.3)
    k3 = dict(s_end, hz=s_end["hz"] + 0.004, hp=10.0, sp=22.0, hdp=4.0)
    k3 = hands_on_knees(k3)
    k4 = dict(s_end, hz=s_end["hz"] - 0.006, sp=s_end["sp"] + 3.0)
    keys = [(0.0, b), (0.3, k1), (0.78, k2), (1.0, k3), (1.18, k4), (1.4, s_end)]
    feet = {S: FootPlan(S) for S in ("Left", "Right")}
    for S in ("Left", "Right"):       # small shuffle of the feet forward while the hips are on the way down
        x, y = foot_place(S, s_end)
        feet[S].step(0.55 if S == "Left" else 0.62, 0.8 if S == "Left" else 0.86, x, y, lift=0.02, roll=8.0,
                     land="flat", land_dur=0.06)
    params, contacts = planned(sec, feet, keys, reach=True, kfollow=0.0)
    return dict(params=params, contacts=contacts, extra=dict(markers={"seated": 1.0}))


def clip_guide_sit():
    sec = 1.6
    b = base()
    sh0 = np.array([0.18, -0.58, 1.34])      # partner's shoulders (standing) relative to this root
    sh1 = np.array([0.17, -0.42, 1.01])      # partner seated (lf_story_sit_down, root 0.60 m ahead)

    def on_sh(p, c, curl=0.35):
        for s, S, sx in SIDES:
            tip = np.array([sx * c[0], c[1], c[2]])
            d = np.array([-sx * 0.12, -0.97, -0.20])
            wrist = tip + np.array([sx * 0.01, 0.105, 0.03])
            put_arm(p, s, wrist, (sx * 0.85, 0.3, -0.35), d=d, n=np.array([0.0, -0.2, -0.98]), curl=curl,
                    thb=0.2, ftw=0.5)
        return p
    k1 = on_sh(dict(b, sp=14.0, hp=6.0, hdp=10.0, hy=-0.02), sh0)
    mid = (sh0 + sh1) / 2 + np.array([0, -0.03, 0.0])
    k2 = on_sh(dict(b, sp=26.0, hp=12.0, hdp=16.0, hz=-0.05, hy=0.0), mid)
    k3 = on_sh(dict(b, sp=34.0, hp=16.0, hdp=20.0, hz=-0.10, hy=0.03), sh1, curl=0.4)
    k4 = dict(b, sp=18.0, hp=8.0, hdp=12.0, hz=-0.04)
    put_arm(k4, "l", (0.24, -0.30, 1.05), (0.7, 0.5, -0.4), curl=0.3)
    put_arm(k4, "r", (-0.24, -0.30, 1.05), (-0.7, 0.5, -0.4), curl=0.3)
    k5 = dict(b, sp=4.0, hdp=6.0)
    keys = [(0.0, b), (0.32, k1), (0.72, k2), (1.08, k3), (1.36, k4), (1.6, k5)]
    params = [keyed2(keys, t) for t in frames(sec)]
    return dict(params=params, contacts=standing_contacts(params),
                extra=dict(markers={"hands_on": 0.32, "seated": 1.08, "release": 1.2},
                           partner={"startShoulders_m": [0.18, 1.34, 0.58], "seatedShoulders_m": [0.17, 1.01, 0.42],
                                    "note": "partner root ~0.60 m in front, same facing, playing lf_story_sit_down"}))


CUP = np.array([0.0, -0.31, 1.10])


def cup_walk_upper(t, p):
    T = 1.1
    walk_upper(p, t, T, 0.64, lean=2.0, bob=0.012, sway=0.014, pyaw=3.0, cyaw=1.0, roll=1.5, arm=0.0)
    w = 2 * math.pi * t / T
    p["hdp"] += 16.0
    p["np_"] = 6.0
    c = CUP + np.array([0.0, 0.0, 0.006 * math.cos(2 * (w - math.pi * 0.64))])
    stand_cup_pose(p, c)
    for s in "lr":
        p[f"{s}_clav"] = 2.0
    return p


def clip_carry_cup():
    T, v = 1.1, 1.0
    params, contacts = loco(T, v, dict(beta=0.64, lift=0.06, step_w=0.10, heel=10.0, toeoff=22.0), cup_walk_upper)
    return dict(params=params, contacts=contacts, speed=v,
                extra=dict(groundSpeed_mps=v, strideLength_m=round(v * T, 4),
                           markers={"step_l": 0.0, "step_r": round(T / 2, 4)}))


def clip_offer():
    sec = 1.4
    b = base()
    k0 = stand_cup_pose(dict(b, hdp=14.0, np_=6.0), CUP)
    k1 = stand_cup_pose(dict(b, sp=6.0, hdp=8.0, hy=-0.01), CUP + np.array([0.0, -0.08, 0.03]))
    k2 = stand_cup_pose(dict(b, sp=12.0, hp=4.0, hdp=6.0, hdyaw=0.0, hy=-0.03, np_=-2.0),
                        np.array([0.0, -0.53, 1.13]), tilt=0.05)
    k3 = stand_cup_pose(dict(b, sp=11.0, hp=4.0, hdp=4.0, hy=-0.03, np_=-2.0, hdr=4.0), np.array([0.0, -0.52, 1.13]),
                        tilt=0.05)
    k2["l_fy"] = -0.12
    k3["l_fy"] = -0.12
    keys = [(0.0, k0), (0.3, k1), (0.85, k2), (1.4, k3)]
    feet ={"Left": FootPlan("Left").step(0.25, 0.55, *foot_place("Left", k2), lift=0.04, roll=12.0, heel=8.0),
            "Right": FootPlan("Right")}
    params, contacts = planned(sec, feet, keys, reach=True)
    return dict(params=params, contacts=contacts, extra=dict(markers={"offer": 0.85}))


def drink_keys(sec=4.0):
    s0 = sit_pose(0.35)
    s0.update(hdp=6.0, np_=4.0)
    low = np.array([0.0, -0.10, 0.80])
    M = solved(s0)
    low = M["Hips"][:3, 3] + np.array([0.0, -0.25, 0.25])
    rest = stand_cup_pose(dict(s0), low, curl=0.55, elbow=(0.5, 0.4, -0.75))
    sip_head = dict(s0, hdp=-10.0, np_=-4.0, sp=s0["sp"] - 4.0)
    M2 = solved(sip_head)
    mouth = pt_on(M2, "Head", np.array([0.0, -0.115, 1.60]))
    Rh = M2["Head"][:3, :3] @ cx.sk.R["Head"][:3, :3].T
    cup_sip = mouth + Rh @ np.array([0.0, -0.075, -0.035])
    sip = stand_cup_pose(sip_head, cup_sip, tilt=0.75, curl=0.55, elbow=(0.45, -0.25, -0.85))
    pre_head = dict(s0, hdp=0.0, np_=2.0)
    M3 = solved(pre_head)
    mouth3 = pt_on(M3, "Head", np.array([0.0, -0.115, 1.60]))
    Rh3 = M3["Head"][:3, :3] @ cx.sk.R["Head"][:3, :3].T
    pre = stand_cup_pose(pre_head, mouth3 + Rh3 @ np.array([0.0, -0.10, -0.07]), tilt=0.35, curl=0.55,
                         elbow=(0.5, -0.1, -0.85))
    keys = [(0.0, rest), (0.85, pre), (1.25, sip), (1.85, sip), (2.25, pre), (3.0, rest), (sec, rest)]
    return keys, rest


def clip_drink():
    sec = 4.0
    keys, rest = drink_keys(sec)
    params = []
    for t in frames(sec):
        p = keyed2(keys, t)
        br = per(t, sec, 2, 0.25)
        p["sp"] = p["sp"] + 1.2 * br
        params.append(p)
    return dict(params=params, contacts=standing_contacts(params), extra=dict(markers={"sip": 1.25}))


BOY = np.array([-0.25, -1.05, 1.22])   # boy (Mitya) 1.05 m in front, 0.25 m to Danko's right; chest/eye height
CAM_DIR = unit(np.array([0.55, -0.55, 0.61]))  # game city camera, glTF offset (75, 83, 75) -> Blender (75, -75, 83)


def clip_show_wrist():
    """Seated: lifts the LEFT forearm to chest height and turns the inner wrist (the ring mark on LeftHand) up
    and out toward the boy in front-right and toward the game camera, then holds."""
    sec = 1.6
    s0 = STORE["sit"]
    up = dict(s0, sp=s0["sp"] - 8.0, hp=s0["hp"] + 2.0, np_=s0["np_"] - 4.0, hdp=s0["hdp"] - 10.0,
              syaw=-10.0, hdyaw=-18.0, nyaw=-6.0, l_clav=8.0, l_clavf=-10.0)
    M = solved(up)
    sh = M["LeftUpperArm"][:3, 3]
    wrist = sh + np.array([0.15, -0.20, -0.15])     # elbow stays down at his side (flank skinning)
    n = unit(unit(BOY - wrist) + CAM_DIR)                    # inner wrist faces boy + camera
    d = unit(np.array([0.0, 0.0, 1.0]) - n[2] * n)           # fingers as upright as that allows
    lift = dict(up)
    put_arm(lift, "l", wrist + np.array([0.02, 0.03, -0.08]), (0.3, 0.2, -0.93), d=(0.0, -0.15, 1.0),
            n=(-1.0, 0.0, 0.1), hw=0.6, curl=0.3, thb=0.2, ftw=0.6)
    show = dict(up, hdp=up["hdp"] + 4.0)
    put_arm(show, "l", wrist, (0.3, 0.2, -0.93), d=d, n=n, curl=0.25, thb=0.15, ftw=0.6)
    show2 = dict(show)
    put_arm(show2, "l", wrist + 0.03 * unit(BOY - wrist), (0.3, 0.2, -0.93), d=d, n=n, curl=0.25, thb=0.15,
            ftw=0.6)
    keys = [(0.0, s0), (0.30, dict(up, l_ik=s0["l_ik"])), (0.75, lift), (1.1, show), (1.6, show2)]
    for _, k in keys:
        k["l_hinge"] = True
    params = [keyed2(keys, t) for t in frames(sec)]
    Mw = solved(params[-1])
    hn = -Mw["LeftHand"][:3, 2]
    log("show_wrist: palm normal", np.round(hn, 2), "to boy", round(math.degrees(math.acos(np.clip(
        hn @ unit(BOY - Mw["LeftHand"][:3, 3]), -1, 1))), 1), "deg, to camera",
        round(math.degrees(math.acos(np.clip(hn @ CAM_DIR, -1, 1))), 1), "deg, wrist z",
        round(float(Mw["LeftHand"][2, 3]), 3))
    return dict(params=params, contacts=standing_contacts(params),
                extra=dict(markers={"lift": 0.75, "show": 1.1},
                           partner={"boy": "1.05 m in front, 0.25 m to Danko's right (glTF (-0.25, 0, 1.05))"}))


def clip_point_low():
    sec = 1.4
    b = base()
    tgt = np.array([-0.05, -0.80, 0.62])
    k1 = dict(b, sp=10.0, hp=3.0, hdp=16.0, hdr=-9.0, hdyaw=-4.0, hy=-0.01, syaw=6.0)
    wr = np.array([-0.15, -0.42, 1.02])
    d = unit(tgt - wr)
    put_arm(k1, "r", wr, (-0.6, 0.6, -0.4), d=d, n=unit(np.array([0.55, -0.15, -0.82])), curl=0.9, idx=0.0, thb=0.7)
    k2 = dict(k1, hdr=-11.0, hdp=18.0)
    put_arm(k2, "r", wr + np.array([0.0, -0.02, -0.01]), (-0.6, 0.6, -0.4), d=d,
            n=unit(np.array([0.55, -0.15, -0.82])), curl=0.9, idx=0.0, thb=0.7)
    k3 = dict(b, sp=4.0, hdp=6.0)
    fk_arm(k3, "r", fwd=14.0, elb=24.0, curl=0.5)
    keys = [(0.0, b), (0.55, k1), (1.0, k2), (1.4, k3)]
    params = [keyed2(keys, t) for t in frames(sec)]
    return dict(params=params, contacts=standing_contacts(params), extra=dict(markers={"point": 0.55}))


def talk_params(t, sec, p0, seated=False):
    p = dict(p0)
    br = per(t, sec, 2)
    p["sp"] = p0["sp"] + 1.0 * br
    p["hdp"] = p0["hdp"] + 3.0 * per(t, sec, 3, 0.1) - 2.0
    p["hdr"] = 4.0 * per(t, sec, 1, 0.35)
    p["hdyaw"] = 9.0 * per(t, sec, 1, 0.15)
    p["syaw"] = p0["syaw"] + 4.0 * per(t, sec, 1, 0.1)
    if not seated:
        p["hx"] = 0.015 * per(t, sec, 1, 0.5)
        p["hr"] = -1.2 * per(t, sec, 1, 0.5)
    return p


def talk_gestures(p0, seated):
    """Gesture keys (right hand leads, left answers) over 3 s, starting/ending in the rest pose."""
    zc = 1.07 if not seated else 0.92
    yc = -0.26 if not seated else -0.25
    hy = p0["hy"]
    a = dict(p0)
    put_arm(a, "r", (-0.20, hy + yc, zc), (-0.7, 0.5, -0.5), d=(0.25, -0.95, 0.15), n=(0.55, 0.0, 0.83),
            curl=0.2, thb=0.15)
    bt = dict(a)
    put_arm(bt, "r", (-0.19, hy + yc - 0.02, zc - 0.05), (-0.7, 0.5, -0.5), d=(0.2, -0.95, 0.0),
            n=(0.55, 0.0, 0.83), curl=0.28, thb=0.2)
    op = dict(bt)
    put_arm(op, "r", (-0.30, hy + yc + 0.02, zc + 0.02), (-0.7, 0.5, -0.5), d=(-0.35, -0.9, 0.2),
            n=(0.4, -0.2, 0.9), curl=0.15, thb=0.1)
    put_arm(op, "l", (0.19, hy + yc + 0.02, zc - 0.04), (0.7, 0.5, -0.5), d=(-0.2, -0.95, 0.1),
            n=(-0.55, 0.0, 0.83), curl=0.25, thb=0.15)
    l2 = dict(op)
    put_arm(l2, "l", (0.24, hy + yc, zc), (0.7, 0.5, -0.5), d=(0.2, -0.95, 0.2), n=(-0.45, -0.1, 0.88),
            curl=0.18, thb=0.1)
    fk_or = dict(p0)
    keys = [(0.0, p0), (0.45, a), (0.8, bt), (1.05, a), (1.45, op), (1.9, l2), (2.35, dict(l2)), (3.0, fk_or)]
    if not seated:
        for i, (t, k) in enumerate(keys[1:-1]):
            if k["l_ik"] is None:
                k = dict(k)
                fk_arm(k, "l", fwd=10.0, elb=24.0)
                keys[i + 1] = (t, k)
    return keys


def clip_talk():
    sec = 3.0
    p0 = base()
    fk_arm(p0, "l", fwd=6.0, elb=16.0, curl=0.35)
    fk_arm(p0, "r", fwd=6.0, elb=16.0, curl=0.35)
    keys = talk_gestures(p0, False)
    params = [talk_params(t, sec, keyed2(keys, t)) for t in frames(sec)]
    return dict(params=params, contacts=standing_contacts(params), extra=dict(markers={"beat": 0.8}))


def clip_talk_seated():
    sec = 3.0
    p0 = sit_pose(0.35)
    keys = talk_gestures(p0, True)
    params = [talk_params(t, sec, keyed2(keys, t), seated=True) for t in frames(sec)]
    return dict(params=params, contacts=standing_contacts(params), extra=dict(markers={"beat": 0.8}))


HOOK = np.array([-0.10, -0.25, 1.95])
LANTERN_HAND = np.array([-0.33, -0.07, 0.94])


def lantern_arm(p, wrist, curl=0.88):
    put_arm(p, "r", wrist, (-0.55, 0.65, -0.4), d=(0.12, -0.08, -1.0), n=(1.0, 0.0, 0.1), curl=curl, thb=0.7,
            ftw=0.5)
    return p


def clip_take_lantern():
    sec = 2.4
    b = base()
    look = dict(b, hdp=-26.0, np_=-10.0, sp=-2.0)
    reach = dict(look, sp=-6.0, syaw=8.0, hdp=-30.0, hy=-0.02, r_clav=14.0, r_clavf=-6.0)
    grip = HOOK + np.array([0.0, 0.0, -0.05])
    put_arm(reach, "r", grip + np.array([0.0, 0.03, -0.065]), (-0.85, -0.2, -0.45), d=(0.0, -0.25, 0.97),
            n=(0.9, -0.2, 0.0), curl=0.35, thb=0.3)
    reach["hz"] = 0.028
    for s in "lr":
        reach[f"{s}_fp"] = 14.0
        reach[f"{s}_toe"] = -14.0
    grab = dict(reach)
    put_arm(grab, "r", grip + np.array([0.0, 0.03, -0.075]), (-0.85, -0.2, -0.45), d=(0.0, -0.25, 0.97),
            n=(0.9, -0.2, 0.0), curl=0.85, thb=0.7)
    off = dict(grab)
    put_arm(off, "r", grip + np.array([0.0, 0.07, -0.02]), (-0.85, -0.1, -0.5), d=(0.0, -0.15, 0.98),
            n=(0.95, -0.1, 0.0), curl=0.88, thb=0.7)
    mid = dict(b, hdp=8.0, np_=2.0, hdyaw=-12.0, sp=4.0)
    put_arm(mid, "r", np.array([-0.30, -0.22, 1.20]), (-0.6, 0.6, -0.5), d=(0.1, -0.5, -0.86), n=(1.0, 0.0, 0.0),
            hw=0.35, curl=0.88, thb=0.7)
    down = dict(b, hdp=6.0, hdyaw=-14.0, sp=2.0, sr=2.0)
    lantern_arm(down, LANTERN_HAND + np.array([0.0, 0.0, -0.01]))
    end = dict(b, hdp=-2.0, sp=3.0, sr=2.5)
    lantern_arm(end, LANTERN_HAND)
    keys = [(0.0, b), (0.32, look), (0.86, reach), (1.0, grab), (1.28, off), (1.66, mid), (2.0, down), (2.4, end)]
    params = [keyed2(keys, t) for t in frames(sec)]
    # heels rise with the reach: ball pivot keeps the toes planted
    for p in params:
        for s, S, sx in SIDES:
            F = FootPlan(S, x=cx.ank[S][0] + p[f"{s}_fx"], y=cx.ank[S][1] + p[f"{s}_fy"] - 0.0, pitch=p[f"{s}_fp"])
            ank, pit, yaw, toe, _ = F.at(0.0)
            q = ank - cx.ank[S]
            p[f"{s}_fz"] = q[2]
            p[f"{s}_fy"] = q[1]
            p[f"{s}_fx"] = q[0]
    contacts = [{S: (True, None, "ball") for S in ("Left", "Right")} for _ in params]
    return dict(params=params, contacts=contacts,
                extra=dict(markers={"grab": 1.0, "down": 2.0},
                           propPoints={"hook_m": [round(float(HOOK[0]), 3), round(float(HOOK[2]), 3),
                                                  round(float(-HOOK[1]), 3)]}))


def lantern_walk_upper(t, p):
    T = 1.0
    walk_upper(p, t, T, 0.61, lean=5.0, bob=0.020, sway=0.018, pyaw=5.0, cyaw=4.0, roll=2.0, arm=0.0)
    w = 2 * math.pi * t / T
    p["hdp"] += 2.0
    p["sr"] += 2.5
    c = -math.cos(w - 0.25)             # left arm swing (+ forward)
    fk_arm(p, "l", fwd=4.0 + 20.0 * c, elb=14.0 + 12.0 * max(0.0, c), curl=0.4)
    wl = LANTERN_HAND + np.array([0.0, -0.025 * math.cos(w - 0.25), 0.008 * math.cos(2 * w)])
    lantern_arm(p, wl)
    return p


def clip_walk_lantern():
    T, v = 1.0, 1.4
    params, contacts = loco(T, v, dict(beta=0.61, lift=0.09, step_w=0.10, heel=14.0, toeoff=30.0),
                            lantern_walk_upper)
    return dict(params=params, contacts=contacts, speed=v,
                extra=dict(groundSpeed_mps=v, strideLength_m=round(v * T, 4),
                           markers={"step_l": 0.0, "step_r": round(T / 2, 4)}))


def clip_look_around():
    sec = 2.4
    b = base()
    tense = dict(b, hz=-0.02, sp=4.0, l_clav=5.0, r_clav=5.0)
    fk_arm(tense, "l", fwd=10.0, add=4.0, elb=34.0, curl=0.55)
    fk_arm(tense, "r", fwd=10.0, add=4.0, elb=34.0, curl=0.55)
    lft = dict(tense, hdyaw=52.0, nyaw=14.0, syaw=14.0, hyaw=5.0, hx=0.02, hr=-1.5, hdp=-4.0)
    rgt = dict(tense, hdyaw=-54.0, nyaw=-14.0, syaw=-14.0, hyaw=-5.0, hx=-0.02, hr=1.5, hdp=-2.0)
    keys = [(0.0, b), (0.22, tense), (0.62, lft), (0.9, dict(lft, hdyaw=46.0)), (1.5, rgt),
            (1.78, dict(rgt, hdyaw=-48.0)), (2.15, dict(tense, hdyaw=4.0)), (2.4, dict(tense))]
    params = [keyed2(keys, t) for t in frames(sec)]
    return dict(params=params, contacts=standing_contacts(params), extra=dict(markers={"look_left": 0.62,
                                                                                         "look_right": 1.5}))


CLIPS = [
    ("lf_story_run", RUN_T, True, clip_run),
    ("lf_story_halt", 0.9, False, clip_halt),
    ("lf_story_backstep", 1.2, True, clip_backstep),
    ("lf_story_collapse", 1.4, False, clip_collapse),
    ("lf_story_collapse_hold", 3.2, True, clip_collapse_hold),
    ("lf_story_support", 1.4, False, clip_support),
    ("lf_story_support_hold", 3.2, True, clip_support_hold),
    ("lf_story_latch_reach", 3.0, False, clip_latch_reach),
    ("lf_story_squeeze", 1.6, False, clip_squeeze),
    ("lf_story_sneak", SNEAK_T, True, clip_sneak),
    ("lf_story_hide", 1.0, False, clip_hide),
    ("lf_story_hide_hold", 3.0, True, clip_hide_hold),
    ("lf_story_peek", 2.2, False, clip_peek),
    ("lf_story_stumble", 1.2, False, clip_stumble),
    ("lf_story_catch", 1.2, False, clip_catch),
    ("lf_story_sit", 4.0, True, clip_sit),
    ("lf_story_sit_down", 1.4, False, clip_sit_down),
    ("lf_story_guide_sit", 1.6, False, clip_guide_sit),
    ("lf_story_carry_cup", 1.1, True, clip_carry_cup),
    ("lf_story_offer", 1.4, False, clip_offer),
    ("lf_story_drink", 4.0, True, clip_drink),
    ("lf_story_show_wrist", 1.6, False, clip_show_wrist),
    ("lf_story_point_low", 1.4, False, clip_point_low),
    ("lf_story_talk", 3.0, True, clip_talk),
    ("lf_story_talk_seated", 3.0, True, clip_talk_seated),
    ("lf_story_take_lantern", 2.4, False, clip_take_lantern),
    ("lf_story_walk_lantern", 1.0, True, clip_walk_lantern),
    ("lf_story_look_around", 2.4, False, clip_look_around),
]


# --------------------------------------------------------------------------- bake + QA

class Skin:
    """numpy linear-blend skinning of the display body (for ground / seat checks)."""

    def __init__(self, obj, sk):
        me = obj.data
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        self.V = np.c_[co.reshape(-1, 3), np.ones(len(me.vertices))]
        names = [g.name for g in obj.vertex_groups]
        self.bones = [n for n in names if n in sk.R]
        bi = {n: i for i, n in enumerate(self.bones)}
        self.idx = np.zeros((len(self.V), 4), int)
        self.w = np.zeros((len(self.V), 4))
        for v in me.vertices:
            gs = sorted(((g.weight, names[g.group]) for g in v.groups if names[g.group] in bi), reverse=True)[:4]
            tot = sum(w for w, _ in gs) or 1.0
            for k, (w, n) in enumerate(gs):
                self.idx[v.index, k] = bi[n]
                self.w[v.index, k] = w / tot
        self.dom = np.array([self.bones[i] for i in self.idx[:, 0]])
        self.inv = np.stack([np.linalg.inv(sk.R[n]) for n in self.bones])
        self.by_bone = {n: np.where(self.dom == n)[0] for n in set(self.dom)}

    def pose(self, M, sel=None):
        S = np.stack([M[n] for n in self.bones]) @ self.inv
        idx = self.idx if sel is None else self.idx[sel]
        w = self.w if sel is None else self.w[sel]
        V = self.V if sel is None else self.V[sel]
        out = np.zeros((len(V), 3))
        for k in range(4):
            out += w[:, k:k + 1] * np.einsum("vij,vj->vi", S[idx[:, k]], V)[:, :3]
        return out


def swing_twist(Ra, Rb):
    """Rotation of frame Rb relative to Ra (both world 3x3) split into swing (deg) and twist about the
    bone's own Y axis (deg)."""
    q = A.matq(Ra.T @ Rb)                     # (w, x, y, z)
    tw = 2.0 * math.atan2(q[2], q[0])
    tw = (tw + math.pi) % (2 * math.pi) - math.pi
    Rs = (Ra.T @ Rb) @ rot(np.array([0, 1.0, 0]), -tw)
    sw = math.acos(np.clip((np.trace(Rs) - 1) / 2, -1, 1))
    return math.degrees(sw), math.degrees(tw)


def wrist_metrics(M):
    """(bend, twist) of each wrist relative to a hand rigidly following its forearm."""
    return [swing_twist(M[f"{S}LowerArm"][:3, :3] @ REL[S], M[f"{S}Hand"][:3, :3]) for S in ("Left", "Right")]


def elbow_twist(M):
    out = []
    for S in ("Left", "Right"):
        rel0 = cx.sk.R[f"{S}UpperArm"][:3, :3].T @ cx.sk.R[f"{S}LowerArm"][:3, :3]
        out.append(swing_twist(M[f"{S}UpperArm"][:3, :3] @ rel0, M[f"{S}LowerArm"][:3, :3])[1])
    return out


def _lag(x, a, loop):
    if loop:
        reps = np.concatenate([x, x, x])
        y = np.zeros_like(reps)
        y[0] = reps[0]
        for i in range(1, len(reps)):
            y[i] = y[i - 1] + a * (reps[i] - y[i - 1])
        return y[len(x):2 * len(x)]
    y = np.zeros_like(x)
    y[0] = x[0]
    for i in range(1, len(x)):
        y[i] = y[i - 1] + a * (x[i] - y[i - 1])
    return y


def cloth_secondary(Ms, loop):
    """Cloth bones from the solved poses, angles measured in the pelvis frame (so kneeling / seated
    flexion is bounded): front panels follow the forward-most thigh and the lower front panel hangs
    over the knee once the thigh passes ~25 deg; back panels follow the rear-most thigh; side panels
    follow abduction (asin, bounded) plus a little flexion; cloak/hood lag the torso; bag swings."""
    sk = cx.sk
    n = len(Ms)
    R0 = sk.R["Hips"][:3, :3]
    flex = {S: np.zeros(n) for S in ("Left", "Right")}
    abd = {S: np.zeros(n) for S in ("Left", "Right")}
    tor = np.zeros(n)
    hipz = np.zeros(n)
    rest = {}
    for S, sx in (("Left", 1.0), ("Right", -1.0)):
        d0 = unit(sk.head(f"{S}LowerLeg") - sk.head(f"{S}UpperLeg"))
        dl = R0.T @ d0
        rest[S] = (math.atan2(dl[2], -dl[1]), math.asin(np.clip(dl[0] * sx, -1, 1)))
    for i, M in enumerate(Ms):
        Rh = M["Hips"][:3, :3]
        for S, sx in (("Left", 1.0), ("Right", -1.0)):
            d = unit(M[f"{S}LowerLeg"][:3, 3] - M[f"{S}UpperLeg"][:3, 3])
            dl = Rh.T @ d
            flex[S][i] = math.atan2(dl[2], -dl[1]) - rest[S][0]
            abd[S][i] = math.asin(np.clip(dl[0] * sx, -1, 1)) - rest[S][1]
        up = M["UpperChest"][:3, 1]
        tor[i] = math.atan2(-up[1], up[2])
        hipz[i] = M["Hips"][2, 3]
    D = math.radians
    front = np.clip(np.maximum(np.maximum(flex["Left"], flex["Right"]), 0), 0, D(100))
    back = np.clip(np.maximum(np.maximum(-flex["Left"], -flex["Right"]), 0), 0, D(45))
    f1 = _lag(front, 0.45, loop) * 0.85
    f2 = _lag(front, 0.25, loop) * 0.10 - 1.15 * np.maximum(f1 - D(15), 0)
    b1 = _lag(back, 0.45, loop) * 0.8
    b2 = _lag(back, 0.25, loop) * 0.25
    out = []
    acc = np.gradient(np.gradient(hipz)) * FPS * FPS
    bag = _lag(np.clip(acc * 0.004, -0.4, 0.4), 0.2, loop)
    tl = _lag(tor, 0.2, loop) - tor
    side = {}
    for S in ("Left", "Right"):
        side[S] = (_lag(np.clip(abd[S], 0, D(40)), 0.4, loop) * 0.8,
                   np.clip(np.maximum(flex[S], 0), 0, D(60)) * 0.35)
    for i in range(n):
        R = {}
        R["SkirtFront1"] = rot(A.X, -f1[i])
        R["SkirtFront2"] = rot(A.X, -f2[i])
        R["SkirtBack1"] = rot(A.X, b1[i])
        R["SkirtBack2"] = rot(A.X, b2[i])
        R["SkirtLeft"] = rot(A.X, -side["Left"][1][i]) @ rot(A.Y, -side["Left"][0][i])
        R["SkirtRight"] = rot(A.X, -side["Right"][1][i]) @ rot(A.Y, side["Right"][0][i])
        R["Cloak1"] = rot(A.X, -0.6 * tl[i] - 0.12 * b1[i])
        R["Cloak2"] = rot(A.X, -0.8 * tl[i] - 0.15 * b1[i])
        R["Hood"] = rot(A.X, -0.5 * tl[i])
        R["Bag"] = rot(A.X, bag[i])
        out.append(R)
    return out


CLOTH_ORDER = ("SkirtFront1", "SkirtBack1", "SkirtLeft", "SkirtRight", "Cloak1", "SkirtFront2", "SkirtBack2",
               "Cloak2")


def cloth_clamp(P, MM, skin, seated, tol=0.0):
    """Swing cloth bones up (about r x up through the bone head) until every vertex they dominate is
    above the ground (and above the bench top behind the root in seated clips, soft front edge)."""
    up = np.array([0, 0, 1.0])
    for bn in CLOTH_ORDER:
        idx = skin.by_bone.get(bn)
        if idx is None or not len(idx):
            continue
        for _ in range(10):
            V = skin.pose(MM, idx)
            fl = np.zeros(len(V))
            if seated:
                over = (np.abs(V[:, 0]) < 0.45) & (V[:, 1] < SEAT_Y + 0.19)
                fl[over] = SEAT_H * smooth((V[over, 1] - (SEAT_Y - 0.17)) / 0.10)
            pen = fl + 0.012 - tol - V[:, 2]
            j = int(np.argmax(pen))
            if pen[j] <= 0:
                break
            head = MM[bn][:3, 3]
            r = V[j] - head
            ax = np.cross(r, up)
            h = np.linalg.norm(ax)
            if h < 1e-4:
                break
            ang = min(math.radians(25), pen[j] / max(h, 0.05) * 1.15 + math.radians(0.5))
            par = cx.sk.parent[bn]
            Prot = MM[par][:3, :3] @ cx.sk.R[par][:3, :3].T
            Dw = rot(ax / h, ang)
            P.rot[bn] = Prot.T @ Dw @ Prot @ P.rot.get(bn, np.eye(3))
            MM = A.solve(cx.sk, P)[1]
    return MM


def smooth_cloth(poses, loop, sigma=2.2):
    """Gaussian-smooth the cloth bones' rotations over time (removes single-frame clamp pops)."""
    for bn in CLOTH_ORDER + ("Hood", "Bag"):
        qs = np.array([A.matq(P.rot.get(bn, np.eye(3))) for P in poses])
        for i in range(1, len(qs)):
            if qs[i] @ qs[i - 1] < 0:
                qs[i] = -qs[i]
        qs = gaussian_filter1d(qs, sigma, axis=0, mode="wrap" if loop else "nearest")
        for P, q in zip(poses, qs):
            P.rot[bn] = np.array(Quaternion(unit(q)).to_matrix())


def slip_mm(Ms, contacts, rootf):
    res = {}
    for S in ("Left", "Right"):
        heel_l = np.linalg.inv(cx.sk.R[f"{S}Foot"]) @ np.append(cx.heel[S], 1.0)
        ball_g = np.array([cx.ball[S][0], cx.ball[S][1], 0.0])
        ball_l = np.linalg.inv(cx.sk.R[f"{S}Foot"]) @ np.append(ball_g, 1.0)
        segs, cur, kind = [], [], None
        for i, (M, c) in enumerate(zip(Ms, contacts)):
            planted, _, k = c.get(S, (False, None, None))
            if planted:
                r3 = tuple(rootf(i / FPS)) + (0.0,)
                pt = (M[f"{S}Foot"] @ (heel_l if k in ("heel", "flat") else ball_l))[:3] + np.array(r3[:3])
                if k != kind and cur:
                    segs.append(cur)
                    cur = []
                kind = k
                cur.append(pt[:2])
            elif cur:
                segs.append(cur)
                cur, kind = [], None
        if cur:
            segs.append(cur)
        res[S] = round(max([float(np.linalg.norm(np.array(s_) - s_[0], axis=1).max()) for s_ in segs] or [0.0])
                       * 1000.0, 2)
    return res


def bake(arm, skin, name, sec, loop, R):
    params, contacts, extra = R["params"], R["contacts"], R.get("extra", {})
    times = frames(sec)
    assert len(params) == len(times), (name, len(params), len(times))
    A.OVERREACH[0] = 0.0
    poses = [make_pose2(p) for p in params]
    Ms = [A.solve(cx.sk, P)[1] for P in poses]
    over = max(A.OVERREACH[0], 0.0)
    sec_rots = cloth_secondary(Ms, loop)
    frames_basis, final_M = [], []
    seated = R.get("seated", False)
    # cloth clamp, warm-started from the previous frame's correction (decaying) so the solution stays
    # on one branch from frame to frame; loops run twice so the first frame is warm too
    poses2 = []
    prev = {}
    for it in range(2 if loop else 1):
        poses2 = []
        for p, extra_r in zip(params, sec_rots):
            P = make_pose2(p)
            for bn, Rr in extra_r.items():
                P.rot[bn] = Rr
            for bn, Dp in prev.items():
                P.rot[bn] = slerp_m(np.eye(3), Dp, 0.85) @ P.rot[bn]
            MM = A.solve(cx.sk, P)[1]
            cloth_clamp(P, MM, skin, seated)
            prev = {bn: P.rot[bn] @ extra_r[bn].T for bn in CLOTH_ORDER if bn in extra_r}
            poses2.append(P)
    smooth_cloth(poses2, loop, sigma=0.8)
    for P in poses2:
        bb, MM = A.solve(cx.sk, P)
        frames_basis.append(bb)
        final_M.append(MM)
    if loop:
        frames_basis[-1] = frames_basis[0]
        final_M[-1] = final_M[0]
    FIN.write_action(arm, name, frames_basis, times, loop)
    speed = float(R.get("speed", 0.0))
    rootf = R.get("root") or (lambda t: (0.0, -speed * t))
    m = {"seconds": round(float(sec), 4), "loop": bool(loop), "frames": len(times), "rootTranslation": "in_place"}
    for k in ("groundSpeed_mps", "strideLength_m"):
        if k in extra:
            m[k] = extra[k]
    m["markers"] = extra.get("markers", {})
    for k, v in extra.items():
        if k not in m and k not in ("markers",):
            m[k] = v
    m["footSlip_mm"] = slip_mm(final_M, contacts, rootf)
    m["ikOverreach_m"] = round(over, 4)
    if loop:
        q0 = np.concatenate([frames_basis[0][n][1] for n in sorted(frames_basis[0])])
        q1 = np.concatenate([frames_basis[-1][n][1] for n in sorted(frames_basis[-1])])
        m["loopSeamMaxQuatDiff"] = float(np.abs(q0 - q1).max())
    # ---- QA numbers (not exported to the meta)
    qa = {}
    wm = np.array([wrist_metrics(M) for M in final_M])          # frames x side x (bend, twist)
    et = np.array([elbow_twist(M) for M in final_M])
    qa["wristBendMax_deg"] = [round(float(wm[:, i, 0].max()), 1) for i in range(2)]
    qa["wristTwistMax_deg"] = [round(float(np.abs(wm[:, i, 1]).max()), 1) for i in range(2)]
    qa["elbowTwistMax_deg"] = [round(float(np.abs(et[:, i]).max()), 1) for i in range(2)]
    zmin, zbody, seat = 9.0, 9.0, None
    feetb = ("LeftFoot", "LeftToes", "RightFoot", "RightToes")
    nf = ~np.isin(skin.dom, feetb)
    where_f, where_b = "", ""
    for i, M in enumerate(final_M):
        V = skin.pose(M)
        j = int(np.argmin(V[:, 2]))
        if V[j, 2] < zmin:
            zmin, where_f = float(V[j, 2]), f"{skin.dom[j]}@{i / FPS:.2f}"
        jb = int(np.argmin(np.where(nf, V[:, 2], 9.0)))
        if V[jb, 2] < zbody:
            zbody, where_b = float(V[jb, 2]), f"{skin.dom[jb]}@{i / FPS:.2f}"
    qa["meshMinZ_m"] = [round(zmin, 4), where_f]
    qa["meshMinZ_nonFeet_m"] = [round(zbody, 4), where_b]
    if name in ("lf_story_sit", "lf_story_drink", "lf_story_talk_seated", "lf_story_show_wrist"):
        V = skin.pose(final_M[0])
        sel = np.isin(skin.dom, ("Hips", "LeftUpperLeg", "RightUpperLeg")) & (V[:, 1] > SEAT_Y - 0.12)
        qa["seatBottom_m"] = round(float(V[sel, 2].min()), 4)
    # popping: max angular speed of any deform bone (deg / frame)
    vmax, vb = 0.0, ""
    for i in range(1, len(frames_basis)):
        for n, (loc, q, sc) in frames_basis[i].items():
            q0 = frames_basis[i - 1][n][1]
            ang = 2 * math.degrees(math.acos(min(1.0, abs(float(np.dot(q, q0))))))
            if ang > vmax:
                vmax, vb = ang, n
    qa["maxBoneSpeed_degPerFrame"] = [round(vmax, 1), vb]
    lean = [math.degrees(math.atan2(-(M["Neck"][1, 3] - M["Hips"][1, 3]), M["Neck"][2, 3] - M["Hips"][2, 3]))
            for M in final_M]
    qa["trunkLean_deg"] = [round(float(np.mean(lean)), 1), round(float(np.min(lean)), 1), round(float(np.max(lean)), 1)]
    end = final_M[-1]
    hips = end["Hips"][:3, 3]
    m["endOffset_m"] = [round(float(hips[0]), 3), 0.0, round(float(-(hips[1] - cx.sk.head("Hips")[1])), 3)]
    return m, qa, frames_basis, final_M


# --------------------------------------------------------------------------- Blender preview sheets

SEATED = ("lf_story_sit", "lf_story_sit_down", "lf_story_drink", "lf_story_show_wrist", "lf_story_talk_seated")
CUP_CLIPS = ("lf_story_carry_cup", "lf_story_offer", "lf_story_drink")
LANTERN_CLIPS = ("lf_story_take_lantern", "lf_story_walk_lantern")


def _mesh_obj(name, bm, color):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1.0)
    me.materials.append(m)
    bpy.context.scene.collection.objects.link(o)
    return o


def _box(name, size, loc, color):
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    bmesh.ops.translate(bm, vec=loc, verts=bm.verts)
    return _mesh_obj(name, bm, color)


def _cyl(name, r, h, color, r2=None):
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=r, radius2=r if r2 is None else r2, depth=h)
    return _mesh_obj(name, bm, color)


def apply_basis(arm, fb):
    for n, (loc, q, sc) in fb.items():
        pb = arm.pose.bones.get(n)
        if pb is None:
            continue
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
        pb.location = tuple(float(x) for x in loc)
        pb.scale = (float(sc),) * 3
    bpy.context.view_layer.update()


CAGE_GLB = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "props", "lf_cage_wood.glb")
CAGE_CLIPS = ("lf_story_latch_reach", "lf_story_squeeze")
ROOTS = {}


def cage_door_at(name, t):
    """Door yaw (deg) the story shows under each clip frame (story_intro.gd timing)."""
    if name == "lf_story_latch_reach":
        return door_angle(DOOR_RATE * (t - DOOR_T0)) if t > DOOR_T0 else 0.0
    if name == "lf_story_squeeze":
        return door_angle(0.55)
    return 0.0


CAGE_OBJS = []


def import_cage():
    """lf_cage_wood (LOD0 + default sockets) at the origin, for previews and the bar-penetration check."""
    if CAGE_OBJS:
        return CAGE_OBJS
    before = set(bpy.data.objects)
    acts_before = set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=CAGE_GLB)
    new = [o for o in bpy.data.objects if o not in before]
    for a in list(bpy.data.actions):
        if a not in acts_before:
            bpy.data.actions.remove(a)
    for o in new:
        if o.animation_data:
            o.animation_data.action = None
        if o.type == "MESH" and (o.name.endswith(("_LOD1", "_LOD2")) or any(
                k in o.name for k in ("amber_crystal", "bone_key", "bronze_seal"))):
            o.hide_render = True
    keep = [o for o in new if o.type == "MESH" and not o.hide_render]
    for o in keep:
        o.select_set(False)
    CAGE_OBJS.extend(keep)
    return keep


def cage_check(baked, skin):
    """Bar / door / jamb penetration of the skinned body in the cage clips: every frame, the door posed as the
    story shows it, each body vertex tested against the nearest cage face (inside = behind its normal)."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    objs = import_cage()
    dg = bpy.context.evaluated_depsgraph_get()
    door_names = ("door_pivot", "latch_pivot", "socket_stone_rune")
    stat_v, stat_f, door_v, door_f = [], [], [], []
    for o in objs:
        me = o.evaluated_get(dg).to_mesh()
        M = o.matrix_world
        vs = [np.array(M @ v.co) for v in me.vertices]
        fs = [list(pp.vertices) for pp in me.polygons]
        tgt_v, tgt_f = (door_v, door_f) if any(k in o.name for k in door_names) else (stat_v, stat_f)
        b0 = len(tgt_v)
        tgt_v += vs
        tgt_f += [[b0 + i for i in f] for f in fs]
    stat = BVHTree.FromPolygons([Vector(v) for v in stat_v], stat_f)
    door_v = np.array(door_v)
    out = {}
    for name in CAGE_CLIPS:
        if name not in baked:
            continue
        fb, Ms, sec, loop = baked[name]
        rootf = ROOTS.get(name, lambda t: (0.0, 0.0))
        worst, worst_at, counts, by_bone = 0.0, "", [], {}
        for i, M in enumerate(Ms):
            t = i / FPS
            ang = cage_door_at(name, t)
            dv = [Vector(door_rot(v, ang)) for v in door_v]
            door = BVHTree.FromPolygons(dv, door_f)
            V = skin.pose(M) + CAGE_ROOT + np.array((tuple(rootf(t)) + (0.0,))[:3])
            n_in = 0
            for j in np.where(V[:, 1] < -1.0)[0]:
                v = Vector(V[j])
                for tr in (stat, door):
                    loc, nrm, _, dist = tr.find_nearest(v, 0.06)
                    if loc is not None and (v - loc).dot(nrm) < -0.003:
                        n_in += 1
                        by_bone[skin.dom[j]] = max(by_bone.get(skin.dom[j], 0.0), dist)
                        if dist > worst:
                            worst, worst_at = dist, f"{skin.dom[j]}@{t:.2f}"
                        break
            counts.append(n_in)
        out[name] = {"maxVertsInsideCage": int(max(counts)), "framesWithPenetration": int(sum(c > 0 for c in counts)),
                     "deepest_m": round(worst, 4), "deepestAt": worst_at,
                     "deepestByBone_m": {k: round(v, 4) for k, v in sorted(by_bone.items(), key=lambda kv: -kv[1])}}
        log("cage check", name, out[name])
    return out


def preview(arm, lod0, baked, names, cols=6):
    from PIL import Image, ImageDraw
    from mathutils import Vector
    out_dir = os.path.join(QA_DIR, "preview")
    os.makedirs(out_dir, exist_ok=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE"
    sh.show_shadows = False
    sh.show_cavity = True
    sc.render.film_transparent = False
    sc.world = bpy.data.worlds.new("pw")
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 300, 400, 100
    sc.render.image_settings.file_format = "PNG"
    ground = _box("qa_ground", (8, 8, 0.01), (0, 0, -0.005), (0.40, 0.42, 0.30))
    scen = {
        "bench": [_box("qa_bench", (0.9, 0.34, SEAT_H), (0, SEAT_Y + 0.02, SEAT_H / 2), (0.45, 0.30, 0.18))],
        "wall": [_box("qa_wall", (0.12, 0.04, 2.4), (HOOK[0], HOOK[1] - 0.06, 1.2), (0.62, 0.58, 0.5)),
                 _box("qa_hook", (0.02, 0.10, 0.02), tuple(HOOK + np.array([0, -0.03, 0])), (0.2, 0.2, 0.2))],
    }
    scen["cage"] = import_cage()
    door = bpy.data.objects.get("door_pivot")
    door_rest = door.matrix_basis.copy() if door else None
    cup = _cyl("qa_cup", 0.042, 0.095, (0.85, 0.85, 0.9), r2=0.036)
    lant = _cyl("qa_lantern", 0.065, 0.20, (0.95, 0.75, 0.25), r2=0.05)
    # props ride on PropR: place them once in a reference frame, then they follow the hand
    for prop, ref, world in ((cup, "lf_story_carry_cup", None), (lant, "lf_story_walk_lantern", None)):
        if ref not in baked:
            prop.hide_render = True
            continue
        apply_basis(arm, baked[ref][0][0])
        g = np.array(arm.matrix_world @ arm.pose.bones["PropR"].head)
        if prop is cup:
            Mt = Matrix.Translation(Vector(tuple(CUP)))
        else:
            Mt = Matrix.Translation(Vector(tuple(g + np.array([0, 0, -0.15]))))
        prop.parent = arm
        prop.parent_type = "BONE"
        prop.parent_bone = "PropR"
        bpy.context.view_layer.update()
        prop.matrix_world = Mt
    cam_d = bpy.data.cameras.new("qa_cam")
    cam_d.lens = 50
    cam = bpy.data.objects.new("qa_cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    for name in names:
        fb, Ms, sec, loop = baked[name]
        for k, objs in scen.items():
            on = (k == "bench" and name in SEATED) or (k == "cage" and name in CAGE_CLIPS) or \
                 (k == "wall" and name == "lf_story_take_lantern")
            for o in objs:
                o.hide_render = not on
        cup.hide_render = name not in CUP_CLIPS
        lant.hide_render = name not in LANTERN_CLIPS
        incage = name in CAGE_CLIPS
        rootf = ROOTS.get(name, lambda t: (0.0, 0.0))
        offs = [np.array((tuple(rootf(i / FPS)) + (0.0,))[:3]) + (CAGE_ROOT if incage else 0.0)
                for i in range(len(Ms))]
        pts = np.array([M[b][:3, 3] + o for M, o in zip(Ms, offs) for b in ("Head", "LeftHand", "RightHand",
                                                                            "LeftToes", "RightToes", "Hips")])
        lo, hi = pts.min(0), pts.max(0)
        hi[2] = max(hi[2] + 0.2, 1.0)
        lo[2] = 0.0
        c = 0.5 * (lo + hi)
        hgt = max(hi[2] - lo[2], 0.9) * 1.12
        dist = (hgt / 2) / math.tan(math.atan(18 / 50)) + 0.4
        idx = np.unique(np.round(np.linspace(0, len(fb) - 1, cols)).astype(int))
        tiles = []
        for vx, vy in ((0.57, -0.82), (1.0, 0.0)):
            loc = Vector((c[0] + vx * dist, c[1] + vy * dist, c[2] + 0.18))
            cam.location = loc
            cam.rotation_euler = (Vector(tuple(c)) - loc).to_track_quat("-Z", "Y").to_euler()
            for i in idx:
                arm.location = Vector(tuple(offs[i]))
                if door is not None:
                    ang = cage_door_at(name, i / FPS)
                    door.matrix_basis = door_rest @ Matrix.Rotation(math.radians(ang), 4, "Z")
                apply_basis(arm, fb[i])
                path = os.path.join(out_dir, "_tmp.png")
                sc.render.filepath = path
                bpy.ops.render.render(write_still=True)
                im = Image.open(path).convert("RGB")
                d = ImageDraw.Draw(im)
                d.text((6, 4), f"{name[9:]} t={i / FPS:.2f}", fill=(255, 255, 255))
                tiles.append(im)
        W, H = tiles[0].size
        sheet = Image.new("RGB", (W * len(idx), H * 2))
        for j, im in enumerate(tiles):
            sheet.paste(im, ((j % len(idx)) * W, (j // len(idx)) * H))
        sheet.save(os.path.join(out_dir, f"{name}.png"))
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    arm.location = (0.0, 0.0, 0.0)
    for o in [ground, cup, lant] + [o for v in scen.values() for o in v]:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.objects.remove(cam, do_unlink=True)
    log("previews", out_dir)


def main():
    global cx, SKIN
    arm, lod0 = load_body()
    cx = make_ctx(arm, lod0)
    HC.CTX[0] = cx
    log("ctx add0", {k: round(v, 2) for k, v in cx.add0.items()}, "belly_y", round(cx.belly_y, 3), "chest_y",
        round(cx.chest_y, 3))
    skin = Skin(lod0, cx.sk)
    SKIN = skin
    only = [a for a in ARGS if a.startswith("lf_story_")]
    meta_clips, qa_all, baked = {}, {}, {}
    for name, sec, loop, fn in CLIPS:
        tc = time.time()
        _FK.clear()
        R = fn()
        R["seated"] = name in SEATED
        if only and name not in only and not ("--preview" in ARGS and name in ("lf_story_carry_cup",
                                                                               "lf_story_walk_lantern")):
            continue
        m, qa, fb, Ms = bake(arm, skin, name, sec, loop, R)
        if R.get("root"):
            ROOTS[name] = R["root"]
        if not only or name in only:
            baked[name] = (fb, Ms, sec, loop)
        elif "--preview" in ARGS:
            baked["_ref_" + name] = (fb, Ms, sec, loop)
        meta_clips[name] = m
        qa_all[name] = dict(qa, footSlip_mm=m["footSlip_mm"], ikOverreach_m=m["ikOverreach_m"])
        log(f"{name}: {sec}s loop={loop} slip={m['footSlip_mm']} over={m['ikOverreach_m']} "
            f"qa={json.dumps(qa)} ({time.time() - tc:.1f}s)")
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    if any(n in baked for n in CAGE_CLIPS):
        for nm, res in cage_check(baked, skin).items():
            qa_all[nm]["cageCheck"] = res
    if "--preview" in ARGS:
        for k in list(baked):
            if k.startswith("_ref_"):
                baked[k[5:]] = baked.pop(k)
        preview(arm, lod0, baked, [k for k in baked if not only or k in only])
    if only:
        log("partial build (clip filter): GLB/meta not written")
        return
    core.export_glb(OUT_GLB, [arm, lod0],
                    extra=dict(export_force_sampling=True, export_optimize_animation_size=False,
                               export_image_format="AUTO", export_def_bones=True,
                               export_animation_mode="ACTIONS", export_bake_animation=False, export_morph=False))
    log("GLB", OUT_GLB, os.path.getsize(OUT_GLB) // 1024, "KB")
    sk = cx.sk

    def g(v):   # Blender (x, y, z) -> glTF (x, z, -y)
        return [round(float(v[0]), 3), round(float(v[2]), 3), round(float(-v[1]), 3)]
    mins, maxs = core.bounds([lod0])
    meta = {
        "id": AID,
        "kind": "clip library",
        "rig": "human_shared",
        "displayBody": f"{SRC_AID} LOD0 (preview only, 1024 atlas)",
        "tris": {"LOD0": core.tri_count(lod0)},
        "bones": {"deform": len([b for b in arm.data.bones if b.use_deform]), "total": len(arm.data.bones)},
        "nodes": {"armature": f"{AID}_rig", "skeleton_godot": f"{AID}_rig/Skeleton3D", "animationPlayer": "AnimationPlayer",
                  "LOD0": f"{AID}_LOD0", "trackPathExample": f"{AID}_rig/Skeleton3D:Hips",
                  "retarget": f"same bone names as lf_civilian_*/lf_squad_*: replace the track prefix '{AID}_rig/' "
                              f"with '<asset_id>_rig/'"},
        "bounds_m": {"min": [round(float(x), 3) for x in mins], "max": [round(float(x), 3) for x in maxs]},
        "seat_height_m": SEAT_H,
        "seat_offset_m": [0.0, SEAT_H, -SEAT_Y],
        "clips": meta_clips,
        "sockets": {
            "hand_r": {"bone": "PropR", "parent": "RightHand", "rest_m": g(sk.head("PropR")),
                       "use": "cup (carry_cup/offer/drink, right side of the cup) and lantern (take_lantern/walk_lantern)"},
            "hand_l": {"bone": "PropL", "parent": "LeftHand", "rest_m": g(sk.head("PropL")),
                       "use": "second hand on the cup"},
        },
        "coordinateConvention": {"up": "+Y", "forward": "+Z", "unit": "metre",
                                 "note": "root at the origin, feet on y=0; Blender -Y forward exported to glTF +Z"},
        "notes": (
            "Story-cutscene clips on human_shared (bone names/rolls identical to every lf_civilian_*/lf_squad_* GLB, "
            "so Godot tracks differ only by the '<asset>_rig/' prefix). 30 fps; loops have identical first/last "
            "frames. Locomotion loops are in place with planted feet sliding back at exactly groundSpeed_mps "
            "(backstep: negative = walking backwards). Travel one-shots (halt, squeeze, stumble) are in place: move "
            "the node along rootPath_m (metres travelled, every 0.1 s) and the planted feet stay put. Acting one-shots "
            "with a short step (support, collapse, catch, hide, offer) keep the root still and end with the body "
            "displaced by endOffset_m; their *_hold loops keep that offset. Seated clips (sit, sit_down end, drink, "
            "show_wrist, talk_seated) assume a 0.45 m seat with the hips 0.36 m behind the root (seat_offset_m). "
            "Props: parent cup/lantern to PropR (hand_r, grip point in the right fist); the left hand (PropL) wraps "
            "the cup's other side. halt starts on lf_story_run frame 0; stumble starts on lf_civilian_follow_tired "
            "frame 0; hide_hold/peek and collapse_hold/support_hold continue their one-shots. Cloth bones (skirt, "
            "cloak, hood, bag) carry thigh-follow secondary motion. Display body = miller LOD0 only."),
    }
    core.write_json(OUT_META, meta)
    os.makedirs(QA_DIR, exist_ok=True)
    core.write_json(os.path.join(QA_DIR, "metrics.json"), qa_all)
    log("meta", OUT_META)


if __name__ == "__main__":
    main()
