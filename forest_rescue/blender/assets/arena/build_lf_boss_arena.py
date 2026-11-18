"""Build the final boss arena kit (lf_boss_arena) and the assembled preview.

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/arena/build_lf_boss_arena.py \
    [--iter 01] [--only cliff_a,...] [--no-qa]
Outputs: godot/project/assets/forest_rescue/arena/*.glb + *.meta.json,
         forest_rescue/blender/sources/arena/lf_boss_arena.blend, textures/arena/*,
         forest_rescue/qa/compare/lf_boss_arena/iterNN_*.png
Layout frame: arena centre at the origin, floor at Z=0, main entrance gap toward -Y (glTF +Z = the route
lf_route_boss arriving from the south in world coords).  World placement: (75, 6.55, -86), yaw +5.4 deg.
"""
import argparse
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import bpy  # noqa: E402
from mathutils import Euler, Matrix, Vector  # noqa: E402

from frlib import core, paths, render, rig, sdf, texproj  # noqa: E402
import arena_lib as AL  # noqa: E402

GROUP = "arena"
AID = "lf_boss_arena"
TEX = 1024


def log(*a):
    print("[arena]", *a, flush=True)


def tex_dir():
    return paths.ensure(paths.TEXTURE_SOURCES, GROUP)


# ------------------------------------------------------------------------------------ helpers
def field_to_object(name, F):
    v, f = F.mesh()
    return core.mesh_object(name, v, f, smooth=True)


def lod_pair(high, name, tris0, tris1):
    l0 = core.decimate_to(high, tris0, name=f"{name}_LOD0")
    core.smart_uv(l0, angle=66.0, margin=0.004)
    core.select_only([l0])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, scale=True, margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")
    l1 = core.decimate_to(l0, tris1, name=f"{name}_LOD1")
    return l0, l1


def texels(obj, size):
    V, tris, uv, vn = core.mesh_arrays(obj, evaluated=False, world=False)
    T = texproj.rasterize_uv(V, tris, uv, size, vn)
    return T


def save_maps(name, col, rough, nrm, T, size):
    td = tex_dir()
    from PIL import Image
    col = texproj.dilate_margin(col, T.valid, px=8)
    nrm = texproj.dilate_margin(nrm, T.valid, px=8)
    orm = np.zeros((size, size, 3))
    orm[..., 0] = 1
    orm[..., 1] = rough
    orm = texproj.dilate_margin(orm, T.valid, px=8)
    pc = os.path.join(td, f"{name}_basecolor.jpg")
    Image.fromarray((np.clip(col, 0, 1) * 255 + 0.5).astype(np.uint8)).save(pc, quality=90)
    pn = core.save_rgba(os.path.join(td, f"{name}_normal.png"), nrm)
    po = core.save_rgba(os.path.join(td, f"{name}_orm.png"), orm)
    return pc, pn, po


def make_material(name, pc, pn, po, double_sided=False):
    ic = core.load_image(pc, "sRGB")
    io = core.load_image(po, "Non-Color")
    inn = core.load_image(pn, "Non-Color") if pn else None
    return core.material(f"M_{name}", base_tex=ic, rough_tex=io, metal_tex=io, normal_tex=inn, double_sided=double_sided)


def bake_maps(lod0, high, size, ao_samples=12):
    tmp_mat = bpy.data.materials.new("bake_tmp")
    tmp_mat.use_nodes = True
    lod0.data.materials.clear()
    lod0.data.materials.append(tmp_mat)
    img_n = core.new_image(f"{lod0.name}_bn", size, colorspace="Non-Color", color=(0.5, 0.5, 1, 1))
    core.bake(lod0, "NORMAL", img_n, samples=1, selected_to_active=high, cage_extrusion=0.06, max_ray_distance=0.15)
    img_ao = core.new_image(f"{lod0.name}_ao", size, colorspace="Non-Color", color=(1, 1, 1, 1))
    hide = high.hide_render
    high.hide_render = True
    core.bake(lod0, "AO", img_ao, samples=ao_samples)
    high.hide_render = hide
    nb = core.image_to_numpy(img_n)[..., :3]
    ao = core.image_to_numpy(img_ao)[..., 0]
    bpy.data.images.remove(img_n)
    bpy.data.images.remove(img_ao)
    lod0.data.materials.clear()
    bpy.data.materials.remove(tmp_mat)
    return nb, ao


def rock_module(name, parts, lo, hi, seed, tris0, tris1, top_z, sub=(), bone_parts=None, voxel=0.05,
                strata=True):
    t0 = time.time()
    F = AL.build_rock_field(parts + (bone_parts or []), lo, hi, voxel, seed, sub=sub, strata_on=strata)
    high = field_to_object(f"{name}_high", F)
    l0, l1 = lod_pair(high, name, tris0, tris1)
    nb, ao = bake_maps(l0, high, TEX)
    T = texels(l0, TEX)
    yy, xx = np.nonzero(T.valid)
    P, N = T.pos[yy, xx], T.nrm[yy, xx]
    bm = None
    if bone_parts:
        d = np.full(len(P), 9.0)
        for p in bone_parts:
            sel = np.all((P >= p.lo - 0.08) & (P <= p.hi + 0.08), axis=1)
            if sel.any():
                d[sel] = np.minimum(d[sel], p.fn(P[sel]))
        bm = np.clip((0.06 - d) / 0.06, 0, 1)
    c, r, mossy = AL.rock_colour(P, N, seed, top_z, bone_mask=bm, ao=ao[yy, xx])
    col = np.zeros((TEX, TEX, 3))
    col[yy, xx] = c
    rough = np.full((TEX, TEX), 0.9)
    rough[yy, xx] = r
    # crack/pit detail in the normal: fine noise gradient (finite differences in 3-D)
    e = 0.01
    h0 = texproj.fbm(P, 9.0, 2, seed + 31)
    gx = (texproj.fbm(P + [e, 0, 0], 9.0, 2, seed + 31) - h0) / e
    gy = (texproj.fbm(P + [0, e, 0], 9.0, 2, seed + 31) - h0) / e
    gz = (texproj.fbm(P + [0, 0, e], 9.0, 2, seed + 31) - h0) / e
    G = np.stack([gx, gy, gz], 1) * 0.004
    G -= N * (G * N).sum(1, keepdims=True)
    V, tris, uv, vn = core.mesh_arrays(l0, evaluated=False, world=False)
    tg, bt = tangent_frames(V, tris, uv, T)
    n1 = nb[yy, xx] * 2 - 1
    nn = np.stack([n1[:, 0] - (G * tg).sum(1), n1[:, 1] - (G * bt).sum(1), n1[:, 2]], 1)
    nn /= np.linalg.norm(nn, axis=1, keepdims=True)
    nrm = np.zeros((TEX, TEX, 3))
    nrm[..., :] = (0.5, 0.5, 1)
    nrm[yy, xx] = nn * 0.5 + 0.5
    pc, pn, po = save_maps(name, col, rough, nrm, T, TEX)
    mat = make_material(name, pc, pn, po)
    for o in (l0, l1):
        o.data.materials.clear()
        o.data.materials.append(mat)
    bpy.data.objects.remove(high, do_unlink=True)
    log(f"{name}: LOD0 {core.tri_count(l0)} LOD1 {core.tri_count(l1)} ({time.time() - t0:.0f}s)")
    return l0, l1


def tangent_frames(V, tris, uv, T):
    t0, t1, t2 = V[tris[:, 0]], V[tris[:, 1]], V[tris[:, 2]]
    e1, e2 = t1 - t0, t2 - t0
    d1, d2 = uv[:, 1] - uv[:, 0], uv[:, 2] - uv[:, 0]
    den = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    den = np.where(np.abs(den) < 1e-12, 1e-12, den)
    Tg = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / den[:, None]
    Bt = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / den[:, None]
    yy, xx = np.nonzero(T.valid)
    tri = T.tri[yy, xx]
    N = T.nrm[yy, xx]
    tg = Tg[tri] - N * (Tg[tri] * N).sum(1, keepdims=True)
    tg /= np.maximum(np.linalg.norm(tg, axis=1, keepdims=True), 1e-12)
    bt = np.cross(N, tg)
    hand = np.sign((bt * Bt[tri]).sum(1))
    hand[hand == 0] = 1
    return tg, bt * hand[:, None]


# ------------------------------------------------------------------------------------ modules
def build_cliff(v):
    parts = AL.cliff_parts(v)
    L = AL.CLIFF_VARIANTS[v][0]
    lo = np.array([-L / 2 - 1.5, -2.2, -0.3])
    hi = np.array([L / 2 + 1.5, 4.6, AL.CLIFF_VARIANTS[v][1][1] + 1.6])
    return rock_module(f"lf_arena_cliff_{v}", parts, lo, hi, AL.CLIFF_VARIANTS[v][3], 2900, 1150,
                       AL.CLIFF_VARIANTS[v][1][1])


def build_fossil():
    parts = AL.fossil_parts()
    ribs = AL.rib_prims()
    skull, sub = AL.skull_prims()
    lo = np.array([-AL.FOSSIL_LEN / 2 - 1.5, -2.4, -0.3])
    hi = np.array([AL.FOSSIL_LEN / 2 + 1.5, 4.6, 7.4])
    return rock_module("lf_arena_fossil_wall", parts, lo, hi, 51, 5600, 2200, 5.8, sub=sub, bone_parts=ribs + skull,
                       voxel=0.04)


def build_pillar(v):
    H, W, seed = AL.PILLAR_VARIANTS[v]
    lo = np.array([-W - 1.2, -W - 1.2, -0.3])
    hi = np.array([W + 1.6, W + 1.2, H + 1.0])
    return rock_module(f"lf_arena_pillar_{v}", AL.pillar_parts(v), lo, hi, seed, 1500 if v == "a" else 1300,
                       600, H, voxel=0.04)


def build_floor():
    """Arena ground: dished disc with entrance/side path tongues; cracked dry dirt texture (2048)."""
    name = "lf_arena_floor"
    rings, segs = 22, 96
    verts, faces = [], []
    R = AL.FLOOR_R + 1.6
    rng = np.random.default_rng(4)
    for i in range(1, rings + 1):
        r = R * (i / rings) ** 0.9
        for j in range(segs):
            a = 2 * math.pi * j / segs
            x, y = r * math.cos(a), r * math.sin(a)
            z = 0.012 * (r / R) ** 2 * 10 + (0.35 * max(0.0, (r - AL.FLOOR_R + 0.6)) ** 1.5 if r > AL.FLOOR_R - 0.6 else 0)
            z += 0.03 * (texproj.fbm(np.array([[x, y, 0.0]]), 0.3, 2, 3)[0] - 0.5)
            verts.append((x, y, z))
    for i in range(rings - 1):
        for j in range(segs):
            a = i * segs + j
            b = i * segs + (j + 1) % segs
            c = (i + 1) * segs + (j + 1) % segs
            d = (i + 1) * segs + j
            faces.append((a, d, c, b))
    verts.append((0.0, 0.0, 0.0))
    ci = len(verts) - 1
    for j in range(segs):
        faces.append((ci, j, (j + 1) % segs)[::-1] if False else (j, (j + 1) % segs, ci))
    V = np.array(verts)
    uv_loops = []
    for f in faces:
        for vi in f:
            uv_loops.append(((V[vi, 0] / (2 * R)) + 0.5, (V[vi, 1] / (2 * R)) + 0.5))
    obj = core.mesh_object(f"{name}_LOD0", V, faces, uvs=np.array(uv_loops))
    # path tongues outside the gaps (entrance -Y, left 160 deg, right -18 deg)
    pv, pf, pu = [], [], []
    for ang, width, length in ((-90.0, 6.5, 9.0), (160.0, 4.0, 6.0), (-18.0, 4.0, 6.0)):
        a = math.radians(ang)
        d = np.array([math.cos(a), math.sin(a)])
        nrm = np.array([-d[1], d[0]])
        base = len(pv)
        n = 6
        for k in range(n + 1):
            s = AL.FLOOR_R - 1.0 + length * k / n
            for side in (-1, 1):
                w = width / 2 * (1.0 - 0.25 * k / n)
                p = d * s + nrm * side * w
                pv.append((p[0], p[1], 0.05 + 0.12 * (k / n)))
        for k in range(n):
            a0 = base + 2 * k
            pf.append((a0, a0 + 2, a0 + 3, a0 + 1))
    PV = np.array(pv)
    for f in pf:
        for vi in f:
            pu.append((PV[vi, 0] / (2 * R) + 0.5, PV[vi, 1] / (2 * R) + 0.5))
    paths_obj = core.mesh_object(f"{name}_paths", PV, pf, uvs=np.array(pu))
    # texture: cracked dirt
    S = 2048
    T = texels(obj, S)
    yy, xx = np.nonzero(T.valid)
    P = T.pos[yy, xx]
    f1, f2 = texproj.voronoi(P * np.array([1, 1, 0]), freq=1 / 0.55, seed=7)
    crack = np.clip(1 - (f2 - f1) / 0.035, 0, 1) ** 1.5
    f1b, f2b = texproj.voronoi(P * np.array([1, 1, 0]), freq=1 / 0.17, seed=9)
    crack2 = np.clip(1 - (f2b - f1b) / 0.012, 0, 1) ** 2 * 0.5
    n1 = texproj.fbm(P, 0.12, 3, 5)
    n2 = texproj.fbm(P, 1.3, 3, 6)
    r = np.linalg.norm(P[:, :2], axis=1)
    base = np.array([0.66, 0.50, 0.33]) * (0.86 + 0.28 * n1[:, None])
    base = base * (1 - 0.18 * np.clip((r - 11) / 6, 0, 1))[:, None] + np.array([0.48, 0.40, 0.30]) * 0.18 * np.clip((r - 11) / 6, 0, 1)[:, None]
    base *= (0.92 + 0.16 * n2)[:, None]
    cr = np.clip(crack + crack2, 0, 1)
    col = base * (1 - 0.55 * cr[:, None])
    pebble = (texproj.fbm(P, 9.0, 1, 8) > 0.82).astype(float)
    col = col * (1 - 0.3 * pebble[:, None]) + np.array([0.70, 0.66, 0.58]) * 0.3 * pebble[:, None]
    C = np.zeros((S, S, 3))
    C[yy, xx] = col
    H = np.zeros((S, S))
    H[yy, xx] = -0.004 * cr + 0.002 * n2
    nrm = texproj.height_to_normal(H, T.valid, strength=1.0, texel_m=2 * R / S)
    rough = np.full((S, S), 0.95)
    from PIL import Image
    td = tex_dir()
    pc = os.path.join(td, f"{name}_basecolor.jpg")
    Image.fromarray((np.clip(texproj.dilate_margin(C, T.valid, 8), 0, 1) * 255 + 0.5).astype(np.uint8)).save(pc, quality=90)
    import cv2
    pn = core.save_rgba(os.path.join(td, f"{name}_normal.png"), cv2.resize(nrm, (1024, 1024), interpolation=cv2.INTER_AREA))
    orm = np.zeros((256, 256, 3))
    orm[..., 0] = 1
    orm[..., 1] = 0.95
    po = core.save_rgba(os.path.join(td, f"{name}_orm.png"), orm)
    mat = make_material(name, pc, pn, po)
    for o in (obj, paths_obj):
        o.data.materials.clear()
        o.data.materials.append(mat)
    floor = core.join([obj, paths_obj], name=f"{name}_LOD0")
    log("floor", core.tri_count(floor))
    return floor


def build_bones():
    """Small bone scatter: femur, rib pieces, vertebrae, a broken jaw (fossil bone colour)."""
    name = "lf_arena_bones"
    rng = np.random.default_rng(12)
    parts = []
    # femur
    parts += [sdf.capsule([-0.6, 0, 0.12], [0.6, 0.05, 0.12], 0.07, name="femur"),
              sdf.sphere([-0.65, 0, 0.14], 0.13), sdf.ellipsoid([0.67, 0.05, 0.13], (0.14, 0.11, 0.1))]
    # ribs
    for i in range(3):
        c = np.array([1.6 + 0.35 * i, 0.9, 0.06])
        pts = [c + np.array([0.0, -0.7 * s, 0.25 * math.sin(math.pi * s)]) for s in np.linspace(0, 1, 6)]
        parts += sdf.chain(pts, [0.05, 0.05, 0.045, 0.04, 0.035, 0.03], k=0.01)
    # vertebrae
    for i in range(3):
        c = np.array([-1.5 + 0.4 * i, 1.2, 0.12])
        parts += [sdf.ellipsoid(c, (0.13, 0.11, 0.12)), sdf.capsule(c, c + [0, 0, 0.22], 0.04),
                  sdf.capsule(c - [0.18, 0, 0], c + [0.18, 0, 0], 0.035)]
    # broken jaw
    parts += [sdf.box([0.2, -1.4, 0.1], (0.6, 0.06, 0.1), rot=np.array([0, 0, 0.3]), rounding=0.04)]
    for i in range(5):
        x = -0.25 + 0.15 * i
        parts.append(sdf.round_cone([x * math.cos(0.3) + 0.2, -1.4 + x * math.sin(0.3), 0.18],
                                    [x * math.cos(0.3) + 0.2, -1.42 + x * math.sin(0.3), 0.3], 0.025, 0.006))
    F = sdf.Field(np.array([-2.2, -2.0, -0.05]), np.array([2.8, 1.8, 0.7]), 0.02)
    F.union_all(parts)
    F.intersect(lambda P: -(P[..., 2] + 0.0), k=0.0)
    F.smooth(0.6)
    high = field_to_object(f"{name}_high", F)
    l0 = core.decimate_to(high, 1400, name=f"{name}_LOD0")
    core.smart_uv(l0, 66.0, 0.006)
    nb, ao = bake_maps(l0, high, 512, ao_samples=8)
    T = texels(l0, 512)
    yy, xx = np.nonzero(T.valid)
    P = T.pos[yy, xx]
    n3 = texproj.fbm(P, 8.0, 2, 3)
    col = AL.BONE[None] * (0.8 + 0.3 * n3[:, None]) * (0.5 + 0.5 * ao[yy, xx])[:, None]
    C = np.zeros((512, 512, 3))
    C[yy, xx] = col
    Nn = np.zeros((512, 512, 3))
    Nn[..., :] = (0.5, 0.5, 1)
    Nn[yy, xx] = nb[yy, xx]
    rough = np.full((512, 512), 0.7)
    pc, pn, po = save_maps(name, C, rough, Nn, T, 512)
    mat = make_material(name, pc, pn, po)
    l0.data.materials.clear()
    l0.data.materials.append(mat)
    bpy.data.objects.remove(high, do_unlink=True)
    log("bones", core.tri_count(l0))
    return l0


def build_stream():
    """Side stream with a small waterfall (image 08 lower-left): channel bed, water ribbon, falling sheet."""
    name = "lf_arena_stream"
    # water ribbon along a curve in module space (origin at the waterfall lip)
    pts = [(-10.0, -1.0, -2.2), (-6.0, -0.6, -2.2), (-2.0, 0.0, -2.1), (0.0, 0.0, -2.0), (0.0, 0.0, 0.0),
           (3.0, 0.4, 0.05), (7.0, 1.6, 0.1), (11.0, 3.5, 0.15)]
    verts, faces, uvs = [], [], []
    acc = 0.0
    prev = None
    for i, p in enumerate(pts):
        p = np.array(p)
        if prev is not None:
            acc += np.linalg.norm(p - prev)
        nxt = np.array(pts[min(i + 1, len(pts) - 1)])
        prv = np.array(pts[max(i - 1, 0)])
        d = nxt - prv
        d[2] = 0
        d /= max(np.linalg.norm(d), 1e-6)
        nrm = np.array([-d[1], d[0], 0])
        w = 1.6 if i >= 4 else 2.4
        verts.append(p - nrm * w)
        verts.append(p + nrm * w)
        uvs.append(acc)
        prev = p
    for i in range(len(pts) - 1):
        a = 2 * i
        faces.append((a, a + 1, a + 3, a + 2))
    V = np.array(verts)
    luv = []
    for f in faces:
        for vi in f:
            luv.append(((vi % 2) * 1.0, uvs[vi // 2] / 8.0))
    water = core.mesh_object(f"{name}_water", V, faces, uvs=np.array(luv))
    S = 512
    yy, xx = np.mgrid[0:S, 0:S]
    stripe = 0.5 + 0.5 * np.sin(yy / S * 2 * math.pi * 6 + 3 * np.sin(xx / S * 9))
    col = np.stack([0.18 + 0.25 * stripe, 0.38 + 0.25 * stripe, 0.42 + 0.22 * stripe], -1)
    foam = np.clip((np.sin(yy / S * 40 + xx / 13.0) - 0.7) * 3, 0, 1)
    col = col * (1 - foam[..., None] * 0.6) + 0.9 * foam[..., None] * 0.6
    from PIL import Image
    td = tex_dir()
    pc = os.path.join(td, f"{name}_basecolor.jpg")
    Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)).save(pc, quality=90)
    orm = np.zeros((64, 64, 3))
    orm[..., 0] = 1
    orm[..., 1] = 0.12
    po = core.save_rgba(os.path.join(td, f"{name}_orm.png"), orm)
    wmat = make_material(name + "_water", pc, None, po, double_sided=True)
    water.data.materials.append(wmat)
    # banks / rocks around the falls
    rng = np.random.default_rng(81)
    parts = []
    for i in range(16):
        x = rng.uniform(-9, 10)
        side = rng.choice([-1, 1])
        y = np.interp(x, [p[0] for p in pts[::-1]], [p[1] for p in pts[::-1]]) + side * rng.uniform(1.8, 3.2)
        z = -2.3 if x < 0 else -0.1
        s = rng.uniform(0.5, 1.2)
        parts.append(AL.rbox([x, y, z + s * 0.4], (s, s * 0.8, s * 0.7), yaw=rng.uniform(0, 3), rounding=0.15, k=0.2))
    parts.append(AL.rbox([0.4, 0.0, -1.0], (0.8, 3.2, 1.25), rounding=0.25, k=0.3))
    lo, hi = np.array([-11, -5, -3.2]), np.array([12, 8, 2.0])
    l0, _l1 = rock_module(name + "_rocks", parts, lo, hi, 81, 1500, 600, 1.5, voxel=0.08, strata=False)
    bpy.data.objects.remove(_l1, do_unlink=True)
    obj = core.join([l0, water], name=f"{name}_LOD0")
    log("stream", core.tri_count(obj))
    return obj


# ------------------------------------------------------------------------------------ banner
BANNER_W, BANNER_H, POLE_H = 1.15, 2.5, 4.6


def banner_texture(S=512):
    H, W = S * 2, S
    yy, xx = np.mgrid[0:H, 0:W]
    u, v = (xx + 0.5) / W, (yy + 0.5) / H
    col = np.zeros((H, W, 3))
    col[...] = (0.62, 0.16, 0.09)
    border = (u < 0.07) | (u > 0.93) | (v < 0.05)
    col[border] = (0.42, 0.10, 0.06)
    # 8-point sun/star emblem (dark orange) in the upper half
    cx, cy = 0.5, 0.36
    dx, dy = (u - cx), (v - cy) * 0.5
    r = np.sqrt(dx * dx + dy * dy)
    a = np.arctan2(dy, dx)
    star = r < 0.16 + 0.12 * np.abs(np.cos(4 * a)) ** 3
    col[star] = (0.92, 0.48, 0.14)
    col[r < 0.07] = (0.62, 0.16, 0.09)
    col[(r > 0.05) & (r < 0.065)] = (0.92, 0.48, 0.14)
    weave = 0.93 + 0.07 * np.sin(xx * 1.7) * np.sin(yy * 1.7)
    col *= weave[..., None]
    grime = texproj.fbm(np.stack([u * 3, v * 6, np.zeros_like(u)], -1).reshape(-1, 3), 1.0, 3, 2).reshape(H, W)
    col *= (0.85 + 0.2 * grime)[..., None]
    col *= (1 - 0.25 * np.clip((v - 0.7) / 0.3, 0, 1))[..., None]
    return np.clip(col, 0, 1)


def build_banner():
    """Wooden pole + crossbar + red cloth (skinned to a 5-bone chain) + lf_banner_wind clip (4.5 s loop)."""
    name = "lf_arena_banner"
    # pole: 8-sided tapered cylinder + crossbar + finial
    verts, faces, uvs = [], [], []

    def cyl(p0, p1, r0, r1, n=8, u0=0.0):
        p0, p1 = np.array(p0, float), np.array(p1, float)
        d = (p1 - p0) / np.linalg.norm(p1 - p0)
        a = np.cross(d, [0, 0, 1]) if abs(d[2]) < 0.9 else np.cross(d, [1, 0, 0])
        a /= np.linalg.norm(a)
        b = np.cross(d, a)
        base = len(verts)
        for k, (p, r) in enumerate(((p0, r0), (p1, r1))):
            for j in range(n):
                t = 2 * math.pi * j / n
                verts.append(p + (a * math.cos(t) + b * math.sin(t)) * r)
        for j in range(n):
            faces.append((base + j, base + (j + 1) % n, base + n + (j + 1) % n, base + n + j))
            for (jj, kk) in ((j, 0), (j + 1, 0), (j + 1, 1), (j, 1)):
                uvs.append((u0 + 0.1 * jj / n, kk * 0.95))
        faces.append(tuple(base + n + j for j in range(n)))
        for j in range(n):
            uvs.append((u0, 0.98))

    cyl((0, 0, -0.3), (0, 0, POLE_H), 0.085, 0.065)
    cyl((-0.15, 0, POLE_H - 0.35), (BANNER_W + 0.15, 0, POLE_H - 0.35), 0.04, 0.04, u0=0.12)
    cyl((0, 0, POLE_H), (0, 0, POLE_H + 0.28), 0.07, 0.005, u0=0.24)
    pole = core.mesh_object(f"{name}_pole", np.array(verts), faces, uvs=np.array(uvs))
    # cloth grid hanging from the crossbar, swallow-tail bottom
    nx, ny = 6, 12
    cv, cf, cu = [], [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            u = i / nx
            v = j / ny
            x = 0.05 + u * (BANNER_W - 0.1)
            z = POLE_H - 0.38 - v * BANNER_H
            if j == ny:
                z += 0.32 * (1 - abs(u - 0.5) * 2)       # notch in the middle of the bottom edge
            cv.append((x, 0.02, z))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            cf.append((a, a + 1, a + nx + 2, a + nx + 1))
            for vi in (a, a + 1, a + nx + 2, a + nx + 1):
                ii, jj = vi % (nx + 1), vi // (nx + 1)
                cu.append((ii / nx * 0.5 + 0.5, 1 - jj / ny))
    cloth = core.mesh_object(f"{name}_cloth", np.array(cv), cf, uvs=np.array(cu))
    # one texture atlas: left half wood, right half cloth
    S = 512
    tex = np.zeros((S * 2, S * 2, 3))
    wood = texproj.fbm(np.stack(np.mgrid[0:S * 2, 0:S].astype(float), -1).reshape(-1, 2).repeat(1, 0) @ np.array([[0.002, 0, 0], [0, 0.05, 0]]), 3.0, 3, 4).reshape(S * 2, S)
    tex[:, :S] = np.array([0.36, 0.25, 0.15])[None, None] * (0.7 + 0.5 * wood[..., None])
    tex[:, S:] = banner_texture(S)
    from PIL import Image
    td = tex_dir()
    pc = os.path.join(td, f"{name}_basecolor.jpg")
    Image.fromarray((np.clip(tex, 0, 1) * 255 + 0.5).astype(np.uint8)).save(pc, quality=90)
    orm = np.zeros((64, 64, 3))
    orm[..., 0] = 1
    orm[..., 1] = 0.85
    po = core.save_rgba(os.path.join(td, f"{name}_orm.png"), orm)
    mat = make_material(name, pc, None, po, double_sided=True)
    for o in (pole, cloth):
        o.data.materials.clear()
        o.data.materials.append(mat)
    # wind weights as vertex colours (R = sway weight 0 top .. 1 bottom, G = phase 0..1 across the width)
    col_layer = cloth.data.color_attributes.new("wind", "FLOAT_COLOR", "POINT")
    for i, v in enumerate(cloth.data.vertices):
        w = (POLE_H - 0.38 - v.co.z) / BANNER_H
        col_layer.data[i].color = (max(0.0, min(1.0, w)), v.co.x / BANNER_W, 0.0, 1.0)
    pc_layer = pole.data.color_attributes.new("wind", "FLOAT_COLOR", "POINT")
    for i in range(len(pole.data.vertices)):
        pc_layer.data[i].color = (0.0, 0.0, 0.0, 1.0)
    obj = core.join([pole, cloth], name=f"{name}_LOD0")
    # rig: root + pole + 5 cloth bones down the cloth centre line
    bones = [{"name": "banner_root", "head": (0, 0, 0), "tail": (0, 0, 0.5)},
             {"name": "pole", "head": (0, 0, 0.5), "tail": (0, 0, POLE_H - 0.35), "parent": "banner_root"}]
    zc = [POLE_H - 0.38 - BANNER_H * k / 5 for k in range(6)]
    for k in range(5):
        bones.append({"name": f"cloth_{k + 1}", "head": (BANNER_W / 2, 0.02, zc[k]), "tail": (BANNER_W / 2, 0.02, zc[k + 1]),
                      "parent": "pole" if k == 0 else f"cloth_{k}", "connect": k > 0})
    arm = rig.armature(f"{name}_rig", bones)
    names = [b["name"] for b in bones]
    nv = len(obj.data.vertices)
    W = np.zeros((nv, len(names)))
    for i, v in enumerate(obj.data.vertices):
        if v.co.y > 0.005 and v.co.z < POLE_H - 0.37 and 0.0 < v.co.x < BANNER_W + 0.01 and abs(v.co.y - 0.02) < 1e-3:
            s = (POLE_H - 0.38 - v.co.z) / (BANNER_H / 5)
            k = min(int(s), 4)
            f = s - k
            if k == 0 and f < 0.5:
                W[i, names.index("pole")] = 1 - f * 2
                W[i, names.index("cloth_1")] = f * 2
            elif k < 4 and f > 0.5:
                W[i, names.index(f"cloth_{k + 1}")] = 1.5 - f
                W[i, names.index(f"cloth_{k + 2}")] = f - 0.5
            else:
                W[i, names.index(f"cloth_{k + 1}")] = 1.0
        else:
            W[i, names.index("pole")] = 1.0
    W = sdf.limit_weights(W, 4)
    rig.bind(obj, arm, names, W)
    # lf_banner_wind: 4.5 s loop, travelling wave down the chain (integer harmonics -> seamless)
    D = 4.5
    N = int(round(D * 30))
    frames = []
    for i in range(N + 1):
        t = (i % N) * D / N
        fr = {"banner_root": (Vector(), rig.euler_q()), "pole": (Vector(), rig.euler_q(y=0.6 * math.sin(2 * math.pi * t / D)))}
        for k in range(5):
            ph = 2 * math.pi * t / D
            sw = 9 + 5 * k
            ax = sw * (0.55 * math.sin(ph - 0.7 * k) + 0.3 * math.sin(2 * ph - 1.1 * k + 0.5) + 0.15 * math.sin(3 * ph - 1.6 * k))
            tw = 6 * math.sin(2 * ph - 0.9 * k + 1.0)
            fr[f"cloth_{k + 1}"] = (Vector(), rig.euler_q(x=ax + 8, z=tw))
        frames.append(fr)
    act = rig.write_action(arm, "lf_banner_wind", frames, loop=True, keep_location=())
    log("banner", core.tri_count(obj), "tris, clip frames", len(frames))
    return obj, arm


# ------------------------------------------------------------------------------------ layout
LAYOUT = {
    # cliffs: (variant, angle deg) — arena centre at origin, main entrance gap at -90 deg
    "cliffs": [("c", -66), ("b", -40), ("b", 2), ("a", 22), ("a", 42), ("a", 96), ("a", 119), ("b", 141),
               ("b", 178), ("a", 201), ("b", 224), ("c", 247)],
    "fossil": 68.0,
    "pillars": [("a", (-10.2, 6.0), 20.0), ("a", (-13.0, -0.6), 75.0), ("a", (13.0, 0.6), -30.0),
                ("b", (5.6, -5.2), 10.0)],
    "banners": [(-112.0, 16.6), (-68.0, 16.6)],
    "bones": [((-4.5, 3.8), 30.0), ((6.5, 7.5), -60.0), ((-8.5, -6.0), 120.0)],
    "stream": ((-21.0, -16.5, 0.0), -40.0),
}


def place(obj_src, loc, rot_deg, name, col):
    o = obj_src.copy()
    o.name = name
    col.objects.link(o)
    o.location = loc
    o.rotation_euler = (0, 0, math.radians(rot_deg))
    return o


def ring_xf(angle_deg):
    a = math.radians(angle_deg)
    return (AL.R_IN * math.cos(a), AL.R_IN * math.sin(a), 0.0), angle_deg - 90.0


def module_tris(o):
    return core.tri_count(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", default="01")
    ap.add_argument("--no-qa", action="store_true")
    args = ap.parse_args(sys.argv[1:])
    core.reset()
    mods = {}
    for v in "abc":
        mods[f"cliff_{v}"] = build_cliff(v)
    mods["fossil"] = build_fossil()
    for v in "ab":
        mods[f"pillar_{v}"] = build_pillar(v)
    floor = build_floor()
    bones = build_bones()
    stream = build_stream()
    banner, banner_arm = build_banner()
    out_dir = paths.ensure(paths.RUNTIME, GROUP)
    meta_all = {}

    def export_module(mid, objs, extra=None, anim=False):
        path = os.path.join(out_dir, f"{mid}.glb")
        core.export_glb(path, objs, animations=anim)
        tris = {o.name.rsplit("_", 1)[-1]: core.tri_count(o) for o in objs if o.type == "MESH"}
        lo, hi = core.bounds([o for o in objs if o.type == "MESH" and o.name.endswith("LOD0")])
        m = {"id": mid, "tris": tris, "bounds_m": {"min": [round(float(x), 2) for x in lo],
                                                   "max": [round(float(x), 2) for x in hi]},
             "materials": sorted({s.material.name for o in objs if o.type == "MESH" for s in o.material_slots if s.material}),
             "notes": "pivot: inner-face base centre, local +Y away from the arena centre (ring radius 17.5 m)"
             if mid.startswith(("lf_arena_cliff", "lf_arena_fossil")) else "pivot at the base centre"}
        if extra:
            m.update(extra)
        core.write_json(os.path.join(out_dir, f"{mid}.meta.json"), m)
        meta_all[mid] = m
        return path

    for key, (l0, l1) in mods.items():
        mid = f"lf_arena_{key}" if not key.startswith("fossil") else "lf_arena_fossil_wall"
        export_module(mid, [l0, l1])
    export_module("lf_arena_floor", [floor], {"notes": "ground disc R=19.4 m + path tongues (entrance -Y, side gaps "
                                                       "160 and -18 deg); cracked dirt 2048 texture"})
    export_module("lf_arena_bones", [bones])
    export_module("lf_arena_stream", [stream])
    rig.rest_pose(banner_arm)
    banner_arm.animation_data.action = bpy.data.actions["lf_banner_wind"]
    export_module("lf_arena_banner", [banner_arm, banner],
                  {"clips": {"lf_banner_wind": {"seconds": 4.5, "loop": True, "markers": {}}},
                   "bones": 7, "vertexColors": {"wind": "R = sway weight (0 at the crossbar .. 1 at the hem), "
                                                         "G = phase across the width; pole verts 0"}}, anim=True)
    # ---------------------------------------------------------------- assembly
    col = core.collection("assembled")
    placed = []
    for i, (v, ang) in enumerate(LAYOUT["cliffs"]):
        loc, rot = ring_xf(ang)
        placed.append(place(mods[f"cliff_{v}"][0], loc, rot, f"cliff_{i:02d}_{v}", col))
    loc, rot = ring_xf(LAYOUT["fossil"])
    placed.append(place(mods["fossil"][0], loc, rot, "fossil_wall", col))
    for i, (v, (x, y), r) in enumerate(LAYOUT["pillars"]):
        placed.append(place(mods[f"pillar_{v}"][0], (x, y, 0), r, f"pillar_{i}_{v}", col))
    for i, ((x, y), r) in enumerate(LAYOUT["bones"]):
        placed.append(place(bones, (x, y, 0.0), r, f"bones_{i}", col))
    placed.append(place(floor, (0, 0, 0), 0, "floor", col))
    (sx, sy, sz), sr = LAYOUT["stream"]
    placed.append(place(stream, (sx, sy, sz), sr, "stream", col))
    banners = []
    for i, (ang, r) in enumerate(LAYOUT["banners"]):
        a = math.radians(ang)
        arm_i = banner_arm.copy()
        arm_i.name = f"banner_{i}_rig"
        col.objects.link(arm_i)
        arm_i.location = (r * math.cos(a), r * math.sin(a), 0)
        arm_i.rotation_euler = (0, 0, a + math.pi / 2)
        arm_i.animation_data.action = bpy.data.actions["lf_banner_wind"]
        mesh_i = banner.copy()
        mesh_i.name = f"banner_{i}"
        col.objects.link(mesh_i)
        mesh_i.parent = arm_i
        mesh_i.modifiers["Armature"].object = arm_i
        banners += [arm_i, mesh_i]
    total = sum(core.tri_count(o) for o in placed if o.type == "MESH") + sum(
        core.tri_count(o) for o in banners if o.type == "MESH")
    log("assembled tris", total)
    asm = os.path.join(out_dir, f"{AID}_assembled.glb")
    core.export_glb(asm, placed + banners, animations=True)
    core.write_json(os.path.join(out_dir, f"{AID}_assembled.meta.json"), {
        "id": f"{AID}_assembled", "tris": {"LOD0_total": total}, "budget_tris": 60000,
        "modules": {k: v["tris"] for k, v in meta_all.items()},
        "layout": LAYOUT, "ring_inner_radius_m": AL.R_IN, "floor_radius_m": AL.FLOOR_R,
        "entrance": "main gap centred on Blender -Y (= glTF/Godot +Z), width ~7 m between the banners; side "
                    "paths at 160 deg (back-left) and -18 deg (right) as in art/08",
        "world_placement": {"centre_xyz": [75.0, 6.545627597111355, -86.0], "yaw_deg_about_up": 5.4,
                            "note": "route lf_route_boss enters from z=-65 (south); +5.4 deg aligns the gap with "
                                    "the last route segment (77,-65)->(75,-86)"},
        "clips": {"lf_banner_wind": {"seconds": 4.5, "loop": True}},
    })
    core.save_blend(paths.source(GROUP, f"{AID}.blend"))
    log("saved blend")
    if not args.no_qa:
        import arena_qa
        arena_qa.run(args.iter, placed, banners, mods, floor)


if __name__ == "__main__":
    main()
