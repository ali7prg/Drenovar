#!/usr/bin/env python3
"""Downsizes the unit portrait renders of tools/bake_unit_portraits.gd into the game assets.

    python3 godot/art/ui/units/finish_portraits.py /tmp/unit_portraits godot/project/assets/ui/units

Full figures become 288 x 352 (cards show them at ~118 x 144 canvas units, 2.4x), busts
128 x 128 (64-unit slots, 2x). Pillow resizes RGBA premultiplied, so the transparent edge
keeps no dark fringe. Lossy WebP at q90 with an exact alpha plane: visually lossless,
a fraction of a PNG.
"""
import os
import sys

from PIL import Image

SIZES = {False: (288, 352), True: (128, 128)}


def main() -> None:
    source, target = sys.argv[1], sys.argv[2]
    os.makedirs(target, exist_ok=True)
    total = 0
    for name in sorted(os.listdir(source)):
        if not name.endswith('.png'):
            continue
        bust = name.endswith('-bust.png')
        image = Image.open(os.path.join(source, name)).convert('RGBA')
        image = image.resize(SIZES[bust], Image.LANCZOS)
        path = os.path.join(target, name[:-4] + '.webp')
        image.save(path, 'WEBP', quality=90, alpha_quality=100, method=6, exact=False)
        total += os.path.getsize(path)
        print(path, os.path.getsize(path))
    print('portraits:', total // 1024, 'KiB')


if __name__ == '__main__':
    main()
