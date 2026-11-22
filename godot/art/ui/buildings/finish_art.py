#!/usr/bin/env python3
"""Downsizes the building card renders of tools/bake_building_art.gd into the game assets.

    python3 godot/art/ui/buildings/finish_art.py /tmp/building_art godot/project/assets/ui/buildings/v6

Every render (1040 x 1040, level I of a V6 type on its diorama tile, transparent) becomes
448 x 448: the construction cards draw it at about 210 canvas units (2.1x, crisp at the
iPhone 12 canvas scale of 1.86). Pillow resizes RGBA premultiplied, so the transparent edge
keeps no dark fringe. Lossy WebP at q88 with an exact alpha plane.
"""
import os
import sys

from PIL import Image

SIZE = (448, 448)


def main() -> None:
    source, target = sys.argv[1], sys.argv[2]
    os.makedirs(target, exist_ok=True)
    total = 0
    for name in sorted(os.listdir(source)):
        if not name.endswith('.png'):
            continue
        image = Image.open(os.path.join(source, name)).convert('RGBA')
        image = image.resize(SIZE, Image.LANCZOS, reducing_gap=3.0)
        path = os.path.join(target, name[:-4] + '.webp')
        image.save(path, 'WEBP', quality=88, alpha_quality=100, method=6, exact=False)
        total += os.path.getsize(path)
        print(path, os.path.getsize(path))
    print('building art:', total // 1024, 'KiB')


if __name__ == '__main__':
    main()
