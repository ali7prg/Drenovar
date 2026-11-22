"""Garments, armour, weapons and shields for DRENOVAR soldiers.

Body-following garments are offset copies of body regions, so they inherit the
CC0 skin weights and deform exactly with the body. Rigid parts (helmets,
weapons, shields, buckles) are bound 100% to one bone. Measurements are in
metres in the rest pose produced by mh_base.build_body().
"""
import math

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

TORSO = {"root", "spine05", "spine04", "spine03", "spine02", "spine01", "neck01"}
NECK = {"neck01", "neck02"}
HEAD = {"head", "neck02"}


def side_bones(prefixes):
    return {f"{p}.{s}" for p in prefixes for s in ("L", "R")}


ARM_UPPER = side_bones(["clavicle", "shoulder01", "upperarm01", "upperarm02"])
ARM_LOWER = side_bones(["lowerarm01", "lowerarm02"])
HANDS = side_bones(["wrist"] + [f"finger{f}-{k}" for f in range(1, 6) for k in range(1, 4)])
HIPS = side_bones(["pelvis"])
THIGH = side_bones(["upperleg01", "upperleg02"])
SHIN = side_bones(["lowerleg01", "lowerleg02"])
FEET = side_bones(["foot", "toe1-1"])


def vertex_weights(obj):
    names = {g.index: g.name for g in obj.vertex_groups}
    return [{names[g.group]: g.weight for g in v.groups} for v in obj.data.vertices]


def bone_share(weights, bones):
    return np.array([sum(w for b, w in vw.items() if b in bones) / max(1e-6, sum(vw.values())) for vw in weights])


def select_faces(body, rule):
    """rule(vertex_index) -> bool; faces whose vertices all pass."""
    mesh = body.data
    ok = np.array([rule(i) for i in range(len(mesh.vertices))])
    return [p.index for p in mesh.polygons if ok[list(p.vertices)].all()], ok


def region_rule(body, bones, minimum=0.5, zmin=-1e9, zmax=1e9, extra=None):
    weights = vertex_weights(body)
    share = bone_share(weights, bones)
    co = np.array([v.co[:] for v in body.data.vertices])

    def rule(i):
        if share[i] < minimum or not (zmin <= co[i][2] <= zmax):
            return False
        return extra(co[i]) if extra else True
    return rule


def bind(obj, rig, groups=None):
    """Adds the armature modifier and parents to the rig; groups: {bone: [(v, w)]}."""
    if groups:
        for bone, pairs in groups.items():
            group = obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
            for v, w in pairs:
                group.add([v], w, "REPLACE")
    obj.modifiers.new("Armature", "ARMATURE").object = rig
    obj.parent = rig
    return obj


def rigid(obj, rig, bone):
    group = obj.vertex_groups.new(name=bone)
    group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    return bind(obj, rig)


def new_object(name, bm, material=None):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    if material is not None:
        mesh.materials.append(material)
    for poly in mesh.polygons:
        poly.use_smooth = True
    return obj


def shell(body, rig, name, rule, offset, material, thickness=0.0, smooth_normals=True):
    """Copies body faces passing rule, pushed out along vertex normals."""
    faces, _ = select_faces(body, rule)
    bm = bmesh.new()
    bm.from_mesh(body.data)
    keep = set(faces)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in keep], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * offset
    obj = new_object(name, bm, material)
    # Copy vertex groups by nearest original vertex (topology is a subset).
    src = body.data
    lookup = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get(), deform=False)
    weights = vertex_weights(body)
    kd_points = np.array([v.co[:] for v in src.vertices])
    from mathutils.kdtree import KDTree
    tree = KDTree(len(kd_points))
    for i, p in enumerate(kd_points):
        tree.insert(p, i)
    tree.balance()
    for v in obj.data.vertices:
        _, index, _ = tree.find(v.co - v.normal * offset)
        for bone, w in weights[index].items():
            group = obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
            group.add([v.index], w, "REPLACE")
    smooth_boundary(obj)
    unwrap(obj)
    if thickness > 0:
        mod = obj.modifiers.new("Thickness", "SOLIDIFY")
        mod.thickness = thickness
        mod.offset = 1.0
        mod.use_rim = True
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return bind(obj, rig)


def smooth_boundary(obj, passes=4, factor=0.5):
    """Relaxes the open edge loops of a garment shell so hems and sleeves end in smooth
    lines instead of following the body's face staircase."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    boundary = [e for e in bm.edges if e.is_boundary]
    neighbours = {}
    for e in boundary:
        a, b = e.verts
        neighbours.setdefault(a, []).append(b)
        neighbours.setdefault(b, []).append(a)
    for _ in range(passes):
        moved = {}
        for v, ns in neighbours.items():
            if len(ns) == 2:
                target = (ns[0].co + ns[1].co) * 0.5
                moved[v] = v.co.lerp(target, factor)
        for v, co in moved.items():
            v.co = co
    bm.to_mesh(obj.data)
    bm.free()


def unwrap(obj, angle=66.0, margin=0.004):
    """Repacks a garment's own UVs so its baked texture uses the whole image."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, area_weight=1.0, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode="OBJECT")


def body_tree(body):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    return BVHTree.FromObject(body, depsgraph, deform=False)


def nearest_weights(body, points):
    from mathutils.kdtree import KDTree
    co = [v.co for v in body.data.vertices]
    tree = KDTree(len(co))
    for i, p in enumerate(co):
        tree.insert(p, i)
    tree.balance()
    weights = vertex_weights(body)
    out = []
    for p in points:
        found = tree.find_n(p, 4)
        acc, total = {}, 0.0
        for _, index, dist in found:
            k = 1.0 / max(dist, 1e-4)
            total += k
            for bone, w in weights[index].items():
                acc[bone] = acc.get(bone, 0.0) + w * k
        out.append({b: w / total for b, w in acc.items()})
    return out


def bind_like_body(obj, body, rig, falloff_bones=None):
    """Skins an arbitrary mesh with weights interpolated from the nearest body vertices."""
    points = [v.co for v in obj.data.vertices]
    for vi, weights in enumerate(nearest_weights(body, points)):
        for bone, w in weights.items():
            if falloff_bones and bone not in falloff_bones:
                continue
            if w < 0.02:
                continue
            group = obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
            group.add([vi], w, "REPLACE")
    return bind(obj, rig)


_TORSO_TREES = {}


def torso_tree(body):
    """BVH of the body without arms and hands (they hang beside the hips in the rest pose)."""
    key = body.name
    if key not in _TORSO_TREES:
        weights = vertex_weights(body)
        arm = bone_share(weights, ARM_UPPER | ARM_LOWER | HANDS)
        co = [v.co.copy() for v in body.data.vertices]
        polys = [list(p.vertices) for p in body.data.polygons if max(arm[i] for i in p.vertices) < 0.35]
        _TORSO_TREES[key] = BVHTree.FromPolygons(co, polys)
    return _TORSO_TREES[key]


def ring_profile(body, z, samples=48, push=0.0):
    """Cross-section of the torso/legs around the vertical axis at height z (arms excluded)."""
    tree = torso_tree(body)
    center = Vector((0, 0.0, z))
    points = []
    for k in range(samples):
        a = 2 * math.pi * k / samples
        d = Vector((math.sin(a), -math.cos(a), 0))
        origin = center + d * 0.6
        hit = tree.ray_cast(origin, -d, 0.7)
        r = (hit[0] - center).length if hit[0] is not None else 0.18
        points.append(center + d * (r + push))
    return points


def skirt(body, rig, name, top_z, bottom_z, material, flare=0.06, push=0.012, samples=48, rows=10,
          front_slit=0.0, hem_noise=0.0, seed=1):
    """Tube from the waist to the hem. Weights blend pelvis -> thighs downward."""
    top = ring_profile(body, top_z, samples, push)
    bm = bmesh.new()
    rings = []
    rng = np.random.default_rng(seed)
    hem_jitter = rng.uniform(-hem_noise, hem_noise, samples) if hem_noise else np.zeros(samples)
    for r in range(rows + 1):
        t = r / rows
        z = top_z + (bottom_z - top_z) * t
        prof = ring_profile(body, max(z, bottom_z + 0.02), samples, push) if z > 0.25 else None
        ring = []
        for k in range(samples):
            base = top[k]
            radial = Vector((base.x, base.y, 0))
            if prof is not None:
                width = max(Vector((prof[k].x, prof[k].y, 0)).length, radial.length * (1 - 0.2 * t))
            else:
                width = radial.length
            spread = width + flare * t * t
            d = radial.normalized()
            zz = z + (hem_jitter[k] if r == rows else 0)
            ring.append(bm.verts.new((d.x * spread, d.y * spread, zz)))
        rings.append(ring)
    uv_rows = []
    for r in range(rows):
        for k in range(samples):
            a = 2 * math.pi * k / samples
            if front_slit and abs(math.sin(a)) < front_slit and r >= rows // 2:
                continue
            k2 = (k + 1) % samples
            bm.faces.new((rings[r][k], rings[r][k2], rings[r + 1][k2], rings[r + 1][k]))
    bm.normal_update()
    # Outward normals.
    for f in bm.faces:
        c = f.calc_center_median()
        if f.normal.dot(Vector((c.x, c.y, 0))) < 0:
            f.normal_flip()
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for loop in f.loops:
            p = loop.vert.co
            loop[uv].uv = ((math.atan2(p.x, -p.y) / (2 * math.pi)) + 0.5, (p.z - bottom_z) / max(0.01, top_z - bottom_z))
    obj = new_object(name, bm, material)
    for v in obj.data.vertices:
        t = max(0.0, min(1.0, (top_z - v.co.z) / max(0.01, top_z - bottom_z)))
        # Smooth left/right blend: centre-front and centre-back follow both thighs equally.
        left = max(0.0, min(1.0, 0.5 + v.co.x / 0.16))
        lateral = min(1.0, abs(v.co.x) / 0.14)
        thigh = t * t * (0.45 + 0.25 * lateral)
        weights = {"spine05": 1 - thigh}
        for side, share in (("L", left), ("R", 1 - left)):
            if share > 0.01:
                weights[f"upperleg02.{side}"] = thigh * share
        for bone, w in weights.items():
            group = obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
            group.add([v.index], w, "REPLACE")
    # Groups exist before the thickness is applied, so the inner wall inherits them.
    mod = obj.modifiers.new("Thickness", "SOLIDIFY")
    mod.thickness = 0.006
    mod.offset = -1.0
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return bind(obj, rig)


def belt(body, rig, name, z, width, material, push=0.03, samples=40, thickness=0.006, smooth_passes=4):
    """Smooth belt ring around the body at height z (radii are smoothed, not projected)."""
    ring = ring_profile(body, z, samples, 0.0)
    radii = np.array([Vector((p.x, p.y)).length for p in ring])
    for _ in range(smooth_passes):
        radii = (np.roll(radii, 1) + radii * 2 + np.roll(radii, -1)) / 4
    bm = bmesh.new()
    top, bottom = [], []
    for k, p in enumerate(ring):
        d = Vector((p.x, p.y, 0)).normalized() * (radii[k] + push)
        top.append(bm.verts.new((d.x, d.y, z + width / 2)))
        bottom.append(bm.verts.new((d.x * 1.01, d.y * 1.01, z - width / 2)))
    for k in range(samples):
        k2 = (k + 1) % samples
        bm.faces.new((bottom[k], bottom[k2], top[k2], top[k]))
    bm.normal_update()
    for f in bm.faces:
        c = f.calc_center_median()
        if f.normal.dot(Vector((c.x, c.y, 0))) < 0:
            f.normal_flip()
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for loop in f.loops:
            p = loop.vert.co
            loop[uv].uv = ((math.atan2(p.x, -p.y) / (2 * math.pi) + 0.5) * 8, 0.0 if p.z < z else 1.0)
    obj = new_object(name, bm, material)
    mod = obj.modifiers.new("Thickness", "SOLIDIFY")
    mod.thickness = thickness
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    buckle = bmesh.new()
    bmesh.ops.create_cube(buckle, size=1.0)
    front = Vector((0, -(radii[0] + push) - 0.006, z))
    transform_bm(buckle, Matrix.Translation(front) @ Matrix.Diagonal((0.05, 0.008, width * 1.2, 1)))
    box_uv(buckle, 8)
    return bind_like_body(join([obj, new_object(name + "_Buckle", buckle, material)], name), body, rig)


def surface_strap(body, rig, name, points, width, material, lift=0.02, thickness=0.004):
    """A strap/belt following the body surface through the given control points."""
    tree = body_tree(body)
    path = []
    for a, b in zip(points[:-1], points[1:]):
        for s in range(12):
            path.append(a.lerp(b, s / 12))
    path.append(points[-1])
    projected = []
    for p in path:
        hit = tree.find_nearest(p)
        if hit[0] is None:
            projected.append((p, Vector((0, -1, 0))))
            continue
        projected.append((hit[0] + hit[1] * lift, hit[1]))
    bm = bmesh.new()
    left, right = [], []
    for i, (p, n) in enumerate(projected):
        nxt = projected[min(i + 1, len(projected) - 1)][0]
        prv = projected[max(i - 1, 0)][0]
        tangent = (nxt - prv).normalized()
        side = tangent.cross(n).normalized() * width * 0.5
        left.append(bm.verts.new(p + side))
        right.append(bm.verts.new(p - side))
    for i in range(len(left) - 1):
        bm.faces.new((left[i], right[i], right[i + 1], left[i + 1]))
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for loop in f.loops:
            idx = left.index(loop.vert) if loop.vert in left else right.index(loop.vert)
            loop[uv].uv = (0.0 if loop.vert in left else 1.0, idx * 0.08)
    obj = new_object(name, bm, material)
    mod = obj.modifiers.new("Thickness", "SOLIDIFY")
    mod.thickness = thickness
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return bind_like_body(obj, body, rig)


# ------------------------------------------------------------ primitives

def box_uv(bm, scale=1.0):
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        axis = max(range(3), key=lambda i: abs(n[i]))
        for loop in f.loops:
            p = loop.vert.co
            if axis == 0:
                loop[uv].uv = (p.y * scale, p.z * scale)
            elif axis == 1:
                loop[uv].uv = (p.x * scale, p.z * scale)
            else:
                loop[uv].uv = (p.x * scale, p.y * scale)


def lathe(profile, segments=32, cap_top=False, cap_bottom=False):
    """Revolves (radius, z) points around Z."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        ring = [bm.verts.new((r * math.cos(2 * math.pi * k / segments), r * math.sin(2 * math.pi * k / segments), z))
                for k in range(segments)]
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(segments):
            k2 = (k + 1) % segments
            bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
    if cap_bottom:
        bm.faces.new(list(reversed(rings[0])))
    if cap_top:
        bm.faces.new(rings[-1])
    bm.normal_update()
    uv = bm.loops.layers.uv.new("UVMap")
    total = sum(((profile[i + 1][0] - profile[i][0]) ** 2 + (profile[i + 1][1] - profile[i][1]) ** 2) ** 0.5
                for i in range(len(profile) - 1)) or 1.0
    for f in bm.faces:
        for loop in f.loops:
            p = loop.vert.co
            loop[uv].uv = ((math.atan2(p.y, p.x) / (2 * math.pi)) % 1.0, p.z / total)
    return bm


def transform_bm(bm, matrix):
    bmesh.ops.transform(bm, matrix=matrix, verts=bm.verts)
    bm.normal_update()


def join(objects, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    objects[0].name = name
    return objects[0]


def bone_frame(rig, bone):
    """World matrix of a bone in rest pose (Y along the bone)."""
    return rig.matrix_world @ rig.data.bones[bone].matrix_local


def palm_normal(points, side):
    """Rest-pose palm normal from bone heads: the MakeHuman A-pose hands face the thighs.
    points: callable(name) -> Vector (armature space)."""
    across = (points(f"finger5-1.{side}") - points(f"finger2-1.{side}")).normalized()
    along = (points(f"finger3-1.{side}") - points(f"wrist.{side}")).normalized()
    palm = across.cross(along).normalized()
    inward = -1.0 if side == "L" else 1.0
    if palm.x * inward < 0:
        palm = -palm
    return palm, across, along


def hand_grip(rig, side):
    """Rest-pose grip frame inside the closed fist.

    origin: centre of the fist; z axis: grip axis across the palm (index -> little finger);
    y axis: from wrist towards the knuckles. Returned as a world Matrix.
    """
    bones = rig.data.bones
    head = lambda name: bones[name].head_local.copy()
    palm, across, along = palm_normal(head, side)
    wrist = head(f"wrist.{side}")
    middle = head(f"finger3-1.{side}")
    origin = wrist + (middle - wrist) * 0.95 + palm * 0.03
    y = along
    z = across
    x = y.cross(z).normalized()
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = origin
    return rig.matrix_world @ m


def place_on_grip(obj, rig, side, local=Matrix.Identity(4), bone=None):
    """Moves a weapon authored along +Z (grip centre at the origin) into the fist."""
    grip = hand_grip(rig, side)
    obj.matrix_world = grip @ local
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return rigid(obj, rig, bone or f"wrist.{side}")


# ------------------------------------------------------------ weapons

def spear(material_wood, material_steel, length=2.3, grip_from_butt=0.95, head=0.32):
    shaft = lathe([(0.0145, 0.0), (0.0155, 0.5), (0.016, 1.2), (0.015, length - head)], 10, True, True)
    transform_bm(shaft, Matrix.Translation((0, 0, -grip_from_butt)))
    shaft_obj = new_object("Spear_Shaft", shaft, material_wood)
    tip = bmesh.new()
    top = length - grip_from_butt
    socket = lathe([(0.017, 0), (0.017, 0.07), (0.012, 0.11)], 10)
    transform_bm(socket, Matrix.Translation((0, 0, top - head)))
    blade_pts = [(0.0, 0.0), (0.028, 0.06), (0.032, 0.12), (0.018, 0.2), (0.0, head - 0.1)]
    socket_obj = new_object("Spear_Socket", socket, material_steel)
    blade = bmesh.new()
    left = [blade.verts.new((x, 0, z + top - head + 0.1)) for x, z in blade_pts]
    right = [blade.verts.new((-x, 0, z + top - head + 0.1)) for x, z in blade_pts]
    ridge_f = [blade.verts.new((0, 0.006, z + top - head + 0.1)) for _, z in blade_pts]
    ridge_b = [blade.verts.new((0, -0.006, z + top - head + 0.1)) for _, z in blade_pts]
    for i in range(len(blade_pts) - 1):
        for edge, ridge in ((left, ridge_f), (right, ridge_b), (left, ridge_b), (right, ridge_f)):
            quad = [edge[i], edge[i + 1], ridge[i + 1], ridge[i]]
            if len({v.index for v in quad}) == 4:
                try:
                    blade.faces.new(quad)
                except ValueError:
                    pass
    bmesh.ops.remove_doubles(blade, verts=blade.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(blade, faces=blade.faces)
    box_uv(blade, 4)
    blade_obj = new_object("Spear_Blade", blade, material_steel)
    ferrule = lathe([(0.016, 0), (0.018, 0.02), (0.016, 0.06), (0.0, 0.0)], 10)
    transform_bm(ferrule, Matrix.Translation((0, 0, -grip_from_butt)))
    ferrule_obj = new_object("Spear_Ferrule", ferrule, material_steel)
    return join([shaft_obj, socket_obj, blade_obj, ferrule_obj], "Spear")


def sword(material_steel, material_leather, blade_length=0.82, grip=0.11):
    """Arming sword: grip centre at origin, blade along +Z."""
    parts = []
    g = lathe([(0.014, -grip / 2), (0.016, 0), (0.014, grip / 2)], 10, True, True)
    parts.append(new_object("Sword_Grip", g, material_leather))
    pommel = bmesh.new()
    bmesh.ops.create_uvsphere(pommel, u_segments=12, v_segments=8, radius=0.024)
    transform_bm(pommel, Matrix.Translation((0, 0, -grip / 2 - 0.018)) @ Matrix.Diagonal((1, 0.55, 1, 1)))
    box_uv(pommel, 6)
    parts.append(new_object("Sword_Pommel", pommel, material_steel))
    guard = bmesh.new()
    bmesh.ops.create_cube(guard, size=1.0)
    transform_bm(guard, Matrix.Translation((0, 0, grip / 2 + 0.008)) @ Matrix.Diagonal((0.2, 0.022, 0.016, 1)))
    box_uv(guard, 6)
    parts.append(new_object("Sword_Guard", guard, material_steel))
    blade = bmesh.new()
    base = grip / 2 + 0.016
    sections = [(0.0, 0.026), (0.35, 0.023), (0.7, 0.016), (0.92, 0.007), (1.0, 0.0)]
    rings = []
    for t, w in sections:
        z = base + blade_length * t
        th = 0.0045 * (1 - t * 0.6)
        rings.append([blade.verts.new(p) for p in ((w, 0, z), (0, th, z), (-w, 0, z), (0, -th, z))])
    for i in range(len(rings) - 1):
        for k in range(4):
            quad = [rings[i][k], rings[i][(k + 1) % 4], rings[i + 1][(k + 1) % 4], rings[i + 1][k]]
            blade.faces.new(quad)
    bmesh.ops.remove_doubles(blade, verts=blade.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(blade, faces=blade.faces)
    box_uv(blade, 3)
    parts.append(new_object("Sword_Blade", blade, material_steel))
    return join(parts, "Sword")


def scabbard(material_leather, material_steel, length=0.86):
    s = lathe([(0.02, 0), (0.026, 0.06), (0.024, length)], 8, True, True)
    transform_bm(s, Matrix.Diagonal((1, 0.42, 1, 1)))
    return new_object("Scabbard", s, material_leather)


def kite_face(height=0.98, width=0.52, curve=0.09):
    """Painted face of a curved kite shield (faces -Y), centred at the origin."""
    bm = bmesh.new()
    cols, rows = 10, 16
    grid = []
    for r in range(rows + 1):
        v = r / rows
        row = [bm.verts.new(grid_point(v, c / cols * 2 - 1, width, height, curve)) for c in range(cols + 1)]
        grid.append(row)
    for r in range(rows):
        for c in range(cols):
            bm.faces.new((grid[r][c], grid[r][c + 1], grid[r + 1][c + 1], grid[r + 1][c]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.normal_update()
    for f in bm.faces:
        if f.normal.y > 0:
            f.normal_flip()
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for loop in f.loops:
            p = loop.vert.co
            loop[uv].uv = (p.x / width + 0.5, p.z / height + 0.5)
    face = new_object("Shield", bm)
    face["outline"] = [list(grid_point(r / rows, -1, width, height, curve)) for r in range(rows + 1)] + \
        [list(grid_point(r / rows, 1, width, height, curve)) for r in range(rows, -1, -1)]
    face["boss_z"] = height * 0.08
    return face


def round_face(radius=0.3, dome=0.04):
    profile = [(0.0, dome), (radius * 0.25, dome * 0.92), (radius * 0.6, dome * 0.6), (radius, 0.0)]
    bm = lathe(profile, 28)
    transform_bm(bm, Matrix.Rotation(math.radians(90), 4, "X"))
    for f in bm.faces:
        if f.normal.y > 0:
            f.normal_flip()
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        for loop in f.loops:
            p = loop.vert.co
            loop[uv].uv = (p.x / (2 * radius) + 0.5, p.z / (2 * radius) + 0.5)
    face = new_object("Shield", bm)
    face["outline"] = [list(Vector((radius * math.cos(a), 0.002, radius * math.sin(a)))) for a in np.linspace(0, 2 * math.pi, 40, endpoint=False)]
    face["boss_z"] = 0.0
    face["dome"] = dome
    return face


def finish_shield(face, material_steel, material_wood, thickness=0.018, closed=True):
    """Adds the wooden body behind the painted face, the steel rim and the boss.
    face must already carry its painted material in slot 0."""
    face.data.materials.append(material_wood)
    solid = face.modifiers.new("Thickness", "SOLIDIFY")
    solid.thickness = thickness
    solid.offset = 1.0
    solid.use_rim = True
    solid.material_offset = 1
    solid.material_offset_rim = 1
    bpy.context.view_layer.objects.active = face
    bpy.ops.object.modifier_apply(modifier=solid.name)
    outline = [Vector(p) for p in face["outline"]]
    rim = new_object("Shield_Rim", tube_along(outline, 0.009, 6, closed=closed), material_steel)
    boss = bmesh.new()
    bmesh.ops.create_uvsphere(boss, u_segments=16, v_segments=8, radius=0.055)
    transform_bm(boss, Matrix.Translation((0, -face.get("dome", 0.0) - 0.012, face["boss_z"])) @ Matrix.Diagonal((1, 0.6, 1, 1)))
    box_uv(boss, 6)
    boss_obj = new_object("Shield_Boss", boss, material_steel)
    return join([face, rim, boss_obj], "Shield")


def grid_point(v, u, width, height, curve):
    z = height * (0.5 - v)
    half = width * 0.5 * (math.sqrt(max(0.0, 1 - ((v - 0.18) / 0.18) ** 2)) if v < 0.18 else (1 - ((v - 0.18) / 0.82) ** 1.5))
    x = u * max(half, 0.004)
    y = -curve * (1 - u * u) + curve
    return Vector((x, -y - 0.001, z))


def tube_along(points, radius, sides=6, closed=False):
    bm = bmesh.new()
    rings = []
    count = len(points)
    for i, p in enumerate(points):
        a = points[(i - 1) % count] if closed or i > 0 else p
        b = points[(i + 1) % count] if closed or i < count - 1 else p
        t = (b - a).normalized() if (b - a).length > 1e-6 else Vector((0, 0, 1))
        n = t.orthogonal().normalized()
        bnorm = t.cross(n)
        rings.append([bm.verts.new(p + (n * math.cos(2 * math.pi * k / sides) + bnorm * math.sin(2 * math.pi * k / sides)) * radius)
                      for k in range(sides)])
    last = count if closed else count - 1
    for i in range(last):
        r1, r2 = rings[i], rings[(i + 1) % count]
        for k in range(sides):
            bm.faces.new((r1[k], r1[(k + 1) % sides], r2[(k + 1) % sides], r2[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    box_uv(bm, 8)
    return bm


def longbow(material_wood, material_string, length=1.82):
    """Stave curved towards -X (away from the archer), grip at origin, along +Z."""
    pts, radii = [], []
    for i in range(25):
        t = i / 24 * 2 - 1
        z = t * length / 2
        x = 0.11 * (1 - t * t)
        pts.append(Vector((x - 0.11, 0, z)))
        radii.append(0.016 * (1 - 0.55 * abs(t)) + 0.005)
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(pts):
        rings.append([bm.verts.new(p + Vector((math.cos(a) * radii[i] * 0.8, math.sin(a) * radii[i], 0)))
                      for a in np.linspace(0, 2 * math.pi, 8, endpoint=False)])
    for i in range(len(rings) - 1):
        for k in range(8):
            bm.faces.new((rings[i][k], rings[i][(k + 1) % 8], rings[i + 1][(k + 1) % 8], rings[i + 1][k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    box_uv(bm, 6)
    stave = new_object("Bow_Stave", bm, material_wood)
    string = new_object("Bow_String", tube_along([pts[0] + Vector((0.004, 0, 0.01)), pts[-1] + Vector((0.004, 0, -0.01))], 0.0018, 4),
                        material_string)
    return join([stave, string], "Longbow")


def crossbow(material_wood, material_steel, material_string):
    """Stock along +Y (pointing forward) with the trigger grip at the origin."""
    parts = []
    stock = bmesh.new()
    bmesh.ops.create_cube(stock, size=1.0)
    transform_bm(stock, Matrix.Translation((0, 0.28, 0.03)) @ Matrix.Diagonal((0.045, 0.82, 0.06, 1)))
    box_uv(stock, 4)
    parts.append(new_object("Crossbow_Stock", stock, material_wood))
    prod_pts = [Vector((x, 0.66 - 0.06 * (x / 0.33) ** 2, 0.05)) for x in np.linspace(-0.33, 0.33, 15)]
    parts.append(new_object("Crossbow_Prod", tube_along(prod_pts, 0.012, 6), material_steel))
    parts.append(new_object("Crossbow_String", tube_along([prod_pts[0], Vector((0, 0.33, 0.065)), prod_pts[-1]], 0.002, 4), material_string))
    stirrup = [Vector((x, 0.7 + 0.08 * math.sin(math.pi * (x + 0.06) / 0.12), 0.05)) for x in np.linspace(-0.06, 0.06, 9)]
    parts.append(new_object("Crossbow_Stirrup", tube_along(stirrup, 0.006, 5), material_steel))
    return join(parts, "Crossbow")


def javelin(material_wood, material_steel, length=1.45):
    shaft = lathe([(0.011, -0.55), (0.012, 0.0), (0.0105, length - 0.55 - 0.16)], 8, True, True)
    shaft_obj = new_object("Javelin_Shaft", shaft, material_wood)
    head = lathe([(0.012, 0), (0.02, 0.05), (0.0, 0.16)], 6, False, True)
    transform_bm(head, Matrix.Translation((0, 0, length - 0.55 - 0.16)))
    return join([shaft_obj, new_object("Javelin_Head", head, material_steel)], "Javelin")


def quiver(material_leather, material_wood, material_fletch, count=7, length=0.62):
    body = lathe([(0.045, 0), (0.05, 0.3), (0.055, length)], 10, False, True)
    transform_bm(body, Matrix.Diagonal((1, 0.8, 1, 1)))
    parts = [new_object("Quiver", body, material_leather)]
    rng = np.random.default_rng(4)
    for i in range(count):
        a = 2 * math.pi * i / count
        x, y = 0.025 * math.cos(a), 0.02 * math.sin(a)
        tilt = rng.uniform(-0.05, 0.05)
        shaft = new_object("Arrow", tube_along([Vector((x, y, 0.15)), Vector((x + tilt, y, length + 0.12))], 0.004, 4), material_wood)
        fl = bmesh.new()
        bmesh.ops.create_cube(fl, size=1.0)
        transform_bm(fl, Matrix.Translation((x + tilt, y, length + 0.09)) @ Matrix.Rotation(a, 4, "Z") @ Matrix.Diagonal((0.022, 0.002, 0.07, 1)))
        box_uv(fl, 8)
        parts += [shaft, new_object("Fletch", fl, material_fletch)]
    return join(parts, "Quiver")


# ------------------------------------------------------------ helmets

def head_frame(rig):
    bones = rig.data.bones
    head = bones["head"]
    return head.head_local.copy(), head.tail_local.copy()


def kettle_hat(rig, material_steel, scale=1.0):
    base, top = head_frame(rig)
    crown_z = top.z + 0.035
    brim_z = base.z + (top.z - base.z) * 0.62
    cx, cy = base.x, (base.y + top.y) / 2 - 0.006
    r = 0.112 * scale
    profile = [(0.0, crown_z + 0.012), (r * 0.35, crown_z + 0.008), (r * 0.7, crown_z - 0.03), (r * 0.93, crown_z - 0.075),
               (r, brim_z + 0.01), (r * 1.02, brim_z), (r * 1.55, brim_z - 0.03), (r * 1.62, brim_z - 0.045),
               (r * 1.58, brim_z - 0.05), (r * 1.02, brim_z - 0.012), (r * 0.98, brim_z + 0.002)]
    bm = lathe(profile, 36)
    transform_bm(bm, Matrix.Translation((cx, cy, 0)) @ Matrix.Diagonal((1.0, 1.12, 1, 1)))
    obj = new_object("Helmet", bm, material_steel)
    return rigid(obj, rig, "head")


def nasal_helm(rig, material_steel, cheeks=False, scale=1.0):
    base, top = head_frame(rig)
    crown_z = top.z + 0.05
    rim_z = base.z + (top.z - base.z) * 0.55
    cx, cy = base.x, (base.y + top.y) / 2 - 0.004
    r = 0.108 * scale
    profile = [(0.0, crown_z + 0.02), (r * 0.3, crown_z - 0.005), (r * 0.65, crown_z - 0.04), (r * 0.9, crown_z - 0.085),
               (r, rim_z + 0.015), (r * 1.02, rim_z), (r * 0.99, rim_z - 0.004)]
    bm = lathe(profile, 32)
    transform_bm(bm, Matrix.Translation((cx, cy, 0)) @ Matrix.Diagonal((0.96, 1.1, 1, 1)))
    parts = [new_object("Helmet", bm, material_steel)]
    nasal = bmesh.new()
    bmesh.ops.create_cube(nasal, size=1.0)
    face_y = cy - r * 1.06
    transform_bm(nasal, Matrix.Translation((cx, face_y - 0.003, rim_z - 0.028)) @ Matrix.Rotation(math.radians(-8), 4, "X") @ Matrix.Diagonal((0.017, 0.005, 0.06, 1)))
    box_uv(nasal, 8)
    parts.append(new_object("Nasal", nasal, material_steel))
    if cheeks:
        for side in (-1, 1):
            plate = bmesh.new()
            bmesh.ops.create_cube(plate, size=1.0)
            transform_bm(plate, Matrix.Translation((cx + side * r * 0.9, cy - r * 0.42, rim_z - 0.045)) @
                         Matrix.Rotation(-side * 0.35, 4, "Z") @ Matrix.Rotation(side * 0.12, 4, "Y") @ Matrix.Diagonal((0.004, 0.07, 0.075, 1)))
            box_uv(plate, 8)
            parts.append(new_object("Cheek", plate, material_steel))
    obj = join(parts, "Helmet")
    return rigid(obj, rig, "head")


def rivets(rig, material, ring_z, radius, count, center, bone="head", size=0.006, ellipse=(1, 1.1)):
    parts = []
    for k in range(count):
        a = 2 * math.pi * k / count
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=6, v_segments=4, radius=size)
        transform_bm(bm, Matrix.Translation((center.x + math.cos(a) * radius * ellipse[0], center.y + math.sin(a) * radius * ellipse[1], ring_z)))
        box_uv(bm, 10)
        parts.append(new_object("Rivet", bm, material))
    obj = join(parts, "Rivets")
    return rigid(obj, rig, bone)


def pauldron(rig, side, material_steel, size=0.13):
    bones = rig.data.bones
    shoulder = bones[f"shoulder01.{side}"].tail_local
    sign = 1 if side == "L" else -1
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=size)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -size * 0.15], context="VERTS")
    transform_bm(bm, Matrix.Translation(shoulder + Vector((sign * 0.03, 0.0, 0.0))) @ Matrix.Rotation(sign * -0.5, 4, "Y") @ Matrix.Diagonal((0.9, 1.05, 0.7, 1)))
    box_uv(bm, 6)
    obj = new_object(f"Pauldron.{side}", bm, material_steel)
    mod = obj.modifiers.new("Thickness", "SOLIDIFY")
    mod.thickness = 0.004
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    groups = {f"shoulder01.{side}": [(v.index, 0.55) for v in obj.data.vertices],
              f"upperarm01.{side}": [(v.index, 0.45) for v in obj.data.vertices]}
    return bind(obj, rig, groups)


def cap(rig, bone, side, material, size, offset=Vector((0, -0.03, 0))):
    """Knee/elbow cop centred on a joint."""
    head = rig.data.bones[f"{bone}.{side}"].head_local
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=size)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > size * 0.2], context="VERTS")
    transform_bm(bm, Matrix.Translation(head + offset))
    box_uv(bm, 8)
    obj = new_object(f"Cop.{side}", bm, material)
    mod = obj.modifiers.new("Thickness", "SOLIDIFY")
    mod.thickness = 0.004
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return rigid(obj, rig, f"{bone}.{side}")
