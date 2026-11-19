"""QA: per-view comparison sheets [reference | render | IoU diff | colour error heat] + heads5 (Blender).

blender-python mv2_qa.py <blend> [--what compare,heads5]
Renders are flat albedo (Workbench FLAT/TEXTURE): the texture carries the painted light exactly as the
game's painted shader does with paintedLightMix=0; Godot sheets show the real in-game shading.
Per-view sheet poses: left = right leg stepped back + right arm forward as drawn (the side view's back
far leg and far arm); front / rear / head = rest pose (head: jaw opened by the solved angle).
"""
import json
import math
import os
import sys

import bpy
import cv2
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mv2_common as C  # noqa: E402
import mv2_cams as CM  # noqa: E402
import mv2_pose as PO  # noqa: E402
import mv2_refs as R  # noqa: E402
from frlib import core, render  # noqa: E402

ARM = C.ASSET_ID + "_rig"
HIDE = ("maw_high", "maw_bake_src")


def setup_flat():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "FLAT"
    sh.color_type = "TEXTURE"
    sh.show_cavity = False
    sh.show_shadows = False
    sh.show_specular_highlight = False
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.color_mode = "RGBA"
    sh.show_backface_culling = True
    for m in bpy.data.materials:
        if m.node_tree is None:
            continue
        for n in m.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image is not None and n.image.colorspace_settings.name == "sRGB":
                m.node_tree.nodes.active = n
    for o in bpy.data.objects:
        if o.name in HIDE or o.name.startswith(("ik_", "pole_")):
            o.hide_render = True
        if o.type == "MESH" and "_LOD1" in o.name or "_LOD2" in o.name:
            o.hide_render = True


def persp_camera_from(cam, name="qa_pcam"):
    W, H = cam.size
    cd = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cd.type = "PERSP"
    cd.sensor_fit = "HORIZONTAL"
    cd.sensor_width = 36.0
    cd.lens = cam.K[0, 0] / W * 36.0
    cd.shift_x = -(cam.K[0, 2] - W / 2.0) / W
    cd.shift_y = (cam.K[1, 2] - H / 2.0) / W
    cd.clip_start = 0.05
    cd.clip_end = 1000
    ob = bpy.data.objects.get(name) or core.link(bpy.data.objects.new(name, cd))
    Rcw = cam.R.T @ np.diag([1.0, -1.0, -1.0])
    M = np.eye(4)
    M[:3, :3] = Rcw
    M[:3, 3] = cam.C
    ob.matrix_world = Matrix(M.tolist())
    sc = bpy.context.scene
    sc.camera = ob
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.resolution_percentage = 100
    return ob


def left_pose(ps, sk, prm):
    """Turnaround (left-view) pose: the far right leg stepped back and the far arm forward, as painted."""
    ay, az, by, arm = prm
    ps.two_bone("thigh_R", "shin_R", np.array([-0.68, ay, az]), pole_dir=(0, -1, 0))
    ps.aim("foot_R", np.array([-0.68, by, 0.17]) - ps.head("foot_R"))
    for t in ("toe2a_R", "toe3a_R", "toe4a_R", "toe2b_R", "toe3b_R", "toe4b_R", "hallux_R"):
        ps.set_world_rot(t, sk.rest[t][:3, :3])
    ps.rot_world_axis("upperarm_R", (1, 0, 0), -arm)
    ps.rot_world_axis("forearm_R", (1, 0, 0), -10)


def fit_left_pose(arm):
    """Grid-search the far leg/arm so the posed silhouette matches the painted left view (numpy LBS)."""
    body = bpy.data.objects["maw_body"]
    V, tris, _uv, _n = core.mesh_arrays(body, evaluated=False)
    wz = np.load(C.cache("maw2_weights_lod0.npz"))
    names = [str(n) for n in wz["names"]]
    W = wz["W"].astype(np.float64)
    sk = PO.Skeleton(arm)
    view = R.side_view(corrected=True, colour=False)
    H, Wd = view.mask.shape
    Vh = np.concatenate([V, np.ones((len(V), 1))], 1)
    inv = {n: np.linalg.inv(sk.rest[n]) for n in names}
    best = None
    for ay in (1.20, 1.30, 1.40, 1.50):
        for az in (0.62, 0.72, 0.82):
            for by in (0.95, 1.07, 1.19):
                for armd in (20.0, 32.0):
                    ps = PO.Pose(sk)
                    left_pose(ps, sk, (ay, az, by, armd))
                    M = ps.fk()
                    Vp = np.zeros((len(V), 3))
                    for j, n in enumerate(names):
                        w = W[:, j]
                        nz = w > 0
                        if nz.any():
                            Vp[nz] += w[nz, None] * (Vh[nz] @ (M[n] @ inv[n]).T)[:, :3]
                    u, v, _ = view.project(Vp)
                    pts = np.stack([u, v], 1)[tris]
                    m = np.zeros((H, Wd), np.uint8)
                    cv2.fillPoly(m, np.round(pts * 8).astype(np.int32), 1, shift=3)
                    mm = m > 0
                    iou = (mm & view.mask).sum() / max((mm | view.mask).sum(), 1)
                    if best is None or iou > best[0]:
                        best = (float(iou), (ay, az, by, armd))
    core.write_json(C.cache("left_pose.json"), {"iou_body_only": best[0], "params": best[1]})
    return best


def sheet_pose(arm, which):
    sk = PO.Skeleton(arm)
    ps = PO.Pose(sk)
    if which == "left":
        prm = json.load(open(C.cache("left_pose.json")))["params"] if os.path.exists(C.cache("left_pose.json")) \
            else (1.38, 0.68, 1.12, 28.0)
        left_pose(ps, sk, prm)
    elif which == "head":
        info = json.load(open(C.cache("head_cam.json")))
        ps.rot_world_axis("jaw", (1, 0, 0), float(info["jaw_open_deg"]))
    ps.to_blender(arm)
    bpy.context.view_layer.update()


def colour_heat(ref, comp, both):
    err = np.abs(comp - ref).mean(2)
    heat = np.zeros_like(ref)
    e = np.clip(err / 0.3, 0, 1)
    heat[..., 0] = np.clip(e * 2, 0, 1)
    heat[..., 1] = np.clip(e * 2 - 1, 0, 1)
    heat[..., 2] = np.clip(0.4 - e, 0, 1)
    heat[~both] = ref[~both] * 0.25 + 0.55
    return heat, float(err[both].mean()) if both.any() else 1.0


def compare_sheet(name, ref, refmask, rgba, out_png, title):
    H, W = ref.shape[:2]
    if rgba.shape[:2] != (H, W):
        rgba = cv2.resize(rgba, (W, H), interpolation=cv2.INTER_AREA)
    bgc = np.median(ref[~refmask], axis=0)
    a = rgba[..., 3:4]
    comp = rgba[..., :3] * a + bgc[None, None, :] * (1 - a)
    rmask = rgba[..., 3] > 0.5
    iou = render.iou(refmask, rmask)
    diff = np.repeat((ref.mean(axis=2, keepdims=True) * 0.5 + 0.35), 3, axis=2)
    both = refmask & rmask
    diff[both] = diff[both] * 0.5 + np.array([0.15, 0.55, 0.15]) * 0.5
    diff[refmask & ~rmask] = (0.85, 0.15, 0.15)
    diff[~refmask & rmask] = (0.15, 0.3, 0.9)
    heat, cerr = colour_heat(ref, comp, both)
    panels = []
    for img, txt in ((ref, "reference"), (comp, "render (albedo, painted light)"), (diff, f"IoU {iou:.3f}"),
                     (heat, f"colour err {cerr:.3f}")):
        panels.append(render._label((np.clip(img, 0, 1) * 255).astype(np.uint8), txt))
    sheet = np.concatenate(panels, axis=1)
    top = render._label(np.full((26, sheet.shape[1], 3), 28, np.uint8), title)
    core.save_rgba(out_png, np.concatenate([top, sheet], axis=0) / 255.0)
    m = {"view": name, "iou": round(iou, 4), "mean_abs_colour_error": round(cerr, 4),
         "ref_pixels": int(refmask.sum()), "render_pixels": int(rmask.sum())}
    core.write_json(out_png.replace(".png", ".json"), m)
    return m


def compare_all(tag):
    arm = bpy.data.objects[ARM]
    print("LEFTPOSE", fit_left_pose(arm))
    setup_flat()
    res = {}
    for key, view in (("left", R.side_view(corrected=True, colour=True)), ("left_raw", R.side_view(corrected=False)),
                      ("front", R.front_view(corrected=True)), ("front_raw", R.front_view(corrected=False))):
        sheet_pose(arm, "left" if key.startswith("left") else "rest")
        render.camera_for_view(view)
        rgba = render.render_rgba()
        res[key] = compare_sheet(key, view.image, view.mask, rgba, C.qa(f"{key}.png"),
                                 f"lf_boss_ancient_maw v2 iter{C.ITER} {key}")
    # rear three-quarter through the solved camera
    rinfo = json.load(open(C.cache("rear_cam.json")))
    crop, mask = R.rear_mask()
    cj = rinfo["camera"]
    rear = CM.PerspCam("rear34", crop, mask, cj["K"], cj["rvec"], cj["tvec"])
    sheet_pose(arm, "rest")
    persp_camera_from(rear)
    rgba = render.render_rgba()
    res["rear34"] = compare_sheet("rear34", crop, mask, rgba, C.qa("rear34.png"),
                                  f"lf_boss_ancient_maw v2 iter{C.ITER} rear 3/4 (solved camera)")
    res["rear34"]["camera"] = {k: rinfo[k] for k in rinfo if k != "camera"}
    # head close-up through the solved camera, jaw opened by the solved angle
    hinfo = json.load(open(C.cache("head_cam.json")))
    hcrop, hmask = R.head_crop()
    hj = hinfo["camera"]
    hcam = CM.PerspCam("head", hcrop, hmask, hj["K"], hj["rvec"], hj["tvec"])
    sheet_pose(arm, "head")
    persp_camera_from(hcam)
    rgba = render.render_rgba()
    res["head_closeup"] = compare_sheet("head_closeup", hcrop, hmask, rgba, C.qa("head_closeup.png"),
                                        f"lf_boss_ancient_maw v2 iter{C.ITER} head close-up (solvePnP camera, jaw "
                                        f"{hinfo['jaw_open_deg']:.0f} deg)")
    res["head_closeup"]["camera"] = {k: hinfo[k] for k in hinfo if k != "camera"}
    sheet_pose(arm, "rest")
    core.write_json(C.qa("metrics.json"), res)
    return res


def heads5(tag, lod_suffix=""):
    """Head at 5 angles (front, 3/4 L, 3/4 R, profile L, profile R): 2 eyes, scar only on the LEFT."""
    setup_flat()
    sc = bpy.context.scene
    imgs = []
    centre = np.array([0.0, -3.82, 3.02])
    for ang in (0, -45, 45, -90, 90):
        a = math.radians(ang)
        # creature faces -Y; angle 0 = camera in front; negative = camera on the creature's left (+X)
        d = np.array([-math.sin(a), -math.cos(a), 0.18])
        loc = centre + d / np.linalg.norm(d) * 9.0
        render.perspective_camera(tuple(loc), tuple(centre), name="h5cam", res=(440, 400), ortho_scale=2.5)
        imgs.append(render.render_rgba())
    labels = ["front 0", "3/4 left (scar)", "3/4 right", "profile left (scar)", "profile right"]
    panels = []
    for img, lab in zip(imgs, labels):
        rgb = img[..., :3] * img[..., 3:4] + 0.93 * (1 - img[..., 3:4])
        u8 = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
        u8 = np.pad(u8, ((6, 6), (6, 6), (0, 0)), constant_values=40)
        panels.append(render._label(u8, lab, (12, 10)))
    core.save_rgba(C.qa(f"heads5_blender{lod_suffix}.png"), np.concatenate(panels, axis=1) / 255.0)


if __name__ == "__main__":
    args = sys.argv[1:]
    blend = args[0]
    what = args[args.index("--what") + 1].split(",") if "--what" in args else ["compare", "heads5"]
    bpy.ops.wm.open_mainfile(filepath=blend)
    if "compare" in what:
        print("METRICS", json.dumps(compare_all(C.ITER)))
    if "heads5" in what:
        heads5(C.ITER)
