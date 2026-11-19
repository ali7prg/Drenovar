"""Build one v2 human (image-based): geometry fitted to the painted turnaround, painted textures,
shared human_shared rig, clips, LODs, GLB + meta, QA sheets.

    python3 forest_rescue/blender/run_limited.py \
        forest_rescue/blender/assets/humans/v2/build_v2.py <asset_id> [--iter NN] [--stage geo|full]

Stage geo: geometry + texture + turnaround/portrait compare sheets (fast iteration).
Stage full: + rig, weights, 22-clip set (10 soldier / 12 civilian), LOD1/2, GLB, meta, .blend.
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from frlib import core, paths, texproj  # noqa: E402
import hv2_fit as F  # noqa: E402
import hv2_body as HB  # noqa: E402
import hv2_hand as HH  # noqa: E402
import hv2_drape as HD  # noqa: E402
import hv2_tex as HT  # noqa: E402
import hv2_blender as HBL  # noqa: E402
import hv2_rig as HRG  # noqa: E402
from hv2_chars import CHARS  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
AID = ARGS[0]
ITER = int(ARGS[ARGS.index("--iter") + 1]) if "--iter" in ARGS else 1
STAGE = ARGS[ARGS.index("--stage") + 1] if "--stage" in ARGS else "geo"
TEX = int(ARGS[ARGS.index("--tex") + 1]) if "--tex" in ARGS else 2048
VOX = float(ARGS[ARGS.index("--vox") + 1]) if "--vox" in ARGS else 0.003
GROUP = "humans"
T0 = time.time()
C = CHARS[AID]
BUDGET = {"civilian": (12000, 6000, 2200), "soldier": (14000, 7000, 2500)}[C["kind"]]


def log(*a):
    print(f"[{time.time() - T0:7.1f}s]", *a, flush=True)


def qa(name):
    return paths.compare(AID, f"v2_iter{ITER:02d}_{name}")


# --------------------------------------------------------------------------- geometry (numpy)

def body_geometry(R, J):
    torso, prof = HB.torso_part(R, C, J)
    parts = [torso] + HB.arm_parts(R, C, J, prof) + HB.leg_parts(R, C, J) + HB.boot_parts(R, C, J) \
        + HB.head_parts(C, J) + HB.neck_trap_parts(C, J) + HB.sleeve_cuff_parts(C, J, R)
    top = C["L"]["top"] + 0.03
    fld = F.Field((-0.62, -0.36, -0.01), (0.62, 0.30, top), VOX)
    for p in parts:
        fld.apply(p)
    fld.intersect_xz(R, k=0.005, dilate=0.0015)
    fld.clip_ground(0.0, k=0.002)
    v, f = fld.mesh()
    log("body MC", len(v), "verts", len(f), "tris")
    weight_parts = parts[1:] + HB.torso_bone_parts(prof, J)
    # support field for garments: torso + legs + boots only (no arms/hands)
    sup = F.Field((-0.62, -0.36, -0.01), (0.62, 0.30, top), 0.006)
    for p in parts:
        if p.name.startswith(("upperarm", "forearm", "deltoid", "elbow")):
            continue
        sup.apply(p)
    log("arm profile k", [round(float(x), 2) for x in getattr(HB, "LAST_K", [])])
    return fld, parts, weight_parts, prof, v, f, sup


def hair_geometry(R, J, body_field):
    """Hair + beard as a volume of wavy clumps fitted to the painted head outline (front/back
    consensus), rounded by a soft hull intersection; textured later from portrait + views."""
    o, S = HB.head_frame(C, J)
    lo = o + np.array([-0.16, -0.17, -0.22])
    hi = o + np.array([0.16, 0.19, 0.22])
    hi[2] = max(hi[2], C["L"]["top"] + 0.05)
    fld = F.Field(lo, hi, 0.0025)
    d, n = HB.hair_clump_field(C, J, R, body_field, fld)
    fld.d = d
    fld.intersect_xz(R, k=0.012, dilate=0.003)
    v, f = fld.mesh()
    log("hair clumps", n, "MC", len(v), "verts", len(f), "tris")
    return v, f


def hands_geometry(J):
    L = C["L"]
    out = {}
    for S, s, sx in HB.SIDES:
        el, wr = J[f"{S}LowerArm"], J[f"{S}Hand"]
        fa = (wr - el) / np.linalg.norm(wr - el)
        medial = np.array([-sx, 0.0, 0.0])
        d = fa + 0.06 * medial + np.array([0, -0.04, 0])
        d /= np.linalg.norm(d)
        palm_n = medial * 0.96 + np.array([0, 0.22, 0])          # palm toward the thigh, a bit back
        thumb_t = np.array([0, -1.0, 0.0])                       # thumb forward
        acc, bones = HH.build_hand(S, wr - fa * 0.010, d, palm_n, thumb_t, scale=L["hand_scale"],
                                   palm_len=1.06 * C["build"].get("palm_len", 0.095 if not C["female"] else 0.085),
                                   female=C["female"])
        out[S] = (acc, bones)
    return out


def skirt_weights_fn(z_top, cx, cy, hem_lo, thigh=0.5):
    """Skirt/apron/tabard weights: hips at the waist, skirt bones lower down, and a share of the
    thigh under each panel so seated / walking legs carry the cloth instead of cutting through it."""
    def fn(V):
        W = []
        for p in V.reshape(-1, 3):
            v = np.clip((z_top - p[2]) / max(z_top - hem_lo, 1e-3), 0, 1)
            phi = math.atan2(p[0] - cx, -(p[1] - cy))
            ap = abs(phi)
            wh = 1 - HT.smoothstep(0.0, 0.32, v)
            rest = 1 - wh
            lvl2 = HT.smoothstep(0.45, 0.8, v)
            # thigh share: strongest on the panels in front of / behind the legs, toward the hem
            facing = max(math.cos(phi), 0.0) if ap < math.pi / 2 else 0.6 * max(-math.cos(phi), 0.0)
            wt = thigh * HT.smoothstep(0.1, 0.55, v) * facing ** 0.5
            wl = wt * float(np.clip(0.5 + (p[0] - cx) / 0.10, 0, 1))
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


def cloak_weights_fn(z_top, hem_lo):
    def fn(V):
        W = []
        for p in V.reshape(-1, 3):
            v = np.clip((z_top - p[2]) / max(z_top - hem_lo, 1e-3), 0, 1)
            side = "Left" if p[0] > 0 else "Right"
            d = {"UpperChest": 1 - HT.smoothstep(0.0, 0.25, v)}
            if p[1] > 0.0:
                d["Cloak1"] = HT.smoothstep(0.0, 0.25, v) * (1 - HT.smoothstep(0.4, 0.8, v))
                d["Cloak2"] = HT.smoothstep(0.4, 0.8, v)
            else:
                d[f"{side}Shoulder"] = HT.smoothstep(0.0, 0.25, v) * 0.5
                d["Chest"] = HT.smoothstep(0.0, 0.25, v) * 0.5
            W.append({k: float(x) for k, x in d.items() if x > 1e-3})
        return W
    return fn


def arm_cap_fn(J):
    """Max half-extent of a garment row so the fit never grabs the painted arms/hands."""
    L = C["L"]

    def cap(z, sgn):
        s = "l" if sgn > 0 else "r"
        S_ = "Left" if sgn > 0 else "Right"
        wr = J[f"{S_}Hand"]
        if z < wr[2] + 0.05:
            return abs(wr[0]) - 0.050 * L["hand_scale"]
        ax = abs(HB._arm_axis_x(L, s, z))
        return ax - 0.050
    return cap


def garments(R, J, fld, prof, sup):
    """Garment sheets + accessories from the character spec."""
    hz = J["Hips"][2]
    cy = 0.012
    T = HD.BodyTable(sup, 0.0, cy, 0.05, C["L"]["neck"] + 0.02, dz=0.01)
    sheets = []
    T_full = None
    for g in C.get("garments", []):
        if g["kind"] in ("skirt", "cloak"):
            if g["kind"] == "cloak":
                if T_full is None:
                    T_full = HD.BodyTable(fld, 0.0, cy, 0.05, C["L"]["neck"] + 0.04, dz=0.01)
                TT = T_full
            else:
                TT = T
            hem = g.get("hem")
            if hem is None:
                hz_ = g.get("hem_z", 0.4)
                hem = (hz_, hz_, hz_)
            hp = g.get("hem_pts")

            def hem_fn(p, hem=hem, hp=hp):
                ap = abs(math.atan2(math.sin(p), math.cos(p)))
                if hp:
                    return float(np.interp(math.degrees(ap), [x for x, _ in hp], [z for _, z in hp]))
                return float(np.interp(ap, [0, math.pi / 2, math.pi], hem))
            if g.get("closed"):
                ph0, ph1 = -math.pi, math.pi
            else:
                ph0, ph1 = (math.radians(a_) for a_ in g["wrap"])
            fit_max = g.get("fit_max")
            capf = arm_cap_fn(J)
            if fit_max is not None:
                capf = (lambda z, sg, fm=fit_max, cf=capf: min(fm, cf(z, sg)))
            if g["kind"] == "cloak":
                capf = (lambda z, sg: 9.0)
            hem_lo = min(hem_fn(pp) for pp in np.linspace(ph0, ph1, 30))
            wfn = skirt_weights_fn(g["z_top"], TT.cx, TT.cy, hem_lo, thigh=g.get("thigh", 0.5))
            if g["kind"] == "cloak":
                wfn = cloak_weights_fn(g["z_top"], hem_lo)
            sh = HD.drape_skirt(g["name"], TT, R, g["z_top"], hem_fn, ph0, ph1, offset=g.get("offset", 0.012),
                                flare=g.get("flare", 0.03), fit=g.get("fit"), nu=g.get("nu", 34), nv=g.get("nv", 18),
                                material=g.get("material", "cloth"), thickness=g.get("thickness", 0.005),
                                weights_fn=wfn, ragged=g.get("ragged", 0.004), seed=len(sheets),
                                fit_rows=g.get("fit_rows"), closed=bool(g.get("closed")), cap_fn=capf,
                                slope=g.get("slope", 0.12))
            sheets.append(sh)
        elif g["kind"] == "bib":
            ht, hb = g["half_angle"]
            sheets.append(HD.bib(g["name"], T, g["z_top"], g["z_bot"], ht, hb, offset=g.get("offset", 0.006),
                                 material=g.get("material", "cloth"), thickness=g.get("thickness", 0.004)))
    meshes = []     # (name, V, F, weights, material, label)
    for a in C.get("acc", []):
        k = a["kind"]
        if k == "band":
            S = "Left" if a["side"] == "l" else "Right"
            A, B = J[f"{S}UpperArm"], J[f"{S}LowerArm"]
            c = A + (B - A) * a["t"]
            sh = HD.band_ring(a["name"], fld, c, B - A, (0, -1, 0), rad_guess=0.07, width=a["width"], offset=0.004,
                              thickness=0.005, material=a.get("material", "cloth"), weights={f"{S}UpperArm": 1.0})
            sheets.append(sh)
        elif k == "belt":
            sh = HD.band_ring(a["name"], fld, (0, cy, a["z"]), (0, 0, 1), (0, -1, 0), rad_guess=0.2,
                              width=a["height"], offset=a.get("offset", 0.012), n=40, thickness=0.006,
                              material=a.get("material", "cloth"), weights={"Hips": 1.0})
            sheets.append(sh)
        elif k == "bow":
            z = a["z"]
            r = T.hull(np.array([z]), np.array([math.pi]))[0] + 0.022
            bc = np.array([0.0, T.cy + r, z])
            for sx in (1, -1):
                loop = [bc + np.array([sx * dx, 0.010 + 0.012 * math.sin(math.pi * dx / 0.07),
                                       0.022 * math.sin(math.pi * dx / 0.07)]) for dx in np.linspace(0.004, 0.07, 7)]
                loop += [bc + np.array([sx * dx, 0.012, -0.016 * math.sin(math.pi * dx / 0.07)])
                         for dx in np.linspace(0.066, 0.004, 6)]
                V, Fc = HD.tube_mesh(np.array(loop), 0.009, sides=6)
                meshes.append((f"{a['name']}_loop{sx}", V, Fc, [{"Hips": 1.0}] * len(V), a.get("material", "cloth")))
                zs = np.linspace(z - 0.01, z - a["tails"], 9)
                pts = []
                for i, zz in enumerate(zs):
                    rr = T.hull(np.array([zz]), np.array([math.pi - sx * 0.10]))[0] + 0.018
                    pts.append([sx * (0.010 + 0.012 * i / 8), T.cy + rr, zz])
                pts = np.array(pts)
                nrm = np.tile(np.array([0, 1.0, 0]), (len(pts), 1))
                wts = [{"Hips": 1 - min(1, i / 4) * 0.6, "SkirtBack1": min(1, i / 4) * 0.6} for i in range(len(pts))
                       for _ in range(2)]
                sheets.append(HD.strip(f"{a['name']}_tail{sx}", pts, nrm, 0.028, material=a.get("material", "cloth"),
                                       weights=wts))
        elif k == "neck_strap":
            z0 = a["z0"]
            nz = C["L"]["neck"]
            pts = []
            # front corner -> over the trapezius -> around the back of the neck
            for sx in (1, -1):
                seq = []
                for f in np.linspace(0, 1, 9):
                    phi = sx * (0.55 + f * 2.55)
                    z = z0 + (nz + 0.035 - z0) * min(1.0, f * 1.6)
                    rr = T.hull(np.array([min(z, T.zs[-1])]), np.array([phi]))[0] + 0.006
                    rr = min(rr, 0.075 + 0.08 * (1 - min(1, f * 1.4)))
                    seq.append([T.cx + rr * math.sin(phi), T.cy - rr * math.cos(phi), z])
                pts.append(np.array(seq))
            path = np.concatenate([pts[0], pts[1][::-1][1:]], 0)
            V, Fc = HD.tube_mesh(path, 0.007, sides=6, cap=False)
            meshes.append((a["name"], V, Fc, [{"UpperChest": 0.6, "Neck": 0.4}] * len(V), a.get("material", "cloth")))
        elif k == "forearm_band":
            S = "Left" if a["side"] == "l" else "Right"
            A_, B_ = J[f"{S}LowerArm"], J[f"{S}Hand"]
            c = A_ + (B_ - A_) * a.get("t", 0.6)
            sh = HD.band_ring(a["name"], fld, c, B_ - A_, (0, -1, 0), rad_guess=0.06, width=a["width"], offset=0.004,
                              thickness=0.005, material=a.get("material", "gear"), weights={f"{S}LowerArm": 1.0})
            sheets.append(sh)
        elif k == "lump":
            V, Fc = HD.box_mesh(np.array(a["at"], float), np.array(a["size"]) * 0.5, bevel=0.9, nseg=2)
            meshes.append((a["name"], V, Fc, [{a.get("bone", "UpperChest"): 1.0}] * len(V), a.get("material", "cloth")))
        elif k == "coil":
            at = np.array(a["at"], float)
            pts = []
            loops = a.get("loops", 4)
            for i in range(loops):
                th_ = np.linspace(0, 2 * math.pi, 14)
                rx, rz = a.get("rx", 0.05) * (1 + 0.08 * i), a.get("rz", 0.17) * (1 - 0.05 * i)
                loop = np.stack([at[0] + rx * np.sin(th_) + 0.006 * i, at[1] - 0.006 * i + 0.01 * np.cos(th_) * 0,
                                 at[2] - rz * (1 - np.cos(th_))], 1)
                V, Fc = HD.tube_mesh(loop, a.get("r", 0.011), sides=6, cap=False)
                meshes.append((f"{a['name']}{i}", V, Fc, [{"Bag": 1.0}] * len(V), a.get("material", "gear")))
        elif k == "hammer":
            at = np.array(a["at"], float)
            handle = np.array([at, at + np.array([0.0, 0.0, -a.get("len", 0.26)])])
            V, Fc = HD.tube_mesh(handle, 0.011, sides=6)
            meshes.append((a["name"] + "_handle", V, Fc, [{"Bag": 1.0}] * len(V), "gear"))
            V, Fc = HD.box_mesh(handle[1] + np.array([0, 0, -0.015]), (0.045, 0.02, 0.02), bevel=0.5, nseg=1)
            meshes.append((a["name"] + "_head", V, Fc, [{"Bag": 1.0}] * len(V), "gear"))
        elif k == "satchel":
            at = np.array(a["at"], float)
            V, Fc = HD.box_mesh(at, np.array(a["size"]) * 0.5, bevel=0.45, nseg=1)
            meshes.append((a["name"], V, Fc, [{"Bag": 1.0}] * len(V), a.get("material", "gear")))
            # strap from the opposite shoulder across the chest/back to the bag
            sh_side = -np.sign(at[0])
            top_z = C["L"]["shoulder_l"][1] + 0.05
            path = []
            for f in np.linspace(0, 1, 16):
                for face_sgn in (-1,):
                    pass
                z = top_z + (at[2] + a["size"][2] * 0.4 - top_z) * f
                x = sh_side * 0.10 + (at[0] - sh_side * 0.10) * f
                rr = float(T.hull(np.array([min(max(z, T.zs[0]), T.zs[-1])]), np.array([math.atan2(x, -0.3)]))[0])
                phi = math.atan2(x, -math.sqrt(max(rr * rr - x * x, 1e-6)))
                rr = float(T.hull(np.array([min(max(z, T.zs[0]), T.zs[-1])]), np.array([phi]))[0]) + 0.008
                path.append([T.cx + rr * math.sin(phi), T.cy - rr * math.cos(phi), z])
            path = np.array(path)
            nrm = path - np.array([T.cx, T.cy, 0]) * np.array([1, 1, 0])
            nrm[:, 2] = 0
            nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-6)
            sheets.append(HD.strip(a["name"] + "_strap", path, nrm, 0.035, material=a.get("material", "gear"),
                                   weights=[{"Chest": 0.6, "UpperChest": 0.4}] * (2 * len(path))))
        elif k == "tails":
            at = np.array(a["at"], float)
            for i, dx in enumerate(a.get("dx", (0.0, 0.03))):
                zs = np.linspace(at[2], at[2] - a["len"], 9)
                pts = []
                for zz in zs:
                    rr = float(T.hull(np.array([max(zz, T.zs[0])]), np.array([math.atan2(at[0] + dx, -0.2)]))[0]) + 0.02
                    phi = math.atan2(at[0] + dx, -0.2)
                    pts.append([T.cx + rr * math.sin(phi), T.cy - rr * math.cos(phi), zz])
                pts = np.array(pts)
                nrm = np.tile(np.array([0, -1.0, 0]), (len(pts), 1))
                wts = [{"Hips": 1 - min(1, j / 6) * 0.6, "SkirtFront1": min(1, j / 6) * 0.6} for j in range(len(pts)) for _ in range(2)]
                sheets.append(HD.strip(f"{a['name']}{i}", pts, nrm, a.get("width", 0.05), material=a.get("material", "cloth"),
                                       weights=wts))
        elif k in ("scabbard", "quiver"):
            top, bot = np.array(a["top"], float), np.array(a["bottom"], float)
            r = 0.022 if k == "scabbard" else 0.042
            if a["name"] == "knife":
                r = 0.014
            V, Fc = HD.tube_mesh(np.array([top, 0.5 * (top + bot), bot]), [r * 1.05, r, r * 0.8], sides=8)
            meshes.append((a["name"], V, Fc, [{"Hips": 1.0}] * len(V), a.get("material", "gear")))
            if k == "scabbard" and a["name"] != "knife":
                ax = (top - bot) / np.linalg.norm(top - bot)
                hilt = np.array([top, top + ax * 0.16])
                V, Fc = HD.tube_mesh(hilt, 0.012, sides=6)
                meshes.append((a["name"] + "_hilt", V, Fc, [{"Hips": 1.0}] * len(V), "gear"))
                V, Fc = HD.box_mesh(top + ax * 0.01, (0.06, 0.012, 0.012), bevel=0.5, nseg=1)
                meshes.append((a["name"] + "_guard", V, Fc, [{"Hips": 1.0}] * len(V), "gear"))
            if k == "quiver":
                for i in range(5):
                    off = np.array([0.012 * math.cos(i * 1.3), 0.012 * math.sin(i * 1.3), 0.0])
                    V, Fc = HD.tube_mesh(np.array([top + off, top + off + np.array([0.01, -0.01, 0.12])]), 0.006, sides=5)
                    meshes.append((f"arrow{i}", V, Fc, [{"Hips": 1.0}] * len(V), "gear"))
        elif k == "pouch":
            at = np.array(a["at"], float)
            V, Fc = HD.box_mesh(at, np.array(a["size"]) * 0.5, bevel=0.55, nseg=1)
            meshes.append((a["name"], V, Fc, [{"Bag": 1.0}] * len(V), a.get("material", "gear")))
            cord = np.array([at + np.array([0.004, 0.0, a["size"][2] * 0.5 + 0.10]), at + np.array([0.004, -0.004, a["size"][2] * 0.5])])
            V, Fc = HD.tube_mesh(cord, 0.006, sides=6)
            meshes.append((a["name"] + "_cord", V, Fc, [{"Bag": 1.0}] * len(V), a.get("material", "gear")))
    return sheets, meshes, T


# --------------------------------------------------------------------------- blender assembly

MAT_IDS = {"body": 0, "hair": 1, "cloth": 2, "gear": 3}


def build_objects(R, J):
    fld, parts, wparts, prof, bv, bf, sup = body_geometry(R, J)
    body = HBL.obj_from(f"{AID}_bodyHQ", bv, bf)
    # protect the face (front of the head) and ears from decimation
    o, S = HB.head_frame(C, J)

    def prot(vv):
        q = (vv - o) / S
        face = (q[:, 2] > -0.15) & (q[:, 2] < 0.08) & (q[:, 1] < 0.0)
        ears = (np.abs(q[:, 0]) > 0.06) & (q[:, 2] > -0.06) & (q[:, 2] < 0.03) & (np.abs(q[:, 1]) < 0.04)
        hands = vv[:, 2] < -10
        return np.where(face | ears, 1.0, 0.0) + hands
    t_body = {"civilian": 6400, "soldier": 6400}[C["kind"]]
    HBL.decimate(body, t_body, protect=prot, factor=1.0)
    HBL.smooth_shade(body)
    log("body tris", core.tri_count(body))
    bvv, btri, _, _ = core.mesh_arrays(body, evaluated=False)
    Wd = HRG.body_weights(bvv, parts, J)
    names, M = HRG.normalize_top4(Wd, len(bvv))
    M = HRG.smooth_weights(names, M, btri, iters=2, factor=0.5)
    names, M = HRG.normalize_top4({n: M[:, j] for j, n in enumerate(names)}, len(bvv))
    HRG.assign_groups(body, names, M)
    objs = [(body, "body", "body")]
    hv, hf = hair_geometry(R, J, fld)
    if hv is not None and len(hf):
        hair = HBL.obj_from(f"{AID}_hairHQ", hv, hf)
        HBL.decimate(hair, C["build"].get("hair_tris", 1500), stage=30000)
        HBL.smooth_shade(hair)
        hvv = np.array([v.co[:] for v in hair.data.vertices])
        hzj = J["Head"][2]
        wn = np.clip((hzj - hvv[:, 2]) / 0.08, 0, 0.6)
        HRG.groups_from_dicts(hair, [{"Head": 1 - w, "Neck": w} if w > 0.01 else {"Head": 1.0} for w in wn])
        objs.append((hair, "hair", "hair"))
        log("hair tris", core.tri_count(hair))
    for g in C.get("garments", []):
        if g["kind"] in ("hood", "cap", "helmet"):
            o_, S_ = HB.head_frame(C, J)
            lo = o_ + np.array([-0.18, -0.19, -0.30])
            hi = o_ + np.array([0.18, 0.21, 0.26])
            sf = F.Field(lo, hi, 0.0028)
            sf.d = HB.head_shell(C, J, R, fld, sf, g["kind"], g)
            if g.get("hull", True):
                sf.intersect_xz(R, k=0.012, dilate=0.003)
            v_, f_ = sf.mesh()
            ob = HBL.obj_from(f"{AID}_{g['name']}", v_, f_)
            HBL.decimate(ob, g.get("tris", 900), stage=20000)
            HBL.smooth_shade(ob)
            vv_ = np.array([v.co[:] for v in ob.data.vertices])
            if g["kind"] == "hood":
                wz = np.clip((J["Head"][2] - vv_[:, 2]) / 0.12, 0, 1)
                HRG.groups_from_dicts(ob, [{"Head": 1 - w * 0.7, "Hood": w * 0.3, "Neck": w * 0.4} for w in wz])
            else:
                HRG.groups_from_dicts(ob, [{"Head": 1.0}] * len(vv_))
            objs.append((ob, g.get("material", "cloth"), "garment"))
            log(g["name"], core.tri_count(ob), "tris")
    hands = hands_geometry(J)
    hand_bones = {}
    for S_, (acc, bones) in hands.items():
        V, Fc, Wts = acc.arrays()
        ob = HBL.obj_from(f"{AID}_hand_{S_}", V, Fc)
        HRG.groups_from_dicts(ob, Wts)
        objs.append((ob, "body", "hand"))
        hand_bones[S_] = bones
    sheets, meshes, T = garments(R, J, fld, prof, sup)
    for sh in sheets:
        ob = HBL.obj_from(f"{AID}_{sh.name}", sh.V, sh.faces())
        HRG.groups_from_dicts(ob, sh.weights)
        HBL.solidify(ob, sh.thickness, offset=-1.0 if not sh.closed_u else 1.0)
        objs.append((ob, sh.material, "garment"))
    for name, V, Fc, Wts, mat in meshes:
        ob = HBL.obj_from(f"{AID}_{name}", V, Fc)
        HRG.groups_from_dicts(ob, Wts)
        objs.append((ob, mat, "acc"))
    # ---- LOD0 triangle budget: thin the garment sheets first (flat cloth keeps its outline), then the body
    total = sum(core.tri_count(o) for o, _, _ in objs)
    limit = int(BUDGET[0] * 0.985) - (420 if C.get("weapon") else 0)   # hand-held props are added later
    if total > limit:
        gar = [(ob_, k_) for ob_, _, k_ in objs if k_ in ("garment", "acc")]
        g_tris = sum(core.tri_count(ob_) for ob_, _ in gar)
        excess = total - limit
        ratio = max(0.35, 1.0 - excess / max(g_tris, 1))
        for ob_, k_ in gar:
            n = core.tri_count(ob_)
            if n > 120:
                HBL.decimate(ob_, int(n * ratio), stage=10 ** 9)
        total = sum(core.tri_count(ob_) for ob_, _, _ in objs)
        if total > limit:
            n = core.tri_count(body)
            HBL.decimate(body, n - (total - limit), protect=prot, factor=1.0, stage=10 ** 9)
        log("budget pass: LOD0 tris", sum(core.tri_count(ob_) for ob_, _, _ in objs), "garment ratio", round(ratio, 2))
    ginfo = {}
    for g in C.get("garments", []):
        if g["kind"] == "skirt" and g.get("bones", "skirt") == "skirt":
            ginfo.setdefault("skirt_top", g["z_top"])
            hem = g.get("hem") or (g.get("hem_z", 0.4),) * 3
            ginfo.setdefault("skirt_hem", float(min(hem)))
        if g["kind"] == "cloak":
            ginfo["cloak_hem"] = g.get("hem_back", 0.9)
    for a in C.get("acc", []):
        if a["kind"] == "satchel" or (a["kind"] in ("pouch", "coil", "hammer") and "bag" not in ginfo):
            ginfo["bag"] = a["at"]
    return dict(field=fld, parts=parts, wparts=wparts, prof=prof, objs=objs, hand_bones=hand_bones, T=T, ginfo=ginfo)


def join_lod0(objs):
    """Join into one mesh with material index per part; face attribute 'region' for UV boost."""
    slots = [bpy.data.materials.get(f"_slot_{k}") or bpy.data.materials.new(f"_slot_{k}") for k in MAT_IDS]
    for ob, mat, kind in objs:
        mid = MAT_IDS[mat]
        me = ob.data
        me.materials.clear()
        for m in slots:
            me.materials.append(m)
        me.polygons.foreach_set("material_index", np.full(len(me.polygons), mid, np.int32))
        reg = np.zeros(len(me.polygons), np.int32)
        if kind in ("body", "hair"):
            cz = np.array([p.center.z for p in me.polygons])
            reg = (cz > C["L"]["chin"] - 0.04).astype(np.int32)
        if kind == "hand":
            reg[:] = 2
        HBL.face_attr(ob, "region", reg)
    lo = core.join([o for o, _, _ in objs], name=f"{AID}_LOD0")
    return lo


def make_materials(img):
    mats = []
    for nm in ("body", "hair", "cloth", "gear"):
        mats.append(HBL.painted_material(f"{AID}_{nm}_qa", img, k=0.0))
    return mats


def portrait_cam(J):
    pc = C.get("portrait")
    if not pc:
        return None
    import humans_refs as HR_
    box = HR_.PANELS[AID]["inset"]
    img = HR_.refs.crop(HR_.sheet(HR_.PANELS[AID]["sheet"]), box)
    lm3 = HB.head_landmarks(C, J)
    X3 = [lm3["eye_r"], lm3["eye_l"], lm3["mouth"]]
    x2 = [(pc["eye_r"][0] - box[0], pc["eye_r"][1] - box[1]), (pc["eye_l"][0] - box[0], pc["eye_l"][1] - box[1]),
          (pc["mouth"][0] - box[0], pc["mouth"][1] - box[1])]
    for key in ("nose", "chin"):
        if key in pc:
            X3.append(lm3[key])
            x2.append((pc[key][0] - box[0], pc[key][1] - box[1]))
    cam, params, err = HT.solve_portrait(X3, x2, img, weight=5.0)
    log("portrait solve", np.round(params, 3), "max px err", round(err, 2))
    # canonical landmark order for masks / SSIM: eye_r, eye_l, nose, mouth, chin
    pt = {k: (pc[k][0] - box[0], pc[k][1] - box[1]) for k in ("eye_r", "eye_l", "nose", "mouth", "chin") if k in pc}
    cam.lm2 = np.array([pt[k] for k in ("eye_r", "eye_l", "nose", "mouth", "chin") if k in pt])
    return dict(cam=cam, params=params.tolist(), err=err)


def clear_face_occluders(lo0, J):
    """Hair / hood / cap faces lying in front of the upper face skin (eyes, forehead, temples, upper
    cheeks) are removed, so no second layer crosses the painted face (hairline bands, the herbalist's
    hood rim and cheek fragment).  Hooded heads also lose the hair dome that pokes through the hood."""
    import bmesh
    from scipy.spatial import cKDTree
    o, S = HB.head_frame(C, J)
    L = C["L"]
    bm = bmesh.new()
    bm.from_mesh(lo0.data)
    bm.faces.ensure_lookup_table()
    cen = np.array([f.calc_center_median()[:] for f in bm.faces])
    nrm = np.array([f.normal[:] for f in bm.faces])
    mat = np.array([f.material_index for f in bm.faces])
    head = (cen[:, 2] > L["chin"] - 0.01) & (np.abs(cen[:, 0]) < 0.2)
    box = (np.abs(cen[:, 0]) < 0.052 * S[0]) & (cen[:, 2] > 0.5 * (L["eye"] + L["mouth"])) & (cen[:, 2] < L["eye"] + 0.055)
    skin = head & box & (mat == MAT_IDS["body"]) & (nrm[:, 1] < -0.3)
    kill = np.zeros(len(cen), bool)
    if skin.sum() >= 20:
        t = cKDTree(cen[skin][:, [0, 2]])
        occ = head & box & (mat != MAT_IDS["body"])
        if occ.any():
            d, i = t.query(cen[occ][:, [0, 2]])
            front = (cen[occ][:, 1] < cen[skin][i, 1] - 0.002) & (d < 0.012)
            kill[np.nonzero(occ)[0][front]] = True
    hooded = any(g.get("kind") == "hood" for g in C.get("garments", []) + C.get("acc", []))
    if kill.any():
        bmesh.ops.delete(bm, geom=[bm.faces[int(k)] for k in np.nonzero(kill)[0]], context="FACES")
        bm.to_mesh(lo0.data)
        lo0.data.update()
    bm.free()
    log("face occluders removed (hair/shell faces over the upper face):", int(kill.sum()))


FRONT_FACES = True   # every face from the front painting (no portrait projection); portrait only lays out UVs


def texture(lo0, R, J, pinfo0=None):
    """Single source per feature.  Face (forehead..chin, cheek..jaw, feathered mask): the expression
    portrait projected from ITS OWN solved camera (yaw/pitch/roll/scale, |n.v| >= 0.5, skin + hair
    only); the painted front view never paints that region.  Everything else: front/back paintings
    with |n.v| >= 0.35 (head: >= 0.5); the rest synthesised per material and head/body (head skin
    from the character's own cheek colour, hair with strand detail from the painted hair)."""
    import cv2 as _cv
    if FRONT_FACES:
        pinfo0 = None
    verts, tris, uv, vn = core.mesh_arrays(lo0, evaluated=False)
    T = texproj.rasterize_uv(verts, tris, uv, TEX, vn)
    o, S = HB.head_frame(C, J)
    chin = C["L"]["chin"]
    yy0, xx0 = np.nonzero(T.valid)
    P0 = T.pos[yy0, xx0]
    me_ = lo0.data
    me_.calc_loop_triangles()
    tp_ = np.empty(len(me_.loop_triangles), np.int64)
    me_.loop_triangles.foreach_get("polygon_index", tp_)
    mi_ = np.array([p.material_index for p in me_.polygons])
    tex_mat = mi_[tp_[T.tri[yy0, xx0]]]
    skin_hair = (tex_mat == MAT_IDS["body"]) | (tex_mat == MAT_IDS["hair"])

    def is_head(P):
        return (P[:, 2] > chin - 0.07) & (np.abs(P[:, 0]) < 0.20)

    # head skin: the painted face region is bounded by natural edges - hairline (hair is its own material),
    # the jaw / neck and the ears - not by per-triangle normals (decimated facets made a patchwork across
    # the cheeks): facing is measured with a smooth proxy normal (tall head ellipsoid above the chin,
    # neck cylinder below), so the front paints the whole face and the fade sits between cheek and ear
    head_skin_t = is_head(P0) & (tex_mat == MAT_IDS["body"])
    hc = np.array([0.0, o[1] + 0.012, C["L"]["eye"] - 0.012])
    rad = np.array([0.080 * S[0], 0.100 * S[1], 0.200 * S[2]])
    neck_y = float(J["Neck"][1])

    def proxy_n(P):
        q = (P - hc) / rad ** 2
        ne = q / np.maximum(np.linalg.norm(q, axis=1, keepdims=True), 1e-9)
        qc = np.stack([P[:, 0], P[:, 1] - neck_y, np.zeros(len(P))], 1)
        nc = qc / np.maximum(np.linalg.norm(qc, axis=1, keepdims=True), 1e-9)
        t = np.clip((P[:, 2] - (chin - 0.03)) / 0.04, 0.0, 1.0)[:, None]
        n = ne * t + nc * (1.0 - t)
        return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)

    def nfn(P, N):
        return np.where(head_skin_t[:, None], proxy_n(P), N) if FRONT_FACES else N

    def lohi(P):
        h = is_head(P)
        lo_ = np.where(h, 0.50, 0.35)
        hi_ = np.where(h, 0.68, 0.55)
        if FRONT_FACES:
            lo_ = np.where(head_skin_t, 0.30, lo_)
            hi_ = np.where(head_skin_t, 0.50, hi_)
        return lo_, hi_
    vis_eps_t = np.where(is_head(P0), 0.012, 0.006)
    views = [R.front, R.back]
    pinfo = pinfo0
    cheek_ref = None
    med_l = None
    skin_med = None
    wport = np.zeros(len(P0))
    col2 = np.zeros((len(P0), 3))
    if pinfo0:
        cam = pinfo0["cam"]
        # feathered face mask in the portrait image: forehead..chin, temples/cheeks..jaw angles
        ctrl = HT.face_controls(*[np.array(p) for p in cam.lm2[:5]])
        hull = _cv.convexHull(ctrl[[5, 6, 8, 10, 12, 4, 13, 11, 9, 7]].astype(np.float32))[:, 0, :]
        m = np.zeros(cam.image.shape[:2], np.uint8)
        _cv.fillPoly(m, [np.round(hull).astype(np.int32)], 1)
        feat = _cv.GaussianBlur(m.astype(np.float32), (0, 0), 4.0)
        img_ = cam.image
        border = np.concatenate([img_[:4].reshape(-1, 3), img_[:, :4].reshape(-1, 3), img_[:, -4:].reshape(-1, 3)])
        from scipy import ndimage as _ndi
        fg = _ndi.binary_erosion(_ndi.binary_opening(np.linalg.norm(img_[..., :3] - np.median(border, 0), axis=-1) > 0.10,
                                                     iterations=1), iterations=2)
        cam.mask = cam.mask & (feat > 0.02) & fg

        def pfeather(P):
            u, v, _ = cam.project(P)
            return texproj._bilinear(feat[..., None], u, v)[:, 0]
        d2, c2, ws2, per2 = HT.project_views(T, verts, tris, [cam], lo=0.50, hi=0.72, erode=0, vis_eps=0.02,
                                             region={"portrait": (lambda P: pfeather(P) * is_head(P))})
        wport = np.clip(ws2, 0, 1) * skin_hair
        col2 = c2
        # hair locks painted over the temples / forehead edge of the portrait never land on head skin:
        # outside the inner face (eyes + brows .. chin) dark portrait pixels on skin texels are dropped
        er_, el_, no_, mo_, ch_ = [np.array(p_, float) for p_ in cam.lm2[:5]]
        up_ = (er_ + el_) / 2 - mo_
        inner = np.array([er_ + up_ * 0.55 + (er_ - el_) * 0.10, el_ + up_ * 0.55 + (el_ - er_) * 0.10,
                          el_ + (el_ - er_) * 0.12, mo_ + (el_ - er_) * 0.35, ch_, mo_ + (er_ - el_) * 0.35,
                          er_ + (er_ - el_) * 0.12])
        im_in = np.zeros(cam.image.shape[:2], np.uint8)
        _cv.fillPoly(im_in, [np.round(_cv.convexHull(inner.astype(np.float32))[:, 0, :]).astype(np.int32)], 1)
        u2_, v2_ = per2["portrait"][1], per2["portrait"][2]
        in_inner = texproj._bilinear(im_in.astype(np.float32)[..., None], u2_, v2_)[:, 0] > 0.5
        lum2 = col2 @ np.array([0.299, 0.587, 0.114])
        skin_t = (tex_mat == MAT_IDS["body"]) & is_head(d2[2])
        ref_sk = skin_t & in_inner & (wport > 0.5)
        if ref_sk.sum() > 100:
            med_l = float(np.median(lum2[ref_sk]))
            skin_med = np.median(col2[ref_sk], 0)
            dark = skin_t & (~in_inner) & (lum2 < 0.75 * med_l) & (wport > 0)
            wport = np.where(dark, 0.0, wport)
            # and skin-coloured portrait pixels never land on hair geometry beside the face (hood openings)
            log("portrait: dark (hair) pixels dropped from head skin", int(dark.sum()))
    # painted front/back views; the front never paints where the portrait paints (complementary)
    data, col, ws, per = HT.project_views(T, verts, tris, views, erode=2, lo_hi_fn=lohi, vis_eps=vis_eps_t,
                                          normal_fn=nfn)
    wf, uf, vf = per["front"]
    wb, ub, vb = per["back"]
    # hoods / caps / helmets never take the painted face pixels (herbalist hood rim)
    lm3 = HB.head_landmarks(C, J)
    fp = np.array([R.front.project(lm3[k])[:2] for k in ("eye_r", "eye_l", "nose", "mouth", "chin")])
    fctrl = HT.face_controls(*fp)
    fhull = _cv.convexHull(fctrl[[5, 6, 8, 10, 12, 4, 13, 11, 9, 7]].astype(np.float32))[:, 0, :]
    fm = np.zeros(R.front.image.shape[:2], np.uint8)
    _cv.fillPoly(fm, [np.round(fhull).astype(np.int32)], 1)
    in_face_px = texproj._bilinear(fm.astype(np.float32)[..., None], uf, vf)[:, 0] > 0.5
    wf = np.where((~skin_hair) & is_head(data[2]) & in_face_px, 0.0, wf)
    if pinfo0:
        # single source: with a portrait, the painted front never textures the face region (the portrait
        # fades out by |n.v| toward the profiles and the sides get synthesised cheek skin instead)
        wf = np.where(is_head(data[2]) & in_face_px, 0.0, wf)
    wf = wf * (1.0 - wport)
    colf = texproj._bilinear(R.front.image, uf, vf)[:, :3]
    colb = texproj._bilinear(R.back.image, ub, vb)[:, :3]
    if FRONT_FACES:
        # inner face (eyes + brows .. mouth .. chin) in the front painting: everything there is kept;
        # outside it, dark painted pixels (hair locks, hat shadow, collar) never land on head skin
        er_, el_, no_, mo_, ch_ = [np.array(p_, float) for p_ in fp]
        up_ = (er_ + el_) / 2 - mo_
        inner = np.array([er_ + up_ * 0.60 + (er_ - el_) * 0.15, el_ + up_ * 0.60 + (el_ - er_) * 0.15,
                          el_ + (el_ - er_) * 0.25, mo_ + (el_ - er_) * 0.45, ch_ + (ch_ - mo_) * 0.3,
                          mo_ + (er_ - el_) * 0.45, er_ + (er_ - el_) * 0.25])
        im_in = np.zeros(R.front.image.shape[:2], np.uint8)
        _cv.fillPoly(im_in, [np.round(_cv.convexHull(inner.astype(np.float32))[:, 0, :]).astype(np.int32)], 1)
        in_inner_f = texproj._bilinear(im_in.astype(np.float32)[..., None], uf, vf)[:, 0] > 0.5
        lw = np.array([0.299, 0.587, 0.114])
        hs_ = is_head(data[2]) & (tex_mat == MAT_IDS["body"])
        ref_f = hs_ & in_inner_f & (wf > 0.5)
        if ref_f.sum() > 50:
            med_l = float(np.median(colf[ref_f] @ lw))
            skin_med = np.median(colf[ref_f], 0)
            dk_f = hs_ & (~in_inner_f) & ((colf @ lw) < 0.55 * med_l)
            dk_b = hs_ & ((colb @ lw) < 0.55 * med_l)
            wf = np.where(dk_f, 0.0, wf)
            wb = np.where(dk_b, 0.0, wb)
            log("front face: skin", np.round(skin_med, 3), "dark pixels dropped outside the inner face",
                int((dk_f & (per["front"][0] > 0)).sum()), "back", int((dk_b & (per["back"][0] > 0)).sum()))
            if True:
                # hair (hairline, sideburns, beard edges, hair under a hood) never takes the painted face's
                # skin: the light bands where the hair volume overlaps the painted forehead / cheeks
                hr_ = is_head(data[2]) & (tex_mat == MAT_IDS["hair"]) & (~in_inner_f) & (data[2][:, 2] > C["L"]["eye"])
                sk_on_hair = hr_ & (np.linalg.norm(colf - skin_med, axis=1) < 0.15) & ((colf @ lw) > 0.7 * med_l)
                wf = np.where(sk_on_hair, 0.0, wf)
                log("painted skin dropped from the hair outside the inner face", int(sk_on_hair.sum()))
                # caps / hoods / helmets: no painted skin on the shell either (cap brim edge, hood rim)
                sh_ = is_head(data[2]) & (~skin_hair)
                sk_on_shell = sh_ & (np.linalg.norm(colf - skin_med, axis=1) < 0.17) & ((colf @ lw) > 0.6 * med_l)
                wf = np.where(sk_on_shell, 0.0, wf)
                log("painted skin dropped from head shells", int(sk_on_shell.sum()))
    if any(g.get("kind") == "hood" for g in C.get("garments", []) + C.get("acc", [])):
        # hood: painted pixels unlike the hood's own cloth (face / hair seen through the wider painted
        # opening) never texture the hood shell - it is synthesised from its own cloth instead
        # (skin-coloured painted pixels only: the painted hair framing the face stays on the hood rim)
        shell_t = is_head(data[2]) & (~skin_hair)
        if skin_med is not None:
            lw_ = np.array([0.299, 0.587, 0.114])
            far_f = shell_t & (np.linalg.norm(colf - skin_med, axis=1) < 0.17) & ((colf @ lw_) > 0.6 * med_l)
            far_b = shell_t & (np.linalg.norm(colb - skin_med, axis=1) < 0.17) & ((colb @ lw_) > 0.6 * med_l)
            wf = np.where(far_f, 0.0, wf)
            wb = np.where(far_b, 0.0, wb)
            log("hood: painted skin pixels dropped from the hood", int((far_f & (per["front"][0] > 0)).sum()))
    if pinfo0 and med_l is not None:
        # painted hair / collar shadow over the temples and neck never lands on head skin either
        hs_ = is_head(data[2]) & (tex_mat == MAT_IDS["body"])
        lw = np.array([0.299, 0.587, 0.114])
        dk_f = hs_ & ((colf @ lw) < 0.60 * med_l)
        dk_b = hs_ & ((colb @ lw) < 0.60 * med_l)
        wf = np.where(dk_f, 0.0, wf)
        wb = np.where(dk_b, 0.0, wb)
        log("front/back: dark pixels dropped from head skin", int((dk_f & (per["front"][0] > 0)).sum()),
            int((dk_b & (per["back"][0] > 0)).sum()))
    if pinfo0:
        both = (wf > 0.2) & (wport > 0.2)
        gain = np.ones(3)
        sel_tone = is_head(data[2]) & skin_hair & (wport > 0.3)
        ref = per["front"][0] > 0.3
        if (sel_tone & ref).sum() > 100:
            gain = np.clip(np.median(colf[sel_tone & ref], 0) / np.maximum(np.median(col2[sel_tone & ref], 0), 1e-3),
                           0.8, 1.2)
        gain = np.sqrt(gain)
        col2 = np.clip(col2 * gain, 0, 1)
        log("portrait (own camera) gain", np.round(gain, 3), "face texels", int((wport > 0.5).sum()))
        sk_in = is_head(data[2]) & (tex_mat == MAT_IDS["body"]) & in_inner & (wport > 0.7)
        cheek_ref = np.median(col2[sk_in], 0) if sk_in.sum() > 200 else None
    ws = wf + wb + wport * 4.0
    col = (colf * wf[:, None] + colb * wb[:, None] + col2 * (wport * 4.0)[:, None]) / np.maximum(ws, 1e-9)[:, None]
    per["front"] = (wf, uf, vf)
    per["back"] = (wb, ub, vb)
    if pinfo0:
        per["portrait"] = (wport, *per2["portrait"][1:])
    # head skin that no view sees well: the character's own cheek colour (no pink patches)
    head_skin = is_head(data[2]) & (tex_mat == MAT_IDS["body"])
    seen_face = head_skin & (ws > 0.5)
    cheek = np.median(col[seen_face], 0) if seen_face.sum() > 50 else None
    if cheek is not None and False:
        weak = head_skin & (ws < 0.06)
        col[weak] = cheek
        ws = np.where(weak, 0.30, ws)
        log("head skin fill colour", np.round(cheek, 3), "texels", int(weak.sum()))
    mi = np.array([p.material_index for p in lo0.data.polygons])
    lt = np.empty(len(lo0.data.loop_triangles), np.int64) if False else None
    me = lo0.data
    me.calc_loop_triangles()
    tri_poly = np.empty(len(me.loop_triangles), np.int64)
    me.loop_triangles.foreach_get("polygon_index", tri_poly)
    yy, xx = data[0], data[1]
    group = mi[tri_poly[T.tri[yy, xx]]] * 2 + is_head(data[2]).astype(np.int64)
    col, seen = HT.synthesize(T, data, col, ws, per, views, group=group)
    log("texture: seen fraction", round(float(seen.mean()), 3))
    if pinfo0 and cheek_ref is not None:
        # side cheeks / jaw / temples no view paints: skin synthesised from the character's own cheek
        # (median colour of the portrait-painted cheek skin) over the low-frequency fill, with a soft
        # blotch noise so no area is a flat patch
        head_skin2 = is_head(data[2]) & (tex_mat == MAT_IDS["body"])
        k_s = np.clip(1.0 - ws / 0.5, 0.0, 1.0) * head_skin2
        sel = np.nonzero(k_s > 0)[0]
        if len(sel):
            Pw = data[2][sel]
            nz = (0.55 * HT._vnoise(Pw[:, 0] / 0.011 + 3.1 * HT._vnoise(Pw[:, 2] / 0.017, 3), 11)
                  + 0.45 * HT._vnoise(Pw[:, 2] / 0.009 + 2.3 * HT._vnoise(Pw[:, 1] / 0.013, 5), 12))
            kk = k_s[sel][:, None]
            base = col[sel] * (1 - 0.55 * kk) + cheek_ref[None, :] * 0.55 * kk
            col[sel] = np.clip(base * (1.0 + 0.045 * nz[:, None] * kk), 0, 1)
            log("cheek skin synthesis texels", len(sel), "cheek colour", np.round(cheek_ref, 3))
    hooded = any(g.get("kind") == "hood" for g in C.get("garments", []) + C.get("acc", []))
    if hooded:
        # inside a hood the sides / back of the head read as hair in the painting (no skin beside the face
        # opening): synthesised head skin behind the face plane takes the painted hair colour + strands
        hair_seen = (tex_mat == MAT_IDS["hair"]) & is_head(data[2]) & (ws > 0.5)
        if hair_seen.sum() > 100:
            hair_med = np.median(col[hair_seen], 0)
            sk = is_head(data[2]) & (tex_mat == MAT_IDS["body"]) & (ws < 0.3) & (data[2][:, 1] > o[1] + 0.015) \
                & (data[2][:, 2] > C["L"]["mouth"] - 0.01)
            col[sk] = hair_med
            tex_mat = np.where(sk, MAT_IDS["hair"], tex_mat)
            log("hooded: head sides under the hood -> hair colour, texels", int(sk.sum()))
    # hair the paintings do not reach (sides, crown, under the beard): strand-direction texture on the
    # synthesised base colour (no smooth "bowl" gradients); painted hair keeps its own strands
    hair_t = (tex_mat == MAT_IDS["hair"]) & is_head(data[2])
    if hair_t.any():
        crown = np.array([0.0, o[1] + 0.012, C["L"]["top"] - 0.035])
        k_syn = np.clip(1.0 - ws / 0.6, 0.0, 1.0)
        fac = HT.hair_strands(data[2][hair_t], crown)
        kk = k_syn[hair_t][:, None]
        col[hair_t] = np.clip(col[hair_t] * (1.0 + (fac[:, None] - 1.0) * (0.35 + 0.65 * kk)), 0, 1)
        log("hair strand synthesis texels", int(hair_t.sum()), "mostly synthesised", int((k_syn[hair_t] > 0.5).sum()))
    img = HT.to_image(T, data, col)
    p_png = paths.texture_master(GROUP, f"{AID}_color_master.png")
    core.save_rgba(p_png, img)
    from PIL import Image
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(p_png.replace("_color_master.png", "_color.jpg"),
                                                                           quality=90)
    return p_png, pinfo


def qa_renders(lo0, R, J, mats, pinfo):
    HBL.qa_scene(samples=10)
    res = {}
    for which, view in (("front", R.front), ("back", R.back)):
        HBL.ortho_cam_for_view(view, scale=3)
        rgba = HBL.render_rgba()
        m = HBL.compare_sheet(view.image, view.mask, rgba, qa(f"{which}.png"),
                              f"{AID} v2 iter{ITER:02d} {which}: reference | render | IoU | colour error")
        res[which] = m
        log(which, m)
    if pinfo:
        import humans_refs as HR
        cam = pinfo["cam"]
        HBL.affine_cam(cam, scale=2)
        rgba = HBL.render_rgba()
        import cv2
        ref = cam.image
        H, W = ref.shape[:2]
        small = cv2.resize(rgba, (W, H), interpolation=cv2.INTER_AREA)
        bgc = np.array([0.85, 0.8, 0.72])
        comp = small[..., :3] * small[..., 3:4] + bgc * (1 - small[..., 3:4])
        mask = small[..., 3] > 0.5
        s = HBL.ssim_gray(comp, ref, mask)
        import cv2 as _cv
        lm2 = cam.lm2
        hull = _cv.convexHull(lm2.astype(np.float32))[:, 0, :]
        ctr = hull.mean(0)
        hull = ctr + (hull - ctr) * 1.45
        fm = np.zeros(ref.shape[:2], np.uint8)
        _cv.fillPoly(fm, [np.round(hull).astype(np.int32)], 1)
        s_face = HBL.ssim_gray(comp, ref, fm.astype(bool) & mask)
        big = cv2.resize(ref, (W * 2, H * 2), interpolation=cv2.INTER_CUBIC)
        compb = rgba[..., :3] * rgba[..., 3:4] + bgc * (1 - rgba[..., 3:4])
        sheet = np.concatenate([HBL._label((np.clip(big, 0, 1) * 255).astype(np.uint8), "portrait (sheet)"),
                                HBL._label((np.clip(compb, 0, 1) * 255).astype(np.uint8), f"model, same framing SSIM {s:.3f} face {s_face:.3f}")], 1)
        core.save_rgba(qa("portrait.png"), sheet / 255.0)
        res["portrait"] = {"ssim": round(s, 4), "ssim_face": round(s_face, 4), "solve_err_px": round(pinfo["err"], 2)}
        log("portrait", res["portrait"])
    # 3/4 views and side
    zc = C["L"]["top"] * 0.5
    tiles = []
    for yaw in (-35, 35, 90, 145):
        a = math.radians(yaw)
        loc = (math.sin(a) * 6.0, -math.cos(a) * 6.0, zc + 0.6)
        HBL.look_at_cam(loc, (0, 0, zc), ortho_scale=C["L"]["top"] * 1.12, res=(520, 980))
        rgba = HBL.render_rgba()
        bg = np.array([0.80, 0.78, 0.74])
        tiles.append(np.clip(rgba[..., :3] * rgba[..., 3:4] + bg * (1 - rgba[..., 3:4]), 0, 1))
    core.save_rgba(qa("views.png"), np.concatenate(tiles, 1))
    # face close-up 3/4
    o, S = HB.head_frame(C, J)
    tiles = []
    for yaw in (0, -30, 30):
        a = math.radians(yaw)
        tgt = (0, 0, o[2] - 0.02)
        HBL.look_at_cam((math.sin(a) * 3, -math.cos(a) * 3, o[2] + 0.05), tgt, ortho_scale=0.36, res=(420, 420))
        rgba = HBL.render_rgba()
        bg = np.array([0.80, 0.78, 0.74])
        tiles.append(np.clip(rgba[..., :3] * rgba[..., 3:4] + bg * (1 - rgba[..., 3:4]), 0, 1))
    core.save_rgba(qa("face.png"), np.concatenate(tiles, 1))
    # duplicate-feature check: head at 5 angles (front, 3/4 L/R, profile L/R), large
    tiles = []
    for yaw in (0, -45, 45, -90, 90):
        a = math.radians(yaw)
        HBL.look_at_cam((math.sin(a) * 3, -math.cos(a) * 3, o[2] + 0.02), (0, 0.005, o[2] - 0.02), ortho_scale=0.36,
                        res=(460, 520))
        rgba = HBL.render_rgba()
        tiles.append(np.clip(rgba[..., :3] * rgba[..., 3:4] + np.array([0.80, 0.78, 0.74]) * (1 - rgba[..., 3:4]), 0, 1))
    core.save_rgba(qa("heads5_blender.png"), np.concatenate(tiles, 1))
    # clay (geometry only) views
    clay_img = bpy.data.images.new("clay", 8, 8)
    clay_img.generated_color = (0.72, 0.70, 0.66, 1.0)
    clay = HBL.painted_material("clay_qa", clay_img, k=0.85, light=(-0.5, -0.7, 0.6))
    saved = list(lo0.data.materials)
    lo0.data.materials.clear()
    for _ in saved:
        lo0.data.materials.append(clay)
    tiles = []
    for yaw in (0, -35, 35, 90, 180):
        a = math.radians(yaw)
        HBL.look_at_cam((math.sin(a) * 6.0, -math.cos(a) * 6.0, zc + 0.6), (0, 0, zc), ortho_scale=C["L"]["top"] * 1.12,
                        res=(440, 900))
        rgba = HBL.render_rgba()
        tiles.append(np.clip(rgba[..., :3] * rgba[..., 3:4] + 0.86 * (1 - rgba[..., 3:4]), 0, 1))
    core.save_rgba(qa("clay.png"), np.concatenate(tiles, 1))
    tiles = []
    for yaw in (0, -40, 40, 90):
        a = math.radians(yaw)
        HBL.look_at_cam((math.sin(a) * 3, -math.cos(a) * 3, o[2] + 0.05), (0, 0, o[2] - 0.02), ortho_scale=0.34,
                        res=(400, 400))
        rgba = HBL.render_rgba()
        tiles.append(np.clip(rgba[..., :3] * rgba[..., 3:4] + 0.86 * (1 - rgba[..., 3:4]), 0, 1))
    core.save_rgba(qa("clay_head.png"), np.concatenate(tiles, 1))
    lo0.data.materials.clear()
    for m in saved:
        lo0.data.materials.append(m)
    with open(qa("metrics.json"), "w") as f:
        json.dump(res, f, indent=1)
    return res


def main():
    core.reset(fps=30)
    R = F.Refs(AID)
    log("refs: front/back consensus IoU", round(R.iou_fb, 3))
    J = HB.joints(C)
    B = build_objects(R, J)
    lo0 = join_lod0(B["objs"])
    clear_face_occluders(lo0, J)
    reg = HBL.face_attr_get(lo0, "region")
    HBL.uv_layout(lo0, boost_faces=reg == 1, boost=2.0)
    pinfo0 = portrait_cam(J)
    # dedicated face island: front-facing head polygons projected with the portrait camera (or the
    # front view when the sheet has no portrait)
    me = lo0.data
    cen = np.array([p.center[:] for p in me.polygons])
    nrm = np.array([p.normal[:] for p in me.polygons])
    o, S = HB.head_frame(C, J)
    if pinfo0:
        cam = pinfo0["cam"]
        facing = nrm @ (-cam.d)
        proj = lambda P: cam.project(P)[:2]  # noqa: E731
    else:
        facing = -nrm[:, 1]
        proj = lambda P: (P[:, 0], -P[:, 2])  # noqa: E731
    face_sel = (reg == 1) & (facing > 0.15) & (cen[:, 1] < o[1] + 0.02) & (cen[:, 2] > C["L"]["chin"] - 0.05) \
        & (np.abs(cen[:, 0]) < 0.085 * S[0])
    HBL.uv_face_island(lo0, face_sel, proj, island=0.40)
    log("LOD0 tris", core.tri_count(lo0), "face island polys", int(face_sel.sum()))
    p_png, pinfo = texture(lo0, R, J, pinfo0)
    img = core.load_image(p_png)
    mats = make_materials(img)
    lo0.data.materials.clear()
    for m in mats:
        lo0.data.materials.append(m)
    res = qa_renders(lo0, R, J, mats, pinfo)
    res["tris_LOD0"] = core.tri_count(lo0)
    log("done", json.dumps(res))
    if STAGE == "full":
        import hv2_finish as FIN
        FIN.finish(AID, C, R, J, B, lo0, p_png, ITER, log)


if __name__ == "__main__":
    main()
