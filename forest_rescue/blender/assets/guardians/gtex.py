"""Guardian texturing: multi-view projection with posed meshes, mirror + 3-D fill, procedural
fur-strand normal map, roughness, region overrides (claws, horns, eyes, mouth...)."""
import math

import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

from frlib import texproj


def project_posed(views_posed, tris, uv, size, mirror_x=True, min_w=0.02, k_fill=8,
                  facing_power=2.5, bind_verts=None, bind_normals=None, filt=None):
    """views_posed: list of (view, verts_posed (N,3), normals_posed (N,3)) for the same mesh.

    Returns colour (H,W,3), weight (H,W), Texels in bind pose (positions for fill/mirroring).
    """
    acc = None
    wsum = None
    T_bind = texproj.rasterize_uv(bind_verts, tris, uv, size, bind_normals)
    for view, vp, nrm in views_posed:
        T = texproj.rasterize_uv(vp, tris, uv, size, nrm)
        zb = texproj.zbuffer(vp, tris, view)
        col, w = texproj.project(T, [view], {view.name: zb}, power=facing_power, depth_eps=0.035,
                                 min_facing=0.12, mask_erode=2)
        if filt is not None:
            w = w * filt(view.name, T_bind)
        if acc is None:
            acc = col * w[..., None]
            wsum = w.copy()
        else:
            acc += col * w[..., None]
            wsum += w
    col = acc / np.maximum(wsum, 1e-9)[..., None]
    valid = T_bind.valid
    known = valid & (wsum > min_w)
    yy, xx = np.nonzero(valid)
    P = T_bind.pos[yy, xx]
    kmask = known[yy, xx]
    out = col.copy()
    if mirror_x and kmask.any():
        # symmetric creature: unknown texels take the colour of their mirror image
        tree = cKDTree(P[kmask])
        src_cols = col[yy[kmask], xx[kmask]]
        need = ~kmask
        Pm = P[need].copy()
        Pm[:, 0] *= -1
        d, i = tree.query(Pm, k=4)
        wts = 1.0 / np.maximum(d, 0.004)
        good = d[:, 0] < 0.03
        c = (src_cols[i] * wts[..., None]).sum(1) / wts.sum(1)[:, None]
        ny, nx = yy[need][good], xx[need][good]
        out[ny, nx] = c[good]
        kmask2 = kmask.copy()
        kmask2[np.nonzero(need)[0][good]] = True
        kmask = kmask2
    # 3-D nearest-neighbour fill for the rest (inside of legs, belly, mouth ...)
    if (~kmask).any() and kmask.any():
        tree = cKDTree(P[kmask])
        src = out[yy[kmask], xx[kmask]]
        d, i = tree.query(P[~kmask], k=k_fill)
        wts = 1.0 / np.maximum(d, 0.005) ** 2
        c = (src[i] * wts[..., None]).sum(1) / wts.sum(1)[:, None]
        out[yy[~kmask], xx[~kmask]] = c
    return out, wsum, T_bind


def strand_height(P, Dfur, scale=1.0, seed=3):
    """Fur strand height field at points P with flow directions Dfur (both (n,3))."""
    D = Dfur / np.maximum(np.linalg.norm(Dfur, axis=1, keepdims=True), 1e-9)
    along = (P * D).sum(1, keepdims=True)
    Q = P - 0.86 * along * D            # compress along the flow -> streaks
    fine = texproj.fbm(Q, freq=95.0 * scale, octaves=3, seed=seed)
    mid = texproj.fbm(Q, freq=34.0 * scale, octaves=2, seed=seed + 7)
    f1, f2 = texproj.voronoi(P - 0.6 * along * D, freq=11.0 * scale, seed=seed + 11)
    clump = np.clip((f2 - f1) * 9.0, 0, 1)
    return 0.45 * fine + 0.30 * mid + 0.25 * clump


def dilate_islands(img, valid, px=6):
    return texproj.dilate_margin(img, valid, px)


def tangent_normal_from_height(height, valid, strength):
    return texproj.height_to_normal(height, valid, strength=strength)


def blend_normals(n1, n2):
    """Reoriented normal mapping of two tangent-space maps (0..1 encoded)."""
    t = n1 * np.array([2, 2, 2]) + np.array([-1, -1, 0])
    u = n2 * np.array([-2, -2, 2]) + np.array([1, 1, -1])
    r = t * (t * u).sum(-1, keepdims=True) / np.maximum(t[..., 2:3], 1e-6) - u
    r /= np.maximum(np.linalg.norm(r, axis=-1, keepdims=True), 1e-9)
    return r * 0.5 + 0.5
