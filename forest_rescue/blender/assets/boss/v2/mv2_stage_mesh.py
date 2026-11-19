"""Stage 1: SDF body (+ side/front visual hull) -> marching cubes -> Blender body LOD0 + detail meshes + UVs.

Output: cache/maw2_mesh.blend (objects: maw_high, maw_body, maw_teeth, maw_claws, maw_eyes, maw_tongue)
"""
import os
import sys
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mv2_common as C  # noqa: E402
import mv2_body as B  # noqa: E402
import mv2_details as D  # noqa: E402
import mv2_refs as R  # noqa: E402
from frlib import core, sdf  # noqa: E402


def mesh_from_arrays(name, V, F, smooth=True):
    me = bpy.data.meshes.new(name)
    V = np.asarray(V, np.float32)
    F = np.asarray(F, np.int32)
    me.vertices.add(len(V))
    me.vertices.foreach_set("co", V.ravel())
    me.loops.add(F.size)
    me.loops.foreach_set("vertex_index", F.ravel())
    me.polygons.add(len(F))
    me.polygons.foreach_set("loop_start", np.arange(0, F.size, 3, dtype=np.int32))
    me.update(calc_edges=True)
    me.validate()
    if smooth:
        me.shade_smooth()
    obj = bpy.data.objects.new(name, me)
    core.link(obj)
    return obj


def part_object(name, parts, smooth=True):
    V, Fs, UV = [], [], []
    off = 0
    for p in parts:
        V.append(p["verts"])
        for f in p["faces"]:
            Fs.append([i + off for i in f])
        UV.append(p["uv"])
        off += len(p["verts"])
    obj = core.mesh_object(name, np.concatenate(V), Fs, uvs=np.concatenate(UV), smooth=smooth)
    return obj


def main():
    t0 = time.time()
    core.reset()
    side = R.side_view(corrected=True, colour=False)
    front = R.front_view()
    F, add, sub = B.build_field(voxel=C.VOXEL, hull_views=[side, front], hull_k=0.02)
    C.log(f"field {F.n} built {time.time() - t0:.1f}s")
    F.d = sdf.ndi.gaussian_filter(F.d, 0.6).astype(np.float32)
    V, Fc = F.mesh()
    C.log(f"marching cubes: {len(V)} verts {len(Fc)} tris {time.time() - t0:.1f}s")
    np.savez_compressed(C.cache("maw2_high.npz"), V=V.astype(np.float32), F=Fc.astype(np.int32))
    high = mesh_from_arrays("maw_high", V, Fc)
    # bake source: ~600k tris
    src = core.decimate_to(high, 600000, name="maw_bake_src", copy=True)
    body = core.decimate_to(src, C.BODY_TRIS[0], name="maw_body", copy=True)
    bpy.data.objects.remove(high, do_unlink=True)
    C.log(f"decimated: bake_src {core.tri_count(src)} body {core.tri_count(body)} {time.time() - t0:.1f}s")
    # UVs: smart projection (3-D continuous texture content hides the seams), pack with margin
    core.smart_uv(body, angle=62.0, margin=0.0035, area_weight=0.0)
    core.pack_uv(body, margin=0.003)
    parts = D.all_parts()
    for key, name in (("teeth", "maw_teeth"), ("claws", "maw_claws"), ("eyes", "maw_eyes"), ("tongue", "maw_tongue")):
        part_object(name, parts[key])
    for o in list(bpy.data.objects):
        if o.type == "MESH":
            C.log(o.name, core.tri_count(o))
    bpy.ops.wm.save_as_mainfile(filepath=C.cache("maw2_mesh.blend"), compress=True)
    C.log(f"stage mesh done {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
