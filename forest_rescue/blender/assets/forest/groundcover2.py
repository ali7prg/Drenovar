"""Ground cover v2 (review rework): angular fractured limestone with draped moss shells, fallen trunk with
moss carpet + splintered end + stream-bed variant, open bramble mound, arching fern rosettes.

Moss shells: the SDF is dilated by t(x) = thickness * upness(grad) * noise; faces outside the bare surface
(F_bare > eps) become moss (foliage-atlas moss tile), the rest keeps the rock/bark material -> a fuzzy,
displaced moss carpet with an irregular border instead of flat cards.
"""
import math
import numpy as np

import atlas
import treegen as tg
from treegen import MeshData, normalize
import trees
import trees_hollow as th
import groundcover as gc

import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from frlib import sdf, texproj  # noqa: E402


def _grid(F):
    return np.stack(np.meshgrid(*F.axes, indexing="ij"), -1)


def moss_dilate(F, thick, seed, up_lo=0.3, cover=0.55, freq=0.7, streak=False):
    """Dilate F.d on up-facing regions (noise-patchy); returns the bare field copy.
    streak=True adds vertical moss streaks running down the sides (bark furrows)."""
    bare = F.d.copy()
    gx, gy, gz = np.gradient(F.d, F.voxel)
    gn = np.sqrt(gx ** 2 + gy ** 2 + gz ** 2) + 1e-6
    up = np.clip((gz / gn - up_lo) / (1 - up_lo), 0, 1)
    P = _grid(F)
    n = texproj.fbm(P, freq, 4, seed=seed)
    if streak:
        st = texproj.fbm(P * np.array([3.0, 3.0, 0.25]), 1.0, 3, seed=seed + 7)
        side = np.clip(1 - np.abs(gz / gn), 0, 1)
        up = np.maximum(up, side * (st > 0.62) * 0.8)
    patch = np.clip((n - (1 - cover) * 0.8 - 0.1) * 5, 0, 1)
    fuzz = 0.6 + 0.8 * texproj.fbm(P, 6.0, 2, seed=seed + 1)
    t = thick * up * patch * fuzz
    F.d = (F.d - t).astype(np.float32)
    return bare


def split_moss(V, T, bare_field, F, eps=0.012):
    """Per-face moss flag: centroid outside the bare surface by > eps."""
    idx = (V[T].mean(1) - F.lo) / F.voxel
    from scipy import ndimage as ndi
    d = ndi.map_coordinates(bare_field, idx.T, order=1, mode="nearest")
    return d > eps


def emit_split(md, V, T, is_moss, mat_main, mat_moss, uv_main, rng, tile="moss_clump"):
    """Main faces keep uv_main(face); moss faces get the opaque centre of the moss tile (planar, noisy)."""
    u0, v0, u1, v1 = atlas.uv_rect(tile)
    cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
    hw = (u1 - u0) * 0.2
    fm, fu, mm, mu = [], [], [], []
    for f, m in zip(T, is_moss):
        if m:
            mm.append(tuple(int(i) for i in f))
            mu.append([(cu + ((V[i, 0] * 0.45 + V[i, 2] * 0.2) % 1.0 - 0.5) * hw,
                        cv + ((V[i, 1] * 0.45 + V[i, 2] * 0.2) % 1.0 - 0.5) * hw) for i in f])
        else:
            fm.append(tuple(int(i) for i in f))
            fu.append(uv_main(f))
    col = np.zeros((len(V), 4))
    col[:, 3] = 1.0
    if fm:
        md.add(V, fm, fu, mat_main, col)
    if mm:
        md.add(V, mm, mu, mat_moss, col)


def box_uv(V):
    def uv(f):
        p = V[f]
        n = np.cross(p[1] - p[0], p[2] - p[0])
        ax = int(np.argmax(np.abs(n)))
        if ax == 2:
            return [(q[0] / 2.0, q[1] / 2.0) for q in p]
        if ax == 1:
            return [(q[0] / 2.0, q[2] / 2.0) for q in p]
        return [(q[1] / 2.0, q[2] / 2.0) for q in p]
    return uv


# ============================================================================ angular limestone

def polyhedron(center, half, yaw, rng, n_planes=13, tilt=(0.0, 0.0), squash=1.0):
    """Irregular fractured block: convex hull of random planes tangent to a tilted ellipsoid; a few planes
    are pushed in further (fracture facets), so faces are planar but not box-like."""
    c = np.asarray(center, float)
    h = np.asarray(half, float)
    cy, sy = math.cos(yaw), math.sin(yaw)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    ax, ay = tilt
    Rx = np.array([[1, 0, 0], [0, math.cos(ax), -math.sin(ax)], [0, math.sin(ax), math.cos(ax)]])
    Ry = np.array([[math.cos(ay), 0, math.sin(ay)], [0, 1, 0], [-math.sin(ay), 0, math.cos(ay)]])
    Rm = Rz @ Ry @ Rx
    N = [np.array([0, 0, 1.0]), np.array([0, 0, -1.0])]              # roughly flat top/bottom beds
    N[0] = normalize(N[0] + rng.normal(0, 0.12, 3))
    g = (1 + 5 ** 0.5) / 2
    for i in range(n_planes):
        z = 1 - 2 * (i + 0.5) / n_planes
        rr = math.sqrt(max(0, 1 - z * z))
        a = 2 * np.pi * i / g + rng.uniform(0, 0.6)
        N.append(normalize(np.array([rr * math.cos(a), rr * math.sin(a), z * 0.55]) + rng.normal(0, 0.15, 3)))
    N = np.array(N)
    D = np.sqrt(((N * h) ** 2).sum(1)) * rng.uniform(0.86, 1.0, len(N))
    D[2 + rng.choice(n_planes, 3, replace=False)] *= rng.uniform(0.75, 0.88, 3)      # fracture facets

    def fn(P):
        q = (P - c) @ Rm
        return (q @ N.T - D).max(-1)
    ext = np.linalg.norm(h)
    return sdf.Prim(fn, c - ext, c + ext, k=0.0)


def polytope(center, half, yaw, rng, n_cuts=7, chip=0.18, tilt=(0.0, 0.0)):
    """Convex polytope SDF (box + random corner/edge plane cuts) -> planar fracture faces, chipped edges."""
    c = np.asarray(center, float)
    h = np.asarray(half, float)
    cy, sy = math.cos(yaw), math.sin(yaw)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    ax, ay = tilt
    Rx = np.array([[1, 0, 0], [0, math.cos(ax), -math.sin(ax)], [0, math.sin(ax), math.cos(ax)]])
    Ry = np.array([[math.cos(ay), 0, math.sin(ay)], [0, 1, 0], [-math.sin(ay), 0, math.cos(ay)]])
    Rm = Rz @ Ry @ Rx
    planes = []
    for k in range(3):
        for s in (-1, 1):
            n = np.zeros(3)
            n[k] = s
            planes.append((n, h[k]))
    for i in range(n_cuts):
        n = normalize(rng.normal(0, 1, 3) * np.array([1, 1, 0.8]) + np.sign(rng.normal(0, 1, 3)) * 0.6)
        support = np.abs(n) @ h
        planes.append((n, support * (1 - rng.uniform(0.06, chip))))
    N = np.array([p[0] for p in planes])
    D = np.array([p[1] for p in planes])

    def fn(P):
        q = (P - c) @ Rm
        return (q @ N.T - D).max(-1)
    ext = np.linalg.norm(h)
    return sdf.Prim(fn, c - ext, c + ext, k=0.0)


def build_moss_rock(variant):
    rng = np.random.default_rng(1600 + variant)
    res = gc._res(["rock", "foliage"], wind=False)
    if variant == 1:     # art/02: leaning fractured blocks, high mass left-centre, lower terrace right
        blocks = [((-1.2, 0.3, 2.4), (1.5, 1.3, 1.45), 0.15, (0.05, -0.16)), ((0.9, 0.2, 2.6), (1.0, 1.1, 1.9), 0.25, (0.04, 0.10)),
                  ((-2.9, 0.5, 1.0), (0.9, 1.0, 1.0), 0.5, (0.12, 0.18)), ((3.0, 0.4, 1.0), (1.3, 1.1, 1.0), -0.2, (-0.06, 0.12)),
                  ((1.9, -1.2, 0.55), (0.8, 0.6, 0.6), 0.6, (0.15, -0.1)), ((-0.6, -1.5, 0.5), (1.0, 0.6, 0.55), 0.1, (-0.1, 0.0)),
                  ((4.4, -0.8, 0.5), (0.6, 0.6, 0.55), 0.9, (0.1, 0.2)), ((-2.3, -1.4, 0.35), (0.55, 0.45, 0.4), 0.7, (0.2, 0)),
                  ((2.6, -1.9, 0.3), (0.45, 0.4, 0.32), 1.2, (0.1, 0.1)), ((-3.8, -0.7, 0.4), (0.6, 0.5, 0.42), 2.0, (0.1, 0.15))]
        size = (11, 6, 6)
        vox = 0.075
    elif variant == 2:
        blocks = [((0, 0, 0.9), (1.2, 0.9, 0.95), 0.2, (0.08, 0)), ((1.5, 0.6, 0.55), (0.8, 0.7, 0.55), 0.7, (0, 0.1)),
                  ((-1.3, -0.5, 0.4), (0.6, 0.55, 0.42), 1.1, (0, 0))]
        size = (6, 5, 3)
        vox = 0.05
    else:
        blocks = [((0, 0, 0.42), (0.75, 0.55, 0.48), 0.4, (0.1, 0.05))]
        size = (3, 3, 2)
        vox = 0.04
    prims = [polyhedron(c, h, yaw, rng, n_planes=13, tilt=tl) for (c, h, yaw, tl) in blocks]
    lo = np.array([-size[0] / 2 - 1, -size[1] / 2 - 1, -0.5])
    hi = np.array([size[0] / 2 + 1, size[1] / 2 + 1, size[2]])
    F = sdf.Field(lo, hi, vox)
    for p in prims:
        F.apply(p, op="union", k=0.0)
    P = _grid(F)
    # bevel/weathering noise + a few fracture slots
    F.d = (F.d + 0.05 * (texproj.fbm(P, 2.5, 3, seed=variant) - 0.5)
           + 0.03 * (texproj.fbm(P, 7.0, 2, seed=variant + 5) - 0.5)).astype(np.float32)        # chipped edges
    f1, f2 = texproj.voronoi(P * np.array([1.0, 1.0, 1.4]), 0.45, seed=variant + 3)
    F.d = (F.d + np.clip(0.04 - (f2 - f1), 0, None) * 1.2).astype(np.float32)
    F.d = np.maximum(F.d, -P[..., 2] - 0.2).astype(np.float32)
    F.smooth(0.55)
    bare = moss_dilate(F, {1: 0.2, 2: 0.12, 3: 0.08}[variant], seed=variant + 10, up_lo=0.25, cover=0.7)
    V, T = F.mesh()
    V, T = th.largest_components(V, T, min_frac=0.002)
    targets = {1: (2700, 1050, 300), 2: (1500, 600, 200), 3: (700, 280, 90)}[variant]
    for lod in range(3):
        v, t, n = th.decimate_bpy(V, T, targets[lod])
        md = MeshData()
        moss = split_moss(v, t, bare, F)
        emit_split(md, v, t, moss, 0, 1, box_uv(v), rng)
        fn = normalize(np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]]))
        if lod < 2:
            moss_fringe(md, v, t, moss, rng, {1: [70, 24], 2: [30, 10], 3: [12, 5]}[variant][lod],
                        {1: (0.5, 0.9), 2: (0.4, 0.7), 3: (0.3, 0.5)}[variant])
            shrub = {1: [30, 10], 2: [12, 5], 3: [5, 2]}[variant][lod]
            ssz = {1: (0.8, 1.4), 2: (0.6, 1.0), 3: (0.45, 0.7)}[variant]
            gc._cards_on_surface(md, v, t, fn, rng, shrub, ["shrub_orange", "shrub_orange", "grass_a", "grass_b"]
                                 if lod == 0 else ["shrub_dense"], ssz, 1, up_min=0.35, flat=False)
        if lod == 0:
            for k in range({1: 14, 2: 6, 3: 3}[variant]):            # small stones around
                a = rng.uniform(0, 2 * np.pi)
                r = rng.uniform(0.6, 1.0) * np.array([size[0], size[1]]) / 2 * 0.95
                pts, faces = _pebble(np.array([math.cos(a) * r[0], math.sin(a) * r[1], 0.05]), rng.uniform(0.15, 0.35), rng)
                md.add(pts, faces, [box_uv(pts)(np.array(f)) for f in faces], 0, np.ones((len(pts), 4)))
        res.lods[lod] = md
        res.info[f"LOD{lod}"] = dict(tris=md.tris(), moss_faces=int(moss.sum()))
    return res


def moss_fringe(md, V, T, moss, rng, n, size, mat=1):
    """Fringe cards hanging over the moss-shell borders (moss faces adjacent to bare, steep faces)."""
    if not moss.any():
        return
    fn = normalize(np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]))
    cen = V[T].mean(1)
    mi = np.nonzero(moss & (fn[:, 2] < 0.75) & (fn[:, 2] > -0.2))[0]
    if len(mi) == 0:
        mi = np.nonzero(moss)[0]
    pick = rng.choice(mi, size=min(n, len(mi)), replace=len(mi) < n)
    for f in pick:
        nn = fn[f]
        out = normalize(np.array([nn[0], nn[1], 0.0]) + rng.normal(0, 0.2, 3) * np.array([1, 1, 0]))
        s = rng.uniform(*size)
        top = cen[f] + nn * 0.02
        side = normalize(np.cross(out, np.array([0, 0, 1.0])))
        down = normalize(np.array([0, 0, -1.0]) + out * 0.25)
        corners = np.array([top - side * s / 2, top + side * s / 2, top + side * s / 2 + down * s, top - side * s / 2 + down * s])
        u0, v0, u1, v1 = atlas.uv_rect("moss_fringe")
        uv = [(u0, v1), (u1, v1), (u1, v0), (u0, v0)]
        col = np.ones((4, 4))
        col[:, 3] = 0.85
        nrm = np.tile(normalize(out + np.array([0, 0, 0.5])), (4, 1))
        md.add(corners, [(0, 1, 2, 3)], [uv], mat, col, normals=nrm)


def _pebble(c, r, rng):
    V, F = _ico()
    V = V * r * (1 + rng.normal(0, 0.15, (len(V), 1)))
    V[:, 2] = np.maximum(V[:, 2] * 0.6, -0.02)
    return V + c, F


def _ico():
    t = (1 + 5 ** 0.5) / 2
    V = normalize(np.array([[-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0], [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
                            [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1]], float))
    F = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
         (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7),
         (9, 8, 1)]
    return V, F


# ============================================================================ fallen trunk

def build_fallen_trunk(variant):
    """v1: art/02 log arching over a stream bed (root plate left, splintered break right); v2: log on the ground;
    v3: v1 + stream bed (water strip, rocks, pebbles)."""
    rng = np.random.default_rng(1500 + variant)
    mats = ["bark:hollow", "foliage"] + (["rock"] if variant == 3 else [])
    res = gc._res(mats, wind=False)
    arch = variant in (1, 3)
    L = 10.0 if arch else 7.5
    xs = np.linspace(-L / 2, L / 2, 13)
    if arch:
        zc = 1.05 + 1.1 * np.sin(np.pi * (xs + L / 2) / L) ** 1.1
        rr = np.interp(xs, [-L / 2, -L / 2 + 1.5, L / 2 - 1.5, L / 2], [1.05, 0.9, 0.78, 0.7])
    else:
        zc = 0.45 + 0.02 * xs
        rr = np.interp(xs, [-L / 2, L / 2], [0.5, 0.36])
    ys = 0.15 * np.sin(xs * 0.6)
    prims = []
    for i in range(len(xs) - 1):
        prims.append(sdf.round_cone((xs[i], ys[i], zc[i]), (xs[i + 1], ys[i + 1], zc[i + 1]), rr[i], rr[i + 1], k=0.25))
    x0, z0 = xs[0], zc[0]
    # torn root plate (left)
    prims.append(sdf.ellipsoid((x0 - 0.35, ys[0], z0 + 0.6), (0.7, 1.8 if arch else 1.0, 2.1 if arch else 1.1), k=0.35))
    for k in range(16 if arch else 8):                       # root tendrils radiating out of the torn plate
        a = 2 * np.pi * k / (16 if arch else 8) + rng.normal(0, 0.2)
        dirr = normalize(np.array([-0.35, math.cos(a), math.sin(a) * 1.1]))
        b = np.array([x0 - 0.5, ys[0], z0 + 0.6]) + np.array([0, math.cos(a) * 1.4, math.sin(a) * 1.7]) * (1 if arch else 0.6)
        mid = b + dirr * rng.uniform(0.5, 0.9) + np.array([0, 0, -0.25])
        tip = mid + normalize(dirr + np.array([0, 0, -0.6])) * rng.uniform(0.5, 1.1)
        prims.append(sdf.round_cone(b, mid, 0.14, 0.08, k=0.12))
        prims.append(sdf.round_cone(mid, tip, 0.08, 0.04, k=0.06))
    for k in range(12 if arch else 7):
        a = rng.uniform(0, 2 * np.pi)
        d = normalize(np.array([-0.5 - 0.5 * rng.random(), math.cos(a) * 0.9, math.sin(a) * 0.9 + 0.2]))
        b = np.array([x0 - 0.2, ys[0], z0 + 0.3]) + np.array([0, math.cos(a), math.sin(a)]) * rr[0] * 0.9
        prims.append(sdf.round_cone(b, b + d * rng.uniform(0.8, 2.2) * (1 if arch else 0.6), 0.16, 0.03, k=0.12))
    # splintered, jagged broken end (right): long spikes continuing the log direction
    x1, z1 = xs[-1], zc[-1]
    for k in range(14):                                     # jagged splintered break (long sharp splinters)
        a = rng.uniform(0, 2 * np.pi)
        off = np.array([0, math.cos(a), math.sin(a)]) * rr[-1] * rng.uniform(0.15, 0.85)
        d = normalize(np.array([1.0, rng.normal(0, 0.3), rng.normal(0.2, 0.3)]))
        b = np.array([x1 - 0.4, ys[-1], z1]) + off
        prims.append(sdf.round_cone(b, b + d * rng.uniform(0.5, 1.8), rr[-1] * rng.uniform(0.18, 0.3), 0.015, k=0.05))
    for k in range(5):                                         # branch stubs
        x = rng.uniform(-L * 0.3, L * 0.4)
        zz, yy, rad = np.interp(x, xs, zc), np.interp(x, xs, ys), np.interp(x, xs, rr)
        a = rng.uniform(0.3, 2.8)
        d = normalize(np.array([0.5, math.cos(a), math.sin(a)]))
        b = np.array([x, yy, zz]) + d * rad * 0.6
        prims.append(sdf.round_cone(b, b + d * rng.uniform(0.5, 1.2), 0.17, 0.06, k=0.1))
    lo = np.array([-L / 2 - 3.0, -2.6, -0.6])
    hi = np.array([L / 2 + 2.0, 2.6, 4.6])
    F = sdf.Field(lo, hi, 0.07)
    F.union_all(prims)
    P = _grid(F)
    ridge = np.abs(np.sin(np.arctan2(P[..., 2] - 1.0, P[..., 1]) * 13 + P[..., 0] * 0.2
                          + 1.2 * texproj.fbm(P * np.array([0.3, 1.0, 1.0]), 1.0, 2, seed=variant + 3)))
    F.d = (F.d + 0.09 * ridge ** 0.55 + 0.10 * (texproj.fbm(P, 0.7, 3, seed=variant) - 0.5)
           + 0.03 * (texproj.fbm(P, 4.0, 2, seed=variant + 9) - 0.5)).astype(np.float32)
    F.d = np.maximum(F.d, -P[..., 2] - 0.25).astype(np.float32)
    F.smooth(0.6)
    bare = moss_dilate(F, 0.12, seed=variant + 20, up_lo=0.5, cover=0.42, freq=0.8)
    V, T = F.mesh()
    V, T = th.largest_components(V, T, min_frac=0.002)
    targets = {0: 2500, 1: 950, 2: 250}
    for lod in range(3):
        v, t, n = th.decimate_bpy(V, T, targets[lod])
        md = MeshData()
        k = 3
        ang = np.arctan2(v[:, 2] - np.interp(v[:, 0], xs, zc), v[:, 1] - np.interp(v[:, 0], xs, ys))
        U = (ang / (2 * np.pi) + 0.5) * k
        Vv = v[:, 0] / 1.6

        def uv_main(f, U=U, Vv=Vv, lod=lod):
            us = U[f].copy()
            if us.max() - us.min() > k * 0.5:
                us[us < k * 0.5] += k
            if lod > 0:
                u0, v0, u1, v1 = atlas.uv_rect("bark_hollow")
                return [(u0 + (u1 - u0) * ((us[j] / k) % 1.0 if np.ptp(us) < 0.9 * k else 0.5),
                         v0 + (v1 - v0) * ((Vv[f[j]] * 0.5) % 1.0 if np.ptp(Vv[f]) < 0.9 else 0.5)) for j in range(3)]
            return [(us[j], Vv[f[j]]) for j in range(3)]
        moss = split_moss(v, t, bare, F)
        mat_bark = 0 if lod == 0 else 1
        emit_split(md, v, t, moss, mat_bark if lod == 0 else 0, 1 if lod == 0 else 0, uv_main, rng)
        if lod == 0:
            anchors = []
            for j in range(6):
                x = rng.uniform(-2.8, 1.0)
                zz, yy, rad = np.interp(x, xs, zc), np.interp(x, xs, ys), np.interp(x, xs, rr)
                anchors.append((np.array([x, yy - rad * 0.95, zz + rng.uniform(-0.25, 0.1)]), (0, -1), rng.uniform(0.2, 0.32)))
            th.fungi(md, rng, anchors, 1, "tile")
        if lod < 2:
            moss_fringe(md, v, t, moss, rng, [26, 8][lod], (0.35, 0.6), mat=1 if lod == 0 else 0)
        if variant == 3 and lod < 2:
            _stream_bed(md, rng, L, lod)
        res.lods[lod] = md
        res.info[f"LOD{lod}"] = dict(tris=md.tris(), moss_faces=int(moss.sum()))
    if arch:
        res.info["arch_clearance_m"] = round(float(zc[6] - rr[6]), 2)
    return res


def _stream_bed(md, rng, L, lod):
    """Water strip (atlas water tile) across the log span + rocks/pebbles on the banks (rock material slot 2)."""
    u0, v0, u1, v1 = atlas.uv_rect("water")
    w, ln = 2.2, 6.0
    quad = np.array([[-w / 2, -ln / 2, -0.12], [w / 2, -ln / 2, -0.12], [w / 2, ln / 2, -0.12], [-w / 2, ln / 2, -0.12]])
    md.add(quad, [(0, 1, 2, 3)], [[(u0, v0), (u1, v0), (u1, v1), (u0, v1)]], 1 if lod == 0 else 0,
           np.ones((4, 4)), normals=np.tile([0, 0, 1.0], (4, 1)))
    for k in range([16, 0][lod]):
        side = rng.choice([-1, 1])
        p = np.array([side * rng.uniform(1.0, 2.2), rng.uniform(-2.6, 2.6), 0.0])
        pts, faces = _pebble(p, rng.uniform(0.18, 0.45), rng)
        md.add(pts, faces, [box_uv(pts)(np.array(f)) for f in faces], 2 if lod == 0 else 0, np.ones((len(pts), 4)))


# ============================================================================ bramble (open mound)

def build_bramble(variant):
    rng = np.random.default_rng(1700 + variant)
    res = gc._res(["foliage"], wind=True)
    W, H = {1: (3.4, 2.1), 2: (2.4, 1.6), 3: (3.0, 1.1)}[variant]
    canes = []
    for k in range({1: 30, 2: 22, 3: 24}[variant]):
        a = rng.uniform(0, 2 * np.pi)
        d = np.array([math.cos(a), math.sin(a) * 0.85, 0])
        base = d * rng.uniform(0.1, 0.8) * W * 0.32
        reach = rng.uniform(0.22, 0.42) * W
        top = rng.uniform(0.75, 1.15) * H
        pts = trees._bezier(base, base + d * reach * 0.3 + np.array([0, 0, top * 1.45]),
                            base + d * reach + np.array([0, 0, top * rng.uniform(0.0, 0.3)]), 9)
        canes.append((pts, rng.random()))
    rect = atlas.uv_rect("bramble_cane")
    for lod in range(3):
        md = MeshData()
        for pts, ph in canes[: [len(canes), len(canes) // 2, 8][lod]]:
            p = pts[:: [1, 2, 4][lod]]
            r = np.linspace(0.026, 0.012, len(p))
            sw = np.clip(p[:, 2] / H, 0, 1) * 0.8
            wind = np.stack([sw, np.zeros(len(p)), np.full(len(p), ph), np.full(len(p), 0.8)], -1)
            tg.tube(md, p, r, [4, 3, 3][lod], 0, wind, "atlas", atlas_rect=rect, cap_tip=False)
        n_cards = {0: 300, 1: 110, 2: 40}[lod]
        centre = np.array([0, 0, H * 0.4])
        for j in range(n_cards):
            pts, ph = canes[rng.integers(len(canes))]
            if rng.random() < 0.4:      # fill the mound
                q = rng.normal(0, 1, 3)
                q[2] = abs(q[2])
                q = normalize(q) * rng.uniform(0.3, 1.0) ** 0.5
                p = np.array([q[0] * W * 0.48, q[1] * W * 0.4, q[2] * H * 0.85])
            else:
                t = rng.uniform(0.25, 0.95)
                i = min(int(t * (len(pts) - 1)), len(pts) - 2)
                p = pts[i] + (pts[i + 1] - pts[i]) * rng.random()
            out = normalize(p - centre + rng.normal(0, 0.3, 3))
            n = normalize(out + np.array([0, 0, 0.5]))
            tile = ["bramble_a", "bramble_b"][rng.integers(2)] if lod < 2 else "bramble_dense"
            s = rng.uniform(0.42, 0.62) * [1.0, 1.35, 2.0][lod]
            upv = normalize(np.cross(n, rng.normal(0, 1, 3)))
            tg.card(md, p - upv * s * 0.5, n, upv, s, s, tile, 0, (min(1, p[2] / H), 0, ph), 0.62 + 0.38 * min(1, p[2] / H),
                    centre, sph=0.6, attach="center", flutter=(0.4, 0.9))
        res.lods[lod] = md
        res.info[f"LOD{lod}"] = dict(tris=md.tris())
    return res


# ============================================================================ fern rosette / reeds

def _frond(md, base, az, length, tile, rng, segs, elev, width, mat=0, ph=0.0, centre=None):
    """Arching pinnate frond: starts at `elev` rad above horizontal and bends down along its length."""
    u0, v0, u1, v1 = atlas.uv_rect(tile)
    d = np.array([math.cos(az), math.sin(az), 0])
    side = np.array([-d[1], d[0], 0])
    pts = [base]
    ang = elev
    seg = length / max(segs, 1)
    for k in range(segs):
        ang -= (elev * 0.75 + 0.35) / max(segs, 1)             # tangent rotates down along the frond
        pts.append(pts[-1] + (d * math.cos(ang) + np.array([0, 0, math.sin(ang)])) * seg)
    pts = np.array(pts)
    centre = base + np.array([0, 0, 0.2]) if centre is None else centre
    verts, uvs, cols, nrms = [], [], [], []
    for k, p in enumerate(pts):
        t = k / max(segs, 1)
        wk = width * (0.55 + 0.45 * math.sin(np.pi * min(1, 0.15 + t * 0.85)))
        for sgn in (-1, 1):
            v = p + side * sgn * wk * 0.5
            verts.append(v)
            uvs.append((u0 if sgn < 0 else u1, v0 + (v1 - v0) * t))
            cols.append([min(1, 0.15 + 0.85 * t), 0.3 + 0.7 * t, ph, 0.62 + 0.38 * t])
            nrms.append(normalize(0.7 * normalize(v - centre) + 0.3 * np.array([0, 0, 1.0])))
    faces, fuv = [], []
    for k in range(segs):
        a = 2 * k
        faces.append((a, a + 1, a + 3, a + 2))
        fuv.append([uvs[a], uvs[a + 1], uvs[a + 3], uvs[a + 2]])
    md.add(np.array(verts), faces, fuv, mat, np.array(cols), normals=np.array(nrms))


def build_reed_fern(kind, variant):
    rng = np.random.default_rng(1800 + 10 * variant + {"reed": 0, "fern": 3, "mixed": 6}[kind])
    if kind == "reed":
        return gc.build_reed_fern("reed", variant)
    res = gc._res(["foliage"], wind=True)
    base_res = gc.build_reed_fern("reed", 1) if kind == "mixed" else None
    for lod in range(3):
        md = MeshData()
        if base_res is not None:
            md.merge(base_res.lods[lod])
        nf = [13, 9, 6][lod] if kind == "fern" else [10, 7, 5][lod]
        cx = 0.75 if kind == "mixed" else 0.0
        L = (1.0 if variant == 1 else 0.8) * (1.75 if kind == "mixed" else 1.0)
        centre = np.array([cx, 0, 0.25])
        for j in range(nf):
            az = 2 * np.pi * j / nf + rng.normal(0, 0.2)
            tile = ["fern_frond_a", "fern_frond_b"][int(rng.random() < (0.35 if variant == 1 else 0.7))]
            _frond(md, np.array([cx, 0, 0.03]) + rng.normal(0, 0.05, 3) * np.array([1, 1, 0]), az,
                   L * rng.uniform(0.8, 1.15), tile, rng, [4, 2, 1][lod], rng.uniform(1.15, 1.4),
                   L * rng.uniform(0.26, 0.34) * [1, 1.15, 1.3][lod], ph=rng.random(), centre=centre)
        res.lods[lod] = md
        res.info[f"LOD{lod}"] = dict(tris=md.tris())
    return res
