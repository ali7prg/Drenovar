"""QA renders for the forest kit: reference-matched silhouettes (IoU), lineups, strategic top views."""
import json
import math
import os

import bpy
import numpy as np
from mathutils import Vector

import fbuild  # noqa: F401  (sets sys.path for frlib)
from frlib import core, render, paths
import refsetup

BG = (0.875, 0.82, 0.784)


def studio(samples=24):
    sc = render.studio(bg=BG, engine="CYCLES", samples=samples, transparent=True, key_energy=3.4,
                       fill_energy=1.1, rim_energy=1.2, ambient=0.75)
    sc.cycles.transparent_max_bounces = 32
    sc.cycles.max_bounces = 3
    sc.cycles.use_denoising = True
    return sc


def only(objs):
    keep = set(o.name for o in objs)
    for o in bpy.data.objects:
        if o.type in ("MESH", "CURVE"):
            o.hide_render = o.name not in keep


def compare_view(view, objs, out_png, title):
    """[reference | render | IoU diff]; metrics: raw IoU and closed-envelope IoU (r=4 px)."""
    only(objs)
    render.camera_for_view(view)
    rgba = render.render_rgba()
    a = rgba.copy()
    clip = getattr(view, "clip_row", None)
    if clip is not None:
        a[clip:, :, 3] = 0
    rm = a[..., 3] > 0.5
    iou_c = refsetup.iou(refsetup.closed(view.mask), refsetup.closed(rm))
    m = render.compare(view, a, out_png, title=title, bg=np.array(BG), extra={"iou_closed_r4": round(iou_c, 4)})
    return m, rgba


def ortho_shot(objs, out_png, direction=(0, 1, 0), up=(0, 0, 1), res=(1400, 700), margin=1.04, bg=True, label=None,
               pitch_deg=None, yaw_deg=0.0):
    """Orthographic shot framing objs. direction = camera view dir; or pitch/yaw (strategic camera)."""
    only(objs)
    lo, hi = core.bounds(objs)
    c = (lo + hi) / 2
    if pitch_deg is not None:
        p, y = math.radians(pitch_deg), math.radians(yaw_deg)
        d = Vector((math.sin(y) * math.cos(p), math.cos(y) * math.cos(p), -math.sin(p)))
    else:
        d = Vector(direction).normalized()
    size = np.linalg.norm(hi - lo)
    loc = Vector(c) - d * size * 2
    cam = render.perspective_camera(tuple(loc), tuple(c), res=res, ortho_scale=1.0)
    bpy.context.view_layer.update()
    # fit ortho scale to the projected mesh vertices (tight framing at any pitch/yaw)
    pts = []
    for o in objs:
        v, _, _, _ = core.mesh_arrays(o, evaluated=True, world=True)
        if len(v) > 4000:
            v = v[:: len(v) // 4000 + 1]
        pts.append(v)
    corners = np.concatenate(pts) if pts else np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    R = np.array(cam.matrix_world.to_3x3())
    q = (corners - np.array(loc)) @ R
    w = (q[:, 0].max() - q[:, 0].min())
    h = (q[:, 1].max() - q[:, 1].min())
    ar = res[0] / res[1]
    cam.data.ortho_scale = max(w, h * ar) * margin
    # recentre
    cx = (q[:, 0].max() + q[:, 0].min()) / 2
    cy = (q[:, 1].max() + q[:, 1].min()) / 2
    cam.location = cam.location + cam.matrix_world.to_3x3() @ Vector((cx, cy, 0))
    rgba = render.render_rgba()
    img = rgba[..., :3] * rgba[..., 3:4] + np.array(BG) * (1 - rgba[..., 3:4]) if bg else rgba
    if label:
        u8 = (np.clip(img, 0, 1) * 255).astype(np.uint8)
        img = render._label(u8, label) / 255.0
    core.save_rgba(out_png, img)
    return img


def ground_plane(size=200, col=(0.36, 0.40, 0.20)):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, 0))
    g = bpy.context.active_object
    g.name = "qa_ground"
    m = bpy.data.materials.new("qa_ground_mat")
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*col, 1)
    bsdf.inputs["Roughness"].default_value = 1.0
    g.data.materials.append(m)
    return g


def iter_path(asset_id, it, name):
    return paths.compare(asset_id, f"iter{it:02d}_{name}.png")
