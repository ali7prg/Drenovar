"""Cage build + QA pipeline shared by build_lf_cage_wood/iron/root.py."""
import json
import math
import os
import re
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
# landmarks on the CLOSED drawing (Blender point -> crop pixel): corner post axes top/bottom, hinge post, apex
LANDMARKS = {
    "oak": [((-1.5, -1.5, 3.18), (122.5, 32.5)), ((-1.5, -1.5, 0.58), (122.5, 257.5)), ((1.5, -1.5, 3.18), (334, 55)),
            ((1.5, -1.5, 0.58), (334, 250)), ((-1.5, 1.5, 3.18), (23.5, 65)), ((-1.5, 1.5, 0.58), (23.5, 250)),
            ((-0.33, -1.5, 0.0), (202.5, 305)), ((-0.33, -1.5, 2.66), (202.5, 87.5)), ((0.0, 0.0, 4.32), (195, 10))],
    "iron": [((-1.48, -1.48, 2.97), (127.5, 37.5)), ((-1.48, -1.48, 3.35), (124, 11)), ((-1.48, -1.48, 0.30), (127.5, 280)),
             ((1.48, -1.48, 2.97), (322.5, 52.5)), ((1.48, -1.48, 0.30), (322.5, 265)), ((-1.48, 1.48, 2.97), (17.5, 65)),
             ((-1.48, 1.48, 0.30), (17.5, 260)), ((1.48, 1.48, 3.35), (181, 11)), ((-0.42, -1.48, 0.30), (185, 272))],
    "root": [((-1.48, -1.48, 2.5), (165, 50)), ((-1.48, -1.48, 0.05), (165, 300)), ((1.48, -1.48, 2.5), (362, 65)),
             ((1.48, -1.48, 0.05), (362, 295)), ((-1.48, 1.48, 2.5), (40, 75)), ((-1.48, 1.48, 0.05), (40, 280)),
             ((-0.36, -1.48, 0.0), (240, 300)), ((-0.36, -1.48, 2.32), (240, 117)), ((1.30, -1.48, 0.0), (345, 300))],
}
# high-res insets: (box, crop px of the anchor, px per metre, parts prefixes, anchor key)
INSETS = {
    "oak": [((60, 772, 270, 948), (88.5, 99.5), 422.0, "hinge"), ((294, 772, 472, 948), (101.7, 90.0), 516.0, "socket")],
    "iron": [((550, 772, 710, 948), (69.5, 93.5), 458.0, "hinge"), ((784, 772, 960, 948), (93.0, 87.0), 596.0, "socket")],
    "root": [((1037, 772, 1218, 948), (64.0, 95.0), 391.0, "hinge"), ((1244, 772, 1430, 948), (71.7, 89.0), 640.0, "socket")],
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


def wire_overlay(A, cam, img, out_png, pose=None, lod=2):
    """Reference with the model's LOD2 edges projected by the fitted camera (alignment check)."""
    import cv2
    from frlib import core as _core
    im = (np.clip(img, 0, 1) * 255).astype(np.uint8).copy()
    cols = [(255, 60, 60), (60, 200, 255), (255, 220, 40), (120, 255, 120), (255, 120, 255), (255, 255, 255), (200, 160, 255)]
    for k, (node, o) in enumerate(A.meshes[lod].items()):
        if o.hide_render and node in ("keyhole", "keyhole_core"):
            continue
        me = o.data
        M = np.array(o.matrix_world)
        co = np.array([v.co[:] for v in me.vertices])
        P = co @ M[:3, :3].T + M[:3, 3]
        uv, z = pk.project_points(P, cam)
        for e in me.edges:
            a, b = e.vertices
            p0, p1 = uv[a], uv[b]
            cv2.line(im, (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])), cols[k % len(cols)], 1, cv2.LINE_AA)
    big = cv2.resize(im, (im.shape[1] * 2, im.shape[0] * 2), interpolation=cv2.INTER_NEAREST)
    _core.save_rgba(out_png, big / 255.0)


def run(asset_id, build_fn, hinge, latch, sock, kind, door, front_y, interior, clear_h, ref_key):
    it = qa.iteration()
    pre = f"iter{it:02d}_"
    core.reset()
    spec = ck.node_spec(asset_id, hinge, latch, sock)
    A = pk.Asset(asset_id, spec)
    A.dirt_scale = 1.0
    A.compile(build_fn)
    # keyhole socket collapsed by default (client enables it for bone-key sites)
    # thin iron members are not projected (mis-registration would paint bars/background onto them): procedural iron
    for nm in A.part_ids:
        if re.match(r"(bars_|rails_|arches_|bar_tips_|tracery_|door_bars|knots_|fleurs_|ridge|latch_keeper)", nm):
            A.part_meta.setdefault(nm, {})["no_paint"] = 1
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
        H0, W0 = m.shape
        if state == "closed":
            LM = LANDMARKS[ref_key]
            P3 = [a for a, b in LM]
            p2 = [b for a, b in LM]
            xs, err = pk.fit_camera_points(P3, p2, W0, H0, np.array(R["x0"] + list(c)), fixed=(2,))
            x, sc = pk.fit_camera(tris, m, xs, fixed=(2,), iters=1, landmarks=(P3, p2), lam=0.004)
            e2 = np.linalg.norm(pk.landmark_errors(x, P3, p2, W0, H0), axis=1)
            print(f"[cage] {asset_id} landmark residuals after refinement (px): {np.round(e2, 1).tolist()}")
            core.write_json(qa.out(asset_id, pre + "landmarks.json"), {"points": [list(a) for a in P3], "pixels": [list(b) for b in p2],
                                                                      "residual_px": [round(float(v), 2) for v in e2]})
        else:
            start = np.array(cams.get(f"{asset_id}:closed"))
            x, sc = pk.fit_camera(tris, m, start, fixed=(0, 1, 2), iters=1)
        cams[key] = [float(a) for a in x]
        H, W = m.shape
        fits[state] = (img, m, pk.cam_from_params(x, W, H), sc)
        print(f"[cage] {asset_id} {state} fit IoU(filled) {sc:.3f}")
    qa.save_cams(cams_path, cams)
    # ---------------- projection + relief + textures
    allobj = A.lod0_objects()
    static = [A.meshes[0]["root"]]
    specs = [pp.ViewSpec("closed", fits["closed"][0], fits["closed"][1], allobj, "persp", cam=fits["closed"][2],
                         weight=1.0, erode=1, delight=0.3, min_facing=0.15, depth_eps=0.03),
             pp.ViewSpec("open", fits["open"][0], fits["open"][1], static, "persp", cam=fits["open"][2],
                         pose=lambda: open_pose(A), unpose=lambda: closed_pose(A), weight=0.8, erode=1, delight=0.3,
                         min_facing=0.15, depth_eps=0.03)]
    from frlib import refs as _refs
    for box, cpx, ppm, what in INSETS[ref_key]:
        img = pk.ref_crop(IMG, box)
        H_, W_ = img.shape[:2]
        full = np.ones((H_, W_), bool)
        pm = full.copy()
        pm[:5] = pm[-5:] = False
        pm[:, :5] = pm[:, -5:] = False
        if what == "hinge":
            zs = getattr(build_fn, "hinge_z", None) or [0.54, 2.04]
            anchors = [(f"hinge{i}_", (hinge[0], hinge[1], z)) for i, z in enumerate(zs)]
            objs_i = [A.meshes[0]["root"], A.meshes[0]["door"]]
        else:
            anchors = [("sock_native_plate", tuple(sock)), ("sock_native_loop", tuple(sock)), ("sock_native_rivets", tuple(sock))]
            objs_i = [A.meshes[0]["socket"]]
        for pref, anc in anchors:
            v = _refs.View(name=f"inset_{what}", image=img, mask=full, d=np.array([0.0, 1.0, 0.0]), ppm=ppm, ax=cpx[0], ay=cpx[1],
                           anchor=np.asarray(anc, float))
            specs.append(pp.ViewSpec(f"inset_{what}_{pref}", img, full, objs_i, "ortho", view=v, weight=4.0, erode=0,
                                     delight=0.15, min_facing=0.05, parts=[pref], paint_mask=pm, height=True))
    files, info = pp.paint_relief_textures(A, shaders(), specs, size=2048, height_gain=0.03,
                                           sizes={"base": 2048, "orm": 1024, "normal": 2048}, relief_levels=2,
                                           ao_distance=0.35, ao_strength=0.6, edge_fade_m=0.01, samples=8,
                                           paint_alpha_w=0.3, gate=2.2)
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
        wire_overlay(A, cam, img, qa.out(asset_id, pre + f"{state}34_wire.png"))
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
