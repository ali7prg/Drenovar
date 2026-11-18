"""Deterministic FK/IK pose solver on the Ancient Maw armature (no constraints needed).

Pose state: per-bone local quaternion q[b] (rest-relative, Blender pose-bone convention) and local
translation t[b].  Helpers rotate bones about armature-space axes, aim bones, solve 2-bone leg IK with
a knee pole, keep toes flat on the ground and return frames for action writing.
"""
import math

from mathutils import Matrix, Quaternion, Vector

import maw_body as B


def qaxis(axis, deg):
    return Quaternion(Vector(axis).normalized(), math.radians(deg))


class Poser:
    def __init__(self, arm):
        self.arm = arm
        bones = arm.data.bones
        self.order = [b.name for b in bones]
        self.rest = {b.name: b.matrix_local.copy() for b in bones}
        self.rest3 = {n: m.to_3x3() for n, m in self.rest.items()}
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in bones}
        self.length = {b.name: b.length for b in bones}
        self.rel = {}
        for n in self.order:
            p = self.parent[n]
            self.rel[n] = self.rest[n] if p is None else self.rest[p].inverted() @ self.rest[n]
        self.reset()

    def reset(self):
        self.q = {n: Quaternion() for n in self.order}
        self.t = {n: Vector((0, 0, 0)) for n in self.order}
        self._P = None

    # ------------------------------------------------------------------ matrices
    def matrices(self):
        P = {}
        for n in self.order:
            p = self.parent[n]
            basis = Matrix.Translation(self.t[n]) @ self.q[n].to_matrix().to_4x4()
            P[n] = (self.rel[n] if p is None else P[p] @ self.rel[n]) @ basis
        self._P = P
        return P

    def unrotated(self, n, P):
        p = self.parent[n]
        base = self.rel[n] if p is None else P[p] @ self.rel[n]
        return base @ Matrix.Translation(self.t[n])

    def head(self, n, P=None):
        P = P or self.matrices()
        return P[n].translation.copy()

    def tail(self, n, P=None):
        P = P or self.matrices()
        return P[n] @ Vector((0, self.length[n], 0))

    # ------------------------------------------------------------------ rotation helpers
    def rot(self, n, axis, deg, compose=True):
        """Rotate bone n about an armature-space (rest) axis, in the bone's own local frame."""
        M = self.rest3[n]
        ql = (M.inverted() @ qaxis(axis, deg).to_matrix() @ M).to_quaternion()
        self.q[n] = self.q[n] @ ql if compose else ql

    def rot_world(self, n, q_world, P):
        """Apply an armature-space rotation to bone n given the current parent pose."""
        U = self.unrotated(n, P).to_3x3()
        cur = U @ self.q[n].to_matrix()
        new = q_world.to_matrix() @ cur
        self.q[n] = (U.inverted() @ new).to_quaternion()

    def aim(self, n, target_dir, P, keep_twist=True):
        """Point bone n's Y axis along target_dir (armature space)."""
        U = self.unrotated(n, P).to_3x3()
        cur = U @ self.q[n].to_matrix() if keep_twist else U
        y = cur.col[1].normalized()
        d = Vector(target_dir).normalized()
        r = y.rotation_difference(d).to_matrix()
        self.q[n] = (U.inverted() @ r @ cur).to_quaternion()

    # ------------------------------------------------------------------ IK
    def leg_ik(self, side, ankle, ball, pole_dir=(0.15, -1.0, 0.0), toes_flat=True, toe_curl=0.0, heading=0.0):
        """Place the ankle at `ankle` and the metatarsus end at `ball` (armature space)."""
        th, sh, ft = f"thigh_{side}", f"shin_{side}", f"foot_{side}"
        P = self.matrices()
        H = self.head(th, P)
        A = Vector(ankle)
        L1, L2 = self.length[th], self.length[sh]
        d = A - H
        dist = max(min(d.length, L1 + L2 - 1e-3), abs(L1 - L2) + 1e-3)
        dn = d.normalized()
        pole = Vector(pole_dir)
        if side == "R":
            pole.x = -pole.x
        if heading:
            pole = Quaternion(Vector((0, 0, 1)), math.radians(heading)) @ pole
        pole = (pole - dn * pole.dot(dn)).normalized()
        a = (L1 * L1 + dist * dist - L2 * L2) / (2 * dist)
        h = math.sqrt(max(L1 * L1 - a * a, 0.0))
        K = H + dn * a + pole * h
        self.aim(th, K - H, P, keep_twist=False)
        P = self.matrices()
        self.aim(sh, (H + dn * dist) - K, P, keep_twist=False)
        P = self.matrices()
        self.aim(ft, Vector(ball) - self.head(ft, P), P, keep_twist=False)
        P = self.matrices()
        if toes_flat:
            self.toes_flat(side, P, curl=toe_curl, heading=heading)
        return K

    def toes_flat(self, side, P=None, curl=0.0, heading=0.0):
        """Toes keep their rest world direction (flat on the ground); curl (deg) bends them down."""
        P = P or self.matrices()
        for t in ("toe2", "toe3", "toe4"):
            for seg in ("a", "b"):
                n = f"{t}{seg}_{side}"
                rest_dir = (self.rest3[n] @ Vector((0, 1, 0))).normalized()
                if heading:
                    rest_dir = Quaternion(Vector((0, 0, 1)), math.radians(heading)) @ rest_dir
                if curl:
                    axis = rest_dir.cross(Vector((0, 0, 1))).normalized()
                    rest_dir = Quaternion(axis, math.radians(-curl * (1.0 if seg == "a" else 1.6))) @ rest_dir
                self.aim(n, rest_dir, P, keep_twist=False)
                P = self.matrices()
        return P

    def arm_reach(self, side, hand_target, pole_dir=(0.6, 0.3, -0.2)):
        ua, fa = f"upperarm_{side}", f"forearm_{side}"
        P = self.matrices()
        S = self.head(ua, P)
        T = Vector(hand_target)
        L1, L2 = self.length[ua], self.length[fa]
        d = T - S
        dist = max(min(d.length, L1 + L2 - 1e-3), abs(L1 - L2) + 1e-3)
        dn = d.normalized()
        pole = Vector(pole_dir)
        if side == "R":
            pole.x = -pole.x
        pole = (pole - dn * pole.dot(dn)).normalized()
        a = (L1 * L1 + dist * dist - L2 * L2) / (2 * dist)
        h = math.sqrt(max(L1 * L1 - a * a, 0.0))
        E = S + dn * a + pole * h
        self.aim(ua, E - S, P, keep_twist=False)
        P = self.matrices()
        self.aim(fa, (S + dn * dist) - E, P, keep_twist=False)

    # ------------------------------------------------------------------ output
    def frame(self):
        out = {}
        for n in self.order:
            out[n] = (self.t[n].copy(), self.q[n].copy())
        return out

    def apply(self, arm=None):
        arm = arm or self.arm
        for n in self.order:
            pb = arm.pose.bones[n]
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = self.q[n]
            pb.location = self.t[n]


def rest_ankle_ball(side):
    m = 1 if side == "L" else -1
    a = B.ANKLE.copy()
    b = B.BALL.copy()
    a[0] *= m
    b[0] *= m
    return Vector(a), Vector(b)
