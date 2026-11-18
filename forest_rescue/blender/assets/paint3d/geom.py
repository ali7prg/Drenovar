"""Geometry for image-based reconstruction (no bpy): mesh container, painted cards fitted to a
reference camera, tapered tubes, revolved trunks, silhouette inflation (marching cubes).

World: Blender Z-up metres. Reference camera = frlib.refs.View (orthographic, possibly elevated:
d = (0, cos e, -sin e)); camera depth t is measured along d (positive = away from the camera).
"""
import numpy as np
from scipy import ndimage as ndi


def nrm(v, axis=-1):
    v = np.asarray(v, float)
    return v / np.maximum(np.linalg.norm(v, axis=axis, keepdims=True), 1e-12)


class Mesh:
    """Triangle soup with per-vertex UV / colour (wind RGBA) / normal and per-triangle material."""

    def __init__(self):
        self.V, self.T, self.UV, self.C, self.N, self.M = [], [], [], [], [], []
        self.nv = 0

    def add(self, V, T, UV, C, N, mat):
        V = np.asarray(V, float).reshape(-1, 3)
        n = len(V)
        T = np.asarray(T, np.int64).reshape(-1, 3)
        C = np.asarray(C, float)
        if C.ndim == 1:
            C = np.tile(C, (n, 1))
        self.V.append(V)
        self.T.append(T + self.nv)
        self.UV.append(np.asarray(UV, float).reshape(n, 2))
        self.C.append(C.reshape(n, 4))
        self.N.append(nrm(np.asarray(N, float).reshape(n, 3)))
        self.M.append(np.full(len(T), int(mat), np.int32))
        self.nv += n
        return self

    def extend(self, other):
        V, T, UV, C, N, M = other.arrays()
        if len(V) == 0:
            return self
        base = self.nv
        self.V.append(V)
        self.T.append(T + base)
        self.UV.append(UV)
        self.C.append(C)
        self.N.append(N)
        self.M.append(M)
        self.nv += len(V)
        return self

    def arrays(self):
        if not self.V:
            return (np.zeros((0, 3)), np.zeros((0, 3), np.int64), np.zeros((0, 2)), np.zeros((0, 4)),
                    np.zeros((0, 3)), np.zeros(0, np.int32))
        return (np.concatenate(self.V), np.concatenate(self.T), np.concatenate(self.UV),
                np.concatenate(self.C), np.concatenate(self.N), np.concatenate(self.M))

    def tris(self):
        return int(sum(len(t) for t in self.T))

    def transformed(self, R=None, t=None, mirror_x=False):
        V, T, UV, C, N, M = self.arrays()
        V = V.copy()
        N = N.copy()
        if mirror_x:
            V[:, 0] *= -1
            N[:, 0] *= -1
            T = T[:, ::-1]
        if R is not None:
            V = V @ np.asarray(R).T
            N = N @ np.asarray(R).T
        if t is not None:
            V = V + np.asarray(t)
        out = Mesh()
        out.add(V, T, UV, C, N, 0)
        out.M = [M.copy()]
        return out


def rot_z(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


# ------------------------------------------------------------------ reference camera helpers

def elevated_dir(elev_deg):
    e = np.radians(elev_deg)
    return np.array([0.0, np.cos(e), -np.sin(e)])


def world_at_y(view, u, v, y):
    """World point on the camera ray through pixel (u,v) with world Y == y (elevated ortho view)."""
    u = np.asarray(u, float)
    v = np.asarray(v, float)
    y = np.broadcast_to(np.asarray(y, float), u.shape) if np.ndim(u) else float(y)
    P0 = view.world_of_pixel(u[..., None] if np.ndim(u) else u, v[..., None] if np.ndim(v) else v, 0.0) \
        if False else None
    # ray: P(t) = A + t d with A = world_of_pixel(u, v, 0)
    A = (view.anchor + ((u - view.ax) / view.ppm)[..., None] * view.right
         + ((view.ay - v) / view.ppm)[..., None] * view.up) if np.ndim(u) else \
        view.anchor + ((u - view.ax) / view.ppm) * view.right + ((view.ay - v) / view.ppm) * view.up
    dy = view.d[1]
    t = (y - A[..., 1]) / dy
    return A + np.asarray(t)[..., None] * view.d if np.ndim(u) else A + t * view.d


def pix_to_world(view, u, v, t):
    """Vectorised view.world_of_pixel(u, v, t)."""
    u = np.asarray(u, float)
    v = np.asarray(v, float)
    t = np.broadcast_to(np.asarray(t, float), u.shape)
    return (view.anchor + ((u - view.ax) / view.ppm)[..., None] * view.right
            + ((view.ay - v) / view.ppm)[..., None] * view.up + t[..., None] * view.d)


def cam_to_world_dir(view, n_cam):
    """Direction in camera coords (right, up, depth) -> world."""
    n_cam = np.asarray(n_cam, float)
    return nrm(n_cam[..., 0:1] * view.right + n_cam[..., 1:2] * view.up + n_cam[..., 2:3] * view.d)


# ------------------------------------------------------------------ cards

def front_card(view, rect, center_px, t_center, normal, uv_rect, col, nrm_v=None, flip=False):
    """Quad whose reference-view projection is exactly `rect` (pixels x0,y0,x1,y1) on the plane through
    the 3-D point at (center_px, t_center) with world normal `normal` (any tilt < 90 deg from -d).

    uv_rect = (u0, v0, u1, v1) Blender UV of the tile (v1 = top row)."""
    x0, y0, x1, y1 = rect
    cu, cv = center_px
    C = pix_to_world(view, np.array([cu]), np.array([cv]), np.array([t_center]))[0]
    n = nrm(normal)
    if np.dot(n, -view.d) < 0.15:  # never edge-on to the reference camera
        n = nrm(n + (0.15 - np.dot(n, -view.d) + 0.05) * -view.d)
    us = np.array([x0, x1, x1, x0], float)
    vs = np.array([y1, y1, y0, y0], float)      # bottom-left, bottom-right, top-right, top-left
    P0 = pix_to_world(view, us, vs, np.zeros(4))
    t = ((C - P0) @ n) / (view.d @ n)
    P = P0 + t[:, None] * view.d
    u0, v0, u1, v1 = uv_rect
    if flip:
        u0, u1 = u1, u0
    UV = np.array([[u0, v0], [u1, v0], [u1, v1], [u0, v1]])
    T = np.array([[0, 1, 2], [0, 2, 3]])
    N = np.tile(n if nrm_v is None else nrm(nrm_v), (4, 1)) if nrm_v is None or np.ndim(nrm_v) == 1 else nrm_v
    return P, T, UV, col, N


def free_card(center, normal, up_hint, w, h, uv_rect, col, nrm_v=None, flip=False, pivot_v=0.5):
    """Rectangle w x h (metres) centred at `center` (pivot_v: 0 = bottom edge at center)."""
    n = nrm(normal)
    up = np.asarray(up_hint, float) - np.dot(up_hint, n) * n
    if np.linalg.norm(up) < 1e-6:
        up = np.cross(n, [1.0, 0, 0]) if abs(n[0]) < 0.9 else np.cross(n, [0, 1.0, 0])
    up = nrm(up)
    rt = nrm(np.cross(up, n))
    c = np.asarray(center, float) + up * h * (0.5 - pivot_v)
    P = np.array([c - rt * w / 2 - up * h / 2, c + rt * w / 2 - up * h / 2,
                  c + rt * w / 2 + up * h / 2, c - rt * w / 2 + up * h / 2])
    u0, v0, u1, v1 = uv_rect
    if flip:
        u0, u1 = u1, u0
    UV = np.array([[u0, v0], [u1, v0], [u1, v1], [u0, v1]])
    T = np.array([[0, 1, 2], [0, 2, 3]])
    N = np.tile(n, (4, 1)) if nrm_v is None else (np.tile(nrm(nrm_v), (4, 1)) if np.ndim(nrm_v) == 1 else nrm_v)
    return P, T, UV, col, N


def bent_card(points, widths, normals, uv_rect, col, nrm_v=None, flip=False):
    """Strip card along a polyline (k points): width per point, facing `normals` (k,3).
    UV: u across (u0..u1), v along (v0 at points[0] .. v1 at points[-1])."""
    P = np.asarray(points, float)
    k = len(P)
    tang = np.gradient(P, axis=0)
    tang = nrm(tang)
    side = nrm(np.cross(tang, normals))
    L = P - side * (np.asarray(widths)[:, None] / 2)
    R = P + side * (np.asarray(widths)[:, None] / 2)
    V = np.empty((2 * k, 3))
    V[0::2] = L
    V[1::2] = R
    u0, v0, u1, v1 = uv_rect
    if flip:
        u0, u1 = u1, u0
    s = np.linspace(0, 1, k)
    UV = np.empty((2 * k, 2))
    UV[0::2, 0] = u0
    UV[1::2, 0] = u1
    UV[0::2, 1] = v0 + (v1 - v0) * s
    UV[1::2, 1] = v0 + (v1 - v0) * s
    T = []
    for i in range(k - 1):
        a, b, c, d = 2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2
        T += [[a, b, c], [a, c, d]]
    N = np.repeat(nrm(normals), 2, axis=0) if nrm_v is None else np.repeat(nrm(nrm_v), 2, axis=0)
    C = np.repeat(np.asarray(col, float).reshape(-1, 4), 2, axis=0) if np.ndim(col) == 2 else col
    return V, np.array(T), UV, C, N


# ------------------------------------------------------------------ tubes

def frames(P):
    """Parallel-transport frames along a polyline: tangents, normals, binormals."""
    P = np.asarray(P, float)
    T = nrm(np.gradient(P, axis=0))
    Nn = np.zeros_like(T)
    a = np.array([0, 0, 1.0]) if abs(T[0, 2]) < 0.9 else np.array([1.0, 0, 0])
    Nn[0] = nrm(np.cross(T[0], a))
    for i in range(1, len(P)):
        b = np.cross(T[i - 1], T[i])
        if np.linalg.norm(b) < 1e-9:
            Nn[i] = Nn[i - 1]
        else:
            b = nrm(b)
            ang = np.arccos(np.clip(np.dot(T[i - 1], T[i]), -1, 1))
            v = Nn[i - 1]
            Nn[i] = v * np.cos(ang) + np.cross(b, v) * np.sin(ang) + b * np.dot(b, v) * (1 - np.cos(ang))
        Nn[i] = nrm(Nn[i] - np.dot(Nn[i], T[i]) * T[i])
    B = np.cross(T, Nn)
    return T, Nn, B


def tube(P, radii, sides, uv_rect, col, depth_scale=None, cap=False, phase=0.0, ref_side=None):
    """Tapered tube along polyline P (k,3) with ring radii (k,). UV strip: u around, v along.

    ref_side: optional world vector to align the ring start (u=0) with (keeps seams at the back)."""
    P = np.asarray(P, float)
    k = len(P)
    T, Nn, B = frames(P)
    if ref_side is not None:
        # rotate frames so that Nn points as close as possible to ref_side
        r = np.asarray(ref_side, float)
        for i in range(k):
            x = np.dot(r, Nn[i])
            y = np.dot(r, B[i])
            a = np.arctan2(y, x)
            n2 = Nn[i] * np.cos(a) + B[i] * np.sin(a)
            b2 = np.cross(T[i], n2)
            Nn[i], B[i] = n2, b2
    ang = phase + np.linspace(0, 2 * np.pi, sides + 1)
    ca, sa = np.cos(ang), np.sin(ang)
    rad = np.asarray(radii, float)
    ds = np.ones(k) if depth_scale is None else np.broadcast_to(np.asarray(depth_scale, float), (k,))
    V = (P[:, None, :] + rad[:, None, None] * (ca[None, :, None] * Nn[:, None, :]
                                              + (sa[None, :] * ds[:, None])[:, :, None] * B[:, None, :]))
    Nv = nrm(ca[None, :, None] * Nn[:, None, :] * ds[:, None, None] + sa[None, :, None] * B[:, None, :])
    V = V.reshape(-1, 3)
    Nv = Nv.reshape(-1, 3)
    u0, v0, u1, v1 = uv_rect
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    s = seg / max(seg[-1], 1e-9)
    UV = np.empty((k, sides + 1, 2))
    UV[..., 0] = u0 + (u1 - u0) * np.linspace(0, 1, sides + 1)[None, :]
    UV[..., 1] = (v0 + (v1 - v0) * s)[:, None]
    UV = UV.reshape(-1, 2)
    Tr = []
    w = sides + 1
    for i in range(k - 1):
        for j in range(sides):
            a, b, c, d = i * w + j, i * w + j + 1, (i + 1) * w + j + 1, (i + 1) * w + j
            Tr += [[a, b, c], [a, c, d]]
    C = np.asarray(col, float)
    if C.ndim == 2 and len(C) == k:
        C = np.repeat(C, w, axis=0)
    return V, np.array(Tr), UV, C, Nv


def resample_polyline(P, step):
    P = np.asarray(P, float)
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    if seg[-1] < 1e-9:
        return P[:1], np.array([0.0])
    n = max(2, int(np.ceil(seg[-1] / step)) + 1)
    s = np.linspace(0, seg[-1], n)
    out = np.stack([np.interp(s, seg, P[:, i]) for i in range(P.shape[1])], 1)
    return out, s


# ------------------------------------------------------------------ inflation (marching cubes)

def inflate(mask, view, voxel_px=2.0, depth_px=None, depth_scale=1.0, back_scale=1.0, t_offset_px=None,
            smooth=1.0, noise=None):
    """Closed mesh from a silhouette: |t - t0(u,v)| <= h(u,v), h = depth_scale * sqrt(DT * (2 R - DT)).

    R = local medial radius (max DT propagated), so tubes get round sections and blobs domes.
    depth_px: optional explicit half-depth image (pixels). back_scale scales the back half.
    Returns world verts, faces (marching cubes in camera space -> world)."""
    from skimage import measure
    m = mask.astype(bool)
    dt = ndi.distance_transform_edt(m)
    if depth_px is None:
        R = ndi.grey_dilation(dt, size=(int(2 * dt.max()) | 1,) * 2) if dt.max() < 40 else _local_radius(dt)
        h = depth_scale * np.sqrt(np.clip(dt * (2 * R - dt), 0, None))
    else:
        h = depth_px
    if smooth:
        h = ndi.gaussian_filter(h, smooth) * m
    H, W = m.shape
    s = voxel_px
    # sample grid (voxel centres) in pixel units
    ys = np.arange(0, H, s)
    xs = np.arange(0, W, s)
    hmax = float(h.max()) * max(1.0, back_scale) + 2 * s
    ts = np.arange(-hmax, hmax + s, s)
    hs = ndi.map_coordinates(h, np.meshgrid(ys, xs, indexing="ij"), order=1)
    t0 = 0.0 if t_offset_px is None else ndi.map_coordinates(t_offset_px, np.meshgrid(ys, xs, indexing="ij"), order=1)
    inside_m = ndi.map_coordinates(m.astype(float), np.meshgrid(ys, xs, indexing="ij"), order=1)
    # signed field: positive inside
    tt = ts[None, None, :] - (t0[..., None] if np.ndim(t0) else t0)
    front = hs[..., None]
    back = hs[..., None] * back_scale
    f = np.minimum(np.where(tt < 0, front + tt, back - tt), (inside_m[..., None] - 0.5) * 4 * s)
    if noise is not None:
        f = f + noise(ys, xs, ts)
    f = np.pad(f, 1, constant_values=-1.0)
    verts, faces, normals, _ = measure.marching_cubes(f, level=0.0)
    verts -= 1.0
    vy = np.interp(verts[:, 0], np.arange(len(ys)), ys)
    vx = np.interp(verts[:, 1], np.arange(len(xs)), xs)
    vt = np.interp(verts[:, 2], np.arange(len(ts)), ts)
    P = pix_to_world(view, vx, vy, vt / view.ppm)
    faces = faces[:, ::-1]  # outward winding after the (y,x,t) axis order flip
    return P, faces


def _local_radius(dt):
    """Medial radius propagated to every pixel: max over medial points whose disk covers the pixel."""
    from skimage import morphology
    sk = morphology.medial_axis(dt > 0)
    R = np.zeros_like(dt)
    ys, xs = np.nonzero(sk)
    r = dt[ys, xs]
    order = np.argsort(r)
    H, W = dt.shape
    for y, x, rr in zip(ys[order], xs[order], r[order]):
        ri = int(np.ceil(rr))
        y0, y1, x0, x1 = max(0, y - ri), min(H, y + ri + 1), max(0, x - ri), min(W, x + ri + 1)
        yy, xx = np.mgrid[y0:y1, x0:x1]
        disk = (yy - y) ** 2 + (xx - x) ** 2 <= rr * rr
        sub = R[y0:y1, x0:x1]
        np.maximum(sub, np.where(disk, rr, 0), out=sub)
    R = np.maximum(R, dt)
    return R


def vertex_normals(V, F):
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    vn = np.zeros_like(V)
    for i in range(3):
        np.add.at(vn, F[:, i], fn)
    return nrm(vn)
