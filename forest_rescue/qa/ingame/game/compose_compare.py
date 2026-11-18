#!/usr/bin/env python3
"""Side-by-side [reference panel | in-game shot] sheets for the «Лес потерянных» gameplay QA.
Usage: python3 compose_compare.py <iter prefix, e.g. iter02>  (run from any directory)."""
import os, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, '..', '..', '..', 'delivery', 'art')
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
# reference file, crop box (left, top, right, bottom) in source pixels, caption
REFS = {
    'locked_card': ('18_hall3_unlock_intro.png', (0, 0, 512, 1024), 'art/18 left: locked card'),
    'intro_banner': ('18_hall3_unlock_intro.png', (512, 0, 1024, 1024), 'art/18 centre: banner'),
    'intro_horse': ('18_hall3_unlock_intro.png', (1024, 0, 1536, 1024), 'art/18 right: horse prompt'),
    'intro_prompt': ('18_hall3_unlock_intro.png', (1024, 0, 1536, 1024), 'art/18 right: horse prompt'),
    'hud_forest': ('07_fog_exploration_interface.png', (0, 0, 1536, 1024), 'art/07: fog exploration + HUD row'),
    'route_moving': ('rescue_animation_storyboard.png', (0, 0, 1672, 320), 'storyboard 1: GUIDE'),
    'mech_trail': ('10_artifact_mechanisms.png', (0, 60, 760, 500), 'art/10: trail cache'),
    'mech_rune': ('10_artifact_mechanisms.png', (770, 60, 1536, 500), 'art/10: rune lock'),
    'mech_winch': ('10_artifact_mechanisms.png', (0, 505, 740, 1024), 'art/10: winch'),
    'mech_paired': ('10_artifact_mechanisms.png', (740, 505, 1536, 1024), 'art/10: paired latch'),
    'guardian_battle': ('rescue_animation_storyboard.png', (770, 320, 1672, 625), 'storyboard 3: GUARDIAN'),
    'cage_unlock_key': ('rescue_animation_storyboard.png', (0, 625, 768, 941), 'storyboard 4: UNLOCK'),
    'cage_open_exit': ('12_civilian_rescue_motion.png', (440, 620, 780, 1024), 'art/12: exit through the door'),
    'escort_home': ('rescue_animation_storyboard.png', (770, 625, 1672, 941), 'storyboard 5: ESCORT'),
    'boss_telegraph_10': ('05_boss_motion_keyposes.png', None, 'art/05 boss key poses'),
    'boss_telegraph_35': ('08_final_boss_arena.png', None, 'art/08 boss arena'),
    'boss_telegraph_60': ('05_boss_motion_keyposes.png', None, 'art/05 boss key poses'),
    'boss_telegraph_85': ('08_final_boss_arena.png', None, 'art/08 boss arena'),
}

def sheet(prefix, name):
    shot = os.path.join(HERE, f'{prefix}_{name}.png')
    if not os.path.exists(shot) or name not in REFS:
        return None
    ref_file, box, caption = REFS[name]
    ref = Image.open(os.path.join(ART, ref_file)).convert('RGB')
    if box:
        ref = ref.crop(box)
    game = Image.open(shot).convert('RGB')
    h = game.height
    ref = ref.resize((max(1, int(ref.width * h / ref.height)), h), Image.LANCZOS)
    out = Image.new('RGB', (ref.width + game.width + 12, h + 34), (24, 22, 20))
    out.paste(ref, (0, 34))
    out.paste(game, (ref.width + 12, 34))
    draw = ImageDraw.Draw(out)
    font = ImageFont.truetype(FONT, 18)
    draw.text((8, 7), 'REFERENCE · ' + caption, fill=(235, 205, 140), font=font)
    draw.text((ref.width + 20, 7), f'IN-GAME · {prefix}_{name} (DRENOVAR city camera)', fill=(235, 205, 140), font=font)
    path = os.path.join(HERE, f'{prefix}_compare_{name}.png')
    out.save(path, optimize=True)
    return path

if __name__ == '__main__':
    prefix = sys.argv[1]
    for name in REFS:
        made = sheet(prefix, name)
        if made:
            print(made)
