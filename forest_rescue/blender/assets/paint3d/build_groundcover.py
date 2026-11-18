"""Ground cover on the new painted atlas: grass tufts (painted grass strips from art/02 bases), mushrooms
(painted bracket fungi of the hollow oak / fallen log), fallen branches (painted oak limbs from the art/02 golden oak
skeleton laid on the ground, tubes textured with their own projected oak bark).

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/paint3d/build_groundcover.py [--iter N]
"""
import argparse
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pblend  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from scipy import ndimage as ndi  # noqa: E402
from frlib import core, paths, render as frr  # noqa: E402

import geom  # noqa: E402
import p3atlas as atl  # noqa: E402
import seg  # noqa: E402
import tree  # noqa: E402
import species as SP  # noqa: E402
import build_tree as BT  # noqa: E402
import build_props as BPR  # noqa: E402

RT = os.path.join(paths.RUNTIME, "forest")
K = 0.35
GRASS_SRC = [(898, 676, 1226, 722), (1236, 388, 1300, 425), (1318, 384, 1365, 425)]
FUNGI_SRC = [(925, 295, 985, 345), (165, 635, 215, 670)]
PPM_GRASS = 60.0          # painted grass blades ~0.5-0.7 m


def tiles_from(boxes, sel_fn, mode, region, **kw):
    S = seg.sheet("02_forest_modular_kit.png")
    bg = seg.bg_colour(S)
    out = []
    for (x0, y0, x1, y1) in boxes:
        img = S[y0:y1, x0:x1].astype(np.float32)
        L = seg.lab(ndi.gaussian_filter(img, (0.6, 0.6, 0)))
        C = np.hypot(L[..., 1], L[..., 2])
        Hh = np.degrees(np.arctan2(L[..., 2], L[..., 1])) % 360
        m = sel_fn(L[..., 0], C, Hh)
        m = ndi.binary_opening(m, structure=np.ones((2, 1)))
        if mode == "strips":
            lbl = seg.strip_patches(img, m, width=kw.get("width", 10), max_h=200, min_px=kw.get("min_px", 40))
        else:
            lbl, n = ndi.label(ndi.binary_closing(m, iterations=1))
            ids, cnt = np.unique(lbl[lbl > 0], return_counts=True)
            for i, c in zip(ids, cnt):
                if c < kw.get("min_px", 40):
                    lbl[lbl == i] = 0
            lbl = seg.relabel(lbl)
        for i in range(1, int(lbl.max()) + 1):
            pm = lbl == i
            tile, rect = seg.make_tile(img, m | pm, pm, margin=2, scale=2, bg=bg)
            ys, xs = np.nonzero(pm)
            out.append(dict(tile=tile, w=rect[2] - rect[0], h=rect[3] - rect[1], area=int(pm.sum())))
    return out


def pack(tiles, key, sub=None):
    region = atl.REGIONS[key]
    rx, ry, rw, rh = region
    if sub is not None:      # (fx0, fx1) fraction of the region width
        rx, rw = rx + int(sub[0] * region[2]), int((sub[1] - sub[0]) * region[2])
    sizes = [(t["tile"].shape[1], t["tile"].shape[0]) for t in tiles]
    pos, s = seg.pack_rects(sizes, (0, 0, rw, rh), pad=3)
    img = np.zeros((rh, rw, 4), np.float32)
    import cv2
    for t, p in zip(tiles, pos):
        tl = t["tile"]
        if s < 0.999:
            tl = cv2.resize(tl, (max(1, int(np.ceil(tl.shape[1] * s))), max(1, int(np.ceil(tl.shape[0] * s)))),
                            interpolation=cv2.INTER_AREA)
        h, w = tl.shape[:2]
        img[p[1]:p[1] + h, p[0]:p[0] + w] = tl
        t["uv"] = atl.uv_rect((rx + p[0] + 0.5, ry + p[1] + 0.5, rx + p[0] + w - 0.5, ry + p[1] + h - 0.5))
    return img, s


def wind(V, top=0.6, phase=0.0, ao=1.0, flutter=0.6):
    C = np.zeros((len(V), 4))
    f = np.clip(V[:, 2] / max(top, 1e-3), 0, 1)
    C[:, 0] = f ** 1.4
    C[:, 1] = flutter * f
    C[:, 2] = phase
    C[:, 3] = ao
    return C


def tuft(tiles, n_cards, radius, h_scale, seed, ppm):
    rng = np.random.default_rng(seed)
    md = geom.Mesh()
    for k in range(n_cards):
        t = tiles[rng.integers(len(tiles))]
        w = t["w"] / ppm * h_scale
        h = t["h"] / ppm * h_scale
        rho = radius * math.sqrt(rng.random())
        phi = rng.uniform(0, 2 * math.pi)
        yaw = rng.uniform(0, math.pi)
        n = np.array([math.sin(yaw), -math.cos(yaw), 0.0])
        pos = np.array([rho * math.cos(phi), rho * math.sin(phi), -0.02])
        tilt = geom.nrm(np.array([0, 0, 1.0]) + rng.normal(0, 0.12, 3) * np.array([1, 1, 0]))
        V, T, UV, _, N = geom.free_card(pos, n, tilt, w, h, t["uv"], np.zeros(4), flip=bool(rng.random() < 0.5),
                                        pivot_v=0.0)
        md.add(V, T, UV, wind(V, top=h, phase=rng.random()), geom.nrm(N + np.array([0, 0, 0.6])), 1)
    return md


def mushrooms(tiles, n, radius, size_k, seed, segs=10):
    """Mushroom cluster: domed caps (painted fungus tile mapped top-down) on short pale stems (painted cap edge)."""
    rng = np.random.default_rng(seed)
    md = geom.Mesh()
    tiles = [t for t in tiles if t.get("cap")] or tiles
    for k in range(n):
        t = tiles[rng.integers(len(tiles))]
        u0, v0, u1, v1 = t["uv"]
        rc = rng.uniform(0.05, 0.11) * size_k
        hs = rng.uniform(0.07, 0.16) * size_k
        rho = radius * math.sqrt(rng.random())
        phi = rng.uniform(0, 2 * math.pi)
        c = np.array([rho * math.cos(phi), rho * math.sin(phi), 0.0])
        tilt = geom.nrm(np.array([0, 0, 1.0]) + rng.normal(0, 0.15, 3) * np.array([1, 1, 0]))
        # stem
        Ps = np.array([c, c + tilt * hs])
        V, T, UV, C, N = geom.tube(Ps, np.array([rc * 0.32, rc * 0.25]), max(4, segs // 2),
                                   (u0, v0, u0 + (u1 - u0) * 0.15, v0 + (v1 - v0) * 0.2), np.zeros(4))
        Cc = np.zeros((len(V), 4))
        Cc[:, 3] = 0.85
        md.add(V, T, UV, Cc, N, 1)
        # cap: spherical cap (dome), rings x segs, top-down planar UV into the painted tile
        top = c + tilt * hs
        rings = 3
        Vc, Uc, Nc = [top + tilt * rc * 0.55], [((u0 + u1) / 2, (v0 + v1) / 2)], [tilt]
        side = geom.nrm(np.cross(tilt, [1.0, 0, 0]) if abs(tilt[0]) < 0.9 else np.cross(tilt, [0, 1.0, 0]))
        side2 = np.cross(tilt, side)
        for ri in range(1, rings + 1):
            th = ri / rings * math.radians(80)
            for si in range(segs):
                ph = 2 * math.pi * si / segs
                d = math.sin(th) * (math.cos(ph) * side + math.sin(ph) * side2) + math.cos(th) * tilt
                Vc.append(top + d * np.array([rc, rc, rc * 0.55]) * 1.0 - tilt * rc * 0.0)
                Uc.append(((u0 + u1) / 2 + (u1 - u0) / 2 * math.sin(th) * math.cos(ph) * 0.95,
                           (v0 + v1) / 2 + (v1 - v0) / 2 * math.sin(th) * math.sin(ph) * 0.95))
                Nc.append(d)
        Tc = []
        for si in range(segs):
            Tc.append([0, 1 + si, 1 + (si + 1) % segs])
        for ri in range(1, rings):
            a0 = 1 + (ri - 1) * segs
            a1 = 1 + ri * segs
            for si in range(segs):
                p, q = si, (si + 1) % segs
                Tc += [[a0 + p, a1 + p, a1 + q], [a0 + p, a1 + q, a0 + q]]
        Vc = np.array(Vc)
        Cc = np.zeros((len(Vc), 4))
        Cc[:, 3] = 1.0
        md.add(Vc, np.array(Tc), np.array(Uc), Cc, np.array(Nc), 1)
    return md


def branches(limbs_px, ppm, uvs, ids, n, seed, bark_mat_index=0):
    """Painted oak limbs (2-D skeleton polylines + radii) laid on the ground as tapered tubes."""
    rng = np.random.default_rng(seed)
    md = geom.Mesh()
    order = rng.permutation(len(limbs_px))[:n]
    for j in order:
        P2, r2 = limbs_px[j]
        lid = ids[j]
        P2 = np.asarray(P2, float)
        L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P2, axis=0), axis=1))]
        if L[-1] < 8:
            continue
        x = (P2[:, 0] - P2[0, 0]) / ppm
        y = -(P2[:, 1] - P2[0, 1]) / ppm             # painted up -> ground plane forward
        yaw = rng.uniform(0, 2 * math.pi)
        c, s = math.cos(yaw), math.sin(yaw)
        X = x * c - y * s
        Y = x * s + y * c
        rr = np.maximum(np.minimum.accumulate(np.asarray(r2, float)) / ppm * 0.55, 0.012)
        Z = rr * 0.8 + 0.03 * np.sin(np.linspace(0, math.pi, len(X)))     # resting on the ground, slight arch
        P = np.stack([X, Y, Z], 1)
        P[:, :2] += rng.uniform(-0.8, 0.8, 2)
        Ps, ss = geom.resample_polyline(P, max(0.08, 2.5 * rr.mean()))
        rs = np.interp(ss, np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))], rr)
        if len(Ps) < 3:
            continue
        V, T, UV, C, N = geom.tube(Ps, rs, 5 if rs.max() > 0.03 else 4, uvs[lid], np.zeros(4))
        C = np.zeros((len(V), 4))
        C[:, 3] = 0.9
        md.add(V, T, UV, C, N, bark_mat_index)
    return md


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=int, default=1)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    t0 = time.time()
    grass = tiles_from(GRASS_SRC, lambda L, C, H: (C > 24) & (H > 80) & (H < 112) & (L > 36), "strips", "grass",
                       width=7, min_px=24)
    fungi = tiles_from(FUNGI_SRC, lambda L, C, H: (C > 22) & (H > 45) & (H < 75) & (L > 42), "blobs", "groundcover",
                       min_px=25)
    grass = sorted(grass, key=lambda t: -t["area"])[:28]
    fungi = sorted(fungi, key=lambda t: -t["area"])[:14]
    # cap tiles: painted fungus colours (pull-push bled RGB of each fungus tile) inside an opaque disc
    caps = []
    for t in fungi[:4]:
        tl = t["tile"].copy()
        h, w = tl.shape[:2]
        s_ = min(h, w)
        y0_, x0_ = (h - s_) // 2, (w - s_) // 2
        sq = tl[y0_:y0_ + s_, x0_:x0_ + s_].copy()
        yy, xx = np.mgrid[0:s_, 0:s_]
        disc = ((yy - s_ / 2 + 0.5) ** 2 + (xx - s_ / 2 + 0.5) ** 2) <= (s_ / 2 - 1) ** 2
        sq[..., 3] = disc.astype(np.float32)
        caps.append(dict(tile=sq, w=s_, h=s_, area=int(disc.sum()), cap=True))
    fungi = caps + fungi
    g_img, gs = pack(grass, "grass")
    f_img, fs = pack(fungi, "groundcover", sub=(0.0, 0.5))
    atl.save_region("grass", g_img, {"tiles": len(grass), "scale": gs})
    atl.save_region("groundcover", np.concatenate([f_img, np.zeros((f_img.shape[0], atl.REGIONS["groundcover"][2] -
                                                                     f_img.shape[1], 4), np.float32)], 1),
                    {"tiles": len(fungi), "scale": fs})
    atlas_path = atl.assemble()
    print(f"[groundcover] grass tiles {len(grass)} (scale {gs:.2f}), fungi tiles {len(fungi)} (scale {fs:.2f})", flush=True)
    # painted oak limbs (same deterministic layout as the golden-oak bark texture)
    sp = SP.TREES["golden_oak"]
    ref = tree.TreeRef(sp["cfg"])
    B = tree.TreeBuilder(ref, None, sp["cfg"])
    base_paths = B.wood_paths()
    bark_uv, dens = BT.bark_layout(base_paths, ref.ppm)
    limbs = [(l["P"], l["r"]) for l in ref.limbs]
    ids = [i + 1 for i in range(len(ref.limbs))]
    keep = [k for k, (P2, r2) in enumerate(limbs) if 1.2 <= float(np.median(r2)) <= 4.5 and
            float(np.linalg.norm(np.diff(np.asarray(P2, float), axis=0), axis=1).sum()) >= 45]
    limbs = [limbs[k] for k in keep]
    ids = [ids[k] for k in keep]
    core.reset()
    fol = pblend.export_material("lf_foliage", atlas_path, alpha_clip=0.5, double_sided=True)
    oak_bark = pblend.export_material("lf_bark_oak", os.path.join(RT, "lf_bark_oak_c.jpg"),
                                      normal_path=os.path.join(RT, "lf_bark_oak_n.png"),
                                      rough_path=os.path.join(RT, "lf_bark_oak_r.png"))
    out = {}
    # ---------------------------------------------------------------- grass tufts
    G = {}
    for v, (n0, rad, hs, seed) in {"v1": (12, 0.28, 1.0, 1), "v2": (16, 0.4, 1.15, 2), "v3": (10, 0.22, 1.35, 3)}.items():
        lods = []
        for lod, frac in ((0, 1.0), (1, 0.5), (2, 0.25)):
            lods.append(tuft(grass, max(2, int(n0 * frac)), rad, hs, seed, PPM_GRASS))
        G[v] = lods
    out["lf_env_grass_tuft"] = (G, [fol, fol], None)
    # ---------------------------------------------------------------- mushrooms (painted fungi clusters)
    M = {}
    for v, (n0, rad, hs, seed) in {"v1": (6, 0.16, 1.0, 4), "v2": (10, 0.28, 0.8, 5)}.items():
        lods = []
        for lod, (seg_c, frac) in enumerate(((10, 1.0), (7, 0.7), (5, 0.5))):
            lods.append(mushrooms(fungi, max(2, int(n0 * frac)), rad, hs, seed, seg_c))
        M[v] = lods
    out["lf_env_mushrooms"] = (M, [fol, fol], None)
    # ---------------------------------------------------------------- fallen branches
    FB = {}
    for v, (n0, seed) in {"v1": (6, 7), "v2": (4, 8)}.items():
        lods = []
        for lod, frac in ((0, 1.0), (1, 0.7), (2, 0.4)):
            md = branches(limbs, ref.ppm, bark_uv, ids, max(2, int(n0 * frac)), seed)
            if lod == 0:
                md.extend(tuft(grass, 4, 0.8, 0.8, seed + 50, PPM_GRASS))
            lods.append(md)
        FB[v] = lods
    out["lf_env_fallen_branches"] = (FB, [oak_bark, fol], "lf_bark_oak")
    pblend.setup_render(12)
    for asset, (V, mats, bark) in out.items():
        built = {}
        info = {}
        for vn, lods in V.items():
            objs = []
            info[vn] = {}
            for lod, md in enumerate(lods):
                o = pblend.obj_from_mesh(f"{asset}_{vn}_LOD{lod}", md, mats)
                objs.append(o)
                info[vn][f"LOD{lod}"] = dict(tris=md.tris())
            built[vn] = objs
        print(f"[{asset}] " + "; ".join(f"{vn}: " + "/".join(str(info[vn][f'LOD{l}']['tris']) for l in range(3))
                                        for vn in info), flush=True)
        allobjs = [o for v in built.values() for o in v]
        pblend.use_painted(allobjs, K)
        lineup = [built[v][0] for v in built]
        x = 0.0
        for o in lineup:
            lo, hi = core.bounds([o])
            o.location.x = x - lo[0]
            x += hi[0] - lo[0] + 0.4
        bpy.context.view_layer.update()
        for nm_, pitch, yaw in (("variants_38", 38, 45), ("variants_front", 5, 0)):
            pblend.only(lineup)
            pblend.ortho_frame(lineup, pitch, yaw, res=(1400, 600))
            pblend.save_shot(frr.render_rgba(), BT.qa_path(asset, a.iter, f"{nm_}.png"), text=f"{asset} {nm_}")
        for o in lineup:
            o.location.x = 0
        bpy.context.view_layer.update()
        pblend.use_painted(allobjs, K, on=False)
        BPR.export(asset, built, info, bark or "lf_none")
        import json as _json
        mp = os.path.join(RT, f"{asset}.meta.json")
        meta = _json.load(open(mp))
        meta["textures"] = {"lf_foliage_atlas.png": 2048}
        if bark:
            meta["textures"].update({f"{bark}_c.jpg": 1024, f"{bark}_n.png": 1024, f"{bark}_r.png": 1024})
        meta["generation"] = "v2: painted tiles from art/02 (grass bases / bracket fungi) and painted golden-oak limbs"
        meta["build"] = "python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/paint3d/build_groundcover.py"
        meta.pop("collision", None)
        core.write_json(mp, meta)
        for o in allobjs:
            bpy.data.objects.remove(o, do_unlink=True)
        for o in [o for o in bpy.data.objects if o.type == "EMPTY"]:
            bpy.data.objects.remove(o, do_unlink=True)
    print(f"[groundcover] done ({time.time() - t0:.1f}s)", flush=True)


if __name__ == "__main__":
    main()
