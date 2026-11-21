#!/usr/bin/env python3
"""Before / after sheets for the checkpoint-2 P0 fixes (same fixtures, same camera, same zoom):

  p0_1_dither_crops.png   400 % crops where the old frames had the Bayer screen-door pattern
                          (canopy fade + fog cover + impostor fade), FFT peak ratio printed per crop
  p0_2_crowns_*.png       crown cut-away ("brown mushrooms") → whole trees, trails/glades kept clear
                          for the camera, remaining occluders faded whole (≥ 0.35)
  p0_3_fog_*.png          veil / haze over revealed ground → clean revealed cells, soft 2.5 m edge,
                          opaque fog beyond

Shots: qa_forest_integration_shots.gd --shots=p0 rendered once with the pre-P0 sources (before/)
and once with the current sources (after/); *_nohud copies feed the FFT check.

    python3 forest_rescue/qa/ingame/integration/compose_p0.py <before dir> <after dir>
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "tools")))
import dither_check  # noqa: E402

OUT = os.path.join(HERE, "sheets", "p0")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def label(img, text, xy=(8, 6), size=17, fill=(255, 236, 190)):
    d = ImageDraw.Draw(img)
    f = font(size, True)
    box = d.textbbox(xy, text, font=f)
    d.rectangle((box[0] - 5, box[1] - 3, box[2] + 5, box[3] + 4), fill=(18, 16, 14))
    d.text(xy, text, font=f, fill=fill)


def pair_sheet(name, title, rows, before, after, crop=None, scale=0.62):
    """rows: [(shot name, caption)] → each row: BEFORE | AFTER (full frame or crop)."""
    tiles = []
    for shot, caption in rows:
        a = Image.open(os.path.join(before, shot + ".png")).convert("RGB")
        b = Image.open(os.path.join(after, shot + ".png")).convert("RGB")
        if crop:
            a, b = a.crop(crop), b.crop(crop)
        w, h = int(a.width * scale), int(a.height * scale)
        a, b = a.resize((w, h), Image.LANCZOS), b.resize((w, h), Image.LANCZOS)
        label(a, "BEFORE · " + caption)
        label(b, "AFTER · " + caption)
        tiles.append((a, b))
    w, h = tiles[0][0].size
    sheet = Image.new("RGB", (w * 2 + 12, 46 + len(tiles) * (h + 8)), (30, 27, 24))
    ImageDraw.Draw(sheet).text((10, 10), title, font=font(20, True), fill=(250, 240, 220))
    for i, (a, b) in enumerate(tiles):
        y = 46 + i * (h + 8)
        sheet.paste(a, (0, y))
        sheet.paste(b, (w + 12, y))
    path = os.path.join(OUT, name + ".png")
    sheet.save(path)
    print("sheet", path, sheet.size)


def dither_sheet(before, after):
    # (shot, zoom caption): crop centred on the worst before-tile (where the dots were), 128 px → 400 %
    cases = [("p0_site01_z24", "zoom 24 · site 1 (mechanism UI zoom)"), ("p0_route_z34", "zoom 34 · route entry"),
             ("p0_escort_z34", "zoom 34 · escort"), ("p0_horse_z68", "zoom 68 · default"),
             ("p0_horse_z120", "zoom 120 · overview")]
    rows = []
    lines = []
    for shot, caption in cases:
        bpath = os.path.join(before, shot + "_nohud.png")
        apath = os.path.join(after, shot + "_nohud.png")
        v_b, at, peaks_b = dither_check.scan(bpath)
        x, y = at
        box = (x, y, x + 128, y + 128)
        peaks_a, v_a = dither_check.check(apath, box, 128)
        v_aw, at_a, _ = dither_check.scan(apath)
        crops = []
        for path, v, tag in ((bpath, v_b, "BEFORE"), (apath, v_a, "AFTER")):
            c = Image.open(path).convert("RGB").crop(box).resize((512, 512), Image.NEAREST)
            label(c, "%s · %s" % (tag, caption), size=14)
            label(c, "FFT peak %.1f (%s)" % (v, "dots" if v > 6.0 else "clean"), xy=(8, 486), size=14,
                  fill=(255, 150, 120) if v > 6.0 else (170, 240, 170))
            crops.append(c)
        rows.append(crops)
        lines.append("%-14s before worst %.1f at %s | after same crop %.1f, after worst tile %.1f at %s"
                     % (shot, v_b, at, v_a, v_aw, at_a))
    sheet = Image.new("RGB", (len(rows) * 516 + 4, 2 * 516 + 60), (30, 27, 24))
    d = ImageDraw.Draw(sheet)
    d.text((10, 10), "P0.1 screen-door dither — 400 % crops at the worst before-tile, FFT of the high-passed crop "
           "(4-px / 2-px period peak ratio; > 6 = periodic dots)", font=font(18, True), fill=(250, 240, 220))
    for i, (a, b) in enumerate(rows):
        sheet.paste(a, (4 + i * 516, 50))
        sheet.paste(b, (4 + i * 516, 50 + 516))
    path = os.path.join(OUT, "p0_1_dither_crops.png")
    sheet.save(path)
    print("sheet", path, sheet.size)
    print("\n".join(lines))


def main():
    before, after = sys.argv[1], sys.argv[2]
    os.makedirs(OUT, exist_ok=True)
    dither_sheet(before, after)
    pair_sheet("p0_2_crowns_close", "P0.2 crown cut-away → whole trees (z12 close-ups at the actors)",
               [("p0_horse_z12", "mare + squad at the horse origin, zoom 12"),
                ("p0_route_z12", "squad walking to the mare, zoom 12"),
                ("p0_escort_z12", "escort on the trail, zoom 12")], before, after, crop=(183, 0, 1183, 470), scale=0.62)
    pair_sheet("p0_2_crowns_play", "P0.2 crown cut-away → whole trees, trails / glades open for the camera (playable zooms)",
               [("p0_horse_z24", "horse origin, zoom 24"), ("p0_route_z34", "route entry, zoom 34"),
                ("p0_site01_z24", "site 1 glade, zoom 24"), ("p0_escort_z34", "escort, zoom 34")],
               before, after, crop=(183, 0, 1183, 470), scale=0.62)
    pair_sheet("p0_3_fog_edge", "P0.3 revealed cells clean (no veil / haze), soft 2.5 m edge, opaque fog beyond",
               [("p0_escort_z34", "escort beside the fog edge, zoom 34"), ("p0_site01_z34", "site 1 at the fog edge, zoom 34"),
                ("p0_escort_z68", "escort, default zoom 68"), ("p0_route_z68", "route entry, zoom 68")],
               before, after, crop=(183, 0, 1366, 470), scale=0.55)
    pair_sheet("p0_overview_z120", "Overview zoom 120 (QA projection 'completed') — trees whole, no dots",
               [("p0_overview_z120", "zoom 120"), ("p0_horse_z120", "horse origin, zoom 120")],
               before, after, crop=(0, 0, 1366, 520), scale=0.55)


if __name__ == "__main__":
    main()
