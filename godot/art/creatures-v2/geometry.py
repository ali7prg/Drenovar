"""Stage 1: sculpt extraction (high-res) and per-LOD low-poly meshes with UV atlases."""
import os
import time

import numpy as np

from sdf import extract, largest_component

LODS = (0, 1, 2)


def highres(spec_parts, work, h_body, h_rigid, log=print):
    """Marching-cubes meshes of every part, cached as .npz in `work`."""
    os.makedirs(work, exist_ok=True)
    out = {}
    for part in spec_parts:
        path = os.path.join(work, f"hi_{part['name']}.npz")
        if os.path.exists(path):
            z = np.load(path)
            out[part["name"]] = (z["v"], z["f"])
            continue
        t = time.time()
        h = h_body if part["rigid"] is None else part.get("voxel", h_rigid)
        v, f = extract(part["part"], h)
        v, f = largest_component(v, f, 0.05 if part["rigid"] is None else 0.2)
        np.savez_compressed(path, v=v, f=f)
        out[part["name"]] = (v, f)
        log(f"  hi {part['name']}: {len(v)} v, {len(f)} f, {time.time() - t:.1f}s")
    return out


def build_lod_objects(bo, spec_parts, hi, lod, log=print):
    """Creates Blender low-poly objects for one LOD. Returns {material: [objects]} and the hi objects."""
    groups = {}
    hi_objs = {}
    for part in spec_parts:
        name = part["name"]
        v, f = hi[name]
        if name not in hi_objs:
            hob = bo.to_object(f"HI_{name}", v, f)
            bo.shade(hob)
            hi_objs[name] = hob
        target = part["faces"][lod]
        lob = bo.to_object(f"L{lod}_{name}", v, f)
        t = time.time()
        if part["rigid"] is None and lod == 0 and target >= 2000:
            # retopology: evenly spaced quads (deform well), then snapped back onto the sculpt
            ok = False
            for attempt in ("decimated", "voxel"):
                if attempt == "decimated":
                    bo.decimate(lob, min(len(f), 200000))
                else:
                    bo.voxel_remesh(lob, 0.011)
                    bo.decimate(lob, 200000)
                bo.clean_manifold(lob)
                ok = bo.quadriflow(lob, target // 2)
                if ok:
                    break
                log(f"  quadriflow refused the {attempt} mesh")
            if not ok:
                bo.decimate(lob, target)
            else:
                bo.project_onto(lob, hi_objs[name], 0.06)
        else:
            bo.decimate(lob, target)
        bo.triangulate(lob)
        bo.shade(lob, None if part["rigid"] is None else part.get("sharp", 55))
        log(f"  L{lod} {name}: {len(lob.data.polygons)} tris {time.time() - t:.1f}s")
        lob["part"] = name
        groups.setdefault(part["material"], []).append(lob)
    return groups, hi_objs


def join(bo, objs, name):
    import bpy
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    # keep the source part per vertex as an integer attribute before joining
    for k, o in enumerate(objs):
        attr = o.data.attributes.get("part_id") or o.data.attributes.new("part_id", "INT", "POINT")
        attr.data.foreach_set("value", np.full(len(o.data.vertices), o.get("part_index", k), np.int32))
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    return ob
