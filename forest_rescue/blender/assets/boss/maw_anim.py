"""Ancient Maw clips (13 manifest clips) authored procedurally on the deterministic Poser.

Conventions: 30 fps sampling on the exact manifest duration (t_i = i*D/N, N = round(30*D)); clips in
place (root bone static); loops identical first/last frame; non-loops start and end in the idle base pose.
Foot plants are solved in world space and converted into root space, so feet do not slide as long as
the client moves the root as documented in the meta (walk: 2.0 m/s; turn: +-90 deg yaw with smoothstep;
lane_charge: translation profile CHARGE_PROFILE during the active window).
"""
import math

import numpy as np
from mathutils import Matrix, Quaternion, Vector

import maw_body as B
from maw_pose import Poser, rest_ankle_ball

FPS = 30
WALK_SPEED = 2.0
WALK_T = 1.6
WALK_DUTY = 0.62
CHARGE_DIST = 7.0
CHARGE_T0, CHARGE_T1 = 2.8, 3.9

MANIFEST = {
    "lf_boss_idle": (5.0, True, {}),
    "lf_boss_walk": (1.6, True, {}),
    "lf_boss_turn_left": (1.3, False, {}),
    "lf_boss_turn_right": (1.3, False, {}),
    "lf_boss_awaken": (4.2, False, {}),
    "lf_boss_phase_roar": (2.8, False, {}),
    "lf_boss_hit": (0.55, False, {}),
    "lf_boss_stagger": (1.8, False, {}),
    "lf_boss_death": (5.2, False, {"ground_contact": 3.7}),
    "lf_boss_jaw_arc": (4.25, False, {"telegraph_begin": 0.0, "active_begin": 2.4, "active_end": 2.85,
                                      "recovery_end": 4.25}),
    "lf_boss_tail_sweep": (5.45, False, {"telegraph_begin": 0.0, "active_begin": 3.0, "active_end": 3.65,
                                         "recovery_end": 5.45}),
    "lf_boss_lane_charge": (5.9, False, {"telegraph_begin": 0.0, "active_begin": 2.8, "active_end": 3.9,
                                         "recovery_end": 5.9}),
    "lf_boss_stomp_waves": (6.9, False, {"telegraph_begin": 0.0, "wave_1_begin": 3.2, "wave_1_end": 3.6,
                                         "wave_2_begin": 4.1, "wave_2_end": 4.5, "recovery_end": 6.9}),
}


# ----------------------------------------------------------------------------------- curves
def ss(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def sss(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * x * (x * (6 * x - 15) + 10)


def win(t, a, b, c, d):
    """0 before a, ramps to 1 by b, holds, ramps down from c to 0 at d (smootherstep)."""
    if t <= a or t >= d:
        return 0.0
    if t < b:
        return sss((t - a) / max(b - a, 1e-6))
    if t <= c:
        return 1.0
    return 1.0 - sss((t - c) / max(d - c, 1e-6))


def ramp(t, a, b):
    return sss((t - a) / max(b - a, 1e-6))


def damped(t, t0, amp, freq, decay):
    if t < t0:
        return 0.0
    x = t - t0
    return amp * math.exp(-decay * x) * math.sin(2 * math.pi * freq * x)


def times(D):
    N = int(round(D * FPS))
    return [i * D / N for i in range(N + 1)]


# ----------------------------------------------------------------------------------- pose layers
class Layer:
    """Accumulated high-level pose parameters, applied in a fixed order onto a Poser."""

    def __init__(self):
        self.pelvis = Vector((0, 0, 0))        # armature-space offset of the pelvis
        self.pelvis_rot = [0.0, 0.0, 0.0]      # pitch(X), roll(Y), yaw(Z) degrees
        self.spine = [[0.0, 0.0, 0.0] for _ in range(3)]
        self.neck = [[0.0, 0.0, 0.0] for _ in range(3)]
        self.head = [0.0, 0.0, 0.0]
        self.jaw = -2.0
        self.tongue = 0.0
        self.tail = [[0.0, 0.0, 0.0] for _ in range(10)]   # pitch, roll, yaw per tail bone
        self.arm = {"L": [0.0, 0.0, 0.0, 0.0], "R": [0.0, 0.0, 0.0, 0.0]}  # upper pitch, upper abduct, fore pitch, hand
        self.feet = {}                         # side -> (ankle, ball, toe_curl)
        self.stabilize_head = 0.0              # 0..1 counter-rotate neck to cancel trunk pitch/yaw
        self.head_target_world = None


def apply_layer(ps, L):
    ps.reset()
    # pelvis translation: local translation in the pelvis bone rest frame
    M = ps.rest3["pelvis"]
    ps.t["pelvis"] = M.inverted() @ L.pelvis
    p, r, y = L.pelvis_rot
    ps.rot("pelvis", (0, 0, 1), y)
    ps.rot("pelvis", (1, 0, 0), p)
    ps.rot("pelvis", (0, 1, 0), r)
    for i, (sp, sr, sy) in enumerate(L.spine):
        n = f"spine_0{i + 1}"
        ps.rot(n, (0, 0, 1), sy)
        ps.rot(n, (1, 0, 0), sp)
        ps.rot(n, (0, 1, 0), sr)
    stab_p = -(p + sum(s[0] for s in L.spine)) * L.stabilize_head
    stab_y = -(y + sum(s[2] for s in L.spine)) * L.stabilize_head
    stab_r = -(r + sum(s[1] for s in L.spine)) * L.stabilize_head
    for i, (np_, nr, ny) in enumerate(L.neck):
        n = f"neck_0{i + 1}"
        ps.rot(n, (0, 0, 1), ny + stab_y / 3)
        ps.rot(n, (1, 0, 0), np_ + stab_p / 3)
        ps.rot(n, (0, 1, 0), nr + stab_r / 3)
    hp, hr, hy = L.head
    ps.rot("head", (0, 0, 1), hy)
    ps.rot("head", (1, 0, 0), hp)
    ps.rot("head", (0, 1, 0), hr)
    ps.rot("jaw", (1, 0, 0), L.jaw)
    ps.rot("tongue_01", (1, 0, 0), L.tongue * 0.4)
    ps.rot("tongue_02", (1, 0, 0), L.tongue * 0.6)
    for i, (tp, tr, ty) in enumerate(L.tail):
        n = f"tail_{i + 1:02d}"
        ps.rot(n, (0, 0, 1), ty)
        ps.rot(n, (1, 0, 0), tp)
        ps.rot(n, (0, 1, 0), tr)
    for side, (up, ab, fp, hd) in L.arm.items():
        s = 1 if side == "L" else -1
        ps.rot(f"upperarm_{side}", (1, 0, 0), up)
        ps.rot(f"upperarm_{side}", (0, 1, 0), -ab * s)
        ps.rot(f"forearm_{side}", (1, 0, 0), fp)
        ps.rot(f"hand_{side}", (1, 0, 0), hd)
        for f in ("finger1a", "finger2a"):
            ps.rot(f"{f}_{side}", (1, 0, 0), hd * 0.5)
    for side in ("L", "R"):
        a0, b0 = rest_ankle_ball(side)
        f = L.feet.get(side, (a0, b0, 0.0))
        ank, ball, curl = f[0], f[1], f[2]
        heading = f[3] if len(f) > 3 else 0.0
        ps.leg_ik(side, ank, ball, toe_curl=curl, heading=heading)
    return ps


def idle_layer(t, D=5.0):
    """Breathing + slow look + tail sway + weight shift; periodic with period D."""
    L = Layer()
    w = 2 * math.pi / D
    br = math.sin(2 * w * t)                 # breath (2 per loop)
    L.pelvis = Vector((0.03 * math.sin(w * t), 0.0, -0.02 + 0.012 * br))
    L.pelvis_rot = [0.6 * br, 0.8 * math.sin(w * t), 1.2 * math.sin(w * t + 0.6)]
    L.spine = [[-0.4 * br, 0, 0], [-0.5 * br, 0, -0.6 * math.sin(w * t)], [-0.5 * br, 0, -0.6 * math.sin(w * t)]]
    look = math.sin(w * t + 1.2)
    L.neck = [[0.8 * br, 0, 2.5 * look], [0.6 * br, 0, 2.5 * look], [0, 0, 2.0 * look]]
    L.head = [-1.0 * br + 2.0 * math.sin(w * t * 1 + 2.0), 1.5 * math.sin(w * t), 3.0 * look]
    L.jaw = -2.0 + 1.2 * max(0.0, br)
    for i in range(10):
        ph = w * t - 0.35 * i
        L.tail[i] = [0.6 * math.sin(ph + 1.0) + (0.3 if i < 3 else 0.0), 0, 2.2 * math.sin(ph) * (0.6 + 0.08 * i)]
    L.arm["L"] = [2.0 * br, 0, -2.0 * br, 3.0 * math.sin(w * t + 0.4)]
    L.arm["R"] = [2.0 * br, 0, -2.0 * br, 3.0 * math.sin(w * t + 2.0)]
    L.stabilize_head = 0.3
    return L


def blend_layers(A, Bl, x):
    """Linear blend of two layers (x=0 -> A)."""
    out = Layer()
    lerp = lambda a, b: a + (b - a) * x  # noqa: E731
    out.pelvis = A.pelvis.lerp(Bl.pelvis, x)
    out.pelvis_rot = [lerp(a, b) for a, b in zip(A.pelvis_rot, Bl.pelvis_rot)]
    out.spine = [[lerp(a, b) for a, b in zip(sa, sb)] for sa, sb in zip(A.spine, Bl.spine)]
    out.neck = [[lerp(a, b) for a, b in zip(sa, sb)] for sa, sb in zip(A.neck, Bl.neck)]
    out.head = [lerp(a, b) for a, b in zip(A.head, Bl.head)]
    out.jaw = lerp(A.jaw, Bl.jaw)
    out.tongue = lerp(A.tongue, Bl.tongue)
    out.tail = [[lerp(a, b) for a, b in zip(sa, sb)] for sa, sb in zip(A.tail, Bl.tail)]
    out.arm = {s: [lerp(a, b) for a, b in zip(A.arm[s], Bl.arm[s])] for s in ("L", "R")}
    out.stabilize_head = lerp(A.stabilize_head, Bl.stabilize_head)
    feet = {}
    for side in ("L", "R"):
        a0, b0 = rest_ankle_ball(side)
        fa = A.feet.get(side, (a0, b0, 0.0))
        fb = Bl.feet.get(side, (a0, b0, 0.0))
        ha = fa[3] if len(fa) > 3 else 0.0
        hb = fb[3] if len(fb) > 3 else 0.0
        feet[side] = (fa[0].lerp(fb[0], x), fa[1].lerp(fb[1], x), lerp(fa[2], fb[2]), lerp(ha, hb))
    out.feet = feet
    return out


def add_offsets(L, **kw):
    """Add offsets: pelvis=(dx,dy,dz), pelvis_rot=(p,r,y), spine=(p,r,y) per bone, neck, head, tail, jaw..."""
    if "pelvis" in kw:
        L.pelvis = L.pelvis + Vector(kw["pelvis"])
    if "pelvis_rot" in kw:
        L.pelvis_rot = [a + b for a, b in zip(L.pelvis_rot, kw["pelvis_rot"])]
    for key in ("spine", "neck"):
        if key in kw:
            arr = getattr(L, key)
            for i in range(len(arr)):
                arr[i] = [a + b for a, b in zip(arr[i], kw[key])]
    if "head" in kw:
        L.head = [a + b for a, b in zip(L.head, kw["head"])]
    if "jaw" in kw:
        L.jaw += kw["jaw"]
    if "tongue" in kw:
        L.tongue += kw["tongue"]
    if "tail" in kw:   # (pitch, roll, yaw) per bone, scaled by profile along the chain
        p, r, y = kw["tail"]
        prof = kw.get("tail_prof", [1.0] * 10)
        for i in range(10):
            L.tail[i] = [L.tail[i][0] + p * prof[i], L.tail[i][1] + r * prof[i], L.tail[i][2] + y * prof[i]]
    if "arms" in kw:
        for s in ("L", "R"):
            L.arm[s] = [a + b for a, b in zip(L.arm[s], kw["arms"])]
    return L


# ----------------------------------------------------------------------------------- foot planning
def rot_z(v, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return Vector((c * v.x - s * v.y, s * v.x + c * v.y, v.z))


def swing_point(p0, p1, s, lift):
    e = sss(s)
    p = p0.lerp(p1, e)
    p.z += lift * math.sin(math.pi * min(max(s, 0), 1)) ** 0.85
    return p


def plan_feet(t, steps, root_xy=lambda t: (Vector((0, 0, 0)), 0.0), lift=0.32, land_t=None):
    """steps: side -> list of (t_lift, t_land, target_world_ankle_offset (Vector), target_yaw_deg).

    Feet start at their rest positions (planted at world positions of t=0 root).
    Returns side -> (ankle, ball, curl) in ROOT space.
    """
    out = {}
    for side in ("L", "R"):
        a0, b0 = rest_ankle_ball(side)
        o0, y0 = root_xy(0.0)
        planted_a = o0 + rot_z(a0, y0)
        planted_b = o0 + rot_z(b0, y0)
        planted_h = y0
        state = ("plant", planted_a, planted_b, 0.0, planted_h)
        for (tl, td, off, yaw) in steps.get(side, []):
            if t < tl:
                break
            ot, yt = root_xy(td if land_t is None else land_t)
            land_a = ot + rot_z(a0 + off, yt + yaw)
            land_b = ot + rot_z(b0 + off, yt + yaw)
            land_h = yt + yaw
            if t < td:
                s = (t - tl) / (td - tl)
                pa = swing_point(planted_a, land_a, s, lift)
                pb = swing_point(planted_b, land_b, s, lift * 0.75)
                # toes curl in swing
                curl = 35.0 * math.sin(math.pi * s)
                state = ("swing", pa, pb, curl, planted_h + (land_h - planted_h) * sss(s))
                break
            planted_a, planted_b, planted_h = land_a, land_b, land_h
            state = ("plant", planted_a, planted_b, 0.0, planted_h)
        _, wa, wb, curl, wh = state
        o, yw = root_xy(t)
        ra = rot_z(wa - o, -yw)
        rb = rot_z(wb - o, -yw)
        out[side] = (ra, rb, curl, wh - yw)
    return out


# ----------------------------------------------------------------------------------- clips
def clip_idle(t):
    L = idle_layer(t)
    return L


def walk_feet(t):
    """Cyclic walk: each foot stance (duty) then swing; world-planted with root moving at WALK_SPEED."""
    out = {}
    D = WALK_SPEED * WALK_DUTY * WALK_T          # stance excursion
    for side, ph0 in (("L", 0.0), ("R", 0.5)):
        a0, b0 = rest_ankle_ball(side)
        ph = (t / WALK_T + ph0) % 1.0
        if ph < WALK_DUTY:
            s = ph / WALK_DUTY
            dy = -D / 2 + D * s                  # forward(-Y) at contact -> backward
            a = a0 + Vector((0, dy, 0))
            b = b0 + Vector((0, dy, 0))
            # toe-off: last 18% of stance the heel lifts around the ball
            heel = max(0.0, (s - 0.82) / 0.18)
            a.z += 0.28 * heel * heel
            a.y -= 0.10 * heel * heel
            curl = -25.0 * heel   # toes stay flat while metatarsus rolls (negative -> toes up relative)
            out[side] = (a, b, 0.0)
        else:
            s = (ph - WALK_DUTY) / (1 - WALK_DUTY)
            pa = Vector(a0 + Vector((0, D / 2, 0.28)))
            pa.y -= 0.10
            pb = Vector(b0 + Vector((0, D / 2, 0)))
            qa = Vector(a0 + Vector((0, -D / 2, 0)))
            qb = Vector(b0 + Vector((0, -D / 2, 0)))
            A = swing_point(pa, qa, s, 0.30)
            Bb = swing_point(pb, qb, s, 0.38)
            out[side] = (A, Bb, 30.0 * math.sin(math.pi * s))
    return out


def clip_walk(t):
    T = WALK_T
    ph = t / T
    w = 2 * math.pi * ph
    L = Layer()
    # vertical: lowest shortly after each contact, highest at passing (2 per cycle)
    bob = -0.07 * math.cos(2 * w - 0.6) - 0.03
    sway = 0.07 * math.sin(w - 0.3)               # over the stance foot (L stance first half)
    L.pelvis = Vector((sway, 0.0, bob))
    L.pelvis_rot = [1.2 * math.cos(2 * w - 0.6), -2.5 * math.sin(w - 0.2), -5.0 * math.sin(w)]
    L.spine = [[-0.4 * math.cos(2 * w), 1.0 * math.sin(w), 2.0 * math.sin(w)],
               [-0.3 * math.cos(2 * w), 0.8 * math.sin(w), 1.5 * math.sin(w)],
               [0, 0.5 * math.sin(w), 1.0 * math.sin(w)]]
    L.neck = [[2.0, 0, 0], [0.5, 0, 0], [0, 0, 0]]
    L.head = [-1.0, 0, 0]
    L.stabilize_head = 0.85
    for i in range(10):
        d = 0.32 * i
        L.tail[i] = [0.8 * math.cos(2 * w - d) * (0.3 + 0.06 * i) + (0.4 if i < 3 else 0),
                     0, 3.2 * math.sin(w - 0.6 - d) * (0.55 + 0.07 * i)]
    L.arm["L"] = [6.0 * math.sin(w + 0.5), 0, -4.0 * math.sin(w + 0.9), 4.0 * math.sin(w + 1.2)]
    L.arm["R"] = [-6.0 * math.sin(w + 0.5), 0, 4.0 * math.sin(w + 0.9), -4.0 * math.sin(w + 1.2)]
    L.jaw = -2.0 + 0.8 * max(0, math.sin(2 * w))
    L.feet = walk_feet(t)
    return L


def clip_turn(t, direction=1, D=1.3, total=90.0):
    yaw = lambda tt: direction * total * ss(tt / D)  # noqa: E731
    root = lambda tt: (Vector((0, 0, 0)), yaw(tt))  # noqa: E731
    inner, outer = ("L", "R") if direction > 0 else ("R", "L")
    steps = {inner: [(0.12, 0.58, Vector((0, -0.05, 0)), 0.0)],
             outer: [(0.55, 1.02, Vector((0, 0.0, 0)), 0.0)]}
    L = idle_layer(0.0)
    lead = win(t, 0.0, 0.35, 0.65, 1.25)
    # upper body leads the turn, pelvis follows the root (body yaw relative to root returns to 0)
    add_offsets(L, pelvis=(direction * -0.05 * lead, 0.04 * lead, -0.06 * lead),
                pelvis_rot=(0, -direction * 2.5 * lead, direction * 8.0 * lead),
                spine=(0.5 * lead, 0, direction * 4.0 * lead), neck=(0, 0, direction * 7.0 * lead),
                head=(2.0 * lead, -direction * 3.0 * lead, direction * 6.0 * lead))
    # tail counterbalance: swings out to the outside then follows
    sw = win(t, 0.0, 0.45, 0.75, 1.3)
    prof = [0.4 + 0.08 * i for i in range(10)]
    add_offsets(L, tail=(1.0 * sw, 0, -direction * 7.0 * sw), tail_prof=prof)
    L.feet = plan_feet(t, steps, root_xy=root, lift=0.26, land_t=D)
    return L


def crouch_layer(depth=1.0):
    """Lying/resting pose: belly on the ground, legs folded, head resting low (used by awaken)."""
    L = Layer()
    L.pelvis = Vector((0, 0.25 * depth, -1.18 * depth))
    L.pelvis_rot = [-6.0 * depth, 0, 0]
    L.spine = [[4.0 * depth, 0, 0], [4.0 * depth, 0, 0], [4.0 * depth, 0, 0]]
    L.neck = [[12.0 * depth, 0, -6.0 * depth], [8.0 * depth, 0, -6.0 * depth], [4.0 * depth, 0, -4 * depth]]
    L.head = [-6.0 * depth, 4.0 * depth, -4.0 * depth]
    L.jaw = -2.0
    for i in range(10):
        L.tail[i] = [(-5.0 if i < 2 else 3.0) * depth, 0, 6.0 * depth * (0.3 + 0.1 * i)]
    L.arm["L"] = [-30.0 * depth, 10 * depth, 30 * depth, 10 * depth]
    L.arm["R"] = [-30.0 * depth, 10 * depth, 30 * depth, 10 * depth]
    feet = {}
    for side in ("L", "R"):
        a0, b0 = rest_ankle_ball(side)
        s = 1 if side == "L" else -1
        a = a0 + Vector((0.10 * s * depth, 0.55 * depth, -0.62 * depth))
        b = b0 + Vector((0.08 * s * depth, -0.05 * depth, -0.06 * depth))
        feet[side] = (a, b, 0.0)
    L.feet = feet
    return L


def clip_awaken(t, D=4.2):
    base = idle_layer(0.0)
    down = crouch_layer(1.0)
    rise = ramp(t, 0.9, 2.6)
    L = blend_layers(down, base, rise)
    # stir: head twitch + breath before rising
    add_offsets(L, head=(damped(t, 0.3, 4.0, 1.5, 2.0), 0, damped(t, 0.5, 3.0, 1.2, 1.5)),
                neck=(-3.0 * win(t, 0.2, 0.6, 0.9, 1.4), 0, 0))
    # snort/roar after standing: head up, jaw opens
    r = win(t, 2.6, 3.0, 3.35, 3.9)
    add_offsets(L, neck=(-5.0 * r, 0, 0), head=(-6.0 * r, 0, 0), jaw=26.0 * r, tongue=-8 * r,
                spine=(-1.5 * r, 0, 0), arms=(-8 * r, 4 * r, -6 * r, 0))
    # shake at the end of the rise
    add_offsets(L, head=(0, damped(t, 2.3, 4.0, 3.0, 3.0), 0), tail=(0, 0, damped(t, 2.2, 3.0, 1.0, 1.5)),
                tail_prof=[0.3 + 0.1 * i for i in range(10)])
    return L


def clip_phase_roar(t, D=2.8):
    L = idle_layer(0.0)
    ant = win(t, 0.0, 0.45, 0.5, 0.75)
    add_offsets(L, pelvis=(0, 0.06 * ant, -0.08 * ant), neck=(4.0 * ant, 0, 0), head=(5.0 * ant, 0, 0),
                spine=(1.5 * ant, 0, 0))
    r = win(t, 0.5, 0.95, 1.95, 2.55)
    add_offsets(L, pelvis=(0, 0.12 * r, -0.04 * r), pelvis_rot=(-5.0 * r, 0, 0), spine=(-4.0 * r, 0, 0),
                neck=(-11.0 * r, 0, 0), head=(-14.0 * r, 0, 0), jaw=40.0 * r, tongue=-10.0 * r,
                arms=(-22.0 * r, 16.0 * r, -18.0 * r, -15 * r))
    add_offsets(L, tail=(-3.0 * r, 0, 0), tail_prof=[0.5 + 0.06 * i for i in range(10)])
    vib = math.sin(2 * math.pi * 11.0 * t) * r
    add_offsets(L, head=(1.2 * vib, 1.0 * vib, 1.5 * vib), jaw=1.5 * vib)
    return L


def clip_hit(t, D=0.55):
    L = idle_layer(0.0)
    k = math.exp(-6.0 * t) * math.sin(math.pi * min(t / 0.12, 1.0) * 0.5) if t < D else 0.0
    k = win(t, 0.0, 0.08, 0.12, 0.5)
    add_offsets(L, pelvis=(0.03 * k, 0.08 * k, -0.03 * k), pelvis_rot=(0, 1.5 * k, -3.0 * k),
                spine=(-1.5 * k, 0, -2.0 * k), neck=(-4.0 * k, 0, -6.0 * k), head=(-6.0 * k, 5.0 * k, -8.0 * k),
                jaw=10.0 * k, arms=(-6 * k, 4 * k, -6 * k, 0))
    add_offsets(L, tail=(0, 0, 4.0 * win(t, 0.05, 0.2, 0.25, 0.55)), tail_prof=[0.3 + 0.08 * i for i in range(10)])
    return L


def clip_stagger(t, D=1.8):
    L = idle_layer(0.0)
    k = win(t, 0.0, 0.25, 0.7, 1.6)
    add_offsets(L, pelvis=(0.10 * k, 0.28 * k, -0.10 * k), pelvis_rot=(-3.0 * k, 3.0 * k, -6.0 * k),
                spine=(-2.0 * k, 1.0 * k, -3.0 * k), neck=(-5.0 * k, 0, -8.0 * k),
                head=(-8.0 * k + damped(t, 0.3, 5, 1.6, 2.5), 7.0 * k, -10.0 * k), jaw=14.0 * k,
                arms=(-14 * k, 10 * k, -10 * k, -8 * k))
    add_offsets(L, tail=(2.0 * k, 0, 6.0 * k), tail_prof=[0.4 + 0.08 * i for i in range(10)])
    steps = {"L": [(0.22, 0.62, Vector((0.05, 0.42, 0)), 0.0), (1.0, 1.42, Vector((0, 0, 0)), 0.0)]}
    L.feet = plan_feet(t, steps, lift=0.22)
    return L


def death_layer():
    """Final death keypose (sheet 05 #12): slumped on its right side, head on the ground, tail curled."""
    L = Layer()
    L.pelvis = Vector((-0.30, 0.10, -1.42))
    L.pelvis_rot = [-6.0, -48.0, 6.0]
    L.spine = [[3.0, -4.0, -4.0], [3.0, -4.0, -5.0], [4.0, -2.0, -6.0]]
    L.neck = [[16.0, 0, -12.0], [12.0, 6.0, -10.0], [6.0, 6.0, -8.0]]
    L.head = [-4.0, 22.0, -6.0]
    L.jaw = 5.0
    L.tongue = -4.0
    for i in range(10):
        L.tail[i] = [2.0 if i > 1 else -6.0, 0.0, -7.5 * (0.5 + 0.08 * i)]
    L.arm["L"] = [-35.0, 20.0, 40.0, 25.0]
    L.arm["R"] = [-20.0, -5.0, 35.0, 20.0]
    feet = {}
    a0, b0 = rest_ankle_ball("L")
    feet["L"] = (a0 + Vector((0.05, 0.62, -0.30)), b0 + Vector((0.25, -0.05, 0.10)), 20.0)
    a0, b0 = rest_ankle_ball("R")
    feet["R"] = (a0 + Vector((0.30, 0.52, -0.55)), b0 + Vector((0.35, 0.10, 0.02)), 10.0)
    L.feet = feet
    return L


def clip_death(t, D=5.2):
    base = idle_layer(0.0)
    dead = death_layer()
    # 0-1.2 wobble/stagger, 1.2-3.7 collapse (accelerating), 3.7 ground contact, bounce/settle, last breath
    wob = win(t, 0.0, 0.5, 1.0, 1.6)
    fall = ramp(t, 1.2, 3.7) ** 1.6 if t < 3.7 else 1.0
    L = blend_layers(base, dead, fall)
    add_offsets(L, pelvis=(0.06 * wob * math.sin(2 * math.pi * 1.4 * t), 0.08 * wob, -0.06 * wob),
                head=(-10 * wob, 6 * wob * math.sin(2 * math.pi * 1.1 * t), 0), jaw=12 * wob,
                neck=(-6 * wob, 0, 0))
    if t >= 3.7:
        b = damped(t, 3.7, 1.0, 2.2, 5.0)
        add_offsets(L, pelvis=(0, 0, 0.035 * abs(b)), head=(-3.0 * abs(b), 0, 0), tail=(-1.5 * abs(b), 0, 0))
        breath = win(t, 4.3, 4.6, 4.7, 5.1)
        add_offsets(L, spine=(-1.0 * breath, 0, 0), jaw=2.0 * breath)
    return L


def clip_jaw_arc(t, D=4.25):
    L = idle_layer(0.0)
    tel = ramp(t, 0.0, 1.6)
    hold = win(t, 1.6, 1.7, 2.3, 2.4)
    w = tel * (1 - ramp(t, 2.38, 2.52))
    # telegraph: weight back, head pulled back/up and to the right, jaw opening wide
    add_offsets(L, pelvis=(0.0, 0.32 * w, -0.06 * w), pelvis_rot=(-4.0 * w, 0, 6.0 * w),
                spine=(-2.5 * w, 0, 3.0 * w), neck=(-9.0 * w, 0, 8.0 * w), head=(-12.0 * w, 4.0 * w, 10.0 * w),
                jaw=34.0 * tel * (1 - ramp(t, 2.62, 2.78)), tongue=-6 * w, arms=(-8 * w, 6 * w, -6 * w, 0))
    add_offsets(L, tail=(-2.0 * w, 0, -3.0 * w), tail_prof=[0.4 + 0.07 * i for i in range(10)])
    add_offsets(L, head=(0.8 * hold * math.sin(2 * math.pi * 6 * t), 0, 0))
    # active 2.4-2.85: lunge forward-low and sweep the head across the front sector (right -> left)
    a = win(t, 2.38, 2.5, 2.85, 3.6)
    sweep = ramp(t, 2.42, 2.85)
    yaw = (1 - 2 * sweep) * 16.0 * a
    add_offsets(L, pelvis=(0.0, -0.38 * a, -0.10 * a), pelvis_rot=(5.0 * a, 0, yaw * 0.4),
                spine=(2.5 * a, 0, yaw * 0.25), neck=(6.0 * a, 0, yaw * 0.6), head=(7.0 * a, 0, yaw * 0.8))
    add_offsets(L, tail=(-3.0 * a, 0, -yaw * 0.35), tail_prof=[0.4 + 0.07 * i for i in range(10)])
    # recovery overshoot settle
    add_offsets(L, head=(damped(t, 2.85, 3.0, 1.4, 3.0), 0, 0), tail=(0, 0, damped(t, 2.9, 2.0, 0.9, 2.0)),
                tail_prof=[0.3 + 0.1 * i for i in range(10)])
    steps = {"R": [(2.4, 2.72, Vector((0, -0.38, 0)), 0.0), (3.35, 3.85, Vector((0, 0, 0)), 0.0)]}
    L.feet = plan_feet(t, steps, lift=0.25)
    return L


def clip_tail_sweep(t, D=5.45):
    L = idle_layer(0.0)
    prof = [0.35 + 0.075 * i for i in range(10)]
    coil = ramp(t, 0.2, 2.4) * (1 - ramp(t, 2.95, 3.1))
    # telegraph: wide stance (right foot steps out), hips coil, tail cocked high to the LEFT, head looks back right
    add_offsets(L, pelvis=(0.06 * coil, 0.05 * coil, -0.12 * coil), pelvis_rot=(0, 0, 14.0 * coil),
                spine=(0, 0, -5.0 * coil), neck=(0, 0, -8.0 * coil), head=(0, -4 * coil, -12.0 * coil))
    add_offsets(L, tail=(-6.0 * coil, 0, 9.0 * coil), tail_prof=prof)
    add_offsets(L, tail=(0, 0, 0.8 * coil * math.sin(2 * math.pi * 1.2 * t)), tail_prof=prof)
    # active 3.0-3.65: whip across rear+side to the right
    s = ramp(t, 2.98, 3.62)
    a = win(t, 2.95, 3.05, 3.65, 4.6)
    yaw_p = (14.0 * (1 - s) - 26.0 * s) * a
    add_offsets(L, pelvis_rot=(0, 2.0 * a, yaw_p), spine=(0, 0, -yaw_p * 0.3), neck=(0, 0, -yaw_p * 0.4),
                pelvis=(-0.05 * a, 0, -0.10 * a))
    delay = [ramp(t, 2.98 + 0.03 * i, 3.55 + 0.03 * i) for i in range(10)]
    for i in range(10):
        L.tail[i][2] += (9.0 * (1 - delay[i]) - 13.0 * delay[i]) * prof[i] * a
        L.tail[i][0] += 3.0 * prof[i] * a
    # follow-through overshoot and settle
    for i in range(10):
        L.tail[i][2] += damped(t, 3.65, -4.0 * prof[i], 0.8, 1.8)
    steps = {"R": [(0.25, 0.75, Vector((-0.22, 0.05, 0)), 0.0), (4.3, 4.85, Vector((0, 0, 0)), 0.0)]}
    L.feet = plan_feet(t, steps, lift=0.24)
    return L


def charge_d(t, a=0.25, b=0.85):
    """Client lane translation (m) during the active window: trapezoidal speed (accelerate over the first
    25 %, constant, decelerate over the last 15 %); distance CHARGE_DIST, peak speed CHARGE_DIST/(0.8*1.1 s)."""
    if t <= CHARGE_T0:
        return 0.0
    if t >= CHARGE_T1:
        return CHARGE_DIST
    s = (t - CHARGE_T0) / (CHARGE_T1 - CHARGE_T0)
    v = 1.0 / (1 - a / 2 - (1 - b) / 2)
    if s < a:
        d = v * s * s / (2 * a)
    elif s < b:
        d = v * (a / 2 + (s - a))
    else:
        d = v * (a / 2 + (b - a) + (s - b) - (s - b) ** 2 / (2 * (1 - b)))
    return CHARGE_DIST * d


def clip_lane_charge(t, D=5.9):
    L = idle_layer(0.0)
    # telegraph: head lowered along the lane, crouch, right foot paws the ground twice, tail stiff
    tel = ramp(t, 0.1, 1.2) * (1 - ramp(t, 4.4, 5.6))
    add_offsets(L, pelvis=(0, 0.10 * tel, -0.16 * tel), pelvis_rot=(4.0 * tel, 0, 0), spine=(2.0 * tel, 0, 0),
                neck=(5.0 * tel, 0, 0), head=(4.0 * tel, 0, 0), tail=(-2.0 * tel, 0, 0),
                tail_prof=[0.5 + 0.05 * i for i in range(10)], arms=(-10 * tel, 0, 8 * tel, 0))
    snort = win(t, 1.9, 2.05, 2.2, 2.4)
    add_offsets(L, jaw=10 * snort, head=(-3 * snort, 0, 0))
    # running: lean forward, low head, strong bob during the active window
    run = win(t, 2.75, 2.95, 3.75, 4.3)
    ph = 2 * math.pi * (t - 2.8) / 0.74
    add_offsets(L, pelvis=(0.04 * run * math.sin(ph), 0, -0.06 * run - 0.06 * run * math.cos(2 * ph)),
                pelvis_rot=(6.0 * run, 0, 4.0 * run * math.sin(ph)), spine=(2.0 * run, 0, -1.5 * run * math.sin(ph)),
                neck=(4.0 * run, 0, 0), head=(2.0 * run, 0, 0), jaw=8 * run)
    for i in range(10):
        L.tail[i][2] += -3.0 * run * math.sin(ph - 0.4 * i) * (0.4 + 0.07 * i)
        L.tail[i][0] += -1.2 * run
    # braking after the active window: pitch forward then rock back
    brk = win(t, 3.85, 4.05, 4.2, 5.2)
    add_offsets(L, pelvis=(0, -0.10 * brk, -0.08 * brk), pelvis_rot=(5.0 * brk, 0, 0),
                head=(damped(t, 3.95, -5.0, 1.0, 2.5), 0, 0), tail=(damped(t, 3.95, 4.0, 0.9, 2.0), 0, 0),
                tail_prof=[0.4 + 0.07 * i for i in range(10)])
    root = lambda tt: (Vector((0, -charge_d(tt), 0)), 0.0)  # noqa: E731
    # pawing (telegraph): right foot scrapes back twice (lift, drag back, return)
    steps = {"R": [(0.6, 0.95, Vector((0, -0.25, 0)), 0.0), (1.15, 1.5, Vector((0, 0.25, 0)), 0.0),
                   (1.65, 2.0, Vector((0, -0.25, 0)), 0.0), (2.15, 2.5, Vector((0, 0.0, 0)), 0.0),
                   # charge strides (land positions relative to the root at landing)
                   (2.80, 3.06, Vector((0, -0.95, 0)), 0.0), (3.24, 3.52, Vector((0, -0.95, 0)), 0.0),
                   (3.66, 3.92, Vector((0, -0.55, 0)), 0.0), (4.35, 4.8, Vector((0, 0, 0)), 0.0)],
             "L": [(2.92, 3.20, Vector((0, -0.95, 0)), 0.0), (3.38, 3.66, Vector((0, -0.95, 0)), 0.0),
                   (3.95, 4.3, Vector((0, 0.0, 0)), 0.0)]}
    L.feet = plan_feet(t, steps, root_xy=root, lift=0.34)
    return L


def clip_stomp(t, D=6.9):
    L = idle_layer(0.0)
    # telegraph 0-3.2: rear up, right foot raised high and held, arms up, roar
    up = ramp(t, 0.3, 1.6)
    st1 = ramp(t, 3.0, 3.2)          # slam 1
    raise_r = up * (1 - st1)
    rear = up * (1 - ramp(t, 3.05, 3.3))
    add_offsets(L, pelvis=(0.12 * rear, 0.22 * rear, -0.05 * rear), pelvis_rot=(-7.0 * rear, 3.0 * rear, 0),
                spine=(-3.0 * rear, 0, 0), neck=(-6.0 * rear, 0, 0), head=(-8.0 * rear, 0, 0),
                jaw=26.0 * win(t, 1.0, 1.5, 2.6, 3.0), arms=(-20 * rear, 14 * rear, -16 * rear, -10 * rear))
    add_offsets(L, tail=(4.0 * rear, 0, 0), tail_prof=[0.3 + 0.08 * i for i in range(10)])
    # impacts: body drops and head jolts at 3.2 and 4.1
    for ti in (3.2, 4.1):
        j = win(t, ti - 0.04, ti + 0.02, ti + 0.06, ti + 0.45)
        add_offsets(L, pelvis=(0, -0.05 * j, -0.12 * j), neck=(5.0 * j, 0, 0), head=(4.0 * j, 0, 0),
                    jaw=8 * j, tail=(-3.0 * j, 0, 0), tail_prof=[0.3 + 0.08 * i for i in range(10)])
    # second stomp: weight onto right, left foot lifts 3.45-4.1
    w2 = win(t, 3.3, 3.5, 4.05, 4.4)
    add_offsets(L, pelvis=(-0.08 * w2, 0.05 * w2, 0.02 * w2), pelvis_rot=(-3.0 * w2, -2.0 * w2, 0))
    feet = {}
    for side in ("L", "R"):
        a0, b0 = rest_ankle_ball(side)
        feet[side] = (a0.copy(), b0.copy(), 0.0)
    # right foot raised high (readable from above): ankle up 0.95 m, forward 0.45 m
    aR, bR = rest_ankle_ball("R")
    lift = raise_r
    feet["R"] = (aR + Vector((0, -0.45 * lift, 0.95 * lift)), bR + Vector((0, -0.70 * lift, 0.82 * lift)),
                 45.0 * lift)
    aL, bL = rest_ankle_ball("L")
    l2 = win(t, 3.45, 3.75, 3.85, 4.1)
    feet["L"] = (aL + Vector((0, -0.25 * l2, 0.70 * l2)), bL + Vector((0, -0.45 * l2, 0.6 * l2)), 40.0 * l2)
    L.feet = feet
    # recovery 4.5-6.9 eases everything back to idle
    rec = ramp(t, 4.5, 6.4)
    if rec > 0:
        L = blend_layers(L, idle_layer(0.0), rec)
    return L


CLIPS = {
    "lf_boss_idle": clip_idle,
    "lf_boss_walk": clip_walk,
    "lf_boss_turn_left": lambda t: clip_turn(t, 1),
    "lf_boss_turn_right": lambda t: clip_turn(t, -1),
    "lf_boss_awaken": clip_awaken,
    "lf_boss_phase_roar": clip_phase_roar,
    "lf_boss_hit": clip_hit,
    "lf_boss_stagger": clip_stagger,
    "lf_boss_death": clip_death,
    "lf_boss_jaw_arc": clip_jaw_arc,
    "lf_boss_tail_sweep": clip_tail_sweep,
    "lf_boss_lane_charge": clip_lane_charge,
    "lf_boss_stomp_waves": clip_stomp,
}


def author_frames(arm, clip_id):
    D, loop, _m = MANIFEST[clip_id]
    ps = Poser(arm)
    ts = times(D)
    frames = []
    fn = CLIPS[clip_id]
    for i, t in enumerate(ts):
        tt = 0.0 if (loop and i == len(ts) - 1) else t
        L = fn(tt)
        apply_layer(ps, L)
        frames.append(ps.frame())
    return ts, frames


def write_clip(arm, clip_id, ts, frames, loop):
    """Dense keys at fractional frames t*30 (exact manifest duration); root/pelvis location keyed."""
    import bpy
    act = bpy.data.actions.get(clip_id)
    if act is not None:
        bpy.data.actions.remove(act)
    act = bpy.data.actions.new(clip_id)
    act.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act
    prev = {}
    for t, fr in zip(ts, frames):
        f = t * FPS
        for bone, (loc, q) in fr.items():
            pb = arm.pose.bones[bone]
            if bone in prev and prev[bone].dot(q) < 0:
                q = -q
            prev[bone] = q
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=f, group=bone)
            if bone in ("root", "pelvis"):
                pb.location = loc
                pb.keyframe_insert("location", frame=f, group=bone)
    act.use_frame_range = True
    act.frame_start = 0
    act.frame_end = ts[-1] * FPS
    act.use_cyclic = bool(loop)
    act["loop"] = bool(loop)
    act["duration_s"] = ts[-1]
    return act
