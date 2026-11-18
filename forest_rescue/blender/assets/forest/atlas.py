"""Shared 2048² foliage atlas for the forest kit: procedurally painted leaf/needle/frond clusters.

All foliage cards of every tree / ground-cover asset sample this ONE texture (alpha-tested,
cutoff 0.5).  Layout rects are pixel boxes (x, y, w, h), origin top-left.  `uv_rect(name)`
returns Blender UV bounds (u0, v0, u1, v1) with v up.  Tiles are painted with the twig
attachment at the bottom-centre unless noted (`attach`).
"""
import math
import numpy as np
import cv2

from ftex import fbm, rng, smoothstep, ramp, value_noise

SIZE = 2048

LAYOUT = {}


def _reg(name, x, y, w, h, attach="bottom"):
    LAYOUT[name] = dict(rect=(x, y, w, h), attach=attach)


# row A: oak leaf CLUMPS (dense round clusters, low transparency) by crown position
OAK_CLUMPS = ["oak_clump_light_a", "oak_clump_light_b", "oak_clump_gold_a", "oak_clump_gold_b", "oak_clump_ochre_a",
              "oak_clump_ochre_b", "oak_clump_dark_a", "oak_clump_red_a"]
for i, n in enumerate(OAK_CLUMPS):
    _reg(n, i * 256, 0, 256, 256, attach="center")
# row B: pine sprays + birch clusters
for i, n in enumerate(["pine_spray_a", "pine_spray_b", "pine_spray_c", "pine_spray_d"]):
    _reg(n, i * 256, 256, 256, 256)
BIRCH_CLUMPS = ["birch_clump_light", "birch_clump_mid", "birch_clump_dark", "birch_clump_gold"]
for i, n in enumerate(BIRCH_CLUMPS):          # small sparse HANGING leaf clusters on drooping twigs (attach top)
    _reg(n, 1024 + i * 256, 256, 256, 256, attach="top")
# row C (512 tall): willow strands, fern fronds, reed blades
for i in range(6):
    _reg(f"willow_strand_{i}", i * 128, 512, 128, 512, attach="top")
_reg("fern_frond_a", 768, 512, 256, 512)
_reg("fern_frond_b", 1024, 512, 256, 512)
_reg("reed_blades_a", 1280, 512, 256, 512)
_reg("reed_blades_b", 1536, 512, 256, 512)
_reg("cattail", 1792, 512, 64, 256, attach="none")       # cattail head colour field (geometry UVs)
_reg("reed_stem", 1856, 512, 32, 256, attach="none")
_reg("berry_red", 1888, 512, 32, 32, attach="none")
_reg("berry_dark", 1920, 512, 32, 32, attach="none")
_reg("bramble_cane", 1952, 512, 32, 256, attach="none")
_reg("twig_brown", 1984, 512, 32, 256, attach="none")
_reg("willow_top_a", 1792, 768, 256, 256)
# row D: ground cover tiles
_reg("grass_a", 0, 1024, 256, 256)
_reg("grass_b", 256, 1024, 256, 256)
_reg("bramble_a", 512, 1024, 256, 256)
_reg("bramble_b", 768, 1024, 256, 256)
_reg("shrub_orange", 1024, 1024, 256, 256)
_reg("moss_clump", 1280, 1024, 256, 256, attach="none")
_reg("mushroom", 1536, 1024, 256, 256, attach="none")
_reg("fungus_bracket", 1792, 1024, 256, 256, attach="none")
# row E: dense clumps for LOD1/LOD2 cards
for i, n in enumerate(["oak_dense_gold", "oak_dense_amber", "oak_dense_orange", "oak_dense_rust", "pine_dense_a",
                       "pine_dense_b", "birch_dense", "willow_dense"]):
    _reg(n, i * 256, 1280, 256, 256, attach="center")
# row F: bark strips (single-material far LODs), fallen-leaf litter, extra
for i, n in enumerate(["bark_oak", "bark_pine", "bark_birch", "bark_hollow", "bark_willow"]):
    _reg(n, i * 128, 1536, 128, 512, attach="none")
_reg("leaf_litter", 640, 1536, 256, 256, attach="none")
_reg("fern_dense", 896, 1536, 256, 256, attach="center")
_reg("bramble_dense", 1152, 1536, 256, 256, attach="center")
_reg("grass_dense", 1408, 1536, 256, 256, attach="center")
_reg("shrub_dense", 1664, 1536, 256, 256, attach="center")
_reg("reed_dense", 1920, 1536, 128, 512, attach="bottom")
_reg("oak_green_a", 640, 1792, 256, 256, attach="center")
_reg("pine_spray_e", 896, 1792, 256, 256)
_reg("birch_spare", 1152, 1792, 256, 256, attach="center")
_reg("pine_top", 1408, 1792, 256, 256, attach="center")
_reg("water", 1664, 1792, 256, 256, attach="none")
# aliases (older names used by builders)
for _old, _new in {"oak_gold_a": "oak_clump_gold_a", "oak_gold_b": "oak_clump_gold_b", "oak_amber_a": "oak_clump_ochre_a",
                   "oak_amber_b": "oak_clump_ochre_b", "oak_orange_a": "oak_clump_ochre_b", "oak_orange_b": "oak_clump_red_a",
                   "oak_rust_a": "oak_clump_dark_a", "oak_rust_b": "oak_clump_red_a", "birch_a": "birch_clump_mid",
                   "birch_b": "birch_clump_light", "birch_c": "birch_clump_dark", "birch_yellow": "birch_clump_gold",
                   "birch_green": "birch_clump_dark"}.items():
    LAYOUT[_old] = LAYOUT[_new]


def uv_rect(name, pad=1.5):
    """(u0, v0, u1, v1) Blender UV (v up) of a layout tile, inset by `pad` texels."""
    x, y, w, h = LAYOUT[name]["rect"]
    u0 = (x + pad) / SIZE
    u1 = (x + w - pad) / SIZE
    v1 = 1.0 - (y + pad) / SIZE
    v0 = 1.0 - (y + h - pad) / SIZE
    return (u0, v0, u1, v1)


# ----------------------------------------------------------------------------- canvas

class Canvas:
    """Supersampled RGBA painting surface with 'over' compositing of anti-aliased shapes."""

    def __init__(self, w, h, ss=3):
        self.w, self.h, self.ss = w, h, ss
        self.rgb = np.zeros((h * ss, w * ss, 3), np.float32)
        self.a = np.zeros((h * ss, w * ss), np.float32)

    def _bbox(self, pts, pad):
        p = np.asarray(pts, float) * self.ss
        H, W = self.a.shape
        x0 = int(max(0, np.floor(p[:, 0].min() - pad)))
        y0 = int(max(0, np.floor(p[:, 1].min() - pad)))
        x1 = int(min(W, np.ceil(p[:, 0].max() + pad)))
        y1 = int(min(H, np.ceil(p[:, 1].max() + pad)))
        return x0, y0, x1, y1

    def _comp(self, m, col, alpha, x0, y0):
        h, w = m.shape
        mm = (m * alpha)[..., None]
        c = np.asarray(col, np.float32)
        R = self.rgb[y0:y0 + h, x0:x0 + w]
        A = self.a[y0:y0 + h, x0:x0 + w]
        self.rgb[y0:y0 + h, x0:x0 + w] = R * (1 - mm) + c * mm
        self.a[y0:y0 + h, x0:x0 + w] = A + mm[..., 0] * (1 - A)

    def comp(self, m, col, alpha=1.0):
        self._comp(m, col, alpha, 0, 0)

    def poly(self, pts, col, alpha=1.0, shade=None):
        x0, y0, x1, y1 = self._bbox(pts, 3)
        if x1 <= x0 or y1 <= y0:
            return None
        m = np.zeros((y1 - y0, x1 - x0), np.uint8)
        p = ((np.asarray(pts) * self.ss - [x0, y0]) * 16).astype(np.int32)
        cv2.fillPoly(m, [p], 255, cv2.LINE_AA, shift=4)
        m = m.astype(np.float32) / 255.0
        if shade is not None:
            col = shade(m, col)
        self._comp(m, col, alpha, x0, y0)
        return m

    def line(self, pts, width, col, alpha=1.0):
        wd = max(1, int(round(width * self.ss)))
        x0, y0, x1, y1 = self._bbox(pts, wd + 3)
        if x1 <= x0 or y1 <= y0:
            return
        m = np.zeros((y1 - y0, x1 - x0), np.uint8)
        p = ((np.asarray(pts) * self.ss - [x0, y0]) * 16).astype(np.int32)
        cv2.polylines(m, [p], False, 255, wd, cv2.LINE_AA, shift=4)
        self._comp(m.astype(np.float32) / 255.0, col, alpha, x0, y0)

    def circle(self, c, r, col, alpha=1.0):
        pts = np.array([[c[0] - r, c[1] - r], [c[0] + r, c[1] + r]])
        x0, y0, x1, y1 = self._bbox(pts, 3)
        if x1 <= x0 or y1 <= y0:
            return
        m = np.zeros((y1 - y0, x1 - x0), np.uint8)
        cc = (int((c[0] * self.ss - x0) * 16), int((c[1] * self.ss - y0) * 16))
        cv2.circle(m, cc, int(r * self.ss * 16), 255, -1, cv2.LINE_AA, shift=4)
        self._comp(m.astype(np.float32) / 255.0, col, alpha, x0, y0)

    def result(self):
        """Downsample with premultiplied alpha -> (h, w, 4) float."""
        pm = self.rgb * self.a[..., None]
        pm = cv2.resize(pm, (self.w, self.h), interpolation=cv2.INTER_AREA)
        a = cv2.resize(self.a, (self.w, self.h), interpolation=cv2.INTER_AREA)
        rgb = pm / np.maximum(a, 1e-6)[..., None]
        return np.concatenate([rgb, a[..., None]], -1).astype(np.float64)


# ----------------------------------------------------------------------------- leaf shapes (unit, base at 0, tip at +y=1)

def leaf_outline(kind, r, n=40):
    t = np.linspace(0, 1, n)
    if kind == "oak":
        lobes = r.integers(4, 6)
        env = 0.36 * np.sin(np.pi * np.clip(t, 0, 1) ** 0.75) ** 0.8 * (0.55 + 0.45 * t)
        lob = 0.62 + 0.38 * np.abs(np.cos(np.pi * lobes * t + 0.3)) ** 0.7
        w = env * lob
        w[:3] = np.array([0.02, 0.04, 0.06])[:3]
    elif kind == "birch":
        w = 0.42 * np.sin(np.pi * t) ** 0.65 * (1.15 - 0.55 * t)
        w += 0.025 * (np.mod(t * 18, 1.0) - 0.5) * (t > 0.08)
    elif kind == "willow":
        w = 0.11 * np.sin(np.pi * t) ** 0.7
    elif kind == "bramble":
        w = 0.40 * np.sin(np.pi * t) ** 0.7 * (1.1 - 0.35 * t)
        w += 0.03 * (np.mod(t * 14, 1.0) - 0.5) * (t > 0.06)
    elif kind == "shrub":
        w = 0.34 * np.sin(np.pi * t) ** 0.8
        w += 0.04 * (np.mod(t * 9, 1.0) - 0.5)
    elif kind == "pinna":
        w = 0.06 * np.sin(np.pi * t) ** 0.6 * (0.6 + 0.5 * np.abs(np.sin(np.pi * 9 * t)))
    elif kind == "blade":
        w = 0.5 * (1 - t) ** 0.9
    else:
        w = 0.3 * np.sin(np.pi * t)
    asym = 1 + 0.08 * r.standard_normal()
    right = np.stack([w, t], -1)
    left = np.stack([-w[::-1] * asym, t[::-1]], -1)
    return np.concatenate([right, left], 0)


def place(pts, base, angle, length, width_scale=1.0, bend=0.0):
    """Unit leaf points -> tile pixels: base point, angle (rad, 0 = up/-y), length px."""
    p = np.array(pts, float)
    p[:, 0] *= width_scale
    if bend:
        p[:, 0] += bend * p[:, 1] ** 2
    ca, sa = math.cos(angle), math.sin(angle)
    x = p[:, 0] * length
    y = p[:, 1] * length
    # leaf +y is "up" in tile = -row
    X = base[0] + x * ca + y * sa
    Y = base[1] + x * sa * 1.0 - y * ca
    return np.stack([X, Y], -1)


def leaf_shade(base_col, r, dark=1.0, vein=True):
    """Returns a shading fn: gradient across the leaf mask + slight noise."""
    def fn(m, col):
        H, W = m.shape
        c = np.asarray(base_col, np.float32) * dark
        yy, xx = np.nonzero(m > 0.01)
        if len(yy) == 0:
            return c
        img = np.zeros((H, W, 3), np.float32)
        y0, y1, x0, x1 = yy.min(), yy.max() + 1, xx.min(), xx.max() + 1
        gy, gx = np.mgrid[y0:y1, x0:x1]
        t = (gy - y0) / max(1, (y1 - y0))
        s = (gx - x0) / max(1, (x1 - x0))
        k = 0.82 + 0.25 * (1 - t) * 0.6 + 0.18 * np.sin(np.pi * s)
        img[y0:y1, x0:x1] = c[None, None, :] * k[..., None]
        return np.clip(img, 0, 1)
    return fn


def jitter_col(c, r, amt=0.06):
    c = np.asarray(c, float) * (1 + r.normal(0, amt, 3)) + r.normal(0, amt * 0.4)
    return np.clip(c, 0, 1)


# ----------------------------------------------------------------------------- tile painters

def paint_broadleaf_cluster(w, h, r, kind, palette, n_leaves=46, leaf_len=(0.17, 0.25), spread=0.42, twig_col=(0.25, 0.17, 0.10),
                            dense=False, attach="bottom", droop=0.0):
    """Cluster of leaves on a twig skeleton; palette = list of (weight, rgb)."""
    cv = Canvas(w, h)
    L = min(w, h)
    if attach == "bottom":
        root = np.array([w / 2, h - 2.0])
        main_dir = -np.pi / 2
    elif attach == "top":
        root = np.array([w / 2, 2.0])
        main_dir = np.pi / 2
    else:
        root = np.array([w / 2, h / 2])
        main_dir = -np.pi / 2
    centre = np.array([w / 2, h / 2])
    # twigs
    tips = []
    if attach != "center":
        # puff centre sits 45% into the tile from the attachment edge
        pc = np.array([w / 2, h * 0.47]) if attach == "bottom" else np.array([w / 2, h * 0.53])
        n_tw = r.integers(5, 8)
        for i in range(n_tw):
            ang = r.uniform(0, 2 * np.pi)
            end = pc + np.array([math.cos(ang), math.sin(ang) * 0.85]) * r.uniform(0.12, 0.30) * L
            end[1] += droop * L * 0.08
            mid = root * 0.5 + end * 0.5 + r.normal(0, 0.03, 2) * L
            cv.line([root, mid, end], r.uniform(1.6, 2.6), twig_col)
            tips.append(end)
        centre = pc
    else:
        tips = [centre + r.normal(0, 0.15, 2) * L for _ in range(6)]
    tips = np.array(tips)
    wts = np.array([p[0] for p in palette], float)
    wts /= wts.sum()
    # leaves: back layer first (darker), front layer last (brighter)
    for i in range(n_leaves):
        layer = i / max(1, n_leaves - 1)
        dark = 0.45 + 0.62 * layer ** 0.8          # deep shadowed back leaves, sunlit front leaves
        if dense:
            p = centre + r.normal(0, spread * 0.55, 2) * L
            d = p - centre
            ang = math.atan2(d[1], d[0]) + np.pi / 2 + r.normal(0, 0.6)
        else:
            tp = tips[r.integers(len(tips))]
            p = tp + r.normal(0, spread * 0.20, 2) * L
            d = p - centre
            ang = math.atan2(d[1], d[0]) + np.pi / 2 + r.normal(0, 0.55)
        ln = r.uniform(*leaf_len) * L
        # keep the whole leaf inside the tile (no cut-off edges)
        tipp = p + np.array([math.sin(ang), -math.cos(ang)]) * ln
        m = 3.0
        lo = np.minimum(p, tipp) - 0.25 * ln
        hi = np.maximum(p, tipp) + 0.25 * ln
        shift = np.maximum(0, m - lo) - np.maximum(0, hi - np.array([w - m, h - m]))
        p = p + shift
        col = palette[r.choice(len(palette), p=wts)][1]
        col = jitter_col(col, r, 0.07)
        pts = place(leaf_outline(kind, r), p, ang, ln, width_scale=r.uniform(0.85, 1.15), bend=r.uniform(-0.06, 0.06))
        cv.poly(pts, col, shade=leaf_shade(col, r, dark))
        if layer > 0.35 and kind in ("oak", "birch", "bramble"):
            mid = place(np.array([[0, 0.05], [0, 0.85]]), p, ang, ln)
            cv.line(mid, 0.9, np.clip(np.asarray(col) * dark * 0.72, 0, 1), alpha=0.55)
    return cv.result()


def paint_clump(w, h, r, palette, kind="oak", n_leaves=300, leaf_len=(0.10, 0.15), radius=0.31, gap=0.06,
                width_scale=1.0):
    """Dense ROUND leaf clump (card for spherified-normal crowns): leaves fill a disc, edge leaves point
    outward (leafy silhouette), back leaves darker -> soft depth; ~90% alpha coverage inside the disc."""
    cv = Canvas(w, h)
    L = min(w, h)
    c = np.array([w / 2, h / 2])
    wts = np.array([p[0] for p in palette], float)
    wts /= wts.sum()
    R = radius * L
    k1, k2 = r.integers(3, 6), r.integers(6, 9)
    f1, f2 = r.uniform(0, 6.28, 2)
    lobe = lambda th: 1 + 0.2 * np.sin(k1 * th + f1) + 0.09 * np.sin(k2 * th + f2)      # lumpy, non-circular outline
    for i in range(n_leaves):
        layer = i / max(1, n_leaves - 1)
        ang0 = r.uniform(0, 2 * np.pi)
        rr = R * lobe(ang0) * np.sqrt(r.random()) * (0.96 if layer > 0.5 else 1.02)
        p = c + rr * np.array([math.cos(ang0), math.sin(ang0)])
        edge = rr / (R * lobe(ang0))
        ang = ang0 + np.pi / 2 + r.normal(0, 1.4 * (1 - edge) + 0.35)
        ln = r.uniform(*leaf_len) * L * (0.85 + 0.3 * edge)
        tipp = p + np.array([math.sin(ang), -math.cos(ang)]) * ln
        m = 3.0
        lo = np.minimum(p, tipp) - 0.25 * ln
        hi = np.maximum(p, tipp) + 0.25 * ln
        p = p + np.maximum(0, m - lo) - np.maximum(0, hi - np.array([w - m, h - m]))
        col = jitter_col(palette[r.choice(len(palette), p=wts)][1], r, 0.06)
        dark = 0.55 + 0.5 * layer ** 0.9
        pts = place(leaf_outline(kind, r), p, ang, ln, width_scale=r.uniform(0.85, 1.15) * width_scale,
                    bend=r.uniform(-0.06, 0.06))
        cv.poly(pts, col, shade=leaf_shade(col, r, dark))
        if layer > 0.6 and kind in ("oak", "birch", "bramble") and ln > 8:
            mid = place(np.array([[0, 0.05], [0, 0.85]]), p, ang, ln)
            cv.line(mid, 0.8, np.clip(np.asarray(col) * dark * 0.7, 0, 1), alpha=0.5)
    out = cv.result()
    # a few dark gaps between leaf groups (depth), never fully transparent inside
    yy, xx = np.mgrid[0:h, 0:w]
    gapn = fbm(h, w, 8, 8, int(r.integers(1e6)), 3)
    g = smoothstep(0.62, 0.72, gapn) * gap * 6
    out[..., :3] *= (1 - np.clip(g, 0, 0.45))[..., None]
    return out


def paint_pine_spray(w, h, r, cols, n_side=11, dense=False):
    """Spruce/pine needle spray: main twig bottom->top, pinnate side twigs, needles as short strokes."""
    cv = Canvas(w, h)
    L = min(w, h)
    base = np.array([w / 2 + r.normal(0, 3), h - 2.0])
    tip = np.array([w / 2 + r.normal(0, 10), 10.0])
    ctrl = (base + tip) / 2 + np.array([r.normal(0, 14), 0])
    tt = np.linspace(0, 1, 24)
    axis = ((1 - tt) ** 2)[:, None] * base + (2 * tt * (1 - tt))[:, None] * ctrl + (tt ** 2)[:, None] * tip
    dark, mid, light = [np.asarray(c, float) for c in cols]
    twig = (0.22, 0.14, 0.08)

    def needles_along(pts, nlen, dens, layer):
        seg = np.diff(pts, axis=0)
        segl = np.linalg.norm(seg, axis=1)
        tot = segl.sum()
        n = int(tot * dens)
        cum = np.concatenate([[0], np.cumsum(segl)])
        for k in range(n):
            s = r.random() * tot
            j = min(np.searchsorted(cum, s) - 1, len(seg) - 1)
            f = (s - cum[j]) / max(segl[j], 1e-6)
            p = pts[j] + seg[j] * f
            dvec = seg[j] / max(segl[j], 1e-6)
            side = 1 if r.random() < 0.5 else -1
            nrm = np.array([-dvec[1], dvec[0]]) * side
            ang = 0.55 + r.normal(0, 0.18)
            nd = nrm * math.cos(ang) + dvec * math.sin(ang)
            ln = nlen * r.uniform(0.7, 1.15) * (0.75 + 0.25 * (1 - s / tot))
            q = p + nd * ln
            tone = r.random()
            tipw = min(1.0, (s / tot) ** 2 * 1.3) if tot > 0 else 0
            c = (dark * (1 - tone) + mid * tone) if r.random() < 0.8 - 0.5 * tipw else light
            c = c * (0.72 + 0.4 * layer)
            cv.line([p, q], r.uniform(1.0, 1.6), np.clip(c, 0, 1))

    # side twigs (back layer first)
    sides = []
    for k in range(n_side):
        t = 0.08 + 0.85 * k / max(1, n_side - 1) + r.normal(0, 0.02)
        j = int(np.clip(t, 0, 0.999) * (len(axis) - 1))
        p0 = axis[j]
        dvec = axis[min(j + 1, len(axis) - 1)] - axis[max(j - 1, 0)]
        dvec /= np.linalg.norm(dvec) + 1e-9
        for side in (-1, 1):
            nrm = np.array([-dvec[1], dvec[0]]) * side
            ln = (0.40 * (1 - t) ** 0.7 + 0.08) * L * r.uniform(0.8, 1.1)
            ang_up = 0.75 + r.normal(0, 0.1)
            d2 = nrm * math.cos(ang_up) + dvec * math.sin(ang_up)
            pts = [p0, p0 + d2 * ln * 0.5 + np.array([0, ln * 0.06]), p0 + d2 * ln + np.array([0, ln * 0.14])]
            sides.append((pts, ln))
    order = r.permutation(len(sides))
    for i, k in enumerate(order):
        pts, ln = sides[k]
        layer = i / max(1, len(order) - 1)
        cv.line(pts, 1.4, twig, 0.9)
        needles_along(np.array(pts), nlen=L * 0.07, dens=(1.7 if dense else 1.25), layer=0.3 + 0.5 * layer)
    cv.line(axis, 2.2, twig)
    needles_along(axis, nlen=L * 0.075, dens=1.4, layer=1.0)
    return cv.result()


def paint_pine_dense(w, h, r, cols):
    """Round dense needle mass for far LOD cards (top-view friendly)."""
    cv = Canvas(w, h)
    dark, mid, light = [np.asarray(c, float) for c in cols]
    centre = np.array([w / 2, h / 2])
    for k in range(110):
        ang = r.uniform(0, 2 * np.pi)
        rad = r.uniform(0.18, 0.46) * w
        p0 = centre + np.array([math.cos(ang), math.sin(ang)]) * rad * 0.3
        p1 = centre + np.array([math.cos(ang), math.sin(ang)]) * rad
        layer = k / 70
        cv.line([p0, p1], 1.3, (0.2, 0.13, 0.08), 0.8)
        for j in range(34):
            f = r.random()
            p = p0 + (p1 - p0) * f
            d = (p1 - p0) / (np.linalg.norm(p1 - p0) + 1e-9)
            n = np.array([-d[1], d[0]]) * (1 if r.random() < 0.5 else -1)
            q = p + (n * 0.85 + d * 0.5) * r.uniform(7, 14)
            c = (dark * (1 - r.random()) + mid * r.random()) * (0.7 + 0.45 * layer)
            if r.random() < 0.12:
                c = light
            cv.line([p, q], 1.3, np.clip(c, 0, 1))
    return cv.result()


def paint_willow_strand(w, h, r, cols, n_strands=3):
    cv = Canvas(w, h)
    for s in range(n_strands):
        x0 = w * (0.3 + 0.4 * r.random())
        sway = r.normal(0, 8)
        tt = np.linspace(0, 1, 30)
        xs = x0 + sway * tt ** 2 + 3 * np.sin(tt * 5 + r.random() * 6)
        ys = 2 + tt * (h - 6) * r.uniform(0.85, 1.0)
        axis = np.stack([xs, ys], -1)
        layer = s / max(1, n_strands - 1)
        cv.line(axis, 1.6, (0.30, 0.25, 0.12), 0.8)
        nleaf = int(h / 9)
        for k in range(nleaf):
            t = k / nleaf
            j = int(t * 29)
            p = axis[j]
            side = 1 if k % 2 else -1
            ang = np.pi - side * r.uniform(0.25, 0.6)          # pointing down and sideways
            ln = r.uniform(0.10, 0.17) * h * (1.0 - 0.35 * t)
            c = jitter_col(cols[r.integers(len(cols))], r, 0.08)
            pts = place(leaf_outline("willow", r), p, ang, ln, width_scale=1.4)
            cv.poly(pts, c, shade=leaf_shade(c, r, 0.7 + 0.4 * layer))
    return cv.result()


def paint_fern(w, h, r, cols, golden=0.0):
    cv = Canvas(w, h)
    base = np.array([w * 0.5, h - 2.0])
    tt = np.linspace(0, 1, 40)
    curl = r.uniform(-0.25, 0.25)
    xs = base[0] + w * curl * tt ** 2 * 1.2
    ys = base[1] - tt * (h - 10)
    axis = np.stack([xs, ys], -1)
    cv.line(axis, 2.0, (0.35, 0.28, 0.12))
    for k in range(24):
        t = 0.12 + 0.86 * k / 24
        j = int(t * 39)
        p = axis[j]
        d = axis[min(j + 1, 39)] - axis[max(j - 1, 0)]
        d /= np.linalg.norm(d) + 1e-9
        ln = (0.44 * math.sin(np.pi * (0.12 + 0.88 * (1 - t))) ** 0.9 + 0.04) * w
        for side in (-1, 1):
            n = np.array([-d[1], d[0]]) * side
            dirv = n * 0.8 + d * 0.55
            ang = math.atan2(dirv[1], dirv[0]) + np.pi / 2
            mix = np.clip(golden + 0.3 * (1 - t) * r.random(), 0, 1)
            c = np.asarray(cols[0]) * (1 - mix) + np.asarray(cols[1]) * mix
            c = jitter_col(c, r, 0.05)
            pts = place(leaf_outline("pinna", r), p, ang, ln, width_scale=1.0, bend=0.05 * side)
            cv.poly(pts, c, shade=leaf_shade(c, r, 0.85 + 0.2 * t))
    return cv.result()


def paint_blades(w, h, r, cols, n=34, height=(0.55, 0.98), width=(3.5, 7.0), seed_heads=False):
    cv = Canvas(w, h)
    for k in range(n):
        x0 = w * (0.5 + r.normal(0, 0.16))
        bh = r.uniform(*height) * h
        lean = r.normal(0, 0.18) * bh
        bw = r.uniform(*width)
        tt = np.linspace(0, 1, 16)
        xs = x0 + lean * tt ** 1.6
        ys = h - 1 - bh * tt
        widths = bw * (1 - tt) ** 0.8 + 0.4
        nrm = np.stack([np.ones_like(tt), np.zeros_like(tt)], -1)
        left = np.stack([xs - widths / 2, ys], -1)
        right = np.stack([xs + widths / 2, ys], -1)
        pts = np.concatenate([left, right[::-1]], 0)
        c = jitter_col(cols[r.integers(len(cols))], r, 0.06)
        cv.poly(pts, c, shade=leaf_shade(c, r, 0.7 + 0.45 * k / n))
    return cv.result()


def paint_bramble(w, h, r, dense=False):
    cv = Canvas(w, h)
    leaf_cols = [(0.27, 0.30, 0.12), (0.34, 0.34, 0.14), (0.40, 0.21, 0.12), (0.44, 0.17, 0.11), (0.32, 0.25, 0.12)]
    centre = np.array([w / 2, h * (0.55 if not dense else 0.5)])
    # canes
    for k in range(6 if not dense else 3):
        a = -np.pi / 2 + r.uniform(-1.2, 1.2)
        p0 = np.array([w / 2 + r.normal(0, 20), h - 2.0])
        p1 = p0 + np.array([math.cos(a), math.sin(a)]) * h * r.uniform(0.5, 0.8)
        p2 = p1 + np.array([r.normal(0, 25), h * 0.15])
        cv.line([p0, p1, p2], 2.0, (0.36, 0.17, 0.10))
    for k in range(40 if not dense else 70):
        p = centre + r.normal(0, 0.24, 2) * np.array([w, h])
        p = np.clip(p, 20, [w - 20, h - 20])
        ang = r.uniform(-2.5, 2.5)
        c = jitter_col(leaf_cols[r.integers(len(leaf_cols))], r, 0.08)
        ln = r.uniform(0.12, 0.18) * w
        for lf in range(3):
            pts = place(leaf_outline("bramble", r), p, ang + (lf - 1) * 0.7, ln * (1.0 if lf == 1 else 0.8))
            cv.poly(pts, c, shade=leaf_shade(c, r, 0.7 + 0.4 * k / 40))
    for k in range(10 if not dense else 14):
        p = centre + r.normal(0, 0.22, 2) * np.array([w, h])
        dark = r.random() < 0.4
        for b in range(r.integers(5, 10)):
            q = p + r.normal(0, 4.5, 2)
            col = (0.18, 0.04, 0.06) if dark else (0.62, 0.08, 0.08)
            cv.circle(q, r.uniform(2.6, 3.8), jitter_col(col, r, 0.1))
            cv.circle(q - 1, 1.0, (0.9, 0.6, 0.55), 0.6)
    return cv.result()


def paint_moss(w, h, r):
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt(((xx - w / 2) / (w * 0.5)) ** 2 + ((yy - h / 2) / (h * 0.5)) ** 2)
    n = fbm(h, w, 8, 8, int(r.integers(1e6)), 5)
    a = smoothstep(0.98, 0.86, d + (n - 0.5) * 0.45)
    g = fbm(h, w, 64, 64, int(r.integers(1e6)), 3)
    g2 = fbm(h, w, 6, 6, int(r.integers(1e6)), 3)
    col = ramp(g * 0.7 + g2 * 0.3, [(0, (0.16, 0.20, 0.06)), (0.5, (0.28, 0.32, 0.09)), (0.8, (0.40, 0.43, 0.13)),
                                    (1, (0.52, 0.53, 0.18))])
    return np.concatenate([col, a[..., None]], -1)


def paint_mushroom(w, h, r):
    out = np.zeros((h, w, 4))
    yy, xx = np.mgrid[0:h, 0:w] / np.array([h, w])[:, None, None]
    n = fbm(h, w, 16, 16, 5, 3)
    cap = ramp(yy * 2 + (n - 0.5) * 0.3, [(0, (0.62, 0.30, 0.14)), (0.6, (0.72, 0.42, 0.20)), (1.0, (0.80, 0.60, 0.38))])
    stem = ramp(n, [(0, (0.80, 0.74, 0.62)), (1, (0.92, 0.88, 0.78))])
    out[..., :3] = np.where((yy < 0.5)[..., None], cap, stem)
    spots = (fbm(h, w, 24, 24, 9, 2) > 0.68) & (yy < 0.45)
    out[spots, :3] = out[spots, :3] * 0.5 + 0.45
    out[..., 3] = 1.0
    return out


def paint_bracket(w, h, r):
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    cx, cy = w / 2, h * 0.18
    dx, dy = (xx - cx) / (w * 0.48), (yy - cy) / (h * 0.75)
    d = np.sqrt(dx ** 2 + dy ** 2)
    n = fbm(h, w, 8, 8, 3, 3)
    a = smoothstep(1.0, 0.94, d + (n - 0.5) * 0.08) * (yy > cy - 2)
    bands = 0.5 + 0.5 * np.sin(d * 28 + n * 3)
    col = ramp(d * 0.8 + bands * 0.2, [(0, (0.40, 0.25, 0.13)), (0.5, (0.62, 0.42, 0.24)), (0.85, (0.78, 0.62, 0.42)),
                                      (1.0, (0.90, 0.82, 0.66))])
    return np.concatenate([col, a[..., None]], -1)


def paint_litter(w, h, r):
    cv = Canvas(w, h)
    cols = [(0.62, 0.36, 0.12), (0.72, 0.50, 0.18), (0.45, 0.25, 0.10), (0.55, 0.45, 0.25)]
    for k in range(90):
        p = r.uniform(10, w - 10, 2)
        c = jitter_col(cols[r.integers(4)], r, 0.1)
        pts = place(leaf_outline("oak", r), p, r.uniform(0, 6.28), r.uniform(0.08, 0.14) * w)
        cv.poly(pts, c, shade=leaf_shade(c, r, 0.7 + 0.4 * k / 90))
    return cv.result()


def bark_strip(albedo):
    """Full-period tileable bark -> 128x512 strip (2 vertical periods)."""
    tall = np.concatenate([albedo, albedo], 0)
    rgb = cv2.resize(tall.astype(np.float32), (128, 512), interpolation=cv2.INTER_AREA)
    return np.concatenate([rgb, np.ones((512, 128, 1), np.float32)], -1)


# ----------------------------------------------------------------------------- palettes (albedo, slightly brighter than painted)

OAK_PALETTES = {   # golden-ochre / amber / orange (art/02 oak, art/01 + art/07 woods); no lemon yellow
    "gold": [(3, (0.78, 0.52, 0.15)), (2, (0.84, 0.60, 0.20)), (1.2, (0.60, 0.35, 0.10)), (0.5, (0.88, 0.70, 0.34))],
    "amber": [(3, (0.72, 0.44, 0.12)), (2, (0.80, 0.53, 0.16)), (1.2, (0.55, 0.29, 0.09)), (0.4, (0.86, 0.64, 0.28))],
    "orange": [(3, (0.70, 0.35, 0.10)), (2, (0.78, 0.45, 0.13)), (1.2, (0.52, 0.23, 0.08)), (0.4, (0.84, 0.56, 0.22))],
    "rust": [(3, (0.62, 0.27, 0.09)), (2, (0.72, 0.36, 0.12)), (1.2, (0.46, 0.19, 0.07)), (0.4, (0.80, 0.50, 0.20))],
    "green": [(2, (0.56, 0.48, 0.16)), (2, (0.68, 0.52, 0.17)), (1, (0.42, 0.36, 0.12)), (0.6, (0.78, 0.60, 0.24))],
}
BIRCH_PALETTES = {   # art/02 birch: warm yellow-green (R >= G), lighter than the oak interior
    "a": [(3, (0.62, 0.55, 0.24)), (2, (0.72, 0.63, 0.30)), (1, (0.48, 0.44, 0.18)), (0.6, (0.82, 0.73, 0.38))],
    "yellow": [(3, (0.76, 0.64, 0.28)), (2, (0.84, 0.72, 0.34)), (1, (0.60, 0.50, 0.20))],
    "green": [(3, (0.50, 0.48, 0.19)), (2, (0.58, 0.54, 0.23)), (1, (0.42, 0.40, 0.15))],
}
PINE_COLS = [(0.10, 0.12, 0.06), (0.24, 0.28, 0.13), (0.40, 0.43, 0.19)]     # olive-dark green (art/02 a*-3 b*17), subtle light tips
PINE_COLS_B = [(0.11, 0.13, 0.07), (0.27, 0.30, 0.15), (0.43, 0.45, 0.21)]
WILLOW_COLS = [(0.52, 0.48, 0.20), (0.62, 0.56, 0.26), (0.72, 0.64, 0.32), (0.44, 0.42, 0.16), (0.78, 0.68, 0.36)]


def paint_willow_thin(w, h, r, cols, n_strands=4):
    """Long thin weeping strands: narrow lanceolate leaves in pairs along a hanging axis (mostly transparent)."""
    cv = Canvas(w, h)
    for s in range(n_strands):
        x0 = w * (0.18 + 0.64 * (s + r.random() * 0.6) / n_strands)
        tt = np.linspace(0, 1, 40)
        xs = x0 + r.normal(0, 4) * tt ** 2 + 2.0 * np.sin(tt * 6 + r.random() * 6)
        ys = 2 + tt * (h - 4) * r.uniform(0.88, 1.0)
        axis = np.stack([xs, ys], -1)
        layer = s / max(1, n_strands - 1)
        cv.line(axis, 1.0, (0.36, 0.30, 0.14), 0.9)
        nleaf = int(h / 10)
        for k in range(nleaf):
            t = k / nleaf
            p = axis[int(t * 39)]
            for side in (-1, 1):
                ang = np.pi - side * r.uniform(0.3, 0.55)
                ln = r.uniform(0.035, 0.05) * h * (1.0 - 0.3 * t)
                c = jitter_col(cols[r.integers(len(cols))], r, 0.08)
                pts = place(leaf_outline("willow", r), p, ang, ln, width_scale=0.95)
                cv.poly(pts, c, shade=leaf_shade(c, r, 0.72 + 0.35 * layer))
    return cv.result()


def paint_fern_frond(w, h, r, cols, golden=0.3):
    """Pinnate fern frond, base at the bottom: rachis + ~22 pairs of narrow pinnae with lobed leaflets,
    angled toward the tip, length tapering to a point (art/02 golden-green fern)."""
    cv = Canvas(w, h)
    base = np.array([w * 0.5, h - 2.0])
    tt = np.linspace(0, 1, 50)
    xs = base[0] + w * 0.04 * np.sin(tt * 2.2)
    ys = base[1] - tt * (h - 8)
    axis = np.stack([xs, ys], -1)
    npairs = 15
    for k in range(npairs):
        t = 0.08 + 0.9 * k / npairs
        j = int(t * 49)
        p = axis[j]
        d = normalize2(axis[min(j + 1, 49)] - axis[max(j - 1, 0)])
        ln = (0.46 * math.sin(np.pi * (0.10 + 0.9 * (1 - t))) ** 0.7 + 0.03) * w
        for side in (-1, 1):
            nrm = np.array([-d[1], d[0]]) * side
            dirv = nrm * 0.72 + d * 0.62
            ang = math.atan2(dirv[1], dirv[0]) + np.pi / 2
            mix = np.clip(golden + 0.35 * t + r.normal(0, 0.08), 0, 1)
            col = jitter_col(np.asarray(cols[0]) * (1 - mix) + np.asarray(cols[1]) * mix, r, 0.05)
            # pinna = midrib + lobed leaflets (pinnules) along it
            q0 = p
            q1 = p + dirv / np.linalg.norm(dirv) * ln
            cv.line([q0, q1], 1.0, np.clip(col * 0.7, 0, 1), 0.9)
            npin = max(3, int(ln / 5))
            for m_ in range(npin):
                f = (m_ + 0.5) / npin
                qq = q0 + (q1 - q0) * f
                pl = (1 - f) ** 0.6 * 0.10 * ln + 1.2
                for s2 in (-1, 1):
                    a2 = ang + s2 * 0.75
                    pts = place(leaf_outline("shrub", r), qq, a2, pl, width_scale=0.9)
                    cv.poly(pts, col, shade=leaf_shade(col, r, 0.8 + 0.25 * f))
    cv.line(axis, 1.8, (0.42, 0.34, 0.15))
    return cv.result()


def normalize2(v):
    return v / (np.linalg.norm(v) + 1e-9)


def paint_bramble_open(w, h, r):
    """Open bramble spray: dark red-brown arching cane, trifoliate leaves green->red, dark-red berry clusters."""
    cv = Canvas(w, h)
    leaf_cols = [(0.28, 0.34, 0.12), (0.36, 0.38, 0.14), (0.46, 0.22, 0.10), (0.52, 0.16, 0.10), (0.40, 0.30, 0.12)]
    tt = np.linspace(0, 1, 20)
    p0 = np.array([w * 0.15, h * 0.85])
    p1 = np.array([w * 0.5, h * 0.05])
    p2 = np.array([w * 0.9, h * 0.55])
    cane = ((1 - tt) ** 2)[:, None] * p0 + (2 * tt * (1 - tt))[:, None] * p1 + (tt ** 2)[:, None] * p2
    cv.line(cane, 2.4, (0.30, 0.12, 0.08))
    for k in range(18):
        p = cane[r.integers(3, 19)] + r.normal(0, 10, 2)
        ang = r.uniform(-2.6, 2.6)
        c = jitter_col(leaf_cols[r.integers(len(leaf_cols))], r, 0.08)
        ln = r.uniform(0.11, 0.16) * w
        for lf in range(3):
            pts = place(leaf_outline("bramble", r), p, ang + (lf - 1) * 0.75, ln * (1.0 if lf == 1 else 0.8))
            cv.poly(pts, c, shade=leaf_shade(c, r, 0.7 + 0.4 * k / 18))
    for k in range(7):
        p = cane[r.integers(4, 18)] + r.normal(0, 14, 2)
        dark = r.random() < 0.6
        for b in range(r.integers(6, 11)):
            q = p + r.normal(0, 5.0, 2)
            col = (0.22, 0.03, 0.06) if dark else (0.55, 0.06, 0.08)
            cv.circle(q, r.uniform(3.0, 4.2), jitter_col(col, r, 0.1))
            cv.circle(q - 1.2, 1.1, (0.85, 0.55, 0.55), 0.55)
    return cv.result()


# ----------------------------------------------------------------------------- palettes from art/02 crown pixels

# art/02 oak crown k-means (painted, lit): (0.83,0.56,0.20) light, (0.62,0.39,0.15) ochre, (0.47,0.28,0.11)
# brown-orange, (0.29,0.19,0.10) shadow.  Albedo = lit tone without the painted shading.
OAK_CLUMP_PAL = {   # iter10: golden (art/02 + art/07/01 compromise): less red than iter09, bright lit tops
    "light": [(3, (0.96, 0.72, 0.22)), (2, (0.98, 0.79, 0.30)), (1, (0.88, 0.60, 0.15))],
    "gold": [(3, (0.91, 0.63, 0.16)), (2, (0.95, 0.70, 0.22)), (1, (0.80, 0.50, 0.12))],
    "ochre": [(3, (0.83, 0.51, 0.13)), (2, (0.88, 0.58, 0.17)), (1, (0.70, 0.40, 0.11))],
    "dark": [(3, (0.66, 0.38, 0.11)), (2, (0.72, 0.44, 0.13)), (1, (0.54, 0.29, 0.09))],
    "red": [(3, (0.82, 0.45, 0.13)), (2, (0.87, 0.52, 0.16)), (1, (0.70, 0.35, 0.10))],   # softer rust accent
}
BIRCH_CLUMP_PAL = {   # iter04: +20% lighter, more yellow (iter03 front L 39 vs 48.6, b* 28 vs 34)
    "light": [(3, (0.88, 0.82, 0.42)), (2, (0.93, 0.87, 0.50)), (1, (0.78, 0.72, 0.34))],
    "mid": [(3, (0.76, 0.70, 0.33)), (2, (0.83, 0.76, 0.38)), (1, (0.66, 0.61, 0.27))],
    "dark": [(3, (0.60, 0.57, 0.25)), (2, (0.68, 0.64, 0.30)), (1, (0.50, 0.48, 0.20))],
    "gold": [(3, (0.93, 0.77, 0.34)), (2, (0.96, 0.83, 0.42)), (1, (0.82, 0.64, 0.26))],
}


def build_atlas(barks=None, seed=7):
    """Paint the whole atlas. barks: dict kind -> albedo (H,W,3) tileable, for the far-LOD strips."""
    A = np.zeros((SIZE, SIZE, 4))

    def put(name, tile):
        x, y, w, h = LAYOUT[name]["rect"]
        A[y:y + h, x:x + w] = tile[:h, :w]

    pal_of = {"light": "light", "gold": "gold", "ochre": "ochre", "dark": "dark", "red": "red"}
    for i, name in enumerate(OAK_CLUMPS):
        key = name.split("_")[2]
        put(name, paint_clump(256, 256, rng(seed + 10 + i), OAK_CLUMP_PAL[pal_of[key]], "oak", n_leaves=200,
                              leaf_len=(0.13, 0.19), radius=0.27))
    for i, (name, key) in enumerate([("oak_dense_gold", "gold"), ("oak_dense_amber", "ochre"),
                                     ("oak_dense_orange", "dark"), ("oak_dense_rust", "red"), ("oak_green_a", "light")]):
        put(name, paint_clump(256, 256, rng(seed + 30 + i), OAK_CLUMP_PAL[key], "oak", n_leaves=360,
                              leaf_len=(0.09, 0.13), radius=0.45))
    for i, name in enumerate(["pine_spray_a", "pine_spray_b", "pine_spray_c", "pine_spray_d", "pine_spray_e"]):
        put(name, paint_pine_spray(256, 256, rng(seed + 50 + i), PINE_COLS if i % 2 == 0 else PINE_COLS_B,
                                   n_side=8 + i % 3, dense=False))
    put("pine_dense_a", paint_pine_dense(256, 256, rng(seed + 60), PINE_COLS))
    put("pine_dense_b", paint_pine_dense(256, 256, rng(seed + 61), PINE_COLS_B))
    put("pine_top", paint_pine_dense(256, 256, rng(seed + 62), PINE_COLS))
    for i, name in enumerate(BIRCH_CLUMPS):
        key = name.split("_")[2]
        put(name, paint_broadleaf_cluster(256, 256, rng(seed + 70 + i), "birch", BIRCH_CLUMP_PAL[key], n_leaves=46,
                                          leaf_len=(0.11, 0.16), attach="top", droop=0.9, spread=0.36,
                                          twig_col=(0.30, 0.24, 0.18)))
    put("birch_dense", paint_clump(256, 256, rng(seed + 79), BIRCH_CLUMP_PAL["mid"], "birch", n_leaves=300,
                                   leaf_len=(0.07, 0.1), radius=0.45))
    put("birch_spare", paint_clump(256, 256, rng(seed + 78), BIRCH_CLUMP_PAL["gold"], "birch", n_leaves=230,
                                   leaf_len=(0.075, 0.11), radius=0.42))
    for i in range(6):
        put(f"willow_strand_{i}", paint_willow_thin(128, 512, rng(seed + 80 + i), WILLOW_COLS, n_strands=3 + i % 2))
    put("willow_top_a", paint_willow_thin(256, 256, rng(seed + 88), WILLOW_COLS, n_strands=6))
    put("willow_dense", paint_clump(256, 256, rng(seed + 89), [(1, c) for c in WILLOW_COLS], "willow", n_leaves=420,
                                    leaf_len=(0.12, 0.2), radius=0.45))
    fern_cols = [(0.50, 0.50, 0.18), (0.74, 0.58, 0.20)]
    put("fern_frond_a", paint_fern_frond(256, 512, rng(seed + 90), fern_cols, golden=0.25))
    put("fern_frond_b", paint_fern_frond(256, 512, rng(seed + 91), fern_cols, golden=0.65))
    put("fern_dense", paint_clump(256, 256, rng(seed + 92), [(1, c) for c in fern_cols], "pinna", n_leaves=260,
                                  leaf_len=(0.16, 0.26), radius=0.45))
    reed_cols = [(0.42, 0.42, 0.16), (0.56, 0.50, 0.22), (0.66, 0.56, 0.30), (0.50, 0.38, 0.18), (0.36, 0.38, 0.14)]
    put("reed_blades_a", paint_blades(256, 512, rng(seed + 100), reed_cols, n=36))
    put("reed_blades_b", paint_blades(256, 512, rng(seed + 101), reed_cols, n=30, height=(0.4, 0.9)))
    put("reed_dense", paint_blades(128, 512, rng(seed + 102), reed_cols, n=40, width=(3, 5)))
    grass_cols = [(0.46, 0.46, 0.18), (0.58, 0.52, 0.22), (0.66, 0.56, 0.30), (0.40, 0.40, 0.14)]
    put("grass_a", paint_blades(256, 256, rng(seed + 110), grass_cols, n=44, height=(0.4, 0.95), width=(3, 5)))
    put("grass_b", paint_blades(256, 256, rng(seed + 111), grass_cols + [(0.70, 0.55, 0.30)], n=40,
                                height=(0.3, 0.8), width=(3, 6)))
    put("grass_dense", paint_blades(256, 256, rng(seed + 112), grass_cols, n=80, height=(0.3, 0.7), width=(3, 5)))
    put("bramble_a", paint_bramble_open(256, 256, rng(seed + 120)))
    put("bramble_b", paint_bramble_open(256, 256, rng(seed + 121)))
    put("bramble_dense", paint_bramble(256, 256, rng(seed + 122), dense=True))
    shrub = [(2, (0.74, 0.34, 0.10)), (2, (0.84, 0.46, 0.14)), (1, (0.58, 0.22, 0.08)), (1, (0.66, 0.50, 0.18))]
    put("shrub_orange", paint_clump(256, 256, rng(seed + 130), shrub, "shrub", n_leaves=200, leaf_len=(0.09, 0.14),
                                    radius=0.40, gap=0.12))
    put("shrub_dense", paint_clump(256, 256, rng(seed + 131), shrub, "shrub", n_leaves=260, leaf_len=(0.08, 0.13)))
    put("moss_clump", paint_moss(256, 256, rng(seed + 140)))
    put("mushroom", paint_mushroom(256, 256, rng(seed + 141)))
    put("fungus_bracket", paint_bracket(256, 256, rng(seed + 142)))
    put("leaf_litter", paint_litter(256, 256, rng(seed + 143)))
    x, y, w, h = LAYOUT["water"]["rect"]
    n = fbm(h, w, 8, 8, seed + 150, 4)
    A[y:y + h, x:x + w, :3] = ramp(n, [(0, (0.14, 0.20, 0.19)), (0.6, (0.22, 0.30, 0.28)), (1, (0.42, 0.50, 0.46))])
    A[y:y + h, x:x + w, 3] = 1.0

    def solid(name, col, noise=0.06):
        x, y, w, h = LAYOUT[name]["rect"]
        n = fbm(h, w, max(1, h // 16), max(1, w // 16), seed + x, 3)
        c = np.asarray(col)[None, None, :] * (1 + (n[..., None] - 0.5) * noise * 4)
        A[y:y + h, x:x + w, :3] = np.clip(c, 0, 1)
        A[y:y + h, x:x + w, 3] = 1.0
    solid("cattail", (0.42, 0.24, 0.12), 0.08)
    solid("reed_stem", (0.50, 0.46, 0.22))
    solid("berry_red", (0.55, 0.06, 0.08))
    solid("berry_dark", (0.18, 0.04, 0.06))
    solid("bramble_cane", (0.30, 0.13, 0.09))
    solid("twig_brown", (0.30, 0.22, 0.14))
    if barks:
        for k in ("oak", "pine", "birch", "hollow", "willow"):
            if k in barks:
                put("bark_" + k, bark_strip(barks[k]))
    return A


def dilate_colour(A, px=12):
    """Bleed RGB into transparent texels (prevents dark mip fringes on alpha-tested cards)."""
    from scipy import ndimage as ndi
    a = A[..., 3]
    known = a > 0.02
    rgb = A[..., :3].copy()
    out = rgb.copy()
    # iterative nearest fill with distance transform indices
    d, (iy, ix) = ndi.distance_transform_edt(~known, return_indices=True)
    fill = rgb[iy, ix]
    m = (~known) & (d <= px * 8)
    out[m] = fill[m]
    out[~known & (d > px * 8)] = rgb[known].mean(0)
    return np.concatenate([out, a[..., None]], -1)
