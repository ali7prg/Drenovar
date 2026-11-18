"""Build the guide horse «Искра» (lf_horse_origin) from scratch.

    python3 forest_rescue/blender/run_limited.py \
        forest_rescue/blender/assets/horse/build_lf_horse_origin.py [--tex-size 2048] [--fast]

Outputs: sources/horse/lf_horse_origin.blend (HQ mesh, rig, actions, LODs, packed textures),
textures/horse/*.png|jpg (masters), godot/project/assets/forest_rescue/horse/lf_horse_origin.glb
+ .meta.json.  Deterministic (fixed seeds).  Verification: verify_lf_horse_origin.py.
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

import bpy  # noqa: E402
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from frlib import core, paths, sdf, texproj  # noqa: E402
import horse_refs as HR  # noqa: E402
import horse_body as HB  # noqa: E402
import horse_mesh as HM  # noqa: E402
import horse_rig as HRig  # noqa: E402
import horse_hair as HH  # noqa: E402
import horse_tack as HT  # noqa: E402
import horse_tex as HX  # noqa: E402
import horse_anim as HA  # noqa: E402
import horse_clips as HC  # noqa: E402
import horse_hairvol as HV  # noqa: E402

ASSET = "lf_horse_origin"
GROUP = "horse"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
FAST = "--fast" in ARGS
TEX = int(ARGS[ARGS.index("--tex-size") + 1]) if "--tex-size" in ARGS else (1024 if FAST else 2048)
BODY_TRIS = {0: 9000, 1: 6000, 2: 2750}   # LOD1/2: body + opaque hair volumes
HAIR_VOL_TRIS = 2700
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:7.1f}s]", *a, flush=True)


# --------------------------------------------------------------------------- geometry

def build_body(views, J):
    vox = 0.009 if FAST else 0.006
    F = HM.body_field(voxel=vox, views=views, J=J)
    v, f = F.mesh()
    hi = core.mesh_object(f"{ASSET}_HQ", v, f)
    log("HQ mesh", len(f), "tris")
    lo = core.decimate_to(hi, BODY_TRIS[0], name=f"{ASSET}_body0")
    # relax triangle shapes while staying on the HQ surface
    for _ in range(3):
        m = lo.modifiers.new("sm", "SMOOTH")
        m.factor, m.iterations = 0.5, 2
        core.select_only([lo])
        bpy.ops.object.modifier_apply(modifier="sm")
        m = lo.modifiers.new("sw", "SHRINKWRAP")
        m.target = hi
        m.wrap_method = "NEAREST_SURFACEPOINT"
        bpy.ops.object.modifier_apply(modifier="sw")
    lo.data.shade_smooth()
    log("body LOD0", core.tri_count(lo), "tris")
    return F, hi, lo


def build_hair_volumes(guide):
    """Opaque mane + forelock + tail masses (HQ for baking, decimated for the game mesh)."""
    vox = 0.006 if FAST else 0.004
    mane, fore, tail = HV.mane_clumps(guide), HV.forelock_clumps(guide), HV.tail_clumps()
    allc = HV.Clumps()
    for c in (mane, fore, tail):
        allc.prims += c.prims
        allc.segs += c.segs
    head = HV.Clumps()
    head.prims = mane.prims + fore.prims
    head.segs = mane.segs + fore.segs
    vs, fs, off = [], [], 0
    for C, lo, hi in ((head, (-0.27, -1.30, 1.30), (0.27, -0.25, 2.06)),
                      (tail, (-0.22, 0.52, 0.08), (0.22, 1.06, 1.52))):
        Fh = HV.volume_field(C, lo, hi, vox, body_guide=guide)
        v, f = Fh.mesh()
        v, f = HV.drop_hidden(v, f, guide)
        vs.append(v)
        fs.append(f + off)
        off += len(v)
    v = np.concatenate(vs)
    f = np.concatenate(fs)
    hq = core.mesh_object(f"{ASSET}_hair_HQ", v, f)
    log("hair volume HQ", len(f), "tris")
    lo = core.decimate_to(hq, HAIR_VOL_TRIS, name=f"{ASSET}_hairvol0")
    lo.data.shade_smooth()
    log("hair volume LOD0", core.tri_count(lo), "tris")
    return hq, lo, allc


def mesh_from_cards(name, cs, col=None):
    v, f, uv, w = cs.arrays()
    obj = core.mesh_object(name, v, f, uvs=uv, col=col, smooth=True)
    return obj, w


def mesh_from_geo(name, geo):
    v, f, uv, w = geo.arrays()
    obj = core.mesh_object(name, v, f, uvs=uv, smooth=True)
    return obj, w


def assign_groups(obj, weights, drop=None):
    """weights: per-vertex dicts (bone -> w); limited to 4, normalised."""
    obj.vertex_groups.clear()
    groups = {}
    for i, wd in enumerate(weights):
        items = {}
        for b, val in wd.items():
            bb = HRig.resolve(b, drop) if drop else b
            items[bb] = items.get(bb, 0.0) + val
        top = sorted(items.items(), key=lambda kv: -kv[1])[:4]
        s = sum(v for _, v in top) or 1.0
        for b, val in top:
            if val / s < 0.01:
                continue
            g = groups.get(b) or obj.vertex_groups.new(name=b)
            groups[b] = g
            g.add([i], val / s, "REPLACE")


# --------------------------------------------------------------------------- armature

def build_armature(J):
    B = HRig.bones(J)
    arm = bpy.data.armatures.new(f"{ASSET}_rig")
    obj = bpy.data.objects.new(f"{ASSET}_rig", arm)
    core.link(obj)
    arm.display_type = "OCTAHEDRAL"
    core.select_only([obj])
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = {}
    for b in B:
        eb = arm.edit_bones.new(b["name"])
        eb.head = Vector(b["head"])
        eb.tail = Vector(b["tail"])
        eb.align_roll(Vector(HRig.roll_vector(b["head"], b["tail"])))
        eb.use_deform = b["deform"]
        ebs[b["name"]] = eb
    for b in B:
        if b["parent"]:
            ebs[b["name"]].parent = ebs[b["parent"]]
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in obj.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return obj


def skel_from_armature(arm_obj):
    rest, parents, lengths = {}, {}, {}
    for b in arm_obj.data.bones:
        rest[b.name] = np.array(b.matrix_local)
        parents[b.name] = b.parent.name if b.parent else None
        lengths[b.name] = b.length
    return HA.Skel(rest, parents, lengths)


def body_weights(lo, J):
    verts, tris, _, _ = core.mesh_arrays(lo, evaluated=False)
    parts = HB.body_parts(J) + HB.ear_parts(J)
    names = sorted({p.bone for p in parts if p.bone})
    A = sdf.adjacency_matrix(len(verts), tris)
    W = sdf.part_weights(verts, parts, names, falloff=0.028, power=1.0, top=6, adjacency=A,
                         smooth_iters=3, smooth_factor=0.5)
    # keep each side's limb bones off the other side (no cross-leg influence)
    for j, n in enumerate(names):
        if n.endswith("_L"):
            W[verts[:, 0] < -0.02, j] = 0.0
        elif n.endswith("_R"):
            W[verts[:, 0] > 0.02, j] = 0.0
    W = sdf.limit_weights(W, top=4, min_w=0.02)
    return names, W


def bind_weights(obj, arm, names, W):
    obj.vertex_groups.clear()
    for j, n in enumerate(names):
        idx = np.nonzero(W[:, j] > 0)[0]
        if len(idx) == 0:
            continue
        g = obj.vertex_groups.new(name=n)
        vals = np.round(W[idx, j], 4)
        order = np.argsort(vals)
        idx, vals = idx[order], vals[order]
        splits = np.nonzero(np.diff(vals))[0] + 1
        for ii, vv in zip(np.split(idx, splits), np.split(vals, splits)):
            g.add(ii.tolist(), float(vv[0]), "REPLACE")


def parent_to_armature(obj, arm):
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    obj.parent = arm
    obj.matrix_parent_inverse = arm.matrix_world.inverted()


def remap_groups(obj, drop):
    """Merge vertex groups of dropped bones into their LOD targets (max 4, normalised)."""
    me = obj.data
    gnames = {g.index: g.name for g in obj.vertex_groups}
    data = []
    for v in me.vertices:
        d = {}
        for ge in v.groups:
            b = HRig.resolve(gnames[ge.group], drop)
            d[b] = d.get(b, 0.0) + ge.weight
        data.append(d)
    assign_groups(obj, data)


# --------------------------------------------------------------------------- materials

def tex_path(name):
    return paths.texture_master(GROUP, f"{ASSET}_{name}")


def alpha_clip_material(name, img, rough=0.55):
    mat = core.material(name, base_tex=img, rough=rough, alpha_clip=0.5, double_sided=True)
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = next(n for n in nt.nodes if n.type == "TEX_IMAGE")
    for l in list(bsdf.inputs["Alpha"].links):
        nt.links.remove(l)
    gt = nt.nodes.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = 0.5
    nt.links.new(tex.outputs["Alpha"], gt.inputs[0])
    nt.links.new(gt.outputs[0], bsdf.inputs["Alpha"])
    mat.surface_render_method = "DITHERED"
    try:
        mat.blend_method = "CLIP"
    except Exception:
        pass
    return mat


# --------------------------------------------------------------------------- textures

def body_textures(lo, hi, views, J, tack_objs, clumps):
    from PIL import Image
    verts, tris, uv, vn = core.mesh_arrays(lo, evaluated=False)
    T = texproj.rasterize_uv(verts, tris, uv, TEX, vn)
    # opaque hair-volume texels (face attribute) + strand flow from the clump segments
    me = lo.data
    me.calc_loop_triangles()
    poly = np.empty(len(me.loop_triangles), np.int64)
    me.loop_triangles.foreach_get("polygon_index", poly)
    fflag = np.empty(len(me.polygons), np.int32)
    me.attributes["hair_volume"].data.foreach_get("value", fflag)
    tri_hair = fflag[poly].astype(bool)
    hair_mask = T.valid & tri_hair[np.clip(T.tri, 0, None)]
    hair_flow = np.zeros(T.pos.shape)
    hy, hx = np.nonzero(hair_mask)
    hair_flow[hy, hx] = HV.flow_dirs(clumps, T.pos[hy, hx])
    pal = HX.sheet_palette(views)
    # sheet hair is painted with light baked in: albedo slightly darker than the painted median
    hair_pal = (pal["mane"][0] * 0.80, pal["mane"][1] * 1.0, pal["tail"][2] * 1.05)
    hoof_col = 0.5 * (pal["hoof"][0] + pal["hoof"][1]) * 0.92
    log("sheet palette mane", np.round(pal["mane"][1], 3), "tail", np.round(pal["tail"][1], 3),
        "hoof", np.round(hoof_col, 3), "hair texels", int(hair_mask.sum()))
    tv, tt = [], []
    off = 0
    for o in tack_objs:
        v2, t2, _, _ = core.mesh_arrays(o, evaluated=False)
        tv.append(v2)
        tt.append(t2 + off)
        off += len(v2)
    tv = np.concatenate(tv)
    tt = np.concatenate(tt)
    excl = HX.exclusion_masks(views, tv, tt)
    col, w = HX.project_body(T, verts, tris, list_views(views), excl)
    log("projection coverage", float((w > 0).sum() / max(T.valid.sum(), 1)))
    col = texproj.fill(col, w > 1e-6)
    col, gain, ref_med, tex_med = HX.match_coat(T, col, views, excl)
    log("coat gain", np.round(gain, 3), "sheet coat", np.round(ref_med, 3), "texture", np.round(tex_med, 3))
    col, rough, height = HX.details(T, col, J, hair_mask=hair_mask, hair_flow=hair_flow,
                                    hair_pal=hair_pal, hoof_col=hoof_col)
    col = texproj.dilate_margin(col, T.valid, 8)
    core.save_rgba(tex_path("body_color_master.png"), col)
    Image.fromarray((np.clip(col, 0, 1) * 255 + 0.5).astype(np.uint8)).save(
        tex_path("body_color.jpg"), quality=90)
    # AO + baked normals from the HQ sculpt
    img_n = core.new_image(f"{ASSET}_body_normal_bake", TEX, colorspace="Non-Color")
    img_ao = core.new_image(f"{ASSET}_body_ao_bake", TEX // 2, colorspace="Non-Color")
    tmp = core.material("bake_tmp", base=(0.5, 0.5, 0.5, 1))
    core.assign(lo, tmp)
    core.bake(lo, "NORMAL", img_n, margin=16, samples=1, selected_to_active=hi,
              cage_extrusion=0.03, max_ray_distance=0.08)
    core.bake(lo, "AO", img_ao, margin=16, samples=16 if not FAST else 6)
    nrm = core.image_to_numpy(img_n)[..., :3]
    ao = core.image_to_numpy(img_ao)[..., 0]
    ao = np.asarray(Image.fromarray((np.clip(ao, 0, 1) * 255).astype(np.uint8)).resize((TEX, TEX)),
                    float) / 255.0
    # fine hair-flow detail on top of the baked normal (UDN blend)
    det = texproj.height_to_normal(height, T.valid, strength=1.2)
    n1 = nrm * 2 - 1
    n2 = det * 2 - 1
    n = np.stack([n1[..., 0] + n2[..., 0], n1[..., 1] + n2[..., 1], n1[..., 2]], -1)
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
    nrm = texproj.dilate_margin(n * 0.5 + 0.5, T.valid, 8)
    core.save_rgba(tex_path("body_normal.png"), nrm)
    ao = np.clip(0.35 + 0.65 * ao, 0, 1)
    orm = np.stack([ao, np.clip(rough, 0.04, 1), np.zeros_like(ao)], -1)
    orm = texproj.dilate_margin(orm, T.valid, 8)
    small = np.asarray(Image.fromarray((orm * 255 + 0.5).astype(np.uint8)).resize(
        (TEX // 2, TEX // 2), Image.LANCZOS))
    Image.fromarray(small).save(tex_path("body_orm.png"))
    # bake AO lightly into albedo (mobile: no SSAO guarantee)
    col2 = col * (0.85 + 0.15 * ao[..., None])
    Image.fromarray((np.clip(col2, 0, 1) * 255 + 0.5).astype(np.uint8)).save(
        tex_path("body_color.jpg"), quality=90)
    bpy.data.materials.remove(tmp)
    for im in (img_n, img_ao):
        bpy.data.images.remove(im)
    return tex_path("body_color.jpg"), tex_path("body_normal.png"), tex_path("body_orm.png")


def list_views(views):
    return {k: views[k] for k in ("left", "right", "front", "rear")}


def hair_tack_textures():
    from PIL import Image
    atlas = HH.hair_atlas(1024 if not FAST else 512)
    core.save_rgba(tex_path("hair.png"), atlas)
    col, orm, hgt = HT.tack_atlas(1024 if not FAST else 512)
    Image.fromarray((col * 255 + 0.5).astype(np.uint8)).save(tex_path("tack_color.jpg"), quality=92)
    nrm = texproj.height_to_normal(hgt, np.ones(hgt.shape, bool), strength=2.0)
    core.save_rgba(tex_path("tack_normal.png"), nrm)
    core.save_rgba(tex_path("tack_orm.png"), orm)
    return tex_path("hair.png"), tex_path("tack_color.jpg"), tex_path("tack_normal.png"), \
        tex_path("tack_orm.png")


# --------------------------------------------------------------------------- animation

def write_clip(arm, clip, frames_basis):
    name = clip["name"]
    act = bpy.data.actions.get(name)
    if act:
        bpy.data.actions.remove(act)
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act
    times = clip["times"]
    keyed_loc = {"spine_02"}
    max_free_loc = 0.0
    for t, fr in zip(times, frames_basis):
        f = float(t * HA.FPS)
        for bname, (loc, q, sc) in fr.items():
            pb = arm.pose.bones.get(bname)
            if pb is None:
                continue
            pb.rotation_quaternion = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
            pb.keyframe_insert("rotation_quaternion", frame=f, group=bname)
            if bname in keyed_loc:
                pb.location = tuple(map(float, loc))
                pb.keyframe_insert("location", frame=f, group=bname)
            else:
                max_free_loc = max(max_free_loc, float(np.abs(loc).max()))
            if bname == "belly":
                pb.scale = tuple(map(float, sc))
                pb.keyframe_insert("scale", frame=f, group=bname)
    _linear_keys(act, arm)
    act.use_frame_range = True
    act.frame_start = 0.0
    act.frame_end = float(times[-1] * HA.FPS)
    act.use_cyclic = bool(clip["loop"])
    act["loop"] = bool(clip["loop"])
    act["seconds"] = float(clip["T"])
    log(f"clip {name}: {len(times)} keys, {clip['T']} s, unkeyed-loc max {max_free_loc:.2e}")
    return act


def _linear_keys(act, arm):
    """Dense keys -> LINEAR interpolation (glTF LINEAR samplers, no cubic overshoot)."""
    fcs = []
    try:
        from bpy_extras import anim_utils
        cbag = anim_utils.action_get_channelbag_for_slot(act, arm.animation_data.action_slot)
        fcs = list(cbag.fcurves) if cbag else []
    except Exception:
        fcs = list(getattr(act, "fcurves", []))
    for fc in fcs:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    return len(fcs)


def hoof_slip(clip, cb, frames_basis):
    """Max horizontal travel (m) of each planted toe (actual solved hoof) in world space."""
    res = {}
    for leg in HC.LEGS:
        segs = []
        cur = []
        for k, pose in enumerate(clip["frames"]):
            prm = pose.ik.get(leg)
            if prm is None:
                continue
            rp, yaw = clip["root"][k]
            toe = cb.toe_track[k].get(leg, prm["toe"])
            w = HA.rotz(yaw) @ toe + np.array([rp[0], rp[1], 0.0])
            planted = prm["toe"][2] < 0.002 and prm.get("pitch", 0) < 0.02
            if planted:
                cur.append(w[:2])
            elif cur:
                segs.append(cur)
                cur = []
        if cur:
            segs.append(cur)
        slip = 0.0
        for s in segs:
            s = np.array(s)
            slip = max(slip, float(np.linalg.norm(s - s[0], axis=1).max()))
        res[leg] = round(slip, 4)
    return res


# --------------------------------------------------------------------------- main

def main():
    core.reset(fps=30)
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    views = HR.load_views()
    J = HB.skeleton()
    hq_col = core.collection("HQ_sculpt")
    F, hi, lo_body = build_body(views, J)
    guide = HH.SurfaceGuide(F)
    hair_hq, hair_lo, clumps = build_hair_volumes(guide)

    # ---- rig + weights (body from part SDFs, hair volumes from their clumps)
    arm = build_armature(J)
    names, W = body_weights(lo_body, J)
    bind_weights(lo_body, arm, names, W)
    hv = np.array([v.co[:] for v in hair_lo.data.vertices])
    assign_groups(hair_lo, HV.volume_weights(clumps, hv, HH._neck_bone_at, HH._mane_bone_at,
                                             HH._tail_weights, HH._blend))
    log("body weights", len(names), "bones")
    n_body_faces = len(lo_body.data.polygons)
    lo0 = core.join([lo_body, hair_lo], name=f"{ASSET}_body0")
    flag = lo0.data.attributes.new("hair_volume", "INT", "FACE")
    flag.data.foreach_set("value", (np.arange(len(lo0.data.polygons)) >= n_body_faces).astype(np.int32))
    core.smart_uv(lo0, angle=62.0, margin=0.004)
    core.pack_uv(lo0, margin=0.004)
    hi = core.join([hi, hair_hq], name=f"{ASSET}_HQ")
    for c in list(hi.users_collection):
        c.objects.unlink(hi)
    hq_col.objects.link(hi)

    # ---- hair / tack per LOD
    parts = {}
    for lod in (0, 1, 2):
        drop = {0: None, 1: HRig.LOD1_DROP, 2: HRig.LOD2_DROP}[lod]
        sets = [("mane", HH.mane_lock_cards(guide, lod) if lod < 2 else HH.CardSet()), ("forelock", HH.forelock_fringe_cards(guide, lod)),
                ("tail", HH.tail_fringe_cards(lod)), ("feather", HH.feather_cards(J, lod))]
        hair_objs = []
        for nm, cs in sets:
            if cs.tris == 0:
                continue
            o, w = mesh_from_cards(f"{ASSET}_{nm}{lod}", cs)
            assign_groups(o, w, drop)
            hair_objs.append(o)
        tack = []
        for nm, geo in (("halter", HT.halter(guide, lod)), ("ribbon", HT.ribbon(lod))):
            o, w = mesh_from_geo(f"{ASSET}_{nm}{lod}", geo)
            assign_groups(o, w, drop)
            tack.append(o)
        parts[lod] = (hair_objs, tack)
        log(f"LOD{lod} hair tris", sum(core.tri_count(o) for o in hair_objs),
            "tack tris", sum(core.tri_count(o) for o in tack))

    # ---- textures
    hair_png, tack_col, tack_nrm, tack_orm = hair_tack_textures()
    body_col, body_nrm, body_orm = body_textures(lo0, hi, views, J, parts[0][1], clumps)
    m_body = core.material(f"{ASSET}_body", base_tex=core.load_image(body_col),
                           normal_tex=core.load_image(body_nrm, "Non-Color"),
                           rough_tex=(orm := core.load_image(body_orm, "Non-Color")), metal_tex=orm)
    bsdf = next(n for n in m_body.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Specular IOR Level"].default_value = 0.20
    m_hair = alpha_clip_material(f"{ASSET}_hair", core.load_image(hair_png))
    m_tack = core.material(f"{ASSET}_tack", base_tex=core.load_image(tack_col),
                           normal_tex=core.load_image(tack_nrm, "Non-Color"),
                           rough_tex=(torm := core.load_image(tack_orm, "Non-Color")),
                           metal_tex=torm, double_sided=True)
    log("textures done")

    # ---- LOD meshes: body LOD1/2 by decimation (UVs + groups preserved), join with hair/tack
    lods = {}
    body_lods = {0: lo0}
    for lod in (1, 2):
        b = core.decimate_to(lo0, BODY_TRIS[lod], name=f"{ASSET}_body{lod}")
        b.modifiers.clear()
        remap_groups(b, {1: HRig.LOD1_DROP, 2: HRig.LOD2_DROP}[lod])
        body_lods[lod] = b
    for lod in (0, 1, 2):
        b = body_lods[lod]
        core.assign(b, m_body)
        for o in parts[lod][0]:
            core.assign(o, m_hair)
        for o in parts[lod][1]:
            core.assign(o, m_tack)
        objs = [b] + parts[lod][0] + parts[lod][1]
        for o in objs:
            o.modifiers.clear()
        j = core.join(objs, name=f"{ASSET}_LOD{lod}")
        parent_to_armature(j, arm)
        lods[lod] = j
        log(f"LOD{lod}", core.tri_count(j), "tris", len(j.vertex_groups), "groups")

    # ---- clips
    skel = skel_from_armature(arm)
    cb = HA.ClipBuilder(skel, J)
    clips = HC.all_clips(cb)
    meta_clips = {}
    for clip in clips:
        HA.OVERREACH[0] = 0.0
        fb = cb.evaluate(clip["frames"])
        log(f"  {clip['name']} IK over-reach max {HA.OVERREACH[0]*100:.1f} cm")
        write_clip(arm, clip, fb)
        m = dict(clip["meta"])
        m["hoofSlip_m"] = hoof_slip(clip, cb, fb)
        if clip["loop"]:
            a0, a1 = fb[0], fb[-1]
            m["loopSeamMaxQuatDiff"] = float(max(min(np.abs(a0[n][1] - a1[n][1]).max(),
                                                     np.abs(a0[n][1] + a1[n][1]).max()) for n in a0))
            log(f"  {clip['name']} loop seam max quat diff {m['loopSeamMaxQuatDiff']:.1e}")
        m["ikOverreach_m"] = round(max(HA.OVERREACH[0], 0.0), 4)
        meta_clips[clip["name"]] = m
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)

    # ---- export
    out_glb = paths.runtime(GROUP, f"{ASSET}.glb")
    core.export_glb(out_glb, [arm, lods[0], lods[1], lods[2]],
                    extra=dict(export_force_sampling=False, export_optimize_animation_size=False,
                               export_image_format="AUTO", export_tangents=True))
    log("GLB", out_glb, os.path.getsize(out_glb) // 1024, "KB")
    mins, maxs = core.bounds([lods[0]])
    deform = HRig.deform_names(J)

    def lod_used(obj):
        used = set()
        idx = {g.index: g.name for g in obj.vertex_groups}
        for v in obj.data.vertices:
            for ge in v.groups:
                if ge.weight > 0:
                    used.add(idx[ge.group])
        return sorted(used)

    meta = {
        "id": ASSET,
        "tris": {f"LOD{k}": core.tri_count(o) for k, o in lods.items()},
        "bones": {"deform": len(deform), "total": len(arm.data.bones),
                  "weightedByLOD": {f"LOD{k}": len(lod_used(o)) for k, o in lods.items()},
                  "maxInfluences": 4},
        "materials": [m_body.name, m_hair.name, m_tack.name],
        "hairMaterial": {"name": m_hair.name, "alphaMode": "MASK", "alphaCutoff": 0.5,
                         "doubleSided": True,
                         "note": "fringe cards only (mane/tail wisps, forelock, feathering); the "
                                 "mane/tail/forelock MASS is opaque geometry in " + m_body.name +
                                 ". Atlas colour is dilated into transparent texels."},
        "textures": {os.path.basename(p): list(bpy.data.images.load(p, check_existing=True).size)
                     for p in (body_col, body_nrm, body_orm, hair_png, tack_col, tack_nrm, tack_orm)},
        "bounds_m": {"min": [round(float(x), 3) for x in mins], "max": [round(float(x), 3) for x in maxs]},
        "clips": meta_clips,
        "sockets": {"ribbon_ring": [round(float(x), 3) for x in HRig.throat_ring()],
                    "lead_ring_chin": [0.0, -1.30, 1.452], "head_look": [0.0, -1.30, 1.75],
                    "withers": [0.0, -0.40, 1.58]},
        "notes": ("Bay cob mare, dark points/mane/tail, white star, worn leather halter with brass "
                  "rings and knotted green ribbon; no saddle/rider. Locomotion clips are in place: "
                  "drive the root at groundSpeed_mps. Turn clips assume the game yaws the root by "
                  "rootYawDeg with the documented curve. Forward = -Y (Blender) = +Z (glTF)."),
        "coordinateConvention": {"up": "+Y", "forward": "+Z", "unit": "metre"},
    }
    core.write_json(paths.runtime(GROUP, f"{ASSET}.meta.json"), meta)
    log("meta", json.dumps(meta["tris"]), json.dumps(meta["bones"]))
    blend = paths.source(GROUP, f"{ASSET}.blend")
    core.save_blend(blend)
    log("saved", blend)


if __name__ == "__main__":
    main()
