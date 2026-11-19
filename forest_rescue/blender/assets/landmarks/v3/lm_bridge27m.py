"""lf_env_bridge27m v3 — timber trestle bridge (art/06) with the art/01 gate: 4 stone tower piers with red
banners and timber arch ribs over the clear water channel.

Engineering (data/world-atlas.json, ART_PRODUCTION_RU §4): deck 27 x 4 m, deck top +1.1 (local), long axis +X
(west -> east 77..104), wet banks x = -6.317 / +6.287 -> NO support for |x| < 6.6; supports on the banks:
abutments at |x| = 13.5, bank piers at |x| = 10.4, tower piers at |x| = 7.25 (inner faces 6.6).
Blender axes: +X east, +Y north (glTF -Z), Z up. Origin = bridge centre on the world datum (y=0).
"""
import json
import math
import os

import numpy as np

from geo import Geo, rot_z, rot_x, frame_from

ID = "lf_env_bridge27m"
MAIN_BOX = (0, 0, 588, 266)
BUDGET0 = 8000
ATLAS = 2048
DECK = 1.1
HL = 13.5
HW = 2.0
WATER = -1.35
POST_Y = 2.1
POST_TOP = 2.25
TOWER_X = 7.25
TOWER_Y = 2.95
TOWER_W = 1.3
BANK_PIER_X = 10.4
ABUT_X = 13.5
RAMP_END = 16.7
BANK_Z = 0.45
MAIN_POST_X = [-13.5 + 4.5 * k for k in range(7)]
MASK_THRESH = 0.09

# painted correspondences (art/06 sheet px): main railing post tops, near (south, y=-2.1) and far (north)
NEAR = [(94, 121), (166, 93), (270, 65), (353, 50), (413, 37), (471, 27), (540, 17)]
FAR = [(37, 77), (104, 58), (193, 42), (267, 31), (331, 22), (382, 16), (458, 8)]
# far post feet on the deck (z = deck top, y = +2.0)
FAR_FOOT = {1: (104, 100), 2: (193, 77), 4: (331, 48), 5: (383, 38), 6: (458, 27)}

INSETS = {
    "side": dict(box=(592, 30, 822, 74), dir=(0, 1, 0), fit="width"),
    "top": dict(box=(592, 98, 822, 144), dir=(0, 0, -1), fit="width"),
}

NO_PROJECT_TAGS = ("tower", "cornice", "cap", "gatepier", "finial", "banner", "niche", "post_cap")
TAG_SWATCH = {"deck": "plank", "ramp": "plank", "subdeck": "plank", "rail": "wood_h", "stringer": "wood_h",
              "fascia": "wood_h", "capbeam": "wood_h", "arch": "wood_h", "tie": "wood_h", "brace": "wood_h",
              "knee": "wood_h", "tower": "stone_face", "cornice": "stone_face", "gatepier": "stone_face",
              "pier": "stone_face", "abut": "stone_face", "wing": "stone_face", "cap": "stone_face"}
SWATCHES = {
    "plank": dict(box=(632, 176, 648, 250), metres=0.9),
    "wood": dict(box=(632, 176, 648, 250), metres=0.9),
    "wood_h": dict(box=(632, 176, 648, 250), metres=0.9, rotate=True),
    "stone": dict(box=(716, 166, 808, 252), metres=1.35),
    "stone_face": dict(box=(722, 214, 790, 248), metres=0.9),
    "ground": dict(box=(0, 140, 40, 180), metres=2.5),
    "water": dict(box=(400, 180, 470, 235), metres=5.0),
    "grass": dict(box=(55, 195, 100, 225), metres=1.6),
    "gravel": dict(box=(330, 222, 372, 250), metres=1.8),
    "cloth": dict(box=(1280, 718, 1386, 828), metres=1.2),
    "metal": dict(box=(1430, 740, 1470, 800), metres=0.4),
}
CLASS_SWATCH = {"ground": {"water": "water", "veg": "grass", "stone": "gravel", "wood": "gravel", "z<-1.0": "water"}}
MORTAR_RGB = (0.27, 0.24, 0.20)
EDGE_WIDTH_M = 0.03
EDGE_STRENGTH = {"stone": 0.6, "wood": 0.3}
TAG_RGB = {"deck": (0.58, 0.44, 0.31), "ramp": (0.58, 0.44, 0.31), "tower": (0.60, 0.56, 0.49),
           "cornice": (0.56, 0.52, 0.45), "cap": (0.50, 0.46, 0.40), "gatepier": (0.60, 0.56, 0.49),
           "post": (0.36, 0.25, 0.16), "rail": (0.45, 0.32, 0.21)}
POLY_JITTER = 0.09
WIND = {"dir": (0, 1, 0), "amp": 0.22, "drop": 2.2}
SWATCH_FALLBACK = {"water": "ground", "rope": "wood", "roof": "stone", "glow": "metal"}
CLASS_TRAIN = {
    "wood": [(160, 96, 176, 140), (262, 70, 278, 140), (200, 110, 250, 125), (610, 175, 640, 250),
             (112, 104, 150, 118), (300, 58, 330, 66), (395, 40, 420, 46), (200, 82, 240, 92)],
    "stone": [(240, 150, 300, 195), (420, 108, 460, 140), (722, 172, 800, 245), (110, 150, 160, 200)],
    "water": [(430, 175, 520, 235), (370, 205, 430, 245), (300, 200, 340, 225)],
    "veg": [(55, 195, 100, 225), (20, 230, 60, 250), (550, 150, 580, 200)],
}
ACCEPT = {"wood": {"wood", "stone"}, "stone": {"stone"}, "ground": {"water", "veg", "stone"},
          "metal": set(), "cloth": set(), "rope": {"wood"}}
NORMAL_STRENGTH = {"stone": 3.0, "wood": 2.5, "ground": 1.5, "cloth": 1.0, "metal": 1.0}
# banner red from art/01 (Lab of the painted banners)
CLASS_LAB = {"cloth": (np.array([38.0, 42.0, 33.0]), np.array([6.0, 5.0, 5.0]))}


def veg_mask(c):
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    return (g > b + 0.06) & (g > 0.25) & ((g >= r - 0.04))


CARD_KINDS = {"fern_a": "fern", "grass_a": "grass", "weed_a": "weed", "grass_b": "grass"}
CARD_SPRITES_UNUSED = {
    "fern_a": dict(box=(40, 186, 112, 236), mask=veg_mask),
    "grass_a": dict(box=(538, 146, 584, 202), mask=veg_mask),
    "weed_a": dict(box=(262, 212, 300, 262), mask=veg_mask),
    "grass_b": dict(box=(0, 108, 40, 140), mask=veg_mask),
}

_CAM = {}


def camera_points():
    P, p = [], []
    for k in range(7):
        P.append((MAIN_POST_X[k], -POST_Y, POST_TOP))
        p.append(NEAR[k])
        P.append((MAIN_POST_X[k], POST_Y, POST_TOP))
        p.append(FAR[k])
    for k, q in FAR_FOOT.items():
        P.append((MAIN_POST_X[k], 2.0, DECK))
        p.append(q)
    opts = dict(free_pp=True)
    if os.environ.get("LM3_K1"):
        opts.update(free_k1=True, k_prior=float(os.environ["LM3_K1"]))
    return np.array(P, float), np.array(p, float), opts


def attach(cam, crop, mask):
    _CAM["cam"], _CAM["crop"], _CAM["mask"] = cam, crop, mask


def bank_profile(x):
    """In-game terrain across the bridge section (route lf_route_10_11 samples, local x)."""
    xs = np.array([-16.5, -13.5, -9.5, -8.5, -7.5, -6.5, -5.5, -4.0, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 13.5, 16.5])
    zs = np.array([0.56, 0.55, 0.50, 0.26, -0.38, -1.21, -2.03, -2.83, -2.83, -2.61, -1.99, -1.15, -0.31, 0.32, 0.53,
                   0.50, 0.50])
    return np.interp(x, xs, zs)


def base_height(x, y):
    """Painted ground patch surface: water plane between the abutments, banks rising to the abutments."""
    ax = np.abs(np.asarray(x, float))
    t = np.clip((ax - 11.2) / (13.8 - 11.2), 0, 1)
    t = t * t * (3 - 2 * t)
    return WATER + 0.02 + (BANK_Z - WATER) * t


# ============================================================================ geometry
def build(lod, cam=None, crop=None, mask=None, cards=None):
    g = Geo(seed=11 + lod)
    rng = g.rng
    deck(g, lod)
    railings(g, lod)
    substructure(g, lod)
    towers(g, lod)
    cloth = Geo(seed=21 + lod)
    banners(g, lod, cloth)
    base = ground_base(lod, cam, mask, cards or {})
    return dict(struct=g, cloth=cloth, base=base)


def deck(g, lod):
    pt = 0.08
    if lod == 0:
        x = -HL
        i = 0
        while x < HL - 1e-6:
            w = min(0.3 + g.rng.uniform(-0.03, 0.03), HL - x)
            dy = g.rng.uniform(-0.06, 0.06)
            g.box((x + w / 2, dy, DECK - pt / 2 + g.rng.uniform(-0.008, 0.008)), (w - 0.018, 2 * HW + 0.12, pt),
                  rot_z(g.rng.normal(0, 0.006)), "wood", "deck", skip=("-z", "-x", "+x"))
            x += w
            i += 1
        # ramps (sloped planks) down to the banks
        for s in (-1, 1):
            n = 11
            for k in range(n):
                xa = s * (HL + (RAMP_END - HL) * k / n)
                xb = s * (HL + (RAMP_END - HL) * (k + 1) / n)
                za = DECK - (DECK - BANK_Z) * k / n
                zb = DECK - (DECK - BANK_Z) * (k + 1) / n
                g.beam((xa, 0, za - pt / 2), (xb, 0, zb - pt / 2), 2 * HW + 0.1, pt, mat="wood", tag="ramp",
                       ext=-0.01, skip=("-z", "-x", "+x"))
        g.quad((-HL, -HW, DECK - pt - 0.01), (HL, -HW, DECK - pt - 0.01), (HL, HW, DECK - pt - 0.01),
               (-HL, HW, DECK - pt - 0.01), "wood", "subdeck")
    else:
        g.box((0, 0, DECK - pt / 2), (2 * HL, 2 * HW + 0.12, pt), None, "wood", "deck", skip=("-z",))
        for s in (-1, 1):
            g.beam((s * HL, 0, DECK - pt / 2), (s * RAMP_END, 0, BANK_Z - pt / 2), 2 * HW + 0.1, pt, mat="wood",
                   tag="ramp", skip=("-z",))
    # stringers + fascia beams
    ys = [-1.55, -0.55, 0.55, 1.55] if lod == 0 else ([-1.2, 1.2] if lod == 1 else [])
    for y in ys:
        g.beam((-HL, y, DECK - pt - 0.15), (HL, y, DECK - pt - 0.15), 0.22, 0.28, mat="wood", tag="stringer",
               skip=("-x", "+x") if lod else ())
    if lod < 2:
        for s in (-1, 1):
            g.beam((-HL - 0.05, s * (HW + 0.02), DECK - 0.27), (HL + 0.05, s * (HW + 0.02), DECK - 0.27), 0.14, 0.34,
                   mat="wood", tag="fascia", chamfer=0.025 if lod == 0 else 0.0)


def railings(g, lod):
    top_z, mid_z = 2.04, 1.6
    for s in (-1, 1):
        y = s * POST_Y
        xs = [-HL + 2.25 * k for k in range(13)]
        for k, x in enumerate(xs):
            main = k % 2 == 0
            if lod == 2 and k % 4 != 0:
                continue
            if main:
                zb = DECK - 0.55 if lod == 0 else DECK - 0.4
                w = 0.26
                g.box((x, y, (zb + POST_TOP) / 2), (w, w, POST_TOP - zb), rot_z(g.rng.normal(0, 0.015)), "wood",
                      "post", skip=("-z",))
                if lod == 0:   # bolt plates / cap
                    g.box((x, y, POST_TOP + 0.02), (w + 0.03, w + 0.03, 0.04), None, "wood", "post_cap", skip=("-z",))
            else:
                w = 0.15
                g.box((x, y, (DECK + top_z) / 2), (w, w, top_z - DECK + 0.04), None, "wood", "baluster",
                      skip=("-z", "+z"))
        # rails along the deck + ramps
        rails = [(top_z, 0.13, 0.11), (mid_z, 0.11, 0.1)] if lod < 2 else [(top_z, 0.13, 0.12)]
        for z, h, w in rails:
            g.beam((-HL, y, z), (HL, y, z), w, h, mat="wood", tag="rail", chamfer=0.02 if lod == 0 else 0.0,
                   skip=() if lod == 0 else ("-x", "+x"))
            for e in (-1, 1):
                g.beam((e * HL, y, z), (e * (RAMP_END - 0.15), y, z - (DECK - BANK_Z)), w, h, mat="wood", tag="rail_ramp")
        if lod < 2:
            for e in (-1, 1):
                x = e * (RAMP_END - 0.15)
                zt = POST_TOP - (DECK - BANK_Z)
                g.box((x, y, (BANK_Z - 0.3 + zt) / 2), (0.26, 0.26, zt - BANK_Z + 0.3), None, "wood", "post_end",
                      skip=("-z",))


def substructure(g, lod):
    cheap = lod > 0
    # cap beams across at the supports
    for x in ((-ABUT_X + 0.35, -BANK_PIER_X, -TOWER_X, TOWER_X, BANK_PIER_X, ABUT_X - 0.35) if lod < 2 else ()):
        g.beam((x, -2.35, DECK - 0.53), (x, 2.35, DECK - 0.53), 0.3, 0.3, mat="wood", tag="capbeam",
               skip=() if lod == 0 else ("-x", "+x"))
    # bank piers (masonry) + trestle posts with knee braces (art/06 style)
    for x in (-BANK_PIER_X, BANK_PIER_X):
        lo = (x - 0.55, -2.3, WATER - 0.45)
        hi = (x + 0.55, 2.3, DECK - 0.95)
        if lod == 0:
            g.masonry_box(lo, hi, course=0.4, block=(0.55, 0.95), seed=int(x * 7) % 97, tag=f"pier{int(x)}",
                          cheap_faces=("+y", "-y", "+x" if x < 0 else "-x"))
        else:
            g.box(((lo[0] + hi[0]) / 2, 0, (lo[2] + hi[2]) / 2), np.subtract(hi, lo), None, "stone", f"pier{int(x)}",
                  skip=("-z",))
        for y in ((-1.7, 1.7) if lod < 2 else ()):
            zt = DECK - 0.68
            g.box((x, y, (hi[2] + zt) / 2), (0.24, 0.24, zt - hi[2]), None, "wood", "trestle", skip=("-z",))
            if lod == 0:
                for d in (-1, 1):
                    g.beam((x + d * 0.1, y, hi[2] + 0.12), (x + d * 1.0, y, DECK - 0.7), 0.16, 0.16, mat="wood",
                           tag="knee")
    # pier walls between the tower pairs (under the deck)
    for x in (-TOWER_X, TOWER_X):
        lo = (x - TOWER_W / 2 + 0.05, -TOWER_Y + TOWER_W / 2, WATER - 0.45)
        hi = (x + TOWER_W / 2 - 0.05, TOWER_Y - TOWER_W / 2, DECK - 0.68)
        if lod == 0:
            g.masonry_box(lo, hi, course=0.42, block=(0.6, 1.0), faces=("+x", "-x"), seed=int(x * 5) % 91,
                          tag=f"gatepier{int(x)}", cheap_faces=("+x" if x < 0 else "-x",))
        else:
            g.box(((lo[0] + hi[0]) / 2, 0, (lo[2] + hi[2]) / 2), np.subtract(hi, lo), None, "stone",
                  f"gatepier{int(x)}", skip=("-z", "-y", "+y"))
    # abutments with wing walls
    for s in (-1, 1):
        x0, x1 = (s * (ABUT_X - 0.5), s * (ABUT_X + 0.9))
        lo = (min(x0, x1), -2.6, WATER - 0.2)
        hi = (max(x0, x1), 2.6, DECK - 0.62)
        if lod == 0:
            g.masonry_box(lo, hi, course=0.45, block=(0.55, 1.0), seed=31 + s, tag=f"abut{s}",
                          faces=("-x", "+y", "-y") if s > 0 else ("+x", "+y", "-y"), cheap_faces=("+y", "-y"))
            for y in (-2.6, 2.6):
                wl = (min(s * (ABUT_X + 0.9), s * (ABUT_X + 3.0)), y - 0.35 if y > 0 else y - 0.35, WATER + 0.6)
                wh = (max(s * (ABUT_X + 0.9), s * (ABUT_X + 3.0)), y + 0.35, BANK_Z + 0.2)
                g.masonry_box(wl, wh, course=0.45, block=(0.5, 0.9), seed=41 + int(y) + s, tag=f"wing{s}",
                              faces=("+y", "-y", "+x" if s > 0 else "-x"), cheap=True)
        else:
            g.box(((lo[0] + hi[0]) / 2, 0, (lo[2] + hi[2]) / 2), np.subtract(hi, lo), None, "stone", f"abut{s}",
                  skip=("-z",))
    # central span: timber arch ribs from the gate piers (art/01) + struts + diagonal braces
    if lod < 2:
        n = 14 if lod == 0 else 8
        for y in ((-1.55, 1.55)):
            xs = np.linspace(-TOWER_X + TOWER_W / 2 - 0.05, TOWER_X - TOWER_W / 2 + 0.05, n + 1)
            span = xs[-1] - xs[0]
            zc = -0.35 + 1.0 * (1 - (2 * (xs - xs[0]) / span - 1) ** 2)
            P = np.stack([xs, np.full_like(xs, y), zc], 1)
            g.tube(P, 0.17, n=4, mat="wood", tag="arch")
            if lod == 0:
                for xv in (-4.4, -2.2, 0.0, 2.2, 4.4):
                    zr = -0.35 + 1.0 * (1 - (2 * (xv - xs[0]) / span - 1) ** 2)
                    if DECK - 0.38 - zr > 0.15:
                        g.box((xv, y, (zr + DECK - 0.38) / 2), (0.16, 0.16, DECK - 0.38 - zr), None, "wood", "strut")
                for e in (-1, 1):
                    g.beam((e * (TOWER_X - TOWER_W / 2), y, -0.1), (e * (TOWER_X - 2.4), y, DECK - 0.4), 0.18, 0.18,
                           mat="wood", tag="brace")
        # cross ties between the ribs
        if lod == 0:
            for xv in (-3.3, 0.0, 3.3):
                g.beam((xv, -1.6, 0.55), (xv, 1.6, 0.55), 0.14, 0.14, mat="wood", tag="tie")


def towers(g, lod):
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * TOWER_X, sy * TOWER_Y
            h = TOWER_W / 2
            lo = (cx - h, cy - h, WATER - 0.45)
            hi = (cx + h, cy + h, 4.6)
            if lod == 0:
                g.masonry_box(lo, hi, course=0.44, block=(0.45, 0.8), seed=7 + 3 * sx + sy, tag=f"tower{sx}{sy}",
                              cheap=True, top=False, relief=0.05)
                # plinth course at the water line
                g.box((cx, cy, WATER + 0.1), (TOWER_W + 0.16, TOWER_W + 0.16, 0.5), None, "stone", f"tower{sx}{sy}",
                      skip=("-z",))
            else:
                g.box((cx, cy, (lo[2] + hi[2]) / 2), (TOWER_W, TOWER_W, hi[2] - lo[2]), None, "stone",
                      f"tower{sx}{sy}", skip=("-z", "+z"))
            # cornice + pyramid cap + finial
            if lod < 2:
                g.box((cx, cy, 4.72), (TOWER_W + 0.22, TOWER_W + 0.22, 0.24), None, "stone", f"cornice{sx}{sy}")
            apex = (cx, cy, 5.75)
            b = (TOWER_W + 0.12) / 2
            base = [(cx - b, cy - b, 4.84), (cx + b, cy - b, 4.84), (cx + b, cy + b, 4.84), (cx - b, cy + b, 4.84)]
            V = np.array(base + [apex])
            g.add(V, [[0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4]], "stone", f"cap{sx}{sy}")
            if lod < 2:
                g.cyl((cx, cy, 5.7), (cx, cy, 6.15), 0.06, 0.02, n=6, mat="metal", tag="finial")
            # arched window niche on the outward face (art/01)
            if lod == 0:
                ny = sy * (h + 0.06)
                for dz, ww in ((3.55, 0.36),):
                    g.quad((cx - ww / 2, cy + ny * 1.0, dz), (cx + ww / 2, cy + ny, dz), (cx + ww / 2, cy + ny, dz + 0.55),
                           (cx - ww / 2, cy + ny, dz + 0.55), "metal", "niche") if sy > 0 else \
                        g.quad((cx + ww / 2, cy + ny, dz), (cx - ww / 2, cy + ny, dz), (cx - ww / 2, cy + ny, dz + 0.55),
                               (cx + ww / 2, cy + ny, dz + 0.55), "metal", "niche")


def banners(g, lod, cloth):
    """Red banners on the two north towers (art/01): iron pole on the cap apex, arm toward +x, a large cloth
    (0.8 x 2.2 m) hanging beside the tower top with a sway-ready curve (wind clip lf_banner_wind)."""
    for sx in (-1, 1):
        cx, cy = sx * TOWER_X, TOWER_Y
        top = 7.25
        g.cyl((cx, cy, 5.6), (cx, cy, top + 0.15), 0.06, 0.05, n=6 if lod == 0 else 4, mat="metal", tag="banner_pole")
        g.cyl((cx - 0.05, cy, top), (cx + 1.55, cy, top), 0.04, n=4, mat="metal", tag="banner_arm", caps=(False, True))
        if lod == 0:
            g.beam((cx + 0.05, cy, top - 0.55), (cx + 0.9, cy, top - 0.02), 0.05, 0.05, mat="metal", tag="banner_arm")
        nu, nv = (6, 10) if lod == 0 else ((3, 5) if lod == 1 else (2, 2))
        Wb, Hb = 0.8, 2.2
        x0 = cx + 0.62
        P = np.zeros((nu, nv, 3))
        for i in range(nu):
            for j in range(nv):
                u = i / (nu - 1)
                v = j / (nv - 1)
                x = x0 + Wb * u
                z = top - 0.04 - Hb * v
                y = cy + (0.06 * math.sin(math.pi * u * 1.6 + 0.4) + 0.12 * v * v) * (0.4 + v)
                if v > 0.88 and lod == 0:          # swallow-tail notch at the bottom
                    z += 0.32 * (1 - abs(2 * u - 1)) * (v - 0.88) / 0.12
                P[i, j] = (x, y, z)
        cloth.grid_surface(P, "cloth", "banner")
        if lod < 2:   # top hem / rod
            g.cyl((x0 - 0.02, cy, top - 0.04), (x0 + Wb + 0.02, cy, top - 0.04), 0.025, n=4, mat="wood", tag="banner_rod")


# ---------------------------------------------------------------------------- ground base (painted patch)
def ground_base(lod, cam, mask, cards):
    import cv2
    b = Geo(seed=5 + lod)
    if cam is None or mask is None:
        return b
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)[:, 0, :].astype(float)
    c = c[:: 2]
    P = cam.on_surface(c[:, 0] + 0.5, c[:, 1] + 0.5, base_height, z0=WATER)
    ok = np.isfinite(P).all(1)
    P = P[ok]
    P[:, 1] = np.clip(P[:, 1], -18.0, 6.5)
    P[:, 0] = np.clip(P[:, 0], -20.0, 20.0)
    poly = P[:, :2]
    step = 1.0 if lod == 0 else (2.0 if lod == 1 else 4.0)
    xs = np.arange(poly[:, 0].min() - step, poly[:, 0].max() + step * 1.5, step)
    ys = np.arange(poly[:, 1].min() - step, poly[:, 1].max() + step * 1.5, step)
    from skimage.measure import points_in_poly
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    inside = points_in_poly(np.stack([X.ravel(), Y.ravel()], 1), poly).reshape(X.shape)
    keep_cell = np.zeros((len(xs) - 1, len(ys) - 1), bool)
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            keep_cell[i, j] = inside[i:i + 2, j:j + 2].any()
    # snap outside vertices of kept cells onto the outline
    V = np.stack([X, Y], -1).astype(float)
    used = np.zeros(X.shape, bool)
    for i, j in zip(*np.nonzero(keep_cell)):
        used[i:i + 2, j:j + 2] = True
    seg_a = poly
    seg_b = np.roll(poly, -1, 0)
    for i, j in zip(*np.nonzero(used & ~inside)):
        p = V[i, j]
        ab = seg_b - seg_a
        t = np.clip(((p - seg_a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-9), 0, 1)
        q = seg_a + ab * t[:, None]
        V[i, j] = q[np.argmin(((q - p) ** 2).sum(1))]
    Z = base_height(V[..., 0], V[..., 1])
    # gentle bank undulation (not on the water)
    Z = Z + np.where(Z > WATER + 0.1, 0.08 * np.sin(V[..., 0] * 1.3) * np.cos(V[..., 1] * 0.9), 0.0)
    idx = -np.ones(X.shape, int)
    verts = []
    for i, j in zip(*np.nonzero(used)):
        idx[i, j] = len(verts)
        verts.append((V[i, j, 0], V[i, j, 1], Z[i, j]))
    F = [[idx[i, j], idx[i + 1, j], idx[i + 1, j + 1], idx[i, j + 1]] for i, j in zip(*np.nonzero(keep_cell))]
    b.add(np.array(verts), F, "ground", "base")
    # rocks along the banks (painted boulders: sheet pixel of the contact point, radius px)
    rocks = [(350, 247, 22), (420, 233, 14), (215, 238, 16), (238, 250, 12), (150, 215, 12), (60, 205, 14),
             (30, 225, 10), (510, 232, 14), (482, 240, 10), (555, 222, 13), (575, 198, 10), (560, 100, 12),
             (542, 180, 9), (196, 215, 9), (280, 245, 9), (400, 248, 9), (575, 120, 9)]
    nrock = len(rocks) if lod == 0 else (8 if lod == 1 else 0)
    for k, (u, v, r) in enumerate(rocks[:nrock]):
        Pc = cam.on_surface(np.array([u + 0.5]), np.array([v + 0.5]), base_height, z0=WATER)[0]
        dist = np.linalg.norm(Pc - cam.centre)
        rad = r * dist / cam.f
        b.rock((Pc[0], Pc[1], Pc[2] + rad * 0.15), (rad * 1.15, rad * 0.95, rad * 0.75), seed=k + 3,
               sub=1 if lod == 0 else 0, mat="stone", tag=f"rock{k}")
    # vegetation cards where the painting shows plants on the patch edge
    if lod < 2 and cards:
        names = [n for n in cards]
        spots = [(70, 210, "fern_a", 46), (40, 235, "fern_a", 40), (110, 228, "fern_a", 40), (285, 255, "weed_a", 30),
                 (560, 170, "grass_a", 40), (570, 215, "grass_a", 34), (520, 245, "grass_a", 28), (12, 130, "grass_b", 26),
                 (180, 235, "fern_a", 30), (470, 250, "weed_a", 26), (580, 150, "grass_a", 30)]
        if lod == 1:
            spots = spots[::2]
        for k, (u, v, nm, hpx) in enumerate(spots):
            if nm not in cards:
                continue
            Pc = cam.on_surface(np.array([u + 0.5]), np.array([v + 0.5]), base_height, z0=WATER)[0]
            dist = np.linalg.norm(Pc - cam.centre)
            h = hpx * dist / cam.f
            u0, v0, u1, v1, aw, ah = cards[nm]
            w = h * aw / ah
            for yaw in (0.0, math.pi / 2):
                b.card(Pc, w, h, yaw + k * 0.7, "card_veg", "veg", (u0, v0, u1, v1))
    return b


# ---------------------------------------------------------------------------- colliders / meta
def colliders():
    C = []
    C.append(dict(type="box", centre=(0, 0, DECK - 0.05), size=(27.0, 4.0, 0.1)))
    for s in (-1, 1):
        C.append(dict(type="box", centre=(0, s * 2.2, DECK + 0.55), size=(27.2, 0.22, 1.1)))
        C.append(dict(type="ramp", centre=(s * (HL + RAMP_END) / 2, 0, (DECK + BANK_Z) / 2 - 0.3), size=(3.25, 4.0, 0.1)))
        C.append(dict(type="box", centre=(s * BANK_PIER_X, 0, (WATER - 0.45 + DECK - 0.95) / 2), size=(1.1, 4.6, DECK - 0.5 - WATER)))
        C.append(dict(type="box", centre=(s * TOWER_X, 0, (WATER - 0.45 + DECK - 0.68) / 2), size=(TOWER_W, 2 * TOWER_Y, DECK - 0.23 - WATER)))
        for sy in (-1, 1):
            C.append(dict(type="box", centre=(s * TOWER_X, sy * TOWER_Y, (WATER - 0.45 + 5.75) / 2),
                          size=(TOWER_W + 0.2, TOWER_W + 0.2, 5.75 - WATER + 0.45)))
    return C


def meta_extra():
    return dict(
        placement={"world_position_xz": [90.48200135039062, 20.0], "world_y": 0.0,
                   "note": "origin = bridge centre on the world datum; deck top local +1.1 = atlas structuralHeight; "
                           "long axis = +X (west->east 77..104); atlas waterLevel -1.35 lies at local -1.35"},
        dimensions={"deck_length_m": 27.0, "deck_width_m": 4.0, "deck_top_z": DECK, "deck_x_range": [-13.5, 13.5],
                    "deck_y_range_gltf_z": [-2.0, 2.0], "piers_x": [-TOWER_X, TOWER_X],
                    "pier_inner_faces_x": [-6.6, 6.6], "bank_piers_x": [-BANK_PIER_X, BANK_PIER_X],
                    "abutments_x": [-ABUT_X, ABUT_X], "wet_banks_x": [-6.317, 6.287],
                    "main_channel_clear": "no support between x=-6.6 and +6.6 (timber arch ribs span the channel)",
                    "towers": "4 stone tower piers 1.3 x 1.3 m at x=+-7.25, gltf z=+-2.95 (beside the deck), top 6.15 m",
                    "banners": "red cloth banners 0.8 x 2.2 m on arms of the two north towers (gltf z=-2.95), arm at 7.25 m; node <id>_cloth_LOD0 carries the lf_banner_wind morph clip",
                    "ramps": "x +-13.5 -> +-16.7, deck 1.1 down to bank 0.45 (11.5 deg)",
                    "railing_top_above_deck_m": round(2.04 + 0.065 - DECK, 3)},
        sockets={"banner_west": [-TOWER_X + 1.02, 7.21, -TOWER_Y], "banner_east": [TOWER_X + 1.02, 7.21, -TOWER_Y],
                 "deck_west": [-13.5, DECK, 0.0], "deck_east": [13.5, DECK, 0.0]},
    )
