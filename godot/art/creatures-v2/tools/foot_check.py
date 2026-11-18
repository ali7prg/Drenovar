"""Foot sliding and ground contact check on the exported GLB (independent of the authoring code).

Reads nodes, rest TRS and animation samples from the GLB, runs FK per frame and follows the four
foot sockets (socket_foot_*). A foot counts as planted while it is within 2 cm of the ground. For
in-place locomotion the planted foot must move backwards at the clip's speed_mps (the controller
carries the body forward); for clips with a controller motion curve (charge, pounce, dodge, turn)
the planted foot must stand still in world space; otherwise it must stand still in model space.
Usage: python3 -I foot_check.py <glb> <clip_manifest.json> [out.json]
"""
import json
import struct
import sys

import numpy as np


def load(path):
    b = open(path, "rb").read()
    _m, _v, length = struct.unpack_from("<III", b, 0)
    off, js, binc = 12, None, None
    while off < length:
        clen, ctype = struct.unpack_from("<II", b, off)
        off += 8
        chunk = b[off:off + clen]
        off += clen
        if ctype == 0x4E4F534A:
            js = json.loads(chunk)
        elif ctype == 0x004E4942:
            binc = chunk
    return js, binc


def acc(js, binc, i):
    a = js["accessors"][i]
    bv = js["bufferViews"][a["bufferView"]]
    n = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[a["type"]]
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    return np.frombuffer(binc, dtype=np.float32, count=a["count"] * n, offset=start).reshape(a["count"], n)


def qmat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def main():
    js, binc = load(sys.argv[1])
    man = json.load(open(sys.argv[2]))
    nodes = js["nodes"]
    parent = {}
    for i, n in enumerate(nodes):
        for c in n.get("children", []):
            parent[c] = i
    feet = {n["name"]: i for i, n in enumerate(nodes) if n.get("name", "").startswith("socket_foot_")}
    order = []
    seen = set()

    def visit(i):
        if i in seen:
            return
        if i in parent:
            visit(parent[i])
        seen.add(i)
        order.append(i)
    for i in range(len(nodes)):
        visit(i)
    report = {}
    for anim in js["animations"]:
        short = anim["name"].split("__", 1)[1]
        row = man["clips"][short]
        frames = row["frames"]
        T = {i: np.tile(np.array(nodes[i].get("translation", [0, 0, 0]), float), (frames + 1, 1)) for i in range(len(nodes))}
        R = {i: np.tile(np.array(nodes[i].get("rotation", [0, 0, 0, 1]), float), (frames + 1, 1)) for i in range(len(nodes))}
        for ch in anim["channels"]:
            smp = anim["samplers"][ch["sampler"]]
            vals = acc(js, binc, smp["output"]).astype(float)
            tgt = ch["target"]
            (T if tgt["path"] == "translation" else R)[tgt["node"]] = vals[:frames + 1]
        pos = {}
        for f in range(frames + 1):
            W = {}
            for i in order:
                M = np.eye(4)
                M[:3, :3] = qmat(R[i][f])
                M[:3, 3] = T[i][f]
                W[i] = W[parent[i]] @ M if i in parent else M
            for name, i in feet.items():
                pos.setdefault(name, []).append(W[i][:3, 3].copy())
        motion = row.get("motion", {})
        fwd = np.array(motion.get("forward_m", [0.0] * (frames + 1)), float)
        side = np.array(motion.get("side_m", [0.0] * (frames + 1)), float)
        yaw = np.array(motion.get("yaw", [0.0] * (frames + 1)), float)
        speed = float(row.get("speed_mps", 0.0))
        worst, lowest = 0.0, 0.0
        slide_sum, planted_frames = 0.0, 0
        for name, P in pos.items():
            P = np.array(P)
            lowest = min(lowest, float(P[:, 1].min()))
            # world position under the controller (forward, side, yaw), in-place locomotion slides back at speed
            c, s = np.cos(yaw), np.sin(yaw)
            Wx = c * P[:, 0] + s * P[:, 2] + fwd
            Wz = -s * P[:, 0] + c * P[:, 2] + side
            Wx = Wx + speed * np.arange(frames + 1) / 30.0
            planted = P[:, 1] < 0.02
            for f in range(frames):
                if planted[f] and planted[f + 1]:
                    d = float(np.hypot(Wx[f + 1] - Wx[f], Wz[f + 1] - Wz[f]))
                    slide_sum += d
                    planted_frames += 1
                    worst = max(worst, d)
        report[short] = {"frames": frames, "loop": row["loop"], "planted_steps": planted_frames,
                         "max_slide_mm_per_frame": round(worst * 1000, 2),
                         "mean_slide_mm_per_frame": round(slide_sum / max(1, planted_frames) * 1000, 3),
                         "lowest_foot_m": round(lowest, 3)}
    out = {"glb": sys.argv[1].split("/")[-1], "clips": report}
    if len(sys.argv) > 3:
        json.dump(out, open(sys.argv[3], "w"), indent=1)
    for k, v in report.items():
        print(f"{k:22s} planted {v['planted_steps']:4d}  max {v['max_slide_mm_per_frame']:7.2f} mm/f  mean {v['mean_slide_mm_per_frame']:6.3f}  lowest {v['lowest_foot_m']:.3f}")


if __name__ == "__main__":
    main()
