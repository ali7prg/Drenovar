"""Quadruped animation authoring: keyed poses, gait generator, leg IK, secondary motion.

All clips are in place: MotionRoot never travels horizontally. Locomotion feet
are planted against a world that slides backwards at `speed` m/s (stance feet
move back at exactly that speed), so a controller moving the actor at
speed * scale with playback tempo 1 shows no foot sliding. Charge/pounce/dodge
publish their controller displacement curve in the clip manifest (`motion`).
"""
import numpy as np

from qmath import q_identity, q_euler, q_mul, q_rotate, q_conj, q_between, q_normalize, q_axis, ease
from rig import two_bone_ik

FPS = 30.0
LEGS = (("Front", "L", -1), ("Front", "R", 1), ("Hind", "L", -1), ("Hind", "R", 1))


# ------------------------------------------------------------------ key tracks
class Track:
    """Hermite track over frames; tangents from neighbouring keys (time-aware), `hold` keys get zero slope."""

    def __init__(self, keys, loop_len=None):
        keys = sorted(keys, key=lambda k: k[0])
        self.f = np.array([k[0] for k in keys], float)
        self.v = [np.atleast_1d(np.asarray(k[1], float)) for k in keys]
        self.hold = [len(k) > 2 and k[2] == "hold" for k in keys]
        self.loop = loop_len

    def __call__(self, fr):
        f, v = self.f, self.v
        n = len(f)
        if n == 1:
            return v[0]
        if self.loop is None:
            if fr <= f[0]:
                return v[0]
            if fr >= f[-1]:
                return v[-1]
        else:
            fr = fr % self.loop
        i = np.searchsorted(f, fr, side="right") - 1
        if self.loop is not None and (i < 0 or i >= n - 1):
            # wrap segment between last and first key
            f0, f1 = f[-1], f[0] + self.loop
            if fr < f[0]:
                fr += self.loop
            v0, v1 = v[-1], v[0]
            m0 = self._slope(n - 1)
            m1 = self._slope(0)
        else:
            i = int(np.clip(i, 0, n - 2))
            f0, f1, v0, v1 = f[i], f[i + 1], v[i], v[i + 1]
            m0, m1 = self._slope(i), self._slope(i + 1)
        dt = f1 - f0
        t = (fr - f0) / dt
        h00 = 2 * t ** 3 - 3 * t ** 2 + 1
        h10 = t ** 3 - 2 * t ** 2 + t
        h01 = -2 * t ** 3 + 3 * t ** 2
        h11 = t ** 3 - t ** 2
        return h00 * v0 + h10 * dt * m0 + h01 * v1 + h11 * dt * m1

    def _slope(self, i):
        f, v, n = self.f, self.v, len(self.f)
        if self.hold[i]:
            return np.zeros_like(v[i])
        if self.loop is not None:
            fp, vp = (f[i - 1], v[i - 1]) if i > 0 else (f[-1] - self.loop, v[-1])
            fn, vn = (f[i + 1], v[i + 1]) if i < n - 1 else (f[0] + self.loop, v[0])
        else:
            if i == 0 or i == n - 1:
                return np.zeros_like(v[i])
            fp, vp, fn, vn = f[i - 1], v[i - 1], f[i + 1], v[i + 1]
        return (vn - vp) / (fn - fp)


def keyed(keys, default=0.0, loop=None):
    if not keys:
        return lambda fr: np.atleast_1d(np.asarray(default, float))
    return Track(keys, loop)


# ------------------------------------------------------------------ rig controller
class Quad:
    """Species rig description + per-frame solver."""

    def __init__(self, sk, spine=("Spine_01", "Spine_02", "Chest"), neck=("Neck_01", "Neck_02"), tail=None,
                 front_pole=-1.0, hind_pole=1.0):
        self.sk = sk
        self.spine, self.neck = spine, neck
        self.tail = tail or [b.name for b in sk.bones if b.name.startswith("Tail_")]
        self.front_pole, self.hind_pole = front_pole, hind_pole
        self.legs = {}
        for kind, side, s in LEGS:
            g = ("Shoulder_" if kind == "Front" else "Hip_") + side
            chain = [g, f"UpperLeg_{kind}_{side}", f"LowerLeg_{kind}_{side}", f"Foot_{kind}_{side}",
                     f"Toe_{kind}_{side}"]
            heads = [sk.bone(n).head for n in chain]
            tip = sk.bone(chain[-1]).tail
            self.legs[(kind, side)] = {"chain": chain, "rest": heads + [tip], "side": s,
                                       "len": [np.linalg.norm(heads[i + 1] - heads[i]) for i in range(1, 4)] +
                                              [np.linalg.norm(tip - heads[4])]}

    def rest_tip(self, kind, side):
        return self.legs[(kind, side)]["rest"][5].copy()

    def solve(self, pose):
        """pose: dict with 'rot' {bone: quat}, 'off' {bone: vec3}, 'legs' {(kind,side): dict(tip, toe, foot, ik)}.
        Returns local rotations for every bone (including solved legs) and offsets."""
        sk = self.sk
        rot = dict(pose.get("rot", {}))
        off = dict(pose.get("off", {}))
        legs = pose.get("legs", {})
        # FK of everything except the IK-driven leg bones
        pos, wrot = sk.fk(rot, off)
        for key, L in self.legs.items():
            spec = legs.get(key)
            if spec is None or not spec.get("ik", True):
                continue
            chain = L["chain"]
            g, U, Lo, Fo, To = chain
            # girdle (scapula/ilium) authored rotation is already in `rot`
            pg, rg = pos[g], wrot[g]
            A = pg + q_rotate(rg, sk.rest_offset(U))
            tip = np.asarray(spec["tip"], float)
            rest = L["rest"]
            l1, l2, l3, l4 = L["len"]
            # toe (pastern+hoof / digits) direction: rest direction pitched by `toe` about the side axis
            toe_dir = q_rotate(q_axis((0, 0, 1), spec.get("toe", 0.0)), rest[5] - rest[4])
            toe_dir /= np.linalg.norm(toe_dir)
            D = tip - toe_dir * l4
            foot_dir = q_rotate(q_axis((0, 0, 1), spec.get("foot", 0.0)), rest[4] - rest[3])
            foot_dir /= np.linalg.norm(foot_dir)
            C = D - foot_dir * l3
            pole_x = self.front_pole if key[0] == "Front" else self.hind_pole
            pole = A + np.array([pole_x, -0.2, 0.0]) + np.array([0, 0, 0.15 * L["side"]]) * spec.get("splay", 0.0)
            B, Cr, stretched = two_bone_ik(A, l1, l2, C, pole)
            # if C was out of reach, Cr is the clamped point: keep foot/toe directions from there
            if stretched:
                D = Cr + foot_dir * l3
            # convert to local rotations along the chain
            def aim(bone, parent_rot, child, want_dir):
                rest_dir = sk.rest_offset(child)
                w = q_rotate(q_conj(parent_rot), want_dir)
                return q_between(rest_dir, w)
            qU = aim(U, rg, Lo, B - A)
            wU = q_normalize(q_mul(rg, qU))
            qL = aim(Lo, wU, Fo, Cr - B)
            wL = q_normalize(q_mul(wU, qL))
            qF = aim(Fo, wL, To, D - Cr)
            wF = q_normalize(q_mul(wL, qF))
            tip_rest = rest[5] - rest[4]
            wT_dir = q_rotate(q_conj(wF), toe_dir)
            qT = q_between(tip_rest, wT_dir)
            rot[U], rot[Lo], rot[Fo], rot[To] = qU, qL, qF, qT
        return rot, off


import os as _os
SWING_SMOOTH = int(_os.environ.get("CV2_SWING_SMOOTH", "0"))   # passes of a (1/4, 1/2, 1/4) filter over the
                                                            # IK legs while the foot is in the air (0: off)
PUSH = float(_os.environ.get("CV2_PUSH", "0.95"))   # toe flex at push-off (rad): the heel rises, the knee bends


def bake(quad, frames, pose_fn, loop=False):
    """Evaluates pose_fn(frame) -> pose for frames 0..N (inclusive). Returns per-bone arrays.
    The IK leg rotations are then smoothed in time over the frames where that foot is off the ground: a leg that
    comes off a stretched stance bends tens of degrees between two frames (two-bone IK near full reach), which
    the eye reads as a snap (smooth_check.py). Planted frames are left exactly as solved, so contacts do not
    slide."""
    sk = quad.sk
    names = [b.name for b in sk.bones]
    R = {n: [] for n in names}
    T = {n: [] for n in names}
    free = {key: [] for key in quad.legs}
    for fr in range(frames + 1):
        pose = pose_fn(fr)
        rot, off = quad.solve(pose)
        legs = pose.get("legs", {}) or {}
        for key in quad.legs:
            spec = legs.get(key)
            up = spec is not None and spec.get("ik", True) and spec.get("tip") is not None and \
                float(np.asarray(spec["tip"])[1]) > 0.004
            free[key].append(bool(up))
        for n in names:
            R[n].append(rot.get(n, q_identity()))
            T[n].append(sk.rest_offset(n) + off.get(n, np.zeros(3)))
    out = {}
    for n in names:
        r = np.array(R[n], float)
        # keep quaternions in one hemisphere for clean linear interpolation
        for i in range(1, len(r)):
            if np.dot(r[i], r[i - 1]) < 0:
                r[i] = -r[i]
        out[n] = (r, np.array(T[n], float))
    if SWING_SMOOTH and frames >= 4:
        for key, L in quad.legs.items():
            mask = np.array(free[key], bool)
            if not mask.any():
                continue
            for bone in L["chain"][1:]:
                r, t = out[bone]
                out[bone] = (_smooth_free(r, mask, loop, SWING_SMOOTH), t)
    return out


def _smooth_free(r, mask, loop, passes):
    """(1/4, 1/2, 1/4) smoothing of quaternion rows where mask is True (others stay fixed)."""
    r = r.copy()
    n = len(r)
    m = n - 1 if loop else n          # loops: frame N repeats frame 0
    for _ in range(passes):
        src = r.copy()
        for i in range(m):
            if not mask[i] or (not loop and (i == 0 or i == n - 1)):
                continue
            a = src[(i - 1) % m]
            b = src[(i + 1) % m] if (loop or i + 1 < n) else src[i]
            c = src[i]
            a = a if np.dot(a, c) >= 0 else -a
            b = b if np.dot(b, c) >= 0 else -b
            q = 0.25 * a + 0.5 * c + 0.25 * b
            r[i] = q / np.linalg.norm(q)
        if loop:
            r[n - 1] = r[0]
    for i in range(1, n):
        if np.dot(r[i], r[i - 1]) < 0:
            r[i] = -r[i]
    return r


def channels(baked, frames, translate=("MotionRoot", "Pelvis"), eps=1e-5):
    times = np.arange(frames + 1, dtype=np.float32) / FPS
    ch = []
    for name, (r, t) in baked.items():
        if np.max(np.abs(r - r[0])) > eps or np.max(np.abs(r[0] - [0, 0, 0, 1])) > eps:
            ch.append((name, "rotation", times, r.astype(np.float32)))
        if name in translate:
            ch.append((name, "translation", times, t.astype(np.float32)))
    return ch


# ------------------------------------------------------------------ gait
def gait_tip(quad, kind, side, phase, stride, duty, lift, reach=0.0, lateral=0.0):
    """Foot tip position for a gait phase in [0,1): stance first (back-moving), then swing.
    Every curve is continuous across lift-off and touch-down - position, its speed, and the toe / foot angles - so
    nothing snaps between two frames (smooth_check.py): the swing leaves with the stance's backward speed and lands
    with it (Hermite), the foot rises from rest, the push-off toe angle carries into the swing and the landing toe
    angle into the stance."""
    rest = quad.rest_tip(kind, side)
    f_push = (-0.15 if kind == "Front" else 0.10) * PUSH / 0.55
    f_flex = -0.9 if kind == "Front" else 0.75
    if phase < duty:
        s = phase / duty
        x = stride * (0.5 - s)
        y = 0.0
        land = 1.0 - ease(s / 0.15)                 # landing toe angle eases out after touch-down
        push = ease((s - 0.7) / 0.3)                # heel lift / push-off at the end of stance
        toe = 0.25 * land - PUSH * push
        foot = f_push * push
    else:
        s = (phase - duty) / (1 - duty)
        # cubic Hermite from the lift-off point to the touch-down point, leaving and arriving with the stance speed
        m = -stride * (1 - duty) / duty
        h00, h10, h01, h11 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s, -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
        x = h00 * (-0.5 * stride) + h10 * m + h01 * (0.5 * stride) + h11 * m + reach * np.sin(np.pi * s) ** 2
        y = lift * np.sin(np.pi * s)
        flex = np.sin(np.pi * min(1.0, s * 1.15)) ** 2
        lift0 = 1.0 - ease(s / 0.25)                # the push-off pose carries into the swing
        land = ease((s - 0.75) / 0.25)
        toe = -PUSH * lift0 - 1.2 * flex + 0.25 * land
        foot = f_push * lift0 + f_flex * flex
    return rest + np.array([x, y, lateral]), toe, foot


def stance_legs(quad, tips=None, toes=None, feet=None):
    out = {}
    for kind, side, s in LEGS:
        k = (kind, side)
        out[k] = {"tip": (tips or {}).get(k, quad.rest_tip(kind, side)), "toe": (toes or {}).get(k, 0.0),
                  "foot": (feet or {}).get(k, 0.0)}
    return out


# ------------------------------------------------------------------ secondary motion
def spring_chain(drive, n_bones, frames, stiffness=60.0, damping=9.0, lag=1.0, loop=False):
    """Damped spring response for a chain (tail/ears): `drive(fr)` gives the target angle vector (pitch, yaw)
    of the first segment; each further segment follows the previous one with a delay. Returns [frames+1][n][2]."""
    dt = 1.0 / FPS
    passes = 3 if loop else 1
    ang = np.zeros((n_bones, 2))
    vel = np.zeros((n_bones, 2))
    out = []
    for p in range(passes):
        out = []
        for fr in range(frames + 1):
            target = np.asarray(drive(fr), float)
            for i in range(n_bones):
                tgt = target if i == 0 else ang[i - 1] * lag
                acc = stiffness * (tgt - ang[i]) - damping * vel[i]
                vel[i] += acc * dt
                ang[i] += vel[i] * dt
            out.append(ang.copy())
    out = np.array(out)
    if loop:
        # remove the residual seam: blend the last 20% toward the first frame
        k = max(2, frames // 5)
        for j in range(k):
            w = (j + 1) / k
            out[frames - k + 1 + j] = out[frames - k + 1 + j] * (1 - w) + out[0] * w
    return out


# ------------------------------------------------------------------ controller-consistent foot planning
def actor_xform(motion, fr):
    """motion(fr) -> (dx, dz, yaw). Returns 3x3 rotation about +Y and translation for the actor."""
    dx, dz, yaw = motion(fr)
    c, s = np.cos(yaw), np.sin(yaw)
    R = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])  # +yaw turns the +X nose toward -Z (left)
    return R, np.array([dx, 0.0, dz])


def plan_feet(rig, frames, motion, swings, lift=0.18, stance_mid=True):
    """World-planted feet for an actor moved by the controller (`motion`). swings: {(kind, side): [(lift_f, land_f),
    ...]}. Each landing is placed so the foot is under its rest position at the middle of the next stance (or at
    the clip end), giving consistent contacts without sliding. Returns legs_fn(fr, prm)."""
    plans = {}
    for key in rig.legs:
        rest = rig.rest_tip(*key)
        sw = sorted(swings.get(key, []))
        # stance intervals between swings
        world = []
        prev_end = 0
        R0, t0 = actor_xform(motion, 0)
        anchors = []
        bounds = [0] + [x for s in sw for x in s] + [frames]
        stances = [(bounds[i], bounds[i + 1]) for i in range(0, len(bounds), 2)]
        for a, b in stances:
            if stance_mid and b != frames:
                anchor = (a + b) / 2.0
            else:
                anchor = b if a != 0 else a
            if a == 0:
                anchor = 0
            R, t = actor_xform(motion, anchor)
            world.append(R @ rest + t)
        plans[key] = (sw, stances, world)

    def local_of(Wp, fr):
        R, t = actor_xform(motion, fr)
        return R.T @ (Wp - t)

    def legs_fn(fr, prm=None):
        out = {}
        for key, (sw, stances, world) in plans.items():
            tip = None
            toe = foot = 0.0
            for i, (a, b) in enumerate(stances):
                if a <= fr <= b:
                    tip = local_of(world[i], fr)
                    # push-off before a swing
                    if i < len(sw):
                        push = ease((fr - (b - 4)) / 4.0)
                        toe = -PUSH * 0.9 * push
                    break
            if tip is None:
                for i, (a, b) in enumerate(sw):
                    if a < fr < b:
                        s = (fr - a) / float(b - a)
                        p0 = local_of(world[i], a)
                        p1 = local_of(world[i + 1], b)
                        e = ease(s)
                        tip = p0 + (p1 - p0) * e
                        tip = tip + np.array([0, lift * np.sin(np.pi * s), 0])
                        # continuous with the push-off before (toe -0.5) and the flat landing after: no snap
                        flex = np.sin(np.pi * s) ** 2
                        toe = -PUSH * 0.9 * (1.0 - ease(s / 0.3)) - 1.1 * flex
                        foot = (-0.8 if key[0] == "Front" else 0.7) * flex
                        break
            out[key] = {"tip": tip, "toe": toe, "foot": foot}
        return out
    return legs_fn


# ------------------------------------------------------------------ skinning sampler / ground contact
class SkinSampler:
    """Skins a vertex sample with the rig (same maths as the GLB: inverse bind = -rest head)."""

    def __init__(self, sk, pos, joints, weights, names, count=4000, seed=0, extra_points=None, rigid=None):
        rng = np.random.default_rng(seed)
        n = len(pos)
        sel = rng.choice(n, min(n, count), replace=False) if n > count else np.arange(n)
        self.v = pos[sel].astype(float)
        self.j = joints[sel]
        self.w = weights[sel]
        self.rigid = (rigid[sel] if rigid is not None else np.zeros(len(sel), bool))
        self.names = names
        self.sk = sk
        self.heads = np.array([sk.bone(nm).head for nm in names])
        if extra_points is not None:
            pts, bones = extra_points
            self.v = np.concatenate([self.v, pts])
            jj = np.zeros((len(pts), 4), self.j.dtype)
            ww = np.zeros((len(pts), 4), np.float32)
            jj[:, 0] = [names.index(b) for b in bones]
            ww[:, 0] = 1.0
            self.j = np.concatenate([self.j, jj])
            self.w = np.concatenate([self.w, ww])

    def skin(self, rot, off):
        pos, wrot = self.sk.fk(rot, off)
        from qmath import q_to_mat
        M = np.array([q_to_mat(wrot[nm]) for nm in self.names])
        Pp = np.array([pos[nm] for nm in self.names])
        out = np.zeros_like(self.v)
        for k in range(4):
            jk = self.j[:, k]
            rel = self.v - self.heads[jk]
            out += self.w[:, k:k + 1] * (np.einsum("nij,nj->ni", M[jk], rel) + Pp[jk])
        return out

    def min_y(self, rot, off, body_only=False):
        y = self.skin(rot, off)[:, 1]
        if body_only and self.rigid.any():
            y = y[~self.rigid]
        return float(y.min())
