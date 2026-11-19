"""Separate detail meshes (numpy): interlocking ivory teeth, keratin claws, amber eyes, tongue.

Each part: dict(name, verts (N,3), faces (M,3|4 lists), uv (per-loop), bone, mat, region).
UVs map into the 512 px 'keratin' atlas (lf_boss_ancient_maw_keratin):
    teeth  u 0.00-0.50, v 0.30-1.00  (gum -> tip along v)
    claws  u 0.50-1.00, v 0.30-1.00  (base -> tip along v)
    eye    u 0.00-0.25, v 0.00-0.25  (iris disc + slit pupil, planar map along the eye axis)
    tongue u 0.50-1.00, v 0.00-0.25
"""
import math

import numpy as np

import mv2_body as B

ATLAS = {"teeth": (0.0, 0.30, 0.5, 1.0), "claws": (0.5, 0.30, 1.0, 1.0), "eye": (0.0, 0.0, 0.25, 0.25),
         "tongue": (0.5, 0.0, 1.0, 0.25)}


def _frame(d, hint):
    d = np.asarray(d, float)
    d = d / np.linalg.norm(d)
    h = np.asarray(hint, float)
    s = np.cross(d, h)
    if np.linalg.norm(s) < 1e-6:
        s = np.cross(d, [0.3, 0.1, 1.0])
    s /= np.linalg.norm(s)
    u = np.cross(s, d)
    return d, s, u


def curved_cone(base, direction, length, r0, bend_dir, bend=0.2, sides=8, rings=6, flat=0.6, region="teeth",
                bone="head", u_slot=(0.0, 1.0), embed=0.03, tip_r=0.003, keel=0.0):
    """Recurved conical tooth/claw; cross-section ellipse (flat = side/bend radius ratio).
    keel > 0 sharpens the inner (bend side) edge like a claw blade."""
    d, s, u = _frame(direction, bend_dir)
    bv = np.asarray(bend_dir, float)
    bv = bv - d * (bv @ d)
    if np.linalg.norm(bv) > 1e-6:
        bv /= np.linalg.norm(bv)
    base = np.asarray(base, float) - d * embed
    L = length + embed
    verts, vt = [], []
    for ri in range(rings):
        t = ri / rings
        c = base + d * (t * L) + bv * (bend * L * t * t)
        tang = d * L + bv * (2 * bend * L * t)
        tang /= np.linalg.norm(tang)
        _, s2, u2 = _frame(tang, bv)
        r = max(r0 * (1 - t) ** 0.8, tip_r)
        for k in range(sides):
            a = 2 * math.pi * k / sides
            ca, sa = math.cos(a), math.sin(a)
            rr = r * (1 + keel * max(0.0, ca) ** 3)
            verts.append(c + u2 * ca * rr + s2 * sa * r * flat)
            vt.append((k / sides, t))
    tip = base + d * L + bv * (bend * L)
    verts.append(tip)
    vt.append((0.5, 1.0))
    verts.append(base - d * 0.003)
    vt.append((0.5, 0.0))
    faces = []
    for ri in range(rings - 1):
        for k in range(sides):
            a = ri * sides + k
            b = ri * sides + (k + 1) % sides
            faces.append([a, b, b + sides, a + sides])
    ti = len(verts) - 2
    for k in range(sides):
        a = (rings - 1) * sides + k
        b = (rings - 1) * sides + (k + 1) % sides
        faces.append([a, b, ti])
    bi = len(verts) - 1
    for k in range(sides):
        faces.append([(k + 1) % sides, k, bi])
    x0, y0, x1, y1 = ATLAS[region]
    ua, ub = u_slot
    uvs = []
    for f in faces:
        for i in f:
            uu, tt = vt[i]
            uvs.append((x0 + (x1 - x0) * (ua + (ub - ua) * uu), y0 + (y1 - y0) * tt))
    return {"verts": np.array(verts), "faces": faces, "uv": np.array(uvs), "bone": bone, "region": region}


def teeth():
    """Upper teeth hang outside the lower jaw rim, lower teeth stand inside the upper row, interleaved."""
    out = []
    n_up, n_lo = 13, 12
    hp = B.head_profile()
    for sx in (1, -1):
        ys_u = np.linspace(-4.50, -3.52, n_up)
        for i, y in enumerate(ys_u):
            wu, _wl = B.head_widths(y)
            zl = float(B.lip_z(y))
            t = i / (n_up - 1)
            ln = 0.075 + 0.075 * math.sin(math.pi * min(1.0, t * 1.25)) ** 0.8 - 0.02 * t
            if i in (2, 5):
                ln *= 1.15
            r0 = 0.020 + 0.010 * math.sin(math.pi * min(1.0, t * 1.2))
            x = sx * (float(wu) - 0.035 - 0.01 * (1 - t))
            if i == 0:
                x = sx * 0.07
            base = np.array([x, y, zl + 0.012])
            dirv = np.array([sx * 0.05, -0.12 + 0.18 * t, -1.0])
            out.append(curved_cone(base, dirv, ln, r0, bend_dir=(0, 1, 0), bend=0.18, sides=6, rings=4, flat=0.62,
                                   region="teeth", bone="head", u_slot=(0.0, 0.5), embed=0.035))
        ys_l = np.linspace(-4.44, -3.60, n_lo)
        for i, y in enumerate(ys_l):
            wu, wl = B.head_widths(y)
            zl = float(B.lip_z(y))
            t = i / (n_lo - 1)
            ln = 0.06 + 0.065 * math.sin(math.pi * min(1.0, t * 1.2)) ** 0.8 - 0.02 * t
            r0 = 0.018 + 0.009 * math.sin(math.pi * min(1.0, t * 1.2))
            x = sx * (float(wl) - 0.060 - 0.008 * (1 - t))
            if i == 0:
                x = sx * 0.06
            base = np.array([x, y + 0.03, zl - 0.012])
            dirv = np.array([-sx * 0.04, -0.10 + 0.15 * t, 1.0])
            out.append(curved_cone(base, dirv, ln, r0, bend_dir=(0, 1, 0), bend=0.16, sides=6, rings=4, flat=0.62,
                                   region="teeth", bone="jaw", u_slot=(0.5, 1.0), embed=0.035))
    return out


def claws():
    out = []
    for side in "LR":
        sx = 1 if side == "L" else -1
        m = (lambda p: np.array(p, float) * np.array([sx, 1, 1]))
        # foot claws (toes II-IV): big, recurved, pointing forward-down
        for toe, chain in B.TOES_L.items():
            pts = [m(p) for p in chain]
            dirv = pts[2] - pts[1]
            dirv = dirv / np.linalg.norm(dirv) + np.array([0, 0, -0.35])
            ln = {"toe2": 0.24, "toe3": 0.27, "toe4": 0.23}[toe]
            out.append(curved_cone(pts[2] + dirv * 0.01, dirv, ln, 0.068, bend_dir=(0, 0, -1), bend=0.45, sides=8,
                                   rings=7, flat=0.62, region="claws", bone=f"{toe}b_{side}", embed=0.05, keel=0.25))
        hx = [m(p) for p in B.HALLUX_L]
        d = hx[1] - hx[0]
        out.append(curved_cone(hx[1], d / np.linalg.norm(d) + np.array([0, 0.2, -0.5]), 0.10, 0.032,
                               bend_dir=(0, -0.3, -1), bend=0.4, sides=7, rings=5, flat=0.6, region="claws",
                               bone=f"hallux_{side}", embed=0.03, keel=0.2))
        # hand claws: long hooked, hanging down
        for f, chain in B.FINGERS_L.items():
            pts = [m(p) for p in chain]
            dirv = pts[2] - pts[1]
            dirv = dirv / np.linalg.norm(dirv)
            ln = 0.13 if f != "finger3" else 0.08
            out.append(curved_cone(pts[2], dirv, ln, 0.028 if f != "finger3" else 0.022, bend_dir=(0, 0.6, -0.4),
                                   bend=0.55, sides=7, rings=6, flat=0.6, region="claws", bone=f"{f}b_{side}",
                                   embed=0.025, keel=0.2))
    return out


def eye_centre(sx):
    return np.array([sx * 0.360, -3.63, 3.285])


def eye_axis(sx):
    a = np.array([sx * 0.80, -0.55, 0.22])
    return a / np.linalg.norm(a)


EYE_R = 0.045


def eyes(n_lat=10, n_lon=16):
    out = []
    for sx, side in ((1, "L"), (-1, "R")):
        c = eye_centre(sx)
        ax, s, u = _frame(eye_axis(sx), (0, 0, 1))
        verts, faces = [], []
        for i in range(n_lat + 1):
            th = math.pi * i / n_lat
            for j in range(n_lon):
                ph = 2 * math.pi * j / n_lon
                p = c + EYE_R * (ax * math.cos(th) + (s * math.cos(ph) + u * math.sin(ph)) * math.sin(th))
                verts.append(p)
        for i in range(n_lat):
            for j in range(n_lon):
                a = i * n_lon + j
                b = i * n_lon + (j + 1) % n_lon
                faces.append([a, b, b + n_lon, a + n_lon])
        x0, y0, x1, y1 = ATLAS["eye"]
        uvs = []
        V_ = np.array(verts)
        for f in faces:
            for k in f:
                q = V_[k] - c
                pu, pv = (q @ s) / EYE_R, (q @ u) / EYE_R
                uvs.append((x0 + (x1 - x0) * (0.5 + 0.5 * pu), y0 + (y1 - y0) * (0.5 + 0.5 * pv)))
        out.append({"verts": V_, "faces": faces, "uv": np.array(uvs), "bone": f"eye_{side}", "region": "eye"})
    return out


def tongue():
    """Flattened tapered tongue lying in the mouth floor (3 bones)."""
    ys = np.linspace(-3.42, -4.22, 9)
    verts, faces, uvs_v = [], [], []
    ring = 10
    for i, y in enumerate(ys):
        t = i / (len(ys) - 1)
        zl = float(B.lip_z(y))
        z = zl - 0.085 + 0.02 * t
        w = 0.17 * (1 - 0.55 * t ** 1.5) + 0.01
        h = 0.045 * (1 - 0.4 * t)
        for k in range(ring):
            a = 2 * math.pi * k / ring
            verts.append([w * math.cos(a), y, z + h * math.sin(a) * (0.6 if math.sin(a) < 0 else 1.0)])
            uvs_v.append((k / ring, t))
    tip = [0.0, ys[-1] - 0.04, float(B.lip_z(ys[-1])) - 0.065]
    verts.append(tip)
    uvs_v.append((0.5, 1.0))
    for i in range(len(ys) - 1):
        for k in range(ring):
            a = i * ring + k
            b = i * ring + (k + 1) % ring
            faces.append([a, b, b + ring, a + ring])
    ti = len(verts) - 1
    for k in range(ring):
        a = (len(ys) - 1) * ring + k
        b = (len(ys) - 1) * ring + (k + 1) % ring
        faces.append([a, b, ti])
    x0, y0, x1, y1 = ATLAS["tongue"]
    uvs = []
    for f in faces:
        for k in f:
            uu, tt = uvs_v[k]
            uvs.append((x0 + (x1 - x0) * uu, y0 + (y1 - y0) * tt))
    return [{"verts": np.array(verts), "faces": faces, "uv": np.array(uvs), "bone": "tongue", "region": "tongue"}]


def mouth_curtain():
    """Inward-facing mouth lining (gum line -> gum line, + throat wall). One-sided: from outside you see the
    far side's lining through the open gape (never the background); skinned head (top) / jaw (bottom)."""
    x0, y0, x1, y1 = (0.25, 0.0, 0.5, 0.25)
    verts, faces, uvs, wjaw = [], [], [], []
    ys = np.linspace(-4.30, -3.36, 13)
    rows = 4
    for sx in (1, -1):
        base = len(verts)
        for i, y in enumerate(ys):
            wu, wl = B.head_widths(y)
            zl = float(B.lip_z(y))
            for r in range(rows):
                t = r / (rows - 1)                       # 0 upper gum -> 1 lower gum
                x = sx * ((1 - t) * (float(wu) - 0.10) + t * (float(wl) - 0.10) - 0.012 * math.sin(math.pi * t))
                z = zl + 0.006 - 0.012 * t
                verts.append([x, y, z])
                wjaw.append(t)
        for i in range(len(ys) - 1):
            for r in range(rows - 1):
                a = base + i * rows + r
                b = a + rows
                q = [a, b, b + 1, a + 1] if sx > 0 else [a, a + 1, b + 1, b]
                faces.append(q)
    # throat wall at the back of the gape
    base = len(verts)
    yb = -3.37
    zl = float(B.lip_z(yb))
    wu, wl = B.head_widths(yb)
    cols = 6
    for r in range(rows):
        t = r / (rows - 1)
        for c in range(cols):
            x = (c / (cols - 1) * 2 - 1) * (float(wu) - 0.09)
            verts.append([x, yb, zl + 0.006 - 0.012 * t])
            wjaw.append(t)
    for r in range(rows - 1):
        for c in range(cols - 1):
            a = base + r * cols + c
            faces.append([a, a + cols, a + cols + 1, a + 1])
    V = np.array(verts)
    for f in faces:
        for k in f:
            uvs.append((x0 + (x1 - x0) * (0.2 + 0.6 * ((V[k, 1] + 4.4) / 1.05)), y0 + (y1 - y0) * (0.2 + 0.6 * wjaw[k])))
    return [{"verts": V, "faces": faces, "uv": np.array(uvs), "bone": "head", "region": "mouth",
             "wjaw": np.array(wjaw)}]


def all_parts():
    return {"teeth": teeth(), "claws": claws(), "eyes": eyes(), "tongue": tongue(), "mouth": mouth_curtain()}
