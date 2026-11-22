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


def drop(alpha, rows):
    """Shift a shadow down by whole texels without wrapping (np.roll would bring the
    bottom rows back in at the top edge)."""
    moved = np.zeros_like(alpha)
    moved[rows:] = alpha[:alpha.shape[0] - rows]
    return moved


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


def header_band(out, name='kit_header', plank_h=56.0, split=None):
    """Carved oak header band. The tall variant (full-screen windows) is two boards: the
    upper one carries the resource plates, the lower one the window title."""
    w, h = 256, int(plank_h) + 12
    W, H = w * S, h * S
    x, y = grid(W, H)
    a = canvas(w, h)
    rgb = wood(W, H, 11)
    # Plank shading: darker toward its top and bottom edges, carved grooves.
    edge = smooth(0, 7, y) * smooth(0, 9, plank_h - y)
    if split is not None:
        # Joint between the two boards: a shaded seam, each board rounded toward it.
        edge = edge * (0.55 + 0.45 * smooth(0, 5, np.abs(y - split)))
    rgb *= (0.62 + 0.38 * edge)[..., None]
    grooves = [5.0, plank_h - 6.0] + ([split - 1.0] if split is not None else [])
    for gy in grooves:
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
    save(name, a, out)


def dais(out):
    """Carved oak band of the recruitment dais (3D drum around the stone slab; tiles on x).
    Slavic three-sided notch carving: a chain of lozenges with six-petal rosettes, notched
    triangle borders and bead ridges; the deepest cuts carry gold leaf. Writes the albedo
    (kit_dais) and a tangent-space normal map (kit_dais_n, OpenGL convention: +Y up)."""
    w, h = 256, 40
    W, H = w * S, h * S
    x, y = grid(W, H)
    rgb = wood(W, H, 171, dark='#3a2614', mid='#62432a', light_c='#8a6440', stretch=40.0)
    period = 32.0
    lx = np.mod(x, period) - period / 2.0
    ly = y - h / 2.0
    cut = np.zeros((H, W), np.float32)      # depth of the carving, 0..1
    gild = np.zeros((H, W), np.float32)
    ridge = np.zeros((H, W), np.float32)
    # Bead ridges along both edges.
    for gy in (2.6, h - 2.6):
        ridge = np.maximum(ridge, np.clip(1.0 - ((y - gy) / 1.5) ** 2, 0, 1))
    # Notched triangles under the top bead and over the bottom one (alternating).
    tx = np.mod(x, 8.0) - 4.0
    for top, sign in ((5.2, 1.0), (h - 5.2, -1.0)):
        t = (y - top) * sign  # 0 at the bead, grows toward the centre
        tri = np.maximum(np.abs(tx) - (3.6 - t * 0.9), -t)
        tri = np.maximum(tri, t - 4.0)
        cut = np.maximum(cut, coverage(tri) * smooth(0.0, 4.0, t) * 0.8)
    # Lozenge chain: an outline groove around each period, a raised inner field.
    rho = np.abs(lx) / 13.0 + np.abs(ly) / 10.5
    outline = np.abs(rho - 1.0) * 9.0 - 1.0
    cut = np.maximum(cut, coverage(outline) * 0.85)
    gild = np.maximum(gild, coverage(np.abs(rho - 1.0) * 9.0 - 0.45) * 0.9)
    # Six-petal rosette in each lozenge (the deepest cuts, gilded).
    r = np.sqrt(lx ** 2 + ly ** 2)
    ang = np.arctan2(ly, lx)
    petal = r - (5.6 * np.abs(np.cos(3.0 * ang)) ** 0.7 + 0.4)
    cut = np.maximum(cut, coverage(petal) * smooth(0.0, 5.0, 5.8 - r) * 1.0)
    gild = np.maximum(gild, coverage(petal + 0.6) * 0.95)
    hub = r - 1.1
    cut = np.minimum(cut, 1.0 - coverage(hub) * 0.7)
    # Small diamonds where two lozenges meet.
    jx = np.mod(x + period / 2.0, period) - period / 2.0
    knot = np.abs(jx) / 3.2 + np.abs(ly) / 3.2 - 1.0
    cut = np.maximum(cut, coverage(knot * 3.0) * 0.7)
    height = ridge * 0.8 - cut * 1.2
    # Albedo: carved faces catch less light and show the darker end grain.
    lit = light(height, 1.3)
    rgb = rgb * (0.78 + 0.32 * lit)[..., None] * (1.0 - 0.32 * cut)[..., None]
    # No gilding (it read as a gold trophy base): the deepest cuts are darker end grain,
    # the raised faces weathered to a lighter, greyer oak.
    rgb = rgb * (1.0 - 0.3 * gild)[..., None]
    weather = smooth(0.2, 0.8, ridge + (1.0 - cut) * 0.4) * (0.5 + 0.5 * fbm(W, H, 6, 3, 172))
    rgb = rgb * (1 - 0.25 * weather[..., None]) + hexc('#8f8577')[:3] * 0.25 * weather[..., None]
    a = canvas(w, h)
    a[..., :3] = rgb
    a[..., 3] = 1.0
    save('kit_dais', a, out)
    gy_, gx_ = np.gradient(height * 2.2)
    nx, ny, nz = -gx_, gy_, np.ones_like(height)
    n = np.sqrt(nx * nx + ny * ny + nz * nz)
    normal = canvas(w, h)
    normal[..., 0] = nx / n * 0.5 + 0.5
    normal[..., 1] = ny / n * 0.5 + 0.5
    normal[..., 2] = nz / n * 0.5 + 0.5
    normal[..., 3] = 1.0
    save('kit_dais_n', normal, out)


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
    b = over(b, np.zeros((BH, BW, 3), np.float32), drop(sh, int(1.5 * S)))
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



# ---------------------------------------------------------------- recruitment stage (stage 2b)

def rot(x, y, cx, cy, deg):
    """Coordinates rotated by deg around (cx, cy): shapes drawn in the rotated frame."""
    a = math.radians(deg)
    dx, dy = x - cx, y - cy
    return cx + dx * math.cos(a) + dy * math.sin(a), cy - dx * math.sin(a) + dy * math.cos(a)


def sdf_ucap(x, y, ax, ay, ra, bx, by, rb):
    """Uneven capsule from (ax, ay) radius ra to (bx, by) radius rb (exact, 2D)."""
    px, py = x - ax, y - ay
    dx, dy = bx - ax, by - ay
    h = math.hypot(dx, dy)
    ux, uy = dx / h, dy / h
    qx = px * uy - py * ux
    qy = px * ux + py * uy
    qx = np.abs(qx)
    b = (ra - rb) / h
    a = math.sqrt(max(0.0, 1.0 - b * b))
    k = qx * a - qy * b  # cross of (b, a) and (qx, qy) rearranged
    k = -qx * b + qy * a
    d_a = np.sqrt(qx * qx + qy * qy) - ra
    d_b = np.sqrt(qx * qx + (qy - h) ** 2) - rb
    d_m = qx * a + qy * b - ra
    return np.where(k < 0.0, d_a, np.where(k > a * h, d_b, d_m))


def halfplanes(x, y, points):
    """Convex polygon (clockwise in screen space) as the max of its edge half-planes."""
    d = None
    n = len(points)
    for i in range(n):
        ax, ay = points[i]
        bx, by = points[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        ln = math.hypot(ex, ey)
        side = ((x - ax) * ey - (y - ay) * ex) / ln
        d = side if d is None else np.maximum(d, side)
    return d


def relief(d, size, tone='gold', bevel=1.3, outline=0.85, grooves=None, shadow=0.55):
    """A forged glyph: bevelled metal inside the signed distance d, a dark outline around
    it (reads on linen and on enamel) and a soft drop shadow. grooves (0..1) are cut
    lines inside the glyph (eye, rings): darker and lower."""
    H, W = d.shape
    t = -d
    height = smooth(0, bevel, t)
    if grooves is not None:
        height = height - grooves * 0.9
    metal = bronze(light(height, 1.7), 1.0, tone)
    if grooves is not None:
        metal = metal * (1.0 - 0.55 * grooves[..., None])
    a = np.zeros((H, W, 4), np.float32)
    if shadow > 0:
        sh = blur(coverage(d - outline), 0.9) * shadow
        a = over(a, np.zeros((H, W, 3), np.float32), drop(sh, max(1, int(0.9 * S))))
    a = over(a, np.broadcast_to(hexc('#1a0f06')[:3], (H, W, 3)).copy(), coverage(d - outline))
    a = over(a, metal, coverage(d))
    return a


def ring_groove(x, y, cx, cy, r, w=0.55):
    return np.exp(-((np.sqrt((x - cx) ** 2 + (y - cy) ** 2) - r) / w) ** 2)


def emblems(out):
    """Rail emblems of the training buildings: forged gold glyphs that sit on the enamel
    discs of kit_rail / kit_rail_on (spear and shield, bow, horse head, ram)."""
    n = 56
    W = H = n * S
    x, y = grid(W, H)
    # Infantry: a spear across, a round shield with a boss in front of it.
    rx, ry = rot(x, y, 28, 28, -40)
    shaft = sdf_segment(rx, ry, 28, 50, 28, 12) - 1.25
    head = sdf_rhombus(rx, ry, 28, 8.0, 3.2, 7.5)
    spear = np.minimum(shaft, head)
    shield = sdf_circle(x, y, 24, 31, 13.5)
    d = np.minimum(spear, shield)
    grooves = ring_groove(x, y, 24, 31, 10.6, 0.5) * coverage(shield)
    grooves += np.exp(-(np.sqrt((x - 24) ** 2 + (y - 31) ** 2) - 3.6) ** 2 / 0.4) * 0.8
    # the shield covers the spear: a thin cut where they meet
    grooves += np.exp(-(shield / 0.45) ** 2) * coverage(spear) * 0.9
    save('kit_emb_inf', relief(d, n, grooves=np.clip(grooves, 0, 1)), out)
    # Archers: a drawn bow facing up-left with a nocked arrow.
    rx, ry = rot(x, y, 28, 28, 35)
    rr = np.sqrt((rx - 40.0) ** 2 + (ry - 28.0) ** 2)
    thick = 1.0 + 1.3 * np.clip(1.0 - np.abs(ry - 28.0) / 20.0, 0, 1)
    bow = np.maximum(np.abs(rr - 22.0) - thick, rx - 29.5)
    string = np.minimum(sdf_segment(rx, ry, 29.6, 8.6, 36.5, 28.0), sdf_segment(rx, ry, 29.6, 47.4, 36.5, 28.0)) - 0.45
    shaft = sdf_segment(rx, ry, 9.0, 28.0, 39.0, 28.0) - 0.75
    tip = halfplanes(rx, ry, [(3.5, 28.0), (10.5, 24.4), (10.5, 31.6)])
    fletch = np.minimum(halfplanes(rx, ry, [(36.0, 28.0), (41.5, 23.6), (43.0, 23.6), (39.0, 28.0)]),
                        halfplanes(rx, ry, [(36.0, 28.0), (39.0, 28.0), (43.0, 32.4), (41.5, 32.4)]))
    d = np.minimum.reduce([bow, string, shaft, tip, fletch])
    save('kit_emb_bow', relief(d, n), out)
    # Cavalry: a horse head in profile, facing left, with an arched neck and a mane.
    head = sdf_ucap(x, y, 27.5, 17.5, 6.6, 12.0, 33.5, 4.6)
    cheek = sdf_circle(x, y, 27.5, 23.5, 7.4)
    neck = sdf_ucap(x, y, 31.5, 20.0, 7.0, 39.5, 47.0, 10.5)
    ex, ey = rot(x, y, 30.0, 10.5, -18)
    ear = sdf_rhombus(ex, ey, 30.0, 10.5, 2.4, 5.4)
    # mane: a saw edge along the back of the neck
    mx0, my0, mx1, my1 = 33.0, 12.0, 47.5, 41.0
    mdx, mdy = mx1 - mx0, my1 - my0
    ml = math.hypot(mdx, mdy)
    tpar = np.clip(((x - mx0) * mdx + (y - my0) * mdy) / (ml * ml), 0, 1)
    saw = np.mod(tpar * 7.0, 1.0)
    mane = sdf_segment(x, y, mx0, my0, mx1, my1) - (1.4 + 2.6 * saw)
    d = np.minimum.reduce([head, cheek, neck, ear, mane])
    d = np.maximum(d, y - 50.5)
    grooves = np.exp(-((x - 24.0) ** 2 + (y - 19.5) ** 2) / 1.6)          # eye
    grooves += np.exp(-((x - 13.2) ** 2 + (y - 31.0) ** 2) / 1.0) * 0.8   # nostril
    grooves += np.exp(-(sdf_segment(x, y, 15.0, 34.5, 22.0, 31.0) / 0.45) ** 2) * 0.6  # mouth
    grooves += np.exp(-(np.abs(sdf_circle(x, y, 27.5, 23.5, 7.4)) / 0.5) ** 2) * coverage(head) * 0.5  # jaw line
    grooves += np.exp(-(np.abs(mane + 1.2) / 0.45) ** 2) * coverage(neck) * 0.6
    save('kit_emb_horse', relief(d, n, grooves=np.clip(grooves, 0, 1)), out)
    # Siege: a battering ram under its roof, on two wheels.
    roof = halfplanes(x, y, [(28.0, 8.0), (50.0, 24.5), (6.0, 24.5)])
    roof = np.maximum(roof, -halfplanes(x, y, [(28.0, 13.0), (42.5, 23.6), (13.5, 23.6)]) - 0.0)
    posts = np.minimum(sdf_segment(x, y, 13.0, 24.0, 13.0, 39.0), sdf_segment(x, y, 43.0, 24.0, 43.0, 39.0)) - 1.3
    log = sdf_segment(x, y, 8.0, 32.0, 48.0, 32.0) - 3.4
    head_r = sdf_circle(x, y, 6.5, 32.0, 4.8)
    beam = sdf_segment(x, y, 10.0, 39.5, 47.0, 39.5) - 1.3
    wheels = np.minimum(sdf_circle(x, y, 16.0, 44.0, 6.2), sdf_circle(x, y, 40.0, 44.0, 6.2))
    d = np.minimum.reduce([roof, posts, log, head_r, beam, wheels])
    grooves = ring_groove(x, y, 16.0, 44.0, 3.6, 0.45) + ring_groove(x, y, 40.0, 44.0, 3.6, 0.45)
    grooves += (np.exp(-((x - 16.0) ** 2 + (y - 44.0) ** 2) / 1.2) + np.exp(-((x - 40.0) ** 2 + (y - 44.0) ** 2) / 1.2)) * 0.8
    grooves += np.exp(-(np.abs(log) / 0.5) ** 2) * coverage(wheels) * 0.7
    for gx in (20.0, 27.0, 34.0):
        grooves += np.exp(-((x - gx) / 0.45) ** 2) * coverage(log) * 0.45
    save('kit_emb_ram', relief(d, n, grooves=np.clip(grooves, 0, 1)), out)


def stat_icons(out):
    """Small forged icons for figures and chips (24 units): attack, defence, health, power,
    wall damage, army places, batch."""
    n = 24
    W = H = n * S
    x, y = grid(W, H)
    def put(name, d, grooves=None, tone='bronze'):
        save(name, relief(d, n, tone=tone, bevel=0.9, outline=0.75, grooves=grooves, shadow=0.35), out)
    # sword, point up-right
    rx, ry = rot(x, y, 12, 12, -45)
    blade = halfplanes(rx, ry, [(12.0, 1.0), (13.7, 4.0), (13.7, 15.0), (10.3, 15.0), (10.3, 4.0)])
    guard = sdf_segment(rx, ry, 7.0, 15.8, 17.0, 15.8) - 1.05
    grip = sdf_segment(rx, ry, 12.0, 16.5, 12.0, 20.5) - 0.95
    pommel = sdf_circle(rx, ry, 12.0, 21.6, 1.5)
    grooves = np.exp(-((rx - 12.0) / 0.4) ** 2) * coverage(blade) * 0.5
    put('kit_ic_attack', np.minimum.reduce([blade, guard, grip, pommel]), grooves)
    # heater shield with a cross
    top = sdf_round(x, y, 12.0, 8.0, 8.2, 5.5, 1.6)
    point = np.maximum(sdf_circle(x, y, 18.0, 9.0, 12.8), sdf_circle(x, y, 6.0, 9.0, 12.8))
    shield = np.maximum(np.minimum(top, np.maximum(point, -(y - 8.0))), -(y - 2.5))
    grooves = (np.exp(-((x - 12.0) / 0.5) ** 2) + np.exp(-((y - 9.5) / 0.5) ** 2)) * coverage(shield + 1.4) * 0.7
    put('kit_ic_defence', shield, np.clip(grooves, 0, 1))
    # heart
    hx = np.abs(x - 12.0)
    lobes = sdf_circle(hx, y, 4.6, 9.0, 4.9)
    tip = halfplanes(x, y, [(12.0, 21.0), (3.0, 10.6), (7.0, 6.8), (12.0, 10.0), (17.0, 6.8), (21.0, 10.6)][::-1])
    tip = np.maximum(halfplanes(x, y, [(2.2, 10.2), (21.8, 10.2), (12.0, 21.2)]), -100)
    put('kit_ic_health', np.minimum(lobes, tip), tone='gold')
    # eight-pointed star (two squares)
    box = np.maximum(np.abs(x - 12.0), np.abs(y - 12.0)) - 6.6
    qx, qy = rot(x, y, 12, 12, 45)
    box2 = np.maximum(np.abs(qx - 12.0), np.abs(qy - 12.0)) - 6.6
    star = np.minimum(box, box2)
    grooves = ring_groove(x, y, 12.0, 12.0, 3.3, 0.45)
    put('kit_ic_power', star, grooves, tone='gold')
    # wall with battlements and a crack
    wall = np.maximum(np.abs(x - 12.0) - 8.5, np.abs(y - 15.5) - 6.0)
    for mx in (5.0, 12.0, 19.0):
        wall = np.minimum(wall, np.maximum(np.abs(x - mx) - 2.0, np.abs(y - 7.5) - 2.6))
    crack = np.minimum(sdf_segment(x, y, 13.0, 10.5, 10.5, 15.0), sdf_segment(x, y, 10.5, 15.0, 14.0, 21.0))
    grooves = np.exp(-(crack / 0.55) ** 2) + np.exp(-((y - 15.5) / 0.4) ** 2) * 0.35
    put('kit_ic_wall', wall, np.clip(grooves, 0, 1))
    # banner on a pole (army places)
    pole = sdf_segment(x, y, 6.0, 2.5, 6.0, 22.0) - 1.0
    flag = np.maximum(halfplanes(x, y, [(6.5, 3.5), (20.5, 4.5), (20.5, 14.5), (6.5, 14.0)]),
                      -halfplanes(x, y, [(21.5, 5.0), (21.5, 14.0), (15.0, 9.5)]))
    knob = sdf_circle(x, y, 6.0, 2.2, 1.6)
    grooves = np.exp(-(sdf_segment(x, y, 9.0, 7.0, 13.5, 9.2) / 0.45) ** 2) * 0.6
    put('kit_ic_places', np.minimum.reduce([pole, flag, knob]), grooves)
    # batch: three spears
    parts = []
    for sx in (6.0, 12.0, 18.0):
        parts.append(sdf_segment(x, y, sx, 9.0, sx, 22.0) - 0.9)
        parts.append(sdf_rhombus(x, y, sx, 5.6, 2.1, 4.2))
    put('kit_ic_batch', np.minimum.reduce(parts))


def ink(out):
    """Painterly watercolour splash behind the recruitment hero (white, alpha; tinted at
    runtime by the tier). A tall ragged blot whose edge is hard and pooled in places and
    soft in others, a dense core low behind the figure that washes out upward, a few
    blooms, dry-brush strokes swept out of it, granulation and splatter. 1 texel per unit
    (soft by nature). RGB carries the value (pooled edges are darker), alpha the density."""
    n = 512
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    u, v = (x - n / 2) / (n / 2), (y - n / 2) / (n / 2)
    warp_x = fbm(n, n, 2, 4, 411, 0.55) - 0.5
    warp_y = fbm(n, n, 2, 4, 412, 0.55) - 0.5
    uu, vv = u + warp_x * 0.5, v + warp_y * 0.38
    r = np.sqrt((uu / 0.74) ** 2 + (vv / 0.9) ** 2)
    ragged = (fbm(n, n, 10, 3, 413, 0.6) - 0.5) * 0.14
    field_v = r + ragged
    # edge character varies round the blot: hard and pooled here, soft and bleeding there
    hard = smooth(0.35, 0.65, fbm(n, n, 3, 2, 414, 0.5))
    soft_w = 0.03 + 0.2 * (1.0 - hard)
    body = 1.0 - smooth(0.86 - soft_w, 0.86, field_v)
    pool = np.exp(-((field_v - 0.84) / 0.035) ** 2) * hard * body
    # dense core low behind the figure, washing out toward the top
    core = np.exp(-((u * 1.1) ** 2 + ((v - 0.18) * 0.9) ** 2) / 0.32)
    wash = 0.42 + 0.45 * core + 0.13 * smooth(-0.2, 0.9, v)
    bloom = fbm(n, n, 4, 4, 415, 0.55)
    bloom_edges = np.exp(-((bloom - 0.55) / 0.02) ** 2) * smooth(0.3, 0.7, 1.0 - core)
    density = body * (wash * (0.85 + 0.3 * (bloom - 0.5))) + pool * 0.5 + bloom_edges * body * 0.18
    # dry-brush strokes swept out of the blot (lower right and upper left)
    strokes = np.zeros((n, n), np.float32)
    rng = np.random.default_rng(416)
    for angle, cx, cy, length, width in ((-28, 0.42, 0.62, 0.9, 0.07), (-22, 0.32, 0.74, 0.7, 0.05), (152, -0.5, -0.42, 0.6, 0.05),
                                         (-35, 0.55, 0.38, 0.55, 0.04), (160, -0.6, -0.2, 0.45, 0.035), (-10, -0.15, 0.86, 0.8, 0.05)):
        a = math.radians(angle)
        du, dv = math.cos(a), math.sin(a)
        along = (u - cx) * du + (v - cy) * dv
        across = -(u - cx) * dv + (v - cy) * du
        # bristles: streaks along the stroke (noise across it), broken where the brush ran dry
        seed = int(rng.integers(1000))
        lanes = np.random.default_rng(seed).random(400).astype(np.float32)
        lane = np.interp((across / width + 1.0) * 100.0, np.arange(400, dtype=np.float32), lanes)
        dry = fbm(n, n, 3, 3, seed + 1, 0.55)
        taper = np.clip(1.0 - np.abs(along) / length, 0, 1) ** 0.6
        profile = 1.0 - smooth(0.5, 1.0, np.abs(across) / (width * (0.35 + 0.65 * taper) + 1e-4))
        ink_left = smooth(0.25, 0.55, lane * 0.6 + dry * 0.7 - (1.0 - taper) * 0.5)
        strokes = np.maximum(strokes, profile * ink_left * taper * 0.85)
    density = np.maximum(density, strokes * (1.0 - body * 0.6))
    # splatter
    for _ in range(110):
        ang = rng.random() * math.tau
        dist = 0.86 + rng.random() ** 1.5 * 0.32
        cx = n / 2 + math.cos(ang) * dist * n / 2 * 0.74
        cy = n / 2 + math.sin(ang) * dist * n / 2 * 0.9
        rad = 0.7 + rng.random() ** 3 * 5.5
        if cx < 6 or cy < 6 or cx > n - 6 or cy > n - 6:
            continue
        dot = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) - rad
        density = np.maximum(density, np.clip(0.5 - dot, 0, 1) * (0.5 + 0.45 * rng.random()))
    grain = np.random.default_rng(417).random((n, n)).astype(np.float32)
    grain = np.asarray(Image.fromarray((grain * 255).astype(np.uint8), 'L').resize((n // 2, n // 2), Image.BILINEAR).resize((n, n), Image.BICUBIC), np.float32) / 255.0
    density = density * (0.86 + 0.24 * grain)
    edge_fade = smooth(0.0, 0.05, np.minimum.reduce([x, y, n - 1 - x, n - 1 - y]) / n)
    alpha = np.clip(density, 0, 1) * edge_fade
    value = np.clip(1.0 - 0.45 * pool - 0.15 * bloom_edges - 0.18 * core * body, 0.4, 1.0)
    a = np.zeros((n, n, 4), np.float32)
    a[..., 0] = value
    a[..., 1] = value
    a[..., 2] = value
    a[..., 3] = alpha
    Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGBA').save(os.path.join(out, 'kit_ink.png'), optimize=True)


def solar(out):
    """Carved solar medallion behind the hero: a double ring with a band of notched
    triangles (three-sided notch carving), an inner ring of lozenges and the six-petal
    rosette drawn with compass arcs, the oldest carved sign of Russian wooden houses.
    Relief in grey (lit from the upper left), alpha = carved area; tinted at runtime."""
    w = h = 160
    W, H = w * S, h * S
    x, y = grid(W, H)
    c = w / 2
    r = np.sqrt((x - c) ** 2 + (y - c) ** 2)
    ang = np.arctan2(y - c, x - c)
    lines = np.zeros((H, W), np.float32)
    for rad in (78.0, 74.5, 61.0, 57.5):
        lines = np.maximum(lines, np.exp(-((r - rad) / 0.7) ** 2))
    # notched triangles between 61 and 74.5
    k = 28
    local = np.mod(ang * k / math.tau, 1.0) - 0.5
    tri_h = (r - 61.5) / 12.5
    tri = coverage((np.abs(local) * 2.0 - (1.0 - tri_h)) * 4.0) * (tri_h > 0) * (tri_h < 1)
    # lozenges between 48 and 57
    k2 = 16
    local2 = (np.mod(ang * k2 / math.tau, 1.0) - 0.5) * (math.tau * 52.5 / k2)
    loz = np.abs(local2) / 6.0 + np.abs(r - 52.5) / 3.6 - 1.0
    loz_m = coverage(loz * 3.0)
    # rosette: six arcs of radius R centred on a circle of radius R
    R = 40.0
    ros = np.zeros((H, W), np.float32)
    for i in range(6):
        a0 = math.tau * i / 6.0
        px, py = c + R * math.cos(a0), c + R * math.sin(a0)
        dd = np.abs(np.sqrt((x - px) ** 2 + (y - py) ** 2) - R)
        ros = np.maximum(ros, np.exp(-(dd / 0.75) ** 2) * (r < R + 0.5))
    ros = np.maximum(ros, np.exp(-((r - R) / 0.75) ** 2))
    hub = np.exp(-((r - 4.0) / 0.7) ** 2)
    cut = np.clip(np.maximum.reduce([lines, tri * 0.85, loz_m * 0.8, ros, hub]), 0, 1)
    height = -cut
    lit = light(height, 1.4)
    value = np.clip(0.62 + 0.5 * (lit - 0.62), 0, 1)
    a = canvas(w, h)
    a[..., 0] = value
    a[..., 1] = value
    a[..., 2] = value
    a[..., 3] = np.clip(cut * 0.9 + 0.08 * (r < 78.5), 0, 1) * (r < 79.0)
    save('kit_solar', a, out)


def beam(out):
    """Warm light falling on the hero from the upper left: a soft cone with dust. White,
    alpha; tinted warm and drawn rotated at runtime. 1 texel per unit."""
    w, h = 96, 320
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    t = y / h
    half = 10.0 + 34.0 * t
    across = np.abs(x - w / 2) / half
    alpha = (1.0 - smooth(0.35, 1.0, across)) * (1.0 - smooth(0.55, 1.0, t)) * smooth(0.0, 0.12, t)
    dust = fbm(w, h, 6, 3, 501, 0.6)
    alpha = alpha * (0.75 + 0.4 * dust)
    a = np.zeros((h, w, 4), np.float32)
    a[..., :3] = 1.0
    a[..., 3] = np.clip(alpha, 0, 1)
    Image.fromarray((a * 255 + 0.5).astype(np.uint8), 'RGBA').save(os.path.join(out, 'kit_beam.png'), optimize=True)


def dais_top(out):
    """End grain of the oak plinth: growth rings round a darker heart, drying cracks,
    a strip of bark at the rim and moss creeping in from it. Opaque surface texture."""
    w = h = 128
    W, H = w * S, h * S
    x, y = grid(W, H)
    c = w / 2
    dx, dy = x - c, y - c
    r = np.sqrt(dx * dx + dy * dy) / (w / 2 - 1.0)
    ang = np.arctan2(dy, dx)
    warp = (fbm(W, H, 3, 3, 601, 0.55) - 0.5) * 0.05
    rr = r + warp
    rings = np.sin(rr * math.tau * 13.0 + (fbm(W, H, 8, 2, 607) - 0.5) * 2.0) * 0.5 + 0.5
    rings = rings ** 4
    base = ramp(np.clip(0.55 + 0.25 * (fbm(W, H, 4, 3, 602) - 0.5) + 0.12 * rr, 0, 1),
                [(0.0, '#4a3220'), (0.5, '#7a5a3a'), (1.0, '#a07a52')])
    rgb = base * (1.0 - 0.14 * rings)[..., None]
    rgb = rgb * (0.82 + 0.18 * smooth(0.0, 0.25, r))[..., None]
    cracks = np.zeros((H, W), np.float32)
    rng = np.random.default_rng(603)
    for _ in range(5):
        a0 = rng.random() * math.tau
        span = 0.25 + rng.random() * 0.45
        da = np.angle(np.exp(1j * (ang - a0 - 0.12 * np.sin(rr * 9.0))))
        width = 0.012 * (1.0 - np.clip(rr / span, 0, 1))
        cracks = np.maximum(cracks, smooth(0.0, 1.0, 1.0 - np.abs(da) / np.maximum(width, 1e-4) * 0.5) * (rr < span) * (rr > 0.06))
    rgb = rgb * (1.0 - 0.6 * cracks)[..., None]
    bark = smooth(0.94, 0.965, r)
    bark_rgb = ramp(fbm(W, H, 18, 2, 604), [(0.0, '#1f150d'), (1.0, '#4b3726')])
    rgb = rgb * (1 - bark[..., None]) + bark_rgb * bark[..., None]
    moss_n = fbm(W, H, 6, 4, 605, 0.6)
    moss = smooth(0.78, 0.97, r + (moss_n - 0.5) * 0.35) * smooth(0.52, 0.66, moss_n)
    moss_rgb = ramp(fbm(W, H, 20, 2, 606), [(0.0, '#3e4a1f'), (0.6, '#62732c'), (1.0, '#8a9a45')])
    rgb = rgb * (1 - moss[..., None] * 0.9) + moss_rgb * (moss[..., None] * 0.9)
    a = canvas(w, h)
    a[..., :3] = rgb
    a[..., 3] = 1.0
    save('kit_dais_top', a, out)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'kit_png'
    os.makedirs(out, exist_ok=True)
    body_tile(out)
    body_dark(out)
    hourglass(out)
    header_band(out)
    header_band(out, 'kit_header_tall', 80.0, 31.0)
    dais(out)
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
    emblems(out)
    stat_icons(out)
    ink(out)
    solar(out)
    beam(out)
    dais_top(out)
    total = sum(os.path.getsize(os.path.join(out, f)) for f in os.listdir(out))
    print('painted', len(os.listdir(out)), 'textures,', total // 1024, 'KiB of PNG in', out)


if __name__ == '__main__':
    main()
