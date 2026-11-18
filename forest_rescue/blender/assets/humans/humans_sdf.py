"""SDF building blocks for clothed human bodies (numpy; compatible with frlib.sdf.Field/Prim).

* `loft`      superelliptic sections interpolated along a segment (torso, limbs, sleeves,
                trouser legs, skirts, boot shafts); per-station asymmetric widths/depths/offsets.
* `head_parts` parametric skull/face (jaw, cheekbones, brow, nose, lips, chin, ears, sockets)
* `hand_parts` palm loft + finger capsules from humans_skel.finger_points
* `boot_parts` sole/heel/toe-box/shaft
* `hull2d`    signed distance of the front/back silhouette intersection, extruded along Y
* every Prim carries `cls` (surface material class) and `bone` (skin owner)
"""
import math

import numpy as np
from scipy import ndimage as ndi

from frlib import sdf as fsdf

Prim = fsdf.Prim


def _unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def tag(p, cls=None, bone=None, k=None, op=None, name=None, weight=None, geom=None):
    if geom is not None:
        p.geom = bool(geom)
    if cls is not None:
        p.cls = cls
    elif not hasattr(p, "cls"):
        p.cls = None
    if bone is not None:
        p.bone = bone
    if k is not None:
        p.k = float(k)
    if op is not None:
        p.op = op
    if name is not None:
        p.name = name
    if weight is not None:
        p.weight = weight
    return p


# --------------------------------------------------------------------------- loft

def _station_arrays(stations):
    """stations: list of dicts {t, w | (wl, wr), d | (df, db), n, o:(ox,oy)} sorted by t."""
    st = sorted(stations, key=lambda s: s["t"])
    t = np.array([s["t"] for s in st], float)

    def pair(s, key, default):
        v = s.get(key, default)
        if np.isscalar(v):
            return (float(v), float(v))
        return (float(v[0]), float(v[1]))

    W = np.array([pair(s, "w", 0.05) for s in st])
    D = np.array([pair(s, "d", 0.05) for s in st])
    N = np.array([pair(s, "n", 2.0) for s in st])     # (front, back) exponents
    O = np.array([pair(s, "o", 0.0) for s in st])
    return t, W, D, N, O


def _interp_fns(T, cols):
    """Shape-preserving (PCHIP) interpolators per column; linear if only 2 stations."""
    from scipy.interpolate import PchipInterpolator
    if len(T) < 3:
        return [lambda tc, c=c: np.interp(tc, T, c) for c in cols]
    return [PchipInterpolator(T, c, extrapolate=False) for c in cols]


def loft(a, b, stations, depth_axis=(0.0, 1.0, 0.0), cls=None, bone=None, k=0.0, name="loft",
         cap="flat", op="union", disp=None):
    """Superelliptic loft along segment a->b.

    Local frame: e = (b-a)/|b-a|, f = depth_axis orthogonalised (default world +Y = back),
    s = f x e (= +X for an upward segment).  Station keys: w = half width along s (or
    (left(+s), right(-s))), d = half depth along f (or (front(-f), back(+f))), n = exponent,
    o = (offset_s, offset_f).  Parameters are PCHIP-interpolated (no creases between stations).
    disp(P, t, x, y) -> metres of outward displacement (folds, quilting, bulges).
    """
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    e = b - a
    L = float(np.linalg.norm(e))
    e /= L
    f = np.asarray(depth_axis, float)
    f = _unit(f - np.dot(f, e) * e)
    s = np.cross(f, e)
    T, W, D, N, O = _station_arrays(stations)
    fns = _interp_fns(T, [W[:, 0], W[:, 1], D[:, 0], D[:, 1], N[:, 0], N[:, 1], O[:, 0], O[:, 1]])

    def fn(P):
        q = P - a
        tr = (q @ e) / L
        tc = np.clip(tr, T[0], T[-1])
        wl, wr, df, db, nf, nb, ox, oy = [g(tc) for g in fns]
        x = q @ s - ox
        y = q @ f - oy
        rx = np.where(x >= 0, wl, wr)
        ry = np.where(y >= 0, db, df)
        n = np.where(y >= 0, nb, nf)
        ax = np.abs(x) / rx
        ay = np.abs(y) / ry
        r = (ax ** n + ay ** n + 1e-12) ** (1.0 / n)
        gx = r ** (1 - n) * ax ** (n - 1) / rx
        gy = r ** (1 - n) * ay ** (n - 1) / ry
        g = np.sqrt(gx * gx + gy * gy)
        g = np.maximum(g, 1.0 / np.maximum(rx, ry))
        dside = (r - 1.0) / g
        if disp is not None:
            dside = dside - disp(P, tc, x, y)
        lo_cap = (T[0] - tr) * L
        hi_cap = (tr - T[-1]) * L
        dcap = np.maximum(lo_cap, hi_cap)
        return np.where((dside > 0) & (dcap > 0), np.sqrt(dside ** 2 + dcap ** 2), np.maximum(dside, dcap))

    rmax = float(max(W.max(), D.max()) + np.abs(O).max()) + 0.02
    pts = np.stack([a + e * L * T[0], a + e * L * T[-1]])
    lo = pts.min(0) - rmax
    hi = pts.max(0) + rmax
    p = tag(Prim(fn, lo, hi, bone=bone, name=name, k=k, op=op), cls=cls)
    p.frame = (a, e, f, s, L)
    return p


def vloft(z0, z1, stations_z, cls=None, bone=None, k=0.0, name="vloft", x=0.0, y=0.0, op="union", disp=None):
    """Vertical loft with stations given at absolute z: [(z, w, d, n, (ox, oy)) ...]."""
    st = []
    for item in stations_z:
        z, w, d = item[0], item[1], item[2]
        n = item[3] if len(item) > 3 else 2.0
        o = item[4] if len(item) > 4 else (0.0, 0.0)
        st.append(dict(t=(z - z0) / (z1 - z0), w=w, d=d, n=n, o=o))
    return loft((x, y, z0), (x, y, z1), st, cls=cls, bone=bone, k=k, name=name, op=op, disp=disp)


def limb(a, b, radii, cls=None, bone=None, k=0.0, name="limb", flat=1.0, n=2.0, depth_axis=(0, 1, 0),
         offsets=None, disp=None):
    """Limb loft: radii = [(t, r_side, r_depth) ...] or [(t, r)] (flat scales depth)."""
    st = []
    for i, item in enumerate(radii):
        if len(item) == 2:
            t, r = item
            w, d = r, r * flat
        else:
            t, w, d = item
        o = offsets[i] if offsets else (0.0, 0.0)
        st.append(dict(t=t, w=w, d=d, n=n, o=o))
    return loft(a, b, st, depth_axis=depth_axis, cls=cls, bone=bone, k=k, name=name, disp=disp)


# --------------------------------------------------------------------------- basic prims with tags

def sphere(c, r, **kw):
    cls = kw.pop("cls", None)
    return tag(fsdf.sphere(c, r, **kw), cls=cls)


def ellipsoid(c, radii, rot=None, **kw):
    cls = kw.pop("cls", None)
    return tag(fsdf.ellipsoid(c, radii, rot=rot, **kw), cls=cls)


def capsule(a, b, ra, rb=None, **kw):
    cls = kw.pop("cls", None)
    return tag(fsdf.round_cone(a, b, ra, ra if rb is None else rb, **kw), cls=cls)


def box(c, half, rot=None, rounding=0.0, **kw):
    cls = kw.pop("cls", None)
    return tag(fsdf.box(c, half, rot=rot, rounding=rounding, **kw), cls=cls)


def torus(c, R, r, axis=(0, 0, 1), **kw):
    cls = kw.pop("cls", None)
    return tag(fsdf.torus(c, R, r, axis=axis, **kw), cls=cls)


def frame_rot(x_axis, y_axis):
    """3x3 matrix whose columns are local axes (x, y, z=x*y) for frlib ellipsoid/box `rot`."""
    x = _unit(x_axis)
    y = _unit(np.asarray(y_axis, float) - np.dot(y_axis, x) * x)
    z = np.cross(x, y)
    return np.stack([x, y, z], axis=1)


# --------------------------------------------------------------------------- head

DEFAULT_FACE = dict(
    width=1.0,          # face (bizygomatic) width scale
    jaw=1.0,            # gonion width scale
    chin=1.0,           # chin prominence/size
    cheek=1.0,          # cheekbone prominence
    cheek_z=0.0,        # cheekbone height offset (m)
    brow=1.0,           # brow ridge prominence
    nose_len=1.0, nose_w=1.0, nose_proj=1.0, nose_tip=1.0, nose_hook=0.0, nose_bridge=1.0,
    lips=1.0, mouth_w=1.0,
    eye_sep=1.0, eye_depth=1.0,
    gaunt=0.0,          # hollow cheeks (0..1)
    fat=0.0,            # soft round face (0..1)
    ear=1.0,
    skull=1.0,
    face_y=None,        # world y of the cornea plane (default Head joint - 0.075*s)
    female=False,
)


def head_parts(J, L, face=None):
    """Ordered head/face primitives (op = union/subtract) in world space.

    Head frame: origin on the mid-sagittal plane at eye height in the cornea plane; +y back.
    The skull+face is ONE smooth vertical loft (egg sections, flatter face front), features
    (brow, sockets, eyes, lids, nose, lips, chin, jaw line, cheekbones, ears) are layered with
    small blend radii.  Average adult male proportions (crown-chin 0.235 m) x landmarks.
    """
    F = dict(DEFAULT_FACE)
    F.update(face or {})
    crown, chin, eye, mouth = L["crown"], L["chin"], L["eye"], L["mouth"]
    s = (crown - chin) / 0.235
    fem = F["female"]
    fy = F["face_y"] if F["face_y"] is not None else J["Head"][1] - 0.095 * s
    O = np.array([0.0, fy, eye])
    w = F["width"]
    up = (crown - eye) / s          # ~0.115-0.120
    dn = (eye - chin) / s           # ~0.115-0.120
    mz = (mouth - eye) / s          # ~ -0.075

    def P(x, y, z):
        return O + np.array([x, y, z]) * s

    out = []

    def U(p, bone="Head", cls="skin", k=0.010):
        out.append(tag(p, cls=cls, bone=bone, k=k * s, op="union"))

    def Sb(p, bone="Head", k=0.004):
        out.append(tag(p, cls=None, bone=bone, k=k * s, op="subtract"))

    sk = F["skull"]
    fat = F["fat"]
    jw = F["jaw"] * (0.92 if fem else 1.0)
    fw = 0.97 if fem else 1.0
    yc = 0.085
    # z (rel. eye line, head units), half width, front depth, back depth, n_front, n_back
    prof = [
        (up - 0.002, 0.020, 0.030, 0.030, 2.0, 2.0),
        (up - 0.012, 0.046 * sk, 0.060, 0.066, 2.0, 2.0),
        (0.085, 0.064 * sk, 0.082, 0.090, 2.1, 2.0),
        (0.055, 0.073 * sk * fw, 0.092, 0.100, 2.2, 2.0),
        (0.025, 0.075 * sk * fw, 0.094, 0.100, 2.3, 2.0),
        (0.000, 0.073 * w * fw, 0.090, 0.095, 2.5, 2.0),
        (-0.025, 0.071 * w * fw, 0.090 + 0.004 * fat, 0.086, 2.5, 2.1),
        (-0.048, 0.064 * w * fw + 0.004 * fat, 0.093, 0.072, 2.4, 2.1),
        (mz + 0.008, 0.058 * jw + 0.004 * fat, 0.099, 0.060, 2.4, 2.2),
        (mz - 0.006, 0.055 * jw + 0.004 * fat, 0.097, 0.054, 2.4, 2.2),
        (-dn + 0.024, 0.046 * jw + 0.003 * fat, 0.092 + 0.006 * (F["chin"] - 1), 0.050, 2.3, 2.2),
        (-dn + 0.010, 0.034 * jw, 0.090 + 0.008 * (F["chin"] - 1), 0.044, 2.2, 2.2),
        (-dn + 0.001, 0.016, 0.078, 0.034, 2.0, 2.0),
    ]
    st = [dict(t=(z + dn) / (up + dn), w=hw * s, d=(df * s, db * s), n=(nf, nb)) for z, hw, df, db, nf, nb in prof]
    U(loft(P(0, yc, -dn), P(0, yc, up), st, name="skull"), k=0.0)
    # brow ridge (soft), glabella
    br = F["brow"] * (0.6 if fem else 1.0)
    U(fsdf.round_cone(P(-0.036 * w, -0.0045, 0.0135), P(0.036 * w, -0.0045, 0.0135), 0.0062 * s * br, 0.0062 * s * br),
      k=0.010)
    # cheekbones
    for sx in (1, -1):
        U(fsdf.ellipsoid(P(sx * 0.046 * w, 0.017 - 0.004 * (F["cheek"] - 1), -0.022 + F["cheek_z"] / s),
                         np.array([0.020, 0.0105 * F["cheek"], 0.012]) * s), k=0.016)
    # jaw line definition (gonion -> chin) for squarer/heavier jaws
    for sx in (1, -1):
        U(fsdf.round_cone(P(sx * 0.050 * jw, 0.062, -0.078), P(sx * 0.022 * jw, 0.010, -dn + 0.016), 0.0072 * s,
                          0.0068 * s), bone="Jaw", k=0.020)
    # chin pad
    ch = F["chin"]
    U(fsdf.ellipsoid(P(0, -0.003 - 0.004 * (ch - 1), -dn + 0.016), np.array([0.017 * ch * (0.85 if fem else 1.0), 0.010, 0.013]) * s),
      bone="Jaw", k=0.010)
    # eye sockets (carved), eyeballs, lids
    es = 0.0315 * F["eye_sep"]
    for sx in (1, -1):
        Sb(fsdf.ellipsoid(P(sx * es, -0.004, 0.001), np.array([0.0185, 0.012, 0.0135]) * s * F["eye_depth"]), k=0.007)
    for sx in (1, -1):
        U(fsdf.sphere(P(sx * es, 0.0118, -0.0005), 0.0122 * s), cls="eye", k=0.0012)
        U(fsdf.round_cone(P(sx * (es - 0.0120), 0.0040, 0.0052), P(sx * (es + 0.0125), 0.0055, 0.0056),
                          0.0029 * s, 0.0026 * s), k=0.0035)
        U(fsdf.round_cone(P(sx * (es - 0.0105), 0.0045, -0.0088), P(sx * (es + 0.0115), 0.0062, -0.0082),
                          0.0021 * s, 0.0021 * s), k=0.0035)
    # nose
    nl, npj, nw = F["nose_len"], F["nose_proj"], F["nose_w"]
    tip = P(0, -0.0215 * npj, -0.043 * nl)
    U(fsdf.round_cone(P(0, -0.004, 0.006), tip + np.array([0, 0.005, 0.007]) * s - np.array([0, F["nose_hook"] * 0.003 * s, 0]),
                      0.0052 * s * F["nose_bridge"], 0.0074 * s * nw), k=0.007)
    U(fsdf.sphere(tip, 0.0092 * s * F["nose_tip"]), k=0.006)
    for sx in (1, -1):
        U(fsdf.sphere(tip + np.array([sx * 0.0100 * nw, 0.0110, -0.0035]) * s, 0.0061 * s * nw), k=0.005)
    for sx in (1, -1):
        Sb(fsdf.sphere(tip + np.array([sx * 0.0064 * nw, 0.0075, -0.0100]) * s, 0.0031 * s), k=0.002)
    # lips
    mw = 0.0235 * F["mouth_w"]
    lp = F["lips"] * (1.12 if fem else 1.0)
    U(fsdf.round_cone(P(-mw, -0.0095, mz + 0.0045), P(mw, -0.0095, mz + 0.0045), 0.0033 * s * lp, 0.0033 * s * lp),
      cls="lip", k=0.007)
    U(fsdf.sphere(P(0, -0.0118, mz + 0.0048), 0.0037 * s * lp), cls="lip", k=0.006)
    U(fsdf.round_cone(P(-mw * 0.80, -0.0080, mz - 0.0058), P(mw * 0.80, -0.0080, mz - 0.0058),
                      0.0042 * s * lp, 0.0042 * s * lp), bone="Jaw", cls="lip", k=0.007)
    Sb(fsdf.round_cone(P(-mw * 1.05, -0.0155, mz - 0.0006), P(mw * 1.05, -0.0155, mz - 0.0006), 0.0012 * s,
                       0.0012 * s), k=0.0015)
    if F["gaunt"] > 0:
        for sx in (1, -1):
            Sb(fsdf.sphere(P(sx * 0.050 * w, -0.004, -0.050), 0.012 * s * F["gaunt"]), k=0.016)
    # ears
    for sx in (1, -1):
        U(fsdf.ellipsoid(P(sx * 0.071 * sk * fw, 0.090, -0.020), np.array([0.009, 0.018, 0.028]) * s * F["ear"],
                         rot=(0.0, sx * 0.20, sx * 0.30)), k=0.005)
    lm = dict(origin=O, scale=s, eye_l=P(es, -0.0004, 0.0), eye_r=P(-es, -0.0004, 0.0), eye_rad=0.0122 * s,
              brow_z=eye + 0.016 * s, mouth=P(0, -0.012, mz), mouth_w=mw * s, nose_tip=tip,
              chin=P(0, -0.004, -dn + 0.012), face_y=fy, jaw_w=0.052 * jw * s, yc=fy + yc * s)
    return out, lm


# --------------------------------------------------------------------------- hands

def hand_parts(J, S_, side, fingers, scale, female=False, cls="skin", k=0.006):
    """Palm loft + finger capsules (bones: hand / thumb / index / middle(+ring,little))."""
    from humans_skel import hand_frame
    w = J[f"{S_}Hand"]
    kn = J[f"{S_}Hand_end"]
    d, t, n = hand_frame(w, kn, side)
    fs = 0.9 if female else 1.0
    P = []
    # palm: superelliptic loft wrist -> knuckles, wide along t, thin along n
    palm = loft(w - d * 0.012 * scale, w + d * 0.088 * scale,
                [dict(t=0.0, w=0.025 * scale * fs, d=0.014 * scale * fs, n=2.4),
                 dict(t=0.35, w=0.036 * scale * fs, d=(0.018 * scale * fs, 0.015 * scale * fs), n=2.6),
                 dict(t=0.85, w=0.041 * scale * fs, d=0.0135 * scale * fs, n=2.8),
                 dict(t=1.0, w=0.039 * scale * fs, d=0.011 * scale * fs, n=2.6)],
                depth_axis=n, cls=cls, bone=f"{S_}Hand", k=k, name=f"palm_{S_}")
    P.append(palm)
    bones = {"index": (f"{S_}IndexProximal", f"{S_}IndexIntermediate"),
             "middle": (f"{S_}MiddleProximal", f"{S_}MiddleIntermediate"),
             "ring": (f"{S_}MiddleProximal", f"{S_}MiddleIntermediate"),
             "little": (f"{S_}MiddleProximal", f"{S_}MiddleIntermediate"),
             "thumb": (f"{S_}ThumbMetacarpal", f"{S_}ThumbProximal")}
    palm.nohull = True
    for name, (pts, rad) in fingers.items():
        rad = rad * fs
        b0, b1 = bones[name]
        for i in range(len(pts) - 1):
            r0 = rad * (1.0 - 0.09 * i)
            r1 = rad * (1.0 - 0.09 * (i + 1))
            if name == "thumb" and i == 0:
                r0, r1 = rad * 1.25, rad * 1.05
            bone = b0 if i == 0 else b1
            P.append(tag(fsdf.round_cone(pts[i], pts[i + 1], r0, r1), cls=cls, bone=bone, k=0.003,
                         name=f"{name}{i}_{S_}"))
            P[-1].nohull = True
    # thenar / hypothenar padding
    P.append(tag(fsdf.ellipsoid(w + d * 0.035 * scale + t * 0.016 * scale + n * 0.010 * scale,
                                (0.020 * scale, 0.020 * scale, 0.020 * scale)), cls=cls, bone=f"{S_}ThumbMetacarpal",
                 k=0.010))
    P[-1].nohull = True
    return P


# --------------------------------------------------------------------------- boots / feet

def boot_parts(J, S_, side, L, top_z, cls="leather", shaft_r=(0.058, 0.050), toe_r=0.042, sole=0.024,
               bone_foot=None, k=0.012, shaft_flare=1.0, width=1.0, cuff=0.0, round_toe=1.0, height=1.0):
    """Leather boot: rounded toe box + heel + sole + shaft up to top_z around the shin."""
    s = L["crown"] / 1.75
    an = J[f"{S_}Foot"]
    ball = J[f"{S_}Toes"]
    tip = J[f"{S_}Toes_end"]
    heel = J[f"{S_}Heel"]
    fwd = _unit(np.array([tip[0] - an[0], tip[1] - an[1], 0.0]))
    sidev = np.cross(fwd, np.array([0, 0, 1.0])) * -1.0   # points to +x for left foot? (lateral/medial agnostic)
    P = []
    # foot body: loft heel -> toe tip (horizontal) with height profile
    back = heel + np.array([0, 0, 0.0])
    a = np.array([back[0], back[1], 0.0]) - fwd * 0.012 * s
    b = np.array([tip[0], tip[1], 0.0]) + fwd * 0.018 * s
    hh = height
    st = [dict(t=0.0, w=0.036 * s * width, d=0.050 * s * hh, n=2.2),
          dict(t=0.16, w=0.043 * s * width, d=0.078 * s * hh, n=2.4),
          dict(t=0.42, w=0.047 * s * width, d=0.070 * s * hh, n=2.5),
          dict(t=0.70, w=0.052 * s * width, d=0.054 * s * hh, n=2.4),
          dict(t=0.88, w=0.049 * s * width, d=0.046 * s * round_toe * hh, n=2.1),
          dict(t=1.0, w=0.034 * s * width, d=0.034 * s * round_toe * hh, n=2.0)]
    # depth axis = up (so 'd' is height), section centre raised so the sole sits on z=0
    foot = loft(a, b, st, depth_axis=(0, 0, 1.0), cls=cls, bone=bone_foot or f"{S_}Foot", k=0.0, name=f"boot_{S_}")
    def boot_fn(Pp, f=foot.fn):
        return np.maximum(f(Pp), -Pp[..., 2] - 0.0)
    P.append(tag(Prim(boot_fn, foot.lo, foot.hi, bone=f"{S_}Foot", name=f"boot_{S_}", k=k), cls=cls))
    P[-1].nohull = True
    # toes region assigned to the toe bone (front part)
    toe_c = np.array([tip[0], tip[1], 0.026 * s]) - fwd * 0.045 * s
    P.append(tag(fsdf.ellipsoid(toe_c, (0.040 * s * width, 0.050 * s, 0.024 * s * round_toe),
                                rot=np.arctan2(fwd[0], -fwd[1]) * np.array([0, 0, 1.0]) * -1),
                 cls=cls, bone=f"{S_}Toes", k=0.015))
    P[-1].nohull = True
    # heel block
    hc = np.array([heel[0], heel[1], 0.030 * s]) + fwd * 0.03 * s
    P.append(tag(fsdf.ellipsoid(hc, (0.034 * s * width, 0.038 * s, 0.030 * s)), cls=cls, bone=f"{S_}Foot", k=0.015))
    P[-1].nohull = True
    # sole slab (slightly wider, dark)
    sa = np.array([heel[0], heel[1], sole * 0.5]) - fwd * 0.010 * s
    sb = np.array([tip[0], tip[1], sole * 0.5]) + fwd * 0.016 * s

    def sole_fn(Pp, f=foot.fn):
        d = f(Pp) - 0.0035
        return np.maximum(np.maximum(d, Pp[..., 2] - sole), -Pp[..., 2])
    P.append(tag(Prim(sole_fn, foot.lo, foot.hi, bone=f"{S_}Foot", name=f"sole_{S_}", k=0.004), cls="sole"))
    P[-1].nohull = True
    # shaft around the lower leg: from ankle to top_z following the shin line
    kn = J[f"{S_}LowerLeg"]
    ax = an + np.array([0, -0.004 * s, 0.0])
    up = _unit(kn - an)
    h = top_z - an[2]
    st = [dict(t=0.0, w=shaft_r[0] * s * 0.92, d=shaft_r[0] * s * 1.05, n=2.0),
          dict(t=0.25, w=shaft_r[1] * s * 0.95, d=shaft_r[1] * s * 1.02, n=2.0),
          dict(t=1.0, w=shaft_r[1] * s * shaft_flare, d=shaft_r[1] * s * shaft_flare * 1.02, n=2.0)]
    shaft = loft(ax - up * 0.03 * s, ax + up * (h / max(up[2], 0.5)), st, cls=cls, bone=f"{S_}LowerLeg", k=k,
                 name=f"shaft_{S_}")
    P.append(shaft)
    if cuff > 0:
        c = ax + up * (h / max(up[2], 0.5))
        R_ = shaft_r[1] * s * shaft_flare + 0.004
        P.append(tag(fsdf.torus(c - up * 0.008 * s, R_, cuff, axis=up), cls=cls, bone=f"{S_}LowerLeg", k=0.006))
        # turned-down fold below the rim
        P.append(tag(loft(c - up * 0.055 * s, c - up * 0.008 * s,
                          [dict(t=0.0, w=R_ - 0.002, d=R_ - 0.002), dict(t=1.0, w=R_ + 0.004, d=R_ + 0.004)]),
                     cls=cls, bone=f"{S_}LowerLeg", k=0.004))
    return P


# --------------------------------------------------------------------------- silhouette hull

def smooth_sdf_2d(mask, ppm, up=4, blur_px=1.2, dilate_px=0.6):
    """Sub-pixel smooth signed distance (metres) of a binary mask: anti-alias (gaussian),
    upsample x`up`, threshold, EDT -> no pixel staircase on carved surfaces."""
    import cv2
    m = ndi.gaussian_filter(mask.astype(np.float32), blur_px)
    H, W = m.shape
    mu = cv2.resize(m, (W * up, H * up), interpolation=cv2.INTER_CUBIC)
    inside = mu > (0.5 - 0.25 * dilate_px)
    dpos = ndi.distance_transform_edt(~inside)
    dneg = ndi.distance_transform_edt(inside)
    sd = (dpos - dneg) / (ppm * up)
    return sd.astype(np.float32), up


def sample_sdf_2d(sd, up, u, v):
    import cv2
    uu = ((np.asarray(u, np.float32) + 0.5) * up - 0.5).ravel()
    vv = ((np.asarray(v, np.float32) + 0.5) * up - 0.5).ravel()
    shp = np.shape(u)
    n = uu.size
    cols = 4096
    rows = max(1, -(-n // cols))
    mx = np.zeros(rows * cols, np.float32)
    my = np.zeros(rows * cols, np.float32)
    mx[:n] = uu
    my[:n] = vv
    out = cv2.remap(sd, mx.reshape(rows, cols), my.reshape(rows, cols), cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_CONSTANT, borderValue=0.5)
    return out.ravel()[:n].reshape(shp)


def hull2d(field, views, dilate_px=0.6, blur_px=1.2):
    """Signed distance (metres) to the intersection of the views' silhouettes, extruded along
    each view direction (all our views look along +-Y).  Returns a full Field-shaped volume."""
    nx, ny, nz = field.n
    xs, ys, zs = field.axes
    X, Z = np.meshgrid(xs, zs, indexing="ij")
    P = np.stack([X, np.zeros_like(X), Z], -1).reshape(-1, 3)
    out = np.full(X.shape, -1e3, np.float32)
    for v in views:
        sd, up = smooth_sdf_2d(v.mask, v.ppm, blur_px=blur_px, dilate_px=dilate_px)
        u, vv, _ = v.project(P)
        samp = sample_sdf_2d(sd, up, u.reshape(X.shape), vv.reshape(X.shape))
        out = np.maximum(out, samp)
    return np.broadcast_to(out[:, None, :], (nx, ny, nz)).astype(np.float32)


# --------------------------------------------------------------------------- per-point owner class

def owner(parts, P, classes=True):
    """Index of the nearest (lowest SDF) union part for each point; returns (idx, dist)."""
    best = np.full(len(P), np.inf)
    idx = np.full(len(P), -1, int)
    for i, p in enumerate(parts):
        if getattr(p, "op", "union") != "union":
            continue
        lo, hi = p.lo - 0.05, p.hi + 0.05
        sel = np.all((P >= lo) & (P <= hi), axis=1)
        if not sel.any():
            continue
        d = p.fn(P[sel])
        cur = best[sel]
        better = d < cur
        ii = np.nonzero(sel)[0][better]
        best[ii] = d[better]
        idx[ii] = i
    return idx, best
