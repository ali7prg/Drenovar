"""Foot sliding of the authored clips before export (same rule as foot_check.py on the GLB): planted foot sockets
(< 2 cm above the ground) must stay still in world space - in-place locomotion: moving back at speed_mps; clips
with a controller curve (motion): following it.  python -I slide_check.py <species> [clip,clip...]"""
import importlib
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)


def main():
    from anim import Quad, SkinSampler
    sp = importlib.import_module("species." + sys.argv[1])
    want = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    sk, parts = sp.build_cached()
    rig = Quad(sk)
    names = [b.name for b in sk.bones]
    # sampler on the bone heads only (the clips that need a skinned sample get a crude one)
    pts = np.array([b.head for b in sk.bones])
    jj = np.zeros((len(pts), 4), np.int32)
    jj[:, 0] = np.arange(len(pts))
    ww = np.zeros((len(pts), 4), np.float32)
    ww[:, 0] = 1
    sampler = SkinSampler(sk, pts, jj, ww, names, count=len(pts))
    clips = sp.clips(rig, sampler)
    feet = [(n, b, p) for n, b, p in sk.sockets if n.startswith("socket_foot_")]
    for c in clips:
        short = c["name"].split("__", 1)[1]
        if want and short not in want:
            continue
        baked = c["_baked"]
        N = c["frames"]
        mo = c.get("motion") or {}
        fwd = np.array(mo.get("forward_m", [0.0] * (N + 1)))
        side = np.array(mo.get("side_m", [0.0] * (N + 1)))
        yaw = np.array(mo.get("yaw", [0.0] * (N + 1)))
        spd = float(c.get("speed_mps", 0.0))
        P = {n: [] for n, _b, _p in feet}
        from qmath import q_rotate
        for f in range(N + 1):
            rot = {n: baked[n][0][f] for n in names}
            off = {n: baked[n][1][f] - sk.rest_offset(n) for n in names}
            pos, wrot = sk.fk(rot, off)
            for n, b, p in feet:
                P[n].append(pos[b] + q_rotate(wrot[b], p - sk.bone(b).head))
        worst, tot, cnt, low = 0.0, 0.0, 0, 0.0
        for n, arr in P.items():
            a = np.array(arr)
            low = min(low, float(a[:, 1].min()))
            cy, sy = np.cos(yaw), np.sin(yaw)
            wx = cy * a[:, 0] + sy * a[:, 2] + fwd + spd * np.arange(N + 1) / 30.0
            wz = -sy * a[:, 0] + cy * a[:, 2] + side
            pl = a[:, 1] < 0.02
            bad = []
            for f in range(N):
                if pl[f] and pl[f + 1]:
                    d = float(np.hypot(wx[f + 1] - wx[f], wz[f + 1] - wz[f]))
                    worst = max(worst, d)
                    tot += d
                    cnt += 1
                    if d > 0.005:
                        bad.append((f, round(d * 1000, 1)))
            if bad and os.environ.get("SLIDE_VERBOSE"):
                print("   ", short, n, bad[:12])
        print(f"{short:22s} planted {cnt:4d}  max {worst * 1000:7.2f} mm/f  mean {tot / max(cnt, 1) * 1000:6.3f}  "
              f"lowest {low:.3f}")


if __name__ == "__main__":
    main()
