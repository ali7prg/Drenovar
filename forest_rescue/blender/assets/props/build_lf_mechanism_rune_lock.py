"""lf_mechanism_rune_lock: limestone drum with three rotating bronze glyph rings, green-crystal lever key,
stone door sliding down to reveal the artifact chest.

Rings (glTF nodes ring_1 top .. ring_3 bottom) rotate about the drum axis (glTF +Y). Each ring carries the
same 10 engraved positions (36 deg apart): 0 blank (rest) + the nine campaign symbols. To show symbol s at the
front index mark: ring rotation_y = RING_ANGLE[s] (meta.symbol_targets). Mechanism progress k (1..3) uses
ring_k. Run: python3 forest_rescue/blender/run_limited.py .../build_lf_mechanism_rune_lock.py --iter N
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

ASSET = "lf_mechanism_rune_lock"
GLYPHS = ["blank", "mountain", "river", "leaf", "coal", "seed", "tree", "sun", "stone", "root"]
STEP = 36.0
SITES = {"lf_site_02": ["mountain", "river", "leaf"], "lf_site_06": ["coal", "seed", "tree"],
         "lf_site_10": ["sun", "stone", "root"]}
R_OUT, WALL_TOP = 0.70, 0.58
RINGS = {  # stacked discs rising toward the back (drawing): name: (radius, centre_y, z_bottom, z_top)
    "ring_3": (0.555, 0.00, 0.640, 0.705),
    "ring_2": (0.470, 0.150, 0.705, 0.770),
    "ring_1": (0.375, 0.265, 0.770, 0.835),
}
GLYPH_R = {"ring_3": 0.43, "ring_2": 0.35, "ring_1": 0.25}   # glyph circle radius on each disc (front crescent)
DOOR_A0, DOOR_A1 = math.radians(247), math.radians(293)
DOOR_DROP = 0.44
KEY_STAND = np.array([-0.62, -1.05, 0.0])
NICHE = np.array([R_OUT + 0.02, -0.10, 0.36])


def ring_angle(symbol):
    """Ring rotation (radians, about +Z Blender / +Y glTF) bringing `symbol` to the front mark."""
    return -math.radians(STEP * GLYPHS.index(symbol))


def glyph_motif(name, R):
    """10 glyph positions engraved on the disc's top face (planar cap UV = local x, y in metres).
    Position k sits at angle 270 + 36k deg (k=0 at the front); glyph 'up' points to the disc centre so the
    glyph at the front index reads upright for the viewer."""
    from scipy import ndimage as ndi
    bb = (-R, -R, R, R)
    cv = mo.Canvas(bb, ppm=1100)
    big = np.zeros((cv.H, cv.W), np.float32)
    s_ = 0.16 if name != "ring_1" else 0.15
    rg = GLYPH_R[name]
    for k, g in enumerate(GLYPHS):
        sub = mo.Canvas((-s_ * 0.6, -s_ * 0.6, s_ * 0.6, s_ * 0.6), ppm=1100)
        if g == "blank":
            sub.ring((0, 0), s_ * 0.18, s_ * 0.06)
        else:
            mo.glyph(sub, g, (0, 0), s_, s_ * 0.1)
        m = sub.mask(0.0)
        ang = 270 + k * STEP
        m = ndi.rotate(m, -(ang - 270), reshape=False, order=1)
        cx = rg * math.cos(math.radians(ang))
        cy = rg * math.sin(math.radians(ang))
        px = int(round((cx - bb[0]) * cv.ppm - m.shape[1] / 2))
        py = int(round((bb[3] - cy) * cv.ppm - m.shape[0] / 2))
        h, w = m.shape
        y0, x0 = max(py, 0), max(px, 0)
        y1, x1 = min(py + h, big.shape[0]), min(px + w, big.shape[1])
        big[y0:y1, x0:x1] = np.maximum(big[y0:y1, x0:x1], m[y0 - py:y1 - py, x0 - px:x1 - px])
    cv.ring((0, 0), R - 0.03, 0.012)
    big = np.maximum(big, cv.mask(0.0))
    big = ndi.gaussian_filter(big, 1.2)
    return [{"mask": big, "bbox": bb, "isl": (2,), "depth": 0.004, "mode": "cut", "colour": sh.C(58, 40, 22), "tint": 0.85}]


def build(lod):
    B = pk.Builder(lod)
    seg = B.seg(44, 28, 16)
    # ---------------- plinth + drum wall (opening at the front for the door) + interior cavity
    base = pk.lathe(np.array([[0.0, 0.0], [R_OUT + 0.1, 0.0], [R_OUT + 0.1, 0.07], [R_OUT + 0.02, 0.085], [0.0, 0.085]]),
                    seg, smooth=False)
    B.add("root", "plinth", "limestone", base, meta={"block_len": 0.5, "course_h": 0.3, "moss": 0.4})
    wall = pk.lathe(np.array([[R_OUT - 0.14, 0.085], [R_OUT, 0.085], [R_OUT + 0.01, 0.33], [R_OUT, WALL_TOP]]), seg,
                    a0=DOOR_A1, a1=DOOR_A0 + 2 * math.pi, smooth=[True, True, True])
    B.add("root", "drum_wall", "limestone", wall, meta={"block_len": 0.36, "course_h": 0.165, "moss": 0.55})
    inner = pk.lathe(np.array([[R_OUT - 0.14, WALL_TOP], [R_OUT - 0.14, 0.085]]), seg, a0=DOOR_A1, a1=DOOR_A0 + 2 * math.pi)
    B.add("root", "drum_inner", "limestone", inner, meta={"block_len": 0.36, "course_h": 0.165})
    for a in (DOOR_A0, DOOR_A1):    # door jambs
        c, s_ = math.cos(a), math.sin(a)
        jb = pk.beam((c * (R_OUT - 0.07), s_ * (R_OUT - 0.07), 0.085), (c * (R_OUT - 0.07), s_ * (R_OUT - 0.07), WALL_TOP),
                     0.14, 0.05)
        B.add("root", "drum_jambs", "limestone", jb, meta={"block_len": 0.36, "course_h": 0.165})
    # cavity behind the door + chest
    cav = pk.beam((0.0, -0.36, 0.08), (0.0, -0.36, 0.09), 0.55, 0.60)
    B.add("root", "cavity", "limestone", cav, meta={"flag_size": 0.3})
    lint = pk.beam((-0.33, -R_OUT + 0.03, 0.52), (0.33, -R_OUT + 0.03, 0.52), 0.12, 0.08)
    B.add("root", "door_lintel", "limestone", lint, meta={"block_len": 0.35, "course_h": 0.2})
    ch = pk.beam((-0.2, -0.42, 0.205), (0.2, -0.42, 0.205), 0.26, 0.24, chamfer=0.01)
    B.add("root", "chest", "plank", ch)
    lid = pk.sweep(np.array([[-0.2, -0.42, 0.325], [0.2, -0.42, 0.325]]), np.array(
        [[0.13 * math.cos(a), 0.07 * math.sin(a)] for a in np.linspace(0, math.pi, B.seg(8, 5, 3))] + [[-0.13, 0.0]]),
        up=(0, 1, 0), smooth=False)
    B.add("root", "chest", "plank", lid)
    for x in (-0.15, 0.0, 0.15):
        bd = pk.beam((x, -0.42, 0.083), (x, -0.42, 0.40), 0.03, 0.27)
        B.add("root", "chest_bands", "bronze", bd, max_lod=1)
    # rim ring (stone) + clamps
    rim = pk.lathe(np.array([[0.565, 0.58], [R_OUT + 0.035, 0.58], [R_OUT + 0.035, 0.635], [0.565, 0.665]]), seg, smooth=False)
    B.add("root", "rim", "limestone", rim, meta={"block_len": 0.4, "course_h": 0.2, "moss": 0.5})
    for k in range(8):
        a = math.radians(22.5 + 45 * k)
        c, s_ = math.cos(a), math.sin(a)
        cl = pk.beam((c * 0.60, s_ * 0.60, 0.648), (c * (R_OUT + 0.04), s_ * (R_OUT + 0.04), 0.648), 0.07, 0.025, chamfer=0.005)
        B.add("root", "clamps", "bronze", cl)
        dn = pk.beam((c * (R_OUT + 0.04), s_ * (R_OUT + 0.04), 0.66), (c * (R_OUT + 0.04), s_ * (R_OUT + 0.04), 0.56), 0.07, 0.025,
                     chamfer=0.005)
        B.add("root", "clamps", "bronze", dn)
    # front index mark (bronze pointer at the front of the rim)
    mark = pk.extrude(np.array([[-0.03, 0], [0.03, 0], [0.0, 0.07]]), 0.02, chamfer=0.004)
    B.add("root", "index_mark", "bronze", mark.transformed(M4(Rx(math.pi / 2), (0, -0.57, 0.67))))
    # niche (arched bronze frame on the +X side)
    nf = np.array([[0.075, -0.12]] + [[0.075 * math.cos(a), 0.06 + 0.075 * math.sin(a)] for a in np.linspace(0, math.pi, B.seg(9, 6, 4))]
                  + [[-0.075, -0.12]])
    hole = pk.offset_poly(pk.ccw(nf), -0.022)
    frame = pk.extrude(nf, 0.05, chamfer=0.006, hole=hole)
    Mn = M4(Rz(math.pi / 2) @ Rx(math.pi / 2), (R_OUT - 0.01, -0.10, 0.36))
    B.add("root", "niche_frame", "bronze", frame.transformed(Mn))
    back = pk.extrude(hole * 1.05, 0.01).transformed(M4(None, (0, 0, -0.02)))
    B.add("root", "niche_back", "iron", back.transformed(Mn))
    # key stand (stone block in front-left)
    ks = pk.beam(KEY_STAND + np.array([-0.2, 0, 0.09]), KEY_STAND + np.array([0.2, 0, 0.09]), 0.2, 0.18, chamfer=0.02)
    B.add("root", "key_stand", "limestone", ks, meta={"block_len": 0.4, "course_h": 0.2, "moss": 0.4})
    # ---------------- door panel (slides down)
    dp = pk.lathe(np.array([[R_OUT - 0.10, 0.09], [R_OUT + 0.005, 0.09], [R_OUT + 0.012, 0.30], [R_OUT + 0.005, 0.505],
                            [R_OUT - 0.10, 0.505]]), B.seg(8, 5, 3), a0=DOOR_A0 + 0.01, a1=DOOR_A1 - 0.01, smooth=False)
    B.add("door", "door_panel", "limestone", dp, meta={"block_len": 0.3, "course_h": 0.21, "moss": 0.3})
    # ---------------- rings: stacked bronze discs (each rotates about its own vertical axis)
    for name, (R, cy, zb, zt) in RINGS.items():
        disc = pk.extrude_round(pk.circle(R, B.seg(48, 32, 20)), zt - zb, r_front=0.012, r_back=0.004, seg=1,
                                cap_spacing=(0.09 if lod == 0 else None))
        B.add(name, f"{name}_disc", "bronze", disc.transformed(M4(None, (0, cy, zb))), meta={"motif": glyph_motif(name, R)})
    # ---------------- lever key (rests on the stand; green crystal in a bronze claw)
    k0 = KEY_STAND + np.array([0.0, 0.0, 0.18 + 0.022])
    rod = pk.rod(k0 + np.array([-0.21, 0, 0]), k0 + np.array([0.14, 0, 0]), 0.018, B.seg(8, 6, 4))
    B.add("key_lever", "key_rod", "bronze", rod)
    for x in (-0.12, 0.05):
        col = pk.lathe(np.array([[0.018, -0.012], [0.026, -0.006], [0.026, 0.006], [0.018, 0.012]]), B.seg(8, 6, 4))
        B.add("key_lever", "key_rod", "bronze", col.transformed(M4(Ry(math.pi / 2), k0 + np.array([x, 0, 0]))))
    claw = pk.lathe(np.array([[0.02, 0.0], [0.05, 0.03], [0.055, 0.06], [0.03, 0.075]]), B.seg(8, 6, 4), smooth=False)
    B.add("key_lever", "key_claw", "bronze", claw.transformed(M4(Ry(math.pi / 2), k0 + np.array([0.13, 0, 0]))))
    gem = pk.lathe(np.array([[0.0, 0.0], [0.045, 0.03], [0.05, 0.065], [0.0, 0.11]]), B.seg(8, 6, 4), smooth=False)
    B.add("key_lever", "key_gem", "gem_green", gem.transformed(M4(Ry(math.pi / 2), k0 + np.array([0.15, 0, 0]))))
    bit = pk.beam(k0 + np.array([-0.23, 0, 0]), k0 + np.array([-0.18, 0, 0]), 0.012, 0.05)
    B.add("key_lever", "key_rod", "bronze", bit.transformed(M4(None, (0, 0, -0.02))))
    return B


SPEC = {"root": {},
        "ring_1": {"pivot": (0, RINGS["ring_1"][1], RINGS["ring_1"][2]), "export_name": "ring_1"},
        "ring_2": {"pivot": (0, RINGS["ring_2"][1], RINGS["ring_2"][2]), "export_name": "ring_2"},
        "ring_3": {"pivot": (0, RINGS["ring_3"][1], RINGS["ring_3"][2]), "export_name": "ring_3"},
        "door": {"pivot": (0, -R_OUT, 0.09), "export_name": "door_pivot"},
        "key_lever": {"pivot": tuple(KEY_STAND + np.array([0.0, 0.0, 0.202])), "export_name": "key_lever"}}
SOLVED_POSE_02 = {"ring_1": {"rot": (0, 0, ring_angle("mountain"))}, "ring_2": {"rot": (0, 0, ring_angle("river"))},
                  "ring_3": {"rot": (0, 0, ring_angle("leaf"))}}


def key_inserted(f=1.0):
    """Lever key transform: from the stand into the +X niche (pointing inward), then turned 90 deg."""
    k0 = KEY_STAND + np.array([0.0, 0.0, 0.202])
    tgt = NICHE + np.array([0.20, 0, 0.04])
    return tgt - k0


def open_pose():
    p = dict(SOLVED_POSE_02)
    p["door"] = {"loc": (0, 0, -DOOR_DROP)}
    p["key_lever"] = {"loc": tuple(key_inserted()), "rot": (math.pi / 2, 0, 0)}
    return p


def clips(A):
    ease = mk.ease
    for r in (1, 2, 3):
        for g in GLYPHS[1:]:
            tgt = ring_angle(g)
            pk.add_clip(A, f"lf_rune_ring{r}_{g}", {
                f"ring_{r}": (lambda f, t=tgt: {"rot": (0, 0, t * float(pk.ease_out_back(np.clip(f / 16, 0, 1), 1.2)))})},
                18, markers={"click": 0.5})
    kv = key_inserted()

    def key_track(f):
        a = ease(f, 0, 16)
        b = ease(f, 16, 26)
        lift = math.sin(math.pi * a) * 0.35
        loc = kv * a + np.array([0, 0, lift])
        return {"loc": tuple(loc), "rot": (math.pi / 2 * b, 0, 0)}
    pk.add_clip(A, "lf_lock_mechanism", {
        "key_lever": key_track,
        "door": lambda f: {"loc": (0, 0, -DOOR_DROP * ease(f, 28, 50) + 0.01 * math.sin(math.pi * ease(f, 26, 30)))},
        "ring_1": lambda f: {"rot": (0, 0, ring_angle("mountain") + math.radians(1.5) * math.sin(math.pi * ease(f, 24, 30)))},
        "ring_2": lambda f: {"rot": (0, 0, ring_angle("river") + math.radians(1.5) * math.sin(math.pi * ease(f, 24, 30)))},
        "ring_3": lambda f: {"rot": (0, 0, ring_angle("leaf") + math.radians(1.5) * math.sin(math.pi * ease(f, 24, 30)))},
    }, 54, markers={"key_turned": 26 / 30, "door_open": 50 / 30})


def meta(A):
    return {
        "symbol_targets": {
            "axis": "each ring disc rotates about glTF +Y through its own node origin (disc centre); discs are stacked rising toward the back",
            "ring_for_progress_step": {"1": "ring_1", "2": "ring_2", "3": "ring_3"},
            "rotation_y_deg": {g: round(math.degrees(ring_angle(g)), 2) for g in GLYPHS},
            "rest_deg": 0.0, "positions_deg_apart": STEP,
            "sites": {s: {f"step{i + 1}": {"symbol": sym, "node": f"ring_{i + 1}",
                                           "rotation_y_deg": round(math.degrees(ring_angle(sym)), 2),
                                           "clip": f"lf_rune_ring{i + 1}_{sym}"} for i, sym in enumerate(v)}
                      for s, v in SITES.items()},
            "wrong_input": "tween the active ring to the chosen symbol (clip lf_rune_ring<k>_<symbol>), then tween all rings "
                           "back to rest_deg (server resets progress)",
            "solved": {"clip": "lf_lock_mechanism", "door_pivot_open_offset_m": [0, -DOOR_DROP, 0],
                       "key_lever_open": "end pose of lf_lock_mechanism"},
        },
        "sockets": {"artifact_spot": pk.b2g((0.0, -0.42, 0.34)), "front_index_mark": pk.b2g((0, -0.57, 0.70)),
                    "glyph_front_positions": {n: pk.b2g((0.0, RINGS[n][1] - GLYPH_R[n], RINGS[n][3])) for n in RINGS}},
    }


def main():
    views = [
        {"name": "closed", "holdout_ground": True, "box": (782, 52, 1104, 378), "x0": [-0.55, 0.62, 0, 6.0, 2.4, 0, 0], "pose": SOLVED_POSE_02},
        {"name": "open", "holdout_ground": True, "box": (1168, 52, 1500, 372), "x0": [-0.55, 0.62, 0, 6.0, 2.4, 0, 0], "pose": open_pose()},
    ]
    mk.run(ASSET, SPEC, build, views, clips, meta,
           markers=[("artifact_spot", (0.0, -0.42, 0.34), "root")],
           notes=("Rings share 10 engraved positions (blank + 9 symbols of sites 02/06/10). Drawing shows site 02 "
                  "(mountain/river/leaf); comparisons use that solved pose. Door panel slides down into the plinth."),
           main_view="closed")


if __name__ == "__main__":
    main()
