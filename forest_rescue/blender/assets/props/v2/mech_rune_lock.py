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
KEY_SIZE = 1.9            # the painted key spans ~0.42 of the drum width
# The painting has no absolute scale: the measured blueprint is shrunk uniformly to the v1 delivery's footprint
# (~1.65 m wide) so the site layouts (cage / camp / squad stand-off) keep their spacing; cameras scale along.
MODEL_SCALE = 0.7

# sizes from the closed drawing's image ratios (wall 156 px : clamps 98 : rim 93 : top disc 64 at the dial row)
PARAMS = dict(Rw=1.1, Rt=0.9, Rb=1.14, hb=0.12, ox=0.0, oy=0.0, zt=0.56, Rr=0.64, rc=0.67, dz=0.07,
              R3=0.57, R2=0.53, R1=0.43, y2=0.12, y1=0.24,
              an=-48.0, ad=-86.0, dh=19.0, dt=0.36,
              sx=0.08, sw=1.05, sd=0.36, sh=0.16)
FREE = ["Rw", "R3", "R2", "R1", "y2", "y1", "dh", "dt", "sw", "sd", "sh"]   # heights (zt, dz) held: the
# dial-to-step drop is otherwise explained by depth instead of wall height (one-view ambiguity)
PRIOR = 0.15
# The painting's perspective is not one camera (the dial is drawn steeper than the drum base), so the wall
# silhouette is not a correspondence: cameras come from the dial, clamps, step and door points; the drum's
# plinth radius / height are then chosen by silhouette IoU (solve()).


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


def step_y(p):
    """Threshold step centre (its back edge touches the drum wall in front of the door)."""
    return -p["Rw"] - p["sd"] / 2 + 0.04


def key_rest(p):
    """Key centre lying on the threshold step (rod along X, crystal at +X)."""
    return np.array([p["sx"] - 0.12 + p["ox"], step_y(p) + 0.02 + p["oy"], p["sh"] + 0.045 * KEY_SIZE])


def key_in_niche(p):
    """Key centre standing upright in the niche (crystal on top, just proud of the wall)."""
    a = math.radians(p["an"])
    r = (p["Rw"] + p["Rt"]) * 0.5 + 0.07
    # rod centre in the niche: the bit end inside, the crystal standing above the niche top (art/10 open)
    return np.array([r * math.cos(a) + p["ox"], r * math.sin(a) + p["oy"], p["zt"] * 0.5 + 0.08 + 0.06 * KEY_SIZE])


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
        "wall_l": (-p["Rw"], 0.0, p["zt"] * 0.5), "wall_r": (p["Rw"], 0.0, p["zt"] * 0.5),
        "step_tl": (p["sx"] - p["sw"] / 2, step_y(p) + p["sd"] / 2, p["sh"]),
        "step_tr": (p["sx"] + p["sw"] / 2, step_y(p) + p["sd"] / 2, p["sh"]),
        "step_bl": (p["sx"] - p["sw"] / 2, step_y(p) - p["sd"] / 2, 0.0),
        "step_br": (p["sx"] + p["sw"] / 2, step_y(p) - p["sd"] / 2, 0.0),
        "niche_top": polar(p["Rw"] + 0.03, p["an"], p["zt"] + 0.08),
        "niche_bot": polar(p["Rw"] + 0.03, p["an"], 0.06),
        "door_tl": polar(p["Rw"] + (p["Rt"] - p["Rw"]) * min(p["dt"], p["zt"] - p["hb"]) / (p["zt"] - p["hb"]), p["ad"] - p["dh"], p["hb"] + p["dt"]),
        "door_tr": polar(p["Rw"] + (p["Rt"] - p["Rw"]) * min(p["dt"], p["zt"] - p["hb"]) / (p["zt"] - p["hb"]), p["ad"] + p["dh"], p["hb"] + p["dt"]),
        "door_bl": polar(p["Rw"], p["ad"] - p["dh"], p["hb"]),
        "door_br": polar(p["Rw"], p["ad"] + p["dh"], p["hb"]),
    }
    for key in list(P):
        if key.startswith("step_") or key.startswith("door_") or key.startswith("niche_"):
            P[key] = (P[key][0] + p["ox"], P[key][1] + p["oy"], P[key][2])
    k = key_in_niche(p)
    P["gem_niche"] = (k[0], k[1], k[2] + 0.2)
    S = p.get("_scale", 1.0)
    return {key: (v[0] * S, v[1] * S, v[2] * S) for key, v in P.items()}


def views():
    closed = pv2.ViewSpec(
        "closed", SHEET, (770, 40, 1110, 400),
        {"r1_left": (877.5, 103), "r1_right": (1005, 103), "r1_back": (941, 79), "r1_front": (941, 126),
         "r2_front": (941, 168), "r3_front": (941, 218),
         "clamp_b": (944, 68), "clamp_f": (944, 240), "clamp_l": (847, 146), "clamp_r": (1043, 146),
         "step_tl": (874, 344), "step_tr": (1033, 341), "step_bl": (876, 387), "step_br": (1031, 384)},
        pose=SOLVED_POSE_02, light=LIGHT, thresh=0.085, fill_holes=True, shadow=None, solve_opts={"fov_prior": 20.0},
        clip_below=391, title="RUNE LOCK closed (site 02 glyphs set, key on the step)")
    open_pose = dict(SOLVED_POSE_02)
    open_pose["door_pivot"] = {"loc": (0, 0, -DOOR_DROP)}
    open_pose["key_lever"] = "key_in_niche"
    # pass 4: the dial texture comes from the closed drawing only (two cameras with ~8 px residuals ghosted
    # the glyphs); the open view still renders the rings for its QA comparison
    open_render = dict(open_pose)
    open_proj = dict(open_pose)
    for r in ("ring_1", "ring_2", "ring_3"):
        open_proj[r] = "hide"
    opened = pv2.ViewSpec(
        "open", SHEET, (1156, 40, 1500, 400),
        {"r1_left": (1262, 103), "r1_right": (1398, 103), "r1_back": (1330, 78), "r1_front": (1330, 125),
         "r2_front": (1330, 168), "r3_front": (1330, 218),
         "clamp_b": (1330, 67), "clamp_f": (1331, 240), "clamp_l": (1229, 142), "clamp_r": (1428, 142),
         "step_tl": (1262, 345), "step_tr": (1410, 343), "step_bl": (1265, 380), "step_br": (1408, 377),
         "door_tl": (1290, 272), "door_tr": (1390, 272), "door_bl": (1292, 345), "door_br": (1388, 345)},
        pose=open_proj, render_pose=open_render, light=LIGHT, thresh=0.085, fill_holes=True, shadow=None,
        solve_opts={"fov_prior": 20.0}, clip_below=386, title="RUNE LOCK open (door down, key in the niche)",
        tex_weight=0.9)
    return [closed, opened]


def _resolve_pose(v, p):
    S = p.get("_scale", 1.0)
    for pose in (v.pose, v.render_pose):
        if pose is None:
            continue
        if "door_pivot" in pose:
            pose["door_pivot"] = {"loc": (0, 0, -DOOR_DROP * S)}
        if pose.get("key_lever") == "key_in_niche" or isinstance(pose.get("key_lever"), dict):
            pose["key_lever"] = {"loc": tuple((key_in_niche(p) - key_rest(p)) * S), "rot": (0.0, -math.pi / 2, 0.0)}


def arc_wall(g, r0, r1, z0, z1, a0, a1, n, mat, tag, top=True, ends=True, r1_top=None):
    """Thick wall segment between angles a0..a1 (radians, CCW), inner r0, outer r1 (r1_top at z1: tapered)."""
    a = np.linspace(a0, a1, n + 1)
    V = []
    for k, rr in enumerate((r1, r0)):
        for z in (z0, z1):
            r = rr if (k == 1 or r1_top is None or z == z0) else r1_top
            for ang in a:
                V.append((r * math.cos(ang), r * math.sin(ang), z))
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
    A._params = p
    g = A.g("root", lod)
    n = (64, 40, 24)[lod]
    Rw, Rb, hb, zt = p["Rw"], p["Rb"], p["hb"], p["zt"]
    ad, dh = math.radians(p["ad"]), math.radians(p["dh"])
    # ---- plinth course + masonry wall with the door opening (front) + stone rim (drum offset ox, oy)
    O = np.array([p["ox"], p["oy"], 0.0])
    gd = pv2.G.Geo()
    g_root = g
    g = gd
    # stepped plinth (art/10): two courses stepping in to the vertical drum wall
    CG.ring_prism(g, (0, 0, 0), np.eye(3), Rb, Rw - 0.3, n, 0.0, hb, "stone", "plinth")
    CG.ring_prism(g, (0, 0, 0), np.eye(3), (Rb + Rw) * 0.5, Rw - 0.3, n, hb, hb + 0.09, "stone", "plinth_step")
    Rt = p["Rt"]

    def r_at(z):         # tapered drum (art/10: the base is drawn wider than the rim)
        return Rw + (Rt - Rw) * (z - hb) / max(zt - hb, 1e-6)
    arc_wall(g, Rt - 0.17, Rw, hb, zt, ad + dh, ad - dh + 2 * math.pi, n - 4, "stone", "wall", top=False, r1_top=Rt)
    # lintel over the door (the wall above the opening) and the jamb returns
    zd = min(hb + p["dt"], zt - 0.05)
    arc_wall(g, Rt - 0.17, r_at(zd), zd, zt, ad - dh, ad + dh, max(4, n // 10), "stone", "lintel", top=False,
             ends=False, r1_top=Rt)
    CG.ring_prism(g, (0, 0, 0), np.eye(3), Rt + 0.025, p["Rr"] + 0.02, n, zt, zt + 0.06, "stone", "rim")
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
    # ---- bronze rim, dial bed, four riveted clamps (painting: back, front, left, right): on the dial axis
    g = g_root
    CG.ring_prism(g, (0, 0, 0), np.eye(3), p["Rr"], p["Rr"] - 0.075, n, zt + 0.01, zt + 0.075, "bronze", "bronze_rim")
    CG.disc_prism(g, (0, 0, 0), np.eye(3), CG.ngon(p["Rr"] - 0.07, n), zt, zt + 0.07, "bronze", "dial_bed")
    for deg in (90.0, -90.0, 180.0, 0.0):
        a = math.radians(deg)
        er = np.array([math.cos(a), math.sin(a), 0.0])
        et = np.array([-math.sin(a), math.cos(a), 0.0])
        Rm = np.stack([er, et, np.array([0, 0, 1.0])], 1)
        c = er * p["rc"]
        g.box(c + (0, 0, zt + 0.085), (0.2, 0.12, 0.035), R=Rm, mat="bronze", tag="clamp",
              chamfer=0.006 if lod == 0 else 0.0)
        g.box(er * (Rt + 0.035) + (0, 0, zt - 0.015), (0.03, 0.11, 0.17), R=Rm, mat="bronze", tag="clamp")
    # ---- key niche: arched bronze frame + dark back plate on the front-right wall (drum group)
    g = gd
    a = math.radians(p["an"])
    er = np.array([math.cos(a), math.sin(a), 0.0])
    et = np.array([-math.sin(a), math.cos(a), 0.0])
    base = er * (r_at(zt * 0.5) + 0.01)
    w2 = 0.15
    z0n, z1n = 0.06, p["zt"] + 0.08 - w2
    ns = (9, 6, 4)[lod]
    arch = [base + et * (w2 * math.cos(t)) + np.array([0, 0, z1n + w2 * math.sin(t)]) for t in np.linspace(0, math.pi, ns)]
    pathl = [base + et * w2 + np.array([0, 0, z0n])] + arch + [base - et * w2 + np.array([0, 0, z0n])]
    g.tube(np.array(pathl), 0.032, n=(6, 5, 4)[lod], mat="bronze", tag="niche_frame", caps=True)
    back = [(w2 * 0.85 * math.cos(t), z1n + w2 * 0.85 * math.sin(t)) for t in np.linspace(0, math.pi, ns)]
    poly = np.array([(w2 * 0.85, z0n)] + back + [(-w2 * 0.85, z0n)])
    Rm = np.stack([et, np.array([0, 0, 1.0]), er], 1)          # local x = tangent, y = up, z = outward
    g.prism(poly, -0.02, 0.0, "iron", "niche_back", R=Rm, t=base)
    # ---- threshold step in front of the door (the key lies on it)
    g.box((p["sx"], step_y(p), p["sh"] / 2), (p["sw"], p["sd"], p["sh"]), mat="stone", tag="step",
          chamfer=0.02 if lod == 0 else 0.0)
    gd.transform(None, O)
    g = g_root
    g.extend(gd)
    # ---- door panel (node door_pivot): the wall piece in the opening, slides down into the plinth
    door = A.part("door_pivot", None, (Rw * math.cos(ad) + O[0], Rw * math.sin(ad) + O[1], hb))
    dgeo = pv2.G.Geo()
    arc_wall(dgeo, Rt - 0.15, Rw + 0.004, hb, zd, ad - dh + 0.01, ad + dh - 0.01, max(4, n // 10),
             "stone", "door_panel", r1_top=r_at(zd) + 0.004)
    door.geo[lod].extend(dgeo.transform(None, O))
    # ---- discs (nodes ring_1..3), each about its own vertical axis
    for name, (R, cy, zb, ztop) in discs(p).items():
        part = A.part(name, None, (0.0, cy, zb))
        dg = part.geo[lod]
        CG.disc_prism(dg, (0.0, cy, 0.0), np.eye(3), CG.ngon(R, n), zb, ztop, "bronze", "disc")
        if lod < 2:
            CG.ring_prism(dg, (0.0, cy, 0.0), np.eye(3), R, R - 0.022, n, ztop, ztop + 0.012, "bronze", "disc_lip")
    # ---- key (node key_lever): bronze rod, collars, claw, green crystal
    kp = key_rest(p)
    key = A.part("key_lever", None, tuple(kp))
    kg = key.geo[lod]
    m = (8, 6, 4)[lod]
    K = KEY_SIZE
    kg.cyl(kp + (-0.24 * K, 0, 0), kp + (0.12 * K, 0, 0), 0.024 * K, n=m, mat="bronze", tag="key_rod", up=(0, 0, 1))
    for xx in (-0.14, 0.06):
        kg.cyl(kp + ((xx - 0.015) * K, 0, 0), kp + ((xx + 0.015) * K, 0, 0), 0.036 * K, n=m, mat="bronze", tag="key_collar",
               up=(0, 0, 1))
    kg.cyl(kp + (0.12 * K, 0, 0), kp + (0.17 * K, 0, 0), 0.03 * K, 0.06 * K, n=m, mat="bronze", tag="key_claw", up=(0, 0, 1))
    kg.rock(kp + (0.25 * K, 0, 0.0), (0.085 * K, 0.06 * K, 0.06 * K), seed=3, sub=2 if lod == 0 else 1, mat="gem",
            tag="key_gem", flat_bottom=False, rough=0.05)
    kg.box(kp + (-0.27 * K, 0, -0.012 * K), (0.06 * K, 0.016 * K, 0.07 * K), mat="bronze", tag="key_bit")
    S = p.get("_scale", 1.0)
    if lod == 0:
        A.marker("artifact_spot", tuple((cc + O + (0, 0, 0.36)) * S))
    if S != 1.0:
        for part in A.parts.values():
            gg = part.geo[lod]
            gg.V = [V * S for V in gg.V]
            if not getattr(part, "_scaled", False):
                part.pivot = part.pivot * S
                part._scaled = True
    return A


STRICT_FACING = ("stone",)
SWATCHES = {
    "stone": dict(sheet=SHEET, box=(905, 278, 975, 318), metres=0.45),
    "bronze": dict(sheet=SHEET, box=(866, 146, 896, 160), metres=0.18),
    "iron": dict(sheet=SHEET, box=(1050, 245, 1062, 285), metres=0.15),
    "wood": dict(sheet=SHEET, box=(1312, 312, 1345, 336), metres=0.25),
    "gem": dict(sheet=SHEET, box=(992, 352, 1016, 368), metres=0.08),
}


def _silhouette_iou(p, views):
    """Mean silhouette IoU of the LOD2 blueprint over the solved views (polygon fill, no z-buffer needed)."""
    import cv2
    A = pv2.Asset(ID, ATLAS)
    build(A, p, 2)
    out = []
    for v in views:
        Wm = A.world_mats(v.pose)
        W_, H_ = v.size
        m = np.zeros((H_, W_), np.uint8)
        for nm, part in A.parts.items():
            M = Wm.get(nm)
            if M is None:
                continue
            V, F, _, _, _ = part.geo[2].arrays()
            if not len(V):
                continue
            Vw = V @ M[:3, :3].T + M[:3, 3]
            u, w, _z = v.cam.project(Vw)
            pts = np.stack([u, w], 1)
            for f in F:     # one convex face at a time (a multi-contour fillPoly XORs the overlaps)
                cv2.fillConvexPoly(m, np.round(pts[f]).astype(np.int32), 1)
        ref, _ = v.mask()
        mm = m.astype(bool)
        out.append(float((mm & ref).sum()) / max(1.0, float((mm | ref).sum())))
    return float(np.mean(out)), out


def solve(views):
    params, reps = pv2.solve_views(views, points, PARAMS, FREE, prior_sigma=PRIOR)
    for v in views:
        _resolve_pose(v, params)
    # plinth flare / height by silhouette IoU (the drum base is drawn wider than the dial's camera implies)
    # drum taper (rim radius Rt) and plinth (Rb, hb) by silhouette IoU, coordinate descent
    best = _silhouette_iou(params, views)[0]
    # pass 4: near-vertical walls (no taper buying the camera residual): only the plinth steps, the drum
    # radius and its offset under the dial are searched
    params["Rt"] = params["Rw"] - 0.03
    grids = {"Rb": np.arange(params["Rw"] + 0.06, params["Rw"] + 0.3, 0.03),
             "hb": np.array([0.08, 0.12, 0.16, 0.2]), "ox": np.arange(-0.1, 0.101, 0.02),
             "oy": np.arange(-0.1, 0.101, 0.02), "Rw": np.arange(params["Rw"] - 0.15, params["Rw"] + 0.151, 0.03)}
    for _round in range(2):
        for key, grid in grids.items():
            for val in grid:
                q = dict(params)
                q[key] = float(val)
                if key == "Rw":
                    q["Rt"] = q["Rw"] - 0.03
                iou = _silhouette_iou(q, views)[0]
                if iou > best + 1e-4:
                    best, params = iou, q
    pv2.log(f"  drum by silhouette IoU: Rt {params['Rt']:.3f} Rb {params['Rb']:.3f} hb {params['hb']:.2f} -> mean IoU "
            f"{best:.3f} {[round(x, 3) for x in _silhouette_iou(params, views)[1]]}")
    params["_scale"] = MODEL_SCALE
    for v in views:
        _resolve_pose(v, params)
        c = v.cam
        v.cam = type(c)(c.f, c.cx, c.cy, c.rvec, c.tvec * MODEL_SCALE, c.k1, c.k2, size=c.size)
    return params


# ------------------------------------------------------------------ glyphs (all ten positions on every disc)
GLYPH_LAYOUT = {   # ring: (glyph centre radius, tangential size, radial size) in metres — pass 4: small, near the rim
    "ring_1": (0.29, 0.085, 0.075), "ring_2": (0.4, 0.09, 0.08), "ring_3": (0.5, 0.09, 0.075)}
ENGRAVE_DEPTH = 0.32      # pass 4: shallow, low contrast (share of the way to the dark fill colour)
PAINTED = {"ring_1": "mountain", "ring_2": "river", "ring_3": "leaf"}   # painted (projected), kept big and clean
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
    P = P / p.get("_scale", 1.0)          # blueprint units (discs(), GLYPH_LAYOUT)
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
        if name in PAINTED:
            continue        # every ring keeps its painted front glyph (mountain / river / leaf), no inpainting
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
        painted = PAINTED.get(name)
        for k, gname in enumerate(GLYPHS):
            if gname == painted:
                continue
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
        col = col * (1 - edge[:, None] * 0.25) + GLYPH_EDGE * edge[:, None] * 0.25
        fill_col = col * 0.62                                   # darker bronze, not black: a shallow engraving
        col = col * (1 - fill[:, None] * ENGRAVE_DEPTH) + fill_col * fill[:, None] * ENGRAVE_DEPTH
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
    S = p.get("_scale", 1.0)
    kv = (key_in_niche(p) - key_rest(p)) * S

    def key_track(t):
        a = _ease(t, 0.0, 0.53)
        b = _ease(t, 0.53, 0.87)
        lift = math.sin(math.pi * a) * 0.35 * S
        return {"loc": tuple(kv * a + np.array([0, 0, lift])), "rot": (0.0, -math.pi / 2 * a, math.pi / 2 * b)}

    def ring(r, sym):
        return lambda t: {"rot": (0, 0, ring_angle(sym) + math.radians(1.5) * math.sin(math.pi * _ease(t, 0.8, 1.0)))}
    pv2.add_clip(A, B, "lf_lock_mechanism", 1.8, {
        "key_lever": key_track,
        "door_pivot": lambda t: {"loc": (0, 0, (-DOOR_DROP * _ease(t, 0.93, 1.67) + 0.01 * math.sin(math.pi * _ease(t, 0.87, 1.0))) * S)},
        "ring_1": ring(1, "mountain"), "ring_2": ring(2, "river"), "ring_3": ring(3, "leaf"),
    }, markers={"key_turned": 26 / 30, "door_open": 50 / 30},
        note="key set into the niche and turned, rings settle, the door slides down into the plinth (solved pose = last frame)")


def meta(A, p):
    S = p.get("_scale", 1.0)

    def g(v):
        return pv2.b2g(tuple(np.asarray(v, float) * S))
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
            "solved": {"clip": "lf_lock_mechanism", "door_pivot_open_offset_m": [0, round(-DOOR_DROP * S, 4), 0],
                       "key_lever_open": "end pose of lf_lock_mechanism"}},
        "sockets": {"artifact_spot": g((p["ox"], cy0 + 0.40 + p["oy"], p["hb"] + 0.36)),
                    "front_index_mark": g((0.0, -p["rc"], p["zt"] + 0.1)),
                    "glyph_front_positions": {nm: g((0.0, D[nm][1] - GLYPH_LAYOUT[nm][0], D[nm][3])) for nm in D}},
        "notes": "v2: geometry measured on both art/10 drawings (closed + open), cameras solved; disc tops carry all ten "
                 "engraved positions (painted style); door panel slides down into the plinth.",
    }
