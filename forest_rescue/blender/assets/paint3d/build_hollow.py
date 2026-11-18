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

# copies: thin limbs (rotated) ; upper_copies: (angle, scale, side) of the inflated upper limbs; v1 sends the left
# limbs -90 deg and the right limbs +90 deg so both land BEHIND the trunk (art/02 front stays exact)
VARIANTS = {1: dict(seed=5, copies=[(92, 0.9), (-88, 0.92)], upper_copies=[(-90, 0.85, "left"), (90, 0.85, "right")]),
            2: dict(seed=6, mirror=True, copies=[(95, 0.92), (-140, 0.9)], umbrella=True,
                    upper_copies=[(-90, 0.85, "left"), (90, 0.85, "right")]),
            3: dict(seed=8, copies=[(130, 0.9), (-100, 0.95)], scale=(0.95, 0.96), umbrella=True,
                    upper_copies=[(-90, 0.85, "left"), (90, 0.85, "right")])}


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
    # asset origin / rotation pivot = trunk centre (the arch centre column), not one arch leg
    tcols = np.nonzero(tunnel.any(0))[0]
    if len(tcols):
        ref.view.ax = float(tcols.mean())
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
    # ------------------------------------------------------------ per-face planar UVs + bark texture
    # texture layout (1024^2): front planar (painting) u 0..0.62 v 0.28..1 | side planar (swatch) u 0.62..1 v 0.28..1
    #                          | limb strips v 0..0.27
    FR = (0.0, 0.28, 0.62, 1.0)
    SR = (0.62, 0.28, 1.0, 1.0)
    LR = (0.0, 0.0, 1.0, 0.27)
    tun_d = ndi.binary_dilation(tunnel, iterations=4)
    side_ext = {}

    def planar_uv(V, T, N):
        Vc = V[T]                                   # (M,3,3) un-indexed
        Nc = N[T]
        fn = geom.nrm(np.cross(Vc[:, 1] - Vc[:, 0], Vc[:, 2] - Vc[:, 0]))
        cen = Vc.mean(1)
        u_c, v_c, _ = ref.view.project(cen)
        uci = np.clip(np.round(u_c).astype(int), 0, W - 1)
        vci = np.clip(np.round(v_c).astype(int), 0, H + 100 - 1)
        in_tun = tun_d[np.clip(vci, 0, H - 1), uci] & (vci < H)
        side = (np.abs(fn @ ref.view.d) < 0.42) | in_tun
        uu, vv, _ = ref.view.project(Vc.reshape(-1, 3))
        vv = np.clip(vv, 0, ref.clip - 2)          # ground band below the crop: continue the lowest painted rows
        uu = np.clip(uu, 0, W - 1)
        uv_f = np.stack([FR[0] + (FR[2] - FR[0]) * uu / W, FR[3] - (FR[3] - FR[1]) * vv / H], -1).reshape(-1, 3, 2)
        # side faces: tri-planar swatch mapping by the dominant normal axis (x -> (y,z) plane, z -> (x,y) plane),
        # 0.9 m of bark per swatch-region unit, wrapped into the side region by mirroring (seamless swatch)
        P_ = Vc.reshape(-1, 3)
        dom_z = (np.abs(fn[:, 2]) > np.abs(fn[:, 0]))
        a_ = np.where(np.repeat(dom_z, 3), P_[:, 0], P_[:, 1])
        b_ = np.where(np.repeat(dom_z, 3), P_[:, 1], P_[:, 2])
        per = 3.2                                              # metres of bark across the side region
        def mirror01(x):
            t_ = np.mod(x, 2.0)
            return np.where(t_ > 1.0, 2.0 - t_, t_)
        # per-face consistent wrap: offset by the face's first-corner period to avoid a mirror flip inside a face
        a3 = a_.reshape(-1, 3) / per
        b3 = b_.reshape(-1, 3) / (per * (SR[3] - SR[1]) / (SR[2] - SR[0]))
        a3 = a3 - 2.0 * np.floor(a3[:, :1] / 2.0)
        b3 = b3 - 2.0 * np.floor(b3[:, :1] / 2.0)
        ua = np.clip(np.where(a3[:, :1] > 1.0, 2.0 - a3, a3), 0, 1)
        vb = np.clip(np.where(b3[:, :1] > 1.0, 2.0 - b3, b3), 0, 1)
        uv_s = np.stack([SR[0] + (SR[2] - SR[0]) * ua, SR[1] + (SR[3] - SR[1]) * vb], -1)
        UVc = np.where(side[:, None, None], uv_s, uv_f)
        return Vc.reshape(-1, 3), np.arange(len(T) * 3).reshape(-1, 3), UVc.reshape(-1, 2), Nc.reshape(-1, 3), in_tun

    # front region texture = the painting itself (wood pixels), filled into non-wood pixels
    img = ref.img.astype(np.float32)
    wm = (wood_c & ~tunnel) | ref.trunk_band if hasattr(ref, "trunk_band") else (wood_c & ~tunnel)
    wm = wood_c & ~tunnel
    front_full = np.zeros((H + 100, W, 3), np.float32)
    known_full = np.zeros((H + 100, W), bool)
    front_full[:H] = img
    known_full[:H] = wm
    known_full[ref.clip:H] = False
    # below the clip row (ground band): continue the lowest painted trunk rows downward
    front_full[ref.clip:] = img[ref.clip - 6:ref.clip - 1].mean(0)[None]
    known_full[ref.clip:] = (wood_c[ref.clip - 3])[None, :]
    ff = texproj.fill(front_full.astype(np.float64), known_full).astype(np.float32)
    TEX = 1024
    tex = np.zeros((TEX, TEX, 3), np.float32)
    fx0, fy0 = int(FR[0] * TEX), int((1 - FR[3]) * TEX)
    fx1, fy1 = int(FR[2] * TEX), int((1 - FR[1]) * TEX)
    tex[fy0:fy1, fx0:fx1] = cv2.resize(ff[:H], (fx1 - fx0, fy1 - fy0), interpolation=cv2.INTER_LANCZOS4)
    # side region: art/02 hollow-oak bark swatch, mirrored tiling, colour-matched to the painted trunk
    sw = tree.swatch(SWATCH)
    sw = cv2.resize(sw, (int(sw.shape[1] * 0.6), int(sw.shape[0] * 0.6)), interpolation=cv2.INTER_AREA)
    tile2 = np.concatenate([np.concatenate([sw, sw[:, ::-1]], 1), np.concatenate([sw[::-1], sw[::-1, ::-1]], 1)], 0)
    sx0, sy0 = int(SR[0] * TEX), int((1 - SR[3]) * TEX)
    sx1, sy1 = int(SR[2] * TEX), int((1 - SR[1]) * TEX)
    tiled = np.tile(tile2, ((sy1 - sy0) // tile2.shape[0] + 1, (sx1 - sx0) // tile2.shape[1] + 1, 1))[:sy1 - sy0, :sx1 - sx0]
    kp = img[wm]
    tiled = np.clip((tiled - tiled.reshape(-1, 3).mean(0)) * np.clip(kp.std(0) / (tiled.reshape(-1, 3).std(0) + 1e-4),
                                                                      0.6, 1.4) + kp.mean(0) * 0.92, 0, 1)
    tex[sy0:sy1, sx0:sx1] = tiled
    # limbs: strips sampled from the painting along each painted limb axis (front half exact, back mirrored)
    B = tree.TreeBuilder(ref, P, CFG)
    ref.trunk_rows = np.array([ref.clip - 1])
    ref.axis_x = np.array([ref.view.ax])
    ref.trunk_r = np.array([1.0])
    paths_ = [p for p in B.wood_paths() if p["kind"] == "limb"]
    uvl, dens = BT.bark_layout(paths_, ref.ppm, size=TEX)
    bark_uv = {k: (LR[0] + (LR[2] - LR[0]) * u0, LR[1] + (LR[3] - LR[1]) * v0, LR[0] + (LR[2] - LR[0]) * u1,
                   LR[1] + (LR[3] - LR[1]) * v1) for k, (u0, v0, u1, v1) in uvl.items()}
    for l, p in zip([ref.limbs[p["id"] - 1] for p in paths_], paths_):
        u0, v0, u1, v1 = bark_uv[p["id"]]
        x0, x1 = int(round(u0 * TEX)), int(round(u1 * TEX))
        y0, y1 = int(round((1 - v1) * TEX)), int(round((1 - v0) * TEX))
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        P2 = l["P"].astype(float)
        seglen = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P2, axis=0), axis=1))]
        s_tex = np.linspace(0, seglen[-1], y1 - y0)[::-1]     # v0 (bottom row) = limb start
        px = np.interp(s_tex, seglen, P2[:, 0])
        py = np.interp(s_tex, seglen, P2[:, 1])
        rr = np.interp(s_tex, seglen, l["r"])
        tg = np.stack([np.gradient(px), np.gradient(py)], -1)
        tg /= np.maximum(np.linalg.norm(tg, axis=1, keepdims=True), 1e-6)
        nx, ny = -tg[:, 1], tg[:, 0]
        th = np.linspace(0, 2 * np.pi, x1 - x0)
        off = np.sin(th - np.pi)                              # ring angle -> image offset (front at u=0.5)
        sx = px[:, None] + nx[:, None] * rr[:, None] * off[None, :]
        sy = py[:, None] + ny[:, None] * rr[:, None] * off[None, :]
        smp = texproj._bilinear(img, sx.ravel(), sy.ravel())[:, :3].reshape(y1 - y0, x1 - x0, 3)
        tex[y0:y1, x0:x1] = smp
    bl = cv2.GaussianBlur(tex, (0, 0), 1.0)
    out = np.clip(tex + 0.25 * (tex - bl), 0, 1)
    cpath = os.path.join(RT, "lf_bark_hollow_c.jpg")
    cv2.imwrite(cpath, cv2.cvtColor((out * 255).astype(np.uint8), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])
    nmap, rmap = tree.bark_maps(out)
    npath = os.path.join(RT, "lf_bark_hollow_n.png")
    rpath = os.path.join(RT, "lf_bark_hollow_r.png")
    seg.save(npath, nmap)
    seg.save(rpath, np.stack([rmap] * 3, -1))
    seg.save(qa("bark_tex.png"), out)
    print(f"[{ASSET}] bark texture assembled ({time.time() - t0:.1f}s)", flush=True)
    # massive + upper meshes with per-face UVs (as Mesh data)
    massive_md = {}
    for key, o in (("massive", om), ("upper", ou)):
        if o is None:
            continue
        V, T, _, N = obj_arrays(o)
        Vu_, Tu_, UVu_, Nu_, in_tun = planar_uv(V, T, N)
        ao = np.ones(len(Vu_))
        ao[np.repeat(in_tun, 3)] = 0.55
        massive_md[key] = (Vu_, Tu_, UVu_, Nu_, ao)
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
    lod_md = {}
    for lod_, frac in ((0, 1.0), (1, 0.3), (2, 0.1)):
        lod_md[lod_] = {}
        for key, o in (("massive", om), ("upper", ou)):
            if o is None:
                continue
            if frac >= 1.0:
                lod_md[lod_][key] = massive_md[key]
                continue
            c = o.copy()
            c.data = o.data.copy()
            core.link(c)
            decimate(c, max(60, int(core.tri_count(o) * frac)))
            V, T, _, N = obj_arrays(c)
            Vu_, Tu_, UVu_, Nu_, in_tun = planar_uv(V, T, N)
            ao = np.ones(len(Vu_))
            ao[np.repeat(in_tun, 3)] = 0.55
            lod_md[lod_][key] = (Vu_, Tu_, UVu_, Nu_, ao)
            bpy.data.objects.remove(c, do_unlink=True)
    built = {}
    info = {}
    LODS = {0: dict(limb_budget=600, limb_sides=5, limb_min_r_px=1.3, front_frac=1.0, front_scale=1.0, n_masses=22,
                    clumps_per=12, max_cards=520, massive=1.0, upper_copies=True),
            1: dict(limb_budget=150, limb_sides=4, limb_min_r_px=2.4, front_frac=0.5, front_scale=1.15, n_masses=12,
                    clumps_per=6, max_cards=170, massive=0.3, upper_copies=True),
            2: dict(limb_budget=0, limb_sides=3, limb_min_r_px=99, front_frac=0.2, front_scale=1.5, n_masses=8,
                    clumps_per=3, max_cards=48, massive=0.1, upper_copies=False)}
    for vi_, vs in VARIANTS.items():
        objs = []
        info[vi_] = {}
        for lod, L in LODS.items():
            rng = np.random.default_rng(vs["seed"] * 31 + lod)
            # wood: massive (per-LOD decimated copy) + upper limb copies (behind for v1) + skeleton limbs
            wood_md = geom.Mesh()
            for key in ("massive", "upper"):
                if key not in lod_md[lod]:
                    continue
                Vq, Tq, UVq, Nq, aoq = lod_md[lod][key]
                reps = [(None, 1.0, None)] if key == "massive" else \
                    ([(ang, sc, side) for ang, sc, side in vs["upper_copies"]] if L["upper_copies"] else [])
                for ang, sc, side in reps:
                    Vr = Vq
                    Tr = Tq
                    if ang is not None:
                        if side is not None:
                            cen_x = Vq[Tq].mean(1)[:, 0]
                            keep_t = (cen_x < trunk_axis[0]) if side == "left" else (cen_x >= trunk_axis[0])
                            Tr = Tq[keep_t]
                        Rm = geom.rot_z(math.radians(ang))
                        Vr = ((Vq - trunk_axis) * sc) @ Rm.T + trunk_axis
                        Nr = Nq @ Rm.T
                    else:
                        Nr = Nq
                    if len(Tr) == 0:
                        continue
                    Cw = tree.wind_rgba(Vr, 16.0, 7.0, "trunk", 0.0, 1.0)
                    Cw[:, 3] = aoq
                    wood_md.add(Vr, Tr, UVq, Cw, Nr, tree.MAT_BARK)
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
            if vs.get("umbrella"):
                # art/01 cave oak: broad full crown of domed lobes (same painted tiles) above the limbs
                B.cfg = dict(CFG, umb_n=max(5, 9 - lod), umb_base=0.48, umb_lobe_r=0.3, mass_zscale=0.55,
                             ao_under=0.7, ao_side=0.86, side_mode="shade", lobe_zf_min=-0.25, umb_rk=1.05)
                ucards = B.mass_cards([], np.full((H, W), np.inf), size_k=1.35, seed=vs["seed"] * 11 + lod, n_masses=0,
                                      mass_r=0.3, clumps_per=(46, 18, 8)[lod], front_extra_frac=0.0,
                                      max_cards=(520, 190, 60)[lod], core_cards=0, placement="umbrella")
                fills = fills + ucards
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
    sp = dict(variants=VARIANTS, tint_note="art/02 palette (copper-orange autumn crown); hero landmark tree "
                                           "(landmark budget 6k/1.5k/400)")
    SP.export_kit(ASSET, built, sp, info, "hollow", K, a)
    print(f"[{ASSET}] exported ({time.time() - t0:.1f}s)", flush=True)


def _vertex_uv(V, T, UVc):
    """Per-corner UVs (M,3,2) -> per-vertex UVs (assumes no seams were split: duplicates take the last)."""
    out = np.zeros((len(V), 2))
    out[T.ravel()] = UVc.reshape(-1, 2)
    return out


if __name__ == "__main__":
    main()
