"""Procedural painted vegetation sprites (fern fronds, grass tufts, weeds, ivy) for alpha-tested cards.
Colours are sampled from the reference painting so the cards keep the painted palette."""
import math

import cv2
import numpy as np


def _poly(img, alpha, pts, col):
    p = np.round(np.asarray(pts) * 4).astype(np.int32)
    cv2.fillPoly(img, [p], col, cv2.LINE_AA, shift=2)
    cv2.fillPoly(alpha, [p], 1.0, cv2.LINE_AA, shift=2)


def leaf(img, alpha, base, tip, width, col):
    base = np.asarray(base, float)
    tip = np.asarray(tip, float)
    d = tip - base
    L = np.linalg.norm(d) + 1e-9
    n = np.array([-d[1], d[0]]) / L
    t = np.linspace(0, 1, 9)
    w = width * np.sin(np.pi * np.clip(t, 0, 1)) ** 0.7
    left = base + d * t[:, None] + n * w[:, None]
    right = base + d * t[:, None] - n * w[:, None]
    _poly(img, alpha, np.concatenate([left, right[::-1]]), col)


def fern(size, palette, rng):
    img = np.zeros((size, size, 3), np.float32)
    a = np.zeros((size, size), np.float32)
    cx = size / 2
    for f in range(7):
        ang = math.radians(rng.uniform(-70, 70))
        L = size * rng.uniform(0.55, 0.9)
        base = np.array([cx + rng.uniform(-10, 10), size - 4])
        curve = rng.uniform(-0.25, 0.25)
        pts = []
        for s in np.linspace(0, 1, 14):
            a_s = ang + curve * s * 2
            pts.append(base + L * s * np.array([math.sin(a_s), -math.cos(a_s)]))
        pts = np.array(pts)
        col = palette[rng.integers(len(palette))] * rng.uniform(0.85, 1.1)
        for i in range(1, len(pts) - 1):
            s = i / len(pts)
            seg = pts[i + 1] - pts[i]
            nrm = np.array([-seg[1], seg[0]]) / (np.linalg.norm(seg) + 1e-9)
            ll = size * 0.13 * (1 - s) ** 0.8 + 3
            for sd in (-1, 1):
                tip = pts[i] + (nrm * sd * 0.9 + seg / (np.linalg.norm(seg) + 1e-9) * 0.5) * ll
                leaf(img, a, pts[i], tip, ll * 0.22, tuple(float(c) for c in np.clip(col * rng.uniform(0.85, 1.15), 0, 1)))
        cv2.polylines(img, [np.round(pts * 4).astype(np.int32)], False, tuple(float(c) for c in col * 0.7), 2, cv2.LINE_AA, shift=2)
    return img, a


def grass(size, palette, rng, blades=26, tall=0.95):
    img = np.zeros((size, size, 3), np.float32)
    a = np.zeros((size, size), np.float32)
    for b in range(blades):
        x0 = size / 2 + rng.normal(0, size * 0.12)
        h = size * rng.uniform(0.35, tall)
        lean = rng.normal(0, size * 0.15)
        base = np.array([x0, size - 2])
        tip = np.array([x0 + lean, size - 2 - h])
        col = palette[rng.integers(len(palette))] * rng.uniform(0.8, 1.15)
        leaf(img, a, base, tip, rng.uniform(2.0, 4.0), tuple(float(c) for c in np.clip(col, 0, 1)))
    return img, a


def weed(size, palette, rng):
    img, a = grass(size, palette, rng, blades=10, tall=0.9)
    for k in range(8):   # small yellow flower heads / seed tips
        p = (int(size / 2 + rng.normal(0, size * 0.18)), int(size * rng.uniform(0.08, 0.45)))
        col = tuple(float(c) for c in np.clip(palette[-1] * 1.25, 0, 1))
        cv2.circle(img, p, int(rng.uniform(3, 6)), col, -1, cv2.LINE_AA)
        cv2.circle(a, p, int(rng.uniform(3, 6)), 1.0, -1, cv2.LINE_AA)
    return img, a


def ivy(size, palette, rng):
    """Hanging ivy strand: stem down the card with heart-ish leaves."""
    img = np.zeros((size, size, 3), np.float32)
    a = np.zeros((size, size), np.float32)
    for strand in range(3):
        x = size / 2 + rng.normal(0, size * 0.15)
        y = 2.0
        while y < size - 6:
            ny = y + rng.uniform(6, 12)
            nx = x + rng.normal(0, 4)
            cv2.line(img, (int(x), int(y)), (int(nx), int(ny)), tuple(float(c) for c in palette[0] * 0.6), 2, cv2.LINE_AA)
            cv2.line(a, (int(x), int(y)), (int(nx), int(ny)), 1.0, 2, cv2.LINE_AA)
            for sd in (-1, 1):
                if rng.random() < 0.8:
                    tip = np.array([nx + sd * rng.uniform(8, 16), ny + rng.uniform(-2, 8)])
                    col = palette[rng.integers(len(palette))] * rng.uniform(0.8, 1.15)
                    leaf(img, a, (nx, ny), tip, rng.uniform(4, 7), tuple(float(c) for c in np.clip(col, 0, 1)))
            x, y = nx, ny
    return img, a


KINDS = {"fern": fern, "grass": grass, "weed": weed, "ivy": ivy}


def atlas(specs, palette, size=1024, seed=3):
    """specs: list of (name, kind). Returns rgba atlas and rects {name: (u0,v0,u1,v1, aspect_w, aspect_h)}."""
    rng = np.random.default_rng(seed)
    n = len(specs)
    cols = int(math.ceil(math.sqrt(n)))
    cell = size // cols
    out = np.zeros((size, size, 4), np.float32)
    rects = {}
    pal = np.asarray(palette, np.float32)
    for i, (name, kind) in enumerate(specs):
        img, a = KINDS[kind](cell, pal, rng)
        # painted shading: darker toward the base
        g = np.linspace(0.62, 1.05, cell)[:, None, None]
        img = np.clip(img * g[::1], 0, 1)
        r, c = divmod(i, cols)
        out[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell, :3] = img
        out[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell, 3] = a
        rects[name] = (c * cell / size, 1 - (r + 1) * cell / size, (c + 1) * cell / size, 1 - r * cell / size, 1.0, 1.0)
    from frlib import texproj
    known = out[..., 3] > 0.5
    out[..., :3] = texproj.fill(out[..., :3], known)
    out[..., 3] = (out[..., 3] > 0.5).astype(np.float32)
    return out, rects


def palette_from(img, mask=None, k=5):
    px = img.reshape(-1, 3) if mask is None else img[mask]
    r, g, b = px[:, 0], px[:, 1], px[:, 2]
    veg = px[(g > b + 0.05) & (g > 0.2)]
    if len(veg) < 20:
        return np.array([[0.36, 0.42, 0.16], [0.5, 0.55, 0.22], [0.62, 0.62, 0.28], [0.3, 0.35, 0.14], [0.75, 0.68, 0.3]])
    veg = veg[np.argsort(veg.sum(1))]
    qs = [veg[int(len(veg) * q)] for q in (0.15, 0.35, 0.55, 0.75, 0.92)]
    return np.array(qs)
