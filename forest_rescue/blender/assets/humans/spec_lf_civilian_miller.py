"""MILLER — stocky man ~40, curly dark-brown hair, full dark beard, russet rolled-sleeve shirt,
flour-stained canvas apron (bib + wide skirt wrapping to the sides, ties in a bow at the back),
hanging canvas pouch at the front-right waist, emerald armband on the LEFT upper arm, baggy brown
trousers bloused over worn leather boots.  Sheet: civilian_survivors (cell 1)."""
import numpy as np

import humans_sdf as H

ASSET = "lf_civilian_miller"
GROUP = "civilian"

# landmarks read from the world-grid resampled front panel (metres; +x = character's left)
L = dict(
    crown=1.750, top=1.80, eye=1.630, mouth=1.552, chin=1.510, neck=1.452,
    shoulder_l=(0.205, 1.400), shoulder_r=(-0.205, 1.400),
    elbow_l=(0.345, 1.130), elbow_r=(-0.330, 1.130),
    wrist_l=(0.352, 0.925), wrist_r=(-0.342, 0.925),
    hip_l=(0.098, 0.905), hip_r=(-0.098, 0.905),
    knee_l=(0.128, 0.480), knee_r=(-0.128, 0.480),
    ankle_l=(0.168, 0.085), ankle_r=(-0.162, 0.085),
    hand_len=0.090, hand_scale=1.06, foot_len=0.27, toe_out_deg=9.0,
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
        (1.36, (0.200, 0.200), (0.112, 0.112), 2.5),
        (1.42, (0.170, 0.170), (0.090, 0.090), 2.4),
        (1.465, (0.090, 0.090), (0.065, 0.060), 2.0),
    ]
    P.append(H.vloft(0.60, 1.465, [(z, w, d, n) for z, w, d, n in torso], cls="shirt", bone=None, k=0.0,
                     name="torso", y=0.012))
    # shoulders / deltoids under the sleeves
    for S_, sx in (("Left", 1), ("Right", -1)):
        sh = J[f"{S_}UpperArm"]
        P.append(H.ellipsoid(sh + np.array([sx * 0.012, 0.0, 0.0]), (0.080, 0.075, 0.082), cls="shirt",
                             bone=f"{S_}UpperArm", k=0.05))
        P.append(H.capsule(J[f"{S_}Shoulder"] + np.array([0, 0.02, 0.01]), sh + np.array([0, 0.02, 0.03]), 0.055,
                           0.060, cls="shirt", bone=f"{S_}Shoulder", k=0.05))
        el = J[f"{S_}LowerArm"]
        wr = J[f"{S_}Hand"]
        # loose sleeve (upper arm)
        P.append(H.limb(sh, el, [(0.0, 0.072), (0.5, 0.068), (0.85, 0.064), (1.0, 0.060)], cls="shirt",
                        bone=f"{S_}UpperArm", k=0.03, name=f"sleeve_{S_}"))
        # rolled cuff just above the elbow
        ax = (el - sh) / np.linalg.norm(el - sh)
        P.append(H.torus(sh + (el - sh) * 0.86, 0.052, 0.024, axis=ax, cls="shirt", bone=f"{S_}UpperArm", k=0.01))
        P.append(H.torus(sh + (el - sh) * 0.95, 0.050, 0.022, axis=ax, cls="shirt", bone=f"{S_}LowerArm", k=0.01))
        # forearm (skin, muscular)
        P.append(H.limb(el, wr, [(0.0, 0.050, 0.046), (0.25, 0.052, 0.047), (0.70, 0.040, 0.034),
                                 (1.0, 0.032, 0.026)], cls="skin", bone=f"{S_}LowerArm", k=0.02,
                        name=f"forearm_{S_}"))
        # legs: baggy trousers bloused above the boots
        hp = J[f"{S_}UpperLeg"]
        kn = J[f"{S_}LowerLeg"]
        an = J[f"{S_}Foot"]
        P.append(H.limb(hp + np.array([0, 0, 0.04]), kn, [(0.0, 0.112, 0.118), (0.4, 0.100, 0.105),
                                                         (1.0, 0.082, 0.085)], cls="trousers",
                        bone=f"{S_}UpperLeg", k=0.04, name=f"thigh_{S_}"))
        P.append(H.limb(kn, an, [(0.0, 0.080, 0.084), (0.35, 0.084, 0.088), (0.62, 0.086, 0.090),
                                 (0.76, 0.072, 0.076), (1.0, 0.050, 0.055)], cls="trousers",
                        bone=f"{S_}LowerLeg", k=0.03, name=f"shin_{S_}"))
        P += H.boot_parts(J, S_, sx, L, top_z=0.225, cls="boot", shaft_r=(0.062, 0.060), width=1.05,
                          shaft_flare=1.08, cuff=0.010)
    return P
