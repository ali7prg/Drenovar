"""Blender (bpy module) operations: retopology, LOD decimation, UV atlas, Cycles bakes.

Coordinates: the pipeline works in glTF space (+Y up, +X forward). Blender objects
are created with the same numbers (no axis conversion): Blender never exports here,
it only remeshes, unwraps and bakes, so its own up axis is irrelevant.
"""
import math

import bpy
import bmesh
import numpy as np


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 16
    sc.render.bake.use_pass_direct = False
    sc.render.bake.use_pass_indirect = False
    if sc.world is None:
        sc.world = bpy.data.worlds.new("World")


def to_object(name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", np.asarray(verts, np.float32).ravel())
    faces = np.asarray(faces, np.int32)
    me.loops.add(faces.size)
    me.loops.foreach_set("vertex_index", faces.ravel())
    me.polygons.add(len(faces))
    me.polygons.foreach_set("loop_start", np.arange(0, faces.size, 3, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(len(faces), 3, np.int32))
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def activate(ob):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)


def copy(ob, name):
    c = ob.copy()
    c.data = ob.data.copy()
    c.name = name
    bpy.context.scene.collection.objects.link(c)
    return c


def apply_mods(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)


def decimate(ob, target_tris):
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    if tris <= target_tris:
        return ob
    m = ob.modifiers.new("dec", "DECIMATE")
    m.decimate_type = "COLLAPSE"
    m.ratio = max(0.0005, target_tris / tris)
    m.use_collapse_triangulate = True
    apply_mods(ob)
    return ob


def clean_manifold(ob, merge=0.0005):
    activate(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=merge)
    bpy.ops.mesh.delete_loose()
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def voxel_remesh(ob, size):
    activate(ob)
    ob.data.remesh_voxel_size = size
    ob.data.use_remesh_fix_poles = True
    bpy.ops.object.voxel_remesh()


def quadriflow(ob, target_faces, seed=0):
    activate(ob)
    try:
        r = bpy.ops.object.quadriflow_remesh(target_faces=int(target_faces), use_mesh_symmetry=False,
                                             use_preserve_sharp=False, use_preserve_boundary=False,
                                             smooth_normals=False, mode="FACES", seed=seed)
    except RuntimeError as e:
        print("quadriflow failed", e)
        return False
    return "FINISHED" in r and len(ob.data.polygons) > 0


def triangulate(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def shade(ob, sharp_angle=None):
    me = ob.data
    me.shade_smooth()
    if sharp_angle is not None:
        me.set_sharp_from_angle(angle=math.radians(sharp_angle))


def smooth_verts(ob, iterations=2, factor=0.5):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    for _ in range(iterations):
        bmesh.ops.smooth_vert(bm, verts=bm.verts[:], factor=factor, use_axis_x=True, use_axis_y=True,
                              use_axis_z=True)
    bm.to_mesh(ob.data)
    bm.free()


def project_onto(ob, target, max_dist=0.05):
    """Snaps low-poly vertices onto the high-res surface (keeps the retopo on the sculpt)."""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    tree = BVHTree.FromObject(target, dg)
    for v in ob.data.vertices:
        loc, _n, _i, d = tree.find_nearest(v.co, max_dist)
        if loc is not None:
            v.co = loc
    ob.data.update()


def uv_xatlas(ob, resolution, padding=4, max_cost=3.0):
    """Automatic charting + packing with xatlas (larger, cleaner charts than smart projection)."""
    import xatlas
    triangulate(ob)
    me = ob.data
    co = np.zeros(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    loops = np.zeros(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", loops)
    faces = loops.reshape(-1, 3)
    atlas = xatlas.Atlas()
    atlas.add_mesh(co, faces)
    copt = xatlas.ChartOptions()
    copt.max_cost = max_cost
    copt.max_iterations = 2
    copt.normal_seam_weight = 4.0
    copt.straightness_weight = 6.0
    popt = xatlas.PackOptions()
    popt.resolution = resolution
    popt.padding = padding
    popt.bilinear = True
    popt.rotate_charts = True
    popt.bruteForce = False
    atlas.generate(copt, popt)
    _vm, ind, uvs = atlas[0]
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv_loops = uvs[ind.reshape(-1)]  # per loop, in face order
    uv_loops = uv_loops.astype(np.float32)
    me.uv_layers.active.data.foreach_set("uv", uv_loops.ravel())
    return atlas.chart_count, atlas.utilization


def uv_atlas(objs, margin=0.004, weights=None, angle=66.0):
    """Smart-projects every object, scales islands by texel weight, packs all into one atlas."""
    for ob in objs:
        if not ob.data.uv_layers:
            ob.data.uv_layers.new(name="UVMap")
    for ob in objs:
        activate(ob)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, area_weight=0.0,
                                 correct_aspect=True, scale_to_bounds=False)
        bpy.ops.object.mode_set(mode="OBJECT")
    # equalise texel density across objects (smart_project normalises each object separately)
    for ob in objs:
        me = ob.data
        uv = np.zeros(len(me.loops) * 2, np.float32)
        me.uv_layers.active.data.foreach_get("uv", uv)
        uv = uv.reshape(-1, 2)
        area3 = sum(p.area for p in me.polygons)
        area2 = 0.0
        for p in me.polygons:
            ls = list(p.loop_indices)
            for i in range(1, len(ls) - 1):
                a, b, c = uv[ls[0]], uv[ls[i]], uv[ls[i + 1]]
                area2 += abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) * 0.5
        w = (weights or {}).get(ob.name, 1.0)
        s = math.sqrt(area3 / max(area2, 1e-12)) * w
        uv *= s
        me.uv_layers.active.data.foreach_set("uv", uv.ravel())
    # pack all objects together
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(udim_source="CLOSEST_UDIM", rotate=True, rotate_method="ANY", scale=True,
                            merge_overlap=False, margin_method="FRACTION", margin=margin, pin=False,
                            shape_method="CONCAVE")
    bpy.ops.object.mode_set(mode="OBJECT")


def bake_image(name, size, float_buffer=True, color=(0.5, 0.5, 1.0, 1.0)):
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=float_buffer)
    img.generated_color = color
    img.colorspace_settings.name = "Non-Color"
    return img


def _target_material(ob, img):
    mat = bpy.data.materials.new(ob.name + "_bake")
    mat.use_nodes = True
    nt = mat.node_tree
    node = nt.nodes.new("ShaderNodeTexImage")
    node.image = img
    nt.nodes.active = node
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    return mat


def bake_normal(low, highs, img, extrusion=0.02, ray=0.06, margin=8):
    sc = bpy.context.scene
    sc.cycles.samples = 1
    _target_material(low, img)
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for h in highs:
        h.select_set(True)
        h.hide_render = False
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", use_selected_to_active=True,
                        cage_extrusion=extrusion, max_ray_distance=ray, margin=margin, use_clear=False,
                        target="IMAGE_TEXTURES")


def bake_ao(low, img, samples=48, distance=0.45, margin=8):
    sc = bpy.context.scene
    sc.cycles.samples = samples
    sc.world.light_settings.distance = distance
    _target_material(low, img)
    activate(low)
    bpy.ops.object.bake(type="AO", margin=margin, use_clear=False, target="IMAGE_TEXTURES")


def image_array(img):
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(h, w, 4)[::-1]  # top row first


def mesh_arrays(ob):
    """Unique render vertices (split on UV seams / sharp edges) with tangents, plus triangles.
    Returns dict(pos, nrm, uv, tan(Nx4), idx, src(vertex index), corner_count)."""
    me = ob.data
    triangulate(ob)
    me.calc_tangents()
    n_loops = len(me.loops)
    vi = np.zeros(n_loops, np.int32)
    me.loops.foreach_get("vertex_index", vi)
    co = np.zeros(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    nrm = np.zeros(n_loops * 3, np.float32)
    me.corner_normals.foreach_get("vector", nrm)
    nrm = nrm.reshape(-1, 3)
    uv = np.zeros(n_loops * 2, np.float32)
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    tan = np.zeros(n_loops * 3, np.float32)
    me.loops.foreach_get("tangent", tan)
    tan = tan.reshape(-1, 3)
    sign = np.zeros(n_loops, np.float32)
    me.loops.foreach_get("bitangent_sign", sign)
    me.free_tangents()
    key = np.concatenate([vi[:, None].astype(np.float64), np.round(uv * 1e5), np.round(nrm * 1e4),
                          sign[:, None]], 1)
    _u, first, inverse = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inverse = inverse.ravel()
    pos = co[vi[first]]
    out_n = nrm[first]
    out_uv = uv[first]
    # average tangents of merged corners
    t_acc = np.zeros((len(first), 3), np.float64)
    np.add.at(t_acc, inverse, tan)
    t_acc /= np.maximum(np.linalg.norm(t_acc, axis=1, keepdims=True), 1e-9)
    tans = np.concatenate([t_acc.astype(np.float32), sign[first][:, None]], 1)
    loops_of_tri = np.zeros(len(me.polygons) * 3, np.int32)
    for p in me.polygons:
        ls = list(p.loop_indices)
        loops_of_tri[p.index * 3:p.index * 3 + 3] = ls
    idx = inverse[loops_of_tri].reshape(-1, 3).astype(np.int32)
    part = np.zeros(len(co), np.int32)
    if me.attributes.get("part_id") is not None:
        me.attributes["part_id"].data.foreach_get("value", part)
    uv_gl = out_uv.copy()
    uv_gl[:, 1] = 1.0 - uv_gl[:, 1]
    return {"pos": pos, "nrm": out_n, "uv": uv_gl, "tan": tans, "idx": idx, "src": vi[first],
            "part": part[vi[first]]}
