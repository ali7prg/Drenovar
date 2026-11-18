"""Halter (leather straps swept on the head surface, brass rings, buckle) and the knotted green
ribbon of «Искра» — pure numpy geometry + procedural tack atlas.

Atlas (1024², row 0 = top): v in [0.5,1] leather straps (u = length, 1 m per atlas width),
v in [0.375,0.5) brass, v in [0,0.375) green ribbon cloth.
"""
import math

import numpy as np

import horse_rig as HRig

V = lambda *a: np.array(a, float)  # noqa: E731

STRAP_W = 0.026
STRAP_T = 0.005
OFFSET = 0.0065


# --------------------------------------------------------------------------- geometry container

class Geo:
    def __init__(self):
        self.v, self.f, self.uv, self.w = [], [], [], []
        self.n = 0

    def quad(self, a, b, c, d, uvs, wts):
        """a,b,c,d vertex positions (CCW from outside); uvs 4 tuples; wts 4 dicts."""
        base = self.n
        self.v += [a, b, c, d]
        self.w += list(wts)
        self.n += 4
        self.f += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
        self.uv += [uvs[0], uvs[1], uvs[2], uvs[0], uvs[2], uvs[3]]

    def tri(self, a, b, c, uvs, wts):
        base = self.n
        self.v += [a, b, c]
        self.w += list(wts)
        self.n += 3
        self.f += [(base, base + 1, base + 2)]
        self.uv += [uvs[0], uvs[1], uvs[2]]

    def extend(self, other):
        off = self.n
        self.v += other.v
        self.w += other.w
        self.uv += other.uv
        self.f += [(a + off, b + off, c + off) for a, b, c in other.f]
        self.n += other.n

    @property
    def tris(self):
        return len(self.f)

    def arrays(self):
        return np.array(self.v), np.array(self.f, np.int64), np.array(self.uv, float), self.w


# --------------------------------------------------------------------------- paths

def _resample(ctrl, step, closed=False):
    """Catmull-Rom through control points, resampled at ~`step` metres."""
    P = np.array(ctrl, float)
    if closed:
        P = np.vstack([P[-1], P, P[0], P[1]])
    else:
        P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    dense = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, 12, endpoint=False):
            t2, t3 = t * t, t * t * t
            dense.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                                (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    dense.append(P[-2] if not closed else P[1])
    dense = np.array(dense)
    seg = np.linalg.norm(np.diff(dense, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    n = max(2, int(round(s[-1] / step)) + 1)
    si = np.linspace(0, s[-1], n)
    return np.stack([np.interp(si, s, dense[:, k]) for k in range(3)], -1), s[-1]


def _push_out(guide, P, offset):
    """Points closer than `offset` to the skin are pushed out; straps may bridge hollows."""
    P = P.copy()
    for _ in range(4):
        d = guide.d(P) - offset
        m = d < 0
        if not m.any():
            break
        P[m] -= guide.grad(P[m]) * d[m, None]
    return P


def halter_paths():
    """Left-side control points mirrored; returns {name: (ctrl, closed, width)}."""
    A = V(0.106, -1.098, 1.735)          # cheek ring (behind/below the eye)
    B = V(0.090, -1.282, 1.552)          # noseband ring
    T = HRig.throat_ring()               # throat ring with the ribbon
    m = lambda p: V(-p[0], p[1], p[2])   # noqa: E731
    paths = {
        "crown": ([A + V(0, 0, -0.006), A + V(0, 0, 0.025), V(0.100, -1.104, 1.84), V(0.074, -1.110, 1.925),
                   V(0.0, -1.112, 1.962), m(V(0.074, -1.110, 1.925)), m(V(0.100, -1.104, 1.84)),
                   m(A + V(0, 0, 0.025)), m(A + V(0, 0, -0.006))], False, STRAP_W),
        "cheek_L": ([A + V(0, -0.012, -0.012), V(0.102, -1.19, 1.648), B + V(0, 0.012, 0.012)],
                    False, STRAP_W * 0.95),
        "cheek_R": ([m(A) + V(0, -0.012, -0.012), m(V(0.102, -1.19, 1.648)),
                     m(B) + V(0, 0.012, 0.012)], False, STRAP_W * 0.95),
        "nose": ([B, V(0.080, -1.355, 1.578), V(0.052, -1.428, 1.603), V(0.0, -1.458, 1.612),
                  m(V(0.052, -1.428, 1.603)), m(V(0.080, -1.355, 1.578)), m(B),
                  m(V(0.070, -1.300, 1.480)), V(0.0, -1.300, 1.452), V(0.070, -1.300, 1.480)],
                 True, STRAP_W * 1.08),
        "throat": ([A + V(0, 0.01, -0.02), V(0.092, -1.075, 1.62), T, V(0.0, -1.075, 1.488),
                    m(V(0.06, -1.07, 1.53)), m(V(0.088, -1.072, 1.64)),
                    m(A + V(0, 0.01, -0.02))], False, STRAP_W * 0.9),
        "jaw": ([T + V(-0.02, -0.02, -0.008), V(0.03, -1.17, 1.468), V(0.0, -1.27, 1.452)], False,
                STRAP_W * 0.85),
    }
    rings = {"ring_A_L": A, "ring_A_R": m(A), "ring_B_L": B, "ring_B_R": m(B), "ring_T": T}
    return paths, rings


# --------------------------------------------------------------------------- straps

def strap(geo, guide, ctrl, closed, width, step, u0, weight_fn, thick=STRAP_T):
    P, length = _resample(ctrl, step, closed)
    P = _push_out(guide, P, OFFSET)
    N = len(P)
    tang = np.gradient(P, axis=0)
    if closed:
        tang = np.roll(P, -1, 0) - np.roll(P, 1, 0)
    tang /= np.maximum(np.linalg.norm(tang, axis=1, keepdims=True), 1e-9)
    nrm = guide.grad(P)
    side = np.cross(nrm, tang)
    side /= np.maximum(np.linalg.norm(side, axis=1, keepdims=True), 1e-9)
    nrm = np.cross(tang, side)
    hw, ht = width * 0.5, thick * 0.5
    corners = [P + side * hw + nrm * ht, P - side * hw + nrm * ht, P - side * hw - nrm * ht,
               P + side * hw - nrm * ht]
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    us = u0 + s / 1.0
    # v bands of the leather region: top face, edge, under face, edge
    bands = [(0.76, 0.97), (0.735, 0.755), (0.53, 0.73), (0.735, 0.755)]
    rng_i = range(N if closed else N - 1)
    for i in rng_i:
        j = (i + 1) % N
        uj = us[j] if j > i else us[i] + np.linalg.norm(P[j] - P[i])
        for k in range(4):
            a, b = corners[k], corners[(k + 1) % 4]
            v0, v1 = bands[k]
            wi, wj = weight_fn(P[i]), weight_fn(P[j])
            geo.quad(a[i], a[j], b[j], b[i], [(us[i], v0), (uj, v0), (uj, v1), (us[i], v1)],
                     [wi, wj, wj, wi])
    return length


def ring(geo, center, axis, R=0.021, r=0.0042, seg=12, sides=5, weight=None):
    axis = axis / np.linalg.norm(axis)
    a = np.cross(axis, V(0, 0, 1))
    if np.linalg.norm(a) < 1e-3:
        a = np.cross(axis, V(1, 0, 0))
    a /= np.linalg.norm(a)
    b = np.cross(axis, a)
    w = weight or {"head": 1.0}

    def pt(i, k):
        t = 2 * math.pi * i / seg
        p = 2 * math.pi * k / sides
        c = center + (a * math.cos(t) + b * math.sin(t)) * R
        radial = (a * math.cos(t) + b * math.sin(t))
        return c + (radial * math.cos(p) + axis * math.sin(p)) * r

    for i in range(seg):
        for k in range(sides):
            u0, u1 = i / seg, (i + 1) / seg
            v0, v1 = 0.385 + 0.1 * k / sides, 0.385 + 0.1 * (k + 1) / sides
            geo.quad(pt(i, k), pt(i + 1, k), pt(i + 1, k + 1), pt(i, k + 1),
                     [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], [w] * 4)


def box(geo, c, ax, ay, az, size, weight, vband=(0.39, 0.49)):
    """Axis-frame box (brass buckle bars)."""
    hx, hy, hz = np.asarray(size) * 0.5
    pts = [c + sx * hx * ax + sy * hy * ay + sz * hz * az for sx in (-1, 1) for sy in (-1, 1)
           for sz in (-1, 1)]
    F = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    for q in F:
        geo.quad(pts[q[0]], pts[q[1]], pts[q[2]], pts[q[3]],
                 [(0.1, vband[0]), (0.2, vband[0]), (0.2, vband[1]), (0.1, vband[1])], [weight] * 4)


def halter(guide, lod=0):
    geo = Geo()
    paths, rings = halter_paths()
    step = {0: 0.024, 1: 0.045, 2: 0.08}[lod]
    head = {"head": 1.0}

    def wfn(p):
        # straps under the jaw follow the jaw a little (neigh mouth opening)
        if p[2] < 1.50 and p[1] < -1.15 and lod < 2:
            return {"head": 0.6, "jaw": 0.4}
        return head

    u = 0.0
    for name, (ctrl, closed, width) in paths.items():
        L = strap(geo, guide, ctrl, closed, width, step, u, wfn)
        u = (u + L + 0.05) % 0.5
    if lod < 2:
        seg, sides = (12, 5) if lod == 0 else (8, 4)
        for name, c in rings.items():
            c2 = _push_out(guide, c[None], OFFSET + 0.004)[0]
            n = guide.grad(c2[None])[0]
            R = 0.025 if name == "ring_T" else (0.018 if name.startswith("ring_A") else 0.020)
            ring(geo, c2, n, R=R, seg=seg, sides=sides, weight=head)
    if lod == 0:
        # buckle on the left cheek piece of the crownpiece
        c = _push_out(guide, V(0.092, -1.107, 1.885)[None], OFFSET + 0.004)[0]
        n = guide.grad(c[None])[0]
        up = V(0, 0, 1) - n * n[2]
        up /= np.linalg.norm(up)
        sd = np.cross(n, up)
        for dz, dw, (sx, sy) in ((0.018, 0.0, (0.036, 0.006)), (-0.018, 0.0, (0.036, 0.006))):
            box(geo, c + up * dz, sd, up, n, (sx, sy, 0.005), head)
        for dsd in (-0.018, 0.018):
            box(geo, c + sd * dsd, sd, up, n, (0.006, 0.042, 0.005), head)
        box(geo, c + n * 0.002, sd, up, n, (0.004, 0.034, 0.004), head)   # tongue
    return geo


# --------------------------------------------------------------------------- ribbon

def ribbon(lod=0, seed=4):
    """Knot on the throat ring + three hanging cloth tails with pointed ends (double-sided)."""
    rng = np.random.default_rng(seed)
    geo = Geo()
    T = HRig.throat_ring()
    rp = HRig.ribbon_points()
    # knot: small bunched ellipsoid (cloth wrapped around the ring bottom)
    kc = T + V(0.004, -0.002, -0.022)
    nu, nv = ({0: (8, 5), 1: (6, 4), 2: (5, 3)})[lod]
    rx, ry, rz = 0.017, 0.016, 0.022

    def kp(i, j):
        th = 2 * math.pi * i / nu
        ph = math.pi * j / nv
        bump = 1.0 + 0.12 * math.sin(3 * th + 1.0) * math.sin(ph)
        return kc + V(rx * math.sin(ph) * math.cos(th) * bump, ry * math.sin(ph) * math.sin(th) * bump,
                      rz * math.cos(ph))

    kw = {"ribbon_01": 0.5, "head": 0.5} if lod < 2 else {"head": 1.0}
    for i in range(nu):
        for j in range(nv):
            geo.quad(kp(i, j), kp(i, j + 1), kp(i + 1, j + 1), kp(i + 1, j),
                     [(0.62 + 0.3 * i / nu, 0.30 - 0.25 * j / nv),
                      (0.62 + 0.3 * i / nu, 0.30 - 0.25 * (j + 1) / nv),
                      (0.62 + 0.3 * (i + 1) / nu, 0.30 - 0.25 * (j + 1) / nv),
                      (0.62 + 0.3 * (i + 1) / nu, 0.30 - 0.25 * j / nv)], [kw] * 4)
    tails = [(0.215, V(0.012, -0.010, 0), 0.30), (0.235, V(-0.004, 0.012, 0), -0.25),
             (0.170, V(0.020, 0.010, 0), 0.55)]
    if lod == 2:
        tails = tails[:2]
    segs = {0: 6, 1: 4, 2: 3}[lod]
    for ti, (L, spread, twist) in enumerate(tails):
        width = 0.056 if ti < 2 else 0.048
        top = kc + V(0, 0, -0.012) + spread * 0.4
        pts = []
        for k in range(segs + 1):
            f = k / segs
            p = top + V(spread[0] * f * 1.4 + 0.004 * math.sin(f * 5 + ti),
                        spread[1] * f * 1.4 + 0.006 * f, -L * f)
            pts.append(p)
        pts = np.array(pts)
        u0 = 0.05 + 0.19 * ti
        for k in range(segs):
            f0, f1 = k / segs, (k + 1) / segs
            a0 = twist * f0 + 0.5 * ti
            a1 = twist * f1 + 0.5 * ti
            d0 = V(math.cos(a0), math.sin(a0), 0) * width * (1 - 0.15 * f0) * 0.5
            d1 = V(math.cos(a1), math.sin(a1), 0) * width * (1 - 0.15 * f1) * 0.5
            w0 = _ribbon_w(pts[k], rp, lod)
            w1 = _ribbon_w(pts[k + 1], rp, lod)
            v0, v1 = 0.36 - 0.34 * f0, 0.36 - 0.34 * f1
            if k < segs - 1:
                geo.quad(pts[k] - d0, pts[k] + d0, pts[k + 1] + d1, pts[k + 1] - d1,
                         [(u0, v0), (u0 + 0.16, v0), (u0 + 0.16, v1), (u0, v1)], [w0, w0, w1, w1])
            else:   # V-cut pointed end
                tip = pts[k + 1]
                mid = pts[k] + (pts[k + 1] - pts[k]) * 0.45
                geo.quad(pts[k] - d0, pts[k] + d0, mid + d1 * 0.9, mid - d1 * 0.9,
                         [(u0, v0), (u0 + 0.16, v0), (u0 + 0.16, v1 + 0.02), (u0, v1 + 0.02)],
                         [w0, w0, w1, w1])
                geo.tri(mid - d1 * 0.9, mid + d1 * 0.9, tip,
                        [(u0, v1 + 0.02), (u0 + 0.16, v1 + 0.02), (u0 + 0.08, v1)], [w1, w1, w1])
    return geo


def _ribbon_w(p, rp, lod):
    if lod >= 2:
        return {"head": 1.0}
    z = p[2]
    z0, z1, z2 = rp[1][2], rp[2][2], rp[3][2]
    if lod == 1:
        return {"ribbon_01": 1.0}
    if z >= z0:
        t = np.clip((rp[0][2] - z) / max(rp[0][2] - z0, 1e-6), 0, 1)
        return {"ribbon_01": 1.0} if t > 0.5 else {"ribbon_01": 0.7, "head": 0.3}
    if z >= z1:
        t = (z0 - z) / (z0 - z1)
        return {"ribbon_01": 1 - t, "ribbon_02": t}
    t = np.clip((z1 - z) / (z1 - z2), 0, 1)
    return {"ribbon_02": 1 - t, "ribbon_03": t}


# --------------------------------------------------------------------------- atlas

def tack_atlas(size=1024, seed=21):
    """Returns (colour RGB, orm RGB, height) float images (row 0 = top)."""
    import cv2
    from frlib import texproj
    rng = np.random.default_rng(seed)
    H = W = size
    yy, xx = np.mgrid[0:H, 0:W] / float(size)
    P = np.stack([xx * 6, yy * 6, np.zeros_like(xx)], -1)
    n1 = texproj.fbm(P, 3.0, 5, seed=seed)
    n2 = texproj.fbm(P, 24.0, 3, seed=seed + 5)
    col = np.zeros((H, W, 3))
    orm = np.zeros((H, W, 3))
    hgt = np.zeros((H, W))
    v = 1.0 - yy
    # leather (v >= 0.5): worn brown with darker edges, light stitching near both edges
    lea = v >= 0.5
    base = np.array([0.30, 0.20, 0.135])
    worn = np.array([0.46, 0.34, 0.24])
    t = np.clip((n1 - 0.45) * 2.2, 0, 1)[..., None]
    c = base * (1 - t) + worn * t
    c *= (0.85 + 0.3 * n2)[..., None]
    # bands: top face 0.76-0.97, edges 0.735-0.755, under 0.53-0.73
    for v0, v1 in ((0.76, 0.97), (0.53, 0.73)):
        band = (v >= v0) & (v <= v1)
        f = (v - v0) / (v1 - v0)
        edge = np.minimum(f, 1 - f)
        dark = np.clip(1 - edge / 0.12, 0, 1)
        c = np.where(band[..., None], c * (1 - 0.35 * dark[..., None]), c)
        # stitches: dashes along lines at 18 % from each edge
        for sl in (0.2, 0.8):
            line = np.abs(f - sl) < 0.035
            dash = (np.mod(xx * 120, 1.0) < 0.55)
            st = band & line & dash
            c[st] = np.array([0.58, 0.48, 0.34]) * (0.85 + 0.2 * n2[st, None])
            hgt[st] += 0.6
        hgt[band] += (0.4 * n2[band] + 0.25 * (1 - dark[band]))
    edgeband = (v > 0.73) & (v < 0.76)
    c[edgeband] *= 0.6
    col[lea] = c[lea]
    orm[lea] = np.stack([np.ones(lea.sum()), 0.58 + 0.12 * n2[lea], np.zeros(lea.sum())], -1)
    # brass (0.375 <= v < 0.5): aged bronze/brass with patina in cavities
    br = (v >= 0.375) & (v < 0.5)
    bc = np.array([0.74, 0.57, 0.28]) * (0.8 + 0.35 * n1)[..., None]
    pat = np.clip((n2 - 0.6) * 3, 0, 1)[..., None]
    bc = bc * (1 - 0.45 * pat) + np.array([0.33, 0.36, 0.24]) * 0.45 * pat
    col[br] = bc[br]
    orm[br] = np.stack([np.ones(br.sum()), 0.30 + 0.25 * pat[br, 0], np.ones(br.sum()) * 0.95], -1)
    # ribbon cloth (v < 0.375): muted emerald with weave and soft fold shading
    rb = v < 0.375
    weave = 0.5 + 0.25 * np.sin(xx * size * 1.3) * np.sin(yy * size * 1.3)
    fold = 0.85 + 0.15 * np.sin(xx * 40 + n1 * 6)
    gc = np.array([0.20, 0.31, 0.18]) * (fold * (0.9 + 0.2 * weave) * (0.85 + 0.3 * n1))[..., None]
    col[rb] = gc[rb]
    orm[rb] = np.stack([np.ones(rb.sum()), 0.86 * np.ones(rb.sum()), np.zeros(rb.sum())], -1)
    hgt[rb] = 0.3 * weave[rb] + 0.4 * fold[rb]
    col = np.clip(col, 0, 1)
    return col, orm, hgt
