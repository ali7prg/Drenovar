"""The 10 lf_orc_warden clips on the shared `human_shared` rig, authored with the hv2 pose-parameter
system (hv2_clips.make_pose / gait / keyed + hv2_anim IK solver) plus three orc additions:

* staff-driven arms: the staff is posed directly (grip point st_g*, axis tilt st_ax/st_ay, hand heading
  st_hd) and the right hand follows it by IK (st_r = 1); the left hand can take it (st_l, grip offset
  st_lo along the shaft); while the right hand is off the staff the PropR bone is placed in world space,
  so the staff mesh (rigidly skinned to PropR) never snaps;
* pointing hands (index straight, r_point / l_point);
* turns in place: the director yaws the node along rootYawDeg * smoothstep(t / T); planted feet are
  counter-rotated in the clip so they stay fixed in the world while each foot steps around.

All clips are in place, 30 fps; loops have identical first / last frames; one-shots start and end in the
idle pose (crossfade friendly)."""
import math

import numpy as np

import hv2_anim as A
import hv2_clips as HC
import spec_lf_orc_warden as SP
from hv2_anim import DEG, X, Y, Z, rot, smooth, smoother

FPS = A.FPS
GRIP = SP.STAFF["grip_from_bottom"]


def unit(v):
    v = np.asarray(v, float)
    return v / max(np.linalg.norm(v), 1e-12)


def frame_cols(a, b):
    a = unit(a)
    b = unit(b - (b @ a) * a)
    return np.stack([a, b, np.cross(a, b)], 1)


def slerp_m(Ra, Rb, t):
    qa, qb = A.matq(Ra), A.matq(Rb)
    if qa @ qb < 0:
        qb = -qb
    d = float(np.clip(qa @ qb, -1, 1))
    if d > 0.9995:
        q = qa + (qb - qa) * t
    else:
        th = math.acos(d)
        q = (math.sin((1 - t) * th) * qa + math.sin(t * th) * qb) / math.sin(th)
    q /= np.linalg.norm(q)
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def heading(deg_):
    """Horizontal direction, deg_ measured from forward (-Y) toward the character's left (+X)."""
    a = math.radians(deg_)
    return np.array([math.sin(a), -math.cos(a), 0.0])


class Staff:
    """Rest staff + hand frames (from the build) and the pose -> rigid staff transform."""

    def __init__(self, sk, info):
        st = info["staff"]
        hb = info["hand_bones"]
        self.u0 = unit(st["axis"])
        self.g0 = np.asarray(st["grip"], float)
        self.crystal0 = np.asarray(st["crystal"], float)
        self.d0 = {S: unit(hb[S]["_frame"][0]) for S in ("Left", "Right")}
        self.t0 = {S: unit(hb[S]["_frame"][1]) for S in ("Left", "Right")}
        self.grip0 = {S: np.asarray(hb[S]["_grip"], float) for S in ("Left", "Right")}
        self.wr0 = {S: sk.head(f"{S}Hand") for S in ("Left", "Right")}
        self.Rh0 = {S: sk.R[f"{S}Hand"][:3, :3] for S in ("Left", "Right")}
        self.Mprop0 = sk.R["PropR"].copy()

    def axis(self, p):
        return unit(np.array([p["st_ax"], p["st_ay"], 1.0]))

    def rigid(self, p):
        """R, t of the staff (rest -> posed): x' = R (x - g0) + G."""
        a = self.axis(p)
        h = heading(p["st_hd"])
        R = frame_cols(a, h) @ frame_cols(self.u0, self.d0["Right"]).T
        G = np.array([p["st_gx"], p["st_gy"], p["st_gz"]])
        return R, G

    def apply(self, p, x):
        R, G = self.rigid(p)
        return R @ (np.asarray(x, float) - self.g0) + G

    def matrix(self, p):
        R, G = self.rigid(p)
        M = np.eye(4)
        M[:3, :3] = R
        M[:3, 3] = G - R @ self.g0
        return M

    def right_target(self, p):
        R, G = self.rigid(p)
        return self.apply(p, self.wr0["Right"]), R

    def left_target(self, p):
        """Left fist on the shaft, st_lo metres along the axis from the right grip, heading st_lhd."""
        a = self.axis(p)
        R_s, G = self.rigid(p)
        GL = G + a * p["st_lo"]
        RL = frame_cols(a, heading(p["st_lhd"])) @ frame_cols(self.t0["Left"], self.d0["Left"]).T
        wrist = GL - RL @ (self.grip0["Left"] - self.wr0["Left"])
        return wrist, RL

    def planted_gz(self, p):
        """Grip height that puts the staff foot on the ground."""
        return GRIP * self.axis(p)[2] + 0.004


def staff_defaults():
    return dict(st_gx=-0.505, st_gy=-0.315, st_gz=GRIP, st_ax=-0.045, st_ay=-0.060, st_hd=18.0, st_r=1.0,
                st_l=0.0, st_lo=-0.24, st_lhd=-70.0, st_ex=-0.75, st_ey=0.55, st_ez=-0.30, st_lex=0.70,
                st_ley=0.45, st_lez=-0.45, r_point=0.0, l_point=0.0)


# --------------------------------------------------------------------------- pose

def make_pose(cx, p):
    """hv2 make_pose + staff-driven arms, world-placed PropR, pointing index, braid follows the head."""
    sk = cx.sk
    stf = cx.staff
    P = HC.make_pose(cx, p)
    sr, sl = float(p.get("st_r", 0.0)), float(p.get("st_l", 0.0))
    need_free = (0.0 < sr < 1.0) or (0.0 < sl < 1.0)
    Mfree = None
    if need_free:
        _, Mfree = A.solve(sk, HC.make_pose(cx, p))
    for S, w, tgt_fn, pole_k in (("Right", sr, stf.right_target, ("st_ex", "st_ey", "st_ez")),
                                 ("Left", sl, stf.left_target, ("st_lex", "st_ley", "st_lez"))):
        if w <= 0.0:
            continue
        wr_s, R_s = tgt_fn(p)
        pole_s = unit(np.array([p[k] for k in pole_k]))
        if w < 1.0:
            Mh = Mfree[f"{S}Hand"]
            wr_f = Mh[:3, 3]
            R_f = Mh[:3, :3] @ sk.R[f"{S}Hand"][:3, :3].T
            sh = Mfree[f"{S}UpperArm"][:3, 3]
            el = Mfree[f"{S}LowerArm"][:3, 3]
            pole_f = el - 0.5 * (sh + wr_f)
            pole_f = unit(pole_f) if np.linalg.norm(pole_f) > 1e-4 else pole_s
            ww = float(smooth(w))
            wrist = wr_f * (1 - ww) + wr_s * ww
            Rh = slerp_m(R_f, R_s, ww)
            pole = unit(pole_f * (1 - ww) + pole_s * ww)
        else:
            wrist, Rh, pole = wr_s, R_s, pole_s
        P.arm[S] = dict(wrist=wrist, elbow=pole, hand_rot=Rh, hand_local=False)
    if sr < 1.0:
        Mst = stf.matrix(p) @ stf.Mprop0
        P.world["PropR"] = (lambda M, Mn, Mst=Mst: Mst.copy())
    for s, S in (("r", "Right"), ("l", "Left")):
        k = float(p.get(f"{s}_point", 0.0))
        if k > 0:
            for b, ang in (("Index1", 10.0 + 30.0 * p[f"{s}_curl"]), ("Index2", 20.0 + 45.0 * p[f"{s}_curl"])):
                n = f"{S}{b}"
                P.r(n, rot(sk.R[n][:3, 0], k * ang * DEG))
    # the braided tail (Hood bone) turns with the head (parent Neck does not)
    P.r("Hood", rot(Z, 0.55 * (p["hdyaw"] + 0.5 * p["nyaw"]) * DEG))
    return P


# --------------------------------------------------------------------------- helpers

def base_idle(cx):
    b = HC.base(cx)
    b.update(staff_defaults())
    b.update(hz=-0.022, sp=5.0, np_=4.0, hdp=-9.0, l_fwd=7.0, l_elb=22.0, l_curl=0.38, l_wr=0.0, r_curl=1.2)
    for s, sx in (("l", 1.0), ("r", -1.0)):
        b[f"{s}_fx"] = sx * 0.022
        b[f"{s}_kout"] = 6.0
    b["st_gz"] = cx.staff.planted_gz(b)
    return b


def stepped(t, t0, t1, h):
    """Foot lift for a step in [t0, t1]: (lift, progress)."""
    if t <= t0 or t >= t1:
        return 0.0, (0.0 if t <= t0 else 1.0)
    u = (t - t0) / (t1 - t0)
    return h * math.sin(math.pi * u) ** 1.2, float(smoother(u))


def plant_staff(cx, p):
    p["st_gz"] = cx.staff.planted_gz(p)
    return p


def keyed_clip(cx, b, sec, keys, post=None, ease=smoother):
    times = HC.frames_for(sec)
    params = []
    for t in times:
        q = HC.keyed(keys, t, ease)
        if post:
            q = post(t, q)
        params.append(q)
    contacts = [{S: (True, None, "flat") for S in ("Left", "Right")} for _ in times]
    return params, contacts


# --------------------------------------------------------------------------- clips

def build_clips(cx):
    HC.CTX[0] = cx
    out = []
    b = base_idle(cx)
    out.append(idle(cx, b))
    out.append(walk(cx, b))
    out.append(turn(cx, b, +1))
    out.append(turn(cx, b, -1))
    out.append(order_point(cx, b, "lf_orc_order_point", right=True))
    out.append(order_point(cx, b, "lf_orc_order_point_left", right=False))
    out.append(talk(cx, b))
    out.append(drain(cx, b))
    out.append(roar(cx, b))
    out.append(look(cx, b))
    return out


def idle(cx, b, sec=3.2):
    def f(t, p):
        br = HC.periodic(t, sec, 2)                 # two heavy breaths per loop
        ws = HC.periodic(t, sec, 1)
        p["sp"] = b["sp"] - 2.2 * br
        p["np_"] = b["np_"] + 1.2 * br
        p["l_clav"] = 3.5 * max(br, -0.3)
        p["r_clav"] = 3.5 * max(br, -0.3)
        p["hz"] = b["hz"] + 0.005 * br
        p["hx"] = 0.022 * ws
        p["hr"] = -1.6 * ws
        p["sr"] = 1.4 * ws
        p["hdyaw"] = 7.0 * HC.periodic(t, sec, 1, 1.1)
        p["hdp"] = b["hdp"] + 2.0 * HC.periodic(t, sec, 2, 0.6)
        p["l_fwd"] = b["l_fwd"] + 1.5 * br
        p["st_hd"] = b["st_hd"] + 2.0 * ws
        return p
    params, contacts = HC.standing_clip(cx, b, sec, f)
    return ("lf_orc_idle", sec, True, params, contacts, {})


def walk(cx, b, T=32.0 / 30.0, v=SP.WALK_SPEED):
    bw = dict(b)
    bw.update(sp=9.0, hdp=-12.0, np_=5.0, l_fwd=5.0, l_elb=26.0, l_curl=0.5, st_hd=10.0)
    params, contacts = HC.locomotion(cx, "walk", T, v, beta=0.60, lift=0.10, step_w=0.185, lean=4.0, bob=0.030,
                                     sway=0.046, pelvis_yaw=7.0, arm_swing=13.0, elbow=12.0, heel=6.0, toeoff=18.0,
                                     base_p=bw)
    times = HC.frames_for(T)
    out = []
    for t, p in zip(times, params):
        w = 2 * math.pi * t / T
        # heavy stomp: quick extra settle + spine give after each heel strike (phase 0 and 0.5)
        imp = 0.0
        for tc in (0.0, T / 2, T):
            dt = t - tc
            if 0 <= dt < 0.25:
                imp += math.exp(-dt / 0.07) * (1 - math.exp(-dt / 0.02))
        p["hz"] -= 0.013 * imp
        p["sp"] += 2.5 * imp
        p["hdp"] += 1.5 * imp
        p["sr"] = p.get("sr", 0.0) + 3.0 * math.sin(w - 0.4)        # shoulders roll over the stance leg
        # staff carried in the right fist, swinging with the arm, foot clear of the ground
        p["st_gx"] = -0.50 + p["hx"] * 0.9
        p["st_gy"] = -0.20 - 0.085 * math.cos(w)
        p["st_gz"] = 1.25 + p["hz"] * 0.9
        p["st_ax"] = -0.07
        p["st_ay"] = -0.20 - 0.08 * math.cos(w)
        out.append(p)
    return ("lf_orc_walk", T, True, out, contacts,
            dict(groundSpeed_mps=v, strideLength_m=round(v * T, 4), markers={"step_l": 0.0, "step_r": round(T / 2, 4)}))


def turn(cx, b, sgn, sec=1.0):
    """sgn +1 = turn left (+90 deg about +Z), -1 = right.  Lead foot = the one on the turning side."""
    yaw_total = 90.0 * sgn
    lead, trail = ("Left", "Right") if sgn > 0 else ("Right", "Left")
    steps = [(lead, 0.05, 0.34, 0.0, 50.0 * sgn), (trail, 0.36, 0.67, 0.0, yaw_total),
             (lead, 0.68, 0.95, 50.0 * sgn, yaw_total)]
    times = HC.frames_for(sec)
    params, contacts, world_feet = [], [], []
    for t in times:
        Yn = yaw_total * float(smooth(t / sec))          # node yaw applied by the director
        Yb = yaw_total * float(smooth(min(1.0, t / (0.82 * sec))))   # body leads the node
        lead_deg = Yb - Yn
        p = dict(b)
        feet = {}
        planted = {}
        for S in ("Left", "Right"):
            th = 0.0
            lift = 0.0
            moving = False
            for (FS, t0, t1, a0, a1) in steps:
                if FS != S:
                    continue
                if t >= t1:
                    th = a1
                elif t > t0:
                    lf, u = stepped(t, t0, t1, 0.075)
                    th = a0 + (a1 - a0) * u
                    lift = lf
                    moving = True
                    break
                else:
                    th = a0 if t0 > 0.5 else th
                    break
            s_ = "l" if S == "Left" else "r"
            sx = 1.0 if S == "Left" else -1.0
            rest = cx.ank[S] + np.array([b[f"{s_}_fx"], b[f"{s_}_fy"], 0.0])
            wpos = rot(Z, th * DEG) @ rest
            loc = rot(Z, -Yn * DEG) @ wpos
            p[f"{s_}_fx"] = loc[0] - cx.ank[S][0]
            p[f"{s_}_fy"] = loc[1] - cx.ank[S][1]
            p[f"{s_}_fz"] = lift
            p[f"{s_}_fyaw"] = th - Yn
            p[f"{s_}_fp"] = -10.0 * math.sin(math.pi * min(1.0, lift / 0.075)) if moving else 0.0
            p[f"{s_}_kout"] = b[f"{s_}_kout"] + sx * (th - Yn) * 0.8
            feet[S] = wpos
            planted[S] = (not moving, None, "flat")
        # pelvis over the support foot, body / head lead into the turn
        sup = None
        for (FS, t0, t1, a0, a1) in steps:
            if t0 - 0.06 <= t <= t1 + 0.04:
                sup = "Right" if FS == "Left" else "Left"
        if sup:
            s_ = "l" if sup == "Left" else "r"
            tgt_x = cx.ank[sup][0] + p[f"{s_}_fx"]
            p["hx"] = 0.28 * tgt_x
        else:
            p["hx"] = 0.0
        p["hyaw"] = lead_deg * 0.55
        p["syaw"] = lead_deg * 0.45
        p["hdyaw"] = lead_deg * 0.9 + 12.0 * sgn * math.sin(math.pi * t / sec)
        p["hz"] = b["hz"] - 0.025 * math.sin(math.pi * t / sec)
        p["sp"] = b["sp"] + 3.0 * math.sin(math.pi * t / sec)
        # staff carried with the body (lifted a hand's width while stepping)
        Rb = rot(Z, lead_deg * 0.6 * DEG)
        g = Rb @ np.array([b["st_gx"], b["st_gy"], b["st_gz"]])
        p["st_gx"], p["st_gy"] = g[0], g[1]
        p["st_gz"] = b["st_gz"] + 0.07 * math.sin(math.pi * t / sec) ** 0.7
        p["st_hd"] = b["st_hd"] + lead_deg * 0.6
        params.append(p)
        contacts.append(planted)
        world_feet.append(feet)
    params[0] = dict(b)
    params[-1] = dict(b)
    name = "lf_orc_turn_left" if sgn > 0 else "lf_orc_turn_right"
    meta = dict(rootYawDeg=yaw_total,
                yawCurve=f"yaw(t) = rootYawDeg * smoothstep(t/{sec}) about the root origin (apply to the node while "
                         "the clip plays; planted feet stay fixed in that yawed world frame)",
                markers={f"step_{i + 1}": round(t1, 3) for i, (_, t0, t1, _, _) in enumerate(steps)})
    return (name, sec, False, params, contacts, meta)


def order_point(cx, b, name, right=True, sec=2.6, t_ext=1.05, t_hold=2.05):
    sk = cx.sk
    side = "Right" if right else "Left"
    sx = -1.0 if right else 1.0
    s_ = "r" if right else "l"
    sh = sk.head(f"{side}UpperArm")
    L = sk.length[f"{side}UpperArm"] + sk.length[f"{side}LowerArm"]
    d = heading(sx * -SP.POINT_DEG * -1.0) if False else np.array([sx * math.sin(math.radians(SP.POINT_DEG)),
                                                                   -math.cos(math.radians(SP.POINT_DEG)), 0.06])
    d = unit(d)
    yaw_body = sx * 24.0                     # torso squares up toward the target
    sh_rot = rot(Z, yaw_body * 0.85 * DEG) @ (sh - np.array([0, 0.03, 0])) + np.array([0, 0.03, 0])
    wrist = sh_rot + d * (L * 0.93)
    point_ik = dict(wrist=wrist, elbow=(sx * 0.15, 0.25, -1.0))
    reach_ik = dict(wrist=sh_rot + unit(d + np.array([0, 0.25, -0.55])) * (L * 0.55), elbow=(sx * 0.4, 0.5, -0.8))
    k0 = dict(b)
    body = dict(syaw=yaw_body, hyaw=yaw_body * 0.30, hdyaw=yaw_body * 1.15, nyaw=yaw_body * 0.35, sp=b["sp"] + 4.0,
                hdp=b["hdp"] - 6.0, np_=b["np_"] + 2.0)
    keys = []
    if right:
        # hand-over through the front-centre: the right fist brings the staff in front of the belly, the left
        # fist takes it above the right (0.30-0.44), the right lets go (0.44-0.56), the left plants it front-left
        # (0.56-0.82); reversed after the hold (2.00-2.60)
        kc = dict(k0, st_gx=-0.17, st_gy=-0.43, st_ax=0.0, st_ay=-0.05, st_hd=40.0, st_lo=0.15, st_lhd=-50.0,
                  sp=b["sp"] + 2.0)
        kl = dict(kc, st_l=1.0, st_r=0.0, st_gx=0.31, st_gy=-0.40, st_ax=0.03, st_ay=-0.05, st_lhd=-25.0,
                  r_ik=reach_ik, r_curl=0.6, **{k: body[k] * 0.5 for k in body})
        k_ext = dict(kl, r_ik=point_ik, r_curl=0.95, r_point=1.0, **body)
        k_hold = dict(k_ext, hdp=k_ext["hdp"] + 2.0, sp=k_ext["sp"] + 1.0)
        k_back = dict(kc, st_l=1.0, st_r=0.0, r_ik=reach_ik, r_curl=0.6)
        keys = [(0.0, k0), (0.30, kc), (0.44, dict(kc, st_l=1.0)),
                (0.56, dict(kc, st_l=1.0, st_r=0.0, r_ik=reach_ik, r_curl=0.6)), (0.82, kl), (t_ext, k_ext),
                (t_hold, k_hold), (2.18, k_back), (2.28, dict(kc, st_l=1.0, st_r=1.0)),
                (2.38, dict(kc, st_l=0.0, st_r=1.0)), (sec, k0)]

        def lift(t):
            up = smooth(t / 0.15) * (1 - smooth((t - 0.70) / 0.12))
            up2 = smooth((t - t_hold) / 0.10) * (1 - smooth((t - 2.45) / 0.15))
            return 0.05 * (up + up2)

        def post(t, q):
            q["st_gz"] = cx.staff.planted_gz(q) + lift(t)
            return q
    else:
        k_brace = dict(k0, st_gx=b["st_gx"] - 0.03, st_hd=b["st_hd"] + 8.0)
        k_brace = plant_staff(cx, k_brace)
        k_ext = dict(k_brace, l_ik=point_ik, l_curl=0.95, l_point=1.0, **body)
        k_hold = dict(k_ext, hdp=k_ext["hdp"] + 2.0, sp=k_ext["sp"] + 1.0)
        k_low = dict(k_brace, l_ik=reach_ik, l_curl=0.6)
        keys = [(0.0, k0), (0.52, dict(k_brace, l_ik=reach_ik, l_curl=0.6, **{k: body[k] * 0.4 for k in body})),
                (t_ext, k_ext), (t_hold, k_hold), (2.30, k_low), (sec, k0)]

        def post(t, q):
            return plant_staff(cx, q)
    params, contacts = keyed_clip(cx, b, sec, keys, post)
    params[0] = dict(b)
    params[-1] = dict(b)
    return (name, sec, False, params, contacts, dict(markers={"point": t_ext}))


def talk(cx, b, sec=3.0):
    g0 = dict(b)
    g1 = dict(b, l_fwd=34.0, l_elb=78.0, l_tw=-55.0, l_curl=0.10, l_add=b["l_add"] - 4.0, l_wr=-6.0)
    g2 = dict(b, l_fwd=46.0, l_elb=38.0, l_tw=-20.0, l_curl=0.30, l_add=b["l_add"] - 2.0, sp=b["sp"] + 5.0)
    g3 = dict(b, l_fwd=30.0, l_elb=58.0, l_tw=-75.0, l_curl=0.05, l_add=b["l_add"] - 22.0)
    g4 = dict(b, l_fwd=26.0, l_elb=86.0, l_tw=-30.0, l_curl=0.75, l_add=b["l_add"] - 6.0, sp=b["sp"] + 3.0)
    keys = [(0.0, g0), (0.45, g1), (0.95, g2), (1.45, g3), (2.10, g4), (2.55, dict(b, l_fwd=14.0, l_elb=34.0)),
            (sec, g0)]

    def post(t, p):
        p["hdp"] = p["hdp"] + 4.0 * HC.periodic(t, sec, 4) + 1.5 * HC.periodic(t, sec, 8, 0.7)   # speaking rhythm
        p["np_"] = p["np_"] + 1.5 * HC.periodic(t, sec, 4, 0.4)
        p["hdyaw"] = 9.0 * HC.periodic(t, sec, 1, 0.5)
        p["hdr"] = 3.0 * HC.periodic(t, sec, 2, 1.0)
        p["syaw"] = 6.0 * HC.periodic(t, sec, 1, 1.3)
        p["hx"] = 0.015 * HC.periodic(t, sec, 1)
        p["sp"] = p["sp"] + 1.5 * HC.periodic(t, sec, 2, 0.3)
        p["st_hd"] = b["st_hd"] + 3.0 * HC.periodic(t, sec, 1, 0.3)
        return p
    params, contacts = keyed_clip(cx, b, sec, keys, post)
    params[-1] = params[0]
    return ("lf_orc_talk", sec, True, params, contacts, {})


def drain(cx, b, sec=3.2, t_start=0.90, t_peak=1.90, t_end=2.70):
    stance = dict(b, l_fy=-0.20, l_fx=b["l_fx"] + 0.03, r_fy=0.10, r_fx=b["r_fx"] - 0.03, hz=-0.075, l_kout=10.0,
                  r_kout=8.0, hyaw=-6.0)
    lift = dict(stance, st_gx=-0.30, st_gy=-0.48, st_gz=1.42, st_ax=0.05, st_ay=-0.85, st_hd=60.0, sp=b["sp"] + 9.0,
                hdp=b["hdp"] - 12.0, st_ex=-0.8, st_ey=0.35, st_ez=-0.5,
                l_fwd=70.0, l_elb=16.0, l_add=b["l_add"] + 4.0, l_tw=-10.0, l_curl=0.05, l_wr=-30.0, l_clav=6.0)
    peak = dict(lift, st_gy=-0.56, st_gz=1.50, st_ay=-0.95, sp=b["sp"] + 13.0, l_fwd=76.0, l_elb=8.0, hz=-0.085, l_clav=9.0,
                r_clav=6.0)
    rel = dict(lift, st_gy=-0.45, st_gz=1.36, sp=b["sp"] + 6.0, l_fwd=55.0, l_elb=30.0, l_curl=0.4)
    keys = [(0.0, b), (0.30, dict(stance, **{k: b[k] for k in ("st_gx", "st_gy", "st_gz")})), (0.62, lift),
            (t_start, lift), (t_peak, peak), (t_end, rel), (sec, b)]

    def post(t, p):
        # strain tremor while draining (ramps up to the peak, fades by the end)
        k = 0.0
        if t_start < t < t_end:
            k = math.sin(math.pi * (t - t_start) / (t_end - t_start))
        p["st_gx"] += 0.004 * k * math.sin(t * 2 * math.pi * 7.0)
        p["st_gz"] += 0.004 * k * math.sin(t * 2 * math.pi * 9.0 + 1.0)
        p["sp"] += 1.0 * k * math.sin(t * 2 * math.pi * 5.0)
        p["l_fwd"] += 1.5 * k * math.sin(t * 2 * math.pi * 6.0 + 0.5)
        # feet step into / out of the braced stance
        for s_, (t0, t1) in (("l", (0.06, 0.34)), ("r", (0.30, 0.56))):
            lf, _ = stepped(t, t0, t1, 0.06)
            lf2, _ = stepped(t, t_end + 0.05, sec - 0.08, 0.05) if s_ == "l" else stepped(t, t_end - 0.10, t_end + 0.12, 0.05)
            p[f"{s_}_fz"] = lf + lf2
        if t < 0.30 or t > t_end + 0.25:
            p = plant_staff(cx, p)
        return p
    params, contacts = keyed_clip(cx, b, sec, keys, post)
    params[0] = dict(b)
    params[-1] = dict(b)
    return ("lf_orc_drain", sec, False, params, contacts,
            dict(markers={"drain_start": t_start, "drain_peak": t_peak, "drain_end": t_end}))


def roar(cx, b, sec=2.0, t_roar=0.75):
    wind = dict(b, hz=-0.07, sp=b["sp"] + 14.0, hdp=b["hdp"] + 14.0, np_=b["np_"] + 6.0, l_fwd=18.0, l_elb=60.0,
                l_curl=0.8, l_add=b["l_add"] + 4.0, st_gy=b["st_gy"] + 0.04, l_clav=-3.0, r_clav=-3.0)
    wind = plant_staff(cx, wind)
    big = dict(b, hz=0.0, sp=b["sp"] - 16.0, np_=b["np_"] - 10.0, hdp=b["hdp"] - 26.0, hp=-4.0,
               l_fwd=30.0, l_add=-50.0, l_elb=42.0, l_tw=-35.0, l_curl=0.55, l_clav=14.0, r_clav=14.0,
               st_gx=-0.70, st_gy=-0.12, st_gz=1.80, st_ax=-0.55, st_ay=-0.08, st_hd=-20.0, st_ex=-0.9, st_ey=0.1,
               st_ez=-0.45)
    hold = dict(big, hdp=big["hdp"] - 3.0, sp=big["sp"] - 2.0)
    keys = [(0.0, b), (0.34, wind), (t_roar, big), (1.30, hold), (1.70, dict(b, sp=b["sp"] + 3.0)), (sec, b)]

    def post(t, p):
        if t_roar - 0.05 < t < 1.35:
            k = math.sin(math.pi * (t - t_roar + 0.05) / 0.65)
            p["hdr"] += 2.0 * k * math.sin(t * 2 * math.pi * 11.0)
            p["sp"] += 0.8 * k * math.sin(t * 2 * math.pi * 8.0)
        if t < 0.34 or t > 1.75:
            p = plant_staff(cx, p)
        return p
    params, contacts = keyed_clip(cx, b, sec, keys, post)
    params[0] = dict(b)
    params[-1] = dict(b)
    return ("lf_orc_roar", sec, False, params, contacts, dict(markers={"roar": t_roar}))


def look(cx, b, sec=2.4):
    lft = dict(b, hdyaw=52.0, nyaw=16.0, syaw=16.0, hyaw=4.0, hdp=b["hdp"] - 2.0, sp=b["sp"] + 3.0, hdr=-4.0)
    rgt = dict(b, hdyaw=-52.0, nyaw=-16.0, syaw=-16.0, hyaw=-4.0, hdp=b["hdp"] - 2.0, sp=b["sp"] + 3.0, hdr=4.0)
    keys = [(0.0, b), (0.45, lft), (0.95, dict(lft, hdyaw=58.0, hdp=b["hdp"] + 2.0)), (1.50, rgt),
            (1.95, dict(rgt, hdyaw=-58.0, hdp=b["hdp"] + 2.0)), (sec, b)]
    params, contacts = keyed_clip(cx, b, sec, keys, lambda t, p: plant_staff(cx, p))
    params[0] = dict(b)
    params[-1] = dict(b)
    return ("lf_orc_look", sec, False, params, contacts, dict(markers={"look_left": 0.95, "look_right": 1.95}))
