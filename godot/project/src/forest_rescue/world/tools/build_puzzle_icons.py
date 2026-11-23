#!/usr/bin/env python3
"""Build 1024: picture icons of the artifact puzzles («Лес потерянных»), one small atlas.

The owner could not read the old option pictures (thin engraved line glyphs on 24 px bronze discs).
Each of the 24 puzzle symbols (trail landmarks, rune-lock runes, winch steps, paired-latch parts) is
painted here procedurally as a bold, high-contrast, painterly picture on a light parchment medallion
(dark ring), so it reads at ~100-120 px on a phone and on the dark panel and the bronze widget discs
alike: silhouettes with a dark outline, a light-from-top-left gradient, short brush strokes for
texture and a soft drop shadow. No web images, no external art.

Output: godot/project/assets/forest_rescue/ui/lf_puzzle_icons.png — 6 x 4 cells of 128 px
(768 x 512, RGBA). The cell order is ORDER below; mechanism_ui.gd (ICON_ORDER) must match it.
Run: python3 build_puzzle_icons.py [--preview /abs/preview.png]"""
import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, '../../../../assets/forest_rescue/ui/lf_puzzle_icons.png'))
ORDER = [
    'split_birch', 'white_moss', 'fallen_trunk', 'resin_pine', 'double_stump', 'resin_bowl',
    'bent_fern', 'flat_slab', 'three_notches', 'mountain', 'river', 'leaf',
    'coal', 'seed', 'tree', 'sun', 'stone', 'root',
    'brake', 'pawl', 'raise', 'left_plate', 'right_plate', 'center_latch',
]
CELL = 128
COLUMNS = 6
SS = 4                      # supersampling
S = CELL * SS               # 512: drawing canvas of one icon
INK = (42, 26, 12, 255)     # outline


def rgb(hex_value, alpha=255):
    hex_value = hex_value.lstrip('#')
    return tuple(int(hex_value[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(4))


class Icon:
    """One supersampled icon canvas; parts are painted bottom to top."""

    def __init__(self, seed):
        self.img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
        self.rng = random.Random(seed)
        self.shadow = Image.new('L', (S, S), 0)

    @staticmethod
    def mask():
        m = Image.new('L', (S, S), 0)
        return m, ImageDraw.Draw(m)

    def paint(self, m, base, light=None, dark=None, outline=10, strokes=40, stroke_len=34, shadow=True, angle=-0.7):
        """Fill mask m: outline under it, top-left lit gradient, brush strokes clipped to it."""
        light = light or mix(base, (255, 255, 255, 255), 0.35)
        dark = dark or mix(base, (0, 0, 0, 255), 0.35)
        if shadow:
            self.shadow = ImageChops.lighter(self.shadow, m)
        if outline > 0:
            ring = m.filter(ImageFilter.MaxFilter(outline * 2 + 1))
            self.img.alpha_composite(Image.composite(Image.new('RGBA', (S, S), INK), Image.new('RGBA', (S, S), (0, 0, 0, 0)), ring))
        box = m.getbbox()
        if box is None:
            return
        x0, y0, x1, y1 = box
        grad = Image.new('RGBA', (S, S), base)
        gd = ImageDraw.Draw(grad)
        steps = 24
        for i in range(steps):
            t = i / (steps - 1)
            col = mix(light, dark, t)
            # bands perpendicular to the light direction (top-left → bottom-right)
            off = (t - 0.5) * 2.0
            cx = (x0 + x1) / 2 + off * (x1 - x0) * 0.5
            cy = (y0 + y1) / 2 + off * (y1 - y0) * 0.5
            r = max(x1 - x0, y1 - y0)
            gd.polygon([(cx - r, cy + r), (cx + r, cy - r), (cx + r * 3, cy + r), (cx + r, cy + r * 3)], fill=col)
        sd = ImageDraw.Draw(grad)
        for _ in range(strokes):
            px = self.rng.uniform(x0, x1)
            py = self.rng.uniform(y0, y1)
            a = angle + self.rng.uniform(-0.35, 0.35)
            ln = stroke_len * self.rng.uniform(0.6, 1.3)
            col = mix(light if self.rng.random() < 0.5 else dark, base, self.rng.uniform(0.2, 0.6))
            sd.line([(px, py), (px + math.cos(a) * ln, py + math.sin(a) * ln)], fill=col, width=int(self.rng.uniform(5, 10)))
        grad = grad.filter(ImageFilter.GaussianBlur(1.5))
        self.img.alpha_composite(Image.composite(grad, Image.new('RGBA', (S, S), (0, 0, 0, 0)), m))

    def flat(self, m, color, blur=0.0):
        if blur > 0:
            m = m.filter(ImageFilter.GaussianBlur(blur))
        self.img.alpha_composite(Image.composite(Image.new('RGBA', (S, S), color), Image.new('RGBA', (S, S), (0, 0, 0, 0)), m))

    def line(self, points, color, width, outline=True):
        if outline:
            m, d = self.mask()
            d.line(points, fill=255, width=width + 16, joint='curve')
            for p in (points[0], points[-1]):
                d.ellipse([p[0] - (width + 16) / 2, p[1] - (width + 16) / 2, p[0] + (width + 16) / 2, p[1] + (width + 16) / 2], fill=255)
            self.flat(m, INK)
        m, d = self.mask()
        d.line(points, fill=255, width=width, joint='curve')
        for p in (points[0], points[-1]):
            d.ellipse([p[0] - width / 2, p[1] - width / 2, p[0] + width / 2, p[1] + width / 2], fill=255)
        self.flat(m, color)

    def result(self):
        return self.img


def medallion():
    """Light parchment disc with a dark ring and a thin gold inner ring."""
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = 6
    d.ellipse([pad, pad, S - pad, S - pad], fill=rgb('#2a1a0c'))
    inner = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(inner)
    for i in range(40):
        t = i / 39
        r = (S / 2 - 26) * (1.0 - t)
        col = mix(rgb('#c99f62'), rgb('#f6ead0'), t ** 0.8)
        gd.ellipse([S / 2 - r - 18 * (1 - t), S / 2 - r - 22 * (1 - t), S / 2 + r - 18 * (1 - t), S / 2 + r - 22 * (1 - t)], fill=col)
    m = Image.new('L', (S, S), 0)
    ImageDraw.Draw(m).ellipse([26, 26, S - 26, S - 26], fill=255)
    img.alpha_composite(Image.composite(inner, Image.new('RGBA', (S, S), (0, 0, 0, 0)), m))
    d.ellipse([30, 30, S - 30, S - 30], outline=rgb('#b8894a'), width=6)
    return img


def finish(icon):
    """Medallion + soft drop shadow of the drawing + the drawing, downsampled to one cell."""
    base = medallion()
    shadow = icon.shadow.filter(ImageFilter.GaussianBlur(10))
    shadow = ImageChops.offset(shadow, 10, 14)
    disc = Image.new('L', (S, S), 0)
    ImageDraw.Draw(disc).ellipse([26, 26, S - 26, S - 26], fill=255)
    shadow = ImageChops.multiply(shadow, disc).point(lambda v: int(v * 0.45))
    base.alpha_composite(Image.composite(Image.new('RGBA', (S, S), (60, 38, 16, 255)), Image.new('RGBA', (S, S), (0, 0, 0, 0)), shadow))
    base.alpha_composite(icon.result())
    return base.resize((CELL, CELL), Image.LANCZOS)


# ------------------------------------------------------------------ the 24 pictures
def ground(icon, y=392, color='#6f8f3a'):
    m, d = icon.mask()
    d.ellipse([86, y - 30, 426, y + 46], fill=255)
    icon.paint(m, rgb(color), outline=8, strokes=30, shadow=False)


def split_birch(icon):
    ground(icon, 400)
    # two halves of a birch trunk split down the middle, the pale heartwood showing
    for side in (-1, 1):
        m, d = icon.mask()
        d.polygon([(256 + side * 8, 410), (256 + side * 62, 410), (256 + side * 112, 112), (256 + side * 60, 96), (256 + side * 18, 250)], fill=255)
        icon.paint(m, rgb('#f2efe6'), light=rgb('#ffffff'), dark=rgb('#c9c3b4'), strokes=10)
        for k in range(5):
            y = 150 + k * 52 + icon.rng.uniform(-8, 8)
            x = 256 + side * (30 + (y - 150) * -0.05 + 40 * (410 - y) / 300)
            icon.line([(x - 22, y), (x + 18, y + 6)], rgb('#1c1712'), 12, outline=False)
    m, d = icon.mask()
    d.polygon([(256, 405), (236, 250), (256, 150), (276, 250)], fill=255)
    icon.paint(m, rgb('#e3b25c'), light=rgb('#ffd98a'), dark=rgb('#a7742c'), outline=0, strokes=8)
    icon.line([(256, 400), (250, 300), (262, 220), (256, 160)], rgb('#3a2412'), 9, outline=False)
    for (x, y) in ((130, 120), (390, 116), (350, 84), (166, 86)):
        m, d = icon.mask()
        d.ellipse([x - 30, y - 18, x + 30, y + 18], fill=255)
        icon.paint(m, rgb('#7fbf3a'), outline=6, strokes=4, shadow=False)


def boulder(icon, cx=256, cy=300, w=180, h=120, color='#8c8a84'):
    m, d = icon.mask()
    d.polygon([(cx - w, cy + h * 0.7), (cx - w * 0.85, cy - h * 0.3), (cx - w * 0.35, cy - h), (cx + w * 0.4, cy - h * 0.95),
               (cx + w * 0.95, cy - h * 0.2), (cx + w, cy + h * 0.7)], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(14)).point(lambda v: 255 if v > 120 else 0)
    icon.paint(m, rgb(color), strokes=50)
    return m


def white_moss(icon):
    ground(icon, 410)
    boulder(icon, 256, 320, 190, 140, '#7b7a76')
    for (x, y, r) in ((160, 214, 46), (232, 186, 56), (316, 196, 50), (378, 240, 40), (120, 270, 34), (270, 240, 36)):
        m, d = icon.mask()
        for k in range(6):
            a = k / 6 * math.tau
            d.ellipse([x + math.cos(a) * r * 0.45 - r * 0.55, y + math.sin(a) * r * 0.3 - r * 0.5, x + math.cos(a) * r * 0.45 + r * 0.55, y + math.sin(a) * r * 0.3 + r * 0.5], fill=255)
        icon.paint(m, rgb('#fbfbf4'), light=rgb('#ffffff'), dark=rgb('#d6dccd'), outline=7, strokes=12, stroke_len=18, shadow=False)


def fallen_trunk(icon):
    ground(icon, 400)
    m, d = icon.mask()
    d.polygon([(70, 330), (110, 260), (400, 196), (430, 270)], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(10)).point(lambda v: 255 if v > 120 else 0)
    icon.paint(m, rgb('#7a4a24'), strokes=60, angle=-0.22)
    for k in range(4):
        x = 150 + k * 70
        icon.line([(x, 290 - k * 16), (x + 50, 282 - k * 16)], rgb('#4a2a12'), 8, outline=False)
    # broken branch stubs
    icon.line([(220, 250), (196, 170)], rgb('#6b3f1e'), 22)
    icon.line([(320, 230), (356, 150)], rgb('#6b3f1e'), 18)
    # cut end with rings
    m, d = icon.mask()
    d.ellipse([370, 186, 460, 286], fill=255)
    icon.paint(m, rgb('#e2b77a'), light=rgb('#f6d9a6'), dark=rgb('#b7834a'), strokes=0)
    for r in (34, 22, 11):
        ImageDraw.Draw(icon.img).ellipse([415 - r, 236 - r * 1.1, 415 + r, 236 + r * 1.1], outline=rgb('#8a5a2a'), width=6)


def resin_pine(icon):
    ground(icon, 420)
    icon.line([(256, 420), (256, 290)], rgb('#6b3f1e'), 44)
    for k, (y, w) in enumerate(((150, 92), (215, 128), (280, 162), (340, 190))):
        m, d = icon.mask()
        d.polygon([(256, y - 80), (256 - w, y + 40), (256 + w, y + 40)], fill=255)
        icon.paint(m, rgb('#2f6b34'), light=rgb('#4f9a4c'), dark=rgb('#1c4422'), strokes=30, outline=8)
    # bright amber drops running down the trunk
    for (x, y) in ((246, 386), (268, 404), (238, 414)):
        m, d = icon.mask()
        d.ellipse([x - 13, y - 10, x + 13, y + 18], fill=255)
        d.polygon([(x - 8, y - 2), (x + 8, y - 2), (x, y - 26)], fill=255)
        icon.paint(m, rgb('#ffb21e'), light=rgb('#ffe58a'), dark=rgb('#d97a00'), outline=5, strokes=0, shadow=False)
    m, d = icon.mask()
    d.ellipse([326, 330, 416, 426], fill=255)
    d.polygon([(334, 362), (408, 362), (371, 278)], fill=255)
    icon.paint(m, rgb('#ffb21e'), light=rgb('#ffe58a'), dark=rgb('#d97a00'), outline=8, strokes=0)
    ImageDraw.Draw(icon.img).ellipse([346, 350, 366, 374], fill=rgb('#fff6c8'))


def stump(icon, cx, top, w, h):
    m, d = icon.mask()
    d.rectangle([cx - w, top, cx + w, top + h], fill=255)
    d.ellipse([cx - w, top + h - w * 0.4, cx + w, top + h + w * 0.4], fill=255)
    d.polygon([(cx - w, top + h), (cx - w - 24, top + h + 18), (cx - w + 10, top + h + 6)], fill=255)
    d.polygon([(cx + w, top + h), (cx + w + 24, top + h + 18), (cx + w - 10, top + h + 6)], fill=255)
    icon.paint(m, rgb('#6e4322'), strokes=30, angle=1.5)
    m, d = icon.mask()
    d.ellipse([cx - w, top - w * 0.42, cx + w, top + w * 0.42], fill=255)
    icon.paint(m, rgb('#e6bd7e'), light=rgb('#f8dcaa'), dark=rgb('#c08a4c'), strokes=0, outline=7, shadow=False)
    dr = ImageDraw.Draw(icon.img)
    for f in (0.7, 0.42, 0.16):
        dr.ellipse([cx - w * f, top - w * 0.42 * f, cx + w * f, top + w * 0.42 * f], outline=rgb('#93602e'), width=5)


def double_stump(icon):
    ground(icon, 400)
    stump(icon, 168, 220, 72, 150)
    stump(icon, 346, 270, 62, 110)


def resin_bowl(icon):
    ground(icon, 410, '#5f7d34')
    m, d = icon.mask()
    d.pieslice([96, 150, 416, 420], 0, 180, fill=255)
    icon.paint(m, rgb('#8a5428'), strokes=40, angle=0.1)
    m, d = icon.mask()
    d.ellipse([100, 236, 412, 334], fill=255)
    icon.paint(m, rgb('#ffae1a'), light=rgb('#ffe27a'), dark=rgb('#d56f00'), strokes=10, outline=8, shadow=False)
    dr = ImageDraw.Draw(icon.img)
    dr.ellipse([170, 254, 260, 282], fill=rgb('#fff3c0', 220))
    # a drip over the rim
    m, d = icon.mask()
    d.rectangle([336, 300, 356, 360], fill=255)
    d.ellipse([328, 344, 364, 384], fill=255)
    icon.paint(m, rgb('#ffae1a'), light=rgb('#ffe27a'), dark=rgb('#d56f00'), strokes=0, outline=6, shadow=False)


def bent_fern(icon):
    ground(icon, 420)
    pts = []
    for i in range(15):
        t = i / 14
        pts.append((110 + t * 310, 440 - t * 780 + t * t * 590))
    icon.line(pts, rgb('#3f7a2a'), 18)
    for i in range(1, 14):
        x, y = pts[i]
        tx, ty = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        ln = math.hypot(tx, ty)
        nx, ny = -ty / ln, tx / ln
        size = 74 * (1.0 - abs(i - 6) / 11) * (0.55 if i > 11 else 1.0)
        for side in (-1, 1):
            m, d = icon.mask()
            ex, ey = x + nx * side * size + tx / ln * 14, y + ny * side * size + ty / ln * 14
            d.polygon([(x, y), (ex - tx / ln * 10 + nx * side * -10, ey - ty / ln * 10), (ex, ey), (ex + tx / ln * 12, ey + ty / ln * 12)], fill=255)
            m = m.filter(ImageFilter.MaxFilter(9))
            icon.paint(m, rgb('#5fae38'), light=rgb('#8fd85a'), dark=rgb('#3a7a22'), outline=5, strokes=3, stroke_len=12, shadow=side < 0)


def flat_slab(icon):
    ground(icon, 380)
    m, d = icon.mask()
    d.polygon([(70, 300), (190, 230), (452, 250), (350, 330)], fill=255)
    icon.paint(m, rgb('#9a9890'), light=rgb('#c9c7bf'), dark=rgb('#7a776f'), strokes=40, angle=0.05)
    m, d = icon.mask()
    d.polygon([(70, 300), (350, 330), (350, 372), (70, 340)], fill=255)
    icon.paint(m, rgb('#6a675f'), strokes=20, outline=8, angle=0.05)
    m, d = icon.mask()
    d.polygon([(350, 330), (452, 250), (452, 290), (350, 372)], fill=255)
    icon.paint(m, rgb('#55524b'), strokes=10, outline=8)
    for (x, y) in ((150, 300), (300, 290)):
        icon.line([(x, y), (x + 40, y - 10), (x + 70, y + 4)], rgb('#5d5a53'), 6, outline=False)


def three_notches(icon):
    ground(icon, 420)
    m, d = icon.mask()
    d.rectangle([186, 70, 326, 420], fill=255)
    d.ellipse([186, 44, 326, 96], fill=255)
    icon.paint(m, rgb('#6e4322'), strokes=70, angle=1.5, stroke_len=50)
    for k in range(3):
        y = 150 + k * 82
        m, d = icon.mask()
        d.polygon([(180, y - 30), (300, y), (180, y + 30)], fill=255)
        icon.paint(m, rgb('#f6d49a'), light=rgb('#fff0cf'), dark=rgb('#d5a55e'), outline=7, strokes=0, shadow=False)
        icon.line([(184, y), (290, y)], rgb('#b07a3a'), 5, outline=False)


def mountain(icon):
    m, d = icon.mask()
    d.polygon([(60, 400), (196, 140), (262, 250), (330, 100), (456, 400)], fill=255)
    icon.paint(m, rgb('#6f7f99'), light=rgb('#9fb0c8'), dark=rgb('#47546a'), strokes=50, angle=1.0)
    m, d = icon.mask()
    d.polygon([(196, 140), (160, 210), (184, 200), (204, 222), (226, 196)], fill=255)
    d.polygon([(330, 100), (284, 186), (312, 172), (334, 196), (356, 168), (378, 186)], fill=255)
    icon.paint(m, rgb('#fbfdff'), light=rgb('#ffffff'), dark=rgb('#cfd9e6'), outline=6, strokes=4, shadow=False)
    m, d = icon.mask()
    d.ellipse([40, 360, 300, 450], fill=255)
    d.ellipse([220, 370, 480, 450], fill=255)
    icon.paint(m, rgb('#5c8a34'), outline=8, strokes=20, shadow=False)


def river(icon):
    m, d = icon.mask()
    d.ellipse([56, 80, 456, 440], fill=255)
    icon.paint(m, rgb('#6f9a3a'), outline=0, strokes=40, shadow=False)
    pts_a, pts_b = [], []
    for i in range(21):
        t = i / 20
        y = 70 + t * 380
        x = 256 + math.sin(t * math.tau * 1.1) * 110
        w = 56 + t * 30
        pts_a.append((x - w, y))
        pts_b.append((x + w, y))
    m, d = icon.mask()
    d.polygon(pts_a + pts_b[::-1], fill=255)
    disc = Image.new('L', (S, S), 0)
    ImageDraw.Draw(disc).ellipse([40, 40, S - 40, S - 40], fill=255)
    m = ImageChops.multiply(m, disc)
    icon.paint(m, rgb('#2f7fd0'), light=rgb('#7cc0ff'), dark=rgb('#1a4f94'), strokes=30, angle=1.3)
    for i in range(3, 19, 4):
        x, y = (pts_a[i][0] + pts_b[i][0]) / 2, pts_a[i][1]
        icon.line([(x - 30, y), (x - 6, y - 10), (x + 18, y), (x + 40, y - 8)], rgb('#e8f6ff'), 9, outline=False)


def leaf(icon):
    m, d = icon.mask()
    pts = []
    for i in range(41):
        t = i / 40
        a = t * math.pi
        pts.append((256 + math.sin(a) * 120 * (1.0 - 0.25 * t), 76 + t * 330))
    pts += [(512 - x, y) for (x, y) in pts[::-1]]
    d.polygon(pts, fill=255)
    m = m.rotate(-28, resample=Image.BICUBIC, center=(256, 256)).point(lambda v: 255 if v > 120 else 0)
    icon.paint(m, rgb('#4f9e2e'), light=rgb('#8fd456'), dark=rgb('#2f6a1a'), strokes=30)
    c, s = math.cos(math.radians(28)), math.sin(math.radians(28))

    def rot(x, y):
        x, y = x - 256, y - 256
        return 256 + x * c - y * s, 256 + x * s + y * c
    icon.line([rot(256, 90), rot(256, 470)], rgb('#24501a'), 10, outline=False)
    for k in range(5):
        y = 150 + k * 52
        for side in (-1, 1):
            icon.line([rot(256, y + 30), rot(256 + side * 80, y - 10)], rgb('#2f6a1a'), 6, outline=False)


def coal(icon):
    for (x, y, r) in ((190, 320, 90), (320, 330, 96), (256, 250, 92), (170, 380, 60), (350, 390, 64)):
        m, d = icon.mask()
        d.polygon([(x - r, y + r * 0.3), (x - r * 0.6, y - r * 0.7), (x + r * 0.3, y - r * 0.9), (x + r, y - r * 0.1), (x + r * 0.7, y + r * 0.7), (x - r * 0.5, y + r * 0.8)], fill=255)
        icon.paint(m, rgb('#2a2726'), light=rgb('#55504c'), dark=rgb('#121010'), strokes=12)
    dr = ImageDraw.Draw(icon.img)
    glow = Image.new('L', (S, S), 0)
    gd = ImageDraw.Draw(glow)
    cracks = [[(200, 270), (240, 300), (226, 340)], [(290, 290), (330, 310), (360, 300)], [(240, 220), (270, 250), (300, 240)],
              [(150, 360), (190, 370)], [(320, 380), (360, 370)]]
    for crack in cracks:
        gd.line(crack, fill=255, width=26)
    icon.flat(glow.filter(ImageFilter.GaussianBlur(10)), rgb('#ff6a1a', 200))
    for crack in cracks:
        dr.line(crack, fill=rgb('#ffd04a'), width=10)
    # rising embers / a small flame
    m, d = icon.mask()
    d.polygon([(256, 80), (300, 160), (284, 210), (256, 190), (228, 210), (212, 160)], fill=255)
    icon.paint(m, rgb('#ff8a1a'), light=rgb('#ffe066'), dark=rgb('#e2400e'), outline=6, strokes=0, shadow=False)
    for (x, y) in ((170, 150), (350, 130), (330, 196)):
        dr.ellipse([x - 9, y - 9, x + 9, y + 9], fill=rgb('#ffb43a'))


def seed(icon):
    ground(icon, 420, '#7a5a34')
    # sprouting seed: a big brown seed in the soil, a green shoot with two leaves
    m, d = icon.mask()
    d.ellipse([150, 260, 362, 420], fill=255)
    icon.paint(m, rgb('#9a6330'), light=rgb('#c98e52'), dark=rgb('#6a3e18'), strokes=30)
    icon.line([(206, 300), (300, 288)], rgb('#6a3e18'), 7, outline=False)
    icon.line([(256, 280), (250, 200), (262, 140)], rgb('#4f9a2e'), 18)
    for side in (-1, 1):
        m, d = icon.mask()
        d.ellipse([256 + side * 10 - (side < 0) * 130, 110, 256 + side * 10 + (side > 0) * 130, 180], fill=255)
        m = m.rotate(side * 18, resample=Image.BICUBIC, center=(256, 150)).point(lambda v: 255 if v > 120 else 0)
        icon.paint(m, rgb('#6cc23a'), light=rgb('#a6ea6e'), dark=rgb('#3c8a1e'), outline=7, strokes=6)


def tree(icon):
    ground(icon, 420)
    icon.line([(256, 420), (256, 250)], rgb('#6b3f1e'), 46)
    icon.line([(256, 320), (196, 260)], rgb('#6b3f1e'), 20)
    m, d = icon.mask()
    for (x, y, r) in ((256, 160, 100), (166, 220, 80), (346, 220, 80), (210, 140, 70), (306, 140, 70)):
        d.ellipse([x - r, y - r, x + r, y + r], fill=255)
    icon.paint(m, rgb('#3f8f34'), light=rgb('#7ccc4e'), dark=rgb('#22581e'), strokes=60, stroke_len=26)
    dr = ImageDraw.Draw(icon.img)
    for (x, y) in ((200, 130), (290, 110), (330, 190)):
        dr.ellipse([x - 22, y - 16, x + 22, y + 16], fill=rgb('#9ade66', 200))


def sun(icon):
    m, d = icon.mask()
    for k in range(12):
        a = k / 12 * math.tau
        w = 0.17
        d.polygon([(256 + math.cos(a - w) * 120, 256 + math.sin(a - w) * 120), (256 + math.cos(a) * 214, 256 + math.sin(a) * 214),
                   (256 + math.cos(a + w) * 120, 256 + math.sin(a + w) * 120)], fill=255)
    icon.paint(m, rgb('#ff9f1a'), light=rgb('#ffd04a'), dark=rgb('#e06a00'), strokes=0, outline=8)
    m, d = icon.mask()
    d.ellipse([136, 136, 376, 376], fill=255)
    icon.paint(m, rgb('#ffd02a'), light=rgb('#fff1a0'), dark=rgb('#f59a00'), strokes=20, outline=9)


def stone(icon):
    ground(icon, 400, '#6f8a3a')
    m = boulder(icon, 256, 300, 170, 150, '#8f8d88')
    icon.line([(230, 190), (262, 250), (240, 300)], rgb('#4d4b47'), 8, outline=False)
    dr = ImageDraw.Draw(icon.img)
    dr.ellipse([170, 196, 230, 230], fill=rgb('#d8d6d0', 170))


def root(icon):
    m, d = icon.mask()
    d.rectangle([60, 250, 452, 440], fill=255)
    disc = Image.new('L', (S, S), 0)
    ImageDraw.Draw(disc).ellipse([30, 30, S - 30, S - 30], fill=255)
    icon.paint(ImageChops.multiply(m, disc), rgb('#7a5430'), light=rgb('#9a6e44'), dark=rgb('#5a3a1e'), outline=0, strokes=40, shadow=False)
    m, d = icon.mask()
    d.rectangle([50, 230, 462, 262], fill=255)
    icon.paint(ImageChops.multiply(m, disc), rgb('#5f8f34'), outline=0, strokes=10, shadow=False)
    icon.line([(256, 80), (256, 260)], rgb('#6b3f1e'), 56)
    for pts in ([(256, 250), (200, 300), (130, 330), (96, 400)], [(256, 250), (250, 330), (232, 420)],
                [(256, 250), (320, 300), (390, 320), (420, 390)], [(230, 300), (170, 380)], [(300, 290), (330, 400)]):
        icon.line(pts, rgb('#c48a4c'), 22)


def wheel(icon, cx, cy, r, teeth=0, color='#8a8a86'):
    m, d = icon.mask()
    if teeth:
        for k in range(teeth):
            a = k / teeth * math.tau
            d.polygon([(cx + math.cos(a - 0.13) * r * 0.9, cy + math.sin(a - 0.13) * r * 0.9), (cx + math.cos(a - 0.05) * r * 1.22, cy + math.sin(a - 0.05) * r * 1.22),
                       (cx + math.cos(a + 0.12) * r * 1.22, cy + math.sin(a + 0.12) * r * 1.22), (cx + math.cos(a + 0.16) * r * 0.9, cy + math.sin(a + 0.16) * r * 0.9)], fill=255)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    icon.paint(m, rgb(color), strokes=30)
    dr = ImageDraw.Draw(icon.img)
    dr.ellipse([cx - r * 0.3, cy - r * 0.3, cx + r * 0.3, cy + r * 0.3], fill=rgb('#3a3632'))
    dr.ellipse([cx - r * 0.62, cy - r * 0.62, cx + r * 0.62, cy + r * 0.62], outline=rgb('#4a4640'), width=8)


def brake(icon):
    wheel(icon, 220, 300, 120, 0, '#8d6a42')
    dr = ImageDraw.Draw(icon.img)
    for k in range(6):
        a = k / 6 * math.tau
        dr.line([(220, 300), (220 + math.cos(a) * 100, 300 + math.sin(a) * 100)], fill=rgb('#5a3e22'), width=12)
    # the brake shoe pressed on the rim and its lever with a red grip
    m, d = icon.mask()
    d.polygon([(330, 210), (372, 236), (350, 380), (310, 378), (334, 300)], fill=255)
    icon.paint(m, rgb('#5a5a5a'), strokes=10)
    icon.line([(340, 400), (420, 110)], rgb('#6b3f1e'), 30)
    m, d = icon.mask()
    d.ellipse([382, 56, 462, 136], fill=255)
    icon.paint(m, rgb('#d8321e'), light=rgb('#ff7a5a'), dark=rgb('#8f1a0e'), outline=8, strokes=4)
    # a bold "press" arrow
    icon.line([(470, 230), (410, 230)], rgb('#d8321e'), 16)
    m, d = icon.mask()
    d.polygon([(386, 230), (420, 204), (420, 256)], fill=255)
    icon.paint(m, rgb('#d8321e'), outline=6, strokes=0)


def pawl(icon):
    wheel(icon, 230, 290, 128, 12, '#9a9a96')
    # the pawl (bronze pick) dropped into the ratchet teeth
    m, d = icon.mask()
    d.polygon([(420, 120), (448, 146), (348, 196), (316, 172)], fill=255)
    icon.paint(m, rgb('#c99a4a'), light=rgb('#f2cc7a'), dark=rgb('#8a6226'), strokes=8)
    dr = ImageDraw.Draw(icon.img)
    dr.ellipse([410, 106, 462, 158], fill=rgb('#3a2614'))
    dr.ellipse([422, 118, 450, 146], fill=rgb('#c99a4a'))
    # the spring
    icon.line([(440, 180), (420, 210), (450, 230), (424, 260)], rgb('#3a3632'), 8, outline=False)


def raise_(icon):
    # the chest coming up on its rope, a big green arrow up
    icon.line([(196, 60), (196, 270)], rgb('#d9bf86'), 10)
    m, d = icon.mask()
    d.rectangle([116, 270, 276, 400], fill=255)
    icon.paint(m, rgb('#8a5428'), strokes=30)
    m, d = icon.mask()
    d.pieslice([116, 220, 276, 320], 180, 360, fill=255)
    icon.paint(m, rgb('#9a6230'), strokes=10, shadow=False)
    dr = ImageDraw.Draw(icon.img)
    dr.rectangle([116, 300, 276, 316], fill=rgb('#c99a4a'))
    dr.rectangle([184, 300, 208, 340], fill=rgb('#e2b673'))
    m, d = icon.mask()
    d.polygon([(370, 70), (460, 200), (406, 200), (406, 420), (334, 420), (334, 200), (280, 200)], fill=255)
    icon.paint(m, rgb('#3fae2e'), light=rgb('#8ae25e'), dark=rgb('#24701a'), strokes=10, outline=10)


def plates(icon, active):
    for side in (-1, 1):
        cx = 256 + side * 120
        lit = (side < 0 and active == 'left') or (side > 0 and active == 'right')
        y = 330 if lit else 312
        m, d = icon.mask()
        d.polygon([(cx - 92, y), (cx - 60, y - 44), (cx + 92, y - 44), (cx + 60, y)], fill=255)
        icon.paint(m, rgb('#e0b04a') if lit else rgb('#8a877f'), strokes=16)
        m, d = icon.mask()
        d.polygon([(cx - 92, y), (cx + 60, y), (cx + 60, y + 30), (cx - 92, y + 30)], fill=255)
        icon.paint(m, rgb('#a0782a') if lit else rgb('#5f5c55'), strokes=6, shadow=False)
    if active in ('left', 'right'):
        side = -1 if active == 'left' else 1
        cx = 256 + side * 120
        # a boot standing on the plate, a big arrow pressing down
        m, d = icon.mask()
        d.rounded_rectangle([cx - 34, 226, cx + 6, 300], radius=10, fill=255)
        d.rounded_rectangle([cx - 40, 280, cx + 46, 312], radius=14, fill=255)
        icon.paint(m, rgb('#5a3418'), strokes=10)
        m, d = icon.mask()
        d.polygon([(cx - 14, 210), (cx - 70, 130), (cx - 36, 130), (cx - 36, 60), (cx + 8, 60), (cx + 8, 130), (cx + 42, 130)], fill=255)
        icon.paint(m, rgb('#ffcf3a'), light=rgb('#fff0a0'), dark=rgb('#e09a00'), outline=9, strokes=4)
        # the other plate dimmed
        o = 256 - side * 120
        ImageDraw.Draw(icon.img).polygon([(o - 92, 312), (o - 60, 268), (o + 92, 268), (o + 60, 312), (o + 60, 342), (o - 92, 342)], fill=(40, 30, 20, 70))


def left_plate(icon):
    plates(icon, 'left')


def right_plate(icon):
    plates(icon, 'right')


def center_latch(icon):
    plates(icon, '')
    m, d = icon.mask()
    d.rounded_rectangle([196, 120, 316, 330], radius=18, fill=255)
    icon.paint(m, rgb('#b8894a'), light=rgb('#e9c27e'), dark=rgb('#7a5624'), strokes=20)
    m, d = icon.mask()
    d.rounded_rectangle([166, 196, 346, 246], radius=12, fill=255)
    icon.paint(m, rgb('#f2c65a'), light=rgb('#fff0a0'), dark=rgb('#c48a20'), strokes=6, outline=8)
    dr = ImageDraw.Draw(icon.img)
    dr.ellipse([240, 140, 272, 172], fill=rgb('#2a1a0c'))
    dr.polygon([(248, 166), (264, 166), (270, 194), (242, 194)], fill=rgb('#2a1a0c'))
    for side in (-1, 1):
        icon.line([(256 + side * 116, 221), (256 + side * 160, 221)], rgb('#ffcf3a'), 14)
        m, d = icon.mask()
        d.polygon([(256 + side * 196, 221), (256 + side * 156, 194), (256 + side * 156, 248)], fill=255)
        icon.paint(m, rgb('#ffcf3a'), outline=6, strokes=0)


PAINTERS = {
    'split_birch': split_birch, 'white_moss': white_moss, 'fallen_trunk': fallen_trunk, 'resin_pine': resin_pine,
    'double_stump': double_stump, 'resin_bowl': resin_bowl, 'bent_fern': bent_fern, 'flat_slab': flat_slab,
    'three_notches': three_notches, 'mountain': mountain, 'river': river, 'leaf': leaf, 'coal': coal, 'seed': seed,
    'tree': tree, 'sun': sun, 'stone': stone, 'root': root, 'brake': brake, 'pawl': pawl, 'raise': raise_,
    'left_plate': left_plate, 'right_plate': right_plate, 'center_latch': center_latch,
}


def build():
    rows = (len(ORDER) + COLUMNS - 1) // COLUMNS
    atlas = Image.new('RGBA', (CELL * COLUMNS, CELL * rows), (0, 0, 0, 0))
    for index, symbol in enumerate(ORDER):
        icon = Icon(1024 + index)
        PAINTERS[symbol](icon)
        atlas.alpha_composite(finish(icon), ((index % COLUMNS) * CELL, (index // COLUMNS) * CELL))
    return atlas


def main():
    atlas = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    atlas.save(OUT, optimize=True)
    print('wrote', OUT, atlas.size)
    if '--preview' in sys.argv:
        path = sys.argv[sys.argv.index('--preview') + 1]
        bg = Image.new('RGBA', atlas.size, (28, 22, 16, 255))
        bg.alpha_composite(atlas)
        bg.convert('RGB').save(path)


if __name__ == '__main__':
    main()
