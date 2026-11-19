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


def face_labels(body):
    """Region label per face: body halves (x sign) cut into Y bands, legs/arms split outer/inner."""
    V, tris, _uv, _n = core.mesh_arrays(body, evaluated=False)
    me = body.data
    nf = len(me.polygons)
    cen = np.zeros(nf * 3)
    me.polygons.foreach_get("center", cen)
    P = cen.reshape(nf, 3)
    add, _sub = B.build_parts()
    groups = {"body": [], "leg": [], "arm": []}
    for p in add:
        b = p.bone or ""
        if b.startswith(("thigh", "shin", "foot", "toe", "hallux")):
            groups["leg"].append(p)
        elif b.startswith(("upperarm", "forearm", "hand", "finger")):
            groups["arm"].append(p)
        else:
            groups["body"].append(p)
    dist = {}
    for g, ps in groups.items():
        d = np.full(nf, 10.0)
        for p in ps:
            d = np.minimum(d, p.fn(P))
        dist[g] = d
    keys = list(dist)
    owner = np.argmin(np.stack([dist[k] for k in keys], 1), 1)
    lab = np.zeros(nf, np.int64)
    side = (P[:, 0] >= 0).astype(np.int64)
    ybands = np.digitize(P[:, 1], [-3.0, -1.2, 0.6, 2.4])
    zl = np.interp(P[:, 1], B.head_profile()["Y"], B.head_profile()["zlip"])
    wu, _wl = B.head_widths(P[:, 1])
    mouth = (P[:, 1] < -3.28) & (P[:, 1] > -4.6) & (np.abs(P[:, 2] - zl) < 0.17) & (np.abs(P[:, 0]) < wu - 0.045)
    lower_head = (P[:, 2] < zl) & (P[:, 1] < -3.0)
    for i, k in enumerate(keys):
        sel = owner == i
        if k == "body":
            lab[sel] = 100 + side[sel] * 10 + ybands[sel] + 5 * lower_head[sel]
        elif k == "leg":
            # outer / inner half of each leg, toes with the leg
            xin = np.abs(P[sel, 0]) - 0.66
            lab[sel] = 200 + side[sel] * 10 + (xin > 0)
        else:
            lab[sel] = 300 + side[sel] * 10 + (P[sel, 1] < -1.95)
    lab[mouth] = 400 + side[mouth]
    return lab


def region_uv(body, margin=0.0025):
    import bmesh
    lab = face_labels(body)
    me = body.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    for e in bm.edges:
        fs = e.link_faces
        e.seam = bool(len(fs) == 2 and lab[fs[0].index] != lab[fs[1].index])
    bm.to_mesh(me)
    bm.free()
    core.select_only([body])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.unwrap(method="CONFORMAL", margin=margin, correct_aspect=True)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, scale=True, margin=margin, shape_method="CONCAVE", margin_method="SCALED")
    bpy.ops.object.mode_set(mode="OBJECT")


def uv_coverage(o, res=1024):
    V, tris, uv, _ = core.mesh_arrays(o, evaluated=False)
    img = np.zeros((res, res), np.uint8)
    pts = np.round(np.stack([uv[..., 0] * res, (1 - uv[..., 1]) * res], -1) * 16).astype(np.int32)
    import cv2
    for t in range(len(tris)):
        cv2.fillConvexPoly(img, pts[t], 1, shift=4)
    return float(img.mean())


def main():
    t0 = time.time()
    core.reset()
    side = R.side_view(corrected=True, colour=False)
    front = R.front_view(corrected=False)     # raw: keeps the pale ventral keel between the legs
    F, add, sub = B.build_field(voxel=C.VOXEL, hull_views=[side, front], hull_k=0.06)
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
    region_uv(body)
    C.log(f"uv coverage {uv_coverage(body):.3f}")
    parts = D.all_parts()
    for key, name in (("teeth", "maw_teeth"), ("claws", "maw_claws"), ("eyes", "maw_eyes"), ("tongue", "maw_tongue"),
                      ("mouth", "maw_mouth")):
        part_object(name, parts[key])
    for o in list(bpy.data.objects):
        if o.type == "MESH":
            C.log(o.name, core.tri_count(o))
    bpy.ops.wm.save_as_mainfile(filepath=C.cache("maw2_mesh.blend"), compress=True)
    C.log(f"stage mesh done {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
