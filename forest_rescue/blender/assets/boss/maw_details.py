"""Separate detail meshes for the Ancient Maw: teeth, claws, eyes, tongue (numpy, deterministic).

Every part returns a dict(verts (N,3), faces (list of index lists), uv (per-loop list), bone (str),
region (str)).  UVs map into the 'keratin' atlas (512 px):
    teeth  u 0.00-0.50, v 0.25-1.00   (base -> tip gradient along v)
    claws  u 0.50-1.00, v 0.25-1.00
    eye    u 0.00-0.25, v 0.00-0.25   (iris disc, slit pupil)
    tongue u 0.50-1.00, v 0.00-0.25
"""
import math

import numpy as np

import maw_body as B

ATLAS = {"teeth": (0.0, 0.25, 0.5, 1.0), "claws": (0.5, 0.25, 1.0, 1.0), "eye": (0.0, 0.0, 0.25, 0.25),
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


def curved_cone(base, direction, length, r0, bend_dir, bend=0.25, sides=6, rings=4, flat=0.65,
                region="teeth", bone="head", u_slot=(0.0, 1.0), embed=0.03, tip_r=0.004):
    """Recurved conical tooth/claw. bend_dir: direction the tip curves toward (unit-ish).

    Cross-section ellipse (flat = width/height ratio across the 'side' axis)."""
    d, s, u = _frame(direction, bend_dir)
    bend_v = np.asarray(bend_dir, float)
    bend_v = bend_v - d * (bend_v @ d)
    if np.linalg.norm(bend_v) > 1e-6:
        bend_v /= np.linalg.norm(bend_v)
    base = np.asarray(base, float) - d * embed
    L = length + embed
    verts, uvs_v = [], []
    ts = np.linspace(0, 1, rings + 1)[:-1]
    centers = []
    for t in ts:
        c = base + d * (t * L) + bend_v * (bend * L * t * t)
        tang = d * L + bend_v * (2 * bend * L * t)
        tang /= np.linalg.norm(tang)
        _, s2, u2 = _frame(tang, u)
        r = max(r0 * (1 - t) ** 0.85, tip_r)
        centers.append((c, s2, u2, r, t))
    tip = base + d * L + bend_v * (bend * L)
    for c, s2, u2, r, t in centers:
        for k in range(sides):
            a = 2 * math.pi * k / sides
            verts.append(c + s2 * math.cos(a) * r * flat + u2 * math.sin(a) * r)
    verts.append(tip)
    verts.append(base - d * 0.002)  # base cap centre
    nv = len(verts)
    tip_i, cap_i = nv - 2, nv - 1
    faces, uv = [], []
    x0, y0, x1, y1 = ATLAS[region]
    ua, ub = u_slot

    def U(k, t):
        return (x0 + (x1 - x0) * (ua + (ub - ua) * (k / sides)), y0 + (y1 - y0) * min(t, 1.0))

    for ri in range(rings - 1):
        for k in range(sides):
            a = ri * sides + k
            b = ri * sides + (k + 1) % sides
            c_ = (ri + 1) * sides + (k + 1) % sides
            d_ = (ri + 1) * sides + k
            faces.append([a, b, c_, d_])
            tA, tB = ts[ri], ts[ri + 1]
            uv += [U(k, tA), U(k + 1, tA), U(k + 1, tB), U(k, tB)]
    last = (rings - 1) * sides
    for k in range(sides):
        a = last + k
        b = last + (k + 1) % sides
        faces.append([a, b, tip_i])
        uv += [U(k, ts[-1]), U(k + 1, ts[-1]), U(k + 0.5, 1.0)]
    for k in range(sides):
        a = k
        b = (k + 1) % sides
        faces.append([b, a, cap_i])
        uv += [U(k + 1, 0.0), U(k, 0.0), U(k + 0.5, 0.0)]
    return {"verts": np.array(verts), "faces": faces, "uv": uv, "bone": bone, "region": region}


def teeth():
    out = []
    g = 0.018  # half gap of the mouth slit (see maw_body.mouth_cavity)
    rng = np.random.default_rng(3)
    # upper row (head bone): premaxillary (4) + maxillary (9) per side
    ys_up = np.concatenate([[-4.475, -4.455, -4.425, -4.39], np.linspace(-4.31, -3.55, 9)])
    for sx in (1, -1):
        for i, y in enumerate(ys_up):
            wu, wl = B.lip_outline(y)
            zm = float(B.mouth_z(y))
            front = y < -4.36
            x = sx * (float(wu) - (0.04 if not front else 0.035))
            L = (0.085 + 0.02 * rng.random()) if front else float(np.interp(y, [-4.3, -4.0, -3.75, -3.55],
                                                                              [0.12, 0.145, 0.12, 0.08]))
            L *= 0.92 + 0.16 * rng.random()
            r0 = 0.032 if front else float(np.interp(y, [-4.3, -3.95, -3.55], [0.038, 0.042, 0.03]))
            base = np.array([x, y, zm + g + 0.004])
            direction = np.array([sx * (0.12 if front else 0.08), -0.10 if front else 0.04, -1.0])
            out.append(curved_cone(base, direction, L, r0, bend_dir=[0, 1, 0], bend=0.16, sides=7, rings=4,
                                   flat=0.72, region="teeth", bone="head",
                                   u_slot=(0.0, 0.5) if sx > 0 else (0.5, 1.0)))
    # lower row (jaw bone): interleaved, slightly inside the upper row
    ys_lo = np.concatenate([[-4.445, -4.41], np.linspace(-4.34, -3.62, 9)])
    for sx in (1, -1):
        for i, y in enumerate(ys_lo):
            wu, wl = B.lip_outline(y)
            zm = float(B.mouth_z(y))
            x = sx * (float(wl) - 0.035)
            L = float(np.interp(y, [-4.45, -4.1, -3.8, -3.62], [0.08, 0.11, 0.095, 0.065])) * (0.9 + 0.2 * rng.random())
            r0 = float(np.interp(y, [-4.45, -4.0, -3.62], [0.03, 0.035, 0.026]))
            base = np.array([x, y, zm - g - 0.004])
            direction = np.array([sx * 0.08, -0.08, 1.0])
            out.append(curved_cone(base, direction, L, r0, bend_dir=[0, 1, 0], bend=0.15, sides=6, rings=4,
                                   flat=0.62, region="teeth", bone="jaw",
                                   u_slot=(0.0, 0.5) if sx > 0 else (0.5, 1.0)))
    return out


def claws():
    out = []
    for side in "LR":
        sx = 1 if side == "L" else -1
        lp = B.leg_points(side)
        for t, (L, r0) in {"toe2": (0.21, 0.075), "toe3": (0.25, 0.085), "toe4": (0.20, 0.072)}.items():
            b0, b1 = lp[f"{t}b_{side}"]
            dvec = (b1 - b0) / np.linalg.norm(b1 - b0)
            dvec = dvec + np.array([0, 0, -0.18])
            base = b1 - (b1 - b0) * 0.15 + np.array([0, 0, 0.012])
            out.append(curved_cone(base, dvec, L, r0, bend_dir=[0, 0, -1], bend=0.38, sides=8, rings=5,
                                   flat=0.72, region="claws", bone=f"{t}b_{side}", embed=0.06, tip_r=0.006))
        d0, d1 = lp[f"dewclaw_{side}"]
        dvec = (d1 - d0) / np.linalg.norm(d1 - d0)
        out.append(curved_cone(d1 - (d1 - d0) * 0.2, dvec + np.array([0, 0, -0.4]), 0.14, 0.045,
                               bend_dir=[0, -0.3, -1], bend=0.35, sides=7, rings=4, flat=0.72, region="claws",
                               bone=f"dewclaw_{side}", embed=0.04))
        ap = B.arm_points(side)
        for f, (L, r0) in {"finger1": (0.22, 0.045), "finger2": (0.24, 0.05)}.items():
            b0, b1 = ap[f"{f}b_{side}"]
            dvec = (b1 - b0) / np.linalg.norm(b1 - b0)
            out.append(curved_cone(b1 - (b1 - b0) * 0.25, dvec + np.array([0, -0.25, 0]), L, r0,
                                   bend_dir=[0, 0.7, -0.3], bend=0.45, sides=7, rings=5, flat=0.65,
                                   region="claws", bone=f"{f}b_{side}", embed=0.03))
        f0, f1 = ap[f"finger3_{side}"]
        dvec = (f1 - f0) / np.linalg.norm(f1 - f0)
        out.append(curved_cone(f1, dvec + np.array([0, -0.2, -0.4]), 0.07, 0.022, bend_dir=[0, 0.5, -0.5],
                               bend=0.35, sides=6, rings=3, flat=0.7, region="claws", bone=f"finger3_{side}",
                               embed=0.02))
    return out


EYE_R = 0.056


def eye_centre(sx):
    return np.array([sx * 0.288, -3.62, 3.27])


def eye_axis(sx):
    a = np.array([sx * 0.80, -0.56, 0.12])
    return a / np.linalg.norm(a)


def eyes():
    out = []
    for sx in (1, -1):
        c = eye_centre(sx)
        ax = eye_axis(sx)
        d, s, u = _frame(ax, [0, 0, 1])
        nlat, nlon = 9, 14
        verts, faces, uv = [], [], []
        x0, y0, x1, y1 = ATLAS["eye"]
        for i in range(nlat + 1):
            th = math.pi * i / nlat
            for j in range(nlon):
                ph = 2 * math.pi * j / nlon
                p = d * math.cos(th) + (s * math.cos(ph) + u * math.sin(ph)) * math.sin(th)
                verts.append(c + p * EYE_R)
        for i in range(nlat):
            for j in range(nlon):
                a = i * nlon + j
                b = i * nlon + (j + 1) % nlon
                c2 = (i + 1) * nlon + (j + 1) % nlon
                d2 = (i + 1) * nlon + j
                faces.append([a, b, c2, d2])
                quad_uv = []
                for vi in (a, b, c2, d2):
                    p = (verts[vi] - c) / EYE_R
                    # planar projection along the eye axis: front hemisphere -> iris disc
                    pu, pv = p @ s, p @ u
                    quad_uv.append((x0 + (x1 - x0) * (0.5 + 0.5 * pu * sx), y0 + (y1 - y0) * (0.5 + 0.5 * pv)))
                uv += quad_uv
        out.append({"verts": np.array(verts), "faces": faces, "uv": uv, "bone": "head", "region": "eye"})
    return out


def tongue():
    """Flattened tapering tongue lying in the mandible trough (bones tongue_01..03)."""
    sp = B.spine_points()
    pts = [sp["tongue_01"][0], sp["tongue_02"][0], sp["tongue_03"][0], sp["tongue_03"][1]]
    pts = [np.asarray(p, float) for p in pts]
    # tongue top just under the lip line, follow the mouth line height
    ys = np.linspace(pts[0][1], pts[-1][1] - 0.06, 16)
    width = np.interp(ys, [ys[0], ys[0] - 0.4, ys[-1] + 0.15, ys[-1]], [0.15, 0.16, 0.10, 0.03])
    thick = np.interp(ys, [ys[0], ys[-1]], [0.07, 0.03])
    nring = 12
    verts, faces, uv = [], [], []
    x0, y0, x1, y1 = ATLAS["tongue"]
    bones = []
    for i, y in enumerate(ys):
        zt = float(B.mouth_z(y)) - 0.018 - 0.012
        for k in range(nring):
            a = 2 * math.pi * k / nring
            cx = math.cos(a)
            sz = math.sin(a)
            groove = -0.012 * math.exp(-(cx / 0.25) ** 2) if sz > 0 else 0.0
            x = width[i] * cx
            z = zt - thick[i] * 0.5 + thick[i] * 0.5 * sz + groove
            verts.append([x, y, z])
        bones.append(i)
    n = len(ys)
    for i in range(n - 1):
        for k in range(nring):
            a = i * nring + k
            b = i * nring + (k + 1) % nring
            c = (i + 1) * nring + (k + 1) % nring
            d = (i + 1) * nring + k
            faces.append([a, d, c, b])
            for vi in (a, d, c, b):
                vx, vy, vz = verts[vi]
                uv.append((x0 + (x1 - x0) * (0.5 + vx / 0.4), y0 + (y1 - y0) * ((vy - ys[0]) / (ys[-1] - ys[0]))))
    # tip cap
    tip = np.array([0.0, ys[-1] - 0.05, float(B.mouth_z(ys[-1])) - 0.04])
    verts.append(tip)
    ti = len(verts) - 1
    base = (n - 1) * nring
    for k in range(nring):
        faces.append([base + k, base + (k + 1) % nring, ti])
        for vi in (base + k, base + (k + 1) % nring, ti):
            vx, vy, vz = verts[vi]
            uv.append((x0 + (x1 - x0) * (0.5 + vx / 0.4), y1))
    # root cap
    root = np.array([0.0, ys[0] + 0.03, float(B.mouth_z(ys[0])) - 0.05])
    verts.append(root)
    ri = len(verts) - 1
    for k in range(nring):
        faces.append([(k + 1) % nring, k, ri])
        uv += [(x0, y0), (x0, y0), (x0, y0)]
    return {"verts": np.array(verts, float), "faces": faces, "uv": uv, "bone": "tongue", "region": "tongue"}


def all_parts():
    return {"teeth": teeth(), "claws": claws(), "eyes": eyes(), "tongue": [tongue()]}
