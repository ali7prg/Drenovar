"""The 10 guide-horse clips (animation_manifest group `guide_horse`), built on horse_anim.

Each clip function returns dict(name, T, loop, frames=[Pose...], times, root=[(pos, yaw)...],
meta) where the root trajectory is the *virtual* gameplay root used for footstep planning
(exported clips are in place).
"""
import math

import numpy as np

import horse_anim as HA
from horse_anim import DEG, Pose, bump, env, smooth, smoother

LEGS = ("F_L", "F_R", "H_L", "H_R")
HIP_Y = 0.47
SHOULDER_Y = -0.62

WALK = dict(T=1.2, v=1.30, duty=0.60, offsets={"H_L": 0.0, "F_L": 0.25, "H_R": 0.5, "F_R": 0.75},
            lift={"F": 0.115, "H": 0.095}, knee=62 * DEG, fet_swing=0.75, fet_load=0.18,
            swing_pitch=0.85)
TROT = dict(T=0.72, v=3.2, duty=0.38, offsets={"F_L": 0.0, "H_R": 0.0, "F_R": 0.5, "H_L": 0.5},
            lift={"F": 0.19, "H": 0.17}, knee=80 * DEG, fet_swing=0.9, fet_load=0.30,
            swing_pitch=1.05)


# --------------------------------------------------------------------------- helpers

def leg_ik(cb, leg, st, toe_rest_y):
    """Plan state (root space) -> IK params with scapula/cannon angles from the leg sweep."""
    fh = leg[0]
    toe = st["toe"]
    prm = dict(toe=np.array(toe, float), pitch=st["pitch"], yaw=st["yaw"], fet=st["fet"],
               knee=st["knee"] if fh == "F" else 0.0, _stance=st["stance"])
    if fh == "F":
        prm["scap"] = 0.32 * (math.atan2(toe[1] - SHOULDER_Y, 1.1) -
                              math.atan2(toe_rest_y - SHOULDER_Y, 1.1))
        prm["scap"] -= 0.10 * max(st["knee"], 0.0)
    else:
        sw = st["swing"]
        flex = 0.42 * math.sin(math.pi * min(1.0, sw / 0.85)) if sw >= 0 else 0.0
        prm["cannon"] = 0.90 * (math.atan2(toe[1] - HIP_Y, 1.1) -
                                math.atan2(toe_rest_y - HIP_Y, 1.1)) + flex
    return prm


def body(pose, dx=0.0, dy=0.0, dz=0.0, pitch=0.0, roll=0.0, yaw=0.0):
    pose.loc["spine_02"] = np.array([dx, dy, dz])
    if yaw:
        pose.add_rot("spine_02", (0, 0, 1), yaw)
    if pitch:
        pose.add_rot("spine_02", (1, 0, 0), pitch)
    if roll:
        pose.add_rot("spine_02", (0, 1, 0), roll)


def neck(pose, pitch=0.0, yaw=0.0, roll=0.0, w=(0.30, 0.30, 0.25, 0.15), head_pitch=0.0,
         head_roll=0.0):
    for b, k in zip(("neck_01", "neck_02", "neck_03", "head"), w):
        if yaw:
            pose.add_rot(b, (0, 0, 1), yaw * k)
        if pitch:
            pose.add_rot(b, (1, 0, 0), pitch * k)
    if head_pitch:
        pose.add_rot("head", (1, 0, 0), head_pitch)
    if roll or head_roll:
        pose.add_rot("head", (0, 1, 0), roll + head_roll)


def ears(pose, skel, l_back=0.0, r_back=0.0, l_out=0.0, r_out=0.0):
    for s, back, out, sx in (("L", l_back, l_out, 1), ("R", r_back, r_out, -1)):
        b = f"ear_{s}"
        if back:
            pose.toward(skel, b, (0, 1, 0), back)
        if out:
            pose.toward(skel, b, (sx, 0, 0), out)


TAIL_STREAM_W = (0.30, 0.25, 0.17, 0.12, 0.09, 0.07)


def tail_pose(pose, skel, lift=0.0, swish=0.0, lag_swish=None, lift_chain=None, stream=0.0):
    """lift: raise the dock (bones 1-2); the hair (bones 3-6) hangs back down under gravity
    so a carried tail arcs like a plume instead of rotating as a rigid stick."""
    names = [f"tail_{i:02d}" for i in range(1, 7)]
    d0 = skel.R["tail_02"][:3, 1]
    axis = np.cross(d0, np.array([0.0, 1.0, 0.3]))          # one lift axis for the chain
    for i, n in enumerate(names):
        if lift_chain is not None:
            li = lift_chain[i]
        else:   # dock carries the lift, the hair hangs back toward vertical (gravity)
            li = lift * (0.65 if i == 0 else 0.45) if i < 2 else -lift * (0.30 if i == 2 else 0.22)
        if stream:   # locomotion: the whole tail flows out behind (walk/trot drawings)
            li += stream * TAIL_STREAM_W[i]
        if li:
            pose.add_rot(n, axis, li)
        sw = lag_swish[i] if lag_swish is not None else swish * (0.35 + 0.15 * i)
        if sw:
            pose.toward(skel, n, (1, 0, 0), sw)


def mane(pose, skel, lift_l, lift_r, swing=0.0):
    for s, lift in (("L", lift_l), ("R", lift_r)):
        for i in range(1, 5):
            b = f"mane_{s}_{i:02d}"
            if lift:
                pose.toward(skel, b, (0, 0, 1), lift * (0.7 + 0.1 * i))
            if swing:
                pose.toward(skel, b, (0, 1, 0), swing)


def ribbon(pose, skel, fwd, side):
    for i, b in enumerate(("ribbon_01", "ribbon_02", "ribbon_03")):
        k = (0.55, 0.30, 0.25)[i]
        if fwd:
            pose.toward(skel, b, (0, 1 if fwd > 0 else -1, 0), abs(fwd) * k)
        if side:
            pose.toward(skel, b, (1 if side > 0 else -1, 0, 0), abs(side) * k)


def standing_ik(cb):
    return {leg: dict(toe=np.array([cb.toe0[leg][0], cb.toe0[leg][1], 0.0]), pitch=0.0, yaw=0.0,
                      fet=0.0, knee=0.0, scap=0.0, cannon=0.0, _stance=0.5) for leg in LEGS}


def secondary(cb, frames, times, loop, root=None, tail_amp=1.0, ribbon_amp=1.0, mane_amp=1.0,
              tail_phase=None):
    """Spring follow-through for ribbon, mane and tail from the primary motion."""
    dt = times[1] - times[0]
    # primary FK pass to sample attachment points
    ring_p, neck_p, pel = [], [], []
    for k, pose in enumerate(frames):
        _, M = HA.fk_and_basis(cb.skel, pose, cb.legs)
        rp = np.zeros(3) if root is None else np.array([root[k][0][0], root[k][0][1], 0.0])
        ring_p.append(M["ribbon_01"][:3, 3] + rp if "ribbon_01" in M else
                      M["head"][:3, 3] + rp)
        neck_p.append(M["neck_02"][:3, 3] + rp)
        pel.append(M["pelvis"][:3, 3] + rp)
    ring_p, neck_p, pel = map(np.array, (ring_p, neck_p, pel))
    from scipy import ndimage as ndi
    if loop:   # one period (last sample duplicates the first), wrap, then close the loop
        ring_p, neck_p, pel = (np.concatenate([ndi.gaussian_filter1d(a[:-1], 2.0, axis=0, mode="wrap")] * 1 +
                                              [ndi.gaussian_filter1d(a[:-1], 2.0, axis=0, mode="wrap")[:1]])
                               for a in (ring_p, neck_p, pel))
    else:
        ring_p, neck_p, pel = (ndi.gaussian_filter1d(a, 2.0, axis=0, mode="nearest")
                               for a in (ring_p, neck_p, pel))
    g = 9.81
    a_ring = np.stack([HA.accel(ring_p[:, i], dt) for i in range(3)], 1)
    a_neck = HA.accel(neck_p[:, 2], dt)
    a_pel = np.stack([HA.accel(pel[:, i], dt) for i in range(3)], 1)
    # ribbon pendulum: tip lags opposite to the acceleration (+gravity coupling)
    rib_fwd = HA.spring_track(-a_ring[:, 1] / g, dt, freq=1.6, zeta=0.25, gain=(2 * math.pi * 1.6) ** 2,
                              periodic=loop)
    rib_side = HA.spring_track(-a_ring[:, 0] / g, dt, freq=1.5, zeta=0.25,
                               gain=(2 * math.pi * 1.5) ** 2, periodic=loop)
    rib_fwd += HA.spring_track(-a_ring[:, 2] / g * 0.3, dt, freq=2.0, zeta=0.3,
                               gain=(2 * math.pi * 2.0) ** 2, periodic=loop)
    mane_l = HA.spring_track(-a_neck / g, dt, freq=2.4, zeta=0.3, gain=(2 * math.pi * 2.4) ** 2,
                             periodic=loop)
    tail_sw = HA.spring_track(-a_pel[:, 0] / g, dt, freq=1.1, zeta=0.3, gain=(2 * math.pi * 1.1) ** 2,
                              periodic=loop)
    tail_up = HA.spring_track(-a_pel[:, 2] / g, dt, freq=1.8, zeta=0.35,
                              gain=(2 * math.pi * 1.8) ** 2, periodic=loop)
    for k, pose in enumerate(frames):
        ribbon(pose, cb.skel, np.clip(0.5 * rib_fwd[k], -0.25, 0.25) * ribbon_amp,
               np.clip(0.5 * rib_side[k], -0.22, 0.22) * ribbon_amp)
        m = np.clip(0.35 * mane_l[k], -0.10, 0.10) * mane_amp
        mane(pose, cb.skel, m, m)
        # tail: cascade lag along the chain
        if tail_phase is not None:
            # locomotion: phase-locked swing with lag down the chain (exactly periodic)
            ph = times[k] / times[-1]
            lag = [tail_phase[0] * DEG * math.sin(2 * math.pi * (ph - 0.12 - 0.05 * i)) * (0.5 + 0.12 * i)
                   for i in range(6)]
            lift = [tail_phase[1] * DEG * math.sin(2 * math.pi * (tail_phase[2] * ph - 0.2 - 0.06 * i))
                    * (0.6 if i < 2 else 0.35) for i in range(6)]
        else:
            lag = [np.clip(0.5 * tail_sw[max(0, k - 2 * i)], -0.10, 0.10) * tail_amp * (0.5 + 0.12 * i)
                   for i in range(6)]
            lift = [np.clip(0.5 * tail_up[k], -0.05, 0.05) * tail_amp * (0.6 if i < 2 else 0.3)
                    for i in range(6)]
        tail_pose(pose, cb.skel, lag_swish=lag, lift_chain=lift)


# --------------------------------------------------------------------------- locomotion loops

def gait_loop(cb, G, name):
    T, v, duty = G["T"], G["v"], G["duty"]
    times = cb.times(T)
    toesN = cb.neutral_toes()
    plans = {}
    for leg in LEGS:
        c = HA.periodic_plan(T, v, duty, G["offsets"][leg], toesN[leg])
        plans[leg] = HA.LegPlan(c, lift=G["lift"][leg[0]], knee=G["knee"] if leg[0] == "F" else 0.0,
                                fet_swing=G["fet_swing"], fet_load=G["fet_load"],
                                swing_pitch=G["swing_pitch"])
    frames, root = [], []
    trot = name == "lf_horse_trot"
    for t in times:
        ph = t / T
        rp = np.array([0.0, -v * t])
        pose = Pose()
        for leg in LEGS:
            st = cb.root_space(plans[leg].state(t), rp, 0.0)
            pose.ik[leg] = leg_ik(cb, leg, st, cb.toe0[leg][1])
        if trot:
            # lowest at mid-stance of each diagonal, high in the suspension
            dz = -0.030 * math.cos(4 * math.pi * (ph - duty / 2)) - 0.012
            body(pose, dx=0.004 * math.sin(2 * math.pi * ph), dz=dz,
                 pitch=0.9 * DEG * math.sin(4 * math.pi * ph), roll=1.2 * DEG * math.sin(2 * math.pi * ph))
            neck(pose, pitch=13 * DEG + 2.5 * DEG * math.cos(4 * math.pi * (ph - 0.1)),
                 yaw=1.0 * DEG * math.sin(2 * math.pi * ph), head_pitch=-7 * DEG)
            pose.add_rot("pelvis", (0, 1, 0), 2.5 * DEG * math.sin(2 * math.pi * (ph + 0.25)))
            pose.add_rot("spine_03", (0, 1, 0), -1.5 * DEG * math.sin(2 * math.pi * (ph + 0.25)))
            tail_base, tail_stream = 12 * DEG, 40 * DEG
            ears(pose, cb.skel, l_back=-4 * DEG, r_back=-4 * DEG)
        else:
            # walk: two dips per stride, lateral sway, head nod synced with fore stance
            dz = -0.011 * math.cos(4 * math.pi * (ph - 0.12)) - 0.006
            body(pose, dx=0.012 * math.sin(2 * math.pi * (ph - 0.05)), dz=dz,
                 pitch=0.6 * DEG * math.sin(4 * math.pi * ph), roll=1.0 * DEG * math.sin(2 * math.pi * ph),
                 yaw=0.8 * DEG * math.sin(2 * math.pi * (ph + 0.1)))
            nod = 3.2 * DEG * math.cos(4 * math.pi * (ph - 0.30))
            neck(pose, pitch=16 * DEG + nod, yaw=1.2 * DEG * math.sin(2 * math.pi * (ph - 0.1)),
                 head_pitch=-8 * DEG)
            pose.add_rot("pelvis", (0, 1, 0), 3.0 * DEG * math.sin(2 * math.pi * (ph + 0.05)))
            pose.add_rot("pelvis", (0, 0, 1), 2.0 * DEG * math.sin(2 * math.pi * (ph + 0.2)))
            pose.add_rot("spine_03", (0, 1, 0), -1.5 * DEG * math.sin(2 * math.pi * ph))
            tail_base, tail_stream = 5 * DEG, 26 * DEG
            ears(pose, cb.skel, l_back=4 * DEG * math.sin(2 * math.pi * ph),
                 r_back=-4 * DEG * math.sin(2 * math.pi * ph))
        tail_pose(pose, cb.skel, lift=tail_base, stream=tail_stream)
        frames.append(pose)
        root.append((rp, 0.0))
    cb.compensate(frames, True)
    secondary(cb, frames, times, True, root=root,
              tail_phase=(2.8, 2.5, 2) if trot else (4.0, 1.5, 2))
    stride = v * T
    meta = dict(seconds=T, loop=True, groundSpeed_mps=round(v, 3), strideLength_m=round(stride, 3),
                markers=_footfall_markers(G, T))
    return dict(name=name, T=T, loop=True, frames=frames, times=times, root=root, meta=meta,
                plans=plans)


def _footfall_markers(G, T):
    m = {}
    for leg, off in G["offsets"].items():
        nm = {"F_L": "LF", "F_R": "RF", "H_L": "LH", "H_R": "RH"}[leg]
        m[f"footfall_{nm}"] = round((off % 1.0) * T, 4)
        m[f"liftoff_{nm}"] = round(((off + G["duty"]) % 1.0) * T, 4)
    return m


# --------------------------------------------------------------------------- idle

def idle(cb):
    T = 5.0
    times = cb.times(T)
    frames = []
    for t in times:
        ph = t / T
        pose = Pose()
        pose.ik = standing_ik(cb)
        breath = 0.5 - 0.5 * math.cos(2 * math.pi * 2 * ph)          # two breaths per loop
        pose.scale["belly"] = (1.0 + 0.035 * breath, 1.0, 1.0 + 0.02 * breath)
        body(pose, dx=0.011 * math.sin(2 * math.pi * ph), dy=0.004 * math.sin(4 * math.pi * ph),
             dz=-0.003 * breath, roll=-0.6 * DEG * math.sin(2 * math.pi * ph))
        pose.add_rot("spine_03", (1, 0, 0), 0.4 * DEG * breath)
        head_low = 0.5 - 0.5 * math.cos(2 * math.pi * ph)
        neck(pose, pitch=3.5 * DEG * head_low, yaw=4 * DEG * math.sin(2 * math.pi * (ph + 0.1)),
             head_pitch=1.5 * DEG * breath)
        flick_l = bump(t, 1.0, 1.55, 1.15)
        flick_r = bump(t, 3.1, 3.7, 3.25)
        ears(pose, cb.skel, l_back=32 * DEG * flick_l, r_back=-6 * DEG + 10 * DEG * flick_r,
             r_out=22 * DEG * flick_r)
        sw = env(t, 2.0, 2.35, 2.45, 3.2)
        swish = [5.5 * DEG * sw * math.sin(2 * math.pi * (t - 2.0) / 1.2 - 0.6 * i) * (0.4 + 0.15 * i)
                 for i in range(6)]
        tail_pose(pose, cb.skel, lift=2 * DEG, lag_swish=swish)
        pose.add_rot("jaw", (1, 0, 0), 2.0 * DEG * bump(t, 4.0, 4.6))
        frames.append(pose)
    secondary(cb, frames, times, True, tail_amp=0.6, tail_phase=(1.5, 1.0, 1))
    meta = dict(seconds=T, loop=True, groundSpeed_mps=0.0, strideLength_m=0.0,
                markers={"ear_flick_L": 1.15, "ear_flick_R": 3.25, "tail_swish": 2.4,
                         "breath_in": [1.25, 3.75]})
    return dict(name="lf_horse_idle", T=T, loop=True, frames=frames, times=times,
                root=[(np.zeros(2), 0.0)] * len(times), meta=meta)


# --------------------------------------------------------------------------- start / stop

def _walk_state_at(cb, phase):
    """Root-space walk leg states at walk phase (for clip boundary matching)."""
    G = WALK
    T, v = G["T"], G["v"]
    toesN = cb.neutral_toes()
    out = {}
    for leg in LEGS:
        c = HA.periodic_plan(T, v, G["duty"], G["offsets"][leg], toesN[leg])
        pl = HA.LegPlan(c, lift=G["lift"][leg[0]])
        t = phase * T
        out[leg] = cb.root_space(pl.state(t), np.array([0.0, -v * t]), 0.0)
    return out


def start(cb):
    """Idle stance -> walk (ends at walk phase 0 timing-wise; crossfade-friendly)."""
    G = WALK
    T = 0.65
    times = cb.times(T)
    v_end = G["v"]
    p = 1.15
    dist = lambda t: v_end * T * (t / T) ** (p + 1) / (p + 1)   # noqa: E731  v = v_end (t/T)^p
    D = dist(T)
    toesN = cb.neutral_toes()
    sweep = G["v"] * G["duty"] * G["T"]
    rest = {leg: np.array([cb.toe0[leg][0], cb.toe0[leg][1]]) for leg in LEGS}
    # world plan: root moves -Y by dist(t); RF stays planted (late stance at the end),
    # LH steps first (short), LF second, RH lifts late and is mid-swing at the end.
    land_front = lambda leg, tl: toesN[leg] + np.array([0.0, -sweep / 2 - dist(tl)])  # noqa: E731
    plans = {
        "F_R": HA.LegPlan([(-1.0, 1.5, rest["F_R"], 0.0)], lift=G["lift"]["F"], knee=G["knee"]),
        "H_L": HA.LegPlan([(-1.0, 0.02, rest["H_L"], 0.0), (0.30, 1.5, land_front("H_L", 0.30) +
                                                           np.array([0, 0.15]), 0.0)],
                          lift=0.07),
        "F_L": HA.LegPlan([(-1.0, 0.12, rest["F_L"], 0.0), (0.56, 1.5, land_front("F_L", 0.56), 0.0)],
                          lift=G["lift"]["F"] * 0.9, knee=G["knee"] * 0.9),
        "H_R": HA.LegPlan([(-1.0, 0.42, rest["H_R"], 0.0), (0.89, 2.0, land_front("H_R", 0.89),
                                                           0.0)], lift=G["lift"]["H"]),
    }
    frames, root = [], []
    for t in times:
        u = t / T
        rp = np.array([0.0, -dist(t)])
        pose = Pose()
        for leg in LEGS:
            st = cb.root_space(plans[leg].state(t), rp, 0.0)
            pose.ik[leg] = leg_ik(cb, leg, st, cb.toe0[leg][1])
        lean = smooth(u / 0.5)
        body(pose, dy=-0.03 * lean * (1 - 0.6 * smooth((u - 0.6) / 0.4)), dz=-0.012 * bump(u, 0.0, 1.0, 0.4),
             pitch=1.2 * DEG * bump(u, 0, 1.0, 0.35))
        neck(pose, pitch=2 * DEG * smooth(u) + 4 * DEG * bump(u, 0.0, 0.8, 0.3))
        tail_pose(pose, cb.skel, lift=5 * DEG * smooth(u), stream=26 * DEG * smooth(u))
        frames.append(pose)
        root.append((rp, 0.0))
    cb.compensate(frames, False)
    secondary(cb, frames, times, False, root=root)
    meta = dict(seconds=T, loop=False, groundSpeed_mps=round(D / T, 3), strideLength_m=0.0,
                markers={"lift_LH": 0.02, "lift_LF": 0.12, "land_LH": 0.30, "lift_RH": 0.42,
                         "land_LF": 0.56},
                speedProfile=f"v(t)={v_end} m/s*(t/{T})^{p}; distance {D:.3f} m")
    return dict(name="lf_horse_start", T=T, loop=False, frames=frames, times=times, root=root,
                meta=meta, plans=plans)


def stop(cb):
    """Walk -> square stance with weight settling back (0.8 s)."""
    G = WALK
    T = 0.8
    times = cb.times(T)
    v0 = G["v"]
    p = 1.6
    dist = lambda t: v0 * T / (p + 1) * (1 - (1 - t / T) ** (p + 1))   # noqa: E731
    D = dist(T)
    rest = {leg: np.array([cb.toe0[leg][0], cb.toe0[leg][1]]) for leg in LEGS}
    final = {leg: rest[leg] + np.array([0.0, -D]) for leg in LEGS}     # world = root_end + rest
    ws = _walk_state_at(cb, 0.0)                                       # walk phase 0 boundary
    start_w = {leg: np.array([ws[leg]["toe"][0], ws[leg]["toe"][1]]) for leg in LEGS}
    plans = {
        # LH lands at phase 0 of the walk: plant it, then a small squaring step at the end
        "H_L": HA.LegPlan([(-1.0, 0.46, start_w["H_L"], 0.0), (0.72, 2.0, final["H_L"], 0.0)],
                          lift=0.06),
        "F_L": HA.LegPlan([(-1.0, 0.10, start_w["F_L"], 0.0), (0.42, 2.0, final["F_L"], 0.0)],
                          lift=G["lift"]["F"] * 0.8, knee=G["knee"] * 0.8),
        "H_R": HA.LegPlan([(-1.0, -0.05, start_w["H_R"], 0.0), (0.30, 2.0, final["H_R"], 0.0)],
                          lift=G["lift"]["H"]),
        "F_R": HA.LegPlan([(-1.0, 0.22, start_w["F_R"], 0.0), (0.60, 2.0, final["F_R"], 0.0)],
                          lift=G["lift"]["F"] * 0.8, knee=G["knee"] * 0.8),
    }
    frames, root = [], []
    for t in times:
        u = t / T
        rp = np.array([0.0, -dist(t)])
        pose = Pose()
        for leg in LEGS:
            st = cb.root_space(plans[leg].state(t), rp, 0.0)
            pose.ik[leg] = leg_ik(cb, leg, st, cb.toe0[leg][1])
        settle = bump(u, 0.2, 1.0, 0.6)
        body(pose, dy=0.025 * settle, dz=-0.01 * settle, pitch=-1.2 * DEG * settle)
        neck(pose, pitch=2 * DEG * (1 - smooth(u)) - 5 * DEG * bump(u, 0.25, 1.0, 0.55))
        tail_pose(pose, cb.skel, lift=5 * DEG * (1 - smooth(u)), stream=26 * DEG * (1 - smooth(u)))
        frames.append(pose)
        root.append((rp, 0.0))
    cb.compensate(frames, False)
    secondary(cb, frames, times, False, root=root)
    meta = dict(seconds=T, loop=False, groundSpeed_mps=round(D / T, 3), strideLength_m=0.0,
                markers={"land_RH": 0.30, "land_LF": 0.42, "land_RF": 0.60, "square_LH": 0.72},
                speedProfile=f"v(t)={v0} m/s*(1-t/{T})^{p}; distance {D:.3f} m")
    return dict(name="lf_horse_stop", T=T, loop=False, frames=frames, times=times, root=root,
                meta=meta, plans=plans)


# --------------------------------------------------------------------------- turns

def turn(cb, direction):
    """Authored 90° turn on the spot (pivot = root origin); game yaws the root by the curve."""
    T = 1.1
    times = cb.times(T)
    sgn = 1.0 if direction == "left" else -1.0
    total = 90 * DEG * sgn
    yaw_f = lambda t: total * smooth(t / T)    # noqa: E731
    rest = {leg: np.array([cb.toe0[leg][0], cb.toe0[leg][1]]) for leg in LEGS}

    def tgt(leg, t):
        return HA.rotz(yaw_f(t))[:2, :2] @ rest[leg]

    # three quick steps per leg in alternating diagonal pairs; each landing aims at the
    # middle of the coming stance so planted hooves stay close to their rest placement
    pairs = [("F_L", "H_R"), ("F_R", "H_L")] if sgn > 0 else [("F_R", "H_L"), ("F_L", "H_R")]
    A = [(0.00, 0.19), (0.33, 0.52), (0.66, 0.85)]
    Bs = [(0.165, 0.355), (0.495, 0.685), (0.825, 1.015)]
    plans = {}
    for pair, steps in ((pairs[0], A), (pairs[1], Bs)):
        for leg in pair:
            cs = []
            prev_land = -1.0
            pos = rest[leg]
            yw = 0.0
            for i, (tl, tn) in enumerate(steps):
                cs.append((prev_land, tl, pos, yw))
                nxt = steps[i + 1][0] if i + 1 < len(steps) else T
                aim = 0.5 * (tn + nxt) if i + 1 < len(steps) else T
                pos, yw, prev_land = tgt(leg, aim), yaw_f(aim), tn
            cs.append((prev_land, 9.0, pos, yw))
            plans[leg] = HA.LegPlan(cs, lift=0.08 if leg[0] == "F" else 0.065,
                                    knee=45 * DEG if leg[0] == "F" else 0.0, swing_pitch=0.6,
                                    fet_swing=0.5, bo=0.15)
    steps = A + Bs
    frames, root = [], []
    for t in times:
        u = t / T
        yaw = yaw_f(t)
        pose = Pose()
        for leg in LEGS:
            st = cb.root_space(plans[leg].state(t), np.zeros(2), yaw)
            pose.ik[leg] = leg_ik(cb, leg, st, cb.toe0[leg][1])
        lead = bump(u, 0.0, 1.0, 0.35)
        neck(pose, yaw=sgn * 26 * DEG * lead, pitch=3 * DEG * lead, head_roll=-sgn * 4 * DEG * lead)
        pose.add_rot("spine_03", (0, 0, 1), sgn * 4 * DEG * bump(u, 0.05, 1.0, 0.45))
        pose.add_rot("spine_01", (0, 0, 1), -sgn * 3 * DEG * bump(u, 0.1, 1.0, 0.5))
        body(pose, dx=sgn * 0.015 * bump(u, 0, 1, 0.4), dz=-0.008 * bump(u, 0, 1, 0.5),
             roll=-sgn * 1.5 * DEG * bump(u, 0, 1, 0.45))
        ears(pose, cb.skel, l_out=sgn * 8 * DEG * lead, r_out=-sgn * 8 * DEG * lead)
        frames.append(pose)
        root.append((np.zeros(2), yaw))
    cb.compensate(frames, False)
    secondary(cb, frames, times, False, root=root)
    meta = dict(seconds=T, loop=False, groundSpeed_mps=0.0, strideLength_m=0.0,
                rootYawDeg=round(math.degrees(total), 1),
                yawCurve="yaw(t) = rootYawDeg * smoothstep(t/1.1) about the root origin "
                         "(apply to the node while the clip plays; hooves are planted in that frame)",
                markers={f"land_{i + 1}": round(st[1], 3) for i, st in enumerate(sorted(steps))})
    return dict(name=f"lf_horse_turn_{direction}", T=T, loop=False, frames=frames, times=times,
                root=root, meta=meta, plans=plans)


# --------------------------------------------------------------------------- expressive clips

def alert(cb):
    T = 1.4
    times = cb.times(T)
    frames = []
    for t in times:
        u = t / T
        pose = Pose()
        pose.ik = standing_ik(cb)
        up = smoother(t / 0.28)
        settle = smooth((t - 0.9) / 0.5)
        tremble = 0.5 * DEG * math.sin(2 * math.pi * 7.0 * t) * env(t, 0.3, 0.45, 0.85, 1.1)
        body(pose, dy=0.035 * up - 0.008 * settle, dz=0.006 * up, pitch=-2.0 * DEG * up + tremble)
        neck(pose, pitch=-17 * DEG * up + 3 * DEG * settle, head_pitch=-5 * DEG * up,
             yaw=-4 * DEG * bump(t, 0.2, 1.4, 0.7))
        ears(pose, cb.skel, l_back=-16 * DEG * up, r_back=-16 * DEG * up,
             l_out=-6 * DEG * up, r_out=-6 * DEG * up)
        tail_pose(pose, cb.skel, lift=16 * DEG * up - 4 * DEG * settle)
        pose.scale["belly"] = (1.0 + 0.03 * bump(t, 0.0, 0.6, 0.25), 1.0, 1.0)
        frames.append(pose)
    secondary(cb, frames, times, False)
    meta = dict(seconds=T, loop=False, groundSpeed_mps=0.0, strideLength_m=0.0,
                markers={"head_up": 0.28, "hold": 0.9})
    return dict(name="lf_horse_alert", T=T, loop=False, frames=frames, times=times,
                root=[(np.zeros(2), 0.0)] * len(times), meta=meta)


LOOK_BACK_PEAK = 0.95


def look_back(cb):
    """Head/neck turn back over the right shoulder toward the squad; hooves planted."""
    T = 1.8
    times = cb.times(T)
    frames = []
    for t in times:
        pose = Pose()
        pose.ik = standing_ik(cb)
        e = env(t, 0.05, 0.62, 1.22, 1.78)
        # turn to the horse's right (-X): negative yaw about world Z
        neck(pose, yaw=-172 * DEG * e, pitch=12 * DEG * e, w=(0.28, 0.30, 0.27, 0.15),
             head_roll=24 * DEG * e, head_pitch=-8 * DEG * e)
        pose.add_rot("spine_03", (0, 0, 1), -10 * DEG * e)
        pose.add_rot("spine_01", (0, 0, 1), 4 * DEG * e)
        body(pose, dx=0.012 * e, dy=0.02 * e, roll=1.0 * DEG * e)
        flick = bump(t, 0.85, 1.15)
        ears(pose, cb.skel, l_back=-10 * DEG * e + 18 * DEG * flick, r_back=-12 * DEG * e)
        tail_pose(pose, cb.skel, lift=3 * DEG * e, swish=-3 * DEG * e)
        frames.append(pose)
    secondary(cb, frames, times, False)
    meta = dict(seconds=T, loop=False, groundSpeed_mps=0.0, strideLength_m=0.0,
                markers={"look_back_peak": LOOK_BACK_PEAK, "return_start": 1.22})
    return dict(name="lf_horse_look_back", T=T, loop=False, frames=frames, times=times,
                root=[(np.zeros(2), 0.0)] * len(times), meta=meta)


def call(cb):
    """Short neigh: draw back, head up with open mouth and vibrating whinny, toss, settle."""
    T = 2.0
    times = cb.times(T)
    frames = []
    for t in times:
        pose = Pose()
        pose.ik = standing_ik(cb)
        prep = bump(t, 0.0, 0.45, 0.25)
        raise_ = env(t, 0.30, 0.60, 1.15, 1.55)
        neigh = env(t, 0.50, 0.62, 1.10, 1.25)
        toss = bump(t, 1.20, 1.65, 1.40)
        vib = math.sin(2 * math.pi * 9.0 * t) * neigh
        body(pose, dy=0.02 * prep - 0.015 * raise_, dz=0.004 * raise_, pitch=-1.5 * DEG * raise_ +
             0.25 * DEG * vib)
        neck(pose, pitch=6 * DEG * prep - 20 * DEG * raise_ + 14 * DEG * toss + 1.0 * DEG * vib,
             head_pitch=-14 * DEG * raise_ + 8 * DEG * toss, yaw=3 * DEG * raise_)
        pose.add_rot("jaw", (1, 0, 0), 20 * DEG * neigh + 2.5 * DEG * vib)
        ears(pose, cb.skel, l_back=-14 * DEG * raise_ + 6 * DEG * prep, r_back=-14 * DEG * raise_)
        pose.scale["belly"] = (1.0 + 0.04 * prep - 0.03 * neigh, 1.0, 1.0 + 0.02 * prep)
        tail_pose(pose, cb.skel, lift=10 * DEG * raise_)
        frames.append(pose)
    secondary(cb, frames, times, False)
    meta = dict(seconds=T, loop=False, groundSpeed_mps=0.0, strideLength_m=0.0,
                markers={"neigh_start": 0.55, "neigh_end": 1.15, "head_toss": 1.40})
    return dict(name="lf_horse_call", T=T, loop=False, frames=frames, times=times,
                root=[(np.zeros(2), 0.0)] * len(times), meta=meta)


def all_clips(cb):
    return [idle(cb), gait_loop(cb, WALK, "lf_horse_walk"), gait_loop(cb, TROT, "lf_horse_trot"),
            start(cb), stop(cb), turn(cb, "left"), turn(cb, "right"), alert(cb), look_back(cb),
            call(cb)]
