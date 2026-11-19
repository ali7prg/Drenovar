"""lf_env_ruined_watchpost v3 — crumbled limestone watchpost: arched gate wall with voussoirs, ivy-covered
side wall, raised masonry terrace, broken stair descending to the right, broken wall stubs and pillars, rubble,
grass (art/06 main view + front/side insets; art/01 ruin arches).

Blueprint (art/06 front inset): terrace 1.8 m high, arch opening 1.3 x 2.4 m on the terrace, gate wall top
~5.5 m, stair risers 0.22 m / treads 0.36 m (7 steps). Camera: f fixed to the sheet focal length, pose from
8 blueprint corners (terrace, arch springers/apex, stair nosings, wall stubs). Wall height profiles are
back-projected from the painted silhouette onto the wall planes. Blender: front faces -Y, Z up.
"""
import math

import numpy as np

import ibm
from geo import Geo, rot_z

ID = "lf_env_ruined_watchpost"
MAIN_BOX = (760, 255, 1240, 575)
OX, OY = MAIN_BOX[0], MAIN_BOX[1]
BUDGET0 = 6000
ATLAS = 2048
MASK_THRESH = 0.09
MASK_EXCLUDE = [(0, 0, 60, 40), (420, 0, 480, 40)]
F_PAINT = 1921.0
TER_H = 1.8
TER_Y = -2.0          # terrace front face
ARCH = dict(x0=-0.65, x1=0.65, spring=TER_H + 1.75, y=0.0, t=0.85)

CORR = [((905, 535), (-2.0, TER_Y, 0.0)), ((905, 446), (-2.0, TER_Y, TER_H)), ((1088, 446), (2.0, TER_Y, TER_H)),
        ((975, 437), (ARCH["x0"], ARCH["y"], TER_H)), ((1008, 437), (ARCH["x1"], ARCH["y"], TER_H)),
        ((990, 328), (0.0, ARCH["y"], ARCH["spring"] + 0.65)), ((1233, 560), (5.0, TER_Y + 0.4, 0.0)),
        ((828, 525), (-4.1, -1.2, 0.0))]

INSETS = {
    "front": dict(box=(1242, 302, 1390, 394), dir=(0, 1, 0), fit="width"),
    "side": dict(box=(1392, 302, 1514, 394), dir=(1, 0, 0), fit="width"),
}
NO_PROJECT_TAGS = ()
TAG_SWATCH = {"wall": "stone_face", "arch": "stone_face", "terrace": "stone_face", "stair": "stair", "stub": "stone_face"}
SWATCHES = {
    "stone": dict(box=(1365, 418, 1495, 485), metres=1.6),
    "stone_face": dict(box=(1420, 430, 1470, 470), metres=0.8),
    "stair": dict(box=(1370, 500, 1495, 552), metres=1.5),
    "ground": dict(box=(880, 550, 960, 570), metres=2.0),
    "gravel": dict(box=(880, 550, 960, 570), metres=2.0),
    "grass": dict(box=(800, 530, 850, 560), metres=1.2),
}
SWATCH_FALLBACK = {"wood": "stone", "metal": "stone", "rope": "stone", "cloth": "stone", "glow": "stone", "water": "ground"}
CLASS_TRAIN = {
    "stone": [(1010, 350, 1060, 420), (930, 300, 970, 360), (1100, 460, 1180, 500), (1365, 418, 1495, 485)],
    "veg": [(840, 380, 880, 440), (800, 530, 840, 560), (1110, 540, 1150, 560)],
    "dirt": [(880, 550, 960, 570)],
}
ACCEPT = {"stone": {"stone", "veg"}, "ground": {"dirt", "veg", "stone"}}
CLASS_SWATCH = {"ground": {"veg": "grass", "dirt": "ground", "stone": "gravel"}}
NORMAL_STRENGTH = {"stone": 3.0, "ground": 1.5}
EDGE_WIDTH_M = 0.03
EDGE_STRENGTH = {"stone": 0.55}
MORTAR_RGB = (0.27, 0.25, 0.20)
POLY_JITTER = 0.09
CARD_KINDS = {"ivy_a": "ivy", "ivy_b": "ivy", "grass_a": "grass", "fern_a": "fern"}


def S(x, y):
    return (x - OX, y - OY)


def camera_points():
    P = [w for _, w in CORR]
    p = [S(*q) for q, _ in CORR]
    return np.array(P, float), np.array(p, float), dict(f0=F_PAINT, fix_f=True, free_pp=True, pp_prior=0.06,
                                                        init_centre=(-6.0, -40.0, 14.0), init_target=(0.5, 0.0, 2.0))


def profile(cam, mask, x_lo, x_hi, plane_y, z_min, z_max, step_px=3):
    """Top of the painted silhouette between sheet columns x_lo..x_hi back-projected onto plane y=plane_y."""
    xs, zs = [], []
    for c in range(S(x_lo, 0)[0], S(x_hi, 0)[0], step_px):
        rows = np.nonzero(mask[:, c])[0]
        if len(rows) == 0:
            continue
        P = cam.on_plane(np.array([c + 0.5]), np.array([rows.min() + 0.5]), (0, plane_y, 0), (0, 1, 0))[0]
        xs.append(P[0])
        zs.append(np.clip(P[2], z_min, z_max))
    return np.array(xs), np.array(zs)


def wall(g, x0, x1, y0, t, z0, prof, lod, tag, rng, opening=None, course=0.36, block=(0.4, 0.75)):
    """Masonry wall between x0..x1 (front face at y0, thickness t) from z0 up to the ragged profile."""
    px, pz = prof
    ch = course if lod == 0 else (0.7 if lod == 1 else 1.4)
    z = z0
    ci = 0
    while z < pz.max() - 0.05:
        x = x0 - (rng.uniform(0, block[0]) if ci % 2 else 0)
        while x < x1 - 0.02:
            L = rng.uniform(*block) if lod == 0 else (1.1 if lod == 1 else 2.0)
            a, b = max(x, x0), min(x + L, x1)
            x += L
            if b - a < 0.12:
                continue
            xm = (a + b) / 2
            top = np.interp(xm, px, pz)
            if z + ch * 0.45 > top:
                continue
            if opening is not None:
                ox0, ox1, spring = opening
                r = (ox1 - ox0) / 2
                xc = (ox0 + ox1) / 2
                if b > ox0 + 0.02 and a < ox1 - 0.02:
                    zc = spring + math.sqrt(max(r * r - (min(abs(xm - xc), r)) ** 2, 0))
                    if z < zc + 0.05:
                        continue
            hh = min(ch, top - z) if top - z < ch * 1.3 else ch
            c = (xm, y0 + t / 2, z + hh / 2)
            g.box(c, (b - a - 0.035, t - rng.uniform(0, 0.06), hh - 0.035), rot_z(rng.normal(0, 0.012)), "stone", tag,
                  skip=("-z",) if z > z0 + 0.01 else ("-z",))
        z += ch
        ci += 1


def build(lod, cam=None, crop=None, mask=None, cards=None):
    g = Geo(seed=61 + lod)
    rng = np.random.default_rng(13 + lod)
    if cam is None:
        return dict(struct=g, base=Geo())
    # gate wall with the arch (on the terrace)
    gp_ = profile(cam, mask, 922, 1078, ARCH["y"], TER_H + 0.4, 7.0)
    wall(g, -1.9, 1.95, ARCH["y"], ARCH["t"], TER_H, gp_, lod, "wall", rng,
         opening=(ARCH["x0"], ARCH["x1"], ARCH["spring"]))
    # voussoirs
    nv = 11 if lod == 0 else (7 if lod == 1 else 0)
    r0 = (ARCH["x1"] - ARCH["x0"]) / 2
    xc = (ARCH["x0"] + ARCH["x1"]) / 2
    for i in range(nv):
        a0 = math.pi * i / nv
        a1 = math.pi * (i + 1) / nv
        P = []
        for a, r in ((a0, r0), (a1, r0), (a1, r0 + 0.42), (a0, r0 + 0.42)):
            P.append((xc + math.cos(a) * r, ARCH["spring"] + math.sin(a) * r))
        poly = np.array(P)
        mid = poly.mean(0)
        poly = mid + (poly - mid) * 0.93
        g.prism(poly, 0, 1, "stone", "arch", R=np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]]).T @ np.eye(3) * 0 +
                np.array([[1, 0, 0], [0, 0, 1.0], [0, 1.0, 0]]) @ np.diag([1, ARCH["t"] + 0.06, 1]) @ np.eye(3),
                t=(0, ARCH["y"] - 0.03, 0))
    # ivy-covered side wall (left, in front of the gate wall)
    lp = profile(cam, mask, 828, 925, -1.0, 1.0, 5.0)
    wall(g, -4.1, -1.9, -1.0, 1.0, 0.0, lp, lod, "wall", rng)
    # terrace (raised masonry platform) + paving top
    tp = (np.array([-2.0, 2.6]), np.array([TER_H, TER_H]))
    wall(g, -2.0, 2.6, TER_Y, 2.0, 0.0, tp, lod, "terrace", rng, course=0.45)
    if lod < 2:
        nx = 6 if lod == 0 else 3
        for i in range(nx):
            for j in range(3 if lod == 0 else 2):
                x0 = -2.0 + 4.6 * i / nx
                y0 = TER_Y + 2.0 * j / (3 if lod == 0 else 2)
                g.box((x0 + 2.3 / nx, y0 + 1.0 / (3 if lod == 0 else 2), TER_H + 0.04), (4.6 / nx - 0.04, 2.0 / (3 if lod == 0 else 2) - 0.04, 0.08),
                      rot_z(rng.normal(0, 0.02)), "stone", "pave", skip=("-z",))
    # broken stair descending to the right-front
    nst = 7
    for k in range(nst if lod < 2 else 3):
        kk = k if lod < 2 else k * 2
        z_top = TER_H - (kk + 1) * TER_H / nst
        x0 = 2.6 + kk * 0.36
        g.box((x0 + 0.36 * (nst - kk) / 2, TER_Y + 1.0, (z_top + TER_H - kk * TER_H / nst) / 2 - (TER_H - kk * TER_H / nst - z_top) / 2 + (TER_H - kk * TER_H / nst) / 2 * 0 + 0.0),
              (0.36 * (nst - kk), 2.0 - 0.1 * (kk % 2), TER_H / nst), rot_z(rng.normal(0, 0.01)), "stone", "stair", skip=("-z",)) if False else None
        zb = TER_H - (kk + 1) * TER_H / nst
        zt = TER_H - kk * TER_H / nst
        g.box((x0 + 0.18, TER_Y + 1.0 + rng.normal(0, 0.03), (zb + zt) / 2), (0.38, 2.0 - 0.12 * (kk % 3), zt - zb), rot_z(rng.normal(0, 0.015)),
              "stone", "stair", skip=("-z",))
        if zb > 0.01:
            g.box((x0 + 0.18, TER_Y + 1.0, zb / 2), (0.36, 2.0, zb), None, "stone", "stair", skip=("-z", "+z", "-x"))
    # broken wall stubs / pillars on the right (painted silhouette profiles)
    for (xa, xb, sx0, sx1, y0) in ((2.6, 4.2, 1075, 1168, -0.3), (4.4, 5.1, 1170, 1206, -1.2), (5.4, 6.0, 1209, 1238, -1.8)):
        sp = profile(cam, mask, sx0, sx1, y0, 0.5, 5.0)
        if len(sp[0]) < 2:
            continue
        wall(g, xa, xb, y0, 0.8, 0.0 if y0 < -1 else TER_H * 0.0, sp, lod, "stub", rng)
    # ivy cards on the side wall / gate wall
    if lod < 2 and cards and "ivy_a" in cards:
        for k, (u, v, hpx, yv) in enumerate([(845, 395, 90, -1.05), (880, 380, 70, -1.05), (945, 345, 80, -0.05),
                                               (1050, 300, 50, -0.05), (905, 420, 60, -1.05), (1000, 455, 40, TER_Y - 0.05)][:: (1 if lod == 0 else 2)]):
            uu, vv = S(u, v)
            P = cam.on_plane(np.array([uu + 0.5]), np.array([vv + 0.5]), (0, yv, 0), (0, 1, 0))[0]
            h = ibm.metres(cam, P, hpx)
            u0, v0, u1, v1, aw, ah = cards["ivy_a" if k % 2 else "ivy_b"]
            top = P + np.array([0, -0.03, h * 0.2])
            g.add(np.array([top + (-h * 0.3, 0, -h), top + (h * 0.3, 0, -h), top + (h * 0.3, 0, 0), top + (-h * 0.3, 0, 0)]),
                  [[0, 1, 2, 3]], "card_ivy", "ivy", uv=[[(u0, v0), (u1, v0), (u1, v1), (u0, v1)]])
    base = Geo(seed=9 + lod)
    poly = ibm.footprint(cam, mask, lambda x, y: np.zeros_like(x), ylim=(-8.0, 1.5), xlim=(-7.0, 8.0))
    ibm.ground_patch(poly, lambda x, y: np.zeros_like(x) - 0.01, 0.7 if lod == 0 else (1.4 if lod == 1 else 2.8), g=base,
                     undulate=0.03)
    rubble = [(840, 515, 12), (900, 545, 9), (940, 560, 10), (955, 540, 11), (1080, 555, 9), (1125, 560, 7), (800, 545, 7),
              (1200, 545, 6), (1170, 520, 6)]
    ibm.place_rocks(base, cam, [(S(u, v)[0], S(u, v)[1], r) for u, v, r in rubble][: (9 if lod == 0 else 4 if lod == 1 else 0)],
                    sub=1 if lod == 0 else 0, seed=90, flat=0.6)
    if lod < 2 and cards:
        spots = [(800, 540, "grass_a", 26), (870, 520, "fern_a", 30), (1120, 548, "grass_a", 20), (1015, 520, "fern_a", 22),
                 (1190, 520, "grass_a", 18), (960, 555, "grass_a", 16), (1060, 545, "fern_a", 18)]
        spots = [(S(u, v)[0], S(u, v)[1], n, h) for u, v, n, h in spots][:: (1 if lod == 0 else 2)]
        ibm.place_cards(base, cam, spots, cards)
    return dict(struct=g, base=base)


def colliders():
    return [dict(type="box", centre=(0.3, TER_Y + 1.0, TER_H / 2), size=(4.6, 2.0, TER_H)),
            dict(type="box", centre=(0.0, ARCH["y"] + ARCH["t"] / 2, TER_H + 1.8), size=(3.9, ARCH["t"], 3.6)),
            dict(type="box", centre=(-3.0, -0.5, 2.0), size=(2.2, 1.0, 4.0)),
            dict(type="ramp", centre=(3.9, TER_Y + 1.0, TER_H / 2), size=(2.6, 2.0, TER_H))]


def meta_extra():
    return dict(dimensions={"terrace_height_m": TER_H, "arch_opening_m": [round(ARCH["x1"] - ARCH["x0"], 2), round(ARCH["spring"] + 0.65 - TER_H, 2)],
                            "stair": "7 steps, riser 0.26 m, tread 0.36 m"},
                sockets={"arch_centre": [0.0, TER_H, 0.0], "stair_foot": [5.3, 0.0, -TER_Y - 1.0]})
