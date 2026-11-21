#!/usr/bin/env python3
"""Atlas v2 evidence sheets: the in-game world (QA full reveal, the real DRENOVAR city camera) next to
art/01 seen through the SAME camera frame.

art/01 is a painting of the masterplan from the city camera; atlas v2 was laid out by warping it onto the
game's screen with a thin-plate spline (forest_rescue/tools/plan_atlas_v2.py: town wall ↔ base ±56, river,
bridge, content border ↔ playable square). The same warp (inverted) maps every pixel of a game frame back to
the painting, so each sheet shows the painting resampled into the game frame beside the game frame itself
(and the overview also the other way round: the game frame resampled into the painting's framing).

    /opt/tools/blender-venv/bin/python forest_rescue/qa/ingame/integration/compose_v2.py <shots dir> <prefix>

Inputs: qa_forest_world_shots.gd frames <prefix>full_overview_z140.png and <prefix>full_<zone>_z68.png
(1366×630, target (x, 0, z), ortho size = zoom). Output: sheets/v2/.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "forest_rescue", "tools"))
import plan_atlas_v2 as P  # noqa: E402

ART = os.path.join(ROOT, "forest_rescue", "delivery", "art", "01_world_masterplan.png")
OUT = os.path.join(HERE, "sheets", "v2")
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W, H = 1366, 630

ZONES = [  # name, target xz, caption (art/01 region, masterplan_inventory.json)
    ("grove", (-84, -16), "golden-oak grove, glade 01 (NW-A) with birches, hollow oak"),
    ("stones", (-56, -70), "standing stones on the mare's trail above the town"),
    ("west", (-76, 52), "west: golden + green oaks, glades 02 / 03, ruined arch"),
    ("quarry", (-8, 94), "SW quarry: mine, ledges, glade 05 (SW-E)"),
    ("south_pines", (62, 92), "dark pines: glade 07 (S-G), dead tree, marsh pools"),
    ("lake", (94, 44), "reedy lake, glade 09 (SE-I), hunter shelter"),
    ("river_bridge", (88, 16), "the bridge (four towers, red banners)"),
    ("east", (94, -40), "east bank willows: glades 10 / 11 (SE-J, E-K)"),
    ("waterfall", (22, -66), "waterfall into the lily pond below the arena"),
    ("arena", (20, -88), "the arena on its outcrop, glade E-L, glade 12 (NE-M)"),
]


def font(size):
    return ImageFont.truetype(BOLD, size)


def label(img, text, xy=(8, 6), size=17):
    d = ImageDraw.Draw(img)
    f = font(size)
    box = d.textbbox(xy, text, font=f)
    d.rectangle((box[0] - 5, box[1] - 3, box[2] + 5, box[3] + 4), fill=(18, 16, 14))
    d.text(xy, text, font=f, fill=(255, 236, 190))


def frame_screen(target, zoom):
    """(u, Y) game-screen coordinates of every pixel centre of a W×H frame."""
    tx, tz = target
    u0, y0 = P.to_screen(tx, tz, h=0.0)
    s = zoom / H
    xs = (np.arange(W) + 0.5 - W / 2) * s + u0
    ys = (np.arange(H) + 0.5 - H / 2) * s + y0
    return xs, ys


def sample(img, px, py):
    """Bilinear sample of an RGB image (numpy float) at fractional pixel coords (outside → dark)."""
    h, w, _ = img.shape
    x0 = np.floor(px).astype(int)
    y0 = np.floor(py).astype(int)
    fx = (px - x0)[..., None]
    fy = (py - y0)[..., None]
    inside = (x0 >= 0) & (y0 >= 0) & (x0 < w - 1) & (y0 < h - 1)
    x0c = np.clip(x0, 0, w - 2)
    y0c = np.clip(y0, 0, h - 2)
    a = img[y0c, x0c]
    b = img[y0c, x0c + 1]
    c = img[y0c + 1, x0c]
    d = img[y0c + 1, x0c + 1]
    out = (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy
    out[~inside] = (30, 27, 24)
    return out


def art_crop(art_img, inv, target, zoom, size):
    """Rectangular art/01 crop with the frame's aspect, centred where the warp puts the frame centre
    and scaled by the warp's local magnification (no resampling distortion)."""
    u0, y0 = P.to_screen(target[0], target[1], h=0.0)
    centre = inv(np.array([[u0, y0]]))[0]
    e = 2.0
    ju = (inv(np.array([[u0 + e, y0]]))[0] - inv(np.array([[u0 - e, y0]]))[0]) / (2 * e)
    jy = (inv(np.array([[u0, y0 + e]]))[0] - inv(np.array([[u0, y0 - e]]))[0]) / (2 * e)
    s = zoom / H
    half_h = 0.5 * H * s * float(np.linalg.norm(jy))
    half_w = 0.5 * W * s * float(np.linalg.norm(ju))
    # keep the frame aspect (mean magnification); near the map edge the warp stretches strongly,
    # so the crop is capped at the median scale of the inner forest (≈ 3.6 art px per m)
    hh = 0.5 * (half_h + half_w * H / W)
    hh = min(hh, 0.5 * H * s * 3.6)
    hw = hh * W / H
    box = (int(centre[0] - hw), int(centre[1] - hh), int(centre[0] + hw), int(centre[1] + hh))
    canvas = Image.new("RGB", (box[2] - box[0], box[3] - box[1]), (30, 27, 24))
    clip = (max(0, box[0]), max(0, box[1]), min(art_img.width, box[2]), min(art_img.height, box[3]))
    if clip[2] > clip[0] and clip[3] > clip[1]:
        canvas.paste(art_img.crop(clip), (clip[0] - box[0], clip[1] - box[1]))
    return canvas.resize(size, Image.LANCZOS), box


def art_in_frame(art, inv, target, zoom, step=6):
    """art/01 resampled into the game frame (target, zoom) through the inverse warp."""
    xs, ys = frame_screen(target, zoom)
    gx = xs[::step]
    gy = ys[::step]
    grid = np.array([[u, y] for y in gy for u in gx])
    mapped = inv(grid).reshape(len(gy), len(gx), 2)
    # upsample the coarse map bilinearly to every pixel
    fx = (np.arange(W) / step)
    fy = (np.arange(H) / step)
    ix = np.clip(np.floor(fx).astype(int), 0, len(gx) - 2)
    iy = np.clip(np.floor(fy).astype(int), 0, len(gy) - 2)
    tx = (fx - ix)[None, :, None]
    ty = (fy - iy)[:, None, None]
    m00 = mapped[iy][:, ix]
    m01 = mapped[iy][:, ix + 1]
    m10 = mapped[iy + 1][:, ix]
    m11 = mapped[iy + 1][:, ix + 1]
    full = (m00 * (1 - tx) + m01 * tx) * (1 - ty) + (m10 * (1 - tx) + m11 * tx) * ty
    return Image.fromarray(sample(art, full[..., 0], full[..., 1]).astype(np.uint8))


def game_in_art(game, fwd, target, zoom, size=(1536, 1024), step=6):
    """A game frame resampled into the painting's framing through the forward warp."""
    aw, ah = size
    gx = np.arange(0, aw + step, step, dtype=float)
    gy = np.arange(0, ah + step, step, dtype=float)
    grid = np.array([[x, y] for y in gy for x in gx])
    scr = fwd(grid).reshape(len(gy), len(gx), 2)
    u0, y0 = P.to_screen(target[0], target[1], h=0.0)
    s = H / zoom
    px = (scr[..., 0] - u0) * s + W / 2 - 0.5
    py = (scr[..., 1] - y0) * s + H / 2 - 0.5
    coarse = np.stack([px, py], -1)
    fx = np.arange(aw) / step
    fy = np.arange(ah) / step
    ix = np.clip(np.floor(fx).astype(int), 0, len(gx) - 2)
    iy = np.clip(np.floor(fy).astype(int), 0, len(gy) - 2)
    tx = (fx - ix)[None, :, None]
    ty = (fy - iy)[:, None, None]
    m = coarse
    full = (m[iy][:, ix] * (1 - tx) + m[iy][:, ix + 1] * tx) * (1 - ty) + (m[iy + 1][:, ix] * (1 - tx) + m[iy + 1][:, ix + 1] * tx) * ty
    return Image.fromarray(sample(game, full[..., 0], full[..., 1]).astype(np.uint8))


def main():
    shots, prefix = sys.argv[1], sys.argv[2]
    os.makedirs(OUT, exist_ok=True)
    art_img = Image.open(ART).convert("RGB")
    art = np.asarray(art_img).astype(float)
    fwd, inv = P.art_warps()
    report = {}
    # ---- overview in the painting's framing (1536 × 1024, town where art/01 has it) ------------
    framed = os.path.join(shots, prefix + "full_overview_art01.png")
    if os.path.exists(framed):
        game = Image.open(framed).convert("RGB").resize((1536, 1024), Image.LANCZOS)
        ref = art_img.copy()
        label(ref, "art/01 masterplan", size=22)
        g = game.copy()
        label(g, "in game · QA full reveal · city camera, zoom 195, town placed as in art/01", size=22)
        pair = Image.new("RGB", (1536 * 2 + 12, 1024 + 56), (30, 27, 24))
        ImageDraw.Draw(pair).text((10, 12), "Atlas v2 vs art/01 — the whole forest, same framing (the painting enlarges "
                                  "the walled town ~1.7×; the forest square ±112 fills both frames)", font=font(22),
                                  fill=(250, 240, 220))
        pair.paste(ref, (0, 52))
        pair.paste(g, (1536 + 12, 52))
        pair.save(os.path.join(OUT, "v2_overview_same_framing.png"))
        report["overview_same_framing"] = True
    # ---- overview: the painting warped into the game frame (diagnostic of the TPS) ------------
    over_path = os.path.join(shots, prefix + "full_overview_z140.png")
    if os.path.exists(over_path):
        game = Image.open(over_path).convert("RGB")
        target, zoom = (0.0, 0.0), 140.0
        a = art_in_frame(art, inv, target, zoom)
        label(a, "art/01 through the game camera (TPS of atlas v2), zoom 140")
        g = game.copy()
        label(g, "in game · QA full reveal · city camera zoom 140")
        sheet = Image.new("RGB", (W, 2 * H + 54), (30, 27, 24))
        ImageDraw.Draw(sheet).text((10, 12), "Atlas v2 vs art/01 — overview, same camera frame (top: painting warped "
                                   "into the frame, bottom: the game)", font=font(20), fill=(250, 240, 220))
        sheet.paste(a, (0, 50))
        sheet.paste(g, (0, 54 + H))
        sheet.save(os.path.join(OUT, "v2_overview_tps_frame.png"))
        report["overview_tps"] = True
    # ---- per zone at zoom 68 ----------------------------------------------------------------
    rows = []
    for name, target, caption in ZONES:
        path = os.path.join(shots, prefix + "full_%s_z68.png" % name)
        if not os.path.exists(path):
            continue
        game = Image.open(path).convert("RGB")
        a, box = art_crop(art_img, inv, target, 68.0, (W, H))
        label(a, "art/01 crop %s · %s" % (str(box), caption), size=15)
        g = game.copy()
        label(g, "in game · zoom 68 · " + name, size=15)
        rows.append((name, a, g))
    if rows:
        scale = 0.62
        tw, th = int(W * scale), int(H * scale)
        for chunk in range(0, len(rows), 5):
            part = rows[chunk:chunk + 5]
            sheet = Image.new("RGB", (2 * tw + 12, 50 + len(part) * (th + 8)), (30, 27, 24))
            ImageDraw.Draw(sheet).text((10, 12), "Atlas v2 per region at zoom 68 — art/01 crop at the warped frame centre and "
                                       "scale | in game (QA full reveal)", font=font(19), fill=(250, 240, 220))
            for i, (name, a, g) in enumerate(part):
                y = 50 + i * (th + 8)
                sheet.paste(a.resize((tw, th), Image.LANCZOS), (0, y))
                sheet.paste(g.resize((tw, th), Image.LANCZOS), (tw + 12, y))
            sheet.save(os.path.join(OUT, "v2_zones_z68_%d.png" % (chunk // 5 + 1)))
        report["zones"] = [r[0] for r in rows]
    print(json.dumps(report))


if __name__ == "__main__":
    main()
