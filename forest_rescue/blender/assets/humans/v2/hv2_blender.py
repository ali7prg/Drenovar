"""Blender-side helpers for the v2 human builds: mesh objects, decimation with protected regions,
solidified garment sheets, UV layout with enlarged face islands, painted-light materials and the
QA renders (turnaround compare sheets, portrait match, 3/4 views)."""
import json
import math
import os

import bpy
import numpy as np
from mathutils import Matrix, Vector

from frlib import core


def obj_from(name, V, Fc, col=None, smooth=True):
    return core.mesh_object(name, np.asarray(V, float), Fc, col=col, smooth=smooth)


def add_group(obj, name, weights):
    g = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
    w = np.asarray(weights, float)
    idx = np.nonzero(w > 0)[0]
    if len(idx):
        vals = np.round(w[idx], 3)
        order = np.argsort(vals)
        idx, vals = idx[order], vals[order]
        splits = np.nonzero(np.diff(vals))[0] + 1
        for ii, vv in zip(np.split(idx, splits), np.split(vals, splits)):
            g.add(ii.tolist(), float(vv[0]), "REPLACE")
    return g


def decimate(obj, target, protect=None, factor=8.0):
    cur = core.tri_count(obj)
    if cur <= target:
        return obj
    mod = obj.modifiers.new("dec", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = max(0.002, target / cur)
    mod.use_collapse_triangulate = True
    if protect is not None:
        # Blender's collapse cost grows where the group weight is LOW: store 1 - protect
        add_group(obj, "_protect", 1.0 - np.clip(np.asarray(protect, float), 0, 1) + 1e-4)
        mod.vertex_group = "_protect"
        mod.vertex_group_factor = factor
    core.select_only([obj])
    bpy.ops.object.modifier_apply(modifier="dec")
    if obj.vertex_groups.get("_protect"):
        obj.vertex_groups.remove(obj.vertex_groups["_protect"])
    # second pass without protection if still above target
    if core.tri_count(obj) > target * 1.06:
        mod = obj.modifiers.new("dec2", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = target / core.tri_count(obj)
        mod.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier="dec2")
    return obj


def solidify(obj, thickness, offset=-1.0):
    mod = obj.modifiers.new("sol", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = offset
    mod.use_even_offset = True
    mod.use_rim = True
    core.select_only([obj])
    bpy.ops.object.modifier_apply(modifier="sol")
    return obj


def smooth_shade(obj, angle=60.0):
    me = obj.data
    try:
        me.shade_smooth()
    except Exception:
        pass
    try:
        bpy.ops.object.shade_auto_smooth(angle=math.radians(angle))
    except Exception:
        pass


def recalc_normals(obj, inside=False):
    core.select_only([obj])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=inside)
    bpy.ops.object.mode_set(mode="OBJECT")


def face_attr(obj, name, values, kind="INT"):
    a = obj.data.attributes.get(name) or obj.data.attributes.new(name, kind, "FACE")
    a.data.foreach_set("value", np.asarray(values).astype(np.int32 if kind == "INT" else np.float32))


def face_attr_get(obj, name):
    a = obj.data.attributes.get(name)
    out = np.zeros(len(obj.data.polygons), np.int32)
    if a is not None:
        a.data.foreach_get("value", out)
    return out


def uv_layout(obj, boost_faces=None, boost=2.4, margin=0.003, angle=64.0):
    core.smart_uv(obj, angle=angle, margin=margin)
    me = obj.data
    if boost_faces is not None and np.any(boost_faces):
        uvl = me.uv_layers.active.data
        nl = len(me.loops)
        uv = np.empty(nl * 2)
        uvl.foreach_get("uv", uv)
        uv = uv.reshape(-1, 2)
        loop_face = np.empty(nl, np.int64)
        for p in me.polygons:
            loop_face[p.loop_start:p.loop_start + p.loop_total] = p.index
        sel = np.asarray(boost_faces)[loop_face]
        c = uv[sel].mean(0)
        uv[sel] = c + (uv[sel] - c) * boost
        uvl.foreach_set("uv", uv.ravel())
    core.pack_uv(obj, margin=margin, rotate=True)


def painted_material(name, img, k=0.0, light=(-0.45, -0.55, 0.70), emission=True, alpha_clip=None):
    """QA material: emission = albedo * mix(1, lambert(light), k) (the game's painted-light model)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    lv = Vector(light).normalized()
    dot.inputs[1].default_value = (lv.x, lv.y, lv.z)
    nt.links.new(geo.outputs["Normal"], dot.inputs[0])
    mx = nt.nodes.new("ShaderNodeMath")
    mx.operation = "MAXIMUM"
    mx.inputs[1].default_value = 0.0
    nt.links.new(dot.outputs["Value"], mx.inputs[0])
    ma = nt.nodes.new("ShaderNodeMath")
    ma.operation = "MULTIPLY_ADD"
    ma.inputs[1].default_value = k
    ma.inputs[2].default_value = 1.0 - k
    nt.links.new(mx.outputs["Value"], ma.inputs[0])
    mul = nt.nodes.new("ShaderNodeVectorMath")
    mul.operation = "SCALE"
    nt.links.new(tex.outputs["Color"], mul.inputs[0])
    nt.links.new(ma.outputs["Value"], mul.inputs["Scale"])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(mul.outputs["Vector"], em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    if alpha_clip is not None:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mixs = nt.nodes.new("ShaderNodeMixShader")
        gt = nt.nodes.new("ShaderNodeMath")
        gt.operation = "GREATER_THAN"
        gt.inputs[1].default_value = alpha_clip
        nt.links.new(tex.outputs["Alpha"], gt.inputs[0])
        nt.links.new(gt.outputs["Value"], mixs.inputs["Fac"])
        nt.links.new(tr.outputs["BSDF"], mixs.inputs[1])
        nt.links.new(em.outputs["Emission"], mixs.inputs[2])
        nt.links.new(mixs.outputs["Shader"], out.inputs["Surface"])
    else:
        nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


def qa_scene(samples=12):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = False
    scene.cycles.max_bounces = 0
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    w = bpy.data.worlds.get("hv2_world") or bpy.data.worlds.new("hv2_world")
    scene.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    scene.render.filter_size = 1.0
    return scene


def ortho_cam_for_view(view, scale=3, name="hv2_cam"):
    from frlib import render
    cam = render.camera_for_view(view, name=name)
    sc = bpy.context.scene
    sc.render.resolution_percentage = int(100 * scale)
    return cam


def affine_cam(acam, scale=3, name="hv2_pcam"):
    """Blender ortho camera reproducing a scaled-orthographic AffineCam over its image."""
    W, H = acam.size
    r1 = acam.rows[0]
    r2 = acam.rows[1]
    s = np.linalg.norm(r1)
    right = r1 / s
    down = r2 / np.linalg.norm(r2)
    up = -down
    d = np.cross(right, up)   # camera forward... ensure it matches acam.d
    if d @ acam.d < 0:
        d = -d
    cam = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cam.type = "ORTHO"
    cam.ortho_scale = max(W, H) / s
    cam.clip_start = 0.01
    cam.clip_end = 100
    obj = bpy.data.objects.get(name) or core.link(bpy.data.objects.new(name, cam))
    # image centre in world: solve u=W/2, v=H/2 on the plane through the head
    # world point X with rows@X + t = (W/2, H/2): X = pinv(rows) @ ((W/2,H/2) - t)
    X = np.linalg.pinv(acam.rows) @ (np.array([W / 2.0, H / 2.0]) - acam.t)
    center = X - d * 20.0
    rotm = Matrix((tuple(right), tuple(up), tuple(-d))).transposed()
    obj.matrix_world = Matrix.Translation(Vector(center)) @ rotm.to_4x4()
    sc = bpy.context.scene
    sc.camera = obj
    sc.render.resolution_x = W
    sc.render.resolution_y = H
    sc.render.resolution_percentage = int(100 * scale)
    return obj


def render_rgba():
    from frlib import render
    return render.render_rgba()


def _label(img_u8, text, xy=(6, 5)):
    from PIL import Image, ImageDraw
    im = Image.fromarray(img_u8)
    dr = ImageDraw.Draw(im)
    x, y = xy
    dr.rectangle([x - 4, y - 3, x + 6 * len(text) + 6, y + 13], fill=(20, 20, 20))
    dr.text((x, y), text, fill=(255, 240, 200))
    return np.asarray(im)


def compare_sheet(ref, ref_mask, rgba_big, out_png, title, scale=3):
    """[reference | render | IoU diff | colour-error heat]; metrics at the reference resolution."""
    import cv2
    H, W = ref.shape[:2]
    rgba = cv2.resize(rgba_big, (W, H), interpolation=cv2.INTER_AREA)
    bg = np.median(ref[~ref_mask], axis=0)
    a = rgba[..., 3:4]
    comp = rgba[..., :3] * a + bg * (1 - a)
    rmask = rgba[..., 3] > 0.5
    inter = (ref_mask & rmask).sum()
    union = (ref_mask | rmask).sum()
    iou = inter / max(union, 1)
    both = ref_mask & rmask
    err = np.abs(comp - ref).mean(-1)
    cerr = float(err[both].mean())
    # error on an eroded core (silhouette edge pixels excluded) for the texture fidelity figure
    from scipy import ndimage as ndi
    core_m = ndi.binary_erosion(both, iterations=2)
    cerr_core = float(err[core_m].mean()) if core_m.any() else cerr
    up = lambda im: cv2.resize(im, (W * scale, H * scale), interpolation=cv2.INTER_NEAREST if im.dtype == bool else cv2.INTER_CUBIC)  # noqa
    big_bg = np.median(ref[~ref_mask], axis=0)
    A = rgba_big[..., 3:4]
    comp_big = rgba_big[..., :3] * A + big_bg * (1 - A)
    diff = np.repeat(ref.mean(-1, keepdims=True) * 0.5 + 0.35, 3, -1)
    diff[both] = diff[both] * 0.5 + np.array([0.15, 0.55, 0.15]) * 0.5
    diff[ref_mask & ~rmask] = (0.85, 0.15, 0.15)
    diff[~ref_mask & rmask] = (0.15, 0.3, 0.9)
    heat = np.zeros((H, W, 3))
    e = np.clip(err / 0.25, 0, 1)
    heat[..., 0] = np.clip(e * 2, 0, 1)
    heat[..., 1] = np.clip(e * 2 - 1, 0, 1)
    heat[..., 2] = np.clip(1 - e * 3, 0, 1) * 0.35
    heat[~both] = 0.12
    panels = [up(np.clip(ref, 0, 1)), np.clip(comp_big, 0, 1), up(diff), up(heat)]
    labels = ["reference", "render (albedo)", f"IoU {iou:.3f}", f"colour err {cerr:.3f}"]
    tiles = [_label((p * 255).astype(np.uint8), l) for p, l in zip(panels, labels)]
    sheet = np.concatenate(tiles, 1)
    top = np.full((24, sheet.shape[1], 3), 28, np.uint8)
    top = _label(top, title)
    core.save_rgba(out_png, np.concatenate([top, sheet], 0) / 255.0)
    m = {"iou": round(float(iou), 4), "colour_error": round(cerr, 4), "colour_error_core": round(cerr_core, 4),
         "ref_px": int(ref_mask.sum()), "render_px": int(rmask.sum())}
    with open(out_png.replace(".png", ".json"), "w") as f:
        json.dump(m, f, indent=1)
    return m


def ssim_gray(a, b, mask=None):
    from skimage.metrics import structural_similarity as ssim
    ga = a[..., :3].mean(-1)
    gb = b[..., :3].mean(-1)
    s, full = ssim(ga, gb, data_range=1.0, full=True)
    if mask is not None and mask.any():
        return float(full[mask].mean())
    return float(s)


def look_at_cam(loc, target, ortho_scale=None, lens=60, res=(700, 1000), name="hv2_vcam"):
    cam = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    if ortho_scale:
        cam.type = "ORTHO"
        cam.ortho_scale = ortho_scale
    else:
        cam.type = "PERSP"
        cam.lens = lens
    cam.clip_start = 0.05
    cam.clip_end = 200
    obj = bpy.data.objects.get(name) or core.link(bpy.data.objects.new(name, cam))
    obj.location = loc
    d = Vector(target) - Vector(loc)
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc = bpy.context.scene
    sc.camera = obj
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    return obj
