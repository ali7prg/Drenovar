"""Strategic-camera forest patch QA (vs art/01 masterplan and art/07 fog storyboard).

Imports the exported kit GLBs, instances LOD meshes (linked duplicates) on a 64x64 m patch with a dirt
path and a clearing, renders: top-down ortho, strategic ortho pitch 55 deg (LOD0 and far LOD1/LOD2),
and a 40 deg perspective like the 07 panels; writes side-by-sides with reference crops.

Run: python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/forest/build_forest_qa.py [--iter N]
"""
import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fbuild  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from frlib import core, paths, refs, render  # noqa: E402
import fqa  # noqa: E402

RT = fbuild.RUNTIME_DIR
KIT = {"golden_oak": ["v1", "v2", "v3", "v4"], "dark_pine": ["v1", "v2", "v3", "v4"], "birch": ["v1", "v2", "v3"],
       "willow": ["v1", "v2", "v3"], "hollow_oak": ["v1"]}
GC = {"bramble": ["v1", "v2", "v3"], "reed_fern": ["fern_v1", "fern_v2"], "moss_rock": ["v2", "v3"],
      "grass_tuft": ["v1", "v2", "v3"], "fallen_branches": ["v1", "v2"], "mushrooms": ["v1"]}


def kit_variants(asset):
    import json
    p = os.path.join(RT, f"lf_env_{asset}.meta.json")
    if not os.path.exists(p):
        return []
    return list(json.load(open(p)).get("variants", {}).keys())


def import_meshes(asset):
    path = os.path.join(RT, f"lf_env_{asset}.glb")
    if not os.path.exists(path):
        return {}
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    out = {}
    for o in new:
        if o.type == "MESH":
            out[o.name] = o
            o.hide_render = True
            o.hide_viewport = True
    return out


def poisson(rng, n, lo, hi, rmin, avoid):
    pts = []
    tries = 0
    while len(pts) < n and tries < n * 200:
        tries += 1
        p = rng.uniform(lo, hi, 2)
        if avoid(p):
            continue
        if pts and np.min(np.linalg.norm(np.array(pts) - p, axis=1)) < rmin:
            continue
        pts.append(p)
    return np.array(pts)


def ground(size=90):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, 0))
    g = bpy.context.active_object
    m = bpy.data.materials.new("qa_forest_ground")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.12
    noise.inputs["Detail"].default_value = 8.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.20, 0.22, 0.09, 1)
    ramp.color_ramp.elements[1].color = (0.42, 0.40, 0.18, 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 1.0
    g.data.materials.append(m)
    return g


def path_strip(points, width=2.6):
    pts = np.array(points, float)
    verts, faces = [], []
    for i, p in enumerate(pts):
        d = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
        d = d / (np.linalg.norm(d) + 1e-9)
        n = np.array([-d[1], d[0]])
        w = width * (0.9 + 0.2 * math.sin(i * 1.7))
        verts += [(*(p + n * w / 2), 0.02), (*(p - n * w / 2), 0.02)]
        if i:
            a = 2 * (i - 1)
            faces.append((a, a + 1, a + 3, a + 2))
    o = core.mesh_object("qa_path", np.array(verts), faces)
    m = bpy.data.materials.new("qa_path_mat")
    m.use_nodes = True
    m.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = (0.55, 0.45, 0.30, 1)
    o.data.materials.append(m)
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=int, default=1)
    ap.add_argument("--samples", type=int, default=24)
    a = ap.parse_args(sys.argv[1:])
    core.reset()
    meshes = {}
    for asset in list(KIT) + list(GC):
        meshes.update(import_meshes(asset))
        have = kit_variants(asset)
        if asset in KIT and have:
            KIT[asset] = [v for v in KIT[asset] if v in have] or have[:1]
        if asset in GC and have:
            GC[asset] = [v for v in GC[asset] if v in have] or have[:1]
    print("imported", len(meshes), flush=True)
    rng = np.random.default_rng(42)
    path_pts = [(-34, -10 + 6 * math.sin(t * 0.25)) for t in range(0)] or \
        [(x, 4 * math.sin(x * 0.09) - 2) for x in np.linspace(-36, 36, 40)]
    clearing = np.array([10.0, 10.0])

    def avoid(p):
        if np.linalg.norm(p - clearing) < 8.0:
            return True
        y_path = 4 * math.sin(p[0] * 0.09) - 2
        return abs(p[1] - y_path) < 3.2
    trees = poisson(rng, 130, -30, 30, 4.2, avoid)
    placed = {lod: [] for lod in range(3)}

    def place(name, p, lod, yaw, s):
        src = meshes.get(name)
        if src is None:
            return
        o = bpy.data.objects.new(name + "_inst", src.data)
        bpy.context.scene.collection.objects.link(o)
        o.location = (p[0], p[1], 0)
        o.rotation_euler = (0, 0, yaw)
        o.scale = (s, s, s)
        placed[lod].append(o)
    species_w = [("golden_oak", 0.52), ("dark_pine", 0.24), ("birch", 0.16), ("willow", 0.04), ("hollow_oak", 0.0)]
    names = [s for s, w in species_w]
    w = np.array([w for s, w in species_w])
    w /= w.sum()
    for i, p in enumerate(trees):
        sp = names[rng.choice(len(names), p=w)]
        if np.linalg.norm(p - np.array([-18, 14])) < 5:
            continue
        v = KIT[sp][rng.integers(len(KIT[sp]))]
        yaw = rng.uniform(0, 6.28)
        s = rng.uniform(0.8, 1.2) if sp != "golden_oak" else rng.uniform(0.6, 0.95)
        for lod in range(3):
            place(f"lf_env_{sp}_{v}_LOD{lod}", p, lod, yaw, s)
    for lod in range(3):
        place("lf_env_hollow_oak_v1_LOD%d" % lod, np.array([-18, 14]), lod, 0.6, 0.85)
    under = poisson(rng, 160, -31, 31, 1.6, lambda p: abs(p[1] - (4 * math.sin(p[0] * 0.09) - 2)) < 1.6)
    for p in under:
        k = rng.choice(list(GC))
        v = GC[k][rng.integers(len(GC[k]))]
        for lod in range(3):
            place(f"lf_env_{k}_{v}_LOD{lod}", p, lod, rng.uniform(0, 6.28), rng.uniform(0.8, 1.3))
    print("instances", {k: len(v) for k, v in placed.items()}, flush=True)
    g = ground()
    pth = path_strip(path_pts)
    fqa.studio(a.samples)
    fqa.use_ao([o for l in range(3) for o in placed[l]], True)
    sc = bpy.context.scene
    sc.render.film_transparent = False
    sc.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.6, 0.65, 1)
    sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    base = [g, pth]
    out = {}
    for lod in range(3):
        for l2 in range(3):
            for o in placed[l2]:
                o.hide_render = l2 != lod
        for o in base:
            o.hide_render = False
        if lod == 0:
            render.perspective_camera((0, -0.01, 120), (0, 0, 0), res=(1200, 1200), ortho_scale=64)
            core.save_rgba(fqa.iter_path("forest_patch", a.iter, "top_LOD0"), render.render_rgba()[..., :3])
            cam = render.perspective_camera((0, -84, 120), (0, 0, 0), res=(1500, 1000), ortho_scale=62)
        else:
            render.perspective_camera((0, -84, 120), (0, 0, 0), res=(1500, 1000), ortho_scale=62)
        img = render.render_rgba()[..., :3]
        core.save_rgba(fqa.iter_path("forest_patch", a.iter, f"strategic55_LOD{lod}"), img)
        out[lod] = img
    # 07-like perspective along the path (LOD0)
    for l2 in range(3):
        for o in placed[l2]:
            o.hide_render = l2 != 0
    render.perspective_camera((-30, -26, 22), (2, 4, 0), lens=30, res=(1000, 1500))
    persp = render.render_rgba()[..., :3]
    ref01 = refs.crop(refs.load("01_world_masterplan.png"), (40, 30, 600, 420))
    ref07 = refs.crop(refs.load("07_fog_exploration_interface.png"), (520, 8, 1020, 875))
    render.side_by_side([ref01, out[0], out[1], out[2]], ["art/01 NW golden-oak woods", "kit LOD0 strategic 55deg (ortho)",
                                                         "kit LOD1", "kit LOD2"],
                        fqa.iter_path("forest_patch", a.iter, "vs_01"), height=620)
    render.side_by_side([ref07, persp], ["art/07 centre panel", "kit LOD0 perspective ~40deg"],
                        fqa.iter_path("forest_patch", a.iter, "vs_07"), height=900)
    tris = {lod: sum(core.tri_count(o) for o in placed[lod] if True) for lod in range(1)}
    print("done", flush=True)


if __name__ == "__main__":
    main()
