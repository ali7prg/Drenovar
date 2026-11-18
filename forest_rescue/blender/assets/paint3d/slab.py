"""Inflated painted props (no bpy): per-face planar UVs from the reference camera (front/back = the painting,
back mirrored), tri-planar swatch UVs for side faces and a separate top swatch (moss) for up-facing faces,
plus the texture assembly. Shared by the moss rock, fallen trunk and landmark masonry."""
import cv2
import numpy as np
from scipy import ndimage as ndi

import geom
import seg
from frlib import texproj

# texture regions (u0, v0, u1, v1), Blender UV (v up)
FRONT = (0.0, 0.30, 0.70, 1.0)
SIDE = (0.70, 0.62, 1.0, 1.0)
TOP = (0.70, 0.30, 1.0, 0.62)
EXTRA = (0.0, 0.0, 1.0, 0.29)      # free band (limb strips, extra parts)


def mirror_wrap(a3):
    """Per-face consistent mirrored wrap of coordinates (M,3) into [0,1] (seamless with mirrored swatches)."""
    a3 = a3 - 2.0 * np.floor(a3[:, :1] / 2.0)
    return np.clip(np.where(a3[:, :1] > 1.0, 2.0 - a3, a3), 0, 1)


def planar_uvs(V, T, N, view, W, H, clip, front_thresh=0.42, top_thresh=0.62, per_side=2.5, per_top=2.5,
               exclude_mask=None, regions=(FRONT, SIDE, TOP), top_paint_mask=None):
    """Un-indexed (per-face) UVs. Returns V3 (M*3,3), T3, UV3 (M*3,2), N3, kind (M,) 0 front 1 side 2 top."""
    FR, SR, TR = regions
    Vc = V[T]
    Nc = N[T]
    fn = geom.nrm(np.cross(Vc[:, 1] - Vc[:, 0], Vc[:, 2] - Vc[:, 0]))
    cen = Vc.mean(1)
    uc, vc, _ = view.project(cen)
    ex = np.zeros(len(T), bool)
    if exclude_mask is not None:
        ui = np.clip(np.round(uc).astype(int), 0, W - 1)
        vi = np.clip(np.round(vc).astype(int), 0, H - 1)
        ex = exclude_mask[vi, ui] & (vc < H)
    kind = np.where(np.abs(fn @ view.d) >= front_thresh, 0, 1)
    kind = np.where((kind == 1) & (fn[:, 2] > top_thresh), 2, kind)
    kind = np.where(ex, 1, kind)
    uu, vv, _ = view.project(Vc.reshape(-1, 3))
    vv = np.clip(vv, 0, clip - 2)
    uu = np.clip(uu, 0, W - 1)
    uv_f = np.stack([FR[0] + (FR[2] - FR[0]) * uu / W, FR[3] - (FR[3] - FR[1]) * vv / H], -1).reshape(-1, 3, 2)
    P_ = Vc
    dom_z = (np.abs(fn[:, 2]) > np.maximum(np.abs(fn[:, 0]), np.abs(fn[:, 1])))
    dom_x = np.abs(fn[:, 0]) >= np.abs(fn[:, 1])
    a_side = np.where(dom_x[:, None], P_[..., 1], P_[..., 0])
    b_side = P_[..., 2]
    us = mirror_wrap(a_side / per_side)
    vs = mirror_wrap(b_side / (per_side * (SR[3] - SR[1]) / (SR[2] - SR[0])))
    uv_s = np.stack([SR[0] + (SR[2] - SR[0]) * us, SR[1] + (SR[3] - SR[1]) * vs], -1)
    ut = mirror_wrap(P_[..., 0] / per_top)
    vt = mirror_wrap(P_[..., 1] / (per_top * (TR[3] - TR[1]) / (TR[2] - TR[0])))
    uv_t = np.stack([TR[0] + (TR[2] - TR[0]) * ut, TR[1] + (TR[3] - TR[1]) * vt], -1)
    if top_paint_mask is not None:
        # top faces the elevated reference camera sees inside the painting: texture = the painted top
        ui = np.clip(np.round(uc).astype(int), 0, W - 1)
        vi = np.clip(np.round(vc).astype(int), 0, H - 1)
        seen = top_paint_mask[vi, ui] & (vc >= 0) & (vc < clip)
        kind = np.where((kind == 2) & seen, 3, kind)
    UV = np.where(((kind == 0) | (kind == 3))[:, None, None], uv_f,
                  np.where((kind == 2)[:, None, None], uv_t, uv_s))
    M = len(T)
    return Vc.reshape(-1, 3), np.arange(M * 3).reshape(-1, 3), UV.reshape(-1, 2), Nc.reshape(-1, 3), kind


def swatch_tile(sw, w, h, ref_px=None, scale=1.0, match_strength=1.0):
    if scale != 1.0:
        sw = cv2.resize(sw, (max(8, int(sw.shape[1] * scale)), max(8, int(sw.shape[0] * scale))),
                        interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LANCZOS4)
    t2 = np.concatenate([np.concatenate([sw, sw[:, ::-1]], 1), np.concatenate([sw[::-1], sw[::-1, ::-1]], 1)], 0)
    tl = np.tile(t2, (h // t2.shape[0] + 1, w // t2.shape[1] + 1, 1))[:h, :w]
    if ref_px is not None and len(ref_px) > 20 and match_strength > 0:
        m_s, s_s = tl.reshape(-1, 3).mean(0), tl.reshape(-1, 3).std(0) + 1e-4
        m_k, s_k = ref_px.mean(0), ref_px.std(0) + 1e-4
        k = np.clip(s_k / s_s, 0.6, 1.4)
        tl2 = np.clip((tl - m_s) * k + m_k, 0, 1)
        tl = tl * (1 - match_strength) + tl2 * match_strength
    return tl.astype(np.float32)


def front_texture(img, paint_mask, clip, size_wh):
    """The painting (paint_mask pixels) filled into the rest (pull-push), resized into the FRONT region."""
    H, W = img.shape[:2]
    known = paint_mask.copy()
    known[clip:] = False
    base = img.astype(np.float64).copy()
    f = texproj.fill(base, known).astype(np.float32)
    f[clip:] = f[clip - 1:clip].mean(0)
    return cv2.resize(f, size_wh, interpolation=cv2.INTER_LANCZOS4)


def assemble(size, img, paint_mask, clip, side_sw, top_sw, side_px=None, top_px=None, side_scale=1.0, top_scale=1.0,
             regions=(FRONT, SIDE, TOP), sharpen=0.25):
    FR, SR, TR = regions
    tex = np.zeros((size, size, 3), np.float32)

    def box(R):
        return int(R[0] * size), int((1 - R[3]) * size), int(R[2] * size), int((1 - R[1]) * size)

    x0, y0, x1, y1 = box(FR)
    tex[y0:y1, x0:x1] = front_texture(img, paint_mask, clip, (x1 - x0, y1 - y0))
    x0, y0, x1, y1 = box(SR)
    tex[y0:y1, x0:x1] = swatch_tile(side_sw, x1 - x0, y1 - y0, side_px, side_scale)
    x0, y0, x1, y1 = box(TR)
    tex[y0:y1, x0:x1] = swatch_tile(top_sw, x1 - x0, y1 - y0, top_px, top_scale)
    if sharpen:
        bl = cv2.GaussianBlur(tex, (0, 0), 1.0)
        tex = np.clip(tex + sharpen * (tex - bl), 0, 1)
    return tex


def slab_depth(mask, k=1.6, dmax_px=None, dmax_frac=0.45, smooth=1.0):
    """Mesa profile: h = min(k * DT, Dmax) -> flat front face with bevelled edges (fractured slab, not a pillow)."""
    dt = ndi.distance_transform_edt(mask)
    if dmax_px is None:
        ys, xs = np.nonzero(mask)
        dmax_px = dmax_frac * min(np.ptp(xs) + 1, np.ptp(ys) + 1)
    h = np.minimum(k * dt, dmax_px)
    if smooth:
        h = ndi.gaussian_filter(h, smooth) * mask
    return h
