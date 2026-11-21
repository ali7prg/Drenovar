#!/usr/bin/env python3
"""Layout pass 4: camp pad readability. For a look frame centred on a glade (city camera, ortho, zoom = frame
height in metres), compares the pad (ellipse 0.35-0.8 x the 8.5 m pad radius, excluding the cage / props in the
middle) with the meadow ring just outside it (1.3-1.7 x), as median CIELAB; ΔE76 >= 15 required. Also reports the
pad's median sRGB (target warm sand ~ (185, 150, 105)) and the meadow HSV.

    /opt/tools/blender-venv/bin/python forest_rescue/qa/ingame/integration/pad_metrics.py <png> <zoom> <glade ground height> [...]
"""
import math
import sys

import numpy as np
from PIL import Image

PAD_R = 8.5


def srgb_to_lab(rgb):
    c = rgb / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def ring_mask(h, w, zoom, r0, r1, ground_h=0.0):
    ppm = h / zoom
    yy, xx = np.mgrid[0:h, 0:w]
    cy = h / 2 - ground_h * math.cos(math.radians(38.0)) * ppm      # the glade stands ground_h above the target
    dx = (xx - w / 2) / ppm
    dy = (yy - cy) / ppm / math.sin(math.radians(38.0))
    d = np.hypot(dx, dy)
    return (d >= r0) & (d <= r1)


def main():
    args = sys.argv[1:]
    for i in range(0, len(args), 3):
        path, zoom, gh = args[i], float(args[i + 1]), float(args[i + 2])
        a = np.asarray(Image.open(path).convert("RGB")).astype(float)
        h, w = a.shape[:2]
        pad = ring_mask(h, w, zoom, PAD_R * 0.35, PAD_R * 0.8, gh)
        meadow = ring_mask(h, w, zoom, PAD_R * 1.3, PAD_R * 1.7, gh)
        lum = a @ np.array([0.299, 0.587, 0.114])
        mx, mn = a.max(-1), a.min(-1)
        sat = (mx - mn) / np.maximum(mx, 1)
        # drop dark tree / prop pixels and pale trail pixels from the meadow sample
        meadow &= (lum > 45) & (sat > 0.2)
        pad &= lum > 45
        lab = srgb_to_lab(a)
        lp = np.median(lab[pad], 0)
        lm = np.median(lab[meadow], 0)
        de = float(np.linalg.norm(lp - lm))
        rgb_p = np.median(a[pad], 0)
        rgb_m = np.median(a[meadow], 0)
        print("%s: pad sRGB %s meadow sRGB %s  ΔE76 %.1f (%s)" % (path.split("/")[-1], rgb_p.astype(int).tolist(),
                                                                rgb_m.astype(int).tolist(), de, "ok" if de >= 15 else "LOW"))


if __name__ == "__main__":
    main()
