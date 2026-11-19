"""lf_mechanism_trail_cache from art/10_artifact_mechanisms.png (upper left): fallen log made of split oak staves
(hollow), a cache recess on top holding bronze tree tokens, a sliding plank lid with an iron strap + bronze ring
(slides along the log), iron latch block at the near end, white-moss boulder behind, split birch stump (landmark
'split_birch'), bracket fungi, forest-floor patch. The three trail landmarks are separate nodes so the game can
highlight them (mark_landmark_a = split birch, mark_landmark_b = white-moss rock, cache_lid = fallen trunk).
"""
import math

import numpy as np

import cagegeo as CG
import pv2

ID = "lf_mechanism_trail_cache"
ATLAS = 2048
SHEET = "10_artifact_mechanisms.png"
LIGHT = (-0.55, -0.45, 0.70)
BOX = (8, 70, 762, 390)
OPEN = 0.55

PARAMS = dict(R=0.45, L=3.3, ltx=-0.9, lx0=-0.15, lx1=0.75, lw=0.36, rx=-1.0, ry=1.3, sx_=-2.6, sy_=0.6)
FREE = ["L", "ltx", "lx0", "lx1", "lw", "rx", "ry", "sx_", "sy_"]


def points(p):
    R, L = p["R"], p["L"]
    zt = 2 * R
    return {
        "latch": (p["ltx"], -0.05, zt + 0.1), "near_end": (-L / 2, -R * 0.2, zt * 0.55), "ring": (p["lx1"] - 0.18 + OPEN, -0.2, zt + 0.1),
        "lid_a": (p["lx0"] + OPEN, -p["lw"], zt + 0.06), "lid_b": (p["lx1"] + OPEN, -p["lw"], zt + 0.06),
        "lid_c": (p["lx0"] + OPEN, p["lw"], zt + 0.06), "lid_d": (p["lx1"] + OPEN, p["lw"], zt + 0.06),
        "rock_top": (p["rx"], p["ry"], 1.55), "stump_top": (p["sx_"], p["sy_"], 1.15),
    }


def views():
    v = pv2.ViewSpec(
        "main", SHEET, BOX,
        {"latch": (340, 215), "ring": (582.5, 220), "near_end": (262, 290),
         "lid_a": (495, 262.5), "lid_b": (630, 222.5), "lid_c": (460, 200), "lid_d": (595, 167.5),
         "rock_top": (310, 82.5), "stump_top": (105, 100)},
        pose={"cache_lid": {"loc": (OPEN, 0, 0)}},
        light=LIGHT, thresh=0.085, fill_holes=True, shadow=None, solve_opts={"fov_prior": 20.0},
        title="TRAIL CACHE main view (lid slid open)")
    return [v]


def stave_ring(g, x0, x1, R, angles, w, t, lod, tag="stave", skip_range=None, gap=None):
    for k, a in enumerate(angles):
        c = np.array([0.0, R * math.cos(a), R + R * math.sin(a)])
        Rm = np.stack([np.array([1.0, 0, 0]), np.array([0, -math.sin(a), math.cos(a)]),
                       np.array([0, math.cos(a), math.sin(a)])], 1)
        segs = [(x0, x1)]
        if gap is not None and skip_range is not None and skip_range[0] <= a <= skip_range[1]:
            segs = [(x0, gap[0]), (gap[1], x1)]
        for (a0, a1) in segs:
            if a1 - a0 < 0.05:
                continue
            g.box(c + ((a0 + a1) / 2, 0, 0), (a1 - a0 - 0.01, w, t), R=Rm, mat="wood", tag=tag,
                  chamfer=0.03 if lod == 0 else 0.0)


def build(A, p, lod):
    R, L = p["R"], p["L"]
    g = A.g("root", lod)
    # ground patch (forest floor)
    n = 20 if lod == 0 else 10
    poly = np.array([((L / 2 + 0.9) * math.cos(a) - 0.4, 1.35 * math.sin(a) + 0.35) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)])
    g.prism(poly, 0.0, 0.03, "ground", "ground", caps=(False, True))
    # hollow log of split staves; cache opening between lx0-0.4 and lx1 on the top staves
    nst = 9 if lod == 0 else 6
    angles = [math.radians(a) for a in np.linspace(-90 - 140, -90 + 140, nst)]
    gap = (min(p["lx0"] - 0.1, p["ltx"] + 0.12), p["lx1"] + 0.02)
    stave_ring(g, -L / 2, L / 2, R * 0.93, angles, 2 * math.pi * R / nst * 1.05, 0.16, lod, skip_range=(math.radians(20), math.radians(160)), gap=gap)
    # end caps (cut ends, rings come from the painting)
    for xe in (-L / 2 + 0.03, L / 2 - 0.03):
        g.cyl((xe - 0.03, 0, R), (xe + 0.03, 0, R), R * 0.86, n=12 if lod == 0 else 8, mat="wood", tag="log_end",
              up=(0, 0, 1))
    # cache recess (dark box) + bronze tokens
    g.box(((gap[0] + gap[1]) / 2, 0, 2 * R - 0.25), (gap[1] - gap[0], 0.62, 0.36), mat="wood", tag="cache_box")
    if lod < 2:
        for k, (dx, dy, tilt) in enumerate(((-0.25, -0.05, 0.25), (-0.02, 0.08, -0.15), (0.2, -0.04, 0.35))):
            c = np.array([p["lx0"] - 0.2 + dx, dy, 2 * R - 0.02])
            Rm = CG.frame((math.cos(tilt), 0, math.sin(tilt) * 0.3), (0, -math.sin(0.5), math.cos(0.5)))
            g.cyl(c - Rm[:, 2] * 0.025, c + Rm[:, 2] * 0.025, 0.12, n=14 if lod == 0 else 8, mat="bronze", tag="token",
                  up=(1, 0, 0))
    # iron latch block at the near end of the opening
    g.box((p["ltx"], -0.05, 2 * R + 0.03), (0.22, 0.26, 0.14), mat="iron", tag="latch_block")
    # sliding lid (node): planks + iron strap + bronze ring; rest = closed over the opening
    lid = A.part("cache_lid", None, ((p["lx0"] + p["lx1"]) / 2, 0, 2 * R))
    lg = lid.geo[lod]
    for k in range(3):
        y = -p["lw"] + (k + 0.5) * (2 * p["lw"] / 3)
        lg.box(((p["lx0"] + p["lx1"]) / 2, y, 2 * R + 0.035), (p["lx1"] - p["lx0"], 2 * p["lw"] / 3 - 0.01, 0.07),
               mat="wood", tag="lid_plank")
    lg.box((p["lx1"] - 0.18, -0.02, 2 * R + 0.075), (0.06, 0.32, 0.012), mat="iron", tag="lid_strap")
    ring = [np.array([p["lx1"] - 0.18 + 0.075 * math.cos(a), -0.2, 2 * R + 0.1 + 0.075 * math.sin(a)]) for a in np.linspace(0, 2 * math.pi, 11)[:-1]]
    lg.tube(np.array(ring + [ring[0]]), 0.014, n=5, mat="bronze", tag="lid_ring")
    # white-moss boulder (landmark b)
    rk = A.part("mark_landmark_b", None, (p["rx"], p["ry"], 0))
    rk.geo[lod].rock((p["rx"], p["ry"], 0.62), (1.0, 0.8, 0.9), seed=4, sub=2 if lod == 0 else 1, mat="stone", tag="rock")
    # split birch stump (landmark a): two half trunks with a split gap
    st = A.part("mark_landmark_a", None, (p["sx_"], p["sy_"], 0))
    sg = st.geo[lod]
    nh = 10 if lod == 0 else 6
    for side in (-1, 1):
        half = [(0.36 * math.cos(a), side * 0.04 + side * 0.36 * abs(math.sin(a))) for a in np.linspace(-math.pi / 2, math.pi / 2, nh)]
        half = np.array([(x, y) for x, y in half])
        if side < 0:
            half = half[::-1]
        poly = np.array([(p["sx_"] + 0, 0) for _ in range(0)])
        pts = np.array([(y, x) for x, y in half])
        pts = pts if side > 0 else pts
        g2 = np.array([(px_, py_) for px_, py_ in pts])
        # D-shaped prism (flat face at the split)
        ang = np.linspace(-math.pi / 2, math.pi / 2, nh)
        D = np.array([(0.36 * math.sin(a), side * (0.03 + 0.36 * math.cos(a))) for a in ang])
        if side > 0:
            D = D[::-1]
        sg.prism(D, 0.0, 1.05 + (0.08 if side > 0 else 0.0), "birch", "stump", t=(p["sx_"], p["sy_"], 0))
    # bracket fungi on the far end
    if lod < 2:
        for k, (dz, dx) in enumerate(((0.62, 0.0), (0.42, 0.1))):
            c = np.array([L / 2 - 0.25 + dx, -R * 0.75, dz + 0.4])
            g.cyl(c, c + (0, 0, 0.05), 0.18 - 0.03 * k, n=10 if lod == 0 else 6, mat="fungus", tag="fungus")
    if lod == 0:
        A.marker("artifact_spot", ((p["lx0"] + p["lx1"]) / 2 - 0.2, 0, 2 * R - 0.05))
    return A


SWATCHES = {
    "wood": dict(sheet=SHEET, box=(380, 205, 420, 225), metres=0.5),
    "stone": dict(sheet=SHEET, box=(240, 95, 290, 135), metres=0.8),
    "birch": dict(sheet=SHEET, box=(60, 140, 90, 200), metres=0.6),
    "bronze": dict(sheet=SHEET, box=(408, 252, 430, 268), metres=0.15),
    "iron": dict(sheet=SHEET, box=(316, 205, 340, 222), metres=0.15),
    "ground": dict(sheet=SHEET, box=(560, 325, 640, 360), metres=0.9),
    "fungus": dict(sheet=SHEET, box=(668, 172, 690, 186), metres=0.2),
}


def clips(A, B):
    pv2.add_clip(A, B, "lf_trail_mark_1", 1.0, {"mark_landmark_a": lambda t: {"loc": (0, 0, 0.03 * math.sin(math.pi * t))}},
                 note="landmark 1 (split birch) acknowledged: small settle bump")
    pv2.add_clip(A, B, "lf_trail_mark_2", 1.0, {"mark_landmark_b": lambda t: {"loc": (0, 0, 0.03 * math.sin(math.pi * t))}},
                 note="landmark 2 (white-moss rock) acknowledged")
    pv2.add_clip(A, B, "lf_lock_mechanism", 1.4, {"cache_lid": lambda t: {"loc": (OPEN * pv2.ease_io((t - 0.15) / 1.1), 0, 0)}},
                 markers={"cache_open": 1.25}, note="log hatch slides open along the log (solved pose = last frame)")
    pv2.add_clip(A, B, "lf_trail_cache_close", 1.0, {"cache_lid": lambda t: {"loc": (OPEN * (1 - pv2.ease_io(t)), 0, 0)}},
                 note="hatch slides closed")


def meta(A, p):
    g = pv2.b2g
    return {"mechanism": "trail_cache",
            "steps": {"split_birch": "lf_trail_mark_1 (node mark_landmark_a)",
                      "white_moss": "lf_trail_mark_2 (node mark_landmark_b)",
                      "fallen_trunk": "lf_lock_mechanism (node cache_lid slides +X 0.55 m)"},
            "solved_clip": "lf_lock_mechanism (hold last frame)",
            "sockets": {"artifact": g(((p["lx0"] + p["lx1"]) / 2 - 0.2, 0, 2 * p["R"] - 0.05))}}
