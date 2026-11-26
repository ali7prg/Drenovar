#!/usr/bin/env python3
"""DRENOVAR — 25 s animated short, built in code from still concept art.

2.5D pipeline: neural segmentation masks (ISNet) cut characters out of each
plate, backgrounds are in-painted, every character gets a puppet rig
(soft-weighted local affine warps: breathing, head, jaw, tail, fingers,
latch...), plates get a depth-ish parallax field, then a virtual camera,
rain, splashes, fog, lightning, grading and procedural sound are layered on.

Usage: python3 anim.py <uploads_dir> <masks_dir> <font_dir> <out.mp4> [--preview t1 t2 ...]
"""
import sys, os, math, subprocess, wave
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from scipy import signal

UP, MASKS, FONTDIR, OUT = sys.argv[1:5]
PREVIEW = [float(x) for x in sys.argv[6:]] if len(sys.argv) > 5 and sys.argv[5] == "--preview" else None

W, H, FPS, DUR = 1920, 1080, 30, 25.0
BAND = 804
BAR = (H - BAND) // 2
NF = int(DUR * FPS)
rng = np.random.default_rng(7)
cv2.setNumThreads(4)


def load(name):
    return np.asarray(Image.open(os.path.join(UP, name)).convert("RGB")).astype(np.float32) / 255.0


def mask(name):
    return np.asarray(Image.open(os.path.join(MASKS, name + ".png")).convert("L")).astype(np.float32) / 255.0


def smoothstep(e0, e1, x):
    x = np.clip((x - e0) / (e1 - e0), 0, 1)
    return x * x * (3 - 2 * x)


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def lerp(a, b, u):
    return a + (b - a) * u


def osc(t, f, ph=0.0):
    return math.sin(2 * math.pi * f * t + ph)


def jitter(t, seed, f=6.0):
    s = seed * 1.71
    return (math.sin(t * f * 1.0 + s) * 0.5 + math.sin(t * f * 2.31 + s * 3) * 0.3 + math.sin(t * f * 4.7 + s * 5) * 0.2)


def damped(t, t0, freq, decay):
    d = t - t0
    if d < 0:
        return 0.0
    return math.sin(2 * math.pi * freq * d) * math.exp(-d * decay)


_grids = {}


def grid(shape):
    key = shape[:2]
    if key not in _grids:
        gy, gx = np.mgrid[0:key[0], 0:key[1]].astype(np.float32)
        _grids[key] = (gx, gy)
    return _grids[key]


def soft_poly(shape, pts, blur):
    m = np.zeros(shape[:2], np.float32)
    cv2.fillPoly(m, [np.array(pts, np.int32)], 1.0, cv2.LINE_AA)
    return cv2.GaussianBlur(m, (0, 0), blur) if blur else m


def noise_field(h, w, scale, seed):
    r = np.random.default_rng(seed)
    small = r.random((max(2, h // scale) + 2, max(2, w // scale) + 2)).astype(np.float32)
    n = cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)
    n = cv2.GaussianBlur(n, (0, 0), scale * 0.3)
    n -= n.min(); n /= n.max() + 1e-6
    return n


# --------------------------------------------------------------------- rig
class Rig:
    """Soft-weighted local affine bones + free-form fields, evaluated per frame."""

    def __init__(self, shape):
        self.shape = shape[:2]
        self.bones = []   # (y0,y1,x0,x1, w, fn) ; fn(t)->dict(c,rot,tx,ty,sx,sy)
        self.fields = []  # fn(t, gx, gy) -> (dx, dy) full-size

    def bone(self, cx, cy, rx, ry, fn, gate=None):
        h, w = self.shape
        x0, x1 = int(max(0, cx - rx)), int(min(w, cx + rx + 1))
        y0, y1 = int(max(0, cy - ry)), int(min(h, cy + ry + 1))
        gy, gx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        d = np.sqrt(((gx - cx) / rx) ** 2 + ((gy - cy) / ry) ** 2)
        wgt = 0.5 + 0.5 * np.cos(np.pi * np.clip(d, 0, 1))
        if gate is not None:
            wgt *= gate[y0:y1, x0:x1]
        self.bones.append((y0, y1, x0, x1, wgt.astype(np.float32), gx, gy, fn))

    def field(self, fn):
        self.fields.append(fn)

    def eval(self, t):
        h, w = self.shape
        dx = np.zeros((h, w), np.float32); dy = np.zeros((h, w), np.float32)
        for (y0, y1, x0, x1, wgt, gx, gy, fn) in self.bones:
            p = fn(t)
            c = p.get("c", (0, 0)); a = math.radians(p.get("rot", 0.0))
            sx, sy = p.get("sx", 1.0), p.get("sy", 1.0)
            ca, sa = math.cos(a), math.sin(a)
            X, Y = (gx - c[0]) * sx, (gy - c[1]) * sy
            nx = c[0] + ca * X - sa * Y + p.get("tx", 0.0)
            ny = c[1] + sa * X + ca * Y + p.get("ty", 0.0)
            dx[y0:y1, x0:x1] += wgt * (nx - gx)
            dy[y0:y1, x0:x1] += wgt * (ny - gy)
        if self.fields:
            gx, gy = grid(self.shape)
            for fn in self.fields:
                fx, fy = fn(t, gx, gy)
                dx += fx; dy += fy
        return dx, dy


def remap(img, dx, dy, border=cv2.BORDER_REFLECT):
    gx, gy = grid(img.shape)
    mx, my = gx - dx, gy - dy
    if img.ndim == 3 and img.shape[2] > 4:
        return np.dstack([cv2.remap(np.ascontiguousarray(img[..., i:i + 3]), mx, my, cv2.INTER_LINEAR, borderMode=border)
                          .reshape(img.shape[0], img.shape[1], -1) for i in range(0, img.shape[2], 3)])
    return cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=border)


class Layer:
    """Cut-out character: premultiplied RGBA + rig + parallax factor."""

    def __init__(self, plate, alpha, par):
        self.alpha = alpha.astype(np.float32)
        self.prem = np.dstack([plate * self.alpha[..., None], self.alpha])
        self.rig = Rig(plate.shape)
        self.par = par

    def render(self, t, px, py, extra=None):
        dx, dy = self.rig.eval(t)
        dx = dx + px * self.par; dy = dy + py * self.par
        if extra is not None:
            dx += extra[0]; dy += extra[1]
        return remap(self.prem, dx, dy, cv2.BORDER_CONSTANT)


def comp(bg, layer_rgba):
    a = layer_rgba[..., 3:4]
    return bg * (1 - a) + layer_rgba[..., :3]


def clean_plate(plate, alpha, grow=21):
    """In-paint what sits behind a cut-out so the background survives motion."""
    m = (alpha > 0.08).astype(np.uint8)
    m = cv2.dilate(m, np.ones((grow, grow), np.uint8))
    h, w = m.shape
    small = cv2.resize((np.clip(plate, 0, 1) * 255).astype(np.uint8), (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    ms = cv2.resize(m, (w // 2, h // 2), interpolation=cv2.INTER_NEAREST)
    fill = cv2.inpaint(small, ms, 9, cv2.INPAINT_TELEA)
    fill = cv2.resize(fill, (w, h), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255
    fill = cv2.GaussianBlur(fill, (0, 0), 2)
    mf = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 3)[..., None]
    return plate * (1 - mf) + fill * mf


# --------------------------------------------------------------------- screen-space helpers
yy, xx = np.mgrid[0:BAND, 0:W].astype(np.float32)
VIG = (1.0 - 0.55 * np.clip(((xx / W - 0.5) ** 2 * 1.4 + (yy / BAND - 0.5) ** 2 * 2.2) * 2.2, 0, 1) ** 1.4)[..., None]
FOG_A = noise_field(BAND * 2, W * 2, 90, 1)
FOG_B = noise_field(BAND * 2, W * 2, 40, 2)
GRAIN = [rng.normal(0, 1, (BAND // 2, W // 2)).astype(np.float32) for _ in range(8)]
WIND = noise_field(1300, 3000, 60, 5) - 0.5          # plate-space wind noise
WIND2 = noise_field(1300, 3000, 25, 6) - 0.5


def view(src, cx, cy, zoom, rot=0.0):
    h, w = src.shape[:2]
    s = max(W / w, BAND / h) * zoom
    hw, hh = W / (2 * s), BAND / (2 * s)
    cx = min(max(cx, hw), w - hw); cy = min(max(cy, hh), h - hh)
    M = cv2.getRotationMatrix2D((cx, cy), rot, s)
    M[0, 2] += W / 2 - cx; M[1, 2] += BAND / 2 - cy
    return cv2.warpAffine(src, M, (W, BAND), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT), M


def view_blur(src, cams, rot=0.0):
    acc = None
    for (cx, cy, z) in cams:
        fr, M = view(src, cx, cy, z, rot)
        acc = fr if acc is None else acc + fr
    return acc / len(cams), M


def to_screen(M, x, y):
    return M[0, 0] * x + M[0, 1] * y + M[0, 2], M[1, 0] * x + M[1, 1] * y + M[1, 2]


def glow(img, x, y, radius, color, strength):
    r = int(radius * 2.2)
    x0, x1 = int(max(0, x - r)), int(min(img.shape[1], x + r))
    y0, y1 = int(max(0, y - r)), int(min(img.shape[0], y + r))
    if x1 <= x0 or y1 <= y0:
        return
    gy, gx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    g = np.exp(-((gx - x) ** 2 + (gy - y) ** 2) / (radius * radius) * 2.0) * strength
    img[y0:y1, x0:x1] += g[..., None] * np.array(color, np.float32)


def puff(img, x, y, radius, color, strength, t, seed):
    """Volumetric breath / steam: noise-textured soft blob."""
    r = int(radius * 1.6)
    x0, x1 = int(max(0, x - r)), int(min(img.shape[1], x + r))
    y0, y1 = int(max(0, y - r)), int(min(img.shape[0], y + r))
    if x1 <= x0 + 2 or y1 <= y0 + 2:
        return
    gy, gx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    g = np.exp(-((gx - x) ** 2 + (gy - y) ** 2) / (radius * radius) * 1.6)
    ox, oy = int(seed * 37 + t * 40) % 600, int(seed * 53 + t * 15) % 300
    n = FOG_B[oy:oy + (y1 - y0), ox:ox + (x1 - x0)]
    n = cv2.resize(n, (x1 - x0, y1 - y0)) if n.shape != (y1 - y0, x1 - x0) else n
    img[y0:y1, x0:x1] += (g * np.clip(n * 1.6 - 0.3, 0, 1) * strength)[..., None] * np.array(color, np.float32)


class Rain:
    def __init__(self, n, speed, length, thick, bright, blur, angle, seed):
        r = np.random.default_rng(seed)
        self.x = r.uniform(-200, W + 200, n); self.y = r.uniform(0, BAND, n)
        self.v = speed * r.uniform(0.8, 1.2, n); self.L = length * r.uniform(0.7, 1.3, n)
        self.b = bright * r.uniform(0.5, 1.0, n)
        self.thick, self.blur, self.ang = thick, blur, angle

    def layer(self, t):
        lay = np.zeros((BAND, W), np.float32)
        y = (self.y + self.v * t) % (BAND + 300) - 150
        x = self.x + y * self.ang
        x0, y0 = x.astype(int), y.astype(int)
        x1, y1 = (x + self.ang * self.L).astype(int), (y + self.L).astype(int)
        for i in range(len(x)):
            cv2.line(lay, (x0[i], y0[i]), (x1[i], y1[i]), float(self.b[i]), self.thick, cv2.LINE_AA)
        if self.blur:
            lay = cv2.GaussianBlur(lay, (0, 0), self.blur)
        return lay


RAIN = [Rain(1400, 1500, 26, 1, 0.22, 0, 0.12, 11),
        Rain(450, 2300, 60, 1, 0.35, 0.8, 0.13, 12),
        Rain(60, 3400, 170, 3, 0.45, 2.5, 0.15, 13)]


def fog(t, amount, speed=(25, 6), tint=(0.55, 0.62, 0.72)):
    ox = int((t * speed[0]) % W); oy = int((t * speed[1]) % BAND)
    a = FOG_A[oy:oy + BAND, ox:ox + W]
    ox2 = int((t * speed[0] * 1.8 + 300) % W); oy2 = int((t * speed[1] * 0.5 + 100) % BAND)
    b = FOG_B[oy2:oy2 + BAND, ox2:ox2 + W]
    f = np.clip((a * 0.7 + b * 0.3) - 0.35, 0, 1) * amount
    return f[..., None] * np.array(tint, np.float32)


class Splashes:
    """Raindrop impacts: crown + expanding ripple ring, in plate coordinates."""

    def __init__(self, region_fn, n, t0, t1, seed, size=1.0):
        r = np.random.default_rng(seed)
        pts = []
        while len(pts) < n:
            x, y = r.uniform(0, 1900), r.uniform(0, 860)
            if region_fn(x, y):
                pts.append((x, y))
        self.p = np.array(pts); self.t = r.uniform(t0, t1, n); self.s = r.uniform(0.6, 1.4, n) * size

    def draw(self, img, t):
        life = 0.35
        for (x, y), t0, s in zip(self.p, self.t, self.s):
            a = (t - t0) / life
            if 0 <= a < 1:
                persp = 0.5 + y / 1700
                rad = (3 + 22 * a) * s * persp
                col = float(0.45 * (1 - a) ** 1.5)
                cv2.ellipse(img, (int(x), int(y)), (max(1, int(rad)), max(1, int(rad * 0.3))), 0, 0, 360,
                            (col * 0.9, col * 0.95, col), 1, cv2.LINE_AA)
                if a < 0.35:
                    k = a / 0.35
                    for j in (-1, 0, 1):
                        cx = int(x + j * 4 * s * k * persp); cy = int(y - 9 * s * persp * math.sin(k * math.pi))
                        cv2.circle(img, (cx, cy), 1, (0.5 * (1 - k),) * 3, -1, cv2.LINE_AA)


# Lightning (absolute seconds, strength)
STRIKES = [(1.0, 1.0), (4.7, 0.75), (14.85, 1.0), (17.75, 1.0), (19.2, 0.8), (20.45, 1.0), (21.32, 1.3)]


def lightning(t):
    v = 0.0
    for t0, a in STRIKES:
        d = t - t0
        if -0.01 < d < 0.9:
            v += a * (math.exp(-d * 9) + 0.6 * math.exp(-((d - 0.12) * 40) ** 2) + 0.35 * math.exp(-((d - 0.26) * 30) ** 2))
    return v


def grade(img, exposure=1.0, warm=1.0):
    img = img * exposure
    lum = (img @ np.array([0.299, 0.587, 0.114], np.float32))[..., None]
    img = lum + (img - lum) * 0.88
    sh = np.clip(1 - lum * 2.5, 0, 1)
    img = img + sh * np.array([-0.01, 0.006, 0.03], np.float32)
    hi = np.clip(lum * 2 - 0.8, 0, 1)
    img = img + hi * np.array([0.04, 0.015, -0.03], np.float32) * warm
    img = np.clip(img, 0, None)
    img = img / (1 + img * 0.25) * 1.25
    return img ** 1.08


def finish(img, f):
    img = img * VIG
    img[..., 0] = np.roll(img[..., 0], 2, 1); img[..., 2] = np.roll(img[..., 2], -2, 1)
    gr = cv2.resize(GRAIN[f % 8], (W, BAND), interpolation=cv2.INTER_LINEAR)[..., None]
    img = img + gr * 0.022 * (0.4 + (1 - np.clip(img, 0, 1)) * 0.6)
    return np.clip(img, 0, 1)


def wind_field(amp, scale_t, weight, seed=0, fine=0.0):
    """Turbulent displacement (fur, cloth, foliage)."""
    def fn(t, gx, gy):
        h, w = weight.shape
        ox = int(t * 140 * scale_t + seed * 211) % 900; oy = int(t * 35 * scale_t + seed * 97) % 300
        n1 = WIND[oy:oy + h, ox:ox + w]; n2 = WIND[oy + 50:oy + 50 + h, ox + 70:ox + 70 + w]
        dx, dy = n1 * amp, n2 * amp * 0.6
        if fine:
            f1 = WIND2[oy:oy + h, (ox * 2) % 900:(ox * 2) % 900 + w]
            dx = dx + f1 * fine
        return dx * weight, dy * weight
    return fn


# ===================================================================== PLATES & RIGS
FONT_B = os.path.join(FONTDIR, "cinzel-latin-700-normal.woff")
FONT_R = os.path.join(FONTDIR, "cinzel-latin-400-normal.woff")

# ---------------- CART -------------------------------------------------
CART = load("e90b9966-image.png")
_cf = mask("cart_full")
head_gate = np.zeros_like(_cf); cv2.ellipse(head_gate, (960, 300), (110, 100), 0, 0, 360, 1.0, -1)
man_a = np.maximum(mask("cart_man"), _cf * cv2.GaussianBlur(head_gate, (0, 0), 6))
man_a = np.clip((man_a - 0.15) / 0.6, 0, 1)
guard_a = np.clip((mask("cart_guard") - 0.15) / 0.6, 0, 1)
CART_BG = clean_plate(CART, np.maximum(man_a, guard_a), 17)
CART_MAN = Layer(CART, man_a, 0.8)
CART_GUARD = Layer(CART, guard_a, 0.3)
_h, _w = CART.shape[:2]
_gx, _gy = grid(CART.shape)
CART_PAR = 0.22 + 0.78 * np.clip((_gy - 300) / 500, 0, 1) ** 1.2
CART_PAR = np.maximum(CART_PAR, smoothstep(1380, 1420, _gx) * 1.0)
CART_PAR = cv2.GaussianBlur(CART_PAR.astype(np.float32), (0, 0), 12)
CART_BG_RIG = Rig(CART.shape)
CART_BG_RIG.bone(205, 140, 40, 55, lambda t: dict(c=(205, 92), rot=4.5 * osc(t, 0.45) + 1.2 * osc(t, 1.3)))      # lantern swing
CART_BG_RIG.bone(1268, 290, 34, 110, lambda t: dict(c=(1262, 185), rot=2.8 * osc(t, 0.55, 1)))                # rope 1
CART_BG_RIG.bone(1360, 450, 34, 95, lambda t: dict(c=(1352, 360), rot=3.5 * osc(t, 0.5, 2)))                  # rope 2
_tarp = soft_poly(CART.shape, [(520, 230), (1390, 170), (1400, 360), (1000, 330), (640, 470), (500, 470)], 25)
def _tarp_wave(t, gx, gy):
    return (_tarp * 1.2 * np.sin(gx / 140 - t * 3.1),
            _tarp * 2.6 * np.sin(gx / 95 - t * 4.3) * smoothstep(220, 420, gy))
CART_BG_RIG.field(_tarp_wave)
_ferns = soft_poly(CART.shape, [(1530, 280), (1846, 250), (1846, 700), (1500, 640)], 30)
CART_BG_RIG.field(wind_field(5, 1.0, _ferns, 3, 3))
m = CART_MAN.rig
m.bone(760, 410, 190, 130, lambda t: dict(c=(760, 520), sx=1 + 0.012 * osc(t, 0.7), sy=1 + 0.018 * osc(t, 0.7)))   # breathing
m.bone(965, 300, 105, 100, lambda t: dict(c=(930, 385), rot=-2.2 * ease((t - 2.4) / 0.6) + 0.5 * osc(t, 0.7, 1),
                                          tx=-5 * ease((t - 2.4) / 0.6) + 2 * ease(t / 5), ty=1.5 * osc(t, 0.7)))   # glance toward guard
m.bone(965, 605, 80, 60, lambda t: dict(c=(940, 600), tx=10 * ease((t - 0.6) / 2.6), ty=2 * ease((t - 0.6) / 2.6),
                                        rot=1.5 * jitter(t, 3, 9) * 0.3))                                          # hand creeps forward
m.bone(640, 750, 80, 60, lambda t: dict(c=(640, 790), ty=1.5 * ease((t - 1.0) / 1.5), rot=0.6 * osc(t, 0.7)))        # left hand presses mud
m.bone(560, 560, 110, 120, wind_field_bone := (lambda t: dict(c=(560, 520), tx=1.5 * osc(t, 1.7), rot=0.8 * osc(t, 1.1))))  # shirt tatters
g = CART_GUARD.rig
g.bone(115, 385, 70, 95, lambda t: dict(c=(170, 330), rot=7 * osc(t, 0.6) + 2 * osc(t, 1.7)))            # wolf tail
g.bone(225, 280, 50, 45, lambda t: dict(c=(240, 300), tx=2 * osc(t, 0.9), ty=2.5 * abs(osc(t, 1.4))))      # wolf head sniffing
g.bone(300, 200, 38, 40, lambda t: dict(c=(300, 232), rot=-7 * ease((t - 3.4) / 0.5) + 1.0 * osc(t, 0.4)))  # guard turns head
g.bone(285, 340, 70, 110, lambda t: dict(c=(290, 250), rot=1.2 * osc(t, 0.8)))                            # cloak sway
g.bone(160, 350, 110, 100, lambda t: dict(c=(160, 420), sy=1 + 0.02 * osc(t, 1.1)))                        # wolf breathing
CART_SPL = Splashes(lambda x, y: (y > 560 and (x < 470 or x > 1150)) or (y > 790), 900, 1.0, 6.4, 21)

# ---------------- GATE -------------------------------------------------
GATE = load("819905a1-image.png")
_gf = mask("gate_full")
_gx, _gy = grid(GATE.shape)
hand_a = np.clip((_gf - 0.15) / 0.6, 0, 1) * (1 - smoothstep(540, 575, _gx)) * smoothstep(240, 270, _gy)
lever_poly = [(1128, 210), (1250, 195), (1300, 250), (1215, 330), (1190, 420), (1140, 520), (1102, 560),
              (1012, 556), (1016, 500), (1098, 395), (1125, 300)]
lever_a = np.clip((_gf - 0.1) / 0.5, 0, 1) * soft_poly(GATE.shape, lever_poly, 2)
GATE_BG = clean_plate(GATE, np.maximum(hand_a, lever_a), 15)
GATE_HAND = Layer(GATE, hand_a, 1.5)
GATE_LEVER = Layer(GATE, lever_a, 1.0)
wolf_a = cv2.GaussianBlur(mask("gate_wolf"), (0, 0), 6)
_posts = np.clip(1 - smoothstep(560, 600, _gx) + smoothstep(1080, 1110, _gx), 0, 1)
GATE_PAR = cv2.GaussianBlur((_posts * 1.0 + (1 - _posts) * (0.15 + 0.5 * wolf_a)).astype(np.float32), (0, 0), 6)
IMPACTS = [1.35, 1.95]


def lever_angle(lt):
    a = 0.0
    for k, t0 in enumerate(IMPACTS):
        d = lt - t0
        if d >= 0:
            a += (9 - 3 * k) * math.exp(-d * 5) * abs(math.cos(2 * math.pi * 3.2 * d)) ** 0.7
    return a


GATE_LEVER.rig.bone(1150, 380, 260, 260, lambda t: dict(c=(1255, 255), rot=lever_angle(t)))
GATE_HAND.rig.bone(390, 330, 190, 80, lambda t: dict(c=(240, 360), rot=-2.5 * ease((t - 1.35) / 0.3) + 0.4 * jitter(t, 1, 14),
                                                      tx=-3 * ease((t - 1.35) / 0.3)))   # fingers clench at impact
GATE_HAND.rig.bone(410, 660, 120, 60, lambda t: dict(c=(300, 670), rot=-2 * ease((t - 1.4) / 0.3) + 0.4 * jitter(t, 2, 12)))
GATE_HAND.rig.field(lambda t, gx, gy: (np.float32(0.8 * jitter(t, 5, 20) + 3 * damped(t, 1.35, 7, 9)), np.float32(0.6 * jitter(t, 6, 18))))
_gr = Rig(GATE.shape)
_gr.bone(690, 95, 200, 150, lambda t: dict(c=(820, 190), rot=-2.0 * ease((t - 3.9) / 0.4) + 0.7 * osc(t, 0.8),
                                           ty=-5 * ease((t - 3.9) / 0.4) + 2 * osc(t, 0.8) + 1.2 * jitter(t, 9, 25) * ease((t - 4.0) / 0.3),
                                           tx=6 * damped(t, 1.35, 4, 6)))           # head: heaves, rams gate, snarls
_gr.field(wind_field(5, 1.2, wolf_a * smoothstep(250, 400, _gy), 1, 4))         # fur in the wind
GATE_BG_RIG = _gr
_gate_post_shake = lambda lt: (5 * damped(lt, 1.35, 9, 10) + 3 * damped(lt, 1.95, 9, 10))

# ---------------- FOREST -----------------------------------------------
FOREST = load("36ead0f1-image.png")
fman_a = np.clip((mask("forest_man") - 0.15) / 0.6, 0, 1)
FOREST_BG = clean_plate(FOREST, fman_a, 15)
FOREST_MAN = Layer(FOREST, fman_a, 0.95)
_gx, _gy = grid(FOREST.shape)
_near = np.clip(np.clip(1 - _gx / 1000, 0, 1) * 0.7 + np.clip((_gy - 560) / 300, 0, 1) * 0.7, 0, 1)
FOREST_PAR = cv2.GaussianBlur((0.1 + 0.85 * _near).astype(np.float32), (0, 0), 20)
FBR = Rig(FOREST.shape)
_tops = np.clip(1 - _gy / 560, 0, 1) ** 2
FBR.field(lambda t, gx, gy: ((3.5 * np.sin(t * 1.3 + gx / 260) + 1.5 * np.sin(t * 2.9 + gx / 90)) * _tops, np.float32(0)))
_sky = soft_poly(FOREST.shape, [(1010, 0), (1560, 0), (1520, 210), (1300, 290), (1060, 250)], 30)
FBR.field(lambda t, gx, gy: (_sky * (t * 5.0), _sky * 0))
_river = soft_poly(FOREST.shape, [(1160, 660), (1300, 650), (1420, 700), (1560, 853), (1120, 853), (1200, 760)], 12)
def _flow(t, gx, gy):
    oy = int(t * 160) % 300; ox = int(t * 60) % 300
    n1 = WIND2[oy:oy + gx.shape[0], ox:ox + gx.shape[1]]
    n2 = WIND2[oy + 100:oy + 100 + gx.shape[0], ox + 50:ox + 50 + gx.shape[1]]
    return _river * n1 * 9, _river * n2 * 7
FBR.field(_flow)
_ferns_f = soft_poly(FOREST.shape, [(0, 400), (620, 470), (900, 700), (900, 853), (0, 853)], 30) * (1 - cv2.GaussianBlur(fman_a, (0, 0), 8))
FBR.field(wind_field(4, 1.0, _ferns_f, 7, 2))
fm = FOREST_MAN.rig
fm.bone(400, 345, 95, 70, lambda t: dict(c=(400, 420), ty=-3.5 * max(0, osc(t, 0.95)), sx=1 + 0.01 * osc(t, 0.95)))   # heavy breathing
fm.bone(462, 275, 52, 55, lambda t: dict(c=(445, 318), rot=1.2 * osc(t, 0.95) - 6 * ease((t - 3.05) / 0.25) + 2 * ease((t - 3.9) / 0.8),
                                         tx=-4 * ease((t - 3.05) / 0.25)))                                         # snaps toward the sound
fm.bone(390, 545, 110, 55, lambda t: dict(c=(390, 500), tx=2.5 * osc(t, 1.8), rot=1.5 * osc(t, 1.3, 1)))           # tunic tatters
fm.bone(320, 480, 50, 60, lambda t: dict(c=(330, 400), rot=2.0 * osc(t, 0.95, 2)))                                  # red-bound arm sway
fm.bone(465, 520, 40, 50, lambda t: dict(c=(445, 440), rot=-1.5 * osc(t, 0.95, 1)))
FOREST_SPL = Splashes(lambda x, y: y > 620 and x < 1100, 700, 12.0, 17.2, 33, 0.8)
# The beast leaping across the ridge — the LAUNCH pose from the sheet.
SHEET = load("bb93b0cd-image.jpg")
LEAP = SHEET[620:810, 780:1070].copy()
LEAP_A = np.clip((mask("leap")[620:810, 780:1070] - 0.4) / 0.35, 0, 1)
LEAP_A[:, :30] *= np.linspace(0, 1, 30)[None, :]  # drop the sheet's arrow glyph

# ---------------- BEAST ------------------------------------------------
BX0, BY0, BX1, BY1 = 0, 70, 705, 560
BEAST = SHEET[BY0:BY1, BX0:BX1].copy()
BEAST_A = np.clip((mask("beast")[BY0:BY1, BX0:BX1] - 0.2) / 0.55, 0, 1)
_b = BEAST
GLOWM = cv2.GaussianBlur(np.clip((_b[..., 2] - _b[..., 0]) * 6.0 - 0.15, 0, 1) * np.clip(_b.mean(-1) * 2, 0, 1), (0, 0), 1.2) * BEAST_A
BEAST_L = Layer(BEAST, BEAST_A, 1.0)
BEAST_L.prem = np.dstack([BEAST * BEAST_A[..., None], GLOWM * BEAST_A, BEAST_A])  # carry glow as extra channel
_gx, _gy = grid(BEAST.shape)
br = BEAST_L.rig
oy = BY0
br.bone(370, 260 - oy, 190, 130, lambda t: dict(c=(370, 420 - oy), sx=1 + 0.012 * osc(t, 0.75), sy=1 + 0.022 * osc(t, 0.75)))     # breathing
br.bone(615, 255 - oy, 120, 115, lambda t: dict(c=(520, 235 - oy), rot=4.5 * ease((t - 0.4) / 2.0) - 6 * ease((t - 3.25) / 0.3)
                                                + 0.8 * osc(t, 0.75) + 0.6 * jitter(t, 4, 22) * ease((t - 1.0) / 0.5)))           # head lowers, then rears
br.bone(645, 315 - oy, 62, 40, lambda t: dict(c=(598, 292 - oy), rot=3 + 7 * ease((t - 1.2) / 0.5) + 2 * jitter(t, 8, 30)
                                              + 6 * ease((t - 3.25) / 0.25)))                                                      # jaw snarls open
br.bone(120, 300 - oy, 170, 190, lambda t: dict(c=(280, 250 - oy), rot=5 * osc(t, 0.55) + 2 * osc(t, 1.4)))                       # tail
br.bone(430, 140 - oy, 260, 90, lambda t: dict(c=(430, 200 - oy), ty=-2.5 * ease((t - 1.0) / 1.0), sy=1 + 0.04 * ease((t - 1.0) / 1.0)))  # hackles rise
br.bone(380, 330 - oy, 330, 120, lambda t: dict(c=(380, 470 - oy), sy=1 - 0.05 * ease((t - 2.9) / 0.4) + 0.08 * ease((t - 3.3) / 0.2)))   # crouch, spring
br.field(wind_field(4, 1.4, (BEAST_A * np.clip(1 - _gy / 420, 0.2, 1)).astype(np.float32), 9, 3))
BEAST_BACK = cv2.GaussianBlur(FOREST[300:853, 900:1844], (0, 0), 6)   # misty valley as the backdrop

# ===================================================================== SHOTS
def shot_cart(t, lt):
    u = ease_io(lt / 5.4)
    px = lerp(-22, 22, u); py = lerp(4, -4, u)
    dx, dy = CART_BG_RIG.eval(lt)
    bg = remap(CART_BG, dx + px * CART_PAR, dy + py * CART_PAR)
    img = comp(bg, CART_GUARD.render(lt, px, py))
    img = comp(img, CART_MAN.render(lt, px, py))
    CART_SPL.draw(img, t)
    wx, wy = jitter(t * 0.35, 1) * 6, jitter(t * 0.3, 2) * 4
    out, M = view(img, lerp(1160, 960, u) + wx, lerp(450, 390, u) + wy, lerp(1.0, 1.2, u))
    out = out.copy()
    lan_x = 205 + 55 * math.sin(math.radians(4.5 * osc(lt, 0.45)))
    for (lx, ly, s) in [(lan_x, 145, 1.0), (650, 195, 0.6), (418, 250, 0.4), (15, 235, 0.3)]:
        sx, sy = to_screen(M, lx, ly)
        fl = 0.75 + 0.25 * math.sin(t * 23 + lx) * math.sin(t * 9.7 + ly) + 0.1 * math.sin(t * 41)
        glow(out, sx, sy, 140 * M[0, 0], (1.0, 0.62, 0.25), 0.22 * s * fl)
    out = grade(out, 0.95)
    out += fog(t, 0.2)
    return out, 1.0


def shot_gate(t, lt):
    u = ease(lt / 3.9)
    px = lerp(-12, 10, u)
    shake = _gate_post_shake(lt)
    dx, dy = GATE_BG_RIG.eval(lt)
    sdx = shake * smoothstep(1000, 1100, grid(GATE.shape)[0])     # right gate post shudders on impact
    bg = remap(GATE_BG, dx + px * GATE_PAR + sdx, dy)
    img = comp(bg, GATE_LEVER.render(lt, px, 0, (np.float32(shake), np.float32(0))))
    img = comp(img, GATE_HAND.render(lt, px, 0))
    # fang drool
    for k, td in enumerate((0.6, 2.6, 4.6)):
        d = lt - td
        if 0 < d < 0.5:
            yv = 262 + 0.5 * 2400 * d * d
            cv2.ellipse(img, (628, int(yv)), (3, 6), 0, 0, 360, (0.75, 0.75, 0.7), -1, cv2.LINE_AA)
    # drop shaken off the latch by the first impact
    d = lt - 1.38
    if 0 < d < 0.55:
        cv2.ellipse(img, (int(1046 + 60 * d), int(585 + 0.5 * 2600 * d * d)), (6, 10), 0, 0, 360, (0.8, 0.65, 0.42), -1, cv2.LINE_AA)
    wx, wy = jitter(t * 0.4, 3) * 4, jitter(t * 0.35, 4) * 3
    wx += 6 * damped(lt, 1.35, 6, 8) + 4 * damped(lt, 1.95, 6, 8)       # camera flinch
    if lt < 3.9:
        out, M = view(img, lerp(820, 1040, u) + wx, lerp(470, 430, u) + wy, lerp(1.02, 1.18, u))
    else:
        def cam(l):
            v = ease_io((l - 3.9) / 0.42)
            return (lerp(1040, 680, v) + wx, lerp(430, 235, v) + wy, lerp(1.18, 1.5, v) + max(0, l - 4.35) * 0.06)
        if lt < 4.4:
            out, M = view_blur(img, [cam(lt - k * 0.007) for k in range(7)])
        else:
            out, M = view(img, *cam(lt))
    out = out.copy()
    for (lx, ly) in [(1035, 265), (765, 345)]:
        sx, sy = to_screen(M, lx, ly)
        glow(out, sx, sy, 110 * M[0, 0], (1.0, 0.6, 0.25), 0.16 * (0.8 + 0.2 * math.sin(t * 19 + lx) * math.sin(t * 7.3)))
    # breath: rhythmic hot puffs from the jaws
    for k in range(4):
        ph = ((lt * 0.85) + k * 0.25) % 1.0
        bx, by = to_screen(M, 740 + ph * 220, 160 + ph * 40 - k * 6)
        puff(out, bx, by, (50 + ph * 160) * M[0, 0], (0.8, 0.85, 0.92), 0.22 * math.sin(ph * math.pi) ** 1.5, lt, k)
    out = grade(out, 1.0)
    out += fog(t, 0.08)
    return out, 1.0


def shot_forest(t, lt):
    u = ease_io(lt / 5.0)
    px = lerp(-26, 26, u); py = lerp(3, -3, u)
    dx, dy = FBR.eval(lt)
    img = remap(FOREST_BG, dx + px * FOREST_PAR, dy + py * FOREST_PAR)
    # the beast crosses the ridge in the lightning
    d = (lt - 2.7) / 0.62
    if 0 <= d <= 1:
        acc = np.zeros(img.shape, np.float32); acca = np.zeros(img.shape[:2], np.float32)
        for k in range(5):
            dd = d - k * 0.012
            if dd < 0:
                continue
            x = lerp(930, 1500, dd); y = lerp(470, 455, dd) - 70 * math.sin(dd * math.pi)
            s = 0.9; ang = lerp(-8, 10, dd)
            Mx = cv2.getRotationMatrix2D((145, 95), ang, s)
            Mx[0, 2] += x - 145; Mx[1, 2] += y - 95
            col = LEAP * 0.14 + np.array([0.012, 0.018, 0.03], np.float32)
            lay = cv2.warpAffine(np.dstack([col * LEAP_A[..., None], LEAP_A]), Mx, (img.shape[1], img.shape[0]))
            acc += lay[..., :3]; acca += lay[..., 3]
        n = 5
        a = (acca / n)[..., None]
        img = img * (1 - a) + acc / n
    img = comp(img, FOREST_MAN.render(lt, px, py))
    FOREST_SPL.draw(img, t)
    wx, wy = jitter(t * 0.3, 5) * 5, jitter(t * 0.3, 6) * 3
    out, M = view(img, lerp(800, 1060, u) + wx, lerp(440, 410, u) + wy, lerp(1.0, 1.15, u))
    out = out.copy()
    sx, sy = to_screen(M, 1531, 386)
    glow(out, sx, sy, 90 * M[0, 0], (1.0, 0.65, 0.3), 0.28 * (0.85 + 0.15 * math.sin(t * 11) * math.sin(t * 4.3 + 1)))
    hx, hy = to_screen(M, 500, 285)
    puff(out, hx, hy, 40 * M[0, 0], (0.75, 0.8, 0.88), 0.12 * max(0, osc(lt, 0.95, -1.2)), lt, 7)   # his breath in the cold
    out = grade(out, 0.95)
    out += fog(t, 0.42, speed=(40, 3), tint=(0.5, 0.58, 0.7))
    return out, 1.0


def shot_beast(t, lt):
    fl = lightning(t)
    # backdrop: misty valley, very dark, lit by lightning
    back, _ = view(BEAST_BACK, 470 + lt * 10, 280, 1.0)
    back = back * (0.16 + 0.9 * min(fl, 1.2)) * np.array([0.7, 0.85, 1.1], np.float32)
    back += fog(t, 0.22, speed=(60, 4), tint=(0.22, 0.27, 0.36))
    layer = BEAST_L.render(lt, 0, 0)
    a = layer[..., 4:5]
    # camera on the beast
    if lt < 3.3:
        v = ease_io(lt / 3.3)
        cam = lambda l: (lerp(360, 520, v), lerp(195, 165, v), lerp(1.0, 1.32, v))
        cams = [cam(lt)]
    else:
        def cam(l):
            v = ease_io((l - 3.3) / 0.9)
            return (lerp(520, 625, v), lerp(165, 180, v), lerp(1.32, 2.3, v ** 1.4))
        cams = [cam(lt - k * 0.012) for k in range(6)]
    sh = max(0.0, lt - 3.25) * 14
    wx, wy = jitter(t * (1 + sh * 0.4), 7) * (3 + sh), jitter(t * (1 + sh * 0.4), 8) * (2 + sh)
    cams = [(c[0] + wx / 3, c[1] + wy / 3, c[2]) for c in cams]
    h, w = BEAST.shape[:2]
    pad = 400   # extend plate so the camera never runs off the cut-out
    big = np.zeros((h + pad * 2, w + pad * 2, 5), np.float32)
    big[pad:pad + h, pad:pad + w] = layer
    cams = [(c[0] + pad, c[1] + pad, c[2] * (w + 2 * pad) / w) for c in cams]
    acc = None
    for (cx, cy, z) in cams:
        s = max(W / (w + 2 * pad), BAND / (h + 2 * pad)) * z
        M = np.array([[s, 0, W / 2 - s * cx], [0, s, BAND / 2 - s * cy]], np.float32)
        fr = np.dstack([cv2.warpAffine(np.ascontiguousarray(big[..., i:i + 3]), M, (W, BAND), flags=cv2.INTER_CUBIC,
                                       borderMode=cv2.BORDER_CONSTANT).reshape(BAND, W, -1) for i in (0, 3)])
        acc = fr if acc is None else acc + fr
    fr = acc / len(cams)
    a = np.clip(fr[..., 4:5], 0, 1)
    gl = fr[..., 3]
    expo = 0.3 + 0.7 * min(fl, 1.1)
    fg = fr[..., :3] * expo + fr[..., :3] * np.array([0.1, 0.2, 0.4], np.float32) * fl
    img = back * (1 - a) + fg
    pulse = 0.55 + 0.45 * math.sin(lt * 3.2) ** 2 + 0.6 * ease((lt - 2.5) / 1.2)
    gb = cv2.GaussianBlur(gl, (0, 0), 9)
    img += (gl * 0.35 + gb * 0.5)[..., None] * np.array([0.25, 0.55, 1.0], np.float32) * pulse * 0.4
    # eye follows the head bone
    p = br.bones[1][7](lt)
    c = p["c"]; ang = math.radians(p["rot"])
    ex0, ey0 = 633 - c[0], 243 - oy - c[1]
    ex = c[0] + math.cos(ang) * ex0 - math.sin(ang) * ey0 + pad
    ey = c[1] + math.sin(ang) * ex0 + math.cos(ang) * ey0 + pad
    sx, sy = M[0, 0] * ex + M[0, 2], M[1, 1] * ey + M[1, 2]
    eye = 0.5 + 0.5 * ease((lt - 1.0) / 1.0)
    glow(img, sx, sy, 5 * M[0, 0], (0.5, 0.85, 1.0), 0.6 * eye)
    glow(img, sx, sy, 20 * M[0, 0], (0.3, 0.6, 1.0), 0.15 * eye)
    # breath from the jaws in the cold
    for k in range(3):
        ph = (lt * 0.75 + k * 0.33) % 1.0
        bx, by = M[0, 0] * (690 + pad + ph * 90) + M[0, 2], M[1, 1] * (320 - oy + pad + ph * 10) + M[1, 2]
        puff(img, bx, by, (20 + ph * 70) * M[0, 0], (0.6, 0.68, 0.8), 0.14 * math.sin(ph * math.pi), lt, k + 3)
    img = grade(img, 1.0, warm=0.3)
    return img, 0.0


def text_layer(txt, size, tracking, font_file):
    font = ImageFont.truetype(font_file, size)
    widths = [font.getbbox(c)[2] for c in txt]
    total = sum(widths) + tracking * (len(txt) - 1)
    im = Image.new("L", (int(total) + 40, size * 2), 0)
    d = ImageDraw.Draw(im)
    x = 20
    for c, wdt in zip(txt, widths):
        d.text((x, size * 0.3), c, font=font, fill=255)
        x += wdt + tracking
    return np.asarray(im).astype(np.float32) / 255.0


SUB = text_layer("THE NIGHT DOES NOT LET GO", 34, 14, FONT_R)


def paste(img, layer, cx, cy, color, alpha):
    h, w = layer.shape
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(BAND, y0 + h)
    if xb <= xa or yb <= ya:
        return
    L = layer[ya - y0:yb - y0, xa - x0:xb - x0][..., None] * alpha
    img[ya:yb, xa:xb] = img[ya:yb, xa:xb] * (1 - L) + np.array(color, np.float32) * L


def shot_title(t, lt):
    gy = (yy / BAND)[..., None]
    img = np.array([0.012, 0.018, 0.03], np.float32) * (1.3 - gy) + fog(t, 0.18, speed=(30, 2), tint=(0.25, 0.3, 0.4))
    trk = lerp(60, 26, ease_io(lt / 3.4))
    title = text_layer("DRENOVAR", 150, trk, FONT_B)
    a = ease(lt / 0.5)
    paste(img, cv2.GaussianBlur(title, (0, 0), 22), W / 2, BAND / 2 - 30, (0.35, 0.6, 1.0), a * 0.9)
    h, w = title.shape
    xs = np.linspace(0, 1, w)[None, :]
    sweep = np.exp(-((xs - lerp(-0.3, 1.3, ease((lt - 0.4) / 1.6))) * 7) ** 2)
    shade = np.clip(0.72 + 0.18 * np.linspace(1, 0, h)[:, None] + sweep * 0.6, 0, 1.3)
    col = np.dstack([shade * 0.86, shade * 0.9, shade * 1.0])
    x0, y0 = int(W / 2 - w / 2), int(BAND / 2 - 30 - h / 2)
    L = title[..., None] * a
    img[y0:y0 + h, x0:x0 + w] = img[y0:y0 + h, x0:x0 + w] * (1 - L) + col * L
    paste(img, SUB, W / 2, BAND / 2 + 95, (0.62, 0.68, 0.76), ease((lt - 1.1) / 0.8))
    ln = int(lerp(0, 260, ease((lt - 0.8) / 1.0)))
    if ln > 2:
        for side in (-1, 1):
            xa = int(W / 2 + side * 470); xb = xa + side * ln
            cv2.line(img, (min(xa, xb), int(BAND / 2 - 28)), (max(xa, xb), int(BAND / 2 - 28)), (0.45, 0.6, 0.8), 1, cv2.LINE_AA)
    return img, 0.0


SHOTS = [(1.0, 6.4, shot_cart, 0.85), (6.4, 12.2, shot_gate, 0.7), (12.2, 17.2, shot_forest, 0.6),
         (17.2, 21.32, shot_beast, 0.75), (21.32, 25.0, shot_title, 0.35)]


def render_shot(i, t):
    s, e, fn, rain = SHOTS[i]
    img, light_amt = fn(t, t - s)
    lf = lightning(t) * light_amt
    if lf > 0:
        img = img + lf * (img * 0.9 + 0.06) * np.array([0.85, 0.92, 1.1], np.float32)
    if rain > 0:
        rl = sum(r.layer(t) for r in RAIN) * rain * (1 + lightning(t) * 2)
        img = img + rl[..., None] * np.array([0.75, 0.82, 0.95], np.float32)
    return img


def frame(f):
    t = f / FPS
    if t < SHOTS[0][0]:
        img = np.zeros((BAND, W, 3), np.float32) + fog(t, 0.05 * t, tint=(0.2, 0.25, 0.32))
    else:
        idx = max(i for i, sh in enumerate(SHOTS) if t >= sh[0])
        img = render_shot(idx, t)
        s, e = SHOTS[idx][0], SHOTS[idx][1]
        if idx in (0, 1) and t > e - 0.3:                      # dip-dissolve out
            k = (t - (e - 0.3)) / 0.3
            img = img * (1 - k) * (1 - 0.5 * math.sin(k * math.pi))
        if idx in (1, 2) and t < s + 0.2:
            img = img * ease((t - s) / 0.2)
        if idx == 2 and t > e - 0.5:
            img = img * (1 - ease((t - (e - 0.5)) / 0.5))
        if idx == 3 and t < s + 0.15:
            img = img * ease((t - s) / 0.15)
        if abs(t - 21.32) < 0.5:
            img = img + math.exp(-abs(t - 21.32) * 14) * 0.9
    if t > DUR - 0.9:
        img = img * (1 - ease((t - (DUR - 0.9)) / 0.9))
    img = finish(img, f)
    out = np.zeros((H, W, 3), np.uint8)
    out[BAR:BAR + BAND] = (img * 255 + 0.5).astype(np.uint8)
    return out


# ===================================================================== SOUND
SR = 48000


def bp(x, lo, hi, order=2):
    return signal.sosfilt(signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos"), x)


def env_at(n, t0, attack, decay):
    t = np.arange(n) / SR - t0
    return np.where(t < 0, 0, np.where(t < attack, t / max(attack, 1e-4), np.exp(-(t - attack) / decay)))


def audio(path):
    n = int(DUR * SR); tt = np.arange(n) / SR
    ar = np.random.default_rng(3)
    out = np.zeros((n, 2))
    rain_lvl = np.interp(tt, [0, 0.9, 1.0, 6.4, 6.6, 12.2, 12.4, 17.1, 17.3, 21.3, 21.5, 25],
                         [0.05, 0.1, 0.55, 0.55, 0.42, 0.42, 0.35, 0.35, 0.3, 0.3, 0.18, 0.0])
    for ch in range(2):
        w = ar.normal(0, 1, n)
        drops = bp((ar.random(n) > 0.9993) * ar.uniform(0.3, 1, n), 1500, 7000) * 3
        out[:, ch] += (bp(w, 900, 9000) * 0.5 + bp(w, 200, 900) * 0.25 + drops) * rain_lvl * 0.35
    for t0, a in STRIKES:
        delay = 0.05 if a >= 1 else 0.4
        for ch in range(2):
            w = ar.normal(0, 1, n)
            crack = bp(w, 300, 5000) * env_at(n, t0 + delay * 0.3, 0.005, 0.12) * 0.7 * a
            rumble = bp(w, 25, 160) * 2.2 * env_at(n, t0 + delay, 0.08, 1.4) * a * (1 + 0.6 * np.sin(2 * np.pi * 3.1 * tt + ch))
            out[:, ch] += crack * (1 if a >= 1 else 0.4) + rumble * 1.6
    drone_env = np.interp(tt, [0, 2, 12, 17, 21.3, 21.4, 24, 25], [0.0, 0.25, 0.45, 0.55, 0.9, 0.35, 0.3, 0])
    drone = (np.sin(2 * np.pi * 41.2 * tt) + 0.6 * np.sin(2 * np.pi * 61.7 * tt + 0.5 * np.sin(2 * np.pi * 0.2 * tt))
             + 0.3 * np.sin(2 * np.pi * 82.4 * tt * 1.003) + 0.15 * np.sin(2 * np.pi * 123.5 * tt))
    out += (drone * drone_env * 0.12)[:, None]
    # latch: heavy thud on the gate + iron rattle
    for k, ti in enumerate(IMPACTS):
        t0 = 6.4 + ti; amp = 1.0 - 0.3 * k
        e = env_at(n, t0, 0.003, 0.25)
        thud = bp(ar.normal(0, 1, n), 40, 250) * e * 2.0 + np.sin(2 * np.pi * 55 * tt) * env_at(n, t0, 0.002, 0.18) * 0.8
        clank = sum(np.sin(2 * np.pi * f0 * tt) * a for f0, a in ((612, .5), (1430, .35), (2210, .25), (3170, .15)))
        rattle = clank * env_at(n, t0 + 0.01, 0.001, 0.07) + clank * env_at(n, t0 + 0.13, 0.001, 0.05) * 0.5 + clank * env_at(n, t0 + 0.24, 0.001, 0.04) * 0.25
        out[:, 0] += (thud + rattle * 0.35) * amp; out[:, 1] += (thud + rattle * 0.3) * amp
    # heartbeat
    hb = np.zeros(n); t = 6.9
    while t < 10.4:
        for off, amp in ((0, 1.0), (0.17, 0.7)):
            s = int((t + off) * SR); k = np.arange(int(0.25 * SR))
            if s + len(k) < n:
                hb[s:s + len(k)] += amp * np.sin(2 * np.pi * 52 * k / SR) * np.exp(-k / SR / 0.06)
        t += lerp(0.9, 0.5, (t - 6.9) / 3.5)
    out += (hb * 0.55)[:, None]
    # growls
    for t0, dur, amp in ((10.3, 1.9, 0.9), (17.6, 1.2, 0.6), (19.4, 1.9, 1.0)):
        g = bp(ar.normal(0, 1, n), 70, 420, 3)
        am = 0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 27 * tt)) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * tt))
        e = np.clip((tt - t0) / 0.15, 0, 1) * np.clip((t0 + dur - tt) / 0.4, 0, 1)
        gg = np.tanh(g * am * 4) * e * amp * 0.45
        out[:, 0] += gg; out[:, 1] += gg * 0.9
    # whoosh as the beast clears the ridge (pans L->R)
    t0 = 12.2 + 2.7
    e = np.clip((tt - t0) / 0.3, 0, 1) * np.clip((t0 + 0.75 - tt) / 0.35, 0, 1)
    wsh = bp(ar.normal(0, 1, n), 300, 2500) * e * 0.5
    pan = np.clip((tt - t0) / 0.7, 0, 1)
    out[:, 0] += wsh * (1 - pan); out[:, 1] += wsh * pan
    # man's breath (forest) — short noisy exhalations
    for i in range(5):
        t0 = 12.4 + i * 1.05
        e = env_at(n, t0, 0.05, 0.18)
        out += (bp(ar.normal(0, 1, n), 400, 2200) * e * 0.12)[:, None]
    # riser + impact
    rs = np.clip((tt - 19.6) / 1.72, 0, 1) * (tt < 21.32)
    out += (bp(ar.normal(0, 1, n), 600, 6000) * rs ** 2 * 0.25 + np.sin(2 * np.pi * (60 + 200 * rs ** 2) * tt) * rs ** 2 * 0.15)[:, None]
    e = env_at(n, 21.32, 0.004, 0.9)
    boom = np.sin(2 * np.pi * (38 + 50 * np.exp(-np.clip(tt - 21.32, 0, None) * 8)) * tt) * e * 0.9
    ring = sum(np.sin(2 * np.pi * f0 * tt) * a for f0, a in ((220, .3), (331, .2), (497, .12), (743, .08))) * env_at(n, 21.32, 0.002, 2.2) * 0.25
    out += (boom + ring)[:, None]
    out[:, 1] = np.roll(out[:, 1], 18)
    out *= (np.clip(tt / 0.6, 0, 1) * np.clip((DUR - tt) / 1.0, 0, 1))[:, None]
    out = np.tanh(out * 1.2) / np.tanh(1.2)
    out /= np.abs(out).max() / 0.92
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes((out * 32767).astype(np.int16).tobytes())


if __name__ == "__main__":
    if PREVIEW:
        for s in PREVIEW:
            Image.fromarray(frame(int(round(s * FPS)))).save(os.path.join(os.path.dirname(os.path.abspath(OUT)), f"p_{s:05.2f}.jpg"), quality=88)
        sys.exit(0)
    wav = OUT.replace(".mp4", ".wav")
    audio(wav)
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav,
                             "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-pix_fmt", "yuv420p",
                             "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
    for f in range(NF):
        proc.stdin.write(frame(f).tobytes())
        if f % 60 == 0:
            print(f"frame {f}/{NF}", flush=True)
    proc.stdin.close(); proc.wait()
    print("done", OUT)
