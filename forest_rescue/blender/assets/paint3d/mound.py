"""Fractured limestone mound (no bpy): the outcrop silhouette is inflated into a MOUND (plan ~ ellipse of depth
0.6-0.8 x width, highest in the middle), then fractured into facets: every vertex belongs to the painted block whose
crack-bounded region contains its frontal projection (cracks continue straight to the back), each block's vertices
are clustered by normal (front / top / sides / back) and snapped onto the least-squares plane of their cluster,
with a small inward push along the cracks. Per-face isometric UV unwrap (stretch ratio 1) for sides and tops."""
import numpy as np
from scipy import ndimage as ndi

import geom


def mound_depth(mask, depth_frac=0.7, dt_k=1.3, top_round=0.6):
    """Half-depth image (px) of a mound: plan ellipse (depth_frac x width) x vertical dome, capped by k * DT."""
    ys, xs = np.nonzero(mask)
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
    W = x1 - x0 + 1
    Hh = y1 - y0 + 1
    uc = 0.5 * (x0 + x1)
    yy, xx = np.mgrid[0:mask.shape[0], 0:mask.shape[1]]
    plan = 0.5 * depth_frac * W * np.sqrt(np.clip(1 - ((xx - uc) / (0.5 * W)) ** 2, 0, None))
    # dome: depth shrinks toward the top of the silhouette (top facets slope back)
    zf = np.clip((y1 - yy) / max(Hh, 1), 0, 1)
    dome = np.sqrt(np.clip(1 - (top_round * zf) ** 2, 0, None))
    dt = ndi.distance_transform_edt(mask)
    h = np.minimum(plan * dome, dt_k * dt + 2.0) * mask
    return ndi.gaussian_filter(h, 1.5) * mask


def facet(V, F, view, block_lbl, W, H, n_clusters=5, crack_push=0.05, rng=None):
    """Snap vertices onto per-block planes (clusters of vertex normals); returns new V."""
    rng = rng or np.random.default_rng(0)
    vn = geom.vertex_normals(V, F)
    u, v, _ = view.project(V)
    ui = np.clip(np.round(u).astype(int), 0, W - 1)
    vi = np.clip(np.round(v).astype(int), 0, H - 1)
    lab = block_lbl[vi, ui]
    # vertices outside every block region: nearest block label
    if (lab == 0).any():
        dist, (iy, ix) = ndi.distance_transform_edt(block_lbl == 0, return_indices=True)
        lab = np.where(lab == 0, block_lbl[iy[vi, ui], ix[vi, ui]], lab)
    out = V.copy()
    dirs = np.array([[0, -1.0, 0.25], [0, 0, 1.0], [-1.0, 0, 0.2], [1.0, 0, 0.2], [0, 1.0, 0.2]])
    dirs = geom.nrm(dirs)
    for b in np.unique(lab):
        idx = np.nonzero(lab == b)[0]
        if len(idx) < 8:
            continue
        # per-block random tilt of the canonical facet directions (natural fracture)
        D = geom.nrm(dirs + rng.normal(0, 0.12, dirs.shape))
        cl = np.argmax(vn[idx] @ D.T, axis=1)
        for k in range(len(D)):
            sel = idx[cl == k]
            if len(sel) < 4:
                continue
            P = V[sel]
            c = P.mean(0)
            n = geom.nrm(D[k] * 0.6 + geom.nrm(vn[sel].mean(0)) * 0.4)
            d = (P - c) @ n
            out[sel] = P - d[:, None] * n[None, :] * 0.92
    # crack push: vertices whose 1-ring touches another block are pushed inward a little
    nb_other = np.zeros(len(V), bool)
    for a, b in ((0, 1), (1, 2), (2, 0)):
        diff = lab[F[:, a]] != lab[F[:, b]]
        nb_other[F[diff, a]] = True
        nb_other[F[diff, b]] = True
    out[nb_other] -= vn[nb_other] * crack_push
    return out, lab


def isometric_uvs(Vc, region, period_m, up=np.array([0, 0, 1.0])):
    """Per-face isometric unwrap (stretch 1): face-plane basis (texture up = world up projected), metric size /
    period_m, each face placed fully inside the region. Vc (M,3,3) -> UV (M,3,2)."""
    u0, v0, u1, v1 = region
    e = Vc[:, 1] - Vc[:, 0]
    n = geom.nrm(np.cross(Vc[:, 1] - Vc[:, 0], Vc[:, 2] - Vc[:, 0]))
    upp = up[None, :] - (n @ up)[:, None] * n
    horiz = np.linalg.norm(upp, axis=1) < 0.3
    upp[horiz] = geom.nrm(e[horiz])
    e2 = geom.nrm(upp)
    e1 = geom.nrm(np.cross(e2, n))
    rel = Vc - Vc[:, :1]
    a = np.einsum("mkj,mj->mk", rel, e1) / period_m
    b = np.einsum("mkj,mj->mk", rel, e2) / period_m * (u1 - u0) / max(v1 - v0, 1e-6)
    out = np.zeros(Vc.shape[:2] + (2,))
    for i, comp in enumerate((a, b)):
        lo = comp.min(1, keepdims=True)
        span = np.clip(comp.max(1, keepdims=True) - lo, 0, 1)
        off = np.mod(Vc[:, :1, i] * 0.37 + 0.11, 1.0) * (1 - span)
        out[..., i] = np.clip(comp - lo + off, 0, 1)
    out[..., 0] = u0 + (u1 - u0) * out[..., 0]
    out[..., 1] = v0 + (v1 - v0) * out[..., 1]
    return out


def stretch_ratio(Vc, UVc, region_wh_px):
    """Max ratio of the singular values of the UV->3D map per face (1 = isometric)."""
    P = Vc[:, 1:] - Vc[:, :1]
    Q = (UVc[:, 1:] - UVc[:, :1]) * np.asarray(region_wh_px)[None, None, :]
    out = []
    for p, q in zip(P, Q):
        try:
            J = p.T @ np.linalg.pinv(q.T)          # 3x2
            s = np.linalg.svd(J, compute_uv=False)
            if s[-1] > 1e-9:
                out.append(s[0] / s[-1])
        except np.linalg.LinAlgError:
            pass
    return float(np.max(out)) if out else 1.0, float(np.median(out)) if out else 1.0
