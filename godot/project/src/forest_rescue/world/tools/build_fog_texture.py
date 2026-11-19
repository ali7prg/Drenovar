#!/usr/bin/env python3
"""Painted fog texture for the world-layer fog shell, built from the reference paintings themselves.

Pure-mist patches (soft billowy blue-grey with highlights, no tree tops / UI) are picked
automatically from art/07 panels 1-3 and art/18 panels 1-2, then splatted with feathered masks onto
a toroidal 1024^2 canvas (seamless by construction), the luminance distribution is matched back to
the source mist, and the result is pre-inverted through the city FILMIC tonemap so that the
unshaded shell shows the painting's colours on screen. Writes
godot/project/assets/forest_rescue/world/lf_fog_painted.png (+ .meta.json, + _screen preview).
Run with the blender venv: /opt/tools/blender-venv/bin/python build_fog_texture.py"""
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage import color as skc

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '../../../../../..'))
ART = os.path.join(REPO, 'forest_rescue/delivery/art')
OUT = os.path.join(REPO, 'godot/project/assets/forest_rescue/world')
SOURCES = {
    '07_fog_exploration_interface.png': [(8, 8, 508, 875), (520, 8, 1020, 875), (1032, 8, 1530, 875)],
    '18_hall3_unlock_intro.png': [(8, 8, 508, 1010), (520, 8, 1018, 1010)],
}
PATCH = 72
STRIDE = 12
SIZE = 1024
RNG = np.random.default_rng(2207)


def lab_of(rgb):
    return skc.rgb2lab(rgb)


def fog_mask(lab):
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    C = np.hypot(a, b)
    h = np.degrees(np.arctan2(b, a)) % 360
    return (C < 16) & (L > 30) & (((h > 180) & (h < 300)) | (C < 6))


def pick_patches():
    patches = []
    stats = []
    for name, boxes in SOURCES.items():
        img = np.asarray(Image.open(os.path.join(ART, name)).convert('RGB'), np.float32) / 255
        lab = lab_of(img)
        fog = fog_mask(lab)
        dark = lab[..., 0] < 33
        for x0, y0, x1, y1 in boxes:
            for y in range(y0, y1 - PATCH, STRIDE):
                for x in range(x0, x1 - PATCH, STRIDE):
                    f = fog[y:y + PATCH, x:x + PATCH].mean()
                    if f < 0.985 or dark[y:y + PATCH, x:x + PATCH].mean() > 0.004:
                        continue
                    L = lab[y:y + PATCH, x:x + PATCH, 0]
                    # soft structure: some variation, but no hard edges (low gradient energy)
                    gy, gx = np.gradient(L)
                    edge = np.percentile(np.hypot(gx, gy), 98)
                    if L.std() < 2.5 or edge > 4.5:
                        continue
                    # no tree tips / dark specks (sharp local minima) and no blown-out sun spots
                    local = L - ndimage.gaussian_filter(L, 5.0)
                    if (local < -4.5).mean() > 0.002 or (L > 72).mean() > 0.01:
                        continue
                    patches.append(img[y:y + PATCH, x:x + PATCH].copy())
                    stats.append((name, x, y, float(L.mean()), float(L.std()), float(edge)))
    return patches, stats


def splat(patches):
    canvas = np.zeros((SIZE, SIZE, 3), np.float32)
    mean = np.mean([p.reshape(-1, 3).mean(0) for p in patches], 0)
    canvas[:] = mean
    order = RNG.permutation(len(patches))
    count = 0
    for k in range(520):
        p = patches[order[k % len(order)]]
        s = RNG.uniform(2.6, 4.2)
        size = int(PATCH * s)
        im = np.asarray(Image.fromarray((p * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC), np.float32) / 255
        if RNG.random() < 0.5:
            im = im[:, ::-1]
        yy, xx = np.mgrid[0:size, 0:size]
        r = np.hypot(xx - size / 2 + 0.5, yy - size / 2 + 0.5) / (size / 2)
        mask = np.clip(1 - r, 0, 1)
        mask = mask * mask * (3 - 2 * mask)          # smooth feather
        mask = mask[..., None] * 0.9
        cx, cy = RNG.integers(0, SIZE, 2)
        ys = (np.arange(size) + cy) % SIZE
        xs = (np.arange(size) + cx) % SIZE
        region = canvas[np.ix_(ys, xs)]
        canvas[np.ix_(ys, xs)] = region * (1 - mask) + im * mask
        count += 1
    return canvas, count


def match_luminance(canvas, patches):
    src = np.concatenate([p.reshape(-1, 3) for p in patches[::3]])
    src_L = np.sort(lab_of(src[None])[0][:, 0])
    lab = lab_of(canvas)
    L = lab[..., 0]
    order = np.argsort(L.ravel())
    ranks = np.empty(L.size)
    ranks[order] = np.arange(L.size) / (L.size - 1)
    lab[..., 0] = np.interp(ranks, np.linspace(0, 1, src_L.size), src_L).reshape(L.shape)
    return np.clip(skc.lab2rgb(lab), 0, 1)


def large_forms(canvas):
    """Gentle large-scale soft forms (tileable): low-frequency luminance swell from wrapped blur."""
    lab = lab_of(canvas)
    noise = RNG.normal(size=(SIZE // 16, SIZE // 16))
    noise = ndimage.gaussian_filter(noise, 2.2, mode='wrap')
    noise = np.asarray(Image.fromarray(((noise - noise.min()) / (np.ptp(noise) + 1e-6) * 255).astype(np.uint8)).resize((SIZE, SIZE), Image.BICUBIC), np.float32) / 255
    lab[..., 0] += (noise - 0.5) * 7.0
    return np.clip(skc.lab2rgb(lab), 0, 1)


# FILMIC (Godot 4 tonemap, white 1.0) and its inverse per channel.
def filmic(x):
    A, B, C, D, E, F = 0.15 * 0 + 0.22 * 4, 0.30 * 2, 0.10, 0.20, 0.01, 0.30
    f = lambda c: ((c * (A * c + C * B) + D * E) / (c * (A * c + B) + D * F)) - E / F
    return f(x) / f(1.0)


def s2l(s):
    return np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4)


def l2s(l):
    return np.where(l <= 0.0031308, l * 12.92, 1.055 * np.power(np.maximum(l, 0), 1 / 2.4) - 0.055)


def inverse_filmic_srgb(screen_srgb):
    grid = np.linspace(0, 1.0, 4096)
    mapped = filmic(grid)
    lin = s2l(screen_srgb)
    return l2s(np.interp(lin, mapped, grid))


def main():
    patches, stats = pick_patches()
    print('patches', len(patches))
    canvas, count = splat(patches)
    canvas = ndimage.gaussian_filter(canvas, (1.2, 1.2, 0), mode='wrap')
    canvas = match_luminance(canvas, patches)
    canvas = large_forms(canvas)
    screen = canvas
    albedo = inverse_filmic_srgb(screen)
    os.makedirs(OUT, exist_ok=True)
    Image.fromarray((np.clip(albedo, 0, 1) * 255 + 0.5).astype(np.uint8)).save(os.path.join(OUT, 'lf_fog_painted.png'))
    Image.fromarray((np.clip(screen, 0, 1) * 255 + 0.5).astype(np.uint8)).save(os.path.join(REPO, 'forest_rescue/qa/ingame/world/lf_fog_painted_screen_preview.png'))
    lab = lab_of(screen)
    m = fog_mask(lab)
    meta = {'id': 'lf_fog_painted', 'size': SIZE, 'tool': os.path.relpath(__file__, REPO),
            'sources': {k: v for k, v in SOURCES.items()}, 'patches': len(patches), 'splats': count,
            'method': 'auto-picked pure-mist patches (fog classifier >= 98.5 %, no dark/tree pixels, soft gradients), '
                      'feathered toroidal splatting (seamless), luminance histogram matched to the source mist, gentle '
                      'large-scale swell; stored pre-inverted through the city FILMIC tonemap (shader ALBEDO = texture)',
            'screen_stats': {'fog_frac': float(m.mean()), 'L_p10_p50_p90': np.percentile(lab[..., 0], [10, 50, 90]).round(1).tolist(),
                             'C_med': float(np.median(np.hypot(lab[..., 1], lab[..., 2])))}}
    with open(os.path.join(OUT, 'lf_fog_painted.meta.json'), 'w') as fh:
        json.dump(meta, fh, indent=1)
    print(json.dumps(meta['screen_stats']))


if __name__ == '__main__':
    main()
