"""SHIELD GUARD — broad man ~40, short ginger-red beard, iron nasal helmet (conical, rim band,
nasal bar); deep-blue diamond-quilted gambeson to mid-thigh with standing collar, toggle
closures and a gold tree emblem on the left chest; wide belt with buckle and a hanging strap at
the right hip; baggy brown trousers, wrapped lower legs, boots.  Round oak shield with iron boss
(LeftProp) and spear (RightProp) are separate rigid meshes.
Sheet: 04_expedition_squad_turnaround (figures 5-6)."""
import math

import numpy as np

from frlib import sdf as fsdf

import humans_cloth as C
import humans_geo as G
import humans_kit as K
import humans_props as PR
import humans_sdf as H

ASSET = "lf_squad_shield_guard"
GROUP = "soldier"
ROLE = "shield_guard"
CLASS_GROUP = {"gambeson": "garment"}
BUDGET = {"head": 2200, "helmet": 900}
FACE_PAINT = {"lip_tint": (1.03, 0.9, 0.88)}
OPTIONAL_COLORS = {"metal": (0.42, 0.42, 0.42)}

L = dict(
    crown=1.840, top=1.92, eye=1.738, mouth=1.665, chin=1.625, neck=1.565,
    shoulder_l=(0.225, 1.500), shoulder_r=(-0.225, 1.500),
    elbow_l=(0.335, 1.230), elbow_r=(-0.335, 1.230),
    wrist_l=(0.405, 0.985), wrist_r=(-0.405, 0.985),
    hip_l=(0.105, 0.940), hip_r=(-0.105, 0.940),
    knee_l=(0.125, 0.510), knee_r=(-0.125, 0.510),
    ankle_l=(0.150, 0.085), ankle_r=(-0.150, 0.085),
    hand_len=0.098, hand_scale=1.12, foot_len=0.28, toe_out_deg=9.0, female=False,
)
FACE = dict(width=1.08, jaw=1.12, chin=1.0, cheek=1.0, brow=1.15, nose_len=1.02, nose_w=1.12, nose_proj=1.0,
            nose_tip=1.1, lips=0.95, fat=0.3, skull=1.03)


def body_parts(J, L):
    P = []
    quilt = None
    P.append(K.torso([
        (0.72, 0.250, (0.150, 0.160), 2.3), (0.84, 0.240, (0.145, 0.150), 2.3), (0.96, 0.228, (0.142, 0.140), 2.4),
        (1.08, 0.222, (0.146, 0.132), 2.4), (1.20, 0.232, (0.150, 0.132), 2.5), (1.32, 0.245, (0.145, 0.135), 2.6),
        (1.44, 0.250, (0.135, 0.132), 2.6), (1.50, 0.215, (0.115, 0.112), 2.5), (1.545, 0.140, (0.090, 0.088), 2.2),
        (1.585, 0.082, (0.070, 0.068), 2.0)], cls="gambeson"))
    # standing collar
    P.append(H.tag(H.vloft(1.54, 1.60, [(1.54, 0.090, 0.082), (1.60, 0.078, 0.072)], y=0.012), cls="gambeson",
                   bone="UpperChest", k=0.012, name="collar"))
    for S_, sx in (("Left", 1), ("Right", -1)):
        P += K.shoulders(J, S_, sx, r=(0.100, 0.094, 0.098), cls="gambeson", off=0.020)
        P.append(K.upper_arm(J, S_, [(0.0, 0.094), (0.5, 0.088), (1.0, 0.078)], cls="gambeson"))
        P.append(K.forearm(J, S_, [(0.0, 0.074, 0.070), (0.6, 0.068, 0.064), (0.86, 0.064, 0.060), (0.90, 0.044, 0.040),
                                   (1.0, 0.038, 0.032)], cls="gambeson"))
        P.append(K.forearm_cuff(J, S_, 0.86, 0.064, 0.010, cls="leather"))
        P.append(K.thigh(J, S_, [(0.0, 0.128, 0.132), (0.5, 0.120, 0.122), (1.0, 0.108, 0.108)], cls="trousers"))
        P.append(K.shin(J, S_, [(0.0, 0.104, 0.104), (0.12, 0.108, 0.108), (0.25, 0.092, 0.094), (0.4, 0.078, 0.080),
                                (1.0, 0.066, 0.070)], cls="wraps"))
        P += K.boot(J, S_, sx, L, top_z=0.17, cls="boot", shaft_r=(0.070, 0.068), width=1.18, height=1.22,
                    shaft_flare=1.06, round_toe=1.15)
    return P


def head_extras(ctx):
    lm = ctx.lm
    s = lm["scale"]
    reg = G.hair_region(lm, front=0.060, temple_drop=0.10, side=-0.020, back=-0.080, noise=0.004, seed=3)
    out = [K.hair_shell(ctx, thick=0.008, region=reg, taper=0.004)]
    out += K.beard_prims(ctx, thick=0.014, curls=50, seed=51, top=-0.042, slope=0.28, back=0.078, lift=0.010,
                         rmin=0.005, rmax=0.009, taper=0.009)
    return out


def garments(ctx):
    J = ctx.J
    cxy = ctx.center
    lm = ctx.lm
    s = lm["scale"]
    out = []
    ax = lambda c: np.array([cxy[0], cxy[1], c[2]])
    # gambeson skirt (front split, quilted), from the belt to z~0.72
    D = C.drape(ctx.torso_fn, cxy, (-3.04, 3.04), lambda th: np.full_like(th, 1.12), lambda th: np.full_like(th, 0.715),
                nu=40, nv=10, clearance=0.006, slack=0.04, flare=0.06, folds=[(10, 0.004, 0.2)], seed=61,
                fit=(ctx.hull_fn, 0.72, 1.10, 0, 0.25), part="gambeson_skirt")
    out.append(G.piece_from_drape("gambeson_skirt", D, "gambeson", 0.010,
                                  {"type": "skirt", "top_z": 1.12, "hem_z": 0.72, "follow": 0.6}, ax))
    # helmet: conical dome + rim band + nasal bar (separate headwear, rigid on Head)
    O = lm["origin"]
    top = O + np.array([0.0, 0.080, 0.150]) * s

    def outer(P):
        Q = (np.asarray(P, float) - O) / s
        dome = fsdf.ellipsoid(O + np.array([0.0, 0.080, 0.035]) * s, np.array([0.092, 0.110, 0.118]) * s).fn(P)
        cone = fsdf.round_cone(O + np.array([0.0, 0.080, 0.050]) * s, top, 0.085 * s, 0.008 * s).fn(P)
        shell = fsdf.smin(dome, cone, 0.03)
        cut = (0.005 - Q[..., 2]) * s           # helmet ends at the brow line
        return np.maximum(shell, cut)

    def inner(P):
        return ctx.head_fn(P) - 0.010 * s
    rim_c = O + np.array([0.0, 0.080, 0.012]) * s
    rim = H.tag(fsdf.torus(rim_c, 0.088 * s, 0.009 * s, axis=(0, 0, 1.0)), cls="metal", bone="Head", k=0.004)
    nasal = H.tag(fsdf.box(O + np.array([0.0, -0.018, -0.012]) * s, np.array([0.008, 0.004, 0.040]) * s,
                           rot=(0.25, 0.0, 0.0), rounding=0.002), cls="metal", bone="Head", k=0.006)
    helmet = K.headwear_piece("helmet", ctx, outer, inner, O - 0.16, O + 0.25, "metal",
                              {"type": "rigid", "bone": "Head"}, voxel=0.0022, extra_prims=[rim, nasal])
    helmet.meta["optional"] = "helmet"
    helmet.meta["default_on"] = True
    out.append(helmet)
    # belt + buckle, hanging strap at the right hip
    out += PR.belt("belt", ctx.body_fn, cxy, 1.13, width=0.050, cls="leather_dark", clearance=0.008,
                   buckle_cls="metal")
    hp = C.surface_point(ctx.body_fn, np.array([-0.20, -0.04, 1.10]), np.array([-0.6, -0.8, 0]), clearance=0.006)
    pts = np.array([hp, hp + np.array([-0.01, -0.012, -0.10]), hp + np.array([-0.015, -0.016, -0.24])])
    out.append(G.band_piece("hang_strap", pts, np.array([[-0.6, -0.8, 0.0]] * 3), 0.040, 0.005, "leather_dark",
                            {"type": "skirt", "top_z": 1.12, "hem_z": 0.86, "follow": 0.3}))
    out.append(PR.pouch("pouch", hp + np.array([-0.012, -0.03, -0.10]), (0.08, 0.04, 0.09), (-0.6, -0.8, 0.0),
                        cls="leather", rule={"type": "rigid", "bone": "Hips"}))
    # gold tree emblem patch on the LEFT chest + toggles down the front
    ep = C.surface_point(ctx.body_fn, np.array([0.10, 0.0, 1.43]), np.array([0.15, -1.0, 0.0]), clearance=0.002)
    out.append(G.lathe_piece("emblem", [(0.0, 0.0), (0.040, 0.0), (0.040, 0.003), (0.0, 0.004)], ep,
                             (0.15, -1.0, 0.0), "brass", {"type": "body"}, sides=6))
    for z in (1.50, 1.40, 1.30, 1.20, 1.03, 0.93):
        tp = C.surface_point(ctx.body_fn, np.array([0.0, 0.0, z]), np.array([0.0, -1.0, 0.0]), clearance=0.0)
        out.append(G.box_piece(f"toggle_{z}", tp + np.array([0, -0.004, 0]), (0.036, 0.012, 0.010), None,
                               "leather_dark", {"type": "body"}, bevel=0.8))
    # leg wraps
    for S_ in ("Left", "Right"):
        out.append(G.wraps_piece(f"wraps_{S_}", ctx.body_fn, J, S_, 0.15, 0.45, turns=4.0, width=0.026, thick=0.003,
                                 cls="wraps"))
    return out


def optional_parts(ctx):
    """Shield on the left hand (LeftProp) and spear in the right hand (RightProp)."""
    B = ctx.B
    Ml = PR.bone_frame(B, "LeftProp", roll_up=(0, 0, 1.0))
    sh = PR.place(PR.round_shield({"type": "rigid", "bone": "LeftProp"}, radius=0.39), Ml)
    sh.name = "shield"
    sh.meta.update(no_compare=True)
    Mr = PR.bone_frame(B, "RightProp", roll_up=(0, 0, 1.0))
    sp = PR.place(PR.spear({"type": "rigid", "bone": "RightProp"}, below=0.95, above=1.05), Mr)
    sp.name = "spear"
    sp.meta.update(no_compare=True)
    return [sh, sp]
