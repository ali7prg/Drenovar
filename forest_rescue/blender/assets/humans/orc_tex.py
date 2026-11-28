"""Hand-authored painted albedo for lf_orc_warden (no reference art: replaces reference projection).

Per texel (rest-pose world position P, normal N, texture class, piece, aux pattern coordinates,
baked AO, mesh curvature) the colour is painted procedurally in three layers, all functions of
3-D position so UV seams never show:
  1. class palette + material detail (skin mottling / veins / scars / face paint, fur strands and
     clumps, leather grain + stitching + edge wear, cloth weave / folds / grime, linen wrap bands,
     iron hammering / rust / edge wear / rivets, bone grime / cracks, carved staff, crystal facets);
  2. the painted light of the human atlases: warm key from the upper left of the front view
     (SP.LIGHT), cool shadow side, a touch of sky on up-facing planes - baked *lightly* because the
     game adds lambert x paintedLightMix (0.4) on top;
  3. occlusion (Cycles AO bake), cavity darkening / convex edge highlights, dry-brush stroke noise.
"""
import math

import numpy as np

import spec_lf_orc_warden as SP
from frlib import texproj

CLASSES = ["skin", "eye", "tusk", "hair", "fur", "leather", "boot", "cloth_dark", "cloth_red", "linen", "iron",
           "bone", "staff_bone", "staff_iron", "staff_leather", "crystal"]
CID = {c: i for i, c in enumerate(CLASSES)}


def C(name):
    return np.array(SP.PALETTE[name], float)


def unit(v):
    v = np.asarray(v, float)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    t = np.asarray(t, float)
    if t.ndim == 1:
        t = t[:, None]
    return a * (1 - t) + b * t


def fbm(P, f, oct_=3, seed=0, aniso=None):
    Q = P * (np.asarray(aniso, float) if aniso is not None else 1.0)
    return texproj.fbm(Q, freq=f, octaves=oct_, seed=seed)


def vnoise(P, f, seed=0):
    return texproj.value_noise(P, freq=f, seed=seed)


def flow_frame_noise(P, flow, f_along, f_across, seed=0, oct_=2):
    """Strand / stroke noise: low frequency along `flow`, high across it."""
    flow = unit(flow)
    a = np.cross(flow, np.array([0.31, 0.53, 0.79]))
    a = unit(a)
    b = np.cross(flow, a)
    Q = np.stack([(P * flow).sum(1) * f_along, (P * a).sum(1) * f_across, (P * b).sum(1) * f_across], 1)
    return texproj.fbm(Q, freq=1.0, octaves=oct_, seed=seed)


def seg_dist(P, a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    u = b - a
    t = np.clip(((P - a) @ u) / (u @ u), 0, 1)
    return np.linalg.norm(P - (a + t[:, None] * u), axis=1), t


# --------------------------------------------------------------------------- class painters

def p_skin(P, N, aux, ao, cv, ctx, pid):
    o, s = ctx["head_o"], ctx["head_s"]
    q = (P - o) / s
    n = len(P)
    base = np.tile(C("skin"), (n, 1))
    m1 = fbm(P, 10.0, 4, 1)
    m2 = fbm(P, 2.2, 3, 2)
    col = mix(base, C("skin_warm"), ss(0.48, 0.78, m1) * 0.42)
    col = col * (0.88 + 0.22 * m2)[:, None]
    # warmer upper body, cooler / grimier extremities, small dark spots
    col = col * (1 + np.outer(ss(1.0, 1.7, P[:, 2]) - 0.5, np.array([0.035, 0.0, -0.035])))
    grime = (1 - ss(0.35, 0.75, P[:, 2])) * 0.35
    col = mix(col, np.array([0.29, 0.27, 0.20]), grime * (0.5 + 0.5 * fbm(P, 9.0, 2, 13)))
    spots = ss(0.80, 0.90, vnoise(P, 170.0, 14))
    col = mix(col, C("skin_dark"), spots * 0.22)
    col = mix(col, C("skin_dark"), ss(0.55, 0.85, fbm(P, 16.0, 2, 3)) * 0.18)
    col = col * (0.97 + 0.06 * vnoise(P, 380.0, 4))[:, None]
    head = (q[:, 2] > -0.26) & (np.abs(q[:, 0]) < 0.24) & (P[:, 2] > 1.78)
    # warm, slightly reddish extremities: ears, nose, brow top, knuckles, elbows, knees
    warm = np.zeros(n)
    warm = np.maximum(warm, head * ss(0.088, 0.13, np.abs(q[:, 0])) * ss(-0.06, 0.0, q[:, 2] + 0.03))
    warm = np.maximum(warm, head * np.exp(-(((q[:, 0]) / 0.03) ** 2 + ((q[:, 2] + 0.046) / 0.025) ** 2
                                           + ((q[:, 1] + 0.15) / 0.03) ** 2)))
    for S in ("Left", "Right"):
        for b, r in (("LowerArm", 0.075), ("LowerLeg", 0.10)):
            d = np.linalg.norm(P - ctx["J"][f"{S}{b}"], axis=1)
            warm = np.maximum(warm, 0.8 * (1 - ss(0.4 * r, r, d)))
        for tip in ctx["knuckles"][S]:
            d = np.linalg.norm(P - tip, axis=1)
            warm = np.maximum(warm, 0.7 * (1 - ss(0.008, 0.022, d)))
    col = mix(col, C("skin_warm") * np.array([1.06, 0.94, 0.90]), warm * 0.65)
    # forearm veins (ridged noise, cooler and darker, subtle)
    arm = np.zeros(n)
    for S in ("Left", "Right"):
        d, t = seg_dist(P, ctx["J"][f"{S}LowerArm"], ctx["J"][f"{S}Hand"])
        arm = np.maximum(arm, (d < 0.085) * ss(0.05, 0.3, t) * (1 - ss(0.75, 0.95, t)))
    rid = 1.0 - np.abs(2.0 * fbm(P, 1.0, 3, 6, aniso=(34.0, 34.0, 10.0)) - 1.0)
    vein = ss(0.92, 0.985, rid) * arm
    col = mix(col, C("skin_dark") * np.array([0.9, 1.0, 1.10]), vein * 0.30)
    # scars (pale with darker rims)
    for a, b in ctx["scars"]:
        d, _ = seg_dist(P, a, b)
        col = mix(col, C("skin_dark"), (1 - ss(0.0035, 0.0065, d)) * 0.25)
        col = mix(col, np.array([0.60, 0.52, 0.44]), (1 - ss(0.0015, 0.0034, d)) * 0.8)
    # face: deep sockets / under-brow shadow, lids, bags, folds, wrinkles, lips, nostrils, war paint
    if head.any():
        fr = head & (q[:, 1] < -0.06)
        for sx in (1.0, -1.0):
            de = np.sqrt((q[:, 0] - sx * 0.040) ** 2 + ((q[:, 2] + 0.004) / 0.8) ** 2)
            col = mix(col, C("skin_dark") * 0.72, fr * (1 - ss(0.015, 0.033, de)) * 0.60)
            col = mix(col, np.array([0.09, 0.08, 0.07]), fr * (1 - ss(0.0098, 0.0128, de)) * 0.85)
            bag = np.abs(np.sqrt((q[:, 0] - sx * 0.040) ** 2 + (q[:, 2] + 0.006) ** 2) - 0.019)
            col = mix(col, C("skin_dark"), fr * (q[:, 2] < -0.012) * (1 - ss(0.0015, 0.0045, bag)) * 0.35)
            d_nl, _ = seg_dist(np.stack([q[:, 0], q[:, 2]], 1), np.array([sx * 0.030, -0.052]),
                               np.array([sx * 0.054, -0.108]))
            col = mix(col, C("skin_dark") * 0.85, fr * (q[:, 1] < -0.10) * (1 - ss(0.002, 0.006, d_nl)) * 0.45)
        # charcoal eye-mask smudge from temple to temple (dry brush): shadowed, menacing eyes
        em = np.sqrt((q[:, 0] / 0.088) ** 2 + ((q[:, 2] + 0.004) / (0.020 + 0.010 * (np.abs(q[:, 0]) / 0.088))) ** 2)
        dry = ss(0.20, 0.65, fbm(P, 1.0, 2, 8, aniso=(160.0, 160.0, 40.0)))
        col = mix(col, np.array([0.11, 0.105, 0.095]), fr * (1 - ss(0.75, 1.05, em)) * (0.38 + 0.35 * dry))
        brow_w = (q[:, 2] > 0.032) & (q[:, 2] < 0.080) & (q[:, 1] < -0.05)
        wr_ = np.sin(q[:, 2] * 2 * math.pi / 0.0115 + 0.5 * np.sin(q[:, 0] * 45.0))
        col = mix(col, C("skin_dark"), head * brow_w * ss(0.80, 0.97, wr_) * (1 - ss(0.03, 0.07, np.abs(q[:, 0]))) * 0.35)
        lipl = np.sqrt((q[:, 0] / 0.056) ** 2 + ((q[:, 1] + 0.150) / 0.026) ** 2 + ((q[:, 2] + 0.113) / 0.019) ** 2)
        lipu = np.sqrt((q[:, 0] / 0.050) ** 2 + ((q[:, 1] + 0.146) / 0.021) ** 2 + ((q[:, 2] + 0.089) / 0.0155) ** 2)
        lip = head * (1 - ss(0.85, 1.15, np.minimum(lipl, lipu))) * (q[:, 1] < -0.125)
        col = mix(col, C("lip"), lip * 0.62)
        mz = -0.1005 - 0.007 * (q[:, 0] / 0.046) ** 2
        mouth = (1 - ss(0.0018, 0.0036, np.abs(q[:, 2] - mz))) * (1 - ss(0.042, 0.050, np.abs(q[:, 0]))) * (q[:, 1] < -0.12)
        col = mix(col, np.array([0.09, 0.07, 0.06]), head * mouth * 0.90)
        for sx in (1.0, -1.0):
            dn = np.linalg.norm((q - np.array([sx * 0.019, -0.149, -0.064])) / np.array([1.0, 1.4, 1.0]), axis=1)
            col = mix(col, np.array([0.10, 0.08, 0.07]), head * (1 - ss(0.0045, 0.0080, dn)) * 0.85)
        # shaved scalp: soft stubble shadow above the ears
        scalp = head * ss(0.015, 0.060, q[:, 2]) * ss(-0.10, -0.05, q[:, 1])
        stub = ss(0.45, 0.75, vnoise(P, 520.0, 9))
        col = mix(col, np.array([0.20, 0.215, 0.17]), scalp * (0.18 + 0.20 * stub))
    # claws / nails at the finger tips
    for S in ("Left", "Right"):
        for tip, nback in ctx["tips"][S]:
            d = np.linalg.norm(P - tip, axis=1)
            back = (N @ nback) > -0.2
            nail = (1 - ss(0.010, 0.016, d)) * back
            col = mix(col, np.array([0.34, 0.30, 0.21]), nail * 0.9)
    return col


def p_eye(P, N, aux, ao, cv, ctx, pid):
    o, s = ctx["head_o"], ctx["head_s"]
    q = (P - o) / s
    sx = np.where(q[:, 0] > 0, 1.0, -1.0)
    dx = q[:, 0] - sx * 0.040
    dz = q[:, 2] + 0.004
    r = np.sqrt(dx ** 2 + dz ** 2)
    col = np.tile(np.array([0.44, 0.35, 0.23]), (len(P), 1))
    col = mix(col, C("eye"), 1 - ss(0.0042, 0.0054, r))
    col = mix(col, np.array([0.05, 0.04, 0.03]), 1 - ss(0.0016, 0.0024, r))
    col = mix(col, np.array([0.28, 0.16, 0.06]), (1 - ss(0.0048, 0.0058, r)) * ss(0.0040, 0.0050, r))
    col = mix(col, np.array([0.95, 0.92, 0.82]), 1 - ss(0.0006, 0.0011, np.sqrt((dx + 0.0016) ** 2 + (dz - 0.0018) ** 2)))
    col = col * (1.0 - 0.5 * ss(0.001, 0.007, dz))[:, None]
    return col


def p_tusk(P, N, aux, ao, cv, ctx, pid):
    t = np.clip(aux[:, 0] / 0.075, 0, 1)
    col = mix(np.tile(np.array([0.55, 0.46, 0.33]), (len(P), 1)), np.array([0.86, 0.82, 0.70]), ss(0.05, 0.75, t))
    col = col * (0.96 + 0.05 * np.sin(aux[:, 0] * 420.0))[:, None]
    crack = ss(0.90, 0.97, 1.0 - np.abs(2 * fbm(P, 1.0, 2, 12, aniso=(60.0, 60.0, 240.0)) - 1))
    return mix(col, np.array([0.35, 0.28, 0.20]), crack * 0.6)


def p_hair(P, N, aux, ao, cv, ctx, pid):
    n = len(P)
    bun = ctx["bun"]
    path = ctx["braid"]
    # flow: toward the bun on the ridge, along the braid path below
    flow = unit(bun - P)
    dmin = np.full(n, 9.0)
    tan = np.zeros((n, 3))
    for a, b in zip(path[:-1], path[1:]):
        d, _ = seg_dist(P, a, b)
        better = d < dmin
        dmin = np.where(better, d, dmin)
        tan[better] = unit(b - a)
    on_braid = dmin < 0.05
    flow[on_braid] = tan[on_braid]
    col = np.tile(C("hair"), (n, 1))
    st = np.zeros(n)
    for f0 in (np.array([0, 0, 1.0]), np.array([1.0, 0, 0]), np.array([0, 1.0, 0])):
        w = np.abs(flow @ f0)
        st += w * flow_frame_noise(P, f0, 8.0, 160.0, seed=21)
    st /= np.maximum(np.abs(flow).sum(1), 1e-6)
    col = col * (0.75 + 0.6 * st)[:, None]
    sheen = ss(0.55, 0.8, st) * ss(0.2, 0.7, N @ unit(np.array(SP.LIGHT)))
    col = mix(col, np.array([0.30, 0.26, 0.22]), sheen * 0.55)
    # leather tie around the base of the bun
    db = np.abs(np.linalg.norm((P - bun) / np.array([1.0, 1.0, 1.0]), axis=1) - 0.05)
    tie = (np.abs(P[:, 2] - (bun[2] - 0.035)) < 0.010) & (np.linalg.norm(P - bun, axis=1) < 0.07)
    col = mix(col, C("leather_worn"), tie * 0.85)
    return col


def p_fur(P, N, aux, ao, cv, ctx, pid):
    n = len(P)
    down = np.array([0.0, 0.0, -1.0])
    tdown = unit(down - (N @ down)[:, None] * N)
    col = np.tile(C("fur"), (n, 1))
    strands = flow_frame_noise(P, np.array([0, 0, 1.0]), 9.0, 120.0, seed=31, oct_=3)
    fine = flow_frame_noise(P, np.array([0, 0, 1.0]), 20.0, 330.0, seed=32, oct_=2)
    col = mix(col, C("fur_tip"), ss(0.50, 0.85, strands) * 0.75)
    col = col * (0.82 + 0.36 * fine)[:, None]
    f1, f2 = texproj.voronoi(P * np.array([1.0, 1.0, 0.45]), freq=26.0, seed=33)
    border = 1 - ss(0.0, 0.012, f2 - f1)
    col = col * (1 - 0.30 * border)[:, None]
    # lighter tips toward the ragged hem and on outward / upward tufts; grey guard hairs
    hem = ctx["hem_fn"](P)
    tip = 1 - ss(0.0, 0.09, P[:, 2] - hem)
    col = mix(col, C("fur_tip") * 1.1, tip * 0.45)
    grey = ss(0.72, 0.86, fbm(P, 11.0, 2, 34))
    g = col.mean(1, keepdims=True)
    col = mix(col, np.repeat(g, 3, 1) * 1.25, grey * 0.5)
    col = col * (0.92 + 0.10 * fbm(P, 3.0, 2, 35))[:, None]
    return col


def p_leather(P, N, aux, ao, cv, ctx, pid):
    n = len(P)
    names = ctx["pieces"]
    pname = np.array(names)[pid]
    col = np.tile(C("leather"), (n, 1))
    col = col * (0.88 + 0.24 * fbm(P, 9.0, 3, 41))[:, None]
    col = col * (0.95 + 0.08 * vnoise(P, 600.0, 42))[:, None]
    worn = ss(0.15, 0.6, cv) * 0.7
    is_strap = np.char.startswith(pname.astype(str), "harness") | (pname == "belt")
    edge = is_strap * (1 - ss(0.04, 0.16, np.minimum(aux[:, 1], 1 - aux[:, 1])))
    col = mix(col, C("leather_worn"), np.clip(worn + edge * 0.6, 0, 1))
    scratch = ss(0.88, 0.96, 1 - np.abs(2 * fbm(P, 1.0, 2, 43, aniso=(25.0, 160.0, 160.0)) - 1))
    col = mix(col, C("leather_worn") * 1.15, scratch * 0.35)
    # stitching along straps (pale thread dots near both edges)
    harn = np.char.startswith(pname.astype(str), "harness")
    for v0 in (0.16, 0.84):
        dots = (np.abs(aux[:, 1] - v0) < 0.05) & (np.mod(aux[:, 0], 0.016) < 0.008)
        col = mix(col, np.array([0.58, 0.50, 0.37]), harn * dots * 0.8)
    # belt: iron studs along the middle row
    belt = pname == "belt"
    stud = np.sqrt(((np.mod(aux[:, 0] * 18.0, 1.0) - 0.5) / 0.22) ** 2 + ((aux[:, 1] - 0.5) / 0.16) ** 2) < 1.0
    col = mix(col, np.array([0.40, 0.40, 0.40]), belt * stud * 0.9)
    # tassets: tooled border lines
    tas = np.char.startswith(pname.astype(str), "tasset")
    border = (np.minimum(aux[:, 0], 1 - aux[:, 0]) < 0.10) & (np.minimum(aux[:, 0], 1 - aux[:, 0]) > 0.06)
    col = mix(col, C("leather") * 0.55, tas * border * 0.8)
    return col


def p_boot(P, N, aux, ao, cv, ctx, pid):
    n = len(P)
    col = np.tile(C("boot"), (n, 1))
    col = col * (0.88 + 0.24 * fbm(P, 10.0, 3, 51))[:, None]
    sx = np.where(P[:, 0] > 0, 1.0, -1.0)
    band = np.mod((P[:, 2] + 0.35 * (P[:, 1] + 0.1)) / 0.050, 1.0)
    strap = (band < 0.30) & (P[:, 2] > 0.06)
    col = mix(col, C("leather_worn") * 0.95, strap * 0.55)
    col = mix(col, np.array([0.10, 0.07, 0.05]), ((band < 0.04) | ((band > 0.28) & (band < 0.32))) * (P[:, 2] > 0.06) * 0.6)
    mud = 1 - ss(0.025, 0.075, P[:, 2] + 0.02 * fbm(P, 30.0, 2, 52))
    col = mix(col, np.array([0.30, 0.27, 0.21]), mud * 0.65)
    col = mix(col, C("leather_worn"), ss(0.2, 0.6, cv) * 0.5)
    return col


def p_cloth(base, folds=6.0):
    def fn(P, N, aux, ao, cv, ctx, pid):
        n = len(P)
        names = np.array(ctx["pieces"])[pid]
        col = np.tile(C(base), (n, 1))
        col = col * (0.88 + 0.22 * fbm(P, 6.0, 3, 61))[:, None]
        weave = (np.sin(P[:, 0] * 900 + P[:, 1] * 900) * np.sin(P[:, 2] * 900)) * 0.03
        col = col * (1 + weave)[:, None]
        fold = 0.5 + 0.5 * np.sin(aux[:, 0] * 2 * math.pi * folds + 1.7 * fbm(P, 4.0, 2, 62) * 6.0)
        col = col * (0.90 + 0.16 * fold)[:, None]
        dirt = ss(0.55, 1.0, aux[:, 1]) * (0.6 + 0.4 * fbm(P, 12.0, 2, 63))
        col = mix(col, np.array([0.22, 0.18, 0.13]), dirt * 0.55)
        fray = (aux[:, 1] > 0.92) * ss(0.5, 0.8, vnoise(P, 200.0, 64))
        col = col * (1 - 0.35 * fray)[:, None]
        if base == "cloth_red":
            front = names == "flap_front"
            u, v = aux[:, 0], aux[:, 1]
            dry = ss(0.3, 0.6, fbm(P, 1.0, 2, 65, aniso=(40.0, 40.0, 180.0)))
            for k in (-1, 0, 1):
                u0 = 0.5 + 0.17 * k
                d = np.abs((u - u0) - 0.22 * (v - 0.35))
                claw = (d < 0.038 * (1 - 0.5 * ss(0.2, 0.62, v))) & (v > 0.12) & (v < 0.64)
                col = mix(col, np.array([0.70, 0.64, 0.50]), front * claw * (0.55 + 0.35 * dry))
        return col
    return fn


def p_linen(P, N, aux, ao, cv, ctx, pid):
    n = len(P)
    col = np.tile(C("linen"), (n, 1))
    col = col * (0.88 + 0.20 * fbm(P, 8.0, 3, 71))[:, None]
    b = np.mod(aux[:, 0] / 0.045 + aux[:, 1], 1.0)
    col = col * (0.84 + 0.20 * ss(0.0, 0.5, b))[:, None]
    col = mix(col, np.array([0.30, 0.25, 0.18]), (b < 0.06) * 0.6)
    stain = ss(0.62, 0.80, fbm(P, 14.0, 3, 72))
    col = mix(col, np.array([0.40, 0.29, 0.19]), stain * 0.5)
    return col


def p_iron(P, N, aux, ao, cv, ctx, pid, rust_k=1.0):
    n = len(P)
    names = np.array(ctx["pieces"])[pid]
    col = np.tile(C("iron"), (n, 1))
    f1, f2 = texproj.voronoi(P, freq=60.0, seed=81)
    col = col * (0.92 + 0.12 * ss(0.0, 0.02, f1))[:, None]
    col = col * (0.92 + 0.14 * fbm(P, 9.0, 3, 82))[:, None]
    rust = ss(0.56, 0.74, fbm(P, 16.0, 3, 83)) * rust_k
    rust = np.clip(rust + (1 - ao) * 0.6 * rust_k * ss(0.4, 0.6, fbm(P, 30.0, 2, 84)), 0, 1)
    col = mix(col, C("rust"), rust * 0.75)
    col = mix(col, np.array([0.56, 0.57, 0.57]), ss(0.2, 0.7, cv) * 0.7)
    dome = names == "pauldron_dome"
    riv = (np.abs(aux[:, 0] - 0.86) < 0.05) & (np.abs(np.mod(aux[:, 1] * 13.0, 1.0) - 0.5) < 0.18)
    col = mix(col, np.array([0.55, 0.55, 0.53]), dome * riv * 0.85)
    rim = dome * (aux[:, 0] > 0.95)
    col = mix(col, np.array([0.48, 0.48, 0.47]), rim * 0.5)
    return col


def p_bone(P, N, aux, ao, cv, ctx, pid):
    n = len(P)
    col = np.tile(C("bone"), (n, 1))
    col = col * (0.90 + 0.16 * fbm(P, 12.0, 3, 91))[:, None]
    col = mix(col, np.array([0.45, 0.36, 0.25]), (1 - ao) * 0.9)
    crack = ss(0.90, 0.97, 1.0 - np.abs(2 * fbm(P, 30.0, 2, 92) - 1))
    col = mix(col, np.array([0.38, 0.30, 0.21]), crack * 0.6)
    return col


def p_staff_bone(P, N, aux, ao, cv, ctx, pid):
    n = len(P)
    names = np.array(ctx["pieces"])[pid]
    col = np.tile(C("staff_bone"), (n, 1))
    col = col * (0.90 + 0.16 * fbm(P, 14.0, 3, 101))[:, None]
    u, v = aux[:, 0], aux[:, 1]
    shaft = names == "staff_shaft"
    ph = np.mod(u / 0.11, 1.0)
    groove = (ph < 0.06) | (ph > 0.94)
    zig = np.abs(np.mod(v * 6.0, 1.0) - 0.5) * 2.0
    carve = (np.abs(ph - (0.25 + 0.5 * zig)) < 0.045) & (ph > 0.1) & (ph < 0.9)
    col = mix(col, np.array([0.30, 0.24, 0.17]), shaft * (groove | carve) * 0.75)
    grime = 1 - ss(0.0, 0.9, u)
    col = mix(col, np.array([0.35, 0.28, 0.20]), shaft * grime * 0.45)
    col = mix(col, np.array([0.40, 0.32, 0.22]), (1 - ao) * 0.7)
    return col


def p_staff_leather(P, N, aux, ao, cv, ctx, pid):
    n = len(P)
    col = np.tile(C("leather"), (n, 1)) * (0.9 + 0.2 * fbm(P, 20.0, 2, 111))[:, None]
    b = np.mod(aux[:, 0] / 0.028 + aux[:, 1], 1.0)
    col = col * (0.75 + 0.35 * ss(0.0, 0.5, b))[:, None]
    col = mix(col, C("leather_worn"), ss(0.3, 0.5, b) * (1 - ss(0.5, 0.8, b)) * 0.35)
    return col


def p_crystal(P, N, aux, ao, cv, ctx, pid):
    n = len(P)
    col = np.tile(C("crystal"), (n, 1))
    key = np.round(N * 3.0)
    h = (np.abs(np.sin(key @ np.array([12.9898, 78.233, 37.719]))) * 43758.5453) % 1.0
    col = col * (0.82 + 0.30 * h)[:, None]
    streak = flow_frame_noise(P, np.array([0, 0, 1.0]), 30.0, 220.0, seed=121)
    col = mix(col, np.array([0.88, 1.0, 0.90]), ss(0.55, 0.85, streak) * 0.5)
    return np.clip(col, 0, 1)


PAINTERS = {
    "skin": p_skin, "eye": p_eye, "tusk": p_tusk, "hair": p_hair, "fur": p_fur, "leather": p_leather,
    "boot": p_boot, "cloth_dark": p_cloth("cloth_dark", 7.0), "cloth_red": p_cloth("cloth_red", 4.0),
    "linen": p_linen, "iron": p_iron, "bone": p_bone, "staff_bone": p_staff_bone,
    "staff_iron": lambda *a: p_iron(*a, rust_k=0.6), "staff_leather": p_staff_leather, "crystal": p_crystal,
}
AO_K = {"skin": 1.0, "eye": 0.4, "tusk": 0.6, "hair": 0.9, "fur": 1.0, "leather": 0.9, "boot": 0.9,
        "cloth_dark": 1.0, "cloth_red": 1.0, "linen": 0.9, "iron": 0.8, "bone": 0.8, "staff_bone": 0.7,
        "staff_iron": 0.7, "staff_leather": 0.8, "crystal": 0.0}
LIGHT_K = {c: 1.0 for c in CLASSES} | {"crystal": 0.15, "eye": 0.5}


def paint(P, N, cls, pid, aux, ao, cv, ctx, log=print):
    n = len(P)
    col = np.zeros((n, 3))
    for name, fn in PAINTERS.items():
        m = cls == CID[name]
        if not m.any():
            continue
        col[m] = fn(P[m], N[m], aux[m], ao[m], cv[m], ctx, pid[m])
        log("  painted", name, int(m.sum()))
    # ---- painted light (warm key upper-left of the front view, cool shadow), lightly baked
    Lw = unit(np.array(SP.LIGHT, float))
    lk = np.array([LIGHT_K[c] for c in CLASSES])[cls]
    ak = np.array([AO_K[c] for c in CLASSES])[cls]
    wrap = np.clip(N @ Lw * 0.5 + 0.5, 0, 1)
    shade = 0.72 + 0.37 * wrap ** 1.4 + 0.04 * np.clip(N[:, 2], 0, 1)
    shade = np.where(cls == CID["skin"], 0.66 + 0.46 * wrap ** 1.4 + 0.04 * np.clip(N[:, 2], 0, 1), shade)
    shade = 1 + (shade - 1) * lk
    tint = 1 + np.outer((wrap - 0.5) * lk, np.array([0.06, 0.015, -0.07]))
    col = col * shade[:, None] * tint
    # occlusion + cavity / convex edges
    occ = 0.42 + 0.58 * np.clip(ao, 0, 1) ** 0.85
    col = col * (1 + (occ - 1) * ak)[:, None]
    edge = np.clip(cv, -1, 1)
    cav = np.where(cls == CID["skin"], 0.26, 0.12)
    col = col * (1 + (0.09 * np.clip(edge, 0, 1) - cav * np.clip(-edge, 0, 1)) * ak)[:, None]
    # dry-brush stroke variation (painterly, low amplitude)
    brush = flow_frame_noise(P, np.array([0.2, 0.1, 1.0]), 6.0, 45.0, seed=7)
    col = col * (0.965 + 0.07 * brush)[:, None]
    return np.clip(col, 0, 1)
