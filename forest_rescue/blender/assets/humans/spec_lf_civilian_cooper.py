"""COOPER — elderly man ~60, grey wavy hair and full grey beard, ochre wool flat cap; light
linen shirt with rolled sleeves; long brown leather apron (bib with neck straps crossing in an X
on the back, waist ties in a bow), wide leather belt with a big buckle over the apron, hammer
hanging at the right hip; emerald band knotted on the RIGHT upper arm; dark baggy trousers,
worn boots.  Sheet: civilian_survivors (cell 5)."""
import math

import numpy as np

from frlib import sdf as fsdf

import humans_cloth as C
import humans_geo as G
import humans_kit as K
import humans_props as PR
import humans_sdf as H

ASSET = "lf_civilian_cooper"
GROUP = "civilian"
CLASS_GROUP = {"shirt": "garment", "cap": "garment"}
BUDGET = {"head": 2500, "cap": 600}
FACE_PAINT = {"lip_tint": (1.03, 0.9, 0.88)}
OPTIONAL_COLORS = {"cap": (0.55, 0.40, 0.18)}

L = dict(
    crown=1.700, top=1.75, eye=1.596, mouth=1.528, chin=1.488, neck=1.430,
    shoulder_l=(0.188, 1.385), shoulder_r=(-0.188, 1.385),
    elbow_l=(0.262, 1.115), elbow_r=(-0.262, 1.115),
    wrist_l=(0.275, 0.905), wrist_r=(-0.272, 0.905),
    hip_l=(0.092, 0.880), hip_r=(-0.092, 0.880),
    knee_l=(0.100, 0.470), knee_r=(-0.100, 0.470),
    ankle_l=(0.122, 0.080), ankle_r=(-0.118, 0.080),
    hand_len=0.090, hand_scale=1.0, foot_len=0.26, toe_out_deg=10.0, female=False,
)
FACE = dict(width=0.98, jaw=0.96, chin=0.92, cheek=1.1, brow=1.2, nose_len=1.06, nose_w=1.1, nose_proj=1.05,
            nose_tip=1.15, lips=0.85, gaunt=0.35, skull=1.0, eye_depth=1.1)


def body_parts(J, L):
    P = []
    P.append(K.torso([
        (0.62, 0.190, (0.120, 0.135), 2.2), (0.75, 0.185, (0.116, 0.128), 2.2), (0.90, 0.178, (0.118, 0.118), 2.3),
        (1.02, 0.172, (0.126, 0.110), 2.3), (1.14, 0.180, (0.128, 0.108), 2.4), (1.26, 0.190, (0.120, 0.112), 2.5),
        (1.34, 0.188, (0.108, 0.108), 2.5), (1.39, 0.160, (0.092, 0.092), 2.4), (1.42, 0.110, (0.072, 0.070), 2.2),
        (1.445, 0.066, (0.056, 0.054), 2.0)], cls="shirt", disp=K.folds_disp(0.004, (22.0, 9.0), seed=3)))
    for S_, sx in (("Left", 1), ("Right", -1)):
        P += K.shoulders(J, S_, sx, r=(0.078, 0.074, 0.080), cls="shirt", off=0.016)
        P.append(K.upper_arm(J, S_, [(0.0, 0.074), (0.5, 0.072), (0.85, 0.068), (1.0, 0.062)], cls="shirt"))
        P += K.rolled_cuff(J, S_, t=0.97, R=0.060, r=0.026, cls="shirt")
        P.append(K.forearm(J, S_, [(0.0, 0.050, 0.046), (0.25, 0.050, 0.046), (0.70, 0.040, 0.034), (1.0, 0.033, 0.027)]))
        P.append(K.thigh(J, S_, [(0.0, 0.108, 0.112), (0.5, 0.100, 0.102), (1.0, 0.090, 0.090)]))
        P.append(K.shin(J, S_, [(0.0, 0.090, 0.092), (0.3, 0.094, 0.096), (0.55, 0.086, 0.088), (0.72, 0.068, 0.072),
                                (1.0, 0.054, 0.058)]))
        P += K.boot(J, S_, sx, L, top_z=0.17, cls="boot", shaft_r=(0.062, 0.060), width=1.12, height=1.20,
                    shaft_flare=1.05, round_toe=1.15)
    return P


def head_extras(ctx):
    lm = ctx.lm
    s = lm["scale"]
    reg = G.hair_region(lm, front=0.040, temple_drop=0.10, side=-0.010, back=-0.090, noise=0.006, seed=6)
    out = [K.hair_shell(ctx, thick=0.014, region=reg, back_extra=0.006, taper=0.004)]
    # unruly grey tufts sticking out under the cap (sides and back)
    tufts = []
    rng = np.random.default_rng(14)
    for k in range(18):
        a = rng.uniform(-2.6, 2.6)
        r0 = np.array([0.072 * math.sin(a), 0.085 - 0.075 * math.cos(a), rng.uniform(-0.03, 0.03)])
        r1 = r0 + np.array([0.025 * math.sin(a), -0.02 * math.cos(a) + 0.01, rng.uniform(-0.035, -0.01)])
        tufts.append([tuple(r0), tuple(r1)])
    out += K.strands(ctx, tufts, r0=0.010, r1=0.004)
    out += K.beard_prims(ctx, thick=0.019, curls=80, seed=41, top=-0.034, slope=0.30, back=0.080, lift=0.014,
                         rmin=0.006, rmax=0.011, taper=0.010)
    return out


def garments(ctx):
    J = ctx.J
    cxy = ctx.center
    lm = ctx.lm
    s = lm["scale"]
    out = []
    ax = lambda c: np.array([cxy[0], cxy[1], c[2]])
    # ---- flat cap (beret-like, slightly puffed, visor band) -> separate headwear
    O = lm["origin"]
    cc = O + np.array([0.0, 0.070, 0.090]) * s

    def outer(P):
        crown = fsdf.ellipsoid(cc + np.array([0, 0.0, 0.010]) * s, np.array([0.095, 0.112, 0.040]) * s).fn(P)
        band = fsdf.ellipsoid(cc - np.array([0, 0.0, 0.020]) * s, np.array([0.082, 0.098, 0.030]) * s).fn(P)
        peak = fsdf.ellipsoid(cc + np.array([0, -0.095, -0.028]) * s, np.array([0.060, 0.040, 0.010]) * s).fn(P)
        return fsdf.smin(fsdf.smin(crown, band, 0.01), peak, 0.006)

    def inner(P):
        return ctx.head_fn(P) - 0.012 * s
    cap = K.headwear_piece("cap", ctx, outer, inner, cc - 0.14, cc + 0.14, "cap", {"type": "rigid", "bone": "Head"},
                           voxel=0.0024)
    cap.meta["optional"] = "cap"
    cap.meta["default_on"] = True
    out.append(cap)
    # ---- leather apron: bib + skirt (front, wrapping to the sides) to the knees
    def hem(th):
        return 0.395 + 0.03 * np.clip(np.abs(th) - 1.2, 0, 1)
    D = C.drape(ctx.torso_fn, cxy, (-2.05, 2.05), lambda th: np.full_like(th, 1.085), hem, nu=28, nv=16,
                clearance=0.012, slack=0.05, flare=0.05, folds=[(8, 0.004, 0.2)], ragged=0.004, seed=21,
                fit=(ctx.hull_fn, 0.40, 1.05, 0, 0.3), part="apron")
    out.append(G.piece_from_drape("apron_skirt", D, "leather", 0.006,
                                  {"type": "skirt", "top_z": 1.08, "hem_z": 0.40, "follow": 0.55}, ax))

    def bib_taper(z):
        w = np.interp(z, [1.06, 1.25, 1.40], [0.90, 0.72, 0.58])
        return (-w, w)
    Db = C.drape(ctx.torso_fn, cxy, (-1.0, 1.0), lambda th: np.full_like(th, 1.395), lambda th: np.full_like(th, 1.06),
                 nu=12, nv=10, clearance=0.010, slack=0.25, taper=bib_taper, part="bib")
    out.append(G.piece_from_drape("apron_bib", Db, "leather", 0.006, {"type": "body"}, ax))
    # neck straps crossing in an X on the back
    for sx in (1, -1):
        th = np.concatenate([np.linspace(sx * 0.45, sx * 1.3, 6), np.linspace(sx * 1.6, sx * 2.8, 6),
                             np.linspace(sx * 3.0, sx * 3.9, 10)])
        zs = np.concatenate([np.linspace(1.39, 1.445, 6), np.linspace(1.45, 1.40, 6), np.linspace(1.36, 1.10, 10)])
        P_, N_ = G.curve_on_body(ctx.body_fn, cxy, th, zs, clearance=0.006)
        out.append(G.band_piece(f"apron_strap_{sx}", P_, N_, 0.026, 0.004, "leather", {"type": "body"}))
    # waist ties + bow at the back (linen)
    th = np.linspace(1.9, 4.38, 20)
    P_, N_ = G.curve_on_body(ctx.torso_fn, cxy, th, np.full_like(th, 1.075), clearance=0.010)
    out.append(G.band_piece("apron_ties", P_, N_, 0.024, 0.003, "linen", {"type": "body"}))
    bc = C.surface_point(ctx.torso_fn, np.array([0, 0.02, 1.07]), np.array([0, 1.0, 0]), clearance=0.018)
    for sx in (1, -1):
        loop = [bc + np.array([sx * dx, 0.010 + 0.010 * np.sin(np.pi * dx / 0.07), dz]) for dx, dz in
                zip(np.linspace(0.0, 0.07, 7), 0.02 * np.sin(np.linspace(0, np.pi, 7)))]
        out.append(G.tube_piece(f"apron_bow_{sx}", np.array(loop), 0.009, "linen", {"type": "body"}, sides=6))
        tail = np.array([bc + np.array([sx * 0.01, 0.012, -0.01]), bc + np.array([sx * 0.025, 0.015, -0.10]),
                         bc + np.array([sx * 0.03, 0.016, -0.20])])
        out.append(G.tube_piece(f"apron_tail_{sx}", tail, 0.010, "linen",
                                {"type": "skirt", "top_z": 1.07, "hem_z": 0.85, "follow": 0.3}, sides=6))
    # wide belt over the apron with a big buckle
    out += PR.belt("belt", ctx.body_fn, cxy, 1.035, width=0.048, cls="leather_dark", clearance=0.012,
                   buckle_cls="metal")
    # hammer hanging at the right front hip (head down)
    hang = C.surface_point(ctx.body_fn, np.array([-0.095, 0.0, 1.00]), np.array([-0.2, -1.0, 0]), clearance=0.02)
    M = PR.frame(hang, (1.0, 0, 0), (0.18, 0.0, 1.0))
    out.append(PR.place(PR.hammer({"type": "rigid", "bone": "Bag"}, handle=0.30), M))
    # emerald band knotted on the RIGHT upper arm
    P_, N_ = G.ring_on_limb(ctx.body_fn, J["RightUpperArm"], J["RightLowerArm"], 0.62, n=20, clearance=0.003)
    out.append(G.band_piece("armband", P_, N_, 0.045, 0.004, "armband", {"type": "rigid", "bone": "RightUpperArm"},
                            closed=True, segs_w=2))
    k = int(np.argmin(P_[:, 0]))
    knot = P_[k] + N_[k] * 0.012
    out.append(G.box_piece("armband_knot", knot, (0.03, 0.03, 0.03), None, "armband",
                           {"type": "rigid", "bone": "RightUpperArm"}, bevel=0.9))
    for d in ((-0.02, -0.01, -0.07), (-0.03, 0.01, -0.06)):
        out.append(G.band_piece(f"armband_end{d[1]}", np.array([knot, knot + np.array(d) * 0.5, knot + np.array(d)]),
                                np.array([[-1.0, 0, 0]] * 3), 0.022, 0.003, "armband",
                                {"type": "rigid", "bone": "RightUpperArm"}))
    return out
