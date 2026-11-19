"""Ancient Maw v2 clips (13 manifest clips, exact durations, markers, measured foot slip).

Pose model per frame (numpy FK/IK, mv2_pose): pelvis offset/rotation, spine/neck/head distribution, jaw,
lids, breath, tail chain with delayed follow-through, legs by two-bone IK to planted/stepping ball targets
with heel lift, toes flat on the ground in stance, arms. Keys at 60 fps so 4.25 / 5.45 / 0.55 s are exact.
Forward = -Y (Blender), left = +X.  Clips are in place (root bone fixed); turns use the horse convention
(node yaw curve rootYawDeg * smoothstep(t/D), feet planted in that rotating frame).
"""
import math

import numpy as np
from scipy.interpolate import PchipInterpolator

import mv2_body as B
import mv2_pose as PO

FPS = 60
REST_BALL = {"L": np.array([0.68, -0.15, 0.17]), "R": np.array([-0.68, -0.15, 0.17])}
REST_ANKLE_OFF = np.array([0.0, 0.25, 0.57])          # ankle - ball (rest)
SPINE = ["spine_01", "spine_02", "spine_03"]
NECK = ["neck_01", "neck_02", "neck_03"]
TAIL = [f"tail_{i:02d}" for i in range(1, 13)]
TOES = ["toe2a", "toe2b", "toe3a", "toe3b", "toe4a", "toe4b", "hallux"]


def ss(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


class Curve:
    """Shape-preserving (PCHIP) curve through keys [(t, v), ...]; constant outside."""

    def __init__(self, keys, loop=None):
        ks = sorted(keys)
        self.t = np.array([k[0] for k in ks], float)
        self.v = np.array([k[1] for k in ks], float)
        self.loop = loop
        if len(ks) == 1:
            self.f = None
        else:
            self.f = PchipInterpolator(self.t, self.v, extrapolate=False)

    def __call__(self, t):
        if self.loop:
            t = t % self.loop
        if self.f is None:
            return float(self.v[0])
        t = float(np.clip(t, self.t[0], self.t[-1]))
        return float(self.f(t))


def C(*keys, loop=None):
    return Curve(list(keys), loop)


def Z(v=0.0):
    return Curve([(0.0, v)])


def rot_xyz(yaw=0.0, pitch=0.0, roll=0.0):
    """World rotation: yaw about +Z (left turn +), pitch about +X (+ lifts a backward-pointing bone such as the
    tail, lowers a forward-pointing one; Rig.build negates it for the forward chain), roll about -Y (left up +)."""
    return PO.qmat((0, 0, 1), yaw) @ PO.qmat((1, 0, 0), pitch) @ PO.qmat((0, -1, 0), roll)


# ------------------------------------------------------------------------------------ steps
class Steps:
    """Planned foot placements: list of (t_lift, t_land, (dx, dy) target offset from rest, lift height)."""

    def __init__(self, side, start=(0.0, 0.0), plan=(), start_yaw=0.0, heel=None):
        self.side = side
        self.start = np.array(start, float)
        self.plan = sorted(plan, key=lambda s: s[0])
        self.heel = heel

    def at(self, t):
        pos = self.start.copy()
        lift = 0.0
        swing = False
        for (t0, t1, tgt, h) in self.plan:
            tgt = np.array(tgt, float)
            if t >= t1:
                pos = tgt
            elif t > t0:
                s = (t - t0) / (t1 - t0)
                e = ss(s) * 0.85 + s * 0.15
                pos = pos + (tgt - pos) * e
                lift = h * math.sin(math.pi * min(1.0, s * 1.08)) ** 0.85
                swing = True
                break
            else:
                break
        return pos, lift, swing


# ------------------------------------------------------------------------------------ pose builder
class Rig:
    def __init__(self, arm):
        self.sk = PO.Skeleton(arm)
        self.ps = PO.Pose(self.sk)
        self.rest_toe_rot = {}
        for s in "LR":
            for t in TOES:
                self.rest_toe_rot[f"{t}_{s}"] = self.sk.rest[f"{t}_{s}"][:3, :3].copy()

    def build(self, p):
        """p: dict of channel values at one instant (missing = neutral)."""
        ps = self.ps
        ps.reset()
        g = lambda k, d=0.0: p.get(k, d)  # noqa: E731
        # pelvis
        # forward-pointing chain (pelvis, spine, neck, head): channel pitch > 0 = nose UP, i.e. a negative
        # rotation about +X (a +X rotation turns -Y forward downwards)
        ps.translate_world("pelvis", [g("px"), g("py"), g("pz")])
        ps.rot_world("pelvis", rot_xyz(g("pyaw"), -g("ppitch"), g("proll")))
        # spine (chest) distribution
        for i, b in enumerate(SPINE):
            w = (0.25, 0.35, 0.40)[i]
            ps.rot_world(b, rot_xyz(g("syaw") * w, -g("spitch") * w, g("sroll") * w))
        if "breath" in self.sk.names:
            sc = 1.0 + g("breath")
            ps.basis["breath"][:3, :3] = ps.basis["breath"][:3, :3] @ np.diag([sc, 1.0 + 0.6 * g("breath"), sc])
            ps.dirty = True
        # neck + head
        for i, b in enumerate(NECK):
            w = (0.40, 0.33, 0.27)[i]
            ps.rot_world(b, rot_xyz(g("nyaw") * w, -g("npitch") * w, g("nroll") * w))
        ps.rot_world("head", rot_xyz(g("hyaw"), -g("hpitch"), g("hroll")))
        ps.rot_world_axis("jaw", (1, 0, 0), g("jaw"))
        for i, b in enumerate(("tongue_01", "tongue_02", "tongue_03")):
            ps.rot_world_axis(b, (1, 0, 0), g("tongue") * (0.5 + 0.25 * i))
        # lids: blink 0..1 (upper lid down 34 deg, lower lid up 16 deg) about the eye's lateral axis
        bl = g("blink")
        if bl > 1e-4:
            for s, sx in (("L", 1), ("R", -1)):
                ps.rot_world_axis(f"lid_up_{s}", (sx * 1, 0, 0), 0.0)
                ax = np.array([0.55, 0.80, 0.0]) * np.array([1, sx, 1])
                ps.rot_world(f"lid_up_{s}", PO.qmat(ax, -34 * bl * sx))
                ps.rot_world(f"lid_lo_{s}", PO.qmat(ax, 16 * bl * sx))
        # tail chain: yaw/pitch per segment (delayed curves supplied in p["tail"] as list of (yaw, pitch))
        for i, b in enumerate(TAIL):
            ty, tp = p.get("tail", [(0.0, 0.0)] * 12)[i]
            ps.rot_world(b, rot_xyz(ty, tp, 0.0))
        # arms
        for s, sx in (("L", 1), ("R", -1)):
            ps.rot_world(f"upperarm_{s}", rot_xyz(sx * g("arm_yaw"), g(f"arm_pitch_{s}", g("arm_pitch")), 0.0))
            ps.rot_world_axis(f"forearm_{s}", (1, 0, 0), g(f"elbow_{s}", g("elbow")))
            ps.rot_world_axis(f"hand_{s}", (1, 0, 0), g("wrist"))
            for f in ("finger1", "finger2", "finger3"):
                ps.rot_world_axis(f"{f}a_{s}", (1, 0, 0), g("fingers"))
                ps.rot_world_axis(f"{f}b_{s}", (1, 0, 0), g("fingers") * 0.8)
        # legs
        over = 0.0
        for s, sx in (("L", 1), ("R", -1)):
            ball = np.asarray(p[f"ball_{s}"], float)
            fyaw = g(f"fyaw_{s}")
            heel = g(f"heel_{s}")          # heel lift (deg) rolling over the toes
            Ry = PO.qmat((0, 0, 1), fyaw)
            off = Ry @ (PO.qmat((1, 0, 0), heel) @ REST_ANKLE_OFF)
            ankle = ball + off
            pole = Ry @ np.array([sx * 0.15, -1.0, 0.0])
            over = max(over, ps.two_bone(f"thigh_{s}", f"shin_{s}", ankle, pole))
            ps.aim(f"foot_{s}", ball - ps.head(f"foot_{s}"))
            curl = g(f"curl_{s}")
            for t in TOES:
                n = f"{t}_{s}"
                Rw = Ry @ self.rest_toe_rot[n]
                if curl:
                    Rw = PO.qmat(Ry @ np.array([1.0, 0, 0]), -curl * (1.3 if t.endswith("b") else 1.0)) @ Rw
                ps.set_world_rot(n, Rw)
        return over

    def keyframe(self):
        out = {}
        for n in self.sk.names:
            loc, q = self.ps.local_qt(n)
            sc = np.sqrt((self.ps.basis[n][:3, :3] ** 2).sum(0))
            out[n] = (loc, q, sc)
        return out

    def foot_points(self):
        M = self.ps.fk()
        pts = {}
        for s in "LR":
            pts[s] = {"ball": self.ps.tail(f"foot_{s}"), "toe3": self.ps.tail(f"toe3b_{s}"),
                      "heel": self.ps.head(f"foot_{s}")}
        return pts


# ------------------------------------------------------------------------------------ helpers
def tail_wave(t, base_yaw, base_pitch, delay=0.05, gain_yaw=None, gain_pitch=None, wave=None):
    """12 segments following base curves with a per-segment delay (follow-through)."""
    gy = gain_yaw or [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.25, 1.3, 1.3, 1.3]
    gp = gain_pitch or [0.8, 0.85, 0.9, 0.95, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    out = []
    for i in range(12):
        ti = t - delay * i
        y = base_yaw(ti) * gy[i] / 12.0 * 1.35
        pch = base_pitch(ti) * gp[i] / 12.0 * 1.2
        if wave is not None:
            y += wave(ti, i)
        out.append((y, pch))
    return out


def planted(side, dx=0.0, dy=0.0):
    return REST_BALL[side] + np.array([dx, dy, 0.0])


def idle_channels(t, D=5.0, amp=1.0):
    """Shared breathing/look layer (loops on D)."""
    w = 2 * math.pi / D
    br = 0.5 - 0.5 * math.cos(2 * w * t)                    # two breaths per idle cycle
    ch = {
        "breath": 0.035 * br * amp,
        "pz": -0.012 * br * amp,
        "spitch": 1.2 * br * amp,
        "npitch": -1.0 * br * amp + 1.5 * math.sin(w * t + 0.6) * amp,
        "nyaw": 5.0 * math.sin(w * t) * amp,
        "hyaw": 3.0 * math.sin(w * t - 0.5) * amp,
        "hpitch": 1.5 * math.sin(2 * w * t + 1.0) * amp,
        "jaw": (1.0 + 1.0 * br) * amp,
        "arm_pitch": 2.0 * math.sin(w * t + 1.2) * amp,
        "elbow": -3.0 + 2.0 * math.sin(w * t + 2.0) * amp,
        "fingers": 4.0 + 2.0 * math.sin(w * t),
    }
    return ch


def blink_at(t, times, dur=0.22):
    v = 0.0
    for tb in times:
        x = (t - tb) / dur
        if 0 <= x <= 1:
            v = max(v, math.sin(math.pi * x))
    return v


# ------------------------------------------------------------------------------------ clips
def clip_idle(t):
    D = 5.0
    ch = idle_channels(t, D)
    ch.update({f"ball_{s}": planted(s) for s in "LR"})
    w = 2 * math.pi / D
    by = lambda x: 4.0 * math.sin(w * x)  # noqa: E731
    bp = lambda x: 2.0 * math.sin(2 * w * x + 0.7)  # noqa: E731
    ch["tail"] = tail_wave(t, by, bp, delay=0.09)
    ch["blink"] = blink_at(t % D, [1.6, 4.05])
    return ch


WALK_D = 1.6
WALK_SPEED = 1.6                     # m/s -> stride 2.56 m per cycle
WALK_DUTY = 0.62


WALK_LIFT = 0.30
WALK_PZ = 0.0
WALK_PITCH = 0.0


def walk_foot(t, side):
    phase = (t / WALK_D + (0.0 if side == "L" else 0.5)) % 1.0
    # body-relative foot excursion during stance = ground speed * stance time (no slip in the world)
    stride = WALK_SPEED * WALK_D * WALK_DUTY
    if phase < WALK_DUTY:
        s = phase / WALK_DUTY
        y = -stride / 2 + stride * s           # forward (-Y) at contact -> backward during stance
        z = 0.0
        heel = 22.0 * ss((s - 0.70) / 0.30)    # heel-off late in stance
        curl = 0.0
        contact = True
    else:
        s = (phase - WALK_DUTY) / (1 - WALK_DUTY)
        e = ss(s)
        y = stride / 2 - stride * e
        z = WALK_LIFT * math.sin(math.pi * s) ** 0.9
        heel = 22.0 * (1 - ss(s / 0.5)) + 6.0 * math.sin(math.pi * s)
        curl = 34.0 * math.sin(math.pi * min(1.0, s * 1.1))
        contact = False
    return np.array([0.0, y, z]), heel, curl, contact


def clip_walk(t):
    D = WALK_D
    ch = idle_channels(t, D, amp=0.3)
    ph = 2 * math.pi * t / D
    ch.update({
        "pz": WALK_PZ - 0.06 * (0.5 + 0.5 * math.cos(2 * ph)) + 0.02,      # dips at each contact
        "px": 0.05 * math.sin(ph - 0.4),                          # sway over the stance foot
        "pyaw": 3.0 * math.sin(ph),
        "proll": 2.5 * math.sin(ph - 0.3),
        "ppitch": WALK_PITCH - 1.0 + 1.0 * math.cos(2 * ph),
        "syaw": -2.0 * math.sin(ph),
        "nyaw": -2.5 * math.sin(ph - 0.3),                        # head stabilised against the pelvis yaw
        "npitch": -2.0 * math.cos(2 * ph + 0.5),
        "hpitch": 1.0 * math.cos(2 * ph + 0.9),
        "arm_pitch": 0.0,
        "arm_pitch_L": 6.0 * math.sin(ph + math.pi),
        "arm_pitch_R": 6.0 * math.sin(ph),
        "jaw": 2.0,
    })
    for s in "LR":
        off, heel, curl, _c = walk_foot(t, s)
        ch[f"contact_{s}"] = _c
        ch[f"ball_{s}"] = planted(s) + off
        ch[f"heel_{s}"] = heel
        ch[f"curl_{s}"] = curl
    by = lambda x: -5.0 * math.sin(2 * math.pi * x / D)  # noqa: E731
    bp = lambda x: 1.5 * math.cos(4 * math.pi * x / D)  # noqa: E731
    ch["tail"] = tail_wave(t, by, bp, delay=0.06)
    return ch


TURN_D = 1.3
TURN_YAW = 45.0


def turn_yaw(t, sign):
    return sign * TURN_YAW * float(ss(t / TURN_D))


def clip_turn(t, sign):
    """sign +1 = left. Node yaw follows rootYawDeg*smoothstep(t/D); planted feet counter-rotate locally."""
    D = TURN_D
    ch = idle_channels(t, 5.0, amp=0.3)
    yaw_node = turn_yaw(t, sign)
    inner = "L" if sign > 0 else "R"
    outer = "R" if sign > 0 else "L"

    def foot(side, t_lift, t_land):
        # world-planted at its start position (node yaw 0) until lift; lands at its rest place in the
        # node frame of the landing time; local = R(-yaw_node(t)) @ world
        y0 = 0.0
        y1 = turn_yaw(t_land, sign)
        start_w = PO.qmat((0, 0, 1), y0) @ planted(side)
        land_w = PO.qmat((0, 0, 1), y1) @ planted(side)
        if t <= t_lift:
            w = start_w
            lift = 0.0
            sw = False
        elif t >= t_land:
            w = land_w
            lift = 0.0
            sw = False
        else:
            s = (t - t_lift) / (t_land - t_lift)
            w = start_w + (land_w - start_w) * ss(s)
            lift = 0.26 * math.sin(math.pi * s)
            sw = True
        loc = PO.qmat((0, 0, 1), -yaw_node) @ w
        loc = loc + np.array([0, 0, lift])
        fy = (y1 if t >= t_land else (0.0 if t <= t_lift else y1 * ss((t - t_lift) / (t_land - t_lift)))) - yaw_node
        return loc, fy, sw
    for side, (a, b) in ((inner, (0.18, 0.62)), (outer, (0.62, 1.10))):
        loc, fy, sw = foot(side, a, b)
        ch[f"contact_{side}"] = not sw
        ch[f"ball_{side}"] = loc
        ch[f"fyaw_{side}"] = fy
        ch[f"heel_{side}"] = 14.0 * (1.0 if sw else 0.0) * math.sin(math.pi * np.clip((t - a) / (b - a), 0, 1))
        ch[f"curl_{side}"] = 20.0 * (1.0 if sw else 0.0)
    # body: anticipation (head leads, hips lag), counter-rotation of the node frame for the hips
    lead = C((0, 0), (0.15, 12), (0.6, 18), (1.0, 8), (1.3, 0))
    lag = C((0, 0), (0.25, -8), (0.75, -6), (1.3, 0))
    ch["nyaw"] = sign * lead(t)
    ch["hyaw"] = sign * lead(t) * 0.5
    ch["pyaw"] = sign * lag(t)
    ch["syaw"] = sign * 0.5 * lead(t)
    ch["proll"] = sign * C((0, 0), (0.3, 3), (0.8, -2), (1.3, 0))(t)
    ch["pz"] = C((0, 0), (0.15, -0.05), (0.6, -0.03), (1.0, -0.05), (1.3, 0))(t)
    by = C((0, 0), (0.3, -18), (0.8, -10), (1.3, 0))
    ch["tail"] = tail_wave(t, lambda x: sign * by(x), lambda x: 0.0, delay=0.06)
    ch["_node_yaw"] = yaw_node
    return ch


def crouch(depth):
    return {"pz": -0.38 * depth, "ppitch": -4.0 * depth, "npitch": -14.0 * depth, "hpitch": -6.0 * depth}


def clip_awaken(t):
    D = 4.2
    ch = idle_channels(t, 5.0, amp=0.6)
    rise = C((0, 1.0), (1.2, 1.0), (2.6, 0.05), (3.0, -0.1), (3.8, 0.0), (4.2, 0.0))(t)
    ch.update({
        "pz": -0.42 * rise + ch["pz"],
        "ppitch": -6.0 * rise + C((0, 0), (2.6, 0), (3.2, 7), (3.9, 0), (4.2, 0))(t),
        "npitch": -24.0 * rise + C((0, 0), (2.6, 0), (2.95, 26), (3.6, 20), (4.0, 0), (4.2, 0))(t),
        "hpitch": -12.0 * rise + C((0, 0), (2.6, 0), (3.0, 14), (3.6, 10), (4.0, 0), (4.2, 0))(t),
        "nyaw": C((0, -10), (1.0, -10), (1.8, 6), (2.5, -4), (3.2, 0), (4.2, 0))(t),
        "jaw": C((0, 0), (2.6, 2), (2.95, 34), (3.55, 30), (3.9, 3), (4.2, 1.5))(t),
        "breath": C((0, 0.01), (2.5, 0.05), (2.9, 0.06), (3.6, 0.0), (4.2, 0.0))(t),
        "arm_pitch": C((0, -10), (2.6, -5), (3.0, -22), (3.7, -18), (4.2, 0))(t),
        "fingers": C((0, 10), (2.9, 0), (3.2, -12), (3.8, -8), (4.2, 4))(t),
        "blink": 1.0 if t < 1.05 else blink_at(t, [1.05], 0.4) if t < 1.45 else blink_at(t, [2.2]),
    })
    for s in "LR":
        ch[f"ball_{s}"] = planted(s)
    by = C((0, 6), (1.5, 4), (2.6, -4), (3.2, 10), (3.8, 4), (4.2, 0))
    bp = C((0, -10), (1.2, -10), (2.6, 0), (3.1, 14), (3.8, 4), (4.2, 0))
    ch["tail"] = tail_wave(t, by, bp, delay=0.07)
    return ch


def clip_phase_roar(t):
    D = 2.8
    ch = idle_channels(t, 5.0, amp=0.3)
    shake = 3.0 * math.sin(2 * math.pi * 7 * t) * float(ss((t - 0.75) / 0.2) * (1 - ss((t - 1.9) / 0.3)))
    ch.update({
        "pz": C((0, 0), (0.45, -0.16), (0.8, 0.06), (1.9, 0.04), (2.8, 0))(t),
        "ppitch": C((0, 0), (0.45, -5), (0.85, 9), (1.9, 7), (2.8, 0))(t),
        "spitch": C((0, 0), (0.45, -4), (0.85, 8), (1.9, 6), (2.8, 0))(t),
        "npitch": C((0, 0), (0.45, -16), (0.85, 32), (1.9, 28), (2.4, 4), (2.8, 0))(t),
        "hpitch": C((0, 0), (0.45, -8), (0.85, 16), (1.9, 12), (2.8, 0))(t) + shake * 0.5,
        "hroll": shake,
        "nyaw": C((0, 0), (0.85, 0), (1.3, 8), (1.9, -6), (2.8, 0))(t),
        "jaw": C((0, 1), (0.45, 4), (0.8, 38), (1.95, 34), (2.3, 4), (2.8, 1))(t),
        "tongue": C((0, 0), (0.8, -10), (1.9, -12), (2.3, 0), (2.8, 0))(t),
        "breath": C((0, 0.0), (0.45, 0.06), (0.9, -0.01), (2.8, 0.0))(t),
        "arm_pitch": C((0, 0), (0.45, 6), (0.85, -26), (1.9, -22), (2.8, 0))(t),
        "arm_yaw": C((0, 0), (0.85, 10), (1.9, 8), (2.8, 0))(t),
        "fingers": C((0, 4), (0.85, -16), (1.9, -12), (2.8, 4))(t),
    })
    for s in "LR":
        ch[f"ball_{s}"] = planted(s)
    by = C((0, 0), (0.85, 0), (1.4, 8), (2.0, -6), (2.8, 0))
    bp = C((0, 0), (0.45, -6), (0.9, 16), (1.9, 12), (2.8, 0))
    ch["tail"] = tail_wave(t, by, bp, delay=0.07)
    return ch


def clip_hit(t):
    D = 0.55
    ch = idle_channels(t, 5.0, amp=0.2)
    k = C((0, 0), (0.09, 1.0), (0.22, 0.75), (0.55, 0))(t)
    ch.update({
        "py": 0.12 * k, "pz": -0.05 * k, "ppitch": 3.0 * k, "proll": -3.0 * k,
        "npitch": 14.0 * k, "nyaw": 10.0 * k, "hpitch": 8.0 * k, "hyaw": 6.0 * k,
        "jaw": 2.0 + 16.0 * C((0, 0), (0.08, 1.0), (0.3, 0.3), (0.55, 0))(t),
        "blink": C((0, 0), (0.05, 1.0), (0.18, 0.2), (0.55, 0))(t),
        "arm_pitch": -10.0 * k, "fingers": 4 - 10.0 * k,
    })
    for s in "LR":
        ch[f"ball_{s}"] = planted(s)
    ch["tail"] = tail_wave(t, lambda x: 6.0 * C((0, 0), (0.12, 1), (0.55, 0))(x),
                           lambda x: 8.0 * C((0, 0), (0.1, 1), (0.55, 0))(x), delay=0.035)
    return ch


def clip_stagger(t):
    D = 1.8
    ch = idle_channels(t, 5.0, amp=0.2)
    k = C((0, 0), (0.25, 1.0), (0.7, 0.9), (1.3, 0.25), (1.8, 0))
    ch.update({
        "px": -0.30 * k(t), "py": 0.18 * k(t), "pz": -0.14 * k(t),
        "proll": -9.0 * k(t), "pyaw": 7.0 * k(t), "ppitch": 4.0 * k(t),
        "sroll": -5.0 * k(t), "syaw": 6.0 * k(t),
        "nyaw": C((0, 0), (0.3, 22), (0.75, -12), (1.25, 6), (1.8, 0))(t),
        "npitch": C((0, 0), (0.3, 14), (0.8, -10), (1.3, 3), (1.8, 0))(t),
        "nroll": -10.0 * k(t),
        "jaw": C((0, 1), (0.3, 18), (0.9, 6), (1.8, 1))(t),
        "blink": C((0, 0), (0.15, 1.0), (0.35, 0.0), (1.8, 0))(t),
        "arm_pitch_L": -14.0 * k(t), "arm_pitch_R": 10.0 * k(t), "fingers": 10.0 * k(t),
    })
    # catch step: right foot steps out to the right (-X) and back, left planted
    st = Steps("R", start=(0, 0), plan=[(0.22, 0.62, (-0.32, 0.22), 0.30), (1.05, 1.55, (0.0, 0.0), 0.22)])
    off, lift, sw = st.at(t)
    ch["ball_R"] = planted("R", off[0], off[1]) + np.array([0, 0, lift])
    ch["contact_R"] = not sw
    ch["curl_R"] = 20.0 if sw else 0.0
    ch["heel_R"] = 12.0 if sw else 0.0
    ch["ball_L"] = planted("L")
    ch["heel_L"] = 8.0 * k(t)
    by = C((0, 0), (0.35, 22), (0.85, -12), (1.35, 6), (1.8, 0))
    ch["tail"] = tail_wave(t, by, lambda x: 4.0 * k(x), delay=0.06)
    return ch


def clip_death(t):
    """Sway, knees buckle, collapse onto the right side; body ground contact at 3.7 s; settles."""
    D = 5.2
    ch = idle_channels(t, 5.0, amp=0.15 * float(1 - ss((t - 1.0) / 1.0)))
    fall = C((0, 0), (1.4, 0.06), (2.3, 0.25), (3.3, 0.82), (3.7, 1.0), (3.95, 0.97), (4.3, 1.0), (5.2, 1.0))(t)
    roll = C((0, 0), (1.2, 4), (2.2, -6), (3.0, -10), (3.7, -14), (3.95, -12), (4.4, -13), (5.2, -13))(t)
    ch.update({
        "pz": -1.36 * fall,
        "px": -0.10 * fall,
        "py": 0.20 * fall,
        "proll": roll,
        "ppitch": C((0, 0), (1.2, 3), (2.4, -6), (3.7, -10), (5.2, -9))(t),
        "pyaw": C((0, 0), (2.0, 4), (3.7, 10), (5.2, 10))(t),
        "spitch": C((0, 0), (1.2, -3), (3.7, -8), (5.2, -7))(t),
        "nyaw": C((0, 0), (1.0, -12), (1.8, 14), (2.6, 6), (3.7, 30), (4.4, 34), (5.2, 34))(t),
        "npitch": C((0, 0), (1.0, 18), (1.8, 6), (2.8, -18), (3.7, -26), (4.3, -22), (5.2, -24))(t),
        "nroll": C((0, 0), (3.0, 10), (3.9, 30), (5.2, 32))(t),
        "hpitch": C((0, 0), (1.0, 10), (2.8, -8), (3.9, -14), (5.2, -12))(t),
        "jaw": C((0, 1), (1.0, 26), (1.7, 10), (2.8, 18), (3.8, 6), (4.6, 12), (5.2, 11))(t),
        "tongue": C((0, 0), (4.0, 0), (4.6, -8), (5.2, -8))(t),
        "blink": C((0, 0), (3.6, 0), (4.4, 0.65), (5.2, 0.8))(t),
        "breath": C((0, 0), (1.0, 0.05), (1.8, -0.02), (5.2, -0.03))(t),
        "arm_pitch": C((0, 0), (1.2, -12), (3.0, -30), (3.8, -45), (5.2, -40))(t),
        "elbow": C((0, -3), (3.8, -30), (5.2, -25))(t),
        "fingers": C((0, 4), (3.8, 22), (5.2, 26))(t),
    })
    # feet: planted until the buckle, then the legs fold (targets pulled in/up relative to the falling body)
    fold = float(ss((t - 2.2) / 1.4))
    ch["contact_L"] = ch["contact_R"] = t < 2.2
    for s, sx in (("L", 1), ("R", -1)):
        b = planted(s)
        ch[f"ball_{s}"] = b + np.array([sx * 0.30 * fold, 0.75 * fold, 0.40 * fold])
        ch[f"heel_{s}"] = 62.0 * fold
        ch[f"curl_{s}"] = 25.0 * fold
    by = C((0, 0), (1.0, -8), (2.0, 10), (3.0, -6), (3.7, -16), (4.3, -22), (5.2, -22))
    bp = C((0, 0), (2.0, -4), (3.2, -18), (3.7, -26), (4.2, -22), (5.2, -24))
    ch["tail"] = tail_wave(t, by, bp, delay=0.07)
    return ch


def clip_jaw_arc(t):
    """Telegraph 0-2.4 (weight back, neck coiled high, jaw opening), active 2.4-2.85 (arcing lunge bite
    right->left, snap at 2.75), recovery 2.85-4.25."""
    D = 4.25
    ch = idle_channels(t, 5.0, amp=0.25)
    tr = 0.6 * math.sin(2 * math.pi * 9 * t) * float(ss((t - 1.4) / 0.6) * (1 - ss((t - 2.35) / 0.05)))
    ch.update({
        "py": C((0, 0), (1.8, 0.32), (2.35, 0.36), (2.62, -0.42), (2.85, -0.36), (3.6, -0.05), (4.25, 0))(t),
        "pz": C((0, 0), (1.8, -0.14), (2.35, -0.16), (2.62, -0.22), (2.85, -0.2), (3.6, -0.03), (4.25, 0))(t),
        "ppitch": C((0, 0), (1.8, 7), (2.35, 8), (2.62, -9), (2.85, -7), (3.8, 0), (4.25, 0))(t),
        "pyaw": C((0, 0), (1.8, -6), (2.35, -8), (2.62, 6), (2.85, 9), (3.8, 1), (4.25, 0))(t),
        "spitch": C((0, 0), (1.8, 6), (2.35, 7), (2.62, -8), (2.85, -6), (4.25, 0))(t),
        "npitch": C((0, 0), (1.8, 26), (2.35, 30), (2.6, -24), (2.85, -20), (3.6, -4), (4.25, 0))(t) + tr,
        "hpitch": C((0, 0), (1.8, -10), (2.35, -12), (2.6, 10), (2.85, 6), (3.6, 0), (4.25, 0))(t),
        "nyaw": C((0, 0), (1.8, -16), (2.35, -22), (2.55, 6), (2.85, 30), (3.5, 8), (4.25, 0))(t),
        "hyaw": C((0, 0), (2.35, -8), (2.85, 12), (3.6, 0), (4.25, 0))(t),
        "nroll": C((0, 0), (2.35, -6), (2.85, 8), (4.25, 0))(t),
        "jaw": C((0, 1), (1.6, 8), (2.35, 30), (2.5, 40), (2.68, 38), (2.76, 2), (2.95, 6), (3.6, 2), (4.25, 1))(t),
        "tongue": C((0, 0), (2.35, -8), (2.7, 0), (4.25, 0))(t),
        "arm_pitch": C((0, 0), (2.35, 8), (2.6, -16), (3.4, -4), (4.25, 0))(t),
        "fingers": C((0, 4), (2.35, -6), (2.7, 18), (3.6, 6), (4.25, 4))(t),
    })
    for s in "LR":
        ch[f"ball_{s}"] = planted(s)
    ch["heel_R"] = C((0, 0), (1.8, 6), (2.35, 8), (2.62, 0), (4.25, 0))(t)
    by = C((0, 0), (1.8, 10), (2.35, 14), (2.7, -16), (3.0, -20), (3.7, 4), (4.25, 0))
    bp = C((0, 0), (1.8, 14), (2.35, 16), (2.7, -4), (3.4, 2), (4.25, 0))
    ch["tail"] = tail_wave(t, by, bp, delay=0.055)
    return ch


def clip_tail_sweep(t):
    """Telegraph 0-3.0: body coils, tail cocked to the LEFT (+X) side and raised, head looks back over the right
    shoulder; active 3.0-3.65: hips whip, full sweep through the rear arc to the right; recovery 3.65-5.45."""
    D = 5.45
    ch = idle_channels(t, 5.0, amp=0.25)
    coil = C((0, 0), (2.2, 0.9), (2.95, 1.0), (3.12, 0.6), (3.4, -0.65), (3.65, -1.0), (4.3, -0.55), (5.0, -0.1),
             (5.45, 0))
    ch.update({
        "pyaw": 24.0 * coil(t),
        "syaw": -16.0 * coil(t),
        "nyaw": -26.0 * coil(t),
        "hyaw": -10.0 * coil(t),
        "proll": 4.0 * coil(t),
        "pz": C((0, 0), (2.2, -0.22), (2.95, -0.26), (3.3, -0.18), (3.65, -0.22), (4.5, -0.06), (5.45, 0))(t),
        "ppitch": C((0, 0), (2.2, -3), (3.3, 2), (4.5, 0), (5.45, 0))(t),
        "npitch": C((0, 0), (2.2, -8), (3.3, 4), (4.5, 0), (5.45, 0))(t),
        "jaw": C((0, 1), (2.2, 6), (3.1, 14), (3.6, 4), (5.45, 1))(t),
        "arm_pitch": C((0, 0), (2.2, 6), (3.4, -10), (5.45, 0))(t),
    })
    for s in "LR":
        ch[f"ball_{s}"] = planted(s)
        ch[f"heel_{s}"] = 0.0
    ch["heel_L"] = C((0, 0), (2.2, 10), (3.0, 12), (3.3, 0), (5.45, 0))(t)
    ch["heel_R"] = C((0, 0), (3.2, 0), (3.6, 10), (4.3, 6), (5.45, 0))(t)
    by = C((0, 0), (2.2, 34), (2.95, 40), (3.15, 20), (3.42, -60), (3.65, -75), (3.95, -60), (4.6, -16),
           (5.1, 4), (5.45, 0))
    bp = C((0, 0), (2.2, 22), (2.95, 26), (3.35, 4), (3.65, -2), (4.4, 2), (5.45, 0))
    ch["tail"] = tail_wave(t, by, bp, delay=0.035)
    return ch


def clip_lane_charge(t):
    """Telegraph 0-2.8: crouch, ram posture, right foot paws twice; active 2.8-3.9: explosive lunge, two strides
    (body +2.6 m forward), brake; recovery 3.9-5.9: steps back to the mark, settle."""
    D = 5.9
    ch = idle_channels(t, 5.0, amp=0.25)
    surge = C((0, 0), (2.75, 0.18), (2.95, 0.05), (3.25, -1.05), (3.6, -2.2), (3.9, -2.55), (4.3, -2.6),
              (5.1, -1.0), (5.6, -0.1), (5.9, 0))
    ch.update({
        "py": surge(t),
        "pz": C((0, 0), (1.0, -0.26), (2.75, -0.30), (3.2, -0.16), (3.6, -0.20), (3.9, -0.14), (4.6, -0.05),
                (5.9, 0))(t),
        "ppitch": C((0, 0), (1.0, -7), (2.75, -8), (3.3, -10), (3.85, 6), (4.3, 2), (5.9, 0))(t),
        "npitch": C((0, 0), (1.0, -18), (2.75, -20), (3.3, -14), (3.85, 10), (4.5, 2), (5.9, 0))(t),
        "hpitch": C((0, 0), (1.0, -6), (2.75, -8), (3.85, 6), (5.9, 0))(t),
        "nyaw": 2.0 * math.sin(2 * math.pi * 1.2 * t) * float(1 - ss((t - 2.6) / 0.2)),
        "jaw": C((0, 1), (0.9, 6), (1.0, 1), (1.8, 6), (1.9, 1), (2.75, 3), (3.1, 24), (3.8, 20), (4.2, 2), (5.9, 1))(t),
        "breath": C((0, 0), (0.85, 0.05), (1.0, -0.01), (1.75, 0.05), (1.9, -0.01), (2.75, 0.04), (5.9, 0))(t),
        "arm_pitch": C((0, 0), (2.75, 10), (3.2, -12), (4.0, -6), (5.9, 0))(t),
        "fingers": C((0, 4), (3.0, 16), (4.4, 6), (5.9, 4))(t),
    })
    # paw: right foot scrapes backward twice during the telegraph
    pawz = 0.0
    pawy = 0.0
    for t0 in (0.55, 1.45):
        x = (t - t0) / 0.6
        if 0 <= x <= 1:
            pawz = 0.20 * math.sin(math.pi * min(1, x * 1.6)) * (x < 0.62)
            pawy = 0.45 * (ss(x / 0.4) - ss((x - 0.55) / 0.45))
    # charge strides in the body frame: feet must cover the surge (py) -> placements along -Y
    stL = Steps("L", start=(0, 0), plan=[(2.82, 3.15, (0, -1.15), 0.34), (3.45, 3.80, (0, -2.55), 0.30),
                                         (4.45, 4.95, (0, -1.25), 0.24), (5.2, 5.65, (0, 0.0), 0.20)])
    stR = Steps("R", start=(0, 0), plan=[(3.05, 3.42, (0, -2.25), 0.36), (3.8, 4.15, (0, -2.6), 0.20),
                                         (4.8, 5.25, (0, -0.95), 0.24), (5.45, 5.85, (0, 0.0), 0.20)])
    for s, st in (("L", stL), ("R", stR)):
        off, lift, sw = st.at(t)
        p = planted(s, off[0], off[1]) + np.array([0, 0, lift])
        ch[f"contact_{s}"] = not sw
        if s == "R":
            p = p + np.array([0, -pawy * 0.0 + pawy - 0.15 * pawz, pawz])
            if any(0 <= (t - t0) / 0.6 <= 1 for t0 in (0.55, 1.45)):
                ch["contact_R"] = False          # pawing scrape: deliberate drag, not a planted foot
        ch[f"ball_{s}"] = p
        ch[f"heel_{s}"] = 18.0 if sw else (10.0 if (s == "R" and pawz > 0.01) else 0.0)
        ch[f"curl_{s}"] = 22.0 if sw else 0.0
    by = C((0, 0), (2.75, 4), (3.3, -6), (3.9, 8), (4.6, -4), (5.9, 0))
    bp = C((0, 0), (1.0, 14), (2.75, 18), (3.3, 6), (3.9, -6), (4.8, 2), (5.9, 0))
    ch["tail"] = tail_wave(t, by, bp, delay=0.05)
    return ch


def clip_stomp_waves(t):
    """Telegraph 0-3.2: rears up on the left leg, right leg raised high; wave_1 3.2 right stomp, wave_2 4.1 left
    stomp; recovery to 6.9."""
    D = 6.9
    ch = idle_channels(t, 5.0, amp=0.25)
    rear = C((0, 0), (1.4, 0.7), (2.9, 1.0), (3.12, 0.95), (3.22, 0.0), (3.4, -0.25), (3.75, 0.45), (4.05, 0.5),
             (4.12, -0.05), (4.3, -0.3), (5.0, -0.1), (6.0, 0), (6.9, 0))
    ch.update({
        "ppitch": 14.0 * rear(t),
        "pz": 0.10 * max(rear(t), 0) - 0.16 * max(-rear(t), 0) * 1.5,
        "px": C((0, 0), (1.4, 0.16), (2.9, 0.20), (3.25, 0.0), (3.6, -0.14), (4.05, -0.16), (4.2, 0.0), (6.9, 0))(t),
        "proll": C((0, 0), (1.4, 5), (2.9, 6), (3.25, 0), (3.6, -5), (4.05, -6), (4.2, 0), (6.9, 0))(t),
        "spitch": 8.0 * rear(t),
        "npitch": 14.0 * rear(t) + C((0, 0), (3.2, 0), (3.3, -8), (4.1, 0), (4.2, -8), (4.6, 0), (6.9, 0))(t),
        "hpitch": 6.0 * rear(t),
        "jaw": C((0, 1), (1.4, 10), (2.9, 30), (3.2, 34), (3.3, 10), (4.1, 26), (4.25, 8), (5.0, 3), (6.9, 1))(t),
        "breath": C((0, 0), (2.9, 0.06), (3.3, -0.01), (4.1, 0.05), (4.3, -0.01), (5.5, 0.04), (6.2, 0.0), (6.9, 0))(t),
        "arm_pitch": C((0, 0), (1.4, -16), (2.9, -24), (3.25, 6), (3.75, -18), (4.15, 6), (5.0, 0), (6.9, 0))(t),
        "fingers": C((0, 4), (2.9, -14), (3.25, 14), (4.15, 14), (5.5, 4))(t),
        "blink": C((0, 0), (3.18, 0), (3.24, 0.8), (3.4, 0), (4.08, 0), (4.14, 0.8), (4.3, 0), (6.9, 0))(t),
    })
    # right leg lifted high then stomps at 3.2; left leg lifted 3.35-4.1, stomps at 4.1
    rz = C((0, 0), (0.6, 0), (1.6, 0.85), (2.9, 1.0), (3.05, 0.9), (3.2, 0.0), (6.9, 0))(t)
    ry = C((0, 0), (0.6, 0), (1.6, -0.35), (2.9, -0.40), (3.2, -0.25), (6.9, -0.25))(t)
    lz = C((0, 0), (3.3, 0), (3.75, 0.62), (3.95, 0.66), (4.1, 0.0), (6.9, 0))(t)
    ly = C((0, 0), (3.3, 0), (3.75, -0.25), (4.1, -0.32), (5.7, -0.32), (6.25, 0.0), (6.9, 0))(t)
    ry2 = C((0, 0), (5.0, 0), (5.6, 1.0), (6.9, 1.0))(t)
    ch["ball_R"] = planted("R", 0.0, ry * (1 - ry2)) + np.array([0, 0, 1.0 * rz])
    ch["ball_L"] = planted("L", 0.0, ly) + np.array([0, 0, lz])
    lift_R = 0.0 + rz
    ch["heel_R"] = 30.0 * min(1.0, lift_R * 1.5)
    ch["curl_R"] = 26.0 * min(1.0, lift_R * 1.5)
    ch["heel_L"] = 30.0 * min(1.0, lz * 1.5)
    ch["curl_L"] = 26.0 * min(1.0, lz * 1.5)
    # recovery steps back to the mark: right 5.0-5.6, left 5.7-6.25 (lifted, never dragged)
    ch["contact_L"] = lz < 1e-3
    ch["contact_R"] = rz < 1e-3
    if 5.0 < t < 5.6:
        s = (t - 5.0) / 0.6
        ch["ball_R"] = ch["ball_R"] + np.array([0, 0, 0.2 * math.sin(math.pi * s)])
        ch["heel_R"] = 14.0
        ch["contact_R"] = False
    if 5.7 < t < 6.25:
        s = (t - 5.7) / 0.55
        ch["ball_L"] = ch["ball_L"] + np.array([0, 0, 0.2 * math.sin(math.pi * s)])
        ch["heel_L"] = 14.0
        ch["contact_L"] = False
    by = C((0, 0), (2.9, 6), (3.3, -10), (3.8, 8), (4.25, -12), (5.0, 4), (6.9, 0))
    bp = C((0, 0), (1.4, -6), (2.9, -10), (3.25, 14), (3.6, -4), (4.15, 14), (4.6, -2), (5.5, 2), (6.9, 0))
    ch["tail"] = tail_wave(t, by, bp, delay=0.045)
    return ch


CLIPS = {
    "lf_boss_idle": (5.0, True, clip_idle, {}),
    "lf_boss_walk": (WALK_D, True, clip_walk, {}),
    "lf_boss_turn_left": (TURN_D, False, lambda t: clip_turn(t, +1), {}),
    "lf_boss_turn_right": (TURN_D, False, lambda t: clip_turn(t, -1), {}),
    "lf_boss_awaken": (4.2, False, clip_awaken, {}),
    "lf_boss_phase_roar": (2.8, False, clip_phase_roar, {}),
    "lf_boss_hit": (0.55, False, clip_hit, {}),
    "lf_boss_stagger": (1.8, False, clip_stagger, {}),
    "lf_boss_death": (5.2, False, clip_death, {"ground_contact": 3.7}),
    "lf_boss_jaw_arc": (4.25, False, clip_jaw_arc, {"telegraph_begin": 0.0, "active_begin": 2.4, "active_end": 2.85,
                                                     "recovery_end": 4.25}),
    "lf_boss_tail_sweep": (5.45, False, clip_tail_sweep, {"telegraph_begin": 0.0, "active_begin": 3.0,
                                                           "active_end": 3.65, "recovery_end": 5.45}),
    "lf_boss_lane_charge": (5.9, False, clip_lane_charge, {"telegraph_begin": 0.0, "active_begin": 2.8,
                                                            "active_end": 3.9, "recovery_end": 5.9}),
    "lf_boss_stomp_waves": (6.9, False, clip_stomp_waves, {"telegraph_begin": 0.0, "wave_1_begin": 3.2,
                                                            "wave_1_end": 3.6, "wave_2_begin": 4.1, "wave_2_end": 4.5,
                                                            "recovery_end": 6.9}),
}


# ------------------------------------------------------------------------------------ art/05 key-pose fit
OVERRIDES = {}
WINDOWS = {"turn_anticipation": (0.0, 0.55), "turn_planted": (0.55, 1.3), "bite_windup": (0.7, 2.42),
           "bite_strike": (2.42, 3.25), "roar": (0.55, 2.3), "tail_coil": (1.2, 3.06), "tail_release": (3.06, 4.5),
           "death_rest": (3.3, 5.2)}
SCALARS = ["pz", "ppitch", "pyaw", "proll", "spitch", "syaw", "npitch", "nyaw", "hpitch", "jaw", "heel_L", "heel_R",
           "arm_pitch"]


def load_keypose_fit(path):
    import json
    import os
    global WALK_SPEED, WALK_LIFT, WALK_PZ, WALK_PITCH
    if not os.path.exists(path):
        return False
    data = json.load(open(path))
    OVERRIDES.clear()
    walk = [r for k, r in data.items() if k.startswith("walk")]
    if walk:
        con = [r["params"] for r in walk if "contact" in r["panel"]]
        pas = [r["params"] for r in walk if "passing" in r["panel"]]
        if con:
            step = float(np.mean([abs(p["bLy"] - p["bRy"]) for p in con]))
            step = float(np.clip(step, 1.2, 2.6))
            WALK_SPEED = round(step / (WALK_D * WALK_DUTY), 3)
            WALK_PZ = float(np.clip(np.mean([p["pz"] for p in con]), -0.4, 0.05))
            WALK_PITCH = float(np.clip(np.mean([p["ppitch"] for p in con + pas]), -8, 8))
        if pas:
            WALK_LIFT = float(np.clip(max(max(p["bLz"], p["bRz"]) for p in pas) - 0.17, 0.25, 0.75))
    for panel, r in data.items():
        if panel in WINDOWS:
            a, b = WINDOWS[panel]
            OVERRIDES.setdefault(r["clip"], []).append((float(r["time"]), a, b, r["params"]))
    return True


def _window(t, a, tk, b):
    if t < a or t > b:
        return 0.0
    if t <= tk:
        return float(ss((t - a) / max(tk - a, 1e-6)))
    return 1.0 - float(ss((t - tk) / max(b - tk, 1e-6)))


def with_overrides(cid, fn):
    """Wrap a clip function: blend the fitted art/05 pose in around its key time (additive deltas vs the base
    pose at that time); feet move with a lifted step in the first/last 40 % of the window."""
    if cid not in OVERRIDES:
        return fn
    base_cache = {}

    def g(t):
        ch = fn(t)
        for (tk, a, b, prm) in OVERRIDES[cid]:
            w = _window(t, a, tk, b)
            if w <= 0:
                continue
            if tk not in base_cache:
                base_cache[tk] = fn(tk)
            b0 = base_cache[tk]
            for k in SCALARS:
                if k in prm:
                    tgt = prm[k]
                    if k == "pz":
                        tgt = min(tgt, -0.02)          # legs must keep reaching the planted feet (no overreach)
                    ch[k] = ch.get(k, 0.0) + (tgt - b0.get(k, 0.0)) * w
            tail = ch.get("tail", [(0.0, 0.0)] * 12)
            tb = b0.get("tail", [(0.0, 0.0)] * 12)
            ch["tail"] = [(tail[i][0] + (prm["ty0"] + prm["ty1"] * i / 11.0 - tb[i][0]) * w,
                           tail[i][1] + (prm["tp0"] + prm["tp1"] * i / 11.0 - tb[i][1]) * w) for i in range(12)]
            # feet: step to the painted placement (y), lifted, then hold; step back in the out window
            # (turn clips keep their own world-planted stepping: a held local offset would slide in the yawing frame)
            for s_, key in ((() if cid.startswith("lf_boss_turn") else (("L", "bLy"), ("R", "bRy")))):
                dy = float(np.clip(prm[key] - float(np.asarray(b0[f"ball_{s_}"])[1]), -0.75, 0.75))
                dz_t = max(prm["b" + s_ + "z"] - 0.17, 0.0)
                if abs(dy) < 0.05 and dz_t < 0.05:
                    continue
                if t <= tk:
                    x = (t - a) / max(tk - a, 1e-6)
                    m = float(ss(x / 0.4)) if x < 0.4 else 1.0
                    lift = 0.22 * math.sin(math.pi * min(1.0, x / 0.4)) if x < 0.4 else 0.0
                    swing = x < 0.4
                else:
                    x = (t - tk) / max(b - tk, 1e-6)
                    m = 1.0 - (float(ss((x - 0.6) / 0.4)) if x > 0.6 else 0.0)
                    lift = 0.22 * math.sin(math.pi * (x - 0.6) / 0.4) if x > 0.6 else 0.0
                    swing = x > 0.6
                # a painted raised foot (dz) is reached at the key time and released after it
                hold_lift = dz_t * w if dz_t >= 0.05 else 0.0
                p = np.asarray(ch[f"ball_{s_}"], float).copy()
                p[1] += dy * m
                p[2] += lift + hold_lift
                ch[f"ball_{s_}"] = p
                if swing or hold_lift > 0.01:
                    ch[f"contact_{s_}"] = False
        return ch
    return g


def frames(rig, clip_id):
    """Sample a clip at 60 fps: returns (keys per frame, foot world points per frame, node yaw, overreach)."""
    D, loop, fn, _m = CLIPS[clip_id]
    fn = with_overrides(clip_id, fn)
    n = int(round(D * FPS))
    out, feet, yaws = [], [], []
    over = 0.0
    for f in range(n + 1):
        t = f / FPS
        if loop and f == n:
            t = 0.0
        ch = fn(t)
        over = max(over, rig.build(ch))
        out.append(rig.keyframe())
        fp = rig.foot_points()
        yaws.append(ch.get("_node_yaw", 0.0))
        fp["contact"] = {s: bool(ch.get(f"contact_{s}", True)) for s in "LR"}
        feet.append(fp)
    return out, feet, yaws, over


def foot_slip(clip_id, feet, yaws, ground_speed=0.0):
    """Max horizontal drift (m) of each ball while in ground contact (z < 3 cm), in the world frame
    (node yaw for turns, root travel at ground_speed for the walk)."""
    res = {}
    for s in "LR":
        best = 0.0
        anchor = None
        for f, (fp, yaw) in enumerate(zip(feet, yaws)):
            p = PO.qmat((0, 0, 1), yaw) @ fp[s]["ball"]
            p = p + np.array([0.0, -ground_speed * f / FPS, 0.0])
            if p[2] < 0.03 + 0.17 and fp.get("contact", {}).get(s, True):   # planted: ball joint 0.17 m up
                if anchor is None:
                    anchor = p.copy()
                best = max(best, float(np.linalg.norm((p - anchor)[:2])))
            else:
                anchor = None
        res[s] = round(best, 4)
    return res
