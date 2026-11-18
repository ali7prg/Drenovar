"""Камнеклык (kamneklyk): armoured stone boar, sculpted to the kit sheet kamneklyk_reference.png (front / left
side / rear read at 145 px per metre: withers 1.65 m, body with head 3.0 m as labelled). A pine cone of
overlapping slate shards (59, rear tips lifted, crest standing up to ~2.1 m) over neck, shoulders, back and rump,
shards on the brow, crescent main tusks curving out and up (~1.0 m span as drawn) and short lower tusks,
dark brown shaggy coat, cloven hooves, thin tufted tail, amber (non-glowing) eyes.
"""
import numpy as np

from sdf import Prim, Part, chain, bezier, rot_x, rot_y, rot_z
from rig import Skeleton
from common import SIDES, leg_bones, locks, scatter_on, surface_points, plate_frame, _frame

ID = "kamneklyk"
NAME = "Камнеклык"
VOXEL_BODY = 0.011
VOXEL_RIGID = 0.006
BAKE_EXTRUSION = 0.02
BAKE_RAY = 0.05
AO_SAMPLES = 40
AO_DISTANCE = 0.4

FRONT = {"joints": [(0.40, 1.45, 0.28), (0.60, 0.98, 0.48), (0.46, 0.64, 0.50), (0.54, 0.32, 0.50),
                    (0.57, 0.12, 0.50), (0.69, 0.0, 0.50)]}
HIND = {"joints": [(-1.05, 1.15, 0.22), (-1.02, 1.00, 0.44), (-0.80, 0.66, 0.47), (-1.12, 0.40, 0.47),
                   (-1.08, 0.12, 0.47), (-0.97, 0.0, 0.47)]}


# idle stance read off the side sheet (hoof contacts): near (left) fore forward, far fore back, far hind forward,
# near hind back - the views are compared in this pose
IDLE_STANCE = {("Front", "L"): {"dx": [(0, 0.08)]}, ("Front", "R"): {"dx": [(0, -0.18)]},
               ("Hind", "L"): {"dx": [(0, -0.25)]}, ("Hind", "R"): {"dx": [(0, 0.30)]}}


def side(p, s):
    return np.array([p[0], p[1], abs(p[2]) * s])


def skeleton():
    sk = Skeleton()
    sk.add("MotionRoot", None, (0, 0, 0))
    sk.add("Pelvis", "MotionRoot", (-1.05, 1.10, 0))
    sk.add("Spine_01", "Pelvis", (-0.62, 1.20, 0))
    sk.add("Spine_02", "Spine_01", (-0.15, 1.30, 0))
    sk.add("Chest", "Spine_02", (0.30, 1.34, 0))
    sk.add("Neck_01", "Chest", (0.66, 1.30, 0))
    sk.add("Neck_02", "Neck_01", (0.88, 1.22, 0))
    sk.add("Head", "Neck_02", (1.04, 1.12, 0), tail=(1.52, 0.86, 0))
    sk.add("Jaw", "Head", (1.10, 0.96, 0), tail=(1.42, 0.80, 0))
    sk.add("Nose", "Head", (1.36, 0.94, 0), tail=(1.53, 0.86, 0))
    for nm, s in SIDES:
        sk.add(f"Ear_{nm}", "Head", (0.96, 1.36, 0.20 * s), tail=(0.90, 1.52, 0.30 * s))
        sk.add(f"Tusk_{nm}", "Head", (1.40, 0.90, 0.12 * s), tail=(1.58, 1.33, 0.47 * s))
    sk.add("Hump", "Chest", (0.30, 1.70, 0), tail=(0.0, 1.80, 0))
    sk.add("Belly", "Spine_02", (-0.20, 0.80, 0), tail=(-0.20, 0.66, 0))
    for nm, s in SIDES:
        leg_bones(sk, "Front", "Chest", None, [side(j, s) for j in FRONT["joints"]], nm)
        leg_bones(sk, "Hind", "Pelvis", None, [side(j, s) for j in HIND["joints"]], nm)
    tail = [(-1.42, 1.14, 0), (-1.58, 1.08, 0), (-1.70, 0.96, 0), (-1.78, 0.83, 0)]
    for i, p in enumerate(tail):
        sk.add(f"Tail_0{i + 1}", "Pelvis" if i == 0 else f"Tail_0{i}", p,
               tail=(-1.83, 0.70, 0) if i == len(tail) - 1 else None)
    sk.socket("socket_head", "Head", (1.10, 1.36, 0))
    sk.socket("socket_mouth", "Jaw", (1.44, 0.82, 0))
    sk.socket("socket_chest", "Chest", (0.80, 0.78, 0))
    for nm, s in SIDES:
        sk.socket(f"socket_foot_front_{nm.lower()}", f"Toe_Front_{nm}", side(FRONT["joints"][5], s))
        sk.socket(f"socket_foot_hind_{nm.lower()}", f"Toe_Hind_{nm}", side(HIND["joints"][5], s))
        sk.socket(f"socket_tusk_{nm.lower()}", f"Tusk_{nm}", (1.58, 1.33, 0.47 * s))
    sk.socket("socket_tail_tip", "Tail_04", (-1.83, 0.70, 0))
    return sk


def leg_prims(kind, nm, s, J):
    j = [side(p, s) for p in J]
    U, L, Fo, T = f"UpperLeg_{kind}_{nm}", f"LowerLeg_{kind}_{nm}", f"Foot_{kind}_{nm}", f"Toe_{kind}_{nm}"
    big = 1.0 if kind == "Front" else 0.85
    out = []
    if kind == "Front":
        out += [Prim("cone", U, k=0.10, a=j[1], b=j[2], ra=0.26, rb=0.20, name="humerus"),
                Prim("sphere", L, k=0.06, c=j[2] + np.array([-0.06, 0.02, 0]), r=0.15, name="elbow"),
                Prim("cone", L, k=0.06, a=j[2], b=j[3], ra=0.21, rb=0.165, name="forearm")]
    else:
        out += [Prim("cone", U, k=0.12, a=j[1], b=j[2], ra=0.28, rb=0.19, name="femur"),
                Prim("cone", L, k=0.06, a=j[2], b=j[3], ra=0.20, rb=0.145, name="tibia"),
                Prim("sphere", Fo, k=0.04, c=j[3] + np.array([-0.06, 0.03, 0]), r=0.06, name="calcaneus")]
    big = 1.0 if kind == "Front" else 0.92
    out += [Prim("sphere", Fo, k=0.05, c=j[3], r=0.15 * big, name="carpus"),
            Prim("cone", Fo, k=0.04, a=j[3], b=j[4], ra=0.145 * big, rb=0.14 * big, name="cannon"),
            Prim("sphere", T, k=0.04, c=j[4], r=0.15 * big, name="fetlock")]
    hc = j[4] * 0.3 + j[5] * 0.7
    for c, sgn in (("in", -1), ("out", 1)):
        out.append(Prim("ellipsoid", T, k=0.016, mat="hoof", name=f"claw_{c}",
                        c=np.array([hc[0], 0.072, j[5][2] + sgn * 0.088 * big]), r=(0.17 * big, 0.11, 0.092 * big),
                        R=rot_z(0.30)))
        # dewclaw behind the fetlock
        out.append(Prim("ellipsoid", T, k=0.012, mat="hoof", name=f"dew_{c}",
                        c=np.array([j[4][0] - 0.12, 0.12, j[5][2] + sgn * 0.07 * big]), r=(0.06, 0.04, 0.035),
                        R=rot_z(-0.6)))
    out.append(Prim("box", T, k=0.006, neg=True, name="cleft", c=np.array([j[5][0] + 0.05, 0.06, j[5][2]]),
                    h=(0.12, 0.11, 0.009), round=0.0))
    out.append(Prim("box", T, k=0.004, neg=True, name="sole", c=np.array([j[5][0] - 0.02, -0.10, j[5][2]]),
                    h=(0.25, 0.10, 0.22), round=0.0))
    return out


def body_core():
    P = [Prim("ellipsoid", "Spine_02", k=0.0, c=(-0.25, 1.05, 0), r=(0.95, 0.42, 0.62), name="barrel"),
         Prim("ellipsoid", "Chest", k=0.16, c=(0.38, 1.28, 0), r=(0.55, 0.40, 0.60), name="hump"),
         Prim("ellipsoid", "Chest", k=0.14, c=(0.62, 0.98, 0), r=(0.32, 0.38, 0.52), name="chestfront"),
         Prim("ellipsoid", "Belly", k=0.18, c=(-0.25, 0.84, 0), r=(0.72, 0.22, 0.54), name="belly"),
         Prim("ellipsoid", "Pelvis", k=0.16, c=(-1.05, 1.05, 0), r=(0.44, 0.36, 0.52), name="rump"),
         Prim("ellipsoid", "Hump", k=0.14, c=(0.25, 1.56, 0), r=(0.55, 0.20, 0.42), name="crest"),
         Prim("cone", "Neck_01", k=0.14, a=(0.60, 1.22, 0), b=(0.95, 1.12, 0), ra=0.52, rb=0.42, name="neck"),
         # head: wedge skull, heavy brow, long snout ending in a disc
         Prim("ellipsoid", "Head", k=0.10, c=(1.04, 1.13, 0), r=(0.34, 0.31, 0.30), name="skull"),
         Prim("ellipsoid", "Head", k=0.06, c=(1.12, 1.27, 0), r=(0.24, 0.10, 0.22), name="brow"),
         Prim("cone", "Nose", k=0.07, a=(1.16, 1.03, 0), b=(1.48, 0.88, 0), ra=0.20, rb=0.125, name="snout"),
         Prim("ellipsoid", "Nose", k=0.03, mat="snout", c=(1.53, 0.865, 0), r=(0.035, 0.10, 0.125), R=rot_z(0.4),
              name="disc"),
         Prim("cone", "Jaw", k=0.05, a=(1.08, 0.95, 0), b=(1.42, 0.80, 0), ra=0.16, rb=0.09, name="jaw"),
         Prim("box", "Head", k=0.006, neg=True, mat="mouth", c=(1.30, 0.86, 0), h=(0.17, 0.007, 0.08), round=0.004,
              R=rot_z(-0.40), name="mouthslit")]
    for nm, s in SIDES:
        P += [Prim("ellipsoid", "Jaw", k=0.07, c=(1.06, 1.00, 0.20 * s), r=(0.20, 0.16, 0.10), name=f"jowl{nm}"),
              Prim("sphere", "Nose", k=0.01, neg=True, c=(1.565, 0.865, 0.055 * s), r=0.026, name=f"nostril{nm}"),
              Prim("sphere", "Head", k=0.012, neg=True, c=(1.20, 1.20, 0.205 * s), r=0.034, name=f"socket{nm}")]
        ec = np.array([0.95, 1.43, 0.24 * s])
        Re = rot_x(-0.75 * s) @ rot_z(0.35)
        P += [Prim("ellipsoid", f"Ear_{nm}", k=0.03, c=ec, r=(0.05, 0.13, 0.08), R=Re, name=f"ear{nm}"),
              Prim("ellipsoid", f"Ear_{nm}", k=0.008, neg=True, mat="skin", c=ec + np.array([0.035, 0, 0]),
                   r=(0.03, 0.10, 0.055), R=Re, name=f"earcav{nm}")]
        P += [Prim("ellipsoid", f"Shoulder_{nm}", k=0.14, c=side((0.48, 1.12, 0.46), s), r=(0.36, 0.42, 0.22),
                   R=rot_z(-0.35), name=f"scapula{nm}"),
              Prim("ellipsoid", f"UpperLeg_Hind_{nm}", k=0.15, c=side((-1.02, 0.92, 0.40), s), r=(0.36, 0.40, 0.20),
                   R=rot_z(0.2), name=f"haunch{nm}")]
        P += leg_prims("Front", nm, s, FRONT["joints"])
        P += leg_prims("Hind", nm, s, HIND["joints"])
    P += chain([(-1.40, 1.15, 0), (-1.58, 1.08, 0), (-1.70, 0.96, 0), (-1.78, 0.83, 0), (-1.83, 0.72, 0)],
               [0.085, 0.065, 0.055, 0.05, 0.06], None, k=0.04, name="tail",
               bones=["Tail_01", "Tail_02", "Tail_03", "Tail_04"])
    return P


def body_bone(p):
    x, y, z = p
    if x > 0.95:
        return "Head"
    if x > 0.62:
        return "Neck_01" if y > 1.0 else "Chest"
    if y < 0.80:
        return "Belly" if -0.8 < x < 0.3 else ("Chest" if x > 0 else "Pelvis")
    if x > 0.10:
        return "Hump" if y > 1.55 else "Chest"
    if x > -0.40:
        return "Spine_02"
    if x > -0.85:
        return "Spine_01"
    return "Pelvis"


def build_body(rng):
    core = Part("body", body_core(), band=0.07)
    P = list(core.prims)
    hang = lambda p, n: np.array([-0.3, -1.0, 0])  # noqa: E731
    # bristle crest along the spine and the neck (short, upright)
    seeds = scatter_on(core, (0.10, 1.55, 0), (0.95, 0.18, 0.18), 40, rng)
    P += locks(core, seeds, lambda p, n: np.array([-1.0, 0.6, 0]), 0.20, 0.06, body_bone, lift=0.7, rng=rng,
               thick=0.4, k=0.03)
    # shaggy brown coat under the armour: flanks, belly hem, legs, cheeks
    seeds = scatter_on(core, (-0.20, 0.95, 0), (1.05, 0.35, 0.64), 70, rng)
    P += locks(core, seeds, lambda p, n: np.array([-0.6, -0.8, 0]), 0.20, 0.08, body_bone, lift=0.2, rng=rng,
               droop=0.3, thick=0.32)
    seeds = scatter_on(core, (-0.25, 0.66, 0), (0.70, 0.08, 0.50), 30, rng)
    P += locks(core, seeds, hang, 0.18, 0.08, body_bone, gravity=0.5, lift=0.1, rng=rng, droop=0.4)
    seeds = scatter_on(core, (1.0, 1.02, 0), (0.16, 0.18, 0.30), 22, rng)
    P += locks(core, seeds, lambda p, n: np.array([-1.0, -0.4, 0]), 0.16, 0.07, body_bone, lift=0.3, rng=rng)
    for nm, s in SIDES:
        fj = [side(j, s) for j in FRONT["joints"]]
        hj = [side(j, s) for j in HIND["joints"]]
        for c, r, cnt, L, bone in (((fj[2] + fj[3]) / 2 + np.array([-0.06, 0.05, 0]), (0.07, 0.14, 0.08), 7, 0.15,
                                    f"LowerLeg_Front_{nm}"),
                                   (fj[4] + np.array([-0.04, 0.05, 0]), (0.06, 0.05, 0.08), 6, 0.12,
                                    f"Toe_Front_{nm}"),
                                   (hj[4] + np.array([-0.04, 0.05, 0]), (0.06, 0.05, 0.08), 6, 0.12,
                                    f"Toe_Hind_{nm}")):
            seeds = scatter_on(core, c, r, cnt, rng)
            P += locks(core, seeds, hang, L, 0.06, lambda p, b=bone: b, gravity=0.4, lift=0.2, rng=rng, k=0.03)
    seeds = scatter_on(core, (-1.81, 0.76, 0), (0.06, 0.08, 0.06), 12, rng)
    P += locks(core, seeds, hang, 0.14, 0.05, lambda p: "Tail_04", gravity=0.6, lift=0.3, rng=rng, k=0.02)
    return Part("body", P, band=0.08)


def stone_plate(centre, n, back, L, W, T, bone, tilt, yaw, name, rng, mat="stone"):
    """creature-references slate shard: a flat elongated leaf - a slab carved to a long sharp rear point and a
    blunt hexagonal front - with a raised keel along its middle; its rear tip lifts off the body by `tilt`."""
    Rf = plate_frame(n, back)
    R = Rf @ rot_y(yaw) @ rot_z(tilt)
    c = np.asarray(centre, float)
    xa, ya, za = R[:, 0], R[:, 1], R[:, 2]
    out = [Prim("box", bone, grp=name, k=0.0, mat=mat, name=name + "a", c=c, h=(L * 0.5, T, W * 0.5), round=min(0.012, T * 0.4),
                R=R)]
    for sgn in (-1, 1):
        # long sharp rear point
        cc = c + xa * L * 0.5 + za * sgn * W * 0.5
        out.append(Prim("box", bone, grp=name, k=0.003, neg=True, name=name + f"cut{sgn}", c=cc,
                        h=(L * 0.62, T * 4, W * 0.36), round=0.0, R=R @ rot_y(sgn * 0.62)))
        # blunt hexagonal front
        cf = c - xa * L * 0.5 + za * sgn * W * 0.5
        out.append(Prim("box", bone, grp=name, k=0.003, neg=True, name=name + f"nick{sgn}", c=cf,
                        h=(L * 0.20, T * 4, W * 0.22), round=0.0, R=R @ rot_y(-sgn * 0.75)))
    # keel: a triangular ridge along the shard (box turned 45 deg about the shard's axis)
    out.append(Prim("box", bone, grp=name, k=0.012, mat=mat, name=name + "keel", c=c + ya * T * 0.9 + xa * L * 0.05,
                    h=(L * 0.40, T * 0.75, T * 0.75), round=0.004, R=R @ rot_x(np.pi / 4)))
    return out


def build_plates(core, rng, level=1):
    """Sheet armour (creature-references): a pine cone of slate shards from the nape to the croup - rows fanning
    from the spine down the flanks to mid-side (top shards lifted into a crest over the shoulders, side shards
    lying flatter and pointing back and down), alternate rows offset - and a column of shards up the forehead."""
    rows = [(1.02, 3, 0.62, 0.34, "Neck_01"), (0.86, 5, 1.00, 0.44, "Chest"), (0.68, 7, 1.30, 0.52, "Hump"),
            (0.49, 8, 1.42, 0.58, "Hump"), (0.30, 8, 1.42, 0.58, "Hump"), (0.10, 8, 1.40, 0.56, "Spine_02"),
            (-0.10, 7, 1.34, 0.54, "Spine_02"), (-0.30, 7, 1.30, 0.50, "Spine_01"), (-0.50, 7, 1.26, 0.46, "Spine_01"),
            (-0.70, 6, 1.18, 0.42, "Pelvis"), (-0.90, 5, 1.08, 0.38, "Pelvis"), (-1.10, 4, 0.96, 0.32, "Pelvis"),
            (-1.28, 3, 0.70, 0.26, "Pelvis")]
    specs = []
    for r, (x, n, amax, L, bone) in enumerate(rows):
        off = 0.5 if r % 2 else 0.0
        for i in range(n):
            u = (i + off) / max(1, n - 1 + off) if n > 1 else 0.5
            a = (u * 2 - 1) * amax
            b = bone
            if abs(a) > 0.9 and 0.0 < x < 0.9:
                b = "Shoulder_R" if a > 0 else "Shoulder_L"   # +Z is the right side
            st = np.array([x + rng.normal(0, 0.008), 1.25 + 1.4 * np.cos(a), 1.4 * np.sin(a)])
            crest = 1.0 if 0.2 < x < 0.95 else 0.0
            specs.append((st, L * (0.9 + 0.2 * rng.random()), b, a, crest))
    starts = np.array([sp[0] for sp in specs], np.float32)
    pts, nrm = surface_points(core, starts, steps=14)
    P = []
    for k, ((st, L, bone, a, crest), p, n) in enumerate(zip(specs, pts, nrm)):
        n = n / np.linalg.norm(n)
        side_f = min(abs(a) / 1.3, 1.0)
        lift = 0.42 - 0.30 * side_f + crest * 0.22 * (1 - side_f)
        P.append(stone_plate(p + n * 0.03, n, np.array([-1.0, -0.25 - 0.45 * side_f, 0]), L, L * 0.44,
                             0.022 + 0.006 * rng.random(), bone, lift + rng.normal(0, 0.02), rng.normal(0, 0.03),
                             f"plate{k}", rng))
    # forehead: a column of shards from between the eyes up over the crown, two flanking it, pointing back and up
    brow_starts = np.array([[1.36, 1.45, 0.0], [1.28, 1.58, 0.0], [1.18, 1.70, 0.0], [1.06, 1.80, 0.0],
                            [1.22, 1.55, 0.24], [1.22, 1.55, -0.24], [1.10, 1.70, 0.30], [1.10, 1.70, -0.30]],
                           np.float32)
    bp, bn = surface_points(core, brow_starts, steps=14)
    for k, (p, n) in enumerate(zip(bp, bn)):
        n = n / np.linalg.norm(n)
        L = (0.20, 0.24, 0.28, 0.32, 0.22, 0.22, 0.26, 0.26)[k]
        P.append(stone_plate(p + n * 0.025, n, np.array([-1.0, 0.55, 0]), L, L * 0.5, 0.042, "Head", 0.34, 0.0,
                             f"brow{k}", rng))
    brow = surface_points(core, np.array([[1.15, 1.6, 0.0]], np.float32), steps=14)
    shield = stone_plate(brow[0][0] + brow[1][0] * 0.09 + np.array([0.04, 0.02, 0]), brow[1][0],
                         np.array([-1.0, 0.45, 0]), 0.46, 0.52, 0.045, "Head", 0.22, 0.0, "headshield", rng)
    return P, shield


def tusks_part():
    P = []
    for nm, s in SIDES:
        root = np.array([1.40, 0.90, 0.13 * s])
        pts = bezier(root, np.array([1.62, 0.76, 0.32 * s]), np.array([1.76, 0.92, 0.54 * s]),
                     np.array([1.58, 1.33, 0.47 * s]), 16)
        P += chain(list(pts), list(np.linspace(0.105, 0.018, len(pts))), f"Tusk_{nm}", k=0.01, mat="tusk",
                   name=f"tusk{nm}")
        root2 = np.array([1.37, 0.84, 0.085 * s])
        pts2 = bezier(root2, root2 + np.array([0.06, 0.02, 0.05 * s]), root2 + np.array([0.09, 0.10, 0.09 * s]),
                      root2 + np.array([0.06, 0.18, 0.12 * s]), 6)
        P += chain(list(pts2), list(np.linspace(0.032, 0.008, len(pts2))), "Jaw", k=0.008, mat="tusk",
                   name=f"tusk2{nm}")
    return P


def eye_part():
    return Part("eyes", [Prim("sphere", "Head", k=0.0, mat="eye", c=(1.205, 1.20, 0.198 * s), r=0.03, name=f"eye{nm}")
                         for nm, s in SIDES], band=0.015)


FUR_KEEP = {0: 0.9, 1: 0.55, 2: 0.15}   # shaggy everywhere on the sheet: more cards than the default
FUR_CARDS = [  # sheet: long shaggy dark-brown coat with lighter tips, beard under the head, tufted tail
    {"centre": (-0.20, 0.86, 0), "radii": (1.00, 0.30, 0.66), "count": 380, "length": 0.30, "width": 0.09,
     "flow": lambda p, n: np.array([-0.5, -0.85, 0]), "lift": 0.12, "droop": 0.25, "tip": "#a87c5a"},  # flanks
    {"centre": (-0.25, 0.62, 0), "radii": (0.75, 0.10, 0.50), "count": 140, "length": 0.28, "width": 0.09,
     "flow": lambda p, n: np.array([-0.2, -1.0, 0]), "lift": 0.05, "gravity": 0.4, "droop": 0.2, "crossed": True,
     "tip": "#9a7052"},                                                                             # belly hem
    {"centre": (1.00, 1.05, 0), "radii": (0.25, 0.30, 0.36), "count": 200, "length": 0.28, "width": 0.09,
     "flow": lambda p, n: np.array([-1.0, -0.5, 0]), "lift": 0.2, "droop": 0.2, "crossed": True,
     "tip": "#b08666"},                                                                             # neck, beard
    {"centre": (0.55, 0.46, 0), "radii": (0.24, 0.52, 0.64), "count": 420, "length": 0.26, "width": 0.10,
     "flow": lambda p, n: np.array([-0.3, -1.0, 0]), "lift": 0.18, "droop": 0.1, "crossed": True,
     "tip": "#966c4e"},                                                                             # forelegs
    {"centre": (-1.00, 0.50, 0), "radii": (0.30, 0.52, 0.62), "count": 420, "length": 0.26, "width": 0.10,
     "flow": lambda p, n: np.array([-0.4, -1.0, 0]), "lift": 0.18, "droop": 0.1, "crossed": True,
     "tip": "#966c4e"},                                                                             # hind legs
    {"centre": (-1.15, 0.95, 0), "radii": (0.35, 0.35, 0.55), "count": 170, "length": 0.26, "width": 0.09,
     "flow": lambda p, n: np.array([-1.0, -0.6, 0]), "lift": 0.15, "droop": 0.2, "tip": "#a47a58"},   # rump
    {"centre": (-1.80, 0.78, 0), "radii": (0.07, 0.12, 0.07), "count": 60, "length": 0.24, "width": 0.07,
     "flow": lambda p, n: np.array([-0.2, -1.0, 0]), "lift": 0.2, "gravity": 0.5, "droop": 0.1, "crossed": True,
     "tip": "#b08666"},                                                                             # tail tuft
    {"centre": (-1.62, 1.02, 0), "radii": (0.14, 0.10, 0.07), "count": 30, "length": 0.10, "width": 0.05,
     "flow": lambda p, n: np.array([-0.6, -0.8, 0]), "lift": 0.15, "droop": 0.05, "crossed": True,
     "tip": "#9a7052"}]                                                                             # tail braid                                                                             # tail tuft

CLASSES = {"body": ["fur", "skin", "snout", "hoof", "mouth"], "stone": ["stone", "tusk", "eye"]}
CLASS_OF = {"base": "fur"}
AXIS_PRIMS = ("lock", "humerus", "forearm", "femur", "tibia", "cannon", "tail", "neck", "snout", "jaw", "tusk")
MATERIAL_NAMES = {"body": "Body", "stone": "Stone"}
_CACHE = {}


def build(rng=None):
    rng = rng or np.random.default_rng(9)
    sk = skeleton()
    core = Part("core", body_core(), band=0.07)
    plates, shield = build_plates(core, rng)
    parts = [{"name": "body", "part": build_body(rng), "material": "body", "rigid": None,
              "faces": (26000, 9000, 3000)},
             {"name": "eyes", "part": eye_part(), "material": "stone", "rigid": "Head", "faces": (240, 120, 40),
              "voxel": 0.003}]
    tp = tusks_part()
    for nm in ("L", "R"):
        parts.append({"name": f"tusk_{nm}", "part": Part(f"tusk_{nm}", [q for q in tp if q.bone == f"Tusk_{nm}"],
                                                          band=0.02), "material": "stone", "rigid": f"Tusk_{nm}",
                      "faces": (1400, 600, 180), "voxel": 0.004})
    parts.append({"name": "tusks_lower", "part": Part("tusks_lower", [q for q in tp if q.bone == "Jaw"], band=0.02),
                  "material": "stone", "rigid": "Jaw", "faces": (500, 220, 60), "voxel": 0.004})
    groups = []
    for pr in plates:
        if groups and groups[-1][0].bone == pr[0].bone and len(groups[-1]) < 3 * len(pr):
            groups[-1] = groups[-1] + pr
        else:
            groups.append(list(pr))
    for k, pr in enumerate(groups):
        n = max(1, round(len(pr) / 6))
        # the forehead shards face the camera in most views: twice the triangles (no holes at LOD1)
        m = 2 if pr[0].bone == "Head" else 1
        parts.append({"name": f"plate{k}", "part": Part(f"plate{k}", pr, band=0.03), "material": "stone",
                      "rigid": pr[0].bone, "faces": (240 * n * m, 100 * n * m, 30 * n * m), "sharp": 40})
    parts.append({"name": "headshield", "part": Part("headshield", shield, band=0.03), "material": "stone",
                  "rigid": "Head", "faces": (900, 380, 0), "level": 3, "sharp": 40})
    return sk, parts


def build_cached():
    if "b" not in _CACHE:
        _CACHE["b"] = build()
        _warp.apply(WARP, *_CACHE["b"])
        for k, p in enumerate(_CACHE["b"][1]):
            p["index"] = k
    return _CACHE["b"]


PROOF_COLORS = {"base": "#4a3627", "fur": "#4a3627", "fur_long": "#5a4231", "skin": "#3a2c26", "snout": "#5a4440",
                "hoof": "#4a3f38", "mouth": "#3a1c1a", "stone": "#77737a", "tusk": "#d8ccb0", "eye": "#d08a20"}


# ---------------------------------------------------------------- surface
from shading import lin, mix, sstep, fur_height, fur_streaks, tangent_flow  # noqa: E402
import noise  # noqa: E402

EMISSION_COLOR = "#E0A040"
LEVELS = {  # R: dark mineral regions, G: bronze-brown veins (III), B: light chips
    1: {"emission_strength": 1.0, "tint_r": (0.30, 0.30, 0.32, 0.0), "tint_g": (0.55, 0.36, 0.20, 0.0),
        "tint_b": (0.78, 0.76, 0.72, 0.0)},
    2: {"emission_strength": 1.0, "tint_r": (0.24, 0.24, 0.26, 0.75), "tint_g": (0.55, 0.36, 0.20, 0.0),
        "tint_b": (0.80, 0.78, 0.74, 0.8)},
    3: {"emission_strength": 1.0, "tint_r": (0.22, 0.22, 0.24, 0.8), "tint_g": (0.58, 0.38, 0.20, 0.9),
        "tint_b": (0.82, 0.80, 0.76, 0.9)},
}


def default_flow(P, part):
    w = sstep(0.75, 0.55, P[:, 1])[:, None]
    return np.asarray(np.array([-1.0, -0.3, 0.0]) * (1 - w) + np.array([-0.2, -1.0, 0.0]) * w, np.float32)


def shade(group, ctx):
    return shade_body(ctx) if group == "body" else shade_stone(ctx)


def shade_body(ctx):
    P, N = ctx.P, ctx.N
    y = P[:, 1]
    w = {c: ctx.W[:, i] for i, c in enumerate(CLASSES["body"])}
    flow = tangent_flow(ctx.flow, N)
    lod = ctx.lod
    hfur = fur_height(flow, 1.6, 3 if lod == 0 else (2 if lod == 1 else 1), clumps=True, seed=7)
    h0 = hfur(P) / 0.0028
    col = mix(lin("#553524"), lin("#3e2619"), sstep(0.1, 0.8, N[:, 1]))
    col = mix(col, lin("#6a4430"), sstep(-0.1, -0.7, N[:, 1]))
    col = mix(col, lin("#33271f"), sstep(0.55, 0.25, y))
    col = col * (1.0 + 0.18 * noise.fbm(P * 2.5, 3, seed=31)[:, None])
    streak = fur_streaks(P, flow, 0.9, seed=23)
    col = col * (0.80 + 0.28 * sstep(-1.0, 1.0, h0))[:, None] * (0.80 + 0.32 * (streak * 0.5 + 0.5))[:, None]
    col = col * np.array([1.30, 1.12, 0.98], np.float32)[None, :]   # creature-references coat: warm red-brown
    col = mix(col, lin("#3a2c26"), w["skin"])
    col = mix(col, lin("#5a4440"), w["snout"])
    rings = 0.5 + 0.5 * np.sin(y * 95.0 + noise.perlin(P * 12, 12) * 2.0)
    hoof = mix(lin("#2a211b"), lin("#5e4a38"), np.clip(sstep(0.18, 0.02, y) * 0.6 + rings * 0.35, 0, 1))
    col = mix(col, hoof, w["hoof"])
    col = mix(col, lin("#3a1c1a"), w["mouth"])
    rough = 0.84 + 0.06 * noise.perlin(P * 12, 3)
    rough = mix(rough, 0.62, w["skin"])
    rough = mix(rough, 0.50, w["snout"])
    rough = mix(rough, 0.40 + 0.12 * sstep(0.035, 0.0, y), w["hoof"])
    rough = mix(rough, 0.45, w["mouth"])

    def height(Q):
        return (hfur(Q) * w["fur"] * 1.7 + noise.perlin(Q * 120, 9) * 0.0005 * (w["skin"] + w["snout"]) +
                np.sin(Q[:, 1] * 240.0) * 0.0004 * w["hoof"])
    cavity = 1.0 - 0.3 * w["fur"] * sstep(0.2, -0.9, h0)
    variant = np.zeros((ctx.n, 4), np.float32)
    variant[:, 3] = 1
    return {"albedo": np.clip(col, 0, 1), "roughness": np.clip(rough, 0, 1), "height": height,
            "height_eps": 0.002 if lod == 0 else 0.0035, "cavity": cavity, "variant": variant}


def slate(P, N, scale=1.0, seed=17):
    """Faceted slate: Voronoi chips (height steps), crack seams, layered grain. Returns height, seam, chip id."""
    q = P * 4.0 * scale
    f1, f2, cid = noise.worley(q, seed)
    seam = 1 - sstep(0.0, 0.04, f2 - f1)
    facet = (cid - 0.5) * 0.004 + (f1 - 0.5) * 0.003
    grain = noise.perlin(P * np.array([30.0, 160.0, 30.0], np.float32) * scale, seed + 3) * 0.0011
    return facet + grain - seam * 0.004, seam, cid


def shade_stone(ctx):
    P, N = ctx.P, ctx.N
    w = {c: ctx.W[:, i] for i, c in enumerate(CLASSES["stone"])}
    rad = getattr(ctx, "rad", np.full(ctx.n, 0.05, np.float32))
    flow = tangent_flow(ctx.flow, N)
    h_s, seam, cid = slate(P, N)
    # grey slate, darker mineral patches, light chipped edges where the normal turns away from the plate face
    stone = mix(lin("#585356"), lin("#454040"), sstep(0.2, 0.8, cid))   # creature-references slate: dark grey
    mineral = sstep(0.15, 0.55, noise.fbm(P * 2.2, 3, seed=40))
    stone = mix(stone, lin("#3e3c3a"), mineral * 0.35)
    edge = sstep(0.55, 0.15, np.abs(N[:, 1])) * sstep(0.2, 0.6, noise.fbm(P * 9, 2, seed=41) + 0.5)
    stone = mix(stone, lin("#a06a40"), edge * 0.55)                     # copper-rust rims of the shards
    stone = stone * (0.92 + 0.16 * noise.perlin(P * np.array([20.0, 90.0, 20.0], np.float32), 19))[:, None]
    stone = mix(stone, lin("#2a2826"), seam * 0.85)
    veins = sstep(0.965, 0.995, 1 - np.abs(noise.perlin(noise.stretch_along(P * 4.0, flow, 3.0), 44)))
    tusk = mix(lin("#e8d8bd"), lin("#9c8466"), sstep(0.035, 0.075, rad))
    tusk = tusk * (0.92 + 0.1 * noise.ridged(noise.stretch_along(P * 50.0, flow, 0.3), 2, 6))[:, None]
    col = stone * w["stone"][:, None] + tusk * w["tusk"][:, None] + lin("#1a1210")[None, :] * w["eye"][:, None]
    for s in (-1, 1):
        c = np.array([1.205, 1.20, 0.198 * s], np.float32)
        ax = np.array([0.45, 0.05, 0.89 * s], np.float32)
        ax /= np.linalg.norm(ax)
        rel = P - c
        cosang = np.sum(rel * ax, 1) / np.maximum(np.linalg.norm(rel, axis=1), 1e-6)
        near = (np.linalg.norm(rel, axis=1) < 0.04).astype(np.float32) * w["eye"]
        col = mix(col, lin("#d0891e"), sstep(0.70, 0.78, cosang) * near)
        col = mix(col, lin("#070505"), sstep(0.93, 0.96, cosang) * near)
    rough = w["stone"] * (0.86 + 0.08 * cid - 0.08 * edge) + w["tusk"] * 0.45 + w["eye"] * 0.10

    def height(Q):
        hs, _s, _c = slate(Q, N)
        return hs * w["stone"] + noise.ridged(noise.stretch_along(Q * 50.0, flow, 0.3), 2, 6) * 0.0006 * w["tusk"]
    cavity = 1.0 - 0.35 * seam * w["stone"]
    variant = np.stack([mineral * w["stone"], veins * w["stone"], edge * w["stone"], np.ones(ctx.n, np.float32)], 1)
    return {"albedo": np.clip(col, 0, 1), "roughness": np.clip(rough, 0, 1), "height": height, "height_eps": 0.002,
            "cavity": cavity, "variant": variant}


# ---------------------------------------------------------------- animation
POSTURE = {}
BREATH_PERIOD_F = 45
BREATH_AMP = 1.2
CLIP_NAMES = ["idle", "walk", "run", "turn_left", "turn_right", "roar", "attack_tusk", "attack_charge",
              "attack_stomp", "hit", "death", "alert"]
SEMANTIC = {"Idle": "idle", "Walk": "walk", "Run": "run", "Alert": "alert", "Attack": "attack_tusk", "Hit": "hit",
            "Death": "death", "Roar": "roar"}
SERVER_EVENTS = {"creature_attack": "attack_tusk", "tusk_sweep": "attack_tusk"}


def clips(rig, sampler):
    import clips as C
    from anim import plan_feet
    from qmath import ease
    g = globals()
    pre = ID + "__"
    out = []
    walk_off = {("Hind", "L"): 0.0, ("Front", "L"): 0.25, ("Hind", "R"): 0.5, ("Front", "R"): 0.75}
    trot_off = {("Hind", "L"): 0.0, ("Front", "R"): 0.03, ("Hind", "R"): 0.5, ("Front", "L"): 0.53}

    out.append(C.standing(rig, g, pre + "idle", 90, {
        "nose": [(0, 0.0), (20, 0.05), (24, -0.03), (28, 0.04), (32, 0.0), (90, 0.0)],
        "earp": [(0, 0.0), (55, 0.0), (58, 0.25), (62, -0.05), (66, 0.0), (90, 0.0)],
        "eary": [(0, 0.0), (55, 0.0), (58, 0.15), (66, 0.0), (90, 0.0)],
        "hy": [(0, 0.0), (35, 0.06), (60, 0.06), (90, 0.0)],
        "n1p": [(0, 0.0), (40, -0.04), (90, 0.0)],
        "taily": [(0, 0.0), (15, 0.35), (25, -0.35), (35, 0.2), (45, 0.0), (90, 0.0)]}, loop=True,
        legs_fn=C.leg_keys(rig, IDLE_STANCE, 90)))

    def walk_body(ph):
        w = 2 * np.pi * ph
        return {"py": -0.02 * np.cos(2 * w), "pr": 0.035 * np.sin(w), "pyw": 0.02 * np.sin(w), "cr": -0.03 *
                np.sin(w), "n1p": 0.03 * np.sin(2 * w + 0.4), "hp": -0.02 * np.sin(2 * w), "gF": 0.06 * np.sin(w),
                "taily": 0.15 * np.sin(w + 1.0)}
    out.append(C.locomotion(rig, g, pre + "walk", 42, 1.2, 0.68, walk_off, 0.12, walk_body))

    def run_body(ph):
        w = 4 * np.pi * ph
        return {"py": 0.035 * np.sin(w) - 0.02, "pp": 0.03 * np.sin(w + 0.5) - 0.03, "px": 0.03, "n1p": -0.08,
                "hp": 0.04 - 0.03 * np.sin(w), "pr": 0.02 * np.sin(w / 2), "earp": -0.3, "tailp": 0.35,
                "gF": 0.08 * np.sin(w / 2)}
    out.append(C.locomotion(rig, g, pre + "run", 24, 4.2, 0.46, trot_off, 0.16, run_body))

    for name, sgn in (("turn_left", 1.0), ("turn_right", -1.0)):
        N = 30
        yaw = lambda fr, s=sgn: s * np.radians(45.0) * ease(fr / 25.0)  # noqa: E731
        a, b = ("L", "R") if sgn > 0 else ("R", "L")
        sw = {("Front", a): [(1, 8)], ("Front", b): [(6, 13)], ("Hind", a): [(12, 19)], ("Hind", b): [(17, 24)],
              }
        sw[("Front", a)].append((20, 26))
        legs = plan_feet(rig, N, lambda fr: (0.0, 0.0, yaw(fr)), sw, lift=0.10)
        out.append(C.standing(rig, g, pre + name, N, {
            "n1y": [(0, 0.0), (8, 0.20 * sgn), (22, 0.06 * sgn), (30, 0.0)],
            "hy": [(0, 0.0), (8, 0.12 * sgn), (30, 0.0)],
            "cy": [(0, 0.0), (10, 0.08 * sgn), (28, 0.0)],
            "pr": [(0, 0.0), (8, -0.04 * sgn), (20, 0.03 * sgn), (30, 0.0)],
            "taily": [(0, 0.0), (12, -0.3 * sgn), (30, 0.0)]},
            legs_fn=legs, motion={"yaw_deg": 45.0 * sgn, "yaw": [float(yaw(f)) for f in range(N + 1)]}))

    out.append(C.standing(rig, g, pre + "roar", 60, {
        "n1p": [(0, 0.0), (8, -0.10), (14, 0.20), (40, 0.22), (50, 0.05), (60, 0.0)],
        "hp": [(0, 0.0), (8, -0.08), (14, 0.16), (40, 0.18), (60, 0.0)],
        "jaw": [(0, 0.0), (10, 0.04), (15, 0.38), (38, 0.36), (46, 0.06), (50, 0.0)],
        "nose": [(0, 0.0), (14, 0.10), (40, 0.10), (50, 0.0)],
        "px": [(0, 0.0), (8, -0.06), (15, 0.05), (40, 0.04), (60, 0.0)],
        "py": [(0, 0.0), (8, -0.03), (15, 0.02), (60, 0.0)],
        "cp": [(0, 0.0), (8, 0.03), (15, -0.04), (40, -0.04), (60, 0.0)],
        "earp": [(0, 0.0), (12, -0.45), (44, -0.40), (56, 0.0)],
        "tailp": [(0, 0.0), (14, 0.5), (44, 0.4), (60, 0.0)]},
        events=[{"event": "sound", "frame": 14, "time": 14 / 30}]))

    out.append(C.standing(rig, g, pre + "attack_tusk", 36, {
        "n1p": [(0, 0.0), (10, -0.34), (12, -0.36), (15, 0.12), (18, 0.24), (26, 0.06), (36, 0.0)],
        "hp": [(0, 0.0), (10, -0.24), (12, -0.25), (15, 0.10), (18, 0.18), (36, 0.0)],
        "n1y": [(0, 0.0), (10, -0.10), (15, 0.12), (22, 0.04), (36, 0.0)],
        "hr": [(0, 0.0), (10, 0.08), (15, -0.14), (36, 0.0)],
        "px": [(0, 0.0), (10, -0.08), (15, 0.14), (20, 0.10), (36, 0.0)],
        "py": [(0, 0.0), (10, -0.07), (15, 0.03), (36, 0.0)],
        "pp": [(0, 0.0), (10, -0.05), (15, 0.06), (24, 0.0)],
        "gF": [(0, 0.0), (10, 0.08), (15, -0.10), (36, 0.0)],
        "earp": [(0, 0.0), (8, -0.4), (28, -0.3), (36, 0.0)], "tailp": [(0, 0.0), (12, 0.45), (36, 0.0)]},
        events=[{"event": "windup", "frame": 0}, {"event": "whoosh", "frame": 13}, {"event": "contact", "frame": 15},
                {"event": "recovery", "frame": 18}],
        windows={"windup": [0, 12], "active": [12, 18], "recovery": [18, 36], "impact": 15}))

    # charge: scrape the ground with the right front hoof, lower the head, burst forward 3 m, heavy stop
    N = 75
    dist = 3.0

    def cx(fr):
        if fr <= 27:
            return 0.0
        if fr <= 48:
            return dist * ease((fr - 27) / 21.0) ** 1.15
        if fr <= 56:
            return dist + 0.18 * np.sin(np.pi * (fr - 48) / 16.0)
        return (dist + 0.18) * (1 - ease((fr - 56) / 19.0))
    sw = {("Hind", "L"): [(27, 33), (37, 43), (58, 64)], ("Hind", "R"): [(28, 34), (38, 44), (62, 68)],
          ("Front", "L"): [(30, 36), (40, 46), (66, 72)], ("Front", "R"): [(31, 37), (41, 47), (52, 58)]}
    pl = plan_feet(rig, N, lambda fr: (cx(fr), 0.0, 0.0), sw, lift=0.16)
    scrape = C.leg_keys(rig, {("Front", "R"): {
        "dx": [(0, 0.0), (5, 0.10), (9, -0.22), (12, 0.06), (16, -0.22), (20, 0.0, "hold")],
        "dy": [(0, 0.0), (4, 0.10), (8, 0.0), (11, 0.10), (15, 0.0), (20, 0.0)],
        "toe": [(0, 0.0), (5, -0.6), (9, 0.1), (12, -0.6), (16, 0.1), (20, 0.0)]}}, N)

    def charge_legs(fr, prm):
        legs = pl(fr)
        if fr <= 21:
            legs[("Front", "R")] = scrape(fr, prm)[("Front", "R")]
        if 27 <= fr <= 37:      # the bound: forelegs reach ahead, hind legs drive out behind
            ext = np.sin(np.pi * (fr - 27) / 10.0)
            for k in legs:
                reach = 0.55 if k[0] == "Front" else -0.60
                legs[k] = dict(legs[k], tip=legs[k]["tip"] + np.array([reach * ext, 0.34 * ext, 0.0]),
                               toe=legs[k].get("toe", 0.0) + (0.3 if k[0] == "Front" else -0.5) * ext)
        if 36 <= fr <= 48:      # the forehand comes off the ground with the upward tusk toss
            up = np.sin(np.pi * (fr - 36) / 12.0)
            for k in (("Front", "L"), ("Front", "R")):
                legs[k] = dict(legs[k], tip=legs[k]["tip"] + np.array([0.16 * up, 0.62 * up, 0.0]),
                               toe=legs[k].get("toe", 0.0) - 0.7 * up, foot=legs[k].get("foot", 0.0) - 0.6 * up)
        return legs
    # creature-references kamneklyk/01-04: 20 preparation - braced on the forehooves, the snout almost on the ground;
    # 32 launch - the hind hooves drive the heavy body forward, head kept low; 41 contact - head and chest flung up,
    # the tusks sweeping from below; 58 recovery - a heavy stop on the forehooves, the head lowered
    out.append(C.standing(rig, g, pre + "attack_charge", N, {
        "n1p": [(0, 0.0), (14, -0.40), (20, -0.52), (27, -0.50), (32, -0.36), (37, -0.30), (41, 0.18), (45, 0.14),
                (50, -0.12), (58, -0.22), (66, -0.10), (75, 0.0)],
        "hp": [(0, 0.0), (14, -0.24), (20, -0.32), (27, -0.30), (32, -0.20), (37, -0.20), (41, 0.36), (45, 0.24),
               (50, -0.04), (58, -0.10), (75, 0.0)],
        "px": [(0, 0.0), (20, -0.12), (27, -0.14), (32, 0.10), (41, 0.10), (48, 0.08), (54, -0.10), (62, -0.06),
               (75, 0.0)],
        "py": [(0, 0.0), (14, -0.08), (20, -0.12), (27, -0.12), (32, 0.20), (36, 0.08), (41, 0.16), (45, 0.10),
               (50, -0.08), (58, -0.10), (66, -0.04), (75, 0.0)],
        "pp": [(0, 0.0), (20, -0.07), (27, -0.05), (32, -0.02), (36, -0.03), (41, 0.46), (45, 0.34), (50, 0.05),
               (58, -0.04), (75, 0.0)],
        "jaw": [(0, 0.0), (36, 0.05), (41, 0.30), (46, 0.20), (54, 0.0)],
        "earp": [(0, 0.0), (14, -0.45), (60, -0.3), (75, 0.0)],
        "nose": [(0, 0.0), (6, 0.08), (10, 0.0), (14, 0.08), (18, 0.0)],
        "tailp": [(0, 0.0), (24, 0.5), (50, 0.5), (75, 0.0)]},
        legs_fn=charge_legs,
        events=[{"event": "scrape", "frame": 9}, {"event": "scrape", "frame": 16}, {"event": "launch", "frame": 27},
                {"event": "contact", "frame": 40}, {"event": "brake", "frame": 51}, {"event": "recovery", "frame": 51}],
        windows={"windup": [0, 27], "active": [27, 51], "recovery": [51, 75], "impact": 40},
        motion={"forward_m": [float(cx(f)) for f in range(N + 1)]}))

    # stomp: rear back (front lifts, hind legs and pelvis take the weight), both front hooves slam at 28
    stomp = C.leg_keys(rig, {k: {
        "dy": [(0, 0.0), (8, 0.06), (20, 0.36), (25, 0.30), (28, 0.0, "hold"), (54, 0.0)],
        "dx": [(0, 0.0), (20, 0.08), (28, 0.14, "hold"), (40, 0.14), (50, 0.0), (54, 0.0)],
        "toe": [(0, 0.0), (20, -0.7), (26, -0.2), (28, 0.0), (54, 0.0)],
        "foot": [(0, 0.0), (20, -0.9), (26, -0.2), (28, 0.0), (54, 0.0)]} for k in (("Front", "L"), ("Front", "R"))},
        54)
    out.append(C.standing(rig, g, pre + "attack_stomp", 54, {
        "pp": [(0, 0.0), (10, 0.06), (20, 0.20), (25, 0.18), (28, -0.08), (34, -0.04), (54, 0.0)],
        "py": [(0, 0.0), (10, -0.05), (20, 0.06), (28, -0.10), (34, -0.06), (54, 0.0)],
        "px": [(0, 0.0), (10, -0.12), (20, -0.14), (28, 0.10), (40, 0.05), (54, 0.0)],
        "n1p": [(0, 0.0), (20, 0.20), (28, -0.20), (36, -0.08), (54, 0.0)],
        "hp": [(0, 0.0), (20, 0.08), (28, -0.10), (54, 0.0)],
        "jaw": [(0, 0.0), (20, 0.15), (28, 0.30), (36, 0.05), (44, 0.0)],
        "earp": [(0, 0.0), (18, -0.4), (40, -0.3), (54, 0.0)], "tailp": [(0, 0.0), (20, 0.5), (40, 0.3), (54, 0.0)]},
        legs_fn=stomp,
        events=[{"event": "windup", "frame": 0}, {"event": "contact", "frame": 28}, {"event": "dust", "frame": 28},
                {"event": "recovery", "frame": 31}],
        windows={"windup": [0, 27], "active": [27, 31], "recovery": [31, 54], "impact": 28}))

    out.append(C.standing(rig, g, pre + "hit", 18, {
        "px": [(0, 0.0), (4, -0.05), (10, -0.02), (18, 0.0)],
        "pr": [(0, 0.0), (4, 0.03), (12, -0.01), (18, 0.0)],
        "n1p": [(0, 0.0), (4, 0.08), (10, 0.0), (18, 0.0)],
        "hy": [(0, 0.0), (4, -0.06), (18, 0.0)],
        "earp": [(0, 0.0), (3, -0.5), (14, -0.2), (18, 0.0)]}, idle_overlay=False,
        events=[{"event": "hit", "frame": 2}]))

    out.append(C.death(rig, g, sampler, pre + "death", 84, {
        "pp": [(0, 0.0), (14, -0.10), (26, -0.06), (84, 0.0)],
        "pr": [(0, 0.0), (20, 0.04), (30, 0.25), (44, 0.95), (54, 1.20), (62, 1.26), (84, 1.26, "hold")],
        "py": [(0, 0.0), (14, -0.20), (24, -0.35), (44, -0.50), (84, -0.52, "hold")],
        "n1p": [(0, 0.0), (14, -0.12), (40, -0.10), (60, -0.18), (84, -0.18, "hold")],
        "n1r": [(0, 0.0), (44, -0.10), (84, -0.10)],
        "jaw": [(0, 0.0), (10, 0.18), (30, 0.10), (84, 0.08)],
        "earp": [(0, 0.0), (16, -0.5), (84, -0.6)], "tailp": [(0, 0.0), (30, -0.3), (84, -0.4)],
        "belly": [(0, 0.0), (66, 0.02), (74, -0.01), (84, 0.0)]},
        {"UpperLeg_Front": 0.30, "LowerLeg_Front": -0.40, "Foot_Front": -0.5, "Toe_Front": -0.3,
         "UpperLeg_Hind": -0.25, "LowerLeg_Hind": 0.40, "Foot_Hind": -0.25, "Toe_Hind": -0.2},
        buckle_end=22, fk_start=20, fk_end=38, lie_frame=44, search_bone="Neck_02", search_range=(0.0, -0.6)))

    out.append(C.standing(rig, g, pre + "alert", 30, {
        "hy": [(0, 0.0), (8, 0.0), (30, 0.0)],
        "n1p": [(0, 0.0), (8, 0.12), (30, 0.10, "hold")],
        "hp": [(0, 0.0), (8, -0.04), (30, -0.03, "hold")],
        "px": [(0, 0.0), (10, -0.04), (30, -0.035, "hold")],
        "gF": [(0, 0.0), (10, -0.05), (30, -0.05, "hold")],
        "earp": [(0, 0.0), (6, 0.30), (30, 0.28, "hold")],
        "nose": [(0, 0.0), (8, 0.06), (12, 0.0), (16, 0.06), (20, 0.0)],
        "tailp": [(0, 0.0), (10, 0.45), (30, 0.4, "hold")]}, idle_overlay=False))
    return out


# ---------------------------------------------------------------- creature-references (model.png) proportions
# kamneklyk/model.png read at 315 px per metre (snout to rump 3.0 m; the slate crest tops out at 2.02 m): the barrel
# and the shard cape are narrower than the kit sheet's (front view +-0.75 m at the flanks), the legs stand wider.
import warp as _warp  # noqa: E402

WARP = [
    ("scale", (0.0, 0.0, 0.0), (1.0, 1.0, 0.88), [("y", 0.70, 0.95), ("x", 1.25, 1.00)]),
]
FUR_CARDS = _warp.cards(WARP, FUR_CARDS)
shade = _warp.unwarped_shade(WARP, shade)


# attack key poses compared with creature-references/<id>/0N-<phase>.png (tools/proof.py poses)
ATTACK_KEYS = {"clip": "attack_charge", "frames": [20,32,41,58], "az": 22, "el": 8}
