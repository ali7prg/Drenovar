"""QUARRY WORKER — sturdy woman ~40, dark curly hair tied in a bun; limestone-grey linen shirt
with sleeves rolled to the forearm, sleeveless brown leather vest (buttoned, ragged hem at the
hips), emerald sash tied at the front-left with long hanging ends; grey baggy trousers bloused at
the knees, short worn boots.  Sheet: civilian_survivors (cell 6)."""
import math

import numpy as np

import humans_cloth as C
import humans_geo as G
import humans_kit as K
import humans_props as PR
import humans_sdf as H

ASSET = "lf_civilian_quarry_worker"
GROUP = "civilian"
CLASS_GROUP = {"linen": "garment", "trousers": "garment"}
BUDGET = {"head": 2400}
FACE_PAINT = {"lip_tint": (1.05, 0.88, 0.86)}

L = dict(
    crown=1.705, top=1.75, eye=1.616, mouth=1.550, chin=1.512, neck=1.455,
    shoulder_l=(0.185, 1.405), shoulder_r=(-0.185, 1.405),
    elbow_l=(0.262, 1.135), elbow_r=(-0.262, 1.135),
    wrist_l=(0.300, 0.925), wrist_r=(-0.300, 0.925),
    hip_l=(0.095, 0.870), hip_r=(-0.095, 0.870),
    knee_l=(0.112, 0.470), knee_r=(-0.112, 0.470),
    ankle_l=(0.140, 0.080), ankle_r=(-0.135, 0.080),
    hand_len=0.088, hand_scale=0.98, foot_len=0.25, toe_out_deg=9.0, female=True,
)
FACE = dict(female=True, width=1.02, jaw=1.02, chin=1.0, cheek=1.2, brow=0.8, nose_len=1.0, nose_w=1.05,
            nose_proj=1.0, lips=1.0, mouth_w=1.05, fat=0.2, skull=0.98)
NECK_R = (0.054, 0.046)
BONE_GARMENTS = dict(waist_z=1.10, skirt_hem_z=0.86)


def body_parts(J, L):
    P = []
    # vest volume over the linen torso (the vest is part of the body surface; classes split by region)
    P.append(K.torso([
        (0.86, 0.200, (0.128, 0.140), 2.3), (0.96, 0.192, (0.124, 0.130), 2.3), (1.06, 0.180, (0.122, 0.118), 2.4),
        (1.16, 0.182, (0.128, 0.112), 2.4), (1.27, 0.186, (0.124, 0.112), 2.5), (1.35, 0.180, (0.112, 0.108), 2.5),
        (1.40, 0.150, (0.092, 0.090), 2.4), (1.43, 0.105, (0.072, 0.070), 2.2), (1.465, 0.064, (0.056, 0.054), 2.0)],
        cls="vest", disp=K.folds_disp(0.003, (20.0, 8.0), seed=10)))
    for S_, sx in (("Left", 1), ("Right", -1)):
        P += K.shoulders(J, S_, sx, r=(0.080, 0.076, 0.082), cls="linen", off=0.016)
        P.append(K.upper_arm(J, S_, [(0.0, 0.076), (0.5, 0.074), (0.85, 0.070), (1.0, 0.066)], cls="linen"))
        P += K.rolled_cuff(J, S_, t=0.92, R=0.064, r=0.028, cls="linen")
        P.append(K.forearm(J, S_, [(0.0, 0.052, 0.048), (0.25, 0.052, 0.047), (0.70, 0.042, 0.036), (1.0, 0.034, 0.028)]))
        P.append(K.thigh(J, S_, [(0.0, 0.118, 0.122), (0.5, 0.112, 0.114), (1.0, 0.104, 0.104)]))
        P.append(K.shin(J, S_, [(0.0, 0.106, 0.106), (0.15, 0.110, 0.110), (0.30, 0.104, 0.104), (0.48, 0.080, 0.084),
                                (0.6, 0.064, 0.068), (1.0, 0.054, 0.058)]))
        P += K.boot(J, S_, sx, L, top_z=0.21, cls="boot", shaft_r=(0.064, 0.062), width=1.10, height=1.15,
                    shaft_flare=1.08, cuff=0.008, round_toe=1.12)
    return P


def class_regions(ctx, cent, cls):
    """Vest covers the torso except the open V at the neck (linen shirt shows)."""
    out = list(cls)
    for i, c in enumerate(out):
        if c != "vest":
            continue
        x, y, z = cent[i]
        if z > 1.30 and y < 0 and abs(x) < 0.03 + 0.5 * (z - 1.30):
            out[i] = "linen"
        if z > 1.40 and abs(x) < 0.085:
            out[i] = "linen"
    return out


def head_extras(ctx):
    lm = ctx.lm
    s = lm["scale"]
    reg = G.hair_region(lm, front=0.074, temple_drop=0.22, side=-0.015, back=-0.050, noise=0.004, seed=7)
    out = [K.hair_shell(ctx, thick=0.012, region=reg, taper=0.004)]
    cl = G.curls(lm, ctx.head_fn, lambda P: reg(P) + 0.004 * s, 60, 0.006 * s, 0.010 * s, 0.010 * s, seed=17)
    for c in cl:
        c.k = 0.006
    out += cl
    out.append(K.bun(ctx, offset=(0.0, 0.158, 0.050), radii=(0.044, 0.036, 0.040)))
    locks = [[(0.060, 0.000, 0.060), (0.072, 0.012, 0.000), (0.070, 0.022, -0.050)],
             [(-0.060, 0.000, 0.060), (-0.074, 0.014, 0.000), (-0.072, 0.024, -0.055)]]
    out += K.strands(ctx, locks, r0=0.008, r1=0.005)
    return out


def garments(ctx):
    J = ctx.J
    cxy = ctx.center
    out = []
    ax = lambda c: np.array([cxy[0], cxy[1], c[2]])
    # vest skirt (ragged, open at the front below the sash)
    D = C.drape(ctx.torso_fn, cxy, (-2.95, 2.95), lambda th: np.full_like(th, 1.10),
                lambda th: 0.88 - 0.02 * np.cos(th), nu=40, nv=8, clearance=0.006, slack=0.05, flare=0.10,
                folds=[(13, 0.004, 0.1)], ragged=0.012, seed=31, fit=(ctx.hull_fn, 0.88, 1.08, 0, 0.25),
                part="vest_skirt")
    out.append(G.piece_from_drape("vest_skirt", D, "vest", 0.005,
                                  {"type": "skirt", "top_z": 1.10, "hem_z": 0.86, "follow": 0.6}, ax))
    # emerald sash (wide, two turns) + knot at the front-left with long ends
    th = np.linspace(-math.pi, math.pi, 46, endpoint=False)
    P_, N_ = G.curve_on_body(ctx.body_fn, cxy, th, np.full_like(th, 1.105), clearance=0.010)
    out.append(G.band_piece("sash", P_, N_, 0.060, 0.005, "sash", {"type": "body"}, closed=True, segs_w=2))
    kn = C.surface_point(ctx.body_fn, np.array([0.06, 0.0, 1.10]), np.array([0.1, -1.0, 0]), clearance=0.02)
    out.append(G.box_piece("sash_knot", kn, (0.05, 0.035, 0.045), None, "sash", {"type": "body"}, bevel=0.85))
    for dx, zend, w in ((0.005, 0.80, 0.045), (0.040, 0.86, 0.040)):
        pts = np.array([kn + np.array([dx * 0.4, -0.005, -0.02]), kn + np.array([dx, -0.012, -0.12]),
                        kn + np.array([dx * 1.2, -0.014, -(1.10 - zend) * 0.7]), kn + np.array([dx * 1.3, -0.012, -(1.10 - zend)])])
        out.append(G.band_piece(f"sash_end_{dx}", pts, np.array([[0, -1.0, 0]] * 4), w, 0.004, "sash",
                                {"type": "skirt", "top_z": 1.10, "hem_z": zend, "follow": 0.25}, segs_w=2))
    # vest buttons
    for z in (1.30, 1.25, 1.20, 1.15):
        bp = C.surface_point(ctx.body_fn, np.array([0.0, 0.0, z]), np.array([0.0, -1.0, 0.0]), clearance=0.0)
        out.append(G.lathe_piece(f"button_{z}", [(0.0, 0.0), (0.008, 0.0), (0.007, 0.004), (0.0, 0.005)], bp,
                                 (0, -1.0, 0), "wood", {"type": "body"}, sides=8))
    return out
