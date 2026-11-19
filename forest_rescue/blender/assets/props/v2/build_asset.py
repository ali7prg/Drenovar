"""Props v2 driver: python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/props/v2/build_asset.py
<module> [--iter N] [--no-export] [--no-godot]

module: cage_oak | cage_iron | cage_root | mech_* | artifacts | supplies (python module in this folder exposing
ID, ATLAS, PARAMS, FREE, points(), views(), build(A, params, lod), SWATCHES, clips(A, B), meta(A, params)).
"""
import importlib
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pv2  # noqa: E402  (sets sys.path for frlib / landmarks v3 / paint3d / forest)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from frlib import core, paths  # noqa: E402
import bl  # noqa: E402


def make_mats(aid, lod, col, nrm, glow=None):
    nm = f"{aid}_mat" if lod == 0 else f"{aid}_lod{lod}_mat"
    mats = {"atlas": core.material(nm, base_tex=col, normal_tex=nrm, rough=0.84, metal=0.0, normal_strength=0.8)}
    if glow is not None:
        m = core.material(f"{aid}_glow", base=glow["base"], rough=0.35, emission=glow["emission"],
                          emission_strength=glow["strength"])
        mats["glow"] = m
    return mats


def swap_images(mat, col=None, nrm=None):
    for n in mat.node_tree.nodes:
        if n.type == "TEX_IMAGE":
            if n.image is not None and n.image.colorspace_settings.name == "Non-Color":
                if nrm is not None:
                    n.image = nrm
            elif col is not None:
                n.image = col


def run(modname, it, do_export=True, do_godot=True):
    t0 = time.time()
    M = importlib.import_module(modname)
    aid = M.ID
    core.reset()
    pv2.log(f"[{aid}] iter {it}")
    views = M.views()
    params, reps = pv2.solve_views(views, M.points, M.PARAMS, M.FREE, prior_sigma=getattr(M, "PRIOR", 0.25))
    params["_cams"] = {v.name: v.cam for v in views}
    if hasattr(M, "ground_poly"):
        for v in views:
            v.ground = M.ground_poly(params)
    A = pv2.Asset(aid, M.ATLAS)
    for lod in range(3):
        M.build(A, params, lod)
    # camera overlays (LOD0 wireframe at each view's pose)
    P3 = M.points(params)
    for v in views:
        Vs, Ts = [], []
        W = A.world_mats(v.pose)
        off = 0
        for nm, p in A.parts.items():
            if W.get(nm) is None:
                continue
            V, F, _, _, _ = p.geo[0].arrays()
            if not len(V):
                continue
            from geo import triangulate
            T = np.array(triangulate(F))
            Vw = V @ W[nm][:3, :3].T + W[nm][:3, 3]
            Vs.append(Vw)
            Ts.append(T + off)
            off += len(V)
        pv2.camera_overlay(v, P3, pv2.qa_path(aid, it, f"camera_{v.name}"), (np.concatenate(Vs), np.concatenate(Ts)))
    # materials with placeholder images, objects
    glow = getattr(M, "GLOW", None)
    blank = bl.image_from_array(f"{aid}_c", np.full((8, 8, 3), 0.5))
    blank_n = bl.image_from_array(f"{aid}_n", np.full((8, 8, 3), (0.5, 0.5, 1.0)), "Non-Color")
    mats = {lod: make_mats(aid, lod, blank, blank_n if lod == 0 else None, glow) for lod in range(3)}
    B = pv2.realize(A, mats)
    tris = {}
    by_node = {}
    for lod in range(3):
        by_node[f"LOD{lod}"] = {nm: core.tri_count(o) for (l_, nm), o in B.objs.items() if l_ == lod}
        tris[f"LOD{lod}"] = int(sum(by_node[f"LOD{lod}"].values()))
    pv2.log(f"[{aid}] tris {tris}")
    # UV atlases
    for lod in range(3):
        objs = [o for (l_, nm), o in B.objs.items() if l_ == lod]
        fixed = [B.finfo[(l_, nm)]["fixed"] for (l_, nm), o in B.objs.items() if l_ == lod]
        bl.atlas_uv(objs, fixed)
    # texture LOD0 by projection, LOD1/2 by transfer
    tviews = views + (pv2.sym_views(views, M.sym_specs(params)) if hasattr(M, "sym_specs") else [])
    alb0, nrm0, info, tstats = pv2.texture_lod0(A, B, tviews, M.SWATCHES, M.ATLAS, it, gate=getattr(M, "GATE", None),
                                                edge=getattr(M, "EDGE", None))
    files = {"c0": f"{aid}_c.jpg", "n0": f"{aid}_n.png", "c1": f"{aid}_lod1_c.jpg", "c2": f"{aid}_lod2_c.jpg"}
    pv2.save_png(os.path.join(pv2.TEXM, f"{aid}_c.png"), alb0)
    pv2.save_png(os.path.join(pv2.TEXM, f"{aid}_n.png"), nrm0)
    lods_img = {}
    for lod, size in ((1, M.ATLAS // 2), (2, M.ATLAS // 4)):
        a = pv2.transfer(A, B, lod, info, size)
        lods_img[lod] = a
        pv2.save_png(os.path.join(pv2.TEXM, f"{aid}_lod{lod}_c.png"), a)
    import cv2
    n_small = cv2.resize(nrm0.astype(np.float32), (M.ATLAS // 2, M.ATLAS // 2), interpolation=cv2.INTER_AREA)
    img_c0 = bl.image_from_array(f"{aid}_c", alb0)
    img_n0 = bl.image_from_array(f"{aid}_n", n_small, "Non-Color")
    swap_images(mats[0]["atlas"], img_c0, img_n0)
    for lod in (1, 2):
        swap_images(mats[lod]["atlas"], bl.image_from_array(f"{aid}_lod{lod}_c", lods_img[lod]))
    # QA per view
    bl.setup_render(16)
    qa = {}
    for v in views:
        rgba = pv2.render_view(A, B, v, ss=2)
        ign = v.ignore()
        if getattr(v, "iou_ignore", None):
            pm = pv2.ignore_mask_from_parts(A, B, v, v.iou_ignore)
            if pm is not None:
                ign = pm if ign is None else (ign | pm)
        m = pv2.compare(v, rgba, pv2.qa_path(aid, it, v.name),
                        f"{aid} v2 iter {it}: {v.title or v.name} | solved camera rms {v.rep['rms_px']:.2f}px "
                        f"(n={v.rep['n']}) | LOD0 painted light k={pv2.PAINT_K}", ignore=ign)
        m["camera_rms_px"] = round(v.rep["rms_px"], 2)
        m["camera_max_px"] = round(v.rep["max_px"], 2)
        m["camera_points"] = v.rep["n"]
        qa[v.name] = m
        pv2.log(f"[{aid}] view {v.name}: IoU raw {m['iou_raw']:.3f} filled {m['iou_filled']:.3f} "
                f"colour {m['colour_err']:.3f} (cam rms {v.rep['rms_px']:.2f}px)")
    # extra QA renders defined by the module (LOD sheet, close-ups)
    if hasattr(M, "extra_qa"):
        qa.update(M.extra_qa(A, B, views, it) or {})
    # clips
    M.clips(A, B)
    pv2.clear_actions(A, B)
    out = {}
    if do_export:
        glb = os.path.join(pv2.RT, f"{aid}.glb")
        pv2.save_jpg(os.path.join(pv2.RT, files["c0"]), alb0, 90)
        pv2.save_png(os.path.join(pv2.RT, files["n0"]), n_small)
        pv2.save_jpg(os.path.join(pv2.RT, files["c1"]), lods_img[1], 88)
        pv2.save_jpg(os.path.join(pv2.RT, files["c2"]), lods_img[2], 88)
        pv2.export(A, B, glb, {f"{aid}_c": files["c0"], f"{aid}_n": files["n0"], f"{aid}_lod1_c": files["c1"],
                               f"{aid}_lod2_c": files["c2"]})
        nodes, anims = pv2.glb_nodes(glb)
        lo = np.min([np.min(np.asarray([o.matrix_world @ v_.co for v_ in o.data.vertices]), 0)
                     for (l_, nm), o in B.objs.items() if l_ == 0], 0)
        hi = np.max([np.max(np.asarray([o.matrix_world @ v_.co for v_ in o.data.vertices]), 0)
                     for (l_, nm), o in B.objs.items() if l_ == 0], 0)
        meta = dict(
            id=aid, generation="props v2: measured blueprint + solved painting cameras + painting projection",
            tris=tris, tris_by_node=by_node, budget=getattr(M, "BUDGET", {}), bones=0,
            materials=sorted({m.name for d in mats.values() for m in d.values()}),
            textures={files["c0"]: M.ATLAS, files["n0"]: M.ATLAS // 2, files["c1"]: M.ATLAS // 2,
                      files["c2"]: M.ATLAS // 4},
            texture_mode="external JPEG/PNG next to the GLB (relative URIs); LOD1/LOD2 have their own atlases",
            paintedLightMix=pv2.PAINT_K,
            paintedLightNote="albedo carries the painted light: shade = albedo * mix(1, lambert, paintedLightMix) "
                             "(actor_rig.apply_look -> ForestKit.painted_material)",
            coordinate_space="glTF (Y up, metres) relative to the GLB root; front (door / main face) faces +Z",
            bounds_m={"min": [round(float(lo[0]), 3), round(float(lo[2]), 3), round(float(-hi[1]), 3)],
                      "max": [round(float(hi[0]), 3), round(float(hi[2]), 3), round(float(-lo[1]), 3)]},
            lod_nodes={f"LOD{l}": sorted(o.name for (l_, nm), o in B.objs.items() if l_ == l) for l in range(3)},
            lod_note="LOD meshes are siblings named *_LOD0/1/2 (actor_rig.set_lod); LOD1/LOD2 are hidden by default "
                     "(KHR_node_visibility) so a plain instance shows LOD0 only.",
            hidden_by_default=sorted(A.hidden),
            clips={k: {kk: vv for kk, vv in v.items() if kk != "nodes"} | {"nodes": v["nodes"]} for k, v in A.clips.items()},
            glb_nodes=nodes, glb_animations=anims,
            blueprint={k: round(float(v), 4) for k, v in params.items() if not k.startswith("_")},
            qa=dict(views=qa, cameras={v.name: dict(rms_px=round(v.rep["rms_px"], 2), max_px=round(v.rep["max_px"], 2),
                                                    n=v.rep["n"], fov_deg=round(v.rep["fov_deg"], 2),
                                                    per_point_px=v.rep["per_point_px"]) for v in views},
                    texture=tstats, sheets=f"forest_rescue/qa/compare/{aid}/v2_iter{it:02d}_*"),
            build=f"python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/props/v2/build_asset.py {modname} --iter {it}",
        )
        meta.update(M.meta(A, params))
        core.write_json(os.path.join(pv2.RT, f"{aid}.meta.json"), meta)
        out["meta"] = meta
        if do_godot:
            bad, log = pv2.godot_import_check(glb, [os.path.join(pv2.RT, f) for f in files.values()])
            pv2.log(f"[{aid}] Godot import: {len(bad)} error/warning lines")
            for ln in bad[:20]:
                pv2.log("   GODOT> " + ln)
            meta["qa"]["godot_import"] = {"errors_warnings": len(bad), "lines": bad[:20]}
            core.write_json(os.path.join(pv2.RT, f"{aid}.meta.json"), meta)
    core.write_json(pv2.qa_path(aid, it, "metrics", "json"), dict(qa=qa, tris=tris, texture=tstats,
                                                                  blueprint={k: round(float(v), 4) for k, v in params.items() if not k.startswith("_")}))
    for o in bpy.data.objects:
        o.hide_render = False
    core.save_blend(os.path.join(pv2.SRC, f"{aid}.blend"))
    pv2.log(f"[{aid}] done in {time.time() - t0:.0f}s")
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    it = int(a[a.index("--iter") + 1]) if "--iter" in a else 1
    run(a[0], it, do_export="--no-export" not in a, do_godot="--no-godot" not in a)
