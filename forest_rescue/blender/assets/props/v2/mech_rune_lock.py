"""lf_mechanism_rune_lock v2 from art/10_artifact_mechanisms.png (upper middle, closed + open drawings): a round
limestone drum (plinth, masonry wall, stone rim) carrying a stepped bronze dial of three stacked discs that rise
toward the back (ring_3 bottom / widest .. ring_1 top), a thin bronze rim with four riveted clamps, an arched bronze
key niche on the front-right of the wall, a stone door panel in the front wall that slides down into the plinth
(the artifact chest waits in the cavity behind it) and a stone threshold step in front of the door on which the
bronze key with its green crystal lies until it is set into the niche.

Same node / clip contract as the v1 delivery (actor_director, meta.symbol_targets): ring_1..ring_3 rotate about the
drum axis (glTF +Y through each disc centre), ten engraved positions 36 deg apart (blank + the nine campaign glyphs),
lf_rune_ring<k>_<glyph> (0.6 s, marker click), lf_lock_mechanism (1.8 s: key into the niche, door slides down),
door_pivot, key_lever, artifact_spot.

Texture: the painting is projected from both drawings (solved cameras); the disc tops are cleaned of the painted
site-02 glyphs (inpaint) and all ten positions are engraved in the painted style (post_texture), so every site's
symbols read at the front index mark.
"""
import math
import os
import sys

import numpy as np

import cagegeo as CG
import pv2

ID = "lf_mechanism_rune_lock"
ATLAS = 2048
SHEET = "10_artifact_mechanisms.png"
LIGHT = (-0.5, -0.55, 0.67)
BUDGET = "mechanism LOD0 <= 6000 tris"

GLYPHS = ["blank", "mountain", "river", "leaf", "coal", "seed", "tree", "sun", "stone", "root"]
STEP = 36.0
SITES = {"lf_site_02": ["mountain", "river", "leaf"], "lf_site_06": ["coal", "seed", "tree"],
         "lf_site_10": ["sun", "stone", "root"]}
DOOR_DROP = 0.62

PARAMS = dict(Rw=0.95, Rb=1.0, hb=0.1, zt=0.56, Rr=0.64, rc=0.68, dz=0.065,
              R3=0.555, R2=0.5, R1=0.41, y2=0.12, y1=0.24,
              an=-38.0, nz=0.34, nh=0.5, ad=-86.0, dh=21.0, dt=0.56,
              sx=0.08, sy=-1.25, sw=1.05, sd=0.36, sh=0.16)
FREE = ["Rw", "Rb", "zt", "Rr", "rc", "dz", "R3", "R2", "R1", "y2", "y1", "an", "nz", "nh", "dh", "dt",
        "sx", "sy", "sw", "sd", "sh"]
PRIOR = 0.3


def ring_angle(symbol):
    """Ring rotation (radians, about +Z Blender / +Y glTF) bringing `symbol` to the front mark."""
    return -math.radians(STEP * GLYPHS.index(symbol))


SOLVED_POSE_02 = {"ring_1": {"rot": (0, 0, ring_angle("mountain"))}, "ring_2": {"rot": (0, 0, ring_angle("river"))},
                  "ring_3": {"rot": (0, 0, ring_angle("leaf"))}}


def discs(p):
    zr = p["zt"] + 0.075
    dz = p["dz"]
    return {"ring_3": (p["R3"], 0.0, zr, zr + dz), "ring_2": (p["R2"], p["y2"], zr + dz, zr + 2 * dz),
            "ring_1": (p["R1"], p["y1"], zr + 2 * dz, zr + 3 * dz)}


def polar(r, deg, z):
    a = math.radians(deg)
    return (r * math.cos(a), r * math.sin(a), z)


def key_rest(p):
    """Key centre lying on the threshold step (rod along X, crystal at +X)."""
    return np.array([p["sx"] - 0.06, p["sy"] + 0.02, p["sh"] + 0.045])


def key_in_niche(p):
    """Key centre standing upright in the niche (crystal on top, just proud of the wall)."""
    a = math.radians(p["an"])
    r = p["Rw"] + 0.07
    return np.array([r * math.cos(a), r * math.sin(a), p["nz"] + 0.12])


def points(p):
    D = discs(p)
    R1, y1, _, z1t = D["ring_1"]
    R2, y2, _, z2t = D["ring_2"]
    R3, y3, _, z3t = D["ring_3"]
    zc = p["zt"] + 0.1
    P = {
        "r1_left": (-R1, y1, z1t), "r1_right": (R1, y1, z1t), "r1_back": (0, y1 + R1, z1t), "r1_front": (0, y1 - R1, z1t),
        "r2_front": (0, y2 - R2, z2t), "r3_front": (0, y3 - R3, z3t),
        "clamp_b": (0, p["rc"], zc), "clamp_f": (0, -p["rc"], zc), "clamp_l": (-p["rc"], 0, zc), "clamp_r": (p["rc"], 0, zc),
        "wall_l": (-p["Rw"], 0.0, 0.3), "wall_r": (p["Rw"], 0.0, 0.3),
        "step_tl": (p["sx"] - p["sw"] / 2, p["sy"] + p["sd"] / 2, p["sh"]),
        "step_tr": (p["sx"] + p["sw"] / 2, p["sy"] + p["sd"] / 2, p["sh"]),
        "step_bl": (p["sx"] - p["sw"] / 2, p["sy"] - p["sd"] / 2, 0.0),
        "step_br": (p["sx"] + p["sw"] / 2, p["sy"] - p["sd"] / 2, 0.0),
        "niche_top": polar(p["Rw"] + 0.03, p["an"], p["nz"] + p["nh"] / 2),
        "niche_bot": polar(p["Rw"] + 0.03, p["an"], p["nz"] - p["nh"] / 2),
        "door_tl": polar(p["Rw"], p["ad"] - p["dh"], p["hb"] + p["dt"]),
        "door_tr": polar(p["Rw"], p["ad"] + p["dh"], p["hb"] + p["dt"]),
        "door_bl": polar(p["Rw"], p["ad"] - p["dh"], p["hb"]),
        "door_br": polar(p["Rw"], p["ad"] + p["dh"], p["hb"]),
    }
    k = key_in_niche(p)
    P["gem_niche"] = (k[0], k[1], k[2] + 0.2)
    return P


def views():
    closed = pv2.ViewSpec(
        "closed", SHEET, (770, 40, 1110, 400),
        {"r1_left": (877.5, 103), "r1_right": (1005, 103), "r1_back": (941, 79), "r1_front": (941, 126),
         "r2_front": (941, 168), "r3_front": (941, 218),
         "clamp_b": (944, 68), "clamp_f": (944, 240), "clamp_l": (847, 146), "clamp_r": (1043, 146),
         "wall_l": (787, 275), "wall_r": (1094, 272),
         "step_tl": (874, 344), "step_tr": (1033, 341), "step_bl": (876, 387), "step_br": (1031, 384),
         "niche_top": (1048, 206), "niche_bot": (1047, 308)},
        pose=SOLVED_POSE_02, light=LIGHT, thresh=0.085, fill_holes=True, shadow=None, solve_opts={"fov_prior": 20.0},
        title="RUNE LOCK closed (site 02 glyphs set, key on the step)")
    open_pose = dict(SOLVED_POSE_02)
    open_pose["door_pivot"] = {"loc": (0, 0, -DOOR_DROP)}
    open_pose["key_lever"] = "key_in_niche"
    opened = pv2.ViewSpec(
        "open", SHEET, (1156, 40, 1500, 400),
        {"r1_left": (1262, 103), "r1_right": (1398, 103), "r1_back": (1330, 78), "r1_front": (1330, 125),
         "r2_front": (1330, 168), "r3_front": (1330, 218),
         "clamp_b": (1330, 67), "clamp_f": (1331, 240), "clamp_l": (1229, 142), "clamp_r": (1428, 142),
         "wall_l": (1172, 270), "wall_r": (1487, 270),
         "step_tl": (1262, 345), "step_tr": (1410, 343), "step_bl": (1265, 380), "step_br": (1408, 377),
         "door_tl": (1290, 272), "door_tr": (1390, 272), "door_bl": (1292, 345), "door_br": (1388, 345),
         "gem_niche": (1470, 186)},
        pose=open_pose, light=LIGHT, thresh=0.085, fill_holes=True, shadow=None, solve_opts={"fov_prior": 20.0},
        title="RUNE LOCK open (door down, key in the niche)", tex_weight=0.9)
    return [closed, opened]


def _resolve_pose(v, p):
    if v.pose.get("key_lever") == "key_in_niche":
        v.pose["key_lever"] = {"loc": tuple(key_in_niche(p) - key_rest(p)), "rot": (0.0, -math.pi / 2, 0.0)}


def arc_wall(g, r0, r1, z0, z1, a0, a1, n, mat, tag, top=True, ends=True):
    """Thick cylindrical wall segment between angles a0..a1 (radians, CCW), inner r0, outer r1."""
    a = np.linspace(a0, a1, n + 1)
    V = []
    for rr in (r1, r0):
        for z in (z0, z1):
            for ang in a:
                V.append((rr * math.cos(ang), rr * math.sin(ang), z))
    V = np.array(V)
    m = n + 1
    o0, o1, i0, i1 = 0, m, 2 * m, 3 * m
    F = []
    for k in range(n):
        F.append([o0 + k, o0 + k + 1, o1 + k + 1, o1 + k])          # outer face
        F.append([i0 + k + 1, i0 + k, i1 + k, i1 + k + 1])          # inner face
        if top:
            F.append([o1 + k, o1 + k + 1, i1 + k + 1, i1 + k])
    if ends:
        F.append([i0, o0, o1, i1])
        F.append([o0 + n, i0 + n, i1 + n, o1 + n])
    return g.add(V, F, mat, tag)


def build(A, p, lod):
    g = A.g("root", lod)
    n = (64, 40, 24)[lod]
    Rw, Rb, hb, zt = p["Rw"], p["Rb"], p["hb"], p["zt"]
    ad, dh = math.radians(p["ad"]), math.radians(p["dh"])
    # ---- plinth course + masonry wall with the door opening (front) + stone rim
    CG.ring_prism(g, (0, 0, 0), np.eye(3), Rb, Rw - 0.3, n, 0.0, hb, "stone", "plinth")
    arc_wall(g, Rw - 0.17, Rw, hb, zt, ad + dh, ad - dh + 2 * math.pi, n - 4, "stone", "wall", top=False)
    # lintel over the door (the wall above the opening) and the jamb returns
    arc_wall(g, Rw - 0.17, Rw, hb + p["dt"], zt, ad - dh, ad + dh, max(4, n // 10), "stone", "lintel", top=False,
             ends=False)
    CG.ring_prism(g, (0, 0, 0), np.eye(3), Rw + 0.025, p["Rr"], n, zt, zt + 0.06, "stone", "rim")
    # cavity behind the door: floor, back wall, side walls (dark), chest
    cy0 = Rw * math.sin(ad)
    cav_w = 2 * Rw * math.sin(dh) + 0.1
    g.box((0.0, cy0 + 0.42, hb + 0.005), (cav_w, 0.7, 0.01), mat="stone", tag="cavity_floor", skip=("-z",))
    g.box((0.0, cy0 + 0.79, hb + p["dt"] / 2), (cav_w, 0.04, p["dt"]), mat="stone", tag="cavity_back")
    for sxx in (-1, 1):
        g.box((sxx * cav_w / 2, cy0 + 0.42, hb + p["dt"] / 2), (0.04, 0.74, p["dt"]), mat="stone", tag="cavity_side")
    g.box((0.0, cy0 + 0.42, hb + p["dt"] + 0.02), (cav_w, 0.74, 0.04), mat="stone", tag="cavity_ceiling")
    cc = np.array([0.0, cy0 + 0.40, hb])
    g.box(cc + (0, 0, 0.13), (0.5, 0.32, 0.26), mat="wood", tag="chest", chamfer=0.012 if lod == 0 else 0.0)
    g.cyl(cc + (-0.25, 0, 0.26), cc + (0.25, 0, 0.26), 0.16, n=(10, 7, 4)[lod], mat="wood", tag="chest_lid",
          up=(0, 0, 1))
    if lod < 2:
        for xx in (-0.17, 0.0, 0.17):
            g.box(cc + (xx, 0, 0.14), (0.035, 0.34, 0.3), mat="bronze", tag="chest_band")
    # ---- bronze rim, dial bed, four riveted clamps (painting: back, front, left, right)
    CG.ring_prism(g, (0, 0, 0), np.eye(3), p["Rr"], p["Rr"] - 0.075, n, zt + 0.01, zt + 0.075, "bronze", "bronze_rim")
    CG.disc_prism(g, (0, 0, 0), np.eye(3), None, CG.ngon(p["Rr"] - 0.07, n), zt, zt + 0.07, "bronze", "dial_bed")
    for deg in (90.0, -90.0, 180.0, 0.0):
        a = math.radians(deg)
        er = np.array([math.cos(a), math.sin(a), 0.0])
        et = np.array([-math.sin(a), math.cos(a), 0.0])
        Rm = np.stack([er, et, np.array([0, 0, 1.0])], 1)
        c = er * p["rc"]
        g.box(c + (0, 0, zt + 0.085), (0.2, 0.12, 0.035), R=Rm, mat="bronze", tag="clamp",
              chamfer=0.006 if lod == 0 else 0.0)
        g.box(er * (Rw + 0.035) + (0, 0, zt - 0.015), (0.03, 0.11, 0.17), R=Rm, mat="bronze", tag="clamp")
    # ---- key niche: arched bronze frame + dark back plate on the front-right wall
    a = math.radians(p["an"])
    er = np.array([math.cos(a), math.sin(a), 0.0])
    et = np.array([-math.sin(a), math.cos(a), 0.0])
    base = er * (Rw + 0.01)
    w2 = 0.15
    z0n, z1n = p["nz"] - p["nh"] / 2, p["nz"] + p["nh"] / 2 - w2
    ns = (9, 6, 4)[lod]
    arch = [base + et * (w2 * math.cos(t)) + np.array([0, 0, z1n + w2 * math.sin(t)]) for t in np.linspace(0, math.pi, ns)]
    pathl = [base + et * w2 + np.array([0, 0, z0n])] + arch + [base - et * w2 + np.array([0, 0, z0n])]
    g.tube(np.array(pathl), 0.032, n=(6, 5, 4)[lod], mat="bronze", tag="niche_frame", caps=True)
    back = [(w2 * 0.85 * math.cos(t), z1n + w2 * 0.85 * math.sin(t)) for t in np.linspace(0, math.pi, ns)]
    poly = np.array([(w2 * 0.85, z0n)] + back + [(-w2 * 0.85, z0n)])
    Rm = np.stack([et, np.array([0, 0, 1.0]), er], 1)          # local x = tangent, y = up, z = outward
    g.prism(poly, -0.02, 0.0, "iron", "niche_back", R=Rm, t=base)
    # ---- threshold step in front of the door (the key lies on it)
    g.box((p["sx"], p["sy"], p["sh"] / 2), (p["sw"], p["sd"], p["sh"]), mat="stone", tag="step",
          chamfer=0.02 if lod == 0 else 0.0)
    # ---- door panel (node door_pivot): the wall piece in the opening, slides down into the plinth
    door = A.part("door_pivot", None, (Rw * math.cos(ad), Rw * math.sin(ad), hb))
    arc_wall(door.geo[lod], Rw - 0.15, Rw + 0.004, hb, hb + p["dt"], ad - dh + 0.01, ad + dh - 0.01, max(4, n // 10),
             "stone", "door_panel")
    # ---- discs (nodes ring_1..3), each about its own vertical axis
    for name, (R, cy, zb, ztop) in discs(p).items():
        part = A.part(name, None, (0.0, cy, zb))
        dg = part.geo[lod]
        CG.disc_prism(dg, (0.0, cy, 0.0), np.eye(3), None, CG.ngon(R, n), zb, ztop, "bronze", "disc")
        if lod < 2:
            CG.ring_prism(dg, (0.0, cy, 0.0), np.eye(3), R, R - 0.022, n, ztop, ztop + 0.012, "bronze", "disc_lip")
    # ---- key (node key_lever): bronze rod, collars, claw, green crystal
    kp = key_rest(p)
    key = A.part("key_lever", None, tuple(kp))
    kg = key.geo[lod]
    m = (8, 6, 4)[lod]
    kg.cyl(kp + (-0.24, 0, 0), kp + (0.12, 0, 0), 0.024, n=m, mat="bronze", tag="key_rod", up=(0, 0, 1))
    for xx in (-0.14, 0.06):
        kg.cyl(kp + (xx - 0.015, 0, 0), kp + (xx + 0.015, 0, 0), 0.036, n=m, mat="bronze", tag="key_collar", up=(0, 0, 1))
    kg.cyl(kp + (0.12, 0, 0), kp + (0.17, 0, 0), 0.03, 0.06, n=m, mat="bronze", tag="key_claw", up=(0, 0, 1))
    kg.rock(kp + (0.25, 0, 0.0), (0.085, 0.06, 0.06), seed=3, sub=2 if lod == 0 else 1, mat="gem", tag="key_gem",
            flat_bottom=False, rough=0.05)
    kg.box(kp + (-0.27, 0, -0.012), (0.06, 0.016, 0.07), mat="bronze", tag="key_bit")
    if lod == 0:
        A.marker("artifact_spot", tuple(cc + (0, 0, 0.36)))
    return A


STRICT_FACING = ("stone",)
SWATCHES = {
    "stone": dict(sheet=SHEET, box=(905, 278, 975, 318), metres=0.45),
    "bronze": dict(sheet=SHEET, box=(866, 146, 896, 160), metres=0.18),
    "iron": dict(sheet=SHEET, box=(1050, 245, 1062, 285), metres=0.15),
    "wood": dict(sheet=SHEET, box=(1312, 312, 1345, 336), metres=0.25),
    "gem": dict(sheet=SHEET, box=(992, 352, 1016, 368), metres=0.08),
}


def solve(views):
    params, reps = pv2.solve_views(views, points, PARAMS, FREE, prior_sigma=PRIOR)
    for v in views:
        _resolve_pose(v, params)
    return params


# ------------------------------------------------------------------ glyphs (all ten positions on every disc)
GLYPH_LAYOUT = {   # ring: (glyph centre radius, tangential size, radial size) in metres
    "ring_1": (0.27, 0.15, 0.13), "ring_2": (0.40, 0.2, 0.15), "ring_3": (0.475, 0.22, 0.13)}
GLYPH_FILL = np.array([0.17, 0.18, 0.12])
GLYPH_EDGE = np.array([0.80, 0.60, 0.33])


def _glyph_masks(res=96):
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(here))
    import motifs as mo
    from scipy import ndimage as ndi
    out = {}
    for gname in GLYPHS:
        cv = mo.Canvas((-0.5, -0.5, 0.5, 0.5), ppm=res, max_px=res)
        if gname == "blank":
            cv.ring((0, 0), 0.16, 0.07)
        else:
            mo.glyph(cv, gname, (0, 0), 0.9, 0.11)
        m = np.asarray(cv.im, np.float32) / 255.0
        fill = ndi.gaussian_filter(m, 0.6)
        edge = np.clip(ndi.grey_dilation(m, size=(5, 5)) - m, 0, 1)
        out[gname] = (np.clip(fill, 0, 1), ndi.gaussian_filter(edge, 0.6))
    return out


def _sample(img, u, v):
    """img over [-0.5, 0.5]^2 (row 0 = +0.5 v), nearest sample; outside -> 0."""
    H, W = img.shape
    inside = (np.abs(u) < 0.5) & (np.abs(v) < 0.5)
    x = np.clip(((u + 0.5) * W).astype(int), 0, W - 1)
    y = np.clip(((0.5 - v) * H).astype(int), 0, H - 1)
    return np.where(inside, img[y, x], 0.0)


def post_texture(A, B, alb_img, info, p):
    """Disc tops: remove the painted site-02 glyph strokes (inpaint from the surrounding bronze), then engrave the
    ten positions (k at local angle 270 + 36k deg, glyph 'up' toward the disc centre) in the painted style."""
    import cv2
    P, N, part, yy, xx = info["P"], info["N"], info["part"], info["yy"], info["xx"]
    pn = info["pnames"]
    alb = info["alb"]
    masks = _glyph_masks()
    img8 = (np.clip(alb_img, 0, 1) * 255).astype(np.uint8)
    hole = np.zeros(alb_img.shape[:2], np.uint8)
    sel_all = {}
    for name, (R, cy, zb, ztop) in discs(p).items():
        if name not in pn:
            continue
        sel = (part == pn.index(name)) & (N[:, 2] > 0.85)
        sel_all[name] = sel
        lum = alb[sel] @ np.array([0.299, 0.587, 0.114])
        med = np.median(lum)
        dark = lum < med * 0.7
        idx = np.nonzero(sel)[0][dark]
        hole[yy[idx], xx[idx]] = 255
    hole = cv2.dilate(hole, np.ones((3, 3), np.uint8))
    clean = cv2.inpaint(img8, hole, 4, cv2.INPAINT_TELEA).astype(np.float32) / 255.0
    out = alb_img.copy()
    for name, sel in sel_all.items():
        R, cy, zb, ztop = discs(p)[name]
        rg, gw, gh = GLYPH_LAYOUT[name]
        idx = np.nonzero(sel)[0]
        col = clean[yy[idx], xx[idx]].copy()
        x = P[idx, 0]
        y = P[idx, 1] - cy
        fill = np.zeros(len(idx))
        edge = np.zeros(len(idx))
        for k, gname in enumerate(GLYPHS):
            ang = math.radians(270.0 + STEP * k)
            cx, cyy = rg * math.cos(ang), rg * math.sin(ang)
            # glyph frame: v ('up') toward the disc centre, u = v rotated -90 deg (reads left->right at the front)
            vx, vy = -math.cos(ang), -math.sin(ang)
            ux, uy = vy, -vx
            dxp, dyp = x - cx, y - cyy
            u = (dxp * ux + dyp * uy) / gw
            v = (dxp * vx + dyp * vy) / gh
            f, e = masks[gname]
            fill = np.maximum(fill, _sample(f, u, v))
            edge = np.maximum(edge, _sample(e, u, v))
        col = col * (1 - edge[:, None] * 0.8) + GLYPH_EDGE * edge[:, None] * 0.8
        col = col * (1 - fill[:, None]) + GLYPH_FILL * fill[:, None]
        out[yy[idx], xx[idx]] = col
        alb[idx] = col
    info["alb"] = alb
    pv2.log(f"  [{ID}] disc tops: painted glyph strokes inpainted ({int((hole > 0).sum())} px), 10 glyph positions "
            f"engraved on {len(sel_all)} discs")
    return out


# ------------------------------------------------------------------ clips (same names / nodes as v1)
def _ease(t, a, b):
    return pv2.ease_io((t - a) / max(b - a, 1e-6))


def _out_back(x, s=1.2):
    x = min(max(x, 0.0), 1.0)
    x -= 1.0
    return x * x * ((s + 1) * x + s) + 1.0


def clips(A, B):
    for r in (1, 2, 3):
        for gname in GLYPHS[1:]:
            tgt = ring_angle(gname)
            pv2.add_clip(A, B, f"lf_rune_ring{r}_{gname}", 0.6,
                         {f"ring_{r}": (lambda t, tg=tgt: {"rot": (0, 0, tg * _out_back(t / 0.533))})},
                         markers={"click": 0.5}, note=f"ring {r} turns {gname} to the front index mark")
    p = A._params
    kv = key_in_niche(p) - key_rest(p)

    def key_track(t):
        a = _ease(t, 0.0, 0.53)
        b = _ease(t, 0.53, 0.87)
        lift = math.sin(math.pi * a) * 0.35
        return {"loc": tuple(kv * a + np.array([0, 0, lift])), "rot": (0.0, -math.pi / 2 * a, math.pi / 2 * b)}

    def ring(r, sym):
        return lambda t: {"rot": (0, 0, ring_angle(sym) + math.radians(1.5) * math.sin(math.pi * _ease(t, 0.8, 1.0)))}
    pv2.add_clip(A, B, "lf_lock_mechanism", 1.8, {
        "key_lever": key_track,
        "door_pivot": lambda t: {"loc": (0, 0, -DOOR_DROP * _ease(t, 0.93, 1.67) + 0.01 * math.sin(math.pi * _ease(t, 0.87, 1.0)))},
        "ring_1": ring(1, "mountain"), "ring_2": ring(2, "river"), "ring_3": ring(3, "leaf"),
    }, markers={"key_turned": 26 / 30, "door_open": 50 / 30},
        note="key set into the niche and turned, rings settle, the door slides down into the plinth (solved pose = last frame)")


def meta(A, p):
    g = pv2.b2g
    D = discs(p)
    cy0 = p["Rw"] * math.sin(math.radians(p["ad"]))
    return {
        "mechanism": "rune_lock",
        "symbol_targets": {
            "axis": "each ring disc rotates about glTF +Y through its own node origin (disc centre); discs are stacked rising toward the back",
            "ring_for_progress_step": {"1": "ring_1", "2": "ring_2", "3": "ring_3"},
            "rotation_y_deg": {gname: round(math.degrees(ring_angle(gname)), 2) for gname in GLYPHS},
            "rest_deg": 0.0, "positions_deg_apart": STEP,
            "sites": {s: {f"step{i + 1}": {"symbol": sym, "node": f"ring_{i + 1}",
                                           "rotation_y_deg": round(math.degrees(ring_angle(sym)), 2),
                                           "clip": f"lf_rune_ring{i + 1}_{sym}"} for i, sym in enumerate(v)}
                      for s, v in SITES.items()},
            "wrong_input": "tween the active ring to the chosen symbol (clip lf_rune_ring<k>_<symbol>), then tween all rings "
                           "back to rest_deg (server resets progress)",
            "solved": {"clip": "lf_lock_mechanism", "door_pivot_open_offset_m": [0, -DOOR_DROP, 0],
                       "key_lever_open": "end pose of lf_lock_mechanism"}},
        "sockets": {"artifact_spot": g((0.0, cy0 + 0.40, p["hb"] + 0.36)),
                    "front_index_mark": g((0.0, -p["rc"], p["zt"] + 0.1)),
                    "glyph_front_positions": {nm: g((0.0, D[nm][1] - GLYPH_LAYOUT[nm][0], D[nm][3])) for nm in D}},
        "notes": "v2: geometry measured on both art/10 drawings (closed + open), cameras solved; disc tops carry all ten "
                 "engraved positions (painted style); door panel slides down into the plinth.",
    }
