"""QA renders for the boss arena: assembled 3/4 view vs art/08 (top), module call-outs vs the bottom row."""
import math
import os

import bpy
import numpy as np
from mathutils import Vector

from frlib import core, paths, refs, render

AID = "lf_boss_arena"
REF = "08_final_boss_arena.png"
TOP_BOX = (0, 0, 1536, 716)
CALLOUTS = {"lf_arena_cliff_a": (0, 720, 612, 1012), "lf_arena_fossil_wall": (614, 720, 1186, 1012),
            "lf_arena_pillar_a": (1188, 720, 1536, 1012)}


def out(name):
    return paths.compare(AID, name)


def scene_light():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = "Standard"
    sc.render.film_transparent = False
    w = bpy.data.worlds.get("arena_world") or bpy.data.worlds.new("arena_world")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.42, 0.47, 0.52, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    for o in [o for o in bpy.data.objects if o.name.startswith("qa_sun")]:
        bpy.data.objects.remove(o, do_unlink=True)
    sun = bpy.data.lights.new("qa_sun", "SUN")
    sun.energy = 3.6
    sun.angle = math.radians(4)
    so = bpy.data.objects.new("qa_sun", sun)
    so.rotation_euler = (math.radians(42), math.radians(-28), math.radians(-35))
    sc.collection.objects.link(so)


def ground_plane():
    if "qa_ground" in bpy.data.objects:
        return
    me = bpy.data.meshes.new("qa_ground")
    s = 70
    me.from_pydata([(-s, -s, -0.08), (s, -s, -0.08), (s, s, -0.08), (-s, s, -0.08)], [], [(0, 1, 2, 3)])
    o = bpy.data.objects.new("qa_ground", me)
    bpy.context.scene.collection.objects.link(o)
    m = core.material("qa_ground_mat", base=(0.16, 0.20, 0.13, 1), rough=1.0)
    o.data.materials.append(m)


def try_boss(col):
    """Place the boss (LOD0 + rig, idle) for scale if its master blend exists."""
    p = paths.source("boss", "lf_boss_ancient_maw.blend")
    if not os.path.exists(p) or "lf_boss_ancient_maw_LOD0" in bpy.data.objects:
        return None
    with bpy.data.libraries.load(p, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in ("lf_boss_ancient_maw_rig", "lf_boss_ancient_maw_LOD0")]
    for o in dst.objects:
        col.objects.link(o)
    arm = bpy.data.objects.get("lf_boss_ancient_maw_rig")
    if arm:
        arm.location = (-0.6, 1.4, 0.0)
        arm.rotation_euler = (0, 0, math.radians(-95))
    return arm


def run(iter_tag, placed, banners, mods, floor):
    scene_light()
    ground_plane()
    for o in bpy.data.objects:
        if o.type == "MESH" and not (o.users_collection and o.users_collection[0].name == "assembled") \
                and o.name != "qa_ground" and not o.name.startswith("lf_boss_ancient_maw"):
            o.hide_render = True
    col = bpy.data.collections.get("assembled")
    try_boss(col)
    sc = bpy.context.scene
    # camera reproducing the 08 framing: from the south, ~32 deg elevation, centre slightly behind middle
    for name, (loc, look, lens) in {"iter{}_assembled_q34": ((0.0, -50.0, 31.0), (0.0, 2.0, 0.0), 30.0)}.items():
        render.perspective_camera(loc, look, lens=lens, res=(1536, 716))
        rgba = render.render_rgba()
        ref = refs.crop(refs.load(REF), TOP_BOX)
        png = out(name.format(iter_tag) + ".png")
        render.side_by_side([ref, rgba], ["art/08 (top)", f"assembled render iter{iter_tag}"], png, height=520)
    render.perspective_camera((0.0, -0.1, 60.0), (0.0, 0.0, 0.0), lens=30.0, res=(1024, 1024))
    rgba = render.render_rgba()
    core.save_rgba(out(f"iter{iter_tag}_assembled_top.png"), rgba[..., :3])
    # module call-outs (single module, studio-ish)
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = True
    bpy.data.objects["qa_ground"].hide_render = False
    for mid, box in CALLOUTS.items():
        key = mid.replace("lf_arena_", "")
        key = "fossil" if key.startswith("fossil") else key
        l0 = mods[key][0]
        l0.hide_render = False
        lo, hi = core.bounds([l0])
        c = (Vector(lo) + Vector(hi)) / 2
        size = (Vector(hi) - Vector(lo)).length
        cam = c + Vector((-0.35, -1.0, 0.42)).normalized() * size * 1.25
        render.perspective_camera(tuple(cam), tuple(c), lens=40, res=(box[2] - box[0], box[3] - box[1]))
        rgba = render.render_rgba()
        ref = refs.crop(refs.load(REF), box)
        render.side_by_side([ref, rgba], [f"art/08 call-out", f"{mid} iter{iter_tag}"], out(f"iter{iter_tag}_{mid}.png"),
                            height=360)
        l0.hide_render = True
    print("[arena_qa] done", flush=True)
