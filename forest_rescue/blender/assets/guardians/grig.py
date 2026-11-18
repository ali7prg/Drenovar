"""Quadruped skeleton maths for the guardians (pure numpy; bpy only in `build_armature`).

Bone matrices follow Blender: bone Y axis = head->tail, Z axis from an "align roll" vector,
X = Y x Z.  Armature space == Blender world (armature object at the origin, unscaled).
Pose representation: dict bone -> 4x4 armature-space matrix of the posed bone.
basis_b = (M_p^-1 M_b)^-1 pose_p^-1 pose_b  (root: M_b^-1 pose_b)   -> written as keyframes.
"""
import math

import numpy as np


def _n(v):
    v = np.asarray(v, float)
    return v / max(np.linalg.norm(v), 1e-12)


def rest_matrix(head, tail, zvec):
    y = _n(np.asarray(tail, float) - np.asarray(head, float))
    z = np.asarray(zvec, float) - np.dot(zvec, y) * y
    if np.linalg.norm(z) < 1e-6:
        z = np.array([0.0, 0.0, 1.0]) - y[2] * y
        if np.linalg.norm(z) < 1e-6:
            z = np.array([0.0, -1.0, 0.0])
    z = _n(z)
    x = np.cross(y, z)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = x, y, z, head
    return M


def rot_axis(axis, ang):
    """3x3 rotation about axis (radians)."""
    a = _n(axis)
    c, s = math.cos(ang), math.sin(ang)
    x, y, z = a
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


def rot_between(a, b):
    """Shortest-arc 3x3 rotation taking unit vector a to unit vector b."""
    a, b = _n(a), _n(b)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if c < -0.999999:
        perp = _n(np.cross(a, [1, 0, 0]) if abs(a[0]) < 0.9 else np.cross(a, [0, 1, 0]))
        return rot_axis(perp, math.pi)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx * (1.0 / (1.0 + c))


def euler_xyz(rx=0.0, ry=0.0, rz=0.0):
    """3x3 from XYZ euler degrees (applied X then Y then Z, like Blender 'XYZ')."""
    return rot_axis([0, 0, 1], math.radians(rz)) @ rot_axis([0, 1, 0], math.radians(ry)) @ \
        rot_axis([1, 0, 0], math.radians(rx))


def mat_to_quat(R):
    """3x3 -> (w,x,y,z)."""
    m = R
    t = m[0, 0] + m[1, 1] + m[2, 2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        w = 0.25 * s
        x = (m[2, 1] - m[1, 2]) / s
        y = (m[0, 2] - m[2, 0]) / s
        z = (m[1, 0] - m[0, 1]) / s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        w = (m[2, 1] - m[1, 2]) / s
        x = 0.25 * s
        y = (m[0, 1] + m[1, 0]) / s
        z = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        w = (m[0, 2] - m[2, 0]) / s
        x = (m[0, 1] + m[1, 0]) / s
        y = 0.25 * s
        z = (m[1, 2] + m[2, 1]) / s
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        w = (m[1, 0] - m[0, 1]) / s
        x = (m[0, 2] + m[2, 0]) / s
        y = (m[1, 2] + m[2, 1]) / s
        z = 0.25 * s
    q = np.array([w, x, y, z])
    return q / np.linalg.norm(q)


def quat_to_mat(q):
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def slerp(q0, q1, t):
    q0 = np.asarray(q0, float)
    q1 = np.asarray(q1, float)
    d = float(np.dot(q0, q1))
    if d < 0:
        q1 = -q1
        d = -d
    if d > 0.9995:
        q = q0 + t * (q1 - q0)
        return q / np.linalg.norm(q)
    th = math.acos(min(1.0, d))
    s = math.sin(th)
    return (math.sin((1 - t) * th) * q0 + math.sin(t * th) * q1) / s


class Skeleton:
    """bones: list of dict(name, head, tail, parent, z=(0,0,1), deform=True)."""

    def __init__(self, bones):
        self.bones = bones
        self.names = [b["name"] for b in bones]
        self.idx = {n: i for i, n in enumerate(self.names)}
        self.parent = {b["name"]: b.get("parent") for b in bones}
        self.children = {n: [] for n in self.names}
        for b in bones:
            if b.get("parent"):
                self.children[b["parent"]].append(b["name"])
        self.rest = {b["name"]: rest_matrix(b["head"], b["tail"], b.get("z", (0, 0, 1))) for b in bones}
        self.length = {b["name"]: float(np.linalg.norm(np.subtract(b["tail"], b["head"]))) for b in bones}
        self.deform = [b["name"] for b in bones if b.get("deform", True)]
        # topological order
        order = []
        todo = [n for n in self.names if not self.parent[n]]
        while todo:
            n = todo.pop(0)
            order.append(n)
            todo.extend(self.children[n])
        self.order = order

    def set_rest_from_blender(self, arm_obj):
        for b in arm_obj.data.bones:
            if b.name in self.rest:
                self.rest[b.name] = np.array(b.matrix_local)
                self.length[b.name] = b.length

    def head(self, n):
        return self.rest[n][:3, 3].copy()

    def tail(self, n):
        return self.rest[n][:3, 3] + self.rest[n][:3, 1] * self.length[n]

    # -------------------------------------------------- FK
    def fk(self, local_rot=None, local_loc=None, base=None):
        """Pose from local basis rotations (3x3) / translations; returns dict of 4x4."""
        local_rot = local_rot or {}
        local_loc = local_loc or {}
        pose = {}
        for n in self.order:
            B = np.eye(4)
            if n in local_rot:
                B[:3, :3] = local_rot[n]
            if n in local_loc:
                B[:3, 3] = local_loc[n]
            p = self.parent[n]
            if p is None:
                pose[n] = self.rest[n] @ B if base is None else base @ self.rest[n] @ B
            else:
                pose[n] = pose[p] @ np.linalg.inv(self.rest[p]) @ self.rest[n] @ B
        return pose

    def fk_from(self, pose, start, local_rot=None):
        """Recompute descendants of `start` (inclusive) in-place after changing local rotations."""
        local_rot = local_rot or {}
        stack = [start]
        while stack:
            n = stack.pop()
            p = self.parent[n]
            B = np.eye(4)
            if n in local_rot:
                B[:3, :3] = local_rot[n]
            pose[n] = pose[p] @ np.linalg.inv(self.rest[p]) @ self.rest[n] @ B
            stack.extend(self.children[n])
        return pose

    def basis(self, pose):
        """Local basis matrices (loc, quat wxyz) for every bone of a full pose."""
        out = {}
        for n in self.names:
            p = self.parent[n]
            if p is None:
                B = np.linalg.inv(self.rest[n]) @ pose[n]
            else:
                B = np.linalg.inv(np.linalg.inv(self.rest[p]) @ self.rest[n]) @ np.linalg.inv(pose[p]) @ pose[n]
            out[n] = (B[:3, 3].copy(), mat_to_quat(B[:3, :3]))
        return out

    def aimed(self, pose, n, head, target, twist_ref=None):
        """Posed matrix of bone n with head at `head` aiming at `target`.

        Orientation = parent rotation delta applied to rest, then shortest arc to the aim
        direction (keeps roll consistent with the parent)."""
        p = self.parent[n]
        R = self.rest[n][:3, :3]
        if p is not None:
            Rd = pose[p][:3, :3] @ self.rest[p][:3, :3].T
            R = Rd @ R
        y = R[:, 1]
        R = rot_between(y, _n(np.asarray(target) - np.asarray(head))) @ R
        M = np.eye(4)
        M[:3, :3] = R
        M[:3, 3] = head
        return M

    def child_head(self, pose, n):
        """Where the head of bone n sits given its parent's pose (rest offset carried)."""
        p = self.parent[n]
        return (pose[p] @ np.linalg.inv(self.rest[p]) @ self.rest[n])[:3, 3]

    def joint(self, pose, n, end="head"):
        M = pose[n]
        return M[:3, 3] + (M[:3, 1] * self.length[n] if end == "tail" else 0.0)


def two_bone_ik(A, C, L1, L2, pole):
    """Middle joint B for a 2-bone chain from A to C with lengths L1, L2 bending toward pole."""
    A = np.asarray(A, float)
    C = np.asarray(C, float)
    d = C - A
    D = np.linalg.norm(d)
    D = min(max(D, abs(L1 - L2) + 1e-4), L1 + L2 - 1e-4)
    u = _n(d)
    pv = np.asarray(pole, float) - np.dot(pole, u) * u
    if np.linalg.norm(pv) < 1e-8:
        pv = np.array([0.0, 1.0, 0.0]) - u[1] * u
    pv = _n(pv)
    a = (L1 * L1 - L2 * L2 + D * D) / (2 * D)
    h = math.sqrt(max(L1 * L1 - a * a, 0.0))
    return A + u * a + pv * h, A + u * D


def solve_leg(sk, pose, chain, target, end_dir, toe_dir, pole, root_rot=None):
    """Analytic leg solve.

    chain = [girdle_or_None, upper, lower, metapodial, digits]; the upper bone's head is fixed by
    its parent (after an optional girdle rotation `root_rot` given as 3x3 local basis).
    target = metapodial->digit joint (paw ball) world position; end_dir = unit vector from the
    wrist/hock to the paw ball; toe_dir = unit digit direction; pole = bend direction of the
    middle joint (elbow: backward, knee: forward).
    Returns the pose (modified in place).
    """
    girdle, upper, lower, meta, digits = chain
    if girdle is not None:
        lr = {girdle: root_rot if root_rot is not None else np.eye(3)}
        p = sk.parent[girdle]
        B = np.eye(4)
        B[:3, :3] = lr[girdle]
        pose[girdle] = pose[p] @ np.linalg.inv(sk.rest[p]) @ sk.rest[girdle] @ B
    S = sk.child_head(pose, upper)
    W = np.asarray(target, float) - _n(end_dir) * sk.length[meta]
    E, Wc = two_bone_ik(S, W, sk.length[upper], sk.length[lower], pole)
    pose[upper] = sk.aimed(pose, upper, S, E)
    pose[lower] = sk.aimed(pose, lower, E, Wc)
    T = Wc + _n(np.asarray(target) - Wc) * sk.length[meta]
    pose[meta] = sk.aimed(pose, meta, Wc, T)
    pose[digits] = sk.aimed(pose, digits, T, T + _n(toe_dir) * sk.length[digits])
    return pose


def build_armature(name, sk, col=None):
    """Create the Blender armature (bpy) from a Skeleton; rolls from the bones' z vectors."""
    import bpy
    from mathutils import Vector
    from frlib import core
    arm = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, arm)
    core.link(obj, col)
    arm.display_type = "OCTAHEDRAL"
    core.select_only([obj])
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = {}
    for b in sk.bones:
        eb = arm.edit_bones.new(b["name"])
        eb.head = Vector(b["head"])
        eb.tail = Vector(b["tail"])
        eb.align_roll(Vector(b.get("z", (0, 0, 1))))
        eb.use_deform = b.get("deform", True)
        ebs[b["name"]] = eb
    for b in sk.bones:
        if b.get("parent"):
            ebs[b["name"]].parent = ebs[b["parent"]]
            ebs[b["name"]].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in obj.pose.bones:
        pb.rotation_mode = "QUATERNION"
    sk.set_rest_from_blender(obj)
    return obj
