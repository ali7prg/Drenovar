"""Stage 3: textures.  Painting projection from every sheet view onto the faces it sees:
  left (ortho, annotation strokes inpainted) + its scar-free mirror for the right side,
  front (ortho), rear three-quarter (solved camera) + mirror,
  head close-up (solvePnP camera, jaw opened by the solved angle, TPS landmark correction) + its
  scar-free mirror — the close-up is the single source for the head (eye/teeth/scar never doubled);
then region scale synthesis (large 5-12 cm neck/shoulders, medium 2-5 cm flanks/thighs, fine 0.5-2 cm
belly/inner limbs), normal map from the scale height, ORM, keratin/eye/tongue atlas.

In: cache/maw2_rig.blend   Out: cache/maw2_tex.blend + textures/boss/*.png masters
"""
import json
import math
import os
import sys
import time

import bpy
import cv2
import numpy as np
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mv2_common as C  # noqa: E402
import mv2_body as B  # noqa: E402
import mv2_cams as CM  # noqa: E402
import mv2_details as D  # noqa: E402
import mv2_refs as R  # noqa: E402
import mv2_texproj as TP  # noqa: E402
from frlib import core, paths, refs, texproj  # noqa: E402

HINGE = np.array([0.0, -3.22, 2.96])


# ------------------------------------------------------------------------------------ views
def mirror_view_ortho(v, name, scar_free_img=None):
    im = (scar_free_img if scar_free_img is not None else v.image)[:, ::-1].copy()
    m = v.mask[:, ::-1].copy()
    W = im.shape[1]
    return refs.View(name=name, image=im, mask=m, d=np.array([1.0, 0.0, 0.0]), ppm=v.ppm, ax=W - v.ax, ay=v.ay)


def mirror_cam(cam, name, image=None):
    F = np.diag([-1.0, 1.0, 1.0])
    M = np.diag([-1.0, 1.0, 1.0])
    Rm = F @ cam.R @ M
    rv = cv2.Rodrigues(Rm)[0].reshape(3)
    tv = F @ cam.tvec
    W = cam.size[0]
    K = cam.K.copy()
    K[0, 2] = W - cam.K[0, 2]
    img = (image if image is not None else cam.image)[:, ::-1].copy()
    return CM.PerspCam(name, img, cam.mask[:, ::-1].copy(), K, rv, tv)


def head_scar_free(crop):
    x0, y0 = R.HEAD_BOX[:2]
    mk = np.zeros(crop.shape[:2], np.uint8)
    pts = np.array([(306, 563), (296, 586), (283, 612), (288, 634), (300, 660), (322, 688), (346, 712)], float)
    pts -= (x0, y0)
    cv2.polylines(mk, [pts.astype(np.int32)], False, 255, 13)
    return R.inpaint(crop, mk > 0, 6)


def side_scar_free():
    return R.side_colour(remove_scar=True)


def jaw_pose(V, N, wjaw, deg):
    a = math.radians(deg)
    Rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    Vr = (V - HINGE) @ Rx.T + HINGE
    Nr = N @ Rx.T
    w = wjaw[:, None]
    Vp = V * (1 - w) + Vr * w
    Np = N * (1 - w) + Nr * w
    Np /= np.maximum(np.linalg.norm(Np, axis=1, keepdims=True), 1e-9)
    return Vp, Np


def texel_from_verts(T, tris, Vx):
    """Per-texel interpolation of a per-vertex attribute (posed positions/normals)."""
    W, H = T.size
    out = np.zeros((H, W, 3))
    yy, xx = np.nonzero(T.valid)
    t = T.tri[yy, xx]
    b = T.bary[yy, xx]
    out[yy, xx] = (Vx[tris[t]] * b[..., None]).sum(1)
    return out


# ------------------------------------------------------------------------------------ synthesis
def voronoi_f12(P, cell, seed):
    f1, f2 = texproj.voronoi(P.astype(np.float64), freq=1.0 / cell, seed=seed, jitter=0.85)
    return f1, f2


def cell_id_noise(P, cell, seed):
    """Per-cell random value (nearest feature cell hash) for per-scale tint variation."""
    Q = P / cell
    i = np.floor(Q).astype(np.int64)
    best = np.full(len(P), 9.0)
    val = np.zeros(len(P))
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = i + np.array([dx, dy, dz])
                fp = c + 0.5 + 0.85 * (np.stack([texproj._hash3(c[:, 0], c[:, 1], c[:, 2], seed + k)
                                                 for k in range(3)], -1) - 0.5)
                d = np.linalg.norm(Q - fp, axis=1)
                better = d < best
                best = np.where(better, d, best)
                val = np.where(better, texproj._hash3(c[:, 0], c[:, 1], c[:, 2], seed + 11), val)
    return val


def region_weights(P, N):
    """large / medium / fine / dorsal weights per texel (sum 1)."""
    prof = B.trunk_profile()
    y, z = P[:, 1], P[:, 2]
    zc = np.interp(y, prof["Y"], prof["zc"])
    hz = np.interp(y, prof["Y"], prof["hz"])
    t = (z - zc) / np.maximum(hz, 0.05)
    neck_sh = np.clip((y + 3.15) / 0.25, 0, 1) * np.clip((-1.15 - y) / 0.35, 0, 1) * np.clip((t + 0.2) / 0.4, 0, 1)
    dorsal = np.clip((t - 0.72) / 0.18, 0, 1) * np.clip((y + 3.0) / 0.3, 0, 1)
    belly = np.clip((-t - 0.35) / 0.3, 0, 1) * (z > 1.0) * np.clip((y + 3.4) / 0.3, 0, 1)
    # inner limb faces: normal pointing to the body midline, low on the body
    inner = np.clip((-(N[:, 0] * np.sign(P[:, 0])) - 0.35) / 0.3, 0, 1) * (z < 2.0) * (np.abs(P[:, 0]) > 0.25)
    fine = np.clip(belly + inner, 0, 1)
    large = neck_sh * (1 - fine)
    dors = dorsal * (1 - fine) * (1 - large)
    med = np.clip(1 - large - fine - dors, 0, 1)
    return large, med, fine, dors


def scale_height(P, N):
    large, med, fine, dors = region_weights(P, N)
    h = np.zeros(len(P))
    cv = np.zeros(len(P))
    for w, cell, seed in ((large, 0.085, 3), (med, 0.036, 5), (fine, 0.013, 7), (dors, 0.060, 9)):
        sel = w > 0.01
        if not sel.any():
            continue
        f1, f2 = voronoi_f12(P[sel], cell, seed)
        edge = np.clip((f2 - f1) / (cell * 0.22), 0, 1)
        dome = np.clip(1 - (f1 / (cell * 0.75)) ** 2, 0, 1)
        hh = 0.55 * edge ** 0.6 + 0.45 * dome
        h[sel] += w[sel] * hh
        cv[sel] += w[sel] * cell_id_noise(P[sel], cell, seed)
    return h, cv, (large, med, fine, dors)


# ------------------------------------------------------------------------------------ keratin atlas
def keratin_atlas(size=512):
    img = np.zeros((size, size, 3))
    yy, xx = np.mgrid[0:size, 0:size] / size        # yy: 0 top
    v = 1 - yy                                       # UV v
    # teeth (u 0-0.5, v 0.3-1): gum-pink root -> ivory -> pale worn tip
    tt = np.clip((v - 0.30) / 0.70, 0, 1)
    ivory = np.array([0.80, 0.72, 0.56])
    root = np.array([0.55, 0.36, 0.30])
    tip = np.array([0.90, 0.85, 0.72])
    tc = np.where(tt[..., None] < 0.12, root + (ivory - root) * (tt[..., None] / 0.12), ivory + (tip - ivory) * np.clip((tt[..., None] - 0.12) / 0.88, 0, 1))
    stain = 0.92 + 0.08 * np.sin(xx * 60.0)[..., None]
    reg = (xx < 0.5) & (v >= 0.30)
    img[reg] = (tc * stain)[reg]
    # claws: dark horn base -> bronze -> pale tip (art/03 foot detail)
    base = np.array([0.20, 0.16, 0.12])
    mid = np.array([0.45, 0.36, 0.24])
    ctip = np.array([0.80, 0.72, 0.56])
    cc = np.where(tt[..., None] < 0.55, base + (mid - base) * (tt[..., None] / 0.55), mid + (ctip - mid) * np.clip((tt[..., None] - 0.55) / 0.45, 0, 1))
    shade = 0.85 + 0.15 * np.cos((xx - 0.75) * 2 * math.pi * 2)[..., None]
    reg = (xx >= 0.5) & (v >= 0.30)
    img[reg] = (cc * shade)[reg]
    # eye: amber iris, dark vertical slit pupil, limbal ring, specular dot
    eu = (xx - 0.125) / 0.125
    ev = (v - 0.125) / 0.125
    r = np.sqrt(eu ** 2 + ev ** 2)
    amber = np.array([0.86, 0.55, 0.12]) * (1.05 - 0.35 * r)[..., None] + np.array([0.08, 0.05, 0.0]) * np.sin(
        np.arctan2(ev, eu) * 18)[..., None] * 0.6
    eye = np.where((r > 0.88)[..., None], np.array([0.18, 0.10, 0.04]), amber)
    pupil = (np.abs(eu) < 0.13 * np.sqrt(np.clip(1 - (ev / 0.82) ** 2, 0, 1))) & (r < 0.85)
    eye[pupil] = (0.04, 0.03, 0.02)
    spec = np.sqrt((eu + 0.30) ** 2 + (ev - 0.35) ** 2) < 0.10
    eye[spec] = (0.95, 0.92, 0.85)
    reg = (xx < 0.25) & (v < 0.25)
    img[reg] = eye[reg]
    # tongue: muted rose-red with darker midline groove (close-up)
    tu = (xx - 0.75) / 0.25
    tong = np.array([0.55, 0.30, 0.28]) * (0.85 + 0.15 * np.cos(tu * math.pi * 3))[..., None]
    reg = (xx >= 0.5) & (v < 0.25)
    img[reg] = tong[reg]
    # gap between teeth/claws strips (v 0.25-0.30): neutral
    reg = (v >= 0.25) & (v < 0.30)
    img[reg] = (0.5, 0.42, 0.33)
    img[(xx >= 0.25) & (xx < 0.5) & (v < 0.25)] = (0.42, 0.24, 0.22)   # gum / mouth flesh swatch
    return np.clip(img, 0, 1)


# ------------------------------------------------------------------------------------ main
def main():
    t0 = time.time()
    bpy.ops.wm.open_mainfile(filepath=C.cache("maw2_rig.blend"))
    body = bpy.data.objects["maw_body"]
    V, tris, uv, VN = core.mesh_arrays(body, evaluated=False)
    wz = np.load(C.cache("maw2_weights_lod0.npz"))
    names = [str(n) for n in wz["names"]]
    W = wz["W"].astype(np.float64)
    wjaw = W[:, names.index("jaw")]
    size = C.TEX
    T = texproj.rasterize_uv(V, tris, uv, size, VN)
    C.log(f"texels {T.valid.sum()} {time.time() - t0:.1f}s")

    # --- views
    left = R.side_view(corrected=True, colour=True)
    right = mirror_view_ortho(left, "right_mirror", side_scar_free())
    front = R.front_view(corrected=False)
    front.name = "front"
    # rear camera (silhouette-refined), solved against the current body occupancy
    surf = V[::2]
    rear, rinfo = CM.rear_cam(occ_points=surf, refine=True, log=C.cache("rear_cam.json"))
    rear_m = mirror_cam(rear, "rear34_mirror")
    head, hinfo, jaw_deg = CM.head_cam(log=C.cache("head_cam.json"))
    # TPS landmark correction for the close-up (and its mirror)
    names_h, P3, p2 = CM.head_points(jaw_deg)
    pu, pv, _ = head.project(P3)
    pproj = np.stack([pu, pv], 1)
    warp = TP.TPSWarp(pproj, p2, head.size, smoothing=0.5)
    Wc = head.size[0]
    head_m = mirror_cam(head, "head_mirror", head_scar_free(head.image))
    warp_m = TP.TPSWarp(np.stack([Wc - pproj[:, 0], pproj[:, 1]], 1), np.stack([Wc - p2[:, 0], p2[:, 1]], 1),
                        head.size, smoothing=0.5)
    C.log(f"cams: rear pnp {rinfo['pnp_rms_px']:.1f}px refined IoU {rinfo.get('refined_iou', 0):.3f}; head pnp "
          f"{hinfo['pnp_rms_px']:.1f}px jaw {jaw_deg} {time.time() - t0:.1f}s")

    # posed geometry for the close-up views (jaw open)
    Vp, Np = jaw_pose(V, VN, wjaw, jaw_deg)
    texel_pos = {"head_closeup": texel_from_verts(T, tris, Vp), "head_mirror": texel_from_verts(T, tris, Vp)}
    nposed = texel_from_verts(T, tris, Np)
    nposed /= np.maximum(np.linalg.norm(nposed, axis=-1, keepdims=True), 1e-9)
    head.normals_posed = nposed
    head_m.normals_posed = nposed
    # colour transfer: close-up tonality -> side view tonality on the head (mean/std per channel, LAB)
    hv = [left, head]
    zb0 = {"left": TP.zbuffer_fast(V, tris, left), "head_closeup": TP.zbuffer_fast(Vp, tris, head)}
    _c, _w, per0 = TP.project_views(T, hv, zb0, texel_pos={"head_closeup": texel_pos["head_closeup"]},
                                    warps={"head_closeup": warp}, per_view_out=True)
    col_s, ws_s = TP.project_views(T, [left], zb0)
    col_h, ws_h = TP.project_views(T, [head], zb0, texel_pos={"head_closeup": texel_pos["head_closeup"]},
                                   warps={"head_closeup": warp})
    both = (ws_s > 0.05) & (ws_h > 0.05) & (T.pos[..., 1] < -2.95)
    if both.sum() > 500:
        a = cv2.cvtColor(col_s[both][None].astype(np.float32), cv2.COLOR_RGB2LAB)[0]
        b = cv2.cvtColor(col_h[both][None].astype(np.float32), cv2.COLOR_RGB2LAB)[0]
        ms, ss, mh, sh = a.mean(0), a.std(0), b.mean(0), b.std(0)
        gain = np.clip(ss / np.maximum(sh, 1e-3), 0.6, 1.3)
        gain[0] = np.clip(0.5 + 0.5 * gain[0], 0.7, 1.2)            # keep most of the close-up contrast

        def transfer(img):
            lab = cv2.cvtColor(img.astype(np.float32), cv2.COLOR_RGB2LAB)
            lab = (lab - mh) * gain + mh + (ms - mh) * 0.85
            return np.clip(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB), 0, 1).astype(np.float64)
        head.image = transfer(head.image)
        head_m.image = transfer(head_m.image)
        C.log(f"close-up colour transfer: mean {mh.round(2)} -> {ms.round(2)} gain {gain.round(2)}")
    views = [left, right, front, rear, rear_m, head, head_m]
    zb = {}
    for v in views:
        geo = Vp if v.name.startswith("head") else V
        zb[v.name] = TP.zbuffer_fast(geo, tris, v)
    C.log(f"zbuffers {time.time() - t0:.1f}s")
    # gates: the close-up is the only source on the head (Y < -2.95); body views fade out there
    Y = T.pos[..., 1]
    X = T.pos[..., 0]
    g_head = np.clip((-2.92 - Y) / 0.12, 0, 1)
    # lip band (outer surface within +-6 cm of the closed lip line): the side view (closed mouth, teeth
    # over the lower lip) is the source there, the open-mouth close-up only for the head above/below it
    zl_t = np.interp(Y, B.head_profile()["Y"], B.head_profile()["zlip"])
    wu_t, _ = B.head_widths(Y)
    hv_t = np.full(Y.shape, 1.0)
    vy, vx = np.nonzero(T.valid)
    hv_t[vy, vx] = B.head_part().fn(T.pos[vy, vx] - T.nrm[vy, vx] * 0.004)
    lipband = (np.abs(T.pos[..., 2] - zl_t) < 0.075) & (hv_t > -0.012) & (Y < -3.25)
    lipband = ndi.gaussian_filter(lipband.astype(np.float64), 1.5)
    g_cu = g_head * (1 - lipband)
    gates = {"head_closeup": g_cu * (X > -0.02), "head_mirror": g_cu * (X < 0.02),
             "left": 1 - 0.97 * g_cu, "right_mirror": 1 - 0.97 * g_cu, "front": 1 - 0.9 * g_cu,
             "rear34": 1 - g_head, "rear34_mirror": 1 - g_head}
    prio = {"left": 1.0, "right_mirror": 1.0, "front": 0.9, "rear34": 0.55, "rear34_mirror": 0.55,
            "head_closeup": 6.0, "head_mirror": 6.0}
    col, wsum, per = TP.project_views(T, views, zb, texel_pos=texel_pos, warps={"head_closeup": warp,
                                      "head_mirror": warp_m}, priority=prio, region_gate=gates, per_view_out=True)
    known = wsum > 0.02
    C.log(f"projected: coverage {known.sum() / T.valid.sum():.3f} {time.time() - t0:.1f}s")
    cov = {k: float((v > 0.02).sum() / T.valid.sum()) for k, v in per.items()}

    # --- unseen texels: pull-push from neighbours, tinted toward the palette region colour
    filled = texproj.fill(col, known)
    yy, xx = np.nonzero(T.valid)
    P = T.pos[yy, xx]
    N = T.nrm[yy, xx]
    h, cvar, (large, med, fine, dors) = scale_height(P, N)
    C.log(f"scale synthesis {time.time() - t0:.1f}s")
    base = filled[yy, xx]
    unseen = ~known[yy, xx]
    umber = np.array([0.42, 0.27, 0.17])
    belly_tint = np.clip(fine * 1.0, 0, 1)[:, None] * unseen[:, None]
    base = base * (1 - 0.45 * belly_tint) + umber * 0.45 * belly_tint
    # mouth interior (inside the closed head volume): gums/palate flesh where the close-up does not see
    zl = np.interp(P[:, 1], B.head_profile()["Y"], B.head_profile()["zlip"])
    wu, _ = B.head_widths(P[:, 1])
    headvol = B.head_part().fn(P - N * 0.004)
    inner_mouth = (P[:, 1] < -3.30) & (np.abs(P[:, 2] - zl) < 0.17) & (headvol < -0.012)
    flesh = np.array([0.45, 0.22, 0.20])
    base[inner_mouth & unseen] = flesh * (0.8 + 0.2 * cvar[inner_mouth & unseen])[:, None]
    # scale detail on the albedo: crevices darker, scale crowns lighter, per-scale value jitter
    seen_amp = np.where(P[:, 1] < -2.95, 0.06, 0.14)
    amp = np.where(unseen, 0.22, seen_amp)
    mod = 1.0 + amp * (h - 0.55) * 1.4 + 0.05 * (cvar - 0.5) * (1 - unseen * 0.0)
    base = np.clip(base * mod[:, None], 0, 1)
    albedo = np.zeros((size, size, 3))
    albedo[yy, xx] = base
    albedo = texproj.fill(albedo, T.valid)            # whole atlas filled: no dark mip bleeding at seams
    # --- normal map from the scale height (+ small osteoderm/ridge relief), tangent space
    hmap = np.zeros((size, size))
    hmap[yy, xx] = h
    texel_m = 9.0 / size * 1.15
    normal = texproj.height_to_normal(hmap, T.valid, strength=0.0035, texel_m=texel_m)
    normal = texproj.fill(normal, T.valid)
    # --- ORM: occlusion from crevices, roughness by region (palette call-outs), metal 0
    occ = np.ones((size, size))
    occ[yy, xx] = 0.72 + 0.28 * np.clip(h * 1.3, 0, 1)
    rough = np.full((size, size), 0.8)
    rough[yy, xx] = np.clip(0.80 + 0.10 * dors + 0.06 * large - 0.16 * fine + 0.05 * (1 - h), 0.5, 0.95)
    orm = np.stack([occ, rough, np.zeros_like(occ)], -1)
    orm = texproj.fill(orm, T.valid)
    # --- save masters + runtime images
    tdir = paths.ensure(paths.TEXTURE_SOURCES, C.GROUP)
    a_path = os.path.join(tdir, f"{C.ASSET_ID}_v2_basecolor_{size}.png")
    n_path = os.path.join(tdir, f"{C.ASSET_ID}_v2_normal_{size}.png")
    o_path = os.path.join(tdir, f"{C.ASSET_ID}_v2_orm_{size}.png")
    k_path = os.path.join(tdir, f"{C.ASSET_ID}_v2_keratin_512.png")
    core.save_rgba(a_path, albedo)
    core.save_rgba(n_path, normal)
    core.save_rgba(o_path, orm)
    core.save_rgba(k_path, keratin_atlas(512))
    # coverage preview (which view textured what)
    cols = {"left": (1, 0.2, 0.2), "right_mirror": (1, 0.6, 0.2), "front": (0.2, 0.9, 0.2), "rear34": (0.2, 0.4, 1),
            "rear34_mirror": (0.4, 0.8, 1), "head_closeup": (1, 1, 0.2), "head_mirror": (0.9, 0.3, 0.9)}
    cprev = np.zeros((size, size, 3))
    ws = np.maximum(wsum, 1e-9)
    for k, pv in per.items():
        cprev += (pv / ws)[..., None] * np.array(cols[k])
    cprev[~known] = (0.1, 0.1, 0.1)
    core.save_rgba(C.cache("tex_coverage.png"), cprev[::2, ::2])
    # --- materials
    img_a = core.load_image(a_path, "sRGB", f"{C.ASSET_ID}_basecolor")
    img_n = core.load_image(n_path, "Non-Color", f"{C.ASSET_ID}_normal")
    img_o = core.load_image(o_path, "Non-Color", f"{C.ASSET_ID}_orm")
    img_k = core.load_image(k_path, "sRGB", f"{C.ASSET_ID}_keratin")
    m_body = core.material(f"{C.ASSET_ID}_body", base_tex=img_a, rough_tex=img_o, metal_tex=img_o, normal_tex=img_n,
                           normal_strength=1.0)
    m_ker = core.material(f"{C.ASSET_ID}_keratin", base_tex=img_k, rough=0.45)
    core.assign(body, m_body)
    for n in ("maw_teeth", "maw_claws", "maw_eyes", "maw_tongue", "maw_mouth"):
        core.assign(bpy.data.objects[n], m_ker)
    info = {"coverage_by_view": cov, "coverage_total": float(known.sum() / T.valid.sum()), "rear_cam": rinfo,
            "head_cam": hinfo, "jaw_open_deg_closeup": jaw_deg, "texture_size": size}
    with open(C.cache("tex_info.json"), "w") as fh:
        json.dump(info, fh, indent=2, default=float)
    bpy.ops.wm.save_as_mainfile(filepath=C.cache("maw2_tex.blend"), compress=True)
    C.log(f"stage tex done {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
