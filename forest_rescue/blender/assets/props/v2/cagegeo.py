"""Shared cage / prop geometry helpers (numpy, Blender axes Z up, metres; outward winding)."""
import math

import numpy as np

import geo as G


def unit(v):
    v = np.asarray(v, float)
    return v / max(np.linalg.norm(v), 1e-12)


def frame(ex, ez=(0, 0, 1)):
    """Rotation with local X = ex, local Z ~ ez (Y = Z x X)."""
    x = unit(ex)
    z = np.asarray(ez, float)
    z = unit(z - x * (z @ x))
    y = np.cross(z, x)
    return np.stack([x, y, z], 1)


def pointed_arch(s0, s1, z_s, h, n=7):
    """Gothic (two-centred) arch over [s0, s1] springing at z_s with rise h -> (left pts, right pts) in (s, z)."""
    w = s1 - s0
    r = (w * w / 4 + h * h) / w
    phim = math.asin(min(1.0, h / r)) if r > 0 else math.pi / 2
    L, R = [], []
    for t in np.linspace(0, 1, n):
        phi = t * phim
        L.append((s0 + r - r * math.cos(phi), z_s + r * math.sin(phi)))
        R.append((s1 - r + r * math.cos(phi), z_s + r * math.sin(phi)))
    return np.array(L), np.array(R)


def sweep_rect(g, P, w, h, up=(0, 0, 1), mat="iron", tag="", caps=True):
    """Rectangular section (w across, h along `up`-ish) swept along polyline P."""
    P = np.asarray(P, float)
    m = len(P)
    prof = np.array([(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)])
    V = []
    prev = None
    for i in range(m):
        t = unit(P[min(i + 1, m - 1)] - P[max(i - 1, 0)])
        R = G.frame_from(t, up)
        if prev is not None and np.dot(R[:, 1], prev) < 0:
            R[:, 1] *= -1
            R[:, 2] *= -1
        prev = R[:, 1]
        for a, b in prof:
            V.append(P[i] + a * R[:, 1] + b * R[:, 2])
    V = np.array(V)
    F = []
    for i in range(m - 1):
        for k in range(4):
            k2 = (k + 1) % 4
            F.append([i * 4 + k, i * 4 + k2, (i + 1) * 4 + k2, (i + 1) * 4 + k])
    # winding check against the local centre line
    F2 = []
    for f in F:
        p = V[f]
        nrm = np.cross(p[1] - p[0], p[3] - p[0])
        c_line = (P[f[0] // 4] + P[f[2] // 4]) / 2
        if nrm @ (p.mean(0) - c_line) < 0:
            f = f[::-1]
        F2.append(f)
    if caps:
        c0 = [3, 2, 1, 0]
        c1 = [(m - 1) * 4 + k for k in range(4)]
        for cap, end, nxt in ((c0, 0, 1), (c1, m - 1, m - 2)):
            p = V[cap]
            nrm = np.cross(p[1] - p[0], p[2] - p[0])
            if nrm @ (P[end] - P[nxt]) < 0:
                cap = cap[::-1]
            F2.append(cap)
    return g.add(V, F2, mat, tag)


def pyramid(g, c, w, h, mat="wood", tag="finial", base_h=0.0, R=None):
    """Square pyramid (optional plinth slab) standing on c."""
    c = np.asarray(c, float)
    if base_h > 0:
        g.box(c + (0, 0, base_h / 2), (w, w, base_h), R=R, mat=mat, tag=tag)
        c = c + (0, 0, base_h)
    hw = w / 2
    Rm = np.eye(3) if R is None else np.asarray(R)
    V = np.array([[-hw, -hw, 0], [hw, -hw, 0], [hw, hw, 0], [-hw, hw, 0], [0, 0, h]]) @ Rm.T + c
    F = [[0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4], [3, 2, 1, 0]]
    return g.add(V, F, mat, tag)


def lathe(g, prof, c, n=10, mat="iron", tag="", R=None, cap_top=True, cap_bot=True):
    """Surface of revolution about local Z: prof = [(r, z)] bottom->top."""
    prof = np.asarray(prof, float)
    m = len(prof)
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    V = []
    for r, z in prof:
        for k in range(n):
            V.append((r * math.cos(a[k]), r * math.sin(a[k]), z))
    V = np.array(V)
    Rm = np.eye(3) if R is None else np.asarray(R)
    V = V @ Rm.T + np.asarray(c, float)
    F = []
    for i in range(m - 1):
        for k in range(n):
            k2 = (k + 1) % n
            F.append([i * n + k, i * n + k2, (i + 1) * n + k2, (i + 1) * n + k])
    if cap_bot and prof[0, 0] > 1e-6:
        F.append(list(range(n))[::-1])
    if cap_top and prof[-1, 0] > 1e-6:
        F.append([(m - 1) * n + k for k in range(n)])
    return g.add(V, F, mat, tag)


def disc_prism(g, c, R, poly, z0, z1, mat, tag, caps=(True, True)):
    """Polygon (local XY, CCW) extruded along local Z from z0 to z1, placed by rotation R at c."""
    return g.prism(np.asarray(poly, float), z0, z1, mat, tag, R=R, t=c, caps=caps)


def ngon(r, n, a0=0.0):
    a = a0 + np.linspace(0, 2 * math.pi, n, endpoint=False)
    return np.stack([r * np.cos(a), r * np.sin(a)], 1)


def ring_prism(g, c, R, r_out, r_in, n, z0, z1, mat, tag, a0=0.0):
    """Annulus (polygonal) extruded along local Z."""
    a = a0 + np.linspace(0, 2 * math.pi, n, endpoint=False)
    O = np.stack([r_out * np.cos(a), r_out * np.sin(a)], 1)
    I = np.stack([r_in * np.cos(a), r_in * np.sin(a)], 1)
    V = []
    for z in (z0, z1):
        for p in O:
            V.append((p[0], p[1], z))
        for p in I:
            V.append((p[0], p[1], z))
    V = np.array(V) @ np.asarray(R).T + np.asarray(c, float)
    F = []
    o0, i0, o1, i1 = 0, n, 2 * n, 3 * n
    for k in range(n):
        k2 = (k + 1) % n
        F.append([o0 + k, o0 + k2, o1 + k2, o1 + k])          # outer wall
        F.append([i0 + k2, i0 + k, i1 + k, i1 + k2])          # inner wall
        F.append([o1 + k, o1 + k2, i1 + k2, i1 + k])          # top
        F.append([o0 + k2, o0 + k, i0 + k, i0 + k2])          # bottom
    return g.add(V, F, mat, tag)


def outline_ring(g, c, R, outer, inner, z0, z1, mat, tag):
    """Frame between two polygons with the same vertex count (outer, inner CCW, local XY), extruded on Z."""
    outer = np.asarray(outer, float)
    inner = np.asarray(inner, float)
    n = len(outer)
    V = []
    for z in (z0, z1):
        for p in outer:
            V.append((p[0], p[1], z))
        for p in inner:
            V.append((p[0], p[1], z))
    V = np.array(V) @ np.asarray(R).T + np.asarray(c, float)
    F = []
    o0, i0, o1, i1 = 0, n, 2 * n, 3 * n
    for k in range(n):
        k2 = (k + 1) % n
        F.append([o0 + k, o0 + k2, o1 + k2, o1 + k])
        F.append([i0 + k2, i0 + k, i1 + k, i1 + k2])
        F.append([o1 + k, o1 + k2, i1 + k2, i1 + k])
        F.append([o0 + k2, o0 + k, i0 + k, i0 + k2])
    return g.add(V, F, mat, tag)


def masonry_run(g, p0, p1, z0, z1, thick, courses, block_len, rng, mat="stone", tag="base", out_dir=None,
                chamfer=0.025, skip=("-z",), lod=0, end_pad=0.0):
    """Wall of stone blocks along the segment p0->p1 (XY), from z0 to z1, `courses` rows, running bond."""
    p0 = np.asarray(p0, float)[:2]
    p1 = np.asarray(p1, float)[:2]
    d = p1 - p0
    L = float(np.linalg.norm(d))
    ex = np.array([d[0], d[1], 0.0]) / max(L, 1e-9)
    R = frame(ex)
    ch = (z1 - z0) / courses
    for ci in range(courses):
        zc = z0 + ch * (ci + 0.5)
        n = max(1, int(round(L / block_len)))
        if ci % 2 == 1 and n > 1:
            cuts = np.concatenate([[0.0], (np.arange(n) + 0.5) * L / n, [L]])
        else:
            cuts = np.linspace(0, L, n + 1)
        for a, b in zip(cuts[:-1], cuts[1:]):
            if b - a < 0.05:
                continue
            gap = 0.012 if lod == 0 else 0.0
            jl = rng.uniform(-0.01, 0.01) if lod == 0 else 0.0
            cen = np.array([p0[0], p0[1], 0.0]) + ex * ((a + b) / 2) + np.array([0, 0, zc])
            sz = (b - a - gap, thick + jl, ch - gap)
            if lod == 0:
                g.rounded_block(cen, sz, chamfer, R=R, mat=mat, tag=tag, skip=skip)
            else:
                g.box(cen, sz, R=R, mat=mat, tag=tag, skip=skip)
    return g


def hip_roof(g, z0, half, apex, rows, lod, mat="roof", tag="roof", step=0.035, apex_xy=(0.0, 0.0)):
    """Hip (pyramid) roof from the eave rectangle (+-hx, +-hy) at z0 to the apex point, shingle rows as stepped
    slabs. half = scalar or (hx, hy)."""
    hx, hy = (half, half) if np.isscalar(half) else half
    sides = [((-hx, -hy), (hx, -hy)), ((hx, -hy), (hx, hy)), ((hx, hy), (-hx, hy)), ((-hx, hy), (-hx, -hy))]
    for (a, b) in sides:
        a = np.array([a[0], a[1], z0])
        b = np.array([b[0], b[1], z0])
        top = np.array([apex_xy[0], apex_xy[1], apex])
        for r in range(rows):
            f0, f1 = r / rows, (r + 1) / rows
            A0, B0 = a + (top - a) * f0, b + (top - b) * f0
            A1, B1 = a + (top - a) * f1, b + (top - b) * f1
            drop = step if lod < 2 else 0.0
            if drop == 0:
                if r == rows - 1:
                    g.add(np.array([A0, B0, top]), [[0, 1, 2]], mat, tag)
                else:
                    g.add(np.array([A0, B0, B1, A1]), [[0, 1, 2, 3]], mat, tag)
                continue
            V = np.array([A0 - (0, 0, drop), B0 - (0, 0, drop), B1, A1, A0, B0])
            if r == rows - 1:
                V[2] = top
                V[3] = top + (A1 - B1) * 0.001
            g.add(V, [[4, 5, 2, 3], [0, 1, 5, 4]], mat, tag)
    return g


def door_hinge_strap(g, hinge_xy, y_face, z, length, w, lod, mat="bronze", tag="hinge", out=-1, leaf=True):
    """Bronze strap hinge lying on the door's outer face (y = y_face, outward = -Y): knuckle at hinge_xy,
    strap toward +X, decorative leaf end. Rivet heads as small boxes."""
    hx, hy = hinge_xy
    t = 0.014
    y0 = y_face + out * t / 2
    pts = np.array([[hx, y0, z], [hx + length * 0.82, y0, z]])
    g.box(((pts[0] + pts[1]) / 2), (length * 0.82, t, w), mat=mat, tag=tag)
    if leaf:
        tipx = hx + length * 0.82
        poly = np.array([[0, -w * 0.62], [length * 0.13, -w * 0.45], [length * 0.18, 0.0], [length * 0.13, w * 0.45],
                         [0, w * 0.62]])
        Rl = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)   # local x->X, y->Z, z->-Y
        g.prism(poly, -t / 2, t / 2, mat, tag, R=Rl, t=(tipx, y0, z))
    if lod == 0:
        for k in range(3):
            rx = hx + length * (0.22 + 0.24 * k)
            g.box((rx, y0 + out * t * 0.9, z), (0.026, 0.012, 0.026), mat=mat, tag=tag + "_rivet")
    return g


def knuckle(g, x, y, z0, z1, r, n=8, mat="bronze", tag="knuckle"):
    return g.cyl((x, y, z0), (x, y, z1), r, n=n, mat=mat, tag=tag)
