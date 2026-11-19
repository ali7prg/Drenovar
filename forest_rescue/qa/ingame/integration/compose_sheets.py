#!/usr/bin/env python3
"""Reference crop | in-game shot comparison sheets for the «Лес потерянных» asset integration.

Every in-game image is a frame of the real client from the DRENOVAR city camera (ortho,
size = zoom, target + (75, 83, 75), 38°), rendered by qa_forest_integration_shots.gd (fixtures
through a stub transport) or cut from the local-realm slice movies. The game crop is scaled so the
compared subject has about the same on-sheet size as in the painting (zoom noted per sheet).

    python3 forest_rescue/qa/ingame/integration/compose_sheets.py <shots dir> [names...]
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.abspath(os.path.join(HERE, "..", "..", "..", "delivery", "art"))
OUT = os.path.join(HERE, "sheets")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
HEIGHT = 560

# name: (reference file, ref crop, caption, [(shot file, game crop or None, caption), ...])
SHEETS = {
    "art18_p1_locked_fog": ("18_hall3_unlock_intro.png", (0, 0, 512, 1024), "art/18 panel 1 — hall I–II: fog beyond the walls, locked card",
                            [("a_locked.png", (300, 0, 1066, 630), "hall II, zoom 68: fog, locked card")]),
    "art18_p2_unlock": ("18_hall3_unlock_intro.png", (512, 0, 1024, 1024), "art/18 panel 2 — «Лес потерянных открыт»",
                        [("a_unlock.png", (300, 0, 1066, 630), "hall III reached: banner, hall glow")]),
    "art18_p3_horse": ("18_hall3_unlock_intro.png", (1024, 0, 1536, 1024), "art/18 panel 3 — Iskra walks out of the mist",
                       [("a_horse.png", (450, 120, 900, 630), "corridor opens, the mare walks out (intro, zoom 40)"),
                        ("intro_horse_z12.png", (383, 0, 983, 630), "same moment up close (zoom 12)"),
                        ("a_prompt.png", (300, 0, 1066, 630), "prompt «Следовать за лошадью»")]),
    "art07_p1_entering": ("07_fog_exploration_interface.png", (0, 0, 506, 1024), "art/07 panel 1 — squad + mare enter, fog wall",
                          [("b_entering.png", (380, 60, 900, 630), "route entry, zoom 34: squad follows the mare")]),
    "art07_p2_path": ("07_fog_exploration_interface.png", (512, 0, 1018, 1024), "art/07 panel 2 — revealed path, camp + cage, seal glow",
                      [("b_path.png", (420, 0, 940, 630), "path revealed behind the squad, fog ahead")]),
    "art07_p3_edge": ("07_fog_exploration_interface.png", (1024, 0, 1536, 1024), "art/07 panel 3 — fog edge, camp with the cage",
                      [("b_edge.png", (420, 0, 940, 630), "site 1 glade at the fog edge, cage + camp")]),
    "story3_guardian": ("rescue_animation_storyboard.png", (775, 325, 1672, 625), "storyboard 3 — guardian battle",
                        [("battle_z30_1.png", (283, 120, 1083, 470), "Tenerys L1 (original model) vs the squad, zoom 30")]),
    "story4_unlock": ("rescue_animation_storyboard.png", (0, 630, 770, 941), "storyboard 4 — soldier sets the seal, gate opens",
                      [("unlock_01.9s.png", (433, 110, 933, 420), "lf_soldier_unlock → latch_release → gate (zoom 12)")]),
    "art12_exit": ("12_civilian_rescue_motion.png", (0, 330, 1536, 1024), "art/12 — sit → stand_up → exit through the door",
                   [("unlock_06.2s.png", (433, 110, 933, 420), "seated captive stands up"), ("unlock_08.2s.png", (433, 110, 933, 420), "exit through the door")]),
    "story5_escort": ("rescue_animation_storyboard.png", (775, 630, 1672, 941), "storyboard 5 — escort home",
                      [("escort_z30.png", (283, 120, 1083, 470), "escort: follow / follow_tired, zoom 30")]),
    "art10_trail": ("10_artifact_mechanisms.png", (0, 60, 760, 500), "art/10 — trail cache",
                    [("mech_trail_close.png", (433, 90, 933, 430), "trail cache (lid, marks), zoom 9")]),
    "art10_rune": ("10_artifact_mechanisms.png", (770, 60, 1536, 500), "art/10 — rune lock",
                   [("mech_rune_close.png", (433, 90, 933, 430), "rune lock, ring 1 set, zoom 9")]),
    "art10_winch": ("10_artifact_mechanisms.png", (0, 505, 740, 1024), "art/10 — winch",
                    [("mech_winch_close.png", (433, 90, 933, 430), "winch solved: chest raised, seal revealed")]),
    "art10_paired": ("10_artifact_mechanisms.png", (740, 505, 1536, 1024), "art/10 — paired latch",
                     [("mech_paired_close.png", (433, 90, 933, 430), "two soldiers on the plates, zoom 9")]),
    "art08_boss": ("08_final_boss_arena.png", (0, 0, 1536, 760), "art/08 — the boss fight, orange arcs",
                   [("tele_tail_sweep_active.png", (183, 60, 1183, 560), "tail sweep active, zoom 34"),
                    ("tele_jaw_arc_warn.png", (183, 60, 1183, 560), "jaw arc telegraph")]),
    "art01_overview": ("01_world_masterplan.png", (0, 0, 1536, 1024), "art/01 — masterplan overview",
                       [("overview_z130.png", None, "completed campaign, zoom 130")]),
}


def label(draw, xy, text, font):
    x, y = xy
    w = draw.textlength(text, font=font)
    draw.rectangle([x - 4, y - 2, x + w + 6, y + 21], fill=(20, 18, 16))
    draw.text((x, y), text, fill=(235, 205, 140), font=font)


def compose(shots, name):
    ref_file, box, caption, games = SHEETS[name]
    ref = Image.open(os.path.join(ART, ref_file)).convert("RGB")
    if box:
        ref = ref.crop(box)
    tiles = [(ref.resize((max(1, int(ref.width * HEIGHT / ref.height)), HEIGHT), Image.LANCZOS), "REFERENCE · " + caption)]
    for shot, crop, cap in games:
        path = os.path.join(shots, shot)
        if not os.path.exists(path):
            print("missing", path)
            return None
        im = Image.open(path).convert("RGB")
        if crop:
            im = im.crop(crop)
        tiles.append((im.resize((max(1, int(im.width * HEIGHT / im.height)), HEIGHT), Image.LANCZOS), "IN-GAME · " + cap))
    width = sum(t[0].width for t in tiles) + 10 * (len(tiles) - 1)
    sheet = Image.new("RGB", (width, HEIGHT), (22, 20, 18))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(FONT, 17)
    x = 0
    for im, cap in tiles:
        sheet.paste(im, (x, 0))
        label(draw, (x + 8, 6), cap, font)
        x += im.width + 10
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, name + ".png")
    sheet.save(out, optimize=True)
    return out


if __name__ == "__main__":
    shots = sys.argv[1]
    for name in (sys.argv[2:] or SHEETS.keys()):
        made = compose(shots, name)
        if made:
            print(made)
