"""Landmark kitbash primitives (numpy -> treegen.MeshData) with world-scaled tiling UVs.

Material slot ids (global, remapped per object): STONE, WOOD, MISC (atlas, alpha), ROOF, GLOW (emissive).
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "forest"))
from treegen import MeshData, normalize  # noqa: E402
import lm_textures as lmt  # noqa: E402

STONE, WOOD, MISC, ROOF, GLOW = 0, 1, 2, 3, 4
MAT_NAMES = {STONE: "lm_stone", WOOD: "lm_wood", MISC: "lm_misc", ROOF: "lm_roof", GLOW: "lm_glow"}


def rotm(rx=0.0, ry=0.0, rz=0.0):
    cx, cy, cz = math.cos(rx), math.cos(ry), math.cos(rz)
    sx, sy, sz = math.sin(rx), math.sin(ry), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


class Kit:
    def __init__(self, seed=0):
        self.md = MeshData()
        self.rng = np.random.default_rng(seed)
        self.colliders = []

    # ------------------------------------------------------------------ primitives
    def box(self, c, size, R=None, mat=STONE, tile=1.0, rect=None, skip=(), uv_jitter=True, grain_axis=None):
        """Axis box (centre, full size) rotated by R. UVs world-scaled (tile metres) or into an atlas rect."""
        c = np.asarray(c, float)
        hx, hy, hz = np.asarray(size, float) / 2
        R = np.eye(3) if R is None else R
        corners = np.array([[sx * hx, sy * hy, sz * hz] for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)])
        V = corners @ R.T + c
        # faces: -z, +z, -y, +y, -x, +x  (indices into corners: bit0 x, bit1 y, bit2 z)
        F = {"-z": (0, 2, 3, 1), "+z": (4, 5, 7, 6), "-y": (0, 1, 5, 4), "+y": (2, 6, 7, 3), "-x": (0, 4, 6, 2),
             "+x": (1, 3, 7, 5)}
        dims = {"-z": (2 * hx, 2 * hy), "+z": (2 * hx, 2 * hy), "-y": (2 * hx, 2 * hz), "+y": (2 * hx, 2 * hz),
                "-x": (2 * hy, 2 * hz), "+x": (2 * hy, 2 * hz)}
        faces, uvs = [], []
        off = self.rng.random(2) * 4 if uv_jitter else np.zeros(2)
        for k, f in F.items():
            if k in skip:
                continue
            w, h = dims[k]
            if grain_axis == "x" and k in ("-z", "+z", "-y", "+y"):
                w, h = h, w
            if rect is not None:
                u0, v0, u1, v1 = rect
                uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
            else:
                a, b = w / tile, h / tile
                uv = [(off[0], off[1]), (off[0] + a, off[1]), (off[0] + a, off[1] + b), (off[0], off[1] + b)]
                if grain_axis == "x" and k in ("-z", "+z", "-y", "+y"):
                    uv = [(p[1], p[0]) for p in uv]
            faces.append(f)
            uvs.append(uv)
        self.md.add(V, faces, uvs, mat, np.ones((8, 4)))

    def beam(self, a, b, w, h, mat=WOOD, up=(0, 0, 1), tile=1.2, rect=None):
        """Timber between points a and b (cross-section w x h), grain along the length."""
        a, b = np.asarray(a, float), np.asarray(b, float)
        d = b - a
        L = np.linalg.norm(d)
        x = d / L
        upv = np.asarray(up, float)
        if abs(np.dot(upv, x)) > 0.95:
            upv = np.array([1.0, 0, 0]) if abs(x[0]) < 0.9 else np.array([0, 1.0, 0])
        y = normalize(np.cross(upv, x))
        z = np.cross(x, y)
        R = np.stack([x, y, z], 1)
        self.box((a + b) / 2, (L, w, h), R, mat, tile, rect=rect, grain_axis="x")

    def cyl(self, a, b, r, segs=8, mat=WOOD, tile=1.0, rect=None, caps=True, r2=None, cap_rect=None):
        a, b = np.asarray(a, float), np.asarray(b, float)
        d = b - a
        L = np.linalg.norm(d)
        x = d / L
        p = normalize(np.cross(x, [0, 0, 1.0] if abs(x[2]) < 0.9 else [1.0, 0, 0]))
        q = np.cross(x, p)
        r2 = r if r2 is None else r2
        verts, faces, uvs = [], [], []
        circ = 2 * np.pi * max(r, r2)
        k = max(1, round(circ / tile)) if rect is None else 1
        for i, (c, rr) in enumerate(((a, r), (b, r2))):
            for j in range(segs):
                t = 2 * np.pi * j / segs
                verts.append(c + rr * (math.cos(t) * p + math.sin(t) * q))
        for j in range(segs):
            j2 = (j + 1) % segs
            faces.append((j, j2, segs + j2, segs + j))
            if rect is None:
                uvs.append([(k * j / segs, 0), (k * (j + 1) / segs, 0), (k * (j + 1) / segs, L / tile), (k * j / segs, L / tile)])
            else:
                u0, v0, u1, v1 = rect
                uvs.append([(u0 + (u1 - u0) * j / segs, v0), (u0 + (u1 - u0) * (j + 1) / segs, v0),
                            (u0 + (u1 - u0) * (j + 1) / segs, v1), (u0 + (u1 - u0) * j / segs, v1)])
        if caps:
            for base, flip in ((0, True), (segs, False)):
                ci = len(verts)
                verts.append(a if base == 0 else b)
                for j in range(segs):
                    j2 = (j + 1) % segs
                    f = (base + j2, base + j, ci) if flip else (base + j, base + j2, ci)
                    faces.append(f)
                    cr = cap_rect or rect
                    if cr is None:
                        t1, t2 = 2 * np.pi * j / segs, 2 * np.pi * j2 / segs
                        rr = (r if base == 0 else r2) / tile
                        uvs.append([(0.5 + rr * math.cos(t2 if flip else t1), 0.5 + rr * math.sin(t2 if flip else t1)),
                                    (0.5 + rr * math.cos(t1 if flip else t2), 0.5 + rr * math.sin(t1 if flip else t2)),
                                    (0.5, 0.5)])
                    else:
                        u0, v0, u1, v1 = cr
                        uvs.append([(u0, v0), (u1, v0), ((u0 + u1) / 2, v1)])
        self.md.add(np.array(verts), faces, uvs, mat, np.ones((len(verts), 4)))

    def quad(self, corners, uv, mat):
        self.md.add(np.asarray(corners, float), [(0, 1, 2, 3)], [uv], mat, np.ones((4, 4)))

    def rock(self, c, size, mat=STONE, detail=1, tile=1.0, flat_bottom=True):
        """Irregular stone: jittered octahedron-sphere (detail 1 = 32 tris)."""
        c = np.asarray(c, float)
        V, F = icosphere(detail)
        V = V * (1 + self.rng.normal(0, 0.12, (len(V), 1)))
        V = V * np.asarray(size, float) / 2
        if flat_bottom:
            V[:, 2] = np.maximum(V[:, 2], -size[2] * 0.25)
        V = V @ rotm(0, 0, self.rng.uniform(0, 6.28)).T + c
        uvs = [[(V[i, 0] / tile + V[i, 2] / tile * 0.5, V[i, 1] / tile + V[i, 2] / tile * 0.5) for i in f] for f in F]
        self.md.add(V, [tuple(f) for f in F], uvs, mat, np.ones((len(V), 4)))

    # ------------------------------------------------------------------ assemblies
    def block_wall(self, x0, x1, z0, height, thick, course=0.42, block=(0.55, 0.85), y=0.0, axis="x", gap=0.025,
                   profile=None, R=None, origin=(0, 0, 0), mat=STONE, jitter=0.02, skip_fn=None):
        """Coursed ashlar wall between x0..x1 (along `axis`), bottom z0; profile(t)->max height (ruins)."""
        rows = int(math.ceil(height / course))
        o = np.asarray(origin, float)
        R = np.eye(3) if R is None else R
        for r in range(rows):
            zb = z0 + r * course
            x = x0 - (self.rng.uniform(0.1, 0.4) if r % 2 else 0.0)
            while x < x1 - 0.05:
                L = self.rng.uniform(*block)
                xa, xb = max(x, x0), min(x + L, x1)
                if xb - xa > 0.12:
                    t = (0.5 * (xa + xb) - x0) / max(x1 - x0, 1e-6)
                    top = profile(t) if profile is not None else height
                    if zb + course * 0.5 <= top and (skip_fn is None or not skip_fn(0.5 * (xa + xb), zb + course / 2)):
                        cc = np.array([0.5 * (xa + xb), y + self.rng.normal(0, jitter), zb + course / 2])
                        sz = np.array([xb - xa - gap, thick + self.rng.normal(0, 0.02), course - gap])
                        Rl = rotm(0, 0, self.rng.normal(0, 0.015))
                        if axis == "y":
                            cc = np.array([cc[1], cc[0], cc[2]])
                            sz = np.array([sz[1], sz[0], sz[2]])
                        self.box(R @ cc + o, sz, R @ Rl, mat, tile=1.6)
                x += L

    def arch(self, cx, z_spring, span, thick, depth, n=11, y=0.0, mat=STONE, R=None, origin=(0, 0, 0)):
        """Semicircular arch of voussoirs (in XZ, depth along Y)."""
        R = np.eye(3) if R is None else R
        o = np.asarray(origin, float)
        r_in = span / 2
        r_mid = r_in + thick / 2
        for i in range(n):
            a0, a1 = np.pi * i / n, np.pi * (i + 1) / n
            am = 0.5 * (a0 + a1)
            c = np.array([cx + r_mid * math.cos(am), y, z_spring + r_mid * math.sin(am)])
            L = 2 * r_mid * math.sin((a1 - a0) / 2) - 0.03
            Rl = rotm(0, -(am - np.pi / 2), 0)
            self.box(R @ c + o, (L, depth, thick), R @ Rl, mat, tile=1.6)

    def stairs(self, x0, z0, n, run, rise, width, y0=0.0, dirx=1.0, mat=STONE, R=None, origin=(0, 0, 0)):
        R = np.eye(3) if R is None else R
        o = np.asarray(origin, float)
        for i in range(n):
            c = np.array([x0 + dirx * (i + 0.5) * run, y0, z0 + (i + 0.5) * rise - 0.5 * rise * i])
            h = rise * (i + 1)
            c[2] = z0 + h / 2
            self.box(R @ c + o, (run - 0.02, width, h), R, mat, tile=1.6)

    def collider(self, kind, centre, size, yaw=0.0):
        """Record a collision primitive (Blender coords); converted to glTF axes on export."""
        self.colliders.append(dict(type=kind, centre=list(map(float, centre)), size=list(map(float, size)), yaw=float(yaw)))


def icosphere(detail=1):
    t = (1 + 5 ** 0.5) / 2
    V = np.array([[-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0], [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
                  [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1]], float)
    F = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
         (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10),
         (8, 6, 7), (9, 8, 1)]
    V = normalize(V)
    if detail == 0:
        return V, F
    V = list(V)
    cache = {}

    def mid(a, b):
        k = (min(a, b), max(a, b))
        if k not in cache:
            V.append(normalize((V[a] + V[b]) / 2))
            cache[k] = len(V) - 1
        return cache[k]
    F2 = []
    for a, b, c in F:
        ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
        F2 += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
    return np.array(V), F2
