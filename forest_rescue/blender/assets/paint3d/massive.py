"""Massive painted forms (no bpy): hollow-oak trunk = revolved lower trunk (per-row painted extents, elliptic
section) UNION inflated thick wood (distance-transform depth), with the painted arch carved through as a tunnel.
Marching cubes in camera space (u, v, t) -> world through the fitted reference view."""
import numpy as np
from scipy import ndimage as ndi
from skimage import measure, morphology

import geom


def arch_mask(wood_closed, fg, row_min, min_area=200, clip=None):
    """Background-coloured hole enclosed by the trunk (the walk-through arch), largest one below row_min.
    The arch opens onto the ground: close the outline along the clip row first."""
    wc = wood_closed.copy()
    if clip is not None:
        cols = np.nonzero(wc[clip - 6:clip].any(0))[0]
        if len(cols):
            wc[clip - 2:clip + 1, cols.min():cols.max() + 1] = True
    filled = ndi.binary_fill_holes(wc)
    holes = filled & ~wc & ~fg
    holes[:row_min] = False
    lab, n = ndi.label(holes)
    if not n:
        return np.zeros_like(holes)
    sizes = ndi.sum(holes, lab, np.arange(1, n + 1))
    i = int(np.argmax(sizes))
    if sizes[i] < min_area:
        return np.zeros_like(holes)
    return lab == (i + 1)


def open_bottom(arch, clip):
    """Extend the arch down to the clip row (the tunnel floor is the ground)."""
    out = arch.copy()
    rows = np.nonzero(arch.any(1))[0]
    if not len(rows):
        return out
    r1 = rows.max()
    cols = np.nonzero(arch[r1])[0]
    out[r1:clip + 1, cols.min():cols.max() + 1] = True
    return out


def trunk_field(ref, wood_closed, thick, tunnel, lathe_top, voxel=2.0, kd_lathe=0.82, kd_infl=0.9,
                ground_extra_m=0.35, smooth=1.0):
    """Returns world verts, faces of the massive trunk."""
    H, W = wood_closed.shape
    clip = ref.clip
    ground = ref.ground
    v_end = int(min(H + 40, ground + ground_extra_m * ref.ppm + 2))
    rows_all = np.nonzero(thick.any(1))[0]
    v_start = int(min(rows_all.min(), lathe_top)) - 3
    ys = np.arange(v_start, v_end, voxel)
    cols = np.nonzero((thick | wood_closed)[:clip].any(0))[0]
    xs = np.arange(max(0, cols.min() - 6), min(W, cols.max() + 7), voxel)
    # per-row outer extents of the lower trunk: run of closed wood (incl. the tunnel) containing the trunk
    # centre column; the half-width may not jump wider going up (side stumps are inflated, not revolved)
    body = (wood_closed | tunnel)
    tc = np.nonzero(tunnel.any(0))[0]
    cx0 = float(tc.mean()) if len(tc) else float(np.nonzero(body[clip - 1])[0].mean())
    xl = np.full(H + 200, np.nan)
    xr = np.full(H + 200, np.nan)
    for v in range(clip - 1, lathe_top - 1, -1):
        lab, n = ndi.label(body[v])
        if not n:
            continue
        k = lab[int(round(cx0))]
        if k == 0:
            continue
        run = np.nonzero(lab == k)[0]
        l_, r_ = float(run.min()), float(run.max())
        if v + 1 < clip and not np.isnan(xl[v + 1]):
            l_ = max(l_, xl[v + 1] - 1.0)
            r_ = min(r_, xr[v + 1] + 1.0)
        xl[v], xr[v] = l_, r_
    vv = np.arange(H + 200)
    ok = ~np.isnan(xl)
    xl = np.interp(vv, vv[ok], xl[ok])
    xr = np.interp(vv, vv[ok], xr[ok])
    # below the clip row: root flare spreading onto the ground (radius +35% at z = 0 and below)
    gr = max(ground - clip, 4)
    for v in range(clip, H + 200):
        f = min(1.0, (v - clip) / gr)
        c_ = 0.5 * (xl[clip - 1] + xr[clip - 1])
        a_ = 0.5 * (xr[clip - 1] - xl[clip - 1]) * (1.0 + 0.12 * f ** 1.5)
        xl[v], xr[v] = c_ - a_, c_ + a_
    xl = ndi.gaussian_filter1d(xl, 2.0)
    xr = ndi.gaussian_filter1d(xr, 2.0)
    a = np.maximum((xr - xl) / 2.0, 1.0)
    xc = (xl + xr) / 2.0
    tmax = float(max(kd_lathe * a[lathe_top:clip].max(), 1.0)) + 4
    # inflation depth for the thick wood
    dt = ndi.distance_transform_edt(thick)
    R = geom._local_radius(dt)
    h = kd_infl * np.sqrt(np.clip(dt * (2 * R - dt), 0, None))
    h = ndi.gaussian_filter(h, 1.0) * thick
    tmax = max(tmax, float(h.max()) + 4)
    ts = np.arange(-tmax, tmax + voxel, voxel)
    Y, X = np.meshgrid(ys, xs, indexing="ij")
    yi = np.clip(np.round(Y).astype(int), 0, H + 199)
    # lathe field (rows >= lathe_top)
    A = a[yi]
    XC = xc[yi]
    # depth semi-axis capped at the trunk's own depth: the painted root spread widens left-right only, so the base
    # does not become a wide flat platform when seen from above
    a_ref = float(np.median(a[lathe_top:lathe_top + 40]))
    Bd = np.minimum(kd_lathe * A, 1.2 * kd_lathe * a_ref + 0.25 * (A - a_ref).clip(0))
    f_l = A[..., None] * (1.0 - np.sqrt(((X - XC) / A)[..., None] ** 2 + (ts[None, None, :] / Bd[..., None]) ** 2))
    # above lathe_top: conical cap (radius shrinks 1.2 px per px) -> smooth merge into the inflated trunk
    f_l = f_l - np.clip(lathe_top - Y, 0, None)[..., None] * 1.2
    # inflated thick wood (rows < clip)
    yc = np.clip(np.round(Y).astype(int), 0, H - 1)
    xcix = np.clip(np.round(X).astype(int), 0, W - 1)
    hh = h[yc, xcix]
    inside = thick[yc, xcix] & (Y < clip)
    f_i = np.where(inside[..., None], hh[..., None] - np.abs(ts[None, None, :]), -50.0)
    f = np.maximum(f_l, f_i)
    # carve the tunnel through all depths
    tun = tunnel[yc, xcix] if tunnel is not None else np.zeros_like(inside)
    tun_ext = np.zeros_like(tun)
    if tunnel is not None:
        tb = np.zeros((H + 200, W), bool)
        tb[:H] = tunnel
        tb[H:] = False
        tun_ext = tb[np.clip(np.round(Y).astype(int), 0, H + 199), xcix]
    d_tun = ndi.distance_transform_edt(~tun_ext) * voxel
    f = np.minimum(f, (d_tun - 1.5 * voxel)[..., None])
    if smooth:
        f = ndi.gaussian_filter(f, smooth)
    f = np.pad(f, 1, constant_values=-50.0)
    verts, faces, _, _ = measure.marching_cubes(f, level=0.0)
    verts -= 1.0
    vy = np.interp(verts[:, 0], np.arange(len(ys)), ys)
    vx = np.interp(verts[:, 1], np.arange(len(xs)), xs)
    vt = np.interp(verts[:, 2], np.arange(len(ts)), ts)
    P = geom.pix_to_world(ref.view, vx, vy, vt / ref.ppm)
    return P, faces[:, ::-1]
