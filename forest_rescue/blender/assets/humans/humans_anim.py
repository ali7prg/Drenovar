"""Procedural clip authoring on the shared skeleton (numpy FK + analytic two-bone IK).

Bone-local conventions (see humans_skel rolls): +X rotation = flexion toward the bone's local Z
(spine/head/thigh/upper arm: forward; fingers: toward the palm; foot: toes up), knee flexion = -X.
Poses are dicts; `Solver.solve(pose)` returns {bone: (loc, quat)} pose-basis values that are
written as dense keys (30 fps).  Locomotion is in place: stance feet slide backward at exactly
the ground speed (stride = speed * cycle), heel -> flat -> ball -> toe rolling contact.
"""
import math

import numpy as np
from mathutils import Matrix, Quaternion, Vector

import humans_skel as SK

FPS = 30


def rad(d):
    return math.radians(d)


def ss(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def sm(x):
    """smootherstep"""
    x = np.clip(x, 0.0, 1.0)
    return x * x * x * (x * (x * 6 - 15) + 10)


def lerp(a, b, t):
    return a + (b - a) * t


def env(t, keys):
    """Piecewise smooth interpolation through (time, value) keys (value scalars or arrays)."""
    ts = [k[0] for k in keys]
    if t <= ts[0]:
        return np.asarray(keys[0][1], float)
    if t >= ts[-1]:
        return np.asarray(keys[-1][1], float)
    for i in range(len(keys) - 1):
        if ts[i] <= t <= ts[i + 1]:
            u = (t - ts[i]) / max(ts[i + 1] - ts[i], 1e-9)
            return lerp(np.asarray(keys[i][1], float), np.asarray(keys[i + 1][1], float), sm(u))


def rot_xyz(x=0.0, y=0.0, z=0.0):
    """Rotation matrix for local Euler (degrees) applied X then Z then Y (flex, side, twist)."""
    q = Quaternion((0, 1, 0), rad(y)) @ Quaternion((0, 0, 1), rad(z)) @ Quaternion((1, 0, 0), rad(x))
    return np.array(q.to_matrix())


def axis_angle(axis, deg):
    return np.array(Quaternion(Vector(axis).normalized(), rad(deg)).to_matrix())


def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def frame_from(y_axis, z_hint):
    y = unit(y_axis)
    z = np.asarray(z_hint, float) - np.dot(z_hint, y) * y
    z = unit(z)
    x = np.cross(y, z)
    return np.stack([x, y, z], 1)


class Solver:
    """Rest data from a Blender armature (canonical rest) + pose solving."""

    def __init__(self, arm):
        self.arm = arm
        self.rest = {}
        self.parent = {}
        self.length = {}
        for b in arm.data.bones:
            M = np.array(b.matrix_local)
            self.rest[b.name] = M
            self.parent[b.name] = b.parent.name if b.parent else None
            self.length[b.name] = b.length
        self.order = [b.name for b in arm.data.bones]   # parents before children
        self.rel = {}
        for n in self.order:
            p = self.parent[n]
            self.rel[n] = np.linalg.inv(self.rest[p]) @ self.rest[n] if p else self.rest[n]

    def head(self, n):
        return self.rest[n][:3, 3]

    def rest_rot(self, n):
        return self.rest[n][:3, :3]

    def solve(self, pose):
        """pose: dict bone -> 3x3 armature-space rotation (absolute) or ('local', R) relative to
        the rest-relative parent frame; 'Hips_pos' armature-space head position for Hips.
        Returns {bone: (loc Vector, quat Quaternion)} basis values."""
        M = {}
        out = {}
        for n in self.order:
            p = self.parent[n]
            base = (M[p] @ self.rel[n]) if p else self.rel[n].copy()
            spec = pose.get(n)
            if spec is None:
                Mn = base
            elif isinstance(spec, tuple) and spec[0] == "local":
                Mn = base.copy()
                Mn[:3, :3] = base[:3, :3] @ spec[1]
            else:
                Mn = base.copy()
                Mn[:3, :3] = spec
            if n == "Hips" and "Hips_pos" in pose:
                Mn[:3, 3] = pose["Hips_pos"]
            M[n] = Mn
            basis = np.linalg.inv(base) @ Mn
            loc = Vector(basis[:3, 3]) if n == "Hips" else Vector((0, 0, 0))
            q = Matrix(basis[:3, :3].tolist()).to_quaternion()
            out[n] = (loc, q)
        self.last_M = M
        return out

    def world(self, pose):
        self.solve(pose)
        return self.last_M


# --------------------------------------------------------------------------- IK

def two_bone(root, target, l1, l2, bend_dir):
    """Joint position of a two-bone chain reaching target; bend_dir = where the middle joint goes."""
    d = target - root
    L = np.linalg.norm(d)
    L = np.clip(L, abs(l1 - l2) + 1e-4, (l1 + l2) * 0.9995)
    dn = unit(d)
    a = (l1 * l1 + L * L - l2 * l2) / (2 * L)
    h = math.sqrt(max(l1 * l1 - a * a, 0.0))
    b = unit(bend_dir - np.dot(bend_dir, dn) * dn)
    mid = root + dn * a + b * h
    tgt = root + dn * L
    return mid, tgt


class Rig:
    """High-level posing on top of Solver: pelvis, spine FK, IK limbs, FK fingers, cloth."""

    def __init__(self, solver, L=None):
        self.S = solver
        r = solver.rest
        self.L = {}
        for S_, _s in SK.SIDES:
            self.L[S_] = dict(
                thigh=np.linalg.norm(r[f"{S_}LowerLeg"][:3, 3] - r[f"{S_}UpperLeg"][:3, 3]),
                shin=np.linalg.norm(r[f"{S_}Foot"][:3, 3] - r[f"{S_}LowerLeg"][:3, 3]),
                uarm=np.linalg.norm(r[f"{S_}LowerArm"][:3, 3] - r[f"{S_}UpperArm"][:3, 3]),
                farm=np.linalg.norm(r[f"{S_}Hand"][:3, 3] - r[f"{S_}LowerArm"][:3, 3]),
                foot=np.linalg.norm(r[f"{S_}Toes"][:3, 3] - r[f"{S_}Foot"][:3, 3]),
            )
        self.hips0 = r["Hips"][:3, 3].copy()
        self.ankle0 = {S_: r[f"{S_}Foot"][:3, 3].copy() for S_, _ in SK.SIDES}
        self.ball0 = {S_: r[f"{S_}Toes"][:3, 3].copy() for S_, _ in SK.SIDES}
        self.toe0 = {S_: (r[f"{S_}Toes"] @ np.array([0, self.S.length[f"{S_}Toes"], 0, 1]))[:3]
                     for S_, _ in SK.SIDES}
        self.leg_len = self.L["Left"]["thigh"] + self.L["Left"]["shin"]

    # --- pose dict builders -------------------------------------------------
    def new(self):
        return {}

    def pelvis(self, P, pos=(0, 0, 0), fwd=0.0, side=0.0, yaw=0.0):
        """Hips position offset (world) from rest + rotation (deg): forward tilt, side roll, yaw."""
        R0 = self.S.rest_rot("Hips")
        Rw = axis_angle((0, 0, 1), yaw) @ axis_angle((0, -1, 0), side) @ axis_angle((1, 0, 0), -fwd)
        P["Hips"] = Rw @ R0
        P["Hips_pos"] = self.hips0 + np.asarray(pos, float)
        return Rw

    def fk(self, P, bone, x=0.0, z=0.0, y=0.0):
        P[bone] = ("local", rot_xyz(x, y, z))

    def spine(self, P, fwd=0.0, side=0.0, twist=0.0, dist=(0.30, 0.35, 0.35)):
        for b, f in zip(("Spine", "Chest", "UpperChest"), dist):
            self.fk(P, b, x=fwd * f, z=side * f, y=twist * f)

    def neck_head(self, P, fwd=0.0, side=0.0, twist=0.0, split=0.4):
        self.fk(P, "Neck", x=fwd * split, z=side * split, y=twist * split)
        self.fk(P, "Head", x=fwd * (1 - split), z=side * (1 - split), y=twist * (1 - split))

    def leg_ik(self, P, S_, ankle, foot_fwd, foot_up=(0, 0, 1), toe_bend=0.0, knee_dir=None):
        """Place the ankle at `ankle` (world), orient the foot (forward/up), bend the toes."""
        M = self.S.world(P)
        hip = M[f"{S_}UpperLeg"][:3, 3]
        Lg = self.L[S_]
        fwd = unit(foot_fwd)
        kd = unit(knee_dir) if knee_dir is not None else unit(fwd * 1.0 + np.array([0, 0, 0.05]))
        knee, ank = two_bone(hip, np.asarray(ankle, float), Lg["thigh"], Lg["shin"], kd)
        yt = unit(knee - hip)
        zt = unit(kd - np.dot(kd, yt) * yt)
        P[f"{S_}UpperLeg"] = frame_from(yt, zt)
        ys = unit(ank - knee)
        xs = np.cross(yt, zt)
        zs = np.cross(xs, ys)
        P[f"{S_}LowerLeg"] = np.stack([xs, ys, zs], 1)
        # foot: rest foot frame has Y toward the ball, Z ~ up; build from desired forward/up
        R_rest = self.S.rest_rot(f"{S_}Foot")
        y_rest = R_rest[:, 1]
        fy = unit(fwd * math.cos(math.atan2(y_rest[2], math.hypot(y_rest[0], y_rest[1]))) +
                  np.asarray(foot_up, float) * y_rest[2])
        P[f"{S_}Foot"] = frame_from(fy, foot_up)
        self.fk(P, f"{S_}Toes", x=toe_bend)
        return ank

    def arm_ik(self, P, S_, wrist, elbow_dir, palm=None, hand_fwd=None, clav=(0.0, 0.0)):
        """Wrist at `wrist` (world), elbow pointing to elbow_dir, hand frame from palm normal and
        finger direction (both world); clav = (raise deg, forward deg) of the clavicle."""
        s = 1.0 if S_ == "Left" else -1.0
        self.fk(P, f"{S_}Shoulder", x=clav[1], z=-s * clav[0] * 0 + 0.0, y=0.0)
        if clav[0]:
            P[f"{S_}Shoulder"] = ("local", rot_xyz(clav[1], 0.0, s * clav[0]))
        M = self.S.world(P)
        sh = M[f"{S_}UpperArm"][:3, 3]
        Lg = self.L[S_]
        bend = -unit(elbow_dir)      # forearm folds away from the elbow direction
        elbow, wr = two_bone(sh, np.asarray(wrist, float), Lg["uarm"], Lg["farm"], unit(elbow_dir))
        yu = unit(elbow - sh)
        zu = unit(bend - np.dot(bend, yu) * yu)
        P[f"{S_}UpperArm"] = frame_from(yu, zu)
        yf = unit(wr - elbow)
        xu = np.cross(yu, zu)
        zf = np.cross(xu, yf)
        P[f"{S_}LowerArm"] = np.stack([xu, yf, zf], 1)
        if palm is not None:
            hf = unit(hand_fwd) if hand_fwd is not None else yf
            P[f"{S_}Hand"] = frame_from(hf, palm)
        else:
            P[f"{S_}Hand"] = ("local", rot_xyz(0, 0, 0))
        return elbow

    def fingers(self, P, S_, curl=0.3, thumb=0.3, index=None, spread=0.0):
        """curl 0 (open, = rest relaxed) .. 1 (fist)."""
        ix = curl if index is None else index
        self.fk(P, f"{S_}IndexProximal", x=ix * 55, z=spread)
        self.fk(P, f"{S_}IndexIntermediate", x=ix * 70)
        self.fk(P, f"{S_}MiddleProximal", x=curl * 60, z=-spread * 0.5)
        self.fk(P, f"{S_}MiddleIntermediate", x=curl * 75)
        self.fk(P, f"{S_}ThumbMetacarpal", x=thumb * 25, z=0.0)
        self.fk(P, f"{S_}ThumbProximal", x=thumb * 45)

    def world_of(self, P):
        return self.S.world(P)


# --------------------------------------------------------------------------- gait

class Gait:
    """Heel-toe foot trajectories for an in-place cycle; phase 0 = left heel strike."""

    def __init__(self, rig, cycle, speed, step_w=0.0, lift=0.11, duty=0.62, heel_ang=14.0, toe_ang=28.0,
                 toe_out=7.0, stance_knee=6.0):
        self.rig = rig
        self.T = cycle
        self.v = speed
        self.stride = speed * cycle
        self.duty = duty
        self.lift = lift
        self.heel_ang = heel_ang
        self.toe_ang = toe_ang
        self.step_w = step_w
        self.toe_out = toe_out

    def foot(self, S_, t, ground=0.0):
        """World ankle position, foot forward, foot up, toe bend for side S_ at time t."""
        s = 1.0 if S_ == "Left" else -1.0
        ph = (t / self.T + (0.0 if S_ == "Left" else 0.5)) % 1.0
        r = self.rig
        a0 = r.ankle0[S_]
        ball0 = r.ball0[S_]
        heel_back = 0.065 * r.leg_len / 0.86          # heel contact behind the ankle
        ankle_h = a0[2]
        fl = np.linalg.norm((ball0 - a0)[:2])           # ankle -> ball horizontal
        x_lat = a0[0] + s * self.step_w
        fwd = np.array([s * math.sin(rad(self.toe_out)), -math.cos(rad(self.toe_out)), 0.0])
        D = self.duty
        S = self.stride
        if ph < D:
            u = ph / D
            # contact point slides backward with the ground: y(u) = y_hs + S*u (forward is -y)
            ground_y = -S * 0.5 + S * u              # displacement along -fwd (world +y)
            # foot pitch: heel strike (+heel_ang toes up) -> flat by 0.18 -> heel rise from 0.62
            if u < 0.18:
                pitch = self.heel_ang * (1 - ss(u / 0.18))
                pivot = "heel"
            elif u < 0.60:
                pitch = 0.0
                pivot = "flat"
            else:
                pitch = -self.toe_ang * ss((u - 0.60) / 0.40)
                pivot = "ball"
            toe_bend = max(0.0, -pitch) * 0.9
        else:
            u = (ph - D) / (1 - D)
            e = sm(u)
            ground_y = S * 0.5 - S * e
            pitch = lerp(-self.toe_ang, self.heel_ang, ss(u * 1.15))
            pivot = "air"
            toe_bend = max(0.0, -pitch) * 0.9 * (1 - ss(u * 2))
        # foot frame
        R = axis_angle(np.cross(fwd, (0, 0, 1)), pitch)          # +pitch lifts toes
        f = R @ fwd
        up = R @ np.array([0, 0, 1.0])
        base = np.array([x_lat, a0[1], 0.0]) + np.array([0, ground_y, 0]) * 1.0
        base = base - fwd * 0.0
        heel = np.array([0, 0, 0.0]) - fwd * heel_back
        ballp = fwd * fl
        ank_local = np.array([0, 0, ankle_h])
        if pivot in ("heel",):
            # rotate the foot about the heel contact
            p_c = base + heel
            ank = p_c + R @ (ank_local - heel)
        elif pivot == "ball":
            p_c = base + ballp
            ank = p_c + R @ (ank_local - ballp)
        elif pivot == "flat":
            ank = base + ank_local
        else:
            clear = self.lift * math.sin(math.pi * u) ** 0.85
            ank = base + ank_local + np.array([0, 0, clear]) + R @ ank_local - ank_local
            ank = ank + np.array([0, 0, max(0.0, -pitch) * 0.0])
        return ank, f, up, toe_bend, ph


# --------------------------------------------------------------------------- secondary motion

class Spring:
    """Critically-damped-ish angular follow-through (per scalar channel)."""

    def __init__(self, k=60.0, d=9.0):
        self.k, self.d = k, d

    def run(self, target, dt=1.0 / FPS, loops=3, loop=True):
        target = np.asarray(target, float)
        n = len(target)
        x = target[0]
        v = 0.0
        out = np.zeros(n)
        for it in range(loops if loop else 1):
            for i in range(n):
                a = self.k * (target[i] - x) - self.d * v
                v += a * dt
                x += v * dt
                out[i] = x
        return out


def make_loop(frames_vals, blend=6):
    """Blend the last `blend` frames toward the first so frame[-1] == frame[0]."""
    v = np.asarray(frames_vals, float).copy()
    n = len(v)
    for i in range(blend):
        w = (i + 1) / blend
        v[n - blend + i] = v[n - blend + i] * (1 - w) + v[0] * w
    v[-1] = v[0]
    return v
