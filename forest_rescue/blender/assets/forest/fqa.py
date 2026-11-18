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


def _ao_copy(mat, layer="Col"):
    """QA-only copy of a material multiplying base colour by COLOR_0 alpha (crown AO), like lf_forest_wind."""
    m = mat.copy()
    m.name = mat.name + "_qa_ao"
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None or not bsdf.inputs["Base Color"].is_linked:
        return m
    src = bsdf.inputs["Base Color"].links[0].from_socket
    attr = nt.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = layer
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 0.85
    nt.links.new(src, mix.inputs[6])
    nt.links.new(attr.outputs["Alpha"], mix.inputs[7])
    nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    return m


def use_ao(objs, on=True):
    """Swap material slots to AO-multiplied QA copies (on) or back to the export materials (off)."""
    for o in objs:
        if o.type != "MESH" or len(o.data.color_attributes) == 0:
            continue
        layer = o.data.color_attributes[0].name
        for s in o.material_slots:
            if s.material is None:
                continue
            if on and not s.material.name.endswith("_qa_ao"):
                qa = bpy.data.materials.get(s.material.name + "_qa_ao") or _ao_copy(s.material, layer)
                s.link = "OBJECT"
                s.material = qa
            elif not on:
                s.link = "DATA"


# ----------------------------------------------------------------------------- strategic references + colour stats

STRATEGIC_REFS = {   # (sheet, box) crops of the strategic-camera paintings
    "oak": [("07_fog_exploration_interface.png", (762, 500, 972, 710), "art/07 p2 oak"),
            ("01_world_masterplan.png", (380, 112, 506, 238), "art/01 oak grove")],
    "pine": [("01_world_masterplan.png", (0, 40, 120, 200), "art/01 conifers"),
             ("07_fog_exploration_interface.png", (930, 120, 1022, 330), "art/07 p2 conifers")],
    "birch": [("07_fog_exploration_interface.png", (780, 130, 960, 300), "art/07 p2 trees"),
              ("01_world_masterplan.png", (380, 112, 506, 238), "art/01 grove")],
}
HUE = {"oak": (8, 34), "pine": (25, 95), "birch": (18, 45), "willow": (18, 45), "hollow": (4, 30)}


def foliage_mask(rgb, hue, smin=0.3, vmin=0.12):
    import cv2
    hsv = cv2.cvtColor((np.clip(rgb[..., :3], 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1] / 255.0, hsv[..., 2] / 255.0
    return (h >= hue[0]) & (h <= hue[1]) & (s > smin) & (v > vmin)


def lab_stats(rgb, mask):
    from skimage import color as skc
    px = np.clip(rgb[..., :3][mask], 0, 1)
    if len(px) < 20:
        return None
    lab = skc.rgb2lab(px[None])[0]
    return {"mean": np.round(lab.mean(0), 2).tolist(), "std": np.round(lab.std(0), 2).tolist(), "n": int(len(px))}


def de(a, b):
    return round(float(np.linalg.norm(np.array(a["mean"]) - np.array(b["mean"]))), 2) if a and b else None


def strategic_compare(objs_by_lod, species, out_png, label, res=(700, 700), pitch=55, yaw=20):
    """Side-by-side [strategic-art crops | render LOD0 | LOD1 | LOD2] (ortho 55deg), plus foliage colour stats."""
    from frlib import refs
    imgs, labels, stats = [], [], {}
    hue = HUE.get(species, (8, 40))
    for sheet, box, lab in STRATEGIC_REFS.get(species, STRATEGIC_REFS["oak"]):
        im = refs.crop(refs.load(sheet), box)
        imgs.append(im)
        labels.append(lab)
        stats[lab] = lab_stats(im, foliage_mask(im, hue))
    for lod, objs in enumerate(objs_by_lod):
        rgba = ortho_shot(objs, "/tmp/_strat.png", pitch_deg=pitch, yaw_deg=yaw, res=res, bg=False)
        img = rgba[..., :3] * rgba[..., 3:4] + np.array([0.40, 0.42, 0.24]) * (1 - rgba[..., 3:4])
        imgs.append(img)
        labels.append(f"kit LOD{lod} {pitch}deg")
        m = (rgba[..., 3] > 0.5) & foliage_mask(rgba[..., :3], hue)
        stats[f"LOD{lod}"] = lab_stats(rgba[..., :3], m)
    render.side_by_side(imgs, labels, out_png, height=420)
    ref0 = stats[labels[0]]
    out = {k: dict(v or {}, dE_vs_first_ref=de(v, ref0)) for k, v in stats.items()}
    core.write_json(out_png.replace(".png", ".json"), out)
    return out
