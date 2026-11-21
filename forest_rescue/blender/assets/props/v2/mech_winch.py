"""lf_mechanism_winch_sequence v2, material path (iter 15+), from art/10_artifact_mechanisms.png (lower left main
view): two oak A-frame trestles (front + back frames, splayed legs, top blocks, iron straps / bands / shoes with
bolt heads, cross beams), a top rail and a tie beam with a diagonal brace and a back post, the rope drum (oak core,
thick coiled rope, iron flanges), the big toothed iron gear on the drum's left end and the smaller pinion meshing
with it on the left trestle (both coplanar, tilted toward the viewer as painted), the brass brake lever with its
round knob, the forged L-shaped crank with a turned wooden grip outside the right trestle (bearing housing turned
to the viewer as painted), the rope down to the iron-banded chest, and the square stone-lined pit with rubble,
grass tufts and a dirt patch.

Material path (pv2mat): clean modelled geometry, no alpha; every surface samples a seamless painted-style tile of
its material (wood, iron, rope, stone, brass, ground, grass, void) box-mapped in metres (grain along each beam,
rope turns round the drum); tile colours are measured on the painting's own pixels of that material.

Same node / clip contract as before (actor_director, meta.symbol_targets): brake_lever, pawl, crank, drum, rope
(scales along its own length), chest (+ chest_lid, artifact_spot), big_gear, pinion; clips lf_winch_brake (0.6 s,
brake_set), lf_winch_pawl (0.5 s, pawl_engaged), lf_rope_release (1.3 s, chest_clear_of_pit), lf_lock_mechanism
(1.8 s, lid_unlocked, lid_open). Gear train: the big gear (25 teeth) turns with the drum, the pinion (16 teeth)
the other way at 25/16 = 1.5625, the crank 1:1 on the axle. Rest = chest at the bottom of the pit.
New node pit_void: the dark pit mouth (the game lifts it to the terrain surface, see actor_director).
"""
import math
import sys

import numpy as np

import cagegeo as CG
import geo as G
import pv2

ID = "lf_mechanism_winch_sequence"
ATLAS = 2048                 # unused by the material path (shared driver signature)
SHEET = "10_artifact_mechanisms.png"
LIGHT = (-0.55, -0.5, 0.67)
BUDGET = "mechanism LOD0 <= 6000 tris"
MATERIAL_MODE = True
PAINT_K = 0.55               # paintedLightMix: the tiles carry no painted light, the engine light gives the form

PIT_D = 1.0
CHEST_TOP_CLEAR = 0.1        # end of the raise: chest bottom this far above the ground (clear of the pit mouth)
BRAKE_ON = math.radians(-48)
PAWL_ON = math.radians(-24)
GEAR_TEETH = 25              # big gear on the drum's left end (the pawl clicks over it)
PINION_TEETH = 16            # 25 / 16 = 1.5625
RATIO = GEAR_TEETH / PINION_TEETH

PARAMS = dict(AX=2.188, L2=0.512, Rc=0.41, FXL=1.264, FXR=0.876, HX=1.164, KX=-0.7525, Ls=0.419, Ac=0.762, Lg=0.56,
              PR=0.80, PY=-0.18, Wc=0.925, Hc=0.5375, Zt=0.353,
              SPL=0.48, WH=0.38, TB=0.45, LW=0.245, FY=0.42, TZ=0.62, SPIL=0.30, SPIR=0.0, PX=-0.22, PSX=-0.35,
              RGP=0.52, GT=45.0, PH=199.0, GBX=0.15, GBY=-0.22, GBZ=0.1, HR=0.19)
FREE = ["AX", "L2", "Rc", "FXL", "FXR", "HX", "KX", "Ls", "Ac", "Lg", "Wc", "Hc", "Zt", "PH", "GBX", "GBZ"]
PRIOR = 0.2

# ---------------------------------------------------------------------------------------------- materials
CLASSES = ("wood", "iron", "rope", "stone", "brass", "ground", "grass", "void")
TILE_M = {"wood": 0.9, "iron": 0.45, "rope": 0.28, "stone": 0.7, "brass": 0.22, "ground": 2.2, "grass": 1.0}
ROPE_ROWS = 4                # rope tile: 4 turns across v
ROPE_D = 0.11                # rope diameter on the drum (one row): art/10 shows ~9 turns across the coil
VOID_COLOUR = (0.055, 0.045, 0.038)
# game sun (forest_world SUN_ROTATION) in the model's frame at the device yaw 45 deg (Blender axes)
GAME_LIGHT = (-0.652, -0.15, 0.743)
SMOOTH_ANGLE = 40.0
# baked vertex AO (pv2mat.bake_vertex_ao): static parts occlude each other (the drum, gears and crank turn in
# place), the chest / lid only themselves (they travel), rope and pit void none; soft sun shadow toward the
# light between the painting's and the game's (model space)
AO_SUN = (-0.612, -0.331, 0.719)
AO_STRENGTH = 0.55
AO_SUN_STRENGTH = 0.38
AO_DIST = 0.9
AO_CLASS_STRENGTH = {"ground": 0.35, "grass": 0.25, "rope": 0.45}
SHARP_TAGS = ("rubble", "lip", "pit_ring", "leg", "cross", "top_block", "tie", "post", "brace", "top_rail")
NO_CALIBRATE = ("brass", "iron", "wood", "stone")
WOOD_BOXES = [(340, 690, 362, 745), (78, 650, 108, 735), (322, 595, 345, 640), (285, 650, 330, 664), (240, 690, 262, 740)]
STONE_BOXES = [(22, 778, 112, 828), (380, 800, 440, 835), (140, 790, 210, 840), (300, 852, 360, 872)]
IRON_BOXES = [(98, 553, 150, 568), (320, 668, 378, 688), (62, 748, 118, 776), (354, 752, 392, 790), (380, 588, 412, 622),
              (190, 560, 210, 640), (318, 548, 392, 568)]
GRASS_BOXES = [(30, 690, 72, 760), (455, 742, 500, 790), (160, 840, 200, 862), (8, 760, 40, 800)]
_STATIC = ("root", "drum", "big_gear", "pinion", "crank")


def ao_occluders(part):
    if part in _STATIC or part in ("brake_lever", "pawl"):
        return _STATIC + (part,)
    if part in ("chest", "chest_lid"):
        return ("chest", "chest_lid")
    return ()


def make_tiles(px, sheet, rng):
    """Default painting-measured tiles, brass from the lit half of its painted pixels (the painting's brass reads by
    its highlights; the game has no specular)."""
    import pv2mat
    import mattex as MT
    px = dict(px)
    gp = MT.pixels(sheet, GRASS_BOXES, lambda c: (c[:, 1] >= c[:, 0] - 0.03) & (c[:, 1] - c[:, 2] > 0.07))
    if len(gp) > 60:
        px["grass"] = gp
    # iron from the painted brackets / shoes / housing / gear rim themselves (dark forged body; the brightest
    # pixels are the painting's edge highlights)
    ip = MT.pixels(sheet, IRON_BOXES, lambda c: ((c @ MT.LUMA) < 0.62) & (c[:, 0] - c[:, 2] < 0.2))
    if len(ip) > 200:
        px["iron"] = ip
    wp = MT.pixels(sheet, WOOD_BOXES, lambda c: (c[:, 0] - c[:, 2] > 0.1) & ((c @ MT.LUMA) > 0.22) & ((c @ MT.LUMA) < 0.72))
    if len(wp) > 200:
        px["wood"] = wp
    sp = MT.pixels(sheet, STONE_BOXES, lambda c: (np.abs(c[:, 0] - c[:, 2]) < 0.13) & ((c @ MT.LUMA) > 0.16))
    if len(sp) > 200:
        px["stone"] = sp
    if "brass" in px and len(px["brass"]) > 80:
        b = px["brass"]
        px["brass"] = b[(b @ MT.LUMA) > np.percentile(b @ MT.LUMA, 45)]
    return pv2mat.default_tiles(sys.modules[__name__], px, sheet, rng)


TILE_CHROMA = 1.15
# trim mapping (pv2mat): beam / strap faces up to this wide take the tile across their width; the wood tile's
# borders darken (art/10 paints every timber edge dark), the iron tile's lighten (worn bevels catch the light)
TRIM_CLASSES = {"wood": 0.42, "iron": 0.3}
TRIM_AMOUNT = {"wood": -0.5, "iron": 0.75}
TRIM_WIDTH = {"wood": 0.04, "iron": 0.06}
TRIM_TAGS = {"wood": ("leg", "cross", "top_block", "top_rail", "tie", "post", "brace", "chest_plinth"),
             "iron": ("strap", "band", "shoe", "housing_plate", "pinion_bracket", "lever_bracket", "chest_band",
                      "crank_arm", "gear", "pinion", "chest_lock")}
# gear train / crank check: lf_rope_release frames, front-plane box (model metres x0, z0, x1, z1)
CLIP_SHEET = {"clip": "lf_rope_release", "times": (0.0, 0.45, 0.8, 1.3), "box": (-1.9, 1.3, 2.3, 3.2)}
# QA close-ups (sheet px): gears, crank, chest + pit, left trestle top + brake
CLOSEUPS = [(100, 510, 280, 680), (360, 560, 520, 712), (180, 728, 380, 876), (40, 515, 200, 650)]
# UV rules per tag prefix (pv2mat.assign_uvs): default "box" = metre box mapping in the primitive's own frame,
# u along its longest axis (grain along every beam); "coil" = rope turns round the drum axle (X); "tube" = rope
# along its length; "fixed" = UVs authored with the geometry (grass blades)
UV_RULES = {"coil": "coil", "rope": "tube", "sling": "tube", "grass": "fixed", "pit_void": "fixed"}


def rise(p):
    """(travel, z_bottom): chest bottom from the pit floor to just above the pit mouth (end of the raise)."""
    z_bottom = -PIT_D + 0.02
    return CHEST_TOP_CLEAR - z_bottom, z_bottom


def drawn_lift(p):
    """Chest lift of the painted view (art/10: the chest hangs at the pit mouth, top at Zt)."""
    _, z_bottom = rise(p)
    return (p["Zt"] - p["Hc"]) - z_bottom


def rope_len(p):
    _, z_bottom = rise(p)
    return p["AX"] - (z_bottom + p["Hc"] + 0.22)


def drawn_pose(p):
    """Node pose of the painted view: chest at the pit mouth, rope shortened to its hook."""
    lift = drawn_lift(p)
    L0 = rope_len(p)
    return {"chest": {"loc": (0, 0, lift)}, "rope": {"scale": (1, 1, (L0 - lift) / L0)}}


def points(p):
    AX, L2, Rc = p["AX"], p["L2"], p["Rc"]
    H = p["HX"]
    zt = p["Zt"]
    gc, _, _, _ = big_gear_frame(p)
    return {
        "coil_lt": (-L2, 0.0, AX + Rc), "coil_rt": (L2, 0.0, AX + Rc),
        "coil_lb": (-L2, 0.0, AX - Rc), "coil_rb": (L2, 0.0, AX - Rc),
        "hub_c": (H + 0.04, -0.36, AX), "shaft_end": (H + p["Ls"], -0.05, AX),
        "grip_in": (H + p["Ls"] + 0.04, -0.1, AX - p["Ac"]), "grip_out": (H + p["Ls"] + 0.04 + p["Lg"], -0.1, AX - p["Ac"]),
        "gear_c": tuple(pinion_centre(p)), "bgear_c": tuple(gc), "knob": (p["KX"], -0.28, AX + 0.78),
        "ttop_l": (-p["FXL"], 0.0, AX + 0.6), "ttop_r": (p["FXR"], 0.0, AX + 0.6),
        "chest_tl": (-p["Wc"] / 2, p["PY"] - 0.25, zt), "chest_tr": (p["Wc"] / 2, p["PY"] - 0.25, zt),
        "chest_bl": (-p["Wc"] / 2, p["PY"] - 0.25, zt - p["Hc"]), "chest_br": (p["Wc"] / 2, p["PY"] - 0.25, zt - p["Hc"]),
    }


def views():
    v = pv2.ViewSpec(
        "main", SHEET, (0, 500, 530, 878),
        {"coil_lt": (225, 556), "coil_rt": (330, 556), "coil_lb": (225, 641), "coil_rb": (330, 641),
         "hub_c": (397, 605), "shaft_end": (440, 603), "grip_in": (447, 680), "grip_out": (505, 690),
         "gear_c": (166, 621), "bgear_c": (229, 591), "knob": (192, 522), "ttop_l": (148, 535), "ttop_r": (368, 535),
         "chest_tl": (222, 795), "chest_tr": (318, 797), "chest_bl": (222, 850), "chest_br": (316, 850)},
        pose={"chest": "raised"}, light=LIGHT, thresh=0.085, fill_holes=True, shadow=None,
        solve_opts={"fov_prior": 22.0, "f_prior": (1370.0, 0.08)}, title="WINCH main view (chest raised to the pit mouth)",
        # the painted motion arrows are annotations, not geometry
        ignore_boxes=[(148, 610, 195, 660), (418, 572, 472, 652), (280, 712, 306, 768)],
        proj_exclude=[(148, 610, 195, 660), (418, 572, 472, 652), (280, 712, 306, 768)])
    return [v]


# ---------------------------------------------------------------------------------------------- gear train
def big_gear_frame(p):
    """Centre, axis and in-plane axes (gu, gw) of the big gear. Painter's cheat (art/10): the wheel on the drum's
    left end is turned GT about the vertical so its face shows to the viewer as a full toothed circle; its left
    half lies in front of the left trestle's legs, its right half behind the rope coil."""
    t = math.radians(p["GT"])
    axis = np.array([math.cos(t), -math.sin(t), 0.0])
    gu = np.array([math.sin(t), math.cos(t), 0.0])
    gw = np.array([0.0, 0.0, 1.0])
    c = np.array([-p["L2"] - 0.14 + p["GBX"], p["GBY"], p["AX"] + p["GBZ"]])
    return c, axis, gu, gw


def gear_radii(p):
    """Pitch / root / tip radii of the big gear and the pinion (same module: pitch radius ~ tooth count)."""
    rg = p["RGP"]
    rp = rg * PINION_TEETH / GEAR_TEETH
    m = 2 * rg / GEAR_TEETH                       # module (m)
    return dict(rg=rg, rp=rp, add=m * 1.0, ded=m * 1.15)


def pinion_centre(p):
    """Coplanar with the big gear, meshing at its lower left (angle PH in the gear plane)."""
    gc, _, gu, gw = big_gear_frame(p)
    r = gear_radii(p)
    a = math.radians(p["PH"])
    return gc + (r["rg"] + r["rp"]) * (math.cos(a) * gu + math.sin(a) * gw)


def tooth_outline(n, r_root, r_tip, phase, lod):
    """Trapezoid teeth (tooth centres at phase + (k + 1/2) * 2 pi / n), CCW in the gear plane."""
    pts = []
    da = 2 * math.pi / n
    prof = ((-0.31, r_root), (-0.16, r_tip), (0.16, r_tip), (0.31, r_root)) if lod < 2 else ((-0.28, r_root), (0.0, r_tip), (0.28, r_root))
    for k in range(n):
        ac = phase + (k + 0.5) * da
        for f, r in prof:
            pts.append((r * math.cos(ac + f * da), r * math.sin(ac + f * da)))
    return np.array(pts)


def rim_open_back(g, c, Rm, outer, inner, z0, z1, tag):
    """Toothed rim: outer (teeth) and inner walls plus the front face (+axis, toward the viewer); the back face is
    never seen from the painting or the city camera and is left open (double-sided painted shader)."""
    n = len(outer)
    V = []
    for z in (z0, z1):
        for q in outer:
            V.append((q[0], q[1], z))
        for q in inner:
            V.append((q[0], q[1], z))
    V = np.array(V) @ np.asarray(Rm).T + np.asarray(c, float)
    F = []
    o0, i0, o1, i1 = 0, n, 2 * n, 3 * n
    for k in range(n):
        k2 = (k + 1) % n
        F.append([o0 + k, o0 + k2, o1 + k2, o1 + k])
        F.append([i0 + k2, i0 + k, i1 + k, i1 + k2])
        F.append([o1 + k, o1 + k2, i1 + k2, i1 + k])
    return g.add(V, F, "iron", tag)


def gear(g, c, Rm, n, r_pitch, add, ded, phase, half_t, lod, tag, spokes, hub_r, hub_half, r_in_k=0.78):
    """Toothed iron wheel in the plane of Rm (columns: in-plane u, in-plane w, axis): rim with real teeth, a hub
    boss through the axis and flat spokes."""
    r_root, r_tip = r_pitch - ded, r_pitch + add
    outer = tooth_outline(n, r_root, r_tip, phase, lod)
    r_in = r_root * r_in_k
    inner = np.array([(r_in * math.cos(math.atan2(q[1], q[0])), r_in * math.sin(math.atan2(q[1], q[0]))) for q in outer])
    rim_open_back(g, c, Rm, outer, inner, -half_t, half_t, tag + "_rim")
    axis = Rm[:, 2]
    g.cyl(tuple(c - axis * hub_half), tuple(c + axis * hub_half), hub_r, n=(14, 10, 8)[lod], mat="iron",
          tag=tag + "_hub", up=tuple(Rm[:, 1]))
    for k in range(spokes):
        a = phase + 2 * math.pi * (k + 0.25) / spokes
        d = Rm[:, 0] * math.cos(a) + Rm[:, 1] * math.sin(a)
        g.beam(tuple(c + d * hub_r * 0.8), tuple(c + d * (r_in + 0.02)), half_t * 1.7, half_t * 1.3, up=tuple(axis),
               mat="iron", tag=tag + "_spoke")


# ---------------------------------------------------------------------------------------------- small parts
def unit(v):
    v = np.asarray(v, float)
    return v / max(np.linalg.norm(v), 1e-12)


def bolt(g, p, n, r=0.034, h=0.028, k=5, tag="bolt", mat="brass"):
    """Domed bolt head on a face (base ring at p, outward normal n): k-sided frustum + cap."""
    n = unit(n)
    R = G.frame_from(n)
    a = np.linspace(0, 2 * math.pi, k, endpoint=False) + 0.3
    ring0 = [np.asarray(p) + r * (math.cos(t) * R[:, 1] + math.sin(t) * R[:, 2]) for t in a]
    ring1 = [np.asarray(p) + n * h + 0.55 * r * (math.cos(t) * R[:, 1] + math.sin(t) * R[:, 2]) for t in a]
    V = np.array(ring0 + ring1)
    F = [[i, (i + 1) % k, k + (i + 1) % k, k + i] for i in range(k)] + [[k + i for i in range(k)]]
    F2 = []
    for f in F:
        P = V[f]
        nrm = np.cross(P[1] - P[0], P[2] - P[0])
        if nrm @ (P.mean(0) - (np.asarray(p) - n * 0.01)) < 0:
            f = f[::-1]
        F2.append(f)
    return g.add(V, F2, mat, tag)


def tuft(g, base, rng, n=6, h=0.32, spread=0.1, lean=0.35, w=0.04, tag="grass"):
    """Grass tuft: n bent blades (quad + tip triangle), UVs fixed (u across, v = 0 root .. 1 tip)."""
    base = np.asarray(base, float)
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0, spread)
        b = base + np.array([r * math.cos(a), r * math.sin(a), 0.0])
        hh = h * rng.uniform(0.55, 1.1)
        la = rng.uniform(0, 2 * math.pi)
        ld = np.array([math.cos(la), math.sin(la), 0.0]) * rng.uniform(0.12, lean) * hh
        side = np.array([-math.sin(la + 1.2), math.cos(la + 1.2), 0.0]) * w * rng.uniform(0.7, 1.2) / 2
        mid = b + np.array([0, 0, hh * 0.55]) + ld * 0.35
        tip = b + np.array([0, 0, hh]) + ld
        V = np.array([b - side, b + side, mid + side * 0.7, mid - side * 0.7, tip])
        g.add(V, [[0, 1, 2, 3], [3, 2, 4]], "grass", tag,
              uv=[[(0.0, 0.0), (1.0, 0.0), (0.85, 0.55), (0.15, 0.55)], [(0.15, 0.55), (0.85, 0.55), (0.5, 1.0)]])


def band_on_beam(g, p0, p1, at, lw, lh, length, up=(0, 0, 1), tag="band"):
    """Iron band round a beam (p0 -> p1) centred at fraction `at`, slightly larger than the beam."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = unit(p1 - p0)
    c = p0 + (p1 - p0) * at
    g.beam(tuple(c - d * length / 2), tuple(c + d * length / 2), lw + 0.03, lh + 0.03, up=up, mat="iron", tag=tag)
    return c, d


def ground_outline(p):
    """Dirt patch outline (world XY, CCW). params['_ground'] (fitted to the painting's silhouette in solve()) or an
    ellipse round the pit."""
    if p.get("_ground") is not None:
        return np.asarray(p["_ground"], float)
    a = np.linspace(0, 2 * math.pi, 40, endpoint=False)
    return np.stack([p["PX"] + 2.2 * np.cos(a), p["PY"] + 1.7 * np.sin(a)], 1)


# ---------------------------------------------------------------------------------------------- build
def build(A, p, lod):
    A._params = p
    g = A.g("root", lod)
    AX, L2, Rc = p["AX"], p["L2"], p["Rc"]
    PR, PY, PX = p["PR"], p["PY"], p["PX"]
    LW, FY = p["LW"], p["FY"]
    rng = np.random.default_rng(7 + lod)
    ch_b = 0.014 if lod == 0 else 0.0
    # ---------------- pit: a ring of cut grey stone blocks (two courses, art/10) round the dark mouth; the back
    # and side walls stand WH above the ground, the front ring lower so the hanging chest shows over it
    hx, hy, t = PR, PR * 0.78, 0.2
    WH = p["WH"]
    xb = (PX - hx - t, PX + hx + t)
    yb = PY + hy + t / 2
    yf = PY - hy - t / 2
    top_lod = lod if lod < 2 else 1
    CG.masonry_run(g, (xb[0], yb), (xb[1], yb), 0.0, WH * 0.5, t, 1, 0.42, rng, mat="stone", tag="pit_ring",
                   chamfer=0.0, lod=1)
    CG.masonry_run(g, (xb[0] + 0.1, yb), (xb[1] - 0.05, yb), WH * 0.5, WH, t, 1, 0.42, rng, mat="stone",
                   tag="pit_ring", chamfer=0.02, lod=top_lod)
    for sx_ in (-1, 1):
        xs = PX + sx_ * (hx + t / 2)
        CG.masonry_run(g, (xs, yf + t / 2), (xs, yb - t / 2), 0.0, WH * 0.5, t, 1, 0.4, rng, mat="stone",
                       tag="pit_ring", chamfer=0.0, lod=1)
        CG.masonry_run(g, (xs, yf + t / 2), (xs, yb - t / 2), WH * 0.5, WH * 0.9, t, 1, 0.4, rng, mat="stone",
                       tag="pit_ring", chamfer=0.0, lod=1)
    FH = WH * 0.42
    CG.masonry_run(g, (xb[0], yf), (xb[1], yf), 0.0, FH * 0.5, t, 1, 0.38, rng, mat="stone", tag="pit_ring",
                   chamfer=0.0, lod=1)
    CG.masonry_run(g, (xb[0] + 0.06, yf), (xb[1] - 0.06, yf), FH * 0.5, FH, t, 1, 0.38, rng, mat="stone",
                   tag="pit_ring", chamfer=0.02, lod=top_lod)
    # pit shaft below the mouth (inner faces only, dark masonry) and the floor
    g.box((PX, yf, -PIT_D / 2), (2 * hx + 2 * t, t, PIT_D), mat="stone", tag="pit_wall", skip=("-y", "-z", "+z"))
    g.box((PX, yb, -PIT_D / 2), (2 * hx + 2 * t, t, PIT_D), mat="stone", tag="pit_wall", skip=("+y", "-z", "+z"))
    for sx_ in (-1, 1):
        g.box((PX + sx_ * (hx + t / 2), PY, -PIT_D / 2), (t, 2 * hy, PIT_D), mat="stone", tag="pit_wall",
              skip=("-z", "+z", "+x" if sx_ > 0 else "-x"))
    g.box((PX, PY, -PIT_D - 0.02), (2 * hx, 2 * hy, 0.04), mat="ground", tag="pit_floor", skip=("-z",))
    # ---------------- dirt patch round the pit (fitted outline), outer edge sloping into the terrain
    out = ground_outline(p)
    m = len(out)
    inner = []
    for q in out:
        a = math.atan2(q[1] - PY, q[0] - PX)
        c_, s_ = math.cos(a), math.sin(a)
        k_ = 1.0 / max(abs(c_) / (hx + t), abs(s_) / (hy + t))
        inner.append((PX + k_ * c_, PY + k_ * s_))
    inner = np.array(inner)
    if lod > 0:
        sel = np.arange(0, m, 2 if lod == 1 else 3)
        out, inner, m = out[sel], inner[sel], len(sel)
    zt_, zo = 0.012, -0.06
    V = np.concatenate([np.c_[inner, np.full(m, zt_)], np.c_[out, np.full(m, zt_)],
                        np.c_[out + (out - np.array([PX, PY])) * 0.06, np.full(m, zo)]])
    F = []
    for i in range(m):
        j = (i + 1) % m
        F.append([i, m + i, m + j, j])                       # top (normal up: the ring runs CCW)
        F.append([m + i, 2 * m + i, 2 * m + j, m + j])       # skirt sloping into the terrain (normal out / up)
    g.add(V, F, "ground", "ground")
    # ---------------- rubble piles round the trestle feet and along the pit's sides
    piles = p.get("_rocks") or [(-1.35, -0.55, 0.36, 0.30), (-1.75, -0.1, 0.30, 0.26), (-0.95, -0.95, 0.24, 0.2),
                                (1.05, -0.85, 0.32, 0.26), (1.45, -0.35, 0.30, 0.24), (0.75, -1.05, 0.22, 0.18),
                                (-1.55, 0.55, 0.26, 0.2), (1.35, 0.5, 0.26, 0.2)]
    keep = (6, 5, 3)[lod]
    for k, (cx, cy, r, h) in enumerate(piles[:keep]):
        g.rock((cx + PX * 0.0, cy, h * 0.3), (r, r * rng.uniform(0.75, 0.95), h * 0.6), seed=k + 40,
               sub=1 if ((lod == 0 and k < 5) or (lod == 1 and k < 3)) else 0, mat="stone", tag="rubble",
               flat_bottom=True, rough=0.15)
    # ---------------- A-frame trestles
    shoes = []
    for sx, fx in ((-1, p["FXL"]), (1, p["FXR"])):
        x = sx * fx
        top = np.array([x, 0.0, AX + p["TB"]])
        spread = {-1: p["SPL"], 1: p["SPIL"]} if sx < 0 else {-1: p["SPIR"], 1: p["SPL"]}
        for sy in (-1, 1):
            y = sy * FY
            legs = []
            for side in (-1, 1):
                foot = np.array([x + side * spread[side], y * 1.15, 0.0])
                head = top + np.array([side * 0.07, y * 0.45, -0.06])
                g.beam(tuple(foot), tuple(head), LW, LW * 1.04, mat="wood", tag="leg", chamfer=ch_b)
                legs.append((foot, head))
                shoes.append((foot, sy, side, sx))
            # cross beam (low) between the two legs of this frame
            zc = 0.55
            pa = legs[0][0] + (legs[0][1] - legs[0][0]) * (zc / legs[0][1][2])
            pb = legs[1][0] + (legs[1][1] - legs[1][0]) * (zc / legs[1][1][2])
            g.beam(tuple(pa + np.array([0, sy * 0.02, 0])), tuple(pb + np.array([0, sy * 0.02, 0])), 0.15, 0.15,
                   mat="wood", tag="cross", chamfer=ch_b * 0.6)
            # mid iron bands on the front legs (art/10: bolted bands where the tie / braces join)
            if sy < 0 and lod < 2:
                for (foot, head) in legs:
                    c, d = band_on_beam(g, foot, head, 0.47, LW + 0.03, LW * 1.04 + 0.03, 0.22, tag="band")
                    if lod == 0:
                        nrm = np.array([0.0, -1.0, 0.0])
                        for off in (-0.07, 0.07):
                            bolt(g, c + nrm * (LW * 1.04 / 2 + 0.032) + d * off, nrm)
        # top block (cap timber along Y), its iron strap with bolts, the axle bearing
        g.box((x, 0.0, AX + p["TB"] - 0.02), (0.30, 0.78, 0.24), mat="wood", tag="top_block", chamfer=ch_b)
        g.box((x, -0.415, AX + p["TB"] - 0.04), (0.42, 0.06, 0.2), mat="iron", tag="strap")
        g.box((x, 0.415, AX + p["TB"] - 0.04), (0.42, 0.06, 0.2), mat="iron", tag="strap")
        if lod == 0:
            for off in (-0.13, 0.0, 0.13):
                bolt(g, (x + off, -0.445, AX + p["TB"] - 0.04), (0, -1, 0))
        g.cyl((x - sx * 0.02, 0, AX), (x + sx * 0.16, 0, AX), 0.11, n=(12, 8, 6)[lod], mat="iron", tag="bearing",
              up=(0, 0, 1))
    # iron shoes at every foot (bolted fronts)
    for (foot, sy, side, sx) in shoes:
        g.box((foot[0], foot[1], 0.13), (0.36, 0.36, 0.28), mat="iron", tag="shoe", skip=("-z",), chamfer=0.0)
        if lod == 0 and sy < 0:
            for off in (-0.1, 0.1):
                bolt(g, (foot[0] + off, foot[1] - 0.18, 0.15), (0, -1, 0))
    # top rail between the trestle tops (behind the drum), tie beam (lower, at the back), brace and back post
    g.beam((-p["FXL"] + 0.1, 0.30, AX + p["TB"] - 0.02), (p["FXR"] - 0.1, 0.30, AX + p["TB"] - 0.02), 0.17, 0.2,
           mat="wood", tag="top_rail", chamfer=ch_b * 0.6)
    g.beam((-p["FXL"], FY * 0.5, AX - p["TZ"]), (p["FXR"], FY * 0.5, AX - p["TZ"]), 0.18, 0.18, mat="wood",
           tag="tie", chamfer=ch_b * 0.6)
    post_x = p["PSX"]
    yb_post = FY * 0.5
    g.beam((post_x, yb_post, 0.0), (post_x, yb_post, AX - p["TZ"] + 0.05), LW * 0.85, LW * 0.85, mat="wood",
           tag="post", chamfer=ch_b)
    g.box((post_x, yb_post, 0.1), (0.32, 0.32, 0.2), mat="iron", tag="shoe", skip=("-z",))
    g.beam((-p["FXL"] + p["SPIL"] * 0.7, yb_post, 0.55), (post_x - 0.05, yb_post, AX - p["TZ"] - 0.12), 0.14, 0.14,
           mat="wood", tag="brace", chamfer=ch_b * 0.5)
    # ---------------- crank bearing housing on the right trestle (painter's cheat: its face turned to the viewer)
    H = p["HX"]
    hax = unit((1.0, -1.15, 0.0))
    hc = np.array([H + 0.02, -0.33, AX])
    g.cyl(tuple(hc - hax * 0.1), tuple(hc + hax * 0.03), p["HR"], n=(18, 12, 8)[lod], mat="iron", tag="housing",
          up=(0, 0, 1))
    g.cyl(tuple(hc + hax * 0.03), tuple(hc + hax * 0.1), p["HR"] * 0.62, n=(14, 10, 6)[lod], mat="iron",
          tag="housing", up=(0, 0, 1))
    g.box((p["FXR"] + 0.17, -0.1, AX), (0.05, 0.42, 0.5), mat="iron", tag="housing_plate")
    g.beam((p["FXR"] + 0.17, -0.12, AX), tuple(hc - hax * 0.06), 0.12, 0.16, mat="iron", tag="housing_plate")
    if lod == 0:
        for (dy, dz) in ((-0.15, 0.19), (0.12, 0.19), (-0.15, -0.19), (0.12, -0.19)):
            bolt(g, (p["FXR"] + 0.195, -0.1 + dy, AX + dz), (1, 0, 0), r=0.028)

    # ---------------- drum node: oak core, rope coil, iron flanges, axle through both trestles
    drum = A.part("drum", None, (0.0, 0.0, AX))
    dg = drum.geo[lod]
    dg.cyl((-L2 - 0.05, 0, AX), (L2 + 0.05, 0, AX), Rc * 0.8, n=(16, 12, 8)[lod], mat="wood", tag="drum_core",
           up=(0, 0, 1))
    dg.cyl((-L2, 0, AX), (L2, 0, AX), Rc, n=(28, 18, 12)[lod], mat="rope", tag="coil", up=(0, 0, 1), caps=(False, False))
    for xe, d in ((-L2, -1), (L2, 1)):
        dg.cyl((xe, 0, AX), (xe + d * 0.06, 0, AX), Rc * 1.16, n=(24, 16, 10)[lod], mat="iron", tag="flange",
               up=(0, 0, 1))
    dg.cyl((-p["FXL"] - 0.2, 0, AX), (H, 0, AX), 0.05, n=(8, 6, 4)[lod], mat="iron", tag="axle", up=(0, 0, 1))
    # ---------------- gear train (coplanar, tilted toward the viewer as painted)
    gc, ga, gu, gw = big_gear_frame(p)
    Rb = np.stack([gu, gw, ga], 1)
    r = gear_radii(p)
    pc = pinion_centre(p)
    psi = math.atan2((pc - gc) @ gw, (pc - gc) @ gu)            # pinion direction in the gear plane
    big = A.part("big_gear", None, tuple(gc))
    phase_b = psi - math.pi / GEAR_TEETH                         # a big-gear tooth centred on the contact line
    gear(big.geo[lod], gc, Rb, GEAR_TEETH if lod < 2 else 15, r["rg"], r["add"], r["ded"], phase_b, 0.05, lod, "gear",
         (5, 5, 4)[lod], 0.1, 0.075)
    pin = A.part("pinion", None, tuple(pc))
    phase_p = psi + math.pi                                      # a pinion gap facing the big gear
    gear(pin.geo[lod], pc, Rb, PINION_TEETH if lod < 2 else 10, r["rp"], r["add"], r["ded"], phase_p, 0.05, lod,
         "pinion", (4, 4, 3)[lod], 0.075, 0.07, r_in_k=0.7)
    # pinion bracket: iron arm from the left trestle's front inner leg to the pinion hub, a bolted plate
    xl = -p["FXL"] + p["SPIL"] * 0.35
    leg_y = -FY * 0.75
    g.beam((pc[0], leg_y - 0.02, pc[2]), tuple(pc - ga * 0.1), 0.09, 0.09, up=(0, 0, 1), mat="iron", tag="pinion_bracket")
    g.box((pc[0], leg_y - 0.03, pc[2]), (0.26, 0.04, 0.26), mat="iron", tag="pinion_bracket")
    if lod == 0:
        for (dx, dz) in ((-0.09, 0.09), (0.09, 0.09), (-0.09, -0.09), (0.09, -0.09)):
            bolt(g, (pc[0] + dx, leg_y - 0.05, pc[2] + dz), (0, -1, 0), r=0.026)
    # stub axle from the drum axle out to the big gear's hub
    g.beam((-L2 - 0.12, 0.0, AX), tuple(gc), 0.09, 0.09, mat="iron", tag="gear_stub")
    # ---------------- crank node: shaft, forged L-shaped arm, turned wooden grip with an iron collar and end cap
    crank = A.part("crank", None, (H, 0.0, AX))
    cg = crank.geo[lod]
    xs = H + p["Ls"]
    cg.cyl((H, 0, AX), (xs, 0, AX), 0.06, n=(12, 8, 6)[lod], mat="iron", tag="shaft", up=(0, 0, 1))
    cg.cyl((H + 0.08, 0, AX), (H + 0.13, 0, AX), 0.075, n=(12, 8, 6)[lod], mat="iron", tag="collar", up=(0, 0, 1))
    zg = AX - p["Ac"]
    arm = [np.array([xs, -0.0, AX + 0.05]), np.array([xs, -0.02, AX - 0.1]), np.array([xs + 0.005, -0.05, zg + 0.12]),
           np.array([xs + 0.02, -0.06, zg - 0.02])]
    CG.sweep_rect(cg, arm, 0.055, 0.09, up=(1, 0, 0), mat="iron", tag="crank_arm")
    cg.cyl((xs - 0.04, -0.0, AX), (xs + 0.04, 0, AX), 0.08, n=(12, 8, 6)[lod], mat="iron", tag="crank_boss", up=(0, 0, 1))
    cg.cyl((xs - 0.02, -0.06, zg), (xs + 0.07, -0.06, zg), 0.072, n=(12, 8, 6)[lod], mat="iron", tag="crank_boss",
           up=(0, 0, 1))
    Lg = p["Lg"]
    gs = 1.0
    prof = [(0.052, 0.0), (0.064, 0.05), (0.071, 0.16), (0.068, 0.3), (0.072, 0.44), (0.066, 0.56), (0.058, 0.62)]
    prof = [(rr * gs, z * Lg / 0.62) for rr, z in prof]
    Rx = np.stack([np.array([0, 1.0, 0]), np.array([0, 0, 1.0]), np.array([1.0, 0, 0])], 1)   # lathe z -> world x
    CG.lathe(cg, prof if lod < 2 else prof[::2], (xs + 0.07, -0.06, zg), n=(12, 8, 6)[lod], mat="wood", tag="grip", R=Rx)
    cg.cyl((xs + 0.07 + Lg - 0.01, -0.06, zg), (xs + 0.07 + Lg + 0.035, -0.06, zg), 0.062, n=(12, 8, 6)[lod],
           mat="iron", tag="grip_cap", up=(0, 0, 1))
    # ---------------- pawl node (over the big gear's top teeth)
    pv = gc + gw * (r["rg"] + r["add"] + 0.07) - gu * 0.12
    pawl = A.part("pawl", None, tuple(pv))
    ol = np.array([[0.0, -0.03], [0.14, -0.045], [0.19, -0.1], [0.13, -0.065], [0.0, 0.03]])
    Rp = np.stack([gu, gw, ga], 1)
    pawl.geo[lod].prism(ol, -0.03, 0.03, "iron", "pawl", R=Rp, t=tuple(pv))
    pawl.geo[lod].cyl(tuple(pv - ga * 0.05), tuple(pv + ga * 0.05), 0.032, n=(8, 6, 6)[lod], mat="iron", tag="pawl_pin",
                      up=(0, 0, 1))
    # ---------------- brake lever node (pivot on the left trestle top), brass rod and turned brass knob
    bp = np.array([p["KX"] - 0.2, -0.3, AX + 0.22])
    brake = A.part("brake_lever", None, tuple(bp))
    bg = brake.geo[lod]
    knob_c = np.array([p["KX"], -0.28, AX + 0.78])
    bg.cyl(tuple(bp), tuple(knob_c - np.array([0, 0, 0.08])), 0.038, n=(10, 8, 6)[lod], mat="brass", tag="lever",
           up=(1, 0, 0))
    CG.lathe(bg, [(0.035, 0.0), (0.075, 0.03), (0.105, 0.09), (0.112, 0.15), (0.095, 0.21), (0.05, 0.245), (0.0, 0.255)],
             tuple(knob_c - np.array([0, 0, 0.1])), n=(12, 9, 6)[lod], mat="brass", tag="knob")
    bg.cyl(tuple(bp + (-0.07, 0, 0)), tuple(bp + (0.07, 0, 0)), 0.06, n=(12, 8, 6)[lod], mat="brass", tag="lever_hub",
           up=(0, 0, 1))
    g.beam((-p["FXL"] + 0.1, -0.3, bp[2]), (bp[0] - 0.05, -0.3, bp[2]), 0.1, 0.12, mat="iron", tag="lever_bracket")
    # ---------------- rope node (top at the drum's front tangent, hangs to the chest hook at rest)
    travel, z_bottom = rise(p)
    hook_up = p["Hc"] + 0.22
    rope_top = np.array([0.0, -Rc, AX])
    L0 = AX - (z_bottom + hook_up)
    rope = A.part("rope", None, tuple(rope_top))
    pts = np.array([rope_top - np.array([0, 0, L0 * f]) for f in np.linspace(0, 1, (9, 6, 4)[lod])])
    rope.geo[lod].tube(pts, 0.03, n=(8, 6, 4)[lod], mat="rope", tag="rope")
    # ---------------- chest node (rest at the pit floor) + lid node + hook + rope sling
    Wc, Hc = p["Wc"], p["Hc"]
    cb = np.array([0.0, PY - 0.25 + 0.2, z_bottom])        # body centre line (front face at PY - 0.25)
    chest = A.part("chest", None, tuple(cb))
    hg = chest.geo[lod]
    body_h = Hc * 0.62
    D = 0.4
    hg.box(tuple(cb + (0, 0, body_h / 2)), (Wc, D, body_h), mat="brass", tag="chest_body", chamfer=0.015 if lod == 0 else 0.0)
    hg.box(tuple(cb + (0, 0, 0.025)), (Wc + 0.02, D + 0.02, 0.05), mat="wood", tag="chest_plinth", skip=("-z",))
    for xx in ((-Wc * 0.42, Wc * 0.42) if lod == 2 else (-Wc * 0.42, -Wc * 0.14, Wc * 0.14, Wc * 0.42)):
        hg.box(tuple(cb + (xx, 0, body_h / 2)), (0.055, D + 0.024, body_h + 0.01), mat="iron", tag="chest_band",
               skip=("-z",))
    hg.box(tuple(cb + (0, -D / 2 - 0.02, body_h * 0.7)), (0.15, 0.03, 0.19), mat="iron", tag="chest_lock")
    hg.box(tuple(cb + (0, -D / 2 - 0.04, body_h * 0.72)), (0.05, 0.02, 0.08), mat="brass", tag="chest_hasp")
    if lod == 0:
        for xx in (-Wc * 0.42, Wc * 0.42):
            for zz in (0.06, body_h - 0.06):
                bolt(hg, cb + np.array([xx, -D / 2 - 0.012, zz]), (0, -1, 0), r=0.016, h=0.012, k=5)
    sling = [cb + np.array([-Wc * 0.45, 0, Hc - 0.02]), cb + np.array([-Wc * 0.2, 0, Hc + 0.12]),
             cb + np.array([0, 0, Hc + 0.2]), cb + np.array([Wc * 0.2, 0, Hc + 0.12]), cb + np.array([Wc * 0.45, 0, Hc - 0.02])]
    hg.tube(np.array(sling), 0.02, n=(6, 5, 4)[lod], mat="rope", tag="sling")
    hg.tube(np.array([cb + np.array([0.08 * math.cos(a), 0, Hc + 0.22 + 0.08 * math.sin(a)])
                      for a in np.linspace(0, math.pi, (7, 5, 4)[lod])]), 0.016, n=(6, 5, 4)[lod], mat="iron", tag="hook")
    lid = A.part("chest_lid", "chest", tuple(cb + (0, D / 2, body_h)))
    lg = lid.geo[lod]
    # domed lid: half cylinder along X with end caps (wood), iron bands over it
    nl = (10, 7, 4)[lod]
    a = np.linspace(0, math.pi, nl + 1)
    rr = D / 2
    prof2 = np.stack([rr * np.cos(a), rr * 1.0 * np.sin(a)], 1)        # (y, z) dome profile
    for xx0, xx1, mat_, tag_ in ((-Wc / 2, Wc / 2, "brass", "chest_lid"),):
        Vd = [cb + np.array([xx, q[0], body_h + q[1]]) for xx in (xx0, xx1) for q in prof2]
        Vd = np.array(Vd)
        k1 = nl + 1
        Fd = [[i, k1 + i, k1 + i + 1, i + 1] for i in range(nl)]
        Fd.append(list(range(k1)))
        Fd.append([k1 + i for i in range(k1)][::-1])
        F2 = []
        cc = cb + np.array([0, 0, body_h + rr * 0.3])
        for f in Fd:
            P = Vd[f]
            nrm = np.cross(P[1] - P[0], P[2] - P[0])
            if nrm @ (P.mean(0) - cc) < 0:
                f = f[::-1]
            F2.append(f)
        lg.add(Vd, F2, mat_, tag_)
    prof3 = np.stack([rr * np.cos(np.linspace(0, math.pi, 7)), rr * 1.0 * np.sin(np.linspace(0, math.pi, 7))], 1)
    for xx in (-Wc * 0.42, -Wc * 0.14, Wc * 0.14, Wc * 0.42):
        band = [cb + np.array([xx, q[0] * 1.06, body_h + q[1] * 1.06 + 0.004]) for q in prof3]
        CG.sweep_rect(lg, np.array(band), 0.055, 0.014, up=(1, 0, 0), mat="iron", tag="chest_band", caps=False)
    if lod == 0:
        A.marker("artifact_spot", tuple(cb + (0, 0, body_h * 0.5)), parent="chest")
    # ---------------- pit void (dark mouth): its own node so the game can lift it onto the terrain surface
    void = A.part("pit_void", None, (PX, PY, -0.24))
    vz = -0.24
    void.geo[lod].add(np.array([[PX - hx, PY - hy, vz], [PX + hx, PY - hy, vz], [PX + hx, PY + hy, vz], [PX - hx, PY + hy, vz]]),
                      [[0, 1, 2, 3]], "void", "pit_void", uv=[[(0, 0), (1, 0), (1, 1), (0, 1)]])
    # ---------------- grass tufts (modelled blades, no alpha) at the painted spots
    tufts = p.get("_tufts") or [(-2.0, -0.6, 0.55, 9), (-1.85, -1.1, 0.35, 6), (1.75, -0.95, 0.42, 7),
                                (1.9, -0.4, 0.35, 6), (-0.75, -1.25, 0.22, 5), (0.55, -1.3, 0.22, 5),
                                (-1.1, 0.75, 0.3, 5), (0.9, 0.75, 0.3, 5)]
    keep = len(tufts) if lod == 0 else (len(tufts) // 2 if lod == 1 else 0)
    trng = np.random.default_rng(31)
    for k, (tx, ty, th, tn) in enumerate(tufts[:keep]):
        tuft(g, (tx, ty, 0.0), trng, n=tn if lod == 0 else max(3, tn // 2), h=th, spread=0.06 + th * 0.25, tag="grass")
    return A


# ---------------------------------------------------------------------------------------------- solve
def _pose_for(v, p):
    pose = dict(v.render_pose if v.render_pose is not None else v.pose)
    if pose.get("chest") == "raised":
        pose.update(drawn_pose(p))
    return pose


def _open_mask(v):
    """Painted silhouette with the background between the legs kept open (holes > 400 px not filled)."""
    from frlib import refs
    crop = v.crop
    bg = refs.border_color(crop, width=2)
    m = refs.silhouette(crop, bg=bg, thresh=v.thresh, blur=0.7, open_px=0, close_px=1, fill_holes=400, keep="all",
                        min_area=25)
    return m


def _silhouette_iou(p, views, lod=2, open_mask=True):
    import cv2
    A = pv2.Asset(ID, ATLAS)
    build(A, p, lod)
    out = []
    for v in views:
        Wm = A.world_mats(_pose_for(v, p))
        W_, H_ = v.size
        m = np.zeros((H_, W_), np.uint8)
        for nm, part in A.parts.items():
            M_ = Wm.get(nm)
            if M_ is None:
                continue
            V, F, _, _, _ = part.geo[lod].arrays()
            if not len(V):
                continue
            Vw = V @ M_[:3, :3].T + M_[:3, 3]
            u, w, _z = v.cam.project(Vw)
            pts = np.stack([u, w], 1)
            for f in F:
                cv2.fillPoly(m, [np.round(pts[f]).astype(np.int32)], 1)
        ref = _open_mask(v) if open_mask else v.mask()[0]
        mm = m.astype(bool)
        ig = v.ignore()
        if ig is not None:
            mm, ref = mm & ~ig, ref & ~ig
        out.append(float((mm & ref).sum()) / max(1.0, float((mm | ref).sum())))
    return float(np.mean(out)), out


def _refine_cameras(params, views):
    import cv2
    for v in views:
        def score(cam):
            keep = v.cam
            v.cam = cam
            val = _silhouette_iou(params, [v])[0]
            v.cam = keep
            return val
        best = score(v.cam)
        for _round in range(2):
            for kind, steps in (("rx", np.radians([-1.0, -0.5, 0.5, 1.0])), ("ry", np.radians([-1.0, -0.5, 0.5, 1.0])),
                                ("rz", np.radians([-0.8, -0.4, 0.4, 0.8])), ("tx", [-0.03, -0.015, 0.015, 0.03]),
                                ("ty", [-0.03, -0.015, 0.015, 0.03]), ("f", [0.97, 0.985, 1.015, 1.03])):
                for d in steps:
                    c = v.cam
                    R = cv2.Rodrigues(np.asarray(c.rvec, float))[0]
                    C = -R.T @ np.asarray(c.tvec, float)
                    f = c.f
                    if kind in ("rx", "ry", "rz"):
                        axis = {"rx": (1, 0, 0), "ry": (0, 1, 0), "rz": (0, 0, 1)}[kind]
                        R2 = cv2.Rodrigues(np.asarray(axis, float) * d)[0] @ R
                        t2 = -R2 @ C
                    elif kind in ("tx", "ty"):
                        R2 = R
                        shift = np.array([d, 0.0, 0.0]) if kind == "tx" else np.array([0.0, d, 0.0])
                        t2 = np.asarray(c.tvec, float) + shift * np.linalg.norm(C) * 0.1
                    else:
                        R2, t2, f = R, np.asarray(c.tvec, float), c.f * d
                    cam = type(c)(f, c.cx, c.cy, cv2.Rodrigues(R2)[0].ravel(), t2, c.k1, c.k2, size=c.size)
                    val = score(cam)
                    if val > best + 1e-4:
                        best, v.cam = val, cam
        pv2.log(f"  [{v.name}] camera refined by silhouette: IoU {best:.3f}")


def _fit_ground(params, v):
    """Dirt patch outline from the painting: the painted silhouette's lower boundary (ground, grass, stones in front
    of the winch) cast onto the ground plane through the solved camera, closed behind the winch by an ellipse."""
    m = _open_mask(v)
    H_, W_ = m.shape
    PX, PY = params["PX"], params["PY"]
    pts = []
    cols = np.arange(6, W_ - 6, 6)
    for x in cols:
        ys = np.nonzero(m[:, x])[0]
        if not len(ys):
            continue
        y = ys.max()
        if y < H_ * 0.62:
            continue
        q = v.cam.on_plane_z(np.array([x + 0.5]), np.array([y - 1.5]), 0.0)[0]
        pts.append(q[:2])
    pts = np.array(pts)
    if len(pts) < 6:
        return None
    ang = np.arctan2(pts[:, 1] - PY, pts[:, 0] - PX)
    rad = np.hypot(pts[:, 0] - PX, pts[:, 1] - PY)
    # angular profile: front half from the painting, back half an ellipse through the side extremes
    bins = np.linspace(-math.pi, math.pi, 37)
    prof = np.full(36, np.nan)
    for i in range(36):
        k = (ang >= bins[i]) & (ang < bins[i + 1])
        if k.any():
            prof[i] = np.median(rad[k])
    centres = (bins[:-1] + bins[1:]) / 2
    rx = np.nanmax(np.abs(np.cos(centres) * prof)) if np.isfinite(prof).any() else 2.2
    ry_back = 1.55
    out = []
    for i, a in enumerate(centres):
        if np.isfinite(prof[i]) and math.sin(a) < 0.15:
            r = float(np.clip(prof[i] * 0.8, 1.2, 2.3))
        else:
            c_, s_ = math.cos(a), math.sin(a)
            r = 1.0 / math.sqrt((c_ / max(rx, 1.6)) ** 2 + (s_ / ry_back) ** 2)
        out.append((PX + r * math.cos(a), PY + r * math.sin(a)))
    out = np.array(out)
    # smooth the radius round the ring
    rr = np.hypot(out[:, 0] - PX, out[:, 1] - PY)
    from scipy import ndimage as ndi
    rr = ndi.gaussian_filter1d(rr, 1.2, mode="wrap")
    return np.stack([PX + rr * np.cos(centres), PY + rr * np.sin(centres)], 1)


# painted tuft / rubble spots (sheet px of the tuft base or stone centre -> cast onto the ground plane)
TUFT_PX = [((48, 762), 0.62, 9), ((22, 790), 0.3, 6), ((475, 790), 0.45, 8), ((500, 805), 0.3, 6), ((183, 858), 0.22, 5),
           ((338, 866), 0.22, 5), ((98, 842), 0.25, 5), ((440, 858), 0.25, 5), ((160, 772), 0.22, 4), ((402, 790), 0.2, 4)]
ROCK_PX = [((60, 808), 0.34, 0.3), ((120, 818), 0.3, 0.26), ((32, 838), 0.24, 0.18), ((410, 822), 0.34, 0.28),
           ((455, 812), 0.26, 0.22), ((378, 846), 0.22, 0.16), ((95, 852), 0.2, 0.14), ((470, 845), 0.2, 0.15)]


def solve(views):
    params, reps = pv2.solve_views(views, points, PARAMS, FREE, prior_sigma=PRIOR)
    v = views[0]
    best = _silhouette_iou(params, views)[0]
    grids = {"SPL": np.arange(0.40, 0.57, 0.04), "SPIL": np.arange(0.2, 0.39, 0.06),
             "SPIR": np.arange(-0.12, 0.07, 0.06), "FY": np.arange(0.36, 0.47, 0.05), "TZ": np.arange(0.5, 0.76, 0.06),
             "PSX": np.arange(-0.5, -0.19, 0.1), "WH": np.arange(0.26, 0.45, 0.06), "PR": np.arange(0.7, 0.86, 0.05),
             "PX": np.arange(-0.3, 0.06, 0.08)}
    for _round in range(2):
        for key, grid in grids.items():
            for val in grid:
                q = dict(params)
                q[key] = float(val)
                iou = _silhouette_iou(q, views)[0]
                if iou > best + 1e-4:
                    best, params = iou, q
        if _round == 0:
            _refine_cameras(params, views)
            best = _silhouette_iou(params, views)[0]
    pv2.log("  shape by silhouette IoU (open mask): " + ", ".join(f"{k} {params[k]:.2f}" for k in grids) +
            f" -> IoU {best:.3f}")
    # dirt patch, tufts and rubble from the painting, cast onto the ground plane
    params["_ground"] = _fit_ground(params, v)
    x0, y0 = v.box[:2]
    params["_tufts"] = []
    for (sx, sy), h, n in TUFT_PX:
        q = v.cam.on_plane_z(np.array([sx - x0 + 0.5]), np.array([sy - y0 + 0.5]), 0.0)[0]
        params["_tufts"].append((float(q[0]), float(q[1]), h, n))
    params["_rocks"] = []
    for (sx, sy), r, h in ROCK_PX:
        q = v.cam.on_plane_z(np.array([sx - x0 + 0.5]), np.array([sy - y0 + 0.5]), 0.0)[0]
        params["_rocks"].append((float(q[0]), float(q[1]), r, h))
    pv2.log(f"  final silhouette IoU (open mask) {_silhouette_iou(params, views)[0]:.3f}, filled-mask "
            f"{_silhouette_iou(params, views, open_mask=False)[0]:.3f}")
    for v_ in views:
        _resolve_pose(v_, params)
    return params


def _resolve_pose(v, p):
    if v.pose.get("chest") == "raised":
        v.pose.update(drawn_pose(p))


def solved_pose(p):
    """End pose of lf_lock_mechanism (QA render): chest raised clear, lid open, drum / crank / gears turned."""
    from mathutils import Matrix, Vector
    travel, _ = rise(p)
    L0 = rope_len(p)
    turn = -travel / p["Rc"]
    _, ax, _, _ = big_gear_frame(p)
    eb = tuple(Matrix.Rotation(turn, 3, Vector(tuple(ax))).to_euler("XYZ"))
    ep = tuple(Matrix.Rotation(-turn * RATIO, 3, Vector(tuple(ax))).to_euler("XYZ"))
    return {"chest": {"loc": (0, 0, travel)}, "rope": {"scale": (1, 1, (L0 - travel) / L0)},
            "chest_lid": {"rot": (-math.radians(105), 0, 0)}, "drum": {"rot": (turn, 0, 0)}, "crank": {"rot": (turn, 0, 0)},
            "pawl": {"rot": (PAWL_ON, 0, 0)}, "big_gear": {"rot": eb}, "pinion": {"rot": ep}}


# ---------------------------------------------------------------------------------------------- clips
def _ease(t, a, b):
    return pv2.ease_io((t - a) / max(b - a, 1e-6))


def _out_back(x, s=1.2):
    x = min(max(x, 0.0), 1.0) - 1.0
    return x * x * ((s + 1) * x + s) + 1.0


def clips(A, B):
    p = A._params
    travel, z_bottom = rise(p)
    Rc = p["Rc"]
    hook_up = p["Hc"] + 0.22
    L0 = p["AX"] - (z_bottom + hook_up)
    turn = travel / Rc

    def raise_state(f):
        return -turn * f, (L0 - travel * f) / L0, travel * f

    pv2.add_clip(A, B, "lf_winch_brake", 0.6, {"brake_lever": lambda t: {"rot": (BRAKE_ON * _out_back(t / 0.5, 1.1), 0, 0)}},
                 markers={"brake_set": 0.5}, note="brake lever thrown")
    pv2.add_clip(A, B, "lf_winch_pawl", 0.5, {
        "pawl": lambda t: {"rot": (PAWL_ON * _out_back(t / 0.37, 1.6), 0, 0)},
        "brake_lever": lambda t: {"rot": (BRAKE_ON, 0, 0)}}, markers={"pawl_engaged": 0.37}, note="pawl drops on the ratchet")

    def rs(t):
        return raise_state(_ease(t, 0.13, 1.2))

    # gear train: the big gear turns with the drum about its own (tilted) axis, the pinion (parallel axis) the
    # other way at 25/16
    _, g_axis, _, _ = big_gear_frame(p)
    prev = {}

    def gear_rot(key, angle):
        from mathutils import Matrix, Vector
        m = Matrix.Rotation(angle, 3, Vector(tuple(g_axis)))
        e = m.to_euler("XYZ", prev[key]) if key in prev else m.to_euler("XYZ")
        prev[key] = e
        return tuple(e)
    pv2.add_clip(A, B, "lf_rope_release", 1.3, {
        "brake_lever": lambda t: {"rot": (BRAKE_ON * (1 - _ease(t, 0.0, 0.17)), 0, 0)},
        "drum": lambda t: {"rot": (rs(t)[0], 0, 0)},
        "crank": lambda t: {"rot": (rs(t)[0], 0, 0)},
        "big_gear": lambda t: {"rot": gear_rot("release_b", rs(t)[0])},
        "pinion": lambda t: {"rot": gear_rot("release_p", -rs(t)[0] * RATIO)},
        "rope": lambda t: {"scale": (1, 1, rs(t)[1])},
        "chest": lambda t: {"loc": (0, 0, rs(t)[2]), "rot": (0, 0, math.radians(4) * math.sin(t * 10.5) * (1 - _ease(t, 1.0, 1.3)))},
        "pawl": lambda t: {"rot": (PAWL_ON + math.radians(7) * abs(math.sin(-rs(t)[0] * GEAR_TEETH / 2)) * (1 - _ease(t, 1.13, 1.3)), 0, 0)},
    }, markers={"chest_clear_of_pit": 1.0}, note="crank turns the drum, the rope shortens, the chest rises out of the pit")
    up = raise_state(1.0)
    pv2.add_clip(A, B, "lf_lock_mechanism", 1.8, {
        "chest": lambda t: {"loc": (0, 0, up[2]), "rot": (0, 0, math.radians(3) * math.sin(t * 12.0) * (1 - _ease(t, 0, 1.0)))},
        "drum": lambda t: {"rot": (up[0], 0, 0)}, "crank": lambda t: {"rot": (up[0], 0, 0)},
        "big_gear": lambda t: {"rot": gear_rot("lock_b", up[0])}, "pinion": lambda t: {"rot": gear_rot("lock_p", -up[0] * RATIO)},
        "rope": lambda t: {"scale": (1, 1, up[1])}, "pawl": lambda t: {"rot": (PAWL_ON, 0, 0)},
        "chest_lid": lambda t: {"rot": (-math.radians(105) * _ease(t, 0.47, 1.53), 0, 0)},
    }, markers={"lid_unlocked": 14 / 30, "lid_open": 46 / 30}, note="chest hangs clear, the lid unlocks and opens")


def meta(A, p):
    g = pv2.b2g
    travel, z_bottom = rise(p)
    Rc = p["Rc"]
    hook_up = p["Hc"] + 0.22
    L0 = p["AX"] - (z_bottom + hook_up)
    up_turn = -travel / Rc
    cb = np.array([0.0, p["PY"] - 0.05, z_bottom])
    r = gear_radii(p)
    return {
        "mechanism": "winch_sequence",
        "symbol_targets": {
            "brake": {"node": "brake_lever", "rotation_x_deg": round(math.degrees(BRAKE_ON), 2), "clip": "lf_winch_brake"},
            "pawl": {"node": "pawl", "rotation_x_deg": round(math.degrees(PAWL_ON), 2), "clip": "lf_winch_pawl"},
            "raise": {"clip": "lf_rope_release", "nodes": {
                "drum": {"rotation_x_deg": round(math.degrees(up_turn), 2)},
                "crank": {"rotation_x_deg": round(math.degrees(up_turn), 2)},
                "big_gear": {"rotation_about_own_axis_deg": round(math.degrees(up_turn), 2),
                             "axis": "drum axle turned GT about the vertical toward the viewer", "teeth": GEAR_TEETH},
                "pinion": {"rotation_about_own_axis_deg": round(-math.degrees(up_turn) * RATIO, 2), "ratio": round(RATIO, 4),
                           "teeth": PINION_TEETH, "axis": "parallel to the big gear's"},
                "rope": {"scale_y": round((L0 - travel) / L0, 4), "note": "rope node scales along its own length (glTF Y)"},
                "chest": {"translation_offset": [0, round(travel, 4), 0]}, "brake_lever": {"rotation_x_deg": 0.0}}},
            "solved": {"clip": "lf_lock_mechanism", "chest_lid": {"rotation_x_deg": -105.0}},
            "wrong_input": "server resets: tween nodes back to rest (all 0, rope scale 1)",
            "sites": ["lf_site_03", "lf_site_07", "lf_site_11"], "order": ["brake", "pawl", "raise"]},
        "sockets": {"artifact_spot_raised": g(tuple(cb + (0, 0, travel + p["Hc"] * 0.33)))},
        "pit_void": {"node": "pit_void", "rest_y_m": -0.24,
                     "note": "dark pit mouth; at rest 0.24 m below the ground (painting match); the game lifts it to "
                             "the terrain surface (+0.25 m) so the pit reads dark through the terrain"},
        "gear_train": {"big_gear_teeth": GEAR_TEETH, "pinion_teeth": PINION_TEETH, "ratio": round(RATIO, 4),
                       "pitch_radius_m": {"big_gear": round(r["rg"], 4), "pinion": round(r["rp"], 4)}},
        "notes": "v2 material path: modelled geometry (real gear teeth, hubs and spokes; bolts; turned grip and knob; "
                 "modelled grass blades) with seamless painted-style material tiles (wood, iron, rope, stone, brass, "
                 "ground, grass, void) box-mapped in metres; no alpha anywhere. Crank and drum share the axle (1:1); "
                 "the big 25-tooth gear on the drum's left end turns with the drum, the coplanar 16-tooth pinion the "
                 "other way at 25/16; the pawl clicks over the big gear while raising.",
    }
