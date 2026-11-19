"""lf_cage_wood (OAK) from art/cage_variants_gate_sockets.png (left column): square weathered-oak pavilion on a
limestone footing, slate hip roof with pyramid finials, curved knee braces, iron bars with gothic tracery, a fixed
bar bay + hinge post + barred oak door on the front face, bronze strap hinges (LEFT jamb seen from outside),
round spiral stone socket, half-disc enamel tree emblem over the door.
"""
import math

import numpy as np

import cagegeo as CG
import cage_common as CC
import pv2

ID = "lf_cage_wood"
ATLAS = 2048
NATIVE = "stone_rune"
SHEET = "cage_variants_gate_sockets.png"
LIGHT = (-0.55, -0.55, 0.62)

# ---------------------------------------------------------------- blueprint (metres) - solved jointly with cameras
PARAMS = dict(c=1.60, cy=1.60, s=0.29, e=0.085, hb=0.58, zf=3.62, zr=4.15, bt=3.10, bh=0.28, ov=0.20,
              hx=0.08, dx1=1.305, dz0=0.13, sz=1.08, sx=1.12, zda=2.42)
FREE = ["cy", "e", "hb", "zf", "zr", "bt", "bh", "ov", "hx", "dx1", "dz0", "sz", "sx", "zda"]


def points(p):
    c, s, e = p["c"], p["s"], p["e"]
    q = s / 2 + e
    yf = -c - 0.06
    bw = 0.23
    return {
        "fin_n": (-c, -c, p["zf"]), "fin_l": (-c, c, p["zf"]), "fin_r": (c, -c, p["zf"]),
        "apex": (0.0, 0.0, p["zr"]),
        "base_n0": (-c - q, -c - q, 0.0), "base_n1": (-c - q, -c - q, p["hb"]),
        "base_l0": (-c - q, c + q, 0.0), "base_r0": (c + q, -c - q, 0.0),
        "door_bl": (p["hx"] + 0.122, yf, p["dz0"]), "door_br": (p["dx1"], yf, p["dz0"]),
        "door_ap": ((p["hx"] + 0.122 + p["dx1"]) / 2, yf, p["zda"]),
        "sock": (p["sx"], yf - 0.05, p["sz"]),
        "beam_r_t": (c + s / 2 + p["ov"], -c - bw / 2, p["bt"]), "beam_r_b": (c + s / 2 + p["ov"], -c - bw / 2, p["bt"] - p["bh"]),
        "beam_l_t": (-c - bw / 2, c + s / 2 + p["ov"], p["bt"]), "beam_l_b": (-c - bw / 2, c + s / 2 + p["ov"], p["bt"] - p["bh"]),
    }


def views():
    closed = pv2.ViewSpec(
        "closed34", SHEET, (100, 108, 466, 432),
        {"fin_n": (223, 120), "fin_l": (124.6, 153), "fin_r": (435, 143), "apex": (295, 118),
         "base_n0": (215, 428), "base_n1": (215, 369), "base_l0": (103, 404), "base_r0": (456, 411),
         "door_bl": (314, 409), "door_br": (420, 404), "door_ap": (366, 222), "sock": (400, 317),
         "beam_r_t": (450, 168), "beam_r_b": (450, 192), "beam_l_t": (106, 181), "beam_l_b": (106, 200)},
        light=LIGHT, thresh=0.11, fill_holes=30, shadow=0.10, title="OAK closed 3/4")
    return [closed]


# ---------------------------------------------------------------- geometry
def bar_face(g, origin, ex, L, z_bot, z_r1, z_r2, z_spring, z_apex, n_arch, spacing, lod, tag):
    """Iron bars + rails + gothic pointed arches in a vertical face. origin = start point (x, y) on the face
    line, ex = unit direction along the face."""
    o = np.array([origin[0], origin[1], 0.0])
    ex = np.array([ex[0], ex[1], 0.0])
    nb = max(3, int(round(L / spacing)) - 1)
    if lod == 2:
        nb = max(3, nb // 2)
    ts = np.linspace(0, L, nb + 2)[1:-1]
    w = L / n_arch
    rise = z_apex - z_spring
    for t in ts:
        k = min(int(t / w), n_arch - 1)
        a0 = k * w
        local = (t - a0) / w
        # height of the pointed arch above this bar
        r = (w * w / 4 + rise * rise) / w
        dx = abs(local - 0.5) * w
        top = z_spring + math.sqrt(max(r * r - (r - w / 2 + dx) ** 2, 0.0)) if lod < 2 else z_apex
        top = min(top, z_apex)
        p0 = o + ex * t + (0, 0, z_bot)
        p1 = o + ex * t + (0, 0, top)
        g.cyl(p0, p1, 0.019, n=6 if lod == 0 else 4, mat="iron", tag=tag + "_bar", caps=(False, False))
        if lod == 0:
            CG.lathe(g, [(0.032, 0.0), (0.0, 0.085)], o + ex * t + (0, 0, z_r2 + 0.02), n=4, mat="iron", tag=tag + "_tip")
    R = CG.frame(ex)
    for zr in (z_bot + 0.03, z_r1, z_r2):
        g.box(o + ex * (L / 2) + (0, 0, zr), (L, 0.04, 0.055), R=R, mat="iron", tag=tag + "_rail")
    if lod < 2:
        n = 7 if lod == 0 else 4
        for k in range(n_arch):
            Lp, Rp = CG.pointed_arch(k * w, (k + 1) * w, z_spring, rise, n)
            for pts in (Lp, Rp):
                P = np.array([o + ex * s_ + (0, 0, z_) for s_, z_ in pts])
                CG.sweep_rect(g, P, 0.04, 0.05, up=(0, 0, 1), mat="iron", tag=tag + "_arch")
            if lod == 0:
                # inner trefoil ring under the apex
                cc = o + ex * ((k + 0.5) * w) + (0, 0, z_spring + rise * 0.42)
                ring = [cc + ex * (0.10 * math.cos(a)) + np.array([0, 0, 0.10 * math.sin(a)]) for a in
                        np.linspace(0, 2 * math.pi, 9)[:-1]]
                g.tube(np.array(ring + [ring[0]]), 0.014, n=4, mat="iron", tag=tag + "_trace")


def knee_brace(g, post_xy, ex, z_spring, z_beam_bottom, reach, lod, tag, w=0.13, h=0.11):
    o = np.array([post_xy[0], post_xy[1], 0.0])
    ex = np.array([ex[0], ex[1], 0.0])
    n = 7 if lod == 0 else (5 if lod == 1 else 3)
    pts = []
    for t in np.linspace(0, 1, n):
        a = t * math.pi / 2
        pts.append(o + ex * (reach * (1 - math.cos(a))) + (0, 0, z_spring + (z_beam_bottom + 0.04 - z_spring) * math.sin(a)))
    nrm = np.cross(ex, (0, 0, 1))
    CG.sweep_rect(g, np.array(pts), w, h, up=nrm, mat="wood", tag=tag)


def leaf_inlay(g, c, R, size=0.16, lod=0):
    poly = []
    for t in np.linspace(0, 1, 9):
        z = -size / 2 + size * t
        x = 0.42 * size * math.sin(math.pi * t) ** 0.9 * (1 - 0.25 * t)
        poly.append((x, z))
    for t in np.linspace(1, 0, 9)[1:-1]:
        z = -size / 2 + size * t
        x = -0.42 * size * math.sin(math.pi * t) ** 0.9 * (1 - 0.25 * t)
        poly.append((x, z))
    g.prism(np.array(poly), 0.0, 0.012, "enamel", "leaf_inlay", R=R, t=c)


def build(A, p, lod):
    rng = np.random.default_rng(3 + lod)
    c, s, e, hb = p["c"], p["s"], p["e"], p["hb"]
    q = s / 2 + e
    bt, bh, ov = p["bt"], p["bh"], p["ov"]
    bb = bt - bh
    zp = p["zf"] - 0.34
    hx = p["hx"]
    g = A.g("root", lod)
    floor_z = 0.12
    # ---------------- limestone footing: corner plinths, walls (door opening left free), floor, threshold
    for sx_ in (-1, 1):
        for sy_ in (-1, 1):
            CG.masonry_run(g, (sx_ * c - q, sy_ * c), (sx_ * c + q, sy_ * c), 0.0, hb, 2 * q, 2, 0.25, rng,
                           tag="plinth", lod=lod)
    wt = 0.34
    runs = [((-c + q, c), (c - q, c)),                       # back
            ((-c, -c + q), (-c, c - q)),                     # left
            ((c, -c + q), (c, c - q)),                       # right
            ((-c + q, -c), (hx - 0.11, -c))]                 # front, left of the hinge post
    for a, b in runs:
        CG.masonry_run(g, a, b, 0.0, hb, wt, 2, 0.36 if lod == 0 else 0.6, rng, tag="basewall", lod=lod)
    g.box((0, 0, floor_z / 2), (2 * (c - wt / 2) + 0.02, 2 * (c - wt / 2) + 0.02, floor_z), mat="stone", tag="floor",
          skip=("-z",))
    door_w0, door_w1 = hx - 0.11, c - q
    g.box(((door_w0 + door_w1) / 2, -c, floor_z / 2), (door_w1 - door_w0, wt + 0.02, floor_z), mat="stone",
          tag="floor_sill", skip=("-z",))
    g.box(((door_w0 + door_w1) / 2 + 0.02, -c - wt / 2 - 0.2, 0.05), (door_w1 - door_w0 + 0.16, 0.4, 0.10),
          mat="stone", tag="threshold", skip=("-z",))
    # ---------------- timber posts, feet, caps, finials
    for sx_ in (-1, 1):
        for sy_ in (-1, 1):
            x, y = sx_ * c, sy_ * c
            g.box((x, y, (hb + zp) / 2), (s, s, zp - hb), mat="wood", tag="post", chamfer=0.0)
            g.box((x, y, hb + 0.07), (s + 0.035, s + 0.035, 0.14), mat="wood", tag="post_foot", skip=("-z",))
            g.box((x, y, zp + 0.05), (s + 0.06, s + 0.06, 0.10), mat="wood", tag="post_cap")
            CG.pyramid(g, (x, y, zp + 0.10), s + 0.02, p["zf"] - zp - 0.10 - 0.04, mat="wood", tag="finial",
                       base_h=0.04 if lod < 2 else 0.0)
    # hinge post (left jamb of the door, seen from outside)
    g.box((hx, -c, bb / 2), (0.22, 0.24, bb), mat="wood", tag="hinge_post", skip=("-z",))
    # ---------------- top plates (beams) with overhanging ends, lintel + emblem over the door
    bw = 0.23
    L = 2 * (c + s / 2 + ov)
    g.box((0, -c, bt - bh / 2), (L, bw, bh), mat="wood", tag="beam_x")
    g.box((0, c, bt - bh / 2), (L, bw, bh), mat="wood", tag="beam_x")
    g.box((-c, 0, bt - bh / 2), (bw - 0.01, L, bh - 0.01), mat="wood", tag="beam_y")
    g.box((c, 0, bt - bh / 2), (bw - 0.01, L, bh - 0.01), mat="wood", tag="beam_y")
    x0d, x1d = hx + 0.122, p["dx1"]
    xc = (x0d + x1d) / 2
    zl0 = p["zda"] + 0.02
    g.box(((hx - 0.11 + c - s / 2) / 2, -c, (zl0 + bb) / 2), (c - s / 2 - hx + 0.11, 0.2, bb - zl0), mat="wood", tag="lintel")
    nr = 14 if lod == 0 else (9 if lod == 1 else 6)
    half = [(0.36 * math.cos(a), 0.36 * math.sin(a)) for a in np.linspace(0, math.pi, nr)]
    Rm = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)
    g.prism(np.array(half), 0.0, 0.05, "enamel", "emblem", R=Rm, t=(xc, -c - 0.10, zl0 + 0.02))
    if lod < 2:
        arc = np.array([(xc + 0.36 * math.cos(a), -c - 0.15, zl0 + 0.02 + 0.36 * math.sin(a)) for a in np.linspace(0, math.pi, nr)])
        g.tube(arc, 0.03, n=5, mat="wood", tag="emblem_rim")
    # bolts with green caps on the beams (LOD0)
    if lod == 0:
        for (x, y, nrm) in ((-c, -c - bw / 2, (0, -1, 0)), (c, -c - bw / 2, (0, -1, 0)), (-c - bw / 2, -c, (-1, 0, 0)),
                            (-c - bw / 2, c, (-1, 0, 0)), (-c - bw / 2 + 0.01, -c - s / 2 - ov + 0.08, (-1, 0, 0))):
            pnt = np.array([x, y, bt - bh / 2]) + np.array(nrm) * 0.01
            g.cyl(pnt, pnt + np.array(nrm) * 0.03, 0.035, n=8, mat="enamel", tag="bolt")
    # ---------------- knee braces (curved) in every bay
    z_spring = bb - 0.78
    for (pxy, ex) in [((-c + s / 2, -c), (1, 0)), ((c - s / 2, -c), (-1, 0)),
                      ((-c, -c + s / 2), (0, 1)), ((-c, c - s / 2), (0, -1)),
                      ((-c + s / 2, c), (1, 0)), ((c - s / 2, c), (-1, 0)),
                      ((c, -c + s / 2), (0, 1)), ((c, c - s / 2), (0, -1))]:
        knee_brace(g, pxy, ex, z_spring, bb, 0.62, lod, "brace")
    # ---------------- iron bar faces
    z_r1 = hb + 0.238 * (bb - hb)
    z_r2 = hb + 0.606 * (bb - hb)
    zs_ = z_r2 + 0.06
    zap = bb - 0.05
    span = 2 * c - s
    bar_face(g, (-c, -c + s / 2), (0, 1), span, hb, z_r1, z_r2, zs_, zap, 2, 0.15, lod, "left")
    bar_face(g, (-c + s / 2, c), (1, 0), span, hb, z_r1, z_r2, zs_, zap, 2, 0.15, lod, "back")
    bar_face(g, (c, -c + s / 2), (0, 1), span, hb, z_r1, z_r2, zs_, zap, 2, 0.15, lod, "right")
    bar_face(g, (-c + s / 2, -c), (1, 0), (hx - 0.11) - (-c + s / 2), hb, z_r1, z_r2, zs_, zap, 1, 0.14, lod, "frontbay")
    # ---------------- hip roof + apex finial
    half_e = c + s / 2 + ov + 0.06
    apex_z = p["zr"] - 0.40
    CG.hip_roof(g, bt, half_e, apex_z, 6 if lod == 0 else (4 if lod == 1 else 1), lod, mat="roof", tag="roof")
    g.box((0, 0, apex_z + 0.03), (0.2, 0.2, 0.14), mat="wood", tag="apex_block")
    CG.pyramid(g, (0, 0, apex_z + 0.10), 0.2, p["zr"] - apex_z - 0.10, mat="wood", tag="apex_finial")
    # ---------------- enamel leaf inlays on post faces (front / left)
    if lod < 2:
        Rf = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)          # facing -Y
        Rl = np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]], float).T       # facing -X
        Rl = np.stack([[0, -1, 0], [0, 0, 1], [-1, 0, 0]], 1).astype(float)
        zi = hb + 0.47 * (bb - hb)
        leaf_inlay(g, (-c, -c - s / 2 - 0.002, zi), Rf, 0.17, lod)
        leaf_inlay(g, (c, -c - s / 2 - 0.002, zi), Rf, 0.17, lod)
        leaf_inlay(g, (-c - s / 2 - 0.002, c, zi), Rl, 0.17, lod)
    # ---------------- door, hinges, sockets, latch
    cfg = door_cfg(p)
    piv = CC.add_door_and_sockets(A, cfg, lod, NATIVE)
    # pintle plates on the hinge post (static)
    for zz in cfg["strap_z"]:
        g.box((hx + 0.03, -c - 0.125, zz), (0.14, 0.012, 0.16), mat="bronze", tag="pintle")
    if lod == 0:
        CC.add_markers(A, cfg, piv)
    return A


def door_cfg(p):
    c, s = p["c"], p["s"]
    hx = p["hx"]
    zda = p["zda"]
    return dict(hinge_x=hx + 0.11, y_face=-c - 0.06, thick=0.08, x1=p["dx1"], z0=p["dz0"],
                z_top_side=zda - 0.24, z_apex=zda, stile_w=0.11, rail_h=0.17, bars=6, bar_r=0.018,
                rails_z=(p["dz0"] + 0.55, p["dz0"] + 1.32), socket_x=p["sx"], socket_z=p["sz"],
                strap_z=(p["dz0"] + 0.55, p["dz0"] + 1.62), strap_len=0.44, latch_z=p["sz"] + 0.28,
                floor_z=0.12, captive_slots_xz=[(-0.72, 0.1), (0.05, -0.45), (0.74, 0.18)],
                exit=[(hx + 0.6, -c + 0.5, 0.12), (hx + 0.6, -c - 0.3, 0.12), (hx + 0.6, -c - 1.4, 0.0),
                      (hx + 0.6, -c - 2.6, 0.0)],
                wood_mat="wood", socket_mat="stone")


SWATCHES = {
    "wood": dict(sheet=SHEET, box=(209, 250, 241, 282), metres=0.27),
    "iron": dict(sheet=SHEET, box=(140, 330, 170, 345), metres=0.2),
    "stone": dict(sheet=SHEET, box=(130, 372, 170, 412), metres=0.36),
    "roof": dict(sheet=SHEET, box=(322, 136, 352, 158), metres=0.4),
    "bronze": dict(sheet=SHEET, box=(178, 838, 210, 868), metres=0.06),
    "enamel": dict(sheet=SHEET, box=(326, 190, 344, 202), metres=0.1),
}


def clips(A, B):
    CC.add_clips(A, B)


def meta(A, p):
    cfg = door_cfg(p)
    piv = np.array([cfg["hinge_x"], cfg["y_face"] - 0.035, 0.0])
    return CC.cage_meta(A, cfg, piv, NATIVE, {"cage_type": "oak", "native_family": NATIVE})
