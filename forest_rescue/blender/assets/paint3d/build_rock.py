"""Moss rock (art/02 middle row) as a fractured limestone MOUND (see mound.py).

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/paint3d/build_rock.py [--iter N]
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
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from scipy import ndimage as ndi  # noqa: E402
from skimage import morphology  # noqa: E402
from frlib import core, paths, render as frr  # noqa: E402

import geom  # noqa: E402
import mound  # noqa: E402
import p3atlas as atl  # noqa: E402
import seg  # noqa: E402
import slab  # noqa: E402
import swatch  # noqa: E402
import tree  # noqa: E402
import types  # noqa: E402
import build_tree as BT  # noqa: E402
import build_props as BPR  # noqa: E402

RT = os.path.join(paths.RUNTIME, "forest")
ASSET = "lf_env_moss_rock"
K = 0.35
FRONT_T = 0.67           # |n . view| above which a face takes the painting (stretch <= 1/0.67 = 1.49)


def best_windows(mask, wh, n=3, stride=4):
    """Top-n windows (x0,y0,x1,y1) with the highest fraction of mask pixels (non-overlapping greedy)."""
    w, h = wh
    ii = np.pad(mask.astype(np.float64), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    H, W = mask.shape
    cands = []
    for y in range(0, H - h, stride):
        for x in range(0, W - w, stride):
            s = ii[y + h, x + w] - ii[y, x + w] - ii[y + h, x] + ii[y, x]
            cands.append((s / (w * h), x, y))
    cands.sort(reverse=True)
    out = []
    for f, x, y in cands:
        if all(abs(x - a) >= w or abs(y - b) >= h for a, b, _, _ in out):
            out.append((x, y, x + w, y + h))
        if len(out) >= n:
            break
    return out


def quilt_from(img, boxes, size, scale=2.0, patch=48, overlap=12, n=7, seed=3):
    srcs = [cv2.resize(img[b[1]:b[3], b[0]:b[2]], None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
            for b in boxes]
    h = min(s.shape[0] for s in srcs)
    src = np.concatenate([cv2.resize(s, (int(s.shape[1] * h / s.shape[0]), h)) for s in srcs], 1)
    q = swatch.quilt_tileable(src.astype(np.float64), n=n, patch=patch, overlap=overlap, seed=seed)
    return np.clip(swatch.upscale_wrap(q, size, sharpen=0.5), 0, 1).astype(np.float32)


def build_mound_mesh(ref, body, lbl, depth_frac, voxel=2.5, rng=None):
    """Union of solid painted blocks arranged as a mound: block depth = top-band estimate clamped to 0.5-1.0 x the
    block's own width, scaled up toward the middle of the outcrop (highest / deepest in the middle)."""
    import prism
    top_like = (((ref.Hu > 75) & (ref.Hu < 118) & (ref.C > 14)) | (ref.L > 64))
    ys, xs = np.nonzero(body)
    xc, half = 0.5 * (xs.min() + xs.max()), 0.5 * (xs.max() - xs.min() + 1)
    Vs, Fs, base = [], [], 0
    for b in range(1, int(lbl.max()) + 1):
        m = (lbl == b) & body
        if m.sum() < 120:
            continue
        mg = ndi.binary_dilation(m, iterations=3) & ndi.binary_dilation(body, iterations=1)
        cx = float(np.nonzero(m)[1].mean())
        mm = math.sqrt(max(0.0, 1.0 - ((cx - xc) / half) ** 2))
        res = prism.block_solid(ref.view, mg, top_like, ref.ppm, ref.cfg["elev"], y0=rng.uniform(-0.12, 0.12),
                                rng=rng, min_depth_k=0.5, max_depth_k=1.0, depth_mul=0.65 + 0.45 * mm, eps_px=4.5,
                                taper=0.8)
        if res is None:
            continue
        V, F, _ = res
        Vs.append(V)
        Fs.append(F + base)
        base += len(V)
    return np.concatenate(Vs), np.concatenate(Fs)


def uv_mesh(V, T, ref, clip):
    Vc = V[T]
    fn = geom.nrm(np.cross(Vc[:, 1] - Vc[:, 0], Vc[:, 2] - Vc[:, 0]))
    facing = fn @ (-ref.view.d)
    kind = np.where(facing >= FRONT_T, 0, np.where(fn[:, 2] >= 0.55, 2, 1))
    uu, vv, _ = ref.view.project(Vc.reshape(-1, 3))
    vv = np.clip(vv, 0, clip - 2)
    uu = np.clip(uu, 0, ref.W - 1)
    FR, SR, TR = slab.FRONT, slab.SIDE, slab.TOP
    uv_f = np.stack([FR[0] + (FR[2] - FR[0]) * uu / ref.W, FR[3] - (FR[3] - FR[1]) * vv / ref.H], -1).reshape(-1, 3, 2)
    uv_s = mound.isometric_uvs(Vc, SR, period_m=7.5)
    uv_t = mound.isometric_uvs(Vc, TR, period_m=7.5)
    UV = np.where((kind == 0)[:, None, None], uv_f, np.where((kind == 2)[:, None, None], uv_t, uv_s))
    return Vc, UV, kind, fn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=int, default=1)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    t0 = time.time()
    qa = lambda n: BT.qa_path(ASSET, a.iter, n)  # noqa: E731
    rng = np.random.default_rng(5)
    ref = BPR.make_ref("moss_rock")
    plants = ref.fg & (ref.Hu < 64) & (ref.C > 26)
    plants = ndi.binary_opening(plants, iterations=1)
    body0 = ndi.binary_fill_holes(ndi.binary_closing(ref.fg & ~plants, structure=morphology.disk(2))) & ref.fg
    body0 = morphology.remove_small_objects(body0, max_size=300)
    plants_card = plants & ~ndi.binary_erosion(body0, iterations=3)
    body = body0 | (plants & ndi.binary_erosion(body0, iterations=3))
    lbl = BPR.blocks_of(ref, body, min_dist=26, min_area=1400)
    paint_mask = ref.fg & ~plants_card
    # ------------------------------------------------------------ textures (all painted pixels)
    stone_px = body & (ref.C < 17) & (ref.L > 40)
    moss_px = body & (ref.Hu > 75) & (ref.Hu < 118) & (ref.C > 14)
    sw = best_windows(stone_px, (36, 36), n=3)
    mw = best_windows(moss_px, (32, 18), n=3)
    TEX = 1024
    tex = np.zeros((TEX, TEX, 3), np.float32)

    def box(R):
        return int(R[0] * TEX), int((1 - R[3]) * TEX), int(R[2] * TEX), int((1 - R[1]) * TEX)
    x0, y0, x1, y1 = box(slab.FRONT)
    tex[y0:y1, x0:x1] = slab.front_texture(ref.img, paint_mask, ref.clip, (x1 - x0, y1 - y0))
    x0, y0, x1, y1 = box(slab.SIDE)
    side = quilt_from(ref.img, sw, max(x1 - x0, y1 - y0))
    tex[y0:y1, x0:x1] = side[:y1 - y0, :x1 - x0]
    x0, y0, x1, y1 = box(slab.TOP)
    top = quilt_from(ref.img, mw + sw[:2], max(x1 - x0, y1 - y0), scale=2.5, patch=40, overlap=10)
    tex[y0:y1, x0:x1] = top[:y1 - y0, :x1 - x0]
    cpath = os.path.join(RT, "lf_rock_limestone_c.jpg")
    cv2.imwrite(cpath, cv2.cvtColor((np.clip(tex, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR),
                [cv2.IMWRITE_JPEG_QUALITY, 90])
    nmap, rmap = tree.bark_maps(tex)
    npath = os.path.join(RT, "lf_rock_limestone_n.png")
    rpath = os.path.join(RT, "lf_rock_limestone_r.png")
    seg.save(npath, nmap)
    seg.save(rpath, np.stack([rmap] * 3, -1))
    seg.save(qa("tex.png"), tex)
    print(f"[{ASSET}] stone windows {sw} moss windows {mw} ({time.time() - t0:.1f}s)", flush=True)
    # ------------------------------------------------------------ plant cards (atlas region)
    pref = types.SimpleNamespace(img=ref.img, fg=plants_card, wood_cov=np.zeros_like(plants_card),
                                 crown_rows=(0, ref.H - 1), xc=np.full(ref.H, ref.W / 2.0), R=np.full(ref.H, ref.W / 2.0),
                                 H=ref.H, W=ref.W, ppm=ref.ppm, bg=ref.bg)
    P = tree.Patches(pref, n_target=40, min_px=30, margin=2, scale=2)
    reg, s = P.pack("rock_plants")
    atl.save_region("rock_plants", reg, {"asset": ASSET, "tiles": P.n, "scale": s})
    atlas_path = atl.assemble()
    # ------------------------------------------------------------ variants
    core.reset()
    rock_mat = pblend.export_material("lf_rock_limestone", cpath, normal_path=npath, rough_path=rpath)
    fol = pblend.export_material("lf_foliage", atlas_path, alpha_clip=0.5, double_sided=True)
    ys_, xs_ = np.nonzero(body)
    xmid = 0.5 * (xs_.min() + xs_.max())
    groups = {"v1": (body, lbl, 0.72, None),
              "v2": None, "v3": None}
    cents = {b: np.array(ndi.center_of_mass(lbl == b)) for b in range(1, lbl.max() + 1)}
    left = [b for b, c in cents.items() if c[1] < 0.55 * ref.W]
    right = [b for b, c in cents.items() if c[1] >= 0.5 * ref.W]
    for vn, ids in (("v2", left), ("v3", right)):
        m = np.isin(lbl, ids) & body
        m = ndi.binary_closing(m, iterations=2)
        groups[vn] = (m, np.where(m, lbl, 0), 0.8, True)
    built, info, stretch = {}, {}, {}
    for vn, (bm, bl, dfrac, center) in groups.items():
        Vf, F = build_mound_mesh(ref, bm, bl, dfrac, rng=rng)
        o = BPR.to_obj(f"tmp_{vn}", Vf, F)
        objs = []
        info[vn] = {}
        for lod, target in ((0, 3600), (1, 1300), (2, 250)):
            oc = o.copy()
            oc.data = o.data.copy()
            core.link(oc)
            BPR.decimate(oc, target)
            V, T, N = BPR.arrays(oc)
            bpy.data.objects.remove(oc, do_unlink=True)
            Vc, UVc, kind, fn = uv_mesh(V, T, ref, ref.clip)
            if lod == 0:
                rs, rm = mound.stretch_ratio(Vc[kind != 0], UVc[kind != 0], (0.3 * 1024, 0.32 * 1024))
                rf, rfm = mound.stretch_ratio(Vc[kind == 0], UVc[kind == 0], (0.7 * 1024 * 3.0, 0.7 * 1024 * 3.0))
                stretch[vn] = dict(side_top_max=round(rs, 3), side_top_median=round(rm, 3),
                                   front_faces=int((kind == 0).sum()), other_faces=int((kind != 0).sum()))
            md = geom.Mesh()
            Cw = np.zeros((len(Vc) * 3, 4))
            Cw[:, 3] = np.where(np.repeat(kind, 3) == 2, 1.0, 0.9)
            md.add(Vc.reshape(-1, 3), np.arange(len(Vc) * 3).reshape(-1, 3), UVc.reshape(-1, 2), Cw,
                   np.repeat(fn, 3, axis=0), 0)
            if lod < 2 and P.n:
                keep = []
                for i in range(P.n):
                    cu, cv_ = P.info[i]["c"]
                    ui, vi = int(np.clip(cu, 0, ref.W - 1)), int(np.clip(cv_, 0, ref.H - 1))
                    if ndi.binary_dilation(bm, iterations=12)[vi, ui]:
                        keep.append(i)
                if lod == 1:
                    keep = sorted(keep, key=lambda i: -P.info[i]["area"])[: max(1, len(keep) // 2)]
                _, zb = tree.tri_id_buffer(V, T, np.arange(len(T)), ref.view)
                md.extend(BPR.plant_cards(ref, P, zb, keep, copies=((55, 0.9), (-60, 0.85)) if lod == 0 else ((70, 0.9),)))
            Vv, Tt, UVv, Cc, Nn, Mm = md.arrays()
            if center:
                used = np.unique(Tt)
                off = Vv[used].mean(0)
                off[2] = 0.0
                md = geom.Mesh()
                md.add(Vv - off, Tt, UVv, Cc, Nn, 0)
                md.M = [Mm]
            if vn == "v3":
                md = md.transformed(mirror_x=True)
            ob = pblend.obj_from_mesh(f"{ASSET}_{vn}_LOD{lod}", md, [rock_mat, fol])
            objs.append(ob)
            info[vn][f"LOD{lod}"] = dict(tris=md.tris())
        bpy.data.objects.remove(o, do_unlink=True)
        built[vn] = objs
        print(f"[{ASSET}] {vn}: " + ", ".join(f"LOD{l}={info[vn][f'LOD{l}']['tris']}" for l in range(3)) +
              f" stretch {stretch[vn]}", flush=True)
    # ------------------------------------------------------------ QA
    pblend.setup_render(16)
    allobjs = [o for v in built.values() for o in v]
    metrics = {"uv_stretch": stretch}
    for lod in range(3):
        for kk, tag in ((K, "painted"), (0.0, "albedo")):
            if lod > 0 and tag == "albedo":
                continue
            pblend.use_painted(allobjs, kk)
            rgba = pblend.render_view(ref.view, [built["v1"][lod]])
            rgba[ref.clip:, :, 3] = 0
            mm = pblend.compare_sheet(ref.img, ref.fg, rgba, ref.bg, qa(f"front_v1_LOD{lod}_{tag}.png"),
                                      f"{ASSET} v1 LOD{lod} vs art/02 ({tag} k={kk}) iter {a.iter}")
            metrics[f"v1_LOD{lod}_{tag}"] = mm
            print(f"[{ASSET}] LOD{lod} {tag}: {mm}", flush=True)
    pblend.use_painted(allobjs, K)
    lineup = [built[v][0] for v in built]
    x = 0.0
    for o in lineup:
        lo, hi = core.bounds([o])
        o.location.x = x - lo[0]
        x += hi[0] - lo[0] + 1.5
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
    BPR.export(ASSET, built, info, "lf_rock_limestone")
    import json as _json
    mp = os.path.join(RT, f"{ASSET}.meta.json")
    meta = _json.load(open(mp))
    meta["generation"] = "v2: fractured limestone mound from the art/02 outcrop (painted front, painted-limestone " \
                         "sides and painted moss tops by patch synthesis, isometric per-face UVs)"
    meta["uvStretch"] = stretch
    meta["build"] = "python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/paint3d/build_rock.py"
    core.write_json(mp, meta)
    print(f"[{ASSET}] exported ({time.time() - t0:.1f}s)", flush=True)


if __name__ == "__main__":
    main()
