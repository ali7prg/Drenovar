"""Quadruped clip authoring for the guardians.

Frame description (dict):
  body : (dx, dy, dz, pitch, roll, yaw)   metres / degrees; pitch>0 nose up, roll>0 left side
         down, yaw>0 turn left; rotation about `pivot` (torso centre), applied to the hips bone.
  rot  : {bone: (rx, ry, rz)}   degrees about the world axes of the bone's rest frame
  feet : {leg: dict(pos=world paw-ball target, meta=deg, toe=deg, girdle=deg)}
         meta>0 tilts the metapodial back (heel lift / fold), toe>0 curls digits down,
         girdle>0 swings the scapula back.
Clips are in place (root never moves); loops have identical first/last frames; 30 fps.
"""
import math

import numpy as np

import grig

FPS = 30
X = np.array([1.0, 0, 0])
Y = np.array([0, 1.0, 0])
Z = np.array([0, 0, 1.0])


def Rd(axis, deg):
    return grig.rot_axis(axis, math.radians(deg))


def unit(v):
    v = np.asarray(v, float)
    return v / max(np.linalg.norm(v), 1e-12)


def ss(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def lerp(a, b, t):
    return np.asarray(a, float) * (1 - t) + np.asarray(b, float) * t


# --------------------------------------------------------------------------- key curves

def keys_smooth(t, keys):
    """Piecewise smoothstep through (time, value) keys (zero slope at keys: holds stay exact)."""
    ts = [k[0] for k in keys]
    if t <= ts[0]:
        return np.asarray(keys[0][1], float)
    if t >= ts[-1]:
        return np.asarray(keys[-1][1], float)
    i = np.searchsorted(ts, t) - 1
    t0, v0 = keys[i]
    t1, v1 = keys[i + 1]
    u = ss((t - t0) / max(t1 - t0, 1e-9))
    return lerp(v0, v1, u)


def keys_cr(t, keys):
    """Catmull-Rom through (time, value) keys (smooth velocity, for body/spine channels)."""
    ts = np.array([k[0] for k in keys], float)
    vs = [np.asarray(k[1], float) for k in keys]
    if t <= ts[0]:
        return vs[0]
    if t >= ts[-1]:
        return vs[-1]
    i = int(np.searchsorted(ts, t) - 1)
    t0, t1 = ts[i], ts[i + 1]
    p0, p1 = vs[i], vs[i + 1]
    pm = vs[i - 1] if i > 0 else p0
    tm = ts[i - 1] if i > 0 else t0 - (t1 - t0)
    p2 = vs[i + 2] if i + 2 < len(vs) else p1
    t2 = ts[i + 2] if i + 2 < len(ts) else t1 + (t1 - t0)
    h = t1 - t0
    m0 = (p1 - pm) / (t1 - tm) * h
    m1 = (p2 - p0) / (t2 - t0) * h
    u = (t - t0) / h
    h00 = 2 * u ** 3 - 3 * u ** 2 + 1
    h10 = u ** 3 - 2 * u ** 2 + u
    h01 = -2 * u ** 3 + 3 * u ** 2
    h11 = u ** 3 - u ** 2
    return h00 * p0 + h10 * m0 + h01 * p1 + h11 * m1


# --------------------------------------------------------------------------- composer

class Composer:
    def __init__(self, sk, legs, pivot, front_legs=("fore_L", "fore_R")):
        self.sk = sk
        self.legs = legs
        self.pivot = np.asarray(pivot, float)
        self.front = set(front_legs)
        self.leg_bones = set(b for ch in legs.values() for b in ch if b)
        self.neutral, self.meta, self.toe = {}, {}, {}
        for leg, (g, u, l, m, d) in legs.items():
            self.neutral[leg] = sk.head(d)
            self.meta[leg] = unit(sk.head(d) - sk.head(m))
            self.toe[leg] = unit(sk.tail(d) - sk.head(d))

    def local(self, bone, r):
        rx, ry, rz = r
        Rb = self.sk.rest[bone][:3, :3]
        Rw = Rd(Z, rz) @ Rd(Y, ry) @ Rd(X, rx)
        return Rb.T @ Rw @ Rb

    def body_matrix(self, body):
        dx, dy, dz, pitch, roll, yaw = body
        Rb = Rd(Z, yaw) @ Rd(Y, roll) @ Rd(X, -pitch)
        M = np.eye(4)
        M[:3, :3] = Rb
        M[:3, 3] = self.pivot + np.array([dx, dy, dz]) - Rb @ self.pivot
        return M

    def compose(self, f):
        sk = self.sk
        rot = f.get("rot", {})
        body = f.get("body", (0, 0, 0, 0, 0, 0))
        Mb = self.body_matrix(body)
        pose = {}
        for n in sk.order:
            p = sk.parent[n]
            if n in self.leg_bones:
                continue
            B = np.eye(4)
            if n in rot:
                B[:3, :3] = self.local(n, rot[n])
            if p is None:
                pose[n] = sk.rest[n] @ B
            elif n == "hips":
                pose[n] = Mb @ sk.rest[n] @ B
            else:
                pose[n] = pose[p] @ np.linalg.inv(sk.rest[p]) @ sk.rest[n] @ B
        lat = Mb[:3, :3] @ X
        feet = f.get("feet", {})
        for leg, ch in self.legs.items():
            ft = feet.get(leg, {})
            tgt = np.asarray(ft.get("pos", self.neutral[leg]), float)
            bw = float(ft.get("body_w", 0.0))
            md = Rd(lat, ft.get("meta", 0.0)) @ unit(lerp(self.meta[leg], Mb[:3, :3] @ self.meta[leg], bw))
            td = Rd(lat, ft.get("toe", 0.0)) @ unit(lerp(self.toe[leg], Mb[:3, :3] @ self.toe[leg], bw))
            pole = Mb[:3, :3] @ (Y if leg in self.front else -Y)
            rr = None
            if ch[0] is not None:
                rr = self.local(ch[0], (ft.get("girdle", 0.0), 0, 0))
            grig.solve_leg(sk, pose, ch, tgt, md, td, pole, root_rot=rr)
        return pose

    def body_point(self, body, p):
        M = self.body_matrix(body)
        return M[:3, :3] @ np.asarray(p, float) + M[:3, 3]


# --------------------------------------------------------------------------- gaits

def foot_gait(phase, duty, sweep, lift, front=True, fold=None, heel=34.0):
    """Returns (forward offset m, height m, meta deg, toe deg, girdle deg, in_stance)."""
    ph = phase % 1.0
    if ph < duty:
        s = ph / duty
        fwd = sweep * (0.5 - s)
        meta = -6.0 + heel * ss((s - 0.55) / 0.45)
        return fwd, 0.0, meta, 0.0, -10.0 + 20.0 * s if front else 0.0, True
    s = (ph - duty) / (1 - duty)
    e = 0.5 - 0.5 * math.cos(math.pi * s)
    fwd = sweep * (-0.5 + e)
    h = lift * math.sin(math.pi * min(1.0, s * 1.08)) ** 0.85
    fmax = fold if fold is not None else (72.0 if front else 48.0)
    if s < 0.32:
        meta = lerp(heel - 6.0, fmax, ss(s / 0.32))
        toe = lerp(0.0, 12.0, ss(s / 0.32))
    elif s < 0.78:
        u = ss((s - 0.32) / 0.46)
        meta = lerp(fmax, -14.0, u)
        toe = lerp(12.0, -10.0, u)
    else:
        u = ss((s - 0.78) / 0.22)
        meta = lerp(-14.0, -6.0, u)
        toe = lerp(-10.0, 0.0, u)
    girdle = (10.0 - 20.0 * e) if front else 0.0
    return fwd, h, float(meta), float(toe), girdle, False


def touchdowns(phases, duty, T):
    """Footfall (touchdown) and lift-off times of a cyclic gait, seconds."""
    out = {}
    for leg, off in phases.items():
        td = (off % 1.0) * T
        lo = ((off + duty) % 1.0) * T
        out[leg] = {"touchdown": round(td, 3), "liftoff": round(lo, 3)}
    return out


def sample(fn, seconds, loop=False):
    n = int(round(seconds * FPS))
    frames = [fn(i / FPS) for i in range(n + 1)]
    if loop:
        frames[-1] = frames[0]
    return frames
