"""Fur clumps as real geometry: tapered, curved, flattened spikes rooted on the body surface.

Lengths are fitted so that clump tips stay inside the reference silhouettes of the chosen
views (visual-hull test), with random shortening for a jagged natural edge.
"""
import math

import numpy as np

import gbody


class Clump:
    __slots__ = ("root", "pts", "width", "flat", "up", "group", "bone_hint", "length")

    def __init__(self, root, pts, width, flat, up, group, bone_hint=None):
        self.root = root
        self.pts = pts
        self.width = width
        self.flat = flat
        self.up = up
        self.group = group
        self.bone_hint = bone_hint
        self.length = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())


def _unit(v):
    v = np.asarray(v, float)
    return v / max(np.linalg.norm(v), 1e-12)


def grow(root, normal, direction, length, bend, n_pts=4, sink=0.015):
    """Quadratic curve from slightly inside the surface: p(t) = r + d L t + bend L t^2."""
    t = np.linspace(0.0, 1.0, n_pts)
    base = np.asarray(root) - np.asarray(normal) * sink
    d = _unit(direction)
    pts = base[None] + d[None] * (length * t)[:, None] + np.asarray(bend)[None] * (length * t * t)[:, None]
    return pts


def fit_length(root, direction, bend, views, max_len, min_len, step=0.012):
    """Longest length (<= max_len) whose curve stays inside all view masks (sampled)."""
    if not views:
        return max_len
    L = min_len
    best = min_len
    while L <= max_len + 1e-9:
        pts = grow(root, np.zeros(3), direction, L, bend, n_pts=8, sink=0.0)
        if gbody.inside_masks(pts[-3:], views).all():
            best = L
        else:
            break
        L += step
    return best


def make_clumps(group, roots, normals, dir_fn, rng, views, max_len, min_len=0.03, width=(0.05, 0.08),
                flat=0.45, bend_fn=None, up_fn=None, jag=(0.72, 1.0), n_pts=4, bone_hint=None,
                fit=True):
    out = []
    for i in range(len(roots)):
        r, nrm = roots[i], normals[i]
        d = _unit(dir_fn(r, nrm, rng))
        bend = bend_fn(r, nrm, d, rng) if bend_fn else np.zeros(3)
        ml = max_len(r) if callable(max_len) else max_len
        L = fit_length(r, d, bend, views, ml, min_len) if fit else ml
        L *= rng.uniform(*jag)
        if L < min_len:
            continue
        pts = grow(r, nrm, d, L, bend, n_pts=n_pts)
        w = rng.uniform(*width)
        up = up_fn(r, nrm, d) if up_fn else nrm
        out.append(Clump(r, pts, w, flat, up, group, bone_hint))
    return out


def clump_mesh(c, sides=3, width_scale=1.0, taper=0.9):
    n = len(c.pts)
    t = np.linspace(0, 1, n)
    rx = c.width * width_scale * np.maximum(1.0 - taper * t, 0.08)
    ry = rx * c.flat
    return gbody.tube(c.pts, rx, ry, sides=sides, up=c.up, tip=True)


def clumps_to_mesh(clumps, sides=3, width_scale=1.0):
    meshes = [clump_mesh(c, sides=sides, width_scale=width_scale) for c in clumps]
    if not meshes:
        return np.zeros((0, 3)), np.zeros((0, 3), int), np.zeros((0, 3, 2)), np.zeros(0, int)
    return gbody.merge(meshes)


def lod_subset(clumps, keep, rng, prefer_long=True):
    """Pick a fraction of clumps for lower LODs (longest first so the silhouette survives)."""
    if keep >= 1.0:
        return list(clumps)
    n = max(1, int(round(len(clumps) * keep)))
    if prefer_long:
        L = np.array([c.length for c in clumps]) * rng.uniform(0.7, 1.3, len(clumps))
        idx = np.argsort(-L)[:n]
    else:
        idx = rng.choice(len(clumps), n, replace=False)
    return [clumps[i] for i in sorted(idx)]


# --------------------------------------------------------------------------- hard details

def claw(root, fwd, length=0.11, base_r=0.022, curl=1.0, sides=5, n=6, lat=(1, 0, 0)):
    """Curved, laterally flattened claw: leaves the toe forward and hooks down to the ground."""
    fwd = _unit(fwd)
    down = np.array([0.0, 0.0, -1.0])
    t = np.linspace(0, 1, n)
    ang = t * math.radians(75) * curl
    pts = np.array([root + (fwd * np.sin(a) * 0.0 + 0) for a in ang])
    # arc in the fwd/down plane
    R = length / max(math.radians(75) * curl, 1e-3)
    pts = np.array([root + fwd * (R * math.sin(a)) + down * (R * (1 - math.cos(a))) for a in ang])
    rx = base_r * (1 - 0.92 * t)
    ry = rx * 0.62
    return gbody.tube(pts, ry, rx, sides=sides, up=lat, tip=True)


def horn(base, direction, curve, length, base_r, sides=6, n=7, ridges=0.0):
    """Curved horn / tusk / antler tine: tube along a quadratic curve, optional growth ridges."""
    t = np.linspace(0, 1, n)
    d = _unit(direction)
    pts = base[None] + d[None] * (length * t)[:, None] + np.asarray(curve)[None] * (length * t * t)[:, None]
    r = base_r * (1 - 0.88 * t ** 0.9)
    if ridges:
        r = r * (1 + ridges * np.cos(t * math.pi * 2 * 3.5) * (1 - t))
    return gbody.tube(pts, r, sides=sides, up=(0, 0, 1) if abs(d[2]) < 0.9 else (0, 1, 0), tip=True)
