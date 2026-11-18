#!/usr/bin/env python3
"""Side-by-side reference | in-game comparisons for the world-layer iterations.
usage: compose_compare.py <shots_dir> <prefix>   (writes <prefix>compare_<name>.png)"""
import sys, os
from PIL import Image, ImageDraw
ART = os.path.join(os.path.dirname(__file__), '../../../../../../forest_rescue/delivery/art')
PAIRS = [  # (game shot, reference file, crop box or None, label)
    ('locked_default', '18_hall3_unlock_intro.png', (8, 8, 508, 1010), 'art/18 panel 1 (locked, hall I-II)'),
    ('unlocked_entrance', '18_hall3_unlock_intro.png', (520, 8, 1018, 1010), 'art/18 panel 2 (hall III, entrance opens)'),
    ('explored_act1', '07_fog_exploration_interface.png', (520, 8, 1020, 875), 'art/07 panel 2 (fog + revealed path)'),
    ('explored_path_close', '07_fog_exploration_interface.png', (1032, 8, 1530, 875), 'art/07 panel 3 (path close)'),
    ('overview_explored', '01_world_masterplan.png', None, 'art/01 masterplan'),
    ('arena', '08_final_boss_arena.png', (0, 0, 1536, 715), 'art/08 arena'),
    ('locked_overview', '18_hall3_unlock_intro.png', (8, 8, 508, 1010), 'art/18 panel 1 (locked overview)'),
]
def main(shots, prefix):
    art = os.path.abspath(ART)
    for name, ref, box, label in PAIRS:
        game_path = os.path.join(shots, prefix + name + '.png')
        if not os.path.exists(game_path):
            continue
        g = Image.open(game_path).convert('RGB')
        r = Image.open(os.path.join(art, ref)).convert('RGB')
        if box:
            r = r.crop(box)
        h = g.height
        r = r.resize((max(1, int(r.width * h / r.height)), h), Image.LANCZOS)
        out = Image.new('RGB', (r.width + g.width + 12, h + 28), (24, 22, 20))
        out.paste(r, (0, 28)); out.paste(g, (r.width + 12, 28))
        d = ImageDraw.Draw(out)
        d.text((8, 8), 'REFERENCE ' + label, fill=(235, 220, 190))
        d.text((r.width + 20, 8), 'IN-GAME (city camera) ' + prefix + name, fill=(235, 220, 190))
        dst = os.path.join(shots, prefix + 'compare_' + name + '.png')
        out.save(dst)
        print(dst)
if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
