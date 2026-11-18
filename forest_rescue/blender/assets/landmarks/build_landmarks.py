"""Build landmark GLBs (art/06) + QA comparisons.

Run: python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/landmarks/build_landmarks.py \
        <bridge27m|hunter_shelter|quarry_mine|ruined_watchpost|standing_stones|camp_props|small|all> [--iter N]
        [--textures] [--no-export]
Outputs godot/project/assets/forest_rescue/landmarks/lf_env_<id>.glb (+ .meta.json), shared external textures
lm_*.jpg/png next to them; sources/landmarks/*.blend; qa/compare/lf_env_<id>/iterNN_*.png
"""
import argparse
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "forest"))
import fbuild  # noqa: E402  (frlib path)
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from frlib import core, paths, refs, render  # noqa: E402
import fqa  # noqa: E402
import lm_textures as lmt  # noqa: E402
import landmarks as L  # noqa: E402
from lmkit import STONE, WOOD, MISC, ROOF, GLOW, MAT_NAMES  # noqa: E402

RT = paths.ensure(paths.RUNTIME, "landmarks")
MASTER = paths.ensure(paths.TEXTURE_SOURCES, "landmarks")
SHEET = "06_environment_landmarks.png"

# reference crops (full sheet px): main 3/4 illustration and orthographic-ish insets
REFS = {
    "bridge27m": dict(main=(0, 0, 590, 265), insets={"side": (592, 30, 822, 74), "top": (592, 98, 822, 144)}),
    "hunter_shelter": dict(main=(820, 0, 1262, 265), insets={"front": (1272, 12, 1392, 88), "side": (1418, 12, 1512, 88)}),
    "quarry_mine": dict(main=(0, 268, 600, 582), insets={"mine_front": (528, 308, 664, 398), "crane_side": (678, 308, 794, 398)}),
    "ruined_watchpost": dict(main=(768, 258, 1232, 572), insets={"front": (1242, 302, 1390, 394), "side": (1392, 302, 1514, 394)}),
    "standing_stones": dict(main=(0, 578, 472, 842), insets={"row": (478, 598, 706, 694)}),
    "camp_props": dict(main=(738, 578, 1252, 842), insets={"front": (1236, 612, 1396, 694), "side": (1408, 612, 1516, 694)}),
}
# camera for the 3/4 side-by-side (location, look-at, lens) roughly matching the painting
CAMS = {
    "bridge27m": ((-21.0, -27.0, 13.0), (1.5, 0.0, -0.2), 38),
    "hunter_shelter": ((-6.5, -9.5, 5.2), (0.2, 0.0, 1.6), 40),
    "quarry_mine": ((-3.5, -14.0, 6.0), (1.0, 0.0, 2.0), 40),
    "ruined_watchpost": ((-7.0, -12.0, 6.0), (0.6, 0.0, 2.2), 40),
    "standing_stones": ((-1.5, -10.5, 5.6), (0.0, 0.5, 0.9), 40),
    "camp_props": ((-4.0, -8.5, 4.6), (0.4, 0.0, 1.0), 40),
}
VIEW_DIR = {"side": (0, 1, 0), "front": (0, 1, 0), "mine_front": (0, 1, 0), "crane_side": (1, 0, 0), "row": (0, 1, 0),
            "top": None}


def textures(it):
    lmt.build_all(RT, MASTER, qa_png=paths.compare("landmarks_textures", f"iter{it:02d}_textures.png"))


_MATS = {}


def mats():
    if _MATS:
        return _MATS
    def p(n):
        return os.path.join(RT, n)
    _MATS[STONE] = fbuild.texture_material("lm_stone", p("lm_stone_c.jpg"), p("lm_stone_n.png"), p("lm_stone_r.png"))
    _MATS[WOOD] = fbuild.texture_material("lm_wood", p("lm_wood_c.jpg"), p("lm_wood_n.png"), p("lm_wood_r.png"))
    _MATS[ROOF] = fbuild.texture_material("lm_roof", p("lm_roof_c.jpg"), p("lm_roof_n.png"), p("lm_roof_r.png"))
    m = core.material("lm_misc", base_tex=fbuild.image(p("lm_misc_c.png")), normal_tex=fbuild.image(p("lm_misc_n.png"), "Non-Color"),
                      rough_tex=fbuild.image(p("lm_misc_r.png"), "Non-Color"), alpha_clip=0.5, double_sided=True)
    _MATS[MISC] = m
    g = core.material("lm_glow", base_tex=fbuild.image(p("lm_misc_c.png")), emission=(1.0, 0.72, 0.36, 1.0),
                      emission_strength=3.0, rough=0.3)
    _MATS[GLOW] = g
    return _MATS


EXT = {n[:-4]: n for n in ("lm_stone_c.jpg", "lm_stone_n.png", "lm_stone_r.png", "lm_wood_c.jpg", "lm_wood_n.png",
                           "lm_wood_r.png", "lm_roof_c.jpg", "lm_roof_n.png", "lm_roof_r.png", "lm_misc_c.png",
                           "lm_misc_n.png", "lm_misc_r.png")}


def kit_object(name, kit):
    """Kit.MeshData -> object; global material ids remapped to the used subset (slot order by id)."""
    md = kit.md
    used = sorted(set(md.MAT))
    remap = {m: i for i, m in enumerate(used)}
    md.MAT = [remap[m] for m in md.MAT]
    M = mats()
    obj = fbuild.object_from_md(name, md, [M[u] for u in used], smooth=False)
    obj.data.color_attributes.remove(obj.data.color_attributes["Col"])
    return obj


def to_gl_collider(c):
    x, y, z = c["centre"]
    sx, sy, sz = c["size"]
    return {"type": c["type"], "centre": [round(x, 3), round(z, 3), round(-y, 3)], "size": [round(sx, 3), round(sz, 3), round(sy, 3)],
            "yaw_deg": round(math.degrees(c["yaw"]), 1)}


def tarp_object(name, data, lod):
    V, F, uvg, pin = data
    u0, v0, u1, v1 = lmt.uv("canvas")
    uvs = [[(u0 + (u1 - u0) * uvg[i][0], v0 + (v1 - v0) * uvg[i][1]) for i in f] for f in F]
    from treegen import MeshData
    md = MeshData()
    md.add(V, F, uvs, 0, np.ones((len(V), 4)))
    obj = fbuild.object_from_md(name, md, [mats()[MISC]], smooth=True)
    obj.data.color_attributes.remove(obj.data.color_attributes["Col"])
    # lf_banner_wind: two billow shape keys driven by a 4.5 s seamless loop (morph-target animation)
    obj.shape_key_add(name="Basis")
    rng = np.random.default_rng(7 + lod)
    for kname, amp, ph in (("billow_up", 0.16, 0.0), ("ripple", 0.07, 1.3)):
        sk = obj.shape_key_add(name=kname)
        for i, v in enumerate(V):
            w = 1.0 - pin[i]
            d = amp * w * (1.0 if kname == "billow_up" else math.sin(v[0] * 2.4 + ph))
            sk.data[i].co = (v[0], v[1], v[2] + d)
    act = bpy.data.actions.new("lf_banner_wind")
    obj.data.shape_keys.animation_data_create()
    obj.data.shape_keys.animation_data.action = act
    fps = 30
    n = int(4.5 * fps)
    for f in range(0, n + 1, 3):
        t = f / n * 2 * math.pi
        obj.data.shape_keys.key_blocks["billow_up"].value = 0.5 + 0.5 * math.sin(t)
        obj.data.shape_keys.key_blocks["ripple"].value = 0.5 + 0.5 * math.sin(2 * t + 0.7)
        obj.data.shape_keys.key_blocks["billow_up"].keyframe_insert("value", frame=f + 1)
        obj.data.shape_keys.key_blocks["ripple"].keyframe_insert("value", frame=f + 1)
    return obj


def inset_compare(asset, it, key, box, objs, direction):
    img = refs.load(SHEET)
    crop = refs.crop(img, box)
    bg = refs.border_color(crop)
    m = refs.silhouette(crop, bg=bg, thresh=0.12, keep="all", min_area=40, fill_holes=200)
    if direction is None:
        rgba = fqa.ortho_shot(objs, "/tmp/_inset.png", pitch_deg=90, res=(800, 400), margin=1.0, bg=False)
    else:
        rgba = fqa.ortho_shot(objs, "/tmp/_inset.png", direction=direction, res=(800, 400), margin=1.0, bg=False)
    rm = rgba[..., 3] > 0.5
    ys, xs = np.nonzero(rm)
    ry, rx = np.nonzero(m)
    if len(xs) == 0 or len(rx) == 0:
        return None
    import cv2
    sub = rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    rw, rh = rx.max() - rx.min() + 1, ry.max() - ry.min() + 1
    s = rw / sub.shape[1]
    nh = max(1, int(round(sub.shape[0] * s)))
    sub = cv2.resize(sub.astype(np.float32), (rw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.zeros(crop.shape[:2] + (4,), np.float32)
    y1 = ry.max() + 1
    y0 = y1 - nh
    sy0 = max(0, -y0)
    canvas[max(y0, 0):y1, rx.min():rx.min() + rw] = sub[sy0:]
    view = refs.View(name=key, image=crop, mask=m, d=refs.VIEW_DIRS["front"], ppm=1.0, ax=0, ay=0)
    big = lambda a: cv2.resize(a.astype(np.float32), (a.shape[1] * 3, a.shape[0] * 3), interpolation=cv2.INTER_NEAREST)
    view.image = big(crop)
    view.mask = big(m.astype(np.float32)) > 0.5
    return render.compare(view, big(canvas), fqa.iter_path(asset, it, f"inset_{key}"), title=f"{asset} {key} inset vs art/06 (iter {it}, width-fitted)")


def three_quarter(asset, it, objs, box, cam):
    loc, look, lens = cam
    fqa.only(objs)
    render.perspective_camera(loc, look, lens=lens, res=(box[2] - box[0], box[3] - box[1]))
    rgba = render.render_rgba()
    ref = refs.crop(refs.load(SHEET), box)
    bg = np.array(refs.border_color(ref))
    comp = rgba[..., :3] * rgba[..., 3:4] + bg * (1 - rgba[..., 3:4])
    render.side_by_side([ref, comp], ["art/06 reference", f"render iter {it}"], fqa.iter_path(asset, it, "threequarter"),
                        height=max(300, box[3] - box[1]))


def add_water_context(asset):
    """QA-only river/bank props (never exported) so the bridge reads like the illustration."""
    if asset != "lf_env_bridge27m":
        return []
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, L.WATER_Z))
    w = bpy.context.active_object
    w.scale = (13.0, 40.0, 1)
    m = bpy.data.materials.new("qa_water")
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (0.16, 0.22, 0.20, 1)
    b.inputs["Roughness"].default_value = 0.15
    w.data.materials.append(m)
    xs = np.linspace(-18, 18, 73)
    verts = []
    for y in (-14.0, 14.0):
        for x in xs:
            verts.append((x, y, L.bank_z(x) - 0.02))
    n = len(xs)
    faces = [(i, i + 1, n + i + 1, n + i) for i in range(n - 1)]
    g = core.mesh_object("qa_banks", np.array(verts), faces)
    mg = bpy.data.materials.new("qa_bank")
    mg.use_nodes = True
    mg.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = (0.33, 0.33, 0.2, 1)
    g.data.materials.append(mg)
    return [w, g]


def build(name, it, export=True, qa=True):
    asset = f"lf_env_{name}"
    core.reset()
    _MATS.clear()
    fbuild._IMG_CACHE.clear()
    objs_lod = {}
    extra_objs = {}
    kits = {}
    small = None
    for lod in range(3):
        if name == "bridge27m":
            k = L.build_bridge(lod)
        elif name == "hunter_shelter":
            k = L.build_shelter(lod)
        elif name == "quarry_mine":
            k = L.build_quarry(lod)
        elif name == "ruined_watchpost":
            k = L.build_watchpost(lod)
        elif name == "standing_stones":
            k = L.build_stones(lod)
        elif name == "camp_props":
            k, tarp = L.build_camp(lod)
            extra_objs[lod] = tarp_object(f"{asset}_tarp_LOD{lod}", tarp, lod)
        else:
            k = L.build_small(name, lod)
        kits[lod] = k
        objs_lod[lod] = kit_object(f"{asset}_LOD{lod}", k)
    tris = {f"LOD{l}": core.tri_count(objs_lod[l]) + (core.tri_count(extra_objs[l]) if l in extra_objs else 0) for l in range(3)}
    print(f"[{asset}] tris {tris}", flush=True)
    if qa and name in REFS:
        fqa.studio(24)
        ctx = add_water_context(asset)
        lod0 = [objs_lod[0]] + ([extra_objs[0]] if 0 in extra_objs else [])
        three_quarter(asset, it, lod0 + ctx, REFS[name]["main"], CAMS[name])
        for o in ctx:
            o.hide_render = True
        mets = {}
        for key, box in REFS[name]["insets"].items():
            sel = lod0
            if name == "quarry_mine":
                sel = lod0
            r = inset_compare(asset, it, key, box, sel, VIEW_DIR.get(key))
            if r:
                mets[key] = r
        # strategic camera
        fqa.ortho_shot(lod0, fqa.iter_path(asset, it, "strategic55"), pitch_deg=55, yaw_deg=25, res=(1200, 700),
                       label=f"{asset} LOD0 strategic 55deg")
        x0 = 0
        line = []
        for l in range(3):
            os_ = [objs_lod[l]] + ([extra_objs[l]] if l in extra_objs else [])
            lo, hi = core.bounds(os_)
            for o in os_:
                o.location.x = x0 - lo[0]
            x0 += hi[0] - lo[0] + 2.0
            line += os_
        bpy.context.view_layer.update()
        fqa.ortho_shot(line, fqa.iter_path(asset, it, "lods_strategic55"), pitch_deg=55, yaw_deg=25, res=(1500, 560),
                       label=f"{asset} LOD0 | LOD1 | LOD2")
        for o in line:
            o.location.x = 0
        core.write_json(paths.compare(asset, f"iter{it:02d}_metrics.json"), {"insets": mets, "tris": tris})
        print(json.dumps({k: v["iou"] for k, v in mets.items()}), flush=True)
    if not export:
        return
    root = fbuild.empty(asset)
    exp = [root]
    lo, hi = core.bounds([objs_lod[0]] + ([extra_objs[0]] if 0 in extra_objs else []))
    spacing = max(hi[1] - lo[1], 4.0) + 2.0
    for l in range(3):
        objs_lod[l].parent = root
        objs_lod[l].location = (0, l * spacing, 0)
        exp.append(objs_lod[l])
        if l in extra_objs:
            extra_objs[l].parent = root
            extra_objs[l].location = (0, l * spacing, 0)
            exp.append(extra_objs[l])
    bpy.context.view_layer.update()
    out = os.path.join(RT, f"{asset}.glb")
    extra = dict(export_vertex_color="NONE", export_image_format="AUTO")
    has_anim = bool(extra_objs)
    core.export_glb(out, exp, animations=has_anim, extra=dict(extra, export_morph=True, export_morph_normal=False,
                                                               export_animation_mode="ACTIONS"))
    import glbx
    glbx.externalize(out, EXT)
    gi = glbx.info(out)
    meta = {"id": asset, "tris": tris, "bones": 0, "materials": sorted(set(gi["materials"])), "glb_images": gi["images"],
            "textures": {n: 1024 for n in EXT.values()},
            "texture_mode": "external shared lm_* files next to the GLB (relative URIs)",
            "nodes": {f"LOD{l}": [objs_lod[l].name] + ([extra_objs[l].name] if l in extra_objs else []) for l in range(3)},
            "bounds_m_gltf": fbuild.gltf_bounds([objs_lod[0]] + ([extra_objs[0]] if 0 in extra_objs else [])),
            "collision": [to_gl_collider(c) for c in kits[0].colliders],
            "collision_note": "Godot axes (x, y=up, z), metres, relative to the asset origin; box size = full extents; "
                              "'ramp' = oriented box along the slope; yaw about +Y.",
            "layout_note": "LOD1/LOD2 nodes are displayed behind LOD0 (+Z offset) for preview only.",
            "build": f"python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/landmarks/build_landmarks.py {name}"}
    if name == "camp_props":
        meta["clips"] = {"lf_banner_wind": {"seconds": 4.5, "loop": True, "type": "morph-target animation on the tarp"}}
        meta["sockets"] = {"lantern_light": fbuild.to_gltf((2.45, -0.2, 1.95)), "fire_light": fbuild.to_gltf((0, -0.6, 0.4))}
    if name == "bridge27m":
        meta["placement"] = {"world_position_xz": [90.48200135039062, 20.0], "world_y": 0.0,
                             "note": "origin = bridge centre on the world datum; deck top local +1.1 = atlas structuralHeight; "
                                     "long axis = +X (west->east 77..104); atlas waterLevel -1.35 lies at local -1.35"}
        meta["dimensions"] = {"deck_length_m": 27.0, "deck_width_m": 4.0, "deck_top_z": 1.1,
                              "deck_x_range": [-13.5, 13.5], "deck_y_range_gltf_z": [-2.0, 2.0],
                              "piers_x": [-7.25, 7.25], "pier_inner_faces_x": [-6.6, 6.6], "wet_banks_x": [-6.317, 6.287],
                              "main_channel_clear": "no support between x=-6.6 and +6.6 (timber arch ribs span the channel)",
                              "ramps": "x ±13.5 -> ±16.7, deck 1.1 down to bank ≈0.45 (≈11.5°)",
                              "railing_top_above_deck_m": 1.04}
    if name == "quarry_mine":
        meta["sockets"] = {"winch_axle": fbuild.to_gltf((5.7, -1.9, 0.75)), "jib_tip": fbuild.to_gltf((1.3, -1.9, 4.85)),
                           "mine_entrance_centre": fbuild.to_gltf((0, -0.95, 0))}
    core.write_json(os.path.join(RT, f"{asset}.meta.json"), meta)
    core.save_blend(paths.source("landmarks", f"{asset}.blend"))
    print(f"[{asset}] exported {gi['meshes']}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--iter", type=int, default=1)
    ap.add_argument("--textures", action="store_true")
    ap.add_argument("--no-export", action="store_true")
    ap.add_argument("--no-qa", action="store_true")
    a = ap.parse_args(sys.argv[1:])
    if a.textures:
        textures(a.iter)
    allnames = ["bridge27m", "hunter_shelter", "quarry_mine", "ruined_watchpost", "standing_stones", "camp_props",
                "stone_wall", "signpost", "rope_coil", "lantern", "platform"]
    names = allnames if a.name == "all" else (allnames[6:] if a.name == "small" else a.name.split(","))
    for n in names:
        t0 = time.time()
        build(n, a.iter, export=not a.no_export, qa=not a.no_qa)
        print(f"[{n}] {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
