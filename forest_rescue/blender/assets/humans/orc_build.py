"""Blender assembly of lf_orc_warden: numpy pieces (orc_geo) -> skinned objects -> one LOD0 mesh with
texture classes as face attributes -> UV atlas with per-island texel density -> Cycles AO bake ->
painted 2048 atlas (orc_tex) -> QA / export materials."""
import math
import os
import time

import bmesh
import bpy
import numpy as np

import hv2_blender as HBL
import hv2_drape as HD
import hv2_rig as HR
import orc_geo as G
import orc_tex as OT
import spec_lf_orc_warden as SP
from frlib import core, paths, texproj

T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:7.1f}s]", *a, flush=True)


def slot_materials():
    out = []
    for m in SP.MATERIALS:
        nm = f"_slot_{m}"
        mat = bpy.data.materials.get(nm) or bpy.data.materials.new(nm)
        mat.use_nodes = True
        out.append(mat)
    return out


def outward_normals(obj):
    """Consistent outward winding (hv2_hand / tube pieces can come out partly inverted, which bakes black AO
    and gets back-face culled in the engine)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()


def set_aux(obj, aux):
    a = obj.data.attributes.get("aux") or obj.data.attributes.new("aux", "FLOAT2", "POINT")
    a.data.foreach_set("vector", np.asarray(aux, np.float32).ravel())


def finish_faces(obj, cls_names, pid, slots, flat=False):
    me = obj.data
    nf = len(me.polygons)
    if isinstance(cls_names, str):
        cls_names = [cls_names] * nf
    cid = np.array([OT.CID[c] for c in cls_names], np.int32)
    HBL.face_attr(obj, "cls", cid)
    HBL.face_attr(obj, "pid", np.full(nf, pid, np.int32))
    me.materials.clear()
    for m in slots:
        me.materials.append(m)
    mi = np.array([SP.MATERIALS.index(SP.MATERIAL_OF[c]) for c in cls_names], np.int32)
    me.polygons.foreach_set("material_index", mi)
    sm = np.full(nf, not flat, bool)
    me.polygons.foreach_set("use_smooth", sm)
    HBL.face_attr(obj, "uvw", np.full(nf, 1000, np.int32))
    me.update()


def piece_object(p, body_ref, pid, slots):
    ob = HBL.obj_from(f"{SP.ID}_{p.name}", p.V, p.F)
    W = p.weights(p.V) if callable(p.weights) else p.weights
    if W is None:
        W = G.transfer(p.V, *body_ref)
    HR.groups_from_dicts(ob, W)
    set_aux(ob, np.zeros((len(p.V), 2)) if p.aux is None else p.aux)
    if p.solid is None:
        outward_normals(ob)
    if p.decimate and core.tri_count(ob) > p.decimate:
        HBL.decimate(ob, p.decimate)
    uvw = None
    if p.solid:
        HBL.solidify(ob, p.solid, offset=-1.0)
        uvw = hidden_sides(ob, p)
    finish_faces(ob, p.cls_faces or p.cls, pid, slots, flat=p.flat)
    HBL.face_attr(ob, "uvw", np.full(len(ob.data.polygons), 1000, np.int32) if uvw is None else uvw)
    return ob


def hidden_sides(ob, p):
    """UV weight (permille) of a solidified sheet: rims and the side facing the body get little texture."""
    me = ob.data
    co = np.array([v.co[:] for v in me.vertices])
    cen = np.array([f.center[:] for f in me.polygons])
    nrm = np.array([f.normal[:] for f in me.polygons])
    mine = np.array([min(np.linalg.norm(co[f.vertices[i]] - co[f.vertices[(i + 1) % len(f.vertices)]])
                         for i in range(len(f.vertices))) for f in me.polygons])
    if getattr(p, "inner_ref", None) is not None:
        out = cen - np.asarray(p.inner_ref, float)
    else:
        out = cen - np.stack([np.zeros(len(cen)), np.full(len(cen), 0.035), cen[:, 2]], 1)
    out /= np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)
    inner = (nrm * out).sum(1) < -0.25
    rim = mine < p.solid * 1.8
    return np.where(rim, 350, np.where(inner, 400, 1000)).astype(np.int32)


# --------------------------------------------------------------------------- pieces -> objects

def build(log=log):
    J = G.joints()
    slots = slot_materials()
    fld, parts, prof = G.body_field(J, SP.VOXEL)
    bv, bf = fld.mesh()
    log("body MC", len(bv), "verts", len(bf), "tris")
    body = HBL.obj_from(f"{SP.ID}_body", bv, bf)
    o, s = G.head_frame()
    hem_pts = SP.MANTLE["hem"]

    def prot(vv):
        q = (vv - o) / s
        head = (vv[:, 2] > 1.80) & (np.abs(q[:, 0]) < 0.25)
        face = head & (q[:, 2] > -0.21) & (q[:, 2] < 0.08) & (q[:, 1] < -0.03) & (np.abs(q[:, 0]) < 0.125)
        ears = head & (np.abs(q[:, 0]) > 0.085) & (q[:, 2] > -0.08) & (q[:, 2] < 0.11)
        phi = np.degrees(np.abs(np.arctan2(vv[:, 0], -(vv[:, 1] - 0.03))))
        hem = np.interp(phi, [a for a, _ in hem_pts], [b for _, b in hem_pts])
        under_mantle = (vv[:, 2] > hem + 0.06) & (vv[:, 2] < 1.80) & (np.abs(vv[:, 0]) < 0.30)
        under_kilt = (vv[:, 2] > 0.74) & (vv[:, 2] < 1.10) & (np.abs(vv[:, 0]) < 0.30)
        w = np.full(len(vv), 0.30)
        w[under_mantle | under_kilt] = 0.0
        w[head] = 0.70
        w[face | ears] = 1.0
        return w
    HBL.decimate(body, 30000)
    log("body pre-decimated", core.tri_count(body))
    bvv = np.array([v.co[:] for v in body.data.vertices])
    btri = np.array([p.vertices[:] for p in body.data.polygons])
    Wd = G.body_weights(bvv, parts, J)
    names, M = HR.normalize_top4(Wd, len(bvv))
    M = HR.smooth_weights(names, M, btri, iters=6, factor=0.5)
    names, M = HR.normalize_top4({n: M[:, j] for j, n in enumerate(names)}, len(bvv))
    HR.assign_groups(body, names, M)
    body_ref = (bvv, names, M)
    set_aux(body, np.zeros((len(bvv), 2)))
    piece_names = ["body"]
    objs = [body]
    # ---- hands
    hands = G.hands(J)
    hand_bones = {}
    for S_, (acc, bones) in hands.items():
        V, Fc, Wts = acc.arrays()
        p = G.Piece(f"hand_{S_}", V, Fc, "skin", Wts)
        objs.append(piece_object(p, body_ref, len(piece_names), slots))
        piece_names.append(p.name)
        hand_bones[S_] = bones
    # ---- support table (no arms) for garments
    sup = G.support_field(J, prof)
    T = HD.BodyTable(sup, 0.0, 0.035, 0.05, 1.90, dz=0.01)
    log("body table ready")
    pieces = []
    mv, mf = G.mantle(fld)
    log("mantle MC", len(mf))

    def mantle_w(V):
        W = G.transfer(V, *body_ref)
        out = []
        for p, w in zip(V, W):
            c = float(np.clip((1.64 - p[2]) / 0.20, 0, 1) * np.clip((p[1] - 0.05) / 0.08, 0, 1))
            c2 = float(np.clip((1.52 - p[2]) / 0.10, 0, 1))
            if c > 0:
                w = {k: v * (1 - 0.7 * c) for k, v in w.items()}
                w["Cloak1"] = w.get("Cloak1", 0) + 0.7 * c * (1 - c2)
                w["Cloak2"] = w.get("Cloak2", 0) + 0.7 * c * c2
            out.append(w)
        return out
    pieces.append(G.Piece("mantle", mv, mf, "fur", mantle_w, decimate=SP.MANTLE["tris"]))
    hv, hf = G.topknot(fld)
    log("hair MC", len(hf))
    pieces.append(G.Piece("hair", hv, hf, "hair", G.hair_weights, decimate=780))
    pieces += G.tusks()
    pieces += G.pauldron(J)
    hp, ring_c = G.harness(fld)
    pieces += hp
    pieces += G.belt(sup, T)
    pieces += G.trinkets(T)
    pieces += G.kilt(T)
    pieces += G.wraps(fld, J)
    sp_pieces, staff_info = G.staff(hand_bones)
    pieces += sp_pieces
    for p in pieces:
        objs.append(piece_object(p, body_ref, len(piece_names), slots))
        piece_names.append(p.name)
    budget_pass(objs, piece_names, body, prot)
    cen = np.array([p.center[:] for p in body.data.polygons])
    finish_faces(body, list(G.label_of(cen, parts)), 0, slots)
    ginfo = dict(skirt_top=SP.KILT["z_top"], skirt_hem=0.60, cloak_hem=1.40,
                 bag=(0.17, float(T.cy - T.hull(np.array([1.02]), np.array([0.5]))[0]) - 0.06, 1.02))
    info = dict(J=J, T=T, hand_bones=hand_bones, staff=staff_info, ring=ring_c, pieces=piece_names, ginfo=ginfo,
                body_ref=body_ref, parts=parts, prof=prof)
    return objs, info


def budget_pass(objs, names, body, prot):
    """Body gets the triangles the pieces leave (face / ears protected, hidden torso under the
    mantle and kilt thinned first); the mantle shrinks only if the body would drop below 5600."""
    limit = int(SP.BUDGET[0] * 0.985)
    others = sum(core.tri_count(o) for o in objs if o is not body)
    target = limit - others
    if target < 5600:
        m = next(o for o in objs if o.name.endswith("_mantle"))
        n = core.tri_count(m)
        HBL.decimate(m, max(1300, n - (5600 - target)), stage=10 ** 9)
        others = sum(core.tri_count(o) for o in objs if o is not body)
        target = limit - others
    HBL.decimate(body, int(target), protect=prot, factor=4.0, stage=10 ** 9)
    total = sum(core.tri_count(o) for o in objs)
    rows = sorted(((core.tri_count(o), o.name.replace(SP.ID + "_", "")) for o in objs), reverse=True)
    log("LOD0 tris", total, "pieces", [r for r in rows if r[0] >= 90])


# --------------------------------------------------------------------------- join + UV

UV_SCALE = {"skin": 1.0, "eye": 1.6, "tusk": 1.3, "hair": 0.85, "fur": 0.80, "leather": 1.0, "boot": 0.9,
            "cloth_dark": 0.8, "cloth_red": 1.0, "linen": 0.85, "iron": 1.0, "bone": 1.1, "staff_bone": 0.8,
            "staff_iron": 0.8, "staff_leather": 0.8, "crystal": 0.6}


def join(objs):
    lo = core.join(objs, name=f"{SP.ID}_LOD0")
    return lo


def face_cls(obj):
    return HBL.face_attr_get(obj, "cls")


def uv_islands(me):
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    nl = len(me.loops)
    uv = np.empty(nl * 2)
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    lv = np.empty(nl, np.int64)
    me.loops.foreach_get("vertex_index", lv)
    key = np.stack([lv, np.round(uv[:, 0] * 2 ** 20).astype(np.int64), np.round(uv[:, 1] * 2 ** 20).astype(np.int64)], 1)
    _, node = np.unique(key, axis=0, return_inverse=True)
    node = node.ravel()
    ls = np.empty(len(me.polygons), np.int64)
    lt = np.empty(len(me.polygons), np.int64)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    a, b = [], []
    for k in range(lt.max()):
        sel = lt > k
        i0 = ls[sel] + k
        i1 = ls[sel] + (k + 1) % lt[sel]
        a.append(node[i0])
        b.append(node[i1])
    a = np.concatenate(a)
    b = np.concatenate(b)
    nn = node.max() + 1
    g = coo_matrix((np.ones(len(a)), (a, b)), shape=(nn, nn))
    _, comp = connected_components(g, directed=False)
    loop_island = comp[node]
    face_island = loop_island[ls]
    return uv, loop_island, face_island, ls, lt


def uv_layout(lo):
    core.smart_uv(lo, angle=62.0, margin=0.002)
    me = lo.data
    uv, li, fi, ls, lt = uv_islands(me)
    cls = face_cls(lo)
    o, s = G.head_frame()
    cen = np.array([p.center[:] for p in me.polygons])
    area = np.array([p.area for p in me.polygons])
    q = (cen - o) / s
    uvw = HBL.face_attr_get(lo, "uvw")
    uvw = np.where(uvw <= 0, 1000, uvw)          # objects without the attribute (the body) join as 0
    fac = np.array([UV_SCALE[OT.CLASSES[c]] for c in cls]) * uvw / 1000.0
    head = (cen[:, 2] > 1.80) & (np.abs(q[:, 0]) < 0.20) & (cls == OT.CID["skin"])
    face = head & (q[:, 1] < -0.04) & (q[:, 2] > -0.22) & (q[:, 2] < 0.08)
    fac = np.where(head, 1.45, fac)
    fac = np.where(face, 2.2, fac)
    hands = (cls == OT.CID["skin"]) & (cen[:, 2] < 1.0) & (np.abs(cen[:, 0]) > 0.36)
    fac = np.where(hands, 1.15, fac)
    nisl = fi.max() + 1
    num = np.bincount(fi, weights=fac * area, minlength=nisl)
    den = np.bincount(fi, weights=area, minlength=nisl)
    isl_fac = num / np.maximum(den, 1e-12)
    ctr = np.zeros((nisl, 2))
    cnt = np.bincount(li, minlength=nisl).astype(float)
    for k in range(2):
        ctr[:, k] = np.bincount(li, weights=uv[:, k], minlength=nisl) / np.maximum(cnt, 1)
    uv2 = ctr[li] + (uv - ctr[li]) * isl_fac[li][:, None]
    me.uv_layers.active.data.foreach_set("uv", uv2.ravel())
    core.pack_uv(lo, margin=0.0025, rotate=True)
    log("UV islands", nisl)


# --------------------------------------------------------------------------- AO + curvature + paint

def bake_ao(lo, size=1024, samples=24, distance=0.30):
    scene = bpy.context.scene
    if scene.world is None:
        scene.world = bpy.data.worlds.new("orc_world")
    scene.world.light_settings.distance = distance
    img = bpy.data.images.new("orc_ao", size, size, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    core.bake(lo, "AO", img, margin=6, samples=samples)
    a = core.image_to_numpy(img)[..., 0]
    bpy.data.images.remove(img)
    return a


def mesh_data(lo):
    me = lo.data
    me.calc_loop_triangles()
    nv = len(me.vertices)
    V = np.empty(nv * 3)
    me.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3)
    Nv = np.empty(nv * 3)
    me.vertices.foreach_get("normal", Nv)
    Nv = Nv.reshape(-1, 3)
    nt = len(me.loop_triangles)
    tris = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", tris)
    tris = tris.reshape(-1, 3)
    loops = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get("loops", loops)
    loops = loops.reshape(-1, 3)
    tpoly = np.empty(nt, np.int64)
    me.loop_triangles.foreach_get("polygon_index", tpoly)
    nl = len(me.loops)
    luv = np.empty(nl * 2)
    me.uv_layers.active.data.foreach_get("uv", luv)
    luv = luv.reshape(-1, 2)
    aux = np.empty(nv * 2, np.float32)
    me.attributes["aux"].data.foreach_get("vector", aux)
    return V, Nv, tris, luv[loops], tpoly, aux.reshape(-1, 2).astype(float)


def curvature(V, Nv, tris):
    from frlib import sdf
    A = sdf.adjacency_matrix(len(V), tris)
    lap = A @ V - V
    e = np.concatenate([np.linalg.norm(V[tris[:, i]] - V[tris[:, (i + 1) % 3]], axis=1) for i in range(3)])
    vi = np.concatenate([tris[:, i] for i in range(3)])
    el = np.bincount(vi, weights=e, minlength=len(V)) / np.maximum(np.bincount(vi, minlength=len(V)), 1)
    c = -(lap * Nv).sum(1) / np.maximum(el, 1e-4)
    return np.clip(c * 2.5, -1, 1)


def paint_atlas(lo, info, ao_img):
    V, Nv, tris, tuv, tpoly, aux = mesh_data(lo)
    size = SP.TEX
    T = texproj.rasterize_uv(V, tris, tuv, size, Nv)
    yy, xx = np.nonzero(T.valid)
    tri = T.tri[yy, xx]
    bary = T.bary[yy, xx]
    P = T.pos[yy, xx]
    N = T.nrm[yy, xx]
    cls_f = face_cls(lo)
    pid_f = HBL.face_attr_get(lo, "pid")
    cls = cls_f[tpoly[tri]]
    pid = pid_f[tpoly[tri]]
    auxt = (aux[tris[tri]] * bary[..., None]).sum(1)
    cv = curvature(V, Nv, tris)
    cvt = (cv[tris[tri]] * bary).sum(1)
    import cv2
    ao = cv2.resize(ao_img.astype(np.float32), (size, size), interpolation=cv2.INTER_LINEAR)[yy, xx]
    ctx = paint_context(info)
    for k, nm in enumerate(info["pieces"]):
        m = pid == k
        if m.sum() > 50:
            med = float(np.median(ao[m]))
            if med < 0.35:
                log("  low AO piece", nm, round(med, 3))
    log("painting texels", len(P))
    col = OT.paint(P, N, cls, pid, auxt, ao.astype(float), cvt, ctx, log=log)
    img = np.zeros((size, size, 3))
    img[yy, xx] = col
    img = texproj.dilate_margin(img, T.valid, 8)
    return img


def paint_context(info):
    J = info["J"]
    o, s = G.head_frame()
    tips, knuckles = {}, {}
    for S in ("Left", "Right"):
        hb = info["hand_bones"][S]
        d, t, n = hb["_frame"]
        tips[S] = [(hb[f"_{f}tip"], -n) for f in ("Index", "Middle", "Ring", "Pinky")]
        tips[S].append((hb[f"{S}Thumb2"][1], -n))
        knuckles[S] = [hb[f"{S}{f}1"][0] for f in ("Index", "Middle", "Ring", "Pinky")]
    hem_pts = SP.MANTLE["hem"]

    def hem_fn(P):
        phi = np.degrees(np.abs(np.arctan2(P[:, 0], -(P[:, 1] - 0.03))))
        return np.interp(phi, [a for a, _ in hem_pts], [b for _, b in hem_pts])
    scars = [(np.array([0.06, -0.215, 1.56]), np.array([0.20, -0.175, 1.43])),
             (np.array([0.36, -0.06, 1.52]), np.array([0.40, -0.02, 1.42])),
             (G.H((-0.070, -0.100, 0.040)), G.H((-0.030, -0.125, -0.030))),
             (np.array([-0.08, -0.22, 1.30]), np.array([-0.02, -0.23, 1.25]))]
    return dict(J=J, head_o=o, head_s=s, tips=tips, knuckles=knuckles, bun=G.H((0.0, 0.082, 0.168)),
                braid=G.braid_path(), hem_fn=hem_fn, pieces=info["pieces"], scars=scars)


def save_atlas(img):
    from PIL import Image
    master = paths.texture_master(SP.GROUP, f"{SP.ID}_color_master.png")
    core.save_rgba(master, img)
    jpg = master.replace("_color_master.png", "_color.jpg")
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(jpg, quality=90)
    return master, jpg


# --------------------------------------------------------------------------- materials

def qa_materials(img_path):
    img = core.load_image(img_path)
    mats = []
    for m in SP.MATERIALS:
        if m == "glow":
            mt = HBL.painted_material(f"{SP.ID}_{m}_qa", img, k=0.0, light=SP.LIGHT)
            em = next(n for n in mt.node_tree.nodes if n.type == "EMISSION")
            em.inputs["Strength"].default_value = 1.7
        else:
            mt = HBL.painted_material(f"{SP.ID}_{m}_qa", img, k=SP.PAINTED_LIGHT_MIX, light=SP.LIGHT)
        mats.append(mt)
    return mats


def export_materials(img_path):
    img = core.load_image(img_path)
    mats = []
    for m in SP.MATERIALS:
        if m == "glow":
            mt = core.material(f"{SP.ID}_glow", base_tex=img, rough=SP.ROUGH[m], emission=(*SP.GLOW["color"], 1.0),
                               emission_strength=SP.GLOW["strength"])
        else:
            mt = core.material(f"{SP.ID}_{m}", base_tex=img, rough=SP.ROUGH[m])
        bsdf = next(n for n in mt.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        bsdf.inputs["Specular IOR Level"].default_value = 0.0 if m == "hair" else (0.35 if m == "glow" else 0.12)
        mats.append(mt)
    return mats


def assign(lo, mats):
    me = lo.data
    for i, m in enumerate(mats):
        if i < len(me.materials):
            me.materials[i] = m
        else:
            me.materials.append(m)


def clay_material():
    img = bpy.data.images.get("clay") or bpy.data.images.new("clay", 8, 8)
    img.generated_color = (0.72, 0.70, 0.66, 1.0)
    return HBL.painted_material("clay_qa", img, k=0.85, light=(-0.5, -0.7, 0.6))
