"""lf_env_hunter_shelter v3 — abandoned hunter shelter (art/06): oak post-and-beam frame with king posts and
braces, mossy tiled gable roof (overlapping tile rows split into tile runs), plank back/gable walls, stone
chimney, workbench, stump seat, woodpile, hanging net, ivy; dirt patch with stones.

Blueprint: 5.6 x 3.6 m frame, eaves 2.0 m, ridge 3.6 m, roof overhang 0.3 m. Camera: f fixed to the sheet focal
length, pose from 9 frame corners (king post foot/apex, eave ends, front posts). Long axis = X, open side -Y.
"""
import math

import numpy as np

import ibm
from geo import Geo, rot_z

ID = "lf_env_hunter_shelter"
MAIN_BOX = (815, 0, 1265, 268)
OX, OY = MAIN_BOX[0], MAIN_BOX[1]
BUDGET0 = 6000
ATLAS = 2048
MASK_THRESH = 0.09
MASK_EXCLUDE = [(442, 0, 450, 268)]
F_PAINT = 1921.0
L, D, EAVE, RIDGE, OH = 5.6, 3.6, 2.0, 3.6, 0.3
CORR = [((950, 222), (-L / 2, 0.0, 0.0)), ((950, 27), (-L / 2, 0.0, RIDGE)), ((870, 95), (-L / 2 - 0.05, D / 2 + OH, EAVE - 0.27)),
        ((1030, 93), (-L / 2 - OH, -D / 2 - OH, EAVE - 0.27)), ((1250, 130), (L / 2 + OH, -D / 2 - OH, EAVE - 0.27)),
        ((1222, 212), (L / 2, -D / 2, 0.0)), ((1222, 135), (L / 2, -D / 2, EAVE)), ((1130, 222), (0.9, -D / 2, 0.0)),
        ((1130, 128), (0.9, -D / 2, EAVE))]
INSETS = {
    "front": dict(box=(1272, 12, 1392, 88), dir=(0, 1, 0), fit="width"),
    "side": dict(box=(1418, 12, 1512, 88), dir=(1, 0, 0), fit="width"),
}
NO_PROJECT_TAGS = ()
TAG_SWATCH = {"tile": "roof", "plank": "wood", "beam": "wood_h", "chimney": "stone"}
SWATCHES = {
    "roof": dict(box=(1376, 104, 1505, 178), metres=1.2),
    "wood": dict(box=(1395, 195, 1420, 250), metres=0.8),
    "wood_h": dict(box=(1395, 195, 1420, 250), metres=0.8, rotate=True),
    "stone": dict(box=(1140, 30, 1160, 60), metres=0.6),
    "ground": dict(plane=dict(origin=(-1.0, -4.2, 0.0), ex=(1, 0, 0), ey=(0, 1, 0), size_m=2.0), metres=2.0),
    "gravel": dict(plane=dict(origin=(-1.0, -4.2, 0.0), ex=(1, 0, 0), ey=(0, 1, 0), size_m=2.0), metres=2.0),
    "grass": dict(box=(830, 220, 870, 240), metres=1.2),
}
SWATCH_FALLBACK = {"metal": "wood", "rope": "wood", "cloth": "wood", "glow": "wood", "water": "ground"}
CLASS_TRAIN = {
    "roof": [(1060, 70, 1120, 100), (1150, 100, 1200, 120), (1376, 104, 1505, 178)],
    "wood": [(940, 60, 960, 200), (1120, 140, 1140, 210), (1180, 160, 1215, 200), (1395, 195, 1420, 250)],
    "stone": [(1140, 30, 1160, 60), (1220, 215, 1250, 235), (900, 200, 940, 215)],
    "veg": [(840, 140, 870, 180), (1240, 150, 1260, 190)],
    "dirt": [(1000, 230, 1100, 250)],
}
ACCEPT = {"roof": {"roof", "veg"}, "wood": {"wood", "roof"}, "stone": {"stone"}, "ground": {"dirt", "veg", "stone"},
          "rope": {"wood"}}
CLASS_SWATCH = {"ground": {"veg": "grass", "dirt": "ground", "stone": "gravel"}}
NORMAL_STRENGTH = {"roof": 3.0, "wood": 2.5, "stone": 3.0, "ground": 1.5}
EDGE_WIDTH_M = 0.03
EDGE_STRENGTH = {"roof": 0.45, "wood": 0.35, "stone": 0.5}
POLY_JITTER = 0.03
CARD_KINDS = {"ivy_a": "ivy", "ivy_b": "ivy", "net": "net", "grass_a": "grass", "fern_a": "fern"}


def S(x, y):
    return (x - OX, y - OY)


def camera_points():
    P = [w for _, w in CORR]
    p = [S(*q) for q, _ in CORR]
    return np.array(P, float), np.array(p, float), dict(f0=F_PAINT, fix_f=True, free_pp=True, pp_prior=0.06,
                                                        init_centre=(-14.0, -24.0, 9.0), init_target=(0.0, 0.0, 1.6))


def build(lod, cam=None, crop=None, mask=None, cards=None):
    g = Geo(seed=71 + lod)
    rng = np.random.default_rng(3 + lod)
    xs_posts = [-L / 2, -0.9, 0.9, L / 2]
    # posts (front/back rows) + gable king posts
    for y in (-D / 2, D / 2):
        for x in xs_posts if lod < 2 else (-L / 2, L / 2):
            g.box((x, y, EAVE / 2), (0.24, 0.24, EAVE), rot_z(rng.normal(0, 0.02)), "wood", "post", skip=("-z",),
                  chamfer=0.03 if lod == 0 else 0)
    for x in (-L / 2, L / 2):
        g.box((x, 0, RIDGE / 2), (0.26, 0.26, RIDGE), None, "wood", "post", skip=("-z",), chamfer=0.03 if lod == 0 else 0)
    # wall plates, tie beams, ridge beam, braces
    for y in (-D / 2, D / 2):
        g.beam((-L / 2 - 0.25, y, EAVE + 0.1), (L / 2 + 0.25, y, EAVE + 0.1), 0.24, 0.22, mat="wood", tag="beam")
    for x in (xs_posts if lod < 2 else (-L / 2, L / 2)):
        g.beam((x, -D / 2 - 0.3, EAVE + 0.1), (x, D / 2 + 0.3, EAVE + 0.1), 0.2, 0.22, mat="wood", tag="beam")
    g.beam((-L / 2 - 0.35, 0, RIDGE + 0.05), (L / 2 + 0.35, 0, RIDGE + 0.05), 0.24, 0.26, mat="wood", tag="beam")
    if lod < 2:
        for x in (-L / 2, L / 2):
            for s in (-1, 1):
                g.beam((x, 0.12 * s, 2.6), (x, s * 1.2, EAVE + 0.2), 0.16, 0.16, mat="wood", tag="brace")
        for x in xs_posts:
            for d in (-1, 1):
                if abs(x + d * 0.6) <= L / 2:
                    g.beam((x, -D / 2, 1.45), (x + d * 0.6, -D / 2, EAVE), 0.14, 0.14, mat="wood", tag="brace")
    # rafters (visible ends) + overlapping tile rows split into tile runs, both slopes
    half = D / 2 + OH
    slope_len = math.hypot(half, RIDGE - EAVE + 0.27 * (OH / (D / 2)) + 0.0)
    ang = math.atan2(RIDGE - (EAVE - 0.27), half)
    nrow = 9 if lod == 0 else (5 if lod == 1 else 2)
    nrun = 7 if lod == 0 else (3 if lod == 1 else 1)
    for s in (-1, 1):
        for k in range(nrow):
            t0 = k / nrow
            row_len = 1.0 / nrow * slope_len * 1.28
            # row starts at the eave and climbs; each row overlaps the one below
            yy = s * half * (1 - t0) - s * 0.0
            zz = (EAVE - 0.27) + (RIDGE - EAVE + 0.27) * t0 + 0.1
            cdir = np.array([0, -s * math.cos(ang), math.sin(ang)])
            centre_r = np.array([0, yy, zz]) + cdir * row_len / 2
            for j in range(nrun):
                x0 = -L / 2 - OH + (L + 2 * OH) * j / nrun
                x1 = -L / 2 - OH + (L + 2 * OH) * (j + 1) / nrun
                c = centre_r + np.array([(x0 + x1) / 2, 0, 0]) + np.array([0, 0, 0.012 * (j % 2)])
                R = np.stack([[1, 0, 0], cdir, np.cross([1, 0, 0], cdir)], 1)
                g.box(c, (x1 - x0 - 0.02, row_len, 0.05), R, "roof", "tile", skip=("-z",) if lod else ())
        if lod == 0:
            for x in np.linspace(-L / 2, L / 2, 7):
                p0 = np.array([x, s * (half + 0.05), EAVE - 0.3])
                p1 = np.array([x, 0.0, RIDGE + 0.05])
                g.beam(p0, p1, 0.12, 0.14, mat="wood", tag="beam")
    # plank walls: back wall and left gable (with triangle)
    pw = 0.26
    nb = int(L / pw)
    for i in range(nb if lod == 0 else (nb // 3 if lod == 1 else 1)):
        w = L / (nb if lod == 0 else (nb // 3 if lod == 1 else 1))
        x = -L / 2 + (i + 0.5) * w
        h = EAVE - rng.uniform(0.0, 0.15) if lod == 0 else EAVE
        g.box((x, D / 2 + 0.06, h / 2), (w - 0.015, 0.05, h), None, "wood", "plank", skip=("-z",))
    ng = int(D / pw)
    for i in range(ng if lod == 0 else (ng // 3 if lod == 1 else 1)):
        w = D / (ng if lod == 0 else (ng // 3 if lod == 1 else 1))
        y = -D / 2 + (i + 0.5) * w
        top = EAVE + (RIDGE - EAVE) * (1 - abs(y) / (D / 2))
        g.box((-L / 2 - 0.06, y, top / 2), (0.05, w - 0.015, top), None, "wood", "plank", skip=("-z",))
    # stone chimney at the back-right
    cx, cy = 1.7, D / 2 - 0.2
    if lod == 0:
        g.masonry_box((cx - 0.38, cy - 0.38, 0.0), (cx + 0.38, cy + 0.38, 4.35), course=0.32, block=(0.3, 0.45), cheap=True,
                      top=True, tag="chimney", seed=4)
    else:
        g.box((cx, cy, 2.17), (0.76, 0.76, 4.35), None, "stone", "chimney", skip=("-z",))
    g.box((cx, cy, 4.42), (0.86, 0.86, 0.14), None, "stone", "chimney")
    # workbench, stump, woodpile
    g.box((-0.6, D / 2 - 0.55, 0.86), (2.6, 0.7, 0.08), None, "wood", "bench")
    for sx in (-1.2, 1.2):
        for sy in (-0.28, 0.28):
            g.box((-0.6 + sx, D / 2 - 0.55 + sy, 0.42), (0.1, 0.1, 0.84), None, "wood", "bench", skip=("-z", "+z"))
    if cam is not None:
        u, v = S(1013, 228)
        Ps = cam.on_plane_z(np.array([u + .5]), np.array([v + .5]), 0.0)[0]
    else:
        Ps = np.array([-1.0, -0.8, 0])
    g.cyl(Ps, Ps + np.array([0, 0, 0.5]), 0.28, 0.25, n=10 if lod == 0 else 6, mat="wood", tag="stump", jitter=0.06)
    nlog = (5, 4, 3) if lod == 0 else ((3, 2) if lod == 1 else (2,))
    for r, n in enumerate(nlog):
        for i in range(n):
            x = L / 2 - 1.0 + (i - (n - 1) / 2) * 0.27 + (0.135 if r % 2 else 0)
            z = 0.14 + r * 0.24
            g.cyl((x, -0.9, z), (x, 0.2, z), 0.13, n=7 if lod == 0 else 5, mat="wood", tag="log")
    # hanging net + ivy cards
    if lod < 2 and cards:
        if "net" in cards:
            u0, v0, u1, v1, aw, ah = cards["net"]
            g.add(np.array([(-L / 2 + 0.6, -D / 2 - 0.02, 0.9), (-L / 2 + 1.4, -D / 2 - 0.02, 0.9), (-L / 2 + 1.4, -D / 2 - 0.02, 2.05),
                            (-L / 2 + 0.6, -D / 2 - 0.02, 2.05)]), [[0, 1, 2, 3]], "card_net", "net",
                  uv=[[(u0, v0), (u1, v0), (u1, v1), (u0, v1)]])
        for k, (y0, z0, h) in enumerate([(-1.2, 2.4, 1.8), (0.4, 2.2, 1.6), (1.4, 2.0, 1.4)][: (3 if lod == 0 else 1)]):
            u0, v0, u1, v1, aw, ah = cards["ivy_a" if k % 2 else "ivy_b"]
            x = -L / 2 - 0.1
            g.add(np.array([(x, y0 - 0.45, z0 - h), (x, y0 + 0.45, z0 - h), (x, y0 + 0.45, z0), (x, y0 - 0.45, z0)]), [[0, 1, 2, 3]],
                  "card_ivy", "ivy", uv=[[(u0, v0), (u1, v0), (u1, v1), (u0, v1)]])
    base = Geo(seed=9 + lod)
    if cam is not None and mask is not None:
        poly = ibm.footprint(cam, mask, lambda x, y: np.zeros_like(x), ylim=(-7.0, D / 2 + 0.8), xlim=(-L / 2 - 2.5, L / 2 + 2.0))
        ibm.ground_patch(poly, lambda x, y: np.zeros_like(x) - 0.01, 0.6 if lod == 0 else (1.2 if lod == 1 else 2.6), g=base, undulate=0.02)
        rocks = [(905, 215, 12), (1090, 225, 9), (1215, 225, 14), (1065, 245, 9), (880, 200, 10), (1250, 230, 6), (1100, 238, 6)]
        ibm.place_rocks(base, cam, [(S(u, v)[0], S(u, v)[1], r) for u, v, r in rocks][: (7 if lod == 0 else 3 if lod == 1 else 0)],
                        sub=1 if lod == 0 else 0, seed=95, flat=0.65)
        if lod < 2 and cards:
            spots = [(850, 215, "fern_a", 24), (930, 230, "grass_a", 18), (1180, 235, "grass_a", 16), (1245, 205, "fern_a", 22),
                     (1020, 240, "grass_a", 14)]
            spots = [(S(u, v)[0], S(u, v)[1], n, h) for u, v, n, h in spots][:: (1 if lod == 0 else 2)]
            ibm.place_cards(base, cam, spots, cards)
    return dict(struct=g, base=base)


def colliders():
    C = [dict(type="box", centre=(0.0, D / 2 + 0.06, EAVE / 2), size=(L, 0.2, EAVE)),
         dict(type="box", centre=(-L / 2 - 0.06, 0.0, EAVE / 2), size=(0.2, D, EAVE)),
         dict(type="box", centre=(1.7, D / 2 - 0.2, 2.2), size=(0.8, 0.8, 4.4))]
    for x in (-L / 2, -0.9, 0.9, L / 2):
        C.append(dict(type="box", centre=(x, -D / 2, EAVE / 2), size=(0.26, 0.26, EAVE)))
    return C


def meta_extra():
    return dict(dimensions={"frame_m": [L, D], "eave_m": EAVE, "ridge_m": RIDGE, "overhang_m": OH},
                sockets={"chimney_top": [1.7, 4.5, -(D / 2 - 0.2)], "workbench": [-0.6, 0.9, -(D / 2 - 0.55)]})
