"""Горный Драгор (dragor; poster: «Горный Драгар»): mountain colossus. L1 dimensions from 02_CREATURES.txt:
shoulder 3.10 m, dorsal spikes 3.80 m, nose to tail base 4.00 m, tail 2.20 m (total 6.20 m), body width 2.50 m.
Five thick clawed toes per foot (front feet bigger), 22 rock plates rigid to their bones, amber seams.
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

FRONT = {"joints": [(0.55, 2.85, 0.55), (0.80, 2.25, 1.00), (0.52, 1.42, 1.12), (0.82, 0.55, 1.06),
                    (0.96, 0.17, 1.06), (1.24, 0.0, 1.06)]}
HIND = {"joints": [(-1.45, 2.45, 0.45), (-1.40, 2.05, 0.86), (-1.05, 1.30, 0.96), (-1.52, 0.52, 0.92),
                   (-1.40, 0.15, 0.92), (-1.14, 0.0, 0.92)]}
TAIL = [(-1.95, 2.45, 0), (-2.35, 2.25, 0), (-2.75, 1.96, 0), (-3.15, 1.62, 0), (-3.52, 1.26, 0), (-3.86, 0.90, 0),
        (-4.15, 0.58, 0)]


def side(p, s):
    return np.array([p[0], p[1], abs(p[2]) * s])


def skeleton():
    sk = Skeleton()
    sk.add("MotionRoot", None, (0, 0, 0))
    sk.add("Pelvis", "MotionRoot", (-1.45, 2.45, 0))
    sk.add("Spine_01", "Pelvis", (-0.85, 2.65, 0))
    sk.add("Spine_02", "Spine_01", (-0.20, 2.80, 0))
    sk.add("Chest", "Spine_02", (0.45, 2.85, 0))
    sk.add("Neck_01", "Chest", (1.05, 2.70, 0))
    sk.add("Neck_02", "Neck_01", (1.36, 2.60, 0))
    sk.add("Head", "Neck_02", (1.56, 2.52, 0), tail=(2.08, 2.34, 0))
    sk.add("Jaw", "Head", (1.58, 2.34, 0), tail=(2.02, 2.10, 0))
    sk.add("Tongue", "Jaw", (1.70, 2.30, 0), tail=(1.92, 2.22, 0))
    sk.add("Throat", "Neck_02", (1.30, 2.18, 0), tail=(1.50, 2.12, 0))
    for nm, s in SIDES:
        sk.add(f"Cheek_{nm}", "Head", (1.62, 2.45, 0.28 * s), tail=(1.80, 2.40, 0.26 * s))
    sk.add("Belly", "Spine_02", (-0.25, 1.55, 0), tail=(-0.25, 1.42, 0))
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
    sk.socket("socket_head", "Head", (1.62, 2.86, 0))
    sk.socket("socket_mouth", "Jaw", (2.00, 2.16, 0))
    sk.socket("socket_chest", "Chest", (1.10, 1.70, 0))
    sk.socket("socket_slam_center", "Chest", (1.40, 0.0, 0))
    for nm, s in SIDES:
        sk.socket(f"socket_foot_front_{nm.lower()}", f"Toe_Front_{nm}", side(FRONT["joints"][5], s))
        sk.socket(f"socket_foot_hind_{nm.lower()}", f"Toe_Hind_{nm}", side(HIND["joints"][5], s))
        sk.socket(f"socket_claw_{nm.lower()}", f"Toe_Front_{nm}", side((1.36, 0.02, 1.06), s))
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
    P = [Prim("ellipsoid", "Chest", k=0.0, c=(0.35, 2.30, 0), r=(1.00, 0.85, 1.02), name="ribcage"),
         Prim("ellipsoid", "Chest", k=0.20, c=(0.95, 2.05, 0), r=(0.55, 0.62, 0.85), name="breast"),
         Prim("ellipsoid", "Belly", k=0.22, c=(-0.45, 1.88, 0), r=(0.85, 0.42, 0.82), name="belly"),
         Prim("ellipsoid", "Spine_01", k=0.22, c=(-0.70, 2.42, 0), r=(0.75, 0.58, 0.84), name="loin"),
         Prim("ellipsoid", "Pelvis", k=0.20, c=(-1.40, 2.28, 0), r=(0.60, 0.58, 0.80), name="hips"),
         Prim("cone", "Neck_01", k=0.18, a=(0.95, 2.55, 0), b=(1.42, 2.52, 0), ra=0.72, rb=0.50, name="neck"),
         Prim("ellipsoid", "Throat", k=0.16, c=(1.25, 2.18, 0), r=(0.40, 0.32, 0.50), name="dewlap"),
         Prim("ellipsoid", "Head", k=0.12, c=(1.62, 2.56, 0), r=(0.42, 0.32, 0.40), name="skull"),
         Prim("cone", "Head", k=0.10, a=(1.78, 2.50, 0), b=(2.06, 2.38, 0), ra=0.31, rb=0.19, name="snout"),
         Prim("cone", "Jaw", k=0.08, a=(1.55, 2.26, 0), b=(2.00, 2.13, 0), ra=0.28, rb=0.15, name="jaw"),
         Prim("box", "Head", k=0.008, neg=True, mat="mouth", c=(1.86, 2.27, 0), h=(0.24, 0.014, 0.30), round=0.006,
              R=rot_z(-0.24), name="mouthslit")]
    for nm, s in SIDES:
        P += [Prim("ellipsoid", f"Cheek_{nm}", k=0.08, c=(1.55, 2.42, 0.30 * s), r=(0.26, 0.20, 0.14),
                   name=f"cheek{nm}"),
              Prim("ellipsoid", "Head", k=0.06, c=(1.72, 2.80, 0.20 * s), r=(0.22, 0.08, 0.12), R=rot_z(-0.2),
                   name=f"brow{nm}"),
              Prim("sphere", "Head", k=0.015, neg=True, c=(1.83, 2.70, 0.255 * s), r=0.06, name=f"socket{nm}"),
              Prim("ellipsoid", f"Shoulder_{nm}", k=0.18, c=side((0.70, 2.50, 0.85), s), r=(0.55, 0.62, 0.36),
                   R=rot_z(-0.35), name=f"scapula{nm}")]
        P += leg_prims("Front", nm, s, FRONT["joints"])
        P += leg_prims("Hind", nm, s, HIND["joints"])
    radii = [0.66, 0.54, 0.43, 0.32, 0.22, 0.13, 0.05]
    P += chain(TAIL, radii, None, k=0.10, name="tail", bones=[f"Tail_0{i + 1}" for i in range(6)])
    return P


def rock_plate(centre, n, back, L, W, T, bone, tilt, yaw, name, rng):
    """Thick faceted rock slab with carved rear point and a raised ridge (rigid to one bone)."""
    Rf = plate_frame(n, back)
    R = Rf @ rot_y(yaw) @ rot_z(tilt)
    c = np.asarray(centre, float)
    xa, ya, za = R[:, 0], R[:, 1], R[:, 2]
    out = [Prim("box", bone, k=0.0, mat="stone", name=name + "a", c=c, h=(L * 0.5, T, W * 0.5), round=0.03, R=R),
           Prim("box", bone, k=0.05, mat="stone", name=name + "ridge", c=c + ya * T * 0.9 - xa * L * 0.05,
                h=(L * 0.32, T * 0.7, W * 0.22), round=0.02, R=R @ rot_y(np.pi / 4) @ rot_x(0.0))]
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


def build_armor(core, rng):
    plates, spikes = [], []
    specs = []
    for (x, ang, L, W, bone) in ((0.95, 0.0, 0.85, 0.80, "Chest"), (0.62, 0.62, 0.85, 0.75, "Chest"),
                                 (0.62, -0.62, 0.85, 0.75, "Chest"), (0.20, 0.0, 0.90, 0.85, "Spine_02"),
                                 (-0.10, 0.65, 0.85, 0.75, "Spine_02"), (-0.10, -0.65, 0.85, 0.75, "Spine_02"),
                                 (-0.55, 0.0, 0.85, 0.80, "Spine_01"), (-0.85, 0.62, 0.80, 0.70, "Spine_01"),
                                 (-0.85, -0.62, 0.80, 0.70, "Spine_01"), (-1.30, 0.40, 0.80, 0.70, "Pelvis"),
                                 (-1.30, -0.40, 0.80, 0.70, "Pelvis"), (-1.62, 0.0, 0.70, 0.66, "Pelvis")):
        specs.append((np.array([x, 2.6 + 2.0 * np.cos(ang), 2.0 * np.sin(ang)]), L, W, bone, 0.09))
    for nm, s in SIDES:
        specs.append((side((0.85, 2.85, 2.2), s), 0.95, 0.80, f"Shoulder_{nm}", 0.10))
        specs.append((side((0.55, 2.35, 2.2), s), 0.75, 0.70, f"Shoulder_{nm}", 0.09))
        specs.append((side((0.70, 1.05, 2.2), s), 0.70, 0.55, f"LowerLeg_Front_{nm}", 0.08))
        specs.append((side((-1.20, 1.85, 2.2), s), 0.80, 0.70, f"UpperLeg_Hind_{nm}", 0.09))
    for i, (x, y) in enumerate(((-2.25, 3.6), (-2.75, 3.3), (-3.20, 2.9))):
        specs.append((np.array([x, y, 0.0]), 0.62 - 0.1 * i, 0.55 - 0.1 * i, f"Tail_0{i + 2}", 0.07 - 0.01 * i))
    starts = np.array([sp[0] for sp in specs], np.float32)
    pts, nrm = surface_points(core, starts, steps=16)
    for k, ((st, L, W, bone, T), p, n) in enumerate(zip(specs, pts, nrm)):
        n = n / np.linalg.norm(n)
        plates.append(rock_plate(p + n * 0.06, n, np.array([-1.0, -0.1, 0]), L * 1.18, W * 1.15, T, bone,
                                 0.14 + rng.normal(0, 0.03), rng.normal(0, 0.12), f"plate{k}", rng))
    # dorsal and shoulder spikes (angular, leaning back)
    xs = [1.0, 0.70, 0.40, 0.10, -0.20, -0.50, -0.80, -1.10, -1.45]
    hs = [0.42, 0.58, 0.68, 0.70, 0.66, 0.58, 0.50, 0.42, 0.36]
    starts = np.array([[x, 4.2, 0.0] for x in xs], np.float32)
    pts, nrm = surface_points(core, starts, steps=16)
    for i, (p, n, h) in enumerate(zip(pts, nrm, hs)):
        bone = "Chest" if p[0] > 0.1 else ("Spine_02" if p[0] > -0.5 else ("Spine_01" if p[0] > -1.0 else "Pelvis"))
        spikes.append(spike(p + n * 0.10, n, h, 0.16, bone, f"spike{i}"))
    for nm, s in SIDES:
        starts = np.array([side((0.75, 3.3, 1.6), s), side((0.45, 3.3, 1.5), s)], np.float32)
        pts, nrm = surface_points(core, starts, steps=16)
        for i, (p, n) in enumerate(zip(pts, nrm)):
            spikes.append(spike(p + n * 0.12, n, 0.36 - 0.06 * i, 0.12, f"Shoulder_{nm}", f"sspike{nm}{i}",
                                lean=np.array([-0.4, 0.2, 0.0])))
    return plates, spikes


def teeth_part():
    P = []
    for nm, s in SIDES:
        for i in range(7):
            t = i / 6.0
            x = 2.00 - 0.42 * t
            zz = (0.06 + 0.20 * t) * s
            a = np.array([x, 2.30 - 0.02 * t, zz])
            L = 0.11 if i in (1, 2) else 0.07
            P.append(Prim("cone", "Head", k=0.006, mat="tooth", name=f"tu{nm}{i}", a=a, b=a + np.array([0.01, -L, 0]),
                          ra=0.028, rb=0.004))
            a2 = np.array([x - 0.02, 2.16 + 0.04 * t, zz * 0.92])
            P.append(Prim("cone", "Jaw", k=0.006, mat="tooth", name=f"tl{nm}{i}", a=a2,
                          b=a2 + np.array([0.0, L * 0.9, 0]), ra=0.026, rb=0.004))
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
    return Part("eyes", [Prim("sphere", "Head", k=0.0, mat="eye", c=(1.82, 2.70, 0.245 * s), r=0.055, name=f"eye{nm}")
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
              "faces": (44000, 17500, 5200)},
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
    for k, pr in enumerate(plates):
        parts.append({"name": f"plate{k}", "part": Part(f"plate{k}", pr, band=0.04), "material": "stone",
                      "rigid": pr[0].bone, "faces": (900, 380, 100), "sharp": 40})
    for k, pr in enumerate(spikes):
        parts.append({"name": f"spike{k}", "part": Part(f"spike{k}", pr, band=0.04), "material": "stone",
                      "rigid": pr[0].bone, "faces": (300, 120, 36), "sharp": 50})
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
LEVELS = {  # R: shoulder plates + veins (II), G: chest/tail glow (III), B: light chips on spikes (III)
    1: {"emission_strength": 0.8, "tint_r": (0.42, 0.40, 0.38, 0.0), "tint_b": (0.80, 0.76, 0.68, 0.0),
        "emit_r": 0.0, "emit_g": 0.0},
    2: {"emission_strength": 1.15, "tint_r": (0.30, 0.29, 0.28, 0.6), "tint_b": (0.80, 0.76, 0.68, 0.0),
        "emit_r": 0.55, "emit_g": 0.0},
    3: {"emission_strength": 1.5, "tint_r": (0.28, 0.27, 0.26, 0.7), "tint_b": (0.86, 0.82, 0.74, 0.85),
        "emit_r": 0.8, "emit_g": 1.3},
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
    col = mix(lin("#2b2724"), lin("#3a332d"), cid * 0.6)
    col = mix(col, lin("#4a4038"), sstep(-0.1, -0.7, N[:, 1]) * 0.6)
    col = mix(col, lin("#151312"), edge * 0.7)
    col = col * (1.0 + 0.15 * noise.fbm(P * 1.5, 3, seed=50)[:, None])
    # faint amber in the deepest skin creases near the chest and under the plates
    crease = edge * sstep(0.35, 0.65, noise.fbm(P * 3.0, 2, seed=52) + 0.5) * sstep(1.6, 2.2, y)
    tooth = mix(lin("#d9cdb3"), lin("#8b7a5c"), sstep(0.012, 0.03, rad))
    claw = mix(lin("#c8b994"), lin("#3a3128"), sstep(0.02, 0.06, rad))
    col = mix(col, lin("#3b1712"), w["mouth"])
    col = mix(col, tooth, w["tooth"])
    col = mix(col, claw, w["claw"])
    col = mix(col, lin("#140c08"), w["eye"])
    em = lin("#bd4b1d")[None, :] * (crease * 0.25 * w["skin"])[:, None]
    eyeglow = np.zeros(ctx.n, np.float32)
    for s in (-1, 1):
        c = np.array([1.82, 2.70, 0.245 * s], np.float32)
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
    chest = sstep(1.6, 2.3, y) * sstep(0.2, 0.9, P[:, 0]) * sstep(0.0, -0.6, N[:, 1] - 0.3)
    tailg = sstep(-2.0, -2.6, P[:, 0])
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
    deep = seam * sstep(0.45, 0.75, noise.fbm(P * 1.8, 3, seed=24) + 0.5)
    base = mix(lin("#5c5853"), lin("#47433f"), sstep(0.2, 0.8, cid))
    base = base * (0.9 + 0.2 * noise.fbm(P * 6.0, 3, seed=25))[:, None]
    chip = sstep(0.55, 0.15, np.abs(N[:, 1])) * sstep(0.1, 0.5, noise.fbm(P * 8, 2, seed=26) + 0.5)
    spike_tip = sstep(0.12, 0.05, rad)
    base = mix(base, lin("#8f887c"), np.clip(chip * 0.5 + spike_tip * 0.4, 0, 1))
    base = mix(base, lin("#0f0d0c"), seam)
    em = (lin("#f0a12d")[None, :] * deep[:, None] * 0.9 + lin("#bd4b1d")[None, :] * (seam * (1 - deep) * 0.12)[:, None])
    rough = 0.88 - 0.10 * chip + 0.06 * cid
    shoulders = sstep(0.0, 0.6, np.abs(P[:, 2]) - 0.7) * sstep(0.1, 0.5, P[:, 0])
    variant = np.stack([np.clip(shoulders + deep, 0, 1), np.zeros(ctx.n, np.float32),
                        np.clip(chip * 0.7 + spike_tip, 0, 1), np.ones(ctx.n, np.float32)], 1)

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
        "jaw": [(0, 0.0), (50, 0.0), (56, 0.06), (66, 0.0), (120, 0.0)]}, loop=True))

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
        "dy": [(0, 0.0), (12, 0.10), (32, 0.95), (39, 0.90), (43, 0.0, "hold"), (90, 0.0)],
        "dx": [(0, 0.0), (32, 0.10), (43, 0.25, "hold"), (70, 0.25), (86, 0.0), (90, 0.0)],
        "toe": [(0, 0.0), (30, -0.9), (40, -0.3), (43, 0.0), (90, 0.0)],
        "foot": [(0, 0.0), (30, -1.1), (40, -0.3), (43, 0.0), (90, 0.0)]} for k in (("Front", "L"), ("Front", "R"))}, 90)
    out.append(C.standing(rig, g, pre + "attack_slam", 90, {
        "pp": [(0, 0.0), (14, -0.04), (32, 0.36), (39, 0.34), (43, -0.10), (52, -0.06), (90, 0.0)],
        "py": [(0, 0.0), (14, -0.10), (32, 0.20), (39, 0.18), (43, -0.22), (55, -0.16), (90, 0.0)],
        "px": [(0, 0.0), (14, -0.18), (32, -0.35), (43, 0.10), (60, 0.05), (90, 0.0)],
        "n1p": [(0, 0.0), (32, 0.18), (43, -0.22), (60, -0.10), (90, 0.0)],
        "hp": [(0, 0.0), (32, 0.10), (43, -0.10), (90, 0.0)],
        "jaw": [(0, 0.0), (30, 0.40), (43, 0.30), (54, 0.05), (62, 0.0)],
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
