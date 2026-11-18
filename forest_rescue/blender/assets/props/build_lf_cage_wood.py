"""lf_cage_wood (OAK cage): timber posts on a limestone footing, shingle hip roof, iron bars with gothic
arches, bronze hinge straps with emerald inlay, round stone socket (stone_rune) + keyhole variant.

Run: python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/props/build_lf_cage_wood.py --iter N
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy
import numpy as np

import cageqa
import cagekit as ck
import motifs as mo
import propkit as pk
import propshaders as sh
from propkit import M4, Rx, Ry, Rz

ASSET = "lf_cage_wood"
# ------------------------------------------------------------------ dimensions (metres, Blender axes)
P = dict(
    W=3.40, D=3.40,            # outer footprint of the timber frame
    pc=1.50,                   # post centre offset from the middle
    post=0.27,                 # post section
    plinth=0.50, plinth_h=0.58, wall_t=0.30, wall_h=0.46,
    floor_z=0.10,
    post_top=3.18, cap_h=0.10, finial_h=0.24,
    beam_z0=2.66, beam_h=0.27, beam_w=0.23, beam_over=0.16,
    roof_over=0.16, roof_apex=3.95, roof_t=0.07,
    hinge_x=0.03,              # hinge post centre x
    door_h=2.30, door_arch=0.14, door_t=0.075,
    rail_z=(1.12, 2.06),
)


def build(lod):
    B = pk.Builder(lod)
    p = P
    pc, post = p["pc"], p["post"]
    front = -pc
    # ---------------- stone footing: corner plinths + low walls + floor + threshold
    for sx in (-1, 1):
        for sy in (-1, 1):
            pl = pk.beam((sx * pc, sy * pc, 0), (sx * pc, sy * pc, p["plinth_h"]), p["plinth"], p["plinth"], chamfer=0.02,
                         up=(0, 1, 0))
            B.add("root", f"plinth_{sx}{sy}", "limestone", pl, meta={"block_len": 0.26, "course_h": 0.29, "moss": 0.5})
    hx = p["hinge_x"]
    walls = [((-pc, -pc), (pc, -pc)), ((-pc, pc), (pc, pc)), ((-pc, -pc), (-pc, pc)), ((pc, -pc), (pc, pc))]
    for i, (a, b) in enumerate(walls):
        a = np.array(a, float)
        b = np.array(b, float)
        if i == 0:   # front wall only left of the hinge post
            b = np.array([hx, -pc])
        d = pk.unit(b - a)
        a2 = a + d * p["plinth"] / 2
        b2 = b - d * (p["plinth"] / 2 if i != 0 else 0.0)
        wl = pk.beam((a2[0], a2[1], p["wall_h"] / 2), (b2[0], b2[1], p["wall_h"] / 2), p["wall_t"], p["wall_h"],
                     chamfer=0.015, up=(0, 0, 1))
        B.add("root", f"wall_{i}", "limestone", wl, meta={"block_len": 0.42, "course_h": 0.23, "moss": 0.45})
    fl = pk.beam((-pc + 0.12, 0, p["floor_z"] / 2), (pc - 0.12, 0, p["floor_z"] / 2), 2 * pc - 0.24, p["floor_z"],
                 chamfer=0.0, up=(0, 0, 1))
    B.add("root", "floor", "limestone", fl, meta={"flag_size": 0.45, "moss": 0.15})
    thr = pk.beam((hx + 0.1, front - 0.12, 0.05), (pc - 0.1, front - 0.12, 0.05), 0.42, 0.10, chamfer=0.015)
    B.add("root", "threshold", "limestone", thr, meta={"block_len": 0.4, "course_h": 0.2, "moss": 0.3})
    # ---------------- timber posts, caps, finials
    tops = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * pc, sy * pc
            po = pk.beam((x, y, p["plinth_h"]), (x, y, p["post_top"]), post, post, chamfer=0.03, up=(0, 1, 0))
            B.add("root", f"post_{sx}{sy}", "oak", po, meta={"moss": 0.1})
            cap = pk.beam((x, y, p["post_top"]), (x, y, p["post_top"] + p["cap_h"]), post + 0.06, post + 0.06, chamfer=0.02,
                          up=(0, 1, 0))
            B.add("root", "post_caps", "oak", cap)
            fin = pk.lathe(np.array([[0.13, 0], [0.13, 0.03], [0.0, p["finial_h"]]]), 4, a0=math.pi / 4,
                           a1=math.pi / 4 + 2 * math.pi, smooth=False)
            B.add("root", "finials", "oak", fin.transformed(M4(None, (x, y, p["post_top"] + p["cap_h"]))))
            tops.append((x, y))
    # hinge post (left jamb of the door, seen from outside)
    hp = pk.beam((hx, front, 0.0), (hx, front, p["beam_z0"]), 0.24, 0.26, chamfer=0.025, up=(0, 1, 0))
    B.add("root", "hinge_post", "oak", hp)
    # ---------------- top beams (plates) with overhang
    z0, bh, bw = p["beam_z0"], p["beam_h"], p["beam_w"]
    zc = z0 + bh / 2
    ov = p["beam_over"]
    for i, (a, b) in enumerate([((-pc - ov, -pc), (pc + ov, -pc)), ((-pc - ov, pc), (pc + ov, pc)),
                                ((-pc, -pc - ov), (-pc, pc + ov)), ((pc, -pc - ov), (pc, pc + ov))]):
        zz = zc if i < 2 else zc + 0.0
        be = pk.beam((a[0], a[1], zz), (b[0], b[1], zz), bw, bh, chamfer=0.025, up=(0, 0, 1))
        B.add("root", f"beam_{i}", "oak", be, meta={"rivets": {"du": 0.42, "v": [bw * 0.5 + 0.02], "r": 0.022,
                                                              "u0": 0.21}})
    # ---------------- curved knee braces (gothic arch braces) and iron bays
    nb = B.seg(9, 6, 3)
    bays = []   # (axis 'x' or 'y', fixed coord, a, b)
    bays.append(("x", -pc, -pc + post / 2, hx - 0.12))            # front-left bay
    bays.append(("x", pc, -pc + post / 2, pc - post / 2))         # back
    bays.append(("y", -pc, -pc + post / 2, pc - post / 2))        # left side
    bays.append(("y", pc, -pc + post / 2, pc - post / 2))         # right side
    for bi, (axis, fixed, a, b) in enumerate(bays):
        def W2(s, z):
            return (s, fixed, z) if axis == "x" else (fixed, s, z)
        L = b - a
        spring = z0 - 0.62
        # knee braces from both posts up into the beam (curved)
        for side, s0, sgn in (("a", a, 1), ("b", b, -1)):
            t = np.linspace(0, 1, nb)
            ang = t * math.pi / 2
            rx, rz = 0.55, 0.62
            pts = np.array([W2(s0 + sgn * rx * (1 - np.cos(q)), spring + rz * np.sin(q)) for q in ang])
            br = pk.sweep(pts, pk.rect(0.13, 0.11, 0.015), up=(0, 0, 1) if axis == "x" else (0, 0, 1), smooth=False,
                          edge_flags=[0, 1] * 4)
            B.add("root", f"brace_{bi}{side}", "oak", br)
        # iron bars
        z_bot = p["wall_h"] if not (bi == 0) else p["wall_h"]
        nbars = max(3, int(round(L / 0.135)))
        xs = np.linspace(a + L / (nbars + 1), b - L / (nbars + 1), nbars)
        bar_r = 0.0175
        n_arch = 2 if L > 2.0 else 1
        arch_w = L / n_arch
        apex = z0 - 0.06
        arch_spring = z0 - 0.62
        for xx in xs:
            # bar top follows the gothic arch it sits under
            k = min(int((xx - a) / arch_w), n_arch - 1)
            ca = a + arch_w * (k + 0.5)
            u = (xx - ca) / (arch_w / 2)
            top = arch_spring + (apex - arch_spring) * max(0.0, 1 - abs(u) ** 1.6)
            bar = pk.rod(W2(xx, z_bot - 0.02), W2(xx, top + 0.02), bar_r, B.seg(6, 5, 4))
            B.add("root", f"bars_{bi}", "iron", bar)
            if lod < 2:
                tip = pk.lathe(np.array([[0.028, 0.0], [0.006, 0.07], [0.0, 0.075]]), 4)
                B.add("root", f"bar_tips_{bi}", "iron", tip.transformed(M4(None, W2(xx, p["rail_z"][1] + 0.02))), max_lod=1)
        for rz in (z_bot + 0.02,) + tuple(p["rail_z"]):
            rail = pk.beam(W2(a, rz), W2(b, rz), 0.035, 0.05, chamfer=0.008, up=(0, 0, 1) if axis == "x" else (0, 0, 1))
            B.add("root", f"rails_{bi}", "iron", rail, meta={"rivets": {"du": 0.135, "v": [0.0175 + 0.025], "r": 0.009}})
        # gothic pointed arches (iron) and a small trefoil tracery ring per arch
        for k in range(n_arch):
            s0 = a + arch_w * k
            s1 = s0 + arch_w
            cen = (s0 + s1) / 2
            n2 = B.seg(10, 7, 4)
            for sgn in (-1, 1):
                t = np.linspace(0, 1, n2)
                rr = arch_w * 0.85
                c0 = cen - sgn * (rr - arch_w / 2)
                ang0 = 0.0
                ang1 = math.acos(np.clip((rr - arch_w / 2) / rr, -1, 1))
                angs = ang0 + (ang1 - ang0) * t
                pts = np.array([W2(c0 + sgn * rr * math.cos(q), arch_spring + (apex - arch_spring) * math.sin(q) / math.sin(ang1))
                                for q in angs])
                arc = pk.sweep(pts, pk.rect(0.045, 0.06, 0.008), up=(0, 0, 1), smooth=False)
                B.add("root", f"arches_{bi}", "iron", arc)
            if lod < 2:
                ring = np.array([W2(cen + 0.12 * math.cos(q), apex - 0.22 + 0.12 * math.sin(q)) for q in
                                 np.linspace(0, 2 * math.pi, B.seg(14, 9, 6), endpoint=False)])
                B.add("root", f"tracery_{bi}", "iron", pk.tube(ring, 0.014, B.seg(5, 4, 3), closed_path=True,
                                                               up=(0, 1, 0) if axis == "x" else (1, 0, 0)), max_lod=1)
    # ---------------- hip roof with shingle steps
    rz0 = z0 + bh
    e = pc + p["roof_over"] + p["beam_over"] * 0.2
    apex = p["roof_apex"]
    nsteps = B.seg(7, 4, 1)
    for q in range(4):
        R = Rz(q * math.pi / 2)
        # one triangular slope facing -Y before rotation, stepped rows
        for r in range(nsteps):
            f0 = r / nsteps
            f1 = (r + 1) / nsteps
            za, zb = rz0 + (apex - rz0) * f0, rz0 + (apex - rz0) * f1
            ya, yb = -e * (1 - f0), -e * (1 - f1)
            xa, xb = e * (1 - f0), e * (1 - f1)
            drop = 0.035 if lod < 2 else 0.0
            V = np.array([[-xa, ya, za - drop], [xa, ya, za - drop], [xb, yb, zb], [-xb, yb, zb],
                          [-xa, ya, za], [xa, ya, za]])
            V = V @ R.T
            pcs = pk.Piece(V)
            uvs = lambda pts: [(pt[0], pt[1]) for pt in pts]
            slope = math.hypot(e, apex - rz0)
            va, vb = f0 * slope, f1 * slope
            pcs.add_face((0, 1, 2, 3), [(-xa, va), (xa, va), (xb, vb), (-xb, vb)], 0, False, 0)
            if drop > 0:
                pcs.add_face((4, 5, 1, 0), [(-xa, va), (xa, va), (xa, va - drop), (-xa, va - drop)], 0, False, 1)
            B.add("root", f"roof_{q}", "shingles", pcs, meta={"row_h": slope / nsteps / 2.0, "shingle_w": 0.17, "moss": 0.2})
        # hip ridge boards
        hip = pk.beam(np.array([e, -e, rz0 + 0.02]) @ R.T, np.array([0, 0, apex + 0.03]) @ R.T, 0.09, 0.06, chamfer=0.01,
                      up=(0, 0, 1))
        B.add("root", "roof_hips", "oak", hip)
    # eave fascia boards
    for q in range(4):
        R = Rz(q * math.pi / 2)
        fa = pk.beam(np.array([-e, -e, rz0 - 0.02]) @ R.T, np.array([e, -e, rz0 - 0.02]) @ R.T, 0.05, 0.1, chamfer=0.01)
        B.add("root", "fascia", "oak", fa)
    fin = pk.lathe(np.array([[0.1, 0], [0.1, 0.12], [0.13, 0.14], [0.0, 0.42]]), 4, a0=math.pi / 4,
                   a1=math.pi / 4 + 2 * math.pi, smooth=False)
    B.add("root", "roof_finial", "oak", fin.transformed(M4(None, (0, 0, apex - 0.05))))
    # ---------------- plaque (emerald enamel half-disc with bronze tree) on the front beam
    pq = np.array([[0.36 * math.cos(q), 0.30 * math.sin(q)] for q in np.linspace(0, math.pi, B.seg(14, 9, 6))])
    pq = np.vstack([pq, [[-0.36, 0.0]]])[:-1]
    plaque = pk.extrude(np.vstack([pq, [[-0.36, -0.02], [0.36, -0.02]]]), 0.04, chamfer=0.01)
    Mp = M4(Rx(math.pi / 2), (0.08, -pc - bw / 2 - 0.0, z0 + 0.02))
    cv = mo.Canvas((-0.37, -0.03, 0.37, 0.31), ppm=1500)
    mo.tree_emblem(cv, (0.0, 0.14), 0.24, 0.016)
    cv.ring((0, 0.0), 0.33, 0.035)
    en = cv.mask(0.002)
    B.add("root", "plaque", "bronze", plaque.transformed(Mp),
          meta={"enamel": {"mask": 1 - en, "bbox": (-0.37, -0.03, 0.37, 0.31), "isl": [2], "colour": sh.C(52, 108, 80)},
                "motif": [{"mask": en, "bbox": (-0.37, -0.03, 0.37, 0.31), "isl": (2,), "depth": 0.004, "mode": "raise"}]})
    # ---------------- door (node 'door'): frame, arched top rail, bars, hinge straps
    dx0, dx1 = hx + 0.12 + 0.008, pc - post / 2 - 0.008
    dfy = -pc - post / 2 + 0.025        # door outer face y
    dt = p["door_t"]
    dz0, dh = p["floor_z"] + 0.02, p["door_h"]
    stile = 0.11
    for nm, x in (("stile_h", dx0 + stile / 2), ("stile_l", dx1 - stile / 2)):
        st = pk.beam((x, dfy + dt / 2, dz0), (x, dfy + dt / 2, dz0 + dh), stile, dt, chamfer=0.012, up=(0, 1, 0))
        B.add("door", f"door_{nm}", "oak", st)
    for nm, z, h in (("rail_bot", dz0 + 0.08, 0.16), ("rail_mid", dz0 + 0.98, 0.09)):
        ra = pk.beam((dx0 + stile, dfy + dt / 2, z), (dx1 - stile, dfy + dt / 2, z), dt, h, chamfer=0.01, up=(0, 1, 0))
        B.add("door", f"door_{nm}", "oak", ra)
    # arched top rail
    na = B.seg(10, 6, 3)
    xs_ = np.linspace(dx0 + stile * 0.5, dx1 - stile * 0.5, na)
    zt = dz0 + dh - 0.06 + p["door_arch"] * np.sin(np.pi * (xs_ - xs_[0]) / (xs_[-1] - xs_[0]))
    arch = pk.sweep(np.stack([xs_, np.full(na, dfy + dt / 2), zt], 1), pk.rect(0.12, dt, 0.012), up=(0, 1, 0), smooth=False)
    B.add("door", "door_arch", "oak", arch)
    nbar = 6
    for k, xx in enumerate(np.linspace(dx0 + stile + 0.07, dx1 - stile - 0.07, nbar)):
        ztop = dz0 + dh - 0.06 + p["door_arch"] * math.sin(math.pi * (xx - xs_[0]) / (xs_[-1] - xs_[0]))
        bar = pk.rod((xx, dfy + dt / 2, dz0 + 0.15), (xx, dfy + dt / 2, ztop - 0.03), 0.017, B.seg(6, 5, 4))
        B.add("door", "door_bars", "iron", bar)
    # hinges: axis on the left jamb, outside of the door face
    hinge = (dx0 - 0.012, dfy - 0.03, 0.0)
    strap_cv = mo.Canvas((0.0, -0.06, 0.5, 0.06), ppm=2500)
    for k in range(3):
        x = 0.1 + k * 0.12
        strap_cv.line(np.array([[x, 0.0], [x + 0.03, 0.025], [x + 0.06, 0.0], [x + 0.03, -0.025], [x, 0.0]]), 0.006)
        strap_cv.circle((x + 0.03, 0.0), 0.012)
    strap_motif = [{"mask": strap_cv.mask(0.001), "bbox": (0.0, -0.06, 0.5, 0.06), "isl": (2,), "depth": 0.002,
                    "mode": "cut", "colour": sh.C(52, 108, 80), "tint": 0.95, "rough": 0.35, "metal": 0.0}]
    ck.hinge_set(B, (hinge[0], hinge[1]), [dz0 + 0.42, dz0 + 1.92], 0.50, 0.11, dfy, -pc - post / 2,
                 cls="bronze", knuckle_r=0.03, strap_motif=strap_motif)
    # latch: lock box under the socket + sliding bolt into a keeper on the right corner post
    sz = 1.25
    lock = pk.beam((dx1 - 0.2, dfy - 0.02, sz - 0.25), (dx1 - 0.04, dfy - 0.02, sz - 0.25), 0.07, 0.045, chamfer=0.008)
    B.add("door", "lock_box", "iron", lock, meta={"rivets": {"du": 0.05, "v": [0.04], "r": 0.008}})
    bolt = pk.beam((dx1 - 0.16, dfy - 0.035, sz - 0.25), (dx1 + 0.10, dfy - 0.035, sz - 0.25), 0.03, 0.03, chamfer=0.006)
    B.add("latch", "latch_bolt", "bronze", bolt)
    kn = pk.lathe(np.array([[0.022, 0], [0.022, 0.03], [0.0, 0.036]]), B.seg(8, 6, 4))
    B.add("latch", "latch_bolt", "bronze", kn.transformed(M4(Rx(math.pi / 2), (dx1 - 0.08, dfy - 0.05, sz - 0.25))))
    keeper = pk.sweep(np.array([[pc - post / 2 + 0.03, dfy - 0.0, sz - 0.25 - 0.05], [pc - post / 2 + 0.03, dfy - 0.065, sz - 0.25 - 0.05],
                                [pc - post / 2 + 0.03, dfy - 0.065, sz - 0.25 + 0.05], [pc - post / 2 + 0.03, dfy - 0.0, sz - 0.25 + 0.05]]),
                      pk.rect(0.03, 0.012), up=(1, 0, 0), smooth=False)
    B.add("root", "latch_keeper", "iron", keeper)
    # sockets
    sock = (dx1 - 0.2, dfy - 0.012, sz)
    ck.add_sockets(B, "circle", sock, plate_cls="limestone_fine", keyhole_cls="limestone_fine")
    return B


GEOM = {}


def main():
    pr = P
    pc, post = pr["pc"], pr["post"]
    hx = pr["hinge_x"]
    dx0, dx1 = hx + 0.12 + 0.008, pc - post / 2 - 0.008
    dfy = -pc - post / 2 + 0.025
    hinge = (dx0 - 0.012, dfy - 0.03, 0.0)
    sock = (dx1 - 0.2, dfy - 0.012, 1.25)
    latch = (dx1 - 0.08, dfy - 0.035, 1.0)
    cageqa.run(ASSET, build, hinge, latch, sock, "circle",
               door=(dx0, dx1, pr["floor_z"], pr["door_h"] + pr["door_arch"]),
               front_y=-pc, interior=[round(2 * (pc - pr["wall_t"] / 2), 3)] * 2,
               clear_h=round(pr["beam_z0"] - pr["floor_z"], 3), ref_key="oak")


if __name__ == "__main__":
    main()
