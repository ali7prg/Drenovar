"""Clip authoring for «Искра» (lf_horse_origin): numpy FK + analytic leg IK + footstep plans.

Every clip is generated from a *world-space* footstep plan and a virtual root trajectory
(position + yaw).  The exported clip is in place: planted hooves move in root space exactly
opposite to the root motion, so with the documented groundSpeed / yaw curve there is no hoof
sliding.  Secondary motion (tail, mane, ribbon, ears) uses damped springs driven by the
attachment acceleration and is made periodic for loops.

Rotations are authored in *rest-world axes* relative to the parent ("rotate the neck toward
-Z by 5°"), converted to Blender local bases with the rest matrices supplied by the build.
"""
import math

import numpy as np

FPS = 30.0

# --------------------------------------------------------------------------- math helpers


def qmul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return np.array([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2])


def qaxis(axis, ang):
    axis = np.asarray(axis, float)
    n = np.linalg.norm(axis)
    if n < 1e-12 or abs(ang) < 1e-12:
        return np.array([1.0, 0, 0, 0])
    axis = axis / n
    s = math.sin(ang / 2)
    return np.array([math.cos(ang / 2), axis[0] * s, axis[1] * s, axis[2] * s])


def qmat(q):
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


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
    return q / np.linalg.norm(q)


def rotz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def rotx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1.0, 0, 0], [0, c, -s], [0, s, c]])


def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def smoother(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * x * (x * (6 * x - 15) + 10)


def bump(x, a, b, c=None):
    """0 outside [a,b], smooth 1 plateau-less bump peaking in the middle (or at c)."""
    if x <= a or x >= b:
        return 0.0
    c = 0.5 * (a + b) if c is None else c
    if x < c:
        return float(smooth((x - a) / (c - a)))
    return float(smooth((b - x) / (b - c)))


def env(x, a, b, c, d):
    """Trapezoid envelope: 0 before a, ease to 1 at b, hold to c, ease to 0 at d."""
    if x <= a or x >= d:
        return 0.0
    if x < b:
        return float(smoother((x - a) / (b - a)))
    if x <= c:
        return 1.0
    return float(smoother((d - x) / (d - c)))


DEG = math.pi / 180.0


# --------------------------------------------------------------------------- skeleton


class Skel:
    """Rest data: R[name] 4x4 armature-space rest matrices, parent map, order."""

    def __init__(self, rest, parents, lengths):
        self.R = {k: np.asarray(v, float) for k, v in rest.items()}
        self.Rinv = {k: np.linalg.inv(v) for k, v in self.R.items()}
        self.parent = parents
        self.length = lengths
        self.order = []
        seen = set()

        def visit(n):
            if n in seen:
                return
            p = parents.get(n)
            if p:
                visit(p)
            seen.add(n)
            self.order.append(n)

        for n in rest:
            visit(n)

    def head(self, n):
        return self.R[n][:3, 3].copy()

    def tail(self, n):
        return self.R[n][:3, 3] + self.R[n][:3, 1] * self.length[n]

    def unposed(self, n, M):
        p = self.parent.get(n)
        if p is None:
            return self.R[n].copy()
        return M[p] @ self.Rinv[p] @ self.R[n]

    def local_q(self, n, Qw):
        """Rotation given in rest-world axes -> local basis quaternion."""
        R3 = self.R[n][:3, :3]
        return matq(R3.T @ qmat(Qw) @ R3)

    def local_v(self, n, vw):
        return self.R[n][:3, :3].T @ np.asarray(vw, float)


class Pose:
    """Per-frame bone inputs (rest-world rotation quats, world translations, scales)."""

    def __init__(self):
        self.rot = {}      # bone -> quaternion in rest-world axes (relative to parent)
        self.loc = {}      # bone -> world-axes translation
        self.scale = {}    # bone -> (sx, sy, sz) local
        self.ik = {}       # leg -> dict

    def add_rot(self, bone, axis, ang):
        q = qaxis(axis, ang)
        self.rot[bone] = qmul(q, self.rot.get(bone, np.array([1.0, 0, 0, 0])))

    def toward(self, skel, bone, target_dir, ang):
        """Rotate bone (rest direction) toward target_dir by ang (radians)."""
        d = skel.R[bone][:3, 1]
        ax = np.cross(d, np.asarray(target_dir, float))
        if np.linalg.norm(ax) < 1e-9:
            return
        self.add_rot(bone, ax, ang)


def fk_and_basis(skel, pose, leg_solver):
    """Returns ({bone: (loc3, quat4, scale3)} local bases, {bone: 4x4 pose matrices})."""
    M = {}
    basis = {}
    ik_bones = leg_solver.bones
    for n in skel.order:
        if n in ik_bones:
            continue
        U = skel.unposed(n, M)
        q = pose.rot.get(n, np.array([1.0, 0, 0, 0]))
        ql = skel.local_q(n, q)
        lw = pose.loc.get(n)
        ll = skel.local_v(n, lw) if lw is not None else np.zeros(3)
        sc = pose.scale.get(n, (1.0, 1.0, 1.0))
        B = np.eye(4)
        B[:3, :3] = qmat(ql) @ np.diag(sc)
        B[:3, 3] = ll
        M[n] = U @ B
        basis[n] = (ll, ql, np.array(sc, float))
        if n in leg_solver.chain_roots:
            leg_solver.solve(skel, pose, M, basis, n)
    return basis, M


# --------------------------------------------------------------------------- leg IK


OVERREACH = [0.0]


def _circle_ik(a, c, la, lb, bend_dir):
    """2-bone IK in 3-D: joint b with |b-a|=la, |c-b|=lb, bending toward bend_dir."""
    ac = c - a
    D = np.linalg.norm(ac)
    OVERREACH[0] = max(OVERREACH[0], D - (la + lb))
    D = min(max(D, abs(la - lb) + 1e-4), la + lb - 1e-4)
    u = ac / max(np.linalg.norm(ac), 1e-9)
    x = (la * la - lb * lb + D * D) / (2 * D)
    h = math.sqrt(max(la * la - x * x, 0.0))
    w = bend_dir - (bend_dir @ u) * u
    w /= max(np.linalg.norm(w), 1e-9)
    return a + u * x + w * h


def _frame(y, xref):
    y = y / np.linalg.norm(y)
    x = xref - (xref @ y) * y
    x /= np.linalg.norm(x)
    z = np.cross(x, y)
    return np.stack([x, y, z], 1)


class Legs:
    """Analytic IK for horse fore/hind limbs (in-place root space)."""

    def __init__(self, skel):
        self.skel = skel
        self.bones = set()
        self.chain_roots = {}
        for s in ("L", "R"):
            self.bones |= {f"scapula_{s}", f"humerus_{s}", f"forearm_{s}", f"cannon_F_{s}",
                           f"pastern_F_{s}", f"hoof_F_{s}", f"femur_{s}", f"tibia_{s}",
                           f"cannon_H_{s}", f"pastern_H_{s}", f"hoof_H_{s}"}
        # chains are solved right after their parent bone is posed
        self.chain_roots = {"spine_03": ["F_L", "F_R"], "pelvis": ["H_L", "H_R"]}
        self.last_over = {}
        self.toe_actual = {}
        sk = skel
        self.toe_rest = {}
        for s in ("L", "R"):
            for fh in ("F", "H"):
                hoof = f"hoof_{fh}_{s}"
                # toe point of the hoof (front of the sole) in rest
                tail = sk.tail(hoof)
                self.toe_rest[f"{fh}_{s}"] = tail + np.array([0, -0.075, 0.0]) * 1.0
                self.toe_rest[f"{fh}_{s}"][2] = 0.0

    def solve(self, skel, pose, M, basis, parent_name):
        for leg in self.chain_roots[parent_name]:
            prm = pose.ik.get(leg)
            if prm is None:
                prm = dict(toe=self.toe_rest[leg].copy(), pitch=0.0, yaw=0.0, fet=0.0,
                           knee=0.0, scap=0.0, cannon=0.0, abduct=0.0)
            if leg[0] == "F":
                self._fore(skel, prm, M, basis, leg[2])
            else:
                self._hind(skel, prm, M, basis, leg[2])

    # hoof -> coffin -> fetlock (common to both)
    def _distal(self, skel, prm, fh, s, lateral):
        sk = skel
        hoof = f"hoof_{fh}_{s}"
        Rh = sk.R[hoof]
        toe_r = self.toe_rest[f"{fh}_{s}"]
        Rot = rotz(prm.get("yaw", 0.0)) @ _axis_rot(lateral, prm.get("pitch", 0.0))
        Mh = np.eye(4)
        Mh[:3, :3] = Rot @ Rh[:3, :3]
        Mh[:3, 3] = prm["toe"] + Rot @ (Rh[:3, 3] - toe_r)
        coffin = Mh[:3, 3]
        # pastern direction (fetlock -> coffin) expressed in the hoof frame at rest
        past = f"pastern_{fh}_{s}"
        dp_rest = sk.R[past][:3, 1]
        dp_h = Rh[:3, :3].T @ dp_rest
        dp = Mh[:3, :3] @ (_axis_rot(np.array([1.0, 0, 0]), -prm.get("fet", 0.0)) @ dp_h)
        fet = coffin - dp * sk.length[past]
        return Mh, coffin, fet

    def _fore(self, skel, prm, M, basis, s):
        sk = skel
        names = [f"scapula_{s}", f"humerus_{s}", f"forearm_{s}", f"cannon_F_{s}",
                 f"pastern_F_{s}", f"hoof_F_{s}"]
        lat = M["spine_03"][:3, :3] @ (sk.R["spine_03"][:3, :3].T @ np.array([1.0, 0, 0]))
        lat = lat / np.linalg.norm(lat)
        # scapula: rotate about the lateral axis around its top
        Us = sk.unposed(names[0], M)
        top = Us[:3, 3]
        Rs = _axis_rot(lat, prm.get("scap", 0.0)) @ Us[:3, :3]
        shoulder = top + Rs[:, 1] * sk.length[names[0]]
        Mh, coffin, fet = self._distal(sk, prm, "F", s, lat)
        # knee flexion: cannon rotated backward relative to the forearm by `knee`
        Lh, Lf, Lc = (sk.length[n] for n in names[1:4])
        rest_rel = _signed_angle(sk.R[names[2]][:3, 1], sk.R[names[3]][:3, 1], np.array([1.0, 0, 0]))
        kappa = rest_rel + prm.get("knee", 0.0)
        # virtual link elbow->fetlock
        Lv = math.sqrt(Lf * Lf + Lc * Lc + 2 * Lf * Lc * math.cos(kappa))
        Mh, coffin, fet = self._reach(f"F_{s}", shoulder, fet, Lh + Lv, Mh, coffin)
        back = np.cross(lat, np.array([0, 0, 1.0]))   # lateral x up = -Y? -> ensure +Y (back)
        if back[1] < 0:
            back = -back
        elbow = _circle_ik(shoulder, fet, Lh, Lv, back)
        # forearm direction: rotate (elbow->fet) by -beta about lateral
        v = fet - elbow
        beta = math.atan2(Lc * math.sin(kappa), Lf + Lc * math.cos(kappa))
        uf = _axis_rot(lat, -beta) @ (v / np.linalg.norm(v))
        knee = elbow + uf * Lf
        joints = [top, shoulder, elbow, knee, fet, coffin]
        self._emit(sk, names, joints, Mh, lat, M, basis, Rs)

    def _reach(self, leg, root, fet, reach, Mh, coffin):
        """Pull an unreachable hoof toward the limb root (keeps the chain connected)."""
        D = np.linalg.norm(fet - root)
        over = D - (reach - 0.002)
        self.last_over[leg] = over
        if over > 0:
            shift = (fet - root) / D * over
            fet = fet - shift
            coffin = coffin - shift
            Mh = Mh.copy()
            Mh[:3, 3] -= shift
        hoof = f"hoof_{leg[0]}_{leg[2]}"
        Rh = self.skel.R[hoof]
        self.toe_actual[leg] = Mh[:3, :3] @ (Rh[:3, :3].T @ (self.toe_rest[leg] - Rh[:3, 3])) + Mh[:3, 3]
        return Mh, coffin, fet

    def _hind(self, skel, prm, M, basis, s):
        sk = skel
        names = [f"femur_{s}", f"tibia_{s}", f"cannon_H_{s}", f"pastern_H_{s}", f"hoof_H_{s}"]
        lat = M["pelvis"][:3, :3] @ (sk.R["pelvis"][:3, :3].T @ np.array([1.0, 0, 0]))
        lat /= np.linalg.norm(lat)
        Uf = sk.unposed(names[0], M)
        hip = Uf[:3, 3]
        Mh, coffin, fet = self._distal(sk, prm, "H", s, lat)
        Lf, Lt, Lc = (sk.length[n] for n in names[:3])
        # cannon direction (hock -> fetlock): rest direction rotated by `cannon` about lateral
        dc_rest = sk.R[names[2]][:3, 1]
        rootrot = M["pelvis"][:3, :3] @ sk.R["pelvis"][:3, :3].T
        dc = _axis_rot(lat, prm.get("cannon", 0.0)) @ (rootrot @ dc_rest)
        hock = fet - dc * Lc
        D = np.linalg.norm(hock - hip)
        over = D - (Lf + Lt - 0.002)
        self.last_over[f"H_{s}"] = over
        if over > 0:
            shift = (hock - hip) / D * over
            hock = hock - shift
            fet = fet - shift
            coffin = coffin - shift
            Mh = Mh.copy()
            Mh[:3, 3] -= shift
        self.toe_actual[f"H_{s}"] = Mh[:3, :3] @ (sk.R[names[4]][:3, :3].T @
                                                  (self.toe_rest[f"H_{s}"] - sk.R[names[4]][:3, 3])) + Mh[:3, 3]
        fwd = -np.cross(lat, np.array([0, 0, 1.0]))
        if fwd[1] > 0:
            fwd = -fwd
        stifle = _circle_ik(hip, hock, Lf, Lt, fwd)
        joints = [hip, stifle, hock, fet, coffin]
        self._emit(sk, names, joints, Mh, lat, M, basis, None)

    def _emit(self, sk, names, joints, Mh, lat, M, basis, Rs):
        for i, n in enumerate(names):
            if n.startswith("hoof"):
                Mp = Mh
            else:
                h = joints[i]
                t = joints[i + 1]
                F = _frame(t - h, lat)
                Mp = np.eye(4)
                Mp[:3, :3] = F
                Mp[:3, 3] = h
            U = sk.unposed(n, M)
            B = np.linalg.inv(U) @ Mp
            M[n] = Mp
            loc = B[:3, 3]
            basis[n] = (loc, matq(B[:3, :3]), np.ones(3))


def _axis_rot(axis, ang):
    return qmat(qaxis(axis, ang))


def _signed_angle(a, b, axis):
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    return math.atan2(np.cross(a, b) @ axis, a @ b)


# --------------------------------------------------------------------------- footstep plans


class LegPlan:
    def __init__(self, contacts, lift=0.1, bo=0.12, swing_pitch=1.0, knee=1.0, fet_swing=0.6,
                 fet_load=0.15):
        """contacts: list of (t_land, t_lift, toe_xy_world (2,), yaw)."""
        self.c = sorted(contacts, key=lambda c: c[0])
        self.lift = lift
        self.bo = bo
        self.swing_pitch = swing_pitch
        self.knee = knee
        self.fet_swing = fet_swing
        self.fet_load = fet_load

    def state(self, t):
        c = self.c
        for k, (tl, tf, p, yaw) in enumerate(c):
            if tl <= t <= tf:
                dur = tf - tl
                s = (t - tl) / max(dur, 1e-6)
                bo = max(0.0, (t - (tf - self.bo * dur)) / max(self.bo * dur, 1e-6)) if \
                    k + 1 < len(c) else 0.0
                load = math.sin(math.pi * min(1.0, s / 0.85)) if s < 0.85 else 0.0
                return dict(toe=np.array([p[0], p[1], 0.0]), yaw=yaw, pitch=0.55 * bo * bo,
                            knee=0.15 * bo * self.knee, fet=self.fet_load * load - 0.25 * bo * bo,
                            swing=-1.0, stance=s)
            if k + 1 < len(c) and tf < t < c[k + 1][0]:
                tn = c[k + 1][0]
                s = (t - tf) / (tn - tf)
                p0, p1 = np.asarray(p, float), np.asarray(c[k + 1][2], float)
                e = smooth(min(1.0, s * 1.08))
                xy = p0 + (p1 - p0) * e
                h = self.lift * math.sin(math.pi * min(1.0, s ** 0.85)) ** 1.2
                yaw = yaw + (c[k + 1][3] - yaw) * e
                pitch = self.swing_pitch * (0.55 + 0.9 * math.sin(math.pi * min(1, s / 0.75))) * \
                    (1 - smooth((s - 0.55) / 0.4)) + (-0.06) * bump(s, 0.7, 1.0, 0.92)
                knee = self.knee * math.sin(math.pi * min(1.0, s / 0.8)) ** 1.1
                fet = -self.fet_swing * math.sin(math.pi * min(1.0, s / 0.85))
                return dict(toe=np.array([xy[0], xy[1], h]), yaw=yaw, pitch=pitch, knee=knee,
                            fet=fet, swing=s, stance=-1.0)
        # before the first / after the last contact
        tl, tf, p, yaw = c[0] if t < c[0][0] else c[-1]
        return dict(toe=np.array([p[0], p[1], 0.0]), yaw=yaw, pitch=0.0, knee=0.0, fet=0.0,
                    swing=-1.0, stance=0.5)


def periodic_plan(T, v, duty, offset, toe_neutral, n_before=3, n_after=3):
    """Constant-speed gait: root at (0, -v t); contacts land at the front of the sweep."""
    sweep = v * duty * T
    contacts = []
    for k in range(-n_before, n_after + 1):
        tl = (offset + k) * T
        tf = tl + duty * T
        land_root = np.array([toe_neutral[0], toe_neutral[1] - sweep / 2])
        world = land_root + np.array([0.0, -v * tl])
        contacts.append((tl, tf, world, 0.0))
    return contacts


# --------------------------------------------------------------------------- springs


def spring_track(drive, dt, freq=2.2, zeta=0.35, gain=1.0, periodic=True, passes=3):
    """Damped oscillator response x'' + 2ζω x' + ω² x = gain*drive (per-sample input)."""
    w = 2 * math.pi * freq
    n = len(drive)
    seq = list(drive) * (passes if periodic else 1)
    x, xv = 0.0, 0.0
    out = []
    sub = 4
    h = dt / sub
    for d in seq:
        for _ in range(sub):
            a = gain * d - 2 * zeta * w * xv - w * w * x
            xv += a * h
            x += xv * h
        out.append(x)
    out = np.array(out[-n:])
    if periodic and n > 1:
        out = out - np.linspace(0, out[-1] - out[0], n)   # exact loop closure
    return out


def accel(series, dt):
    s = np.asarray(series, float)
    a = np.zeros_like(s)
    a[1:-1] = (s[2:] - 2 * s[1:-1] + s[:-2]) / (dt * dt)
    a[0], a[-1] = a[1], a[-2]
    return a


# --------------------------------------------------------------------------- clip generator


class ClipBuilder:
    def __init__(self, skel, J):
        self.skel = skel
        self.J = J
        self.legs = Legs(skel)
        self.toe0 = {k: v.copy() for k, v in self.legs.toe_rest.items()}

    # ---- per-clip helpers
    def times(self, T):
        n = max(1, int(round(T * FPS)))
        return np.linspace(0.0, T, n + 1)

    def neutral_toes(self, narrow=0.92):
        """Symmetric walking stance (hind legs square) used by locomotion."""
        t = {}
        fy = 0.5 * (self.toe0["F_L"][1] + self.toe0["F_R"][1]) - 0.05
        hy = 0.5 * (self.toe0["H_L"][1] + self.toe0["H_R"][1]) - 0.06
        for leg, v in self.toe0.items():
            y = fy if leg[0] == "F" else hy
            t[leg] = np.array([v[0] * narrow, y])
        return t

    def root_space(self, plan_state, root_pos, yaw):
        st = dict(plan_state)
        w = st["toe"]
        p = rotz(-yaw) @ (np.array([w[0], w[1], w[2]]) - np.array([root_pos[0], root_pos[1], 0.0]))
        st["toe"] = p
        st["yaw"] = st["yaw"] - yaw
        return st

    def compensate(self, frames, loop, gain=1.15, passes=2):
        """Lower the body where planted legs cannot reach (stride extremes)."""
        n = len(frames)
        for _ in range(passes):
            need = np.zeros(n)
            for k, pose in enumerate(frames):
                fk_and_basis(self.skel, pose, self.legs)
                o = [self.legs.last_over.get(leg, 0.0) for leg, prm in pose.ik.items()
                     if prm.get("_stance", -1.0) >= 0]
                need[k] = max([0.0] + o)
            if need.max() <= 0.003:
                break
            # widen + smooth the requirement (circular for loops)
            from scipy import ndimage as ndi
            mode = "wrap" if loop else "nearest"
            need = ndi.maximum_filter1d(need, 5, mode=mode)
            need = ndi.gaussian_filter1d(need, 1.5, mode=mode)
            for k, pose in enumerate(frames):
                l = pose.loc.get("spine_02", np.zeros(3)).copy()
                l[2] -= gain * need[k]
                pose.loc["spine_02"] = l
        return frames

    def evaluate(self, frames_inputs):
        """frames_inputs: list of Pose -> list of {bone: (loc, quat, scale)}."""
        out = []
        prev = {}
        self.toe_track = []
        for pose in frames_inputs:
            basis, M = fk_and_basis(self.skel, pose, self.legs)
            self.toe_track.append({k: v.copy() for k, v in self.legs.toe_actual.items()})
            fr = {}
            for n, (l, q, s) in basis.items():
                if n in prev and prev[n] @ q < 0:
                    q = -q
                prev[n] = q
                fr[n] = (l, q, s)
            out.append(fr)
        return out

    def hoof_world_positions(self, pose_frames, root_traj):
        """For slip QA: world toe positions of each leg per frame (root-space -> world)."""
        res = {k: [] for k in self.toe0}
        for (pose, (rp, yaw)) in zip(pose_frames, root_traj):
            for leg, prm in pose.ik.items():
                p = rotz(yaw) @ prm["toe"] + np.array([rp[0], rp[1], 0.0])
                res[leg].append((p, prm.get("_stance", -1.0)))
        return res
