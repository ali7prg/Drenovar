"""Multi-view projection texturing from orthographic reference views + procedural detail.

Workflow
--------
    verts, tris, uv, vn = core.mesh_arrays(obj)            # world space, triangulated
    T = rasterize_uv(verts, tris, uv, 2048, vn)             # texel -> position/normal
    zbs = {v.name: zbuffer(verts, tris, v) for v in views}
    col, w = project(T, views, zbs)                        # colour from references
    col = fill(col, w > 0)                                 # pull-push hole filling
    core.save_rgba(path, col)

Texture convention: row 0 = top of the PNG; Blender UV v=1 is the top row.
"""
import cv2
import numpy as np
from scipy import ndimage as ndi


# --------------------------------------------------------------------------- UV rasterisation

class Texels:
    def __init__(self, pos, nrm, tri, bary, valid, size):
        self.pos, self.nrm, self.tri, self.bary, self.valid, self.size = pos, nrm, tri, bary, valid, size


def rasterize_uv(verts, tris, uv, size, vnormals=None, flat_normals=False):
    """Rasterise mesh UVs: per-texel world position, interpolated normal, triangle id, barycentrics."""
    W, H = (size, size) if isinstance(size, int) else size
    px = np.empty_like(uv)
    px[..., 0] = uv[..., 0] * W - 0.5
    px[..., 1] = (1.0 - uv[..., 1]) * H - 0.5
    ids = np.full((H, W), -1, dtype=np.int32)
    shift = 4
    pts = np.round(px * (1 << shift)).astype(np.int32)
    for t in range(len(tris)):
        cv2.fillConvexPoly(ids, pts[t], int(t), lineType=cv2.LINE_8, shift=shift)
    valid = ids >= 0
    yy, xx = np.nonzero(valid)
    t = ids[yy, xx]
    a, b, c = px[t, 0], px[t, 1], px[t, 2]
    p = np.stack([xx, yy], 1).astype(np.float64)
    v0, v1, v2 = b - a, c - a, p - a
    d00 = (v0 * v0).sum(1)
    d01 = (v0 * v1).sum(1)
    d11 = (v1 * v1).sum(1)
    d20 = (v2 * v0).sum(1)
    d21 = (v2 * v1).sum(1)
    den = d00 * d11 - d01 * d01
    den = np.where(np.abs(den) < 1e-12, 1e-12, den)
    bv = (d11 * d20 - d01 * d21) / den
    bw = (d00 * d21 - d01 * d20) / den
    bu = 1.0 - bv - bw
    bary = np.clip(np.stack([bu, bv, bw], 1), 0.0, 1.0)
    bary /= np.maximum(bary.sum(1, keepdims=True), 1e-9)
    tv = tris[t]
    P = (verts[tv] * bary[..., None]).sum(1)
    if vnormals is None or flat_normals:
        e1 = verts[tris[:, 1]] - verts[tris[:, 0]]
        e2 = verts[tris[:, 2]] - verts[tris[:, 0]]
        fn = np.cross(e1, e2)
        fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
        N = fn[t]
    else:
        N = (vnormals[tv] * bary[..., None]).sum(1)
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
    pos = np.zeros((H, W, 3))
    nrm = np.zeros((H, W, 3))
    pos[yy, xx] = P
    nrm[yy, xx] = N
    baryimg = np.zeros((H, W, 3))
    baryimg[yy, xx] = bary
    return Texels(pos, nrm, ids, baryimg, valid, (W, H))


# --------------------------------------------------------------------------- view z-buffer

def zbuffer(verts, tris, view, pad=1):
    """Nearest depth (along view.d) per reference-crop pixel; inf where the mesh is absent."""
    W, H = view.size
    u, v, dep = view.project(verts)
    zb = np.full((H, W), np.inf)
    U = u[tris]
    V = v[tris]
    D = dep[tris]
    x0 = np.clip(np.floor(U.min(1)).astype(int), 0, W)
    x1 = np.clip(np.ceil(U.max(1)).astype(int) + 1, 0, W)
    y0 = np.clip(np.floor(V.min(1)).astype(int), 0, H)
    y1 = np.clip(np.ceil(V.max(1)).astype(int) + 1, 0, H)
    for t in np.nonzero((x1 > x0) & (y1 > y0))[0]:
        xs = np.arange(x0[t], x1[t])
        ys = np.arange(y0[t], y1[t])
        X, Y = np.meshgrid(xs, ys)
        ax_, bx_, cx_ = U[t]
        ay_, by_, cy_ = V[t]
        den = (by_ - cy_) * (ax_ - cx_) + (cx_ - bx_) * (ay_ - cy_)
        if abs(den) < 1e-12:
            continue
        l1 = ((by_ - cy_) * (X - cx_) + (cx_ - bx_) * (Y - cy_)) / den
        l2 = ((cy_ - ay_) * (X - cx_) + (ax_ - cx_) * (Y - cy_)) / den
        l3 = 1 - l1 - l2
        inside = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)
        if not inside.any():
            continue
        z = l1 * D[t, 0] + l2 * D[t, 1] + l3 * D[t, 2]
        sub = zb[y0[t]:y1[t], x0[t]:x1[t]]
        np.minimum(sub, np.where(inside, z, np.inf), out=sub)
    if pad:
        zb = ndi.minimum_filter(zb, size=2 * pad + 1)
    return zb


# --------------------------------------------------------------------------- projection

def _bilinear(img, u, v):
    n = len(u)
    cols = 4096
    rows = max(1, -(-n // cols))
    mx = np.zeros(rows * cols, np.float32)
    my = np.zeros(rows * cols, np.float32)
    mx[:n] = u
    my[:n] = v
    out = cv2.remap(img.astype(np.float32), mx.reshape(rows, cols), my.reshape(rows, cols),
                    interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return out.reshape(rows * cols, -1)[:n]


def project(T, views, zbufs, power=3.0, depth_eps=0.03, min_facing=0.08, mask_erode=1,
            per_view_out=False):
    """Blend reference colours onto texels. Returns (colour (H,W,3), weight (H,W))."""
    W, H = T.size
    acc = np.zeros((H, W, 3))
    wsum = np.zeros((H, W))
    yy, xx = np.nonzero(T.valid)
    P = T.pos[yy, xx]
    N = T.nrm[yy, xx]
    per_view = {}
    for view in views:
        vw, vh = view.size
        u, v, dep = view.project(P)
        ui = np.round(u).astype(int)
        vi = np.round(v).astype(int)
        ok = (ui >= 0) & (ui < vw) & (vi >= 0) & (vi < vh)
        zb = zbufs[view.name]
        zval = np.full(len(u), -np.inf)
        zval[ok] = zb[vi[ok], ui[ok]]
        vis = ok & (dep <= zval + depth_eps)
        m = view.mask if not mask_erode else ndi.binary_erosion(view.mask, iterations=mask_erode)
        inmask = np.zeros(len(u), bool)
        inmask[ok] = m[vi[ok], ui[ok]]
        facing = np.clip(N @ (-view.d), 0.0, 1.0)
        w = np.where(vis & inmask & (facing > min_facing), (facing ** power) * view.weight, 0.0)
        col = _bilinear(view.image, u, v)[:, :3]
        acc[yy, xx] += w[:, None] * col
        wsum[yy, xx] += w
        if per_view_out:
            pv = np.zeros((H, W))
            pv[yy, xx] = w
            per_view[view.name] = pv
    out = acc / np.maximum(wsum, 1e-9)[..., None]
    if per_view_out:
        return out, wsum, per_view
    return out, wsum


# --------------------------------------------------------------------------- filling

def fill(img, known, levels=None):
    """Pull-push hole filling of img where known==False (keeps known texels unchanged)."""
    img = np.asarray(img, np.float64)
    C = img.shape[2] if img.ndim == 3 else 1
    a = img.reshape(img.shape[0], img.shape[1], C) * known[..., None]
    w = known.astype(np.float64)
    pyr = [(a, w)]
    while min(a.shape[:2]) > 1 and (levels is None or len(pyr) <= levels):
        h2, w2 = (a.shape[0] + 1) // 2, (a.shape[1] + 1) // 2
        a2 = cv2.resize(a, (w2, h2), interpolation=cv2.INTER_AREA).reshape(h2, w2, C)
        ww = cv2.resize(w, (w2, h2), interpolation=cv2.INTER_AREA)
        pyr.append((a2, ww))
        a, w = a2, ww
    a, w = pyr[-1]
    filled = a / np.maximum(w, 1e-9)[..., None]
    for a_l, w_l in reversed(pyr[:-1]):
        up = cv2.resize(filled, (a_l.shape[1], a_l.shape[0]), interpolation=cv2.INTER_LINEAR)
        up = up.reshape(a_l.shape[0], a_l.shape[1], C)
        mine = a_l / np.maximum(w_l, 1e-9)[..., None]
        t = np.clip(w_l, 0, 1)[..., None]
        filled = mine * t + up * (1 - t)
    out = np.where(known[..., None], img.reshape(filled.shape), filled)
    return out if img.ndim == 3 else out[..., 0]


def dilate_margin(img, valid, px=8):
    """Extend texel colours px pixels outside UV islands (prevents mip bleeding)."""
    ring = ndi.binary_dilation(valid, iterations=px) & ~valid
    filled = fill(img, valid)
    out = img.copy()
    out[ring] = filled[ring]
    return out


# --------------------------------------------------------------------------- de-lighting

def delight(col, T, light_dir=(-0.45, -0.35, 0.82), ambient=0.5, strength=0.55, mask=None):
    """Remove part of the painted key-light: col / shade^strength, mean brightness preserved."""
    L = np.asarray(light_dir, float)
    L /= np.linalg.norm(L)
    shade = ambient + (1 - ambient) * np.clip(T.nrm @ L, 0, 1)
    shade = np.where(T.valid, shade, 1.0)
    out = col / np.maximum(shade, 0.2)[..., None] ** strength
    m = T.valid if mask is None else mask
    if m.any():
        out *= (col[m].mean() / max(out[m].mean(), 1e-6))
    return np.clip(out, 0, 1)


# --------------------------------------------------------------------------- procedural detail

def _hash3(ix, iy, iz, seed=0):
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    return (h & 0xFFFFFF).astype(np.float64) / float(0xFFFFFF)


def value_noise(P, freq=1.0, seed=0):
    Q = np.asarray(P, float) * freq
    i = np.floor(Q).astype(np.int64)
    f = Q - i
    s = f * f * (3 - 2 * f)
    out = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (s[..., 0] if dx else 1 - s[..., 0]) * (s[..., 1] if dy else 1 - s[..., 1]) * \
                    (s[..., 2] if dz else 1 - s[..., 2])
                out = out + w * _hash3(i[..., 0] + dx, i[..., 1] + dy, i[..., 2] + dz, seed)
    return out


def fbm(P, freq=1.0, octaves=5, lacunarity=2.0, gain=0.5, seed=0):
    amp, total, norm = 1.0, 0.0, 0.0
    for o in range(octaves):
        total = total + amp * value_noise(P, freq * lacunarity ** o, seed + o * 17)
        norm += amp
        amp *= gain
    return total / norm


def voronoi(P, freq=1.0, seed=0, jitter=0.9):
    """Returns (F1, F2) distances to the nearest feature points (cell size 1/freq)."""
    Q = np.asarray(P, float) * freq
    i = np.floor(Q).astype(np.int64)
    f1 = np.full(Q.shape[:-1], 9.0)
    f2 = np.full(Q.shape[:-1], 9.0)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = i + np.array([dx, dy, dz])
                fp = c + 0.5 + jitter * (np.stack([_hash3(c[..., 0], c[..., 1], c[..., 2], seed + k)
                                                   for k in range(3)], -1) - 0.5)
                d = np.linalg.norm(Q - fp, axis=-1)
                f2 = np.where(d < f1, f1, np.minimum(f2, d))
                f1 = np.minimum(f1, d)
    return f1 / freq, f2 / freq


def texel_field(T, fn, fill_value=0.0):
    """Evaluate fn(positions (n,3), normals (n,3)) on valid texels -> (H,W) image."""
    W, H = T.size
    out = np.full((H, W), fill_value, dtype=np.float64)
    yy, xx = np.nonzero(T.valid)
    out[yy, xx] = fn(T.pos[yy, xx], T.nrm[yy, xx])
    return out


def height_to_normal(height, valid, strength=2.0, texel_m=None):
    """Tangent-space normal map (RGB 0..1, OpenGL +Y) from a UV-space height map."""
    h = fill(height[..., None], valid)[..., 0]
    gx = cv2.Sobel(h, cv2.CV_64F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(h, cv2.CV_64F, 0, 1, ksize=3) / 8.0
    scale = strength if texel_m is None else strength / texel_m
    n = np.stack([-gx * scale, gy * scale, np.ones_like(h)], -1)  # image y down -> +V up
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def ao_from_height(height, radius=6, strength=0.6):
    blur = ndi.gaussian_filter(height, radius)
    cav = np.clip((blur - height) * strength * 10, 0, 1)
    return 1.0 - cav
