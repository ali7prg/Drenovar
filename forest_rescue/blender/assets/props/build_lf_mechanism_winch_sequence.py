"""lf_mechanism_winch_sequence: oak A-frame hand winch over a stone-lined pit; rope drum with ratchet gear,
crank, pawl and brake lever; the artifact chest hangs from the rope.

Steps (campaign solution brake -> pawl -> raise): clip lf_winch_brake, lf_winch_pawl, lf_rope_release
(raise: crank + drum turn, rope shortens, chest rises out of the pit, pawl clicks), then lf_lock_mechanism
(chest lid unlocks and opens at the top). Run: python3 forest_rescue/blender/run_limited.py ... --iter N
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np

import mechkit as mk
import motifs as mo
import propkit as pk
import propshaders as sh
from propkit import M4, Rx, Ry, Rz

ASSET = "lf_mechanism_winch_sequence"
AX_Z, AX_Y = 1.42, 0.0          # drum axle
FX = 0.78                       # frame (trestle) x
PIT = np.array([0.0, -0.205, 0.0])
PIT_R, PIT_D = 0.62, 1.0
DRUM_R, ROPE_R = 0.17, 0.205
CHEST_H = 0.32
Z_BOTTOM = -PIT_D + 0.02        # chest bottom at rest (in the pit)
Z_TOP = 0.30                    # chest bottom when raised
RISE = Z_TOP - Z_BOTTOM
HOOK_UP = CHEST_H + 0.16        # rope end above the chest bottom
ROPE_TOP = np.array([0.0, -ROPE_R, AX_Z])
L0 = AX_Z - (Z_BOTTOM + HOOK_UP)
DRUM_TURN = RISE / ROPE_R       # radians
BRAKE_ON = math.radians(-48)
PAWL_ON = math.radians(-24)


def gear_outline(r_root, r_tip, teeth, lod):
    pts = []
    per = 4 if lod < 2 else 2
    for k in range(teeth):
        a0 = 2 * math.pi * k / teeth
        da = 2 * math.pi / teeth
        if per == 4:
            for f, r in ((0.0, r_root), (0.25, r_tip), (0.5, r_tip), (0.75, r_root)):
                pts.append((r * math.cos(a0 + f * da), r * math.sin(a0 + f * da)))
        else:
            for f, r in ((0.0, r_root), (0.4, r_tip)):
                pts.append((r * math.cos(a0 + f * da), r * math.sin(a0 + f * da)))
    return np.array(pts)


def build(lod):
    B = pk.Builder(lod)
    seg = B.seg(28, 18, 12)
    # ---------------- ground ring + pit (stone lined) + rim stones
    gr = pk.orient_toward(pk.lathe(np.array([[PIT_R + 0.05, 0.02], [1.45, 0.0]]), seg, smooth=True), (0, 0, 1))
    B.add("root", "ground", "dirt", gr.transformed(M4(None, PIT)), meta={"moss": 0.6})
    wall = pk.lathe(np.array([[PIT_R, 0.04], [PIT_R - 0.02, -PIT_D * 0.5], [PIT_R - 0.04, -PIT_D]]), seg, smooth=True)
    B.add("root", "pit_wall", "limestone", wall.transformed(M4(None, PIT)), meta={"block_len": 0.3, "course_h": 0.16, "moss": 0.4})
    fl = pk.lathe(np.array([[0.0, -PIT_D], [PIT_R - 0.04, -PIT_D]]), seg)
    fl.F = [tuple(reversed(f)) for f in fl.F]
    fl.UV = [list(reversed(u)) for u in fl.UV]
    B.add("root", "pit_floor", "dirt", fl.transformed(M4(None, PIT)))
    rng = np.random.RandomState(7)
    nst = 14 if lod < 2 else 8
    for k in range(nst):
        a = 2 * math.pi * k / nst + rng.uniform(-0.1, 0.1)
        r = PIT_R + 0.2 + rng.uniform(-0.03, 0.06)
        c = PIT + np.array([r * math.cos(a), r * math.sin(a), 0.07])
        w, d, h = rng.uniform(0.32, 0.46), rng.uniform(0.26, 0.34), rng.uniform(0.18, 0.28)
        t = np.array([-math.sin(a), math.cos(a), 0]) * w / 2
        st = pk.beam(c - t + np.array([0, 0, h / 2 - 0.07]), c + t + np.array([0, 0, h / 2 - 0.07]), d, h, chamfer=0.04)
        B.add("root", "rim_stones", "limestone", st, meta={"moss": 0.6})
    # ---------------- A-frame trestles
    for sx in (-1, 1):
        x = sx * FX
        top = np.array([x, AX_Y, AX_Z + 0.12])
        for sy in (-1, 1):
            foot = np.array([x, sy * 0.78, 0.10])
            B.add("root", "frame_legs", "oak", pk.beam(foot, top + np.array([0, sy * 0.08, 0]), 0.13, 0.15, chamfer=0.018))
        B.add("root", "frame_sills", "oak", pk.beam((x, -0.95, 0.07), (x, 0.95, 0.07), 0.16, 0.14, chamfer=0.018))
        B.add("root", "frame_cross", "oak", pk.beam((x, -0.47, 0.62), (x, 0.47, 0.62), 0.12, 0.12, chamfer=0.015))
        B.add("root", "frame_tops", "oak", pk.beam((x, -0.2, AX_Z + 0.1), (x, 0.2, AX_Z + 0.1), 0.2, 0.2, chamfer=0.02))
        # iron bearing + brackets
        bear = pk.lathe(np.array([[0.0, -0.06], [0.075, -0.06], [0.08, 0.06], [0.0, 0.06]]), B.seg(12, 8, 6), smooth=False)
        B.add("root", "bearings", "iron", bear.transformed(M4(Ry(math.pi / 2), (x + sx * 0.12, AX_Y, AX_Z))))
        for zz in (0.62, AX_Z + 0.1):
            br = pk.beam((x - 0.11, -0.12, zz), (x + 0.11, -0.12, zz), 0.03, 0.08, chamfer=0.006)
            B.add("root", "brackets", "iron", br, meta={"rivets": {"du": 0.08, "v": [pk.rect_face_v(0.03, 0.08, 0.006, "-N")], "r": 0.01}})
    # cross beams between the trestles + diagonal brace
    B.add("root", "frame_tie", "oak", pk.beam((-FX, 0.45, 0.62), (FX, 0.45, 0.62), 0.11, 0.11, chamfer=0.015))
    B.add("root", "frame_tie", "oak", pk.beam((-FX, 0.5, 0.2), (0.0, 0.5, 0.62), 0.1, 0.1, chamfer=0.015))
    # ---------------- drum node: core, flanges, rope coil, ratchet gear, axle
    d = []
    core_ = pk.rod((-0.52, AX_Y, AX_Z), (0.52, AX_Y, AX_Z), DRUM_R, B.seg(20, 14, 8))
    B.add("drum", "drum_core", "oak", core_)
    coil = pk.rod((-0.45, AX_Y, AX_Z), (0.45, AX_Y, AX_Z), ROPE_R, B.seg(24, 16, 10), caps=False)
    B.add("drum", "drum_rope", "rope", coil, meta={"rope_pitch": 0.9 / 11, "rope_circ": 2 * math.pi * ROPE_R})
    for xx in (-0.5, 0.5):
        fl_ = pk.rod((xx - 0.025, AX_Y, AX_Z), (xx + 0.025, AX_Y, AX_Z), 0.255, B.seg(20, 14, 8))
        B.add("drum", "drum_flanges", "oak", fl_, meta={"pith_x": 0.0, "pith_y": 0.0})
    for xx in (-0.5, 0.5):
        band = pk.rod((xx - 0.03, AX_Y, AX_Z), (xx + 0.03, AX_Y, AX_Z), 0.262, B.seg(20, 14, 8), caps=False)
        B.add("drum", "drum_bands", "iron", band)
    gear = pk.extrude(gear_outline(0.27, 0.32, 22, lod), 0.06, chamfer=0.008)
    B.add("drum", "ratchet", "iron", gear.transformed(M4(Ry(-math.pi / 2), (-0.58, AX_Y, AX_Z))))
    hub = pk.rod((-0.66, AX_Y, AX_Z), (-0.52, AX_Y, AX_Z), 0.09, B.seg(10, 7, 5))
    B.add("drum", "ratchet", "iron", hub)
    axle = pk.rod((-0.98, AX_Y, AX_Z), (0.98, AX_Y, AX_Z), 0.04, B.seg(8, 6, 4))
    B.add("drum", "axle", "iron", axle)
    # ---------------- crank node (outside the right trestle, same axle)
    arm = pk.beam((1.0, AX_Y, AX_Z), (1.0, AX_Y, AX_Z - 0.36), 0.05, 0.035, chamfer=0.008)
    B.add("crank", "crank_arm", "iron", arm)
    hb = pk.rod((0.97, AX_Y, AX_Z), (1.06, AX_Y, AX_Z), 0.07, B.seg(10, 7, 5))
    B.add("crank", "crank_arm", "iron", hb)
    grip = pk.lathe(np.array([[0.0, 0.0], [0.035, 0.01], [0.042, 0.12], [0.036, 0.22], [0.0, 0.23]]), B.seg(10, 7, 5))
    B.add("crank", "crank_grip", "dark_oak", grip.transformed(M4(Ry(math.pi / 2), (1.03, AX_Y, AX_Z - 0.36))))
    # ---------------- pawl node (pivot on the left trestle, above-front of the gear)
    pv = np.array([-0.58, -0.30, AX_Z + 0.27])
    ol = np.array([[0.0, -0.022], [0.10, -0.034], [0.128, -0.062], [0.098, -0.046], [0.0, 0.022]])
    ang = math.radians(-18)
    ol = ol @ np.array([[math.cos(ang), math.sin(ang)], [-math.sin(ang), math.cos(ang)]])
    pawl = pk.extrude(ol, 0.05, chamfer=0.006)
    Mp = np.array([[0, 0, 1, pv[0] - 0.025], [1, 0, 0, pv[1]], [0, 1, 0, pv[2]], [0, 0, 0, 1]], float)
    B.add("pawl", "pawl", "iron", pawl.transformed(Mp))
    B.add("pawl", "pawl", "iron", pk.rod(pv + np.array([-0.04, 0, 0]), pv + np.array([0.06, 0, 0]), 0.025, B.seg(8, 6, 4)))
    # ---------------- brake lever node (pivot on top of the left trestle), brake shoe on the flange
    bp = np.array([-FX, 0.12, AX_Z + 0.22])
    lever = pk.beam(bp, bp + np.array([0, -0.08, 0.52]), 0.05, 0.05, chamfer=0.008)
    B.add("brake", "brake_lever", "iron", lever)
    knob = pk.lathe(np.array([[0.0, 0.0], [0.035, 0.02], [0.04, 0.06], [0.0, 0.1]]), B.seg(10, 7, 5))
    B.add("brake", "brake_knob", "dark_oak", knob.transformed(M4(None, bp + np.array([0, -0.08, 0.5]))))
    hubb = pk.rod(bp + np.array([-0.05, 0, 0]), bp + np.array([0.05, 0, 0]), 0.035, B.seg(8, 6, 4))
    B.add("brake", "brake_lever", "iron", hubb)
    # ---------------- rope (node pivot at the drum tangent; mesh hangs down L0)
    rope = pk.rod(ROPE_TOP, ROPE_TOP - np.array([0, 0, L0]), 0.022, B.seg(6, 5, 4), segs=4)
    B.add("rope", "rope", "rope", rope, meta={"rope_pitch": 0.05, "rope_circ": 2 * math.pi * 0.022})
    # ---------------- chest node (in the pit), hook + lid node
    cb = np.array([PIT[0], PIT[1], Z_BOTTOM])
    body = pk.beam(cb + np.array([-0.26, 0, CHEST_H * 0.35]), cb + np.array([0.26, 0, CHEST_H * 0.35]), 0.34, CHEST_H * 0.7,
                   chamfer=0.012)
    B.add("chest", "chest_body", "plank", body)
    for xx in (-0.2, 0.0, 0.2):
        bd = pk.beam(cb + np.array([xx, 0, -0.005]), cb + np.array([xx, 0, CHEST_H * 0.72]), 0.035, 0.355)
        B.add("chest", "chest_bands", "iron", bd, max_lod=1)
    hook = pk.tube(np.array([cb + np.array([0.12 * math.cos(a), 0, CHEST_H + 0.08 + 0.08 * math.sin(a)]) for a in
                             np.linspace(0, math.pi, 8)]), 0.012, 5)
    B.add("chest", "chest_hook", "iron", hook)
    B.add("chest", "chest_hook", "iron", pk.rod(cb + np.array([0, 0, CHEST_H + 0.16]), cb + np.array([0, 0, HOOK_UP + 0.02]), 0.015, 5))
    lidp = np.array([[0.17 * math.cos(a), 0.09 * math.sin(a)] for a in np.linspace(0, math.pi, B.seg(9, 6, 3))])
    lid = pk.sweep(np.array([cb + np.array([-0.265, 0, CHEST_H * 0.7]), cb + np.array([0.265, 0, CHEST_H * 0.7])]),
                   lidp, up=(0, 1, 0), smooth=False)
    B.add("chest_lid", "chest_lid", "plank", lid)
    lock = pk.beam(cb + np.array([-0.04, -0.175, CHEST_H * 0.6]), cb + np.array([0.04, -0.175, CHEST_H * 0.6]), 0.02, 0.09)
    B.add("chest", "chest_lock", "bronze", lock)
    return B


def spec():
    return {"root": {},
            "drum": {"pivot": (0.0, AX_Y, AX_Z), "export_name": "drum"},
            "crank": {"pivot": (1.0, AX_Y, AX_Z), "export_name": "crank"},
            "pawl": {"pivot": (-0.58, -0.30, AX_Z + 0.27), "export_name": "pawl"},
            "brake": {"pivot": (-FX, 0.12, AX_Z + 0.22), "export_name": "brake_lever"},
            "rope": {"pivot": tuple(ROPE_TOP), "export_name": "rope"},
            "chest": {"pivot": (PIT[0], PIT[1], Z_BOTTOM), "export_name": "chest"},
            "chest_lid": {"pivot": (PIT[0], PIT[1] + 0.17, Z_BOTTOM + CHEST_H * 0.7), "parent": "chest",
                          "export_name": "chest_lid"}}


def raise_state(t):
    """t in [0,1] -> (drum angle, rope scale, chest dz)."""
    dz = RISE * t
    return -DRUM_TURN * t, (L0 - dz) / L0, dz


def clips(A):
    ease = mk.ease
    pk.add_clip(A, "lf_winch_brake", {"brake": lambda f: {"rot": (BRAKE_ON * float(pk.ease_out_back(np.clip(f / 15, 0, 1), 1.1)), 0, 0)}},
                18, markers={"brake_set": 0.5})
    pk.add_clip(A, "lf_winch_pawl", {"pawl": lambda f: {"rot": (PAWL_ON * float(pk.ease_out_back(np.clip(f / 11, 0, 1), 1.6)), 0, 0)},
                                     "brake": lambda f: {"rot": (BRAKE_ON, 0, 0)}}, 15, markers={"pawl_engaged": 0.37})

    def rs(f):
        return raise_state(ease(f, 4, 36))
    teeth = 22
    pk.add_clip(A, "lf_rope_release", {
        "brake": lambda f: {"rot": (BRAKE_ON * (1 - ease(f, 0, 5)), 0, 0)},
        "drum": lambda f: {"rot": (rs(f)[0], 0, 0)},
        "crank": lambda f: {"rot": (rs(f)[0], 0, 0)},
        "rope": lambda f: {"scale": (1, 1, rs(f)[1])},
        "chest": lambda f: {"loc": (0, 0, rs(f)[2]), "rot": (0, 0, math.radians(4) * math.sin(f * 0.35) * (1 - ease(f, 30, 39)))},
        "pawl": lambda f: {"rot": (PAWL_ON + math.radians(7) * abs(math.sin(-rs(f)[0] * teeth / 2)) * (1 - ease(f, 34, 39)), 0, 0)},
    }, 39, markers={"chest_clear_of_pit": 30 / 30})
    up = raise_state(1.0)
    pk.add_clip(A, "lf_lock_mechanism", {
        "chest": lambda f: {"loc": (0, 0, up[2]), "rot": (0, 0, math.radians(3) * math.sin(f * 0.4) * (1 - ease(f, 0, 30)))},
        "drum": lambda f: {"rot": (up[0], 0, 0)}, "crank": lambda f: {"rot": (up[0], 0, 0)},
        "rope": lambda f: {"scale": (1, 1, up[1])}, "pawl": lambda f: {"rot": (PAWL_ON, 0, 0)},
        "chest_lid": lambda f: {"rot": (-math.radians(105) * ease(f, 14, 46), 0, 0)},
    }, 54, markers={"lid_unlocked": 14 / 30, "lid_open": 46 / 30})


def meta(A):
    up = raise_state(1.0)
    return {"symbol_targets": {
        "brake": {"node": "brake_lever", "rotation_x_deg": round(math.degrees(BRAKE_ON), 2), "clip": "lf_winch_brake"},
        "pawl": {"node": "pawl", "rotation_x_deg": round(math.degrees(PAWL_ON), 2), "clip": "lf_winch_pawl"},
        "raise": {"clip": "lf_rope_release", "nodes": {
            "drum": {"rotation_x_deg": round(math.degrees(up[0]), 2)}, "crank": {"rotation_x_deg": round(math.degrees(up[0]), 2)},
            "rope": {"scale_y": round(up[1], 4), "note": "rope node scales along its own length (glTF Y)"},
            "chest": {"translation_offset": [0, round(up[2], 4), 0]}, "brake_lever": {"rotation_x_deg": 0.0}}},
        "solved": {"clip": "lf_lock_mechanism", "chest_lid": {"rotation_x_deg": -105.0}},
        "wrong_input": "server resets: tween nodes back to rest (all 0, rope scale 1)",
        "sites": ["lf_site_03", "lf_site_07", "lf_site_11"], "order": ["brake", "pawl", "raise"]},
        "sockets": {"artifact_spot_raised": pk.b2g((PIT[0], PIT[1], Z_TOP + CHEST_H * 0.5))}}


def main():
    views = [{"name": "main", "box": (0, 505, 528, 875), "x0": [-0.6, 0.42, 0, 8.0, 2.4, 0, 0],
              "pose": {"brake": {"rot": (BRAKE_ON * 0.0, 0, 0)}, "chest": {"loc": (0, 0, RISE * 0.92)},
                       "rope": {"scale": (1, 1, (L0 - RISE * 0.92) / L0)}}}]
    mk.run(ASSET, spec(), build, views, clips, meta,
           markers=[("artifact_spot", (PIT[0], PIT[1], Z_BOTTOM + CHEST_H * 0.5), "chest")],
           notes="Crank and drum share the axle (1:1); pawl clicks over the 22-tooth ratchet while raising.",
           main_view="main")


if __name__ == "__main__":
    main()
