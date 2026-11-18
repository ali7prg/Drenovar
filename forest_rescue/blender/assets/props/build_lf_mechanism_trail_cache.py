"""lf_mechanism_trail_cache: split birch stump, white-moss boulder and a hollow fallen log whose sliding lid
hides the coin/token box.  Landmark A = stump, B = boulder, C = log cache (campaign symbols map to A/B/C in
solution order).  Step marks: white trail ribbons (scale 0 at rest) on A and B; the lid slides on solve.

Run: python3 forest_rescue/blender/run_limited.py .../build_lf_mechanism_trail_cache.py --iter N
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np

import mechkit as mk
import motifs as mo
import propkit as pk
import propshaders as sh
from propkit import M4, Rx, Ry, Rz
from frlib import sdf

ASSET = "lf_mechanism_trail_cache"
LOG_R = 0.33
LOG_X0, LOG_X1 = -0.35, 2.35
CUT_X0, CUT_X1 = 0.55, 1.45
LOG_Y = 0.0
TOP_Z = LOG_R * 2 * 0.80          # flat top of the trough (cut)
LID_SLIDE = 0.55
STUMP = np.array([-1.15, 0.50, 0.0])
STUMP_R, STUMP_H = 0.35, 0.98
BOULDER = np.array([0.25, 1.05, 0.0])
_ORG = {}


def boulder_pieces():
    if "b" in _ORG:
        return _ORG["b"]
    F = sdf.Field((-0.8, -0.65, -0.1), (0.8, 0.65, 1.0), 0.03)
    F.union_all([sdf.ellipsoid((0, 0, 0.38), (0.68, 0.52, 0.5), k=0.05),
                 sdf.ellipsoid((0.25, 0.1, 0.55), (0.35, 0.3, 0.32), k=0.12),
                 sdf.ellipsoid((-0.3, -0.05, 0.3), (0.38, 0.35, 0.3), k=0.12)])
    rng = np.random.RandomState(3)
    X, Y, Z = np.meshgrid(*F.axes, indexing="ij")
    P = np.stack([X, Y, Z], -1)
    from frlib import texproj
    n = texproj.fbm(P * 2.2, 1.0, 4, seed=5)
    F.d = (F.d + (n - 0.5) * 0.09).astype(np.float32)
    F.d = np.maximum(F.d, (0.02 - Z).astype(np.float32))      # flat bottom at ground
    V, Fc = F.mesh()
    _ORG["b"] = pk.organic_piece(V, Fc, 900, lod_ratios=(1.0, 0.5, 0.25), name="boulder")
    return _ORG["b"]


def build(lod):
    B = pk.Builder(lod)
    seg = B.seg(22, 14, 9)
    # ---------------- ground patch (dirt + moss + leaves)
    gp = pk.orient_toward(pk.lathe(np.array([[0.0, 0.03], [1.9, 0.0]]), seg, smooth=True), (0, 0, 1))
    B.add("root", "ground", "dirt", gp.transformed(M4(np.diag([1.0, 0.62, 1.0]), (0.55, 0.35, 0.0))), meta={"moss": 0.6})
    # ---------------- hollow log: solid ends + trough + bark rim
    for (x0, x1, nm) in ((LOG_X0, CUT_X0, "log_left"), (CUT_X1, LOG_X1, "log_right")):
        lg = pk.rod((x0, LOG_Y, LOG_R), (x1, LOG_Y, LOG_R), LOG_R, seg)
        B.add("root", nm, "log_bark", lg, meta={"moss": 0.7})
    # trough: outer arc + inner arc (ring segment), flat top at TOP_Z
    th0 = math.asin((TOP_Z - LOG_R) / LOG_R)
    arc = [(LOG_R * math.cos(a), LOG_R * math.sin(a)) for a in np.linspace(th0, math.pi - th0 - 2 * math.pi, max(8, seg))]
    ri = LOG_R - 0.06
    th1 = math.asin(np.clip((TOP_Z - LOG_R) / ri, -1, 1))
    arc_i = [(ri * math.cos(a), ri * math.sin(a)) for a in np.linspace(math.pi - th1 - 2 * math.pi, th1, max(6, seg - 4))]
    prof = np.array(arc + arc_i)       # (y, z-LOG_R) in the cross-section
    tr = pk.sweep(np.array([[CUT_X0, LOG_Y, LOG_R], [CUT_X1, LOG_Y, LOG_R]]), prof[:, ::-1] * np.array([1, 1]), up=(0, 0, 1),
                  smooth=True)
    B.add("root", "log_trough", "log_bark", tr, meta={"moss": 0.6})
    # inner wood floor of the compartment
    B.add("root", "log_inner", "plank", pk.beam((CUT_X0, LOG_Y, LOG_R - ri * 0.55), (CUT_X1, LOG_Y, LOG_R - ri * 0.55), ri * 1.4, 0.03))
    # bundle logs (front-left) + end grain
    for (y, z, r, x0, x1) in ((-0.42, 0.17, 0.17, LOG_X0 - 0.1, 1.2), (-0.30, 0.47, 0.13, LOG_X0 - 0.05, 0.6)):
        B.add("root", "bundle_logs", "log_bark", pk.rod((x0, y, z), (x1, y, z), r, B.seg(14, 9, 6)), meta={"moss": 0.5})
    # bracket fungi on the right end
    for k, (x, a) in enumerate(((1.95, -0.5), (2.15, -0.2), (2.05, 0.4))):
        fu = pk.lathe(np.array([[0.0, 0.0], [0.11, 0.0], [0.12, 0.02], [0.0, 0.035]]), B.seg(10, 6, 4), a0=-math.pi / 2,
                      a1=math.pi / 2, smooth=True)
        M = M4(Rz(-math.pi / 2 + a) , (x, LOG_Y - LOG_R * math.cos(a) * 0.98, LOG_R + LOG_R * math.sin(a) * 0.9 + 0.08))
        B.add("root", "fungi", "fungus", fu.transformed(M), max_lod=1)
    # coin box inside the trough + bronze tokens
    cb = pk.beam((0.75, LOG_Y, LOG_R - 0.02), (1.25, LOG_Y, LOG_R - 0.02), 0.26, 0.16, chamfer=0.01)
    B.add("root", "coin_box", "plank", cb)
    for k, (x, y) in enumerate(((0.86, -0.04), (1.0, 0.05), (1.13, -0.03))):
        coin = pk.extrude(pk.circle(0.05, B.seg(16, 10, 6)), 0.012, chamfer=0.002)
        cv = mo.Canvas((-0.05, -0.05, 0.05, 0.05), ppm=5000)
        mo.tree_emblem(cv, (0, 0.0), 0.06, 0.003)
        cv.ring((0, 0), 0.043, 0.003)
        B.add("root", "tokens", "bronze", coin.transformed(M4(Ry(0.2 * (k - 1)), (x, y, LOG_R + 0.065))),
              meta={"motif": [{"mask": cv.mask(0.0006), "bbox": (-0.05, -0.05, 0.05, 0.05), "isl": (2,), "depth": 0.0015, "mode": "raise"}]})
    # ---------------- lid node (planks + iron strap + ring handle node)
    lid_z = TOP_Z + 0.03
    for k in range(3):
        y = LOG_Y - 0.16 + k * 0.16
        pl = pk.beam((CUT_X0 - 0.02, y, lid_z), (CUT_X1 + 0.02, y, lid_z), 0.155, 0.05, chamfer=0.008)
        B.add("lid", "lid_planks", "plank", pl)
    for x in (CUT_X0 + 0.1, CUT_X1 - 0.1):
        st = pk.beam((x, LOG_Y - 0.25, lid_z + 0.03), (x, LOG_Y + 0.25, lid_z + 0.03), 0.05, 0.012, chamfer=0.003)
        B.add("lid", "lid_straps", "iron", st, meta={"rivets": {"du": 0.12, "v": [pk.rect_face_v(0.05, 0.012, 0.003, "+B")], "r": 0.008}})
    ring = np.array([[0.0, 0.045 * math.cos(a), 0.045 * math.sin(a)] for a in np.linspace(0, 2 * math.pi, B.seg(14, 9, 6), endpoint=False)])
    B.add("handle", "handle_ring", "bronze", pk.tube(ring + np.array([CUT_X1 - 0.22, LOG_Y, lid_z + 0.075]), 0.009, 5, closed_path=True,
                                                     up=(1, 0, 0)))
    B.add("lid", "handle_staple", "iron", pk.beam((CUT_X1 - 0.22, LOG_Y, lid_z + 0.026), (CUT_X1 - 0.22, LOG_Y, lid_z + 0.04), 0.05, 0.03))
    # ---------------- split birch stump (landmark A)
    sg = B.seg(12, 8, 6)
    for k, (a0, a1, off) in enumerate(((math.radians(-80), math.radians(95), 0.05), (math.radians(105), math.radians(275), -0.05))):
        prof = np.array([[STUMP_R * 1.12, 0.0], [STUMP_R * 1.02, 0.12], [STUMP_R, 0.45], [STUMP_R * 0.98, STUMP_H - 0.02 * k]])
        half = pk.lathe(prof, sg, a0=a0, a1=a1, smooth=True)
        am = (a0 + a1) / 2
        d = np.array([math.cos(am), math.sin(am), 0]) * abs(off)
        M = M4(Rz(0.0), STUMP + d)
        B.add("root", "stump_bark", "birch", half.transformed(M), meta={"moss": 0.4})
        # split face (inner wood): quad strip between the two radial edges
        e0 = np.array([math.cos(a0), math.sin(a0), 0])
        e1 = np.array([math.cos(a1), math.sin(a1), 0])
        top_h = STUMP_H - 0.02 * k
        face = pk.Piece(np.array([STUMP + d + e0 * STUMP_R * 1.12 * 0.0, STUMP + d + e0 * STUMP_R, STUMP + d + e0 * STUMP_R + [0, 0, top_h],
                                  STUMP + d + [0, 0, top_h], STUMP + d + e1 * STUMP_R + [0, 0, top_h], STUMP + d + e1 * STUMP_R]))
        face.add_face((0, 1, 2, 3), [(0, 0), (STUMP_R, 0), (STUMP_R, top_h), (0, top_h)], 1, False, 0)
        face.add_face((0, 3, 4, 5), [(0, 0), (0, top_h), (STUMP_R, top_h), (STUMP_R, 0)], 2, False, 0)
        cen = STUMP + d + np.array([math.cos(am), math.sin(am), 0]) * STUMP_R * 0.5
        pk._orient_faces_outward(face, range(len(face.F)), lambda c, fi, cc=cen: np.array([cc[0], cc[1], c[2]]))
        B.add("root", "stump_inner", "birch", face, meta={"inner_wood": 1})
        cap = pk.lathe(np.array([[0.0, top_h], [STUMP_R * 0.98, top_h]]), sg, a0=a0, a1=a1)
        cap.F = [tuple(reversed(f)) for f in cap.F]
        cap.UV = [list(reversed(u)) for u in cap.UV]
        B.add("root", "stump_top", "birch", cap.transformed(M4(None, d)) if False else cap.transformed(M4(None, STUMP + d)),
              meta={"inner_wood": 1})
    # ---------------- boulder (landmark B)
    bp = boulder_pieces()[lod]
    B.add("root", "boulder", "rock", bp.transformed(M4(Rz(0.3), BOULDER)), meta={"moss": 0.75})
    # ---------------- trail ribbons (marks) - scale 0 at rest
    rb = np.array([[STUMP_R * 1.06 * math.cos(a), STUMP_R * 1.06 * math.sin(a), 0.0] for a in np.linspace(0, 2 * math.pi, B.seg(16, 10, 6), endpoint=False)])
    rib = pk.sweep(rb + STUMP + np.array([0, 0, 0.52]), pk.rect(0.006, 0.07), closed_path=True, up=(0, 0, 1), smooth=True)
    tail = pk.beam(STUMP + np.array([0, -STUMP_R * 1.06, 0.52]), STUMP + np.array([0.06, -STUMP_R * 1.1 - 0.02, 0.3]), 0.05, 0.006)
    B.add("mark_1", "ribbon_1", "linen", pk.Piece.merge([rib, tail]))
    stick = pk.rod(BOULDER + np.array([-0.1, -0.2, 0.75]), BOULDER + np.array([-0.12, -0.25, 1.25]), 0.015, 5)
    flag = pk.beam(BOULDER + np.array([-0.12, -0.25, 1.22]), BOULDER + np.array([0.12, -0.32, 1.12]), 0.06, 0.006)
    B.add("mark_2", "ribbon_2", "linen", pk.Piece.merge([stick, flag]))
    return B


def spec():
    return {"root": {},
            "lid": {"pivot": (CUT_X0, LOG_Y, TOP_Z), "export_name": "cache_lid"},
            "handle": {"pivot": (CUT_X1 - 0.22, LOG_Y, TOP_Z + 0.06), "parent": "lid", "export_name": "cache_lid_ring"},
            "mark_1": {"pivot": tuple(STUMP + np.array([0, 0, 0.52])), "export_name": "mark_landmark_a"},
            "mark_2": {"pivot": tuple(BOULDER + np.array([-0.1, -0.2, 0.75])), "export_name": "mark_landmark_b"}}


def clips(A):
    ease = mk.ease
    for k, node in ((1, "mark_1"), (2, "mark_2")):
        pk.add_clip(A, f"lf_trail_mark_{k}", {node: lambda f: {"scale": (1, 1, 1) if f > 0 else (0.001, 0.001, 0.001),
                                                                 "rot": (0, 0, math.radians(6) * math.sin(f * 0.6) * (1 - ease(f, 0, 18)))}},
                    18, markers={"mark_visible": 0.1})
    pk.add_clip(A, "lf_lock_mechanism", {
        "handle": lambda f: {"rot": (0, -math.radians(80) * ease(f, 0, 10) * (1 - 0.0 * ease(f, 44, 54)), 0)},
        "lid": lambda f: {"loc": (LID_SLIDE * ease(f, 12, 46) + 0.012 * math.sin(math.pi * ease(f, 46, 54)), 0, 0)},
    }, 54, markers={"lid_open": 46 / 30})
    for nm in ("mark_1", "mark_2"):
        A.pivots[nm]["rest_scale"] = (0.0, 0.0, 0.0)


def meta(A):
    return {"symbol_targets": {
        "landmarks": {"A": {"node": "mark_landmark_a", "where": "split birch stump", "clip": "lf_trail_mark_1", "visible_scale": 1},
                      "B": {"node": "mark_landmark_b", "where": "white-moss boulder", "clip": "lf_trail_mark_2", "visible_scale": 1},
                      "C": {"node": "cache_lid", "where": "hollow log cache", "clip": "lf_lock_mechanism",
                            "open_translation_offset": [LID_SLIDE, 0, 0]}},
        "sites": {"lf_site_01": {"split_birch": "A", "white_moss": "B", "fallen_trunk": "C"},
                  "lf_site_05": {"resin_pine": "A", "double_stump": "B", "resin_bowl": "C"},
                  "lf_site_09": {"bent_fern": "A", "flat_slab": "B", "three_notches": "C"}},
        "progress_rule": "progress k shows marks of steps <= k (scale 1); solved plays lf_lock_mechanism; wrong input -> marks scale 0",
        "note": ("Sites 05/09 reuse the same three landmark nodes; their biome-specific look (resin pine, double stump, "
                 "resin bowl, bent fern, flat slab, three-notch stone) is NOT modelled here - deviation documented.")},
        "sockets": {"artifact_spot": pk.b2g((1.0, LOG_Y, LOG_R + 0.08)),
                    "landmark_offsets_from_log": {"A": pk.b2g(STUMP), "B": pk.b2g(BOULDER)}}}


def main():
    views = [{"name": "main", "box": (0, 62, 760, 384), "x0": [-0.35, 0.55, 0, 9.0, 2.2, 0, 0], "pose": {"lid": {"loc": (LID_SLIDE * 0.55, 0, 0)}}}]
    mk.run(ASSET, spec(), build, views, clips, meta, markers=[("artifact_spot", (1.0, LOG_Y, LOG_R + 0.08), "root")],
           notes="Landmarks A/B and the log cache are one GLB; client may offset A/B per the site layout.", main_view="main")


if __name__ == "__main__":
    main()
