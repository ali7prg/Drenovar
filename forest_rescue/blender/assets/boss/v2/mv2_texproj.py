"""Projection helpers for ortho (frlib View) and perspective (PerspCam) reference views (numpy + cv2).

* zbuffer_fast: painter's-order triangle-id raster per view -> per-pixel depth of the nearest surface
* project_views: blend reference colours onto texels with visibility, facing |n.v| >= 0.5 ramp,
  mask erosion, per-view priority, optional per-view posed texel positions and 2-D TPS warps.
"""
import cv2
import numpy as np
from scipy import ndimage as ndi


def view_dir_at(view, P):
    if hasattr(view, "view_dirs"):
        return view.view_dirs(P)
    return np.broadcast_to(view.d, P.shape)


def zbuffer_fast(verts, tris, view):
    W, H = view.size
    u, v, dep = view.project(verts)
    U, Vv, D = u[tris], v[tris], dep[tris]
    order = np.argsort(-D.mean(1))          # far -> near
    ids = np.full((H, W), -1, np.int32)
    shift = 3
    pts = np.round(np.stack([U - 0.5, Vv - 0.5], -1) * (1 << shift)).astype(np.int32)
    for t in order:
        cv2.fillConvexPoly(ids, pts[t], int(t), lineType=cv2.LINE_8, shift=shift)
    zb = np.full((H, W), np.inf)
    yy, xx = np.nonzero(ids >= 0)
    t = ids[yy, xx]
    # depth from barycentrics in screen space
    a = np.stack([U[t, 0], Vv[t, 0]], 1)
    b = np.stack([U[t, 1], Vv[t, 1]], 1)
    c = np.stack([U[t, 2], Vv[t, 2]], 1)
    p = np.stack([xx + 0.5, yy + 0.5], 1).astype(float)
    v0, v1, v2 = b - a, c - a, p - a
    d00 = (v0 * v0).sum(1)
    d01 = (v0 * v1).sum(1)
    d11 = (v1 * v1).sum(1)
    d20 = (v2 * v0).sum(1)
    d21 = (v2 * v1).sum(1)
    den = d00 * d11 - d01 * d01
    den = np.where(np.abs(den) < 1e-12, 1e-12, den)
    bv = np.clip((d11 * d20 - d01 * d21) / den, 0, 1)
    bw = np.clip((d00 * d21 - d01 * d20) / den, 0, 1)
    bu = np.clip(1 - bv - bw, 0, 1)
    zb[yy, xx] = bu * D[t, 0] + bv * D[t, 1] + bw * D[t, 2]
    zb = ndi.minimum_filter(zb, size=3)
    return zb


def bilinear(img, u, v):
    n = len(u)
    cols = 4096
    rows = max(1, -(-n // cols))
    mx = np.zeros(rows * cols, np.float32)
    my = np.zeros(rows * cols, np.float32)
    mx[:n] = u - 0.5
    my[:n] = v - 0.5
    out = cv2.remap(img.astype(np.float32), mx.reshape(rows, cols), my.reshape(rows, cols),
                    interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return out.reshape(rows * cols, -1)[:n]


class TPSWarp:
    """2-D displacement field (thin-plate spline) from landmark residuals: corrected = p + f(p)."""

    def __init__(self, p_proj, p_ref, size, smoothing=1.0):
        from scipy.interpolate import RBFInterpolator
        W, H = size
        disp = np.asarray(p_ref, float) - np.asarray(p_proj, float)
        mean = disp.mean(0)
        border = np.array([[0, 0], [W, 0], [0, H], [W, H], [W / 2, 0], [W / 2, H], [0, H / 2], [W, H / 2]], float)
        P = np.concatenate([p_proj, border])
        Dd = np.concatenate([disp, np.repeat(mean[None], len(border), 0)])
        self.f = RBFInterpolator(P, Dd, kernel="thin_plate_spline", smoothing=smoothing)

    def __call__(self, u, v):
        out = np.empty((len(u), 2))
        step = 200000
        pts = np.stack([u, v], 1)
        for i in range(0, len(u), step):
            out[i:i + step] = self.f(pts[i:i + step])
        return u + out[:, 0], v + out[:, 1]


def project_views(T, views, zbufs, texel_pos=None, warps=None, priority=None, facing_lo=0.45, facing_hi=0.62,
                  depth_eps=0.035, mask_erode=2, region_gate=None, per_view_out=False):
    """Blend reference colours onto texels.

    texel_pos: {view_name: (H,W,3) posed texel positions} (default T.pos)
    warps: {view_name: TPSWarp}; priority: {view_name: weight multiplier}
    region_gate: {view_name: (H,W) multiplier} (e.g. head-only for the close-up)
    """
    W, H = T.size
    acc = np.zeros((H, W, 3))
    wsum = np.zeros((H, W))
    yy, xx = np.nonzero(T.valid)
    N0 = T.nrm[yy, xx]
    per = {}
    for view in views:
        P = (texel_pos[view.name] if texel_pos and view.name in texel_pos else T.pos)[yy, xx]
        vw, vh = view.size
        u, v, dep = view.project(P)
        ui = np.floor(u).astype(int)
        vi = np.floor(v).astype(int)
        ok = (ui >= 0) & (ui < vw) & (vi >= 0) & (vi < vh)
        zb = zbufs[view.name]
        zval = np.full(len(u), -np.inf)
        zval[ok] = zb[vi[ok], ui[ok]]
        vis = ok & (dep <= zval + depth_eps)
        if warps and view.name in warps:
            u, v = warps[view.name](u, v)
            ui = np.floor(u).astype(int)
            vi = np.floor(v).astype(int)
            ok2 = (ui >= 0) & (ui < vw) & (vi >= 0) & (vi < vh)
            vis &= ok2
        m = ndi.binary_erosion(view.mask, iterations=mask_erode) if mask_erode else view.mask
        inm = np.zeros(len(u), bool)
        okk = (ui >= 0) & (ui < vw) & (vi >= 0) & (vi < vh)
        inm[okk] = m[vi[okk], ui[okk]]
        N = N0
        if texel_pos and view.name in texel_pos and hasattr(view, "normals_posed"):
            N = view.normals_posed[yy, xx]
        facing = np.clip(-(N * view_dir_at(view, P)).sum(1), 0.0, 1.0)
        ramp = np.clip((facing - facing_lo) / (facing_hi - facing_lo), 0.0, 1.0)
        w = np.where(vis & inm, ramp * (0.35 + 0.65 * facing ** 2), 0.0)
        if priority and view.name in priority:
            w = w * priority[view.name]
        if region_gate and view.name in region_gate:
            w = w * region_gate[view.name][yy, xx]
        col = bilinear(view.image, u, v)[:, :3]
        acc[yy, xx] += w[:, None] * col
        wsum[yy, xx] += w
        if per_view_out:
            pv = np.zeros((H, W))
            pv[yy, xx] = w
            per[view.name] = pv
    out = acc / np.maximum(wsum, 1e-9)[..., None]
    return (out, wsum, per) if per_view_out else (out, wsum)
