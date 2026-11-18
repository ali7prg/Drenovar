"""Landmarks v2 driver: painted art/06 textures (lm_paint_textures.py) on the landmark geometry built from the
art/06 orthographic insets (landmarks/landmarks.py), camera fitted to each art/06 main view by silhouette IoU,
QA in forest_rescue/qa/compare/<asset>/v2_iterNN_*.

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/paint3d/build_landmarks_v2.py <names|all>
        [--iter N]
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "landmarks"))
sys.path.insert(0, os.path.join(HERE, "..", "forest"))
import pblend  # noqa: E402  (frlib path)
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from frlib import core, paths, refs, render as frr  # noqa: E402
import fqa  # noqa: E402
import build_landmarks as BL  # noqa: E402

IT = 1
BUDGET = {0: 6000, 1: 1500, 2: 400}
_orig_kit_object = BL.kit_object


def kit_object_budget(name, kit):
    """Landmark budgets (LOD0 <= 6k, LOD1 <= 1.5k, LOD2 <= 400 incl. extra objects): collapse-decimate."""
    o = _orig_kit_object(name, kit)
    lod = int(name[-1]) if name[-1].isdigit() else 0
    target = BUDGET[lod] - (180 if "camp_props" in name and lod > 0 else (300 if "camp_props" in name else 0))
    n = core.tri_count(o)
    if n > target:
        m = o.modifiers.new("dec", "DECIMATE")
        m.ratio = max(0.02, target / n * 0.98)
        m.use_collapse_triangulate = True
        core.select_only([o])
        bpy.ops.object.modifier_apply(modifier="dec")
    return o


BL.kit_object = kit_object_budget

# LOD0 masonry with chamfered blocks (44 tris/block) exceeds the 6k landmark budget for the bridge and the ruin:
# use plain blocks there instead of collapse-decimating (decimation melts the block edges and UVs)
import landmarks as _L  # noqa: E402
_orig_kit_init = _L.Kit.__init__
NO_BEVEL = set()


def _kit_init(self, seed=0, bevel=False):
    _orig_kit_init(self, seed=seed, bevel=bevel and not NO_BEVEL)


_L.Kit.__init__ = _kit_init


def v2_path(asset, it, name):
    return paths.compare(asset, f"v2_iter{it:02d}_{name}.png")


fqa.iter_path = v2_path


def fit_camera(asset, objs, box, cam0, it):
    """Perspective camera (location, look-at, lens) maximising the silhouette IoU against the art/06 main view."""
    import cv2
    from scipy.optimize import minimize
    ref = refs.crop(refs.load(BL.SHEET), box)
    bg = refs.border_color(ref)
    m_ref = refs.silhouette(ref, bg=bg, thresh=0.12, keep="all", min_area=60, fill_holes=400)
    W, H = box[2] - box[0], box[3] - box[1]
    sc = 0.4
    w2, h2 = int(W * sc), int(H * sc)
    m_small = cv2.resize(m_ref.astype(np.uint8), (w2, h2), interpolation=cv2.INTER_NEAREST).astype(bool)
    fqa.only(objs)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "FLAT"
    scene.display.shading.color_type = "SINGLE"
    scene.render.film_transparent = True
    loc0, look0, lens0 = cam0
    p0 = np.r_[loc0, look0, lens0]

    def render_mask(p):
        cam = frr.perspective_camera(tuple(p[:3]), tuple(p[3:6]), lens=float(p[6]), res=(w2, h2))
        rgba = frr.render_rgba()
        return rgba[..., 3] > 0.5

    def loss(p):
        rm = render_mask(p)
        inter = (rm & m_small).sum()
        uni = (rm | m_small).sum()
        return 1.0 - inter / max(uni, 1)

    best = minimize(loss, p0, method="Nelder-Mead", options=dict(maxfev=90, xatol=0.05, fatol=0.002,
                                                                  initial_simplex=None))
    p = best.x
    iou = 1.0 - best.fun
    return (tuple(p[:3]), tuple(p[3:6]), float(p[6])), iou, m_ref


def three_quarter_fitted(asset, it, objs, box, cam, m_ref):
    loc, look, lens = cam
    fqa.studio(24)
    fqa.only(objs)
    frr.perspective_camera(loc, look, lens=lens, res=(box[2] - box[0], box[3] - box[1]))
    rgba = frr.render_rgba()
    ref = refs.crop(refs.load(BL.SHEET), box)
    bg = np.array(refs.border_color(ref))
    m = pblend.compare_sheet(ref.astype(np.float64), m_ref, rgba, bg, v2_path(asset, it, "threequarter_fitted"),
                             f"{asset} vs art/06 main view (camera fitted by silhouette IoU) iter {it}")
    return m


def run(name, it, fit=True):
    asset = f"lf_env_{name}"
    NO_BEVEL.clear()
    if name in ("bridge27m", "ruined_watchpost"):
        NO_BEVEL.add(name)
    BL.build(name, it, export=True, qa=True)
    if not fit:
        # metrics sheet at the hand-matched art/06 camera (painted-light QA material)
        objs = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(asset) and o.name.endswith("LOD0")]
        box = BL.REFS[name]["main"]
        ref = refs.crop(refs.load(BL.SHEET), box)
        bg = refs.border_color(ref)
        m_ref = refs.silhouette(ref, bg=bg, thresh=0.12, keep="all", min_area=60, fill_holes=400)
        pblend.use_painted(objs, 0.35)
        met = three_quarter_fitted(asset, it, objs, box, BL.CAMS[name], m_ref)
        met["camera"] = dict(location=list(BL.CAMS[name][0]), look_at=list(BL.CAMS[name][1]), lens_mm=BL.CAMS[name][2],
                             note="hand-matched to the art/06 main view (reference mask includes the painted ground base)")
        core.write_json(v2_path(asset, it, "threequarter_fitted").replace(".png", ".json"), met)
        print(f"[{asset}] art/06 view: IoU {met['iou']:.3f} colour err {met['colour_err']:.3f} SSIM {met['ssim']:.3f}",
              flush=True)
        return met
    # fitted camera comparison (painted-light QA material on the exported LOD0)
    if name not in BL.REFS:
        return None
    objs = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(asset) and o.name.endswith("LOD0")]
    cam, iou, m_ref = fit_camera(asset, objs, BL.REFS[name]["main"], BL.CAMS[name], it)
    pblend.use_painted(objs, 0.35)
    met = three_quarter_fitted(asset, it, objs, BL.REFS[name]["main"], cam, m_ref)
    met["camera"] = dict(location=[round(v, 3) for v in cam[0]], look_at=[round(v, 3) for v in cam[1]],
                         lens_mm=round(cam[2], 2), fit_iou=round(iou, 4))
    core.write_json(v2_path(asset, it, "threequarter_fitted").replace(".png", ".json"), met)
    print(f"[{asset}] fitted camera {met['camera']} -> {met['iou']:.3f} / err {met['colour_err']:.3f}", flush=True)
    return met


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    names = args[0]
    it = int(args[args.index("--iter") + 1]) if "--iter" in args else 1
    alln = ["bridge27m", "hunter_shelter", "quarry_mine", "ruined_watchpost", "standing_stones", "camp_props"]
    small = ["stone_wall", "signpost", "rope_coil", "lantern", "platform"]
    lst = alln + small if names == "all" else names.split(",")
    for n in lst:
        if n in small:
            BL.build(n, it, export=True, qa=False)
        else:
            run(n, it, fit="--fit" in args)
