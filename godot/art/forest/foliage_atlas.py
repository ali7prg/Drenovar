"""Procedural foliage atlas for DRENOVAR forests (no external art).

2048x1024 RGBA, 512 px tiles:
  row 0: spruce sprig | pine tuft branch | oak leaf cluster | birch leaf cluster
  row 1: conifer crown cap | conifer bark | broadleaf bark | (reserved, transparent)
Colours are baked (rich, slightly desaturated); vertex colour can still tint per tree.
Transparent pixels carry dilated colour so mipmaps of alpha-tested cards have no dark fringe.

    python3 foliage_atlas.py out.png
"""
import math
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

T = 512
SS = 2  # supersampling


def tile_canvas():
    return Image.new("RGBA", (T * SS, T * SS), (0, 0, 0, 0))


def jitter(c, rng, amount):
    return tuple(max(0, min(255, int(v + rng.uniform(-amount, amount)))) for v in c[:3]) + (255,)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)


def conifer_sprig(rng, base_dark, base_light, needle_len, density, droop):
    img = tile_canvas()
    d = ImageDraw.Draw(img)
    s = SS
    # Main twig from bottom-centre to the top, slightly curved; side twigs alternate.
    def twig(x0, y0, angle, length, width, depth):
        pts = []
        x, y = x0, y0
        steps = 24
        for i in range(steps + 1):
            t = i / steps
            a = angle + droop * t * t
            pts.append((x, y))
            x += math.cos(a) * length / steps
            y -= math.sin(a) * length / steps
        # Shadowed mass under the needles keeps the frond full at a distance.
        for i, (px, py) in enumerate(pts[2:], 2):
            t = i / steps
            r = needle_len * s * (0.95 - 0.5 * t)
            d.ellipse([px - r, py - r, px + r, py + r], fill=jitter(base_dark, rng, 6))
        d.line(pts, fill=(78, 58, 40, 255), width=max(1, int(width * s)))
        # Needles along the twig, denser and lighter toward the tip.
        for i, (px, py) in enumerate(pts[1:], 1):
            t = i / steps
            local = angle + droop * t * t
            for k in range(density):
                side = 1 if k % 2 == 0 else -1
                na = local + side * rng.uniform(0.55, 1.15) + rng.uniform(-0.15, 0.15)
                nl = needle_len * s * rng.uniform(0.7, 1.15) * (1.0 - 0.35 * t)
                ox = px + rng.uniform(-2, 2) * s
                oy = py + rng.uniform(-2, 2) * s
                ex = ox + math.cos(na) * nl
                ey = oy - math.sin(na) * nl
                shade = lerp(base_dark, base_light, min(1.0, t * 0.8 + rng.uniform(0, 0.45)))
                d.line([(ox, oy), (ex, ey)], fill=jitter(shade, rng, 10), width=max(1, int(2.6 * s)))
        if depth > 0:
            for i in range(2, steps - 2, 2):
                px, py = pts[i]
                t = i / steps
                for side in (1, -1):
                    if rng.random() < 0.85:
                        twig(px, py, angle + side * rng.uniform(0.6, 0.95), length * (0.42 - 0.22 * t), width * 0.6, depth - 1)
    twig(T * s * 0.5, T * s * 0.98, math.pi / 2, T * s * 0.92, 5, 1)
    return img


def pine_branch(rng):
    img = tile_canvas()
    d = ImageDraw.Draw(img)
    s = SS
    x0, y0 = T * s * 0.5, T * s * 0.98
    pts = [(x0 + math.sin(t * 2.2) * 18 * s, y0 - t * T * s * 0.9) for t in np.linspace(0, 1, 20)]
    d.line(pts, fill=(96, 66, 44, 255), width=6 * s)
    # Tufts of long needles at the twig ends.
    for i in range(16):
        t = i / 15
        px, py = pts[min(19, int(t * 19))]
        for side in (1, -1):
            bx = px + side * rng.uniform(40, 150) * s * (1 - 0.5 * t)
            by = py - rng.uniform(10, 60) * s
            d.line([(px, py), (bx, by)], fill=(92, 64, 42, 255), width=3 * s)
            r0 = rng.uniform(30, 44) * s
            d.ellipse([bx - r0, by - r0 * 0.8, bx + r0, by + r0 * 0.6], fill=jitter((30, 50, 30), rng, 6))
            for k in range(70):
                a = rng.uniform(0, 2 * math.pi)
                r = rng.uniform(26, 62) * s
                col = lerp((44, 70, 38), (118, 140, 66), rng.random())
                d.line([(bx, by), (bx + math.cos(a) * r, by - abs(math.sin(a)) * r * 0.9)], fill=jitter(col, rng, 8), width=max(1, int(2.4 * s)))
    return img


def leaf(d, cx, cy, ang, length, width, col, vein, lobed, rng):
    pts = []
    n = 26
    for i in range(n + 1):
        t = i / n
        w = math.sin(math.pi * t) ** 0.8 * width
        if lobed:
            w *= 0.78 + 0.22 * math.cos(t * math.pi * 8)
        pts.append((t * length, w))
    outline = pts + [(x, -y) for x, y in reversed(pts)]
    ca, sa = math.cos(ang), math.sin(ang)
    poly = [(cx + x * ca - y * sa, cy - (x * sa + y * ca)) for x, y in outline]
    d.polygon(poly, fill=col)
    d.line([(cx, cy), (cx + length * ca, cy - length * sa)], fill=vein, width=max(1, SS))


def leaf_cluster(rng, palette, lobed, size, count):
    img = tile_canvas()
    d = ImageDraw.Draw(img)
    s = SS
    stem = [(T * s * 0.5, T * s * 0.98)]
    d.line([(T * s * 0.5, T * s * 0.98), (T * s * 0.5, T * s * 0.25)], fill=(84, 64, 46, 255), width=5 * s)
    for k in range(count):
        # Leaves fill an ellipse; darker toward the bottom/inside (self-shadowing).
        a = rng.uniform(0, 2 * math.pi)
        r = math.sqrt(rng.random())
        cx = T * s * (0.5 + 0.40 * r * math.cos(a))
        cy = T * s * (0.47 + 0.38 * r * math.sin(a))
        light = 1.0 - (cy / (T * s)) * 0.7 + rng.uniform(-0.15, 0.15)
        col = lerp(palette[0], palette[1], max(0.0, min(1.0, light)))
        col = jitter(col, rng, 10)
        vein = tuple(int(c * 0.82) for c in col[:3]) + (255,)
        leaf(d, cx, cy, rng.uniform(0, 2 * math.pi), size * s * rng.uniform(0.8, 1.2), size * s * (0.32 if lobed else 0.42),
             col, vein, lobed, rng)
    return img


def crown_cap(rng):
    # Dense top-down needle mass: many short sprigs radiating from the centre.
    img = tile_canvas()
    d = ImageDraw.Draw(img)
    s = SS
    c = T * s * 0.5
    for k in range(9000):
        a = rng.uniform(0, 2 * math.pi)
        r = (rng.random() ** 0.7) * T * s * 0.46
        x, y = c + math.cos(a) * r, c + math.sin(a) * r
        na = a + rng.uniform(-0.6, 0.6)
        nl = rng.uniform(10, 24) * s
        t = r / (T * s * 0.46)
        col = lerp((24, 46, 34), (86, 112, 66), t * 0.7 + rng.uniform(0, 0.3))
        d.line([(x, y), (x + math.cos(na) * nl, y + math.sin(na) * nl)], fill=jitter(col, rng, 8), width=max(1, int(2.6 * s)))
    return img


def bark(rng, base, groove, plates):
    h = w = T * SS
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    noise = np.zeros((h, w), np.float32)
    for octave in range(5):
        f = 2 ** octave
        g = rng.random() * 100
        noise += np.sin(xx / w * math.pi * 2 * (3 + 4 * f) + np.sin(yy / h * math.pi * 2 * (1 + f) + g) * (0.25 + 0.12 * plates) + g) / f
    noise = (noise - noise.min()) / (noise.max() - noise.min())
    vertical = np.sin(yy / h * math.pi * 14 + xx / w * 3) * 0.08
    t = np.clip(noise + vertical, 0, 1)[..., None]
    col = np.array(groove, np.float32) * (1 - t) + np.array(base, np.float32) * t
    grain = np.random.default_rng(rng.randint(0, 10 ** 6)).normal(0, 9, (h, w, 1))
    col = np.clip(col + grain, 0, 255).astype(np.uint8)
    alpha = np.full((h, w, 1), 255, np.uint8)
    return Image.fromarray(np.concatenate([col, alpha], axis=2), "RGBA")


def dilate_colour(img):
    """Spread opaque colours into transparent pixels (keeps alpha)."""
    arr = np.asarray(img).astype(np.float32)
    rgb, a = arr[..., :3], arr[..., 3:] / 255.0
    acc = rgb * a
    wsum = a.copy()
    for radius in (2, 6, 16, 40):
        blur_rgb = np.asarray(Image.fromarray(np.clip(acc, 0, 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(radius))).astype(np.float32)
        blur_w = np.asarray(Image.fromarray((wsum[..., 0] * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(radius))).astype(np.float32)[..., None] / 255.0
        fill = blur_rgb / np.maximum(blur_w, 1e-3)
        mask = (wsum < 0.01) & (blur_w > 0.01)
        rgb = np.where(mask, fill, rgb)
        acc = np.where(mask, fill * 0.6, acc)
        wsum = np.where(mask, 0.6, wsum)
    out = np.concatenate([np.clip(rgb, 0, 255), arr[..., 3:]], axis=2).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def main(path):
    rng = random.Random(60)
    atlas = Image.new("RGBA", (T * 4, T * 2), (0, 0, 0, 0))
    tiles = [
        conifer_sprig(rng, (18, 38, 30), (88, 118, 72), 27, 8, -0.35),
        pine_branch(rng),
        leaf_cluster(rng, ((40, 60, 26), (122, 140, 58)), True, 70, 150),
        leaf_cluster(rng, ((44, 74, 34), (128, 152, 70)), False, 46, 260),
        crown_cap(rng),
        bark(rng, (118, 86, 64), (46, 32, 26), 2.5),
        bark(rng, (128, 118, 102), (52, 46, 40), 0.6),
    ]
    for index, tile in enumerate(tiles):
        tile = tile.resize((T, T), Image.LANCZOS)
        atlas.paste(tile, ((index % 4) * T, (index // 4) * T))
    # Thin strokes lose alpha when downsampled; harden it so alpha-tested cards keep their
    # coverage in every mip, and calm the palette (the scene light is warm and bright).
    arr = np.asarray(atlas).astype(np.float32)
    arr[..., 3] = np.clip(arr[..., 3] * 2.4, 0, 255)
    arr[: T, :, :3] *= 0.78
    atlas = Image.fromarray(arr.astype(np.uint8), "RGBA")
    atlas = dilate_colour(atlas)
    atlas.save(path)
    print("atlas", path, atlas.size)


if __name__ == "__main__":
    main(sys.argv[1])
