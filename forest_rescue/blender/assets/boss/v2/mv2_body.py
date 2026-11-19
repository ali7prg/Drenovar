"""Ancient Maw v2 anatomy: rest-pose skeleton landmarks + SDF parts (numpy only, no bpy).

World: Blender Z up, metres, creature faces -Y, feet on Z = 0, left side = +X.
Every landmark is read from art/03 (side view: Y = (u-445)/88.3, Z = (465-row)/88.3;
front view: X = (u-1029)/97.64, Z = (466-row)/97.64); see mv2_refs.

The rest (bind) pose is the side-view pose with the near (left) leg as drawn and symmetric legs/arms.
"""
import math
import os
import sys

import numpy as np
from scipy import ndimage as ndi
from scipy.interpolate import PchipInterpolator

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..")))
from frlib import sdf  # noqa: E402
import mv2_refs as R  # noqa: E402

PPM = R.SIDE_PPM


def SY(u):
    return (np.asarray(u, float) - R.SIDE_HIP_COL) / PPM


def SZ(row):
    return (R.SIDE_GROUND - np.asarray(row, float)) / PPM


def V(*a):
    return np.array(a, float)


# ------------------------------------------------------------------------------------ joints (left)
J = {
    # spine / head (x = 0)
    "pelvis": V(0, -0.15, 2.50),
    "spine_01": V(0, -0.70, 2.66),
    "spine_02": V(0, -1.28, 2.78),
    "spine_03": V(0, -1.86, 2.84),
    "neck_01": V(0, -2.32, 2.90),
    "neck_02": V(0, -2.68, 2.98),
    "neck_03": V(0, -2.98, 3.05),
    "head": V(0, -3.20, 3.10),
    "head_end": V(0, -4.50, 3.05),
    "jaw": V(0, -3.22, 2.96),
    "jaw_end": V(0, -4.48, 2.70),
    "eye_L": V(0.385, -3.63, 3.285),
    # left leg (near leg in the side view)
    "hip_L": V(0.58, -0.22, 2.42),
    "knee_L": V(0.73, -0.52, 1.45),
    "ankle_L": V(0.68, 0.10, 0.74),
    "ball_L": V(0.68, -0.15, 0.17),
    # left arm
    "shoulder_L": V(0.56, -1.86, 2.18),
    "elbow_L": V(0.66, -1.70, 1.84),
    "wrist_L": V(0.47, -1.93, 1.49),
    "hand_end_L": V(0.45, -2.00, 1.38),
}
# toe chains (left): [knuckle0 (MTP), knuckle1, claw base], claw direction
TOES_L = {
    "toe2": [V(0.57, -0.20, 0.15), V(0.43, -0.45, 0.11), V(0.33, -0.63, 0.085)],
    "toe3": [V(0.69, -0.22, 0.16), V(0.71, -0.48, 0.12), V(0.72, -0.71, 0.09)],
    "toe4": [V(0.81, -0.18, 0.15), V(0.98, -0.39, 0.11), V(1.10, -0.54, 0.085)],
}
HALLUX_L = [V(0.55, 0.12, 0.42), V(0.52, 0.17, 0.28)]
FINGERS_L = {   # [base (knuckle), mid, claw base]
    "finger1": [V(0.40, -1.98, 1.40), V(0.385, -2.03, 1.32), V(0.38, -2.05, 1.25)],
    "finger2": [V(0.47, -2.00, 1.39), V(0.475, -2.05, 1.31), V(0.48, -2.07, 1.24)],
    "finger3": [V(0.53, -1.96, 1.41), V(0.55, -2.00, 1.35), V(0.56, -2.01, 1.30)],
}


def mirror(p):
    p = np.array(p, float)
    p[..., 0] *= -1
    return p


def joint(name, side="L"):
    if name.endswith("_L") and side == "R":
        return mirror(J[name])
    return J[name].copy()


# ------------------------------------------------------------------------------------ side profiles
_CACHE = {}


def side_mask():
    if "side" not in _CACHE:
        _CACHE["side"] = R.side_mask(corrected=True)[1]
    return _CACHE["side"]


def front_mask():
    if "front" not in _CACHE:
        _CACHE["front"] = R.front_mask(corrected=True)[1]
    return _CACHE["front"]


def top_profile(u0, u1, open_w=0):
    """Top skin line (full-image rows) per column u in [u0, u1]; open_w>0 removes knobs (opening)."""
    m = side_mask()
    x0, y0 = R.SIDE_BOX[:2]
    us = np.arange(u0, u1 + 1)
    top = np.array([np.nonzero(m[:, u - x0])[0].min() + y0 if m[:, u - x0].any() else np.nan for u in us], float)
    good = ~np.isnan(top)
    top = np.interp(us, us[good], top[good])
    if open_w:
        # rows grow downward: knobs are local minima of `top`; a max-filter then min-filter (closing of
        # the row value) removes bumps narrower than open_w
        top = ndi.minimum_filter1d(ndi.maximum_filter1d(top, open_w, mode="nearest"), open_w, mode="nearest")
    return us, top


def first_run_bottom(u0, u1):
    m = side_mask()
    x0, y0 = R.SIDE_BOX[:2]
    us = np.arange(u0, u1 + 1)
    out = np.full(len(us), np.nan)
    for i, u in enumerate(us):
        col = m[:, u - x0]
        if not col.any():
            continue
        r0 = np.nonzero(col)[0].min()
        r1 = r0
        while r1 + 1 < len(col) and col[r1 + 1]:
            r1 += 1
        out[i] = r1 + y0
    return us, out


# belly/throat line (full-image side coords): measured where visible, interpolated behind limbs
BELLY_CTRL = [(150, 262.0), (176, 264.0), (200, 272.0), (218, 280.0), (232, 296.0), (250, 316.0),
              (275, 323.0), (300, 325.0), (330, 329.0), (360, 331.0), (390, 332.0), (420, 330.0),
              (450, 325.0), (480, 314.0), (505, 302.0), (525, 292.0), (545, 285.0)]
TRUNK_U0, TRUNK_U1 = 150, 914


def trunk_profile():
    if "trunk" in _CACHE:
        return _CACHE["trunk"]
    us, top_raw = top_profile(TRUNK_U0, TRUNK_U1)
    _, top_open = top_profile(TRUNK_U0, TRUNK_U1, open_w=17)
    skin = ndi.gaussian_filter1d(top_open, 4.0) + 1.0      # skin line just under the knob bases
    _, bot = first_run_bottom(TRUNK_U0, TRUNK_U1)
    bu = np.array([p[0] for p in BELLY_CTRL], float)
    bv = np.array([p[1] for p in BELLY_CTRL], float)
    belly = PchipInterpolator(bu, bv)(np.clip(us, bu[0], bu[-1]))
    bottom = np.where(us > bu[-1], bot, belly)
    bottom = ndi.gaussian_filter1d(bottom, 2.0)
    Y = SY(us)
    ztop, zbot = SZ(skin), SZ(bottom)
    # inside the head the loft is only the neck core: pull the top down under the skull
    pull = np.clip((200 - us) / 45.0, 0, 1)
    ztop = ztop - pull * 0.30
    # lateral half widths (anatomical profile, fitted against the front + rear views)
    cy = [-3.30, -3.00, -2.70, -2.40, -2.10, -1.80, -1.50, -1.15, -0.80, -0.45, -0.10, 0.30, 0.70, 1.10,
          1.60, 2.20, 2.90, 3.60, 4.30, 4.90, 5.30]
    cw = [0.40, 0.42, 0.45, 0.52, 0.60, 0.67, 0.72, 0.76, 0.78, 0.76, 0.70, 0.62, 0.55, 0.48,
          0.41, 0.34, 0.27, 0.20, 0.135, 0.075, 0.03]
    hx = PchipInterpolator(cy, cw)(np.clip(Y, cy[0], cy[-1]))
    # egg: >0 widest low (belly/ribcage), <0 widest high (neck top / tail base muscles)
    egg = np.interp(Y, [-3.3, -2.9, -2.6, -2.0, -1.4, -0.8, -0.2, 0.4, 1.2, 2.5, 5.3],
                    [0.05, 0.12, 0.18, 0.28, 0.36, 0.36, 0.26, 0.08, -0.08, -0.05, 0.0])
    pexp = np.interp(Y, [-3.3, -2.0, -0.5, 1.0, 3.0, 5.3], [2.2, 2.35, 2.45, 2.35, 2.2, 2.1])
    pup = np.interp(Y, [-3.3, -2.7, -2.2, -1.2, 0.0, 0.8, 2.0, 5.3], [2.0, 1.85, 1.65, 1.6, 1.7, 1.9, 2.0, 2.0])
    zc = 0.5 * (ztop + zbot)
    hz = 0.5 * (ztop - zbot)
    _CACHE["trunk"] = {"us": us, "Y": Y, "ztop": ztop, "zbot": zbot, "zc": zc, "hz": hz, "hx": hx,
                       "egg": egg, "p": pexp, "pup": pup, "top_raw": SZ(top_raw), "top_open": SZ(top_open)}
    return _CACHE["trunk"]


def loft(Y, zc, hz, hx, egg, pexp, name="loft", bone=None, cap_front=0.10, cap_back=0.06, k=0.0, pup=None):
    """Generalised cylinder along Y with super-elliptic slices (|x/w|^p + |t|^p = 1)."""
    Y = np.asarray(Y, float)
    n = len(Y)
    y0, y1 = Y[0], Y[-1]
    Yu = np.linspace(y0, y1, n)
    dy = (y1 - y0) / (n - 1)
    pup = pexp if pup is None else pup
    zc, hz, hx, egg, pexp, pup = [np.interp(Yu, Y, np.asarray(a, float)) for a in (zc, hz, hx, egg, pexp, pup)]
    hz, hx = hz.copy(), hx.copy()
    if cap_front > 0:
        t = np.clip((y0 + cap_front - Yu) / cap_front, 0, 1)
        f = np.sqrt(np.clip(1 - t * t, 0.0, 1.0))
        hz *= np.maximum(f, 0.03)
        hx *= np.maximum(f, 0.03)
    if cap_back > 0:
        t = np.clip((Yu - (y1 - cap_back)) / cap_back, 0, 1)
        f = np.sqrt(np.clip(1 - t * t, 0.0, 1.0))
        hz *= np.maximum(f, 0.03)
        hx *= np.maximum(f, 0.03)
    T = [zc, hz, hx, egg, pexp, pup]

    def fn(P):
        x, y, z = P[..., 0], P[..., 1], P[..., 2]
        fi = np.clip((y - y0) / dy, 0, n - 1.0001)
        i = np.floor(fi).astype(np.int64)
        f = fi - i
        c, h, w, e, pl, pu = [a[i] * (1 - f) + a[i + 1] * f for a in T]
        h = np.maximum(h, 1e-3)
        t = (z - c) / h
        pp = np.where(t > 0, pu, pl)
        wt = np.maximum(w * (1.0 - e * np.clip(t, -1, 1)), 1e-3)
        s = np.abs(x) / wt
        r = (s ** pp + np.abs(t) ** pp) ** (1.0 / pp)
        d = (r - 1.0) * np.minimum(wt, h)
        return np.maximum(d, np.maximum(y0 - y, y - y1))

    lo = np.array([-np.max(hx) * 1.4, y0, np.min(zc - hz) - 0.05])
    hi = np.array([np.max(hx) * 1.4, y1, np.max(zc + hz) + 0.05])
    return sdf.Prim(fn, lo, hi, bone=bone, name=name, k=k)


def oell(c, axis, ra, rs, ru, up=(0, 0, 1), **kw):
    """Ellipsoid with its first axis along `axis` (radii: along axis, side, up)."""
    a = np.asarray(axis, float)
    a /= np.linalg.norm(a)
    u = np.asarray(up, float)
    s = np.cross(a, u)
    if np.linalg.norm(s) < 1e-6:
        s = np.cross(a, [1.0, 0, 0])
    s /= np.linalg.norm(s)
    u2 = np.cross(s, a)
    Rm = np.stack([a, s, u2], 1)
    return sdf.ellipsoid(c, (ra, rs, ru), rot=Rm, **kw)


# ------------------------------------------------------------------------------------ head
HEAD_U0, HEAD_U1 = 44, 196


def head_profile():
    """Skull top / lip line / jaw bottom (metres) per Y from the side mask + close-up proportions."""
    if "head" in _CACHE:
        return _CACHE["head"]
    us, top = top_profile(HEAD_U0, HEAD_U1, open_w=9)
    top = ndi.gaussian_filter1d(top, 1.5)
    _, bot = first_run_bottom(HEAD_U0, HEAD_U1)
    bot = np.where(np.isnan(bot), np.nanmax(bot), bot)
    bot = ndi.gaussian_filter1d(bot, 1.2)
    # lip line (upper tooth row) measured in the side view; corner at u=142
    lip_u = [44, 50, 60, 75, 90, 105, 118, 130, 140, 150, 165, 182]
    lip_r = [207.0, 211.5, 213.0, 213.0, 212.0, 210.5, 208.5, 205.0, 200.0, 197.0, 196.0, 196.0]
    lip = np.interp(us, lip_u, lip_r)
    Y = SY(us)
    _CACHE["head"] = {"us": us, "Y": Y, "ztop": SZ(top), "zlip": SZ(lip), "zbot": SZ(bot)}
    return _CACHE["head"]


def head_widths(Y):
    """Half widths (upper jaw at the lip line, mandible) from the front view (+ close-up taper)."""
    Y = np.asarray(Y, float)
    wu = np.interp(Y, [-4.56, -4.50, -4.42, -4.28, -4.10, -3.90, -3.70, -3.50, -3.30, -3.10],
                   [0.10, 0.20, 0.26, 0.30, 0.33, 0.36, 0.40, 0.445, 0.47, 0.47])
    wl = np.maximum(wu - np.interp(Y, [-4.56, -4.3, -3.6, -3.1], [0.02, 0.04, 0.05, 0.02]), 0.05)
    return wu, wl


def head_part():
    hp = head_profile()
    Yh = hp["Y"]
    n = len(Yh)
    y0, y1 = Yh[0], Yh[-1]
    Yu = np.linspace(y0, y1, n)
    dy = (y1 - y0) / (n - 1)
    zt, zm, zb = [np.interp(Yu, Yh, hp[k]) for k in ("ztop", "zlip", "zbot")]
    wu, wl = head_widths(Yu)
    cap = 0.07
    t = np.clip((y0 + cap - Yu) / cap, 0, 1)
    f = np.sqrt(np.clip(1 - t * t, 0, 1))
    wu, wl = wu * np.maximum(f, 0.05), wl * np.maximum(f, 0.05)
    pu = np.interp(Yu, [-4.55, -4.2, -3.9, -3.1], [3.0, 3.0, 2.7, 2.4])
    pl = np.interp(Yu, [-4.55, -3.8, -3.1], [2.7, 2.8, 2.4])
    T = [zt, zm, zb, wu, wl, pu, pl]

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
        d = (r - 1.0) * np.minimum(w, np.where(up, hu, hl))
        return np.maximum(d, np.maximum(y0 - y, y - y1))

    lo = np.array([-0.6, y0, zb.min() - 0.05])
    hi = np.array([0.6, y1, zt.max() + 0.05])
    return sdf.Prim(fn, lo, hi, bone="head", name="head")


def lip_z(y):
    hp = head_profile()
    return np.interp(y, hp["Y"], hp["zlip"])


def head_detail_parts():
    add, sub = [], []
    for sx in (1, -1):
        # jaw adductor / cheek mass behind the eye, above the mouth corner
        add.append(oell([sx * 0.31, -3.33, 3.14], [0, -1, 0.1], 0.30, 0.15, 0.24, k=0.10, name="cheek",
                        bone="head"))
        # mandible angle (lower jaw rear, under the corner)
        add.append(oell([sx * 0.32, -3.40, 2.70], [0, -1, 0.2], 0.30, 0.15, 0.18, k=0.08, name="jaw_angle",
                        bone="jaw"))
        # orbit rim under the eye (cheekbone)
        add.append(sdf.round_cone([sx * 0.36, -3.86, 3.20], [sx * 0.43, -3.48, 3.22], 0.05, 0.06, k=0.05,
                                  name="cheekbone", bone="head"))
        # brow ridge: keratin ridge over the eye running back to the skull roof (jagged knobs added below)
        add.append(sdf.round_cone([sx * 0.30, -3.84, 3.38], [sx * 0.33, -3.45, 3.50], 0.055, 0.065, k=0.06,
                                  name="brow", bone="head"))
        # nostril boss + nostril pit
        add.append(oell([sx * 0.20, -4.36, 3.12], [0, -1, 0.3], 0.09, 0.06, 0.05, k=0.05, name="nasal",
                        bone="head"))
        sub.append(oell([sx * 0.235, -4.37, 3.115], [0.3 * sx, -1, 0.2], 0.045, 0.022, 0.028, k=0.02,
                        name="nostril", bone="head"))
        # eye socket (eyeball is a separate mesh of radius 0.052)
        sub.append(sdf.sphere([sx * 0.392, -3.63, 3.285], 0.050, k=0.012, name="eyesocket", bone="head"))
    return add, sub


def brow_knobs():
    """Modest jagged keratin knobs along each brow ridge (front view: tips at x=+-0.37, z=3.51)."""
    parts = []
    pts = [(-3.82, 3.39, 0.032), (-3.72, 3.43, 0.040), (-3.62, 3.465, 0.046), (-3.52, 3.49, 0.042),
           (-3.42, 3.50, 0.034)]
    for sx in (1, -1):
        for i, (y, z, r) in enumerate(pts):
            x = sx * (0.31 + 0.02 * i)
            parts.append(oell([x, y, z + r * 0.4], [0, -0.3, 1], r * 1.5, r * 0.9, r * 1.1, k=0.025,
                              name="browknob", bone="head"))
    return parts


def mouth_cut():
    """Thin mouth slit along the lip line + oral cavity carved into both jaws (separates the mandible)."""
    Ys = np.linspace(-4.50, -3.36, 60)
    zl = lip_z(Ys)
    wu, wl = head_widths(Ys)

    def fn(P):
        x, y, z = P[..., 0], P[..., 1], P[..., 2]
        yy = np.clip(y, Ys[0], Ys[-1])
        zlip = np.interp(yy, Ys, zl)
        w = np.interp(yy, Ys, wu)
        # slit: |z - zlip| < 0.012, inside the lips (|x| < w + margin), from the snout to the corner
        d_slit = np.maximum(np.abs(z - zlip) - 0.009, np.maximum(np.abs(x) - (w + 0.08), np.maximum(
            Ys[0] - 0.08 - y, y - Ys[-1])))
        # cavity: ellipsoid-ish volume inside, 0.09 m above and 0.14 m below the lip line, inset 0.07 m
        wi = np.maximum(w - 0.075, 0.03)
        tz = np.where(z > zlip, (z - zlip) / 0.085, (zlip - z) / 0.15)
        tx = np.abs(x) / wi
        ty_front = np.clip((Ys[0] + 0.10 - y) / 0.10, 0, None)
        ty_back = np.clip((y - (Ys[-1] - 0.05)) / 0.10, 0, None)
        r = np.sqrt(tx ** 2 + tz ** 2 + ty_front ** 2 + ty_back ** 2)
        d_cav = (r - 1.0) * 0.06
        return np.minimum(d_slit, d_cav)

    lo = np.array([-0.6, -4.62, 2.5])
    hi = np.array([0.6, -3.2, 3.2])
    return sdf.Prim(fn, lo, hi, name="mouth", bone="head", k=0.01, op="subtract")


SCAR_PTS = [V(0.335, -3.70, 3.52), V(0.385, -3.58, 3.42), V(0.425, -3.50, 3.24), V(0.445, -3.40, 3.06)]


def scar_ridge():
    """Raised healed scar over the LEFT eye: brow -> behind the eye -> cheek (side view u 128->145)."""
    return sdf.chain(SCAR_PTS, [0.014, 0.016, 0.015, 0.012], bones="head", k=0.012, name="scar")


# ------------------------------------------------------------------------------------ limbs
def leg_parts(side):
    m = (lambda p: mirror(p)) if side == "R" else (lambda p: np.array(p, float))
    s = 1 if side == "L" else -1
    hip, knee, ankle, ball = m(J["hip_L"]), m(J["knee_L"]), m(J["ankle_L"]), m(J["ball_L"])
    P = []
    th = f"thigh_{side}"
    sh = f"shin_{side}"
    ft = f"foot_{side}"
    # thigh: big muscular mass (side: Y -1.0..+0.45, Z 1.2..2.9; front: outer surface x=1.04)
    # thigh: widest LOW (front view: x 1.02-1.05 at z 1.45-1.8, only 0.76 at z 2.5); side: Y -1.0..+0.45
    P.append(oell(m([0.65, -0.36, 1.86]), knee - hip, 0.80, 0.33, 0.60, k=0.16, name="thigh", bone=th))
    P.append(oell(m([0.55, -0.18, 2.32]), [0, -0.3, -1.0], 0.40, 0.22, 0.45, k=0.16, name="thigh_top", bone=th))
    P.append(oell(m([0.70, -0.62, 1.70]), [0, -0.5, -1.0], 0.42, 0.30, 0.34, k=0.14, name="quad", bone=th))
    P.append(oell(m([0.56, 0.18, 2.05]), [0, 1.0, -0.35], 0.50, 0.31, 0.40, k=0.16, name="caudofem", bone=th))
    # knee (broad in the front view: outer edge x = 1.04 at z 1.3-1.5)
    P.append(oell(knee + m([0.02, -0.02, 0.0]), [1, 0, 0], 0.30, 0.25, 0.24, k=0.10, name="knee", bone=sh))
    # shin + calf (gastrocnemius at the back of the upper shin); side width 0.57 m at z = 1.05
    P.append(sdf.round_cone(knee, ankle, 0.24, 0.17, k=0.10, name="shin", bone=sh))
    P.append(oell(knee + (ankle - knee) * 0.40 + m([0.0, 0.12, 0.04]), ankle - knee, 0.48, 0.19, 0.20, k=0.10,
                  name="calf", bone=sh))
    P.append(oell(knee + (ankle - knee) * 0.5, [1, 0, 0], 0.21, 0.20, 0.30, k=0.08, name="shin_w", bone=sh))
    # ankle + metatarsus (broad: three metatarsals side by side; front half-width 0.23)
    P.append(oell(ankle + m([0, 0.05, 0]), [1, 0, 0], 0.22, 0.20, 0.17, k=0.06, name="ankle", bone=ft))
    P.append(oell((ankle + ball) * 0.5, ball - ankle, 0.40, 0.23, 0.16, up=(0, 1, 0), k=0.07, name="metatarsus",
                  bone=ft))
    P.append(sdf.round_cone(ankle, ball, 0.17, 0.14, k=0.06, name="metatarsus_core", bone=ft))
    # toes (II, III, IV): two phalanx segments + pads, claws are separate meshes
    for toe, chain in TOES_L.items():
        pts = [m(p) for p in chain]
        rr = {"toe2": (0.10, 0.085, 0.07), "toe3": (0.11, 0.09, 0.075), "toe4": (0.10, 0.08, 0.065)}[toe]
        bones = [f"{toe}a_{side}", f"{toe}b_{side}"]
        P.append(sdf.round_cone(ball + (pts[0] - ball) * 0.2, pts[0], 0.12, rr[0], k=0.05, name=toe, bone=ft))
        P.append(sdf.round_cone(pts[0], pts[1], rr[0], rr[1], k=0.035, name=toe, bone=bones[0]))
        P.append(sdf.round_cone(pts[1], pts[2], rr[1], rr[2], k=0.03, name=toe, bone=bones[1]))
        for q, r in ((pts[0], rr[0]), (pts[1], rr[1])):   # knuckle pads
            P.append(oell(q + V(0, 0, -0.02), pts[2] - pts[0], r * 1.05, r * 1.1, r * 0.85, k=0.03,
                          name="pad", bone=bones[0]))
    hx = [m(p) for p in HALLUX_L]
    P.append(sdf.round_cone(hx[0], hx[1], 0.055, 0.04, k=0.04, name="hallux", bone=f"hallux_{side}"))
    return P


def arm_parts(side):
    m = (lambda p: mirror(p)) if side == "R" else (lambda p: np.array(p, float))
    sh, el, wr, he = m(J["shoulder_L"]), m(J["elbow_L"]), m(J["wrist_L"]), m(J["hand_end_L"])
    P = []
    ua, fa, hd = f"upperarm_{side}", f"forearm_{side}", f"hand_{side}"
    P.append(oell(sh + m([0.02, 0.02, 0.05]), el - sh, 0.30, 0.17, 0.20, k=0.12, name="shoulder", bone=ua))
    P.append(sdf.round_cone(sh, el, 0.14, 0.11, k=0.08, name="upperarm", bone=ua))
    P.append(oell((sh + el) * 0.5 + m([0.02, -0.05, 0.0]), el - sh, 0.22, 0.12, 0.13, k=0.06, name="biceps",
                  bone=ua))
    P.append(sdf.round_cone(el, wr, 0.11, 0.08, k=0.06, name="forearm", bone=fa))
    P.append(oell(el + (wr - el) * 0.35, wr - el, 0.20, 0.10, 0.11, k=0.05, name="forearm_mus", bone=fa))
    P.append(sdf.round_cone(wr, he, 0.08, 0.07, k=0.04, name="hand", bone=hd))
    for f, chain in FINGERS_L.items():
        pts = [m(p) for p in chain]
        r0 = 0.040 if f != "finger3" else 0.032
        P.append(sdf.round_cone(he + (pts[0] - he) * 0.3, pts[0], 0.05, r0, k=0.03, name=f, bone=hd))
        P.append(sdf.round_cone(pts[0], pts[1], r0, r0 * 0.85, k=0.02, name=f, bone=f"{f}a_{side}"))
        P.append(sdf.round_cone(pts[1], pts[2], r0 * 0.85, r0 * 0.7, k=0.02, name=f, bone=f"{f}b_{side}"))
    return P


# ------------------------------------------------------------------------------------ osteoderms
def dorsal_knobs():
    """Low knobby osteoderms: midline row placed on the drawn silhouette bumps (side view), paired
    lateral rows on neck/back/tail (rear 3/4 view shows 2-3 rows per side on the back, 1 on the tail)."""
    prof = trunk_profile()
    us, top_raw = top_profile(TRUNK_U0, TRUNK_U1)
    _, top_open = top_profile(TRUNK_U0, TRUNK_U1, open_w=17)
    bump = top_open - top_raw            # px the knob rises above the skin line
    peaks = []
    for i in range(2, len(us) - 2):
        if bump[i] >= 2.0 and bump[i] == bump[max(0, i - 5):i + 6].max():
            if not peaks or us[i] - peaks[-1][0] >= 7:
                peaks.append((us[i], bump[i]))
    parts = []
    Yp = prof["Y"]
    for u, b in peaks:
        y = SY(u)
        if y < -3.0:
            continue
        zt = float(np.interp(y, Yp, prof["ztop"]))
        h = min(0.085, b / PPM + 0.015)
        w = np.clip(h * 1.5, 0.05, 0.11)
        parts.append(oell([0, y, zt + h * 0.35], [0, 1, 0], w * 1.25, w, h, k=0.03, name="osteoderm",
                          bone=None))
    # paired lateral rows (smaller), following the loft surface at angle phi from the top
    rng = np.random.default_rng(7)
    for row, (phi, ys, step, size) in enumerate([(0.30, (-2.6, 1.6), 0.20, 0.048), (0.60, (-1.9, 0.9), 0.24, 0.040),
                                                 (0.38, (1.6, 4.6), 0.21, 0.040)]):
        y = ys[0] + rng.uniform(0, step)
        while y < ys[1]:
            for sx in (1, -1):
                ang = phi + rng.uniform(-0.05, 0.05)
                p, nrm = trunk_surface(y, ang)
                p[0] *= sx
                nrm[0] *= sx
                s_ = size * rng.uniform(0.8, 1.15)
                c = p + nrm * s_ * 0.15
                parts.append(oell(c, [0, 1, 0], s_ * 1.3, s_ * 1.0, s_ * 0.75, up=nrm, k=0.025, name="osteoderm_lat",
                                  bone=None))
            y += step * rng.uniform(0.85, 1.15)
    return parts


def trunk_part():
    if "trunk_prim" not in _CACHE:
        prof = trunk_profile()
        _CACHE["trunk_prim"] = loft(prof["Y"], prof["zc"], prof["hz"], prof["hx"], prof["egg"], prof["p"],
                                    name="trunk", bone="spine_02", pup=prof["pup"])
    return _CACHE["trunk_prim"]


def trunk_surface(y, phi):
    """Point + outward normal on the trunk loft surface at station y, angle phi from the top (+x side)."""
    prof = trunk_profile()
    tr = trunk_part()
    zc = float(np.interp(y, prof["Y"], prof["zc"]))
    dirv = np.array([math.sin(phi), 0.0, math.cos(phi)])
    ts = np.linspace(0.0, 1.6, 321)
    P = np.array([0.0, y, zc])[None, :] + ts[:, None] * dirv[None, :]
    d = tr.fn(P)
    k = int(np.argmax(d > 0)) if np.any(d > 0) else len(ts) - 1
    p = P[max(k, 1)]
    e = 0.004
    g = np.array([(tr.fn((p + dv)[None])[0] - tr.fn((p - dv)[None])[0]) / (2 * e)
                  for dv in (np.array([e, 0, 0]), np.array([0, e, 0]), np.array([0, 0, e]))])
    return p, g / max(np.linalg.norm(g), 1e-9)


# ------------------------------------------------------------------------------------ assembly
def build_parts():
    prof = trunk_profile()
    add = [trunk_part()]
    add.append(head_part())
    ha, hs = head_detail_parts()
    add += ha
    add += brow_knobs()
    # throat/dewlap fullness under the neck (burnt-umber throat)
    for side in "LR":
        add += leg_parts(side)
        add += arm_parts(side)
    add += dorsal_knobs()
    add += scar_ridge()
    sub = hs + [mouth_cut()]
    return add, sub


def build_field(voxel=0.03, lo=(-1.35, -4.66, -0.02), hi=(1.35, 5.42, 3.75), hull_views=None, hull_k=0.02,
                parts=None):
    add, sub = parts if parts is not None else build_parts()
    F = sdf.Field(lo, hi, voxel)
    for p in add:
        F.apply(p)
    if hull_views:
        hs = sdf.hull_sdf(F, hull_views, dilate_px=1.0)
        F.intersect(hs, k=hull_k)
    for p in sub:
        F.apply(p, op="subtract")
    # ground: nothing below z = 0
    F.d = np.maximum(F.d, (-(F.axes[2]))[None, None, :].astype(np.float32))
    return F, add, sub
