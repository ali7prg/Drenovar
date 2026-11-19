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
MASK_EXCLUDE = [(0, 0, 60, 40), (420, 0, 480, 40), (462, 0, 480, 165), (0, 0, 70, 30)]
F_PAINT = 1921.0
TER_H = 1.8
TER_Y = -2.0          # terrace front face
ARCH = dict(x0=-0.5, x1=0.5, spring=TER_H + 1.85, y=0.0, t=0.85)

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
    "ground": dict(ground_px=(1000, 556), metres=1.6),
    "gravel": dict(ground_px=(1000, 556), metres=1.6),
    "grass": dict(box=(800, 530, 850, 560), metres=1.2),
}
SWATCH_FALLBACK = {"wood": "stone", "metal": "stone", "rope": "stone", "cloth": "stone", "glow": "stone", "water": "ground"}
CLASS_TRAIN = {
    "stone": [(1010, 350, 1060, 420), (930, 300, 970, 360), (1100, 460, 1180, 500), (1365, 418, 1495, 485)],
    "veg": [(840, 380, 880, 440), (800, 530, 840, 560), (1110, 540, 1150, 560)],
    "dirt": [(880, 550, 960, 570)],
}
ACCEPT = {"stone": {"stone", "veg"}, "ground": {"dirt", "veg", "stone"}}
CLASS_SWATCH = {"ground": {"veg": "ground", "dirt": "ground", "stone": "gravel"}}
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


def _vline_height(cam, foot, px):
    o, d = cam.ray(np.array([px[0] + 0.5]), np.array([px[1] + 0.5]))
    d = d[0]
    t = ((foot[:2] - o[:2]) @ d[:2]) / max(d[:2] @ d[:2], 1e-9)
    return float(o[2] + t * d[2])


def column_wall(g, cam, mask, foot_line, foot_z, x0s, x1s, lod, tag, rng, thickness=0.9, course=0.38, block=(0.4, 0.75),
                z_cap=None, step=3):
    """Masonry wall following the painted foot line (sheet px polyline on plane z=foot_z); per image column the
    solid runs of the painted mask above the foot give the wall's height intervals (gaps = arch openings)."""
    fx = np.array([q[0] for q in foot_line], float)
    fy = np.array([q[1] for q in foot_line], float)
    cols = np.arange(x0s, x1s, step)
    F, runs = [], []
    for c in cols:
        yf = float(np.interp(c, fx, fy))
        u, v = S(c, yf)
        if not (0 <= int(u) < mask.shape[1]):
            continue
        Pf = cam.on_plane_z(np.array([u + 0.5]), np.array([v + 0.5]), foot_z)[0]
        col = mask[: max(1, int(v)), int(u)]
        rr = []
        y = 0
        n = len(col)
        while y < n:
            if col[y]:
                y2 = y
                while y2 < n and col[y2]:
                    y2 += 1
                ztop = _vline_height(cam, Pf, (u, y))
                zbot = _vline_height(cam, Pf, (u, y2)) if y2 < n - 2 else foot_z
                rr.append((max(zbot, foot_z), ztop))
                y = y2
            else:
                y += 1
        F.append(Pf)
        runs.append(rr)
    if len(F) < 2:
        return
    F = np.array(F)
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(F[:, :2], axis=0), axis=1))]
    total = seg[-1]
    ch = course if lod == 0 else (0.75 if lod == 1 else 1.5)
    zmax = max((r[1] for rr in runs for r in rr), default=foot_z)
    if z_cap is not None:
        zmax = min(zmax, z_cap)
    z = foot_z
    ci = 0
    cam_c = cam.centre
    while z < zmax - 0.05:
        sdist = -(rng.uniform(0, block[0]) if ci % 2 else 0.0)
        while sdist < total - 0.02:
            L = rng.uniform(*block) if lod == 0 else (1.2 if lod == 1 else 2.4)
            a, b = max(sdist, 0.0), min(sdist + L, total)
            sdist += L
            if b - a < 0.12:
                continue
            sm = (a + b) / 2
            k = int(np.clip(np.searchsorted(seg, sm), 1, len(seg) - 1))
            zc = z + ch / 2
            ok = any(lo - 0.05 <= zc <= hi + 0.02 for (lo, hi) in runs[k]) if runs[k] else False
            if not ok:
                continue
            top_here = max((hi for (lo, hi) in runs[k] if lo - 0.05 <= zc), default=z)
            hh = ch if top_here - z >= ch * 0.7 else max(0.18, top_here - z)
            if z_cap is not None:
                hh = min(hh, z_cap - z)
            if hh < 0.1:
                continue
            pa = F[k - 1] + (F[k] - F[k - 1]) * 0.5
            dirv = F[min(k + 1, len(F) - 1)] - F[max(k - 2, 0)]
            dirv[2] = 0
            dirv /= max(np.linalg.norm(dirv), 1e-6)
            nrm = np.array([-dirv[1], dirv[0], 0.0])
            if (cam_c - pa) @ nrm < 0:
                nrm = -nrm
            # position along the foot polyline at arc length sm
            j = int(np.clip(np.searchsorted(seg, sm) - 1, 0, len(seg) - 2))
            tt = (sm - seg[j]) / max(seg[j + 1] - seg[j], 1e-6)
            base = F[j] + (F[j + 1] - F[j]) * tt
            c = base - nrm * thickness / 2 + np.array([0, 0, z - foot_z + hh / 2])
            c[2] = z + hh / 2
            yaw = math.atan2(dirv[1], dirv[0])
            g.box(c, (b - a - 0.035, thickness - rng.uniform(0, 0.05), hh - 0.035), rot_z(yaw + rng.normal(0, 0.01)),
                  "stone", tag, skip=("-z",))
        z += ch
        ci += 1


def build(lod, cam=None, crop=None, mask=None, cards=None):
    g = Geo(seed=61 + lod)
    rng = np.random.default_rng(13 + lod)
    if cam is None:
        return dict(struct=g, base=Geo())
    # terrace height from its painted front face (foot 535, top 446 on the same vertical line)
    u, v = S(960, 535)
    Tf = cam.on_plane_z(np.array([u + 0.5]), np.array([v + 0.5]), 0.0)[0]
    th = float(np.clip(_vline_height(cam, Tf, S(960, 446)), 1.0, 2.6))
    TER["h"] = th
    # terrace front wall (flat top at th), then the gate wall with the arch standing on the terrace top
    column_wall(g, cam, mask, [(905, 535), (1092, 533)], 0.0, 905, 1092, lod, "terrace", rng, thickness=2.2, course=0.45,
                z_cap=th)
    if lod < 2:   # paving slabs on the terrace top
        top_c = cam.on_plane_z(np.array([S(1000, 452)[0] + .5]), np.array([S(1000, 452)[1] + .5]), th)[0]
        g.box((top_c[0], top_c[1] + 0.4, th + 0.04), (4.2, 2.0, 0.08), rot_z(0.0), "stone", "pave", skip=("-z",))
    column_wall(g, cam, mask, [(922, 444), (1080, 440)], th, 922, 1080, lod, "wall", rng, thickness=0.95)
    # left wall section receding diagonally (foot on the ground)
    column_wall(g, cam, mask, [(826, 524), (925, 532)], 0.0, 826, 924, lod, "wall", rng, thickness=1.0)
    # low broken wall on the terrace (right)
    column_wall(g, cam, mask, [(1082, 446), (1166, 450)], th, 1082, 1166, lod, "stub", rng, thickness=0.7, z_cap=th + 1.6)
    # stair: 9 stone steps from the terrace edge down to the ground at the front right
    top = cam.on_plane_z(np.array([S(1092, 447)[0] + .5]), np.array([S(1092, 447)[1] + .5]), th)[0]
    bot = cam.on_plane_z(np.array([S(1232, 560)[0] + .5]), np.array([S(1232, 560)[1] + .5]), 0.0)[0]
    run = bot - top
    run[2] = 0
    Lr = np.linalg.norm(run)
    rd = run / max(Lr, 1e-6)
    side = np.array([-rd[1], rd[0], 0.0])
    if (cam.centre - top) @ side > 0:
        side = -side            # steps extend away from the camera (visible end faces the viewer)
    nst = 9 if lod < 2 else 3
    width = 1.9
    for k in range(nst):
        zt = th * (1 - k / nst)
        zb = th * (1 - (k + 1) / nst)
        c = top + rd * (Lr * (k + 0.5) / nst) + side * (width / 2)
        hgt = zt if lod < 2 else zt
        g.box((c[0], c[1], hgt / 2), (Lr / nst + 0.03, width - 0.08 * (k % 2), hgt), rot_z(math.atan2(rd[1], rd[0]) + rng.normal(0, 0.01)),
              "stone", "stair", skip=("-z",))
    TER["stair"] = (top, bot)
    # ivy cards on the walls where the painting shows ivy
    if lod < 2 and cards and "ivy_a" in cards:
        for k, (u0p, v0p, hpx) in enumerate([(845, 395, 90), (880, 380, 70), (945, 345, 80), (1050, 300, 50), (905, 420, 60)][:: (1 if lod == 0 else 2)]):
            uu, vv = S(u0p, v0p)
            P = cam.on_plane_z(np.array([uu + 0.5]), np.array([vv + 0.5]), th + 1.0)[0]
            # grazing rays near the wall top can land far behind the ruin: keep ivy on the structure
            P[0] = float(np.clip(P[0], -4.5, 6.5))
            P[1] = float(np.clip(P[1], -4.5, 1.5))
            h = ibm.metres(cam, P, hpx)
            u0, v0, u1, v1, aw, ah = cards["ivy_a" if k % 2 else "ivy_b"]
            d = cam.centre - P
            d[2] = 0
            d /= np.linalg.norm(d)
            r = np.array([-d[1], d[0], 0.0])
            topp = P + d * 0.55
            g.add(np.array([topp - r * h * 0.3 - [0, 0, h], topp + r * h * 0.3 - [0, 0, h], topp + r * h * 0.3, topp - r * h * 0.3]),
                  [[0, 1, 2, 3]], "card_ivy", "ivy", uv=[[(u0, v0), (u1, v0), (u1, v1), (u0, v1)]])
    base = Geo(seed=9 + lod)
    # the painted outline's top edge back-projects towards the horizon: bound the base to the ruin's surroundings
    poly = ibm.footprint(cam, mask, lambda x, y: np.zeros_like(x), ylim=(-7.0, 2.5), xlim=(-6.5, 8.5))
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


TER = {}


def colliders():
    th = TER.get("h", TER_H)
    C = [dict(type="box", centre=(0.0, 0.0, th / 2), size=(4.4, 2.4, th)),
         dict(type="box", centre=(0.0, 0.6, th + 1.8), size=(4.0, 1.0, 3.6))]
    if "stair" in TER:
        t, b = TER["stair"]
        c = (t + b) / 2
        C.append(dict(type="ramp", centre=(c[0], c[1], th / 2), size=(float(np.linalg.norm((b - t)[:2])), 1.9, th),
                      yaw=math.atan2(b[1] - t[1], b[0] - t[0])))
    return C


def meta_extra():
    th = TER.get("h", TER_H)
    t, b = TER.get("stair", (np.zeros(3), np.zeros(3)))
    gl = lambda p: [round(float(p[0]), 3), round(float(p[2]), 3), round(float(-p[1]), 3)]
    return dict(dimensions={"terrace_height_m": round(th, 2), "stair": f"9 steps, riser {th / 9:.2f} m",
                            "construction": "walls follow the painted foot lines (back-projected); per image column the painted solid runs give the wall heights and the arch opening"},
                sockets={"stair_top": gl(t), "stair_foot": gl(b)})
