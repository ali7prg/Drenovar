"""Лесной Велькор (velkor): forest warden, sculpted to the kit sheet velkor_reference.png (front / left side /
rear views read at 112 px per metre, where the sheet's own labels agree: withers 2.1 m, length 3.6 m nose to
tail tip). Wolf head held level, heavy maned neck, shingled bark plates with moss over withers and back,
antler crown sweeping back over the body (six tines a side), long chest mane, bushy hanging tail,
thick shaggy legs on cloven hooves. Rune on the shoulders only, as on the sheet.
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
    "joints": [(0.62, 1.80, 0.22), (0.92, 1.36, 0.40), (0.76, 0.98, 0.39), (0.86, 0.48, 0.37), (0.88, 0.20, 0.37),
               (1.00, 0.0, 0.37)]}
HIND = {
    "joints": [(-0.90, 1.60, 0.20), (-1.00, 1.36, 0.38), (-0.70, 0.98, 0.40), (-1.10, 0.58, 0.37), (-1.02, 0.20, 0.36),
               (-0.90, 0.0, 0.36)]}


def mirror(p, s):
    return (p[0], p[1], p[2] * s if s < 0 else p[2])


# idle stance read off the side sheet (hoof contacts): near (left) fore forward, far fore back, far hind forward,
# near hind back - the views are compared in this pose
IDLE_STANCE = {("Front", "L"): {"dx": [(0, 0.06)]}, ("Front", "R"): {"dx": [(0, -0.20)]},
               ("Hind", "L"): {"dx": [(0, -0.22)]}, ("Hind", "R"): {"dx": [(0, 0.28)]}}


def side(p, s):
    return np.array([p[0], p[1], abs(p[2]) * s])


def skeleton():
    sk = Skeleton()
    sk.add("MotionRoot", None, (0, 0, 0))
    sk.add("Pelvis", "MotionRoot", (-0.92, 1.58, 0))
    sk.add("Spine_01", "Pelvis", (-0.42, 1.68, 0))
    sk.add("Spine_02", "Spine_01", (0.08, 1.74, 0))
    sk.add("Chest", "Spine_02", (0.56, 1.78, 0))
    sk.add("Neck_01", "Chest", (0.98, 1.78, 0))
    sk.add("Neck_02", "Neck_01", (1.24, 1.94, 0))
    sk.add("Head", "Neck_02", (1.46, 2.16, 0), tail=(2.00, 2.06, 0))
    sk.add("Jaw", "Head", (1.60, 2.06, 0), tail=(1.92, 1.98, 0))
    sk.add("Nose", "Head", (1.86, 2.10, 0), tail=(2.00, 2.07, 0))
    for nm, s in SIDES:
        sk.add(f"Ear_{nm}", "Head", (1.42, 2.32, 0.13 * s), tail=(1.27, 2.47, 0.21 * s))
        sk.add(f"Antler_{nm}", "Head", (1.47, 2.38, 0.10 * s), tail=(0.40, 2.74, 0.90 * s))
    sk.add("Mane_01", "Neck_01", (1.16, 1.40, 0), tail=(1.20, 1.02, 0))
    sk.add("Mane_02", "Neck_02", (1.40, 1.80, 0), tail=(1.42, 1.50, 0))
    sk.add("Belly", "Spine_02", (-0.05, 1.10, 0), tail=(-0.05, 0.96, 0))
    for nm, s in SIDES:
        leg_bones(sk, "Front", "Chest", None, [side(j, s) for j in FRONT["joints"]], nm)
        leg_bones(sk, "Hind", "Pelvis", None, [side(j, s) for j in HIND["joints"]], nm)
    sk.add("Tail_01", "Pelvis", (-1.22, 1.70, 0))
    sk.add("Tail_02", "Tail_01", (-1.36, 1.54, 0))
    sk.add("Tail_03", "Tail_02", (-1.48, 1.36, 0))
    sk.add("Tail_04", "Tail_03", (-1.56, 1.18, 0), tail=(-1.61, 1.02, 0))
    # sockets (effects and debug only)
    sk.socket("socket_head", "Head", (1.58, 2.30, 0))
    sk.socket("socket_mouth", "Jaw", (1.92, 2.00, 0))
    sk.socket("socket_chest", "Chest", (1.14, 1.28, 0))
    for nm, s in SIDES:
        sk.socket(f"socket_foot_front_{nm.lower()}", f"Toe_Front_{nm}", side(FRONT["joints"][5], s))
        sk.socket(f"socket_foot_hind_{nm.lower()}", f"Toe_Hind_{nm}", side(HIND["joints"][5], s))
        sk.socket(f"socket_antler_{nm.lower()}", f"Antler_{nm}", (0.80, 3.02, 0.84 * s))
    sk.socket("socket_tail_tip", "Tail_04", (-1.61, 1.02, 0))
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
    # deep wolf chest, long body, croup a little lower than the withers (sheet side view)
    P += [Prim("ellipsoid", "Chest", k=0.0, c=(0.45, 1.50, 0), r=(0.74, 0.50, 0.47), name="ribcage"),
          Prim("ellipsoid", "Chest", k=0.15, c=(0.95, 1.34, 0), r=(0.36, 0.44, 0.42), name="brisket"),
          Prim("ellipsoid", "Chest", k=0.18, c=(0.62, 1.86, 0), r=(0.54, 0.18, 0.30), name="withers"),
          Prim("ellipsoid", "Spine_02", k=0.18, c=(-0.22, 1.56, 0), r=(0.52, 0.38, 0.41), name="waist"),
          Prim("ellipsoid", "Spine_01", k=0.18, c=(-0.55, 1.60, 0), r=(0.42, 0.32, 0.40), name="loin"),
          Prim("ellipsoid", "Pelvis", k=0.18, c=(-0.92, 1.48, 0), r=(0.42, 0.36, 0.40), name="rump"),
          Prim("ellipsoid", "Pelvis", k=0.14, c=(-0.90, 1.64, 0), r=(0.40, 0.12, 0.28), name="croup"),
          Prim("ellipsoid", "Belly", k=0.20, c=(0.10, 1.20, 0), r=(0.48, 0.18, 0.36), name="belly")]
    # short heavy neck carrying the head forward at back height
    P += [Prim("cone", "Neck_01", k=0.16, a=(0.90, 1.70, 0), b=(1.22, 1.92, 0), ra=0.46, rb=0.36, name="neck1"),
          Prim("cone", "Neck_02", k=0.10, a=(1.22, 1.92, 0), b=(1.46, 2.14, 0), ra=0.36, rb=0.27, name="neck2"),
          Prim("ellipsoid", "Mane_02", k=0.14, c=(1.24, 1.72, 0), r=(0.22, 0.32, 0.26), name="throat")]
    # wolf head: broad skull, long tapering muzzle, black nose, held level
    P += [Prim("ellipsoid", "Head", k=0.08, c=(1.51, 2.23, 0), r=(0.31, 0.20, 0.21), name="cranium"),
          Prim("ellipsoid", "Head", k=0.06, c=(1.47, 2.33, 0), r=(0.23, 0.10, 0.16), name="crown"),
          Prim("cone", "Nose", k=0.06, a=(1.68, 2.19, 0), b=(1.97, 2.09, 0), ra=0.125, rb=0.060, name="muzzle"),
          Prim("ellipsoid", "Head", k=0.04, c=(1.80, 2.20, 0), r=(0.18, 0.052, 0.09), R=rot_z(-0.34),
               name="nasal"),
          Prim("sphere", "Nose", k=0.02, mat="nose", c=(1.98, 2.09, 0), r=0.048, name="nosepad"),
          Prim("cone", "Jaw", k=0.04, a=(1.60, 2.05, 0), b=(1.92, 2.005, 0), ra=0.09, rb=0.042, name="jaw"),
          Prim("sphere", "Jaw", k=0.03, mat="skin", c=(1.94, 2.005, 0), r=0.044, name="chin")]
    for nm, s in SIDES:
        P += [Prim("ellipsoid", "Jaw", k=0.06, c=(1.58, 2.10, 0.13 * s), r=(0.16, 0.11, 0.08), name=f"cheek{nm}"),
              Prim("ellipsoid", "Head", k=0.04, c=(1.60, 2.20, 0.155 * s), r=(0.12, 0.05, 0.05), name=f"zygoma{nm}"),
              Prim("ellipsoid", "Head", k=0.035, c=(1.68, 2.32, 0.095 * s), r=(0.12, 0.052, 0.07), R=rot_z(-0.10),
                   name=f"brow{nm}"),
              Prim("cone", "Nose", k=0.03, mat="skin", a=(1.76, 2.035, 0.10 * s), b=(1.93, 2.025, 0.048 * s),
                   ra=0.036, rb=0.025, name=f"lip{nm}"),
              Prim("sphere", "Head", k=0.015, neg=True, c=(1.718, 2.252, 0.124 * s), r=0.038, name=f"socket{nm}")]
        ec = np.array([1.38, 2.40, 0.20 * s])
        Re = rot_x(-0.45 * s) @ rot_z(0.42)
        P += [Prim("ellipsoid", f"Ear_{nm}", k=0.03, c=ec, r=(0.055, 0.16, 0.085), R=Re, name=f"ear{nm}"),
              Prim("cone", f"Ear_{nm}", k=0.03, a=ec, b=ec + Re @ np.array([0.0, 0.19, 0.0]), ra=0.058, rb=0.012,
                   name=f"eartip{nm}"),
              Prim("ellipsoid", f"Ear_{nm}", k=0.01, neg=True, mat="skin", c=ec + Re @ np.array([0.042, 0.0, 0.0]),
                   r=(0.032, 0.12, 0.058), R=Re, name=f"earcav{nm}")]
        P += [Prim("ellipsoid", f"Shoulder_{nm}", k=0.14, c=side((0.78, 1.50, 0.34), s), r=(0.36, 0.48, 0.22),
                   R=rot_z(-0.42), name=f"scapula{nm}"),
              Prim("ellipsoid", f"UpperLeg_Front_{nm}", k=0.12, c=side((0.95, 1.30, 0.37), s), r=(0.23, 0.23, 0.18),
                   name=f"deltoid{nm}"),
              Prim("ellipsoid", f"UpperLeg_Hind_{nm}", k=0.16, c=side((-0.98, 1.30, 0.34), s), r=(0.40, 0.46, 0.21),
                   R=rot_z(0.22), name=f"haunch{nm}")]
        P += leg_prims("Front", nm, s, FRONT["joints"])
        P += leg_prims("Hind", nm, s, HIND["joints"])
    P += chain([(-1.22, 1.70, 0), (-1.36, 1.54, 0), (-1.48, 1.36, 0), (-1.56, 1.18, 0), (-1.61, 1.02, 0)],
               [0.12, 0.16, 0.17, 0.15, 0.08], None, k=0.06, mat="fur_long", name="tail",
               bones=["Tail_01", "Tail_02", "Tail_03", "Tail_04"])
    return P


def body_bone(p):
    x, y, z = p
    if x > 1.40:
        return "Head" if (y > 2.02 or x > 1.62) else "Neck_02"
    if x > 0.98:
        return "Mane_01" if y < 1.58 else "Neck_01"
    if y < 1.18:
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
    seeds = scatter_on(core, (1.02, 1.56, 0), (0.22, 0.34, 0.42), 84, rng)
    P += locks(core, seeds, lambda p, n: np.array([-0.60, -1.0, 0]),
               lambda p: 0.18 + 0.16 * np.clip((1.85 - p[1]) / 0.6, 0, 1), 0.14, body_bone,
               gravity=0.55, lift=0.04, rng=rng, droop=0.5)
    # neck ruff laid back
    seeds = scatter_on(core, (1.22, 1.92, 0), (0.30, 0.30, 0.40), 66, rng)
    P += locks(core, seeds, lambda p, n: np.array([-1.0, -0.70, 0]), 0.32, 0.14, body_bone, lift=0.16, rng=rng,
               droop=0.30)
    # shoulder, flank and back shag
    seeds = scatter_on(core, (0.10, 1.58, 0), (1.05, 0.34, 0.56), 60, rng)
    P += locks(core, seeds, back, 0.26, 0.11, body_bone, thick=0.28, lift=0.24, rng=rng, droop=0.25)
    # belly fringe and haunch feathering
    seeds = scatter_on(core, (0.15, 1.05, 0), (0.85, 0.10, 0.40), 48, rng)
    P += locks(core, seeds, hang, 0.18, 0.12, body_bone, gravity=0.45, lift=0.06, rng=rng, droop=0.45)
    for nm, s in SIDES:
        seeds = scatter_on(core, side((-1.18, 1.18, 0.30), s), (0.22, 0.30, 0.16), 16, rng)
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
    seeds = scatter_on(core, (-1.44, 1.38, 0), (0.20, 0.32, 0.17), 40, rng)
    P += locks(core, seeds, lambda p, n: np.array([-0.30, -1.0, 0]), 0.30, 0.12,
               lambda p: "Tail_04" if p[1] < 1.22 else ("Tail_03" if p[1] < 1.45 else "Tail_02"), gravity=0.30,
               lift=0.20, rng=rng, droop=0.3)
    # moss drapes along the flanks under the bark plates
    return Part("body", P, band=0.09)


# ---------------------------------------------------------------- antlers
def antler_prims(s):
    """Sheet crown: the beam leaves the skull, sweeps out and back over the withers almost level; a brow tine
    points forward over the muzzle, five tall tines rise along the beam, tips curling forward."""
    nm = "L" if s < 0 else "R"
    bone = f"Antler_{nm}"
    base = np.array([1.47, 2.38, 0.10 * s])
    beam = bezier(base, np.array([1.40, 2.58, 0.32 * s]), np.array([0.98, 2.62, 0.70 * s]),
                  np.array([0.40, 2.98, 0.92 * s]), 16)
    radii = np.linspace(0.062, 0.026, len(beam))
    P = [Prim("ellipsoid", bone, k=0.0, mat="antler", c=base + np.array([0, 0.03, 0.01 * s]), r=(0.08, 0.035, 0.08),
              name="burr")]
    P += chain(list(beam), list(radii), bone, k=0.02, mat="antler", name="beam")
    tines = [(0.10, (0.62, 0.78, -0.06 * s), 0.40),
             (0.28, (0.40, 0.92, 0.02 * s), 0.36),
             (0.45, (0.20, 1.00, 0.05 * s), 0.40),
             (0.62, (0.10, 1.00, 0.08 * s), 0.37),
             (0.79, (0.02, 1.00, 0.12 * s), 0.33),
             (0.96, (-0.06, 0.95, 0.20 * s), 0.28)]
    for i, (f, d, L) in enumerate(tines):
        k = f * (len(beam) - 1)
        i0 = int(k)
        t = k - i0
        root = beam[i0] * (1 - t) + beam[min(i0 + 1, len(beam) - 1)] * t
        r0 = np.interp(f, np.linspace(0, 1, len(beam)), radii) * 0.62
        d = np.asarray(d, float)
        d /= np.linalg.norm(d)
        # sheet tines: rise, then hook forward and a little inward toward the tip
        curve = bezier(root, root + d * L * 0.42, root + d * L * 0.80 + np.array([0.08, 0.0, -0.03 * s]),
                       root + d * L * 0.88 + np.array([0.16, -0.02, -0.06 * s]), 9)
        P += chain(list(curve), list(np.linspace(r0, 0.008, len(curve))), bone, k=0.02, mat="antler", name=f"tine{i}")
    rng = np.random.default_rng(11 if s < 0 else 12)
    from common import _frame
    for i in range(22):
        f = 0.12 + 0.84 * rng.random()
        k = f * (len(beam) - 1)
        root = beam[int(k)] + np.array([0, -0.03, 0])
        L = 0.10 + 0.20 * rng.random()
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
    rows = [(1.04, 3, 0.36, "Chest"), (0.86, 4, 0.48, "Chest"), (0.62, 4, 0.50, "Chest"), (0.38, 4, 0.48, "Chest"),
            (0.14, 4, 0.46, "Spine_02"), (-0.10, 3, 0.44, "Spine_02"), (-0.34, 3, 0.42, "Spine_01"),
            (-0.58, 3, 0.40, "Spine_01"), (-0.82, 3, 0.34, "Pelvis")]
    for r, (x, n, L, bone) in enumerate(rows):
        for i in range(n):
            u = (i - (n - 1) / 2)
            ang = u * 0.62  # around the back, radians from the top
            start = np.array([x + rng.normal(0, 0.025) + (0.08 if i % 2 else 0), 2.0 + 1.2 * np.cos(ang),
                              1.2 * np.sin(ang)])
            specs.append((start, L * (0.9 + 0.2 * rng.random()), L * 0.78, bone))
    for nm, s in SIDES:
        for (x, y, z, L) in ((0.88, 1.80, 0.50, 0.38), (0.62, 1.78, 0.55, 0.36), (0.36, 1.74, 0.56, 0.34)):
            specs.append((np.array([x, y + 0.6, z * s * 2.0]), L, L * 0.8, f"Shoulder_{nm}"))
    starts = np.array([sp[0] for sp in specs], np.float32)
    pts, nrm = surface_points(core, starts, steps=12)
    P = []
    for k, ((st, L, W, bone), p, n) in enumerate(zip(specs, pts, nrm)):
        n = n / np.linalg.norm(n)
        P += scale_plate(p + n * 0.03, n, np.array([-1.0, -0.10, 0]), L, W, 0.030 + 0.008 * rng.random(), bone,
                         "bark", tilt=0.20 + rng.normal(0, 0.04), yaw=rng.normal(0, 0.12), name=f"plate{k}")
    return P


def eye_part():
    P = []
    for nm, s in SIDES:
        P.append(Prim("sphere", "Head", k=0.0, mat="eye", c=(1.712, 2.252, 0.118 * s), r=0.034, name=f"eye{nm}"))
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


_hang = lambda p, n: np.array([-0.45, -1.0, 0])  # noqa: E731
_back = lambda p, n: np.array([-1.0, -0.30, 0])  # noqa: E731
FUR_KEEP = {0: 0.75, 1: 0.45, 2: 0.12}   # shaggy everywhere on the sheet: more cards than the default
FUR_CARDS = [  # sheet: shaggy grey-brown coat everywhere, long pale chest mane, leg feathering, moss drips
    {"centre": (1.10, 1.62, 0), "radii": (0.32, 0.45, 0.42), "count": 260, "length": 0.40, "width": 0.13,
     "flow": _hang, "lift": 0.15, "gravity": 0.35, "droop": 0.2, "crossed": True, "tip": "#c4ae98",
     "root_k": 0.75},                                                                               # chest mane
    {"centre": (1.20, 2.00, 0), "radii": (0.30, 0.28, 0.38), "count": 120, "length": 0.30, "width": 0.11,
     "flow": lambda p, n: np.array([-1.0, -0.5, 0]), "lift": 0.25, "droop": 0.15, "crossed": True,
     "tip": "#a8927a"},                                                                             # neck ruff
    {"centre": (0.00, 1.45, 0), "radii": (1.10, 0.40, 0.56), "count": 300, "length": 0.24, "width": 0.10,
     "flow": _back, "lift": 0.15, "droop": 0.2, "tip": "#a3907e"},                                  # back, flanks
    {"centre": (0.15, 1.06, 0), "radii": (0.85, 0.14, 0.42), "count": 120, "length": 0.26, "width": 0.09,
     "flow": lambda p, n: np.array([-0.3, -1.0, 0]), "lift": 0.05, "gravity": 0.45, "droop": 0.25,
     "crossed": True, "tip": "#a39079"},                                                            # belly fringe
    {"centre": (-1.00, 1.25, 0), "radii": (0.40, 0.40, 0.48), "count": 140, "length": 0.22, "width": 0.09,
     "flow": lambda p, n: np.array([-0.6, -1.0, 0]), "lift": 0.15, "droop": 0.2, "tip": "#9d8770"},  # haunches
    {"centre": (0.82, 0.72, 0), "radii": (0.20, 0.46, 0.50), "count": 110, "length": 0.20, "width": 0.08,
     "flow": lambda p, n: np.array([-0.3, -1.0, 0]), "lift": 0.15, "gravity": 0.2, "droop": 0.1,
     "crossed": True, "tip": "#a8957f"},                                                            # forelegs
    {"centre": (-0.95, 0.68, 0), "radii": (0.26, 0.40, 0.50), "count": 100, "length": 0.18, "width": 0.08,
     "flow": lambda p, n: np.array([-0.4, -1.0, 0]), "lift": 0.15, "droop": 0.1, "crossed": True,
     "tip": "#a08b74"},                                                                             # hind legs
    {"centre": (0.00, 0.20, 0), "radii": (1.10, 0.10, 0.50), "count": 70, "length": 0.14, "width": 0.07,
     "flow": lambda p, n: np.array([0.0, -1.0, 0]), "lift": 0.3, "droop": 0.05, "crossed": True,
     "tip": "#b5a38d"},                                                                             # fetlock tufts
    {"centre": (-1.45, 1.36, 0), "radii": (0.22, 0.36, 0.18), "count": 120, "length": 0.36, "width": 0.12,
     "flow": lambda p, n: np.array([-0.3, -1.0, 0]), "lift": 0.25, "droop": 0.2, "crossed": True,
     "tip": "#b09b84"},                                                                             # tail brush
    {"centre": (1.55, 2.16, 0), "radii": (0.16, 0.14, 0.22), "count": 50, "length": 0.12, "width": 0.06,
     "flow": lambda p, n: np.array([-1.0, -0.2, 0]), "lift": 0.25, "droop": 0.05, "tip": "#a69280"},  # cheeks
    {"centre": (0.10, 1.80, 0), "radii": (1.05, 0.12, 0.58), "count": 70, "length": 0.30, "width": 0.05,
     "flow": lambda p, n: np.array([-0.1, -1.0, 0]), "lift": 0.05, "gravity": 0.9, "droop": 0.3,
     "crossed": True, "root": "#5f5a1e", "tip": "#a8b545"}]                                         # moss drips

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
        {"name": "body", "part": body, "material": "body", "rigid": None, "faces": (26000, 9500, 2800)},
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
    # one large spiral-and-stem rune on each shoulder (the sheet shows the left one; no flank runes)
    RUNES.append(((0.86, 1.66, 0.52 * _s), (0, 0, _s), (0.10, 1, 0), 0.13))


def default_flow(P, part):
    x, y = P[:, 0], P[:, 1]
    back = np.array([-1.0, -0.25, 0.0], np.float32)
    down = np.array([-0.25, -1.0, 0.0], np.float32)
    w_leg = sstep(1.10, 0.85, y)[:, None]
    w_chest = (sstep(0.95, 1.20, x) * sstep(2.00, 1.80, y))[:, None]
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
    col = mix(lin("#7a6250"), lin("#6a5444"), sstep(0.1, 0.8, N[:, 1]))
    col = mix(col, lin("#9a8068"), sstep(-0.1, -0.7, N[:, 1]) * sstep(0.90, 1.15, y))
    col = mix(col, lin("#64574a"), sstep(0.60, 0.25, y) * 0.5)
    col = mix(col, lin("#7e6a58"), sstep(1.70, 1.90, x) * sstep(1.95, 2.15, y))      # grey-brown muzzle
    col = mix(col, lin("#5a463c"), sstep(1.40, 1.60, x) * sstep(2.22, 2.36, y))      # darker brow
    col = mix(col, lin("#5c3c2a"), sstep(1.20, 1.40, x) * sstep(2.30, 2.40, y) * sstep(0.2, 0.7, np.abs(N[:, 2])))
    patch = noise.fbm(P * 2.2, 3, seed=21)
    col = col * (1.0 + 0.16 * patch[:, None])
    # long fur: cream tips; the chest and throat mane is the palest part of the coat
    mane = mix(lin("#6e5848"), lin("#c2a68a"), sstep(-0.2, 0.9, h0))
    chest = sstep(0.95, 1.15, x) * sstep(2.0, 1.8, y)
    mane = mix(mane, mix(lin("#8a6e56"), lin("#d4bc9c"), sstep(-0.2, 0.9, h0)), chest)
    col = mix(col, mane, w["fur_long"])
    col = col * (0.70 + 0.40 * sstep(-1.0, 1.0, h0))[:, None] * 0.92
    col = col * np.array([1.20, 1.40, 1.58], np.float32)[None, :]   # sheet coat: light grey-brown, not red-brown
    skin = mix(lin("#4c3a33"), lin("#6a4c42"), sstep(0.5, -0.5, N[:, 1]))
    col = mix(col, skin, w["skin"])
    col = mix(col, lin("#1c1916"), w["nose"])
    hoof = mix(lin("#3a2e26"), lin("#5a4636"), sstep(0.035, 0.0, y) + 0.3 * sstep(0.0, 1.0, noise.perlin(P * 40, 9)))
    col = mix(col, hoof, w["hoof"])
    mossc = mix(lin("#8c8030"), lin("#c8bc50"), sstep(-0.4, 0.6, noise.fbm(P * 9, 3, seed=4)))
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
    ant = mix(lin("#e0cca6"), lin("#b0946c"), sstep(0.012, 0.032, rad))   # sheet: aged ivory tines, tan beam
    ant = mix(ant, lin("#6e5638"), sstep(0.050, 0.066, rad))
    ant = ant * (0.86 + 0.18 * groove)[:, None]
    mm = moss_mask(P, N, 0.22, seed=12) * sstep(0.045, 0.065, rad)
    mossc = mix(lin("#8c8030"), lin("#c8bc50"), sstep(-0.4, 0.6, noise.fbm(P * 11, 3, seed=6)))
    ant = mix(ant, mossc, mm)
    # bark plates: cracked dark bark, lighter worn edges, moss tops with a few golden leaves
    bh, crack, cid = bark(P, flow, 1.0)
    bk = mix(lin("#7a5a40"), lin("#5e4430"), sstep(0.2, 0.8, cid))
    bk = mix(bk, lin("#22170f"), crack)
    edge = sstep(0.35, 0.0, np.abs(N[:, 1]))
    bk = mix(bk, lin("#b0926e"), edge * 0.7 * (1 - crack))
    bm = moss_mask(P, N, 0.55, seed=14)
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
        c = np.array([1.712, 2.252, 0.118 * s], np.float32)
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
                l, g = rune_field(P, N, [((cx, 1.82, 0.56 * s), (0, 0.6, s), (-0.2, 1, 0), 0.10)])
                cl_line = np.maximum(cl_line, l)
        cl_line *= carved_w
        col = mix(col, col * 0.45, cl_line)
        em += lin("#55d675")[None, :] * cl_line[:, None]
    rough = (w["antler"] * (0.72 + 0.16 * (1 - groove)) + w["bark"] * (0.90 - 0.05 * edge) + w["moss"] * 0.95
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
        "taily": [(0, 0.0), (20, 0.12), (45, -0.10), (70, 0.08), (90, 0.0)]}, loop=True,
        legs_fn=C.leg_keys(rig, IDLE_STANCE, 90)))

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
    stride = plan_feet(rig, N, lambda fr: (charge_x(fr), 0.0, 0.0), sw, lift=0.24)

    def legs(fr, prm):
        """Sheet 'explosive charge': in the first bounds the forelegs reach far forward and the hind legs drive
        out behind (on top of the planned steps, only while the feet are off the ground)."""
        out_legs = stride(fr, prm)
        if 21 <= fr <= 32:
            ext = np.sin(np.pi * (fr - 21) / 11.0) ** 0.7
            for k in out_legs:
                reach = 0.52 if k[0] == "Front" else -0.62
                out_legs[k] = dict(out_legs[k], tip=out_legs[k]["tip"] + np.array([reach * ext, 0.16 * ext, 0.0]),
                                   toe=out_legs[k].get("toe", 0.0) + (0.4 if k[0] == "Front" else -0.7) * ext)
        return out_legs
    out.append(C.standing(rig, globals(), pre + "attack_charge", N, {
        "n1p": [(0, 0.0), (14, -0.40), (21, -0.42), (31, -0.40), (35, -0.20), (40, -0.24), (48, 0.10), (66, 0.0)],
        "hp": [(0, 0.0), (14, -0.24), (21, -0.26), (31, -0.26), (35, 0.04), (40, -0.06), (48, 0.06), (66, 0.0)],
        "n1y": [(0, 0.0), (29, 0.0), (31, -0.14), (35, 0.20), (40, 0.14), (48, 0.0), (66, 0.0)],
        "hy": [(0, 0.0), (29, 0.0), (31, -0.26), (35, 0.32), (40, 0.24), (48, 0.02), (66, 0.0)],
        "hr": [(0, 0.0), (29, 0.0), (31, 0.12), (35, -0.24), (40, -0.12), (48, 0.0), (66, 0.0)],
        "px": [(0, 0.0), (14, -0.14), (21, -0.16), (26, 0.10), (40, 0.12), (46, -0.10), (56, -0.04), (66, 0.0)],
        "py": [(0, 0.0), (14, -0.08), (21, -0.09), (30, -0.03), (40, -0.03), (48, -0.06), (66, 0.0)],
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
