#!/usr/bin/env python3
"""Rough canopy-cover fraction per zone: art/01 crops vs in-game zoom-68 shots (same classifier).
Canopy = dark foliage (L < 52, chroma > 10, hue 60..200) or golden crowns (chroma > 38, hue 45..95,
L 45..85); excluded = fog/water (hue 190..260, chroma < 32 or blue water); rest = open ground
(trails, grass, rock). usage (blender venv): canopy_cover.py <shots_dir> <prefix>"""
import json
import os
import sys

import numpy as np
from PIL import Image
from skimage import color as skc

ART = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../../../forest_rescue/delivery/art/01_world_masterplan.png'))
ZONES = {  # zone: (art/01 crop box, in-game view)
    'NW golden grove': ((60, 60, 560, 420), 'full_grove_z68'),
    'south spruce': ((420, 640, 960, 1000), 'full_spruce_z68'),
    'east river': ((960, 240, 1500, 760), 'full_east_z68'),
    'SW quarry': ((20, 600, 470, 960), 'full_quarry_z68'),
}


def cover(rgb):
    lab = skc.rgb2lab(rgb.reshape(-1, 3)[None])[0]
    L, a, b = lab[:, 0], lab[:, 1], lab[:, 2]
    c = np.hypot(a, b)
    h = np.degrees(np.arctan2(b, a)) % 360
    fog = ((h > 190) & (h < 270) & (c < 32)) | ((h > 180) & (h < 260) & (c >= 32))
    canopy = ((L < 52) & (c > 10) & (h > 60) & (h < 200)) | ((c > 38) & (h > 45) & (h < 95) & (L > 45) & (L < 85))
    canopy &= ~fog
    valid = ~fog
    return float(canopy.sum()) / max(1, int(valid.sum())), float(fog.mean())


def main(shots, prefix):
    art = np.asarray(Image.open(ART).convert('RGB'), np.float32) / 255
    rows = {}
    for zone, (box, view) in ZONES.items():
        x0, y0, x1, y1 = box
        art_cover, _ = cover(art[y0:y1, x0:x1])
        path = os.path.join(shots, prefix + view + '.png')
        game_cover, game_fog = (None, None)
        if os.path.exists(path):
            g = np.asarray(Image.open(path).convert('RGB'), np.float32) / 255
            game_cover, game_fog = cover(g)
        rows[zone] = {'art01': round(art_cover, 3), 'game': round(game_cover, 3) if game_cover is not None else None,
                      'game_fog_fraction_excluded': round(game_fog, 3) if game_fog is not None else None, 'view': view, 'art_box': box}
    print(json.dumps(rows, indent=1))
    with open(os.path.join(shots, prefix + 'canopy_cover.json'), 'w') as fh:
        json.dump(rows, fh, indent=1)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
