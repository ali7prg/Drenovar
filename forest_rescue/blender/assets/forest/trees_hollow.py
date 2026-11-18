"""Hero hollow oak (art/02, 4th tree): SDF trunk with walk-through arch + tube limbs + sparse foliage.

Trunk: stacked ellipses fitted to the reference silhouette (centre/half-width per height), vertical
bark ridges + gnarl noise, 8 buttress roots, smooth leader stubs; minus an arch tunnel along Y
(clear doorway ≥1.6 m wide, ≥3.0 m high) and an inner cavity.  Marching cubes -> Blender decimate
to the LOD budget -> per-face cylindrical / planar tiling UVs (bark) or atlas bark-strip UVs.
"""
import math
import numpy as np

import atlas
import treegen as tg
from treegen import MeshData, normalize
import trees

import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from frlib import sdf, texproj  # noqa: E402

# (z, centre x, half-width) measured on the art/02 silhouette (ppm 30, ground row 424)
PROFILE_V1 = [(-0.4, 0.6, 5.0), (0.0, 0.6, 4.9), (0.8, 0.65, 4.6), (1.4, 0.45, 4.0), (2.0, 0.45, 3.6),
              (2.6, 0.45, 3.4), (3.2, 0.4, 3.2), (3.8, 0.4, 3.05), (4.4, 0.7, 2.85), (5.0, 0.85, 2.7),
              (5.6, 0.95, 2.5), (6.2, 1.0, 2.25), (6.8, 1.0, 1.9), (7.2, 1.0, 1.4)]
ARCH = dict(x=0.9, w=1.7, h=3.1)            # clear walk-through opening (doorway), along Y
CAVITY = dict(c=(0.85, 0.0, 2.3), r=(1.55, 1.25, 2.6))


def trunk_sdf_mesh(profile, depth_k=0.72, arch=ARCH, cavity=CAVITY, voxel=0.1, seed=0, leaders=(), roots=8,
                   mirror=False, broken_top=None):
    prof = np.array(profile, float)
    if mirror:
        prof[:, 1] = -prof[:, 1]
        arch = dict(arch, x=-arch["x"])
        cavity = dict(cavity, c=(-cavity["c"][0], cavity["c"][1], cavity["c"][2]))
    zmax = prof[-1, 0]
    hwmax = prof[:, 2].max()
    lo = np.array([prof[:, 1].min() - hwmax - 1.5, -hwmax * depth_k - 1.5, -0.6])
    hi = np.array([prof[:, 1].max() + hwmax + 1.5, hwmax * depth_k + 1.5, zmax + 3.5])
    F = sdf.Field(lo, hi, voxel)
    rng = np.random.default_rng(seed)

    def body(Pt):
        x, y, z = Pt[..., 0], Pt[..., 1], Pt[..., 2]
        zc = np.clip(z, prof[0, 0], prof[-1, 0])
        cx = np.interp(zc, prof[:, 0], prof[:, 1])
        hw = np.interp(zc, prof[:, 0], prof[:, 2])
        ry = hw * depth_k
        th = np.arctan2(y, x - cx)
        q = np.sqrt(((x - cx) / hw) ** 2 + (y / ry) ** 2)
        d = (q - 1.0) * np.minimum(hw, ry)
        # vertical ridges, slowly twisting, + gnarls
        ridge = np.abs(np.sin(th * 7 + z * 0.35 + 1.5 * texproj.fbm(Pt * 0.35, 1.0, 3, seed=seed)))
        d += 0.26 * (ridge ** 0.55) - 0.13
        d += 0.30 * (texproj.fbm(Pt, 0.45, 3, seed=seed + 1) - 0.5)
        # cap the top smoothly
        d = np.maximum(d, z - zmax)
        return d.astype(np.float32)

    F.d = F.evaluate_full(body)
    prims = []
    for k in range(roots):
        th = 2 * np.pi * k / roots + rng.normal(0, 0.18)
        c0 = np.interp(0.8, prof[:, 0], prof[:, 1])
        hw0 = np.interp(0.8, prof[:, 0], prof[:, 2])
        a = np.array([c0 + 0.55 * hw0 * math.cos(th), 0.55 * hw0 * depth_k * math.sin(th), 1.6])
        b = np.array([c0 + (hw0 + rng.uniform(0.8, 1.8)) * math.cos(th),
                      (hw0 * depth_k + rng.uniform(0.8, 1.8)) * math.sin(th), -0.35])
        prims.append(sdf.round_cone(a, b, rng.uniform(0.75, 1.0), rng.uniform(0.22, 0.35), k=0.55))
    for (a, b, ra, rb) in leaders:
        a = np.array(a, float)
        b = np.array(b, float)
        if mirror:
            a[0], b[0] = -a[0], -b[0]
        prims.append(sdf.round_cone(a, b, ra, rb, k=0.6))
    for p in prims:
        F.apply(p)
    # arch tunnel (2D arch in XZ extruded along Y) and inner cavity
    ax, aw, ah = arch["x"], arch["w"], arch["h"]

    def tunnel(Pt):
        x, z = Pt[..., 0] - ax, Pt[..., 2]
        r = aw / 2
        zc = ah - r
        # rectangle below the spring line, half-disc above (round arch)
        dx = np.abs(x) - r
        rect = np.maximum(dx, np.maximum(z - zc, -0.8 - z))
        circ = np.sqrt(x ** 2 + (z - zc) ** 2) - r
        d = np.where(z > zc, circ, rect)
        d += 0.12 * (texproj.fbm(Pt, 0.8, 2, seed=seed + 5) - 0.5)
        return d.astype(np.float32)

    T = F.evaluate_full(tunnel)
    F.d = sdf.smax(F.d, -T, 0.18).astype(np.float32)
    cav = sdf.ellipsoid(cavity["c"], cavity["r"], k=0.35, op="subtract")
    F.apply(cav)
    if broken_top is not None:
        # jagged broken top: cut above a noisy plane
        z0 = broken_top

        def cut(Pt):
            return (Pt[..., 2] - (z0 + 0.8 * (texproj.fbm(Pt * np.array([1.6, 1.6, 0]), 0.9, 2, seed=seed + 9) - 0.5)
                                  + 0.6 * np.abs(np.sin(Pt[..., 0] * 2.1 + Pt[..., 1] * 1.3)))).astype(np.float32)
        F.d = sdf.smax(F.d, cut(np.stack(np.meshgrid(*F.axes, indexing="ij"), -1)), 0.1).astype(np.float32)
    F.d = np.maximum(F.d, (lo[2] + 0.25 + 0.15) - np.stack(np.meshgrid(*F.axes, indexing="ij"), -1)[..., 2]).astype(np.float32) \
        if False else F.d
    F.smooth(0.7)
    V, Fc = F.mesh()
    keep = V[:, 2] > -0.5
    return V, Fc, dict(arch=arch, cavity=cavity, prof=prof)


def decimate_bpy(V, Fc, target, name="tmp_trunk"):
    import bpy
    from frlib import core
    obj = core.mesh_object(name, V, Fc, smooth=True)
    core.decimate_to(obj, target, copy=False)
    v, t, _, n = core.mesh_arrays(obj, evaluated=False, world=False)
    bpy.data.objects.remove(obj, do_unlink=True)
    return v, t, n


def trunk_meshdata(md, V, T, N, mode, tile, info, mat=0, ao_c=None):
    """Per-face cylindrical (sides) / planar (tops) tiling UVs; COLOR_0 R=0 (static), A=cavity AO."""
    prof = info["prof"]
    cxz = lambda z: np.interp(np.clip(z, prof[0, 0], prof[-1, 0]), prof[:, 0], prof[:, 1])
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    fn = normalize(fn)
    cx = cxz(V[:, 2])
    th = np.arctan2(V[:, 1], V[:, 0] - cx)
    circ = 2 * np.pi * 3.0
    k = max(1, int(round(circ / tile[0])))
    U = (th / (2 * np.pi) + 0.5) * k
    Vv = V[:, 2] / tile[1]
    # AO: inward-facing normals (towards the trunk axis) and points inside the cavity are dark
    rad = normalize(np.stack([V[:, 0] - cx, V[:, 1], np.zeros(len(V))], -1))
    inward = np.clip(-(N * rad).sum(1), 0, 1)
    c = np.asarray(info["cavity"]["c"])
    r = np.asarray(info["cavity"]["r"])
    incav = np.clip(1.25 - np.linalg.norm((V - c) / (r * 1.25), axis=1), 0, 1)
    ao = np.clip(1.0 - 0.55 * inward - 0.35 * incav, 0.38, 1.0)
    ao *= 0.85 + 0.15 * np.clip(V[:, 2] / 6.0, 0, 1)
    col = np.zeros((len(V), 4))
    col[:, 3] = ao
    faces, uvs = [], []
    for f, n in zip(T, fn):
        if abs(n[2]) > 0.75:
            uv = [(V[i, 0] / tile[0], V[i, 1] / tile[1]) for i in f]
        else:
            us = U[f].copy()
            if us.max() - us.min() > k * 0.5:
                us[us < k * 0.5] += k
            uv = [(us[j], Vv[f[j]]) for j in range(3)]
        if mode == "atlas":
            u0, v0, u1, v1 = atlas.uv_rect("bark_hollow")
            uv = [(u0 + (u1 - u0) * ((a / max(k, 1)) % 1.0), v0 + (v1 - v0) * ((b * 0.5) % 1.0)) for a, b in uv]
            # avoid wrap discontinuity inside a face
            us = [p[0] for p in uv]
            if max(us) - min(us) > (u1 - u0) * 0.5:
                uv = [(u0 + 0.02 * (u1 - u0), p[1]) if p[0] < (u0 + u1) / 2 else (u0 + 0.02 * (u1 - u0), p[1]) for p in uv]
            vs = [p[1] for p in uv]
            if max(vs) - min(vs) > (v1 - v0) * 0.5:
                uv = [(p[0], v0 + 0.02 * (v1 - v0)) for p in uv]
        faces.append(tuple(int(i) for i in f))
        uvs.append(uv)
    md.add(V, faces, uvs, mat, col, normals=None)


def fungi(md, rng, anchors, mat, mode):
    """Bracket fungi: semicircular shelves (fan of 6 tris) mapped to the atlas fungus tile."""
    u0, v0, u1, v1 = atlas.uv_rect("fungus_bracket")
    for (p, outdir, size) in anchors:
        outdir = normalize(np.array([outdir[0], outdir[1], 0.0]))
        side = normalize(np.cross(np.array([0, 0, 1.0]), outdir))
        n = 7
        verts = [p + np.array([0, 0, 0.02])]
        uvs_v = [((u0 + u1) / 2, v1 - (v1 - v0) * 0.18)]
        for j in range(n):
            a = math.pi * j / (n - 1)
            q = p + (side * math.cos(a) * size + outdir * math.sin(a) * size * 0.8) + np.array([0, 0, -0.05 * math.sin(a)])
            verts.append(q)
            uvs_v.append(((u0 + u1) / 2 + (u1 - u0) * 0.48 * math.cos(a), v1 - (v1 - v0) * (0.18 + 0.75 * math.sin(a))))
        faces = [(0, j + 1, j + 2) for j in range(n - 1)]
        fuv = [[uvs_v[0], uvs_v[j + 1], uvs_v[j + 2]] for j in range(n - 1)]
        col = np.zeros((len(verts), 4))
        col[:, 3] = 0.85
        nrm = np.tile(normalize(np.array([0, 0, 1.0]) + outdir * 0.3), (len(verts), 1))
        md.add(np.array(verts), faces, fuv, mat, col, normals=nrm)


HOLLOW_MOODS = [(4, ["oak_orange_a", "oak_orange_b", "oak_rust_a"]), (3, ["oak_rust_a", "oak_rust_b", "oak_orange_a"]),
                (1, ["oak_amber_b", "oak_orange_a"])]


def build_hollow_oak(variant, view=None, budget=(6800, 2700, 300)):
    seed = {1: 141, 2: 252, 3: 363}[variant]
    rng = np.random.default_rng(seed)
    mirror = variant == 2
    sgn = -1.0 if mirror else 1.0
    leaders = [((-0.4, 0, 5.6), (-1.9, -0.2, 10.4), 1.2, 0.5), ((1.9, 0.1, 5.6), (3.2, 0.3, 11.0), 1.3, 0.55),
               ((2.4, 0.0, 5.2), (4.8, 0.2, 5.5), 0.75, 0.38), ((-0.8, 0.1, 6.4), (-3.4, 0.2, 7.6), 0.8, 0.4)]
    broken = None
    prof = PROFILE_V1
    if variant == 3:
        leaders = [((1.6, 0.1, 5.4), (2.4, 0.2, 7.6), 1.1, 0.7)]
        broken = 7.3
        prof = [(z, cx, hw * 0.92) for z, cx, hw in PROFILE_V1]
    V, T, tinfo = trunk_sdf_mesh(prof, seed=seed, leaders=leaders, mirror=mirror, broken_top=broken)
    # skeleton for limbs (tubes): seeded leaders continuing from the SDF stubs
    sk = tg.Skeleton()
    root = sk.add(np.array([sgn * 0.6, 0, 5.6]), -1, fixed=True, can_grow=False)
    if variant in (1, 2):
        limb_defs = [  # (start, mid, end)
            ((-1.4, -0.2, 8.6), (-2.0, -0.3, 10.6), (-2.2, -0.1, 12.6)),
            ((-0.9, 0.1, 7.2), (-3.0, 0.3, 7.6), (-4.8, 0.2, 8.4)),
            ((2.8, 0.3, 9.0), (3.3, 0.4, 11.6), (3.6, 0.2, 13.6)),
            ((3.0, 0.2, 7.6), (5.4, 0.3, 8.6), (8.2, 0.4, 9.6)),
            ((4.3, 0.2, 5.6), (5.3, 0.2, 5.4), (6.4, 0.2, 5.0)),
            ((1.2, 1.4, 7.4), (1.6, 3.2, 8.6), (2.0, 4.4, 9.8)),
            ((0.6, -1.4, 7.6), (0.8, -3.0, 8.8), (0.9, -4.4, 10.2)),
        ]
        att_env = tg.envelope_from_mask(view.mask, view.ppm, view.ay, view.ax, z_min=6.5, depth_scale=0.75,
                                        voxel=0.25, mirror=mirror)
    else:
        limb_defs = [((2.2, 0.2, 7.2), (3.6, 0.4, 8.6), (5.6, 0.6, 9.8)),
                     ((0.2, -0.3, 6.8), (-1.8, -0.4, 7.4), (-3.6, -0.2, 8.6)),
                     ((2.0, 0.6, 7.4), (2.4, 2.2, 8.8), (2.2, 3.4, 10.4))]
        att_env = tg.envelope_ellipsoid((sgn * 1.4, 0, 8.6), (5.0, 3.8, 2.4), voxel=0.25)
    for a, m, e in limb_defs:
        a, m, e = (np.array(p) * np.array([sgn, 1, 1]) for p in (a, m, e))
        pts = trees._bezier(a, m, e, 7)
        sk.add_polyline(list(pts), parent=root, can_grow_from_z=6.0)
    puffs = att_env.sample(18 if variant != 3 else 10, rng, shell=1.2)
    att = att_env.sample(900 if variant != 3 else 500, rng, shell=1.8, inner_weight=0.1, clumps=puffs, clump_r=1.6)
    tg.space_colonize(sk, att, D=0.42, di=2.6, dk=0.8, iters=90, tropism=(0, 0, 0.6), trop_w=0.15, rng=rng,
                      jitter=0.25)
    spec = dict(bark="hollow", r_base=0.75, r_tip=0.02, gamma=2.3, cull=(0.05, 0.14, 0.3), max_order=[9, 2, 1],
                flare=None, roots=None, card_size=(0.85, 1.2), moods=HOLLOW_MOODS, dense_map=trees.OAK_DENSE,
                dense_frac=0.35, dense_scale=1.2, puff_max_gap=1.3,
                leaf_tip_dist=1.2, leaf_r_max=0.08, site_spacing=0.5, side_frac=0.5, sph=0.6, up_bias=0.2,
                seed=seed, bark_tile=(1.6, 1.6), leaf_z_min=5.0, puffs=puffs, puff_r=(1.0, 1.6), puff_frac=0.75,
                skip_order0=True, bark_frac=(0.45, 0.35, 0.2))
    trunk_targets = {0: 3900, 1: 1350, 2: 170}
    if variant == 3:
        trunk_targets = {0: 3300, 1: 1150, 2: 170}
    spec["budget"] = tuple(budget[l] - trunk_targets[l] - (60 if l == 0 else 0) for l in range(3))
    res = trees.finish_broadleaf(sk, att_env, spec, rng)
    res.env = att_env
    # trunk per LOD
    for lod in range(3):
        v, t, n = decimate_bpy(V, T, trunk_targets[lod])
        md = MeshData()
        trunk_meshdata(md, v, t, n, "tile" if lod == 0 else "atlas", (2.4, 2.4), tinfo, mat=0)
        if lod == 0:
            anchors = []
            for j in range(7):
                z = 1.9 + 0.32 * j + rng.normal(0, 0.05)
                ang = math.pi + rng.normal(0, 0.25)
                if mirror:
                    ang = rng.normal(0, 0.25)
                cx = np.interp(z, tinfo["prof"][:, 0], tinfo["prof"][:, 1])
                hw = np.interp(z, tinfo["prof"][:, 0], tinfo["prof"][:, 2])
                p = np.array([cx + math.cos(ang) * hw * 0.98, math.sin(ang) * hw * 0.7, z])
                anchors.append((p, (math.cos(ang), math.sin(ang)), rng.uniform(0.38, 0.6)))
            fungi(md, rng, anchors, 1, "tile")
        md.merge(res.lods[lod])
        res.lods[lod] = md
        res.info[f"LOD{lod}"]["tris"] = md.tris()
        res.info[f"LOD{lod}"]["trunk_tris"] = len(t)
    res.info["arch_clear_m"] = {"width": ARCH["w"], "height": ARCH["h"], "x": float(tinfo["arch"]["x"])}
    return res
