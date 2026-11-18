"""Ancient Maw anatomy: skeleton landmarks, SDF parts (trunk loft, skull, jaw, limbs, osteoderms).

World: Blender Z up, metres, creature faces -Y, feet on Z=0, hip joint above the origin.
All landmark numbers come from measurements of art/03 (see maw_refs for the pixel->metre mapping).
The trunk (neck->tail tip) is a loft whose vertical extent per Y is read from the reference side mask
(top skin line with osteoderm bumps closed away) and a belly line (hidden behind the legs in the
drawing, so given by control points); lateral half-widths are an anatomical profile checked against
the front view.
"""
import math
import os
import sys

import numpy as np
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
from frlib import sdf  # noqa: E402
import maw_refs as R  # noqa: E402

PPM = R.SIDE_PPM


def S(u, row):
    """full-image side pixel -> (Y, Z) metres"""
    y, z = R.side_to_world(u, row)
    return float(y), float(z)


# ------------------------------------------------------------------------------------- skeleton
HIP = np.array([0.56, 0.0, 2.41])          # left hip joint (x mirrored for right)
KNEE = np.array([0.74, -0.68, 1.67])
ANKLE = np.array([0.66, 0.0, 0.86])
BALL = np.array([0.66, -0.13, 0.18])
SHOULDER = np.array([0.50, -1.80, 2.30])
ELBOW = np.array([0.64, -1.62, 1.88])
WRIST = np.array([0.47, -1.84, 1.55])
HAND_END = np.array([0.45, -1.93, 1.42])
JAW_HINGE = np.array([0.0, -3.24, 2.97])
MOUTH_CORNER_Y = -3.36


def _y(u):
    return (u - R.SIDE_HIP_COL) / PPM


def _z(row):
    return (R.SIDE_GROUND - row) / PPM


def tail_centreline(n=11):
    """Points along the tail centre (mid between skin top and bottom) from the tail base to the tip."""
    prof = trunk_profile()
    Y, ztop, zbot = prof["Y"], prof["ztop"], prof["zbot"]
    ys = np.linspace(0.38, Y[-1] - 0.01, 400)
    zc = np.interp(ys, Y, 0.5 * (ztop + zbot))
    # arc-length param, segment lengths shrinking toward the tip
    seg = np.linspace(1.25, 0.75, n - 1)
    seg = seg / seg.sum()
    pts3 = np.stack([np.zeros_like(ys), ys, zc], 1)
    d = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts3, axis=0), axis=1))])
    targets = np.concatenate([[0], np.cumsum(seg)]) * d[-1]
    out = np.stack([np.interp(targets, d, pts3[:, k]) for k in range(3)], 1)
    return out


def spine_points():
    """pelvis -> chest -> neck -> head base control points (x=0)."""
    return {
        "pelvis": (np.array([0, 0.02, 2.47]), np.array([0, -0.50, 2.62])),
        "spine_01": (np.array([0, -0.50, 2.62]), np.array([0, -1.08, 2.76])),
        "spine_02": (np.array([0, -1.08, 2.76]), np.array([0, -1.62, 2.86])),
        "spine_03": (np.array([0, -1.62, 2.86]), np.array([0, -2.15, 2.93])),
        "neck_01": (np.array([0, -2.15, 2.93]), np.array([0, -2.55, 3.02])),
        "neck_02": (np.array([0, -2.55, 3.02]), np.array([0, -2.90, 3.10])),
        "neck_03": (np.array([0, -2.90, 3.10]), np.array([0, -3.17, 3.16])),
        "head": (np.array([0, -3.17, 3.16]), np.array([0, -4.35, 3.10])),
        "jaw": (JAW_HINGE.copy(), np.array([0, -4.40, 2.70])),
        "tongue_01": (np.array([0, -3.30, 2.86]), np.array([0, -3.62, 2.86])),
        "tongue_02": (np.array([0, -3.62, 2.86]), np.array([0, -3.92, 2.85])),
        "tongue_03": (np.array([0, -3.92, 2.85]), np.array([0, -4.18, 2.84])),
    }


def _mir(p, side):
    p = np.array(p, float)
    if side == "R":
        p[0] = -p[0]
    return p


def leg_points(side="L"):
    m = lambda p: _mir(p, side)  # noqa: E731
    pts = {
        f"thigh_{side}": (m(HIP), m(KNEE)),
        f"shin_{side}": (m(KNEE), m(ANKLE)),
        f"foot_{side}": (m(ANKLE), m(BALL)),
        # digit II (inner), III (middle), IV (outer): proximal + distal(claw) segments
        f"toe2a_{side}": (m([0.57, -0.20, 0.13]), m([0.45, -0.46, 0.10])),
        f"toe2b_{side}": (m([0.45, -0.46, 0.10]), m([0.37, -0.64, 0.07])),
        f"toe3a_{side}": (m([0.67, -0.22, 0.14]), m([0.70, -0.53, 0.10])),
        f"toe3b_{side}": (m([0.70, -0.53, 0.10]), m([0.72, -0.73, 0.07])),
        f"toe4a_{side}": (m([0.78, -0.18, 0.13]), m([0.93, -0.42, 0.10])),
        f"toe4b_{side}": (m([0.93, -0.42, 0.10]), m([1.02, -0.58, 0.07])),
        f"dewclaw_{side}": (m([0.50, 0.08, 0.44]), m([0.48, 0.17, 0.31])),
    }
    return pts


def arm_points(side="L"):
    m = lambda p: _mir(p, side)  # noqa: E731
    return {
        f"upperarm_{side}": (m(SHOULDER), m(ELBOW)),
        f"forearm_{side}": (m(ELBOW), m(WRIST)),
        f"hand_{side}": (m(WRIST), m(HAND_END)),
        f"finger1a_{side}": (m([0.41, -1.95, 1.42]), m([0.39, -2.03, 1.33])),
        f"finger1b_{side}": (m([0.39, -2.03, 1.33]), m([0.38, -2.06, 1.20])),
        f"finger2a_{side}": (m([0.50, -1.95, 1.41]), m([0.51, -2.02, 1.31])),
        f"finger2b_{side}": (m([0.51, -2.02, 1.31]), m([0.51, -2.04, 1.18])),
        f"finger3_{side}": (m([0.55, -1.90, 1.43]), m([0.58, -1.94, 1.36])),
    }


PARENTS = {
    "root": None, "pelvis": "root", "spine_01": "pelvis", "spine_02": "spine_01", "spine_03": "spine_02",
    "neck_01": "spine_03", "neck_02": "neck_01", "neck_03": "neck_02", "head": "neck_03", "jaw": "head",
    "tongue_01": "jaw", "tongue_02": "tongue_01", "tongue_03": "tongue_02",
}


def bone_table():
    """Ordered list of dicts for frlib.rig.armature (all deform)."""
    bones = [{"name": "root", "head": (0, 0, 0), "tail": (0, -0.6, 0), "parent": None}]
    sp = spine_points()
    for name in ["pelvis", "spine_01", "spine_02", "spine_03", "neck_01", "neck_02", "neck_03", "head",
                 "jaw", "tongue_01", "tongue_02", "tongue_03"]:
        h, t = sp[name]
        bones.append({"name": name, "head": tuple(h), "tail": tuple(t), "parent": PARENTS[name],
                      "connect": name in ("spine_01", "spine_02", "spine_03", "neck_01", "neck_02",
                                          "neck_03", "tongue_02", "tongue_03")})
    tc = tail_centreline(11)
    for i in range(10):
        bones.append({"name": f"tail_{i + 1:02d}", "head": tuple(tc[i]), "tail": tuple(tc[i + 1]),
                      "parent": "pelvis" if i == 0 else f"tail_{i:02d}", "connect": i > 0})
    for side in "LR":
        lp = leg_points(side)
        par = {f"thigh_{side}": "pelvis", f"shin_{side}": f"thigh_{side}", f"foot_{side}": f"shin_{side}",
               f"toe2a_{side}": f"foot_{side}", f"toe2b_{side}": f"toe2a_{side}",
               f"toe3a_{side}": f"foot_{side}", f"toe3b_{side}": f"toe3a_{side}",
               f"toe4a_{side}": f"foot_{side}", f"toe4b_{side}": f"toe4a_{side}",
               f"dewclaw_{side}": f"foot_{side}"}
        for n, (h, t) in lp.items():
            bones.append({"name": n, "head": tuple(h), "tail": tuple(t), "parent": par[n],
                          "connect": n.startswith(("shin", "foot", "toe2b", "toe3b", "toe4b"))})
        ap = arm_points(side)
        par = {f"upperarm_{side}": "spine_03", f"forearm_{side}": f"upperarm_{side}",
               f"hand_{side}": f"forearm_{side}", f"finger1a_{side}": f"hand_{side}",
               f"finger1b_{side}": f"finger1a_{side}", f"finger2a_{side}": f"hand_{side}",
               f"finger2b_{side}": f"finger2a_{side}", f"finger3_{side}": f"hand_{side}"}
        for n, (h, t) in ap.items():
            bones.append({"name": n, "head": tuple(h), "tail": tuple(t), "parent": par[n],
                          "connect": n.startswith(("forearm", "hand", "finger1b", "finger2b"))})
    return bones


# ------------------------------------------------------------------------------------- profiles
_PROFILE = None

# belly line control points (full-image side coords); hidden behind legs in the drawing
BELLY_CTRL = [(232, 300), (262, 316), (300, 326), (330, 327), (360, 329), (390, 333), (420, 344),
              (450, 352), (475, 348), (495, 333), (515, 313), (530, 302)]
TRUNK_U0, TRUNK_U1 = 132, 914           # trunk loft extent (neck/throat start .. tail tip)


def _closing_profile(top, w=13):
    mx = ndi.maximum_filter1d(top, w, mode="nearest")
    return ndi.minimum_filter1d(mx, w, mode="nearest")


def trunk_profile():
    """Per-Y tables of the trunk loft (computed once from the corrected side mask)."""
    global _PROFILE
    if _PROFILE is not None:
        return _PROFILE
    _crop, m = R.side_mask(corrected=True)
    x0, y0 = R.SIDE_BOX[:2]
    us = np.arange(TRUNK_U0, TRUNK_U1 + 1)
    top = np.array([np.nonzero(m[:, u - x0])[0].min() + y0 if m[:, u - x0].any() else np.nan for u in us],
                   float)
    # first-run bottom (trunk) where it is the trunk (tail / throat)
    bot = np.full(len(us), np.nan)
    for i, u in enumerate(us):
        col = m[:, u - x0]
        if not col.any():
            continue
        r0 = np.nonzero(col)[0].min()
        r1 = r0
        while r1 + 1 < len(col) and col[r1 + 1]:
            r1 += 1
        bot[i] = r1 + y0
    # osteoderm bumps closed away -> skin line
    good = ~np.isnan(top)
    top = np.interp(us, us[good], top[good])
    skin = _closing_profile(top, 15)
    skin = ndi.gaussian_filter1d(skin, 6.0)
    # bottom: mask in throat (u<232) and tail (u>530), control points in between
    bu = np.array([p[0] for p in BELLY_CTRL], float)
    bv = np.array([p[1] for p in BELLY_CTRL], float)
    from scipy.interpolate import PchipInterpolator
    belly = PchipInterpolator(bu, bv)(np.clip(us, bu[0], bu[-1]))
    bottom = np.where(us < bu[0], bot, np.where(us > bu[-1], bot, belly))
    # throat: the head's lower jaw covers u<150; keep throat line smooth
    bottom = ndi.gaussian_filter1d(np.interp(us, us[~np.isnan(bottom)], bottom[~np.isnan(bottom)]), 3.5)
    # neck start: keep the loft top below the skull top (head parts own the skull)
    Y = _y(us.astype(float))
    ztop = _z(skin)
    zbot = _z(bottom)
    # front cap of the loft (inside the head): pull the top down for u<175
    pull = np.clip((175 - us) / 43.0, 0, 1)
    ztop = ztop - pull * 0.35
    # half widths (anatomical profile, checked against the front view)
    ctrl_y = [-3.40, -3.10, -2.80, -2.40, -2.00, -1.60, -1.20, -0.70, -0.20, 0.30, 0.80, 1.40, 2.00,
              2.70, 3.40, 4.10, 4.70, 5.10, 5.26]
    ctrl_w = [0.36, 0.44, 0.48, 0.53, 0.60, 0.67, 0.73, 0.77, 0.75, 0.66, 0.55, 0.45, 0.37,
              0.30, 0.23, 0.155, 0.095, 0.05, 0.02]
    hx = np.interp(Y, ctrl_y, ctrl_w)
    egg = np.interp(Y, [-3.4, -2.6, -2.0, -1.6, -1.0, -0.4, 0.0, 0.4, 0.9, 1.4, 5.3],
                    [0.0, 0.08, 0.22, 0.33, 0.45, 0.45, 0.36, 0.22, 0.10, 0.08, 0.05])
    pexp = np.interp(Y, [-3.4, -2.0, 0.0, 2.0, 5.3], [2.1, 2.05, 2.1, 2.2, 2.2])
    zc = 0.5 * (ztop + zbot)
    hz = 0.5 * (ztop - zbot)
    # tail tip rounding
    _PROFILE = {"us": us, "Y": Y, "ztop": ztop, "zbot": zbot, "zc": zc, "hz": hz, "hx": hx, "egg": egg,
                "p": pexp, "top_raw_row": top}
    return _PROFILE


# ------------------------------------------------------------------------------------- SDF prims
def loft(Y, zc, hz, hx, egg, pexp, bone=None, name="loft", k=0.0, cap_front=0.12, cap_back=0.0):
    """Generalised cylinder with super-elliptic vertical slices; ellipsoidal end caps."""
    Y = np.asarray(Y, float)
    y0 = Y[0]
    n = len(Y)
    dy = (Y[-1] - Y[0]) / (n - 1)
    Yu = y0 + np.arange(n) * dy
    zc, hz, hx, egg, pexp = [np.interp(Yu, Y, np.asarray(a, float)) for a in (zc, hz, hx, egg, pexp)]
    hz = hz.copy()
    hx = hx.copy()
    if cap_front > 0:
        t = np.clip((y0 + cap_front - Yu) / cap_front, 0, 1)
        f = np.sqrt(np.clip(1 - t * t, 0.0, 1.0))
        hz *= np.maximum(f, 0.02)
        hx *= np.maximum(f, 0.02)
    if cap_back > 0:
        t = np.clip((Yu - (Yu[-1] - cap_back)) / cap_back, 0, 1)
        f = np.sqrt(np.clip(1 - t * t, 0.0, 1.0))
        hz *= np.maximum(f, 0.02)
        hx *= np.maximum(f, 0.02)
    T = [zc, hz, hx, egg, pexp]

    def fn(P):
        x, y, z = P[..., 0], P[..., 1], P[..., 2]
        fi = np.clip((y - y0) / dy, 0, n - 1.0001)
        i = np.floor(fi).astype(np.int64)
        f = fi - i
        c, h, w, e, pp = [a[i] * (1 - f) + a[i + 1] * f for a in T]
        h = np.maximum(h, 1e-3)
        t = (z - c) / h
        wt = np.maximum(w * (1.0 - e * np.clip(t, -1, 1)), 1e-3)
        s = np.abs(x) / wt
        r = (s ** pp + np.abs(t) ** pp) ** (1.0 / pp)
        d = (r - 1.0) * np.minimum(wt, h)
        d = np.maximum(d, np.maximum(y0 - y, y - Yu[-1]))
        return d

    lo = np.array([-np.max(hx) * 1.35, y0, np.min(zc - hz) - 0.05])
    hi = np.array([np.max(hx) * 1.35, Yu[-1], np.max(zc + hz) + 0.05])
    return sdf.Prim(fn, lo, hi, bone=bone, name=name, k=k)


def oriented_ellipsoid(c, axis, r_axis, r_side, r_up, up=(0, 0, 1), **kw):
    a = np.asarray(axis, float)
    a /= np.linalg.norm(a)
    u = np.asarray(up, float)
    s = np.cross(a, u)
    if np.linalg.norm(s) < 1e-6:
        s = np.cross(a, [1, 0, 0])
    s /= np.linalg.norm(s)
    u2 = np.cross(s, a)
    Rm = np.stack([a, s, u2], 1)  # columns = local axes
    return sdf.ellipsoid(c, (r_axis, r_side, r_up), rot=Rm, **kw)


def head_profiles():
    """Upper skull and lower jaw outlines (full-image side coords -> metres)."""
    # skull top skin line (brow knobs excluded) — read from mask, closed
    _crop, m = R.side_mask(corrected=True)
    x0, y0 = R.SIDE_BOX[:2]
    us = np.arange(46, 200)
    top = np.array([np.nonzero(m[:, u - x0])[0].min() + y0 for u in us], float)
    top = ndi.gaussian_filter1d(_closing_profile(top, 11), 3.0)
    # snout front: blunt rounded tip (mask gives it)
    mouth_u = [44, 60, 80, 100, 115, 130, 142, 152]
    mouth_r = [211, 212, 212, 211, 209, 205, 200, 197]          # upper lip line (teeth row)
    # lower jaw bottom: reference mask (first run) up to the throat start, then held level
    bot = []
    for u in us:
        col = m[:, u - x0]
        r0 = np.nonzero(col)[0].min()
        r1 = r0
        while r1 + 1 < len(col) and col[r1 + 1]:
            r1 += 1
        bot.append(r1 + y0)
    bot = np.array(bot, float)
    jaw_u = [int(u) for u in us[us <= 132]] + [150, 165, 180]
    jaw_r = list(ndi.gaussian_filter1d(bot[us <= 132], 1.2)) + [250, 248, 242]
    return {"us": us, "top": top, "mouth_u": mouth_u, "mouth_r": mouth_r, "jaw_u": jaw_u, "jaw_r": jaw_r}


def mouth_z(y):
    hp = head_profiles()
    us = R.SIDE_HIP_COL + np.asarray(y) * PPM
    return _z(np.interp(us, hp["mouth_u"], hp["mouth_r"]))


def head_widths(y):
    """Upper-jaw (W_u) and mandible (W_l) half widths at the lip line, per Y."""
    y = np.asarray(y, float)
    wu = np.interp(y, [-4.52, -4.47, -4.38, -4.20, -3.95, -3.70, -3.50, -3.30, -3.10],
                   [0.13, 0.23, 0.29, 0.33, 0.36, 0.40, 0.43, 0.44, 0.41])
    wl = np.maximum(wu - np.interp(y, [-4.5, -4.3, -3.5, -3.3], [0.035, 0.045, 0.05, 0.03]), 0.06)
    return wu, wl


HEAD_Y0 = (46 - R.SIDE_HIP_COL) / PPM
HEAD_CAP = 0.07


def lip_outline(y):
    """Half widths of upper/lower lip margins including the rounded snout tip."""
    wu, wl = head_widths(y)
    t = np.clip((HEAD_Y0 + HEAD_CAP - np.asarray(y, float)) / HEAD_CAP, 0, 1)
    f = np.maximum(np.sqrt(np.clip(1 - t * t, 0, 1)), 0.05)
    return wu * f, wl * f


def head_prim(Yh, ztop, zm, zj, cap=HEAD_CAP):
    """Skull + mandible as one loft: widest at the lip line (upper jaw overhangs the lower jaw)."""
    Yh = np.asarray(Yh, float)
    n = len(Yh)
    y0 = Yh[0]
    dy = (Yh[-1] - y0) / (n - 1)
    Yu = y0 + np.arange(n) * dy
    zt = np.interp(Yu, Yh, ztop)
    zmm = np.interp(Yu, Yh, zm)
    zb = np.interp(Yu, Yh, zj)
    wu, wl = head_widths(Yu)
    # rounded snout tip (top view): shrink widths in the first `cap` metres
    t = np.clip((y0 + cap - Yu) / cap, 0, 1)
    f = np.sqrt(np.clip(1 - t * t, 0, 1))
    wu = wu * np.maximum(f, 0.05)
    wl = wl * np.maximum(f, 0.05)
    pu = np.interp(Yu, [-4.5, -4.2, -3.9, -3.1], [3.0, 3.0, 2.6, 2.2])
    pl = np.interp(Yu, [-4.5, -3.1], [2.3, 2.1])
    T = [zt, zmm, zb, wu, wl, pu, pl]

    def fn(P):
        x, y, z = P[..., 0], P[..., 1], P[..., 2]
        fi = np.clip((y - y0) / dy, 0, n - 1.0001)
        i = np.floor(fi).astype(np.int64)
        fr = fi - i
        a_t, a_m, a_b, a_wu, a_wl, a_pu, a_pl = [arr[i] * (1 - fr) + arr[i + 1] * fr for arr in T]
        hu = np.maximum(a_t - a_m, 1e-3)
        hl = np.maximum(a_m - a_b, 1e-3)
        up = z >= a_m
        sz = np.where(up, (z - a_m) / hu, (a_m - z) / hl)
        w = np.where(up, a_wu, a_wl)
        pp = np.where(up, a_pu, a_pl)
        sx = np.abs(x) / np.maximum(w, 1e-3)
        r = (sx ** pp + sz ** pp) ** (1.0 / pp)
        sc = np.minimum(w, np.where(up, hu, hl))
        d = (r - 1.0) * sc
        d = np.maximum(d, np.maximum(y0 - y, y - Yu[-1]))
        return d

    lo = np.array([-0.6, y0, zb.min() - 0.05])
    hi = np.array([0.6, Yu[-1], zt.max() + 0.05])
    return sdf.Prim(fn, lo, hi, bone="head", name="head", k=0.0)


def build_parts(detail=True):
    """Return (add_parts, sub_parts, weight_parts) lists of sdf.Prim."""
    add, sub = [], []
    prof = trunk_profile()
    add.append(loft(prof["Y"], prof["zc"], prof["hz"], prof["hx"], prof["egg"], prof["p"], name="trunk",
                    bone="spine_02"))
    hp = head_profiles()
    us = hp["us"].astype(float)
    Yh = _y(us)
    ztop = _z(hp["top"])
    zm = _z(np.interp(us, hp["mouth_u"], hp["mouth_r"]))
    zj = _z(np.interp(us, hp["jaw_u"], hp["jaw_r"]))
    add.append(head_prim(Yh, ztop, zm, zj))
    for sx in (1, -1):
        # jaw adductor / cheek bulge behind the mouth corner
        add.append(oriented_ellipsoid([sx * 0.30, -3.30, 2.98], [0, -1, 0.15], 0.30, 0.15, 0.26, k=0.10,
                                      name="cheek", bone="head"))
        # jaw angle mass (lower jaw rear)
        add.append(oriented_ellipsoid([sx * 0.30, -3.42, 2.72], [0, -1, 0.25], 0.28, 0.14, 0.17, k=0.08,
                                      name="jaw_angle", bone="jaw"))
        # brow ridge (keratin) above the eye, running to the skull roof
        add.append(sdf.round_cone([sx * 0.25, -3.86, 3.33], [sx * 0.28, -3.48, 3.45], 0.055, 0.065, k=0.06,
                                  name="brow", bone="head"))
        # orbit rim below the eye
        add.append(sdf.round_cone([sx * 0.33, -3.78, 3.18], [sx * 0.40, -3.48, 3.22], 0.05, 0.06, k=0.05,
                                  name="cheekbone", bone="head"))
        # nostril pits
        sub.append(oriented_ellipsoid([sx * 0.13, -4.42, 3.10], [0, -1, 0.3], 0.07, 0.045, 0.035, k=0.015,
                                      name="nostril"))
        # eye socket + eyelid ring (the eye mesh sits inside, see maw_details.eye_centre)
        sub.append(sdf.sphere([sx * 0.315, -3.62, 3.27], 0.062, k=0.015, name="orbit"))
        ax = np.array([sx * 0.80, -0.56, 0.12])
        ax /= np.linalg.norm(ax)
        add.append(sdf.torus(np.array([sx * 0.29, -3.62, 3.27]) + ax * 0.036, 0.052, 0.019, axis=ax, k=0.015,
                             name="eyelid", bone="head"))
    if detail:
        add += brow_knobs()
        add += osteoderms()
        add += scar_ridge()
    # ---- legs
    for side in "LR":
        add += leg_parts(side)
        add += arm_parts(side)
    # ---- mouth: thin slit along the lip line + lens-shaped oral cavity
    sub.append(mouth_cavity())
    return add, sub


def mouth_cavity():
    """Thin slit along the lip line (open at the lips) + inner cavity (palate dome, tongue trough)."""
    hp = head_profiles()
    y_lo, y_hi = -4.60, MOUTH_CORNER_Y + 0.05
    half_gap = 0.018

    def fn(P):
        x, y, z = P[..., 0], P[..., 1], P[..., 2]
        zmid = mouth_z(np.clip(y, -4.6, -3.0))
        # inner width shrinks toward the back/front
        win = np.interp(y, [-4.6, -4.45, -4.2, -3.8, -3.45, -3.30], [0.05, 0.12, 0.19, 0.25, 0.25, 0.10])
        s = np.clip(np.abs(x) / np.maximum(win, 1e-3), 0, 1)
        dome = 0.11 * (1 - s ** 2) * np.interp(y, [-4.6, -4.4, -4.2, -3.6, -3.35], [0.0, 0.0, 0.7, 1.0, 0.5])
        trough = 0.07 * (1 - s ** 2) * np.interp(y, [-4.6, -4.4, -4.2, -3.6, -3.35], [0.0, 0.1, 0.7, 1.0, 0.6])
        upper = zmid + half_gap + dome
        lower = zmid - half_gap - trough
        dz = np.maximum(z - upper, lower - z)          # <0 inside the vertical band
        # band open to the outside at the lips: no x limit for the slit itself; cavity limited by win
        dy = np.maximum(y_lo - y, y - y_hi)
        return np.maximum(dz, dy)

    lo = np.array([-0.7, y_lo, 2.4])
    hi = np.array([0.7, y_hi, 3.3])
    return sdf.Prim(fn, lo, hi, name="mouth", k=0.012)


def brow_knobs():
    """Jagged keratin knobs on the brow ridges and the snout midline (front view shows a central crest)."""
    out = []
    rng = np.random.default_rng(7)
    for sx in (1, -1):
        for i, t in enumerate(np.linspace(0, 1, 5)):
            p = np.array([sx * (0.25 + 0.03 * t), -3.88 + 0.40 * t, 3.36 + 0.11 * t])
            h = 0.045 + 0.025 * math.sin(math.pi * t) + 0.012 * rng.random()
            out.append(oriented_ellipsoid(p + [sx * 0.015, 0, 0.03], [0, 0.3, 1], h, 0.035, 0.03, k=0.03,
                                          name="brow_knob", bone="head"))
        # horn-like tip at the rear-top of the ridge (front view)
        out.append(oriented_ellipsoid([sx * 0.30, -3.52, 3.47], [sx * 0.5, 0.3, 1], 0.07, 0.038, 0.038, k=0.04,
                                      name="brow_horn", bone="head"))
    # skull-roof rows of large knobby osteoderms (close-up: big knobs behind the brow toward the neck)
    for sx in (1, -1):
        for j, y in enumerate(np.linspace(-3.55, -3.05, 5)):
            z = np.interp(y, [-3.6, -3.3, -3.0], [3.53, 3.57, 3.52])
            sz = 0.055 + 0.012 * rng.random()
            out.append(oriented_ellipsoid([sx * (0.17 + 0.03 * j / 4), y, z], [0, 1, 0.2], sz * 1.3, sz, sz * 0.9,
                                          k=0.03, name="roof_knob", bone="head"))
    for i, y in enumerate(np.linspace(-4.30, -3.30, 9)):
        z = np.interp(y, [-4.4, -4.0, -3.6, -3.3], [3.16, 3.30, 3.48, 3.56])
        out.append(sdf.sphere([0, y, z + 0.005], 0.028 + 0.006 * (i % 2), k=0.025, name="snout_crest",
                              bone="head"))
    return out


def scar_ridge():
    """Healed scar over the LEFT eye (+X side): raised pale fibrous ridge (geometry + texture mask)."""
    pts = scar_points()
    out = sdf.chain(pts, [0.016, 0.02, 0.021, 0.02, 0.015], bones="head", k=0.012, name="scar")
    return out


def scar_points():
    # side-view scar line projected onto the left head surface (x from the skull half width)
    line = [(120, 155), (127, 167), (133, 178), (139, 189), (145, 200)]
    out = []
    for u, r in line:
        y, z = S(u, r)
        x = {155: 0.26, 167: 0.33, 178: 0.40, 189: 0.44, 200: 0.46}[r]
        out.append(np.array([x, y, z]))
    return out


def loft_surface(prof, y, phi, side=1):
    """Point and outward normal on the trunk loft at Y=y, angle phi (0 = mid-side, pi/2 = top)."""
    Y = prof["Y"]
    c = np.interp(y, Y, prof["zc"])
    h = np.interp(y, Y, prof["hz"])
    w = np.interp(y, Y, prof["hx"])
    e = np.interp(y, Y, prof["egg"])
    p = np.interp(y, Y, prof["p"])
    sp, cp = math.sin(phi), math.cos(phi)
    t = math.copysign(abs(sp) ** (2.0 / p), sp)
    sx = abs(cp) ** (2.0 / p)
    x = side * w * (1 - e * t) * sx
    z = c + h * t
    # numerical normal in the slice plane
    eps = 1e-3
    sp2, cp2 = math.sin(phi + eps), math.cos(phi + eps)
    t2 = math.copysign(abs(sp2) ** (2.0 / p), sp2)
    x2 = side * w * (1 - e * t2) * abs(cp2) ** (2.0 / p)
    z2 = c + h * t2
    tang = np.array([x2 - x, 0.0, z2 - z])
    n = np.array([tang[2], 0.0, -tang[0]]) * (1 if side > 0 else -1)
    if np.linalg.norm(n) < 1e-9:
        n = np.array([0, 0, 1.0])
    n /= np.linalg.norm(n)
    if n[2] < -0.5 and phi > 0.3:
        n = -n
    return np.array([x, y, z]), n


def osteoderms():
    """Small low knobby dorsal osteoderms: paired paramedian rows + scattered flank knobs + tail row."""
    prof = trunk_profile()
    rng = np.random.default_rng(11)
    out = []
    # paramedian rows neck -> tail base (angle from the top, as a lateral offset)
    y = -3.05
    while y < 1.6:
        spacing = np.interp(y, [-3.0, -1.0, 1.6], [0.17, 0.22, 0.22])
        for sx in (1, -1):
            off = np.interp(y, [-3.0, -1.0, 0.5, 1.6], [0.12, 0.17, 0.15, 0.09])
            jitter = rng.normal(0, 0.012)
            yy = y + jitter
            w = np.interp(yy, prof["Y"], prof["hx"])
            # find phi giving lateral offset ~off
            phis = np.linspace(math.pi / 2, 0.2, 60)
            xs = [abs(loft_surface(prof, yy, ph, sx)[0][0]) for ph in phis]
            ph = phis[int(np.argmin(np.abs(np.array(xs) - min(off, 0.8 * w))))]
            P, n = loft_surface(prof, yy, ph, sx)
            size = np.interp(y, [-3.0, -1.5, 0.5, 1.6], [0.07, 0.085, 0.08, 0.065]) * (0.85 + 0.3 * rng.random())
            out.append(oriented_ellipsoid(P + n * size * 0.15, [0, 1, 0.05], size * 1.5,
                                          size * 0.9, size * 0.85, up=n, k=0.03, name="osteoderm"))
        y += spacing
    # tail: central row
    y = 1.6
    while y < 4.9:
        P, n = loft_surface(prof, y, math.pi / 2, 1)
        size = np.interp(y, [1.6, 3.0, 4.9], [0.06, 0.045, 0.025])
        out.append(oriented_ellipsoid(P + n * size * 0.12, [0, 1, -0.1], size * 1.6, size * 0.9,
                                      size * 0.8, k=0.025, name="osteoderm_tail"))
        y += np.interp(y, [1.6, 4.9], [0.22, 0.16])
    # scattered smaller knobs on the upper flanks (neck -> mid tail)
    for i in range(190):
        y = rng.uniform(-3.0, 3.0)
        sx = 1 if rng.random() < 0.5 else -1
        ph = rng.uniform(0.25, 1.25)
        P, n = loft_surface(prof, y, ph, sx)
        size = rng.uniform(0.022, 0.04) * np.interp(y, [-3, 0, 3.0], [1.0, 1.0, 0.7])
        out.append(sdf.sphere(P + n * size * 0.2, size, k=0.02, name="flank_knob"))
    return out


def leg_parts(side):
    m = lambda p: _mir(p, side)  # noqa: E731
    sx = 1 if side == "L" else -1
    lp = leg_points(side)
    out = []
    b = lambda n: f"{n}_{side}"  # noqa: E731
    hip, knee, ankle, ball = m(HIP), m(KNEE), m(ANKLE), m(BALL)
    # huge thigh muscle (side view: mass from u~360..480, rows ~190..330)
    out.append(oriented_ellipsoid(m([0.63, -0.30, 1.86]), [0.06 * sx, -0.48, -0.88],
                                  0.68, 0.355, 0.46, k=0.16, name="thigh_mass", bone=b("thigh")))
    out.append(sdf.round_cone(hip + np.array([-0.06 * sx, 0.05, 0.0]), knee, 0.25, 0.24, k=0.14, name="femur",
                              bone=b("thigh")))
    # knee
    out.append(sdf.sphere(knee + np.array([0.02 * sx, -0.02, 0.0]), 0.25, k=0.10, name="knee", bone=b("shin")))
    # shin + calf (calf mass behind the upper shin)
    out.append(sdf.round_cone(knee, ankle, 0.25, 0.215, k=0.10, name="shin", bone=b("shin")))
    calf_c = knee + (ankle - knee) * 0.45 + np.array([0, 0.13, 0.0])
    out.append(oriented_ellipsoid(calf_c, ankle - knee, 0.47, 0.19, 0.18, k=0.12, name="calf", bone=b("shin")))
    # ankle bulge + metatarsus (massive, scutate; nearly vertical column in the drawing)
    out.append(sdf.sphere(ankle + [0, 0.03, 0], 0.215, k=0.08, name="ankle", bone=b("foot")))
    out.append(sdf.round_cone(ankle, ball + [0, 0.03, 0.0], 0.21, 0.20, k=0.08, name="metatarsus", bone=b("foot")))
    out.append(sdf.round_cone(ankle + [0, 0.07, -0.06], ball + [0, 0.24, 0.02], 0.17, 0.15, k=0.08,
                              name="metatarsus_rear", bone=b("foot")))
    out.append(sdf.round_cone(ball + [0, 0.04, -0.04], ball + [0, 0.25, -0.04], 0.145, 0.13, k=0.06,
                              name="heel_pad", bone=b("foot")))
    # toes: thick, padded, tapering; distal segment carries the claw (separate mesh)
    radii = {"toe2": (0.135, 0.105, 0.075), "toe3": (0.15, 0.115, 0.08), "toe4": (0.13, 0.10, 0.07)}
    for t in ("toe2", "toe3", "toe4"):
        a0, a1 = lp[f"{t}a_{side}"]
        b0, b1 = lp[f"{t}b_{side}"]
        r0, r1, r2 = radii[t]
        out.append(sdf.round_cone(a0 + [0, 0.05, 0.02], a1, r0, r1, k=0.05, name=t, bone=b(f"{t}a")))
        out.append(sdf.round_cone(a1, b1 + (b1 - b0) * -0.25, r1, r2, k=0.04, name=t + "_d", bone=b(f"{t}b")))
        # toe pads
        out.append(sdf.sphere(a1 + [0, 0, -0.03], r1 * 0.95, k=0.03, name=t + "_pad", bone=b(f"{t}a")))
    d0, d1 = lp[f"dewclaw_{side}"]
    out.append(sdf.round_cone(d0, d1, 0.06, 0.04, k=0.04, name="dewclaw", bone=b("dewclaw")))
    return out


def arm_parts(side):
    ap = arm_points(side)
    b = lambda n: f"{n}_{side}"  # noqa: E731
    out = []
    sh, el = ap[b("upperarm")]
    _el, wr = ap[b("forearm")]
    _wr, he = ap[b("hand")]
    out.append(sdf.sphere(sh, 0.21, k=0.14, name="shoulder", bone=b("upperarm")))
    out.append(sdf.round_cone(sh, el, 0.19, 0.14, k=0.10, name="upperarm", bone=b("upperarm")))
    out.append(sdf.round_cone(el, wr, 0.14, 0.10, k=0.07, name="forearm", bone=b("forearm")))
    out.append(sdf.round_cone(wr, he, 0.10, 0.085, k=0.04, name="hand", bone=b("hand")))
    for f, (r0, r1) in {"finger1": (0.058, 0.046), "finger2": (0.062, 0.05)}.items():
        a0, a1 = ap[b(f + "a")]
        b0, b1 = ap[b(f + "b")]
        out.append(sdf.round_cone(he + (a0 - he) * 0.2, a1, r0, r1, k=0.03, name=f, bone=b(f + "a")))
        out.append(sdf.round_cone(a1, b0 + (b1 - b0) * 0.35, r1, r1 * 0.85, k=0.02, name=f + "_d", bone=b(f + "b")))
    f0, f1 = ap[b("finger3")]
    out.append(sdf.round_cone(f0, f1, 0.035, 0.028, k=0.02, name="finger3", bone=b("finger3")))
    return out


def build_field(voxel=0.025, detail=True, hull_views=None, hull_k=0.03, lo=None, hi=None):
    lo = np.array([-1.35, -4.75, -0.02]) if lo is None else lo
    hi = np.array([1.35, 5.40, 3.80]) if hi is None else hi
    F = sdf.Field(lo, hi, voxel)
    add, sub = build_parts(detail=detail)
    for p in add:
        F.apply(p, op="union")
    for p in sub:
        F.apply(p, op="subtract")
    if hull_views:
        H = sdf.hull_sdf(F, hull_views, dilate_px=2.0)
        H = ndi.gaussian_filter(H, 1.2).astype(np.float32)
        F.intersect(H, k=hull_k)
    # floor clip (soles flat on Z=0)
    F.intersect(lambda P: -P[..., 2], k=0.0)
    return F, add, sub
