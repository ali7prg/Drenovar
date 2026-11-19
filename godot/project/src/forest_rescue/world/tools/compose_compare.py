#!/usr/bin/env python3
"""Reference | in-game comparison sheets for the world layer (city camera, matched scale).

usage: compose_compare.py <shots_dir> <prefix> [--art01-ppm 11]
Reads <prefix>shots.json (written by qa_forest_world_shots.gd: zoom + px/m per view) and writes
<prefix>compare_<view>.png for every view that has a reference below.

Scale matching: in-game px/m = viewport height / zoom (ortho size = zoom). art/01 is drawn at
~11 px/m (native) in the city camera's orientation, so an art/01 crop is resized by
(game px/m) / 11 before it is placed next to the screenshot (zoom 68 -> x0.84, zoom 40 -> x1.43).
Panel references (art/07, art/18, art/08) are composition references: shown at the same height.
"""
import json
import os
import sys

from PIL import Image, ImageDraw

ART = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../../../forest_rescue/delivery/art'))
ART01 = '01_world_masterplan.png'
# art/01 region centres (painting px, city-camera orientation: screen-up = world (-X,-Z)).
REGIONS = {
    'grove': (300, 230), 'top_birch': (640, 170), 'quarry': (240, 730), 'spruce': (690, 850),
    'river_bridge': (1110, 560), 'east': (1290, 520), 'arena': (1240, 160), 'town': (745, 440),
}
# view -> (reference file, crop box or None, label, mode) ; mode 'scale' = art/01 matched scale
PANELS = {
    'locked_town_z68': ('18_hall3_unlock_intro.png', (8, 8, 508, 1010), 'art/18 panel 1 (hall I-II: forest cloaked)'),
    'locked_town_z40': ('18_hall3_unlock_intro.png', (8, 200, 508, 760), 'art/18 panel 1 (town + fog banks)'),
    'locked_overview_z130': ('18_hall3_unlock_intro.png', (8, 8, 508, 1010), 'art/18 panel 1 (locked overview)'),
    'unlocked_entrance_z68': ('18_hall3_unlock_intro.png', (520, 8, 1018, 1010), 'art/18 panel 2 (hall III: entrance opens)'),
    'entrance_reveal_2': ('18_hall3_unlock_intro.png', (520, 200, 1018, 760), 'art/18 panel 2 (corridor reveal)'),
    'unlocked_horse_z30': ('18_hall3_unlock_intro.png', (1030, 8, 1528, 1010), 'art/18 panel 3 (the horse)'),
    'entrance_corridor_z46': ('18_hall3_unlock_intro.png', (520, 8, 1018, 1010), 'art/18 panel 2 (entrance corridor)'),
    'partial_squad_z40': ('07_fog_exploration_interface.png', (8, 8, 508, 875), 'art/07 panel 1 (squad enters the fog)'),
    'partial_path_z40': ('07_fog_exploration_interface.png', (520, 8, 1020, 875), 'art/07 panel 2 (revealed path)'),
    'partial_edge_z68': ('07_fog_exploration_interface.png', (1032, 8, 1530, 875), 'art/07 panel 3 (fog edge)'),
    'partial_overview_z130': (ART01, None, 'art/01 masterplan (fog at the edges)'),
    'full_overview_z120': (ART01, None, 'art/01 masterplan'),
    'full_overview_z140': (ART01, None, 'art/01 masterplan'),
    'partial_edge_z68_art07p1': ('07_fog_exploration_interface.png', (8, 8, 508, 875), 'art/07 panel 1'),
    'full_arena_z40': ('08_final_boss_arena.png', (0, 0, 1536, 715), 'art/08 arena'),
}


def label(img, text, xy):
    d = ImageDraw.Draw(img)
    w = 7 * len(text) + 10
    d.rectangle([xy[0] - 4, xy[1] - 3, xy[0] + w, xy[1] + 14], fill=(16, 14, 12))
    d.text(xy, text, fill=(240, 226, 196))


def art01_crop(region, zoom, game_h, game_w, ppm):
    art = Image.open(os.path.join(ART, ART01)).convert('RGB')
    game_ppm = game_h / zoom
    h = min(art.height, int(round(game_h * ppm / game_ppm)))
    w = min(art.width, int(round(game_w * ppm / game_ppm)))
    cx, cy = REGIONS[region]
    x0 = max(0, min(art.width - w, cx - w // 2))
    y0 = max(0, min(art.height - h, cy - h // 2))
    crop = art.crop((x0, y0, x0 + w, y0 + h))
    s = game_ppm / ppm
    return crop.resize((max(1, int(crop.width * s)), max(1, int(crop.height * s))), Image.LANCZOS), s


def sheet(left, right, left_label, right_label, out):
    h = max(left.height, right.height)
    canvas = Image.new('RGB', (left.width + right.width + 12, h + 24), (24, 22, 20))
    canvas.paste(left, (0, 24))
    canvas.paste(right, (left.width + 12, 24))
    label(canvas, left_label, (8, 5))
    label(canvas, right_label, (left.width + 20, 5))
    canvas.save(out)
    print(out)


def main(shots, prefix, ppm=11.0):
    meta_path = os.path.join(shots, prefix + 'shots.json')
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    for view in sorted(set(list(meta.keys()) + list(PANELS.keys()))):
        game_path = os.path.join(shots, prefix + view + '.png')
        if not os.path.exists(game_path):
            continue
        game = Image.open(game_path).convert('RGB')
        zoom = float(meta.get(view, {}).get('zoom', 68.0))
        out = os.path.join(shots, prefix + 'compare_' + view + '.png')
        region = None
        if view.startswith('full_'):
            key = view[5:].rsplit('_z', 1)[0]
            region = key if key in REGIONS else None
        if region is not None:
            crop, s = art01_crop(region, zoom, game.height, game.width, ppm)
            sheet(crop, game, 'REFERENCE art/01 %s, scale-matched (x%.2f of native ~%g px/m)' % (region, s, ppm),
                  'IN-GAME city camera zoom %g (%.1f px/m) %s' % (zoom, game.height / zoom, prefix + view), out)
        if view in PANELS:
            ref, box, text = PANELS[view]
            art = Image.open(os.path.join(ART, ref)).convert('RGB')
            if box:
                art = art.crop(box)
            art = art.resize((max(1, int(art.width * game.height / art.height)), game.height), Image.LANCZOS)
            target = out if region is None else out.replace('compare_', 'compare_panel_')
            sheet(art, game, 'REFERENCE ' + text, 'IN-GAME city camera zoom %g %s' % (zoom, prefix + view), target)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    ppm = 11.0
    for a in sys.argv[1:]:
        if a.startswith('--art01-ppm='):
            ppm = float(a.split('=', 1)[1])
    main(args[0], args[1], ppm)
