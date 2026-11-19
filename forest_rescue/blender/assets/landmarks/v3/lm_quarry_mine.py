"""lf_env_quarry_mine v3 — limestone outcrop of big cut blocks with a timber mine portal, rails with sleepers,
a winch crane with a hanging block, cut blocks and a crate (art/06 main view + insets; art/01 SW quarry).

Blueprint: portal clear opening 2.2 x 2.0 m (posts 0.3, lintel 0.38, cap joists 0.24), rail gauge 0.6 m.
The camera is solved from the portal frame; everything else is placed by back-projecting its painted ground
contact onto z = 0 and sized from its painted pixel extent at that depth.
Blender axes: front (portal) faces -Y, Z up, origin = portal centre on the ground.
"""
import math

import numpy as np

import ibm
from geo import Geo, rot_z

ID = "lf_env_quarry_mine"
MAIN_BOX = (0, 272, 605, 588)
OX, OY = MAIN_BOX[0], MAIN_BOX[1]
BUDGET0 = 6000
ATLAS = 2048
MASK_THRESH = 0.09
MASK_EXCLUDE = [(515, 20, 605, 135)]
MASK_FILL = 4000
F_PAINT = 1921.0     # focal length (px) solved on the bridge view of the same sheet


def S(x, y):
    """sheet px -> crop px"""
    return (x - OX, y - OY)


PORTAL = [((165, 506), (-1.40, -0.15, 0.0)), ((188, 507), (-1.10, -0.15, 0.0)), ((188, 398), (-1.10, -0.15, 2.0)),
          ((316, 398), (1.10, -0.15, 2.0)), ((330, 398), (1.40, -0.15, 2.0)), ((316, 500), (1.10, -0.15, 0.0)),
          ((160, 377), (-1.62, -0.20, 2.38)), ((340, 377), (1.62, -0.20, 2.38))]

INSETS = {
    "mine_front": dict(box=(528, 308, 664, 398), dir=(0, 1, 0), fit="width", parts="outcrop"),
}
NO_PROJECT_TAGS = ("tunnel_side",)
TAG_SWATCH = {"block": "stone_face", "outcrop": "stone_face", "rail": "metal", "sleeper": "wood_h", "jib": "wood_h",
              "beam": "wood_h", "sill": "wood_h", "lintel": "wood_h", "joist": "wood_h", "drum_rope": "rope"}
SWATCHES = {
    "wood": dict(box=(650, 470, 668, 560), metres=0.8),
    "wood_h": dict(box=(650, 470, 668, 560), metres=0.8, rotate=True),
    "stone": dict(box=(150, 300, 240, 360), metres=1.6),
    "stone_face": dict(box=(300, 300, 380, 330), metres=1.2),
    "ground": dict(box=(440, 560, 520, 585), metres=2.0),
    "gravel": dict(box=(440, 560, 520, 585), metres=2.0),
    "grass": dict(box=(30, 520, 90, 560), metres=1.5),
    "rope": dict(box=(660, 520, 735, 560), metres=0.5),
    "metal": dict(box=(1430, 740, 1470, 800), metres=0.4),
    "cloth": dict(box=(1280, 718, 1386, 828), metres=1.2),
}
SWATCH_FALLBACK = {"rope": "wood", "roof": "stone", "glow": "metal", "water": "ground"}
CLASS_TRAIN = {
    "wood": [(330, 400, 345, 480), (165, 400, 185, 500), (476, 420, 488, 540), (430, 520, 560, 532), (650, 470, 668, 560)],
    "stone": [(110, 400, 230, 485), (300, 300, 380, 330), (200, 480, 310, 555), (150, 300, 240, 360)],
    "dark": [(210, 430, 300, 500)],
    "veg": [(180, 320, 230, 360), (120, 515, 160, 545), (360, 285, 400, 300)],
    "dirt": [(420, 560, 520, 585), (250, 560, 330, 580)],
}
ACCEPT = {"wood": {"wood", "dark"}, "stone": {"stone", "veg", "dark"}, "ground": {"dirt", "veg", "stone"},
          "metal": {"dark", "wood"}, "rope": {"wood"}, "cloth": set()}
CLASS_SWATCH = {"ground": {"veg": "grass", "dirt": "gravel", "stone": "gravel"}}
NORMAL_STRENGTH = {"stone": 3.0, "wood": 2.5, "ground": 1.5, "rope": 2.0}
EDGE_WIDTH_M = 0.035
EDGE_STRENGTH = {"stone": 0.6, "wood": 0.4}
TAG_RGB = {"tunnel": (0.07, 0.06, 0.05)}
MORTAR_RGB = (0.25, 0.23, 0.19)
POLY_JITTER = 0.03
CARD_KINDS = {"ivy_a": "ivy", "ivy_b": "ivy", "grass_a": "grass", "weed_a": "weed"}
_CAM = {}


def camera_points():
    P = [w for _, w in PORTAL]
    p = [S(*q) for q, _ in PORTAL]
    return np.array(P, float), np.array(p, float), dict(free_pp=True, pp_prior=0.08, f0=F_PAINT, fix_f=True,
                                                        init_centre=(-9.0, -38.0, 14.0), init_target=(0.5, 0.0, 1.5))


def attach(cam, crop, mask):
    _CAM.update(cam=cam, crop=crop, mask=mask)


def gp(cam, x, y, z=0.0):
    u, v = S(x, y)
    return ibm.ground_at(cam, u, v, None, z)


def mpx(cam, P, px):
    return ibm.metres(cam, P, px)


# ============================================================================ geometry
def build(lod, cam=None, crop=None, mask=None, cards=None):
    g = Geo(seed=3 + lod)
    _CARDS.clear()
    _CARDS.update(cards or {})
    _CARDS["__crop__"] = crop
    portal(g, lod)
    outcrop(g, lod, cam, mask)
    crane(g, lod, cam)
    blocks(g, lod, cam)
    rails(g, lod, cam)
    base = Geo(seed=9 + lod)
    if cam is not None and mask is not None:
        poly = ibm.footprint(cam, mask, lambda x, y: np.zeros_like(x), ylim=(-9.0, 1.2), xlim=(-7.5, 9.5))
        ibm.ground_patch(poly, lambda x, y: np.zeros_like(x) - 0.02, 0.8 if lod == 0 else (1.6 if lod == 1 else 3.2), g=base,
                         undulate=0.03)
        rocks = [(60, 560, 8), (125, 555, 7), (260, 560, 6), (430, 575, 7), (590, 545, 6), (515, 575, 6), (300, 575, 5),
                 (20, 500, 9), (590, 520, 6)]
        ibm.place_rocks(base, cam, [(S(u, v)[0], S(u, v)[1], r) for u, v, r in rocks][: (9 if lod == 0 else 4 if lod == 1 else 0)],
                        sub=1 if lod == 0 else 0, seed=40)
        if lod < 2 and cards:
            spots = [(140, 530, "grass_a", 22), (40, 510, "grass_a", 20), (330, 470, "weed_a", 18), (520, 560, "grass_a", 16),
                     (580, 540, "weed_a", 14), (250, 575, "grass_a", 12), (450, 495, "grass_a", 14)]
            spots = [(S(u, v)[0], S(u, v)[1], n, h) for u, v, n, h in spots][:: (1 if lod == 0 else 2)]
            ibm.place_cards(base, cam, spots, cards)
    return dict(struct=g, base=base)


def portal(g, lod):
    for sx in (-1, 1):
        x = sx * 1.25
        g.box((x, 0.0, 1.19), (0.3, 0.3, 2.38), None, "wood", "post", chamfer=0.03 if lod == 0 else 0, skip=("-z",))
        if lod < 2:
            g.beam((x - sx * 0.12, -0.05, 1.45), (x - sx * 0.75, -0.05, 1.98), 0.2, 0.2, mat="wood", tag="brace")
    g.beam((-1.62, -0.02, 2.19), (1.62, -0.02, 2.19), 0.34, 0.38, mat="wood", tag="lintel", chamfer=0.03 if lod == 0 else 0)
    nj = 6 if lod == 0 else (3 if lod == 1 else 0)
    for i in range(nj):
        x = -1.45 + 2.9 * i / max(1, nj - 1)
        g.beam((x, -0.38, 2.5), (x, 1.6, 2.5), 0.24, 0.24, mat="wood", tag="joist")
    if lod < 2:
        g.beam((-1.7, -0.25, 2.66), (1.7, -0.25, 2.66), 0.2, 0.1, mat="wood", tag="joist")
        # inner frame sets receding into the tunnel
        for yy in ((1.0, 2.0) if lod == 0 else (1.4,)):
            for sx in (-1, 1):
                g.box((sx * 1.05, yy, 1.0), (0.24, 0.24, 2.0), None, "wood", "frame", skip=("-z",))
            g.beam((-1.2, yy, 2.08), (1.2, yy, 2.08), 0.24, 0.26, mat="wood", tag="frame")
            if lod == 0:
                for sx in (-1, 1):
                    g.beam((sx * 0.95, yy, 1.5), (sx * 0.45, yy, 1.98), 0.16, 0.16, mat="wood", tag="frame")
    # tunnel: dark lining (floor, walls, ceiling, back)
    L, Wt, Ht = 3.2, 1.1, 2.0
    g.quad((-Wt, 0.15, Ht), (Wt, 0.15, Ht), (Wt, L, Ht), (-Wt, L, Ht), "stone", "tunnel_side")
    g.quad((-Wt, L, 0), (Wt, L, 0), (Wt, L, Ht), (-Wt, L, Ht), "stone", "tunnel")
    g.quad((-Wt, 0.15, 0), (-Wt, L, 0), (-Wt, L, Ht), (-Wt, 0.15, Ht), "stone", "tunnel_side")
    g.quad((Wt, L, 0), (Wt, 0.15, 0), (Wt, 0.15, Ht), (Wt, L, Ht), "stone", "tunnel_side")
    g.quad((-Wt, 0.15, 0.01), (Wt, 0.15, 0.01), (Wt, L, 0.01), (-Wt, L, 0.01), "stone", "tunnel_side")


def outcrop(g, lod, cam, mask):
    """Rounded limestone blocks at their painted positions: watershed segmentation of the painted outcrop on its
    dark joints; each segment becomes a rounded block (edge radius 0.1 m) on the outcrop front surface, sized from
    its painted extent; deeper rounded blocks behind give the mound its volume."""
    if cam is None:
        return
    from scipy import ndimage as ndi
    from skimage.feature import peak_local_max
    from skimage.segmentation import watershed
    import cv2 as _cv2
    crop = _CARDS.get("__crop__")
    H, W = mask.shape
    lab = _cv2.cvtColor(crop.astype(np.float32), _cv2.COLOR_RGB2LAB)[..., 0]
    region = mask.copy()
    region[:, S(376, 0)[0]:] = False
    region[S(0, 362)[1]:S(0, 520)[1], S(150, 0)[0]:S(346, 0)[0]] = False      # portal timbers + tunnel
    for (x0, x1, yt, yb) in BLOCKS:
        region[S(0, yt)[1]:S(0, yb)[1] + 1, S(x0, 0)[0]:S(x1, 0)[0] + 1] = False
    region[S(0, 512)[1]:, :] = False                                           # ground / rails
    blur = ndi.gaussian_filter(lab, 3.0)
    joints = (lab < blur - 6.0)
    solid = region & ~joints
    solid = ndi.binary_opening(solid, iterations=1)
    dist = ndi.distance_transform_edt(solid)
    peaks = peak_local_max(dist, min_distance=7, threshold_abs=2.5, labels=ndi.label(solid)[0])
    markers = np.zeros(mask.shape, np.int32)
    for i, (y, x) in enumerate(peaks):
        markers[y, x] = i + 1
    seg = watershed(-dist, markers, mask=region)
    rng = np.random.default_rng(17 + lod)
    y_front = 0.15
    blocks = []
    for lbl in range(1, seg.max() + 1):
        ys, xs = np.nonzero(seg == lbl)
        if len(xs) < 40:
            continue
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        cxp, cyp = (x0 + x1) / 2, (y0 + y1) / 2
        P = cam.on_plane(np.array([cxp + 0.5]), np.array([cyp + 0.5]), (0, y_front, 0), (0, 1, 0))[0]
        w = ibm.metres(cam, P, x1 - x0 + 3)
        h = ibm.metres(cam, P, y1 - y0 + 3)
        if P[2] - h / 2 < -0.2:
            continue
        blocks.append((P, w, h, len(xs)))
    blocks.sort(key=lambda b: -b[3])
    if lod == 1:
        blocks = blocks[: max(8, len(blocks) // 3)]
    if lod == 2:
        blocks = blocks[: 6]
    for k, (P, w, h, n) in enumerate(blocks):
        d = rng.uniform(0.7, 0.95)
        c = (P[0], y_front + d / 2 - 0.05 + rng.normal(0, 0.03), max(P[2], h / 2 - 0.05))
        if lod == 0:
            g.rounded_block(c, (w * 0.97, d, h * 0.97), 0.11, rot_z(rng.normal(0, 0.03)), mat="stone", tag="block",
                            skip=("+y", "-z"), seed=k, jitter=0.03)
        else:
            g.box(c, (w, d, h), rot_z(rng.normal(0, 0.03)), "stone", "block", skip=("-z", "+y"))
    OUT["n_blocks"] = len(blocks)
    # mound volume behind: rounded blocks stepping back and down (stay inside the painted silhouette)
    cols = np.arange(S(14, 0)[0], S(372, 0)[0], 4)
    prof_x, prof_z = [], []
    for c in cols:
        rows = np.nonzero(mask[:, c])[0]
        if len(rows) == 0:
            continue
        Pq = cam.on_plane(np.array([c + 0.5]), np.array([rows.min() + 0.5]), (0, y_front, 0), (0, 1, 0))[0]
        prof_x.append(Pq[0])
        prof_z.append(Pq[2])
    prof_x, prof_z = np.array(prof_x), np.array(prof_z)
    for li, (yb, drop) in enumerate([(0.95, 1.05), (1.75, 2.0), (2.55, 3.0)] if lod == 0 else ([(1.2, 1.4)] if lod == 1 else [])):
        x = prof_x.min()
        while x < prof_x.max() - 0.3:
            L = rng.uniform(0.9, 1.4) if lod == 0 else 1.8
            xm = x + L / 2
            top = np.interp(xm, prof_x, prof_z) - drop
            z = 0.0
            while z < top - 0.3:
                hh = min(0.65, top - z)
                c = (xm, yb + 0.4, z + hh / 2)
                g.box(c, (L - 0.05, 0.8, hh - 0.03), rot_z(rng.normal(0, 0.03)), "stone", "outcrop", skip=("-z", "+y"),
                      chamfer=0.0)
                z += 0.65
            x += L
    # ivy cards hanging on the front face where the painting shows ivy
    if lod < 2 and "ivy_a" in _CARDS:
        for k, (u, v, hpx) in enumerate([(120, 330, 90), (170, 320, 80), (90, 360, 70), (215, 300, 50), (60, 330, 50),
                                          (365, 310, 40), (140, 380, 60)][:: (1 if lod == 0 else 2)]):
            uu, vv = S(u, v)
            P = cam.on_plane(np.array([uu + 0.5]), np.array([vv + 0.5]), (0, -0.12, 0), (0, 1, 0))[0]
            h = mpx(cam, P, hpx)
            u0, v0, u1, v1, aw, ah = _CARDS["ivy_a" if k % 2 else "ivy_b"]
            top = P + np.array([0, -0.02, h * 0.15])
            g.add(np.array([top + (-h * 0.35, 0, -h), top + (h * 0.35, 0, -h), top + (h * 0.35, 0, 0), top + (-h * 0.35, 0, 0)]),
                  [[0, 1, 2, 3]], "card_ivy", "ivy", uv=[[(u0, v0), (u1, v0), (u1, v1), (u0, v1)]])


OUT = {}
BLOCKS = [(112, 236, 397, 490), (193, 318, 475, 560), (318, 403, 520, 582), (232, 302, 437, 482), (345, 380, 470, 505),
          (16, 110, 455, 528), (130, 190, 520, 560), (372, 430, 450, 492), (300, 345, 448, 498)]


_CARDS = {}
SOCK = {}


def crane(g, lod, cam):
    if cam is None:
        foot, fl, fr = np.array([3.6, -0.6, 0]), np.array([2.9, -0.9, 0]), np.array([5.2, -0.9, 0])
        H = 3.3
    else:
        foot = gp(cam, 482, 548)
        fl = gp(cam, 440, 552)
        fr = gp(cam, 556, 552)
        H = mpx(cam, foot, 548 - 378) * 1.05
    ex = fr - fl
    ex[2] = 0
    Lx = np.linalg.norm(ex)
    ex /= Lx
    ey = np.array([-ex[1], ex[0], 0.0])
    back = 1.2
    o = fl
    # base frame (sills) + legs
    for d in ((0.0, back) if lod < 2 else (0.0,)):
        g.beam(o + ey * d + np.array([0, 0, 0.45]), o + ex * Lx + ey * d + np.array([0, 0, 0.45]), 0.22, 0.22, mat="wood",
               tag="sill")
    for t in ((0.0, 1.0) if lod < 2 else ()):
        g.beam(o + ex * Lx * t + np.array([0, 0, 0.45]), o + ex * Lx * t + ey * back + np.array([0, 0, 0.45]), 0.2, 0.2,
               mat="wood", tag="sill")
        for d in (0.0, back):
            g.box(o + ex * Lx * t + ey * d + np.array([0, 0, 0.22]), (0.2, 0.2, 0.44), rot_z(math.atan2(ex[1], ex[0])),
                  "wood", "leg", skip=("-z",))
    # mast + jib + strut + back leg: painted points back-projected onto the crane's vertical plane
    m0 = foot + ey * 0.35
    if cam is not None:
        def cp(x, y):
            u, v = S(x, y)
            return cam.on_plane(np.array([u + 0.5]), np.array([v + 0.5]), m0, ey)[0]
        m1 = cp(482, 380)
        m1 = np.array([m0[0], m0[1], m1[2]])
        tip = cp(386, 346)
        root = cp(497, 404)
        strut_lo = cp(470, 466)
        strut_hi = cp(408, 360)
    else:
        m1 = m0 + np.array([0, 0, H])
        tip = m1 + np.array([-2.0, 0, 0.6])
        root, strut_lo, strut_hi = m1 + ex * 0.2, m0 + np.array([0, 0, 1.2]), tip * 0.8 + m1 * 0.2
    H = m1[2] - m0[2]
    g.box((m0 + m1) / 2, (0.26, 0.26, H), rot_z(math.atan2(ex[1], ex[0])), "wood", "mast", skip=("-z",))
    g.beam(root, tip, 0.2, 0.22, mat="wood", tag="jib")
    g.beam(strut_lo, strut_hi, 0.18, 0.18, mat="wood", tag="beam")
    g.beam(m1 - np.array([0, 0, 0.2]), m0 + ey * 1.1 + np.array([0, 0, 0.45]), 0.18, 0.18, mat="wood", tag="beam")
    g.beam(m0 + np.array([0, 0, 0.45]), m0 - ex * 0.9 + np.array([0, 0, 0.45]) + np.array([0, 0, 1.4]) * 0, 0.16, 0.16,
           mat="wood", tag="beam")
    # winch: two A-frame cheeks, drum with rope, crank
    wc = o + ex * (Lx * 0.72) + ey * 0.6 + np.array([0, 0, 0.45])
    if lod == 2:
        g.cyl(wc - ex * 0.46 + np.array([0, 0, 0.6]), wc + ex * 0.46 + np.array([0, 0, 0.6]), 0.36, n=5, mat="rope", tag="drum_rope")
        return
    for s in (-0.5, 0.5):
        p = wc + ex * s
        g.beam(p - ey * 0.45, p + np.array([0, 0, 0.62]), 0.14, 0.14, mat="wood", tag="cheek")
        g.beam(p + ey * 0.45, p + np.array([0, 0, 0.62]), 0.14, 0.14, mat="wood", tag="cheek")
    axle0 = wc - ex * 0.62 + np.array([0, 0, 0.6])
    axle1 = wc + ex * 0.62 + np.array([0, 0, 0.6])
    g.cyl(wc - ex * 0.42 + np.array([0, 0, 0.6]), wc + ex * 0.42 + np.array([0, 0, 0.6]), 0.3, n=12 if lod == 0 else 6,
          mat="rope", tag="drum_rope")
    for s in (-0.46, 0.46):
        g.cyl(wc + ex * (s - 0.04) + np.array([0, 0, 0.6]), wc + ex * (s + 0.04) + np.array([0, 0, 0.6]), 0.38,
              n=12 if lod == 0 else 6, mat="wood", tag="drum_flange")
    g.cyl(axle0, axle1, 0.05, n=6, mat="metal", tag="axle")
    if lod == 0:
        SOCK["winch_axle"] = ((axle0 + axle1) / 2).tolist()
    if lod == 0:
        g.beam(axle1, axle1 + np.array([0, 0, -0.35]) + ey * 0.1, 0.06, 0.06, mat="metal", tag="crank")
    # rope from drum to the jib tip, hanging chains + pulley + block in a sling
    g.tube([wc + np.array([0, 0, 0.9]), m1 - np.array([0, 0, 0.35]), tip], 0.025, n=4, mat="rope", tag="rope")
    hang = 0.95 if cam is None else mpx(cam, foot, 448 - 345) * 0.95
    pul = tip - np.array([0, 0, hang * 0.55])
    if cam is not None:
        pul = cp(392, 410)
        pul[0], pul[1] = tip[0], tip[1]
    if lod == 0:
        SOCK["jib_tip"] = tip.tolist()
    g.tube([tip, pul], 0.02, n=4, mat="metal", tag="chain")
    g.cyl(pul - ey * 0.05, pul + ey * 0.05, 0.11, n=8, mat="metal", tag="pulley")
    bs = 0.85 if cam is None else mpx(cam, foot, 58)
    bc = pul - np.array([0, 0, hang * 0.45 + bs * 0.45])
    if cam is not None:
        bc = cp(396, 465)
        bc[0], bc[1] = tip[0], tip[1]
    g.box(bc, (bs, bs * 0.9, bs * 0.7), rot_z(0.2), "stone", "hblock")
    for sx in (-1, 1):
        g.tube([pul, bc + np.array([sx * bs * 0.5, 0, bs * 0.35]), bc + np.array([sx * bs * 0.52, 0, -bs * 0.36])], 0.018,
               n=4, mat="rope", tag="sling")


def blocks(g, lod, cam):
    spec = list(BLOCKS)
    if lod == 1:
        spec = spec[:6]
    if lod == 2:
        spec = spec[:2]
    rng = np.random.default_rng(5)
    for k, (x0, x1, yt, yb) in enumerate(spec):
        if cam is None:
            continue
        P = gp(cam, (x0 + x1) / 2, yb)
        w = mpx(cam, P, (x1 - x0)) * 0.8
        h = mpx(cam, P, (yb - yt)) * 0.75
        if lod == 0:
            g.rounded_block((P[0], P[1] + w * 0.35, h / 2), (w, w * 0.8, h), 0.1, rot_z(rng.uniform(-0.4, 0.4)), mat="stone",
                            tag=f"cut{k}", skip=("-z",), seed=200 + k, jitter=0.03)
        else:
            g.box((P[0], P[1] + w * 0.35, h / 2), (w, w * 0.8, h), rot_z(rng.uniform(-0.4, 0.4)), "stone", f"cut{k}", skip=("-z",))
    # crate next to the crane
    if cam is not None:
        P = gp(cam, 404, 556)
        w = mpx(cam, P, 52)
        g.box((P[0], P[1] + w * 0.4, w * 0.4), (w, w * 0.8, w * 0.8), rot_z(0.15), "wood", "crate", skip=("-z",))
        if lod == 0:
            for dz in (0.2, 0.6):
                g.box((P[0], P[1] + w * 0.4 - w * 0.41, w * 0.8 * dz), (w * 1.02, 0.03, 0.06), rot_z(0.15), "wood", "crate_band")


def rails(g, lod, cam):
    if cam is None:
        return
    a = gp(cam, 335, 575)
    b = gp(cam, 400, 573)
    near_c = (a + b) / 2
    start_c = np.array([-0.32, -0.1, 0.0])
    d = near_c - start_c
    d[2] = 0
    Lr = np.linalg.norm(d)
    d /= Lr
    n = np.array([-d[1], d[0], 0])
    for s in (-0.3, 0.3):
        g.beam(start_c + n * s + np.array([0, 0, 0.1]), near_c + n * s + np.array([0, 0, 0.1]), 0.06, 0.08, mat="metal",
               tag="rail")
        g.beam(np.array([-0.32 + s, 2.9, 0.1]), start_c + np.array([s, 0, 0.1]), 0.06, 0.08, mat="metal", tag="rail")
    ns = int(Lr / 0.55) if lod == 0 else (int(Lr / 1.1) if lod == 1 else 0)
    for i in range(ns):
        c = start_c + d * (0.3 + i * Lr / max(ns, 1)) + np.array([0, 0, 0.04])
        g.box(c, (0.95, 0.18, 0.08), rot_z(math.atan2(d[1], d[0]) + math.pi / 2), "wood", "sleeper", skip=("-z",))


def colliders():
    return [dict(type="box", centre=(-1.2, 1.6, 2.0), size=(7.6, 3.4, 4.0)),
            dict(type="box", centre=(-1.25, -0.0, 1.2), size=(0.32, 0.32, 2.4)),
            dict(type="box", centre=(1.25, -0.0, 1.2), size=(0.32, 0.32, 2.4)),
            dict(type="box", centre=(4.2, -0.5, 1.6), size=(2.6, 1.6, 3.2))]


def meta_extra():
    gl = lambda p: [round(p[0], 3), round(p[2], 3), round(-p[1], 3)]
    return dict(sockets={"mine_entrance_centre": [0.0, 0.0, 0.15], "winch_axle": gl(SOCK.get("winch_axle", (4, 0, 1))),
                         "jib_tip": gl(SOCK.get("jib_tip", (2, 0, 4)))},
                dimensions={"portal_clear_m": [2.2, 2.0], "rail_gauge_m": 0.6},
                notes="crane, blocks, crate and rails are placed by back-projecting their painted ground contacts (v3 camera json)")
