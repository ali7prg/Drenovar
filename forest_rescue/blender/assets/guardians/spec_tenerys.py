"""TENERYS — lean striped lynx-wolf predator (art/09_tenerys_guardian_direction.png).

All landmark numbers are pixel coordinates on the 1536x1024 sheet, measured on grid overlays
of the side view (head to image-left => "left" view, camera at +X).  Scale: nose->tail tip
884 px == 5.0 m (keeps the original TENERYS footprint, 5.26 m) -> 176.8 px/m.
"""
import math

import numpy as np

import gref
import grig
from gbody import Part, loft, stretch
from frlib import sdf

ID = "lf_guardian_tenerys"
SPECIES = "tenerys"
PPM = 176.8
GROUND = 372
CX = 385.0          # sheet column of the world origin (between fore and hind feet)


def S(x, y, lat=0.0):
    """Side-view sheet pixel -> world (Blender: -Y forward, Z up), lateral X in metres."""
    return np.array([lat, (x - CX) / PPM, (GROUND - y) / PPM])


def shadow_fn(row0):
    def fn(m, img):
        bg = np.median(img[:4].reshape(-1, 3), axis=0)
        d = img - bg
        luma = d @ np.array([0.299, 0.587, 0.114])
        ch = np.sqrt(((d - luma[..., None]) ** 2).sum(2))
        sh = (ch < 0.024) & (luma > -0.47) & (luma < -0.02)
        sh[:row0] = False
        m = m & ~sh
        from scipy import ndimage as ndi
        m = ndi.binary_opening(m, iterations=1)
        lab, n = ndi.label(m)
        if n:
            sizes = ndi.sum(m, lab, range(1, n + 1))
            m = lab == (int(np.argmax(sizes)) + 1)
        return m
    return fn


def panels():
    side = gref.Panel("side", "09", (18, 0, 916, 378), "left", PPM, GROUND, CX, thresh=0.09,
                      clip_below=375, extra_mask_fn=shadow_fn(352))
    front = gref.Panel("front", "09", (918, 0, 1196, 378), "front", PPM, GROUND, 1043.5, thresh=0.09,
                       clip_below=375, extra_mask_fn=shadow_fn(352))
    rear = gref.Panel("rear", "09", (1240, 0, 1515, 378), "rear", PPM, GROUND, 1377.0, thresh=0.09,
                      clip_below=375, extra_mask_fn=shadow_fn(352))
    return {"side": side, "front": front, "rear": rear}


# --------------------------------------------------------------------------- skeleton

def skeleton():
    up, fwd, lat = (0, 0, 1), (0, -1, 0), (1, 0, 0)
    B = []

    def bone(name, head, tail, parent, z=up, deform=True):
        B.append(dict(name=name, head=np.asarray(head, float), tail=np.asarray(tail, float),
                      parent=parent, z=z, deform=deform))

    LS = S(545, 92)
    TB = S(600, 112)
    TL = S(440, 100)
    T8 = S(330, 115)
    C7 = S(225, 130)
    MN = S(165, 125)
    AT = S(118, 118)
    bone("root", (0, 0, 0), (0, -0.4, 0), None, up)
    bone("hips", LS, TB, "root", up)
    bone("spine_01", LS, TL, "hips", up)
    bone("spine_02", TL, T8, "spine_01", up)
    bone("spine_03", T8, C7, "spine_02", up)
    bone("neck_01", C7, MN, "spine_03", up)
    bone("neck_02", MN, AT, "neck_01", up)
    bone("head", AT, S(40, 150), "neck_02", up)
    bone("jaw", S(110, 160), S(45, 182), "head", (0, 0, -1))
    for s, sx in (("L", 1), ("R", -1)):
        bone(f"ear_{s}", S(120, 98, 0.20 * sx), S(101, 46, 0.355 * sx), "head", fwd)
    bone("mane_01", S(132, 96), S(152, 40), "neck_02", fwd)
    bone("mane_02", S(190, 104), S(214, 30), "neck_01", fwd)
    bone("mane_03", S(262, 104), S(292, 38), "spine_03", fwd)
    tail_pts = [TB, S(640, 135), S(690, 178), S(740, 230), S(790, 265), S(845, 276), S(905, 250)]
    prev = "hips"
    for i in range(6):
        bone(f"tail_{i + 1:02d}", tail_pts[i], tail_pts[i + 1], prev, up)
        prev = f"tail_{i + 1:02d}"
    for s, sx in (("L", 1), ("R", -1)):
        bone(f"scapula_{s}", S(255, 100, 0.16 * sx), S(215, 175, 0.31 * sx), "spine_03", fwd)
        bone(f"upperarm_{s}", S(215, 175, 0.31 * sx), S(262, 240, 0.33 * sx), f"scapula_{s}", fwd)
        bone(f"forearm_{s}", S(262, 240, 0.33 * sx), S(258, 322, 0.335 * sx), f"upperarm_{s}", fwd)
        bone(f"hand_{s}", S(258, 322, 0.335 * sx), S(243, 352, 0.34 * sx), f"forearm_{s}", fwd)
        bone(f"fingers_{s}", S(243, 352, 0.34 * sx), S(190, 360, 0.345 * sx), f"hand_{s}", up)
        bone(f"thigh_{s}", S(575, 125, 0.26 * sx), S(548, 218, 0.35 * sx), "hips", fwd)
        bone(f"shin_{s}", S(548, 218, 0.35 * sx), S(630, 268, 0.37 * sx), f"thigh_{s}", fwd)
        bone(f"foot_{s}", S(630, 268, 0.375 * sx), S(612, 350, 0.40 * sx), f"shin_{s}", fwd)
        bone(f"toes_{s}", S(612, 350, 0.40 * sx), S(560, 359, 0.405 * sx), f"foot_{s}", up)
    return grig.Skeleton(B)


LEGS = {
    "fore_L": ["scapula_L", "upperarm_L", "forearm_L", "hand_L", "fingers_L"],
    "fore_R": ["scapula_R", "upperarm_R", "forearm_R", "hand_R", "fingers_R"],
    "hind_L": [None, "thigh_L", "shin_L", "foot_L", "toes_L"],
    "hind_R": [None, "thigh_R", "shin_R", "foot_R", "toes_R"],
}


# --------------------------------------------------------------------------- body SDF parts

def body_parts(sk):
    P = []
    # torso + neck loft (skin under the fur), sheet x -> (top y, bottom y, half-width m)
    prof = [
        (106, 104, 176, 0.15), (120, 102, 178, 0.21), (150, 105, 186, 0.26), (190, 109, 202, 0.30),
        (230, 110, 220, 0.30), (280, 106, 232, 0.32), (330, 100, 233, 0.315), (380, 93, 224, 0.30),
        (420, 86, 203, 0.28), (460, 80, 188, 0.27), (500, 76, 178, 0.285), (540, 73, 170, 0.30),
        (570, 76, 170, 0.29), (596, 88, 172, 0.25), (614, 102, 176, 0.18), (626, 116, 172, 0.09),
        (630, 128, 164, 0.03)]
    Y = [(x - CX) / PPM for x, *_ in prof]
    zt = [(GROUND - t) / PPM for _, t, b, w in prof]
    zb = [(GROUND - b) / PPM for _, t, b, w in prof]
    w = [w for *_, w in prof]
    P.append(Part(loft(Y, zt, zb, w, bone="spine_02"), "spine_02", k=0.0, tag="torso"))

    # ---- head
    head = "head"
    P.append(Part(sdf.ellipsoid(S(95, 116), (0.21, 0.17, 0.16)), head, k=0.06, tag="cranium"))
    P.append(Part(sdf.ellipsoid(S(72, 114), (0.16, 0.11, 0.115)), head, k=0.05, tag="brow"))
    P.append(Part(sdf.ellipsoid(S(54, 128), (0.10, 0.09, 0.105)), head, k=0.05, tag="nasalbridge"))
    for sx in (1, -1):
        P.append(Part(sdf.ellipsoid(S(92, 146, 0.11 * sx), (0.12, 0.13, 0.12)), head, k=0.05, tag="cheek"))
        P.append(Part(sdf.ellipsoid(S(66, 118, 0.085 * sx), (0.06, 0.06, 0.045)), head, k=0.03, tag="browridge"))
    P.append(Part(sdf.round_cone(S(80, 142), S(38, 157), 0.115, 0.075), head, k=0.05, tag="muzzle"))
    P.append(Part(sdf.ellipsoid(S(31, 156), (0.055, 0.04, 0.042)), head, k=0.02, tag="nose"))
    P.append(Part(sdf.round_cone(S(112, 158), S(46, 179), 0.075, 0.048), "jaw", k=0.03, tag="jaw"))
    # mouth slit (upper lip / jaw separation) and eye sockets
    mouth = sdf.box(S(64, 171), (0.15, 0.115, 0.0065), rot=(math.radians(-8), 0, 0), rounding=0.005)
    P.append(Part(mouth, head, k=0.008, op="subtract", tag="mouth"))
    for sx in (1, -1):
        P.append(Part(sdf.ellipsoid(S(40, 163, 0.052 * sx), (0.055, 0.06, 0.045)), head, k=0.03, tag="whiskerpad"))
    for sx in (1, -1):
        P.append(Part(sdf.ellipsoid(S(66, 129, 0.118 * sx), (0.034, 0.042, 0.027)), head, k=0.012, op="subtract",
                      tag="eyesocket"))
    # ears: big lynx ears (flattened cones facing forward)
    for s, sx in (("L", 1), ("R", -1)):
        b = sk.head(f"ear_{s}")
        t = sk.tail(f"ear_{s}")
        P.append(Part(sdf.flat_capsule(b + np.array([0, -0.03, 0]), t, 0.13, 0.022, 0.40, up=(0, 1, 0)), f"ear_{s}",
                      k=0.035, tag="ear"))
    # light cheek / throat ruff volume (lynx facial ruff)
    for sx in (1, -1):
        P.append(Part(sdf.ellipsoid(S(108, 152, 0.19 * sx), (0.14, 0.15, 0.14)), head, k=0.06, tag="ruffvol"))
        P.append(Part(sdf.ellipsoid(S(140, 166, 0.15 * sx), (0.14, 0.13, 0.11)), "neck_02", k=0.06, tag="ruffvol"))
    P.append(Part(sdf.ellipsoid(S(172, 194, 0.0), (0.18, 0.13, 0.11)), "neck_01", k=0.07, tag="ruffvol"))
    # dark mane ridge along the dorsal neck (spikes grow from it)
    ridge = [(98, 86, 0.065, "neck_02"), (140, 78, 0.095, "neck_02"), (190, 72, 0.115, "neck_01"),
             (250, 74, 0.12, "spine_03"), (320, 80, 0.105, "spine_03"), (400, 80, 0.075, "spine_02"),
             (470, 74, 0.05, "spine_01")]
    for (x0, y0, r0, b0), (x1, y1, r1, b1) in zip(ridge[:-1], ridge[1:]):
        P.append(Part(sdf.round_cone(S(x0, y0), S(x1, y1), r0, r1), b0, k=0.05, tag="maneridge"))

    # ---- legs (thick, furred; lateral radii measured on the front/rear views)
    for s, sx in (("L", 1), ("R", -1)):
        sc, ua, fa, ha, fi = LEGS[f"fore_{s}"]
        Sj, E, Wr, M = sk.head(ua), sk.head(fa), sk.head(ha), sk.head(fi)
        T = sk.tail(fi)
        P.append(Part(sdf.ellipsoid(S(240, 160, 0.31 * sx), (0.20, 0.23, 0.29)), sc, k=0.08, tag="shoulder"))
        P.append(Part(sdf.ellipsoid(S(258, 205, 0.33 * sx), (0.19, 0.16, 0.19)), ua, k=0.07, tag="triceps"))
        P.append(Part(stretch(sdf.round_cone(Sj, E, 0.125, 0.115), 1.2, center=Sj), ua, k=0.05, tag="upperarm"))
        Mid = E + (Wr - E) * 0.45
        P.append(Part(stretch(sdf.round_cone(E, Mid, 0.145, 0.135), 1.08, center=E), fa, k=0.05, tag="forearm"))
        P.append(Part(stretch(sdf.round_cone(Mid, Wr, 0.135, 0.125), 1.32, center=Wr), fa, k=0.05, tag="forearm"))
        P.append(Part(sdf.ellipsoid(E + (Wr - E) * 0.22 + np.array([0, 0.01, 0]), (0.15, 0.15, 0.17)), fa, k=0.06,
                      tag="forearm_m"))
        P.append(Part(stretch(sdf.round_cone(Wr, M, 0.12, 0.115), 1.32, center=Wr), ha, k=0.04, tag="hand"))
        _paw(P, M, T, fi, sx, scale=1.0, latf=1.2)
        th, sh, ft, to = LEGS[f"hind_{s}"][1:]
        H, K, Hk, Mt = sk.head(th), sk.head(sh), sk.head(ft), sk.head(to)
        Tt = sk.tail(to)
        P.append(Part(sdf.ellipsoid(S(566, 158, 0.28 * sx), (0.20, 0.30, 0.33), rot=(math.radians(18), 0, 0)), th,
                      k=0.09, tag="thigh_m"))
        P.append(Part(sdf.ellipsoid(S(596, 200, 0.27 * sx), (0.15, 0.14, 0.22)), th, k=0.07, tag="hamstring"))
        P.append(Part(sdf.round_cone(H, K, 0.15, 0.13), th, k=0.06, tag="thigh"))
        P.append(Part(stretch(sdf.round_cone(K, Hk, 0.15, 0.12), 0.85, center=K), sh, k=0.05, tag="shin"))
        P.append(Part(sdf.ellipsoid(K + (Hk - K) * 0.28, (0.12, 0.15, 0.13)), sh, k=0.06, tag="gaskin"))
        P.append(Part(stretch(sdf.round_cone(Hk, Mt, 0.125, 0.12), 0.95, center=Hk), ft, k=0.04, tag="metatarsus"))
        _paw(P, Mt, Tt, to, sx, scale=0.92, latf=1.15)
    # ---- tail core
    tb = ["hips"] + [f"tail_{i:02d}" for i in range(1, 7)]
    for i in range(1, 7):
        n = f"tail_{i:02d}"
        r0 = 0.115 - 0.010 * (i - 1)
        P.append(Part(sdf.round_cone(sk.head(n), sk.tail(n), r0, r0 - 0.010), n, k=0.04, tag="tail"))
    return P


TOES = list(enumerate(((-0.155, 0.15), (-0.058, 0.225), (0.058, 0.225), (0.155, 0.15))))


def _paw(P, M, T, bone, sx, scale=1.0, latf=1.0):
    """Felid paw: pad mass + 4 toes in an arc + metacarpal pad (ground at z=0)."""
    fwd = T - M
    fwd[2] = 0
    fwd /= np.linalg.norm(fwd)
    lat = np.array([1.0, 0, 0])
    c = np.array([M[0], M[1], 0.0]) + fwd * 0.05 * scale
    P.append(Part(sdf.ellipsoid(c + fwd * 0.03 + np.array([0, 0, 0.09 * scale]), (0.19 * scale * latf, 0.24 * scale, 0.095 * scale)),
                  bone, k=0.05, tag="paw"))
    for j, (ox, of) in TOES:
        p = c + (np.array([1.0, 0, 0]) * ox * sx * latf + fwd * of) * scale + np.array([0, 0, 0.055 * scale])
        P.append(Part(sdf.ellipsoid(p, (0.062 * scale, 0.08 * scale, 0.062 * scale)), bone, k=0.03, tag="toe"))


def toe_tips(sk, side, hind=False, scale=1.0, latf=None):
    """Claw roots (4 per paw) consistent with _paw()."""
    if hind:
        M, T = sk.head(f"toes_{side}"), sk.tail(f"toes_{side}")
        scale = 0.92
    else:
        M, T = sk.head(f"fingers_{side}"), sk.tail(f"fingers_{side}")
    sx = 1 if side == "L" else -1
    fwd = T - M
    fwd[2] = 0
    fwd /= np.linalg.norm(fwd)
    lat = np.array([1.0, 0, 0])
    c = np.array([M[0], M[1], 0.0]) + fwd * 0.05 * scale
    out = []
    latf = (1.15 if hind else 1.2) if latf is None else latf
    for j, (ox, of) in TOES:
        p = c + (lat * ox * sx * latf + fwd * (of + 0.06)) * scale + np.array([0, 0, 0.06 * scale])
        out.append((p, fwd, lat * sx))
    return out


# --------------------------------------------------------------------------- reference stance (side view)

def side_stance(sk, pose=None):
    """Leg IK so the rig matches the drawn stalking stance in the side view."""
    pose = sk.fk() if pose is None else pose
    fwd = np.array([0, -1.0, 0])
    # (paw ball sheet x,y), metapodial direction from wrist/hock (sheet dx,dy), toe dir
    legs = {
        "fore_L": ((124, 352), (-0.45, 1.0)),    # reaching forward
        "fore_R": ((284, 352), (-0.20, 1.0)),    # planted under the shoulder
        "hind_L": ((688, 352), (-0.06, 1.0)),    # extended back
        "hind_R": ((472, 352), (-0.62, 1.0)),    # stepping forward under the belly
    }
    girdle = {"fore_L": 2.0, "fore_R": 22.0}
    for leg, ((x, y), (dx, dy)) in legs.items():
        side = leg[-1]
        sx = 1 if side == "L" else -1
        lat = 0.355 if leg.startswith("fore") else 0.36
        tgt = S(x, y, lat * sx)
        ed = np.array([0.0, dx, -dy])
        pole = np.array([0, 1.0, 0]) if leg.startswith("fore") else np.array([0, -1.0, 0])
        rr = None
        if leg in girdle:
            sc = LEGS[leg][0]
            Rw = grig.rot_axis([1, 0, 0], math.radians(girdle[leg]))
            Rb = sk.rest[sc][:3, :3]
            rr = Rb.T @ Rw @ Rb
        grig.solve_leg(sk, pose, LEGS[leg], tgt, ed, fwd + np.array([0, 0, -0.08]), pole, root_rot=rr)
    return pose


# --------------------------------------------------------------------------- fur & details

SEED = 909
VOXEL = 0.011
BODY_TRIS = (8600, 4300, 2050)
CLUMP_KEEP = (1.0, 0.45, 0.12)
CLUMP_WIDTH = (1.0, 1.3, 1.8)
CLUMP_UV_SCALE = 0.6
DETAIL_UV_SCALE = 1.4


def sheet_xy(P):
    P = np.atleast_2d(P)
    return P[:, 1] * PPM + CX, GROUND - P[:, 2] * PPM


def _roots(hv, hf, rng, n, weight_fn, min_dist):
    import gbody as gb
    pts, nrm, _ = gb.sample_surface(hv, hf, n * 6, rng, weight_fn=weight_fn)
    if len(pts) == 0:
        return pts, nrm
    keep = gb.poisson_thin(pts, min_dist, rng)[:n]
    return pts[keep], nrm[keep]


def _ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def fur(sk, hv, hf, pans, rng):
    import gfur
    side, front, rear = pans["side"].view, pans["front"].view, pans["rear"].view
    C = []

    # ---- dorsal mane: neck crest -> withers -> back ridge
    def w_mane(c, n):
        x, y = sheet_xy(c)
        return (_ss(78, 96, x) * (1 - _ss(560, 590, x)) * _ss(0.05, 0.35, n[:, 2]) *
                (1 - _ss(0.20, 0.27, np.abs(c[:, 0]))) * (1 + 1.5 * _ss(100, 180, x) * (1 - _ss(300, 440, x))))
    r, nr = _roots(hv, hf, rng, 255, w_mane, 0.034)
    # keep the big lynx ears clear
    for s_ in ("L", "R"):
        eb = sk.head(f"ear_{s_}")
        far = np.linalg.norm(r - eb, axis=1) > 0.11
        r, nr = r[far], nr[far]

    def d_mane(p, n, rng):
        x, _ = sheet_xy(p)
        th = math.radians(np.interp(x[0], [90, 150, 220, 280, 340, 420, 500, 580], [58, 52, 46, 36, 26, 18, 12, 8]))
        d = np.array([0.0, math.cos(th), math.sin(th)])
        d[0] += n[0] * 0.65
        d += rng.normal(0, 0.07, 3)
        return d

    def b_mane(p, n, d, rng):
        return np.array([0.0, 0.28, -0.10]) + rng.normal(0, 0.05, 3)

    import gref
    mane_views = [gref.morph_view(side, -3), gref.morph_view(front, 6), gref.morph_view(rear, 6)]
    C += gfur.make_clumps("mane", r, nr, d_mane, rng, mane_views, 0.66, min_len=0.05,
                          width=(0.04, 0.072), flat=0.45, bend_fn=b_mane,
                          up_fn=lambda p, n, d: np.array([0.0, 1.0, 0.0]), jag=(0.82, 1.0))
    # ---- tail bush (side view only: the rear sheet draws the tail hanging, inconsistent)
    tail_bones = [f"tail_{i:02d}" for i in range(1, 7)]
    seg = [(sk.head(b), sk.tail(b)) for b in tail_bones]

    def tail_t(c):
        best = np.full(len(c), 9.0)
        tang = np.zeros((len(c), 3))
        for a, b in seg:
            ab = b - a
            t = np.clip(((c - a) @ ab) / (ab @ ab), 0, 1)
            q = a + t[:, None] * ab
            d = np.linalg.norm(c - q, axis=1)
            m = d < best
            best[m] = d[m]
            tang[m] = ab / np.linalg.norm(ab)
        return best, tang

    def w_tail(c, n):
        d, _ = tail_t(c)
        x, _ = sheet_xy(c)
        return (d < 0.14) * _ss(600, 625, x)
    r, nr = _roots(hv, hf, rng, 140, w_tail, 0.045)
    _, tg = tail_t(r)

    def d_tail(p, n, rng):
        _, t = tail_t(p[None])
        return t[0] * 0.85 + n * 0.55 + rng.normal(0, 0.08, 3)

    C += gfur.make_clumps("tail", r, nr, d_tail, rng, [side], 0.42, min_len=0.08, width=(0.07, 0.11),
                          flat=0.5, bend_fn=lambda p, n, d, rng: n * 0.12,
                          up_fn=lambda p, n, d: np.cross(d, n), jag=(0.75, 1.0))
    # tail-tip brush
    tip = sk.tail("tail_06")
    tdir = (sk.tail("tail_06") - sk.head("tail_06"))
    tdir /= np.linalg.norm(tdir)
    tips = []
    for i in range(20):
        a = 2 * math.pi * i / 20
        off = np.array([math.cos(a) * 0.05, 0.0, math.sin(a) * 0.05])
        tips.append(tip - tdir * 0.12 + off)
    tips = np.array(tips)
    nt = (tips - (tip - tdir * 0.12))
    nt /= np.linalg.norm(nt, axis=1, keepdims=True)
    C += gfur.make_clumps("tailtip", tips, nt, lambda p, n, rng: tdir + n * 0.35 + rng.normal(0, 0.1, 3),
                          rng, [side], 0.30, min_len=0.06, width=(0.05, 0.08), flat=0.5,
                          bend_fn=lambda p, n, d, rng: np.array([0, 0.0, 0.18]),
                          up_fn=lambda p, n, d: np.cross(d, n), jag=(0.75, 1.0))
    # ---- cheek ruff + throat (light)
    def w_ruff(c, n):
        x, y = sheet_xy(c)
        return (_ss(68, 88, x) * (1 - _ss(165, 185, x)) * _ss(128, 145, y) * (1 - _ss(200, 215, y)) *
                (_ss(0.04, 0.10, np.abs(c[:, 0])) + _ss(-0.2, -0.6, n[:, 2])))
    r, nr = _roots(hv, hf, rng, 75, w_ruff, 0.04)
    C += gfur.make_clumps("ruff", r, nr, lambda p, n, rng: np.array([n[0] * 0.9, 0.55, -0.85]) + n * 0.3 +
                          rng.normal(0, 0.1, 3), rng, [side, front], 0.30, min_len=0.05,
                          width=(0.04, 0.07), flat=0.45, bend_fn=lambda p, n, d, rng: np.array([0, 0.12, -0.12]),
                          up_fn=lambda p, n, d: np.cross(d, n), jag=(0.7, 1.0))
    # ---- chest tuft (dark, front view hangs to ~0.45 m above ground)
    def w_chest(c, n):
        x, y = sheet_xy(c)
        return (_ss(160, 172, x) * (1 - _ss(212, 228, x)) * _ss(195, 210, y) * (1 - _ss(0.10, 0.16, np.abs(c[:, 0]))) *
                _ss(0.0, 0.4, -n[:, 1] - n[:, 2] * 0.5))
    r, nr = _roots(hv, hf, rng, 20, w_chest, 0.035)
    C += gfur.make_clumps("chest", r, nr, lambda p, n, rng: np.array([0, -0.12, -1.0]) + rng.normal(0, 0.08, 3),
                          rng, [side, front], 0.55, min_len=0.08, width=(0.055, 0.085), flat=0.4,
                          bend_fn=lambda p, n, d, rng: np.array([0, 0.18, 0.0]),
                          up_fn=lambda p, n, d: np.array([1.0, 0, 0]), jag=(0.75, 1.0))
    # ---- belly fringe
    def w_belly(c, n):
        x, y = sheet_xy(c)
        return _ss(290, 305, x) * (1 - _ss(425, 440, x)) * _ss(0.4, 0.8, -n[:, 2]) * (np.abs(c[:, 0]) < 0.24)
    r, nr = _roots(hv, hf, rng, 22, w_belly, 0.06)
    C += gfur.make_clumps("belly", r, nr, lambda p, n, rng: np.array([0, 0.35, -1.0]) + rng.normal(0, 0.1, 3),
                          rng, [side], 0.11, min_len=0.03, width=(0.035, 0.06), flat=0.5,
                          up_fn=lambda p, n, d: np.array([1.0, 0, 0]), jag=(0.7, 1.0))
    # ---- lynx ear tufts
    for s in ("L", "R"):
        e = sk.tail(f"ear_{s}")
        sx = 1 if s == "L" else -1
        roots = np.array([e + np.array([0, 0.012 * k, -0.01]) for k in (-1, 0, 1)])
        nn = np.tile(np.array([0.3 * sx, 0, 1.0]), (3, 1))
        C += gfur.make_clumps("eartuft", roots, nn, lambda p, n, rng: n + rng.normal(0, 0.12, 3), rng, [],
                              0.10, min_len=0.05, width=(0.012, 0.018), flat=0.6, fit=False, jag=(0.75, 1.0),
                              up_fn=lambda p, n, d: np.array([0, 1.0, 0]), bone_hint=f"ear_{s}")
    return C


def details(sk):
    """Hard-surface details: claws, horn nubs, eyes, fangs, whiskers (real geometry)."""
    import gfur
    import gbody as gb
    D = []
    for s in ("L", "R"):
        for hind in (False, True):
            bone = f"toes_{s}" if hind else f"fingers_{s}"
            for p, fw, lat in toe_tips(sk, s, hind):
                D.append(dict(mesh=gfur.claw(p, fw, length=0.135 if not hind else 0.12, base_r=0.026,
                                             curl=1.0, lat=lat), bone=bone, kind="claw", lods=(0, 1)))
    for s, sx in (("L", 1), ("R", -1)):
        base = S(63, 111, 0.092 * sx)
        D.append(dict(mesh=gfur.horn(base, np.array([0.28 * sx, 0.45, 0.85]), np.array([0.0, 0.42, -0.25]),
                                     0.135, 0.032, sides=6, n=7, ridges=0.10), bone="head", kind="horn",
                      lods=(0, 1, 2)))
        D.append(dict(mesh=gb.uv_sphere(S(66, 129, 0.114 * sx), 0.034, 8, 6, scale=(0.8, 1.0, 0.72)), bone="head",
                      kind="eye", lods=(0, 1, 2)))
        D.append(dict(mesh=gfur.horn(S(43, 162, 0.046 * sx), np.array([0, -0.12, -1.0]), np.zeros(3), 0.032, 0.012,
                                     sides=4, n=3), bone="head", kind="tooth", lods=(0,)))
        D.append(dict(mesh=gfur.horn(S(50, 176, 0.040 * sx), np.array([0, -0.05, 1.0]), np.zeros(3), 0.026, 0.010,
                                     sides=4, n=3), bone="jaw", kind="tooth", lods=(0,)))
        for k, (dz, dy) in enumerate(((0.06, 0.30), (-0.05, 0.40))):
            root = S(38 + 4 * k, 162 + 3 * k, 0.085 * sx)
            D.append(dict(mesh=gb.tube(gb.catmull([root, root + np.array([0.07 * sx, 0.04, dz * 0.4]),
                                                   root + np.array([0.14 * sx, dy * 0.22, dz])], 4),
                                       np.array([0.0022, 0.0019, 0.0014, 0.0008]), sides=3, up=(0, 1, 0)),
                          bone="head", kind="whisker", lods=(0,)))
    return D


def weight_sources(sk, parts):
    """(prim, bone) pairs: anatomical parts (minus torso loft / subtractions) + spine proxies."""
    src = [(p.prim, p.bone) for p in parts if p.op == "union" and p.tag != "torso"]
    caps = {"hips": 0.27, "spine_01": 0.30, "spine_02": 0.33, "spine_03": 0.33, "neck_01": 0.26,
            "neck_02": 0.22, "mane_01": 0.09, "mane_02": 0.10, "mane_03": 0.10}
    for b, r in caps.items():
        src.append((sdf.round_cone(sk.head(b), sk.tail(b), r, r * 0.9), b))
    return src


RIGID_KINDS = {"claw", "horn", "eye", "tooth", "whisker"}

# LOD bone budgets (manifest: 46 / 30 / 18 deform bones)
LOD_REMAP = {
    1: {"fingers_L": "hand_L", "fingers_R": "hand_R", "toes_L": "foot_L", "toes_R": "foot_R",
        "ear_L": "head", "ear_R": "head", "mane_01": "neck_02", "mane_02": "neck_01", "mane_03": "spine_03",
        "tail_02": "tail_01", "tail_04": "tail_03", "tail_06": "tail_05"},
    2: {"fingers_L": "hand_L", "fingers_R": "hand_R", "toes_L": "foot_L", "toes_R": "foot_R",
        "ear_L": "head", "ear_R": "head", "mane_01": "neck_02", "mane_02": "neck_01", "mane_03": "spine_03",
        "jaw": "head", "neck_01": "spine_03", "spine_01": "hips", "scapula_L": "spine_03",
        "scapula_R": "spine_03", "tail_01": "hips", "tail_02": "hips", "tail_04": "tail_03",
        "tail_05": "tail_03", "tail_06": "tail_03", "hand_L": "forearm_L", "hand_R": "forearm_R"},
}

# projection views: (panel name, pose key)
PROJECTION = [("side", "side"), ("front", "bind"), ("rear", "bind")]
COMPARE = [("side", "side"), ("front", "bind"), ("rear", "bind")]


# --------------------------------------------------------------------------- texture hooks

WEIGHT_FALLOFF = 0.05
NORMAL_STRENGTH = 4.0
STRAND_SCALE = 1.0
ROUGHNESS = {"body": 0.86, "fur_mane": 0.9, "fur_tail": 0.9, "fur_tailtip": 0.9, "fur_ruff": 0.92,
             "fur_chest": 0.9, "fur_belly": 0.92, "fur_eartuft": 0.9, "claw": 0.32, "horn": 0.48,
             "eye": 0.06, "tooth": 0.28, "whisker": 0.55}

_FLOW_SIGN = {"hips": 1, "spine_01": -1, "spine_02": -1, "spine_03": -1, "neck_01": -1, "neck_02": -1,
              "head": -1, "jaw": 1}


def fur_flow(B, T):
    sk = B.sk
    bones = [b for b in sk.deform if b not in ("root",)]
    segs = [(sk.head(b), sk.tail(b), _FLOW_SIGN.get(b, 1)) for b in bones]

    def flow(P, N):
        best = np.full(len(P), 9.0)
        D = np.zeros_like(P)
        for a, b, sg in segs:
            ab = b - a
            t = np.clip(((P - a) @ ab) / (ab @ ab), 0, 1)
            d = np.linalg.norm(P - (a + t[:, None] * ab), axis=1)
            m = d < best
            best[m] = d[m]
            D[m] = sg * ab / np.linalg.norm(ab)
        D = D + np.array([0, 0, -0.25])            # gravity: hair falls slightly downward
        D -= (D * N).sum(1, keepdims=True) * N       # tangent plane
        return D
    return flow


def texture_overrides(B, col, T, lab):
    sk = B.sk
    inv = {v: k for k, v in B.label_names.items()}
    valid = T.valid
    P = T.pos
    out = col.copy()

    def region(name):
        return (lab == inv[name]) if name in inv else np.zeros_like(valid)
    # claws: dark base -> ivory tip (distance from the toe root)
    m = region("claw")
    if m.any():
        roots = np.array([p for s in ("L", "R") for h in (False, True) for p, _, _ in toe_tips(sk, s, h)])
        d = np.min(np.linalg.norm(P[m][:, None, :] - roots[None], axis=2), axis=1)
        t = np.clip(d / 0.10, 0, 1)[:, None]
        dark = np.array([0.24, 0.20, 0.17])
        ivory = np.array([0.86, 0.82, 0.72])
        out[m] = dark * (1 - t) + ivory * t
    m = region("horn")
    if m.any():
        bases = np.array([S(63, 111, 0.092), S(63, 111, -0.092)])
        d = np.min(np.linalg.norm(P[m][:, None, :] - bases[None], axis=2), axis=1)
        t = np.clip(d / 0.12, 0, 1)
        ridge = 0.08 * np.cos(d * 2 * math.pi / 0.022)
        base = np.array([0.55, 0.50, 0.44])
        tipc = np.array([0.86, 0.82, 0.74])
        out[m] = (base * (1 - t[:, None]) + tipc * t[:, None]) * (1 + ridge[:, None])
    m = region("eye")
    if m.any():
        q = P[m]
        out_e = np.zeros((len(q), 3))
        for sx in (1, -1):
            c = S(66, 129, 0.114 * sx)
            ax = np.array([0.55 * sx, -1.0, 0.05])
            ax /= np.linalg.norm(ax)
            sel = (q[:, 0] * sx) > 0
            v = q[sel] - c
            v /= np.linalg.norm(v, axis=1, keepdims=True)
            ang = np.degrees(np.arccos(np.clip(v @ ax, -1, 1)))
            iris = np.array([0.86, 0.50, 0.10]) * (0.75 + 0.25 * np.clip(1 - ang / 48, 0, 1))[:, None]
            e = np.where((ang < 13)[:, None], np.array([0.03, 0.02, 0.02]), iris)
            e = np.where((ang > 46)[:, None], np.array([0.10, 0.07, 0.05]), e)
            out_e[sel] = e
        out[m] = out_e
    for nm, c in (("tooth", (0.90, 0.87, 0.78)), ("whisker", (0.72, 0.70, 0.66))):
        m = region(nm)
        if m.any():
            out[m] = c
    # mouth interior (inside the subtracted slit, bind pose)
    m = region("body")
    if m.any():
        q = P[m]
        c0 = S(54, 170)
        ang = math.radians(-8)
        R = np.array([[1, 0, 0], [0, math.cos(ang), -math.sin(ang)], [0, math.sin(ang), math.cos(ang)]])
        lq = (q - c0) @ R
        inside = (np.abs(lq[:, 0]) < 0.10) & (np.abs(lq[:, 1]) < 0.15) & (np.abs(lq[:, 2]) < 0.030)
        nz = T.nrm[m][:, 2]
        inner = inside & (np.abs(nz) > 0.55)
        tmp = out[m]
        tmp[inner] = np.array([0.32, 0.10, 0.10])
        out[m] = tmp
    return out


def projection_filter(B, vname, Tb):
    """Per-view trust: the rear sheet draws the tail hanging (inconsistent with the side view),
    so it only paints the haunches/hind legs; the front sheet paints the front half only."""
    lab = B.tex_labels if hasattr(B, "tex_labels") else None
    P = Tb.pos
    y = P[..., 1]
    if vname == "rear":
        w = np.clip((y - 0.55) / 0.25, 0, 1) * np.clip((1.52 - y) / 0.08, 0, 1)
        # rump centre where the drawn tail hangs
        w[(np.abs(P[..., 0]) < 0.16) & (P[..., 2] > 0.25)] *= 0.0
        return w
    if vname == "front":
        return np.clip((-0.25 - y) / 0.3, 0, 1)
    return np.ones_like(y)
