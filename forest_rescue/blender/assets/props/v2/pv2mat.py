"""Props v2 material path (build_asset.run dispatches here when the module sets MATERIAL_MODE = True).

Clean modelled geometry + one seamless painted-style tile per material class (mattex), no painting projection and
no alpha:
  solve (cameras + blueprint, module.solve) -> LOD0/1/2 geometry -> per-face UVs box-mapped in metres in each
  primitive's own frame (u along its longest axis: grain along every beam; rope turns round the drum; authored
  UVs for grass blades) -> material classes rasterised at the solved painting camera -> de-lit colour ramps from
  the painting's own pixels of every class -> tiles (mattex) -> Blender materials shared by all LODs -> QA renders
  (pv2.compare: same IoU / colour-error metrics as the projection path) -> one colour calibration pass (per-class
  gain render vs painting) -> clips -> GLB + external tiles + meta -> Godot import check.

Module contract (on top of the v2 one): MATERIAL_MODE, CLASSES, TILE_M {class: metres per tile}, UV_RULES
{tag prefix: box | coil | tube | fixed}, PAINT_K, optional make_tiles(ramps, rng) and VOID_COLOUR.
"""
import math
import os
import time

import numpy as np

import pv2
import bpy  # noqa: E402
from frlib import core  # noqa: E402
import bl  # noqa: E402
import tex  # noqa: E402
import mattex as MT  # noqa: E402
from geo import triangulate  # noqa: E402


# ============================================================================ UVs
def rule_for(tag, rules):
    best, n = "box", -1
    for k, r in rules.items():
        if tag.startswith(k) and len(k) > n:
            best, n = r, len(k)
    return best


def assign_uvs(g, M, rng):
    """Per-face UVs (metres / tile) for every face of Geo g, written into g.UV (fixed UVs for bl.object_from_geo)."""
    V, F, Mc, Tg, UV = g.arrays()
    if not len(F):
        return
    starts = np.cumsum([0] + [len(v) for v in g.V])
    prim = np.searchsorted(starts, np.array([f[0] for f in F]), side="right") - 1
    frames = {}
    for pi in np.unique(prim):
        P = V[starts[pi]:starts[pi + 1]]
        c = P.mean(0)
        if len(P) >= 3:
            w, vecs = np.linalg.eigh(np.cov((P - c).T) + np.eye(3) * 1e-9)
            R = vecs[:, np.argsort(w)[::-1]]
        else:
            R = np.eye(3)
        if np.linalg.det(R) < 0:
            R[:, 2] *= -1
        frames[pi] = (c, R, rng.uniform(0, 1, 2))
    tile = M.TILE_M
    rows = getattr(M, "ROPE_ROWS", 4)
    trims = dict(getattr(M, "TRIM_CLASSES", {}))     # class -> max face width (m) that takes the trim mapping
    trim_tags = {c: tuple(t) for c, t in getattr(M, "TRIM_TAGS", {}).items()}
    out = []
    for fi, (f, mc, tg, uv) in enumerate(zip(F, Mc, Tg, UV)):
        rule = rule_for(str(tg), M.UV_RULES)
        if rule == "fixed" and uv is not None:
            out.append(uv)
            continue
        P = V[f]
        c, R, off = frames[prim[fi]]
        if rule == "coil":
            # rope turns round the drum axle (world X through the primitive's centre): u round, v along the axle
            ang = np.arctan2(P[:, 2] - c[2], P[:, 1] - c[1])
            if ang.max() - ang.min() > math.pi:
                ang = np.where(ang < 0, ang + 2 * math.pi, ang)
            rad = float(np.mean(np.hypot(P[:, 2] - c[2], P[:, 1] - c[1])))
            n_round = max(1, int(round(2 * math.pi * rad / tile.get("rope", 0.3))))
            u = ang / (2 * math.pi) * n_round
            v = (P[:, 0] - c[0]) / (rows * getattr(M, "ROPE_D", 0.07))
            out.append([(float(a), float(b)) for a, b in zip(u, v)])
            continue
        q = (P - c) @ R
        n = np.cross(P[1] - P[0], P[2] - P[0])
        n = n / max(np.linalg.norm(n), 1e-12)
        k = int(np.argmax(np.abs(n @ R)))
        uvm = q[:, [1, 2]] if k == 0 else (q[:, [0, 2]] if k == 1 else q[:, [0, 1]])
        ttags = trim_tags.get(str(mc))
        if rule == "box" and str(mc) in trims and len(f) == 4 and (ttags is None or str(tg).startswith(ttags)):
            # trim: an elongated face (beam side, strap, band) takes the tile's full height across its width, so the
            # tile's edge band lands on the face's long edges; u stays metric along the grain
            span = np.ptp(uvm, 0)
            a_, b_ = (0, 1) if span[0] >= span[1] else (1, 0)
            if span[b_] <= trims[str(mc)] and span[a_] >= span[b_] * 1.15:
                along = uvm[:, a_] / tile.get(str(mc), 1.0) + off[0]
                across = (uvm[:, b_] - uvm[:, b_].min()) / max(span[b_], 1e-6)
                out.append([(float(x), float(y)) for x, y in zip(along, across)])
                continue
        if rule == "tube":
            # one rope row across the tube's diameter, the lay along its length
            d = max(float(np.ptp(q[:, 1])), float(np.ptp(q[:, 2])), 0.02)
            uvm = np.stack([uvm[:, 0] / tile.get("rope", 0.3), uvm[:, 1] / (rows * 0.06)], 1)
        else:
            s = tile.get(str(mc), 1.0)
            uvm = uvm / s
        uvm = uvm + off
        out.append([(float(a), float(b)) for a, b in uvm])
    g.UV = out


# ============================================================================ painting colour ramps per class
def class_raster(A, v, lod=0):
    """Per painting pixel: material class index (-1 none) and face normal of the nearest triangle, posed for v."""
    pose = v.pose
    Wm = A.world_mats(pose)
    Vs, Ts, ids, Ns = [], [], [], []
    off = 0
    classes = []
    for nm, part in A.parts.items():
        Mx = Wm.get(nm)
        if Mx is None:
            continue
        V, F, Mc, Tg, _ = part.geo[lod].arrays()
        if not len(V):
            continue
        Vw = V @ Mx[:3, :3].T + Mx[:3, 3]
        for f, mc in zip(F, Mc):
            if mc not in classes:
                classes.append(mc)
            ci = classes.index(mc)
            for t in triangulate([f]):
                Ts.append([off + t[0], off + t[1], off + t[2]])
                ids.append(ci)
        Vs.append(Vw)
        off += len(Vw)
    V = np.concatenate(Vs)
    T = np.array(Ts)
    ids = np.array(ids)
    W_, H_ = v.size
    tri_id, zb = tex.id_buffer(v.cam, W_, H_, V, T, np.arange(len(T)))
    cls = np.where(tri_id >= 0, ids[np.maximum(tri_id, 0)], -1)
    e1 = V[T[:, 1]] - V[T[:, 0]]
    e2 = V[T[:, 2]] - V[T[:, 0]]
    FN = np.cross(e1, e2)
    FN /= np.maximum(np.linalg.norm(FN, axis=1, keepdims=True), 1e-12)
    # face the camera (double-sided look)
    C = v.cam.centre
    cen = V[T].mean(1)
    flip = ((C - cen) * FN).sum(1) < 0
    FN[flip] *= -1
    nrm = np.where(tri_id[..., None] >= 0, FN[np.maximum(tri_id, 0)], 0.0)
    return cls, classes, nrm


def _l(c):
    return c @ np.array([0.299, 0.587, 0.114])


# plausibility gates on the painting's raw colours (misregistered pixels of other materials / background out)
DEFAULT_RAMP_GATES = {
    "wood": lambda c: (c[..., 0] - c[..., 2] > 0.08) & (_l(c) > 0.1) & (_l(c) < 0.85),
    "iron": lambda c: (_l(c) < 0.5) & (c[..., 0] - c[..., 2] < 0.22),
    "rope": lambda c: (c[..., 0] - c[..., 2] > 0.1) & (_l(c) > 0.12),
    "stone": lambda c: (np.abs(c[..., 0] - c[..., 2]) < 0.16) & (_l(c) > 0.12),
    "brass": lambda c: (c[..., 0] - c[..., 2] > 0.12) & (_l(c) > 0.12),
    "grass": lambda c: (c[..., 1] - c[..., 2] > 0.04) & (np.abs(c[..., 0] - c[..., 1]) < 0.14),
}


def measure_ramps(A, v, k, M, log=pv2.log):
    """De-lit colour ramps of every class from the painting pixels the posed geometry covers (eroded mask)."""
    from scipy import ndimage as ndi
    cls, classes, nrm = class_raster(A, v)
    ref, _ = v.mask()
    ref = ndi.binary_erosion(ref, iterations=2)
    ig = v.ignore()
    if ig is not None:
        ref &= ~ig
    crop = v.crop
    L = np.asarray(v.light, float)
    L /= np.linalg.norm(L)
    shade = (1 - k) + k * np.clip(nrm @ L, 0, 1)
    ramps, stats = {}, {}
    _, bgc = v.mask()
    gates = dict(DEFAULT_RAMP_GATES)
    gates.update(getattr(M, "RAMP_GATES", {}))
    far_bg = np.linalg.norm(crop - bgc[None, None], axis=2) > 0.075
    bg_ok = set(getattr(M, "RAMP_BG_OK", ("stone", "ground")))     # these really are close to the backdrop grey
    for ci, c in enumerate(classes):
        sel = (cls == ci) & ref & (True if c in bg_ok else far_bg)
        # one-pixel class border trimmed (anti-aliased neighbours of other materials)
        sel &= ndi.binary_erosion(cls == ci, iterations=1)
        if c in gates:
            sel &= gates[c](crop)
        if sel.sum() < 40:
            continue
        px = crop[sel] / np.maximum(shade[sel], 0.3)[:, None]
        px = np.clip(px, 0, 1)
        ramps[c] = px
        stats[c] = dict(px=int(sel.sum()), mean_srgb=[round(float(x) * 255) for x in px.mean(0)])
    log("  painted pixels per class (de-lit): " + ", ".join(f"{c} {s['px']} {s['mean_srgb']}" for c, s in stats.items()))
    return ramps, stats, (cls, classes, nrm)


# ============================================================================ tiles
def default_tiles(M, px, sheet, rng):
    """Tiles from the measured painting pixels (class -> HxWx3)."""
    L = MT.LUMA

    def chroma(p):
        return np.linalg.norm(p - (p @ L)[:, None], axis=1)
    T = {}
    if "wood" in px:
        T["wood"] = MT.wood(512, MT.ramp(px["wood"]), rng)
    if "iron" in px:
        ir = px["iron"]
        rust = ir[(chroma(ir) > np.percentile(chroma(ir), 85)) & (ir[:, 0] > ir[:, 2] + 0.06)]
        rust_col = rust.mean(0) if len(rust) > 20 else np.array([0.45, 0.3, 0.2])
        base = ir[chroma(ir) <= np.percentile(chroma(ir), 80)]
        T["iron"] = MT.iron(512, MT.ramp(base), rust_col, rng, rust_amount=0.05)
    if "rope" in px:
        T["rope"] = MT.rope(512, MT.ramp(px["rope"]), rng, rows=getattr(M, "ROPE_ROWS", 4))
    if "stone" in px:
        st = px["stone"]
        gr = st[(st[:, 1] > st[:, 2] + 0.05) & (st[:, 1] >= st[:, 0] - 0.02)]
        moss = gr.mean(0) if len(gr) > 20 else np.array([0.42, 0.42, 0.22])
        T["stone"] = MT.stone(512, MT.ramp(st[chroma(st) < np.percentile(chroma(st), 85)]), moss, rng, moss=0.07)
    if "brass" in px:
        T["brass"] = MT.brass(256, MT.ramp(px["brass"]), rng)
    gr_px = px.get("grass")
    if gr_px is None or len(gr_px) < 40:
        gr_px = np.array([[0.30, 0.30, 0.16], [0.45, 0.42, 0.22], [0.62, 0.55, 0.3]])
    gs = gr_px[np.argsort(gr_px @ L)]
    g_root, g_mid, g_tip = gs[int(len(gs) * 0.3)], gs[int(len(gs) * 0.62)], gs[int(len(gs) * 0.92)]
    if "ground" in px:
        gp = px["ground"]
        dirt = gp[chroma(gp) < np.percentile(chroma(gp), 70)]
        leaf = gp[(gp[:, 0] > gp[:, 2] + 0.12) & (gp[:, 0] > gp[:, 1] + 0.04)]
        if len(leaf) < 20:
            leaf = np.array([[0.62, 0.42, 0.25], [0.55, 0.36, 0.2], [0.7, 0.52, 0.3]])
        lq = leaf[np.argsort(leaf @ L)]
        leafs = [lq[int(len(lq) * q)] for q in (0.3, 0.55, 0.8)]
        pebble = MT.ramp(px["stone"]) if "stone" in px else MT.ramp(dirt)
        T["ground"] = MT.ground(1024, MT.ramp(dirt), leafs, g_mid, pebble, rng, leaves=0.05, grass=0.05, pebbles=0.05)
    T["grass"] = MT.grass(256, g_root, g_mid, g_tip)
    T["void"] = np.ones((8, 8, 3)) * np.asarray(getattr(M, "VOID_COLOUR", (0.05, 0.045, 0.04)))
    return T


# ============================================================================ Blender side
def make_materials(aid, tiles):
    imgs, mats = {}, {}
    for c, arr in tiles.items():
        imgs[c] = bl.image_from_array(f"{aid}_{c}_c", arr)
        m = core.material(f"{aid}_{c}", base_tex=imgs[c], rough={"iron": 0.6, "brass": 0.45}.get(c, 0.88),
                          metal={"iron": 0.0, "brass": 0.0}.get(c, 0.0), double_sided=(c == "grass"))
        mats[c] = m
    return imgs, mats


def set_tile(img, arr):
    h, w = arr.shape[:2]
    a = np.concatenate([np.asarray(arr, np.float32), np.ones((h, w, 1), np.float32)], 2)
    img.pixels.foreach_set(np.ascontiguousarray(a[::-1]).ravel())
    img.update()
    img.pack()


def smooth_by_angle(B, angle=40.0, sharp_tags=()):
    """Smooth shading split at edges sharper than `angle`; faces whose tag starts with one of sharp_tags (rubble,
    rough stones) keep every edge sharp (faceted)."""
    import bmesh
    for key, o in B.objs.items():
        me = o.data
        me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
        me.set_sharp_from_angle(angle=math.radians(angle))
        tags = B.finfo[key]["tag"]
        if sharp_tags and any(str(t).startswith(sharp_tags) for t in tags):
            bm = bmesh.new()
            bm.from_mesh(me)
            bm.faces.ensure_lookup_table()
            for f in bm.faces:
                if str(tags[f.index]).startswith(sharp_tags):
                    for e in f.edges:
                        e.smooth = False
            bm.to_mesh(me)
            bm.free()
        me.update()


# ============================================================================ baked vertex AO (COLOR_0 alpha)
AO_FLOOR = 0.42          # forest_painted.gdshaderinc: v_ao = mix(ao_floor, 1, COLOR.a^2)


def _hemi_dirs(n, seed=3):
    """Cosine-weighted hemisphere directions (local frame, +Z up), stratified."""
    rng = np.random.default_rng(seed)
    k = int(math.ceil(math.sqrt(n)))
    out = []
    for i in range(k):
        for j in range(k):
            u1 = (i + rng.uniform(0.1, 0.9)) / k
            u2 = (j + rng.uniform(0.1, 0.9)) / k
            r, phi = math.sqrt(u1), 2 * math.pi * u2
            out.append((r * math.cos(phi), r * math.sin(phi), math.sqrt(max(0.0, 1 - u1))))
    return np.array(out[:n])


def bake_vertex_ao(A, B, M, log=pv2.log):
    """Per face-corner ambient occlusion (cosine-weighted hemisphere, distance falloff) times a soft sun-shadow term
    (cone of rays toward M.AO_SUN) for every LOD mesh at rest, each part occluded by M.ao_occluders(part) only
    (moving parts by themselves). Written as colour attribute 'Col' (RGB 1, A = sqrt((F - floor) / (1 - floor)),
    the game's painted shader turns A back into F)."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    rays = getattr(M, "AO_RAYS", 40)
    dist = getattr(M, "AO_DIST", 0.9)
    strength = getattr(M, "AO_STRENGTH", 0.75)
    sun = getattr(M, "AO_SUN", None)
    sun_strength = getattr(M, "AO_SUN_STRENGTH", 0.35)
    H = _hemi_dirs(rays)
    cone = None
    if sun is not None:
        L = np.asarray(sun, float)
        L /= np.linalg.norm(L)
        Rl = np.array(pv2.G.frame_from(L))
        cone = [L] + [Rl[:, 0] * math.cos(0.12) + math.sin(0.12) * (Rl[:, 1] * math.cos(a) + Rl[:, 2] * math.sin(a))
                      for a in np.linspace(0, 2 * math.pi, 6, endpoint=False)]
    stats = {}
    for lod in range(3):
        geo = {}
        for (l_, nm), o in B.objs.items():
            if l_ != lod:
                continue
            me = o.data
            mw = np.array(o.matrix_world)
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get("co", co)
            V = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
            geo[nm] = (o, V, [list(p.vertices) for p in me.polygons])
        trees = {}
        vals = []
        for nm, (o, V, P) in geo.items():
            occ = tuple(sorted(x for x in M.ao_occluders(nm) if x in geo))
            if not occ:
                F = np.ones(sum(len(p) for p in P))
            else:
                if occ not in trees:
                    Vs, Ps, off = [], [], 0
                    for x in occ:
                        Vs.append(geo[x][1])
                        Ps += [[i + off for i in p] for p in geo[x][2]]
                        off += len(geo[x][1])
                    trees[occ] = BVHTree.FromPolygons([tuple(v) for v in np.concatenate(Vs)], Ps)
                tree = trees[occ]
                F = []
                fcls = B.finfo[(lod, nm)]["cls"]
                cstr = getattr(M, "AO_CLASS_STRENGTH", {})
                for pi_, p in enumerate(P):
                    Q = V[p]
                    n = np.cross(Q[1] - Q[0], Q[2] - Q[0])
                    if len(p) > 3:
                        n = n + np.cross(Q[2] - Q[0], Q[3] - Q[0])
                    nn = np.linalg.norm(n)
                    n = n / nn if nn > 1e-12 else np.array([0, 0, 1.0])
                    fstr = cstr.get(str(fcls[pi_]), strength) if cstr else strength
                    Rf = np.array(pv2.G.frame_from(n))       # local X = n
                    dirs = H[:, 2:3] * n + H[:, 0:1] * Rf[:, 1] + H[:, 1:2] * Rf[:, 2]
                    dirs = [Vector(tuple(d)) for d in dirs]
                    cen = Q.mean(0)
                    for q in Q:
                        o_ = q + (cen - q) * 0.12 + n * 0.006
                        ov = Vector(tuple(o_))
                        occl = 0.0
                        for d in dirs:
                            hit = tree.ray_cast(ov, d, dist)
                            if hit[0] is not None:
                                occl += 1.0 - (hit[3] / dist) ** 0.5 * 0.6
                        ao = 1.0 - occl / len(dirs)
                        f = 1.0 - fstr * (1.0 - ao)
                        if cone is not None and float(n @ cone[0]) > 0.02:
                            sh = 0
                            for d in cone:
                                if tree.ray_cast(ov, Vector(tuple(d)), 6.0)[0] is not None:
                                    sh += 1
                            f *= 1.0 - sun_strength * sh / len(cone)
                        F.append(f)
                F = np.array(F)
            F = np.clip(F, AO_FLOOR, 1.0)
            a = np.sqrt((F - AO_FLOOR) / (1.0 - AO_FLOOR))
            me = o.data
            attr = me.color_attributes.get("Col") or me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
            cols = np.ones((len(me.loops), 4), np.float32)
            cols[:, 3] = a.astype(np.float32)
            attr.data.foreach_set("color", cols.ravel())
            me.color_attributes.active_color = attr
            me.color_attributes.render_color_index = list(me.color_attributes).index(attr)
            vals.append(F)
        allF = np.concatenate(vals) if vals else np.ones(1)
        stats[f"LOD{lod}"] = dict(mean=round(float(allF.mean()), 3), p10=round(float(np.percentile(allF, 10)), 3))
    log(f"  vertex AO baked: {stats}")
    return stats


def qa_material_ao(src, k, light):
    """QA twin of the game's painted shader with vertex AO: emission = albedo * mix(1, lambert, k) *
    mix(AO_FLOOR, 1, Col.a^2)."""
    name = f"{src.name}_qaao{k:.2f}"
    if bpy.data.materials.get(name):
        return bpy.data.materials[name]
    base = bl.painted_qa_material(src, k, light)
    m = base.copy()
    m.name = name
    nt = m.node_tree
    em = next(n for n in nt.nodes if n.type == "EMISSION")
    link = next(l_ for l_ in nt.links if l_.to_node == em and l_.to_socket.name == "Color")
    src_sock = link.from_socket
    nt.links.remove(link)
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "Col"
    sq = nt.nodes.new("ShaderNodeMath")
    sq.operation = "MULTIPLY"
    nt.links.new(vc.outputs["Alpha"], sq.inputs[0])
    nt.links.new(vc.outputs["Alpha"], sq.inputs[1])
    mx = nt.nodes.new("ShaderNodeMath")
    mx.operation = "MULTIPLY_ADD"
    mx.inputs[1].default_value = 1.0 - AO_FLOOR
    mx.inputs[2].default_value = AO_FLOOR
    nt.links.new(sq.outputs["Value"], mx.inputs[0])
    sc = nt.nodes.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    nt.links.new(src_sock, sc.inputs[0])
    nt.links.new(mx.outputs["Value"], sc.inputs["Scale"])
    nt.links.new(sc.outputs["Vector"], em.inputs["Color"])
    return m


def use_qa_ao(objs, light, on=True):
    for o in objs:
        for i, s_ in enumerate(o.material_slots):
            if on:
                s_.link = "OBJECT"
                s_.material = qa_material_ao(o.data.materials[i], pv2.PAINT_K, light)
            else:
                s_.link = "DATA"


def class_gains(rgba, v, cls_info, classes_wanted, ig=None):
    """Per-class mean colour of the painting / of the render on the same pixels (sRGB)."""
    from scipy import ndimage as ndi
    cls, classes = cls_info[0], cls_info[1]
    ref, _ = v.mask()
    a = rgba[..., 3] > 0.9
    use = ndi.binary_erosion(ref & a, iterations=2)
    if ig is not None:
        use &= ~ig
    crop = v.crop
    out = {}
    for ci, c in enumerate(classes):
        if c not in classes_wanted:
            continue
        sel = use & (cls == ci) & ndi.binary_erosion(cls == ci, iterations=1)
        if sel.sum() < 60:
            continue
        pm = crop[sel].mean(0)
        rm = rgba[..., :3][sel].mean(0)
        out[c] = (np.clip(pm / np.maximum(rm, 1e-3), 0.6, 1.6), int(sel.sum()), pm, rm)
    return out


def fullres_sheet(v, rgba, out_png, title):
    """Painting crop | render (both 2x, no resampling blur beyond cubic) side by side, background composited."""
    import cv2
    from PIL import Image
    ref = v.crop
    _, bg = v.mask()
    a = rgba[..., 3:4]
    comp = rgba[..., :3] * a + bg[None, None] * (1 - a)
    panels = []
    for img, txt in ((ref, "reference (painting)"), (comp, "render (painted light)")):
        u8 = (np.clip(img, 0, 1) * 255).astype(np.uint8)
        u8 = cv2.resize(u8, (u8.shape[1] * 2, u8.shape[0] * 2), interpolation=cv2.INTER_CUBIC)
        panels.append(pv2._label(u8, txt))
    sheet = np.concatenate([panels[0], np.full((panels[0].shape[0], 8, 3), 30, np.uint8), panels[1]], 1)
    top = pv2._label(np.full((24, sheet.shape[1], 3), 28, np.uint8), title)
    Image.fromarray(np.concatenate([top, sheet], 0)).save(out_png)


def render_closeups(A, B, v, out_png, title, boxes, scale=4):
    """Native-resolution close-ups (render at ss=4 of the painting camera: 4x the painting crop) of sheet boxes,
    painting above render."""
    import cv2
    from PIL import Image
    rgba = render_hi(A, B, v, scale)
    _, bg = v.mask()
    comp = rgba[..., :3] * rgba[..., 3:4] + bg[None, None] * (1 - rgba[..., 3:4])
    ref = v.crop
    x0, y0 = v.box[:2]
    cols = []
    for (a, b, c, d) in boxes:
        pr = ref[b - y0:d - y0, a - x0:c - x0]
        pr = cv2.resize((np.clip(pr, 0, 1) * 255).astype(np.uint8), ((c - a) * scale, (d - b) * scale),
                        interpolation=cv2.INTER_CUBIC)
        rr = (np.clip(comp[(b - y0) * scale:(d - y0) * scale, (a - x0) * scale:(c - x0) * scale], 0, 1) * 255).astype(np.uint8)
        cols.append(np.concatenate([pr, np.full((6, pr.shape[1], 3), 30, np.uint8), rr], 0))
    hmax = max(c_.shape[0] for c_ in cols)
    cols = [np.concatenate([c_, np.full((hmax - c_.shape[0], c_.shape[1], 3), 30, np.uint8)], 0) for c_ in cols]
    sheet = np.concatenate(sum([[c_, np.full((hmax, 8, 3), 30, np.uint8)] for c_ in cols], [])[:-1], 1)
    top = pv2._label(np.full((24, sheet.shape[1], 3), 28, np.uint8), title)
    Image.fromarray(np.concatenate([top, sheet], 0)).save(out_png)
    return rgba


def render_hi(A, B, v, scale):
    """Render at `scale` x the painting crop resolution (undistorted pinhole of the solved camera, no warp)."""
    pv2.set_pose(A, B, pv2.rpose(v))
    hid = pv2.hidden_parts(A, pv2.rpose(v))
    objs = [o for (l_, nm), o in B.objs.items() if l_ == 0 and nm not in hid]
    pv2.use_qa(objs, v.light, True)
    rgba = _render_scaled(v, objs, scale)
    pv2.use_qa(objs, v.light, False)
    pv2.rest(A, B)
    return rgba


def _render_scaled(v, objs, scale):
    """Like bl.render_painting_cam with ss=scale but returns the full scale x scale image (no downsample)."""
    import cv2
    from mathutils import Matrix
    cam = v.cam
    W, H = v.size
    bl.only(objs)
    ss = scale
    RW, RH = W * ss, H * ss
    f = cam.f * ss
    cx, cy = cam.cx * ss, cam.cy * ss
    cd = bpy.data.cameras.get("lm3_cam") or bpy.data.cameras.new("lm3_cam")
    co = bpy.data.objects.get("lm3_cam") or core.link(bpy.data.objects.new("lm3_cam", cd))
    cd.type = "PERSP"
    cd.sensor_fit = "HORIZONTAL" if RW >= RH else "VERTICAL"
    cd.sensor_width = cd.sensor_height = 36.0
    cd.lens = f * 36.0 / max(RW, RH)
    cd.shift_x = (RW / 2.0 - cx) / max(RW, RH)
    cd.shift_y = (cy - RH / 2.0) / max(RW, RH)
    cd.clip_start = 0.1
    cd.clip_end = 2000
    R = cam.R
    rot = np.stack([R[0], -R[1], -R[2]], 1)
    Mx = np.eye(4)
    Mx[:3, :3] = rot
    Mx[:3, 3] = cam.centre
    co.matrix_world = Matrix(Mx.tolist())
    sc = bpy.context.scene
    sc.camera = co
    sc.render.resolution_x, sc.render.resolution_y = RW, RH
    sc.render.resolution_percentage = 100
    img = bl.render_rgba()
    # radial distortion warp at the high resolution
    mapx, mapy = cam.undistort_maps(W, H)
    mapx = cv2.resize(mapx.astype(np.float32), (RW, RH), interpolation=cv2.INTER_LINEAR) * ss + (ss - 1) / 2.0
    mapy = cv2.resize(mapy.astype(np.float32), (RW, RH), interpolation=cv2.INTER_LINEAR) * ss + (ss - 1) / 2.0
    out = cv2.remap(img.astype(np.float32), mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                    borderValue=(0, 0, 0, 0))
    rgb = out[..., :3] / np.maximum(out[..., 3:4], 1e-6)
    return np.concatenate([np.clip(rgb, 0, 1), out[..., 3:4]], 2)


def game_view(A, B, out_png, light_game, lod=0, res=900, pose=None, k=0.55, title=""):
    """Orthographic render from the city camera's direction (model front toward the camera, 38 deg down), lit
    by the game's sun direction in model space; returns RGBA."""
    from PIL import Image
    from mathutils import Matrix, Vector
    pv2.set_pose(A, B, pose or {})
    hid = pv2.hidden_parts(A, pose or {})
    objs = [o for (l_, nm), o in B.objs.items() if l_ == lod and nm not in hid]
    pv2.use_qa(objs, light_game, True)
    bl.only(objs)
    lo, hi = core.bounds(objs)
    c = (lo + hi) / 2
    size = float(np.linalg.norm(hi - lo))
    e = math.atan(83.0 / (75.0 * math.sqrt(2)))
    d = Vector((0.0, math.cos(e), -math.sin(e)))          # view direction: from the front (-Y) and above, looking +Y down
    cd = bpy.data.cameras.get("mat_game") or bpy.data.cameras.new("mat_game")
    co = bpy.data.objects.get("mat_game") or core.link(bpy.data.objects.new("mat_game", cd))
    cd.type = "ORTHO"
    cd.ortho_scale = size * 0.78
    cd.clip_start = 0.01
    cd.clip_end = size * 6
    co.location = Vector(c.tolist()) - d * size * 2
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc = bpy.context.scene
    sc.camera = co
    sc.render.resolution_x = res
    sc.render.resolution_y = int(res * 0.78)
    rgba = bl.render_rgba()
    pv2.use_qa(objs, light_game, False)
    pv2.rest(A, B)
    bg = np.array([0.80, 0.72, 0.55])          # camp sand
    comp = rgba[..., :3] * rgba[..., 3:4] + bg * (1 - rgba[..., 3:4])
    img = (np.clip(comp, 0, 1) * 255).astype(np.uint8)
    if title:
        img = pv2._label(img, title)
    Image.fromarray(img).save(out_png)
    return rgba


def clip_sheet(A, B, M, out_png, light):
    """Frames of a clip rendered from the city-camera direction, cropped round M.CLIP_SHEET['box'] (model metres:
    x0, z0, x1, z1 on the front plane) - gear train / crank check."""
    from PIL import Image
    from mathutils import Vector
    spec = M.CLIP_SHEET
    clip = spec["clip"]
    frames = []
    for t in spec["times"]:
        pv2.pose_from_clip(A, B, clip, t)
        objs = [o for (l_, nm), o in B.objs.items() if l_ == 0]
        use_qa_ao(objs, light, True)
        bl.only(objs)
        e = math.atan(83.0 / (75.0 * math.sqrt(2)))
        d = Vector((0.0, math.cos(e), -math.sin(e)))
        x0, z0, x1, z1 = spec["box"]
        c = Vector(((x0 + x1) / 2, 0.0, (z0 + z1) / 2))
        cd = bpy.data.cameras.get("mat_clip") or bpy.data.cameras.new("mat_clip")
        co = bpy.data.objects.get("mat_clip") or core.link(bpy.data.objects.new("mat_clip", cd))
        cd.type = "ORTHO"
        cd.ortho_scale = max(x1 - x0, z1 - z0)
        cd.clip_start = 0.01
        cd.clip_end = 60
        co.location = c - d * 20
        co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        sc = bpy.context.scene
        sc.camera = co
        sc.render.resolution_x = 420
        sc.render.resolution_y = int(420 * (z1 - z0) / max(x1 - x0, 1e-6))
        rgba = bl.render_rgba()
        use_qa_ao(objs, light, False)
        bg = np.array([0.8, 0.72, 0.55])
        img = (np.clip(rgba[..., :3] * rgba[..., 3:4] + bg * (1 - rgba[..., 3:4]), 0, 1) * 255).astype(np.uint8)
        frames.append(pv2._label(img, f"{clip} t={t:.2f}s"))
    pv2.clear_actions(A, B)
    h = max(f.shape[0] for f in frames)
    frames = [np.concatenate([f, np.full((h - f.shape[0], f.shape[1], 3), 30, np.uint8)], 0) for f in frames]
    Image.fromarray(np.concatenate(sum([[f, np.full((h, 6, 3), 30, np.uint8)] for f in frames], [])[:-1], 1)).save(out_png)


# ============================================================================ run
def run(M, modname, it, do_export=True, do_godot=True):
    import json
    t0 = time.time()
    aid = M.ID
    core.reset()
    qdir = os.environ.get("PV2_QA_DIR")
    if qdir:
        # development iterations: QA sheets to a scratch folder (the repo keeps the shipped iteration's)
        os.makedirs(qdir, exist_ok=True)
        pv2.qa_path = lambda a_, it_, name, ext="png": os.path.join(qdir, f"v2_iter{it_:02d}_{name}.{ext}")
    pv2.PAINT_K = getattr(M, "PAINT_K", pv2.PAINT_K)
    k = pv2.PAINT_K
    pv2.log(f"[{aid}] iter {it} (material path, paintedLightMix {k})")
    views = M.views()
    params = M.solve(views)
    A = pv2.Asset(aid, getattr(M, "ATLAS", 2048))
    for lod in range(3):
        M.build(A, params, lod)
    rng = np.random.default_rng(5)
    for part in A.parts.values():
        for g in part.geo:
            assign_uvs(g, M, rng)
    P3 = M.points(params)
    for v in views:
        Vs, Ts = [], []
        W = A.world_mats(v.pose)
        off = 0
        for nm, p in A.parts.items():
            if W.get(nm) is None:
                continue
            V, F, _, _, _ = p.geo[0].arrays()
            if not len(V):
                continue
            T = np.array(triangulate(F))
            Vw = V @ W[nm][:3, :3].T + W[nm][:3, 3]
            Vs.append(Vw)
            Ts.append(T + off)
            off += len(V)
        pv2.camera_overlay(v, P3, pv2.qa_path(aid, it, f"camera_{v.name}"), (np.concatenate(Vs), np.concatenate(Ts)))
    # ---- painting colour ramps per class, tiles
    v0 = views[0]
    px, pstats, cls_info = measure_ramps(A, v0, k, M)
    from PIL import Image
    sheet = np.asarray(Image.open(os.path.join(pv2.paths.ART, M.SHEET)).convert("RGB"), np.float64) / 255.0
    trng = np.random.default_rng(11)
    tiles = M.make_tiles(px, sheet, trng) if hasattr(M, "make_tiles") else default_tiles(M, px, sheet, trng)
    dbg = os.environ.get("PV2_DEBUG_DIR")
    if dbg:
        os.makedirs(dbg, exist_ok=True)
        np.savez_compressed(os.path.join(dbg, f"{aid}_iter{it}_tiles.npz"), **{c: t.astype(np.float32) for c, t in tiles.items()},
                            **{"px_" + c: np.asarray(v_, np.float32) for c, v_ in px.items()})
    imgs, mats = make_materials(aid, tiles)
    B = pv2.realize(A, {lod: mats for lod in range(3)}, slotmap=lambda m: m)
    smooth_by_angle(B, getattr(M, "SMOOTH_ANGLE", 40.0), tuple(getattr(M, "SHARP_TAGS", ())))
    ao_stats = None
    if hasattr(M, "ao_occluders"):
        ao_stats = bake_vertex_ao(A, B, M)
        pv2.use_qa = use_qa_ao            # QA renders = the game's painted shader incl. the vertex AO
        pv2.EXPORT_VERTEX_COLOR = "ACTIVE"
    else:
        pv2.EXPORT_VERTEX_COLOR = "NONE"
    tris, by_node = {}, {}
    for lod in range(3):
        by_node[f"LOD{lod}"] = {nm: core.tri_count(o) for (l_, nm), o in B.objs.items() if l_ == lod}
        tris[f"LOD{lod}"] = int(sum(by_node[f"LOD{lod}"].values()))
    pv2.log(f"[{aid}] tris {tris}")
    pv2.log(f"[{aid}] LOD0 by node {by_node['LOD0']}")
    bl.setup_render(16)
    # ---- QA + one colour calibration pass
    qa = {}
    gains_log = {}
    for rnd in range(2):
        v = v0
        rgba = pv2.render_view(A, B, v, ss=2)
        ign = v.ignore()
        if rnd == 0:
            skip = set(getattr(M, "NO_CALIBRATE", ())) | {"void", "grass"}
            gains = class_gains(rgba, v, cls_info, [c for c in tiles if c not in skip], ign)
            for c, (gn, n_, pm, rm) in gains.items():
                gains_log[c] = dict(gain=[round(float(x), 3) for x in gn], px=n_,
                                    painting=[round(float(x) * 255) for x in pm], render=[round(float(x) * 255) for x in rm])
                tiles[c] = np.clip(tiles[c] * gn[None, None], 0, 1)
                set_tile(imgs[c], tiles[c])
            pv2.log("  colour calibration gains: " + ", ".join(f"{c} {d['gain']}" for c, d in gains_log.items()))
            for c, amt in getattr(M, "TRIM_AMOUNT", {}).items():
                if c in tiles:
                    tiles[c] = MT.trim(tiles[c], amt)
                    set_tile(imgs[c], tiles[c])
            # the game's FILMIC tonemap desaturates the unshaded painted path: tiles carry a little extra chroma
            ch = float(getattr(M, "TILE_CHROMA", 1.0))
            if ch != 1.0:
                for c in tiles:
                    if c in ("void",):
                        continue
                    lab = tex.to_lab(tiles[c].reshape(-1, 3))
                    lab[:, 1:] *= ch
                    tiles[c] = tex.from_lab(lab).reshape(tiles[c].shape)
                    set_tile(imgs[c], tiles[c])
            continue
        dbg = os.environ.get("PV2_DEBUG_DIR")
        if dbg:
            os.makedirs(dbg, exist_ok=True)
            np.savez_compressed(os.path.join(dbg, f"{aid}_iter{it}_render.npz"), rgba=rgba.astype(np.float32),
                                cls=cls_info[0], classes=np.array(cls_info[1]), nrm=cls_info[2].astype(np.float32))
        m = pv2.compare(v, rgba, pv2.qa_path(aid, it, v.name),
                        f"{aid} v2 iter {it} (material path): {v.title or v.name} | solved camera rms "
                        f"{v.rep['rms_px']:.2f}px (n={v.rep['n']}) | painted light k={k}", ignore=ign)
        m["camera_rms_px"] = round(v.rep["rms_px"], 2)
        m["camera_max_px"] = round(v.rep["max_px"], 2)
        m["camera_points"] = v.rep["n"]
        # diagnostic: IoU against the painted silhouette with the background between the legs kept open
        if hasattr(M, "_open_mask"):
            from scipy import ndimage as ndi
            om = M._open_mask(v)
            rm_ = rgba[..., 3] > 0.5
            use = np.ones(rm_.shape, bool) if ign is None else ~ign
            m["iou_raw_open_mask"] = round(float((om & rm_ & use).sum()) / max(1, float(((om | rm_) & use).sum())), 4)
        qa[v.name] = m
        pv2.log(f"[{aid}] view {v.name}: IoU raw {m['iou_raw']:.3f} filled {m['iou_filled']:.3f} "
                f"(open-mask raw {m.get('iou_raw_open_mask', 0):.3f}) colour {m['colour_err']:.3f} "
                f"(cam rms {v.rep['rms_px']:.2f}px)")
        fullres_sheet(v, rgba, pv2.qa_path(aid, it, "painting_vs_render_fullres"),
                      f"{aid} v2 iter {it} (material path) | painting vs render at 2x | IoU raw {m['iou_raw']:.3f} "
                      f"filled {m['iou_filled']:.3f} colour {m['colour_err']:.3f}")
    if hasattr(M, "CLOSEUPS"):
        render_closeups(A, B, v0, pv2.qa_path(aid, it, "closeups_4x"),
                        f"{aid} v2 iter {it}: close-ups at 4x the painting (painting above, render below)", M.CLOSEUPS)
    # game-camera views (model front toward the city camera, game sun in model space), rest and solved poses
    lg = getattr(M, "GAME_LIGHT", (0.0, -0.45, 0.89))
    game_view(A, B, pv2.qa_path(aid, it, "game_view_rest"), lg, title=f"{aid} iter {it}: city-camera direction, rest")
    if hasattr(M, "solved_pose"):
        game_view(A, B, pv2.qa_path(aid, it, "game_view_solved"), lg, pose=M.solved_pose(params),
                  title=f"{aid} iter {it}: city-camera direction, solved (chest raised, lid open)")
    for lod in (1, 2):
        game_view(A, B, pv2.qa_path(aid, it, f"game_view_lod{lod}"), lg, lod=lod, res=600,
                  title=f"LOD{lod} {tris[f'LOD{lod}']} tris")
    # ---- clips, export
    M.clips(A, B)
    if hasattr(M, "CLIP_SHEET"):
        clip_sheet(A, B, M, pv2.qa_path(aid, it, "clip_frames"), lg)
    pv2.clear_actions(A, B)
    out = {}
    files = {c: f"{aid}_{c}_c.jpg" for c in tiles}
    if do_export:
        glb = os.path.join(pv2.RT, f"{aid}.glb")
        os.makedirs(pv2.TEXM, exist_ok=True)
        for c, fn in files.items():
            pv2.save_jpg(os.path.join(pv2.RT, fn), tiles[c], 92)
            pv2.save_png(os.path.join(pv2.TEXM, fn.replace(".jpg", ".png")), tiles[c])
        pv2.export(A, B, glb, {f"{aid}_{c}_c": fn for c, fn in files.items()})
        # retire the projection-path atlases (no longer referenced)
        for old in (f"{aid}_c.jpg", f"{aid}_n.png", f"{aid}_lod1_c.jpg", f"{aid}_lod2_c.jpg"):
            for ext in ("", ".import"):
                pth = os.path.join(pv2.RT, old + ext)
                if os.path.exists(pth):
                    os.remove(pth)
        nodes, anims = pv2.glb_nodes(glb)
        objs0 = [o for (l_, nm), o in B.objs.items() if l_ == 0]
        allv = np.concatenate([np.asarray([o.matrix_world @ v_.co for v_ in o.data.vertices]) for o in objs0])
        lo, hi = allv.min(0), allv.max(0)
        sizes = {files[c]: [int(tiles[c].shape[1]), int(tiles[c].shape[0])] for c in tiles}
        meta = dict(
            id=aid, generation="props v2 material path: measured blueprint + solved painting camera + modelled geometry "
                              "+ seamless painted-style material tiles (colours measured on the painting)",
            tris=tris, tris_by_node=by_node, budget=getattr(M, "BUDGET", {}), bones=0,
            materials=sorted(m_.name for m_ in mats.values()),
            textures={files[c]: max(sizes[files[c]]) for c in tiles},
            texture_sizes=sizes,
            texture_mode="external JPEG tiles next to the GLB (relative URIs), one per material, shared by LOD0/1/2; "
                         "UVs box-mapped in metres (TEXCOORD_0, repeat); no alpha",
            tile_metres={c: M.TILE_M.get(c) for c in tiles if c in M.TILE_M},
            paintedLightMix=k,
            vertexAO=ao_stats is not None,
            vertexAONote="COLOR_0.a = sqrt((F - 0.42) / 0.58), F = baked ambient occlusion x soft sun shadow (rest pose; "
                         "moving parts by themselves); actor_rig enables the painted shader's use_ao for this asset",
            vertexAOStats=ao_stats,
            paintedLightNote="tiles carry no painted light: shade = albedo * mix(1, lambert, paintedLightMix) "
                             "(actor_rig.apply_look -> ForestKit.painted_material)",
            coordinate_space="glTF (Y up, metres) relative to the GLB root; front (door / main face) faces +Z",
            bounds_m={"min": [round(float(lo[0]), 3), round(float(lo[2]), 3), round(float(-hi[1]), 3)],
                      "max": [round(float(hi[0]), 3), round(float(hi[2]), 3), round(float(-lo[1]), 3)]},
            lod_nodes={f"LOD{l}": sorted(o.name for (l_, nm), o in B.objs.items() if l_ == l) for l in range(3)},
            lod_note="LOD meshes are siblings named *_LOD0/1/2 (actor_rig.set_lod); LOD1/LOD2 are hidden by default "
                     "(KHR_node_visibility) so a plain instance shows LOD0 only.",
            hidden_by_default=sorted(A.hidden),
            clips={k_: {kk: vv for kk, vv in v_.items() if kk != "nodes"} | {"nodes": v_["nodes"]} for k_, v_ in A.clips.items()},
            glb_nodes=nodes, glb_animations=anims,
            blueprint={k_: round(float(v_), 4) for k_, v_ in params.items() if not k_.startswith("_")},
            qa=dict(views=qa, cameras={v.name: dict(rms_px=round(v.rep["rms_px"], 2), max_px=round(v.rep["max_px"], 2),
                                                    n=v.rep["n"], fov_deg=round(v.rep["fov_deg"], 2),
                                                    per_point_px=v.rep["per_point_px"]) for v in views},
                    colour_ramps=pstats, calibration=gains_log,
                    sheets=f"forest_rescue/qa/compare/{aid}/v2_iter{it:02d}_*"),
            build=f"python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/props/v2/build_asset.py {modname} --iter {it}",
        )
        meta.update(M.meta(A, params))
        core.write_json(os.path.join(pv2.RT, f"{aid}.meta.json"), meta)
        out["meta"] = meta
        if do_godot:
            bad, log = pv2.godot_import_check(glb, [os.path.join(pv2.RT, f) for f in files.values()])
            pv2.log(f"[{aid}] Godot import: {len(bad)} error/warning lines")
            for ln in bad[:20]:
                pv2.log("   GODOT> " + ln)
            meta["qa"]["godot_import"] = {"errors_warnings": len(bad), "lines": bad[:20]}
            core.write_json(os.path.join(pv2.RT, f"{aid}.meta.json"), meta)
    core.write_json(pv2.qa_path(aid, it, "metrics", "json"),
                    dict(qa=qa, tris=tris, tris_by_node=by_node, colour_ramps=pstats, calibration=gains_log,
                         blueprint={k_: round(float(v_), 4) for k_, v_ in params.items() if not k_.startswith("_")}))
    for o in bpy.data.objects:
        o.hide_render = False
    core.save_blend(os.path.join(pv2.SRC, f"{aid}.blend"))
    pv2.log(f"[{aid}] done in {time.time() - t0:.0f}s")
    return out
