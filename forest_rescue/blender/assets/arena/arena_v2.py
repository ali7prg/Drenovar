"""Boss arena v2 after art/08: an oval of cracked packed dirt (the painting's own floor pixels quilted at true scale,
no tiling) enclosed by NATURAL limestone outcrops (accepted kit lf_env_moss_rock v1-v3, limestone palette) with
grass tufts, dark pines (lf_env_dark_pine v2-v4) and bramble on the rim, the fossil wall (art/08 top right) and the
two red sun-emblem banners at the entrance.  No pillars/totems/stream/loose bones (not in art/08).
Kit meshes are linked duplicates: each unique mesh is stored once in a GLB (glTF mesh instancing).

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/arena/arena_v2.py
Out: godot/project/assets/forest_rescue/arena/lf_boss_arena_assembled{,_lod1,_lod2}.glb + meta (lods/layout),
     forest_rescue/blender/sources/arena/lf_boss_arena_v2.blend, textures/arena/lf_arena_floor_v2_quilt.png
Node names: floor, fossil_wall, rock_NN_<v>, tree_NN_<v>, shrub_NN_<v>, tuft_NN, banner_N / banner_N_rig
(forest_landmarks.gd swaps only cliff_*/pillar_*/fossil_wall meshes: fossil_wall keeps its module LOD1 swap).
"""
import json
import math
import os
import sys

import bpy
import cv2
import numpy as np
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from frlib import core, paths  # noqa: E402

AID = "lf_boss_arena"
FOREST = os.path.join(paths.RUNTIME, "forest")
ARENA = os.path.join(paths.RUNTIME, "arena")
R_IN = 17.5
Z0 = 0.30             # arena root sits 0.3 m below the terrain pad (forest_landmarks.gd)
RNG = np.random.default_rng(81)


def log(*a):
    print("[arena2]", *a, flush=True)


# ------------------------------------------------------------------------------------ floor texture (quilting)
def floor_exemplars():
    art = cv2.cvtColor(cv2.imread(paths.art("08_final_boss_arena.png")), cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    ex = []
    for x0, y0, x1, y1 in ((520, 198, 645, 300), (452, 382, 640, 452), (1112, 238, 1192, 330)):
        c = art[y0:y1, x0:x1]
        c = cv2.resize(c, (c.shape[1], int(c.shape[0] * 1.6)), interpolation=cv2.INTER_CUBIC)   # undo foreshortening
        ex.append(c)
    return ex


def quilt(ex, size=1024, P=44, O=11, cand=700, seed=5):
    rng = np.random.default_rng(seed)
    out = np.zeros((size, size, 3), np.float32)
    step = P - O
    n = (size - O) // step + 1
    srcs = [(e, e.shape[0] - P, e.shape[1] - P) for e in ex]
    for by in range(n):
        for bx in range(n):
            y, x = by * step, bx * step
            if y + P > size or x + P > size:
                y, x = min(y, size - P), min(x, size - P)
            pats = []
            for _ in range(cand):
                e, hy, hx = srcs[rng.integers(len(srcs))]
                yy, xx = rng.integers(0, hy + 1), rng.integers(0, hx + 1)
                pats.append(e[yy:yy + P, xx:xx + P])
            pats = np.stack(pats)
            err = np.zeros(cand, np.float32)
            if bx > 0:
                err += ((pats[:, :, :O] - out[None, y:y + P, x:x + O]) ** 2).sum((1, 2, 3))
            if by > 0:
                err += ((pats[:, :O, :] - out[None, y:y + O, x:x + P]) ** 2).sum((1, 2, 3))
            ok = np.nonzero(err <= err.min() * 1.08 + 1e-6)[0]
            p = pats[rng.choice(ok)].copy()
            mask = np.ones((P, P), bool)
            if bx > 0:   # vertical min-error cut in the left overlap
                e2 = ((p[:, :O] - out[y:y + P, x:x + O]) ** 2).sum(2)
                cost = e2.copy()
                for i in range(1, P):
                    for j in range(O):
                        cost[i, j] += cost[i - 1, max(j - 1, 0):min(j + 2, O)].min()
                j = int(np.argmin(cost[-1]))
                for i in range(P - 1, -1, -1):
                    mask[i, :j] = False
                    if i > 0:
                        lo_, hi_ = max(j - 1, 0), min(j + 2, O)
                        j = lo_ + int(np.argmin(cost[i - 1, lo_:hi_]))
            if by > 0:   # horizontal cut in the top overlap
                e2 = ((p[:O, :] - out[y:y + O, x:x + P]) ** 2).sum(2).T
                cost = e2.copy()
                for i in range(1, P):
                    for j in range(O):
                        cost[i, j] += cost[i - 1, max(j - 1, 0):min(j + 2, O)].min()
                j = int(np.argmin(cost[-1]))
                for i in range(P - 1, -1, -1):
                    mask[:j, i] = False
                    if i > 0:
                        lo_, hi_ = max(j - 1, 0), min(j + 2, O)
                        j = lo_ + int(np.argmin(cost[i - 1, lo_:hi_]))
            region = out[y:y + P, x:x + P]
            region[mask] = p[mask]
    return out


def floor_texture(path, size=1024, extent=50.0):
    ex = floor_exemplars()
    q = quilt(ex, size)
    # low-frequency dust variation + radial rim blend (darker, greener under the rocks), painted warm light
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    X = (xx / size - 0.5) * extent
    Y = (0.5 - yy / size) * extent
    r = np.sqrt(X ** 2 + Y ** 2)
    noise = cv2.GaussianBlur(np.random.default_rng(3).normal(0, 1, (size // 16, size // 16)).astype(np.float32), (0, 0), 1.5)
    noise = cv2.resize(noise, (size, size), interpolation=cv2.INTER_CUBIC)
    q = q * (1.0 + 0.06 * noise[..., None])
    rim = np.clip((r - 17.0) / 5.0, 0, 1)[..., None]
    q = q * (1 - 0.30 * rim) + np.array([0.33, 0.33, 0.20], np.float32) * 0.30 * rim
    core.save_rgba(path, np.clip(q, 0, 1))
    return path


def floor_mesh(name, spacing, extent=25.0):
    """Polar disc r <= 23.5 m (smooth round rim under the rocks) + path tongues (entrance -Y, side paths
    160 / -18 deg) as overlapping strips 5 mm higher; planar UVs over a 50 m square."""
    nseg = int(round(360 / (5.0 * spacing)))
    rings = list(np.arange(spacing * 2.0, 23.5, spacing * 2.0)) + [23.5]
    V, faces = [(0.0, 0.0, Z0 + 0.02)], []

    def zf(x, y, lift=0.0):
        r = math.hypot(x, y)
        return Z0 + 0.02 + lift + 0.30 * max(0.0, (r - 18.5) / 5.0) ** 2 + 0.03 * math.sin(0.7 * x) * math.cos(0.6 * y)
    for ri, r in enumerate(rings):
        for k in range(nseg):
            a = 2 * math.pi * k / nseg
            x, y = r * math.cos(a), r * math.sin(a)
            V.append((x, y, zf(x, y)))
    for k in range(nseg):
        faces.append([0, 1 + k, 1 + (k + 1) % nseg])
    for ri in range(len(rings) - 1):
        b0, b1 = 1 + ri * nseg, 1 + (ri + 1) * nseg
        for k in range(nseg):
            k2 = (k + 1) % nseg
            faces.append([b0 + k, b1 + k, b1 + k2, b0 + k2])
    for ang, half_w in ((-90.0, 3.6), (160.0, 2.4), (-18.0, 2.4)):
        d = math.radians(ang)
        ux, uy = math.cos(d), math.sin(d)
        px, py = -uy, ux
        steps = 6
        base = len(V)
        for i in range(steps + 1):
            t = 22.5 + 9.5 * i / steps
            w = half_w + 0.12 * (t - 22.5)
            for sgn in (-1, 1):
                x, y = ux * t + px * sgn * w, uy * t + py * sgn * w
                V.append((x, y, zf(x, y, 0.005) if t < 24 else Z0 + 0.025 + 0.30 * 1.0))
        for i in range(steps):
            a0 = base + 2 * i
            faces.append([a0, a0 + 2, a0 + 3, a0 + 1])
    V = np.array(V)
    uvs = []
    for f in faces:
        for k in f:
            uvs.append(((V[k, 0] + extent) / (2 * extent), (V[k, 1] + extent) / (2 * extent)))
    return core.mesh_object(name, V, faces, uvs=np.array(uvs), smooth=True)


# ------------------------------------------------------------------------------------ kit import
def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


def kit_meshes(objs):
    out = {}
    for o in objs:
        if o.type == "MESH":
            out[o.name.split(".")[0]] = o
    return out


def place(src, name, loc, yaw_deg, scale, col):
    o = bpy.data.objects.new(name, src.data)        # linked duplicate: shared mesh data (glTF instancing)
    col.objects.link(o)
    base = src.matrix_world.copy()
    base.translation = (0, 0, 0)
    o.matrix_world = Matrix.Translation(loc) @ Matrix.Rotation(math.radians(yaw_deg), 4, "Z") @ \
        Matrix.Diagonal((scale, scale, scale, 1.0)) @ base
    return o


def main():
    core.reset()
    kit = {}
    for f in ("lf_env_moss_rock", "lf_env_dark_pine", "lf_env_bramble", "lf_env_grass_tuft"):
        kit.update(kit_meshes(import_glb(os.path.join(FOREST, f + ".glb"))))
    fossil = kit_meshes(import_glb(os.path.join(ARENA, "lf_arena_fossil_wall.glb")))
    ban_objs = import_glb(os.path.join(ARENA, "lf_arena_banner.glb"))
    for o in list(kit.values()) + list(fossil.values()) + ban_objs:
        o.hide_render = True
    log("kit:", sorted(kit))
    # limestone palette for the v2/v3 boulders and ledges
    lime = None
    for m in bpy.data.materials:
        if m.name.startswith("lf_rock_limestone"):
            lime = m
    for k, o in kit.items():
        if k.startswith("lf_env_moss_rock_v2") or k.startswith("lf_env_moss_rock_v3"):
            for i, s in enumerate(o.data.materials):
                if s and s.name.startswith("lf_rock_quarry") and lime is not None:
                    o.data.materials[i] = lime
    # floor
    tex = floor_texture(paths.texture_master("arena", "lf_arena_floor_v2_quilt.png"))
    img = core.load_image(tex, "sRGB", "lf_arena_floor_v2")
    fmat = core.material("lf_arena_floor_v2", base_tex=img, rough=0.95)

    # layout (Blender: entrance gap toward -Y = glTF +Z; angles CCW from +X)
    slots = [-66, -40, 2, 22, 42, 96, 119, 141, 178, 201, 224, 247]
    inner = [((-10.2, 6.0), 20.0, "v1", 0.62), ((-13.0, -0.6), 75.0, "v2", 1.05), ((13.0, 0.6), -30.0, "v1", 0.55),
             ((7.0, -10.5), 10.0, "v2", 0.9)]
    banners = [(-101.0, 14.6), (-79.0, 14.6)]     # flank the entrance path in front of the outcrops

    def build(level):
        col = core.collection(f"arena_v2_lod{level}")
        objs = []
        fl = floor_mesh("floor", (1.3, 2.0, 3.6)[level])
        core.assign(fl, fmat)
        objs.append(fl)
        rl = ("LOD1", "LOD2", "LOD2")[level]
        tl = ("LOD1", "LOD2", "LOD2")[level]
        k = 0
        for si, ang in enumerate(slots):
            a = math.radians(ang)
            pieces = [("v1", 0.0, 0.0, 0.85 + 0.25 * RNG.random()), ("v3", 0.55, 2.2, 0.8 + 0.2 * RNG.random()),
                      ("v2", -0.6, 1.6, 0.7 + 0.3 * RNG.random())]
            if level == 2:
                pieces = pieces[:1]
            for (v, dang, dr, sc) in pieces:
                aa = a + dang / R_IN * 3.0
                r = R_IN + 1.6 - dr * 0.5 + (0.0 if v == "v1" else -1.2)
                loc = (r * math.cos(aa), r * math.sin(aa), Z0 - 0.15)
                lod = rl if (v == "v1" or level > 0) else "LOD2"      # small boulders use the light kit LOD
                o = place(kit[f"lf_env_moss_rock_{v}_{lod}"], f"rock_{k:02d}_{v}", loc, math.degrees(aa) - 90 + RNG.uniform(-20, 20),
                          sc, col)
                objs.append(o)
                k += 1
        for (x, y), rot, v, sc in inner:
            o = place(kit[f"lf_env_moss_rock_{v}_{rl}"], f"rock_{k:02d}_{v}", (x, y, Z0 - 0.1), rot, sc, col)
            objs.append(o)
            k += 1
        # rim: dark pines and bramble outside the outcrops (none across the entrance gap)
        t = 0
        tree_angles = [a for a in np.arange(-60, 260, 17.0)]
        for ang in tree_angles:
            if level == 2 and t % 2:
                t += 1
                continue
            a = math.radians(ang + RNG.uniform(-5, 5))
            r = R_IN + 6.5 + RNG.uniform(0, 4.5)
            v = ("v2", "v3", "v4")[t % 3]
            o = place(kit[f"lf_env_dark_pine_{v}_{tl}"], f"tree_{t:02d}_{v}", (r * math.cos(a), r * math.sin(a), Z0 - 0.2),
                      RNG.uniform(0, 360), 0.75 + 0.3 * RNG.random(), col)
            objs.append(o)
            t += 1
        if level < 2:
            sb = 0
            for ang in np.arange(-75, 255, 23.0):
                a = math.radians(ang + RNG.uniform(-6, 6))
                r = R_IN + 3.2 + RNG.uniform(0, 1.5)
                v = ("v1", "v2", "v3")[sb % 3]
                o = place(kit[f"lf_env_bramble_{v}_{tl}"], f"shrub_{sb:02d}_{v}", (r * math.cos(a), r * math.sin(a), Z0),
                          RNG.uniform(0, 360), 0.9 + 0.3 * RNG.random(), col)
                objs.append(o)
                sb += 1
            tf = 0
            for ang in np.arange(-80, 262, 9.0):
                a = math.radians(ang + RNG.uniform(-3, 3))
                r = R_IN - 0.4 + RNG.uniform(-0.6, 0.8)
                v = ("v1", "v2")[tf % 2]
                o = place(kit[f"lf_env_grass_tuft_{v}_{'LOD0' if level == 0 else 'LOD1'}"], f"tuft_{tf:02d}",
                          (r * math.cos(a), r * math.sin(a), Z0), RNG.uniform(0, 360), 1.0 + 0.5 * RNG.random(), col)
                objs.append(o)
                tf += 1
        # fossil wall at 68 deg on the ring (art/08 top right); module LOD0 only in LOD0
        a = math.radians(68.0)
        fsrc = fossil["lf_arena_fossil_wall_LOD0" if level == 0 else "lf_arena_fossil_wall_LOD1"]
        objs.append(place(fsrc, "fossil_wall", (R_IN * math.cos(a), R_IN * math.sin(a), Z0 - 0.3), 68.0 - 90.0, 1.0, col))
        # banners: armature copies with the wind clip
        arm_src = [o for o in ban_objs if o.type == "ARMATURE"][0]
        ban_meshes = [o for o in ban_objs if o.type == "MESH" and not o.name.lower().startswith("icosphere")]
        mesh_src = max(ban_meshes, key=lambda o: len(o.data.polygons) + (10 ** 6 if "banner" in o.name.lower() else 0))
        for i, (ang, r) in enumerate(banners):
            a = math.radians(ang)
            arm_i = arm_src.copy()
            arm_i.name = f"banner_{i}_rig"
            col.objects.link(arm_i)
            arm_i.matrix_world = Matrix.Translation((r * math.cos(a), r * math.sin(a), Z0)) @ \
                Matrix.Rotation(a + math.pi / 2, 4, "Z")
            arm_i.hide_render = False
            mesh_i = mesh_src.copy()
            mesh_i.name = f"banner_{i}"
            col.objects.link(mesh_i)
            mesh_i.parent = arm_i
            mesh_i.matrix_parent_inverse = Matrix.Identity(4)
            mesh_i.matrix_basis = Matrix.Identity(4)
            for m in mesh_i.modifiers:
                if m.type == "ARMATURE":
                    m.object = arm_i
            mesh_i.hide_render = False
            act = bpy.data.actions.get("lf_banner_wind")
            if act is not None:
                arm_i.animation_data_create()
                arm_i.animation_data.action = act
            objs += [arm_i, mesh_i]
        return objs

    out_meta = {}
    names = {0: f"{AID}_assembled.glb", 1: f"{AID}_assembled_lod1.glb", 2: f"{AID}_assembled_lod2.glb"}
    for level in (0, 1, 2):
        objs = build(level)
        tris = sum(core.tri_count(o) for o in objs if o.type == "MESH")
        path = os.path.join(ARENA, names[level])
        core.export_glb(path, objs, animations=True)
        out_meta[f"LOD{level}"] = {"file": names[level], "tris": tris, "bytes": os.path.getsize(path),
                                   "nodes": len(objs)}
        log(f"LOD{level}: {tris} tris, {len(objs)} nodes, {os.path.getsize(path) / 1e6:.2f} MB")
        for o in objs:
            o.hide_render = True
            o.hide_viewport = True
    mp = os.path.join(ARENA, f"{AID}_assembled.meta.json")
    meta = json.load(open(mp))
    meta["tris"] = {"LOD0_total": out_meta["LOD0"]["tris"]}
    meta["lods"] = dict(out_meta, note="v2 (art/08 rebuild): same node names in every LOD file; suggested use LOD0 "
                                       "zoom <= 34, LOD1 zoom <= 85, LOD2 beyond")
    meta["layout"] = {"ring_slots_deg": slots, "fossil": 68.0, "inner_outcrops": [[list(p), r, v, s] for p, r, v, s in inner],
                      "banners": banners, "removed": ["pillars (carved totems)", "loose floor bones", "stream piece"],
                      "kit": "lf_env_moss_rock v1-v3 (limestone material), lf_env_dark_pine v2-v4, lf_env_bramble v1-v3, "
                             "lf_env_grass_tuft v1-v2 as linked duplicates (glTF mesh instancing)"}
    meta["generation"] = "v2 rebuild after art/08 (natural limestone enclosure, quilted painted floor)"
    meta["floor"] = {"texture": "art/08 floor pixels quilted (Efros-Freeman) at ~20 px/m over 50 m, rim blend under the "
                                "rocks", "radius_m": 23.5, "height_local_m": Z0 + 0.02}
    core.write_json(mp, meta)
    core.save_blend(paths.source("arena", f"{AID}_v2.blend"))
    print("ARENA2", json.dumps(out_meta))


if __name__ == "__main__":
    main()
