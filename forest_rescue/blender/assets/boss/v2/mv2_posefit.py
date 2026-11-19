"""Fit the rig to every art/05 key pose: silhouette IoU + extremal landmarks (snout tip = leftmost, tail tip =
rightmost point, feet on the lowest row) at a fitted near-side camera (scale, offset, azimuth, elevation).

blender-python mv2_posefit.py <anim_blend>     -> cache/keypose_fit.json + qa v2_iterNN_keypose_fit.png
Pose vector: pelvis (pz, pitch, yaw, roll), spine (pitch, yaw), neck (pitch, yaw), head pitch, jaw, tail pitch/yaw
(base + linear curl along the chain), ball targets L/R (y, z), heel lift L/R, arm pitch.
"""
import json
import math
import os
import sys
import time

import bpy
import cv2
import numpy as np
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mv2_clips as CL  # noqa: E402
import mv2_common as C  # noqa: E402
import mv2_pose as PO  # noqa: E402
import mv2_refs as R  # noqa: E402
from frlib import core  # noqa: E402

ARM = C.ASSET_ID + "_rig"
PANELS = [("walk_contact_L", "lf_boss_walk", 0.0), ("walk_passing_1", "lf_boss_walk", 0.4),
          ("walk_contact_R", "lf_boss_walk", 0.8), ("walk_passing_2", "lf_boss_walk", 1.2),
          ("turn_anticipation", "lf_boss_turn_left", 0.25), ("turn_planted", "lf_boss_turn_left", 0.9),
          ("bite_windup", "lf_boss_jaw_arc", 2.2), ("bite_strike", "lf_boss_jaw_arc", 2.6),
          ("roar", "lf_boss_phase_roar", 1.3), ("tail_coil", "lf_boss_tail_sweep", 2.8),
          ("tail_release", "lf_boss_tail_sweep", 3.5), ("death_rest", "lf_boss_death", 5.2)]
NAMES = ["pz", "ppitch", "pyaw", "proll", "spitch", "syaw", "npitch", "nyaw", "hpitch", "jaw", "tp0", "tp1", "ty0",
         "ty1", "bLy", "bLz", "bRy", "bRz", "heel_L", "heel_R", "arm_pitch"]
LIMITS = {"pz": (-1.6, 0.3), "ppitch": (-25, 30), "pyaw": (-60, 60), "proll": (-85, 30), "spitch": (-30, 30),
          "syaw": (-45, 45), "npitch": (-50, 60), "nyaw": (-70, 70), "hpitch": (-35, 35), "jaw": (0, 42),
          "tp0": (-14, 14), "tp1": (-14, 14), "ty0": (-14, 14), "ty1": (-14, 14), "bLy": (-1.6, 1.6),
          "bLz": (0.17, 1.4), "bRy": (-1.6, 1.6), "bRz": (0.17, 1.4), "heel_L": (-10, 60), "heel_R": (-10, 60),
          "arm_pitch": (-60, 40)}


def channels_from(x, base):
    p = dict(base)
    v = dict(zip(NAMES, x))
    for k in ("pz", "ppitch", "pyaw", "proll", "spitch", "syaw", "npitch", "nyaw", "hpitch", "jaw", "arm_pitch",
              "heel_L", "heel_R"):
        p[k] = v[k]
    p["tail"] = [(v["ty0"] + v["ty1"] * i / 11.0, v["tp0"] + v["tp1"] * i / 11.0) for i in range(12)]
    p["ball_L"] = np.array([0.68, v["bLy"], v["bLz"]])
    p["ball_R"] = np.array([-0.68, v["bRy"], v["bRz"]])
    return p


def x_from(ch):
    t = ch.get("tail", [(0.0, 0.0)] * 12)
    ty = np.array([a for a, _ in t])
    tp = np.array([b for _, b in t])
    i = np.arange(12) / 11.0
    py1, py0 = np.polyfit(i, ty, 1)
    pp1, pp0 = np.polyfit(i, tp, 1)
    bl = np.asarray(ch["ball_L"], float)
    br = np.asarray(ch["ball_R"], float)
    v = {"pz": ch.get("pz", 0.0), "ppitch": ch.get("ppitch", 0.0), "pyaw": ch.get("pyaw", 0.0),
         "proll": ch.get("proll", 0.0), "spitch": ch.get("spitch", 0.0), "syaw": ch.get("syaw", 0.0),
         "npitch": ch.get("npitch", 0.0), "nyaw": ch.get("nyaw", 0.0), "hpitch": ch.get("hpitch", 0.0),
         "jaw": ch.get("jaw", 0.0), "tp0": pp0, "tp1": pp1, "ty0": py0, "ty1": py1, "bLy": bl[1],
         "bLz": max(bl[2], 0.17), "bRy": br[1], "bRz": max(br[2], 0.17), "heel_L": ch.get("heel_L", 0.0),
         "heel_R": ch.get("heel_R", 0.0), "arm_pitch": ch.get("arm_pitch", 0.0)}
    return np.array([v[n] for n in NAMES], float)


class Fitter:
    def __init__(self, arm, body):
        self.rig = CL.Rig(arm)
        lo = body.copy()
        lo.data = body.data.copy()
        bpy.context.scene.collection.objects.link(lo)
        for m in list(lo.modifiers):
            if m.type == "ARMATURE":
                lo.modifiers.remove(m)
        mod = lo.modifiers.new("dec", "DECIMATE")
        mod.ratio = 3200 / max(len(lo.data.polygons), 1)
        core.select_only([lo])
        bpy.ops.object.modifier_apply(modifier="dec")
        me = lo.data
        self.V = np.array([v.co[:] for v in me.vertices])
        me.calc_loop_triangles()
        self.T = np.array([t.vertices[:] for t in me.loop_triangles])
        names = self.rig.sk.names
        self.names = names
        W = np.zeros((len(self.V), len(names)))
        gidx = {g.index: g.name for g in lo.vertex_groups}
        for v in me.vertices:
            for g in v.groups:
                n = gidx[g.group]
                if n in names:
                    W[v.index, names.index(n)] = g.weight
        W /= np.maximum(W.sum(1, keepdims=True), 1e-9)
        self.W = W
        self.used = [j for j in range(len(names)) if W[:, j].max() > 0]
        self.inv = {n: np.linalg.inv(self.rig.sk.rest[n]) for n in names}
        self.Vh = np.concatenate([self.V, np.ones((len(self.V), 1))], 1)
        self.sub = {}
        for j in self.used:
            nz = np.nonzero(self.W[:, j] > 0)[0]
            self.sub[j] = (nz, self.Vh[nz], self.W[nz, j][:, None])

    def skin(self, ch):
        self.rig.build(ch)
        M = self.rig.ps.fk()
        out = np.zeros((len(self.V), 3))
        for j in self.used:
            nz, vh, w = self.sub[j]
            out[nz] += w * (vh @ (M[self.names[j]] @ self.inv[self.names[j]])[:3].T)
        snout = self.rig.ps.tail("head")
        tail = self.rig.ps.tail("tail_12")
        return out, snout, tail


def project(P, cam):
    s, tx, ty, az, el = cam
    Rz = PO.qmat((0, 0, 1), az)
    Rx = PO.qmat((0, 1, 0), el)       # tilt about the image-horizontal (Y) axis: camera slightly above
    Q = P @ (Rx @ Rz).T
    u = tx + s * Q[:, 1]
    v = ty - s * Q[:, 2]
    return u, v


def render_mask(F, Vp, cam, shape):
    u, v = project(Vp, cam)
    pts = np.stack([u, v], 1)[F.T]
    m = np.zeros(shape, np.uint8)
    cv2.fillPoly(m, np.round(pts * 4).astype(np.int32), 1, shift=2)
    return m > 0


def landmarks_ref(mask):
    ys, xs = np.nonzero(mask)
    H = mask.shape[0]
    top = ys < ys.min() + 0.65 * (ys.max() - ys.min())
    i = np.argmin(np.where(top, xs, 1e9))
    snout = np.array([xs[i], ys[i]], float)
    j = np.argmax(xs)
    tail = np.array([xs[j], ys[j]], float)
    return snout, tail, float(ys.max())


def fit_panel(fitter, panel, ch0, iters=650):
    img = R.keypose_panel(panel)
    mask = R.keypose_mask(img)
    H, W = mask.shape
    sn_ref, tl_ref, ground = landmarks_ref(mask)
    x0 = x_from(ch0)
    Vp, sn, tl = fitter.skin(channels_from(x0, ch0))
    # camera init from the bbox: model length vs mask length, feet on the lowest row
    ys, xs = np.nonzero(mask)
    s0 = (xs.max() - xs.min()) / max(Vp[:, 1].max() - Vp[:, 1].min(), 1e-3)
    tx0 = xs.min() - s0 * Vp[:, 1].min()
    ty0 = ground + s0 * Vp[:, 2].min()
    cam0 = np.array([math.log(s0), tx0, ty0, 0.0, 6.0])
    lo = np.array([LIMITS[n][0] for n in NAMES])
    hi = np.array([LIMITS[n][1] for n in NAMES])

    def unpack(z):
        x = np.clip(z[:len(NAMES)], lo, hi)
        c = z[len(NAMES):]
        cam = (math.exp(c[0]), c[1], c[2], c[3], c[4])
        return x, cam

    def loss(z, detail=False):
        x, cam = unpack(z)
        Vp, sn, tl = fitter.skin(channels_from(x, ch0))
        m = render_mask(fitter.T, Vp, cam, (H, W))
        iou = (m & mask).sum() / max((m | mask).sum(), 1)
        su, sv = project(np.array([sn, tl]), cam)
        lm = (np.hypot(su[0] - sn_ref[0], sv[0] - sn_ref[1]) + np.hypot(su[1] - tl_ref[0], sv[1] - tl_ref[1])) / H
        u, v = project(Vp, cam)
        ground_err = abs(v.max() - ground) / H
        reg = float((((x - x0) / (hi - lo + 1e-9)) ** 2).mean())
        f = (1 - iou) + 0.35 * lm + 0.5 * ground_err + 0.05 * reg + 0.0003 * abs(cam[3])
        return (f, iou, lm, m) if detail else f

    z0 = np.concatenate([x0, cam0])
    # stage 1: camera only, stage 2: everything
    def lc(c):
        return loss(np.concatenate([x0, c]))
    r1 = minimize(lc, cam0, method="Powell", options={"maxfev": 160, "xtol": 1e-3, "ftol": 1e-4})
    z1 = np.concatenate([x0, r1.x])
    r2 = minimize(loss, z1, method="Powell", options={"maxfev": iters, "xtol": 1e-3, "ftol": 1e-5})
    f, iou, lm, m = loss(r2.x, detail=True)
    x, cam = unpack(r2.x)
    f0, iou0, _l0, _m0 = loss(z1, detail=True)
    return {"panel": panel, "iou": float(iou), "iou_before": float(iou0), "landmark_err_frac": float(lm),
            "params": dict(zip(NAMES, map(float, x))), "camera": list(map(float, cam))}, mask, m, img


def main():
    t0 = time.time()
    args = sys.argv[1:]
    blend = [a for a in args if a.endswith(".blend")][0]
    only = None
    if "--panels" in args:
        only = [int(i) for i in args[args.index("--panels") + 1].split(",")]
    bpy.ops.wm.open_mainfile(filepath=blend)
    arm = bpy.data.objects[ARM]
    if arm.animation_data:
        arm.animation_data.action = None
    fitter = Fitter(arm, bpy.data.objects["maw_body"])
    out = {}
    tiles = []
    for pi, (panel, cid, t) in enumerate(PANELS):
        if only is not None and pi not in only:
            continue
        ch0 = CL.CLIPS[cid][2](t)
        res, mask, m, img = fit_panel(fitter, panel, ch0)
        res["clip"] = cid
        res["time"] = t
        out[panel] = res
        core.write_json(C.cache(f"keypose_fit_{panel}.json"), res)
        np.save(C.cache(f"keypose_fit_{panel}_mask.npy"), m)
        C.log(f"{panel}: IoU {res['iou_before']:.3f} -> {res['iou']:.3f} lm {res['landmark_err_frac']:.3f} "
              f"{time.time() - t0:.0f}s")
        ov = img.copy()
        ov[m & ~mask] = ov[m & ~mask] * 0.3 + np.array([0.15, 0.3, 0.9]) * 0.7
        ov[mask & ~m] = ov[mask & ~m] * 0.3 + np.array([0.85, 0.15, 0.15]) * 0.7
        ov[mask & m] = ov[mask & m] * 0.6 + np.array([0.15, 0.55, 0.15]) * 0.4
        h = 260
        a = cv2.resize(img, (int(img.shape[1] * h / img.shape[0]), h))
        b = cv2.resize(ov, (int(ov.shape[1] * h / ov.shape[0]), h))
        tile = (np.clip(np.concatenate([a, np.full((h, 4, 3), 0.1), b], 1), 0, 1) * 255).astype(np.uint8)
        from frlib import render
        tiles.append(render._label(tile, f"{panel}: pose IoU {res['iou']:.3f}"))
    if only is not None:
        print("POSEFIT_PART", json.dumps({k: round(v["iou"], 3) for k, v in out.items()}))
        return
    core.write_json(C.cache("keypose_fit.json"), out)
    w = max(t.shape[1] for t in tiles)
    tiles = [np.pad(t, ((0, 6), (0, w - t.shape[1]), (0, 0)), constant_values=25) for t in tiles]
    rows = [np.concatenate(tiles[i:i + 2], 1) if i + 1 < len(tiles) else tiles[i] for i in range(0, len(tiles), 2)]
    w = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 0), (0, w - r.shape[1]), (0, 0)), constant_values=25) for r in rows]
    core.save_rgba(C.qa("keypose_fit.png"), np.concatenate(rows, 0) / 255.0)
    print("POSEFIT", json.dumps({k: round(v["iou"], 3) for k, v in out.items()}))


if __name__ == "__main__":
    main()
