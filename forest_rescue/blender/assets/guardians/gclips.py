"""Generic quadruped clips (in place, 30 fps) parametrised per species; Attack comes from the spec.

Rotation conventions (rest-frame world axes, degrees):
  forward-pointing chain bones (spine/neck/head/jaw): rx>0 tips down, rz>0 turns left
  tail bones (point back): rx>0 lifts the tail, rz>0 swings it to the left
"""
import math

import numpy as np

import ganim
from ganim import keys_cr, keys_smooth, ss

TAU = 2 * math.pi


def _chains(P):
    return P["spine"], P["neck"], P["tail"]


def tail_rot(P, t, base_amp=1.0, sway=0.0, freq=1.0, lift=0.0, lag=0.08, extra=None):
    """Tail with travelling wave (follow-through = phase delay per bone)."""
    out = {}
    tb = P["tail"]
    n = len(tb)
    for i, b in enumerate(tb):
        k = (i + 1) / n
        rx = P["tail_base"][i] * base_amp + lift * (1.0 - 0.5 * k)
        rz = sway * (0.35 + k) * math.sin(TAU * freq * (t - i * lag))
        if extra is not None:
            ex = extra(i, t)
            rx += ex[0]
            rz += ex[1]
        out[b] = (rx, 0.0, rz)
    return out


def planted(C, legs=None, **kw):
    return {leg: dict(pos=C.neutral[leg], **kw) for leg in (legs or C.legs)}


# --------------------------------------------------------------------------- Idle

def idle(C, P):
    T = P.get("idle_T", 4.0)

    def frame(t):
        w = TAU * t / T
        breath = math.sin(2 * w)
        body = (0.012 * math.sin(w), 0.008 * math.sin(w + 1.0), 0.008 * breath - 0.004, 0.4 * breath,
                0.8 * math.sin(w), 0.0)
        rot = {}
        sp = P["spine"]
        for i, b in enumerate(sp):
            rot[b] = (0.6 * breath * (1 if i == len(sp) - 1 else -0.5), 0.0, 0.6 * math.sin(w + 0.4))
        look = 11.0 * math.sin(w + 0.6) + 4.0 * math.sin(2 * w + 1.3)
        nk = P["neck"]
        rot[nk[0]] = (1.5 * math.sin(w), 0.0, 0.35 * look)
        rot[nk[1]] = (-1.0 * math.sin(w), 0.0, 0.35 * look)
        rot["head"] = (-1.5 + 2.0 * math.sin(2 * w + 0.5), 2.0 * math.sin(w), 0.3 * look)
        if "jaw" in P.get("bones", ()):
            rot["jaw"] = (1.0 + 1.0 * max(0.0, math.sin(2 * w)), 0, 0)
        for s, ph in (("L", 0.35), ("R", 0.72)):
            e = f"ear_{s}"
            if e in P.get("bones", ()):
                tw = math.exp(-((((t / T) - ph) % 1.0) * T - 0.15) ** 2 / 0.01) if True else 0
                rot[e] = (-14.0 * tw + 3.0 * math.sin(w + ph * 6), 0.0, 6.0 * tw)
        rot.update(tail_rot(P, t, sway=P.get("idle_tail_sway", 6.0), freq=1.0 / T,
                            lag=P.get("tail_lag", 0.1) * 2.0,
                            extra=lambda i, t: (P.get("idle_tail_curl", 4.0) * math.sin(TAU * t / T * 2 - i * 0.6), 0)))
        for b in P.get("mane", []):
            rot[b] = (1.5 * math.sin(2 * w - 0.8), 0, 0)
        return dict(body=body, rot=rot, feet=planted(C))
    return ganim.sample(frame, T, loop=True)


# --------------------------------------------------------------------------- locomotion

def locomotion(C, P, kind="walk"):
    g = P[kind]
    T, v, duty = g["T"], g["speed"], g["duty"]
    sweep = v * duty * T
    td = g["touchdown"]               # leg -> touchdown phase fraction

    def frame(t):
        ph = t / T
        w = TAU * ph
        feet = {}
        for leg, off in td.items():
            front = leg in C.front
            fwd, h, meta, toe, gird, st = ganim.foot_gait(ph - off, duty, sweep * g.get("sweep_f" if front else "sweep_h", 1.0),
                                                          g["lift_f" if front else "lift_h"], front=front,
                                                          fold=g.get("fold_f" if front else "fold_h"),
                                                          heel=g.get("heel", 34.0))
            n = C.neutral[leg]
            feet[leg] = dict(pos=n + np.array([0.0, -fwd, h]), meta=meta, toe=toe, girdle=gird * g.get("girdle", 1.0),
                             stance=st)
        bob = g["bob"] * math.cos(2 * w + g.get("bob_phase", 0.0))
        body = (g["sway"] * math.sin(w), 0.0, bob + g.get("height", 0.0),
                g["pitch"] * math.sin(2 * w + g.get("pitch_phase", 0.0)) + g.get("pitch0", 0.0),
                g["roll"] * math.sin(w + 0.4), g["yaw"] * math.sin(w))
        rot = {}
        sp = P["spine"]
        flex = g.get("flex", 0.0)
        for i, b in enumerate(sp):
            k = (i - (len(sp) - 1) / 2.0)
            rot[b] = (flex * math.cos(w * g.get("flex_mult", 2) + g.get("flex_phase", 0.0)) * (1 if i < len(sp) - 1 else -1),
                      0.0, g["spine_yaw"] * math.sin(w + 0.6 + k * 0.5))
        nk = P["neck"]
        hp = g.get("head_pitch", 0.0)
        rot[nk[0]] = (g.get("neck_pitch0", 0.0) - 0.6 * g["pitch"] * math.sin(2 * w + g.get("pitch_phase", 0.0)),
                      0.0, -0.5 * g["yaw"] * math.sin(w))
        rot[nk[1]] = (-0.3 * g["pitch"] * math.sin(2 * w + 0.3), 0.0, -0.4 * g["yaw"] * math.sin(w))
        rot["head"] = (hp + 0.5 * g["pitch"] * math.sin(2 * w + 0.6) + g.get("head_nod", 0.0) * math.sin(2 * w + 1.2),
                       0.0, -0.5 * g["yaw"] * math.sin(w - 0.3))
        for s in ("L", "R"):
            e = f"ear_{s}"
            if e in P.get("bones", ()):
                rot[e] = (g.get("ears", 0.0) + 2.0 * math.sin(2 * w + (0 if s == "L" else 1.0)), 0, 0)
        rot.update(tail_rot(P, t, sway=g["tail_sway"], freq=1.0 / T, lift=g.get("tail_lift", 0.0),
                            lag=P.get("tail_lag", 0.08),
                            extra=lambda i, t: (g.get("tail_bounce", 0.0) * math.sin(2 * TAU * t / T - i * 0.7), 0)))
        for i, b in enumerate(P.get("mane", [])):
            rot[b] = (g.get("mane_bounce", 3.0) * math.sin(2 * w - 1.0 - 0.5 * i), 0, 0)
        return dict(body=body, rot=rot, feet=feet)
    frames = ganim.sample(frame, T, loop=True)
    meta = {"groundSpeed_mps": v, "strideLength_m": round(v * T, 3), "duty": duty,
            "footfalls": ganim.touchdowns(td, duty, T)}
    return frames, meta


# --------------------------------------------------------------------------- Hit

def hit(C, P, seconds=14 / 30):
    def frame(t):
        u = t / seconds
        k = keys_cr(u, [(0, 0), (0.18, 1.0), (0.45, 0.55), (1.0, 0.0)])
        body = (0.03 * k, 0.07 * k, -0.05 * k, 2.5 * k, -4.0 * k, 4.0 * k)
        rot = {}
        for i, b in enumerate(P["spine"]):
            rot[b] = (-2.0 * k, 0, 2.5 * k)
        nk = P["neck"]
        rot[nk[0]] = (-8.0 * k, 0, 6.0 * k)
        rot[nk[1]] = (-6.0 * k, 0, 4.0 * k)
        rot["head"] = (-6.0 * k, 4.0 * k, 3.0 * k)
        if "jaw" in P.get("bones", ()):
            rot["jaw"] = (14.0 * k, 0, 0)
        for s in ("L", "R"):
            if f"ear_{s}" in P.get("bones", ()):
                rot[f"ear_{s}"] = (-30.0 * k, 0, 0)
        kk = lambda i, t: (-12.0 * keys_cr(max(0.0, u - 0.05 * i), [(0, 0), (0.25, 1.0), (0.6, -0.4), (1.0, 0)]),
                           8.0 * keys_cr(max(0.0, u - 0.06 * i), [(0, 0), (0.3, 1.0), (1.0, 0)]))
        rot.update(tail_rot(P, t, extra=kk))
        for b in P.get("mane", []):
            rot[b] = (8.0 * k, 0, 0)
        return dict(body=body, rot=rot, feet=planted(C))
    return ganim.sample(frame, seconds)


# --------------------------------------------------------------------------- Roar

def roar(C, P, seconds=2.0):
    def frame(t):
        u = t / seconds
        rise = keys_cr(u, [(0, 0), (0.18, -0.25), (0.35, 1.0), (0.75, 1.0), (1.0, 0.0)])
        shake = math.sin(TAU * 7 * t) * keys_smooth(u, [(0, 0), (0.4, 0), (0.48, 1), (0.72, 1), (0.8, 0), (1, 0)])
        body = (0.0, 0.04 * rise, -0.02 * rise, 3.0 * rise, 0.0, 0.0)
        rot = {}
        for i, b in enumerate(P["spine"]):
            rot[b] = (-2.0 * rise, 0, 0)
        nk = P["neck"]
        rot[nk[0]] = (-P.get("roar_neck", 14.0) * rise, 0, 1.5 * shake)
        rot[nk[1]] = (-P.get("roar_neck", 14.0) * 0.7 * rise, 0, 1.5 * shake)
        rot["head"] = (-P.get("roar_head", 10.0) * rise + 2.0 * shake, 2.0 * shake, 0)
        if "jaw" in P.get("bones", ()):
            rot["jaw"] = (P.get("roar_jaw", 34.0) * keys_cr(u, [(0, 0), (0.25, 0.1), (0.38, 1.0), (0.74, 1.0), (0.9, 0.0), (1, 0)])
                          + 1.5 * shake, 0, 0)
        for s in ("L", "R"):
            if f"ear_{s}" in P.get("bones", ()):
                rot[f"ear_{s}"] = (-40.0 * rise, 0, 0)
        rot.update(tail_rot(P, t, lift=P.get("roar_tail_lift", 18.0) * rise, sway=10.0 * rise, freq=1.5,
                            lag=P.get("tail_lag", 0.08)))
        for b in P.get("mane", []):
            rot[b] = (P.get("mane_bristle", 14.0) * rise + 2 * shake, 0, 0)
        return dict(body=body, rot=rot, feet=planted(C))
    return ganim.sample(frame, seconds)


# --------------------------------------------------------------------------- Alert

def alert(C, P, seconds=1.2):
    A = P["alert_pose"]

    def frame(t):
        u = t / seconds
        k = keys_cr(u, [(0, 0), (0.15, 0.35), (0.45, 1.05), (0.7, 0.97), (1.0, 1.0)])
        snap = keys_cr(u, [(0, 0), (0.12, 1.0), (0.4, 0.6), (1.0, 0.0)])
        body = tuple(np.asarray(A["body"]) * k)
        rot = {b: tuple(np.asarray(r) * k) for b, r in A["rot"].items()}
        nk = P["neck"]
        rot[nk[0]] = tuple(np.asarray(rot.get(nk[0], (0, 0, 0))) + np.array([-10.0 * snap, 0, 0]))
        rot["head"] = tuple(np.asarray(rot.get("head", (0, 0, 0))) + np.array([-8.0 * snap, 0, 0]))
        for s in ("L", "R"):
            if f"ear_{s}" in P.get("bones", ()):
                rot[f"ear_{s}"] = (12.0 * snap - 28.0 * ss((u - 0.35) / 0.4), 0, 0)
        lash = lambda i, t: (0, 14.0 * math.sin(TAU * 1.6 * (t - 0.07 * i)) * ss(u / 0.3))
        tr = tail_rot(P, t, lift=A.get("tail_lift", 10.0) * k, extra=lash)
        rot.update(tr)
        for b in P.get("mane", []):
            rot[b] = (P.get("mane_bristle", 14.0) * k, 0, 0)
        feet = planted(C)
        return dict(body=body, rot=rot, feet=feet)
    return ganim.sample(frame, seconds)


# --------------------------------------------------------------------------- Death

def death(C, P, seconds=2.8, side=-1.0, dz_fix=0.0):
    """Stagger, front legs buckle, roll onto the side, settle (stable final pose)."""
    lie = (P["death_lie"][0] + dz_fix, P["death_lie"][1])     # (dz, roll) final

    def frame(t):
        u = t / seconds
        stag = keys_cr(u, [(0, 0), (0.08, 1.0), (0.2, 0.4), (0.3, 0.7), (0.4, 0.0), (1, 0)])
        drop = keys_cr(u, [(0, 0), (0.22, 0.05), (0.42, 0.45), (0.58, 1.0), (0.66, 0.97), (1.0, 1.0)])
        rollk = keys_cr(u, [(0, 0), (0.3, 0.0), (0.5, 0.35), (0.62, 1.0), (0.7, 0.96), (1, 1.0)])
        body = (side * 0.10 * stag + side * 0.25 * rollk, 0.10 * stag, lie[0] * drop,
                -6.0 * drop + 4.0 * stag, lie[1] * rollk * -side, 6.0 * stag)
        rot = {}
        for i, b in enumerate(P["spine"]):
            rot[b] = (3.0 * drop, 0, -4.0 * rollk * side)
        nk = P["neck"]
        hd = keys_cr(u, [(0, 0), (0.1, -1.0), (0.3, -0.6), (0.62, 0.6), (0.8, 1.0), (1, 1.0)])
        rot[nk[0]] = (P.get("death_neck", 18.0) * hd, 0, -10.0 * rollk * side)
        rot[nk[1]] = (P.get("death_neck", 18.0) * 0.6 * hd, 0, -8.0 * rollk * side)
        rot["head"] = (10.0 * hd, -12.0 * rollk * side, 0)
        if "jaw" in P.get("bones", ()):
            rot["jaw"] = (keys_cr(u, [(0, 0), (0.1, 22.0), (0.35, 8.0), (0.8, 6.0), (1, 6.0)]), 0, 0)
        for s in ("L", "R"):
            if f"ear_{s}" in P.get("bones", ()):
                rot[f"ear_{s}"] = (-35.0 * ss(u / 0.4), 0, 0)
        limp = lambda i, t: (-P["tail_base"][i] * 0.8 * drop - 6.0 * drop, side * 10.0 * rollk * (i + 1) / len(P["tail"]))
        rot.update(tail_rot(P, t, extra=limp))
        for b in P.get("mane", []):
            rot[b] = (-6.0 * drop, 0, 0)
        # feet: planted while standing, then carried by the body (limp, slightly folded)
        feet = {}
        follow = ss((u - 0.38) / 0.22)
        for leg in C.legs:
            n = C.neutral[leg]
            front = leg in C.front
            buckle = (0.0, -0.10 if front else 0.05, 0.0)
            planted_pos = n + np.array(buckle) * drop
            fold = np.array([0.0, (0.12 if front else -0.10), 0.20 if front else 0.12])
            carried = C.body_point(body, n + fold)
            pos = planted_pos * (1 - follow) + carried * follow
            feet[leg] = dict(pos=pos, meta=30.0 * follow + (12.0 if front else 0.0) * drop,
                             toe=25.0 * follow, girdle=8.0 * follow if front else 0.0, body_w=follow)
        return dict(body=body, rot=rot, feet=feet)
    return ganim.sample(frame, seconds)
