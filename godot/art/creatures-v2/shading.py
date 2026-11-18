"""Shared procedural surface functions (vectorised over texels)."""
import numpy as np

import noise
from texturing import hexcol, srgb_to_linear


def lin(h):
    return srgb_to_linear(hexcol(h))


def mix(a, b, t):
    t = np.asarray(t, np.float32)
    if t.ndim == 1 and np.ndim(a) >= 1 and np.shape(a)[-1:] == (3,):
        t = t[:, None]
    return a + (b - a) * t


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def tangent_flow(flow, N):
    f = flow - np.sum(flow * N, 1, keepdims=True) * N
    n = np.linalg.norm(f, axis=1, keepdims=True)
    fallback = np.cross(N, np.array([0, 0, 1.0], np.float32))
    f = np.where(n > 1e-4, f / np.maximum(n, 1e-9), fallback / np.maximum(np.linalg.norm(fallback, axis=1,
                                                                                         keepdims=True), 1e-9))
    return f.astype(np.float32)


def fur_height(flow, scale=1.0, octaves=3, clumps=True, seed=0):
    """Strands stretched along `flow` (captured per texel) + clump separation. Returns h(P)."""
    f = flow.astype(np.float32)

    def h(P):
        q = noise.stretch_along(P * (26.0 * scale), f, 8.0)
        out = 0.55 * noise.perlin(q, seed)
        if octaves > 1:
            out += 0.30 * noise.perlin(q * 2.13 + 1.7, seed + 1)
        if octaves > 2:
            out += 0.15 * noise.perlin(q * 4.41 + 3.1, seed + 2)
        if clumps:
            c = noise.stretch_along(P * (7.5 * scale), f, 3.2)
            v = noise.perlin(c, seed + 7)
            out += 0.8 * (np.abs(v) - 0.35)
        return out * 0.0028
    return h


def fur_streaks(P, flow, scale=1.0, seed=11):
    """Albedo streaks of individual hairs: thin, high-contrast lines along `flow` (no clumps), -1..1. The coat under
    the fur cards reads as hair instead of marbled skin."""
    q = noise.stretch_along(P * (70.0 * scale), flow.astype(np.float32), 14.0)
    a = noise.perlin(q, seed)
    b = noise.perlin(q * 1.93 + 2.3, seed + 1)
    return np.clip((0.65 * a + 0.35 * b) * 2.2, -1.0, 1.0)


def rune_glyph(u, v, size):
    """Distance (m) to a spiral rune with a stem and two leaves, centred at (0,0); `size` = outer radius."""
    r = np.sqrt(u * u + v * v)
    th = np.arctan2(v, u)
    b = size / (2.2 * 2 * np.pi)
    a = 0.12 * size
    k = (r - a) / (2 * np.pi * b) - th / (2 * np.pi)
    d_sp = np.abs(k - np.round(k)) * 2 * np.pi * b
    d_sp = np.where((r > a * 0.6) & (r < size * 1.02), d_sp, 9.0)
    # stem down from the spiral, then two leaves
    def seg(px, py, ax, ay, bx, by):
        pa_x, pa_y, ba_x, ba_y = px - ax, py - ay, bx - ax, by - ay
        h = np.clip((pa_x * ba_x + pa_y * ba_y) / (ba_x * ba_x + ba_y * ba_y), 0, 1)
        return np.hypot(pa_x - h * ba_x, pa_y - h * ba_y)
    d = np.minimum(d_sp, seg(u, v, 0.0, -size, 0.0, -2.3 * size))
    for sgn in (-1, 1):
        d = np.minimum(d, seg(u, v, 0.0, -1.55 * size, 0.55 * size * sgn, -1.05 * size))
        d = np.minimum(d, seg(u, v, 0.55 * size * sgn, -1.05 * size, 0.62 * size * sgn, -0.55 * size))
    d = np.minimum(d, np.abs(np.hypot(u, v + 2.45 * size) - 0.18 * size))
    return d


def rune_field(P, N, runes):
    """runes: list of (centre, side_axis, up_axis, size). Returns (line mask 0..1, glow 0..1)."""
    line = np.zeros(len(P), np.float32)
    glow = np.zeros(len(P), np.float32)
    for c, side, up, size in runes:
        side = np.asarray(side, np.float32) / np.linalg.norm(side)
        up = np.asarray(up, np.float32) / np.linalg.norm(up)
        right = np.cross(up, side)
        rel = P - np.asarray(c, np.float32)
        facing = np.clip((np.sum(N * side, 1) - 0.2) / 0.4, 0, 1)
        depth = np.abs(np.sum(rel * side, 1))
        near = (depth < 0.45).astype(np.float32) * facing
        u = np.sum(rel * right, 1)
        v = np.sum(rel * up, 1)
        dd = rune_glyph(u, v, size)
        w = 0.010 + 0.004 * size / 0.2
        line = np.maximum(line, near * (1 - sstep(w * 0.55, w, dd)))
        glow = np.maximum(glow, near * np.exp(-dd / (w * 2.5)) * 0.55)
    return line, glow


def bark(P, flow, scale=1.0, seed=3):
    """Bark: plates of Voronoi cells with deep cracks, grain along `flow`. Returns (height, crack, cell)."""
    q = noise.stretch_along(P * 9.0 * scale, flow, 2.6)
    f1, f2, cid = noise.worley(q, seed)
    crack = 1 - sstep(0.0, 0.11, f2 - f1)
    grain = noise.perlin(noise.stretch_along(P * 60.0 * scale, flow, 9.0), seed + 1)
    h = (1 - crack) * 0.004 + grain * 0.0007 - crack * 0.003
    return h, crack, cid


def moss_mask(P, N, amount=0.5, seed=5):
    up = N[:, 1]
    n = noise.fbm(P * 6.0, 4, seed=seed)
    return sstep(0.25, 0.6, up * 0.7 + n * 0.8 + (amount - 0.5))
