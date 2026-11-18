"""Blender-side helpers for the forest kit: MeshData -> objects, materials, export, metadata."""
import json
import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))   # forest_rescue/blender (frlib)
from frlib import core, paths  # noqa: E402

import glbx  # noqa: E402

GROUP = "forest"
RUNTIME_DIR = os.path.join(paths.RUNTIME, GROUP)
TEX_MASTER_DIR = os.path.join(paths.TEXTURE_SOURCES, GROUP)

# runtime texture files shared by every forest GLB (external URIs, relative to the GLB)
FOLIAGE_ATLAS = "lf_foliage_atlas.png"


def bark_files(kind):
    return (f"lf_bark_{kind}_c.jpg", f"lf_bark_{kind}_n.png", f"lf_bark_{kind}_r.png")


# ---------------------------------------------------------------------------- objects

def object_from_md(name, md, materials, col=None, smooth=True):
    V, F, UV, MAT, C, N = md.arrays()
    # drop degenerate (repeated index) and duplicate faces so validate() keeps loop/UV order
    keep, seen = [], set()
    for i, f in enumerate(F):
        key = tuple(sorted(f))
        if len(set(f)) < len(f) or key in seen:
            continue
        seen.add(key)
        keep.append(i)
    if len(keep) != len(F):
        F = [F[i] for i in keep]
        UV = [UV[i] for i in keep]
        MAT = MAT[keep]
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], [list(f) for f in F])
    me.validate(clean_customdata=False)
    if len(me.polygons) != len(F):
        raise RuntimeError(f"{name}: validate removed faces ({len(F)} -> {len(me.polygons)})")
    uvl = me.uv_layers.new(name="UVMap")
    flat = np.array([c for uv in UV for c in uv], np.float32)
    uvl.data.foreach_set("uv", flat.ravel())
    me.polygons.foreach_set("material_index", MAT.astype(np.int32))
    for m in materials:
        me.materials.append(m)
    ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    ca.data.foreach_set("color", np.clip(C, 0, 1).astype(np.float32).ravel())
    me.color_attributes.active_color = ca
    me.color_attributes.render_color_index = 0
    if smooth:
        me.shade_smooth()
    if N is not None:
        nn = np.where(np.isnan(N), 0.0, N)
        me.normals_split_custom_set_from_vertices([tuple(v) for v in nn])
    me.update()
    obj = bpy.data.objects.new(name, me)
    core.link(obj, col)
    return obj


def empty(name, parent=None, location=(0, 0, 0), col=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.5
    e.location = location
    core.link(e, col)
    if parent is not None:
        e.parent = parent
    return e


# ---------------------------------------------------------------------------- materials

_IMG_CACHE = {}


def image(path, colorspace="sRGB"):
    key = (path, colorspace)
    if key in _IMG_CACHE:
        try:
            _IMG_CACHE[key].name
            return _IMG_CACHE[key]
        except ReferenceError:
            del _IMG_CACHE[key]
    img = bpy.data.images.load(path, check_existing=False)
    img.name = os.path.splitext(os.path.basename(path))[0]
    img.colorspace_settings.name = colorspace
    img.pack()                                    # read pixels NOW (no lazy load at render time -> no magenta)
    if not img.has_data and img.size[0] > 0:
        _ = img.pixels[0]                         # after a factory reset bpy 5.3 loads the buffer lazily: force it
    if not img.has_data or img.size[0] == 0:
        raise RuntimeError(f"texture failed to load: {path}")
    _IMG_CACHE[key] = img
    return img


def foliage_material(name="lf_foliage"):
    m = bpy.data.materials.get(name)
    if m:
        return m
    img = image(os.path.join(RUNTIME_DIR, FOLIAGE_ATLAS))
    m = core.material(name, base_tex=img, rough=0.85, alpha_clip=0.5, double_sided=True)
    return m


def bark_material(kind, name=None):
    name = name or f"lf_bark_{kind}"
    m = bpy.data.materials.get(name)
    if m:
        return m
    c, n, r = bark_files(kind)
    m = core.material(name, base_tex=image(os.path.join(RUNTIME_DIR, c)),
                      normal_tex=image(os.path.join(RUNTIME_DIR, n), "Non-Color"),
                      rough_tex=image(os.path.join(RUNTIME_DIR, r), "Non-Color"), normal_strength=1.0)
    return m


def texture_material(name, base_path, normal_path=None, rough_path=None, double_sided=False):
    m = bpy.data.materials.get(name)
    if m:
        return m
    return core.material(name, base_tex=image(base_path),
                         normal_tex=image(normal_path, "Non-Color") if normal_path else None,
                         rough_tex=image(rough_path, "Non-Color") if rough_path else None,
                         double_sided=double_sided)


# ---------------------------------------------------------------------------- export

def export(path, objects, external_images=None, with_colors=True):
    """GLB export; images whose names are in external_images are replaced by relative URIs."""
    extra = dict(export_vertex_color="ACTIVE" if with_colors else "NONE", export_all_vertex_colors=False,
                 export_active_vertex_color_when_no_material=False, export_image_format="AUTO")
    core.export_glb(path, objects, animations=False, extra=extra)
    if external_images:
        glbx.externalize(path, external_images)
    return path


def tri_count_md(md):
    return md.tris()


def write_meta(path, data):
    core.write_json(path, data)


def gltf_bounds(objs):
    """Bounds in glTF / Godot axes (x, y=up, z=-blender_y) of the given objects (world space)."""
    lo, hi = core.bounds(objs)
    gl_lo = [lo[0], lo[2], -hi[1]]
    gl_hi = [hi[0], hi[2], -lo[1]]
    return [round(v, 3) for v in gl_lo], [round(v, 3) for v in gl_hi]


def to_gltf(p):
    """Blender (x, y, z) -> glTF/Godot (x, z, -y)."""
    return [round(float(p[0]), 3), round(float(p[2]), 3), round(float(-p[1]), 3)]
