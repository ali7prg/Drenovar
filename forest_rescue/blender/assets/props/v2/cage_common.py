"""Shared cage build: door leaf + hinges + socket plates (4 families) + latch + markers + clips + meta.

Production rule (ART_REFERENCE_NOTES_MODEL_AGENT_RU): hinge on the LEFT jamb seen from outside, one pivot,
door opens OUTWARD by 95 deg. Door faces -Y (Blender) = +Z glTF. Hinge axis vertical through the knuckles.
"""
import math

import numpy as np

import cagegeo as CG
import pv2

FAMILIES = ("stone_rune", "bronze_seal", "amber_crystal", "bone_key")
# artifact silhouettes (metres) shared with the artifact build (sockets fit them with 1 cm clearance)
ART_SIZE = {"stone_rune": 0.30, "bronze_seal": 0.30, "amber_crystal": 0.32, "bone_key": 0.34}
OPEN_DEG = 95.0


def socket_plate(g, family, c, lod, frame_mat="bronze", tag_prefix="socket", native_style=None):
    """Socket receptacle on the door's outer face; c = centre of the plate's back (on the stile face).
    The plate faces -Y. Shapes: circle (stone_rune), hexagon (bronze_seal), diamond (amber_crystal),
    keyhole plate (bone_key)."""
    R = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)      # local x->X, y->Z, z->-Y (outward)
    c = np.asarray(c, float)
    tag = f"{tag_prefix}_{family}"
    n_round = 20 if lod == 0 else (12 if lod == 1 else 8)
    s = ART_SIZE[family]
    if family == "stone_rune":
        r_in = s / 2 + 0.012
        CG.ring_prism(g, c, R, r_in + 0.05, r_in, n_round, 0.0, 0.05, "stone", tag + "_rim")
        g.prism(CG.ngon(r_in, n_round), 0.0, 0.018, "stone", tag + "_seat", R=R, t=c)
        if lod == 0:   # C-shaped iron clasp on the hinge side (painting)
            g.box(c + (-(r_in + 0.065), -0.035, 0), (0.05, 0.05, 0.16), mat="iron", tag=tag + "_clasp")
    elif family == "bronze_seal":
        r_in = s / 2 + 0.012
        outer = CG.ngon(r_in + 0.05, 6, 0.0)
        inner = CG.ngon(r_in, 6, 0.0)
        CG.outline_ring(g, c, R, outer, inner, 0.0, 0.045, frame_mat, tag + "_rim")
        g.prism(inner, 0.0, 0.016, frame_mat, tag + "_seat", R=R, t=c)
    elif family == "amber_crystal":
        hw, hh = 0.13 + 0.012, s / 2 + 0.012
        inner = np.array([[0, -hh], [hw, 0], [0, hh], [-hw, 0]])
        outer = np.array([[0, -hh - 0.06], [hw + 0.05, 0], [0, hh + 0.06], [-hw - 0.05, 0]])
        CG.outline_ring(g, c, R, outer, inner, 0.0, 0.045, frame_mat, tag + "_rim")
        g.prism(inner, 0.0, 0.016, frame_mat, tag + "_seat", R=R, t=c)
    elif family == "bone_key":
        # stone/bronze keyhole plate with an octagonal outline and a keyhole recess
        oct_ = CG.ngon(0.13, 8, math.pi / 8)
        g.prism(oct_, 0.0, 0.035, frame_mat, tag + "_plate", R=R, t=c)
        # keyhole: dark recess = round hole + slot drawn as a thin dark insert (texture), slightly raised lips
        g.prism(CG.ngon(0.035, 10), 0.035, 0.040, "iron", tag + "_hole", R=R, t=c + (0, 0, 0.03))
        g.box(c + (0, -0.038, -0.03), (0.03, 0.006, 0.07), mat="iron", tag=tag + "_slot")
    return g


def add_door_and_sockets(A, cfg, lod, native):
    """cfg: dict(hinge_x, y_face (outer face of the leaf), y_back, x1 (free edge), z0, z_top_side, z_apex,
    stile_w, rail_h, bars, rails_z, socket_z, socket_x, strap_z, strap_len, wood_mat, bar_r, arch)."""
    hx = cfg["hinge_x"]
    yf = cfg["y_face"]
    t = cfg["thick"]
    ym = yf + t / 2
    piv = np.array([hx, yf - 0.035, 0.0])
    door = A.part("door_pivot", "root", piv)
    g = door.geo[lod]
    x0 = hx + 0.012
    x1 = cfg["x1"]
    z0 = cfg["z0"]
    zs = cfg["z_top_side"]
    za = cfg["z_apex"]
    sw = cfg["stile_w"]
    wm = cfg.get("wood_mat", "wood")
    # stiles
    g.box(((x0 + sw / 2), ym, (z0 + zs) / 2), (sw, t, zs - z0), mat=wm, tag="door_stile")
    g.box(((x1 - sw / 2), ym, (z0 + zs) / 2), (sw, t, zs - z0), mat=wm, tag="door_stile")
    # bottom rail
    g.box(((x0 + x1) / 2, ym, z0 + cfg["rail_h"] / 2), (x1 - x0, t, cfg["rail_h"]), mat=wm, tag="door_rail")
    # segmental arched top rail
    n = 9 if lod == 0 else (6 if lod == 1 else 4)
    xs = np.linspace(x0, x1, n)
    xc = (x0 + x1) / 2
    half = (x1 - x0) / 2
    zarc = zs + (za - zs) * np.sqrt(np.clip(1 - ((xs - xc) / half) ** 2, 0, 1))
    P = np.stack([xs, np.full(n, ym), zarc - 0.06], 1)
    CG.sweep_rect(g, P, t, 0.13, up=(0, -1, 0), mat=wm, tag="door_arch")
    # iron bars and cross rails
    nb = cfg["bars"] if lod < 2 else max(3, cfg["bars"] // 2)
    bx = np.linspace(x0 + sw, x1 - sw, nb + 2)[1:-1]
    for x in bx:
        ztop = zs + (za - zs) * math.sqrt(max(0.0, 1 - ((x - xc) / half) ** 2)) - 0.1
        g.cyl((x, ym, z0 + cfg["rail_h"] - 0.01), (x, ym, ztop), cfg["bar_r"], n=6 if lod == 0 else 4, mat="iron",
              tag="door_bar", caps=(False, False))
    for zr in cfg["rails_z"]:
        g.box((xc, ym - 0.004, zr), (x1 - x0 - 2 * sw + 0.02, 0.03, 0.045), mat="iron", tag="door_ironrail")
    if lod == 0:
        for zr in cfg["rails_z"]:
            for x in bx:
                g.box((x, ym - 0.022, zr), (0.03, 0.012, 0.03), mat="iron", tag="door_rivet")
        for k in range(6):
            x = x0 + 0.06 + (x1 - x0 - 0.12) * k / 5
            g.box((x, yf - 0.005, z0 + cfg["rail_h"] / 2), (0.028, 0.012, 0.028), mat="iron", tag="door_rivet")
    # hinge straps + knuckles (knuckles straddle the pivot)
    for zz in cfg["strap_z"]:
        CG.door_hinge_strap(g, (hx, 0.0), yf, zz, cfg["strap_len"], cfg.get("strap_w", 0.09), lod, mat="bronze",
                            tag="hinge_strap")
        CG.knuckle(g, piv[0], piv[1], zz - 0.075, zz + 0.075, 0.03, n=8 if lod == 0 else 6, mat="bronze", tag="knuckle")
    # socket plates (one node per family, native visible)
    sc = np.array([cfg["socket_x"], yf, cfg["socket_z"]])
    for fam in FAMILIES:
        nm = f"socket_{fam}"
        A.part(nm, "door_pivot", sc)
        socket_plate(A.g(nm, lod), fam, sc, lod, frame_mat=cfg.get("socket_mat", "bronze"))
        if fam != native and nm not in A.hidden:
            A.hidden.append(nm)
    # latch bolt (slides along -X into the door when unlocking): node on the door
    lat = A.part("latch_pivot", "door_pivot", (x1 - 0.02, yf - 0.03, cfg["latch_z"]))
    lg = lat.geo[lod]
    lg.box((x1 + 0.03, yf - 0.03, cfg["latch_z"]), (0.16, 0.035, 0.05), mat="iron", tag="latch_bolt")
    lg.box((x1 - 0.06, yf - 0.05, cfg["latch_z"]), (0.04, 0.03, 0.08), mat="iron", tag="latch_knob")
    return piv


def add_markers(A, cfg, piv):
    sc = np.array([cfg["socket_x"], cfg["y_face"] - 0.05, cfg["socket_z"]])
    A.marker("key_slot", sc, parent="door_pivot", rot=(math.pi / 2, 0, 0))
    A.marker("hinge_axis_bottom", (piv[0], piv[1], cfg["z0"]), parent=None)
    A.marker("hinge_axis_top", (piv[0], piv[1], cfg["z_top_side"]), parent=None)
    A.marker("floor", (0.0, 0.0, cfg["floor_z"]), parent=None)
    for i, (gx, gz) in enumerate(cfg["captive_slots_xz"]):
        A.marker(f"captive_slot_{i}", (gx, -gz, cfg["floor_z"]), parent=None)
    for i, p in enumerate(cfg["exit"]):
        A.marker(f"exit_corridor_{i}", p, parent=None)


def add_clips(A, B):
    op = -math.radians(OPEN_DEG)

    def latch_off(t):
        return {"loc": (-0.12 * pv2.smooth((t - 0.15) / 0.55), 0, 0)}

    nat = [n for n in A.parts if n.startswith("socket_")]
    tracks = {"latch_pivot": latch_off}
    for nm in nat:
        tracks[nm] = lambda t: {"loc": (0, 0.012 * math.sin(math.pi * min(t / 0.6, 1.0)), 0)}
    pv2.add_clip(A, B, "lf_cage_unlock", 1.0, tracks, markers={"latch_clear": 0.7},
                 note="socket plate settles (artifact pressed home), latch bolt slides 0.12 m toward the hinge")

    def door_open(t):
        x = t / 1.6
        k = pv2.ease_io(x)
        ov = 0.035 * math.sin(math.pi * min(1.0, max(0.0, (x - 0.7) / 0.3)))
        return {"rot": (0, 0, op * (k + ov))}

    pv2.add_clip(A, B, "lf_cage_gate_open", 1.6,
                 {"door_pivot": door_open, "latch_pivot": lambda t: {"loc": (-0.12, 0, 0)}},
                 markers={"passage_clear": 1.2}, note="door swings OUTWARD 95 deg about the left-jamb hinge axis")

    def settle(t):
        x = t / 0.4
        return {"rot": (0, 0, op * (1.0 + 0.02 * math.cos(math.pi * x) * (1 - x)))}

    pv2.add_clip(A, B, "lf_cage_gate_settle", 0.4,
                 {"door_pivot": settle, "latch_pivot": lambda t: {"loc": (-0.12, 0, 0)}},
                 note="small damped settle at the open stop (95 deg)")

    def close(t):
        x = t / 1.2
        return {"rot": (0, 0, op * (1 - pv2.ease_io(x)))}

    def latch_back(t):
        return {"loc": (-0.12 * (1 - pv2.smooth((t - 1.0) / 0.2)), 0, 0)}

    pv2.add_clip(A, B, "lf_cage_gate_close", 1.2, {"door_pivot": close, "latch_pivot": latch_back},
                 note="door returns to the frame, latch re-engages at the end")


def cage_meta(A, cfg, piv, native, extra=None):
    g = pv2.b2g
    sock = {
        "floor": g((0.0, 0.0, cfg["floor_z"])),
        "hinge": g((piv[0], piv[1], cfg["z0"])),
    }
    for i, (gx, gz) in enumerate(cfg["captive_slots_xz"]):
        sock[f"captive_slot_{i}"] = [round(gx, 3), round(cfg["floor_z"], 3), round(gz, 3)]
    sc = (cfg["socket_x"], cfg["y_face"] - 0.05, cfg["socket_z"])
    info = {
        "floor": {"node": "floor", "height_m": round(cfg["floor_z"], 3),
                  "note": "top of the cage floor (glTF y). Seat captives at cage.global_transform * sockets.floor "
                          "(or add sockets.floor[1] to their ground height); captive_slot_0..2 are seat spots on the "
                          "floor that match actor_director CAGE_SLOTS."},
        "key_slot": {"node": "key_slot", "parent": "door_pivot", "position_closed": g(sc), "normal": [0, 0, 1],
                     "note": "live node on the door (moves with it). Use find_part('key_slot').global_transform; "
                             "parent the artifact there with identity transform. Not listed in 'sockets' on purpose "
                             "(a static array would leave the artifact floating when the door is open)."},
        "socket_plates": {f: f"socket_{f}" for f in FAMILIES},
        "socket_native": f"socket_{native}",
        "socket_switch": "all four plates are children of door_pivot at the same spot; only the native one is visible "
                         "by default (KHR_node_visibility). For a site whose artifact family differs, set "
                         "socket_<family>.visible = true and socket_<native>.visible = false.",
        "hinge_axis": {"nodes": ["hinge_axis_bottom", "hinge_axis_top"], "point": g(piv), "direction": [0, 1, 0],
                       "side": "LEFT jamb seen from outside (glTF -X side of the opening)"},
        "door": {"node": "door_pivot", "open_rotation_y_deg": -OPEN_DEG,
                 "rule": "door_pivot rotates about its local +Y (through the hinge pins); closed 0, open -95 deg "
                         "(outward: the free edge moves toward +Z)",
                 "clear_width_m": round(cfg["x1"] - piv[0] - 0.02, 3),
                 "clear_height_m": round(cfg["z_top_side"] - cfg["z0"], 3)},
        "latch": {"node": "latch_pivot", "travel_m": 0.12, "axis_gltf": [-1, 0, 0]},
        "exit_corridor": [g(p) for p in cfg["exit"]],
    }
    meta = {
        "door_open_deg": -OPEN_DEG,
        "door_open_deg_note": "signed Godot rotation.y of door_pivot for the open pose (actor_director.swing_door "
                              "fallback adds door_open_deg * amount: negative = outward)",
        "sockets": sock,
        "socketInfo": info,
        "poses": {"closed": {"door_pivot": {"rotation_y_deg": 0.0}, "latch_pivot": {"translation_offset": [0, 0, 0]}},
                  "open": {"door_pivot": {"rotation_y_deg": -OPEN_DEG},
                           "latch_pivot": {"translation_offset": [-0.12, 0, 0]}}},
    }
    if extra:
        meta.update(extra)
    return meta
