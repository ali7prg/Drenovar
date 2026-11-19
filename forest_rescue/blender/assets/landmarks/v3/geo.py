"""Landmarks v3 geometry kit (pure numpy): parts with material classes -> triangle soups.

Every primitive appends polygons to a Geo with a material class ('stone', 'wood', 'roof', 'cloth', 'rope',
'metal', 'ground', 'water', 'glow', 'card_*') and a part tag (used for texture-fill colour matching).
Blender axes: Z up, metres.
"""
import math

import numpy as np


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def frame_from(direction, up=(0, 0, 1)):
    """Rotation whose local X = direction, local Z ~ up."""
    x = np.asarray(direction, float)
    x = x / np.linalg.norm(x)
    u = np.asarray(up, float)
    if abs(np.dot(u, x)) > 0.98:
        u = np.array([0, 1.0, 0]) if abs(x[1]) < 0.9 else np.array([1.0, 0, 0])
    y = np.cross(u, x)
    y /= np.linalg.norm(y)
    z = np.cross(x, y)
    return np.stack([x, y, z], 1)


class Geo:
    def __init__(self, seed=0):
        self.V = []
        self.F = []          # list of index lists (global)
        self.M = []          # material class per face
        self.T = []          # part tag per face
        self.UV = []         # optional fixed uv per face (list of (u,v)) or None
        self.n = 0
        self.rng = np.random.default_rng(seed)

    # ------------------------------------------------------------- core
    def add(self, V, F, mat, tag, uv=None):
        V = np.asarray(V, float)
        base = self.n
        self.V.append(V)
        self.n += len(V)
        for i, f in enumerate(F):
            self.F.append([base + int(k) for k in f])
            self.M.append(mat)
            self.T.append(tag)
            self.UV.append(None if uv is None else uv[i])
        return self

    def extend(self, other):
        base = self.n
        for V in other.V:
            self.V.append(V)
        self.n += other.n
        for f, m, t, uv in zip(other.F, other.M, other.T, other.UV):
            self.F.append([base + k for k in f])
            self.M.append(m)
            self.T.append(t)
            self.UV.append(uv)
        return self

    def arrays(self):
        V = np.concatenate(self.V) if self.V else np.zeros((0, 3))
        return V, self.F, self.M, self.T, self.UV

    def tris(self, mats=None):
        return sum(len(f) - 2 for f, m in zip(self.F, self.M) if mats is None or m in mats)

    def subset(self, pred):
        g = Geo()
        V = np.concatenate(self.V) if self.V else np.zeros((0, 3))
        used = {}
        for f, m, t, uv in zip(self.F, self.M, self.T, self.UV):
            if not pred(m, t):
                continue
            idx = []
            for k in f:
                if k not in used:
                    used[k] = len(used)
                idx.append(used[k])
            g.F.append(idx)
            g.M.append(m)
            g.T.append(t)
            g.UV.append(uv)
        order = np.array(sorted(used, key=used.get), dtype=np.int64)
        g.V = [V[order]] if len(order) else []
        g.n = len(order)
        return g

    def transform(self, R=None, t=(0, 0, 0)):
        R = np.eye(3) if R is None else np.asarray(R, float)
        self.V = [V @ R.T + np.asarray(t, float) for V in self.V]
        return self

    # ------------------------------------------------------------- primitives
    def box(self, c, size, R=None, mat="wood", tag="", skip=(), chamfer=0.0):
        """Box centred at c (size full extents) rotated by R. skip: faces to drop ('+x','-x',...).
        chamfer > 0: the 4 edges parallel to local X get a 45-degree chamfer (octagonal beam)."""
        sx, sy, sz = (np.asarray(size, float) / 2.0)
        R = np.eye(3) if R is None else np.asarray(R, float)
        c = np.asarray(c, float)
        if chamfer > 0:
            ch = min(chamfer, sy * 0.45, sz * 0.45)
            prof = [(-sy + ch, -sz), (sy - ch, -sz), (sy, -sz + ch), (sy, sz - ch), (sy - ch, sz), (-sy + ch, sz),
                    (-sy, sz - ch), (-sy, -sz + ch)]
            V = [(x, y, z) for x in (-sx, sx) for (y, z) in prof]
            V = np.array(V) @ R.T + c
            F = []
            n = len(prof)
            names = ["-z", "+y", "+y", "+y", "+z", "-y", "-y", "-y"]
            for i in range(n):
                j = (i + 1) % n
                if names[i] in skip and i in (0, 4):
                    continue
                F.append([i, j, n + j, n + i])
            if "-x" not in skip:
                F.append(list(range(n))[::-1])
            if "+x" not in skip:
                F.append([n + i for i in range(n)])
            return self.add(V, F, mat, tag)
        V = np.array([[x, y, z] for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)])
        V = V @ R.T + c
        faces = {"-x": [0, 1, 3, 2], "+x": [4, 6, 7, 5], "-y": [0, 4, 5, 1], "+y": [2, 3, 7, 6],
                 "-z": [0, 2, 6, 4], "+z": [1, 5, 7, 3]}
        F = [f for k, f in faces.items() if k not in skip]
        return self.add(V, F, mat, tag)

    def beam(self, p0, p1, w, h, up=(0, 0, 1), mat="wood", tag="", chamfer=0.0, ext=0.0, skip=()):
        p0 = np.asarray(p0, float)
        p1 = np.asarray(p1, float)
        d = p1 - p0
        L = np.linalg.norm(d)
        R = frame_from(d, up)
        return self.box((p0 + p1) / 2, (L + 2 * ext, w, h), R, mat, tag, chamfer=chamfer, skip=skip)

    def cyl(self, p0, p1, r0, r1=None, n=8, mat="wood", tag="", caps=(True, True), up=(0, 0, 1), jitter=0.0):
        r1 = r0 if r1 is None else r1
        p0 = np.asarray(p0, float)
        p1 = np.asarray(p1, float)
        R = frame_from(p1 - p0, up)
        a = np.linspace(0, 2 * math.pi, n, endpoint=False)
        ring = np.stack([np.zeros(n), np.cos(a), np.sin(a)], 1)
        jr = 1 + jitter * (self.rng.random(n) - 0.5) if jitter else np.ones(n)
        V0 = p0 + (ring * (r0 * jr)[:, None]) @ R.T
        V1 = p1 + (ring * (r1 * jr)[:, None]) @ R.T
        V = np.concatenate([V0, V1])
        F = [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
        if caps[0]:
            F.append(list(range(n))[::-1])
        if caps[1]:
            F.append([n + i for i in range(n)])
        return self.add(V, F, mat, tag)

    def tube(self, P, r, n=6, mat="rope", tag="", up=(0, 0, 1), caps=False):
        """Swept circle along polyline P (rope, rails, ribs)."""
        P = np.asarray(P, float)
        m = len(P)
        rr = np.full(m, r) if np.isscalar(r) else np.asarray(r, float)
        a = np.linspace(0, 2 * math.pi, n, endpoint=False)
        V = []
        prev_y = None
        for i in range(m):
            t = P[min(i + 1, m - 1)] - P[max(i - 1, 0)]
            R = frame_from(t, up)
            if prev_y is not None and np.dot(R[:, 1], prev_y) < 0:
                R[:, 1] *= -1
                R[:, 2] *= -1
            prev_y = R[:, 1]
            for k in range(n):
                V.append(P[i] + rr[i] * (math.cos(a[k]) * R[:, 1] + math.sin(a[k]) * R[:, 2]))
        F = []
        for i in range(m - 1):
            for k in range(n):
                k2 = (k + 1) % n
                F.append([i * n + k, i * n + k2, (i + 1) * n + k2, (i + 1) * n + k])
        if caps:
            F.append(list(range(n))[::-1])
            F.append([(m - 1) * n + k for k in range(n)])
        return self.add(np.array(V), F, mat, tag)

    def quad(self, a, b, c, d, mat, tag, uv=None):
        return self.add(np.array([a, b, c, d], float), [[0, 1, 2, 3]], mat, tag, uv=[uv] if uv is not None else None)

    def grid_surface(self, P, mat, tag, double=False, uv=None):
        """P (nu, nv, 3) quad grid -> faces. uv (nu,nv,2) fixed UVs (optional)."""
        P = np.asarray(P, float)
        nu, nv = P.shape[:2]
        V = P.reshape(-1, 3)
        F, U = [], []
        for i in range(nu - 1):
            for j in range(nv - 1):
                f = [i * nv + j, (i + 1) * nv + j, (i + 1) * nv + j + 1, i * nv + j + 1]
                F.append(f)
                if uv is not None:
                    U.append([tuple(uv.reshape(-1, 2)[k]) for k in f])
        self.add(V, F, mat, tag, uv=U if uv is not None else None)
        if double:
            self.add(V, [f[::-1] for f in F], mat, tag + "_back", uv=[u[::-1] for u in U] if uv is not None else None)
        return self

    def prism(self, poly, z0, z1, mat, tag, R=None, t=(0, 0, 0), caps=(True, True)):
        """Extruded 2-D polygon (counter-clockwise, local XY) from z0 to z1."""
        poly = np.asarray(poly, float)
        n = len(poly)
        V = np.concatenate([np.c_[poly, np.full(n, z0)], np.c_[poly, np.full(n, z1)]])
        if R is not None:
            V = V @ np.asarray(R).T
        V = V + np.asarray(t, float)
        F = [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
        if caps[0]:
            F.append(list(range(n))[::-1])
        if caps[1]:
            F.append([n + i for i in range(n)])
        return self.add(V, F, mat, tag)

    def rock(self, c, radii, seed=0, sub=1, mat="stone", tag="rock", flat_bottom=True, rough=0.18, R=None):
        """Lumpy rock: subdivided octahedron/icosphere with smooth noise; bottom flattened."""
        rng = np.random.default_rng(seed)
        V, F = icosphere(sub)
        k = rng.normal(size=(6, 3))
        disp = 1 + rough * (np.sin(V @ k[:3].T * 2.3 + rng.random(3) * 6).sum(1) / 3 +
                            0.5 * np.sin(V @ k[3:].T * 4.1 + rng.random(3) * 6).sum(1) / 3)
        V = V * disp[:, None]
        # blocky facets: flatten towards a few random planes
        for _ in range(3):
            nrm = rng.normal(size=3)
            nrm /= np.linalg.norm(nrm)
            d = V @ nrm
            cut = np.quantile(d, 0.8)
            over = d > cut
            V[over] -= np.outer(d[over] - cut, nrm) * 0.7
        V = V * np.asarray(radii, float)
        if flat_bottom:
            V[:, 2] = np.maximum(V[:, 2], -radii[2] * 0.35)
        if R is not None:
            V = V @ np.asarray(R).T
        return self.add(V + np.asarray(c, float), F, mat, tag)

    # ------------------------------------------------------------- masonry
    def masonry_face(self, origin, ex, ey, width, height, courses, rng=None, block=(0.45, 0.85), gap=0.03,
                     relief=0.04, bevel=0.035, mat="stone", tag="masonry", offsets=None, backing=True,
                     cheap=False, ragged_top=None, min_block=0.18):
        """A wall face: origin = lower-left corner, ex = unit along width, ey = unit up the face,
        normal = ex x ey. courses: list of course heights (bottom->top). Each block is a bevelled pillow
        (front quad inset by `bevel` + 4 chamfer quads down to the backing plane), mortar gaps between.
        ragged_top: optional function(s in [0,width]) -> max height (ruined walls)."""
        rng = rng or self.rng
        o = np.asarray(origin, float)
        ex = np.asarray(ex, float)
        ey = np.asarray(ey, float)
        nz = np.cross(ex, ey)
        nz /= np.linalg.norm(nz)
        if backing:
            top_h = sum(courses)
            self.quad(o - nz * 0.0, o + ex * width, o + ex * width + ey * top_h, o + ey * top_h, mat, tag + "_mortar")
        y = 0.0
        for ci, ch in enumerate(courses):
            x = 0.0 if offsets is None else -offsets[ci]
            while x < width - 1e-6:
                L = rng.uniform(*block)
                x0, x1 = max(x, 0.0), min(x + L, width)
                if width - x1 < min_block:
                    x1 = width
                x = x1 if x1 >= width else x + L
                if x1 - x0 < 0.05:
                    continue
                if ragged_top is not None and y + ch > ragged_top((x0 + x1) / 2):
                    continue
                g = gap / 2
                a0, a1 = x0 + (g if x0 > 1e-6 else 0), x1 - (g if x1 < width - 1e-6 else 0)
                b0, b1 = y + g, y + ch - g
                rl = relief * rng.uniform(0.6, 1.3)
                bv = min(bevel, (a1 - a0) * 0.3, (b1 - b0) * 0.3)
                corners = [(a0, b0), (a1, b0), (a1, b1), (a0, b1)]
                P0 = [o + ex * u + ey * v for u, v in corners]
                if cheap:
                    P1 = [p + nz * rl for p in P0]
                    self.add(np.array(P1), [[0, 1, 2, 3]], mat, tag)
                    continue
                inner = [(a0 + bv, b0 + bv), (a1 - bv, b0 + bv), (a1 - bv, b1 - bv), (a0 + bv, b1 - bv)]
                bulge = rl + rng.uniform(0, 0.02)
                P1 = [o + ex * u + ey * v + nz * bulge for u, v in inner]
                V = np.array(P0 + P1)
                F = [[4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
                self.add(V, F, mat, tag)
            y += ch
        return self

    def masonry_box(self, lo, hi, course=0.42, block=(0.5, 0.9), gap=0.035, relief=0.045, bevel=0.04,
                    faces=("+x", "-x", "+y", "-y"), top=True, mat="stone", tag="masonry", cheap=False, seed=0,
                    ragged=None, top_blocks=True, cheap_faces=()):
        """Masonry block (pier/abutment/tower shaft) between lo and hi corners (axis aligned)."""
        rng = np.random.default_rng(seed)
        lo = np.asarray(lo, float)
        hi = np.asarray(hi, float)
        H = hi[2] - lo[2]
        n = max(1, int(round(H / course)))
        courses = [H / n] * n
        offs = [rng.uniform(0, block[0]) for _ in range(n)]
        sx, sy = hi[0] - lo[0], hi[1] - lo[1]
        fdef = {"-y": (lo, np.array([1.0, 0, 0]), sx), "+x": (np.array([hi[0], lo[1], lo[2]]), np.array([0, 1.0, 0]), sy),
                "+y": (np.array([hi[0], hi[1], lo[2]]), np.array([-1.0, 0, 0]), sx),
                "-x": (np.array([lo[0], hi[1], lo[2]]), np.array([0, -1.0, 0]), sy)}
        for k, (o, ex, w) in fdef.items():
            if k not in faces:
                continue
            ofs = [(v + 0.37 * ("+x-y+y-x".index(k))) % block[0] for v in offs]
            self.masonry_face(o, ex, np.array([0, 0, 1.0]), w, H, courses, rng=rng, block=block, gap=gap,
                              relief=relief, bevel=bevel, mat=mat, tag=tag, offsets=ofs, cheap=cheap or k in cheap_faces,
                              ragged_top=None if ragged is None else ragged.get(k))
        if top:
            if top_blocks:
                # cap course: slabs across the top
                z = hi[2]
                xs = np.linspace(lo[0], hi[0], max(2, int(round(sx / 0.7)) + 1))
                for i in range(len(xs) - 1):
                    self.box(((xs[i] + xs[i + 1]) / 2, (lo[1] + hi[1]) / 2, z + 0.03),
                             (xs[i + 1] - xs[i] - 0.03, sy + 0.06, 0.06), mat=mat, tag=tag + "_cap", skip=("-z",))
            else:
                self.quad((lo[0], lo[1], hi[2]), (hi[0], lo[1], hi[2]), (hi[0], hi[1], hi[2]), (lo[0], hi[1], hi[2]),
                          mat, tag + "_top")
        return self

    def rounded_block(self, c, size, r, R=None, mat="stone", tag="block", skip=(), seed=0, jitter=0.0):
        """Block with rounded edges: 3x3 vertex grid per face pushed onto a rounded box (edge radius r)."""
        hs = np.asarray(size, float) / 2.0
        r = float(min(r, hs.min() * 0.9))
        inner = hs - r
        rng = np.random.default_rng(seed)
        faces = {"+x": (0, 1, 2, 1), "-x": (0, 2, 1, -1), "+y": (1, 2, 0, 1), "-y": (1, 0, 2, -1), "+z": (2, 0, 1, 1),
                 "-z": (2, 1, 0, -1)}
        V, F = [], []
        g = np.array([-1.0, 0.0, 1.0])
        for k, (ax, a1, a2, sg) in faces.items():
            if k in skip:
                continue
            base = len(V)
            for i in range(3):
                for j in range(3):
                    p = np.zeros(3)
                    p[ax] = sg * hs[ax]
                    p[a1] = g[i] * hs[a1]
                    p[a2] = g[j] * hs[a2]
                    q = np.clip(p, -inner, inner)
                    d = p - q
                    n = np.linalg.norm(d)
                    p2 = q + (d / n * r if n > 1e-9 else 0)
                    if jitter:
                        p2 = p2 * (1 + jitter * (rng.random(3) - 0.5))
                    V.append(p2)
            for i in range(2):
                for j in range(2):
                    a = base + i * 3 + j
                    F.append([a, a + 3, a + 4, a + 1])
        V = np.array(V)
        R = np.eye(3) if R is None else np.asarray(R, float)
        V = V @ R.T + np.asarray(c, float)
        # orient faces outward (winding by face normal vs centre)
        F2 = []
        for f in F:
            P = V[f]
            nrm = np.cross(P[1] - P[0], P[2] - P[0])
            if nrm @ (P.mean(0) - c) < 0:
                f = f[::-1]
            F2.append(f)
        return self.add(V, F2, mat, tag)

    def card(self, base, w, h, yaw, mat, tag, uv_rect, tilt=0.0, bend=0.0):
        """Vertical alpha card (grass/ivy sprite) standing at base; uv_rect=(u0,v0,u1,v1) in the card atlas."""
        u0, v0, u1, v1 = uv_rect
        R = rot_z(yaw) @ rot_x(tilt)
        P = np.array([[-w / 2, 0, 0], [w / 2, 0, 0], [w / 2 + bend, 0, h], [-w / 2 + bend, 0, h]]) @ R.T + base
        return self.add(P, [[0, 1, 2, 3]], mat, tag, uv=[[(u0, v0), (u1, v0), (u1, v1), (u0, v1)]])


def icosphere(sub=1):
    t = (1 + 5 ** 0.5) / 2
    V = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
         (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    F = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
         (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10),
         (8, 6, 7), (9, 8, 1)]
    V = [np.array(v, float) / np.linalg.norm(v) for v in V]
    for _ in range(sub):
        cache = {}
        nf = []

        def mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in cache:
                m = V[a] + V[b]
                V.append(m / np.linalg.norm(m))
                cache[key] = len(V) - 1
            return cache[key]
        for a, b, c in F:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        F = nf
    return np.array(V), [list(f) for f in F]


def triangulate(F):
    out = []
    for f in F:
        for k in range(1, len(f) - 1):
            out.append((f[0], f[k], f[k + 1]))
    return out
