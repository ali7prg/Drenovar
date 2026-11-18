"""Skinning, canonical re-rest and LOD meshes for the shared `human_shared` skeleton."""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector
from scipy import sparse
from scipy.spatial import cKDTree

from frlib import core, sdf as fsdf

import humans_pipeline as PL
import humans_sdf as H
import humans_skel as SK

log = PL.log


def weight_parts(J, L):
    """Weight-only primitives for torso bones (the clothed torso geometry has no bone)."""
    s = L["crown"] / 1.75
    P = []

    def w(p, bone):
        return H.tag(p, bone=bone, geom=False, cls=None)

    hz = J["Hips"][2]
    P.append(w(fsdf.ellipsoid(J["Hips"] + np.array([0, 0, -0.04 * s]), np.array([0.13, 0.09, 0.08]) * s), "Hips"))
    P.append(w(fsdf.round_cone(J["Spine"], J["Chest"], 0.09 * s, 0.10 * s), "Spine"))
    P.append(w(fsdf.round_cone(J["Chest"], J["UpperChest"], 0.10 * s, 0.10 * s), "Chest"))
    P.append(w(fsdf.round_cone(J["UpperChest"], J["Neck"] + np.array([0, 0, -0.02 * s]), 0.10 * s, 0.07 * s),
               "UpperChest"))
    for S_, sx in SK.SIDES:
        P.append(w(fsdf.round_cone(J[f"{S_}Shoulder"] + np.array([sx * 0.03 * s, 0, 0]), J[f"{S_}UpperArm"],
                                   0.05 * s, 0.06 * s), f"{S_}Shoulder"))
    return P


def adjacency(nv, faces):
    rows, cols = [], []
    for f in faces:
        k = len(f)
        for i in range(k):
            rows += [f[i], f[(i + 1) % k]]
            cols += [f[(i + 1) % k], f[i]]
    A = sparse.coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(nv, nv)).tocsr()
    A.data[:] = 1.0
    deg = np.asarray(A.sum(1)).ravel()
    deg[deg == 0] = 1
    return sparse.diags(1.0 / deg) @ A


def limit(W, top=4, min_w=0.02):
    return fsdf.limit_weights(W, top=top, min_w=min_w)


def body_weights(V, faces, parts, bones, falloff=0.032, smooth_iters=6):
    idx = {b: i for i, b in enumerate(bones)}
    W = np.zeros((len(V), len(bones)))
    for p in parts:
        b = getattr(p, "bone", None)
        if b is None or b not in idx:
            continue
        lo, hi = p.lo - 0.25, p.hi + 0.25
        sel = np.all((V >= lo) & (V <= hi), axis=1)
        if not sel.any():
            continue
        d = p.fn(V[sel])
        wv = np.exp(-np.maximum(d, 0.0) / falloff) * getattr(p, "weight", 1.0)
        j = idx[b]
        W[sel, j] = np.maximum(W[sel, j], wv)
    A = adjacency(len(V), faces)
    for _ in range(smooth_iters):
        W = 0.5 * W + 0.5 * (A @ W)
    # sharpen: keep dominant bones
    W = W ** 1.6
    return limit(W)


def transfer(Vsrc, Wsrc, Vdst, k=4):
    tree = cKDTree(Vsrc)
    d, i = tree.query(Vdst, k=k)
    w = 1.0 / np.maximum(d, 1e-4) ** 2
    w /= w.sum(1, keepdims=True)
    return np.einsum("nk,nkb->nb", w, Wsrc[i])


def skirt_weights(V, Wbody_t, bones, center, top_z, hem_z, follow=0.3, back_bones=True):
    idx = {b: i for i, b in enumerate(bones)}
    n = len(V)
    W = np.zeros((n, len(bones)))
    th = np.arctan2(V[:, 0] - center[0], -(V[:, 1] - center[1]))      # 0 = front, +left
    v = np.clip((top_z - V[:, 2]) / max(top_z - hem_z, 1e-3), 0, 1)
    a = np.abs(th)
    wf = np.clip(1 - a / (math.pi * 0.42), 0, 1)
    wb = np.clip((a - math.pi * 0.58) / (math.pi * 0.42), 0, 1)
    ws = np.clip(1 - np.abs(a - math.pi / 2) / (math.pi * 0.42), 0, 1)
    wl = ws * (th > 0)
    wr = ws * (th < 0)
    lower = np.clip((v - 0.35) / 0.4, 0, 1)
    for nm, ww in (("SkirtFront", wf), ("SkirtBack", wb)):
        W[:, idx[nm + "1"]] += ww * (1 - lower)
        W[:, idx[nm + "2"]] += ww * lower
    W[:, idx["SkirtLeft"]] += wl
    W[:, idx["SkirtRight"]] += wr
    W /= np.maximum(W.sum(1, keepdims=True), 1e-9)
    top = np.clip(1 - v / 0.18, 0, 1)
    legs = np.zeros(n)
    for b in ("LeftUpperLeg", "RightUpperLeg", "LeftLowerLeg", "RightLowerLeg"):
        legs += Wbody_t[:, idx[b]]
    mix = top[:, None] * Wbody_t + (1 - top)[:, None] * W
    mix = (1 - follow * legs * v)[:, None] * mix + (follow * legs * v)[:, None] * Wbody_t
    return limit(mix)


def cape_weights(V, Wbody_t, bones, top_z, hem_z, side_bones=False, center=(0.0, 0.0)):
    idx = {b: i for i, b in enumerate(bones)}
    n = len(V)
    v = np.clip((top_z - V[:, 2]) / max(top_z - hem_z, 1e-3), 0, 1)
    W = np.zeros((n, len(bones)))
    W[:, idx["Cape1"]] = np.clip(1.4 - np.abs(v - 0.35) * 2.2, 0, 1)
    W[:, idx["Cape2"]] = np.clip((v - 0.4) * 2.0, 0, 1)
    if side_bones:
        th = np.arctan2(V[:, 0] - center[0], -(V[:, 1] - center[1]))
        side = np.clip(1 - np.abs(np.abs(th) - math.pi * 0.45) / 0.9, 0, 1) * np.clip(v * 1.6 - 0.3, 0, 1)
        W[:, idx["SkirtLeft"]] += side * (th > 0) * 0.8
        W[:, idx["SkirtRight"]] += side * (th < 0) * 0.8
    W /= np.maximum(W.sum(1, keepdims=True), 1e-9)
    top = np.clip(1 - v / 0.30, 0, 1)
    mix = top[:, None] * Wbody_t + (1 - top)[:, None] * W
    return limit(mix)


def compute_weights(ctx, lod0, pieces_order):
    """Per-vertex weights for the joined LOD0 according to each piece's rule."""
    bones = SK.BONES
    V, tri, uv, vn, poly = PL.mesh_np(lod0)
    me = lod0.data
    nv = len(me.vertices)
    fpiece = PL.get_face_attr(lod0, "piece")
    vpiece = np.full(nv, -1)
    faces = [list(p.vertices) for p in me.polygons]
    for f, pi in zip(faces, fpiece):
        vpiece[f] = pi
    names = pieces_order
    rules = {p.name: p.rule for p in ctx.pieces}
    body_ids = [i for i, n in enumerate(names) if n == "body"]
    parts = [p for p in ctx.parts if getattr(p, "bone", None)] + weight_parts(ctx.J, ctx.L)
    bmask = np.isin(vpiece, body_ids)
    bidx = np.nonzero(bmask)[0]
    remap = -np.ones(nv, int)
    remap[bidx] = np.arange(len(bidx))
    bfaces = [[remap[i] for i in f] for f, pi in zip(faces, fpiece) if pi in body_ids]
    Wb = body_weights(V[bidx], bfaces, parts, bones)
    W = np.zeros((nv, len(bones)))
    W[bidx] = Wb
    for pi, nm in enumerate(names):
        if nm == "body":
            continue
        sel = np.nonzero(vpiece == pi)[0]
        if len(sel) == 0:
            continue
        rule = rules.get(nm, {"type": "body"})
        t = rule.get("type", "body")
        Wt = transfer(V[bidx], Wb, V[sel])
        if t == "rigid":
            w = np.zeros((len(sel), len(bones)))
            w[:, bones.index(rule["bone"])] = 1.0
        elif t == "skirt":
            w = skirt_weights(V[sel], Wt, bones, ctx.center, rule["top_z"], rule["hem_z"], rule.get("follow", 0.3))
        elif t == "cape":
            w = cape_weights(V[sel], Wt, bones, rule["top_z"], rule["hem_z"], rule.get("side", False), ctx.center)
        elif t == "hood":
            w = np.zeros((len(sel), len(bones)))
            hz = rule.get("pivot_z", ctx.J["Head"][2])
            f = np.clip((V[sel, 2] - (hz - 0.05)) / 0.12, 0, 1)
            w[:, bones.index("Head")] = f * (1 - rule.get("lag", 0.35))
            w[:, bones.index("Hood")] = f * rule.get("lag", 0.35)
            w += (1 - f)[:, None] * Wt
            w = limit(w)
        elif t == "blend":
            w = np.zeros((len(sel), len(bones)))
            for b, val in rule["bones"].items():
                w[:, bones.index(b)] = val
            w = limit(w)
        else:
            w = limit(Wt)
        W[sel] = w
    return W


def bind(obj, arm, W, bones=None):
    bones = bones or SK.BONES
    obj.vertex_groups.clear()
    for j, b in enumerate(bones):
        col = W[:, j]
        nz = np.nonzero(col > 0)[0]
        vg = obj.vertex_groups.new(name=b)
        if len(nz) == 0:
            continue
        vals = np.round(col[nz], 3)
        for val in np.unique(vals):
            vg.add(nz[vals == val].tolist(), float(val), "REPLACE")
    for m in list(obj.modifiers):
        if m.type == "ARMATURE":
            obj.modifiers.remove(m)
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    obj.parent = arm
    obj.matrix_parent_inverse = arm.matrix_world.inverted()


def read_weights(obj, bones=None):
    bones = bones or SK.BONES
    nv = len(obj.data.vertices)
    W = np.zeros((nv, len(bones)))
    gi = {vg.index: bones.index(vg.name) for vg in obj.vertex_groups if vg.name in bones}
    for v in obj.data.vertices:
        for g in v.groups:
            if g.group in gi:
                W[v.index, gi[g.group]] = g.weight
    return W


def fold_bones(W, keep, bones=None):
    """Move weights of bones not in `keep` to their nearest kept ancestor (animation LOD)."""
    bones = bones or SK.BONES
    W = W.copy()
    for j, b in enumerate(bones):
        if b in keep:
            continue
        a = SK.PARENT[b]
        while a is not None and a not in keep:
            a = SK.PARENT[a]
        if a is None:
            continue
        W[:, bones.index(a)] += W[:, j]
        W[:, j] = 0
    return limit(W)


# --------------------------------------------------------------------------- re-rest

def rerest_canonical(arm, meshes, B):
    """Pose limb bones onto canonical directions, bake mesh deformation, apply pose as rest."""
    core.select_only([arm])
    bpy.ops.object.mode_set(mode="POSE")
    order = []
    for S_, s in SK.SIDES:
        order += [f"{S_}UpperArm", f"{S_}LowerArm", f"{S_}Hand", f"{S_}UpperLeg", f"{S_}LowerLeg"]
    for name in order:
        part = name.replace("Left", "").replace("Right", "")
        s = 1.0 if name.startswith("Left") else -1.0
        want = SK.CANON[part].copy()
        want[0] *= s
        bpy.context.view_layer.update()
        pb = arm.pose.bones[name]
        M = arm.matrix_world @ pb.matrix
        head = Vector(M.translation)
        cur = (arm.matrix_world @ pb.tail) - head
        q = cur.normalized().rotation_difference(Vector(want).normalized())
        R = Matrix.Translation(head) @ q.to_matrix().to_4x4() @ Matrix.Translation(-head)
        pb.matrix = arm.matrix_world.inverted() @ (R @ M)
    bpy.context.view_layer.update()
    bpy.ops.object.mode_set(mode="OBJECT")
    for m in meshes:
        core.select_only([m])
        for mod in m.modifiers:
            if mod.type == "ARMATURE":
                bpy.ops.object.modifier_apply(modifier=mod.name)
                break
    core.select_only([arm])
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.select_all(action="SELECT")
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    for m in meshes:
        mod = m.modifiers.new("Armature", "ARMATURE")
        mod.object = arm


# --------------------------------------------------------------------------- LODs

def make_lod(lod0, name, ratio_body, ratio_other, keep_bones, piece_names):
    """Decimate a copy of LOD0 piece-by-piece (thin shells keep their thickness)."""
    src = lod0.copy()
    src.data = lod0.data.copy()
    core.link(src)
    for m in list(src.modifiers):
        src.modifiers.remove(m)
    fpiece = PL.get_face_attr(src, "piece")
    objs = []
    for pi, nm in enumerate(piece_names):
        if not (fpiece == pi).any():
            continue
        o = src.copy()
        o.data = src.data.copy()
        core.link(o)
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.faces.ensure_lookup_table()
        dead = [f for f, p in zip(bm.faces, fpiece) if p != pi]
        bmesh.ops.delete(bm, geom=dead, context="FACES")
        bm.to_mesh(o.data)
        bm.free()
        r = ratio_body if nm == "body" else ratio_other
        if r < 0.999 and len(o.data.polygons) > 24:
            mod = o.modifiers.new("dec", "DECIMATE")
            mod.decimate_type = "COLLAPSE"
            mod.ratio = r
            mod.use_collapse_triangulate = True
            core.select_only([o])
            bpy.ops.object.modifier_apply(modifier="dec")
        objs.append(o)
    bpy.data.objects.remove(src, do_unlink=True)
    lod = core.join(objs, name)
    W = read_weights(lod)
    W = fold_bones(W, keep_bones)
    return lod, W
