"""Clip library for the civilian and soldier groups (animation_manifest ids/durations).

A frame is described by a *spec* (pelvis offset/rotation, spine/neck FK, IK feet, FK or IK arms,
fingers, props); specs are keyframed with smooth interpolation, layered with breathing/gait and
solved by humans_anim.Rig.  Feet are always IK: planted feet never move in world space (in-place
clips subtract the root path, so stance feet slide backward at exactly the root speed).
"""
import math

import numpy as np

import humans_anim as A
from humans_anim import env, lerp, rad, sm, ss, unit, axis_angle, rot_xyz

FPS = A.FPS

CIVILIAN = [("lf_civilian_cage_sit", 5.4, True), ("lf_civilian_cage_stand", 4.8, True),
            ("lf_civilian_cage_wait", 6.1, True), ("lf_civilian_react", 1.4, False),
            ("lf_civilian_stand_up", 2.2, False), ("lf_civilian_exit", 2.8, False),
            ("lf_civilian_follow", 1.1, True), ("lf_civilian_follow_tired", 1.25, True),
            ("lf_civilian_wait", 4.4, True), ("lf_civilian_look_back", 1.6, False),
            ("lf_civilian_arrive", 2.6, False), ("lf_civilian_thank", 2.3, False)]
SOLDIER = [("lf_soldier_idle", 4.0, True), ("lf_soldier_walk", 1.0, True), ("lf_soldier_jog", 0.7, True),
           ("lf_soldier_guard", 3.2, True), ("lf_soldier_attack", 1.2, False), ("lf_soldier_hit", 0.5, False),
           ("lf_soldier_death", 2.0, False), ("lf_soldier_unlock", 2.4, False), ("lf_soldier_help", 2.8, False),
           ("lf_soldier_salute", 1.8, False)]
MARKERS = {"lf_soldier_attack": {"weapon_contact": 0.65}, "lf_soldier_unlock": {"latch_release": 1.6}}
SEAT_H = 0.45
SOCKET = np.array([0.0, -0.46, 1.25])      # cage latch socket (chest height, in front)


# --------------------------------------------------------------------------- spec helpers

def neutral(R, w=0.0):
    """Relaxed standing spec; w>0 = weight on the left leg (contrapposto)."""
    sp = dict(hip=np.array([0.025 * w, 0.0, -0.014 - 0.008 * abs(w)]), pel=np.array([2.0, 3.0 * w, 0.0]),
              sp=np.array([1.0, -3.5 * w, 0.0]), nk=np.array([-2.0, 0.5 * w, 0.0]), jaw=0.0,
              feet={}, arm={}, clav={}, fing={})
    for S_, s in (("Left", 1.0), ("Right", -1.0)):
        a = R.ankle0[S_]
        sp["feet"][S_] = dict(ank=a.copy(), fwd=foot_fwd(S_, 7.0), up=np.array([0, 0, 1.0]), toe=0.0)
        sp["arm"][S_] = dict(fk=np.array([5.0, -9.0, 0.0, 12.0, 4.0, 0.0]))
        sp["clav"][S_] = np.array([0.0, 0.0])
        sp["fing"][S_] = np.array([0.22, 0.15, 0.18])
    return sp


def foot_fwd(S_, toe_out):
    s = 1.0 if S_ == "Left" else -1.0
    return np.array([s * math.sin(rad(toe_out)), -math.cos(rad(toe_out)), 0.0])


def copy(sp):
    out = {}
    for k, v in sp.items():
        if isinstance(v, dict):
            out[k] = {kk: (dict((a, np.array(b, float) if not isinstance(b, (str, bool)) else b)
                                for a, b in vv.items()) if isinstance(vv, dict) else np.array(vv, float))
                      for kk, vv in v.items()}
        elif isinstance(v, (str, bool)) or v is None:
            out[k] = v
        else:
            out[k] = np.array(v, float)
    return out


IK_KEYS = ("wrist", "elbow", "palm", "hfwd")


def _arm_mix(a, b, w):
    wa = a.get("w_ik", 1.0 if "wrist" in a else 0.0)
    wb = b.get("w_ik", 1.0 if "wrist" in b else 0.0)
    out = {"w_ik": lerp(float(wa), float(wb), w)}
    if "fk" in a and "fk" in b:
        out["fk"] = lerp(np.asarray(a["fk"], float), np.asarray(b["fk"], float), w)
    elif "fk" in a or "fk" in b:
        out["fk"] = np.asarray(a.get("fk", b.get("fk")), float)
    for k in IK_KEYS:
        if k in a and k in b and a[k] is not None and b[k] is not None:
            v = lerp(np.asarray(a[k], float), np.asarray(b[k], float), w)
            out[k] = v
        elif k in a or k in b:
            out[k] = a.get(k, b.get(k))
    return out


def mix(a, b, w):
    """Interpolate two specs (same structure); arm specs blend FK<->IK smoothly."""
    if isinstance(a, dict) and isinstance(b, dict) and ("fk" in a or "wrist" in a) and ("fk" in b or "wrist" in b):
        return _arm_mix(a, b, w)
    if isinstance(a, dict):
        return {k: (mix(a[k], b[k], w) if k in b else a[k]) for k in a}
    if isinstance(a, (str, bool)) or a is None:
        return a if w < 0.5 else b
    return lerp(np.asarray(a, float), np.asarray(b, float), w)


def keyed(t, keys):
    """keys: [(time, spec)] -> smoothly interpolated spec."""
    if t <= keys[0][0]:
        return copy(keys[0][1])
    for i in range(len(keys) - 1):
        t0, a = keys[i]
        t1, b = keys[i + 1]
        if t0 <= t <= t1:
            return mix(a, b, sm((t - t0) / max(t1 - t0, 1e-9)))
    return copy(keys[-1][1])


def slerp_m(A_, B_, w):
    from mathutils import Matrix
    qa = Matrix(A_.tolist()).to_quaternion()
    qb = Matrix(B_.tolist()).to_quaternion()
    if qa.dot(qb) < 0:
        qb = -qb
    return np.array(qa.slerp(qb, w).to_matrix())


def arm_fk(R, P, S_, v):
    flex, abd, tw, el, wf, wd = v
    s = 1.0 if S_ == "Left" else -1.0
    R.fk(P, f"{S_}UpperArm", x=flex, z=s * abd, y=s * tw)
    R.fk(P, f"{S_}LowerArm", x=el, y=s * 0.0)
    R.fk(P, f"{S_}Hand", x=wf, z=s * wd)


def solve(R, sp, props=None):
    """spec -> Solver pose dict (bone -> rotation) with IK limbs."""
    P = {}
    R.pelvis(P, pos=sp["hip"], fwd=sp["pel"][0], side=sp["pel"][1], yaw=sp["pel"][2])
    R.spine(P, *sp["sp"])
    R.neck_head(P, *sp["nk"])
    R.fk(P, "Jaw", x=-float(sp.get("jaw", 0.0)))
    for S_ in ("Left", "Right"):
        c = sp["clav"][S_]
        s = 1.0 if S_ == "Left" else -1.0
        P[f"{S_}Shoulder"] = ("local", rot_xyz(float(c[1]), 0.0, s * float(c[0])))
        a = sp["arm"][S_]
        w_ik = float(a.get("w_ik", 1.0 if "wrist" in a else 0.0))
        if w_ik <= 1e-3 or "wrist" not in a:
            arm_fk(R, P, S_, a["fk"])
        elif w_ik >= 0.999 or "fk" not in a:
            R.arm_ik(P, S_, a["wrist"], a["elbow"], palm=a.get("palm"), hand_fwd=a.get("hfwd"),
                     clav=(float(c[0]), float(c[1])))
        else:
            arm_fk(R, P, S_, a["fk"])
            Mfk = R.S.world(P)
            Pk = dict(P)
            R.arm_ik(Pk, S_, a["wrist"], a["elbow"], palm=a.get("palm"), hand_fwd=a.get("hfwd"),
                     clav=(float(c[0]), float(c[1])))
            Mik = R.S.world(Pk)
            for bn in (f"{S_}UpperArm", f"{S_}LowerArm", f"{S_}Hand"):
                P[bn] = slerp_m(Mfk[bn][:3, :3], Mik[bn][:3, :3], w_ik)
        f = sp["fing"][S_]
        R.fingers(P, S_, curl=float(f[0]), thumb=float(f[1]), index=float(f[2]))
    for S_ in ("Left", "Right"):
        ft = sp["feet"][S_]
        R.leg_ik(P, S_, ft["ank"], ft["fwd"], ft["up"], float(ft["toe"]), ft.get("knee"))
    if props:
        props(P)
    return P


# --------------------------------------------------------------------------- layers

def breathe(sp, t, rate=0.25, amp=1.0):
    ph = math.sin(2 * math.pi * rate * t)
    sp["sp"] = sp["sp"] + np.array([-0.8 * amp * ph, 0, 0])
    sp["nk"] = sp["nk"] + np.array([0.5 * amp * ph, 0, 0])
    for S_ in ("Left", "Right"):
        sp["clav"][S_] = sp["clav"][S_] + np.array([0.9 * amp * ph, 0.0])
    sp["hip"] = sp["hip"] + np.array([0, 0, 0.0015 * amp * ph])
    return sp


def periodic(t, T, n=1, phase=0.0):
    return math.sin(2 * math.pi * (n * t / T + phase))


# --------------------------------------------------------------------------- loops: walking

def gait_spec(R, G, t, style):
    """Walking/jogging spec from an analytic Gait at time t (in place)."""
    sp = neutral(R)
    T = G.T
    ph = t / T
    c = math.cos(2 * math.pi * ph)
    s2 = math.sin(2 * math.pi * ph)
    st = style
    for S_ in ("Left", "Right"):
        ank, fwd, up, toe, _ = G.foot(S_, t)
        sp["feet"][S_] = dict(ank=ank, fwd=fwd, up=up, toe=toe, knee=unit(fwd + np.array([0, 0, 0.02])))
    yaw = -st["pel_yaw"] * c
    roll = st["pel_roll"] * s2
    sway = st["sway"] * s2
    sp["pel"] = np.array([st["lean"] * 0.5, roll, yaw])
    sp["sp"] = np.array([st["lean"], -roll * 0.7, -yaw * 1.9 + st.get("twist0", 0.0)])
    sp["nk"] = np.array([-st["lean"] * 0.8 + st.get("head", 0.0), 0.0, yaw * 0.6])
    # arms swing opposite to the legs
    for S_, sgn in (("Left", -1.0), ("Right", 1.0)):
        sw = sgn * c   # +1 = forward
        flex = st["arm_base"] + st["arm_amp"] * sw
        el = st["el_base"] + st["el_amp"] * max(sw, 0.0) + 4.0 * max(-sw, 0)
        sp["arm"][S_] = dict(fk=np.array([flex, -st.get("arm_in", 10.0), 0.0, el, 6.0, 0.0]))
        sp["fing"][S_] = np.array(st.get("fing", (0.28, 0.2, 0.22)))
    sp["clav"]["Left"] = np.array([0.0, st["clav_fwd"] + 2.0 * c])
    sp["clav"]["Right"] = np.array([0.0, st["clav_fwd"] - 2.0 * c])
    sp["hip"] = np.array([sway, st.get("hip_y", 0.0), 0.0])
    sp["_gait"] = True
    return sp


def fit_pelvis_height(R, specs, bend=0.012, smooth_s=0.06, loop=True):
    """Lower the pelvis so no leg over-extends (natural bob: high mid-stance, low at contact)."""
    n = len(specs)
    hz = np.zeros(n)
    for i, sp in enumerate(specs):
        P = {}
        R.pelvis(P, pos=np.array([sp["hip"][0], sp["hip"][1], 0.0]), fwd=sp["pel"][0], side=sp["pel"][1],
                 yaw=sp["pel"][2])
        M = R.S.world(P)
        best = 9.0
        for S_ in ("Left", "Right"):
            hip = M[f"{S_}UpperLeg"][:3, 3]
            ank = sp["feet"][S_]["ank"]
            Lg = (R.L[S_]["thigh"] + R.L[S_]["shin"]) * 0.985
            dxy = np.linalg.norm((hip - ank)[:2])
            maxz = ank[2] + math.sqrt(max(Lg * Lg - dxy * dxy, 0.0))
            best = min(best, maxz - hip[2])
        hz[i] = best - bend
    k = max(1, int(smooth_s * FPS))
    if loop:
        ext = np.concatenate([hz[-k * 3:], hz, hz[:k * 3]])
        sm_ = np.convolve(ext, np.ones(2 * k + 1) / (2 * k + 1), mode="same")[k * 3:-k * 3]
    else:
        sm_ = hz
    sm_ = np.minimum(sm_, hz + 0.004)
    for i, sp in enumerate(specs):
        sp["hip"] = np.array([sp["hip"][0], sp["hip"][1], sm_[i]])
    return specs


STYLES = {
    "civ_walk": dict(lean=4.0, pel_yaw=5.0, pel_roll=3.0, sway=0.018, arm_base=4.0, arm_amp=15.0, el_base=12.0,
                     el_amp=14.0, clav_fwd=1.0, head=2.0),
    "civ_tired": dict(lean=11.0, pel_yaw=4.0, pel_roll=4.0, sway=0.024, arm_base=6.0, arm_amp=7.0, el_base=16.0,
                      el_amp=8.0, clav_fwd=6.0, head=10.0, fing=(0.35, 0.25, 0.3)),
    "sol_walk": dict(lean=5.0, pel_yaw=5.5, pel_roll=2.5, sway=0.016, arm_base=4.0, arm_amp=13.0, el_base=14.0,
                     el_amp=14.0, clav_fwd=0.0, head=3.0),
    "sol_jog": dict(lean=10.0, pel_yaw=7.0, pel_roll=3.0, sway=0.014, arm_base=8.0, arm_amp=26.0, el_base=70.0,
                    el_amp=14.0, clav_fwd=2.0, head=6.0, fing=(0.6, 0.5, 0.6)),
}


# --------------------------------------------------------------------------- footstep planner

class Planner:
    """World-space footsteps with heel-toe rolling; root path from the feet midpoint."""

    def __init__(self, R, dur, toe_out=7.0, lift=0.10, heel=12.0, toe=24.0):
        self.R = R
        self.dur = dur
        self.toe_out = toe_out
        self.lift = lift
        self.heel = heel
        self.toe = toe
        self.steps = {"Left": [], "Right": []}
        self.start = {S_: R.ankle0[S_].copy() for S_ in ("Left", "Right")}
        self.root = None

    def step(self, S_, t_lift, t_land, dy, dx=0.0):
        prev = self.steps[S_][-1][3] if self.steps[S_] else self.start[S_]
        land = prev + np.array([dx, dy, 0.0])
        self.steps[S_].append((t_lift, t_land, prev.copy(), land))
        return self

    def foot(self, S_, t):
        fwd = foot_fwd(S_, self.toe_out)
        cur = self.start[S_]
        last_land = -9.0
        for (t0, t1, p0, p1) in self.steps[S_]:
            if t < t0:
                # planted at cur; heel-off before lift
                return self._planted(S_, cur, t, last_land, t0, fwd)
            if t0 <= t <= t1:
                u = (t - t0) / (t1 - t0)
                e = sm(u)
                a0 = self._frame(p0, -self.toe * 0.8, fwd, 0.0, "ball")[0]     # heel-off end pose
                a1 = self._frame(p1, self.heel, fwd, 0.0, "heel")[0]          # heel-strike start pose
                pos = a0 * (1 - e) + a1 * e + np.array([0, 0, self.lift * math.sin(math.pi * u) ** 0.8])
                pitch = lerp(-self.toe * 0.8, self.heel, ss(u * 1.2))
                toe = self.toe * 0.8 * (1 - ss(u * 2.5))
                return self._frame(pos, pitch, fwd, toe, pivot=None)
            cur = p1
            last_land = t1
        return self._planted(S_, cur, t, last_land, 99.0, fwd)

    def _planted(self, S_, pos, t, t_land, t_lift, fwd):
        a = t - t_land
        b = t_lift - t
        pitch = 0.0
        pivot = None
        if 0 <= a < 0.14:
            pitch = self.heel * (1 - ss(a / 0.14))
            pivot = "heel"
        elif 0 <= b < 0.22:
            pitch = -self.toe * 0.8 * ss(1 - b / 0.22)
            pivot = "ball"
        return self._frame(pos, pitch, fwd, max(0.0, -pitch) * 0.95, pivot)

    def _frame(self, pos, pitch, fwd, toe, pivot):
        R = axis_angle(np.cross(fwd, (0, 0, 1)), pitch)
        hl = self.R.leg_len / 0.86
        if pivot == "heel":
            heel = -fwd * 0.062 * hl - np.array([0, 0, pos[2]])
            ank = pos + heel - R @ heel
        elif pivot == "ball":
            ballp = fwd * 0.135 * hl - np.array([0, 0, pos[2]])
            ank = pos + ballp - R @ ballp
        else:
            ank = pos.copy()
        return ank, R @ fwd, R @ np.array([0, 0, 1.0]), toe

    def build_root(self, sigma=0.22):
        ts = np.arange(0, self.dur + 1e-6, 1.0 / FPS)
        mid = []
        for t in ts:
            a = self.foot("Left", t)[0]
            b = self.foot("Right", t)[0]
            mid.append(0.5 * (a + b))
        mid = np.array(mid)
        y = mid[:, 1] - 0.5 * (self.start["Left"][1] + self.start["Right"][1])
        k = int(sigma * FPS)
        pad = np.concatenate([np.full(k * 3, y[0]), y, np.full(k * 3, y[-1])])
        g = np.exp(-0.5 * (np.arange(-3 * k, 3 * k + 1) / max(k, 1)) ** 2)
        g /= g.sum()
        ys = np.convolve(pad, g, mode="same")[k * 3:-k * 3]
        self.root = ys
        self.ts = ts
        return ys

    def root_at(self, t):
        return float(np.interp(t, self.ts, self.root))

    def feet_spec(self, sp, t):
        ry = self.root_at(t)
        for S_ in ("Left", "Right"):
            ank, fwd, up, toe = self.foot(S_, t)
            ank = ank - np.array([0, ry, 0])
            sp["feet"][S_] = dict(ank=ank, fwd=fwd, up=up, toe=toe, knee=unit(fwd + np.array([0, 0, 0.02])))
        return ry


# --------------------------------------------------------------------------- props (soldiers)

def hand_matrix(R, P, S_):
    M = R.S.world(P)
    return M[f"{S_}Hand"]


class Role:
    """Weapon handling per squad member."""

    def __init__(self, role):
        self.role = role            # civilian | captain | scout | shield_guard
        self.free = {"captain": "Left", "scout": "Right", "shield_guard": "Right"}.get(role, "Right")
        self.weapon_hand = {"captain": "Right", "scout": "Left", "shield_guard": "Right"}.get(role)


# --------------------------------------------------------------------------- civilian clips

def civ_seated(R, lean=34.0, look=-26.0):
    sp = neutral(R)
    for S_, s in (("Left", 1.0), ("Right", -1.0)):
        a = R.ankle0[S_].copy()
        a[0] += s * 0.03
        a[1] -= 0.06
        sp["feet"][S_] = dict(ank=a, fwd=foot_fwd(S_, 10.0), up=np.array([0, 0, 1.0]), toe=0.0,
                              knee=unit(np.array([s * 0.15, -1.0, 0.25])))
    hz = SEAT_H + 0.105 - R.hips0[2]
    sp["hip"] = np.array([0.0, 0.40, hz])
    sp["pel"] = np.array([lean * 0.35, 0.0, 0.0])
    sp["sp"] = np.array([lean * 0.65, 0.0, 0.0])
    sp["nk"] = np.array([-look * 0.0 + 22.0, 0.0, 0.0])
    for S_, s in (("Left", 1.0), ("Right", -1.0)):
        knee = np.array([s * 0.13, -0.08, SEAT_H + 0.08])
        sp["arm"][S_] = dict(wrist=knee + np.array([-s * 0.05, -0.06, 0.02]),
                             elbow=np.array([s * 0.6, 0.6, -0.2]), palm=np.array([-s * 0.4, 0.2, -0.9]),
                             hfwd=np.array([0, -0.4, -1.0]))
        sp["clav"][S_] = np.array([-2.0, 8.0])
        sp["fing"][S_] = np.array([0.35, 0.25, 0.3])
    return sp


def clip_cage_sit(R, t, T):
    sp = civ_seated(R)
    sp = breathe(sp, t, rate=1.0 / (T / 2), amp=1.6)
    sp["nk"] = sp["nk"] + np.array([3.0 * periodic(t, T, 1, 0.1), 2.5 * periodic(t, T, 1, 0.3), 6.0 * periodic(t, T, 1)])
    sp["sp"] = sp["sp"] + np.array([1.5 * periodic(t, T, 1, 0.6), 0, 1.5 * periodic(t, T, 1, 0.2)])
    return sp


def clip_cage_stand(R, t, T):
    w = 0.65 * periodic(t, T, 1)
    sp = neutral(R, w)
    sp = breathe(sp, t, rate=2.0 / T, amp=1.2)
    sp["nk"] = sp["nk"] + np.array([4.0 + 3.0 * periodic(t, T, 1, 0.25), 0, 14.0 * periodic(t, T, 1, 0.1)])
    sp["sp"] = sp["sp"] + np.array([3.0, 0, 3.0 * periodic(t, T, 1, 0.15)])
    for S_ in ("Left", "Right"):
        sp["clav"][S_] = sp["clav"][S_] + np.array([-2.0, 4.0])
    return sp


def clip_cage_wait(R, t, T):
    w = 0.6 * periodic(t, T, 2, 0.1)
    sp = neutral(R, w)
    sp = breathe(sp, t, rate=3.0 / T, amp=1.0)
    # arms wrapped around the body (cold, anxious), glancing toward the door
    for S_, s in (("Left", 1.0), ("Right", -1.0)):
        sp["arm"][S_] = dict(fk=np.array([38.0, -18.0, s * 0.0, 105.0 if S_ == "Left" else 98.0, 10.0, 0.0]))
        sp["fing"][S_] = np.array([0.45, 0.3, 0.4])
        sp["clav"][S_] = np.array([3.0, 9.0])
    look = 24.0 * math.sin(2 * math.pi * (t / T)) + 8.0 * math.sin(2 * math.pi * (3 * t / T + 0.2))
    sp["nk"] = sp["nk"] + np.array([5.0, 0, look])
    sp["sp"] = sp["sp"] + np.array([5.0, 0, look * 0.2])
    return sp


def clip_react(R, t, T):
    base = neutral(R, 0.3)
    startle = copy(base)
    startle["hip"] = startle["hip"] + np.array([0, 0.03, 0.006])
    startle["sp"] = np.array([-6.0, -1.0, 0.0])
    startle["nk"] = np.array([-8.0, 0, 0])
    for S_ in ("Left", "Right"):
        startle["arm"][S_] = dict(fk=np.array([30.0, -6.0, 0.0, 70.0, -10.0, 0.0]))
        startle["clav"][S_] = np.array([8.0, 4.0])
        startle["fing"][S_] = np.array([0.1, 0.1, 0.1])
    hope = copy(base)
    hope["sp"] = np.array([6.0, 0.0, 0.0])
    hope["nk"] = np.array([-4.0, 0, 0])
    hope["hip"] = hope["hip"] + np.array([0, -0.01, 0])
    for S_ in ("Left", "Right"):
        hope["arm"][S_] = dict(fk=np.array([22.0, -14.0, 0.0, 60.0, 0.0, 0.0]))
        hope["fing"][S_] = np.array([0.3, 0.2, 0.25])
    end = neutral(R, 0.0)
    return keyed(t, [(0.0, base), (0.22, startle), (0.55, startle), (0.95, hope), (1.4, end)])


def clip_stand_up(R, t, T):
    s0 = civ_seated(R)
    # 1: hands slide onto the knees, torso leans further forward
    s1 = civ_seated(R, lean=46.0)
    for S_, s in (("Left", 1.0), ("Right", -1.0)):
        kn = np.array([s * 0.12, -0.07, SEAT_H + 0.085])
        s1["arm"][S_] = dict(wrist=kn + np.array([0.0, 0.02, 0.06]), elbow=np.array([s * 0.8, 0.4, 0.0]),
                             palm=np.array([0, 0.2, -1.0]), hfwd=np.array([0, -1.0, -0.25]))
        s1["fing"][S_] = np.array([0.25, 0.2, 0.2])
    s1["nk"] = np.array([10.0, 0, 0])
    # 2: hips leave the seat, pushing on the knees (drawing panel 2)
    s2 = copy(s1)
    s2["hip"] = np.array([0.0, 0.16, -0.30])
    s2["pel"] = np.array([28.0, 0, 0])
    s2["sp"] = np.array([26.0, 0, 0])
    s2["nk"] = np.array([2.0, 0, 0])
    for S_, s in (("Left", 1.0), ("Right", -1.0)):
        kn = np.array([s * 0.11, -0.04, 0.50])
        s2["arm"][S_] = dict(wrist=kn + np.array([0.0, -0.01, 0.05]), elbow=np.array([s * 0.9, 0.3, 0.1]),
                             palm=np.array([0, 0.2, -1.0]), hfwd=np.array([0, -1.0, -0.2]))
    # 3: half-standing, hands on thighs, head lifting (panel 3)
    s3 = copy(s2)
    s3["hip"] = np.array([0.0, 0.07, -0.13])
    s3["pel"] = np.array([16.0, 0, 0])
    s3["sp"] = np.array([14.0, 0, 0])
    s3["nk"] = np.array([-14.0, 0, 0])
    for S_, s in (("Left", 1.0), ("Right", -1.0)):
        s3["arm"][S_] = dict(wrist=np.array([s * 0.15, -0.08, 0.66]), elbow=np.array([s * 0.9, 0.4, 0.1]),
                             palm=np.array([-s * 0.3, 0.3, -0.9]), hfwd=np.array([0, -0.6, -1.0]))
    # 4: upright, relieved, looking up (panel 4)
    s4 = neutral(R, 0.0)
    s4["nk"] = np.array([-16.0, 0, 0])
    s4["sp"] = np.array([-3.0, 0, 0])
    for S_ in ("Left", "Right"):
        s4["clav"][S_] = np.array([3.0, -2.0])
    s5 = neutral(R, 0.0)
    s5["nk"] = np.array([-8.0, 0, 0])
    sp = keyed(t, [(0.0, s0), (0.55, s1), (1.05, s2), (1.5, s3), (1.95, s4), (2.2, s5)])
    return sp


def clip_look_back(R, t, T):
    a = neutral(R, 0.2)
    b = copy(a)
    b["sp"] = b["sp"] + np.array([0, 0, 28.0])
    b["nk"] = b["nk"] + np.array([0, 2.0, 48.0])
    b["pel"] = b["pel"] + np.array([0, 0, 8.0])
    b["arm"]["Right"] = dict(fk=np.array([10.0, -6.0, 0.0, 20.0, 4.0, 0.0]))
    return keyed(t, [(0.0, a), (0.55, b), (1.0, b), (1.6, neutral(R, 0.0))])


def clip_thank(R, t, T):
    a = neutral(R, 0.0)
    b = copy(a)
    chest = R.S.world({})["Chest"][:3, 3]
    b["arm"]["Right"] = dict(wrist=chest + np.array([0.07, -0.20, 0.10]), elbow=np.array([-0.8, 0.2, -0.6]),
                             palm=np.array([0.2, 1.0, 0.1]), hfwd=np.array([0.6, -0.2, 0.75]))
    b["fing"]["Right"] = np.array([0.08, 0.1, 0.05])
    b["clav"]["Right"] = np.array([2.0, 6.0])
    c = copy(b)
    c["sp"] = c["sp"] + np.array([9.0, 0, 0])
    c["nk"] = c["nk"] + np.array([14.0, 0, 0])
    c["pel"] = c["pel"] + np.array([3.0, 0, 0])
    return keyed(t, [(0.0, a), (0.55, b), (0.95, c), (1.55, c), (1.85, b), (2.3, neutral(R, 0.0))])


def clip_wait(R, t, T):
    w = 0.7 * periodic(t, T, 1, 0.0)
    sp = neutral(R, w)
    sp = breathe(sp, t, rate=2.0 / T, amp=1.0)
    look = 20.0 * periodic(t, T, 1, 0.2) + 6.0 * periodic(t, T, 3)
    sp["nk"] = sp["nk"] + np.array([1.0, 0, look])
    sp["sp"] = sp["sp"] + np.array([0, 0, look * 0.25])
    # one hand rubbing the other forearm, then dropping
    sp["arm"]["Left"] = dict(fk=np.array([18.0, -16.0, 0.0, 62.0 + 6.0 * periodic(t, T, 4), 8.0, 0.0]))
    sp["arm"]["Right"] = dict(fk=np.array([14.0, -20.0, 0.0, 70.0 + 8.0 * periodic(t, T, 4, 0.3), 6.0, 0.0]))
    return sp


def locomotion_specs(R, G, style, n, dur):
    specs = [gait_spec(R, G, i * dur / (n - 1), style) for i in range(n)]
    return fit_pelvis_height(R, specs, bend=style.get("bend", 0.016))


def planner_walk(R, dur, steps, rest_after=None, speed_style="civ_walk", end_spec=None, start_spec=None,
                 lift=0.09):
    """Specs for start/stop walks from a step list [(side, t_lift, t_land, dy)]."""
    pl = Planner(R, dur, lift=lift)
    for S_, t0, t1, dy in steps:
        pl.step(S_, t0, t1, dy)
    pl.build_root()
    st = STYLES[speed_style]
    out = []
    ry_prev = 0.0
    for i in range(int(round(dur * FPS)) + 1):
        t = i / FPS
        sp = neutral(R)
        ry = pl.feet_spec(sp, t)
        v = (ry - ry_prev) * FPS if i else 0.0
        ry_prev = ry
        moving = min(1.0, abs(v) / 1.2)
        # lateral sway toward the stance foot, arm swing from foot offsets
        fl = sp["feet"]["Left"]["ank"]
        fr = sp["feet"]["Right"]["ank"]
        dyf = (fl[1] - fr[1])          # >0: left foot behind
        sp["hip"] = np.array([0.012 * np.clip((fr[2] - fl[2]) * 12, -1, 1), 0.0, 0.0])
        sp["pel"] = np.array([st["lean"] * 0.5 * moving, 0.0, 6.0 * np.clip(dyf * 2.5, -1, 1)])
        sp["sp"] = np.array([st["lean"] * moving, 0.0, -10.0 * np.clip(dyf * 2.5, -1, 1)])
        for S_, sgn in (("Left", 1.0), ("Right", -1.0)):
            sw = sgn * np.clip(dyf * 2.2, -1, 1)
            sp["arm"][S_] = dict(fk=np.array([4.0 + 14.0 * sw, -10.0, 0.0, 12.0 + 12.0 * max(sw, 0), 6.0, 0.0]))
        out.append(sp)
    out = fit_pelvis_height(R, out, bend=0.016, loop=False)
    return out, pl


def clip_exit_specs(R, dur):
    steps = [("Right", 0.30, 0.78, -0.42), ("Left", 0.72, 1.22, -0.62), ("Right", 1.16, 1.66, -0.60),
             ("Left", 1.60, 2.10, -0.34)]
    specs, pl = planner_walk(R, dur, steps, lift=0.10)
    # cautious: slight duck under the lintel and a hand reaching for the door frame
    for i, sp in enumerate(specs):
        t = i / FPS
        duck = env(t, [(0.0, 0.0), (0.5, 1.0), (1.3, 1.0), (1.9, 0.0)])
        sp["sp"] = sp["sp"] + np.array([10.0 * duck, 0, 0])
        sp["nk"] = sp["nk"] + np.array([6.0 * duck, 0, 0])
        reach = float(env(t, [(0.0, 0.0), (0.45, 1.0), (1.1, 1.0), (1.6, 0.0)]))
        a = sp["arm"]["Left"]["fk"]
        sp["arm"]["Left"] = dict(fk=lerp(a, np.array([42.0, 34.0, 0.0, 30.0, -15.0, 0.0]), reach))
    return specs, pl


def clip_arrive_specs(R, dur):
    steps = [("Right", 0.00, 0.40, -0.66), ("Left", 0.38, 0.84, -0.58), ("Right", 0.82, 1.32, -0.44),
             ("Left", 1.30, 1.72, -0.18)]
    specs, pl = planner_walk(R, dur, steps, lift=0.09)
    for i, sp in enumerate(specs):
        t = i / FPS
        relief = float(env(t, [(1.6, 0.0), (2.0, 1.0), (2.6, 0.6)]))
        sp["nk"] = sp["nk"] + np.array([-10.0 * relief, 0, 8.0 * relief * math.sin(t * 3)])
        sp["sp"] = sp["sp"] + np.array([-3.0 * relief, 0, 0])
        for S_ in ("Left", "Right"):
            sp["clav"][S_] = sp["clav"][S_] + np.array([4.0 * relief * (1 - (t - 2.0) * 1.5 if t > 2.0 else 1), 0])
    return specs, pl


# --------------------------------------------------------------------------- soldier clips

def sol_neutral(R, role, w=0.0, ready=0.0):
    sp = neutral(R, w)
    if role in ("captain", "scout") and ready <= 0.0:
        # weapon carried (sword sheathed / bow slung): relaxed arms, captain's left hand near the hilt
        if role == "captain":
            sp["arm"]["Left"] = dict(fk=np.array([14.0, -2.0, 0.0, 38.0, 8.0, 0.0]))
            sp["fing"]["Left"] = np.array([0.45, 0.35, 0.4])
        return sp
    if role == "captain":
        # sword in the right hand, blade low and forward
        sp["arm"]["Right"] = dict(fk=np.array([14.0 + 30 * ready, -6.0, 0.0, 28.0 + 50 * ready, -10.0, 0.0]))
        sp["fing"]["Right"] = np.array([0.85, 0.7, 0.85])
    elif role == "scout":
        sp["arm"]["Left"] = dict(fk=np.array([10.0 + 30 * ready, -4.0, 0.0, 22.0 + 30 * ready, 0.0, 0.0]))
        sp["fing"]["Left"] = np.array([0.85, 0.7, 0.85])
    elif role == "shield_guard":
        sp["arm"]["Right"] = dict(fk=np.array([26.0 + 10 * ready, -2.0, 0.0, 72.0 - 10 * ready, 10.0, 0.0]))
        sp["fing"]["Right"] = np.array([0.9, 0.75, 0.9])
        sp["arm"]["Left"] = dict(fk=np.array([18.0 + 25 * ready, 4.0, 0.0, 72.0 + 10 * ready, 0.0, 0.0]))
        sp["fing"]["Left"] = np.array([0.9, 0.75, 0.9])
    return sp


def guard_stance(R, role, t=0.0, T=3.2):
    sp = sol_neutral(R, role, 0.0, ready=1.0)
    for S_, s in (("Left", 1.0), ("Right", -1.0)):
        a = R.ankle0[S_].copy()
        a[0] += s * 0.06
        a[1] += -0.14 if S_ == "Left" else 0.12
        sp["feet"][S_] = dict(ank=a, fwd=foot_fwd(S_, 14.0 if S_ == "Left" else 22.0), up=np.array([0, 0, 1.0]),
                              toe=0.0)
    sp["hip"] = np.array([0.0, 0.0, -0.075])
    sp["pel"] = np.array([6.0, 0.0, 10.0])
    sp["sp"] = np.array([8.0, 0.0, -14.0])
    sp["nk"] = np.array([-6.0, 0.0, 6.0])
    return sp


def soldier_clip_specs(R, role, name, dur):
    n = int(round(dur * FPS)) + 1
    ts = [i / FPS for i in range(n)]
    if name == "lf_soldier_idle":
        out = []
        for t in ts:
            sp = sol_neutral(R, role, 0.5 * periodic(t, dur, 1))
            sp = breathe(sp, t, rate=2.0 / dur, amp=1.0)
            sp["nk"] = sp["nk"] + np.array([0, 0, 10.0 * periodic(t, dur, 1, 0.2)])
            out.append(sp)
        return out, None
    if name in ("lf_soldier_walk", "lf_soldier_jog"):
        jog = name.endswith("jog")
        G = A.Gait(R, dur, 2.6 if jog else 1.35, duty=0.38 if jog else 0.62, lift=0.17 if jog else 0.10,
                   heel_ang=10.0 if jog else 14.0, toe_ang=30.0 if jog else 26.0)
        style = dict(STYLES["sol_jog" if jog else "sol_walk"])
        specs = []
        for t in ts:
            sp = gait_spec(R, G, t, style)
            base = sol_neutral(R, role, 0.0, ready=0.0)
            hold = role_hold_arm(role)
            if hold:
                sp["arm"][hold] = base["arm"][hold]
                sp["arm"][hold]["fk"] = sp["arm"][hold]["fk"] + np.array([6.0 * periodic(t, dur, 1), 0, 0, 0, 0, 0])
                sp["fing"][hold] = base["fing"][hold]
            if role == "shield_guard":
                sp["arm"]["Left"] = base["arm"]["Left"]
                sp["fing"]["Left"] = base["fing"]["Left"]
            specs.append(sp)
        if jog:
            # flight phase: allow both feet up; pelvis from reach with more bend
            specs = fit_pelvis_height(R, specs, bend=0.05)
        else:
            specs = fit_pelvis_height(R, specs, bend=0.014)
        return specs, G
    if name == "lf_soldier_guard":
        out = []
        for t in ts:
            sp = guard_stance(R, role, t, dur)
            sp = breathe(sp, t, rate=3.0 / dur, amp=0.8)
            scan = 16.0 * periodic(t, dur, 1, 0.1)
            sp["nk"] = sp["nk"] + np.array([0, 0, scan])
            sp["sp"] = sp["sp"] + np.array([0, 0, scan * 0.3])
            sp["hip"] = sp["hip"] + np.array([0.01 * periodic(t, dur, 2), 0, 0.006 * periodic(t, dur, 2, 0.25)])
            out.append(sp)
        return out, None
    if name == "lf_soldier_attack":
        g = guard_stance(R, role)
        wind = copy(g)
        hit = copy(g)
        if role == "captain":
            wind["arm"]["Right"] = dict(fk=np.array([60.0, 70.0, -20.0, 95.0, -30.0, 0.0]))
            wind["sp"] = g["sp"] + np.array([-4.0, 4.0, 26.0])
            hit["arm"]["Right"] = dict(fk=np.array([68.0, -20.0, 20.0, 12.0, 10.0, 0.0]))
            hit["sp"] = g["sp"] + np.array([12.0, -4.0, -30.0])
        elif role == "scout":
            wind["arm"]["Left"] = dict(fk=np.array([80.0, 4.0, 0.0, 6.0, 0.0, 0.0]))
            wind["arm"]["Right"] = dict(fk=np.array([70.0, -40.0, 0.0, 120.0, 0.0, 0.0]))
            wind["sp"] = g["sp"] + np.array([-2.0, 0, 30.0])
            hit = copy(wind)
            hit["arm"]["Right"] = dict(fk=np.array([60.0, 10.0, 0.0, 40.0, 10.0, 0.0]))
            hit["fing"]["Right"] = np.array([0.1, 0.1, 0.1])
        else:
            wind["arm"]["Right"] = dict(fk=np.array([40.0, 20.0, 0.0, 110.0, 0.0, 0.0]))
            wind["sp"] = g["sp"] + np.array([-4.0, 0, 18.0])
            hit["arm"]["Right"] = dict(fk=np.array([78.0, -6.0, 0.0, 8.0, 0.0, 0.0]))
            hit["sp"] = g["sp"] + np.array([14.0, 0, -18.0])
            hit["hip"] = g["hip"] + np.array([0, -0.08, -0.02])
        keys = [(0.0, g), (0.42, wind), (0.65, hit), (0.85, hit), (1.2, g)]
        return [keyed(t, keys) for t in ts], None
    if name == "lf_soldier_hit":
        g = sol_neutral(R, role, 0.0, ready=0.5)
        h = copy(g)
        h["sp"] = g["sp"] + np.array([-12.0, 6.0, -8.0])
        h["nk"] = g["nk"] + np.array([-10.0, 0, 6.0])
        h["hip"] = g["hip"] + np.array([0, 0.05, -0.02])
        return [keyed(t, [(0.0, g), (0.12, h), (0.5, g)]) for t in ts], None
    if name == "lf_soldier_death":
        g = sol_neutral(R, role, 0.0, ready=0.3)
        k1 = copy(g)                                      # struck: recoil
        k1["hip"] = g["hip"] + np.array([0, 0.05, -0.02])
        k1["sp"] = np.array([-12.0, 4.0, 6.0])
        k1["nk"] = np.array([-14.0, 0, 0])
        k2 = copy(g)                                      # knees buckle
        k2["hip"] = np.array([0.0, 0.08, -0.42])
        k2["pel"] = np.array([18.0, 4.0, 0.0])
        k2["sp"] = np.array([22.0, 6.0, 0.0])
        k2["nk"] = np.array([18.0, 0, 0])
        for S_, s in (("Left", 1.0), ("Right", -1.0)):
            a = R.ankle0[S_].copy()
            a[1] += 0.16
            a[2] = 0.17
            k2["feet"][S_] = dict(ank=a, fwd=unit(np.array([s * 0.05, -0.64, -0.77])),
                                  up=unit(np.array([0, 0.77, -0.64]) * -1.0), toe=50.0,
                                  knee=unit(np.array([s * 0.2, -1.0, -0.3])))
        k3 = copy(k2)                                     # falling forward, hands reach for the ground
        h0 = R.hips0
        k3["hip"] = np.array([0.0, 0.12, 0.40 - h0[2]])
        k3["pel"] = np.array([62.0, 4.0, 0.0])
        k3["sp"] = np.array([16.0, 0, 0])
        k3["nk"] = np.array([-10.0, 0, 0])
        for S_, s in (("Left", 1.0), ("Right", -1.0)):
            k3["feet"][S_] = dict(ank=np.array([s * 0.12, 0.70, 0.18]), fwd=unit(np.array([0, 0.55, -0.8])),
                                  up=unit(np.array([0, 0.8, 0.55])), toe=30.0, knee=unit(np.array([s * 0.1, -0.2, -1.0])))
            k3["arm"][S_] = dict(wrist=np.array([s * 0.26, -0.62, 0.10]), elbow=np.array([s * 0.8, 0.2, -0.4]),
                                 palm=np.array([0, 0, -1.0]), hfwd=np.array([0, -1.0, 0.0]), w_ik=1.0,
                                 fk=k2["arm"][S_].get("fk", np.zeros(6)))
            k3["fing"][S_] = np.array([0.2, 0.1, 0.15])
        k4 = copy(k3)                                     # prone, settled
        k4["hip"] = np.array([0.0, 0.22, 0.16 - h0[2]])
        k4["pel"] = np.array([86.0, 6.0, 0.0])
        k4["sp"] = np.array([4.0, 0, 0])
        k4["nk"] = np.array([-18.0, 0.0, 65.0])
        for S_, s in (("Left", 1.0), ("Right", -1.0)):
            k4["feet"][S_] = dict(ank=np.array([s * 0.13, 1.05, 0.18]), fwd=unit(np.array([s * 0.1, 0.8, -0.6])),
                                  up=unit(np.array([0, 0.66, 0.75])), toe=35.0, knee=np.array([s * 0.1, 0.0, -1.0]))
            k4["arm"][S_] = dict(wrist=np.array([s * 0.30, -0.66, 0.05]), elbow=np.array([s * 0.9, 0.1, -0.3]),
                                 palm=np.array([0, 0, -1.0]), hfwd=np.array([s * 0.2, -1.0, 0.0]), w_ik=1.0,
                                 fk=k2["arm"][S_].get("fk", np.zeros(6)))
            k4["fing"][S_] = np.array([0.35, 0.2, 0.3])
        k5 = copy(k4)
        k5["hip"] = k4["hip"] + np.array([0, 0, -0.01])
        keys = [(0.0, g), (0.18, k1), (0.62, k2), (1.10, k3), (1.55, k4), (2.0, k5)]
        return [keyed(t, keys) for t in ts], "death"
    if name in ("lf_soldier_unlock", "lf_soldier_help", "lf_soldier_salute"):
        return support_clip(R, role, name, dur, ts), None
    raise KeyError(name)


def role_hold_arm(role):
    return {"shield_guard": "Right"}.get(role)


def support_clip(R, role, name, dur, ts):
    free = {"captain": "Left", "scout": "Right", "shield_guard": "Right"}.get(role, "Right")
    s = 1.0 if free == "Left" else -1.0
    g = sol_neutral(R, role, 0.0, ready=0.0)
    if name == "lf_soldier_unlock":
        reach = copy(g)
        reach["hip"] = g["hip"] + np.array([0, -0.06, -0.01])
        reach["sp"] = np.array([6.0, 0, -s * 8.0])
        reach["arm"][free] = dict(wrist=SOCKET + np.array([s * 0.03, 0.10, -0.02]), elbow=np.array([s * 0.8, 0.4, -0.5]),
                                  palm=np.array([0, -1.0, 0.1]), hfwd=np.array([0, -0.3, 1.0]))
        reach["fing"][free] = np.array([0.35, 0.2, 0.3])
        press = copy(reach)
        press["arm"][free] = dict(wrist=SOCKET + np.array([s * 0.03, 0.05, -0.02]), elbow=np.array([s * 0.8, 0.4, -0.5]),
                                  palm=np.array([0, -1.0, 0.1]), hfwd=np.array([0.4 * s, -0.3, 1.0]))
        turn = copy(press)
        turn["arm"][free] = dict(wrist=SOCKET + np.array([s * 0.03, 0.05, -0.02]), elbow=np.array([s * 0.8, 0.4, -0.5]),
                                 palm=np.array([0, -1.0, 0.1]), hfwd=np.array([1.0 * s, -0.3, 0.3]))
        back = copy(g)
        back["hip"] = g["hip"] + np.array([0, 0.03, 0])
        keys = [(0.0, g), (0.7, reach), (1.25, press), (1.6, turn), (1.9, turn), (2.4, g)]
        return [keyed(t, keys) for t in ts]
    if name == "lf_soldier_help":
        offer = copy(g)
        offer["sp"] = np.array([10.0, 0, -s * 10.0])
        offer["arm"][free] = dict(wrist=np.array([s * 0.12, -0.52, 1.02]), elbow=np.array([s * 0.7, 0.3, -0.6]),
                                  palm=np.array([0, -0.2, 1.0]), hfwd=np.array([0, -1.0, 0.1]))
        offer["fing"][free] = np.array([0.1, 0.1, 0.1])
        lift = copy(offer)
        lift["sp"] = np.array([2.0, 0, -s * 6.0])
        lift["arm"][free] = dict(wrist=np.array([s * 0.15, -0.38, 1.10]), elbow=np.array([s * 0.7, 0.4, -0.5]),
                                 palm=np.array([0.2 * s, -0.1, 1.0]), hfwd=np.array([0, -1.0, 0.2]))
        lift["fing"][free] = np.array([0.55, 0.4, 0.5])
        come = copy(g)
        come["arm"][free] = dict(wrist=np.array([s * 0.30, -0.25, 1.15]), elbow=np.array([s * 0.6, 0.4, -0.6]),
                                 palm=np.array([-s * 0.5, 0.3, 0.8]), hfwd=np.array([s * 0.5, 0.0, 1.0]))
        come["nk"] = np.array([0, 0, s * 20.0])
        keys = [(0.0, g), (0.6, offer), (1.2, offer), (1.7, lift), (2.2, come), (2.8, g)]
        return [keyed(t, keys) for t in ts]
    # salute: fist to the heart (captain: sword hilt to the chin), small bow
    sal = copy(g)
    chest = R.S.world({})["UpperChest"][:3, 3]
    if role == "captain":
        sal["arm"]["Right"] = dict(wrist=chest + np.array([0.0, -0.17, 0.12]), elbow=np.array([-0.8, 0.3, -0.5]),
                                   palm=np.array([1.0, 0.0, 0.0]), hfwd=np.array([0.0, -0.2, 1.0]))
    else:
        sal["arm"][free] = dict(wrist=chest + np.array([s * 0.10, -0.16, 0.04]), elbow=np.array([s * 0.8, 0.2, -0.6]),
                                palm=np.array([-s * 0.2, 1.0, 0.0]), hfwd=np.array([-s * 1.0, 0.0, 0.2]))
        sal["fing"][free] = np.array([0.9, 0.8, 0.9])
    bow = copy(sal)
    bow["sp"] = sal["sp"] + np.array([8.0, 0, 0])
    bow["nk"] = sal["nk"] + np.array([12.0, 0, 0])
    keys = [(0.0, g), (0.45, sal), (0.8, bow), (1.25, sal), (1.8, g)]
    return [keyed(t, keys) for t in ts]
