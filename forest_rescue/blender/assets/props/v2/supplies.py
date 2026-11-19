"""lf_props_supplies from art/loot_artifact_families.png (RECOVERED SUPPLIES band): nine solid items as separate
nodes (supply_*): closed crate, open crate (hinged lid), folded russet blankets, grain sacks (tied + open with grain
and spill), bronze coin stacks, arrow bundle (shafts, steel heads, fletching, rope tie), two bread loaves, rolled
bandages with a loose strip, open travel chest (curved lid, iron bands, ring handles) with its contents.
Each item is textured from its own painted view (camera fitted to the item's painted silhouette box).
"""
import math

import cv2
import numpy as np

import camsolve
import cagegeo as CG
import pv2

ID = "lf_props_supplies"
ATLAS = 2048
SHEET = "loot_artifact_families.png"
LIGHT = (-0.45, -0.5, 0.74)
PARAMS = {}
FREE = []

# item: (sheet box, layout (x, y) in the pile, yaw of the painted camera deg (+ = camera on the right), elevation deg)
ITEMS = {
    "crate_closed": ((20, 742, 208, 895), (-1.75, 0.55), -24, 20),
    "crate_open": ((214, 700, 388, 895), (-1.0, 0.65), -18, 22),
    "blankets": ((402, 754, 628, 895), (-0.2, 0.7), 8, 20),
    "sacks": ((626, 728, 845, 918), (0.65, 0.7), 0, 16),
    "coins": ((846, 780, 1018, 880), (1.35, 0.35), 0, 32),
    "arrows": ((970, 748, 1172, 982), (1.45, 0.95), 0, 12),
    "bread": ((92, 902, 318, 998), (-1.55, -0.35), 0, 28),
    "bandages": ((394, 912, 630, 1002), (-0.7, -0.35), 0, 24),
    "chest": ((1138, 702, 1510, 993), (0.45, -0.45), 18, 20),
}


def points(p):
    return {}


def views():
    out = []
    for name, (box, xy, yaw, el) in ITEMS.items():
        hide = {f"supply_{o}": "hide" for o in ITEMS if o != name}
        v = pv2.ViewSpec(name, SHEET, box, {}, pose=hide, light=LIGHT, thresh=0.10, fill_holes=True, shadow=0.10,
                         title=f"SUPPLIES {name} (camera fitted to the painted silhouette box)")
        v.yaw, v.el = yaw, el
        out.append(v)
    return out


def plank_box(g, c, size, lod, mat="wood", tag="plank", n=4, axis=0):
    """Box made of n planks stacked along Z (visible plank seams as geometry steps)."""
    c = np.asarray(c, float)
    w, d, h = size
    if lod > 0:
        g.box(c, size, mat=mat, tag=tag, skip=("-z",))
        return
    for k in range(n):
        z = c[2] - h / 2 + h * (k + 0.5) / n
        inset = 0.004 * (k % 2)
        g.box((c[0], c[1], z), (w - inset, d - inset, h / n - 0.004), mat=mat, tag=tag, skip=("-z",) if k == 0 else ())


def crate(g, o, lod, w=0.66, d=0.5, h=0.5, lid=True, lid_open=False, A=None, name=""):
    o = np.asarray(o, float)
    plank_box(g, o + (0, 0, h / 2), (w, d, h), lod, tag="crate_body", n=4)
    if not lid:
        g.box(o + (0, 0, h - 0.06), (w - 0.06, d - 0.06, 0.02), mat="wood", tag="crate_inner")
    # corner battens + rim battens
    b = 0.06
    for sx in (-1, 1):
        for sy in (-1, 1):
            g.box(o + (sx * (w / 2 - b / 2 + 0.008), sy * (d / 2 - b / 2 + 0.008), h / 2), (b, b, h + 0.01), mat="wood",
                  tag="batten")
            if lod == 0:
                g.box(o + (sx * (w / 2 + 0.006), sy * (d / 2 - 0.05), h - 0.05), (0.008, 0.1, 0.1), mat="iron", tag="bracket")
    for zz in (0.03, h - 0.03):
        g.box(o + (0, -d / 2 - 0.006, zz), (w, 0.02, 0.06), mat="wood", tag="rim")
        g.box(o + (-w / 2 - 0.006, 0, zz), (0.02, d, 0.06), mat="wood", tag="rim")
    if lid and lod < 2:
        # diagonal brace on the front (closed crate)
        a = o + (-w / 2 + 0.08, -d / 2 - 0.012, 0.08)
        bpt = o + (w / 2 - 0.08, -d / 2 - 0.012, h - 0.08)
        g.beam(a, bpt, 0.05, 0.02, up=(0, -1, 0), mat="wood", tag="brace")
        a = o + (-w / 2 - 0.012, d / 2 - 0.08, 0.08)
        bpt = o + (-w / 2 - 0.012, -d / 2 + 0.08, h - 0.08)
        g.beam(a, bpt, 0.05, 0.02, up=(-1, 0, 0), mat="wood", tag="brace")
    if lid:
        g.box(o + (0, 0, h + 0.02), (w + 0.02, d + 0.02, 0.04), mat="wood", tag="crate_lid")


def blob(g, c, radii, lod, mat, tag, flat=0.2, seed=0, sub=None, squash_top=0.0):
    V, F = __import__("geo").icosphere(sub if sub is not None else (2 if lod == 0 else 1))
    rng = np.random.default_rng(seed)
    V = V * (1 + 0.04 * np.sin(V @ rng.normal(size=(3, 3)) * 3).sum(1, keepdims=True) / 3)
    V = V * np.asarray(radii, float)
    V[:, 2] = np.maximum(V[:, 2], -radii[2] * (1 - flat))
    if squash_top:
        V[:, 2] = np.where(V[:, 2] > 0, V[:, 2] * (1 - squash_top), V[:, 2])
    V[:, 2] -= V[:, 2].min()
    g.add(V + np.asarray(c, float), F, mat, tag)


def build(A, p, lod):
    for name, (box, (x, y), yaw, el) in ITEMS.items():
        part = A.part(f"supply_{name}", None, (x, y, 0.0))
        g = part.geo[lod]
        o = np.array([x, y, 0.0])
        if name == "crate_closed":
            crate(g, o, lod, lid=True)
        elif name == "crate_open":
            crate(g, o, lod, w=0.62, d=0.48, h=0.44, lid=False)
            # open lid hinged at the back top edge, tilted back 100 deg
            hinge = o + (0, 0.24, 0.44)
            ang = math.radians(100)
            R = np.array([[1, 0, 0], [0, math.cos(ang), -math.sin(ang)], [0, math.sin(ang), math.cos(ang)]])
            g.box(hinge + R @ np.array([0, -0.24, 0.02]), (0.64, 0.5, 0.04), R=R, mat="wood", tag="crate_lid")
        elif name == "blankets":
            for k in range(3):
                c = o + (0.01 * (k - 1), 0.0, 0.06 + 0.115 * k)
                g.box(c, (0.6, 0.4, 0.11), mat="cloth", tag="blanket", chamfer=0.04 if lod == 0 else 0.0)
                g.cyl(c + (-0.3, -0.2, 0), c + (0.3, -0.2, 0), 0.055, n=8 if lod == 0 else 5, mat="cloth", tag="blanket_fold")
        elif name == "sacks":
            # tied sack (back-left) and open sack with grain (front-right) + grain spill
            prof = [(0.0, 0.0), (0.17, 0.02), (0.22, 0.14), (0.21, 0.32), (0.13, 0.46), (0.05, 0.52), (0.06, 0.56),
                    (0.09, 0.62), (0.0, 0.64)]
            CG.lathe(g, prof, o + (-0.15, 0.12, 0), n=12 if lod == 0 else 7, mat="sack", tag="sack_tied")
            g.cyl(o + (-0.15, 0.12, 0.52), o + (-0.15, 0.12, 0.555), 0.065, n=8, mat="rope", tag="sack_tie")
            prof2 = [(0.0, 0.0), (0.2, 0.02), (0.27, 0.14), (0.27, 0.3), (0.22, 0.42), (0.2, 0.46)]
            CG.lathe(g, prof2, o + (0.12, -0.08, 0), n=14 if lod == 0 else 8, mat="sack", tag="sack_open", cap_top=False)
            CG.lathe(g, [(0.19, 0.0), (0.12, 0.04), (0.0, 0.06)], o + (0.12, -0.08, 0.40), n=12 if lod == 0 else 7,
                     mat="grain", tag="grain")
            blob(g, o + (0.05, -0.32, 0), (0.12, 0.06, 0.02), lod, "grain", "grain_spill", flat=0.9, seed=3, sub=1)
        elif name == "coins":
            for (dx, dy, n_, tilt) in ((-0.01, 0.07, 7, 0.0), (-0.1, 0.0, 3, 0.0), (0.1, 0.02, 4, 0.0), (0.03, -0.03, 2, 0.0)):
                for k in range(n_ if lod < 2 else max(1, n_ // 2)):
                    z = 0.009 * k * (1 if lod < 2 else 2) + 0.0045
                    g.cyl(o + (dx + 0.002 * math.sin(k), dy, z - 0.0045), o + (dx + 0.002 * math.sin(k), dy, z + 0.0045),
                          0.04, n=12 if lod == 0 else 7, mat="bronze", tag="coin")
            for (dx, dy) in ((-0.17, -0.06), (0.16, -0.07), (-0.08, -0.1)):
                g.cyl(o + (dx, dy, 0.0), o + (dx, dy, 0.009), 0.04, n=10 if lod == 0 else 6, mat="bronze", tag="coin_loose")
            # one big coin standing upright at the front (painting)
            g.cyl(o + (0.0, -0.12, 0.055), o + (0.0, -0.135, 0.055), 0.055, n=14 if lod == 0 else 7, mat="bronze",
                  tag="coin_front", up=(0, 0, 1))
        elif name == "arrows":
            n_ar = 8 if lod < 2 else 4
            tie = o + (0, 0, 0.36)
            for k in range(n_ar):
                ang = (k - (n_ar - 1) / 2) * 0.06
                d = np.array([-0.62 + ang, -0.08 + 0.03 * (k % 3), -0.78])
                d /= np.linalg.norm(d)
                base = tie - d * 0.40 + (0.012 * (k % 3) - 0.012, 0.014 * (k // 3), 0)
                tip = base + d * 0.78
                g.cyl(base, tip - d * 0.06, 0.006, n=4, mat="wood", tag="shaft", caps=(False, False))
                CG.lathe(g, [(0.014, 0.0), (0.0, 0.07)], tip - d * 0.07, n=4, mat="iron", tag="arrowhead",
                         R=CG.frame(np.cross(d, (1, 0, 0)), d) if abs(d[0]) < 0.9 else None)
                if lod < 2:
                    for f in range(2):
                        side = np.cross(d, (0, 1, 0) if f == 0 else (1, 0, 0))
                        side /= np.linalg.norm(side)
                        c = base + d * 0.06
                        g.add(np.array([c - d * 0.05, c + d * 0.07, c + d * 0.05 + side * 0.022, c - d * 0.05 + side * 0.022]),
                              [[0, 1, 2, 3], [3, 2, 1, 0]], "feather", "fletching")
            ring = [tie + np.array([0.035 * math.cos(a), 0.03 * math.sin(a), 0.0]) for a in np.linspace(0, 2 * math.pi, 9)[:-1]]
            g.tube(np.array(ring + [ring[0]]), 0.012, n=5, mat="rope", tag="arrow_tie")
            # the bundle leans: rotate later via the part (static lean baked here)
        elif name == "bread":
            blob(g, o + (-0.17, 0.0, 0), (0.17, 0.12, 0.10), lod, "bread", "loaf", flat=0.75, seed=1)
            blob(g, o + (0.17, 0.05, 0), (0.15, 0.11, 0.095), lod, "bread", "loaf", flat=0.75, seed=2)
        elif name == "bandages":
            ax = np.array([0.85, 0.55, 0.0]) / np.linalg.norm([0.85, 0.55])
            for (dx, dy, L) in ((-0.16, 0.02, 0.26), (0.1, -0.05, 0.24)):
                cc = o + (dx, dy, 0.075)
                g.cyl(cc - ax * L / 2, cc + ax * L / 2, 0.075, n=12 if lod == 0 else 7, mat="cloth",
                      tag="bandage_roll", up=(0, 0, 1))
            g.box(o + (0.3, -0.12, 0.004), (0.26, 0.14, 0.008), mat="cloth", tag="bandage_strip")
        elif name == "chest":
            w, d, h = 1.0, 0.58, 0.48
            plank_box(g, o + (0, 0, h / 2), (w, d, h), lod, tag="chest_body", n=4)
            for xx in (-w / 2 + 0.05, -0.2, 0.2, w / 2 - 0.05):
                g.box(o + (xx, -d / 2 - 0.008, h / 2), (0.05, 0.016, h), mat="iron", tag="band")
                g.box(o + (xx, d / 2 + 0.008, h / 2), (0.05, 0.016, h), mat="iron", tag="band")
            for zz in (0.04, h - 0.04):
                g.box(o + (0, -d / 2 - 0.01, zz), (w, 0.02, 0.05), mat="iron", tag="band")
            for sx in (-1, 1):
                ring = [o + np.array([sx * (w / 2 + 0.03), 0.07 * math.cos(a), 0.3 + 0.07 * math.sin(a)]) for a in np.linspace(0, 2 * math.pi, 9)[:-1]]
                g.tube(np.array(ring + [ring[0]]), 0.012, n=4, mat="iron", tag="handle")
            # shield-shaped knot plate on the front
            g.box(o + (0, -d / 2 - 0.016, 0.24), (0.16, 0.012, 0.2), mat="wood", tag="front_plate")
            # contents (top level)
            g.box(o + (0, 0, h - 0.03), (w - 0.08, d - 0.08, 0.02), mat="cloth", tag="chest_fill")
            blob(g, o + (-0.28, -0.06, h - 0.05), (0.15, 0.11, 0.09), lod, "bread", "loaf", flat=0.7, seed=5, sub=1)
            CG.lathe(g, [(0.0, 0.0), (0.09, 0.02), (0.11, 0.1), (0.07, 0.17), (0.03, 0.2), (0.0, 0.21)],
                     o + (-0.1, 0.12, h - 0.05), n=8 if lod == 0 else 5, mat="sack", tag="sack_small")
            CG.lathe(g, [(0.0, 0.0), (0.09, 0.02), (0.11, 0.1), (0.07, 0.17), (0.03, 0.2), (0.0, 0.21)],
                     o + (0.05, 0.14, h - 0.05), n=8 if lod == 0 else 5, mat="sack", tag="sack_small")
            g.cyl(o + (0.12, 0.08, h + 0.06), o + (0.42, 0.08, h + 0.06), 0.1, n=10 if lod == 0 else 6, mat="cloth",
                  tag="cloth_roll", up=(0, 0, 1))
            g.cyl(o + (-0.12, -0.12, h + 0.04), o + (0.0, -0.12, h + 0.04), 0.05, n=8 if lod == 0 else 5, mat="cloth",
                  tag="bandage_roll", up=(0, 0, 1))
            for k in range(3):
                g.cyl(o + (0.12, -0.1, h - 0.02 + 0.012 * k), o + (0.12, -0.1, h - 0.008 + 0.012 * k), 0.035, n=8,
                      mat="bronze", tag="coin")
            # curved lid open (hinged at the back top edge, tilted back ~100 deg)
            lid_n = 7 if lod == 0 else 4
            hinge = o + (0, d / 2, h)
            ang = math.radians(100)
            Rx = np.array([[1, 0, 0], [0, math.cos(ang), -math.sin(ang)], [0, math.sin(ang), math.cos(ang)]])
            arc = [np.array([0.0, -d / 2 + d / 2 * math.cos(a), d / 2 * math.sin(a) * 0.55]) for a in np.linspace(0, math.pi, lid_n)]
            for k in range(lid_n - 1):
                a0, a1 = arc[k], arc[k + 1]
                mid = (a0 + a1) / 2 + np.array([0, -d / 2, 0])
                seg = a1 - a0
                L = float(np.linalg.norm(seg))
                tilt = math.atan2(seg[2], seg[1])
                Rt = np.array([[1, 0, 0], [0, math.cos(tilt), -math.sin(tilt)], [0, math.sin(tilt), math.cos(tilt)]])
                g.box(hinge + Rx @ (mid + np.array([0, d / 2, 0]) - np.array([0, d / 2, 0])), (w + 0.02, L + 0.01, 0.035),
                      R=Rx @ Rt, mat="wood", tag="chest_lid")
    return A


def make_cameras(views, A):
    """Per item: pinhole camera at 40 m along the painted view direction; f and principal point fitted so the
    item's projected bounding box equals its painted silhouette box. rep = box-corner residuals (px)."""
    W_ = A.world_mats({})
    for v in views:
        part = A.parts[f"supply_{v.name}"]
        V, F, _, _, _ = part.geo[0].arrays()
        c = V.mean(0)
        yaw, el = math.radians(v.yaw), math.radians(v.el)
        dirc = np.array([math.sin(yaw) * math.cos(el), -math.cos(yaw) * math.cos(el), math.sin(el)])
        C = c + dirc * 40.0
        fwd = (c - C) / np.linalg.norm(c - C)
        right = np.cross(fwd, (0, 0, 1.0))
        right /= np.linalg.norm(right)
        down = np.cross(fwd, right)
        R = np.stack([right, down, fwd])
        rv = cv2.Rodrigues(R)[0].ravel()
        tv = -R @ C
        cam = camsolve.Cam(1.0, 0.0, 0.0, rv, tv, size=v.size)
        u, w_, z = cam.project(V)
        m, _ = v.mask()
        ys, xs = np.nonzero(m)
        X0, X1, Y0, Y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        fx = (X1 - X0) / (u.max() - u.min())
        fy = (Y1 - Y0) / (w_.max() - w_.min())
        f = 0.5 * (fx + fy)
        cam.f = f
        cam.cx = (X0 + X1) / 2 - f * (u.max() + u.min()) / 2
        cam.cy = (Y0 + Y1) / 2 - f * (w_.max() + w_.min()) / 2
        u, w_, z = cam.project(V)
        res = np.array([u.min() - X0, u.max() - X1, w_.min() - Y0, w_.max() - Y1])
        v.cam = cam
        v.rep = dict(rms_px=float(np.sqrt((res ** 2).mean())), max_px=float(np.abs(res).max()), n=4,
                     per_point_px={"x0": round(float(res[0]), 2), "x1": round(float(res[1]), 2), "y0": round(float(res[2]), 2),
                                   "y1": round(float(res[3]), 2)},
                     fov_deg=float(2 * math.degrees(math.atan(max(v.size) / 2 / f))), f=f,
                     method="silhouette-box fit of a 40 m pinhole along the painted view direction (no PnP)")


SWATCHES = {
    "wood": dict(sheet=SHEET, box=(60, 790, 100, 830), metres=0.3),
    "iron": dict(sheet=SHEET, box=(1150, 860, 1165, 900), metres=0.1),
    "cloth": dict(sheet=SHEET, box=(430, 800, 470, 830), metres=0.25),
    "sack": dict(sheet=SHEET, box=(650, 790, 690, 830), metres=0.25),
    "grain": dict(sheet=SHEET, box=(740, 800, 770, 812), metres=0.1),
    "rope": dict(sheet=SHEET, box=(1050, 850, 1070, 870), metres=0.05),
    "bronze": dict(sheet=SHEET, box=(915, 830, 945, 860), metres=0.06),
    "bread": dict(sheet=SHEET, box=(120, 930, 170, 960), metres=0.15),
    "feather": dict(sheet=SHEET, box=(1130, 790, 1150, 810), metres=0.05),
}


def clips(A, B):
    pass


def meta(A, p):
    return {"items": {f"supply_{k}": {"painted_box": list(v[0]), "pile_xy_gltf": [v[1][0], -v[1][1]]} for k, v in ITEMS.items()},
            "budget_note": "supplies <= 1k tris per item at LOD0",
            "usage": "each supply_* node can be shown/hidden or instanced separately (reward piles, chest contents)"}
