#!/usr/bin/env python3
"""Offline bake of the green-broadleaf copy of the kit foliage atlas (world-layer palette zoning).

art/01 is mostly deep-green round broadleaf crowns; gold is concentrated in the NW grove. The kit
ships one golden-oak palette (lf_foliage_atlas.png). This tool measures the art/01 green
broadleaf crowns and golden grove crowns (CIE Lab/LCh), then maps the atlas' golden foliage texels
(hue 25..100 deg) by the measured art/01 golden->green shift (lightness z-score transfer, chroma
ratio, hue rotation) and writes lf_foliage_atlas_green.png + .meta.json next to the kit.
Run with the blender venv (numpy, scikit-image):
  /opt/tools/blender-venv/bin/python bake_green_oak_atlas.py
"""
import json
import os

import numpy as np
from PIL import Image
from skimage import color as skc

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '../../../../../..'))
KIT = os.path.join(REPO, 'godot/project/assets/forest_rescue/forest')
ART01 = os.path.join(REPO, 'forest_rescue/delivery/art/01_world_masterplan.png')
GREEN_BOXES = {'east_river': (1150, 280, 1500, 470), 'mid_belt': (250, 560, 560, 700),
               'town_wall': (600, 300, 900, 560), 'east_low': (1100, 620, 1400, 760)}
GOLD_BOXES = {'nw_grove_a': (400, 100, 620, 240), 'nw_grove_b': (40, 120, 330, 330), 'grove_top': (560, 40, 760, 140)}


def lch(px):
    lab = skc.rgb2lab(px[None])[0]
    c = np.hypot(lab[:, 1], lab[:, 2])
    h = np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) % 360
    return lab, c, h


def stats(art, boxes, hue_lo, hue_hi):
    sel = []
    for x0, y0, x1, y1 in boxes.values():
        px = art[y0:y1, x0:x1].reshape(-1, 3)
        lab, c, h = lch(px)
        m = (c > 12) & (h > hue_lo) & (h < hue_hi) & (lab[:, 0] < 75)
        sel.append(np.stack([lab[m, 0], c[m], h[m]], 1))
    s = np.concatenate(sel)
    return {'L_mean': float(s[:, 0].mean()), 'L_std': float(s[:, 0].std()), 'C_med': float(np.median(s[:, 1])),
            'H_med': float(np.median(s[:, 2])), 'n': int(len(s)),
            'L_p10_p50_p90': np.percentile(s[:, 0], [10, 50, 90]).round(1).tolist()}


def main():
    art = np.asarray(Image.open(ART01).convert('RGB'), np.float32) / 255
    green = stats(art, GREEN_BOXES, 95, 160)
    gold = stats(art, GOLD_BOXES, 40, 95)
    atlas = np.asarray(Image.open(os.path.join(KIT, 'lf_foliage_atlas.png')).convert('RGBA'), np.float32) / 255
    rgb = atlas[..., :3].reshape(-1, 3)
    alpha = atlas[..., 3].reshape(-1)
    lab, c, h = lch(rgb)
    sel = (alpha > 0.05) & (c > 8) & (h > 25) & (h < 100)
    src = {'L_mean': float(lab[sel, 0].mean()), 'L_std': float(lab[sel, 0].std()), 'C_med': float(np.median(c[sel])),
           'H_med': float(np.median(h[sel]))}
    # Transfer the art/01 golden->green shift onto the atlas golden texels.
    d_l = green['L_mean'] - gold['L_mean']
    k_l = green['L_std'] / max(gold['L_std'], 1e-3)
    k_c = green['C_med'] / max(gold['C_med'], 1e-3)
    d_h = green['H_med'] - gold['H_med']
    z = (lab[:, 0] - src['L_mean']) / max(src['L_std'], 1e-3)
    new_l = src['L_mean'] + d_l + z * src['L_std'] * k_l
    # weight: full on clearly golden texels, fading out toward browns/greys (twigs keep their colour)
    w = np.clip((c - 8) / 10, 0, 1) * np.clip((h - 25) / 10, 0, 1) * np.clip((100 - h) / 10, 0, 1)
    new_c = c * (1 + (k_c - 1) * w)
    new_h = (h + d_h * w) % 360
    out_lab = lab.copy()
    out_lab[:, 0] = lab[:, 0] + (new_l - lab[:, 0]) * w
    out_lab[:, 1] = new_c * np.cos(np.radians(new_h))
    out_lab[:, 2] = new_c * np.sin(np.radians(new_h))
    out = np.clip(skc.lab2rgb(out_lab[None])[0], 0, 1)
    rgb_out = np.where(sel[:, None], out, rgb)
    img = np.concatenate([rgb_out.reshape(atlas.shape[0], atlas.shape[1], 3), atlas[..., 3:]], 2)
    Image.fromarray((img * 255 + 0.5).astype(np.uint8), 'RGBA').save(os.path.join(KIT, 'lf_foliage_atlas_green.png'))
    lab2, c2, h2 = lch(rgb_out[sel])
    result = {'lab': {'L_mean': float(lab2[:, 0].mean()), 'C_med': float(np.median(c2)), 'H_med': float(np.median(h2))}}
    meta = {
        'id': 'lf_foliage_atlas_green', 'source': 'lf_foliage_atlas.png (kit v2)', 'tool': os.path.relpath(__file__, REPO),
        'purpose': 'baked green-broadleaf palette copy for golden-oak instances outside the art/01 golden grove '
                   '(world layer palette zoning; no runtime tint)',
        'method': 'golden foliage texels (hue 25..100, chroma > 8) get the measured art/01 golden->green shift: '
                  'lightness z-score transfer, chroma ratio, hue rotation; browns/greys/other hues untouched',
        'art01_green_broadleaf': green, 'art01_golden_grove': gold, 'atlas_golden_before': src, 'atlas_after': result,
        'transfer': {'dL': d_l, 'kL': k_l, 'kC': k_c, 'dH_deg': d_h}, 'selected_texels': int(sel.sum())}
    with open(os.path.join(KIT, 'lf_foliage_atlas_green.meta.json'), 'w') as fh:
        json.dump(meta, fh, indent=1)
    print(json.dumps(meta, indent=1))


if __name__ == '__main__':
    main()
