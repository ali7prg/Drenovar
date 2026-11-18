"""Reusable part builders for the character specs (torso, sleeves, cuffs, legs, boots, hair, hoods)."""
import math

import numpy as np

from frlib import sdf as fsdf

import humans_geo as G
import humans_sdf as H


def torso(stations, cls="shirt", y=0.012, name="torso", disp=None):
    """stations: [(z, (wl, wr) or w, (df, db) or d, n)]"""
    z0, z1 = stations[0][0], stations[-1][0]
    return H.vloft(z0, z1, [(z, w, d, n) for z, w, d, n in stations], cls=cls, bone=None, k=0.0, name=name, y=y,
                   disp=disp)


def folds_disp(amp=0.004, freq=(26.0, 9.0), seed=0, zband=None):
    """Soft cloth folds: vertical-ish ridges (cos in angle) modulated along z."""
    rng = np.random.default_rng(seed)
    ph = rng.uniform(0, 6.28, 4)

    def disp(P, t, x, y):
        ang = np.arctan2(x, -y)
        d = amp * (0.6 * np.sin(ang * freq[1] + ph[0] + P[..., 2] * 3.0) +
                   0.4 * np.sin(ang * freq[1] * 1.7 + ph[1] - P[..., 2] * 5.0)) * (0.5 + 0.5 * np.sin(P[..., 2] * freq[0] + ph[2]))
        if zband is not None:
            d = d * np.clip((zband[1] - P[..., 2]) / 0.05, 0, 1) * np.clip((P[..., 2] - zband[0]) / 0.05, 0, 1)
        return d
    return disp


def shoulders(J, S_, sx, r=(0.085, 0.080, 0.085), cls="shirt", off=0.018):
    sh = J[f"{S_}UpperArm"]
    return [H.ellipsoid(sh + np.array([sx * off, 0.0, -0.010]), r, cls=cls, bone=f"{S_}UpperArm", k=0.05),
            H.capsule(J[f"{S_}Shoulder"] + np.array([0, 0.02, 0.01]), sh + np.array([0, 0.02, 0.03]), 0.050, 0.056,
                      cls=cls, bone=f"{S_}Shoulder", k=0.05)]


def upper_arm(J, S_, radii, cls="shirt", name="sleeve"):
    return H.limb(J[f"{S_}UpperArm"], J[f"{S_}LowerArm"], radii, cls=cls, bone=f"{S_}UpperArm", k=0.03,
                  name=f"{name}_{S_}")


def forearm(J, S_, radii, cls="skin", name="forearm"):
    return H.limb(J[f"{S_}LowerArm"], J[f"{S_}Hand"], radii, cls=cls, bone=f"{S_}LowerArm", k=0.02,
                  name=f"{name}_{S_}")


def rolled_cuff(J, S_, t=0.86, R=0.058, r=0.028, cls="shirt", second=True):
    sh, el = J[f"{S_}UpperArm"], J[f"{S_}LowerArm"]
    ax = (el - sh) / np.linalg.norm(el - sh)
    out = [H.torus(sh + (el - sh) * t, R, r, axis=ax, cls=cls, bone=f"{S_}UpperArm", k=0.012)]
    if second:
        out.append(H.torus(sh + (el - sh) * min(t + 0.11, 1.02), R * 0.95, r * 0.9, axis=ax, cls=cls,
                           bone=f"{S_}LowerArm", k=0.012))
    return out


def forearm_cuff(J, S_, t, R, r, cls="shirt"):
    el, wr = J[f"{S_}LowerArm"], J[f"{S_}Hand"]
    ax = (wr - el) / np.linalg.norm(wr - el)
    return H.torus(el + (wr - el) * t, R, r, axis=ax, cls=cls, bone=f"{S_}LowerArm", k=0.01)


def thigh(J, S_, radii, cls="trousers", top=0.04, name="thigh"):
    hp, kn = J[f"{S_}UpperLeg"], J[f"{S_}LowerLeg"]
    return H.limb(hp + np.array([0, 0, top]), kn, radii, cls=cls, bone=f"{S_}UpperLeg", k=0.04, name=f"{name}_{S_}")


def shin(J, S_, radii, cls="trousers", name="shin"):
    return H.limb(J[f"{S_}LowerLeg"], J[f"{S_}Foot"], radii, cls=cls, bone=f"{S_}LowerLeg", k=0.03,
                  name=f"{name}_{S_}")


def boot(J, S_, sx, L, top_z, **kw):
    return H.boot_parts(J, S_, sx, L, top_z, **kw)


# --------------------------------------------------------------------------- hair

def tapered_shell(ctx, region, thick, taper=0.006, extra=None):
    """Shell on the head surface whose thickness fades to 0 at the region boundary (seamless
    union with the skin).  region(P) < 0 inside (metres); thick in head units (x scale)."""
    lm = ctx.lm
    s = lm["scale"]
    O = lm["origin"]

    def fn(P):
        r = region(P)
        w = np.clip(-r / (taper * s), 0.0, 1.0)
        w = w * w * (3 - 2 * w)
        t = thick * s * w
        if extra is not None:
            t = t + extra(P) * w
        return np.maximum(ctx.head_fn(P) - t, r - 0.002)
    return fn


def hair_shell(ctx, thick=0.016, region=None, cls="hair", top_extra=0.0, back_extra=0.0, name="hair_shell",
               taper=0.004):
    lm = ctx.lm
    s = lm["scale"]
    reg = region or G.hair_region(lm)
    O = lm["origin"]

    def extra(P):
        Q = (np.asarray(P, float) - O) / s
        return (top_extra * np.clip((Q[..., 2] - 0.03) / 0.08, 0, 1)
                + back_extra * np.clip((Q[..., 1] - 0.08) / 0.08, 0, 1)) * s
    fn = tapered_shell(ctx, reg, thick, taper=taper, extra=extra)
    return H.tag(fsdf.Prim(fn, O - 0.17, O + 0.22), cls=cls, bone="Head", k=0.003, name=name)


def bun(ctx, offset=(0.0, 0.16, 0.06), radii=(0.040, 0.034, 0.036), cls="hair"):
    lm = ctx.lm
    c = G.head_frame_point(lm, *offset)
    return H.ellipsoid(c, np.array(radii) * lm["scale"], cls=cls, bone="Head", k=0.012)


def strands(ctx, pts_list, r0=0.006, r1=0.003, cls="hair", bone="Head"):
    """Loose locks: chains of tapering round cones through head-frame points."""
    lm = ctx.lm
    out = []
    for pts in pts_list:
        W = [G.head_frame_point(lm, *p) for p in pts]
        n = len(W)
        for i in range(n - 1):
            ra = r0 + (r1 - r0) * i / max(n - 1, 1)
            rb = r0 + (r1 - r0) * (i + 1) / max(n - 1, 1)
            out.append(H.tag(fsdf.round_cone(W[i], W[i + 1], ra * lm["scale"], rb * lm["scale"]), cls=cls,
                             bone=bone, k=0.004))
    return out


def beard_region(ctx, top=-0.040, slope=0.28, back=0.085, mouth_open=0.0045, chin_drop=0.0):
    lm = ctx.lm
    s = lm["scale"]
    O = lm["origin"]
    mz = (lm["mouth"][2] - O[2]) / s

    def region(P):
        Q = (np.asarray(P, float) - O) / s
        x, y, z = Q[..., 0], Q[..., 1], Q[..., 2]
        r1 = z - (top + slope * np.maximum(np.abs(x) - 0.020, 0) - 0.010)
        r2 = y - back
        mouth = np.maximum(np.abs(x) - 0.021, np.abs(z - mz + 0.002) - mouth_open)
        return np.maximum(np.maximum(r1, r2), -mouth) * s
    return region


def beard_prims(ctx, thick=0.016, curls=60, seed=21, cls="beard", mustache=True, rmin=0.006, rmax=0.010,
                lift=0.012, taper=0.010, **reg_kw):
    lm = ctx.lm
    s = lm["scale"]
    O = lm["origin"]
    region = beard_region(ctx, **reg_kw)
    fn = tapered_shell(ctx, region, thick, taper=taper)
    prims = [H.tag(fsdf.Prim(fn, O - 0.14, O + 0.14), cls=cls, bone="Jaw", k=0.003, name="beard_shell")]
    if curls:
        inner = lambda P: region(P) + 0.006 * s
        cl = G.curls(lm, ctx.head_fn, inner, curls, rmin * s, rmax * s, lift * s, seed=seed, bone="Jaw", cls=cls)
        for c in cl:
            c.k = 0.008
        prims += cl
    if mustache:
        m = lm["mouth"]
        for sx in (1, -1):
            prims.append(H.capsule(m + np.array([0, -0.005, 0.011]) * 1.0, m + np.array([sx * 0.026, 0.004, -0.003]),
                                   0.0070, 0.0055, cls=cls, bone="Head", k=0.008))
    return prims


def headwear_piece(name, ctx, outer_fn, inner_fn, lo, hi, cls, rule, voxel=0.0025, extra_prims=()):
    """Shell (outer minus inner) meshed separately: caps, hoods, helmets."""
    def fn(P):
        return np.maximum(outer_fn(P), -inner_fn(P))
    prims = [H.tag(fsdf.Prim(fn, lo, hi), cls=cls, bone="Head", k=0.0)] + list(extra_prims)
    return G.sdf_piece(name, prims, lo, hi, voxel, cls, rule, smooth=0.6)
