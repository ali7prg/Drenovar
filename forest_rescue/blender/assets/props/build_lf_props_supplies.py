"""lf_props_supplies: recovered supplies set (one GLB, one node per item group).

Nodes (glTF): supply_crate_closed, supply_crate_open (+ supply_crate_open_lid hinge), supply_blankets,
supply_sacks, supply_coins, supply_bread, supply_bandages, supply_arrows, supply_chest (+ supply_chest_lid hinge).
Each node origin = item base centre; items are laid out in a row (meta.layout_offsets) - zero the node
translation to place an item on its own. Clip lf_supply_chest_open opens the travel chest lid (presentation).

Run: python3 forest_rescue/blender/run_limited.py .../build_lf_props_supplies.py --iter N
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy
import numpy as np

import motifs as mo
import propkit as pk
import propproj as pp
import propqa as qa
import propshaders as sh
from frlib import core, paths
from propkit import M4, Rx, Ry, Rz

ASSET = "lf_props_supplies"
IMG = "loot_artifact_families.png"
LAYOUT = {"crate_closed": (-3.6, 0), "crate_open": (-2.75, 0), "blankets": (-1.9, 0), "sacks": (-1.0, 0), "coins": (-0.2, 0),
          "bread": (0.35, 0), "bandages": (0.95, 0), "arrows": (1.6, 0), "chest": (2.75, 0)}
REF = {"crate_closed": (20, 742, 212, 900), "crate_open": (212, 698, 392, 902), "blankets": (398, 748, 632, 892),
       "sacks": (622, 726, 846, 930), "coins": (842, 776, 1022, 892), "bread": (88, 906, 322, 1008),
       "bandages": (392, 918, 632, 998), "arrows": (976, 752, 1136, 978), "chest": (1132, 700, 1512, 992)}
X0 = {"crate_closed": [-0.7, 0.45, 0, 3.0, 2.4, 0, 0], "crate_open": [-0.6, 0.45, 0, 3.0, 2.4, 0, 0],
      "blankets": [-0.45, 0.5, 0, 3.0, 2.4, 0, 0], "sacks": [-0.3, 0.35, 0, 3.0, 2.4, 0, 0],
      "coins": [-0.3, 0.6, 0, 1.5, 2.4, 0, 0], "bread": [-0.3, 0.45, 0, 2.0, 2.4, 0, 0],
      "bandages": [-0.4, 0.5, 0, 2.0, 2.4, 0, 0], "arrows": [-0.55, 0.75, 0, 3.0, 2.4, 0, 0], "chest": [-0.55, 0.42, 0, 3.5, 2.4, 0, 0]}
TRIQ = None


def triq_motif(r, depth=0.0015, mode="cut", isl=(2,), colour=None):
    bb = (-r, -r, r, r)
    cv = mo.Canvas(bb, ppm=3000)
    mo.triquetra(cv, (0, 0), r * 0.75, r * 0.12)
    cv.ring((0, 0), r * 0.92, r * 0.07)
    d = {"mask": cv.mask(r * 0.02), "bbox": bb, "isl": isl, "depth": depth, "mode": mode}
    if colour is not None:
        d["colour"] = colour
        d["tint"] = 0.7
    return d


def crate(B, node, o, open_=False):
    W, D, H = 0.62, 0.46, 0.44
    o = np.asarray(o, float)
    c = 0.006
    for sx in (-1, 1):
        for sy in (-1, 1):
            B.add(node, f"{node}_posts", "plank", pk.beam(o + (sx * (W / 2 - 0.03), sy * (D / 2 - 0.03), 0), o + (sx * (W / 2 - 0.03), sy * (D / 2 - 0.03), H),
                                                       0.06, 0.06, chamfer=c))
    nrow = 3
    for k in range(nrow):
        z = (k + 0.5) * H / nrow
        h = H / nrow - 0.008
        for sy in (-1, 1):
            B.add(node, f"{node}_planks", "plank", pk.beam(o + (-W / 2 + 0.06, sy * (D / 2 - 0.012), z), o + (W / 2 - 0.06, sy * (D / 2 - 0.012), z),
                                                        0.024, h, chamfer=0.0))
        for sx in (-1, 1):
            B.add(node, f"{node}_planks", "plank", pk.beam(o + (sx * (W / 2 - 0.012), -D / 2 + 0.06, z), o + (sx * (W / 2 - 0.012), D / 2 - 0.06, z),
                                                        0.024, h, chamfer=0.0))
    B.add(node, f"{node}_bottom", "plank", pk.beam(o + (-W / 2 + 0.02, 0, 0.012), o + (W / 2 - 0.02, 0, 0.012), D - 0.04, 0.024))
    if not open_:
        for sx in (-1, 1):   # diagonal X braces on the front
            B.add(node, f"{node}_braces", "plank", pk.beam(o + (sx * (W / 2 - 0.07), -D / 2 - 0.006, 0.05), o + (-sx * (W / 2 - 0.07), -D / 2 - 0.006, H - 0.05),
                                                        0.012, 0.05, chamfer=0.004))
        for k in range(4):
            y = -D / 2 + (k + 0.5) * D / 4
            B.add(node, f"{node}_lid", "plank", pk.beam(o + (-W / 2, y, H + 0.012), o + (W / 2, y, H + 0.012), D / 4 - 0.006, 0.024, chamfer=0.0))
        for x in (-W / 2 + 0.07, W / 2 - 0.07):
            B.add(node, f"{node}_straps", "iron", pk.beam(o + (x, -D / 2 - 0.004, H + 0.026), o + (x, D / 2 + 0.004, H + 0.026), 0.04, 0.006),
                  meta={"rivets": {"du": 0.09, "v": [pk.rect_face_v(0.04, 0.006, 0.0, "+B")], "r": 0.007}})
    else:
        cv = mo.Canvas((-0.12, -0.12, 0.12, 0.12), ppm=3000)
        mo.triquetra(cv, (0, 0), 0.09, 0.012)
        B.add(node, f"{node}_panel", "plank", pk.extrude(pk.rect(0.2, 0.18, 0.01), 0.014, chamfer=0.003).transformed(M4(Rx(math.pi / 2), o + (0, -D / 2 - 0.012, H * 0.5))),
              meta={"motif": [{"mask": cv.mask(0.002), "bbox": (-0.12, -0.12, 0.12, 0.12), "isl": (2,), "depth": 0.003, "mode": "cut"}]})
    for sx in (-1, 1):   # iron corner brackets
        for sy in (-1, 1):
            for zz in (0.03, H - 0.03):
                B.add(node, f"{node}_brackets", "iron", pk.beam(o + (sx * (W / 2 - 0.0), sy * (D / 2 - 0.0), zz - 0.03), o + (sx * (W / 2), sy * (D / 2), zz + 0.03),
                                                             0.075, 0.075, chamfer=0.0), max_lod=0)


def crate_lid(B, node, o):
    W, D, H = 0.62, 0.46, 0.44
    o = np.asarray(o, float)
    for k in range(4):
        y = -D / 2 + (k + 0.5) * D / 4
        B.add(node, f"{node}_planks", "plank", pk.beam(o + (-W / 2, y, H + 0.012), o + (W / 2, y, H + 0.012), D / 4 - 0.006, 0.024, chamfer=0.0))
    for x in (-W / 2 + 0.07, W / 2 - 0.07):
        B.add(node, f"{node}_straps", "iron", pk.beam(o + (x, -D / 2, H + 0.026), o + (x, D / 2, H + 0.026), 0.04, 0.006))


def blanket(B, node, o, k):
    w, d, t = 0.52, 0.36, 0.068
    o = np.asarray(o, float) + np.array([0.01 * (k - 1), 0.012 * k, k * (t - 0.006)])
    prof = pk.rounded_rect(d, t, t * 0.45, 3)
    path = np.array([o + (-w / 2, 0, t / 2), o + (w / 2, 0, t / 2)])
    sl = pk.sweep(path, np.stack([prof[:, 1], prof[:, 0]], 1), up=(0, 0, 1), smooth=True)
    cv = mo.Canvas((0, 0, 0.6, 0.6), ppm=800)
    for yy in (0.08, 0.13):
        mo.celtic_band(cv, np.array([[0.0, yy], [0.6, yy]]), 0.035, period=0.05)
    B.add(node, f"{node}_folds", "cloth", sl, meta={"motif": [{"mask": cv.mask(0.002), "bbox": (0, 0, 0.6, 0.6), "isl": (0,), "depth": 0.001,
                                                              "mode": "raise", "colour": sh.C(214, 186, 150), "tint": 0.85}]})


def sack(B, node, o, open_=False, seed=0):
    o = np.asarray(o, float)
    rng = np.random.RandomState(seed)
    H = 0.50 if not open_ else 0.40
    R = 0.19 if not open_ else 0.21

    def fn(u, v):
        th = u * 2 * math.pi
        z = v * H
        if open_:
            r = R * (0.85 + 0.3 * np.sin(np.clip(v, 0, 1) * math.pi * 0.9) ** 0.6) * (1 - 0.05 * (v > 0.9))
        else:
            r = R * np.where(v < 0.78, 0.8 + 0.35 * np.sin(np.clip(v / 0.78, 0, 1) * math.pi * 0.95) ** 0.7,
                             np.where(v < 0.86, 0.32, 0.32 + (v - 0.86) * 2.8))
        r = r * (1 + 0.05 * np.sin(th * 3 + seed) + 0.03 * np.sin(th * 7 + v * 6))
        z = z - 0.02 * np.cos(th) * (v > 0.95)
        return np.stack([o[0] + r * np.cos(th), o[1] + r * np.sin(th), o[2] + z], -1)
    body = pk.grid(fn, 16, 8, Lu=2 * math.pi * R, Lv=H, wrap_u=True)
    bottom = pk.orient_toward(pk.lathe(np.array([[0.0, 0.0], [R * 0.8, 0.0]]), 20).transformed(M4(None, o)), (0, 0, -1))
    m = triq_motif(0.06, 0.001, "cut", isl=(0,), colour=sh.C(70, 50, 32))
    m["bbox"] = (2 * math.pi * R * 0.75 - 0.06, H * 0.35 - 0.06, 2 * math.pi * R * 0.75 + 0.06, H * 0.35 + 0.06)
    B.add(node, f"{node}_body{int(open_)}", "burlap", pk.Piece.merge([body, bottom]), meta={"motif": [m]})
    if open_:
        g = pk.orient_toward(pk.lathe(np.array([[0.0, H * 0.9], [R * 0.98, H * 0.86]]), 16), (0, 0, 1)).transformed(M4(None, o))
        B.add(node, f"{node}_grain", "grain", g)
    else:
        tie = pk.tube(np.array([o + (R * 0.34 * math.cos(a), R * 0.34 * math.sin(a), H * 0.8) for a in np.linspace(0, 2 * math.pi, 10, endpoint=False)]),
                      0.009, 4, closed_path=True)
        B.add(node, f"{node}_tie", "rope", tie, meta={"rope_pitch": 0.02, "rope_circ": 0.05})


def build(lod):
    B = pk.Builder(lod)
    L = {k: np.array([v[0], v[1], 0.0]) for k, v in LAYOUT.items()}
    crate(B, "crate_closed", L["crate_closed"])
    crate(B, "crate_open", L["crate_open"], open_=True)
    crate_lid(B, "crate_open_lid", L["crate_open"])
    for k in range(3):
        blanket(B, "blankets", L["blankets"], k)
    sack(B, "sacks", L["sacks"] + (-0.12, 0.1, 0), False, 1)
    sack(B, "sacks", L["sacks"] + (0.15, -0.08, 0), True, 2)
    # coins: tight cluster as drawn - three stacks, loose coins, one upright coin in front
    cs = B.seg(14, 10, 7)
    for k, (dx, dy, n) in enumerate(((0.0, 0.06, 5), (-0.075, 0.0, 2), (0.075, 0.005, 3))):
        st = pk.extrude(pk.circle(0.036, cs), n * 0.0068, chamfer=0.0)
        B.add("coins", "coin_stacks", "bronze", st.transformed(M4(None, L["coins"] + (dx, dy, 0))),
              meta={"motif": [triq_motif(0.036, 0.0008, "raise")]})
    for k, (dx, dy, a, z) in enumerate(((-0.12, -0.05, 0.12, 0.004), (0.13, -0.06, 0.08, 0.004), (0.02, -0.035, 1.25, 0.034))):
        c = pk.extrude(pk.circle(0.036, cs), 0.0068, chamfer=0.0)
        B.add("coins", "coin_loose", "bronze", c.transformed(M4(Rx(a), L["coins"] + (dx, dy, z))),
              meta={"motif": [triq_motif(0.036, 0.0008, "raise")]})
    # bread loaves
    for k, (dx, dy, s) in enumerate(((-0.12, 0.0, 1.0), (0.13, 0.04, 0.92))):
        def deform(P, u, v, s=s):
            P = P.copy()
            P[..., 2] = np.where(P[..., 2] < 0, P[..., 2] * 0.25, P[..., 2])
            return P
        e = pk.ellipsoid((dx, dy, 0.025), (0.13 * s, 0.1 * s, 0.085 * s), nu=B.seg(12, 9, 7), nv=B.seg(6, 5, 4), deform=deform)
        cv = mo.Canvas((0, 0, 2 * math.pi * 0.115, math.pi * 0.105), ppm=1500)
        for j in range(3):
            cv.line(np.array([[0.25 + j * 0.06, 0.24], [0.32 + j * 0.06, 0.29]]), 0.008)
        B.add("bread", "loaves", "bread", e.transformed(M4(Rz(0.4 * k), L["bread"])),
              meta={"motif": [{"mask": cv.mask(0.002), "bbox": (0, 0, 2 * math.pi * 0.115, math.pi * 0.105), "isl": (0,), "depth": 0.006, "mode": "cut"}]})
    # bandages: two rolls + loose tail
    for k, (dx, dy, a) in enumerate(((-0.09, 0.03, 0.05), (0.09, -0.02, -0.05))):
        roll = pk.rod((-0.075, 0, 0.045), (0.075, 0, 0.045), 0.045, B.seg(14, 9, 6))
        B.add("bandages", "rolls", "linen", roll.transformed(M4(Rz(a), L["bandages"] + (dx, dy, 0))))
    tail = pk.beam(L["bandages"] + (0.17, -0.05, 0.003), L["bandages"] + (0.33, -0.11, 0.003), 0.13, 0.004)
    B.add("bandages", "tail", "linen", tail)
    # arrows: bundle of 8 tied with cord
    rng = np.random.RandomState(4)
    for k in range(8):
        a = 2 * math.pi * k / 8
        off = np.array([0.0, 0.022 * math.cos(a), 0.022 * math.sin(a) + 0.06])
        tilt = rng.uniform(-0.05, 0.05)
        offy = np.array([0.022 * math.cos(a), 0.0, 0.022 * math.sin(a) + 0.06])
        p0 = L["arrows"] + offy + np.array([tilt * 2, 0.38, 0.0])
        p1 = L["arrows"] + offy + np.array([-tilt * 2, -0.38, 0.0])
        B.add("arrows", "shafts", "plank", pk.rod(p0, p1, 0.006, 5))
        head = pk.lathe(np.array([[0.0, 0.0], [0.014, 0.012], [0.0, 0.07]]), 4)
        B.add("arrows", "heads", "iron", head.transformed(M4(Rx(math.pi / 2), p1)))
        for f in range(3 if lod < 2 else 0):
            fa = a + f * 2 * math.pi / 3
            nrm = np.array([math.cos(fa), 0, math.sin(fa)])
            fl = pk.Piece(np.array([p0 + (0, -0.02, 0), p0 + (0, -0.14, 0), p0 + (0, -0.12, 0) + nrm * 0.022, p0 + (0, -0.03, 0) + nrm * 0.03]))
            fl.add_face((0, 1, 2, 3), [(0, 0), (0.12, 0), (0.1, 0.022), (0.01, 0.03)], 0, False, 0)
            fl.add_face((3, 2, 1, 0), [(0.01, 0.03), (0.1, 0.022), (0.12, 0), (0, 0)], 1, False, 0)
            B.add("arrows", "fletching", "feather", fl, max_lod=1)
    for x in (-0.12, 0.08):
        cord = pk.tube(np.array([L["arrows"] + (0.032 * math.cos(t), x, 0.06 + 0.032 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 10, endpoint=False)]),
                       0.006, 4, closed_path=True, up=(0, 1, 0))
        B.add("arrows", "cords", "rope", cord, meta={"rope_pitch": 0.01, "rope_circ": 0.04})
    # travel chest: body + iron bands + plaque + contents ; lid node (barrel vault)
    o = L["chest"]
    W, D, H = 0.9, 0.5, 0.42
    B.add("chest", "chest_body", "dark_oak", pk.beam(o + (-W / 2, 0, H / 2), o + (W / 2, 0, H / 2), D, H, chamfer=0.012),
          meta={"rivets": {"du": 0.1, "v": [pk.rect_face_v(D, H, 0.012, "-N") - 0.12, pk.rect_face_v(D, H, 0.012, "-N") + 0.12], "r": 0.008}})
    for x in (-W / 2 + 0.05, -0.15, 0.15, W / 2 - 0.05):
        B.add("chest", "chest_bands", "iron", pk.beam(o + (x, 0, -0.002), o + (x, 0, H + 0.002), 0.045, D + 0.012),
              meta={"rivets": {"du": 0.08, "v": [0.0225], "r": 0.008}})
    cv = mo.Canvas((-0.1, -0.12, 0.1, 0.12), ppm=3000)
    mo.triquetra(cv, (0, 0.0), 0.075, 0.01)
    shield = np.array([[0.0, -0.11], [0.08, -0.05], [0.08, 0.1], [-0.08, 0.1], [-0.08, -0.05]])
    B.add("chest", "chest_plaque", "iron", pk.extrude(shield, 0.012, chamfer=0.003).transformed(M4(Rx(math.pi / 2), o + (0, -D / 2 - 0.006, H * 0.52))),
          meta={"motif": [{"mask": cv.mask(0.002), "bbox": (-0.1, -0.12, 0.1, 0.12), "isl": (2,), "depth": 0.003, "mode": "raise"}]})
    for sx in (-1, 1):
        hd = pk.tube(np.array([o + (sx * (W / 2 + 0.03), 0.06 * math.cos(t), H * 0.6 + 0.06 * math.sin(t)) for t in np.linspace(math.pi, 2 * math.pi, 7)]), 0.01, 4)
        B.add("chest", "chest_handles", "iron", hd, max_lod=1)
    # contents peeking out
    loaf = pk.ellipsoid((0, 0, 0), (0.1, 0.08, 0.07), nu=10, nv=6)
    B.add("chest", "contents", "bread", loaf.transformed(M4(None, o + (-0.28, -0.04, H + 0.02))))
    sk = pk.ellipsoid((0, 0, 0), (0.08, 0.07, 0.11), nu=10, nv=6)
    B.add("chest", "contents_sack", "burlap", sk.transformed(M4(None, o + (-0.05, 0.05, H + 0.04))))
    roll = pk.rod((0.08, 0.04, H + 0.06), (0.36, 0.04, H + 0.06), 0.075, 10)
    B.add("chest", "contents_roll", "cloth", roll.transformed(M4(None, o)))
    for k in range(3):
        cc = pk.extrude(pk.circle(0.03, 10), 0.012 * (k + 1)).transformed(M4(None, o + (0.12 + 0.05 * k, -0.14, H - 0.01)))
        B.add("chest", "contents_coins", "bronze", cc)
    # lid: barrel vault sweep along X (half ellipse), bands
    lp = np.array([[0.25 * math.cos(a), 0.15 * math.sin(a)] for a in np.linspace(0, math.pi, B.seg(10, 7, 4))])
    lp = np.vstack([lp, lp[::-1] * 0.92])
    lid = pk.sweep(np.array([o + (-W / 2, 0, H), o + (W / 2, 0, H)]), np.stack([lp[:, 0], lp[:, 1]], 1), up=(0, 1, 0), smooth=False)
    B.add("chest_lid", "lid_shell", "dark_oak", lid)
    for x in (-W / 2 + 0.05, -0.15, 0.15, W / 2 - 0.05):
        bp = np.array([[0.255 * math.cos(a), 0.155 * math.sin(a)] for a in np.linspace(0, math.pi, B.seg(10, 7, 4))])
        band = pk.sweep(np.array([o + (x - 0.022, 0, H), o + (x + 0.022, 0, H)]), np.vstack([bp, bp[::-1] * 0.95]), up=(0, 1, 0), smooth=False)
        B.add("chest_lid", "lid_bands", "iron", band, max_lod=1)
    return B


def spec():
    s = {"root": {}}
    for k, (x, y) in LAYOUT.items():
        s[k] = {"pivot": (x, y, 0.0), "export_name": f"supply_{k}"}
    s["crate_open_lid"] = {"pivot": (LAYOUT["crate_open"][0], LAYOUT["crate_open"][1] + 0.23, 0.44), "parent": "crate_open",
                           "export_name": "supply_crate_open_lid"}
    s["chest_lid"] = {"pivot": (LAYOUT["chest"][0], LAYOUT["chest"][1] + 0.25, 0.42), "parent": "chest", "export_name": "supply_chest_lid"}
    return s


CRATE_LID_OPEN = math.radians(-112)
CHEST_LID_OPEN = math.radians(-100)


def open_pose(A):
    pk.set_static_pose(A, {"crate_open_lid": {"rot": (CRATE_LID_OPEN, 0, 0)}, "chest_lid": {"rot": (CHEST_LID_OPEN, 0, 0)}})


def main():
    it = qa.iteration()
    pre = f"iter{it:02d}_"
    core.reset()
    A = pk.Asset(ASSET, spec())
    A.dirt_scale = 0.0

    def build_(lod):
        return build(lod)
    A.compile(build_)
    # the open crate's lid planks: rest pose = open (drawing); clip closes nothing - rest kept open via rest rotation
    pk.pack_atlas(A.lod0_objects(), margin=0.003)
    pk.transfer_atlas_uv(A)
    cams_path = os.path.join(paths.ensure(paths.QA_COMPARE, "props_cams"), "supplies_cams.json")
    cams = qa.load_cams(cams_path)
    fits = {}
    open_pose(A)
    for item, box in REF.items():
        img, m = qa.crop_and_mask(IMG, box, tol=3)
        objs = [A.meshes[0][item]] + ([A.meshes[0][item + "_lid"]] if item + "_lid" in A.meshes[0] else [])
        tris = pk.world_triangles(objs)
        c = tris.reshape(-1, 3).mean(0)
        key = f"{ASSET}:{item}"
        start = np.array(cams[key]) if key in cams and not qa.flag("--refit") else np.array(X0[item] + list(c))
        x, sc = pk.fit_camera(tris, m, start, fixed=(2,), iters=(1 if key in cams else 2))
        cams[key] = [float(a) for a in x]
        H, W = m.shape
        fits[item] = (img, m, pk.cam_from_params(x, W, H), sc, objs)
        print(f"[supplies] {item} fit IoU {sc:.3f}")
    qa.save_cams(cams_path, cams)
    pk.set_static_pose(A, {})
    specs = [pp.ViewSpec(item, f[0], f[1], f[4], "persp", cam=f[2], pose=(lambda: open_pose(A)), unpose=(lambda: pk.set_static_pose(A, {})),
                         weight=1.0, erode=1, delight=0.3, min_facing=0.1, depth_eps=0.02) for item, f in fits.items()]
    files, info = pp.paint_relief_textures(A, dict(sh.SHADERS), specs, size=2048, height_gain=0.006,
                                           sizes={"base": 2048, "orm": 1024, "normal": 2048}, relief_levels=2,
                                           ao_distance=0.08, ao_strength=0.6, edge_fade_m=0.003, samples=8, paint_alpha_w=0.3)
    pk.make_material(A, files)
    pk.add_clip(A, "lf_supply_chest_open", {"chest_lid": lambda f: {"rot": (CHEST_LID_OPEN * float(pk.ease_in_out(np.clip(f / 30, 0, 1))), 0, 0)}},
                36, markers={"lid_open": 1.0})
    pk.add_clip(A, "lf_supply_crate_open", {"crate_open_lid": lambda f: {"rot": (CRATE_LID_OPEN * float(pk.ease_in_out(np.clip(f / 24, 0, 1))), 0, 0)}},
                30, markers={"lid_open": 0.8})
    glb = paths.runtime(pk.GROUP, f"{ASSET}.glb")
    A.pivots["crate_open_lid"]["rest_rot"] = (CRATE_LID_OPEN, 0.0, 0.0)
    pk.export(A, glb)
    st = pk.tri_stats(A)
    summ = pk.glb_summary(glb)
    meta = {"id": ASSET, "tris": {f"LOD{l}": st[f"LOD{l}"]["total"] for l in (0, 1, 2)},
            "tris_by_node": {f"LOD{l}": st[f"LOD{l}"]["by_node"] for l in (0, 1, 2)},
            "budget": "supplies set <= 5000 tris (LOD0, whole set)", "bones": 0, "materials": [f"{ASSET}_mat"],
            "textures": {"baseColor": "2048 JPEG", "metallicRoughness": "1024 JPEG", "normal": "2048 PNG"},
            "coordinate_space": "glTF (Y up, metres); item fronts face +Z",
            "items": {k: {"node": f"supply_{k}", "layout_offset": pk.b2g((v[0], v[1], 0))} for k, v in LAYOUT.items()},
            "lid_nodes": {"supply_crate_open_lid": {"open_rotation_x_deg": round(math.degrees(CRATE_LID_OPEN), 1)},
                          "supply_chest_lid": {"open_rotation_x_deg": round(math.degrees(CHEST_LID_OPEN), 1)}},
            "clips": {c: {"seconds": round(v["frames"] / 30, 3), "loop": False, "markers": v["markers"]} for c, v in A.clips.items()},
            "glb_nodes": summ["nodes"], "projection": info,
            "camera_fit_iou": {k: round(v[3], 4) for k, v in fits.items()},
            "notes": "Lids rest closed; drawing shows them open (comparison renders use the open pose). Counts are visual only (economy from data)."}
    core.write_json(paths.runtime(pk.GROUP, f"{ASSET}.meta.json"), meta)
    print("[supplies] tris", meta["tris"])
    core.save_blend(paths.source(pk.GROUP, f"{ASSET}.blend"))
    if qa.flag("--noqa"):
        return
    pk.studio(engine="CYCLES", samples=40, key=3.6, fill=1.2, rim=1.2, ambient=0.9, bg=(0.90, 0.82, 0.73))
    open_pose(A)
    res = {}
    for item, (img, m, cam, sc, objs) in fits.items():
        for o in A.all_meshes():
            o.hide_render = True
        for o in objs:
            o.hide_render = False
        pk.blender_camera(cam)
        rgba = pk.render_rgba(qa.out(ASSET, "_tmp.png"))
        res[item] = pk.compare_panels(img, rgba, m, qa.out(ASSET, pre + f"{item}.png"), f"{ASSET} {item} (fitted camera)")
    core.write_json(qa.out(ASSET, pre + "metrics.json"), {k: {kk: r.get(kk) for kk in ("iou_filled", "iou_raw", "mean_abs_colour_error")}
                                                          for k, r in res.items()})
    print("[supplies-qa]", {k: (r.get("iou_filled"), r.get("mean_abs_colour_error")) for k, r in res.items()})
    for o in A.all_meshes():
        o.hide_render = True
    for o in A.lod0_objects():
        o.hide_render = False
    mn, mx = core.bounds(A.lod0_objects())
    c = (mn + mx) / 2
    cam = pk.cam_from_params([-0.15, 0.45, 0, 9.5, 2.0, 0, 0, *c], 1600, 600)
    pk.blender_camera(cam)
    rgba = pk.render_rgba(qa.out(ASSET, "_tmp.png"))
    pk.side_by_side([pk.ref_crop(IMG, (0, 690, 1536, 1024)), rgba], ["drawing: recovered supplies", "model set (same order)"],
                    qa.out(ASSET, pre + "set_overview.png"), height=420)
    pk.set_static_pose(A, {})


if __name__ == "__main__":
    main()
