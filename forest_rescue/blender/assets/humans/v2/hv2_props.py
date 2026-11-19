"""Hand-held weapons of the squad (drawn sword, spear, round shield, short bow) as real meshes on the
PropR / PropL bones, with their own small material: the shield face, spear and bow are textured
from their detached painted views on art/04 (planar UVs), metal/wood/leather parts from colours
sampled on the sheet.  They are hidden (bone scale 0) in clips where the hand is free."""
import math

import numpy as np
from PIL import Image

import hv2_drape as HD

SQ = "04_expedition_squad_turnaround.png"
# painted detached views on art/04 (sheet px)
SHIELD_BOX = (1018, 598, 1180, 752)
SPEAR_BOX = (926, 750, 1490, 772)
BOW_BOX = (520, 618, 852, 656)
ATLAS = 512


def build_atlas(path):
    from frlib import paths
    sheet = Image.open(paths.art(SQ)).convert("RGB")
    A = Image.new("RGB", (ATLAS, ATLAS), (110, 80, 52))
    A.paste(sheet.crop(SHIELD_BOX).resize((256, 256), Image.LANCZOS), (0, 0))
    A.paste(sheet.crop(SPEAR_BOX).resize((512, 32), Image.LANCZOS), (0, 288))
    A.paste(sheet.crop(BOW_BOX).resize((512, 48), Image.LANCZOS), (0, 336))
    # flat swatches: iron, wood, leather, bronze (sampled colours of the sheet)
    sw = {"iron": (138, 136, 134), "wood": (112, 78, 48), "leather": (82, 56, 38), "bronze": (150, 112, 62),
          "blade": (168, 168, 166)}
    for i, (k, c) in enumerate(sw.items()):
        A.paste(Image.new("RGB", (48, 48), c), (272 + (i % 4) * 56, 8 + (i // 4) * 56))
    A.save(path, quality=92)
    return path


SW_UV = {"iron": (272, 8), "wood": (328, 8), "leather": (384, 8), "bronze": (440, 8), "blade": (272, 64)}


def _uv_swatch(n, key):
    x, y = SW_UV[key]
    u = (x + 24) / ATLAS
    v = 1.0 - (y + 24) / ATLAS
    return np.tile([u, v], (n, 1))


def _loops_uv(F, vert_uv):
    out = []
    for f in F:
        for vi in f:
            out.append(vert_uv[vi])
    return np.array(out)


def disc(center, normal, radius, thick, segs=28):
    n = normal / np.linalg.norm(normal)
    a = np.cross(n, [0, 0, 1.0])
    if np.linalg.norm(a) < 1e-6:
        a = np.cross(n, [1.0, 0, 0])
    a /= np.linalg.norm(a)
    b = np.cross(n, a)
    V, F, uv = [], [], []
    for side in (1, -1):
        c = center + n * thick * 0.5 * side
        ci = len(V)
        V.append(c)
        uv.append((0.25, 1 - 0.25) if side == 1 else (0.5, 0.5))
        for k in range(segs):
            t = 2 * math.pi * k / segs
            p = c + (a * math.cos(t) + b * math.sin(t)) * radius
            V.append(p)
            if side == 1:
                uv.append((0.25 + 0.245 * math.cos(t), 1 - (0.25 - 0.245 * math.sin(t))))
            else:
                uv.append((SW_UV["wood"][0] / ATLAS + 0.04, 1 - (SW_UV["wood"][1] + 20) / ATLAS))
        for k in range(segs):
            k2 = (k + 1) % segs
            F.append([ci, ci + 1 + k, ci + 1 + k2] if side == 1 else [ci, ci + 1 + k2, ci + 1 + k])
    # rim
    for k in range(segs):
        k2 = (k + 1) % segs
        F.append([1 + k, 1 + k2, segs + 2 + k2, segs + 2 + k])
    boss = []
    return np.array(V), F, np.array(uv)


def build(kind, hand_bones, J):
    """Returns list of (name, V, F, per-vertex uv, bone)."""
    out = []
    if kind == "sword":
        hb = hand_bones["Right"]
        d, t, n = hb["_frame"]
        g = hb["_grip"]
        ax = t / np.linalg.norm(t)                       # blade forward from the fist
        blade = np.array([g + ax * 0.06, g + ax * 0.45, g + ax * 0.80])
        V, F = HD.tube_mesh(blade, [0.020, 0.017, 0.004], sides=4)
        out.append(("sword_blade", V, F, _uv_swatch(len(V), "blade"), "PropR"))
        V, F = HD.box_mesh(g + ax * 0.05, (0.012, 0.012, 0.012), bevel=0.4, nseg=1)
        V = (V - (g + ax * 0.05)) * np.array([5.0, 1.0, 1.0]) + (g + ax * 0.05)
        out.append(("sword_guard", V, F, _uv_swatch(len(V), "bronze"), "PropR"))
        grip = np.array([g - ax * 0.07, g + ax * 0.04])
        V, F = HD.tube_mesh(grip, 0.014, sides=6)
        out.append(("sword_grip", V, F, _uv_swatch(len(V), "leather"), "PropR"))
    elif kind == "spear":
        hb = hand_bones["Right"]
        g = hb["_grip"]
        shaft = np.array([[g[0], g[1], 0.03], [g[0], g[1], 1.0], [g[0], g[1], 2.08]])
        V, F = HD.tube_mesh(shaft, [0.016, 0.016, 0.014], sides=6)
        uv = np.zeros((len(V), 2))
        uv[:, 0] = np.clip(0.05 + 0.75 * (V[:, 2] / 2.1), 0, 1)
        uv[:, 1] = 1 - 300 / ATLAS
        out.append(("spear_shaft", V, F, uv, "PropR"))
        head = np.array([[g[0], g[1], 2.06], [g[0], g[1], 2.16], [g[0], g[1], 2.30]])
        V, F = HD.tube_mesh(head, [0.012, 0.030, 0.002], sides=4)
        out.append(("spear_head", V, F, _uv_swatch(len(V), "iron"), "PropR"))
    elif kind == "shield":
        hb = hand_bones["Left"]
        d, t, n = hb["_frame"]
        g = hb["_grip"]
        c = g - n * 0.09 - d * 0.04
        V, F, uv = disc(c, -n, 0.36, 0.028)
        out.append(("shield", V, F, uv, "PropL"))
        V, F = HD.box_mesh(c - n * 0.03, (0.06, 0.06, 0.06), bevel=0.9, nseg=2)
        out.append(("shield_boss", V, F, _uv_swatch(len(V), "iron"), "PropL"))
    elif kind == "bow":
        hb = hand_bones["Left"]
        d, t, n = hb["_frame"]
        g = hb["_grip"]
        up = np.array([0, 0, 1.0])
        fwd = t / np.linalg.norm(t)
        pts = []
        for s in np.linspace(-1, 1, 13):
            pts.append(g + up * 0.62 * s + fwd * (0.10 * (1 - s * s) - 0.02))
        pts = np.array(pts)
        r = 0.009 + 0.006 * (1 - np.abs(np.linspace(-1, 1, 13)))
        V, F = HD.tube_mesh(pts, r, sides=6)
        uv = np.zeros((len(V), 2))
        uv[:, 0] = np.clip(0.03 + 0.94 * (V[:, 2] - pts[0][2]) / (pts[-1][2] - pts[0][2]), 0, 1)
        uv[:, 1] = 1 - 356 / ATLAS
        out.append(("bow", V, F, uv, "PropL"))
        string = np.array([pts[0] + fwd * 0.004, pts[-1] + fwd * 0.004])
        V, F = HD.tube_mesh(string, 0.0025, sides=4)
        out.append(("bow_string", V, F, _uv_swatch(len(V), "leather"), "PropL"))
    return out
