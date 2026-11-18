"""Горный Драгор (dragor; art name «Dragar / Mountain Colossus»): sculpted to creature-references/dragar/model.png
(side / front / rear / top read at 121.6 px per metre: the highest point - the dorsal scutes over the shoulders -
at 3.1 m, as the shoulders of the kit sheet next to its 1.8 m man). A long, low, sprawling armoured reptile 9.4 m
from the snout to the tail tip: crocodile-dragon head held low with a toothy, slightly open jaw and a scute crest,
short thick neck, broad barrel, massive splayed legs (feet 1.3-1.4 m off the midline) on five big horn claws, a
long thick tail tapering to a point near the ground. Head, neck, back and tail are shingled with leaf-shaped
basalt scutes - pointed rear tips lifted, a keel along each, bronze rims - in overlapping rows down to mid-flank;
legs and belly are charcoal skin of rounded cobble scales.
"""
import numpy as np

from sdf import Prim, Part, chain, bezier, rot_x, rot_y, rot_z
from rig import Skeleton
from common import SIDES, leg_bones, surface_points, plate_frame

ID = "dragor"
NAME = "Горный Драгор"
VOXEL_BODY = 0.022
VOXEL_RIGID = 0.009
BAKE_EXTRUSION = 0.035
BAKE_RAY = 0.09
AO_SAMPLES = 40
AO_DISTANCE = 0.9

# joints: girdle, upper (shoulder / hip joint), lower (elbow / knee), foot (wrist / ankle), toe, tip (claw front)
# sprawling reptile stance: the elbows and knees stand out from the body, the feet 1.3-1.4 m off the midline
FRONT = {"joints": [(0.95, 2.00, 0.55), (1.35, 1.62, 0.96), (1.26, 1.00, 1.28), (1.62, 0.42, 1.07),
                    (1.84, 0.15, 1.06), (2.30, 0.0, 1.06)]}   # elbow back and out: the forelegs bend at rest
HIND = {"joints": [(-2.00, 1.65, 0.50), (-2.05, 1.38, 0.86), (-1.62, 0.88, 1.16), (-2.04, 0.42, 1.12),
                   (-1.90, 0.14, 1.11), (-1.50, 0.0, 1.11)]}
# tail centre line (sheet side view: thick at the croup, tapering to a point a little above the ground at 6 m)
TAIL = [(-2.45, 1.45, 0), (-3.05, 1.18, 0), (-3.65, 0.95, 0), (-4.25, 0.76, 0), (-4.85, 0.60, 0), (-5.45, 0.47, 0),
        (-6.02, 0.38, 0)]
TAIL_R = [0.62, 0.47, 0.35, 0.26, 0.19, 0.12, 0.035]
SPINE_Y = [(-2.45, 1.60), (-1.1, 1.88), (0.2, 2.12), (1.2, 2.08), (2.0, 1.98), (2.6, 2.00)]  # body axis (scute fan)

# idle stance read off the side view (claw contacts): near (left) fore forward, far fore back, far hind forward,
# near hind back - the views are compared in this pose
IDLE_STANCE = {("Front", "L"): {"dx": [(0, 0.0)]}, ("Front", "R"): {"dx": [(0, -0.60)]},
               ("Hind", "L"): {"dx": [(0, -0.25)]}, ("Hind", "R"): {"dx": [(0, 0.70)]}}


def tail_y(x):
    xs = np.array([p[0] for p in TAIL])[::-1]
    ys = np.array([p[1] for p in TAIL])[::-1]
    return float(np.interp(x, xs, ys))


def tail_r(x):
    xs = np.array([p[0] for p in TAIL])[::-1]
    return float(np.interp(x, xs, np.array(TAIL_R)[::-1]))


def axis_y(x):
    """Height of the body / tail axis at x (the centre the scute rows fan around)."""
    if x < TAIL[0][0]:
        return tail_y(x)
    xs, ys = zip(*SPINE_Y)
    return float(np.interp(x, xs, ys))


def tail_bone(x):
    for i in range(len(TAIL) - 1):
        if x >= TAIL[i + 1][0]:
            return f"Tail_0{i + 1}"
    return f"Tail_0{len(TAIL) - 1}"


def side(p, s):
    return np.array([p[0], p[1], abs(p[2]) * s])


def skeleton():
    sk = Skeleton()
    sk.add("MotionRoot", None, (0, 0, 0))
    sk.add("Pelvis", "MotionRoot", (-2.00, 1.65, 0))
    sk.add("Spine_01", "Pelvis", (-1.05, 1.90, 0))
    sk.add("Spine_02", "Spine_01", (-0.05, 2.12, 0))
    sk.add("Chest", "Spine_02", (0.95, 2.08, 0))
    sk.add("Neck_01", "Chest", (1.65, 2.04, 0))
    sk.add("Neck_02", "Neck_01", (1.95, 2.02, 0))
    sk.add("Head", "Neck_02", (2.21, 2.04, 0), tail=(3.09, 1.92, 0))
    sk.add("Jaw", "Head", (2.25, 1.74, 0), tail=(3.05, 1.55, 0))
    sk.add("Tongue", "Jaw", (2.43, 1.70, 0), tail=(2.85, 1.64, 0))
    sk.add("Throat", "Neck_02", (1.95, 1.58, 0), tail=(2.25, 1.52, 0))
    for nm, s in SIDES:
        sk.add(f"Cheek_{nm}", "Head", (2.33, 1.88, 0.36 * s), tail=(2.63, 1.82, 0.32 * s))
    sk.add("Belly", "Spine_02", (-0.40, 1.35, 0), tail=(-0.40, 1.20, 0))
    for nm, s in SIDES:
        leg_bones(sk, "Front", "Chest", None, [side(j, s) for j in FRONT["joints"]], nm)
        leg_bones(sk, "Hind", "Pelvis", None, [side(j, s) for j in HIND["joints"]], nm)
        for kind, J in (("Front", FRONT), ("Hind", HIND)):
            toe = side(J["joints"][4], s)
            sk.add(f"Digit_In_{kind}_{nm}", f"Toe_{kind}_{nm}", toe + np.array([0.05, 0, -0.20 * s]),
                   tail=side(J["joints"][5], s) + np.array([-0.06, 0, -0.26 * s]))
            sk.add(f"Digit_Out_{kind}_{nm}", f"Toe_{kind}_{nm}", toe + np.array([0.05, 0, 0.20 * s]),
                   tail=side(J["joints"][5], s) + np.array([-0.06, 0, 0.26 * s]))
    for i in range(6):
        sk.add(f"Tail_0{i + 1}", "Pelvis" if i == 0 else f"Tail_0{i}", TAIL[i], tail=TAIL[6] if i == 5 else None)
    sk.socket("socket_head", "Head", (2.36, 2.50, 0))
    sk.socket("socket_mouth", "Jaw", (2.95, 1.66, 0))
    sk.socket("socket_chest", "Chest", (1.90, 1.40, 0))
    sk.socket("socket_slam_center", "Chest", (2.30, 0.0, 0))
    for nm, s in SIDES:
        sk.socket(f"socket_foot_front_{nm.lower()}", f"Toe_Front_{nm}", side(FRONT["joints"][5], s))
        sk.socket(f"socket_foot_hind_{nm.lower()}", f"Toe_Hind_{nm}", side(HIND["joints"][5], s))
        sk.socket(f"socket_claw_{nm.lower()}", f"Toe_Front_{nm}", side((2.45, 0.03, 1.38), s))
    sk.socket("socket_tail_tip", "Tail_06", TAIL[6])
    return sk


TOE_SPREAD = [-0.29, -0.145, 0.0, 0.145, 0.29]


def toes(kind, nm, s, j):
    """Five thick toes fanning forward and out; outer two on the Digit_In/Out bones."""
    T = f"Toe_{kind}_{nm}"
    out = []
    for i, dz in enumerate(TOE_SPREAD):
        bone = f"Digit_In_{kind}_{nm}" if i == 0 else (f"Digit_Out_{kind}_{nm}" if i == 4 else T)
        base = j[4] + np.array([0.02, -0.02, dz * s * 0.55])
        tip = j[5] + np.array([-0.10 - 0.10 * abs(dz) / 0.29, 0.09, dz * s])
        r0 = 0.15 if kind == "Front" else 0.13
        out.append(Prim("cone", bone, k=0.05, name=f"toe{i}", a=base, b=tip, ra=r0, rb=r0 * 0.78))
    return out


def leg_prims(kind, nm, s, J):
    j = [side(p, s) for p in J]
    U, L, Fo, T = f"UpperLeg_{kind}_{nm}", f"LowerLeg_{kind}_{nm}", f"Foot_{kind}_{nm}", f"Toe_{kind}_{nm}"
    out = []
    if kind == "Front":
        out += [Prim("cone", U, k=0.18, a=j[1], b=j[2], ra=0.62, rb=0.50, name="humerus"),
                Prim("ellipsoid", U, k=0.16, c=j[1] * 0.45 + j[2] * 0.55 + np.array([-0.05, 0.02, 0.05 * s]),
                     r=(0.52, 0.56, 0.44), name="biceps"),
                Prim("sphere", L, k=0.12, c=j[2] + np.array([-0.14, 0.02, 0.04 * s]), r=0.48, name="elbow"),
                Prim("cone", L, k=0.12, a=j[2], b=j[3], ra=0.52, rb=0.42, name="forearm"),
                Prim("ellipsoid", L, k=0.12, c=j[2] * 0.6 + j[3] * 0.4 + np.array([0.08, 0, 0.03 * s]),
                     r=(0.42, 0.50, 0.42), name="forearm_m")]
    else:
        out += [Prim("cone", U, k=0.20, a=j[1], b=j[2], ra=0.66, rb=0.50, name="femur"),
                Prim("ellipsoid", U, k=0.18, c=j[1] * 0.5 + j[2] * 0.5 + np.array([-0.10, 0.04, 0.03 * s]),
                     r=(0.68, 0.70, 0.46), name="thigh_m"),
                Prim("cone", L, k=0.12, a=j[2], b=j[3], ra=0.46, rb=0.36, name="shin"),
                Prim("ellipsoid", L, k=0.10, c=j[2] * 0.55 + j[3] * 0.45 + np.array([-0.08, 0.02, 0]),
                     r=(0.40, 0.46, 0.36), name="calf")]
    out += [Prim("sphere", Fo, k=0.10, c=j[3], r=0.40 if kind == "Front" else 0.35, name="wrist"),
            Prim("cone", Fo, k=0.08, a=j[3], b=j[4], ra=0.38 if kind == "Front" else 0.34, rb=0.36, name="hand"),
            Prim("ellipsoid", T, k=0.08, c=j[4] + np.array([0.10, -0.05, 0]), r=(0.40, 0.16, 0.42), name="sole_pad")]
    out += toes(kind, nm, s, j)
    out.append(Prim("box", T, k=0.004, neg=True, name="sole", c=np.array([j[5][0] - 0.2, -0.15, j[5][2]]),
                    h=(0.8, 0.15, 0.7), round=0.0))
    return out


def body_core():
    # long broad barrel, the belly ~1.0 m above the ground, the back rising to the shoulders
    P = [Prim("ellipsoid", "Chest", k=0.0, c=(0.50, 1.90, 0), r=(1.50, 0.80, 0.86), name="ribcage"),
         Prim("ellipsoid", "Chest", k=0.24, c=(1.40, 1.46, 0), r=(0.70, 0.62, 0.82), name="breast"),
         Prim("ellipsoid", "Belly", k=0.26, c=(-0.50, 1.38, 0), r=(1.35, 0.60, 0.84), name="belly"),
         Prim("ellipsoid", "Spine_01", k=0.26, c=(-1.15, 1.82, 0), r=(1.05, 0.56, 0.80), name="loin"),
         Prim("ellipsoid", "Pelvis", k=0.24, c=(-2.05, 1.58, 0), r=(0.88, 0.55, 0.74), name="hips"),
         Prim("cone", "Neck_01", k=0.22, a=(1.62, 1.97, 0), b=(2.02, 1.98, 0), ra=0.72, rb=0.48, name="neck"),
         Prim("ellipsoid", "Throat", k=0.18, c=(1.95, 1.66, 0), r=(0.45, 0.26, 0.48), name="dewlap"),
         # crocodile-dragon head held low: broad skull, long tapering upper jaw, heavy lower jaw, mouth a little open
         Prim("ellipsoid", "Head", k=0.14, c=(2.31, 2.10, 0), r=(0.46, 0.28, 0.44), name="skull"),
         Prim("ellipsoid", "Head", k=0.12, c=(2.77, 1.93, 0), r=(0.48, 0.15, 0.24), name="snout"),
         Prim("ellipsoid", "Head", k=0.06, c=(3.17, 1.86, 0), r=(0.08, 0.09, 0.13), name="nosetip"),
         Prim("ellipsoid", "Jaw", k=0.08, c=(2.65, 1.65, 0), r=(0.50, 0.13, 0.22), R=rot_z(-0.12), name="jaw"),
         Prim("box", "Head", k=0.012, neg=True, mat="mouth", c=(2.75, 1.745, 0), h=(0.46, 0.045, 0.26),
              round=0.02, R=rot_z(-0.12), name="mouthgap")]
    for nm, s in SIDES:
        P += [Prim("ellipsoid", f"Cheek_{nm}", k=0.10, c=(2.30, 1.80, 0.32 * s), r=(0.30, 0.20, 0.16),
                   name=f"cheek{nm}"),
              Prim("ellipsoid", "Head", k=0.07, c=(2.55, 2.24, 0.26 * s), r=(0.28, 0.09, 0.14), R=rot_z(-0.18),
                   name=f"brow{nm}"),
              Prim("sphere", "Head", k=0.015, neg=True, c=(2.57, 2.16, 0.315 * s), r=0.06, name=f"socket{nm}"),
              Prim("cone", "Head", k=0.03, a=(3.07, 1.91, 0.08 * s), b=(3.19, 1.89, 0.06 * s), ra=0.033, rb=0.02,
                   neg=True, name=f"nostril{nm}"),
              Prim("ellipsoid", f"Shoulder_{nm}", k=0.22, c=side((1.15, 1.80, 0.84), s), r=(0.70, 0.52, 0.40),
                   R=rot_z(-0.30), name=f"scapula{nm}"),
              Prim("ellipsoid", f"UpperLeg_Hind_{nm}", k=0.22, c=side((-2.00, 1.40, 0.80), s), r=(0.80, 0.70, 0.42),
                   R=rot_z(0.20), name=f"haunch{nm}")]
        P += leg_prims("Front", nm, s, FRONT["joints"])
        P += leg_prims("Hind", nm, s, HIND["joints"])
    P += chain(TAIL, TAIL_R, None, k=0.14, name="tail", bones=[f"Tail_0{i + 1}" for i in range(6)])
    return P


def scute(centre, n, back, L, W, T, bone, tilt, yaw, name, mat="stone"):
    """A leaf-shaped basalt scute lying on the surface: a slab carved to a long pointed rear tip and a blunt
    six-sided front, a keel along the middle; its rear tip lifts off the body by `tilt` (rigid to one bone)."""
    Rf = plate_frame(n, back)
    R = Rf @ rot_y(yaw) @ rot_z(tilt)
    c = np.asarray(centre, float)
    xa, ya, za = R[:, 0], R[:, 1], R[:, 2]
    out = [Prim("box", bone, grp=name, k=0.0, mat=mat, name=name + "a", c=c, h=(L * 0.5, T, W * 0.5), round=min(0.016, T * 0.4),
                R=R)]
    for sgn in (-1, 1):
        cc = c + xa * L * 0.5 + za * sgn * W * 0.5
        out.append(Prim("box", bone, grp=name, k=0.004, neg=True, name=name + f"cut{sgn}", c=cc,
                        h=(L * 0.66, T * 4, W * 0.37), round=0.0, R=R @ rot_y(sgn * 0.60)))
        cf = c - xa * L * 0.5 + za * sgn * W * 0.5
        out.append(Prim("box", bone, grp=name, k=0.004, neg=True, name=name + f"nick{sgn}", c=cf,
                        h=(L * 0.20, T * 4, W * 0.22), round=0.0, R=R @ rot_y(-sgn * 0.75)))
    out.append(Prim("box", bone, grp=name, k=0.016, mat=mat, name=name + "keel", c=c + ya * T * 0.95 + xa * L * 0.06,
                    h=(L * 0.42, T * 0.8, T * 0.8), round=0.006, R=R @ rot_x(np.pi / 4)))
    return out


def body_bone(x, a):
    """Bone that carries a dorsal scute at x, `a` radians round the body from the spine."""
    if x > 1.98:
        return "Head"
    if x > 1.75:
        return "Neck_01" if x < 1.82 else "Neck_02"
    if abs(a) > 0.95 and 0.55 < x < 1.75:
        return "Shoulder_R" if a > 0 else "Shoulder_L"
    if x > 0.45:
        return "Chest"
    if x > -0.55:
        return "Spine_02"
    if x > -1.55:
        return "Spine_01"
    if x > TAIL[0][0]:
        return "Pelvis"
    return tail_bone(x)


def build_armor(core, rng):
    """Rows of leaf scutes (quincunx) from the nape over the back and down the tail, each row fanning round the
    body axis from the spine to mid-flank (top scutes tallest and most lifted, side scutes flatter and pointing
    back and down); small scutes in rows over the skull up to a crest. Returns a list of scutes (prim lists)."""
    specs = []
    # (x, count, max angle from the spine, length) along neck, back and croup
    rows = [(1.97, 9, 1.55, 0.52), (1.71, 11, 1.70, 0.66), (1.44, 12, 1.74, 0.74),
            (1.17, 13, 1.76, 0.80), (0.90, 13, 1.78, 0.84), (0.63, 13, 1.80, 0.86), (0.36, 13, 1.80, 0.86),
            (0.09, 13, 1.80, 0.84), (-0.18, 13, 1.78, 0.82), (-0.45, 12, 1.74, 0.80), (-0.72, 12, 1.70, 0.78),
            (-0.99, 11, 1.60, 0.75), (-1.26, 11, 1.50, 0.72), (-1.53, 10, 1.42, 0.69), (-1.80, 10, 1.36, 0.66),
            (-2.07, 9, 1.32, 0.63), (-2.32, 9, 1.30, 0.60)]
    # tail rows: fewer, smaller scutes down to the tip
    for i, tx in enumerate(np.arange(-2.56, -5.95, -0.26)):
        f = i / 13.0
        rows.append((float(tx), 7 if f < 0.5 else 5, 1.50 - 0.35 * f, 0.56 - 0.36 * f))
    for r, (x, n, amax, L) in enumerate(rows):
        off = 0.5 if r % 2 else 0.0
        R0 = 1.8 if x > TAIL[0][0] else tail_r(x) + 1.0
        for i in range(n):
            u = (i + off) / max(1, n - 1 + off) if n > 1 else 0.5
            a = (u * 2 - 1) * amax
            st = np.array([x + rng.normal(0, 0.012), axis_y(x) + R0 * np.cos(a), R0 * np.sin(a)])
            specs.append((st, L * (0.95 + 0.10 * rng.random()), body_bone(x, a), a, x))
    # head: small scutes over the skull and the snout ridge, rising to a crest at the back of the head
    head = [(3.05, 1, 0.0, 0.09), (2.91, 2, 0.40, 0.10), (2.77, 3, 0.60, 0.12), (2.63, 3, 0.70, 0.13),
            (2.49, 4, 0.85, 0.15), (2.35, 4, 0.95, 0.18), (2.21, 5, 1.05, 0.22), (2.07, 5, 1.10, 0.27)]
    for (x, n, amax, L) in head:
        for i in range(n):
            u = (i + 0.5) / n if n > 1 else 0.5
            a = (u * 2 - 1) * amax if n > 1 else 0.0
            st = np.array([x, 2.05 + 1.0 * np.cos(a), 1.0 * np.sin(a)])
            specs.append((st, L, "Head" if x > 1.98 else "Neck_02", a, x + 10.0))   # x + 10: head scute marker
    starts = np.array([sp[0] for sp in specs], np.float32)
    pts, nrm = surface_points(core, starts, steps=18)
    out = []
    for k, ((st, L, bone, a, x), p, n) in enumerate(zip(specs, pts, nrm)):
        n = n / np.linalg.norm(n)
        if x > 9.0:   # head scutes: small, lying flat, only the crest at the back of the skull lifts
            x -= 10.0
            lift = 0.20 + 0.10 * float(x < 2.33)
            out.append(scute(p + n * 0.022, n, np.array([-1.0, -0.1, 0]), L * 1.2, L * 0.7, 0.026, bone,
                             lift, rng.normal(0, 0.04), f"sc{k}"))
            continue
        side_f = min(abs(a) / 1.70, 1.0)
        tail_f = 1.0 if x < TAIL[0][0] else 0.0
        lift = 0.50 - 0.32 * side_f - 0.08 * tail_f + (0.10 if (abs(a) < 0.3 and -1.0 < x < 1.8) else 0.0)
        T = (0.045 if x > TAIL[0][0] else 0.034) * (L / 0.7) ** 0.5
        back = np.array([-1.0, -0.20 - 0.60 * side_f, 0])
        out.append(scute(p + n * 0.035, n, back, L, L * 0.60, T, bone, lift + rng.normal(0, 0.02),
                         rng.normal(0, 0.02), f"sc{k}"))
    return out


def teeth_part():
    """Rows of sharp teeth along the slightly open jaws (upper pointing down, lower up), longest at the front."""
    P = []
    for nm, s in SIDES:
        for i in range(12):
            t = i / 11.0
            a = np.array([3.15 - 0.72 * t, 1.76 + 0.05 * t, (0.10 + 0.17 * t) * s])
            L = 0.15 if i in (1, 2, 5) else (0.12 if i < 7 else 0.09)
            P.append(Prim("cone", "Head", k=0.006, mat="tooth", name=f"tu{nm}{i}", a=a,
                          b=a + np.array([0.02, -L, 0]), ra=0.034, rb=0.005))
        for i in range(10):
            t = i / 9.0
            a2 = np.array([3.05 - 0.60 * t, 1.655 + 0.07 * t, (0.08 + 0.13 * t) * s])
            L = 0.12 if i in (1, 2, 4) else 0.085
            P.append(Prim("cone", "Jaw", k=0.006, mat="tooth", name=f"tl{nm}{i}", a=a2,
                          b=a2 + np.array([0.012, L, 0]), ra=0.030, rb=0.005))
    return P


def claws_part(kind, nm, s):
    j = [side(p, s) for p in (FRONT if kind == "Front" else HIND)["joints"]]
    P = []
    for i, dz in enumerate(TOE_SPREAD):
        bone = f"Digit_In_{kind}_{nm}" if i == 0 else (f"Digit_Out_{kind}_{nm}" if i == 4 else f"Toe_{kind}_{nm}")
        base = j[5] + np.array([-0.12 - 0.10 * abs(dz) / 0.29, 0.16, dz * s])
        L = 0.44 if kind == "Front" else 0.36
        pts = bezier(base, base + np.array([0.10, 0.05, 0]), base + np.array([L * 0.75, 0.01, 0]),
                     base + np.array([L * 0.95, -0.16, 0]), 7)
        P += chain(list(pts), list(np.linspace(0.105, 0.014, len(pts))), bone, k=0.006, mat="claw", name=f"claw{i}")
    return P


def eye_part():
    return Part("eyes", [Prim("sphere", "Head", k=0.0, mat="eye", c=(2.575, 2.16, 0.300 * s), r=0.062, name=f"eye{nm}")
                         for nm, s in SIDES], band=0.02)


CLASSES = {"skin": ["skin", "mouth", "tooth", "claw", "eye"], "stone": ["stone"]}
CLASS_OF = {"base": "skin"}
AXIS_PRIMS = ("humerus", "forearm", "femur", "shin", "hand", "toe", "tail", "neck", "snout", "jaw", "claw", "tu", "tl")
MATERIAL_NAMES = {"skin": "Skin", "stone": "Stone"}
PROOF_COLORS = {"base": "#3b322d", "skin": "#3b322d", "mouth": "#3b1712", "tooth": "#d9cdb3", "claw": "#cdb89a",
                "eye": "#f08a1e", "stone": "#4a423c"}
_CACHE = {}


def build(rng=None):
    rng = rng or np.random.default_rng(13)
    sk = skeleton()
    core = Part("core", body_core(), band=0.12)
    scutes = build_armor(core, rng)
    parts = [{"name": "body", "part": Part("body", body_core(), band=0.12), "material": "skin", "rigid": None,
              "faces": (30000, 10000, 3000)},
             {"name": "eyes", "part": eye_part(), "material": "skin", "rigid": "Head", "faces": (240, 120, 40),
              "voxel": 0.005}]
    tp = teeth_part()
    parts.append({"name": "teeth_upper", "part": Part("teeth_upper", [q for q in tp if q.bone == "Head"], band=0.02),
                  "material": "skin", "rigid": "Head", "faces": (1400, 560, 0), "voxel": 0.004})
    parts.append({"name": "teeth_lower", "part": Part("teeth_lower", [q for q in tp if q.bone == "Jaw"], band=0.02),
                  "material": "skin", "rigid": "Jaw", "faces": (1200, 480, 0), "voxel": 0.004})
    for kind in ("Front", "Hind"):
        for nm, s in SIDES:
            cp = claws_part(kind, nm, s)
            for bone in sorted({q.bone for q in cp}):
                parts.append({"name": f"claws_{bone}", "part": Part(f"claws_{bone}", [q for q in cp if q.bone == bone],
                                                                    band=0.02),
                              "material": "skin", "rigid": bone, "faces": (380, 160, 50), "voxel": 0.006})
    # scutes grouped per bone (up to 4 a part), small faces each: the shingle count, not the facets, is the look
    groups = []
    for sc in scutes:
        if groups and groups[-1][0][0].bone == sc[0].bone and len(groups[-1]) < 4:
            groups[-1].append(sc)
        else:
            groups.append([sc])
    for k, grp in enumerate(groups):
        n = len(grp)
        parts.append({"name": f"scute{k}", "part": Part(f"scute{k}", [q for sc in grp for q in sc], band=0.04),
                      "material": "stone", "rigid": grp[0][0].bone, "faces": (128 * n, 48 * n, 12 * n), "sharp": 40})
    return sk, parts


def build_cached():
    if "b" not in _CACHE:
        _CACHE["b"] = build()
        _warp.apply(WARP, *_CACHE["b"])
        for k, p in enumerate(_CACHE["b"][1]):
            p["index"] = k
    return _CACHE["b"]


# ---------------------------------------------------------------- surface
from shading import lin, mix, sstep, tangent_flow  # noqa: E402
import noise  # noqa: E402

EMISSION_COLOR = "#F0A12D"
LEVELS = {  # R: shoulder/forelimb scutes (darker contrast, II+), G: deep cracks in the scutes and the chest/tail skin
    # creases (glow), B: bronze rims and chips (III). Level I as the sheet: no visible glow. Light stays inside the
    # cracks: never a whole glowing plate. "groups" overrides one material group: the skin glows far less.
    1: {"emission_strength": 0.8, "tint_r": (0.42, 0.40, 0.38, 0.0), "tint_b": (0.80, 0.70, 0.52, 0.0),
        "emit_g": 0.0},
    2: {"emission_strength": 1.05, "tint_r": (0.30, 0.29, 0.28, 0.55), "tint_b": (0.80, 0.70, 0.52, 0.0),
        "emit_g": 0.30, "groups": {"skin": {"emit_g": 0.06}}},
    3: {"emission_strength": 1.3, "tint_r": (0.27, 0.26, 0.25, 0.65), "tint_b": (0.86, 0.72, 0.50, 0.6),
        "emit_g": 0.65, "groups": {"skin": {"emit_g": 0.16}}},
}


def default_flow(P, part):
    return np.broadcast_to(np.array([-1.0, -0.2, 0.0], np.float32), P.shape).copy()


def shade(group, ctx):
    return shade_skin(ctx) if group == "skin" else shade_stone(ctx)


def scales(P, size=1.0, seed=5):
    """Rounded cobble scales (sheet skin): Voronoi cells, domed, dark gaps."""
    f1, f2, cid = noise.worley(P * (8.5 / size), seed)
    edge = 1 - sstep(0.0, 0.14, f2 - f1)
    dome = np.sqrt(sstep(0.0, 0.9, f2 - f1))
    h = dome * 0.013 * (0.7 + 0.3 * cid) - edge * 0.004
    return h, edge, cid


def eye_iris(P):
    out = np.zeros(len(P), np.float32)
    slit = np.zeros(len(P), np.float32)
    for s in (-1, 1):
        c = np.array([2.575, 2.16, 0.300 * s], np.float32)
        ax = np.array([0.45, 0.05, 0.89 * s], np.float32)
        ax /= np.linalg.norm(ax)
        rel = P - c
        dist = np.linalg.norm(rel, axis=1)
        cosang = np.sum(rel * ax, 1) / np.maximum(dist, 1e-6)
        near = (dist < 0.08).astype(np.float32)
        out = np.maximum(out, sstep(0.55, 0.68, cosang) * near)
        slit = np.maximum(slit, sstep(0.88, 0.95, cosang) * near * sstep(0.5, 0.2, np.abs(rel[:, 0]) / 0.07))
    return out, slit


def shade_skin(ctx):
    P, N = ctx.P, ctx.N
    y = P[:, 1]
    w = {c: ctx.W[:, i] for i, c in enumerate(CLASSES["skin"])}
    rad = getattr(ctx, "rad", np.full(ctx.n, 0.1, np.float32))
    h_s, edge, cid = scales(P)
    # sheet skin: dark charcoal-brown cobbles with lighter, warm grey crowns and black gaps
    col = mix(lin("#231a14"), lin("#433428"), cid * 0.55 + 0.30 * sstep(0.2, 0.8, 1 - edge))
    col = mix(col, lin("#2c221b"), sstep(-0.1, -0.7, N[:, 1]) * 0.6)
    col = mix(col, lin("#120d0b"), edge * 0.85)
    col = col * (1.0 + 0.14 * noise.fbm(P * 1.2, 3, seed=50)[:, None])
    crease = edge * sstep(0.35, 0.65, noise.fbm(P * 2.4, 2, seed=52) + 0.5) * sstep(1.2, 1.9, y)
    tooth = mix(lin("#d6c7a6"), lin("#7d6a4c"), sstep(0.014, 0.034, rad))
    claw = mix(lin("#c9ae86"), lin("#3e2f22"), sstep(0.022, 0.080, rad))
    col = mix(col, lin("#3b1712"), w["mouth"])
    col = mix(col, tooth, w["tooth"])
    col = mix(col, claw, w["claw"])
    col = mix(col, lin("#140c08"), w["eye"])
    iris, slit = eye_iris(P)
    iris = iris * w["eye"]
    slit = slit * w["eye"]
    col = mix(col, lin("#e0881c"), iris)
    col = mix(col, lin("#050302"), slit)
    em = lin("#f0a12d")[None, :] * (iris * (1 - slit) * 0.6)[:, None]
    rough = w["skin"] * (0.74 + 0.10 * cid) + w["mouth"] * 0.45 + w["tooth"] * 0.40 + w["claw"] * 0.48 + w["eye"] * 0.1
    chest = sstep(1.1, 1.8, y) * sstep(1.0, 1.8, P[:, 0]) * sstep(0.0, -0.6, N[:, 1] - 0.3)
    tailg = sstep(-2.6, -3.4, P[:, 0])
    variant = np.stack([np.zeros(ctx.n, np.float32), np.clip((chest + tailg * 0.8) * crease * 3.0, 0, 1),
                        np.zeros(ctx.n, np.float32), np.ones(ctx.n, np.float32)], 1)

    def height(Q):
        hs, _e, _c = scales(Q)
        return hs * w["skin"] + noise.ridged(Q * 60.0, 2, seed=8) * 0.0005 * (w["tooth"] + w["claw"])
    return {"albedo": np.clip(col, 0, 1), "roughness": np.clip(rough, 0, 1), "emissive": em, "height": height,
            "height_eps": 0.003, "cavity": 1.0 - 0.32 * edge * w["skin"], "variant": variant}


_AX = np.array([p[0] for p in TAIL[::-1]] + [p[0] for p in SPINE_Y[1:]], np.float32)
_AY = np.array([p[1] for p in TAIL[::-1]] + [p[1] for p in SPINE_Y[1:]], np.float32)


def rim_of(P, N):
    """How much a scute texel faces sideways from the body axis (the scute rims and keel flanks catch the light
    on the sheet: bronze edges) - the scutes lie on the body, so their faces look away from the axis."""
    x = P[:, 0]
    ay = np.interp(x, _AX, _AY).astype(np.float32)
    radial = np.stack([np.zeros_like(x), P[:, 1] - ay, P[:, 2]], 1)
    radial /= np.maximum(np.linalg.norm(radial, axis=1, keepdims=True), 1e-6)
    facing = np.abs(np.sum(N * radial, 1))
    return sstep(0.42, 0.12, facing)


def shade_stone(ctx):
    P, N = ctx.P, ctx.N
    rad = getattr(ctx, "rad", np.full(ctx.n, 0.2, np.float32))
    rim = rim_of(P, N)
    # fine flaking of the basalt and a few deep cracks (amber seams of the higher levels)
    f1, f2, cid = noise.worley(P * 6.0, 23)
    crack = 1 - sstep(0.0, 0.05, f2 - f1)
    deep = crack * sstep(0.60, 0.85, noise.fbm(P * 1.8, 3, seed=24) + 0.5)
    grain = noise.fbm(P * np.array([14.0, 40.0, 14.0], np.float32), 3, seed=25)
    base = mix(lin("#2e2722"), lin("#41372f"), sstep(0.2, 0.8, cid))
    base = base * (0.88 + 0.22 * grain)[:, None]
    bronze = mix(lin("#7a5536"), lin("#a87a4a"), sstep(-0.3, 0.6, grain))
    base = mix(base, bronze, np.clip(rim * 0.80, 0, 1))
    base = mix(base, lin("#1a1512"), crack * 0.7)
    em = lin("#f0a12d")[None, :] * deep[:, None] * 0.0
    rough = 0.80 - 0.12 * rim + 0.06 * cid
    shoulders = sstep(0.0, 0.6, np.abs(P[:, 2]) - 0.8) * sstep(0.6, 1.2, P[:, 0]) * sstep(1.9, 1.5, P[:, 0])
    variant = np.stack([np.clip(shoulders, 0, 1) * (1 - crack), np.clip(deep * 0.9 + crack * 0.2, 0, 1),
                        np.clip(rim * 0.8, 0, 1) * (1 - crack), np.ones(ctx.n, np.float32)], 1)

    def height(Q):
        a1, a2, ci = noise.worley(Q * 6.0, 23)
        s2 = 1 - sstep(0.0, 0.05, a2 - a1)
        return ((ci - 0.5) * 0.003 + noise.fbm(Q * np.array([14.0, 40.0, 14.0], np.float32), 2, seed=25) * 0.0016
                - s2 * 0.004)
    return {"albedo": np.clip(base, 0, 1), "roughness": np.clip(rough, 0, 1), "emissive": em, "height": height,
            "height_eps": 0.004, "cavity": 1.0 - 0.35 * crack, "variant": variant}


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
    from anim import plan_feet, keyed
    from qmath import ease, q_euler
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

    # slam (creature-references dragar/01-04): 14 preparation - crouched on all four feet, head down, the body
    # gathered; 32 launch - the weight on the hind legs and the tail, chest high, both forefeet off the ground and
    # reaching forward; 43 contact - both forefeet strike the ground together ahead of the shoulders, which sag
    # under the armour; 62 recovery - the weight back on four feet, the body steadies; the forefeet then step back
    # to the idle stance (the clip starts and ends in the idle stance)
    st = {k: IDLE_STANCE[k]["dx"][0][1] for k in IDLE_STANCE}

    def fore(k, sgn):
        x0 = st[k]
        return {"dy": [(0, 0.0, "hold"), (12, 0.0, "hold"), (20, 0.30), (30, 1.80), (36, 1.62), (41, 0.40), (43, 0.0, "hold"),
                       (72, 0.0, "hold"), (77, 0.18), (82, 0.0, "hold"), (90, 0.0)],
                "dx": [(0, x0, "hold"), (12, x0, "hold"), (30, x0 + 0.30), (36, x0 + 0.40), (43, 0.34, "hold"), (72, 0.34, "hold"),
                       (82, x0, "hold"), (90, x0)],
                "dz": [(0, 0.0, "hold"), (12, 0.0, "hold"), (30, 0.30 * sgn), (43, 0.06 * sgn, "hold"),
                       (72, 0.06 * sgn, "hold"), (82, 0.0, "hold")],
                "toe": [(0, 0.0, "hold"), (12, 0.0, "hold"), (22, -0.8), (36, -0.9), (41, -0.2), (43, 0.0, "hold"),
                        (72, 0.0, "hold"), (77, -0.6), (82, 0.0, "hold")],
                "foot": [(0, 0.0, "hold"), (12, 0.0, "hold"), (22, -0.9), (36, -1.1), (41, -0.3), (43, 0.0, "hold"),
                         (72, 0.0, "hold"), (77, -0.5), (82, 0.0, "hold")]}
    slam_legs = C.leg_keys(rig, {("Front", "L"): fore(("Front", "L"), -1), ("Front", "R"): fore(("Front", "R"), 1),
                                 ("Hind", "L"): {"dx": [(0, st[("Hind", "L")])]},
                                 ("Hind", "R"): {"dx": [(0, st[("Hind", "R")])]}}, 90)
    slam_pp = [(0, 0.0), (14, -0.07), (22, 0.18), (32, 0.52), (37, 0.46), (43, -0.14), (52, -0.08), (66, 0.0),
               (90, 0.0)]
    pp_track = keyed(slam_pp)

    def slam_tail(fr):
        """The long tail stays on the ground as a prop while the body rears: the base counters the pelvis pitch,
        the next segments bend gently down (the spring chain would curl a 3.6 m tail over the back)."""
        a = float(pp_track(fr)[0])
        return {"Tail_01": q_euler(-1.05 * a, 0, 0), "Tail_02": q_euler(0.16 * a, 0, 0),
                "Tail_03": q_euler(0.10 * a, 0, 0)}
    out.append(C.standing(rig, g, pre + "attack_slam", 90, {
        "pp": slam_pp,
        "py": [(0, 0.0), (14, -0.32), (22, -0.08), (32, 0.30), (37, 0.26), (43, -0.38), (55, -0.22), (68, -0.04),
               (90, 0.0)],
        "px": [(0, 0.0), (14, -0.12), (32, -0.08), (43, 0.26), (60, 0.24), (72, 0.20), (84, 0.04), (90, 0.0)],
        "n1p": [(0, 0.0), (14, -0.32), (24, -0.12), (32, -0.16), (37, -0.18), (43, -0.32), (58, -0.20), (72, 0.02),
                (90, 0.0)],
        "hp": [(0, 0.0), (14, -0.12), (32, -0.06), (43, -0.18), (72, 0.04), (90, 0.0)],
        "jaw": [(0, 0.0), (14, 0.06), (28, 0.45), (43, 0.42), (54, 0.12), (66, 0.0), (90, 0.0)],
        "taily": [(0, 0.0), (20, 0.06), (43, -0.05), (60, 0.0)],
        "gF": [(0, 0.0), (14, -0.08), (32, -0.25), (43, 0.10), (58, 0.04), (90, 0.0)],
        "cp": [(0, 0.0), (32, 0.10), (43, -0.10), (60, 0.0)],
        "belly": [(0, 0.0), (43, -0.06), (60, 0.0)]},
        legs_fn=slam_legs, stiff=70.0, damp=14.0, tail_amp=0.0, extra_fn=slam_tail,
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


# attack key poses compared with creature-references/<id>/0N-<phase>.png (tools/proof.py poses)
ATTACK_KEYS = {"clip": "attack_slam", "frames": [14, 32, 43, 62], "az": 34, "el": 6}


# ---------------------------------------------------------------- creature-references (model.png) head carriage
# dragar/model.png side and front views: the head is carried lower than the shoulders (jaw line ~1.5 m, eyes
# ~2.0 m); the head and the front of the neck move down 0.12 m (rigid teeth and eyes follow without shear).
import warp as _warp  # noqa: E402

WARP = [("move", (0.0, -0.12, 0.0), [("x", 1.68, 2.18), ("y", 0.95, 1.30)])]   # head only, not the forefeet
shade = _warp.unwarped_shade(WARP, shade)

# battle footprint / display adapter (publish.py): the body plus the first metre of the tail
FOOTPRINT_X_MIN = -3.5
