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
    B.clumps = spec.fur(sk, hv, hf, B.pans, rng)
    cV, cF, cU, cI = gfur.clumps_to_mesh(B.clumps)
    B.clump_faces = 6 * (len(B.clumps[0].pts) - 2) + 3 if B.clumps else 0
    clump_obj = gb.obj_from("clumps", cV, cF, cU)
    gb.log("clumps", len(B.clumps), "tris", len(cF))
    # details
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
    meshes = [gfur.clump_mesh(B.clumps[i], width_scale=spec.CLUMP_WIDTH[li]) for i in idx]
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
    col, w, T = gtex.project_posed(vp, t0, uv0, size, bind_verts=v0, bind_normals=n0)
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
    col = spec.texture_overrides(B, col, T, lab) if hasattr(spec, "texture_overrides") else col
    # normal map: fur strands on body+fur, smooth on hard details
    flow = spec.fur_flow(B, T) if hasattr(spec, "fur_flow") else None
    valid = T.valid
    yy, xx = np.nonzero(valid)
    P = T.pos[yy, xx]
    furry = np.isin(lab[yy, xx], [0] + [100 + i for i in range(len(B.groups))])
    H = np.zeros(valid.shape)
    if flow is not None:
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


def main(spec):
    opt = args()
    B = build_model(spec, opt)
    texture(B, opt)
    if opt["iter"]:
        compare(B, f"iter{opt['iter']}")
    return B
