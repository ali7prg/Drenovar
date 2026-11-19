"""lf_env_standing_stones v3 — five carved standing stones (knotwork) around a paved dirt circle with moss,
grass and pebbles (art/06 main view + row inset; art/01 south forest stones).

Blueprint (art/06 row inset, previous collider layout): stone heights 2.2 / 2.0 / 2.75 / 2.1 / 2.3 m on a ring
of radius ~3 m. Camera: solvePnP on the 10 stone foot/top points (f fixed to the sheet focal length), then each
stone is re-placed by back-projecting its painted foot. Blender: front faces -Y, Z up, origin = circle centre.
"""
import math

import numpy as np

import ibm
from geo import Geo, rot_z

ID = "lf_env_standing_stones"
MAIN_BOX = (0, 578, 472, 845)
OX, OY = MAIN_BOX[0], MAIN_BOX[1]
BUDGET0 = 6000
ATLAS = 2048
MASK_THRESH = 0.09
MASK_FILL = 40000
F_PAINT = 1921.0
# name: (blueprint xy, height, painted foot px, painted top px, painted width px, thickness ratio)
STONES = {
    "S1": ((-3.2, -1.2), 2.2, (88, 810), (76, 662), 80, 0.55),
    "S2": ((-2.0, 1.9), 2.0, (130, 730), (127, 619), 58, 0.55),
    "S3": ((0.4, 2.9), 2.75, (247, 715), (245, 578), 86, 0.6),
    "S4": ((3.0, 1.6), 2.1, (393, 740), (395, 624), 62, 0.55),
    "S5": ((2.6, -1.6), 2.3, (361, 817), (380, 689), 80, 0.55),
}
INSETS = {"row": dict(box=(478, 598, 706, 694), dir=(0, 1, 0), fit="width")}
NO_PROJECT_TAGS = ()
TAG_SWATCH = {"stone": "stone_carved"}
SWATCHES = {
    "stone": dict(box=(630, 722, 705, 828), metres=0.9),
    "stone_carved": dict(box=(503, 720, 600, 828), metres=0.9),
    "ground": dict(box=(170, 700, 230, 735), metres=1.8),
    "gravel": dict(box=(170, 700, 230, 735), metres=1.8),
    "grass": dict(box=(20, 790, 60, 815), metres=1.2),
}
SWATCH_FALLBACK = {"wood": "stone", "metal": "stone", "rope": "stone", "cloth": "stone", "glow": "stone", "water": "ground"}
CLASS_TRAIN = {
    "stone": [(60, 680, 110, 760), (215, 600, 280, 690), (340, 700, 390, 790), (380, 640, 415, 700)],
    "veg": [(15, 790, 50, 815), (300, 795, 330, 815), (100, 735, 120, 755)],
    "dirt": [(170, 700, 230, 735), (150, 760, 220, 790)],
}
ACCEPT = {"stone": {"stone", "veg"}, "ground": {"dirt", "veg", "stone"}}
CLASS_SWATCH = {"ground": {"veg": "grass", "dirt": "ground", "stone": "gravel"}}
NORMAL_STRENGTH = {"stone": 4.0, "ground": 1.5}
EDGE_STRENGTH = {"stone": 0.0}
POLY_JITTER = 0.03
CARD_KINDS = {"grass_a": "grass", "fern_a": "fern", "weed_a": "weed", "grass_b": "grass"}
PLACED = {}


def S(x, y):
    return (x - OX, y - OY)


def camera_points():
    P, p = [], []
    for k, ((x, y), h, foot, top, w, t) in STONES.items():
        P += [(x, y, 0.0), (x, y, h)]
        p += [S(*foot), S(*top)]
    return np.array(P, float), np.array(p, float), dict(f0=F_PAINT, fix_f=True, free_pp=True, pp_prior=0.05,
                                                        init_centre=(-2.0, -18.0, 8.0), init_target=(0.0, 0.5, 0.8))


def stone_mesh(g, c, h, w, t, yaw, seed, lod, tag):
    """Rounded menhir: lofted superellipse rings, tapering, domed top, slight lean; flat-ish carved faces."""
    rng = np.random.default_rng(seed)
    nr = 12 if lod == 0 else (8 if lod == 1 else 5)
    nz = 9 if lod == 0 else (5 if lod == 1 else 3)
    ang = np.linspace(0, 2 * math.pi, nr, endpoint=False)
    rings = []
    lean = rng.normal(0, 0.04, 2)
    for i in range(nz + 1):
        s = i / nz
        zz = h * s
        taper = 1.0 - 0.18 * s ** 1.5
        if s > 0.75:          # domed / rounded top
            k = (s - 0.75) / 0.25
            taper *= math.sqrt(max(1 - k * k, 0.02)) * 0.85 + 0.15 * (1 - k)
        ring = []
        for a in ang:
            ca, sa = math.cos(a), math.sin(a)
            # superellipse cross-section (flat faces), slight noise
            ex = 2.6
            r = 1.0 / (abs(ca) ** ex + abs(sa) ** ex) ** (1 / ex)
            noise = 1 + 0.05 * math.sin(3 * a + seed) * math.sin(5 * s + seed)
            ring.append((ca * r * w / 2 * taper * noise, sa * r * t / 2 * taper * noise, zz))
        rings.append(np.array(ring) + np.array([lean[0] * zz, lean[1] * zz, 0]))
    V = np.concatenate(rings)
    V = V @ rot_z(yaw).T + np.array([c[0], c[1], -0.15])
    F = []
    for i in range(nz):
        for j in range(nr):
            j2 = (j + 1) % nr
            F.append([i * nr + j, i * nr + j2, (i + 1) * nr + j2, (i + 1) * nr + j])
    F.append([nz * nr + j for j in range(nr)])
    g.add(V, F, "stone", tag)


def build(lod, cam=None, crop=None, mask=None, cards=None):
    g = Geo(seed=51 + lod)
    for i, (k, ((x, y), h, foot, top, w, t)) in enumerate(STONES.items()):
        if cam is not None:
            P = ibm.ground_at(cam, *S(*foot), None, 0.0)
            x, y = P[0], P[1]
            wm = ibm.metres(cam, P, w)
            # height from the painted top: closest point of the top pixel ray to the stone's vertical axis
            o, d = cam.ray(np.array([S(*top)[0] + 0.5]), np.array([S(*top)[1] + 0.5]))
            d = d[0]
            tt = ((np.array([x, y]) - o[:2]) @ d[:2]) / max(d[:2] @ d[:2], 1e-9)
            h = float(np.clip(o[2] + tt * d[2], 1.2, 3.6))
            # face the circle centre
            yaw = math.atan2(-y, -x) + math.pi / 2
        else:
            wm, yaw = 1.1, 0.0
        PLACED[k] = (x, y, h, wm, wm * t, yaw)
        stone_mesh(g, (x, y), h, wm, wm * t, yaw, 7 + i, lod, f"stone{k}")
    base = Geo(seed=9 + lod)
    if cam is not None and mask is not None:
        poly = ibm.footprint(cam, mask, lambda x, y: np.zeros_like(x), ylim=(-7.0, 5.0), xlim=(-7.0, 7.0))
        ibm.ground_patch(poly, lambda x, y: np.zeros_like(x) - 0.01, 0.6 if lod == 0 else (1.2 if lod == 1 else 2.6), g=base,
                         undulate=0.02)
        rocks = [(215, 820, 7), (165, 738, 5), (235, 718, 5), (300, 770, 5), (272, 810, 6), (430, 770, 6), (60, 760, 4),
                 (128, 790, 4), (330, 740, 4)]
        ibm.place_rocks(base, cam, [(S(u, v)[0], S(u, v)[1], r) for u, v, r in rocks][: (9 if lod == 0 else 4 if lod == 1 else 0)],
                        sub=1 if lod == 0 else 0, seed=80, flat=0.5)
        if lod < 2 and cards:
            spots = [(30, 795, "grass_a", 24), (115, 815, "fern_a", 22), (300, 805, "grass_a", 20), (420, 795, "grass_b", 22),
                     (190, 715, "grass_a", 18), (300, 712, "weed_a", 18), (440, 745, "fern_a", 20), (20, 760, "grass_b", 18),
                     (150, 740, "grass_a", 16), (350, 830, "weed_a", 14)]
            spots = [(S(u, v)[0], S(u, v)[1], n, h) for u, v, n, h in spots][:: (1 if lod == 0 else 2)]
            ibm.place_cards(base, cam, spots, cards)
    return dict(struct=g, base=base)


def colliders():
    C = []
    for k, (x, y, h, w, t, yaw) in PLACED.items():
        C.append(dict(type="box", centre=(x, y, h / 2), size=(w, t, h), yaw=yaw))
    return C


def meta_extra():
    return dict(dimensions={k: {"height_m": round(v[2], 2), "width_m": round(v[3], 2), "thickness_m": round(v[4], 2),
                                "position_gltf": [round(v[0], 2), 0.0, round(-v[1], 2)]} for k, v in PLACED.items()},
                sockets={"circle_centre": [0.0, 0.0, 0.0]},
                notes="knotwork carving: painted relief projected from art/06 + normal map from the carving swatch")
