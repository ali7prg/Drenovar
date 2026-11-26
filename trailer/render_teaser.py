#!/usr/bin/env python3
"""DRENOVAR — 25s cinematic teaser, rendered procedurally from reference plates.

Video: 1920x1080 @ 30fps, 2.39:1 letterbox. Audio: procedural 48 kHz stereo.
Usage: python3 render.py <uploads_dir> <font.woff> <out.mp4> [--preview SECONDS...]
"""
import sys, os, math, subprocess
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy import signal

UP, FONT, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
PREVIEW = [float(x) for x in sys.argv[5:]] if len(sys.argv) > 4 and sys.argv[4] == "--preview" else None

W, H, FPS, DUR = 1920, 1080, 30, 25.0
BAND = 804                      # 2.39:1 active picture
BAR = (H - BAND) // 2
NF = int(DUR * FPS)
rng = np.random.default_rng(7)


def load(name):
    return np.asarray(Image.open(os.path.join(UP, name)).convert("RGB")).astype(np.float32) / 255.0

# ---------------------------------------------------------------- plates
GATE = load("819905a1-image.png")      # hand / latch / fang
CART = load("e90b9966-image.png")      # hiding behind cart
FOREST = load("36ead0f1-image.png")    # forest, cabin
SHEET = load("bb93b0cd-image.jpg")     # creature sheet

# Creature: crop the hero pose, key out the grey studio backdrop.
CX0, CY0 = 0, 70
BEAST = SHEET[CY0:560, CX0:705].copy()
r, g, b = BEAST[..., 0], BEAST[..., 1], BEAST[..., 2]
mx, mn = BEAST.max(-1), BEAST.min(-1)
lum = BEAST @ np.array([0.299, 0.587, 0.114], np.float32)
sat = (mx - mn) / (mx + 1e-4)
warm = r - b
bgm = (np.clip((lum - 0.47) / 0.08, 0, 1) * np.clip((0.13 - sat) / 0.05, 0, 1)
       * np.clip((warm - 0.015) / 0.02, 0, 1))
bgm = cv2.GaussianBlur(cv2.morphologyEx(bgm, cv2.MORPH_OPEN, np.ones((3, 3))), (0, 0), 1.5)
BEAST_A = 1.0 - bgm
GLOW = np.clip((b - r) * 6.0 - 0.15, 0, 1) * np.clip(lum * 2.0, 0, 1)   # blue fur accents
GLOW = cv2.GaussianBlur(GLOW, (0, 0), 1.2)

# ---------------------------------------------------------------- noise helpers
def smooth_noise(h, w, scale, seed):
    rr = np.random.default_rng(seed)
    small = rr.random((max(2, h // scale), max(2, w // scale))).astype(np.float32)
    n = cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)
    n = cv2.GaussianBlur(n, (0, 0), scale * 0.35)
    n -= n.min(); n /= n.max() + 1e-6
    return n

FOG_A = smooth_noise(BAND * 2, W * 2, 90, 1)
FOG_B = smooth_noise(BAND * 2, W * 2, 40, 2)
GRAIN = [rng.normal(0, 1, (BAND // 2, W // 2)).astype(np.float32) for _ in range(8)]

yy, xx = np.mgrid[0:BAND, 0:W].astype(np.float32)
VIG = 1.0 - 0.55 * np.clip(((xx / W - 0.5) ** 2 * 1.4 + (yy / BAND - 0.5) ** 2 * 2.2) * 2.2, 0, 1) ** 1.4
VIG = VIG[..., None]


def wobble(t, amp, seed):
    """Organic handheld drift (sum of incommensurate sines)."""
    s = seed * 1.37
    x = (math.sin(t * 1.3 + s) * 0.6 + math.sin(t * 2.9 + s * 2) * 0.3 + math.sin(t * 7.1 + s * 3) * 0.1)
    y = (math.sin(t * 1.1 + s * 5) * 0.6 + math.sin(t * 3.3 + s * 7) * 0.3 + math.sin(t * 6.3 + s) * 0.1)
    return x * amp, y * amp


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ease_io_cubic(x):
    x = min(max(x, 0.0), 1.0)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def lerp(a, b, u):
    return a + (b - a) * u


def view(src, cx, cy, zoom, rot=0.0):
    """Virtual camera: show src centred on (cx,cy) at zoom (1 = cover the band)."""
    h, w = src.shape[:2]
    s = max(W / w, BAND / h) * zoom
    # keep frame inside the plate
    hw, hh = W / (2 * s), BAND / (2 * s)
    cx = min(max(cx, hw), w - hw); cy = min(max(cy, hh), h - hh)
    M = cv2.getRotationMatrix2D((cx, cy), rot, s)
    M[0, 2] += W / 2 - cx; M[1, 2] += BAND / 2 - cy
    return cv2.warpAffine(src, M, (W, BAND), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT), M


def to_screen(M, x, y):
    return M[0, 0] * x + M[0, 1] * y + M[0, 2], M[1, 0] * x + M[1, 1] * y + M[1, 2]


def glow(img, x, y, radius, color, strength):
    d2 = ((xx - x) ** 2 + (yy - y) ** 2) / (radius * radius)
    g = np.exp(-d2 * 2.0) * strength
    img += g[..., None] * np.array(color, np.float32)

# ---------------------------------------------------------------- rain
class Rain:
    def __init__(self, n, speed, length, thick, bright, blur, angle, seed):
        rr = np.random.default_rng(seed)
        self.x = rr.uniform(-200, W + 200, n); self.y = rr.uniform(0, BAND, n)
        self.v = speed * rr.uniform(0.8, 1.2, n); self.L = length * rr.uniform(0.7, 1.3, n)
        self.b = bright * rr.uniform(0.5, 1.0, n)
        self.thick, self.blur, self.ang = thick, blur, angle

    def layer(self, t):
        lay = np.zeros((BAND, W), np.float32)
        y = (self.y + self.v * t) % (BAND + 300) - 150
        x = self.x + y * self.ang
        dx, dy = self.ang * self.L, self.L
        x0, y0 = x.astype(int), y.astype(int)
        x1, y1 = (x + dx).astype(int), (y + dy).astype(int)
        for i in range(len(x)):
            cv2.line(lay, (x0[i], y0[i]), (x1[i], y1[i]), float(self.b[i]), self.thick, cv2.LINE_AA)
        if self.blur:
            lay = cv2.GaussianBlur(lay, (0, 0), self.blur)
        return lay

RAIN = [Rain(1400, 1500, 26, 1, 0.22, 0, 0.12, 11),
        Rain(450, 2300, 60, 1, 0.35, 0.8, 0.13, 12),
        Rain(60, 3400, 170, 3, 0.45, 2.5, 0.15, 13)]


def rain_layer(t, amount):
    if amount <= 0:
        return 0
    return (RAIN[0].layer(t) + RAIN[1].layer(t) + RAIN[2].layer(t)) * amount

# ---------------------------------------------------------------- timeline
# Lightning strikes (seconds): used by both picture and sound.
STRIKES = [(1.15, 1.0), (5.6, 0.7), (14.9, 0.55), (17.9, 1.0), (19.25, 0.8), (20.55, 1.0), (21.32, 1.3)]


def lightning(t):
    v = 0.0
    for t0, a in STRIKES:
        d = t - t0
        if -0.01 < d < 0.9:
            # double flicker + decaying afterglow
            f = math.exp(-d * 9) + 0.6 * math.exp(-((d - 0.12) * 40) ** 2) + 0.35 * math.exp(-((d - 0.26) * 30) ** 2)
            v += a * f
    return v


def fog(t, amount, speed=(25, 6), tint=(0.55, 0.62, 0.72)):
    ox = int((t * speed[0]) % W); oy = int((t * speed[1]) % BAND)
    a = FOG_A[oy:oy + BAND, ox:ox + W]
    ox2 = int((t * speed[0] * 1.8 + 300) % W); oy2 = int((t * speed[1] * 0.5 + 100) % BAND)
    bb = FOG_B[oy2:oy2 + BAND, ox2:ox2 + W]
    f = np.clip((a * 0.7 + bb * 0.3) - 0.35, 0, 1) * amount
    return f[..., None] * np.array(tint, np.float32)


def grade(img, exposure=1.0, warm=1.0):
    img = img * exposure
    lum = (img @ np.array([0.299, 0.587, 0.114], np.float32))[..., None]
    img = lum + (img - lum) * 0.88                                     # slight desat
    sh = np.clip(1 - lum * 2.5, 0, 1)
    img = img + sh * np.array([-0.01, 0.006, 0.03], np.float32)         # teal shadows
    hi = np.clip(lum * 2 - 0.8, 0, 1)
    img = img + hi * np.array([0.04, 0.015, -0.03], np.float32) * warm  # warm highlights
    img = np.clip(img, 0, None)
    img = img / (1 + img * 0.25) * 1.25                                  # soft shoulder
    img = img ** 1.08
    return img


def finish(img, t, f):
    img = img * VIG
    # light chromatic aberration at the edges
    shift = 2
    img[..., 0] = np.roll(img[..., 0], shift, 1); img[..., 2] = np.roll(img[..., 2], -shift, 1)
    gr = cv2.resize(GRAIN[f % 8], (W, BAND), interpolation=cv2.INTER_LINEAR)[..., None]
    img = img + gr * 0.022 * (0.4 + (1 - np.clip(img, 0, 1)) * 0.6)
    return np.clip(img, 0, 1)

# ---------------------------------------------------------------- shots
def shot_cart(t, lt):          # 1.15 – 6.8
    u = ease_io_cubic(lt / 5.65)
    wx, wy = wobble(t, 6, 1)
    img, M = view(CART, lerp(1180, 960, u) + wx, lerp(450, 385, u) + wy, lerp(1.0, 1.22, u))
    img = img.copy()
    for (lx, ly, s) in [(205, 150, 1.0), (650, 195, 0.6), (410, 225, 0.4)]:
        sx, sy = to_screen(M, lx, ly)
        fl = 0.75 + 0.25 * math.sin(t * 23 + lx) * math.sin(t * 9.7 + ly) + 0.1 * math.sin(t * 41)
        glow(img, sx, sy, 140 * M[0, 0], (1.0, 0.62, 0.25), 0.22 * s * fl)
    img = grade(img, 0.95)
    img += fog(t, 0.22)
    return img, 1.0


def shot_gate(t, lt):          # 6.8 – 12.4  (5.6s)
    wx, wy = wobble(t, 4, 2)
    # 0–3.6 slow push on hand+latch, 3.6–4.0 whip to the fang, then hold
    if lt < 3.6:
        u = ease(lt / 3.6)
        cx, cy, z = lerp(820, 1040, u), lerp(470, 430, u), lerp(1.02, 1.2, u)
    else:
        u = ease_io_cubic((lt - 3.6) / 0.45)
        cx, cy, z = lerp(1040, 680, u), lerp(430, 235, u), lerp(1.2, 1.5, u)
        hold = max(0.0, lt - 4.05)
        z += hold * 0.05
    # motion blur during the whip
    if 3.55 < lt < 4.1:
        acc = None
        for k in range(6):
            lt2 = lt - k * 0.006
            u2 = ease_io_cubic((lt2 - 3.6) / 0.45)
            fr, M = view(GATE, lerp(1040, 680, u2) + wx, lerp(430, 215, u2) + wy, lerp(1.2, 1.55, u2))
            acc = fr if acc is None else acc + fr
        img = acc / 6
    else:
        img, M = view(GATE, cx + wx, cy + wy, z)
        img = img.copy()
    # lantern flicker
    for (lx, ly) in [(1035, 265), (765, 345)]:
        sx, sy = to_screen(M, lx, ly)
        fl = 0.8 + 0.2 * math.sin(t * 19 + lx) * math.sin(t * 7.3)
        glow(img, sx, sy, 110 * M[0, 0], (1.0, 0.6, 0.25), 0.16 * fl)
    # a fresh drop falls from the latch
    td = lt - 2.2
    if 0 < td < 0.6:
        sx, sy = to_screen(M, 1046, 588 + 0.5 * 2600 * td * td)
        rad = max(2, int(6 * M[0, 0]))
        cv2.ellipse(img, (int(sx), int(sy)), (rad, int(rad * 1.6)), 0, 0, 360, (0.85, 0.7, 0.45), -1, cv2.LINE_AA)
    # hot breath from the jaws once we see them
    if lt > 3.8:
        for k in range(3):
            ph = ((lt - 3.8) * 0.9 + k * 0.33) % 1.0
            bx, by = to_screen(M, 760 + ph * 160, 175 + ph * 25 - k * 10)
            glow(img, bx, by, (60 + ph * 140) * M[0, 0], (0.75, 0.8, 0.88), 0.10 * math.sin(ph * math.pi))
    img = grade(img, 1.0)
    img += fog(t, 0.08)
    return img, 1.0


def shot_forest(t, lt):        # 12.4 – 17.2
    u = ease_io_cubic(lt / 4.8)
    wx, wy = wobble(t, 5, 3)
    img, M = view(FOREST, lerp(820, 1080, u) + wx, lerp(440, 410, u) + wy, lerp(1.0, 1.16, u))
    img = img.copy()
    sx, sy = to_screen(M, 1531, 386)
    fl = 0.85 + 0.15 * math.sin(t * 11) * math.sin(t * 4.3 + 1)
    glow(img, sx, sy, 90 * M[0, 0], (1.0, 0.65, 0.3), 0.28 * fl)
    img = grade(img, 0.95)
    img += fog(t, 0.42, speed=(40, 3), tint=(0.5, 0.58, 0.7))
    return img, 1.0


def shot_beast(t, lt):         # 17.2 – 21.4
    # stormy backdrop behind the keyed creature
    gy = (yy / BAND)[..., None]
    back = np.array([0.03, 0.045, 0.07], np.float32) * (1.4 - gy) + fog(t, 0.25, speed=(60, 4), tint=(0.25, 0.3, 0.4))
    # build creature plate with backdrop composited
    pulse = 0.55 + 0.45 * math.sin(lt * 3.2) ** 2 + 0.6 * ease((lt - 2.5) / 1.5)
    beast = BEAST * (0.85 + 0.0 * pulse)
    beast = beast + (GLOW * pulse * 0.4)[..., None] * np.array([0.35, 0.65, 1.0], np.float32)
    # camera on the beast plate
    if lt < 3.55:
        u = ease_io_cubic(lt / 3.55)
        cx, cy, z = lerp(370, 520, u), lerp(260, 220, u), lerp(1.0, 1.35, u)
    else:
        u = ease_io_cubic((lt - 3.55) / 0.6)
        cx, cy, z = lerp(520, 615, u), lerp(220, 195, u), lerp(1.35, 1.95, u)
    sh = max(0.0, lt - 3.4) * 18
    wx, wy = wobble(t * (1 + sh * 0.3), 3 + sh, 4)
    s_cover = max(W / BEAST.shape[1], BAND / BEAST.shape[0]) * z
    M = np.array([[s_cover, 0, W / 2 - s_cover * (cx + wx / s_cover)], [0, s_cover, BAND / 2 - s_cover * (cy + wy / s_cover)]], np.float32)
    rgba = np.dstack([beast, BEAST_A])
    warped = cv2.warpAffine(rgba, M, (W, BAND), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    a = warped[..., 3:4]
    lt_flash = lightning(t)
    expo = 0.3 + 0.7 * min(lt_flash, 1.1)
    fg = warped[..., :3] * expo
    # rim light from the lightning: bluish
    fg = fg + warped[..., :3] * np.array([0.1, 0.2, 0.4], np.float32) * lt_flash
    img = back * (1 + lt_flash * 2.5) * (1 - a) + fg * a
    # glow accents stay visible even in the dark
    g = cv2.warpAffine(GLOW, M, (W, BAND), flags=cv2.INTER_LINEAR)
    gb = cv2.GaussianBlur(g, (0, 0), 9)
    img += (g * 0.3 + gb * 0.5)[..., None] * np.array([0.25, 0.55, 1.0], np.float32) * pulse * 0.35
    # eye
    ex, ey = to_screen(M, 633, 243 - CY0)
    eye = 0.5 + 0.5 * ease((lt - 1.0) / 1.0)
    glow(img, ex, ey, 18 * s_cover, (0.5, 0.85, 1.0), 0.55 * eye)
    glow(img, ex, ey, 70 * s_cover, (0.3, 0.6, 1.0), 0.18 * eye)
    img = grade(img, 1.0, warm=0.3)
    return img, 0.0   # lightning handled internally


def text_layer(txt, size, tracking, weight_file=None):
    font = ImageFont.truetype(weight_file or FONT, size)
    widths = [font.getbbox(c)[2] for c in txt]
    total = sum(widths) + tracking * (len(txt) - 1)
    im = Image.new("L", (int(total) + 40, size * 2), 0)
    d = ImageDraw.Draw(im)
    x = 20
    for c, wdt in zip(txt, widths):
        d.text((x, size * 0.3), c, font=font, fill=255)
        x += wdt + tracking
    return np.asarray(im).astype(np.float32) / 255.0


FONT_B = FONT.replace("600", "700")
FONT_R = FONT.replace("600", "400")
SUB = text_layer("THE NIGHT DOES NOT LET GO", 34, 14, FONT_R)


def paste(img, layer, cx, cy, color, alpha):
    h, w = layer.shape
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    xa, ya = max(0, x0), max(0, y0)
    xb, yb = min(W, x0 + w), min(BAND, y0 + h)
    if xb <= xa or yb <= ya:
        return
    L = layer[ya - y0:yb - y0, xa - x0:xb - x0][..., None] * alpha
    img[ya:yb, xa:xb] = img[ya:yb, xa:xb] * (1 - L) + np.array(color, np.float32) * L


def shot_title(t, lt):         # 21.4 – 25
    gy = (yy / BAND)[..., None]
    img = np.array([0.012, 0.018, 0.03], np.float32) * (1.3 - gy) + fog(t, 0.18, speed=(30, 2), tint=(0.25, 0.3, 0.4))
    # tracking tightens over time
    trk = lerp(60, 26, ease_io_cubic(lt / 3.4))
    title = text_layer("DRENOVAR", 150, trk, FONT_B)
    a = ease(lt / 0.5)
    # glow behind title
    gl = cv2.GaussianBlur(title, (0, 0), 22)
    paste(img, gl, W / 2, BAND / 2 - 30, (0.35, 0.6, 1.0), a * 0.9)
    # metallic gradient fill w/ moving light sweep
    h, w = title.shape
    xs = np.linspace(0, 1, w)[None, :]
    sweep = np.exp(-((xs - lerp(-0.3, 1.3, ease((lt - 0.4) / 1.6))) * 7) ** 2)
    base = 0.72 + 0.18 * np.linspace(1, 0, h)[:, None]
    shade = np.clip(base + sweep * 0.6, 0, 1.3)
    col = np.dstack([shade * 0.86, shade * 0.9, shade * 1.0])
    x0, y0 = int(W / 2 - w / 2), int(BAND / 2 - 30 - h / 2)
    region = img[y0:y0 + h, x0:x0 + w]
    L = title[..., None] * a
    img[y0:y0 + h, x0:x0 + w] = region * (1 - L) + col * L
    # rule lines + subtitle
    sa = ease((lt - 1.1) / 0.8)
    paste(img, SUB, W / 2, BAND / 2 + 95, (0.62, 0.68, 0.76), sa)
    ln = int(lerp(0, 260, ease((lt - 0.8) / 1.0)))
    if ln > 2:
        for side in (-1, 1):
            xa = int(W / 2 + side * 470); xb = xa + side * ln
            cv2.line(img, (min(xa, xb), int(BAND / 2 + 2 - 30)), (max(xa, xb), int(BAND / 2 + 2 - 30)), (0.45, 0.6, 0.8), 1, cv2.LINE_AA)
    return img, 0.0

SHOTS = [  # (start, end, fn, rain amount)
    (1.15, 6.8, shot_cart, 0.85),
    (6.8, 12.4, shot_gate, 0.7),
    (12.4, 17.2, shot_forest, 0.6),
    (17.2, 21.32, shot_beast, 0.75),
    (21.32, 25.0, shot_title, 0.35),
]
XFADE = 0.35


def render_shot(i, t):
    s, e, fn, rain = SHOTS[i]
    img, light_amt = fn(t, t - s)
    lf = lightning(t) * light_amt
    if lf > 0:
        img = img + lf * (img * 0.9 + 0.06) * np.array([0.85, 0.92, 1.1], np.float32)
    rl = rain_layer(t, rain)
    if not np.isscalar(rl):
        rl = rl * (1 + lightning(t) * 2)
        img = img + rl[..., None] * np.array([0.75, 0.82, 0.95], np.float32)
    return img


def frame(f):
    t = f / FPS
    if t < SHOTS[0][0]:
        img = np.zeros((BAND, W, 3), np.float32)
        img += fog(t, 0.05 * t, tint=(0.2, 0.25, 0.32))
    else:
        idx = max(i for i, sh in enumerate(SHOTS) if t >= sh[0])
        img = render_shot(idx, t)
        # cross-dissolve into the next shot (except hard cuts on lightning)
        if idx + 1 < len(SHOTS) and idx not in (2, 3):
            ne = SHOTS[idx][1]
            if t > ne - XFADE:
                k = (t - (ne - XFADE)) / XFADE
                # dip toward black through the dissolve
                img = img * (1 - k) * (1 - 0.5 * math.sin(k * math.pi))
        if idx > 0 and idx - 1 not in (2, 3):
            st = SHOTS[idx][0]
            if t < st + XFADE * 0.6:
                k = (t - st) / (XFADE * 0.6)
                img = img * ease(k)
        # dip to black between forest and beast
        if idx == 2 and t > SHOTS[2][1] - 0.5:
            img = img * (1 - ease((t - (SHOTS[2][1] - 0.5)) / 0.5))
        # white flash into title
        fw = math.exp(-abs(t - 21.32) * 14) if abs(t - 21.32) < 0.5 else 0
        img = img + fw * 0.9
    if t > DUR - 0.9:
        img = img * (1 - ease((t - (DUR - 0.9)) / 0.9))
    # opening fade in
    if t < 1.15:
        pass
    img = finish(img, t, f)
    out = np.zeros((H, W, 3), np.uint8)
    out[BAR:BAR + BAND] = (img * 255 + 0.5).astype(np.uint8)
    return out

# ---------------------------------------------------------------- audio
SR = 48000


def bp(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def lp(x, hi, order=2):
    return signal.sosfilt(signal.butter(order, hi, btype="low", fs=SR, output="sos"), x)


def env_at(n, t0, attack, decay):
    t = np.arange(n) / SR - t0
    e = np.where(t < 0, 0, np.where(t < attack, t / max(attack, 1e-4), np.exp(-(t - attack) / decay)))
    return e


def audio(path):
    n = int(DUR * SR)
    tt = np.arange(n) / SR
    ar = np.random.default_rng(3)
    out = np.zeros((n, 2))
    # rain bed (stereo decorrelated), level follows shots
    rain_lvl = np.interp(tt, [0, 1.1, 1.2, 6.8, 7.0, 12.4, 12.6, 17.1, 17.3, 21.3, 21.5, 25],
                             [0.05, 0.1, 0.55, 0.55, 0.42, 0.42, 0.35, 0.35, 0.3, 0.3, 0.18, 0.0])
    for ch in range(2):
        w = ar.normal(0, 1, n)
        r1 = bp(w, 900, 9000) * 0.5 + bp(w, 200, 900) * 0.25
        drops = (ar.random(n) > 0.9993) * ar.uniform(0.3, 1, n)
        drops = bp(drops, 1500, 7000) * 3
        out[:, ch] += (r1 + drops) * rain_lvl * 0.35
    # thunder per strike (sound lags the flash slightly)
    for t0, a in STRIKES:
        delay = 0.05 if a >= 1 else 0.4
        for ch in range(2):
            w = ar.normal(0, 1, n)
            crack = bp(w, 300, 5000) * env_at(n, t0 + delay * 0.3, 0.005, 0.12) * 0.7 * a
            rumble = bp(w, 25, 160, 2) * 2.2 * env_at(n, t0 + delay, 0.08, 1.4) * a
            rumble *= 1 + 0.6 * np.sin(2 * np.pi * 3.1 * tt + ch)
            out[:, ch] += crack * (1 if a >= 1 else 0.4) + rumble * 1.6
    # low drone swell
    drone_env = np.interp(tt, [0, 2, 12, 17, 21.3, 21.4, 24, 25], [0.0, 0.25, 0.45, 0.55, 0.9, 0.35, 0.3, 0])
    drone = (np.sin(2 * np.pi * 41.2 * tt) + 0.6 * np.sin(2 * np.pi * 61.7 * tt + 0.5 * np.sin(2 * np.pi * 0.2 * tt))
             + 0.3 * np.sin(2 * np.pi * 82.4 * tt * 1.003) + 0.15 * np.sin(2 * np.pi * 123.5 * tt))
    out += (drone * drone_env * 0.12)[:, None]
    # heartbeat during the gate shot, quickening
    hb = np.zeros(n)
    t = 7.2
    while t < 11.2:
        for off, amp in ((0, 1.0), (0.17, 0.7)):
            s = int((t + off) * SR)
            k = np.arange(int(0.25 * SR))
            if s + len(k) < n:
                hb[s:s + len(k)] += amp * np.sin(2 * np.pi * 52 * k / SR) * np.exp(-k / SR / 0.06)
        t += lerp(0.95, 0.55, (t - 7.2) / 4.0)
    out += (hb * 0.55)[:, None]
    # growls: fang reveal + beast push-in
    for t0, dur, amp in ((10.85, 1.4, 0.9), (20.6, 0.9, 1.0)):
        w = ar.normal(0, 1, n)
        g = bp(w, 70, 420, 3)
        am = 0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 27 * tt)) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * tt))
        e = np.clip((tt - t0) / 0.15, 0, 1) * np.clip((t0 + dur - tt) / 0.4, 0, 1)
        gg = np.tanh(g * am * 4) * e * amp * 0.45
        out[:, 0] += gg; out[:, 1] += gg * 0.9
    # riser into title
    rs = np.clip((tt - 19.4) / 1.9, 0, 1) * (tt < 21.32)
    w = ar.normal(0, 1, n)
    riser = bp(w, 600, 6000) * rs ** 2 * 0.25 + np.sin(2 * np.pi * (60 + 200 * rs ** 2) * tt) * rs ** 2 * 0.15
    out += riser[:, None]
    # title impact: sub boom + metallic ring
    e = env_at(n, 21.32, 0.004, 0.9)
    boom = np.sin(2 * np.pi * (38 + 50 * np.exp(-(np.clip(tt - 21.32, 0, None)) * 8)) * tt) * e * 0.9
    ring = sum(np.sin(2 * np.pi * f0 * tt) * a for f0, a in ((220, 0.3), (331, 0.2), (497, 0.12), (743, 0.08))) * env_at(n, 21.32, 0.002, 2.2) * 0.25
    out += (boom + ring)[:, None]
    out[:, 1] = np.roll(out[:, 1], 18)  # tiny stereo width
    # fades + master limiter
    fade = np.clip(tt / 0.6, 0, 1) * np.clip((DUR - tt) / 1.0, 0, 1)
    out *= fade[:, None]
    out = np.tanh(out * 1.2) / np.tanh(1.2)
    out /= np.abs(out).max() / 0.92
    pcm = (out * 32767).astype(np.int16)
    import wave
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR); wf.writeframes(pcm.tobytes())


if __name__ == "__main__":
    if PREVIEW:
        for s in PREVIEW:
            Image.fromarray(frame(int(s * FPS))).save(os.path.join(os.path.dirname(OUT), f"prev_{s:05.2f}.jpg"), quality=88)
        sys.exit(0)
    wav = OUT.replace(".mp4", ".wav")
    audio(wav)
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav,
                             "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
                             "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", OUT],
                            stdin=subprocess.PIPE)
    for f in range(NF):
        proc.stdin.write(frame(f).tobytes())
        if f % 60 == 0:
            print(f"frame {f}/{NF}", flush=True)
    proc.stdin.close(); proc.wait()
    print("done", OUT)
