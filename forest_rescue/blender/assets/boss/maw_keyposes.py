"""Pose the rig like each panel of art/05 and render side by side (+ bbox-aligned silhouette IoU)."""
import math

import bpy
import numpy as np
from mathutils import Vector

import maw_anim as A
import maw_common as C
import maw_refs as R
from frlib import core, render
from maw_pose import Poser

AID = C.ASSET_ID

# panel -> (clip, time s, client root yaw deg, camera azimuth deg (0 = left side view), elevation deg)
PANELS = {
    "walk_left_contact": ("lf_boss_walk", 0.0, 0, 0, 6),
    "walk_down_passing": ("lf_boss_walk", 0.30, 0, 0, 6),
    "walk_right_contact": ("lf_boss_walk", 0.80, 0, 0, 6),
    "walk_up_passing": ("lf_boss_walk", 1.12, 0, 0, 6),
    "turn_anticipation": ("lf_boss_turn_left", 0.32, None, 8, 8),
    "turn_planted": ("lf_boss_turn_left", 0.80, None, 8, 8),
    "bite_windup": ("lf_boss_jaw_arc", 2.0, 0, 6, 6),
    "bite_forward": ("lf_boss_jaw_arc", 2.62, 0, 6, 6),
    "roar": ("lf_boss_phase_roar", 1.35, 0, 10, 6),
    "tail_sweep_telegraph": ("lf_boss_tail_sweep", 2.6, 0, 38, 10),
    "tail_sweep_active": ("lf_boss_tail_sweep", 3.4, 0, 10, 8),
    "death_rest": ("lf_boss_death", 5.2, 0, 0, 10),
}


def mask_of(rgba):
    return rgba[..., 3] > 0.5


def aligned_iou(ref_mask, ren_mask):
    import cv2
    ys, xs = np.nonzero(ref_mask)
    yr, xr = np.nonzero(ren_mask)
    if len(ys) == 0 or len(yr) == 0:
        return 0.0
    h_ref = ys.max() - ys.min() + 1
    w_ref = xs.max() - xs.min() + 1
    crop = ren_mask[yr.min():yr.max() + 1, xr.min():xr.max() + 1].astype(np.uint8)
    # scale to the reference bbox (uniform scale on the larger extent ratio)
    s = min(h_ref / crop.shape[0], w_ref / crop.shape[1])
    sc = cv2.resize(crop, (max(1, int(crop.shape[1] * s)), max(1, int(crop.shape[0] * s))),
                    interpolation=cv2.INTER_NEAREST).astype(bool)
    canvas = np.zeros_like(ref_mask)
    y0 = ys.max() + 1 - sc.shape[0]   # align ground (bottom) and horizontal centre
    x0 = int((xs.min() + xs.max()) / 2 - sc.shape[1] / 2)
    y0, x0 = max(0, y0), max(0, x0)
    hh = min(sc.shape[0], canvas.shape[0] - y0)
    ww = min(sc.shape[1], canvas.shape[1] - x0)
    canvas[y0:y0 + hh, x0:x0 + ww] = sc[:hh, :ww]
    inter = (canvas & ref_mask).sum()
    return float(inter) / max(float((canvas | ref_mask).sum()), 1.0)


def run(iter_tag):
    arm = bpy.data.objects[f"{AID}_rig"]
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = not o.name.endswith("_LOD0")
    render.studio(bg=(0.66, 0.66, 0.66), engine="CYCLES", samples=24, key_dir=(-0.45, -0.55, 0.70))
    ps = Poser(arm)
    results = {}
    sheet = []
    for name, (clip, t, yaw, az, el) in PANELS.items():
        L = A.CLIPS[clip](t)
        A.apply_layer(ps, L)
        ps.apply()
        if yaw is None:
            D = A.MANIFEST[clip][0]
            yaw = 90.0 * A.ss(t / D)
        arm.rotation_euler = (0, 0, math.radians(yaw))
        bpy.context.view_layer.update()
        panel = R.keypose_panel(name)
        H, W = panel.shape[:2]
        a, e = math.radians(az), math.radians(el)
        target = Vector((0, 0.3, 1.7))
        d = Vector((math.cos(a) * math.cos(e), -math.sin(a) * math.cos(e), math.sin(e)))
        cam = render.perspective_camera(tuple(target + d * 30), tuple(target), lens=50, res=(W, H))
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = 12.5
        rgba = render.render_rgba()
        ref_mask = R.keypose_mask(panel)
        iou = aligned_iou(ref_mask, mask_of(rgba))
        results[name] = {"clip": clip, "time_s": t, "aligned_iou": round(iou, 3)}
        png = C.qa_compare(f"iter{iter_tag}_keypose_{name}.png")
        render.side_by_side([panel, rgba], [f"art/05 {name}", f"{clip} @ {t:.2f}s  bboxIoU {iou:.2f}"], png,
                            height=300)
        sheet.append(png)
        arm.rotation_euler = (0, 0, 0)
    # combined sheet (2 columns)
    from PIL import Image
    ims = [Image.open(p) for p in sheet]
    w = max(i.size[0] for i in ims)
    h = ims[0].size[1]
    out = Image.new("RGB", (w * 2, h * 6), (30, 30, 30))
    for i, im in enumerate(ims):
        out.paste(im, ((i % 2) * w, (i // 2) * h))
    out.save(C.qa_compare(f"iter{iter_tag}_keyposes_sheet.png"))
    core.write_json(C.qa_compare(f"iter{iter_tag}_keyposes.json"), results)
    print("[keyposes]", results, flush=True)
    return results
