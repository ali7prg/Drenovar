"""Горный Драгор (dragor; sheet: «Dragar / Mountain Colossus»): sculpted to the kit sheet dragor_reference.png
(front / left side / rear read at 80 px per metre; the sheet has no labels, 80 px/m is the closest fit to the
TXT numbers): low, wide reptile 6.5 m long, crocodile-dragon head with an open toothy jaw and a spiked crest,
short heavy neck, three rows of flat basalt dorsal spikes from the skull to the tail tip, big faceted plates on
back, shoulders, forearms and thighs with amber seams, charcoal scaled skin, five big horn claws per foot,
a thick tail sweeping down to the ground.
"""
import numpy as np

from sdf import Prim, Part, chain, bezier, rot_x, rot_y, rot_z
from rig import Skeleton
from common import SIDES, leg_bones, locks, scatter_on, surface_points, plate_frame, _frame

ID = "dragor"
NAME = "Горный Драгор"
VOXEL_BODY = 0.018
VOXEL_RIGID = 0.009
BAKE_EXTRUSION = 0.03
BAKE_RAY = 0.08
AO_SAMPLES = 40
AO_DISTANCE = 0.7

FRONT = {"joints": [(1.00, 2.20, 0.50), (1.45, 1.75, 0.90), (1.30, 1.05, 0.95), (1.55, 0.42, 0.92),
                    (1.70, 0.16, 0.92), (2.05, 0.0, 0.92)]}
HIND = {"joints": [(-1.20, 1.90, 0.42), (-0.95, 1.55, 0.78), (-0.40, 1.05, 0.82), (-0.85, 0.44, 0.76),
                   (-0.72, 0.15, 0.76), (-0.40, 0.0, 0.76)]}
TAIL = [(-1.55, 1.38, 0), (-1.95, 1.16, 0), (-2.35, 1.02, 0), (-2.70, 0.92, 0), (-2.98, 0.80, 0), (-3.18, 0.60, 0),
        (-3.30, 0.42, 0)]   # sheet: thick, low tail (lower edge ~0.7-0.8 m from the rump to x -2.8)


# idle stance read off the side sheet (paw contacts): near (left) fore forward, far fore back, far hind forward,
# near hind back - the views are compared in this pose
IDLE_STANCE = {("Front", "L"): {"dx": [(0, 0.25)]}, ("Front", "R"): {"dx": [(0, -0.25)]},
               ("Hind", "L"): {"dx": [(0, -0.40)]}, ("Hind", "R"): {"dx": [(0, 0.15)]}}


def tail_y(x):
    """Tail centre line height at x (for seeding plates and blades right above it)."""
    xs = np.array([p[0] for p in TAIL])[::-1]
    ys = np.array([p[1] for p in TAIL])[::-1]
    return float(np.interp(x, xs, ys))


def tail_bone(x):
    """Tail bone whose segment holds x (for rigid tail plates)."""
    for i in range(len(TAIL) - 1):
        if x >= TAIL[i + 1][0]:
            return f"Tail_0{i + 1}"
    return f"Tail_0{len(TAIL) - 1}"


def side(p, s):
    return np.array([p[0], p[1], abs(p[2]) * s])


def skeleton():
    sk = Skeleton()
    sk.add("MotionRoot", None, (0, 0, 0))
    sk.add("Pelvis", "MotionRoot", (-1.25, 1.85, 0))
    sk.add("Spine_01", "Pelvis", (-0.55, 2.05, 0))
    sk.add("Spine_02", "Spine_01", (0.20, 2.15, 0))
    sk.add("Chest", "Spine_02", (0.95, 2.10, 0))
    sk.add("Neck_01", "Chest", (1.65, 2.05, 0))
    sk.add("Neck_02", "Neck_01", (2.05, 1.98, 0))
    sk.add("Head", "Neck_02", (2.35, 1.96, 0), tail=(3.28, 1.78, 0))
    sk.add("Jaw", "Head", (2.40, 1.72, 0), tail=(3.05, 1.45, 0))
    sk.add("Tongue", "Jaw", (2.55, 1.68, 0), tail=(2.95, 1.60, 0))
    sk.add("Throat", "Neck_02", (2.00, 1.55, 0), tail=(2.30, 1.50, 0))
    for nm, s in SIDES:
        sk.add(f"Cheek_{nm}", "Head", (2.48, 1.86, 0.30 * s), tail=(2.78, 1.80, 0.28 * s))
    sk.add("Belly", "Spine_02", (-0.10, 1.25, 0), tail=(-0.10, 1.12, 0))
    for nm, s in SIDES:
        leg_bones(sk, "Front", "Chest", None, [side(j, s) for j in FRONT["joints"]], nm)
        leg_bones(sk, "Hind", "Pelvis", None, [side(j, s) for j in HIND["joints"]], nm)
        for kind, J in (("Front", FRONT), ("Hind", HIND)):
            toe = side(J["joints"][4], s)
            sk.add(f"Digit_In_{kind}_{nm}", f"Toe_{kind}_{nm}", toe + np.array([0.04, 0, -0.14 * s]),
                   tail=side(J["joints"][5], s) + np.array([-0.04, 0, -0.18 * s]))
            sk.add(f"Digit_Out_{kind}_{nm}", f"Toe_{kind}_{nm}", toe + np.array([0.04, 0, 0.14 * s]),
                   tail=side(J["joints"][5], s) + np.array([-0.04, 0, 0.18 * s]))
    for i in range(6):
        sk.add(f"Tail_0{i + 1}", "Pelvis" if i == 0 else f"Tail_0{i}", TAIL[i],
               tail=TAIL[6] if i == 5 else None)
    sk.socket("socket_head", "Head", (2.45, 2.30, 0))
    sk.socket("socket_mouth", "Jaw", (3.05, 1.60, 0))
    sk.socket("socket_chest", "Chest", (1.80, 1.30, 0))
    sk.socket("socket_slam_center", "Chest", (2.10, 0.0, 0))
    for nm, s in SIDES:
        sk.socket(f"socket_foot_front_{nm.lower()}", f"Toe_Front_{nm}", side(FRONT["joints"][5], s))
        sk.socket(f"socket_foot_hind_{nm.lower()}", f"Toe_Hind_{nm}", side(HIND["joints"][5], s))
        sk.socket(f"socket_claw_{nm.lower()}", f"Toe_Front_{nm}", side((2.20, 0.02, 0.92), s))
    sk.socket("socket_tail_tip", "Tail_06", TAIL[6])
    return sk


def toes(kind, nm, s, j):
    """Five thick toes fanning forward; outer two on the Digit_In/Out bones."""
    T = f"Toe_{kind}_{nm}"
    out = []
    spread = [-0.24, -0.12, 0.0, 0.12, 0.24]
    for i, dz in enumerate(spread):
        bone = f"Digit_In_{kind}_{nm}" if i == 0 else (f"Digit_Out_{kind}_{nm}" if i == 4 else T)
        base = j[4] + np.array([0.02, -0.02, dz * s * 0.6])
        tip = j[5] + np.array([-0.06 - 0.06 * abs(dz) / 0.24, 0.07, dz * s])
        r0 = 0.12 if kind == "Front" else 0.105
        out.append(Prim("cone", bone, k=0.04, name=f"toe{i}", a=base, b=tip, ra=r0, rb=r0 * 0.75))
    return out


def leg_prims(kind, nm, s, J):
    j = [side(p, s) for p in J]
    U, L, Fo, T = f"UpperLeg_{kind}_{nm}", f"LowerLeg_{kind}_{nm}", f"Foot_{kind}_{nm}", f"Toe_{kind}_{nm}"
    out = []
    if kind == "Front":
        out += [Prim("cone", U, k=0.16, a=j[1], b=j[2], ra=0.48, rb=0.36, name="humerus"),
                Prim("sphere", L, k=0.10, c=j[2] + np.array([-0.10, 0.02, 0]), r=0.30, name="elbow"),
                Prim("cone", L, k=0.10, a=j[2], b=j[3], ra=0.38, rb=0.28, name="forearm"),
                Prim("ellipsoid", L, k=0.10, c=j[2] * 0.6 + j[3] * 0.4 + np.array([0.06, 0, 0.02 * s]),
                     r=(0.26, 0.40, 0.26), name="forearm_m")]
    else:
        out += [Prim("cone", U, k=0.18, a=j[1], b=j[2], ra=0.52, rb=0.36, name="femur"),
                Prim("ellipsoid", U, k=0.16, c=j[1] * 0.5 + j[2] * 0.5 + np.array([-0.08, 0, 0]),
                     r=(0.42, 0.52, 0.32), name="thigh_m"),
                Prim("cone", L, k=0.10, a=j[2], b=j[3], ra=0.34, rb=0.24, name="shin")]
    out += [Prim("sphere", Fo, k=0.08, c=j[3], r=0.29 if kind == "Front" else 0.25, name="wrist"),
            Prim("cone", Fo, k=0.06, a=j[3], b=j[4], ra=0.27 if kind == "Front" else 0.24, rb=0.26, name="hand"),
            Prim("ellipsoid", T, k=0.06, c=j[4] + np.array([0.08, -0.04, 0]), r=(0.30, 0.13, 0.30), name="sole_pad")]
    out += toes(kind, nm, s, j)
    out.append(Prim("box", T, k=0.004, neg=True, name="sole", c=np.array([j[5][0] - 0.1, -0.15, j[5][2]]),
                    h=(0.6, 0.15, 0.5), round=0.0))
    return out


def body_core():
    # low, wide body: deep chest between the forelegs, belly ~1.2 m above the ground, hips lower than the withers
    P = [Prim("ellipsoid", "Chest", k=0.0, c=(0.55, 1.75, 0), r=(1.05, 0.62, 0.92), name="ribcage"),
         Prim("ellipsoid", "Chest", k=0.20, c=(1.40, 1.55, 0), r=(0.55, 0.50, 0.82), name="breast"),
         Prim("ellipsoid", "Belly", k=0.22, c=(-0.20, 1.40, 0), r=(0.95, 0.30, 0.90), name="belly"),
         Prim("ellipsoid", "Spine_01", k=0.22, c=(-0.55, 1.85, 0), r=(0.75, 0.45, 0.92), name="loin"),
         Prim("ellipsoid", "Pelvis", k=0.20, c=(-1.20, 1.70, 0), r=(0.55, 0.50, 0.85), name="hips"),
         Prim("cone", "Neck_01", k=0.18, a=(1.50, 2.00, 0), b=(2.20, 1.95, 0), ra=0.62, rb=0.42, name="neck"),
         Prim("ellipsoid", "Throat", k=0.16, c=(2.05, 1.62, 0), r=(0.40, 0.25, 0.42), name="dewlap"),
         # crocodile-dragon head: broad skull, long tapering upper jaw, heavy lower jaw, mouth open
         Prim("ellipsoid", "Head", k=0.12, c=(2.45, 2.02, 0), r=(0.42, 0.28, 0.36), name="skull"),
         Prim("cone", "Head", k=0.10, a=(2.62, 1.98, 0), b=(3.22, 1.82, 0), ra=0.27, rb=0.14, name="snout"),
         Prim("cone", "Jaw", k=0.08, a=(2.40, 1.70, 0), b=(3.05, 1.45, 0), ra=0.22, rb=0.11, name="jaw"),
         Prim("box", "Head", k=0.012, neg=True, mat="mouth", c=(2.90, 1.66, 0), h=(0.38, 0.06, 0.24), round=0.025,
              R=rot_z(-0.24), name="mouthgap")]
    for nm, s in SIDES:
        P += [Prim("ellipsoid", f"Cheek_{nm}", k=0.08, c=(2.45, 1.86, 0.30 * s), r=(0.28, 0.20, 0.16),
                   name=f"cheek{nm}"),
              Prim("ellipsoid", "Head", k=0.06, c=(2.78, 2.12, 0.20 * s), r=(0.24, 0.08, 0.12), R=rot_z(-0.25),
                   name=f"brow{nm}"),
              Prim("sphere", "Head", k=0.015, neg=True, c=(2.91, 1.99, 0.255 * s), r=0.055, name=f"socket{nm}"),
              Prim("ellipsoid", f"Shoulder_{nm}", k=0.18, c=side((1.05, 2.02, 0.80), s), r=(0.60, 0.55, 0.32),
                   R=rot_z(-0.35), name=f"scapula{nm}"),
              Prim("ellipsoid", f"UpperLeg_Hind_{nm}", k=0.18, c=side((-0.85, 1.45, 0.78), s), r=(0.55, 0.55, 0.30),
                   R=rot_z(0.30), name=f"haunch{nm}")]
        P += leg_prims("Front", nm, s, FRONT["joints"])
        P += leg_prims("Hind", nm, s, HIND["joints"])
    radii = [0.44, 0.34, 0.28, 0.22, 0.18, 0.12, 0.05]
    P += chain(TAIL, radii, None, k=0.10, name="tail", bones=[f"Tail_0{i + 1}" for i in range(6)])
    return P


def rock_plate(centre, n, back, L, W, T, bone, tilt, yaw, name, rng):
    """Thick faceted rock slab with carved rear point and a raised ridge (rigid to one bone)."""
    Rf = plate_frame(n, back)
    R = Rf @ rot_y(yaw) @ rot_z(tilt)
    c = np.asarray(centre, float)
    xa, ya, za = R[:, 0], R[:, 1], R[:, 2]
    out = [Prim("box", bone, k=0.0, mat="stone", name=name + "a", c=c, h=(L * 0.5, T * 0.5, W * 0.5), round=0.02,
                R=R),
           Prim("box", bone, k=0.04, mat="stone", name=name + "ridge", c=c + ya * T * 0.45 - xa * L * 0.05,
                h=(L * 0.30, T * 0.40, W * 0.20), round=0.015, R=R @ rot_y(np.pi / 4) @ rot_x(0.0))]
    for sgn in (-1, 1):
        cc = c + xa * L * 0.5 + za * sgn * W * 0.5
        out.append(Prim("box", bone, k=0.006, neg=True, name=name + f"cut{sgn}", c=cc, h=(L * 0.40, T * 4, W * 0.32),
                        round=0.0, R=R @ rot_y(sgn * 0.7)))
    return out


def spike(base, n, height, radius, bone, name, lean=np.array([-0.35, 0, 0])):
    d = n + lean
    d = d / np.linalg.norm(d)
    return [Prim("cone", bone, k=0.0, mat="stone", name=name, a=base - n * 0.05, b=base + d * height, ra=radius,
                 rb=radius * 0.12)]


def blade(base, n, height, width, thick, bone, name, lean=0.55, along=np.array([-1.0, 0.0, 0.0])):
    """A flat triangular basalt blade standing on the surface (dorsal spike of the sheet): a thin box carved
    into a point that leans back, with a faceted ridge."""
    up = n / np.linalg.norm(n)
    fwd = along - np.dot(along, up) * up
    fwd = fwd / max(np.linalg.norm(fwd), 1e-6)
    d = up * np.cos(lean) + fwd * np.sin(lean)
    side_ax = np.cross(d, fwd if abs(np.dot(d, fwd)) < 0.95 else up)
    side_ax /= np.linalg.norm(side_ax)
    fw = np.cross(side_ax, d)
    R = np.stack([fw, d, side_ax], 1)  # local x = across the blade (toward the front), y = up the blade, z = flat
    c = base + d * height * 0.45
    out = [Prim("box", bone, k=0.0, mat="stone", name=name + "a", c=c, h=(width * 0.5, height * 0.5, thick),
                round=0.015, R=R)]
    for sgn in (-1, 1):
        cc = c + d * height * 0.5 + fw * sgn * width * 0.5
        out.append(Prim("box", bone, k=0.006, neg=True, name=name + f"cut{sgn}", c=cc,
                        h=(width * 0.42, height * 0.62, thick * 4), round=0.0, R=R @ rot_z(sgn * (0.42 if sgn > 0 else 0.25))))
    out.append(Prim("box", bone, k=0.02, mat="stone", name=name + "ridge", c=c - d * height * 0.08,
                    h=(width * 0.14, height * 0.36, thick * 1.5), round=0.01, R=R))
    return out


def build_armor(core, rng):
    """Rows of big faceted plates over back, shoulders, forearms, thighs and tail; three rows of dorsal blades
    from the skull crest to the tail tip (central row tallest)."""
    plates, spikes = [], []
    specs = []
    A = (0.0, 0.42, -0.42, 0.84, -0.84, 1.22, -1.22)
    B = (0.21, -0.21, 0.63, -0.63, 1.03, -1.03, 1.40, -1.40)
    rows = [(1.95, (0.30, -0.30, 0.75, -0.75), 0.50, "Neck_01"), (1.70, A[:5], 0.56, "Chest"),
            (1.42, B[:6], 0.60, "Chest"), (1.12, A, 0.64, "Chest"), (0.82, B, 0.64, "Chest"),
            (0.52, A, 0.64, "Chest"), (0.22, B, 0.62, "Spine_02"), (-0.08, A, 0.62, "Spine_02"),
            (-0.38, B, 0.60, "Spine_01"), (-0.68, A, 0.58, "Spine_01"), (-0.98, B[:6], 0.56, "Pelvis"),
            (-1.26, A[:5], 0.52, "Pelvis")]
    for (x, angs, L, bone) in rows:
        for a in angs:
            b = bone
            if abs(a) > 1.0 and 0.4 < x < 1.4:
                b = "Shoulder_R" if a > 0 else "Shoulder_L"
            specs.append((np.array([x + rng.normal(0, 0.03), 1.8 + 2.0 * np.cos(a), 2.0 * np.sin(a)]),
                          L * (0.9 + 0.2 * rng.random()), L * 0.85, b, 0.10))
    for nm, s in SIDES:
        specs.append((side((1.30, 1.95, 2.2), s), 0.70, 0.62, f"Shoulder_{nm}", 0.08))      # shoulder cap
        specs.append((side((1.35, 1.25, 2.2), s), 0.70, 0.62, f"UpperLeg_Front_{nm}", 0.08))  # upper arm
        specs.append((side((1.40, 0.80, 2.2), s), 0.62, 0.55, f"LowerLeg_Front_{nm}", 0.08))  # forearm
        specs.append((side((1.55, 0.50, 2.0), s), 0.48, 0.45, f"LowerLeg_Front_{nm}", 0.07))  # wrist guard
        specs.append((side((-0.80, 1.55, 2.2), s), 0.78, 0.70, f"UpperLeg_Hind_{nm}", 0.08))  # thigh
        specs.append((side((-0.55, 0.90, 2.0), s), 0.55, 0.50, f"LowerLeg_Hind_{nm}", 0.07))  # shin
        specs.append((side((1.50, 0.20, 1.6), s), 0.36, 0.34, f"LowerLeg_Front_{nm}", 0.06))  # front paw guard
        specs.append((side((-0.95, 1.05, 2.0), s), 0.60, 0.52, f"UpperLeg_Hind_{nm}", 0.08))  # lower thigh
        specs.append((side((-0.62, 0.40, 1.8), s), 0.40, 0.36, f"LowerLeg_Hind_{nm}", 0.06))  # hock guard
        for i, tx in enumerate((-1.62, -1.95, -2.28, -2.60, -2.90, -3.12)):
            tb = tail_bone(tx)
            specs.append((np.array([tx, tail_y(tx) + 0.25, 0.9 * s]), 0.46 - 0.05 * i, 0.40 - 0.045 * i,
                          tb, 0.07 - 0.008 * i))                                                # tail sides
    for i, tx in enumerate((-1.62, -1.95, -2.28, -2.60, -2.90)):
        tb = tail_bone(tx)
        specs.append((np.array([tx, tail_y(tx) + 0.9, 0.0]), 0.44 - 0.05 * i, 0.40 - 0.05 * i, tb,
                      0.07 - 0.008 * i))                                                        # tail top
    starts = np.array([sp[0] for sp in specs], np.float32)
    pts, nrm = surface_points(core, starts, steps=16)
    for k, ((st, L, W, bone, T), p, n) in enumerate(zip(specs, pts, nrm)):
        n = n / np.linalg.norm(n)
        plates.append(rock_plate(p + n * 0.05, n, np.array([-1.0, -0.1, 0]), L, W, T, bone,
                                 0.18 + rng.normal(0, 0.04), rng.normal(0, 0.12), f"plate{k}", rng))
    # dorsal blades: central row along the spine and tail, two lower side rows over the back
    central = [(2.30, 0.30, "Head"), (1.88, 0.44, "Neck_01"), (1.48, 0.66, "Chest"), (1.08, 0.84, "Chest"),
               (0.66, 0.84, "Chest"), (0.24, 0.70, "Spine_02"), (-0.18, 0.56, "Spine_02"), (-0.58, 0.38, "Spine_01"),
               (-0.98, 0.24, "Pelvis"), (-1.38, 0.16, "Pelvis"), (-1.78, 0.20, "Tail_01"), (-2.16, 0.17, "Tail_02"),
               (-2.52, 0.14, "Tail_03"), (-2.86, 0.11, "Tail_04"), (-3.12, 0.08, "Tail_05")]
    starts = np.array([[x, (3.6 if x > -1.5 else tail_y(x) + 0.9), 0.0] for x, _h, _b in central], np.float32)
    pts, nrm = surface_points(core, starts, steps=18)
    for i, ((x, h, bone), p, n) in enumerate(zip(central, pts, nrm)):
        spikes.append(blade(p + n * 0.06, np.array([0, 1.0, 0]) * 0.6 + n * 0.4, h, h * 0.62, 0.05, bone,
                            f"spike{i}", lean=0.55 if x > -1.5 else 0.85))
    for nm, s in SIDES:
        side_row = [(1.30, 0.40, f"Shoulder_{nm}"), (0.90, 0.46, "Chest"), (0.48, 0.48, "Chest"),
                    (0.05, 0.44, "Spine_02"), (-0.38, 0.40, "Spine_01"), (-0.80, 0.36, "Pelvis"),
                    (-1.20, 0.30, "Pelvis")]
        starts = np.array([[x, 3.4, 0.95 * s] for x, _h, _b in side_row], np.float32)
        pts, nrm = surface_points(core, starts, steps=18)
        for i, ((x, h, bone), p, n) in enumerate(zip(side_row, pts, nrm)):
            spikes.append(blade(p + n * 0.06, n, h, h * 0.62, 0.045, bone, f"sspike{nm}{i}", lean=0.6))
    # skull crest: horn blades at the back of the head pointing back
    for nm, s in SIDES:
        starts = np.array([[2.30, 2.40, 0.22 * s], [2.50, 2.35, 0.26 * s]], np.float32)
        pts, nrm = surface_points(core, starts, steps=18)
        for i, (p, n) in enumerate(zip(pts, nrm)):
            spikes.append(blade(p + n * 0.03, n, 0.30 - 0.06 * i, 0.16, 0.035, "Head", f"crest{nm}{i}", lean=1.0))
    return plates, spikes


def teeth_part():
    """Rows of sharp teeth along the open jaws (upper pointing down, lower pointing up), longest at the front."""
    P = []
    for nm, s in SIDES:
        for i in range(8):
            t = i / 7.0
            a = np.array([3.16 - 0.54 * t, 1.755 - 0.03 * t, (0.055 + 0.19 * t) * s])
            L = 0.13 if i in (1, 2) else (0.10 if i < 5 else 0.07)
            P.append(Prim("cone", "Head", k=0.006, mat="tooth", name=f"tu{nm}{i}", a=a,
                          b=a + np.array([0.015, -L, 0]), ra=0.030, rb=0.004))
        for i in range(7):
            t = i / 6.0
            a2 = np.array([2.98 - 0.44 * t, 1.535 + 0.07 * t, (0.05 + 0.17 * t) * s])
            L = 0.11 if i in (1, 2) else 0.07
            P.append(Prim("cone", "Jaw", k=0.006, mat="tooth", name=f"tl{nm}{i}", a=a2,
                          b=a2 + np.array([0.01, L, 0]), ra=0.028, rb=0.004))
    return P


def claws_part(kind, nm, s):
    j = [side(p, s) for p in (FRONT if kind == "Front" else HIND)["joints"]]
    P = []
    for i, dz in enumerate([-0.24, -0.12, 0.0, 0.12, 0.24]):
        bone = f"Digit_In_{kind}_{nm}" if i == 0 else (f"Digit_Out_{kind}_{nm}" if i == 4 else f"Toe_{kind}_{nm}")
        base = j[5] + np.array([-0.08 - 0.06 * abs(dz) / 0.24, 0.08, dz * s])
        L = 0.26 if kind == "Front" else 0.20
        pts = bezier(base, base + np.array([0.08, 0.02, 0]), base + np.array([L * 0.8, -0.02, 0]),
                     base + np.array([L, -0.08, 0]), 5)
        P += chain(list(pts), list(np.linspace(0.075, 0.012, len(pts))), bone, k=0.006, mat="claw", name=f"claw{i}")
    return P


def eye_part():
    return Part("eyes", [Prim("sphere", "Head", k=0.0, mat="eye", c=(2.905, 1.995, 0.245 * s), r=0.055, name=f"eye{nm}")
                         for nm, s in SIDES], band=0.02)


CLASSES = {"skin": ["skin", "mouth", "tooth", "claw", "eye"], "stone": ["stone"]}
CLASS_OF = {"base": "skin"}
AXIS_PRIMS = ("humerus", "forearm", "femur", "shin", "hand", "toe", "tail", "neck", "snout", "jaw", "claw", "spike",
              "tu", "tl")
MATERIAL_NAMES = {"skin": "Skin", "stone": "Stone"}
_CACHE = {}


def build(rng=None):
    rng = rng or np.random.default_rng(13)
    sk = skeleton()
    core = Part("core", body_core(), band=0.10)
    plates, spikes = build_armor(core, rng)
    parts = [{"name": "body", "part": Part("body", body_core(), band=0.10), "material": "skin", "rigid": None,
              "faces": (30000, 10000, 3000)},
             {"name": "eyes", "part": eye_part(), "material": "skin", "rigid": "Head", "faces": (240, 120, 40),
              "voxel": 0.005}]
    tp = teeth_part()
    parts.append({"name": "teeth_upper", "part": Part("teeth_upper", [q for q in tp if q.bone == "Head"], band=0.02),
                  "material": "skin", "rigid": "Head", "faces": (1400, 560, 0), "voxel": 0.004})
    parts.append({"name": "teeth_lower", "part": Part("teeth_lower", [q for q in tp if q.bone == "Jaw"], band=0.02),
                  "material": "skin", "rigid": "Jaw", "faces": (1400, 560, 0), "voxel": 0.004})
    for kind in ("Front", "Hind"):
        for nm, s in SIDES:
            cp = claws_part(kind, nm, s)
            for bone in sorted({q.bone for q in cp}):
                parts.append({"name": f"claws_{bone}", "part": Part(f"claws_{bone}", [q for q in cp if q.bone == bone],
                                                                    band=0.02),
                              "material": "skin", "rigid": bone, "faces": (380, 160, 50), "voxel": 0.006})
    def grouped(pieces, per):
        out = []
        for pr in pieces:
            if out and out[-1][0][0].bone == pr[0].bone and len(out[-1]) < per:
                out[-1].append(pr)
            else:
                out.append([pr])
        return out
    for k, grp in enumerate(grouped(plates, 3)):
        n = len(grp)
        parts.append({"name": f"plate{k}", "part": Part(f"plate{k}", [q for pr in grp for q in pr], band=0.04),
                      "material": "stone", "rigid": grp[0][0].bone, "faces": (260 * n, 100 * n, 30 * n), "sharp": 40})
    for k, grp in enumerate(grouped(spikes, 4)):
        n = len(grp)
        parts.append({"name": f"spike{k}", "part": Part(f"spike{k}", [q for pr in grp for q in pr], band=0.04),
                      "material": "stone", "rigid": grp[0][0].bone, "faces": (200 * n, 80 * n, 24 * n), "sharp": 50})
    return sk, parts


def build_cached():
    if "b" not in _CACHE:
        _CACHE["b"] = build()
        for k, p in enumerate(_CACHE["b"][1]):
            p["index"] = k
    return _CACHE["b"]


# ---------------------------------------------------------------- surface
from shading import lin, mix, sstep, tangent_flow  # noqa: E402
import noise  # noqa: E402

EMISSION_COLOR = "#F0A12D"
LEVELS = {  # R: shoulder/forelimb plates (darker contrast, II+), G: deep seams in the plates and chest/tail skin
    # creases (glow), B: light chips on plate edges and spikes (III). Light stays inside seams: never a whole
    # glowing plate. "groups" overrides one material group: the skin creases glow far less than the plate seams.
    1: {"emission_strength": 0.8, "tint_r": (0.42, 0.40, 0.38, 0.0), "tint_b": (0.80, 0.76, 0.68, 0.0),
        "emit_g": 0.0},
    2: {"emission_strength": 1.05, "tint_r": (0.30, 0.29, 0.28, 0.55), "tint_b": (0.80, 0.76, 0.68, 0.0),
        "emit_g": 0.30, "groups": {"skin": {"emit_g": 0.06}}},
    3: {"emission_strength": 1.3, "tint_r": (0.27, 0.26, 0.25, 0.65), "tint_b": (0.74, 0.70, 0.64, 0.6),
        "emit_g": 0.65, "groups": {"skin": {"emit_g": 0.16}}},
}


def default_flow(P, part):
    return np.broadcast_to(np.array([-1.0, -0.2, 0.0], np.float32), P.shape).copy()


def shade(group, ctx):
    return shade_skin(ctx) if group == "skin" else shade_stone(ctx)


def scales(P, size=1.0, seed=5):
    f1, f2, cid = noise.worley(P * (14.0 / size), seed)
    edge = 1 - sstep(0.0, 0.12, f2 - f1)
    h = (1 - edge) * 0.0025 * (0.6 + 0.4 * cid) - edge * 0.002
    return h, edge, cid


def shade_skin(ctx):
    P, N = ctx.P, ctx.N
    y = P[:, 1]
    w = {c: ctx.W[:, i] for i, c in enumerate(CLASSES["skin"])}
    rad = getattr(ctx, "rad", np.full(ctx.n, 0.1, np.float32))
    h_s, edge, cid = scales(P)
    col = mix(lin("#4c3f37"), lin("#62534a"), cid * 0.6)
    col = mix(col, lin("#6e5f55"), sstep(-0.1, -0.7, N[:, 1]) * 0.6)
    col = mix(col, lin("#1c1511"), edge * 0.7)
    col = col * (1.0 + 0.15 * noise.fbm(P * 1.5, 3, seed=50)[:, None])
    # faint amber in the deepest skin creases near the chest and under the plates
    crease = edge * sstep(0.35, 0.65, noise.fbm(P * 3.0, 2, seed=52) + 0.5) * sstep(1.1, 1.7, y)
    tooth = mix(lin("#d9cdb3"), lin("#8b7a5c"), sstep(0.012, 0.03, rad))
    claw = mix(lin("#e0ccb6"), lin("#6a5644"), sstep(0.02, 0.06, rad))
    col = mix(col, lin("#3b1712"), w["mouth"])
    col = mix(col, tooth, w["tooth"])
    col = mix(col, claw, w["claw"])
    col = mix(col, lin("#140c08"), w["eye"])
    em = lin("#bd4b1d")[None, :] * (crease * 0.08 * w["skin"])[:, None]
    eyeglow = np.zeros(ctx.n, np.float32)
    for s in (-1, 1):
        c = np.array([2.905, 1.995, 0.245 * s], np.float32)
        ax = np.array([0.55, 0.05, 0.83 * s], np.float32)
        ax /= np.linalg.norm(ax)
        rel = P - c
        cosang = np.sum(rel * ax, 1) / np.maximum(np.linalg.norm(rel, axis=1), 1e-6)
        near = (np.linalg.norm(rel, axis=1) < 0.07).astype(np.float32) * w["eye"]
        iris = sstep(0.62, 0.72, cosang) * near
        slit = (sstep(0.88, 0.95, cosang) * near * sstep(0.5, 0.2, np.abs(rel[:, 0]) / 0.06))
        col = mix(col, lin("#f08a1e"), iris)
        col = mix(col, lin("#050302"), slit)
        em += lin("#f0a12d")[None, :] * (iris * (1 - slit) * 0.9)[:, None]
        eyeglow = np.maximum(eyeglow, iris)
    rough = w["skin"] * (0.72 + 0.12 * cid) + w["mouth"] * 0.45 + w["tooth"] * 0.40 + w["claw"] * 0.50 + w["eye"] * 0.1
    chest = sstep(1.1, 1.8, y) * sstep(0.9, 1.6, P[:, 0]) * sstep(0.0, -0.6, N[:, 1] - 0.3)
    tailg = sstep(-1.9, -2.5, P[:, 0])
    variant = np.stack([np.zeros(ctx.n, np.float32), np.clip((chest + tailg * 0.8) * crease * 3.0, 0, 1),
                        np.zeros(ctx.n, np.float32), np.ones(ctx.n, np.float32)], 1)

    def height(Q):
        hs, _e, _c = scales(Q)
        return hs * w["skin"] + noise.ridged(Q * 60.0, 2, seed=8) * 0.0005 * (w["tooth"] + w["claw"])
    return {"albedo": np.clip(col, 0, 1), "roughness": np.clip(rough, 0, 1), "emissive": em, "height": height,
            "height_eps": 0.003, "cavity": 1.0 - 0.3 * edge * w["skin"], "variant": variant}


def shade_stone(ctx):
    P, N = ctx.P, ctx.N
    rad = getattr(ctx, "rad", np.full(ctx.n, 0.2, np.float32))
    q = P * 4.2
    f1, f2, cid = noise.worley(q, 23)
    seam = 1 - sstep(0.0, 0.06, f2 - f1)
    deep = seam * sstep(0.62, 0.86, noise.fbm(P * 1.8, 3, seed=24) + 0.5)
    base = mix(lin("#7d6c63"), lin("#62534a"), sstep(0.2, 0.8, cid))
    base = base * (0.9 + 0.2 * noise.fbm(P * 6.0, 3, seed=25))[:, None]
    chip = sstep(0.55, 0.15, np.abs(N[:, 1])) * sstep(0.1, 0.5, noise.fbm(P * 8, 2, seed=26) + 0.5)
    spike_tip = sstep(0.12, 0.05, rad)
    base = mix(base, lin("#b09a8e"), np.clip(chip * 0.55 + spike_tip * 0.4, 0, 1))
    base = mix(base, lin("#1a1512"), seam * 0.85)
    em = lin("#f0a12d")[None, :] * deep[:, None] * 0.9
    rough = 0.88 - 0.10 * chip + 0.06 * cid
    shoulders = sstep(0.0, 0.6, np.abs(P[:, 2]) - 0.7) * sstep(0.7, 1.1, P[:, 0])
    variant = np.stack([np.clip(shoulders, 0, 1) * (1 - seam), np.clip(deep * 0.8 + seam * 0.25, 0, 1),
                        np.clip(chip * 0.7 + spike_tip, 0, 1) * (1 - seam), np.ones(ctx.n, np.float32)], 1)

    def height(Q):
        a1, a2, ci = noise.worley(Q * 4.2, 23)
        s2 = 1 - sstep(0.0, 0.06, a2 - a1)
        return (ci - 0.5) * 0.006 + (a1 - 0.5) * 0.004 - s2 * 0.006 + noise.perlin(Q * 30, 27) * 0.0008
    return {"albedo": np.clip(base, 0, 1), "roughness": np.clip(rough, 0, 1), "emissive": em, "height": height,
            "height_eps": 0.004, "cavity": 1.0 - 0.4 * seam, "variant": variant}


# ---------------------------------------------------------------- animation
POSTURE = {}
BREATH_PERIOD_F = 60
BREATH_AMP = 1.6
CLIP_NAMES = ["idle", "walk", "run", "turn_left", "turn_right", "roar", "attack_claw", "attack_bite", "attack_tail",
              "attack_slam", "stagger", "hit", "death", "alert"]
SEMANTIC = {"Idle": "idle", "Walk": "walk", "Run": "run", "Alert": "alert", "Attack": "attack_claw", "Hit": "hit",
            "Death": "death", "Roar": "roar"}
SERVER_EVENTS = {"creature_attack": "attack_claw", "shockwave": "attack_slam"}


def clips(rig, sampler):
    import clips as C
    from anim import plan_feet
    from qmath import ease
    g = globals()
    pre = ID + "__"
    out = []
    walk_off = {("Hind", "L"): 0.0, ("Front", "L"): 0.25, ("Hind", "R"): 0.5, ("Front", "R"): 0.75}

    out.append(C.standing(rig, g, pre + "idle", 120, {
        "taily": [(0, 0.0), (30, 0.06), (60, -0.06), (90, 0.05), (120, 0.0)],
        "tailp": [(0, 0.0), (60, 0.03), (120, 0.0)],
        "hy": [(0, 0.0), (40, 0.05), (80, -0.04), (120, 0.0)],
        "jaw": [(0, 0.0), (50, 0.0), (56, 0.06), (66, 0.0), (120, 0.0)]}, loop=True,
        legs_fn=C.leg_keys(rig, IDLE_STANCE, 120)))

    def walk_body(ph):
        w = 2 * np.pi * ph
        return {"py": -0.035 * np.cos(2 * w), "pr": 0.035 * np.sin(w), "pyw": 0.04 * np.sin(w), "cr": -0.03 *
                np.sin(w), "s1y": -0.03 * np.sin(w), "n1p": 0.02 * np.sin(2 * w + 0.5),
                "n1y": -0.03 * np.sin(w), "gF": 0.06 * np.sin(w), "taily": 0.14 * np.sin(w + 1.4)}
    out.append(C.locomotion(rig, g, pre + "walk", 54, 1.3, 0.70, walk_off, 0.22, walk_body))

    def run_body(ph):
        w = 2 * np.pi * ph
        return {"py": -0.06 * np.cos(2 * w) - 0.03, "pr": 0.05 * np.sin(w), "pyw": 0.05 * np.sin(w), "pp": -0.04,
                "n1p": -0.05 + 0.03 * np.sin(2 * w), "gF": 0.10 * np.sin(w), "taily": 0.20 * np.sin(w + 1.2),
                "tailp": 0.05}
    out.append(C.locomotion(rig, g, pre + "run", 36, 3.2, 0.52, walk_off, 0.30, run_body))

    for name, sgn in (("turn_left", 1.0), ("turn_right", -1.0)):
        N = 42
        yaw = lambda fr, s=sgn: s * np.radians(45.0) * ease(fr / 36.0)  # noqa: E731
        a, b = ("L", "R") if sgn > 0 else ("R", "L")
        sw = {("Front", a): [(2, 12)], ("Front", b): [(9, 19)], ("Hind", a): [(17, 27)], ("Hind", b): [(24, 34)]}
        sw[("Front", a)].append((30, 40))
        legs = plan_feet(rig, N, lambda fr: (0.0, 0.0, yaw(fr)), sw, lift=0.20)
        out.append(C.standing(rig, g, pre + name, N, {
            "n1y": [(0, 0.0), (10, 0.18 * sgn), (30, 0.06 * sgn), (42, 0.0)],
            "hy": [(0, 0.0), (10, 0.10 * sgn), (42, 0.0)],
            "cy": [(0, 0.0), (14, 0.08 * sgn), (38, 0.0)],
            "pr": [(0, 0.0), (10, -0.03 * sgn), (26, 0.03 * sgn), (42, 0.0)],
            "taily": [(0, 0.0), (18, -0.30 * sgn), (32, -0.15 * sgn), (42, 0.0)]},
            legs_fn=legs, stiff=25.0, damp=6.0,
            motion={"yaw_deg": 45.0 * sgn, "yaw": [float(yaw(f)) for f in range(N + 1)]}))

    out.append(C.standing(rig, g, pre + "roar", 90, {
        "n1p": [(0, 0.0), (14, -0.10), (24, 0.24), (60, 0.26), (74, 0.05), (90, 0.0)],
        "hp": [(0, 0.0), (14, -0.06), (24, 0.14), (60, 0.16), (90, 0.0)],
        "jaw": [(0, 0.0), (18, 0.04), (25, 0.55), (58, 0.52), (68, 0.08), (74, 0.0)],
        "px": [(0, 0.0), (14, -0.12), (25, 0.14), (60, 0.12), (90, 0.0)],
        "py": [(0, 0.0), (14, -0.06), (25, 0.05), (60, 0.04), (90, 0.0)],
        "cp": [(0, 0.0), (14, 0.04), (25, -0.06), (60, -0.05), (90, 0.0)],
        "belly": [(0, 0.0), (14, 0.05), (25, -0.03), (60, -0.03), (90, 0.0)],
        "tailp": [(0, 0.0), (24, 0.12), (60, 0.10), (90, 0.0)], "taily": [(0, 0.0), (30, 0.10), (60, -0.1), (90, 0)]},
        events=[{"event": "sound", "frame": 24, "time": 24 / 30}, {"event": "seams_flare", "frame": 26}],
        stiff=25.0, damp=6.0))

    claw = C.leg_keys(rig, {("Front", "R"): {
        "dx": [(0, 0.0), (20, -0.15), (27, -0.10), (31, 0.55), (36, 0.50), (48, 0.15), (60, 0.0, "hold")],
        "dy": [(0, 0.0), (14, 0.45), (24, 0.75), (29, 0.40), (31, 0.06), (36, 0.0), (60, 0.0)],
        "dz": [(0, 0.0), (20, 0.25), (31, -0.30), (36, -0.32), (52, 0.0), (60, 0.0)],
        "toe": [(0, 0.0), (20, -0.8), (29, 0.3), (32, 0.1), (44, 0.0)],
        "foot": [(0, 0.0), (20, -0.9), (29, -0.1), (34, 0.0)]}}, 60)
    out.append(C.standing(rig, g, pre + "attack_claw", 60, {
        "px": [(0, 0.0), (20, -0.14), (27, -0.12), (31, 0.18), (40, 0.10), (60, 0.0)],
        "pr": [(0, 0.0), (20, -0.08), (31, 0.06), (60, 0.0)],
        "pyw": [(0, 0.0), (20, -0.10), (31, 0.12), (60, 0.0)],
        "cy": [(0, 0.0), (20, -0.08), (31, 0.10), (60, 0.0)],
        "n1y": [(0, 0.0), (20, -0.12), (31, 0.15), (60, 0.0)],
        "jaw": [(0, 0.0), (22, 0.20), (32, 0.25), (44, 0.0)],
        "taily": [(0, 0.0), (22, 0.35), (34, -0.30), (60, 0.0)]},
        legs_fn=claw, stiff=25.0, damp=6.0,
        events=[{"event": "windup", "frame": 0}, {"event": "whoosh", "frame": 28}, {"event": "contact", "frame": 31},
                {"event": "recovery", "frame": 36}],
        windows={"windup": [0, 27], "active": [27, 36], "recovery": [36, 60], "impact": 31}))

    out.append(C.standing(rig, g, pre + "attack_bite", 54, {
        "px": [(0, 0.0), (18, -0.16), (24, -0.12), (27, 0.26), (34, 0.20), (54, 0.0)],
        "py": [(0, 0.0), (18, -0.08), (27, -0.04), (54, 0.0)],
        "n1p": [(0, 0.0), (18, 0.10), (24, 0.08), (27, -0.16), (34, -0.10), (54, 0.0)],
        "hp": [(0, 0.0), (18, 0.10), (27, -0.06), (54, 0.0)],
        "jaw": [(0, 0.0), (14, 0.10), (22, 0.62), (26, 0.50), (28, 0.02), (34, 0.0)],
        "gF": [(0, 0.0), (18, 0.06), (27, -0.08), (54, 0.0)],
        "tailp": [(0, 0.0), (20, 0.15), (54, 0.0)]},
        stiff=25.0, damp=6.0,
        events=[{"event": "windup", "frame": 0}, {"event": "whoosh", "frame": 25}, {"event": "contact", "frame": 27},
                {"event": "recovery", "frame": 31}],
        windows={"windup": [0, 24], "active": [24, 31], "recovery": [31, 54], "impact": 27}))

    out.append(C.standing(rig, g, pre + "attack_tail", 75, {
        "pyw": [(0, 0.0), (24, 0.20), (33, 0.22), (40, -0.30), (48, -0.38), (62, -0.08), (75, 0.0)],
        "s1y": [(0, 0.0), (24, 0.12), (40, -0.18), (48, -0.22), (75, 0.0)],
        "s2y": [(0, 0.0), (24, 0.08), (40, -0.10), (75, 0.0)],
        "pr": [(0, 0.0), (24, -0.05), (40, 0.06), (75, 0.0)],
        "n1y": [(0, 0.0), (24, -0.25), (40, 0.20), (60, 0.05), (75, 0.0)],
        "taily": [(0, 0.0), (24, -0.70), (33, -0.80), (40, 0.90), (46, 1.05), (58, 0.30), (75, 0.0)],
        "tailp": [(0, 0.0), (24, 0.20), (40, 0.30), (52, 0.10), (75, 0.0)],
        "py": [(0, 0.0), (24, -0.05), (40, -0.08), (75, 0.0)]},
        stiff=18.0, damp=4.0, tail_amp=1.0,
        events=[{"event": "windup", "frame": 0}, {"event": "whoosh", "frame": 36}, {"event": "contact", "frame": 40},
                {"event": "recovery", "frame": 48}],
        windows={"windup": [0, 33], "active": [33, 48], "recovery": [48, 75], "impact": 40}))

    # slam: rear up on the hind legs and tail, slam both front feet at 43 (one impact), long recovery
    slam_legs = C.leg_keys(rig, {k: {
        "dy": [(0, 0.0), (12, 0.10), (32, 1.35), (38, 1.25), (43, 0.0, "hold"), (90, 0.0)],
        "dx": [(0, 0.0), (32, -0.05), (43, 0.25, "hold"), (70, 0.25), (86, 0.0), (90, 0.0)],
        "dz": [(0, 0.0), (32, 0.28 * (1 if k[1] == "R" else -1)), (43, 0.12 * (1 if k[1] == "R" else -1), "hold"),
               (70, 0.12 * (1 if k[1] == "R" else -1)), (86, 0.0), (90, 0.0)],
        "toe": [(0, 0.0), (30, -0.9), (40, -0.3), (43, 0.0), (90, 0.0)],
        "foot": [(0, 0.0), (30, -1.1), (40, -0.3), (43, 0.0), (90, 0.0)]} for k in (("Front", "L"), ("Front", "R"))}, 90)
    out.append(C.standing(rig, g, pre + "attack_slam", 90, {
        "pp": [(0, 0.0), (14, -0.04), (32, 0.62), (38, 0.58), (43, -0.10), (52, -0.06), (90, 0.0)],
        "py": [(0, 0.0), (14, -0.10), (32, 0.22), (38, 0.20), (43, -0.22), (55, -0.16), (90, 0.0)],
        "px": [(0, 0.0), (14, -0.18), (32, -0.35), (43, 0.10), (60, 0.05), (90, 0.0)],
        "n1p": [(0, 0.0), (32, -0.10), (43, -0.22), (60, -0.10), (72, 0.12), (90, 0.0)],
        "hp": [(0, 0.0), (32, -0.12), (43, -0.10), (72, 0.10), (90, 0.0)],
        "jaw": [(0, 0.0), (30, 0.40), (43, 0.30), (54, 0.05), (64, 0.0), (72, 0.30), (84, 0.0)],
        "tailp": [(0, 0.0), (20, -0.20), (32, -0.30), (43, 0.15), (60, 0.0)],
        "belly": [(0, 0.0), (43, -0.04), (60, 0.0)]},
        legs_fn=slam_legs, stiff=25.0, damp=6.0,
        events=[{"event": "windup", "frame": 0}, {"event": "contact", "frame": 43}, {"event": "shockwave", "frame": 43},
                {"event": "dust", "frame": 43}, {"event": "recovery", "frame": 47}],
        windows={"windup": [0, 42], "active": [42, 47], "recovery": [47, 90], "impact": 43}))

    stagger_legs = C.leg_keys(rig, {("Front", "L"): {
        "dz": [(0, 0.0), (12, 0.0), (22, -0.35, "hold"), (36, -0.35), (45, 0.0)],
        "dy": [(0, 0.0), (12, 0.0), (17, 0.25), (22, 0.0, "hold"), (36, 0.0), (40, 0.18), (45, 0.0)],
        "toe": [(0, 0.0), (17, -0.8), (22, 0.0), (40, -0.6), (45, 0.0)]}}, 45)
    out.append(C.standing(rig, g, pre + "stagger", 45, {
        "pr": [(0, 0.0), (10, -0.10), (20, -0.14), (30, 0.04), (45, 0.0)],
        "pz": [(0, 0.0), (10, -0.15), (20, -0.20), (32, 0.02), (45, 0.0)],
        "pyw": [(0, 0.0), (14, 0.10), (30, -0.04), (45, 0.0)],
        "n1y": [(0, 0.0), (10, 0.20), (24, -0.10), (45, 0.0)],
        "n1p": [(0, 0.0), (10, -0.12), (28, 0.02), (45, 0.0)],
        "jaw": [(0, 0.0), (8, 0.3), (24, 0.05), (45, 0.0)],
        "taily": [(0, 0.0), (12, 0.45), (28, -0.25), (45, 0.0)]},
        legs_fn=stagger_legs, stiff=25.0, damp=5.0, events=[{"event": "stagger", "frame": 0},
                                                            {"event": "footstep", "frame": 22}]))

    out.append(C.standing(rig, g, pre + "hit", 24, {
        "px": [(0, 0.0), (5, -0.08), (14, -0.02), (24, 0.0)],
        "pr": [(0, 0.0), (5, 0.03), (16, -0.01), (24, 0.0)],
        "n1p": [(0, 0.0), (5, 0.06), (14, 0.0), (24, 0.0)],
        "hy": [(0, 0.0), (5, -0.06), (24, 0.0)],
        "jaw": [(0, 0.0), (5, 0.12), (14, 0.0)]}, idle_overlay=False, stiff=25.0, damp=6.0,
        events=[{"event": "hit", "frame": 3}]))

    out.append(C.death(rig, g, sampler, pre + "death", 120, {
        "pp": [(0, 0.0), (20, -0.10), (40, -0.06), (120, 0.0)],
        "pr": [(0, 0.0), (30, 0.05), (46, 0.30), (64, 0.80), (78, 0.95), (90, 1.0), (120, 1.0, "hold")],
        "py": [(0, 0.0), (20, -0.40), (40, -0.80), (64, -1.05), (120, -1.10, "hold")],
        "n1p": [(0, 0.0), (20, -0.15), (50, -0.25), (80, -0.35), (120, -0.35, "hold")],
        "n1r": [(0, 0.0), (64, -0.25), (120, -0.30)],
        "hp": [(0, 0.0), (30, -0.15), (90, -0.10)],
        "jaw": [(0, 0.0), (16, 0.30), (40, 0.15), (120, 0.12)],
        "tailp": [(0, 0.0), (40, -0.25), (120, -0.35)], "taily": [(0, 0.0), (60, 0.2), (120, 0.25)],
        "belly": [(0, 0.0), (96, 0.03), (108, -0.01), (120, 0.0)]},
        {"UpperLeg_Front": 0.30, "LowerLeg_Front": -0.45, "Foot_Front": -0.45, "Toe_Front": -0.3,
         "UpperLeg_Hind": -0.25, "LowerLeg_Hind": 0.45, "Foot_Hind": -0.3, "Toe_Hind": -0.2},
        buckle_end=30, fk_start=28, fk_end=52, lie_frame=64, search_bone="Neck_02", search_range=(0.0, -0.5),
        events=[{"event": "collapse", "frame": 16}, {"event": "ground_contact", "frame": 64},
                {"event": "dust", "frame": 64}, {"event": "seams_fade", "frame": 70}, {"event": "dead", "frame": 120}]))

    out.append(C.standing(rig, g, pre + "alert", 42, {
        "n1p": [(0, 0.0), (14, 0.16), (42, 0.14, "hold")],
        "hp": [(0, 0.0), (14, -0.04), (42, -0.03, "hold")],
        "px": [(0, 0.0), (16, -0.06), (42, -0.05, "hold")],
        "py": [(0, 0.0), (16, 0.04), (42, 0.035, "hold")],
        "gF": [(0, 0.0), (16, -0.06), (42, -0.05, "hold")],
        "jaw": [(0, 0.0), (16, 0.08), (42, 0.06, "hold")],
        "tailp": [(0, 0.0), (16, 0.12), (42, 0.10, "hold")]}, idle_overlay=False, stiff=25.0, damp=6.0))
    return out
