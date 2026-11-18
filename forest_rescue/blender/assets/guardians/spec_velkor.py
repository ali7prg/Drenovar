"""VELKOR — shaggy elk/bison antler beast (art/11_other_guardians_direction.png, top row).

Side view: head to image-right ("right" view, camera at -X).  Scale 110 px/m: nose->tail ~4.97 m
(original VELKOR prototype 5.0 m long).  Ground row 332, origin column 315.
"""
import math

import numpy as np

import gref
import grig
import gspec
from gbody import Part, loft, stretch
from frlib import sdf

ID = "lf_guardian_velkor"
SPECIES = "velkor"
SH = gspec.Sheet(110.0, 332, 315.0, "right")
S = SH.S
PPM, GROUND = SH.ppm, SH.ground


def panels():
    side = gref.Panel("side", "11", (60, 0, 700, 336), "right", PPM, GROUND, 315.0, thresh=0.10, clip_below=335,
                      extra_mask_fn=gspec.shadow_fn(318))
    front = gref.Panel("front", "11", (760, 0, 1085, 336), "front", PPM, GROUND, 922.0, thresh=0.10, clip_below=335,
                       extra_mask_fn=gspec.shadow_fn(318))
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
    LS, TB, TL, T8, C7, MN, AT = S(255, 128), S(215, 132), S(335, 122), S(430, 118), S(505, 125), S(545, 118), S(578, 112)
    bone("root", (0, 0, 0), (0, -0.4, 0), None)
    bone("hips", LS, TB, "root")
    bone("spine_01", LS, TL, "hips")
    bone("spine_02", TL, T8, "spine_01")
    bone("spine_03", T8, C7, "spine_02")
    bone("neck_01", C7, MN, "spine_03")
    bone("neck_02", MN, AT, "neck_01")
    bone("head", AT, S(638, 134), "neck_02")
    bone("jaw", S(592, 130), S(630, 150), "head", (0, 0, -1))
    for s, sx in (("L", 1), ("R", -1)):
        bone(f"ear_{s}", S(583, 108, 0.22 * sx), S(572, 104, 0.46 * sx), "head", fwd)
    bone("mane_01", S(582, 140), S(588, 178), "neck_02", fwd)
    bone("mane_02", S(538, 168), S(545, 220), "neck_01", fwd)
    pts = [TB, S(196, 152), S(180, 176), S(168, 200)]
    prev = "hips"
    for i, n in enumerate(TAIL):
        bone(n, pts[i], pts[i + 1], prev)
        prev = n
    for s, sx in (("L", 1), ("R", -1)):
        bone(f"scapula_{s}", S(482, 102, 0.28 * sx), S(512, 168, 0.44 * sx), "spine_03", fwd)
        bone(f"upperarm_{s}", S(512, 168, 0.44 * sx), S(474, 214, 0.46 * sx), f"scapula_{s}", fwd)
        bone(f"forearm_{s}", S(474, 214, 0.46 * sx), S(458, 280, 0.47 * sx), f"upperarm_{s}", fwd)
        bone(f"cannon_{s}", S(458, 280, 0.47 * sx), S(455, 309, 0.47 * sx), f"forearm_{s}", fwd)
        bone(f"hoof_{s}", S(455, 309, 0.47 * sx), S(468, 328, 0.47 * sx), f"cannon_{s}", fwd)
        bone(f"thigh_{s}", S(238, 148, 0.38 * sx), S(265, 214, 0.44 * sx), "hips", fwd)
        bone(f"shin_{s}", S(265, 214, 0.44 * sx), S(208, 262, 0.45 * sx), f"thigh_{s}", fwd)
        bone(f"hcannon_{s}", S(208, 262, 0.45 * sx), S(213, 309, 0.46 * sx), f"shin_{s}", fwd)
        bone(f"hhoof_{s}", S(213, 309, 0.46 * sx), S(226, 328, 0.46 * sx), f"hcannon_{s}", fwd)
    return grig.Skeleton(B)


def _hoof(P, sk, digit_bone, sx):
    """Cloven hoof: two keratin digits (ground at z=0) + dew claws, dark via texture region."""
    a, b = sk.head(digit_bone), sk.tail(digit_bone)
    c = np.array([b[0], b[1], 0.0])
    for o in (-0.055, 0.055):
        P.append(Part(sdf.ellipsoid(c + np.array([o, 0.02, 0.07]), (0.065, 0.10, 0.075)), digit_bone, k=0.015,
                      tag="hoof"))
    P.append(Part(sdf.round_cone(a, c + np.array([0, 0.03, 0.12]), 0.085, 0.10), digit_bone, k=0.04, tag="pastern"))
    for o in (-0.07, 0.07):
        P.append(Part(sdf.ellipsoid(a + np.array([o, 0.07, -0.03]), (0.025, 0.03, 0.035)), digit_bone, k=0.01,
                      tag="dewclaw"))


def body_parts(sk):
    P = []
    prof = [(206, 132, 160, 0.10), (222, 118, 196, 0.36), (245, 110, 214, 0.47), (280, 104, 226, 0.53),
            (330, 100, 234, 0.56), (380, 94, 238, 0.57), (430, 86, 238, 0.58), (470, 82, 232, 0.56),
            (505, 88, 222, 0.50), (530, 98, 206, 0.40), (555, 106, 184, 0.31), (574, 106, 162, 0.24),
            (582, 108, 150, 0.12)]
    prof = sorted(prof, key=lambda r: -r[0])          # ascending world Y (right-facing sheet)
    Y = [S(x, 0)[1] for x, *_ in prof]
    zt = [S(0, t)[2] for _, t, b, w in prof]
    zb = [S(0, b)[2] for _, t, b, w in prof]
    w = [w for *_, w in prof]
    P.append(Part(loft(Y, zt, zb, w, bone="spine_02"), "spine_02", k=0.0, tag="torso"))
    P.append(Part(sdf.ellipsoid(S(482, 100), (0.30, 0.45, 0.20)), "spine_03", k=0.12, tag="hump"))
    hd = "head"
    P.append(Part(sdf.ellipsoid(S(588, 114), (0.21, 0.22, 0.19)), hd, k=0.07, tag="cranium"))
    P.append(Part(sdf.round_cone(S(600, 122), S(634, 134), 0.165, 0.11), hd, k=0.06, tag="muzzle"))
    P.append(Part(sdf.ellipsoid(S(641, 133), (0.10, 0.07, 0.085)), hd, k=0.03, tag="nose"))
    P.append(Part(sdf.round_cone(S(594, 136), S(628, 148), 0.11, 0.07), "jaw", k=0.03, tag="jaw"))
    P.append(Part(sdf.box(S(615, 142), (0.13, 0.17, 0.006), rot=(math.radians(14), 0, 0), rounding=0.004), hd,
                  k=0.008, op="subtract", tag="mouth"))
    for sx in (1, -1):
        P.append(Part(sdf.ellipsoid(S(603, 116, 0.165 * sx), (0.03, 0.04, 0.026)), hd, k=0.01, op="subtract",
                      tag="eyesocket"))
        P.append(Part(sdf.ellipsoid(S(596, 109, 0.13 * sx), (0.08, 0.08, 0.06)), hd, k=0.04, tag="brow"))
        P.append(Part(sdf.ellipsoid(S(566, 92, 0.15 * sx), (0.07, 0.07, 0.07)), hd, k=0.03, tag="pedicle"))
        b, t = sk.head(f"ear_{'L' if sx > 0 else 'R'}"), sk.tail(f"ear_{'L' if sx > 0 else 'R'}")
        P.append(Part(sdf.flat_capsule(b, t, 0.075, 0.03, 0.45, up=(0, 1, 0)), f"ear_{'L' if sx > 0 else 'R'}",
                      k=0.03, tag="ear"))
    for s, sx in (("L", 1), ("R", -1)):
        sc, ua, fa, cn, hf = LEGS[f"fore_{s}"]
        Sj, E, K, F_ = sk.head(ua), sk.head(fa), sk.head(cn), sk.head(hf)
        P.append(Part(sdf.ellipsoid(S(498, 152, 0.36 * sx), (0.22, 0.32, 0.36)), sc, k=0.1, tag="shoulder"))
        P.append(Part(sdf.round_cone(Sj, E, 0.20, 0.17), ua, k=0.07, tag="upperarm"))
        P.append(Part(sdf.round_cone(E, K, 0.16, 0.095), fa, k=0.05, tag="forearm"))
        P.append(Part(sdf.round_cone(K, F_, 0.085, 0.08), cn, k=0.04, tag="cannon"))
        _hoof(P, sk, hf, sx)
        th, sh, hc, hh = LEGS[f"hind_{s}"][1:]
        H, Kn, Hk, Fh = sk.head(th), sk.head(sh), sk.head(hc), sk.head(hh)
        P.append(Part(sdf.ellipsoid(S(240, 150, 0.34 * sx), (0.26, 0.36, 0.34)), "hips", k=0.1, tag="haunch"))
        P.append(Part(sdf.ellipsoid(H + (Kn - H) * 0.5, (0.21, 0.24, 0.26)), th, k=0.08, tag="thigh_m"))
        P.append(Part(sdf.round_cone(Kn, Hk, 0.16, 0.095), sh, k=0.05, tag="gaskin"))
        P.append(Part(sdf.round_cone(Hk, Fh, 0.085, 0.08), hc, k=0.04, tag="hcannon"))
        _hoof(P, sk, hh, sx)
    for i, n in enumerate(TAIL):
        r0 = 0.10 - 0.02 * i
        P.append(Part(sdf.round_cone(sk.head(n), sk.tail(n), r0, r0 - 0.02), n, k=0.04, tag="tail"))
    return P


# --------------------------------------------------------------------------- fur / moss / details

SEED = 1101
VOXEL = 0.016
BODY_TRIS = (6800, 3600, 1700)
CLUMP_KEEP = (1.0, 0.42, 0.12)
CLUMP_WIDTH = (1.0, 1.35, 1.9)
CLUMP_UV_SCALE = 0.55
DETAIL_UV_SCALE = 1.2


def fur(sk, hv, hf, pans, rng):
    import gfur
    side, front = pans["side"].view, pans["front"].view
    hull = [gref.morph_view(side, 1), gref.morph_view(front, 1)]
    C = []
    xy = SH.xy

    # long shaggy locks hanging from torso / neck / upper legs
    def w_shag(c, n):
        x, y = xy(c)
        return (np.abs(n[:, 2]) < 0.75) * (y < 300) * gspec.ss(200, 215, x) * (1 - gspec.ss(585, 600, x))
    r, nr = gspec.roots(hv, hf, rng, 250, w_shag, 0.075)
    C += gfur.make_clumps("shag", r, nr, lambda p, n, rng: n * 0.35 + np.array([0, 0.18, -1.0]) +
                          rng.normal(0, 0.1, 3), rng, hull, 0.85, min_len=0.10, width=(0.07, 0.12), flat=0.35,
                          bend_fn=lambda p, n, d, rng: n * 0.05 + np.array([0, 0.05, -0.05]),
                          up_fn=lambda p, n, d: np.cross(d, n), jag=(0.9, 1.0))
    # belly / chest underside fringe (long hanging hair)
    def w_belly(c, n):
        x, y = xy(c)
        return (n[:, 2] < -0.45) * gspec.ss(220, 245, x) * (1 - gspec.ss(560, 580, x))
    r, nr = gspec.roots(hv, hf, rng, 70, w_belly, 0.09)
    C += gfur.make_clumps("shag", r, nr, lambda p, n, rng: np.array([0, 0.15, -1.0]) + rng.normal(0, 0.08, 3), rng,
                          hull, 0.7, min_len=0.10, width=(0.09, 0.13), flat=0.75,
                          up_fn=lambda p, n, d: np.array([0, 1.0, 0]), jag=(0.9, 1.0))
    # throat / chest beard (long, hanging)
    def w_beard(c, n):
        x, y = xy(c)
        return gspec.ss(520, 540, x) * (1 - gspec.ss(632, 640, x)) * (n[:, 2] < -0.2) * (np.abs(c[:, 0]) < 0.3)
    r, nr = gspec.roots(hv, hf, rng, 55, w_beard, 0.06)
    C += gfur.make_clumps("beard", r, nr, lambda p, n, rng: np.array([0, 0.05, -1.0]) + rng.normal(0, 0.1, 3), rng,
                          hull, 0.55, min_len=0.12, width=(0.08, 0.12), flat=0.7,
                          up_fn=lambda p, n, d: np.array([1.0, 0, 0]), jag=(0.85, 1.0))
    # moss + leaves on the back / neck top (short, flat blades lying on the surface)
    def w_moss(c, n):
        x, y = xy(c)
        return (n[:, 2] > 0.35) * gspec.ss(215, 240, x) * (1 - gspec.ss(565, 580, x))
    r, nr = gspec.roots(hv, hf, rng, 120, w_moss, 0.075)
    C += gfur.make_clumps("moss", r, nr, lambda p, n, rng: n * 0.9 + rng.normal(0, 0.3, 3), rng, [side, front], 0.24,
                          min_len=0.05, width=(0.07, 0.11), flat=0.25,
                          bend_fn=lambda p, n, d, rng: -n * 0.4, up_fn=lambda p, n, d: np.cross(d, n),
                          jag=(0.6, 1.0))
    # tail hair
    tb = [(sk.head(b), sk.tail(b)) for b in TAIL]

    def w_tail(c, n):
        d = np.full(len(c), 9.0)
        for a, b in tb:
            ab = b - a
            t = np.clip(((c - a) @ ab) / (ab @ ab), 0, 1)
            d = np.minimum(d, np.linalg.norm(c - (a + t[:, None] * ab), axis=1))
        x, y = xy(c)
        return (d < 0.16) | ((x < 230) & (y < 200) & (np.abs(c[:, 0]) < 0.3))
    r, nr = gspec.roots(hv, hf, rng, 60, w_tail, 0.045)
    C += gfur.make_clumps("tail", r, nr, lambda p, n, rng: np.array([0, 0.55, -1.0]) + n * 0.5 + rng.normal(0, 0.12, 3),
                          rng, [side], 1.15, min_len=0.15, width=(0.07, 0.11), flat=0.45,
                          up_fn=lambda p, n, d: np.cross(d, n), jag=(0.85, 1.0))
    # fetlock feathering
    for leg in LEGS.values():
        a = sk.head(leg[4])
        ring = []
        for k in range(6):
            ang = 2 * math.pi * k / 6
            ring.append(a + np.array([math.cos(ang) * 0.08, math.sin(ang) * 0.08, 0.02]))
        ring = np.array(ring)
        nn = ring - a
        nn /= np.linalg.norm(nn, axis=1, keepdims=True)
        C += gfur.make_clumps("feather", ring, nn, lambda p, n, rng: n * 0.5 + np.array([0, 0, -1.0]), rng, [], 0.13,
                              min_len=0.06, width=(0.04, 0.06), flat=0.5, fit=False, jag=(0.8, 1.0),
                              up_fn=lambda p, n, d: np.cross(d, n))
    return C


def _antler(base, sx, rng):
    """Bowed beam sweeping out/back/up (sheet: ~±1.25 m, 1.7 m behind the head) with 8 curved tines
    rising and hooking slightly forward; brow tine reaches over the face."""
    import gfur
    import gbody as gb
    beam_pts = np.array([base, base + np.array([0.40 * sx, 0.15, 0.06]), base + np.array([0.80 * sx, 0.45, 0.10]),
                         base + np.array([1.08 * sx, 0.85, 0.13]), base + np.array([1.25 * sx, 1.30, 0.15]),
                         base + np.array([1.32 * sx, 1.70, 0.18])])
    beam = gb.catmull(beam_pts, 11)
    r = np.linspace(0.13, 0.05, 11)
    meshes = [gb.tube(beam, r, sides=6, up=(0, 0, 1), tip=True)]
    tines = [(0.03, (0.05 * sx, -1.0, 0.25), (0.0, -0.1, 0.55), 0.70),
             (0.16, (0.06 * sx, -0.55, 0.85), (0.0, -0.2, 0.25), 0.52),
             (0.30, (0.06 * sx, -0.30, 0.95), (0.0, -0.30, 0.05), 0.60),
             (0.42, (0.08 * sx, -0.20, 1.0), (0.04 * sx, -0.30, 0.0), 0.62),
             (0.55, (0.10 * sx, -0.10, 1.0), (0.04 * sx, -0.28, 0.0), 0.60),
             (0.68, (0.12 * sx, 0.0, 1.0), (0.05 * sx, -0.25, 0.0), 0.58),
             (0.81, (0.16 * sx, 0.10, 1.0), (0.06 * sx, -0.22, 0.0), 0.52),
             (0.93, (0.22 * sx, 0.25, 0.95), (0.06 * sx, -0.18, 0.0), 0.42)]
    for f, d, cv, L in tines:
        i = f * (len(beam) - 1)
        p = beam[int(i)] * (1 - (i % 1)) + beam[min(int(i) + 1, len(beam) - 1)] * (i % 1)
        rr = float(np.interp(f, np.linspace(0, 1, 11), r)) * 0.85
        meshes.append(gfur.horn(p, np.array(d), np.array(cv), L, rr, sides=5, n=6))
    return meshes


def details(sk):
    import gfur
    import gbody as gb
    rng = np.random.default_rng(5)
    D = []
    for s, sx in (("L", 1), ("R", -1)):
        base = S(566, 90, 0.15 * sx)
        for m in _antler(base, sx, rng):
            D.append(dict(mesh=m, bone="head", kind="antler", lods=(0, 1, 2)))
        D.append(dict(mesh=gb.uv_sphere(S(603, 116, 0.16 * sx), 0.03, 8, 6, scale=(0.8, 1.0, 0.75)), bone="head",
                      kind="eye", lods=(0, 1, 2)))
        # hanging moss vines from the beam (green strands)
        for k, f in enumerate((0.25, 0.45, 0.62, 0.8)):
            top = base + np.array([(0.40 + 0.9 * f) * sx, 0.15 + 1.5 * f, 0.05 + 0.12 * f])
            L = 0.28 + 0.12 * ((k * 7) % 3)
            pts = gb.catmull([top, top + np.array([0.02 * sx, 0.02, -L * 0.5]), top + np.array([0.0, 0.05, -L])], 5)
            D.append(dict(mesh=gb.tube(pts, np.linspace(0.022, 0.006, 5), sides=4, up=(0, 1, 0), tip=True),
                          bone="head", kind="vine", lods=(0, 1)))
    return D


def weight_sources(sk, parts):
    src = [(p.prim, p.bone) for p in parts if p.op == "union" and p.tag != "torso"]
    caps = {"hips": 0.45, "spine_01": 0.5, "spine_02": 0.52, "spine_03": 0.5, "neck_01": 0.36, "neck_02": 0.3,
            "mane_01": 0.12, "mane_02": 0.14}
    for b, r in caps.items():
        src.append((sdf.round_cone(sk.head(b), sk.tail(b), r, r * 0.9), b))
    return src


RIGID_KINDS = {"antler", "eye", "vine"}
LOD_REMAP = {
    1: {"ear_L": "head", "ear_R": "head", "mane_01": "neck_02", "mane_02": "neck_01", "tail_03": "tail_02",
        "hoof_L": "cannon_L", "hoof_R": "cannon_R", "hhoof_L": "hcannon_L", "hhoof_R": "hcannon_R"},
    2: {"ear_L": "head", "ear_R": "head", "mane_01": "neck_02", "mane_02": "neck_01", "tail_03": "tail_01",
        "tail_02": "tail_01", "hoof_L": "cannon_L", "hoof_R": "cannon_R", "hhoof_L": "hcannon_L",
        "hhoof_R": "hcannon_R", "jaw": "head", "spine_01": "hips", "neck_01": "spine_03", "scapula_L": "spine_03",
        "scapula_R": "spine_03", "cannon_L": "forearm_L", "cannon_R": "forearm_R"},
}
PROJECTION = [("side", "side"), ("front", "bind")]
COMPARE = [("side", "side"), ("front", "bind")]


def side_stance(sk):
    """Drawn walking stance: near hind leg extended back, far hind under the belly."""
    return gspec.stance(sk, LEGS, SH, {
        "fore_L": ((452, 309), (0.05, 1.0)), "fore_R": ((412, 306), (-0.12, 1.0)),
        "hind_L": ((142, 309), (-0.45, 1.0)), "hind_R": ((262, 309), (0.10, 1.0))},
        girdle={"fore_R": 8.0})
WEIGHT_FALLOFF = 0.06
NORMAL_STRENGTH = 4.5
ROUGHNESS = {"body": 0.88, "fur_shag": 0.92, "fur_beard": 0.92, "fur_moss": 0.95, "fur_tail": 0.92,
             "fur_feather": 0.92, "antler": 0.55, "eye": 0.06, "vine": 0.9}
_FLOW_SIGN = {"hips": 1, "spine_01": -1, "spine_02": -1, "spine_03": -1, "neck_01": -1, "neck_02": -1, "head": -1}


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
        D = D * 0.4 + np.array([0, 0.1, -1.0])          # long hair falls
        D -= (D * N).sum(1, keepdims=True) * N
        return D
    return flow


def texture_overrides(B, col, T, lab):
    inv = {v: k for k, v in B.label_names.items()}
    P = T.pos
    out = col.copy()
    m = lab == inv.get("antler", -9)
    if m.any():
        bases = np.array([S(566, 90, 0.15), S(566, 90, -0.15)])
        d = np.min(np.linalg.norm(P[m][:, None, :] - bases[None], axis=2), axis=1)
        t = np.clip(d / 1.1, 0, 1)[:, None] ** 0.7
        streak = 0.08 * np.sin(P[m][:, 0] * 90 + P[m][:, 2] * 140)[:, None]
        out[m] = (np.array([0.42, 0.34, 0.25]) * (1 - t) + np.array([0.86, 0.81, 0.70]) * t) * (1 + streak)
    m = lab == inv.get("vine", -9)
    if m.any():
        out[m] = np.array([0.36, 0.42, 0.14]) * (0.85 + 0.3 * np.random.default_rng(1).random((m.sum(), 1)))
    m = lab == inv.get("eye", -9)
    if m.any():
        out[m] = np.array([0.08, 0.05, 0.03])
    m = (lab == inv["body"]) & (P[..., 2] < 0.16)
    if m.any():                                     # hoof keratin
        k = np.clip((0.16 - P[m][:, 2]) / 0.06, 0, 1)[:, None]
        out[m] = out[m] * (1 - k) + np.array([0.20, 0.17, 0.15]) * k
    return out


def roughness_extra(B, rough, T, lab):
    inv = {v: k for k, v in B.label_names.items()}
    m = (lab == inv["body"]) & (T.pos[..., 2] < 0.12)
    rough[m] = 0.5
    return rough


# --------------------------------------------------------------------------- animation

PIVOT = S(370, 170)
ANIM = dict(
    spine=["spine_01", "spine_02", "spine_03"], neck=["neck_01", "neck_02"], tail=TAIL,
    mane=["mane_01", "mane_02"], bones={"jaw", "ear_L", "ear_R"},
    tail_base=[0.0] * 3, tail_lag=0.09, idle_tail_sway=5.0, idle_tail_curl=2.0,
    walk=dict(T=33 / 30, speed=1.3, duty=0.64, height=-0.10,
              touchdown={"hind_L": 0.0, "fore_L": 0.25, "hind_R": 0.5, "fore_R": 0.75},
              lift_f=0.16, lift_h=0.14, fold_f=60.0, fold_h=45.0, bob=0.03, sway=0.03, pitch=1.2, roll=2.2,
              yaw=1.5, spine_yaw=1.5, tail_sway=6.0, tail_lift=0.0, tail_bounce=2.0, ears=0.0,
              mane_bounce=5.0, head_nod=3.0),
    run=dict(T=22 / 30, speed=3.2, duty=0.42, touchdown={"fore_L": 0.0, "hind_R": 0.0, "fore_R": 0.5, "hind_L": 0.5},
             lift_f=0.24, lift_h=0.2, fold_f=75.0, fold_h=55.0, bob=0.05, bob_phase=0.0, sway=0.0, pitch=1.5,
             roll=1.5, yaw=1.0, spine_yaw=1.0, flex=2.0, tail_sway=4.0, tail_lift=8.0, tail_bounce=5.0,
             ears=-10.0, mane_bounce=8.0, head_nod=4.0, height=-0.07),
    alert_pose=dict(body=(0.0, 0.05, -0.05, -2.0, 0.0, 0.0),
                    rot={"neck_01": (10.0, 0, 0), "neck_02": (6.0, 0, 0), "head": (6.0, 0, 0)}, tail_lift=8.0),
    death_lie=(-0.9, 84.0), roar_neck=16.0, roar_head=18.0, roar_jaw=26.0, mane_bristle=6.0,
)


def attack(C, P):
    """Antler charge: head drops (antlers forward), 3 driving steps in place while the body lunges,
    upward antler sweep at contact (0.70 s), recover."""
    import ganim
    from ganim import keys_cr, keys_smooth
    import gclips
    A = P["alert_pose"]
    ab = tuple(A["body"])
    body_k = [(0, ab), (0.18, (0, 0.12, -0.08, -4, 0, 0)), (0.35, (0, -0.15, -0.12, -6, 0, 0)),
              (0.55, (0, -0.55, -0.10, -7, 0, 2)), (0.70, (0, -0.85, -0.02, 6, 0, -3)),
              (0.85, (0, -0.78, -0.06, 2, 0, 0)), (1.05, (0, -0.35, -0.06, -1, 0, 0)), (1.3, ab)]
    rot_k = {"neck_01": [(0, (10, 0, 0)), (0.3, (26, 0, 0)), (0.6, (30, 0, 0)), (0.7, (-6, 0, -8)),
                         (0.85, (4, 0, 0)), (1.3, (10, 0, 0))],
             "neck_02": [(0, (6, 0, 0)), (0.3, (18, 0, 0)), (0.62, (20, 0, 0)), (0.7, (-10, 0, -6)),
                         (0.88, (2, 0, 0)), (1.3, (6, 0, 0))],
             "head": [(0, (6, 0, 0)), (0.3, (24, 0, 0)), (0.62, (26, 0, 0)), (0.7, (-14, 0, 0)), (0.9, (0, 0, 0)),
                      (1.3, (6, 0, 0))],
             "jaw": [(0, (2, 0, 0)), (0.7, (10, 0, 0)), (1.0, (3, 0, 0)), (1.3, (2, 0, 0))],
             "spine_01": [(0, (0, 0, 0)), (0.35, (-3, 0, 0)), (0.7, (3, 0, 0)), (1.3, (0, 0, 0))]}
    steps = {"fore_L": [0.12, 0.40], "fore_R": [0.26, 0.54], "hind_L": [0.20, 0.48], "hind_R": [0.33, 0.62]}
    adv = 0.85

    def foot_keys(leg):
        ks = [(0, 0.0, 0.0)]
        pos = 0.0
        for i, t0 in enumerate(steps[leg]):
            nxt = adv * (i + 1) / len(steps[leg])
            ks += [(t0, pos, 0.0), (t0 + 0.07, (pos + nxt) / 2, 0.22), (t0 + 0.14, nxt, 0.0)]
            pos = nxt
        back = 0.95 + (0.08 if leg.startswith("hind") else 0.0)
        ks += [(back, pos, 0.0), (back + 0.08, pos / 2, 0.18), (back + 0.16, 0.0, 0.0), (1.3, 0.0, 0.0)]
        return ks

    fk = {leg: foot_keys(leg) for leg in C.legs}

    def frame(t):
        body = tuple(keys_cr(t, body_k))
        rot = {b: tuple(keys_cr(t, k)) for b, k in rot_k.items()}
        for b in ("ear_L", "ear_R"):
            rot[b] = (-25.0 * ganim.ss(t / 0.3), 0, 0)
        rot.update(gclips.tail_rot(P, t, lift=12.0, sway=8.0, freq=2.0, lag=0.09))
        for b in P["mane"]:
            rot[b] = (8.0 * math.sin(2 * math.pi * 2.5 * t), 0, 0)
        feet = {}
        for leg in C.legs:
            v = keys_smooth(t, [(k[0], np.array(k[1:])) for k in fk[leg]])
            n = C.neutral[leg]
            lifting = v[1] > 0.01
            feet[leg] = dict(pos=n + np.array([0.0, -v[0], v[1]]), meta=40.0 * min(1.0, v[1] / 0.2),
                             toe=20.0 * min(1.0, v[1] / 0.2), girdle=0.0)
        return dict(body=body, rot=rot, feet=feet)
    return ganim.sample(frame, 1.3), {"markers": {"contact": 0.70}}


LEVELS = {
    "L1": {"game_scale": 1.18, "sites": [], "baseColorFactor": [1, 1, 1, 1], "show_nodes": [],
           "look": "brown shaggy coat, mossy back, 12-point antlers (not used by the campaign)"},
    "L2": {"game_scale": 1.34, "sites": ["lf_site_05"], "baseColorFactor": [0.88, 0.86, 0.84, 1.0],
           "show_nodes": ["lf_guardian_velkor_L2"], "look": "darker coat, extra antler tines"},
    "L3": {"game_scale": 1.50, "sites": ["lf_site_08"], "baseColorFactor": [0.76, 0.74, 0.72, 1.0],
           "show_nodes": ["lf_guardian_velkor_L2", "lf_guardian_velkor_L3"],
           "look": "darkest coat, extra tines + heavy brow tines and long hanging vines"},
}
NOTES = ("Velkor: level scale applied by the game (1.02+0.16*level).  Level looks via baseColorFactor and the "
         "hidden-by-default nodes listed in levels.Lx.show_nodes (KHR_node_visibility).  Attack = antler charge "
         "with contact 0.70 s (the game's 'antler_charge' event plays Alert as wind-up first).  Run = trot.")


def sockets(sk):
    return {"mouth": S(640, 142), "head_top": S(560, -20), "antler_tip_L": S(380, 5, 1.2), "chest": S(540, 200),
            "hit_center": S(370, 170), "tail_tip": sk.tail("tail_03")}


def level_geometry(B):
    import gfur
    ant = [i for i, d in enumerate(B.details) if d["kind"] == "antler"]
    src = ant[1]                         # a tine (sides=5, n=6) -> UV island reused
    out = {"L2": [], "L3": []}
    for sx in (1, -1):
        base = S(566, 90, 0.15 * sx)
        out["L2"].append((gfur.horn(base + np.array([0.75 * sx, 0.38, 0.47]), np.array([0.2 * sx, -0.3, 1.0]),
                                    np.array([0, 0.08, -0.1]), 0.42, 0.04, sides=5, n=6), src, "head"))
        out["L2"].append((gfur.horn(base + np.array([1.05 * sx, 0.6, 0.56]), np.array([0.3 * sx, 0.1, 1.0]),
                                    np.array([0, 0.08, -0.1]), 0.36, 0.035, sides=5, n=6), src, "head"))
        out["L3"].append((gfur.horn(base + np.array([0.1 * sx, 0.0, 0.08]), np.array([0.25 * sx, -1.0, 0.25]),
                                    np.array([0, 0.0, 0.25]), 0.48, 0.05, sides=5, n=6), src, "head"))
    return out


HEAD_VIEWS = {
    "side": {"sheet": "11", "box": (1110, 0, 1536, 345), "kind": "persp",
             "cam": S(600, 120) + np.array([-2.6, -1.1, 0.25]), "look": S(585, 100), "lens": 50.0},
}


CLUMP_TAPER = 0.55            # long hair locks end blunt (not spikes)
TIP_LIGHTEN = (0.55, 0.45, (0.78, 0.66, 0.50))   # strength, distance from skin (m), light hair colour
