"""Generic build + QA pipeline for the four artifact mechanisms (node animations, projection, meta)."""
import math
import os

import bpy
import numpy as np

import propkit as pk
import propproj as pp
import propqa as qa
import propshaders as sh
from frlib import core, paths

IMG = "10_artifact_mechanisms.png"


def shaders():
    S = dict(sh.SHADERS)
    S["limestone_fine"] = lambda c: sh.limestone(c, base=sh.C(150, 136, 118), light=sh.C(190, 178, 160), dark=sh.C(100, 88, 76))
    return S


def apply_pose(A, pose):
    pk.set_static_pose(A, pose or {})


def run(asset_id, spec, build_fn, views, clips_fn, meta_fn, markers=(), tex_size=2048, height_gain=0.03,
        relief_levels=2, ao_distance=0.3, notes="", main_view=None):
    """views: list of dict(name, box, objects: 'all'|'static'|[node...], pose: {node: dict}, x0: [...], exclude: [(x0,y0,x1,y1)],
    project: bool, compare: bool)."""
    it = qa.iteration()
    pre = f"iter{it:02d}_"
    core.reset()
    A = pk.Asset(asset_id, spec)
    A.dirt_scale = 1.0
    A.compile(build_fn)
    if qa.flag("--geom"):     # quick geometry / clip / export check without textures or QA
        clips_fn(A)
        glb = paths.runtime(pk.GROUP, f"{asset_id}.glb") if not qa.flag("--scratch") else os.path.join(paths.ensure(paths.QA_COMPARE, asset_id), "_geom.glb")
        pk.export(A, glb)
        st = pk.tri_stats(A)
        print("[geom]", asset_id, {k: v["total"] for k, v in st.items()}, st["LOD0"]["by_node"], list(A.clips))
        return A, None, None
    pk.pack_atlas(A.lod0_objects(), margin=0.002)
    pk.transfer_atlas_uv(A)
    for name, pos, node in markers:
        pk.marker(A, name, pos, node)
    cams_path = os.path.join(paths.ensure(paths.QA_COMPARE, "props_cams"), "mech_cams.json")
    cams = qa.load_cams(cams_path)
    fits = {}

    def objs_for(sel):
        if sel == "all":
            return A.lod0_objects()
        if sel == "static":
            return [A.meshes[0]["root"]]
        return [A.meshes[0][n] for n in sel if n in A.meshes[0]]
    for v in views:
        img, m = qa.crop_and_mask(IMG, v["box"], tol=v.get("tol", 3))
        for (x0, y0, x1, y1) in v.get("exclude", []):
            m[y0:y1, x0:x1] = False
        apply_pose(A, v.get("pose"))
        objs = objs_for(v.get("fit_objects", v.get("objects", "all")))
        tris = pk.world_triangles(objs)
        c = tris.reshape(-1, 3).mean(0)
        key = f"{asset_id}:{v['name']}"
        if key in cams and not qa.flag("--refit"):
            x, sc = pk.fit_camera(tris, m, np.array(cams[key]), fixed=(2,), iters=1)
        else:
            x, sc = pk.fit_camera(tris, m, np.array(list(v["x0"]) + list(c)), fixed=(2,), iters=2)
        cams[key] = [float(a) for a in x]
        H, W = m.shape
        fits[v["name"]] = (img, m, pk.cam_from_params(x, W, H), sc)
        print(f"[mech] {asset_id} {v['name']} fit IoU(filled) {sc:.3f}")
        apply_pose(A, {})
    qa.save_cams(cams_path, cams)
    specs = []
    for v in views:
        if not v.get("project", True):
            continue
        img, m, cam, _ = fits[v["name"]]
        pose = v.get("pose")
        specs.append(pp.ViewSpec(v["name"], img, m, objs_for(v.get("objects", "all")), "persp", cam=cam,
                                 pose=(lambda p=pose: apply_pose(A, p)), unpose=(lambda: apply_pose(A, {})),
                                 weight=v.get("weight", 1.0), erode=v.get("erode", 1), delight=0.3, min_facing=0.12,
                                 depth_eps=v.get("depth_eps", 0.03)))
    files, info = pp.paint_relief_textures(A, shaders(), specs, size=tex_size, height_gain=height_gain,
                                           sizes={"base": 2048, "orm": 1024, "normal": 2048},
                                           relief_levels=relief_levels, ao_distance=ao_distance, ao_strength=0.6,
                                           edge_fade_m=0.008, samples=8, paint_alpha_w=0.3,
                                           no_relief_cls=("amber", "gem_green"), gate=2.4)
    pk.make_material(A, files)
    clips_fn(A)
    glb = paths.runtime(pk.GROUP, f"{asset_id}.glb")
    pk.export(A, glb)
    st = pk.tri_stats(A)
    summ = pk.glb_summary(glb)
    mn, mx = core.bounds(A.lod0_objects())
    meta = {
        "id": asset_id,
        "tris": {f"LOD{l}": st[f"LOD{l}"]["total"] for l in (0, 1, 2)},
        "tris_by_node": {f"LOD{l}": st[f"LOD{l}"]["by_node"] for l in (0, 1, 2)},
        "budget": "mechanism LOD0 <= 6000 tris",
        "bones": 0, "materials": [f"{asset_id}_mat"],
        "textures": {"baseColor": "2048 JPEG", "metallicRoughness": "1024 JPEG (G rough, B metal)", "normal": "2048 PNG"},
        "coordinate_space": "glTF (Y up, metres); operator/front side faces +Z",
        "bounds_m": {"min": pk.b2g(mn), "max": pk.b2g(mx)},
        "clips": {c: {"seconds": round(v["frames"] / 30.0, 4), "frames": v["frames"], "loop": False, "markers": v["markers"],
                      "glb_seconds": summ["animations"].get(c, {}).get("seconds")} for c, v in A.clips.items()},
        "glb_nodes": summ["nodes"],
        "glb_animations": {k: v["channels"] for k, v in summ["animations"].items()},
        "markers": {n: {"position": pk.b2g(p), "parent": nd} for n, p, nd in markers},
        "projection": info, "camera_fit_iou": {k: round(v[3], 4) for k, v in fits.items()},
        "notes": notes,
    }
    meta.update(meta_fn(A))
    core.write_json(paths.runtime(pk.GROUP, f"{asset_id}.meta.json"), meta)
    print("[mech] tris", meta["tris"])
    core.save_blend(paths.source(pk.GROUP, f"{asset_id}.blend"))
    if qa.flag("--noqa"):
        return A, meta, fits
    pk.studio(engine="CYCLES", samples=40, key=3.6, fill=1.2, rim=1.2, ambient=0.9, bg=(0.58, 0.51, 0.47))
    for o in A.all_meshes():
        o.hide_render = True
    for o in A.lod0_objects():
        o.hide_render = False
    res = {}
    ground = None
    if any(v.get("holdout_ground") for v in views):
        bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0.0))
        ground = bpy.context.active_object
        gm = bpy.data.materials.new("__holdout")
        gm.use_nodes = True
        nt = gm.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        ho = nt.nodes.new("ShaderNodeHoldout")
        nt.links.new(ho.outputs[0], out.inputs["Surface"])
        ground.data.materials.append(gm)
        ground.hide_render = True
    for v in views:
        if not v.get("compare", True):
            continue
        img, m, cam, _ = fits[v["name"]]
        if ground is not None:
            ground.hide_render = not v.get("holdout_ground", False)
        apply_pose(A, v.get("pose"))
        pk.blender_camera(cam)
        rgba = pk.render_rgba(qa.out(asset_id, "_tmp.png"))
        import cageqa as _cq
        _cq.wire_overlay(A, cam, img, qa.out(asset_id, pre + f"{v['name']}_wire.png"))
        res[v["name"]] = pk.compare_panels(img, rgba, m, qa.out(asset_id, pre + f"{v['name']}.png"),
                                           f"{asset_id} {v['name']} (camera fitted to the drawing)")
        apply_pose(A, {})
    core.write_json(qa.out(asset_id, pre + "metrics.json"),
                    {k: {kk: r.get(kk) for kk in ("iou_filled", "iou_raw", "mean_abs_colour_error", "mean_rgb_ref",
                                                  "mean_rgb_render")} for k, r in res.items()})
    print("[mech-qa]", asset_id, {k: (r.get("iou_filled"), r.get("iou_raw"), r.get("mean_abs_colour_error")) for k, r in res.items()})
    if not qa.flag("--noclips"):
        if ground is not None:
            ground.hide_render = False
        mv = main_view or views[0]["name"]
        cam = dict(fits[mv][2])
        pk.blender_camera(cam)
        for clip in A.clips:
            if clip.startswith("lf_rune_ring") and clip not in ("lf_rune_ring1_mountain", "lf_rune_ring2_river",
                                                               "lf_rune_ring3_leaf"):
                continue
            out = paths.video(asset_id, f"{clip}.mp4")
            pk.render_clip_frames(A, clip, out, res=(min(1280, cam["W"] * 2), min(960, cam["H"] * 2)),
                                  engine="BLENDER_EEVEE", samples=12, hold=8)
            print("[clip]", out)
    return A, meta, fits


def ease(f, a, b):
    return float(pk.smoothstep(np.clip((f - a) / max(b - a, 1e-6), 0, 1)))
