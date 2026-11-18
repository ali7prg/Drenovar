"""2-D engraving / relief motifs drawn in metric coordinates -> float masks for propshaders.

Each motif is drawn on a `Canvas(bbox=(u0, v0, u1, v1), px_per_m)`; `mask()` returns (H, W)
float in [0, 1] (row 0 = v1) with a soft bevel (gaussian) so heights get sloped walls.
All shapes are recognisable by luminance (relief/engraving), never by hue alone.
"""
import math

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi


class Canvas:
    def __init__(self, bbox, ppm=6000.0, max_px=1400):
        self.bbox = tuple(float(b) for b in bbox)
        u0, v0, u1, v1 = self.bbox
        s = min(ppm, max_px / max(u1 - u0, v1 - v0))
        self.ppm = s
        self.W = max(8, int(round((u1 - u0) * s)))
        self.H = max(8, int(round((v1 - v0) * s)))
        self.im = Image.new("L", (self.W, self.H), 0)
        self.dr = ImageDraw.Draw(self.im)

    def px(self, pts):
        u0, v0, u1, v1 = self.bbox
        pts = np.asarray(pts, float).reshape(-1, 2)
        x = (pts[:, 0] - u0) * self.ppm
        y = (v1 - pts[:, 1]) * self.ppm
        return [(float(a), float(b)) for a, b in zip(x, y)]

    def w(self, metres):
        return max(1, int(round(metres * self.ppm)))

    def poly(self, pts, fill=255):
        self.dr.polygon(self.px(pts), fill=fill)

    def line(self, pts, width, fill=255, joint="curve"):
        self.dr.line(self.px(pts), fill=fill, width=self.w(width), joint=joint)
        # round caps
        r = width / 2
        for p in (pts[0], pts[-1]):
            self.circle(p, r, fill)

    def circle(self, c, r, fill=255, outline=None, width=0.0):
        (x, y), = self.px([c])
        rr = r * self.ppm
        if outline is None:
            self.dr.ellipse([x - rr, y - rr, x + rr, y + rr], fill=fill)
        else:
            self.dr.ellipse([x - rr, y - rr, x + rr, y + rr], outline=outline, width=self.w(width))

    def ring(self, c, r, width, fill=255):
        self.circle(c, r + width / 2, fill)
        self.circle(c, max(r - width / 2, 0), 0)

    def mask(self, blur_m=0.0006, invert=False):
        a = np.asarray(self.im, np.float32) / 255.0
        if blur_m > 0:
            a = ndi.gaussian_filter(a, blur_m * self.ppm)
        a = np.clip(a, 0, 1)
        return 1 - a if invert else a

    def motif(self, depth, mode="cut", blur_m=0.0006, **kw):
        d = dict(mask=self.mask(blur_m), bbox=self.bbox, depth=depth, mode=mode)
        d.update(kw)
        return d


# ------------------------------------------------------------------------------ curves

def spiral_pts(c, r0, r1, turns, n=300, a0=0.0, sign=1):
    t = np.linspace(0, 1, n)
    a = a0 + sign * t * turns * 2 * math.pi
    r = r0 + (r1 - r0) * t
    return np.stack([c[0] + r * np.cos(a), c[1] + r * np.sin(a)], 1)


def leaf_shape(base, tip, width, n=40):
    base, tip = np.asarray(base, float), np.asarray(tip, float)
    d = tip - base
    L = np.linalg.norm(d)
    t = d / L
    nrm = np.array([-t[1], t[0]])
    s = np.linspace(0, 1, n)
    w = width * np.sin(np.pi * s) ** 0.8 * (1 - 0.25 * s)
    left = base + np.outer(s * L, t) + np.outer(w, nrm)
    right = base + np.outer(s * L, t) - np.outer(w, nrm)
    return np.vstack([left, right[::-1]])


def bezier(p0, p1, p2, n=40):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2 = (np.asarray(p, float) for p in (p0, p1, p2))
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2


def rot2(p, ang, c=(0, 0)):
    p = np.asarray(p, float) - c
    ca, sa = math.cos(ang), math.sin(ang)
    return p @ np.array([[ca, sa], [-sa, ca]]) + c


# ------------------------------------------------------------------------------ ornaments

def celtic_band(cv, pts, width, strands=2, period=None, gap=0.25):
    """Interlace band along a polyline: two sinusoidal strands with over/under breaks."""
    pts = np.asarray(pts, float)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    L = s[-1]
    period = period or width * 2.2
    n = max(60, int(L / (width * 0.08)))
    ss = np.linspace(0, L, n)
    P = np.stack([np.interp(ss, s, pts[:, 0]), np.interp(ss, s, pts[:, 1])], 1)
    T = np.gradient(P, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    Nn = np.stack([-T[:, 1], T[:, 0]], 1)
    sw = width * 0.18
    for k in range(strands):
        ph = 2 * math.pi * ss / period + k * math.pi
        off = np.sin(ph)[:, None] * (width * 0.38)
        Q = P + Nn * off
        # draw dashes, interrupt the strand where it passes under the other one
        under = (np.cos(ph) > 0) if k == 0 else (np.cos(ph) < 0)
        cross = np.abs(np.sin(ph)) < gap
        draw = ~(under & cross)
        start = None
        for i in range(n):
            if draw[i] and start is None:
                start = i
            if (not draw[i] or i == n - 1) and start is not None:
                if i - start > 1:
                    cv.line(Q[start:i], sw)
                start = None
    # border lines
    cv.line(P + Nn * width * 0.5, width * 0.06)
    cv.line(P - Nn * width * 0.5, width * 0.06)


def triquetra(cv, c, r, width, rot=0.0):
    """Three interlaced vesica loops (trinity knot)."""
    c = np.asarray(c, float)
    for k in range(3):
        a = rot + k * 2 * math.pi / 3
        # each loop: arc of circle centred at distance r*0.58 from c
        cc = c + 0.5 * r * np.array([math.cos(a), math.sin(a)])
        t = np.linspace(a + 2 * math.pi / 3 + 0.35, a - 2 * math.pi / 3 + 2 * math.pi - 0.35, 60)
        arc = np.stack([cc[0] + 0.62 * r * np.cos(t), cc[1] + 0.62 * r * np.sin(t)], 1)
        cv.line(arc, width)
    cv.ring(c, r * 0.32, width * 0.8)


def knot_triangle(cv, c, size, width, rot=0.0):
    """Triangular interlace knot (stone rune border ornaments)."""
    c = np.asarray(c, float)
    pts = np.array([[math.cos(rot + k * 2 * math.pi / 3 + math.pi / 2), math.sin(rot + k * 2 * math.pi / 3 + math.pi / 2)]
                    for k in range(3)]) * size
    tri = np.vstack([pts, pts[:1]]) + c
    cv.line(tri, width)
    triquetra(cv, c, size * 0.55, width * 0.8, rot + math.pi / 2)


def sprig3(cv, c, h, width, stem_w=None, veins=True):
    """Three-leaf sprig: vertical stem, one top leaf, two side leaves (bronze seal / cage plaque)."""
    c = np.asarray(c, float)
    stem_w = stem_w or h * 0.06
    base = c + np.array([0.0, -0.5 * h])
    top = c + np.array([0.0, 0.18 * h])
    stem = bezier(base, c + np.array([0.02 * h, -0.1 * h]), top)
    cv.line(stem, stem_w)
    L = leaf_shape(top - np.array([0, 0.02 * h]), c + np.array([0.0, 0.5 * h]), 0.15 * h)
    cv.poly(L)
    for sgn in (-1, 1):
        b = c + np.array([0.0, -0.12 * h])
        t = c + np.array([sgn * 0.42 * h, 0.12 * h])
        cv.poly(leaf_shape(b, t, 0.13 * h))
        if veins:
            cv.line(np.vstack([b, (b + t) / 2 + np.array([0, 0.01 * h])]), width * 0.4, fill=90)
    if veins:
        cv.line(np.vstack([top, c + np.array([0, 0.45 * h])]), width * 0.4, fill=90)


def tree_emblem(cv, c, h, width):
    """Stylised tree (trunk, root fork, branching crown) for plaques, chests, coins."""
    c = np.asarray(c, float)
    trunk_b = c + np.array([0, -0.42 * h])
    trunk_t = c + np.array([0, 0.05 * h])
    cv.line(np.vstack([trunk_b, trunk_t]), width * 1.4)
    for sgn in (-1, 1):
        cv.line(bezier(trunk_b + np.array([0, 0.05 * h]), trunk_b + np.array([sgn * 0.1 * h, 0]),
                       trunk_b + np.array([sgn * 0.22 * h, -0.05 * h])), width * 0.8)
    for k, (dx, dy) in enumerate([(-0.32, 0.32), (-0.18, 0.44), (0.0, 0.5), (0.18, 0.44), (0.32, 0.32),
                                  (-0.38, 0.12), (0.38, 0.12)]):
        tip = c + np.array([dx * h, dy * h])
        cv.line(bezier(trunk_t, c + np.array([dx * 0.4 * h, 0.15 * h]), tip), width * 0.75)
        cv.circle(tip, width * 0.7)


def fleur_sprig(cv, c, h, width):
    """Hexagonal iron-cage socket sprig: central upright leaf + two curled side leaves + base."""
    c = np.asarray(c, float)
    cv.poly(leaf_shape(c + np.array([0, -0.05 * h]), c + np.array([0, 0.48 * h]), 0.13 * h))
    for sgn in (-1, 1):
        cv.poly(leaf_shape(c + np.array([0, -0.12 * h]), c + np.array([sgn * 0.42 * h, 0.22 * h]), 0.11 * h))
        cv.poly(leaf_shape(c + np.array([0, -0.2 * h]), c + np.array([sgn * 0.36 * h, -0.34 * h]), 0.08 * h))
    cv.line(np.vstack([c + np.array([0, -0.45 * h]), c + np.array([0, 0.1 * h])]), width)


# ------------------------------------------------------------------------------ rune-lock glyphs

def glyph(cv, name, c, s, width):
    """Pictograms for rune-lock rings / UI. s = glyph size (m)."""
    c = np.asarray(c, float)
    if name == "mountain":
        pts = np.array([[-0.5, -0.3], [-0.2, 0.25], [-0.02, -0.02], [0.18, 0.38], [0.5, -0.3]]) * s + c
        cv.line(pts, width)
        cv.line(np.array([[-0.28, 0.1], [-0.2, 0.25], [-0.12, 0.12]]) * s + c, width * 0.6)
    elif name in ("river", "waves"):
        for dy in (-0.15, 0.12):
            x = np.linspace(-0.5, 0.5, 40)
            y = 0.1 * np.sin(x * 2 * math.pi * 1.5) + dy
            cv.line(np.stack([x, y], 1) * s + c, width)
    elif name == "leaf":
        cv.poly(leaf_shape(c + np.array([-0.35, -0.3]) * s, c + np.array([0.35, 0.32]) * s, 0.16 * s))
        cv.line(np.array([[-0.45, -0.42], [0.1, 0.12]]) * s + c, width * 0.6, fill=0)
    elif name == "coal":
        pts = np.array([[-0.38, -0.25], [-0.2, 0.18], [0.05, 0.3], [0.32, 0.12], [0.4, -0.22], [0.0, -0.36]]) * s + c
        cv.poly(pts)
        cv.line(np.array([[-0.15, -0.05], [0.12, 0.1], [0.25, -0.12]]) * s + c, width * 0.6, fill=0)
    elif name == "seed":
        cv.poly(leaf_shape(c + np.array([0, -0.4]) * s, c + np.array([0, 0.4]) * s, 0.26 * s))
        cv.line(np.array([[0, -0.3], [0, 0.3]]) * s + c, width * 0.5, fill=0)
    elif name == "tree":
        tree_emblem(cv, c, s, width * 0.7)
    elif name == "sun":
        cv.circle(c, 0.2 * s)
        for k in range(8):
            a = k * math.pi / 4
            cv.line(np.array([[0.3 * math.cos(a), 0.3 * math.sin(a)], [0.47 * math.cos(a), 0.47 * math.sin(a)]]) * s + c,
                    width * 0.7)
    elif name == "stone":
        cv.poly(np.array([[-0.42, -0.35], [0.42, -0.35], [0.36, -0.05], [-0.36, -0.05]]) * s + c)
        cv.poly(np.array([[-0.28, 0.0], [0.28, 0.0], [0.22, 0.22], [-0.22, 0.22]]) * s + c)
        cv.poly(np.array([[-0.13, 0.27], [0.13, 0.27], [0.08, 0.42], [-0.08, 0.42]]) * s + c)
    elif name == "root":
        cv.line(np.array([[0, 0.45], [0, 0.0]]) * s + c, width)
        for dx in (-0.4, -0.15, 0.15, 0.4):
            cv.line(bezier(np.array([0, 0.02]) * s + c, np.array([dx * 0.4, -0.1]) * s + c,
                           np.array([dx, -0.42]) * s + c), width * 0.7)
    elif name == "blank":
        cv.ring(c, 0.18 * s, width * 0.6)
    elif name == "bell":
        pts = np.array([[-0.32, -0.3], [-0.24, 0.0], [-0.18, 0.28], [0.0, 0.38], [0.18, 0.28], [0.24, 0.0],
                        [0.32, -0.3]]) * s + c
        cv.poly(pts)
        cv.circle(c + np.array([0, -0.38]) * s, 0.08 * s)
        cv.line(np.array([[0, 0.38], [0, 0.48]]) * s + c, width * 0.8)
    elif name == "flame":
        out = []
        for t in np.linspace(0, 1, 30):
            a = math.pi * t
            out.append([0.32 * math.sin(a) * (1 - 0.3 * t), -0.4 + 0.85 * t])
        out = np.array(out)
        left = out.copy()
        left[:, 0] *= -1
        cv.poly(np.vstack([out, left[::-1]]) * s + c)
        cv.poly(np.vstack([out * 0.5, (left * 0.5)[::-1]]) * s + c + np.array([0, -0.12 * s]), fill=0)
    else:
        cv.circle(c, 0.3 * s)
