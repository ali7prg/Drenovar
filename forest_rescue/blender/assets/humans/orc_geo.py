"""Geometry of lf_orc_warden (numpy only; Blender objects are made by the build script).

Body: one SDF field (hv2_fit.Field) of authored parts - superellipse torso stack with a forward
hunch, muscle masses, limb tubes, an orc head template (heavy brow, deep sockets, flat broad nose,
under-bite jaw, swept pointed ears), thick neck, booted feet - meshed by marching cubes.
Hands: hv2_hand (five fingers, shared finger bones) at 1.42x.  Everything detachable is its own
mesh: shaggy fur mantle (offset-shell field with clump / strand noise), topknot + braided tail,
tusks, iron pauldron with spikes, crossed harness with ring + chest crystal, wide belt with buckle
and bone trinkets, layered kilt (cloth under-skirt, red flaps, leather tassets), forearm and shin
wraps, and the bone-and-iron staff with its cage finial and crystal (rigid on PropR).

Every piece: Piece(name, V, F, cls, weights, aux) - cls = texture class (orc_tex), weights =
per-vertex {bone: w} (or None = transferred from the skinned body), aux = per-vertex (u, v)
coordinates for painted patterns (wraps, straps, staff carving)."""
import math

import numpy as np

import hv2_drape as HD
import hv2_fit as F
import hv2_hand as HH
import spec_lf_orc_warden as SP
from frlib import sdf as fsdf

SIDES = (("Left", "l", 1.0), ("Right", "r", -1.0))


def unit(v):
    v = np.asarray(v, float)
    return v / max(np.linalg.norm(v), 1e-12)


def mirror(p, sx):
    p = np.asarray(p, float)
    return np.array([p[0] * sx, p[1], p[2]])


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, float) - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


class Piece:
    def __init__(self, name, V, F_, cls, weights=None, aux=None, solid=None, flat=False, kind="acc",
                 decimate=None, cls_faces=None):
        self.name, self.V, self.F, self.cls = name, np.asarray(V, float), [list(map(int, f)) for f in F_], cls
        self.weights, self.aux, self.solid, self.flat, self.kind = weights, aux, solid, flat, kind
        self.decimate = decimate
        self.cls_faces = cls_faces      # optional per-face class names
        self.inner_ref = None           # solidified sheets: point the hidden side faces (default: torso axis)


# --------------------------------------------------------------------------- skeleton

def joints():
    J = {"Root": np.zeros(3)}
    for k, v in SP.SPINE.items():
        J[k] = np.array(v, float)
    for S, s, sx in SIDES:
        for k, v in SP.ARM.items():
            J[f"{S}{k}"] = mirror(v, sx)
        for k, v in SP.LEG.items():
            J[f"{S}{k}"] = mirror(v, sx)
        an = J[f"{S}Foot"]
        fl = SP.FOOT["length"]
        yaw = math.radians(SP.FOOT["toe_out_deg"]) * sx
        fwd = np.array([math.sin(yaw), -math.cos(yaw), 0.0])
        heel = an + np.array([0.0, SP.FOOT["heel_back"], 0.0])
        heel[2] = 0.0
        ball = heel + fwd * (0.72 * fl)
        ball[2] = 0.036
        toe = heel + fwd * fl
        toe[2] = 0.024
        J[f"{S}Toes"] = ball
        J[f"{S}ToeTip"] = toe
        J[f"{S}Heel"] = heel
        J[f"_{S}fwd"] = fwd
    return J


def head_frame():
    return np.array(SP.HEAD["origin"], float), float(SP.HEAD["scale"])


def H(p):
    o, s = head_frame()
    return o + np.asarray(p, float) * s


# --------------------------------------------------------------------------- body parts

def _part(prim, bone, label, k, op="union", name=""):
    return F.Part(prim.fn, prim.lo, prim.hi, bone=bone, label=label, k=k, op=op, name=name)


def torso_part():
    from scipy.interpolate import PchipInterpolator
    rows = np.array(SP.TORSO, float)
    zs = np.arange(rows[0, 0], rows[-1, 0] + 1e-6, 0.004)
    hw, fr, bk, cy, pw = (PchipInterpolator(rows[:, 0], rows[:, i])(zs) for i in range(1, 6))
    p = F.stack(zs, np.zeros_like(zs), hw, hw, cy, fr, bk, pw, label="skin", k=0.0, name="torso")
    p.bone = None
    prof = dict(zs=zs, hw=hw, front=fr, back=bk, cy=cy)
    return p, prof


def prof_at(prof, z, key):
    return float(np.interp(z, prof["zs"], prof[key]))


def limb(A, B, table, bone, k, name, extend=0.0):
    A, B = np.asarray(A, float), np.asarray(B, float)
    if extend:
        B = B + unit(B - A) * extend
    s = [r[0] for r in table]
    a = [r[1] for r in table]
    b = [r[2] for r in table]
    return F.tube(A, B, s, a, b, bone=bone, label="skin", k=k, name=name)


def head_parts():
    """Orc head in the eye-level head frame (metres, scaled by HEAD.scale)."""
    o, s = head_frame()
    P = []
    hb = "Head"

    def E(c, r, label="skin", k=0.02, op="union", name="", bone=hb):
        P.append(_part(fsdf.ellipsoid(H(c), np.asarray(r) * s), bone, label, k, op, name))

    def C(a, b, ra, rb, label="skin", k=0.02, name="", bone=hb):
        P.append(_part(fsdf.round_cone(H(a), H(b), ra * s, rb * s), bone, label, k, "union", name))

    E((0, 0.045, 0.045), (0.100, 0.118, 0.112), k=0.0, name="cranium")
    E((0, 0.080, -0.010), (0.088, 0.080, 0.088), k=0.03, name="occiput")
    E((0, -0.040, 0.048), (0.086, 0.062, 0.066), k=0.03, name="forehead")
    # heavy brow ridge + glabella
    C((-0.070, -0.101, 0.021), (0.070, -0.101, 0.021), 0.025, 0.025, k=0.016, name="brow")
    E((0, -0.108, 0.010), (0.024, 0.020, 0.022), k=0.018, name="glabella")
    for sx in (1, -1):
        E((sx * 0.062, -0.090, 0.030), (0.030, 0.020, 0.018), k=0.02, name="brow_out")
        E((sx * 0.066, -0.074, -0.030), (0.034, 0.030, 0.026), k=0.022, name="cheekbone")
        # massive jaw from below the ear to the chin
        C((sx * 0.084, 0.004, -0.052), (sx * 0.050, -0.104, -0.136), 0.038, 0.033, k=0.026, name="jaw")
    E((0, -0.084, -0.064), (0.072, 0.066, 0.062), k=0.03, name="muzzle")
    E((0, -0.116, -0.076), (0.058, 0.040, 0.034), k=0.02, name="maxilla")
    E((0, -0.124, -0.140), (0.062, 0.043, 0.038), k=0.024, name="chin")
    for sx in (1, -1):
        E((sx * 0.072, -0.082, -0.098), (0.030, 0.032, 0.036), k=0.03, name="jowl")
    # lips: heavy protruding lower lip (under-bite), thinner upper lip
    E((0, -0.150, -0.113), (0.050, 0.021, 0.015), k=0.012, name="lip_l")
    E((0, -0.146, -0.089), (0.044, 0.016, 0.012), k=0.010, name="lip_u")
    # flat broad nose: short low bridge, wide tip and nostril wings
    C((0, -0.116, 0.000), (0, -0.142, -0.040), 0.012, 0.018, k=0.012, name="nose_bridge")
    E((0, -0.146, -0.046), (0.026, 0.019, 0.019), k=0.012, name="nose_tip")
    for sx in (1, -1):
        E((sx * 0.025, -0.137, -0.054), (0.016, 0.014, 0.013), k=0.010, name="nostril")
    # deep-set eye sockets (subtract) and small eyes
    for sx in (1, -1):
        prim = fsdf.ellipsoid(H((sx * 0.040, -0.118, -0.004)), np.array((0.022, 0.022, 0.0155)) * s)
        P.append(F.Part(prim.fn, prim.lo - 0.02, prim.hi + 0.02, bone=hb, label="skin", k=0.008, op="subtract",
                        name="socket"))
    for sx in (1, -1):
        E((sx * 0.040, -0.101, -0.004), (0.0100, 0.0095, 0.0092), label="eye", k=0.003, name="eyeball")
    for sx in (1, -1):
        prim = fsdf.ellipsoid(H((sx * 0.019, -0.150, -0.065)), np.array((0.0050, 0.0060, 0.0042)) * s)
        P.append(F.Part(prim.fn, prim.lo - 0.01, prim.hi + 0.01, bone=hb, label="skin", k=0.004, op="subtract",
                        name="nostril_hole"))
    # swept pointed ears (flattened round cones)
    for sx in (1, -1):
        a = H((sx * 0.092, 0.012, -0.022))
        b = H((sx * 0.205, 0.092, 0.072))
        up = unit((sx * 0.78, -0.52, 0.34))
        ear = fsdf.flat_capsule(a, b, 0.036 * s, 0.004 * s, 0.27, up=up)
        P.append(_part(ear, hb, "skin", 0.012, name="ear"))
        lobe = fsdf.ellipsoid(H((sx * 0.094, 0.006, -0.040)), np.array((0.012, 0.014, 0.020)) * s)
        P.append(_part(lobe, hb, "skin", 0.012, name="earlobe"))
    # thick neck, merging into the traps
    neck = fsdf.round_cone(np.array([0.0, 0.030, 1.735]), np.array([0.0, -0.050, 1.950]), 0.118, 0.096)
    P.append(_part(neck, "Neck", "skin", 0.05, name="neck"))
    throat = fsdf.round_cone(np.array([0.0, -0.060, 1.800]), H((0, -0.060, -0.150)), 0.070, 0.050)
    P.append(_part(throat, "Neck", "skin", 0.05, name="throat"))
    return P


def body_parts(J, prof):
    P = []
    # muscle masses on the torso stack
    zc = 1.555
    for S, s, sx in SIDES:
        fy = prof_at(prof, zc, "cy") - prof_at(prof, zc, "front")
        P.append(_part(fsdf.ellipsoid((sx * 0.140, fy + 0.058, zc), (0.128, 0.062, 0.088)), "UpperChest", "skin",
                       0.05, name="pec"))
        P.append(_part(fsdf.round_cone((sx * 0.050, 0.035, 1.865), (sx * 0.250, 0.030, 1.770), 0.072, 0.060),
                       "UpperChest", "skin", 0.06, name="trap"))
        P.append(_part(fsdf.ellipsoid((sx * 0.205, 0.130, 1.500), (0.120, 0.090, 0.180)), "Chest", "skin", 0.06,
                       name="lat"))
        P.append(_part(fsdf.ellipsoid((sx * 0.115, 0.125, 0.985), (0.122, 0.090, 0.115)), "Hips", "skin", 0.05,
                       name="glute"))
    # arms
    for S, s, sx in SIDES:
        sh, el, wr = J[f"{S}UpperArm"], J[f"{S}LowerArm"], J[f"{S}Hand"]
        P.append(limb(sh, el, SP.UPPER_ARM, f"{S}UpperArm", 0.02, f"upperarm_{s}"))
        P.append(_part(fsdf.ellipsoid(sh + np.array([sx * 0.024, 0.0, 0.016]), (0.114, 0.110, 0.118)),
                       f"{S}UpperArm", "skin", 0.045, name=f"deltoid_{s}"))
        P.append(_part(fsdf.ellipsoid(sh + (el - sh) * 0.45 + np.array([0.0, -0.035, 0.0]), (0.070, 0.060, 0.110)),
                       f"{S}UpperArm", "skin", 0.04, name=f"bicep_{s}"))
        P.append(_part(fsdf.sphere(el, 0.066), f"{S}LowerArm", "skin", 0.03, name=f"elbow_{s}"))
        P.append(limb(el, wr, SP.FOREARM, f"{S}LowerArm", 0.02, f"forearm_{s}", extend=0.014))
    # legs
    for S, s, sx in SIDES:
        hp, kn, an = J[f"{S}UpperLeg"], J[f"{S}LowerLeg"], J[f"{S}Foot"]
        top = hp + np.array([sx * 0.006, 0.0, 0.07])
        P.append(limb(top, kn, SP.THIGH, f"{S}UpperLeg", 0.03, f"thigh_{s}"))
        P.append(_part(fsdf.sphere(kn + np.array([0, -0.01, 0]), 0.088), f"{S}LowerLeg", "skin", 0.03, name=f"knee_{s}"))
        P.append(limb(kn, an + np.array([0.0, 0.0, -0.03]), SP.SHIN, f"{S}LowerLeg", 0.025, f"shin_{s}"))
    P += boot_parts(J)
    return P


def boot_parts(J):
    P = []
    fl = SP.FOOT["length"]
    hw = SP.FOOT["width"] * 0.5
    k = fl / 0.27
    for S, s, sx in SIDES:
        an, heel = J[f"{S}Foot"], J[f"{S}Heel"]
        fwd = J[f"_{S}fwd"]
        yaw = math.atan2(fwd[0], -fwd[1])
        rot = np.array([[math.cos(yaw), -math.sin(yaw), 0], [math.sin(yaw), math.cos(yaw), 0], [0, 0, 1.0]])

        def ctr(u):
            return heel + fwd * (u * fl)
        P.append(_part(fsdf.ellipsoid(ctr(0.16) + [0, 0, 0.060], (hw * 0.84, 0.060 * k, 0.064), rot=rot),
                       f"{S}Foot", "boot", 0.02, name=f"heel_{s}"))
        P.append(_part(fsdf.ellipsoid(ctr(0.46) + [0, 0, 0.066], (hw * 0.95, 0.115 * k, 0.064), rot=rot),
                       f"{S}Foot", "boot", 0.025, name=f"arch_{s}"))
        P.append(_part(fsdf.ellipsoid(ctr(0.74) + [0, 0, 0.046], (hw * 1.0, 0.085 * k, 0.050), rot=rot),
                       f"{S}Toes", "boot", 0.025, name=f"ball_{s}"))
        P.append(_part(fsdf.ellipsoid(ctr(0.89) + [0, 0, 0.038], (hw * 0.88, 0.058 * k, 0.040), rot=rot),
                       f"{S}Toes", "boot", 0.02, name=f"toe_{s}"))
        P.append(_part(fsdf.box(ctr(0.52) + [0, 0, 0.015], (hw * 1.04, 0.50 * fl, 0.015), rot=rot, rounding=0.010),
                       f"{S}Foot", "boot", 0.012, name=f"sole_{s}"))
        P.append(_part(fsdf.round_cone(an + [0, 0.006, -0.05], an + [0, 0.0, 0.07], 0.070, 0.066),
                       f"{S}Foot", "boot", 0.02, name=f"ankle_{s}"))
        P.append(_part(fsdf.round_cone(an + [0, 0.0, 0.05], an + [0, -0.012, 0.205], 0.075, 0.078),
                       f"{S}LowerLeg", "boot", 0.02, name=f"shaft_{s}"))
    return P


def body_field(J, voxel):
    torso, prof = torso_part()
    parts = [torso] + body_parts(J, prof) + head_parts()
    lo = (-0.66, -0.36, -0.01)
    hi = (0.66, 0.34, 2.215)
    fld = F.Field(lo, hi, voxel)
    for p in parts:
        fld.apply(p)
    fld.clip_ground(0.0, k=0.002)
    return fld, parts, prof


def support_field(J, prof):
    """Torso + legs + boots + neck (no arms / head) for garment cross-sections."""
    torso, _ = torso_part()
    parts = [torso] + [p for p in body_parts(J, prof) if not p.name.startswith(("upperarm", "deltoid", "bicep",
                                                                                   "elbow", "forearm"))]
    fld = F.Field((-0.55, -0.36, -0.01), (0.55, 0.34, 1.95), 0.006)
    for p in parts:
        fld.apply(p)
    return fld


# --------------------------------------------------------------------------- weights

def body_weights(verts, parts, J, falloff=0.030):
    """hv2_rig.body_weights with orc-sized blend radii."""
    names, dists = [], []
    torso = None
    for p in parts:
        if p.name == "torso":
            torso = p
            continue
        if p.bone is None or p.op == "subtract":
            continue
        lo, hi = p.lo - 0.1, p.hi + 0.1
        d = np.full(len(verts), 9.0)
        sel = np.all((verts >= lo) & (verts <= hi), axis=1)
        if sel.any():
            d[sel] = p.fn(verts[sel])
        dists.append(d)
        names.append(p.bone)
    dt = torso.fn(verts)
    D = np.stack(dists, 1)
    dmin = np.minimum(D.min(1), dt)
    W = {}
    for j, n in enumerate(names):
        w = np.exp(-np.maximum(D[:, j] - dmin, 0) / falloff)
        W[n] = np.maximum(W.get(n, 0), w)
    wt = np.exp(-np.maximum(dt - dmin, 0) / falloff)
    sp = [("Hips", J["Hips"][2] - 0.05), ("Spine", J["Spine"][2] + 0.02), ("Chest", J["Chest"][2] + 0.03),
          ("UpperChest", J["UpperChest"][2] + 0.05), ("Neck", J["Neck"][2] + 0.04)]
    z = verts[:, 2]
    zs = np.array([v for _, v in sp])
    for i, (n, z0) in enumerate(sp):
        lo = zs[i - 1] if i > 0 else -9
        hi = zs[i + 1] if i + 1 < len(sp) else 9
        up = np.clip((z - lo) / max(z0 - lo, 1e-3), 0, 1) if i > 0 else np.ones_like(z)
        dn = np.clip((hi - z) / max(hi - z0, 1e-3), 0, 1) if i + 1 < len(sp) else np.ones_like(z)
        w = np.where(z < z0, up, dn) * wt
        W[n] = np.maximum(W.get(n, 0), w)
    for S, s, sx in SIDES:
        c = J[f"{S}UpperArm"]
        dd = np.linalg.norm(verts - c, axis=1)
        w = np.clip(1 - dd / 0.19, 0, 1) * (verts[:, 0] * sx > 0.09) * wt
        W[f"{S}Shoulder"] = np.maximum(W.get(f"{S}Shoulder", 0), w * 0.9)
        h = J[f"{S}UpperLeg"]
        dd = np.linalg.norm((verts - h) * np.array([1, 1, 1.4]), axis=1)
        w = np.clip(1 - dd / 0.19, 0, 1) * (verts[:, 2] < h[2] + 0.05) * (verts[:, 0] * sx > -0.01)
        W[f"{S}UpperLeg"] = np.maximum(W.get(f"{S}UpperLeg", 0), w * 0.8)
    return W


def transfer(V, src_V, names, M, k=6, power=2.0):
    """Inverse-distance weight transfer from the skinned body (accessories, mantle)."""
    from scipy.spatial import cKDTree
    d, i = cKDTree(src_V).query(np.asarray(V, float), k=k)
    w = 1.0 / np.maximum(d, 1e-4) ** power
    w /= w.sum(1, keepdims=True)
    Mt = (M[i] * w[..., None]).sum(1)
    out = []
    for row in Mt:
        out.append({names[j]: float(row[j]) for j in np.nonzero(row > 1e-3)[0]})
    return out


def label_of(verts, parts):
    who, _ = F.nearest_part_labels(verts, [p for p in parts if p.op != "subtract"])
    labs = np.array([p.label for p in parts if p.op != "subtract"])[np.maximum(who, 0)]
    # boots: everything below the boot cuff (the wraps start above it)
    return np.where(np.asarray(verts)[:, 2] < 0.318, "boot", labs)


# --------------------------------------------------------------------------- hands

def hands(J):
    out = {}
    for S, s, sx in SIDES:
        el, wr = J[f"{S}LowerArm"], J[f"{S}Hand"]
        fa = unit(wr - el)
        medial = np.array([-sx, 0.0, 0.0])
        d = unit(fa + 0.06 * medial + np.array([0, -0.04, 0]))
        palm_n = medial * 0.96 + np.array([0, 0.22, 0])
        thumb_t = np.array([0, -1.0, 0.0])
        acc, bones = HH.build_hand(S, wr - fa * 0.010, d, palm_n, thumb_t, scale=SP.HAND["scale"],
                                   palm_len=SP.HAND["palm_len"], curl=SP.HAND["curl"])
        d_, t_, n_ = bones["_frame"]
        pl = SP.HAND["palm_len"] * SP.HAND["scale"]
        # staff channel of the closed fist: in front of the palm, across the proximal phalanges
        bones["_grip"] = (wr - fa * 0.010) + d_ * (0.86 * pl) + n_ * (0.036 * SP.HAND["scale"] / 1.42)
        out[S] = (acc, bones)
    return out


# --------------------------------------------------------------------------- ray helpers

def cast_in(field, origin, direction, rmax=0.8, step=0.0015):
    """First surface point travelling from outside into the field along direction (or None)."""
    rs = np.arange(0.0, rmax, step)
    P = np.asarray(origin, float)[None] + rs[:, None] * unit(direction)[None]
    d = field.sample(P)
    idx = np.nonzero(d < 0)[0]
    if not len(idx):
        return None
    k = idx[0]
    if k == 0:
        return P[0]
    d0, d1 = d[k - 1], d[k]
    f = d0 / (d0 - d1) if d0 != d1 else 0.0
    return P[k - 1] + (P[k] - P[k - 1]) * f


def cast_out(field, origin, direction, rmax=0.4, step=0.0012):
    """First exit point travelling from inside outward (or origin + rmax)."""
    rs = np.arange(0.0, rmax, step)
    P = np.asarray(origin, float)[None] + rs[:, None] * unit(direction)[None]
    d = field.sample(P)
    idx = np.nonzero(d >= 0)[0]
    if not len(idx):
        return P[-1]
    return P[idx[0]]


def grad(field, p, eps=0.003):
    g = np.array([field.sample((p + np.eye(3)[a] * eps)[None])[0] - field.sample((p - np.eye(3)[a] * eps)[None])[0]
                  for a in range(3)])
    return unit(g)


# --------------------------------------------------------------------------- generic meshes

def grid_faces(nr, nc, wrap=False):
    f = []
    last = nc if wrap else nc - 1
    for i in range(nr - 1):
        for j in range(last):
            j2 = (j + 1) % nc
            f.append([i * nc + j, i * nc + j2, (i + 1) * nc + j2, (i + 1) * nc + j])
    return f


def tube_aux(pts, radii, sides=8, cap=True, twist=0.0):
    """Tube along pts with (u = arc length, v = angle fraction) aux per vertex."""
    pts = np.asarray(pts, float)
    V, Fc = HD.tube_mesh(pts, radii, sides=sides, cap=cap)
    m = len(pts)
    seg = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    aux = np.zeros((len(V), 2))
    for i in range(m):
        for k in range(sides):
            aux[i * sides + k] = (seg[i], k / sides)
    if cap:
        aux[m * sides] = (0.0, 0.0)
        aux[m * sides + 1] = (seg[-1], 0.0)
    return V, Fc, aux


def bipyramid(center, axis, half_h, r, sides=6, ref=(1.0, 0.0, 0.0), squash=1.0):
    axis = unit(axis)
    e1 = unit(np.asarray(ref, float) - (np.asarray(ref, float) @ axis) * axis)
    e2 = np.cross(axis, e1)
    c = np.asarray(center, float)
    V = [c + axis * half_h, c - axis * half_h * 0.75]
    for k in range(sides):
        a = 2 * math.pi * k / sides
        rr = r * (1.0 if k % 2 == 0 else 0.86)
        V.append(c + axis * half_h * 0.12 + (e1 * math.cos(a) * squash + e2 * math.sin(a)) * rr)
    Fc = []
    for k in range(sides):
        k2 = (k + 1) % sides
        Fc.append([0, 2 + k, 2 + k2])
        Fc.append([1, 2 + k2, 2 + k])
    return np.array(V), Fc


def torus_mesh(center, axis, R, r, nu=16, nv=6, ref=(0.0, 0.0, 1.0)):
    axis = unit(axis)
    e1 = unit(np.asarray(ref, float) - (np.asarray(ref, float) @ axis) * axis)
    e2 = np.cross(axis, e1)
    V = []
    for i in range(nu):
        a = 2 * math.pi * i / nu
        d = e1 * math.cos(a) + e2 * math.sin(a)
        for j in range(nv):
            b = 2 * math.pi * j / nv
            V.append(np.asarray(center) + d * (R + r * math.cos(b)) + axis * r * math.sin(b))
    Fc = []
    for i in range(nu):
        for j in range(nv):
            i2, j2 = (i + 1) % nu, (j + 1) % nv
            Fc.append([i * nv + j, i2 * nv + j, i2 * nv + j2, i * nv + j2])
    return np.array(V), Fc


def mesh_field(fld):
    v, f = fld.mesh()
    return v, f


# --------------------------------------------------------------------------- fur mantle

def mantle(body, voxel=None):
    from frlib import texproj
    M = SP.MANTLE
    vox = voxel or M["voxel"]
    lo = np.array([-0.64, -0.33, 1.30])
    hi = np.array([0.64, 0.40, 2.03])
    fld = F.Field(lo, hi, vox)
    P = fld.points(np.zeros(3, int), fld.n)
    shp = P.shape[:3]
    Pf = P.reshape(-1, 3)
    db = body.sample(Pf).reshape(shp)
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    phi = np.degrees(np.abs(np.arctan2(x, -(y - 0.03))))
    hem = np.interp(phi, [a for a, _ in M["hem"]], [b for _, b in M["hem"]])
    top = np.interp(phi, [a for a, _ in M["top"]], [b for _, b in M["top"]])
    # hanging tufts: vertical-streak noise lowers the hem in places
    streak = texproj.fbm(Pf * np.array([34.0, 34.0, 4.0]), freq=1.0, octaves=3, seed=11).reshape(shp)
    hem_l = hem - M["ragged"] * smoothstep(0.35, 0.80, streak) - 0.012
    lump = texproj.fbm(Pf * np.array([20.0, 20.0, 9.0]), freq=1.0, octaves=3, seed=5).reshape(shp)
    strand = texproj.fbm(Pf * np.array([70.0, 70.0, 14.0]), freq=1.0, octaves=2, seed=9).reshape(shp)
    t = M["thick"] * (0.62 + 0.62 * lump + 0.22 * (strand - 0.5))
    # thinner toward the hem and the front edges, thin under the iron pauldron
    t *= 0.55 + 0.45 * smoothstep(0.0, 0.10, z - hem_l)
    t *= 0.75 + 0.25 * smoothstep(20.0, 60.0, phi)
    sxp = 1.0 if SP.PAULDRON["side"] == "l" else -1.0
    pc = np.array([sxp * 0.31, 0.0, 1.80])
    dp = np.sqrt(((P - pc) ** 2).sum(-1))
    t *= 0.45 + 0.55 * smoothstep(0.10, 0.20, dp)
    d = np.maximum(db - t, 0.0035 - db)
    d = np.maximum(d, hem_l - z)
    d = np.maximum(d, z - top)
    # neck opening (a ruff stands behind the head)
    a0, a1 = np.array([0.0, 0.0, 1.70]), np.array([0.0, -0.075, 2.06])
    u = a1 - a0
    tt = np.clip(((P - a0) @ u) / (u @ u), 0, 1)
    dist = np.sqrt(((P - (a0 + tt[..., None] * u)) ** 2).sum(-1))
    d = np.maximum(d, M["neck_open"] - dist)
    fld.d = d.astype(np.float32)
    v, f = fld.mesh()
    return v, f


# --------------------------------------------------------------------------- hair: topknot + braid

def topknot(body):
    o, s = head_frame()
    lo = np.array([-0.13, -0.24, 1.58])
    hi = np.array([0.13, 0.40, 2.30])
    fld = F.Field(lo, hi, 0.003)
    P = fld.points(np.zeros(3, int), fld.n)
    shp = P.shape[:3]
    Pf = P.reshape(-1, 3)
    db = body.sample(Pf).reshape(shp)
    q = (P - o) / s
    # shaved sides: a ridge of hair from the forehead line to the crown
    ridge_w = 0.040 + 0.018 * smoothstep(-0.06, 0.08, q[..., 1])
    d_ridge = np.maximum(db - 0.011, np.abs(q[..., 0]) * s - ridge_w * s)
    d_ridge = np.maximum(d_ridge, (0.070 - q[..., 2]) * s)            # above the hairline
    d_ridge = np.maximum(d_ridge, (q[..., 1] - 0.13) * s)            # stops at the crown/back
    d_ridge = np.maximum(d_ridge, -db - 0.004)                       # no inner volume
    bun_c = H((0.0, 0.082, 0.168))
    d_bun = np.sqrt((((P - bun_c) / (np.array([0.050, 0.052, 0.056]) * s)) ** 2).sum(-1)) - 1.0
    d_bun = d_bun * 0.050 * s
    d = F.smin(d_ridge, d_bun, 0.012)
    # braided tail: beads along a path down the back (over the mantle)
    path = braid_path()
    prims = []
    seg = np.cumsum(np.r_[0, np.linalg.norm(np.diff(path, axis=0), axis=1)])
    L = seg[-1]
    nb = int(L / 0.026)
    for i in range(nb):
        u_ = (i + 0.5) / nb
        p = np.array([np.interp(u_ * L, seg, path[:, k]) for k in range(3)])
        p2 = np.array([np.interp(min(u_ * L + 0.01, L), seg, path[:, k]) for k in range(3)])
        tdir = unit(p2 - p)
        side = unit(np.cross(tdir, [0, 1.0, 0]))
        r = 0.021 - 0.009 * u_
        c = p + side * (0.007 if i % 2 else -0.007)
        prims.append(fsdf.round_cone(c - tdir * r * 0.55, c + tdir * r * 0.55, r * 0.95, r * 0.80))
    for pr in prims:
        i0, i1 = fld.block(pr.lo - 0.01, pr.hi + 0.01)
        if np.any(i1 <= i0):
            continue
        sl = tuple(slice(i0[j], i1[j]) for j in range(3))
        d[sl] = F.smin(d[sl], pr.fn(fld.points(i0, i1)).astype(np.float32), 0.006)
    fld.d = d.astype(np.float32)
    v, f = fld.mesh()
    return v, f


def braid_path():
    return np.array([H((0.0, 0.110, 0.150)), [0.0, 0.030, 2.105], [0.0, 0.090, 2.030], [0.0, 0.150, 1.940],
                     [0.0, 0.222, 1.820], [0.0, 0.296, 1.690]], float)


def hair_weights(V):
    out = []
    for p in V:
        if p[2] > 1.99:
            out.append({"Head": 1.0})
        else:
            w = float(np.clip((1.99 - p[2]) / 0.16, 0, 1))
            out.append({"Head": 1.0 - 0.85 * w, "Hood": 0.85 * w})
    return out


def tusks():
    out = []
    o, s = head_frame()
    for sx in (1, -1):
        base = H((sx * 0.034, -0.150, -0.118))
        tip = H((sx * 0.052, -0.170, -0.056))
        mid = 0.5 * (base + tip) + np.array([sx * 0.006, -0.010, 0.0])
        pts = np.array([base - np.array([0, -0.006, 0.006]), base, mid, tip])
        V, Fc, aux = tube_aux(pts, [0.0115 * s, 0.011 * s, 0.0085 * s, 0.0016], sides=7)
        out.append(Piece(f"tusk_{'l' if sx > 0 else 'r'}", V, Fc, "tusk", [{"Head": 1.0}] * len(V), aux, flat=False))
    return out


# --------------------------------------------------------------------------- pauldron

def pauldron(J):
    sx = 1.0 if SP.PAULDRON["side"] == "l" else -1.0
    S = "Left" if sx > 0 else "Right"
    c = J[f"{S}UpperArm"] + np.array([sx * 0.020, 0.0, 0.030])
    a = unit((sx * 0.62, 0.0, 0.78))
    e1 = np.array([0.0, -1.0, 0.0])
    e2 = unit(np.cross(a, e1))           # outward-down
    if e2[0] * sx < 0:
        e2 = -e2
    R = SP.PAULDRON["radius"]
    nt, nph = 7, 20
    V, aux = [c + a * R * 1.0], [(0.0, 0.0)]
    for i in range(1, nt + 1):
        for j in range(nph):
            ph = 2 * math.pi * j / nph
            tmax = math.radians(58.0 + 15.0 * math.cos(ph))
            th = tmax * i / nt
            ridge = 1.0 + 0.035 * math.exp(-((math.sin(ph)) / 0.25) ** 2) * math.sin(th / max(tmax, 1e-6) * math.pi)
            dvec = math.cos(th) * a + math.sin(th) * (math.cos(ph) * e2 + math.sin(ph) * e1)
            V.append(c + dvec * R * ridge)
            aux.append((th / max(tmax, 1e-6), j / nph))
    Fc = [[0, 1 + (j + 1) % nph, 1 + j] for j in range(nph)]
    Fc += [[1 + f_ for f_ in q] for q in grid_faces(nt, nph, wrap=True)]
    pieces = [Piece("pauldron_dome", np.array(V), Fc, "iron", None, np.array(aux), solid=0.012)]
    pieces[0].inner_ref = c
    # two lames below the outer edge
    for li, (t0, t1, rs) in enumerate(((0.92, 1.18, 1.035), (1.12, 1.38, 1.07))):
        V, aux = [], []
        nr, nc = 3, 13
        for i in range(nr):
            for j in range(nc):
                ph = math.radians(-72 + 144 * j / (nc - 1))
                tmax = math.radians(58.0 + 15.0 * math.cos(ph))
                th = tmax * (t0 + (t1 - t0) * i / (nr - 1))
                dvec = math.cos(th) * a + math.sin(th) * (math.cos(ph) * e2 + math.sin(ph) * e1)
                V.append(c + dvec * R * rs)
                aux.append((1.0 + i / (nr - 1), j / nc))
        w = [{f"{S}UpperArm": 0.8, f"{S}Shoulder": 0.2}] * len(V)
        pieces.append(Piece(f"pauldron_lame{li}", np.array(V), grid_faces(nr, nc), "iron", w, np.array(aux), solid=0.010))
        pieces[-1].inner_ref = c
    # spikes along the outer ridge
    for k, th_deg in enumerate((14.0, 34.0, 54.0)[:SP.PAULDRON["spikes"]]):
        th = math.radians(th_deg)
        n = unit(math.cos(th) * a + math.sin(th) * e2)
        base = c + n * R * 1.03
        ln = SP.PAULDRON["spike_len"] * (1.0 - 0.12 * k)
        pts = np.array([base - n * 0.012, base + n * ln * 0.35, base + n * ln])
        V, Fc, aux = tube_aux(pts, [0.024, 0.014, 0.0015], sides=6)
        pieces.append(Piece(f"pauldron_spike{k}", V, Fc, "iron", [{f"{S}Shoulder": 0.45, f"{S}UpperArm": 0.55}] * len(V),
                            aux, flat=True))
    for p in pieces:
        if p.weights is None:
            p.weights = [{f"{S}Shoulder": 0.45, f"{S}UpperArm": 0.55}] * len(p.V)
    return pieces


# --------------------------------------------------------------------------- straps, belt, trinkets

def harness(body):
    Hs = SP.HARNESS
    pieces = []
    ring_pts = []
    for k, sg in enumerate((1.0, -1.0)):
        pts, nrm = [], []
        for f in np.linspace(0.0, 1.0, 22):
            x = sg * Hs["x_top"] + (-sg * Hs["x_bot"] - sg * Hs["x_top"]) * f
            z = Hs["z_top"] + (Hs["z_bot"] - Hs["z_top"]) * f
            p = cast_in(body, (x, -0.6, z), (0, 1.0, 0))
            if p is None:
                continue
            n = grad(body, p)
            pts.append(p + n * (0.010 + 0.007 * k))
            nrm.append(n)
        pts = np.array(pts)
        sh = HD.strip(f"harness_{k}", pts, np.array(nrm), Hs["width"])
        V = sh.V
        aux = np.zeros((len(V), 2))
        seg = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
        for i in range(len(pts)):
            aux[2 * i] = (seg[i], 0.0)
            aux[2 * i + 1] = (seg[i], 1.0)
        pieces.append(Piece(f"harness_{k}", V, sh.faces(), "leather", None, aux, solid=0.008))
    # ring at the crossing + chest crystal hanging below it
    p = cast_in(body, (0.0, -0.6, Hs["ring_z"]), (0, 1.0, 0))
    ring_c = p + np.array([0.0, -0.030, 0.0])
    V, Fc = torus_mesh(ring_c, (0, -1.0, 0.2), 0.036, 0.0085, nu=12, nv=5)
    pieces.append(Piece("harness_ring", V, Fc, "iron", None, None))
    A = SP.AMULET
    cc = ring_c + np.array([0.0, -0.012, -0.036 - A["len"] * 0.55])
    V, Fc = torus_mesh(ring_c + np.array([0, -0.006, -0.040]), (1.0, 0.0, 0.0), 0.011, 0.004, nu=8, nv=4,
                       ref=(0, 0, 1))
    pieces.append(Piece("amulet_loop", V, Fc, "iron", None, None))
    V, Fc, aux = tube_aux(np.array([cc + [0, 0, A["len"] * 0.62], cc + [0, 0, A["len"] * 0.40]]),
                          [0.010, A["r"] * 1.06], sides=6)
    pieces.append(Piece("amulet_cap", V, Fc, "iron", None, aux, flat=True))
    V, Fc = bipyramid(cc, (0, 0, 1.0), A["len"] * 0.5, A["r"], sides=6, ref=(1, 0, 0))
    pieces.append(Piece("amulet_crystal", V, Fc, "crystal", None, None, flat=True, kind="glow"))
    return pieces, ring_c


def belt(sup, T):
    B = SP.BELT
    sh = HD.band_ring("belt", sup, (0.0, T.cy, B["z"]), (0, 0, 1), (0, -1, 0), rad_guess=0.32, width=B["height"],
                      offset=B["offset"] + 0.012, n=36, rows=3, thickness=0.008)
    V = sh.V
    aux = np.zeros((len(V), 2))
    nv, nu = sh.shape
    for i in range(nv):
        for j in range(nu):
            aux[i * nu + j] = (j / nu * 2.0, i / (nv - 1))
    pieces = [Piece("belt", V, sh.faces(), "leather", [{"Hips": 1.0}] * len(V), aux, solid=0.009)]
    fy = T.cy - float(T.hull(np.array([B["z"]]), np.array([0.0]))[0]) - B["offset"] - 0.024
    V, Fc = HD.box_mesh((0.0, fy, B["z"]), (0.060, 0.013, 0.054), bevel=0.35, nseg=0)
    pieces.append(Piece("buckle", V, Fc, "iron", [{"Hips": 1.0}] * len(V), None, flat=True))
    return pieces


def trinkets(T):
    """Bone / charm trinkets hanging from the belt (front-left cluster, skull on the right hip)."""
    B = SP.BELT
    zb = B["z"] - B["height"] * 0.45
    pieces = []

    def front_at(phi_deg, z, extra):
        r = float(T.hull(np.array([z]), np.array([math.radians(phi_deg)]))[0]) + extra
        ph = math.radians(phi_deg)
        return np.array([T.cx + r * math.sin(ph), T.cy - r * math.cos(ph), z]), np.array([math.sin(ph), -math.cos(ph), 0])

    wb = {"Bag": 0.75, "Hips": 0.25}
    # three bones on cords (front-left)
    for i, (ph, ln) in enumerate(((22.0, 0.10), (34.0, 0.16), (46.0, 0.12))):
        top, n = front_at(ph, zb, B["offset"] + 0.05)
        bot = top + np.array([0.0, 0.0, -ln])
        V, Fc, aux = tube_aux(np.array([top, bot]), 0.0035, sides=4)
        pieces.append(Piece(f"cord{i}", V, Fc, "leather", [wb] * len(V), aux))
        b0 = bot + np.array([0, 0, -0.004])
        b1 = b0 + np.array([0.008 * (i - 1), -0.004, -0.085])
        V, Fc, aux = tube_aux(np.array([b0, b0 + (b1 - b0) * 0.2, b0 + (b1 - b0) * 0.8, b1]),
                              [0.013, 0.008, 0.008, 0.013], sides=6)
        pieces.append(Piece(f"bone{i}", V, Fc, "bone", [wb] * len(V), aux))
    # two fangs on a short cord
    for i, ph in enumerate((10.0, 15.0)):
        top, n = front_at(ph, zb - 0.02, B["offset"] + 0.05)
        pts = np.array([top, top + np.array([0, -0.004, -0.030]), top + np.array([0.004, -0.010, -0.075])])
        V, Fc, aux = tube_aux(pts, [0.008, 0.007, 0.0012], sides=5)
        pieces.append(Piece(f"fang{i}", V, Fc, "bone", [wb] * len(V), aux))
    # small skull on the right hip
    c, n = front_at(-58.0, zb - 0.07, B["offset"] + 0.07)
    V, Fc = HD.box_mesh(c, (0.036, 0.034, 0.040), bevel=0.75, nseg=1)
    pieces.append(Piece("skull", V, Fc, "bone", [{"Hips": 0.6, "SkirtRight": 0.4}] * len(V), None))
    V, Fc = HD.box_mesh(c + np.array([0, -0.008, -0.040]), (0.026, 0.022, 0.014), bevel=0.6, nseg=0)
    pieces.append(Piece("skull_jaw", V, Fc, "bone", [{"Hips": 0.6, "SkirtRight": 0.4}] * len(V), None))
    top, n = front_at(-58.0, zb, B["offset"] + 0.05)
    V, Fc, aux = tube_aux(np.array([top, c + np.array([0, 0, 0.035])]), 0.004, sides=4)
    pieces.append(Piece("skull_cord", V, Fc, "leather", [{"Hips": 1.0}] * len(V), aux))
    # pouch on the right back hip
    c, n = front_at(-118.0, zb - 0.06, B["offset"] + 0.045)
    V, Fc = HD.box_mesh(c, (0.050, 0.030, 0.070), bevel=0.5, nseg=0)
    pieces.append(Piece("pouch", V, Fc, "leather", [{"Hips": 0.7, "SkirtRight": 0.3}] * len(V), None))
    return pieces


def skirt_weights_fn(z_top, cx, cy, hem_lo, thigh=0.5):
    def fn(V):
        W = []
        for p in V.reshape(-1, 3):
            v = float(np.clip((z_top - p[2]) / max(z_top - hem_lo, 1e-3), 0, 1))
            phi = math.atan2(p[0] - cx, -(p[1] - cy))
            ap = abs(phi)
            wh = 1 - float(smoothstep(0.0, 0.30, v))
            rest = 1 - wh
            lvl2 = float(smoothstep(0.45, 0.8, v))
            facing = max(math.cos(phi), 0.0) if ap < math.pi / 2 else 0.6 * max(-math.cos(phi), 0.0)
            wt = thigh * float(smoothstep(0.1, 0.55, v)) * facing ** 0.5
            wl = wt * float(np.clip(0.5 + (p[0] - cx) / 0.16, 0, 1))
            wr = wt - wl
            rest2 = rest * (1 - wt)
            d = {"Hips": wh * (1 - wt)}
            if ap < math.radians(55):
                d["SkirtFront1"] = rest2 * (1 - lvl2)
                d["SkirtFront2"] = rest2 * lvl2
            elif ap > math.radians(125):
                d["SkirtBack1"] = rest2 * (1 - lvl2)
                d["SkirtBack2"] = rest2 * lvl2
            else:
                d["SkirtLeft" if phi > 0 else "SkirtRight"] = rest2
            d["LeftUpperLeg"] = wl
            d["RightUpperLeg"] = wr
            W.append({k: float(x) for k, x in d.items() if x > 1e-3})
        return W
    return fn


def kilt(T):
    K = SP.KILT
    pieces = []
    zt = K["z_top"]
    hem = K["under_hem"]
    wfn = skirt_weights_fn(zt, T.cx, T.cy, hem, thigh=0.55)
    sh = HD.drape_skirt("kilt", T, None, zt, lambda p: hem + 0.03 * math.cos(p) ** 2, -math.pi, math.pi,
                        offset=0.014, flare=0.05, fit=None, nu=26, nv=7, closed=True, weights_fn=wfn,
                        ragged=0.006, slope=0.10, seed=3)
    pieces.append(_sheet_piece(sh, "cloth_dark", 0.006))
    for fdef in K["flaps"] + K["tassets"]:
        ph, hw = math.radians(fdef["phi"]), math.radians(fdef["half"])
        hl = fdef["hem"]
        wfn = skirt_weights_fn(zt, T.cx, T.cy, hl, thigh=0.55)
        sh = HD.drape_skirt(fdef["name"], T, None, zt + 0.01, lambda p, hl=hl: hl, ph - hw, ph + hw,
                            offset=fdef["offset"], flare=0.06, fit=None, nu=5 if fdef["cls"] == "cloth_red" else 4,
                            nv=8 if fdef["cls"] == "cloth_red" else 6, closed=False, weights_fn=wfn,
                            ragged=0.008 if fdef["cls"] == "cloth_red" else 0.003, slope=0.10,
                            seed=int(abs(fdef["phi"])) + 7)
        pieces.append(_sheet_piece(sh, fdef["cls"], 0.006))
    return pieces


def _sheet_piece(sh, cls, thick):
    nv, nu = sh.shape
    aux = np.zeros((nv * nu, 2))
    for i in range(nv):
        for j in range(nu):
            aux[i * nu + j] = (j / max(nu - 1, 1), i / (nv - 1))
    return Piece(sh.name, sh.V, sh.faces(), cls, sh.weights, aux, solid=thick if not sh.closed_u else thick)


# --------------------------------------------------------------------------- wraps

def wrap_tube(body, A, B, t0, t1, rings, sides, offset, name, cls, weights_fn, bump=0.004):
    A, B = np.asarray(A, float), np.asarray(B, float)
    ax = unit(B - A)
    e1 = unit(np.cross(ax, (0, 1.0, 0)))
    e2 = np.cross(ax, e1)
    V, aux = [], []
    L = np.linalg.norm(B - A)
    for i in range(rings):
        f = t0 + (t1 - t0) * i / (rings - 1)
        c = A + (B - A) * f
        edge = 1.0 if 0 < i < rings - 1 else 0.25
        for j in range(sides):
            a = 2 * math.pi * j / sides
            dvec = e1 * math.cos(a) + e2 * math.sin(a)
            p = cast_out(body, c, dvec, rmax=0.25)
            wob = 0.5 + 0.5 * math.cos(2 * math.pi * (f * L / 0.05 + j / sides))
            V.append(p + dvec * (offset + bump * wob) * edge)
            aux.append((f * L, j / sides))
    V = np.array(V)
    Fc = grid_faces(rings, sides, wrap=True)
    return Piece(name, V, Fc, cls, weights_fn(V), np.array(aux), kind="acc")


def wraps(body, J):
    out = []
    for S, s, sx in SIDES:
        el, wr = J[f"{S}LowerArm"], J[f"{S}Hand"]

        def wf(V, S=S, el=el, wr=wr):
            ax = wr - el
            t = np.clip(((V - el) @ ax) / (ax @ ax), 0, 1.2)
            return [{f"{S}LowerArm": float(1 - 0.35 * smoothstep(0.92, 1.05, tt)),
                     f"{S}Hand": float(0.35 * smoothstep(0.92, 1.05, tt))} for tt in t]
        out.append(wrap_tube(body, el, wr, 0.50, 1.01, 9, 12, 0.004, f"wrap_arm_{s}", "linen", wf, bump=0.003))
        kn, an = J[f"{S}LowerLeg"], J[f"{S}Foot"]
        out.append(wrap_tube(body, kn, an, 0.26, 0.60, 7, 12, 0.004, f"wrap_shin_{s}", "linen",
                             lambda V, S=S: [{f"{S}LowerLeg": 1.0}] * len(V)))
    return out


# --------------------------------------------------------------------------- staff

def staff_frame(hand_bones):
    """Rest-pose staff axis (thumb direction of the right fist) and grip point."""
    hb = hand_bones["Right"]
    d, t, n = hb["_frame"]
    g = np.asarray(hb["_grip"], float)
    u = unit(t)
    return g, u, unit(n)


def staff(hand_bones):
    St = SP.STAFF
    g, u, n = staff_frame(hand_bones)
    side = unit(np.cross(u, n))
    base = g - u * St["grip_from_bottom"]

    def at(sv):
        return base + u * sv
    pieces = []
    W = [{"PropR": 1.0}]
    r = St["radius"]
    # carved bone shaft: alternating rings (carving) and knots
    ss = np.linspace(0.05, 1.66, 20)
    rad = [r * (1.0 + 0.10 * math.sin(2 * math.pi * sv / 0.11) ** 8 + 0.04 * math.sin(sv * 7.0)) for sv in ss]
    V, Fc, aux = tube_aux(np.array([at(sv) for sv in ss]), rad, sides=8)
    aux[:, 0] += 0.05
    pieces.append(Piece("staff_shaft", V, Fc, "staff_bone", W * len(V), aux))
    # iron ferrule + collars
    V, Fc, aux = tube_aux(np.array([at(-0.005), at(0.03), at(0.075)]), [0.007, r * 1.2, r * 1.28], sides=8)
    pieces.append(Piece("staff_ferrule", V, Fc, "staff_iron", W * len(V), aux))
    for i, sv in enumerate((0.42, 0.78, 1.38, 1.60)):
        V, Fc, aux = tube_aux(np.array([at(sv - 0.018), at(sv + 0.018)]), r * 1.32, sides=8)
        pieces.append(Piece(f"staff_collar{i}", V, Fc, "staff_iron", W * len(V), aux))
    # leather grip wrap
    gs = St["grip_from_bottom"]
    V, Fc, aux = tube_aux(np.array([at(gs - 0.15), at(gs - 0.05), at(gs + 0.05), at(gs + 0.13)]), r * 1.22, sides=8)
    pieces.append(Piece("staff_grip", V, Fc, "staff_leather", W * len(V), aux))
    # two bone horns below the cage
    for k, sg in enumerate((1.0, -1.0)):
        p0 = at(1.555)
        out_dir = unit(side * sg + n * 0.25)
        pts = np.array([p0, p0 + out_dir * 0.045 + u * 0.010, p0 + out_dir * 0.080 + u * 0.050,
                        p0 + out_dir * 0.088 + u * 0.095])
        V, Fc, aux = tube_aux(pts, [0.016, 0.012, 0.007, 0.0015], sides=6)
        pieces.append(Piece(f"staff_horn{k}", V, Fc, "staff_bone", W * len(V), aux))
    # iron cage finial (5 bars) around the crystal
    c0, c1 = 1.645, 1.895
    V, Fc, aux = tube_aux(np.array([at(c0 - 0.03), at(c0 + 0.012)]), [r * 1.35, St["cage_r"] * 0.48], sides=8)
    pieces.append(Piece("staff_cage_base", V, Fc, "staff_iron", W * len(V), aux))
    for b in range(5):
        pts = []
        for f in np.linspace(0.0, 1.0, 9):
            rr = 0.028 + (St["cage_r"] - 0.028) * math.sin(math.pi * f) ** 0.75
            if f > 0.97:
                rr = 0.006
            ang = 2 * math.pi * b / 5 + 0.55 * f
            pts.append(at(c0 + (c1 - c0) * f) + (side * math.cos(ang) + n * math.sin(ang)) * rr)
        V, Fc, aux = tube_aux(np.array(pts), 0.0058, sides=4, cap=False)
        pieces.append(Piece(f"staff_bar{b}", V, Fc, "staff_iron", W * len(V), aux))
    V, Fc, aux = tube_aux(np.array([at(c1 - 0.01), at(c1 + 0.012), at(c1 + 0.055)]), [0.016, 0.012, 0.0015], sides=6)
    pieces.append(Piece("staff_tip", V, Fc, "staff_iron", W * len(V), aux, flat=True))
    cc = at(0.5 * (c0 + c1) - 0.002)
    V, Fc = bipyramid(cc, u, St["crystal_h"] * 0.5, St["crystal_r"], sides=6, ref=side)
    pieces.append(Piece("staff_crystal", V, Fc, "crystal", W * len(V), None, flat=True, kind="glow"))
    info = dict(base=base, axis=u, grip=g, crystal=cc, top=at(c1 + 0.055), side=side, n=n)
    return pieces, info
