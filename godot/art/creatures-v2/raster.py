"""UV-space rasteriser: which triangle covers each texel and where (barycentrics).

Texel (row r, column c) has glTF UV ((c+0.5)/W, (r+0.5)/H) (origin top-left).
Attributes interpolated with these barycentrics reproduce what the renderer
interpolates, so baked maps line up with the exported vertices and tangents.
"""
import numpy as np


def rasterize(uv, idx, size, conservative=0.6):
    """uv: (V,2) glTF UVs; idx: (T,3). Returns tri (H,W) int32 (-1 empty) and bary (H,W,3)."""
    H = W = size
    tri = np.full((H, W), -1, np.int32)
    bary = np.zeros((H, W, 3), np.float32)
    best = np.full((H, W), -np.inf, np.float32)  # largest min-barycentric wins on overlaps
    P = uv * np.array([W, H], np.float32)
    A, B, C = P[idx[:, 0]], P[idx[:, 1]], P[idx[:, 2]]
    lo = np.floor(np.minimum(np.minimum(A, B), C) - conservative).astype(int)
    hi = np.ceil(np.maximum(np.maximum(A, B), C) + conservative).astype(int)
    lo = np.clip(lo, 0, [W - 1, H - 1])
    hi = np.clip(hi, 0, [W - 1, H - 1])
    area = (B[:, 0] - A[:, 0]) * (C[:, 1] - A[:, 1]) - (C[:, 0] - A[:, 0]) * (B[:, 1] - A[:, 1])
    for t in range(len(idx)):
        if abs(area[t]) < 1e-12:
            continue
        x0, y0 = lo[t]
        x1, y1 = hi[t]
        xs = np.arange(x0, x1 + 1, dtype=np.float32) + 0.5
        ys = np.arange(y0, y1 + 1, dtype=np.float32) + 0.5
        X, Y = np.meshgrid(xs, ys)
        a, b, c = A[t], B[t], C[t]
        w0 = ((b[0] - X) * (c[1] - Y) - (c[0] - X) * (b[1] - Y)) / area[t]
        w1 = ((c[0] - X) * (a[1] - Y) - (a[0] - X) * (c[1] - Y)) / area[t]
        w2 = 1.0 - w0 - w1
        m = np.minimum(np.minimum(w0, w1), w2)
        # conservative edge: accept texels within ~conservative px of the triangle
        edge = conservative / max(np.sqrt(abs(area[t])), 1.0)
        sel = m > -edge
        if not sel.any():
            continue
        sub_best = best[y0:y1 + 1, x0:x1 + 1]
        take = sel & (m > sub_best)
        if not take.any():
            continue
        sub_best[take] = m[take]
        tri[y0:y1 + 1, x0:x1 + 1][take] = t
        wb = np.stack([w0, w1, w2], -1)
        wb = np.clip(wb, 0.0, 1.0)
        wb /= np.maximum(wb.sum(-1, keepdims=True), 1e-9)
        bary[y0:y1 + 1, x0:x1 + 1][take] = wb[take]
    return tri, bary


def interpolate(attr, idx, tri, bary):
    """attr (V, k) at texels -> (H, W, k); empty texels get zeros."""
    H, W = tri.shape
    out = np.zeros((H, W, attr.shape[1]), np.float32)
    m = tri >= 0
    t = tri[m]
    b = bary[m]
    out[m] = (attr[idx[t, 0]] * b[:, 0:1] + attr[idx[t, 1]] * b[:, 1:2] + attr[idx[t, 2]] * b[:, 2:3])
    return out


def dilate(img, mask, px=8):
    """Edge padding: grows covered texels into empty ones (keeps mip/bilinear seams clean)."""
    img = img.copy()
    m = mask.copy()
    for _ in range(px):
        if m.all():
            break
        acc = np.zeros_like(img)
        cnt = np.zeros(m.shape, np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                sm = np.roll(np.roll(m, dy, 0), dx, 1)
                si = np.roll(np.roll(img, dy, 0), dx, 1)
                acc += si * sm[..., None]
                cnt += sm
        grow = (~m) & (cnt > 0)
        img[grow] = acc[grow] / cnt[grow][:, None]
        m = m | grow
    # whatever is still empty gets the mean colour
    if not m.all():
        img[~m] = img[m].mean(0)
    return img
