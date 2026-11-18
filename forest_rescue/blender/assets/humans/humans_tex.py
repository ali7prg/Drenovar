"""UV atlas + reference-projection texturing + procedural PBR maps for human characters.

Material groups (4 glTF materials sharing one atlas): skin, garment, gear, hair.
Tintable groups (skin, garment, hair) store the atlas *normalised* by the group's mean colour
(texture ~ detail/luminance) and carry the colour in baseColorFactor, so captive variants can
re-colour clothing, skin tone and hair at runtime by changing the factor only.
"""
import math
import os

import bpy
import cv2
import numpy as np
from scipy import ndimage as ndi

from frlib import core, texproj

GROUPS = ["skin", "garment", "gear", "hair"]
TINTABLE = {"skin": True, "garment": True, "gear": False, "hair": True}

# class -> (group default, roughness, metallic, detail kind)
CLASS_PBR = {
    "skin": (0.52, 0.0, "skin"), "lip": (0.45, 0.0, "skin"), "eye": (0.25, 0.0, "eye"),
    "hair": (0.62, 0.0, "hair"), "beard": (0.66, 0.0, "hair"), "brow": (0.6, 0.0, "hair"),
    "shirt": (0.86, 0.0, "linen"), "linen": (0.86, 0.0, "linen"), "tunic": (0.88, 0.0, "wool"),
    "wool": (0.9, 0.0, "wool"), "dress": (0.9, 0.0, "wool"), "cloak": (0.9, 0.0, "wool"),
    "trousers": (0.88, 0.0, "wool"), "apron": (0.84, 0.0, "canvas"), "canvas": (0.84, 0.0, "canvas"),
    "armband": (0.85, 0.0, "wool"), "sash": (0.85, 0.0, "linen"), "rope": (0.92, 0.0, "rope"),
    "boot": (0.62, 0.0, "leather"), "leather": (0.6, 0.0, "leather"), "leather_dark": (0.58, 0.0, "leather"),
    "sole": (0.8, 0.0, "leather"), "metal": (0.38, 1.0, "metal"), "brass": (0.42, 1.0, "metal"),
    "wood": (0.72, 0.0, "wood"), "chainmail": (0.45, 1.0, "mail"), "gambeson": (0.9, 0.0, "quilt"),
    "tabard": (0.88, 0.0, "wool"), "felt": (0.9, 0.0, "wool"), "herbs": (0.8, 0.0, "linen"),
    "feather": (0.8, 0.0, "linen"), "body": (0.8, 0.0, "linen"),
}


def class_group(cls, spec):
    m = getattr(spec, "CLASS_GROUP", {})
    if cls in m:
        return m[cls]
    if cls in ("skin", "lip", "eye"):
        return "skin"
    if cls in ("hair", "beard", "brow"):
        return "hair"
    return "gear"


# --------------------------------------------------------------------------- UV helpers (bpy)

def smart_uv(obj, angle=62.0, margin=0.002):
    core.select_only([obj])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def scale_uvs(obj, factor):
    me = obj.data
    uv = np.empty(len(me.loops) * 2)
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    c = uv.mean(0)
    uv = (uv - c) * factor + c
    me.uv_layers.active.data.foreach_set("uv", uv.ravel())


def pack_atlas(obj, margin=0.0035):
    core.select_only([obj])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, margin=margin, scale=True)
    bpy.ops.object.mode_set(mode="OBJECT")


def average_scale(obj):
    core.select_only([obj])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode="OBJECT")


# --------------------------------------------------------------------------- procedural detail

def _n(P, f, seed):
    return texproj.value_noise(P, f, seed)


def detail_maps(kind, P, N, seed=0):
    """Per-texel (height, albedo_mult, rough_add) for a material kind; P,N (n,3)."""
    n = len(P)
    h = np.zeros(n)
    a = np.ones(n)
    r = np.zeros(n)
    if kind in ("linen", "canvas", "wool"):
        f = {"linen": 900.0, "canvas": 700.0, "wool": 500.0}[kind]
        # weave from two orthogonal sine families in a tangent-ish frame (x/z and y/z)
        u = P[:, 0] + P[:, 1] * 0.7
        v = P[:, 2]
        w = 0.5 * (np.sin(u * f) + np.sin(v * f)) * 0.5 + 0.5
        h = 0.35 * w + 0.65 * texproj.fbm(P, 60.0, 3, seed=seed)
        fold = texproj.fbm(P * np.array([1, 1, 0.35]), 14.0, 3, seed=seed + 7)
        h = h * 0.4 + fold * 0.9
        a = 0.90 + 0.14 * texproj.fbm(P, 9.0, 4, seed=seed + 3)
        r = 0.05 * (texproj.fbm(P, 20.0, 3, seed=seed + 9) - 0.5)
    elif kind == "quilt":
        # diamond quilting (gambeson): two diagonal families of grooves ~6 cm apart
        q1 = np.abs(np.sin((P[:, 0] + P[:, 2]) * math.pi / 0.062 + 0.3 * (P[:, 1] * 30)))
        q2 = np.abs(np.sin((P[:, 0] - P[:, 2]) * math.pi / 0.062))
        g = np.minimum(q1, q2)
        h = np.clip(g * 1.6, 0, 1) ** 0.6 + 0.25 * texproj.fbm(P, 400.0, 2, seed=seed)
        a = 0.86 + 0.18 * np.clip(g * 1.5, 0, 1)
        r = 0.03 * (texproj.fbm(P, 25, 2, seed=seed) - 0.5)
    elif kind == "leather":
        f1, f2 = texproj.voronoi(P, 260.0, seed=seed)
        h = np.clip((f2 - f1) * 260.0, 0, 1) * 0.5 + 0.5 * texproj.fbm(P, 30.0, 4, seed=seed + 1)
        a = 0.88 + 0.22 * texproj.fbm(P, 12.0, 4, seed=seed + 2)
        r = -0.10 * (texproj.fbm(P, 8.0, 3, seed=seed + 5) - 0.5) * 2
    elif kind == "metal":
        h = 0.3 * texproj.fbm(P, 120.0, 3, seed=seed)
        scratch = np.abs(np.sin((P[:, 0] * 3 + P[:, 2] * 7) * 900 + texproj.fbm(P, 30, 2, seed=seed) * 10))
        a = 0.85 + 0.25 * texproj.fbm(P, 20.0, 3, seed=seed + 4)
        r = 0.12 * (texproj.fbm(P, 15.0, 3, seed=seed + 6) - 0.5) - 0.06 * (scratch > 0.995)
    elif kind == "mail":
        # riveted ring mail ~ 8 mm rings
        g = np.abs(np.sin(P[:, 2] * math.pi / 0.004)) * np.abs(np.sin((P[:, 0] + P[:, 1]) * math.pi / 0.004))
        h = g ** 0.5
        a = 0.55 + 0.5 * g ** 0.5
        r = 0.15 * (1 - g)
    elif kind == "wood":
        grain = np.sin(P[:, 2] * 40 + texproj.fbm(P * np.array([6, 6, 0.5]), 3, 4, seed=seed) * 9)
        h = 0.5 + 0.5 * grain * 0.6
        a = 0.86 + 0.16 * grain
    elif kind == "rope":
        tw = np.sin((P[:, 0] + P[:, 1] + P[:, 2]) * 1100.0)
        h = 0.5 + 0.5 * tw
        a = 0.85 + 0.2 * (0.5 + 0.5 * tw)
    elif kind == "hair":
        strands = np.sin(P[:, 0] * 1500 + texproj.fbm(P, 40, 3, seed=seed) * 30)
        h = 0.5 + 0.35 * strands + 0.3 * texproj.fbm(P, 90.0, 3, seed=seed + 1)
        a = 0.80 + 0.30 * (0.5 + 0.5 * strands)
        r = 0.05 * strands
    elif kind == "skin":
        h = 0.5 + 0.25 * texproj.fbm(P, 600.0, 2, seed=seed)
        a = 0.96 + 0.08 * texproj.fbm(P, 30.0, 3, seed=seed + 1)
    return h, a, r


# --------------------------------------------------------------------------- projection

def project_colours(verts, tris, uv, vnorm, views, size, face_cls, tri_face):
    """Projected colour + weight per texel and per-texel class index."""
    T = texproj.rasterize_uv(verts, tris, uv, size, vnorm)
    zbs = {v.name: texproj.zbuffer(verts, tris, v) for v in views}
    col, w = texproj.project(T, views, zbs, power=3.0, depth_eps=0.02, min_facing=0.32, mask_erode=2)
    cls_img = np.full(T.valid.shape, -1, np.int32)
    yy, xx = np.nonzero(T.valid)
    cls_img[yy, xx] = face_cls[tri_face[T.tri[yy, xx]]]
    return T, col, w, cls_img


def reject_outliers(col, w, cls_img, valid, k=3.2):
    """Per class: projected colours far from the class median (background bleed, wrong layer)
    lose their weight (robust distance in a luma/chroma space, MAD scaled)."""
    w = w.copy()
    for c in np.unique(cls_img[valid]):
        m = (cls_img == c) & valid & (w > 0.05)
        if m.sum() < 50:
            continue
        x = col[m]
        med = np.median(x, axis=0)
        d = np.linalg.norm(x - med, axis=1)
        mad = np.median(d) + 1e-3
        bad = d > k * mad * 1.4826
        ww = w[m]
        ww[bad] = 0.0
        w[m] = ww
    return w


def fill_by_class(col, w, cls_img, valid, thresh=0.15, min_known=40):
    """Low-confidence texels are filled per class: pull-push inside the class + class median."""
    out = col.copy()
    known_all = (w > thresh) & valid
    for c in np.unique(cls_img[valid]):
        m = (cls_img == c) & valid
        k = m & known_all
        if k.sum() < min_known:
            continue
        med = np.median(col[k], axis=0)
        filled = texproj.fill(np.where(k[..., None], col, med), k | ~m)
        # blend toward the class median where confidence is low
        conf = np.clip(w / thresh, 0, 1)[..., None]
        out[m] = (filled * conf + (0.6 * filled + 0.4 * med) * (1 - conf))[m]
    return out


def class_medians(col, w, cls_img, valid, thresh=0.3):
    med = {}
    for c in np.unique(cls_img[valid]):
        k = (cls_img == c) & valid & (w > thresh)
        if k.sum() > 30:
            med[int(c)] = np.median(col[k], axis=0)
    return med
