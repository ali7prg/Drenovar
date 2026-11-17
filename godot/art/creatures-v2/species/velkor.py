"""Лесной Велькор (velkor): forest warden. L1 dimensions from 02_CREATURES.txt:
withers 2.10 m, antler top 3.65 m, nose to tail base 3.60 m, tail 0.45 m,
chest width 1.15 m, antler span 2.70 m. Cloven hooves, wolf-like predator head.
"""
import numpy as np

from sdf import Prim, Part, chain, bezier, rot_x, rot_y, rot_z
from rig import Skeleton
from common import SIDES, leg_bones, strands, locks, scatter_on, surface_points, plate_frame, scale_plate

ID = "velkor"
NAME = "Лесной Велькор"
VOXEL_BODY = 0.012
VOXEL_RIGID = 0.005
BAKE_EXTRUSION = 0.018
BAKE_RAY = 0.05
AO_SAMPLES = 40
AO_DISTANCE = 0.45

# ---------------------------------------------------------------- skeleton
FRONT = {  # girdle, upper(shoulder joint), lower(elbow), foot(carpus), toe(fetlock), tip(hoof front)
    "joints": [(0.66, 1.98, 0.22), (0.98, 1.46, 0.40), (0.80, 1.06, 0.39), (0.93, 0.52, 0.36), (0.96, 0.21, 0.36),
               (1.08, 0.0, 0.36)]}
HIND = {
    "joints": [(-0.98, 1.74, 0.20), (-1.12, 1.50, 0.38), (-0.82, 1.06, 0.40), (-1.30, 0.63, 0.37), (-1.23, 0.21, 0.36),
               (-1.11, 0.0, 0.36)]}


def mirror(p, s):
    return (p[0], p[1], p[2] * s if s < 0 else p[2])


def side(p, s):
    return np.array([p[0], p[1], abs(p[2]) * s])


def skeleton():
    sk = Skeleton()
    sk.add("MotionRoot", None, (0, 0, 0))
    sk.add("Pelvis", "MotionRoot", (-0.96, 1.72, 0))
    sk.add("Spine_01", "Pelvis", (-0.45, 1.80, 0))
    sk.add("Spine_02", "Spine_01", (0.08, 1.88, 0))
    sk.add("Chest", "Spine_02", (0.58, 1.92, 0))
    sk.add("Neck_01", "Chest", (1.02, 1.96, 0))
    sk.add("Neck_02", "Neck_01", (1.30, 2.20, 0))
    sk.add("Head", "Neck_02", (1.54, 2.44, 0), tail=(2.05, 2.30, 0))
    sk.add("Jaw", "Head", (1.66, 2.33, 0), tail=(1.98, 2.22, 0))
    sk.add("Nose", "Head", (1.92, 2.36, 0), tail=(2.05, 2.32, 0))
    for nm, s in SIDES:
        sk.add(f"Ear_{nm}", "Head", (1.47, 2.63, 0.14 * s), tail=(1.42, 2.84, 0.24 * s))
        sk.add(f"Antler_{nm}", "Head", (1.52, 2.67, 0.12 * s), tail=(1.36, 3.55, 1.25 * s))
    sk.add("Mane_01", "Neck_01", (1.20, 1.52, 0), tail=(1.24, 1.15, 0))
    sk.add("Mane_02", "Neck_02", (1.44, 1.98, 0), tail=(1.46, 1.70, 0))
    sk.add("Belly", "Spine_02", (-0.05, 1.22, 0), tail=(-0.05, 1.08, 0))
    for nm, s in SIDES:
        leg_bones(sk, "Front", "Chest", None, [side(j, s) for j in FRONT["joints"]], nm)
        leg_bones(sk, "Hind", "Pelvis", None, [side(j, s) for j in HIND["joints"]], nm)
    sk.add("Tail_01", "Pelvis", (-1.55, 1.80, 0))
    sk.add("Tail_02", "Tail_01", (-1.67, 1.70, 0))
    sk.add("Tail_03", "Tail_02", (-1.77, 1.58, 0))
    sk.add("Tail_04", "Tail_03", (-1.84, 1.46, 0), tail=(-1.88, 1.36, 0))
    # sockets (effects and debug only)
    sk.socket("socket_head", "Head", (1.62, 2.58, 0))
    sk.socket("socket_mouth", "Jaw", (1.98, 2.26, 0))
    sk.socket("socket_chest", "Chest", (1.18, 1.40, 0))
    for nm, s in SIDES:
        sk.socket(f"socket_foot_front_{nm.lower()}", f"Toe_Front_{nm}", side(FRONT["joints"][5], s))
        sk.socket(f"socket_foot_hind_{nm.lower()}", f"Toe_Hind_{nm}", side(HIND["joints"][5], s))
        sk.socket(f"socket_antler_{nm.lower()}", f"Antler_{nm}", (1.30, 3.50, 1.20 * s))
    sk.socket("socket_tail_tip", "Tail_04", (-1.88, 1.36, 0))
    return sk


# ---------------------------------------------------------------- body sculpt
def leg_prims(kind, nm, s, J):
    j = [side(p, s) for p in J]
    U, L, Fo, T = f"UpperLeg_{kind}_{nm}", f"LowerLeg_{kind}_{nm}", f"Foot_{kind}_{nm}", f"Toe_{kind}_{nm}"
    out = []
    if kind == "Front":
        out += [Prim("cone", U, k=0.10, a=j[1], b=j[2], ra=0.22, rb=0.16, name="humerus"),
                Prim("ellipsoid", U, k=0.10, c=j[1] * 0.5 + j[2] * 0.5 + np.array([-0.03, 0.02, 0.02 * s]),
                     r=(0.21, 0.27, 0.16), name="triceps"),
                Prim("sphere", L, k=0.06, c=j[2] + np.array([-0.07, 0.03, 0]), r=0.12, name="elbow"),
                Prim("cone", L, k=0.07, a=j[2], b=j[3], ra=0.16, rb=0.108, name="forearm"),
                Prim("ellipsoid", L, k=0.08, c=j[2] * 0.6 + j[3] * 0.4 + np.array([0.03, 0, 0]),
                     r=(0.13, 0.26, 0.125), name="forearm_m")]
    else:
        out += [Prim("cone", U, k=0.12, a=j[1], b=j[2], ra=0.26, rb=0.17, name="femur"),
                Prim("cone", L, k=0.07, a=j[2], b=j[3], ra=0.17, rb=0.095, name="tibia"),
                Prim("ellipsoid", L, k=0.08, c=j[2] * 0.58 + j[3] * 0.42 + np.array([-0.03, 0.03, 0]),
                     r=(0.17, 0.25, 0.135), name="gaskin"),
                Prim("sphere", Fo, k=0.04, c=j[3] + np.array([-0.075, 0.04, 0]), r=0.065, name="calcaneus")]
    out += [Prim("sphere", Fo, k=0.05, c=j[3], r=0.10 if kind == "Front" else 0.092, name="carpus"),
            Prim("cone", Fo, k=0.04, a=j[3], b=j[4], ra=0.092, rb=0.082, name="cannon"),
            Prim("sphere", T, k=0.045, c=j[4] + np.array([-0.012, 0, 0]), r=0.10, name="fetlock"),
            Prim("cone", T, k=0.035, a=j[4], b=j[4] * 0.42 + j[5] * 0.58 + np.array([-0.01, 0.07, 0]), ra=0.088,
                 rb=0.098, name="pastern")]
    # cloven hoof: two big dark claws and a cleft
    hc = j[4] * 0.28 + j[5] * 0.72
    for c, sgn in (("in", -1), ("out", 1)):
        out.append(Prim("ellipsoid", T, k=0.016, mat="hoof", name=f"claw_{c}",
                        c=np.array([hc[0] - 0.005, 0.055, j[5][2] + sgn * 0.055]),
                        r=(0.122, 0.085, 0.058), R=rot_z(0.32)))
    out.append(Prim("box", T, k=0.006, neg=True, name="cleft", c=np.array([j[5][0] + 0.035, 0.05, j[5][2]]),
                    h=(0.085, 0.09, 0.0075), round=0.0))
    out.append(Prim("box", T, k=0.004, neg=True, name="sole", c=np.array([j[5][0] - 0.02, -0.10, j[5][2]]),
                    h=(0.25, 0.10, 0.20), round=0.0))
    return out


def body_core():
    P = []
    P += [Prim("ellipsoid", "Chest", k=0.0, c=(0.50, 1.60, 0), r=(0.72, 0.52, 0.46), name="ribcage"),
          Prim("ellipsoid", "Chest", k=0.15, c=(0.95, 1.45, 0), r=(0.34, 0.42, 0.42), name="brisket"),
          Prim("ellipsoid", "Chest", k=0.18, c=(0.66, 2.02, 0), r=(0.52, 0.20, 0.29), name="withers"),
          Prim("ellipsoid", "Spine_02", k=0.18, c=(-0.22, 1.68, 0), r=(0.50, 0.36, 0.40), name="waist"),
          Prim("ellipsoid", "Spine_01", k=0.18, c=(-0.55, 1.72, 0), r=(0.42, 0.31, 0.40), name="loin"),
          Prim("ellipsoid", "Pelvis", k=0.18, c=(-1.00, 1.66, 0), r=(0.48, 0.36, 0.40), name="rump"),
          Prim("ellipsoid", "Pelvis", k=0.14, c=(-0.95, 1.86, 0), r=(0.42, 0.12, 0.28), name="croup"),
          Prim("ellipsoid", "Belly", k=0.20, c=(0.10, 1.32, 0), r=(0.42, 0.18, 0.34), name="belly")]
    P += [Prim("cone", "Neck_01", k=0.16, a=(0.92, 1.84, 0), b=(1.26, 2.13, 0), ra=0.44, rb=0.34, name="neck1"),
          Prim("cone", "Neck_02", k=0.10, a=(1.26, 2.13, 0), b=(1.50, 2.40, 0), ra=0.34, rb=0.25, name="neck2"),
          Prim("ellipsoid", "Mane_02", k=0.14, c=(1.34, 1.98, 0), r=(0.22, 0.32, 0.26), name="throat")]
    P += [Prim("ellipsoid", "Head", k=0.08, c=(1.57, 2.52, 0), r=(0.30, 0.185, 0.19), name="cranium"),
          Prim("ellipsoid", "Head", k=0.06, c=(1.52, 2.60, 0), r=(0.22, 0.10, 0.15), name="crown"),
          Prim("cone", "Nose", k=0.06, a=(1.74, 2.47, 0), b=(2.03, 2.345, 0), ra=0.14, rb=0.072, name="muzzle"),
          Prim("ellipsoid", "Head", k=0.04, c=(1.87, 2.475, 0), r=(0.19, 0.055, 0.095), R=rot_z(-0.38),
               name="nasal"),
          Prim("sphere", "Nose", k=0.02, mat="nose", c=(2.036, 2.348, 0), r=0.060, name="nosepad"),
          Prim("cone", "Jaw", k=0.04, a=(1.63, 2.31, 0), b=(1.99, 2.255, 0), ra=0.105, rb=0.05, name="jaw"),
          Prim("sphere", "Jaw", k=0.03, mat="skin", c=(2.0, 2.265, 0), r=0.045, name="chin")]
    for nm, s in SIDES:
        P += [Prim("ellipsoid", "Jaw", k=0.06, c=(1.62, 2.37, 0.13 * s), r=(0.16, 0.11, 0.08), name=f"cheek{nm}"),
              Prim("ellipsoid", "Head", k=0.04, c=(1.64, 2.47, 0.155 * s), r=(0.12, 0.05, 0.05), name=f"zygoma{nm}"),
              Prim("ellipsoid", "Head", k=0.035, c=(1.715, 2.59, 0.095 * s), r=(0.12, 0.052, 0.07), R=rot_z(-0.15),
                   name=f"brow{nm}"),
              Prim("cone", "Nose", k=0.03, mat="skin", a=(1.80, 2.30, 0.10 * s), b=(1.99, 2.29, 0.048 * s),
                   ra=0.037, rb=0.026, name=f"lip{nm}"),
              Prim("sphere", "Head", k=0.015, neg=True, c=(1.748, 2.522, 0.124 * s), r=0.038, name=f"socket{nm}")]
        ec = np.array([1.44, 2.77, 0.205 * s])
        Re = rot_x(-0.55 * s) @ rot_z(0.18)
        P += [Prim("ellipsoid", f"Ear_{nm}", k=0.03, c=ec, r=(0.055, 0.17, 0.09), R=Re, name=f"ear{nm}"),
              Prim("cone", f"Ear_{nm}", k=0.03, a=ec, b=ec + Re @ np.array([0.0, 0.20, 0.0]), ra=0.06, rb=0.012,
                   name=f"eartip{nm}"),
              Prim("ellipsoid", f"Ear_{nm}", k=0.01, neg=True, mat="skin", c=ec + np.array([0.045, 0.0, 0.0]),
                   r=(0.034, 0.13, 0.062), R=Re, name=f"earcav{nm}")]
        P += [Prim("ellipsoid", f"Shoulder_{nm}", k=0.14, c=side((0.80, 1.62, 0.33), s), r=(0.36, 0.50, 0.21),
                   R=rot_z(-0.45), name=f"scapula{nm}"),
              Prim("ellipsoid", f"UpperLeg_Front_{nm}", k=0.12, c=side((0.98, 1.40, 0.36), s), r=(0.22, 0.22, 0.17),
                   name=f"deltoid{nm}"),
              Prim("ellipsoid", f"UpperLeg_Hind_{nm}", k=0.16, c=side((-1.04, 1.40, 0.33), s), r=(0.40, 0.48, 0.20),
                   R=rot_z(0.25), name=f"haunch{nm}")]
        P += leg_prims("Front", nm, s, FRONT["joints"])
        P += leg_prims("Hind", nm, s, HIND["joints"])
    P += chain([(-1.46, 1.85, 0), (-1.62, 1.74, 0), (-1.74, 1.61, 0), (-1.83, 1.48, 0), (-1.89, 1.38, 0)],
               [0.12, 0.15, 0.15, 0.12, 0.06], None, k=0.06, mat="fur_long", name="tail",
               bones=["Tail_01", "Tail_02", "Tail_03", "Tail_04"])
    return P


def body_bone(p):
    x, y, z = p
    if x > 1.40:
        return "Neck_02" if y < 2.25 else "Head"
    if x > 1.0:
        return "Mane_01" if y < 1.72 else "Neck_01"
    if y < 1.30:
        return "Belly" if -0.6 < x < 0.6 else ("Chest" if x > 0 else "Pelvis")
    if x > 0.3:
        return "Chest"
    if x > -0.25:
        return "Spine_02"
    if x > -0.75:
        return "Spine_01"
    return "Pelvis"


def build_body(rng):
    core = Part("body", body_core(), band=0.08)
    P = list(core.prims)
    back = lambda p, n: np.array([-1.0, -0.35, 0])  # noqa: E731
    hang = lambda p, n: np.array([-0.25, -1.0, 0])  # noqa: E731
    # chest mane: long locks, longest low on the brisket
    seeds = scatter_on(core, (1.16, 1.62, 0), (0.30, 0.45, 0.42), 70, rng)
    P += locks(core, seeds, hang, lambda p: 0.30 + 0.32 * np.clip((1.95 - p[1]) / 0.8, 0, 1), 0.13, body_bone,
               gravity=0.5, lift=0.18, rng=rng, droop=0.5)
    # neck ruff laid back
    seeds = scatter_on(core, (1.24, 2.15, 0), (0.30, 0.28, 0.38), 60, rng)
    P += locks(core, seeds, lambda p, n: np.array([-1.0, -0.45, 0]), 0.34, 0.13, body_bone, lift=0.32, rng=rng,
               droop=0.25)
    # shoulder, flank and back shag
    seeds = scatter_on(core, (0.15, 1.72, 0), (1.05, 0.32, 0.55), 52, rng)
    P += locks(core, seeds, back, 0.24, 0.10, body_bone, thick=0.28, lift=0.22, rng=rng, droop=0.2)
    # belly fringe and haunch feathering
    seeds = scatter_on(core, (0.15, 1.16, 0), (0.80, 0.10, 0.40), 40, rng)
    P += locks(core, seeds, hang, 0.26, 0.11, body_bone, gravity=0.4, lift=0.08, rng=rng, droop=0.4)
    for nm, s in SIDES:
        seeds = scatter_on(core, side((-1.22, 1.30, 0.30), s), (0.22, 0.30, 0.16), 14, rng)
        P += locks(core, seeds, hang, 0.22, 0.10, lambda p, b=f"UpperLeg_Hind_{nm}": b, lift=0.2, rng=rng, droop=0.3)
        fj = [side(j, s) for j in FRONT["joints"]]
        hj = [side(j, s) for j in HIND["joints"]]
        for c, r, cnt, L, bone in (((fj[2] + fj[3]) / 2 + np.array([-0.09, 0.12, 0]), (0.08, 0.24, 0.09), 9, 0.24,
                                    f"LowerLeg_Front_{nm}"),
                                   (fj[1] * 0.5 + fj[2] * 0.5 + np.array([-0.12, 0, 0]), (0.08, 0.16, 0.12), 7, 0.22,
                                    f"UpperLeg_Front_{nm}"),
                                   (fj[4] + np.array([-0.05, 0.04, 0]), (0.06, 0.05, 0.08), 7, 0.15, f"Toe_Front_{nm}"),
                                   (hj[4] + np.array([-0.05, 0.04, 0]), (0.06, 0.05, 0.08), 7, 0.15, f"Toe_Hind_{nm}"),
                                   (hj[3] + np.array([0.0, 0.14, 0]), (0.07, 0.16, 0.08), 6, 0.18, f"Foot_Hind_{nm}")):
            seeds = scatter_on(core, c, r, cnt, rng)
            P += locks(core, seeds, hang, L, 0.075, lambda p, b=bone: b, gravity=0.3, lift=0.22, rng=rng, droop=0.3,
                       k=0.035)
    # tail brush
    seeds = scatter_on(core, (-1.72, 1.60, 0), (0.18, 0.24, 0.15), 30, rng)
    P += locks(core, seeds, lambda p, n: np.array([-0.7, -1.0, 0]), 0.30, 0.10,
               lambda p: "Tail_03" if p[1] < 1.62 else "Tail_02", gravity=0.2, lift=0.35, rng=rng, droop=0.3)
    # moss drapes along the flanks under the bark plates
    seeds = scatter_on(core, (0.30, 1.86, 0), (0.95, 0.12, 0.52), 34, rng)
    P += locks(core, seeds, lambda p, n: np.array([-0.15, -1.0, 0]), 0.36, 0.045, body_bone, mat="moss",
               thick=0.45, gravity=0.9, lift=0.10, rng=rng, droop=0.7, k=0.025)
    return Part("body", P, band=0.09)


# ---------------------------------------------------------------- antlers
def antler_prims(s):
    """Main beam rising, then sweeping out and back, six upward tines; burr at the base."""
    nm = "L" if s < 0 else "R"
    bone = f"Antler_{nm}"
    base = np.array([1.53, 2.66, 0.12 * s])
    beam = bezier(base, np.array([1.51, 2.92, 0.36 * s]), np.array([1.38, 3.12, 0.86 * s]),
                  np.array([1.18, 3.28, 1.31 * s]), 14)
    radii = np.linspace(0.080, 0.034, len(beam))
    P = [Prim("ellipsoid", bone, k=0.0, mat="antler", c=base + np.array([0, 0.03, 0.01 * s]), r=(0.10, 0.04, 0.10),
              name="burr")]
    P += chain(list(beam), list(radii), bone, k=0.02, mat="antler", name="beam")
    tines = [(0.14, (0.62, 0.78, -0.10 * s), 0.36),
             (0.32, (0.30, 0.95, -0.06 * s), 0.46),
             (0.48, (0.16, 1.00, -0.02 * s), 0.50),
             (0.64, (0.06, 1.00, 0.04 * s), 0.44),
             (0.80, (-0.04, 1.00, 0.12 * s), 0.36),
             (0.95, (-0.10, 0.90, 0.30 * s), 0.26)]
    for i, (f, d, L) in enumerate(tines):
        k = f * (len(beam) - 1)
        i0 = int(k)
        t = k - i0
        root = beam[i0] * (1 - t) + beam[min(i0 + 1, len(beam) - 1)] * t
        r0 = np.interp(f, np.linspace(0, 1, len(beam)), radii) * 0.85
        d = np.asarray(d, float)
        d /= np.linalg.norm(d)
        curve = bezier(root, root + d * L * 0.45, root + d * L * 0.8 + np.array([0.04, 0.03, 0.03 * s]),
                       root + d * L + np.array([0.07, 0.0, 0.04 * s]), 7)
        P += chain(list(curve), list(np.linspace(r0, 0.011, len(curve))), bone, k=0.025, mat="antler", name=f"tine{i}")
    rng = np.random.default_rng(11 if s < 0 else 12)
    from common import _frame
    for i in range(16):
        f = 0.16 + 0.78 * rng.random()
        k = f * (len(beam) - 1)
        root = beam[int(k)] + np.array([0, -0.03, 0])
        L = 0.14 + 0.30 * rng.random()
        d = np.array([-0.04, -1.0, 0.06 * rng.standard_normal()])
        d /= np.linalg.norm(d)
        R = _frame(d, np.array([1.0, 0, 0]))
        P.append(Prim("ellipsoid", bone, k=0.015, mat="moss", name=f"mossh{i}", c=root + d * L * 0.48,
                      r=(L * 0.5, 0.012, 0.022 + 0.012 * rng.random()), R=R))
    return Part(f"antler_{nm}", P, band=0.04)


# ---------------------------------------------------------------- bark plates
def build_plates(core, rng, overlay=None):
    """Shingled bark plates over the neck base, withers, back and shoulders (rigid per plate)."""
    specs = []
    rows = [(1.06, 3, 0.32, "Chest"), (0.88, 4, 0.42, "Chest"), (0.64, 4, 0.44, "Chest"), (0.40, 4, 0.42, "Chest"),
            (0.16, 3, 0.40, "Spine_02"), (-0.08, 3, 0.38, "Spine_02"), (-0.32, 3, 0.36, "Spine_01"),
            (-0.56, 3, 0.34, "Spine_01"), (-0.80, 2, 0.32, "Pelvis")]
    for r, (x, n, L, bone) in enumerate(rows):
        for i in range(n):
            u = (i - (n - 1) / 2)
            ang = u * 0.62  # around the back, radians from the top
            start = np.array([x + rng.normal(0, 0.025) + (0.08 if i % 2 else 0), 2.0 + 1.2 * np.cos(ang),
                              1.2 * np.sin(ang)])
            specs.append((start, L * (0.9 + 0.2 * rng.random()), L * 0.78, bone))
    for nm, s in SIDES:
        for (x, y, z, L) in ((0.86, 1.82, 0.50, 0.34), (0.62, 1.78, 0.55, 0.32), (0.78, 1.55, 0.62, 0.28)):
            specs.append((np.array([x, y + 0.6, z * s * 2.0]), L, L * 0.8, f"Shoulder_{nm}"))
    starts = np.array([sp[0] for sp in specs], np.float32)
    pts, nrm = surface_points(core, starts, steps=12)
    P = []
    for k, ((st, L, W, bone), p, n) in enumerate(zip(specs, pts, nrm)):
        n = n / np.linalg.norm(n)
        P += scale_plate(p + n * 0.012, n, np.array([-1.0, -0.10, 0]), L, W, 0.024 + 0.006 * rng.random(), bone,
                         "bark", tilt=0.12 + rng.normal(0, 0.03), yaw=rng.normal(0, 0.10), name=f"plate{k}")
    return P


def eye_part():
    P = []
    for nm, s in SIDES:
        P.append(Prim("sphere", "Head", k=0.0, mat="eye", c=(1.742, 2.522, 0.118 * s), r=0.034, name=f"eye{nm}"))
    return Part("eyes", P, band=0.02)


def crest_part(rng):
    """Level II+: a wooden crest of upright bark spines along the back."""
    P = []
    core = Part("core", body_core(), band=0.08)
    xs = np.linspace(0.95, -0.85, 9)
    starts = np.array([[x, 2.6, 0.0] for x in xs], np.float32)
    pts, nrm = surface_points(core, starts, steps=12)
    for i, (p, n) in enumerate(zip(pts, nrm)):
        bone = "Chest" if p[0] > 0.3 else ("Spine_02" if p[0] > -0.25 else ("Spine_01" if p[0] > -0.7 else "Pelvis"))
        h = 0.26 + 0.10 * np.sin(i * 0.9) + (0.08 if 0.2 < p[0] < 0.9 else 0)
        top = p + np.array([-0.10, h, 0])
        P.append(Prim("cone", bone, k=0.0 if i == 0 else 0.0, mat="bark", name=f"crest{i}", a=p - n * 0.02,
                      b=top, ra=0.065, rb=0.012))
    return P


def carved_part(rng):
    """Level III: four large ancient carved plates over the shoulders."""
    P = []
    core = Part("core", body_core(), band=0.08)
    for nm, s in SIDES:
        starts = np.array([[0.92, 2.2, 0.9 * s], [0.62, 2.1, 0.95 * s]], np.float32)
        pts, nrm = surface_points(core, starts, steps=12)
        for i, (p, n) in enumerate(zip(pts, nrm)):
            P += scale_plate(p + n * 0.055, n, np.array([-1.0, -0.25, 0]), 0.56, 0.44, 0.04, f"Shoulder_{nm}",
                             "carved", tilt=0.10, yaw=0.0, name=f"carved{nm}{i}")
    return P


CLASSES = {"body": ["fur", "fur_long", "skin", "nose", "hoof", "moss"],
           "horn": ["antler", "bark", "moss", "eye", "carved"]}
CLASS_OF = {"base": "fur"}
AXIS_PRIMS = ("lock", "beam", "tine", "mossh", "humerus", "forearm", "femur", "tibia", "cannon", "pastern",
              "tail", "neck", "plate", "carved", "crest", "muzzle", "jaw", "lip")
_CACHE = {}


def build(rng=None):
    rng = rng or np.random.default_rng(7)
    sk = skeleton()
    body = build_body(rng)
    core = Part("core", body_core(), band=0.08)
    plates = build_plates(core, rng)
    parts = [
        {"name": "body", "part": body, "material": "body", "rigid": None, "faces": (30000, 12500, 3600)},
        {"name": "antler_L", "part": antler_prims(-1), "material": "horn", "rigid": "Antler_L", "faces": (4600, 1900, 560)},
        {"name": "antler_R", "part": antler_prims(1), "material": "horn", "rigid": "Antler_R", "faces": (4600, 1900, 560)},
        {"name": "eyes", "part": eye_part(), "material": "horn", "rigid": "Head", "faces": (320, 160, 48),
         "voxel": 0.003},
    ]
    for k in range(0, len(plates), 2):
        pr = plates[k:k + 2]
        parts.append({"name": f"plate{k // 2}", "part": Part(f"plate{k // 2}", pr, band=0.03), "material": "horn",
                      "rigid": pr[0].bone, "faces": (260, 110, 36)})
    for k, pr in enumerate(crest_part(rng)):
        parts.append({"name": f"crest{k}", "part": Part(f"crest{k}", [pr], band=0.03), "material": "horn",
                      "rigid": pr.bone, "faces": (160, 70, 0), "level": 2})
    carved = carved_part(rng)
    for k in range(0, len(carved), 2):
        pr = carved[k:k + 2]
        parts.append({"name": f"carved{k // 2}", "part": Part(f"carved{k // 2}", pr, band=0.03), "material": "horn",
                      "rigid": pr[0].bone, "faces": (420, 180, 0), "level": 3})
    return sk, parts


def build_cached():
    if "b" not in _CACHE:
        _CACHE["b"] = build()
        for k, p in enumerate(_CACHE["b"][1]):
            p["index"] = k
    return _CACHE["b"]


# ---------------------------------------------------------------- surface
from shading import lin, mix, sstep, fur_height, rune_field, bark, moss_mask, tangent_flow  # noqa: E402
import noise  # noqa: E402

EMERALD = (0.33, 0.84, 0.46)  # #55D675 in sRGB terms -> converted below
RUNES = []
for _nm, _s in SIDES:
    RUNES.append(((0.82, 1.66, 0.50 * _s), (0, 0, _s), (0.28, 1, 0), 0.155))   # shoulder
    RUNES.append(((-0.32, 1.64, 0.47 * _s), (0, 0, _s), (-0.15, 1, 0), 0.105))  # flank


def default_flow(P, part):
    x, y = P[:, 0], P[:, 1]
    back = np.array([-1.0, -0.25, 0.0], np.float32)
    down = np.array([-0.25, -1.0, 0.0], np.float32)
    w_leg = sstep(1.20, 0.95, y)[:, None]
    w_chest = (sstep(0.95, 1.20, x) * sstep(2.25, 2.05, y))[:, None]
    f = back * (1 - np.maximum(w_leg, w_chest)) + down * np.maximum(w_leg, w_chest)
    if part.startswith("antler"):
        f = np.broadcast_to(np.array([0, 1.0, 0], np.float32), P.shape)
    return np.asarray(f, np.float32)


def shade(group, ctx):
    return shade_body(ctx) if group == "body" else shade_horn(ctx)


def shade_body(ctx):
    P, N = ctx.P, ctx.N
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    W = ctx.W
    cl = CLASSES["body"]
    w = {c: W[:, i] for i, c in enumerate(cl)}
    flow = tangent_flow(ctx.flow, N)
    lod = ctx.lod
    hfur = fur_height(flow, 1.0, 3 if lod == 0 else (2 if lod == 1 else 1), clumps=True)
    h0 = hfur(P) / 0.0028
    # regional coat colour
    col = mix(lin("#5d4f40"), lin("#463b30"), sstep(0.1, 0.8, N[:, 1]))
    col = mix(col, lin("#7c6a52"), sstep(-0.1, -0.7, N[:, 1]) * sstep(0.95, 1.25, y))
    col = mix(col, lin("#3e352c"), sstep(1.10, 0.80, y))
    col = mix(col, lin("#2f2924"), sstep(0.55, 0.25, y))
    col = mix(col, lin("#4b4239"), sstep(1.72, 1.92, x) * sstep(2.10, 2.30, y))
    col = mix(col, lin("#6e5e49"), sstep(1.30, 1.50, x) * sstep(2.55, 2.40, y) * sstep(0.2, 0.7, np.abs(N[:, 2])))
    patch = noise.fbm(P * 2.2, 3, seed=21)
    col = col * (1.0 + 0.16 * patch[:, None])
    # long mane: light tips
    mane = mix(lin("#5e5141"), lin("#8c7b60"), sstep(-0.2, 0.9, h0))
    col = mix(col, mane, w["fur_long"])
    col = col * (0.62 + 0.46 * sstep(-1.0, 1.0, h0))[:, None] * 0.82
    skin = mix(lin("#4c3a33"), lin("#6a4c42"), sstep(0.5, -0.5, N[:, 1]))
    col = mix(col, skin, w["skin"])
    col = mix(col, lin("#1c1916"), w["nose"])
    hoof = mix(lin("#262019"), lin("#4a3d30"), sstep(0.035, 0.0, y) + 0.3 * sstep(0.0, 1.0, noise.perlin(P * 40, 9)))
    col = mix(col, hoof, w["hoof"])
    mossc = mix(lin("#34481a"), lin("#5f6d24"), sstep(-0.4, 0.6, noise.fbm(P * 9, 3, seed=4)))
    col = mix(col, mossc, w["moss"])
    # runes (emissive, a little darkened/burnt fur around them)
    line, glow = rune_field(P, N, RUNES)
    line = line * (1 - w["hoof"]) * (1 - w["moss"])
    glow = glow * (1 - w["hoof"]) * (1 - w["moss"])
    col = mix(col, col * 0.55, line)
    em_col = lin("#55d675")
    emissive = em_col[None, :] * (line + 0.18 * glow)[:, None]
    shoulder = np.zeros_like(line)
    sl, sg = rune_field(P, N, [r for r in RUNES if r[3] > 0.13])
    shoulder = np.clip(sl + 0.5 * sg, 0, 1) * (1 - w["moss"])
    rough = 0.86 + 0.06 * noise.perlin(P * 15, 3)
    rough = mix(rough, 0.80 + 0.06 * h0.clip(-1, 1), w["fur_long"])
    rough = mix(rough, 0.62, w["skin"])
    rough = mix(rough, 0.42, w["nose"])
    rough = mix(rough, 0.50 + 0.15 * sstep(0.035, 0.0, y), w["hoof"])
    rough = mix(rough, 0.95, w["moss"])
    furw = w["fur"] + w["fur_long"]

    def height(Q):
        h = hfur(Q) * furw * 1.6
        h = h + noise.perlin(Q * 120, 13) * 0.0004 * (w["skin"] + w["nose"])
        h = h + np.sin(Q[:, 1] * 260.0) * 0.0004 * w["hoof"]
        h = h + noise.fbm(Q * 35, 2, seed=8) * 0.002 * w["moss"]
        return h
    cavity = 1.0 - 0.28 * furw * sstep(0.2, -0.9, h0)
    variant = np.stack([shoulder, np.zeros_like(line), np.clip(line + 0.4 * glow, 0, 1), np.ones_like(line)], 1)
    return {"albedo": np.clip(col, 0, 1), "roughness": np.clip(rough, 0, 1), "emissive": emissive,
            "height": height, "height_eps": 0.0025 if lod == 0 else 0.004, "cavity": cavity, "variant": variant}


def shade_horn(ctx):
    P, N = ctx.P, ctx.N
    W = ctx.W
    cl = CLASSES["horn"]
    w = {c: W[:, i] for i, c in enumerate(cl)}
    flow = tangent_flow(ctx.flow, N)
    rad = getattr(ctx, "rad", np.full(ctx.n, 0.05, np.float32))
    # antler: aged ivory, dark at the burr, pale tips, long woody grooves, moss near the base
    groove = noise.ridged(noise.stretch_along(P * 34.0, flow, 7.0), 3, seed=31)
    ant = mix(lin("#e3d7bb"), lin("#b59f78"), sstep(0.02, 0.06, rad))
    ant = mix(ant, lin("#7a6548"), sstep(0.065, 0.085, rad))
    ant = ant * (0.86 + 0.18 * groove)[:, None]
    mm = moss_mask(P, N, 0.22, seed=12) * sstep(0.035, 0.065, rad)
    mossc = mix(lin("#2f4317"), lin("#5a6a22"), sstep(-0.4, 0.6, noise.fbm(P * 11, 3, seed=6)))
    ant = mix(ant, mossc, mm)
    # bark plates: cracked dark bark, lighter worn edges, moss tops with a few golden leaves
    bh, crack, cid = bark(P, flow, 1.0)
    bk = mix(lin("#4f3826"), lin("#33251a"), sstep(0.2, 0.8, cid))
    bk = mix(bk, lin("#140e09"), crack)
    edge = sstep(0.35, 0.0, np.abs(N[:, 1]))
    bk = mix(bk, lin("#75573a"), edge * 0.7 * (1 - crack))
    bm = moss_mask(P, N, 0.40, seed=14)
    bk = mix(bk, mossc, bm)
    f1, _f2, lid = noise.worley(P * 28.0, 41)
    leaf = (lid > 0.94).astype(np.float32) * sstep(0.32, 0.18, f1) * bm
    bk = mix(bk, lin("#c69a3c"), leaf)
    # carved (level III) plates: bark with emerald-lit carved runes
    cv = mix(lin("#5b432d"), lin("#3e2d1f"), sstep(0.2, 0.8, cid))
    cv = mix(cv, lin("#1b130d"), crack * 0.6)
    carve_line, carve_glow = rune_field(P, N, [((0.0, 0.0, 0.0), (0, 1, 0), (1, 0, 0), 0.0)])  # placeholder
    eye_c = lin("#2a2a22")
    col = (ant * w["antler"][:, None] + bk * w["bark"][:, None] + mossc * w["moss"][:, None]
           + eye_c * w["eye"][:, None] + cv * w["carved"][:, None])
    # eyes: emerald iris + dark pupil, glossy
    em = np.zeros((ctx.n, 3), np.float32)
    for s in (-1, 1):
        c = np.array([1.742, 2.522, 0.118 * s], np.float32)
        ax = np.array([0.55, 0.06, 0.83 * s], np.float32)
        ax /= np.linalg.norm(ax)
        rel = P - c
        cosang = np.sum(rel * ax, 1) / np.maximum(np.linalg.norm(rel, axis=1), 1e-6)
        near = (np.linalg.norm(rel, axis=1) < 0.05).astype(np.float32) * w["eye"]
        iris = sstep(0.80, 0.86, cosang) * near
        pupil = sstep(0.955, 0.975, cosang) * near
        col = mix(col, lin("#2e8a4a"), iris)
        col = mix(col, lin("#050505"), pupil)
        em += lin("#55d675")[None, :] * (iris * (1 - pupil) * 0.9)[:, None]
    # carved runes on the level III plates: emerald grooves along a spiral
    carved_w = w["carved"]
    cl_line = np.zeros(ctx.n, np.float32)
    if carved_w.max() > 0:
        for s in (-1, 1):
            for cx in (0.92, 0.62):
                l, g = rune_field(P, N, [((cx, 1.95, 0.55 * s), (0, 0.6, s), (-0.2, 1, 0), 0.10)])
                cl_line = np.maximum(cl_line, l)
        cl_line *= carved_w
        col = mix(col, col * 0.45, cl_line)
        em += lin("#55d675")[None, :] * cl_line[:, None]
    rough = (w["antler"] * (0.62 + 0.18 * (1 - groove)) + w["bark"] * (0.90 - 0.05 * edge) + w["moss"] * 0.95
             + w["eye"] * 0.12 + w["carved"] * 0.86)
    rough = mix(rough, 0.95, mm * w["antler"] + bm * w["bark"])

    def height(Q):
        g = noise.ridged(noise.stretch_along(Q * 34.0, flow, 7.0), 2, seed=31)
        hb, _c, _i = bark(Q, flow, 1.0)
        return (g * 0.0012 * w["antler"] + hb * (w["bark"] + w["carved"]) + noise.fbm(Q * 40, 2, seed=8) * 0.0015 *
                (w["moss"] + mm * w["antler"] + bm * w["bark"]))
    cavity = 1.0 - 0.35 * crack * (w["bark"] + w["carved"])
    gold = sstep(0.026, 0.014, rad) * w["antler"]
    variant = np.stack([np.zeros(ctx.n, np.float32), gold, np.zeros(ctx.n, np.float32), np.ones(ctx.n, np.float32)], 1)
    return {"albedo": np.clip(col, 0, 1), "roughness": np.clip(rough, 0, 1), "emissive": em, "height": height,
            "height_eps": 0.002, "cavity": cavity, "variant": variant}


# ---------------------------------------------------------------- materials / levels
MATERIAL_NAMES = {"body": "Body", "horn": "AntlerBark"}
# Level look (Godot shader uniforms; also baked into per-level web files). Masks: R shoulder runes,
# G antler tips (gold), B all runes. Emission strength multiplies the emissive map.
LEVELS = {
    1: {"emission_strength": 0.9, "tint_g": (0.84, 0.66, 0.28, 0.0), "emit_r": 0.0, "emit_b": 0.0},
    2: {"emission_strength": 1.25, "tint_g": (0.84, 0.66, 0.28, 0.0), "emit_r": 0.9, "emit_b": 0.2},
    3: {"emission_strength": 1.7, "tint_g": (0.86, 0.66, 0.24, 0.85), "emit_r": 1.2, "emit_b": 0.9},
}
EMISSION_COLOR = "#55D675"

# ---------------------------------------------------------------- animation
POSTURE = {}
BREATH_PERIOD_F = 45
BREATH_AMP = 1.0
CLIP_NAMES = ["idle", "walk", "alert", "run", "turn_left", "turn_right", "roar", "attack_antler_sweep",
              "attack_charge", "hit", "death", "rest"]
SEMANTIC = {"Idle": "idle", "Walk": "walk", "Run": "run", "Alert": "alert", "Attack": "attack_antler_sweep",
            "Hit": "hit", "Death": "death", "Roar": "roar"}
SERVER_EVENTS = {"creature_attack": "attack_antler_sweep", "antler_charge": "attack_charge"}


def clips(rig, sampler):
    import clips as C
    from anim import plan_feet, LEGS
    from qmath import q_euler, ease
    out = []
    pre = ID + "__"
    walk_off = {("Hind", "L"): 0.0, ("Front", "L"): 0.25, ("Hind", "R"): 0.5, ("Front", "R"): 0.75}
    gal_off = {("Hind", "L"): 0.0, ("Hind", "R"): 0.10, ("Front", "L"): 0.48, ("Front", "R"): 0.58}

    # idle: breathing, weight shift, a slow look and an ear flick; antlers stay stable
    out.append(C.standing(rig, globals(), pre + "idle", 90, {
        "pz": [(0, 0.0), (22, 0.012), (45, 0.0), (67, -0.012), (90, 0.0)],
        "pr": [(0, 0.0), (22, -0.01), (45, 0.0), (67, 0.01), (90, 0.0)],
        "hy": [(0, 0.0), (30, 0.07), (55, 0.07), (78, -0.02), (90, 0.0)],
        "n1y": [(0, 0.0), (30, 0.03), (55, 0.03), (90, 0.0)],
        "earp": [(0, 0.0), (40, 0.0), (44, 0.18), (49, 0.0), (90, 0.0)],
        "taily": [(0, 0.0), (20, 0.12), (45, -0.10), (70, 0.08), (90, 0.0)]}, loop=True))

    def walk_body(ph):
        w = 2 * np.pi * ph
        return {"py": -0.028 * np.cos(2 * w), "pr": 0.025 * np.sin(w), "pyw": 0.018 * np.sin(w),
                "pp": 0.012 * np.sin(2 * w), "cr": -0.02 * np.sin(w), "n1p": 0.035 * np.sin(2 * w + 0.6),
                "hp": -0.03 * np.sin(2 * w + 0.6), "gF": 0.05 * np.sin(w), "taily": 0.10 * np.sin(w + 1.0),
                "tailp": 0.04 * np.sin(2 * w)}
    out.append(C.locomotion(rig, globals(), pre + "walk", 36, 1.6, 0.66, walk_off, 0.22, walk_body))

    out.append(C.standing(rig, globals(), pre + "alert", 30, {
        "n1p": [(0, 0.0), (9, 0.20), (14, 0.17, "hold"), (30, 0.17, "hold")],
        "hp": [(0, 0.0), (9, -0.10), (30, -0.08, "hold")],
        "hy": [(0, 0.0), (10, 0.0), (30, 0.0)],
        "px": [(0, 0.0), (10, -0.05), (30, -0.04, "hold")],
        "py": [(0, 0.0), (10, 0.03), (30, 0.025, "hold")],
        "gF": [(0, 0.0), (12, -0.05), (30, -0.05, "hold")],
        "earp": [(0, 0.0), (6, 0.30), (30, 0.28, "hold")],
        "eary": [(0, 0.0), (6, -0.25), (30, -0.22, "hold")],
        "tailp": [(0, 0.0), (10, 0.35), (30, 0.30, "hold")]}, idle_overlay=False))

    def run_body(ph):
        w = 2 * np.pi * ph
        return {"py": 0.10 * np.sin(w - 0.4) - 0.04, "pp": 0.08 * np.sin(w + 0.6), "s1p": -0.06 * np.sin(w),
                "s2p": -0.05 * np.sin(w), "cp": 0.04 * np.sin(w + 0.4), "n1p": -0.10 * np.sin(w + 0.9) - 0.06,
                "hp": 0.08 * np.sin(w + 0.9), "gF": 0.14 * np.sin(w + 2.0), "gH": 0.10 * np.sin(w),
                "tailp": 0.18 * np.sin(w), "earp": -0.25}
    out.append(C.locomotion(rig, globals(), pre + "run", 21, 6.0, 0.36, gal_off, 0.40, run_body, reach=0.12))

    # turns: the controller yaws the actor 45 deg; feet step to stay planted in the world
    for name, sgn in (("turn_left", 1.0), ("turn_right", -1.0)):
        N = 24
        yaw = lambda fr, s=sgn, N=N: s * np.radians(45.0) * ease(fr / (N - 4.0))  # noqa: E731
        first = "L" if sgn > 0 else "R"
        second = "R" if sgn > 0 else "L"
        sw = {("Front", first): [(1, 9)], ("Front", second): [(5, 13)], ("Hind", first): [(9, 17)],
              ("Hind", second): [(13, 21)]}
        legs = plan_feet(rig, N, lambda fr: (0.0, 0.0, yaw(fr)), sw, lift=0.16)
        out.append(C.standing(rig, globals(), pre + name, N, {
            "n1y": [(0, 0.0), (6, 0.22 * sgn), (16, 0.10 * sgn), (24, 0.0)],
            "hy": [(0, 0.0), (6, 0.16 * sgn), (18, 0.04 * sgn), (24, 0.0)],
            "cy": [(0, 0.0), (8, 0.10 * sgn), (20, 0.0)],
            "s2y": [(0, 0.0), (10, 0.06 * sgn), (22, 0.0)],
            "pr": [(0, 0.0), (6, -0.03 * sgn), (16, 0.03 * sgn), (24, 0.0)],
            "taily": [(0, 0.0), (10, -0.25 * sgn), (24, 0.0)]},
            legs_fn=legs, motion={"yaw_deg": 45.0 * sgn, "yaw": [float(yaw(f)) for f in range(N + 1)]}))

    out.append(C.standing(rig, globals(), pre + "roar", 72, {
        "n1p": [(0, 0.0), (10, -0.10), (16, 0.30), (40, 0.32), (52, 0.12), (72, 0.0)],
        "n2p": [(0, 0.0), (10, -0.05), (16, 0.10), (40, 0.12), (72, 0.0)],
        "hp": [(0, 0.0), (10, -0.06), (16, 0.12), (40, 0.14), (56, 0.02), (72, 0.0)],
        "jaw": [(0, 0.0), (12, 0.02), (17, 0.42), (40, 0.40), (48, 0.10), (54, 0.0)],
        "nose": [(0, 0.0), (16, 0.06), (44, 0.06), (54, 0.0)],
        "cp": [(0, 0.0), (10, 0.04), (16, -0.06), (44, -0.05), (72, 0.0)],
        "px": [(0, 0.0), (10, -0.08), (17, 0.06), (44, 0.05), (72, 0.0)],
        "py": [(0, 0.0), (10, -0.03), (17, 0.04), (44, 0.03), (72, 0.0)],
        "gF": [(0, 0.0), (16, -0.08), (44, -0.07), (72, 0.0)],
        "earp": [(0, 0.0), (14, -0.40), (48, -0.38), (64, 0.0)],
        "belly": [(0, 0.0), (10, 0.03), (17, -0.02), (44, -0.02), (72, 0.0)],
        "tailp": [(0, 0.0), (16, 0.40), (48, 0.30), (72, 0.0)]},
        events=[{"event": "sound", "frame": 16, "time": 16 / 30}, {"event": "rune_pulse", "frame": 24, "time": 24 / 30}]))

    out.append(C.standing(rig, globals(), pre + "attack_antler_sweep", 45, {
        "n1p": [(0, 0.0), (12, -0.34), (18, -0.36), (22, -0.12), (27, 0.06), (45, 0.0)],
        "hp": [(0, 0.0), (12, -0.22), (18, -0.24), (22, -0.06), (27, 0.04), (45, 0.0)],
        "n1y": [(0, 0.0), (12, -0.26), (18, -0.28), (22, 0.18), (27, 0.32), (36, 0.10), (45, 0.0)],
        "hy": [(0, 0.0), (12, -0.20), (18, -0.22), (22, 0.20), (27, 0.30), (45, 0.0)],
        "hr": [(0, 0.0), (12, 0.12), (18, 0.14), (22, -0.18), (27, -0.24), (45, 0.0)],
        "cy": [(0, 0.0), (12, -0.10), (22, 0.10), (30, 0.06), (45, 0.0)],
        "px": [(0, 0.0), (12, -0.10), (18, -0.11), (22, 0.16), (27, 0.12), (45, 0.0)],
        "py": [(0, 0.0), (12, -0.05), (22, 0.0), (45, 0.0)],
        "pr": [(0, 0.0), (12, 0.04), (22, -0.05), (45, 0.0)],
        "gF": [(0, 0.0), (12, 0.08), (22, -0.08), (45, 0.0)],
        "earp": [(0, 0.0), (10, -0.35), (30, -0.3), (45, 0.0)],
        "taily": [(0, 0.0), (18, 0.25), (24, -0.35), (45, 0.0)]},
        events=[{"event": "windup", "frame": 0}, {"event": "whoosh", "frame": 19}, {"event": "contact", "frame": 22},
                {"event": "recovery", "frame": 27}],
        windows={"windup": [0, 18], "active": [18, 27], "recovery": [27, 45], "impact": 22}))

    # charge: lower antlers, explode forward (controller displacement), brake and back off
    N = 66
    dist = 2.4
    def charge_x(fr):
        if fr <= 21:
            return 0.0
        if fr <= 40:
            return dist * ease((fr - 21) / 19.0) ** 1.2
        if fr <= 46:
            return dist + 0.15 * np.sin(np.pi * (fr - 40) / 12.0)
        return (dist + 0.15 * np.sin(np.pi * 0.5)) * (1 - ease((fr - 46) / 20.0))
    sw = {("Hind", "L"): [(21, 27), (32, 38), (49, 55)], ("Hind", "R"): [(22, 28), (33, 39), (52, 58)],
          ("Front", "L"): [(24, 30), (35, 41), (55, 61)], ("Front", "R"): [(25, 31), (36, 42), (46, 52)]}
    legs = plan_feet(rig, N, lambda fr: (charge_x(fr), 0.0, 0.0), sw, lift=0.24)
    out.append(C.standing(rig, globals(), pre + "attack_charge", N, {
        "n1p": [(0, 0.0), (14, -0.40), (21, -0.42), (32, -0.38), (40, -0.30), (48, 0.10), (66, 0.0)],
        "hp": [(0, 0.0), (14, -0.24), (21, -0.26), (40, -0.20), (48, 0.06), (66, 0.0)],
        "px": [(0, 0.0), (14, -0.14), (21, -0.16), (26, 0.10), (40, 0.12), (46, -0.10), (56, -0.04), (66, 0.0)],
        "py": [(0, 0.0), (14, -0.08), (21, -0.09), (30, 0.02), (40, -0.02), (48, -0.06), (66, 0.0)],
        "pp": [(0, 0.0), (21, 0.03), (30, -0.04), (42, 0.0), (47, 0.07), (66, 0.0)],
        "gF": [(0, 0.0), (21, 0.06), (32, -0.08), (46, 0.12), (66, 0.0)],
        "earp": [(0, 0.0), (12, -0.4), (50, -0.3), (66, 0.0)],
        "tailp": [(0, 0.0), (21, 0.3), (40, 0.45), (66, 0.0)]},
        legs_fn=legs,
        events=[{"event": "windup", "frame": 0}, {"event": "launch", "frame": 21}, {"event": "contact", "frame": 34},
                {"event": "brake", "frame": 42}, {"event": "recovery", "frame": 46}],
        windows={"windup": [0, 21], "active": [21, 42], "recovery": [42, 66], "impact": 34},
        motion={"forward_m": [float(charge_x(f)) for f in range(N + 1)]}))

    out.append(C.standing(rig, globals(), pre + "hit", 18, {
        "px": [(0, 0.0), (4, -0.08), (10, -0.03), (18, 0.0)],
        "pr": [(0, 0.0), (4, 0.035), (12, -0.01), (18, 0.0)],
        "n1p": [(0, 0.0), (4, 0.10), (10, 0.02), (18, 0.0)],
        "hp": [(0, 0.0), (4, 0.10), (12, -0.02), (18, 0.0)],
        "hy": [(0, 0.0), (4, -0.08), (18, 0.0)],
        "earp": [(0, 0.0), (3, -0.5), (14, -0.2), (18, 0.0)],
        "tailp": [(0, 0.0), (4, 0.3), (18, 0.0)]}, idle_overlay=False,
        events=[{"event": "hit", "frame": 2}]))

    out.append(death(rig, sampler, pre + "death", 84))

    # rest: relaxed standing, head low, right hind hoof resting on its tip, slow breathing
    rest_legs = C.leg_keys(rig, {("Hind", "R"): {"dy": [(0, 0.05)], "dx": [(0, 0.10)], "toe": [(0, -0.75)],
                                                   "foot": [(0, 0.20)]}}, 120)
    out.append(C.standing(rig, dict(globals(), BREATH_PERIOD_F=60, BREATH_AMP=1.5), pre + "rest", 120, {
                   "n1p": [(0, -0.26)], "hp": [(0, 0.14)], "py": [(0, -0.03)], "pr": [(0, -0.025)],
                   "gH": [(0, 0.0)], "earp": [(0, -0.15), (70, -0.15), (74, 0.05), (80, -0.15), (120, -0.15)],
                   "eary": [(0, 0.20)], "tailp": [(0, -0.12)],
                   "hy": [(0, 0.0), (60, 0.05), (120, 0.0)]}, loop=True, legs_fn=rest_legs))
    return out


def death(rig, sampler, name, N):
    """Buckle (front first), roll onto the side, settle; antlers kept above the ground (clips.death)."""
    import clips as C
    return C.death(rig, globals(), sampler, name, N, {
        "pp": [(0, 0.0), (14, -0.16), (24, -0.12), (40, -0.02), (84, 0.0)],
        "pr": [(0, 0.0), (18, 0.05), (26, 0.30), (40, 1.05), (50, 1.30), (58, 1.36), (84, 1.36, "hold")],
        "py": [(0, 0.0), (12, -0.25), (22, -0.55), (40, -0.95), (84, -1.0, "hold")],
        "px": [(0, 0.0), (14, 0.05), (40, -0.05), (84, -0.05)],
        "n1p": [(0, 0.0), (12, -0.15), (26, -0.05), (44, -0.20), (60, -0.32), (84, -0.32, "hold")],
        "n1r": [(0, 0.0), (30, -0.10), (50, -0.25), (60, -0.28), (84, -0.28, "hold")],
        "n1y": [(0, 0.0), (40, 0.10), (60, 0.25), (84, 0.25)],
        "hp": [(0, 0.0), (20, -0.20), (50, -0.10), (84, -0.08)],
        "hr": [(0, 0.0), (40, -0.10), (60, -0.15), (84, -0.15, "hold")],
        "jaw": [(0, 0.0), (10, 0.20), (30, 0.10), (60, 0.06), (84, 0.06)],
        "s1r": [(0, 0.0), (40, 0.08), (84, 0.10)], "cr": [(0, 0.0), (40, 0.05), (84, 0.06)],
        "earp": [(0, 0.0), (16, -0.5), (84, -0.6)], "tailp": [(0, 0.0), (30, -0.4), (84, -0.5)],
        "belly": [(0, 0.0), (64, 0.02), (72, -0.01), (84, 0.0)]},
        {"UpperLeg_Front": 0.35, "LowerLeg_Front": -0.55, "Foot_Front": -0.6, "Toe_Front": -0.4,
         "UpperLeg_Hind": -0.30, "LowerLeg_Hind": 0.55, "Foot_Hind": -0.35, "Toe_Hind": -0.3},
        buckle_end=20, fk_start=18, fk_end=34, lie_frame=40, search_bone="Neck_02", search_range=(0.0, -0.9))


LEGS_ALL = (("Front", "L", -1), ("Front", "R", 1), ("Hind", "L", -1), ("Hind", "R", 1))
