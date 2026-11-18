"""Guardian build pipeline (bpy): model -> rig/weights -> UV atlas -> projected textures -> LODs.

A species spec module provides: ID, panels(), skeleton(), body_parts(sk), fur(...),
details(sk), weight_proxies(sk), stance poses, texture overrides and clip authoring.
"""
import json
import math
import os
import time

import bpy
import numpy as np
from scipy.spatial import cKDTree

from frlib import core, render, sdf, texproj, paths
import gbody
import gfur
import grig
import gtex

T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:7.1f}s]", *a, flush=True)


# --------------------------------------------------------------------------- mesh helpers

def obj_from(name, v, f, uvs=None, smooth=True):
    return core.mesh_object(name, v, f, uvs=None if uvs is None else np.asarray(uvs).reshape(-1, 2),
                            smooth=smooth)


def obj_arrays(obj):
    """Bind-pose (non-evaluated) verts / tris / per-loop uv of a mesh object (triangulated)."""
    me = obj.data
    me.calc_loop_triangles()
    nv = len(me.vertices)
    V = np.empty(nv * 3)
    me.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3)
    nt = len(me.loop_triangles)
    T = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", T)
    L = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get("loops", L)
    uv = None
    if me.uv_layers.active:
        luv = np.empty(len(me.loops) * 2)
        me.uv_layers.active.data.foreach_get("uv", luv)
        uv = luv.reshape(-1, 2)[L.reshape(-1, 3)]
    return V, T.reshape(-1, 3), uv


def loop_uvs(obj):
    me = obj.data
    luv = np.empty(len(me.loops) * 2)
    me.uv_layers.active.data.foreach_get("uv", luv)
    return luv.reshape(-1, 2)


def set_loop_uvs(obj, uv):
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    me.uv_layers.active.data.foreach_set("uv", np.asarray(uv, np.float32).ravel())


def face_attr(obj, name, values):
    me = obj.data
    a = me.attributes.get(name) or me.attributes.new(name, "INT", "FACE")
    a.data.foreach_set("value", np.asarray(values, np.int32))


def decimate_obj(obj, target, name):
    o = core.decimate_to(obj, target, name=name, copy=True)
    return o


# --------------------------------------------------------------------------- UV atlas

def uv_atlas(body, others, scales, margin=0.0025):
    """Smart-project the body, average island density over everything, rescale per object,
    then pack all islands of all objects into one 0..1 atlas."""
    core.smart_uv(body, angle=60.0, margin=0.002)
    objs = [body] + others
    core.select_only(objs, body)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode="OBJECT")
    for o, s in zip(objs, scales):
        if s != 1.0:
            uv = loop_uvs(o)
            set_loop_uvs(o, uv * s)
    core.select_only(objs, body)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, margin=margin, scale=True)
    bpy.ops.object.mode_set(mode="OBJECT")


# --------------------------------------------------------------------------- weights

def weight_matrix(verts, sources, bone_names, falloff=0.05, top=4, adjacency=None, smooth_iters=0,
                  smooth_factor=0.5):
    """sources: list of (prim, bone).  Distance-shifted exponential falloff (no underflow)."""
    N = len(verts)
    idx = {b: i for i, b in enumerate(bone_names)}
    D = np.full((N, len(bone_names)), np.inf)
    for prim, bone in sources:
        if bone not in idx:
            continue
        d = prim.fn(verts)
        j = idx[bone]
        D[:, j] = np.minimum(D[:, j], d)
    Dp = np.maximum(D, 0.0)
    dmin = Dp.min(1, keepdims=True)
    W = np.exp(-(Dp - dmin) / falloff)
    W[np.isinf(D)] = 0.0
    if adjacency is not None and smooth_iters:
        for _ in range(smooth_iters):
            W = (1 - smooth_factor) * W + smooth_factor * (adjacency @ W)
    return sdf.limit_weights(W, top)


def bind_weights(obj, arm, bone_names, W):
    from frlib import rig
    rig.bind(obj, arm, bone_names, W)


def remap_weights(W, bone_names, remap, top=4):
    """Fold removed bones into their kept ancestors: remap = {bone: target_bone}."""
    idx = {b: i for i, b in enumerate(bone_names)}
    W = W.copy()
    for b, tgt in remap.items():
        while tgt in remap:
            tgt = remap[tgt]
        if b in idx and tgt in idx:
            W[:, idx[tgt]] += W[:, idx[b]]
            W[:, idx[b]] = 0.0
    return sdf.limit_weights(W, top)


# --------------------------------------------------------------------------- posing in Blender

def apply_pose(arm, sk, pose):
    """Set pose bones from an armature-space pose dict (None -> rest)."""
    if pose is None:
        for pb in arm.pose.bones:
            pb.location = (0, 0, 0)
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.scale = (1, 1, 1)
    else:
        B = sk.basis(pose)
        for pb in arm.pose.bones:
            loc, q = B[pb.name]
            pb.location = tuple(loc)
            pb.rotation_quaternion = tuple(q)
    bpy.context.view_layer.update()


def posed_arrays(obj):
    v, t, uv, n = core.mesh_arrays(obj, evaluated=True, world=True)
    return v, t, uv, n


# --------------------------------------------------------------------------- materials / images

def save_jpg(path, arr, quality=92):
    from PIL import Image
    a = (np.clip(arr[..., :3], 0, 1) * 255 + 0.5).astype(np.uint8)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(a, "RGB").save(path, quality=quality, subsampling=0)
    return path


def resize(arr, size):
    import cv2
    return cv2.resize(arr.astype(np.float32), (size, size), interpolation=cv2.INTER_AREA)


# --------------------------------------------------------------------------- comparison renders

def render_view(view, out_png=None, samples=32, engine="CYCLES"):
    render.studio(engine=engine, samples=samples)
    render.camera_for_view(view)
    return render.render_rgba(out_png)


def compare_views(items, out_dir, prefix, title_prefix, samples=32):
    """items: list of (view, pose_label).  Returns metrics dict."""
    res = {}
    for view, label in items:
        rgba = render_view(view, samples=samples)
        m = render.compare(view, rgba, os.path.join(out_dir, f"{prefix}_{view.name}.png"),
                           title=f"{title_prefix} {view.name} ({label})")
        res[view.name] = m
        log("compare", view.name, m["iou"], m["mean_abs_colour_error"])
    return res
