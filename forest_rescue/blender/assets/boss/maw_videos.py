"""Clip review videos for the Ancient Maw: side view (with simulated client root motion over a 1 m grid)
and the high strategic game camera (50.4 deg tilt, 43 deg FOV, 45 m) with QA-only attack-zone overlays,
plus contact sheets and a numeric foot-slide report.
"""
import math
import os
import shutil
import subprocess
import tempfile

import bpy
import numpy as np
from mathutils import Matrix, Vector

import maw_anim as A
import maw_common as C
from frlib import core, render
from maw_pose import Poser

AID = C.ASSET_ID
GAME_TILT = 0.88
GAME_FOV = 43.0


def client_root(cid, t):
    """(offset Vector, yaw deg) the game client applies to the actor root at clip time t."""
    if cid == "lf_boss_walk":
        return Vector((0, -A.WALK_SPEED * t, 0)), 0.0
    if cid == "lf_boss_turn_left":
        return Vector((0, 0, 0)), 90.0 * A.ss(t / 1.3)
    if cid == "lf_boss_turn_right":
        return Vector((0, 0, 0)), -90.0 * A.ss(t / 1.3)
    if cid == "lf_boss_lane_charge":
        return Vector((0, -A.charge_d(t), 0)), 0.0
    return Vector((0, 0, 0)), 0.0


def grid_image(size=512):
    img = bpy.data.images.get("qa_grid") or bpy.data.images.new("qa_grid", size, size)
    a = np.full((size, size, 4), 1.0)
    a[..., :3] = (0.50, 0.47, 0.40)
    a[::64, :, :3] = 0.25
    a[:, ::64, :3] = 0.25
    a[1::64, :, :3] = 0.25
    a[:, 1::64, :3] = 0.25
    img.pixels.foreach_set(a.ravel().astype(np.float32))
    img.update()
    return img


def ground(scale=80.0):
    if "qa_floor" in bpy.data.objects:
        return bpy.data.objects["qa_floor"]
    s = scale / 2
    uv = np.array([(0, 0), (1, 0), (1, 1), (0, 1)]) * (scale / 8.0)
    o = core.mesh_object("qa_floor", np.array([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)]), [(0, 1, 2, 3)], uvs=uv)
    m = core.material("qa_floor_mat", base_tex=grid_image())
    o.data.materials.append(m)
    return o


def overlay_material(name, rgb):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1.0)
    return m


def fan(name, centre, r0, r1, a0, a1, n=40):
    verts = []
    faces = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        d = Vector((math.cos(a), math.sin(a), 0))
        verts.append(Vector(centre) + d * r0 + Vector((0, 0, 0.03)))
        verts.append(Vector(centre) + d * r1 + Vector((0, 0, 0.03)))
    for i in range(n):
        faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    return core.mesh_object(name, np.array([tuple(v) for v in verts]), faces, smooth=False)


def zone_objects(cid):
    """QA overlays (not exported).  Angles: 0 deg = +X, forward = -Y = -90 deg."""
    objs = []
    if cid == "lf_boss_jaw_arc":
        objs.append(fan("qa_zone", (0, -2.0, 0), 1.0, 7.5, -90 - 50, -90 + 50))
    elif cid == "lf_boss_tail_sweep":
        objs.append(fan("qa_zone", (0, 0.5, 0), 1.5, 7.5, -20, 200))
    elif cid == "lf_boss_lane_charge":
        objs.append(core.mesh_object("qa_zone", np.array([(-1.6, -1.0, 0.03), (1.6, -1.0, 0.03), (1.6, -11.0, 0.03),
                                                          (-1.6, -11.0, 0.03)]), [(0, 1, 2, 3)], smooth=False))
    elif cid == "lf_boss_stomp_waves":
        objs.append(fan("qa_zone", (0, 0, 0), 0.0, 0.01, 0, 1))
    return objs


def zone_state(cid, t):
    m = A.MANIFEST[cid][2]
    if cid == "lf_boss_stomp_waves":
        for k in (1, 2):
            if m[f"wave_{k}_begin"] <= t <= m[f"wave_{k}_end"]:
                return "active", (t - m[f"wave_{k}_begin"]) / 0.4
        return ("telegraph", 0) if t < m["wave_1_begin"] else ("idle", 0)
    if "active_begin" not in m:
        return "idle", 0
    if t < m["active_begin"]:
        return "telegraph", t / m["active_begin"]
    if t <= m["active_end"]:
        return "active", 0
    return "recovery", 0


def stomp_ring(progress):
    for o in [o for o in bpy.data.objects if o.name.startswith("qa_zone")]:
        bpy.data.objects.remove(o, do_unlink=True)
    r = 2.0 + 9.0 * progress
    objs = []
    for g in range(6):     # ring segments with explicit gaps
        a0 = g * 60 + 12
        objs.append(fan(f"qa_zone_{g}", (0, -0.2, 0), r - 0.7, r, a0, a0 + 36, n=8))
    return objs


def setup_render(res=(960, 540)):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE"
    sh.show_shadows = True
    sh.shadow_intensity = 0.45
    sh.show_cavity = True
    sh.cavity_type = "WORLD"
    sc.display.shadow_focus = 0.5
    sc.render.film_transparent = False
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.image_settings.file_format = "PNG"
    sh.background_type = "VIEWPORT" if hasattr(sh, "background_type") else sh.background_type


def annotate(png, text, sub=""):
    from PIL import Image, ImageDraw
    im = Image.open(png).convert("RGB")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, im.size[0], 34], fill=(20, 20, 20))
    d.text((8, 4), text, fill=(255, 235, 190))
    if sub:
        d.text((8, 18), sub, fill=(255, 140, 90) if "ACTIVE" in sub else (220, 220, 220))
    im.save(png)


def render_clip(arm, cid, view, out_mp4, loops=1):
    D, loop, markers = A.MANIFEST[cid]
    act = bpy.data.actions[cid]
    arm.animation_data.action = act
    sc = bpy.context.scene
    ground()
    zones = zone_objects(cid) if view == "game" else []
    col_tel = overlay_material("qa_tel", (0.95, 0.55, 0.08))
    col_act = overlay_material("qa_act", (0.85, 0.08, 0.05))
    for z in zones:
        z.data.materials.append(col_tel)
    cam = bpy.data.objects.get("qa_cam") or core.link(bpy.data.objects.new("qa_cam", bpy.data.cameras.new("qa_cam")))
    sc.camera = cam
    tmp = tempfile.mkdtemp()
    N = int(round(D * A.FPS))
    k = 0
    for lp in range(loops):
        for i in range(N + (0 if (loop and lp < loops - 1) else 1)):
            t = i * D / N
            off, yaw = client_root(cid, t)
            if loop and cid == "lf_boss_walk":
                off = Vector((0, -A.WALK_SPEED * (t + lp * D), 0))
            arm.location = off
            arm.rotation_euler = (0, 0, math.radians(yaw))
            sc.frame_set(0)
            sc.frame_float = t * A.FPS if hasattr(sc, "frame_float") else 0
            sc.frame_set(int(math.floor(t * A.FPS)), subframe=(t * A.FPS) % 1.0)
            state, prog = zone_state(cid, t)
            if cid == "lf_boss_stomp_waves" and view == "game":
                for z in [o for o in bpy.data.objects if o.name.startswith("qa_zone")]:
                    bpy.data.objects.remove(z, do_unlink=True)
                zones = stomp_ring(prog) if state == "active" else []
                for z in zones:
                    z.data.materials.append(col_act)
            for z in zones:
                z.hide_render = state not in ("telegraph", "active")
                if z.data.materials:
                    z.data.materials[0] = col_act if state == "active" else col_tel
                z.location = off
                z.rotation_euler = (0, 0, math.radians(yaw))
            if view == "side":
                target = off + Vector((0, 0.2, 1.8))
                cam.data.type = "PERSP"
                cam.data.lens = 35
                cam.location = target + Vector((15.5, -2.5, 1.2))
            else:
                target = off + Vector((0, -1.0, 1.0))
                cam.data.type = "PERSP"
                cam.data.sensor_fit = "VERTICAL"
                cam.data.angle = math.radians(GAME_FOV)
                dist = 45.0
                d = Vector((0, -math.cos(GAME_TILT), math.sin(GAME_TILT))).normalized()
                d = Matrix.Rotation(math.radians(30), 3, "Z") @ d
                cam.location = target + d * dist
            cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
            p = os.path.join(tmp, f"f{k:05d}.png")
            sc.render.filepath = p
            bpy.ops.render.render(write_still=True)
            mk = ", ".join(f"{n}={v}" for n, v in markers.items())
            annotate(p, f"{cid}  t={t:5.2f}s / {D}s  view={view}", (f"{state.upper()}  " if state != "idle" else "") + mk)
            k += 1
    os.makedirs(os.path.dirname(out_mp4), exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(A.FPS), "-i", os.path.join(tmp, "f%05d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21", out_mp4], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    for z in [o for o in bpy.data.objects if o.name.startswith("qa_zone")]:
        bpy.data.objects.remove(z, do_unlink=True)
    arm.location = (0, 0, 0)
    arm.rotation_euler = (0, 0, 0)
    return out_mp4


def foot_slide(arm, cid):
    """Max world-space drift (m) of each planted toe tip during contact (ball within 4 cm of the ground)."""
    D, loop, _m = A.MANIFEST[cid]
    ps = Poser(arm)
    ts = A.times(D)
    tracks = {"L": [], "R": []}
    for t in ts:
        A.apply_layer(ps, A.CLIPS[cid](t))
        P = ps.matrices()
        off, yaw = client_root(cid, t)
        Rz = Matrix.Rotation(math.radians(yaw), 4, "Z")
        for s in "LR":
            w = Matrix.Translation(off) @ Rz @ ps.tail(f"toe3b_{s}", P).to_4d()
            ball = Matrix.Translation(off) @ Rz @ ps.tail(f"foot_{s}", P).to_4d()
            tracks[s].append((t, Vector(w[:3]), ball[2]))
    out = {}
    for s, tr in tracks.items():
        best, seg = 0.0, []
        for t, p, bz in tr:
            if p.z < 0.10 and bz < 0.30:
                seg.append(p)
            else:
                if len(seg) > 2:
                    best = max(best, max((q - seg[0]).xy.length for q in seg))
                seg = []
        if len(seg) > 2:
            best = max(best, max((q - seg[0]).xy.length for q in seg))
        out[s] = round(best, 3)
    return out


def run_all(iter_tag="", views=("side", "game"), clips=None):
    arm = bpy.data.objects[f"{AID}_rig"]
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name.startswith(AID):
            o.hide_render = not o.name.endswith("_LOD0")
    setup_render()
    report = {}
    for cid in (clips or list(A.MANIFEST)):
        D, loop, _ = A.MANIFEST[cid]
        rep = {"seconds": D, "foot_slide_m": foot_slide(arm, cid)}
        for v in views:
            if v == "game" and cid in ("lf_boss_idle", "lf_boss_hit"):
                continue
            mp4 = C.qa_video(f"{cid}{'' if v == 'side' else '_gamecam'}.mp4")
            render_clip(arm, cid, v, mp4, loops=2 if (loop and cid == "lf_boss_walk") else 1)
            render.contact_sheet_from_video(mp4, mp4.replace(".mp4", "_sheet.png"), frames=12)
            rep[v] = os.path.basename(mp4)
        report[cid] = rep
        print("[videos]", cid, rep, flush=True)
    core.write_json(C.qa_video(f"clips_report{iter_tag}.json"), report)
    return report
