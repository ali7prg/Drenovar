"""SCOUT — lean man ~30, dark tousled hair, light stubble; olive-green hood lowered as a cowl
around the neck; brown leather jerkin with short sleeves over a linen shirt with rolled sleeves,
laced chest, diagonal strap from the right shoulder, bronze tree emblem on the left chest; two
belts (buckle front), dagger on the right hip, quiver with fletched arrows on the LEFT hip; dark
brown trousers, soft boots with turned cuffs.  Bow: slung on the back (default) and an in-hand
copy on LeftProp for shooting.  Sheet: 04_expedition_squad_turnaround (figures 3-4)."""
import math

import numpy as np

from frlib import sdf as fsdf

import humans_cloth as C
import humans_geo as G
import humans_kit as K
import humans_props as PR
import humans_sdf as H

ASSET = "lf_squad_scout"
GROUP = "soldier"
ROLE = "scout"
CLASS_GROUP = {"hood": "garment"}
BUDGET = {"head": 2500, "hood_down": 700}
FACE_PAINT = {"lip_tint": (1.03, 0.9, 0.88), "stubble": 0.18}

L = dict(
    crown=1.830, top=1.87, eye=1.720, mouth=1.646, chin=1.605, neck=1.548,
    shoulder_l=(0.188, 1.475), shoulder_r=(-0.188, 1.475),
    elbow_l=(0.280, 1.195), elbow_r=(-0.280, 1.195),
    wrist_l=(0.330, 0.955), wrist_r=(-0.330, 0.955),
    hip_l=(0.092, 0.930), hip_r=(-0.092, 0.930),
    knee_l=(0.100, 0.500), knee_r=(-0.100, 0.500),
    ankle_l=(0.122, 0.085), ankle_r=(-0.122, 0.085),
    hand_len=0.094, hand_scale=1.04, foot_len=0.27, toe_out_deg=7.0, female=False,
)
FACE = dict(width=0.95, jaw=1.0, chin=1.08, cheek=1.2, brow=1.1, nose_len=1.08, nose_w=0.92, nose_proj=1.08,
            lips=0.92, gaunt=0.35, skull=1.0)
BONE_GARMENTS = dict(waist_z=1.10, skirt_hem_z=0.82, bag=((0.20, -0.03, 1.02), (0.21, -0.03, 0.70)))


def body_parts(J, L):
    P = []
    P.append(K.torso([
        (0.80, 0.192, (0.122, 0.132), 2.2), (0.92, 0.180, (0.116, 0.120), 2.3), (1.04, 0.168, (0.112, 0.108), 2.3),
        (1.14, 0.170, (0.118, 0.105), 2.4), (1.26, 0.184, (0.124, 0.108), 2.5), (1.38, 0.196, (0.118, 0.112), 2.5),
        (1.45, 0.185, (0.104, 0.102), 2.5), (1.49, 0.130, (0.082, 0.080), 2.3), (1.535, 0.070, (0.062, 0.060), 2.0)],
        cls="leather", disp=K.folds_disp(0.003, (22.0, 8.0), seed=14)))
    for S_, sx in (("Left", 1), ("Right", -1)):
        P += K.shoulders(J, S_, sx, r=(0.078, 0.074, 0.080), cls="leather", off=0.016)
        # short leather sleeve over the linen sleeve, rolled linen cuff below the elbow
        P.append(K.upper_arm(J, S_, [(0.0, 0.074), (0.45, 0.070), (0.6, 0.068), (0.62, 0.060), (1.0, 0.056)],
                             cls="leather"))
        P += K.rolled_cuff(J, S_, t=1.04, R=0.054, r=0.024, cls="linen", second=False)
        P.append(K.forearm(J, S_, [(0.0, 0.050, 0.046), (0.25, 0.051, 0.046), (0.7, 0.042, 0.036), (1.0, 0.034, 0.028)]))
        P.append(K.thigh(J, S_, [(0.0, 0.102, 0.106), (0.5, 0.090, 0.094), (1.0, 0.074, 0.076)], cls="trousers"))
        P.append(K.shin(J, S_, [(0.0, 0.074, 0.076), (0.3, 0.078, 0.080), (0.6, 0.064, 0.066), (1.0, 0.052, 0.056)],
                        cls="trousers"))
        P += K.boot(J, S_, sx, L, top_z=0.34, cls="boot", shaft_r=(0.058, 0.060), width=1.04, height=1.1,
                    shaft_flare=1.14, cuff=0.011, round_toe=1.1)
    return P


def class_regions(ctx, cent, cls):
    """Linen shirt sleeve between the leather sleeve and the rolled cuff."""
    out = list(cls)
    for i, c in enumerate(out):
        if c != "leather":
            continue
        p = cent[i]
        for S_ in ("Left", "Right"):
            sh, el = ctx.J[f"{S_}UpperArm"], ctx.J[f"{S_}LowerArm"]
            a = el - sh
            t = np.dot(p - sh, a) / np.dot(a, a)
            if 0.63 < t < 1.1 and np.linalg.norm(p - (sh + a * t)) < 0.08:
                out[i] = "linen"
    return out


def head_extras(ctx):
    lm = ctx.lm
    s = lm["scale"]
    reg = G.hair_region(lm, front=0.074, temple_drop=0.18, side=-0.020, back=-0.075, noise=0.006, seed=21)
    out = [K.hair_shell(ctx, thick=0.020, region=reg, top_extra=0.006, taper=0.004)]
    cl = G.curls(lm, ctx.head_fn, lambda P: reg(P) + 0.004 * s, 70, 0.008 * s, 0.013 * s, 0.016 * s, seed=23)
    for c in cl:
        c.k = 0.007
    out += cl
    out += K.strands(ctx, [[(0.012, -0.020, 0.105), (0.020, -0.034, 0.075), (0.030, -0.030, 0.055)],
                           [(-0.020, -0.020, 0.108), (-0.025, -0.036, 0.080)]], r0=0.008, r1=0.005)
    return out


def garments(ctx):
    J = ctx.J
    cxy = ctx.center
    lm = ctx.lm
    out = []
    ax = lambda c: np.array([cxy[0], cxy[1], c[2]])
    # jerkin skirt (to the hips, front split)
    D = C.drape(ctx.torso_fn, cxy, (-3.0, 3.0), lambda th: np.full_like(th, 1.10), lambda th: 0.80 + 0.02 * np.cos(th),
                nu=40, nv=10, clearance=0.008, slack=0.05, flare=0.07, folds=[(12, 0.004, 0.5)], ragged=0.006, seed=41,
                fit=(ctx.hull_fn, 0.80, 1.08, 0, 0.25), part="jerkin_skirt")
    out.append(G.piece_from_drape("jerkin_skirt", D, "leather", 0.005,
                                  {"type": "skirt", "top_z": 1.10, "hem_z": 0.80, "follow": 0.6}, ax))
    # lowered hood: cowl ring around the neck + hood bag on the upper back
    O = np.array([0.0, 0.02, 1.48])

    def outer(P):
        cowl = fsdf.torus(O, 0.115, 0.042, axis=(0, 0.25, 1.0)).fn(P)
        bag = fsdf.ellipsoid(O + np.array([0.0, 0.11, -0.10]), (0.13, 0.055, 0.12)).fn(P)
        return fsdf.smin(cowl, bag, 0.04)

    def inner(P):
        return ctx.body_fn(P) - 0.004
    hood = K.headwear_piece("hood_down", ctx, outer, inner, O - 0.26, O + 0.26, "hood",
                            {"type": "blend", "bones": {"UpperChest": 0.5, "Neck": 0.2, "Hood": 0.3}})
    out.append(hood)
    # diagonal strap (right shoulder -> left hip) and chest lacing
    th = np.concatenate([np.linspace(0.75, -0.42, 18), np.linspace(-0.55, -2.6, 6), np.linspace(-2.75, -3.85, 16)])
    zs = np.concatenate([np.linspace(0.98, 1.50, 18), np.full(6, 1.54), np.linspace(1.50, 0.98, 16)])
    P_, N_ = G.curve_on_body(ctx.body_fn, cxy, th, zs, clearance=0.008)
    out.append(G.band_piece("strap", P_, N_, 0.032, 0.004, "leather_dark", {"type": "body"}))
    lace = []
    for k, z in enumerate(np.linspace(1.42, 1.22, 6)):
        for sx in ((-1, 1) if k % 2 == 0 else (1, -1)):
            lace.append(C.surface_point(ctx.body_fn, np.array([0.0, 0.0, z]), np.array([sx * 0.10, -1.0, 0.0]),
                                        clearance=0.0))
    out.append(G.tube_piece("lacing", np.array(lace), 0.0025, "leather_dark", {"type": "body"}, sides=4))
    # bronze tree emblem plate on the LEFT chest
    ep = C.surface_point(ctx.body_fn, np.array([0.10, 0.0, 1.41]), np.array([0.15, -1.0, 0.0]), clearance=0.002)
    out.append(G.lathe_piece("emblem", [(0.0, 0.0), (0.030, 0.0), (0.030, 0.003), (0.0, 0.004)], ep, (0.15, -1.0, 0.0),
                             "brass", {"type": "body"}, sides=6))
    # belts
    out += PR.belt("belt", ctx.torso_fn, cxy, 1.095, width=0.040, cls="leather_dark", clearance=0.010)
    out += PR.belt("hip_belt", ctx.torso_fn, cxy, 1.02, width=0.030, cls="leather_dark", clearance=0.016, tilt=-0.02,
                   buckle_theta=0.4)
    # dagger in sheath on the RIGHT hip
    hilt = C.surface_point(ctx.torso_fn, np.array([-0.15, -0.02, 1.04]), np.array([-0.7, -0.7, 0]), clearance=0.03)
    M = PR.frame(hilt, (0.7, -0.7, 0.0), (0.05, 0.0, 1.0))
    rule = {"type": "rigid", "bone": "Hips"}
    sh = PR.place(PR.sheath(rule, 0.22), PR.frame(hilt - np.array([0, 0, 0.05]), (0.7, -0.7, 0.0), (0.05, 0.0, 1.0)))
    dg = PR.dagger(rule)
    Mf = M @ np.diag([1.0, -1.0, -1.0, 1.0])
    Mf[:3, 3] = hilt + np.array([0, 0, 0.03])
    out += [sh, PR.place(dg, Mf)]
    # quiver on the LEFT hip, tilted forward, with arrows
    qtop = C.surface_point(ctx.torso_fn, np.array([0.17, -0.02, 1.00]), np.array([0.8, -0.6, 0]), clearance=0.05)
    Mq = PR.frame(qtop, (0.6, 0.8, 0.0), (0.12, -0.05, 1.0))
    out.append(PR.place(PR.quiver({"type": "rigid", "bone": "Bag"}, length=0.40, r=0.050), Mq))
    # bow slung across the back (default)
    bc = np.array([0.0, 0.17, 1.30])
    Mb = PR.frame(bc, (0.0, -1.0, 0.0), (0.55, 0.0, 0.84))
    bow = PR.place(PR.bow({"type": "rigid", "bone": "LeftProp"}, length=1.20), Mb)
    bow.name = "bow"
    bow.meta["no_compare"] = True        # the sheet shows the bow only as a separate inset
    bow.meta["prop"] = {"bone": "LeftProp", "carry_bone": "UpperChest", "carry_place": Mb,
                        "hand_place": PR.bone_frame(ctx.B, "LeftProp", roll_up=(0, 0, 1.0)),
                        "held": ["lf_soldier_guard", "lf_soldier_attack", "lf_soldier_hit", "lf_soldier_death"]}
    out.append(bow)
    return out
