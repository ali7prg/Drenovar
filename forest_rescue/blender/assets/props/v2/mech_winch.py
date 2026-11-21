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
              PR=0.73, PY=-0.18, Wc=0.8, Hc=0.48, Zt=0.42)
FREE = ["AX", "L2", "Rc", "FXL", "FXR", "HX", "GX", "KX", "Ls", "Ac", "Lg", "Wc", "Hc", "Zt"]
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
        "gear_c": (p["GX"], -0.18, AX), "knob": (p["KX"], -0.28, AX + 0.78),
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
        solve_opts={"fov_prior": 22.0}, title="WINCH main view (chest raised to the pit mouth)")
    return [v]


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
    pit = np.array([0.0, PY, 0.0])
    rng = np.random.default_rng(7 + lod)
    # ---- ground ring, stone-lined well pit, rim stones
    CG.ring_prism(g, tuple(pit), np.eye(3), PR + 1.25, PR + 0.06, n, -0.03, 0.0, "ground", "ground")
    CG.ring_prism(g, tuple(pit), np.eye(3), PR + 0.08, PR, n, -PIT_D, 0.02, "stone", "pit_wall")
    CG.disc_prism(g, tuple(pit), np.eye(3), CG.ngon(PR, n), -PIT_D - 0.04, -PIT_D, "ground", "pit_floor")
    nst = (16, 10, 6)[lod]
    for k in range(nst):
        a = 2 * math.pi * k / nst + rng.uniform(-0.12, 0.12)
        r = PR + 0.3 + rng.uniform(-0.04, 0.08)
        c = pit + np.array([r * math.cos(a), r * math.sin(a), 0.1])
        g.rock(tuple(c), (rng.uniform(0.2, 0.28), rng.uniform(0.16, 0.22), rng.uniform(0.13, 0.2)), seed=k,
               sub=1, mat="stone", tag="rim_stone", flat_bottom=True, rough=0.12)
    # ---- A-frame trestles (legs splayed along X, front + back frames), sills, top blocks, iron straps
    for sx, fx in ((-1, p["FXL"]), (1, p["FXR"])):
        x = sx * fx
        top = np.array([x, 0.0, AX + 0.6])
        for sy in (-1, 1):
            y = sy * 0.3
            for side in (-1, 1):
                foot = np.array([x + side * 0.5, y * 1.2, 0.08])
                g.beam(foot, top + np.array([side * 0.07, y * 0.4, -0.06]), 0.14, 0.16, mat="wood", tag="leg",
                       chamfer=0.016 if lod == 0 else 0.0)
            g.beam((x - 0.36, y * 0.95, 0.5), (x + 0.36, y * 0.95, 0.5), 0.11, 0.11, mat="wood", tag="cross",
                   chamfer=0.012 if lod == 0 else 0.0)
            g.box((x - 0.5, y * 1.2, 0.08), (0.24, 0.26, 0.18), mat="iron", tag="shoe")
            g.box((x + 0.5, y * 1.2, 0.08), (0.24, 0.26, 0.18), mat="iron", tag="shoe")
        g.box((x, 0.0, AX + 0.58), (0.26, 0.74, 0.22), mat="wood", tag="top_block", chamfer=0.02 if lod == 0 else 0.0)
        g.box((x, -0.37, AX + 0.4), (0.3, 0.035, 0.12), mat="iron", tag="strap")
        g.box((x, -0.37, 0.45), (0.3, 0.035, 0.12), mat="iron", tag="strap")
        g.cyl((x - sx * 0.02, 0, AX), (x + sx * 0.14, 0, AX), 0.1, n=(12, 8, 6)[lod], mat="iron", tag="bearing",
              up=(0, 0, 1))
    # tie beam between the trestles (lower, at the back) + front brace
    g.beam((-p["FXL"], 0.34, 0.62), (p["FXR"], 0.34, 0.62), 0.12, 0.12, mat="wood", tag="tie",
           chamfer=0.015 if lod == 0 else 0.0)
    # ---- drum node: wooden core, rope coil, iron flange, ratchet gear (left), axle through both trestles
    drum = A.part("drum", None, (0.0, 0.0, AX))
    dg = drum.geo[lod]
    dg.cyl((-L2 - 0.05, 0, AX), (L2 + 0.05, 0, AX), Rc * 0.8, n=(20, 14, 8)[lod], mat="wood", tag="drum_core",
           up=(0, 0, 1))
    dg.cyl((-L2, 0, AX), (L2, 0, AX), Rc, n=(24, 16, 10)[lod], mat="rope", tag="coil", up=(0, 0, 1), caps=(False, False))
    dg.cyl((-L2 - 0.06, 0, AX), (-L2, 0, AX), Rc * 1.18, n=(20, 14, 8)[lod], mat="iron", tag="flange", up=(0, 0, 1))
    gear = gear_outline(Rc * 1.05, Rc * 1.2, TEETH, lod)
    Rg = np.array([[0, 0, 1.0], [1.0, 0, 0], [0, 1.0, 0]])      # local x -> world y, y -> z, z (extrusion) -> x
    dg.prism(gear, -0.05, 0.05, "iron", "ratchet", R=Rg, t=(p["GX"], 0.0, AX))
    dg.cyl((-p["FXL"] - 0.2, 0, AX), (p["HX"], 0, AX), 0.045, n=(8, 6, 4)[lod], mat="iron", tag="axle", up=(0, 0, 1))
    # ---- crank node: hub disc, shaft stub, arm, long wooden grip
    H = p["HX"]
    crank = A.part("crank", None, (H, 0.0, AX))
    cg = crank.geo[lod]
    cg.cyl((H - 0.04, 0, AX), (H + 0.06, 0, AX), 0.16, n=(16, 10, 6)[lod], mat="iron", tag="hub", up=(0, 0, 1))
    cg.cyl((H, 0, AX), (H + p["Ls"], 0, AX), 0.045, n=(8, 6, 4)[lod], mat="iron", tag="shaft", up=(0, 0, 1))
    cg.beam((H + p["Ls"], -0.05, AX + 0.04), (H + p["Ls"], -0.08, AX - p["Ac"] - 0.03), 0.06, 0.04, mat="iron",
            tag="crank_arm")
    gx0 = H + p["Ls"] + 0.04
    cg.cyl((gx0, -0.1, AX - p["Ac"]), (gx0 + p["Lg"], -0.1, AX - p["Ac"]), 0.055, n=(10, 7, 5)[lod], mat="wood",
           tag="grip", up=(0, 0, 1))
    # ---- pawl node (on the left trestle, over the gear)
    pv = np.array([p["GX"] - 0.02, -0.2, AX + Rc * 1.35])
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


def solve(views):
    params, reps = pv2.solve_views(views, points, PARAMS, FREE, prior_sigma=PRIOR)
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
