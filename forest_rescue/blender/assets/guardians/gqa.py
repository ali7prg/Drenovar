"""Guardian QA: clip videos + contact sheets, motion-strip match, head close-ups, Godot checks."""
import json
import math
import os
import shutil
import subprocess
import tempfile

import bpy
import numpy as np

from frlib import core, render, refs, paths
import gbody
import gbuild as gb

REPO = paths.REPO


def _hide_extras(B, hide=True):
    for o in [B.body_hi] + B.lods[1:] + getattr(B, "level_objs", []):
        o.hide_render = hide


def ground_plane(size=80.0, squares=160):
    pl = bpy.data.objects.get("qa_ground")
    if pl is None:
        me = bpy.data.meshes.new("qa_ground")
        h = size / 2
        me.from_pydata([(-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0)], [], [(0, 1, 2, 3)])
        me.uv_layers.new(name="UVMap")
        pl = bpy.data.objects.new("qa_ground", me)
        core.link(pl)
        mat = bpy.data.materials.new("qa_ground_mat")
        mat.use_nodes = True
        nt = mat.node_tree
        bs = nt.nodes["Principled BSDF"]
        ck = nt.nodes.new("ShaderNodeTexChecker")
        ck.inputs["Scale"].default_value = squares
        ck.inputs["Color1"].default_value = (0.42, 0.40, 0.33, 1)
        ck.inputs["Color2"].default_value = (0.30, 0.28, 0.23, 1)
        nt.links.new(ck.outputs["Color"], bs.inputs["Base Color"])
        bs.inputs["Roughness"].default_value = 0.95
        pl.data.materials.append(mat)
    return pl


def _engine(scene, samples=12):
    try:
        scene.render.engine = "BLENDER_EEVEE"
        scene.eevee.taa_render_samples = samples
        return "BLENDER_EEVEE"
    except Exception:
        scene.render.engine = "BLENDER_WORKBENCH"
        return "BLENDER_WORKBENCH"


def clip_videos(B, cams=("q34",), res=(960, 540)):
    spec = B.spec
    out = paths.ensure(paths.QA_VIDEO, spec.ID)
    scene = bpy.context.scene
    render.studio(engine="CYCLES", samples=8, transparent=False)
    eng = _engine(scene)
    scene.render.film_transparent = False
    scene.render.resolution_x, scene.render.resolution_y = res
    _hide_extras(B, True)
    pl = ground_plane()
    pl.hide_render = False
    camdefs = {
        "q34": (np.array([5.6, -6.4, 2.5]), np.array([0.0, 0.0, 0.95]), 35.0),
        "side": (np.array([7.5, 0.25, 0.55]), np.array([0.0, 0.25, 0.75]), 32.0),
    }
    results = {}
    for clip, info in B.clip_meta.items():
        act = bpy.data.actions[clip]
        B.arm.animation_data.action = act
        n = int(act.frame_range[1])
        loops = 3 if info["loop"] else 1
        speed = info.get("groundSpeed_mps", 0.0)
        for cam in (cams + (("side",) if clip in ("Walk", "Run") else ())):
            loc, look, lens = camdefs[cam]
            render.perspective_camera(tuple(loc), tuple(look), lens=lens, res=res)
            tmp = tempfile.mkdtemp()
            k = 0
            for lp in range(loops):
                for f in range(n + (1 if lp == loops - 1 else 0)):
                    tt = (lp * n + f) / 30.0
                    pl.location.y = (speed * tt) % 1.0          # ground scrolls back at groundSpeed
                    scene.frame_set(f)
                    scene.render.filepath = os.path.join(tmp, f"f{k:05d}.png")
                    scene.render.image_settings.file_format = "PNG"
                    bpy.ops.render.render(write_still=True)
                    k += 1
            name = clip if cam == "q34" else f"{clip}_{cam}"
            mp4 = os.path.join(out, f"{name}.mp4")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i",
                            os.path.join(tmp, "f%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                            mp4], check=True)
            shutil.rmtree(tmp, ignore_errors=True)
            sheet = os.path.join(out, f"{name}_contact.png")
            render.contact_sheet_from_video(mp4, sheet, frames=12 if not info["loop"] else 8)
            results[name] = {"mp4": os.path.relpath(mp4, REPO), "contact": os.path.relpath(sheet, REPO),
                             "frames": k, "engine": eng}
            gb.log("video", name, k)
    pl.location.y = 0
    pl.hide_render = True
    B.arm.animation_data.action = None
    scene.frame_set(0)
    gb.apply_pose(B.arm, B.sk, None)
    _hide_extras(B, False)
    B.videos = results
    return results


# --------------------------------------------------------------------------- motion strip (Tenerys)

def strip_match(B, tag="strip"):
    spec = B.spec
    if not hasattr(spec, "STRIP"):
        return {}
    import gref
    out = paths.ensure(paths.QA_COMPARE, spec.ID)
    _hide_extras(B, True)
    act = bpy.data.actions["Attack"]
    B.arm.animation_data.action = act
    res = {}
    imgs = []
    for name, (box, tsec) in spec.STRIP.items():
        img = refs.crop(gref.sheet("09"), box)
        m = refs.silhouette(img, thresh=0.09, keep="largest", fill_holes=600)
        if hasattr(spec, "strip_mask_fix"):
            m = spec.strip_mask_fix(name, m, img)
        H, W = m.shape
        ground = spec.STRIP_GROUND[name] - box[1]
        f = int(round(tsec * 30))
        bpy.context.scene.frame_set(f)
        v, t, _, _ = core.mesh_arrays(B.lods[0])
        best = None
        x0m, y0m, x1m, y1m = refs.bbox(m)
        for ppm in np.arange(70.0, 140.0, 1.0):
            view = refs.View("strip", img, m, refs.VIEW_DIRS["right"], ppm, 0.0, ground)
            u, vv, _ = view.project(v)
            ax = (x0m + x1m) / 2.0 - (u.min() + u.max()) / 2.0
            for dax in (-6, -3, 0, 3, 6):
                view.ax = ax + dax
                s = gbody.iou(m, gbody.silhouette(v, t, view))
                if best is None or s > best[0]:
                    best = (s, ppm, ax + dax)
        s, ppm, ax = best
        view = refs.View(f"strip_{name}", img, m, refs.VIEW_DIRS["right"], ppm, ax, ground)
        render.studio(engine="CYCLES", samples=24)
        render.camera_for_view(view)
        rgba = render.render_rgba()
        mt = render.compare(view, rgba, os.path.join(out, f"{tag}_{name}.png"),
                            title=f"{spec.ID} Attack t={tsec:.2f}s vs strip '{name}' (fitted ppm {ppm:.0f})")
        res[name] = {"attack_time_s": tsec, "iou": mt["iou"], "fitted_ppm": float(ppm)}
        gb.log("strip", name, res[name])
    B.arm.animation_data.action = None
    bpy.context.scene.frame_set(0)
    gb.apply_pose(B.arm, B.sk, None)
    _hide_extras(B, False)
    core.write_json(os.path.join(out, f"{tag}_metrics.json"), res)
    B.strip = res
    return res


# --------------------------------------------------------------------------- head close-ups

def head_closeups(B, tag="head"):
    spec = B.spec
    if not hasattr(spec, "HEAD_VIEWS"):
        return {}
    import gref
    out = paths.ensure(paths.QA_COMPARE, spec.ID)
    _hide_extras(B, True)
    gb.apply_pose(B.arm, B.sk, None)
    res = {}
    for name, hv in spec.HEAD_VIEWS.items():
        img = refs.crop(gref.sheet(hv["sheet"]), hv["box"])
        render.studio(engine="CYCLES", samples=32)
        if hv["kind"] == "ortho":
            view = refs.View(name, img, np.ones(img.shape[:2], bool), refs.VIEW_DIRS[hv["dir"]], hv["ppm"],
                             hv["anchor_px"][0], hv["anchor_px"][1], anchor=np.asarray(hv["anchor_world"], float))
            render.camera_for_view(view)
        else:
            render.perspective_camera(tuple(hv["cam"]), tuple(hv["look"]), lens=hv.get("lens", 85.0),
                                      res=(img.shape[1], img.shape[0]))
        rgba = render.render_rgba()
        bgc = np.median(img[:6].reshape(-1, 3), axis=0)
        comp = rgba[..., :3] * rgba[..., 3:4] + bgc * (1 - rgba[..., 3:4])
        p = os.path.join(out, f"{tag}_{name}.png")
        render.side_by_side([img, comp], ["reference", "render (LOD0)"], p, height=img.shape[0])
        res[name] = os.path.relpath(p, REPO)
        gb.log("head", name)
    _hide_extras(B, False)
    return res


# --------------------------------------------------------------------------- Godot

def godot(B, seconds=None):
    spec = B.spec
    tool = os.path.join(REPO, "forest_rescue", "tools", "godot_view.sh")
    shots = paths.ensure(paths.QA_COMPARE, spec.ID, "godot")
    r1 = subprocess.run([tool, B.glb_path, "shots", shots, "Idle"], capture_output=True, text=True, timeout=900)
    vid = os.path.join(paths.ensure(paths.QA_VIDEO, spec.ID), "godot_all_clips.mp4")
    secs = seconds or 34
    r2 = subprocess.run([tool, B.glb_path, "clip", vid, "all", str(secs)], capture_output=True, text=True, timeout=1500)
    log = (r1.stdout + r1.stderr + r2.stdout + r2.stderr)
    lines = [l for l in log.splitlines() if "VIEWER" in l or "ERROR" in l]
    if os.path.exists(vid):
        render.contact_sheet_from_video(vid, vid.replace(".mp4", "_contact.png"), frames=16)
    B.godot_log = lines
    gb.log("godot", lines[:6])
    return lines


def old_vs_new(B):
    from PIL import Image, ImageDraw
    spec = B.spec
    d = paths.ensure(paths.QA_COMPARE, spec.ID)
    old = os.path.join(d, "original", "L1")
    new = os.path.join(d, "godot")
    # originals face +X, new GLBs face +Z: pair yaws that show the same side of the animal
    pairs = [(180, 90, "left side"), (90, 0, "front"), (135, 45, "front-left 3/4"), (270, 180, "rear")]
    W, H = 400, 225
    sheet = Image.new("RGB", (W * len(pairs), H * 2 + 30), (25, 25, 25))
    dr = ImageDraw.Draw(sheet)
    dr.text((8, 8), f"{spec.ID}: top = original {spec.SPECIES.upper()}_L1 prototype (creature-assets37), "
                    f"bottom = new GLB, Godot 4.6 viewer", fill=(255, 230, 160))
    for i, (yo, yn, lab) in enumerate(pairs):
        po = os.path.join(old, f"shot_yaw{yo:03d}.png")
        pn = os.path.join(new, f"shot_yaw{yn:03d}.png")
        for j, p in enumerate((po, pn)):
            if os.path.exists(p):
                im = Image.open(p).convert("RGB").resize((W, H))
                sheet.paste(im, (i * W, 30 + j * H))
        dr.text((i * W + 6, 34), lab, fill=(255, 255, 0))
    p = os.path.join(d, "old_vs_new.png")
    sheet.save(p)
    return p
