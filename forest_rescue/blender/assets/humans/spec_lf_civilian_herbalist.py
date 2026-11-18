"""HERBALIST — woman ~45, wavy brown hair framing the face under a raised emerald wool hood;
hooded capelet (gold trim at the hem) closed by a round bronze brooch at the throat, long
side panels hanging outside the arms; long brown dress with wide sleeves over light linen
under-sleeves; rope belt knotted at the front with hanging ends; canvas herb pouch with
lavender/yellow sprigs at the right hip.  Sheet: civilian_survivors (cell 2)."""
import math

import numpy as np

from frlib import sdf as fsdf

import humans_cloth as C
import humans_geo as G
import humans_kit as K
import humans_sdf as H

ASSET = "lf_civilian_herbalist"
GROUP = "civilian"
CLASS_GROUP = {"cloak": "garment", "hood": "garment"}
BUDGET = {"head": 2300, "hood": 1500, "hood_down": 500}
FACE_PAINT = {"lip_tint": (1.06, 0.88, 0.86)}
OPTIONAL_COLORS = {"hair": (0.30, 0.20, 0.13), "cloak": (0.22, 0.30, 0.20)}
DRAPE_EXTRA = ("dress",)

L = dict(
    crown=1.660, top=1.72, eye=1.566, mouth=1.495, chin=1.455, neck=1.408,
    shoulder_l=(0.168, 1.360), shoulder_r=(-0.168, 1.360),
    elbow_l=(0.255, 1.105), elbow_r=(-0.255, 1.105),
    wrist_l=(0.268, 0.915), wrist_r=(-0.270, 0.915),
    hip_l=(0.090, 0.860), hip_r=(-0.090, 0.860),
    knee_l=(0.098, 0.450), knee_r=(-0.098, 0.450),
    ankle_l=(0.105, 0.075), ankle_r=(-0.108, 0.075),
    hand_len=0.084, hand_scale=0.92, foot_len=0.24, toe_out_deg=8.0, female=True,
)
FACE = dict(female=True, width=0.97, jaw=0.92, chin=0.95, cheek=1.1, brow=0.7, nose_len=1.02, nose_w=0.9,
            nose_proj=1.0, lips=1.0, mouth_w=1.0, skull=0.96, eye_sep=1.0)
NECK_R = (0.050, 0.044)
BONE_GARMENTS = dict(waist_z=1.12, skirt_hem_z=0.14, front_y=-0.16, back_y=0.16, side_x=0.20,
                     cape_top_z=1.38, cape_hem_z=1.10, bag=((-0.17, -0.06, 1.05), (-0.17, -0.07, 0.85)))


def body_parts(J, L):
    P = []
    P.append(K.torso([
        (0.95, 0.170, (0.115, 0.125), 2.2), (1.04, 0.150, (0.110, 0.110), 2.3), (1.13, 0.140, (0.105, 0.100), 2.3),
        (1.22, 0.152, (0.110, 0.100), 2.4), (1.30, 0.165, (0.112, 0.100), 2.5), (1.35, 0.160, (0.100, 0.095), 2.5),
        (1.385, 0.120, (0.080, 0.078), 2.3), (1.415, 0.065, (0.055, 0.052), 2.0)], cls="dress"))
    # long dress skirt: waist -> hem (front view half-width 0.29 at the hem), soft folds
    sk = [(0.10, 0.300, (0.215, 0.235), 2.1), (0.30, 0.265, (0.190, 0.210), 2.1), (0.55, 0.225, (0.165, 0.180), 2.1),
          (0.80, 0.190, (0.140, 0.150), 2.2), (1.00, 0.165, (0.120, 0.128), 2.2), (1.14, 0.142, (0.105, 0.104), 2.3)]
    P.append(K.torso(sk, cls="dress", name="dress", disp=K.folds_disp(0.006, (14.0, 11.0), seed=2, zband=(0.10, 1.0))))
    for S_, sx in (("Left", 1), ("Right", -1)):
        P += K.shoulders(J, S_, sx, r=(0.060, 0.058, 0.064), cls="dress", off=0.010)
        # wide dress sleeve to mid-forearm over a tight linen under-sleeve
        P.append(K.upper_arm(J, S_, [(0.0, 0.058), (0.5, 0.054), (1.0, 0.052)], cls="dress"))
        P.append(H.limb(J[f"{S_}LowerArm"], J[f"{S_}Hand"], [(0.0, 0.054), (0.30, 0.058), (0.42, 0.060), (0.46, 0.040),
                                                           (0.75, 0.034), (1.0, 0.030)], cls="dress",
                        bone=f"{S_}LowerArm", k=0.012, name=f"forearm_{S_}"))
        P.append(K.forearm_cuff(J, S_, 0.40, 0.050, 0.012, cls="dress"))
        # hidden legs (only the feet show under the hem) + low shoes
        P.append(K.thigh(J, S_, [(0.0, 0.080), (1.0, 0.055)], cls="dress"))
        P.append(K.shin(J, S_, [(0.0, 0.052), (0.7, 0.045), (1.0, 0.034)], cls="dress"))
        P += K.boot(J, S_, sx, L, top_z=0.115, cls="boot", shaft_r=(0.046, 0.042), width=0.95, height=0.95,
                    round_toe=1.1)
    return P


def class_regions(ctx, cent, cls):
    """Linen under-sleeves between the dress sleeve and the wrist."""
    out = list(cls)
    for i, c in enumerate(out):
        if c != "dress":
            continue
        p = cent[i]
        for S_ in ("Left", "Right"):
            el, wr = ctx.J[f"{S_}LowerArm"], ctx.J[f"{S_}Hand"]
            ax = wr - el
            t = np.dot(p - el, ax) / np.dot(ax, ax)
            if 0.45 < t < 1.05 and np.linalg.norm(p - (el + ax * t)) < 0.06:
                out[i] = "linen"
    return out


def head_extras(ctx):
    lm = ctx.lm
    reg = G.hair_region(lm, front=0.060, temple_drop=0.15, side=-0.020, back=-0.080)
    hair = K.hair_shell(ctx, thick=0.012, region=reg)
    # wavy locks framing the face down to the shoulders (visible inside the hood opening)
    locks = []
    for sx in (1, -1):
        for k, dx in enumerate((0.0, 0.012, 0.022)):
            locks.append([(sx * (0.064 + dx), 0.010 + 0.01 * k, 0.040), (sx * (0.070 + dx), 0.018 + 0.01 * k, -0.020),
                          (sx * (0.066 + dx), 0.028 + 0.01 * k, -0.080), (sx * (0.070 + dx), 0.040 + 0.01 * k, -0.140),
                          (sx * (0.082 + dx), 0.050 + 0.01 * k, -0.190)])
    return [hair] + K.strands(ctx, locks, r0=0.010, r1=0.006)


def garments(ctx):
    J, L = ctx.J, ctx.L
    cxy = ctx.center
    lm = ctx.lm
    s = lm["scale"]
    out = []

    def axis_center(c):
        return np.array([cxy[0], cxy[1], c[2]])

    # ---- hood (raised): shell around the head with a face opening, merges into the capelet
    O = lm["origin"]

    def hood_outer(P):
        Q = (np.asarray(P, float) - O) / s
        head = ctx.head_fn(P) - (0.040 + 0.020 * np.clip((Q[..., 1] - 0.05) / 0.12, 0, 1)
                                 + 0.010 * np.clip((Q[..., 2] - 0.05) / 0.07, 0, 1)) * s
        # neck drape: the hood falls onto the shoulders around the neck
        neck = fsdf.round_cone(O + np.array([0, 0.10, -0.08]) * s, O + np.array([0, 0.10, -0.205]) * s,
                               0.085 * s, 0.13 * s).fn(P)
        return np.minimum(head, neck) if False else fsdf.smin(head, neck, 0.04)

    def hood_inner(P):
        Q = (np.asarray(P, float) - O) / s
        inner = ctx.head_fn(P) - 0.028 * s
        inner = fsdf.smin(inner, fsdf.round_cone(O + np.array([0, 0.10, -0.08]) * s,
                                                 O + np.array([0, 0.10, -0.215]) * s, 0.070 * s, 0.115 * s).fn(P), 0.03)
        # face opening (front) and the bottom (open toward the shoulders)
        opening = np.maximum(np.maximum(np.abs(Q[..., 0]) - 0.078 + 0.12 * np.maximum(-0.02 - Q[..., 2], 0),
                                        Q[..., 1] - 0.010), np.maximum(Q[..., 2] - 0.082, -0.125 - Q[..., 2])) * s
        bottom = (-0.20 - Q[..., 2]) * s
        return fsdf.smin(np.minimum(inner, opening), bottom, 0.01)
    lo = O + np.array([-0.17, -0.10, -0.25]) * s
    hi = O + np.array([0.17, 0.26, 0.17]) * s
    hood = K.headwear_piece("hood", ctx, hood_outer, hood_inner, lo, hi, "cloak",
                            {"type": "hood", "pivot_z": J["Head"][2], "lag": 0.25}, voxel=0.0028)
    hood.meta["optional"] = "hood_up"
    hood.meta["default_on"] = True
    out.append(hood)
    # ---- capelet: shoulders to z~1.12, open in front below the brooch
    def cap_top(th):
        return 1.425 + 0.02 * np.cos(th) * 0
    def cap_hem(th):
        a = np.abs(th)
        return 1.115 + 0.03 * np.clip((math.pi - a) / math.pi, 0, 1) ** 2 - 0.0 * a

    def cap_region(th, z):
        # V opening in front below the brooch at z~1.40
        a = np.abs(th)
        return a > (0.16 + 0.9 * np.clip((1.40 - z) / 0.28, 0, 1) ** 1.2)
    D = C.drape(ctx.body_fn, cxy, (-math.pi, math.pi), cap_top, cap_hem, nu=48, nv=14, clearance=0.020, slack=0.30,
                closed=True, flare=0.10, folds=[(10, 0.006, 0.2), (17, 0.003, 1.0)], ragged=0.004, seed=4,
                region=cap_region, part="capelet")
    out.append(G.piece_from_drape("capelet", D, "cloak", 0.005,
                                  {"type": "cape", "top_z": 1.42, "hem_z": 1.10, "side": False}, axis_center))
    # ---- long side panels outside the arms (front view: down to z~0.45 left / 0.58 right)
    for sx, hem in ((1, 0.58), (-1, 0.45)):
        th0 = sx * 1.05
        th1 = sx * 2.05
        D = C.drape(ctx.body_fn, cxy, (min(th0, th1), max(th0, th1)), lambda th: np.full_like(th, 1.36),
                    lambda th, hem=hem: np.full_like(th, hem), nu=8, nv=18, clearance=0.024, slack=0.05, flare=0.02,
                    folds=[(14, 0.006, 0.5)], ragged=0.008, seed=7 + sx, part="panel",
                    fit=(ctx.hull_fn, hem + 0.02, 1.20, sx, 0.25))
        out.append(G.piece_from_drape(f"cloak_panel_{sx}", D, "cloak", 0.005,
                                      {"type": "cape", "top_z": 1.36, "hem_z": hem, "side": True}, axis_center))
    # ---- brooch
    bp = C.surface_point(ctx.body_fn, np.array([0.0, 0.0, 1.400]), np.array([0, -1.0, 0]), clearance=0.026)
    out.append(G.lathe_piece("brooch", [(0.0, 0.0), (0.018, 0.0), (0.020, 0.004), (0.014, 0.008), (0.0, 0.008)],
                             bp, (0, -1.0, 0), "brass", {"type": "rigid", "bone": "UpperChest"}, sides=14))
    # ---- rope belt (two turns), knot at front-left and two hanging ends
    th = np.linspace(-math.pi, math.pi, 44, endpoint=False)
    for k, dz in enumerate((0.0, 0.016)):
        P_, N_ = G.curve_on_body(ctx.torso_fn, cxy, th, np.full_like(th, 1.122 + dz + 0.004 * np.cos(th)), clearance=0.008)
        out.append(G.tube_piece(f"rope_belt_{k}", np.vstack([P_, P_[:1]]), 0.0065, "rope", {"type": "body"}, sides=6,
                                closed=False, caps=False))
    kn = C.surface_point(ctx.torso_fn, np.array([0.05, 0.0, 1.125]), np.array([0, -1.0, 0]), clearance=0.016)
    out.append(G.box_piece("rope_knot", kn, (0.030, 0.022, 0.026), None, "rope", {"type": "body"}, bevel=0.9))
    for dx, zend in ((0.0, 0.93), (0.07, 0.96)):
        pts = np.array([kn + np.array([dx * 0.3, -0.004, -0.01]), kn + np.array([dx * 0.7, -0.012, -0.08]),
                        kn + np.array([dx, -0.020, -(1.125 - zend) * 0.6]), kn + np.array([dx, -0.020, -(1.125 - zend)])])
        out.append(G.tube_piece(f"rope_end_{dx}", pts, 0.0055, "rope", {"type": "skirt", "top_z": 1.12,
                                                                             "hem_z": 0.9, "follow": 0.2}, sides=6))
    # ---- herb pouch (right hip) with sprigs
    top = C.surface_point(ctx.torso_fn, np.array([-0.135, 0.0, 0.97]), np.array([-0.35, -1.0, 0]), clearance=0.02)
    Rm = G.rot_from((0.9, -0.3, 0.1), (-0.3, -0.9, 0.0))
    out.append(G.box_piece("herb_pouch", top + np.array([-0.01, -0.02, -0.060]), (0.095, 0.050, 0.120), Rm, "canvas",
                           {"type": "rigid", "bone": "Bag"}, bevel=0.6, segs=2))
    rng = np.random.default_rng(3)
    sprigs = []
    for k in range(9):
        base = top + np.array([rng.uniform(-0.035, 0.03), rng.uniform(-0.02, 0.0), 0.0])
        tipv = base + np.array([rng.uniform(-0.05, 0.06), rng.uniform(-0.05, -0.01), rng.uniform(0.07, 0.14)])
        mid = (base + tipv) / 2 + np.array([0, -0.01, 0])
        sprigs.append(G.tube_piece(f"sprig{k}", np.array([base, mid, tipv]), 0.0028, "herbs",
                                   {"type": "rigid", "bone": "Bag"}, sides=4))
        cls = "flower_purple" if k % 3 else "flower_yellow"
        sprigs.append(G.box_piece(f"bloom{k}", tipv + np.array([0, 0, 0.012]), (0.012, 0.012, 0.030), None, cls,
                                  {"type": "rigid", "bone": "Bag"}, bevel=0.9))
    out.append(G.merge_pieces("herbs", sprigs, cls="herbs", rule={"type": "rigid", "bone": "Bag"}))
    return out


def optional_parts(ctx):
    """Captive variants: hood lowered onto the shoulders (hair then visible)."""
    lm = ctx.lm
    s = lm["scale"]
    O = lm["origin"]
    c = O + np.array([0, 0.15, -0.22]) * s

    def outer(P):
        return fsdf.round_cone(c, c + np.array([0, 0.05, -0.10]), 0.11 * s, 0.09 * s).fn(P)

    def inner(P):
        return fsdf.round_cone(c + np.array([0, -0.01, 0.01]), c + np.array([0, 0.04, -0.09]), 0.098 * s, 0.078 * s).fn(P)
    p = K.headwear_piece("hood_down", ctx, outer, inner, c - 0.2, c + 0.2, "cloak",
                         {"type": "blend", "bones": {"UpperChest": 0.6, "Hood": 0.4}})
    p.meta["optional"] = "hood_down"
    p.meta["default_on"] = False
    return [p]
