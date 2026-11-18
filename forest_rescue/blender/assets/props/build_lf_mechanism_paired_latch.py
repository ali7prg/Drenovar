"""lf_mechanism_paired_latch: two spring-loaded stone pressure plates linked by oak levers to a central bronze
latch (T-bar) on a stone post; releasing the latch exposes the artifact niche.

Steps: left_plate (lf_latch_left_plate), right_plate (lf_latch_right_plate), center_latch (lf_lock_mechanism:
latch bar drops, levers swing level, niche revealed). Run: python3 forest_rescue/blender/run_limited.py ... --iter N
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

ASSET = "lf_mechanism_paired_latch"
PX = 1.62                 # plate centre |x|
PS = 1.0                  # plate size
BASE_H = 0.30
PLATE_T = 0.08
PRESS = 0.09
BAR_DROP = 0.24
LY = -0.36                # lever plane y (front of the bases)
PIN_IN = 0.34             # inner pin |x| (on the latch yoke)
PIN_Z = 0.55              # inner pin height (latch up)
END_X = PX - PS / 2 + 0.12  # outer lever end |x| (under the plate inner edge)
END_Z = BASE_H - 0.08     # outer end height (plate up)


def lever_angle(z_in, z_out):
    """Angle (rad) of the lever from horizontal (positive = outer end lower)."""
    return math.atan2(z_in - z_out, END_X - PIN_IN)


REST = lever_angle(PIN_Z, END_Z)


def spring(c, h, r=0.07, turns=4.5, wire=0.012, nseg=None, sides=4):
    n = nseg or int(turns * 8)
    t = np.linspace(0, 1, n)
    path = np.stack([c[0] + r * np.cos(t * turns * 2 * math.pi), c[1] + r * np.sin(t * turns * 2 * math.pi), c[2] + t * h], 1)
    return pk.tube(path, wire, sides)


def build(lod):
    B = pk.Builder(lod)
    # ---------------- pavement (flagstones) under everything
    pv = pk.beam((-2.35, 0.05, 0.03), (2.35, 0.05, 0.03), 1.75, 0.06, chamfer=0.01)
    B.add("root", "pavement", "limestone", pv, meta={"flag_size": 0.42, "moss": 0.55})
    for sx in (-1, 1):
        x = sx * PX
        # plate base: stone box with a front opening showing the springs
        for nm, (a, b, w, h) in {"back": ((x - 0.5, 0.42, BASE_H / 2), (x + 0.5, 0.42, BASE_H / 2), 0.16, BASE_H),
                                 "out": ((x + sx * 0.46, -0.36, BASE_H / 2), (x + sx * 0.46, 0.36, BASE_H / 2), 0.16, BASE_H),
                                 "in": ((x - sx * 0.46, -0.36, BASE_H / 2), (x - sx * 0.46, 0.36, BASE_H / 2), 0.16, BASE_H),
                                 "frontsill": ((x - 0.5, -0.43, 0.05), (x + 0.5, -0.43, 0.05), 0.14, 0.1)}.items():
            B.add("root", f"base_{nm}", "limestone", pk.beam(a, b, w, h, chamfer=0.02), meta={"block_len": 0.35, "course_h": 0.15, "moss": 0.45})
        # plate node (slab + bronze trim)
        node = "plate_l" if sx < 0 else "plate_r"
        slab = pk.beam((x - PS / 2, 0.0, BASE_H + PLATE_T / 2), (x + PS / 2, 0.0, BASE_H + PLATE_T / 2), PS, PLATE_T, chamfer=0.012)
        B.add(node, f"{node}_slab", "limestone", slab, meta={"block_len": 0.0, "flag_size": 0.0, "moss": 0.0})
        for (a, b) in (((x - PS / 2, -PS / 2), (x + PS / 2, -PS / 2)), ((x - PS / 2, PS / 2), (x + PS / 2, PS / 2)),
                       ((x - PS / 2, -PS / 2), (x - PS / 2, PS / 2)), ((x + PS / 2, -PS / 2), (x + PS / 2, PS / 2))):
            tr = pk.beam((a[0], a[1], BASE_H + PLATE_T + 0.004), (b[0], b[1], BASE_H + PLATE_T + 0.004), 0.05, 0.016, chamfer=0.004)
            B.add(node, f"{node}_trim", "bronze", tr, meta={"rivets": {"du": 0.24, "v": [pk.rect_face_v(0.05, 0.016, 0.004, "+B")], "r": 0.012}})
        # springs (two per plate at the front opening) -> separate nodes (scale Z)
        for k, yy in enumerate((-0.25,)):
            for kx, xx in enumerate((x - 0.28, x + 0.28)):
                sn = f"spring_{'l' if sx < 0 else 'r'}{kx}"
                B.add(sn, f"{sn}_coil", "iron", spring((xx, yy, 0.02), BASE_H - 0.02, sides=B.seg(4, 4, 3),
                                                       nseg=B.seg(36, 20, 10)))
    # ---------------- central post: stone base + upper block with slot + bronze arch frame
    B.add("root", "post_base", "limestone", pk.beam((0, 0.0, 0.0), (0, 0.0, 0.42), 0.78, 0.62, chamfer=0.03),
          meta={"block_len": 0.4, "course_h": 0.21, "moss": 0.5})
    for sx in (-1, 1):
        B.add("root", "post_cheeks", "limestone", pk.beam((sx * 0.25, 0.0, 0.42), (sx * 0.25, 0.0, 0.95), 0.22, 0.5, chamfer=0.02),
              meta={"block_len": 0.4, "course_h": 0.18})
    arch = np.array([[0.30, 0.0]] + [[0.30 * math.cos(a), 0.62 + 0.30 * math.sin(a)] for a in np.linspace(0, math.pi, B.seg(14, 9, 5))]
                    + [[-0.30, 0.0]])
    hole = pk.offset_poly(pk.ccw(arch), -0.06)
    fr = pk.extrude(arch, 0.06, chamfer=0.01, hole=hole)
    B.add("root", "arch_frame", "bronze", fr.transformed(M4(Rx(math.pi / 2), (0, -0.26, 0.42))))
    cv = mo.Canvas((-0.3, 0.6, 0.3, 0.95), ppm=1500)
    mo.tree_emblem(cv, (0.0, 0.79), 0.2, 0.012)
    panel = pk.extrude(np.array([[0.24 * math.cos(a), 0.62 + 0.24 * math.sin(a)] for a in np.linspace(0, math.pi, B.seg(12, 8, 5))]),
                       0.03, chamfer=0.006)
    B.add("root", "arch_panel", "bronze", panel.transformed(M4(Rx(math.pi / 2), (0, -0.22, 0.42))),
          meta={"motif": [{"mask": cv.mask(0.002), "bbox": (-0.3, 0.6, 0.3, 0.95), "isl": (2,), "depth": 0.004, "mode": "raise"}]})
    # niche (behind the latch crossbar) with the artifact pedestal
    B.add("root", "niche", "iron", pk.beam((0, 0.05, 0.62), (0, 0.05, 0.64), 0.26, 0.3))
    B.add("root", "pedestal", "limestone", pk.beam((0, -0.05, 0.62), (0, -0.05, 0.72), 0.16, 0.16, chamfer=0.01))
    # ---------------- latch node: T-bar + crossbar + yoke with lever pins
    bar = pk.beam((0, -0.25, 0.30), (0, -0.25, 1.02), 0.09, 0.07, chamfer=0.01)
    B.add("latch", "latch_bar", "bronze", bar)
    cross = pk.beam((-0.2, -0.27, 0.92), (0.2, -0.27, 0.92), 0.1, 0.12, chamfer=0.012)
    B.add("latch", "latch_cross", "bronze", cross)
    yoke = pk.beam((-PIN_IN - 0.04, LY + 0.02, PIN_Z), (PIN_IN + 0.04, LY + 0.02, PIN_Z), 0.05, 0.1, chamfer=0.01)
    B.add("latch", "latch_yoke", "bronze", yoke)
    for sx in (-1, 1):
        pin = pk.rod((sx * PIN_IN, LY - 0.06, PIN_Z), (sx * PIN_IN, LY + 0.06, PIN_Z), 0.03, B.seg(8, 6, 4))
        B.add("latch", "latch_pins", "bronze", pin)
    # ---------------- levers (children of the latch; pivot at the inner pin)
    for sx in (-1, 1):
        node = "lever_l" if sx < 0 else "lever_r"
        p0 = np.array([sx * PIN_IN, LY, PIN_Z])
        p1 = np.array([sx * END_X, LY, END_Z])
        lv = pk.beam(p0, p1 + (p1 - p0) * 0.04, 0.07, 0.11, chamfer=0.015)
        B.add(node, f"{node}_beam", "oak", lv)
        endc = pk.rod(p1 + np.array([0, -0.06, 0]), p1 + np.array([0, 0.06, 0]), 0.04, B.seg(8, 6, 4))
        B.add(node, f"{node}_end", "bronze", endc)
    return B


def spec():
    s = {"root": {},
         "plate_l": {"pivot": (-PX, 0.0, BASE_H), "export_name": "plate_left"},
         "plate_r": {"pivot": (PX, 0.0, BASE_H), "export_name": "plate_right"},
         "latch": {"pivot": (0.0, LY, PIN_Z), "export_name": "latch_bar"},
         "lever_l": {"pivot": (-PIN_IN, LY, PIN_Z), "parent": "latch", "export_name": "lever_left"},
         "lever_r": {"pivot": (PIN_IN, LY, PIN_Z), "parent": "latch", "export_name": "lever_right"}}
    for side, x in (("l", -PX), ("r", PX)):
        for kx, xx in enumerate((x - 0.28, x + 0.28)):
            s[f"spring_{side}{kx}"] = {"pivot": (xx, -0.25, 0.02), "export_name": f"spring_{side}{kx}"}
    return s


def lever_rot(side, z_in, z_out):
    """Rotation about Y (Blender) of a lever relative to its rest pose."""
    d = lever_angle(z_in, z_out) - REST
    return d if side == "r" else -d


def pressed_pose(left=True, right=True, released=False):
    zi = PIN_Z - (BAR_DROP if released else 0.0)
    p = {"latch": {"loc": (0, 0, zi - PIN_Z)}}
    for side, on in (("l", left), ("r", right)):
        zo = END_Z - (PRESS if on else 0.0)
        p["plate_" + side] = {"loc": (0, 0, -PRESS if on else 0.0)}
        p["lever_" + side] = {"rot": (0, lever_rot(side, zi, zo), 0)}
        for k in (0, 1):
            p[f"spring_{side}{k}"] = {"scale": (1, 1, (BASE_H - 0.02 - (PRESS if on else 0.0)) / (BASE_H - 0.02))}
    return p


def clips(A):
    ease = mk.ease

    def plate_clip(side, other_on):
        def mk_track(f):
            t = float(pk.ease_out_back(np.clip(f / 12, 0, 1), 0.8))
            return t
        tr = {
            "plate_" + side: lambda f: {"loc": (0, 0, -PRESS * mk_track(f))},
            "lever_" + side: lambda f: {"rot": (0, lever_rot(side, PIN_Z, END_Z - PRESS * mk_track(f)), 0)},
        }
        for k in (0, 1):
            tr[f"spring_{side}{k}"] = lambda f: {"scale": (1, 1, (BASE_H - 0.02 - PRESS * mk_track(f)) / (BASE_H - 0.02))}
        return tr
    pk.add_clip(A, "lf_latch_left_plate", plate_clip("l", False), 15, markers={"plate_down": 0.4})
    pk.add_clip(A, "lf_latch_right_plate", plate_clip("r", True), 15, markers={"plate_down": 0.4})
    tr = {"latch": lambda f: {"loc": (0, 0, -BAR_DROP * ease(f, 6, 36) + 0.012 * math.sin(math.pi * ease(f, 0, 6)))}}
    for side in ("l", "r"):
        tr["plate_" + side] = lambda f: {"loc": (0, 0, -PRESS)}
        tr["lever_" + side] = (lambda f, sd=side: {"rot": (0, lever_rot(sd, PIN_Z - BAR_DROP * ease(f, 6, 36), END_Z - PRESS), 0)})
        for k in (0, 1):
            tr[f"spring_{side}{k}"] = lambda f: {"scale": (1, 1, (BASE_H - 0.02 - PRESS) / (BASE_H - 0.02))}
    pk.add_clip(A, "lf_lock_mechanism", tr, 54, markers={"latch_released": 6 / 30, "niche_open": 36 / 30})


def meta(A):
    pp = pressed_pose(True, True, True)
    return {"symbol_targets": {
        "left_plate": {"clip": "lf_latch_left_plate", "nodes": {"plate_left": {"translation_offset": [0, -PRESS, 0]},
                                                                 "lever_left": {"rotation_z_deg_glTF": round(-math.degrees(pressed_pose(True, False)["lever_l"]["rot"][1]), 3)},
                                                                 "spring_l0/l1": {"scale_y": round((BASE_H - 0.02 - PRESS) / (BASE_H - 0.02), 4)}}},
        "right_plate": {"clip": "lf_latch_right_plate", "nodes": {"plate_right": {"translation_offset": [0, -PRESS, 0]},
                                                                   "lever_right": {"rotation_z_deg_glTF": round(-math.degrees(pressed_pose(False, True)["lever_r"]["rot"][1]), 3)},
                                                                   "spring_r0/r1": {"scale_y": round((BASE_H - 0.02 - PRESS) / (BASE_H - 0.02), 4)}}},
        "center_latch": {"clip": "lf_lock_mechanism", "nodes": {"latch_bar": {"translation_offset": [0, -BAR_DROP, 0]},
                                                                 "lever_left": {"rotation_z_deg_glTF": round(-math.degrees(pp["lever_l"]["rot"][1]), 3)},
                                                                 "lever_right": {"rotation_z_deg_glTF": round(-math.degrees(pp["lever_r"]["rot"][1]), 3)}}},
        "note": ("Blender rotation about +Y equals glTF rotation about -Z; values above are glTF-space Euler Z "
                 "(sign already converted). Plates may be released after the solve: the latch stays down."),
        "occupy_plates": "server splits the squad over both plates; play both plate clips together",
        "sites": ["lf_site_04", "lf_site_08", "lf_site_12"], "order": ["left_plate", "right_plate", "center_latch"]},
        "sockets": {"plate_left_stand": pk.b2g((-PX, 0, BASE_H + PLATE_T)), "plate_right_stand": pk.b2g((PX, 0, BASE_H + PLATE_T)),
                    "artifact_spot": pk.b2g((0, -0.05, 0.72))}}


def main():
    views = [{"name": "unpressed", "box": (745, 515, 1312, 762), "x0": [-0.05, 0.48, 0, 9.0, 2.6, 0, 0], "pose": {}},
             {"name": "held", "box": (745, 762, 1312, 1012), "x0": [-0.05, 0.48, 0, 9.0, 2.6, 0, 0],
              "pose": pressed_pose(True, True, True), "project": False,
              "exclude": [(50, 0, 230, 140), (440, 0, 560, 140)]}]
    mk.run(ASSET, spec(), build, views, clips, meta, markers=[("artifact_spot", (0, -0.05, 0.72), "root")],
           notes="Soldiers in the 'held' drawing are excluded from its mask (approximate boxes).", main_view="unpressed")


if __name__ == "__main__":
    main()
