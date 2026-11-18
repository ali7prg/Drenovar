"""Build ground cover / features GLBs + QA (art/02 bottom row).

Run: python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/forest/build_groundcover.py \
        <fallen_trunk|moss_rock|bramble|reed_fern|grass_tuft|fallen_branches|mushrooms|all> [--iter N] [--no-export]
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
import groundcover as gc  # noqa: E402
from build_trees import WIND_DOC  # noqa: E402

ASSETS = {
    "fallen_trunk": dict(variants={"v1": lambda: gc.build_fallen_trunk(1), "v2": lambda: gc.build_fallen_trunk(2)},
                         ref="fallen_trunk", ref_variant="v1"),
    "moss_rock": dict(variants={f"v{i}": (lambda i=i: gc.build_moss_rock(i)) for i in (1, 2, 3)}, ref="moss_rock",
                      ref_variant="v1"),
    "bramble": dict(variants={f"v{i}": (lambda i=i: gc.build_bramble(i)) for i in (1, 2, 3)}, ref="bramble",
                    ref_variant="v1", fit_height=True),
    "reed_fern": dict(variants={"reed_v1": lambda: gc.build_reed_fern("reed", 1), "reed_v2": lambda: gc.build_reed_fern("reed", 2),
                                "fern_v1": lambda: gc.build_reed_fern("fern", 1), "fern_v2": lambda: gc.build_reed_fern("fern", 2),
                                "mixed_v1": lambda: gc.build_reed_fern("mixed", 1)}, ref="reed_fern", ref_variant="mixed_v1",
                      fit_height=True),
    "grass_tuft": dict(variants={f"v{i}": (lambda i=i: gc.build_grass_tuft(i)) for i in (1, 2, 3)}),
    "fallen_branches": dict(variants={f"v{i}": (lambda i=i: gc.build_fallen_branches(i)) for i in (1, 2)}),
    "mushrooms": dict(variants={f"v{i}": (lambda i=i: gc.build_mushrooms(i)) for i in (1, 2)}),
}


def materials_for(names):
    out = []
    for n in names:
        if n.startswith("bark:"):
            out.append(fbuild.bark_material(n[5:]))
        elif n == "rock":
            R = fbuild.RUNTIME_DIR
            out.append(fbuild.texture_material("lf_rock_limestone", os.path.join(R, "lf_rock_limestone_c.jpg"),
                                               os.path.join(R, "lf_rock_limestone_n.png"), os.path.join(R, "lf_rock_limestone_r.png")))
        else:
            out.append(fbuild.foliage_material())
    return out


def ext_map(mat_names):
    ext = {fbuild.FOLIAGE_ATLAS[:-4]: fbuild.FOLIAGE_ATLAS}
    for n in mat_names:
        if n.startswith("bark:"):
            for f in fbuild.bark_files(n[5:]):
                ext[os.path.splitext(f)[0]] = f
        if n == "rock":
            for f in ("lf_rock_limestone_c.jpg", "lf_rock_limestone_n.png", "lf_rock_limestone_r.png"):
                ext[os.path.splitext(f)[0]] = f
    return ext


def build(name, it, export=True, qa=True, samples=20):
    spec = ASSETS[name]
    asset = f"lf_env_{name}"
    core.reset()
    built = {}
    for vn, fn in spec["variants"].items():
        res = fn()
        mats0 = materials_for(res.mats)
        fol_only = materials_for(["foliage"])
        objs = []
        for lod in range(3):
            if name == "moss_rock":
                mats = mats0
            elif name == "fallen_trunk":
                mats = mats0 if lod == 0 else fol_only
            else:
                mats = fol_only
            o = fbuild.object_from_md(f"{asset}_{vn}_LOD{lod}", res.lods[lod], mats)
            if not res.wind:
                o.data.color_attributes.remove(o.data.color_attributes["Col"])
            objs.append(o)
        built[vn] = (res, objs)
        print(f"[{asset}] {vn}: " + ", ".join(f"LOD{l}={core.tri_count(objs[l])}" for l in range(3)), flush=True)
    metrics = {}
    if qa:
        fqa.studio(samples)
        fqa.use_ao([o for r, os_ in built.values() for o in os_], True)
        if spec.get("ref"):
            rv = spec["ref_variant"]
            obj = built[rv][1][0]
            ppm = None
            if spec.get("fit_height"):
                lo, hi = core.bounds([obj])
                v0 = refsetup.kit_view(spec["ref"], ppm=100.0)
                ys, xs = np.nonzero(v0.mask)
                ppm = (v0.ay - ys.min()) / hi[2]
            view = refsetup.kit_view(spec["ref"], ppm=ppm)
            m, _ = fqa.compare_view(view, [obj], fqa.iter_path(asset, it, f"{rv}_front"), f"{asset} {rv} LOD0 vs art/02 (iter {it})")
            metrics[f"{rv}_front_LOD0"] = m
        x = 0.0
        line = []
        for vn, (res, objs) in built.items():
            lo, hi = core.bounds([objs[0]])
            objs[0].location.x = x - lo[0]
            x += hi[0] - lo[0] + 0.8
            line.append(objs[0])
        bpy.context.view_layer.update()
        fqa.ortho_shot(line, fqa.iter_path(asset, it, "variants_front"), direction=(0, 1, 0), res=(1600, 600),
                       label=f"{asset} variants LOD0 front")
        fqa.ortho_shot(line, fqa.iter_path(asset, it, "variants_strategic55"), pitch_deg=55, yaw_deg=20, res=(1600, 700),
                       label=f"{asset} variants strategic 55deg")
        for o in line:
            o.location.x = 0
        first = list(built.values())[0][1]
        lo, hi = core.bounds([first[0]])
        for i, o in enumerate(first):
            o.location.x = i * (hi[0] - lo[0] + 0.8)
        bpy.context.view_layer.update()
        fqa.ortho_shot(first, fqa.iter_path(asset, it, "lods_strategic55"), pitch_deg=55, yaw_deg=20, res=(1500, 600),
                       label=f"{asset} LOD0 | LOD1 | LOD2")
        for o in first:
            o.location.x = 0
        core.write_json(paths.compare(asset, f"iter{it:02d}_metrics.json"),
                        {"metrics": metrics, "tris": {vn: r.info for vn, (r, o) in built.items()}})
        print(json.dumps({k: (v["iou"], v["iou_closed_r4"]) for k, v in metrics.items()}), flush=True)
    if not export:
        return
    fqa.use_ao([o for r, os_ in built.values() for o in os_], False)
    root = fbuild.empty(asset)
    spacing = 0.0
    for vn, (res, objs) in built.items():
        lo, hi = core.bounds([objs[0]])
        spacing = max(spacing, hi[0] - lo[0], hi[1] - lo[1])
    spacing += 1.0
    exp = [root]
    meta_vars = {}
    allm = set()
    for i, (vn, (res, objs)) in enumerate(built.items()):
        ve = fbuild.empty(f"{asset}_{vn}", parent=root, location=(i * spacing, 0, 0))
        exp.append(ve)
        lo, hi = core.bounds([objs[0]])
        for lod, o in enumerate(objs):
            o.parent = ve
            o.location = (0, 0, 0)
            exp.append(o)
        allm |= set(res.mats)
        meta_vars[vn] = {"nodes": [o.name for o in objs], "tris": {f"LOD{l}": core.tri_count(objs[l]) for l in range(3)},
                         "display_offset_gltf": fbuild.to_gltf((i * spacing, 0, 0)),
                         "materials": {f"LOD{l}": [m.name for m in objs[l].data.materials] for l in range(3)},
                         "height_m": round(float(hi[2]), 2),
                         "footprint_radius_m": round(float(max(-lo[0], hi[0], -lo[1], hi[1])), 2),
                         "bounds_m_blender": [np.round(lo, 2).tolist(), np.round(hi, 2).tolist()],
                         "wind": bool(res.wind), "info": res.info}
    bpy.context.view_layer.update()
    out = paths.runtime("forest", f"{asset}.glb")
    anywind = any(r.wind for r, o in built.values())
    fbuild.export(out, exp, external_images=ext_map(allm), with_colors=anywind)
    import glbx
    gi = glbx.info(out)
    meta = {"id": asset, "variants": meta_vars,
            "tris": {f"LOD{l}": max(v["tris"][f"LOD{l}"] for v in meta_vars.values()) for l in range(3)},
            "bones": 0, "materials": sorted(set(gi["materials"])), "glb_images": gi["images"],
            "texture_mode": "external shared files next to the GLB (relative URIs)",
            "wind": WIND_DOC if anywind else "static (no COLOR_0)",
            "layout_note": "Variants along +X (display_offset_gltf); LOD0/1/2 of a variant share its origin (show one per "
                           "distance). Mesh origin = ground contact centre.",
            "build": f"python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/forest/build_groundcover.py {name}"}
    if name in ("fallen_trunk", "moss_rock"):
        meta["collision"] = "use a convex hull / capsule of LOD2 (see footprint_radius_m, height_m)"
    fbuild.write_meta(paths.runtime("forest", f"{asset}.meta.json"), meta)
    core.save_blend(paths.source("forest", f"{asset}.blend"))
    print(f"[{asset}] exported {gi['meshes']}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--iter", type=int, default=1)
    ap.add_argument("--no-export", action="store_true")
    ap.add_argument("--no-qa", action="store_true")
    a = ap.parse_args(sys.argv[1:])
    names = list(ASSETS) if a.name == "all" else a.name.split(",")
    for n in names:
        t0 = time.time()
        build(n, a.iter, export=not a.no_export, qa=not a.no_qa)
        print(f"[{n}] {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
