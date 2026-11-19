"""Pose solver for the shared human rig: FK in rest-world axes carried by the parent, analytic
2-bone IK for legs (ankle target + foot orientation + knee pole) and optionally arms, finger curl,
props.  Produces Blender local bases (loc, quat) per bone and the posed world matrices (for the
foot-slip measurement).

Axes (Blender world, character faces -Y, +X = character's left):
  pitch +  = rotation about +X  (spine/head lean forward, foot toe-down)
  roll  +  = rotation about +Y  (lean toward the character's left)
  yaw   +  = rotation about +Z  (turn toward the character's left)
"""
import math

import numpy as np

FPS = 30.0
X = np.array([1.0, 0, 0])
Y = np.array([0, 1.0, 0])
Z = np.array([0, 0, 1.0])


def rot(axis, ang):
    axis = np.asarray(axis, float)
    n = np.linalg.norm(axis)
    if n < 1e-12 or abs(ang) < 1e-12:
        return np.eye(3)
    x, y, z = axis / n
    c, s = math.cos(ang), math.sin(ang)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


def ypr(yaw=0.0, pitch=0.0, roll=0.0):
    return rot(Z, yaw) @ rot(X, pitch) @ rot(Y, roll)


def matq(m):
    m = np.asarray(m, float)
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        q = [0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        q = [(m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s]
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        q = [(m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s]
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        q = [(m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s]
    q = np.array(q)
    q /= np.linalg.norm(q)
    return q if q[0] >= 0 else -q


def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def smoother(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * x * (x * (6 * x - 15) + 10)


DEG = math.pi / 180.0
OVERREACH = [0.0]


class Skel:
    def __init__(self, arm_obj):
        self.R, self.parent, self.length = {}, {}, {}
        for b in arm_obj.data.bones:
            self.R[b.name] = np.array(b.matrix_local)
            self.parent[b.name] = b.parent.name if b.parent else None
            self.length[b.name] = b.length
        self.order = []
        seen = set()

        def visit(n):
            if n in seen:
                return
            p = self.parent.get(n)
            if p:
                visit(p)
            seen.add(n)
            self.order.append(n)
        for n in self.R:
            visit(n)
        self.order = [n for n in self.order if not n.startswith(("IK_", "Pole_"))]

    def head(self, n):
        return self.R[n][:3, 3].copy()

    def tail(self, n):
        return self.R[n][:3, 3] + self.R[n][:3, 1] * self.length[n]


def circle_ik(a, c, la, lb, bend):
    ac = c - a
    D = np.linalg.norm(ac)
    OVERREACH[0] = max(OVERREACH[0], D - (la + lb) + 0.002)
    D = min(max(D, abs(la - lb) + 1e-4), la + lb - 0.002)
    u = ac / max(np.linalg.norm(ac), 1e-9)
    x = (la * la - lb * lb + D * D) / (2 * D)
    h = math.sqrt(max(la * la - x * x, 0.0))
    w = bend - (bend @ u) * u
    w /= max(np.linalg.norm(w), 1e-9)
    return a + u * x + w * h, a + u * D


def frame_from(y, zref):
    y = y / np.linalg.norm(y)
    z = zref - (zref @ y) * y
    z /= max(np.linalg.norm(z), 1e-9)
    x = np.cross(y, z)
    return np.stack([x, y, z], 1)


class Pose:
    def __init__(self):
        self.hip_off = np.zeros(3)
        self.hip_rot = np.eye(3)
        self.rot = {}          # bone -> 3x3 rest-world-axes delta (carried by the parent)
        self.leg = {}          # 'Left'/'Right' -> dict(ankle, foot_rot, knee, toe)
        self.arm = {}          # 'Left'/'Right' -> dict(wrist, hand_rot (world delta), elbow)
        self.scale = {}        # bone -> uniform scale
        self.world = {}        # bone -> callable(M) -> 4x4 world matrix override

    def r(self, bone, R):
        self.rot[bone] = R @ self.rot.get(bone, np.eye(3))


def solve(sk, pose):
    """-> (basis {bone: (loc, quat, scale)}, M {bone: 4x4 posed armature-space})."""
    M = {}
    basis = {}
    for n in sk.order:
        Rn = sk.R[n]
        p = sk.parent.get(n)
        if p is None:
            U = Rn.copy()
            Prot = np.eye(3)
        else:
            U = M[p] @ np.linalg.inv(sk.R[p]) @ Rn
            Prot = M[p][:3, :3] @ sk.R[p][:3, :3].T
        Mn = U.copy()
        side = "Left" if n.startswith("Left") else ("Right" if n.startswith("Right") else None)
        short = n[len(side):] if side else n
        if n == "Hips":
            Mn[:3, :3] = pose.hip_rot @ Rn[:3, :3]
            Mn[:3, 3] = Rn[:3, 3] + pose.hip_off
        elif side and short in ("UpperLeg", "LowerLeg") and side in pose.leg:
            L = pose.leg[side]
            hipj = U[:3, 3] if short == "UpperLeg" else None
            if short == "UpperLeg":
                la = sk.length[f"{side}UpperLeg"]
                lb = sk.length[f"{side}LowerLeg"]
                knee, ank = circle_ik(hipj, L["ankle"], la, lb, L["knee"])
                L["_knee"], L["_ank"] = knee, ank
                Mn[:3, :3] = frame_from(knee - hipj, L["knee"])
            else:
                knee, ank = L["_knee"], L["_ank"]
                Mn[:3, :3] = frame_from(ank - knee, L["knee"])
                Mn[:3, 3] = knee
        elif side and short == "Foot" and side in pose.leg:
            L = pose.leg[side]
            Mn[:3, :3] = L["foot_rot"] @ Rn[:3, :3]
            Mn[:3, 3] = L["_ank"]
        elif side and short in ("UpperArm", "LowerArm") and side in pose.arm and pose.arm[side].get("wrist") is not None:
            A = pose.arm[side]
            if short == "UpperArm":
                sh = U[:3, 3]
                la = sk.length[f"{side}UpperArm"]
                lb = sk.length[f"{side}LowerArm"]
                el, wr = circle_ik(sh, A["wrist"], la, lb, A["elbow"])
                A["_el"], A["_wr"] = el, wr
                zref = Prot @ sk.R[n][:3, 2]
                Mn[:3, :3] = frame_from(el - sh, zref)
            else:
                zref = M[p][:3, 2]
                Mn[:3, :3] = frame_from(A["_wr"] - A["_el"], zref)
                Mn[:3, 3] = A["_el"]
        elif side and short == "Hand" and side in pose.arm and pose.arm[side].get("hand_rot") is not None:
            Mn[:3, :3] = pose.arm[side]["hand_rot"] @ Prot @ Rn[:3, :3] if pose.arm[side].get("hand_local", False) \
                else pose.arm[side]["hand_rot"] @ Rn[:3, :3]
        else:
            Q = pose.rot.get(n)
            if Q is not None:
                Mn[:3, :3] = Prot @ Q @ Rn[:3, :3]
        if n in pose.world:
            Mn = pose.world[n](M, Mn)
        sc = pose.scale.get(n, 1.0)
        B = np.linalg.inv(U) @ Mn
        Bq = matq(B[:3, :3])
        basis[n] = (B[:3, 3].copy(), Bq, sc)
        M[n] = Mn.copy()
        if sc != 1.0:
            M[n][:3, :3] = M[n][:3, :3] * sc
    return basis, M
