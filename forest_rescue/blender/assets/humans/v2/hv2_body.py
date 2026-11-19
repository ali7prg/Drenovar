"""Body of a v2 human: shared-skeleton joints from the painted landmarks, silhouette-fitted
SDF parts (torso stack, limb tubes, head template, boots) and the hair/beard field.

Every in-plane width comes from the consensus silhouette (hv2_fit.Refs); depth from the ratio
tables below (anatomical template, scaled per character by the painted widths)."""
import math

import numpy as np

import hv2_fit as F

# --------------------------------------------------------------------------- skeleton joints

SIDES = (("Left", "l", 1.0), ("Right", "r", -1.0))


def joints(C):
    """3-D joint positions (Blender world) from the 2-D landmarks + template depth."""
    L = C["L"]
    J = {}
    hz = 0.5 * (L["hip_l"][1] + L["hip_r"][1])
    nz = L["neck"]
    H = nz - hz
    J["Root"] = np.array([0.0, 0.0, 0.0])
    J["Hips"] = np.array([0.0, 0.0, hz])
    J["Spine"] = np.array([0.0, 0.012, hz + 0.20 * H])
    J["Chest"] = np.array([0.0, 0.022, hz + 0.44 * H])
    J["UpperChest"] = np.array([0.0, 0.024, hz + 0.68 * H])
    J["Neck"] = np.array([0.0, 0.018, nz])
    J["Head"] = np.array([0.0, 0.020, 0.5 * (L["mouth"] + L["chin"]) + 0.012])
    J["HeadTop"] = np.array([0.0, 0.010, L["crown"]])
    for S, s, sx in SIDES:
        sh = np.array([L[f"shoulder_{s}"][0], 0.004, L[f"shoulder_{s}"][1]])
        el = np.array([L[f"elbow_{s}"][0], 0.022, L[f"elbow_{s}"][1]])
        wr = np.array([L[f"wrist_{s}"][0], -0.004, L[f"wrist_{s}"][1]])
        J[f"{S}Shoulder"] = np.array([sx * 0.028, 0.004, sh[2] + 0.012])
        J[f"{S}UpperArm"] = sh
        J[f"{S}LowerArm"] = el
        J[f"{S}Hand"] = wr
        hp = np.array([L[f"hip_{s}"][0], -0.004, L[f"hip_{s}"][1]])
        kn = np.array([L[f"knee_{s}"][0], -0.018, L[f"knee_{s}"][1]])
        an = np.array([L[f"ankle_{s}"][0], 0.030, L[f"ankle_{s}"][1]])
        J[f"{S}UpperLeg"] = hp
        J[f"{S}LowerLeg"] = kn
        J[f"{S}Foot"] = an
        fl = L["foot_len"]
        yaw = math.radians(L["toe_out_deg"]) * sx
        fwd = np.array([math.sin(yaw), -math.cos(yaw), 0.0])
        heel = an + np.array([0, 0.062 * fl / 0.26, 0])
        ball = heel + fwd * (0.73 * fl)
        ball[2] = 0.028
        toe = heel + fwd * fl
        toe[2] = 0.018
        J[f"{S}Toes"] = ball
        J[f"{S}ToeTip"] = toe
        J[f"{S}Heel"] = np.array([heel[0], heel[1], 0.0])
        J[f"_{S}fwd"] = fwd
    return J


# --------------------------------------------------------------------------- torso

def _arm_axis_x(L, s, z):
    """x of the painted arm axis at height z (shoulder->elbow->wrist polyline)."""
    pts = [L[f"shoulder_{s}"], L[f"elbow_{s}"], L[f"wrist_{s}"]]
    zs = np.array([p[1] for p in pts])[::-1]
    xs = np.array([p[0] for p in pts])[::-1]
    return np.interp(z, zs, xs)


def torso_part(R, C, J):
    L = C["L"]
    B = C["build"]
    fem = C["female"]
    hz = J["Hips"][2]
    nz = L["neck"]
    shz = 0.5 * (L["shoulder_l"][1] + L["shoulder_r"][1])
    xsh = 0.5 * (L["shoulder_l"][0] - L["shoulder_r"][0])
    z_bot = hz - 0.115
    z_top = nz + 0.032
    zs = np.arange(z_bot, z_top + 1e-6, 0.005)
    # template half-widths (fractions of the shoulder-joint half span) by height
    stocky = B.get("stocky", 0.0)
    waist_f = (0.70 if fem else 0.76) + 0.10 * stocky
    hip_f = (0.98 if fem else 0.86) + 0.04 * stocky
    tz = [z_bot, hz, hz + 0.17, shz - 0.11, shz + 0.01, nz - 0.012, z_top]
    tw = [0.86 * hip_f, hip_f, waist_f, 0.90, 0.95, 0.62, 0.34 * (0.88 if fem else 1.0)]
    tmpl = np.interp(zs, tz, tw) * xsh
    al, ar = np.zeros_like(zs), np.zeros_like(zs)
    for i, z in enumerate(zs):
        run = R.central_run(z)
        runs = R.row_runs(z)
        for side, sgn in (("l", 1.0), ("r", -1.0)):
            meas = None
            if run is not None:
                meas = run[1] if sgn > 0 else -run[0]
            if z < shz:
                ax = abs(_arm_axis_x(L, side, z))
                # half-width of the painted arm at this row (its own run), template if merged
                aw = 0.050 if z > shz - 0.12 else 0.044
                for r0, r1 in runs:
                    if r0 - 0.002 <= sgn * ax <= r1 + 0.002 and not (run is not None and r0 == run[0] and r1 == run[1]):
                        aw = 0.5 * (r1 - r0)
                lim = ax - 0.92 * aw
            else:
                lim = xsh + 0.012
            t = tmpl[i]
            v = t if meas is None else meas
            v = min(v, lim)
            v = float(np.clip(v, 0.80 * t, 1.25 * t))
            if sgn > 0:
                al[i] = v
            else:
                ar[i] = v
    from scipy.ndimage import gaussian_filter1d
    al = gaussian_filter1d(al, 3, mode="nearest")
    ar = gaussian_filter1d(ar, 3, mode="nearest")
    cx = np.zeros_like(zs)
    # depth: ratio of the local half-width (template), front/back split, centre offsets
    f = np.clip((zs - z_bot) / (nz - z_bot), 0, 1.06)
    td = B.get("torso_depth", 1.0)
    ratio = np.interp(f, [0.0, 0.18, 0.40, 0.62, 0.80, 0.92, 1.0, 1.06],
                      [0.66, 0.70, 0.74 + 0.06 * stocky, 0.70, 0.64, 0.56, 0.62, 0.85]) * td
    a = 0.5 * (al + ar)
    depth = ratio * a
    belly = B.get("belly", 0.0)
    front = depth * np.interp(f, [0, 0.2, 0.4, 0.7, 1.0], [0.92, 1.0, 1.06, 1.02, 0.95]) \
        + belly * np.exp(-((f - 0.36) / 0.16) ** 2)
    back = depth * np.interp(f, [0, 0.12, 0.3, 0.6, 0.85, 1.0], [1.10, 1.12, 0.96, 1.02, 1.0, 0.95])
    if fem:
        front = front + 0.016 * np.exp(-((f - 0.70) / 0.09) ** 2)     # bust
        back = back + 0.010 * np.exp(-((f - 0.06) / 0.08) ** 2)       # hips/glutes
    cy = np.interp(f, [0, 0.3, 0.6, 1.0], [0.012, 0.008, 0.010, 0.012])
    pw = np.interp(f, [0, 0.5, 0.85, 1.0], [2.4, 2.4, 2.6, 2.1])
    part = F.stack(zs, cx, al, ar, cy, front, back, pw, label="body", k=0.0, name="torso")
    part.bone = None
    prof = dict(zs=zs, al=al, ar=ar, front=front, back=back, cy=cy)
    return part, prof


def torso_bone(z, J):
    order = [("Hips", J["Hips"][2] - 1), ("Spine", J["Spine"][2]), ("Chest", J["Chest"][2]),
             ("UpperChest", J["UpperChest"][2]), ("Neck", J["Neck"][2])]
    name = "Hips"
    for n, z0 in order:
        if z >= z0:
            name = n
    return name


def torso_bone_parts(prof, J):
    """Thin slab SDFs that only serve as weight owners for the torso stack, by height."""
    parts = []
    bounds = [("Hips", J["Hips"][2] - 0.20, J["Spine"][2]), ("Spine", J["Spine"][2], J["Chest"][2]),
              ("Chest", J["Chest"][2], J["UpperChest"][2]), ("UpperChest", J["UpperChest"][2], J["Neck"][2]),
              ("Neck", J["Neck"][2], J["Head"][2] + 0.02)]
    for name, z0, z1 in bounds:
        zc = 0.5 * (z0 + z1)
        half = 0.5 * (z1 - z0)

        def fn(P, zc=zc, half=half):
            r = np.sqrt(P[..., 0] ** 2 + (P[..., 1] - 0.01) ** 2)
            dz = np.abs(P[..., 2] - zc) - half
            return np.maximum(dz, 0) + np.maximum(r - 0.22, 0) * 0.3
        parts.append(F.Part(fn, [-0.3, -0.3, z0 - 0.05], [0.3, 0.3, z1 + 0.05], bone=name, label="body",
                            name=f"slab_{name}"))
    return parts


# --------------------------------------------------------------------------- limbs

ARM_T = ([0.0, 0.25, 0.6, 1.0], [0.056, 0.050, 0.046, 0.042])        # upper arm half-widths
FARM_T = ([0.0, 0.3, 0.7, 1.0], [0.044, 0.043, 0.034, 0.028])         # forearm
THIGH_T = ([0.0, 0.3, 0.7, 1.0], [0.090, 0.082, 0.068, 0.060])
SHIN_T = ([0.0, 0.25, 0.55, 0.85, 1.0], [0.058, 0.062, 0.058, 0.048, 0.044])


def limb_profile(R, A, B, tmpl, max_half, n=40, blocked=None, smooth=2.0):
    pr = R.profile((A[0], A[2]), (B[0], B[2]), n=n, max_half=max_half, medial_limit=blocked)
    ok = pr["ok"] & (pr["a"] > 0.012)
    a, k = F.fill_profile(pr["s"], pr["a"], ok, tmpl, smooth=smooth)
    c = np.where(ok, pr["c"], 0.0)
    from scipy.ndimage import gaussian_filter1d
    c = gaussian_filter1d(c, smooth, mode="nearest")
    return pr["s"], a, c, ok, k


def arm_parts(R, C, J, prof):
    parts = []
    L = C["L"]
    for S, s, sx in SIDES:
        sh, el, wr = J[f"{S}UpperArm"], J[f"{S}LowerArm"], J[f"{S}Hand"]

        def blocked(x, z, sx=sx):
            # points medial of the torso's lateral boundary belong to the torso
            zz = np.clip(z, prof["zs"][0], prof["zs"][-1])
            lat = np.interp(zz, prof["zs"], prof["al"] if sx > 0 else prof["ar"])
            return (sx * x) < lat - 0.004
        s1, a1, c1, ok1, k1 = limb_profile(R, sh, el, ARM_T, 0.085, blocked=blocked)
        s2, a2, c2, ok2, k2 = limb_profile(R, el, wr, FARM_T, 0.07, blocked=blocked)
        # the upper part of the upper arm is merged with the torso in the painting: template
        # deltoid scaled by the measured mid-arm width
        top = np.interp(s1, [0, 0.35], [1.0, 0.0])
        a1 = a1 * (1 - top) + top * (ARM_T[1][0] * k1)
        c1 = c1 * (1 - top)
        b1 = a1 * np.interp(s1, [0, 0.5, 1.0], [1.0, 1.02, 0.95])
        b2 = a2 * np.interp(s2, [0, 0.4, 1.0], [0.95, 0.88, 0.70])
        parts.append(F.tube(sh, el, s1, a1, b1, c1, bone=f"{S}UpperArm", label="body", k=0.012,
                            name=f"upperarm_{s}"))
        parts.append(F.tube(el, wr + (wr - el) / np.linalg.norm(wr - el) * 0.012, s2, a2, b2, c2,
                            bone=f"{S}LowerArm", label="body", k=0.014, name=f"forearm_{s}"))
        # deltoid cap + elbow
        dr = float(ARM_T[1][0] * k1)
        parts.append(F.ellipsoid(sh + np.array([sx * 0.010, 0.004, 0.004]), (dr * 1.02, dr * 1.0, dr * 1.05),
                                 bone=f"{S}UpperArm", label="body", k=0.03, name=f"deltoid_{s}"))
        er = 0.5 * (a1[-1] + a2[0])
        parts.append(F.sphere(el, er * 0.92, bone=f"{S}LowerArm", label="body", k=0.02, name=f"elbow_{s}"))
    return parts


def leg_parts(R, C, J, skirt_top=None):
    parts = []
    for S, s, sx in SIDES:
        hp, kn, an = J[f"{S}UpperLeg"], J[f"{S}LowerLeg"], J[f"{S}Foot"]
        top = hp + np.array([sx * 0.006, 0.0, 0.06])

        def blocked(x, z, sx=sx):
            return (sx * x) < 0.004          # the other leg / crotch gap
        s1, a1, c1, ok1, k1 = limb_profile(R, top, kn, THIGH_T, 0.13, blocked=blocked)
        s2, a2, c2, ok2, k2 = limb_profile(R, kn, an, SHIN_T, 0.11, blocked=blocked)
        fem = C["female"]
        b1 = a1 * np.interp(s1, [0, 0.5, 1.0], [1.15 if fem else 1.08, 1.04, 0.98])
        b2 = a2 * np.interp(s2, [0, 0.4, 1.0], [1.0, 1.04, 1.0])
        parts.append(F.tube(top, kn, s1, a1, b1, c1, bone=f"{S}UpperLeg", label="body", k=0.02,
                            name=f"thigh_{s}"))
        parts.append(F.tube(kn, an + np.array([0, 0, -0.03]), s2, a2, b2, c2, bone=f"{S}LowerLeg",
                            label="body", k=0.018, name=f"shin_{s}"))
        parts.append(F.sphere(kn, 0.5 * (a1[-1] + a2[0]) * 0.95, bone=f"{S}LowerLeg", label="body", k=0.02,
                              name=f"knee_{s}"))
    return parts


def boot_parts(R, C, J):
    """Boots: shaft continues the shin tube; foot = heel/arch/ball/toe ellipsoids; flat sole."""
    parts = []
    L = C["L"]
    for S, s, sx in SIDES:
        an, ball, toe, heel = J[f"{S}Foot"], J[f"{S}Toes"], J[f"{S}ToeTip"], J[f"{S}Heel"]
        fwd = J[f"_{S}fwd"]
        side = np.array([-fwd[1], fwd[0], 0.0]) * sx     # lateral
        # measured sole width (front view run near the ground)
        runs = R.row_runs(0.03)
        w = 0.105 * L["foot_len"] / 0.27
        for a, b in runs:
            if a - 0.01 <= an[0] <= b + 0.01:
                w = float(np.clip(b - a, 0.08, 0.15))
        hw = 0.5 * w
        fl = L["foot_len"]
        yaw = math.atan2(fwd[0], -fwd[1])
        # local axes (columns): x = lateral, y = along the foot (+-fwd), z = up
        rot = np.array([[math.cos(yaw), -math.sin(yaw), 0], [math.sin(yaw), math.cos(yaw), 0], [0, 0, 1.0]])
        ctr = lambda u: heel + fwd * (u * fl)  # noqa: E731
        k27 = fl / 0.27
        parts.append(F.ellipsoid(ctr(0.17) + np.array([0, 0, 0.052]), (hw * 0.84, 0.060 * k27, 0.056),
                                 rot=rot, bone=f"{S}Foot", label="boot", k=0.02, name=f"heel_{s}"))
        parts.append(F.ellipsoid(ctr(0.47) + np.array([0, 0, 0.056]), (hw * 0.94, 0.11 * k27, 0.055),
                                 rot=rot, bone=f"{S}Foot", label="boot", k=0.025, name=f"arch_{s}"))
        parts.append(F.ellipsoid(ctr(0.74) + np.array([0, 0, 0.040]), (hw * 1.0, 0.085 * k27, 0.044),
                                 rot=rot, bone=f"{S}Toes", label="boot", k=0.025, name=f"ball_{s}"))
        parts.append(F.ellipsoid(ctr(0.89) + np.array([0, 0, 0.034]), (hw * 0.90, 0.058 * k27, 0.036),
                                 rot=rot, bone=f"{S}Toes", label="boot", k=0.02, name=f"toe_{s}"))
        # sole slab (flat bottom, slight welt) + heel block
        parts.append(F.rbox(ctr(0.52) + np.array([0, 0, 0.012]), (hw * 1.02, 0.50 * fl, 0.012), rot=rot,
                            rounding=0.008, bone=f"{S}Foot", label="boot", k=0.012, name=f"sole_{s}"))
        # ankle / shaft bottom joins the shin
        parts.append(F.rcone(an + np.array([0, 0.004, -0.045]), an + np.array([0, 0.0, 0.06]), 0.052 * fl / 0.27,
                             0.048 * fl / 0.27, bone=f"{S}Foot", label="boot", k=0.02, name=f"ankle_{s}"))
    return parts


# --------------------------------------------------------------------------- head

def head_frame(C, J):
    L = C["L"]
    B = C["build"]
    sz = (L["crown"] - L["chin"]) / 0.238
    sx = sz * B.get("head_w", 1.0)
    o = np.array([0.0, 0.006, L["eye"]])
    return o, np.array([sx, sz, sz])


def head_parts(C, J):
    """Template head (face features) in the eye-level head frame, scaled to the painting."""
    o, S = head_frame(C, J)
    fem = C["female"]
    P = []

    def W(p):
        return o + np.asarray(p, float) * S

    def R_(r):
        return np.asarray(r, float) * S
    bone = "Head"
    jaw = 0.90 if fem else 1.0
    brow = 0.6 if fem else 1.0
    nose = 0.88 if fem else 1.0
    P.append(F.ellipsoid(W((0, 0.015, 0.025)), R_((0.076, 0.098, 0.093)), bone=bone, label="skin", k=0.0, name="cranium"))
    P.append(F.ellipsoid(W((0, 0.045, -0.012)), R_((0.064, 0.060, 0.074)), bone=bone, label="skin", k=0.02, name="occiput"))
    P.append(F.ellipsoid(W((0, -0.040, -0.030)), R_((0.064, 0.055, 0.084)), bone=bone, label="skin", k=0.02, name="face"))
    for sx in (1, -1):
        P.append(F.rcone(W((sx * 0.057 * jaw, 0.006, -0.050)), W((sx * 0.031 * jaw, -0.056, -0.106)), 0.020 * S[0] * jaw,
                         0.016 * S[0], bone=bone, label="skin", k=0.018, name="jaw"))
        P.append(F.ellipsoid(W((sx * 0.047, -0.056, -0.022)), R_((0.022, 0.024, 0.017)), bone=bone, label="skin",
                             k=0.016, name="cheekbone"))
        P.append(F.ellipsoid(W((sx * 0.077, 0.008, -0.018)), R_((0.011, 0.020, 0.030)), bone=bone, label="skin",
                             k=0.006, name="ear"))
    P.append(F.ellipsoid(W((0, -0.073, -0.110)), R_((0.025 * jaw, 0.020, 0.019)), bone=bone, label="skin", k=0.016, name="chin"))
    P.append(F.ellipsoid(W((0, -0.068, -0.068)), R_((0.036, 0.030, 0.034)), bone=bone, label="skin", k=0.016, name="muzzle"))
    P.append(F.rcone(W((-0.043, -0.079, 0.018)), W((0.043, -0.079, 0.018)), 0.011 * S[0] * brow, 0.011 * S[0] * brow,
                     bone=bone, label="skin", k=0.014, name="brow"))
    # eye sockets (subtract) + eyeballs (add back slightly recessed)
    for sx in (1, -1):
        P.append(F.Part(F.ellipsoid(W((sx * 0.032, -0.091, 0.0)), R_((0.018, 0.016, 0.012))).fn,
                        W((sx * 0.032, -0.091, 0.0)) - 0.03, W((sx * 0.032, -0.091, 0.0)) + 0.03,
                        bone=bone, label="skin", k=0.010, op="subtract", name="socket"))
    for sx in (1, -1):
        P.append(F.sphere(W((sx * 0.032, -0.077, 0.0)), 0.0122 * S[0], bone=bone, label="skin", k=0.003, name="eyeball"))
    P.append(F.rcone(W((0, -0.083, -0.002)), W((0, -0.104 * nose - 0.0, -0.043)), 0.008 * S[0] * nose, 0.0105 * S[0] * nose,
                     bone=bone, label="skin", k=0.008, name="nose"))
    for sx in (1, -1):
        P.append(F.sphere(W((sx * 0.0125 * nose, -0.092 * nose, -0.047)), 0.0095 * S[0] * nose, bone=bone, label="skin",
                          k=0.006, name="nostril"))
    P.append(F.ellipsoid(W((0, -0.090, -0.066)), R_((0.024, 0.010, 0.0075)), bone=bone, label="skin", k=0.006, name="lip_u"))
    P.append(F.ellipsoid(W((0, -0.087, -0.081)), R_((0.021, 0.010, 0.0075)), bone=bone, label="skin", k=0.006, name="lip_l"))
    # neck
    nz = C["L"]["neck"]
    nr = 0.056 if not fem else 0.048
    P.append(F.rcone(np.array([0, 0.016, nz - 0.05]), np.array([0, 0.018, o[2] - 0.075 * S[2]]), nr, nr * 0.9,
                     bone="Neck", label="skin", k=0.03, name="neck"))
    return P


def head_landmarks(C, J):
    """3-D face landmarks of the template (for the portrait camera solve)."""
    o, S = head_frame(C, J)
    nose = 0.88 if C["female"] else 1.0

    def W(p):
        return o + np.asarray(p, float) * S
    return dict(eye_r=W((-0.032, -0.088, 0.0)), eye_l=W((0.032, -0.088, 0.0)),
                nose=W((0, -0.112 * nose, -0.045)), mouth=W((0, -0.096, -0.073)),
                chin=W((0, -0.090, -0.122)), crown=W((0, 0.015, 0.118)),
                ear_l=W((0.085, 0.008, -0.018)), ear_r=W((-0.085, 0.008, -0.018)))


# --------------------------------------------------------------------------- hair & beard

def _noise3(P, freq, seed=0):
    from frlib import texproj
    return texproj.fbm(P, freq=freq, octaves=3, seed=seed)


HAIRLINES = {
    # |phi| (0 front .. pi back) -> hairline height in head units (eye level = 0)
    "default": ([0, 0.9, 1.35, 1.75, 2.4, math.pi], [0.062, 0.050, 0.012, -0.028, -0.070, -0.084]),
    "bun": ([0, 0.9, 1.35, 1.75, 2.4, math.pi], [0.066, 0.054, 0.020, -0.020, -0.066, -0.080]),
    "helmet": ([0, 1.4, 1.9, 2.4, math.pi], [0.30, 0.30, -0.02, -0.075, -0.090]),
}


def hair_sdf(C, J, P, d_body):
    """Signed distance of scalp hair + beard at world points P, from the body distance d_body
    (hair = body offset by a regional thickness; cut at the painted hairline / beard line)."""
    o, S = head_frame(C, J)
    B = C["build"]
    style = B.get("hair", "short")
    beard = B.get("beard")
    t_h = B.get("hair_thick", 0.015)
    q = (P - o) / S
    x, y, z = q[..., 0], q[..., 1], q[..., 2]
    phi = np.arctan2(x, -y)
    aphi = np.abs(phi)
    key = "bun" if style == "bun" else ("helmet" if style == "helmet" else "default")
    hp, hv = HAIRLINES[key]
    hl = np.interp(aphi, hp, hv)
    above = z - hl                                   # >0 above the hairline
    # thickness: fuller on top/back, curly noise
    vol = 1.0 + 0.35 * np.clip((z + 0.02) / 0.10, 0, 1) + 0.25 * np.clip((aphi - 1.2) / 1.5, 0, 1)
    if style in ("curly", "wavy", "tousled"):
        vol = vol * (0.80 + 0.45 * _noise3(P, 70.0, 3))
    # thin at the hairline (no visor), full volume 3-4 cm above it; thinner over the forehead
    taper = np.clip(above / 0.035, 0.0, 1.0)
    taper = taper * taper * (3 - 2 * taper)
    front = np.clip(1.0 - (aphi / 1.3), 0.0, 1.0)
    t = t_h * vol * (0.25 + 0.75 * taper) * (1.0 - 0.45 * front)
    d_scalp = np.maximum(d_body - t, -above * 0.9 * S[2])
    if style == "bun":
        c = o + np.array([0.0, 0.088, 0.035]) * S
        d_bun = np.linalg.norm(P - c, axis=-1) - 0.034 * S[0]
        d_scalp = smin_np(d_scalp, d_bun, 0.012)
    if style == "helmet":
        d_scalp = np.maximum(d_scalp, (z - (-0.02)) * S[2])      # only the nape below the helmet
    out = d_scalp
    if beard and beard != "stubble":
        base = {"full": 0.010, "full_grey": 0.009, "full_red": 0.011}.get(beard, 0.008)
        chin_bulk = {"full": 0.016, "full_grey": 0.014, "full_red": 0.016}.get(beard, 0.01)
        tb = base + chin_bulk * np.exp(-((z + 0.120) / 0.045) ** 2) * np.exp(-(x / 0.050) ** 2)
        tb = tb * (0.85 + 0.3 * _noise3(P, 90.0, 7))
        top = np.interp(aphi, [0, 0.30, 0.55, 1.0, 1.45, 1.75], [-0.050, -0.052, -0.040, -0.024, -0.016, -0.02])
        below = top - z
        tb = tb * (0.35 + 0.65 * np.clip(below / 0.02, 0, 1))
        front = 1.70 - aphi
        lips = np.sqrt((x / 0.021) ** 2 + ((z + 0.075) / 0.0105) ** 2) - 1.0
        allow = np.minimum(np.minimum(below, front * 0.05), np.where(aphi < 0.8, lips * 0.012, 1.0))
        d_beard = np.maximum(d_body - tb, -allow * S[2])
        out = smin_np(out, d_beard, 0.004)
    return out


def smin_np(a, b, k):
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25
