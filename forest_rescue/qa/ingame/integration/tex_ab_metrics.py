#!/usr/bin/env python3
"""Texture-compression A/B check: the last frame of every qa_forest_perf.gd --segments run (--save-frames=<dir>)
before / after a texture import change, same fixtures + fixed fps. Per frame and per central crop (the segment's
target actor sits at the screen centre): SSIM (luma, Gaussian window) and mean / p95 ΔE76.

    /opt/tools/blender-venv/bin/python forest_rescue/qa/ingame/integration/tex_ab_metrics.py <before dir> <after dir> [crop dir]
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi


def lab(rgb):
    c = rgb / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def ssim(a, b):
    a = a @ [0.299, 0.587, 0.114]
    b = b @ [0.299, 0.587, 0.114]
    g = lambda x: ndi.gaussian_filter(x, 1.5)
    mu_a, mu_b = g(a), g(b)
    va, vb, cov = g(a * a) - mu_a ** 2, g(b * b) - mu_b ** 2, g(a * b) - mu_a * mu_b
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    m = ((2 * mu_a * mu_b + c1) * (2 * cov + c2)) / ((mu_a ** 2 + mu_b ** 2 + c1) * (va + vb + c2))
    return float(m.mean())


def main():
    before, after = sys.argv[1], sys.argv[2]
    crops = sys.argv[3] if len(sys.argv) > 3 else None
    print("%-26s %8s %8s %8s | %8s %8s %8s" % ("frame", "SSIM", "dE mean", "dE p95", "crop SSIM", "dE mean", "dE p95"))
    for name in sorted(os.listdir(before)):
        if not name.endswith(".png") or not os.path.exists(os.path.join(after, name)):
            continue
        a = np.asarray(Image.open(os.path.join(before, name)).convert("RGB")).astype(float)
        b = np.asarray(Image.open(os.path.join(after, name)).convert("RGB")).astype(float)
        h, w = a.shape[:2]
        y0, y1, x0, x1 = h // 2 - 170, h // 2 + 170, w // 2 - 260, w // 2 + 260
        de = np.linalg.norm(lab(a) - lab(b), axis=-1)
        dc = de[y0:y1, x0:x1]
        print("%-26s %8.4f %8.2f %8.2f | %8.4f %8.2f %8.2f" % (name[:-4], ssim(a, b), de.mean(), np.percentile(de, 95),
                                                           ssim(a[y0:y1, x0:x1], b[y0:y1, x0:x1]), dc.mean(), np.percentile(dc, 95)))
        if crops:
            os.makedirs(crops, exist_ok=True)
            pair = Image.new("RGB", (2 * (x1 - x0) + 8, y1 - y0), (30, 27, 24))
            pair.paste(Image.fromarray(a[y0:y1, x0:x1].astype(np.uint8)), (0, 0))
            pair.paste(Image.fromarray(b[y0:y1, x0:x1].astype(np.uint8)), (x1 - x0 + 8, 0))
            pair.save(os.path.join(crops, name[:-4] + "_before_after.jpg"), quality=92)


if __name__ == "__main__":
    main()
