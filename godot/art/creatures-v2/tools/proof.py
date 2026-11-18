"""Proof renders for the reference check (Blender 5.3 as a Python module, Cycles on the CPU).

  python -I proof.py sculpt <species> <rc dir> <out dir> [voxel] [clip:frame]   # coarse sculpt + solid fur strips
  python -I proof.py glb <species> <glb> <rc dir> <out dir> [clip:frame]        # a built GLB (textured)

Views are rendered orthographically at the sheet's own scale (refs.json px_per_m from refcheck.py refs), the
model ground on the sheet's ground line; only a horizontal shift is searched (top view: both shifts). Writes
<species>_<tag>_<view>.png (render) and <species>_<tag>.jpg: reference | render | overlay per view.
"""
import importlib
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))

import refcheck  # noqa: E402

FLAT = {"base": "#5a4c40", "fur_long": "#6b5b4b", "skin": "#4a3d35", "nose": "#151210", "hoof": "#2a2420",
        "antler": "#cdbf9f", "moss": "#6f7a24", "bark": "#5a4330", "stone": "#5f5a58", "tusk": "#d9ccb0",
        "claw": "#c9b79a", "eye": "#c08020", "tooth": "#ddd2bb", "mouth": "#3b1712", "mane": "#7a6a58",
        "glow": "#61bdf4"}
MARGIN = 160


def hexlin(h):
    c = np.array([int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)])
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


# ------------------------------------------------------------------ proof mesh (coarse sculpt)
def proof_mesh(sp, voxel):
    """Every level-I part extracted at `voxel`, coloured by the owning primitive's surface class, with 4-bone skin
    weights (softmin ownership like export.skin_weights, rigid parts on their bone), plus the fur cards as solid
    strips skinned from the nearest body vertex."""
    from sdf import extract, largest_component
    sk, parts = sp.build_cached()
    names = [b.name for b in sk.bones]
    jidx = {n: i for i, n in enumerate(names)}
    V, F, C, J, W = [], [], [], [], []
    base = 0
    body = None
    colors = getattr(sp, "PROOF_COLORS", {})
    for part in parts:
        if part.get("level", 1) > 1:
            continue
        h = voxel if part["rigid"] is None else min(voxel, max(0.006, part.get("voxel", sp.VOXEL_RIGID) * 1.6))
        v, f = extract(part["part"], h)
        if len(f) == 0:
            continue
        v, f = largest_component(v, f, 0.02 if part["rigid"] is None else 0.1)
        _d, D = part["part"].eval(v, keep=True, displace=False)
        prims = part["part"].prims
        valid = np.array([not p.neg for p in prims])
        D = np.where(valid[None, :], D, 1e3)
        owner = np.argmin(D, 1)
        col = np.array([hexlin(colors.get(prims[o].mat, FLAT.get(prims[o].mat, "#6a6a6a"))) for o in owner])
        jw = np.zeros((len(v), 4), np.int32)
        ww = np.zeros((len(v), 4), np.float32)
        if part["rigid"] is not None:
            jw[:, 0] = jidx[part["rigid"]]
            ww[:, 0] = 1.0
        else:
            infl = np.exp(-(D - D.min(1, keepdims=True)) / 0.045)
            Wf = np.zeros((len(v), len(names)), np.float32)
            for j, p in enumerate(prims):
                if not p.neg:
                    Wf[:, jidx[p.bone]] += infl[:, j]
            order = np.argsort(-Wf, 1)[:, :4]
            w4 = np.take_along_axis(Wf, order, 1)
            w4 /= np.maximum(w4.sum(1, keepdims=True), 1e-9)
            jw, ww = order.astype(np.int32), w4.astype(np.float32)
            if part["name"] == "body":
                body = (v, jw, ww)
        V.append(v)
        F.append(f + base)
        C.append(col)
        J.append(jw)
        W.append(ww)
        base += len(v)
    fur = getattr(sp, "FUR_CARDS", None)
    furmesh = None
    if fur and body is not None:
        import furcards
        from scipy.spatial import cKDTree
        rng = np.random.default_rng(21)
        clist = furcards.cards(furcards.outer_surface(sp), fur, rng, getattr(sp, "FUR_KEEP", furcards.KEEP)[1],
                               furcards.WIDEN[1])
        if clist:
            pos, nrm, uv, idx, rootv, tv = furcards.card_mesh(clist, crossed_ok=True, segments=2)
            roots = np.array([c["root"] for c in clist])
            _d, nearest = cKDTree(body[0]).query(roots)
            body_col = hexlin(colors.get("fur_long", FLAT["fur_long"]))
            tipc = np.array([hexlin(c["tip"]) if c["tip"] else body_col * 1.4 for c in clist])
            rootc = np.array([hexlin(c["root_hex"]) if c["root_hex"] else body_col for c in clist])
            s = (tv ** 1.3)[:, None]
            col = rootc[rootv] * (1 - s) + tipc[rootv] * s
            one_side = np.arange(len(idx)) % 4 < 2      # card_mesh emits both windings; Cycles needs one
            furmesh = {"v": pos.astype(np.float64), "f": idx[one_side].astype(np.int64), "uv": uv, "col": col,
                       "j": body[1][nearest][rootv], "w": body[2][nearest][rootv],
                       "glow": np.array([c["col"] == furcards.GLOW_COLUMN for c in clist])[rootv]}
    return (np.concatenate(V).astype(np.float64), np.concatenate(F).astype(np.int64), np.concatenate(C),
            np.concatenate(J), np.concatenate(W), names, furmesh)


def pose_vertices(sk, names, v, j, w, rot, off):
    """Linear blend skinning with the pipeline's rig (inverse bind = -rest head, as in the GLB)."""
    from qmath import q_to_mat
    pos, wrot = sk.fk(rot, off)
    M = np.array([q_to_mat(wrot[n]) for n in names])
    Pp = np.array([pos[n] for n in names])
    heads = np.array([sk.bone(n).head for n in names])
    out = np.zeros_like(v)
    for k in range(4):
        jk = j[:, k]
        rel = v - heads[jk]
        out += w[:, k:k + 1] * (np.einsum("nij,nj->ni", M[jk], rel) + Pp[jk])
    return out


def clip_pose(sp, v, j, w, names, clip_name, frame):
    """Local rotations / offsets of `clip_name` at `frame` (all clips are baked by the species module)."""
    from anim import Quad, SkinSampler
    sk, parts = sp.build_cached()
    rig = Quad(sk)
    sampler = SkinSampler(sk, v, j, w, names, count=5000)
    clips = sp.clips(rig, sampler)
    clip = next(c for c in clips if c["name"].endswith("__" + clip_name))
    baked = clip["_baked"]
    f = int(min(frame, clip["frames"]))
    rot = {n: baked[n][0][f] for n in names}
    off = {n: baked[n][1][f] - sk.rest_offset(n) for n in names}
    motion = clip.get("motion")
    return rot, off, motion, clip


# ------------------------------------------------------------------ Blender scene
def scene_setup(samples=24):
    """Studio like the reference sheets: a bright, even backdrop light plus a soft key from the camera's upper left
    and a weak fill from its right (both follow the camera, see light_rig); Standard view transform."""
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"
    w = bpy.data.worlds.new("studio")
    sc.world = w
    w.use_nodes = True
    bgn = w.node_tree.nodes["Background"]
    bgn.inputs[0].default_value = (0.72, 0.71, 0.69, 1)
    bgn.inputs[1].default_value = 0.85
    for name, energy, ang in (("key", 3.4, 20), ("fill", 1.0, 30), ("top", 0.7, 25)):
        L = bpy.data.lights.new(name, "SUN")
        L.energy = energy
        L.angle = math.radians(ang)
        o = bpy.data.objects.new(name, L)
        sc.collection.objects.link(o)
    return sc


def light_rig(sc, cam):
    """Key from the camera's upper left, fill from its right, a top light; sun lamps shine along their -Z."""
    import bpy
    from mathutils import Euler
    rel = {"key": (math.radians(38), math.radians(-28), 0), "fill": (math.radians(15), math.radians(35), 0),
           "top": (math.radians(70), 0, 0)}
    bpy.context.view_layer.update()
    for name, e in rel.items():
        o = bpy.data.objects.get(name)
        if o is not None:
            o.matrix_world = cam.matrix_world @ Euler(e, "XYZ").to_matrix().to_4x4()


def add_fur(fm, v_gltf, atlas_dir):
    """Fur cards with the pipeline's strand atlas (alpha clip) tinted by the vertex colour."""
    import bpy
    import furcards
    os.makedirs(atlas_dir, exist_ok=True)
    atlas = os.path.join(atlas_dir, "fur_basecolor.png")
    if not os.path.exists(atlas):
        furcards.hair_atlas(atlas_dir)
    vb = np.stack([v_gltf[:, 0], -v_gltf[:, 2], v_gltf[:, 1]], 1)
    me = bpy.data.meshes.new("fur")
    me.from_pydata(vb.tolist(), [], fm["f"].tolist())
    me.update()
    ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    rgba = np.concatenate([fm["col"], np.ones((len(fm["col"]), 1))], 1).astype(np.float32)
    ca.data.foreach_set("color", rgba.ravel())
    uvl = me.uv_layers.new(name="UV")
    loops = np.array([l.vertex_index for l in me.loops])
    uvs = fm["uv"][loops].copy()
    uvs[:, 1] = 1.0 - uvs[:, 1]          # glTF v down -> Blender v up
    uvl.data.foreach_set("uv", uvs.astype(np.float32).ravel())
    ob = bpy.data.objects.new("fur", me)
    bpy.context.scene.collection.objects.link(ob)
    mat = bpy.data.materials.new("fur")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(atlas)
    attr = nt.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Col"
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(attr.outputs["Color"], mul.inputs["A"])
    nt.links.new(tex.outputs["Color"], mul.inputs["B"])
    nt.links.new(mul.outputs["Result"], bsdf.inputs["Base Color"])
    # alpha clip like the glTF material (cutoff 0.42)
    gt = nt.nodes.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = 0.42
    nt.links.new(tex.outputs["Alpha"], gt.inputs[0])
    nt.links.new(gt.outputs[0], bsdf.inputs["Alpha"])
    bsdf.inputs["Roughness"].default_value = 0.85
    ob.data.materials.append(mat)
    return ob


def add_mesh(v_gltf, f, col):
    """glTF axes (+Y up, +Z right) -> Blender (+Z up): (x, y, z) -> (x, -z, y)."""
    import bpy
    vb = np.stack([v_gltf[:, 0], -v_gltf[:, 2], v_gltf[:, 1]], 1)
    me = bpy.data.meshes.new("proof")
    me.from_pydata(vb.tolist(), [], f.tolist())
    me.update()
    ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    rgba = np.concatenate([col, np.ones((len(col), 1))], 1).astype(np.float32)
    ca.data.foreach_set("color", rgba.ravel())
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("proof", me)
    bpy.context.scene.collection.objects.link(ob)
    mat = bpy.data.materials.new("proof")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    attr = nt.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Col"
    nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.8
    ob.data.materials.append(mat)
    return ob


def render_view(sc, view, ppm, W, H, ground, centre, path, margin=MARGIN):
    """Orthographic camera at the sheet scale; canvas W+2*margin wide. `centre`: model point (Blender coords)
    to put at the canvas centre horizontally (side: x, front/rear: y, top: x and y)."""
    import bpy
    cam_data = bpy.data.cameras.new("cam_" + view)
    cam_data.type = "ORTHO"
    cam_data.sensor_fit = "HORIZONTAL"
    Wc = W + 2 * margin
    Hc = H + (2 * margin if view == "top" else 0)
    cam_data.ortho_scale = Wc / ppm
    cam_data.clip_end = 200
    cam = bpy.data.objects.new("cam_" + view, cam_data)
    sc.collection.objects.link(cam)
    zc = (ground - H / 2.0) / ppm
    if view == "side":
        cam.location = (centre[0], 40, zc)
        cam.rotation_euler = (math.radians(90), 0, math.radians(180))
    elif view == "front":
        cam.location = (40, centre[1], zc)
        cam.rotation_euler = (math.radians(90), 0, math.radians(90))
    elif view == "rear":
        cam.location = (-40, centre[1], zc)
        cam.rotation_euler = (math.radians(90), 0, math.radians(-90))
    elif view == "top":
        cam.location = (centre[0], centre[1], 40)
        cam.rotation_euler = (0, 0, math.radians(180))
    sc.camera = cam
    light_rig(sc, cam)
    sc.render.resolution_x = Wc
    sc.render.resolution_y = Hc
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def compare(species, rc, out, tag, renders, grid_info=None):
    """reference | render | overlay rows; IoU at the sheet scale with a horizontal shift only."""
    refs = json.load(open(os.path.join(rc, "refs.json")))[species]
    rows, res, colors = [], {}, {}
    for view, path in renders.items():
        ref = np.asarray(Image.open(os.path.join(rc, f"{species}_{view}_mask.png"))) > 127
        H, W = ref.shape
        im = Image.open(path).convert("RGBA")
        a = np.asarray(im)[:, :, 3] > 110
        best = (-1, 0, 0)
        dys = range(-MARGIN, MARGIN + 1, 4) if view == "top" else [0]
        oy0 = MARGIN if view == "top" else 0
        for dy in dys:
            for dx in range(-MARGIN, MARGIN + 1, 4):
                m = a[oy0 + dy:oy0 + dy + H, MARGIN + dx:MARGIN + dx + W]
                iou = (m & ref).sum() / max(1, (m | ref).sum())
                if iou > best[0]:
                    best = (iou, dx, dy)
        _, bx, by = best
        for dy in (range(by - 3, by + 4) if view == "top" else [0]):
            for dx in range(bx - 3, bx + 4):
                m = a[oy0 + dy:oy0 + dy + H, MARGIN + dx:MARGIN + dx + W]
                iou = (m & ref).sum() / max(1, (m | ref).sum())
                if iou > best[0]:
                    best = (iou, dx, dy)
        iou, dx, dy = best
        res[view] = round(float(iou), 3)
        crop = im.crop((MARGIN + dx, oy0 + dy, MARGIN + dx + W, oy0 + dy + H))
        m = np.asarray(crop)[:, :, 3] > 110
        if grid_info is not None:
            grid_view(species, rc, out, tag, view, ref, m, refs, grid_info, dx, dy)
        refimg = Image.open(os.path.join(rc, f"{species}_{view}_ref.png")).convert("RGB")
        bg = Image.new("RGBA", (W, H), tuple(int(c) for c in np.asarray(refimg)[3, 3]) + (255,))
        bg.alpha_composite(crop)
        bg.convert("RGB").save(os.path.join(out, f"{species}_{tag}_{view}_aligned.png"))   # for tools/detail.py
        cut = Image.open(os.path.join(rc, f"{species}_{view}_cut.png"))
        ov = refcheck.overlay(ref, m, cut)
        ra = np.asarray(refimg).reshape(-1, 3)[ref.ravel()]
        ma = np.asarray(crop.convert("RGB")).reshape(-1, 3)[m.ravel()]
        if len(ma) and len(ra):
            colors[view] = {"reference": "#%02x%02x%02x" % tuple(np.median(ra, 0).astype(int)),
                            "model": "#%02x%02x%02x" % tuple(np.median(ma, 0).astype(int))}
            print("COLOR", species, view, "ref", colors[view]["reference"], "model", colors[view]["model"], flush=True)
        tiles = [refcheck.label(refimg.copy(), f"{view}: reference"),
                 refcheck.label(bg.convert("RGB"), f"{view}: model {tag}"),
                 refcheck.label(ov, f"{view}: overlay IoU {iou:.3f} @ {refs['views'][view].get('px_per_m', refs['scale']['px_per_m'])} px/m")]
        rows.append(tiles)
    # rows: one per view, scaled to a common width
    target = 1800
    out_rows = []
    for tiles in rows:
        w = sum(t.size[0] for t in tiles) + 16
        s = min(1.0, target / w)
        row = Image.new("RGB", (int(w * s), int(tiles[0].size[1] * s)), (255, 255, 255))
        x = 0
        for t in tiles:
            t2 = t.resize((int(t.size[0] * s), int(t.size[1] * s)), Image.LANCZOS)
            row.paste(t2, (x, 0))
            x += t2.size[0] + int(8 * s)
        out_rows.append(row)
    Wt = max(r.size[0] for r in out_rows)
    Ht = sum(r.size[1] for r in out_rows) + 10 * len(out_rows)
    sheet = Image.new("RGB", (Wt, Ht), (255, 255, 255))
    y = 0
    for r in out_rows:
        sheet.paste(r, (0, y))
        y += r.size[1] + 10
    path = os.path.join(out, f"{species}_{tag}.jpg")
    sheet.save(path, quality=88)
    print("IOU", species, tag, json.dumps(res), flush=True)
    if tag.startswith("model"):
        json.dump({"iou": res, "median_colour": colors,
                   "px_per_m": {v: refs["views"][v].get("px_per_m") for v in res}},
                  open(os.path.join(out, f"{species}_views.json"), "w"), indent=1)
    return res


def bounds_blender(objs):
    import bpy
    from mathutils import Vector
    pts = []
    dg = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
        mw = o.matrix_world
        for v in me.vertices:
            pts.append(tuple(mw @ v.co))
        oe.to_mesh_clear()
    p = np.array(pts)
    return p.min(0), p.max(0)


def run_views(species, rc, out, tag, objs, views=None):
    import bpy  # noqa: F401
    refs = json.load(open(os.path.join(rc, "refs.json")))[species]
    ppm = refs["scale"]["px_per_m"]
    lo, hi = bounds_blender(objs)
    centre = (lo + hi) / 2
    renders = {}
    sc = bpy.context.scene
    for view, row in refs["views"].items():
        if view == "three_quarter" or (views and view not in views):
            continue
        H, W = row["bbox"][3] + 1, row["bbox"][2] + 1
        ref = Image.open(os.path.join(rc, f"{species}_{view}_mask.png"))
        W, H = ref.size
        path = os.path.join(out, f"{species}_{tag}_{view}.png")
        render_view(sc, view, row.get("px_per_m", ppm), W, H, row.get("ground", H / 2), centre, path)
        renders[view] = path
    return compare(species, rc, out, tag, renders, {"centre": centre.tolist(), "ppm": ppm})


def model_axes(view, u, r, W, H, g, centre, ppm, dx, dy):
    """Reference crop pixel (u, r) -> model (glTF) coordinates of the two axes of the view."""
    if view == "side":
        return centre[0] - (u + dx - W / 2) / ppm, (g - r) / ppm            # x, y
    if view == "front":
        return -(centre[1] + (u + dx - W / 2) / ppm), (g - r) / ppm         # z, y
    if view == "rear":
        return -(centre[1] - (u + dx - W / 2) / ppm), (g - r) / ppm         # z, y
    return centre[0] - (u + dx - W / 2) / ppm, -(centre[1] + (r + dy - H / 2) / ppm)   # top: x, z


def grid_view(species, rc, out, tag, view, ref, mdl, refs, info, dx, dy, k=2):
    """The reference view enlarged x2 with a metric grid labelled in model coordinates (side: x forward / y up,
    front and rear: z right / y up, top: x / z), the reference outline (red) and the model outline (green)."""
    import cv2
    H, W = ref.shape
    g = refs["views"][view].get("ground", H / 2)
    ppm, centre = refs["views"][view].get("px_per_m", info["ppm"]), info["centre"]
    img = np.asarray(Image.open(os.path.join(rc, f"{species}_{view}_ref.png")).convert("RGB"))
    img = cv2.resize(img, (W * k, H * k), interpolation=cv2.INTER_CUBIC).copy()
    img = (img.astype(np.float32) * 0.75 + 255 * 0.25).astype(np.uint8)
    # grid: find the model value of every column / row and draw lines where it crosses a 0.25 m step
    cols = np.array([model_axes(view, u, 0, W, H, g, centre, ppm, dx, dy)[0] for u in range(W)])
    rows = np.array([model_axes(view, 0, r, W, H, g, centre, ppm, dx, dy)[1] for r in range(H)])
    pil = Image.fromarray(img)
    d = ImageDraw.Draw(pil)
    for arr, horiz in ((cols, False), (rows, True)):
        q = np.floor(arr / 0.25)
        for i in range(1, len(arr)):
            if q[i] != q[i - 1]:
                val = max(q[i], q[i - 1]) * 0.25
                major = abs(val - round(val)) < 1e-6
                colr = (40, 70, 220) if not horiz else (220, 90, 30)
                if not major:
                    colr = tuple(int(c * 0.45 + 255 * 0.55) for c in colr)
                if horiz:
                    d.line([(0, i * k), (W * k, i * k)], fill=colr, width=2 if major else 1)
                    if major or abs(val * 2 - round(val * 2)) < 1e-6:
                        d.text((3, i * k + 2), f"{val:+.2f}", fill=(160, 50, 0))
                else:
                    d.line([(i * k, 0), (i * k, H * k)], fill=colr, width=2 if major else 1)
                    if major or abs(val * 2 - round(val * 2)) < 1e-6:
                        d.text((i * k + 3, 3), f"{val:+.2f}", fill=(20, 30, 160))
    img = np.asarray(pil).copy()
    for mask, colr in ((ref, (230, 30, 30)), (mdl, (0, 170, 40))):
        cnt, _h = cv2.findContours(cv2.resize(mask.astype(np.uint8), (W * k, H * k), interpolation=cv2.INTER_NEAREST),
                                   cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(img, cnt, -1, colr, 2)
    axes = {"side": "x fwd / y up", "front": "z right / y up", "rear": "z right / y up", "top": "x fwd / z right"}[view]
    out_im = refcheck.label(Image.fromarray(img), f"{species} {view} [{axes}] red: reference, green: model {tag}")
    out_im.save(os.path.join(out, f"{species}_{tag}_{view}_grid.jpg"), quality=86)


def cmd_sculpt(species, rc, out, voxel=0.03, pose=None):
    import bpy  # noqa: F401
    os.makedirs(out, exist_ok=True)
    sp = importlib.import_module("species." + species)
    v, f, col, j, w, names, fm = proof_mesh(sp, voxel)
    tag = "sculpt"
    fv = fm["v"] if fm else None
    if pose:
        clip, frame = pose.split(":")
        sk, _parts = sp.build_cached()
        rot, off, motion, _c = clip_pose(sp, v, j, w, names, clip, int(frame))
        v = pose_vertices(sk, names, v, j, w, rot, off)
        if fm:
            fv = pose_vertices(sk, names, fm["v"], fm["j"], fm["w"], rot, off)
        tag = "sculpt" if pose == "idle:0" else f"sculpt_{clip}_{frame}"
    if os.environ.get("PROOF_LEGS"):
        # debug: colour by the dominant bone - near (left) legs red / blue, far (right) legs orange / cyan
        legc = {"Front_L": "#e02020", "Front_R": "#f0a020", "Hind_L": "#2040e0", "Hind_R": "#20c0e0"}
        dom = j[np.arange(len(j)), np.argmax(w, 1)]
        for key, hx in legc.items():
            sel = np.array([names[d].endswith(key) and not names[d].startswith(("Shoulder", "Hip")) for d in dom])
            col = col.copy()
            col[sel] = hexlin(hx)
        tag += "_legs"
        fm = None
    sc = scene_setup()
    objs = [add_mesh(v, f, col)]
    if fm:
        objs.append(add_fur(fm, fv, os.path.join(out, "_atlas")))
    return run_views(species, rc, out, tag, objs)


def import_glb(sc, glb):
    import bpy
    sc.render.fps = 30
    sc.render.fps_base = 1.0
    bpy.ops.import_scene.gltf(filepath=glb)


def set_clip(sc, species, clip, frame):
    """Plays `<species>__<clip>` on the imported armature and evaluates `frame` (30 fps)."""
    import bpy
    arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    act = next((a for a in bpy.data.actions if a.name.startswith(f"{species}__{clip}")), None)
    if arm is None or act is None:
        raise RuntimeError(f"no armature/action for {species}__{clip}")
    arm.animation_data_create()
    if arm.animation_data.nla_tracks:
        for t in list(arm.animation_data.nla_tracks):
            t.mute = True
    arm.animation_data.action = act
    if getattr(act, "slots", None) and len(act.slots):
        arm.animation_data.action_slot = act.slots[0]
    sc.frame_set(int(frame))
    bpy.context.view_layer.update()


def cmd_glb(species, glb, rc, out, pose=None, tag="model"):
    import bpy
    os.makedirs(out, exist_ok=True)
    sc = scene_setup()
    import_glb(sc, glb)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    clip, fr = (pose or "idle:0").split(":")
    set_clip(sc, species, clip, int(fr))
    tag = f"{tag}_{clip}_{fr}"
    return run_views(species, rc, out, tag, meshes)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "sculpt":
        a = sys.argv[2:]
        cmd_sculpt(a[0], a[1], a[2], float(a[3]) if len(a) > 3 else 0.03, a[4] if len(a) > 4 else "idle:0")
    elif cmd == "glb":
        a = sys.argv[2:]
        cmd_glb(a[0], a[1], a[2], a[3], a[4] if len(a) > 4 else None)
    elif cmd not in ("poses", "cycle", "glbposes", "glbcycles"):
        raise SystemExit(__doc__)


# ------------------------------------------------------------------ attack key poses vs the pose images
def project_persp(V, cam_pos, target, fov_deg, W, H):
    """World (glTF axes) -> pixel coordinates for a pinhole camera looking at `target` (+Y up)."""
    f = target - cam_pos
    f = f / np.linalg.norm(f)
    r = np.cross(f, np.array([0.0, 1.0, 0.0]))
    r = r / np.linalg.norm(r)
    u = np.cross(r, f)
    rel = V - cam_pos
    z = rel @ f
    x = rel @ r
    y = rel @ u
    foc = 0.5 * W / np.tan(np.radians(fov_deg) / 2)
    return np.stack([W / 2 + foc * x / z, H / 2 - foc * y / z], 1)


def silhouette(V, F, cam_pos, target, fov, W, H, pad=2.0):
    """Model silhouette on a canvas `pad` times the reference size (field of view widened to keep the pixel
    scale), so nothing is clipped at the frame edge; fit_mask / place then align it to the reference."""
    import cv2
    Wc, Hc = int(W * pad), int(H * pad)
    fovc = float(np.degrees(2 * np.arctan(np.tan(np.radians(fov) / 2) * pad)))
    q = project_persp(V, cam_pos, target, fovc, Wc, Hc)
    W, H = Wc, Hc
    img = np.zeros((H, W), np.uint8)
    tris = np.round(q[F] * 4).astype(np.int32)      # 2 bits of sub-pixel precision
    cv2.fillPoly(img, list(tris), 255, lineType=cv2.LINE_8, shift=2)
    return img > 0


def cam_for(az_deg, el_deg, dist, centre):
    az, el = np.radians(az_deg), np.radians(el_deg)
    # az 0: camera on the creature's right (+Z) looking at -Z, the head (+X) on the right of the image;
    # positive az swings the camera toward the head (a 3/4 front view)
    d = np.array([np.sin(az) * np.cos(el), np.sin(el), np.cos(az) * np.cos(el)])
    return centre + d * dist


def fit_mask(mask, ref, pad=0.06):
    """Scale + translation of `mask` onto `ref` by their bounding boxes (height match, bottom-centre aligned);
    returns the moved mask on the ref canvas and the IoU."""
    import cv2
    ys, xs = np.where(mask)
    ry, rx = np.where(ref)
    if len(ys) == 0:
        return np.zeros_like(ref), 0.0, 1.0
    s = (ry.max() - ry.min() + 1) / (ys.max() - ys.min() + 1)
    return place(mask, ref, s)


def place(mask, ref, s, dx_extra=0, dy_extra=0):
    import cv2
    ys, xs = np.where(mask)
    ry, rx = np.where(ref)
    H, W = ref.shape
    M = np.float32([[s, 0, 0], [0, s, 0]])
    # bottom-centre of mask -> bottom-centre of ref
    bx, by = (xs.min() + xs.max()) / 2 * s, ys.max() * s
    M[0, 2] = (rx.min() + rx.max()) / 2 - bx + dx_extra
    M[1, 2] = ry.max() - by + dy_extra
    out = cv2.warpAffine(mask.astype(np.uint8) * 255, M, (W, H), flags=cv2.INTER_NEAREST) > 127
    iou = (out & ref).sum() / max(1, (out | ref).sum())
    return out, float(iou), s


def attack_pose_vertices(sp, v, j, w, fm, names, clip, frame):
    sk, _parts = sp.build_cached()
    baked = clip["_baked"]
    f = int(min(frame, clip["frames"]))
    rot = {n: baked[n][0][f] for n in names}
    off = {n: baked[n][1][f] - sk.rest_offset(n) for n in names}
    V = pose_vertices(sk, names, v, j, w, rot, off)
    FV = pose_vertices(sk, names, fm["v"], fm["j"], fm["w"], rot, off) if fm else None
    # the reference frames are each framed on the creature: the controller displacement (charge / pounce
    # travel, motion in the clip manifest) is left out so every pose is seen from the same place
    shift = np.zeros(3)
    V = V + shift
    if FV is not None:
        FV = FV + shift
    return V, FV


def cmd_poses(species, rc, out, voxel=0.035):
    """The four attack key poses of `sp.ATTACK_KEYS` against the creature-references pose images: one camera per
    species (az / elevation / scale fitted on the recovery pose), the same camera and scale for all four poses."""
    import bpy  # noqa: F401
    from PIL import Image as PImage
    os.makedirs(out, exist_ok=True)
    sp = importlib.import_module("species." + species)
    keys = sp.ATTACK_KEYS
    v, f, col, j, w, names, fm = proof_mesh(sp, voxel)
    from anim import Quad, SkinSampler
    sk, _parts = sp.build_cached()
    clips = sp.clips(Quad(sk), SkinSampler(sk, v, j, w, names, count=5000))
    clip = next(c for c in clips if c["name"].endswith("__" + keys["clip"]))
    refs = json.load(open(os.path.join(rc, "refs.json")))[species]
    phases = list(refs["poses"].keys())
    masks = {ph: np.asarray(PImage.open(os.path.join(rc, f"{species}_pose_{ph}_mask.png"))) > 127 for ph in phases}
    allF = np.concatenate([f, fm["f"] + len(v)]) if fm else f
    posed = {}
    for ph, fr in zip(phases, keys["frames"]):
        V, FV = attack_pose_vertices(sp, v, j, w, fm, names, clip, fr)
        posed[ph] = np.concatenate([V, FV]) if FV is not None else V
    # camera: the view angle estimated from the sheet (ATTACK_KEYS az / el) refined a little on the recovery pose
    # (closest to a standing stance); the distance is then set so the model appears at the reference's size
    base = "recovery"
    Vb = posed[base]
    lo, hi = Vb.min(0), Vb.max(0)
    centre = (lo + hi) / 2
    dist = float(np.linalg.norm(hi - lo)) * 2.2
    H0, W0 = masks[base].shape
    az0, el0 = keys.get("az", 0.0), keys.get("el", 8.0)
    best = (-1, az0, el0)
    for az in np.arange(az0 - 12, az0 + 13, 3):
        for el in np.arange(el0 - 6, el0 + 7, 2):
            m = silhouette(Vb, allF, cam_for(az, el, dist, centre), centre, 30.0, W0, H0)
            _o, iou, _s = fit_mask(m, masks[base])
            if iou > best[0]:
                best = (iou, az, el)
    _, az, el = best
    _o, _iou, scale = fit_mask(silhouette(Vb, allF, cam_for(az, el, dist, centre), centre, 30.0, W0, H0),
                               masks[base])
    dist = dist / scale
    cam = cam_for(az, el, dist, centre)
    _o, _iou, scale = fit_mask(silhouette(Vb, allF, cam, centre, 30.0, W0, H0), masks[base])
    print(f"POSECAM {species} az {az:.1f} el {el:.1f} dist {dist:.2f} scale {scale:.3f}", flush=True)
    # renders: Cycles, same camera for every pose; the model is placed by the fitted scale, translated per pose
    sc = scene_setup(samples=20)
    res, rows = {}, []
    for ph, fr in zip(phases, keys["frames"]):
        import bpy
        for o in list(bpy.data.objects):
            if o.type == "MESH":
                bpy.data.objects.remove(o, do_unlink=True)
        V, FV = attack_pose_vertices(sp, v, j, w, fm, names, clip, fr)
        add_mesh(V, f, col)
        if fm:
            add_fur(fm, FV, os.path.join(out, "_atlas"))
        ref = masks[ph]
        H, W = ref.shape
        cb = bpy.data.cameras.new("pc")
        cb.lens_unit = "FOV"
        cb.angle = 2 * np.arctan(np.tan(np.radians(30.0) / 2) * 2.0)     # 2x canvas, same pixel scale
        cb.sensor_fit = "HORIZONTAL"
        co = bpy.data.objects.new("pc", cb)
        sc.collection.objects.link(co)
        # glTF -> Blender axes
        cpos = np.array([cam[0], -cam[2], cam[1]])
        tgt = np.array([centre[0], -centre[2], centre[1]])
        co.location = cpos.tolist()
        dvec = tgt - cpos
        from mathutils import Vector
        co.rotation_euler = Vector(dvec.tolist()).to_track_quat("-Z", "Y").to_euler()
        sc.camera = co
        light_rig(sc, co)
        sc.render.resolution_x, sc.render.resolution_y = 2 * W, 2 * H
        path = os.path.join(out, f"{species}_pose_{ph}.png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        im = PImage.open(path).convert("RGBA")
        a = np.asarray(im)[:, :, 3] > 110
        moved, iou, _s = place(a, ref, scale)
        # translation refine (the creature moves through the attack)
        bestp = (iou, 0, 0)
        for ddx in range(-60, 61, 6):
            for ddy in range(-40, 41, 6):
                m2, i2, _ = place(a, ref, scale, ddx, ddy)
                if i2 > bestp[0]:
                    bestp = (i2, ddx, ddy)
        moved, iou, _s = place(a, ref, scale, bestp[1], bestp[2])
        res[ph] = round(iou, 3)
        import cv2
        Mx = np.float32([[scale, 0, 0], [0, scale, 0]])
        ys, xs = np.where(a)
        ry, rx = np.where(ref)
        Mx[0, 2] = (rx.min() + rx.max()) / 2 - (xs.min() + xs.max()) / 2 * scale + bestp[1]
        Mx[1, 2] = ry.max() - ys.max() * scale + bestp[2]
        rgba = cv2.warpAffine(np.asarray(im), Mx, (W, H), flags=cv2.INTER_LINEAR)
        refimg = PImage.open(os.path.join(rc, f"{species}_pose_{ph}_ref.png")).convert("RGB")
        bg = PImage.new("RGBA", (W, H), tuple(int(c) for c in np.asarray(refimg)[3, 3]) + (255,))
        bg.alpha_composite(PImage.fromarray(rgba))
        cut = PImage.open(os.path.join(rc, f"{species}_pose_{ph}_cut.png"))
        ov = refcheck.overlay(ref, moved, cut)
        rows.append([refcheck.label(refimg.copy(), f"{ph}: reference"),
                     refcheck.label(bg.convert("RGB"), f"{ph}: model frame {fr}"),
                     refcheck.label(ov, f"{ph}: overlay IoU {iou:.3f}")])
    th = 300
    tiles = []
    for r in rows:
        tt = [t.resize((int(t.size[0] * th / t.size[1]), th), PImage.LANCZOS) for t in r]
        row = PImage.new("RGB", (sum(t.size[0] for t in tt) + 16, th), (255, 255, 255))
        x = 0
        for t in tt:
            row.paste(t, (x, 0))
            x += t.size[0] + 8
        tiles.append(row)
    sheet = PImage.new("RGB", (max(t.size[0] for t in tiles), (th + 8) * len(tiles)), (255, 255, 255))
    for i, t in enumerate(tiles):
        sheet.paste(t, (0, i * (th + 8)))
    sheet.save(os.path.join(out, f"{species}_poses.jpg"), quality=88)
    print("POSES", species, json.dumps(res), flush=True)
    return res


if __name__ == "__main__" and sys.argv[1] == "poses":
    cmd_poses(sys.argv[2], sys.argv[3], sys.argv[4])


# ------------------------------------------------------------------ locomotion / idle filmstrips
def cmd_cycle(species, rc, out, clips_csv="idle,walk,run", n=8, voxel=0.04):
    """Filmstrip of each clip: n evenly spaced frames, side view at the sheet's scale (half size) and a 3/4 view,
    ground line drawn; the in-place locomotion is shown with the ground sliding back (feet planted on it)."""
    import bpy
    from PIL import Image as PImage
    os.makedirs(out, exist_ok=True)
    sp = importlib.import_module("species." + species)
    v, f, col, j, w, names, fm = proof_mesh(sp, voxel)
    from anim import Quad, SkinSampler
    sk, _parts = sp.build_cached()
    allc = sp.clips(Quad(sk), SkinSampler(sk, v, j, w, names, count=5000))
    refs = json.load(open(os.path.join(rc, "refs.json")))[species]
    ppm = refs["scale"]["px_per_m"] * 0.5
    sheet_rows = []
    for short in clips_csv.split(","):
        clip = next(c for c in allc if c["name"].endswith("__" + short))
        frames = [int(round(i * clip["frames"] / n)) for i in range(n)] if clip["loop"] else \
            [int(round(i * clip["frames"] / (n - 1))) for i in range(n)]
        tiles = []
        for fr in frames:
            V, FV = attack_pose_vertices(sp, v, j, w, fm, names, clip, fr)
            sc = scene_setup(samples=8)
            add_mesh(V, f, col)
            if fm:
                add_fur(fm, FV, os.path.join(out, "_atlas"))
            lo, hi = V.min(0), V.max(0)
            L = max(hi[0] - lo[0], 1.0)
            W = int((L + 1.2) * ppm)
            H = int((max(hi[1], 1.0) + 0.5) * ppm)
            cam_data = bpy.data.cameras.new("c")
            cam_data.type = "ORTHO"
            cam_data.ortho_scale = W / ppm
            cam = bpy.data.objects.new("c", cam_data)
            sc.collection.objects.link(cam)
            cx = (lo[0] + hi[0]) / 2
            cam.location = (cx, 40, (H / 2.0 - 0.3 * ppm) / ppm)
            cam.rotation_euler = (math.radians(90), 0, math.radians(180))
            sc.camera = cam
            light_rig(sc, cam)
            sc.render.resolution_x, sc.render.resolution_y = W, H
            path = os.path.join(out, f"{species}_{short}_{fr:03d}.png")
            sc.render.filepath = path
            bpy.ops.render.render(write_still=True)
            im = PImage.open(path).convert("RGBA")
            bg = PImage.new("RGBA", im.size, (214, 208, 200, 255))
            d = ImageDraw.Draw(bg)
            gy = H - 0.3 * ppm
            d.rectangle([0, gy, W, H], fill=(178, 170, 160, 255))
            # ground ticks that slide back at speed_mps (in-place locomotion), so planted feet stay on a tick
            spd = clip.get("speed_mps", 0.0)
            off = (spd * fr / 30.0) % 0.5
            x = -off
            while x * ppm < W:
                px = W - (x + 0.6) * ppm   # side view: +X (head) to the left
                d.line([(px, gy), (px, gy + 6)], fill=(90, 84, 76, 255), width=2)
                x += 0.5
            bg.alpha_composite(im)
            refcheck.label(bg, f"{short} f{fr}")
            tiles.append(bg.convert("RGB"))
        th = max(t.size[1] for t in tiles)
        row = PImage.new("RGB", (sum(t.size[0] for t in tiles) + 4 * len(tiles), th), (255, 255, 255))
        x = 0
        for t in tiles:
            row.paste(t, (x, th - t.size[1]))
            x += t.size[0] + 4
        sheet_rows.append(row)
    Wt = max(r.size[0] for r in sheet_rows)
    sheet = PImage.new("RGB", (Wt, sum(r.size[1] + 6 for r in sheet_rows)), (255, 255, 255))
    y = 0
    for r in sheet_rows:
        sheet.paste(r, (0, y))
        y += r.size[1] + 6
    path = os.path.join(out, f"{species}_cycles.jpg")
    sheet.save(path, quality=86)
    print("CYCLES", species, path, flush=True)


if __name__ == "__main__" and sys.argv[1] == "cycle":
    a = sys.argv[2:]
    cmd_cycle(a[0], a[1], a[2], a[3] if len(a) > 3 else "idle,walk,run")


def cmd_poses_glb(species, glb, rc, out, voxel=0.035):
    """The attack key poses rendered from the built GLB (textured, its own skinning and clip) with the camera
    fitted on the sculpt (cmd_poses), compared with the creature-references pose images."""
    import bpy
    from PIL import Image as PImage
    import cv2
    os.makedirs(out, exist_ok=True)
    sp = importlib.import_module("species." + species)
    keys = sp.ATTACK_KEYS
    refs = json.load(open(os.path.join(rc, "refs.json")))[species]
    phases = list(refs["poses"].keys())
    masks = {ph: np.asarray(PImage.open(os.path.join(rc, f"{species}_pose_{ph}_mask.png"))) > 127 for ph in phases}
    # camera fit on the coarse sculpt in the recovery pose (same procedure as cmd_poses)
    v, f, col, j, w, names, fm = proof_mesh(sp, voxel)
    from anim import Quad, SkinSampler
    sk, _parts = sp.build_cached()
    clips = sp.clips(Quad(sk), SkinSampler(sk, v, j, w, names, count=5000))
    clip = next(c for c in clips if c["name"].endswith("__" + keys["clip"]))
    allF = np.concatenate([f, fm["f"] + len(v)]) if fm else f
    V, FV = attack_pose_vertices(sp, v, j, w, fm, names, clip, keys["frames"][3])
    Vb = np.concatenate([V, FV]) if FV is not None else V
    lo, hi = Vb.min(0), Vb.max(0)
    centre = (lo + hi) / 2
    dist = float(np.linalg.norm(hi - lo)) * 2.2
    H0, W0 = masks["recovery"].shape
    best = (-1, keys["az"], keys["el"])
    for az in np.arange(keys["az"] - 12, keys["az"] + 13, 3):
        for el in np.arange(keys["el"] - 6, keys["el"] + 7, 2):
            _o, iou, _s = fit_mask(silhouette(Vb, allF, cam_for(az, el, dist, centre), centre, 30.0, W0, H0),
                                   masks["recovery"])
            if iou > best[0]:
                best = (iou, az, el)
    _, az, el = best
    _o, _iou, scale = fit_mask(silhouette(Vb, allF, cam_for(az, el, dist, centre), centre, 30.0, W0, H0),
                               masks["recovery"])
    dist = dist / scale
    cam = cam_for(az, el, dist, centre)
    _o, _iou, scale = fit_mask(silhouette(Vb, allF, cam, centre, 30.0, W0, H0), masks["recovery"])
    print(f"POSECAM {species} az {az:.1f} el {el:.1f} dist {dist:.2f} scale {scale:.3f}", flush=True)
    sc = scene_setup(samples=24)
    import_glb(sc, glb)
    cb = bpy.data.cameras.new("pc")
    cb.lens_unit = "FOV"
    cb.angle = 2 * np.arctan(np.tan(np.radians(30.0) / 2) * 2.0)
    cb.sensor_fit = "HORIZONTAL"
    co = bpy.data.objects.new("pc", cb)
    sc.collection.objects.link(co)
    from mathutils import Vector
    cpos = np.array([cam[0], -cam[2], cam[1]])
    tgt = np.array([centre[0], -centre[2], centre[1]])
    co.location = cpos.tolist()
    co.rotation_euler = Vector((tgt - cpos).tolist()).to_track_quat("-Z", "Y").to_euler()
    sc.camera = co
    light_rig(sc, co)
    res, rows = {}, []
    for ph, fr in zip(phases, keys["frames"]):
        set_clip(sc, species, keys["clip"], fr)
        ref = masks[ph]
        H, W = ref.shape
        sc.render.resolution_x, sc.render.resolution_y = 2 * W, 2 * H
        path = os.path.join(out, f"{species}_glbpose_{ph}.png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        im = PImage.open(path).convert("RGBA")
        a = np.asarray(im)[:, :, 3] > 110
        bestp = (-1, 0, 0)
        for ddx in range(-60, 61, 6):
            for ddy in range(-40, 41, 6):
                _m2, i2, _ = place(a, ref, scale, ddx, ddy)
                if i2 > bestp[0]:
                    bestp = (i2, ddx, ddy)
        moved, iou, _s = place(a, ref, scale, bestp[1], bestp[2])
        res[ph] = round(iou, 3)
        Mx = np.float32([[scale, 0, 0], [0, scale, 0]])
        ys, xs = np.where(a)
        ry, rx = np.where(ref)
        Mx[0, 2] = (rx.min() + rx.max()) / 2 - (xs.min() + xs.max()) / 2 * scale + bestp[1]
        Mx[1, 2] = ry.max() - ys.max() * scale + bestp[2]
        rgba = cv2.warpAffine(np.asarray(im), Mx, (W, H), flags=cv2.INTER_LINEAR)
        refimg = PImage.open(os.path.join(rc, f"{species}_pose_{ph}_ref.png")).convert("RGB")
        bg = PImage.new("RGBA", (W, H), tuple(int(c) for c in np.asarray(refimg)[3, 3]) + (255,))
        bg.alpha_composite(PImage.fromarray(rgba))
        bg.convert("RGB").save(os.path.join(out, f"{species}_glbpose_{ph}_aligned.png"))  # for tools/detail.py
        cut = PImage.open(os.path.join(rc, f"{species}_pose_{ph}_cut.png"))
        ov = refcheck.overlay(ref, moved, cut)
        rows.append([refcheck.label(refimg.copy(), f"{ph}: reference"),
                     refcheck.label(bg.convert("RGB"), f"{ph}: model {keys['clip']} frame {fr}"),
                     refcheck.label(ov, f"{ph}: overlay IoU {iou:.3f}")])
    th = 300
    tiles = []
    for r in rows:
        tt = [t.resize((int(t.size[0] * th / t.size[1]), th), PImage.LANCZOS) for t in r]
        row = PImage.new("RGB", (sum(t.size[0] for t in tt) + 16, th), (255, 255, 255))
        x = 0
        for t in tt:
            row.paste(t, (x, 0))
            x += t.size[0] + 8
        tiles.append(row)
    sheet = PImage.new("RGB", (max(t.size[0] for t in tiles), (th + 8) * len(tiles)), (255, 255, 255))
    for i, t in enumerate(tiles):
        sheet.paste(t, (0, i * (th + 8)))
    sheet.save(os.path.join(out, f"{species}_glbposes.jpg"), quality=88)
    print("GLBPOSES", species, json.dumps(res), flush=True)
    json.dump({"camera": {"az": float(az), "el": float(el), "dist": float(dist)}, "iou": res},
              open(os.path.join(out, f"{species}_glbposes.json"), "w"), indent=1)
    return res


if __name__ == "__main__" and sys.argv[1] == "glbposes":
    cmd_poses_glb(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])


def cmd_glbcycles(species, glb, out, clips_csv="idle,walk,run", n=6):
    """Filmstrips of the built GLB's clips from a 3/4 front view (perspective, the same camera for every frame):
    n evenly spaced frames per clip, one row per clip."""
    import bpy
    from PIL import Image as PImage
    from mathutils import Vector
    os.makedirs(out, exist_ok=True)
    sc = scene_setup(samples=12)
    import_glb(sc, glb)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    set_clip(sc, species, "idle", 0)
    lo, hi = bounds_blender(meshes)
    centre = (lo + hi) / 2
    size = float(np.max(hi - lo))
    cb = bpy.data.cameras.new("fc")
    cb.lens_unit = "FOV"
    cb.angle = math.radians(32)
    co = bpy.data.objects.new("fc", cb)
    sc.collection.objects.link(co)
    # Blender axes: +X forward (head), -Y = creature's right; a 3/4 view from the front-left, a little above
    d = Vector((0.42, 0.88, 0.26)).normalized()
    co.location = Vector(centre.tolist()) + d * size * 1.9
    co.rotation_euler = (Vector(centre.tolist()) - co.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = co
    light_rig(sc, co)
    sc.render.resolution_x, sc.render.resolution_y = 520, 360
    rows = []
    for short in clips_csv.split(","):
        act = next((a for a in bpy.data.actions if a.name.startswith(f"{species}__{short}")), None)
        if act is None:
            continue
        f0, f1 = act.frame_range
        frames = [int(round(f0 + (f1 - f0) * i / n)) for i in range(n)]
        tiles = []
        for fr in frames:
            set_clip(sc, species, short, fr)
            path = os.path.join(out, f"{species}_cyc_{short}_{fr:03d}.png")
            sc.render.filepath = path
            bpy.ops.render.render(write_still=True)
            im = PImage.open(path).convert("RGBA")
            bg = PImage.new("RGBA", im.size, (214, 208, 200, 255))
            bg.alpha_composite(im)
            tiles.append(refcheck.label(bg.convert("RGB"), f"{short} frame {fr}"))
        row = PImage.new("RGB", (sum(t.size[0] for t in tiles) + 4 * len(tiles), tiles[0].size[1]), (255, 255, 255))
        x = 0
        for t in tiles:
            row.paste(t, (x, 0))
            x += t.size[0] + 4
        rows.append(row)
    sheet = PImage.new("RGB", (max(r.size[0] for r in rows), sum(r.size[1] + 4 for r in rows)), (255, 255, 255))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.size[1] + 4
    path = os.path.join(out, f"{species}_glbcycles.jpg")
    sheet.save(path, quality=86)
    print("GLBCYCLES", species, path, flush=True)


if __name__ == "__main__" and sys.argv[1] == "glbcycles":
    cmd_glbcycles(sys.argv[2], sys.argv[3], sys.argv[4])
