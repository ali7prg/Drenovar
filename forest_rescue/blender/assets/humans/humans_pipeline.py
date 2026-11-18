"""Build pipeline: pieces -> LOD0 mesh (budgeted, UV atlas, textures, materials).
Rigging/animation/export are in humans_rig.py / humans_anim.py / humans_export.py."""
import math
import os
import time

import bmesh
import bpy
import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

from frlib import core, paths, texproj

import humans_build as HBLD
import humans_geo as G
import humans_sdf as H
import humans_tex as T

log = HBLD.log


# --------------------------------------------------------------------------- mesh helpers

def obj_from_piece(p, name=None):
    me = bpy.data.meshes.new(name or p.name)
    me.from_pydata(p.verts.tolist(), [], p.faces)
    me.validate(clean_customdata=False)
    if p.uvs and not p.meta.get("sdf"):
        uv = np.array([c for u in p.uvs for c in u], np.float32)
        lay = me.uv_layers.new(name="UVMap")
        lay.data.foreach_set("uv", uv.ravel())
    me.shade_smooth()
    obj = bpy.data.objects.new(name or p.name, me)
    core.link(obj)
    return obj


def set_face_attr(obj, name, values, dtype="INT"):
    me = obj.data
    a = me.attributes.get(name) or me.attributes.new(name, dtype, "FACE")
    a.data.foreach_set("value", np.asarray(values, np.int32 if dtype == "INT" else np.float32))


def get_face_attr(obj, name):
    me = obj.data
    a = me.attributes[name]
    out = np.zeros(len(me.polygons), np.int32)
    a.data.foreach_get("value", out)
    return out


def decimate(obj, target, protect=None, protect_factor=3.0):
    cur = core.tri_count(obj)
    if cur <= target:
        return obj
    mod = obj.modifiers.new("dec", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.use_collapse_triangulate = True
    mod.ratio = max(0.002, target / cur)
    if protect is not None:
        vg = obj.vertex_groups.new(name="protect")
        idx = np.nonzero(protect > 0)[0]
        for val in np.unique(np.round(protect[idx], 2)):
            sel = idx[np.round(protect[idx], 2) == val]
            vg.add(sel.tolist(), float(val), "REPLACE")
        mod.vertex_group = "protect"
        mod.vertex_group_factor = protect_factor
        mod.invert_vertex_group = True
    core.select_only([obj])
    bpy.ops.object.modifier_apply(modifier="dec")
    if obj.vertex_groups.get("protect"):
        obj.vertex_groups.remove(obj.vertex_groups["protect"])
    return obj


def mesh_np(obj):
    me = obj.data
    me.calc_loop_triangles()
    nv = len(me.vertices)
    V = np.empty(nv * 3)
    me.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3)
    M = np.array(obj.matrix_world)
    V = V @ M[:3, :3].T + M[:3, 3]
    nt = len(me.loop_triangles)
    tri = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", tri)
    loops = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get("loops", loops)
    poly = np.empty(nt, np.int64)
    me.loop_triangles.foreach_get("polygon_index", poly)
    luv = np.empty(len(me.loops) * 2)
    me.uv_layers.active.data.foreach_get("uv", luv)
    uv = luv.reshape(-1, 2)[loops.reshape(-1, 3)]
    vn = np.empty(nv * 3)
    me.vertices.foreach_get("normal", vn)
    return V, tri.reshape(-1, 3), uv, vn.reshape(-1, 3), poly


# --------------------------------------------------------------------------- LOD0 assembly

def build_lod0(ctx, budget):
    """Decimate/unwrap pieces, join into one object with face attributes cls/piece/group."""
    spec = ctx.spec
    t0 = time.time()
    classes = []          # global class list
    objs = []
    piece_names = []
    ppart = [p for p in ctx.parts if getattr(p, "cls", None) and getattr(p, "geom", True)]
    body_budget = budget["body"]
    for pi, p in enumerate(ctx.pieces):
        if p.meta.get("optional"):
            continue
        obj = obj_from_piece(p)
        if p.meta.get("sdf"):
            if p.name == "body":
                V = p.verts
                lm = ctx.lm
                d_face = np.linalg.norm((V - (lm["origin"] + np.array([0, 0.03, -0.03]))) * np.array([1, 1, 0.8]), axis=1)
                prot = np.clip(1.4 - d_face / 0.09, 0, 1)
                for S_ in ("Left", "Right"):
                    dh = np.linalg.norm(V - ctx.J[f"{S_}Hand_end"], axis=1)
                    prot = np.maximum(prot, np.clip(1.3 - dh / 0.08, 0, 1) * 0.8)
                decimate(obj, body_budget, protect=prot, protect_factor=4.0)
            else:
                decimate(obj, budget.get(p.name, 400))
        objs.append((p, obj))
        piece_names.append(p.name)
    # classes per face
    for p, obj in objs:
        me = obj.data
        nf = len(me.polygons)
        cent = np.empty(nf * 3)
        me.polygons.foreach_get("center", cent)
        cent = cent.reshape(-1, 3)
        if p.name == "body":
            idx, _ = H.owner(ppart, cent)
            cls = [ppart[i].cls if i >= 0 else "skin" for i in idx]
            # override by class regions declared in the spec (texture-driven material zones)
            if hasattr(spec, "class_regions"):
                cls = spec.class_regions(ctx, cent, cls)
        else:
            cls = [p.cls] * nf
            if hasattr(spec, "piece_classes") and p.name in getattr(spec, "PIECE_CLASS_FN", ()):
                cls = spec.piece_classes(ctx, p.name, cent, cls)
        for c in set(cls):
            if c not in classes:
                classes.append(c)
        set_face_attr(obj, "cls", [classes.index(c) for c in cls])
        set_face_attr(obj, "piece", [piece_names.index(p.name)] * nf)
    # UVs for SDF pieces (body split: head gets its own denser islands)
    final = []
    for p, obj in objs:
        if p.meta.get("sdf"):
            if p.name == "body":
                zc = ctx.L["chin"] - 0.035
                head, rest = split_by(obj, lambda c: c[:, 2] > zc, "body_head", "body_rest")
                T.smart_uv(head, angle=55)
                T.smart_uv(rest, angle=62)
                set_face_attr(head, "uvboost", [1] * len(head.data.polygons))
                final += [head, rest]
                continue
            T.smart_uv(obj, angle=60)
        final.append(obj)
    lod0 = core.join(final, ctx.asset + "_LOD0")
    core.select_only([lod0])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.00005)
    bpy.ops.object.mode_set(mode="OBJECT")
    T.average_scale(lod0)
    boost_uvs(lod0, "uvboost", 1.9)
    T.pack_atlas(lod0, margin=0.003)
    lod0["classes"] = ",".join(classes)
    lod0["pieces"] = ",".join(piece_names)
    log(ctx.asset, "LOD0 %d tris, %d classes, %.1fs" % (core.tri_count(lod0), len(classes), time.time() - t0))
    return lod0, classes


def split_by(obj, pred, name_a, name_b):
    me = obj.data
    nf = len(me.polygons)
    cent = np.empty(nf * 3)
    me.polygons.foreach_get("center", cent)
    sel = pred(cent.reshape(-1, 3))
    b = obj.copy()
    b.data = obj.data.copy()
    core.link(b)
    obj.name, b.name = name_a, name_b
    for o, keep in ((obj, sel), (b, ~sel)):
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.faces.ensure_lookup_table()
        dead = [f for f, k in zip(bm.faces, keep) if not k]
        bmesh.ops.delete(bm, geom=dead, context="FACES")
        bm.to_mesh(o.data)
        bm.free()
    return obj, b


def boost_uvs(obj, attr, factor):
    me = obj.data
    if attr not in me.attributes:
        return
    fl = np.zeros(len(me.polygons), np.int32)
    me.attributes[attr].data.foreach_get("value", fl)
    uv = np.empty(len(me.loops) * 2)
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    ls = np.empty(len(me.polygons), np.int64)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(len(me.polygons), np.int64)
    me.polygons.foreach_get("loop_total", lt)
    sel = np.zeros(len(uv), bool)
    for f in np.nonzero(fl > 0)[0]:
        sel[ls[f]:ls[f] + lt[f]] = True
    c = uv[sel].mean(0)
    uv[sel] = (uv[sel] - c) * factor + c
    me.uv_layers.active.data.foreach_set("uv", uv.ravel())


# --------------------------------------------------------------------------- textures

def texture_lod0(ctx, lod0, classes, size=2048, hi_objs=None):
    """Projection + procedural maps -> images (albedo, orm, normal) and per-group factors."""
    spec = ctx.spec
    t0 = time.time()
    V, tri, uv, vn, poly = mesh_np(lod0)
    fcls = get_face_attr(lod0, "cls")
    Tx, col, w, cls_img = T.project_colours(V, tri, uv, vn, ctx.views, size, fcls, poly)
    valid = Tx.valid
    w = T.reject_outliers(col, w, cls_img, valid)
    col = T.fill_by_class(col, w, cls_img, valid)
    col = texproj.delight(col, Tx, light_dir=(-0.45, -0.55, 0.70), ambient=0.55, strength=0.45, mask=valid)
    # spec colour overrides / painting hooks (e.g. tint unseen areas, emblems)
    if hasattr(spec, "paint"):
        col = spec.paint(ctx, Tx, col, cls_img, classes)
    paint_face(ctx, Tx, col, cls_img, classes)
    # procedural detail per class
    H_ = np.zeros(valid.shape)
    rough = np.full(valid.shape, 0.8)
    metal = np.zeros(valid.shape)
    yy, xx = np.nonzero(valid)
    P = Tx.pos[yy, xx]
    Nn = Tx.nrm[yy, xx]
    cidx = cls_img[yy, xx]
    amult = np.ones(len(yy))
    hv = np.zeros(len(yy))
    rv = np.zeros(len(yy))
    mv = np.zeros(len(yy))
    for ci, c in enumerate(classes):
        sel = cidx == ci
        if not sel.any():
            continue
        rb, mb, kind = T.CLASS_PBR.get(c, (0.8, 0.0, "linen"))
        h, a, r = T.detail_maps(kind, P[sel], Nn[sel], seed=ci * 13)
        hv[sel] = h
        amult[sel] = a
        rv[sel] = rb + r
        mv[sel] = mb
    col[yy, xx] *= amult[:, None]
    H_[yy, xx] = hv
    rough[yy, xx] = np.clip(rv, 0.05, 1.0)
    metal[yy, xx] = mv
    # AO (Cycles bake on LOD0) multiplies the albedo lightly
    ao = bake_ao(lod0, size // 2)
    if ao is not None:
        ao_full = cv2.resize(ao, (size, size), interpolation=cv2.INTER_LINEAR)
        col = col * (0.62 + 0.38 * ao_full[..., None])
    col = np.clip(col, 0, 1)
    # group factors (tintable groups normalised)
    groups = [T.class_group(c, spec) for c in classes]
    gimg = np.full(valid.shape, -1, np.int32)
    gimg[yy, xx] = np.array([T.GROUPS.index(groups[c]) for c in cidx])
    factors = {}
    out = col.copy()
    for gi, g in enumerate(T.GROUPS):
        m = gimg == gi
        if not m.any() or not T.TINTABLE[g]:
            factors[g] = (1.0, 1.0, 1.0)
            continue
        mean = np.median(col[m], axis=0)
        f = mean / max(mean.max(), 1e-3) * 0.97
        hi_ = np.percentile(col[m] / np.maximum(f, 1e-3), 99.0)
        f = f * max(hi_, 1.0) if hi_ > 1.0 else f
        f = np.clip(f, 0.02, 1.0)
        factors[g] = tuple(float(x) for x in f)
        out[m] = np.clip(col[m] / f, 0, 1)
    # margins
    out = texproj.dilate_margin(out, valid, px=8)
    hmap = texproj.fill(H_[..., None], valid)[..., 0]
    nrm_detail = texproj.height_to_normal(hmap, valid, strength=1.2)
    nrm_bake = bake_normal(lod0, hi_objs, size) if hi_objs else None
    if nrm_bake is not None:
        nrm = blend_normals(nrm_bake, nrm_detail)
    else:
        nrm = nrm_detail
    orm = np.stack([np.ones_like(rough), rough, metal], -1)
    orm = texproj.dilate_margin(orm, valid, px=8)
    nrm = texproj.dilate_margin(nrm, valid, px=8)
    log(ctx.asset, "textures %.1fs" % (time.time() - t0))
    return dict(albedo=out, albedo_raw=col, orm=orm, normal=nrm, factors=factors, valid=valid, cls_img=cls_img,
                group_img=gimg, texels=Tx)


import cv2  # noqa: E402


def blend_normals(base, detail):
    """Whiteout blend of two tangent-space normal maps (0..1 encoded)."""
    a = base * 2 - 1
    b = detail * 2 - 1
    n = np.stack([a[..., 0] + b[..., 0], a[..., 1] + b[..., 1], a[..., 2] * b[..., 2]], -1)
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-9)
    return n * 0.5 + 0.5


def _bake_setup(obj, img):
    mats = []
    if not obj.data.materials:
        m = core.material("bake_tmp")
        obj.data.materials.append(m)
    return mats


def bake_ao(obj, size, samples=12):
    img = core.new_image(obj.name + "_ao", size, colorspace="Non-Color", color=(1, 1, 1, 1))
    tmp = core.material("bake_tmp_ao", base=(0.8, 0.8, 0.8, 1))
    saved = [s.material for s in obj.material_slots]
    obj.data.materials.clear()
    obj.data.materials.append(tmp)
    try:
        bpy.context.scene.cycles.samples = samples
        core.bake(obj, "AO", img, margin=8, samples=samples)
        a = core.image_to_numpy(img)[..., 0]
    except Exception as e:  # pragma: no cover
        log("AO bake failed", e)
        a = None
    obj.data.materials.clear()
    for m in saved:
        obj.data.materials.append(m)
    return a


def bake_normal(obj, hi_objs, size):
    img = core.new_image(obj.name + "_nrm", size, colorspace="Non-Color", color=(0.5, 0.5, 1, 1))
    tmp = core.material("bake_tmp_n", base=(0.8, 0.8, 0.8, 1))
    saved = [s.material for s in obj.material_slots]
    obj.data.materials.clear()
    obj.data.materials.append(tmp)
    hi = core.join(hi_objs, "bake_hi") if len(hi_objs) > 1 else hi_objs[0]
    try:
        core.bake(obj, "NORMAL", img, margin=8, samples=1, selected_to_active=hi, cage_extrusion=0.012,
                  max_ray_distance=0.03)
        n = core.image_to_numpy(img)[..., :3]
    except Exception as e:  # pragma: no cover
        log("normal bake failed", e)
        n = None
    bpy.data.objects.remove(hi, do_unlink=True)
    obj.data.materials.clear()
    for m in saved:
        obj.data.materials.append(m)
    return n


# --------------------------------------------------------------------------- face painting

def paint_face(ctx, Tx, col, cls_img, classes):
    lm = ctx.lm
    spec = ctx.spec
    fp = getattr(spec, "FACE_PAINT", {})
    yy, xx = np.nonzero(Tx.valid)
    P = Tx.pos[yy, xx]
    cid = cls_img[yy, xx]
    s = lm["scale"]
    iris = np.array(fp.get("iris", (0.28, 0.20, 0.13)))
    if "eye" in classes:
        ei = classes.index("eye")
        sel = cid == ei
        for key in ("eye_l", "eye_r"):
            c = lm[key] + np.array([0, 0.0122, 0]) * s   # eyeball centre
            d = P[sel] - c
            d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
            gaze = np.array(fp.get("gaze", (0.0, -1.0, 0.08)))
            gaze /= np.linalg.norm(gaze)
            ang = np.degrees(np.arccos(np.clip(d @ gaze, -1, 1)))
            near = np.linalg.norm(P[sel] - c, axis=1) < 0.02 * s
            idx = np.nonzero(sel)[0][near]
            a = ang[near]
            sclera = np.array(fp.get("sclera", (0.78, 0.72, 0.66)))
            colv = np.where((a < 11)[:, None], np.array([0.05, 0.04, 0.035]),
                            np.where((a < 24)[:, None], iris * (0.75 + 0.25 * (a[:, None] / 24)), sclera))
            col[yy[idx], xx[idx]] = colv
    # eyebrows on skin texels (arched strokes above each eye)
    if "skin" in classes and fp.get("brows", True):
        si = classes.index("skin")
        sel = np.nonzero(cid == si)[0]
        Q = P[sel]
        bc = np.array(fp.get("brow_col", (0.16, 0.11, 0.08)))
        for key, sx in (("eye_l", 1), ("eye_r", -1)):
            e = lm[key]
            dx = (Q[:, 0] - e[0]) * sx / s
            arch = 0.0135 + 0.006 * np.cos(np.clip(dx / 0.026, -1.4, 1.4) * 1.1) - 0.002 * (dx > 0.01)
            dz = (Q[:, 2] - e[2]) / s - arch
            th = fp.get("brow_thick", 0.0035)
            m = (np.abs(dx) < 0.024) & (np.abs(dz) < th) & (Q[:, 1] < e[1] + 0.03 * s)
            fall = np.clip(1 - np.abs(dz[m]) / th, 0, 1) * np.clip(1 - np.abs(dx[m]) / 0.024, 0, 1) ** 0.3
            k = sel[m]
            col[yy[k], xx[k]] = col[yy[k], xx[k]] * (1 - 0.75 * fall[:, None]) + bc * 0.75 * fall[:, None]
    if "lip" in classes:
        li = classes.index("lip")
        sel = np.nonzero(cid == li)[0]
        tint = np.array(fp.get("lip_tint", (1.08, 0.86, 0.84)))
        col[yy[sel], xx[sel]] = np.clip(col[yy[sel], xx[sel]] * tint, 0, 1)
    if fp.get("stubble", 0) > 0 and "skin" in classes:
        si = classes.index("skin")
        sel = np.nonzero(cid == si)[0]
        Q = (P[sel] - lm["origin"]) / s
        m = (Q[:, 2] < -0.035) & (Q[:, 2] > -0.125) & (Q[:, 1] < 0.07)
        k = sel[m]
        nz = texproj.value_noise(P[m], 900.0, seed=4)
        col[yy[k], xx[k]] *= (1 - fp["stubble"] * (0.6 + 0.4 * nz))[:, None]


# --------------------------------------------------------------------------- materials

def save_textures(asset, tex, gl_size=1024):
    d = paths.ensure(paths.TEXTURE_SOURCES, "humans")
    out = {}
    for key, arr, fmt in (("albedo", tex["albedo"], "png"), ("orm", tex["orm"], "png"), ("normal", tex["normal"], "png")):
        p = os.path.join(d, f"{asset}_{key}.{fmt}")
        core.save_rgba(p, arr)
        out[key] = p
    # game sizes: JPEG albedo/ORM, PNG normal
    from PIL import Image
    gd = paths.ensure(paths.SOURCES, "humans", "_gl_textures")
    for key, ext in (("albedo", "jpg"), ("orm", "jpg"), ("normal", "png")):
        im = Image.open(out[key]).convert("RGB").resize((gl_size, gl_size), Image.LANCZOS)
        p = os.path.join(gd, f"{asset}_{key}.{ext}")
        if ext == "jpg":
            im.save(p, quality=90)
        else:
            im.save(p, optimize=True)
        out[key + "_gl"] = p
    return out


def make_materials(asset, lod0, classes, spec, tex_paths, factors):
    imgs = {
        "albedo": core.load_image(tex_paths["albedo_gl"], "sRGB", name=f"{asset}_albedo"),
        "orm": core.load_image(tex_paths["orm_gl"], "Non-Color", name=f"{asset}_orm"),
        "normal": core.load_image(tex_paths["normal_gl"], "Non-Color", name=f"{asset}_normal"),
    }
    mats = []
    for g in T.GROUPS:
        m = group_material(f"{asset}_{g}", imgs, factors.get(g, (1, 1, 1)))
        mats.append(m)
    lod0.data.materials.clear()
    for m in mats:
        lod0.data.materials.append(m)
    fcls = get_face_attr(lod0, "cls")
    gi = np.array([T.GROUPS.index(T.class_group(classes[c], spec)) for c in fcls], np.int32)
    lod0.data.polygons.foreach_set("material_index", gi)
    lod0.data.update()
    return mats, imgs


def group_material(name, imgs, factor):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    ta = nt.nodes.new("ShaderNodeTexImage")
    ta.image = imgs["albedo"]
    if tuple(factor) != (1.0, 1.0, 1.0):
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        nt.links.new(ta.outputs["Color"], mix.inputs[6])
        mix.inputs[7].default_value = (*factor, 1.0)
        nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    else:
        nt.links.new(ta.outputs["Color"], bsdf.inputs["Base Color"])
    to = nt.nodes.new("ShaderNodeTexImage")
    to.image = imgs["orm"]
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(to.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = imgs["normal"]
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    mat["tint_factor"] = list(factor)
    return mat
