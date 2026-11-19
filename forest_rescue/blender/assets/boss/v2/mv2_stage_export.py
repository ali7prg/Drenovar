"""Stage 5: LOD0/1/2 (48k/24k/9k tris, <=80/50/28 weighted bones), runtime textures, GLB + meta.json,
packed master .blend.   In: cache/maw2_anim.blend
Out: godot/project/assets/forest_rescue/boss/lf_boss_ancient_maw.glb (+ .meta.json),
     forest_rescue/blender/sources/boss/lf_boss_ancient_maw.blend
"""
import json
import os
import sys
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mv2_common as C  # noqa: E402
import mv2_rig as RG  # noqa: E402
from frlib import core, paths  # noqa: E402

ARM = C.ASSET_ID + "_rig"
DETAILS = ["maw_teeth", "maw_claws", "maw_eyes", "maw_tongue", "maw_mouth"]
# detail decimation per LOD (ratio of the LOD0 detail triangles; None = dropped)
DETAIL_RATIO = {1: {"maw_teeth": 0.5, "maw_claws": 0.6, "maw_eyes": 0.5, "maw_tongue": 0.6, "maw_mouth": 1.0},
                2: {"maw_teeth": 0.22, "maw_claws": 0.32, "maw_eyes": 0.25, "maw_tongue": None, "maw_mouth": 1.0}}


def dup(obj, name):
    new = obj.copy()
    new.data = obj.data.copy()
    new.name = name
    new.data.name = name
    for c in obj.users_collection:
        c.objects.link(new)
    return new


def decimate(obj, ratio):
    if ratio >= 0.999:
        return obj
    mod = obj.modifiers.new("decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    core.select_only([obj])
    while obj.modifiers.find("decimate") > 0:
        bpy.ops.object.modifier_move_up(modifier="decimate")
    bpy.ops.object.modifier_apply(modifier="decimate")
    return obj


def merge_groups(obj, merged):
    """Fold the vertex groups of merged bones into their surviving ancestors; renormalise; <= 4 influences."""
    names = [g.name for g in obj.vertex_groups]
    nv = len(obj.data.vertices)
    W = np.zeros((nv, len(names)))
    for v in obj.data.vertices:
        for g in v.groups:
            W[v.index, g.group] = g.weight
    allnames = [b["name"] for b in RG.bone_table()]
    full = np.zeros((nv, len(allnames)))
    for j, n in enumerate(names):
        if n in allnames:
            full[:, allnames.index(n)] = W[:, j]
    full = RG.merge_weights(full, allnames, set(merged))
    full = RG.limit(full, 4, 0.02)
    obj.vertex_groups.clear()
    used = []
    for j, n in enumerate(allnames):
        col = full[:, j]
        nz = np.nonzero(col > 0)[0]
        if len(nz) == 0:
            continue
        used.append(n)
        vg = obj.vertex_groups.new(name=n)
        vals = np.round(col[nz], 4)
        order = np.argsort(vals)
        nz, vals = nz[order], vals[order]
        splits = np.nonzero(np.diff(vals))[0] + 1
        for idx, val in zip(np.split(nz, splits), np.split(vals, splits)):
            vg.add(idx.tolist(), float(val[0]), "REPLACE")
    return used


def weighted_bones(obj):
    used = set()
    for v in obj.data.vertices:
        for g in v.groups:
            if g.weight > 0:
                used.add(obj.vertex_groups[g.group].name)
    return sorted(used)


def runtime_images():
    """Smaller runtime copies for normal/ORM (the painted game shader uses albedo only)."""
    for key, size in (("normal", 1024), ("orm", 1024)):
        img = bpy.data.images.get(f"{C.ASSET_ID}_{key}")
        if img is None:
            continue
        img.scale(size, size)


def main():
    t0 = time.time()
    bpy.ops.wm.open_mainfile(filepath=C.cache("maw2_anim.blend"))
    arm = bpy.data.objects[ARM]
    body = bpy.data.objects["maw_body"]
    for o in list(bpy.data.objects):
        if o.name in ("maw_high", "maw_bake_src"):
            bpy.data.objects.remove(o, do_unlink=True)
    lods = {}
    stats = {}
    # LOD0: body + all details joined (2 materials)
    parts0 = [dup(body, "lod0_body")] + [dup(bpy.data.objects[n], f"lod0_{n}") for n in DETAILS]
    lod0 = core.join(parts0, f"{C.ASSET_ID}_LOD0")
    lods[0] = lod0
    for lv, body_tris in ((1, C.BODY_TRIS[1]), (2, C.BODY_TRIS[2])):
        b = dup(body, f"lod{lv}_body")
        decimate(b, body_tris / max(core.tri_count(b), 1))
        ps = [b]
        for n in DETAILS:
            r = DETAIL_RATIO[lv][n]
            if r is None:
                continue
            d = dup(bpy.data.objects[n], f"lod{lv}_{n}")
            decimate(d, r)
            ps.append(d)
        lods[lv] = core.join(ps, f"{C.ASSET_ID}_LOD{lv}")
    for lv, merged in ((0, []), (1, RG.MERGE_LOD1), (2, RG.MERGE_LOD2)):
        o = lods[lv]
        merge_groups(o, merged)
        # make sure the (single) armature modifier is last and points at the rig
        for m in list(o.modifiers):
            if m.type == "ARMATURE":
                o.modifiers.remove(m)
        mod = o.modifiers.new("Armature", "ARMATURE")
        mod.object = arm
        o.parent = arm
        stats[lv] = {"tris": core.tri_count(o), "weighted_bones": len(weighted_bones(o))}
        C.log(f"LOD{lv}: {stats[lv]}")
    for n in ["maw_body"] + DETAILS:
        bpy.data.objects[n].hide_render = True
        bpy.data.objects[n].hide_viewport = True
    runtime_images()
    # --- GLB
    out = paths.runtime(C.GROUP, f"{C.ASSET_ID}.glb")
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()
    bpy.context.scene.render.fps = 60
    core.export_glb(out, [arm, lods[0], lods[1], lods[2]], animations=True, image_format="AUTO",
                    jpeg_quality=88, extra={"export_animation_mode": "ACTIONS", "export_force_sampling": True,
                                             "export_optimize_animation_size": True, "export_frame_step": 1})
    size = os.path.getsize(out)
    # --- meta
    rep = json.load(open(C.cache("clip_report.json")))
    tinfo = json.load(open(C.cache("tex_info.json")))
    lmin, lmax = core.bounds([lods[0]])
    names = [b.name for b in arm.data.bones]
    tb = {b["name"]: b for b in RG.bone_table()}
    scale_info = json.load(open(C.cache("scale_info.json"))) if os.path.exists(C.cache("scale_info.json")) else {}
    meta = {
        "id": C.ASSET_ID,
        "generation": "v2 image-based: anatomical SDF fitted to art/03 side/front silhouettes (soft visual hull), "
                      "7-view painting projection (ortho side/front, solved rear-3/4 and head close-up cameras)",
        "rig": "new_dinosaur_boss",
        "tris": {f"LOD{k}": v["tris"] for k, v in stats.items()},
        "budget": {"LOD0": 48000, "LOD1": 24000, "LOD2": 9000},
        "bones": {"deform": len(names), "total": len(names),
                  "weightedByLOD": {f"LOD{k}": v["weighted_bones"] for k, v in stats.items()},
                  "budgetByLOD": [80, 50, 28], "maxInfluences": 4, "names": names},
        "nodes": {f"LOD{k}": f"{C.ASSET_ID}_LOD{k}" for k in (0, 1, 2)},
        "materials": [f"{C.ASSET_ID}_body", f"{C.ASSET_ID}_keratin"],
        "paintedLightMix": 0.38,
        "shading": "albedo * mix(1, lambert(sun), paintedLightMix): the atlas carries the painted light of art/03",
        "textures": {f"{C.ASSET_ID}_body_basecolor": 2048, f"{C.ASSET_ID}_body_normal": 1024,
                     f"{C.ASSET_ID}_body_orm": 1024, f"{C.ASSET_ID}_keratin": 512},
        "bounds_m": {"min": [round(float(x), 3) for x in lmin], "max": [round(float(x), 3) for x in lmax]},
        "dimensions_m": {"snoutToTailTip": round(float(lmax[1] - lmin[1]), 3), "skullTop": 3.6, "hipLine": 2.75,
                         "note": "built at the sheet's vertical key stats (head 3.6 m, hip line 2.75 m); the drawn "
                                 "length line then measures 8.46 m, snout->tail tip ~9.8 m (sheet not self-consistent)"},
        "sockets": {k: [round(v[0], 3), round(v[2], 3), round(-v[1], 3)] for k, v in {
            "head_top": (0.0, -3.62, 3.60), "jaw_tip": (0.0, -4.48, 2.68), "mouth": (0.0, -4.10, 2.95),
            "eye_L": (0.36, -3.63, 3.285), "chest": (0.0, -1.60, 2.40), "hips": (0.0, -0.15, 2.50),
            "tail_tip": (0.0, 5.30, 2.19), "foot_L": (0.68, -0.30, 0.10), "foot_R": (-0.68, -0.30, 0.10)}.items()},
        "clips": rep,
        "glbBytes": size,
        "textureProjection": {"coverageByView": tinfo.get("coverage_by_view"), "rearCamera": {
            k: tinfo["rear_cam"].get(k) for k in ("pnp_rms_px", "refined_iou", "refined_rms_px")},
            "headCamera": {k: tinfo["head_cam"].get(k) for k in ("pnp_rms_px", "jaw_open_deg")}},
        "coordinateConvention": {"up": "+Y", "forward": "+Z", "unit": "metre",
                                 "note": "Blender -Y forward exported to glTF +Z; feet on y=0, root at the origin"},
        "notes": "Clips in place (root bone fixed). Turn clips: apply rootYawDeg with the documented curve to the node. "
                 "lane_charge lunges the body ~2.6 m forward inside the clip and steps back during recovery (root stays "
                 "on the mark). Markers are presentation-only (manifest). Keys sampled at 60 fps so 4.25/5.45/0.55 s are "
                 "exact.",
    }
    if scale_info:
        meta["recommendedScale"] = scale_info.get("recommendedScale")
        meta["recommendedScaleInfo"] = scale_info
    core.write_json(paths.runtime(C.GROUP, f"{C.ASSET_ID}.meta.json"), meta)
    # --- master .blend (packed textures, rig, all actions, LODs)
    master = paths.source(C.GROUP, f"{C.ASSET_ID}.blend")
    core.save_blend(master)
    C.log(f"export done {size / 1e6:.2f} MB {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
