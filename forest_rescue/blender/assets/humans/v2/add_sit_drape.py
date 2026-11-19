"""Seated cloth for the civilians: Blender cloth simulation baked into a corrective morph `sit_drape`.

For one character's .blend (built by build_v2.py --stage full):
  1. cloth = LOD0 faces skinned to the skirt / apron / cloak chain (SkirtFront*, SkirtBack*, SkirtLeft/Right,
     Cloak1/2); pinned where those weights fade out (waist band, shoulders);
  2. the armature plays stand_up in reverse at half speed (standing -> seated on the cage floor, cloth bones
     neutral) and then holds the seated pose; the cloth simulates against the body (collision) and the floor
     plane (the seat), so it drapes over the thighs and hangs between / over the knees;
  3. the settled drape is converted to rest-space deltas through the seated skinning matrices and stored as
     the morph `sit_drape` on LOD0 (LOD1/LOD2 by nearest-vertex transfer);
  4. clips: cloth bones neutral in cage_sit and while the morph is on in stand_up; morph weight 1 in cage_sit,
     1 -> 0 in stand_up as the thighs come down (driven by the thigh angle), 0 in every other clip (the morph
     curves live in the same actions, KEY slot, exported as glTF morph-weight channels);
  5. QA: draped cloth renders (front / side / 3/4) to qa/video/<id>/sit_drape_*.png; GLB + meta re-exported.

    python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/humans/v2/add_sit_drape.py <asset_id>
        [--src <blend>] [--dry <out_dir>]
"""
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))

import bpy  # noqa: E402
import bmesh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Quaternion  # noqa: E402

from frlib import core, paths, render  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
AID = ARGS[0]
SRC = ARGS[ARGS.index("--src") + 1] if "--src" in ARGS else None
DRY = ARGS[ARGS.index("--dry") + 1] if "--dry" in ARGS else None
CLOTH = ("SkirtFront1", "SkirtFront2", "SkirtBack1", "SkirtBack2", "SkirtLeft", "SkirtRight", "Cloak1", "Cloak2")
SLOW = 3                  # simulated sit-down runs at half the clip speed (collision robustness)
HOLD = 50                 # frames held in the seated pose to settle
OFF_ANGLE = 38.0          # stand_up: morph reaches 0 when the thighs are this many degrees from vertical
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


def slot_of(act, id_type):
    for s in act.slots:
        if s.target_id_type == id_type:
            return s
    return None


def fcurves(act, id_type="OBJECT"):
    from bpy_extras import anim_utils
    slot = slot_of(act, id_type)
    cb = anim_utils.action_get_channelbag_for_slot(act, slot) if slot else None
    return list(cb.fcurves) if cb else []


def cloth_curves(act):
    by_bone = {}
    for fc in fcurves(act):
        for b in CLOTH:
            if fc.data_path == f'pose.bones["{b}"].rotation_quaternion':
                by_bone.setdefault(b, {})[fc.array_index] = fc
    return {b: c for b, c in by_bone.items() if len(c) == 4}


def neutralize(act, t_of_frame):
    """Cloth-bone quaternion keys -> slerp(identity, original, t(frame))."""
    for b, comps in cloth_curves(act).items():
        for k in range(len(comps[0].keyframe_points)):
            f = comps[0].keyframe_points[k].co[0]
            q = Quaternion([comps[i].keyframe_points[k].co[1] for i in range(4)])
            qq = Quaternion((1, 0, 0, 0)).slerp(q, t_of_frame(f))
            for i in range(4):
                comps[i].keyframe_points[k].co[1] = qq[i]
                comps[i].keyframe_points[k].handle_left[1] = qq[i]
                comps[i].keyframe_points[k].handle_right[1] = qq[i]
        for fc in comps.values():
            fc.update()


def pose_at(arm, act, frame):
    arm.animation_data.action = act
    arm.animation_data.action_slot = slot_of(act, "OBJECT")
    bpy.context.scene.frame_set(int(frame))
    return {pb.name: pb.matrix_basis.copy() for pb in arm.pose.bones}


def thigh_angle(arm):
    a = []
    for S in ("Left", "Right"):
        pb = arm.pose.bones.get(f"{S}UpperLeg")
        d = np.array(pb.matrix)[:3, 1]
        d = d / np.linalg.norm(d)
        a.append(math.degrees(math.acos(float(np.clip(-d[2], -1, 1)))))
    return max(a)


def snapshots(objs, out_dir, label, colors, ctype="OBJECT"):
    """Workbench renders (front / side / 3/4) of the given objects, joined into one PNG."""
    from PIL import Image
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = ctype
    sh.show_shadows = False
    sh.show_cavity = False
    hidden = {o.name: o.hide_render for o in sc.objects}
    for o in sc.objects:
        o.hide_render = o not in objs
    for o, c in zip(objs, colors):
        o.color = c
    tiles = []
    tgt = (0.0, 0.12, 0.40)
    for nm, loc in (("front", (0.0, -4.0, 0.55)), ("side", (4.0, 0.12, 0.55)), ("q34", (2.6, -2.6, 1.6)),
                    ("back", (0.0, 4.2, 0.9))):
        render.perspective_camera(loc, tgt, res=(420, 420), ortho_scale=1.45)
        tiles.append(render.render_rgba())
    for o in sc.objects:
        if o.name in hidden:
            o.hide_render = hidden[o.name]
    img = np.concatenate(tiles, axis=1)
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, f"{label}.png")
    Image.fromarray((np.clip(img[..., :3], 0, 1) * 255).astype(np.uint8)).save(p)
    return p


LEG = {"LeftUpperLeg", "RightUpperLeg", "LeftLowerLeg", "RightLowerLeg", "LeftFoot", "RightFoot", "LeftToes", "RightToes"}
FORE = ("LowerArm", "Hand", "Thumb", "Index", "Middle", "Ring", "Pinky", "Prop")


def islands(o):
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    nv = len(o.data.vertices)
    e = np.zeros(len(o.data.edges) * 2, np.int32)
    o.data.edges.foreach_get("vertices", e)
    e = e.reshape(-1, 2)
    A = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(nv, nv))
    return connected_components(A, directed=False)[1]


def vweights(o):
    gi = {g.index: g.name for g in o.vertex_groups}
    return [{gi[ge.group]: ge.weight for ge in v.groups if ge.weight > 0} for v in o.data.vertices]


def reweight_garments(o):
    """Skirt / apron / cloak islands: weights on leg bones move to the vertex's dominant cloth bone (or Hips),
    so a seated pose with neutral cloth bones leaves the garment hanging rigidly from the hips (no boards /
    wings from blending with 140-degree thigh rotations) and the inverse skinning of the morph is well posed.
    Returns (moved, n_islands, garment-vertex mask, island labels)."""
    W = vweights(o)
    lab = islands(o)
    cw = np.array([sum(w for n, w in d.items() if n in CLOTH) for d in W])
    garment = set()
    for li in np.unique(lab[cw > 0.03]):
        m = lab == li
        if (cw[m] > 0.03).mean() >= 0.15:
            garment.add(int(li))
    moved = 0
    for i, d in enumerate(W):
        if int(lab[i]) not in garment:
            continue
        wl = sum(w for n, w in d.items() if n in LEG)
        if wl <= 0:
            continue
        cl = {n: w for n, w in d.items() if n in CLOTH}
        tgt = max(cl, key=cl.get) if cl else "Hips"
        for n in [n for n in d if n in LEG]:
            o.vertex_groups[n].remove([i])
        g = o.vertex_groups.get(tgt) or o.vertex_groups.new(name=tgt)
        g.add([i], wl, "ADD")
        moved += 1
    mask = np.array([int(l) in garment for l in lab])
    return moved, len(garment), mask, lab


def build_proxy(lo0, arm, mask, lab, step=0.032):
    """Single-layer, hole-free quad sheet over the outer surface of every garment island: a cylindrical
    (arc, z) grid around the body axis, each column spanning that column's waist-to-hem extent, radius from
    the outer garment layer; skin weights + pin weights from the nearest garment vertices."""
    from scipy.spatial import cKDTree
    W = vweights(lo0)
    rest = np.array([v.co[:] for v in lo0.data.vertices])
    cw = np.array([sum(w for n, w in d.items() if n in CLOTH) for d in W])
    bones = arm.data.bones
    verts, faces, wts, pins = [], [], [], []
    for li in sorted(set(lab[mask].tolist())):
        idx = np.where(lab == li)[0]
        P = rest[idx]
        zref = np.percentile(P[:, 2], 80)
        cand = [b for b in ("Hips", "Spine", "Chest", "UpperChest") if b in bones]
        bb = min(cand, key=lambda b: abs(bones[b].head_local.z - zref))
        cx, cy = 0.0, bones[bb].head_local.y
        phi = np.arctan2(P[:, 0] - cx, -(P[:, 1] - cy))
        r = np.hypot(P[:, 0] - cx, P[:, 1] - cy)
        rbar = float(np.median(r))
        ps = np.sort(phi)
        gaps = np.diff(np.concatenate([ps, [ps[0] + 2 * np.pi]]))
        g = int(np.argmax(gaps))
        closed = gaps[g] < math.radians(25)
        start = -np.pi if closed else ps[(g + 1) % len(ps)]
        span = 2 * np.pi if closed else 2 * np.pi - gaps[g]
        ncol = max(2, int(math.ceil(span * rbar / step)) + (0 if closed else 1))
        sv = np.mod(phi - start, 2 * np.pi) * rbar           # arc coordinate of the garment vertices
        L = 2 * np.pi * rbar
        zmax, zmin = P[:, 2].max(), P[:, 2].min()
        nrow = max(2, int(math.ceil((zmax - zmin) / step)) + 1)
        zs = np.linspace(zmax, zmin, nrow)
        node = {}
        for i in range(ncol):
            si = i * span * rbar / (ncol if closed else (ncol - 1))
            ds = np.abs(sv - si)
            if closed:
                ds = np.minimum(ds, L - ds)
            near = ds < 1.5 * step
            if near.sum() < 2:
                continue
            zt, zb = P[near, 2].max(), P[near, 2].min()
            rows = [j for j, z in enumerate(zs) if zb - 0.35 * step <= z <= zt + 0.35 * step]
            for t, j in enumerate(rows):
                z = zs[j]
                m = near & (np.abs(P[:, 2] - z) < 1.5 * step)
                if not m.any():
                    m = near
                rr = float(np.percentile(r[m], 85))
                ang = start + si / rbar
                node[(i, j)] = len(verts)
                verts.append((cx + rr * math.sin(ang), cy - rr * math.cos(ang), float(z)))
                k = idx[m][int(np.argmin(np.abs(P[m, 2] - z) + ds[m]))]
                wts.append(W[k])
                pn = float(np.clip(1.0 - (cw[idx[m]].mean() - 0.05) / 0.25, 0.0, 1.0))
                pins.append(1.0 if t == 0 else pn)
        for i in range(ncol if closed else ncol - 1):
            i2 = (i + 1) % ncol
            for j in range(nrow - 1):
                q = [(i, j), (i2, j), (i2, j + 1), (i, j + 1)]
                if all(n in node for n in q):
                    faces.append([node[n] for n in q])
        log("proxy island", li, "closed" if closed else f"arc {math.degrees(span):.0f} deg", "columns", ncol,
            "rows", nrow, "axis", bb)
    me = bpy.data.meshes.new("_cloth_proxy")
    me.from_pydata(verts, [], faces)
    me.update()
    pr = bpy.data.objects.new("_cloth_proxy", me)
    bpy.context.scene.collection.objects.link(pr)
    pr.matrix_world = lo0.matrix_world.copy()
    for j, d in enumerate(wts):
        for n, w in d.items():
            if n in bones:
                (pr.vertex_groups.get(n) or pr.vertex_groups.new(name=n)).add([j], w, "REPLACE")
    pg = pr.vertex_groups.new(name="_pin")
    for j, pn in enumerate(pins):
        pg.add([j], pn, "REPLACE")
    am = pr.modifiers.new("Armature", "ARMATURE")
    am.object = arm
    bm = bmesh.new()
    bm.from_mesh(me)
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(me)
    bm.free()
    return pr


def rot_between(a, b):
    a = a / (np.linalg.norm(a) + 1e-12)
    b = b / (np.linalg.norm(b) + 1e-12)
    v = np.cross(a, b)
    s = np.linalg.norm(v)
    c = float(np.dot(a, b))
    if s < 1e-8:
        return np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * ((1 - c) / (s * s))


def skin_matrices(arm):
    return {pb.name: np.array(pb.matrix) @ np.linalg.inv(np.array(arm.data.bones[pb.name].matrix_local))
            for pb in arm.pose.bones}


def lbs(o, gi, Bm, idx):
    M = np.zeros((4, 4))
    tot = 0.0
    for ge in o.data.vertices[int(idx)].groups:
        b = gi[ge.group]
        if b in Bm and ge.weight > 0:
            M += ge.weight * Bm[b]
            tot += ge.weight
    return M / tot if tot > 0 else np.eye(4)


def main():
    src = SRC or paths.source("humans", f"{AID}.blend")
    bpy.ops.wm.open_mainfile(filepath=src)
    sc = bpy.context.scene
    arm = bpy.data.objects[f"{AID}_rig"]
    lods = [bpy.data.objects[f"{AID}_LOD{k}"] for k in range(3)]
    lo0 = lods[0]
    acts = {a.name: a for a in bpy.data.actions}
    sit, up = acts["lf_civilian_cage_sit"], acts["lf_civilian_stand_up"]
    if arm.animation_data is None:
        arm.animation_data_create()
    qa_dir = DRY or os.path.join(paths.QA_VIDEO, AID)
    # ---- garments hang from the hips / chest only: leg weights on garment islands -> their cloth bone
    gmask = {}
    for o in lods:
        moved, isl, mask, lab = reweight_garments(o)
        gmask[o.name] = (mask, lab)
        log(o.name, "garment islands", isl, "garment verts", int(mask.sum()), "re-weighted from the legs", moved)
    mask0, lab0 = gmask[lo0.name]
    if mask0.sum() < 20:
        log("no cloth on", AID)
        return
    nv = len(lo0.data.vertices)
    # ---- stand_up timing from the thigh angle (before any edits)
    n_up = int(round(up.frame_range[1]))
    ang = []
    for f in range(n_up + 1):
        pose_at(arm, up, f)
        ang.append(thigh_angle(arm))
    ang = np.array(ang)
    a0, a1 = ang[0], ang[-1] + OFF_ANGLE
    x = np.clip((ang - a1) / max(a0 - a1, 1e-3), 0, 1)
    x = np.minimum.accumulate(x)               # monotone: never re-applies once fading
    w_up = x * x * (3 - 2 * x)
    f_off = int(np.argmax(w_up <= 0.0)) if (w_up <= 0.0).any() else n_up
    log("stand_up thigh angle", round(float(a0), 1), "->", round(float(ang[-1]), 1), "deg; morph off at frame", f_off)
    log("transforms identity:", np.allclose(np.array(arm.matrix_world), np.eye(4)),
        np.allclose(np.array(lo0.matrix_world), np.eye(4)))
    # ---- cloth proxy (single-layer sheet over each garment) and body collider (everything else)
    for o in lods:
        if o.data.shape_keys:
            o.shape_key_clear()
    sim = build_proxy(lo0, arm, mask0, lab0)
    P_rest = np.array([v.co[:] for v in sim.data.vertices])
    log("proxy", len(sim.data.vertices), "verts", len(sim.data.polygons), "quads")
    col = lo0.copy()
    col.data = lo0.data.copy()
    col.name = "_cloth_collider"
    sc.collection.objects.link(col)
    gic = {g.index: g.name for g in col.vertex_groups}
    fore = np.array([sum(ge.weight for ge in v.groups if any(k in gic[ge.group] for k in FORE)) > 0.5
                     for v in col.data.vertices])
    drop = mask0 | fore
    bm = bmesh.new()
    bm.from_mesh(col.data)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if all(drop[v.index] for v in f.verts)], context="FACES")
    bm.to_mesh(col.data)
    bm.free()
    cm = sim.modifiers.new("Cloth", "CLOTH")
    st = cm.settings
    st.vertex_group_mass = "_pin"
    st.quality = 10
    st.mass = 0.3
    st.tension_stiffness = 15
    st.compression_stiffness = 15
    st.shear_stiffness = 5
    st.bending_stiffness = 0.8
    st.air_damping = 2.0
    cs = cm.collision_settings
    cs.use_collision = True
    cs.collision_quality = 4
    cs.distance_min = 0.012
    cs.use_self_collision = False
    col.modifiers.new("Collision", "COLLISION")
    col.collision.thickness_outer = 0.012
    col.collision.cloth_friction = 5.0
    col.collision.damping = 0.5
    me = bpy.data.meshes.new("_floor")
    me.from_pydata([(-3, -3, 0), (3, -3, 0), (3, 3, 0), (-3, 3, 0)], [], [(0, 1, 2, 3)])
    floor = bpy.data.objects.new("_floor", me)
    sc.collection.objects.link(floor)
    floor.modifiers.new("Collision", "COLLISION")
    floor.collision.thickness_outer = 0.008
    floor.collision.cloth_friction = 12.0
    # ---- armature: standing -> seated (reverse stand_up, slowed, cloth bones neutral), then hold
    bases = [pose_at(arm, up, n_up - f) for f in range(n_up + 1)]
    seat = pose_at(arm, sit, 0)
    sim_act = bpy.data.actions.new("_sim_sitdown")
    arm.animation_data.action = sim_act
    seq = [(f * SLOW, B) for f, B in enumerate(bases)]
    last_motion = n_up * SLOW
    seq += [(last_motion + 6, seat), (last_motion + 6 + HOLD, seat)]
    for f, B in seq:
        for pb in arm.pose.bones:
            if pb.name not in B:
                continue
            pb.matrix_basis = Matrix.Identity(4) if pb.name in CLOTH else B[pb.name]
            pb.keyframe_insert("rotation_quaternion", frame=f, group=pb.name)
            pb.keyframe_insert("location", frame=f, group=pb.name)
    last = seq[-1][0]
    # hanging reference (armature only) in the seated pose
    cm.show_viewport = cm.show_render = False
    sc.frame_set(last)
    deps = bpy.context.evaluated_depsgraph_get()
    ev = sim.evaluated_get(deps)
    P_hang = np.array([v.co[:] for v in ev.data.vertices])
    N_hang = np.array([v.normal[:] for v in ev.data.vertices])
    cm.show_viewport = cm.show_render = True
    cm.point_cache.frame_start = 0
    cm.point_cache.frame_end = last
    sc.frame_start, sc.frame_end = 0, last
    snaps = {int(last_motion * 0.5), last_motion, last}
    for f in range(0, last + 1):
        sc.frame_set(f)
        if DRY and f in snaps:
            snapshots([sim, col, floor], DRY, f"{AID}_sim_f{f:03d}", [(0.25, 0.55, 0.95, 1), (0.8, 0.8, 0.8, 1),
                                                                      (0.35, 0.3, 0.25, 1)])
    deps = bpy.context.evaluated_depsgraph_get()
    ev = sim.evaluated_get(deps)
    P_drape = np.array([v.co[:] for v in ev.data.vertices])
    N_drape = np.array([v.normal[:] for v in ev.data.vertices])
    log("simulated proxy over", last, "frames; z range", round(float(P_drape[:, 2].min()), 3),
        round(float(P_drape[:, 2].max()), 3), "mean move", round(float(np.linalg.norm(P_drape - P_hang, axis=1).mean()), 3))
    # ---- seated skinning (cloth bones neutral) -> rest-space morph deltas for every LOD
    sc.frame_set(last)
    bpy.context.view_layer.update()
    Bm = skin_matrices(arm)
    from scipy.spatial import cKDTree
    tree = cKDTree(P_rest)
    Rk = np.array([rot_between(a, b) for a, b in zip(N_hang, N_drape)])
    deltas = {}
    for o in lods:
        mask, _ = gmask[o.name]
        gi_o = {g.index: g.name for g in o.vertex_groups}
        co = np.array([v.co[:] for v in o.data.vertices])
        d = np.zeros_like(co)
        idx = np.where(mask)[0]
        if len(idx):
            dist, nn = tree.query(co[idx], k=4)
            w = 1.0 / np.maximum(dist, 0.004) ** 2
            w /= w.sum(1, keepdims=True)
            fade = np.clip(1.0 - (dist[:, 0] - 0.05) / 0.05, 0.0, 1.0)
            for t, i in enumerate(idx):
                M = lbs(o, gi_o, Bm, i)
                vh = (M @ np.append(co[i], 1.0))[:3]
                vd = np.zeros(3)
                for kk in range(4):
                    n = nn[t, kk]
                    vd += w[t, kk] * (P_drape[n] + Rk[n] @ (vh - P_hang[n]))
                d[i] = np.linalg.solve(M[:3, :3], (vd - vh) * fade[t])
        deltas[o.name] = d
    dn = np.linalg.norm(deltas[lo0.name], axis=1)
    cloth_v = mask0
    log("morph |delta| max", round(float(dn.max()), 3), "m, mean over garment", round(float(dn[cloth_v].mean()), 3),
        "p95", round(float(np.percentile(dn[cloth_v], 95)), 3))
    # ---- shape keys on all LODs
    for o in lods:
        o.shape_key_add(name="Basis", from_mix=False)
        sk = o.shape_key_add(name="sit_drape", from_mix=False)
        co = np.array([v.co[:] for v in o.data.vertices])
        sk.data.foreach_set("co", (co + deltas[o.name]).astype(np.float32).ravel())
        o.data.update()
    # ---- QA: proxy drape + LOD0 with the morph at weight 1 in the seated pose (cloth bones neutral)
    out_dir = DRY or qa_dir
    snapshots([sim, col, floor], out_dir, f"{AID}_sit_drape_sim" if DRY else "sit_drape_sim",
              [(0.25, 0.55, 0.95, 1), (0.8, 0.8, 0.8, 1), (0.35, 0.3, 0.25, 1)])
    for o in lods:
        o.data.shape_keys.key_blocks["sit_drape"].value = 1.0
    sc.frame_set(last)
    snapshots([lo0, floor], out_dir, f"{AID}_sit_drape_lod0" if DRY else "sit_drape_lod0",
              [(1, 1, 1, 1), (0.35, 0.3, 0.25, 1)], ctype="TEXTURE")
    for o in lods:
        o.data.shape_keys.key_blocks["sit_drape"].value = 0.0
    if DRY:
        return
    # ---- clips: neutral cloth bones while seated / while the morph is on
    neutralize(sit, lambda f: 0.0)
    neutralize(up, lambda f: float(np.clip((f - f_off) / 8.0, 0, 1)) ** 2 * (3 - 2 * float(np.clip((f - f_off) / 8.0, 0, 1))))
    # ---- morph weight curves in every civilian clip (KEY slot of the same action) + NLA strips for export
    for o in lods:
        key = o.data.shape_keys
        if key.animation_data is None:
            key.animation_data_create()
    key_slot = {}
    for name, act in sorted(acts.items()):
        if not name.startswith("lf_civilian_"):
            continue
        n = int(round(act.frame_range[1]))
        if name == "lf_civilian_cage_sit":
            keys = [(0, 1.0), (n, 1.0)]
        elif name == "lf_civilian_stand_up":
            keys = [(f, float(w_up[f])) for f in range(0, min(f_off + 2, n) + 1, 2)] + [(n, 0.0)]
        else:
            keys = [(0, 0.0), (n, 0.0)]
        for o in lods:
            key = o.data.shape_keys
            key.animation_data.action = act
            if name in key_slot:
                key.animation_data.action_slot = key_slot[name]
            kb = key.key_blocks["sit_drape"]
            for f, val in keys:
                kb.value = val
                kb.keyframe_insert("value", frame=f)
            key_slot[name] = key.animation_data.action_slot
    for o in lods:
        ad = o.data.shape_keys.animation_data
        ad.action = None
        for tr in list(ad.nla_tracks):
            ad.nla_tracks.remove(tr)
        for name, act in sorted(acts.items()):
            if name not in key_slot:
                continue
            tr = ad.nla_tracks.new()
            tr.name = name
            stp = tr.strips.new(name, 0, act)
            stp.action_slot = key_slot[name]
            tr.mute = True       # Blender playback stays clean; the glTF exporter still reads single-strip tracks
        o.data.shape_keys.key_blocks["sit_drape"].value = 0.0
    # ---- clean up the simulation helpers
    for o in (sim, col, floor):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.actions.remove(sim_act)
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    # ---- re-export + meta
    out_glb = paths.runtime("humans", f"{AID}.glb")
    core.export_glb(out_glb, [arm] + lods,
                    extra=dict(export_force_sampling=True, export_optimize_animation_size=False,
                               export_image_format="AUTO", export_def_bones=True, export_animation_mode="ACTIONS",
                               export_bake_animation=False, export_morph=True, export_morph_normal=False,
                               export_morph_animation=True, export_merge_animation="ACTION"))
    log("GLB", out_glb, os.path.getsize(out_glb) // 1024, "KB")
    mp = paths.runtime("humans", f"{AID}.meta.json")
    meta = json.load(open(mp))
    meta["morphs"] = {"sit_drape": {
        "kind": "corrective cloth drape baked from a Blender cloth simulation (pinned at the waist / shoulders, "
                "body + cage-floor collision), stored relative to the posed rest shape",
        "clips": {"lf_civilian_cage_sit": "1.0",
                  "lf_civilian_stand_up": f"1 -> 0 over 0-{f_off / 30.0:.2f} s as the thighs come down",
                  "other civilian clips": "0"},
        "cloth_bones": "neutral while the morph is on (cage_sit; stand_up until the morph is off, then blended back)",
        "mean_delta_m": round(float(dn[cloth_v].mean()), 3)}}
    core.write_json(mp, meta)
    blend = paths.source("humans", f"{AID}.blend")
    core.save_blend(blend)
    log("saved", blend)


if __name__ == "__main__":
    main()
