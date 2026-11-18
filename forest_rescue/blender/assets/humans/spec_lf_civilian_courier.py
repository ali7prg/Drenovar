"""COURIER — slim woman ~30, dark hair in a loose bun; short rust hooded cape (hood lying on the
back, emerald trim at the hem, round brooch at the throat); fitted grey-olive tunic to the hips,
leather belt with buckle + hip belt with a pouch on the right; leather satchel on the LEFT hip on
a strap across the body from the right shoulder; leather bracers; fitted brown trousers tucked
into tall laced boots with turned cuffs.  Sheet: civilian_survivors (cell 4)."""
import math

import numpy as np

from frlib import sdf as fsdf

import humans_cloth as C
import humans_geo as G
import humans_kit as K
import humans_props as PR
import humans_sdf as H

ASSET = "lf_civilian_courier"
GROUP = "civilian"
CLASS_GROUP = {"tunic": "garment", "cloak": "garment"}
BUDGET = {"head": 2400, "hood_down": 500}
FACE_PAINT = {"lip_tint": (1.06, 0.88, 0.86)}

L = dict(
    crown=1.690, top=1.73, eye=1.600, mouth=1.535, chin=1.500, neck=1.445,
    shoulder_l=(0.174, 1.395), shoulder_r=(-0.174, 1.395),
    elbow_l=(0.248, 1.125), elbow_r=(-0.248, 1.125),
    wrist_l=(0.284, 0.905), wrist_r=(-0.284, 0.905),
    hip_l=(0.085, 0.865), hip_r=(-0.085, 0.865),
    knee_l=(0.085, 0.470), knee_r=(-0.088, 0.470),
    ankle_l=(0.098, 0.080), ankle_r=(-0.102, 0.080),
    hand_len=0.084, hand_scale=0.92, foot_len=0.245, toe_out_deg=8.0, female=True,
)
FACE = dict(female=True, width=0.96, jaw=0.95, chin=1.02, cheek=1.15, brow=0.75, nose_len=1.0, nose_w=0.9,
            nose_proj=1.0, lips=1.0, mouth_w=0.98, skull=0.96)
NECK_R = (0.050, 0.043)
BONE_GARMENTS = dict(waist_z=1.05, skirt_hem_z=0.80, cape_top_z=1.42, cape_hem_z=1.15,
                     bag=((0.20, -0.02, 1.00), (0.21, -0.03, 0.82)))


def body_parts(J, L):
    P = []
    P.append(K.torso([
        (0.80, 0.180, (0.112, 0.125), 2.2), (0.90, 0.170, (0.105, 0.115), 2.3), (1.00, 0.150, (0.098, 0.100), 2.3),
        (1.10, 0.145, (0.100, 0.095), 2.4), (1.22, 0.158, (0.110, 0.098), 2.4), (1.32, 0.166, (0.106, 0.100), 2.5),
        (1.37, 0.160, (0.096, 0.094), 2.5), (1.41, 0.120, (0.078, 0.078), 2.3), (1.455, 0.062, (0.054, 0.052), 2.0)],
        cls="tunic", disp=K.folds_disp(0.003, (24.0, 9.0), seed=8)))
    for S_, sx in (("Left", 1), ("Right", -1)):
        P += K.shoulders(J, S_, sx, r=(0.058, 0.056, 0.062), cls="tunic", off=0.010)
        P.append(K.upper_arm(J, S_, [(0.0, 0.062), (0.5, 0.057), (1.0, 0.052)], cls="tunic"))
        P.append(K.forearm(J, S_, [(0.0, 0.050, 0.047), (0.3, 0.052, 0.047), (0.75, 0.045, 0.040), (1.0, 0.035, 0.030)],
                           cls="tunic"))
        # leather bracers over the forearms (wrist to 2/3 up)
        P.append(H.limb(J[f"{S_}LowerArm"], J[f"{S_}Hand"], [(0.30, 0.056, 0.052), (0.65, 0.051, 0.047),
                                                           (0.95, 0.043, 0.039)], cls="leather", bone=f"{S_}LowerArm",
                        k=0.004, name=f"bracer_{S_}"))
        P.append(K.thigh(J, S_, [(0.0, 0.106, 0.110), (0.5, 0.093, 0.096), (1.0, 0.078, 0.080)]))
        P.append(K.shin(J, S_, [(0.0, 0.077, 0.079), (0.4, 0.071, 0.073), (1.0, 0.058, 0.060)]))
        P += K.boot(J, S_, sx, L, top_z=0.40, cls="boot", shaft_r=(0.063, 0.065), width=1.08, height=1.15,
                    shaft_flare=1.12, cuff=0.011, round_toe=1.12)
    return P


def head_extras(ctx):
    lm = ctx.lm
    s = lm["scale"]
    reg = G.hair_region(lm, front=0.074, temple_drop=0.20, side=-0.010, back=-0.050, noise=0.003, seed=4)
    out = [K.hair_shell(ctx, thick=0.016, region=reg, top_extra=0.004, taper=0.004)]
    out.append(K.bun(ctx, offset=(0.0, 0.155, 0.050), radii=(0.048, 0.040, 0.046)))
    locks = [[(0.055, 0.010, 0.050), (0.068, 0.020, -0.010), (0.066, 0.030, -0.060)],
             [(-0.055, 0.010, 0.050), (-0.070, 0.022, -0.010), (-0.068, 0.034, -0.070)],
             [(0.020, -0.020, 0.090), (0.045, -0.015, 0.060), (0.058, 0.0, 0.020)]]
    out += K.strands(ctx, locks, r0=0.007, r1=0.004)
    return out


def garments(ctx):
    J = ctx.J
    cxy = ctx.center
    out = []
    ax = lambda c: np.array([cxy[0], cxy[1], c[2]])
    # short cape (open at the front below the brooch)
    def hem(th):
        a = np.abs(th)
        return 1.165 - 0.035 * np.clip((a - 2.2) / 0.9, 0, 1)

    def region(th, z):
        return np.abs(th) > (0.10 + 0.55 * np.clip((1.405 - z) / 0.25, 0, 1))
    D = C.drape(ctx.body_fn, cxy, (-math.pi, math.pi), lambda th: np.full_like(th, 1.425), hem, nu=48, nv=12,
                closed=True, clearance=0.018, slack=0.30, flare=0.07, folds=[(12, 0.007, 0.0), (19, 0.003, 0.7)],
                ragged=0.004, seed=9, region=region, fit=(ctx.hull_fn, 1.17, 1.38, 0, 0.30), part="cape")
    out.append(G.piece_from_drape("cape", D, "cloak", 0.005, {"type": "cape", "top_z": 1.42, "hem_z": 1.14}, ax))
    # emerald trim band along the hem
    th = np.linspace(-math.pi, math.pi, 48, endpoint=False)
    mask = np.abs(th) > 0.62
    Vh = D["verts"][-2]
    Nn = Vh - np.array([cxy[0], cxy[1], 0])
    Nn[:, 2] = 0
    Pt, Nt = Vh[mask], Nn[mask]
    out.append(G.band_piece("cape_trim", Pt, Nt, 0.026, 0.003, "armband", {"type": "cape", "top_z": 1.42,
                                                                            "hem_z": 1.14}, lift=0.006))
    # hood lying on the upper back
    O = np.array([0.0, 0.105, 1.36])

    def outer(P):
        return fsdf.ellipsoid(O, (0.135, 0.050, 0.095)).fn(P)

    def inner(P):
        return fsdf.ellipsoid(O + np.array([0, -0.012, 0.015]), (0.115, 0.036, 0.075)).fn(P)
    hood = K.headwear_piece("hood_down", ctx, outer, inner, O - 0.16, O + 0.16, "cloak",
                            {"type": "blend", "bones": {"UpperChest": 0.6, "Cape1": 0.4}})
    out.append(hood)
    # brooch at the throat
    bp = C.surface_point(ctx.body_fn, np.array([-0.02, 0.0, 1.415]), np.array([0, -1.0, 0]), clearance=0.022)
    out.append(G.lathe_piece("brooch", [(0.0, 0.0), (0.014, 0.0), (0.016, 0.004), (0.010, 0.007), (0.0, 0.007)],
                             bp, (0, -1.0, 0), "brass", {"type": "rigid", "bone": "UpperChest"}, sides=12))
    # belts
    out += PR.belt("belt", ctx.torso_fn, cxy, 1.045, width=0.036, cls="leather", clearance=0.006)
    out += PR.belt("hip_belt", ctx.torso_fn, cxy, 0.965, width=0.026, cls="leather", clearance=0.012, tilt=-0.02,
                   buckle_theta=-0.5)
    # satchel on the LEFT hip, strap from the right shoulder across the chest and back
    sc = C.surface_point(ctx.torso_fn, np.array([0.17, -0.02, 0.89]), np.array([0.6, -0.8, 0]), clearance=0.04)
    out.append(PR.pouch("satchel", sc, (0.17, 0.065, 0.15), (0.6, -0.8, 0.0), cls="leather",
                        rule={"type": "rigid", "bone": "Bag"}))
    th = np.concatenate([np.linspace(0.70, -0.45, 16), np.linspace(-0.6, -2.5, 6), np.linspace(-2.7, -3.9, 16)])
    zs = np.concatenate([np.linspace(0.98, 1.43, 16), np.full(6, 1.455), np.linspace(1.43, 0.98, 16)])
    P_, N_ = G.curve_on_body(ctx.body_fn, cxy, th, zs, clearance=0.012)
    out.append(G.band_piece("satchel_strap", P_, N_, 0.030, 0.004, "leather", {"type": "body"}))
    # right-hip pouch
    pc = C.surface_point(ctx.torso_fn, np.array([-0.15, -0.02, 0.90]), np.array([-0.7, -0.7, 0]), clearance=0.03)
    out.append(PR.pouch("pouch", pc, (0.08, 0.04, 0.10), (-0.7, -0.7, 0.0), cls="leather",
                        rule={"type": "rigid", "bone": "Hips"}))
    # boot laces
    for S_ in ("Left", "Right"):
        out.append(G.laces_piece(f"laces_{S_}", ctx.body_fn, J, S_, 0.12, 0.36, n=7, half=0.020))
    return out
