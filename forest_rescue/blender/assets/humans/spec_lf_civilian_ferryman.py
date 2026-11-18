"""FERRYMAN — broad-shouldered man ~35-40, wavy dark hair to the collar, short dark beard;
slate-grey wool tunic (V-slit neck, rolled sleeves, ragged hem to mid-thigh), twisted rope belt
with a long coil hanging at the right front, emerald armband on the LEFT upper arm, grey baggy
trousers, leather wraps cross-bound from ankle to knee over turnshoe boots.
Differs from the miller: longer, narrower face, higher sharper cheekbones, straight longer
narrow nose, leaner cheeks, shorter beard, younger.  Sheet: civilian_survivors (cell 3)."""
import math

import numpy as np

import humans_cloth as C
import humans_geo as G
import humans_kit as K
import humans_sdf as H

ASSET = "lf_civilian_ferryman"
GROUP = "civilian"
CLASS_GROUP = {"tunic": "garment"}
BUDGET = {"head": 2400}
FACE_PAINT = {"lip_tint": (1.04, 0.9, 0.88)}

L = dict(
    crown=1.790, top=1.83, eye=1.676, mouth=1.596, chin=1.548, neck=1.490,
    shoulder_l=(0.205, 1.430), shoulder_r=(-0.205, 1.430),
    elbow_l=(0.300, 1.150), elbow_r=(-0.300, 1.150),
    wrist_l=(0.318, 0.930), wrist_r=(-0.318, 0.930),
    hip_l=(0.098, 0.910), hip_r=(-0.098, 0.910),
    knee_l=(0.120, 0.490), knee_r=(-0.120, 0.490),
    ankle_l=(0.160, 0.085), ankle_r=(-0.158, 0.085),
    hand_len=0.094, hand_scale=1.08, foot_len=0.27, toe_out_deg=9.0, female=False,
)
FACE = dict(width=0.96, jaw=0.98, chin=1.12, cheek=1.35, cheek_z=0.004, brow=1.15, nose_len=1.12, nose_w=0.88,
            nose_proj=1.12, nose_tip=0.9, nose_bridge=1.1, lips=0.92, mouth_w=1.0, gaunt=0.55, fat=0.0, skull=1.0,
            eye_sep=0.98)


def body_parts(J, L):
    P = []
    P.append(K.torso([
        (0.700, 0.215, (0.135, 0.150), 2.2), (0.80, 0.205, (0.128, 0.138), 2.2), (0.92, 0.190, (0.122, 0.122), 2.3),
        (1.04, 0.180, (0.122, 0.112), 2.3), (1.14, 0.188, (0.128, 0.112), 2.4), (1.26, 0.205, (0.128, 0.116), 2.5),
        (1.38, 0.212, (0.118, 0.115), 2.5), (1.435, 0.180, (0.098, 0.098), 2.4), (1.470, 0.120, (0.078, 0.076), 2.2),
        (1.500, 0.070, (0.060, 0.058), 2.0)], cls="tunic", disp=K.folds_disp(0.004, (20.0, 9.0), seed=6)))
    for S_, sx in (("Left", 1), ("Right", -1)):
        P += K.shoulders(J, S_, sx, r=(0.090, 0.082, 0.090), cls="tunic", off=0.018)
        P.append(K.upper_arm(J, S_, [(0.0, 0.080), (0.5, 0.076), (0.85, 0.072), (1.0, 0.066)], cls="tunic"))
        P += K.rolled_cuff(J, S_, t=0.98, R=0.064, r=0.028, cls="tunic")
        P.append(K.forearm(J, S_, [(0.0, 0.054, 0.050), (0.25, 0.056, 0.050), (0.70, 0.044, 0.037), (1.0, 0.035, 0.028)]))
        P.append(K.thigh(J, S_, [(0.0, 0.112, 0.118), (0.4, 0.104, 0.108), (1.0, 0.088, 0.090)]))
        P.append(K.shin(J, S_, [(0.0, 0.090, 0.092), (0.18, 0.094, 0.096), (0.30, 0.074, 0.078), (0.6, 0.064, 0.068),
                                (1.0, 0.056, 0.060)], cls="wraps"))
        P += K.boot(J, S_, sx, L, top_z=0.15, cls="boot", shaft_r=(0.062, 0.058), width=1.10, height=1.15,
                    round_toe=1.15)
    return P


def head_extras(ctx):
    lm = ctx.lm
    s = lm["scale"]
    reg = G.hair_region(lm, front=0.070, temple_drop=0.18, side=-0.030, back=-0.110, noise=0.004, seed=9)
    out = [K.hair_shell(ctx, thick=0.020, region=reg, back_extra=0.012, taper=0.004)]
    cl = G.curls(lm, ctx.head_fn, lambda P: reg(P) + 0.004 * s, 90, 0.008 * s, 0.013 * s, 0.016 * s, seed=13)
    for c in cl:
        c.k = 0.007
    out += cl
    # longer waves at the nape and over the ears
    locks = []
    for sx in (1, -1):
        for k in range(3):
            locks.append([(sx * (0.050 + 0.010 * k), 0.080 + 0.015 * k, -0.010), (sx * (0.060 + 0.010 * k), 0.100 + 0.012 * k, -0.070),
                          (sx * (0.055 + 0.012 * k), 0.110 + 0.010 * k, -0.120)])
    out += K.strands(ctx, locks, r0=0.012, r1=0.008)
    out += K.beard_prims(ctx, thick=0.011, curls=40, seed=31, top=-0.050, slope=0.26, back=0.075, lift=0.008,
                         rmin=0.005, rmax=0.008, taper=0.008)
    return out


def garments(ctx):
    J, L = ctx.J, ctx.L
    cxy = ctx.center
    out = []
    # rope belt (twisted, 2 turns)
    th = np.linspace(-math.pi, math.pi, 34, endpoint=False)
    for k, dz in enumerate((0.0, 0.020)):
        P_, N_ = G.curve_on_body(ctx.torso_fn, cxy, th, np.full_like(th, 1.110 + dz + 0.006 * np.cos(th)),
                                 clearance=0.010)
        out.append(G.tube_piece(f"rope_belt_{k}", np.vstack([P_, P_[:1]]), 0.0105, "rope", {"type": "body"}, sides=7,
                                caps=False))
    # long coil hanging at the right front: loops from the belt down to z~0.62
    top = C.surface_point(ctx.torso_fn, np.array([-0.10, 0.0, 1.10]), np.array([-0.3, -1.0, 0.0]), clearance=0.02)
    loops = []
    for k, (dx, bottom) in enumerate(((0.0, 0.62), (0.03, 0.68), (-0.025, 0.72))):
        t = np.linspace(0, 1, 18)
        x = top[0] + dx + 0.035 * np.sin(2 * math.pi * t) * (0.6 + 0.4 * k)
        z = top[2] - (top[2] - bottom) * np.sin(math.pi * t) ** 0.7
        y = top[1] - 0.022 - 0.012 * np.sin(math.pi * t) - 0.008 * k
        loops.append(G.tube_piece(f"coil_{k}", np.stack([x, y, z], -1), 0.0095, "rope",
                                  {"type": "skirt", "top_z": 1.10, "hem_z": 0.62, "follow": 0.15}, sides=6))
    out.append(G.merge_pieces("rope_coil", loops, cls="rope",
                              rule={"type": "skirt", "top_z": 1.10, "hem_z": 0.62, "follow": 0.15}))
    # tunic skirt from the belt down (ragged hem, open slits at the sides)
    def hem(th):
        return 0.700 + 0.03 * np.cos(th) ** 2
    D = C.drape(ctx.torso_fn, cxy, (-math.pi, math.pi), lambda th: np.full_like(th, 1.100), hem, nu=32, nv=9,
                closed=True, clearance=0.006, slack=0.05, flare=0.06, folds=[(11, 0.005, 0.3), (19, 0.002, 1.1)],
                ragged=0.010, seed=12, fit=(ctx.hull_fn, 0.70, 1.0, 0, 0.25), part="tunic_skirt")
    out.append(G.piece_from_drape("tunic_skirt", D, "tunic", 0.004,
                                  {"type": "skirt", "top_z": 1.10, "hem_z": 0.70, "follow": 0.6},
                                  lambda c: np.array([cxy[0], cxy[1], c[2]])))
    # armband LEFT
    P_, N_ = G.ring_on_limb(ctx.body_fn, J["LeftUpperArm"], J["LeftLowerArm"], 0.42, n=20, clearance=0.003)
    out.append(G.band_piece("armband", P_, N_, 0.058, 0.004, "armband", {"type": "rigid", "bone": "LeftUpperArm"},
                            closed=True, segs_w=2))
    # leg wraps (criss-cross leather bindings) + boot straps
    for S_ in ("Left", "Right"):
        out.append(G.wraps_piece(f"wraps_{S_}", ctx.body_fn, J, S_, 0.13, 0.42, turns=3.5, width=0.020, thick=0.003,
                                 cls="leather"))
    return out
