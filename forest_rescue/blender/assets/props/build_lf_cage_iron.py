"""lf_cage_iron (IRON cage): riveted black iron frame with spike finials on an oak skid base, gothic iron
tracery, collared bars with fleur tips, bronze hinge straps, hexagonal bronze socket (bronze_seal) + keyhole.

Run: python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/props/build_lf_cage_iron.py --iter N
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np

import cageqa
import cagekit as ck
import motifs as mo
import propkit as pk
import propshaders as sh
from propkit import M4, Rx, Ry, Rz

ASSET = "lf_cage_iron"
P = dict(pc=1.48, post=0.17, base_top=0.30, base_h=0.20, base_over=0.20, runner_h=0.12,
         top_z0=2.80, top_h=0.17, fin_h=0.38, hinge_x=0.0, door_h=2.22, door_arch=0.16, door_t=0.06,
         rail_z=(1.02,), knot_z=(0.92, 1.12))


def riv(du, v, r=0.011, u0=None):
    d = {"du": du, "v": v, "r": r}
    if u0 is not None:
        d["u0"] = u0
    return {"rivets": d}


def build(lod):
    B = pk.Builder(lod)
    p = P
    pc, post = p["pc"], p["post"]
    bt, bh, bo = p["base_top"], p["base_h"], p["base_over"]
    front = -pc
    # ---------------- oak skid base: planked platform + runners + iron corner caps
    e = pc + bo
    nplank = 7 if lod < 2 else 1
    for i in range(nplank):
        y0 = -e + 2 * e * i / nplank
        y1 = -e + 2 * e * (i + 1) / nplank
        pl = pk.beam((-e, (y0 + y1) / 2, bt - bh / 2), (e, (y0 + y1) / 2, bt - bh / 2), (y1 - y0) - 0.006, bh,
                     chamfer=0.02, up=(0, 0, 1))
        B.add("root", "base_planks", "plank", pl, meta={"moss": 0.15, "pith_x": 0.0, "pith_y": -0.2})
    for sx in (-1, 1):
        for sy in (-1, 0.0, 1):
            if sy == 0.0 and lod > 0:
                continue
            ru = pk.beam((sx * (e - 0.28), sy * (e - 0.22), 0.0), (sx * (e - 0.28), sy * (e - 0.22), bt - bh),
                         0.40, 0.34, chamfer=0.02, up=(0, 1, 0))
            B.add("root", "base_runners", "plank", ru)
    # long sleepers under the platform (front/back)
    for sy in (-1, 1):
        sl = pk.beam((-e + 0.05, sy * (e - 0.22), bt - bh - 0.05), (e - 0.05, sy * (e - 0.22), bt - bh - 0.05), 0.30, 0.1,
                     chamfer=0.015)
        B.add("root", "base_runners", "plank", sl)
    # iron corner caps on the platform + big boss rivets on the front edge
    for sx in (-1, 1):
        for sy in (-1, 1):
            cap = pk.beam((sx * (e - 0.09), sy * (e - 0.09), bt - bh - 0.005), (sx * (e - 0.09), sy * (e - 0.09), bt + 0.006),
                          0.2, 0.2, chamfer=0.01, up=(0, 1, 0))
            B.add("root", "base_caps", "iron", cap)
    for k in range(5 if lod < 2 else 0):
        x = -e + 0.35 + k * (2 * e - 0.7) / 4
        boss = pk.lathe(np.array([[0.04, 0], [0.038, 0.02], [0.02, 0.035], [0, 0.04]]), B.seg(10, 6, 4))
        B.add("root", "base_bosses", "iron", boss.transformed(M4(Rx(math.pi / 2), (x, -e, bt - bh / 2))), max_lod=1)
    # ---------------- iron posts + finials
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * pc, sy * pc
            po = pk.beam((x, y, bt), (x, y, p["top_z0"] + p["top_h"]), post, post, chamfer=0.012, up=(0, 1, 0))
            B.add("root", f"post_{sx}{sy}", "iron", po, meta=riv(0.16, [post * 0.5 + 0.012 + k * (post + 0.024) for k in range(4)], 0.012))
            z = p["top_z0"] + p["top_h"]
            fin = pk.lathe(np.array([[0.1, 0], [0.1, 0.03], [0.06, 0.05], [0.07, 0.09], [0.045, 0.12], [0.06, 0.15],
                                     [0.0, p["fin_h"]]]), B.seg(8, 6, 4), smooth=False)
            B.add("root", "finials", "iron", fin.transformed(M4(None, (x, y, z))))
    hx = p["hinge_x"]
    hp = pk.beam((hx, front, bt), (hx, front, p["top_z0"]), 0.15, 0.15, chamfer=0.012, up=(0, 1, 0))
    B.add("root", "hinge_post", "iron", hp, meta=riv(0.16, [0.075 + 0.0125 + k * 0.175 for k in range(4)], 0.011))
    # ---------------- top frame beams
    z0, th = p["top_z0"], p["top_h"]
    for i, (a, b) in enumerate([((-pc, -pc), (pc, -pc)), ((-pc, pc), (pc, pc)), ((-pc, -pc), (-pc, pc)), ((pc, -pc), (pc, pc))]):
        be = pk.beam((a[0], a[1], z0 + th / 2), (b[0], b[1], z0 + th / 2), 0.13, th, chamfer=0.01, up=(0, 0, 1))
        B.add("root", f"topbeam_{i}", "iron", be, meta=riv(0.16, [0.065 + 0.01 + 0.085, 0.13 + th + 0.065 + 0.085], 0.012))
    # roof ridge strap (arched) across the top + boss
    nr = B.seg(9, 5, 3)
    xs = np.linspace(-pc, pc, nr)
    rid = np.stack([xs, np.zeros(nr), z0 + th + 0.16 * np.sin(np.pi * (xs + pc) / (2 * pc))], 1)
    B.add("root", "ridge", "iron", pk.sweep(rid, pk.rect(0.06, 0.03, 0.006), up=(0, 0, 1), smooth=False))
    for sy in (-1, 1):
        ys = np.linspace(0, sy * pc, max(3, nr // 2))
        rr = np.stack([np.zeros(len(ys)), ys, z0 + th + 0.16 * np.cos(np.pi * ys / (2 * pc))], 1)
        B.add("root", "ridge", "iron", pk.sweep(rr, pk.rect(0.05, 0.025, 0.005), up=(0, 0, 1), smooth=False))
    # ---------------- bays: bars with collars + fleur tips, rails, gothic tracery
    bays = [("x", -pc, -pc + post / 2, hx - 0.075), ("x", pc, -pc + post / 2, pc - post / 2),
            ("y", -pc, -pc + post / 2, pc - post / 2), ("y", pc, -pc + post / 2, pc - post / 2)]
    for bi, (axis, fixed, a, b) in enumerate(bays):
        def W2(s, z):
            return (s, fixed, z) if axis == "x" else (fixed, s, z)
        L = b - a
        nbars = max(3, int(round(L / 0.15)))
        xs = np.linspace(a + L / (nbars + 1), b - L / (nbars + 1), nbars)
        n_arch = max(1, int(round(L / 0.95)))
        aw = L / n_arch
        spring = z0 - 0.62
        apex = z0 - 0.04
        for xx in xs:
            k = min(int((xx - a) / aw), n_arch - 1)
            ca = a + aw * (k + 0.5)
            u = (xx - ca) / (aw / 2)
            top = spring + (apex - spring) * max(0.0, 1 - abs(u) ** 1.7)
            bar = pk.rod(W2(xx, bt + 0.04), W2(xx, top), 0.016, B.seg(6, 5, 4))
            B.add("root", f"bars_{bi}", "iron", bar)
            if lod < 2:
                for kz in p["knot_z"]:
                    kn = pk.lathe(np.array([[0.016, -0.04], [0.03, -0.015], [0.032, 0.0], [0.03, 0.015], [0.016, 0.04]]), 6)
                    B.add("root", f"knots_{bi}", "iron", kn.transformed(M4(None, W2(xx, kz))), max_lod=1)
                fl = pk.lathe(np.array([[0.016, 0.0], [0.036, 0.03], [0.02, 0.06], [0.0, 0.13]]), 4)
                B.add("root", f"fleurs_{bi}", "iron", fl.transformed(M4(None, W2(xx, spring - 0.18))), max_lod=1)
        for rz in (bt + 0.05,) + tuple(p["rail_z"]) + (spring - 0.18,):
            rail = pk.beam(W2(a, rz), W2(b, rz), 0.03, 0.045, chamfer=0.006, up=(0, 0, 1))
            B.add("root", f"rails_{bi}", "iron", rail, meta=riv(0.15, [0.03 + 0.0225], 0.008))
        for k in range(n_arch):
            s0 = a + aw * k
            s1 = s0 + aw
            cen = (s0 + s1) / 2
            n2 = B.seg(10, 7, 4)
            for sgn in (-1, 1):
                t = np.linspace(0, 1, n2)
                rr = aw * 0.85
                c0 = cen - sgn * (rr - aw / 2)
                ang1 = math.acos(np.clip((rr - aw / 2) / rr, -1, 1))
                pts = np.array([W2(c0 + sgn * rr * math.cos(q), spring + (apex - spring) * math.sin(q) / math.sin(ang1))
                                for q in ang1 * t])
                B.add("root", f"arches_{bi}", "iron", pk.sweep(pts, pk.rect(0.035, 0.05, 0.006), up=(0, 0, 1), smooth=False))
            if lod < 2:
                ring = np.array([W2(cen + 0.1 * math.cos(q), apex - 0.2 + 0.1 * math.sin(q))
                                 for q in np.linspace(0, 2 * math.pi, B.seg(12, 8, 6), endpoint=False)])
                B.add("root", f"tracery_{bi}", "iron", pk.tube(ring, 0.012, 4, closed_path=True,
                                                               up=(0, 1, 0) if axis == "x" else (1, 0, 0)), max_lod=1)
    # plaque above the door
    pq = np.array([[0.30 * math.cos(q), 0.24 * math.sin(q)] for q in np.linspace(0, math.pi, B.seg(14, 9, 6))])
    plaque = pk.extrude(np.vstack([pq, [[-0.30, -0.02], [0.30, -0.02]]]), 0.035, chamfer=0.008)
    cv = mo.Canvas((-0.31, -0.03, 0.31, 0.25), ppm=1500)
    mo.tree_emblem(cv, (0.0, 0.11), 0.2, 0.014)
    cv.ring((0, 0.0), 0.27, 0.03)
    en = cv.mask(0.002)
    B.add("root", "plaque", "bronze", plaque.transformed(M4(Rx(math.pi / 2), (0.62, -pc - 0.07, z0 - 0.05))),
          meta={"enamel": {"mask": 1 - en, "bbox": (-0.31, -0.03, 0.31, 0.25), "isl": [2], "colour": sh.C(52, 108, 80)},
                "motif": [{"mask": en, "bbox": (-0.31, -0.03, 0.31, 0.25), "isl": (2,), "depth": 0.004, "mode": "raise"}]})
    # ---------------- door
    dx0, dx1 = hx + 0.075 + 0.008, pc - post / 2 - 0.008
    dfy = -pc - post / 2 + 0.03
    dt = p["door_t"]
    dz0, dh = bt + 0.02, p["door_h"]
    for nm, x in (("stile_h", dx0 + 0.04), ("stile_l", dx1 - 0.04)):
        st = pk.beam((x, dfy + dt / 2, dz0), (x, dfy + dt / 2, dz0 + dh), 0.08, dt, chamfer=0.008, up=(0, 1, 0))
        B.add("door", f"door_{nm}", "iron", st, meta=riv(0.15, [0.04 + 0.008], 0.009))
    for nm, z, h in (("rail_bot", dz0 + 0.05, 0.1), ("rail_mid", dz0 + 0.95, 0.06)):
        ra = pk.beam((dx0 + 0.08, dfy + dt / 2, z), (dx1 - 0.08, dfy + dt / 2, z), dt, h, chamfer=0.008, up=(0, 1, 0))
        B.add("door", f"door_{nm}", "iron", ra, meta=riv(0.12, [0.03], 0.008))
    na = B.seg(10, 6, 3)
    xs_ = np.linspace(dx0 + 0.04, dx1 - 0.04, na)
    zt = dz0 + dh - 0.05 + p["door_arch"] * np.sin(np.pi * (xs_ - xs_[0]) / (xs_[-1] - xs_[0]))
    B.add("door", "door_arch", "iron", pk.sweep(np.stack([xs_, np.full(na, dfy + dt / 2), zt], 1), pk.rect(0.08, dt, 0.008),
                                                up=(0, 1, 0), smooth=False))
    for xx in np.linspace(dx0 + 0.15, dx1 - 0.15, 7):
        ztop = dz0 + dh - 0.05 + p["door_arch"] * math.sin(math.pi * (xx - xs_[0]) / (xs_[-1] - xs_[0]))
        B.add("door", "door_bars", "iron", pk.rod((xx, dfy + dt / 2, dz0 + 0.1), (xx, dfy + dt / 2, ztop - 0.03), 0.015,
                                                  B.seg(6, 5, 4)))
    hinge = (dx0 - 0.01, dfy - 0.028, 0.0)
    strap_cv = mo.Canvas((0.0, -0.05, 0.42, 0.05), ppm=2500)
    mo.fleur_sprig(strap_cv, (0.27, 0.0), 0.07, 0.006)
    strap_motif = [{"mask": strap_cv.mask(0.001), "bbox": (0.0, -0.05, 0.42, 0.05), "isl": (2,), "depth": 0.002,
                    "mode": "cut", "colour": sh.C(52, 108, 80), "tint": 0.95, "rough": 0.35, "metal": 0.0}]
    ck.hinge_set(B, (hinge[0], hinge[1]), [dz0 + 0.42, dz0 + 1.62], 0.42, 0.09, dfy, -pc - 0.075, cls="bronze",
                 knuckle_r=0.028, strap_motif=strap_motif)
    sz = 1.30
    lock = pk.beam((dx1 - 0.2, dfy - 0.02, sz - 0.24), (dx1 - 0.04, dfy - 0.02, sz - 0.24), 0.06, 0.045, chamfer=0.008)
    B.add("door", "lock_box", "iron", lock)
    bolt = pk.beam((dx1 - 0.16, dfy - 0.035, sz - 0.24), (dx1 + 0.09, dfy - 0.035, sz - 0.24), 0.028, 0.028, chamfer=0.005)
    B.add("latch", "latch_bolt", "bronze", bolt)
    kn = pk.lathe(np.array([[0.02, 0], [0.02, 0.028], [0.0, 0.034]]), B.seg(8, 6, 4))
    B.add("latch", "latch_bolt", "bronze", kn.transformed(M4(Rx(math.pi / 2), (dx1 - 0.08, dfy - 0.048, sz - 0.24))))
    keeper = pk.sweep(np.array([[pc - post / 2 + 0.03, dfy, sz - 0.29], [pc - post / 2 + 0.03, dfy - 0.06, sz - 0.29],
                                [pc - post / 2 + 0.03, dfy - 0.06, sz - 0.19], [pc - post / 2 + 0.03, dfy, sz - 0.19]]),
                      pk.rect(0.03, 0.012), up=(1, 0, 0), smooth=False)
    B.add("root", "latch_keeper", "iron", keeper)
    ck.add_sockets(B, "hex", (dx1 - 0.2, dfy - 0.012, sz), plate_cls="bronze", keyhole_cls="bronze")
    return B


def main():
    p = P
    pc, post = p["pc"], p["post"]
    hx = p["hinge_x"]
    dx0, dx1 = hx + 0.075 + 0.008, pc - post / 2 - 0.008
    dfy = -pc - post / 2 + 0.03
    sz = 1.30
    cageqa.run(ASSET, build, (dx0 - 0.01, dfy - 0.028, 0.0), (dx1 - 0.08, dfy - 0.035, sz - 0.24),
               (dx1 - 0.2, dfy - 0.012, sz), "hex", door=(dx0, dx1, p["base_top"], p["door_h"] + p["door_arch"]),
               front_y=-pc, interior=[round(2 * (pc - post / 2), 3)] * 2, clear_h=round(p["top_z0"] - p["base_top"], 3),
               ref_key="iron")


if __name__ == "__main__":
    main()
