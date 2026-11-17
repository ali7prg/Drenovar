"""Signed distance sculpting: primitives, smooth blending, grid evaluation.

A creature part is an ordered list of primitives. Each primitive carries the
bone that owns it (used for skin weights), a blend radius `k` (polynomial smooth
minimum with everything before it) and a surface material id. Negative
primitives carve (smooth maximum).
"""
import numpy as np

F = np.float32


def _v(x):
    return np.asarray(x, dtype=F)


def rot_x(a):
    c, s = np.cos(a), np.sin(a)
    return _v([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(a):
    c, s = np.cos(a), np.sin(a)
    return _v([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(a):
    c, s = np.cos(a), np.sin(a)
    return _v([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


class Prim:
    """One primitive. kinds: sphere, ellipsoid, capsule, cone (round cone), box."""

    def __init__(self, kind, bone, k=0.04, mat="base", name="", neg=False, **p):
        self.kind, self.bone, self.k, self.mat, self.name, self.neg = kind, bone, float(k), mat, name, neg
        self.p = {key: (_v(v) if isinstance(v, (list, tuple, np.ndarray)) else v) for key, v in p.items()}
        self.bounds = self._bounds()

    def _bounds(self):
        p = self.p
        if self.kind == "sphere":
            r = p["r"]
            return p["c"] - r, p["c"] + r
        if self.kind == "ellipsoid":
            r = float(np.max(p["r"]))
            return p["c"] - r, p["c"] + r
        if self.kind == "capsule":
            r = p["r"]
            return np.minimum(p["a"], p["b"]) - r, np.maximum(p["a"], p["b"]) + r
        if self.kind == "cone":
            r = max(p["ra"], p["rb"])
            return np.minimum(p["a"], p["b"]) - r, np.maximum(p["a"], p["b"]) + r
        if self.kind == "box":
            r = float(np.linalg.norm(p["h"])) + p.get("round", 0.0)
            return p["c"] - r, p["c"] + r
        raise ValueError(self.kind)

    def dist(self, P):
        p = self.p
        k = self.kind
        if k == "sphere":
            return np.linalg.norm(P - p["c"], axis=1) - p["r"]
        if k == "ellipsoid":
            q = P - p["c"]
            if "R" in p:
                q = q @ p["R"]  # into local frame (R columns = local axes)
            r = p["r"]
            k0 = np.linalg.norm(q / r, axis=1)
            k1 = np.linalg.norm(q / (r * r), axis=1)
            return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)
        if k == "capsule":
            a, b, r = p["a"], p["b"], p["r"]
            pa, ba = P - a, b - a
            h = np.clip((pa @ ba) / float(ba @ ba), 0.0, 1.0)
            return np.linalg.norm(pa - h[:, None] * ba, axis=1) - r
        if k == "cone":
            a, b, r1, r2 = p["a"], p["b"], p["ra"], p["rb"]
            ba = b - a
            l2 = float(ba @ ba)
            rr = r1 - r2
            a2 = l2 - rr * rr
            il2 = 1.0 / l2
            pa = P - a
            y = pa @ ba
            z = y - l2
            xv = pa * l2 - y[:, None] * ba
            x2 = np.sum(xv * xv, axis=1)
            y2 = y * y * l2
            z2 = z * z * l2
            kk = np.sign(rr) * rr * rr * x2
            out = (np.sqrt(x2 * a2 * il2) + y * rr) * il2 - r1
            m1 = np.sign(z) * a2 * z2 > kk
            out = np.where(m1, np.sqrt(x2 + z2) * il2 - r2, out)
            m2 = np.sign(y) * a2 * y2 < kk
            out = np.where(m2, np.sqrt(x2 + y2) * il2 - r1, out)
            return out
        if k == "box":
            q = P - p["c"]
            if "R" in p:
                q = q @ p["R"]
            d = np.abs(q) - p["h"]
            outside = np.linalg.norm(np.maximum(d, 0.0), axis=1)
            inside = np.minimum(np.max(d, axis=1), 0.0)
            return outside + inside - p.get("round", 0.0)
        raise ValueError(k)


def chain(points, radii, bone, k=0.02, mat="base", name="", bones=None):
    """Tapered tube through `points` as round cones (antlers, tusks, tails, claws)."""
    out = []
    for i in range(len(points) - 1):
        out.append(Prim("cone", bones[i] if bones else bone, k=k if i else (k if name.endswith("+") else k), mat=mat,
                        name=f"{name}{i}", a=points[i], b=points[i + 1], ra=radii[i], rb=radii[i + 1]))
    return out


def bezier(p0, p1, p2, p3, n):
    t = np.linspace(0.0, 1.0, n, dtype=F)[:, None]
    p0, p1, p2, p3 = map(_v, (p0, p1, p2, p3))
    return ((1 - t) ** 3) * p0 + 3 * ((1 - t) ** 2) * t * p1 + 3 * (1 - t) * t * t * p2 + (t ** 3) * p3


class Part:
    """An ordered primitive list plus an optional displacement function."""

    def __init__(self, name, prims, displace=None, band=0.06):
        self.name, self.prims, self.displace, self.band = name, list(prims), displace, band

    def bounds(self, pad=0.05):
        lo = np.min([p.bounds[0] for p in self.prims if not p.neg], axis=0) - pad
        hi = np.max([p.bounds[1] for p in self.prims if not p.neg], axis=0) + pad
        return lo, hi

    def eval(self, P, keep=False, displace=True, cull=True):
        """Distance at points P (N,3). keep=True also returns per-primitive distances (N,M).
        cull=False evaluates every primitive everywhere (exact far field, slower)."""
        P = _v(P)
        n = len(P)
        big = F(1e3)
        d = np.full(n, big, F)
        D = np.full((n, len(self.prims)), big, F) if keep else None
        for j, pr in enumerate(self.prims):
            if cull:
                lo, hi = pr.bounds
                m = pr.k + self.band + 0.02
                sel = np.all((P >= lo - m) & (P <= hi + m), axis=1)
                if not sel.any():
                    continue
                idx = np.nonzero(sel)[0]
            else:
                idx = np.arange(n)
            dj = pr.dist(P[idx]).astype(F)
            if keep:
                D[idx, j] = dj
            if pr.neg:
                d[idx] = smax(d[idx], -dj, pr.k)
            else:
                d[idx] = smin(d[idx], dj, pr.k)
        if displace and self.displace is not None:
            near = np.abs(d) < self.band
            if near.any():
                idx = np.nonzero(near)[0]
                d[idx] = d[idx] - self.displace(P[idx], D[idx] if keep else None, self)
        return (d, D) if keep else d

    def gradient(self, P, eps=0.002, displace=True, cull=True):
        P = _v(P)
        g = np.zeros_like(P)
        for a in range(3):
            o = np.zeros(3, F)
            o[a] = eps
            g[:, a] = (self.eval(P + o, displace=displace, cull=cull) -
                       self.eval(P - o, displace=displace, cull=cull)) / (2 * eps)
        return g


def grid(part, h, pad=0.06, coarse=4):
    """Distance grid over the part's bounds. A coarse pass (h*coarse) is upsampled everywhere; only voxels
    within a narrow band of the coarse surface are evaluated exactly (marching cubes only needs the sign
    pattern and values near the zero crossing)."""
    lo, hi = part.bounds(pad)
    shape = np.ceil((hi - lo) / h).astype(int) + 1
    H = h * coarse
    cshape = np.ceil((shape - 1) / coarse).astype(int) + 2
    cx = [lo[a] + np.arange(cshape[a], dtype=F) * H for a in range(3)]
    X, Y, Z = np.meshgrid(*cx, indexing="ij")
    C = part.eval(np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)).reshape(X.shape)
    # trilinear upsampling of the coarse field to the fine grid
    fi = [np.arange(shape[a], dtype=F) / coarse for a in range(3)]
    i0 = [np.clip(np.floor(f).astype(int), 0, cshape[a] - 2) for a, f in enumerate(fi)]
    t = [f - i for f, i in zip(fi, i0)]
    vol = np.zeros(tuple(shape), F)
    for dx in (0, 1):
        wx = (t[0] if dx else 1 - t[0])[:, None, None]
        for dy in (0, 1):
            wy = (t[1] if dy else 1 - t[1])[None, :, None]
            for dz in (0, 1):
                wz = (t[2] if dz else 1 - t[2])[None, None, :]
                vol += wx * wy * wz * C[np.ix_(i0[0] + dx, i0[1] + dy, i0[2] + dz)]
    band = H * 1.8 + 0.01
    near = np.abs(vol) < band
    idx = np.nonzero(near)
    xs = [lo[a] + np.arange(shape[a], dtype=F) * h for a in range(3)]
    P = np.stack([xs[0][idx[0]], xs[1][idx[1]], xs[2][idx[2]]], 1)
    out = np.empty(len(P), F)
    step = 2_000_000
    for s0 in range(0, len(P), step):
        out[s0:s0 + step] = part.eval(P[s0:s0 + step])
    vol[idx] = out
    return vol, lo, h


def extract(part, h, pad=0.06):
    """Marching cubes on the part. Returns verts (V,3), faces (F,3) int32."""
    from skimage import measure
    vol, lo, h = grid(part, h, pad)
    verts, faces, _n, _v2 = measure.marching_cubes(vol, level=0.0, spacing=(h, h, h), allow_degenerate=False)
    verts = verts.astype(F) + lo
    # skimage's default (gradient "descent") winding already faces outward for inside-negative fields
    faces = faces.astype(np.int32)
    return verts, faces


def largest_component(verts, faces, min_fraction=0.0):
    """Keeps the largest connected component (drops floaters from thin features)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = len(verts)
    rows = np.concatenate([faces[:, 0], faces[:, 1], faces[:, 2]])
    cols = np.concatenate([faces[:, 1], faces[:, 2], faces[:, 0]])
    g = coo_matrix((np.ones(len(rows), np.int8), (rows, cols)), shape=(n, n))
    _, labels = connected_components(g, directed=False)
    counts = np.bincount(labels[faces[:, 0]])
    keep_labels = {int(np.argmax(counts))}
    if min_fraction > 0:
        keep_labels |= set(np.nonzero(counts >= counts.max() * min_fraction)[0].tolist())
    keep_f = np.isin(labels[faces[:, 0]], list(keep_labels))
    faces = faces[keep_f]
    used = np.unique(faces)
    remap = -np.ones(n, np.int64)
    remap[used] = np.arange(len(used))
    return verts[used], remap[faces].astype(np.int32)
