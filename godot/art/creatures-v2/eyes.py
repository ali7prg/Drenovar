"""Eyes that read as eyes at close range: eyelids that give the almond opening and sit over the eyeball, and an iris
texture (radial fibres, a darker limbal ring, a round or slit pupil, almost no visible sclera) on a wet, very glossy
eyeball. Shared by the four creatures.

lid_prims(...)  - SDF primitives for the upper and lower lids (part of the body: they cover the top and the bottom of
                  the eyeball, so the visible eye is an almond, not a marble)
iris(...)       - per-texel colour / weights for the eyeball texels, in the creature's unwarped coordinates
"""
import numpy as np

from sdf import Prim


def _basis(ax):
    ax = np.asarray(ax, float)
    ax = ax / np.linalg.norm(ax)
    up = np.array([0.0, 1.0, 0.0]) - ax * ax[1]
    up = up / np.linalg.norm(up)
    h = np.cross(up, ax)
    return ax, up, h


def lid_prims(c, r, ax, bone, name, mat="skin", tilt=0.0, upper=0.80, lower=0.92, k=0.008, thick=1.0):
    """Upper and lower lid around an eyeball at `c` (radius r, looking along `ax`). `upper` / `lower`: how far the lid
    centres sit above / below the eye centre in eye radii (smaller = more of the eye covered); `tilt` turns the
    opening about the view axis (positive raises the outer corner on the creature's left side)."""
    a, up, h = _basis(ax)
    ct, st = np.cos(tilt), np.sin(tilt)
    up2 = up * ct + h * st
    h2 = np.cross(up2, a)
    R = np.stack([h2, up2, a], 1)
    c = np.asarray(c, float)
    return [Prim("ellipsoid", bone, k=k, mat=mat, name=f"{name}_lidup", c=c + up2 * r * upper + a * r * 0.12,
                 r=(1.45 * r, 0.62 * r * thick, 0.98 * r), R=R),
            Prim("ellipsoid", bone, k=k, mat=mat, name=f"{name}_lidlo", c=c - up2 * r * lower + a * r * 0.06,
                 r=(1.30 * r, 0.52 * r * thick, 0.92 * r), R=R)]


def iris(P, c, ax, r, col_in, col_out, ring="#120d0a", pupil="round", pupil_size=0.30, iris_ang=1.0, fibres=34,
         noise=None, seed=0):
    """Eyeball texels P (n, 3): returns (rgb linear (n, 3), iris (n,), pupil (n,), near (n,)). The iris spans the cap
    within `iris_ang` radians of the view axis; slit pupils are vertical."""
    a, up, h = _basis(ax)
    rel = P - np.asarray(c, np.float32)
    dist = np.linalg.norm(rel, axis=1)
    near = (dist < r * 1.3).astype(np.float32)
    cosang = np.clip(np.sum(rel * a, 1) / np.maximum(dist, 1e-6), -1.0, 1.0)
    rho = np.arccos(cosang) / iris_ang                 # 0 at the pupil centre, 1 at the iris edge
    u = rel @ h
    v = rel @ up
    th = np.arctan2(v, u)
    jit = 0.0 if noise is None else noise.perlin(P * 140.0, seed) * 1.5
    fib = 0.5 + 0.5 * np.sin(th * fibres + jit)
    fib2 = 0.5 + 0.5 * np.sin(th * fibres * 2.3 + 1.7 + jit * 0.7)

    def sst(e0, e1, x):
        t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
        return t * t * (3 - 2 * t)

    cin, cout, cring = (_lin(col_in), _lin(col_out), _lin(ring))
    t = sst(0.15, 0.95, rho)[:, None]
    col = cin * (1 - t) + cout * t
    col = col * (0.78 + 0.30 * (0.6 * fib + 0.4 * fib2) * sst(0.22, 0.45, rho))[:, None]   # radial fibres
    ring_w = sst(0.80, 0.98, rho) * (1 - sst(1.02, 1.12, rho))
    col = col * (1 - ring_w[:, None] * 0.75) + cring * (ring_w[:, None] * 0.75)              # limbal ring
    beyond = sst(1.0, 1.10, rho)[:, None]                                                      # a sliver of dark sclera
    col = col * (1 - beyond) + _lin("#2a201a") * beyond
    if pupil == "slit":
        # vertical slit: narrow across (u), long along (v)
        across = np.abs(u) / (r * pupil_size * 0.35)
        along = np.abs(v) / (r * 0.85)
        pu = sst(1.0, 0.7, across) * sst(1.0, 0.8, along)
    else:
        pu = sst(pupil_size, pupil_size * 0.80, rho)
    col = col * (1 - pu[:, None]) + _lin("#030303") * pu[:, None]
    irisw = (1 - sst(0.98, 1.05, rho)) * (1 - pu)
    return col.astype(np.float32), (irisw * near).astype(np.float32), (pu * near).astype(np.float32), near


def _lin(hexs):
    c = np.array([int(hexs[i:i + 2], 16) / 255.0 for i in (1, 3, 5)], np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)[None, :]
