"""Boss arena (lf_boss_arena) modules: SDF limestone cliffs, fossil rib/skull wall, pillars, floor,
bone scatter, stream/waterfall, banner geometry; procedural texturing helpers (numpy).

Module frame (cliffs/fossil): pivot at the inner-face base centre, local +Y points AWAY from the arena
centre, the inner face looks toward -Y; the module follows an arc of radius R_IN around (0,-R_IN,0).
"""
import math
import os
import sys

import numpy as np
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from frlib import sdf, texproj  # noqa: E402

R_IN = 17.5          # inner wall radius (m)
FLOOR_R = 17.8


# ------------------------------------------------------------------------------------ noise
def vnoise(P, freq, seed=0, octaves=3):
    return texproj.fbm(P, freq=freq, octaves=octaves, seed=seed)


def displaced(prim, amp, freq, seed):
    fn0 = prim.fn

    def fn(P):
        return fn0(P) + amp * (texproj.fbm(P, freq=freq, octaves=3, seed=seed) - 0.5) * 2.0
    p = sdf.Prim(fn, prim.lo - amp, prim.hi + amp, name=prim.name, k=prim.k)
    return p


def arc_pos(alpha, r, z=0.0):
    """Module-local position at angle alpha (rad, + to local +X) and radius r from the arena centre."""
    return np.array([r * math.sin(alpha), r * math.cos(alpha) - R_IN, z])


def rbox(c, half, yaw=0.0, tilt=(0.0, 0.0), rounding=0.12, k=0.12, name="block"):
    return sdf.box(c, half, rot=np.array([tilt[0], tilt[1], yaw]), rounding=rounding, k=k, name=name)


# ------------------------------------------------------------------------------------ cliffs
CLIFF_VARIANTS = {
    # name: (arc_len m, height range, depth range, seed, ledge, fallen blocks)
    "a": (8.4, (5.2, 6.6), (2.6, 3.4), 11, False, 2),
    "b": (8.4, (4.3, 5.6), (2.4, 3.2), 23, True, 3),
    "c": (8.4, (3.4, 4.8), (2.2, 3.0), 37, False, 5),
}


def cliff_parts(variant):
    L, (h0, h1), (d0, d1), seed, ledge, nfall = CLIFF_VARIANTS[variant]
    rng = np.random.default_rng(seed)
    half_ang = (L / 2) / R_IN
    parts = []
    a = -half_ang - 0.02
    while a < half_ang + 0.02:
        w = rng.uniform(0.9, 1.7)
        da = w / R_IN
        ac = a + da / 2
        h = rng.uniform(h0, h1) * (0.85 + 0.15 * math.cos(ac / half_ang * 1.3))
        dep = rng.uniform(d0, d1)
        r_mid = R_IN + dep / 2 + rng.uniform(-0.25, 0.15)
        c = arc_pos(ac, r_mid, h / 2 - 0.3)
        parts.append(rbox(c, (w / 2 + 0.06, dep / 2, h / 2 + 0.3), yaw=-ac,
                          tilt=(rng.uniform(-0.05, 0.05), rng.uniform(-0.04, 0.04)), rounding=0.18, k=0.10,
                          name="column"))
        # stepped top blocks
        if rng.random() < 0.6:
            hh = rng.uniform(0.5, 1.1)
            c2 = arc_pos(ac + rng.uniform(-0.2, 0.2) * da, r_mid + rng.uniform(0.0, 0.5), h + hh / 2 - 0.15)
            parts.append(rbox(c2, (w * 0.4, dep * 0.35, hh / 2), yaw=-ac + rng.uniform(-0.3, 0.3), rounding=0.15,
                              k=0.12, name="cap"))
        a += da
    if ledge:
        parts.append(rbox(arc_pos(0.05, R_IN - 0.3, 1.6), (2.4, 0.7, 0.35), yaw=0.0, rounding=0.15, k=0.25,
                          name="ledge"))
    # scree / fallen blocks on the arena side
    for i in range(nfall + 4):
        ac = rng.uniform(-half_ang, half_ang)
        s = rng.uniform(0.25, 0.75) if i >= nfall else rng.uniform(0.6, 1.2)
        c = arc_pos(ac, R_IN - rng.uniform(0.1, 1.2) * (1.5 if i < nfall else 1.0), s * 0.55)
        parts.append(rbox(c, (s, s * rng.uniform(0.6, 0.9), s * rng.uniform(0.5, 0.8)), yaw=rng.uniform(0, 3),
                          tilt=(rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3)), rounding=0.12, k=0.08, name="scree"))
    # vegetation lumps on top (coloured as moss/shrub by the texture)
    for i in range(6):
        ac = rng.uniform(-half_ang * 0.9, half_ang * 0.9)
        parts.append(sdf.ellipsoid(arc_pos(ac, R_IN + rng.uniform(0.8, 2.4), h0 + rng.uniform(0.0, h1 - h0) * 0.6),
                                   (rng.uniform(0.4, 0.8), rng.uniform(0.4, 0.8), rng.uniform(0.25, 0.5)), k=0.15,
                                   name="shrub"))
    return parts


def strata(fn, seed, spacing=0.65, depth=0.045):
    """Horizontal bedding grooves + vertical joint emphasis (limestone)."""
    def f(P):
        z = P[..., 2] + 0.15 * (texproj.fbm(P, 0.35, 2, seed) - 0.5)
        ph = (z / spacing) % 1.0
        groove = np.exp(-((ph - 0.5) / 0.06) ** 2)
        return fn(P) + depth * groove
    return f


def build_rock_field(parts, lo, hi, voxel, seed, sub=(), disp=0.07, disp_freq=1.3, strata_on=True):
    F = sdf.Field(lo, hi, voxel)
    for p in parts:
        F.apply(p, op="union")
    for p in sub:
        F.apply(p, op="subtract")
    # noise displacement over the full grid + bedding
    d = F.d
    noise = F.evaluate_full(lambda P: (texproj.fbm(P, disp_freq, 3, seed) - 0.5) * 2 * disp
                            + (texproj.fbm(P, disp_freq * 3.1, 2, seed + 5) - 0.5) * 0.6 * disp)
    F.d = (d + noise).astype(np.float32)
    if strata_on:
        F.d = F.d + F.evaluate_full(lambda P: 0.045 * np.exp(-((((P[..., 2] + 0.15 * (
            texproj.fbm(P, 0.35, 2, seed) - 0.5)) / 0.62) % 1.0 - 0.5) / 0.07) ** 2)).astype(np.float32)
    F.intersect(lambda P: -(P[..., 2] + 0.25), k=0.0)  # cut below ground
    F.smooth(0.7)
    return F


# ------------------------------------------------------------------------------------ fossil wall
FOSSIL_LEN = 11.0


def fossil_parts(seed=51):
    rng = np.random.default_rng(seed)
    half = (FOSSIL_LEN / 2) / R_IN
    parts = []
    a = -half - 0.02
    while a < half + 0.02:
        w = rng.uniform(1.0, 1.8)
        da = w / R_IN
        ac = a + da / 2
        h = rng.uniform(4.6, 5.8)
        dep = rng.uniform(2.6, 3.4)
        c = arc_pos(ac, R_IN + dep / 2 + 0.1, h / 2 - 0.3)
        parts.append(rbox(c, (w / 2 + 0.06, dep / 2, h / 2 + 0.3), yaw=-ac,
                          tilt=(rng.uniform(-0.04, 0.04), rng.uniform(-0.04, 0.04)), rounding=0.2, k=0.12, name="column"))
        a += da
    # matrix (bulging rock) around the bones
    parts.append(sdf.ellipsoid(arc_pos(-0.06, R_IN + 0.35, 1.9), (3.6, 1.1, 1.7), k=0.4, name="matrix"))
    parts.append(sdf.ellipsoid(arc_pos(0.19, R_IN + 0.2, 1.5), (1.9, 1.0, 1.3), k=0.4, name="matrix"))
    for i in range(6):
        ac = rng.uniform(-half, half)
        s = rng.uniform(0.3, 0.7)
        parts.append(rbox(arc_pos(ac, R_IN - rng.uniform(0.2, 1.0), s * 0.5), (s, s * 0.8, s * 0.6),
                          yaw=rng.uniform(0, 3), tilt=(rng.uniform(-0.3, 0.3), 0.2), rounding=0.1, k=0.08, name="scree"))
    return parts


def rib_prims():
    """Six curved ribs half-embedded in the wall (ribcage seen from the side)."""
    out = []
    for i in range(6):
        ac = -0.20 + i * 0.052
        base = arc_pos(ac, R_IN + 0.15, 4.2 - 0.15 * i)
        pts = []
        n = 9
        for k in range(n):
            s = k / (n - 1)
            # arc bulging toward the arena (-local Y), sweeping down and slightly back
            off = np.array([0.35 * s, -0.95 * math.sin(math.pi * s * 0.9), -3.3 * s + 0.4 * s * s])
            pts.append(base + off * np.array([1, 1, 1.0 - 0.06 * i]))
        radii = [0.13 - 0.05 * (k / (n - 1)) for k in range(n)]
        out += sdf.chain(pts, radii, k=0.03, name="rib")
    # spine (vertebral column) along the top
    for i in range(9):
        ac = -0.23 + i * 0.04
        out.append(sdf.ellipsoid(arc_pos(ac, R_IN + 0.05, 4.35 - 0.1 * i), (0.22, 0.2, 0.17), k=0.05, name="vertebra"))
    return out


def skull_prims():
    """Theropod fossil skull (~2.3 m) embedded at the right end, left side facing the arena."""
    c = arc_pos(0.24, R_IN - 0.15, 2.2)
    out, sub = [], []
    # cranium + snout (box-ish), lower jaw slightly open
    out.append(rbox(c + [0.0, 0.0, 0.15], (1.1, 0.30, 0.42), yaw=-0.24, tilt=(0.0, 0.08), rounding=0.18, k=0.08,
                    name="skull"))
    out.append(rbox(c + [-0.85, -0.02, 0.02], (0.45, 0.26, 0.30), yaw=-0.24, rounding=0.16, k=0.12, name="skull"))
    out.append(rbox(c + [0.05, 0.02, -0.42], (1.0, 0.24, 0.13), yaw=-0.24, tilt=(0.0, -0.10), rounding=0.08, k=0.05,
                    name="skull"))
    # fenestrae through the side (orbit, antorbital, lateral temporal), nostril
    for off, r in (([0.35, 0, 0.30], (0.20, 0.5, 0.18)), ([-0.25, 0, 0.18], (0.32, 0.5, 0.17)),
                   ([0.75, 0, 0.10], (0.18, 0.5, 0.24)), ([-1.05, 0, 0.22], (0.09, 0.5, 0.06))):
        sub.append(sdf.ellipsoid(c + np.array(off), r, k=0.03, name="fenestra"))
    # teeth rows
    for i in range(10):
        x = -1.15 + i * 0.2
        out.append(sdf.round_cone(c + [x, -0.20, -0.25], c + [x - 0.03, -0.22, -0.48], 0.045, 0.012, k=0.01,
                                  name="tooth"))
        out.append(sdf.round_cone(c + [x + 0.1, -0.16, -0.32], c + [x + 0.12, -0.18, -0.12], 0.04, 0.01, k=0.01,
                                  name="tooth"))
    return out, sub


# ------------------------------------------------------------------------------------ pillars
PILLAR_VARIANTS = {"a": (4.4, 1.5, 61), "b": (2.4, 2.2, 67)}


def pillar_parts(variant):
    H, W, seed = PILLAR_VARIANTS[variant]
    rng = np.random.default_rng(seed)
    parts = []
    z = 0.0
    while z < H:
        hh = rng.uniform(0.7, 1.3)
        sh = 1.0 - 0.35 * (z / H)
        parts.append(rbox([rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12), z + hh / 2 - 0.1],
                          (W / 2 * sh * rng.uniform(0.75, 1.0), W / 2 * sh * rng.uniform(0.65, 0.95), hh / 2),
                          yaw=rng.uniform(-0.4, 0.4), tilt=(rng.uniform(-0.06, 0.06), rng.uniform(-0.06, 0.06)),
                          rounding=0.14, k=0.08, name="block"))
        z += hh * 0.92
    if variant == "b":
        parts.append(rbox([1.1, 0.3, 0.55], (0.75, 0.6, 0.6), yaw=0.5, rounding=0.15, k=0.15, name="block"))
    for i in range(5):
        s = rng.uniform(0.18, 0.4)
        ang = rng.uniform(0, 2 * math.pi)
        r = W * 0.7 + rng.uniform(0, 0.5)
        parts.append(rbox([r * math.cos(ang), r * math.sin(ang), s * 0.4], (s, s * 0.8, s * 0.6), yaw=ang,
                          rounding=0.08, k=0.05, name="scree"))
    parts.append(sdf.ellipsoid([0.2, -0.3, H * 0.92], (0.45, 0.4, 0.22), k=0.12, name="shrub"))
    return parts


# ------------------------------------------------------------------------------------ procedural colour
LIME = np.array([0.66, 0.62, 0.55])
LIME_WARM = np.array([0.70, 0.58, 0.42])
MOSS = np.array([0.36, 0.40, 0.17])
MOSS_Y = np.array([0.62, 0.55, 0.20])
DIRT = np.array([0.45, 0.36, 0.26])
BONE = np.array([0.80, 0.72, 0.56])


def rock_colour(P, N, seed, top_z, bone_mask=None, ao=None):
    n1 = vnoise(P, 0.45, seed)
    n2 = vnoise(P * np.array([1, 1, 0.25]), 2.2, seed + 3)      # vertical streaks
    n3 = vnoise(P, 6.0, seed + 7, octaves=2)
    col = LIME[None] * (1 - n1[:, None] * 0.5) + LIME_WARM[None] * (n1[:, None] * 0.5)
    band = 0.5 + 0.5 * np.sin(P[:, 2] * 9.5 + 3 * n1)
    col *= (0.90 + 0.10 * band)[:, None]
    vert = np.clip(1 - np.abs(N[:, 2]) * 1.4, 0, 1)
    col *= (1 - 0.22 * vert * np.clip(n2 - 0.35, 0, 1) * 2.2)[:, None]       # water stains
    col *= (0.88 + 0.24 * n3)[:, None]
    up = np.clip((N[:, 2] - 0.45) / 0.4, 0, 1)
    high = np.clip((P[:, 2] - (top_z - 1.6)) / 1.2, 0, 1)
    mossy = np.clip(up * (0.55 + 0.6 * high) * (0.6 + 0.8 * vnoise(P, 1.1, seed + 11)), 0, 1)
    mcol = MOSS[None] * (1 - n3[:, None]) + MOSS_Y[None] * n3[:, None]
    col = col * (1 - mossy[:, None]) + mcol * mossy[:, None]
    base = np.clip((0.45 - P[:, 2]) / 0.45, 0, 1)
    col = col * (1 - 0.5 * base[:, None]) + DIRT[None] * 0.5 * base[:, None]
    if bone_mask is not None:
        bcol = BONE[None] * (0.82 + 0.25 * n3[:, None]) * (1 - 0.15 * vnoise(P, 3.0, seed + 19)[:, None])
        col = col * (1 - bone_mask[:, None]) + bcol * bone_mask[:, None]
    if ao is not None:
        col *= (0.45 + 0.55 * ao)[:, None]
    rough = 0.88 - 0.05 * n3 + 0.05 * mossy
    if bone_mask is not None:
        rough = rough * (1 - bone_mask) + 0.72 * bone_mask
    return np.clip(col, 0, 1), np.clip(rough, 0, 1), mossy
