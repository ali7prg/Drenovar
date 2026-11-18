"""Stage 3: textures for the Ancient Maw LOD0 UVs.

normal  = Cycles bake high->LOD0 (+) procedural scales/scutes (analytic 3-D gradients, UDN blend)
colour  = projection of the reference left / mirrored-left / front views (de-lit), 3-D nearest fill,
          scale grooves, per-scale tint, knob bronze, mouth interior, LEFT-eye scar, baked AO
ORM     = R ambient occlusion, G roughness (region based), B metallic 0
keratin = 512 atlas for teeth / claws / eye / tongue
python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/boss/maw_stage_tex.py [--size 4096]
"""
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maw_common as C  # noqa: E402
import bpy  # noqa: E402

from frlib import core, paths, refs, texproj  # noqa: E402
from scipy import ndimage as ndi  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402
import maw_body as B  # noqa: E402
import maw_refs as R  # noqa: E402
import maw_tex as MT  # noqa: E402

AID = C.ASSET_ID


def log(*a):
    print("[maw_tex]", *a, flush=True)


def body_copy(lod0):
    o = lod0.copy()
    o.data = lod0.data.copy()
    o.modifiers.clear()
    o.parent = None
    o.matrix_world = lod0.matrix_world.copy()
    bpy.context.scene.collection.objects.link(o)
    o.name = "maw_bake_body"
    core.select_only([o])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    for p in o.data.polygons:
        p.select = p.material_index == 1
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.delete(type="FACE")
    bpy.ops.object.mode_set(mode="OBJECT")
    o.data.materials.clear()
    m = bpy.data.materials.new("M_bake_tmp")
    m.use_nodes = True
    o.data.materials.append(m)
    return o


def high_object():
    d = np.load(C.cache("maw_high.npz"))
    return core.mesh_object("maw_high", d["verts"], d["faces"], smooth=True)


def tangent_frames(V, tris, uv, T):
    t0, t1, t2 = V[tris[:, 0]], V[tris[:, 1]], V[tris[:, 2]]
    e1, e2 = t1 - t0, t2 - t0
    d1, d2 = uv[:, 1] - uv[:, 0], uv[:, 2] - uv[:, 0]
    den = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    den = np.where(np.abs(den) < 1e-12, 1e-12, den)
    Tg = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / den[:, None]
    Bt = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / den[:, None]
    yy, xx = np.nonzero(T.valid)
    tri = T.tri[yy, xx]
    N = T.nrm[yy, xx]
    tg = Tg[tri]
    tg = tg - N * (tg * N).sum(1, keepdims=True)
    tg /= np.maximum(np.linalg.norm(tg, axis=1, keepdims=True), 1e-12)
    bt = np.cross(N, tg)
    hand = np.sign((bt * Bt[tri]).sum(1))
    hand[hand == 0] = 1
    return tg, bt * hand[:, None]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=int(os.environ.get("MAW_TEX", C.TEX_MASTER)))
    ap.add_argument("--ao-samples", type=int, default=24)
    args = ap.parse_args(sys.argv[1:])
    S = args.size
    bpy.ops.wm.open_mainfile(filepath=C.cache("maw_rig.blend"))
    lod0 = bpy.data.objects[f"{AID}_LOD0"]
    body = body_copy(lod0)
    high = high_object()
    t0 = time.time()
    img_n = core.new_image("maw_bake_n", S, colorspace="Non-Color", color=(0.5, 0.5, 1, 1))
    core.bake(body, "NORMAL", img_n, samples=1, selected_to_active=high, cage_extrusion=0.03,
              max_ray_distance=0.08, margin=8)
    log(f"normal bake {S} {time.time() - t0:.1f}s")
    t0 = time.time()
    ao_size = min(S, 2048)
    img_ao = core.new_image("maw_bake_ao", ao_size, colorspace="Non-Color", color=(1, 1, 1, 1))
    bpy.data.objects.remove(high, do_unlink=True)
    core.bake(body, "AO", img_ao, samples=args.ao_samples, margin=8)
    log(f"AO bake {ao_size} {time.time() - t0:.1f}s")
    nb = core.image_to_numpy(img_n)[..., :3]
    ao = core.image_to_numpy(img_ao)[..., 0]
    if ao_size != S:
        import cv2
        ao = cv2.resize(ao, (S, S), interpolation=cv2.INTER_LINEAR)
    ao = ndi.gaussian_filter(ao, S / 1024.0)

    # ---------------------------------------------------------------- texels
    V, tris, uv, vn = core.mesh_arrays(body, evaluated=False, world=True)
    T = texproj.rasterize_uv(V, tris, uv, S, vn)
    yy, xx = np.nonzero(T.valid)
    P = T.pos[yy, xx]
    N = T.nrm[yy, xx]
    log("texels", len(P))

    # ---------------------------------------------------------------- colour projection
    t0 = time.time()
    views = [R.side_view(corrected=False), R.side_view_mirrored(), R.front_view()]
    for v in views:
        v.image = ndi.gaussian_filter(v.image, (0.45, 0.45, 0))
    views[2].weight = 0.8
    zbs = {v.name: texproj.zbuffer(V, tris, v) for v in views}
    col, w = texproj.project(T, views, zbs, power=2.5, depth_eps=0.04, min_facing=0.22, mask_erode=3)
    log(f"projection {time.time() - t0:.1f}s, covered {(w[yy, xx] > 0).mean():.2f}")
    col = texproj.delight(col, T, light_dir=(0.25, -0.45, 0.86), ambient=0.45, strength=0.45,
                          mask=T.valid & (w > 0))
    known = (w[yy, xx] > 0.02)
    C3 = col[yy, xx]
    # 3-D nearest fill for unseen texels (belly underside, top midline, inner legs)
    kd = cKDTree(P[known][:: max(1, known.sum() // 600000)])
    src = C3[known][:: max(1, known.sum() // 600000)]
    dist, nn = kd.query(P[~known], k=6)
    wgt = 1.0 / np.maximum(dist, 1e-3)
    C3[~known] = (src[nn] * wgt[..., None]).sum(1) / wgt.sum(1, keepdims=True)
    # soften the seam between projected and filled texels in 3-D
    log(f"fill {time.time() - t0:.1f}s")

    # ---------------------------------------------------------------- procedural detail
    t0 = time.time()
    reg = MT.regions(P, N)
    Hs, Gs = np.zeros(len(P)), np.zeros((len(P), 3))
    groove = np.zeros(len(P))
    tint = np.zeros(len(P))
    # layer weights
    wL = np.clip(reg["neck_sh"] * 0.9 + reg["head"] * 0.8 + reg["dorsal"] * 0.5, 0, 1)
    wF = np.clip(reg["ventral"] + reg["inner"] * 0.8, 0, 1) * (1 - reg["head"] * 0.7)
    wM = np.clip(1 - wL - wF, 0, 1)
    for cell, depth, wgt_, seed in ((0.075, 0.0095, wL, 1), (0.034, 0.0055, wM, 2), (0.013, 0.0026, wF, 3)):
        h, g, idc = MT.scale_layer(P, cell, seed, depth)
        Hs += h * wgt_
        Gs += g * wgt_[:, None]
        groove += np.clip(h / depth, 0, 1) * wgt_
        tint += idc * wgt_
    # transverse scutes: throat/belly/tail underside (coordinate = Y), metatarsus & toes (coordinate = Z / length)
    vb = reg["ventral"] * (1 - reg["inner"])
    hb, gb = MT.band_layer(P[:, 1], np.tile([0, 1.0, 0], (len(P), 1)), 0.055, 0.004)
    Hs = Hs * (1 - 0.7 * vb) + hb * 0.7 * vb
    Gs = Gs * (1 - 0.7 * vb)[:, None] + gb * (0.7 * vb)[:, None]
    ft = reg["foot"]
    hf, gf = MT.band_layer(P[:, 2] + 0.3 * np.abs(P[:, 1] + 0.2), np.tile([0, 0, 1.0], (len(P), 1)), 0.05, 0.005)
    Hs = Hs * (1 - 0.75 * ft) + hf * 0.75 * ft
    Gs = Gs * (1 - 0.75 * ft)[:, None] + gf * (0.75 * ft)[:, None]
    knob = MT.knob_mask(P)
    mouth = MT.mouth_mask(P)
    scar, scar_d = MT.scar_mask(P)
    # fibrous scar streaks (along the scar, across = ridges)
    Gs *= (1 - 0.8 * mouth)[:, None]
    log(f"procedural {time.time() - t0:.1f}s")

    # tangent-space normal from the 3-D gradient, UDN-blended with the baked normal
    tg, bt = tangent_frames(V, tris, uv, T)
    gx = (Gs * tg).sum(1)
    gy = (Gs * bt).sum(1)
    n1 = nb[yy, xx] * 2 - 1
    nx = n1[:, 0] - gx * 1.0
    ny = n1[:, 1] - gy * 1.0
    nz = n1[:, 2]
    nn_ = np.stack([nx, ny, nz], 1)
    nn_ /= np.maximum(np.linalg.norm(nn_, axis=1, keepdims=True), 1e-9)
    nrm_img = np.zeros((S, S, 3))
    nrm_img[..., :] = (0.5, 0.5, 1.0)
    nrm_img[yy, xx] = nn_ * 0.5 + 0.5

    # ---------------------------------------------------------------- colour composition
    col3 = C3.copy()
    lum = col3 @ np.array([0.299, 0.587, 0.114])
    gdark = 0.86 - 0.20 * reg["head"] - 0.08 * reg["dorsal"]
    col3 *= (gdark + (1.04 - gdark) * np.clip(groove, 0, 1))[:, None]
    # large rough scales: per-scale olive-iron / charcoal alternation with bronze centres (head, neck, back)
    big = np.clip(reg["head"] + reg["neck_sh"] + 0.7 * reg["dorsal"], 0, 1)
    olive = np.array([0.40, 0.38, 0.28])
    charcoal = np.array([0.17, 0.17, 0.16])
    lum0 = (col3 @ np.array([0.299, 0.587, 0.114]))[:, None]
    pal = np.where((tint > 0.55)[:, None], olive, charcoal) * (lum0 / 0.26)
    col3 = col3 * (1 - 0.35 * big[:, None]) + pal * 0.35 * big[:, None]
    col3 *= (1 + (0.16 * big + 0.07) * (tint - 0.5))[:, None]
    ctr = np.clip(groove, 0, 1) ** 3 * big
    col3 = col3 * (1 - 0.18 * ctr[:, None]) + np.array([0.55, 0.45, 0.30]) * 0.18 * ctr[:, None]
    bronze = np.array([0.60, 0.48, 0.30])
    col3 = col3 * (1 - 0.6 * knob[:, None]) + (bronze * (0.75 + 0.6 * lum[:, None])) * 0.6 * knob[:, None]
    mouth_col = np.array([0.42, 0.17, 0.17]) * (0.6 + 0.4 * np.clip((P[:, 1] + 3.2) / -1.0, 0, 1))[:, None]
    col3 = col3 * (1 - mouth[:, None]) + mouth_col * mouth[:, None]
    # burnt-umber throat/chest (sheet palette) on the ventral front half
    umber = np.array([0.50, 0.27, 0.13])
    vz = reg["ventral"] * MT.smoothstep(-0.6, -1.4, P[:, 1]) * MT.smoothstep(-3.6, -3.1, P[:, 1])
    vz = np.maximum(vz, MT.smoothstep(0.2, 0.7, -N[:, 1]) * MT.smoothstep(-1.2, -1.8, P[:, 1])
                    * MT.smoothstep(2.9, 2.5, P[:, 2]) * (np.abs(P[:, 0]) < 0.55) * (P[:, 2] > 1.4))
    lumv = (col3 @ np.array([0.299, 0.587, 0.114]))[:, None]
    col3 = col3 * (1 - 0.45 * vz[:, None]) + umber * (lumv / 0.30) * 0.45 * vz[:, None]
    fib = 0.85 + 0.15 * np.sin(scar_d * 900.0)
    scar_col = np.array([0.90, 0.76, 0.74]) * fib[:, None]
    col3 = col3 * (1 - 0.95 * scar[:, None]) + scar_col * 0.95 * scar[:, None]
    aov = ao[yy, xx]
    col3 *= (0.70 + 0.30 * aov)[:, None]
    # calibration against the side view (iter01 render/reference mean ratio, see REPORT.md)
    gain = np.array([1.24, 1.17, 1.08])
    col3 = col3 * (1 - mouth[:, None]) * gain + col3 * mouth[:, None]
    col_img = np.zeros((S, S, 3))
    col_img[yy, xx] = np.clip(col3, 0, 1)
    col_img = texproj.dilate_margin(col_img, T.valid, px=12)
    nrm_img = texproj.dilate_margin(nrm_img, T.valid, px=12)

    rough = 0.78 + 0.08 * (1 - np.clip(groove, 0, 1))
    rough = rough * (1 - 0.6 * reg["ventral"]) + 0.62 * 0.6 * reg["ventral"]
    rough = rough * (1 - knob) + 0.9 * knob
    rough = rough * (1 - mouth) + 0.35 * mouth
    rough = rough * (1 - scar) + 0.6 * scar
    orm = np.zeros((S, S, 3))
    orm[..., 0] = 1.0
    orm[..., 1] = 0.8
    orm[yy, xx, 0] = aov
    orm[yy, xx, 1] = rough
    orm = texproj.dilate_margin(orm, T.valid, px=12)

    # ---------------------------------------------------------------- save masters + runtime
    tdir = paths.ensure(C.cache("tex"))      # copied to forest_rescue/blender/textures/boss by the export stage
    rdir = paths.ensure(tdir, "runtime")
    core.save_rgba(os.path.join(tdir, f"{AID}_basecolor_{S}.png"), col_img)
    core.save_rgba(os.path.join(tdir, f"{AID}_normal_{S}.png"), nrm_img)
    core.save_rgba(os.path.join(tdir, f"{AID}_orm_{S}.png"), orm)
    import cv2
    from PIL import Image
    rs = C.TEX_RUNTIME

    def down(a):
        return cv2.resize(a, (rs, rs), interpolation=cv2.INTER_AREA) if a.shape[0] != rs else a

    Image.fromarray((np.clip(down(col_img), 0, 1) * 255 + 0.5).astype(np.uint8)).save(
        os.path.join(rdir, f"{AID}_basecolor.jpg"), quality=90)
    nr = down(nrm_img) * 2 - 1
    nr /= np.maximum(np.linalg.norm(nr, axis=2, keepdims=True), 1e-9)
    core.save_rgba(os.path.join(rdir, f"{AID}_normal.png"), nr * 0.5 + 0.5)
    core.save_rgba(os.path.join(rdir, f"{AID}_orm.png"), down(orm))
    kc, kr = MT.keratin_atlas(512)
    korm = np.stack([np.ones_like(kr), kr, np.zeros_like(kr)], -1)
    Image.fromarray((kc * 255 + 0.5).astype(np.uint8)).save(os.path.join(rdir, f"{AID}_keratin_basecolor.jpg"),
                                                             quality=92)
    core.save_rgba(os.path.join(rdir, f"{AID}_keratin_orm.png"), korm)
    core.save_rgba(os.path.join(tdir, f"{AID}_keratin_basecolor_512.png"), kc)
    log("saved textures")

    # ---------------------------------------------------------------- materials
    bpy.data.objects.remove(body, do_unlink=True)
    for nm in ("M_maw_skin", "M_maw_keratin"):
        m = bpy.data.materials.get(nm)
        if m:
            m.name = nm + "_old"
    ld = lambda f, cs: core.load_image(os.path.join(rdir, f), cs)  # noqa: E731
    skin = core.material("M_maw_skin", base_tex=ld(f"{AID}_basecolor.jpg", "sRGB"),
                         rough_tex=ld(f"{AID}_orm.png", "Non-Color"), normal_tex=ld(f"{AID}_normal.png", "Non-Color"))
    orm_img = skin.node_tree.nodes  # metal from the same ORM image (blue)
    korm_img = ld(f"{AID}_keratin_orm.png", "Non-Color")
    ker = core.material("M_maw_keratin", base_tex=ld(f"{AID}_keratin_basecolor.jpg", "sRGB"),
                        rough_tex=korm_img, metal_tex=korm_img)
    sk_orm = bpy.data.images[f"{AID}_orm.png"]
    skin2 = core.material("M_maw_skin_tmp", base_tex=bpy.data.images[f"{AID}_basecolor.jpg"], rough_tex=sk_orm,
                          metal_tex=sk_orm, normal_tex=bpy.data.images[f"{AID}_normal.png"])
    bpy.data.materials.remove(skin)
    skin2.name = "M_maw_skin"
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name.startswith(AID):
            o.data.materials[0] = skin2
            o.data.materials[1] = ker
    for m in list(bpy.data.materials):
        if m.name.endswith("_old") or m.name == "M_bake_tmp":
            bpy.data.materials.remove(m)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=C.cache("maw_tex.blend"), compress=True)
    log("saved maw_tex.blend")


if __name__ == "__main__":
    main()
