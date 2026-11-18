"""Image-based tree build (art/02): python3 forest_rescue/blender/run_limited.py \
    forest_rescue/blender/assets/paint3d/build_tree.py <species> [--iter N] [--no-export] [--qa light|full]

Outputs: godot/project/assets/forest_rescue/forest/lf_env_<species>.glb + .meta.json, shared
lf_foliage_atlas.png region, lf_bark_<kind>_{c.jpg,n.png,r.png}; .blend in sources/forest;
QA in forest_rescue/qa/compare/lf_env_<species>/v2_iterNN_*.
"""
import argparse
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pblend  # noqa: E402  (sets frlib path)
import bpy  # noqa: E402
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from frlib import core, paths  # noqa: E402

import p3atlas as atl  # noqa: E402
import geom  # noqa: E402
import seg  # noqa: E402
import tree  # noqa: E402
import species as SP  # noqa: E402

RT = os.path.join(paths.RUNTIME, "forest")
TEXM = paths.ensure(paths.TEXTURE_SOURCES, "forest", "v2")


def qa_path(asset, it, name):
    return paths.compare(asset, f"v2_iter{it:02d}_{name}")


def bark_layout(paths_, ppm, size=1024, fill=0.80):
    sizes = []
    for p in paths_:
        L = float(np.linalg.norm(np.diff(p["P"], axis=0), axis=1).sum())
        circ = 2 * math.pi * float(np.max(p["r"]))
        sizes.append((circ, L))
    area = sum(a * b for a, b in sizes)
    dens = math.sqrt(fill * size * size / max(area, 1e-6))
    dens = min(dens, 2.4 * ppm)
    rects = [(max(4, int(a * dens)), max(4, int(b * dens))) for a, b in sizes]
    pos, s = seg.pack_rects(rects, (0, 0, size, size), pad=3)
    uv = {}
    for p, (w, h), (x, y) in zip(paths_, rects, pos):
        w2, h2 = max(2, int(w * s)), max(2, int(h * s))
        uv[p["id"]] = (x / size, 1 - (y + h2) / size, (x + w2) / size, 1 - y / size)
    return uv, dens * s


def limit_paths(paths_, budget, sides_limb, min_r_px):
    """Drop thin limbs until the limb tube triangle estimate fits the budget."""
    def est(ps, mr):
        n = 0
        for p in ps:
            if p["kind"] != "limb" or p.get("r_px", 9) < mr:
                continue
            k = len(p["P"])
            sides = sides_limb if p.get("r_px", 9) >= 2.5 else max(3, sides_limb - 2)
            n += (k - 1) * sides * 2
        return n
    mr = min_r_px
    while est(paths_, mr) > budget and mr < 12:
        mr += 0.25
    return mr, est(paths_, mr)


def simplify_path(p, step_m):
    P, r = p["P"], p["r"]
    Ps, s = geom.resample_polyline(P, step_m)
    seg_ = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    rs = np.interp(s, seg_, r)
    q = dict(p)
    q["P"], q["r"] = Ps, rs
    return q


def build_lod(B, base_paths, bark_uv, sp, lod, variant, front_all):
    ref, P = B.ref, B.p
    L = sp["lods"][lod]
    vs = sp["variants"][variant]
    # wood
    ps = []
    for p in base_paths:
        if p["kind"] == "trunk":
            q = simplify_path(p, L["trunk_step_m"])
        else:
            q = simplify_path(p, max(L["limb_step_m"], 2.2 * float(np.max(p["r"]))))
        ps.append(q)
    mr, est = limit_paths(ps, L["limb_budget"], L["limb_sides"], L["limb_min_r_px"])
    copies = []
    if L.get("copies") or sp.get("placement") == "anchors":
        axis_top = ref.axis_x[0]
        tv = geom.world_at_y(ref.view, np.array([axis_top]), np.array([float(ref.trunk_rows[0])]), np.array([0.0]))[0]
        tv[2] = 0.0
        for ang, sc in vs["copies"]:
            copies.append((geom.rot_z(math.radians(ang)), tv, False, sc))
    # cards
    if L["front_frac"] < 1.0:
        order = np.argsort([-q["area"] for q in P.info])
        keep = set(order[: max(4, int(len(order) * L["front_frac"]))].tolist())
    else:
        keep = None
    rng = np.random.default_rng(vs["seed"] * 31 + lod)
    if vs.get("drop_front", 0) > 0 and keep is None:
        n = P.n
        drop = set(rng.choice(n, int(n * vs["drop_front"]), replace=False).tolist())
        keep = set(range(n)) - drop
    fronts = B.front_cards(scale=L["front_scale"], keep=keep, seed=vs["seed"])
    dm = B.front_depth_map(front_all)
    if sp.get("crown_mode") == "mass":
        anchors = None
        if sp.get("placement") == "anchors":
            tips = [p["P"][-1] for p in base_paths if p["kind"] == "limb" and p.get("r_px", 0) >= sp.get("anchor_min_r", 1.5)]
            anchors = list(tips)
            for (Rm, tv, mir, sc) in copies:
                anchors += [((tp - tv) * sc) @ Rm.T + tv for tp in tips]
        fills = B.mass_cards(fronts, dm, size_k=L["fill_size"], seed=vs["seed"] * 7 + lod, n_masses=L["n_masses"],
                             mass_r=sp.get("mass_r", 0.34), clumps_per=L["clumps_per"],
                             front_extra_frac=L.get("front_extra", 0.6), max_cards=L.get("max_cards"),
                             core_cards=L.get("core_cards", 30), placement=sp.get("placement", "dome"),
                             anchors=anchors, curtains=L.get("curtains", 0))
    elif sp.get("crown_mode", "volume") == "volume":
        fills = B.volume_cards(L["n_clumps"], fronts, dm, size_k=L["fill_size"], seed=vs["seed"] * 7 + lod,
                               min_dist_k=L.get("min_dist_k", 0.7), front_extra_frac=L.get("front_extra", 0.65),
                               shell_pow=sp.get("shell_pow", 1.4), top_boost=sp.get("top_boost", 1.2),
                               max_cards=L.get("max_cards"))
    elif sp.get("crown_mode") == "lobes":
        fills = B.lobe_cards(L["n_fill"], dm, size_k=L["fill_size"], seed=vs["seed"] * 7 + lod,
                             n_lobes=L.get("n_lobes", sp["cfg"].get("n_lobes", 12)), lobe_r=sp.get("lobe_r", 0.32),
                             min_dist_k=L.get("min_dist_k", 0.45), inset=sp.get("lobe_inset", 0.74))
    else:
        fills = B.fill_cards(L["n_fill"], dm, size_k=L["fill_size"], seed=vs["seed"] * 7 + lod, n_inner=L["n_inner"],
                             min_dist_k=L.get("min_dist_k", 0.55))
    H = sp.get("height_hint", 12.0)
    Rc = sp.get("crown_hint", 6.0)
    bark, leaf = B.assemble(ps, fronts + fills, bark_uv, sides_trunk=L["trunk_sides"], sides_limb=L["limb_sides"],
                            min_limb_r_px=mr if L["limb_budget"] > 0 else 999, copies=copies if L.get("copies") and copies else None,
                            tree_h=H, crown_r=Rc, seed=vs["seed"], copy_min_r_px=L.get("copy_min_r_px", 0.0))
    if L["limb_budget"] <= 0:
        # trunk only
        pass
    out = geom.Mesh()
    out.extend(bark)
    out.extend(leaf)
    if vs.get("mirror"):
        out = out.transformed(mirror_x=True)
    sxy, sz = vs.get("scale", (1.0, 1.0))
    if (sxy, sz) != (1.0, 1.0):
        Vv, T, UV, C, N, M = out.arrays()
        Vv = Vv * np.array([sxy, sxy, sz])
        N = geom.nrm(N / np.array([sxy, sxy, sz]))
        o2 = geom.Mesh()
        o2.add(Vv, T, UV, C, N, 0)
        o2.M = [M]
        out = o2
    return out, dict(fronts=len(fronts), fills=len(fills), limb_min_r=round(mr, 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("species")
    ap.add_argument("--iter", type=int, default=1)
    ap.add_argument("--no-export", action="store_true")
    ap.add_argument("--qa", default="full")
    ap.add_argument("--samples", type=int, default=16)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    sp = SP.TREES[a.species]
    asset = f"lf_env_{a.species}"
    t0 = time.time()
    ref = tree.TreeRef(sp["cfg"])
    ref.masks_preview(qa_path(asset, a.iter, "masks.png"))
    P = tree.Patches(ref, n_target=sp["n_patches"], min_px=sp.get("min_px", 50), margin=sp.get("margin", 3),
                     scale=sp.get("tile_scale", 2))
    P.preview(qa_path(asset, a.iter, "patches.png"))
    reg_img, s = P.pack(sp["region"])
    atl.save_region(sp["region"], reg_img, {"asset": asset, "scale": s, "tiles": P.n})
    if sp.get("hires"):
        hr = sp["hires"]
        nh = P.add_hires(hr["region"], hr["sheet"], hr["box"], rosette_px=hr.get("rosette_px", 800),
                         m_per_px=hr.get("m_per_px"), l_shift=hr.get("l_shift", 4.0), hue=hr.get("hue", (70, 100)))
        print(f"[{asset}] hi-res top tiles: {nh}", flush=True)
    atlas_path = atl.assemble()
    print(f"[{asset}] patches={P.n} atlas_scale={s:.3f} limbs={len(ref.limbs)} ({time.time() - t0:.1f}s)", flush=True)
    B = tree.TreeBuilder(ref, P, sp["cfg"])
    base_paths = B.wood_paths()
    bark_uv, dens = bark_layout(base_paths, ref.ppm)
    front_all = B.front_cards(scale=1.0, seed=sp["variants"][1]["seed"])
    # ---------------------------------------------------------------- bark texture from v1 original wood
    orig = geom.Mesh()
    ids = []
    for p in base_paths:
        q = simplify_path(p, 0.12 if p["kind"] == "trunk" else max(0.12, 1.5 * float(np.max(p["r"]))))
        sides = 16 if p["kind"] == "trunk" else 8
        V, T, UV, C, N = geom.tube(q["P"], q["r"], sides, bark_uv[p["id"]], np.ones(4),
                                   depth_scale=p.get("depth_scale"), ref_side=ref.view.d)
        orig.add(V, T, UV, C, N, 0)
        ids += [p["id"]] * len(T)
    col, known, Tx = tree.bark_texture(ref, orig, np.array(ids), size=1024, swatch_box=sp["swatch"])
    nmap, rmap = tree.bark_maps(col)
    kind = sp["bark"]
    cpath = os.path.join(RT, f"lf_bark_{kind}_c.jpg")
    cv2.imwrite(cpath, cv2.cvtColor((col * 255).astype(np.uint8), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])
    npath = os.path.join(RT, f"lf_bark_{kind}_n.png")
    rpath = os.path.join(RT, f"lf_bark_{kind}_r.png")
    seg.save(npath, nmap)
    seg.save(rpath, np.stack([rmap] * 3, -1))
    seg.save(os.path.join(TEXM, f"lf_bark_{kind}_c_master.png"), col)
    seg.save(qa_path(asset, a.iter, "bark_known.png"), np.where(known[..., None], col, col * 0.3 + 0.2))
    print(f"[{asset}] bark texture ({known.mean():.2f} projected) ({time.time() - t0:.1f}s)", flush=True)
    # ---------------------------------------------------------------- meshes
    core.reset()
    fol = pblend.export_material("lf_foliage", atlas_path, alpha_clip=0.5, double_sided=True)
    bark = pblend.export_material(f"lf_bark_{kind}", cpath, normal_path=npath, rough_path=rpath)
    fol_vol = pblend.export_material("lf_foliage_vol", atlas_path, alpha_clip=0.5, double_sided=True) \
        if sp["cfg"].get("vol_material") else fol
    built = {}
    info = {}
    for vi in sorted(sp["variants"]):
        objs = []
        info[vi] = {}
        for lod in range(3):
            m, st = build_lod(B, base_paths, bark_uv, sp, lod, vi, front_all)
            o = pblend.obj_from_mesh(f"{asset}_v{vi}_LOD{lod}", m, [bark, fol, fol_vol] if fol_vol is not fol else [bark, fol])
            objs.append(o)
            info[vi][f"LOD{lod}"] = dict(tris=m.tris(), **st)
        built[vi] = objs
        print(f"[{asset}] v{vi}: " + ", ".join(f"LOD{l}={info[vi][f'LOD{l}']['tris']}" for l in range(3)), flush=True)
    # ---------------------------------------------------------------- QA
    k = sp.get("paintedLightMix", 0.4)
    pblend.KMAP.update(sp.get("paintedLightMixByMaterial", {}))
    pblend.setup_render(a.samples)
    allobjs = [o for v in built.values() for o in v]
    metrics = {}
    bg = ref.bg
    v1 = built[1]
    for lod in range(3):
        for kk, tag in ((k, "painted"), (0.0, "albedo")):
            if lod > 0 and tag == "albedo":
                continue
            pblend.use_painted(allobjs, kk)
            rgba = pblend.render_view(ref.view, [v1[lod]])
            rgba[ref.clip:, :, 3] = 0
            mm = pblend.compare_sheet(ref.img, ref.fg, rgba, bg, qa_path(asset, a.iter, f"front_v1_LOD{lod}_{tag}.png"),
                                      f"{asset} v1 LOD{lod} vs art/02 ({tag} k={kk}) iter {a.iter}")
            metrics[f"v1_LOD{lod}_{tag}"] = mm
            print(f"[{asset}] LOD{lod} {tag}: {mm}", flush=True)
    pblend.use_painted(allobjs, k)
    # variants lineup: 55deg / top / front
    lineup = [built[v][0] for v in sorted(built)]
    x = 0.0
    for o in lineup:
        lo, hi = core.bounds([o])
        o.location.x = x - lo[0]
        x += hi[0] - lo[0] + 2.0
    bpy.context.view_layer.update()
    for name, pitch, yaw in (("variants_front", 0, 0), ("variants_55", 55, 20), ("variants_top", 90, 0)):
        pblend.only(lineup)
        pblend.ortho_frame(lineup, pitch, yaw, res=(1600, 640 if pitch < 80 else 700))
        rgba = pblend.render_view_current() if hasattr(pblend, "render_view_current") else None
        from frlib import render as frr
        rgba = frr.render_rgba()
        pblend.save_shot(rgba, qa_path(asset, a.iter, f"{name}.png"), text=f"{asset} variants LOD0 {name} (painted k={k})")
    for o in lineup:
        o.location.x = 0
    # LOD lineup
    x = 0.0
    for o in v1:
        lo, hi = core.bounds([o])
        o.location.x = x - lo[0]
        x += hi[0] - lo[0] + 2.0
    bpy.context.view_layer.update()
    pblend.only(v1)
    pblend.ortho_frame(v1, 55, 20, res=(1500, 600))
    from frlib import render as frr
    pblend.save_shot(frr.render_rgba(), qa_path(asset, a.iter, "lods_55.png"), text=f"{asset} v1 LOD0 | LOD1 | LOD2 (55deg)")
    for o in v1:
        o.location.x = 0
    bpy.context.view_layer.update()
    acc = pblend.crown_checks(v1[0], qa_path(asset, a.iter, "accept"))
    metrics["acceptance"] = acc
    print(f"[{asset}] acceptance: {acc}", flush=True)
    if sp.get("single_refs"):
        SP.matched_scale(asset, v1[0], qa_path(asset, a.iter, "matched_scale.png"), kind=sp["single_refs"])
    core.write_json(qa_path(asset, a.iter, "metrics.json"), {"metrics": metrics, "lods": info,
                                                            "atlas_scale": s, "patches": P.n})
    print(f"[{asset}] QA done ({time.time() - t0:.1f}s)", flush=True)
    if a.no_export:
        core.save_blend(os.path.join(TEXM, f"_inspect_{asset}.blend"))
        return
    pblend.use_painted(allobjs, k, on=False)
    SP.export_kit(asset, built, sp, info, kind, k, a)
    print(f"[{asset}] exported ({time.time() - t0:.1f}s)", flush=True)
    if a.qa == "full" and sp.get("patch"):
        files = ["lf_foliage_atlas.png", f"lf_bark_{kind}_c.jpg", f"lf_bark_{kind}_n.png", f"lf_bark_{kind}_r.png"]
        pth = SP.godot_patch(asset, built, sp, qa_path(asset, a.iter, "patch"), k, files)
        print(f"[{asset}] godot patch {pth} ({time.time() - t0:.1f}s)", flush=True)


if __name__ == "__main__":
    main()
