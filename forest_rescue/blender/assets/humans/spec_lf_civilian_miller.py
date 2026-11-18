"""MILLER — stocky man ~40, curly dark-brown hair, full dark beard, russet rolled-sleeve shirt,
flour-stained canvas apron (bib + wide skirt wrapping to the sides, ties in a bow at the back),
hanging canvas pouch at the front-right waist, emerald armband on the LEFT upper arm, baggy brown
trousers bloused over worn leather boots.  Sheet: civilian_survivors (cell 1)."""
import numpy as np

import humans_sdf as H

ASSET = "lf_civilian_miller"
GROUP = "civilian"
CLASS_GROUP = {"shirt": "garment"}
BUDGET = {"head": 2500}
FACE_PAINT = {"lip_tint": (1.05, 0.9, 0.88)}

# landmarks read from the world-grid resampled front panel (metres; +x = character's left)
L = dict(
    crown=1.750, top=1.80, eye=1.630, mouth=1.552, chin=1.510, neck=1.452,
    shoulder_l=(0.205, 1.400), shoulder_r=(-0.205, 1.400),
    elbow_l=(0.345, 1.130), elbow_r=(-0.330, 1.130),
    wrist_l=(0.352, 0.925), wrist_r=(-0.342, 0.925),
    hip_l=(0.098, 0.905), hip_r=(-0.098, 0.905),
    knee_l=(0.128, 0.480), knee_r=(-0.128, 0.480),
    ankle_l=(0.168, 0.085), ankle_r=(-0.162, 0.085),
    hand_len=0.092, hand_scale=1.12, foot_len=0.27, toe_out_deg=9.0,
    female=False,
)

FACE = dict(width=1.06, jaw=1.10, chin=0.95, cheek=0.85, cheek_z=-0.004, brow=1.05, nose_len=0.95,
            nose_w=1.25, nose_proj=0.95, nose_tip=1.25, lips=1.1, mouth_w=1.05, fat=0.6, skull=1.04,
            eye_sep=1.02)


def body_parts(J, L):
    s = 1.0
    P = []
    # torso + long shirt (shirt tail reaches mid-thigh at the back, z~0.64)
    torso = [
        (0.60, (0.205, 0.205), (0.125, 0.150), 2.2),
        (0.70, (0.205, 0.205), (0.120, 0.140), 2.2),
        (0.82, (0.195, 0.195), (0.120, 0.125), 2.3),
        (0.92, (0.185, 0.185), (0.125, 0.118), 2.3),
        (1.04, (0.185, 0.185), (0.135, 0.110), 2.3),
        (1.16, (0.192, 0.192), (0.135, 0.110), 2.4),
        (1.28, (0.200, 0.200), (0.125, 0.115), 2.5),
        (1.35, (0.198, 0.198), (0.112, 0.112), 2.5),
        (1.40, (0.165, 0.165), (0.095, 0.095), 2.4),
        (1.435, (0.115, 0.115), (0.075, 0.075), 2.2),
        (1.465, (0.075, 0.075), (0.060, 0.058), 2.0),
    ]
    P.append(H.vloft(0.60, 1.465, [(z, w, d, n) for z, w, d, n in torso], cls="shirt", bone=None, k=0.0,
                     name="torso", y=0.012))
    # shoulders / deltoids under the sleeves
    for S_, sx in (("Left", 1), ("Right", -1)):
        sh = J[f"{S_}UpperArm"]
        P.append(H.ellipsoid(sh + np.array([sx * 0.020, 0.0, -0.010]), (0.092, 0.085, 0.092), cls="shirt",
                             bone=f"{S_}UpperArm", k=0.05))
        P.append(H.capsule(J[f"{S_}Shoulder"] + np.array([0, 0.02, 0.01]), sh + np.array([0, 0.02, 0.03]), 0.055,
                           0.060, cls="shirt", bone=f"{S_}Shoulder", k=0.05))
        el = J[f"{S_}LowerArm"]
        wr = J[f"{S_}Hand"]
        # loose sleeve (upper arm)
        P.append(H.limb(sh, el, [(0.0, 0.088), (0.45, 0.084), (0.80, 0.076), (1.0, 0.066)], cls="shirt",
                        bone=f"{S_}UpperArm", k=0.03, name=f"sleeve_{S_}"))
        # rolled cuff just above the elbow
        ax = (el - sh) / np.linalg.norm(el - sh)
        P.append(H.torus(sh + (el - sh) * 0.84, 0.060, 0.030, axis=ax, cls="shirt", bone=f"{S_}UpperArm", k=0.012))
        P.append(H.torus(sh + (el - sh) * 0.97, 0.056, 0.027, axis=ax, cls="shirt", bone=f"{S_}LowerArm", k=0.012))
        # forearm (skin, muscular)
        P.append(H.limb(el, wr, [(0.0, 0.056, 0.050), (0.25, 0.058, 0.052), (0.70, 0.045, 0.038),
                                 (1.0, 0.036, 0.029)], cls="skin", bone=f"{S_}LowerArm", k=0.02,
                        name=f"forearm_{S_}"))
        # legs: baggy trousers bloused above the boots
        hp = J[f"{S_}UpperLeg"]
        kn = J[f"{S_}LowerLeg"]
        an = J[f"{S_}Foot"]
        P.append(H.limb(hp + np.array([0, 0, 0.04]), kn, [(0.0, 0.112, 0.118), (0.4, 0.100, 0.105),
                                                         (1.0, 0.082, 0.085)], cls="trousers",
                        bone=f"{S_}UpperLeg", k=0.04, name=f"thigh_{S_}"))
        P.append(H.limb(kn, an, [(0.0, 0.088, 0.090), (0.35, 0.096, 0.098), (0.60, 0.100, 0.102),
                                 (0.74, 0.084, 0.088), (1.0, 0.058, 0.062)], cls="trousers",
                        bone=f"{S_}LowerLeg", k=0.03, name=f"shin_{S_}"))
        P += H.boot_parts(J, S_, sx, L, top_z=0.225, cls="boot", shaft_r=(0.068, 0.066), width=1.18,
                          shaft_flare=1.10, cuff=0.012, height=1.30)
    return P


# ----------------------------------------------------------------------------- garments
def garments(ctx):
    import humans_cloth as C
    import humans_geo as G
    from frlib import sdf as fsdf
    J, L, s = ctx.J, ctx.L, 1.0
    cxy = ctx.center
    out = []

    def axis_center(c):
        return np.array([cxy[0], cxy[1], c[2]])

    # --- apron skirt: wraps front+sides, open at the back (back view: edges at x~+-0.22)
    def zhem(th):
        a = np.minimum(np.abs(th), np.pi / 2)
        return 0.352 + 0.112 * np.sin(a) ** 2 - 0.055 * np.clip((np.abs(th) - np.pi / 2) / 0.75, 0, 1)

    D = C.drape(ctx.torso_fn, cxy, (-2.28, 2.28), lambda th: np.full_like(th, 1.112), zhem, nu=30, nv=18,
                clearance=0.013, slack=0.06, flare=0.085, flare_pow=1.6,
                folds=[(9, 0.0055, 0.4), (15, 0.0025, 1.3)], ragged=0.006, seed=3,
                fit=(ctx.hull_fn, 0.40, 1.02, 0, 0.30), part="apron")
    out.append(G.piece_from_drape("apron_skirt", D, "apron", 0.0045,
                                  {"type": "skirt", "top_z": 1.11, "hem_z": 0.35, "follow": 0.55}, axis_center))
    # --- bib (front, chest to waist), narrowing toward the top
    def bib_taper(z):
        w = np.interp(z, [1.08, 1.20, 1.40], [0.98, 0.80, 0.56])
        return (-w, w)
    Db = C.drape(ctx.torso_fn, cxy, (-1.0, 1.0), lambda th: np.full_like(th, 1.405), lambda th: np.full_like(th, 1.085),
                 nu=14, nv=12, clearance=0.009, slack=0.25, folds=[(7, 0.002, 0.0)], taper=bib_taper, part="bib")
    out.append(G.piece_from_drape("apron_bib", Db, "apron", 0.004, {"type": "body"}, axis_center))
    # --- neck strap: bib corners -> over the trapezius -> around the back of the neck
    half_t = np.array([0.55, 0.68, 0.85, 1.05, 1.30, 1.60, 1.95, 2.35, 2.75, 3.14159])
    half_z = np.array([1.400, 1.425, 1.448, 1.462, 1.472, 1.478, 1.481, 1.483, 1.484, 1.485])
    th = np.concatenate([-half_t, half_t[::-1][1:]])
    zz = np.concatenate([half_z, half_z[::-1][1:]])
    P, N = G.curve_on_body(ctx.body_fn, cxy, th, zz, clearance=0.006)
    out.append(G.band_piece("apron_strap", P, N, 0.024, 0.003, "apron", {"type": "body"}))
    # --- waist tie (closed ring) + bow and tails at the back
    th = np.linspace(-np.pi, np.pi, 40, endpoint=False)
    P, N = G.curve_on_body(ctx.torso_fn, cxy, th, np.full_like(th, 1.112), clearance=0.017)
    out.append(G.band_piece("apron_tie", P, N, 0.028, 0.003, "apron", {"type": "body"}, closed=True))
    back = G.surface_point_body = None
    bc = C.surface_point(ctx.torso_fn, np.array([0, 0.02, 1.095]), np.array([0, 1.0, 0]), clearance=0.02)
    for sx in (1, -1):
        loop = [bc + np.array([sx * dx, 0.012 + 0.010 * np.sin(np.pi * dx / 0.075), dz]) for dx, dz in
                zip(np.linspace(0.0, 0.075, 7), 0.02 * np.sin(np.linspace(0, np.pi, 7)))]
        loop += [bc + np.array([sx * dx, 0.012, -0.012 * np.sin(np.pi * dx / 0.075)]) for dx in np.linspace(0.07, 0.0, 6)]
        out.append(G.tube_piece(f"apron_bow_{sx}", np.array(loop), 0.010, "apron", {"type": "body"}, sides=6))
    for sx, (dx, zend) in ((1, (0.020, 0.74)), (-1, (0.040, 0.72))):
        zs = np.linspace(1.085, zend, 12)
        ths = np.pi - sx * np.linspace(0.02, dx * 4.0, 12)
        P, N = G.curve_on_body(ctx.torso_fn, cxy, ths, zs, clearance=0.020)
        out.append(G.band_piece(f"apron_tail_{sx}", P, N, 0.030, 0.003, "apron",
                                {"type": "skirt", "top_z": 1.09, "hem_z": 0.72, "follow": 0.4}))
    # --- hanging canvas pouch at the front-right waist
    top = C.surface_point(ctx.torso_fn, np.array([-0.115, 0.0, 0.975]), np.array([0, -1.0, 0]), clearance=0.025)
    R = G.rot_from((1.0, 0.0, 0.12), (0, -1.0, 0.0))
    out.append(G.box_piece("pouch", top + np.array([0, -0.030, -0.080]), (0.095, 0.048, 0.150), R, "canvas",
                           {"type": "rigid", "bone": "Bag"}, bevel=0.55, segs=2))
    st = np.array([top + np.array([0.004, -0.010, 0.14]), top + np.array([0.004, -0.020, 0.06]),
                   top + np.array([0.0, -0.028, 0.0])])
    out.append(G.tube_piece("pouch_cord", st, 0.006, "canvas", {"type": "rigid", "bone": "Bag"}, sides=6))
    tie = np.array([top + np.array([0.02, -0.036, -0.150]), top + np.array([0.026, -0.040, -0.20]),
                    top + np.array([0.020, -0.038, -0.255])])
    out.append(G.tube_piece("pouch_tie", tie, 0.007, "canvas", {"type": "rigid", "bone": "Bag"}, sides=6))
    # --- emerald armband, LEFT upper arm
    P, N = G.ring_on_limb(ctx.body_fn, J["LeftUpperArm"], J["LeftLowerArm"], 0.50, n=20, clearance=0.003)
    out.append(G.band_piece("armband", P, N, 0.060, 0.004, "armband", {"type": "rigid", "bone": "LeftUpperArm"},
                            closed=True, segs_w=2))
    return out


def head_extras(ctx):
    """Curly dark hair + full beard, both merged into the head mesh (tapered, seamless)."""
    import humans_geo as G
    import humans_kit as K
    lm = ctx.lm
    s = lm["scale"]
    reg = G.hair_region(lm, front=0.066, temple_drop=0.25, side=0.000, back=-0.072, noise=0.004, seed=5)
    out = [K.hair_shell(ctx, thick=0.016, region=reg, taper=0.004)]
    cl = G.curls(lm, ctx.head_fn, lambda P: reg(P) + 0.004 * s, 120, 0.007 * s, 0.011 * s, 0.013 * s, seed=11)
    for c in cl:
        c.k = 0.007
    out += cl
    out += K.beard_prims(ctx, thick=0.017, curls=70, seed=21, top=-0.036, slope=0.30, back=0.080, lift=0.012,
                         taper=0.010)
    return out
