#!/usr/bin/env python3
"""Screen-door dither detector: high-pass a crop, 2D FFT, compare the energy at the 4-px and
2-px periods (Bayer 4x4 / 2x2 frequencies) with the median spectrum around them.

    python3 forest_rescue/tools/dither_check.py <png>... [--box x0,y0,x1,y1]
Prints per image: peak ratio at (N/4, 0), (0, N/4), (N/4, N/4), (N/2, 0), (0, N/2) and a verdict
(ratio > 6 at any of them = periodic dot pattern).
"""
import sys

import numpy as np
from PIL import Image, ImageFilter


def check(path, box=None, size=256):
    im = Image.open(path).convert("L")
    if box:
        im = im.crop(box)
    w, h = im.size
    # centred square crop (power of two keeps the dither frequencies on exact bins)
    s = min(size, w, h)
    s = 1 << (s.bit_length() - 1)
    x0, y0 = (w - s) // 2, (h - s) // 2
    im = im.crop((x0, y0, x0 + s, y0 + s))
    a = np.asarray(im, np.float32)
    low = np.asarray(im.filter(ImageFilter.GaussianBlur(2.0)), np.float32)
    hp = a - low
    hp *= np.hanning(s)[:, None] * np.hanning(s)[None, :]
    spec = np.abs(np.fft.fft2(hp))
    def ratio(fy, fx):
        v = spec[fy % s, fx % s]
        ys = [(fy + dy) % s for dy in range(-6, 7)]
        xs = [(fx + dx) % s for dx in range(-6, 7)]
        ring = spec[np.ix_(ys, xs)].copy()
        ring[5:8, 5:8] = np.nan
        return float(v / (np.nanmedian(ring) + 1e-6))
    q, hf = s // 4, s // 2
    peaks = {"4px_x": ratio(0, q), "4px_y": ratio(q, 0), "4px_xy": ratio(q, q), "2px_x": ratio(0, hf), "2px_y": ratio(hf, 0)}
    worst = max(peaks.values())
    return peaks, worst


def scan(path, tile=128, step=96, region=None):
    """Worst tile over the image (the dither is local: crowns / fog edge around actors)."""
    w, h = Image.open(path).size
    x0, y0, x1, y1 = region or (0, 60, w, h - 120)       # skip the HUD rows
    worst = (0.0, None, None)
    for y in range(y0, y1 - tile + 1, step):
        for x in range(x0, x1 - tile + 1, step):
            peaks, v = check(path, (x, y, x + tile, y + tile), tile)
            if v > worst[0]:
                worst = (v, (x, y), peaks)
    return worst


if __name__ == "__main__":
    box = None
    if "--box" in sys.argv:
        box = tuple(int(v) for v in sys.argv[sys.argv.index("--box") + 1].split(","))
    for p in sys.argv[1:]:
        if not p.endswith(".png"):
            continue
        v, at, peaks = scan(p, region=box)
        verdict = "DOTS" if v > 6.0 else "clean"
        print(f"{verdict:5s} worst tile {v:6.1f} at {at}  " + "  ".join(f"{k} {x:5.1f}" for k, x in (peaks or {}).items()) + f"  {p}")
