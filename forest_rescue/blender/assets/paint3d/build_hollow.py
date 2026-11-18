"""Hollow oak (art/02 top row, 4th): massive inflated trunk with the painted walk-through arch carved as a tunnel,
skeleton limbs, painted orange clump cards (front fit + lobes at limb tips), bark = the painting projected.

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/paint3d/build_hollow.py [--iter N] [--qa full]
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
from frlib import core, paths, texproj, render as frr  # noqa: E402

import p3atlas as atl  # noqa: E402
import geom  # noqa: E402
import massive  # noqa: E402
import seg  # noqa: E402
import skel  # noqa: E402
import tree  # noqa: E402
import species as SP  # noqa: E402
import build_tree as BT  # noqa: E402

RT = os.path.join(paths.RUNTIME, "forest")
ASSET = "lf_env_hollow_oak"

CFG = dict(name="hollow_oak", box=(850, 0, 1262, 445), exclude=[(1165, 355, 1212, 435)], clip_row=414, ground_row=426,
           fork_row=150, wood=dict(mode="notfoliage", hue_max=63, Cmax=28, min_area=150), keep_x=(852, 1236),
           trunk_close=4, float_min_r=1.8, crown_kd=0.8, front_bias=0.45, seed=21, lum_pref=3.0, front_tilt_max=30,
           top_part=0.65, vol_material=True, mass_zscale=0.6, ao_under=0.8, front_extra_eta=0.7, core_eta_max=0.3,
           p_hires=0.0, limb_min_r=1.3)
LATHE_TOP = 290          # crop row where the lower trunk becomes a body of revolution (arch + root flare below)
THICK_R = 6              # px: wood thicker than this radius is inflated (trunk + main limbs)
SWATCH = (882, 798, 1222, 984)
K = 0.3

VARIANTS = {1: dict(seed=5, copies=[(110, 0.9), (-115, 0.92)]),
            2: dict(seed=6, mirror=True, copies=[(95, 0.92), (-140, 0.9)]),
            3: dict(seed=8, copies=[(130, 0.9), (-100, 0.95)], scale=(0.95, 0.96))}


def massive_mesh(ref, wood_c, thick, tunnel):
    P, F = massive.trunk_field(ref, wood_c, thick, tunnel, LATHE_TOP, voxel=2.0, kd_lathe=0.8, kd_infl=0.85)
    return P, F


def upper_thick_mesh(ref, thick):
    up = thick.copy()
    up[LATHE_TOP - 10:] = False
    lab_, n = ndi.label(up)
    if not n:
        return None, None
    P, F = geom.inflate(up, ref.view, voxel_px=2.0, depth_scale=0.85, smooth=1.0)
    return P, F


def to_obj(name, V, F, mat):
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], F.tolist())
    me.validate()
    o = bpy.data.objects.new(name, me)
    core.link(o)
    o.data.materials.append(mat)
    return o


def decimate(o, target):
    n = core.tri_count(o)
    if n > target:
        m = o.modifiers.new("dec", "DECIMATE")
        m.ratio = target / n
        m.use_collapse_triangulate = True
        core.select_only([o])
        bpy.ops.object.modifier_apply(modifier="dec")
    return o


def smooth_obj(o, iters=4, factor=0.5):
    m = o.modifiers.new("sm", "SMOOTH")
    m.iterations = iters
    m.factor = factor
    core.select_only([o])
    bpy.ops.object.modifier_apply(modifier="sm")


def obj_arrays(o):
    V, T, UV, N = core.mesh_arrays(o, evaluated=False, world=True)
    return V, T, UV, N


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=int, default=1)
    ap.add_argument("--qa", default="full")
    ap.add_argument("--no-export", action="store_true")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    t0 = time.time()
    qa = lambda n: BT.qa_path(ASSET, a.iter, n)  # noqa: E731
    ref = tree.TreeRef(CFG)
    H, W = ref.H, ref.W
    wood = ref.wood_raw
    wood_c = (ndi.binary_closing(wood, structure=morphology.disk(3)) & ref.fg_full) | wood
    thick = ndi.binary_opening(wood_c, structure=morphology.disk(THICK_R))
    thick &= ~(np.arange(H)[:, None] >= ref.clip)
    arch = massive.arch_mask(wood_c, ref.fg_full, 250, clip=ref.clip)
    tunnel = massive.open_bottom(arch, ref.clip + 30)
    # thin limbs = wood not covered by the thick region
    thin = wood & ~ndi.binary_dilation(thick, iterations=1)
    segs, jc, sk, dist = skel.segments(thin)
    axis_fn = lambda v: None  # noqa: E731
    limbs = skel.limb_tree(segs, jc, ndi.binary_dilation(thick, iterations=2), axis_fn, min_r=1.2, float_min_r=1.6,
                           float_min_len=8)
    ref.limbs = limbs
    cov = thick.astype(np.uint8)
    for l in limbs:
        for (x, y), rr in zip(l["P"], l["r"]):
            cv2.circle(cov, (int(round(x)), int(round(y))), int(max(1, round(rr))), 1, -1)
    ref.wood_cov = cov.astype(bool) & ref.fg
    seg.save(qa("masks.png"), np.concatenate([
        seg.overlay(ref.img, [(thick, (0.9, 0.4, 0.1)), (tunnel, (0.1, 0.3, 0.9)), (ref.fg & ~wood, (0.1, 0.8, 0.1))], 0.55),
        seg.overlay(ref.img, [(ref.wood_cov, (0.9, 0.2, 0.2))], 0.5)], 1))
    print(f"[{ASSET}] masks: thick {thick.sum()} tunnel {tunnel.sum()} limbs {len(limbs)} ({time.time() - t0:.1f}s)", flush=True)
    # ------------------------------------------------------------ foliage patches + atlas region
    P = tree.Patches(ref, n_target=70, min_px=30, margin=3, scale=2)
    P.preview(qa("patches.png"))
    reg_img, s = P.pack("hollow_oak")
    atl.save_region("hollow_oak", reg_img, {"asset": ASSET, "scale": s, "tiles": P.n})
    atlas_path = atl.assemble()
    print(f"[{ASSET}] patches={P.n} atlas_scale={s:.3f}", flush=True)
    # ------------------------------------------------------------ massive meshes
    core.reset()
    tmpmat = bpy.data.materials.new("tmp")
    Vm, Fm = massive_mesh(ref, wood_c, thick, tunnel)
    om = to_obj("massive", Vm, Fm, tmpmat)
    smooth_obj(om, 3, 0.5)
    decimate(om, 2300)
    Vu, Fu = upper_thick_mesh(ref, thick)
    ou = to_obj("upper", Vu, Fu, tmpmat) if Vu is not None else None
    if ou is not None:
        smooth_obj(ou, 2, 0.5)
        decimate(ou, 700)
    print(f"[{ASSET}] massive tris {core.tri_count(om)} upper {core.tri_count(ou) if ou else 0} ({time.time() - t0:.1f}s)",
          flush=True)
    # UVs: massive + upper share the left 76% of the bark texture, limb strips the right 22%
    for o in [om] + ([ou] if ou else []):
        o.data.uv_layers.new(name="UVMap")
    joined_src = [om] + ([ou] if ou else [])
    core.select_only(joined_src, om)
    for o in joined_src:
        o.select_set(True)
    bpy.context.view_layer.objects.active = om
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.006, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    for o in joined_src:
        uv = o.data.uv_layers.active.data
        arr = np.empty(len(uv) * 2, np.float32)
        uv.foreach_get("uv", arr)
        arr = arr.reshape(-1, 2)
        arr[:, 0] *= 0.76
        uv.foreach_set("uv", arr.ravel())
    # limbs (thin skeleton tubes) via the tree builder; bark layout restricted to u in [0.78, 1]
    B = tree.TreeBuilder(ref, P, CFG)
    ref.trunk_rows = np.array([ref.clip - 1])
    ref.axis_x = np.array([ref.view.ax])
    ref.trunk_r = np.array([1.0])
    paths_ = [p for p in B.wood_paths() if p["kind"] == "limb"]
    for p in paths_:
        # limbs start on the inflated surface: keep them in the painted plane (y from wood_paths)
        pass
    uvl, dens = BT.bark_layout(paths_, ref.ppm, size=1024)
    bark_uv = {k: (0.78 + 0.22 * u0, v0, 0.78 + 0.22 * u1, v1) for k, (u0, v0, u1, v1) in uvl.items()}
    # ------------------------------------------------------------ bark texture: project the painting
    Vt, Tt, UVt, Nt = [], [], [], []
    ids = []
    base = 0
    for i, o in enumerate(joined_src):
        V, T, UV, N = obj_arrays(o)
        Vt.append(V)
        Tt.append(T + base)
        UVt.append(UV)
        Nt.append(N)
        ids += [i] * len(T)
        base += len(V)
    limb_mesh = geom.Mesh()
    for p in paths_:
        q = BT.simplify_path(p, max(0.1, 1.5 * float(np.max(p["r"]))))
        if len(q["P"]) < 3:
            q = BT.simplify_path(p, max(0.02, float(np.linalg.norm(p["P"][-1] - p["P"][0])) / 3))
        if len(q["P"]) < 3:
            continue
        V, T, UV, C, N = geom.tube(q["P"], q["r"], 8, bark_uv[p["id"]], np.ones(4), ref_side=ref.view.d)
        limb_mesh.add(V, T, UV, C, N, 0)
        ids += [100 + p["id"]] * len(T)
    Vl, Tl, UVl, Cl, Nl, Ml = limb_mesh.arrays()
    V = np.concatenate(Vt + [Vl])
    T = np.concatenate(Tt + [Tl + base])
    UV = np.concatenate(UVt + [UVl[Tl]])
    N = np.concatenate(Nt + [Nl])
    ids = np.array(ids)
    Tx = texproj.rasterize_uv(V, T, UV, 1024, N)
    ib, zb = tree.tri_id_buffer(V, T, np.arange(len(T)), ref.view)
    yy, xx = np.nonzero(Tx.valid)
    Pp = Tx.pos[yy, xx]
    u, v, dep = ref.view.project(Pp)
    ui = np.clip(np.round(u).astype(int), 0, W - 1)
    vi = np.clip(np.round(v).astype(int), 0, H - 1)
    tri = Tx.tri[yy, xx]
    woodpx = (wood_c & ~tunnel)[vi, ui]
    # front-visible texels: own triangle is the nearest at that pixel (3x3 tolerance)
    vis = np.zeros(len(ui), bool)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            vis |= ib[np.clip(vi + dy, 0, H - 1), np.clip(ui + dx, 0, W - 1)] == tri
    facing = np.abs(Tx.nrm[yy, xx] @ ref.view.d)
    # massive back side = mirrored front (same pixel), limbs: front only
    is_massive = ids[tri] < 100
    ok = woodpx & (facing > 0.3) & (vis | (is_massive & (Tx.nrm[yy, xx] @ ref.view.d > 0.3)))
    col = np.zeros((1024, 1024, 3), np.float32)
    known = np.zeros((1024, 1024), bool)
    samp = texproj._bilinear(ref.img.astype(np.float32), u, v)[:, :3]
    col[yy[ok], xx[ok]] = samp[ok]
    known[yy[ok], xx[ok]] = True
    filled = texproj.fill(col.astype(np.float64), known).astype(np.float32)
    sw = tree.swatch(SWATCH)
    sw = cv2.resize(sw, (int(sw.shape[1] * 0.55), int(sw.shape[0] * 0.55)), interpolation=cv2.INTER_AREA)
    tile2 = np.concatenate([np.concatenate([sw, sw[:, ::-1]], 1), np.concatenate([sw[::-1], sw[::-1, ::-1]], 1)], 0)
    tiled = np.tile(tile2, (1024 // tile2.shape[0] + 1, 1024 // tile2.shape[1] + 1, 1))[:1024, :1024]
    kp = col[known]
    tiled = np.clip((tiled - tiled.reshape(-1, 3).mean(0)) * np.clip(kp.std(0) / (tiled.reshape(-1, 3).std(0) + 1e-4), 0.6, 1.4)
                    + kp.mean(0), 0, 1)
    unknown = Tx.valid & ~known
    soft = cv2.GaussianBlur(unknown.astype(np.float32), (0, 0), 3.0)
    soft = np.where(unknown, np.maximum(soft, 0.65), soft * 0.5)
    out = filled * (1 - soft[..., None]) + tiled * soft[..., None]
    # tunnel interior: darken texels inside / near the tunnel volume (seen through the arch)
    tun_px = ndi.binary_dilation(tunnel, iterations=3)[vi, ui]
    deep = np.abs(dep * ref.ppm) < 0.6 * np.abs(geom.pix_to_world(ref.view, np.array([0.0]), np.array([0.0]), np.array([0.0]))[0][1] * 0 + 40)
    dark = np.zeros((1024, 1024), np.float32)
    dark[yy[tun_px & ~ok], xx[tun_px & ~ok]] = 1.0
    dark = cv2.GaussianBlur(dark, (0, 0), 2.0)
    out = out * (1 - 0.55 * dark[..., None])
    bl = cv2.GaussianBlur(out, (0, 0), 1.0)
    out = np.clip(out + 0.3 * (out - bl), 0, 1)
    out = texproj.dilate_margin(out.astype(np.float64), Tx.valid, px=6).astype(np.float32)
    cpath = os.path.join(RT, "lf_bark_hollow_c.jpg")
    cv2.imwrite(cpath, cv2.cvtColor((out * 255).astype(np.uint8), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])
    nmap, rmap = tree.bark_maps(out)
    npath = os.path.join(RT, "lf_bark_hollow_n.png")
    rpath = os.path.join(RT, "lf_bark_hollow_r.png")
    seg.save(npath, nmap)
    seg.save(rpath, np.stack([rmap] * 3, -1))
    seg.save(qa("bark_known.png"), np.where(known[..., None], out, out * 0.3 + 0.2))
    print(f"[{ASSET}] bark projected {known.sum() / max(1, Tx.valid.sum()):.2f} ({time.time() - t0:.1f}s)", flush=True)
    # ------------------------------------------------------------ assemble variants / LODs
    fol = pblend.export_material("lf_foliage", atlas_path, alpha_clip=0.5, double_sided=True)
    fol_vol = pblend.export_material("lf_foliage_vol", atlas_path, alpha_clip=0.5, double_sided=True)
    bark = pblend.export_material("lf_bark_hollow", cpath, normal_path=npath, rough_path=rpath)
    front_all = B.front_cards(scale=1.0, seed=5)
    dm = B.front_depth_map(front_all)
    # inflated trunk depth also counts as "front" for the depth test (cards stay behind its surface)
    Vm_, Tm_, _, _ = obj_arrays(om)
    ibm, zbm = tree.tri_id_buffer(Vm_, Tm_, np.arange(len(Tm_)), ref.view)
    dm = np.minimum(dm, np.where(np.isfinite(zbm), zbm * ref.ppm, np.inf))
    trunk_axis = geom.world_at_y(ref.view, np.array([ref.view.ax]), np.array([float(LATHE_TOP)]), np.array([0.0]))[0]
    trunk_axis[2] = 0.0
    built = {}
    info = {}
    LODS = {0: dict(limb_budget=700, limb_sides=5, limb_min_r_px=1.3, front_frac=1.0, front_scale=1.0, n_masses=22,
                    clumps_per=12, max_cards=640, massive=1.0, upper_copies=True),
            1: dict(limb_budget=200, limb_sides=4, limb_min_r_px=2.4, front_frac=0.55, front_scale=1.15, n_masses=14,
                    clumps_per=6, max_cards=220, massive=0.45, upper_copies=True),
            2: dict(limb_budget=0, limb_sides=3, limb_min_r_px=99, front_frac=0.2, front_scale=1.5, n_masses=8,
                    clumps_per=3, max_cards=48, massive=0.1, upper_copies=False)}
    for vi_, vs in VARIANTS.items():
        objs = []
        info[vi_] = {}
        for lod, L in LODS.items():
            rng = np.random.default_rng(vs["seed"] * 31 + lod)
            # wood: massive (decimated per LOD) + upper limb copies + skeleton limbs
            parts = []
            mo = om.copy()
            mo.data = om.data.copy()
            core.link(mo)
            decimate(mo, int(core.tri_count(om) * L["massive"]))
            parts.append(mo)
            if ou is not None and L["upper_copies"]:
                for ang, sc in vs["copies"]:
                    c = ou.copy()
                    c.data = ou.data.copy()
                    core.link(c)
                    if lod > 0:
                        decimate(c, int(core.tri_count(ou) * L["massive"]))
                    Rm = geom.rot_z(math.radians(ang))
                    Vc = np.array([list(vv.co) for vv in c.data.vertices])
                    Vc = ((Vc - trunk_axis) * sc) @ Rm.T + trunk_axis
                    c.data.vertices.foreach_set("co", Vc.ravel())
                    c.data.update()
                    parts.append(c)
            wood_md = geom.Mesh()
            for pobj in parts:
                Vp, Tp, UVp, Np = obj_arrays(pobj)
                Cw = tree.wind_rgba(Vp, 16.0, 7.0, "trunk", 0.0, 1.0)
                wood_md.add(Vp, Tp, UVp[np.argsort(np.concatenate([Tp.ravel()]))[:0]] if False else
                            _vertex_uv(Vp, Tp, UVp), Cw, Np, tree.MAT_BARK)
                bpy.data.objects.remove(pobj, do_unlink=True)
            # limbs + cards through the tree builder
            ps = [BT.simplify_path(p, max(0.25 if lod == 0 else 0.5, 2.2 * float(np.max(p["r"])))) for p in paths_]
            mr, est = BT.limit_paths(ps, L["limb_budget"], L["limb_sides"], L["limb_min_r_px"])
            copies = [(geom.rot_z(math.radians(ang)), trunk_axis, False, sc) for ang, sc in vs["copies"]]
            keep = None
            if L["front_frac"] < 1.0:
                order = np.argsort([-P.info[i]["area"] for i in range(P.n)])
                keep = set(order[: max(3, int(len(order) * L["front_frac"]))].tolist())
            fronts = B.front_cards(scale=L["front_scale"], keep=keep, seed=vs["seed"])
            tips = [p["P"][-1] for p in paths_ if p.get("r_px", 0) >= 1.2]
            anchors = list(tips) + [((tp - trunk_axis) * sc) @ Rm.T + trunk_axis for (Rm, _, _, sc) in copies for tp in tips]
            B.cfg = dict(CFG, mass_min_dist=1.3)
            fills = B.mass_cards(fronts, dm, size_k=1.2, seed=vs["seed"] * 7 + lod, n_masses=L["n_masses"],
                                 mass_r=0.1, clumps_per=L["clumps_per"], front_extra_frac=0.4,
                                 max_cards=L["max_cards"], core_cards=0, placement="anchors", anchors=anchors)
            barkm, leaf = B.assemble(ps, fronts + fills, bark_uv, sides_trunk=6, sides_limb=L["limb_sides"],
                                     min_limb_r_px=mr if L["limb_budget"] > 0 else 999,
                                     copies=copies if L["limb_budget"] > 0 else None, tree_h=16.0, crown_r=7.0,
                                     seed=vs["seed"], copy_min_r_px=1.8)
            m = geom.Mesh()
            m.extend(wood_md)
            m.extend(barkm)
            m.extend(leaf)
            if vs.get("mirror"):
                m = m.transformed(mirror_x=True)
            if vs.get("scale"):
                sxy, sz = vs["scale"]
                Vv, Tq, UVq, Cq, Nq, Mq = m.arrays()
                m2 = geom.Mesh()
                m2.add(Vv * np.array([sxy, sxy, sz]), Tq, UVq, Cq, geom.nrm(Nq / np.array([sxy, sxy, sz])), 0)
                m2.M = [Mq]
                m = m2
            o = pblend.obj_from_mesh(f"{ASSET}_v{vi_}_LOD{lod}", m, [bark, fol, fol_vol])
            objs.append(o)
            info[vi_][f"LOD{lod}"] = dict(tris=m.tris(), fronts=len(fronts), fills=len(fills))
        built[vi_] = objs
        print(f"[{ASSET}] v{vi_}: " + ", ".join(f"LOD{l}={info[vi_][f'LOD{l}']['tris']}" for l in range(3)), flush=True)
    bpy.data.objects.remove(om, do_unlink=True)
    if ou is not None:
        bpy.data.objects.remove(ou, do_unlink=True)
    # ------------------------------------------------------------ QA
    pblend.KMAP.update({"lf_foliage_vol": 0.5})
    pblend.setup_render(16)
    allobjs = [o for v in built.values() for o in v]
    metrics = {}
    for lod in range(3):
        for kk, tag in ((K, "painted"), (0.0, "albedo")):
            if lod > 0 and tag == "albedo":
                continue
            pblend.use_painted(allobjs, kk)
            rgba = pblend.render_view(ref.view, [built[1][lod]])
            rgba[ref.clip:, :, 3] = 0
            mm = pblend.compare_sheet(ref.img, ref.fg, rgba, ref.bg, qa(f"front_v1_LOD{lod}_{tag}.png"),
                                      f"{ASSET} v1 LOD{lod} vs art/02 ({tag} k={kk}) iter {a.iter}")
            metrics[f"v1_LOD{lod}_{tag}"] = mm
            print(f"[{ASSET}] LOD{lod} {tag}: {mm}", flush=True)
    pblend.use_painted(allobjs, K)
    acc = pblend.crown_checks(built[1][0], qa("accept"))
    metrics["acceptance"] = acc
    lineup = [built[v][0] for v in sorted(built)]
    x = 0.0
    for o in lineup:
        lo, hi = core.bounds([o])
        o.location.x = x - lo[0]
        x += hi[0] - lo[0] + 2.0
    bpy.context.view_layer.update()
    for name, pitch, yaw in (("variants_front", 0, 0), ("variants_38", 38, 45), ("variants_top", 90, 0)):
        pblend.only(lineup)
        pblend.ortho_frame(lineup, pitch, yaw, res=(1600, 700))
        pblend.save_shot(frr.render_rgba(), qa(f"{name}.png"), text=f"{ASSET} variants {name}")
    for o in lineup:
        o.location.x = 0
    bpy.context.view_layer.update()
    core.write_json(qa("metrics.json"), {"metrics": metrics, "lods": info})
    if a.no_export:
        return
    pblend.use_painted(allobjs, K, on=False)
    sp = dict(variants=VARIANTS, tint_note="art/02 palette (copper-orange autumn crown)")
    SP.export_kit(ASSET, built, sp, info, "hollow", K, a)
    print(f"[{ASSET}] exported ({time.time() - t0:.1f}s)", flush=True)


def _vertex_uv(V, T, UVc):
    """Per-corner UVs (M,3,2) -> per-vertex UVs (assumes no seams were split: duplicates take the last)."""
    out = np.zeros((len(V), 2))
    out[T.ravel()] = UVc.reshape(-1, 2)
    return out


if __name__ == "__main__":
    main()
