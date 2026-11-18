"""Ground cover & features (art/02 bottom row): fallen trunk, moss rocks, bramble, reed/fern, scatter.

Each builder returns trees.Result with lods {0,1,2: MeshData}; `res.mats` names the material
slots ("bark:<kind>", "rock", "foliage"); `res.wind` False for static assets (no COLOR_0 export).
"""
import math
import numpy as np

import atlas
import treegen as tg
from treegen import MeshData, normalize
import trees
import trees_hollow as th

import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from frlib import sdf, texproj  # noqa: E402


def _res(mats, wind):
    r = trees.Result()
    r.mats = mats
    r.wind = wind
    return r


def _sdf_mesh(prims, lo, hi, voxel, extra=None, smooth=0.6):
    F = sdf.Field(lo, hi, voxel)
    for p in prims:
        F.apply(p)
    if extra is not None:
        F.d = extra(F).astype(np.float32)
    F.smooth(smooth)
    return F.mesh()


def _planar_uvs(V, T, tile, mode="tile", rect=None, axis_uv=None):
    """Per-face planar projection along the dominant normal axis (box mapping) for tiling textures."""
    fn = normalize(np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]))
    uvs = []
    for f, n in zip(T, fn):
        ax = int(np.argmax(np.abs(n)))
        if ax == 2:
            uv = [(V[i, 0] / tile, V[i, 1] / tile) for i in f]
        elif ax == 1:
            uv = [(V[i, 0] / tile, V[i, 2] / tile) for i in f]
        else:
            uv = [(V[i, 1] / tile, V[i, 2] / tile) for i in f]
        uvs.append(uv)
    return uvs, fn


def _cards_on_surface(md, V, T, fn, rng, n, tiles, size, mat, zmin=-1.0, up_min=0.6, lift=0.03, wind=False,
                      flat=True):
    """Moss/shrub cards on upward-facing triangles (area weighted)."""
    up = fn[:, 2]
    a = 0.5 * np.linalg.norm(np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]), axis=1)
    w = a * (up > up_min) * (V[T].mean(1)[:, 2] > zmin)
    if w.sum() <= 0:
        return
    pick = rng.choice(len(T), size=n, p=w / w.sum())
    for f in pick:
        b = rng.dirichlet([1, 1, 1])
        p = (V[T[f]] * b[:, None]).sum(0)
        nn = fn[f]
        s = rng.uniform(*size)
        tile = tiles[rng.integers(len(tiles))]
        if flat:
            nrm = normalize(nn + rng.normal(0, 0.1, 3))
            upv = normalize(np.cross(nrm, rng.normal(0, 1, 3)))
            c = p + nrm * lift - upv * s * 0.5
            att = "center"
        else:
            nrm = normalize(np.array([rng.normal(), rng.normal(), 0.25]))
            upv = np.array([0, 0, 1.0])
            c = p - nrm * 0.05
            att = atlas.LAYOUT[tile]["attach"]
        tg.card(md, c, nrm, upv, s, s, tile, mat, (0.15 if wind else 0.0, 0, rng.random()), 0.85, p - nn,
                sph=0.3, attach=att, flutter=(0.2, 0.6) if wind else (0, 0), up_bias=0.2)


# ============================================================================ fallen trunk

def build_fallen_trunk(variant):
    """v1: art/02 arching log over a stream (10 m, splintered root end); v2: straight log on the ground."""
    rng = np.random.default_rng(500 + variant)
    res = _res(["bark:hollow", "foliage"], wind=False)
    L = 10.0 if variant == 1 else 7.5
    xs = np.linspace(-L / 2, L / 2, 11)
    if variant == 1:
        # art/02: ~1.3 m thick log arching ~1.4 m above the stream bed, root end resting on the bank
        zc = 0.75 + 1.2 * np.sin(np.pi * (xs + L / 2) / L) ** 1.1
        rr = np.interp(xs, [-L / 2, -L / 2 + 1.5, L / 2 - 1.5, L / 2], [0.78, 0.66, 0.56, 0.42])
    else:
        zc = 0.42 + 0.02 * xs
        rr = np.interp(xs, [-L / 2, L / 2], [0.48, 0.32])
    ys = 0.15 * np.sin(xs * 0.6)
    prims = []
    for i in range(len(xs) - 1):
        prims.append(sdf.round_cone((xs[i], ys[i], zc[i]), (xs[i + 1], ys[i + 1], zc[i + 1]), rr[i], rr[i + 1], k=0.25))
    # splintered root end: spikes
    x0, z0 = xs[0], zc[0]
    for k in range(10 if variant == 1 else 6):
        a = rng.uniform(0, 2 * np.pi)
        d = normalize(np.array([-0.35 - 0.4 * rng.random(), math.cos(a) * 0.6, math.sin(a) * 0.5 + 1.1]))
        ln = rng.uniform(1.2, 2.8) * (1.0 if variant == 1 else 0.55)
        b = np.array([x0, ys[0], z0]) + np.array([0, math.cos(a), math.sin(a)]) * rr[0] * 0.55
        prims.append(sdf.round_cone(b, b + d * ln, rr[0] * 0.35, 0.03, k=0.15))
    # branch stubs along the log
    for k in range(4):
        x = rng.uniform(-L * 0.25, L * 0.45)
        i = np.searchsorted(xs, x)
        zz, yy = np.interp(x, xs, zc), np.interp(x, xs, ys)
        rad = np.interp(x, xs, rr)
        a = rng.uniform(0.3, 2.8)
        d = normalize(np.array([0.5, math.cos(a), math.sin(a)]))
        b = np.array([x, yy, zz]) + d * rad * 0.6
        prims.append(sdf.round_cone(b, b + d * rng.uniform(0.6, 1.4), 0.16, 0.05, k=0.1))
    lo = np.array([-L / 2 - 3.0, -2.6, -0.6])
    hi = np.array([L / 2 + 2.0, 2.6, 4.6])

    def extra(F):
        P = np.stack(np.meshgrid(*F.axes, indexing="ij"), -1)
        ridge = np.abs(np.sin(np.arctan2(P[..., 2] - 0.8, P[..., 1]) * 9 + P[..., 0] * 0.15))
        return F.d + 0.05 * ridge ** 0.6 + 0.10 * (texproj.fbm(P, 0.7, 3, seed=variant) - 0.5) \
            if True else F.d
    V, T = _sdf_mesh(prims, lo, hi, 0.07, extra=extra)
    V = V[:, :]
    keep_lo = -0.25
    targets = {0: 2300, 1: 900, 2: 240}
    for lod in range(3):
        v, t, n = th.decimate_bpy(V, T, targets[lod])
        md = MeshData()
        # cylindrical UV around the log axis (X)
        k = 3
        ang = np.arctan2(v[:, 2] - np.interp(v[:, 0], xs, zc), v[:, 1] - np.interp(v[:, 0], xs, ys))
        U = (ang / (2 * np.pi) + 0.5) * k
        Vv = v[:, 0] / 1.6
        faces, uvs = [], []
        for f in t:
            us = U[f].copy()
            if us.max() - us.min() > k * 0.5:
                us[us < k * 0.5] += k
            if lod > 0:
                u0, v0, u1, v1 = atlas.uv_rect("bark_hollow")
                uvs.append([(u0 + (u1 - u0) * ((us[j] / k) % 1.0 if us.max() - us.min() < 0.9 * k else 0.5),
                             v0 + (v1 - v0) * ((Vv[f[j]] * 0.5) % 1.0 if np.ptp(Vv[f]) < 0.9 else 0.5)) for j in range(3)])
            else:
                uvs.append([(us[j], Vv[f[j]]) for j in range(3)])
            faces.append(tuple(int(i) for i in f))
        col = np.zeros((len(v), 4))
        col[:, 3] = 1.0
        md.add(v, faces, uvs, 0, col)
        fn = normalize(np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]]))
        fmat = 1 if lod == 0 else 0
        _cards_on_surface(md, v, t, fn, rng, [90, 30, 10][lod], ["moss_clump"], (0.9, 1.5) if lod == 0 else (1.4, 2.2),
                          fmat, up_min=0.6, lift=0.02)
        if lod == 0:
            anchors = []
            for j in range(5):
                x = rng.uniform(-2.5, 1.0)
                zz, yy, rad = np.interp(x, xs, zc), np.interp(x, xs, ys), np.interp(x, xs, rr)
                anchors.append((np.array([x, yy - rad * 0.95, zz + rng.uniform(-0.25, 0.15)]), (0, -1), rng.uniform(0.18, 0.3)))
            th.fungi(md, rng, anchors, 1, "tile")
            _cards_on_surface(md, v, t, fn, rng, 18, ["grass_a", "grass_b"], (0.5, 0.8), 1, up_min=0.3, zmin=-0.3,
                              flat=False) if variant == 2 else None
        res.lods[lod] = md
        res.info[f"LOD{lod}"] = dict(tris=md.tris())
    if variant == 1:
        res.info["arch_clearance_m"] = round(float(zc[5] - rr[5]), 2)
    return res


# ============================================================================ moss rock (limestone outcrop)

def build_moss_rock(variant):
    """v1: art/02 stepped limestone outcrop (~10 x 6 x 5.4 m); v2: medium boulder group; v3: small rock."""
    rng = np.random.default_rng(600 + variant)
    res = _res(["rock", "foliage"], wind=False)
    prims = []
    if variant == 1:
        blocks = [((-0.7, 0.2, 2.6), (2.9, 1.9, 1.55), (0.05, -0.34, 0.08)),  # big slab, top rising to the right
                  ((3.0, 0.3, 1.0), (2.0, 2.0, 1.05), (0.0, 0.08, 0.1)),        # lower right terrace
                  ((-3.7, 0.5, 0.8), (1.2, 1.4, 0.85), (0.0, 0.0, -0.1)),
                  ((0.4, -1.7, 0.5), (2.8, 0.9, 0.55), (0.0, 0.0, 0.05)),
                  ((4.2, -1.1, 0.6), (1.0, 1.0, 0.65), (0.0, 0.05, -0.1))]
        size = (11, 6, 6)
    elif variant == 2:
        blocks = [((0, 0, 0.95), (1.4, 1.1, 0.95), (0.1, 0.0, 0.25)), ((1.6, 0.6, 0.55), (0.9, 0.8, 0.55), (0, 0.1, -0.2)),
                  ((-1.3, -0.5, 0.45), (0.7, 0.7, 0.45), (0, 0, 0.4))]
        size = (6, 5, 3)
    else:
        blocks = [((0, 0, 0.45), (0.8, 0.6, 0.5), (0.05, 0.08, 0.3))]
        size = (3, 3, 2)
    for c, h, r in blocks:
        prims.append(sdf.box(c, h, rot=np.array(r) * np.array([1, 1, 1]), rounding=min(h) * 0.35, k=0.25))
    lo = np.array([-size[0] / 2 - 1, -size[1] / 2 - 1, -0.6])
    hi = np.array([size[0] / 2 + 1, size[1] / 2 + 1, size[2]])
    vox = 0.08 if variant == 1 else 0.05

    def extra(F):
        P = np.stack(np.meshgrid(*F.axes, indexing="ij"), -1)
        d = F.d
        # fractures: thin vertical / horizontal slab cuts
        f1, f2 = texproj.voronoi(P * np.array([1.0, 1.0, 1.6]), 0.55, seed=variant)
        crack = np.clip(0.06 - (f2 - f1), 0, None) * 2.2
        d = d + crack
        d = d + 0.10 * (texproj.fbm(P, 0.9, 3, seed=variant + 3) - 0.5)
        d = np.maximum(d, -P[..., 2] - 0.3)
        return d
    V, T = _sdf_mesh(prims, lo, hi, vox, extra=extra, smooth=0.5)
    targets = {1: (2600, 1000, 280), 2: (1500, 600, 200), 3: (700, 280, 90)}[variant]
    for lod in range(3):
        v, t, n = th.decimate_bpy(V, T, targets[lod])
        md = MeshData()
        if lod == 0:
            uvs, fn = _planar_uvs(v, t, 2.0)
        else:
            uvs0, fn = _planar_uvs(v, t, 2.0)
            u0, v0, u1, v1 = atlas.uv_rect("bark_hollow")
            uvs = uvs0
        col = np.zeros((len(v), 4))
        col[:, 3] = 1.0
        md.add(v, [tuple(int(i) for i in f) for f in t], uvs, 0, col)
        fmat = 1
        moss_n = {1: [170, 60, 16], 2: [70, 26, 8], 3: [26, 9, 3]}[variant][lod]
        msz = {1: [(1.6, 2.6), (2.4, 3.4), (3.2, 4.2)], 2: [(1.0, 1.6), (1.5, 2.2), (2.0, 2.8)],
               3: [(0.6, 1.0), (0.9, 1.4), (1.2, 1.8)]}[variant][lod]
        _cards_on_surface(md, v, t, fn, rng, moss_n, ["moss_clump"], msz, fmat, up_min=0.5, lift=0.02)
        if lod < 2:
            shrub = {1: [44, 14], 2: [16, 6], 3: [6, 2]}[variant][lod]
            ssz = {1: (0.9, 1.6), 2: (0.7, 1.2), 3: (0.5, 0.8)}[variant]
            _cards_on_surface(md, v, t, fn, rng, shrub, ["shrub_orange", "shrub_orange", "grass_a", "grass_b"] if lod == 0
                              else ["shrub_dense"], ssz, fmat, up_min=0.35, flat=False)
        res.lods[lod] = md
        res.info[f"LOD{lod}"] = dict(tris=md.tris())
    return res


# ============================================================================ bramble

def build_bramble(variant):
    """Arching thorny canes (atlas cane strip) with leaf+berry cards. v1 3.4 m, v2 2.4 m, v3 low spreading."""
    rng = np.random.default_rng(700 + variant)
    res = _res(["foliage"], wind=True)
    W, H = {1: (3.4, 2.0), 2: (2.4, 1.5), 3: (3.0, 1.0)}[variant]
    canes = []
    for k in range({1: 36, 2: 26, 3: 28}[variant]):
        a = rng.uniform(0, 2 * np.pi)
        d = np.array([math.cos(a), math.sin(a) * 0.8, 0])
        base = d * rng.uniform(0, 0.35) * W * 0.3
        reach = rng.uniform(0.35, 0.62) * W
        top = rng.uniform(0.75, 1.15) * H
        pts = trees._bezier(base, base + d * reach * 0.3 + np.array([0, 0, top * 1.35]), base + d * reach +
                            np.array([0, 0, top * rng.uniform(0.25, 0.7)]), 7)
        canes.append((pts, rng.random()))
    rect = atlas.uv_rect("bramble_cane")
    for lod in range(3):
        md = MeshData()
        for pts, ph in canes[: [len(canes), len(canes) // 2, 6][lod]]:
            p = pts[:: [1, 2, 3][lod]]
            r = np.linspace(0.035, 0.014, len(p))
            sw = np.clip(p[:, 2] / H, 0, 1) * 0.8
            wind = np.stack([sw, np.zeros(len(p)), np.full(len(p), ph), np.full(len(p), 0.85)], -1)
            tg.tube(md, p, r, 3, 0, wind, "atlas", atlas_rect=rect, cap_tip=False)
        n_cards = {0: 230, 1: 110, 2: 45}[lod]
        centre = np.array([0, 0, H * 0.45])
        for j in range(n_cards):
            pts, ph = canes[rng.integers(len(canes))]
            t = rng.uniform(0.1, 0.8) if lod == 0 else rng.uniform(0.15, 0.85)
            i = min(int(t * (len(pts) - 1)), len(pts) - 2)
            p = pts[i] + (pts[i + 1] - pts[i]) * rng.random()
            out = normalize(p - centre + rng.normal(0, 0.3, 3))
            n = normalize(out + np.array([0, 0, 0.5]))
            tile = ["bramble_a", "bramble_b"][rng.integers(2)] if lod < 2 else "bramble_dense"
            s = rng.uniform(0.38, 0.62) * [1.0, 1.4, 2.2][lod]
            upv = normalize(np.cross(n, rng.normal(0, 1, 3)))
            tg.card(md, p - upv * s * 0.5, n, upv, s, s, tile, 0, (min(1, p[2] / H), 0, ph), 0.6 + 0.4 * min(1, p[2] / H),
                    centre, sph=0.5, attach="center", flutter=(0.4, 0.9))
        res.lods[lod] = md
        res.info[f"LOD{lod}"] = dict(tris=md.tris())
    return res


# ============================================================================ reeds / ferns

def _frond(md, base, az, length, tile, rng, segs, droop, width, mat=0, ph=0.0):
    """Curved frond strip: rises then arches outward/down (fern) — atlas tile mapped along the strip."""
    u0, v0, u1, v1 = atlas.uv_rect(tile)
    d = np.array([math.cos(az), math.sin(az), 0])
    side = np.array([-d[1], d[0], 0])
    pts = []
    for k in range(segs + 1):
        t = k / segs
        pts.append(base + d * length * 0.75 * (0.2 + 0.8 * t) * t + np.array([0, 0, length * (1.15 * t - droop * t * t)]))
    verts, uvs, cols, nrms = [], [], [], []
    for k, p in enumerate(pts):
        t = k / segs
        for sgn in (-1, 1):
            verts.append(p + side * sgn * width * 0.5)
            uvs.append((u0 if sgn < 0 else u1, v0 + (v1 - v0) * t))
            cols.append([min(1, 0.2 + 0.8 * t), 0.3 + 0.7 * t, ph, 0.7 + 0.3 * t])
            tang = normalize(pts[min(k + 1, segs)] - pts[max(k - 1, 0)])
            nrms.append(normalize(np.cross(tang, side) * -1 + np.array([0, 0, 0.6])))
    faces, fuv = [], []
    for k in range(segs):
        a = 2 * k
        faces.append((a, a + 1, a + 3, a + 2))
        fuv.append([uvs[a], uvs[a + 1], uvs[a + 3], uvs[a + 2]])
    md.add(np.array(verts), faces, fuv, mat, np.array(cols), normals=np.array(nrms))


def build_reed_fern(kind, variant):
    """kind 'reed' (blades + cattails), 'fern' (arching fronds), 'mixed' (art/02 patch)."""
    rng = np.random.default_rng(800 + 10 * variant + {"reed": 0, "fern": 3, "mixed": 6}[kind])
    res = _res(["foliage"], wind=True)
    for lod in range(3):
        md = MeshData()
        if kind in ("reed", "mixed"):
            H = 2.2 if variant == 1 else 1.6
            n_cards = [34, 12, 4][lod]
            cx = -0.6 if kind == "mixed" else 0.0
            for j in range(n_cards):
                az = rng.uniform(0, np.pi)
                p = np.array([cx + rng.normal(0, 0.5), rng.normal(0, 0.4), -0.05])
                n = np.array([math.cos(az), math.sin(az), 0.0])
                tile = ["reed_blades_a", "reed_blades_b"][rng.integers(2)] if lod < 2 else "reed_dense"
                w = rng.uniform(0.8, 1.2) * [1, 1.4, 2.0][lod]
                h = H * rng.uniform(0.8, 1.05)
                tg.card(md, p, n, np.array([0, 0, 1.0]), w, h, tile, 0, (1.0, 0, rng.random()), 0.8, p + np.array([0, 0, 1]),
                        sph=0.2, attach="bottom", flutter=(0.0, 0.9), up_bias=0.3)
            if lod < 2:
                rect = atlas.uv_rect("cattail")
                srect = atlas.uv_rect("reed_stem")
                for j in range([11, 5][lod]):
                    p = np.array([cx + rng.normal(0, 0.3), rng.normal(0, 0.25), 0.0])
                    hh = H * rng.uniform(0.9, 1.2)
                    lean = rng.normal(0, 0.06, 2)
                    top = p + np.array([lean[0] * hh, lean[1] * hh, hh])
                    ph = rng.random()
                    stem = np.array([p, (p + top) / 2, top])
                    wind = np.array([[0, 0, ph, 0.8], [0.5, 0, ph, 0.9], [1.0, 0, ph, 1.0]])
                    tg.tube(md, stem, np.array([0.012, 0.01, 0.008]), 3, 0, wind, "atlas", atlas_rect=srect, cap_tip=False)
                    head = np.array([top - np.array([0, 0, 0.32]), top - np.array([0, 0, 0.02])])
                    tg.tube(md, head, np.array([0.035, 0.03]), [6, 4][lod], 0, np.array([[1, 0, ph, 1], [1, 0, ph, 1]]),
                            "atlas", atlas_rect=rect, cap_tip=True)
        if kind in ("fern", "mixed"):
            nf = {"fern": 13, "mixed": 9}[kind] if lod == 0 else {"fern": 9, "mixed": 6}[kind] if lod == 1 else 5
            cx = 0.7 if kind == "mixed" else 0.0
            L = 1.8 if variant == 1 else 1.3
            for j in range(nf):
                az = 2 * np.pi * j / nf + rng.normal(0, 0.2)
                tile = ["fern_frond_a", "fern_frond_b"][int(rng.random() < (0.35 if variant == 1 else 0.7))]
                if lod == 2:
                    tile = "fern_frond_a"
                _frond(md, np.array([cx, 0, 0.02]) + rng.normal(0, 0.05, 3) * np.array([1, 1, 0]), az,
                       L * rng.uniform(0.8, 1.15), tile, rng, [3, 2, 1][lod], rng.uniform(0.35, 0.6),
                       rng.uniform(0.55, 0.72), ph=rng.random())
        res.lods[lod] = md
        res.info[f"LOD{lod}"] = dict(tris=md.tris())
    return res


# ============================================================================ scatter

def build_grass_tuft(variant):
    rng = np.random.default_rng(900 + variant)
    res = _res(["foliage"], wind=True)
    for lod in range(3):
        md = MeshData()
        n = [5, 3, 2][lod]
        for j in range(n):
            az = np.pi * j / n + rng.normal(0, 0.15)
            p = np.array([rng.normal(0, 0.08), rng.normal(0, 0.08), -0.03])
            h = rng.uniform(0.45, 0.7) * (1.3 if variant == 3 else 1.0)
            tile = ["grass_a", "grass_b", "grass_dense"][variant - 1]
            tg.card(md, p, np.array([math.cos(az), math.sin(az), 0]), np.array([0, 0, 1.0]), h * 1.1, h, tile, 0,
                    (1.0, 0, rng.random()), 0.85, p + np.array([0, 0, 1]), sph=0.3, attach="bottom", flutter=(0, 0.9))
        res.lods[lod] = md
        res.info[f"LOD{lod}"] = dict(tris=md.tris())
    return res


def build_fallen_branches(variant):
    rng = np.random.default_rng(950 + variant)
    res = _res(["foliage"], wind=False)
    rect = atlas.uv_rect("bark_oak")
    for lod in range(3):
        md = MeshData()
        nb = [4, 3, 2][lod] if variant == 1 else [3, 2, 1][lod]
        for j in range(nb):
            a = rng.uniform(0, np.pi)
            L = rng.uniform(1.4, 2.6)
            d = np.array([math.cos(a), math.sin(a), 0])
            p0 = rng.normal(0, 0.4, 3) * np.array([1, 1, 0])
            pts = np.array([p0 + d * L * t + np.array([0, 0, 0.06 + 0.05 * math.sin(t * 3)]) for t in np.linspace(0, 1, [4, 3, 2][lod])])
            r = np.linspace(0.07, 0.03, len(pts))
            w = np.zeros((len(pts), 4))
            w[:, 3] = 0.9
            tg.tube(md, pts, r, [5, 4, 3][lod], 0, w, "atlas", atlas_rect=rect)
            if lod < 2:
                for k in range(2):
                    t = rng.uniform(0.3, 0.8)
                    b = p0 + d * L * t + np.array([0, 0, 0.06])
                    dd = normalize(d + np.array([-d[1], d[0], 0]) * rng.choice([-1, 1]) * 0.8 + np.array([0, 0, 0.3]))
                    tg.tube(md, np.array([b, b + dd * rng.uniform(0.3, 0.6)]), np.array([0.025, 0.01]), 3, 0, w[:2], "atlas",
                            atlas_rect=rect)
        nl = [10, 4, 2][lod]
        for k in range(nl):
            p = rng.normal(0, 0.7, 3) * np.array([1, 1, 0]) + np.array([0, 0, 0.02])
            s = rng.uniform(0.5, 0.9)
            tg.card(md, p, np.array([0, 0, 1.0]), normalize(np.array([rng.normal(), rng.normal(), 0])), s, s, "leaf_litter", 0,
                    (0, 0, 0), 0.9, p - np.array([0, 0, 1]), sph=0.0, attach="center", flutter=(0, 0))
        res.lods[lod] = md
        res.info[f"LOD{lod}"] = dict(tris=md.tris())
    return res


def build_mushrooms(variant):
    rng = np.random.default_rng(980 + variant)
    res = _res(["foliage"], wind=False)
    u0, v0, u1, v1 = atlas.uv_rect("mushroom")
    vm = (v0 + v1) / 2
    for lod in range(3):
        md = MeshData()
        n = [7, 4, 2][lod] if variant == 1 else [5, 3, 1][lod]
        segs = [8, 6, 4][lod]
        for j in range(n):
            p = rng.normal(0, 0.18, 3) * np.array([1, 1, 0])
            h = rng.uniform(0.08, 0.22) * (1.6 if variant == 2 else 1.0)
            rc = h * rng.uniform(0.55, 0.9)
            verts, faces, uvs = [], [], []
            ring = []
            # stem (cylinder) + cap (cone-ish dome)
            for k in range(segs):
                a = 2 * np.pi * k / segs
                ring.append((math.cos(a), math.sin(a)))
            ring = np.array(ring)
            base = len(verts)
            for z, r in ((0.0, rc * 0.22), (h * 0.85, rc * 0.18)):
                for c in ring:
                    verts.append(p + np.array([c[0] * r, c[1] * r, z]))
            for k in range(segs):
                a, b = k, (k + 1) % segs
                faces.append((a, b, segs + b, segs + a))
                uvs.append([(u0 + (u1 - u0) * k / segs, v0), (u0 + (u1 - u0) * (k + 1) / segs, v0),
                            (u0 + (u1 - u0) * (k + 1) / segs, vm - 0.002), (u0 + (u1 - u0) * k / segs, vm - 0.002)])
            cb = len(verts)
            for c in ring:
                verts.append(p + np.array([c[0] * rc, c[1] * rc, h * 0.78]))
            top = len(verts)
            verts.append(p + np.array([0, 0, h * 1.12]))
            for k in range(segs):
                a, b = cb + k, cb + (k + 1) % segs
                faces.append((a, b, top))
                uvs.append([(u0 + (u1 - u0) * k / segs, vm + 0.002), (u0 + (u1 - u0) * (k + 1) / segs, vm + 0.002),
                            ((u0 + u1) / 2, v1)])
                faces.append((b, a, segs + (k + 1) % segs, ) if False else (b, a, base + segs + k))
                uvs.append([(u0, vm + 0.002), (u1, vm + 0.002), ((u0 + u1) / 2, vm + 0.01)])
            col = np.zeros((len(verts), 4))
            col[:, 3] = 0.9
            md.add(np.array(verts), faces, uvs, 0, col)
        res.lods[lod] = md
        res.info[f"LOD{lod}"] = dict(tris=md.tris())
    return res
