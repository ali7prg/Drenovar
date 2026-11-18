"""Armature + skin weights for the Ancient Maw (deterministic, part-based).

Weights: every SDF part owns a bone; the trunk loft is distributed along the
head-neck-spine-pelvis-tail chain by its Y coordinate; the head loft is split by the lip plane
(upper -> head, lower -> jaw, hinge blend); limbs by part ownership; then Laplacian smoothing over the
mesh and a 4-influence limit.  LOD1/LOD2 merge small bones into parents (bone budget 50/28 used).
"""
import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from frlib import core, rig, sdf
import maw_body as B

# bones merged into a parent for the lower LODs (child -> parent)
LOD1_MERGE = {
    "tongue_02": "tongue_01", "tongue_03": "tongue_01",
    "finger1b_L": "finger1a_L", "finger2b_L": "finger2a_L", "finger3_L": "hand_L",
    "finger1b_R": "finger1a_R", "finger2b_R": "finger2a_R", "finger3_R": "hand_R",
    "toe2b_L": "toe2a_L", "toe3b_L": "toe3a_L", "toe4b_L": "toe4a_L",
    "toe2b_R": "toe2a_R", "toe3b_R": "toe3a_R", "toe4b_R": "toe4a_R",
}
LOD2_MERGE = dict(LOD1_MERGE)
LOD2_MERGE.update({
    "tongue_01": "jaw",
    "finger1a_L": "hand_L", "finger2a_L": "hand_L", "finger1a_R": "hand_R", "finger2a_R": "hand_R",
    "toe2a_L": "foot_L", "toe3a_L": "foot_L", "toe4a_L": "foot_L", "dewclaw_L": "foot_L",
    "toe2a_R": "foot_R", "toe3a_R": "foot_R", "toe4a_R": "foot_R", "dewclaw_R": "foot_R",
    "neck_03": "neck_02",
    "tail_02": "tail_01", "tail_04": "tail_03", "tail_06": "tail_05", "tail_08": "tail_07", "tail_10": "tail_09",
})


def resolve(name, merge):
    while name in merge:
        name = merge[name]
    return name


def build_armature(name):
    bones = B.bone_table()
    arm = rig.armature(name, bones)
    core.select_only([arm])
    bpy.ops.object.mode_set(mode="EDIT")
    for eb in arm.data.edit_bones:
        d = (eb.tail - eb.head).normalized()
        if abs(d.z) > 0.85:          # near-vertical bones (metatarsus): Z axis forward
            eb.align_roll(Vector((0, -1, 0)))
        else:
            eb.align_roll(Vector((0, 0, 1)))
    bpy.ops.object.mode_set(mode="OBJECT")
    arm.data.display_type = "OCTAHEDRAL"
    arm.show_in_front = True
    return arm, [b["name"] for b in bones]


# ---------------------------------------------------------------------------------- weights
CHAIN = ["head", "neck_03", "neck_02", "neck_01", "spine_03", "spine_02", "spine_01", "pelvis",
         "tail_01", "tail_02", "tail_03", "tail_04", "tail_05", "tail_06", "tail_07", "tail_08", "tail_09",
         "tail_10"]


def chain_joints():
    """Y positions of the joints between consecutive chain bones (front to back)."""
    sp = B.spine_points()
    tc = B.tail_centreline(11)
    ys = [sp["head"][0][1], sp["neck_03"][0][1], sp["neck_02"][0][1], sp["neck_01"][0][1],
          sp["spine_03"][0][1], sp["spine_02"][0][1], sp["spine_01"][0][1], 0.20]
    ys += [tc[i + 1][1] for i in range(9)]
    return np.array(ys)  # len = len(CHAIN) - 1


def chain_weights(Y, blend=0.16):
    """(N, len(CHAIN)) weights along the trunk chain by Y with linear blends around joints."""
    J = chain_joints()
    N = len(Y)
    W = np.zeros((N, len(CHAIN)))
    # bone i spans (J[i-1], J[i]) in Y (front is more negative)
    idx = np.searchsorted(J, Y)  # 0 .. len(J)
    W[np.arange(N), idx] = 1.0
    for j, yj in enumerate(J):
        bw = blend * (0.6 if j >= 8 else 1.0)
        t = np.clip((Y - (yj - bw)) / (2 * bw), 0, 1)
        near = np.abs(Y - yj) < bw
        a, b = j, j + 1      # a in front of the joint, b behind
        W[near, :] = 0
        W[near, a] = 1 - t[near]
        W[near, b] = t[near]
    return W


def head_split(V):
    """Head/jaw weights for points of the head region by the lip plane, hinge blend."""
    y, z = V[:, 1], V[:, 2]
    zm = B.mouth_z(np.clip(y, -4.6, -3.0))
    hinge = B.JAW_HINGE
    corner = B.MOUTH_CORNER_Y
    below = z < zm
    w_jaw = below.astype(float)
    # behind the mouth corner: blend by height around the hinge-to-corner line
    behind = y > corner - 0.02
    zline = np.interp(y, [corner - 0.02, hinge[1] + 0.05], [zm.min() if np.ndim(zm) else zm, hinge[2]])
    zline = np.where(behind, np.interp(y, [corner, hinge[1]], [float(B.mouth_z(corner)), hinge[2]]), zm)
    band = np.where(behind, 0.10, 0.012)
    w_jaw = np.clip((zline - z) / (2 * band) + 0.5, 0, 1)
    return w_jaw


def compute_weights(verts, faces, bone_names, merge=None, smooth_iters=8):
    merge = merge or {}
    idx = {b: i for i, b in enumerate(bone_names)}
    N = len(verts)
    W = np.zeros((N, len(bone_names)))
    add, _sub = B.build_parts(detail=False)
    falloff = 0.05
    trunk_w = np.zeros(N)
    head_w = np.zeros(N)
    for p in add:
        if p.bone is None:
            continue
        d = p.fn(verts)
        w = np.exp(-np.maximum(d, 0.0) / falloff)
        if p.name == "trunk":
            trunk_w = np.maximum(trunk_w, w)
            continue
        if p.name == "head":
            head_w = np.maximum(head_w, w)
            continue
        b = resolve(p.bone, merge)
        if b in idx:
            W[:, idx[b]] = np.maximum(W[:, idx[b]], w)
    # trunk along the chain
    CW = chain_weights(verts[:, 1])
    for j, cb in enumerate(CHAIN):
        b = resolve(cb, merge)
        W[:, idx[b]] = np.maximum(W[:, idx[b]], trunk_w * CW[:, j])
    # head loft: upper/lower split
    wj = head_split(verts)
    hb, jb = idx[resolve("head", merge)], idx[resolve("jaw", merge)]
    W[:, hb] = np.maximum(W[:, hb], head_w * (1 - wj))
    W[:, jb] = np.maximum(W[:, jb], head_w * wj)
    # throat under the jaw follows the jaw toward the chin
    throat = (verts[:, 1] < -3.15) & (verts[:, 2] < B.mouth_z(np.clip(verts[:, 1], -4.6, -3.0)) - 0.05)
    tj = np.clip((-3.15 - verts[:, 1]) / 0.35, 0, 1) * throat
    W[:, jb] = np.maximum(W[:, jb], tj * trunk_w)
    # side constraint: left bones never on the right side and vice versa
    for b, i in idx.items():
        if b.endswith("_L"):
            W[verts[:, 0] < -0.05, i] = 0
        elif b.endswith("_R"):
            W[verts[:, 0] > 0.05, i] = 0
    # inside the mouth: the palate (above the lip line) is head only, the floor jaw only
    head_region = (verts[:, 1] < B.MOUTH_CORNER_Y) & (np.abs(verts[:, 0]) < 0.3)
    zm = B.mouth_z(np.clip(verts[:, 1], -4.6, -3.0))
    pal = head_region & (verts[:, 2] > zm)
    flo = head_region & (verts[:, 2] < zm)
    keep = np.zeros(len(bone_names), bool)
    keep[hb] = True
    W[pal] = W[pal] * keep
    W[pal, hb] = np.maximum(W[pal, hb], 1.0)
    keepj = np.zeros(len(bone_names), bool)
    keepj[jb] = True
    W[flo] = W[flo] * keepj
    W[flo, jb] = np.maximum(W[flo, jb], 1.0)
    # normalise -> smooth -> limit
    s = W.sum(1, keepdims=True)
    W = np.where(s > 1e-6, W / np.maximum(s, 1e-9), 0)
    from scipy import sparse
    e = np.asarray(faces)  # edges (E,2)
    e = np.concatenate([e, e[:, ::-1]])
    A = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(N, N)).tocsr()
    A.data[:] = 1.0
    deg = np.asarray(A.sum(axis=1)).ravel()
    deg[deg == 0] = 1
    A = sparse.diags(1.0 / deg) @ A
    lock = np.zeros(N, bool)
    lock[pal | flo] = True
    Wl = W[lock].copy()
    for _ in range(smooth_iters):
        W = 0.5 * W + 0.5 * (A @ W)
        W[lock] = Wl
    W = sdf.limit_weights(W, top=4, min_w=0.02)
    return W


def bind_body(obj, arm, bone_names, rigid_table, merge=None):
    """Weights for a joined mesh: body verts (rigid_id<0) part-based, detail verts rigid to their bone."""
    nv = len(obj.data.vertices)
    V = np.empty(nv * 3)
    obj.data.vertices.foreach_get("co", V)
    V = V.reshape(nv, 3)
    ne = len(obj.data.edges)
    faces = np.empty(ne * 2, np.int64)
    obj.data.edges.foreach_get("vertices", faces)
    faces = faces.reshape(ne, 2)
    rid = np.empty(nv, np.int32)
    obj.data.attributes["rigid_id"].data.foreach_get("value", rid)
    W = compute_weights(V, faces, bone_names, merge)
    idx = {b: i for i, b in enumerate(bone_names)}
    merge = merge or {}
    sp = B.spine_points()
    j1, j2 = sp["tongue_02"][0][1], sp["tongue_03"][0][1]
    for i in np.nonzero(rid >= 0)[0]:
        W[i] = 0
        b = rigid_table[rid[i]]
        if b == "tongue":
            y = V[i, 1]
            t1 = np.clip((j1 + 0.05 - y) / 0.1, 0, 1)
            t2 = np.clip((j2 + 0.05 - y) / 0.1, 0, 1)
            w = {"tongue_01": 1 - t1, "tongue_02": t1 * (1 - t2), "tongue_03": t2}
            for k, v in w.items():
                W[i, idx[resolve(k, merge)]] += v
        else:
            W[i, idx[resolve(b, merge)]] = 1.0
    W = sdf.limit_weights(W, top=4, min_w=0.02)
    rig.bind(obj, arm, bone_names, W)
    used = sorted({bone_names[j] for j in np.nonzero(W.max(0) > 0)[0]})
    return W, used


# ---------------------------------------------------------------------------------- posing helpers
def arm_rotation(arm, bone, q_arm):
    """Local quaternion that rotates `bone` by q_arm expressed in armature (rest) space."""
    M = arm.data.bones[bone].matrix_local.to_3x3()
    return (M.inverted() @ q_arm.to_matrix() @ M).to_quaternion()


def axis_q(axis, deg):
    return Quaternion(Vector(axis).normalized(), math.radians(deg))
