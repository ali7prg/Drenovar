"""Scene, mesh, material, baking and export helpers (bpy 5.x)."""
import json
import math
import os

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector


# --------------------------------------------------------------------------- scene

def reset(fps=30):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = fps
    scene.render.fps_base = 1.0
    return scene


def collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    return col


def link(obj, col=None):
    (col or bpy.context.scene.collection).objects.link(obj)
    return obj


def select_only(objs, active=None):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or (objs[0] if objs else None)


def apply_transforms(obj, location=True, rotation=True, scale=True):
    select_only([obj])
    bpy.ops.object.transform_apply(location=location, rotation=rotation, scale=scale)


# --------------------------------------------------------------------------- meshes

def mesh_object(name, verts, faces, uvs=None, col=None, smooth=True, uv_name="UVMap"):
    """Create an object from numpy vertices (N,3) and faces (M,k) or list of lists.

    uvs: optional per-loop UV array (sum(len(face)),2) in face-loop order.
    """
    verts = np.asarray(verts, dtype=np.float64)
    if isinstance(faces, np.ndarray):
        faces_list = faces.astype(np.int64).tolist()
    else:
        faces_list = [list(map(int, f)) for f in faces]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts.tolist(), [], faces_list)
    me.validate(clean_customdata=False)
    if uvs is not None:
        layer = me.uv_layers.new(name=uv_name)
        layer.data.foreach_set("uv", np.asarray(uvs, dtype=np.float32).ravel())
    if smooth:
        me.shade_smooth()
    me.update()
    obj = bpy.data.objects.new(name, me)
    link(obj, col)
    return obj


def mesh_arrays(obj, evaluated=True, world=True):
    """Return (verts (N,3), tris (M,3), loop_uv (M,3,2) or None, vert_normals (N,3)).

    Triangulates through loop_triangles; uses the evaluated (modifier) mesh by default.
    """
    deps = bpy.context.evaluated_depsgraph_get()
    src = obj.evaluated_get(deps) if evaluated else obj
    me = src.to_mesh()
    me.calc_loop_triangles()
    nv = len(me.vertices)
    verts = np.empty(nv * 3, dtype=np.float64)
    me.vertices.foreach_get("co", verts)
    verts = verts.reshape(nv, 3)
    normals = np.empty(nv * 3, dtype=np.float64)
    me.vertices.foreach_get("normal", normals)
    normals = normals.reshape(nv, 3)
    nt = len(me.loop_triangles)
    tris = np.empty(nt * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", tris)
    tris = tris.reshape(nt, 3)
    loops = np.empty(nt * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("loops", loops)
    loops = loops.reshape(nt, 3)
    uv = None
    if me.uv_layers.active is not None:
        nl = len(me.loops)
        luv = np.empty(nl * 2, dtype=np.float64)
        me.uv_layers.active.data.foreach_get("uv", luv)
        luv = luv.reshape(nl, 2)
        uv = luv[loops]
    if world:
        m = np.array(obj.matrix_world)
        verts = verts @ m[:3, :3].T + m[:3, 3]
        nm = np.linalg.inv(m[:3, :3]).T
        normals = normals @ nm.T
        normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
    src.to_mesh_clear()
    return verts, tris, uv, normals


def tri_count(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    ev.to_mesh_clear()
    return n


def join(objs, name=None):
    select_only(objs, objs[0])
    bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    if name:
        obj.name = name
        obj.data.name = name
    return obj


def decimate_to(obj, target_tris, name=None, copy=True, symmetric_axis=None):
    """Collapse-decimate a copy of obj down to roughly target_tris triangles (applied)."""
    if copy:
        new = obj.copy()
        new.data = obj.data.copy()
        new.animation_data_clear()
        for c in obj.users_collection:
            c.objects.link(new)
        obj = new
    if name:
        obj.name = name
        obj.data.name = name
    current = tri_count(obj)
    if current > target_tris:
        mod = obj.modifiers.new("decimate", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = max(0.01, target_tris / current)
        mod.use_collapse_triangulate = True
        if symmetric_axis:
            mod.use_symmetry = True
            mod.symmetry_axis = symmetric_axis
        # keep the armature modifier (if any) after decimate
        select_only([obj])
        while obj.modifiers.find("decimate") > 0:
            bpy.ops.object.modifier_move_up(modifier="decimate")
        bpy.ops.object.modifier_apply(modifier="decimate")
    return obj


def remesh_voxel(obj, size):
    mod = obj.modifiers.new("vox", "REMESH")
    mod.mode = "VOXEL"
    mod.voxel_size = size
    mod.use_smooth_shade = True
    select_only([obj])
    bpy.ops.object.modifier_apply(modifier="vox")
    return obj


def smooth_corrective(obj, factor=0.5, iterations=5):
    mod = obj.modifiers.new("csmooth", "CORRECTIVE_SMOOTH")
    mod.factor = factor
    mod.iterations = iterations
    mod.use_only_smooth = True
    mod.rest_source = "ORCO"
    select_only([obj])
    bpy.ops.object.modifier_apply(modifier="csmooth")


def smart_uv(obj, angle=66.0, margin=0.004, area_weight=0.0):
    select_only([obj])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin,
                             area_weight=area_weight, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def pack_uv(obj, margin=0.003, rotate=True):
    select_only([obj])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=rotate, margin=margin)
    bpy.ops.object.mode_set(mode="OBJECT")


# --------------------------------------------------------------------------- images & materials

def save_rgba(path, arr):
    """Save float [0,1] array (H,W,3|4), row 0 = top, to PNG (8-bit)."""
    from PIL import Image
    a = np.clip(np.asarray(arr, dtype=np.float64), 0.0, 1.0)
    a = (a * 255.0 + 0.5).astype(np.uint8)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    mode = "RGBA" if a.shape[2] == 4 else "RGB"
    Image.fromarray(a, mode).save(path, optimize=True)
    return path


def load_image(path, colorspace="sRGB", name=None):
    img = bpy.data.images.load(path, check_existing=True)
    if name:
        img.name = name
    img.colorspace_settings.name = colorspace
    return img


def new_image(name, size, alpha=False, colorspace="sRGB", color=(0.5, 0.5, 0.5, 1.0)):
    w, h = (size, size) if isinstance(size, int) else size
    img = bpy.data.images.new(name, w, h, alpha=alpha, float_buffer=False)
    img.generated_color = color
    img.colorspace_settings.name = colorspace
    return img


def image_to_numpy(img):
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    return buf.reshape(h, w, 4)[::-1]  # row 0 = top


def numpy_to_image(img, arr):
    h, w = arr.shape[:2]
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.ones((h, w, 1))], axis=2)
    img.pixels.foreach_set(np.ascontiguousarray(arr[::-1], dtype=np.float32).ravel())
    img.update()


def material(name, base=(0.8, 0.8, 0.8, 1.0), rough=0.8, metal=0.0, base_tex=None,
             rough_tex=None, metal_tex=None, normal_tex=None, normal_strength=1.0,
             alpha_clip=None, alpha_blend=False, emission=None, emission_strength=1.0,
             double_sided=False, uv_map=None):
    """Principled material wired so the glTF exporter writes proper PBR channels.

    *_tex: bpy.types.Image (base sRGB; rough/metal/normal Non-Color).
    alpha_clip: cutoff (MASK) using base image alpha.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (250, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    uv_node = None
    if uv_map:
        uv_node = nt.nodes.new("ShaderNodeUVMap")
        uv_node.uv_map = uv_map
        uv_node.location = (-700, 0)

    def tex(img, y, non_color=False):
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        node.location = (-350, y)
        node.interpolation = "Linear"
        if non_color:
            img.colorspace_settings.name = "Non-Color"
        if uv_node:
            nt.links.new(uv_node.outputs["UV"], node.inputs["Vector"])
        return node

    if base_tex is not None:
        n = tex(base_tex, 300)
        nt.links.new(n.outputs["Color"], bsdf.inputs["Base Color"])
        if alpha_clip is not None:
            # glTF exporter recognises alpha = 1 - (A < cutoff) as alphaMode MASK + alphaCutoff
            lt = nt.nodes.new("ShaderNodeMath")
            lt.operation = "LESS_THAN"
            lt.location = (-60, 420)
            lt.inputs[1].default_value = float(alpha_clip)
            inv = nt.nodes.new("ShaderNodeMath")
            inv.operation = "SUBTRACT"
            inv.location = (90, 420)
            inv.inputs[0].default_value = 1.0
            nt.links.new(n.outputs["Alpha"], lt.inputs[0])
            nt.links.new(lt.outputs["Value"], inv.inputs[1])
            nt.links.new(inv.outputs["Value"], bsdf.inputs["Alpha"])
        elif alpha_blend:
            nt.links.new(n.outputs["Alpha"], bsdf.inputs["Alpha"])
    else:
        bsdf.inputs["Base Color"].default_value = base
    if rough_tex is not None:
        n = tex(rough_tex, 0, True)
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        sep.location = (-80, 0)
        nt.links.new(n.outputs["Color"], sep.inputs["Color"])
        nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
        if metal_tex is rough_tex:
            nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    else:
        bsdf.inputs["Roughness"].default_value = rough
    if metal_tex is not None and metal_tex is not rough_tex:
        n = tex(metal_tex, -150, True)
        nt.links.new(n.outputs["Color"], bsdf.inputs["Metallic"])
    elif metal_tex is None:
        bsdf.inputs["Metallic"].default_value = metal
    if normal_tex is not None:
        n = tex(normal_tex, -350, True)
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.location = (0, -350)
        nm.inputs["Strength"].default_value = normal_strength
        if uv_map:
            nm.uv_map = uv_map
        nt.links.new(n.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if emission is not None:
        bsdf.inputs["Emission Color"].default_value = emission
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    if alpha_clip is not None:
        mat["gltf_alpha_mode"] = "MASK"
        mat["gltf_alpha_cutoff"] = alpha_clip
        mat.surface_render_method = "DITHERED"
    elif alpha_blend:
        mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = not double_sided
    return mat


def assign(obj, mat, slot=None):
    if slot is None:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
    else:
        while len(obj.data.materials) <= slot:
            obj.data.materials.append(None)
        obj.data.materials[slot] = mat


# --------------------------------------------------------------------------- baking (Cycles CPU)

def bake(obj, bake_type, image, margin=16, samples=4, normal_space="TANGENT", selected_to_active=None,
         cage_extrusion=0.02, max_ray_distance=0.0, pass_filter=None):
    """Bake into `image` for every material of obj (image node must be active in each material).

    bake_type: NORMAL | AO | DIFFUSE | ROUGHNESS | EMIT | COMBINED ...
    selected_to_active: optional high-poly source object.
    """
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.render.bake.margin = margin
    scene.render.bake.margin_type = "EXTEND"
    scene.render.bake.normal_space = normal_space
    added = []
    for slot in obj.material_slots:
        mat = slot.material
        if mat is None:
            continue
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = image
        node.name = "__bake_target__"
        mat.node_tree.nodes.active = node
        added.append((mat, node))
    if selected_to_active is not None:
        select_only([selected_to_active, obj], obj)
        scene.render.bake.use_selected_to_active = True
        scene.render.bake.cage_extrusion = cage_extrusion
        scene.render.bake.max_ray_distance = max_ray_distance
    else:
        select_only([obj], obj)
        scene.render.bake.use_selected_to_active = False
    kwargs = {"type": bake_type}
    if pass_filter is not None:
        kwargs["pass_filter"] = pass_filter
    bpy.ops.object.bake(**kwargs)
    for mat, node in added:
        mat.node_tree.nodes.remove(node)
    return image


# --------------------------------------------------------------------------- export & bookkeeping

def export_glb(path, objects, animations=True, image_format="AUTO", jpeg_quality=88,
               apply_modifiers=True, extra=None):
    """Export selected objects (with their armature parents) to a binary glTF."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    sel = list(objects)
    select_only(sel, sel[0])
    kwargs = dict(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=apply_modifiers,
        export_animations=animations,
        export_animation_mode="ACTIONS",
        export_force_sampling=True,
        export_optimize_animation_size=True,
        export_skins=True,
        export_influence_nb=4,
        export_all_influences=False,
        export_def_bones=True,
        export_leaf_bone=False,
        export_image_format=image_format,
        export_jpeg_quality=jpeg_quality,
        export_image_quality=jpeg_quality,
        export_materials="EXPORT",
        export_extras=True,
        export_tangents=False,
        export_morph=False,
        export_reset_pose_bones=True,
        export_rest_position_armature=True,
    )
    if extra:
        kwargs.update(extra)
    bpy.ops.export_scene.gltf(**kwargs)
    return path


def save_blend(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    return path


def write_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def bounds(objs):
    pts = []
    deps = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        if o.type != "MESH":
            continue
        ev = o.evaluated_get(deps)
        for c in ev.bound_box:
            pts.append(ev.matrix_world @ Vector(c))
    a = np.array([tuple(p) for p in pts])
    return a.min(axis=0), a.max(axis=0)
