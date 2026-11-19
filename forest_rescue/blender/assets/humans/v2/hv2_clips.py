"""The 22 human clips on the shared rig (10 soldier + 12 civilian), authored procedurally from
semantic pose parameters + an IK gait generator.  Every clip is in place (root at the origin),
30 fps, loops have identical first/last frames, planted feet do not slide (ankle targets are
derived from a stationary ground pivot - heel, flat foot or ball - moving back at exactly the
authored ground speed).

Acting follows art/12_civilian_rescue_motion.png (walk with heel-toe roll and hip counter-rotation,
seated exhaustion -> hands on knees -> rising -> relieved breathing, offered open hand, elder
stepping out, supporting walk, restrained hand-on-heart thanks) and the rescue storyboard
(captain unlocking the cage socket, guard/attack/hit for the squad)."""
import math

import numpy as np

import hv2_anim as A
from hv2_anim import DEG, X, Y, Z, rot, ypr, smooth, smoother

FPS = A.FPS


# --------------------------------------------------------------------------- context

class Ctx:
    def __init__(self, sk, C, J, T, kind, weapon=None):
        self.sk, self.C, self.J, self.T, self.kind, self.weapon = sk, C, J, T, kind, weapon
        self.hz = sk.head("Hips")[2]
        self.ank = {S: sk.head(f"{S}Foot") for S in ("Left", "Right")}
        self.ball = {S: sk.head(f"{S}Toes") for S in ("Left", "Right")}
        self.heel = {S: np.array([J[f"{S}Heel"][0], J[f"{S}Heel"][1], 0.0]) for S in ("Left", "Right")}
        self.leg_len = {S: sk.length[f"{S}UpperLeg"] + sk.length[f"{S}LowerLeg"] for S in ("Left", "Right")}
        self.hipj = {S: sk.head(f"{S}UpperLeg") for S in ("Left", "Right")}
        self.fwd = {S: J[f"_{S}fwd"] for S in ("Left", "Right")}
        self.lat = {S: np.cross(self.fwd[S], Z) * (-1.0) for S in ("Left", "Right")}
        # neutral arm adduction: bring the painted A-pose arms toward the body but keep the hands
        # clear of the garments/torso at hand height
        self.add0 = {}
        for S, sx in (("Left", 1.0), ("Right", -1.0)):
            sh = sk.head(f"{S}UpperArm")
            wr = sk.head(f"{S}Hand")
            v = wr - sh
            abd = math.degrees(math.atan2(abs(v[0]), -v[2]))
            r_body = float(T.hull(np.array([max(wr[2] - 0.05, T.zs[0])]), np.array([sx * math.pi / 2]))[0])
            room = abs(wr[0]) - (r_body + 0.075)
            arm = np.linalg.norm(v) + 0.09
            max_add = math.degrees(math.asin(np.clip(room / arm, -0.5, 0.9))) if room > 0 else 0.0
            self.add0[S] = float(np.clip(min(abd - 9.0, max_add), 0.0, 22.0))
        self.stance = {S: 0.0 for S in ("Left", "Right")}
        self.belly_y = -float(T.hull(np.array([self.hz + 0.05]), np.array([0.0]))[0])
        self.chest_y = -float(T.hull(np.array([sk.head("Chest")[2] + 0.05]), np.array([0.0]))[0])


def base(cx):
    """Neutral relaxed standing parameters (degrees / metres)."""
    p = dict(hx=0.0, hy=0.0, hz=0.0, hp=0.0, hr=0.0, hyaw=0.0,
             sp=2.0, sr=0.0, syaw=0.0, np_=2.0, nyaw=0.0, nr=0.0, hdp=-2.0, hdyaw=0.0, hdr=0.0,
             prop_r=1.0, prop_l=1.0)
    for s, S in (("l", "Left"), ("r", "Right")):
        p.update({f"{s}_clav": 0.0, f"{s}_clavf": 0.0, f"{s}_fwd": 3.0, f"{s}_add": cx.add0[S], f"{s}_tw": 0.0,
                  f"{s}_elb": 10.0, f"{s}_wr": 4.0, f"{s}_curl": 0.35, f"{s}_ik": None,
                  f"{s}_fx": 0.0, f"{s}_fy": 0.0, f"{s}_fz": 0.0, f"{s}_fp": 0.0, f"{s}_fyaw": 0.0, f"{s}_toe": 0.0,
                  f"{s}_kout": 0.0, f"{s}_kup": 0.0})
    # narrow the painted (wide) stance a little for relaxed standing
    for s, S, sx in (("l", "Left", 1.0), ("r", "Right", -1.0)):
        x = cx.ank[S][0]
        p[f"{s}_fx"] = -sx * max(0.0, abs(x) - 0.125) * 0.6
    return p


CTX = [None]
_FKW = {}


def ik_from_fk(p, s):
    """IK dict reproducing the FK arm of params p (wrist + elbow pole from the solved FK pose)."""
    key = (id(p), s)
    if key in _FKW:
        return _FKW[key]
    cx = CTX[0]
    S = "Left" if s == "l" else "Right"
    q = dict(p)
    q[f"{s}_ik"] = None
    basis, M = A.solve(cx.sk, make_pose(cx, q))
    sh = M[f"{S}UpperArm"][:3, 3]
    el = M[f"{S}LowerArm"][:3, 3]
    wr = M[f"{S}Hand"][:3, 3]
    mid = 0.5 * (sh + wr)
    pole = el - mid
    if np.linalg.norm(pole) < 1e-4:
        pole = np.array([0.0, 0.3, 0.0])
    out = dict(wrist=wr, elbow=pole / np.linalg.norm(pole))
    _FKW[key] = out
    return out


def lerp_params(a, b, t):
    out = {}
    for k in a:
        va, vb = a[k], b.get(k, a[k])
        if k.endswith("_ik") and (va is not None or vb is not None):
            s = k[0]
            if va is None:
                va = ik_from_fk(a, s)
            if vb is None:
                vb = ik_from_fk(b, s)
            w = (1 - t) * np.asarray(va["wrist"], float) + t * np.asarray(vb["wrist"], float)
            e = (1 - t) * np.asarray(va.get("elbow", vb.get("elbow")), float) + t * np.asarray(vb.get("elbow", va.get("elbow")), float)
            out[k] = dict(wrist=w, elbow=e / max(np.linalg.norm(e), 1e-6))
        elif va is None or vb is None or isinstance(va, (dict, tuple, list)):
            out[k] = vb if t >= 0.5 else va
        else:
            out[k] = va + (vb - va) * t
    return out


def keyed(keys, t, ease=smoother):
    """keys: list of (time, params-dict-delta-applied-on-previous).  Smooth piecewise blend."""
    if t <= keys[0][0]:
        return dict(keys[0][1])
    for (t0, p0), (t1, p1) in zip(keys[:-1], keys[1:]):
        if t <= t1:
            f = (t - t0) / max(t1 - t0, 1e-9)
            return lerp_params(p0, p1, float(ease(f)))
    return dict(keys[-1][1])


def expand(base_p, keys):
    """Turn delta keyframes into absolute keyframes (each key starts from the previous one)."""
    out = []
    cur = dict(base_p)
    for t, d in keys:
        cur = dict(cur)
        cur.update(d)
        out.append((t, cur))
    return out


# --------------------------------------------------------------------------- params -> Pose

def make_pose(cx, p):
    sk = cx.sk
    P = A.Pose()
    P.hip_off = np.array([p["hx"], p["hy"], p["hz"]])
    P.hip_rot = ypr(p["hyaw"] * DEG, p["hp"] * DEG, p["hr"] * DEG)
    for b, f in (("Spine", 0.34), ("Chest", 0.36), ("UpperChest", 0.30)):
        P.r(b, ypr(p["syaw"] * f * DEG, p["sp"] * f * DEG, p["sr"] * f * DEG))
    P.r("Neck", ypr(p["nyaw"] * DEG, p["np_"] * DEG, p["nr"] * DEG))
    P.r("Head", ypr(p["hdyaw"] * DEG, p["hdp"] * DEG, p["hdr"] * DEG))
    for s, S, sx in (("l", "Left", 1.0), ("r", "Right", -1.0)):
        P.r(f"{S}Shoulder", rot(Z, sx * p[f"{s}_clavf"] * DEG) @ rot(Y, -sx * p[f"{s}_clav"] * DEG))
        ik = p.get(f"{s}_ik")
        if ik is not None:
            P.arm[S] = dict(wrist=np.asarray(ik["wrist"], float), elbow=np.asarray(ik.get("elbow", (sx * 0.6, 0.8, -0.3)), float),
                            hand_rot=ik.get("hand_rot"), hand_local=ik.get("hand_local", True))
        else:
            arm_dir = sk.R[f"{S}UpperArm"][:3, 1]
            Rua = rot(X, -p[f"{s}_fwd"] * DEG) @ rot(Y, sx * p[f"{s}_add"] * DEG) @ rot(arm_dir, sx * p[f"{s}_tw"] * DEG)
            P.r(f"{S}UpperArm", Rua)
            fa = sk.R[f"{S}LowerArm"][:3, 1]
            ax = np.cross(fa, np.array([0, -1.0, 0]))
            P.r(f"{S}LowerArm", rot(ax, p[f"{s}_elb"] * DEG))
        hx = sk.R[f"{S}Hand"][:3, 0]
        if ik is None or ik.get("hand_rot") is None:
            P.r(f"{S}Hand", rot(hx, -p[f"{s}_wr"] * DEG))
        c = p[f"{s}_curl"]
        for f, amt in (("Index1", 30), ("Index2", 45), ("Middle1", 34), ("Middle2", 48), ("Ring1", 55),
                       ("Pinky1", 60), ("Thumb1", 10), ("Thumb2", 20)):
            n = f"{S}{f}"
            if n in sk.R:
                P.r(n, rot(sk.R[n][:3, 0], -c * amt * DEG))
        # legs (IK): ankle target = rest ankle + offset (root space)
        ank = cx.ank[S] + np.array([p[f"{s}_fx"], p[f"{s}_fy"], p[f"{s}_fz"]])
        fwdv = cx.fwd[S]
        yaw = p[f"{s}_fyaw"] * DEG
        lat = rot(Z, yaw) @ cx.lat[S]
        frot = rot(lat, p[f"{s}_fp"] * DEG) @ rot(Z, yaw)
        pole = rot(Z, sx * p[f"{s}_kout"] * DEG) @ np.array([0, -1.0, 0]) + np.array([0, 0, p[f"{s}_kup"]])
        P.leg[S] = dict(ankle=ank, foot_rot=frot, knee=pole / np.linalg.norm(pole))
        P.r(f"{S}Toes", rot(lat, p[f"{s}_toe"] * DEG))
    P.scale["PropR"] = max(p["prop_r"], 0.001)
    P.scale["PropL"] = max(p["prop_l"], 0.001)
    return P


# --------------------------------------------------------------------------- gait

def gait(cx, t, T, v, beta=0.62, lift=0.09, step_w=0.095, lean=4.0, bob=0.022, sway=0.022,
         pelvis_yaw=6.0, arm_swing=18.0, elbow=18.0, heel=14.0, toeoff=32.0, base_p=None, flight=0.0):
    """In-place gait at speed v (m/s) and cycle T (s).  Left foot contacts at phase 0, right at 0.5.
    Returns params + contact info {S: (planted, pivot_world)} (pivot in world = root space + travel)."""
    p = dict(base_p or base(cx))
    S_len = v * T
    travel = v * t
    contacts = {}
    for s, S, sx, ph0 in (("l", "Left", 1.0, 0.0), ("r", "Right", -1.0, 0.5)):
        ph = ((t / T) - ph0) % 1.0
        heel_r, ball_r, ank_r = cx.heel[S], cx.ball[S], cx.ank[S]
        foot_l = np.linalg.norm((ball_r - heel_r)[:2])
        x_off = sx * step_w - ank_r[0]
        if ph < beta:
            u = ph / beta                                      # stance progress
            # contact heel at y = -beta*S_len/2 (ahead) moving back at v
            y_heel = -beta * S_len / 2 + v * (ph * T)
            if u < 0.12:
                pitch = -heel * (1 - smooth(u / 0.12))         # heel strike: toes up
            elif u < 0.68:
                pitch = 0.0
            else:
                pitch = toeoff * smooth((u - 0.68) / 0.32)       # heel off, roll over the ball
            fwd = cx.fwd[S]
            if pitch <= 0:      # heel pivot (or flat)
                piv_rest = heel_r
                piv = np.array([heel_r[0] + x_off, heel_r[1] - heel_r[1] + y_heel + (heel_r[1] - ank_r[1]) * 0, 0.0])
                piv = np.array([heel_r[0] + x_off, y_heel, 0.0])
            else:               # ball pivot
                piv_rest = np.array([ball_r[0], ball_r[1], 0.0])
                piv = np.array([ball_r[0] + x_off, y_heel - foot_l * (-fwd[1]), 0.0])
            lat = cx.lat[S]
            Rp = rot(lat, pitch * DEG)
            ank = piv + Rp @ (ank_r - piv_rest)
            contacts[S] = (True, piv + np.array([0, -travel, 0]), "heel" if pitch <= 0 else "ball")
            toe = -pitch if pitch > 0 else 0.0
        else:
            u = (ph - beta) / (1 - beta)                        # swing progress
            y0 = beta * S_len / 2                                # lift-off heel position
            y1 = -beta * S_len / 2 + v * (0)                     # next contact
            # the swing ankle travels from the toe-off ankle to the heel-strike ankle
            lat = cx.lat[S]
            piv_b = np.array([ball_r[0] + x_off, y0 - foot_l * (-cx.fwd[S][1]), 0.0])
            a0 = piv_b + rot(lat, toeoff * DEG) @ (ank_r - np.array([ball_r[0], ball_r[1], 0.0]))
            piv_h = np.array([heel_r[0] + x_off, -beta * S_len / 2 - v * 0.0, 0.0])
            a1 = piv_h + rot(lat, -heel * DEG) @ (ank_r - heel_r)
            # the next contact happens one cycle later: the heel target is ahead by S_len relative to y0 path
            a1 = a1 + np.array([0, 0.0, 0])
            k = smoother(u)
            ank = a0 * (1 - k) + a1 * k
            ank[2] += lift * math.sin(math.pi * min(1.0, u * 1.08)) ** 1.2 * (1.0 + flight)
            pitch = toeoff * (1 - smooth(u / 0.55)) - heel * smooth((u - 0.55) / 0.45)
            toe = 8.0 * math.sin(math.pi * u)
            contacts[S] = (False, None, None)
        p[f"{s}_fx"] = ank[0] - ank_r[0]
        p[f"{s}_fy"] = ank[1] - ank_r[1]
        p[f"{s}_fz"] = ank[2] - ank_r[2]
        p[f"{s}_fp"] = pitch
        p[f"{s}_toe"] = toe
    w = 2 * math.pi * t / T
    # pelvis: lowest at double support (phase 0, 0.5), highest mid-stance; sway over the stance leg
    p["hz"] = p.get("hz", 0.0) - bob * (0.5 + 0.5 * math.cos(2 * w)) - (0.02 if flight else 0.0) \
        + (flight * 0.03 * max(0.0, math.cos(2 * w + math.pi)))
    p["hx"] = p.get("hx", 0.0) + sway * math.sin(w + 0.5 * math.pi * 0.0) * -1.0 * math.cos(w * 0 + 0) * 0 \
        + sway * math.cos(w - 0.35) * (1.0)
    p["hyaw"] = p.get("hyaw", 0.0) + pelvis_yaw * math.cos(w)
    p["hr"] = p.get("hr", 0.0) + 2.5 * math.sin(2 * w)
    p["hp"] = p.get("hp", 0.0) + lean * 0.4
    p["sp"] = p.get("sp", 0.0) + lean * 0.6 + 1.0 * math.cos(2 * w)
    p["syaw"] = p.get("syaw", 0.0) - pelvis_yaw * 1.5 * math.cos(w)
    p["hdyaw"] = p.get("hdyaw", 0.0) + pelvis_yaw * 0.4 * math.cos(w)
    p["hdp"] = p.get("hdp", 0.0) - lean * 0.6 + 1.2 * math.cos(2 * w)
    for s, sgn in (("l", -1.0), ("r", 1.0)):
        sw = arm_swing * sgn * math.cos(w)
        p[f"{s}_fwd"] = p.get(f"{s}_fwd", 0.0) + sw
        p[f"{s}_elb"] = p.get(f"{s}_elb", 10.0) + elbow * (0.6 + 0.4 * max(0.0, sgn * math.cos(w)))
    return p, contacts


def reach_fix(cx, p, margin=0.006):
    """Lower the pelvis just enough that both ankle targets are reachable (no knee snap)."""
    worst = 0.0
    for s, S in (("l", "Left"), ("r", "Right")):
        ank = cx.ank[S] + np.array([p[f"{s}_fx"], p[f"{s}_fy"], p[f"{s}_fz"]])
        hip = cx.hipj[S] + np.array([p["hx"], p["hy"], p["hz"]])
        d = np.linalg.norm(ank - hip)
        L = cx.leg_len[S] - margin
        if d > L:
            dz = hip[2] - ank[2]
            horiz = math.sqrt(max(d * d - dz * dz, 0))
            need = dz - math.sqrt(max(L * L - horiz * horiz, 0))
            worst = max(worst, need)
    return worst


# --------------------------------------------------------------------------- clip builders

def frames_for(seconds):
    n = int(round(seconds * FPS))
    return np.arange(n + 1) / FPS


def clip(name, seconds, loop, fn, meta=None, contacts_fn=None):
    return dict(name=name, seconds=seconds, loop=loop, fn=fn, meta=meta or {}, contacts=contacts_fn)


def locomotion(cx, name, T, v, **kw):
    sec = T
    times = frames_for(sec)
    raw = [gait(cx, t, T, v, **kw) for t in times]
    # pelvis reach correction made periodic (max over the loop, smoothed)
    need = np.array([reach_fix(cx, p) for p, _ in raw])
    from scipy.ndimage import gaussian_filter1d
    need = gaussian_filter1d(np.concatenate([need, need, need]), 3)[len(need):2 * len(need)]
    need = np.maximum(need, 0) + 0.004
    params = []
    for (p, c), nd in zip(raw, need):
        p = dict(p)
        p["hz"] -= nd
        params.append(p)
    return params, [c for _, c in raw]


def build_clips(cx):
    """Return list of (name, seconds, loop, params-per-frame, contacts-per-frame, meta)."""
    CTX[0] = cx
    _FKW.clear()
    out = []
    b = base(cx)
    if cx.kind == "civilian":
        out += civilian_clips(cx, b)
    else:
        out += soldier_clips(cx, b)
    return out


def periodic(t, sec, cycles=1.0, phase=0.0):
    return math.sin(2 * math.pi * (t / sec) * cycles + phase)


def standing_clip(cx, b, sec, fn):
    times = frames_for(sec)
    params = [fn(t, dict(b)) for t in times]
    contacts = [{S: (True, None, "flat") for S in ("Left", "Right")} for _ in times]
    return params, contacts


def knee_point(cx, S, p):
    s = "l" if S == "Left" else "r"
    sx = 1.0 if S == "Left" else -1.0
    ank = cx.ank[S] + np.array([p[f"{s}_fx"], p[f"{s}_fy"], p[f"{s}_fz"]])
    hip = cx.hipj[S] + np.array([p["hx"], p["hy"], p["hz"]])
    la = cx.sk.length[f"{S}UpperLeg"]
    lb = cx.sk.length[f"{S}LowerLeg"]
    pole = rot(Z, sx * p[f"{s}_kout"] * DEG) @ np.array([0, -1.0, 0]) + np.array([0, 0, p[f"{s}_kup"]])
    k, _ = A.circle_ik(hip, ank, la, lb, pole / np.linalg.norm(pole))
    return k


def sit_params(cx, b):
    p = dict(b)
    hz = cx.hz
    p.update(hz=-(hz - 0.15), hy=0.30, hp=-8.0, sp=38.0, np_=14.0, hdp=16.0)
    for s, S, sx in (("l", "Left", 1.0), ("r", "Right", -1.0)):
        p[f"{s}_fx"] = -sx * max(0.0, abs(cx.ank[S][0]) - 0.13)
        p[f"{s}_fy"] = -0.04
        p[f"{s}_kup"] = 1.2
        p[f"{s}_kout"] = 12.0
        p[f"{s}_fp"] = 6.0
    # forearms rest on the knees, hands hang in front of them
    for s, S, sx in (("l", "Left", 1.0), ("r", "Right", -1.0)):
        k = knee_point(cx, S, p)
        p[f"{s}_ik"] = dict(wrist=k + np.array([-sx * 0.035, -0.10, -0.05]), elbow=(sx * 0.5, 0.6, -0.6))
        p[f"{s}_curl"] = 0.55
    return p


def civilian_clips(cx, b):
    out = []
    hz = cx.hz
    sit = sit_params(cx, b)

    # 1 cage_sit (loop 5.4): slumped on the cage floor, slow breathing, head lifts once
    def f_sit(t, p):
        q = dict(sit)
        br = periodic(t, 5.4, 2)
        q["sp"] = sit["sp"] + 2.0 * br
        q["hz"] = sit["hz"] + 0.004 * br
        look = 0.5 - 0.5 * math.cos(2 * math.pi * t / 5.4)
        q["hdp"] = sit["hdp"] - 14.0 * look ** 2
        q["np_"] = sit["np_"] - 6.0 * look ** 2
        q["hdyaw"] = 10.0 * math.sin(2 * math.pi * t / 5.4) * look
        return q
    out.append(("lf_civilian_cage_sit", 5.4, True) + standing_clip(cx, b, 5.4, f_sit) + ({},))

    # 2 cage_stand (loop 4.8): standing, hands clasped low in front, weight shifting, head low
    def clasp(p, k=1.0):
        zc = hz + 0.02
        y = cx.belly_y - 0.07
        for s, sx in (("l", 1.0), ("r", -1.0)):
            p[f"{s}_ik"] = dict(wrist=np.array([sx * 0.045, y, zc]), elbow=(sx * 0.7, 0.6, -0.2))
            p[f"{s}_curl"] = 0.6
        return p

    def f_stand(t, p):
        w = periodic(t, 4.8, 1)
        p["hx"] = 0.022 * w
        p["hr"] = -2.0 * w
        p["sr"] = 2.5 * w
        p["sp"] = 6.0 + 1.2 * periodic(t, 4.8, 2)
        p["hdp"] = 12.0 + 3.0 * periodic(t, 4.8, 1, 1.0)
        p["hdyaw"] = 8.0 * periodic(t, 4.8, 1, 2.0)
        p["l_fz"] = 0.0
        return clasp(p)
    out.append(("lf_civilian_cage_stand", 4.8, True) + standing_clip(cx, b, 4.8, f_stand) + ({},))

    # 3 cage_wait (loop 6.1): looking out through the bars, glances left/right, weight shift
    def f_wait(t, p):
        g = periodic(t, 6.1, 1)
        p["hx"] = -0.018 * periodic(t, 6.1, 1, 0.6)
        p["hr"] = 1.5 * periodic(t, 6.1, 1, 0.6)
        p["hdyaw"] = 28.0 * g
        p["nyaw"] = 10.0 * g
        p["syaw"] = 6.0 * g
        p["hdp"] = -4.0 + 3.0 * periodic(t, 6.1, 2)
        p["l_fwd"] = b["l_fwd"] + 4.0
        p["r_fwd"] = b["r_fwd"] + 4.0
        p["sp"] = 3.0 + 1.2 * periodic(t, 6.1, 3)
        return p
    out.append(("lf_civilian_cage_wait", 6.1, True) + standing_clip(cx, b, 6.1, f_wait) + ({},))

    # 4 react (1.4): flinch toward the noise, shoulders up, then relief
    keys = expand(b, [(0.0, {}), (0.18, dict(l_clav=9, r_clav=9, sp=-4, hdp=-10, hy=0.02, l_elb=35, r_elb=35,
                                              l_fwd=12, r_fwd=12, l_curl=0.8, r_curl=0.8)),
                      (0.55, dict(hdp=-6, sp=-2)), (1.0, dict(l_clav=0, r_clav=0, hdp=-4, l_elb=12, r_elb=12, l_fwd=3, r_fwd=3,
                                                              hy=0.0, sp=4, l_curl=0.4, r_curl=0.4)),
                      (1.4, dict(sp=2, hdp=-2))])
    out.append(("lf_civilian_react", 1.4, False) + standing_clip(cx, b, 1.4, lambda t, p: keyed(keys, t)) + ({},))

    # 5 stand_up (2.2): seated -> hands on knees -> push -> upright relieved
    def hands_on_knees(p, k=1.0):
        for s, S, sx in (("l", "Left", 1.0), ("r", "Right", -1.0)):
            kp = knee_point(cx, S, p)
            p[f"{s}_ik"] = dict(wrist=kp + np.array([-sx * 0.01, -0.03, 0.02]), elbow=(sx * 0.8, 0.3, 0.1))
            p[f"{s}_curl"] = 0.5
        return p
    k1 = dict(sit)
    k1.update(sp=45, hy=0.22, hz=sit["hz"] + 0.02, hdp=4)
    k1 = hands_on_knees(k1)
    k2 = dict(b)
    k2.update(hz=-(hz * 0.30), hy=0.10, hp=18, sp=40, hdp=-10, np_=6)
    for s, S, sx in (("l", "Left", 1.0), ("r", "Right", -1.0)):
        k2[f"{s}_fx"] = b[f"{s}_fx"]
        k2[f"{s}_kout"] = 8
        k2[f"{s}_kup"] = 0.4
    k2 = hands_on_knees(k2)
    k3 = dict(b)
    k3.update(hz=-0.03, hp=6, sp=12, hdp=-14, np_=-4)
    k4 = dict(b)
    k4.update(sp=-2, hdp=-10, np_=-2)
    keys = [(0.0, sit), (0.55, k1), (1.25, k2), (1.8, k3), (2.2, k4)]

    out.append(("lf_civilian_stand_up", 2.2, False) + standing_clip(cx, b, 2.2, lambda t, p: keyed(keys, t)) + ({},))

    # 6 exit (2.8): cautious walk out of the cage at 1.0 m/s, head scanning, hands slightly forward
    bx = dict(b)
    bx.update(sp=7.0, l_fwd=8, r_fwd=8, l_elb=20, r_elb=20, hdp=-2)
    params, contacts = locomotion(cx, "exit", 1.12, 1.0, beta=0.64, lift=0.07, lean=6.0, arm_swing=10.0,
                                  base_p=bx)
    times = frames_for(2.8)
    P2, C2 = [], []
    for t in times:
        i = int(round((t % 1.12) * FPS)) % (len(params) - 1)
        q = dict(params[i])
        q["hdyaw"] += 22.0 * math.sin(2 * math.pi * t / 2.8)
        P2.append(q)
        C2.append(contacts[i])
    out.append(("lf_civilian_exit", 2.8, False, P2, C2, dict(groundSpeed_mps=1.0, strideLength_m=1.12)))

    # 7 follow (1.1 loop, 1.2 m/s): relieved escort walk
    params, contacts = locomotion(cx, "follow", 1.1, 1.2, beta=0.62, lift=0.085, lean=3.0, arm_swing=16.0,
                                  base_p=b)
    out.append(("lf_civilian_follow", 1.1, True, params, contacts, dict(groundSpeed_mps=1.2, strideLength_m=1.32)))

    # 8 follow_tired (1.25 loop, 0.95 m/s): heavier, hunched, low clearance, little arm swing
    bt = dict(b)
    bt.update(sp=12.0, np_=8.0, hdp=10.0, l_clav=-3, r_clav=-3, l_elb=8, r_elb=8, l_curl=0.25, r_curl=0.25)
    params, contacts = locomotion(cx, "follow_tired", 1.25, 0.95, beta=0.66, lift=0.055, lean=9.0, arm_swing=7.0,
                                  elbow=6.0, bob=0.03, sway=0.03, pelvis_yaw=4.0, heel=8.0, toeoff=24.0, base_p=bt)
    out.append(("lf_civilian_follow_tired", 1.25, True, params, contacts,
                dict(groundSpeed_mps=0.95, strideLength_m=1.1875)))

    # 9 wait (4.4 loop): relieved standing, deep breathing, weight shift, look around
    def f_wait2(t, p):
        br = periodic(t, 4.4, 2)
        p["sp"] = 1.0 - 2.0 * br
        p["l_clav"] = 2.0 * br
        p["r_clav"] = 2.0 * br
        p["hx"] = 0.02 * periodic(t, 4.4, 1)
        p["hr"] = -1.5 * periodic(t, 4.4, 1)
        p["hdyaw"] = 18.0 * periodic(t, 4.4, 1, 1.3)
        p["hdp"] = -6.0 + 3.0 * periodic(t, 4.4, 1, 0.4)
        return p
    out.append(("lf_civilian_wait", 4.4, True) + standing_clip(cx, b, 4.4, f_wait2) + ({},))

    # 10 look_back (1.6): over the right shoulder and back
    keys = expand(b, [(0.0, {}), (0.55, dict(hdyaw=-62, nyaw=-20, syaw=-22, hyaw=-5, hdp=-4, l_fwd=6, r_fwd=-4)),
                      (1.0, {}), (1.6, dict(hdyaw=0, nyaw=0, syaw=0, hyaw=0, hdp=-2, l_fwd=3, r_fwd=3))])
    out.append(("lf_civilian_look_back", 1.6, False) + standing_clip(cx, b, 1.6, lambda t, p: keyed(keys, t)) + ({},))

    # 11 arrive (2.6): stop, look up at the settlement, deep relieved exhale
    keys = expand(b, [(0.0, dict(sp=4)), (0.7, dict(hdp=-18, np_=-6, sp=-4, l_clav=6, r_clav=6)),
                      (1.4, dict(hdp=-12, sp=6, l_clav=-2, r_clav=-2, hz=-0.012)), (2.0, dict(hdp=-6, sp=4, hz=-0.006)),
                      (2.6, dict(hdp=-2, sp=2, l_clav=0, r_clav=0, hz=0.0))])
    out.append(("lf_civilian_arrive", 2.6, False) + standing_clip(cx, b, 2.6, lambda t, p: keyed(keys, t)) + ({},))

    # 12 thank (2.3): restrained hand-on-heart and a small bow
    heart = np.array([0.055, cx.chest_y - 0.035, cx.sk.head("Chest")[2] + 0.06])
    kh = dict(b)
    kh.update(r_ik=dict(wrist=heart + np.array([-0.03, 0.0, -0.035]), elbow=(-0.8, 0.5, -0.5)), r_curl=0.2)
    keys = [(0.0, b), (0.5, dict(kh, sp=4, hdp=4)), (1.2, dict(kh, sp=14, hdp=12, np_=6)),
            (1.8, dict(kh, sp=6, hdp=2)), (2.3, b)]

    out.append(("lf_civilian_thank", 2.3, False) + standing_clip(cx, b, 2.3, lambda t, p: keyed(keys, t)) + ({},))
    return out


def soldier_clips(cx, b):
    out = []
    hz = cx.hz
    weapon = cx.weapon or "sword"
    show_r = 1.0 if weapon in ("spear",) else 0.0       # sword drawn only in combat; spear carried
    b = dict(b)
    b["prop_r"] = show_r
    b["prop_l"] = 1.0 if weapon in ("spear", "bow") else 0.0
    if weapon == "spear":            # spear upright in the right hand, shield on the left forearm
        b.update(r_fwd=14, r_elb=62, r_wr=-4, r_curl=0.9, l_fwd=10, l_elb=78, l_curl=0.8, l_add=b["l_add"] - 4)
    elif weapon == "bow":
        b.update(l_fwd=6, l_elb=20, l_curl=0.9)
    else:
        b.update(l_fwd=5, l_elb=14)

    # 1 idle (4.0 loop)
    def f_idle(t, p):
        br = periodic(t, 4.0, 2)
        p["sp"] = 1.5 - 1.5 * br
        p["hx"] = 0.015 * periodic(t, 4.0, 1)
        p["hr"] = -1.2 * periodic(t, 4.0, 1)
        p["hdyaw"] = 12.0 * periodic(t, 4.0, 1, 1.0)
        return p
    out.append(("lf_soldier_idle", 4.0, True) + standing_clip(cx, b, 4.0, f_idle) + ({},))
    # 2 walk (1.0 loop, 1.4 m/s)
    params, contacts = locomotion(cx, "walk", 1.0, 1.4, beta=0.61, lift=0.09, lean=3.0,
                                  arm_swing=16.0 if weapon != "spear" else 10.0, base_p=b)
    out.append(("lf_soldier_walk", 1.0, True, params, contacts, dict(groundSpeed_mps=1.4, strideLength_m=1.4)))
    # 3 jog (0.7 loop, 3.0 m/s) with a short flight phase
    bj = dict(b)
    bj.update(l_elb=b["l_elb"] + 50 if weapon != "spear" else b["l_elb"], r_elb=b["r_elb"] + 50 if weapon != "spear" else b["r_elb"])
    params, contacts = locomotion(cx, "jog", 0.7, 3.0, beta=0.40, lift=0.14, lean=9.0, arm_swing=26.0 if weapon != "spear" else 12.0,
                                  elbow=10.0, bob=0.035, sway=0.012, pelvis_yaw=8.0, heel=8.0, toeoff=38.0,
                                  base_p=bj, flight=0.6)
    out.append(("lf_soldier_jog", 0.7, True, params, contacts, dict(groundSpeed_mps=3.0, strideLength_m=2.1)))
    # 4 guard (3.2 loop): ready stance, weapon up, staggered feet
    g = dict(b)
    g.update(hz=-0.05, sp=8, hdp=-6, l_fx=0.02, l_fy=-0.12, r_fy=0.10, r_fx=-0.02, hyaw=-10, syaw=6,
             l_kout=8, r_kout=6, prop_r=1.0)
    if weapon == "sword":
        g.update(r_fwd=38, r_elb=70, r_wr=10, r_curl=0.95, r_add=b["r_add"] - 6, l_fwd=26, l_elb=60, l_curl=0.5)
    elif weapon == "spear":
        g.update(r_fwd=30, r_elb=70, r_curl=0.95, l_fwd=36, l_elb=86, l_add=b["l_add"] - 10)
    else:
        g.update(l_fwd=42, l_elb=30, l_add=b["l_add"] - 14, r_fwd=30, r_elb=95, r_curl=0.9)

    def f_guard(t, p):
        q = dict(g)
        q["hz"] = g["hz"] + 0.006 * periodic(t, 3.2, 2)
        q["sp"] = g["sp"] + 1.5 * periodic(t, 3.2, 2, 0.5)
        q["hdyaw"] = 6.0 * periodic(t, 3.2, 1)
        q["hx"] = 0.01 * periodic(t, 3.2, 1, 1.0)
        return q
    out.append(("lf_soldier_guard", 3.2, True) + standing_clip(cx, b, 3.2, f_guard) + ({},))
    # 5 attack (1.2; weapon_contact 0.65)
    if weapon == "sword":
        wind = dict(g, r_fwd=95, r_add=g["r_add"] - 25, r_elb=95, r_tw=-30, syaw=-22, hyaw=-18, sp=4)
        hit = dict(g, r_fwd=45, r_add=g["r_add"] + 25, r_elb=10, r_tw=20, syaw=26, hyaw=8, sp=18, l_fy=-0.20, hz=-0.08)
        follow = dict(hit, r_fwd=20, r_add=g["r_add"] + 35, syaw=30, sp=20)
    elif weapon == "spear":
        wind = dict(g, r_fwd=10, r_elb=110, syaw=-16, hyaw=-14, sp=2, r_fy=0.14)
        hit = dict(g, r_fwd=70, r_elb=5, syaw=18, hyaw=10, sp=16, l_fy=-0.22, hz=-0.08)
        follow = dict(hit, r_fwd=66, syaw=20, sp=18)
    else:   # bow: draw and release
        wind = dict(g, r_fwd=78, r_elb=140, r_add=g["r_add"] - 30, l_fwd=88, l_elb=6, l_add=g["l_add"] - 20, syaw=-30,
                    hyaw=-30, hdyaw=30, sp=2)
        hit = dict(wind, r_fwd=70, r_elb=150, r_add=g["r_add"] - 40)
        follow = dict(wind, r_fwd=40, r_elb=70, r_add=g["r_add"] - 10)
    keys = [(0.0, g), (0.42, wind), (0.65, hit), (0.85, follow), (1.2, g)]
    out.append(("lf_soldier_attack", 1.2, False) + standing_clip(cx, b, 1.2, lambda t, p: keyed(keys, t)) +
               (dict(markers={"weapon_contact": 0.65}),))
    # 6 hit (0.5): recoil and recover
    hk = dict(g, sp=-10, hdp=-16, hy=0.05, l_clav=8, r_clav=8, hz=-0.06, syaw=-8)
    keys = [(0.0, g), (0.12, hk), (0.5, g)]
    out.append(("lf_soldier_hit", 0.5, False) + standing_clip(cx, b, 0.5, lambda t, p: keyed(keys, t)) + ({},))
    # 7 death (2.0): stagger, knees give, fall to the side and lie still
    d1 = dict(g, sp=-12, hdp=-20, hy=0.06, hz=-0.10, l_fwd=20, r_fwd=30, prop_r=g["prop_r"])
    d2 = dict(d1, hz=-(hz * 0.55), hp=20, sp=30, hdp=20, hr=10, sr=12,
              l_kout=25, r_kout=25, l_kup=0.9, r_kup=0.9, l_fy=-0.05, r_fy=0.08, l_fwd=40, r_fwd=50, l_elb=50, r_elb=40)
    d3 = dict(d2, hz=-(hz - 0.13), hp=-70, hr=80, sp=10, sr=10, hdr=20, hx=0.30, hy=0.10,
              l_fwd=80, r_fwd=60, l_add=-10, r_add=10, l_elb=20, r_elb=30, l_fz=0.04, r_fz=0.10, l_fp=40, r_fp=30,
              l_kup=2.0, r_kup=2.0, l_kout=40, r_kout=10, prop_r=g["prop_r"])
    keys = [(0.0, g), (0.35, d1), (0.95, d2), (1.55, d3), (2.0, d3)]
    out.append(("lf_soldier_death", 2.0, False) + standing_clip(cx, b, 2.0, lambda t, p: keyed(keys, t)) + ({},))
    # 8 unlock (2.4; latch_release 1.6): reach to the socket (~1.25 m), insert, turn, step back
    slot = np.array([0.10, -0.55, 1.25])
    u0 = dict(b, prop_r=0.0)
    u1 = dict(u0, sp=10, hdp=6, l_fy=-0.10, hz=-0.02, r_ik=dict(wrist=slot + np.array([-0.04, 0.10, -0.03]), elbow=(-0.8, 0.4, -0.4)),
              r_curl=0.6)
    u2 = dict(u1, r_ik=dict(wrist=slot + np.array([-0.03, 0.04, -0.02]), elbow=(-0.8, 0.4, -0.4)), r_curl=0.8)
    u3 = dict(u2, r_ik=dict(wrist=slot + np.array([-0.03, 0.04, -0.02]), elbow=(-0.9, 0.2, 0.2),
                            hand_rot=None), r_tw=40, r_curl=0.9)
    u4 = dict(u0, sp=2, hy=0.04)
    keys = [(0.0, u0), (0.7, u1), (1.25, u2), (1.6, u3), (1.95, dict(u1, sp=6)), (2.4, u4)]
    out.append(("lf_soldier_unlock", 2.4, False) + standing_clip(cx, b, 2.4, lambda t, p: keyed(keys, t)) +
               (dict(markers={"latch_release": 1.6}),))
    # 9 help (2.8): offer an open hand (palm up), beckon, hold, return
    h0 = dict(b, prop_r=0.0)
    h1 = dict(h0, r_fwd=52, r_add=h0["r_add"] - 8, r_elb=28, r_tw=-70, r_curl=0.08, r_wr=-8, sp=8, hdp=4, l_fy=-0.08)
    h2 = dict(h1, r_elb=48, r_curl=0.3)
    keys = [(0.0, h0), (0.6, h1), (1.1, h2), (1.5, h1), (2.2, h1), (2.8, h0)]
    out.append(("lf_soldier_help", 2.8, False) + standing_clip(cx, b, 2.8, lambda t, p: keyed(keys, t)) + ({},))
    # 10 salute (1.8): fist to the heart + a nod
    heart = np.array([0.06, cx.chest_y - 0.03, cx.sk.head("Chest")[2] + 0.05])
    s0 = dict(b, prop_r=0.0)
    s1 = dict(s0, r_ik=dict(wrist=heart + np.array([-0.02, 0.0, -0.04]), elbow=(-0.8, 0.5, -0.4)), r_curl=1.0, sp=3,
              hdp=-2)
    s2 = dict(s1, sp=10, hdp=14, np_=6)
    keys = [(0.0, s0), (0.45, s1), (0.9, s2), (1.3, s1), (1.8, s0)]

    out.append(("lf_soldier_salute", 1.8, False) + standing_clip(cx, b, 1.8, lambda t, p: keyed(keys, t)) + ({},))
    return out
