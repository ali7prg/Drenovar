"""KAMNEKLYK — armoured boar (art/11_other_guardians_direction.png, middle row).

Head to image-right; 120 px/m (tail tuft -> tusk tip ~5.2 m, original prototype 5.23 m); ground 660.
Rock scutes are real faceted geometry (rigid per bone), bristles are geometric clumps, tusks are tubes.
"""
import math

import numpy as np

import gref
import grig
import gspec
from gbody import Part, loft, stretch
from frlib import sdf

ID = "lf_guardian_kamneklyk"
SPECIES = "kamneklyk"
SH = gspec.Sheet(120.0, 660, 360.0, "right")
S = SH.S
PPM, GROUND = SH.ppm, SH.ground


def panels():
    side = gref.Panel("side", "11", (55, 345, 715, 664), "right", PPM, GROUND, 360.0, thresh=0.10, clip_below=663, fill_holes=2500,
                      extra_mask_fn=gspec.shadow_fn(645))
    front = gref.Panel("front", "11", (790, 345, 1055, 664), "front", PPM, GROUND, 925.0, thresh=0.10, fill_holes=2500,
                       clip_below=663, extra_mask_fn=gspec.shadow_fn(645))
    return {"side": side, "front": front}


LEGS = {
    "fore_L": ["scapula_L", "upperarm_L", "forearm_L", "cannon_L", "hoof_L"],
    "fore_R": ["scapula_R", "upperarm_R", "forearm_R", "cannon_R", "hoof_R"],
    "hind_L": [None, "thigh_L", "shin_L", "hcannon_L", "hhoof_L"],
    "hind_R": [None, "thigh_R", "shin_R", "hcannon_R", "hhoof_R"],
}
TAIL = ["tail_01", "tail_02", "tail_03"]


def skeleton():
    up, fwd = (0, 0, 1), (0, -1, 0)
    B = []

    def bone(name, head, tail, parent, z=up):
        B.append(dict(name=name, head=np.asarray(head, float), tail=np.asarray(tail, float), parent=parent, z=z))
    LS, TB, TL, T8, C7, MN, AT = S(232, 505), S(178, 515), S(330, 492), S(450, 478), S(535, 488), S(570, 490), S(600, 497)
    bone("root", (0, 0, 0), (0, -0.4, 0), None)
    bone("hips", LS, TB, "root")
    bone("spine_01", LS, TL, "hips")
    bone("spine_02", TL, T8, "spine_01")
    bone("spine_03", T8, C7, "spine_02")
    bone("neck_01", C7, MN, "spine_03")
    bone("neck_02", MN, AT, "neck_01")
    bone("head", AT, S(684, 565), "neck_02")
    bone("jaw", S(625, 545), S(668, 590), "head", (0, 0, -1))
    for s, sx in (("L", 1), ("R", -1)):
        bone(f"ear_{s}", S(602, 474, 0.16 * sx), S(592, 446, 0.30 * sx), "head", fwd)
    bone("mane_01", S(560, 470), S(585, 420), "neck_01", fwd)
    bone("mane_02", S(500, 455), S(530, 400), "spine_03", fwd)
    pts = [TB, S(150, 545), S(126, 582), S(106, 618)]
    prev = "hips"
    for i, n in enumerate(TAIL):
        bone(n, pts[i], pts[i + 1], prev)
        prev = n
    for s, sx in (("L", 1), ("R", -1)):
        bone(f"scapula_{s}", S(470, 445, 0.30 * sx), S(520, 520, 0.56 * sx), "spine_03", fwd)
        bone(f"upperarm_{s}", S(520, 520, 0.56 * sx), S(498, 575, 0.62 * sx), f"scapula_{s}", fwd)
        bone(f"forearm_{s}", S(498, 575, 0.62 * sx), S(503, 624, 0.64 * sx), f"upperarm_{s}", fwd)
        bone(f"cannon_{s}", S(503, 624, 0.64 * sx), S(505, 640, 0.64 * sx), f"forearm_{s}", fwd)
        bone(f"hoof_{s}", S(505, 640, 0.64 * sx), S(516, 657, 0.64 * sx), f"cannon_{s}", fwd)
        bone(f"thigh_{s}", S(232, 505, 0.42 * sx), S(258, 570, 0.52 * sx), "hips", fwd)
        bone(f"shin_{s}", S(258, 570, 0.52 * sx), S(218, 612, 0.55 * sx), f"thigh_{s}", fwd)
        bone(f"hcannon_{s}", S(218, 612, 0.55 * sx), S(222, 640, 0.56 * sx), f"shin_{s}", fwd)
        bone(f"hhoof_{s}", S(222, 640, 0.56 * sx), S(232, 657, 0.56 * sx), f"hcannon_{s}", fwd)
    return grig.Skeleton(B)


def _hoof(P, sk, digit_bone, w=1.0):
    a, b = sk.head(digit_bone), sk.tail(digit_bone)
    c = np.array([b[0], b[1], 0.0])
    for o in (-0.06, 0.06):
        P.append(Part(sdf.ellipsoid(c + np.array([o * w, 0.01, 0.06]), (0.07 * w, 0.10, 0.065)), digit_bone, k=0.015,
                      tag="hoof"))
    P.append(Part(sdf.round_cone(a, c + np.array([0, 0.03, 0.10]), 0.11 * w, 0.12 * w), digit_bone, k=0.04,
                  tag="pastern"))


def body_parts(sk):
    P = []
    prof = [(160, 515, 560, 0.10), (182, 490, 588, 0.36), (210, 468, 598, 0.50), (260, 450, 602, 0.60),
            (330, 438, 604, 0.64), (400, 430, 604, 0.66), (450, 430, 600, 0.66), (500, 438, 592, 0.60),
            (535, 450, 582, 0.50), (565, 462, 572, 0.40), (590, 474, 560, 0.32), (604, 485, 548, 0.18)]
    prof = sorted(prof, key=lambda r: -r[0])
    Y = [S(x, 0)[1] for x, *_ in prof]
    zt = [S(0, t)[2] for _, t, b, w in prof]
    zb = [S(0, b)[2] for _, t, b, w in prof]
    w = [w for *_, w in prof]
    P.append(Part(loft(Y, zt, zb, w, bone="spine_02"), "spine_02", k=0.0, tag="torso"))
    hd = "head"
    P.append(Part(sdf.ellipsoid(S(612, 505), (0.24, 0.20, 0.20)), hd, k=0.07, tag="cranium"))
    P.append(Part(sdf.round_cone(S(622, 520), S(676, 560), 0.18, 0.11), hd, k=0.06, tag="snout"))
    P.append(Part(sdf.ellipsoid(S(684, 566), (0.10, 0.04, 0.09), rot=(0, 0, 0)), hd, k=0.02, tag="nosedisc"))
    P.append(Part(sdf.round_cone(S(626, 552), S(664, 586), 0.12, 0.075), "jaw", k=0.03, tag="jaw"))
    P.append(Part(sdf.box(S(646, 575), (0.12, 0.15, 0.006), rot=(math.radians(26), 0, 0), rounding=0.004), hd,
                  k=0.008, op="subtract", tag="mouth"))
    for sx in (1, -1):
        s = "L" if sx > 0 else "R"
        P.append(Part(sdf.ellipsoid(S(646, 512, 0.13 * sx), (0.025, 0.03, 0.02)), hd, k=0.01, op="subtract",
                      tag="eyesocket"))
        P.append(Part(sdf.ellipsoid(S(640, 503, 0.12 * sx), (0.07, 0.07, 0.05)), hd, k=0.03, tag="brow"))
        P.append(Part(sdf.ellipsoid(S(634, 556, 0.14 * sx), (0.07, 0.08, 0.06)), hd, k=0.04, tag="tuskbase"))
        P.append(Part(sdf.flat_capsule(sk.head(f"ear_{s}"), sk.tail(f"ear_{s}"), 0.07, 0.015, 0.45, up=(0, 1, 0)),
                      f"ear_{s}", k=0.03, tag="ear"))
    for s, sx in (("L", 1), ("R", -1)):
        sc, ua, fa, cn, hf = LEGS[f"fore_{s}"]
        Sj, E, K, F_ = sk.head(ua), sk.head(fa), sk.head(cn), sk.head(hf)
        P.append(Part(sdf.ellipsoid(S(505, 500, 0.50 * sx), (0.24, 0.30, 0.32)), sc, k=0.1, tag="shoulder"))
        P.append(Part(stretch(sdf.round_cone(Sj, E, 0.20, 0.17), 1.15, center=Sj), ua, k=0.07, tag="upperarm"))
        P.append(Part(stretch(sdf.round_cone(E, K, 0.165, 0.12), 1.25, center=E), fa, k=0.05, tag="forearm"))
        P.append(Part(sdf.round_cone(K, F_, 0.115, 0.11), cn, k=0.04, tag="cannon"))
        _hoof(P, sk, hf, 1.15)
        th, sh, hc, hh = LEGS[f"hind_{s}"][1:]
        H, Kn, Hk, Fh = sk.head(th), sk.head(sh), sk.head(hc), sk.head(hh)
        P.append(Part(sdf.ellipsoid(S(232, 505, 0.42 * sx), (0.26, 0.33, 0.30)), "hips", k=0.1, tag="haunch"))
        P.append(Part(sdf.ellipsoid(H + (Kn - H) * 0.5, (0.22, 0.24, 0.24)), th, k=0.08, tag="thigh_m"))
        P.append(Part(sdf.round_cone(Kn, Hk, 0.17, 0.11), sh, k=0.05, tag="gaskin"))
        P.append(Part(sdf.round_cone(Hk, Fh, 0.105, 0.10), hc, k=0.04, tag="hcannon"))
        _hoof(P, sk, hh, 1.05)
    for i, n in enumerate(TAIL):
        r0 = 0.07 - 0.015 * i
        P.append(Part(sdf.round_cone(sk.head(n), sk.tail(n), r0, r0 - 0.012), n, k=0.04, tag="tail"))
    return P


SEED = 1201
VOXEL = 0.015
BODY_TRIS = (6600, 3500, 1650)
CLUMP_KEEP = (1.0, 0.42, 0.12)
CLUMP_WIDTH = (1.0, 1.35, 1.9)
CLUMP_UV_SCALE = 0.5
DETAIL_UV_SCALE = 1.0


def fur(sk, hv, hf, pans, rng):
    import gfur
    side, front = pans["side"].view, pans["front"].view
    C = []
    xy = SH.xy
    hull = [gref.morph_view(side, 1), gref.morph_view(front, 1)]

    # dark bristle mane (neck / withers): long stiff spikes swept back
    def w_mane(c, n):
        x, y = xy(c)
        return gspec.ss(470, 500, x) * (1 - gspec.ss(600, 615, x)) * (n[:, 2] > 0.1)
    r, nr = gspec.roots(hv, hf, rng, 110, w_mane, 0.05)
    C += gfur.make_clumps("bristle", r, nr, lambda p, n, rng: np.array([n[0] * 0.6, 0.85, 0.75]) + rng.normal(0, 0.12, 3),
                          rng, hull, 0.95, min_len=0.08, width=(0.035, 0.06), flat=0.5,
                          bend_fn=lambda p, n, d, rng: np.array([0, 0.25, -0.1]),
                          up_fn=lambda p, n, d: np.array([0, 1.0, 0]), jag=(0.8, 1.0))
    # coarse hair on flanks / belly / legs between plates (hanging, shaggy fringe)
    def w_hair(c, n):
        x, y = xy(c)
        return (np.abs(n[:, 2]) < 0.8) * (y < 640) * gspec.ss(170, 190, x) * (1 - gspec.ss(615, 630, x))
    r, nr = gspec.roots(hv, hf, rng, 230, w_hair, 0.08)
    C += gfur.make_clumps("hair", r, nr, lambda p, n, rng: n * 0.45 + np.array([0, 0.25, -1.0]) + rng.normal(0, 0.12, 3),
                          rng, hull, 0.42, min_len=0.06, width=(0.05, 0.085), flat=0.4,
                          up_fn=lambda p, n, d: np.cross(d, n), jag=(0.8, 1.0))
    # long tail hair (hangs down-back like the sheet)
    tb = [(sk.head(b), sk.tail(b)) for b in TAIL]

    def w_tail(c, n):
        d = np.full(len(c), 9.0)
        for a, b in tb:
            ab = b - a
            t = np.clip(((c - a) @ ab) / (ab @ ab), 0, 1)
            d = np.minimum(d, np.linalg.norm(c - (a + t[:, None] * ab), axis=1))
        return d < 0.1
    r, nr = gspec.roots(hv, hf, rng, 28, w_tail, 0.04)
    C += gfur.make_clumps("tuft", r, nr, lambda p, n, rng: np.array([0, 0.5, -1.0]) + n * 0.5 + rng.normal(0, 0.1, 3),
                          rng, [side], 0.7, min_len=0.1, width=(0.04, 0.07), flat=0.5,
                          up_fn=lambda p, n, d: np.cross(d, n), jag=(0.85, 1.0))
    # tail tuft
    tip = sk.tail("tail_03")
    ring = np.array([tip + np.array([math.cos(a) * 0.03, 0, math.sin(a) * 0.03]) for a in np.linspace(0, 6.0, 8)])
    nn = ring - tip
    nn /= np.linalg.norm(nn, axis=1, keepdims=True)
    C += gfur.make_clumps("tuft", ring, nn, lambda p, n, rng: np.array([0, 0.3, -1.0]) + n * 0.4, rng, [side], 0.3,
                          min_len=0.08, width=(0.04, 0.06), flat=0.5, up_fn=lambda p, n, d: np.cross(d, n),
                          jag=(0.85, 1.0))
    return C


def _plate_specs(sk, hv, hf, rng, pans):
    """Dorsal scutes: big pointed plates in 3 rows along the back + leg plates."""
    import gfur
    xy = SH.xy
    side, front = pans["side"].view, pans["front"].view
    out = []
    # dorsal: sample on the top, sizes peak over the shoulders (drawing), apex fitted to the side mask
    def w_back(c, n):
        x, y = xy(c)
        return (n[:, 2] > 0.25) * gspec.ss(180, 210, x) * (1 - gspec.ss(540, 560, x))
    r, nr = gspec.roots(hv, hf, rng, 60, w_back, 0.19)
    hull = [gref.morph_view(side, -1), gref.morph_view(front, 2)]
    for p, n in zip(r, nr):
        x, _ = xy(p[None])
        size = float(np.interp(x[0], [180, 300, 430, 520, 560], [0.20, 0.28, 0.37, 0.30, 0.21])) * rng.uniform(0.85, 1.1)
        nrm = gfur._unit(n + np.array([0, 0.30, 0.35]))        # tilted back like shingles / raised spikes
        hfit = gspec.fit_height(p, nrm, hull, 1.0)
        th = float(np.clip(hfit / 1.15, size * 0.35, size * 2.2)) * rng.uniform(0.88, 1.0)
        out.append((p - n * 0.02, nrm, np.array([0, 1.0, 0.3]), size, th))
    # forearm / thigh plates
    for leg in ("fore_L", "fore_R", "hind_L", "hind_R"):
        ch = LEGS[leg]
        for b, f, sz in ((ch[2], 0.35, 0.13), (ch[2], 0.7, 0.11), (ch[1], 0.55, 0.16)):
            a, t = sk.head(b), sk.tail(b)
            p = a + (t - a) * f
            sx = np.sign(p[0])
            for ang in (-0.6, 0.0, 0.6):
                nrm = gfur._unit(np.array([sx * math.cos(ang), math.sin(ang) * 0.8 * (-1 if leg.startswith("fore") else 1), 0.15]))
                out.append((p + nrm * 0.12, nrm, np.array([0, 0, 1.0]), sz * rng.uniform(0.85, 1.1), sz * 0.45))
    return out


def details(sk, hv=None, hf=None, pans=None):
    import gfur
    import gbody as gb
    rng = np.random.default_rng(7)
    D = []
    for s, sx in (("L", 1), ("R", -1)):
        # big curved ivory tusk: out of the lip, forward-out then up and back
        base = S(650, 568, 0.15 * sx)
        D.append(dict(mesh=gfur.horn(base, np.array([0.55 * sx, -0.75, 0.15]), np.array([0.25 * sx, 0.15, 0.85]),
                                     0.62, 0.065, sides=7, n=9, ridges=0.0), bone="head", kind="tusk", lods=(0, 1, 2)))
        D.append(dict(mesh=gb.uv_sphere(S(646, 512, 0.125 * sx), 0.022, 8, 6), bone="head", kind="eye", lods=(0, 1, 2)))
    if hv is not None:
        bones = [b for b in sk.deform if b not in ("root",)]
        for (c, n, up, size, th) in _plate_specs(sk, hv, hf, rng, pans):
            # rigid to the nearest bone
            best, bb = 9.0, "spine_02"
            for b in bones:
                a, t = sk.head(b), sk.tail(b)
                ab = t - a
                u = np.clip(((c - a) @ ab) / (ab @ ab), 0, 1)
                d = np.linalg.norm(c - (a + u * ab))
                if d < best:
                    best, bb = d, b
            D.append(dict(mesh=gspec.rock_plate(c, n, up, size, th, sides=6, rng=rng), bone=bb, kind="plate",
                          lods=(0, 1, 2) if size > 0.2 else (0, 1)))
    return D


def weight_sources(sk, parts):
    src = [(p.prim, p.bone) for p in parts if p.op == "union" and p.tag != "torso"]
    caps = {"hips": 0.5, "spine_01": 0.55, "spine_02": 0.58, "spine_03": 0.55, "neck_01": 0.4, "neck_02": 0.33,
            "mane_01": 0.12, "mane_02": 0.14}
    for b, r in caps.items():
        src.append((sdf.round_cone(sk.head(b), sk.tail(b), r, r * 0.9), b))
    return src


RIGID_KINDS = {"tusk", "eye", "plate"}
LOD_REMAP = {
    1: {"ear_L": "head", "ear_R": "head", "mane_01": "neck_01", "mane_02": "spine_03", "tail_03": "tail_02",
        "hoof_L": "cannon_L", "hoof_R": "cannon_R", "hhoof_L": "hcannon_L", "hhoof_R": "hcannon_R"},
    2: {"ear_L": "head", "ear_R": "head", "mane_01": "neck_01", "mane_02": "spine_03", "tail_03": "tail_01",
        "tail_02": "tail_01", "hoof_L": "cannon_L", "hoof_R": "cannon_R", "hhoof_L": "hcannon_L",
        "hhoof_R": "hcannon_R", "jaw": "head", "spine_01": "hips", "neck_01": "spine_03", "scapula_L": "spine_03",
        "scapula_R": "spine_03", "cannon_L": "forearm_L", "cannon_R": "forearm_R"},
}
PROJECTION = [("side", "side"), ("front", "bind")]
COMPARE = [("side", "side"), ("front", "bind")]
WEIGHT_FALLOFF = 0.06
NORMAL_STRENGTH = 4.0
ROUGHNESS = {"body": 0.86, "fur_bristle": 0.85, "fur_hair": 0.9, "fur_tuft": 0.9, "tusk": 0.38, "eye": 0.06,
             "plate": 0.82}
_FLOW_SIGN = {"hips": 1, "spine_01": -1, "spine_02": -1, "spine_03": -1, "neck_01": -1, "neck_02": -1, "head": -1}


def side_stance(sk):
    return gspec.stance(sk, LEGS, SH, {
        "fore_L": ((505, 640), (0.15, 1.0)), "fore_R": ((425, 640), (-0.2, 1.0)),
        "hind_L": ((150, 640), (-0.5, 1.0)), "hind_R": ((268, 640), (0.15, 1.0))},
        girdle={"fore_R": 6.0})


def fur_flow(B, T):
    sk = B.sk
    segs = [(sk.head(b), sk.tail(b), _FLOW_SIGN.get(b, 1)) for b in sk.deform if b != "root"]

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
        D = D + np.array([0, 0.2, -0.5])
        D -= (D * N).sum(1, keepdims=True) * N
        return D
    return flow


def texture_overrides(B, col, T, lab):
    inv = {v: k for k, v in B.label_names.items()}
    P = T.pos
    out = col.copy()
    m = lab == inv.get("tusk", -9)
    if m.any():
        bases = np.array([S(650, 568, 0.15), S(650, 568, -0.15)])
        d = np.min(np.linalg.norm(P[m][:, None, :] - bases[None], axis=2), axis=1)
        t = np.clip(d / 0.5, 0, 1)[:, None]
        out[m] = np.array([0.55, 0.47, 0.36]) * (1 - t) + np.array([0.90, 0.86, 0.76]) * t
    m = lab == inv.get("eye", -9)
    if m.any():
        out[m] = np.array([0.10, 0.05, 0.03])
    m = (lab == inv["body"]) & (P[..., 2] < 0.13)
    if m.any():
        k = np.clip((0.13 - P[m][:, 2]) / 0.05, 0, 1)[:, None]
        out[m] = out[m] * (1 - k) + np.array([0.24, 0.21, 0.18]) * k
    return out


PIVOT = S(370, 540)
ANIM = dict(
    spine=["spine_01", "spine_02", "spine_03"], neck=["neck_01", "neck_02"], tail=TAIL,
    mane=["mane_01", "mane_02"], bones={"jaw", "ear_L", "ear_R"},
    tail_base=[0.0] * 3, tail_lag=0.08, idle_tail_sway=12.0, idle_tail_curl=4.0,
    walk=dict(T=33 / 30, speed=1.4, duty=0.64, height=-0.05,
              touchdown={"hind_L": 0.0, "fore_L": 0.25, "hind_R": 0.5, "fore_R": 0.75},
              lift_f=0.13, lift_h=0.12, fold_f=55.0, fold_h=40.0, bob=0.025, sway=0.03, pitch=1.0, roll=2.5,
              yaw=2.0, spine_yaw=1.5, tail_sway=14.0, tail_lift=4.0, tail_bounce=4.0, ears=0.0,
              mane_bounce=4.0, head_nod=2.5),
    run=dict(T=20 / 30, speed=3.8, duty=0.42, touchdown={"fore_L": 0.0, "hind_R": 0.0, "fore_R": 0.5, "hind_L": 0.5},
             lift_f=0.2, lift_h=0.18, fold_f=70.0, fold_h=50.0, bob=0.045, sway=0.0, pitch=1.5, roll=2.0, yaw=1.0,
             spine_yaw=1.0, flex=2.0, tail_sway=10.0, tail_lift=20.0, tail_bounce=6.0, ears=-12.0, mane_bounce=8.0,
             head_nod=3.0, height=-0.02),
    alert_pose=dict(body=(0.0, 0.06, -0.06, -3.0, 0.0, 0.0),
                    rot={"neck_01": (8.0, 0, 0), "neck_02": (6.0, 0, 0), "head": (4.0, 0, 0)}, tail_lift=25.0),
    death_lie=(-0.75, 86.0), roar_neck=12.0, roar_head=10.0, roar_jaw=28.0, mane_bristle=18.0,
)


def attack(C, P):
    """Tusk gore: head low, short charge (feet drive in place), upward hooking toss of the tusks at
    contact 0.70 s, recover back to the start."""
    import ganim
    import gclips
    from ganim import keys_cr, keys_smooth
    ab = tuple(P["alert_pose"]["body"])
    body_k = [(0, ab), (0.2, (0, 0.10, -0.10, -5, 0, 0)), (0.42, (0, -0.30, -0.10, -6, 0, 3)),
              (0.62, (0, -0.70, -0.08, -4, 0, -2)), (0.70, (0, -0.80, 0.02, 7, 2, -6)),
              (0.86, (0, -0.70, -0.04, 2, 0, 0)), (1.08, (0, -0.30, -0.06, -1, 0, 0)), (1.3, ab)]
    rot_k = {"neck_01": [(0, (8, 0, 0)), (0.3, (22, 0, 0)), (0.62, (24, 0, 4)), (0.70, (-14, 0, -10)),
                         (0.88, (4, 0, 0)), (1.3, (8, 0, 0))],
             "neck_02": [(0, (6, 0, 0)), (0.3, (16, 0, 0)), (0.62, (18, 0, 0)), (0.70, (-12, 0, -8)),
                         (0.9, (2, 0, 0)), (1.3, (6, 0, 0))],
             "head": [(0, (4, 0, 0)), (0.3, (14, 0, 0)), (0.62, (16, 0, 0)), (0.70, (-20, -8, 0)), (0.9, (0, 0, 0)),
                      (1.3, (4, 0, 0))],
             "jaw": [(0, (2, 0, 0)), (0.6, (14, 0, 0)), (0.75, (20, 0, 0)), (1.0, (3, 0, 0)), (1.3, (2, 0, 0))]}
    steps = {"fore_L": [0.14, 0.42], "fore_R": [0.27, 0.55], "hind_L": [0.22, 0.50], "hind_R": [0.34, 0.62]}
    adv = 0.8

    def foot_keys(leg):
        ks = [(0, 0.0, 0.0)]
        pos = 0.0
        for i, t0 in enumerate(steps[leg]):
            nxt = adv * (i + 1) / len(steps[leg])
            ks += [(t0, pos, 0.0), (t0 + 0.06, (pos + nxt) / 2, 0.16), (t0 + 0.12, nxt, 0.0)]
            pos = nxt
        back = 0.95 + (0.08 if leg.startswith("hind") else 0.0)
        ks += [(back, pos, 0.0), (back + 0.08, pos / 2, 0.14), (back + 0.16, 0.0, 0.0), (1.3, 0.0, 0.0)]
        return ks
    fk = {leg: foot_keys(leg) for leg in C.legs}

    def frame(t):
        body = tuple(keys_cr(t, body_k))
        rot = {b: tuple(keys_cr(t, k)) for b, k in rot_k.items()}
        for b in ("ear_L", "ear_R"):
            rot[b] = (-30.0 * ganim.ss(t / 0.3), 0, 0)
        rot.update(gclips.tail_rot(P, t, lift=30.0, sway=12.0, freq=2.5, lag=0.08))
        for b in P["mane"]:
            rot[b] = (18.0 + 6.0 * math.sin(2 * math.pi * 3 * t), 0, 0)
        feet = {}
        for leg in C.legs:
            v = keys_smooth(t, [(k[0], np.array(k[1:])) for k in fk[leg]])
            feet[leg] = dict(pos=C.neutral[leg] + np.array([0.0, -v[0], v[1]]), meta=40.0 * min(1.0, v[1] / 0.16),
                             toe=20.0 * min(1.0, v[1] / 0.16))
        return dict(body=body, rot=rot, feet=feet)
    return ganim.sample(frame, 1.3), {"markers": {"contact": 0.70}}


LEVELS = {
    "L1": {"game_scale": 1.18, "sites": [], "baseColorFactor": [1, 1, 1, 1], "show_nodes": [],
           "look": "charcoal bristles, mossy rock scutes, ivory tusks (not used by the campaign)"},
    "L2": {"game_scale": 1.34, "sites": ["lf_site_06"], "baseColorFactor": [0.88, 0.86, 0.85, 1.0],
           "show_nodes": ["lf_guardian_kamneklyk_L2"], "look": "darker hide, second (upper) tusk pair"},
    "L3": {"game_scale": 1.50, "sites": ["lf_site_09"], "baseColorFactor": [0.76, 0.74, 0.73, 1.0],
           "show_nodes": ["lf_guardian_kamneklyk_L2", "lf_guardian_kamneklyk_L3"],
           "look": "darkest hide, upper tusks + extra crest scutes"},
}
NOTES = ("Kamneklyk: rock scutes are rigid real geometry bound to the nearest spine/limb bone; tusks are tubes "
         "on the head bone.  Attack = tusk gore (contact 0.70 s).  Run = trot.  Level scale by the game.")


def sockets(sk):
    return {"mouth": S(680, 580), "tusk_tip_L": S(700, 525, 0.6), "head_top": S(600, 380), "chest": S(560, 575),
            "hit_center": S(370, 540), "tail_tip": sk.tail("tail_03")}


def level_geometry(B):
    import gfur
    src = [i for i, d in enumerate(B.details) if d["kind"] == "tusk"][0]
    out = {"L2": [], "L3": []}
    for sx in (1, -1):
        out["L2"].append((gfur.horn(S(640, 552, 0.17 * sx), np.array([0.6 * sx, -0.4, 0.5]),
                                    np.array([0.1 * sx, 0.3, 0.6]), 0.38, 0.045, sides=7, n=9), src, "head"))
    plates = [i for i, d in enumerate(B.details) if d["kind"] == "plate"]
    if plates:
        for k, x in enumerate((300, 360, 420, 480)):
            y = np.interp(x, [300, 480], [452, 445]) - 10
            out["L3"].append((gfur.horn(S(x, y), np.array([0, 0.45, 0.9]), np.array([0, 0.3, -0.1]), 0.32, 0.06,
                                        sides=7, n=9), src, "spine_02" if x < 450 else "spine_03"))
    return out


HEAD_VIEWS = {
    "side": {"sheet": "11", "box": (1120, 350, 1536, 680), "kind": "persp",
             "cam": S(640, 520) + np.array([-2.2, -1.0, 0.15]), "look": S(640, 525), "lens": 50.0},
}
