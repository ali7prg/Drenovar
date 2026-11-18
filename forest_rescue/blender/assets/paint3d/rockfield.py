"""SDF fractured limestone mound (no bpy): ellipsoidal mound following the painted front-view height profile,
fractured by Voronoi cells (seeds at the painted block centres, spread through the depth), crack gap, rounded
edges (blurred SDF), rough faces (noise), marching cubes."""
import numpy as np
from scipy import ndimage as ndi
from skimage import measure

from frlib import texproj


def noise3(P, freq, seed, octaves=3):
    return texproj.fbm(P, freq=freq, octaves=octaves, seed=seed) * 2 - 1


def mound_sdf(G, prof_x, prof_h, W, depth_frac=0.7, back_fall=1.0, seed=1, lf_amp=0.08):
    """G: (...,3) grid points. Height profile h(x) along x (front-view silhouette), plan half-depth
    0.5*depth_frac*W*sqrt(1-(2x/W)^2); cross-section in y: z <= h(x)*sqrt(1-(y/Y(x))^2)^back_fall."""
    x, y, z = G[..., 0], G[..., 1], G[..., 2]
    h = np.interp(x, prof_x, prof_h, left=0.0, right=0.0)
    Y = 0.5 * depth_frac * W * np.sqrt(np.clip(1 - (2 * x / W) ** 2, 0.02, None))
    q = np.clip(1 - (y / np.maximum(Y, 1e-3)) ** 2, 0, None)
    lf = 1 + lf_amp * noise3(G * np.array([1, 1, 0.5]), 0.35, seed)
    top = h * q ** (0.5 * back_fall) * lf
    f = np.maximum(z - top, -(z + 0.25))
    f = np.maximum(f, np.abs(y) - Y)
    return f


def voronoi_crack(G, seeds):
    """Signed distance (<= 0) of each point to the boundary of its own Voronoi cell, and the cell index."""
    S = np.asarray(seeds, float)
    P = G.reshape(-1, 3)
    d2 = ((P[:, None, :] - S[None, :, :]) ** 2).sum(-1)
    own = np.argmin(d2, axis=1)
    best = np.full(len(P), -1e9)
    for j in range(len(S)):
        sj = S[j]
        si = S[own]
        n = sj[None, :] - si
        ln = np.linalg.norm(n, axis=1)
        valid = ln > 1e-6
        m = 0.5 * (si + sj[None, :])
        d = np.where(valid, ((P - m) * n).sum(1) / np.maximum(ln, 1e-6), -1e9)
        best = np.maximum(best, d)
    return best.reshape(G.shape[:-1]), own.reshape(G.shape[:-1])


def fractured_mound(prof_x, prof_h, W, seeds, depth_frac=0.7, voxel=0.07, gap=0.06, round_m=0.05, rough=0.025,
                    seed=3, back_fall=1.0):
    pad = 0.4
    Hmax = float(np.max(prof_h)) * 1.15 + pad
    Ymax = 0.5 * depth_frac * W + pad
    xs = np.arange(-W / 2 - pad, W / 2 + pad, voxel)
    ys = np.arange(-Ymax, Ymax, voxel)
    zs = np.arange(-0.35, Hmax, voxel)
    G = np.stack(np.meshgrid(xs, ys, zs, indexing="ij"), -1)
    f = mound_sdf(G, prof_x, prof_h, W, depth_frac, back_fall=back_fall, seed=seed)
    c, own = voronoi_crack(G, seeds)
    F = np.maximum(f, c + gap / 2)
    F = F + rough * noise3(G, 2.2, seed + 7, octaves=2)
    F = ndi.gaussian_filter(F, max(0.5, round_m / voxel))
    Fp = np.pad(F, 1, constant_values=1.0)
    verts, faces, normals, _ = measure.marching_cubes(Fp, level=0.0, spacing=(voxel, voxel, voxel))
    verts = verts - voxel + np.array([xs[0], ys[0], zs[0]])
    faces = faces.copy()
    # outward orientation: positive signed volume
    a, b, c_ = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    vol = np.einsum("ij,ij->i", a, np.cross(b, c_)).sum() / 6.0
    if vol < 0:
        faces = faces[:, ::-1]
    # per-vertex crack proximity (for AO) and cell id
    vi = np.clip(np.round((verts - np.array([xs[0], ys[0], zs[0]])) / voxel).astype(int), 0,
                 np.array(G.shape[:3]) - 1)
    crack = c[vi[:, 0], vi[:, 1], vi[:, 2]]
    cell = own[vi[:, 0], vi[:, 1], vi[:, 2]]
    return verts, faces, crack, cell


def drop_thin(verts, faces, min_dim=0.2):
    """Remove connected components whose smallest PCA extent is < min_dim (chips/flakes). Returns faces, report."""
    import scipy.sparse as sp
    n = len(verts)
    A = sp.coo_matrix((np.ones(len(faces) * 3), (np.repeat(faces[:, 0], 3), faces.ravel())), shape=(n, n))
    ncomp, lab = sp.csgraph.connected_components(A + A.T, directed=False)
    keep_v = np.zeros(n, bool)
    dims = []
    for k in range(ncomp):
        idx = np.nonzero(lab == k)[0]
        if len(idx) < 4:
            continue
        P = verts[idx] - verts[idx].mean(0)
        s = np.linalg.svd(P, compute_uv=False)
        ext = 2 * s / np.sqrt(len(idx)) * 1.7
        dims.append(float(ext.min()))
        if ext.min() >= min_dim:
            keep_v[idx] = True
    kf = keep_v[faces].all(1)
    return faces[kf], dict(components=int(ncomp), kept=int(sum(1 for d in dims if d >= min_dim)),
                           min_dim_kept=round(min([d for d in dims if d >= min_dim] or [0]), 3))
