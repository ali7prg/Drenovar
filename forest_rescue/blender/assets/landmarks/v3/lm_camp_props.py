"""lf_env_camp_props v3 — traveller camp (art/06): russet canvas tarp on four lashed poles (sagging, folds,
hanging side flap, guy ropes), lantern on the right pole, two benches, stool, fire ring with tripod and pot,
crate stack with cloth, barrel, dirt patch with grass.

Camera: joint solve of the pole rectangle (width a, depth b) and pole heights with the painting camera
(f fixed to the sheet's solved focal length; front-left pole height 2.6 m sets the scale). Props are placed by
back-projecting their painted ground contacts. Blender: front faces -Y, Z up; origin = fire ring centre.
"""
import math

import numpy as np
from scipy.optimize import least_squares

import ibm
from camsolve import Cam
from geo import Geo, rot_z

ID = "lf_env_camp_props"
MAIN_BOX = (735, 578, 1240, 845)
OX, OY = MAIN_BOX[0], MAIN_BOX[1]
BUDGET0 = 6000
ATLAS = 2048
MASK_THRESH = 0.09
F_PAINT = 1921.0
H_FL = 2.6

# pole (bottom, top) in sheet px: front-left, front-right (lantern), back-right, back-left
POLES = {"FL": ((902, 815), (902, 582)), "FR": ((1172, 781), (1172, 617)), "BR": ((1050, 752), (1050, 607)),
         "BL": ((786, 782), (786, 664))}

INSETS = {
    "front": dict(box=(1236, 612, 1396, 694), dir=(0, 1, 0), fit="width"),
    "side": dict(box=(1408, 612, 1516, 694), dir=(1, 0, 0), fit="width"),
}
NO_PROJECT_TAGS = ()
TAG_SWATCH = {"bench": "wood_h", "plank": "wood_h", "crate": "wood_h", "stool": "wood_h"}
SWATCHES = {
    "wood": dict(box=(1504, 740, 1522, 830), metres=0.8),
    "wood_h": dict(box=(1504, 740, 1522, 830), metres=0.8, rotate=True),
    "cloth": dict(box=(1280, 718, 1386, 828), metres=1.4),
    "stone": dict(box=(1176, 820, 1206, 838), metres=0.6),
    "ground": dict(box=(900, 835, 990, 845), metres=2.0),
    "gravel": dict(box=(940, 780, 990, 800), metres=1.6),
    "grass": dict(box=(760, 805, 800, 830), metres=1.2),
    "rope": dict(box=(1278, 720, 1300, 740), metres=0.3),
    "metal": dict(box=(1430, 740, 1470, 800), metres=0.4),
    "glow": dict(box=(1440, 760, 1460, 790), metres=0.2),
}
SWATCH_FALLBACK = {"roof": "stone", "water": "ground"}
CLASS_TRAIN = {
    "cloth": [(870, 610, 990, 650), (800, 690, 860, 740), (1000, 610, 1100, 640)],
    "wood": [(897, 700, 907, 800), (1170, 650, 1176, 760), (900, 770, 960, 790), (1110, 730, 1150, 760)],
    "stone": [(960, 790, 1040, 815)],
    "dirt": [(940, 760, 1000, 790), (1000, 820, 1060, 840)],
    "veg": [(760, 780, 790, 800), (1210, 800, 1235, 820)],
}
ACCEPT = {"cloth": {"cloth"}, "wood": {"wood", "cloth"}, "stone": {"stone"}, "ground": {"dirt", "veg", "stone"},
          "metal": {"wood"}, "rope": {"wood", "cloth"}, "glow": set()}
CLASS_SWATCH = {"ground": {"veg": "grass", "dirt": "ground", "stone": "gravel"}}
NORMAL_STRENGTH = {"stone": 2.5, "wood": 2.5, "ground": 1.5, "cloth": 1.5, "rope": 2.0}
EDGE_WIDTH_M = 0.025
EDGE_STRENGTH = {"stone": 0.45, "wood": 0.35}
TAG_RGB = {"glass": (1.0, 0.82, 0.45)}
CLASS_LAB = {"cloth": (np.array([42.0, 22.0, 26.0]), np.array([6.0, 4.0, 5.0]))}
POLY_JITTER = 0.06
WIND = {"dir": (0.3, 1.0, 0.25), "amp": 0.10, "ztop": 2.7, "drop": 1.4}
CARD_KINDS = {"grass_a": "grass", "weed_a": "weed", "fern_a": "fern", "grass_b": "grass"}
LAYOUT = {}


def S(x, y):
    return (x - OX, y - OY)


def _layout_points(a, b, hs):
    base = {"FL": (-a / 2, -b / 2), "FR": (a / 2, -b / 2), "BR": (a / 2, b / 2), "BL": (-a / 2, b / 2)}
    P, p = [], []
    for k, ((bx, by), (tx, ty)) in POLES.items():
        x, y = base[k]
        P += [(x, y, 0.0), (x, y, hs[k])]
        p += [S(bx, by), S(tx, ty)]
    return np.array(P, float), np.array(p, float)


def solve_layout(W, H):
    names = ["FR", "BR", "BL"]

    def unpack(x):
        cam = Cam(F_PAINT, W / 2, H / 2, x[0:3], x[3:6], size=(W, H))
        a, b = x[6], x[7]
        hs = {"FL": H_FL, **{n: x[8 + i] for i, n in enumerate(names)}}
        return cam, a, b, hs

    def res(x):
        cam, a, b, hs = unpack(x)
        P, p = _layout_points(a, b, hs)
        u, v, z = cam.project(P)
        return np.r_[u - p[:, 0], v - p[:, 1], 0.5 * (np.array([hs[n] for n in names]) - 2.4)]

    best = None
    import cv2
    for a0, b0, yaw in [(4.4, 2.8, 0.5), (4.0, 3.4, 0.3), (3.6, 3.0, 0.7)]:
        C = np.array([-6.0, -16.0, 8.0])
        tgt = np.array([0.0, 0.0, 0.8])
        fwd = (tgt - C) / np.linalg.norm(tgt - C)
        right = np.cross(fwd, [0, 0, 1.0])
        right /= np.linalg.norm(right)
        down = np.cross(fwd, right)
        Rg = np.stack([right, down, fwd])
        x0 = np.r_[cv2.Rodrigues(Rg)[0].ravel(), -Rg @ C, a0, b0, 2.4, 2.4, 2.0]
        sol = least_squares(res, x0, max_nfev=4000)
        if best is None or sol.cost < best.cost:
            best = sol
    cam, a, b, hs = unpack(best.x)
    P, p = _layout_points(a, b, hs)
    return cam, a, b, hs, P, p


def camera_points():
    if "P" not in LAYOUT:
        cam, a, b, hs, P, p = solve_layout(MAIN_BOX[2] - MAIN_BOX[0], MAIN_BOX[3] - MAIN_BOX[1])
        LAYOUT.update(a=a, b=b, hs=hs, P=P, p=p)
    return LAYOUT["P"], LAYOUT["p"], dict(f0=F_PAINT, fix_f=True, free_pp=True, pp_prior=0.05,
                                          init_centre=(-6.0, -16.0, 8.0), init_target=(0.0, 0.0, 0.8))


def gp(cam, x, y):
    u, v = S(x, y)
    return ibm.ground_at(cam, u, v, None, 0.0)


def mpx(cam, P, px):
    return ibm.metres(cam, P, px)


# ============================================================================ geometry
def build(lod, cam=None, crop=None, mask=None, cards=None):
    g = Geo(seed=31 + lod)
    cloth = Geo(seed=41 + lod)
    a, b, hs = LAYOUT["a"], LAYOUT["b"], LAYOUT["hs"]
    pos = {"FL": np.array([-a / 2, -b / 2, 0.0]), "FR": np.array([a / 2, -b / 2, 0.0]), "BR": np.array([a / 2, b / 2, 0.0]),
           "BL": np.array([-a / 2, b / 2, 0.0])}
    # poles (rough round timber) with rope lashings
    for k, p in pos.items():
        h = hs[k] + 0.18
        g.cyl(p, p + np.array([0, 0, h]), 0.085, 0.07, n=8 if lod == 0 else 5, mat="wood", tag="pole", jitter=0.08)
        if lod < 2:
            for dz in ((0.0, 0.08, 0.16) if lod == 0 else (0.08,)):
                g.cyl(p + np.array([0, 0, hs[k] - 0.12 + dz]), p + np.array([0, 0, hs[k] - 0.07 + dz]), 0.105, n=8,
                      mat="rope", tag="lashing")
            if lod == 0:
                g.cyl(p + np.array([0, 0, 0.35]), p + np.array([0, 0, 0.45]), 0.1, n=8, mat="rope", tag="lashing")
    # tarp: bilinear sagging sheet between the pole tops + a hanging flap on the left (BL-FL) side
    corners = {k: pos[k] + np.array([0, 0, hs[k]]) for k in pos}
    nu, nv = (14, 10) if lod == 0 else ((7, 5) if lod == 1 else (3, 3))
    P = np.zeros((nu, nv, 3))
    rng = np.random.default_rng(5)
    for i in range(nu):
        for j in range(nv):
            u, v = i / (nu - 1), j / (nv - 1)
            q = (1 - u) * (1 - v) * corners["FL"] + u * (1 - v) * corners["FR"] + u * v * corners["BR"] + (1 - u) * v * corners["BL"]
            sag = 0.45 * math.sin(math.pi * u) * math.sin(math.pi * v) + 0.75 * math.sin(math.pi * u) * (1 - v) ** 2 \
                + 0.25 * math.sin(math.pi * v) * (1 - u)
            fold = 0.05 * math.sin(u * 9.0 + v * 2.0) * math.sin(math.pi * v)
            q = q + np.array([0, 0, -sag + fold])
            P[i, j] = q
    # overhang beyond the poles (canvas edges flop over)
    cloth.grid_surface(P, "cloth", "tarp")
    nf = 6 if lod == 0 else 3
    F = np.zeros((nf, nv, 3))
    for i in range(nf):
        t = i / (nf - 1)
        for j in range(nv):
            top = P[0, j]
            F[i, j] = top + np.array([-0.08 * t, -0.05 * t, -1.5 * t * (0.75 + 0.25 * (j / (nv - 1)))]) + \
                np.array([0.03 * math.sin(j * 1.7) * t, 0, 0])
    cloth.grid_surface(F, "cloth", "flap")
    # guy ropes from the outer pole tops to pegs
    if lod < 2:
        for k, d in (("FL", (-0.5, -0.6)), ("BL", (-0.7, 0.4)), ("BR", (0.5, 0.6))):
            top = corners[k]
            peg = pos[k] + np.array([d[0] * 1.4, d[1] * 1.0, 0.0])
            g.tube([top, (top + peg) / 2 + np.array([0, 0, -0.05]), peg], 0.015, n=4, mat="rope", tag="guy")
            g.cyl(peg, peg + np.array([0, 0, 0.18]), 0.03, n=4, mat="wood", tag="peg")
    props(g, lod, cam, pos, hs)
    base = Geo(seed=9 + lod)
    if cam is not None and mask is not None:
        poly = ibm.footprint(cam, mask, lambda x, y: np.zeros_like(x), ylim=(-6.0, b / 2 + 1.6), xlim=(-a / 2 - 4.0, a / 2 + 3.0))
        ibm.ground_patch(poly, lambda x, y: np.zeros_like(x) - 0.01, 0.6 if lod == 0 else (1.2 if lod == 1 else 2.6), g=base,
                         undulate=0.02)
        rocks = [(900, 830, 5), (1060, 838, 4), (1185, 822, 5), (812, 815, 4), (1215, 805, 4), (950, 835, 3)]
        ibm.place_rocks(base, cam, [(S(u, v)[0], S(u, v)[1], r) for u, v, r in rocks][: (6 if lod == 0 else 3 if lod == 1 else 0)],
                        sub=1 if lod == 0 else 0, seed=60)
        if lod < 2 and cards:
            spots = [(770, 790, "grass_a", 26), (760, 760, "fern_a", 30), (1220, 800, "grass_a", 22), (1015, 735, "weed_a", 28),
                     (1060, 740, "grass_b", 20), (800, 820, "grass_a", 18), (1180, 830, "weed_a", 16), (860, 735, "grass_b", 18)]
            spots = [(S(u, v)[0], S(u, v)[1], n, h) for u, v, n, h in spots][:: (1 if lod == 0 else 2)]
            ibm.place_cards(base, cam, spots, cards)
    return dict(struct=g, cloth=cloth, base=base)


def props(g, lod, cam, pos, hs):
    if cam is None:
        return
    rng = np.random.default_rng(3)
    yaw0 = 0.0

    def bench(px, py, wpx, yaw, tag):
        P = gp(cam, px, py)
        L = mpx(cam, P, wpx) * 1.05
        R = rot_z(yaw)
        ex = R[:, 0]
        ey = R[:, 1]
        g.box(P + np.array([0, 0, 0.44]), (L, 0.36, 0.08), R, "wood", tag, chamfer=0.015 if lod == 0 else 0)
        for s in (-0.4, 0.4):
            g.box(P + ex * L * s + np.array([0, 0, 0.2]), (0.1, 0.32, 0.4), R, "wood", tag, skip=("-z",))
        return P

    b1 = bench(865, 812, 112, 0.18, "bench")
    bench(917, 755, 80, 0.12, "bench")
    if lod == 0:   # bedroll / bag on the front bench
        g.cyl(b1 + np.array([-0.35, 0, 0.62]), b1 + np.array([0.25, 0.02, 0.62]), 0.17, n=10, mat="cloth", tag="bedroll")
    # stool
    P = gp(cam, 1090, 833)
    w = mpx(cam, P, 62)
    g.box(P + np.array([0, 0, 0.4]), (w, w * 0.7, 0.08), rot_z(-0.2), "wood", "stool")
    for sx in ((-1, 1) if lod < 2 else ()):
        for sy in (-1, 1):
            g.box(P + rot_z(-0.2) @ np.array([sx * w * 0.35, sy * w * 0.22, 0.18]), (0.07, 0.07, 0.36), rot_z(-0.2), "wood",
                  "stool", skip=("-z", "+z"))
    # fire ring + embers + tripod + pot
    Pf = gp(cam, 1000, 798)
    rr = mpx(cam, Pf, 50)
    ns = 11 if lod == 0 else (7 if lod == 1 else 0)
    for k in range(ns):
        a = 2 * math.pi * k / ns
        c = Pf + np.array([math.cos(a) * rr, math.sin(a) * rr * 0.9, 0.0])
        g.rock(c + np.array([0, 0, 0.08]), (0.17, 0.15, 0.13), seed=70 + k, sub=0 if lod else 1, mat="stone", tag="ring")
    g.quad(Pf + np.array([-rr * 0.7, -rr * 0.7, 0.03]), Pf + np.array([rr * 0.7, -rr * 0.7, 0.03]),
           Pf + np.array([rr * 0.7, rr * 0.7, 0.03]), Pf + np.array([-rr * 0.7, rr * 0.7, 0.03]), "glow", "embers")
    if lod < 2:
        for k in range(4 if lod == 0 else 2):
            a = 0.5 + k * 1.3
            g.beam(Pf + np.array([math.cos(a) * 0.35, math.sin(a) * 0.3, 0.08]), Pf + np.array([-math.cos(a) * 0.35, -math.sin(a) * 0.3, 0.12]),
                   0.07, 0.07, mat="wood", tag="log")
    top = Pf + np.array([0, 0, 1.45])
    for k in range(3 if lod < 2 else 0):
        a = 2 * math.pi * k / 3 + 0.3
        g.beam(Pf + np.array([math.cos(a) * rr * 0.9, math.sin(a) * rr * 0.8, 0.0]), top + np.array([0, 0, 0.1]), 0.05, 0.05,
               mat="metal" if lod == 0 else "wood", tag="tripod")
    g.tube([top, top - np.array([0, 0, 0.55])], 0.012, n=4, mat="metal", tag="chain")
    g.cyl(top - np.array([0, 0, 0.85]), top - np.array([0, 0, 0.55]), 0.17, 0.2, n=10 if lod == 0 else 6, mat="metal", tag="pot")
    # crate stack with draped cloth
    Pc = gp(cam, 1117, 778)
    wc = mpx(cam, Pc, 100)
    R = rot_z(-0.25)
    g.box(Pc + np.array([0, 0, 0.32]), (wc, wc * 0.55, 0.64), R, "wood", "crate", skip=("-z",))
    g.box(Pc + R @ np.array([wc * 0.18, 0, 0.0]) + np.array([0, 0, 0.82]), (wc * 0.55, wc * 0.45, 0.36), R, "wood", "crate",
          skip=("-z",))
    if lod == 0:
        for s in (-0.25, 0.25):
            g.box(Pc + R @ np.array([wc * s, -wc * 0.28, 0.32]), (0.05, 0.02, 0.6), R, "wood", "crate_band")
    cl = np.zeros((5, 4, 3))
    for i in range(5):
        for j in range(4):
            u, v = i / 4, j / 3
            cl[i, j] = Pc + R @ np.array([wc * 0.18 + (u - 0.5) * wc * 0.62, (v - 0.5) * wc * 0.5 - 0.02, 0.0]) + \
                np.array([0, 0, 1.02 - 0.55 * max(0, abs(v - 0.5) - 0.3) * 2 - 0.05 * math.sin(u * 7)])
    g.grid_surface(cl, "cloth", "crate_cloth")
    # barrel
    Pb = gp(cam, 1201, 781)
    rb = mpx(cam, Pb, 30) * 0.5
    g.cyl(Pb, Pb + np.array([0, 0, rb * 2.4]), rb * 0.9, rb * 0.9, n=12 if lod == 0 else 6, mat="wood", tag="barrel")
    if lod == 0:
        for z in (0.2, 0.8):
            g.cyl(Pb + np.array([0, 0, rb * 2.4 * z - 0.02]), Pb + np.array([0, 0, rb * 2.4 * z + 0.03]), rb * 0.93, n=12,
                  mat="metal", tag="hoop", caps=(False, False))
    # lantern on the front-right pole with an iron bracket
    fr = pos["FR"]
    lz = hs["FR"] - 0.25
    arm_end = fr + np.array([-0.35, -0.05, lz])
    g.beam(fr + np.array([0, 0, lz]), arm_end, 0.04, 0.04, mat="metal", tag="bracket")
    lc = arm_end + np.array([0, 0, -0.32])
    g.cyl(lc + np.array([0, 0, -0.18]), lc + np.array([0, 0, 0.16]), 0.11, n=6, mat="glow" if lod else "metal", tag="glass")
    if lod < 2:
        g.cyl(lc + np.array([0, 0, 0.16]), lc + np.array([0, 0, 0.3]), 0.12, 0.03, n=6, mat="metal", tag="lantern_cap")
    if lod == 0:
        g.cyl(lc + np.array([0, 0, -0.14]), lc + np.array([0, 0, 0.12]), 0.085, n=6, mat="glow", tag="glass")
    LAYOUT["lantern"] = lc.tolist()
    LAYOUT["fire"] = Pf.tolist()


def colliders():
    a, b, hs = LAYOUT["a"], LAYOUT["b"], LAYOUT["hs"]
    C = []
    for (x, y), k in (((-a / 2, -b / 2), "FL"), ((a / 2, -b / 2), "FR"), ((a / 2, b / 2), "BR"), ((-a / 2, b / 2), "BL")):
        C.append(dict(type="cylinder", centre=(x, y, hs[k] / 2), size=(0.2, 0.2, hs[k])))
    if "fire" in LAYOUT:
        f = LAYOUT["fire"]
        C.append(dict(type="cylinder", centre=(f[0], f[1], 0.15), size=(1.2, 1.2, 0.3)))
    return C


def meta_extra():
    gl = lambda p: [round(p[0], 3), round(p[2], 3), round(-p[1], 3)]
    return dict(sockets={"lantern_light": gl(LAYOUT.get("lantern", (2, 0, 2))), "fire_light": gl(np.add(LAYOUT.get("fire", (0, 0, 0)), (0, 0, 0.4)))},
                dimensions={"pole_rectangle_m": [round(LAYOUT["a"], 2), round(LAYOUT["b"], 2)],
                            "pole_heights_m": {k: round(v, 2) for k, v in LAYOUT["hs"].items()}},
                notes="origin = centre of the pole rectangle on the ground; pole layout and heights solved jointly with the art/06 camera")
