"""Hand props, weapons and small accessories (built in a local frame, placed by a 4x4).

Prop-local frame for hand-held items = the <Side>Prop bone rest frame: origin at the grip
centre, +Y along the grip axis (toward the thumb side of the fist), +Z ~ palm normal,
+X = Y x Z (~ finger direction).  Everything returns humans_geo.Piece objects.
"""
import math

import numpy as np

import humans_cloth as C
import humans_geo as G


def _xf(V, M):
    V = np.asarray(V, float)
    return V @ M[:3, :3].T + M[:3, 3]


def place(piece, M):
    piece.verts = _xf(piece.verts, M)
    return piece


def frame(origin, x, y):
    x = np.asarray(x, float)
    x = x / np.linalg.norm(x)
    y = np.asarray(y, float)
    y = y - np.dot(y, x) * x
    y = y / np.linalg.norm(y)
    z = np.cross(x, y)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = x, y, z, origin
    return M


def bone_frame(B, name, roll_up=(0, 0, 1)):
    """Approximate rest frame of a bone from (head, tail): Y along the bone, Z ~ roll_up."""
    h, t = B[name]
    y = (t - h) / np.linalg.norm(t - h)
    z = np.asarray(roll_up, float)
    z = z - np.dot(z, y) * y
    if np.linalg.norm(z) < 1e-6:
        z = np.array([0, -1.0, 0]) - np.dot([0, -1.0, 0], y) * y
    z /= np.linalg.norm(z)
    x = np.cross(y, z)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = x, y, z, h
    return M


def lathe_y(name, profile, cls, rule, sides=12, y0=0.0):
    """Revolve [(r, y)] around local +Y."""
    V, F, U = C.lathe([(r, y + y0) for r, y in profile], (0, 0, 0), (0, 1.0, 0), sides=sides, ref=(1.0, 0, 0))
    return G.Piece(name, V, F, U, cls, rule)


def box(name, c, size, cls, rule, bevel=0.3, rot=None, segs=1):
    V, F, U = C.rbox(c, size, rot=rot, bevel=bevel, segs=segs)
    return G.Piece(name, V, F, U, cls, rule)


def blade(name, y0, y1, w0, w1, t, cls, rule, tip=0.10, fuller=0.0, n=10):
    """Flat double-edged blade along +Y (width along X, thickness along Z), pointed tip."""
    ys = np.linspace(y0, y1, n)
    rows = []
    for y in ys:
        f = (y - y0) / (y1 - y0)
        w = w0 + (w1 - w0) * f
        if y > y1 - tip:
            w *= max(0.0, (y1 - y) / tip) ** 0.8
        th = t * (1.0 - 0.6 * f)
        rows.append([(-w, y, 0.0), (0.0, y, th), (w, y, 0.0), (0.0, y, -th)])
    V = np.array(rows).reshape(-1, 3)
    F, Uv = [], []
    for j in range(n - 1):
        for i in range(4):
            a, b = j * 4 + i, j * 4 + (i + 1) % 4
            F.append([a, b, b + 4, a + 4])
            Uv.append([(i / 4, ys[j]), ((i + 1) / 4, ys[j]), ((i + 1) / 4, ys[j + 1]), (i / 4, ys[j + 1])])
    return G.Piece(name, V, F, Uv, cls, rule)


# --------------------------------------------------------------------------- weapons

def sword(rule, blade_len=0.78):
    parts = [
        lathe_y("sword_grip", [(0.0, -0.065), (0.016, -0.062), (0.017, -0.055), (0.014, -0.050), (0.015, 0.0),
                               (0.014, 0.048), (0.0, 0.052)], "leather_dark", rule, sides=8),
        lathe_y("sword_pommel", [(0.0, -0.100), (0.016, -0.096), (0.024, -0.082), (0.016, -0.066), (0.0, -0.062)],
                "metal", rule, sides=10),
        box("sword_guard", (0.0, 0.060, 0.0), (0.20, 0.018, 0.026), "metal", rule, bevel=0.5),
        blade("sword_blade", 0.068, 0.068 + blade_len, 0.026, 0.020, 0.0045, "metal", rule, tip=0.12),
    ]
    return G.merge_pieces("sword", parts, cls="metal", rule=rule)


def scabbard(rule, length=0.80):
    V, F, U = C.lathe([(0.0, -0.01), (0.030, 0.0), (0.030, length * 0.5), (0.026, length * 0.95), (0.012, length),
                       (0.0, length + 0.005)], (0, 0, 0), (0, -1.0, 0), sides=10, ref=(1.0, 0, 0))
    V[:, 2] *= 0.45            # flat oval section
    sc = G.Piece("scabbard", V, F, U, "leather_dark", rule)
    chape = lathe_y("scabbard_chape", [(0.0, -length - 0.004), (0.020, -length + 0.02), (0.031, -length + 0.07),
                                       (0.0, -length + 0.071)], "metal", rule, sides=10)
    chape.verts[:, 2] *= 0.5
    throat = lathe_y("scabbard_throat", [(0.032, -0.03), (0.033, 0.0), (0.0, 0.001)], "metal", rule, sides=10)
    throat.verts[:, 2] *= 0.5
    return G.merge_pieces("scabbard_set", [sc, chape, throat], cls="leather_dark", rule=rule)


def spear(rule, below=1.05, above=0.95):
    shaft = lathe_y("spear_shaft", [(0.0, -below - 0.01), (0.015, -below), (0.017, 0.0), (0.016, above - 0.10),
                                    (0.0, above - 0.09)], "wood", rule, sides=8)
    socket = lathe_y("spear_socket", [(0.0, above - 0.20), (0.019, above - 0.19), (0.017, above - 0.10),
                                      (0.012, above - 0.06), (0.0, above - 0.05)], "metal", rule, sides=8)
    head = blade("spear_head", above - 0.07, above + 0.22, 0.032, 0.040, 0.007, "metal", rule, tip=0.17)
    butt = lathe_y("spear_butt", [(0.0, -below - 0.04), (0.012, -below - 0.035), (0.018, -below + 0.03),
                                  (0.0, -below + 0.035)], "metal", rule, sides=8)
    return G.merge_pieces("spear", [shaft, socket, head, butt], cls="wood", rule=rule)


def round_shield(rule, radius=0.39, thick=0.022, boss_r=0.085):
    """Disc in the local Y-Z plane facing +X (the knuckle direction); grip at the origin."""
    prof = [(0.0, thick * 0.5), (radius - 0.012, thick * 0.5), (radius, thick * 0.2), (radius, -thick * 0.3),
            (radius - 0.015, -thick * 0.5), (0.0, -thick * 0.5)]
    V, F, U = C.lathe(prof[::-1], (0.0, 0.0, 0.0), (1.0, 0, 0), sides=28, ref=(0, 1.0, 0))
    V[:, 0] += 0.075
    board = G.Piece("shield_board", V, F, U, "wood", rule)
    V, F, U = C.lathe([(0.0, thick * 0.5 + 0.055), (boss_r * 0.35, thick * 0.5 + 0.050),
                       (boss_r * 0.8, thick * 0.5 + 0.030), (boss_r, thick * 0.5 + 0.004), (boss_r * 1.12, thick * 0.5),
                       (boss_r * 1.12, thick * 0.5 - 0.002)][::-1], (0.0, 0.0, 0.0), (1.0, 0, 0), sides=16,
                      ref=(0, 1.0, 0))
    V[:, 0] += 0.075
    boss = G.Piece("shield_boss", V, F, U, "metal", rule)
    # iron rim band
    t = np.linspace(0, 2 * math.pi, 49)[:-1]
    ring = np.stack([np.full_like(t, 0.075), radius * np.cos(t), radius * np.sin(t)], -1)
    Vr, Fr, Ur = C.tube(np.vstack([ring, ring[:1]]), 0.007, sides=6, caps=False)
    rim = G.Piece("shield_rim", Vr, Fr, Ur, "metal", rule)
    # back grip bar
    grip = box("shield_grip", (0.045, 0.0, 0.0), (0.03, 0.16, 0.03), "wood", rule, bevel=0.6)
    return G.merge_pieces("shield", [board, boss, rim, grip], cls="wood", rule=rule)


def bow(rule, length=1.25, drawn=False):
    """Short self bow along local Y through the grip; string on -X side (toward the archer)."""
    n = 21
    ys = np.linspace(-length / 2, length / 2, n)
    bend = 0.055 if not drawn else 0.09
    xs = bend * (1 - (2 * ys / length) ** 2) - bend
    r = 0.016 - 0.010 * np.abs(2 * ys / length)
    pts = np.stack([xs, ys, np.zeros(n)], -1)
    V, F, U = C.tube(pts, r, sides=7)
    limb = G.Piece("bow_stave", V, F, U, "wood", rule)
    grip = lathe_y("bow_grip", [(0.0, -0.07), (0.019, -0.065), (0.020, 0.065), (0.0, 0.07)], "leather_dark", rule,
                   sides=8)
    sx = -bend - (0.12 if drawn else 0.0)
    s_pts = np.array([[xs[0], ys[0], 0], [sx, 0.0, 0], [xs[-1], ys[-1], 0]])
    Vs, Fs, Us = C.tube(s_pts, 0.0018, sides=4)
    string = G.Piece("bow_string", Vs, Fs, Us, "rope", rule)
    return G.merge_pieces("bow", [limb, grip, string], cls="wood", rule=rule)


def quiver(rule, length=0.46, r=0.055, n_arrows=7, seed=1):
    """Leather quiver along local -Y (opening at +Y=0) with fletched arrows sticking out."""
    V, F, U = C.lathe([(0.0, -length - 0.005), (r * 0.8, -length), (r, -length + 0.03), (r * 1.05, -0.05),
                       (r * 1.12, 0.0)], (0, 0, 0), (0, 1.0, 0), sides=12, ref=(1.0, 0, 0))
    V[:, 2] *= 0.75
    body = G.Piece("quiver_body", V, F, U, "leather", rule)
    rim = lathe_y("quiver_rim", [(r * 1.14, -0.018), (r * 1.18, -0.004), (r * 1.10, 0.004)], "leather_dark", rule,
                  sides=12)
    rim.verts[:, 2] *= 0.75
    rng = np.random.default_rng(seed)
    arrows = []
    for k in range(n_arrows):
        a = 2 * math.pi * k / n_arrows
        ox, oz = 0.55 * r * math.cos(a), 0.4 * r * math.sin(a)
        tilt = np.array([rng.uniform(-0.12, 0.12), 1.0, rng.uniform(-0.1, 0.1)])
        tilt /= np.linalg.norm(tilt)
        base = np.array([ox, -0.30, oz])
        top = base + tilt * (0.30 + rng.uniform(0.08, 0.14))
        Vs, Fs, Us = C.tube(np.array([base, top]), 0.004, sides=4)
        arrows.append(G.Piece(f"arrow{k}", Vs, Fs, Us, "wood", rule))
        for f in range(3):
            fa = a + f * 2 * math.pi / 3
            d = np.array([math.cos(fa), 0, math.sin(fa)]) * 0.012
            q = [top - tilt * 0.09, top - tilt * 0.01, top - tilt * 0.01 + d, top - tilt * 0.09 + d * 0.6]
            arrows.append(G.Piece(f"fletch{k}_{f}", np.array(q), [[0, 1, 2, 3], [3, 2, 1, 0]],
                                  [[(0, 0), (1, 0), (1, 1), (0, 1)]] * 2, "feather", rule))
    return G.merge_pieces("quiver", [body, rim] + arrows, cls="leather", rule=rule)


def dagger(rule):
    parts = [lathe_y("dagger_grip", [(0.0, -0.05), (0.012, -0.045), (0.013, 0.04), (0.0, 0.045)], "leather_dark", rule,
                     sides=7),
             box("dagger_guard", (0.0, 0.047, 0.0), (0.075, 0.012, 0.018), "metal", rule, bevel=0.5),
             blade("dagger_blade", 0.052, 0.25, 0.017, 0.013, 0.0035, "metal", rule, tip=0.06)]
    return G.merge_pieces("dagger", parts, cls="metal", rule=rule)


def sheath(rule, length=0.22):
    V, F, U = C.lathe([(0.0, -0.005), (0.022, 0.0), (0.020, length * 0.6), (0.010, length), (0.0, length + 0.004)],
                      (0, 0, 0), (0, -1.0, 0), sides=8, ref=(1.0, 0, 0))
    V[:, 2] *= 0.5
    return G.Piece("sheath", V, F, U, "leather_dark", rule)


def hammer(rule, handle=0.34):
    """Cooper's hammer: handle along local -Y from the hang point, head at the bottom."""
    h = lathe_y("hammer_handle", [(0.0, 0.0), (0.012, -0.004), (0.013, -handle * 0.6), (0.015, -handle),
                                  (0.0, -handle - 0.004)], "wood", rule, sides=8)
    head = box("hammer_head", (0.0, -handle - 0.02, 0.0), (0.11, 0.045, 0.045), "metal", rule, bevel=0.35)
    return G.merge_pieces("hammer", [h, head], cls="wood", rule=rule)


def buckle(name, c, x_axis, n_axis, w=0.05, h=0.04, cls="brass", rule=None):
    """Rectangular frame buckle (tube loop) on a belt: plane spanned by x_axis and belt-up."""
    x = np.asarray(x_axis, float) / np.linalg.norm(x_axis)
    n = np.asarray(n_axis, float) / np.linalg.norm(n_axis)
    up = np.cross(n, x)
    pts = [c + x * (-w / 2) + up * (-h / 2), c + x * (w / 2) + up * (-h / 2), c + x * (w / 2) + up * (h / 2),
           c + x * (-w / 2) + up * (h / 2), c + x * (-w / 2) + up * (-h / 2)]
    pts = np.array(pts) + n * 0.004
    V, F, U = C.tube(pts, 0.0035, sides=5, caps=False)
    prong = np.array([c + x * (-w / 2) + n * 0.004, c + x * (w * 0.15) + n * 0.008])
    V2, F2, U2 = C.tube(prong, 0.0025, sides=4)
    a = G.Piece(name + "_frame", V, F, U, cls, rule or {"type": "body"})
    b = G.Piece(name + "_prong", V2, F2, U2, cls, rule or {"type": "body"})
    return G.merge_pieces(name, [a, b], cls=cls, rule=rule or {"type": "body"})


def belt(name, fn, center_xy, z, width=0.040, thick=0.006, cls="leather", clearance=0.006, tilt=0.0, n=48,
         buckle_theta=0.0, buckle_cls="brass", rule=None):
    """Closed belt hugging the body at height z (tilt: z varies with cos(theta)), with buckle."""
    th = np.linspace(-math.pi, math.pi, n, endpoint=False)
    zz = z + tilt * np.cos(th)
    P, N = G.curve_on_body(fn, center_xy, th, zz, clearance=clearance)
    rule = rule or {"type": "body"}
    out = [G.band_piece(name, P, N, width, thick, cls, rule, closed=True, segs_w=2)]
    k = int(np.argmin(np.abs(th - buckle_theta)))
    tdir = P[(k + 1) % n] - P[k - 1]
    out.append(buckle(name + "_buckle", P[k] + N[k] * thick, tdir, N[k], w=width * 1.25, h=width * 1.05,
                      cls=buckle_cls, rule=rule))
    return out


def pouch(name, c, size, facing, cls="leather", rule=None, flap=True):
    """Belt pouch: rounded box + flap, facing = outward normal (horizontal)."""
    f = np.asarray(facing, float)
    f /= np.linalg.norm(f)
    x = np.cross([0, 0, 1.0], f)
    R = np.stack([x, f, [0, 0, 1.0]], 1)
    rule = rule or {"type": "rigid", "bone": "Hips"}
    out = [box(name, c, size, cls, rule, bevel=0.55, rot=R, segs=2)]
    if flap:
        fc = c + f * (size[1] / 2 + 0.002) + np.array([0, 0, size[2] * 0.22])
        out.append(box(name + "_flap", fc, (size[0] * 1.02, 0.008, size[2] * 0.58), cls, rule, bevel=0.5, rot=R))
    return G.merge_pieces(name, out, cls=cls, rule=rule)
