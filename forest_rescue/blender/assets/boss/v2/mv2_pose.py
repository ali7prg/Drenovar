"""Numpy FK/IK pose solver for the `new_dinosaur_boss` armature (no per-bone depsgraph updates).

Blender convention: M_b = M_parent @ inv(Rest_parent) @ Rest_b @ Basis_b (armature space).
Pose stores Basis (4x4) per bone; helpers aim bones in world space with minimal twist, solve two-bone
leg/arm IK with a pole, keep toes on the ground, and write Blender pose / keyframes.
"""
import math

import numpy as np


def qmat(axis, deg):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    x, y, z = a
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


def shortest_arc(a, b):
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    v = np.cross(a, b)
    c = float(a @ b)
    if c < -0.999999:
        axis = np.cross(a, [1, 0, 0])
        if np.linalg.norm(axis) < 1e-6:
            axis = np.cross(a, [0, 1, 0])
        return qmat(axis, 180.0)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx * (1.0 / (1.0 + c))


def mat_to_quat(M):
    m = M
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
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


class Skeleton:
    """Rest data read once from a Blender armature object (or a bone table)."""

    def __init__(self, arm_obj):
        self.names = [b.name for b in arm_obj.data.bones]
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in arm_obj.data.bones}
        self.rest = {b.name: np.array(b.matrix_local, float) for b in arm_obj.data.bones}
        self.length = {b.name: b.length for b in arm_obj.data.bones}
        self.order = []
        seen = set()

        def visit(n):
            if n in seen:
                return
            p = self.parent[n]
            if p:
                visit(p)
            seen.add(n)
            self.order.append(n)
        for n in self.names:
            visit(n)
        self.rel = {}
        for n in self.names:
            p = self.parent[n]
            self.rel[n] = self.rest[n] if p is None else np.linalg.inv(self.rest[p]) @ self.rest[n]


class Pose:
    def __init__(self, sk):
        self.sk = sk
        self.basis = {n: np.eye(4) for n in sk.names}
        self.M = {}
        self.dirty = True

    def reset(self):
        for n in self.basis:
            self.basis[n] = np.eye(4)
        self.dirty = True

    def fk(self):
        if not self.dirty:
            return self.M
        M = {}
        for n in self.sk.order:
            p = self.sk.parent[n]
            base = self.sk.rel[n] if p is None else M[p] @ self.sk.rel[n]
            M[n] = base @ self.basis[n]
        self.M = M
        self.dirty = False
        return M

    def base_world(self, n):
        """World matrix of bone n with identity basis (current parent pose)."""
        M = self.fk()
        p = self.sk.parent[n]
        return self.sk.rel[n] if p is None else M[p] @ self.sk.rel[n]

    def head(self, n):
        return self.fk()[n][:3, 3].copy()

    def tail(self, n):
        M = self.fk()[n]
        return M[:3, 3] + M[:3, 1] * self.sk.length[n]

    def ydir(self, n):
        return self.fk()[n][:3, 1].copy()

    # --- local rotations (in the bone's rest frame)
    def rot_local(self, n, axis, deg):
        R = np.eye(4)
        R[:3, :3] = qmat(axis, deg)
        self.basis[n] = self.basis[n] @ R
        self.dirty = True

    def rot_world(self, n, Rw):
        """Apply a world-space rotation Rw (3x3) to bone n about its head."""
        M = self.fk()[n]
        Rl = M[:3, :3].T @ Rw @ M[:3, :3]
        R = np.eye(4)
        R[:3, :3] = Rl
        self.basis[n] = self.basis[n] @ R
        self.dirty = True

    def rot_world_axis(self, n, axis, deg):
        self.rot_world(n, qmat(axis, deg))

    def translate_world(self, n, dv):
        M0 = self.base_world(n)
        dl = M0[:3, :3].T @ np.asarray(dv, float)
        self.basis[n][:3, 3] += dl
        self.dirty = True

    def aim(self, n, target_dir, keep=None):
        """Point bone n's Y axis along target_dir (world) with minimal twist from its current pose."""
        d = np.asarray(target_dir, float)
        d = d / np.linalg.norm(d)
        y = self.ydir(n)
        self.rot_world(n, shortest_arc(y, d))

    def set_world_rot(self, n, Rw_target):
        M0 = self.base_world(n)
        Bm = np.eye(4)
        Bm[:3, :3] = M0[:3, :3].T @ Rw_target
        Bm[:3, 3] = self.basis[n][:3, 3]
        self.basis[n] = Bm
        self.dirty = True

    def world_rot_rest_relative(self, n, Rw):
        """World rotation of bone n's REST orientation rotated by Rw (for 'keep rest world dir')."""
        return Rw @ self.sk.rest[n][:3, :3]

    # --- IK
    def two_bone(self, upper, lower, target, pole_dir, end=None):
        H = self.head(upper)
        L1 = self.sk.length[upper]
        L2 = self.sk.length[lower]
        t = np.asarray(target, float)
        dvec = t - H
        d = np.linalg.norm(dvec)
        d = np.clip(d, abs(L1 - L2) + 1e-3, L1 + L2 - 1e-4)
        e = dvec / max(np.linalg.norm(dvec), 1e-9)
        p = np.asarray(pole_dir, float)
        n_ = p - e * (p @ e)
        if np.linalg.norm(n_) < 1e-6:
            n_ = np.cross(e, [1, 0, 0])
        n_ /= np.linalg.norm(n_)
        ca = (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)
        a = math.acos(np.clip(ca, -1, 1))
        K = H + L1 * (math.cos(a) * e + math.sin(a) * n_)
        self.aim(upper, K - H)
        self.aim(lower, (H + e * d) - self.head(lower))
        return float(np.linalg.norm(t - H)) - (L1 + L2)   # >0: overreach

    def to_blender(self, arm_obj):
        from mathutils import Matrix
        for n, Bm in self.basis.items():
            arm_obj.pose.bones[n].matrix_basis = Matrix(Bm.tolist())

    def local_qt(self, n):
        Bm = self.basis[n]
        return Bm[:3, 3].copy(), mat_to_quat(Bm[:3, :3])
