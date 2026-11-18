"""Cage build + QA pipeline shared by build_lf_cage_wood/iron/root.py."""
import json
import math
import os
import sys

import bpy
import numpy as np

import cagekit as ck
import propkit as pk
import propproj as pp
import propqa as qa
import propshaders as sh
from frlib import core, paths

IMG = "cage_variants_gate_sockets.png"
REF = {
    "oak": {"closed": (100, 110, 492, 432), "open": (100, 432, 500, 742), "hinge": (60, 772, 270, 948),
            "socket": (294, 772, 472, 948), "artifact": "stone_rune", "x0": [-0.75, 0.30, 0, 15.0, 2.6, 0, 0]},
    "iron": {"closed": (598, 110, 972, 446), "open": (598, 442, 986, 742), "hinge": (550, 772, 710, 948),
             "socket": (784, 772, 960, 948), "artifact": "bronze_seal", "x0": [-0.75, 0.30, 0, 15.0, 2.6, 0, 0]},
    "root": {"closed": (1062, 100, 1490, 426), "open": (1062, 424, 1490, 742), "hinge": (1037, 772, 1218, 948),
             "socket": (1244, 772, 1430, 948), "artifact": "amber_crystal", "x0": [-0.75, 0.28, 0, 15.0, 2.6, 0, 0]},
}
# reference door region in the OPEN crop (drawn hinged on the right: production rule overrides) -> excluded
OPEN_DOOR_EXCLUDE = {"oak": (285, 85, 400, 310), "iron": (290, 85, 388, 300), "root": (300, 85, 428, 318)}


def shaders():
    S = dict(sh.SHADERS)
    S["limestone_fine"] = lambda c: sh.limestone(c, base=sh.C(166, 150, 130), light=sh.C(204, 192, 174), dark=sh.C(112, 98, 84))
    return S


def open_pose(A):
    pk.set_static_pose(A, {"door": {"rot": (0, 0, -math.radians(ck.OPEN_DEG))}, "latch": {"loc": (-0.12, 0, 0)}})


def closed_pose(A):
    pk.set_static_pose(A, {"door": {"rot": (0, 0, 0)}, "latch": {"loc": (0, 0, 0)}})


def import_artifact(fam, variant=1):
    """Import the artifact GLB (built by build_lf_artifacts.py) and return its v<variant> LOD0 mesh."""
    glb = paths.runtime(pk.GROUP, f"lf_artifact_{fam}.glb")
    if not os.path.exists(glb):
        return None
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=glb)
    new = [o for o in bpy.data.objects if o not in before]
    keep = None
    for o in new:
        if o.name.startswith(f"lf_artifact_{fam}_v{variant}_LOD0"):
            keep = o
    for o in new:
        if o is not keep:
            bpy.data.objects.remove(o, do_unlink=True)
    if keep is not None:
        keep.parent = None
        keep.matrix_world = pk.Matrix.Identity(4) if hasattr(pk, "Matrix") else keep.matrix_world
    return keep


def run(asset_id, build_fn, hinge, latch, sock, kind, door, front_y, interior, clear_h, ref_key):
    it = qa.iteration()
    pre = f"iter{it:02d}_"
    core.reset()
    spec = ck.node_spec(asset_id, hinge, latch, sock)
    A = pk.Asset(asset_id, spec)
    A.dirt_scale = 1.0
    A.compile(build_fn)
    # keyhole socket collapsed by default (client enables it for bone-key sites)
    pk.pack_atlas(A.lod0_objects(), margin=0.002, shape="CONCAVE")
    pk.transfer_atlas_uv(A)
    # markers
    pk.marker(A, "key_slot", sock, "socket_core")
    pk.marker(A, "key_slot_keyhole", sock, "keyhole_core")
    pk.marker(A, "hinge_axis_bottom", (hinge[0], hinge[1], 0.0), "root")
    pk.marker(A, "hinge_axis_top", (hinge[0], hinge[1], 2.5), "root")
    corridor = ck.corridor_points(door[0], door[1], front_y, door[2])
    for i, c in enumerate(corridor):
        pk.marker(A, f"exit_corridor_{i}", c, "root")
    R = REF[ref_key]
    cams_path = os.path.join(paths.ensure(paths.QA_COMPARE, "props_cams"), "cage_cams.json")
    cams = qa.load_cams(cams_path)
    A.pivots["keyhole"]["rest_scale"] = (0.0, 0.0, 0.0)   # applied by rest_pose() at export
    # ---------------- camera fits (closed: all; open: static frame only, drawn door excluded)
    fits = {}
    for state in ("closed", "open"):
        img, m = qa.crop_and_mask(IMG, R[state], tol=3)
        if state == "open":
            x0_, y0_, x1_, y1_ = OPEN_DOOR_EXCLUDE[ref_key]
            m[y0_:y1_, x0_:x1_] = False
            objs = [A.meshes[0]["root"]]
        else:
            objs = A.lod0_objects()
        tris = pk.world_triangles(objs)
        c = tris.reshape(-1, 3).mean(0)
        key = f"{asset_id}:{state}"
        if key in cams and not qa.flag("--refit"):
            start = np.array(cams[key])
            x, sc = pk.fit_camera(tris, m, start, fixed=(2,), iters=1)
        else:
            start = np.array(list(cams.get(f"{asset_id}:closed", R["x0"] + list(c)))) if state == "open" else np.array(R["x0"] + list(c))
            x, sc = pk.fit_camera(tris, m, start, fixed=(2,), iters=2)
        cams[key] = [float(a) for a in x]
        H, W = m.shape
        fits[state] = (img, m, pk.cam_from_params(x, W, H), sc)
        print(f"[cage] {asset_id} {state} fit IoU(filled) {sc:.3f}")
    qa.save_cams(cams_path, cams)
    # ---------------- projection + relief + textures
    allobj = A.lod0_objects()
    static = [A.meshes[0]["root"]]
    specs = [pp.ViewSpec("closed", fits["closed"][0], fits["closed"][1], allobj, "persp", cam=fits["closed"][2],
                         weight=1.0, erode=0, delight=0.3, min_facing=0.15, depth_eps=0.03),
             pp.ViewSpec("open", fits["open"][0], fits["open"][1], static, "persp", cam=fits["open"][2],
                         pose=lambda: open_pose(A), unpose=lambda: closed_pose(A), weight=0.8, erode=0, delight=0.3,
                         min_facing=0.15, depth_eps=0.03)]
    files, info = pp.paint_relief_textures(A, shaders(), specs, size=2048, height_gain=0.03,
                                           sizes={"base": 2048, "orm": 1024, "normal": 2048}, relief_levels=2,
                                           ao_distance=0.35, ao_strength=0.6, edge_fade_m=0.01, samples=8,
                                           paint_alpha_w=0.3)
    pk.make_material(A, files)
    # ---------------- clips
    ck.add_cage_clips(A, latch_travel=0.12)
    glb = paths.runtime(pk.GROUP, f"{asset_id}.glb")
    pk.export(A, glb)
    meta = ck.cage_meta(A, asset_id, kind, hinge, round(door[1] - door[0], 3), round(door[3], 3), sock, 0.12, corridor,
                        interior, clear_h,
                        ("Production rule: hinge on the LEFT jamb seen from outside (drawing's open view shows it on "
                         "the right - not followed), single door pivot, outward opening 95 deg. socket_keyhole_pivot is "
                         "scale 0 by default; for bone-key sites show it and hide socket_pivot."), glb,
                        extra={"projection": info, "camera_fit_iou": {k: round(v[3], 4) for k, v in fits.items()}})
    print("[cage] tris", meta["tris"])
    core.save_blend(paths.source(pk.GROUP, f"{asset_id}.blend"))
    if qa.flag("--noqa"):
        return A, meta
    # ---------------- QA renders
    art = import_artifact(R["artifact"], 1)
    if art is not None:
        e = bpy.data.objects["key_slot"]
        art.parent = e
        art.matrix_parent_inverse.identity()
        art.location = (0, 0, 0)
        art.rotation_euler = (0, 0, 0)
    pk.studio(engine="CYCLES", samples=40, key=3.6, fill=1.2, rim=1.2, ambient=0.9, bg=(0.88, 0.80, 0.70))
    for o in A.all_meshes():
        o.hide_render = True
    for o in A.lod0_objects():
        o.hide_render = False
    for nm in ("keyhole", "keyhole_core"):
        A.meshes[0][nm].hide_render = True
    if art is not None:
        art.hide_render = False
    res = {}
    for state in ("closed", "open"):
        img, m, cam, _ = fits[state]
        (open_pose if state == "open" else closed_pose)(A)
        pk.blender_camera(cam)
        rgba = pk.render_rgba(qa.out(asset_id, "_tmp.png"))
        mm = m.copy()
        res[state] = pk.compare_panels(img, rgba, mm, qa.out(asset_id, pre + f"{state}34.png"),
                                       f"{asset_id} {state} 3/4 (camera fitted)" + (" - drawn door hinge side ignored" if state == "open" else ""))
    closed_pose(A)
    # close-ups: hinge and socket, frontal camera vs the drawing insets
    from PIL import Image
    for nm, tgt, sz in (("hinge", (hinge[0] + 0.12, hinge[1], 0.12 + 0.42 + 0.02), 0.42), ("socket", (sock[0], sock[1], sock[2]), 0.36)):
        cam = {"R": np.array([[1.0, 0, 0], [0, 0, -1.0], [0, 1.0, 0]]), "f": 900.0, "cx": 300, "cy": 300, "W": 600, "H": 600}
        C = np.array(tgt) + np.array([0, -sz * 900 / 600 * 1.0, 0])
        cam["C"] = C
        cam["t"] = -cam["R"] @ C
        pk.blender_camera(cam)
        rgba = pk.render_rgba(qa.out(asset_id, "_tmp.png"))
        refimg = pk.ref_crop(IMG, R[nm])
        pk.side_by_side([refimg, rgba], [f"drawing {nm} inset", f"model {nm} close-up (frontal)"],
                        qa.out(asset_id, pre + f"closeup_{nm}.png"), height=420)
    core.write_json(qa.out(asset_id, pre + "metrics.json"), {k: {kk: v.get(kk) for kk in ("iou_filled", "iou_raw", "mean_abs_colour_error", "mean_rgb_ref", "mean_rgb_render")} for k, v in res.items()})
    print("[cage-qa]", asset_id, {k: (v.get("iou_filled"), v.get("iou_raw"), v.get("mean_abs_colour_error")) for k, v in res.items()})
    # clip videos (EEVEE) from the closed-view camera
    if not qa.flag("--noclips"):
        pk.blender_camera(fits["closed"][2])
        sc = bpy.context.scene
        for clip in ("lf_cage_unlock", "lf_cage_gate_open", "lf_cage_gate_settle"):
            out = paths.video(asset_id, f"{clip}.mp4")
            pk.render_clip_frames(A, clip, out, res=(fits["closed"][2]["W"] * 2, fits["closed"][2]["H"] * 2),
                                  engine="BLENDER_EEVEE", samples=16, hold=6)
            print("[clip]", out)
    return A, meta
