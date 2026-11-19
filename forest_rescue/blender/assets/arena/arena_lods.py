"""Light LOD1 / LOD2 assemblies of the boss arena for the normal city zoom (keeps every node name and the
state_* dressing nodes of lf_boss_arena_assembled.glb; the module GLBs are untouched).

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/arena/arena_lods.py
Out: godot/project/assets/forest_rescue/arena/lf_boss_arena_assembled_lod1.glb / _lod2.glb and an "lods" entry
in lf_boss_arena_assembled.meta.json.  LOD1 = module LOD1 meshes (cliffs, fossil wall, pillars, the same meshes
forest_landmarks.gd swaps in above zoom 34) + decimated floor/bones/stream; LOD2 = a further ~45 % of LOD1 and
half-size textures.
"""
import json
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from frlib import core, paths  # noqa: E402

AID = "lf_boss_arena"


def decimate(o, ratio):
    if ratio >= 0.999 or o.type != "MESH":
        return
    mod = o.modifiers.new("dec", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    core.select_only([o])
    while o.modifiers.find("dec") > 0:
        bpy.ops.object.modifier_move_up(modifier="dec")
    bpy.ops.object.modifier_apply(modifier="dec")


def main():
    bpy.ops.wm.open_mainfile(filepath=paths.source("arena", f"{AID}.blend"))
    col = bpy.data.collections["assembled"]
    objs = list(col.objects)
    placed = [o for o in objs if o.type == "MESH" and not o.name.startswith("banner_")]
    banners = [o for o in objs if o.name.startswith("banner_")]
    lod1_src = {}
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name.endswith("_LOD1"):
            lod1_src[o.name[:-5].replace("lf_arena_", "")] = o
    out_dir = paths.ensure(paths.RUNTIME, "arena")
    meta_path = os.path.join(out_dir, f"{AID}_assembled.meta.json")
    meta = json.load(open(meta_path))
    lods = {}
    # LOD1: swap module meshes for their LOD1 data (cliff_a/b/c, fossil, pillar_a/b), decimate the rest
    for o in placed:
        key = None
        if o.name.startswith("cliff_"):
            key = "cliff_" + o.name[-1]
        elif o.name.startswith("pillar_"):
            key = "pillar_" + o.name[-1]
        elif o.name == "fossil_wall":
            key = "fossil_wall"
        if key and key in lod1_src:
            o.data = lod1_src[key].data
        elif o.name == "floor":
            o.data = o.data.copy()
            decimate(o, 0.5)
        elif o.name.startswith(("bones_", "stream")):
            o.data = o.data.copy()
            decimate(o, 0.55)
    t1 = sum(core.tri_count(o) for o in placed + banners if o.type == "MESH")
    p1 = os.path.join(out_dir, f"{AID}_assembled_lod1.glb")
    core.export_glb(p1, placed + banners, animations=True)
    lods["LOD1"] = {"file": os.path.basename(p1), "tris": t1, "bytes": os.path.getsize(p1)}
    # LOD2: everything to ~45 % of LOD1 (unique copies), textures halved
    done = {}
    for o in placed:
        if o.data.name not in done:
            o.data = o.data.copy()
            decimate(o, 0.45 if not o.name.startswith("floor") else 0.5)
            done[o.data.name] = o.data
        else:
            o.data = done[o.data.name]
    for img in bpy.data.images:
        if img.size[0] >= 512:
            img.scale(img.size[0] // 2, img.size[1] // 2)
    t2 = sum(core.tri_count(o) for o in placed + banners if o.type == "MESH")
    p2 = os.path.join(out_dir, f"{AID}_assembled_lod2.glb")
    core.export_glb(p2, placed + banners, animations=True)
    lods["LOD2"] = {"file": os.path.basename(p2), "tris": t2, "bytes": os.path.getsize(p2)}
    meta["lods"] = dict(lods, LOD0={"file": f"{AID}_assembled.glb", "tris": meta["tris"]["LOD0_total"]},
                        note="same node names (cliff_NN_v, fossil_wall, pillar_N_v, bones_N, floor, stream, "
                             "banner_N[_rig]) in every LOD file; suggested use: LOD0 zoom <= 34, LOD1 zoom <= 85, "
                             "LOD2 beyond (actor LOD thresholds 42/85)")
    core.write_json(meta_path, meta)
    print("ARENA_LODS", json.dumps(lods))


if __name__ == "__main__":
    main()
