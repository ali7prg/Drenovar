"""Per-species configuration (art/02 crops, segmentation, LOD/variant recipes) + kit export + QA patch."""
import math
import os

import bpy
import numpy as np

import pblend
from frlib import core, paths, render as frr

RT = os.path.join(paths.RUNTIME, "forest")

LODS_TREE = {
    0: dict(trunk_step_m=0.3, trunk_sides=12, limb_step_m=0.25, limb_sides=6, limb_min_r_px=1.3, limb_budget=820,
            copies=True, front_frac=1.0, front_scale=1.0, n_fill=390, fill_size=1.6, n_inner=40, min_dist_k=0.5),
    1: dict(trunk_step_m=0.6, trunk_sides=8, limb_step_m=0.5, limb_sides=4, limb_min_r_px=3.0, limb_budget=260,
            copies=True, front_frac=0.6, front_scale=1.12, n_fill=170, fill_size=1.75, n_inner=12, min_dist_k=0.6),
    2: dict(trunk_step_m=1.6, trunk_sides=5, limb_step_m=1.0, limb_sides=3, limb_min_r_px=99, limb_budget=0,
            copies=False, front_frac=0.18, front_scale=1.5, n_fill=96, fill_size=1.9, n_inner=0, min_dist_k=0.6),
}

TREES = {
    "golden_oak": dict(
        cfg=dict(name="golden_oak", box=(0, 0, 430, 445), exclude=[(284, 360, 320, 432)], clip_row=410, ground_row=421,
                 fork_row=245, wood=dict(ratio=0.85, Lmax=64, hue_rng=(61, 95)), float_min_r=2.2, keep_x=(0, 428),
                 crown_kd=0.9, front_bias=0.45, trunk_kd=0.9, seed=7, root_zone=34, root_k=0.8, n_lobes=13, top_weight=1.6, lum_pref=3.5, mass_up=0.55, front_tilt_max=30),
        n_patches=110, min_px=50, region="golden_oak", bark="oak", swatch=(20, 798, 318, 984), paintedLightMix=0.4,
        height_hint=13.3, crown_hint=7.2, lods=LODS_TREE,
        variants={1: dict(seed=5, copies=[(125, 0.92), (-125, 0.9)]),
                  2: dict(seed=6, mirror=True, copies=[(105, 0.9), (-150, 0.92)]),
                  3: dict(seed=8, copies=[(140, 0.9), (-110, 0.95)], scale=(0.9, 1.06))},
        patch=dict(refs=[("07_fog_exploration_interface.png", (518, 110, 1020, 720), "art/07 panel 2"),
                         ("01_world_masterplan.png", (0, 0, 560, 330), "art/01 NW golden-oak grove")],
                   ground=(0.42, 0.44, 0.24), n=30, area=78.0, spacing=12.0),
    ),
}


def export_kit(asset, built, sp, info, kind, k, args):
    from frlib import paths as P
    import fbuild  # noqa: F401 (forest helpers path)
    import glbx
    root = bpy.data.objects.new(asset, None)
    core.link(root)
    spacing = 0.0
    for v, objs in built.items():
        lo, hi = core.bounds([objs[0]])
        spacing = max(spacing, hi[0] - lo[0], hi[1] - lo[1])
    spacing += 2.0
    export_objs = [root]
    meta_vars = {}
    for i, v in enumerate(sorted(built)):
        objs = built[v]
        ve = bpy.data.objects.new(f"{asset}_v{v}", None)
        core.link(ve)
        ve.parent = root
        ve.location = (i * spacing, 0, 0)
        export_objs.append(ve)
        for o in objs:
            o.parent = ve
            o.location = (0, 0, 0)
            export_objs.append(o)
        bpy.context.view_layer.update()
        lo, hi = core.bounds([objs[0]])
        lo = lo - np.array([i * spacing, 0, 0])
        hi = hi - np.array([i * spacing, 0, 0])
        meta_vars[f"v{v}"] = {
            "nodes": [o.name for o in objs],
            "tris": {f"LOD{l}": core.tri_count(objs[l]) for l in range(3)},
            "materials": {f"LOD{l}": [m.name for m in objs[l].data.materials] for l in range(3)},
            "height_m": round(float(hi[2]), 2),
            "crown_radius_m": round(float(max(-lo[0], hi[0], -lo[1], hi[1])), 2),
            "bounds_m_blender": [np.round(lo, 2).tolist(), np.round(hi, 2).tolist()],
            "display_offset_gltf": [round(i * spacing, 3), 0.0, 0.0],
            "recipe": {kk: vv for kk, vv in sp["variants"][v].items() if kk != "seed"},
        }
    bpy.context.view_layer.update()
    out = os.path.join(RT, f"{asset}.glb")
    ext = {"lf_foliage_atlas": "lf_foliage_atlas.png", f"lf_bark_{kind}_c": f"lf_bark_{kind}_c.jpg",
           f"lf_bark_{kind}_n": f"lf_bark_{kind}_n.png", f"lf_bark_{kind}_r": f"lf_bark_{kind}_r.png"}
    core.select_only(export_objs, export_objs[0])
    core.export_glb(out, export_objs, animations=False,
                    extra=dict(export_vertex_color="ACTIVE", export_all_vertex_colors=False,
                               export_active_vertex_color_when_no_material=False, export_image_format="AUTO"))
    glbx.externalize(out, ext)
    gi = glbx.info(out)
    meta = {
        "id": asset,
        "generation": "v2 image-based reconstruction from art/02 (painted cards + projected bark)",
        "variants": meta_vars,
        "tris": {f"LOD{l}": max(mv["tris"][f"LOD{l}"] for mv in meta_vars.values()) for l in range(3)},
        "bones": 0,
        "materials": sorted(set(gi["materials"])),
        "textures": {"lf_foliage_atlas.png": 2048, f"lf_bark_{kind}_c.jpg": 1024, f"lf_bark_{kind}_n.png": 1024,
                     f"lf_bark_{kind}_r.png": 1024},
        "texture_mode": "external shared files next to the GLB (relative URIs); one foliage atlas for the whole kit",
        "alpha": {"lf_foliage": {"mode": "MASK", "cutoff": 0.5, "double_sided": True}},
        "paintedLightMix": k,
        "paintedLightNote": "Textures carry the painted light. Shade as albedo * mix(1, lambert, paintedLightMix) "
                            "(lambert = max(dot(N, L), 0)); foliage normals are smoothed crown normals.",
        "wind": {"attribute": "COLOR_0 (RGBA float, linear)",
                 "R": "sway weight 0 at the trunk base -> 1 at crown tips", "G": "leaf flutter (cards 0.45..1, bark 0)",
                 "B": "per-branch / crown-sector phase 0..1", "A": "ambient occlusion (1 outer front/top cards, "
                 "0.9 fill, 0.78 inner, bark 1)"},
        "clips": {"lf_forest_wind": {"seconds": 8.0, "loop": True, "type": "shader (vertex colour driven)"}},
        "layout_note": "Variants laid out along +X (display_offset_gltf); the three LODs of a variant share its origin "
                       "(trunk base on the ground).",
        "scale_note": "Real scale from the 1.8 m figure on art/02 (29.8 px/m).",
        "glb_images": gi["images"],
        "build": f"python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/paint3d/build_tree.py "
                 f"{asset.replace('lf_env_', '')}",
    }
    core.write_json(os.path.join(RT, f"{asset}.meta.json"), meta)
    core.save_blend(paths.source("forest", f"{asset}.blend"))
    return out


def forest_patch(asset, built, out_png, sp):
    """~30 mixed instances (variants, yaw, scale) on a ground plane at 55 deg, next to art/07 + art/01 crops."""
    from frlib import refs
    cfg = sp["patch"]
    rng = np.random.default_rng(3)
    insts = []
    area = cfg["area"]
    pts = []
    tries = 0
    while len(pts) < cfg["n"] and tries < 5000:
        tries += 1
        p = rng.uniform(-area / 2, area / 2, 2)
        if all(np.linalg.norm(p - q) > cfg.get("spacing", 7.0) for q in pts):
            pts.append(p)
    vs = sorted(built)
    for i, p in enumerate(pts):
        src = built[vs[i % len(vs)]][0]
        o = src.copy()
        o.name = f"patch_{i}"
        core.link(o)
        o.location = (p[0], p[1], 0)
        o.rotation_euler = (0, 0, rng.uniform(0, 2 * math.pi))
        s = rng.uniform(0.8, 1.1)
        o.scale = (s, s, s)
        insts.append(o)
    bpy.ops.mesh.primitive_plane_add(size=area * 1.6, location=(0, 0, 0))
    g = bpy.context.active_object
    m = bpy.data.materials.new("patch_ground")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*cfg["ground"], 1)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs[0])
    g.data.materials.append(m)
    bpy.context.view_layer.update()
    pblend.only(insts + [g])
    # perspective camera at 55 deg pitch (game-like), framing the patch centre
    d = area * 0.95
    loc = (0.0, -d * math.cos(math.radians(55)), d * math.sin(math.radians(55)))
    cam = frr.perspective_camera(loc, (0, 0, 2.0), lens=35, res=(1100, 900))
    rgba = frr.render_rgba()
    img = rgba[..., :3] * rgba[..., 3:4] + np.array(cfg["ground"]) * (1 - rgba[..., 3:4])
    ims, labs = [], []
    for sheet, box, lab in cfg["refs"]:
        ims.append(refs.crop(refs.load(sheet), box))
        labs.append(lab)
    ims.append(img)
    labs.append(f"{asset} x{len(insts)} instances, 55deg, painted-light")
    frr.side_by_side(ims, labs, out_png, height=640)
    for o in insts:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.objects.remove(g, do_unlink=True)
