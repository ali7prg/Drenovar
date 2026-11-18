"""Тенерис (tenerys): twilight predator, sculpted to the kit sheet tenerys_reference.png (front / left side /
rear read at 127 px per metre, the scale that best fits the sheet labels shoulder 1.55, body 2.80, tail 1.15).
Tall body with a spiky charcoal mane over neck, shoulders and back, tall pointed ears, sabre fangs below the
lip, long drooping bushy tail, big paws with long claws. Claws <= 0.13 m, four toes, rigid claws.
"""
import numpy as np

from sdf import Prim, Part, chain, bezier, rot_x, rot_y, rot_z
from rig import Skeleton
from common import SIDES, leg_bones, locks, scatter_on, surface_points, _frame

ID = "tenerys"
NAME = "Тенерис"
VOXEL_BODY = 0.009
VOXEL_RIGID = 0.0035
BAKE_EXTRUSION = 0.015
BAKE_RAY = 0.04
AO_SAMPLES = 40
AO_DISTANCE = 0.35

FRONT = {"joints": [(0.50, 1.55, 0.15), (0.62, 1.22, 0.29), (0.42, 0.80, 0.30), (0.38, 0.25, 0.30),
                    (0.47, 0.08, 0.30), (0.68, 0.0, 0.30)]}
HIND = {"joints": [(-0.90, 1.40, 0.14), (-1.02, 1.20, 0.26), (-0.75, 0.86, 0.29), (-1.22, 0.53, 0.27),
                   (-1.13, 0.09, 0.27), (-0.99, 0.0, 0.27)]}   # high hock (sheet), long thigh + shin (walk reach)


# idle stance read off the side sheet (paw contacts): near (left) fore forward, far fore back, far hind forward,
# near hind back - the views are compared in this pose
IDLE_STANCE = {("Front", "L"): {"dx": [(0, 0.08)]}, ("Front", "R"): {"dx": [(0, -0.26)]},
               ("Hind", "L"): {"dx": [(0, -0.20)]}, ("Hind", "R"): {"dx": [(0, 0.26)]}}


def side(p, s):
    return np.array([p[0], p[1], abs(p[2]) * s])


def skeleton():
    sk = Skeleton()
    sk.add("MotionRoot", None, (0, 0, 0))
    sk.add("Pelvis", "MotionRoot", (-0.90, 1.40, 0))
    sk.add("Spine_01", "Pelvis", (-0.48, 1.45, 0))
    sk.add("Spine_02", "Spine_01", (0.02, 1.50, 0))
    sk.add("Chest", "Spine_02", (0.44, 1.52, 0))
    sk.add("Neck_01", "Chest", (0.86, 1.52, 0))
    sk.add("Neck_02", "Neck_01", (1.04, 1.62, 0))
    sk.add("Head", "Neck_02", (1.16, 1.70, 0), tail=(1.53, 1.56, 0))
    sk.add("Jaw", "Head", (1.22, 1.58, 0), tail=(1.50, 1.47, 0))
    sk.add("Tongue", "Jaw", (1.28, 1.55, 0), tail=(1.44, 1.51, 0))
    sk.add("Nose", "Head", (1.42, 1.61, 0), tail=(1.53, 1.56, 0))
    sk.add("Throat", "Neck_02", (1.02, 1.44, 0), tail=(1.12, 1.48, 0))
    for nm, s in SIDES:
        sk.add(f"Ear_{nm}", "Head", (1.13, 1.88, 0.11 * s), tail=(1.14, 2.26, 0.17 * s))
        sk.add(f"Cheek_{nm}", "Head", (1.30, 1.61, 0.07 * s), tail=(1.40, 1.59, 0.06 * s))
    sk.add("Mane_01", "Neck_01", (0.88, 1.72, 0), tail=(0.70, 1.88, 0))
    sk.add("Mane_02", "Chest", (0.52, 1.70, 0), tail=(0.30, 1.80, 0))
    sk.add("Belly", "Spine_02", (-0.05, 1.08, 0), tail=(-0.05, 1.00, 0))
    for nm, s in SIDES:
        leg_bones(sk, "Front", "Chest", None, [side(j, s) for j in FRONT["joints"]], nm)
        leg_bones(sk, "Hind", "Pelvis", None, [side(j, s) for j in HIND["joints"]], nm)
    tail = [(-0.86, 1.56, 0), (-1.15, 1.50, 0), (-1.45, 1.26, 0), (-1.75, 0.98, 0), (-2.00, 0.72, 0)]
    for i, p in enumerate(tail):
        sk.add(f"Tail_0{i + 1}", "Pelvis" if i == 0 else f"Tail_0{i}", p,
               tail=(-2.20, 0.44, 0) if i == len(tail) - 1 else None)
    sk.socket("socket_head", "Head", (1.22, 1.82, 0))
    sk.socket("socket_mouth", "Jaw", (1.50, 1.48, 0))
    sk.socket("socket_chest", "Chest", (0.70, 1.06, 0))
    for nm, s in SIDES:
        sk.socket(f"socket_foot_front_{nm.lower()}", f"Toe_Front_{nm}", side(FRONT["joints"][5], s))
        sk.socket(f"socket_foot_hind_{nm.lower()}", f"Toe_Hind_{nm}", side(HIND["joints"][5], s))
        sk.socket(f"socket_claw_{nm.lower()}", f"Toe_Front_{nm}", side((0.84, 0.02, 0.30), s))
    sk.socket("socket_tail_tip", "Tail_05", (-2.20, 0.44, 0))
    return sk


def leg_prims(kind, nm, s, J):
    j = [side(p, s) for p in J]
    U, L, Fo, T = f"UpperLeg_{kind}_{nm}", f"LowerLeg_{kind}_{nm}", f"Foot_{kind}_{nm}", f"Toe_{kind}_{nm}"
    out = []
    if kind == "Front":
        out += [Prim("cone", U, k=0.08, a=j[1], b=j[2], ra=0.16, rb=0.115, name="humerus"),
                Prim("ellipsoid", U, k=0.08, c=j[1] * 0.5 + j[2] * 0.5 + np.array([-0.03, 0.02, 0.01 * s]),
                     r=(0.13, 0.19, 0.10), name="triceps"),
                Prim("sphere", L, k=0.05, c=j[2] + np.array([-0.05, 0.02, 0]), r=0.075, name="elbow"),
                Prim("cone", L, k=0.06, a=j[2], b=j[3], ra=0.15, rb=0.105, name="forearm"),
                Prim("ellipsoid", L, k=0.06, c=j[2] * 0.62 + j[3] * 0.38 + np.array([0.02, 0, 0]),
                     r=(0.125, 0.21, 0.13), name="forearm_m")]
    else:
        out += [Prim("cone", U, k=0.10, a=j[1], b=j[2], ra=0.18, rb=0.12, name="femur"),
                Prim("ellipsoid", U, k=0.10, c=j[1] * 0.45 + j[2] * 0.55 + np.array([-0.04, 0.02, 0]),
                     r=(0.17, 0.21, 0.12), name="thigh_m"),
                Prim("cone", L, k=0.06, a=j[2], b=j[3], ra=0.14, rb=0.095, name="tibia"),
                Prim("ellipsoid", L, k=0.06, c=j[2] * 0.6 + j[3] * 0.4 + np.array([-0.02, 0.02, 0]),
                     r=(0.12, 0.19, 0.11), name="gaskin"),
                Prim("sphere", Fo, k=0.03, c=j[3] + np.array([-0.05, 0.03, 0]), r=0.05, name="calcaneus")]
    out += [Prim("sphere", Fo, k=0.04, c=j[3], r=0.088 if kind == "Front" else 0.078, name="wrist"),
            Prim("cone", Fo, k=0.04, a=j[3], b=j[4], ra=0.082, rb=0.086, name="metapodium"),
            Prim("ellipsoid", T, k=0.04, c=j[4] + np.array([0.04, -0.015, 0]), r=(0.13, 0.058, 0.105), name="pad")]
    # four toes spread across the big paw (claws are a separate rigid part)
    for i, dz in enumerate((-0.062, -0.022, 0.022, 0.062)):
        tip = j[5] + np.array([-0.01 + (0.03 if abs(dz) < 0.03 else 0.0), 0.032, dz * 1.45])
        out.append(Prim("cone", T, k=0.025, name=f"toe{i}", a=j[4] + np.array([0.03, -0.01, dz * 0.8]),
                        b=tip, ra=0.043, rb=0.035))
    out.append(Prim("box", T, k=0.004, neg=True, name="sole", c=np.array([j[5][0] - 0.05, -0.10, j[5][2]]),
                    h=(0.25, 0.10, 0.20), round=0.0))
    return out


def body_core():
    P = [Prim("ellipsoid", "Chest", k=0.0, c=(0.30, 1.22, 0), r=(0.50, 0.40, 0.34), name="ribcage"),
         Prim("ellipsoid", "Chest", k=0.12, c=(0.58, 1.27, 0), r=(0.24, 0.24, 0.27), name="brisket"),
         Prim("ellipsoid", "Chest", k=0.14, c=(0.48, 1.60, 0), r=(0.44, 0.18, 0.25), name="withers"),
         Prim("ellipsoid", "Spine_02", k=0.16, c=(-0.12, 1.34, 0), r=(0.42, 0.26, 0.27), name="waist"),
         Prim("ellipsoid", "Spine_01", k=0.16, c=(-0.50, 1.38, 0), r=(0.34, 0.22, 0.26), name="loin"),
         Prim("ellipsoid", "Pelvis", k=0.15, c=(-0.92, 1.34, 0), r=(0.36, 0.27, 0.27), name="rump"),
         Prim("ellipsoid", "Belly", k=0.18, c=(-0.10, 1.19, 0), r=(0.36, 0.10, 0.22), name="belly"),
         Prim("cone", "Neck_01", k=0.14, a=(0.70, 1.46, 0), b=(0.98, 1.60, 0), ra=0.32, rb=0.26, name="neck1"),
         Prim("cone", "Neck_02", k=0.10, a=(0.98, 1.60, 0), b=(1.14, 1.70, 0), ra=0.26, rb=0.21, name="neck2"),
         Prim("ellipsoid", "Throat", k=0.10, c=(0.96, 1.48, 0), r=(0.15, 0.16, 0.16), name="throat"),
         # head: long wolf muzzle, heavy brow, flat crown; mouth a little open (snarl, sabres show)
         Prim("ellipsoid", "Head", k=0.06, c=(1.20, 1.73, 0), r=(0.22, 0.150, 0.145), name="cranium"),
         Prim("ellipsoid", "Head", k=0.05, c=(1.15, 1.81, 0), r=(0.15, 0.075, 0.12), name="crown"),
         Prim("cone", "Nose", k=0.05, a=(1.30, 1.665, 0), b=(1.52, 1.57, 0), ra=0.085, rb=0.040, name="muzzle"),
         Prim("ellipsoid", "Head", k=0.035, c=(1.40, 1.67, 0), r=(0.13, 0.04, 0.06), R=rot_z(-0.30), name="nasal"),
         Prim("sphere", "Nose", k=0.012, mat="nose", c=(1.535, 1.565, 0), r=0.036, name="nosepad"),
         Prim("cone", "Jaw", k=0.035, a=(1.22, 1.56, 0), b=(1.49, 1.49, 0), ra=0.060, rb=0.027, name="jaw"),
         Prim("box", "Head", k=0.006, neg=True, mat="mouth", c=(1.41, 1.53, 0), h=(0.16, 0.012, 0.05), round=0.004,
              R=rot_z(-0.22), name="mouthslit")]
    for nm, s in SIDES:
        P += [Prim("ellipsoid", f"Cheek_{nm}", k=0.05, c=(1.22, 1.625, 0.09 * s), r=(0.11, 0.08, 0.06),
                   name=f"cheek{nm}"),
              Prim("ellipsoid", "Head", k=0.03, c=(1.30, 1.76, 0.065 * s), r=(0.08, 0.035, 0.045), R=rot_z(-0.2),
                   name=f"brow{nm}"),
              Prim("cone", "Nose", k=0.02, mat="skin", a=(1.33, 1.565, 0.062 * s), b=(1.51, 1.548, 0.026 * s),
                   ra=0.022, rb=0.015, name=f"lip{nm}"),
              Prim("sphere", "Head", k=0.01, neg=True, c=(1.31, 1.715, 0.085 * s), r=0.026, name=f"socket{nm}")]
        # tall pointed ears, the opening turned forward and a little outward (front view: the cupped inner ear)
        ec = np.array([1.12, 1.98, 0.115 * s])
        Re = rot_x(-0.20 * s) @ rot_y(-0.30 * s) @ rot_z(-0.08)
        P += [Prim("ellipsoid", f"Ear_{nm}", k=0.025, c=ec, r=(0.062, 0.19, 0.088), R=Re, name=f"ear{nm}"),
              Prim("cone", f"Ear_{nm}", k=0.02, a=ec, b=ec + Re @ np.array([-0.01, 0.34, 0.0]), ra=0.062, rb=0.006,
                   name=f"eartip{nm}"),
              Prim("ellipsoid", f"Ear_{nm}", k=0.008, neg=True, mat="skin", c=ec + Re @ np.array([0.052, 0.04, 0.0]),
                   r=(0.032, 0.16, 0.058), R=Re, name=f"earcav{nm}")]
        P += [Prim("ellipsoid", f"Shoulder_{nm}", k=0.12, c=side((0.56, 1.34, 0.24), s), r=(0.26, 0.38, 0.15),
                   R=rot_z(-0.45), name=f"scapula{nm}"),
              Prim("ellipsoid", f"UpperLeg_Hind_{nm}", k=0.14, c=side((-0.96, 1.14, 0.21), s), r=(0.27, 0.34, 0.14),
                   R=rot_z(0.25), name=f"haunch{nm}")]
        P += leg_prims("Front", nm, s, FRONT["joints"])
        P += leg_prims("Hind", nm, s, HIND["joints"])
    tail_pts = [(-0.86, 1.56, 0), (-1.15, 1.50, 0), (-1.45, 1.26, 0), (-1.75, 0.98, 0), (-2.00, 0.72, 0),
                (-2.20, 0.44, 0)]
    P += chain(tail_pts, [0.08, 0.11, 0.14, 0.16, 0.15, 0.07], None, k=0.05, mat="fur_long", name="tail",
               bones=["Tail_01", "Tail_02", "Tail_03", "Tail_04", "Tail_05"])
    return P


def body_bone(p):
    x, y, z = p
    if x > 1.02:
        return "Neck_02" if y < 1.66 else "Head"
    if x > 0.70:
        return "Mane_01" if y > 1.55 else "Neck_01"
    if y < 1.06:
        return "Belly" if -0.5 < x < 0.4 else ("Chest" if x > 0 else "Pelvis")
    if x > 0.25:
        return "Mane_02" if y > 1.58 else "Chest"
    if x > -0.25:
        return "Spine_02"
    if x > -0.70:
        return "Spine_01"
    return "Pelvis"


def build_body(rng):
    core = Part("body", body_core(), band=0.06)
    P = list(core.prims)
    back = lambda p, n: np.array([-1.0, -0.25, 0])  # noqa: E731
    hang = lambda p, n: np.array([-0.35, -1.0, 0])  # noqa: E731
    # shaggy mane over neck and shoulders, laid back and up
    seeds = scatter_on(core, (0.56, 1.74, 0), (0.54, 0.22, 0.26), 110, rng)
    P += locks(core, seeds, lambda p, n: np.array([-1.0, 0.35, 0]), 0.30, 0.10, body_bone, lift=0.35, rng=rng,
               droop=0.05, thick=0.30)
    seeds = scatter_on(core, (0.86, 1.56, 0), (0.22, 0.16, 0.30), 32, rng)
    P += locks(core, seeds, hang, 0.09, 0.07, body_bone, gravity=0.2, lift=0.2, rng=rng, droop=0.25)
    # back ridge spikes of fur and flank shag
    seeds = scatter_on(core, (-0.02, 1.62, 0), (0.62, 0.10, 0.18), 56, rng)
    P += locks(core, seeds, lambda p, n: np.array([-1.0, 0.45, 0]), 0.17, 0.07, body_bone, lift=0.35, rng=rng,
               thick=0.3)
    seeds = scatter_on(core, (-0.15, 1.26, 0), (0.80, 0.24, 0.32), 44, rng)
    P += locks(core, seeds, back, 0.16, 0.07, body_bone, lift=0.2, rng=rng, droop=0.15, thick=0.28)
    for nm, s in SIDES:
        fj = [side(j, s) for j in FRONT["joints"]]
        hj = [side(j, s) for j in HIND["joints"]]
        for c, r, cnt, L, bone in ((fj[1] * 0.5 + fj[2] * 0.5 + np.array([-0.08, 0, 0]), (0.06, 0.12, 0.08), 6, 0.16,
                                    f"UpperLeg_Front_{nm}"),
                                   ((fj[2] + fj[3]) / 2 + np.array([-0.06, 0.08, 0]), (0.05, 0.14, 0.06), 6, 0.14,
                                    f"LowerLeg_Front_{nm}"),
                                   (side((-1.08, 1.10, 0.22), s), (0.15, 0.22, 0.12), 10, 0.17,
                                    f"UpperLeg_Hind_{nm}")):
            seeds = scatter_on(core, c, r, cnt, rng)
            P += locks(core, seeds, hang, L, 0.06, lambda p, b=bone: b, gravity=0.3, lift=0.25, rng=rng, droop=0.25,
                       k=0.03)
    # haunches, rump and thigh backs: the hind half is as shaggy as the front
    seeds = scatter_on(core, (-0.92, 1.34, 0), (0.36, 0.24, 0.30), 50, rng)
    P += locks(core, seeds, lambda p, n: np.array([-1.0, -0.45, 0]), 0.20, 0.08, body_bone, lift=0.25, rng=rng,
               droop=0.25, thick=0.3)
    for nm, s in SIDES:
        seeds = scatter_on(core, side((-1.02, 1.10, 0.20), s), (0.20, 0.24, 0.10), 18, rng)
        P += locks(core, seeds, hang, 0.18, 0.075, lambda p, b=f"UpperLeg_Hind_{nm}": b, lift=0.25, rng=rng,
                   droop=0.3, thick=0.3)
    seeds = scatter_on(core, (-0.10, 1.11, 0), (0.45, 0.05, 0.22), 18, rng)
    P += locks(core, seeds, hang, 0.08, 0.06, body_bone, gravity=0.3, lift=0.1, rng=rng, droop=0.3)
    # bushy tail
    seeds = scatter_on(core, (-1.78, 0.90, 0), (0.46, 0.44, 0.18), 120, rng)
    P += locks(core, seeds, lambda p, n: np.array([-0.70, -0.72, 0]), 0.36, 0.13,
               lambda p: "Tail_01" if p[0] > -1.0 else ("Tail_02" if p[0] > -1.30 else (
                   "Tail_03" if p[0] > -1.60 else ("Tail_04" if p[0] > -1.86 else "Tail_05"))),
               lift=0.15, rng=rng, droop=0.12, thick=0.35)
    # cheek ruff
    seeds = scatter_on(core, (1.12, 1.64, 0), (0.09, 0.10, 0.15), 24, rng)
    P += locks(core, seeds, lambda p, n: np.array([-1.0, -0.1, 0]), 0.13, 0.055, body_bone, lift=0.3, rng=rng)
    return Part("body", P, band=0.07)


def teeth_part():
    """Sabre fangs (0.30 m), canines/incisors and claws are rigid details (M_Tenerys_Details)."""
    P = []
    for nm, s in SIDES:
        root = np.array([1.39, 1.556, 0.058 * s])
        pts = bezier(root, root + np.array([0.02, -0.10, 0.004 * s]), root + np.array([0.0, -0.22, 0.008 * s]),
                     root + np.array([-0.045, -0.30, 0.006 * s]), 8)
        P += chain(list(pts), list(np.linspace(0.021, 0.004, len(pts))), "Head", k=0.01, mat="fang",
                   name=f"sabre{nm}")
        for i, (x, ln) in enumerate(((1.48, 0.035), (1.38, 0.03), (1.33, 0.025))):
            a = np.array([x, 1.545, (0.035 + 0.01 * i) * s])
            P.append(Prim("cone", "Head", k=0.005, mat="fang", name=f"up{nm}{i}", a=a, b=a + np.array([0, -ln, 0]),
                          ra=0.009, rb=0.002))
        for i, (x, ln) in enumerate(((1.46, 0.045), (1.40, 0.03), (1.34, 0.025))):
            a = np.array([x, 1.49, (0.030 + 0.008 * i) * s])
            P.append(Prim("cone", "Jaw", k=0.005, mat="fang", name=f"lo{nm}{i}", a=a, b=a + np.array([0, ln, 0]),
                          ra=0.010, rb=0.002))
    return Part("teeth", P, band=0.02)


def claw_parts():
    parts = []
    for kind, J in (("Front", FRONT["joints"]), ("Hind", HIND["joints"])):
        for nm, s in SIDES:
            j = [side(p, s) for p in J]
            P = []
            for i, dz in enumerate((-0.062, -0.022, 0.022, 0.062)):
                base = j[5] + np.array([-0.01 + (0.03 if abs(dz) < 0.03 else 0.0), 0.034, dz * 1.45])
                L = 0.165 if kind == "Front" else 0.13
                pts = bezier(base, base + np.array([0.05, 0.01, 0]), base + np.array([L * 0.8, -0.005, 0]),
                             base + np.array([L, -0.035, 0]), 6)
                P += chain(list(pts), list(np.linspace(0.021, 0.0035, len(pts))), f"Toe_{kind}_{nm}", k=0.004,
                           mat="claw", name=f"claw{i}")
            parts.append((f"claws_{kind}_{nm}", Part(f"claws_{kind}_{nm}", P, band=0.02), f"Toe_{kind}_{nm}"))
    return parts


def eye_part():
    P = [Prim("sphere", "Head", k=0.0, mat="eye", c=(1.307, 1.715, 0.083 * s), r=0.027, name=f"eye{nm}")
         for nm, s in SIDES]
    return Part("eyes", P, band=0.015)


_SHORT = {1: 1, 2: 1}   # short coat cards lie flat: one strip segment is enough at LOD1 / LOD2
FUR_CARDS = [  # creature-references: swept-back mane behind the head (ears and face stay clear), glowing strands,
    # silver cheek ruff, dark furred legs to the paws, huge silver brush tail with white tips
    {"centre": (0.55, 1.70, 0), "radii": (0.42, 0.26, 0.32), "count": 420, "length": 0.32, "width": 0.11,
     "flow": lambda p, n: np.array([-1.0, 0.22, 0]), "lift": 0.24, "droop": 0.05, "crossed": True,
     "tip": "#b9bdcb", "root_k": 0.88},                                                             # mane
    {"centre": (0.50, 1.78, 0), "radii": (0.40, 0.16, 0.24), "count": 110, "length": 0.28, "width": 0.07,
     "flow": lambda p, n: np.array([-1.0, 0.15, 0]), "lift": 0.22, "droop": 0.05, "crossed": True,
     "glow": True, "tip": "#a6d6ff"},                                                               # glowing strands
    {"centre": (-0.45, 1.64, 0), "radii": (0.70, 0.10, 0.16), "count": 220, "length": 0.16, "width": 0.09,
     "flow": lambda p, n: np.array([-1.0, 0.12, 0]), "lift": 0.14, "droop": 0.04, "crossed": True,
     "tip": "#a7aab8", "root_k": 0.88},                                                             # back ridge
    {"centre": (-0.45, 1.66, 0), "radii": (0.70, 0.08, 0.10), "count": 60, "length": 0.14, "width": 0.06,
     "flow": lambda p, n: np.array([-1.0, 0.05, 0]), "lift": 0.22, "crossed": True, "glow": True,
     "tip": "#8fb4dc"},                                                                             # ridge glow
    {"centre": (1.00, 1.54, 0), "radii": (0.24, 0.20, 0.30), "count": 110, "length": 0.11, "width": 0.09,
     "flow": lambda p, n: np.array([-0.35, -1.0, 0]), "lift": 0.12, "gravity": 0.2, "droop": 0.15,
     "crossed": True, "tip": "#c6c8d4", "root_k": 0.9},                                            # throat ruff
    {"centre": (1.12, 1.60, 0), "radii": (0.10, 0.12, 0.18), "count": 70, "length": 0.16, "width": 0.07,
     "flow": lambda p, n: np.array([-1.0, -0.30, 0]), "lift": 0.22, "droop": 0.05, "crossed": True,
     "tip": "#d0d2dc", "root_k": 0.95},                                                            # cheek ruff
    {"centre": (1.18, 1.80, 0), "radii": (0.14, 0.06, 0.12), "count": 60, "length": 0.06, "width": 0.05,
     "flow": lambda p, n: np.array([-1.0, 0.05, 0]), "lift": 0.12, "droop": 0.02, "tip": "#77757f",
     "root_k": 1.0, "segments": _SHORT},                                                            # crown
    {"centre": (0.55, 1.38, 0), "radii": (0.32, 0.22, 0.36), "count": 280, "length": 0.24, "width": 0.08,
     "flow": lambda p, n: np.array([-0.8, -0.6, 0]), "lift": 0.10, "droop": 0.1, "tip": "#77757f",
     "root_k": 0.9},                                                                                # shoulders
    {"centre": (-0.20, 1.30, 0), "radii": (0.95, 0.30, 0.34), "count": 520, "length": 0.13, "width": 0.08,
     "flow": lambda p, n: np.array([-1.0, -0.30, 0]), "lift": 0.10, "droop": 0.08, "tip": "#6e6c78",
     "root_k": 0.95, "segments": _SHORT},                                                           # coat
    {"centre": (-0.95, 1.22, 0), "radii": (0.36, 0.30, 0.32), "count": 200, "length": 0.17, "width": 0.08,
     "flow": lambda p, n: np.array([-1.0, -0.55, 0]), "lift": 0.12, "droop": 0.12, "tip": "#7b7985",
     "root_k": 0.92},                                                                               # croup, flanks
    {"centre": (0.50, 0.62, 0), "radii": (0.22, 0.52, 0.36), "count": 380, "length": 0.16, "width": 0.085,
     "flow": lambda p, n: np.array([-0.4, -1.0, 0]), "lift": 0.16, "gravity": 0.15, "droop": 0.1,
     "tip": "#83818e", "root_k": 0.92, "segments": _SHORT},                                         # forelegs
    {"centre": (0.50, 0.22, 0), "radii": (0.20, 0.20, 0.36), "count": 150, "length": 0.09, "width": 0.07,
     "flow": lambda p, n: np.array([0.25, -1.0, 0]), "lift": 0.10, "droop": 0.02, "tip": "#6e6c78",
     "root_k": 0.95, "segments": _SHORT},                                                           # fore paws
    {"centre": (-0.05, 1.09, 0), "radii": (0.50, 0.07, 0.24), "count": 80, "length": 0.11, "width": 0.07,
     "flow": lambda p, n: np.array([-0.5, -1.0, 0]), "lift": 0.05, "gravity": 0.3, "droop": 0.15,
     "tip": "#4b4852", "segments": _SHORT},                                                         # belly fringe
    {"centre": (-1.00, 0.85, 0), "radii": (0.30, 0.50, 0.34), "count": 380, "length": 0.17, "width": 0.085,
     "flow": lambda p, n: np.array([-0.6, -1.0, 0]), "lift": 0.15, "droop": 0.1, "crossed": True,
     "tip": "#83818e", "root_k": 0.92},                                                             # thighs, hocks
    {"centre": (-1.18, 0.28, 0), "radii": (0.20, 0.28, 0.34), "count": 150, "length": 0.10, "width": 0.07,
     "flow": lambda p, n: np.array([-0.3, -1.0, 0]), "lift": 0.10, "droop": 0.02, "tip": "#6e6c78",
     "root_k": 0.95, "segments": _SHORT},                                                           # hind feet
    {"centre": (-1.80, 0.90, 0), "radii": (0.48, 0.44, 0.20), "count": 520, "length": 0.33, "width": 0.14,
     "flow": lambda p, n: np.array([-0.78, -0.62, 0]), "lift": 0.10, "droop": 0.02, "crossed": True,
     "tip": "#eef0f6", "root": "#5d5b66", "root_k": 1.0, "bone": "Tail_03"},                        # tail brush
    {"centre": (-1.72, 0.96, 0), "radii": (0.44, 0.36, 0.16), "count": 50, "length": 0.30, "width": 0.06, "bone": "Tail_03",
     "flow": lambda p, n: np.array([-0.6, -0.8, 0]), "lift": 0.2, "crossed": True, "glow": True,
     "tip": "#a9c8ec"}]                                                                             # tail glow

CLASSES = {"body": ["fur", "fur_long", "skin", "nose", "mouth"], "detail": ["fang", "claw", "eye"]}
CLASS_OF = {"base": "fur"}
AXIS_PRIMS = ("lock", "humerus", "forearm", "femur", "tibia", "metapodium", "tail", "neck", "muzzle", "jaw", "sabre",
              "claw", "toe", "lip", "up", "lo")
MATERIAL_NAMES = {"body": "Body", "detail": "Details"}
_CACHE = {}


def build(rng=None):
    rng = rng or np.random.default_rng(5)
    sk = skeleton()
    parts = [{"name": "body", "part": build_body(rng), "material": "body", "rigid": None,
              "faces": (30000, 10500, 3600)},
             {"name": "teeth", "part": teeth_part(), "material": "detail", "rigid": "Head", "faces": (1600, 700, 160),
              "voxel": 0.0025},
             {"name": "eyes", "part": eye_part(), "material": "detail", "rigid": "Head", "faces": (240, 120, 40),
              "voxel": 0.0025}]
    for name, part, bone in claw_parts():
        parts.append({"name": name, "part": part, "material": "detail", "rigid": bone, "faces": (520, 220, 60),
                      "voxel": 0.003})
    # lower teeth follow the jaw: split them into their own rigid part
    return sk, parts


def build_cached():
    if "b" not in _CACHE:
        sk, parts = build()
        # lower teeth: separate part bound to the jaw
        tp = next(p for p in parts if p["name"] == "teeth")
        lower = [q for q in tp["part"].prims if q.bone == "Jaw"]
        tp["part"] = Part("teeth", [q for q in tp["part"].prims if q.bone != "Jaw"], band=0.02)
        parts.insert(2, {"name": "teeth_lower", "part": Part("teeth_lower", lower, band=0.02), "material": "detail",
                         "rigid": "Jaw", "faces": (300, 140, 0), "voxel": 0.0025})
        _warp.apply(WARP, sk, parts)
        for k, p in enumerate(parts):
            p["index"] = k
        _CACHE["b"] = (sk, parts)
    return _CACHE["b"]


PROOF_COLORS = {"base": "#3a383d", "fur": "#3a383d", "fur_long": "#3f3d44", "skin": "#2b2224", "nose": "#0b0b0c", "mouth": "#3a1418",
                "fang": "#e4dccb", "claw": "#d8d0c0", "eye": "#61bdf4"}


# ---------------------------------------------------------------- surface
from shading import lin, mix, sstep, fur_height, fur_streaks, tangent_flow  # noqa: E402
import noise  # noqa: E402

EMISSION_COLOR = "#61BDF4"
LEVELS = {  # R: mane and shoulders (silver edges, II+), G: blue veins along the coat (glow), B: eyes (detail).
    # Restrained: the coat stays black-blue; the glow is thin veins and eyes, readable without bloom.
    1: {"emission_strength": 0.85, "tint_r": (0.72, 0.80, 0.88, 0.0), "emit_r": 0.0, "emit_g": 0.0, "emit_b": 0.0},
    2: {"emission_strength": 1.0, "tint_r": (0.52, 0.60, 0.70, 0.30), "emit_r": 0.0, "emit_g": 0.30, "emit_b": 0.0},
    3: {"emission_strength": 1.2, "tint_r": (0.62, 0.72, 0.84, 0.40), "emit_r": 0.04, "emit_g": 0.75,
        "emit_b": 0.9},
}


def default_flow(P, part):
    x, y = P[:, 0], P[:, 1]
    back = np.array([-1.0, -0.15, 0.0], np.float32)
    down = np.array([-0.2, -1.0, 0.0], np.float32)
    w = sstep(0.95, 0.70, y)[:, None]
    return np.asarray(back * (1 - w) + down * w, np.float32)


def veins(P, N, flow, seed=3):
    """Thin glowing strands along the coat flow on mane, shoulders and flanks (emissive mask 0..1)."""
    q = noise.stretch_along(P * 7.0, flow, 9.0)
    v = 1.0 - np.abs(noise.perlin(q, seed))
    line = sstep(0.972, 0.995, v)
    region = sstep(1.40, 1.60, P[:, 1]) * sstep(-0.3, 0.2, P[:, 0])  # mane / shoulders
    region = np.maximum(region, sstep(0.25, 0.65, np.abs(N[:, 2])) * sstep(-0.9, -0.2, P[:, 0]) *
                        sstep(1.12, 1.38, P[:, 1]) * 0.55)  # flanks (fewer)
    region = np.maximum(region, sstep(-1.0, -1.3, P[:, 0]) * 0.7)  # tail
    return line * region


def shade(group, ctx):
    return shade_body(ctx) if group == "body" else shade_detail(ctx)


def shade_body(ctx):
    P, N = ctx.P, ctx.N
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    cl = CLASSES["body"]
    w = {c: ctx.W[:, i] for i, c in enumerate(cl)}
    flow = tangent_flow(ctx.flow, N)
    lod = ctx.lod
    hfur = fur_height(flow, 1.35, 3 if lod == 0 else (2 if lod == 1 else 1), clumps=True, seed=4)
    h0 = hfur(P) / 0.0028
    # sheet palette: neutral charcoal coat (#2d292b-#524e53), silver-grey tips (#75737d-#8b91a2)
    col = mix(lin("#423d40"), lin("#2f2a2c"), sstep(0.1, 0.8, N[:, 1]))
    col = mix(col, lin("#524c50"), sstep(-0.1, -0.7, N[:, 1]))
    col = mix(col, lin("#38333a"), sstep(0.90, 0.60, y) * (1 - sstep(0.25, 0.10, y)))
    col = mix(col, lin("#1f1b1c"), sstep(0.20, 0.05, y))
    patch = noise.fbm(P * 3.0, 3, seed=22)
    col = col * (1.0 + 0.20 * patch[:, None])
    # silver edges at the tips of the long strands (mane, ruff, tail) and the muzzle grizzle
    tips = sstep(0.35, 1.0, h0)
    silver = mix(lin("#4c474d"), lin("#9a9ca8"), tips)
    col = mix(col, silver, w["fur_long"] * tips * 0.60)
    col = mix(col, lin("#6a6670"), sstep(1.38, 1.50, x) * sstep(1.62, 1.54, y) * 0.6)
    tailtip = sstep(-1.55, -1.95, x)
    col = mix(col, mix(lin("#5d5a62"), lin("#a7a9b4"), tips), tailtip * w["fur_long"] * 0.7)
    streak = fur_streaks(P, flow, 1.0, seed=31)
    col = col * (0.82 + 0.22 * sstep(-1.0, 1.0, h0))[:, None] * (0.80 + 0.32 * (streak * 0.5 + 0.5))[:, None]
    # creature-references face: silver-white muzzle and chin, silver cheeks, dark mask round the eyes and brow
    muzzle = sstep(1.30, 1.42, x) * sstep(1.70, 1.62, y)
    chin = sstep(1.20, 1.32, x) * sstep(1.60, 1.53, y)
    col = mix(col, lin("#a9a8b2") * (0.85 + 0.25 * (streak * 0.5 + 0.5))[:, None], np.clip(muzzle * 0.8 + chin * 0.8, 0, 1))
    cheek = sstep(1.08, 1.20, x) * sstep(1.50, 1.60, y) * sstep(1.72, 1.64, y) * sstep(0.05, 0.10, np.abs(z))
    col = mix(col, lin("#8d8b96"), cheek * 0.7)
    for sgn in (-1.0, 1.0):
        d_eye = np.linalg.norm(P - np.array([1.31, 1.715, 0.085 * sgn], np.float32), axis=1)
        col = mix(col, lin("#141215"), sstep(0.075, 0.035, d_eye) * 0.85)
    col = mix(col, lin("#2a2629"), sstep(1.97, 2.05, y) * (1 - w["skin"]) * 0.7)     # dark ear backs
    col = mix(col, lin("#2b2224"), w["skin"])
    col = mix(col, lin("#8d8b96"), w["skin"] * sstep(1.90, 1.97, y))                # pale fur in the ear cup
    col = mix(col, lin("#0b0b0c"), w["nose"])
    col = mix(col, lin("#3a1418"), w["mouth"])
    vn = veins(P, N, flow) * (w["fur"] + w["fur_long"])
    col = mix(col, lin("#3c6f93"), vn * 0.5)
    emissive = lin("#61bdf4")[None, :] * (vn * 0.6)[:, None]
    rough = 0.80 + 0.06 * noise.perlin(P * 15, 3)
    rough = mix(rough, 0.72 - 0.06 * tips, w["fur_long"])
    rough = mix(rough, 0.58, w["skin"])
    rough = mix(rough, 0.38, w["nose"])
    rough = mix(rough, 0.45, w["mouth"])
    furw = w["fur"] + w["fur_long"]

    def height(Q):
        return hfur(Q) * furw * 1.5 + noise.perlin(Q * 140, 13) * 0.0003 * (w["skin"] + w["nose"])
    cavity = 1.0 - 0.3 * furw * sstep(0.2, -0.9, h0)
    mane = (w["fur_long"] * sstep(1.35, 1.55, y)).astype(np.float32)
    shoulders = sstep(1.30, 1.50, y) * sstep(-0.1, 0.3, x) * sstep(0.85, 0.55, x)
    variant = np.stack([np.clip(mane + shoulders * 0.6, 0, 1), np.clip(vn * 1.2 + 0.25 * veins(P, N, flow, 9), 0, 1),
                        np.zeros(ctx.n, np.float32), np.ones(ctx.n, np.float32)], 1)
    return {"albedo": np.clip(col, 0, 1), "roughness": np.clip(rough, 0, 1), "emissive": emissive, "height": height,
            "height_eps": 0.002 if lod == 0 else 0.0035, "cavity": cavity, "variant": variant}


def shade_detail(ctx):
    P, N = ctx.P, ctx.N
    cl = CLASSES["detail"]
    w = {c: ctx.W[:, i] for i, c in enumerate(cl)}
    rad = getattr(ctx, "rad", np.full(ctx.n, 0.01, np.float32))
    flow = tangent_flow(ctx.flow, N)
    ring = noise.ridged(noise.stretch_along(P * 90.0, flow, 0.25), 2, seed=5)
    fang = mix(lin("#c9bfa8"), lin("#efe8d8"), sstep(0.02, 0.006, rad))
    fang = fang * (0.9 + 0.12 * ring)[:, None]
    claw = mix(lin("#4a4038"), lin("#e2d8c4"), sstep(0.017, 0.007, rad))
    eye = lin("#0e1216")
    col = fang * w["fang"][:, None] + claw * w["claw"][:, None] + eye * w["eye"][:, None]
    em = np.zeros((ctx.n, 3), np.float32)
    eyeglow = np.zeros(ctx.n, np.float32)
    for s in (-1, 1):
        c = np.array([1.305, 1.715, 0.081 * s], np.float32)
        ax = np.array([0.62, 0.0, 0.78 * s], np.float32)
        ax /= np.linalg.norm(ax)
        rel = P - c
        cosang = np.sum(rel * ax, 1) / np.maximum(np.linalg.norm(rel, axis=1), 1e-6)
        near = (np.linalg.norm(rel, axis=1) < 0.035).astype(np.float32) * w["eye"]
        iris = sstep(0.62, 0.72, cosang) * near
        pupil = sstep(0.93, 0.96, cosang) * near
        col = mix(col, lin("#b8e5ff"), iris)
        col = mix(col, lin("#06080a"), pupil)
        em += lin("#b8e5ff")[None, :] * (iris * (1 - pupil) * 1.6)[:, None]
        eyeglow = np.maximum(eyeglow, iris)
    rough = w["fang"] * (0.35 + 0.15 * (1 - ring)) + w["claw"] * 0.42 + w["eye"] * 0.08

    def height(Q):
        return noise.ridged(noise.stretch_along(Q * 90.0, flow, 0.25), 2, seed=5) * 0.0004 * (w["fang"] + w["claw"])
    variant = np.stack([np.zeros(ctx.n, np.float32), np.zeros(ctx.n, np.float32), eyeglow,
                        np.ones(ctx.n, np.float32)], 1)
    return {"albedo": np.clip(col, 0, 1), "roughness": np.clip(rough, 0, 1), "emissive": em, "height": height,
            "height_eps": 0.0012, "variant": variant}


# ---------------------------------------------------------------- animation
POSTURE = {}
BREATH_PERIOD_F = 30
BREATH_AMP = 0.8
CLIP_NAMES = ["idle", "walk", "stalk", "run", "turn_left", "turn_right", "howl", "attack_bite", "attack_claw",
              "attack_pounce", "dodge", "hit", "death", "alert"]
SEMANTIC = {"Idle": "idle", "Walk": "walk", "Run": "run", "Alert": "alert", "Attack": "attack_bite", "Hit": "hit",
            "Death": "death", "Roar": "howl"}
SERVER_EVENTS = {"creature_attack": "attack_bite", "pounce": "attack_pounce"}


def clips(rig, sampler):
    import clips as C
    from anim import plan_feet
    from qmath import ease, q_euler
    g = globals()
    pre = ID + "__"
    out = []
    walk_off = {("Hind", "L"): 0.0, ("Front", "L"): 0.25, ("Hind", "R"): 0.5, ("Front", "R"): 0.75}
    gal_off = {("Hind", "L"): 0.0, ("Hind", "R"): 0.08, ("Front", "L"): 0.42, ("Front", "R"): 0.50}

    out.append(C.standing(rig, g, pre + "idle", 90, {
        "taily": [(0, 0.0), (25, 0.22), (55, -0.20), (80, 0.10), (90, 0.0)],
        "tailp": [(0, 0.05), (45, 0.12), (90, 0.05)],
        "hy": [(0, 0.0), (20, -0.10), (38, -0.10), (52, 0.12), (75, 0.12), (90, 0.0)],
        "earp": [(0, 0.0), (60, 0.0), (63, 0.25), (67, 0.0), (90, 0.0)],
        "pz": [(0, 0.0), (45, 0.01), (90, 0.0)]}, loop=True, legs_fn=C.leg_keys(rig, IDLE_STANCE, 90)))

    def walk_body(ph):
        w = 2 * np.pi * ph
        return {"py": -0.018 * np.cos(2 * w), "pr": 0.03 * np.sin(w), "pyw": 0.03 * np.sin(w), "cr": -0.025 *
                np.sin(w), "n1p": 0.02 * np.sin(2 * w + 0.5), "gF": 0.07 * np.sin(w), "gH": 0.04 * np.sin(w),
                "taily": 0.18 * np.sin(w + 1.2), "tailp": 0.05}
    out.append(C.locomotion(rig, g, pre + "walk", 36, 1.5, 0.62, walk_off, 0.14, walk_body))

    def stalk_body(ph):
        w = 2 * np.pi * ph
        return {"py": -0.13 - 0.008 * np.cos(2 * w), "pp": 0.02, "pr": 0.015 * np.sin(w), "s2p": -0.03,
                "n1p": -0.16, "n2p": -0.05, "hp": 0.16 - 0.01 * np.sin(2 * w), "earp": 0.15, "tailp": -0.18,
                "taily": 0.05 * np.sin(w), "gF": 0.05 * np.sin(w)}
    out.append(C.locomotion(rig, g, pre + "stalk", 48, 0.75, 0.75, walk_off, 0.09, stalk_body))

    def run_body(ph):
        w = 2 * np.pi * ph
        return {"py": 0.07 * np.sin(w - 0.6) - 0.03, "pp": 0.10 * np.sin(w + 0.4), "s1p": -0.16 * np.sin(w),
                "s2p": -0.12 * np.sin(w), "cp": 0.06 * np.sin(w + 0.3), "n1p": -0.08 * np.sin(w + 0.9) - 0.10,
                "hp": 0.06 * np.sin(w + 0.9) + 0.06, "gF": 0.20 * np.sin(w + 2.1), "gH": 0.16 * np.sin(w),
                "tailp": 0.10 + 0.12 * np.sin(w), "earp": -0.35}
    out.append(C.locomotion(rig, g, pre + "run", 18, 8.0, 0.32, gal_off, 0.24, run_body, reach=0.10))

    for name, sgn in (("turn_left", 1.0), ("turn_right", -1.0)):
        N = 18
        yaw = lambda fr, s=sgn, N=N: s * np.radians(45.0) * ease(fr / (N - 3.0))  # noqa: E731
        a, b = ("L", "R") if sgn > 0 else ("R", "L")
        sw = {("Front", a): [(1, 7)], ("Front", b): [(4, 10)], ("Hind", a): [(7, 13)], ("Hind", b): [(10, 16)]}
        legs = plan_feet(rig, N, lambda fr: (0.0, 0.0, yaw(fr)), sw, lift=0.10)
        out.append(C.standing(rig, g, pre + name, N, {
            "n1y": [(0, 0.0), (4, 0.25 * sgn), (12, 0.08 * sgn), (18, 0.0)],
            "hy": [(0, 0.0), (4, 0.18 * sgn), (14, 0.03 * sgn), (18, 0.0)],
            "cy": [(0, 0.0), (6, 0.12 * sgn), (16, 0.0)],
            "s2y": [(0, 0.0), (8, 0.08 * sgn), (17, 0.0)],
            "taily": [(0, 0.0), (8, -0.35 * sgn), (18, 0.0)]},
            legs_fn=legs, motion={"yaw_deg": 45.0 * sgn, "yaw": [float(yaw(f)) for f in range(N + 1)]}))

    out.append(C.standing(rig, g, pre + "howl", 75, {
        "n1p": [(0, 0.0), (10, -0.08), (18, 0.42), (52, 0.46), (64, 0.10), (75, 0.0)],
        "n2p": [(0, 0.0), (18, 0.18), (52, 0.20), (75, 0.0)],
        "hp": [(0, 0.0), (10, -0.05), (18, 0.38), (52, 0.42), (66, 0.05), (75, 0.0)],
        "jaw": [(0, 0.0), (14, 0.05), (19, 0.30), (48, 0.26), (56, 0.05), (62, 0.0)],
        "cp": [(0, 0.0), (10, 0.05), (18, -0.08), (52, -0.07), (75, 0.0)],
        "py": [(0, 0.0), (10, -0.04), (18, 0.04), (52, 0.03), (75, 0.0)],
        "px": [(0, 0.0), (10, -0.05), (18, 0.02), (75, 0.0)],
        "earp": [(0, 0.0), (16, -0.30), (55, -0.28), (70, 0.0)],
        "belly": [(0, 0.0), (10, 0.025), (18, -0.02), (50, -0.03), (75, 0.0)],
        "tailp": [(0, 0.0), (18, 0.15), (55, 0.12), (75, 0.0)]},
        events=[{"event": "sound", "frame": 18, "time": 18 / 30}]))

    out.append(C.standing(rig, g, pre + "attack_bite", 24, {
        "px": [(0, 0.0), (6, -0.07), (10, 0.16), (13, 0.12), (24, 0.0)],
        "py": [(0, 0.0), (6, -0.05), (10, -0.02), (24, 0.0)],
        "n1p": [(0, 0.0), (6, 0.06), (10, -0.12), (14, -0.08), (24, 0.0)],
        "hp": [(0, 0.0), (6, 0.10), (10, -0.06), (24, 0.0)],
        "jaw": [(0, 0.0), (5, 0.10), (8, 0.48), (10, 0.02), (13, 0.0), (24, 0.0)],
        "earp": [(0, 0.0), (5, -0.4), (18, -0.3), (24, 0.0)],
        "gF": [(0, 0.0), (6, 0.08), (10, -0.10), (24, 0.0)],
        "tailp": [(0, 0.0), (8, 0.25), (24, 0.0)]},
        events=[{"event": "windup", "frame": 0}, {"event": "whoosh", "frame": 8}, {"event": "contact", "frame": 10},
                {"event": "recovery", "frame": 12}],
        windows={"windup": [0, 8], "active": [8, 12], "recovery": [12, 24], "impact": 10}))

    claw_legs = C.leg_keys(rig, {("Front", "R"): {
        "dx": [(0, 0.0), (8, -0.05), (12, 0.38), (15, 0.34), (20, 0.10), (24, 0.0, "hold"), (30, 0.0, "hold")],
        "dy": [(0, 0.0), (6, 0.22), (10, 0.42), (13, 0.12), (16, 0.08), (20, 0.06), (24, 0.0, "hold"), (30, 0.0)],
        "dz": [(0, 0.0), (8, 0.10), (13, -0.16), (16, -0.18), (22, -0.04), (24, 0.0, "hold"), (30, 0.0)],
        "toe": [(0, 0.0), (8, -0.9), (11, 0.35), (14, 0.25), (22, 0.0)],
        "foot": [(0, 0.0), (8, -1.1), (11, -0.2), (16, 0.0), (22, 0.0)]}}, 30)
    out.append(C.standing(rig, g, pre + "attack_claw", 30, {
        "px": [(0, 0.0), (8, -0.06), (13, 0.10), (20, 0.03), (30, 0.0)],
        "pr": [(0, 0.0), (8, -0.06), (13, 0.05), (30, 0.0)],
        "cr": [(0, 0.0), (8, -0.08), (13, 0.07), (30, 0.0)],
        "cy": [(0, 0.0), (8, -0.08), (13, 0.10), (30, 0.0)],
        "n1y": [(0, 0.0), (8, -0.10), (13, 0.12), (30, 0.0)],
        "jaw": [(0, 0.0), (8, 0.18), (14, 0.22), (22, 0.0)],
        "earp": [(0, 0.0), (6, -0.35), (24, 0.0)], "taily": [(0, 0.0), (10, 0.3), (16, -0.3), (30, 0.0)]},
        legs_fn=claw_legs,
        events=[{"event": "windup", "frame": 0}, {"event": "whoosh", "frame": 11}, {"event": "contact", "frame": 13},
                {"event": "recovery", "frame": 16}],
        windows={"windup": [0, 10], "active": [10, 16], "recovery": [16, 30], "impact": 13}))

    # pounce: crouch (0-15), take off at 15, fly to 31, land/impact 32, recover to 48 (controller moves 3.2 m)
    N = 48
    dist = 3.2
    fx = lambda fr: dist * ease((fr - 15) / 16.0) if fr > 15 else 0.0  # noqa: E731
    sw = {("Hind", "L"): [(15, 34)], ("Hind", "R"): [(15, 35)], ("Front", "L"): [(14, 31)], ("Front", "R"): [(14, 32)]}
    pl = plan_feet(rig, N, lambda fr: (fx(fr), 0.0, 0.0), sw, lift=0.10, stance_mid=False)

    spread = C.step_offsets({("Front", "L"): [(0, 5, 0.0, 0.30, 0.10), (41, 46, 0.30, 0.0, 0.08)],
                             ("Front", "R"): [(1, 6, 0.0, 0.30, 0.10), (43, 48, 0.30, 0.0, 0.08)],
                             ("Hind", "L"): [(2, 7, 0.0, -0.40, 0.10), (42, 47, -0.40, 0.0, 0.08)],
                             ("Hind", "R"): [(3, 8, 0.0, -0.40, 0.10), (43, 48, -0.40, 0.0, 0.08)]})

    def pounce_legs(fr, prm):
        legs = pl(fr)
        # creature-references: the whole attack from a long, low stance (forepaws well ahead, hind paws well back),
        # taken by quick steps before the crouch and given back by steps at the end (no sliding)
        for k in legs:
            dx, dy, toe = spread(fr, k)
            legs[k]["tip"] = legs[k]["tip"] + np.array([dx, dy, 0.0])
            legs[k]["toe"] = legs[k].get("toe", 0.0) + toe
        if 14 < fr < 34:
            s = (fr - 14) / 20.0
            for k in legs:
                reach = 0.80 if k[0] == "Front" else -0.78
                ext = np.sin(np.pi * min(1, s * 1.1)) ** 0.7
                legs[k]["tip"] = legs[k]["tip"] + np.array([reach * ext, (0.70 if k[0] == "Front" else 0.55) * ext, 0])
                legs[k]["toe"] = (0.3 if k[0] == "Front" else -0.6) * ext
                legs[k]["foot"] = (0.25 if k[0] == "Front" else 0.4) * ext
        # landing strike: the near (right) forepaw rakes down and forward, then comes back under the shoulder
        if 26 <= fr <= 42:
            # the claws rake the ground ahead of the landing (32-34), then the paw comes back in a low arc
            k = ("Front", "R")
            sw = np.interp(fr, [26, 29, 32, 34, 42], [0.0, 0.55, 0.62, 0.62, 0.0])
            up = np.interp(fr, [26, 29, 31, 32, 34, 38, 42], [0.0, 0.22, 0.06, 0.0, 0.0, 0.10, 0.0])
            legs[k]["tip"] = legs[k]["tip"] + np.array([sw, up, 0.04 * sw])
            legs[k]["toe"] = legs[k].get("toe", 0.0) + np.interp(fr, [26, 29, 32, 34, 38, 42],
                                                                 [0.0, -0.6, 0.35, 0.30, -0.4, 0.0])
        return legs
    # creature-references teneris/01-04: 12 preparation - pressed to the ground, the hind legs gathered; 25 launch -
    # stretched out in the leap, forepaws and claws reaching ahead; 32 contact - on landing the near forepaw rakes
    # down and forward; 42 recovery - the paw back under the shoulder, a low steady stance
    def pounce_tail(fr):
        up = float(np.interp(fr, [0, 8, 40, 48], [0.0, 1.0, 1.0, 0.0]))
        # the brush is carried straight out behind: the drooping segments are lifted, the root barely
        return {"Tail_01": q_euler(-0.12 * up, 0, 0), "Tail_02": q_euler(-0.40 * up, 0, 0),
                "Tail_03": q_euler(0.03 * up, 0, 0), "Tail_04": q_euler(0.14 * up, 0, 0)}
    out.append(C.standing(rig, g, pre + "attack_pounce", N, {
        "py": [(0, 0.0), (8, -0.30), (12, -0.38), (15, -0.36), (21, 0.52), (25, 0.60), (29, 0.30), (32, -0.20),
               (36, -0.28), (41, -0.28), (48, 0.0)],
        "pp": [(0, 0.0), (8, -0.10), (12, -0.12), (15, -0.06), (20, 0.16), (25, 0.10), (29, -0.04), (32, -0.14),
               (40, -0.02), (48, 0.0)],
        "px": [(0, 0.0), (8, -0.12), (12, -0.16), (15, -0.16), (24, 0.04), (32, 0.12), (40, 0.02), (48, 0.0)],
        "s1p": [(0, 0.0), (10, 0.0), (20, -0.20), (25, -0.22), (30, 0.04), (48, 0.0)],
        "s2p": [(0, 0.0), (10, 0.0), (20, -0.16), (25, -0.18), (30, 0.03), (48, 0.0)],
        "n1p": [(0, 0.0), (8, -0.10), (12, -0.12), (20, -0.02), (25, -0.06), (31, -0.20), (36, -0.16), (42, -0.10),
                (48, 0.0)],
        "hp": [(0, 0.0), (8, 0.14), (12, 0.18), (20, -0.02), (25, 0.04), (31, 0.12), (42, 0.06), (48, 0.0)],
        "jaw": [(0, 0.0), (8, 0.18), (14, 0.20), (22, 0.40), (28, 0.45), (32, 0.30), (38, 0.18), (42, 0.24),
                (48, 0.0)],
        "earp": [(0, 0.0), (8, -0.45), (40, -0.35), (48, 0.0)],
        "tailp": [(0, 0.0), (48, 0.0)]},
        legs_fn=pounce_legs, tail_amp=0.5, extra_fn=pounce_tail,
        events=[{"event": "windup", "frame": 0}, {"event": "takeoff", "frame": 15}, {"event": "contact", "frame": 32},
                {"event": "land", "frame": 32}, {"event": "recovery", "frame": 35}],
        windows={"windup": [0, 31], "active": [31, 35], "recovery": [35, 48], "impact": 32},
        motion={"forward_m": [float(fx(f)) for f in range(N + 1)]}))

    # dodge: crouch, spring sideways (controller frames 5-16, 1.4 m to the right), land, recover
    N = 24
    dz = lambda fr: 1.4 * ease((fr - 5) / 11.0) if fr > 5 else 0.0  # noqa: E731
    sw = {("Front", "L"): [(6, 15)], ("Front", "R"): [(5, 14)], ("Hind", "L"): [(7, 16)], ("Hind", "R"): [(6, 15)]}
    dl = plan_feet(rig, N, lambda fr: (0.0, dz(fr), 0.0), sw, lift=0.22, stance_mid=False)
    out.append(C.standing(rig, g, pre + "dodge", N, {
        "py": [(0, 0.0), (5, -0.14), (10, 0.12), (16, -0.08), (24, 0.0)],
        "pr": [(0, 0.0), (5, -0.08), (10, 0.12), (16, 0.02), (24, 0.0)],
        "pyw": [(0, 0.0), (8, -0.10), (16, -0.04), (24, 0.0)],
        "n1y": [(0, 0.0), (8, 0.14), (18, 0.04), (24, 0.0)],
        "earp": [(0, 0.0), (4, -0.4), (20, 0.0)], "taily": [(0, 0.0), (10, 0.4), (20, 0.0)]},
        legs_fn=dl, events=[{"event": "push", "frame": 5}, {"event": "land", "frame": 16}],
        motion={"side_m": [float(dz(f)) for f in range(N + 1)], "window": [5, 16]}))

    out.append(C.standing(rig, g, pre + "hit", 15, {
        "px": [(0, 0.0), (3, -0.07), (9, -0.02), (15, 0.0)],
        "pr": [(0, 0.0), (3, -0.05), (10, 0.01), (15, 0.0)],
        "n1p": [(0, 0.0), (3, 0.12), (9, 0.02), (15, 0.0)],
        "hy": [(0, 0.0), (3, 0.12), (15, 0.0)],
        "jaw": [(0, 0.0), (3, 0.18), (9, 0.0)],
        "earp": [(0, 0.0), (2, -0.55), (12, -0.15), (15, 0.0)]}, idle_overlay=False,
        events=[{"event": "hit", "frame": 2}]))

    out.append(C.death(rig, g, sampler, pre + "death", 72, {
        "pp": [(0, 0.0), (10, -0.14), (20, -0.10), (34, -0.02), (72, 0.0)],
        "pr": [(0, 0.0), (14, 0.05), (22, 0.35), (34, 1.10), (44, 1.32), (52, 1.38), (72, 1.38, "hold")],
        "py": [(0, 0.0), (10, -0.18), (18, -0.40), (34, -0.70), (72, -0.75, "hold")],
        "n1p": [(0, 0.0), (10, -0.12), (24, -0.04), (40, -0.18), (52, -0.25), (72, -0.25, "hold")],
        "n1r": [(0, 0.0), (30, -0.10), (52, -0.20), (72, -0.20, "hold")],
        "hp": [(0, 0.0), (18, -0.18), (44, -0.08), (72, -0.08)],
        "jaw": [(0, 0.0), (8, 0.22), (26, 0.10), (52, 0.10), (72, 0.10)],
        "earp": [(0, 0.0), (14, -0.5), (72, -0.6)], "tailp": [(0, 0.0), (24, -0.3), (72, -0.45)],
        "belly": [(0, 0.0), (56, 0.02), (64, -0.01), (72, 0.0)]},
        {"UpperLeg_Front": 0.35, "LowerLeg_Front": -0.50, "Foot_Front": -0.4, "Toe_Front": -0.5,
         "UpperLeg_Hind": -0.30, "LowerLeg_Hind": 0.50, "Foot_Hind": -0.30, "Toe_Hind": -0.4},
        buckle_end=16, fk_start=14, fk_end=28, lie_frame=34, search_bone="Neck_02", search_range=(0.0, -0.3)))

    out.append(C.standing(rig, g, pre + "alert", 24, {
        "py": [(0, 0.0), (8, -0.08), (24, -0.07, "hold")],
        "px": [(0, 0.0), (8, -0.04), (24, -0.04, "hold")],
        "n1p": [(0, 0.0), (8, -0.08), (24, -0.07, "hold")],
        "hp": [(0, 0.0), (8, 0.10), (24, 0.09, "hold")],
        "jaw": [(0, 0.0), (10, 0.08), (24, 0.06, "hold")],
        "earp": [(0, 0.0), (5, 0.30), (24, 0.28, "hold")],
        "mane": [(0, 0.0), (8, -0.20), (24, -0.18, "hold")],
        "tailp": [(0, 0.0), (10, 0.20), (24, 0.18, "hold")]}, idle_overlay=False))
    return out


# ---------------------------------------------------------------- creature-references (model.png) proportions
# The turnaround of creature-references/teneris/model.png read at 225.6 px per metre (nose to tail tip 3.95 m;
# withers 1.55 m): the head is carried low in front of the withers (nose 1.22 m, ears 1.85 m), the mane tops out
# at ~1.76 m, the croup is lower than the withers, the tail leaves the croup lower and further back and hangs in
# a long brush to the ground, the body is slimmer than the kit sheet's. One warp moves every part consistently.
import warp as _warp  # noqa: E402

WARP = [
    # tail set further back and lower, longer, hanging steeper (tail bones only: the hind feet stand under it)
    ("move", (-0.30, -0.10, 0.0), ("x", -0.92, -1.20), {"bones": ("Tail_",)}),
    ("rotate", (-1.20, 1.30, 0.0), (0, 0, 1), 0.10, ("x", -1.20, -1.45), {"bones": ("Tail_",)}),
    ("scale", (-1.20, 1.30, 0.0), (1.08, 1.08, 1.0), ("x", -1.20, -1.45), {"bones": ("Tail_",)}),
    # croup lower than the withers (only above the hip joint, so the thighs keep their length)
    ("move", (0.0, -0.14, 0.0), [("x", -0.35, -0.85), ("y", 1.12, 1.42)]),
    # ears 15 % shorter above the crown
    ("scale", (1.13, 1.92, 0.0), (1.0, 0.85, 1.0), [("y", 1.88, 1.98), ("x", 0.95, 1.05)]),
    # head carried low and forward of the withers; the neck bends down to it
    ("move", (-0.14, -0.36, 0.0), ("x", 0.72, 1.02)),
    # mane, withers and back ridge lower
    ("scale", (0.0, 1.45, 0.0), (1.0, 0.72, 1.0), [("y", 1.45, 1.60), ("x", -1.3, -1.0), ("x", 0.95, 0.75)]),
    # body and legs slimmer; the head keeps its width; the torso slimmer still above the elbows
    ("scale", (0.0, 0.0, 0.0), (1.0, 1.0, 0.80), ("x", 1.0, 0.75)),
    ("scale", (0.0, 0.0, 0.0), (1.0, 1.0, 0.88), [("x", 1.0, 0.75), ("y", 0.85, 1.05)]),
]
FUR_CARDS = _warp.cards(WARP, FUR_CARDS)
shade = _warp.unwarped_shade(WARP, shade)


# attack key poses compared with creature-references/<id>/0N-<phase>.png (tools/proof.py poses)
ATTACK_KEYS = {"clip": "attack_pounce", "frames": [12, 25, 32, 40], "az": 10, "el": 6}
