"""Reference-matched renders, side-by-side comparisons with silhouette IoU, and clip videos."""
import json
import math
import os
import shutil
import subprocess
import tempfile

import bpy
import numpy as np
from mathutils import Matrix, Vector

from . import core


def studio(bg=(0.86, 0.82, 0.74), engine="CYCLES", samples=48, transparent=True,
           key_dir=(-0.55, -0.6, 0.65), key_energy=3.2, fill_energy=1.0, rim_energy=1.6,
           ambient=0.55, view_transform="Standard"):
    """Neutral studio close to the painted reference sheets (key light upper-left-front)."""
    scene = bpy.context.scene
    scene.render.engine = engine
    if engine == "CYCLES":
        scene.cycles.device = "CPU"
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
        scene.cycles.max_bounces = 4
    elif engine == "BLENDER_EEVEE":
        scene.eevee.taa_render_samples = samples
    scene.view_settings.view_transform = view_transform
    scene.view_settings.look = "None"
    scene.render.film_transparent = transparent
    world = bpy.data.worlds.get("frlib_world") or bpy.data.worlds.new("frlib_world")
    scene.world = world
    world.use_nodes = True
    bgn = world.node_tree.nodes.get("Background")
    bgn.inputs["Color"].default_value = (*[c * ambient for c in bg], 1.0)
    bgn.inputs["Strength"].default_value = 1.0
    for o in [o for o in bpy.data.objects if o.name.startswith("frlib_light")]:
        bpy.data.objects.remove(o, do_unlink=True)

    def sun(name, direction, energy, angle=8.0):
        light = bpy.data.lights.new(name, "SUN")
        light.energy = energy
        light.angle = math.radians(angle)
        obj = bpy.data.objects.new(name, light)
        d = Vector(direction).normalized()
        obj.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        core.link(obj)
        return obj

    sun("frlib_light_key", key_dir, key_energy, 6.0)
    sun("frlib_light_fill", (0.6, -0.4, 0.25), fill_energy, 25.0)
    sun("frlib_light_rim", (0.2, 0.9, 0.45), rim_energy, 10.0)
    return scene


def camera_for_view(view, name="frlib_cam", distance=40.0):
    """Orthographic camera reproducing a refs.View pixel mapping over its crop size."""
    W, H = view.size
    cam = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cam.type = "ORTHO"
    cam.ortho_scale = max(W, H) / view.ppm
    cam.sensor_fit = "AUTO"
    cam.clip_start = 0.05
    cam.clip_end = distance * 3
    obj = bpy.data.objects.get(name) or core.link(bpy.data.objects.new(name, cam))
    center = view.world_of_pixel(W / 2.0, H / 2.0, depth=-distance)
    rotm = Matrix((tuple(view.right), tuple(view.up), tuple(-view.d))).transposed()
    obj.matrix_world = Matrix.Translation(Vector(center)) @ rotm.to_4x4()
    scene = bpy.context.scene
    scene.camera = obj
    scene.render.resolution_x = W
    scene.render.resolution_y = H
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1.0
    return obj


def perspective_camera(location, look_at, lens=50.0, name="frlib_pcam", res=(1024, 768), ortho_scale=None):
    cam = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    if ortho_scale:
        cam.type = "ORTHO"
        cam.ortho_scale = ortho_scale
    else:
        cam.type = "PERSP"
        cam.lens = lens
    cam.clip_start = 0.05
    cam.clip_end = 500
    obj = bpy.data.objects.get(name) or core.link(bpy.data.objects.new(name, cam))
    obj.location = location
    d = Vector(look_at) - Vector(location)
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    scene = bpy.context.scene
    scene.camera = obj
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    return obj


def render_rgba(path=None):
    scene = bpy.context.scene
    tmp = path or os.path.join(tempfile.mkdtemp(), "frame.png")
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.filepath = tmp
    bpy.ops.render.render(write_still=True)
    from PIL import Image
    return np.asarray(Image.open(tmp).convert("RGBA"), dtype=np.float64) / 255.0


def _label(img_u8, text, xy=(8, 6)):
    from PIL import Image, ImageDraw
    im = Image.fromarray(img_u8)
    dr = ImageDraw.Draw(im)
    x, y = xy
    dr.rectangle([x - 4, y - 3, x + 7 * len(text) + 6, y + 14], fill=(20, 20, 20))
    dr.text((x, y), text, fill=(255, 240, 200))
    return np.asarray(im)


def iou(mask_a, mask_b):
    inter = np.logical_and(mask_a, mask_b).sum()
    union = np.logical_or(mask_a, mask_b).sum()
    return float(inter) / max(float(union), 1.0)


def compare(view, rgba, out_png, title="", bg=None, extra=None):
    """Write [reference | render | silhouette diff] and return metrics."""
    ref = view.image
    H, W = ref.shape[:2]
    if rgba.shape[:2] != (H, W):
        import cv2
        rgba = cv2.resize(rgba, (W, H), interpolation=cv2.INTER_AREA)
    bgc = np.median(ref[~view.mask], axis=0) if bg is None else np.asarray(bg)
    a = rgba[..., 3:4]
    comp = rgba[..., :3] * a + bgc[None, None, :] * (1 - a)
    rmask = rgba[..., 3] > 0.5
    score = iou(view.mask, rmask)
    diff = np.repeat((ref.mean(axis=2, keepdims=True) * 0.5 + 0.35), 3, axis=2)
    both = view.mask & rmask
    diff[both] = diff[both] * 0.5 + np.array([0.15, 0.55, 0.15]) * 0.5
    diff[view.mask & ~rmask] = (0.85, 0.15, 0.15)
    diff[~view.mask & rmask] = (0.15, 0.3, 0.9)
    # mean colour error inside the overlap (perceptual sanity check, not a pass/fail gate)
    col_err = float(np.abs(comp[both] - ref[both]).mean()) if both.any() else 1.0
    panels = []
    for img, txt in ((ref, "reference"), (comp, "render"), (diff, f"IoU {score:.3f}")):
        u8 = (np.clip(img, 0, 1) * 255).astype(np.uint8)
        panels.append(_label(u8, txt))
    sheet = np.concatenate(panels, axis=1)
    if title:
        top = np.full((26, sheet.shape[1], 3), 28, np.uint8)
        top = _label(top, title)
        sheet = np.concatenate([top, sheet], axis=0)
    core.save_rgba(out_png, sheet / 255.0)
    metrics = {"view": view.name, "iou": round(score, 4), "mean_abs_colour_error": round(col_err, 4),
               "ref_pixels": int(view.mask.sum()), "render_pixels": int(rmask.sum())}
    if extra:
        metrics.update(extra)
    core.write_json(out_png.replace(".png", ".json"), metrics)
    return metrics


def side_by_side(images, labels, out_png, height=512):
    import cv2
    panels = []
    for img, lab in zip(images, labels):
        img = np.asarray(img, float)
        if img.shape[2] == 4:
            img = img[..., :3] * img[..., 3:4] + 0.9 * (1 - img[..., 3:4])
        s = height / img.shape[0]
        img = cv2.resize(img, (int(img.shape[1] * s), height), interpolation=cv2.INTER_AREA)
        panels.append(_label((np.clip(img, 0, 1) * 255).astype(np.uint8), lab))
    core.save_rgba(out_png, np.concatenate(panels, axis=1) / 255.0)


def render_clip(arm_obj, action, out_mp4, camera_obj=None, fps=30, engine="BLENDER_WORKBENCH",
                res=(960, 540), loops=1, ground=True, follow_root=False, samples=16):
    """Render an action to MP4 (H.264) for motion review."""
    scene = bpy.context.scene
    scene.render.engine = engine
    scene.render.film_transparent = False
    if engine == "BLENDER_WORKBENCH":
        sh = scene.display.shading
        sh.light = "STUDIO"
        sh.color_type = "TEXTURE"
        sh.show_shadows = True
        sh.show_cavity = True
    elif engine == "CYCLES":
        scene.cycles.samples = samples
    elif engine == "BLENDER_EEVEE":
        scene.eevee.taa_render_samples = samples
    if camera_obj is not None:
        scene.camera = camera_obj
    scene.render.resolution_x, scene.render.resolution_y = res
    arm_obj.animation_data.action = action
    f0, f1 = int(action.frame_range[0]), int(action.frame_range[1])
    tmp = tempfile.mkdtemp()
    n = 0
    for _ in range(loops):
        for f in range(f0, f1 + 1):
            scene.frame_set(f)
            scene.render.filepath = os.path.join(tmp, f"f{n:05d}.png")
            scene.render.image_settings.file_format = "PNG"
            bpy.ops.render.render(write_still=True)
            n += 1
    os.makedirs(os.path.dirname(out_mp4), exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i",
                    os.path.join(tmp, "f%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "20", out_mp4], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return out_mp4


def contact_sheet_from_video(mp4, out_png, frames=8, width=1600):
    """Grid of evenly spaced frames from a clip video (for quick visual review)."""
    import cv2
    cap = cv2.VideoCapture(mp4)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    imgs = []
    for i in range(frames):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i * max(total - 1, 1) / max(frames - 1, 1)))
        ok, fr = cap.read()
        if ok:
            imgs.append(fr[..., ::-1])
    cap.release()
    if not imgs:
        return None
    cols = 4
    rows = math.ceil(len(imgs) / cols)
    h, w = imgs[0].shape[:2]
    sheet = np.full((rows * h, cols * w, 3), 30, np.uint8)
    for i, im in enumerate(imgs):
        r, c = divmod(i, cols)
        sheet[r * h:(r + 1) * h, c * w:(c + 1) * w] = im
    s = width / sheet.shape[1]
    sheet = cv2.resize(sheet, (width, int(sheet.shape[0] * s)), interpolation=cv2.INTER_AREA)
    core.save_rgba(out_png, sheet / 255.0)
    return out_png
