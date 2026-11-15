"""Reusable outfit layers. Each function adds finished, textured, skinned parts to a Kit."""
import math

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

import gear
import patterns
from patterns import srgb


def trousers(kit, color=srgb(0.33, 0.30, 0.27), top=1.02, bottom=0.25, seed=21):
    obj = kit.add(gear.shell(kit.body, kit.rig, "Trousers", kit.rule(gear.THIGH | gear.SHIN | gear.HIPS, 0.5, bottom, top), 0.006, None))
    kit.baked(obj, "wool_trousers", patterns.cloth(color, seed=seed, grime_start=0.75, grime=0.75), 512)
    kit.cover(gear.THIGH | gear.SHIN | gear.HIPS, 0.55, bottom + 0.03, top - 0.03)
    return obj


def boots(kit, color=srgb(0.30, 0.19, 0.11), top=0.44, straps=0.06, seed=22):
    obj = kit.add(gear.shell(kit.body, kit.rig, "Boots", kit.rule(gear.SHIN | gear.FEET, 0.45, -1, top), 0.013, None, thickness=0.003))
    kit.baked(obj, "leather_boots", patterns.leather(color, seed=seed, straps_every=straps), 512, 0.6)
    kit.cover(gear.SHIN | gear.FEET, 0.5, -1, top - 0.03)
    return obj


def aketon(kit, color, name="cloth_aketon", spacing=0.022, diamond=False, top=1.505, bottom=0.86, sleeves=True, offset=0.014, seed=23):
    bones = gear.TORSO | gear.HIPS | (gear.ARM_UPPER | gear.ARM_LOWER if sleeves else gear.ARM_UPPER)
    rule = kit.rule(bones, 0.45, bottom, top)
    if not sleeves:
        upper = kit.rule(gear.ARM_LOWER, 0.3)
        rule_fn = lambda i: rule(i) and not upper(i)
    else:
        rule_fn = rule
    obj = kit.add(gear.shell(kit.body, kit.rig, "Aketon", rule_fn, offset, None, thickness=0.003))
    kit.baked(obj, name, patterns.quilted(color, spacing, diamond=diamond, seed=seed), 512)
    kit.cover(gear.TORSO | gear.ARM_UPPER, 0.6, bottom + 0.04, top - 0.04)
    if sleeves:
        kit.cover(gear.ARM_LOWER, 0.7)
    return obj


def mail(kit, top=1.5, bottom=0.82, sleeves="long", offset=0.022, skirt_to=0.6, seed=10):
    bones = gear.TORSO | gear.HIPS | gear.ARM_UPPER | (gear.ARM_LOWER if sleeves == "long" else set())
    obj = kit.add(gear.shell(kit.body, kit.rig, "Mail", kit.rule(bones, 0.45, bottom, top), offset, None, thickness=0.002))
    kit.baked(obj, "mail_shirt", patterns.mail(seed), 512, 0.45, 0.55)
    if skirt_to:
        sk = kit.add(gear.skirt(kit.body, kit.rig, "MailSkirt", 0.98, skirt_to, None, flare=0.04, push=offset + 0.005, front_slit=0.1))
        kit.baked(sk, "mail_skirt", patterns.mail(seed + 1), 512, 0.45, 0.55)
    kit.cover(gear.TORSO | gear.ARM_UPPER, 0.6, bottom + 0.04, top - 0.04)
    return obj


def surcoat(kit, cross=True, base=None, red=None, hem=0.5, offset=0.032, sleeveless=True, chest_z=1.31, seed=8, slit=0.12):
    base = patterns.LINEN if base is None else base
    red = patterns.RED if red is None else red
    top = kit.add(gear.shell(kit.body, kit.rig, "Surcoat", kit.rule(gear.TORSO | gear.HIPS, 0.6, 0.9, 1.47, extra=lambda p: abs(p[0]) < 0.19),
                             offset, None, thickness=0.002))
    kit.baked(top, "linen_surcoat", patterns.tabard(cross, base, red, chest_z, seed=seed), 512)
    if hem is not None:
        sk = kit.add(gear.skirt(kit.body, kit.rig, "SurcoatSkirt", 1.0, hem, None, flare=0.07, push=offset + 0.006, front_slit=slit, hem_noise=0.012, seed=seed))
        kit.baked(sk, "linen_skirt", patterns.tabard(cross, base, red, 99.0, seed=seed + 1, hem_z=hem), 512)
    return top


def face_open(p, width=0.072, height=0.105, center=1.6):
    return not ((p[0] / width) ** 2 + ((p[2] - center) / height) ** 2 < 1 and p[1] < -0.05)


def hood(kit, color=srgb(0.6, 0.55, 0.45), name="linen_hood", cowl=1.46, seed=24, offset=0.009):
    obj = kit.add(gear.shell(kit.body, kit.rig, "Hood", kit.rule(gear.HEAD | gear.NECK | gear.TORSO, 0.5, cowl, 2.0, extra=face_open),
                             offset, None, thickness=0.003))
    kit.baked(obj, name, patterns.cloth(color, seed=seed, grime_start=0.0, grime=0.0), 512)
    return obj


def mail_coif(kit, cowl=1.42, seed=12):
    obj = kit.add(gear.shell(kit.body, kit.rig, "Coif", kit.rule(gear.HEAD | gear.NECK | gear.TORSO, 0.5, cowl, 2.0, extra=face_open),
                             0.012, None, thickness=0.002))
    kit.baked(obj, "mail_coif", patterns.mail(seed), 512, 0.45, 0.55)
    return obj


def scarf(kit, color=srgb(0.45, 0.09, 0.07), seed=26):
    rule = kit.rule(gear.NECK | gear.TORSO, 0.5, 1.43, 1.56, extra=lambda p: True)
    obj = kit.add(gear.shell(kit.body, kit.rig, "Scarf", rule, 0.022, None, thickness=0.004))
    kit.baked(obj, "wool_scarf", patterns.cloth(color, seed=seed, grime_start=0.0, grime=0.0), 512)
    return obj


def bracers(kit, color=srgb(0.28, 0.17, 0.1), length=0.13, offset=0.024, name="leather_bracers", metal=False):
    rule = kit.rule(gear.ARM_LOWER, 0.5)
    obj = kit.add(gear.shell(kit.body, kit.rig, "Bracers", lambda i: rule(i) and kit.near_wrist(i, length), offset, None, thickness=0.003))
    if metal:
        kit.baked(obj, "steel_vambrace", plate_pattern(), 512, 0.4, 0.55)
    else:
        kit.baked(obj, name, patterns.leather(color, seed=25), 512, 0.6)
    return obj


def plate_pattern(base=srgb(0.55, 0.55, 0.57), seed=30):
    from texbake import fbm

    def pattern(p):
        n = fbm(p * 18.0, 3, seed)
        streak = np.sin(p[:, 2] * 900 + fbm(p * 6, 2, seed + 1) * 4) * 0.03
        rust = np.clip((fbm(p * 14.0, 4, seed + 2) - 0.64) * 5, 0, 1)
        rgb = np.tile(base, (len(p), 1)) * (0.8 + 0.3 * n[:, None] + streak[:, None])
        rgb = rgb * (1 - rust[:, None] * 0.7) + srgb(0.38, 0.22, 0.1) * rust[:, None] * 0.7
        return np.clip(rgb, 0, 1), n * 0.3 + rust * 0.4, 0.3 + 0.25 * n + rust * 0.4
    return pattern


def greaves(kit, top=0.5, bottom=0.12):
    obj = kit.add(gear.shell(kit.body, kit.rig, "Greaves", kit.rule(gear.SHIN, 0.55, bottom, top, extra=lambda p: p[1] < 0.02), 0.024, None, thickness=0.003))
    kit.baked(obj, "steel_greaves", plate_pattern(), 512, 0.4, 0.55)
    return obj


def belt(kit, z=1.0, width=0.045, color=(0.85, 0.75, 0.7), push=0.045, name="Belt"):
    mat = kit.tile("leather", "leather_belt", color, 0.6)
    return kit.add(gear.belt(kit.body, kit.rig, name, z, width, mat, push=push))


def baldric(kit, left_hip=True, lift=0.042, width=0.038):
    mat = kit.tile("leather", "leather_belt", (0.85, 0.75, 0.7), 0.6)
    sx = -1 if left_hip else 1
    points = [Vector((sx * 0.12, 0.08, 1.46)), Vector((sx * 0.1, -0.12, 1.42)), Vector((0.0, -0.17, 1.25)), Vector((-sx * 0.14, -0.12, 1.02))]
    return kit.add(gear.surface_strap(kit.body, kit.rig, "Baldric", points, width, mat, lift=lift))


def pouch(kit, x=-0.17, z=0.94, push=0.1):
    mat = kit.tile("leather", "leather_belt", (0.85, 0.75, 0.7), 0.6)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.006, segments=2, affect="EDGES")
    gear.transform_bm(bm, Matrix.Translation((x, -push, z)) @ Matrix.Diagonal((0.075, 0.04, 0.09, 1)))
    gear.box_uv(bm, 6)
    return kit.add(gear.bind_like_body(gear.new_object("Pouch", bm, mat), kit.body, kit.rig))


def sheathed_sword(kit, side="L"):
    """Scabbard and hilt hanging from the belt on the given hip."""
    leather = kit.tile("leather", "leather_scabbard", (0.55, 0.42, 0.36), 0.6)
    steel = kit.tile("steel", "steel_weapon", (0.7, 0.7, 0.72), 0.35, 0.55)
    s = gear.scabbard(leather, steel, 0.8)
    sx = 1 if side == "L" else -1
    s.matrix_world = Matrix.Translation((sx * 0.2, -0.04, 0.2)) @ Matrix.Rotation(math.radians(-sx * 12), 4, "Y") @ Matrix.Rotation(math.radians(10), 4, "X")
    hilt = gear.sword(steel, leather, 0.0, 0.1)
    hilt.matrix_world = Matrix.Translation((sx * 0.215, -0.07, 1.02)) @ Matrix.Rotation(math.radians(sx * 12 + 180), 4, "Y") @ Matrix.Rotation(math.radians(-10 + 180), 4, "X")
    for o in (s, hilt):
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    obj = gear.join([s, hilt], "Scabbard")
    groups = {f"upperleg01.{side}": [(v.index, 0.35) for v in obj.data.vertices], "spine05": [(v.index, 0.65) for v in obj.data.vertices]}
    return kit.add(gear.bind(obj, kit.rig, groups))


def quiver_on_hip(kit, side="R", count=8, kind="arrow"):
    leather = kit.tile("leather", "leather_quiver", (0.7, 0.55, 0.45), 0.6)
    wood = kit.tile("wood", "wood_arrow", (0.85, 0.75, 0.6), 0.7)
    fletch = kit.tile("feather", "cloth_fletch", (1, 1, 1), 0.9)
    q = gear.quiver(leather, wood, fletch, count, 0.55 if kind == "arrow" else 0.38)
    sx = 1 if side == "L" else -1
    q.matrix_world = Matrix.Translation((sx * 0.21, 0.04, 0.55)) @ Matrix.Rotation(math.radians(sx * 8), 4, "Y") @ Matrix.Rotation(math.radians(-14), 4, "X")
    bpy.context.view_layer.objects.active = q
    bpy.ops.object.select_all(action="DESELECT")
    q.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    groups = {f"upperleg01.{side}": [(v.index, 0.4) for v in q.data.vertices], "spine05": [(v.index, 0.6) for v in q.data.vertices]}
    return kit.add(gear.bind(q, kit.rig, groups))


def kite_shield(kit, side="L", height=0.92, width=0.5, design=None, seed=12):
    steel = kit.tile("steel", "steel_weapon", (0.7, 0.7, 0.72), 0.35, 0.55)
    wood = kit.tile("wood", "wood_shield", (0.72, 0.6, 0.48), 0.7)
    face = gear.kite_face(height, width)
    kit.baked(face, "wood_shieldPaint", design or patterns.shield_cross(height=height, seed=seed), 1024, 0.7)
    shield = gear.finish_shield(face, steel, wood)
    return kit.add(kit.strap_shield(shield, side, drop=height * 0.17))


def round_shield(kit, side="L", radius=0.3, design=None, seed=13, drop=0.0):
    steel = kit.tile("steel", "steel_weapon", (0.7, 0.7, 0.72), 0.35, 0.55)
    wood = kit.tile("wood", "wood_shield", (0.72, 0.6, 0.48), 0.7)
    face = gear.round_face(radius)
    kit.baked(face, "wood_shieldPaint", design or round_design(radius, seed), 1024, 0.7)
    shield = gear.finish_shield(face, steel, wood, 0.016)
    return kit.add(kit.strap_shield(shield, side, drop=drop, standoff=0.06))


def round_design(radius, seed, base=srgb(0.42, 0.28, 0.16), rim_red=False):
    from texbake import fbm

    def pattern(p):
        r = np.sqrt(p[:, 0] ** 2 + p[:, 2] ** 2) / radius
        planks = np.abs(((p[:, 0] / 0.07) % 1) - 0.5) < 0.04
        grain = fbm(np.c_[p[:, 0] * 3, p[:, 2] * 40, p[:, 1]], 3, seed)
        rgb = np.tile(base, (len(p), 1)) * (0.75 + 0.4 * grain[:, None])
        rgb[planks] *= 0.6
        if rim_red:
            band = (r > 0.75) & (r < 0.9)
            rgb[band] = patterns.RED * 0.9
        return np.clip(rgb, 0, 1), grain * 0.4 - planks * 0.4, 0.75 + 0.1 * grain
    return pattern


def kettle_hat(kit, scale=1.0):
    steel = kit.tile("steel", "steel_helmet", (0.62, 0.62, 0.64), 0.42, 0.55)
    return kit.add(gear.kettle_hat(kit.rig, steel, scale))


def nasal_helm(kit, cheeks=False, scale=1.0):
    steel = kit.tile("steel", "steel_helmet", (0.62, 0.62, 0.64), 0.42, 0.55)
    return kit.add(gear.nasal_helm(kit.rig, steel, cheeks, scale))


def arming_cap(kit, color=srgb(0.58, 0.52, 0.42)):
    obj = kit.add(gear.shell(kit.body, kit.rig, "Cap", kit.rule(gear.HEAD, 0.6, 1.66, 2.0, extra=lambda p: p[1] > -0.11 or p[2] > 1.69), 0.008, None, thickness=0.003))
    kit.baked(obj, "linen_cap", patterns.quilted(color, 0.02, diamond=False, seed=40), 512)
    return obj


def pauldrons(kit):
    steel = kit.tile("steel", "steel_plate", (0.6, 0.6, 0.62), 0.35, 0.55)
    return [kit.add(gear.pauldron(kit.rig, s, steel)) for s in "LR"]


def knee_cops(kit):
    steel = kit.tile("steel", "steel_plate", (0.6, 0.6, 0.62), 0.35, 0.55)
    return [kit.add(gear.cap(kit.rig, "lowerleg01", s, steel, 0.06, Vector((0, -0.045, 0.01)))) for s in "LR"]


def elbow_cops(kit):
    steel = kit.tile("steel", "steel_plate", (0.6, 0.6, 0.62), 0.35, 0.55)
    return [kit.add(gear.cap(kit.rig, "lowerarm01", s, steel, 0.05, Vector((0, 0.035, 0.0)))) for s in "LR"]


def javelin_case(kit, wood, steel, side="R", count=3):
    """Leather case on the hip holding spare javelins, heads up."""
    leather = kit.tile("leather", "leather_quiver", (0.7, 0.55, 0.45), 0.6)
    case = gear.new_object("JavelinCase", gear.lathe([(0.04, 0), (0.045, 0.25), (0.05, 0.42)], 10, False, True), leather)
    parts = [case]
    for i in range(count):
        a = 2 * math.pi * i / count
        j = gear.javelin(wood, steel, 1.1)
        j.matrix_world = Matrix.Translation((0.018 * math.cos(a), 0.018 * math.sin(a), 0.55 + 0.04 * i))
        bpy.context.view_layer.objects.active = j
        bpy.ops.object.select_all(action="DESELECT")
        j.select_set(True)
        bpy.ops.object.transform_apply(location=True)
        parts.append(j)
    q = gear.join(parts, "JavelinCase")
    sx = 1 if side == "L" else -1
    q.matrix_world = Matrix.Translation((sx * 0.21, 0.06, 0.5)) @ Matrix.Rotation(math.radians(sx * 8), 4, "Y") @ Matrix.Rotation(math.radians(-12), 4, "X")
    bpy.context.view_layer.objects.active = q
    bpy.ops.object.select_all(action="DESELECT")
    q.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    groups = {f"upperleg01.{side}": [(v.index, 0.4) for v in q.data.vertices], "spine05": [(v.index, 0.6) for v in q.data.vertices]}
    return kit.add(gear.bind(q, kit.rig, groups))


def pennant(kit, z, length=0.5, width=0.16):
    """Swallow-tailed St George pennant below the lance head (in the weapon's frame)."""
    face = bmesh.new()
    pts = [(0.0, z), (0.0, z - width), (length, z - width * 0.5 - 0.03), (length * 0.8, z - width * 0.5), (length, z - width * 0.5 + 0.03)]
    verts = [face.verts.new((x, 0.0, zz)) for x, zz in pts]
    face.faces.new(verts)
    bmesh.ops.triangulate(face, faces=face.faces)
    uv = face.loops.layers.uv.new("UVMap")
    for f in face.faces:
        for loop in f.loops:
            p = loop.vert.co
            loop[uv].uv = (p.x / length, (p.z - z + width) / width)
    obj = gear.new_object("Pennant", face)
    obj.data.materials.append(kit.tile("feather", "cloth_pennant", (0.9, 0.85, 0.75), 0.9))
    mod = obj.modifiers.new("Thickness", "SOLIDIFY")
    mod.thickness = 0.003
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj
