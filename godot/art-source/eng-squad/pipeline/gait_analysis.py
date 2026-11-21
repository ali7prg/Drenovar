#!/usr/bin/env python3
"""Gait metrics of in-place locomotion clips from model_probe.gd samples.

For every foot/hoof: stance = frames where the contact point (min of joint heights) is within
`tol` of its minimum; stance velocity = least-squares slope of the forward (z) coordinate.
Implied ground speed v = -slope (model units/s); in game multiply by the actor scale (1.15).
usage: python3 gait_analysis.py <godot_model_probe.json> <out.json>  (needs --sample ids in the probe)
"""
import json, sys
import numpy as np

SCALE = 1.15


def contact_series(frames, joints):
    ys = np.array([[f[j][1] for j in joints] for f in frames])
    zs = np.array([[f[j][2] for j in joints] for f in frames])
    xs = np.array([[f[j][0] for j in joints] for f in frames])
    lo = ys.argmin(1)
    y = ys[np.arange(len(frames)), lo]
    # use the deepest joint of the foot for forward position (toe in toe-off, ankle in heel strike)
    z = zs.mean(1)
    x = xs.mean(1)
    return y, z, x


def stance_runs(mask):
    runs = []
    n = len(mask)
    i = 0
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1]:
                j += 1
            runs.append((i, j))
            i = j + 1
        else:
            i += 1
    # merge wrap-around
    if len(runs) >= 2 and runs[0][0] == 0 and runs[-1][1] == n - 1:
        a = runs.pop(0)
        b = runs.pop(-1)
        runs.append((b[0], a[1] + n))
    return runs


def analyse(sample, feet, tol=0.012):
    frames = sample["frames"][:-1]  # drop duplicated last frame (t = length)
    t = np.array([f["t"] for f in frames])
    length = sample["length"]
    dt = t[1] - t[0]
    out = {}
    for name, joints in feet.items():
        if any(j not in frames[0] for j in joints):
            continue
        y, z, x = contact_series(frames, joints)
        mask = y <= y.min() + tol
        runs = stance_runs(mask)
        slopes = []
        stance_frames = 0
        drift = []
        for a, b in runs:
            idx = np.arange(a, b + 1) % len(frames)
            tt = t[0] + np.arange(len(idx)) * dt
            zz = z[idx]
            stance_frames += len(idx)
            if len(idx) >= 4:
                k = np.polyfit(tt, zz, 1)[0]
                slopes.append(k)
                drift.append(float(np.ptp(x[idx])))
        v = -float(np.mean(slopes)) if slopes else 0.0
        out[name] = {"stance_fraction": round(stance_frames / len(frames), 3), "stance_runs": len(runs),
                     "speed_model": round(v, 4), "speed_game": round(v * SCALE, 4),
                     "z_range": round(float(np.ptp(z)), 4), "lift_max": round(float(y.max() - y.min()), 4),
                     "contact_y": round(float(y.min()), 4), "lateral_drift_in_stance": round(max(drift) if drift else 0.0, 4)}
    speeds = [o["speed_model"] for o in out.values() if o["speed_model"] > 0]
    v = float(np.mean(speeds)) if speeds else 0.0
    return {"length": round(length, 4), "feet": out, "speed_model": round(v, 4), "speed_game": round(v * SCALE, 4),
            "cycle_distance_model": round(v * length, 4), "cycle_distance_game": round(v * length * SCALE, 4)}


def main():
    probe = json.load(open(sys.argv[1]))
    human = {"LeftFoot": ["LeftFoot", "LeftToe"], "RightFoot": ["RightFoot", "RightToe"]}
    horse = {"FrontLHoof": ["FrontLHoof"], "FrontRHoof": ["FrontRHoof"], "HindLHoof": ["HindLHoof"], "HindRHoof": ["HindRHoof"]}
    res = {}
    for key, m in probe["models"].items():
        if "samples" not in m:
            continue
        mounted = "HorseRoot" in m["samples"]["Walk"]["frames"][0]
        feet = horse if mounted else human
        res[key] = {}
        for clip in ("Walk", "Run"):
            if clip in m["samples"]:
                res[key][clip] = analyse(m["samples"][clip], feet, tol=0.015 if mounted else 0.012)
        idle = m["samples"].get("Idle")
        if idle:
            f0 = idle["frames"][0]
            res[key]["idle_pose"] = {k: f0[k] for k in f0 if k != "t"}
    json.dump(res, open(sys.argv[2], "w"), indent=1)
    for key, r in res.items():
        for clip in ("Walk", "Run"):
            if clip in r:
                a = r[clip]
                feet = ", ".join(f"{n}: v={o['speed_model']:.3f} duty={o['stance_fraction']:.2f} lift={o['lift_max']:.3f}" for n, o in a["feet"].items())
                print(f"{key:12s} {clip:4s} T={a['length']:.3f}s v_model={a['speed_model']:.3f} m/s v_game(x1.15)={a['speed_game']:.3f} m/s stride_game={a['cycle_distance_game']:.3f} m | {feet}")


if __name__ == "__main__":
    main()
