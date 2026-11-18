"""Moss rock + fallen trunk (art/02 middle row) as inflated painted forms.

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/paint3d/build_props.py <moss_rock|fallen_trunk>
        [--iter N]
Rock: limestone segmented into blocks along the dark cracks, each inflated as a flat-faced slab (mesa profile,
bevelled edges, per-block depth offset); front/back faces = the painting (back mirrored), sides = painted
limestone swatch, tops = painted moss swatch; orange plants = painted clump cards.
Trunk: the log + root plate inflated round (distance transform), the stream arch kept open; v3_stream adds the
painted stream stones as slabs.
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
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from scipy import ndimage as ndi  # noqa: E402
from skimage import feature, morphology, segmentation  # noqa: E402
from frlib import core, paths, refs, texproj, render as frr  # noqa: E402

import geom  # noqa: E402
import prism  # noqa: E402
import p3atlas as atl  # noqa: E402
import seg  # noqa: E402
import slab  # noqa: E402
import tree  # noqa: E402
import species as SP  # noqa: E402
import build_tree as BT  # noqa: E402

RT = os.path.join(paths.RUNTIME, "forest")
SHEET = "02_forest_modular_kit.png"
PPM_MID = 40.0
ELEV_MID = 8.0
K = 0.35

CFG = {
    "moss_rock": dict(box=(470, 480, 892, 728), human=(470, 590, 515, 700), clip=220, ground=232, elev=9.4,
                      side_sw=(600, 568, 720, 668), top_sw=(604, 524, 652, 545), tex="lf_rock_limestone"),
    "fallen_trunk": dict(box=(0, 520, 470, 740), human=(0, 580, 50, 690), clip=148, ground=180,
                         side_sw=(100, 615, 230, 650), top_sw=(130, 596, 200, 612), tex="lf_bark_fallen"),
}


def make_ref(name):
    c = CFG[name]
    S = seg.sheet(SHEET)
    bg = seg.bg_colour(S)
    x0, y0, x1, y1 = c["box"]
    img = S[y0:y1, x0:x1].astype(np.float32)
    hx = (c["human"][0] - x0, c["human"][1] - y0, c["human"][2] - x0, c["human"][3] - y0)
    fg, _ = seg.fg_mask(img, bg, thresh=10, exclude=[hx], min_area=200)
    H, W = fg.shape
    fg_clip = fg.copy()
    fg_clip[c["clip"]:] = False
    lab = seg.lab(ndi.gaussian_filter(img, (1.0, 1.0, 0)))
    Cc = np.hypot(lab[..., 1], lab[..., 2])
    Hh = np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) % 360
    ys, xs = np.nonzero(fg_clip)
    cx = float(xs.mean())
    view = refs.View(name=name, image=img, mask=fg_clip, d=geom.elevated_dir(c.get("elev", ELEV_MID)), ppm=PPM_MID, ax=cx,
                     ay=float(c["ground"]))
    return types.SimpleNamespace(name=name, img=img, fg_full=fg, fg=fg_clip, H=H, W=W, clip=c["clip"],
                                 ground=c["ground"], view=view, ppm=PPM_MID, bg=bg, L=lab[..., 0], C=Cc, Hu=Hh, cfg=c)


def blocks_of(ref, body, min_dist=16, min_area=450, face_L=44):
    """Limestone blocks: markers = bright stone faces (distance-transform peaks), watershed on the smoothed
    luminance (dark cracks / shadow lines become the boundaries)."""
    faces = body & (ref.L > face_L)
    faces = ndi.binary_opening(faces, structure=morphology.disk(2))
    dt = ndi.distance_transform_edt(faces)
    pk = feature.peak_local_max(dt, min_distance=min_dist, threshold_abs=4, labels=morphology.label(faces),
                                exclude_border=False)
    mk = np.zeros(body.shape, np.int32)
    for i, (y, x) in enumerate(pk):
        mk[y, x] = i + 1
    Ls = ndi.gaussian_filter(ref.L, 1.5)
    lbl = segmentation.watershed(-Ls, mk, mask=body, compactness=0.002)
    lbl = seg.merge_small(lbl, min_area)
    return seg.relabel(lbl)


def inflate_slab(ref, mask, t_off_m, k=1.6, dmax_frac=0.42, back=0.85, voxel=2.0, body_depth=None):
    h = slab.slab_depth(mask, k=k, dmax_frac=dmax_frac)
    if body_depth is not None:
        # block = a piece of the thick outcrop: flat bevelled front face, depth of the whole mass behind it
        dt = ndi.distance_transform_edt(mask)
        h = np.minimum(np.minimum(k * dt + 2.0, body_depth), body_depth) * mask
        h = ndi.gaussian_filter(h, 0.8) * mask
    t0 = np.full(mask.shape, t_off_m * ref.ppm)
    V, F = geom.inflate(mask, ref.view, voxel_px=voxel, depth_px=h, back_scale=back, t_offset_px=t0, smooth=0)
    return V, F


def inflate_round(ref, mask, kd=0.85, voxel=2.0):
    V, F = geom.inflate(mask, ref.view, voxel_px=voxel, depth_scale=kd, smooth=1.0)
    return V, F


def to_obj(name, V, F):
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], F.tolist())
    me.validate()
    o = bpy.data.objects.new(name, me)
    core.link(o)
    return o


def decimate(o, target):
    n = core.tri_count(o)
    if n > target:
        m = o.modifiers.new("dec", "DECIMATE")
        m.ratio = max(0.01, target / n)
        m.use_collapse_triangulate = True
        core.select_only([o])
        bpy.ops.object.modifier_apply(modifier="dec")
    return o


def smooth(o, it=2, f=0.5):
    m = o.modifiers.new("sm", "SMOOTH")
    m.iterations = it
    m.factor = f
    core.select_only([o])
    bpy.ops.object.modifier_apply(modifier="sm")


def arrays(o):
    V, T, UV, N = core.mesh_arrays(o, evaluated=False, world=True)
    return V, T, N


def plant_cards(ref, P, zb, idx, ao=1.0, copies=((55, 0.9), (-60, 0.85)), rng=None):
    """Projectively fitted painted plant cards at the rock surface depth + 2 crossed copies behind each."""
    rng = rng or np.random.default_rng(3)
    md = geom.Mesh()
    for i in idx:
        x0, y0, x1, y1 = P.rects[i]
        cu, cv_ = P.info[i]["c"]
        ui, vi = int(np.clip(cu, 0, ref.W - 1)), int(np.clip(cv_, 0, ref.H - 1))
        t = (zb[vi, ui] - 0.08) if np.isfinite(zb[vi, ui]) else 0.0
        n = geom.nrm(-ref.view.d + np.array([0, 0, 0.25]))
        V, T, UV, _, N = geom.front_card(ref.view, (x0, y0, x1, y1), (cu, cv_), t, n, P.uv[i], np.zeros(4))
        C = np.tile([0.6, 0.8, rng.random(), ao], (4, 1))
        C[:2, 0] = 0.1
        md.add(V, T, UV, C, N, 1)
        cen = V.mean(0)
        base = cen.copy()
        base[2] = V[:, 2].min()
        for ang, sc in copies:
            R = geom.rot_z(math.radians(ang))
            V2 = ((V - base) * sc) @ R.T + base + ref.view.d * 0.25
            md.add(V2, T, UV, C, N @ R.T, 1)
    return md


def build(name, it):
    t0 = time.time()
    ref = make_ref(name)
    c = ref.cfg
    asset = f"lf_env_{name}"
    qa = lambda n: BT.qa_path(asset, it, n)  # noqa: E731
    rng = np.random.default_rng(11)
    if name == "moss_rock":
        plants = ref.fg & (ref.Hu < 64) & (ref.C > 26)
        plants = ndi.binary_opening(plants, iterations=1)
        body0 = ndi.binary_fill_holes(ndi.binary_closing(ref.fg & ~plants, structure=morphology.disk(2))) & ref.fg
        body0 = morphology.remove_small_objects(body0, max_size=300)
        # plants that lie inside the rock body are painted on the stone (texture); peripheral ones become cards
        plants_card = plants & ~ndi.binary_erosion(body0, iterations=3)
        body = body0 | (plants & ndi.binary_erosion(body0, iterations=3))
        lbl = blocks_of(ref, body)
        paint_mask = ref.fg & ~plants_card
    else:
        plants_card = np.zeros_like(ref.fg)
        body = ndi.binary_fill_holes(ndi.binary_closing(ref.fg, structure=morphology.disk(2))) & ref.fg_full
        body[ref.clip:] = False
        body = morphology.remove_small_objects(body, max_size=300)
        lbl = body.astype(np.int32)
        paint_mask = ref.fg.copy()
        # stream stones (below the trunk clip row): low-chroma blobs in the ground band
        stones = ref.fg_full & (ref.C < 24) & (ref.L > 40) & (np.arange(ref.H)[:, None] >= ref.clip + 6)
        stones = ndi.binary_opening(stones, structure=morphology.disk(2))
        stones = morphology.remove_small_objects(stones, max_size=120)
        st_lbl = seg.relabel(morphology.label(stones))
    nb = int(lbl.max())
    seg.save(qa("masks.png"), np.concatenate([seg.overlay(ref.img, [(plants_card, (0.9, 0.4, 0.1))], 0.5),
                                              seg.label_preview(lbl, ref.img, 0.5)], 1))
    print(f"[{asset}] blocks {nb} plants {plants_card.sum()} ({time.time() - t0:.1f}s)", flush=True)
    # ---------------------------------------------------------------- texture
    S = seg.sheet(SHEET)
    sx0, sy0, sx1, sy1 = c["side_sw"]
    tx0, ty0, tx1, ty1 = c["top_sw"]
    side_sw = S[sy0:sy1, sx0:sx1].astype(np.float32)
    top_sw = S[ty0:ty1, tx0:tx1].astype(np.float32)
    tex_clip = ref.clip if name == "moss_rock" else ref.H
    pm = paint_mask if name == "moss_rock" else (paint_mask | (ref.fg_full & (st_lbl > 0)))
    tex = slab.assemble(1024, ref.img, pm, tex_clip, side_sw, top_sw, side_scale=1.6, top_scale=1.6)
    log_parts = straight_log_parts(ref, tex, tex_clip) if name == "fallen_trunk" else None
    cpath = os.path.join(RT, f"{c['tex']}_c.jpg")
    cv2.imwrite(cpath, cv2.cvtColor((tex * 255).astype(np.uint8), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])
    nmap, rmap = tree.bark_maps(tex)
    npath = os.path.join(RT, f"{c['tex']}_n.png")
    rpath = os.path.join(RT, f"{c['tex']}_r.png")
    seg.save(npath, nmap)
    seg.save(rpath, np.stack([rmap] * 3, -1))
    seg.save(qa("tex.png"), tex)
    # ---------------------------------------------------------------- plants (cards)
    P = None
    if plants_card.sum() > 200:
        pref = types.SimpleNamespace(img=ref.img, fg=plants_card, wood_cov=np.zeros_like(plants_card),
                                     crown_rows=(0, ref.H - 1), xc=np.full(ref.H, ref.W / 2.0), R=np.full(ref.H, ref.W / 2.0),
                                     H=ref.H, W=ref.W, ppm=ref.ppm, bg=ref.bg)
        P = tree.Patches(pref, n_target=40, min_px=30, margin=2, scale=2)
        reg, s = P.pack("rock_plants")
        atl.save_region("rock_plants", reg, {"asset": asset, "tiles": P.n, "scale": s})
    atlas_path = atl.assemble()
    # ---------------------------------------------------------------- geometry per block
    core.reset()
    blocks = []
    body_depth = None
    if name == "moss_rock":
        # outcrop mass depth: mesa profile of the whole body (deep, flat-backed) ~ 0.5 x its height
        rows = np.nonzero(body.any(1))[0]
        body_depth = slab.slab_depth(body, k=1.3, dmax_px=0.55 * (rows.max() - rows.min()), smooth=2.0)
    for b in range(1, nb + 1):
        m = lbl == b
        if m.sum() < 150:
            continue
        if name == "moss_rock":
            top_like = (((ref.Hu > 75) & (ref.Hu < 118) & (ref.C > 14)) | (ref.L > 64))
            mg = ndi.binary_dilation(m, iterations=3) & ndi.binary_dilation(ref.fg, iterations=1)
            res_ = prism.block_solid(ref.view, mg, top_like, ref.ppm, c["elev"], y0=rng.uniform(-0.15, 0.15), rng=rng)
            if res_ is None:
                continue
            V, F, binfo = res_
        else:
            V, F = inflate_round(ref, m, kd=1.0)
        if len(F) == 0:
            continue
        o = to_obj(f"blk{b}", V, F)
        if name != "moss_rock":
            smooth(o, 1, 0.4)
        ys, xs = np.nonzero(m)
        blocks.append(dict(obj=o, area=int(m.sum()), cx=float(xs.mean()), cy=float(ys.mean()), kind="body"))
    if name == "fallen_trunk":
        for b in range(1, int(st_lbl.max()) + 1):
            m = st_lbl == b
            if m.sum() < 120:
                continue
            V, F = inflate_round(ref, m, kd=0.8)
            o = to_obj(f"stone{b}", V, F)
            smooth(o, 2, 0.5)
            ys, xs = np.nonzero(m)
            blocks.append(dict(obj=o, area=int(m.sum()), cx=float(xs.mean()), cy=float(ys.mean()), kind="stone"))
    tot_area = sum(b_["area"] for b_ in blocks if b_["kind"] == "body")
    budget0 = 2600 if name == "moss_rock" else 2300
    for b_ in blocks:
        share = b_["area"] / max(tot_area, 1) if b_["kind"] == "body" else 0.0
        decimate(b_["obj"], max(60, int(budget0 * share)) if b_["kind"] == "body" else 80)
    # z-buffer of all body blocks (plant card depth)
    allV, allT = [], []
    base = 0
    for b_ in blocks:
        V, T, N = arrays(b_["obj"])
        allV.append(V)
        allT.append(T + base)
        base += len(V)
    Vz = np.concatenate(allV)
    Tz = np.concatenate(allT)
    _, zb = tree.tri_id_buffer(Vz, Tz, np.arange(len(Tz)), ref.view)
    zb = np.where(np.isfinite(zb), zb, np.nan)
    zb = np.where(np.isnan(zb), np.inf, zb)
    # ---------------------------------------------------------------- variants
    rock_mat = pblend.export_material(c["tex"], cpath, normal_path=npath, rough_path=rpath)
    fol = pblend.export_material("lf_foliage", atlas_path, alpha_clip=0.5, double_sided=True)
    mats = [rock_mat, fol]
    body_blocks = [b_ for b_ in blocks if b_["kind"] == "body"]
    if name == "moss_rock":
        xs_ = np.array([b_["cx"] for b_ in body_blocks])
        ys_ = np.array([b_["cy"] for b_ in body_blocks])
        big = int(np.argmax([b_["area"] for b_ in body_blocks]))
        left = [i for i in range(len(body_blocks)) if xs_[i] < 0.55 * ref.W]
        right = [i for i in range(len(body_blocks)) if xs_[i] >= 0.5 * ref.W]
        variants = {
            "v1": dict(blocks=list(range(len(body_blocks))), plants=True),
            # compact boulders: a painted block group + a copy of it rotated behind (outcrop depth ~ width)
            "v2": dict(blocks=left, plants=True, center=True),
            "v3": dict(blocks=right, plants=True, center=True, mirror=True),
        }
    else:
        variants = {
            "v1": dict(blocks=list(range(len(body_blocks))), stones=False, flatten=True, mirror=True),
            "v2": dict(blocks=list(range(len(body_blocks))), stones=False, cut_x=0.36, center=True, flatten=True),
            "v3_stream": dict(blocks=list(range(len(body_blocks))), stones=True),
        }
    built = {}
    info = {}
    for vn, vd in variants.items():
        objs = []
        info[vn] = {}
        if log_parts is not None and vd.get("flatten"):
            for lod in range(3):
                md = straight_log(log_parts, lod, seed=7 + len(vn), short=bool(vd.get("cut_x")))
                if vd.get("mirror"):
                    md = md.transformed(mirror_x=True)
                o = pblend.obj_from_mesh(f"{asset}_{vn}_LOD{lod}", md, mats)
                objs.append(o)
                info[vn][f"LOD{lod}"] = dict(tris=md.tris())
            built[vn] = objs
            print(f"[{asset}] {vn}: " + ", ".join(f"LOD{l}={info[vn][f'LOD{l}']['tris']}" for l in range(3)), flush=True)
            continue
        for lod, frac in ((0, 1.0), (1, 0.38), (2, 0.11)):
          for attempt in range(6):
              md = geom.Mesh()
              parts = [body_blocks[i] for i in vd["blocks"]] + \
                  ([b_ for b_ in blocks if b_["kind"] == "stone"] if vd.get("stones") else [])
              if lod == 2:
                  amax = max(b_["area"] for b_ in parts)
                  parts = [b_ for b_ in parts if b_["area"] >= (0.22 if vd.get("rot_copy") else 0.05) * amax]
              for b_ in parts:
                  o = b_["obj"]
                  if frac < 1.0:
                      oc = o.copy()
                      oc.data = o.data.copy()
                      core.link(oc)
                      decimate(oc, max(8 if lod == 2 else 30, int(core.tri_count(o) * frac)))
                      V, T, N = arrays(oc)
                      bpy.data.objects.remove(oc, do_unlink=True)
                  else:
                      V, T, N = arrays(o)
                  if name == "moss_rock":
                      fnrm = geom.nrm(np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]))
                      Vu, Tu, UVu, Nu, kind = slab.planar_uvs(V, T, N, ref.view, ref.W, ref.H, tex_clip,
                                                              per_side=7.5, per_top=7.5)
                      Nu = np.repeat(fnrm, 3, axis=0)
                  else:
                      Vu, Tu, UVu, Nu, kind = slab.planar_uvs(V, T, N, ref.view, ref.W, ref.H, tex_clip)
                  Cw = np.zeros((len(Vu), 4))
                  Cw[:, 3] = np.where(np.isin(np.repeat(kind, 3), (2, 3)), 1.0, 0.9)
                  md.add(Vu, Tu, UVu, Cw, Nu, 0)
              if name == "moss_rock" and vd.get("plants") and P is not None and lod < 2:
                  keep = []
                  bx = [body_blocks[i] for i in vd["blocks"]]
                  for i in range(P.n):
                      cu, cv_ = P.info[i]["c"]
                      if min(abs(cu - b_["cx"]) + 0.5 * abs(cv_ - b_["cy"]) for b_ in bx) < 70:
                          keep.append(i)
                  if lod == 1:
                      keep = sorted(keep, key=lambda i: -P.info[i]["area"])[: max(1, len(keep) // 2)]
                  md.extend(plant_cards(ref, P, zb, keep, copies=((55, 0.9), (-60, 0.85)) if lod == 0 else ((70, 0.9),)))
              if vd.get("flatten"):
                  # lay the log on the ground along its whole length: remove the painted stream arch
                  Vv, Tt, UVv, Cc, Nn, Mm = md.arrays()
                  xs_v = Vv[:, 0]
                  bins = np.linspace(xs_v.min(), xs_v.max(), 40)
                  idx = np.clip(np.digitize(xs_v, bins) - 1, 0, len(bins) - 2)
                  bottom = np.full(len(bins) - 1, np.nan)
                  for bi in range(len(bins) - 1):
                      sel = idx == bi
                      if sel.any():
                          bottom[bi] = Vv[sel, 2].min()
                  ok_ = ~np.isnan(bottom)
                  bottom = np.interp(np.arange(len(bottom)), np.nonzero(ok_)[0], bottom[ok_])
                  sink = 0.08
                  off = np.clip(bottom + sink, 0, None)
                  off = ndi.gaussian_filter1d(off, 1.5)
                  # the root plate (ends that already reach the ground) keeps its height -> tilted up
                  dz = off[idx]
                  md = geom.Mesh()
                  md.add(Vv - np.stack([np.zeros_like(dz), np.zeros_like(dz), dz], 1), Tt, UVv, Cc, Nn, 0)
                  md.M = [Mm]
              if vd.get("rot_copy"):
                  ang, sc = vd["rot_copy"]
                  Vv, Tt, UVv, Cc, Nn, Mm = md.arrays()
                  used = np.unique(Tt)
                  cen = Vv[used].mean(0)
                  cen[2] = 0.0
                  R = geom.rot_z(math.radians(ang))
                  V2 = ((Vv - cen) * sc) @ R.T + cen - ref.view.d * 0.0 + np.array([0, 0, 0]) 
                  V2 = V2 + (R @ np.array([0.0, 1.0, 0.0])) * 0.0
                  md2 = geom.Mesh()
                  md2.add(V2 + np.array([0.0, 0.6 * np.ptp(Vv[used][:, 0]) * 0.25, 0.0]), Tt, UVv, Cc, Nn @ R.T, 0)
                  md2.M = [Mm]
                  md.extend(md2)
              if vd.get("cut_x"):
                  # shorter log: keep the part right of cut_x (fraction of the crop width) -> drop root plate
                  Vv, Tt, UVv, Cc, Nn, Mm = md.arrays()
                  xcut = geom.pix_to_world(ref.view, np.array([vd["cut_x"] * ref.W]), np.array([0.0]), np.array([0.0]))[0][0]
                  keep_t = Vv[Tt].mean(1)[:, 0] > xcut
                  md = geom.Mesh()
                  md.add(Vv, Tt[keep_t], UVv, Cc, Nn, 0)
                  md.M = [Mm[keep_t]]
              if vd.get("mirror"):
                  md = md.transformed(mirror_x=True)
              Vv, Tt, UVv, Cc, Nn, Mm = md.arrays()
              if vd.get("center") and len(Vv):
                  used = np.unique(Tt)
                  off = Vv[used].mean(0)
                  off[2] = 0.0
                  md = geom.Mesh()
                  md.add(Vv - off, Tt, UVv, Cc, Nn, 0)
                  md.M = [Mm]
              budget = (4000, 1500, 290)[lod]
              if md.tris() <= budget or lod == 0:
                  break
              frac *= 0.8 * budget / max(md.tris(), 1)
          o = pblend.obj_from_mesh(f"{asset}_{vn}_LOD{lod}", md, mats)
          objs.append(o)
          info[vn][f"LOD{lod}"] = dict(tris=md.tris())
        built[vn] = objs
        print(f"[{asset}] {vn}: " + ", ".join(f"LOD{l}={info[vn][f'LOD{l}']['tris']}" for l in range(3)), flush=True)
    for b_ in blocks:
        bpy.data.objects.remove(b_["obj"], do_unlink=True)
    # ---------------------------------------------------------------- QA
    pblend.setup_render(16)
    allobjs = [o for v in built.values() for o in v]
    metrics = {}
    for lod in range(3):
        for kk, tag in ((K, "painted"), (0.0, "albedo")):
            if lod > 0 and tag == "albedo":
                continue
            pblend.use_painted(allobjs, kk)
            cmp_v = "v3_stream" if name == "fallen_trunk" else "v1"
            rgba = pblend.render_view(ref.view, [built[cmp_v][lod]])
            rgba[ref.clip:, :, 3] = 0
            mm = pblend.compare_sheet(ref.img, ref.fg, rgba, ref.bg, qa(f"front_{cmp_v}_LOD{lod}_{tag}.png"),
                                      f"{asset} {cmp_v} LOD{lod} vs art/02 ({tag} k={kk}) iter {it}")
            metrics[f"{cmp_v}_LOD{lod}_{tag}"] = mm
            print(f"[{asset}] LOD{lod} {tag}: {mm}", flush=True)
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
        pblend.save_shot(frr.render_rgba(), qa(f"{nm_}.png"), text=f"{asset} variants {nm_}")
    for o in lineup:
        o.location.x = 0
    bpy.context.view_layer.update()
    core.write_json(qa("metrics.json"), {"metrics": metrics, "lods": info})
    pblend.use_painted(allobjs, K, on=False)
    export(asset, built, info, c["tex"])
    print(f"[{asset}] exported ({time.time() - t0:.1f}s)", flush=True)


def straight_log_parts(ref, tex, tex_clip):
    """Painted log strip (EXTRA band of the texture) + root plate measurements from the art/02 fallen trunk."""
    import logbuild
    m = ref.fg.copy()
    cols = np.nonzero(m.any(0))[0]
    x0, x1 = cols.min(), cols.max()
    # root plate = the tall left mass; log body = columns whose painted height is close to the median log height
    hgt = np.array([np.ptp(np.nonzero(m[:, x])[0]) + 1 if m[:, x].any() else 0 for x in range(ref.W)])
    med = np.median(hgt[x0:x1])
    tall = np.nonzero(hgt > 1.6 * med)[0]
    x_root = int(tall[tall < (x0 + x1) / 2].max()) + 4 if len(tall[tall < (x0 + x1) / 2]) else x0 + 10
    x_end = x1 - 4
    xs, cs, rs = logbuild.painted_log(ref.img, m, x_root, x_end)
    TEX = tex.shape[0]
    ex0, ey0, ex1, ey1 = int(slab.EXTRA[0] * TEX), int((1 - slab.EXTRA[3]) * TEX), int(slab.EXTRA[2] * TEX), int((1 - slab.EXTRA[1]) * TEX)
    strip = logbuild.unwrap_strip(ref.img, xs, cs, rs, ex1 - ex0, int((ey1 - ey0) * 0.72))
    tex[ey0:ey0 + strip.shape[0], ex0:ex1] = strip
    # root-plate face texture: painted root mass pixels quilted into the rest of the EXTRA band
    root = ref.img[:, max(0, x0):x_root]
    rmask = m[:, max(0, x0):x_root]
    rf = texproj.fill(root.astype(np.float64), rmask).astype(np.float32) if rmask.any() else root
    rh = (ey1 - ey0) - strip.shape[0]
    rface = cv2.resize(rf[np.nonzero(rmask.any(1))[0].min():np.nonzero(rmask.any(1))[0].max() + 1], (rh, rh))
    tex[ey0 + strip.shape[0]:ey1, ex0:ex0 + rh] = rface
    tex[ey0 + strip.shape[0]:ey1, ex0 + rh:ex0 + 2 * rh] = rface[:, ::-1]
    S_ = TEX
    uv_strip = (ex0 / S_, 1 - (ey0 + strip.shape[0]) / S_, ex1 / S_, 1 - ey0 / S_)
    uv_root_face = (ex0 / S_, 1 - ey1 / S_, (ex0 + rh) / S_, 1 - (ey0 + strip.shape[0]) / S_)
    uv_root_rim = ((ex0 + rh) / S_, 1 - ey1 / S_, (ex0 + 2 * rh) / S_, 1 - (ey0 + strip.shape[0]) / S_)
    radius = float(np.median(rs)) / ref.ppm
    length = float(xs[-1] - xs[0]) / ref.ppm
    root_r = 0.5 * float(med * 1.9) / ref.ppm
    return dict(uv_strip=uv_strip, uv_root_face=uv_root_face, uv_root_rim=uv_root_rim, radius=max(0.42, radius),
                length=length, root_r=float(np.clip(root_r, 1.25, 1.5)))


def straight_log(parts, lod, seed=0, short=False):
    import logbuild
    segs_len, segs_rad, n_root = ((26, 12, 18), (12, 8, 12), (5, 5, 8))[lod]
    L = parts["length"] * (0.62 if short else 1.0)
    V, T, UV, N, r = logbuild.log_mesh(L, parts["radius"], parts["uv_strip"], segs_len, segs_rad, seed=seed)
    md = geom.Mesh()
    C = np.zeros((len(V), 4))
    C[:, 3] = 0.95
    md.add(V, T, UV, C, N, 0)
    if not short:
        Vr, Tr, UVr, Nr = logbuild.root_plate(np.array([-0.15, 0.0, parts["root_r"] * 0.85]), parts["root_r"],
                                             0.7, parts["uv_root_rim"], parts["uv_root_face"], n=n_root, seed=seed)
        Cr = np.zeros((len(Vr), 4))
        Cr[:, 3] = 0.9
        md.add(Vr, Tr, UVr, Cr, Nr, 0)
    if lod < 2:
        end = np.array([L, 0.0, r[-1] - 0.06])
        Vs, Ts, UVs, Ns = logbuild.splinters(end, r[-1], parts["uv_strip"], n=7 if lod == 0 else 4, seed=seed)
        Cs = np.zeros((len(Vs), 4))
        Cs[:, 3] = 0.85
        md.add(Vs, Ts, UVs, Cs, Ns, 0)
    Vv, Tt, UVv, Cc, Nn, Mm = md.arrays()
    off = np.array([0.5 * L, 0.0, 0.0])
    out = geom.Mesh()
    out.add(Vv - off, Tt, UVv, Cc, Nn, 0)
    out.M = [Mm]
    return out


def export(asset, built, info, texname):
    import glbx
    root = bpy.data.objects.new(asset, None)
    core.link(root)
    spacing = 0.0
    for v, objs in built.items():
        lo, hi = core.bounds([objs[0]])
        spacing = max(spacing, hi[0] - lo[0], hi[1] - lo[1])
    spacing += 2.0
    export_objs = [root]
    meta_vars = {}
    for i, (vn, objs) in enumerate(built.items()):
        ve = bpy.data.objects.new(f"{asset}_{vn}", None)
        core.link(ve)
        ve.parent = root
        ve.location = (i * spacing, 0, 0)
        export_objs.append(ve)
        for o in objs:
            o.parent = ve
            o.location = (0, 0, 0)
            export_objs.append(o)
        bpy.context.view_layer.update()
        lo, hi = core.bounds([objs[0]])
        lo = lo - np.array([i * spacing, 0, 0])
        hi = hi - np.array([i * spacing, 0, 0])
        meta_vars[vn] = {"nodes": [o.name for o in objs],
                         "tris": {f"LOD{l}": core.tri_count(objs[l]) for l in range(3)},
                         "materials": {f"LOD{l}": [m.name for m in objs[l].data.materials if m] for l in range(3)},
                         "height_m": round(float(hi[2]), 2),
                         "footprint_radius_m": round(float(max(-lo[0], hi[0], -lo[1], hi[1])), 2),
                         "bounds_m_blender": [np.round(lo, 2).tolist(), np.round(hi, 2).tolist()],
                         "display_offset_gltf": [round(i * spacing, 3), 0.0, 0.0],
                         "heightM": round(float(hi[2]), 2),
                         "footprintM": [round(float(hi[0] - lo[0]), 2), round(float(hi[1] - lo[1]), 2)]}
    out = os.path.join(RT, f"{asset}.glb")
    ext = {"lf_foliage_atlas": "lf_foliage_atlas.png", f"{texname}_c": f"{texname}_c.jpg",
           f"{texname}_n": f"{texname}_n.png", f"{texname}_r": f"{texname}_r.png"}
    core.export_glb(out, export_objs, animations=False,
                    extra=dict(export_vertex_color="ACTIVE", export_all_vertex_colors=False,
                               export_active_vertex_color_when_no_material=False, export_image_format="AUTO"))
    glbx.externalize(out, ext)
    gi = glbx.info(out)
    meta = {"id": asset, "generation": "v2 image-based reconstruction from art/02 (solid painted blocks / logs)",
            "heightM": max(mv["heightM"] for mv in meta_vars.values()),
            "footprintM": [max(mv["footprintM"][0] for mv in meta_vars.values()),
                           max(mv["footprintM"][1] for mv in meta_vars.values())],
            "scaleNote": "real metres from the 1.8 m figure on art/02 (understory without a figure: realistic "
                         "height, see build script); world layer should respect heightM instead of normalising",
            "variants": meta_vars,
            "tris": {f"LOD{l}": max(mv["tris"][f"LOD{l}"] for mv in meta_vars.values()) for l in range(3)},
            "bones": 0, "materials": sorted(set(gi["materials"])), "glb_images": gi["images"],
            "textures": {f"{texname}_c.jpg": 1024, f"{texname}_n.png": 1024, f"{texname}_r.png": 1024,
                         "lf_foliage_atlas.png": 2048},
            "paintedLightMix": K,
            "paintedLightNote": "Texture = the painting (front/back), painted swatches on sides/tops. Shade as "
                                "albedo * mix(1, lambert, paintedLightMix).",
            "wind": {"attribute": "COLOR_0", "R": "0 (static); plant cards 0.1-0.6", "G": "plant flutter",
                     "B": "phase", "A": "AO"},
            "layout_note": "Variants laid out along +X (display_offset_gltf); the LODs of a variant share its origin.",
            "collision": [{"type": "box", "centre": [0.0, round(meta_vars[v]["height_m"] / 2, 2), 0.0],
                           "size": [round(meta_vars[v]["bounds_m_blender"][1][0] - meta_vars[v]["bounds_m_blender"][0][0], 2),
                                    round(meta_vars[v]["height_m"], 2),
                                    round(meta_vars[v]["bounds_m_blender"][1][1] - meta_vars[v]["bounds_m_blender"][0][1], 2)],
                           "variant": v} for v in meta_vars],
            "build": f"python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/paint3d/build_props.py "
                     f"{asset.replace('lf_env_', '')}"}
    core.write_json(os.path.join(RT, f"{asset}.meta.json"), meta)
    core.save_blend(paths.source("forest", f"{asset}.blend"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--iter", type=int, default=1)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    build(a.name, a.iter)
