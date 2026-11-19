"""Key-pose fit v3 against art/05: free camera azimuth/elevation (3/4 panels), pelvis yaw/pitch/roll, spine twist,
neck yaw/roll, head yaw, quadratic per-bone tail yaw AND pitch (curl up and over in 3-D), leg IK targets on the
painted feet (x, y, z), hip drop; loss = (1 - IoU) + landmark error (snout, eye, jaw tip, tail tip, tail apex,
both feet; hand-picked on art/05) + ground contact.

blender-python mv2_posefit3.py --panels 0,1 <anim_blend>   -> cache/kp3_<panel>.json (+ _mask.npy)
"""
import json
import math
import os
import sys
import time

import bpy
import numpy as np
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mv2_clips as CL  # noqa: E402
import mv2_common as C  # noqa: E402
import mv2_pose as PO  # noqa: E402
import mv2_posefit as F1  # noqa: E402
import mv2_refs as R  # noqa: E402
from frlib import core  # noqa: E402

# hand-picked art/05 landmarks (full-sheet pixels): snout tip, eye, jaw tip, tail tip, tail apex, feet (toe tips)
LM = {
    "walk_contact_L": {"snout": (16, 137.5), "eye": (50, 122.5), "tail": (374, 167.5), "feet": [(90, 262.5), (257.5, 257.5)]},
    "walk_passing_1": {"snout": (392.5, 135), "eye": (425, 120), "tail": (747.5, 170), "feet": [(517.5, 247.5), (575, 259)]},
    "walk_contact_R": {"snout": (765, 147.5), "eye": (800, 122.5), "tail": (1127.5, 170), "feet": [(835, 259), (980, 259)]},
    "walk_passing_2": {"snout": (1146, 135), "eye": (1177.5, 117.5), "tail": (1522.5, 167.5), "feet": [(1282.5, 261), (1357.5, 235)]},
    "turn_anticipation": {"snout": (22.5, 415), "eye": (65, 390), "tail": (377.5, 467.5), "feet": [(65, 582.5), (270, 585)]},
    "turn_planted": {"snout": (557.5, 400), "eye": (515, 380), "tail": (732.5, 505), "feet": [(425, 582.5), (645, 585)]},
    "bite_windup": {"snout": (782.5, 355), "jaw": (775, 387.5), "eye": (830, 362.5), "tail": (1104, 517.5),
                    "feet": [(795, 585), (1020, 587.5)]},
    "bite_strike": {"snout": (1132.5, 400), "jaw": (1137.5, 457.5), "eye": (1185, 397.5), "tail": (1522.5, 487.5),
                    "feet": [(1205, 585), (1460, 585)]},
    "roar": {"snout": (39, 677.5), "jaw": (37.5, 732.5), "eye": (87.5, 685), "tail": (367.5, 837.5),
             "feet": [(47.5, 922.5), (295, 922.5)]},
    "tail_coil": {"snout": (552.5, 800), "eye": (505, 775), "tail": (697.5, 767.5), "apex": (575, 710),
                  "feet": [(400, 917.5), (625, 920)]},
    "tail_release": {"snout": (851, 737.5), "eye": (817.5, 727.5), "tail": (1100, 807.5), "feet": [(740, 915), (950, 920)]},
    "death_rest": {"snout": (1125, 902.5), "eye": (1157.5, 875), "tail": (1372.5, 930)},
}
NAMES = ["pz", "ppitch", "pyaw", "proll", "spitch", "syaw", "sroll", "npitch", "nyaw", "nroll", "hpitch", "hyaw", "jaw",
         "tp0", "tp1", "tp2", "ty0", "ty1", "ty2", "fLx", "fLy", "fLz", "fRx", "fRy", "fRz", "heel_L", "heel_R",
         "arm_pitch"]
LIM = {"pz": (-0.75, 0.2), "ppitch": (-25, 35), "pyaw": (-70, 70), "proll": (-30, 30), "spitch": (-30, 35),
       "syaw": (-50, 50), "sroll": (-30, 30), "npitch": (-50, 65), "nyaw": (-75, 75), "nroll": (-35, 35),
       "hpitch": (-35, 40), "hyaw": (-40, 40), "jaw": (0, 42), "tp0": (-14, 16), "tp1": (-20, 24), "tp2": (-20, 24),
       "ty0": (-16, 16), "ty1": (-24, 24), "ty2": (-24, 24), "fLx": (0.2, 1.6), "fLy": (-1.9, 1.9), "fLz": (0.17, 1.4),
       "fRx": (-1.6, -0.2), "fRy": (-1.9, 1.9), "fRz": (0.17, 1.4), "heel_L": (-10, 60), "heel_R": (-10, 60),
       "arm_pitch": (-60, 40)}
SNOUT = np.array([0.0, -4.555, 2.93])
JAWTIP = np.array([0.0, -4.48, 2.66])
EYES = [np.array([0.40, -3.63, 3.285]), np.array([-0.40, -3.63, 3.285])]


def channels(x, base):
    v = dict(zip(NAMES, x))
    p = dict(base)
    for k in ("pz", "ppitch", "pyaw", "proll", "spitch", "syaw", "sroll", "npitch", "nyaw", "nroll", "hpitch", "hyaw",
              "jaw", "heel_L", "heel_R", "arm_pitch"):
        p[k] = v[k]
    t = np.arange(12) / 11.0
    p["tail"] = [(v["ty0"] + v["ty1"] * ti + v["ty2"] * ti * ti, v["tp0"] + v["tp1"] * ti + v["tp2"] * ti * ti)
                 for ti in t]
    p["ball_L"] = np.array([v["fLx"], v["fLy"], v["fLz"]])
    p["ball_R"] = np.array([v["fRx"], v["fRy"], v["fRz"]])
    return p


def x_init(ch):
    t = ch.get("tail", [(0.0, 0.0)] * 12)
    i = np.arange(12) / 11.0
    ty = np.polyfit(i, [a for a, _ in t], 2)
    tp = np.polyfit(i, [b for _, b in t], 2)
    bl, br = np.asarray(ch["ball_L"], float), np.asarray(ch["ball_R"], float)
    v = {k: ch.get(k, 0.0) for k in NAMES}
    v.update({"tp0": tp[2], "tp1": tp[1], "tp2": tp[0], "ty0": ty[2], "ty1": ty[1], "ty2": ty[0],
              "fLx": bl[0], "fLy": bl[1], "fLz": max(bl[2], 0.17), "fRx": br[0], "fRy": br[1], "fRz": max(br[2], 0.17)})
    return np.array([np.clip(v[n], *LIM[n]) for n in NAMES], float)


def model_points(fit, ch):
    """Skinned verts + landmark points (snout, jaw tip, eyes, tail tip, tail apex candidates, feet toe tips)."""
    Vp, _sn, tl = fit.skin(ch)
    ps = fit.rig.ps
    M = ps.fk()

    def bone_pt(bone, p):
        Mi = M[bone] @ np.linalg.inv(fit.rig.sk.rest[bone])
        return (Mi @ np.append(p, 1.0))[:3]
    lm = {"snout": bone_pt("head", SNOUT), "jaw": bone_pt("jaw", JAWTIP),
          "eyes": [bone_pt("head", e) for e in EYES], "tail": ps.tail("tail_12"),
          "tailpts": [ps.tail(f"tail_{i:02d}") for i in range(4, 12)],
          "feet": [ps.tail("toe3b_L"), ps.tail("toe3b_R")]}
    return Vp, lm


def fit_panel(fit, panel, ch0, iters=1300):
    img = R.keypose_panel(panel)
    mask = R.keypose_mask(img)
    H, W = mask.shape
    x0p, y0p = R.KEYPOSE_PANELS[panel][:2]
    L = {k: (np.array(v, float) - (x0p, y0p)) if k != "feet" else [np.array(f, float) - (x0p, y0p) for f in v]
         for k, v in LM[panel].items()}
    ys, xs = np.nonzero(mask)
    ground = float(ys.max())
    xinit = x_init(ch0)
    lo = np.array([LIM[n][0] for n in NAMES])
    hi = np.array([LIM[n][1] for n in NAMES])

    def lm_err(lm, cam):
        errs = []

        def pr(p):
            u, v = F1.project(np.asarray(p)[None], cam)
            return np.array([u[0], v[0]])
        errs.append(np.linalg.norm(pr(lm["snout"]) - L["snout"]))
        errs.append(np.linalg.norm(pr(lm["tail"]) - L["tail"]))
        if "eye" in L:
            errs.append(min(np.linalg.norm(pr(e) - L["eye"]) for e in lm["eyes"]))
        if "jaw" in L:
            errs.append(np.linalg.norm(pr(lm["jaw"]) - L["jaw"]))
        if "apex" in L:
            errs.append(min(np.linalg.norm(pr(p) - L["apex"]) for p in lm["tailpts"]))
        if "feet" in L:
            a, b = pr(lm["feet"][0]), pr(lm["feet"][1])
            f0, f1 = L["feet"]
            errs.append(min(np.linalg.norm(a - f0) + np.linalg.norm(b - f1), np.linalg.norm(a - f1) + np.linalg.norm(b - f0)) / 2)
        return float(np.mean(errs)) / H

    # camera init: grid over azimuth/elevation, least-squares scale/offset on the landmarks
    Vp, lm = model_points(fit, channels(xinit, ch0))
    best = None
    for az in range(-90, 91, 15):
        for el in (0, 10, 20, 30):
            src, dst = [], []
            for k in ("snout", "tail"):
                src.append(lm[k])
                dst.append(L[k])
            if "feet" in L:
                src += lm["feet"]
                dst += L["feet"]
            Rz = PO.qmat((0, 0, 1), az)
            Ry = PO.qmat((0, 1, 0), el)
            Q = np.array(src) @ (Ry @ Rz).T
            A = []
            bb = []
            for q, d in zip(Q, dst):
                A.append([q[1], 1, 0])
                bb.append(d[0])
                A.append([-q[2], 0, 1])
                bb.append(d[1])
            sol, *_ = np.linalg.lstsq(np.array(A), np.array(bb), rcond=None)
            s, tx, ty = sol
            if s <= 1:
                continue
            res = float(np.linalg.norm(np.array(A) @ sol - bb))
            if best is None or res < best[0]:
                best = (res, np.array([math.log(s), tx, ty, float(az), float(el)]))
    cam0 = best[1]

    def unpack(z):
        x = np.clip(z[:len(NAMES)], lo, hi)
        c = z[len(NAMES):]
        return x, (math.exp(c[0]), c[1], c[2], c[3], c[4])

    def loss(z, detail=False):
        x, cam = unpack(z)
        ch = channels(x, ch0)
        Vp, lm = model_points(fit, ch)
        m = F1.render_mask(fit.T, Vp, cam, (H, W))
        iou = (m & mask).sum() / max((m | mask).sum(), 1)
        le = lm_err(lm, cam)
        u, v = F1.project(Vp, cam)
        g = abs(v.max() - ground) / H
        reg = float((((x - xinit) / (hi - lo)) ** 2).mean())
        f = (1 - iou) + 1.6 * le + 0.6 * g + 0.04 * reg
        return (f, iou, le, m) if detail else f

    z0 = np.concatenate([xinit, cam0])
    r = minimize(loss, z0, method="Powell", options={"maxfev": iters, "xtol": 1e-3, "ftol": 1e-5})
    f, iou, le, m = loss(r.x, detail=True)
    f_0, iou0, _l, _m = loss(z0, detail=True)
    x, cam = unpack(r.x)
    return {"panel": panel, "iou": float(iou), "iou_init": float(iou0), "landmark_err_frac": float(le),
            "params": dict(zip(NAMES, map(float, x))), "camera": list(map(float, cam))}, m


def main():
    t0 = time.time()
    args = sys.argv[1:]
    blend = [a for a in args if a.endswith(".blend")][0]
    only = [int(i) for i in args[args.index("--panels") + 1].split(",")]
    bpy.ops.wm.open_mainfile(filepath=blend)
    arm = bpy.data.objects[F1.ARM]
    if arm.animation_data:
        arm.animation_data.action = None
    CL.load_keypose_fit(C.cache("keypose_fit.json"))
    fit = F1.Fitter(arm, bpy.data.objects["maw_body"])
    for pi, (panel, cid, t) in enumerate(F1.PANELS):
        if pi not in only:
            continue
        ch0 = CL.with_overrides(cid, CL.CLIPS[cid][2])(t)
        res, m = fit_panel(fit, panel, ch0)
        res.update({"clip": cid, "time": t})
        core.write_json(C.cache(f"kp3_{panel}.json"), res)
        np.save(C.cache(f"kp3_{panel}_mask.npy"), m)
        C.log(f"{panel}: IoU {res['iou_init']:.3f} -> {res['iou']:.3f} lm {res['landmark_err_frac']:.3f} "
              f"cam az {res['camera'][3]:.0f} el {res['camera'][4]:.0f} {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
