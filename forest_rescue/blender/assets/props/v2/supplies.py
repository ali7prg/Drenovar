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


EXCLUDE = {"arrows": [(965, 790, 1004, 874), (1136, 832, 1176, 986)], "bread": [(276, 895, 322, 918)],
           "bandages": [(425, 994, 565, 1006)]}


def views():
    out = []
    for name, (box, xy, yaw, el) in ITEMS.items():
        hide = {f"supply_{o}": "hide" for o in ITEMS if o != name}
        v = pv2.ViewSpec(name, SHEET, box, {}, pose=hide, light=LIGHT, thresh=0.10, fill_holes=True, shadow=0.10,
                         exclude=EXCLUDE.get(name, ()),
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


ARROW = dict(theta=math.radians(34), tie_z=0.39, lh=0.47, ln=0.37, n=12)


def arrow_frame(o):
    th = ARROW["theta"]
    d = np.array([math.sin(th), 0.0, math.cos(th)])
    u = np.array([math.cos(th), 0.0, -math.sin(th)])
    w = np.array([0.0, 1.0, 0.0])
    T = np.asarray(o, float) + np.array([0.0, 0.0, ARROW["tie_z"]])
    return T, d, u, w


def arrow_keypoints(o):
    T, d, u, w = arrow_frame(o)
    H = T - d * ARROW["lh"]
    N = T + d * ARROW["ln"]
    return {"nock_c": N, "head_c": H, "tie_c": T, "tie_l": T - u * 0.05, "tie_r": T + u * 0.05,
            "head_l": H - u * 0.085, "head_r": H + u * 0.085, "nock_l": N - u * 0.075, "nock_r": N + u * 0.075}


def arrow_bundle(g, o, lod):
    """About 12 arrows tied at the waist: shafts fanning out to both ends, steel bodkin heads, three grey vanes each,
    a rope tie of three turns."""
    T, d, u, w = arrow_frame(o)
    n = ARROW["n"] if lod < 2 else 6
    rng = np.random.default_rng(3)
    for i in range(n):
        a = 2 * math.pi * i / n + rng.uniform(-0.2, 0.2)
        ra = 0.55 + 0.45 * (i % 3) / 2
        ou, ow = math.cos(a) * ra, math.sin(a) * ra * 0.7
        offH = (u * ou + w * ow) * 0.10
        offN = (u * ou + w * ow) * 0.09
        offT = (u * ou + w * ow) * 0.022
        Hh = T - d * ARROW["lh"] + offH
        Nn = T + d * ARROW["ln"] + offN
        Tt = T + offT
        g.tube(np.array([Hh + (Tt - Hh) * 0.08, Tt, Nn]), 0.0058, n=5 if lod == 0 else 4, mat="shaftwood", tag="shaft")
        dh = (Hh - Tt) / np.linalg.norm(Hh - Tt)
        # bodkin head: long 4-sided pyramid with a short socket
        CG.lathe(g, [(0.009, -0.012), (0.013, 0.0), (0.0, 0.075)], Hh, n=4, mat="steel", tag="arrowhead",
                 R=CG.frame(np.cross(dh, (0, 1.0, 0)), dh))
        if lod < 2:
            dn = (Nn - Tt) / np.linalg.norm(Nn - Tt)
            side0 = np.cross(dn, (0, 1.0, 0))
            side0 /= np.linalg.norm(side0)
            for k in range(3):
                ang = 2 * math.pi * k / 3 + a
                sd = side0 * math.cos(ang) + np.cross(dn, side0) * math.sin(ang)
                c0 = Nn - dn * 0.03
                q = [c0 - dn * 0.135, c0 - dn * 0.01, c0 - dn * 0.03 + sd * 0.033, c0 - dn * 0.12 + sd * 0.031]
                g.add(np.array(q), [[0, 1, 2, 3], [3, 2, 1, 0]], "feather", "fletching")
                if lod == 0:
                    g.tube(np.array([c0 - dn * 0.13, c0 - dn * 0.012]), 0.0018, n=3, mat="quill", tag="quill")
    for k in range(3 if lod < 2 else 1):
        c = T + d * (0.016 * (k - 1))
        ring = [c + (u * 0.031 * math.cos(t) + w * 0.026 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 13)[:-1]]
        g.tube(np.array(ring + [ring[0]]), 0.0075, n=5 if lod == 0 else 4, mat="rope", tag="arrow_tie")


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
            nc = 14 if lod == 0 else 7
            for (dx, dy, n_) in ((0.0, 0.05, 6), (0.078, 0.015, 3), (-0.078, 0.025, 2), (0.13, -0.03, 2), (-0.135, -0.025, 1)):
                for k in range(n_ if lod < 2 else max(1, (n_ + 1) // 2)):
                    t0 = 0.0085 * k * (1 if lod < 2 else 2)
                    c = o + (dx + 0.0015 * math.sin(3 * k), dy, t0)
                    g.cyl(c, c + (0, 0, 0.0085), 0.047, n=nc, mat="bronze", tag="coin")
            # big coin leaning toward the viewer in front of the stacks (painting)
            nrm = np.array([0.0, -math.sin(math.radians(52)), math.cos(math.radians(52))])
            c = o + (0.0, -0.04, 0.05)
            g.cyl(c - nrm * 0.007, c + nrm * 0.007, 0.062, n=16 if lod == 0 else 8, mat="bronze", tag="coin_front",
                  up=(0, 0, 1))
        elif name == "arrows":
            arrow_bundle(g, o, lod)
        elif name == "bread":
            blob(g, o + (-0.16, -0.02, 0), (0.17, 0.13, 0.135), lod, "bread", "loaf", flat=0.55, seed=1)
            blob(g, o + (0.16, 0.06, 0), (0.16, 0.125, 0.14), lod, "bread", "loaf", flat=0.55, seed=2)
        elif name == "bandages":
            ax = np.array([0.55, 0.83, 0.0])
            ax /= np.linalg.norm(ax)
            for (dx, dy, L, r) in ((-0.13, 0.02, 0.30, 0.088), (0.13, -0.04, 0.28, 0.084)):
                cc = o + (dx, dy, r)
                g.cyl(cc - ax * L / 2, cc + ax * L / 2, r, n=14 if lod == 0 else 8, mat="cloth", tag="bandage_roll",
                      up=(0, 0, 1))
            # loose tail unrolling from the right roll toward the front-right
            tail = [o + (0.17, -0.12, 0.004), o + (0.3, -0.16, 0.004), o + (0.42, -0.15, 0.004)]
            for k in range(2):
                p0_, p1_ = np.array(tail[k]), np.array(tail[k + 1])
                g.beam(p0_, p1_, 0.24, 0.008, up=(0, 0, 1), mat="cloth", tag="bandage_tail")
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


ARROW_PX = {"nock_c": (1131, 764), "head_c": (1010, 961), "tie_c": (1067, 865), "tie_l": (1045, 860),
            "tie_r": (1090, 876.7), "head_l": (978.3, 950), "head_r": (1046.7, 965), "nock_l": (1090, 761.7),
            "nock_r": (1163.3, 785)}


def _sil_iou(cam, V, T, mask):
    u, w_, z = cam.project(V)
    H, W = mask.shape
    m = np.zeros((H, W), np.uint8)
    pts = np.stack([u, w_], 1)
    for t in T:
        cv2.fillConvexPoly(m, np.round(pts[t] * 4).astype(np.int32), 1, lineType=cv2.LINE_8, shift=2)
    r = m > 0
    return (r & mask).sum() / max(1, (r | mask).sum())


def make_cameras(views, A):
    """Arrows: cv2.solvePnP (9 painted points: nock/head fan ends, tie) via camsolve. Other items: pinhole 40 m
    away; yaw / elevation searched by silhouette IoU, f + principal point fitted to the painted box."""
    from geo import triangulate
    for v in views:
        if v.name == "arrows":
            x, y = ITEMS["arrows"][1]
            K3 = arrow_keypoints((x, y, 0.0))
            keys = list(ARROW_PX)
            v.points = dict(ARROW_PX)
            cam, rep = camsolve.solve(np.array([K3[k] for k in keys]), v.p2(keys), v.size, f0=None)
            v.cam = cam
            rep["method"] = "cv2.solvePnP (focal scan) + LM refinement on 9 points (nock/head fan ends, tie)"
            rep["per_point_px"] = {k: e for k, e in zip(keys, rep["per_point_px"])}
            v.rep = rep
            continue
        part = A.parts[f"supply_{v.name}"]
        V, F, _, _, _ = part.geo[0].arrays()
        T = np.array(triangulate(F))
        m, _ = v.mask()
        best = None
        y0, e0 = v.yaw, v.el
        for dy in range(-30, 31, 6):
            for de in range(-12, 19, 6):
                cam = _box_cam(v, V, y0 + dy, max(2, e0 + de), m)
                iou = _sil_iou(cam, V, T, m)
                if best is None or iou > best[0]:
                    best = (iou, cam, y0 + dy, max(2, e0 + de))
        iou, cam, yy, ee = best
        v.cam = cam
        u, w_, z = cam.project(V)
        ys, xs = np.nonzero(m)
        res = np.array([u.min() - xs.min(), u.max() - xs.max() - 1, w_.min() - ys.min(), w_.max() - ys.max() - 1])
        v.rep = dict(rms_px=float(np.sqrt((res ** 2).mean())), max_px=float(np.abs(res).max()), n=4,
                     per_point_px={"x0": round(float(res[0]), 2), "x1": round(float(res[1]), 2),
                                   "y0": round(float(res[2]), 2), "y1": round(float(res[3]), 2)},
                     fov_deg=float(2 * math.degrees(math.atan(max(v.size) / 2 / cam.f))), f=cam.f,
                     method=f"silhouette-IoU search of the painted view direction (yaw {yy}, el {ee}) + box fit")


def _box_cam(v, V, yaw_deg, el_deg, m):
    c = V.mean(0)
    yaw, el = math.radians(yaw_deg), math.radians(el_deg)
    dirc = np.array([math.sin(yaw) * math.cos(el), -math.cos(yaw) * math.cos(el), math.sin(el)])
    C = c + dirc * 40.0
    fwd = (c - C) / np.linalg.norm(c - C)
    right = np.cross(fwd, (0, 0, 1.0))
    right /= np.linalg.norm(right)
    down = np.cross(fwd, right)
    R = np.stack([right, down, fwd])
    cam = camsolve.Cam(1.0, 0.0, 0.0, cv2.Rodrigues(R)[0].ravel(), -R @ C, size=v.size)
    u, w_, z = cam.project(V)
    ys, xs = np.nonzero(m)
    X0, X1, Y0, Y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    f = 0.5 * ((X1 - X0) / (u.max() - u.min()) + (Y1 - Y0) / (w_.max() - w_.min()))
    cam.f = f
    cam.cx = (X0 + X1) / 2 - f * (u.max() + u.min()) / 2
    cam.cy = (Y0 + Y1) / 2 - f * (w_.max() + w_.min()) / 2
    return cam


def make_cameras_old(views, A):
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


def _lum(c):
    return c @ np.array([0.299, 0.587, 0.114])


GATE = {"shaftwood": lambda c: _lum(c) < 0.72,
        "feather": lambda c: np.zeros(c.shape[:2], bool),      # vanes: synthesised from painted feather pixels only
        "quill": lambda c: np.zeros(c.shape[:2], bool),
        "steel": lambda c: _lum(c) < 0.6,
        "rope": lambda c: _lum(c) < 0.75}

SWATCHES = {
    "wood": dict(sheet=SHEET, box=(60, 790, 100, 830), metres=0.3),
    "shaftwood": dict(sheet=SHEET, box=(1046, 892, 1050, 900), metres=0.03),
    "iron": dict(sheet=SHEET, box=(1150, 860, 1165, 900), metres=0.1),
    "cloth": dict(sheet=SHEET, box=(430, 800, 470, 830), metres=0.25),
    "sack": dict(sheet=SHEET, box=(650, 790, 690, 830), metres=0.25),
    "grain": dict(sheet=SHEET, box=(740, 800, 770, 812), metres=0.1),
    "rope": dict(sheet=SHEET, box=(1058, 860, 1072, 870), metres=0.04),
    "bronze": dict(sheet=SHEET, box=(915, 830, 945, 860), metres=0.06),
    "bread": dict(sheet=SHEET, box=(120, 930, 170, 960), metres=0.15),
    "feather": dict(sheet=SHEET, box=(1127, 778, 1141, 792), metres=0.05),
    "steel": dict(sheet=SHEET, box=(985, 935, 1000, 950), metres=0.04),
    "quill": dict(sheet=SHEET, box=(1098, 796, 1102, 800), metres=0.01),
}


def clips(A, B):
    pass


def meta(A, p):
    return {"items": {f"supply_{k}": {"painted_box": list(v[0]), "pile_xy_gltf": [v[1][0], -v[1][1]]} for k, v in ITEMS.items()},
            "budget_note": "supplies <= 1k tris per item at LOD0",
            "usage": "each supply_* node can be shown/hidden or instanced separately (reward piles, chest contents)"}
