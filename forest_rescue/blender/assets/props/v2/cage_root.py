"""lf_cage_root (ROOT) from art/cage_variants_gate_sockets.png (right column): living-root enclosure. Four corner
trunks of three thick roots twisted together (swept tubes along twisted centrelines with taper) flaring into
buttress roots on the ground, twisted root arches over every face and diagonally over the top (a domed lattice),
pointed-oval (gothic lancet) lattices of thinner roots in the walls, emerald leaf emblems (bronze rim) on the trunks,
a separate timber-framed slatted door on a wooden jamb post (bronze hinges on the LEFT jamb seen from outside) with
the amber diamond socket, flat limestone floor slabs and a stone threshold.
"""
import math

import numpy as np

import cagegeo as CG
import cage_common as CC
import pv2

ID = "lf_cage_root"
ATLAS = 2048
NATIVE = "amber_crystal"
SHEET = "cage_variants_gate_sockets.png"
LIGHT = (-0.55, -0.55, 0.62)
BOXES = {"closed34": (1062, 104, 1466, 426), "open34": (1062, 430, 1488, 736)}

PARAMS = dict(c=1.62, cy=1.40, ze=2.05, zt=2.75, zc=3.25, kx=0.0, ky=0.0, hx=-0.20, dx1=1.20, dz0=0.10, zda=2.30,
              sx=1.02, sz=1.20)
FREE = ["cy", "ze", "zt", "zc", "kx", "ky", "hx", "dx1", "dz0", "zda", "sx", "sz"]
RT = 0.24          # trunk bundle radius


def points(p):
    c, cy = p["c"], p["cy"]
    yf = -cy - 0.04
    d = 1 / math.sqrt(2)
    return {
        "emb_n": (-c - RT * d, -cy - RT * d, p["ze"]), "emb_l": (-c - RT, cy, p["ze"]), "emb_r": (c + RT, -cy, p["ze"]),
        "base_n": (-c, -cy, 0.0), "base_l": (-c, cy, 0.0), "base_r": (c, -cy, 0.0), "base_b": (c, cy, 0.0),
        "door_bl": (p["hx"] + 0.11, yf, p["dz0"]), "door_br": (p["dx1"], yf, p["dz0"]),
        "door_ap": ((p["hx"] + 0.11 + p["dx1"]) / 2, yf, p["zda"]), "sock": (p["sx"], yf - 0.05, p["sz"]),
        "jamb_top": (p["hx"] - 0.11, -cy - 0.11, p["zda"] + 0.18), "crown": (p["kx"], p["ky"], p["zc"]),
    }


def views():
    closed = pv2.ViewSpec(
        "closed34", SHEET, BOXES["closed34"],
        {"emb_n": (1223, 195), "emb_l": (1094, 200), "emb_r": (1423, 199), "base_n": (1223.3, 412),
         "base_l": (1103.3, 396), "base_r": (1420, 400), "door_bl": (1313.3, 406.7), "door_br": (1408.3, 400),
         "door_ap": (1356.7, 228.3), "sock": (1388, 318), "jamb_top": (1289.3, 215), "crown": (1260, 116.7)},
        light=LIGHT, thresh=0.10, fill_holes=30, shadow=0.10, title="ROOT closed 3/4")
    opened = pv2.ViewSpec(
        "open34", SHEET, BOXES["open34"],
        {"emb_n": (1212, 511.7), "emb_l": (1091.3, 525), "emb_r": (1396.3, 521.7), "base_n": (1208.7, 723.3),
         "base_l": (1095.3, 703.3), "base_b": (1267, 678.3), "crown": (1243.7, 440)},
        light=LIGHT, thresh=0.10, fill_holes=30, shadow=0.10, hide_parts=("door_pivot",), tex_weight=0.75,
        render_pose={"door_pivot": {"rot": (0, 0, -math.radians(95))}}, ignore_boxes=[(1375, 520, 1488, 736)],
        iou_ignore=("door_pivot",),
        title="ROOT open 3/4 (painted door on the RIGHT jamb = drawing inconsistency; production rule LEFT jamb -> "
              "door region ignored)")
    return [closed, opened]


def ground_poly(p):
    c, cy = p["c"], p["cy"]
    m = 0.75
    return [(-c - m, -cy - m - 0.3, 0), (c + m, -cy - m - 0.3, 0), (c + m, cy + m, 0), (-c - m, cy + m, 0)]


# ---------------------------------------------------------------- organic helpers
def sides(lod, big=True):
    return (6 if big else 5) if lod == 0 else ((5 if big else 4) if lod == 1 else 3)


def wobble(P, amp, seed, freq=3.0):
    rng = np.random.default_rng(seed)
    P = np.asarray(P, float).copy()
    t = np.linspace(0, 1, len(P))
    ph = rng.uniform(0, 6.28, 3)
    env = np.sin(np.pi * t)
    for k in range(3):
        P[:, k] += amp * env * np.sin(freq * 2 * np.pi * t + ph[k])
    return P


def twisted_pair(g, P, r, twist_turns, sep, lod, tag, seed=0, taper=(1.0, 0.8), strands=2):
    """Two (or three) roots twisted around the centreline P."""
    P = np.asarray(P, float)
    m = len(P)
    T = np.gradient(P, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    up = np.array([0, 0, 1.0])
    for k in range(strands):
        Q = []
        for i in range(m):
            t = i / (m - 1)
            a = 2 * np.pi * (k / strands + twist_turns * t) + seed
            ref = up if abs(T[i] @ up) < 0.9 else np.array([1.0, 0, 0])
            u = np.cross(T[i], ref)
            u /= np.linalg.norm(u)
            v = np.cross(T[i], u)
            Q.append(P[i] + sep * (math.cos(a) * u + math.sin(a) * v))
        rr = r * np.linspace(taper[0], taper[1], m)
        g.tube(np.array(Q), rr, n=sides(lod, r > 0.05), mat="root", tag=tag)


def trunk(g, x, y, z_top, lod, seed, out_dir):
    """Three roots twisted into a column, flaring into buttress roots at the ground."""
    n = 9 if lod == 0 else (7 if lod == 1 else 5)
    out_dir = np.asarray(out_dir, float)
    for k in range(3):
        a0 = 2 * np.pi * k / 3 + seed
        Q = []
        for i in range(n):
            t = i / (n - 1)
            z = 0.02 + (z_top - 0.02) * t
            ang = a0 + 2 * np.pi * 0.9 * t
            rho = 0.13 + 0.5 * max(0.0, 0.28 - t) ** 1.6 * 3.0
            Q.append((x + rho * math.cos(ang), y + rho * math.sin(ang), z))
        Q = np.array(Q)
        Q[0, 2] = 0.0
        rr = np.linspace(0.15, 0.11, n)
        g.tube(Q, rr, n=sides(lod), mat="root", tag="trunk")
    # buttress roots on the ground
    nb = 6 if lod == 0 else (4 if lod == 1 else 2)
    rng = np.random.default_rng(abs(int(seed * 100)) + 3)
    for j in range(nb):
        a = math.atan2(out_dir[1], out_dir[0]) + (j - (nb - 1) / 2) * (1.5 / max(nb - 1, 1)) + rng.uniform(-0.12, 0.12)
        L = rng.uniform(0.5, 0.85)
        pts = []
        m = 5 if lod == 0 else 4
        for i in range(m):
            t = i / (m - 1)
            rad = 0.14 + L * t
            z = 0.42 * (1 - t) ** 1.8 + 0.03
            pts.append((x + rad * math.cos(a + 0.25 * t), y + rad * math.sin(a + 0.25 * t), z))
        g.tube(np.array(pts), np.linspace(0.12, 0.03, m), n=sides(lod, False), mat="root", tag="buttress")


def arch_curve(a, b, z0, rise, n, bulge=None):
    """Pointed arch from a to b (3-D points at z0), apex rise above z0."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    pts = []
    for t in np.linspace(0, 1, n):
        q = a + (b - a) * t
        s_ = 1 - abs(2 * t - 1)
        q[2] = z0 + rise * (1 - (1 - s_) ** 1.6)
        if bulge is not None:
            q = q + np.asarray(bulge, float) * math.sin(math.pi * t)
        pts.append(q)
    return np.array(pts)


def lancet_lattice(g, origin, ex, L, z0, z1, n_lancet, lod, tag, seed=0):
    """Pointed-oval (vesica) lattice of thin roots between z0 and z1 along a face."""
    o = np.array([origin[0], origin[1], 0.0])
    ex = np.array([ex[0], ex[1], 0.0])
    w = L / n_lancet
    m = 7 if lod == 0 else (5 if lod == 1 else 4)
    for j in range(n_lancet):
        sc = (j + 0.5) * w
        for sgn in (-1, 1):
            pts = []
            for t in np.linspace(0, 1, m):
                z = z0 + (z1 - z0) * t
                s_ = sc + sgn * (w * 0.5) * math.sin(math.pi * t) ** 0.8
                pts.append(o + ex * s_ + (0, 0, z))
            P = wobble(np.array(pts), 0.012, seed + j * 7 + (sgn > 0), 1.5)
            g.tube(P, np.linspace(0.06, 0.045, m), n=sides(lod, False), mat="root", tag=tag)
    if lod < 2:
        # two diagonal roots crossing the lower half
        for sgn in (-1, 1):
            a = o + ex * (0.0 if sgn > 0 else L) + (0, 0, z0 + 0.05)
            b = o + ex * (L if sgn > 0 else 0.0) + (0, 0, z0 + (z1 - z0) * 0.55)
            P = wobble(np.linspace(a, b, m), 0.02, seed + 31 + sgn, 1.2)
            g.tube(P, np.linspace(0.055, 0.045, m), n=sides(lod, False), mat="root", tag=tag)


def leaf_emblem(g, c, out, lod, w=0.22, h=0.52):
    out = np.asarray(out, float)
    out /= np.linalg.norm(out)
    R = CG.frame(np.cross((0, 0, 1), out), out)             # local x along the trunk surface, z = outward
    R = np.stack([R[:, 0], np.array([0, 0, 1.0]), out], 1)
    n = 10 if lod == 0 else 6
    poly = [(w / 2 * math.sin(math.pi * t) ** 0.85 * (1 if k == 0 else -1), -h / 2 + h * t)
            for k in (0, 1) for t in (np.linspace(0, 1, n) if k == 0 else np.linspace(1, 0, n)[1:-1])]
    poly = np.array(poly)
    g.prism(poly, 0.0, 0.035, "enamel", "leaf_emblem", R=R, t=c)
    if lod < 2:
        rim = np.array([c + R @ np.array([px * 1.08, py * 1.05, 0.03]) for px, py in poly] + [c + R @ np.array([poly[0][0] * 1.08, poly[0][1] * 1.05, 0.03])])
        g.tube(rim, 0.016, n=4, mat="bronze", tag="leaf_rim")


def build(A, p, lod):
    c, cy = p["c"], p["cy"]
    zt, zc = p["zt"], p["zc"]
    hx = p["hx"]
    g = A.g("root", lod)
    rng = np.random.default_rng(5 + lod)
    corners = [(-c, -cy), (-c, cy), (c, cy), (c, -cy)]
    outs = [(-1, -1), (-1, 1), (1, 1), (1, -1)]
    # ---------------- floor slabs + threshold
    floor_z = 0.10
    nx, ny = (4, 3) if lod < 2 else (2, 2)
    xs = np.linspace(-c + 0.1, c - 0.1, nx + 1)
    ys = np.linspace(-cy + 0.1, cy - 0.1, ny + 1)
    for i in range(nx):
        for j in range(ny):
            cx_ = (xs[i] + xs[i + 1]) / 2
            cy_ = (ys[j] + ys[j + 1]) / 2
            sz = (xs[i + 1] - xs[i] - 0.02, ys[j + 1] - ys[j] - 0.02, floor_z)
            g.box((cx_, cy_, floor_z / 2), sz, mat="stone", tag="floor", skip=("-z",))
    x0d, x1d = hx - 0.1, p["dx1"] + 0.1
    for k in range(3 if lod < 2 else 1):
        a = x0d + (x1d - x0d) * k / 3
        b = x0d + (x1d - x0d) * (k + 1) / 3 if lod < 2 else x1d
        g.box(((a + b) / 2, -cy - 0.32, 0.04), (b - a - 0.02, 0.45, 0.08), mat="stone", tag="threshold", skip=("-z",))
    # ---------------- corner trunks (twisted roots) + leaf emblems
    for (x, y), o in zip(corners, outs):
        trunk(g, x, y, zt, lod, seed=0.7 * (x + 2 * y), out_dir=o)
        oc = np.array([o[0], o[1], 0.0]) / math.sqrt(2)
        if not (x > 0 and y > 0):
            leaf_emblem(g, np.array([x, y, p["ze"]]) + oc * (RT + 0.02), oc, lod)
    # ---------------- canopy: twisted arches over every face + diagonals to the crown
    n_arc = 9 if lod == 0 else (6 if lod == 1 else 4)
    crown = np.array([p["kx"], p["ky"], zc])
    for i in range(4):
        a = np.array([*corners[i], zt])
        b = np.array([*corners[(i + 1) % 4], zt])
        mid_out = np.array([outs[i][0] + outs[(i + 1) % 4][0], outs[i][1] + outs[(i + 1) % 4][1], 0.0]) * -0.03
        P = arch_curve(a, b, zt, 0.38, n_arc, bulge=mid_out)
        twisted_pair(g, P, 0.095, 1.5, 0.08, lod, "canopy_edge", seed=i)
        if lod < 2:
            P2 = arch_curve(a + (0, 0, -0.35), b + (0, 0, -0.35), zt - 0.35, 0.5, n_arc, bulge=mid_out * 0.5)
            g.tube(wobble(P2, 0.03, 40 + i), np.linspace(0.085, 0.07, n_arc), n=sides(lod), mat="root", tag="canopy_edge2")
    for i in range(4):
        a = np.array([*corners[i], zt])
        P = []
        for t in np.linspace(0, 1, n_arc):
            q = a + (crown - a) * t
            q[2] = zt + (zc - zt) * math.sin(t * math.pi / 2)
            P.append(q)
        twisted_pair(g, np.array(P), 0.09, 1.0, 0.07, lod, "canopy_diag", seed=10 + i)
    if lod < 2:
        # cross roots linking edge apexes over the top (dome lattice)
        apexes = []
        for i in range(4):
            a = np.array([*corners[i], 0.0])
            b = np.array([*corners[(i + 1) % 4], 0.0])
            m_ = (a + b) / 2
            m_[2] = zt + 0.36
            apexes.append(m_)
        for i in range(4):
            a, b = apexes[i], apexes[(i + 1) % 4]
            P = arch_curve(a, b, zt + 0.36, (zc - zt - 0.36) * 0.8, n_arc)
            g.tube(wobble(P, 0.04, 70 + i), np.linspace(0.085, 0.075, n_arc), n=sides(lod), mat="root", tag="canopy_cross")
    # ---------------- walls: lancet lattices
    zl0, zl1 = 0.12, zt - 0.05
    span_x, span_y = 2 * c - 2 * RT, 2 * cy - 2 * RT
    lancet_lattice(g, (-c, -cy + RT), (0, 1), span_y, zl0, zl1, 4, lod, "lattice_left", 1)
    lancet_lattice(g, (-c + RT, cy), (1, 0), span_x, zl0, zl1, 3, lod, "lattice_back", 2)
    lancet_lattice(g, (c, -cy + RT), (0, 1), span_y, zl0, zl1, 3, lod, "lattice_right", 3)
    fb = (hx - 0.11) - (-c + RT)
    if fb > 0.2:
        lancet_lattice(g, (-c + RT, -cy), (1, 0), fb, zl0, zl1, 1, lod, "lattice_front", 4)
    # ---------------- jamb post + lintel (timber), roots wrapping the lintel
    g.box((hx, -cy, (p["zda"] + 0.25) / 2), (0.2, 0.2, p["zda"] + 0.25), mat="wood", tag="jamb", skip=("-z",))
    g.box(((hx + c) / 2, -cy, p["zda"] + 0.17), (c - hx + 0.1, 0.18, 0.16), mat="wood", tag="lintel")
    if lod < 2:
        P = arch_curve((hx - 0.1, -cy - 0.12, p["zda"] + 0.05), (c, -cy - 0.12, zt - 0.05), p["zda"], 0.28, n_arc)
        g.tube(wobble(P, 0.02, 90), np.linspace(0.06, 0.045, n_arc), n=sides(lod), mat="root", tag="lintel_root")
    # ---------------- door, socket, latch
    cfg = door_cfg(p)
    piv = CC.add_door_and_sockets(A, cfg, lod, NATIVE)
    for zz in cfg["strap_z"]:
        g.box((hx + 0.02, -cy - 0.105, zz), (0.12, 0.012, 0.15), mat="bronze", tag="pintle")
    if lod == 0:
        CC.add_markers(A, cfg, piv)
    return A


def door_cfg(p):
    c, cy = p["c"], p["cy"]
    hx = p["hx"]
    return dict(hinge_x=hx + 0.10, y_face=-cy - 0.04, thick=0.08, x1=p["dx1"], z0=max(p["dz0"], 0.06),
                z_top_side=p["zda"] - 0.22, z_apex=p["zda"], stile_w=0.10, rail_h=0.14, bars=6, bar_r=0.03,
                rails_z=(p["dz0"] + 0.55, p["dz0"] + 1.45), socket_x=p["sx"], socket_z=p["sz"],
                strap_z=(p["dz0"] + 0.48, p["dz0"] + 1.52), strap_len=0.46, strap_w=0.10, latch_z=p["sz"] + 0.3,
                floor_z=0.10, captive_slots_xz=[(-0.72, 0.1), (0.05, -0.45), (0.74, 0.18)],
                exit=[(hx + 0.6, -cy + 0.5, 0.1), (hx + 0.6, -cy - 0.3, 0.08), (hx + 0.6, -cy - 1.4, 0.0),
                      (hx + 0.6, -cy - 2.6, 0.0)],
                wood_mat="wood", socket_mat="bronze", slats=True)


GATE = {"root": lambda c: (c @ np.array([0.299, 0.587, 0.114])) < 0.68,
        "wood": lambda c: (c @ np.array([0.299, 0.587, 0.114])) < 0.66}

SWATCHES = {
    "root": dict(sheet=SHEET, box=(1213, 262, 1237, 300), metres=0.3),
    "wood": dict(sheet=SHEET, box=(1292, 260, 1308, 300), metres=0.25),
    "stone": dict(sheet=SHEET, box=(1330, 412, 1380, 422), metres=0.4),
    "bronze": dict(sheet=SHEET, box=(1300, 840, 1330, 860), metres=0.06),
    "enamel": dict(sheet=SHEET, box=(1210, 175, 1222, 200), metres=0.1),
    "iron": dict(sheet=SHEET, box=(1300, 840, 1330, 860), metres=0.06),
}


def clips(A, B):
    CC.add_clips(A, B)


def meta(A, p):
    cfg = door_cfg(p)
    piv = np.array([cfg["hinge_x"], cfg["y_face"] - 0.035, 0.0])
    return CC.cage_meta(A, cfg, piv, NATIVE, {"cage_type": "root", "native_family": NATIVE})
