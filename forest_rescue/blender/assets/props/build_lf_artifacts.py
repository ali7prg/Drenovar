"""Build lf_artifact_stone_rune / bronze_seal / amber_crystal / bone_key (3 variants + socket each).

Run: python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/props/build_lf_artifacts.py [--iter N] [--family stone_rune] [--noqa]
Outputs: godot/project/assets/forest_rescue/props/lf_artifact_<family>.glb + .meta.json,
         forest_rescue/blender/sources/props/lf_artifact_<family>.blend, textures/props/*,
         forest_rescue/qa/compare/lf_artifact_<family>/iterNN_*.png
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy
import numpy as np

import artifactkit as ak
import propkit as pk
import propqa as qa
import propshaders as sh
import propproj as pp
from frlib import core, paths, refs

FAMILIES = ["stone_rune", "bronze_seal", "amber_crystal", "bone_key"]
KEYMAP = {  # family -> {variant: key id}
    "stone_rune": {1: "lf_key_10", 2: "lf_key_02", 3: "lf_key_04"},
    "bronze_seal": {1: "lf_key_11", 2: "lf_key_03", 3: "lf_key_06"},
    "amber_crystal": {1: "lf_key_05", 2: "lf_key_08", 3: "lf_key_09"},
    "bone_key": {1: "lf_key_01", 2: "lf_key_07", 3: "lf_key_12"},
}
SOCKET_KIND = {"stone_rune": "circle", "bronze_seal": "hex", "amber_crystal": "diamond", "bone_key": "keyhole"}
IMG = "loot_artifact_families.png"
REF = {  # family -> view -> (box, mask params)
    "stone_rune": {"hero": (75, 140, 345, 368), "front": (40, 393, 180, 523), "side": (200, 388, 246, 505),
                   "socket": (110, 560, 257, 667)},
    "bronze_seal": {"hero": (450, 143, 707, 360), "front": (413, 393, 560, 520), "side": (580, 390, 630, 504),
                    "socket": (493, 560, 637, 667)},
    "amber_crystal": {"hero": (853, 137, 1080, 360), "front": (807, 387, 930, 523), "side": (957, 390, 1006, 517),
                      "socket": (863, 557, 1027, 663)},
    "bone_key": {"hero": (1187, 147, 1513, 357), "front": (1170, 423, 1340, 490), "side": (1354, 390, 1386, 515),
                 "socket": (1263, 563, 1390, 667)},
}
MASK = dict(method="flood", tol=3)


def fine(fn, scale):
    def f(ctx):
        P = ctx.P
        ctx.P = P * scale
        r = fn(ctx)
        ctx.P = P
        return r
    return f


def rune_stone(ctx):
    return sh.limestone(ctx, base=sh.C(150, 132, 112), light=sh.C(196, 182, 162), dark=sh.C(104, 90, 76),
                        mortar=sh.C(90, 80, 68))


SHADERS = dict(sh.SHADERS)
SHADERS.update({
    "rune_stone": fine(rune_stone, 5.0),
    "limestone_fine": fine(lambda c: sh.limestone(c, base=sh.C(160, 144, 124), light=sh.C(200, 188, 170),
                                                  dark=sh.C(112, 98, 84)), 3.0),
    "bronze": fine(lambda c: sh.bronze(c, base=sh.C(158, 100, 36), hi=sh.C(222, 160, 72), patina=sh.C(64, 92, 66),
                                       dark=sh.C(66, 40, 16), patina_amt=0.6), 3.0),
    "oak_fine": fine(lambda c: sh.oak(c, base=sh.C(120, 84, 54), light=sh.C(164, 120, 80), dark=sh.C(66, 44, 28),
                                      grey=sh.C(140, 118, 96), weather=0.12), 4.0),
    "amber": sh.gem,
    "bone": fine(sh.bone, 1.0),
})


HEIGHT_GAIN = {"stone_rune": 0.022, "bronze_seal": 0.016, "amber_crystal": 0.010, "bone_key": 0.005}
HERO_X0 = {"stone_rune": [-0.25, 0.75, 0, 0.66, 2.2, 0, 0], "bronze_seal": [-0.3, 0.7, 0, 0.58, 2.2, 0, 0],
           "amber_crystal": [-0.35, 0.95, 0, 0.65, 2.2, 0, 0], "bone_key": [-0.9, 0.8, 0, 0.69, 2.2, 0, 0]}
VIEWS = {}   # family -> computed views/cameras (shared by projection and QA)


def trace(fam):
    """Outline/thickness of the drawn design (variant v1) from the sheet's front and side views."""
    box = REF[fam]
    fimg, fm = qa.crop_and_mask(IMG, box["front"], **MASK)
    simg, sm = qa.crop_and_mask(IMG, box["side"], method="flood", tol=2)
    fx0, fy0, fx1, fy1, fw, fh = pp.mask_extent(fm)
    sx0, sy0, sx1, sy1, sw, shh = pp.mask_extent(sm)
    info = {"front_px": [fw, fh], "side_px": [sw, shh]}
    if fam in ("stone_rune", "bronze_seal"):
        D = 2 * ak.DIMS[fam]["R"]
        ppm = fw / D
        outline = pp.outline_metres(pp.mask_outline(fm, 160), ((fx0 + fx1) / 2, (fy0 + fy1) / 2), ppm)
        t = sw / shh * (fh / ppm)
        ak.TRACE[fam] = dict(outline=outline, t=float(t))
        info.update(diameter_m=D, height_m=float(fh / ppm), thickness_m=float(t))
    elif fam == "amber_crystal":
        W = ak.DIMS[fam]["W"]
        H = W * fh / fw
        t = sw / shh * H
        ppm = fw / W
        outline = pp.outline_metres(pp.mask_outline(fm, 160), ((fx0 + fx1) / 2, (fy0 + fy1) / 2), ppm)
        ak.TRACE[fam] = dict(H=float(H), W=W, t=float(t), outline=outline)
        info.update(H_m=float(H), W_m=W, thickness_m=float(t))
    else:
        info.update(length_m=ak.DIMS[fam]["L"], aspect=float(fh / fw))
    print("[trace]", fam, info)
    return info


def lay_flat(A, node, fam, on=True):
    """Rotate a node so its front faces up (+Z) like the drawing's table-top hero views."""
    e = A.pivots[node]
    if not on:
        e.rotation_euler = (0, 0, 0)
    elif fam == "bone_key" and node != "socket":
        e.rotation_euler = (0, -math.pi / 2, 0)      # flat side (+X) up
    else:
        e.rotation_euler = (-math.pi / 2, 0, 0)      # front (-Y) up
    bpy.context.view_layer.update()


def make_views(A, fam, cams):
    box = REF[fam]
    v1 = [A.meshes[0]["v1"]]
    so = [A.meshes[0]["socket"]]
    V = {}
    fimg, fm = qa.crop_and_mask(IMG, box["front"], **MASK)
    simg, sm = qa.crop_and_mask(IMG, box["side"], method="flood", tol=2)
    mn, mx = core.bounds(v1)
    size = mx - mn
    if fam == "bone_key":
        V["front"] = (fimg, fm, pp.ortho_view_for("front", fimg, fm, np.array([-1.0, 0, 0]), v1, real_width=size[1]))
        V["side"] = (simg, sm, pp.ortho_view_for("side", simg, sm, "top", v1, real_height=size[1]))
    else:
        V["front"] = (fimg, fm, pp.ortho_view_for("front", fimg, fm, "front", v1, real_width=size[0]))
        V["side"] = (simg, sm, pp.ortho_view_for("side", simg, sm, "left", v1, real_height=size[2]))
    for key, objs, node, x0 in (("hero", v1, "v1", HERO_X0[fam]), ("socket", so, "socket", [0.0, 0.85, 0, 1.05, 2.2, 0, 0])):
        img, m = qa.crop_and_mask(IMG, box[key], **MASK)
        lay_flat(A, node, fam)
        tris = pk.world_triangles(objs)
        c = tris.reshape(-1, 3).mean(0)
        ck = f"{A.id}:{key}"
        if ck in cams and not qa.flag("--refit"):
            x, sc = pk.fit_camera(tris, m, np.array(cams[ck]), fixed=(2,), iters=1)
        else:   # multi-start (yaw/pitch/distance) -> best silhouette IoU, then refine
            best = None
            for dy, dp, ds in ((0, 0, 1), (-0.35, 0, 1), (0.35, 0, 1), (0, -0.2, 1), (0, 0.15, 1), (0, 0, 0.8), (0, 0, 1.25)):
                st = np.array(list(x0) + list(c))
                st[0] += dy
                st[1] += dp
                st[3] *= ds
                xx, ss = pk.fit_camera(tris, m, st, fixed=(2,), iters=1)
                if best is None or ss > best[1]:
                    best = (xx, ss)
            x, sc = pk.fit_camera(tris, m, best[0], fixed=(2,), iters=1)
        cams[ck] = [float(a) for a in x]
        lay_flat(A, node, fam, False)
        H, W = m.shape
        V[key] = (img, m, pk.cam_from_params(x, W, H))
    VIEWS[fam] = V
    return V


SWATCH_CLS = {"stone_rune": ["rune_stone"], "bronze_seal": ["bronze"], "amber_crystal": ["oak_fine"],
              "bone_key": ["bone"]}


def swatch_for(fam, V):
    """Plain-material swatch = interior of the drawing's side view (no ornament there)."""
    img, m, _ = V["side"]
    x0, y0, x1, y1, w, h = pp.mask_extent(m)
    dx, dy = max(2, int(w * 0.18)), max(2, int(h * 0.12))
    sw = img[y0 + dy:y1 - dy, x0 + dx:x1 - dx]
    out = {c: (sw, 0.03 if fam != "bone_key" else 0.02) for c in SWATCH_CLS[fam]}
    return out


def build_family(fam, cams):
    asset_id = f"lf_artifact_{fam}"
    core.reset()
    tinfo = trace(fam)
    spec = {"root": {}}
    for v in (1, 2, 3):
        spec[f"v{v}"] = {"pivot": (0, 0, 0), "export_name": f"{asset_id}_v{v}"}
    spec["socket"] = {"pivot": (0, 0, 0), "export_name": f"{asset_id}_socket"}
    A = pk.Asset(asset_id, spec)
    A.dirt_scale = 0.0

    def build(lod):
        B = pk.Builder(lod)
        for v in (1, 2, 3):
            node = f"v{v}"
            {"stone_rune": ak.build_rune, "bronze_seal": ak.build_seal, "amber_crystal": ak.build_amber,
             "bone_key": ak.build_key}[fam](B, node, v)
        ak.build_socket(B, "socket", SOCKET_KIND[fam], cls="limestone_fine")
        return B

    A.compile(build)
    pk.pack_atlas(A.lod0_objects(), margin=0.006)
    pk.transfer_atlas_uv(A)
    V = make_views(A, fam, cams)
    v1 = [A.meshes[0]["v1"]]
    so = [A.meshes[0]["socket"]]
    hero_pose = (lambda: lay_flat(A, "v1", fam)), (lambda: lay_flat(A, "v1", fam, False))
    sock_pose = (lambda: lay_flat(A, "socket", fam)), (lambda: lay_flat(A, "socket", fam, False))
    specs = [pp.ViewSpec("front", V["front"][0], V["front"][1], v1, "ortho", view=V["front"][2], weight=0.6),
             pp.ViewSpec("side", V["side"][0], V["side"][1], v1, "ortho", view=V["side"][2], weight=0.8, height=False),
             pp.ViewSpec("hero", V["hero"][0], V["hero"][1], v1, "persp", cam=V["hero"][2], pose=hero_pose[0],
                         unpose=hero_pose[1], weight=3.0),
             pp.ViewSpec("socket", V["socket"][0], V["socket"][1], so, "persp", cam=V["socket"][2], pose=sock_pose[0],
                         unpose=sock_pose[1], weight=1.0)]
    files, info = pp.paint_relief_textures(A, SHADERS, specs, size=2048, height_gain=HEIGHT_GAIN[fam],
                                           sizes={"base": 1024, "orm": 512, "normal": 1024}, relief_levels=4,
                                           ao_distance=0.012, ao_strength=0.38, edge_fade_m=0.0012, samples=10,
                                           swatches=swatch_for(fam, V), no_relief_cls=("amber",))
    pk.make_material(A, files)
    A.trace_info = tinfo
    A.paint_info = info
    return A


def place_layout(A, spread=True):
    """QA layout: variants side by side (runtime GLB keeps all at the origin)."""
    xs = {"v1": -0.17, "v2": 0.0, "v3": 0.17, "socket": 0.40}
    for node, e in A.pivots.items():
        e.location = (xs[node], 0, 0) if spread else (0, 0, 0)


def write_meta(A, fam, glb):
    stats = pk.tri_stats(A)
    summ = pk.glb_summary(glb)
    per_variant = {}
    for v in (1, 2, 3):
        per_variant[f"v{v}"] = {f"LOD{l}": stats[f"LOD{l}"]["by_node"].get(f"v{v}", 0) for l in (0, 1, 2)}
    kind = SOCKET_KIND[fam]
    rd = ak.DIMS[fam]["recess_d"]
    meta = {
        "id": A.id,
        "tris": {f"LOD{l}": stats[f"LOD{l}"]["total"] for l in (0, 1, 2)},
        "tris_per_variant": per_variant,
        "tris_socket": {f"LOD{l}": stats[f"LOD{l}"]["by_node"].get("socket", 0) for l in (0, 1, 2)},
        "budget": "artifact <= 800 tris (LOD0, per variant)",
        "bones": 0,
        "materials": [f"{A.id}_mat"],
        "textures": {"baseColor": "1024 JPEG", "metallicRoughness": "512 JPEG (G rough, B metal)", "normal": "1024 PNG"},
        "coordinate_space": "glTF (Y up, metres); artifact front faces +Z; origin = key-slot insertion point",
        "variants": {f"v{v}": {"node": f"{A.id}_v{v}", "key_id": KEYMAP[fam][v],
                               "lods": [f"{A.id}_v{v}_LOD{l}" for l in (0, 1, 2)]} for v in (1, 2, 3)},
        "socket": {"node": f"{A.id}_socket", "shape": kind, "recess_depth_m": rd,
                   "key_slot": [0.0, 0.0, 0.0], "normal": [0.0, 0.0, 1.0],
                   "note": "socket origin = recess floor centre; artifact origin goes exactly here with identity rotation"},
        "clips": {},
        "bounds_m": None,
        "glb_nodes": summ["nodes"],
        "notes": ("All three variants sit at the origin; show exactly one variant node per key (meta.variants). "
                  "bone_key: shaft along -Z of glTF (into the lock), turn = rotation about the glTF Z axis. "
                  "LOD1/LOD2 are lower-tessellation rebuilds sharing the LOD0 atlas (parametric UV transfer)."),
    }
    if fam == "bone_key":
        meta["socket"]["insertion"] = "key enters along -Z (glTF); bit hangs toward -Y; 90 deg turn about Z unlocks"
    mn, mx = core.bounds(A.lod0_objects())
    meta["bounds_m"] = {"min": pk.b2g(mn), "max": pk.b2g(mx)}
    core.write_json(paths.runtime(pk.GROUP, f"{A.id}.meta.json"), meta)
    return meta


def qa_family(A, fam, it):
    asset_id = A.id
    pre = f"iter{it:02d}_"
    pk.studio(engine="CYCLES", samples=40, key=3.6, fill=1.2, rim=1.2, ambient=0.9, bg=(0.90, 0.82, 0.73))
    V = VIEWS[fam]
    results = {}
    lod0 = A.lod0_objects()
    v1 = [A.meshes[0]["v1"]]
    so = [A.meshes[0]["socket"]]
    from frlib import render as frr
    for key, objs, node in (("front", v1, None), ("side", v1, None), ("hero", v1, "v1"), ("socket", so, "socket")):
        only(objs, A)
        img, m, vw = V[key]
        if node:
            lay_flat(A, node, fam)
            pk.blender_camera(vw)
        else:
            frr.camera_for_view(vw)
        rgba = pk.render_rgba(qa.out(asset_id, "_tmp.png"))
        nm = {"front": "front", "side": "side", "hero": "hero34", "socket": "socket"}[key]
        results[nm] = pk.compare_panels(img, rgba, m, qa.out(asset_id, pre + nm + ".png"),
                                        f"{asset_id} v1 {nm} ({'ortho' if not node else 'fitted perspective'})")
        if node:
            lay_flat(A, node, fam, False)
    # variants line-up for readability without colour
    only(lod0, A)
    place_layout(A, True)
    for n in ("v1", "v2", "v3", "socket"):
        lay_flat(A, n, fam)
    mn, mx = core.bounds(lod0)
    c = (mn + mx) / 2
    span = float(np.max(mx - mn))
    for nm, (yaw, pitch) in (("lineup_top", (0.0, 1.45)), ("lineup_34", (-0.35, 0.75))):
        cam = pk.cam_from_params([yaw, pitch, 0, span * 2.3, 1.3, 0, 0, *c], 1400, 520)
        pk.blender_camera(cam)
        rgba = pk.render_rgba(qa.out(asset_id, "_tmp.png"))
        g = rgba[..., :3].mean(2, keepdims=True)
        grey = np.concatenate([np.repeat(g, 3, 2), rgba[..., 3:]], 2)
        pk.side_by_side([rgba, grey], ["v1 | v2 | v3 | socket (colour)", "same, greyscale (shape/relief only)"],
                        qa.out(asset_id, pre + nm + ".png"), height=360)
    for n in ("v1", "v2", "v3", "socket"):
        lay_flat(A, n, fam, False)
    place_layout(A, False)
    for o in A.all_meshes():
        o.hide_render = False
    return results


def only(objs, A):
    for o in A.all_meshes():
        o.hide_render = True
    for o in objs:
        o.hide_render = False


def main():
    it = qa.iteration()
    fams = FAMILIES
    for i, a in enumerate(sys.argv):
        if a == "--family":
            fams = sys.argv[i + 1].split(",")
    cams_path = os.path.join(paths.ensure(paths.QA_COMPARE, "props_cams"), "artifact_cams.json")
    cams = qa.load_cams(cams_path)
    summary = {}
    for fam in fams:
        A = build_family(fam, cams)
        qa.save_cams(cams_path, cams)
        glb = paths.runtime(pk.GROUP, f"{A.id}.glb")
        pk.export(A, glb)
        meta = write_meta(A, fam, glb)
        print("[artifacts]", fam, meta["tris"], meta["tris_per_variant"])
        if not qa.flag("--noqa"):
            res = qa_family(A, fam, it)
            summary[fam] = {k: {kk: vv for kk, vv in v.items() if kk in ("iou_filled", "iou_raw", "mean_abs_colour_error")}
                            for k, v in res.items()}
            summary[fam]["trace"] = A.trace_info
            summary[fam]["paint"] = A.paint_info
            print("[artifacts-qa]", fam, summary[fam])
        # QA layout GLB (variants side by side, lying flat like the drawing) for the Godot viewer
        place_layout(A, True)
        for n in ("v1", "v2", "v3", "socket"):
            lay_flat(A, n, fam)
            A.pivots[n]["rest_rot"] = tuple(A.pivots[n].rotation_euler)
            A.pivots[n]["rest_loc"] = list(A.pivots[n].location)
        qa_glb = os.path.join(paths.ensure(paths.QA_COMPARE, A.id), f"{A.id}_layout_qa.glb")
        pk.export(A, qa_glb)
        for n in ("v1", "v2", "v3", "socket"):
            del A.pivots[n]["rest_rot"]
            del A.pivots[n]["rest_loc"]
            lay_flat(A, n, fam, False)
        place_layout(A, False)
        core.save_blend(paths.source(pk.GROUP, f"{A.id}.blend"))
    core.write_json(os.path.join(paths.ensure(paths.QA_COMPARE, "props_cams"), f"artifacts_iter{it:02d}.json"), summary)


if __name__ == "__main__":
    main()
