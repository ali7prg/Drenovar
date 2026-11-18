"""CAPTAIN — mature woman, short dark hair; long russet tabard (gold tree emblem on the chest,
worn hem to mid-shin) over riveted mail (mail sleeves to the elbow, mail skirt showing at the
sides), dark leather jerkin with shoulder pieces and a high collar, leather bracers, layered
belts with a buckle at the front, sword in a scabbard at the LEFT hip; dark trousers, tall laced
boots.  Sheet: 04_expedition_squad_turnaround (figures 1-2)."""
import math

import numpy as np

import humans_cloth as C
import humans_geo as G
import humans_kit as K
import humans_props as PR
import humans_sdf as H

ASSET = "lf_squad_captain"
GROUP = "soldier"
ROLE = "captain"
CLASS_GROUP = {"tabard": "garment"}
BUDGET = {"head": 2500}
FACE_PAINT = {"lip_tint": (1.03, 0.9, 0.88), "brow_thick": 0.003, "iris": (0.25, 0.18, 0.12)}

L = dict(
    crown=1.745, top=1.79, eye=1.640, mouth=1.570, chin=1.533, neck=1.478,
    shoulder_l=(0.175, 1.430), shoulder_r=(-0.175, 1.430),
    elbow_l=(0.262, 1.155), elbow_r=(-0.262, 1.155),
    wrist_l=(0.305, 0.920), wrist_r=(-0.305, 0.920),
    hip_l=(0.088, 0.890), hip_r=(-0.088, 0.890),
    knee_l=(0.092, 0.480), knee_r=(-0.092, 0.480),
    ankle_l=(0.108, 0.080), ankle_r=(-0.108, 0.080),
    hand_len=0.088, hand_scale=0.95, foot_len=0.25, toe_out_deg=6.0, female=True,
)
FACE = dict(female=True, width=0.98, jaw=1.0, chin=1.02, cheek=1.15, brow=0.95, nose_len=1.05, nose_w=0.95,
            nose_proj=1.05, lips=0.9, mouth_w=0.98, gaunt=0.25, skull=0.98, eye_depth=1.05)
NECK_R = (0.052, 0.045)
BONE_GARMENTS = dict(waist_z=1.06, skirt_hem_z=0.36, front_y=-0.15, back_y=0.15, side_x=0.19)


def body_parts(J, L):
    P = []
    P.append(K.torso([
        (0.70, 0.190, (0.118, 0.128), 2.2), (0.82, 0.176, (0.112, 0.118), 2.3), (0.94, 0.165, (0.108, 0.108), 2.3),
        (1.05, 0.158, (0.110, 0.102), 2.4), (1.16, 0.168, (0.120, 0.104), 2.4), (1.28, 0.180, (0.120, 0.108), 2.5),
        (1.38, 0.186, (0.112, 0.108), 2.5), (1.43, 0.165, (0.096, 0.094), 2.4), (1.465, 0.105, (0.074, 0.072), 2.2),
        (1.51, 0.066, (0.060, 0.058), 2.0)], cls="leather"))
    # high leather collar
    P.append(H.tag(H.vloft(1.45, 1.52, [(1.45, 0.075, 0.068), (1.52, 0.064, 0.060)], y=0.012), cls="leather",
                   bone="UpperChest", k=0.01, name="collar"))
    for S_, sx in (("Left", 1), ("Right", -1)):
        sh = J[f"{S_}UpperArm"]
        # leather shoulder pieces
        P.append(H.ellipsoid(sh + np.array([sx * 0.025, 0.0, 0.010]), (0.088, 0.082, 0.070), cls="leather",
                             bone=f"{S_}UpperArm", k=0.03))
        P += K.shoulders(J, S_, sx, r=(0.072, 0.070, 0.076), cls="chainmail", off=0.014)
        P.append(K.upper_arm(J, S_, [(0.0, 0.066), (0.6, 0.060), (0.9, 0.056), (1.0, 0.052)], cls="chainmail"))
        P.append(K.forearm(J, S_, [(0.0, 0.048, 0.044), (0.25, 0.050, 0.045), (0.7, 0.042, 0.037), (1.0, 0.034, 0.029)],
                           cls="leather_dark"))
        P.append(H.limb(J[f"{S_}LowerArm"], J[f"{S_}Hand"], [(0.30, 0.054, 0.050), (0.65, 0.050, 0.046),
                                                           (0.96, 0.044, 0.040)], cls="leather", bone=f"{S_}LowerArm",
                        k=0.004, name=f"bracer_{S_}"))
        P.append(K.thigh(J, S_, [(0.0, 0.096, 0.100), (0.5, 0.084, 0.088), (1.0, 0.068, 0.070)], cls="trousers"))
        P.append(K.shin(J, S_, [(0.0, 0.066, 0.068), (0.4, 0.062, 0.064), (1.0, 0.048, 0.052)], cls="trousers"))
        P += K.boot(J, S_, sx, L, top_z=0.36, cls="boot", shaft_r=(0.056, 0.058), width=1.0, height=1.1,
                    shaft_flare=1.10, cuff=0.009, round_toe=1.1)
    return P


def head_extras(ctx):
    lm = ctx.lm
    s = lm["scale"]
    reg = G.hair_region(lm, front=0.078, temple_drop=0.14, side=-0.045, back=-0.085, noise=0.004, seed=12)
    out = [K.hair_shell(ctx, thick=0.020, region=reg, top_extra=0.004, back_extra=0.010, taper=0.004)]
    locks = []
    for sx in (1, -1):
        for k in range(4):
            locks.append([(sx * (0.050 + 0.008 * k), -0.005 + 0.025 * k, 0.090 - 0.010 * k),
                          (sx * (0.076 + 0.004 * k), 0.010 + 0.025 * k, 0.010),
                          (sx * (0.078 + 0.004 * k), 0.030 + 0.022 * k, -0.060)])
    out += K.strands(ctx, locks, r0=0.012, r1=0.008)
    return out


def garments(ctx):
    J = ctx.J
    cxy = ctx.center
    out = []
    ax = lambda c: np.array([cxy[0], cxy[1], c[2]])
    # mail skirt (all around, to the knees)
    D = C.drape(ctx.torso_fn, cxy, (-math.pi, math.pi), lambda th: np.full_like(th, 1.05),
                lambda th: np.full_like(th, 0.43), nu=40, nv=12, closed=True, clearance=0.008, slack=0.05, flare=0.05,
                folds=[(12, 0.003, 0.0)], part="mail_skirt")
    out.append(G.piece_from_drape("mail_skirt", D, "chainmail", 0.004,
                                  {"type": "skirt", "top_z": 1.05, "hem_z": 0.43, "follow": 0.7}, ax))
    # tabard: front + back panels from the shoulders to the hem (z~0.36), sides open
    for side, (t0, t1) in (("front", (-0.95, 0.95)), ("back", (math.pi - 0.95, math.pi + 0.95))):
        def top(th):
            return np.full_like(th, 1.465)

        def hem(th, side=side):
            return np.full_like(th, 0.36 if side == "front" else 0.375)

        def taper(z):
            w = np.interp(z, [0.36, 1.10, 1.30, 1.46], [0.82, 0.78, 0.74, 0.50])
            return (-w, w) if side == "front" else (math.pi - w, math.pi + w)
        Dt = C.drape(ctx.body_fn, cxy, (t0, t1), top, hem, nu=16, nv=22, clearance=0.020, slack=0.03, flare=0.0,
                     folds=[(9, 0.004, 0.4)], ragged=0.004, seed=5, taper=taper, part="tabard")
        out.append(G.piece_from_drape(f"tabard_{side}", Dt, "tabard", 0.005,
                                      {"type": "skirt", "top_z": 1.06, "hem_z": 0.36, "follow": 0.5}, ax))
    # belts: waist belt with buckle + lower sword belt slanting toward the left hip
    out += PR.belt("belt", ctx.body_fn, cxy, 1.075, width=0.040, cls="leather_dark", clearance=0.026,
                   buckle_cls="metal")
    out += PR.belt("sword_belt", ctx.body_fn, cxy, 1.02, width=0.030, cls="leather_dark", clearance=0.030,
                   tilt=0.0, buckle_theta=0.0, buckle_cls="metal")
    # sword in scabbard at the LEFT hip: hilt up at (0.14, 1.10), scabbard tip at (0.30, 0.30)
    hilt = np.array([0.135, -0.075, 1.075])
    tip = np.array([0.300, -0.010, 0.300])
    yv = (hilt - tip) / np.linalg.norm(hilt - tip)
    M = PR.frame(hilt, np.cross(yv, (0, -1.0, 0)), yv)
    rule = {"type": "rigid", "bone": "Hips"}
    sc = PR.scabbard(rule, length=0.80)
    sc = PR.place(sc, M)
    out.append(sc)
    sw = PR.sword(rule, blade_len=0.74)
    # sheathed: blade inside the scabbard (flip so the blade points down along -Y)
    Mflip = M @ np.diag([1.0, -1.0, -1.0, 1.0])
    Mflip[:3, 3] = hilt + yv * 0.07
    sw = PR.sword({"type": "rigid", "bone": "RightProp"}, blade_len=0.74)
    sw = PR.place(sw, Mflip)
    sw.name = "sword"
    sw.meta["prop"] = {"bone": "RightProp", "carry_bone": "Hips", "carry_place": Mflip,
                       "hand_place": PR.bone_frame(ctx.B, "RightProp", roll_up=(0, 0, 1.0)),
                       "held": ["lf_soldier_guard", "lf_soldier_attack", "lf_soldier_hit", "lf_soldier_death"]}
    out.append(sw)
    return out
