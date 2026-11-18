"""Numpy signed-distance modelling: primitives, smooth CSG, visual-hull carving, meshing, weights.

Typical creature workflow
-------------------------
    F = Field(lo, hi, voxel=0.01)
    parts = [round_cone(a, b, r1, r2, bone="spine_01", k=0.06), ...]
    F.union_all(parts)
    F.intersect(hull_sdf(F, views), k=0.02)      # optional: silhouettes match reference views
    verts, faces = F.mesh()
    W = part_weights(verts, parts, bones)        # skin weights from part ownership

Distances are metres (Blender world, Z up). Negative = inside.
"""
import numpy as np
from scipy import ndimage as ndi
from skimage import measure


# --------------------------------------------------------------------------- primitive SDFs

def _rotm(rot):
    if rot is None:
        return None
    rot = np.asarray(rot, float)
    if rot.shape == (3,):  # XYZ euler radians
        cx, cy, cz = np.cos(rot)
        sx, sy, sz = np.sin(rot)
        rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
        ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
        rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
        return rz @ ry @ rx
    return rot


class Prim:
    """A primitive: fn(P[...,3]) -> d[...]; lo/hi = conservative AABB; bone = skin owner."""

    def __init__(self, fn, lo, hi, bone=None, name="", k=0.0, op="union", weight=1.0):
        self.fn = fn
        self.lo = np.asarray(lo, float)
        self.hi = np.asarray(hi, float)
        self.bone = bone
        self.name = name
        self.k = float(k)
        self.op = op
        self.weight = weight

    def __call__(self, P):
        return self.fn(P)


def sphere(c, r, **kw):
    c = np.asarray(c, float)
    return Prim(lambda P: np.linalg.norm(P - c, axis=-1) - r, c - r, c + r, **kw)


def ellipsoid(c, radii, rot=None, **kw):
    c = np.asarray(c, float)
    r = np.asarray(radii, float)
    R = _rotm(rot)

    def fn(P):
        q = P - c
        if R is not None:
            q = q @ R  # world -> local (R columns are local axes)
        k0 = np.linalg.norm(q / r, axis=-1)
        k1 = np.linalg.norm(q / (r * r), axis=-1)
        return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)

    ext = np.full(3, r.max()) if R is not None else r
    return Prim(fn, c - ext, c + ext, **kw)


def round_cone(a, b, ra, rb, **kw):
    """Exact SDF of a cone capped by spheres (radius ra at a, rb at b)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ba = b - a
    l2 = float(ba @ ba)
    rr = ra - rb
    a2 = l2 - rr * rr
    il2 = 1.0 / l2

    def fn(P):
        pa = P - a
        y = pa @ ba
        z = y - l2
        x2v = pa * l2 - y[..., None] * ba
        x2 = (x2v * x2v).sum(-1)
        y2 = y * y * l2
        z2 = z * z * l2
        k = np.sign(rr) * rr * rr * x2
        d1 = np.sqrt(x2 + z2) * il2 - rb
        d2 = np.sqrt(x2 + y2) * il2 - ra
        d3 = (np.sqrt(np.maximum(x2 * a2 * il2, 0.0)) + y * rr) * il2 - ra
        return np.where(np.sign(z) * a2 * z2 > k, d1, np.where(np.sign(y) * a2 * y2 < k, d2, d3))

    m = max(ra, rb)
    return Prim(fn, np.minimum(a, b) - m, np.maximum(a, b) + m, **kw)


def capsule(a, b, r, **kw):
    return round_cone(a, b, r, r, **kw)


def flat_capsule(a, b, ra, rb, flatten, up=(0, 0, 1), **kw):
    """Round cone squashed along `up` (scale factor flatten<1) — good for tails, ears, tongues."""
    base = round_cone(np.zeros(3), np.asarray(b, float) - np.asarray(a, float), ra, rb)
    a = np.asarray(a, float)
    up = np.asarray(up, float) / np.linalg.norm(up)

    def fn(P):
        q = P - a
        h = q @ up
        q2 = q + (h / flatten - h)[..., None] * up
        return base.fn(q2) * flatten

    m = max(ra, rb)
    bb = np.asarray(b, float)
    return Prim(fn, np.minimum(a, bb) - m, np.maximum(a, bb) + m, **kw)


def box(c, half, rot=None, rounding=0.0, **kw):
    c = np.asarray(c, float)
    h = np.asarray(half, float)
    R = _rotm(rot)

    def fn(P):
        q = P - c
        if R is not None:
            q = q @ R
        q = np.abs(q) - h + rounding
        outside = np.linalg.norm(np.maximum(q, 0.0), axis=-1)
        inside = np.minimum(q.max(axis=-1), 0.0)
        return outside + inside - rounding

    ext = np.full(3, np.linalg.norm(h)) if R is not None else h
    return Prim(fn, c - ext, c + ext, **kw)


def torus(c, R_major, r_minor, axis=(0, 0, 1), **kw):
    c = np.asarray(c, float)
    ax = np.asarray(axis, float) / np.linalg.norm(axis)

    def fn(P):
        q = P - c
        h = q @ ax
        radial = np.linalg.norm(q - h[..., None] * ax, axis=-1)
        return np.sqrt((radial - R_major) ** 2 + h ** 2) - r_minor

    e = R_major + r_minor
    return Prim(fn, c - e, c + e, **kw)


def chain(points, radii, bones=None, k=0.0, name="chain", **kw):
    """Round cones along a polyline; bones: per-segment bone names (or one name)."""
    pts = [np.asarray(p, float) for p in points]
    out = []
    for i in range(len(pts) - 1):
        bone = bones[i] if isinstance(bones, (list, tuple)) else bones
        out.append(round_cone(pts[i], pts[i + 1], radii[i], radii[i + 1], bone=bone,
                              name=f"{name}_{i}", k=k, **kw))
    return out


# --------------------------------------------------------------------------- CSG

def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def smax(a, b, k):
    return -smin(-a, -b, k)


class Field:
    """Dense SDF volume on a regular grid with block-local primitive evaluation."""

    def __init__(self, lo, hi, voxel):
        self.lo = np.asarray(lo, float)
        self.voxel = float(voxel)
        self.n = (np.ceil((np.asarray(hi, float) - self.lo) / voxel).astype(int) + 1)
        self.d = np.full(tuple(self.n), 10.0, dtype=np.float32)
        self.axes = [self.lo[i] + np.arange(self.n[i]) * self.voxel for i in range(3)]

    def _block(self, lo, hi):
        i0 = np.clip(np.floor((np.asarray(lo) - self.lo) / self.voxel).astype(int), 0, self.n)
        i1 = np.clip(np.ceil((np.asarray(hi) - self.lo) / self.voxel).astype(int) + 1, 0, self.n)
        return i0, i1

    def _points(self, i0, i1):
        X, Y, Z = np.meshgrid(self.axes[0][i0[0]:i1[0]], self.axes[1][i0[1]:i1[1]],
                              self.axes[2][i0[2]:i1[2]], indexing="ij")
        return np.stack([X, Y, Z], axis=-1)

    def apply(self, prim, op=None, k=None):
        op = op or prim.op
        k = prim.k if k is None else k
        pad = k + 3 * self.voxel
        i0, i1 = self._block(prim.lo - pad, prim.hi + pad)
        if np.any(i1 <= i0):
            return self
        P = self._points(i0, i1)
        dp = prim.fn(P).astype(np.float32)
        sl = tuple(slice(i0[j], i1[j]) for j in range(3))
        cur = self.d[sl]
        if op == "union":
            self.d[sl] = smin(cur, dp, k)
        elif op == "subtract":
            self.d[sl] = smax(cur, -dp, k)
        elif op == "intersect_local":
            self.d[sl] = smax(cur, dp, k)
        else:
            raise ValueError(op)
        return self

    def union_all(self, prims):
        for p in prims:
            self.apply(p)
        return self

    def evaluate_full(self, fn, slab=32):
        """Evaluate fn on the whole grid (slab-wise along X)."""
        out = np.empty(tuple(self.n), dtype=np.float32)
        for x0 in range(0, self.n[0], slab):
            x1 = min(self.n[0], x0 + slab)
            P = self._points(np.array([x0, 0, 0]), np.array([x1, self.n[1], self.n[2]]))
            out[x0:x1] = fn(P)
        return out

    def intersect(self, other, k=0.0):
        """Smooth intersection with another full volume (same grid) or callable."""
        vol = other if isinstance(other, np.ndarray) else self.evaluate_full(other)
        self.d = smax(self.d, vol, k).astype(np.float32)
        return self

    def smooth(self, sigma_vox=0.8):
        self.d = ndi.gaussian_filter(self.d, sigma_vox).astype(np.float32)
        return self

    def mesh(self, level=0.0, step=1):
        verts, faces, _n, _v = measure.marching_cubes(self.d, level=level, spacing=(self.voxel,) * 3,
                                                      step_size=step, allow_degenerate=False)
        verts = verts + self.lo
        # orient faces outward: signed volume must be positive
        v0, v1, v2 = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
        vol = np.einsum("ij,ij->i", v0, np.cross(v1, v2)).sum() / 6.0
        if vol < 0:
            faces = faces[:, ::-1]
        return verts, faces

    def sample(self, P):
        """Trilinear sample of the field at world points P (N,3)."""
        idx = (np.asarray(P) - self.lo) / self.voxel
        return ndi.map_coordinates(self.d, idx.T, order=1, mode="nearest")


# --------------------------------------------------------------------------- visual hull

def hull_occupancy(field, views, dilate_px=1.0, slab=24):
    """Boolean occupancy of grid points projecting inside every view's mask."""
    occ = np.ones(tuple(field.n), dtype=bool)
    for v in views:
        m = v.mask
        if dilate_px > 0:
            m = ndi.binary_dilation(m, iterations=int(round(dilate_px)))
        H, W = m.shape
        for x0 in range(0, field.n[0], slab):
            x1 = min(field.n[0], x0 + slab)
            P = field._points(np.array([x0, 0, 0]), np.array([x1, field.n[1], field.n[2]]))
            u, vv, _ = v.project(P.reshape(-1, 3))
            ui = np.round(u).astype(int)
            vi = np.round(vv).astype(int)
            ok = (ui >= 0) & (ui < W) & (vi >= 0) & (vi < H)
            inside = np.zeros(ui.shape, bool)
            inside[ok] = m[vi[ok], ui[ok]]
            occ[x0:x1] &= inside.reshape(P.shape[:3])
    return occ


def occupancy_sdf(occ, voxel):
    occ = occ.astype(bool)
    outside = ndi.distance_transform_edt(~occ).astype(np.float32)
    inside = ndi.distance_transform_edt(occ).astype(np.float32)
    return (outside - inside) * voxel


def hull_sdf(field, views, dilate_px=1.0):
    return occupancy_sdf(hull_occupancy(field, views, dilate_px), field.voxel)


# --------------------------------------------------------------------------- skin weights

def part_weights(verts, parts, bone_names, falloff=0.04, power=1.0, top=4, adjacency=None,
                 smooth_iters=4, smooth_factor=0.5):
    """Per-vertex bone weights from primitive ownership.

    Weight of bone b at vertex v = max over parts of b of exp(-max(d,0)/falloff)*part.weight.
    Returns (N, B) array normalised, limited to `top` influences.
    """
    N = len(verts)
    B = len(bone_names)
    idx = {b: i for i, b in enumerate(bone_names)}
    W = np.zeros((N, B), dtype=np.float64)
    for p in parts:
        if p.bone is None or p.bone not in idx:
            continue
        d = p.fn(verts)
        w = np.exp(-np.maximum(d, 0.0) / falloff) ** power * p.weight
        j = idx[p.bone]
        W[:, j] = np.maximum(W[:, j], w)
    if adjacency is not None and smooth_iters:
        for _ in range(smooth_iters):
            avg = adjacency @ W
            W = (1 - smooth_factor) * W + smooth_factor * avg
    return limit_weights(W, top)


def limit_weights(W, top=4, min_w=0.01):
    W = W.copy()
    if W.shape[1] > top:
        cut = np.argsort(-W, axis=1)[:, top:]
        np.put_along_axis(W, cut, 0.0, axis=1)
    W[W < min_w] = 0.0
    s = W.sum(axis=1, keepdims=True)
    bad = s[:, 0] <= 0
    if np.any(bad):
        W[bad, int(np.argmax(W.sum(axis=0)))] = 1.0
        s = W.sum(axis=1, keepdims=True)
    return W / s


def adjacency_matrix(n_verts, faces):
    """Row-normalised vertex adjacency (scipy.sparse CSR) for weight smoothing."""
    from scipy import sparse
    f = np.asarray(faces)
    edges = []
    k = f.shape[1]
    for i in range(k):
        edges.append(np.stack([f[:, i], f[:, (i + 1) % k]], 1))
    e = np.concatenate(edges)
    e = np.concatenate([e, e[:, ::-1]])
    A = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n_verts, n_verts)).tocsr()
    A.data[:] = 1.0
    deg = np.asarray(A.sum(axis=1)).ravel()
    deg[deg == 0] = 1
    return sparse.diags(1.0 / deg) @ A
