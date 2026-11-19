"""Image-based placement helpers: with the solved painting camera, painted ground contacts are back-projected
onto the ground surface to place parts; painted pixel sizes become metres at that depth; the painted
silhouette outline becomes the ground-base footprint."""
import math

import cv2
import numpy as np
from skimage.measure import points_in_poly

from geo import Geo


def ground_at(cam, u, v, height_fn=None, z=0.0):
    if height_fn is None:
        return cam.on_plane_z(np.array([u + 0.5]), np.array([v + 0.5]), z)[0]
    return cam.on_surface(np.array([u + 0.5]), np.array([v + 0.5]), height_fn, z0=z)[0]


def metres(cam, P, px):
    return px * np.linalg.norm(np.asarray(P) - cam.centre) / cam.f


def footprint(cam, mask, height_fn, ylim=(-30, 30), xlim=(-30, 30), every=2, keep_rows_below=None):
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)[:, 0, :].astype(float)[::every]
    P = cam.on_surface(c[:, 0] + 0.5, c[:, 1] + 0.5, height_fn, z0=0.0)
    ok = np.isfinite(P).all(1)
    P = P[ok]
    P[:, 0] = np.clip(P[:, 0], *xlim)
    P[:, 1] = np.clip(P[:, 1], *ylim)
    return P[:, :2]


def ground_patch(poly, height_fn, step, mat="ground", tag="base", g=None, undulate=0.06, seed=0):
    g = g or Geo(seed)
    xs = np.arange(poly[:, 0].min() - step, poly[:, 0].max() + step * 1.5, step)
    ys = np.arange(poly[:, 1].min() - step, poly[:, 1].max() + step * 1.5, step)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    inside = points_in_poly(np.stack([X.ravel(), Y.ravel()], 1), poly).reshape(X.shape)
    keep = np.zeros((len(xs) - 1, len(ys) - 1), bool)
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            keep[i, j] = inside[i:i + 2, j:j + 2].any()
    V = np.stack([X, Y], -1).astype(float)
    used = np.zeros(X.shape, bool)
    for i, j in zip(*np.nonzero(keep)):
        used[i:i + 2, j:j + 2] = True
    a = poly
    b = np.roll(poly, -1, 0)
    ab = b - a
    for i, j in zip(*np.nonzero(used & ~inside)):
        p = V[i, j]
        t = np.clip(((p - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-9), 0, 1)
        q = a + ab * t[:, None]
        V[i, j] = q[np.argmin(((q - p) ** 2).sum(1))]
    Z = height_fn(V[..., 0], V[..., 1]) + undulate * np.sin(V[..., 0] * 1.7) * np.cos(V[..., 1] * 1.3)
    # outline drops slightly so the patch edge blends into the terrain
    Z = np.where(used & ~inside, Z - 0.03, Z)
    idx = -np.ones(X.shape, int)
    verts = []
    for i, j in zip(*np.nonzero(used)):
        idx[i, j] = len(verts)
        verts.append((V[i, j, 0], V[i, j, 1], Z[i, j]))
    F = [[idx[i, j], idx[i + 1, j], idx[i + 1, j + 1], idx[i, j + 1]] for i, j in zip(*np.nonzero(keep))]
    g.add(np.array(verts), F, mat, tag)
    return g


def place_rocks(g, cam, rocks, height_fn=None, sub=1, seed=0, mat="stone", tag="rock", flat=0.75):
    for k, (u, v, r) in enumerate(rocks):
        P = ground_at(cam, u, v, height_fn)
        rad = metres(cam, P, r)
        g.rock((P[0], P[1], P[2] + rad * 0.12), (rad * 1.1, rad * 0.95, rad * flat), seed=seed + k, sub=sub, mat=mat,
               tag=f"{tag}{k}")
    return g


def place_cards(g, cam, spots, cards, height_fn=None, cross=True, mat="card_veg", tag="veg"):
    for k, (u, v, nm, hpx) in enumerate(spots):
        if nm not in cards:
            continue
        P = ground_at(cam, u, v, height_fn)
        h = metres(cam, P, hpx)
        u0, v0, u1, v1, aw, ah = cards[nm]
        w = h * aw / ah * 1.2
        for yaw in ((0.0, math.pi / 2) if cross else (0.0,)):
            g.card(P - np.array([0, 0, 0.03]), w, h, yaw + k * 0.9, mat, tag, (u0, v0, u1, v1))
    return g
