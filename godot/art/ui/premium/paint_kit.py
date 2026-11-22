#!/usr/bin/env python3
"""DRENOVAR premium UI kit — procedural painter.

Original art, painted from code (numpy + PIL): carved dark oak, forged bronze, gilded
plates, enamel, linen, cross-stitch embroidery (rushnyk). No third-party images.

Every texture is painted at S texels per canvas unit (S = 2: crisp on iPhone 12, whose
canvas scale is 1170/630 = 1.86). bake_kit.gd stores each one as a lossless
PortableCompressedTexture2D whose size_override is the canvas size, so nine-patch
margins below are given in canvas units.

    python3 godot/art/ui/premium/paint_kit.py /tmp/kit_png
    godot --headless --path godot/project -s res://tools/bake_ui_kit.gd -- --src=/tmp/kit_png

The PNGs are an intermediate; only the baked .res files are kept in the project.
"""
import math
import os
import sys

import numpy as np
from PIL import Image

S = 2  # texels per canvas unit


# ---------------------------------------------------------------- helpers

def hexc(value, alpha=1.0):
    value = value.lstrip('#')
    return np.array([int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4)] + [alpha], np.float32)


def grid(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    return (x + 0.5) / S, (y + 0.5) / S  # canvas units


def smooth(e0, e1, v):
    t = np.clip((v - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def tile_noise(w, h, cx, cy, seed):
    """Value noise that tiles on both axes: bicubic upsample of a wrapped grid."""
    r = np.random.default_rng(seed).random((cy, cx)).astype(np.float32)
    big = Image.fromarray(np.tile(r, (3, 3)), 'F').resize((w * 3, h * 3), Image.BICUBIC)
    return np.asarray(big)[h:2 * h, w:2 * w].copy()


def fbm(w, h, base, octaves, seed, gain=0.5):
    total = np.zeros((h, w), np.float32)
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        c = base * (2 ** o)
        total += amp * tile_noise(w, h, max(1, int(c * w / h)) if w > h else c, max(1, int(c * h / w)) if h > w else c, seed + o)
        norm += amp
        amp *= gain
    return total / norm


def ramp(t, stops):
    """Colour ramp: stops = [(pos, '#rrggbb'), ...]; t in 0..1 -> RGB."""
    t = np.clip(t, 0.0, 1.0)
    pos = np.array([s[0] for s in stops], np.float32)
    cols = np.array([hexc(s[1])[:3] for s in stops], np.float32)
    out = np.zeros(t.shape + (3,), np.float32)
    for ch in range(3):
        out[..., ch] = np.interp(t, pos, cols[:, ch])
    return out


def light(height, strength, direction=(-0.42, -0.78, 0.46)):
    """Lambert term of a height field (height in canvas units)."""
    gy, gx = np.gradient(height * S)
    nx, ny, nz = -gx * strength, -gy * strength, np.ones_like(height)
    n = np.sqrt(nx * nx + ny * ny + nz * nz)
    lx, ly, lz = direction
    ln = math.sqrt(lx * lx + ly * ly + lz * lz)
    return (nx * lx + ny * ly + nz * lz) / (n * ln)


def sdf_chamfer(x, y, cx, cy, hw, hh, cut):
    px, py = np.abs(x - cx), np.abs(y - cy)
    box = np.maximum(px - hw, py - hh)
    corner = (px + py - (hw + hh - cut)) / math.sqrt(2.0)
    return np.maximum(box, corner)


def sdf_round(x, y, cx, cy, hw, hh, r):
    qx = np.abs(x - cx) - hw + r
    qy = np.abs(y - cy) - hh + r
    outside = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2)
    return outside + np.minimum(np.maximum(qx, qy), 0) - r


def sdf_circle(x, y, cx, cy, r):
    return np.sqrt((x - cx) ** 2 + (y - cy) ** 2) - r


def sdf_rhombus(x, y, cx, cy, rx, ry):
    return (np.abs(x - cx) / rx + np.abs(y - cy) / ry - 1.0) * min(rx, ry) / math.sqrt(2.0)


def sdf_segment(x, y, ax, ay, bx, by):
    pax, pay, bax, bay = x - ax, y - ay, bx - ax, by - ay
    h = np.clip((pax * bax + pay * bay) / (bax * bax + bay * bay), 0.0, 1.0)
    return np.sqrt((pax - bax * h) ** 2 + (pay - bay * h) ** 2)


def coverage(d):
    """Anti-aliased inside coverage of a signed distance (canvas units)."""
    return np.clip(0.5 - d * S, 0.0, 1.0)


def over(dst, rgb, alpha):
    """Composite rgb (H,W,3) with alpha (H,W) over dst RGBA (premultiplied maths, straight store)."""
    a = alpha[..., None]
    out_a = a + dst[..., 3:4] * (1 - a)
    safe = np.where(out_a > 1e-6, out_a, 1.0)
    dst[..., :3] = (rgb * a + dst[..., :3] * dst[..., 3:4] * (1 - a)) / safe
    dst[..., 3:4] = out_a
    return dst


def blur(alpha, radius):
    im = Image.fromarray((np.clip(alpha, 0, 1) * 255).astype(np.uint8), 'L')
    from PIL import ImageFilter
    return np.asarray(im.filter(ImageFilter.GaussianBlur(radius * S)), np.float32) / 255.0


def save(name, rgba, out):
    img = Image.fromarray((np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGBA')
    img.save(os.path.join(out, name + '.png'), optimize=True)


def canvas(w, h):
    return np.zeros((h * S, w * S, 4), np.float32)


# ---------------------------------------------------------------- materials

def bronze(lit, polish=1.0, tone='bronze'):
    stops = {
        'bronze': [(0.0, '#2a1a0a'), (0.35, '#6b451b'), (0.62, '#b07b35'), (0.82, '#e2b766'), (1.0, '#fff0c4')],
        'gold':   [(0.0, '#3a2408'), (0.35, '#8a5c1e'), (0.62, '#d3a24c'), (0.82, '#f6d989'), (1.0, '#fffbe6')],
        'iron':   [(0.0, '#1d1d1c'), (0.35, '#3f3e3b'), (0.62, '#6f6c66'), (0.82, '#a29e95'), (1.0, '#e6e2d8')],
    }[tone]
    t = np.clip(lit * 0.5 + 0.45, 0, 1)
    rgb = ramp(t, stops)
    spec = np.clip(lit - 0.55, 0, 1) ** 2 * 1.6 * polish
    return np.clip(rgb + spec[..., None] * hexc('#fff4d6')[:3], 0, 1)


def wood(w, h, seed, dark='#20150d', mid='#3b2818', light_c='#5a3e25', stretch=26.0):
    """Dark oak with horizontal grain; tiles on x (w texels per period)."""
    base = fbm(w, h, 3, 4, seed)
    warp = tile_noise(w, h, max(1, w // 48), max(2, h // 6), seed + 10)
    y = np.mgrid[0:h, 0:w][0].astype(np.float32) / S
    rings = np.sin((y + warp * 9.0) * (2 * math.pi / 3.1)) * 0.5 + 0.5
    fine = tile_noise(w, h, max(1, w // 3), max(1, h // 1), seed + 20)
    t = 0.34 + 0.30 * base + 0.18 * rings * (0.6 + 0.4 * base) + 0.10 * (fine - 0.5)
    rgb = ramp(t, [(0.0, dark), (0.5, mid), (1.0, light_c)])
    return rgb


def linen(w, h, seed, base='#efe5cf'):
    """Warm linen: woven threads, slow mottling; tiles on both axes."""
    col = hexc(base)[:3]
    mott = fbm(w, h, 2, 4, seed) - 0.5
    weft = tile_noise(w, h, max(1, w // 64), max(1, h // 2), seed + 3) - 0.5
    warp = tile_noise(w, h, max(1, w // 2), max(1, h // 64), seed + 4) - 0.5
    speck = (np.random.default_rng(seed + 5).random((h, w)).astype(np.float32) - 0.5)
    shade = 1.0 + 0.055 * mott + 0.022 * weft + 0.022 * warp + 0.012 * speck
    return np.clip(col[None, None, :] * shade[..., None], 0, 1)


# ---------------------------------------------------------------- textures

def body_tile(out):
    w = h = 128
    W, H = w * S, h * S
    rgb = linen(W, H, 7)
    # Very faint embossed rhombus lattice (Slavic lozenge), period 64 canvas units.
    x, y = grid(W, H)
    u = (x % 64.0) - 32.0
    v = (y % 64.0) - 32.0
    lattice = np.abs(np.abs(u) + np.abs(v) - 30.0)
    ridge = 1.0 - smooth(0.0, 1.4, lattice)
    lit = light(ridge * 0.6, 1.2)
    rgb = rgb * (1.0 + 0.035 * (lit - 0.62)[..., None]) * (1.0 - 0.012 * ridge[..., None])
    a = canvas(w, h)
    a[..., :3] = rgb
    a[..., 3] = 1.0
    save('kit_body', a, out)


def header_band(out):
    w, h = 256, 68
    W, H = w * S, h * S
    x, y = grid(W, H)
    a = canvas(w, h)
    plank_h = 56.0
    rgb = wood(W, H, 11)
    # Plank shading: darker toward its top and bottom edges, carved grooves.
    edge = smooth(0, 7, y) * smooth(0, 9, plank_h - y)
    rgb *= (0.62 + 0.38 * edge)[..., None]
    for gy in (5.0, plank_h - 6.0):
        groove = np.exp(-((y - gy) / 0.55) ** 2)
        lip = np.exp(-((y - gy - 1.0) / 0.55) ** 2)
        rgb = rgb * (1 - 0.45 * groove)[..., None] + lip[..., None] * hexc('#8a6440')[:3] * 0.35
    plank = (y < plank_h).astype(np.float32)
    a = over(a, rgb, plank)
    # Bronze trim with an embossed running lozenge (period 16).
    top, bot = plank_h - 1.0, plank_h + 8.0
    band = smooth(top - 0.4, top + 0.4, y) * (1 - smooth(bot - 0.4, bot + 0.4, y))
    cy = (top + bot) / 2
    u = (x % 16.0) - 8.0
    loz = 1.0 - smooth(-0.3, 0.6, np.abs(u) / 6.2 + np.abs(y - cy) / 3.0 - 1.0)
    dots = 1.0 - smooth(-0.2, 0.5, np.sqrt(((x + 8.0) % 16.0 - 8.0) ** 2 + (y - cy) ** 2) - 1.1)
    height = smooth(top, top + 1.6, y) * (1 - smooth(bot - 1.6, bot, y)) * 0.8 + loz * 0.9 + dots * 0.7
    lit = light(height, 1.6)
    metal = bronze(lit, 1.0)
    a = over(a, metal, band)
    # Soft shadow under the trim onto the window body.
    shadow = (1 - smooth(bot, h, y)) * (y > bot) * 0.55
    a = over(a, np.zeros_like(metal), shadow)
    save('kit_header', a, out)


def frame(out):
    """Window rim for docked and centred windows: oak + bronze, corner brackets."""
    w = h = 96
    W, H = w * S, h * S
    x, y = grid(W, H)
    a = canvas(w, h)
    d = sdf_round(x, y, w / 2, h / 2, w / 2 - 1.0, h / 2 - 1.0, 2.5)
    outer = coverage(d)
    inner_d = d + 7.0
    ring = outer * (1 - coverage(inner_d))
    # rim height profile: bronze bevel between d=-2 and d=-6, oak edge outside it
    t = -d
    height = smooth(1.5, 3.0, t) * (1 - smooth(5.5, 7.0, t)) * 1.2
    lit = light(height, 1.5)
    metal = bronze(lit, 0.9)
    oak = wood(W, H, 31) * 0.8
    metal_mask = smooth(1.2, 2.2, t) * (1 - smooth(6.2, 7.0, t))
    rgb = oak * (1 - metal_mask[..., None]) + metal * metal_mask[..., None]
    a = over(a, rgb, ring)
    # inner shadow onto the body
    inner_shadow = coverage(-inner_d) * (1 - smooth(0, 6, -inner_d)) * 0.28
    a = over(a, np.zeros((H, W, 3), np.float32), inner_shadow)
    # corner brackets: L plates with a lozenge rivet
    for cx, cy, sx, sy in ((0, 0, 1, 1), (w, 0, -1, 1), (0, h, 1, -1), (w, h, -1, -1)):
        lx = (x - cx) * sx
        ly = (y - cy) * sy
        plate = np.maximum(np.minimum(np.maximum(lx - 24, ly - 7.5), np.maximum(lx - 7.5, ly - 24)), -np.minimum(lx, ly) + 1.0)
        plate = np.maximum(plate, (lx + ly - 30.0) / math.sqrt(2))
        pm = coverage(plate)
        riv = sdf_rhombus(lx, ly, 9.5, 9.5, 4.2, 4.2)
        ph = smooth(0, 1.6, -plate) * 0.9 + (1 - smooth(-1.0, 0.5, riv)) * 1.0
        plit = light(ph, 1.7)
        a = over(a, bronze(plit, 1.1, 'gold'), pm)
    save('kit_frame', a, out)


BUTTONS = {
    'primary':   {'face': [(0.0, '#fbe6a6'), (0.45, '#e2b45d'), (1.0, '#a8702a')], 'rim': 'bronze', 'gloss': 0.35},
    'secondary': {'face': [(0.0, '#5b93c8'), (0.45, '#2c5e93'), (1.0, '#183a60')], 'rim': 'bronze', 'gloss': 0.30},
    'green':     {'face': [(0.0, '#6fb36e'), (0.45, '#3a7b43'), (1.0, '#1f4d2a')], 'rim': 'bronze', 'gloss': 0.28},
    'danger':    {'face': [(0.0, '#d76a5f'), (0.45, '#a3343a'), (1.0, '#651a21')], 'rim': 'bronze', 'gloss': 0.28},
    'tertiary':  {'face': [(0.0, '#fbf5e7'), (0.5, '#efe3c8'), (1.0, '#d9c6a0')], 'rim': 'bronze', 'gloss': 0.20},
    'disabled':  {'face': [(0.0, '#a6a39b'), (0.5, '#8b8881'), (1.0, '#6c6a65')], 'rim': 'iron', 'gloss': 0.08},
}


def button(out, kind, pressed=False):
    spec = BUTTONS[kind]
    w, h = 112, 52
    W, H = w * S, h * S
    x, y = grid(W, H)
    a = canvas(w, h)
    cx, cy = w / 2, (h - 2) / 2
    hw, hh = w / 2 - 2.0, h / 2 - 3.5
    d = sdf_chamfer(x, y, cx, cy, hw, hh, 8.0)
    if not pressed:
        shadow = blur(coverage(sdf_chamfer(x, y, cx, cy + 2.0, hw, hh, 8.0)), 1.4) * 0.45
        a = over(a, np.zeros((H, W, 3), np.float32), shadow)
    shape = coverage(d)
    t = -d
    rim_w = 2.6 if kind != 'tertiary' else 2.2
    # face: vertical gradient + gloss on the upper half, brushed noise
    fy = (y - (cy - hh)) / (2 * hh)
    stops = spec['face']
    if pressed:
        stops = [(p, '#%02x%02x%02x' % tuple(int(c * 255 * 0.84) for c in hexc(col)[:3])) for p, col in stops]
    face = ramp(fy, stops)
    brushed = tile_noise(W, H, max(1, W // 40), max(1, H // 2), 51) - 0.5
    face = face * (1 + 0.05 * brushed[..., None])
    gloss_y = (0.30 if not pressed else 0.78)
    gloss = np.exp(-((fy - gloss_y) / 0.16) ** 2) * spec['gloss'] * smooth(rim_w, rim_w + 6, t)
    face = np.clip(face + gloss[..., None] * (0.55 if kind in ('primary', 'tertiary') else 0.35), 0, 1)
    # engraved groove one unit inside the rim
    groove_d = t - (rim_w + 2.2)
    groove = np.exp(-(groove_d / 0.45) ** 2)
    face = face * (1 - 0.22 * groove[..., None]) + np.exp(-((groove_d - 0.7) / 0.45) ** 2)[..., None] * 0.10
    # rhombus rivets at both ends
    rivet = np.minimum(sdf_rhombus(x, y, 9.0, cy, 3.0, 4.0), sdf_rhombus(x, y, w - 9.0, cy, 3.0, 4.0))
    rivet_m = coverage(rivet)
    # rim bevel
    height = smooth(0.0, rim_w * 0.55, t) * (1 - smooth(rim_w * 0.55, rim_w + 0.4, t)) * 1.0 + smooth(0, 1.2, -rivet) * 0.9
    direction = (-0.42, -0.78, 0.46) if not pressed else (0.3, 0.8, 0.5)
    lit = light(height, 1.7, direction)
    metal = bronze(lit, 0.9, spec['rim'] if kind != 'primary' else 'gold')
    rim_m = 1 - smooth(rim_w - 0.4, rim_w + 0.4, t)
    rgb = face * (1 - rim_m[..., None]) + metal * rim_m[..., None]
    rgb = rgb * (1 - rivet_m[..., None]) + metal * rivet_m[..., None]
    a = over(a, rgb, shape)
    save('kit_btn_%s%s' % (kind, '_pressed' if pressed else ''), a, out)


def medallion(out, name, size, ring_tone, face_stops, glyph=None, glow=None, pressed=False):
    w = h = size
    W, H = w * S, h * S
    x, y = grid(W, H)
    a = canvas(w, h)
    c = size / 2
    r = size / 2 - (6.0 if glow else 2.5)
    if glow is not None:
        g = blur(coverage(sdf_circle(x, y, c, c, r + 2.2)), 2.6)
        a = over(a, np.broadcast_to(hexc(glow)[:3], (H, W, 3)).copy(), g * 0.95)
    elif not pressed:
        sh = blur(coverage(sdf_circle(x, y, c, c + 1.8, r)), 1.2) * 0.45
        a = over(a, np.zeros((H, W, 3), np.float32), sh)
    d = sdf_circle(x, y, c, c, r)
    t = -d
    ring_w = max(3.0, size * 0.075)
    fy = (y - (c - r)) / (2 * r)
    rr = np.sqrt((x - c) ** 2 + (y - c * 0.8) ** 2) / r
    face = ramp(np.clip(rr * 0.8 + fy * 0.2, 0, 1), face_stops)
    if pressed:
        face *= 0.82
    height = smooth(0, ring_w * 0.5, t) * (1 - smooth(ring_w * 0.5, ring_w + 0.5, t))
    if glyph == 'x':
        arm = r * 0.42
        bars = np.minimum(sdf_segment(x, y, c - arm, c - arm, c + arm, c + arm), sdf_segment(x, y, c - arm, c + arm, c + arm, c - arm)) - r * 0.12
        height = height + smooth(0, 1.6, -bars) * 1.0
        glyph_m = coverage(bars)
    else:
        glyph_m = np.zeros_like(d)
    direction = (-0.42, -0.78, 0.46) if not pressed else (0.3, 0.8, 0.5)
    lit = light(height, 1.6, direction)
    metal = bronze(lit, 1.0, ring_tone)
    ring_m = 1 - smooth(ring_w - 0.4, ring_w + 0.4, t)
    m = np.maximum(ring_m, glyph_m)
    rgb = face * (1 - m[..., None]) + metal * m[..., None]
    # inner shadow under the ring
    inner = np.exp(-((t - ring_w - 0.8) / 1.2) ** 2) * 0.35 * (1 - m)
    rgb = rgb * (1 - inner[..., None])
    a = over(a, rgb, coverage(d))
    save(name, a, out)


def card_parts(out):
    """Tier card: neutral fill (tinted at runtime) + bronze frame, chamfered."""
    w, h = 100, 132
    W, H = w * S, h * S
    x, y = grid(W, H)
    d = sdf_chamfer(x, y, w / 2, h / 2, w / 2 - 1.5, h / 2 - 1.5, 9.0)
    fill = canvas(w, h)
    fy = y / h
    g = ramp(fy, [(0.0, '#ffffff'), (0.6, '#c9c9c9'), (1.0, '#7a7a7a')])
    tex = fbm(W, H, 3, 3, 71) - 0.5
    g = g * (1 + 0.06 * tex[..., None])
    fill = over(fill, g, coverage(d + 1.0))
    save('kit_card_fill', fill, out)
    fr = canvas(w, h)
    t = -d
    rim_w = 3.2
    height = smooth(0, 1.6, t) * (1 - smooth(1.8, rim_w + 0.3, t))
    lit = light(height, 1.6)
    metal = bronze(lit, 1.0)
    rim_m = coverage(d) * (1 - smooth(rim_w - 0.4, rim_w + 0.4, t))
    fr = over(fr, metal, rim_m)
    inner = coverage(d) * np.exp(-((t - rim_w - 1.0) / 1.4) ** 2) * 0.45 * (t > rim_w)
    fr = over(fr, np.zeros((H, W, 3), np.float32), inner)
    save('kit_card_frame', fr, out)
    # kokoshnik badge (ogee arch) for the tier numeral
    bw, bh = 36, 34
    BW, BH = bw * S, bh * S
    x, y = grid(BW, BH)
    b = canvas(bw, bh)
    cx = bw / 2
    # arch = union of a box (lower part) and the intersection of two circles (pointed top)
    box = sdf_round(x, y, cx, 22.0, 15.0, 10.5, 2.0)
    rad = 19.0
    left = sdf_circle(x, y, cx + 6.5, 20.0, rad)
    right = sdf_circle(x, y, cx - 6.5, 20.0, rad)
    arch = np.maximum(left, right)
    shape_d = np.minimum(box, arch)
    shape_d = np.maximum(shape_d, y - 32.5)
    t = -shape_d
    height = smooth(0, 1.4, t) * (1 - smooth(1.6, 3.0, t)) + 0.0
    lit = light(height, 1.7)
    metal = bronze(lit, 1.1, 'gold')
    face = ramp(y / bh, [(0.0, '#3b2a1e'), (1.0, '#1b120c')])
    ring_m = 1 - smooth(2.4, 3.2, t)
    rgb = face * (1 - ring_m[..., None]) + metal * ring_m[..., None]
    sh = blur(coverage(shape_d - 0.2), 1.0) * 0.5
    b = over(b, np.zeros((BH, BW, 3), np.float32), np.roll(sh, int(1.5 * S), axis=0))
    b = over(b, rgb, coverage(shape_d))
    save('kit_badge', b, out)


def strip(out):
    """Dark oak cost strip with bronze rails and lozenge end caps."""
    w, h = 160, 46
    W, H = w * S, h * S
    x, y = grid(W, H)
    a = canvas(w, h)
    body_d = sdf_round(x, y, w / 2, h / 2, w / 2 - 10.0, h / 2 - 5.0, 3.0)
    rgb = wood(W, H, 81, dark='#1c130c', mid='#33231a', light_c='#4d3624') * 0.95
    t = -body_d
    edge = smooth(0, 5, t)
    rgb = rgb * (0.7 + 0.3 * edge)[..., None]
    sh = blur(coverage(body_d), 1.2) * 0.4
    a = over(a, np.zeros((H, W, 3), np.float32), np.roll(sh, int(2 * S), axis=0))
    a = over(a, rgb, coverage(body_d))
    rail_h = smooth(0, 0.8, t) * (1 - smooth(1.4, 2.2, t))
    lit = light(rail_h, 1.5)
    rail_m = coverage(body_d) * (1 - smooth(1.8, 2.4, t))
    a = over(a, bronze(lit, 0.9), rail_m)
    for cx in (9.0, w - 9.0):
        cap = sdf_rhombus(x, y, cx, h / 2, 8.0, 13.0)
        ch = smooth(0, 2.0, -cap) * 0.9 + (1 - smooth(-0.5, 0.6, sdf_rhombus(x, y, cx, h / 2, 2.5, 4.0))) * 0.8
        a = over(a, bronze(light(ch, 1.7), 1.0), coverage(cap))
    save('kit_strip', a, out)


def pill(out):
    w, h = 120, 36
    W, H = w * S, h * S
    x, y = grid(W, H)
    a = canvas(w, h)
    d = sdf_round(x, y, w / 2, h / 2 - 0.5, w / 2 - 1.5, h / 2 - 2.5, h / 2 - 2.5)
    t = -d
    face = ramp(y / h, [(0.0, '#3d2c1f'), (1.0, '#1a110b')])
    sheen = np.exp(-((y / h - 0.25) / 0.14) ** 2) * 0.10
    face = face + sheen[..., None]
    height = smooth(0, 1.0, t) * (1 - smooth(1.2, 2.2, t))
    metal = bronze(light(height, 1.6), 1.0)
    rim = 1 - smooth(1.9, 2.5, t)
    rgb = face * (1 - rim[..., None]) + metal * rim[..., None]
    a = over(a, rgb, coverage(d))
    save('kit_pill', a, out)


def row_card(out):
    w, h = 96, 64
    W, H = w * S, h * S
    x, y = grid(W, H)
    a = canvas(w, h)
    d = sdf_chamfer(x, y, w / 2, h / 2 - 1.0, w / 2 - 2.0, h / 2 - 3.0, 6.0)
    sh = blur(coverage(d), 1.5) * 0.30
    a = over(a, np.zeros((H, W, 3), np.float32), np.roll(sh, int(1.5 * S), axis=0))
    t = -d
    face = linen(W, H, 91, '#f7f0e0') * ramp(y / h, [(0.0, '#ffffff'), (1.0, '#e8dcc3')])
    groove = np.exp(-((t - 3.6) / 0.45) ** 2) * 0.16
    face = face * (1 - groove[..., None])
    height = smooth(0, 0.8, t) * (1 - smooth(1.0, 1.9, t))
    metal = bronze(light(height, 1.4), 0.6)
    rim = 1 - smooth(1.5, 2.1, t)
    rgb = face * (1 - rim[..., None]) + metal * rim[..., None]
    a = over(a, rgb, coverage(d))
    save('kit_row', a, out)


def icon_tile(out):
    w = h = 64
    W, H = w * S, h * S
    x, y = grid(W, H)
    a = canvas(w, h)
    d = sdf_chamfer(x, y, w / 2, h / 2, w / 2 - 2.0, h / 2 - 2.0, 7.0)
    t = -d
    rr = np.sqrt((x - w * 0.45) ** 2 + (y - h * 0.38) ** 2) / (w * 0.6)
    face = ramp(rr, [(0.0, '#4d5b58'), (0.6, '#27302f'), (1.0, '#151b1b')])
    height = smooth(0, 1.4, t) * (1 - smooth(1.6, 3.2, t))
    metal = bronze(light(height, 1.6), 1.0)
    rim = 1 - smooth(2.8, 3.4, t)
    inner = np.exp(-((t - 4.0) / 1.5) ** 2) * 0.35 * (1 - rim)
    rgb = face * (1 - inner[..., None]) * (1 - rim[..., None]) + metal * rim[..., None]
    a = over(a, rgb, coverage(d))
    save('kit_tile', a, out)


def field(out):
    w, h = 96, 44
    W, H = w * S, h * S
    x, y = grid(W, H)
    a = canvas(w, h)
    d = sdf_round(x, y, w / 2, h / 2, w / 2 - 1.0, h / 2 - 1.0, 5.0)
    t = -d
    face = ramp(y / h, [(0.0, '#e9dec6'), (0.3, '#fbf6ea'), (1.0, '#fffdf6')])
    inner = np.exp(-((t - 1.5) / 2.2) ** 2) * 0.22 * (y < h * 0.6)
    face = face * (1 - inner[..., None])
    height = 1 - smooth(0, 1.4, t)
    metal = bronze(light(-height, 1.2), 0.5)
    rim = 1 - smooth(1.0, 1.6, t)
    rgb = face * (1 - rim[..., None]) + metal * rim[..., None]
    a = over(a, rgb, coverage(d))
    save('kit_field', a, out)


def progress(out):
    w, h = 96, 22
    W, H = w * S, h * S
    x, y = grid(W, H)
    d = sdf_round(x, y, w / 2, h / 2, w / 2 - 1.0, h / 2 - 1.0, h / 2 - 1.0)
    t = -d
    track = canvas(w, h)
    face = ramp(y / h, [(0.0, '#0f0a06'), (1.0, '#3a2a1c')])
    height = smooth(0, 1.0, t) * (1 - smooth(1.2, 2.0, t))
    metal = bronze(light(height, 1.4), 0.8)
    rim = 1 - smooth(1.6, 2.2, t)
    track = over(track, face * (1 - rim[..., None]) + metal * rim[..., None], coverage(d))
    save('kit_track', track, out)
    fill = canvas(w, h)
    fd = d + 2.0
    fy = y / h
    g = ramp(fy, [(0.0, '#fff1bf'), (0.35, '#f1c35f'), (1.0, '#a4651f')])
    g = g + (np.exp(-((fy - 0.3) / 0.12) ** 2) * 0.25)[..., None]
    fill = over(fill, np.clip(g, 0, 1), coverage(fd))
    save('kit_fill', fill, out)
    # green fill for health/positive bars
    fill2 = canvas(w, h)
    g2 = ramp(fy, [(0.0, '#d9f5a8'), (0.35, '#7dbb4f'), (1.0, '#2f6a24')])
    fill2 = over(fill2, g2, coverage(fd))
    save('kit_fill_green', fill2, out)


def knob(out):
    w = h = 34
    W, H = w * S, h * S
    x, y = grid(W, H)
    a = canvas(w, h)
    c = w / 2
    sh = blur(coverage(sdf_circle(x, y, c, c + 1.5, 14.0)), 1.2) * 0.5
    a = over(a, np.zeros((H, W, 3), np.float32), sh)
    d = sdf_circle(x, y, c, c, 14.0)
    t = -d
    loz = sdf_rhombus(x, y, c, c, 5.0, 7.0)
    height = smooth(0, 3.0, t) * 0.8 + (1 - smooth(-0.6, 0.6, loz)) * 0.7
    lit = light(height, 1.5)
    rgb = bronze(lit, 1.2, 'gold')
    enamel = 1 - smooth(-0.6, 0.4, sdf_rhombus(x, y, c, c, 3.2, 4.8))
    rgb = rgb * (1 - enamel[..., None]) + hexc('#a3343a')[:3] * enamel[..., None]
    a = over(a, rgb, coverage(d))
    save('kit_knob', a, out)


def embroidery(out):
    """Rushnyk cross-stitch band: red lozenge chain with black accents; tiles on x (period 24)."""
    w, h = 24, 12
    W, H = w * S, h * S
    a = canvas(w, h)
    # stitch grid: 1 canvas unit per stitch (2 texels)
    red = hexc('#b4232c')[:3]
    blk = hexc('#2a1a17')[:3]
    pattern = [
        "............................",
    ]
    cells = np.zeros((h, w), np.int8)
    cy = h // 2
    for cx in range(w):
        # lozenge chain: |dx| + |dy| == 4 (outline) around centres every 12 units
        dx = ((cx + 6) % 12) - 6
        for cyy in range(h):
            dy = cyy - cy
            r = abs(dx) + abs(dy)
            if r == 4:
                cells[cyy, cx] = 1
            elif r == 1 or (dx == 0 and dy == 0):
                cells[cyy, cx] = 2
        # border lines
        cells[0, cx] = 1 if cx % 2 == 0 else 0
        cells[h - 1, cx] = 1 if cx % 2 == 0 else 0
        # black crosses between lozenges
        dx2 = (cx % 12) - 6
        if abs(dx2) + abs(cy - cy) == 0:
            pass
    for cyy in range(h):
        for cx in range(w):
            if (cx % 12 == 0) and abs(cyy - cy) <= 1 and cells[cyy, cx] == 0:
                cells[cyy, cx] = 2
    for cyy in range(h):
        for cx in range(w):
            v = cells[cyy, cx]
            if not v:
                continue
            col = red if v == 1 else blk
            # one stitch = a small X across 2x2 texels, slightly rounded
            px, py = cx * S, cyy * S
            a[py:py + S, px:px + S, :3] = col
            a[py:py + S, px:px + S, 3] = 0.92
    save('kit_stitch', a, out)
    # end ornament: an eight-point star rosette (12x12 units, stitched)
    w2 = h2 = 13
    b = canvas(w2, h2)
    c = 6
    for yy in range(h2):
        for xx in range(w2):
            dx, dy = xx - c, yy - c
            r = abs(dx) + abs(dy)
            m = max(abs(dx), abs(dy))
            v = 0
            if r == 6 or (m == 4 and r >= 4 and (dx == 0 or dy == 0 or abs(dx) == abs(dy))):
                v = 1
            if r <= 1:
                v = 2
            if (abs(dx) == abs(dy)) and 2 <= abs(dx) <= 3:
                v = 1
            if v:
                col = red if v == 1 else blk
                b[yy * S:(yy + 1) * S, xx * S:(xx + 1) * S, :3] = col
                b[yy * S:(yy + 1) * S, xx * S:(xx + 1) * S, 3] = 0.95
    save('kit_rosette', b, out)


def flourish(out):
    """Bronze title flourish (left side; mirrored for the right): a tapering bar that
    ends in a curl, with a lozenge and two dots."""
    w, h = 110, 26
    W, H = w * S, h * S
    x, y = grid(W, H)
    a = canvas(w, h)
    cy = h / 2
    # tapering bar from x=18 to x=98
    t = np.clip((x - 18.0) / 80.0, 0, 1)
    thick = 0.5 + 1.4 * t
    bar = np.abs(y - cy) - thick
    bar = np.maximum(bar, np.maximum(18.0 - x, x - 98.0))
    # curl at the left end: ring arc
    ring = np.abs(sdf_circle(x, y, 13.0, cy - 2.6, 4.2)) - 0.9
    ring = np.maximum(ring, -(y - (cy - 2.6)) - 0.0 + 0.0 * x)  # keep the lower half arc
    ring2 = np.abs(sdf_circle(x, y, 13.0, cy, 6.6)) - 0.9
    ring2 = np.maximum(ring2, (y - cy))  # upper half
    tail = sdf_segment(x, y, 6.4, cy, 18.0, cy) - 0.9
    loz = sdf_rhombus(x, y, 103.0, cy, 5.0, 4.0)
    dots = np.minimum(sdf_circle(x, y, 92.0, cy - 5.0, 1.2), sdf_circle(x, y, 92.0, cy + 5.0, 1.2))
    d = np.minimum.reduce([bar, ring2, tail, loz, dots])
    height = smooth(0, 1.2, -d)
    lit = light(height, 1.8)
    metal = bronze(lit, 1.2, 'gold')
    sh = blur(coverage(d), 0.8) * 0.65
    a = over(a, np.zeros((H, W, 3), np.float32), np.roll(sh, int(1.2 * S), axis=0))
    a = over(a, metal, coverage(d))
    save('kit_flourish', a, out)


def splash(out):
    """Soft ink-wash blot (white, alpha) — tinted at runtime behind hero art. 1 texel/unit:
    it is soft by nature, so a low resolution keeps it small without a visible loss."""
    n = 256
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    cx = cy = n / 2
    r = np.sqrt(((x - cx) / (n * 0.46)) ** 2 + ((y - cy) / (n * 0.40)) ** 2)
    noise = fbm(n, n, 4, 5, 123, 0.55) - 0.5
    noise2 = fbm(n, n, 10, 3, 321, 0.5) - 0.5
    field_v = r + noise * 0.55 + noise2 * 0.18
    alpha = 1 - smooth(0.55, 1.0, field_v)
    # dry-brush streaks
    grain = fbm(n, n, 24, 2, 77) - 0.5
    alpha = np.clip(alpha * (0.9 + 0.35 * grain), 0, 1)
    a = np.zeros((n, n, 4), np.float32)
    a[..., :3] = 1.0
    a[..., 3] = np.clip(alpha, 0, 1)
    img = Image.fromarray((a * 255).astype(np.uint8), 'RGBA')
    img.save(os.path.join(out, 'kit_splash.png'), optimize=True)


def body_dark(out):
    """Smoked oak body for result windows and dark plates; tiles on both axes."""
    w = h = 128
    W, H = w * S, h * S
    rgb = wood(W, H, 141, dark='#16100b', mid='#2a1e15', light_c='#3c2b1d')
    a = canvas(w, h)
    a[..., :3] = rgb
    a[..., 3] = 1.0
    save('kit_body_dark', a, out)


def hourglass(out):
    """Small bronze hourglass for timers (22 x 26 units)."""
    w, h = 22, 26
    W, H = w * S, h * S
    x, y = grid(W, H)
    a = canvas(w, h)
    cx = w / 2
    caps = np.minimum(sdf_round(x, y, cx, 3.2, 8.5, 1.9, 1.0), sdf_round(x, y, cx, h - 3.2, 8.5, 1.9, 1.0))
    # glass: two triangles meeting at the waist
    ty = np.abs(y - h / 2) / (h / 2 - 5.0)
    half_w = 1.2 + 5.6 * np.clip(ty, 0, 1)
    glass = np.maximum(np.abs(x - cx) - half_w, np.abs(y - h / 2) - (h / 2 - 5.0))
    rim = np.abs(glass) - 0.7
    posts = np.minimum(sdf_segment(x, y, cx - 7.2, 4.0, cx - 7.2, h - 4.0), sdf_segment(x, y, cx + 7.2, 4.0, cx + 7.2, h - 4.0)) - 0.8
    sand = np.maximum(glass + 0.8, -(y - (h / 2 + 3.0)))
    sand = np.minimum(sand, np.maximum(glass + 0.8, np.maximum(y - 9.0, -(y - 5.5)) ))
    metal_d = np.minimum.reduce([caps, rim, posts])
    height = smooth(0, 1.0, -metal_d)
    a = over(a, np.broadcast_to(hexc('#f4d27e')[:3], (H, W, 3)).copy(), coverage(sand) * 0.95)
    a = over(a, bronze(light(height, 1.6), 1.1, 'gold'), coverage(metal_d))
    save('kit_hourglass', a, out)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'kit_png'
    os.makedirs(out, exist_ok=True)
    body_tile(out)
    body_dark(out)
    hourglass(out)
    header_band(out)
    frame(out)
    for kind in BUTTONS:
        button(out, kind)
        if kind != 'disabled':
            button(out, kind, pressed=True)
    face_dark = [(0.0, '#3e2d20'), (0.7, '#22170f'), (1.0, '#140d08')]
    medallion(out, 'kit_close', 50, 'bronze', face_dark, glyph='x')
    medallion(out, 'kit_close_pressed', 50, 'bronze', face_dark, glyph='x', pressed=True)
    rail_face = [(0.0, '#36505a'), (0.7, '#1b2a31'), (1.0, '#101a1f')]
    medallion(out, 'kit_rail', 64, 'bronze', rail_face)
    medallion(out, 'kit_rail_on', 72, 'gold', rail_face, glow='#ffd36b')
    card_parts(out)
    strip(out)
    pill(out)
    row_card(out)
    icon_tile(out)
    field(out)
    progress(out)
    knob(out)
    embroidery(out)
    flourish(out)
    splash(out)
    total = sum(os.path.getsize(os.path.join(out, f)) for f in os.listdir(out))
    print('painted', len(os.listdir(out)), 'textures,', total // 1024, 'KiB of PNG in', out)


if __name__ == '__main__':
    main()
