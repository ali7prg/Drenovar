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
        + HB.head_parts(C, J)
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
    """Hair/beard = body field offset by a regional thickness, cut at the hairline/beard line,
    clipped by the painted outline (visual hull)."""
    o, S = HB.head_frame(C, J)
    lo = o + np.array([-0.15, -0.16, -0.19])
    hi = o + np.array([0.15, 0.18, 0.22])
    hi[2] = max(hi[2], C["L"]["top"] + 0.05)
    fld = F.Field(lo, hi, VOX * 0.8)
    P = fld.points(np.zeros(3, int), fld.n)
    db = body_field.sample(P.reshape(-1, 3)).reshape(P.shape[:3])
    fld.d = HB.hair_sdf(C, J, P, db).astype(np.float32)
    fld.intersect_xz(R, k=0.018, dilate=0.004)
    v, f = fld.mesh()
    log("hair MC", len(v), "verts", len(f), "tris")
    return v, f


def hands_geometry(J):
    L = C["L"]
    out = {}
    for S, s, sx in HB.SIDES:
        el, wr = J[f"{S}LowerArm"], J[f"{S}Hand"]
        fa = (wr - el) / np.linalg.norm(wr - el)
        medial = np.array([-sx, 0.0, 0.0])
        d = fa + 0.10 * medial + np.array([0, -0.10, 0])
        d /= np.linalg.norm(d)
        palm_n = medial * 0.92 + np.array([0, -0.38, 0])
        thumb_t = np.array([0, -1.0, 0.0])
        acc, bones = HH.build_hand(S, wr - fa * 0.008, d, palm_n, thumb_t, scale=L["hand_scale"],
                                   palm_len=0.088, female=C["female"])
        out[S] = (acc, bones)
    return out


def skirt_weights_fn(z_top, cx, cy, hem_lo):
    def fn(V):
        W = []
        for p in V.reshape(-1, 3):
            v = np.clip((z_top - p[2]) / max(z_top - hem_lo, 1e-3), 0, 1)
            phi = math.atan2(p[0] - cx, -(p[1] - cy))
            ap = abs(phi)
            wh = 1 - HT.smoothstep(0.0, 0.32, v)
            rest = 1 - wh
            lvl2 = HT.smoothstep(0.45, 0.8, v)
            d = {"Hips": wh}
            if ap < math.radians(55):
                d["SkirtFront1"] = rest * (1 - lvl2)
                d["SkirtFront2"] = rest * lvl2
            elif ap > math.radians(125):
                d["SkirtBack1"] = rest * (1 - lvl2)
                d["SkirtBack2"] = rest * lvl2
            else:
                d["SkirtLeft" if phi > 0 else "SkirtRight"] = rest
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
    for g in C.get("garments", []):
        if g["kind"] == "skirt":
            hem = g.get("hem")
            if hem is None:
                hz_ = g.get("hem_z", 0.4)
                hem = (hz_, hz_, hz_)

            def hem_fn(p, hem=hem):
                ap = abs(p)
                return float(np.interp(ap, [0, math.pi / 2, math.pi], hem))
            ph0, ph1 = (math.radians(a) for a in g["wrap"])
            sh = HD.drape_skirt(g["name"], T, R, g["z_top"], hem_fn, ph0, ph1, offset=g.get("offset", 0.012),
                                flare=g.get("flare", 0.03), fit=g.get("fit"), nu=g.get("nu", 34), nv=g.get("nv", 18),
                                material=g.get("material", "cloth"), thickness=g.get("thickness", 0.005),
                                weights_fn=skirt_weights_fn(g["z_top"], T.cx, T.cy, min(hem)),
                                ragged=g.get("ragged", 0.004), seed=len(sheets), fit_rows=g.get("fit_rows"),
                                closed=g.get("closed", False), cap_fn=arm_cap_fn(J))
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
    t_body = {"civilian": 6400, "soldier": 6600}[C["kind"]]
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
        HBL.decimate(hair, 1100, stage=20000)
        HBL.smooth_shade(hair)
        hvv = np.array([v.co[:] for v in hair.data.vertices])
        hzj = J["Head"][2]
        wn = np.clip((hzj - hvv[:, 2]) / 0.08, 0, 0.6)
        HRG.groups_from_dicts(hair, [{"Head": 1 - w, "Neck": w} if w > 0.01 else {"Head": 1.0} for w in wn])
        objs.append((hair, "hair", "hair"))
        log("hair tris", core.tri_count(hair))
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
    limit = int(BUDGET[0] * 0.985)
    if total > limit:
        gar = [(o, k) for o, _, k in objs if k in ("garment", "acc")]
        g_tris = sum(core.tri_count(o) for o, _ in gar)
        excess = total - limit
        ratio = max(0.35, 1.0 - excess / max(g_tris, 1))
        for o, k in gar:
            n = core.tri_count(o)
            if n > 120:
                HBL.decimate(o, int(n * ratio), stage=10 ** 9)
        total = sum(core.tri_count(o) for o, _, _ in objs)
        if total > limit:
            n = core.tri_count(body)
            HBL.decimate(body, n - (total - limit), protect=prot, factor=1.0, stage=10 ** 9)
        log("budget pass: LOD0 tris", sum(core.tri_count(o) for o, _, _ in objs), "garment ratio", round(ratio, 2))
    ginfo = {}
    for g in C.get("garments", []):
        if g["kind"] == "skirt" and g.get("bones", "skirt") == "skirt":
            ginfo.setdefault("skirt_top", g["z_top"])
            hem = g.get("hem") or (g.get("hem_z", 0.4),) * 3
            ginfo.setdefault("skirt_hem", float(min(hem)))
        if g["kind"] == "cloak":
            ginfo["cloak_hem"] = g.get("hem_back", 0.9)
    for a in C.get("acc", []):
        if a["kind"] in ("pouch", "satchel"):
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


def texture(lo0, R, J):
    verts, tris, uv, vn = core.mesh_arrays(lo0, evaluated=False)
    T = texproj.rasterize_uv(verts, tris, uv, TEX, vn)
    views = [R.front, R.back]
    data, col, ws, per = HT.project_views(T, verts, tris, views, lo=0.35, hi=0.55, erode=2)
    # portrait (civilians): scaled orthographic camera solved from landmarks
    pinfo = None
    pc = C.get("portrait")
    if pc:
        import humans_refs as HR
        box = HR.PANELS[AID]["inset"]
        img = HR.refs.crop(HR.sheet(HR.PANELS[AID]["sheet"]), box)
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
        o, S = HB.head_frame(C, J)
        chin = C["L"]["chin"]

        def head_region(P):
            q = P - o
            near = np.exp(-np.maximum(0, (q[:, 1] + 0.0)) / 0.06)
            return (P[:, 2] > chin - 0.035) * near

        d2, col2, ws2, per2 = HT.project_views(T, verts, tris, [cam], lo=0.30, hi=0.6, erode=0,
                                               region={"portrait": head_region})
        # tone-match the portrait to the full-body painting on texels both see
        both = (ws > 0.3) & (ws2 > 0.3)
        if both.sum() > 200:
            gain = np.clip(np.median(col[both], 0) / np.maximum(np.median(col2[both], 0), 1e-3), 0.8, 1.2)
        else:
            gain = np.ones(3)
        log("portrait gain", np.round(gain, 3))
        col2 = np.clip(col2 * gain, 0, 1)
        wp = ws2 * 4.0
        tot = ws + wp
        col = (col * ws[:, None] + col2 * wp[:, None]) / np.maximum(tot, 1e-9)[:, None]
        ws = tot
        per.update(per2)
        pinfo = dict(cam=cam, params=params.tolist(), err=err)
    mi = np.array([p.material_index for p in lo0.data.polygons])
    lt = np.empty(len(lo0.data.loop_triangles), np.int64) if False else None
    me = lo0.data
    me.calc_loop_triangles()
    tri_poly = np.empty(len(me.loop_triangles), np.int64)
    me.loop_triangles.foreach_get("polygon_index", tri_poly)
    yy, xx = data[0], data[1]
    group = mi[tri_poly[T.tri[yy, xx]]]
    col, seen = HT.synthesize(T, data, col, ws, per, views, group=group)
    log("texture: seen fraction", round(float(seen.mean()), 3))
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
        big = cv2.resize(ref, (W * 2, H * 2), interpolation=cv2.INTER_CUBIC)
        compb = rgba[..., :3] * rgba[..., 3:4] + bgc * (1 - rgba[..., 3:4])
        sheet = np.concatenate([HBL._label((np.clip(big, 0, 1) * 255).astype(np.uint8), "portrait (sheet)"),
                                HBL._label((np.clip(compb, 0, 1) * 255).astype(np.uint8), f"model, same framing  SSIM {s:.3f}")], 1)
        core.save_rgba(qa("portrait.png"), sheet / 255.0)
        res["portrait"] = {"ssim": round(s, 4), "solve_err_px": round(pinfo["err"], 2)}
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
    reg = HBL.face_attr_get(lo0, "region")
    HBL.uv_layout(lo0, boost_faces=reg == 1, boost=2.6)
    log("LOD0 tris", core.tri_count(lo0))
    p_png, pinfo = texture(lo0, R, J)
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
