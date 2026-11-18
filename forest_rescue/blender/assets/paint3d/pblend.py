"""Blender side of the painted reconstruction: objects from geom.Mesh, export/QA materials,
reference-camera renders with the painted-light model, metrics + comparison sheets."""
import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
sys.path.append(os.path.abspath(os.path.join(HERE, "..", "forest")))
from frlib import core, render  # noqa: E402

# painting key light (upper-left-front) used for the painted-light QA shading
PAINT_LIGHT = (-0.45, -0.55, 0.70)


def obj_from_mesh(name, mesh, materials, col=None):
    V, T, UV, C, N, M = mesh.arrays()
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], T.tolist())
    if len(me.polygons) != len(T):
        raise RuntimeError(f"{name}: polygon count mismatch")
    uvl = me.uv_layers.new(name="UVMap")
    uvl.data.foreach_set("uv", UV[T].reshape(-1).astype(np.float32))
    me.polygons.foreach_set("material_index", M.astype(np.int32))
    for m in materials:
        me.materials.append(m)
    ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    ca.data.foreach_set("color", np.clip(C, 0, 1).astype(np.float32).ravel())
    me.color_attributes.active_color = ca
    me.color_attributes.render_color_index = 0
    me.shade_smooth()
    me.normals_split_custom_set_from_vertices([tuple(v) for v in N])
    me.update()
    o = bpy.data.objects.new(name, me)
    core.link(o, col)
    return o


_IMG = {}


def image(path, colorspace="sRGB", reload=False):
    key = (path, colorspace)
    if key in _IMG and not reload:
        try:
            _IMG[key].name
            return _IMG[key]
        except ReferenceError:
            pass
    img = bpy.data.images.load(path, check_existing=False)
    img.name = os.path.splitext(os.path.basename(path))[0]
    img.colorspace_settings.name = colorspace
    img.pack()
    _IMG[key] = img
    return img


def export_material(name, base_path, alpha_clip=None, normal_path=None, rough_path=None, double_sided=False):
    m = bpy.data.materials.get(name)
    if m:
        return m
    return core.material(name, base_tex=image(base_path), alpha_clip=alpha_clip,
                         normal_tex=image(normal_path, "Non-Color") if normal_path else None,
                         rough_tex=image(rough_path, "Non-Color") if rough_path else None,
                         rough=0.9, double_sided=double_sided)


EDGE_FADE = (0.10, 0.30)   # |dot(face normal, view)| range faded out on alpha-tested cards


def painted_material(src, k=0.4, light=PAINT_LIGHT, name=None):
    """QA material = the game look: emission = albedo * mix(1, max(N.L,0), k) * mix(0.42, 1, AO^2);
    alpha-tested cards also fade out when seen edge-on (|dot(true normal, view)| < EDGE_FADE)."""
    name = name or f"{src.name}_paint{k:.2f}"
    m = bpy.data.materials.get(name)
    if m:
        return m
    img = None
    for n in src.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image is not None and n.image.colorspace_settings.name != "Non-Color":
            img = n.image
            break
    foliage = src.get("gltf_alpha_mode") == "MASK"
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    L = np.asarray(light, float)
    L = L / np.linalg.norm(L)
    dot.inputs[1].default_value = tuple(L)
    nt.links.new(geo.outputs["Normal"], dot.inputs[0])
    mx = nt.nodes.new("ShaderNodeMath")
    mx.operation = "MAXIMUM"
    mx.inputs[1].default_value = 0.0
    nt.links.new(dot.outputs["Value"], mx.inputs[0])
    lerp = nt.nodes.new("ShaderNodeMath")       # 1 - k + k * lambert
    lerp.operation = "MULTIPLY_ADD"
    lerp.inputs[1].default_value = k
    lerp.inputs[2].default_value = 1.0 - k
    nt.links.new(mx.outputs["Value"], lerp.inputs[0])
    # AO from COLOR_0 alpha, world-layer formula mix(0.42, 1, ao^2)
    va = nt.nodes.new("ShaderNodeVertexColor")
    va.layer_name = "Col"
    sq = nt.nodes.new("ShaderNodeMath")
    sq.operation = "POWER"
    sq.inputs[1].default_value = 2.0
    nt.links.new(va.outputs["Alpha"], sq.inputs[0])
    aom = nt.nodes.new("ShaderNodeMath")
    aom.operation = "MULTIPLY_ADD"
    aom.inputs[1].default_value = 0.58
    aom.inputs[2].default_value = 0.42
    nt.links.new(sq.outputs["Value"], aom.inputs[0])
    shade = nt.nodes.new("ShaderNodeMath")
    shade.operation = "MULTIPLY"
    nt.links.new(lerp.outputs["Value"], shade.inputs[0])
    nt.links.new(aom.outputs["Value"], shade.inputs[1])
    sc = nt.nodes.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    nt.links.new(tex.outputs["Color"], sc.inputs[0])
    nt.links.new(shade.outputs["Value"], sc.inputs["Scale"])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(sc.outputs["Vector"], em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    alpha_src = tex.outputs["Alpha"]
    if foliage:
        d2 = nt.nodes.new("ShaderNodeVectorMath")
        d2.operation = "DOT_PRODUCT"
        nt.links.new(geo.outputs["True Normal"], d2.inputs[0])
        nt.links.new(geo.outputs["Incoming"], d2.inputs[1])
        ab = nt.nodes.new("ShaderNodeMath")
        ab.operation = "ABSOLUTE"
        nt.links.new(d2.outputs["Value"], ab.inputs[0])
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.interpolation_type = "SMOOTHSTEP"
        mr.inputs["From Min"].default_value = EDGE_FADE[0]
        mr.inputs["From Max"].default_value = EDGE_FADE[1]
        nt.links.new(ab.outputs["Value"], mr.inputs["Value"])
        am = nt.nodes.new("ShaderNodeMath")
        am.operation = "MULTIPLY"
        nt.links.new(tex.outputs["Alpha"], am.inputs[0])
        nt.links.new(mr.outputs["Result"], am.inputs[1])
        alpha_src = am.outputs["Value"]
    gt = nt.nodes.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = 0.5
    nt.links.new(alpha_src, gt.inputs[0])
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(gt.outputs["Value"], mix.inputs[0])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    m.use_backface_culling = False
    return m


KMAP = {}     # material name -> paintedLightMix override (e.g. lf_foliage_vol)


def use_painted(objs, k=0.4, light=PAINT_LIGHT, on=True, tag=""):
    for o in objs:
        if o.type != "MESH":
            continue
        for i, s in enumerate(o.material_slots):
            src = o.data.materials[i]
            kk = KMAP.get(src.name, k) if k > 0 else 0.0
            if on:
                s.link = "OBJECT"
                s.material = painted_material(src, kk, light, name=f"{src.name}_paint{kk:.2f}{tag}")
            else:
                s.link = "DATA"


def setup_render(samples=16, res=None):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 0
    sc.cycles.transparent_max_bounces = 64
    sc.cycles.use_adaptive_sampling = False
    sc.render.film_transparent = True
    sc.render.filter_size = 0.8
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    world = bpy.data.worlds.get("p3d_world") or bpy.data.worlds.new("p3d_world")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    if res:
        sc.render.resolution_x, sc.render.resolution_y = res
        sc.render.resolution_percentage = 100
    return sc


def only(objs):
    keep = set(o.name for o in objs)
    for o in bpy.data.objects:
        if o.type in ("MESH", "CURVE"):
            o.hide_render = o.name not in keep


def render_view(view, objs, path=None):
    only(objs)
    render.camera_for_view(view, distance=60.0)
    return render.render_rgba(path)


def ortho_frame(objs, pitch_deg, yaw_deg, res=(1400, 800), margin=1.06):
    """Orthographic camera at pitch/yaw framing objs (pitch 90 = top)."""
    from mathutils import Vector
    lo, hi = core.bounds(objs)
    c = (lo + hi) / 2
    p, y = math.radians(pitch_deg), math.radians(yaw_deg)
    d = Vector((math.sin(y) * math.cos(p), math.cos(y) * math.cos(p), -math.sin(p)))
    size = float(np.linalg.norm(hi - lo))
    loc = Vector(c) - d * size * 2
    cam = render.perspective_camera(tuple(loc), tuple(c), res=res, ortho_scale=1.0)
    if pitch_deg > 89:
        cam.rotation_euler = (0, 0, math.radians(-yaw_deg))
    bpy.context.view_layer.update()
    pts = []
    for o in objs:
        v, _, _, _ = core.mesh_arrays(o, evaluated=True, world=True)
        pts.append(v[:: max(1, len(v) // 3000)])
    P = np.concatenate(pts)
    R = np.array(cam.matrix_world.to_3x3())
    q = (P - np.array(cam.location)) @ R
    w = q[:, 0].max() - q[:, 0].min()
    h = q[:, 1].max() - q[:, 1].min()
    cam.data.ortho_scale = max(w, h * res[0] / res[1]) * margin
    cx = (q[:, 0].max() + q[:, 0].min()) / 2
    cy = (q[:, 1].max() + q[:, 1].min()) / 2
    cam.location = cam.location + cam.matrix_world.to_3x3() @ Vector((cx, cy, 0))
    return cam


# ------------------------------------------------------------------ metrics + sheets

def metrics(ref_img, ref_mask, rgba, bg):
    from skimage.metrics import structural_similarity
    a = rgba[..., 3:4]
    comp = rgba[..., :3] * a + np.asarray(bg)[None, None] * (1 - a)
    rm = rgba[..., 3] > 0.5
    inter = (ref_mask & rm).sum()
    union = (ref_mask | rm).sum()
    iou = float(inter) / max(1.0, float(union))
    both = ref_mask & rm
    err = float(np.abs(comp[both] - ref_img[both]).mean()) if both.any() else 1.0
    refc = np.where(ref_mask[..., None], ref_img, np.asarray(bg)[None, None])
    g1 = refc @ np.array([0.299, 0.587, 0.114])
    g2 = comp @ np.array([0.299, 0.587, 0.114])
    ys, xs = np.nonzero(ref_mask | rm)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    ssim = float(structural_similarity(g1[y0:y1, x0:x1], g2[y0:y1, x0:x1], data_range=1.0))
    return dict(iou=round(iou, 4), colour_err=round(err, 4), ssim=round(ssim, 4),
                ref_px=int(ref_mask.sum()), render_px=int(rm.sum())), comp, rm


def label(img_u8, text, xy=(6, 4)):
    from PIL import Image, ImageDraw
    im = Image.fromarray(img_u8)
    dr = ImageDraw.Draw(im)
    x, y = xy
    dr.rectangle([x - 3, y - 2, x + 6 * len(text) + 6, y + 12], fill=(20, 20, 20))
    dr.text((x, y), text, fill=(255, 240, 200))
    return np.asarray(im)


def compare_sheet(ref_img, ref_mask, rgba, bg, out_png, title, scale=2):
    import cv2
    m, comp, rm = metrics(ref_img, ref_mask, rgba, bg)
    diff = np.repeat((ref_img.mean(2, keepdims=True) * 0.5 + 0.35), 3, 2)
    both = ref_mask & rm
    diff[both] = diff[both] * 0.5 + np.array([0.15, 0.55, 0.15]) * 0.5
    diff[ref_mask & ~rm] = (0.85, 0.15, 0.15)
    diff[~ref_mask & rm] = (0.15, 0.3, 0.9)
    heat = np.abs(comp - ref_img).mean(2)
    heat = np.clip(heat / 0.25, 0, 1)
    hm = cv2.applyColorMap((heat * 255).astype(np.uint8), cv2.COLORMAP_INFERNO)[..., ::-1] / 255.0
    hm[~(ref_mask | rm)] *= 0.25
    panels = []
    refc = np.where(ref_mask[..., None], ref_img, ref_img)
    for img, txt in ((refc, "reference (art)"), (comp, "render (painted-light)"),
                     (diff, f"IoU {m['iou']:.3f}"), (hm, f"|err| {m['colour_err']:.3f} SSIM {m['ssim']:.3f}")):
        u8 = (np.clip(img, 0, 1) * 255).astype(np.uint8)
        if scale != 1:
            u8 = cv2.resize(u8, (u8.shape[1] * scale, u8.shape[0] * scale), interpolation=cv2.INTER_NEAREST)
        panels.append(label(u8, txt))
    sheet = np.concatenate(panels, 1)
    top = np.full((24, sheet.shape[1], 3), 28, np.uint8)
    top = label(top, title)
    core.save_rgba(out_png, np.concatenate([top, sheet], 0) / 255.0)
    core.write_json(out_png.replace(".png", ".json"), m)
    return m


def save_shot(rgba, path, bg=(0.86, 0.82, 0.76), text=None):
    img = rgba[..., :3] * rgba[..., 3:4] + np.asarray(bg)[None, None] * (1 - rgba[..., 3:4])
    u8 = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    if text:
        u8 = label(u8, text)
    core.save_rgba(path, u8 / 255.0)
    return u8


# ------------------------------------------------------------------ acceptance checks (55 deg / top)

def crown_checks(obj, out_prefix, res=700):
    """Top coverage of the crown disc and see-through holes at 55 deg from 4 yaws (alpha renders)."""
    import cv2
    from scipy import ndimage as ndi
    from frlib import render as frr
    res_d = {}
    only([obj])
    ortho_frame([obj], 90, 0, res=(res, res), margin=1.04)
    rgba = frr.render_rgba()
    a = rgba[..., 3] > 0.5
    pts = np.argwhere(a)
    hull = cv2.convexHull(pts[:, ::-1].astype(np.int32))
    disc = np.zeros(a.shape, np.uint8)
    cv2.fillConvexPoly(disc, hull, 1)
    disc = disc.astype(bool)
    diam = np.sqrt(disc.sum() / np.pi) * 2
    inner = ndi.binary_erosion(disc, iterations=max(1, int(0.04 * diam)))
    cov = float(a[inner].mean())
    img = save_shot(rgba, out_prefix + "_top.png", bg=(0.9, 0.2, 0.9), text=f"top: crown-disc coverage {cov:.3f}")
    res_d["top_coverage"] = round(cov, 4)
    holes = {}
    shots = []
    for yaw in (0, 90, 180, 270):
        only([obj])
        ortho_frame([obj], 55, yaw, res=(res, res), margin=1.04)
        rgba = frr.render_rgba()
        a = rgba[..., 3] > 0.5
        filled = ndi.binary_fill_holes(ndi.binary_closing(a, iterations=2))
        rows = np.nonzero(filled.any(1))[0]
        r0, r1 = rows.min(), rows.max()
        crown = filled.copy()
        crown[int(r0 + 0.72 * (r1 - r0)):] = False          # crown part (exclude the trunk zone at the bottom)
        size = np.sqrt(crown.sum())
        crown = ndi.binary_erosion(crown, iterations=max(1, int(0.035 * size)))
        hf = float((~a[crown]).mean()) if crown.any() else 0.0
        holes[str(yaw)] = round(hf, 4)
        shots.append(save_shot(rgba, "/tmp/_h.png", bg=(0.9, 0.2, 0.9), text=f"55deg yaw {yaw}: holes {hf:.3f}"))
    core.save_rgba(out_prefix + "_55holes.png", np.concatenate(shots, 1) / 255.0)
    res_d["holes_55"] = holes
    return res_d
