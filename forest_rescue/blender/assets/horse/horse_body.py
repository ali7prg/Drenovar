"""Anatomical SDF parts of the guide horse «Искра» (lf_horse_origin) — pure numpy.

World frame (Blender): X = horse's left, -Y = forward, Z = up, metres, hooves on Z = 0.
The rest pose reproduces the turnaround stance: fore legs square, left hind slightly back.

`skeleton()`  -> joint landmarks shared by the SDF parts and the armature.
`body_parts()`-> list of frlib.sdf.Prim (each owns a deform bone for part-based weights).
`hair_proxies()` -> rough mane/tail/forelock volumes used only for silhouette fitting.
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(os.path.dirname(HERE))
if BLENDER_DIR not in sys.path:
    sys.path.insert(0, BLENDER_DIR)

from frlib.sdf import Prim, ellipsoid, round_cone, flat_capsule, sphere  # noqa: E402

V = lambda *a: np.array(a, float)  # noqa: E731


# --------------------------------------------------------------------------- skeleton landmarks

def skeleton():
    """Joint positions (metres).  Side-specific joints get the sign of X (left = +X)."""
    J = {}
    # spine / torso (centre line)
    J["root"] = V(0, 0, 0)
    J["spine_02"] = V(0, -0.30, 1.36)     # thorax / barrel (centre of mass bone)
    J["spine_01"] = V(0, 0.02, 1.40)      # loins
    J["pelvis"] = V(0, 0.30, 1.44)        # sacrum (croup)
    J["tail_head"] = V(0, 0.75, 1.39)
    J["spine_03"] = V(0, -0.52, 1.40)     # withers / chest
    J["neck_01"] = V(0, -0.70, 1.40)
    J["neck_02"] = V(0, -0.84, 1.57)
    J["neck_03"] = V(0, -0.96, 1.72)
    J["head"] = V(0, -1.08, 1.86)         # atlas / poll joint
    J["head_tip"] = V(0, -1.50, 1.44)
    J["jaw"] = V(0, -1.13, 1.71)          # TMJ (behind the eye, below the ear)
    J["jaw_tip"] = V(0, -1.43, 1.37)
    for s, sx in (("L", 1.0), ("R", -1.0)):
        # ears: right ear turned slightly forward (both profiles show one ear ahead)
        ey = -1.195 if s == "L" else -1.245
        J[f"ear_{s}"] = V(0.062 * sx, ey, 1.925)
        J[f"ear_tip_{s}"] = V(0.122 * sx, ey - 0.04, 2.045)
        J[f"eye_{s}"] = V(0.118 * sx, -1.255, 1.75)
        # fore limb: left fore slightly behind the right fore (turnaround stance)
        dy = 0.04 if s == "L" else -0.035
        J[f"scap_top_{s}"] = V(0.115 * sx, -0.38, 1.47)
        J[f"shoulder_{s}"] = V(0.19 * sx, -0.78, 1.08)
        J[f"elbow_{s}"] = V(0.155 * sx, -0.565 + dy, 0.86)
        J[f"knee_{s}"] = V(0.13 * sx, -0.60 + dy, 0.49)
        J[f"fetlock_F_{s}"] = V(0.125 * sx, -0.59 + dy, 0.19)
        J[f"coffin_F_{s}"] = V(0.125 * sx, -0.625 + dy, 0.07)
        J[f"toe_F_{s}"] = V(0.125 * sx, -0.705 + dy, 0.0)
        J[f"heel_F_{s}"] = V(0.125 * sx, -0.555 + dy, 0.0)
    # hind limbs: left hind back (near leg of the left profile), right hind forward
    for s, sx, dy in (("L", 1.0, 0.12), ("R", -1.0, -0.13)):
        J[f"hip_{s}"] = V(0.20 * sx, 0.47, 1.21)
        J[f"stifle_{s}"] = V(0.215 * sx, 0.415 + 0.15 * dy, 0.84)
        J[f"hock_{s}"] = V(0.165 * sx, 0.62 + dy, 0.55)
        J[f"fetlock_H_{s}"] = V(0.160 * sx, 0.585 + dy, 0.19)
        J[f"coffin_H_{s}"] = V(0.160 * sx, 0.55 + dy, 0.07)
        J[f"toe_H_{s}"] = V(0.160 * sx, 0.47 + dy, 0.0)
        J[f"heel_H_{s}"] = V(0.160 * sx, 0.615 + dy, 0.0)
    return J


# --------------------------------------------------------------------------- helpers

def _lerp(a, b, t):
    return a + (b - a) * t


def flat_cone(a, b, ra, rb, flatten, axis=(1, 0, 0), **kw):
    """Round cone squashed along `axis` (lateral by default)."""
    return flat_capsule(a, b, ra, rb, flatten, up=axis, **kw)


def ell(c, r, rot_deg=(0, 0, 0), **kw):
    rot = None if not np.any(rot_deg) else np.radians(rot_deg)
    return ellipsoid(c, r, rot=rot, **kw)


def hoof(coffin, toe, heel, side, bone, scale=1.0):
    """Hoof: slanted, flared wall from the coronet to the ground + sole/heel bulbs."""
    parts = []
    gc = (toe + heel) * 0.5                     # ground centre
    top = coffin + V(0, 0.01, 0.025)
    r_bot = 0.090 * scale
    r_top = 0.068 * scale
    parts.append(flat_cone(gc + V(0, -0.008, 0.024), top, r_bot, r_top, 0.9, axis=(0, 1, 0),
                           bone=bone, name=f"hoof_{side}"))
    parts.append(ell(gc + V(0, -0.012, 0.02), (r_bot * 1.0, r_bot * 1.06, 0.022), bone=bone,
                     name=f"hoof_sole_{side}"))
    return parts


# --------------------------------------------------------------------------- body parts

def body_parts(J=None):
    J = J or skeleton()
    P = []

    def add(p, k=0.0):
        p.k = k
        P.append(p)
        return p

    # ---------------- torso ----------------
    add(ell((0, -0.21, 1.15), (0.352, 0.59, 0.34), bone="spine_02", name="barrel"), 0.0)
    add(ell((0, -0.55, 1.13), (0.265, 0.30, 0.295), bone="spine_03", name="thorax_front"), 0.18)
    add(ell((0, -0.12, 0.995), (0.285, 0.34, 0.18), bone="belly", name="belly"), 0.12)
    for sx in (1, -1):   # pectorals (breast) between the fore legs
        add(ell((0.09 * sx, -0.73, 0.95), (0.11, 0.10, 0.17), bone="spine_03",
                name="pectoral"), 0.15)
    add(ell((0, -0.64, 0.86), (0.13, 0.15, 0.09), bone="spine_03", name="brisket"), 0.12)
    # withers / back / loin top line
    add(round_cone(V(0, -0.64, 1.40), V(0, -0.38, 1.43), 0.145, 0.125, bone="spine_03",
                   name="withers"), 0.10)
    add(round_cone(V(0, -0.36, 1.38), V(0, -0.10, 1.33), 0.115, 0.15, bone="spine_02",
                   name="back"), 0.08)
    add(round_cone(V(0, -0.10, 1.33), V(0, 0.25, 1.38), 0.15, 0.175, bone="spine_01",
                   name="loin"), 0.08)
    # croup and hindquarters (draft "double" rump: two gluteal masses with a groove)
    add(ell((0, 0.40, 1.40), (0.235, 0.31, 0.17), bone="pelvis", name="croup"), 0.16)
    for sx in (1, -1):
        add(ell((0.19 * sx, 0.49, 1.20), (0.175, 0.30, 0.30), bone="pelvis", name="haunch"), 0.16)
        add(ell((0.24 * sx, 0.18, 1.36), (0.06, 0.09, 0.06), bone="pelvis", name="hip_point"), 0.15)
        add(ell((0.22 * sx, 0.16, 1.09), (0.11, 0.19, 0.155), bone="spine_01", name="flank"), 0.15)
    # tail head (dock root)
    add(round_cone(V(0, 0.60, 1.42), J["tail_head"] + V(0, 0.01, -0.01), 0.08, 0.06,
                   bone="tail_01", name="tail_root"), 0.08)

    # ---------------- neck ----------------
    neck = [V(0, -0.64, 1.38), V(0, -0.79, 1.56), V(0, -0.91, 1.71), V(0, -1.02, 1.82),
            V(0, -1.09, 1.87)]
    nr = [0.26, 0.20, 0.16, 0.13, 0.11]
    nf = [0.74, 0.72, 0.74, 0.78, 0.82]
    nb = ["neck_01", "neck_02", "neck_03", "neck_03"]
    for i in range(4):
        add(flat_cone(neck[i], neck[i + 1], nr[i], nr[i + 1], 0.5 * (nf[i] + nf[i + 1]),
                      bone=nb[i], name=f"neck_{i}"), 0.10)
    crest = [V(0, -0.40, 1.50), V(0, -0.58, 1.62), V(0, -0.76, 1.75), V(0, -0.93, 1.85),
             V(0, -1.06, 1.895)]
    cr = [0.10, 0.10, 0.085, 0.07, 0.06]
    cb = ["spine_03", "neck_01", "neck_02", "neck_03"]
    for i in range(4):
        add(flat_cone(crest[i], crest[i + 1], cr[i], cr[i + 1], 0.85, bone=cb[i],
                      name=f"crest_{i}"), 0.10)

    # ---------------- head ----------------
    H = "head"
    add(ell((0, -1.19, 1.845), (0.105, 0.115, 0.10), bone=H, name="cranium"), 0.06)
    # forehead + face (nasal bones): front plane from between the eyes down to the nose
    add(flat_cone(V(0, -1.265, 1.84), V(0, -1.31, 1.70), 0.088, 0.09, 0.95, bone=H,
                  name="forehead"), 0.05)
    add(flat_cone(V(0, -1.29, 1.76), V(0, -1.425, 1.55), 0.095, 0.07, 0.85, bone=H,
                  name="face"), 0.06)
    for sx in (1, -1):
        # cheeks / jowls (masseter over the mandible ramus)
        add(ell((0.068 * sx, -1.16, 1.65), (0.06, 0.115, 0.12), (-30, 0, 0), bone="jaw",
                name="jowl"), 0.06)
        add(ell((0.11 * sx, -1.255, 1.75), (0.032, 0.035, 0.028), bone=H, name="eye_bulge"), 0.025)
        add(ell((0.10 * sx, -1.245, 1.78), (0.03, 0.05, 0.02), (20, 0, 0), bone=H,
                name="brow"), 0.03)
        add(flat_cone(V(0.088 * sx, -1.24, 1.71), V(0.075 * sx, -1.33, 1.62), 0.03, 0.022, 0.8,
                      bone=H, name="face_crest"), 0.04)
    # lower jaw
    add(flat_cone(V(0, -1.15, 1.61), V(0, -1.40, 1.42), 0.085, 0.045, 0.85, bone="jaw",
                  name="mandible"), 0.06)
    # muzzle, nostrils, lips, chin
    add(ell((0, -1.44, 1.47), (0.08, 0.078, 0.088), (-28, 0, 0), bone=H, name="muzzle"), 0.06)
    for sx in (1, -1):
        add(ell((0.046 * sx, -1.48, 1.51), (0.033, 0.034, 0.04), (-28, 0, 0), bone=H,
                name="nostril_wing"), 0.03)
    add(ell((0, -1.46, 1.425), (0.064, 0.055, 0.042), (-15, 0, 0), bone=H, name="upper_lip"), 0.04)
    add(ell((0, -1.43, 1.385), (0.053, 0.052, 0.03), (-10, 0, 0), bone="jaw", name="lower_lip"), 0.03)
    add(ell((0, -1.385, 1.39), (0.046, 0.058, 0.034), bone="jaw", name="chin"), 0.03)

    # ---------------- fore limbs ----------------
    for s, sx in (("L", 1), ("R", -1)):
        sc, sh, el = J[f"scap_top_{s}"], J[f"shoulder_{s}"], J[f"elbow_{s}"]
        kn, fe, co = J[f"knee_{s}"], J[f"fetlock_F_{s}"], J[f"coffin_F_{s}"]
        # shoulder blade muscle slab (broad, gently convex)
        add(flat_cone(sc + V(0.02 * sx, -0.02, -0.03), sh + V(0.0, 0.05, 0.04), 0.135, 0.12, 0.6,
                      bone=f"scapula_{s}", name="shoulder"), 0.15)
        # upper arm (humerus) + triceps mass above the elbow
        add(round_cone(sh + V(0, -0.02, 0.0), el + V(0, -0.02, 0.03), 0.085, 0.08,
                       bone=f"humerus_{s}", name="upper_arm"), 0.15)
        add(ell(_lerp(sh, el, 0.62) + V(-0.01 * sx, 0.08, 0.03), (0.08, 0.14, 0.15), (-25, 0, 0),
                bone=f"humerus_{s}", name="triceps"), 0.16)
        # forearm (muscular top tapering to the knee)
        add(round_cone(el + V(0, -0.02, -0.02), kn + V(0, 0.0, 0.03), 0.095, 0.062,
                       bone=f"forearm_{s}", name="forearm"), 0.06)
        add(ell(el + V(-0.01 * sx, -0.06, -0.09), (0.08, 0.085, 0.17), bone=f"forearm_{s}",
                name="forearm_muscle"), 0.08)
        # knee (carpus)
        add(ell(kn + V(0, -0.005, 0.0), (0.068, 0.064, 0.072), bone=f"cannon_F_{s}",
                name="knee"), 0.04)
        # cannon (deep front-back because of the tendons) + feathered fetlock
        add(flat_cone(kn + V(0, 0.005, -0.03), fe + V(0, 0.01, 0.03), 0.058, 0.058, 0.95,
                      bone=f"cannon_F_{s}", name="cannon"), 0.04)
        add(flat_cone(kn + V(0, 0.04, -0.07), fe + V(0, 0.045, 0.04), 0.034, 0.04, 0.95,
                      bone=f"cannon_F_{s}", name="tendon"), 0.04)
        add(ell(fe + V(0, 0.012, 0.0), (0.072, 0.078, 0.07), bone=f"pastern_F_{s}",
                name="fetlock"), 0.04)
        add(ell(fe + V(0, 0.07, -0.04), (0.06, 0.05, 0.05), bone=f"pastern_F_{s}",
                name="feather"), 0.05)
        add(round_cone(fe + V(0, 0.0, -0.02), co + V(0, 0.005, 0.01), 0.066, 0.064,
                       bone=f"pastern_F_{s}", name="pastern"), 0.03)
        for p in hoof(co, J[f"toe_F_{s}"], J[f"heel_F_{s}"], s, f"hoof_F_{s}"):
            add(p, 0.02)

    # ---------------- hind limbs ----------------
    for s, sx in (("L", 1), ("R", -1)):
        hp, st, hk = J[f"hip_{s}"], J[f"stifle_{s}"], J[f"hock_{s}"]
        fe, co = J[f"fetlock_H_{s}"], J[f"coffin_H_{s}"]
        add(ell(_lerp(hp, st, 0.5) + V(-0.02 * sx, 0.03, 0.02), (0.14, 0.20, 0.22), (8, 0, 0),
                bone=f"femur_{s}", name="thigh"), 0.08)
        add(sphere(st + V(0.0, 0.0, 0.0), 0.08, bone=f"femur_{s}", name="stifle"), 0.06)
        add(round_cone(st + V(-0.01 * sx, 0.05, -0.02), hk + V(0, -0.005, 0.05), 0.11, 0.065,
                       bone=f"tibia_{s}", name="gaskin"), 0.07)
        add(ell(_lerp(st, hk, 0.35) + V(0.0, 0.07, 0.0), (0.08, 0.095, 0.15), (-25, 0, 0),
                bone=f"tibia_{s}", name="gaskin_muscle"), 0.07)
        add(round_cone(V(0.12 * sx, 0.72, 1.10), hk + V(0, 0.075, 0.08), 0.11, 0.04,
                       bone=f"tibia_{s}", name="hamstring"), 0.08)
        add(ell(hk + V(0, 0.01, 0.0), (0.066, 0.075, 0.08), bone=f"cannon_H_{s}", name="hock"), 0.04)
        add(sphere(hk + V(0, 0.07, 0.05), 0.042, bone=f"cannon_H_{s}", name="point_of_hock"), 0.04)
        add(flat_cone(hk + V(0, 0.005, -0.04), fe + V(0, 0.01, 0.03), 0.06, 0.058, 0.95,
                      bone=f"cannon_H_{s}", name="cannon_h"), 0.04)
        add(flat_cone(hk + V(0, 0.045, -0.07), fe + V(0, 0.045, 0.04), 0.035, 0.04, 0.95,
                      bone=f"cannon_H_{s}", name="tendon_h"), 0.04)
        add(ell(fe + V(0, 0.012, 0.0), (0.072, 0.078, 0.07), bone=f"pastern_H_{s}",
                name="fetlock_h"), 0.04)
        add(ell(fe + V(0, 0.07, -0.04), (0.06, 0.05, 0.05), bone=f"pastern_H_{s}",
                name="feather_h"), 0.05)
        add(round_cone(fe + V(0, 0.0, -0.02), co + V(0, 0.005, 0.01), 0.066, 0.064,
                       bone=f"pastern_H_{s}", name="pastern_h"), 0.03)
        for p in hoof(co, J[f"toe_H_{s}"], J[f"heel_H_{s}"], s, f"hoof_H_{s}", 0.97):
            add(p, 0.02)
    return P


def ear_parts(J=None):
    """Ears are thin: added after the hull carving so no single painted view can clip them."""
    J = J or skeleton()
    P = []
    for s, sx in (("L", 1), ("R", -1)):
        b, t = J[f"ear_{s}"], J[f"ear_tip_{s}"]
        p = flat_cone(b + V(0, 0, -0.03), t, 0.052, 0.012, 0.55, axis=(0.35 * sx, -1.0, 0.0),
                      bone=f"ear_{s}", name="ear")
        p.k = 0.035
        P.append(p)
    return P


def carve_parts(J=None):
    """Subtractive details (nostril openings, mouth slit, ear cups)."""
    J = J or skeleton()
    C = []
    for sx in (1, -1):
        C.append(ell((0.046 * sx, -1.54, 1.485), (0.013, 0.03, 0.028), (-30, 0, 15 * sx),
                     name="nostril_hole", k=0.012))
    C.append(ell((0, -1.50, 1.378), (0.06, 0.04, 0.006), (-12, 0, 0), name="mouth", k=0.008))
    for s, sx in (("L", 1), ("R", -1)):
        b, t = J[f"ear_{s}"], J[f"ear_tip_{s}"]
        c = _lerp(b, t, 0.45) + V(0.004 * sx, -0.022, 0.0)
        C.append(flat_cone(_lerp(b, t, 0.12) + V(0.002 * sx, -0.026, 0.0),
                           _lerp(b, t, 0.88) + V(0.0, -0.012, 0.0), 0.028, 0.006, 0.45,
                           axis=(0.3 * sx, -1.0, 0.0), name="ear_cup", k=0.008))
    return C


def hair_proxies(J=None):
    """Rough hair volumes (no bone) used only to judge silhouettes before hair cards exist."""
    J = J or skeleton()
    P = []
    top = [(-0.40, 1.60), (-0.55, 1.75), (-0.70, 1.86), (-0.85, 1.92), (-1.00, 1.96),
           (-1.08, 1.97)]
    r = 0.08
    for i in range(len(top) - 1):
        a = V(0, top[i][0], top[i][1] - r)
        b = V(0, top[i + 1][0], top[i + 1][1] - r)
        P.append(flat_cone(a, b, r, r, 1.6, name="mane_proxy"))
    P.append(flat_cone(V(0, -1.16, 1.93), V(0, -1.26, 1.80), 0.05, 0.03, 0.5, axis=(0, 1, 0),
                       name="forelock_proxy"))
    tail = [V(0, 0.76, 1.42), V(0, 0.84, 1.20), V(0, 0.86, 0.90), V(0, 0.86, 0.55),
            V(0, 0.83, 0.25), V(0, 0.80, 0.14)]
    tr = [0.07, 0.09, 0.10, 0.09, 0.05, 0.02]
    for i in range(len(tail) - 1):
        P.append(flat_cone(tail[i], tail[i + 1], tr[i], tr[i + 1], 0.8, name="tail_proxy"))
    return P
