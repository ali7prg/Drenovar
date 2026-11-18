"""Animation smoothness on the exported GLB (independent of the authoring code): per clip and joint, the angular
speed between consecutive frames (deg / frame at 30 fps) and its change from frame to frame (the angular
acceleration); a frame where the acceleration jumps far above what the clip does elsewhere is a hitch the eye
sees as a jerk. Looping clips are also checked across the seam (last frame -> first frame). The body root
(Pelvis / hips) translation is checked the same way.

Usage: python3 -I smooth_check.py <glb> [out.json] [clip_manifest.json]   (the manifest gives the loop flags)
"""
import json
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from foot_check import load, acc  # noqa: E402

SKIP = ("socket_", "MotionRoot")


def qdist(a, b):
    """Angle (deg) between unit quaternions, rows of a and b."""
    d = np.abs(np.sum(a * b, 1)).clip(0, 1)
    return np.degrees(2 * np.arccos(d))


def main():
    js, binc = load(sys.argv[1])
    nodes = js["nodes"]
    man = json.load(open(sys.argv[3]))["clips"] if len(sys.argv) > 3 else None
    report = {}
    for anim in js["animations"]:
        name = anim["name"].split("__", 1)[-1]
        rows = []
        if man is not None and name in man:
            loop = bool(man[name].get("loop"))
        else:
            loop = name in ("idle", "walk", "run", "stalk", "trot", "swim", "fly", "rest") or name.endswith("_loop")
        for ch in anim["channels"]:
            node = nodes[ch["target"]["node"]].get("name", "")
            if node.startswith(SKIP):
                continue
            smp = anim["samplers"][ch["sampler"]]
            vals = acc(js, binc, smp["output"]).astype(float)
            if len(vals) < 4:
                continue
            path = ch["target"]["path"]
            if path == "rotation":
                q = vals / np.linalg.norm(vals, axis=1, keepdims=True)
                if loop and qdist(q[-1:], q[:1])[0] < 0.5:
                    q = q[:-1]                                     # frame N repeats frame 0
                seq = np.vstack([q, q[:1]]) if loop else q
                v = qdist(seq[1:], seq[:-1])                       # deg / frame
            elif path == "translation" and ("Pelvis" in node or "Hips" in node or "Root" in node):
                if loop and np.linalg.norm(vals[-1] - vals[0]) < 1e-4:
                    vals = vals[:-1]
                seq = np.vstack([vals, vals[:1]]) if loop else vals
                v = np.linalg.norm(seq[1:] - seq[:-1], axis=1) * 100.0   # cm / frame
            else:
                continue
            a = np.abs(np.diff(np.concatenate([v, v[:1]]))) if loop else np.abs(np.diff(v))   # speed change / frame
            if len(a) == 0:
                continue
            med = float(np.median(a)) + 1e-3
            k = int(np.argmax(a))
            rows.append({"node": node, "path": path, "max_speed": round(float(v.max()), 2),
                         "max_accel": round(float(a.max()), 2), "median_accel": round(med, 3),
                         "spike": round(float(a.max() / med), 1), "frame": k + 1,
                         "seam_accel": round(float(a[-1]), 2) if loop else None})
        rows.sort(key=lambda r: -r["max_accel"])
        report[name] = {"loop": loop, "worst": rows[:6],
                        "max_accel": rows[0]["max_accel"] if rows else 0.0}
    for name, r in report.items():
        w = r["worst"][0] if r["worst"] else {}
        print(f"{name:22s} max accel {r['max_accel']:7.2f} deg/f^2  worst {w.get('node', '-'):22s} f{w.get('frame', '-')}"
              f"  speed {w.get('max_speed', 0):6.2f}  seam {w.get('seam_accel')}")
    if len(sys.argv) > 2 and sys.argv[2] != "-":
        json.dump(report, open(sys.argv[2], "w"), indent=1)


if __name__ == "__main__":
    main()
