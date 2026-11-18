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
    """RGBA strand atlas (float, row 0 = top), 8 vertical strips, roots at the top.

    Each strip is a hair *clump*: strands are dense near the root and separate into
    individual tapered strands toward the tip, so the 0.5 alpha test leaves real gaps.
    Colours: dark brown 0.10-0.22 with warm highlight strands (not black).
    """
    rng = np.random.default_rng(seed)
    ss = 2
    W = H = size * ss
    sw = W // N_STRIPS
    col = np.zeros((H, W, 3), np.float32)
    cov = np.zeros((H, W), np.float32)
    # palette sampled from the sheet's mane/tail pixels (horse_tex.sheet_palette)
    dark = np.array([0.17, 0.12, 0.09])
    mid = np.array([0.27, 0.19, 0.14])
    warm = np.array([0.45, 0.32, 0.22])
    #        strands, length range, waviness, width px@2x, root spread, tip spread, highlights
    params = {
        0: dict(n=230, len=(0.55, 1.00), wave=0.08, width=(3, 5), root=0.80, tip=1.00, high=0.30),
        1: dict(n=150, len=(0.50, 1.00), wave=0.15, width=(3, 5), root=0.75, tip=1.10, high=0.35),
        2: dict(n=90, len=(0.45, 0.95), wave=0.16, width=(3, 4), root=0.70, tip=1.15, high=0.35),
        3: dict(n=200, len=(0.75, 1.00), wave=0.07, width=(3, 5), root=0.80, tip=1.00, high=0.28),
        4: dict(n=140, len=(0.65, 1.00), wave=0.13, width=(3, 5), root=0.75, tip=1.10, high=0.32),
        5: dict(n=110, len=(0.60, 1.00), wave=0.06, width=(3, 4), root=0.75, tip=1.00, high=0.30),
        6: dict(n=80, len=(0.50, 1.00), wave=0.08, width=(3, 4), root=0.80, tip=1.20, high=0.25),
        7: dict(n=80, len=(0.40, 0.95), wave=0.14, width=(2, 4), root=0.70, tip=1.25, high=0.40),
    }
    for s in range(N_STRIPS):
        p = params[s]
        x0 = s * sw
        layer_c = np.zeros((H, sw, 3), np.float32)
        layer_a = np.zeros((H, sw), np.float32)
        for k in range(p["n"]):
            u_root = (0.5 + rng.uniform(-0.5, 0.5) * p["root"]) * sw
            u_tip = (0.5 + rng.uniform(-0.5, 0.5) * p["tip"]) * sw
            L = rng.uniform(*p["len"]) * H
            ph = rng.uniform(0, 2 * math.pi)
            freq = rng.uniform(1.2, 2.8)
            n = 48
            t = np.linspace(0, 1, n)
            y = t * L
            x = u_root + (u_tip - u_root) * t ** 1.3 + p["wave"] * sw * np.sin(ph + freq * math.pi * t) * t
            pts = np.stack([np.clip(x, 0, sw - 1), y], 1).astype(np.int32)
            w0 = int(rng.integers(p["width"][0], p["width"][1] + 1))
            r = rng.random()
            c = dark * (1 - r) + mid * r
            if rng.random() < p["high"]:
                c = mid * 0.5 + warm * rng.uniform(0.55, 1.0)
            y1b = min(H, int(pts[:, 1].max()) + 8)
            img_a = np.zeros((y1b, sw), np.float32)
            # tapered strand: draw thick root half and thinner tip half
            half = n // 2
            cv2.polylines(img_a, [pts[:half + 1]], False, 1.0, thickness=w0, lineType=cv2.LINE_AA)
            cv2.polylines(img_a, [pts[half:]], False, 1.0, thickness=max(2, w0 - 1),
                          lineType=cv2.LINE_AA)
            fade = np.clip((L - np.arange(y1b)) / (0.18 * L + 1e-6), 0, 1)[:, None]
            img_a *= fade
            sub_a = layer_a[:y1b]
            m = img_a > sub_a * 0.9
            layer_c[:y1b][m] = c
            layer_a[:y1b] = np.maximum(sub_a, img_a)
        # root shading (hair is darker close to the skin)
        grad = (0.72 + 0.33 * np.linspace(0, 1, H) ** 0.6)[:, None, None]
        layer_c *= grad
        col[:, x0:x0 + sw] = layer_c
        cov[:, x0:x0 + sw] = layer_a
    col = cv2.resize(col, (size, size), interpolation=cv2.INTER_AREA)
    cov = cv2.resize(cov, (size, size), interpolation=cv2.INTER_AREA)
    known = cov > 0.05
    filled = col.copy()
    if known.any():
        from scipy import ndimage as ndi
        idx = ndi.distance_transform_edt(~known, return_distances=False, return_indices=True)
        filled = col[idx[0], idx[1]]
    alpha = np.clip(cov * 1.25, 0, 1)
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

MANE_BOTTOM = ([-1.10, -0.95, -0.80, -0.62, -0.45, -0.30], [1.86, 1.67, 1.555, 1.495, 1.50, 1.53])


def _crest_point(guide, y, sx=0.0, lift=0.0):
    """Top of the neck at (x, y): march down a vertical ray until the skin (robust root)."""
    x = 0.012 * sx
    zs = np.arange(2.08, 1.30, -0.004)
    P = np.stack([np.full_like(zs, x), np.full_like(zs, y), zs], 1)
    d = guide.d(P) - (0.003 + lift)
    i = int(np.argmax(d <= 0)) if np.any(d <= 0) else len(zs) - 1
    return P[i]


def mane_lock_cards(guide, lod=0, seed=3):
    """Strand-lock cards over the opaque mane underlayer (iter12 layout, kept for the
    strand look); the underlayer blocks see-through so the rear view reads as one mass."""
    rng = np.random.default_rng(seed + lod)
    cs = CardSet()
    y_poll, y_with = -1.115, -0.36
    segs = {0: 6, 1: 4, 2: 3}[lod]
    layers = {0: [(40, 0.006, 1.0, "mane_dense"), (30, 0.013, 1.06, "mane_wavy"),
                  (16, 0.020, 1.10, "mane_wisp")],
              1: [(22, 0.010, 1.0, "mane_dense"), (16, 0.022, 1.1, "mane_wavy")],
              2: [(11, 0.014, 1.05, "mane_dense")]}[lod]
    for s, sx in (("L", 1.0), ("R", -1.0)):
        for li, (n_roots, off, lmul, strip_name) in enumerate(layers):
            for k in range(n_roots):
                t = (k + rng.uniform(0.1, 0.9)) / n_roots
                y = y_poll + (y_with - y_poll) * t
                root = _crest_point(guide, y, sx)
                # length: reach the sheet's mane-bottom line (curving over the crest), irregular
                bottom = float(np.interp(y, *MANE_BOTTOM))
                length = max(0.12, (root[2] - bottom) * 1.32) * lmul * rng.uniform(0.75, 1.18)
                # the mane falls mainly to the horse's right (front/rear views of the sheet)
                length *= 1.10 if s == "R" else 0.88
                width = rng.uniform(0.050, 0.072) * (1.25 if lod == 2 else 1.0)
                d0 = V(sx * (0.85 if s == "R" else 0.6), rng.uniform(0.0, 0.15), 0.02)
                path = _strand_on_surface(guide, root, d0, length, segs,
                                          off if s == "R" else off * 0.7, rng, sx, stiff=0.50,
                                          off_gain=(0.008 + 0.004 * li) * (1.0 if s == "R" else 0.6))
                keep = path[:, 2] > bottom - 0.07
                keep[:2] = True
                path = path[:max(2, int(np.argmin(keep)) if not keep.all() else len(path))]
                if len(path) < 2:
                    continue
                nrm = guide.grad(path)
                weights = []
                for i in range(len(path)):
                    f = i / (len(path) - 1)
                    w = _blend(_neck_bone_at(y), _mane_bone_at(y, s) if lod < 1 else
                               _neck_bone_at(y), min(1.0, f * 1.5))
                    weights.append(w)
                cs.add_card(path, np.linspace(width, width * 0.85, len(path)), nrm,
                            STRIP[strip_name], weights, twist=rng.normal(0, 0.35),
                            flip=bool(rng.integers(2)))
    # crest volume: arching cards from the midline over to each side (mass above the crest)
    n_crest = {0: 9, 1: 5, 2: 0}[lod]
    for k in range(n_crest):
        t = (k + rng.uniform(0.2, 0.8)) / max(n_crest, 1)
        y = y_poll + (y_with + 0.05 - y_poll) * t
        root = _crest_point(guide, y, 0.0)
        for sx in (1.0, -1.0):
            s = "L" if sx > 0 else "R"
            up = 0.012 + 0.012 * math.sin(math.pi * t)
            L = rng.uniform(0.06, 0.09)
            f = np.linspace(0, 1, 4)
            path = np.array([root + V(sx * L * 0.75 * ff, rng.uniform(-0.01, 0.02) * ff,
                                      up * math.sin(math.pi * ff * 0.8) - 0.05 * ff * ff) for ff in f])
            path = np.array([guide.project(p[None], max(0.004, guide.d(p[None])[0]))[0] for p in path])
            nrm = np.tile(V(0, -0.2, 1.0), (4, 1)) + rng.normal(0, 0.15, (4, 3))
            w = [_blend(_neck_bone_at(y), _mane_bone_at(y, s) if lod < 1 else _neck_bone_at(y), ff)
                 for ff in f]
            cs.add_card(path, np.array([0.065, 0.06, 0.055, 0.045]), nrm, STRIP["mane_wisp"], w,
                        flip=bool(rng.integers(2)))
    return cs


def _strand_on_surface(guide, root, d0, length, segs, offset, rng, sx, stiff=0.55, off_gain=0.0):
    """March a strand from `root` along the skin; gravity bends it down, the offset from the
    skin grows along the strand (hair volume), slight waves."""
    step = length / segs
    p = root.copy()
    d = d0 / np.linalg.norm(d0)
    pts = [p.copy()]
    wav = rng.uniform(0.3, 1.0)
    ph = rng.uniform(0, 6.28)
    for i in range(segs):
        f = (i + 1) / segs
        g = V(0.0, 0.10, -1.0)
        d = stiff * d + (1 - stiff) * g / np.linalg.norm(g)
        d += V(0, math.sin(ph + i * 1.4) * 0.16 * wav, 0)
        d /= np.linalg.norm(d)
        q = p + d * step
        target = offset + off_gain * f
        dd = guide.d(q)[0] - target
        if dd < 0 or dd > 0.012:      # stay on (and close to) the skin
            q = guide.project(q, target + min(max(dd, 0.0), 0.012) * 0.3)[0]
        d = (q - p) / max(np.linalg.norm(q - p), 1e-9)
        p = q
        pts.append(p.copy())
    return np.array(pts)


# --------------------------------------------------------------------------- tail



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


# --------------------------------------------------------------------------- fringe cards
# The hair MASS is opaque geometry (horse_hairvol); cards only add the wispy fringe.

def mane_fringe_cards(guide, lod=0, seed=3):
    """Wisps hanging below the mane volume's lower edge + a few flyaways above the crest."""
    import horse_hairvol as HV
    if lod >= 2:
        return CardSet()
    rng = np.random.default_rng(seed + lod)
    cs = CardSet()
    y0, y1 = -1.10, -0.40
    for s, sx, n, line, lr in (("R", -1.0, {0: 26, 1: 13}[lod], HV.MANE_BOTTOM_R, (0.10, 0.17)),
                               ("L", 1.0, {0: 18, 1: 9}[lod], HV.MANE_BOTTOM_L, (0.07, 0.12))):
        for k in range(n):
            t = (k + rng.uniform(0.15, 0.85)) / n
            y = y0 + (y1 - y0) * t
            bottom = float(np.interp(y, *line))
            root = guide.project(V(0.10 * sx, y, bottom + 0.055)[None], 0.010)[0]
            length = rng.uniform(*lr)
            path = _strand_on_surface(guide, root, V(sx * 0.3, rng.uniform(0.0, 0.1), -1.0), length,
                                      {0: 4, 1: 3}[lod], 0.012, rng, sx, stiff=0.6, off_gain=0.008)
            nrm = guide.grad(path)
            w = [_blend(_neck_bone_at(y), _mane_bone_at(y, s) if lod < 1 else _neck_bone_at(y),
                        min(1.0, 0.5 + 0.5 * i / (len(path) - 1))) for i in range(len(path))]
            cs.add_card(path, np.linspace(0.06, 0.045, len(path)), nrm,
                        STRIP["mane_wavy"] if k % 2 else STRIP["mane_wisp"], w,
                        twist=rng.normal(0, 0.3), flip=bool(rng.integers(2)))
    # flyaway strands arching over the crest (read above the crest line in the profiles)
    for k in range({0: 6, 1: 3}[lod]):
        t = (k + rng.uniform(0.2, 0.8)) / {0: 6, 1: 3}[lod]
        y = y0 + 0.02 + (y1 - y0 - 0.06) * t
        top = HV._crest_top(guide, y)
        for sx in (1.0, -1.0):
            s = "L" if sx > 0 else "R"
            f = np.linspace(0, 1, 4)
            L = rng.uniform(0.06, 0.08)
            path = np.array([top + V(sx * L * 0.8 * ff, 0.01 * ff, 0.002 + 0.006 * math.sin(math.pi * ff * 0.8)
                                     - 0.05 * ff * ff) for ff in f])
            nrm = np.tile(V(0, -0.2, 1.0), (4, 1)) + rng.normal(0, 0.15, (4, 3))
            w = [_blend(_neck_bone_at(y), _mane_bone_at(y, s) if lod < 1 else _neck_bone_at(y), ff)
                 for ff in f]
            cs.add_card(path, np.array([0.05, 0.05, 0.045, 0.035]), nrm, STRIP["mane_wisp"], w,
                        flip=bool(rng.integers(2)))
    return cs


def forelock_fringe_cards(guide, lod=0, seed=5):
    """Forelock wisps falling between the eyes, parted around the white star."""
    if lod >= 2:
        return CardSet()
    rng = np.random.default_rng(seed)
    cs = CardSet()
    xs = {0: (-0.045, 0.0, 0.040), 1: (-0.04, 0.0, 0.045)}[lod]
    for x in xs:
        root = guide.project(V(x * 0.5, -1.20, 1.975)[None], 0.006)[0]
        # centre strand stops above the star (top tip ~1.865 m); side strands reach eye level
        zend = 1.875 if abs(x) < 0.01 else rng.uniform(1.765, 1.80)
        length = max(0.08, (root[2] - zend) * 1.35)
        path = _strand_on_surface(guide, root, V(x * 1.4, -0.8, -0.6), length, 4, 0.006, rng, 1.0,
                                  stiff=0.45, off_gain=0.004)
        nrm = guide.grad(path)
        w = [_blend({"head": 1.0}, {"forelock": 1.0} if lod < 1 else {"head": 1.0}, i / (len(path) - 1))
             for i in range(len(path))]
        cs.add_card(path, np.linspace(0.034, 0.022, len(path)), nrm, STRIP["forelock"], w,
                    twist=rng.normal(0, 0.25), flip=bool(rng.integers(2)))
    return cs


def tail_fringe_cards(lod=0, seed=7, drop=None):
    """Wisps on the lower outer surface and past the tip of the solid tail mass."""
    import horse_hairvol as HV
    if lod >= 2:
        return CardSet()
    rng = np.random.default_rng(seed)
    cs = CardSet()
    n = {0: 14, 1: 7}[lod]
    segs = {0: 5, 1: 3}[lod]
    for k in range(n):
        ang = 2 * math.pi * (k + rng.uniform(-0.3, 0.3)) / n
        t0 = rng.uniform(0.50, 0.72)
        t1 = rng.uniform(0.97, 1.03)
        ts = np.linspace(t0, t1, segs + 1)
        c = HV.tail_center(np.clip(ts, 0, 1))
        c[:, 2] -= np.clip(ts - 1.0, 0, None) * 1.2          # extend past the tip
        ax, ay = HV._tail_section(np.clip(ts, 0, 1))
        rho = 0.86 + 0.06 * np.clip((ts - t0) / (t1 - t0), 0, 1)
        wav = rng.uniform(0.008, 0.02)
        ph = rng.uniform(0, 6.28)
        x = c[:, 0] + rho * math.cos(ang) * ax + wav * np.sin(ph + ts * 12)
        y = c[:, 1] + rho * math.sin(ang) * ay + 0.6 * wav * np.cos(ph + ts * 9)
        path = np.stack([x, y, c[:, 2]], 1)
        nrm = np.tile(V(math.cos(ang), math.sin(ang), 0.1), (len(ts), 1))
        w = [_tail_weights(p) for p in path]
        if drop:
            w = [{HRig.resolve(b, drop): v for b, v in ww.items()} for ww in w]
        cs.add_card(path, rng.uniform(0.06, 0.085) * np.ones(len(ts)), nrm,
                    [STRIP["tail_a"], STRIP["tail_b"], STRIP["tail_wisp"]][k % 3], w,
                    twist=rng.normal(0, 0.3), flip=bool(rng.integers(2)))
    return cs


def feather_cards(J, lod=0, seed=9):
    """Draft feathering: tufts from the fetlock falling over the coronet onto the hoof wall,
    around the back and sides of every leg, longer on the hind legs."""
    if lod >= 2:
        return CardSet()
    rng = np.random.default_rng(seed)
    cs = CardSet()
    n = {0: 7, 1: 3}[lod]
    for fh in ("F", "H"):
        for s in ("L", "R"):
            sx = 1.0 if s == "L" else -1.0
            fet = J[f"fetlock_{fh}_{s}"]
            top = 0.07 if fh == "F" else 0.12             # hind tufts start higher (longer)
            bone = f"pastern_{fh}_{s}"
            for k in range(n):
                ang = math.radians(35 + 290 * k / max(n - 1, 1))   # skip the front of the pastern
                c, sn = math.cos(ang + math.pi / 2), math.sin(ang + math.pi / 2)
                # angle 0 = front (-Y): direction (sin, -cos)
                dx, dy = math.sin(ang) * sx, -math.cos(ang)
                r0, r1 = 0.058, 0.080
                root = fet + V(dx * r0, dy * r0 + 0.012, top)
                tip = V(fet[0] + dx * r1, fet[1] + dy * r1 + 0.01, 0.035 + rng.uniform(-0.008, 0.01))
                path = np.array([root + (tip - root) * f + V(dx, dy, 0) * 0.015 * math.sin(math.pi * f)
                                 for f in np.linspace(0, 1, 4)])
                nrm = np.tile(V(dx, dy, 0.0), (4, 1))
                wk = 1.45 if abs(math.degrees(ang) - 180.0) < 70.0 else 1.0   # fuller at the back
                cs.add_card(path, np.array([0.032, 0.036, 0.034, 0.028]) * wk, nrm, STRIP["tail_wisp"],
                            [{bone: 1.0}] * 4, twist=rng.normal(0, 0.2), flip=bool(rng.integers(2)))
            # fringe hanging behind the fetlock (reads as the feathering mass in the profiles)
            for k in range({0: 3, 1: 1}[lod]):
                f = (k / 2.0 - 0.5) if lod == 0 else 0.0
                root = fet + V(sx * 0.03 * f * 2, 0.06, 0.13 + 0.02 * rng.random())
                tip = fet + V(sx * 0.04 * f * 2, 0.10 + 0.02 * rng.random(), -0.14)
                path = np.array([root + (tip - root) * t + V(0, 0.02 * math.sin(math.pi * t), 0)
                                 for t in np.linspace(0, 1, 4)])
                nrm = np.tile(V(1.0, 0.25 * f, 0.0), (4, 1))
                cs.add_card(path, np.array([0.045, 0.055, 0.055, 0.045]), nrm, STRIP["feather"],
                            [{bone: 1.0}] * 4, twist=rng.normal(0, 0.15), flip=bool(rng.integers(2)))
    return cs
