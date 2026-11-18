"""End-to-end guardian build (bpy).  Usage from a species build script:

    import gpipe, spec_x
    gpipe.main(spec_x)

CLI flags (after the script path): --iter NN (comparison iteration tag), --no-anim, --no-export,
--fast (lower voxel / texture size for shape iterations), --no-godot.
"""
import json
import math
import os
import sys
import time

import bpy
import numpy as np

from frlib import core, render, sdf, texproj, paths
import gbody
import gbuild as gb
import gfur
import grig
import gtex

GROUP = "guardians"


def args():
    a = sys.argv[1:]
    out = {"iter": None, "anim": True, "export": True, "fast": False, "godot": True, "videos": True}
    for i, x in enumerate(a):
        if x == "--iter":
            out["iter"] = a[i + 1]
        elif x == "--no-anim":
            out["anim"] = False
        elif x == "--no-export":
            out["export"] = False
        elif x == "--fast":
            out["fast"] = True
        elif x == "--no-godot":
            out["godot"] = False
        elif x == "--no-videos":
            out["videos"] = False
    return out


class Build:
    pass


def build_model(spec, opt):
    B = Build()
    B.spec = spec
    core.reset()
    B.pans = spec.panels()
    B.sk = sk = spec.skeleton()
    rng = np.random.default_rng(spec.SEED)
    B.parts = parts = spec.body_parts(sk)
    vox = spec.VOXEL * (1.6 if opt["fast"] else 1.0)
    F = gbody.build_field(parts, vox)
    hv, hf = F.mesh()
    gb.log("body field", F.n, "hi mesh", len(hv), len(hf))
    B.hi_v, B.hi_f = hv, hf
    body_hi = gb.obj_from("body_hi", hv, hf)
    body = core.decimate_to(body_hi, spec.BODY_TRIS[0], name="body", copy=True)
    core.smooth_corrective(body, 0.25, 2)
    gb.log("body LOD0", core.tri_count(body))
    B.body_hi = body_hi
    # fur clumps (roots on the hi-res surface)
    gfur.TAPER = getattr(spec, "CLUMP_TAPER", 0.9)
    B.field = F
    B.clumps = spec.fur(sk, hv, hf, B.pans, rng)
    cV, cF, cU, cI = gfur.clumps_to_mesh(B.clumps)
    B.clump_faces = 6 * (len(B.clumps[0].pts) - 2) + 3 if B.clumps else 0
    clump_obj = gb.obj_from("clumps", cV, cF, cU)
    gb.log("clumps", len(B.clumps), "tris", len(cF))
    # details
    if spec.details.__code__.co_argcount >= 4:
        B.details = spec.details(sk, hv, hf, B.pans)
    else:
        B.details = spec.details(sk)
    dV, dF, dU, dI = gbody.merge([d["mesh"] for d in B.details])
    B.detail_face_ids = dI
    det_obj = gb.obj_from("details", dV, dF, dU)
    gb.log("details", len(B.details), "tris", len(dF))
    # UV atlas over body + clumps + details
    gb.uv_atlas(body, [clump_obj, det_obj], [1.0, spec.CLUMP_UV_SCALE, spec.DETAIL_UV_SCALE])
    B.clump_uv = gb.loop_uvs(clump_obj)
    B.detail_uv = gb.loop_uvs(det_obj)
    # LOD bodies from the UV'd body
    B.body_lods = [body]
    for li in (1, 2):
        o = core.decimate_to(body, spec.BODY_TRIS[li], name=f"body_lod{li}", copy=True)
        B.body_lods.append(o)
    # part labels (face attribute) for texture regions
    groups = sorted({c.group for c in B.clumps})
    B.groups = groups
    kinds = sorted({d["kind"] for d in B.details})
    B.kinds = kinds
    B.label_names = {0: "body"}
    for i, g in enumerate(groups):
        B.label_names[100 + i] = "fur_" + g
    for i, k in enumerate(kinds):
        B.label_names[200 + i] = k
    B.clump_label = np.array([100 + groups.index(c.group) for c in B.clumps])
    B.detail_label = np.array([200 + kinds.index(d["kind"]) for d in B.details])
    # armature
    B.arm = grig.build_armature(spec.ID + "_rig", sk)
    B.bone_names = list(sk.names)
    B.sources = spec.weight_sources(sk, parts)
    # assemble LODs
    B.lods = []
    for li in range(3):
        B.lods.append(assemble_lod(B, li))
    for o in (clump_obj, det_obj):
        bpy.data.objects.remove(o, do_unlink=True)
    return B


def clump_lod_mesh(B, li):
    spec = B.spec
    rng = np.random.default_rng(spec.SEED + 17 * li)
    keep = spec.CLUMP_KEEP[li]
    if keep >= 1.0:
        idx = list(range(len(B.clumps)))
    else:
        # keep per group so every fur group survives (longest first)
        idx = []
        for g in B.groups:
            gi = [i for i, c in enumerate(B.clumps) if c.group == g]
            n = max(1, int(round(len(gi) * keep)))
            L = np.array([B.clumps[i].length for i in gi]) * rng.uniform(0.75, 1.25, len(gi))
            idx += [gi[j] for j in np.argsort(-L)[:n]]
        idx = sorted(idx)
    meshes = [gfur.clump_mesh(B.clumps[i], width_scale=spec.CLUMP_WIDTH[li], taper=gfur.TAPER) for i in idx]
    V, F, U, ids = gbody.merge(meshes)
    fpc = B.clump_faces
    uv = np.concatenate([B.clump_uv[i * fpc * 3:(i + 1) * fpc * 3] for i in idx])
    return V, F, uv, np.array(idx)


def assemble_lod(B, li):
    spec = B.spec
    name = f"{spec.ID}_LOD{li}"
    body = B.body_lods[li]
    objs = [body]
    labels = [np.zeros(len(body.data.polygons), int)]
    # clumps
    if B.clumps:
        V, F, U, idx = clump_lod_mesh(B, li)
        co = gb.obj_from(f"clumps_lod{li}", V, F)
        gb.set_loop_uvs(co, U)
        objs.append(co)
        labels.append(np.repeat(B.clump_label[idx], B.clump_faces))
    # details
    keep = [i for i, d in enumerate(B.details) if li in d.get("lods", (0, 1, 2))]
    if keep:
        meshes = [B.details[i]["mesh"] for i in keep]
        V, F, U, ids = gbody.merge(meshes)
        # packed UVs of the kept details
        starts = np.concatenate([[0], np.cumsum([len(d["mesh"][1]) for d in B.details])])
        uv = np.concatenate([B.detail_uv[starts[i] * 3:starts[i + 1] * 3] for i in keep])
        do = gb.obj_from(f"details_lod{li}", V, F)
        gb.set_loop_uvs(do, uv)
        objs.append(do)
        labels.append(np.repeat(B.detail_label[keep], [len(B.details[i]["mesh"][1]) for i in keep]))
        det_bones = [B.details[i]["bone"] for i in keep]
        det_kinds = [B.details[i]["kind"] for i in keep]
        det_nf = [len(B.details[i]["mesh"][1]) for i in keep]
        det_nv = [len(B.details[i]["mesh"][0]) for i in keep]
    # weights + bind per piece, then join
    remap = getattr(spec, "LOD_REMAP", {}).get(li, {})
    for oi, o in enumerate(objs):
        V, _, _ = gb.obj_arrays(o)
        adj = None
        iters = 0
        if oi == 0:
            faces = np.array([p.vertices[:] for p in o.data.polygons], dtype=object)
            tri = np.array([list(f) for f in faces if len(f) == 3])
            adj = sdf.adjacency_matrix(len(V), tri)
            iters = 5
        W = gb.weight_matrix(V, B.sources, B.bone_names, falloff=spec.WEIGHT_FALLOFF if hasattr(spec, "WEIGHT_FALLOFF") else 0.05,
                             adjacency=adj, smooth_iters=iters)
        if o.name.startswith("clumps") and hasattr(spec, "clump_bone_hints"):
            W = spec.clump_bone_hints(B, V, W)
        if o.name.startswith("details"):
            # rigid details
            off = 0
            bi = {b: i for i, b in enumerate(B.bone_names)}
            for b, k, nv in zip(det_bones, det_kinds, det_nv):
                if k in spec.RIGID_KINDS:
                    W[off:off + nv] = 0
                    W[off:off + nv, bi[b]] = 1.0
                off += nv
        if remap:
            W = gb.remap_weights(W, B.bone_names, remap)
        gb.bind_weights(o, B.arm, B.bone_names, W)
        gb.face_attr(o, "part", labels[oi])
    lod = core.join(objs, name=name)
    # drop empty vertex groups
    used = set()
    me = lod.data
    for v in me.vertices:
        for g in v.groups:
            if g.weight > 0:
                used.add(g.group)
    for vg in list(lod.vertex_groups):
        if vg.index not in used:
            pass  # keep the full group list (glTF skin is shared); counted per LOD in meta
    gb.log(name, "tris", core.tri_count(lod))
    return lod


# --------------------------------------------------------------------------- texture

def texture(B, opt):
    spec = B.spec
    size = 1024 if opt["fast"] else 2048
    lod0 = B.lods[0]
    for o in B.lods[1:]:
        o.hide_set(True)
    poses = {"bind": None, "side": spec.side_stance(B.sk)} if hasattr(spec, "side_stance") else {"bind": None}
    B.poses = poses
    vp = []
    for vname, pk in spec.PROJECTION:
        gb.apply_pose(B.arm, B.sk, poses[pk])
        v, t, uv, n = gb.posed_arrays(lod0)
        vp.append((B.pans[vname].view, v, n))
    gb.apply_pose(B.arm, B.sk, None)
    v0, t0, uv0, n0 = gb.posed_arrays(lod0)
    gb.log("projecting", size)
    filt = None
    if hasattr(spec, "projection_filter"):
        filt = lambda vn, Tb: spec.projection_filter(B, vn, Tb)
    col, w, T = gtex.project_posed(vp, t0, uv0, size, bind_verts=v0, bind_normals=n0, filt=filt)
    # labels per texel
    me = lod0.data
    me.calc_loop_triangles()
    pidx = np.empty(len(me.loop_triangles), np.int64)
    me.loop_triangles.foreach_get("polygon_index", pidx)
    plab = np.empty(len(me.polygons), np.int32)
    me.attributes["part"].data.foreach_get("value", plab)
    tri_lab = plab[pidx]
    lab = np.full(T.valid.shape, -1)
    lab[T.valid] = tri_lab[T.tri[T.valid]]
    B.tex_labels = lab
    gb.log("projection done; known fraction", float((w > 0.02)[T.valid].mean()))
    if hasattr(spec, "TIP_LIGHTEN"):
        # hair gets lighter away from the skin (distance sampled from the body SDF)
        stren, dist, lc = spec.TIP_LIGHTEN
        fur_lbl = [k for k, v in B.label_names.items() if v.startswith("fur_") and v not in ("fur_moss",)]
        fm = np.isin(lab, fur_lbl)
        if fm.any():
            dsk = np.clip(B.field.sample(T.pos[fm]), 0, None)
            k = (stren * np.clip(dsk / dist, 0, 1))[:, None]
            col[fm] = col[fm] * (1 - k) + np.asarray(lc) * k
    col = spec.texture_overrides(B, col, T, lab) if hasattr(spec, "texture_overrides") else col
    # normal map: fur strands on body+fur, smooth on hard details
    flow = spec.fur_flow(B, T) if hasattr(spec, "fur_flow") else None
    valid = T.valid
    yy, xx = np.nonzero(valid)
    P = T.pos[yy, xx]
    furry = np.isin(lab[yy, xx], [0] + [100 + i for i in range(len(B.groups))])
    H = np.zeros(valid.shape)
    if hasattr(spec, "height_fn"):
        hgt = spec.height_fn(P, T.nrm[yy, xx])
        plate = np.isin(lab[yy, xx], [k for k, v in B.label_names.items() if v in ("plate", "spike")])
        H[yy, xx] = np.where(furry | plate, hgt, 0.5)
    elif flow is not None:
        D = flow(P, T.nrm[yy, xx])
        h = gtex.strand_height(P, D, scale=getattr(spec, "STRAND_SCALE", 1.0))
        H[yy, xx] = np.where(furry, h, 0.5)
    nrm_map = gtex.tangent_normal_from_height(H, valid, strength=getattr(spec, "NORMAL_STRENGTH", 5.0))
    # roughness / ORM
    rough = np.full(valid.shape, 0.9)
    rmap = getattr(spec, "ROUGHNESS", {})
    for lbl, name in B.label_names.items():
        if name in rmap:
            rough[lab == lbl] = rmap[name]
    if hasattr(spec, "roughness_extra"):
        rough = spec.roughness_extra(B, rough, T, lab)
    rough[valid] = np.clip(rough[valid] + (H[valid] - 0.5) * 0.12, 0.05, 1.0)
    ao = np.ones(valid.shape)
    orm = np.stack([ao, rough, np.zeros_like(rough)], -1)
    col = gtex.dilate_islands(col, valid, 8)
    B.base_col = col
    nrm_map = gtex.dilate_islands(nrm_map, valid, 8)
    orm = gtex.dilate_islands(orm, valid, 8)
    # masters + game textures
    tdir = os.path.join(paths.TEXTURE_SOURCES, GROUP)
    os.makedirs(tdir, exist_ok=True)
    base_m = os.path.join(tdir, f"{spec.ID}_basecolor_master.png")
    core.save_rgba(base_m, col)
    core.save_rgba(os.path.join(tdir, f"{spec.ID}_normal_master.png"), nrm_map)
    core.save_rgba(os.path.join(tdir, f"{spec.ID}_orm_master.png"), orm)
    gsize_n = 1024
    base_p = gb.save_jpg(os.path.join(tdir, f"{spec.ID}_basecolor.jpg"), col if size == 2048 else col, 90)
    nrm_p = os.path.join(tdir, f"{spec.ID}_normal.png")
    core.save_rgba(nrm_p, gb.resize(nrm_map, gsize_n))
    orm_p = os.path.join(tdir, f"{spec.ID}_orm.png")
    core.save_rgba(orm_p, gb.resize(orm, gsize_n))
    img_b = core.load_image(base_p, "sRGB", name=f"{spec.ID}_basecolor")
    img_n = core.load_image(nrm_p, "Non-Color", name=f"{spec.ID}_normal")
    img_o = core.load_image(orm_p, "Non-Color", name=f"{spec.ID}_orm")
    mat = core.material(f"{spec.ID}_mat", base_tex=img_b, rough_tex=img_o, metal_tex=img_o, normal_tex=img_n,
                        normal_strength=1.0)
    for o in B.lods:
        core.assign(o, mat)
    B.material = mat
    B.base_path, B.base_img, B.base_master = base_p, img_b, base_m
    B.textures = {"basecolor": [2048 if size == 2048 else size] * 2, "normal": [gsize_n] * 2, "orm": [gsize_n] * 2}
    for o in B.lods[1:]:
        o.hide_set(False)
    gb.log("texture done")


# --------------------------------------------------------------------------- comparisons

def compare(B, tag, samples=32):
    spec = B.spec
    out = paths.ensure(paths.QA_COMPARE, spec.ID)
    for o in B.lods[1:]:
        o.hide_render = True
    B.body_hi.hide_render = True
    res = {}
    for vname, pk in spec.COMPARE:
        gb.apply_pose(B.arm, B.sk, B.poses.get(pk) if hasattr(B, "poses") else None)
        view = B.pans[vname].view
        rgba = gb.render_view(view, samples=samples)
        m = render.compare(view, rgba, os.path.join(out, f"{tag}_{vname}.png"),
                           title=f"{spec.ID} {tag} {vname} ({pk} pose) LOD0")
        res[vname] = m
        gb.log("compare", vname, m)
    gb.apply_pose(B.arm, B.sk, None)
    for o in B.lods[1:]:
        o.hide_render = False
    core.write_json(os.path.join(out, f"{tag}_metrics.json"), res)
    return res


def calibrate(B, samples=24):
    """Albedo gain so the studio render matches the painted sheet brightness (side view)."""
    spec = B.spec
    for o in B.lods[1:]:
        o.hide_render = True
    B.body_hi.hide_render = True
    vname, pk = spec.COMPARE[0]
    gb.apply_pose(B.arm, B.sk, B.poses.get(pk))
    view = B.pans[vname].view
    rgba = gb.render_view(view, samples=samples)
    both = view.mask & (rgba[..., 3] > 0.5)
    lum = np.array([0.299, 0.587, 0.114])
    g = float(np.median(view.image[both] @ lum) / max(np.median(rgba[..., :3][both] @ lum), 1e-3))
    gain = np.clip(np.array([g, g, g]), 0.85, 1.45)    # luminance only (keeps the painted hue)
    gb.apply_pose(B.arm, B.sk, None)
    col = np.clip(B.base_col * gain, 0, 1)
    B.base_col = col
    core.save_rgba(B.base_master, col)
    gb.save_jpg(B.base_path, col, 90)
    B.base_img.reload()
    B.albedo_gain = gain.round(3).tolist()
    gb.log("albedo gain", B.albedo_gain)
    return gain


def main(spec):
    opt = args()
    B = build_model(spec, opt)
    texture(B, opt)
    calibrate(B)
    if opt["iter"]:
        B.compare_res = compare(B, f"iter{opt['iter']}")
    if opt["anim"]:
        animate(B)
        fix_ground_all(B)
    if opt["export"]:
        import gqa
        level_nodes(B)
        export(B)
        save_source(B)
        if opt["videos"]:
            gqa.clip_videos(B)
        gqa.strip_match(B, f"iter{opt['iter']}_strip" if opt["iter"] else "strip")
        gqa.head_closeups(B, f"iter{opt['iter']}_head" if opt["iter"] else "head")
        if opt["godot"]:
            gqa.godot(B)
            gqa.old_vs_new(B)
            gqa.godot_vs_sheet(B)
        summary = {"compare": getattr(B, "compare_res", None), "strip": getattr(B, "strip", None),
                   "videos": getattr(B, "videos", None), "godot": getattr(B, "godot_log", None),
                   "albedo_gain": getattr(B, "albedo_gain", None), "clips": B.clip_meta,
                   "glb": B.glb_stats, "glb_size_kb": os.path.getsize(B.glb_path) // 1024}
        core.write_json(os.path.join(paths.ensure(paths.QA_COMPARE, spec.ID), "build_summary.json"), summary)
    return B


# --------------------------------------------------------------------------- animation

def write_action(arm, sk, name, poses, loop):
    """Dense quaternion keys for every bone; location keys only where the body translates."""
    from mathutils import Quaternion, Vector
    act = bpy.data.actions.get(name)
    if act is not None:
        bpy.data.actions.remove(act)
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act
    prev = {}
    bases = [sk.basis(p) for p in poses]
    moving = {b for B in bases for b, (loc, q) in B.items() if np.linalg.norm(loc) > 2e-4}
    for f, B in enumerate(bases):
        for bname, (loc, q) in B.items():
            pb = arm.pose.bones[bname]
            qq = Quaternion(tuple(q))
            if bname in prev and prev[bname].dot(qq) < 0:
                qq = -qq
            prev[bname] = qq
            pb.rotation_quaternion = qq
            pb.keyframe_insert("rotation_quaternion", frame=f, group=bname)
            if bname in moving:
                pb.location = Vector(tuple(loc))
                pb.keyframe_insert("location", frame=f, group=bname)
    act.use_frame_range = True
    act.frame_start = 0
    act.frame_end = len(poses) - 1
    act.use_cyclic = bool(loop)
    act["loop"] = bool(loop)
    return act


def foot_slip(sk, poses, C, legs, speed, contact_h=0.004, frames=None, upto=None):
    """Max horizontal drift (cm) of each planted paw ball in a world where the root moves forward at
    `speed`.  Planted = gait stance flag (locomotion) or ball within contact_h of its rest height."""
    out = {}
    dt = 1.0 / 30
    n = len(poses) if upto is None else upto
    for leg, ch in legs.items():
        d = ch[4]
        P = np.array([p[d][:3, 3] for p in poses[:n]])
        world = P.copy()
        world[:, 1] -= speed * dt * np.arange(len(P))       # root travels -Y (forward)
        if frames is not None and "stance" in frames[0]["feet"][leg]:
            planted = np.array([bool(f["feet"][leg]["stance"]) for f in frames[:n]])
        else:
            planted = np.abs(P[:, 2] - C.neutral[leg][2]) < contact_h
        worst = 0.0
        i = 0
        while i < len(P):
            if planted[i]:
                j = i
                while j + 1 < len(P) and planted[j + 1]:
                    j += 1
                seg = world[i:j + 1, :2]
                worst = max(worst, float(np.max(np.linalg.norm(seg - seg[0], axis=1))) if j > i else 0.0)
                i = j + 1
            else:
                i += 1
        out[leg] = round(worst * 100, 2)
    return out


def animate(B):
    import ganim
    import gclips
    spec = B.spec
    sk = B.sk
    C = ganim.Composer(sk, spec.LEGS, spec.PIVOT)
    P = spec.ANIM
    clips = {}
    meta = {}
    fr = gclips.idle(C, P)
    clips["Idle"] = (fr, True)
    fr, m = gclips.locomotion(C, P, "walk")
    clips["Walk"] = (fr, True)
    meta["Walk"] = m
    if "run" in P:
        fr, m = gclips.locomotion(C, P, "run")
        clips["Run"] = (fr, True)
        meta["Run"] = m
    clips["Alert"] = (gclips.alert(C, P), False)
    fr, m = spec.attack(C, P)
    clips["Attack"] = (fr, False)
    meta["Attack"] = m
    clips["Hit"] = (gclips.hit(C, P), False)
    clips["Roar"] = (gclips.roar(C, P), False)
    clips["Death"] = (gclips.death(C, P), False)
    B.clip_frames = {}
    B.clip_meta = {}
    B.clip_desc = clips
    for name, (frames, loop) in clips.items():
        poses = [C.compose(f) for f in frames]
        if name not in ("Walk", "Run", "Death"):
            # planted feet must reach the ground: lower the body where a leg is overstretched
            from scipy import ndimage as ndi
            for it in range(3):
                err = np.zeros(len(frames))
                for i, (f, p) in enumerate(zip(frames, poses)):
                    for leg, ch in spec.LEGS.items():
                        tgt = np.asarray(f["feet"][leg]["pos"], float)
                        if abs(tgt[2] - C.neutral[leg][2]) < 1e-4:
                            err[i] = max(err[i], float(np.linalg.norm(p[ch[4]][:3, 3] - tgt)))
                if err.max() < 0.008:
                    break
                corr = np.maximum(ndi.gaussian_filter1d(ndi.maximum_filter1d(err, 5), 1.2), err) * 1.1
                for f, c in zip(frames, corr):
                    b = list(f.get("body", (0, 0, 0, 0, 0, 0)))
                    b[2] -= float(c)
                    f["body"] = tuple(b)
                poses = [C.compose(f) for f in frames]
        reach = 0.0
        for f, p in zip(frames, poses):
            for leg, ch in spec.LEGS.items():
                tgt = f["feet"][leg]["pos"]
                reach = max(reach, float(np.linalg.norm(p[ch[4]][:3, 3] - tgt)))
        B.clip_frames[name] = poses
        act = write_action(B.arm, sk, name, poses, loop)
        info = {"seconds": round((len(poses) - 1) / 30.0, 4), "loop": loop, "frames": len(poses)}
        info.update(meta.get(name, {}))
        if name in ("Walk", "Run"):
            info["footSlip_cm_max"] = foot_slip(sk, poses, C, spec.LEGS, info["groundSpeed_mps"], frames=frames)
        elif name == "Death":
            info["footSlip_cm_max"] = foot_slip(sk, poses, C, spec.LEGS, 0.0, upto=int(0.3 * len(poses)))
        else:
            info["footSlip_cm_max"] = foot_slip(sk, poses, C, spec.LEGS, 0.0)
        info["ikReachError_cm_max"] = round(reach * 100, 2)
        B.clip_meta[name] = info
        gb.log("clip", name, info)
    B.arm.animation_data.action = None
    gb.apply_pose(B.arm, sk, None)
    B.composer = C


def ground_check(B, clip="Death", frames=None):
    """Lowest LOD0 vertex per sampled frame (m) — death/roar must not sink into the ground."""
    arm = B.arm
    act = bpy.data.actions[clip]
    arm.animation_data.action = act
    n = int(act.frame_range[1])
    res = []
    for f in (frames or range(0, n + 1, max(1, n // 12))):
        bpy.context.scene.frame_set(f)
        v, _, _, _ = core.mesh_arrays(B.lods[0])
        res.append((f, round(float(v[:, 2].min()), 3)))
    arm.animation_data.action = None
    bpy.context.scene.frame_set(0)
    gb.apply_pose(arm, B.sk, None)
    return res


def fix_death(B, iters=2):
    """Re-author Death so the settled body rests on the ground (lowest vertex ~ +1 cm)."""
    import gclips
    C = B.composer
    dz_fix = 0.0
    for it in range(iters):
        g = ground_check(B, "Death")
        low = min(z for f, z in g if f >= int(0.55 * 84))
        gb.log("death ground", it, g[-4:], "low", low)
        if abs(low - 0.01) < 0.015:
            break
        dz_fix += 0.01 - low
        frames = gclips.death(C, B.spec.ANIM, dz_fix=dz_fix)
        poses = [C.compose(f) for f in frames]
        B.clip_frames["Death"] = poses
        write_action(B.arm, B.sk, "Death", poses, False)
        B.arm.animation_data.action = None
    B.death_ground = ground_check(B, "Death")
    B.clip_meta["Death"]["lowestVertex_m_by_frame"] = B.death_ground
    gb.log("death ground final", B.death_ground)


# --------------------------------------------------------------------------- level variants / export

def detail_uv(B, i):
    starts = np.concatenate([[0], np.cumsum([len(d["mesh"][1]) for d in B.details])])
    return B.detail_uv[starts[i] * 3:starts[i + 1] * 3]


def level_nodes(B):
    """Optional per-level geometry (hidden by default via KHR_node_visibility)."""
    spec = B.spec
    out = []
    if not hasattr(spec, "level_geometry"):
        return out
    bi = {b: i for i, b in enumerate(B.bone_names)}
    for lvl, items in spec.level_geometry(B).items():
        meshes, uvs, bones = [], [], []
        for mesh, uv_src_index, bone in items:
            meshes.append(mesh)
            uvs.append(detail_uv(B, uv_src_index))
            bones.append((bone, len(mesh[0])))
        V, F, U, _ = gbody.merge(meshes)
        o = gb.obj_from(f"{spec.ID}_{lvl}", V, F)
        gb.set_loop_uvs(o, np.concatenate(uvs))
        W = np.zeros((len(V), len(B.bone_names)))
        off = 0
        for b, nv in bones:
            W[off:off + nv, bi[b]] = 1.0
            off += nv
        gb.bind_weights(o, B.arm, B.bone_names, W)
        core.assign(o, B.material)
        out.append(o)
        gb.log("level node", o.name, core.tri_count(o))
    B.level_objs = out
    return out


def glb_coords(p):
    """Blender (Z up, -Y forward) -> glTF (Y up, +Z forward)."""
    return [round(float(p[0]), 3), round(float(p[2]), 3), round(float(-p[1]), 3)]


def export(B):
    import gglb
    spec = B.spec
    path = paths.runtime(GROUP, f"{spec.ID}.glb")
    B.arm.animation_data.action = None
    gb.apply_pose(B.arm, B.sk, None)
    objs = [B.arm] + B.lods + getattr(B, "level_objs", [])
    for o in objs:
        o.hide_set(False)
        o.hide_render = False
    core.export_glb(path, objs, extra={"export_animation_mode": "ACTIONS"})
    # LOD1/LOD2 and level nodes hidden by default (KHR_node_visibility, honoured by Godot 4.6): the current
    # game instantiates the scene without LOD logic, so only LOD0 must render unless visibility ranges are set.
    hidden = [o.name for o in getattr(B, "level_objs", [])] + [o.name for o in B.lods[1:]]
    extras = {n: {"loop": m["loop"], "markers": m.get("markers", {}), "seconds": m["seconds"]}
              for n, m in B.clip_meta.items()}
    gglb.postprocess(path, hidden_nodes=hidden, anim_extras=extras,
                     scene_extras={"id": spec.ID, "species": spec.SPECIES, "levels": spec.LEVELS})
    st = gglb.stats(path)
    B.glb_path, B.glb_stats = path, st
    gb.log("export", path, os.path.getsize(path) // 1024, "KB", json.dumps(st)[:600])
    # sidecar meta
    lo, hi = core.bounds([B.lods[0]])
    meshes = st["meshes"]
    meta = {
        "id": spec.ID, "species": spec.SPECIES, "group": GROUP,
        "source": f"forest_rescue/blender/sources/{GROUP}/{spec.ID}.blend",
        "build": f"python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/{GROUP}/build_{spec.ID}.py",
        "tris": {f"LOD{i}": meshes[f"{spec.ID}_LOD{i}"]["tris"] for i in range(3)},
        "bones": len(B.sk.deform),
        "bones_used_by_lod": {f"LOD{i}": meshes[f"{spec.ID}_LOD{i}"]["joints_used"] for i in range(3)},
        "max_influences": max(m["max_influences"] for m in meshes.values()),
        "materials": [B.material.name],
        "textures": {"basecolor": "2048 JPEG (sRGB)", "normal": "1024 PNG (tangent, OpenGL)",
                     "orm": "1024 PNG (G=roughness, B=metal=0)"},
        "albedo_gain_vs_sheet": getattr(B, "albedo_gain", None),
        "bounds_m": {"min": glb_coords(np.array([lo[0], hi[1], lo[2]])), "max": glb_coords(np.array([hi[0], lo[1], hi[2]])),
                     "length_m": round(float(hi[1] - lo[1]), 3), "height_m": round(float(hi[2] - lo[2]), 3),
                     "width_m": round(float(hi[0] - lo[0]), 3)},
        "coordinate_space": "glTF: +Y up, +Z forward (head), metres; root bone at the origin on the ground",
        "clips": B.clip_meta,
        "sockets": {k: glb_coords(v) for k, v in spec.sockets(B.sk).items()} if hasattr(spec, "sockets") else {},
        "levels": spec.LEVELS,
        "lod_nodes": [f"{spec.ID}_LOD{i}" for i in range(3)],
        "lod_usage": "LOD0 visible by default; LOD1/LOD2 are hidden (KHR_node_visibility). Integration: set "
                     "visible=true and GeometryInstance3D.visibility_range_begin/end per LOD (suggested 0-35 m, "
                     "35-80 m, >80 m at strategic zoom).",
        "level_nodes_hidden_by_default": hidden,
        "glb_stats": st,
        "notes": spec.NOTES,
    }
    B.meta = meta
    core.write_json(paths.runtime(GROUP, f"{spec.ID}.meta.json"), meta)
    return path


def save_source(B):
    for o in getattr(B, "level_objs", []):
        o.hide_set(False)
    core.save_blend(paths.source(GROUP, f"{B.spec.ID}.blend"))


def min_z_per_frame(B, clip):
    arm = B.arm
    act = bpy.data.actions[clip]
    arm.animation_data.action = act
    n = int(act.frame_range[1])
    zs = []
    for f in range(n + 1):
        bpy.context.scene.frame_set(f)
        v, _, _, _ = core.mesh_arrays(B.lods[0])
        zs.append(float(v[:, 2].min()))
    arm.animation_data.action = None
    bpy.context.scene.frame_set(0)
    gb.apply_pose(arm, B.sk, None)
    return np.array(zs)


def fix_ground_all(B, tol=0.012):
    """Lift the body (dz) on frames where the evaluated LOD0 mesh sinks below the ground plane
    (claw tips touching z~0 are the reference); smooth so the correction never pops."""
    from scipy import ndimage as ndi
    import gclips
    bind_min = float(gb.posed_arrays(B.lods[0])[0][:, 2].min())
    floor = min(bind_min, 0.0) - tol
    report = {}
    for name, (frames, loop) in B.clip_desc.items():
        if name == "Death":
            frames = gclips.death(B.composer, B.spec.ANIM)
        for it in range(3):
            zs = min_z_per_frame(B, name)
            need = np.maximum(0.0, floor - zs)
            if need.max() < 0.004 or loop:
                break
            need = np.maximum(ndi.gaussian_filter1d(ndi.maximum_filter1d(need, 5), 1.5), need) * 1.05
            for f, c in zip(frames, need):
                b = list(f.get("body", (0, 0, 0, 0, 0, 0)))
                b[2] += float(c)
                f["body"] = tuple(b)
                for leg, ft in f.get("feet", {}).items():      # body-carried feet move with the body
                    w = float(ft.get("body_w", 0.0))
                    if w > 0:
                        ft["pos"] = np.asarray(ft["pos"], float) + np.array([0, 0, c * w])
            poses = [B.composer.compose(f) for f in frames]
            B.clip_frames[name] = poses
            write_action(B.arm, B.sk, name, poses, loop)
            B.arm.animation_data.action = None
        if name == "Death":
            # settled pose must rest on the ground (not float): lower the tail end if it hovers
            zs = min_z_per_frame(B, name)
            hover = zs[-1] - bind_min
            if hover > 0.03:
                k = len(frames)
                for i, f in enumerate(frames):
                    u = gclips.ss((i / (k - 1) - 0.80) / 0.12)
                    c = -float(hover - 0.01) * u
                    b = list(f["body"])
                    b[2] += c
                    f["body"] = tuple(b)
                    for leg, ft in f.get("feet", {}).items():
                        w = float(ft.get("body_w", 0.0))
                        if w > 0:
                            ft["pos"] = np.asarray(ft["pos"], float) + np.array([0, 0, c * w])
                poses = [B.composer.compose(f) for f in frames]
                B.clip_frames[name] = poses
                write_action(B.arm, B.sk, name, poses, loop)
                B.arm.animation_data.action = None
        zs = min_z_per_frame(B, name)
        report[name] = {"min_z_m": round(float(zs.min()), 3), "end_min_z_m": round(float(zs[-1]), 3),
                        "bind_min_z_m": round(bind_min, 3)}
        B.clip_meta[name]["ground"] = report[name]
    gb.log("ground", report)
