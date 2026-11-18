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
    vtop = ys.min()
    apex_w = geom.world_at_y(ref.view, np.array([xc]), np.array([vtop + 0.45 * (ys.max() - vtop)]), np.array([0.0]))[0]
    apex = (float(apex_w[0]), float(apex_w[2]))
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
                                taper=0.55, apex=apex)
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


def rock_profile(ref, body):
    """Front-view height profile (world x, max height z) of the painted outcrop body."""
    cols = np.nonzero(body.any(0))[0]
    px, ph = [], []
    for x in cols:
        top = np.nonzero(body[:, x])[0].min()
        P = geom.world_at_y(ref.view, np.array([float(x)]), np.array([float(top)]), np.array([0.0]))[0]
        G = geom.world_at_y(ref.view, np.array([float(x)]), np.array([float(ref.ground)]), np.array([0.0]))[0]
        px.append(P[0])
        ph.append(max(0.0, P[2] - G[2]))
    px, ph = np.array(px), ndi.gaussian_filter1d(np.array(ph), 3)
    return px, ph


def lab_grade(img, dl=0.0, kc=1.0):
    from skimage import color as skc
    lab_ = seg.lab(np.clip(img, 0, 1))
    lab_[..., 0] = np.clip(lab_[..., 0] + dl, 0, 100)
    lab_[..., 1:] *= kc
    return np.clip(skc.lab2rgb(lab_), 0, 1).astype(np.float32)


def main():
    import rockfield
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
    lbl = BPR.blocks_of(ref, body, min_dist=22, min_area=900)
    paint_mask = ref.fg & ~plants_card
    # ------------------------------------------------------------ textures: painting / quilted limestone / moss
    stone_px = body & (ref.C < 17) & (ref.L > 40)
    moss_px = body & (ref.Hu > 75) & (ref.Hu < 118) & (ref.C > 14)
    sw = best_windows(stone_px, (36, 36), n=3)
    mw = best_windows(moss_px, (32, 18), n=3)
    TEX = 1024

    def box(R):
        return int(R[0] * TEX), int((1 - R[3]) * TEX), int(R[2] * TEX), int((1 - R[1]) * TEX)
    tex = np.zeros((TEX, TEX, 3), np.float32)
    x0, y0, x1, y1 = box(slab.FRONT)
    tex[y0:y1, x0:x1] = slab.front_texture(ref.img, paint_mask, ref.clip, (x1 - x0, y1 - y0))
    x0, y0, x1, y1 = box(slab.SIDE)
    side = quilt_from(ref.img, sw, max(x1 - x0, y1 - y0))
    tex[y0:y1, x0:x1] = side[:y1 - y0, :x1 - x0]
    x0, y0, x1, y1 = box(slab.TOP)
    top = quilt_from(ref.img, mw + sw[:1], max(x1 - x0, y1 - y0), scale=2.5, patch=40, overlap=10)
    tex[y0:y1, x0:x1] = top[:y1 - y0, :x1 - x0]
    variants_tex = {"lf_rock_limestone": tex,
                    "lf_rock_quarry": lab_grade(tex, dl=8.0, kc=0.65)}     # art/01 SW quarry: lighter, greyer
    paths_ = {}
    for nm, tx in variants_tex.items():
        cpath = os.path.join(RT, f"{nm}_c.jpg")
        cv2.imwrite(cpath, cv2.cvtColor((np.clip(tx, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR),
                    [cv2.IMWRITE_JPEG_QUALITY, 90])
        nmap, rmap = tree.bark_maps(tx)
        npath = os.path.join(RT, f"{nm}_n.png")
        rpath = os.path.join(RT, f"{nm}_r.png")
        seg.save(npath, nmap)
        seg.save(rpath, np.stack([rmap] * 3, -1))
        paths_[nm] = (cpath, npath, rpath)
    seg.save(qa("tex.png"), np.concatenate([tex, variants_tex["lf_rock_quarry"]], 1))
    # ------------------------------------------------------------ plant cards
    pref = types.SimpleNamespace(img=ref.img, fg=plants_card, wood_cov=np.zeros_like(plants_card),
                                 crown_rows=(0, ref.H - 1), xc=np.full(ref.H, ref.W / 2.0), R=np.full(ref.H, ref.W / 2.0),
                                 H=ref.H, W=ref.W, ppm=ref.ppm, bg=ref.bg)
    P = tree.Patches(pref, n_target=40, min_px=30, margin=2, scale=2)
    reg, s = P.pack("rock_plants")
    atl.save_region("rock_plants", reg, {"asset": ASSET, "tiles": P.n, "scale": s})
    atlas_path = atl.assemble()
    # ------------------------------------------------------------ fractured mound geometry
    px, ph = rock_profile(ref, body)
    xc_w = 0.5 * (px.min() + px.max())
    Wm = float(px.max() - px.min())
    cents = []
    for b in range(1, int(lbl.max()) + 1):
        m = lbl == b
        if m.sum() < 200:
            continue
        cy, cx = ndi.center_of_mass(m)
        Pw = geom.world_at_y(ref.view, np.array([cx]), np.array([cy]), np.array([0.0]))[0]
        cents.append((Pw[0] - xc_w, Pw[2]))
    D = 0.7 * Wm
    seeds = []
    for (sx, sz) in cents:                      # front row at the painted block centres
        seeds.append((sx, -0.28 * D + rng.uniform(-0.05, 0.05) * D, sz))
    for k in range(max(0, 13 - len(seeds))):    # cells spread through the depth
        sx, sz = cents[rng.integers(len(cents))]
        seeds.append((sx + rng.normal(0, 0.12 * Wm), rng.uniform(-0.05, 0.3) * D, max(0.2, sz * rng.uniform(0.6, 1.1))))
    seeds = np.array(seeds)
    protect = np.array([True] * len(cents) + [False] * (len(seeds) - len(cents)))
    specs = {
        "v1": dict(prof=(px - xc_w, ph), W=Wm, seeds=seeds, depth=0.7, tex="lf_rock_limestone", painted=True,
                   protect=protect),
    }
    # v2: compact boulder pile (4 cells) ; v3: long low ledge (7 cells)
    Wb = 4.2
    xb = np.linspace(-Wb / 2, Wb / 2, 60)
    hb = 2.4 * np.sqrt(np.clip(1 - (2 * xb / Wb) ** 2, 0, None)) ** 0.6
    sb = np.array([(-0.9, -0.5, 0.8), (0.8, -0.4, 0.9), (0.1, 0.5, 1.4), (-0.2, -0.2, 2.0)])
    specs["v2"] = dict(prof=(xb, hb), W=Wb, seeds=sb, depth=0.85, tex="lf_rock_quarry", painted=False)
    Wl = 8.5
    xl = np.linspace(-Wl / 2, Wl / 2, 80)
    hl = 1.35 * np.sqrt(np.clip(1 - (2 * xl / Wl) ** 6, 0, None)) * (1 + 0.12 * np.sin(xl * 1.3))
    sl = np.array([(x_, rng.uniform(-0.6, 0.6), 0.7) for x_ in np.linspace(-Wl / 2 + 0.7, Wl / 2 - 0.7, 7)])
    specs["v3"] = dict(prof=(xl, hl), W=Wl, seeds=sl, depth=0.45, tex="lf_rock_quarry", painted=False)
    core.reset()
    fol = pblend.export_material("lf_foliage", atlas_path, alpha_clip=0.5, double_sided=True)
    mats = {nm: pblend.export_material(nm, paths_[nm][0], normal_path=paths_[nm][1], rough_path=paths_[nm][2])
            for nm in paths_}
    built, info, report = {}, {}, {}
    for vn, spc in specs.items():
        objs = []
        info[vn] = {}
        for lod, target, vox in ((0, 3600, 0.07), (1, 1400, 0.11), (2, 280, 0.24)):
            Vg, Fg, crack, cell = rockfield.fractured_mound(spc["prof"][0], spc["prof"][1], spc["W"], spc["seeds"],
                                                            depth_frac=spc["depth"], seed=11 + len(vn), voxel=vox,
                                                            gap=max(0.11, 1.4 * vox) if lod < 2 else 0.0,
                                                            facet_cut=0.22 if spc["painted"] else 0.05,
                                                            plane_pct=80 if spc["painted"] else 60,
                                                            side_cut=0.06 if spc["painted"] else 0.02,
                                                            step_amp=0.3, protect=spc.get("protect"),
                                                            angular=not spc["painted"])
            Fg, rep = rockfield.drop_thin(Vg, Fg, 0.2)
            if spc["painted"]:
                Vg = Vg + np.array([xc_w, 0.0, 0.0])
            o = BPR.to_obj(f"tmp_{vn}_{lod}", Vg, Fg)
            ca = o.data.color_attributes.new("ao", "FLOAT_COLOR", "POINT")
            aov = np.clip(0.5 + 0.5 * crack / 0.3, 0.5, 1.0)
            cols = np.zeros((len(Vg), 4), np.float32)
            cols[:, 0] = aov
            cols[:, 3] = 1.0
            ca.data.foreach_set("color", cols.ravel())
            oc = o
            BPR.decimate(oc, target)
            for _ in range(4):
                if core.tri_count(oc) <= target * 1.08:
                    break
                BPR.decimate(oc, int(target * 0.8))
            me = oc.data
            V = np.array([v.co[:] for v in me.vertices])
            me.calc_loop_triangles()
            T = np.array([t.vertices[:] for t in me.loop_triangles])
            aol = np.zeros(len(me.vertices) * 4, np.float32)
            me.color_attributes["ao"].data.foreach_get("color", aol)
            aov2 = aol.reshape(-1, 4)[:, 0]
            Mw = np.array(oc.matrix_world)
            V = V @ Mw[:3, :3].T + Mw[:3, 3]
            bpy.data.objects.remove(oc, do_unlink=True)
            if lod == 0:
                rep0 = rep
            Vc = V[T]
            fn = geom.nrm(np.cross(Vc[:, 1] - Vc[:, 0], Vc[:, 2] - Vc[:, 0]))
            cen = Vc.mean(1)
            # front row seen by the art/02 camera keeps the painting; noisy moss threshold on up faces
            facing = fn @ (-ref.view.d)
            if spc["painted"]:
                _, zb = tree.tri_id_buffer(V, T, np.arange(len(T)), ref.view)
                uu, vv, dd = ref.view.project(cen)
                ui = np.clip(np.round(uu).astype(int), 0, ref.W - 1)
                vi = np.clip(np.round(vv).astype(int), 0, ref.H - 1)
                vis = np.isfinite(zb[vi, ui]) & (dd <= zb[vi, ui] + 0.25) & paint_mask[vi, ui]
                front = (facing >= 0.5) & vis
            else:
                front = np.zeros(len(T), bool)
            nz_thr = 0.55 + 0.12 * rockfield.noise3(cen, 0.9, 5, octaves=2)
            edge = aov2[T].mean(1) < 0.7
            kind = np.where(front, 0, np.where((fn[:, 2] >= nz_thr) & ~edge, 2, 1))
            uu, vv, _ = ref.view.project(Vc.reshape(-1, 3))
            vv = np.clip(vv, 0, ref.clip - 2)
            uu = np.clip(uu, 0, ref.W - 1)
            FR, SR, TR = slab.FRONT, slab.SIDE, slab.TOP
            uv_f = np.stack([FR[0] + (FR[2] - FR[0]) * uu / ref.W, FR[3] - (FR[3] - FR[1]) * vv / ref.H], -1).reshape(-1, 3, 2)
            uv_s = mound.isometric_uvs(Vc, SR, period_m=3.0)
            uv_t = mound.isometric_uvs(Vc, TR, period_m=3.0)
            UVc = np.where((kind == 0)[:, None, None], uv_f, np.where((kind == 2)[:, None, None], uv_t, uv_s))
            if lod == 0:
                rs_, rm_ = mound.stretch_ratio(Vc[kind != 0], UVc[kind != 0], (0.3 * 1024, 0.32 * 1024))
                report[vn] = dict(uv_stretch_max=round(rs_, 3), uv_stretch_median=round(rm_, 3), **rep0,
                                  painted_face_stretch_max=round(1 / 0.5, 2),
                                  painted_front_faces=int((kind == 0).sum()), moss_faces=int((kind == 2).sum()))
            md = geom.Mesh()
            Cw = np.zeros((len(Vc) * 3, 4))
            Cw[:, 3] = aov2[T].reshape(-1)
            md.add(Vc.reshape(-1, 3), np.arange(len(Vc) * 3).reshape(-1, 3), UVc.reshape(-1, 2), Cw,
                   np.repeat(fn, 3, axis=0), 0)
            if spc["painted"] and lod < 2 and P.n:
                keep = [i for i in range(P.n)]
                if lod == 1:
                    keep = sorted(keep, key=lambda i: -P.info[i]["area"])[: max(1, len(keep) // 2)]
                _, zb = tree.tri_id_buffer(V, T, np.arange(len(T)), ref.view)
                md.extend(BPR.plant_cards(ref, P, zb, keep, copies=((55, 0.9), (-60, 0.85)) if lod == 0 else ((70, 0.9),)))
            ob = pblend.obj_from_mesh(f"{ASSET}_{vn}_LOD{lod}", md, [mats[spc["tex"]], fol])
            objs.append(ob)
            info[vn][f"LOD{lod}"] = dict(tris=md.tris())
        built[vn] = objs
        print(f"[{ASSET}] {vn}: " + ", ".join(f"LOD{l}={info[vn][f'LOD{l}']['tris']}" for l in range(3)) +
              f" {report[vn]}", flush=True)
    # ------------------------------------------------------------ QA
    pblend.setup_render(16)
    allobjs = [o for v in built.values() for o in v]
    metrics = {"report": report}
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
    import glbx
    out = os.path.join(RT, f"{ASSET}.glb")
    glbx.externalize(out, {f"lf_rock_quarry_{s_}": f"lf_rock_quarry_{s_}.{'jpg' if s_ == 'c' else 'png'}"
                           for s_ in ("c", "n", "r")})
    import json as _json
    mp = os.path.join(RT, f"{ASSET}.meta.json")
    meta = _json.load(open(mp))
    meta["glb_images"] = glbx.info(out)["images"]
    meta["textures"].update({"lf_rock_quarry_c.jpg": 1024, "lf_rock_quarry_n.png": 1024, "lf_rock_quarry_r.png": 1024})
    meta["generation"] = ("v2: SDF fractured limestone mound (Voronoi cells seeded at the painted art/02 blocks, crack gap "
                          "6 cm, rounded edges, rough faces); front row = projected painting, sides = quilted painted "
                          "limestone, up faces = painted moss; v2/v3 in an art/01 quarry palette copy")
    meta["rockReport"] = report
    meta["build"] = "python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/paint3d/build_rock.py"
    core.write_json(mp, meta)
    print(f"[{ASSET}] exported ({time.time() - t0:.1f}s)", flush=True)


if __name__ == "__main__":
    main()
