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
    "bronze": fine(lambda c: sh.bronze(c, base=sh.C(150, 104, 48), hi=sh.C(212, 164, 88), patina=sh.C(70, 104, 80),
                                       dark=sh.C(70, 46, 22), patina_amt=0.55), 3.0),
    "oak_fine": fine(lambda c: sh.oak(c, base=sh.C(120, 84, 54), light=sh.C(164, 120, 80), dark=sh.C(66, 44, 28),
                                      grey=sh.C(140, 118, 96), weather=0.12), 4.0),
    "amber": sh.gem,
    "bone": fine(sh.bone, 1.0),
})


def build_family(fam):
    asset_id = f"lf_artifact_{fam}"
    core.reset()
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
            if fam == "stone_rune":
                ak.build_rune(B, node, v)
            elif fam == "bronze_seal":
                ak.build_seal(B, node, v)
            elif fam == "amber_crystal":
                ak.build_amber(B, node, v)
            else:
                ak.build_key(B, node, v)
        ak.build_socket(B, "socket", SOCKET_KIND[fam], cls="limestone_fine")
        return B

    A.compile(build)
    pk.pack_atlas(A.lod0_objects(), margin=0.006)
    worst = pk.transfer_atlas_uv(A)
    tex, tx = pk.synthesize(A, SHADERS, size=2048)
    ao = pk.bake_ao(A, size=1024, samples=24, distance=0.03, isolate=("*",))
    imgs = pk.finalize_textures(A, tex, ao=ao, ao_strength=0.5, sizes={"base": 1024, "orm": 512, "normal": 1024},
                                cavity=(0.0025, 0.0022, 0.75), normal_strength=1.4)
    pk.make_material(A, imgs)
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


def only(objs, A):
    for o in A.all_meshes():
        o.hide_render = True
    for o in objs:
        o.hide_render = False


def qa_family(A, fam, it, cams):
    asset_id = A.id
    pre = f"iter{it:02d}_"
    pk.studio(engine="CYCLES", samples=40, key=3.2, fill=1.1, rim=1.2, ambient=0.75, bg=(0.90, 0.82, 0.73))
    results = {}
    lod0 = A.lod0_objects()
    v1 = [A.meshes[0]["v1"]]
    only(v1, A)
    box = REF[fam]
    # --- front & side orthographic (variant v1 = the drawn design)
    for view in ("front", "side"):
        img, m = qa.crop_and_mask(IMG, box[view], **MASK)
        mn, mx = core.bounds(v1)
        size = mx - mn
        if fam == "bone_key":
            direction = np.array([-1.0, 0.0, 0.0]) if view == "front" else "top"
            kw = {"real_width": size[1]} if view == "front" else {"real_height": size[1]}
        else:
            direction = "front" if view == "front" else "left"
            kw = {"real_width": size[0]} if view == "front" else {"real_height": size[2]}
        met = qa.ortho_view_compare(asset_id, pre + view, v1, img, m, direction,
                                    title=f"{asset_id} v1 {view} (ortho, scaled by {'width' if view == 'front' else 'length'})", **kw)
        results[view] = met
    # --- hero 3/4 perspective fit (object lying on the table as drawn)
    lay_flat(A, "v1", fam)
    img, m = qa.crop_and_mask(IMG, box["hero"], **MASK)
    mn, mx = core.bounds(v1)
    c = (mn + mx) / 2
    x0 = {"stone_rune": [-0.25, 0.75, 0, 0.5, 2.2, 0, 0, *c], "bronze_seal": [-0.3, 0.7, 0, 0.45, 2.2, 0, 0, *c],
          "amber_crystal": [-0.35, 0.95, 0, 0.5, 2.2, 0, 0, *c], "bone_key": [-0.9, 0.8, 0, 0.55, 2.2, 0, 0, *c]}[fam]
    met, cam = qa.persp_fit_compare(asset_id, pre + "hero34", v1, img, m, x0, fixed=(2,), cam_store=cams,
                                    title=f"{asset_id} v1 hero 3/4 (camera fitted to silhouette)")
    results["hero34"] = met
    lay_flat(A, "v1", fam, False)
    # --- socket (3/4 from above)
    so = [A.meshes[0]["socket"]]
    only(so, A)
    lay_flat(A, "socket", fam)
    img, m = qa.crop_and_mask(IMG, box["socket"], **MASK)
    mn, mx = core.bounds(so)
    c = (mn + mx) / 2
    met, cam = qa.persp_fit_compare(asset_id, pre + "socket", so, img, m, [0.0, 0.85, 0, 0.8, 2.2, 0, 0, *c],
                                    fixed=(2,), cam_store=cams, title=f"{asset_id} socket ({SOCKET_KIND[fam]})")
    results["socket"] = met
    lay_flat(A, "socket", fam, False)
    # --- variants line-up for readability without colour
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
    only([], A)
    for o in A.all_meshes():
        o.hide_render = False
    return results


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
        A = build_family(fam)
        glb = paths.runtime(pk.GROUP, f"{A.id}.glb")
        pk.export(A, glb)
        meta = write_meta(A, fam, glb)
        print("[artifacts]", fam, meta["tris"], meta["tris_per_variant"])
        if not qa.flag("--noqa"):
            res = qa_family(A, fam, it, cams)
            qa.save_cams(cams_path, cams)
            summary[fam] = {k: {kk: vv for kk, vv in v.items() if kk in ("iou_filled", "iou_raw", "mean_abs_colour_error")}
                            for k, v in res.items()}
            print("[artifacts-qa]", fam, summary[fam])
        # QA layout GLB (variants side by side) for the Godot viewer
        place_layout(A, True)
        qa_glb = os.path.join(paths.ensure(paths.QA_COMPARE, A.id), f"{A.id}_layout_qa.glb")
        pk.export(A, qa_glb)
        place_layout(A, False)
        core.save_blend(paths.source(pk.GROUP, f"{A.id}.blend"))
    core.write_json(os.path.join(paths.ensure(paths.QA_COMPARE, "props_cams"), f"artifacts_iter{it:02d}.json"), summary)


if __name__ == "__main__":
    main()
