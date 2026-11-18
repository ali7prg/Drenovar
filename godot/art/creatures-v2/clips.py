"""Generic quadruped clip builders, parameterised per species (see species modules).

Every builder returns a clip dict: name, frames (N), fps, loop, events, windows,
motion (controller displacement, optional) and channels. Clip names are
"<species>__<name>"; N follows 03_ANIMATIONS_AND_MATERIALS.txt exactly.
"""
import numpy as np

from anim import Quad, keyed, bake, channels, gait_tip, spring_chain, LEGS, FPS
from qmath import q_euler, q_mul, q_identity, q_axis, ease, smoothstep

# pose parameter names (angles in radians, offsets in metres)
PARAMS = ["px", "py", "pz", "pp", "pyw", "pr", "s1p", "s1y", "s1r", "s2p", "s2y", "s2r", "cp", "cy", "cr",
          "n1p", "n1y", "n1r", "n2p", "n2y", "n2r", "hp", "hy", "hr", "jaw", "nose", "earp", "eary", "tailp", "taily",
          "tailc", "gF", "gH", "belly", "mane"]


class Layered:
    """Sum of parameter layers; each layer maps frame -> {param: value}."""

    def __init__(self):
        self.layers = []

    def add(self, fn):
        self.layers.append(fn)
        return self

    def keys(self, table, loop=None):
        """table: {param: [(frame, value[, 'hold']), ...]}"""
        tracks = {k: keyed(v, loop=loop) for k, v in table.items()}
        self.layers.append(lambda fr: {k: float(t(fr)[0]) for k, t in tracks.items()})
        return self

    def __call__(self, fr):
        out = {k: 0.0 for k in PARAMS}
        for fn in self.layers:
            for k, v in fn(fr).items():
                out[k] = out.get(k, 0.0) + float(v)
        return out


def side_names(sk):
    return [n for n in ("L", "R") if f"Ear_{n}" in sk.by]


def compose(rig, prm, legs, tail_angles=None, extra=None, girdle=None):
    """Parameters -> pose dict for Quad.solve."""
    sk = rig.sk
    rot, off = {}, {}
    rot["Pelvis"] = q_euler(prm["pp"], prm["pyw"], prm["pr"])
    off["Pelvis"] = np.array([prm["px"], prm["py"], prm["pz"]])
    for bone, a in zip(rig.spine, ("s1", "s2", "c")):
        rot[bone] = q_euler(prm[a + "p"], prm[a + "y"], prm[a + "r"])
    for bone, a in zip(list(rig.neck) + ["Head"], ("n1", "n2", "h")):
        rot[bone] = q_euler(prm[a + "p"], prm[a + "y"], prm[a + "r"])
    if "Jaw" in sk.by:
        rot["Jaw"] = q_euler(-prm["jaw"], 0, 0)
    if "Nose" in sk.by:
        rot["Nose"] = q_euler(prm["nose"], 0, 0)
    for n, s in (("L", -1), ("R", 1)):
        if f"Ear_{n}" in sk.by:
            rot[f"Ear_{n}"] = q_euler(prm["earp"], -s * prm["eary"], 0)
    for kind, side, s in LEGS:
        g = ("Shoulder_" if kind == "Front" else "Hip_") + side
        a = prm["gF"] if kind == "Front" else prm["gH"]
        if girdle and (kind, side) in girdle:
            a += girdle[(kind, side)]
        rot[g] = q_euler(a, 0, 0)
    if "Belly" in sk.by:
        off["Belly"] = np.array([0.0, -prm["belly"], 0.0])
    for i, b in enumerate(rig.tail):
        p, y = (tail_angles[i] if tail_angles is not None else (0.0, 0.0))
        rot[b] = q_euler(p + prm["tailc"] * (0.6 + 0.4 * i / max(1, len(rig.tail) - 1)), y, 0)
    for m in ("Mane_01", "Mane_02"):
        if m in sk.by:
            rot[m] = q_euler(prm["mane"], 0, 0)
    if extra:
        for b, q in extra.items():
            rot[b] = q_mul(rot.get(b, q_identity()), q)
    return {"rot": rot, "off": off, "legs": legs}


def tail_drive(prm_fn, amp=1.0):
    def drive(fr):
        p = prm_fn(fr)
        # the tail follows pelvis yaw/pitch with opposite sign plus its own authored swing
        return np.array([p["tailp"] - 0.6 * p["pp"], p["taily"] - 0.8 * p["pyw"]]) * amp
    return drive


def smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def finish(rig, name, frames, loop, pose_fn, events=None, windows=None, motion=None, speed=None, extras=None):
    b = bake(rig, frames, pose_fn)
    clip = {"name": name, "frames": frames, "fps": FPS, "length": frames / FPS, "loop": bool(loop),
            "events": events or [], "channels": channels(b, frames)}
    if windows:
        clip["windows"] = windows
    if motion is not None:
        clip["motion"] = motion
    if speed is not None:
        clip["speed_mps"] = speed
    if extras:
        clip.update(extras)
    clip["_baked"] = b
    return clip


# ------------------------------------------------------------------ locomotion
def locomotion(rig, sp, name, frames, speed, duty, offsets, lift, body, tail_amp=1.0, reach=0.0, extra_keys=None):
    """Cyclic gait. offsets: {(kind, side): phase}; body: callable(phase)->{param: value}."""
    T = frames / FPS
    stride = speed * duty * T
    base = Layered().add(lambda fr: dict(_g(sp, "POSTURE"))).add(lambda fr: body((fr / frames) % 1.0))
    if extra_keys:
        base.keys(extra_keys, loop=frames)
    tails = spring_chain(tail_drive(base, tail_amp), len(rig.tail), frames, 55.0, 8.0, 1.0, loop=True)
    events = []
    for (kind, side), off in offsets.items():
        # footfall (contact) frame of this foot: stance starts at phase 0
        f = int(round(((-off) % 1.0) * frames)) % frames
        events.append({"event": "footstep", "frame": f, "time": f / FPS, "foot": f"{kind.lower()}_{side.lower()}"})

    def pose(fr):
        ph = (fr / frames) % 1.0
        prm = base(fr)
        legs = {}
        for kind, side, s in LEGS:
            lp = (ph + offsets[(kind, side)]) % 1.0
            tip, toe, foot = gait_tip(rig, kind, side, lp, stride, duty, lift * (1.0 if kind == "Front" else 0.9),
                                      reach)
            legs[(kind, side)] = {"tip": tip, "toe": toe, "foot": foot}
        return compose(rig, prm, legs, tails[fr])
    events.sort(key=lambda e: e["frame"])
    return finish(rig, name, frames, True, pose, events, speed=speed)


# ------------------------------------------------------------------ standing clips
def _g(sp, k):
    return sp[k] if isinstance(sp, dict) else getattr(sp, k)


def standing(rig, sp, name, frames, keys, loop=False, events=None, windows=None, legs_fn=None, tail_amp=1.0,
             girdle_fn=None, extra_fn=None, motion=None, idle_overlay=True, root_fn=None, stiff=55.0, damp=8.0):
    """Feet planted (or keyed by legs_fn) while keyed parameters move the body."""
    lay = Layered().add(lambda fr: dict(_g(sp, "POSTURE")))
    if idle_overlay:
        lay.add(lambda fr: breathing(fr, _g(sp, "BREATH_PERIOD_F"), _g(sp, "BREATH_AMP")))
    lay.keys(keys, loop=frames if loop else None)
    tails = spring_chain(tail_drive(lay, tail_amp), len(rig.tail), frames, stiff, damp, 1.0, loop=loop)

    def pose(fr):
        prm = lay(fr)
        legs = legs_fn(fr, prm) if legs_fn else {k: {"tip": rig.rest_tip(*k), "toe": 0.0, "foot": 0.0}
                                                  for k in rig.legs}
        p = compose(rig, prm, legs, tails[fr], extra_fn(fr) if extra_fn else None,
                    girdle_fn(fr) if girdle_fn else None)
        if root_fn:
            p["off"]["MotionRoot"] = root_fn(fr)
        return p
    return finish(rig, name, frames, loop, pose, events, windows, motion)


def breathing(fr, period, amp):
    ph = 2 * np.pi * fr / period
    b = np.sin(ph)
    return {"cp": 0.012 * amp * b, "belly": 0.010 * amp * (0.5 + 0.5 * b), "n1p": -0.006 * amp * b,
            "py": 0.004 * amp * b}


def leg_keys(rig, table, frames):
    """table: {(kind, side): {"dx": keys, "dy": keys, "dz": keys, "toe": keys, "foot": keys}} -> legs_fn."""
    tr = {}
    for k, d in table.items():
        tr[k] = {p: keyed(v) for p, v in d.items()}

    def fn(fr, prm):
        out = {}
        for k in rig.legs:
            rest = rig.rest_tip(*k)
            t = tr.get(k, {})
            dx = float(t["dx"](fr)[0]) if "dx" in t else 0.0
            dy = float(t["dy"](fr)[0]) if "dy" in t else 0.0
            dz = float(t["dz"](fr)[0]) if "dz" in t else 0.0
            out[k] = {"tip": rest + np.array([dx, dy, dz]), "toe": float(t["toe"](fr)[0]) if "toe" in t else 0.0,
                      "foot": float(t["foot"](fr)[0]) if "foot" in t else 0.0}
        return out
    return fn


def step_keys(f0, f1, dx, lift=0.12, dz=0.0, toe=-0.9, foot=-0.6):
    """Keys for one step of a foot from frame f0 to f1 moving dx (and dz)."""
    m = (f0 + f1) / 2
    return {"dx": [(f0, 0.0, "hold"), (m, dx * 0.5), (f1, dx, "hold")],
            "dy": [(f0, 0.0, "hold"), (m, lift), (f1, 0.0, "hold")],
            "dz": [(f0, 0.0, "hold"), (f1, dz, "hold")],
            "toe": [(f0, 0.0), (m, toe), (f1, 0.0)],
            "foot": [(f0, 0.0), (m, foot), (f1, 0.0)]}


def merge_steps(*steps):
    out = {}
    for st in steps:
        for p, keys in st.items():
            out.setdefault(p, []).extend(keys)
    for p in out:
        out[p].sort(key=lambda k: k[0])
        # drop duplicate frames (keep the later key)
        ded = {}
        for k in out[p]:
            ded[k[0]] = k
        out[p] = sorted(ded.values(), key=lambda k: k[0])
    return out


def chain_steps(seq):
    """seq: list of (f0, f1, dx, dz, lift) cumulative steps for one foot."""
    keys = {"dx": [], "dy": [], "dz": [], "toe": [], "foot": []}
    x = z = 0.0
    for f0, f1, dx, dz, lift in seq:
        m = (f0 + f1) / 2
        keys["dx"] += [(f0, x, "hold"), (m, x + dx * 0.5), (f1, x + dx, "hold")]
        keys["dz"] += [(f0, z, "hold"), (m, z + dz * 0.5), (f1, z + dz, "hold")]
        keys["dy"] += [(f0, 0.0, "hold"), (m, lift), (f1, 0.0, "hold")]
        keys["toe"] += [(f0, 0.0), (m, -0.9), (f1, 0.0)]
        keys["foot"] += [(f0, 0.0), (m, -0.6), (f1, 0.0)]
        x += dx
        z += dz
    for p in keys:
        ded = {}
        for k in keys[p]:
            ded[k[0]] = k
        keys[p] = sorted(ded.values(), key=lambda k: k[0])
    return keys


# ------------------------------------------------------------------ death (generic)
def death(rig, sp, sampler, name, N, keys, fk_angles, buckle_end=20, fk_start=18, fk_end=34, lie_frame=40,
          search_bone="Neck_02", search_range=(0.0, -0.9), events=None):
    """Buckle on planted feet, blend the legs to limp FK poses while the body rolls, then rest on the ground.
    Per frame the skinned sample decides the MotionRoot height (never below ground, lying exactly on it after
    `lie_frame`) and a small neck roll keeps rigid horns/antlers from sinking below the body's contact."""
    from qmath import q_euler, q_slerp, q_mul
    lay = Layered().add(lambda fr: dict(_g(sp, "POSTURE"))).keys(keys)
    tails = spring_chain(tail_drive(lay), len(rig.tail), N, 40.0, 6.0)
    lift_log = []

    def pose(fr):
        prm = lay(fr)
        b = smoothstep(4, buckle_end, fr)
        legs = {k: {"tip": rig.rest_tip(*k), "toe": (-0.6 if k[0] == "Front" else -0.3) * b,
                    "foot": (-0.5 if k[0] == "Front" else 0.4) * b} for k in rig.legs}
        rot, off = rig.solve(compose(rig, prm, legs, tails[fr]))
        w = smoothstep(fk_start, fk_end, fr)
        if w > 0:
            for kind, side, s in LEGS:
                for seg in ("UpperLeg", "LowerLeg", "Foot", "Toe"):
                    bn = f"{seg}_{kind}_{side}"
                    a = fk_angles[f"{seg}_{kind}"] * (1.0 + (0.25 if side == "R" else 0.0))
                    rot[bn] = q_slerp(rot[bn], q_euler(a, 0, 0.12 * s), w)
        off = dict(off)
        off["MotionRoot"] = np.zeros(3)
        best = None
        if search_bone in rot and sampler.rigid.any():
            base = rot[search_bone]
            for extra in np.linspace(search_range[0], search_range[1], 10):
                r2 = dict(rot)
                r2[search_bone] = q_mul(base, q_euler(0, 0, extra))
                by = sampler.min_y(r2, off, body_only=True)
                ay = sampler.min_y(r2, off)
                pen = by - ay
                if best is None or pen < best[0] - 1e-4:
                    best = (pen, extra, by, ay)
                if pen <= 0.01:
                    break
            rot[search_bone] = q_mul(base, q_euler(0, 0, best[1]))
            y0 = min(best[2], best[3])
        else:
            y0 = sampler.min_y(rot, off)
        lift = -y0 if (y0 < 0 or fr >= lie_frame) else 0.0
        off["MotionRoot"] = np.array([0.0, lift, 0.0])
        lift_log.append(lift)
        return {"rot": rot, "off": off, "legs": {}}
    clip = finish(rig, name, N, False, pose, events or [{"event": "collapse", "frame": 10},
                                                        {"event": "ground_contact", "frame": lie_frame},
                                                        {"event": "dead", "frame": N}])
    clip["ground_lift"] = [float(v) for v in lift_log]
    return clip


def step_offsets(table):
    """Stance changes made as steps, never slides. table: {(kind, side): [(f0, f1, dx0, dx1, lift), ...]} - the
    foot moves from dx0 to dx1 (metres along +X) between f0 and f1 with an arc of `lift` (use 0 when the move
    rides on a swing that already lifts the foot). Returns fn(fr, key) -> (dx, dy, toe)."""
    from qmath import ease

    def fn(fr, key):
        rows = table.get(key, [])
        dx = 0.0
        for f0, f1, a, b, lift in rows:
            if fr <= f0:
                return a, 0.0, 0.0
            if fr < f1:
                s = (fr - f0) / float(f1 - f0)
                arc = np.sin(np.pi * s)
                return a + (b - a) * ease(s), lift * arc, -0.8 * arc * (1.0 if lift > 0 else 0.0)
            dx = b
        return dx, 0.0, 0.0
    return fn
