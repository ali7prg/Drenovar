"""lf_cage_root (ROOT cage): twisted living roots with green leaf inlays, root lattice walls, timber door
frame with a plank door, bronze hinge straps, diamond bronze socket (amber_crystal) + keyhole.

Run: python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/props/build_lf_cage_root.py --iter N
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

ASSET = "lf_cage_root"
P = dict(pc=1.48, top=2.42, dome=3.05, floor_z=0.10, jamb_h=0.0, door_x0=-0.30, door_x1=1.24, door_h=2.18,
         door_arch=0.12, door_t=0.06)


def spline(ctrl, n):
    """Catmull-Rom through control points -> n samples."""
    c = np.asarray(ctrl, float)
    c = np.vstack([c[0] * 2 - c[1], c, c[-1] * 2 - c[-2]])
    seg = len(c) - 3
    out = []
    for i in range(n):
        t = i / (n - 1) * seg
        k = min(int(t), seg - 1)
        u = t - k
        p0, p1, p2, p3 = c[k], c[k + 1], c[k + 2], c[k + 3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u +
                          (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3))
    return np.array(out)


def root(B, name, ctrl, r0, r1, nseg, sides, seed, wobble=0.03, node="root", meta=None):
    rng = np.random.RandomState(seed)
    pts = spline(ctrl, nseg)
    if wobble > 0:
        L = np.linspace(0, 1, nseg)
        for k in range(3):
            ph = rng.uniform(0, 6.28)
            fr = rng.uniform(2.0, 4.0)
            amp = wobble * (1 - 0.5 * L)
            off = np.zeros(3)
            off[k] = 1
            pts += np.outer(amp * np.sin(L * fr * math.pi + ph), off) * (0.6 if k == 2 else 1.0)
    t = np.linspace(0, 1, nseg)
    sc = (r0 + (r1 - r0) * t ** 0.8) / r0
    tw = np.linspace(0, rng.uniform(1.5, 3.0), nseg)
    tb = pk.tube(pts, r0, sides, up=(0.3, 0.2, 1.0), scale=sc, twist=tw)
    B.add(node, name, "root", tb, meta=meta or {"moss": 0.55})


def bundle(B, base, top_pts, seed, strands=3, R=0.11, nseg=10, sides=5, rr=0.07):
    """Twisted bundle of strands around a centre line (base -> top control points)."""
    centre = spline([base] + top_pts, 40)
    for s in range(strands):
        ctrl = []
        for i, t in enumerate(np.linspace(0, 1, 6)):
            c = centre[int(t * (len(centre) - 1))]
            ph = s * 2 * math.pi / strands + t * 2.6 + seed
            rad = R * (1.0 - 0.35 * t)
            ctrl.append(c + np.array([math.cos(ph) * rad, math.sin(ph) * rad, 0.0]))
        root(B, f"bundle_{seed}_{s}", ctrl, rr, rr * 0.65, nseg, sides, seed * 10 + s, wobble=0.0)


def build(lod):
    B = pk.Builder(lod)
    p = P
    pc, top, dome = p["pc"], p["top"], p["dome"]
    nseg = B.seg(9, 6, 4)
    sides = B.seg(5, 4, 3)
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    # ---------------- corner bundles + flared feet + inlays
    for ci, (sx, sy) in enumerate(corners):
        base = np.array([sx * pc, sy * pc, -0.05])
        tp = [np.array([sx * pc * 0.98, sy * pc * 0.98, 1.2]), np.array([sx * pc * 1.02, sy * pc * 1.02, top - 0.2]),
              np.array([sx * pc * 0.95, sy * pc * 0.95, top + 0.12])]
        bundle(B, base, tp, ci + 1, strands=3 if lod < 2 else 2, R=0.14, nseg=nseg, sides=sides, rr=0.115)
        nfeet = 3 if lod < 2 else 2
        for k in range(nfeet):
            ang = math.atan2(sy, sx) + (k - (nfeet - 1) / 2) * 0.55
            d = np.array([math.cos(ang), math.sin(ang), 0])
            ctrl = [base + np.array([0, 0, 0.7]), base + d * 0.32 + np.array([0, 0, 0.26]), base + d * 0.75 + np.array([0, 0, 0.05]),
                    base + d * 1.1 + np.array([0, 0, -0.02])]
            root(B, f"feet_{ci}", ctrl, 0.10, 0.03, B.seg(6, 4, 3), max(3, sides - 1), 100 + ci * 10 + k, wobble=0.04)
        # emerald leaf inlay (diamond plate) on the outward diagonal face near the top
        if True:
            d = pk.unit(np.array([sx, sy, 0.0]))
            dia = np.array([[0, 0.21], [-0.08, 0], [0, -0.21], [0.08, 0]])
            pl = pk.extrude(dia, 0.03, chamfer=(0.008 if lod < 2 else 0.0))
            ang = math.atan2(d[1], d[0])
            M = M4(Rz(ang - math.pi / 2) @ Rx(math.pi / 2) @ Rz(0), base + d * 0.16 + np.array([0, 0, top - 0.35]))
            Mrot = M4(Rz(ang + math.pi / 2)) @ M4(Rx(math.pi / 2))
            Mrot[:3, 3] = base[:3] + d * 0.24 + np.array([0, 0, top - 0.35])
            cv = mo.Canvas((-0.085, -0.22, 0.085, 0.22), ppm=2500)
            cv.poly(dia * 0.82)
            inner = mo.Canvas((-0.085, -0.22, 0.085, 0.22), ppm=2500)
            mo.fleur_sprig(inner, (0, -0.01), 0.25, 0.009)
            B.add("root", "inlays", "bronze", pl.transformed(Mrot),
                  meta={"enamel": {"mask": cv.mask(0.002) * (1 - inner.mask(0.001)), "bbox": (-0.085, -0.22, 0.085, 0.22),
                                   "isl": [2], "colour": sh.C(48, 104, 76)},
                        "motif": [{"mask": inner.mask(0.001), "bbox": (-0.085, -0.22, 0.085, 0.22), "isl": (2,),
                                   "depth": 0.003, "mode": "raise"}]})
    # ---------------- top edge arches (two roots per edge) + dome diagonals
    for ci in range(4):
        a = np.array([corners[ci][0] * pc, corners[ci][1] * pc, top])
        b = np.array([corners[(ci + 1) % 4][0] * pc, corners[(ci + 1) % 4][1] * pc, top])
        mid = (a + b) / 2
        out = pk.unit(np.array([mid[0], mid[1], 0])) * 0.06
        for k, (lift, off) in enumerate(((0.22, 0.0), (0.38, -0.08))):
            ctrl = [a + np.array([0, 0, -0.15]), a + (b - a) * 0.25 + np.array([0, 0, lift * 0.8]) + out * (1 - k),
                    mid + np.array([0, 0, lift]) + out, b + (a - b) * 0.25 + np.array([0, 0, lift * 0.8]) + out * (1 - k),
                    b + np.array([0, 0, -0.15])]
            root(B, f"edge_{ci}", ctrl, 0.10 - 0.02 * k, 0.075, B.seg(10, 7, 5), sides, 200 + ci * 10 + k, wobble=0.03)
    for ci in range(2):
        a = np.array([corners[ci][0] * pc, corners[ci][1] * pc, top + 0.05])
        b = np.array([corners[ci + 2][0] * pc, corners[ci + 2][1] * pc, top + 0.05])
        ctrl = [a, a * 0.55 + np.array([0, 0, dome - top - 0.05 + top * 0.45]), np.array([0, 0, dome]),
                b * 0.55 + np.array([0, 0, dome - top - 0.05 + top * 0.45]), b]
        root(B, "dome", ctrl, 0.085, 0.07, B.seg(12, 8, 6), sides, 300 + ci, wobble=0.04)
    if lod < 2:
        for ci in range(4):
            a = np.array([corners[ci][0] * pc, corners[ci][1] * pc, top + 0.1]) * np.array([1, 1, 1])
            mid = np.array([corners[ci][0] * pc * 0.2, corners[(ci + 1) % 4][1] * pc * 0.5, dome - 0.1])
            ctrl = [a, (a + mid) / 2 + np.array([0, 0, 0.35]), mid]
            root(B, "dome2", ctrl, 0.065, 0.045, B.seg(8, 6, 4), 4, 320 + ci, wobble=0.03)
    # ---------------- wall lattices (back, left, right, front-left bay): mullion + lancet arches + crossing roots
    walls = [("x", pc, -pc, pc), ("y", -pc, -pc, pc), ("y", pc, -pc, pc), ("x", -pc, -pc, 0.0)]
    for wi, (axis, fixed, a, b) in enumerate(walls):
        def W(s, z):
            return np.array([s, fixed, z]) if axis == "x" else np.array([fixed, s, z])
        L = b - a
        m = (a + b) / 2
        r = 0.07
        sg = B.seg(8, 6, 4)
        sd = max(3, sides - 1)
        if wi < 3:
            root(B, f"wall_{wi}", [W(m, 0.0), W(m + 0.03, 1.2), W(m, top - 0.1)], r, 0.035, sg, sd, 400 + wi * 10, 0.02)
            for k, (s0, s1) in enumerate(((a + 0.1, m), (m, b - 0.1))):
                c = (s0 + s1) / 2
                root(B, f"wall_{wi}", [W(s0, 0.25), W(s0 + 0.05, 1.5), W(c, top - 0.18), W(s1 - 0.05, 1.5), W(s1, 0.25)],
                     0.06, 0.045, B.seg(10, 7, 5), sd, 410 + wi * 10 + k, 0.02)
            if lod < 2:
                root(B, f"wall_{wi}x", [W(a + 0.15, 0.4), W(m, 1.6), W(b - 0.15, top - 0.2)], 0.05, 0.035, sg, 4,
                     430 + wi * 10, 0.03)
                root(B, f"wall_{wi}x", [W(b - 0.15, 0.4), W(m, 1.6), W(a + 0.15, top - 0.2)], 0.05, 0.035, sg, 4,
                     440 + wi * 10, 0.03)
        else:   # front-left bay (left of the door frame)
            s1 = p["door_x0"] - 0.09
            c = (a + s1) / 2
            root(B, "wall_front", [W(a + 0.15, 0.3), W(a + 0.2, 1.5), W(c, top - 0.15), W(s1 - 0.05, 1.5), W(s1, 0.3)],
                 0.06, 0.045, B.seg(10, 7, 5), sd, 470, 0.02)
            root(B, "wall_front", [W(c, 0.0), W(c + 0.02, 1.2), W(c, top - 0.25)], 0.065, 0.045, sg, sd, 471, 0.02)
            if lod < 2:
                root(B, "wall_frontx", [W(a + 0.2, 0.4), W(c, 1.4), W(s1, top - 0.3)], 0.032, 0.024, sg, 3, 472, 0.03)
    # ---------------- stone floor + kerb
    fl = pk.beam((-pc + 0.1, 0, p["floor_z"] / 2), (pc - 0.1, 0, p["floor_z"] / 2), 2 * pc - 0.2, p["floor_z"], chamfer=0.0)
    B.add("root", "floor", "limestone", fl, meta={"flag_size": 0.42, "moss": 0.25})
    # ---------------- timber door frame (inserted into the roots)
    x0, x1 = p["door_x0"], p["door_x1"]
    fy = -pc
    jh = top - 0.1
    for nm, x in (("jamb_h", x0 - 0.06), ("jamb_l", x1 + 0.06)):
        jb = pk.beam((x, fy, 0.0), (x, fy, jh), 0.16, 0.12, chamfer=(0.015 if lod < 2 else 0.0))
        B.add("root", f"frame_{nm}", "dark_oak", jb)
    lt = pk.beam((x0 - 0.13, fy, jh + 0.06), (x1 + 0.13, fy, jh + 0.06), 0.16, 0.13, chamfer=(0.015 if lod < 2 else 0.0))
    B.add("root", "frame_lintel", "dark_oak", lt)
    # ---------------- plank door
    dfy = fy - 0.08 + 0.01
    dt = p["door_t"]
    dz0, dh = p["floor_z"] + 0.02, p["door_h"]
    dx0, dx1 = x0 + 0.006, x1 - 0.006
    npl = 7 if lod < 2 else 3
    xs = np.linspace(dx0, dx1, npl + 1)
    for k in range(npl):
        xa, xb = xs[k] + 0.006, xs[k + 1] - 0.006
        xc = (xa + xb) / 2
        ztop = dz0 + dh - 0.05 + p["door_arch"] * math.sin(math.pi * (xc - dx0) / (dx1 - dx0))
        pl = pk.beam((xc, dfy + dt / 2, dz0), (xc, dfy + dt / 2, ztop), xb - xa, dt * 0.7, chamfer=(0.008 if lod < 2 else 0.0), up=(0, 1, 0))
        B.add("door", "door_planks", "plank", pl)
    for nm, z, h in (("rail_bot", dz0 + 0.2, 0.12), ("rail_mid", dz0 + 1.05, 0.1), ("rail_top", dz0 + dh - 0.25, 0.1)):
        ra = pk.beam((dx0 + 0.02, dfy - 0.012, z), (dx1 - 0.02, dfy - 0.012, z), 0.03, h, chamfer=(0.008 if lod < 2 else 0.0), up=(0, 1, 0))
        B.add("door", f"door_{nm}", "plank", ra)
    hinge = (dx0 - 0.012, dfy - 0.034, 0.0)
    strap_cv = mo.Canvas((0.0, -0.05, 0.42, 0.05), ppm=2500)
    for k in range(2):
        x = 0.12 + k * 0.14
        strap_cv.line(mo.bezier((x, -0.02), (x + 0.05, 0.03), (x + 0.1, -0.01)), 0.006)
        strap_cv.circle((x + 0.05, 0.01), 0.008)
    strap_motif = [{"mask": strap_cv.mask(0.001), "bbox": (0.0, -0.05, 0.42, 0.05), "isl": (2,), "depth": 0.002,
                    "mode": "cut", "colour": sh.C(52, 108, 80), "tint": 0.95, "rough": 0.35, "metal": 0.0}]
    ck.hinge_set(B, (hinge[0], hinge[1]), [dz0 + 0.45, dz0 + 1.65], 0.42, 0.125, dfy - 0.012, fy - 0.08, cls="bronze",
                 knuckle_r=0.036, strap_motif=strap_motif)
    sz = 1.25
    lock = pk.beam((dx1 - 0.2, dfy - 0.03, sz - 0.25), (dx1 - 0.04, dfy - 0.03, sz - 0.25), 0.06, 0.045, chamfer=(0.008 if lod < 2 else 0.0))
    B.add("door", "lock_box", "iron", lock)
    bolt = pk.beam((dx1 - 0.16, dfy - 0.045, sz - 0.25), (dx1 + 0.11, dfy - 0.045, sz - 0.25), 0.028, 0.028, chamfer=(0.005 if lod < 2 else 0.0))
    B.add("latch", "latch_bolt", "bronze", bolt)
    kn = pk.lathe(np.array([[0.02, 0], [0.02, 0.028], [0.0, 0.034]]), B.seg(8, 6, 4))
    B.add("latch", "latch_bolt", "bronze", kn.transformed(M4(Rx(math.pi / 2), (dx1 - 0.08, dfy - 0.058, sz - 0.25))))
    keeper = pk.sweep(np.array([[x1 + 0.06, fy - 0.08, sz - 0.3], [x1 + 0.06, dfy - 0.07, sz - 0.3],
                                [x1 + 0.06, dfy - 0.07, sz - 0.2], [x1 + 0.06, fy - 0.08, sz - 0.2]]),
                      pk.rect(0.03, 0.012), up=(1, 0, 0), smooth=False)
    B.add("root", "latch_keeper", "iron", keeper)
    ck.add_sockets(B, "diamond", (dx1 - 0.2, dfy - 0.024, sz), plate_cls="bronze", keyhole_cls="bronze")
    return B


build.hinge_z = [P["floor_z"] + 0.02 + 0.45, P["floor_z"] + 0.02 + 1.65]


def main():
    p = P
    x0, x1 = p["door_x0"], p["door_x1"]
    fy = -p["pc"]
    dfy = fy - 0.08 + 0.01
    dx0, dx1 = x0 + 0.006, x1 - 0.006
    sz = 1.25
    cageqa.run(ASSET, build, (dx0 - 0.012, dfy - 0.034, 0.0), (dx1 - 0.08, dfy - 0.045, sz - 0.25),
               (dx1 - 0.2, dfy - 0.024, sz), "diamond", door=(dx0, dx1, p["floor_z"], p["door_h"] + p["door_arch"]),
               front_y=fy, interior=[round(2 * p["pc"] - 0.2, 3)] * 2, clear_h=round(p["top"] - 0.15 - p["floor_z"], 3),
               ref_key="root")


if __name__ == "__main__":
    main()
