"""Landmarks v3 Blender side: objects from Geo, multi-object UV atlas, painted-light QA material, renders at
the solved painting camera (with radial distortion warp), orthographic inset renders, GLB export."""
import math
import os
import sys
import tempfile

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))
from frlib import core  # noqa: E402

# material classes -> (atlas, roughness, metallic, double sided, alpha)
MAT_DEF = {
    "stone": (0.92, 0.0, False), "wood": (0.86, 0.0, False), "roof": (0.88, 0.0, False),
    "cloth": (0.95, 0.0, True), "rope": (0.95, 0.0, False), "metal": (0.55, 0.6, False),
    "ground": (1.0, 0.0, False), "water": (0.25, 0.0, False), "glow": (0.4, 0.0, False),
    "card": (0.9, 0.0, True),
}


def mat_class(m):
    return "card" if m.startswith("card") else m


def object_from_geo(name, geo, materials, smooth_mats=("cloth", "rope", "ground", "water")):
    """materials: dict class -> bpy material. Faces keep their fixed UVs (if any) in UV layer 'UVMap'."""
    V, F, M, Tg, UVf = geo.arrays()
    classes = sorted(set(mat_class(m) for m in M))
    slot = {c: i for i, c in enumerate(classes)}
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], [list(f) for f in F])
    if len(me.polygons) != len(F):
        raise RuntimeError(f"{name}: polygon count mismatch {len(me.polygons)} != {len(F)}")
    me.polygons.foreach_set("material_index", np.array([slot[mat_class(m)] for m in M], np.int32))
    for c in classes:
        me.materials.append(materials[c])
    uvl = me.uv_layers.new(name="UVMap")
    flat = []
    for f, uv in zip(F, UVf):
        if uv is None:
            flat += [(0.0, 0.0)] * len(f)
        else:
            flat += list(uv)
    uvl.data.foreach_set("uv", np.asarray(flat, np.float32).ravel())
    sm = np.array([mat_class(m) in smooth_mats for m in M])
    me.polygons.foreach_set("use_smooth", sm)
    me.update()
    o = bpy.data.objects.new(name, me)
    core.link(o)
    o["fixed_uv_faces"] = [i for i, uv in enumerate(UVf) if uv is not None][:0]
    o["tags"] = list(Tg)[:0]
    return o, np.array([u is not None for u in UVf]), list(M), list(Tg)


def atlas_uv(objs, fixed_masks, margin=0.004, angle=60.0):
    """Unique UV atlas shared by objs (multi-object edit). Faces flagged in fixed_masks keep their UVs
    (cards) and are excluded from the unwrap/pack (they live in another atlas)."""
    core.select_only(objs, objs[0])
    bpy.ops.object.mode_set(mode="EDIT")
    import bmesh
    for o, fixed in zip(objs, fixed_masks):
        bm = bmesh.from_edit_mesh(o.data)
        bm.faces.ensure_lookup_table()
        for f in bm.faces:
            f.select = not fixed[f.index]
        bmesh.update_edit_mesh(o.data)
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, margin=margin)
    bpy.ops.object.mode_set(mode="OBJECT")


def restore_fixed_uv(obj, geo):
    """Re-apply the fixed UVs (alpha cards) after the atlas unwrap/pack touched them."""
    V, F, M, Tg, UVf = geo.arrays()
    me = obj.data
    uvl = me.uv_layers["UVMap"]
    cur = np.empty(len(me.loops) * 2)
    uvl.data.foreach_get("uv", cur)
    cur = cur.reshape(-1, 2)
    li = 0
    for f, uv in zip(F, UVf):
        if uv is not None:
            cur[li:li + len(f)] = np.asarray(uv, float)
        li += len(f)
    uvl.data.foreach_set("uv", cur.astype(np.float32).ravel())
    me.update()


def mesh_tris(obj):
    """World verts, tris, per-corner uv (M,3,2), face normals, material slot per tri, polygon index per tri."""
    me = obj.data
    me.calc_loop_triangles()
    nv = len(me.vertices)
    V = np.empty(nv * 3)
    me.vertices.foreach_get("co", V)
    V = V.reshape(nv, 3)
    m = np.array(obj.matrix_world)
    V = V @ m[:3, :3].T + m[:3, 3]
    nt = len(me.loop_triangles)
    T = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", T)
    T = T.reshape(nt, 3)
    L = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get("loops", L)
    L = L.reshape(nt, 3)
    luv = np.empty(len(me.loops) * 2)
    me.uv_layers["UVMap"].data.foreach_get("uv", luv)
    UV = luv.reshape(-1, 2)[L]
    mi = np.empty(nt, np.int64)
    me.loop_triangles.foreach_get("material_index", mi)
    pi = np.empty(nt, np.int64)
    me.loop_triangles.foreach_get("polygon_index", pi)
    e1 = V[T[:, 1]] - V[T[:, 0]]
    e2 = V[T[:, 2]] - V[T[:, 0]]
    FN = np.cross(e1, e2)
    FN /= np.maximum(np.linalg.norm(FN, axis=1, keepdims=True), 1e-12)
    return V, T, UV, FN, mi, pi


def image_from_array(name, arr, colorspace="sRGB", alpha=False):
    h, w = arr.shape[:2]
    img = bpy.data.images.get(name)
    if img is not None:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, w, h, alpha=alpha)
    img.colorspace_settings.name = colorspace
    a = np.asarray(arr, np.float32)
    if a.shape[2] == 3:
        a = np.concatenate([a, np.ones((h, w, 1), np.float32)], 2)
    img.pixels.foreach_set(np.ascontiguousarray(a[::-1]).ravel())
    img.update()
    img.pack()
    return img


def load_image(path, colorspace="sRGB"):
    img = bpy.data.images.load(path, check_existing=False)
    img.name = os.path.splitext(os.path.basename(path))[0]
    img.colorspace_settings.name = colorspace
    img.pack()
    if img.size[0] > 0 and not img.has_data:
        _ = img.pixels[0]
    return img


def export_materials(prefix, col_img, nrm_img, card_img):
    mats = {}
    for c, (rough, metal, ds) in MAT_DEF.items():
        if c == "card":
            if card_img is None:
                continue
            m = core.material(f"{prefix}_card", base_tex=card_img, rough=rough, alpha_clip=0.5, double_sided=True)
        else:
            m = core.material(f"{prefix}_{c}", base_tex=col_img, normal_tex=nrm_img, rough=rough, metal=metal,
                              double_sided=ds, normal_strength=1.0)
            if c == "glow":
                bsdf = [n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"][0]
                bsdf.inputs["Emission Color"].default_value = (1.0, 0.72, 0.36, 1.0)
                bsdf.inputs["Emission Strength"].default_value = 2.0
        mats[c] = m
    return mats


# ----------------------------------------------------------------------------- painted QA material
PAINT_LIGHT_06 = (-0.55, -0.45, 0.70)   # art/06 key light: upper left, slightly toward the viewer


def painted_qa_material(src, k=0.35, light=PAINT_LIGHT_06):
    """Emission = albedo * mix(1, lambert, k); alpha clip from the texture alpha (cards)."""
    name = f"{src.name}_qa{k:.2f}"
    if bpy.data.materials.get(name):
        return bpy.data.materials[name]
    img = None
    for n in src.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image is not None and n.image.colorspace_settings.name != "Non-Color":
            img = n.image
            break
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
    L /= np.linalg.norm(L)
    dot.inputs[1].default_value = tuple(L)
    nt.links.new(geo.outputs["Normal"], dot.inputs[0])
    mx = nt.nodes.new("ShaderNodeMath")
    mx.operation = "MAXIMUM"
    mx.inputs[1].default_value = 0.0
    nt.links.new(dot.outputs["Value"], mx.inputs[0])
    lerp = nt.nodes.new("ShaderNodeMath")
    lerp.operation = "MULTIPLY_ADD"
    lerp.inputs[1].default_value = k
    lerp.inputs[2].default_value = 1.0 - k
    nt.links.new(mx.outputs["Value"], lerp.inputs[0])
    sc = nt.nodes.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    nt.links.new(tex.outputs["Color"], sc.inputs[0])
    nt.links.new(lerp.outputs["Value"], sc.inputs["Scale"])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(sc.outputs["Vector"], em.inputs["Color"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    gt = nt.nodes.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = 0.5
    nt.links.new(tex.outputs["Alpha"], gt.inputs[0])
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(gt.outputs["Value"], mix.inputs[0])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    m.use_backface_culling = False
    return m


def use_qa(objs, k=0.35, light=PAINT_LIGHT_06, on=True):
    for o in objs:
        for i, s in enumerate(o.material_slots):
            if on:
                s.link = "OBJECT"
                s.material = painted_qa_material(o.data.materials[i], k, light)
            else:
                s.link = "DATA"


def setup_render(samples=12):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 0
    sc.cycles.transparent_max_bounces = 32
    sc.cycles.use_adaptive_sampling = False
    sc.render.film_transparent = True
    sc.render.filter_size = 1.0
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    w = bpy.data.worlds.get("lm3_world") or bpy.data.worlds.new("lm3_world")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    return sc


def only(objs):
    keep = set(o.name for o in objs)
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = o.name not in keep


def render_rgba():
    tmp = os.path.join(tempfile.mkdtemp(), "frame.png")
    sc = bpy.context.scene
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.filepath = tmp
    bpy.ops.render.render(write_still=True)
    from PIL import Image
    return np.asarray(Image.open(tmp).convert("RGBA"), np.float64) / 255.0


def render_painting_cam(cam, W, H, objs, ss=2, pad=0.18):
    """Render objs as seen by the solved painting camera (undistorted pinhole, then radial-distortion warp
    to painting pixels). Returns RGBA (H, W, 4) at painting resolution."""
    import cv2
    only(objs)
    mx, my = int(W * pad), int(H * pad)
    RW, RH = (W + 2 * mx) * ss, (H + 2 * my) * ss
    f = cam.f * ss
    cx, cy = (cam.cx + mx) * ss, (cam.cy + my) * ss
    cd = bpy.data.cameras.get("lm3_cam") or bpy.data.cameras.new("lm3_cam")
    co = bpy.data.objects.get("lm3_cam") or core.link(bpy.data.objects.new("lm3_cam", cd))
    cd.type = "PERSP"
    cd.sensor_fit = "HORIZONTAL" if RW >= RH else "VERTICAL"
    cd.sensor_width = cd.sensor_height = 36.0
    cd.lens = f * 36.0 / max(RW, RH)
    cd.shift_x = (RW / 2.0 - cx) / max(RW, RH)
    cd.shift_y = (cy - RH / 2.0) / max(RW, RH)
    cd.clip_start = 0.1
    cd.clip_end = 2000
    R = cam.R
    rot = np.stack([R[0], -R[1], -R[2]], 1)
    M = np.eye(4)
    M[:3, :3] = rot
    M[:3, 3] = cam.centre
    co.matrix_world = Matrix(M.tolist())
    sc = bpy.context.scene
    sc.camera = co
    sc.render.resolution_x, sc.render.resolution_y = RW, RH
    sc.render.resolution_percentage = 100
    img = render_rgba()
    # painting pixel -> undistorted pixel -> render pixel
    mapx, mapy = cam.undistort_maps(W, H)
    mapx = (mapx + mx) * ss + (ss - 1) / 2.0
    mapy = (mapy + my) * ss + (ss - 1) / 2.0
    big = cv2.resize(img.astype(np.float32), None, fx=1, fy=1)
    # supersampled lookup: average ss x ss taps
    acc = np.zeros((H, W, 4), np.float32)
    for dy in range(ss):
        for dx in range(ss):
            ox, oy = (dx - (ss - 1) / 2.0), (dy - (ss - 1) / 2.0)
            acc += cv2.remap(big, mapx + ox, mapy + oy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                             borderValue=(0, 0, 0, 0))
    acc /= ss * ss
    rgb = acc[..., :3] / np.maximum(acc[..., 3:4], 1e-6)
    return np.concatenate([np.clip(rgb, 0, 1), acc[..., 3:4]], 2)


def ortho_render(objs, direction, up=(0, 0, 1), res=900, margin=1.02):
    """Orthographic render looking along `direction`; returns RGBA cropped to the alpha bbox."""
    only(objs)
    d = Vector(direction).normalized()
    lo, hi = core.bounds(objs)
    c = Vector(((lo + hi) / 2).tolist())
    size = float(np.linalg.norm(hi - lo))
    cd = bpy.data.cameras.get("lm3_ortho") or bpy.data.cameras.new("lm3_ortho")
    co = bpy.data.objects.get("lm3_ortho") or core.link(bpy.data.objects.new("lm3_ortho", cd))
    cd.type = "ORTHO"
    cd.ortho_scale = size * margin
    cd.clip_start = 0.01
    cd.clip_end = size * 4
    co.location = c - d * size * 2
    co.rotation_euler = d.to_track_quat("-Z", "Y" if abs(d.z) < 0.99 else "Y").to_euler()
    if abs(d.z) > 0.99:
        co.rotation_euler = (0, 0, 0)
    sc = bpy.context.scene
    sc.camera = co
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    rgba = render_rgba()
    a = rgba[..., 3] > 0.5
    ys, xs = np.nonzero(a)
    if len(xs) == 0:
        return rgba
    return rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def export_glb(path, objs, root_name):
    root = bpy.data.objects.new(root_name, None)
    core.link(root)
    for o in objs:
        o.parent = root
    bpy.context.view_layer.update()
    core.export_glb(path, [root] + list(objs), animations=False,
                    extra=dict(export_vertex_color="NONE", export_image_format="AUTO", export_morph=False))
    for o in objs:
        o.parent = None
    bpy.data.objects.remove(root, do_unlink=True)
    return path
