"""Build one tree species (all variants, LOD0/1/2), QA renders, GLB + meta + .blend.

Run: python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/forest/build_trees.py \
        <golden_oak|dark_pine|birch|willow|hollow_oak> [--iter N] [--no-export] [--no-qa] [--samples S]

Outputs:
  godot/project/assets/forest_rescue/forest/lf_env_<species>.glb (+ .meta.json); textures are external
  shared files in the same folder (lf_foliage_atlas.png, lf_bark_<kind>_{c,n,r}).
  forest_rescue/blender/sources/forest/lf_env_<species>.blend
  forest_rescue/qa/compare/lf_env_<species>/iterNN_*.png|json
GLB layout: root `<id>` -> `<id>_vK` (display offset along +X) -> meshes `<id>_vK_LOD0/1/2`
(LOD1/LOD2 displayed behind LOD0).  Mesh data is authored around the trunk base = local origin.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fbuild  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from frlib import core, paths  # noqa: E402
import fqa  # noqa: E402
import refsetup  # noqa: E402
import trees  # noqa: E402
import trees_hollow  # noqa: E402

SPECIES = {
    "golden_oak": dict(fn=trees.build_golden_oak, variants=[1, 2, 3, 4], bark="oak", ref="golden_oak"),
    "dark_pine": dict(fn=trees.build_dark_pine, variants=[1, 2, 3, 4], bark="pine", ref="dark_pine"),
    "birch": dict(fn=trees.build_birch, variants=[1, 2, 3], bark="birch", ref="birch"),
    "willow": dict(fn=trees.build_willow, variants=[1, 2, 3], bark="willow", ref="willow"),
    "hollow_oak": dict(fn=trees_hollow.build_hollow_oak, variants=[1, 2, 3], bark="hollow", ref="hollow_oak"),
}

WIND_DOC = {
    "attribute": "COLOR_0 (RGBA float, linear)",
    "R": "branch sway weight: 0 at trunk base -> 1 at branch tips (path length along the skeleton, ^1.35)",
    "G": "leaf flutter weight: 0 on bark, 0.25-0.3 at a card's attachment edge -> 0.8-1.0 at its free edge",
    "B": "per-branch phase 0..1 (first-order branch random, sub-branches inherit +-0.06); trunk 0",
    "A": "crown ambient occlusion 0.45..1 (1 = outer/top of crown); multiply albedo in the shader",
    "clip": "lf_forest_wind, 8 s seamless loop: use TIME*2pi/8 with integer harmonics (see lf_forest_wind.gdshader)",
    "godot_note": "Godot's glTF importer enables vertex_color_use_as_albedo when COLOR_0 exists: use the "
                  "provided ShaderMaterial (or disable that flag) or the wind mask tints the albedo.",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("species")
    ap.add_argument("--iter", type=int, default=1)
    ap.add_argument("--no-export", action="store_true")
    ap.add_argument("--no-qa", action="store_true")
    ap.add_argument("--samples", type=int, default=20)
    ap.add_argument("--variants", default="")
    ap.add_argument("--quick", action="store_true", help="intermediate iteration: fewer QA renders")
    a = ap.parse_args(sys.argv[1:])
    sp = SPECIES[a.species]
    asset = f"lf_env_{a.species}"
    t0 = time.time()
    core.reset()
    view = refsetup.kit_view(sp["ref"])
    fol = fbuild.foliage_material()
    bark = fbuild.bark_material(sp["bark"])
    variants = [int(v) for v in a.variants.split(",")] if a.variants else sp["variants"]
    built = {}
    info = {}
    for v in variants:
        res = sp["fn"](v, view=view)
        objs = []
        for lod in range(3):
            mats = [bark, fol] if lod == 0 else [fol]
            o = fbuild.object_from_md(f"{asset}_v{v}_LOD{lod}", res.lods[lod], mats)
            objs.append(o)
        built[v] = (res, objs)
        info[v] = res.info
        print(f"[{asset}] v{v}: " + ", ".join(f"LOD{l}={res.info[f'LOD{l}']['tris']}" for l in range(3)) +
              f"  ({time.time() - t0:.1f}s)", flush=True)
    # ------------------------------------------------------------------ QA
    if not a.no_qa:
        fqa.studio(a.samples)
        metrics = {}
        if 1 in built:
            m, _ = fqa.compare_view(view, [built[1][1][0]], fqa.iter_path(asset, a.iter, "v1_front"),
                                    f"{asset} v1 LOD0 vs art/02 (iter {a.iter})")
            metrics["v1_front_LOD0"] = m
            for lod in (() if a.quick else (1, 2)):
                m, _ = fqa.compare_view(view, [built[1][1][lod]], fqa.iter_path(asset, a.iter, f"v1_front_LOD{lod}"),
                                        f"{asset} v1 LOD{lod} vs art/02")
                metrics[f"v1_front_LOD{lod}"] = m
        # lineup: variants side by side (LOD0), front ortho
        x = 0.0
        lineup = []
        for v in variants:
            res, objs = built[v]
            lo, hi = core.bounds([objs[0]])
            w = hi[0] - lo[0]
            objs[0].location.x = x - lo[0]
            lineup.append(objs[0])
            x += w + 1.5
        bpy.context.view_layer.update()
        fqa.ortho_shot(lineup, fqa.iter_path(asset, a.iter, "variants_front"), direction=(0, 1, 0), res=(1600, 640),
                       label=f"{asset} variants v{variants[0]}..v{variants[-1]} LOD0 front")
        fqa.ortho_shot(lineup, fqa.iter_path(asset, a.iter, "variants_top"), pitch_deg=90, res=(1600, 640),
                       label=f"{asset} variants top-down (ortho)")
        fqa.ortho_shot(lineup, fqa.iter_path(asset, a.iter, "variants_strategic55"), pitch_deg=55, yaw_deg=20,
                       res=(1600, 720), label=f"{asset} variants strategic 55deg")
        for o in lineup:
            o.location.x = 0
        # LOD lineup of v1
        v1 = variants[0]
        if a.quick:
            core.write_json(paths.compare(asset, f"iter{a.iter:02d}_metrics.json"),
                            {"metrics": metrics, "tris": {f"v{v}": info[v] for v in variants}})
            print(json.dumps({k: (v["iou"], v["iou_closed_r4"]) for k, v in metrics.items()}), flush=True)
            v1 = None
        objs = built[v1 or variants[0]][1]
        lo, hi = core.bounds([objs[0]])
        w = hi[0] - lo[0] + 1.5
        for i, o in enumerate(objs):
            o.location.x = i * w
        bpy.context.view_layer.update()
        if not a.quick:
          fqa.ortho_shot(objs, fqa.iter_path(asset, a.iter, "lods_front"), direction=(0, 1, 0), res=(1500, 600),
                       label=f"{asset} v{v1} LOD0 | LOD1 | LOD2")
        fqa.ortho_shot(objs, fqa.iter_path(asset, a.iter, "lods_strategic55"), pitch_deg=55, yaw_deg=20,
                       res=(1500, 600), label=f"{asset} v{v1} LOD0 | LOD1 | LOD2 strategic 55deg")
        for o in objs:
            o.location.x = 0
        core.write_json(paths.compare(asset, f"iter{a.iter:02d}_metrics.json"),
                        {"metrics": metrics, "tris": {f"v{v}": info[v] for v in variants}})
        print(json.dumps({k: (v["iou"], v["iou_closed_r4"]) for k, v in metrics.items()}), flush=True)
    if a.no_export:
        return
    # ------------------------------------------------------------------ export layout + meta
    root = fbuild.empty(asset)
    spacing = 0.0
    for v in variants:
        lo, hi = core.bounds([built[v][1][0]])
        spacing = max(spacing, hi[0] - lo[0], hi[1] - lo[1])
    spacing += 2.0
    export_objs = [root]
    meta_vars = {}
    for i, v in enumerate(variants):
        res, objs = built[v]
        ve = fbuild.empty(f"{asset}_v{v}", parent=root, location=(i * spacing, 0, 0))
        export_objs.append(ve)
        for lod, o in enumerate(objs):
            o.parent = ve
            o.location = (0, lod * spacing, 0)
            export_objs.append(o)
        lo, hi = core.bounds([objs[0]])
        lo = lo - np.array([i * spacing, 0, 0])
        hi = hi - np.array([i * spacing, 0, 0])
        bpy.context.view_layer.update()
        meta_vars[f"v{v}"] = {
            "nodes": [o.name for o in objs],
            "tris": {f"LOD{l}": core.tri_count(objs[l]) for l in range(3)},
            "materials": {f"LOD{l}": [m.name for m in objs[l].data.materials] for l in range(3)},
            "height_m": round(float(hi[2]), 2),
            "crown_radius_m": round(float(max(-lo[0], hi[0], -lo[1], hi[1])), 2),
            "bounds_m_blender": [np.round(lo, 2).tolist(), np.round(hi, 2).tolist()],
            "display_offset_gltf": fbuild.to_gltf((i * spacing, 0, 0)),
        }
    bpy.context.view_layer.update()
    out = paths.runtime("forest", f"{asset}.glb")
    ext = {fbuild.FOLIAGE_ATLAS[:-4]: fbuild.FOLIAGE_ATLAS}
    for f in fbuild.bark_files(sp["bark"]):
        ext[os.path.splitext(f)[0]] = f
    fbuild.export(out, export_objs, external_images=ext)
    import glbx
    gi = glbx.info(out)
    meta = {
        "id": asset,
        "variants": meta_vars,
        "tris": {f"LOD{l}": max(mv["tris"][f"LOD{l}"] for mv in meta_vars.values()) for l in range(3)},
        "bones": 0,
        "materials": sorted(set(gi["materials"])),
        "textures": {fbuild.FOLIAGE_ATLAS: 2048, **{f: 1024 for f in fbuild.bark_files(sp["bark"])}},
        "texture_mode": "external shared files next to the GLB (relative URIs); one foliage atlas for the whole kit",
        "alpha": {"lf_foliage": {"mode": "MASK", "cutoff": 0.5, "double_sided": True}},
        "wind": WIND_DOC,
        "clips": {"lf_forest_wind": {"seconds": 8.0, "loop": True, "type": "shader (vertex colour driven)"}},
        "layout_note": "Node translations are preview offsets only (variants along +X, LOD1/LOD2 rows behind). "
                       "Instance the Mesh resources with your own transforms; mesh origin = trunk base on the ground.",
        "lod_note": "LOD0: bark+foliage (2 surfaces); LOD1/LOD2: single foliage-atlas surface (bark strip in atlas).",
        "glb_images": gi["images"],
        "build": f"python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/forest/build_trees.py {a.species}",
    }
    fbuild.write_meta(paths.runtime("forest", f"{asset}.meta.json"), meta)
    core.save_blend(paths.source("forest", f"{asset}.blend"))
    print(f"[{asset}] exported {out} {gi['meshes']} ({time.time() - t0:.1f}s)", flush=True)


if __name__ == "__main__":
    main()
