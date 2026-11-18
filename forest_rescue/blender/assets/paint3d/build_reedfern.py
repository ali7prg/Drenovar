"""Reeds + fern (art/02 middle row, right): reeds = vertical strand cards (painted strips) in crossed planes,
fern = arching frond cards (painted frond patches on bent strips radiating from the crown).

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/paint3d/build_reedfern.py [--iter N]
Variants (names kept for forest_kit.gd / forest_kit.json): reed_v1, reed_v2, fern_v1, fern_v2, mixed_v1 (= art/02).
"""
import argparse
import math
import os
import sys
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pblend  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from scipy import ndimage as ndi  # noqa: E402
from frlib import core, paths, refs, render as frr  # noqa: E402

import geom  # noqa: E402
import p3atlas as atl  # noqa: E402
import seg  # noqa: E402
import tree  # noqa: E402
import build_tree as BT  # noqa: E402
import build_props as BPR  # noqa: E402

RT = os.path.join(paths.RUNTIME, "forest")
ASSET = "lf_env_reed_fern"
BOX = (1228, 478, 1536, 728)
CLIP = 236            # crop rows: painted ground mound below
GROUND = 244
PPM = 94.0            # tallest cattail ~2.4 m
SPLIT_X = 158         # crop col: reeds left of it, fern right (+ overlap handled by hue)
K = 0.35


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=int, default=1)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    t0 = time.time()
    qa = lambda n: BT.qa_path(ASSET, a.iter, n)  # noqa: E731
    S = seg.sheet("02_forest_modular_kit.png")
    bg = seg.bg_colour(S)
    x0, y0, x1, y1 = BOX
    img = S[y0:y1, x0:x1].astype(np.float32)
    fg_full, _ = seg.fg_mask(img, bg, thresh=10, min_area=60)
    fg = fg_full.copy()
    fg[CLIP:] = False
    H, W = fg.shape
    Lab = seg.lab(ndi.gaussian_filter(img, (0.8, 0.8, 0)))
    Hu = np.degrees(np.arctan2(Lab[..., 2], Lab[..., 1])) % 360
    xx = np.arange(W)[None, :]
    # fern: bright yellow-green fronds right of the split; reeds: everything else (blades + cattails)
    fern = fg & (xx >= SPLIT_X - 30) & (Hu > 78) & (Lab[..., 0] > 30)
    fern = ndi.binary_closing(fern, iterations=3) & fg
    fern &= (xx >= SPLIT_X - 30)
    lab_, n = ndi.label(fern)
    if n:
        sz = ndi.sum(fern, lab_, np.arange(1, n + 1))
        fern = np.isin(lab_, np.nonzero(sz > 150)[0] + 1)
    fern = ndi.binary_fill_holes(fern) & fg
    reed = fg & ~fern
    view = refs.View(name="reed_fern", image=img, mask=fg, d=geom.elevated_dir(8.0), ppm=PPM, ax=W / 2.0, ay=float(GROUND))
    # patches: reeds = vertical strips, fern = frond clumps
    reed_lbl = seg.strip_patches(img, reed, width=9, max_h=200, min_px=40)
    fern_lbl = seg.clump_patches(img, fern, n_target=14, min_px=120, compactness=0.002, max_k=0)
    lbl = reed_lbl.copy()
    lbl[fern_lbl > 0] = fern_lbl[fern_lbl > 0] + reed_lbl.max()
    n_reed = int(reed_lbl.max())
    pref = types.SimpleNamespace(img=img, fg=fg, wood_cov=np.zeros_like(fg), crown_rows=(0, H - 1),
                                 xc=np.full(H, W / 2.0), R=np.full(H, W / 2.0), H=H, W=W, ppm=PPM, bg=bg)
    P = tree.Patches.__new__(tree.Patches)
    P.ref = pref
    P.lbl = seg.relabel(lbl)
    P.n = int(P.lbl.max())
    P.tiles, P.rects, P.info = [], [], []
    for i in range(1, P.n + 1):
        m = P.lbl == i
        tile, rect = seg.make_tile(img, fg, m, margin=4 if i <= n_reed else 3, scale=2 if i > n_reed else 1, bg=bg)
        ys, xs = np.nonzero(m)
        P.tiles.append(tile)
        P.rects.append(rect)
        P.info.append(dict(c=(float(xs.mean()), float(ys.mean())), area=int(m.sum()), kind="reed" if i <= n_reed else "fern",
                           w_m=(rect[2] - rect[0]) / PPM, h_m=(rect[3] - rect[1]) / PPM, y1=int(ys.max()),
                           y0=int(ys.min())))
    from skimage import color as skc
    n0 = P.n
    for i in range(n0):
        inf = P.info[i]
        t_ = P.tiles[i]
        if inf["kind"] == "reed":
            # golden copy (art/01 reed-bed colour): Lab hue -6 deg, L +7, chroma x1.15
            lab_ = seg.lab(t_[..., :3])
            C_ = np.hypot(lab_[..., 1], lab_[..., 2]) * 1.15
            h_ = np.arctan2(lab_[..., 2], lab_[..., 1]) - np.radians(6)
            lab_ = np.stack([np.clip(lab_[..., 0] + 7, 0, 100), C_ * np.cos(h_), C_ * np.sin(h_)], -1)
            P.tiles.append(np.concatenate([np.clip(skc.lab2rgb(lab_), 0, 1).astype(np.float32), t_[..., 3:4]], 2))
            P.rects.append(P.rects[i])
            P.info.append(dict(inf, kind="gold"))
            # green base: lower 45 % of the strip (painted green blades at the base)
            hh = t_.shape[0]
            P.tiles.append(t_[int(hh * 0.55):].copy())
            r_ = P.rects[i]
            P.rects.append((r_[0], r_[1] + int((r_[3] - r_[1]) * 0.55), r_[2], r_[3]))
            P.info.append(dict(inf, kind="base", h_m=inf["h_m"] * 0.45))
        elif inf["kind"] == "fern":
            # golden-green fern copy (lighter, more saturated)
            lab_ = seg.lab(t_[..., :3])
            C_ = np.hypot(lab_[..., 1], lab_[..., 2]) * 1.12
            h_ = np.arctan2(lab_[..., 2], lab_[..., 1]) - np.radians(4)
            lab_ = np.stack([np.clip(lab_[..., 0] + 6, 0, 100), C_ * np.cos(h_), C_ * np.sin(h_)], -1)
            P.tiles.append(np.concatenate([np.clip(skc.lab2rgb(lab_), 0, 1).astype(np.float32), t_[..., 3:4]], 2))
            P.rects.append(P.rects[i])
            P.info.append(dict(inf, kind="fern_gold"))
    P.n = len(P.tiles)
    reg, s = P.pack("reed_fern")
    atl.save_region("reed_fern", reg, {"asset": ASSET, "tiles": P.n, "scale": s})
    atlas_path = atl.assemble()
    seg.save(qa("patches.png"), seg.label_preview(P.lbl, img, 0.45))
    print(f"[{ASSET}] reed strips {n_reed} fern fronds {P.n - n_reed} atlas scale {s:.3f} ({time.time() - t0:.1f}s)",
          flush=True)
    core.reset()
    fol = pblend.export_material("lf_foliage", atlas_path, alpha_clip=0.5, double_sided=True)
    reed_ids = [i for i in range(P.n) if P.info[i]["kind"] == "reed"]
    fern_ids = [i for i in range(P.n) if P.info[i]["kind"] == "fern"]
    gold_ids = [i for i in range(P.n) if P.info[i]["kind"] == "gold"]
    base_ids = [i for i in range(P.n) if P.info[i]["kind"] == "base"]
    fern_gold = [i for i in range(P.n) if P.info[i]["kind"] == "fern_gold"]
    fcx = np.mean([P.info[i]["c"][0] for i in fern_ids]) if fern_ids else W * 0.75
    rcx = np.mean([P.info[i]["c"][0] for i in reed_ids]) if reed_ids else W * 0.3

    def wind(V, base_z=0.0, top=2.4, phase=0.0, ao=1.0):
        C = np.zeros((len(V), 4))
        C[:, 0] = np.clip((V[:, 2] - base_z) / top, 0, 1) ** 1.3
        C[:, 1] = np.clip((V[:, 2] - base_z) / top, 0, 1) * 0.8
        C[:, 2] = phase
        C[:, 3] = ao
        return C

    def front(ids, t_m=0.0, md=None, shift=None):
        md = md or geom.Mesh()
        for i in ids:
            rect = P.rects[i]
            cu, cv_ = P.info[i]["c"]
            n = geom.nrm(-view.d)
            V, T, UV, _, N = geom.front_card(view, rect, (cu, cv_), t_m, n, P.uv[i], np.zeros(4))
            if shift is not None:
                V = V + shift
            md.add(V, T, UV, wind(V, phase=(i * 0.137) % 1), geom.nrm(N + np.array([0, 0, 0.3])), 1)
        return md

    def reed_clump(ids, angles, center_px, md=None, scale=1.0, seed=0, radius=0.7):
        """Vertical painted strip cards scattered in a tuft: each strip keeps its painted height/bottom, gets a
        random yaw and a random position inside the clump radius (len(angles) copies of the strip set)."""
        rng = np.random.default_rng(seed)
        md = md or geom.Mesh()
        c_w = geom.world_at_y(view, np.array([center_px]), np.array([float(GROUND)]), np.array([0.0]))[0]
        c_w[2] = 0.0
        for ang in angles:
            for i in ids:
                inf = P.info[i]
                w = inf["w_m"] * scale
                h = inf["h_m"] * scale
                bottom_z = (GROUND - P.rects[i][3]) / PPM * scale
                rho = radius * scale * math.sqrt(rng.random())
                phi = rng.uniform(0, 2 * math.pi)
                pos = c_w + np.array([rho * math.cos(phi), rho * math.sin(phi), max(bottom_z, -0.05)])
                yaw = math.radians(ang) + rng.normal(0, 0.6)
                n = np.array([math.sin(yaw), -math.cos(yaw), 0.0])
                V, T, UV, _, N = geom.free_card(pos, n, np.array([0, 0, 1.0]), w, h, P.uv[i], np.zeros(4),
                                                flip=bool(rng.random() < 0.5), pivot_v=0.0)
                md.add(V, T, UV, wind(V, phase=rng.random()), geom.nrm(N + np.array([0, 0, 0.3])), 1)
        return md

    def fern_rosette(ids, n_fronds, center_px, md=None, scale=1.0, seed=0, reach=1.0):
        """Arching frond cards: each painted frond patch laid on a bent strip from the crown outward."""
        rng = np.random.default_rng(seed)
        md = md or geom.Mesh()
        c_w = geom.world_at_y(view, np.array([center_px]), np.array([float(GROUND)]), np.array([0.0]))[0]
        c_w[2] = 0.05
        big = sorted(ids, key=lambda i: -P.info[i]["area"])
        for k in range(n_fronds):
            i = big[k % len(big)]
            inf = P.info[i]
            L = max(inf["w_m"], inf["h_m"]) * scale * reach * rng.uniform(0.9, 1.1)
            Wd = min(inf["w_m"], inf["h_m"]) * scale * 0.9
            phi = 2 * math.pi * k / n_fronds + rng.normal(0, 0.15)
            dirr = np.array([math.cos(phi), math.sin(phi), 0.0])
            rise = rng.uniform(0.45, 0.7)
            s_ = np.linspace(0, 1, 5)
            # arch: up and out, then drooping tip
            Pq = c_w[None] + (L * s_)[:, None] * dirr[None] * 0.85 + np.array([0, 0, 1.0])[None] * \
                (L * (rise * np.sin(np.pi * s_ * 0.85) + 0.05))[:, None]
            side = geom.nrm(np.cross(np.array([0, 0, 1.0]), dirr))
            tang = geom.nrm(np.gradient(Pq, axis=0))
            nn = geom.nrm(np.cross(side, tang))
            nn[nn[:, 2] < 0] *= -1
            widths = Wd * np.array([0.35, 0.8, 1.0, 0.85, 0.45])
            V, T, UV, C, N = geom.bent_card(Pq, widths, nn, P.uv[i], np.zeros(4), flip=bool(rng.random() < 0.5))
            md.add(V, T, UV, wind(V, top=1.3, phase=(k * 0.21) % 1), N, 1)
        return md

    variants = {}
    # mixed_v1 = art/02: front strips/fronds + crossed reed planes + fern rosette behind
    mixed = front(reed_ids + fern_ids)
    # behind the painted front: tuft of scattered strips pushed back so the front layer stays exact
    back = reed_clump(reed_ids, (60, 120), rcx, scale=0.92, seed=1, radius=0.55)
    Vb, Tb, UVb, Cb, Nb, Mb = back.arrays()
    mixed.add(Vb + view.d * 0.6, Tb, UVb, Cb, Nb, 1)
    fern_rosette(fern_ids, 7, fcx, md=mixed, scale=0.9, seed=2, reach=0.85)
    variants["mixed_v1"] = mixed
    # reed BEDS (art/01 east river: dense golden clusters a few metres across, ~2-2.4 m tall, green at the base)
    def reed_bed(angles, scale, seed, radius, base_n):
        md = reed_clump(gold_ids, angles, rcx, scale=scale, seed=seed, radius=radius)
        rngb = np.random.default_rng(seed + 100)
        c_w = geom.world_at_y(view, np.array([rcx]), np.array([float(GROUND)]), np.array([0.0]))[0]
        c_w[2] = 0.0
        for k in range(base_n):                         # dense green base blades (lower halves of the strips)
            i = base_ids[rngb.integers(len(base_ids))]
            inf = P.info[i]
            w, h = inf["w_m"] * scale, inf["h_m"] * scale
            rho = radius * scale * math.sqrt(rngb.random())
            phi = rngb.uniform(0, 2 * math.pi)
            yaw = rngb.uniform(0, math.pi)
            n = np.array([math.sin(yaw), -math.cos(yaw), 0.0])
            pos = c_w + np.array([rho * math.cos(phi), rho * math.sin(phi), -0.02])
            V, T, UV, _, N = geom.free_card(pos, n, np.array([0, 0, 1.0]), w, h, P.uv[i], np.zeros(4),
                                            flip=bool(rngb.random() < 0.5), pivot_v=0.0)
            md.add(V, T, UV, wind(V, phase=rngb.random()), geom.nrm(N + np.array([0, 0, 0.3])), 1)
        return md
    variants["reed_v1"] = reed_bed((0, 36, 72, 108, 144), 1.0, 3, 1.7, 220)
    variants["reed_v2"] = reed_bed((20, 80, 140, 170), 0.9, 4, 1.3, 160)
    # fern clusters: several arching rosettes
    f1 = geom.Mesh()
    for k_, (dx, dy, sc_) in enumerate(((0, 0, 1.4), (1.5, 0.5, 1.2), (-1.3, 0.9, 1.25), (0.4, -1.4, 1.1))):
        fr = fern_rosette(fern_gold, 10, fcx, scale=sc_, seed=5 + k_)
        Vf, Tf, UVf, Cf, Nf, Mf = fr.arrays()
        f1.add(Vf + np.array([dx, dy, 0.0]), Tf, UVf, Cf, Nf, 1)
    variants["fern_v1"] = f1
    f2 = geom.Mesh()
    for k_, (dx, dy, sc_) in enumerate(((0, 0, 1.3), (1.3, -0.7, 1.15), (-1.0, -0.9, 1.1))):
        fr = fern_rosette(fern_gold, 9, fcx, scale=sc_, seed=11 + k_, reach=1.1)
        Vf, Tf, UVf, Cf, Nf, Mf = fr.arrays()
        f2.add(Vf + np.array([dx, dy, 0.0]), Tf, UVf, Cf, Nf, 1)
    variants["fern_v2"] = f2
    built = {}
    info = {}
    for vn, md in variants.items():
        Vv, Tt, UVv, Cc, Nn, Mm = md.arrays()
        used = np.unique(Tt)
        off = Vv[used].mean(0) if vn != "mixed_v1" else np.zeros(3)
        off[2] = 0.0
        objs = []
        info[vn] = {}
        for lod in range(3):
            if lod == 0:
                keep = np.arange(len(Tt))
            else:
                # fewer cards: keep every 2nd (LOD1) / 4th (LOD2) card (2 tris per quad, 8 per bent frond)
                step = 2 if lod == 1 else 4
                quad = np.arange(len(Tt)) // 2
                keep = np.nonzero(quad % step == 0)[0]
            m = geom.Mesh()
            m.add(Vv - off, Tt[keep], UVv, Cc, Nn, 0)
            m.M = [Mm[keep]]
            o = pblend.obj_from_mesh(f"{ASSET}_{vn}_LOD{lod}", m, [fol, fol])
            objs.append(o)
            info[vn][f"LOD{lod}"] = dict(tris=m.tris())
        built[vn] = objs
        print(f"[{ASSET}] {vn}: " + ", ".join(f"LOD{l}={info[vn][f'LOD{l}']['tris']}" for l in range(3)), flush=True)
    pblend.setup_render(16)
    allobjs = [o for v in built.values() for o in v]
    metrics = {}
    for lod in range(3):
        for kk, tag in ((K, "painted"), (0.0, "albedo")):
            if lod > 0 and tag == "albedo":
                continue
            pblend.use_painted(allobjs, kk)
            rgba = pblend.render_view(view, [built["mixed_v1"][lod]])
            rgba[CLIP:, :, 3] = 0
            mm = pblend.compare_sheet(img, fg, rgba, bg, qa(f"front_mixed_v1_LOD{lod}_{tag}.png"),
                                      f"{ASSET} mixed_v1 LOD{lod} vs art/02 ({tag} k={kk}) iter {a.iter}")
            metrics[f"mixed_v1_LOD{lod}_{tag}"] = mm
            print(f"[{ASSET}] LOD{lod} {tag}: {mm}", flush=True)
    pblend.use_painted(allobjs, K)
    lineup = [built[v][0] for v in built]
    x = 0.0
    for o in lineup:
        lo, hi = core.bounds([o])
        o.location.x = x - lo[0]
        x += hi[0] - lo[0] + 0.8
    bpy.context.view_layer.update()
    for nm_, pitch, yaw in (("variants_front", 0, 0), ("variants_38", 38, 45), ("variants_top", 90, 0)):
        pblend.only(lineup)
        pblend.ortho_frame(lineup, pitch, yaw, res=(1600, 700))
        pblend.save_shot(frr.render_rgba(), qa(f"{nm_}.png"), text=f"{ASSET} variants {nm_}")
    for o in lineup:
        o.location.x = 0
    bpy.context.view_layer.update()
    core.write_json(qa("metrics.json"), {"metrics": metrics, "lods": info})
    pblend.use_painted(allobjs, K, on=False)
    BPR.export(ASSET, built, info, "lf_foliage_only")
    # meta: no bark texture for this asset
    import json as _json
    mp = os.path.join(RT, f"{ASSET}.meta.json")
    meta = _json.load(open(mp))
    meta["textures"] = {"lf_foliage_atlas.png": 2048}
    meta["paintedLightMix"] = K
    meta["build"] = "python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/paint3d/build_reedfern.py"
    meta.pop("collision", None)
    core.write_json(mp, meta)
    print(f"[{ASSET}] exported ({time.time() - t0:.1f}s)", flush=True)


if __name__ == "__main__":
    main()
