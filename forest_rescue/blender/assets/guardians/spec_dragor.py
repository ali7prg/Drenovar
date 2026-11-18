"""DRAGOR — ankylosaur-like stone-plated colossus (art/11_other_guardians_direction.png, bottom row).

Head to image-right; 118 px/m (tail tip -> snout 6.29 m, original prototype 6.31 m); ground 984.
Stone plates and tail spikes are real faceted geometry (rigid per nearest bone); skin is pebbled
via the normal map; moss tufts are small geometric clumps.
"""
import math

import numpy as np

import gref
import grig
import gspec
from gbody import Part, loft, stretch
from frlib import sdf, texproj

ID = "lf_guardian_dragor"
SPECIES = "dragor"
SH = gspec.Sheet(118.0, 984, 400.0, "right")
S = SH.S
PPM, GROUND = SH.ppm, SH.ground


def panels():
    side = gref.Panel("side", "11", (0, 685, 770, 990), "right", PPM, GROUND, 400.0, thresh=0.10, clip_below=988, fill_holes=2500,
                      extra_mask_fn=gspec.shadow_fn(968))
    front = gref.Panel("front", "11", (795, 685, 1140, 990), "front", PPM, GROUND, 969.0, thresh=0.10, fill_holes=2500,
                       clip_below=988, extra_mask_fn=gspec.shadow_fn(968))
    return {"side": side, "front": front}


LEGS = {
    "fore_L": ["scapula_L", "upperarm_L", "forearm_L", "hand_L", "fingers_L"],
    "fore_R": ["scapula_R", "upperarm_R", "forearm_R", "hand_R", "fingers_R"],
    "hind_L": [None, "thigh_L", "shin_L", "foot_L", "toes_L"],
    "hind_R": [None, "thigh_R", "shin_R", "foot_R", "toes_R"],
}
TAIL = ["tail_01", "tail_02", "tail_03", "tail_04"]


def skeleton():
    up, fwd = (0, 0, 1), (0, -1, 0)
    B = []

    def bone(name, head, tail, parent, z=up):
        B.append(dict(name=name, head=np.asarray(head, float), tail=np.asarray(tail, float), parent=parent, z=z))
    LS, TB, TL, T8, C7, MN, AT = S(270, 812), S(212, 838), S(380, 795), S(500, 790), S(610, 802), S(640, 806), S(668, 812)
    bone("root", (0, 0, 0), (0, -0.4, 0), None)
    bone("hips", LS, TB, "root")
    bone("spine_01", LS, TL, "hips")
    bone("spine_02", TL, T8, "spine_01")
    bone("spine_03", T8, C7, "spine_02")
    bone("neck_01", C7, MN, "spine_03")
    bone("neck_02", MN, AT, "neck_01")
    bone("head", AT, S(748, 848), "neck_02")
    bone("jaw", S(690, 842), S(736, 868), "head", (0, 0, -1))
    pts = [TB, S(158, 872), S(108, 903), S(62, 928), S(18, 946)]
    prev = "hips"
    for i, n in enumerate(TAIL):
        bone(n, pts[i], pts[i + 1], prev)
        prev = n
    for s, sx in (("L", 1), ("R", -1)):
        bone(f"scapula_{s}", S(560, 790, 0.55 * sx), S(588, 872, 0.84 * sx), "spine_03", fwd)
        bone(f"upperarm_{s}", S(588, 872, 0.84 * sx), S(565, 922, 0.90 * sx), f"scapula_{s}", fwd)
        bone(f"forearm_{s}", S(565, 922, 0.90 * sx), S(560, 960, 0.92 * sx), f"upperarm_{s}", fwd)
        bone(f"hand_{s}", S(560, 960, 0.92 * sx), S(562, 972, 0.93 * sx), f"forearm_{s}", fwd)
        bone(f"fingers_{s}", S(562, 972, 0.93 * sx), S(596, 980, 0.93 * sx), f"hand_{s}", up)
        bone(f"thigh_{s}", S(272, 828, 0.62 * sx), S(298, 900, 0.84 * sx), "hips", fwd)
        bone(f"shin_{s}", S(298, 900, 0.84 * sx), S(262, 952, 0.88 * sx), f"thigh_{s}", fwd)
        bone(f"foot_{s}", S(262, 952, 0.88 * sx), S(264, 971, 0.89 * sx), f"shin_{s}", fwd)
        bone(f"toes_{s}", S(264, 971, 0.89 * sx), S(296, 980, 0.89 * sx), f"foot_{s}", up)
    return grig.Skeleton(B)


def _foot(P, sk, digit_bone, sx, w=1.0):
    """Elephantine foot: broad pad + 4 toes (nails are tubes in details)."""
    a, b = sk.head(digit_bone), sk.tail(digit_bone)
    c = np.array([a[0], a[1], 0.0])
    fwd = np.array([0.0, (b - a)[1], 0.0])
    fwd /= np.linalg.norm(fwd)
    P.append(Part(sdf.ellipsoid(c + fwd * 0.08 + np.array([0, 0, 0.13]), (0.26 * w, 0.27, 0.14)), digit_bone,
                  k=0.06, tag="foot"))
    for ox in (-0.18, -0.06, 0.06, 0.18):
        P.append(Part(sdf.ellipsoid(c + fwd * 0.26 + np.array([ox * w, 0, 0.08]), (0.07, 0.09, 0.08)), digit_bone,
                      k=0.03, tag="toe"))


def nail_roots(sk, digit_bone, w=1.0):
    a, b = sk.head(digit_bone), sk.tail(digit_bone)
    c = np.array([a[0], a[1], 0.0])
    fwd = np.array([0.0, (b - a)[1], 0.0])
    fwd /= np.linalg.norm(fwd)
    return [(c + fwd * 0.32 + np.array([ox * w, 0, 0.075]), fwd) for ox in (-0.18, -0.06, 0.06, 0.18)]


def body_parts(sk):
    P = []
    prof = [(150, 848, 905, 0.20), (200, 802, 930, 0.62), (260, 765, 942, 0.86), (330, 736, 946, 1.00),
            (400, 726, 946, 1.04), (470, 728, 944, 1.04), (540, 742, 940, 0.98), (600, 768, 925, 0.82),
            (640, 796, 902, 0.58), (668, 806, 882, 0.40)]
    prof = sorted(prof, key=lambda r: -r[0])
    Y = [S(x, 0)[1] for x, *_ in prof]
    zt = [S(0, t)[2] for _, t, b, w in prof]
    zb = [S(0, b)[2] for _, t, b, w in prof]
    w = [w for *_, w in prof]
    P.append(Part(loft(Y, zt, zb, w, bone="spine_02"), "spine_02", k=0.0, tag="torso"))
    hd = "head"
    P.append(Part(sdf.ellipsoid(S(690, 822), (0.36, 0.24, 0.20)), hd, k=0.08, tag="cranium"))
    P.append(Part(sdf.round_cone(S(700, 830), S(742, 846), 0.20, 0.13), hd, k=0.06, tag="snout"))
    P.append(Part(sdf.round_cone(S(694, 852), S(734, 866), 0.14, 0.09), "jaw", k=0.03, tag="jaw"))
    P.append(Part(sdf.box(S(716, 858), (0.20, 0.20, 0.006), rot=(math.radians(20), 0, 0), rounding=0.004), hd,
                  k=0.008, op="subtract", tag="mouth"))
    for sx in (1, -1):
        P.append(Part(sdf.ellipsoid(S(704, 822, 0.24 * sx), (0.025, 0.03, 0.02)), hd, k=0.01, op="subtract",
                      tag="eyesocket"))
        P.append(Part(sdf.ellipsoid(S(698, 812, 0.22 * sx), (0.09, 0.09, 0.06)), hd, k=0.04, tag="brow"))
        P.append(Part(sdf.ellipsoid(S(672, 830, 0.30 * sx), (0.12, 0.12, 0.10)), hd, k=0.05, tag="cheekhorn"))
    for s, sx in (("L", 1), ("R", -1)):
        sc, ua, fa, ha, fi = LEGS[f"fore_{s}"]
        Sj, E, Wr, M = sk.head(ua), sk.head(fa), sk.head(ha), sk.head(fi)
        P.append(Part(sdf.ellipsoid(S(580, 860, 0.78 * sx), (0.30, 0.33, 0.33)), sc, k=0.12, tag="shoulder"))
        P.append(Part(sdf.round_cone(Sj, E, 0.27, 0.24), ua, k=0.08, tag="upperarm"))
        P.append(Part(sdf.round_cone(E, Wr, 0.24, 0.21), fa, k=0.06, tag="forearm"))
        P.append(Part(sdf.round_cone(Wr, M, 0.21, 0.22), ha, k=0.05, tag="hand"))
        _foot(P, sk, fi, sx, 1.1)
        th, sh, ft, to = LEGS[f"hind_{s}"][1:]
        H, K, Hk, Mt = sk.head(th), sk.head(sh), sk.head(ft), sk.head(to)
        P.append(Part(sdf.ellipsoid(S(280, 840, 0.62 * sx), (0.32, 0.38, 0.36)), "hips", k=0.12, tag="haunch"))
        P.append(Part(sdf.round_cone(H, K, 0.30, 0.25), th, k=0.08, tag="thigh"))
        P.append(Part(sdf.round_cone(K, Hk, 0.24, 0.20), sh, k=0.06, tag="shin"))
        P.append(Part(sdf.round_cone(Hk, Mt, 0.20, 0.21), ft, k=0.05, tag="ankle"))
        _foot(P, sk, to, sx, 1.0)
    for i, n in enumerate(TAIL):
        r0 = 0.30 - 0.065 * i
        P.append(Part(stretch(sdf.round_cone(sk.head(n), sk.tail(n), r0, r0 - 0.06), 1.25, center=sk.head(n)), n,
                      k=0.06, tag="tail"))
    return P


SEED = 1301
VOXEL = 0.018
BODY_TRIS = (8200, 4200, 1900)
CLUMP_KEEP = (1.0, 0.4, 0.0)
CLUMP_WIDTH = (1.0, 1.4, 2.0)
CLUMP_UV_SCALE = 0.5
DETAIL_UV_SCALE = 0.9


def fur(sk, hv, hf, pans, rng):
    """Moss tufts on the shell (small flat blades)."""
    import gfur
    xy = SH.xy

    def w(c, n):
        x, y = xy(c)
        return (n[:, 2] > 0.5) * gspec.ss(200, 240, x) * (1 - gspec.ss(600, 640, x))
    r, nr = gspec.roots(hv, hf, rng, 70, w, 0.16)
    return gfur.make_clumps("moss", r, nr, lambda p, n, rng: n * 0.6 + rng.normal(0, 0.4, 3), rng, [], 0.12,
                            min_len=0.05, width=(0.06, 0.1), flat=0.25, fit=False,
                            bend_fn=lambda p, n, d, rng: -n * 0.4, up_fn=lambda p, n, d: np.cross(d, n),
                            jag=(0.6, 1.0))


def _nearest_bone(sk, c, bones):
    best, bb = 9.0, bones[0]
    for b in bones:
        a, t = sk.head(b), sk.tail(b)
        ab = t - a
        u = np.clip(((c - a) @ ab) / (ab @ ab), 0, 1)
        d = np.linalg.norm(c - (a + u * ab))
        if d < best:
            best, bb = d, b
    return bb


def details(sk, hv=None, hf=None, pans=None):
    import gfur
    import gbody as gb
    rng = np.random.default_rng(11)
    D = []
    xy = SH.xy
    for s, sx in (("L", 1), ("R", -1)):
        D.append(dict(mesh=gb.uv_sphere(S(704, 822, 0.235 * sx), 0.022, 8, 6), bone="head", kind="eye", lods=(0, 1, 2)))
        for leg, w in ((f"fore_{s}", 1.1), (f"hind_{s}", 1.0)):
            db = LEGS[leg][4]
            for p, fw in nail_roots(sk, db, w):
                D.append(dict(mesh=gfur.claw(p, fw, length=0.10, base_r=0.04, curl=0.55, lat=(1, 0, 0)), bone=db,
                              kind="nail", lods=(0, 1)))
    if hv is None:
        return D
    bones = [b for b in sk.deform if b not in ("root",) and not b.startswith(("upperarm", "forearm", "hand",
                                                                               "fingers", "shin", "foot", "toes"))]
    # shell plates: big on top, smaller on the flanks; shingled backwards
    def w_shell(c, n):
        x, y = xy(c)
        return (n[:, 2] > -0.1) * gspec.ss(150, 190, x) * (1 - gspec.ss(650, 670, x)) * (y < 900)
    r, nr = gspec.roots(hv, hf, rng, 170, w_shell, 0.18)
    side, front = pans["side"].view, pans["front"].view
    hull = [gref.morph_view(side, -1), gref.morph_view(front, 1)]
    for p, n in zip(r, nr):
        top = n[2]
        size = (0.15 + 0.12 * top) * rng.uniform(0.85, 1.12)
        hfit = gspec.fit_height(p, gfur._unit(n + np.array([0, 0.25, 0.1])), hull, 0.5)
        th = float(np.clip(hfit / 1.15, size * 0.3, size * 1.2)) * rng.uniform(0.85, 1.0)
        nrm = gfur._unit(n + np.array([0, 0.25, 0.1]))
        D.append(dict(mesh=gspec.rock_plate(p - n * 0.03, nrm, np.array([0, 1.0, 0.2]), size, th, sides=6, rng=rng),
                      bone=_nearest_bone(sk, p, bones), kind="plate", lods=(0, 1, 2) if size > 0.2 else (0, 1)))
    # head armour plates
    def w_head(c, n):
        x, y = xy(c)
        return (n[:, 2] > 0.2) * gspec.ss(660, 675, x) * (1 - gspec.ss(735, 745, x))
    r, nr = gspec.roots(hv, hf, rng, 14, w_head, 0.11)
    for p, n in zip(r, nr):
        D.append(dict(mesh=gspec.rock_plate(p - n * 0.02, n, np.array([0, 1.0, 0]), 0.09, 0.05, sides=6, rng=rng),
                      bone="head", kind="plate", lods=(0, 1)))
    # tail spikes: paired lateral spikes along the tail (pointed scutes)
    for i, b in enumerate(TAIL):
        a, t = sk.head(b), sk.tail(b)
        for f in (0.3, 0.8):
            p = a + (t - a) * f
            rad = 0.26 - 0.06 * (i + f)
            for sx in (1, -1):
                base = p + np.array([sx * rad * 1.1, 0, 0.05])
                D.append(dict(mesh=gfur.horn(base, np.array([sx * 0.9, 0.35, 0.35]), np.array([0, 0.25, 0.0]),
                                             0.26 - 0.03 * i, 0.07 - 0.008 * i, sides=6, n=7),
                              bone=b, kind="spike", lods=(0, 1, 2)))
            D.append(dict(mesh=gfur.horn(p + np.array([0, 0, rad * 0.9]), np.array([0, 0.5, 0.9]),
                                         np.array([0, 0.2, 0.0]), 0.18 - 0.02 * i, 0.06 - 0.008 * i, sides=6, n=7),
                          bone=b, kind="spike", lods=(0, 1)))
    return D


def weight_sources(sk, parts):
    src = [(p.prim, p.bone) for p in parts if p.op == "union" and p.tag != "torso"]
    caps = {"hips": 0.75, "spine_01": 0.85, "spine_02": 0.9, "spine_03": 0.85, "neck_01": 0.45, "neck_02": 0.38}
    for b, r in caps.items():
        src.append((sdf.round_cone(sk.head(b), sk.tail(b), r, r * 0.9), b))
    return src


RIGID_KINDS = {"eye", "nail", "plate", "spike"}
LOD_REMAP = {
    1: {"fingers_L": "hand_L", "fingers_R": "hand_R", "toes_L": "foot_L", "toes_R": "foot_R", "tail_04": "tail_03"},
    2: {"fingers_L": "hand_L", "fingers_R": "hand_R", "toes_L": "foot_L", "toes_R": "foot_R", "tail_04": "tail_03",
        "tail_02": "tail_01", "jaw": "head", "spine_01": "hips", "neck_01": "spine_03", "scapula_L": "spine_03",
        "scapula_R": "spine_03", "hand_L": "forearm_L", "hand_R": "forearm_R", "neck_02": "spine_03"},
}
PROJECTION = [("side", "side"), ("front", "bind")]
COMPARE = [("side", "side"), ("front", "bind")]
WEIGHT_FALLOFF = 0.07
NORMAL_STRENGTH = 6.0
ROUGHNESS = {"body": 0.84, "fur_moss": 0.95, "eye": 0.06, "nail": 0.5, "plate": 0.78, "spike": 0.7}


def side_stance(sk):
    return gspec.stance(sk, LEGS, SH, {
        "fore_L": ((566, 972), (0.0, 1.0)), "fore_R": ((515, 972), (-0.1, 1.0)),
        "hind_L": ((232, 972), (-0.2, 1.0)), "hind_R": ((352, 972), (0.1, 1.0))})


def height_fn(P, N):
    """Pebbled reptile skin (voronoi pebbles) instead of fur strands."""
    f1, f2 = texproj.voronoi(P, freq=14.0, seed=5)
    peb = np.clip((f2 - f1) * 16.0, 0, 1)
    fine = texproj.fbm(P, freq=60.0, octaves=3, seed=9)
    return 0.7 * peb + 0.3 * fine


def texture_overrides(B, col, T, lab):
    inv = {v: k for k, v in B.label_names.items()}
    out = col.copy()
    for nm, c in (("nail", (0.62, 0.56, 0.46)), ("eye", (0.12, 0.08, 0.03))):
        m = lab == inv.get(nm, -9)
        if m.any():
            out[m] = c
    m = lab == inv.get("fur_moss", -9)
    if m.any():
        out[m] = out[m] * 0.4 + np.array([0.36, 0.40, 0.16]) * 0.6
    return out


PIVOT = S(400, 860)
ANIM = dict(
    spine=["spine_01", "spine_02", "spine_03"], neck=["neck_01", "neck_02"], tail=TAIL, mane=[],
    bones={"jaw"}, tail_base=[0.0] * 4, tail_lag=0.12, idle_tail_sway=6.0, idle_tail_curl=1.5,
    walk=dict(T=33 / 30, speed=1.0, duty=0.68, height=-0.07,
              touchdown={"hind_L": 0.0, "fore_L": 0.25, "hind_R": 0.5, "fore_R": 0.75},
              lift_f=0.12, lift_h=0.11, fold_f=35.0, fold_h=30.0, bob=0.02, sway=0.03, pitch=0.8, roll=1.4, heel=16.0,
              yaw=2.5, spine_yaw=2.0, tail_sway=9.0, tail_lift=0.0, tail_bounce=1.5, head_nod=1.5),
    run=dict(T=24 / 30, speed=1.7, duty=0.55, height=-0.09, touchdown={"hind_L": 0.0, "fore_L": 0.22, "hind_R": 0.5, "fore_R": 0.72},
             lift_f=0.16, lift_h=0.14, fold_f=40.0, fold_h=32.0, bob=0.03, sway=0.03, pitch=1.0, roll=1.8, yaw=3.0, heel=16.0,
             spine_yaw=2.5, tail_sway=12.0, tail_lift=2.0, tail_bounce=3.0, head_nod=2.0),
    alert_pose=dict(body=(0.0, 0.04, -0.04, -2.0, 0.0, 0.0),
                    rot={"neck_01": (6.0, 0, 0), "neck_02": (4.0, 0, 0), "head": (2.0, 0, 0)}, tail_lift=6.0),
    death_lie=(-0.5, 70.0), roar_neck=10.0, roar_head=12.0, roar_jaw=30.0,
)


def attack(C, P):
    """Tail bash: wind-up (hips turn left, tail cocks left) -> whip to the right through the target at
    contact 0.70 s (with a short head swing) -> recover.  Feet stay planted (heavy animal)."""
    import ganim
    import gclips
    from ganim import keys_cr
    ab = tuple(P["alert_pose"]["body"])
    body_k = [(0, ab), (0.25, (0.05, 0.05, -0.06, -2, 3, 14)), (0.45, (0.06, 0.04, -0.08, -2, 4, 18)),
              (0.62, (-0.02, 0.0, -0.06, -1, -2, -4)), (0.72, (-0.08, -0.02, -0.04, 0, -4, -16)),
              (0.9, (-0.05, 0.0, -0.05, -1, -2, -10)), (1.3, ab)]
    tail_wave = [(0, 0), (0.25, 1.0), (0.48, 1.25), (0.64, -0.4), (0.72, -1.4), (0.82, -1.1), (1.05, -0.3), (1.3, 0)]
    head_k = [(0, (2, 0, 0)), (0.45, (4, 0, 12)), (0.70, (-6, 0, -14)), (0.9, (0, 0, -6)), (1.3, (2, 0, 0))]

    def frame(t):
        body = tuple(keys_cr(t, body_k))
        rot = {"head": tuple(keys_cr(t, head_k)), "neck_01": tuple(np.asarray(keys_cr(t, head_k)) * 0.6),
               "jaw": (8.0 * math.sin(math.pi * min(1.0, t / 1.3)), 0, 0)}
        for i, b in enumerate(P["spine"]):
            rot[b] = (0, 0, float(keys_cr(t, body_k)[5]) * -0.15)
        tw = lambda i, tt: (6.0 * (i + 1) / 4, 18.0 * (0.6 + 0.4 * i) * float(keys_cr(max(0.0, tt - 0.035 * i), tail_wave)))
        rot.update(gclips.tail_rot(P, t, extra=tw))
        feet = gclips.planted(C)
        return dict(body=body, rot=rot, feet=feet)
    return ganim.sample(frame, 1.3), {"markers": {"contact": 0.70}}


LEVELS = {
    "L1": {"game_scale": 1.18, "sites": [], "baseColorFactor": [1, 1, 1, 1], "show_nodes": [],
           "look": "slate-brown stone plates with moss (not used by the campaign)"},
    "L2": {"game_scale": 1.34, "sites": ["lf_site_10"], "baseColorFactor": [0.88, 0.87, 0.86, 1.0],
           "show_nodes": ["lf_guardian_dragor_L2"], "look": "darker stone, extra dorsal spike row"},
    "L3": {"game_scale": 1.50, "sites": ["lf_site_11", "lf_site_12"], "baseColorFactor": [0.76, 0.75, 0.75, 1.0],
           "show_nodes": ["lf_guardian_dragor_L2", "lf_guardian_dragor_L3"],
           "look": "darkest stone, dorsal spike row + brow horns (lf_site_12 adds ancient_watch modifier in data)"},
}
NOTES = ("Dragor: stone plates/spikes rigid on the nearest bone, pebbled skin from the normal map.  Attack = tail "
         "bash (contact 0.70 s); the wide shock-wave of the campaign is a separate VFX/server event.  Run = fast "
         "lumbering walk (duty 0.55).  Level scale by the game.")


def sockets(sk):
    return {"mouth": S(740, 860), "head_top": S(690, 780), "tail_tip": sk.tail("tail_04"), "chest": S(620, 900),
            "hit_center": S(400, 860)}


def level_geometry(B):
    import gfur
    src = [i for i, d in enumerate(B.details) if d["kind"] == "spike"][0]
    out = {"L2": [], "L3": []}
    for k, x in enumerate((260, 320, 380, 440, 500, 560)):
        y = np.interp(x, [260, 400, 560], [778, 742, 760]) - 8
        b = "spine_01" if x < 380 else ("spine_02" if x < 500 else "spine_03")
        out["L2"].append((gfur.horn(S(x, y), np.array([0, 0.3, 1.0]), np.array([0, 0.15, 0]), 0.30, 0.08, sides=6, n=7),
                          src, b))
    for sx in (1, -1):
        out["L3"].append((gfur.horn(S(690, 806, 0.24 * sx), np.array([0.6 * sx, 0.6, 0.5]), np.array([0, 0.3, 0]),
                                    0.26, 0.06, sides=6, n=7), src, "head"))
    return out


HEAD_VIEWS = {
    "side": {"sheet": "11", "box": (1170, 690, 1536, 1010), "kind": "persp",
             "cam": S(700, 830) + np.array([-2.4, -1.2, 0.2]), "look": S(700, 830), "lens": 50.0},
}
