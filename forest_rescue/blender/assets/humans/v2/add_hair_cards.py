"""Hair-strand cards: a fringe of alpha-tested cards around the hair silhouette of a v2 human.

The strand clumps are cut from the character's own painted hair edge (the portrait inset, where the
hair meets the plain background): patches along the hair outline, rotated so the strands point
outward, alpha from the distance to the background colour, colour bled into the transparent texels.
Cards (single quads, double-sided, alphaMode MASK) stand on the hair shell, skinned like the nearest
hair vertex, on LOD0 and LOD1 (LOD2 keeps the shell).  Runs on the finished (and draped) .blend,
re-exports the GLB, updates the meta and writes front/back QA sheets with the cards.

    python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/humans/v2/add_hair_cards.py <aid> <iter>
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

from frlib import core, paths  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
AID = ARGS[0]
ITER = int(ARGS[1]) if len(ARGS) > 1 else 25
T0 = time.time()
# short tousled crop: outward tufts all over; tied-back hair: flat tufts along the flow + loose strands
STYLE = {
    "lf_squad_captain": dict(kind="crop", n=(64, 28), L=(0.020, 0.034), W=0.030, loose=0),
    "lf_civilian_courier": dict(kind="tied", n=(52, 24), L=(0.016, 0.028), W=0.026, loose=12, loose_L=(0.055, 0.095)),
    "lf_civilian_quarry_worker": dict(kind="tied", n=(52, 24), L=(0.016, 0.028), W=0.026, loose=12,
                                      loose_L=(0.055, 0.095)),
}
CELL, GRID = 128, 4


def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


def atlas_from_portrait(C):
    """4x4 atlas of strand clumps cut along the painted hair outline (above the eye line)."""
    import cv2
    from scipy import ndimage as ndi
    import humans_refs as HR_
    box = HR_.PANELS[AID]["inset"]
    img = np.asarray(HR_.refs.crop(HR_.sheet(HR_.PANELS[AID]["sheet"]), box), dtype=np.float32)[..., :3]
    if img.max() > 1.5:
        img = img / 255.0
    H, W = img.shape[:2]
    border = np.concatenate([img[:3].reshape(-1, 3), img[:, :3].reshape(-1, 3), img[:, -3:].reshape(-1, 3)])
    bg = np.median(border, 0)
    dist = np.linalg.norm(img - bg, axis=-1)
    alpha = np.clip((dist - 0.05) / 0.12, 0, 1)
    lab, n = ndi.label(alpha > 0.5)
    if n == 0:
        raise RuntimeError("no figure in the portrait")
    big = np.argmax(ndi.sum(np.ones_like(lab), lab, range(1, n + 1))) + 1
    mask = ndi.binary_fill_holes(lab == big)
    pc = C["portrait"]
    er = np.array(pc["eye_r"], float) - box[:2]
    el = np.array(pc["eye_l"], float) - box[:2]
    eye_y = 0.5 * (er[1] + el[1])
    e = float(np.linalg.norm(el - er))
    cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cont = max(cs, key=len)[:, 0, :].astype(float)
    keep = (cont[:, 1] < eye_y - 0.15 * e) & (cont[:, 1] > 2) & (cont[:, 0] > 2) & (cont[:, 0] < W - 3)
    pts = cont[keep]
    sm = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), max(2.0, 0.08 * e))
    gy, gx = np.gradient(sm)
    s = 0.75 * e
    P = CELL
    # evenly spaced along the kept outline
    if len(pts) < 20:
        raise RuntimeError("hair outline too short")
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    picks = np.interp(np.linspace(0.04, 0.96, GRID * GRID) * seg[-1], seg, np.arange(len(pts))).astype(int)
    atlas = np.zeros((GRID * P, GRID * P, 4), np.float32)
    xs = (np.arange(P) + 0.5) / P
    win = np.clip(np.minimum(xs, 1 - xs) / 0.22, 0, 1)
    win = win * win * (3 - 2 * win)
    for k, pi in enumerate(picks):
        cx, cy = pts[pi]
        nx, ny = -gx[int(cy), int(cx)], -gy[int(cy), int(cx)]
        nn = math.hypot(nx, ny)
        if nn < 1e-6:
            nx, ny, nn = 0.0, -1.0, 1.0
        nx, ny = nx / nn, ny / nn                       # outward (image coords, y down)
        tx, ty = -ny, nx
        c = np.array([cx, cy]) - np.array([nx, ny]) * 0.10 * s
        # dst (u, v) -> src: c + (u - P/2) * (s/P) * t + (v - P/2) * (s/P) * (-n)
        sc = s / P
        M = np.array([[sc * tx, -sc * nx, c[0] - (P / 2) * sc * tx + (P / 2) * sc * nx],
                      [sc * ty, -sc * ny, c[1] - (P / 2) * sc * ty + (P / 2) * sc * ny]], np.float32)
        rgb = cv2.warpAffine(img, M, (P, P), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                             borderMode=cv2.BORDER_REFLECT)
        d = np.linalg.norm(rgb - bg, axis=-1)
        a = np.clip((d - 0.05) / 0.12, 0, 1)
        a[int(P * 0.62):] = np.maximum(a[int(P * 0.62):], 1.0)      # root: the hair mass, opaque
        a = a * win[None, :]
        a[:4] = 0
        # colour bleed into the transparent texels (no halo when mip-mapped / alpha-tested)
        far = a < 0.5
        if far.any() and (~far).any():
            _, (iy, ix) = ndi.distance_transform_edt(far, return_indices=True)
            rgb = rgb[iy, ix]
        r0, c0 = (k // GRID) * P, (k % GRID) * P
        atlas[r0:r0 + P, c0:c0 + P, :3] = rgb
        atlas[r0:r0 + P, c0:c0 + P, 3] = a
    return np.clip(atlas, 0, 1)


def fps(points, n, seed=0):
    rng = np.random.default_rng(seed)
    sel = [int(rng.integers(len(points)))]
    d = np.linalg.norm(points - points[sel[0]], axis=1)
    for _ in range(min(n, len(points)) - 1):
        i = int(np.argmax(d))
        sel.append(i)
        d = np.minimum(d, np.linalg.norm(points - points[i], axis=1))
    return np.array(sel)


def rot_about(v, axis, ang):
    axis = axis / np.linalg.norm(axis)
    return v * math.cos(ang) + np.cross(axis, v) * math.sin(ang) + axis * np.dot(axis, v) * (1 - math.cos(ang))


def cards_for(lod, n_cards, st, seed):
    """Card quads (verts, faces, uvs, per-vertex weight dicts) on the hair shell of one LOD mesh."""
    from scipy.spatial import cKDTree
    me = lod.data
    hair_slots = [i for i, m in enumerate(me.materials) if m is not None and m.name.endswith("_hair")]
    if not hair_slots:
        return None
    hs = hair_slots[0]
    cen = np.array([p.center[:] for p in me.polygons])
    nrm = np.array([p.normal[:] for p in me.polygons])
    mi = np.array([p.material_index for p in me.polygons])
    hair = (mi == hs) & (cen[:, 2] > 1.2)
    if hair.sum() < 30:
        return None
    hc_ = cen[hair]
    hc = np.array([0.0, float(np.mean(hc_[:, 1])), 0.5 * (hc_[:, 2].min() + hc_[:, 2].max())])
    top = hc_[:, 2].max()
    radial = cen - hc
    radial /= np.maximum(np.linalg.norm(radial, axis=1, keepdims=True), 1e-9)
    out = np.einsum("ij,ij->i", nrm, radial)
    cand = hair & (out > 0.35) & (nrm[:, 2] > -0.35) & (cen[:, 2] > hc[2] - 0.03) \
        & ~((nrm[:, 1] < -0.6) & (cen[:, 2] < top - 0.045))
    idx = np.nonzero(cand)[0]
    if len(idx) < 10:
        return None
    rng = np.random.default_rng(seed)
    sel = idx[fps(cen[idx], n_cards, seed)]
    vco = np.array([v.co[:] for v in me.vertices])
    gi = {g.index: g.name for g in lod.vertex_groups}
    hv = np.unique(np.array([lv for p in np.nonzero(mi == hs)[0] for lv in me.polygons[p].vertices]))
    tree = cKDTree(vco[hv])
    V, F, UV, WT = [], [], [], []
    up = np.array([0.0, 0.0, 1.0])
    back = np.array([0.0, 1.0, -0.25])

    def add(p, d, w, L, Wd, cell):
        v0 = len(V)
        V.extend([p - w * Wd / 2, p + w * Wd / 2, p + w * Wd / 2 + d * L, p - w * Wd / 2 + d * L])
        F.append([v0, v0 + 1, v0 + 2, v0 + 3])
        r0, c0 = (cell // GRID) * CELL, (cell % GRID) * CELL
        S_ = GRID * CELL
        u0, u1 = (c0 + 2) / S_, (c0 + CELL - 2) / S_
        v_root, v_tip = 1 - (r0 + CELL - 2) / S_, 1 - (r0 + 2) / S_
        UV.extend([(u0, v_root), (u1, v_root), (u1, v_tip), (u0, v_tip)])
        _, j = tree.query(p)
        wd = {gi[ge.group]: ge.weight for ge in me.vertices[int(hv[j])].groups if ge.weight > 0}
        WT.extend([wd] * 4)

    for k, f in enumerate(sel):
        n = nrm[f]
        p = cen[f] - n * 0.005
        tang = np.cross(n, up)
        tang = tang / np.linalg.norm(tang) if np.linalg.norm(tang) > 1e-3 else np.array([1.0, 0, 0])
        if st["kind"] == "crop":
            d = n + 0.30 * rng.uniform(-1, 1) * tang + 0.12 * up
        else:
            d = n * 0.55 + 0.45 * back + 0.15 * rng.uniform(-1, 1) * tang
        d /= np.linalg.norm(d)
        w = np.cross(d, up) if abs(d[2]) < 0.85 else np.array([1.0, 0.0, 0.0])
        w /= np.linalg.norm(w)
        w = rot_about(w, d, rng.uniform(-1.0, 1.0))
        add(p, d, w, rng.uniform(*st["L"]), st["W"] * rng.uniform(0.85, 1.15), int(rng.integers(GRID * GRID)))
    # loose strands hanging beside the face (tied-back styles)
    if st.get("loose", 0):
        side = hair & (np.abs(nrm[:, 0]) > 0.45) & (cen[:, 2] > hc[2] - 0.05) & (cen[:, 2] < hc[2] + 0.03) \
            & (cen[:, 1] < hc[1] + 0.01)
        sidx = np.nonzero(side)[0]
        if len(sidx):
            nl = max(2, int(st["loose"] * n_cards / st["n"][0]))
            for f in sidx[fps(cen[sidx], nl, seed + 1)]:
                n = nrm[f]
                p = cen[f] - n * 0.004
                d = 0.30 * n + np.array([0.0, 0.05, -1.0])
                d /= np.linalg.norm(d)
                w = np.cross(d, n)
                w /= max(np.linalg.norm(w), 1e-6)
                w = rot_about(w, d, rng.uniform(-0.5, 0.5))
                add(p, d, w, rng.uniform(*st["loose_L"]), st["W"] * 0.8, int(rng.integers(GRID * GRID)))
    return np.array(V), F, UV, WT


def main():
    st = STYLE[AID]
    from hv2_chars import CHARS
    C = CHARS[AID]
    bpy.ops.wm.open_mainfile(filepath=paths.source("humans", f"{AID}.blend"))
    arm = bpy.data.objects[f"{AID}_rig"]
    lods = [bpy.data.objects[f"{AID}_LOD{k}"] for k in range(3)]
    for o in lods:
        if any(m is not None and m.name.endswith("_hair_cards") for m in o.data.materials):
            log("cards already present on", o.name, "- nothing to do")
            return
    atlas = atlas_from_portrait(C)
    tex_path = paths.texture_master("humans", f"{AID}_hair_cards.png")
    core.save_rgba(tex_path, atlas)
    img = core.load_image(tex_path)
    img.alpha_mode = "STRAIGHT"
    mat = core.material(f"{AID}_hair_cards", base_tex=img, alpha_clip=0.5, double_sided=True, rough=1.0)
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Specular IOR Level"].default_value = 0.0
    added = {}
    for k, o in enumerate(lods[:2]):
        res = cards_for(o, st["n"][k], st, seed=7 + k)
        if res is None:
            log("no hair shell on", o.name)
            continue
        V, F, UV, WT = res
        me = bpy.data.meshes.new(f"_cards_{k}")
        me.from_pydata([tuple(v) for v in V], [], F)
        me.update()
        uvname = o.data.uv_layers.active.name if o.data.uv_layers.active else "UVMap"
        uvl = me.uv_layers.new(name=uvname)
        for li, loop in enumerate(me.loops):
            uvl.data[li].uv = UV[loop.vertex_index]
        me.materials.append(mat)
        co = bpy.data.objects.new(f"_cards_{k}", me)
        bpy.context.scene.collection.objects.link(co)
        co.matrix_world = o.matrix_world.copy()
        for vi, wd in enumerate(WT):
            for b, w in wd.items():
                (co.vertex_groups.get(b) or co.vertex_groups.new(name=b)).add([vi], w, "REPLACE")
        bpy.ops.object.select_all(action="DESELECT")
        co.select_set(True)
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        nv_before = len(o.data.vertices)
        bpy.ops.object.join()
        # joined card vertices carry no shape displacement (sit_drape etc. stay garment-only)
        if o.data.shape_keys:
            kbs = o.data.shape_keys.key_blocks
            base = kbs[0]
            for kb in kbs[1:]:
                for vi in range(nv_before, len(o.data.vertices)):
                    kb.data[vi].co = base.data[vi].co
        added[o.name] = len(F)
        log(o.name, "cards", len(F), "tris now", core.tri_count(o))
    # ---- re-export (same settings as the drape pass) + meta
    out_glb = paths.runtime("humans", f"{AID}.glb")
    if arm.animation_data:
        arm.animation_data.action = None
    core.export_glb(out_glb, [arm] + lods,
                    extra=dict(export_force_sampling=True, export_optimize_animation_size=False,
                               export_image_format="AUTO", export_def_bones=True, export_animation_mode="ACTIONS",
                               export_bake_animation=False, export_morph=True, export_morph_normal=False,
                               export_morph_animation=True, export_merge_animation="ACTION"))
    log("GLB", out_glb, os.path.getsize(out_glb) // 1024, "KB")
    mp = paths.runtime("humans", f"{AID}.meta.json")
    meta = json.load(open(mp))
    meta["tris"] = {f"LOD{k}": core.tri_count(o) for k, o in enumerate(lods)}
    meta["hairCards"] = {"style": st["kind"], "cardsByLOD": {k: v for k, v in added.items()},
                         "material": f"{AID}_hair_cards (alphaMode MASK 0.5, double sided)",
                         "atlas": os.path.relpath(tex_path, paths.REPO),
                         "source": "strand clumps cut from the painted hair outline of the portrait inset"}
    core.write_json(mp, meta)
    core.save_blend(paths.source("humans", f"{AID}.blend"))
    log("saved; tris", meta["tris"])
    qa(lods[0], img)


def qa(lo0, card_img):
    """Front / back compare sheets of LOD0 with the cards (same QA renderer and metrics as build_v2)."""
    import hv2_blender as HBL
    import hv2_fit as F
    R = F.Refs(AID)
    for o in bpy.data.objects:
        o.hide_render = not (o is lo0)
    if bpy.data.objects[f"{AID}_rig"].animation_data:
        bpy.data.objects[f"{AID}_rig"].animation_data.action = None
    from mathutils import Matrix
    for pb in bpy.data.objects[f"{AID}_rig"].pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    col_img = None
    for m in lo0.data.materials:
        if m and not m.name.endswith("_hair_cards"):
            for nd in m.node_tree.nodes:
                if nd.type == "TEX_IMAGE" and nd.image is not None:
                    col_img = nd.image
                    break
        if col_img:
            break
    for i, m in enumerate(lo0.data.materials):
        if m is None:
            continue
        if m.name.endswith("_hair_cards"):
            lo0.data.materials[i] = HBL.painted_material(m.name + "_qa", card_img, k=0.0, alpha_clip=0.5)
        else:
            lo0.data.materials[i] = HBL.painted_material(m.name + "_qa", col_img, k=0.0)
    HBL.qa_scene(samples=10)
    res = {}
    for which, view in (("front", R.front), ("back", R.back)):
        HBL.ortho_cam_for_view(view, scale=3)
        rgba = HBL.render_rgba()
        out = os.path.join(paths.QA_COMPARE, AID, f"v2_iter{ITER:02d}_{which}.png")
        res[which] = HBL.compare_sheet(view.image, view.mask, rgba, out,
                                       f"{AID} v2 iter{ITER:02d} {which} (with hair cards): reference | render | IoU | colour error")
        log(which, res[which])
    core.write_json(os.path.join(paths.QA_COMPARE, AID, f"v2_iter{ITER:02d}_metrics.json"), res)


if __name__ == "__main__":
    main()
