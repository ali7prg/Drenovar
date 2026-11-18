"""Material class shaders for propkit.synthesize (palette sampled from the reference sheets).

Every shader receives a propkit.Ctx (texel subset) and returns dict(albedo (n,3) sRGB 0..1,
rough (n), metal (n), height (n) metres).  Parametric UVs are metres: u along the grain /
sweep path, v around the profile; extrude caps carry local (x, y).

Part meta keys understood here (all optional):
  motif:      list of dict(mask=(H,W) float, bbox=(u0,v0,u1,v1), isl=(...), depth=m (+raised/-cut),
              mode='raise'|'cut', colour=(r,g,b) recess tint, enamel=bool)
  rivets:     dict(du=spacing along u, v=[v positions], r=radius, u0=offset)
  moss:       0..1 amount on upward faces
  tint:       (r,g,b) multiplier
  blocks:     (course_h, block_len) limestone coursing in world (horizontal axis auto)
  flags:      flagstone cell size (m) for horizontal stone surfaces
  pith:       (x, y) end-grain ring centre (profile coords)
"""
import math

import cv2
import numpy as np

from propkit import fbm2, fbm3, hash1, mix, smoothstep
from frlib import texproj


def C(*rgb):
    return np.array(rgb, float) / 255.0


def _n(ctx):
    return ctx.n


def lerp3(a, b, t):
    t = np.asarray(t, float)[..., None]
    return a * (1 - t) + b * t


def sample_mask(mask, bbox, u, v):
    """Bilinear sample of mask (H,W) mapped over bbox=(u0,v0,u1,v1) (row 0 = v1); 0 outside."""
    H, W = mask.shape
    u0, v0, u1, v1 = bbox
    x = (u - u0) / (u1 - u0) * (W - 1)
    y = (v1 - v) / (v1 - v0) * (H - 1)
    n = len(u)
    cols = 4096
    rows = max(1, -(-n // cols))
    mx = np.full(rows * cols, -10, np.float32)
    my = np.full(rows * cols, -10, np.float32)
    mx[:n] = x
    my[:n] = y
    out = cv2.remap(mask.astype(np.float32), mx.reshape(rows, cols), my.reshape(rows, cols),
                    interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return out.reshape(-1)[:n].astype(np.float64)


def apply_motifs(ctx, albedo, height, rough, metal, recess_col=None, raise_col=None):
    """Engrave/raise part motifs; returns cavity (0..1) for patina/dirt."""
    cavity = np.zeros(ctx.n)
    for m, motifs in ctx.by_part("motif"):
        for mo in (motifs if isinstance(motifs, (list, tuple)) else [motifs]):
            sel = m.copy()
            if mo.get("isl") is not None:
                sel &= np.isin(ctx.isl, mo["isl"])
            if mo.get("normal") is not None:
                sel &= (ctx.N @ np.asarray(mo["normal"], float)) > mo.get("normal_min", 0.5)
            if not sel.any():
                continue
            val = sample_mask(mo["mask"], mo["bbox"], ctx.u[sel], ctx.v[sel])
            d = mo.get("depth", 0.002)
            if mo.get("mode", "cut") == "cut":
                height[sel] -= d * val
                cavity[sel] = np.maximum(cavity[sel], val)
                col = mo.get("colour", recess_col)
                if col is not None:
                    albedo[sel] = lerp3(albedo[sel], np.asarray(col, float), val * mo.get("tint", 0.75))
            else:
                height[sel] += d * val
                col = mo.get("colour", raise_col)
                if col is not None:
                    albedo[sel] = lerp3(albedo[sel], np.asarray(col, float), val * mo.get("tint", 0.6))
                # recessed field around raised motif gets the cavity
                cavity[sel] = np.maximum(cavity[sel], (1 - val) * mo.get("field_cavity", 0.0))
            if mo.get("rough") is not None:
                rough[sel] = rough[sel] * (1 - val) + mo["rough"] * val
            if mo.get("metal") is not None:
                metal[sel] = metal[sel] * (1 - val) + mo["metal"] * val
    return cavity


def apply_rivets(ctx, height, albedo=None, col=None):
    mask = np.zeros(ctx.n)
    for m, rv in ctx.by_part("rivets"):
        du = rv["du"]
        r = rv["r"]
        u0 = rv.get("u0", du / 2)
        uu = ctx.u[m] - u0
        cu = np.round(uu / du) * du
        umin, umax = rv.get("umin", -1e9), rv.get("umax", 1e9)
        best = np.full(m.sum(), 1e9)
        for vv in rv["v"]:
            d = np.sqrt((uu - cu) ** 2 + (ctx.v[m] - vv) ** 2)
            best = np.minimum(best, d)
        ok = (ctx.u[m] > umin) & (ctx.u[m] < umax)
        if rv.get("isl") is not None:
            ok &= np.isin(ctx.isl[m], rv["isl"])
        dome = np.where(ok, np.sqrt(np.clip(1 - (best / r) ** 2, 0, 1)), 0.0)
        height[m] += dome * r * 0.55
        mask[m] = np.maximum(mask[m], dome > 0.02)
        if albedo is not None and col is not None:
            albedo[m] = lerp3(albedo[m], np.asarray(col, float), (dome > 0.05) * (0.55 + 0.45 * dome))
    return mask


def ground_dirt(ctx, albedo, amount=0.45, h=0.35, col=C(70, 58, 44)):
    h = h * getattr(ctx.asset, "dirt_scale", 1.0)
    if h <= 0 or amount <= 0:
        return albedo
    z = ctx.P[:, 2]
    d = smoothstep((h - z) / h) * amount
    n = fbm3(ctx.P * 3.0, 1.0, 3, seed=77)
    d = d * (0.6 + 0.8 * n)
    return lerp3(albedo, col, np.clip(d, 0, 1))


def add_moss(ctx, albedo, rough, height, amount, col=C(112, 108, 52), col2=C(150, 140, 70)):
    if np.all(amount <= 0):
        return albedo
    up = np.clip(ctx.N[:, 2], 0, 1)
    n = fbm3(ctx.P * 4.0, 1.0, 4, seed=91)
    n2 = fbm3(ctx.P * 22.0, 1.0, 2, seed=92)
    m = smoothstep((n + 0.55 * up + 0.25 * amount - 1.0 + 0.25) / 0.12) * (amount > 0)
    m *= np.clip(amount * 1.4, 0, 1)
    colm = lerp3(col, col2, n2)
    albedo = lerp3(albedo, colm, m)
    rough[:] = rough * (1 - m) + 0.95 * m
    height += m * 0.0015 * (0.5 + n2)
    return albedo


# =============================================================================== wood

def oak(ctx, base=C(118, 96, 76), light=C(168, 145, 120), dark=C(66, 50, 37), grey=C(150, 141, 128),
        weather=0.35, plank=False):
    n = ctx.n
    u, v = ctx.u, ctx.v
    s = ctx.seed * 37.0
    endg = ctx.flag == 2
    side = ~endg
    alb = np.zeros((n, 3))
    hgt = np.zeros(n)
    rough = np.full(n, 0.84)
    # long-grain streaks
    a = fbm2(u * 0.9 + s, v * 26.0 + s, octaves=4, seed=1)
    b = fbm2(u * 0.2 + s, v * 6.0 + s * 0.5, octaves=3, seed=2)
    warp = fbm2(u * 0.5 + s, v * 3.0, octaves=2, seed=3)
    lines = np.abs(np.sin((v * 70.0 + warp * 9.0 + s) * math.pi))
    fine = smoothstep((0.16 - lines) / 0.16)
    g = (a - 0.5) * 1.8 + (b - 0.5) * 1.1
    col = lerp3(base, light, np.clip(g, 0, 1))
    col = lerp3(col, dark, np.clip(-g, 0, 1) * 0.9)
    col = lerp3(col, dark, fine * 0.35)
    # checks / cracks along the grain
    cf = fbm2(u * 0.35 + s, v * 30.0 + s, octaves=3, seed=9)
    gate = smoothstep((fbm2(u * 0.6 + s, v * 1.5, octaves=2, seed=10) - 0.52) / 0.08)
    crack = smoothstep((0.035 - np.abs(cf - 0.5)) / 0.035) * gate
    col = lerp3(col, dark * 0.6, crack * 0.85)
    hgt += -0.0009 * np.clip(-g, 0, 1) - 0.00035 * fine - 0.0035 * crack
    # knots
    kn = fbm2(u * 2.2 + s, v * 2.2 + s, octaves=2, seed=13)
    knot = smoothstep((kn - 0.78) / 0.05)
    col = lerp3(col, dark, knot * 0.7)
    hgt -= knot * 0.001
    # end grain rings
    if endg.any():
        px, py = ctx.meta_value("pith_x", 0.0)[endg], ctx.meta_value("pith_y", 0.0)[endg]
        r = np.sqrt((u[endg] - px) ** 2 + (v[endg] - py) ** 2)
        rn = fbm2(u[endg] * 8 + s[endg], v[endg] * 8, octaves=2, seed=17)
        rings = 0.5 + 0.5 * np.sin((r * 110.0 + rn * 4.0) * 2 * math.pi / 6.28)
        ec = lerp3(C(150, 118, 86), C(98, 74, 52), rings * 0.7)
        ang = np.arctan2(v[endg] - py, u[endg] - px)
        rc = smoothstep((0.04 - np.abs(np.sin(ang * 3 + s[endg]))) / 0.04) * (r > 0.01)
        ec = lerp3(ec, dark * 0.6, rc * 0.8)
        col[endg] = ec
        hgt[endg] = -0.0004 * rings - 0.002 * rc
    # edge wear (chamfer bands) and weathering
    edge = (ctx.flag == 1).astype(float)
    col = lerp3(col, lerp3(col, grey, 0.5) * 1.12, edge * 0.55)
    up = np.clip(ctx.N[:, 2], 0, 1)
    wn = fbm3(ctx.P * 1.5, 1.0, 3, seed=19)
    col = lerp3(col, grey, np.clip(weather * (0.4 + up * 0.8) * (0.5 + wn), 0, 0.7))
    tint = None
    for m, t in ctx.by_part("tint"):
        col[m] = col[m] * np.asarray(t, float)
    rough = rough + (a - 0.5) * 0.08
    col = ground_dirt(ctx, col, amount=0.35)
    hgt_m = np.zeros(n)
    moss_amt = ctx.meta_value("moss", 0.0)
    col = add_moss(ctx, col, rough, hgt_m, moss_amt)
    hgt += hgt_m
    cav = apply_motifs(ctx, col, hgt, rough, np.zeros(n), recess_col=dark * 0.8)
    metal = np.zeros(n)
    rv = apply_rivets(ctx, hgt, col, C(60, 56, 52))
    metal = np.where(rv > 0, 0.7, 0.0)
    rough = np.where(rv > 0, 0.5, rough)
    return {"albedo": np.clip(col, 0, 1), "rough": np.clip(rough, 0.3, 1), "metal": metal, "height": hgt}


def plank_wood(ctx, **kw):
    kw.setdefault("base", C(112, 82, 56))
    kw.setdefault("light", C(158, 120, 84))
    kw.setdefault("dark", C(62, 44, 30))
    kw.setdefault("grey", C(140, 124, 106))
    kw.setdefault("weather", 0.25)
    return oak(ctx, **kw)


def dark_oak(ctx, **kw):
    kw.setdefault("base", C(96, 70, 48))
    kw.setdefault("light", C(140, 105, 72))
    kw.setdefault("dark", C(52, 36, 24))
    kw.setdefault("grey", C(120, 106, 92))
    kw.setdefault("weather", 0.18)
    return oak(ctx, **kw)


# =============================================================================== stone

def limestone(ctx, base=C(170, 152, 132), light=C(208, 194, 176), dark=C(118, 104, 90), mortar=C(92, 82, 70),
              moss_default=0.0):
    n = ctx.n
    P, N = ctx.P, ctx.N
    s = ctx.seed * 13.0
    col = np.repeat(base[None], n, 0)
    hgt = np.zeros(n)
    rough = np.full(n, 0.9)
    # coursing in world space
    joint = np.zeros(n)
    blockid = np.zeros(n)
    bl = ctx.meta_value("block_len", 0.0)
    ch = ctx.meta_value("course_h", 0.0)
    fl = ctx.meta_value("flag_size", 0.0)
    has_blocks = bl > 0
    if has_blocks.any():
        m = has_blocks
        Pm, Nm = P[m], N[m]
        horiz = np.abs(Nm[:, 2]) > 0.7
        ax = np.where(np.abs(Nm[:, 0]) > np.abs(Nm[:, 1]), 1, 0)  # along-wall axis
        along = np.where(ax == 0, Pm[:, 0], Pm[:, 1])
        across = np.where(ax == 0, Pm[:, 1], Pm[:, 0])
        z = Pm[:, 2]
        course = np.floor(z / ch[m])
        off = (course % 2) * 0.5 + hash1(course.astype(np.int64), 3) * 0.3
        bx = along / bl[m] + off
        jitter = (fbm3(Pm * 2.0, 1.0, 2, seed=5) - 0.5) * 0.25
        fx = np.abs(((bx + jitter) % 1.0) - 0.5)
        fz = np.abs(((z / ch[m]) % 1.0) - 0.5)
        dx = (0.5 - fx) * bl[m]
        dz = (0.5 - fz) * ch[m]
        # horizontal faces: joints along both directions
        ax2 = across / (ch[m] * 1.6) + off
        fy = np.abs((ax2 % 1.0) - 0.5)
        dy = (0.5 - fy) * ch[m] * 1.6
        dmin = np.where(horiz, np.minimum(dx, dy), np.minimum(dx, dz))
        jw = 0.012
        jt = smoothstep((jw - dmin) / jw)
        bevel = smoothstep((0.035 - dmin) / 0.035)
        joint[m] = jt
        bid = (np.floor(bx + jitter) * 7 + course * 13).astype(np.int64)
        blockid[m] = hash1(bid, 21)
        hgt[m] += -0.012 * jt - 0.004 * bevel
    if (fl > 0).any():
        m = fl > 0
        f1, f2 = texproj.voronoi(np.c_[P[m][:, 0], P[m][:, 1], np.zeros(m.sum())], 1.0 / fl[m].mean(), seed=8)
        e = f2 - f1
        jt = smoothstep((0.02 - e) / 0.02)
        joint[m] = np.maximum(joint[m], jt)
        cell = np.floor((P[m][:, 0] * 3.1 + P[m][:, 1] * 1.7) * 2)
        blockid[m] = hash1(np.round(f1 * 997).astype(np.int64), 4)
        hgt[m] += -0.008 * jt
    var = (blockid - 0.5) * 0.18
    col = col * (1 + var)[:, None]
    n1 = fbm3(P * 6.0, 1.0, 4, seed=31)
    n2 = fbm3(P * 28.0, 1.0, 3, seed=32)
    col = lerp3(col, light, np.clip((n1 - 0.5) * 1.6, 0, 1) * 0.6)
    col = lerp3(col, dark, np.clip((0.5 - n1) * 1.6, 0, 1) * 0.6)
    pits = smoothstep((n2 - 0.72) / 0.06)
    col = lerp3(col, dark, pits * 0.5)
    hgt += (n1 - 0.5) * 0.004 - pits * 0.0015 + (n2 - 0.5) * 0.0012
    col = lerp3(col, mortar, joint * 0.85)
    # edge wear (chamfers) lighter
    col = lerp3(col, light, (ctx.flag == 1) * 0.35)
    col = ground_dirt(ctx, col, amount=0.3, h=0.25)
    moss_amt = np.maximum(ctx.meta_value("moss", moss_default), 0)
    hm = np.zeros(n)
    col = add_moss(ctx, col, rough, hm, moss_amt, col=C(104, 110, 56), col2=C(140, 140, 72))
    hgt += hm
    metal = np.zeros(n)
    cav = apply_motifs(ctx, col, hgt, rough, metal, recess_col=dark * 0.75)
    return {"albedo": np.clip(col, 0, 1), "rough": rough, "metal": metal, "height": hgt}


def granite_rock(ctx, base=C(118, 112, 100), light=C(170, 164, 150), dark=C(70, 66, 58)):
    n = ctx.n
    P = ctx.P
    n1 = fbm3(P * 2.5, 1.0, 5, seed=41)
    n2 = fbm3(P * 14.0, 1.0, 3, seed=42)
    col = lerp3(base, light, np.clip((n1 - 0.45) * 2, 0, 1))
    col = lerp3(col, dark, np.clip((0.45 - n1) * 2, 0, 1))
    lich = smoothstep((fbm3(P * 9.0, 1.0, 3, seed=43) - 0.68) / 0.05)
    col = lerp3(col, C(200, 196, 180), lich * 0.6)
    hgt = (n1 - 0.5) * 0.02 + (n2 - 0.5) * 0.004
    rough = np.full(n, 0.88)
    hm = np.zeros(n)
    col = add_moss(ctx, col, rough, hm, np.maximum(ctx.meta_value("moss", 0.6), 0), col=C(96, 108, 50), col2=C(150, 150, 80))
    hgt += hm
    return {"albedo": np.clip(col, 0, 1), "rough": rough, "metal": np.zeros(n), "height": hgt}


# =============================================================================== metals

def iron(ctx, base=C(60, 56, 53), rust=C(112, 76, 50), edge=C(122, 116, 108), rustiness=0.35):
    n = ctx.n
    P = ctx.P
    n1 = fbm3(P * 9.0, 1.0, 4, seed=51)
    n2 = fbm3(P * 45.0, 1.0, 2, seed=52)
    col = np.repeat(base[None], n, 0) * (0.85 + 0.3 * n2)[:, None]
    r = smoothstep((n1 - (0.62 - rustiness * 0.3)) / 0.1)
    low = smoothstep((0.6 - ctx.P[:, 2]) / 0.6)
    r = np.clip(r + low * 0.3 * n1, 0, 1)
    col = lerp3(col, rust, r * 0.8)
    e = (ctx.flag == 1).astype(float)
    col = lerp3(col, edge, e * 0.6)
    metal = 0.75 - 0.55 * r
    rough = 0.58 + 0.3 * r - 0.12 * e
    hgt = (n2 - 0.5) * 0.0006 + r * 0.0004
    rv = apply_rivets(ctx, hgt, col, C(84, 80, 74))
    cav = apply_motifs(ctx, col, hgt, rough, metal, recess_col=C(40, 36, 34))
    col = ground_dirt(ctx, col, amount=0.25)
    return {"albedo": np.clip(col, 0, 1), "rough": np.clip(rough, 0.2, 1), "metal": np.clip(metal, 0, 1), "height": hgt}


def bronze(ctx, base=C(150, 108, 56), hi=C(206, 166, 98), patina=C(76, 116, 90), dark=C(74, 52, 30),
           patina_amt=0.45):
    n = ctx.n
    P = ctx.P
    n1 = fbm3(P * 18.0, 1.0, 4, seed=61)
    n2 = fbm3(P * 60.0, 1.0, 2, seed=62)
    col = lerp3(base, hi, np.clip((n1 - 0.4) * 1.5, 0, 1) * 0.6)
    col = col * (0.9 + 0.2 * n2)[:, None]
    hgt = (n2 - 0.5) * 0.0003
    rough = np.full(n, 0.42) + (n1 - 0.5) * 0.12
    metal = np.full(n, 0.95)
    cav = apply_motifs(ctx, col, hgt, rough, metal, recess_col=dark, raise_col=hi)
    rv = apply_rivets(ctx, hgt, col, hi)
    # patina in recesses and noisy patches
    pn = fbm3(P * 30.0, 1.0, 3, seed=63)
    pat = np.clip(cav * (0.5 + pn) * patina_amt * 1.6 + smoothstep((pn - 0.7) / 0.08) * patina_amt * 0.5, 0, 1)
    col = lerp3(col, patina, pat * 0.85)
    rough = rough * (1 - pat) + 0.8 * pat
    metal = metal * (1 - pat) + 0.1 * pat
    e = (ctx.flag == 1).astype(float)
    col = lerp3(col, hi, e * 0.45)
    # enamel fields
    for m, en in ctx.by_part("enamel"):
        sel = m & np.isin(ctx.isl, en.get("isl", [0, 1, 2]))
        if not sel.any():
            continue
        val = sample_mask(en["mask"], en["bbox"], ctx.u[sel], ctx.v[sel])
        ec = np.asarray(en.get("colour", C(48, 104, 78)), float)
        ecol = ec * (0.85 + 0.3 * fbm3(P[sel] * 50.0, 1.0, 2, seed=64))[:, None]
        col[sel] = lerp3(col[sel], ecol, val)
        metal[sel] = metal[sel] * (1 - val)
        rough[sel] = rough[sel] * (1 - val) + 0.32 * val
        hgt[sel] -= 0.0004 * val
    return {"albedo": np.clip(col, 0, 1), "rough": np.clip(rough, 0.15, 1), "metal": np.clip(metal, 0, 1), "height": hgt}


def enamel(ctx, base=C(46, 98, 74)):
    n = ctx.n
    n1 = fbm3(ctx.P * 40.0, 1.0, 3, seed=71)
    col = np.repeat(base[None], n, 0) * (0.85 + 0.3 * n1)[:, None]
    hgt = np.zeros(n)
    rough = np.full(n, 0.3)
    metal = np.zeros(n)
    apply_motifs(ctx, col, hgt, rough, metal, raise_col=C(196, 158, 92))
    return {"albedo": np.clip(col, 0, 1), "rough": rough, "metal": metal, "height": hgt}


def gem(ctx, base=C(200, 112, 18), deep=C(120, 52, 8), light=C(250, 190, 70)):
    """Amber / green crystal: facet-dependent painted depth (glossy dielectric)."""
    n = ctx.n
    N = ctx.N
    fac = np.clip(N @ np.array([-0.4, -0.5, 0.75]) * 0.5 + 0.5, 0, 1)
    n1 = fbm3(ctx.P * 35.0, 1.0, 3, seed=81)
    col = lerp3(deep, base, fac)
    col = lerp3(col, light, smoothstep((n1 - 0.6) / 0.15) * 0.6)
    inc = smoothstep((fbm3(ctx.P * 80.0, 1.0, 2, seed=82) - 0.75) / 0.05)
    col = lerp3(col, deep * 0.7, inc * 0.4)
    return {"albedo": np.clip(col, 0, 1), "rough": np.full(n, 0.12), "metal": np.zeros(n), "height": np.zeros(n)}


def gem_green(ctx):
    return gem(ctx, base=C(110, 170, 40), deep=C(40, 80, 20), light=C(200, 230, 110))


# =============================================================================== organic

def birch_bark(ctx):
    n = ctx.n
    u, v = ctx.u, ctx.v
    P = ctx.P
    s = ctx.seed * 11
    col = np.repeat(C(214, 208, 192)[None], n, 0)
    n1 = fbm2(u * 3.0 + s, v * 3.0, octaves=4, seed=101)
    col = col * (0.9 + 0.15 * n1)[:, None]
    # lenticels: short horizontal dark dashes (around the trunk => along v, thin in u)
    lu = (u * 9.0 + fbm2(u * 2, v * 2, 2, 102) * 2)
    band = np.abs(((lu) % 1.0) - 0.5)
    dash = smoothstep((0.06 - band) / 0.06) * smoothstep((fbm2(u * 9, v * 4.0 + s, 2, 103) - 0.55) / 0.08)
    col = lerp3(col, C(48, 44, 40), dash * 0.85)
    # dark rough patches near the base
    base = smoothstep((0.35 - P[:, 2]) / 0.3) * smoothstep((fbm3(P * 5, 1, 3, 104) - 0.4) / 0.2)
    col = lerp3(col, C(58, 52, 46), base * 0.85)
    blot = smoothstep((fbm2(u * 4 + s, v * 4, 3, 105) - 0.7) / 0.06)
    col = lerp3(col, C(80, 72, 62), blot * 0.6)
    hgt = -dash * 0.0012 - base * 0.002 + (n1 - 0.5) * 0.001
    rough = np.full(n, 0.75)
    # inner split wood / cut top (flag 2 or meta inner)
    inner = (ctx.flag == 2) | ctx.meta_mask("inner_wood")
    if inner.any():
        r = np.sqrt(u[inner] ** 2 + v[inner] ** 2)
        rings = 0.5 + 0.5 * np.sin(r * 2 * math.pi * 28 + fbm2(u[inner] * 9, v[inner] * 9, 2, 106) * 3)
        ic = lerp3(C(196, 164, 122), C(150, 116, 80), rings * 0.6)
        ic = lerp3(ic, C(110, 90, 66), smoothstep((fbm2(u[inner] * 20, v[inner] * 3, 3, 107) - 0.55) / 0.1) * 0.5)
        col[inner] = ic
        hgt[inner] = -rings * 0.0006
    hm = np.zeros(n)
    col = add_moss(ctx, col, rough, hm, np.maximum(ctx.meta_value("moss", 0.35), 0), col=C(104, 112, 50), col2=C(146, 148, 70))
    hgt += hm
    return {"albedo": np.clip(col, 0, 1), "rough": rough, "metal": np.zeros(n), "height": hgt}


def root_bark(ctx, base=C(122, 104, 82), light=C(176, 158, 132), dark=C(66, 54, 42)):
    n = ctx.n
    u, v = ctx.u, ctx.v
    s = ctx.seed * 17
    tw = v * 1.0 + u * 0.35
    f = fbm2(u * 1.4 + s, tw * 16 + s, octaves=4, seed=111)
    furrow = smoothstep((0.42 - f) / 0.12)
    col = lerp3(base, light, np.clip((f - 0.5) * 2.2, 0, 1) * 0.7)
    col = lerp3(col, dark, furrow * 0.8)
    n2 = fbm2(u * 6 + s, v * 12, octaves=3, seed=112)
    col = col * (0.9 + 0.2 * n2)[:, None]
    hgt = -furrow * 0.004 + (f - 0.5) * 0.002
    rough = np.full(n, 0.86)
    hm = np.zeros(n)
    col = add_moss(ctx, col, rough, hm, np.maximum(ctx.meta_value("moss", 0.55), 0), col=C(108, 112, 48), col2=C(150, 146, 66))
    hgt += hm
    col = ground_dirt(ctx, col, amount=0.3)
    cav = apply_motifs(ctx, col, hgt, rough, np.zeros(n), recess_col=dark)
    return {"albedo": np.clip(col, 0, 1), "rough": rough, "metal": np.zeros(n), "height": hgt}


def log_bark(ctx):
    r = root_bark(ctx, base=C(92, 72, 54), light=C(140, 112, 84), dark=C(46, 34, 26))
    return r


def rope(ctx, base=C(150, 116, 78), dark=C(92, 68, 44)):
    n = ctx.n
    u, v = ctx.u, ctx.v
    k = ctx.meta_value("rope_pitch", 0.03)
    ph = (u / k + v / max(1e-3, ctx.meta_value("rope_circ", 0.06).mean()) * 3.0) % 1.0
    strand = 0.5 + 0.5 * np.cos(ph * 2 * math.pi)
    fib = fbm2(u * 60, v * 60, octaves=2, seed=121)
    col = lerp3(dark, base, strand * 0.8 + fib * 0.2)
    hgt = strand * 0.0012
    return {"albedo": np.clip(col, 0, 1), "rough": np.full(n, 0.92), "metal": np.zeros(n), "height": hgt}


def bone(ctx, base=C(212, 186, 150), dark=C(150, 124, 92)):
    n = ctx.n
    P = ctx.P
    n1 = fbm3(P * 30.0, 1.0, 4, seed=131)
    pores = smoothstep((fbm3(P * 140.0, 1.0, 2, seed=132) - 0.72) / 0.05)
    col = lerp3(base, C(232, 214, 186), np.clip((n1 - 0.5) * 2, 0, 1) * 0.5)
    col = lerp3(col, dark, np.clip((0.5 - n1) * 2, 0, 1) * 0.5)
    col = lerp3(col, C(120, 96, 70), pores * 0.6)
    hgt = (n1 - 0.5) * 0.0004 - pores * 0.0002
    rough = np.full(n, 0.6)
    metal = np.zeros(n)
    cav = apply_motifs(ctx, col, hgt, rough, metal, recess_col=C(130, 104, 74))
    return {"albedo": np.clip(col, 0, 1), "rough": rough, "metal": metal, "height": hgt}


def shingles(ctx, base=C(112, 104, 100), light=C(158, 150, 144), dark=C(70, 64, 62)):
    """Slate/wood shingles; u along the eave, v up the slope (metres)."""
    n = ctx.n
    u, v = ctx.u, ctx.v
    rh = ctx.meta_value("row_h", 0.11)
    sw = ctx.meta_value("shingle_w", 0.17)
    row = np.floor(v / rh)
    fv = (v / rh) % 1.0
    off = (row % 2) * 0.5
    su = u / sw + off + (hash1(row.astype(np.int64), 5) - 0.5) * 0.3
    sid = np.floor(su)
    fu = su % 1.0
    vid = hash1((sid * 31 + row * 7).astype(np.int64), 6)
    col = lerp3(base, light, vid * 0.5)
    col = lerp3(col, dark, (1 - vid) * 0.3)
    gap = smoothstep((0.05 - np.minimum(fu, 1 - fu)) / 0.05)
    col = lerp3(col, dark * 0.6, gap * 0.8)
    # overlap shadow at the lower edge of each row (v increases up the slope)
    edge = smoothstep((0.18 - fv) / 0.18)
    col = lerp3(col, dark * 0.7, edge * 0.45)
    n1 = fbm3(ctx.P * 12.0, 1.0, 3, seed=141)
    col = col * (0.88 + 0.24 * n1)[:, None]
    hgt = fv * 0.012 - gap * 0.004 + (n1 - 0.5) * 0.001
    rough = np.full(n, 0.85)
    hm = np.zeros(n)
    col = add_moss(ctx, col, rough, hm, np.maximum(ctx.meta_value("moss", 0.15), 0))
    hgt += hm
    return {"albedo": np.clip(col, 0, 1), "rough": rough, "metal": np.zeros(n), "height": hgt}


def cloth(ctx, base=C(150, 76, 52), light=C(186, 110, 82), band=C(214, 186, 150), weave=0.004):
    n = ctx.n
    u, v = ctx.u, ctx.v
    wv = 0.5 + 0.25 * (np.sin(u / weave * math.pi) + np.sin(v / weave * math.pi))
    n1 = fbm2(u * 4, v * 4, octaves=3, seed=151)
    col = lerp3(base, light, np.clip(n1 * 0.8 + wv * 0.3 - 0.3, 0, 1))
    hgt = (wv - 0.5) * 0.0008
    rough = np.full(n, 0.95)
    metal = np.zeros(n)
    apply_motifs(ctx, col, hgt, rough, metal, raise_col=band)
    return {"albedo": np.clip(col, 0, 1), "rough": rough, "metal": metal, "height": hgt}


def burlap(ctx):
    n = ctx.n
    u, v = ctx.u, ctx.v
    w = 0.006
    wv = np.abs(np.sin(u / w * math.pi)) * 0.5 + np.abs(np.sin(v / w * math.pi)) * 0.5
    n1 = fbm2(u * 5, v * 5, octaves=3, seed=161)
    col = lerp3(C(118, 88, 58), C(176, 140, 98), np.clip(wv * 0.6 + n1 * 0.6 - 0.1, 0, 1))
    hgt = wv * 0.0012
    rough = np.full(n, 0.97)
    metal = np.zeros(n)
    apply_motifs(ctx, col, hgt, rough, metal, recess_col=C(80, 56, 36))
    return {"albedo": np.clip(col, 0, 1), "rough": rough, "metal": metal, "height": hgt}


def linen(ctx):
    r = cloth(ctx, base=C(198, 172, 140), light=C(226, 206, 178), band=C(150, 60, 44), weave=0.002)
    return r


def bread(ctx):
    n = ctx.n
    P = ctx.P
    n1 = fbm3(P * 30.0, 1.0, 4, seed=171)
    up = np.clip(ctx.N[:, 2], 0, 1)
    col = lerp3(C(150, 92, 46), C(196, 136, 76), np.clip(n1 * 1.2 - 0.2, 0, 1))
    col = lerp3(col, C(122, 70, 34), up * 0.35)
    flour = smoothstep((fbm3(P * 18.0, 1.0, 3, seed=172) - 0.6) / 0.1) * up
    col = lerp3(col, C(226, 206, 170), flour * 0.6)
    hgt = (n1 - 0.5) * 0.002
    rough = np.full(n, 0.8)
    metal = np.zeros(n)
    apply_motifs(ctx, col, hgt, rough, metal, recess_col=C(222, 196, 150))
    return {"albedo": np.clip(col, 0, 1), "rough": rough, "metal": metal, "height": hgt}


def grain(ctx):
    n = ctx.n
    P = ctx.P
    f1, f2 = texproj.voronoi(P, 140.0, seed=181)
    e = smoothstep((f2 - f1) / 0.004)
    col = lerp3(C(150, 110, 50), C(214, 172, 96), e)
    return {"albedo": col, "rough": np.full(n, 0.7), "metal": np.zeros(n), "height": e * 0.0015}


def feather(ctx):
    n = ctx.n
    u, v = ctx.u, ctx.v
    barbs = 0.5 + 0.5 * np.sin((u * 0.6 + v) * 900)
    col = lerp3(C(150, 146, 140), C(222, 220, 212), barbs * 0.5 + 0.3)
    tip = smoothstep((u - 0.09) / 0.03)
    col = lerp3(col, C(70, 66, 62), tip * 0.5)
    return {"albedo": np.clip(col, 0, 1), "rough": np.full(n, 0.8), "metal": np.zeros(n), "height": barbs * 0.0002}


def leather(ctx):
    n = ctx.n
    n1 = fbm3(ctx.P * 40, 1, 3, 191)
    col = lerp3(C(70, 44, 26), C(120, 80, 48), n1)
    return {"albedo": col, "rough": np.full(n, 0.7), "metal": np.zeros(n), "height": (n1 - 0.5) * 0.0004}


def dirt(ctx):
    n = ctx.n
    n1 = fbm3(ctx.P * 6, 1, 4, 195)
    n2 = fbm3(ctx.P * 30, 1, 2, 196)
    col = lerp3(C(92, 76, 56), C(134, 114, 86), n1)
    leaves = smoothstep((n2 - 0.72) / 0.05)
    col = lerp3(col, C(150, 96, 52), leaves * 0.6)
    hm = np.zeros(n)
    rough = np.full(n, 0.97)
    col = add_moss(ctx, col, rough, hm, np.maximum(ctx.meta_value("moss", 0.4), 0), col=C(96, 106, 48), col2=C(126, 132, 60))
    return {"albedo": np.clip(col, 0, 1), "rough": rough, "metal": np.zeros(n), "height": (n1 - 0.5) * 0.01 + hm}


def fungus(ctx):
    n = ctx.n
    n1 = fbm3(ctx.P * 50, 1, 3, 197)
    col = lerp3(C(150, 110, 70), C(206, 168, 120), n1)
    return {"albedo": col, "rough": np.full(n, 0.7), "metal": np.zeros(n), "height": np.zeros(n)}


def fern(ctx):
    n = ctx.n
    n1 = fbm3(ctx.P * 20, 1, 3, 198)
    col = lerp3(C(60, 92, 38), C(118, 146, 62), n1)
    return {"albedo": col, "rough": np.full(n, 0.7), "metal": np.zeros(n), "height": np.zeros(n)}


SHADERS = {
    "oak": oak, "plank": plank_wood, "dark_oak": dark_oak, "limestone": limestone, "rock": granite_rock,
    "iron": iron, "bronze": bronze, "enamel": enamel, "amber": gem, "gem_green": gem_green,
    "birch": birch_bark, "root": root_bark, "log_bark": log_bark, "rope": rope, "bone": bone,
    "shingles": shingles, "cloth": cloth, "burlap": burlap, "linen": linen, "bread": bread, "grain": grain,
    "feather": feather, "leather": leather, "dirt": dirt, "fungus": fungus, "fern": fern,
}
