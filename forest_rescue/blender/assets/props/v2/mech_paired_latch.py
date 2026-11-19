"""lf_mechanism_paired_latch from art/10_artifact_mechanisms.png (lower right): paved stone platform, two raised
stone plate pedestals with bronze-framed pressure plates riding on coil springs in pits (guide posts), wooden
levers with bronze pin joints linking each plate to the central stone pedestal, bronze arched latch housing with
the tree emblem and a vertical latch tongue in a square collar. States: unpressed / held (both plates down,
tongue lifted). Plate spacing 5.2 m matches the site layout (plate_left/right = cage +- 2.6 m).
"""
import math

import numpy as np

import cagegeo as CG
import pv2

ID = "lf_mechanism_paired_latch"
ATLAS = 2048
SHEET = "10_artifact_mechanisms.png"
LIGHT = (-0.5, -0.6, 0.62)
BOX = (748, 528, 1312, 728)

PARAMS = dict(px=2.6, ph=0.82, hs=0.86, hd=0.86, cw=0.68, cd=0.52, chh=0.62, top=2.55, hw=0.56)
FREE = ["ph", "hs", "hd", "cw", "cd", "chh", "top", "hw"]
PRESS = 0.14          # plate travel (m)
LIFT = 0.34           # latch tongue lift (m)


def points(p):
    px, ph, hs, hd = p["px"], p["ph"], p["hs"], p["hd"]
    P = {}
    for side, sx in (("l", -1), ("r", 1)):
        cx = sx * px
        P[f"{side}_tl"] = (cx - hs, hd, ph)
        P[f"{side}_tr"] = (cx + hs, hd, ph)
        P[f"{side}_bl"] = (cx - hs, -hd, ph)
        P[f"{side}_br"] = (cx + hs, -hd, ph)
    P["c_apex"] = (0.0, 0.0, p["top"])
    P["c_bl"] = (-p["cw"], -p["cd"], 0.0)
    P["c_br"] = (p["cw"], -p["cd"], 0.0)
    P["h_l"] = (-p["hw"], -0.10, p["top"] - p["hw"])
    P["h_r"] = (p["hw"], -0.10, p["top"] - p["hw"])
    return P


def views():
    v = pv2.ViewSpec(
        "unpressed", SHEET, BOX,
        {"l_tl": (810, 562.5), "l_tr": (927.5, 565), "l_bl": (802.5, 630), "l_br": (925, 630),
         "r_tl": (1192.5, 562.5), "r_tr": (1297.5, 562.5), "r_bl": (1197.5, 627.5), "r_br": (1300, 627.5),
         "c_apex": (1062.5, 522.5), "c_bl": (1015, 710), "c_br": (1107.5, 710),
         "h_l": (1024, 560), "h_r": (1101, 560)},
        light=LIGHT, thresh=0.09, fill_holes=True, shadow=None, title="PAIRED LATCH unpressed (main view)")
    return [v]


def build(A, p, lod):
    px, ph, hs, hd = p["px"], p["ph"], p["hs"], p["hd"]
    g = A.g("root", lod)
    rng = np.random.default_rng(2 + lod)
    # ---------------- paved stone platform (slabs) around everything
    W, D = px + hs + 1.05, hd + 0.95
    nx, ny = (12, 4) if lod == 0 else ((6, 2) if lod == 1 else (3, 1))
    xs = np.linspace(-W, W, nx + 1)
    ys = np.linspace(-D, D, ny + 1)
    for i in range(nx):
        for j in range(ny):
            cx_ = (xs[i] + xs[i + 1]) / 2
            cy_ = (ys[j] + ys[j + 1]) / 2
            if any(abs(cx_ - sx * px) < hs + 0.05 and abs(cy_) < hd + 0.05 for sx in (-1, 1)):
                continue
            h = 0.12 + (rng.uniform(-0.02, 0.02) if lod == 0 else 0)
            g.box((cx_, cy_, h / 2), (xs[i + 1] - xs[i], ys[j + 1] - ys[j], h), mat="stone",
                  tag="paving", skip=("-z",))
    # ---------------- plate pits, pedestal frames (stone), springs, guide posts
    for sx in (-1, 1):
        cx = sx * px
        side = "left" if sx < 0 else "right"
        # pit floor + low stone walls of the pit (back / sides), open at the front where the spring shows
        g.box((cx, 0, 0.02), (2 * hs, 2 * hd, 0.04), mat="stone", tag="pit_floor", skip=("-z",))
        for (dx, dy, sxz, syz) in ((0, hd - 0.12, 2 * hs, 0.24), (-hs + 0.12, 0, 0.24, 2 * hd - 0.24), (hs - 0.12, 0, 0.24, 2 * hd - 0.24)):
            g.box((cx + dx, dy, (ph - PRESS - 0.18) / 2), (sxz, syz, ph - PRESS - 0.18), mat="stone", tag="pit_wall", skip=("-z",))
        # moving plate: stone slab with bronze frame, carried by the spring
        pl = A.part(f"plate_{side}", None, (cx, 0.0, ph))
        pg = pl.geo[lod]
        pg.box((cx, 0, ph - 0.11), (2 * hs, 2 * hd, 0.22), mat="stone", tag="plate_slab")
        fr = 0.06
        for (dx, dy, lx, ly) in ((0, -hd + 0.12, 2 * hs - 0.24, fr), (0, hd - 0.12, 2 * hs - 0.24, fr),
                                 (-hs + 0.12, 0, fr, 2 * hd - 0.24), (hs - 0.12, 0, fr, 2 * hd - 0.24)):
            pg.box((cx + dx, dy, ph + 0.012), (lx + fr, ly + fr, 0.024), mat="bronze", tag="plate_frame")
        if lod == 0:
            for (dx, dy) in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                pg.cyl((cx + dx * (hs - 0.12), dy * (hd - 0.12), ph + 0.02), (cx + dx * (hs - 0.12), dy * (hd - 0.12), ph + 0.045),
                       0.03, n=6, mat="bronze", tag="plate_rivet")
        # spring (helix tube) in its own node so it can compress (scale Z)
        sp = A.part(f"spring_{side}", None, (cx, -hd + 0.45, 0.04))
        n_turn = 6
        m = 6 * n_turn * (2 if lod == 0 else 1) + 1
        r_c = 0.22
        z0s, z1s = 0.04, ph - 0.22
        H = [(cx + r_c * math.cos(2 * math.pi * n_turn * t), -hd + 0.45 + r_c * math.sin(2 * math.pi * n_turn * t),
              z0s + (z1s - z0s) * t) for t in np.linspace(0, 1, m)]
        sp.geo[lod].tube(np.array(H), 0.035, n=6 if lod == 0 else 4, mat="iron", tag="spring")
        # wooden guide posts either side of the spring (static)
        for gx in (-0.42, 0.42):
            g.box((cx + gx, -hd + 0.45, (ph - 0.25) / 2 + 0.02), (0.14, 0.14, ph - 0.25), mat="wood", tag="guide")
    # ---------------- central stone pedestal + bronze latch housing (static) + tongue (moves)
    cw, cd, chh = p["cw"], p["cd"], p["chh"]
    g.box((0, 0, chh / 2), (2 * cw, 2 * cd, chh), mat="stone", tag="pedestal")
    g.box((0, 0, 0.06), (2 * cw + 0.2, 2 * cd + 0.2, 0.12), mat="stone", tag="pedestal_base", skip=("-z",))
    top, hw = p["top"], p["hw"]
    zs = top - hw
    # housing: two bronze uprights + semicircular arch + emblem plate between
    for sx in (-1, 1):
        g.box((sx * (hw - 0.07), -0.05, (chh + zs) / 2), (0.14, 0.26, zs - chh), mat="bronze", tag="housing_post")
    nr = 12 if lod == 0 else 7
    arc = np.array([(hw * 0.93 * math.cos(a), -0.05, zs + hw * 0.93 * math.sin(a)) for a in np.linspace(0, math.pi, nr)])
    CG.sweep_rect(g, arc, 0.26, 0.14, up=(0, -1, 0), mat="bronze", tag="housing_arch")
    half = np.array([(hw * 0.86 * math.cos(a), hw * 0.86 * math.sin(a)) for a in np.linspace(0, math.pi, nr)])
    g.prism(half, 0.0, 0.05, "bronze", "housing_emblem", R=np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float),
            t=(0, 0.06, zs))
    g.box((0, -0.05, zs - 0.05), (2 * hw, 0.26, 0.1), mat="bronze", tag="housing_sill")
    # square collar on the pedestal front
    g.box((0, -cd - 0.06, chh + 0.22), (0.5, 0.14, 0.16), mat="bronze", tag="collar")
    g.box((0, -cd - 0.06, chh / 2), (0.24, 0.12, chh), mat="bronze", tag="post")
    tg = A.part("latch_tongue", None, (0, -cd - 0.06, chh + 0.3))
    tg.geo[lod].box((0, -cd - 0.06, chh + 0.85), (0.2, 0.1, 1.1), mat="bronze", tag="tongue")
    tg.geo[lod].box((0, -cd - 0.06, chh + 1.35), (0.34, 0.14, 0.12), mat="bronze", tag="tongue_head")
    # ---------------- levers (wood, bronze pins) - one node each, pivot at the pedestal pin
    for sx in (-1, 1):
        side = "left" if sx < 0 else "right"
        a = np.array([sx * (cw + 0.02), -cd - 0.12, chh * 0.62])          # pin on the pedestal
        b = np.array([sx * (px - 0.55), -hd + 0.05, 0.28])                 # pin at the plate pit
        lv = A.part(f"lever_{side}", None, a)
        lg = lv.geo[lod]
        lg.beam(a, b, 0.12, 0.2, up=(0, -1, 0), mat="wood", tag="lever")
        for q in (a, b):
            lg.cyl(q + (0, -0.08, 0), q + (0, 0.08, 0), 0.07, n=8 if lod == 0 else 5, mat="bronze", tag="pin")
    # markers: plate centres (where squad members stand), artifact spot (tongue head)
    if lod == 0:
        A.marker("plate_left_top", (-px, 0, ph))
        A.marker("plate_right_top", (px, 0, ph))
        A.marker("artifact_spot", (0, -cd - 0.06, chh + 1.5), parent="latch_tongue")
    return A


SWATCHES = {
    "stone": dict(sheet=SHEET, box=(940, 570, 990, 600), metres=0.7),
    "bronze": dict(sheet=SHEET, box=(1050, 625, 1062, 680), metres=0.15),
    "wood": dict(sheet=SHEET, box=(930, 655, 980, 670), metres=0.4),
    "iron": dict(sheet=SHEET, box=(840, 655, 870, 685), metres=0.3),
}


def clips(A, B):
    def plate(t, t0, dur):
        return {"loc": (0, 0, -PRESS * pv2.ease_io((t - t0) / dur))}

    def spring(t, t0, dur):
        return {"scale": (1, 1, 1 - 0.32 * pv2.ease_io((t - t0) / dur))}

    def lever(sx, t, t0, dur):
        # lever end at the plate drops by PRESS -> rotation about the pedestal pin (Y axis), sign by side
        ang = math.atan2(PRESS, 2.0) * pv2.ease_io((t - t0) / dur)
        return {"rot": (0, sx * ang, 0)}

    pv2.add_clip(A, B, "lf_latch_plate_left", 0.8,
                 {"plate_left": lambda t: plate(t, 0, 0.8), "spring_left": lambda t: spring(t, 0, 0.8),
                  "lever_left": lambda t: lever(-1, t, 0, 0.8)}, note="left plate pressed (squad member steps on)")
    pv2.add_clip(A, B, "lf_latch_plate_right", 0.8,
                 {"plate_right": lambda t: plate(t, 0, 0.8), "spring_right": lambda t: spring(t, 0, 0.8),
                  "lever_right": lambda t: lever(1, t, 0, 0.8)}, note="right plate pressed")
    held = {"plate_left": lambda t: plate(t, 0, 0.6), "spring_left": lambda t: spring(t, 0, 0.6),
            "lever_left": lambda t: lever(-1, t, 0, 0.6),
            "plate_right": lambda t: plate(t, 0, 0.6), "spring_right": lambda t: spring(t, 0, 0.6),
            "lever_right": lambda t: lever(1, t, 0, 0.6),
            "latch_tongue": lambda t: {"loc": (0, 0, LIFT * pv2.ease_io((t - 0.7) / 1.0))}}
    pv2.add_clip(A, B, "lf_lock_mechanism", 1.8, held, markers={"plates_down": 0.6, "latch_open": 1.7},
                 note="both plates pressed and held, linkage pulls, the central latch tongue lifts (solved pose = last frame)")
    pv2.add_clip(A, B, "lf_latch_reset", 1.0,
                 {"plate_left": lambda t: plate(1.0 - t, 0, 1.0), "plate_right": lambda t: plate(1.0 - t, 0, 1.0),
                  "spring_left": lambda t: spring(1.0 - t, 0, 1.0), "spring_right": lambda t: spring(1.0 - t, 0, 1.0),
                  "lever_left": lambda t: lever(-1, 1.0 - t, 0, 1.0), "lever_right": lambda t: lever(1, 1.0 - t, 0, 1.0)},
                 note="wrong input / plates released: springs push both plates back up")


def meta(A, p):
    g = pv2.b2g
    return {
        "mechanism": "paired_latch",
        "sockets": {"plate_left": g((-p["px"], 0, p["ph"])), "plate_right": g((p["px"], 0, p["ph"])),
                    "artifact": g((0, -p["cd"] - 0.06, p["chh"] + 1.5 + LIFT))},
        "steps": {"left_plate": "lf_latch_plate_left", "right_plate": "lf_latch_plate_right",
                  "center_latch": "lf_lock_mechanism"},
        "solved_clip": "lf_lock_mechanism (hold last frame)", "reset_clip": "lf_latch_reset",
        "plate_spacing_m": round(2 * p["px"], 3),
        "nodes_note": "plate_left/right translate -Y(glTF) by 0.14 m, spring_left/right scale Y (compress), "
                      "lever_left/right rotate about their pedestal pins, latch_tongue lifts 0.34 m",
    }
