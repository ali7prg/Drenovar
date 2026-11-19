#!/usr/bin/env python3
"""Fog colour statistics (CIELAB) with the coordinator's classifier: fog pixel = C < 16 and L > 30 and
(bluish hue 180..300 deg or C < 6). Prints L p10/p50/p90, C median, h median per image (optional box).
usage (blender venv): fog_colour_stats.py <image>[:x0,y0,x1,y1] ..."""
import sys

import numpy as np
from PIL import Image
from skimage import color as skc


def stats(path, box=None):
    im = np.asarray(Image.open(path).convert('RGB'), np.float32) / 255
    if box:
        x0, y0, x1, y1 = box
        im = im[y0:y1, x0:x1]
    lab = skc.rgb2lab(im.reshape(-1, 3)[None])[0]
    L, a, b = lab[:, 0], lab[:, 1], lab[:, 2]
    C = np.hypot(a, b)
    h = np.degrees(np.arctan2(b, a)) % 360
    m = (C < 16) & (L > 30) & (((h > 180) & (h < 300)) | (C < 6))
    if m.sum() < 50:
        return None
    return {'n': int(m.sum()), 'frac': float(m.mean()), 'L': np.percentile(L[m], [10, 50, 90]).round(1).tolist(),
            'C': round(float(np.median(C[m])), 1), 'h': round(float(np.median(h[m & (C > 3)])), 1) if (m & (C > 3)).sum() else None}


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        path, _, box = arg.partition(':')
        b = tuple(int(v) for v in box.split(',')) if box else None
        s = stats(path, b)
        print('%-60s %s' % (path.split('/')[-1] + (':' + box if box else ''), s))
