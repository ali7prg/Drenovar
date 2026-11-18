"""Hair cards for «Искра»: mane, forelock, tail, fetlock feathering (pure numpy).

Cards are strips that follow the body SDF at a small offset (mane/forelock lie on the skin,
tail hangs from the dock).  Every card maps to one vertical strip of the hair atlas
(u = strip, v = 1 at the root .. 0 at the tip); the atlas is drawn procedurally
(`hair_atlas`) as alpha-tested strands.  Weights: root follows the body bone, the rest of the
strand blends into its follow-through bone chain.
"""
import math

import cv2
import numpy as np

import horse_rig as HRig

V = lambda *a: np.array(a, float)  # noqa: E731

N_STRIPS = 8
STRIP = {"mane_dense": 0, "mane_wavy": 1, "mane_wisp": 2, "tail_a": 3, "tail_b": 4,
         "forelock": 5, "feather": 6, "tail_wisp": 7}


# --------------------------------------------------------------------------- atlas

def hair_atlas(size=1024, seed=11):
    """RGBA hair atlas (float, row 0 = top).  8 vertical strips, roots at the top."""
    rng = np.random.default_rng(seed)
    ss = 2
    W = H = size * ss
    sw = W // N_STRIPS
    col = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    base_dark = np.array([0.055, 0.040, 0.032])
    base_mid = np.array([0.13, 0.085, 0.060])
    high = np.array([0.30, 0.19, 0.12])
    params = {
        0: dict(n=420, len=(0.80, 1.00), wave=0.010, width=(1.4, 2.6), spread=0.85, high=0.25),
        1: dict(n=380, len=(0.70, 1.00), wave=0.030, width=(1.4, 2.4), spread=0.85, high=0.30),
        2: dict(n=220, len=(0.45, 0.95), wave=0.035, width=(1.0, 2.0), spread=0.95, high=0.30),
        3: dict(n=520, len=(0.85, 1.00), wave=0.018, width=(1.4, 2.6), spread=0.80, high=0.22),
        4: dict(n=460, len=(0.70, 1.00), wave=0.030, width=(1.2, 2.4), spread=0.90, high=0.28),
        5: dict(n=260, len=(0.65, 1.00), wave=0.020, width=(1.2, 2.2), spread=0.85, high=0.25),
        6: dict(n=240, len=(0.55, 1.00), wave=0.025, width=(1.0, 2.0), spread=0.95, high=0.18),
        7: dict(n=200, len=(0.40, 0.95), wave=0.040, width=(1.0, 1.8), spread=0.98, high=0.32),
    }
    for s in range(N_STRIPS):
        p = params[s]
        x0 = s * sw
        layer_c = np.zeros((H, sw, 3), np.float32)
        layer_a = np.zeros((H, sw), np.float32)
        for k in range(p["n"]):
            # strands fan slightly: start inside the root band, may drift sideways
            u0 = rng.uniform(0.5 - p["spread"] / 2, 0.5 + p["spread"] / 2) * sw
            L = rng.uniform(*p["len"]) * H
            drift = rng.normal(0, 0.06) * sw
            ph = rng.uniform(0, 2 * math.pi)
            freq = rng.uniform(2.0, 4.5)
            n = 40
            t = np.linspace(0, 1, n)
            y = t * L
            x = u0 + drift * t ** 1.5 + p["wave"] * sw * 6 * np.sin(ph + freq * math.pi * t) * t
            pts = np.stack([x, y], 1).astype(np.int32)
            w = int(round(rng.uniform(*p["width"]) * ss))
            r = rng.random()
            c = base_dark * (1 - r) + base_mid * r
            if rng.random() < p["high"]:
                c = c * 0.4 + high * rng.uniform(0.5, 1.0)
            pad = w + 2
            x0b = max(0, int(pts[:, 0].min()) - pad)
            x1b = min(sw, int(pts[:, 0].max()) + pad + 1)
            y1b = min(H, int(pts[:, 1].max()) + pad + 1)
            if x1b <= x0b:
                continue
            img_a = np.zeros((y1b, x1b - x0b), np.float32)
            cv2.polylines(img_a, [pts - np.array([x0b, 0])], False, 1.0, thickness=max(1, w),
                          lineType=cv2.LINE_AA)
            # taper: fade the last 25 % of each strand
            fade = np.clip((L - np.arange(y1b)) / (0.25 * L + 1e-6), 0, 1)[:, None]
            img_a *= fade
            sub_a = layer_a[:y1b, x0b:x1b]
            m = img_a > sub_a
            layer_c[:y1b, x0b:x1b][m] = c
            layer_a[:y1b, x0b:x1b] = np.maximum(sub_a, img_a)
        # root darkening + slight ambient occlusion toward the root
        grad = np.linspace(0.75, 1.05, H)[:, None, None]
        layer_c *= grad
        col[:, x0:x0 + sw] = layer_c
        cov[:, x0:x0 + sw] = layer_a
    # downsample (anti-alias), then bleed colour into transparent texels
    col = cv2.resize(col, (size, size), interpolation=cv2.INTER_AREA)
    cov = cv2.resize(cov, (size, size), interpolation=cv2.INTER_AREA)
    known = cov > 0.05
    filled = col.copy()
    if known.any():
        from scipy import ndimage as ndi
        idx = ndi.distance_transform_edt(~known, return_distances=False, return_indices=True)
        filled = col[idx[0], idx[1]]
    alpha = np.clip(cov * 1.6, 0, 1)
    return np.concatenate([filled, alpha[..., None]], -1)


def strip_u(index):
    u0 = index / N_STRIPS
    return u0 + 0.004, u0 + 1.0 / N_STRIPS - 0.004


# --------------------------------------------------------------------------- SDF helpers

class SurfaceGuide:
    """Trilinear SDF sampling + gradient on a frlib.sdf.Field (the body)."""

    def __init__(self, field):
        self.F = field

    def d(self, P):
        P = np.atleast_2d(P)
        return self.F.sample(P)

    def grad(self, P, h=0.006):
        P = np.atleast_2d(P)
        g = np.zeros_like(P)
        for i in range(3):
            e = np.zeros(3)
            e[i] = h
            g[:, i] = (self.d(P + e) - self.d(P - e)) / (2 * h)
        n = np.linalg.norm(g, axis=1, keepdims=True)
        return g / np.maximum(n, 1e-9)

    def project(self, P, offset):
        """Move points onto the iso-surface d = offset (few Newton steps)."""
        P = np.atleast_2d(P).copy()
        for _ in range(4):
            dd = self.d(P) - offset
            P -= self.grad(P) * dd[:, None]
        return P


# --------------------------------------------------------------------------- card builder

class CardSet:
    def __init__(self):
        self.verts, self.faces, self.uvs, self.groups = [], [], [], []
        self.weights = []      # per vertex: dict bone -> w
        self.n = 0

    def add_card(self, path, widths, normals, strip, weights, twist=0.0, flip=False,
                 v_range=(1.0, 0.0)):
        """path (N,3) root->tip, widths (N,), normals (N,3) card-plane normals."""
        N = len(path)
        tang = np.gradient(path, axis=0)
        tang /= np.maximum(np.linalg.norm(tang, axis=1, keepdims=True), 1e-9)
        side = np.cross(normals, tang)
        side /= np.maximum(np.linalg.norm(side, axis=1, keepdims=True), 1e-9)
        if twist:
            a = np.linspace(0, twist, N)[:, None]
            nrm = normals - (normals * tang).sum(1, keepdims=True) * tang
            nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
            side = side * np.cos(a) + nrm * np.sin(a)
        L = path - side * widths[:, None] * 0.5
        R = path + side * widths[:, None] * 0.5
        u0, u1 = strip_u(strip)
        if flip:
            u0, u1 = u1, u0
        vv = np.linspace(v_range[0], v_range[1], N)
        base = self.n
        for i in range(N):
            self.verts += [L[i], R[i]]
            self.weights += [weights[i], weights[i]]
        for i in range(N - 1):
            a, b, c, d = base + 2 * i, base + 2 * i + 1, base + 2 * i + 3, base + 2 * i + 2
            self.faces += [(a, b, c), (a, c, d)]
            self.uvs += [((u0, vv[i]), (u1, vv[i]), (u1, vv[i + 1])),
                         ((u0, vv[i]), (u1, vv[i + 1]), (u0, vv[i + 1]))]
        self.n += 2 * N

    def arrays(self):
        return (np.array(self.verts), np.array(self.faces, np.int64),
                np.array(self.uvs, float).reshape(-1, 2), self.weights)

    @property
    def tris(self):
        return len(self.faces)


def _blend(a, b, t):
    """Weight dict blend."""
    out = {}
    for k, v in a.items():
        out[k] = out.get(k, 0.0) + v * (1 - t)
    for k, v in b.items():
        out[k] = out.get(k, 0.0) + v * t
    return out


def _neck_bone_at(y):
    """Neck bone weights for a crest position (y along the neck)."""
    if y < -1.00:
        return {"neck_03": 0.7, "head": 0.3}
    if y < -0.90:
        return {"neck_03": 1.0}
    if y < -0.80:
        t = (y + 0.90) / 0.10
        return {"neck_03": 1 - t, "neck_02": t}
    if y < -0.68:
        t = (y + 0.80) / 0.12
        return {"neck_02": 1 - t, "neck_01": t}
    if y < -0.52:
        t = (y + 0.68) / 0.16
        return {"neck_01": 1 - t, "spine_03": t}
    return {"spine_03": 1.0}


def _mane_bone_at(y, s):
    roots = HRig.mane_roots()
    mids = [0.5 * (roots[i][1] + roots[i + 1][1]) for i in range(4)]
    names = [f"mane_{s}_{4 - i:02d}" for i in range(4)]
    if y <= mids[0]:
        return {names[0]: 1.0}
    if y >= mids[-1]:
        return {names[-1]: 1.0}
    for i in range(3):
        if mids[i] <= y <= mids[i + 1]:
            t = (y - mids[i]) / (mids[i + 1] - mids[i])
            return {names[i]: 1 - t, names[i + 1]: t}
    return {names[0]: 1.0}


# --------------------------------------------------------------------------- mane

def mane_cards(guide, lod=0, seed=3):
    rng = np.random.default_rng(seed + lod)
    cs = CardSet()
    crest = HRig.mane_roots()
    ys = np.array([p[1] for p in crest])
    zs = np.array([p[2] for p in crest])
    n_roots = {0: 30, 1: 18, 2: 8}[lod]
    segs = {0: 6, 1: 4, 2: 3}[lod]
    layers = {0: 2, 1: 2, 2: 1}[lod]
    for s, sx in (("L", 1.0), ("R", -1.0)):
        for li in range(layers):
            for k in range(n_roots):
                t = (k + rng.uniform(0.15, 0.85)) / n_roots
                y = np.interp(t, [0, 1], [ys[0] + 0.01, ys[-1] - 0.02])
                z = np.interp(y, ys[::-1], zs[::-1])
                root = guide.project(V(0.012 * sx, y, z + 0.06), 0.004)[0]
                # length profile: longest mid-neck, shorter at poll and withers
                tl = (y - ys[0]) / (ys[-1] - ys[0])
                length = (0.20 + 0.16 * math.sin(math.pi * min(1, max(0, tl * 1.05)))) * \
                    rng.uniform(0.85, 1.12) * (1.0 + 0.12 * li)
                # the right side carries more hair (front/rear views show the mane on -X)
                if s == "R":
                    length *= 1.12
                width = rng.uniform(0.060, 0.085) * (1.15 if lod == 2 else 1.0)
                off = 0.010 + 0.016 * li + rng.uniform(0, 0.006)
                path = _strand_on_surface(guide, root, V(sx * 0.75, 0.10, -0.66), length, segs,
                                          off, rng, sx)
                nrm = guide.grad(path)
                weights = []
                for i in range(len(path)):
                    f = i / (len(path) - 1)
                    w = _blend(_neck_bone_at(y), _mane_bone_at(y, s) if lod < 1 else
                               _neck_bone_at(y), min(1.0, f * 1.6))
                    weights.append(w)
                strip = [STRIP["mane_dense"], STRIP["mane_wavy"], STRIP["mane_wisp"]][
                    (k + li) % 3 if li == 1 else (k % 2)]
                cs.add_card(path, np.linspace(width, width * 0.8, len(path)), nrm, strip,
                            weights, twist=rng.normal(0, 0.15), flip=bool(rng.integers(2)))
    # crest ridge: short standing cards that give the mane volume from the front/top
    n_crest = {0: 16, 1: 9, 2: 0}[lod]
    for k in range(n_crest):
        t = (k + 0.5) / max(n_crest, 1)
        y = np.interp(t, [0, 1], [ys[0], ys[-1] - 0.03])
        z = np.interp(y, ys[::-1], zs[::-1])
        root = guide.project(V(0.0, y, z + 0.06), 0.002)[0]
        for sx in (1.0, -1.0):
            d = V(sx * 0.55, 0.15, 0.25)
            d /= np.linalg.norm(d)
            L = rng.uniform(0.08, 0.13)
            path = np.array([root + d * L * f + V(sx * 0.02, 0, -0.03) * f * f for f in
                             np.linspace(0, 1, 3)])
            nrm = np.tile(V(0, 1, 0), (3, 1))
            s = "L" if sx > 0 else "R"
            w = [_blend(_neck_bone_at(y), _mane_bone_at(y, s) if lod < 1 else _neck_bone_at(y),
                        f) for f in (0, 0.5, 1)]
            cs.add_card(path, np.array([0.07, 0.065, 0.05]), nrm, STRIP["mane_wisp"], w)
    return cs


def _strand_on_surface(guide, root, d0, length, segs, offset, rng, sx, stiff=0.55):
    """March a strand from `root` along the skin (kept at `offset`), gravity pulls it down."""
    step = length / segs
    p = root.copy()
    d = d0 / np.linalg.norm(d0)
    pts = [p.copy()]
    wav = rng.uniform(0.3, 0.9)
    ph = rng.uniform(0, 6.28)
    for i in range(segs):
        g = V(0.0, 0.08, -1.0)
        d = stiff * d + (1 - stiff) * g / np.linalg.norm(g)
        d += V(0, math.sin(ph + i * 1.3) * 0.12 * wav, 0)
        d /= np.linalg.norm(d)
        q = p + d * step
        dd = guide.d(q)[0] - offset
        if dd < 0 or dd > 0.02:      # stay on (and close to) the skin
            q = guide.project(q, offset + min(max(dd, 0.0), 0.02) * 0.4)[0]
        d = (q - p) / max(np.linalg.norm(q - p), 1e-9)
        p = q
        pts.append(p.copy())
    return np.array(pts)


# --------------------------------------------------------------------------- forelock

def forelock_cards(guide, lod=0, seed=5):
    rng = np.random.default_rng(seed)
    cs = CardSet()
    n = {0: 7, 1: 4, 2: 2}[lod]
    segs = {0: 4, 1: 3, 2: 2}[lod]
    for k in range(n):
        x = (k / max(n - 1, 1) - 0.5) * 0.09
        root = guide.project(V(x, -1.17, 1.97), 0.004)[0]
        # fall forward/down over the forehead; parted so the star stays visible
        d0 = V(x * 1.2, -0.75, -0.45)
        length = rng.uniform(0.11, 0.16)
        path = _strand_on_surface(guide, root, d0, length, segs, 0.006, rng, 1.0, stiff=0.75)
        nrm = guide.grad(path)
        w = [_blend({"head": 1.0}, {"forelock": 1.0} if lod < 1 else {"head": 1.0},
                    i / (len(path) - 1)) for i in range(len(path))]
        cs.add_card(path, np.linspace(0.05, 0.035, len(path)), nrm, STRIP["forelock"], w,
                    twist=rng.normal(0, 0.2))
    return cs


# --------------------------------------------------------------------------- tail

def _tail_center(t):
    """Tail centre line (root t=0 at the dock, t=1 tip) as a smooth curve."""
    pts = HRig.tail_points()[1:]
    pts = np.array(pts)
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    s /= s[-1]
    return np.stack([np.interp(t, s, pts[:, i]) for i in range(3)], -1)


def _tail_weights(p):
    """Weights along the tail bone chain from the nearest point on the chain."""
    tp = np.array(HRig.tail_points())
    best = None
    for i in range(6):
        a, b = tp[i], tp[i + 1]
        ab = b - a
        t = np.clip((p - a) @ ab / (ab @ ab), 0, 1)
        dist = np.linalg.norm(a + ab * t - p)
        if best is None or dist < best[0]:
            best = (dist, i, t)
    _, i, t = best
    names = [f"tail_{k + 1:02d}" for k in range(6)]
    if t < 0.5 and i > 0:
        return {names[i - 1]: 0.5 - t, names[i]: 0.5 + t}
    if t >= 0.5 and i < 5:
        return {names[i]: 1.5 - t, names[i + 1]: t - 0.5}
    return {names[i]: 1.0}


def tail_cards(lod=0, seed=7, drop=None):
    rng = np.random.default_rng(seed)
    cs = CardSet()
    n_ang = {0: 18, 1: 11, 2: 6}[lod]
    rings = {0: 2, 1: 2, 2: 1}[lod]
    segs = {0: 11, 1: 7, 2: 4}[lod]
    for r in range(rings):
        for k in range(n_ang):
            ang = 2 * math.pi * (k + 0.5 * r + rng.uniform(-0.2, 0.2)) / n_ang
            t0 = rng.uniform(0.0, 0.10) + 0.10 * r
            t1 = rng.uniform(0.88, 1.0) if r == 0 else rng.uniform(0.80, 0.97)
            ts = np.linspace(t0, t1, segs + 1)
            c = _tail_center(ts)
            # cross-section radius: hugs the dock, bulges mid-length, gathers to the tip
            rad = (0.045 + 0.075 * np.sin(np.pi * np.clip(ts * 1.15, 0, 1)) ** 0.8) * \
                rng.uniform(0.8, 1.1) * (0.75 if r == 1 else 1.0)
            # flatten laterally (tail is narrower from behind than from the side)
            ox = np.cos(ang) * rad * 0.82
            oy = np.sin(ang) * rad * 1.05
            wav = rng.uniform(0.006, 0.02)
            ph = rng.uniform(0, 6.28)
            path = c + np.stack([ox + wav * np.sin(ph + ts * 9), oy + 0.6 * wav * np.cos(ph + ts * 7),
                                 np.zeros_like(ts)], -1)
            # card plane tangent to the cross-section circle
            nrm = np.stack([np.cos(ang) * np.ones_like(ts), np.sin(ang) * np.ones_like(ts),
                            np.zeros_like(ts)], -1)
            width = rng.uniform(0.07, 0.10) * np.linspace(1.0, 1.25, len(ts))
            w = [_tail_weights(p) for p in path]
            if drop:
                w = [{HRig.resolve(b, drop): v for b, v in ww.items()} for ww in w]
            strip = [STRIP["tail_a"], STRIP["tail_b"], STRIP["tail_wisp"]][(k + r) % 3]
            cs.add_card(path, width, nrm, strip, w, twist=rng.normal(0, 0.3),
                        flip=bool(rng.integers(2)))
    return cs


# --------------------------------------------------------------------------- feathering

def feather_cards(J, lod=0, seed=9):
    if lod >= 2:
        return CardSet()
    rng = np.random.default_rng(seed)
    cs = CardSet()
    n = {0: 6, 1: 3}[lod]
    for fh, legs in (("F", ("L", "R")), ("H", ("L", "R"))):
        for s in legs:
            sx = 1.0 if s == "L" else -1.0
            fet = J[f"fetlock_{fh}_{s}"]
            bone = f"pastern_{fh}_{s}"
            for k in range(n):
                ang = math.pi * (0.15 + 0.7 * k / max(n - 1, 1))   # around the back half
                ox = math.cos(ang) * 0.07 * sx
                oy = math.sin(ang) * 0.075
                root = fet + V(ox, oy + 0.015, 0.05)
                tip = fet + V(ox * 1.25, oy * 1.15 + 0.03, -0.14 + rng.uniform(-0.02, 0.02))
                path = np.array([root + (tip - root) * f + V(0, 0.02, 0) * math.sin(math.pi * f)
                                 for f in np.linspace(0, 1, 4)])
                nrm = np.tile(V(math.cos(ang) * sx, math.sin(ang), 0.0), (4, 1))
                w = [{bone: 1.0}] * 4
                cs.add_card(path, np.array([0.06, 0.06, 0.055, 0.045]), nrm, STRIP["feather"], w,
                            flip=bool(rng.integers(2)))
    return cs
