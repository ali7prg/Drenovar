"""Re-run the painting comparison of a props v2 asset with its CURRENT runtime atlases (no rebuild,
no re-projection, no export): same solved cameras, same geometry/UV build, same QA material and
metrics as build_asset.py. Used to verify texture-only fixes (e.g. tools/fix_cage_top_textures.py).

    python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/props/v2/qa_recompare.py cage_iron [--iter 90]

Writes forest_rescue/qa/compare/<id>/v2_iter<NN>_<view>.png/.json and prints old vs new metrics.
"""
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pv2  # noqa: E402

import numpy as np  # noqa: E402
from frlib import core  # noqa: E402
import bl  # noqa: E402
import build_asset  # noqa: E402
from PIL import Image  # noqa: E402


def main(modname, it):
    M = importlib.import_module(modname)
    aid = M.ID
    core.reset()
    views = M.views()
    params, reps = pv2.solve_views(views, M.points, M.PARAMS, M.FREE, prior_sigma=getattr(M, "PRIOR", 0.25))
    params["_cams"] = {v.name: v.cam for v in views}
    if hasattr(M, "ground_poly"):
        for v in views:
            v.ground = M.ground_poly(params)
    A = pv2.Asset(aid, M.ATLAS)
    for lod in range(3):
        M.build(A, params, lod)
    glow = getattr(M, "GLOW", None)
    blank = bl.image_from_array(f"{aid}_c", np.full((8, 8, 3), 0.5))
    blank_n = bl.image_from_array(f"{aid}_n", np.full((8, 8, 3), (0.5, 0.5, 1.0)), "Non-Color")
    mats = {lod: build_asset.make_mats(aid, lod, blank, blank_n if lod == 0 else None, glow) for lod in range(3)}
    B = pv2.realize(A, mats)
    for lod in range(3):
        objs = [o for (l_, nm), o in B.objs.items() if l_ == lod]
        fixed = [B.finfo[(l_, nm)]["fixed"] for (l_, nm), o in B.objs.items() if l_ == lod]
        bl.atlas_uv(objs, fixed)
    # UV determinism check against the exported GLB (same UV layout = the atlas lines up).
    alb = np.asarray(Image.open(os.path.join(pv2.RT, f"{aid}_c.jpg")).convert("RGB"), dtype=np.float32) / 255.0
    nrm = np.asarray(Image.open(os.path.join(pv2.RT, f"{aid}_n.png")).convert("RGB"), dtype=np.float32) / 255.0
    build_asset.swap_images(mats[0]["atlas"], bl.image_from_array(f"{aid}_c", alb), bl.image_from_array(f"{aid}_n", nrm, "Non-Color"))
    bl.setup_render(16)
    meta = json.load(open(os.path.join(pv2.RT, f"{aid}.meta.json")))
    old = meta.get("qa", {}).get("views", {})
    result = {}
    for v in views:
        rgba = pv2.render_view(A, B, v, ss=2)
        ign = v.ignore()
        if getattr(v, "iou_ignore", None):
            pm = pv2.ignore_mask_from_parts(A, B, v, v.iou_ignore)
            if pm is not None:
                ign = pm if ign is None else (ign | pm)
        m = pv2.compare(v, rgba, pv2.qa_path(aid, it, v.name), f"{aid} v2 iter {it} (texture-only top-face fix): {v.title or v.name}", ignore=ign)
        o = old.get(v.name, {})
        result[v.name] = {"old": {k: o.get(k) for k in ("iou_raw", "iou_filled", "colour_err", "colour_err_core")},
                          "new": {k: m[k] for k in ("iou_raw", "iou_filled", "colour_err", "colour_err_core")}}
        print(f"RECOMPARE {aid} {v.name} old {result[v.name]['old']} new {result[v.name]['new']}", flush=True)
    core.write_json(pv2.qa_path(aid, it, "recompare", "json"), result)


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], int(a[a.index("--iter") + 1]) if "--iter" in a else 90)
