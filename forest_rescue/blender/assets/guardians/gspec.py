"""Shared helpers for guardian species specs (sheet mapping, hooves, plates, clump groups)."""
import math

import numpy as np

import gbody
import gfur
import gref
from frlib import sdf


class Sheet:
    """Side-view sheet mapping. facing='left': head to image-left (Tenerys); 'right': head right."""

    def __init__(self, ppm, ground, cx, facing):
        self.ppm, self.ground, self.cx, self.facing = ppm, ground, cx, facing

    def S(self, x, y, lat=0.0):
        sgn = 1.0 if self.facing == "left" else -1.0
        return np.array([lat, sgn * (x - self.cx) / self.ppm, (self.ground - y) / self.ppm])

    def xy(self, P):
        P = np.atleast_2d(P)
        sgn = 1.0 if self.facing == "left" else -1.0
        return P[:, 1] * self.ppm * sgn + self.cx, self.ground - P[:, 2] * self.ppm


def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def roots(hv, hf, rng, n, weight_fn, min_dist):
    pts, nrm, _ = gbody.sample_surface(hv, hf, n * 6, rng, weight_fn=weight_fn)
    if len(pts) == 0:
        return pts, nrm
    keep = gbody.poisson_thin(pts, min_dist, rng)[:n]
    return pts[keep], nrm[keep]


def shadow_fn(row0, chroma=0.024):
    def fn(m, img):
        from scipy import ndimage as ndi
        bg = np.median(img[:4].reshape(-1, 3), axis=0)
        d = img - bg
        luma = d @ np.array([0.299, 0.587, 0.114])
        ch = np.sqrt(((d - luma[..., None]) ** 2).sum(2))
        sh = (ch < chroma) & (luma > -0.47) & (luma < -0.02)
        sh[:row0] = False
        m = m & ~sh
        m = ndi.binary_opening(m, iterations=1)
        lab, n = ndi.label(m)
        if n:
            sizes = ndi.sum(m, lab, range(1, n + 1))
            m = lab == (int(np.argmax(sizes)) + 1)
        return m
    return fn


def rock_plate(center, normal, up, size, thick, sides=6, jitter=0.18, rng=None, ridge=0.35):
    """Faceted stone scute: jittered polygon base (sunk) with a raised off-centre apex.
    Same topology for every call with the same `sides` (UV islands can be reused)."""
    rng = rng or np.random.default_rng(0)
    n = gfur._unit(normal)
    u = np.asarray(up, float) - np.dot(up, n) * n
    if np.linalg.norm(u) < 1e-6:
        u = np.cross(n, [1.0, 0, 0])
    u = gfur._unit(u)
    v = np.cross(n, u)
    base = []
    for i in range(sides):
        a = 2 * math.pi * i / sides
        r = size * (1 + rng.uniform(-jitter, jitter))
        base.append(center + (u * math.cos(a) * r * 1.15 + v * math.sin(a) * r) - n * thick * 0.25)
    mid = []
    for i in range(sides):
        a = 2 * math.pi * (i + 0.5) / sides
        r = size * 0.55 * (1 + rng.uniform(-jitter, jitter))
        mid.append(center + (u * math.cos(a) * r * 1.1 + v * math.sin(a) * r) + n * thick * 0.75)
    apex = center + u * size * ridge * 0.4 + n * thick * 1.15
    V = np.array(base + mid + [apex])
    F = []
    for i in range(sides):
        j = (i + 1) % sides
        F.append((i, j, sides + i))
        F.append((j, sides + j, sides + i))
        F.append((sides + i, sides + j, 2 * sides))
    F = np.array(F)
    # planar-projection UVs in metres (island scale handled by the atlas)
    uv2 = np.stack([(V - center) @ u, (V - center) @ v], 1) + size * 1.5
    return V, F, uv2[F]


def hoof(fetlock, tip_dir, length, width, lat=(1, 0, 0), cloven=True):
    """Hoof as real geometry: two digit capsules (cloven) or one (solid), ground at z=0."""
    out = []
    lat = np.asarray(lat, float)
    offs = (-0.28, 0.28) if cloven else (0.0,)
    d = gfur._unit(tip_dir)
    for o in offs:
        a = fetlock + lat * o * width
        b = np.array([a[0], a[1], 0.0]) + np.array([0, d[1], 0]) * length
        pts = gbody.catmull([a, a + (b - a) * 0.5 + np.array([0, 0, 0.02]), b + np.array([0, 0, 0.03])], 5)
        r = np.linspace(width * (0.42 if cloven else 0.6), width * (0.36 if cloven else 0.5), 5)
        out.append(gbody.tube(pts, r, r * 0.8, sides=6, up=(0, 0, 1), tip=False, cap_base=False))
    return out


def stance(sk, legs, sheet, targets, girdle=None, toe_down=0.08):
    """Leg IK to a drawn side-view stance.  targets: leg -> ((x, y) paw-ball/fetlock sheet px,
    (dx, dy) sheet direction from wrist/hock to that joint)."""
    import grig
    pose = sk.fk()
    girdle = girdle or {}
    for leg, ((x, y), (dx, dy)) in targets.items():
        ch = legs[leg]
        side = leg[-1]
        lat = sk.head(ch[4])[0]
        tgt = sheet.S(x, y, lat)
        ed = sheet.S(x + dx * 10, y + dy * 10, lat) - tgt
        front = leg.startswith("fore")
        pole = np.array([0, 1.0, 0]) if front else np.array([0, -1.0, 0])
        toe = sk.tail(ch[4]) - sk.head(ch[4])
        rr = None
        if ch[0] is not None and leg in girdle:
            Rw = grig.rot_axis([1, 0, 0], math.radians(girdle[leg]))
            Rb = sk.rest[ch[0]][:3, :3]
            rr = Rb.T @ Rw @ Rb
        grig.solve_leg(sk, pose, ch, tgt, ed, toe / np.linalg.norm(toe), pole, root_rot=rr)
    return pose
