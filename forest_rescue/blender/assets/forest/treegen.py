"""Procedural tree skeletons and game meshes (pure numpy) for the «Лес потерянных» forest kit.

Pipeline per tree variant
-------------------------
1. crown envelope: reference-silhouette visual hull (front-view mask + elliptical depth) or analytic
2. skeleton: space colonisation (Runions 2007) from a trunk polyline into crown attractors
   (or the whorl generator for conifers), Laplacian smoothing, pipe-model radii
3. bark: tapered tubes along branch chains (parallel-transport rings, root flare/buttress lobes,
   world-scaled tiling UVs, tip fans) -> material slot 0
4. foliage: alpha-tested cards from the shared atlas, oriented outward/up, spherized normals -> slot 1
5. vertex colour COLOR_0 (wind): R = branch sway weight (0 trunk base -> 1 tips),
   G = leaf flutter weight, B = per-branch phase 0..1, A = crown ambient occlusion (1 = open)
6. LOD1/LOD2: pruned skeleton, fewer ring segments, k-means merged cards (dense clump tiles),
   bark mapped to the atlas bark strip (single material) when requested.
"""
import math
import numpy as np
from scipy.spatial import cKDTree
from scipy.cluster.vq import kmeans2

import atlas


# ============================================================================ mesh accumulator

class MeshData:
    """Polygon soup with per-loop UVs, per-vertex colour/normal, per-face material."""

    def __init__(self):
        self.V = []          # list of (n,3)
        self.F = []          # list of faces (tuples of global vertex ids)
        self.UV = []         # per face: list of (u,v) per corner
        self.MAT = []
        self.COL = []        # list of (n,4) per-vertex colours
        self.NRM = []        # list of (n,3) custom normals or None blocks
        self.nv = 0
        self.has_custom_normals = False

    def add(self, verts, faces, uvs, mat, col, normals=None):
        verts = np.asarray(verts, float)
        base = self.nv
        self.V.append(verts)
        self.COL.append(np.asarray(col, float).reshape(len(verts), 4))
        if normals is not None:
            self.has_custom_normals = True
            self.NRM.append(np.asarray(normals, float))
        else:
            self.NRM.append(None)
        for f, uv in zip(faces, uvs):
            self.F.append(tuple(int(i) + base for i in f))
            self.UV.append(uv)
            self.MAT.append(mat)
        self.nv += len(verts)

    def merge(self, other):
        for i in range(len(other.V)):
            pass
        base = self.nv
        self.V += other.V
        self.COL += other.COL
        self.NRM += other.NRM
        self.has_custom_normals |= other.has_custom_normals
        self.F += [tuple(i + base for i in f) for f in other.F]
        self.UV += other.UV
        self.MAT += other.MAT
        self.nv += other.nv

    def arrays(self):
        V = np.concatenate(self.V) if self.V else np.zeros((0, 3))
        C = np.concatenate(self.COL) if self.COL else np.zeros((0, 4))
        N = None
        if self.has_custom_normals:
            blocks = []
            for v, n in zip(self.V, self.NRM):
                blocks.append(n if n is not None else np.full((len(v), 3), np.nan))
            N = np.concatenate(blocks)
        return V, self.F, self.UV, np.array(self.MAT, int), C, N

    def tris(self):
        return sum(len(f) - 2 for f in self.F)


# ============================================================================ geometry helpers

def normalize(v, axis=-1):
    v = np.asarray(v, float)
    return v / np.maximum(np.linalg.norm(v, axis=axis, keepdims=True), 1e-12)


def perp(v):
    v = normalize(v)
    a = np.array([1.0, 0, 0]) if abs(v[0]) < 0.9 else np.array([0, 1.0, 0])
    p = np.cross(v, a)
    return normalize(p)


def transport_frames(P):
    """Parallel-transport frames (T, N, B) along a polyline P (k,3)."""
    k = len(P)
    T = np.zeros((k, 3))
    for i in range(k):
        a = P[max(i - 1, 0)]
        b = P[min(i + 1, k - 1)]
        T[i] = normalize(b - a)
    N = np.zeros((k, 3))
    N[0] = perp(T[0])
    for i in range(1, k):
        n = N[i - 1] - T[i] * np.dot(N[i - 1], T[i])
        if np.linalg.norm(n) < 1e-6:
            n = perp(T[i])
        N[i] = normalize(n)
    B = np.cross(T, N)
    return T, N, B


# ============================================================================ crown envelopes

class Envelope:
    """Crown volume as a voxel occupancy grid with inside-depth (metres)."""

    def __init__(self, occ, lo, voxel):
        from scipy import ndimage as ndi
        self.occ = occ
        self.lo = np.asarray(lo, float)
        self.voxel = voxel
        self.depth = ndi.distance_transform_edt(occ) * voxel
        idx = np.argwhere(occ)
        pts = self.lo + idx * voxel
        self.centre = pts.mean(0)
        self.pmin = pts.min(0)
        self.pmax = pts.max(0)

    def inside_depth(self, P):
        idx = np.round((np.asarray(P) - self.lo) / self.voxel).astype(int)
        ok = np.all((idx >= 0) & (idx < np.array(self.occ.shape)), axis=-1)
        out = np.zeros(len(idx))
        ii = idx[ok]
        out[ok] = self.depth[ii[:, 0], ii[:, 1], ii[:, 2]]
        return out

    def contains(self, P):
        return self.inside_depth(P) > 0

    def sample_even(self, n, rng, dmin=0.6, dmax=1.6):
        """Farthest-point sampling of n points whose inside-depth is in [dmin, dmax]."""
        idx = np.argwhere(self.occ & (self.depth >= dmin) & (self.depth <= dmax))
        if len(idx) < n:
            idx = np.argwhere(self.occ)
        pts = self.lo + idx * self.voxel
        if len(pts) > 6000:
            pts = pts[rng.choice(len(pts), 6000, replace=False)]
        sel = [int(rng.integers(len(pts)))]
        d = np.linalg.norm(pts - pts[sel[0]], axis=1)
        for _ in range(n - 1):
            k = int(np.argmax(d))
            sel.append(k)
            d = np.minimum(d, np.linalg.norm(pts - pts[k], axis=1))
        return pts[sel] + rng.uniform(-0.5, 0.5, (n, 3)) * self.voxel

    def sample(self, n, rng, shell=None, inner_weight=0.15, clumps=None, clump_r=1.6):
        """Attractor sampling: uniform in volume, biased to an outer shell and/or clumps."""
        idx = np.argwhere(self.occ)
        d = self.depth[self.occ]
        w = np.ones(len(idx))
        if shell is not None:
            w = np.where(d <= shell, 1.0, inner_weight)
        if clumps is not None:
            pts = self.lo + idx * self.voxel
            dd, _ = cKDTree(clumps).query(pts)
            w = w * (0.08 + np.exp(-(dd / clump_r) ** 2))
        w = w / w.sum()
        pick = rng.choice(len(idx), size=n, p=w)
        P = self.lo + (idx[pick] + rng.uniform(-0.5, 0.5, (n, 3))) * self.voxel
        return P


def envelope_from_mask(mask, ppm, ground_row, centre_col, z_min=0.0, depth_scale=1.0, voxel=0.2,
                       depth_shift=None, y_offset=0.0, x_scale=1.0, z_scale=1.0, mirror=False, row_lo=None):
    """Visual hull of a front-view silhouette (image right=+X, up=+Z) with elliptical depth (Y).

    Each image row's horizontal extent [xl, xr] defines an ellipse of half-depth
    (xr-xl)/2*depth_scale around Y=y_offset.  Only rows above z_min are used."""
    H, W = mask.shape
    xs_all = (np.arange(W) - centre_col) / ppm * x_scale
    if mirror:
        xs_all = -xs_all
    zs_all = (ground_row - np.arange(H)) / ppm * z_scale
    xmin, xmax = xs_all.min(), xs_all.max()
    if mirror:
        xmin, xmax = min(xmin, xmax), max(xmin, xmax)
    zmax = zs_all.max()
    hw = max(abs(xmin), abs(xmax))
    lo = np.array([-hw - 0.5, -hw * depth_scale - 0.5 + y_offset, z_min])
    hi = np.array([hw + 0.5, hw * depth_scale + 0.5 + y_offset, zmax + 0.2])
    n = np.ceil((hi - lo) / voxel).astype(int) + 1
    occ = np.zeros(n, bool)
    gx = lo[0] + np.arange(n[0]) * voxel
    gy = lo[1] + np.arange(n[1]) * voxel
    gz = lo[2] + np.arange(n[2]) * voxel
    for k, z in enumerate(gz):
        row = int(round(ground_row - z / z_scale * ppm))
        if row < 0 or row >= H:
            continue
        if row_lo is not None and row > row_lo:
            continue
        cols = np.nonzero(mask[row])[0]
        if len(cols) == 0:
            continue
        xr = xs_all[cols]
        xl_, xr_ = xr.min(), xr.max()
        cx = (xl_ + xr_) / 2
        hwr = max((xr_ - xl_) / 2, voxel)
        # columns of this row inside the mask (allow gaps)
        u = (gx / x_scale * (-1 if mirror else 1)) * ppm + centre_col
        ui = np.clip(np.round(u).astype(int), 0, W - 1)
        inx = mask[row, ui] & (u >= 0) & (u < W)
        ry = hwr * depth_scale
        if depth_shift is not None:
            yc = y_offset + depth_shift(z)
        else:
            yc = y_offset
        ell = ((gx[:, None] - cx) / hwr) ** 2 + ((gy[None, :] - yc) / ry) ** 2 <= 1.0
        occ[:, :, k] = ell & inx[:, None]
    return Envelope(occ, lo, voxel)


def envelope_ellipsoid(centre, radii, voxel=0.2, squash_top=1.0, noise=None, rng=None):
    c = np.asarray(centre, float)
    r = np.asarray(radii, float)
    lo = c - r - 0.4
    hi = c + r + 0.4
    n = np.ceil((hi - lo) / voxel).astype(int) + 1
    g = [lo[i] + np.arange(n[i]) * voxel for i in range(3)]
    X, Y, Z = np.meshgrid(*g, indexing="ij")
    q = ((X - c[0]) / r[0]) ** 2 + ((Y - c[1]) / r[1]) ** 2 + ((Z - c[2]) / r[2]) ** 2
    if noise is not None:
        q = q + noise(X, Y, Z)
    return Envelope(q <= 1.0, lo, voxel)


# ============================================================================ skeleton

class Skeleton:
    def __init__(self):
        self.P = []
        self.parent = []
        self.fixed = []       # True for authored trunk nodes (not smoothed / not grown from unless allowed)
        self.can_grow = []

    def add(self, p, parent, fixed=False, can_grow=True):
        self.P.append(np.asarray(p, float))
        self.parent.append(parent)
        self.fixed.append(fixed)
        self.can_grow.append(can_grow)
        return len(self.P) - 1

    def add_polyline(self, pts, parent=-1, can_grow_from_z=None, fixed=True):
        ids = []
        for i, p in enumerate(pts):
            cg = can_grow_from_z is not None and p[2] >= can_grow_from_z
            pid = parent if i == 0 else ids[-1]
            ids.append(self.add(p, pid, fixed=fixed, can_grow=cg))
        return ids

    def arrays(self):
        return np.array(self.P), np.array(self.parent), np.array(self.fixed), np.array(self.can_grow)


def space_colonize(sk, attractors, D=0.35, di=2.6, dk=0.7, iters=120, tropism=(0, 0, 0), trop_w=0.0,
                   rng=None, jitter=0.08, max_children=3):
    """Grow skeleton `sk` (in place) toward attractors (Runions et al. 2007)."""
    rng = rng or np.random.default_rng(0)
    A = np.asarray(attractors, float)
    alive = np.ones(len(A), bool)
    trop = np.asarray(tropism, float)
    nchild = {}
    for i, p in enumerate(sk.parent):
        if p >= 0:
            nchild[p] = nchild.get(p, 0) + 1
    for it in range(iters):
        if not alive.any():
            break
        P = np.array(sk.P)
        grow_ids = np.nonzero(np.array(sk.can_grow))[0]
        if len(grow_ids) == 0:
            break
        tree = cKDTree(P[grow_ids])
        Aa = A[alive]
        d, nn = tree.query(Aa, distance_upper_bound=di)
        ok = np.isfinite(d)
        if not ok.any():
            break
        nodes = grow_ids[nn[ok]]
        vec = normalize(Aa[ok] - P[nodes])
        acc = np.zeros((len(P), 3))
        np.add.at(acc, nodes, vec)
        cnt = np.bincount(nodes, minlength=len(P))
        new_ids = []
        for n in np.nonzero(cnt)[0]:
            if nchild.get(n, 0) >= max_children:
                continue
            dvec = acc[n] / cnt[n]
            if np.linalg.norm(dvec) < 0.15:
                dvec = dvec + rng.normal(0, 0.3, 3)
            dvec = normalize(normalize(dvec) + trop * trop_w + rng.normal(0, jitter, 3))
            q = P[n] + D * dvec
            nid = sk.add(q, int(n), fixed=False, can_grow=True)
            nchild[n] = nchild.get(n, 0) + 1
            new_ids.append(nid)
        if not new_ids:
            break
        NP = np.array(sk.P)[new_ids]
        kt = cKDTree(NP)
        hit = kt.query_ball_point(A, dk)
        kill = np.array([len(h) > 0 for h in hit])
        alive &= ~kill
    return sk


def children_lists(parent):
    ch = [[] for _ in range(len(parent))]
    for i, p in enumerate(parent):
        if p >= 0:
            ch[p].append(i)
    return ch


def smooth_skeleton(P, parent, fixed, iters=3, w=0.5):
    P = P.copy()
    ch = children_lists(parent)
    for _ in range(iters):
        Q = P.copy()
        for i in range(len(P)):
            if fixed[i] or parent[i] < 0:
                continue
            nb = [P[parent[i]]]
            if len(ch[i]) == 1:
                nb.append(P[ch[i][0]])
            elif len(ch[i]) > 1:
                continue      # keep branching points
            Q[i] = P[i] * (1 - w) + np.mean(nb, axis=0) * w
        P = Q
    return P


def pipe_radii(parent, r_tip=0.012, gamma=2.4, order=None):
    """Pipe model: r_parent^gamma = sum r_child^gamma, from tips down."""
    n = len(parent)
    ch = children_lists(parent)
    R = np.zeros(n)
    # process in reverse topological order (children have larger ids than parents in growth)
    order = order if order is not None else range(n - 1, -1, -1)
    for i in order:
        if not ch[i]:
            R[i] = r_tip
        else:
            R[i] = (np.sum(R[ch[i]] ** gamma)) ** (1.0 / gamma)
            # continuation bonus so straight chains taper slowly
            R[i] = max(R[i], R[ch[i]].max() * 1.02)
    return R


def topo_order(parent):
    """Indices so that every parent precedes its children."""
    ch = children_lists(parent)
    roots = [i for i, p in enumerate(parent) if p < 0]
    out = []
    stack = list(roots)
    while stack:
        i = stack.pop()
        out.append(i)
        stack.extend(ch[i])
    return out


def path_lengths(P, parent):
    order = topo_order(parent)
    L = np.zeros(len(P))
    for i in order:
        p = parent[i]
        if p >= 0:
            L[i] = L[p] + np.linalg.norm(P[i] - P[p])
    return L


def build_chains(P, parent, R):
    """Split skeleton into chains following the thickest child. Each chain = list of node ids,
    starting with its junction parent node (if any). Returns chains, chain_parent, chain_order."""
    ch = children_lists(parent)
    roots = [i for i, p in enumerate(parent) if p < 0]
    chains, cpar, corder = [], [], []
    stack = [(r, -1, 0, -1) for r in roots]   # (start node, parent chain, order, junction node)
    while stack:
        start, pc, order, junction = stack.pop()
        chain = [junction] if junction >= 0 else []
        n = start
        while True:
            chain.append(n)
            kids = ch[n]
            if not kids:
                break
            kids = sorted(kids, key=lambda k: -R[k])
            for k in kids[1:]:
                stack.append((k, len(chains), order + 1, n))
            n = kids[0]
        chains.append(chain)
        cpar.append(pc)
        corder.append(order)
    return chains, cpar, corder


# ============================================================================ bark tubes

def seg_count(r, table):
    for rmin, s in table:
        if r >= rmin:
            return s
    return table[-1][1]


SEG_LOD0 = [(0.45, 12), (0.25, 9), (0.12, 7), (0.06, 5), (0.0, 4)]
SEG_LOD1 = [(0.45, 8), (0.20, 6), (0.08, 5), (0.0, 4)]
SEG_LOD2 = [(0.30, 6), (0.0, 4)]


def resample_chain(pts, rad, step_fn, min_angle_deg=6.0):
    """Keep chain vertices where curvature/size demands; ensure max spacing step_fn(r)."""
    keep = [0]
    acc = 0.0
    for i in range(1, len(pts) - 1):
        a = pts[keep[-1]]
        b = pts[i]
        c = pts[i + 1]
        d1 = normalize(b - a)
        d2 = normalize(c - b)
        ang = math.degrees(math.acos(np.clip(np.dot(d1, d2), -1, 1)))
        acc = np.linalg.norm(b - a)
        if ang > min_angle_deg or acc >= step_fn(rad[i]):
            keep.append(i)
    keep.append(len(pts) - 1)
    return pts[keep], rad[keep], keep


def tube(md, pts, rad, segs, mat, wind, uv_mode, tile=(1.4, 1.4), flare=None, cap_tip=True, start_v=0.0,
         atlas_rect=None, ao=None, twist=0.0, seam_rot=0.0):
    """Append a tapered tube. wind: (n,4) per-point (R,G,B,A) colour; flare(i, theta) -> radius multiplier.

    uv_mode 'tile': U wraps k times around (k from circumference/tile), V by length;
    'atlas': U spans atlas_rect width once around, V spans along the length (2 periods/strip)."""
    pts = np.asarray(pts, float)
    n = len(pts)
    if n < 2:
        return
    T, N, B = transport_frames(pts)
    s = segs
    th = np.linspace(0, 2 * np.pi, s + 1) + seam_rot
    verts = []
    cols = []
    uv_ring = []
    circ0 = 2 * np.pi * max(rad[0], 1e-3)
    k_rep = max(1, int(round(circ0 / tile[0])))
    seglen = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    for i in range(n):
        ring = []
        for j, t in enumerate(th):
            tt = t + twist * seglen[i]
            r = rad[i] * (flare(i, t) if flare is not None else 1.0)
            ring.append(pts[i] + r * (math.cos(tt) * N[i] + math.sin(tt) * B[i]))
        verts.append(ring)
        cols.append([wind[i]] * (s + 1))
    verts = np.array(verts).reshape(-1, 3)
    cols = np.array(cols).reshape(-1, 4)
    faces, uvs = [], []
    if uv_mode == "tile":
        vscale = k_rep / circ0 * tile[0] / tile[1]
        U = lambda j: k_rep * j / s
        V = lambda i: start_v + seglen[i] * vscale
    else:
        u0, v0, u1, v1 = atlas_rect
        total = max(seglen[-1], 1e-3)
        U = lambda j: u0 + (u1 - u0) * j / s
        V = lambda i: v0 + (v1 - v0) * min(1.0, seglen[i] / max(total, 4.0))
    for i in range(n - 1):
        for j in range(s):
            a = i * (s + 1) + j
            b = a + 1
            c = a + (s + 1) + 1
            d = a + (s + 1)
            faces.append((a, b, c, d))
            uvs.append([(U(j), V(i)), (U(j + 1), V(i)), (U(j + 1), V(i + 1)), (U(j), V(i + 1))])
    if cap_tip:
        tip_dir = normalize(pts[-1] - pts[-2])
        tip = pts[-1] + tip_dir * rad[-1] * 1.5
        ti = len(verts)
        verts = np.vstack([verts, tip])
        cols = np.vstack([cols, wind[-1]])
        last = (n - 1) * (s + 1)
        for j in range(s):
            faces.append((last + j, last + j + 1, ti))
            vv = V(n - 1)
            uvs.append([(U(j), vv), (U(j + 1), vv), (U(j + 0.5), vv + 0.05)])
    md.add(verts, faces, uvs, mat, cols)


# ============================================================================ wind / AO

def branch_phases(chains, cpar, rng):
    """Per-chain phase: first-order chains random, deeper chains inherit with small offset."""
    ph = np.zeros(len(chains))
    for c in range(len(chains)):
        p = cpar[c]
        if p < 0:
            ph[c] = 0.0
        elif cpar[p] < 0:
            ph[c] = rng.random()
        else:
            ph[c] = (ph[p] + rng.normal(0, 0.06)) % 1.0
    return ph


def crown_ao(P, env=None, centre=None, radii=None, zrange=None, floor=0.45):
    """Ambient-occlusion proxy: deep inside the crown and low in the crown is darker."""
    P = np.asarray(P, float)
    if env is not None:
        d = env.inside_depth(P)
        dd = np.clip(d / 2.2, 0, 1)
        ao = 1.0 - 0.5 * dd
        zr = (env.pmin[2], env.pmax[2])
    else:
        q = np.linalg.norm((P - centre) / radii, axis=1)
        ao = np.clip(0.5 + 0.5 * q ** 1.5, 0, 1)
        zr = zrange
    if zr is not None:
        h = np.clip((P[:, 2] - zr[0]) / max(zr[1] - zr[0], 1e-3), 0, 1)
        ao *= 0.78 + 0.22 * h
    return np.clip(ao, floor, 1.0)


# ============================================================================ leaf cards

def card(md, centre, normal, up, w, h, tile, mat, wind_rgb, ao, crown_c, sph=0.65, attach="bottom",
         flutter=(0.25, 1.0), up_bias=0.25, bend=0.0):
    """One alpha-tested quad (optionally folded = 2 quads when bend != 0)."""
    n = normalize(normal)
    t = normalize(up - n * np.dot(up, n))
    if np.linalg.norm(t) < 1e-6:
        t = perp(n)
    b = normalize(np.cross(t, n))
    u0, v0, u1, v1 = atlas.uv_rect(tile)
    if attach == "top":
        # tile's attachment edge at the top: geometry 'up' maps to texture down
        vb, vt = v1, v0
    else:
        vb, vt = v0, v1
    if attach in ("bottom", "top"):
        c0 = centre                    # attachment point at the bottom edge
        cmid = centre + t * h * 0.5
    else:
        cmid = centre
        c0 = centre - t * h * 0.5
    corners = [c0 - b * w / 2, c0 + b * w / 2, c0 + b * w / 2 + t * h, c0 - b * w / 2 + t * h]
    uv = [(u0, vb), (u1, vb), (u1, vt), (u0, vt)]
    corners = np.array(corners)
    if bend:
        corners[2:] += n * bend * h
    # spherized normals
    out = normalize(corners - crown_c)
    nn = normalize(n * (1 - sph) + out * sph + np.array([0, 0, up_bias]))
    g = np.array([flutter[0], flutter[0], flutter[1], flutter[1]])
    if attach == "center":
        g = np.full(4, 0.5 * (flutter[0] + flutter[1]))
    col = np.zeros((4, 4))
    col[:, 0] = wind_rgb[0]
    col[:, 1] = g
    col[:, 2] = wind_rgb[2]
    col[:, 3] = ao
    md.add(corners, [(0, 1, 2, 3)], [uv], mat, col, normals=nn)


# ============================================================================ LOD helpers

def merge_cards(cards, n_out, tile_map, rng, size_gain=0.85, min_size=0.6, max_size=4.0):
    """k-means merge of card records -> fewer, larger cards using dense tiles.

    cards: list of dict(c, n, up, w, h, tile, wind(3), ao)."""
    if len(cards) <= n_out:
        return [dict(cc) for cc in cards]
    C = np.array([cc["c"] + cc["n"] * 0.0 for cc in cards])
    cent, lab = kmeans2(C, n_out, minit="++", seed=int(rng.integers(1 << 30)))
    out = []
    for k in range(n_out):
        idx = np.nonzero(lab == k)[0]
        if len(idx) == 0:
            continue
        grp = [cards[i] for i in idx]
        area = sum(g["w"] * g["h"] for g in grp)
        c = np.mean([g["c"] + g["up"] * g["h"] * 0.5 for g in grp], axis=0)
        nrm = normalize(np.sum([g["n"] for g in grp], axis=0))
        upv = normalize(np.sum([g["up"] for g in grp], axis=0) + rng.normal(0, 0.05, 3))
        spread = np.sqrt(np.mean(np.sum((np.array([g["c"] for g in grp]) - c) ** 2, axis=1)))
        size = np.clip(math.sqrt(area) * size_gain * 0.55 + spread * 1.1, min_size, max_size)
        tiles = [g["tile"] for g in grp]
        tile = max(set(tiles), key=tiles.count)
        tile = tile_map.get(tile, tile)
        wind = np.mean([g["wind"] for g in grp], axis=0)
        wind[2] = grp[0]["wind"][2]
        ao = float(np.mean([g["ao"] for g in grp]))
        out.append(dict(c=c, n=nrm, up=upv, w=size, h=size, tile=tile, wind=wind, ao=ao, attach="center"))
    return out


def emit_cards(md, cards, crown_c, mat=1, sph=0.65, up_bias=0.25):
    for cc in cards:
        card(md, cc["c"], cc["n"], cc["up"], cc["w"], cc["h"], cc["tile"], mat, cc["wind"], cc["ao"], crown_c,
             sph=sph, attach=cc.get("attach", atlas.LAYOUT[cc["tile"]]["attach"]), up_bias=up_bias,
             flutter=cc.get("flutter", (0.25, 1.0)), bend=cc.get("bend", 0.0))
