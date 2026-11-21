"""lf_mechanism_winch_sequence v2 from art/10_artifact_mechanisms.png (lower left main view): two oak A-frame
trestles with iron straps over a stone-lined well pit, a rope drum (coil between an iron flange and the right
trestle), the iron ratchet gear and pawl inside the left trestle, the brake lever with its wooden knob above it,
the crank with a long wooden grip outside the right trestle, and the banded artifact chest hanging on the rope at
the pit mouth.

Same node / clip contract as the v1 delivery (actor_director, meta.symbol_targets): brake_lever, pawl, crank, drum,
rope (scales along its own length), chest (+ chest_lid, artifact_spot); clips lf_winch_brake (0.6 s, brake_set),
lf_winch_pawl (0.5 s, pawl_engaged), lf_rope_release (1.3 s, chest_clear_of_pit), lf_lock_mechanism (1.8 s,
lid_unlocked, lid_open). Rest = chest at the bottom of the pit; the drawing shows it raised to the mouth.
"""
import math

import numpy as np

import cagegeo as CG
import pv2

ID = "lf_mechanism_winch_sequence"
ATLAS = 2048
SHEET = "10_artifact_mechanisms.png"
LIGHT = (-0.55, -0.5, 0.67)
BUDGET = "mechanism LOD0 <= 6000 tris"

PIT_D = 1.0
CHEST_RAISED = 0.92          # share of the rise the drawing shows
BRAKE_ON = math.radians(-48)
PAWL_ON = math.radians(-24)
TEETH = 22

PARAMS = dict(AX=1.42, L2=0.45, Rc=0.36, FXL=1.05, FXR=0.86, HX=1.02, GX=-0.83, KX=-0.8, Ls=0.36, Ac=0.66, Lg=0.5,
              PR=0.73, PY=-0.18, Wc=0.8, Hc=0.48, Zt=0.42,
              SPL=0.5, WH=0.42, WR=0.4, GR=1.0, TB=0.6,     # leg splay, pit wall height / width, ground ring, top block
              LW=0.26, FY=0.42, TZ=0.75, GRr=0.48, SH=0.42,   # leg width, front/back frame offset, tie drop below
                                                              # the axle, gear radius, stone pile height
              SPIL=0.26, SPIR=-0.06, PX=0.0, PSX=-0.36,       # ... back post x (art/10: under the tie, left of the rope)
              RG=0.55, RP=0.24, GT=31.0, GZ=0.2, HR=0.22, GRP=1.0)  # gear train: big gear / pinion radius, big gear
                                                              # tilt (deg, its face toward the viewer as painted),
                                                              # pinion drop below the axle; crank hub radius; grip scale                  # inner leg splay (left / right trestle), pit x offset
FREE = ["AX", "L2", "Rc", "FXL", "FXR", "HX", "GX", "GZ", "KX", "Ls", "Ac", "Lg", "Wc", "Hc", "Zt"]
GEAR_TEETH = 30              # big gear on the drum's left end (the pawl clicks over it)
PINION_TEETH = 12
PRIOR = 0.2


def rise(p):
    """Chest bottom travel from the pit floor to the raised (drawn) height."""
    z_bottom = -PIT_D + 0.02
    z_top = p["Zt"] - p["Hc"]
    return z_top - z_bottom, z_bottom


def points(p):
    AX, L2, Rc = p["AX"], p["L2"], p["Rc"]
    H = p["HX"]
    zt = p["Zt"]
    return {
        "coil_lt": (-L2, 0.0, AX + Rc), "coil_rt": (L2, 0.0, AX + Rc),
        "coil_lb": (-L2, 0.0, AX - Rc), "coil_rb": (L2, 0.0, AX - Rc),
        "hub_c": (H, -0.08, AX), "shaft_end": (H + p["Ls"], -0.05, AX),
        "grip_in": (H + p["Ls"] + 0.04, -0.1, AX - p["Ac"]), "grip_out": (H + p["Ls"] + 0.04 + p["Lg"], -0.1, AX - p["Ac"]),
        "gear_c": (p["GX"], -0.25, AX - p["GZ"]), "knob": (p["KX"], -0.28, AX + 0.78),   # gear_c = pinion centre
        "ttop_l": (-p["FXL"], 0.0, AX + 0.6), "ttop_r": (p["FXR"], 0.0, AX + 0.6),
        "chest_tl": (-p["Wc"] / 2, p["PY"] - 0.25, zt), "chest_tr": (p["Wc"] / 2, p["PY"] - 0.25, zt),
        "chest_bl": (-p["Wc"] / 2, p["PY"] - 0.25, zt - p["Hc"]), "chest_br": (p["Wc"] / 2, p["PY"] - 0.25, zt - p["Hc"]),
    }


def views():
    v = pv2.ViewSpec(
        "main", SHEET, (0, 500, 530, 878),
        {"coil_lt": (225, 556), "coil_rt": (330, 556), "coil_lb": (225, 641), "coil_rb": (330, 641),
         "hub_c": (397, 605), "shaft_end": (440, 603), "grip_in": (447, 680), "grip_out": (505, 690),
         "gear_c": (172, 613), "knob": (192, 522), "ttop_l": (148, 535), "ttop_r": (368, 535),
         "chest_tl": (222, 795), "chest_tr": (318, 797), "chest_bl": (222, 850), "chest_br": (316, 850)},
        pose={"chest": "raised"}, light=LIGHT, thresh=0.085, fill_holes=True, shadow=None,
        solve_opts={"fov_prior": 22.0}, title="WINCH main view (chest raised to the pit mouth)",
        # the painted motion arrows are annotations, not geometry
        ignore_boxes=[(148, 610, 195, 660), (418, 572, 472, 652), (280, 712, 306, 768)],
        proj_exclude=[(148, 610, 195, 660), (418, 572, 472, 652), (280, 712, 306, 768)])
    return [v]


def big_gear_frame(p):
    """Centre, axis and in-plane axes of the big gear (left end of the drum, tilted GT toward the viewer)."""
    t = math.radians(p["GT"])
    axis = np.array([math.cos(t), -math.sin(t), 0.0])
    gu = np.array([math.sin(t), math.cos(t), 0.0])
    gw = np.array([0.0, 0.0, 1.0])
    return np.array([-p["L2"] - 0.12, 0.0, p["AX"]]), axis, gu, gw


def pinion_centre(p):
    return np.array([p["GX"], -0.25, p["AX"] - p["GZ"]])


def gear_outline(r_root, r_tip, teeth, lod):
    pts = []
    for k in range(teeth):
        a0 = 2 * math.pi * k / teeth
        da = 2 * math.pi / teeth
        steps = ((0.0, r_root), (0.25, r_tip), (0.5, r_tip), (0.75, r_root)) if lod < 2 else ((0.0, r_root), (0.4, r_tip))
        for f, r in steps:
            pts.append((r * math.cos(a0 + f * da), r * math.sin(a0 + f * da)))
    return np.array(pts)


def build(A, p, lod):
    A._params = p
    g = A.g("root", lod)
    n = (28, 18, 12)[lod]
    AX, L2, Rc = p["AX"], p["L2"], p["Rc"]
    PR, PY = p["PR"], p["PY"]
    pit = np.array([p["PX"], PY, 0.0])
    rng = np.random.default_rng(7 + lod)
    # ---- ground patch round a square stone-lined pit (art/10: dressed-block shaft, the back wall's courses show
    #      through the mouth), rough stone piles round the trestle feet, small stones along the front edge
    GR, WH, SH = p["GR"], p["WH"], p["SH"]
    hx, hy, t = PR, PR * 0.78, 0.2
    m = (48, 32, 20)[lod]
    ang = np.linspace(0, 2 * math.pi, m, endpoint=False)
    inner, outer = [], []
    for a in ang:
        c, s_ = math.cos(a), math.sin(a)
        k = 1.0 / max(abs(c) / (hx + t), abs(s_) / (hy + t))
        inner.append((k * c, k * s_))
        wob = 1.0 + 0.07 * math.sin(3 * a + 1.0) + 0.04 * math.sin(7 * a + 2.0)
        outer.append(((hx + t + GR) * wob * c, (hy + t + GR * 0.75) * wob * s_))
    CG.outline_ring(g, tuple(pit), np.eye(3), outer, inner, -0.03, 0.0, "ground", "ground")
    courses = (3, 2, 1)[lod]
    ch = 0.012 if lod == 0 else 0.0
    yb = PY + hy + t / 2
    px = p["PX"]
    CG.masonry_run(g, (px - hx - t, yb), (px + hx + t, yb), -0.55, WH, t, courses + 1, 0.42, rng, mat="stone", tag="pit_wall",
                   chamfer=ch, lod=lod)
    for sx_ in (-1, 1):
        xs = px + sx_ * (hx + t / 2)
        CG.masonry_run(g, (xs, PY - hy), (xs, PY + hy), -0.55, 0.06, t, courses, 0.4, rng, mat="stone", tag="pit_wall",
                       chamfer=ch, lod=lod)
    g.box((px, PY - hy - t / 2, (0.03 - PIT_D) / 2), (2 * hx + 2 * t, t, PIT_D + 0.03), mat="stone", tag="pit_wall")
    g.box((px, yb, (-0.55 - PIT_D) / 2), (2 * hx + 2 * t, t, PIT_D - 0.55), mat="stone", tag="pit_wall")
    for sx_ in (-1, 1):
        g.box((px + sx_ * (hx + t / 2), PY, (-0.55 - PIT_D) / 2), (t, 2 * hy, PIT_D - 0.55), mat="stone", tag="pit_wall")
    g.box((px, PY, -PIT_D - 0.02), (2 * hx, 2 * hy, 0.04), mat="ground", tag="pit_floor")
    npile = (8, 5, 3)[lod]
    for sx_ in (-1, 1):
        for k in range(npile):
            cx = px + sx_ * (hx + t + 0.12 + rng.uniform(0.0, 0.55))
            cy = PY + rng.uniform(-hy - 0.35, hy + 0.15)
            h = SH * rng.uniform(0.55, 1.0)
            g.rock((cx, cy, h * 0.35), (rng.uniform(0.2, 0.32), rng.uniform(0.18, 0.28), h * 0.5), seed=k + 40 + 20 * (sx_ + 1),
                   sub=1, mat="stone", tag="rubble", flat_bottom=True, rough=0.14)
    nfr = (6, 4, 2)[lod]
    for k in range(nfr):
        cx = px - hx + (k + 0.5) * 2 * hx / nfr + rng.uniform(-0.08, 0.08)
        cy = PY - hy - t - 0.12 + rng.uniform(-0.06, 0.06)
        g.rock((cx, cy, 0.05), (rng.uniform(0.13, 0.2), rng.uniform(0.1, 0.15), rng.uniform(0.07, 0.11)), seed=k + 90,
               sub=1, mat="stone", tag="rubble", flat_bottom=True, rough=0.14)
    # ---- A-frame trestles (legs splayed along X, front + back frames), sills, top blocks, iron straps
    for sx, fx in ((-1, p["FXL"]), (1, p["FXR"])):
        x = sx * fx
        top = np.array([x, 0.0, AX + p["TB"]])
        # outer legs splay by SPL, inner legs by SPIL / SPIR (art/10: both right-trestle feet stand right of its
        # top, the inner feet frame the pit)
        spread = {-1: p["SPL"], 1: p["SPIL"]} if sx < 0 else {-1: p["SPIR"], 1: p["SPL"]}
        for sy in (-1, 1):
            y = sy * p["FY"]
            for side in (-1, 1):
                foot = np.array([x + side * spread[side], y * 1.15, 0.08])
                g.beam(foot, top + np.array([side * 0.07, y * 0.45, -0.06]), p["LW"], p["LW"] * 1.1, mat="wood", tag="leg",
                       chamfer=0.02 if lod == 0 else 0.0)
            g.beam((x - spread[-1] * 0.62, y * 0.95, 0.5), (x + spread[1] * 0.62, y * 0.95, 0.5), 0.14, 0.14, mat="wood", tag="cross",
                   chamfer=0.012 if lod == 0 else 0.0)
            g.box((x - spread[-1], y * 1.15, 0.08), (0.3, 0.3, 0.2), mat="iron", tag="shoe")
            g.box((x + spread[1], y * 1.15, 0.08), (0.3, 0.3, 0.2), mat="iron", tag="shoe")
        g.box((x, 0.0, AX + p["TB"] - 0.02), (0.26, 0.74, 0.22), mat="wood", tag="top_block", chamfer=0.02 if lod == 0 else 0.0)
        g.box((x, -0.37, AX + 0.4), (0.3, 0.035, 0.12), mat="iron", tag="strap")
        g.box((x, -0.37, 0.45), (0.3, 0.035, 0.12), mat="iron", tag="strap")
        g.cyl((x - sx * 0.02, 0, AX), (x + sx * 0.14, 0, AX), 0.1, n=(12, 8, 6)[lod], mat="iron", tag="bearing",
              up=(0, 0, 1))
    # tie beam between the trestles (lower, at the back) + front brace
    g.beam((-p["FXL"], p["FY"] * 0.5, AX - p["TZ"]), (p["FXR"], p["FY"] * 0.5, AX - p["TZ"]), 0.17, 0.17, mat="wood",
           tag="tie", chamfer=0.015 if lod == 0 else 0.0)
    # back post under the tie left of the rope, on an iron shoe, braced from the left trestle (art/10)
    post_x = p["PSX"]
    yb_post = p["FY"] * 0.5
    g.beam((post_x, yb_post, 0.0), (post_x, yb_post, AX - p["TZ"] + 0.05), p["LW"] * 0.9, p["LW"] * 0.9, mat="wood",
           tag="post", chamfer=0.02 if lod == 0 else 0.0)
    g.box((post_x, yb_post, 0.1), (0.3, 0.3, 0.2), mat="iron", tag="shoe")
    g.beam((-p["FXL"] + p["SPIL"] * 0.7, yb_post, 0.55), (post_x - 0.05, yb_post, AX - p["TZ"] - 0.12), 0.13, 0.13,
           mat="wood", tag="brace")
    # ---- drum node: wooden core, rope coil, iron flange, ratchet gear (left), axle through both trestles
    drum = A.part("drum", None, (0.0, 0.0, AX))
    dg = drum.geo[lod]
    dg.cyl((-L2 - 0.05, 0, AX), (L2 + 0.05, 0, AX), Rc * 0.8, n=(20, 14, 8)[lod], mat="wood", tag="drum_core",
           up=(0, 0, 1))
    dg.cyl((-L2, 0, AX), (L2, 0, AX), Rc, n=(24, 16, 10)[lod], mat="rope", tag="coil", up=(0, 0, 1), caps=(False, False))
    dg.cyl((-L2 - 0.06, 0, AX), (-L2, 0, AX), Rc * 1.18, n=(20, 14, 8)[lod], mat="iron", tag="flange", up=(0, 0, 1))
    dg.cyl((-p["FXL"] - 0.2, 0, AX), (p["HX"], 0, AX), 0.05, n=(8, 6, 4)[lod], mat="iron", tag="axle", up=(0, 0, 1))
    # ---- gear train (art/10 left frame): the big toothed gear on the drum's left end (hub, spokes, toothed rim;
    # tilted GT so its face shows as painted, turning about its own axis with the drum) and the small pinion on
    # the left trestle meshing with its lower left (face to the viewer, turning at RG/RP the other way)
    gc, ga, gu, gw = big_gear_frame(p)
    big = A.part("big_gear", None, tuple(gc))
    bgg = big.geo[lod]
    Rb = np.stack([gu, gw, ga], 1)                         # local x, y in the gear plane, z = axis
    RG, RP = p["RG"], p["RP"]
    nt = GEAR_TEETH if lod < 2 else GEAR_TEETH // 2
    outer = gear_outline(RG * 0.9, RG, nt, lod)
    ring_in = np.array([(RG * 0.74 * math.cos(math.atan2(q[1], q[0])), RG * 0.74 * math.sin(math.atan2(q[1], q[0]))) for q in outer])
    CG.outline_ring(bgg, tuple(gc), Rb, outer, ring_in, -0.045, 0.045, "iron", "gear_rim")
    bgg.cyl(tuple(gc - ga * 0.07), tuple(gc + ga * 0.07), RG * 0.22, n=(14, 10, 6)[lod], mat="iron", tag="gear_hub",
            up=tuple(gw))
    for k in range(6 if lod < 2 else 4):
        ang = 2 * math.pi * k / (6 if lod < 2 else 4)
        d = gu * math.cos(ang) + gw * math.sin(ang)
        bgg.beam(tuple(gc + d * RG * 0.18), tuple(gc + d * RG * 0.78), 0.07, 0.05, mat="iron", tag="gear_spoke")
    pc = pinion_centre(p)
    pin = A.part("pinion", None, tuple(pc))
    pg = pin.geo[lod]
    Rq = np.array([[1.0, 0, 0], [0, 0, 1.0], [0, -1.0, 0]])   # local x -> x, y -> -y? (z axis -> world -y: faces the viewer)
    Rq = np.stack([np.array([1.0, 0, 0]), np.array([0, 0, 1.0]), np.array([0, -1.0, 0])], 1)
    pg.prism(gear_outline(RP * 0.8, RP, PINION_TEETH, lod), -0.05, 0.05, "iron", "pinion", R=Rq, t=tuple(pc))
    pg.cyl(tuple(pc + (0, 0.06, 0)), tuple(pc + (0, -0.09, 0)), RP * 0.32, n=(12, 8, 6)[lod], mat="iron", tag="pinion_hub",
           up=(0, 0, 1))
    g.beam(tuple(pc + (0, 0.12, 0)), (p["GX"], 0.12, AX - p["GZ"] + 0.02), 0.08, 0.08, mat="iron", tag="pinion_bracket")
    # ---- crank node: hub disc, shaft stub, arm, long wooden grip
    H = p["HX"]
    crank = A.part("crank", None, (H, 0.0, AX))
    cg = crank.geo[lod]
    HR = p["HR"]
    cg.cyl((H - 0.05, 0, AX), (H + 0.08, 0, AX), HR, n=(18, 12, 8)[lod], mat="iron", tag="hub", up=(0, 0, 1))
    cg.cyl((H + 0.08, 0, AX), (H + 0.13, 0, AX), HR * 0.62, n=(14, 10, 6)[lod], mat="iron", tag="hub_boss", up=(0, 0, 1))
    xs = H + p["Ls"]
    cg.cyl((H, 0, AX), (xs, 0, AX), 0.068, n=(10, 8, 5)[lod], mat="iron", tag="shaft", up=(0, 0, 1))
    # L-shaped forged arm: elbow on the shaft end, flat bar down to the grip
    cg.cyl((xs - 0.05, 0, AX), (xs + 0.05, 0, AX), 0.085, n=(12, 8, 6)[lod], mat="iron", tag="crank_elbow", up=(0, 0, 1))
    cg.beam((xs, -0.02, AX + 0.02), (xs, -0.06, AX - p["Ac"] - 0.06), 0.13, 0.06, mat="iron", tag="crank_arm",
            chamfer=0.01 if lod == 0 else 0.0)
    cg.cyl((xs - 0.05, -0.06, AX - p["Ac"]), (xs + 0.06, -0.06, AX - p["Ac"]), 0.08, n=(12, 8, 6)[lod], mat="iron",
           tag="crank_boss", up=(0, 0, 1))
    # turned wooden grip (bulges + necks) with an iron end cap
    gs = p["GRP"]
    Lg = p["Lg"]
    prof = [(0.05 * gs, 0.0), (0.072 * gs, 0.06), (0.08 * gs, 0.16), (0.066 * gs, 0.26), (0.075 * gs, 0.36),
            (0.083 * gs, 0.46), (0.07 * gs, 0.56), (0.058 * gs, 0.62)]
    prof = [(r, z * Lg / 0.62) for r, z in prof]
    Rx = np.stack([np.array([0, 1.0, 0]), np.array([0, 0, 1.0]), np.array([1.0, 0, 0])], 1)   # lathe z -> world x
    CG.lathe(cg, prof, (xs + 0.06, -0.06, AX - p["Ac"]), n=(12, 9, 6)[lod], mat="wood", tag="grip", R=Rx)
    cg.cyl((xs + 0.06 + Lg - 0.01, -0.06, AX - p["Ac"]), (xs + 0.06 + Lg + 0.04, -0.06, AX - p["Ac"]), 0.062 * gs,
           n=(12, 8, 6)[lod], mat="iron", tag="grip_cap", up=(0, 0, 1))
    # ---- pawl node (on the left trestle, over the gear)
    pv = gc + gw * (RG + 0.06) - ga * 0.02
    pawl = A.part("pawl", None, tuple(pv))
    ol = np.array([[0.0, -0.025], [0.12, -0.04], [0.16, -0.08], [0.11, -0.055], [0.0, 0.025]])
    Rp = np.array([[0, 0, 1.0], [1.0, 0, 0], [0, 1.0, 0]])
    pawl.geo[lod].prism(ol, -0.03, 0.03, "iron", "pawl", R=Rp, t=tuple(pv + np.array([0.0, 0.0, 0.0])))
    pawl.geo[lod].cyl(tuple(pv + (-0.05, 0, 0)), tuple(pv + (0.05, 0, 0)), 0.03, n=6, mat="iron", tag="pawl_pin",
                      up=(0, 0, 1))
    # ---- brake lever node (pivot on the left trestle top), wooden knob
    bp = np.array([p["KX"], -0.24, AX + 0.22])
    brake = A.part("brake_lever", None, tuple(bp))
    bg = brake.geo[lod]
    knob_c = np.array([p["KX"], -0.28, AX + 0.78])
    bg.beam(bp, knob_c - np.array([0, 0, 0.06]), 0.06, 0.06, mat="iron", tag="lever")
    bg.rock(tuple(knob_c), (0.085, 0.085, 0.09), seed=5, sub=2 if lod == 0 else 1, mat="wood", tag="knob",
            flat_bottom=False, rough=0.04)
    bg.cyl(tuple(bp + (-0.06, 0, 0)), tuple(bp + (0.06, 0, 0)), 0.045, n=8, mat="iron", tag="lever_hub", up=(0, 0, 1))
    # ---- rope node (top at the drum's front tangent, hangs to the chest hook at rest)
    travel, z_bottom = rise(p)
    hook_up = p["Hc"] + 0.22
    rope_top = np.array([0.0, -Rc, AX])
    L0 = AX - (z_bottom + hook_up)
    rope = A.part("rope", None, tuple(rope_top))
    pts = np.array([rope_top - np.array([0, 0, L0 * t]) for t in np.linspace(0, 1, 6)])
    rope.geo[lod].tube(pts, 0.028, n=(6, 5, 4)[lod], mat="rope", tag="rope")
    # ---- chest node (rest at the pit floor) + lid node + hook + rope sling
    cb = np.array([0.0, PY - 0.25 + 0.2, z_bottom])       # body centre line (front face at PY - 0.25)
    chest = A.part("chest", None, tuple(cb))
    hg = chest.geo[lod]
    Wc, Hc = p["Wc"], p["Hc"]
    body_h = Hc * 0.66
    hg.box(tuple(cb + (0, 0, body_h / 2)), (Wc, 0.4, body_h), mat="wood", tag="chest_body", chamfer=0.012 if lod == 0 else 0.0)
    if lod < 2:
        for xx in (-Wc * 0.36, 0.0, Wc * 0.36):
            hg.box(tuple(cb + (xx, 0, body_h / 2)), (0.05, 0.42, body_h + 0.01), mat="iron", tag="chest_band")
    hg.box(tuple(cb + (0, -0.205, body_h * 0.65)), (0.1, 0.02, 0.14), mat="bronze", tag="chest_lock")
    sling = [cb + np.array([-Wc * 0.45, 0, Hc]), cb + np.array([0, 0, Hc + 0.2]), cb + np.array([Wc * 0.45, 0, Hc])]
    hg.tube(np.array(sling), 0.018, n=5, mat="rope", tag="sling")
    hg.tube(np.array([cb + np.array([0.09 * math.cos(a), 0, Hc + 0.22 + 0.09 * math.sin(a)]) for a in np.linspace(0, math.pi, 7)]),
            0.014, n=5, mat="iron", tag="hook")
    lid = A.part("chest_lid", "chest", tuple(cb + (0, 0.2, body_h)))
    lid.geo[lod].cyl(tuple(cb + (-Wc / 2, 0, body_h)), tuple(cb + (Wc / 2, 0, body_h)), 0.2, n=(10, 7, 4)[lod],
                     mat="wood", tag="chest_lid", up=(0, 0, 1))
    if lod == 0:
        A.marker("artifact_spot", tuple(cb + (0, 0, body_h * 0.5)), parent="chest")
    return A


STRICT_FACING = ("wood",)
SWATCHES = {
    "wood": dict(sheet=SHEET, box=(336, 690, 356, 740), metres=0.35, angle=-8.0, tile_v="stack"),
    "rope": dict(sheet=SHEET, box=(250, 575, 300, 600), metres=0.25),
    "iron": dict(sheet=SHEET, box=(112, 553, 160, 566), metres=0.25),
    "stone": dict(sheet=SHEET, box=(60, 790, 110, 820), metres=0.4),
    "ground": dict(sheet=SHEET, box=(20, 842, 80, 862), metres=0.5),
    "bronze": dict(sheet=SHEET, box=(262, 812, 272, 824), metres=0.06),
}


def _resolve_pose(v, p):
    travel, _ = rise(p)
    if v.pose.get("chest") == "raised":
        v.pose["chest"] = {"loc": (0, 0, travel * CHEST_RAISED)}


def _silhouette_iou(p, views):
    import cv2
    A = pv2.Asset(ID, ATLAS)
    build(A, p, 2)
    out = []
    for v in views:
        pose = dict(v.render_pose if v.render_pose is not None else v.pose)
        if pose.get("chest") == "raised":
            pose["chest"] = {"loc": (0, 0, rise(p)[0] * CHEST_RAISED)}
        Wm = A.world_mats(pose)
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
            for f in F:
                cv2.fillConvexPoly(m, np.round(pts[f]).astype(np.int32), 1)
        ref, _ = v.mask()
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
            for kind, steps in (("rx", np.radians([-1.2, -0.6, 0.6, 1.2])), ("ry", np.radians([-1.2, -0.6, 0.6, 1.2])),
                                ("rz", np.radians([-1.0, -0.5, 0.5, 1.0])), ("tx", [-0.04, -0.02, 0.02, 0.04]),
                                ("ty", [-0.04, -0.02, 0.02, 0.04]), ("f", [0.96, 0.98, 1.02, 1.04])):
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


def solve(views):
    params, reps = pv2.solve_views(views, points, PARAMS, FREE, prior_sigma=PRIOR)
    best = _silhouette_iou(params, views)[0]
    # sane ranges only: a taller well wall or a wider ground patch can buy silhouette IoU without looking like art/10
    grids = {"SPL": np.arange(0.42, 0.63, 0.04), "RG": np.arange(0.44, 0.65, 0.03), "RP": np.arange(0.16, 0.31, 0.02),
             "GT": np.arange(18.0, 46.0, 4.0), "HR": np.arange(0.16, 0.31, 0.03), "GRP": np.arange(0.8, 1.41, 0.1), "WH": np.arange(0.06, 0.36, 0.03), "SH": np.arange(0.25, 0.81, 0.05),
             "GR": np.arange(0.3, 1.41, 0.1), "TB": np.arange(0.3, 0.71, 0.05), "PR": np.arange(0.55, 0.86, 0.05),
             "LW": np.arange(0.18, 0.34, 0.03), "FY": np.arange(0.25, 0.56, 0.05), "TZ": np.arange(0.5, 1.01, 0.05),
             "SPIL": np.arange(0.14, 0.39, 0.06),
             "SPIR": np.arange(-0.18, 0.07, 0.06), "PX": np.arange(-0.3, 0.21, 0.05), "PSX": np.arange(-0.5, -0.19, 0.05)}
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
    pv2.log(f"  shape by silhouette IoU: " + ", ".join(f"{k} {params[k]:.2f}" for k in grids) + f" -> IoU {best:.3f}")
    for v in views:
        _resolve_pose(v, params)
    return params


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
    pv2.add_clip(A, B, "lf_rope_release", 1.3, {
        "brake_lever": lambda t: {"rot": (BRAKE_ON * (1 - _ease(t, 0.0, 0.17)), 0, 0)},
        "drum": lambda t: {"rot": (rs(t)[0], 0, 0)},
        "crank": lambda t: {"rot": (rs(t)[0], 0, 0)},
        "rope": lambda t: {"scale": (1, 1, rs(t)[1])},
        "chest": lambda t: {"loc": (0, 0, rs(t)[2]), "rot": (0, 0, math.radians(4) * math.sin(t * 10.5) * (1 - _ease(t, 1.0, 1.3)))},
        "pawl": lambda t: {"rot": (PAWL_ON + math.radians(7) * abs(math.sin(-rs(t)[0] * TEETH / 2)) * (1 - _ease(t, 1.13, 1.3)), 0, 0)},
    }, markers={"chest_clear_of_pit": 1.0}, note="crank turns the drum, the rope shortens, the chest rises out of the pit")
    up = raise_state(1.0)
    pv2.add_clip(A, B, "lf_lock_mechanism", 1.8, {
        "chest": lambda t: {"loc": (0, 0, up[2]), "rot": (0, 0, math.radians(3) * math.sin(t * 12.0) * (1 - _ease(t, 0, 1.0)))},
        "drum": lambda t: {"rot": (up[0], 0, 0)}, "crank": lambda t: {"rot": (up[0], 0, 0)},
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
    return {
        "mechanism": "winch_sequence",
        "symbol_targets": {
            "brake": {"node": "brake_lever", "rotation_x_deg": round(math.degrees(BRAKE_ON), 2), "clip": "lf_winch_brake"},
            "pawl": {"node": "pawl", "rotation_x_deg": round(math.degrees(PAWL_ON), 2), "clip": "lf_winch_pawl"},
            "raise": {"clip": "lf_rope_release", "nodes": {
                "drum": {"rotation_x_deg": round(math.degrees(up_turn), 2)},
                "crank": {"rotation_x_deg": round(math.degrees(up_turn), 2)},
                "rope": {"scale_y": round((L0 - travel) / L0, 4), "note": "rope node scales along its own length (glTF Y)"},
                "chest": {"translation_offset": [0, round(travel, 4), 0]}, "brake_lever": {"rotation_x_deg": 0.0}}},
            "solved": {"clip": "lf_lock_mechanism", "chest_lid": {"rotation_x_deg": -105.0}},
            "wrong_input": "server resets: tween nodes back to rest (all 0, rope scale 1)",
            "sites": ["lf_site_03", "lf_site_07", "lf_site_11"], "order": ["brake", "pawl", "raise"]},
        "sockets": {"artifact_spot_raised": g(tuple(cb + (0, 0, travel + p["Hc"] * 0.33)))},
        "notes": "v2: blueprint measured on the art/10 main drawing (camera solved), painting projection; crank and drum "
                 "share the axle (1:1); the pawl clicks over the 22-tooth ratchet while raising.",
    }
