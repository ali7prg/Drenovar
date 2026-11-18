"""Mounted soldiers: the project's existing horse (geometry, tack, caparison, rig and
horse animation from the 0.5.9 GLB) carries a new MakeHuman rider.

The rider skeleton is joined into the horse armature with its root parented to
HorseBack. Rider poses are solved in the HorseBack rest frame (stirrups, reins,
weapon), so the rider rides every horse clip without sliding in the saddle.
"""
import math
import os

import bpy
import bmesh
from mathutils import Matrix, Vector

import anim
import poses
from anim import FWD, LEFT, UP, smooth

HORSE_PREFIXES = ("Horse", "Front", "Hind", "Tail")
OLD_RIDER = ("Hips", "Spine", "Chest", "Neck", "Head", "RightUpperArm", "RightForearm", "RightHand", "LeftUpperArm",
             "LeftForearm", "LeftHand", "RightThigh", "RightShin", "RightFoot", "RightToe", "LeftThigh", "LeftShin",
             "LeftFoot", "LeftToe")


def is_horse_bone(name):
    return name.startswith(HORSE_PREFIXES)


def import_horse(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    armature = next(o for o in new if o.type == "ARMATURE")
    meshes = [o for o in new if o.type == "MESH"]
    kept = []
    # Keep only vertices that belong to the horse (body, mane, tack, caparison).
    for obj in meshes:
        names = {g.index: g.name for g in obj.vertex_groups}
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        deform = bm.verts.layers.deform.verify()
        doomed = []
        for v in bm.verts:
            total = sum(v[deform].values()) or 1.0
            horse = sum(w for g, w in v[deform].items() if is_horse_bone(names.get(g, ""))) / total
            if horse < 0.5:
                doomed.append(v)
        bmesh.ops.delete(bm, geom=doomed, context="VERTS")
        bm.to_mesh(obj.data)
        bm.free()
        if len(obj.data.vertices) == 0:
            bpy.data.objects.remove(obj)
        else:
            kept.append(obj)
            for g in list(obj.vertex_groups):
                if not is_horse_bone(g.name):
                    obj.vertex_groups.remove(g)
    # Remove the old rider bones.
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    saddle = None
    for eb in list(armature.data.edit_bones):
        if eb.name == "Hips":
            saddle = (armature.matrix_world @ eb.head).copy()
        if not is_horse_bone(eb.name):
            armature.data.edit_bones.remove(eb)
    bpy.ops.object.mode_set(mode="OBJECT")
    # Strip rider channels from the horse actions.
    for action in bpy.data.actions:
        for bag in anim_channelbags(action):
            for fc in list(bag.fcurves):
                bone = fc.data_path.split('"')[1] if '"' in fc.data_path else ""
                if bone and not is_horse_bone(bone):
                    bag.fcurves.remove(fc)
    return armature, kept, saddle


def anim_channelbags(action):
    bags = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            bags.extend(strip.channelbags)
    return bags


def mount(kit, horse_path, info, seat_drop=0.02):
    """Joins the built rider into the imported horse armature and animates every clip."""
    rider_rig = kit.rig
    rider_bones = [b.name for b in rider_rig.data.bones]
    horse, horse_meshes, saddle = import_horse(horse_path)
    # Rider in the saddle: pelvis on the old rider's hip joint.
    pelvis = rider_rig.data.bones["root"].head_local
    offset = Vector((0.0, saddle.y - pelvis.y, saddle.z - pelvis.z - seat_drop))
    shift = Matrix.Translation(offset)
    for child in list(rider_rig.children):
        if child.type == "MESH":
            child.data.transform(shift)
        mod = next((m for m in child.modifiers if m.type == "ARMATURE"), None)
        if mod:
            mod.object = horse
        child.parent = horse
        child.matrix_parent_inverse = Matrix.Identity(4)
        child.matrix_world = horse.matrix_world.copy()
    # Whole-armature transform (per-bone moves would double-shift connected bones).
    rider_rig.data.transform(shift)
    # Join armatures: rider bones become children of HorseBack.
    bpy.ops.object.select_all(action="DESELECT")
    horse.select_set(True)
    rider_rig.select_set(True)
    bpy.context.view_layer.objects.active = horse
    bpy.ops.object.join()
    bpy.ops.object.mode_set(mode="EDIT")
    horse.data.edit_bones["root"].parent = horse.data.edit_bones["HorseBack"]
    bpy.ops.object.mode_set(mode="OBJECT")
    kit.rig = horse
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            for m in obj.modifiers:
                if m.type == "ARMATURE":
                    m.object = horse
    # Weapon grips were captured in the rider's original frame; move them with it.
    for key, (side, matrix) in list(kit.grips.items()):
        kit.grips[key] = (side, Matrix.Translation(offset) @ matrix)
    animate_rider(kit, horse, rider_bones, info)
    return horse


class SeatRig(anim.Rig):
    """anim.Rig restricted to the rider bones; poses solved in the HorseBack rest frame."""

    def __init__(self, kit, rider_bones):
        super().__init__(kit)
        self.rider_bones = set(rider_bones)
        self.sk.order = [n for n in self.sk.order if n in self.rider_bones]


def animate_rider(kit, horse, rider_bones, info):
    r = SeatRig(kit, rider_bones)
    for key, (side, matrix) in kit.grips.items():
        r.capture_weapon(key, side, matrix)
    root = r.sk.rest["root"].translation
    stirrup = {"L": root + Vector((0.3, -0.07, -0.8)), "R": root + Vector((-0.3, -0.07, -0.8))}
    reins = root + Vector((0.06, -0.38, 0.12))

    def seat(r, t, lean=4.0, bob=0.0, twist=0.0, pitch=0.0, sway=0.0):
        r.body(bob=bob, sway=sway, lean=lean, spine_twist=twist, head_pitch=pitch - lean * 0.5)
        sk = r.sk
        for side, sign in (("L", 1), ("R", -1)):
            target = stirrup[side] + Vector((0, 0, bob * 0.3))
            r.foot(side, target, 10, -sign * 4, 0, knee_out=0.45)

    def shield_reins(r, t, raise_=0.0):
        poses.shield_arm(r, hand=(0.05, -0.36, -0.2 + raise_), forearm=(-0.6, -1.0, 0.05), palm=(-0.3, 0.2, -1.0),
                         elbow=(0.9, 0.2, -0.5))

    def carry(r, t, lift=0.0):
        r.weapon_to("main", poses.chest_point(r, (-0.3, -0.18, -0.12 + lift)), Vector((0.0, -0.2, 1.0)), FWD + LEFT * 0.2)

    def thrust(r, t, cycles=1):
        local = (t * cycles) % 1.0
        windup = smooth(local / 0.35)
        strike = smooth((local - 0.35) / 0.14) if local > 0.35 else 0.0
        recover = smooth((local - 0.62) / 0.38) if local > 0.62 else 0.0
        drive = strike * (1 - recover)
        seat(r, t, lean=6 + 14 * drive, twist=-16 * windup * (1 - strike) + 20 * drive)
        shield_reins(r, t, 0.08 * drive)
        rest_pos = poses.chest_point(r, (-0.3, -0.18, -0.12))
        back = poses.chest_point(r, (-0.3, 0.12, 0.18))
        reach = poses.chest_point(r, (-0.18, -0.62, 0.0))
        pos = rest_pos.lerp(back, windup * (1 - strike)).lerp(reach, drive).lerp(rest_pos, recover)
        z_dir = Vector((0.0, -0.2, 1.0)).lerp(Vector((0.0, -1.0, 0.05)), windup * (1 - recover))
        r.weapon_to("main", pos, z_dir, UP * (1 - recover) + FWD * recover + LEFT * 0.2)

    def clip_pose(name):
        if name in ("Attack",):
            return lambda r, t: thrust(r, t)
        if name == info["drill"]:
            return lambda r, t: thrust(r, t, 2)
        if name == "Recruit_Showcase":
            def showcase(r, t):
                up = smooth(t / 0.3) * (1 - smooth((t - 0.7) / 0.3))
                seat(r, t, lean=2 - 4 * up, pitch=-6 * up)
                shield_reins(r, t, 0.1 * up)
                r.weapon_to("main", poses.chest_point(r, (-0.32, -0.14, -0.12 + 0.35 * up)), Vector((0.0, -0.2 - 0.3 * up, 1.0)), FWD + LEFT * 0.2)
            return showcase
        if name == "Hit":
            def hit(r, t):
                k = math.sin(math.pi * min(1.0, t * 1.4)) * (1 - smooth((t - 0.5) / 0.5))
                seat(r, t, lean=4 - 14 * k, pitch=14 * k)
                shield_reins(r, t)
                carry(r, t)
            return hit
        if name == "Death":
            def death(r, t):
                k = smooth(t / 0.6)
                seat(r, t, lean=4 + 35 * k, pitch=25 * k, twist=10 * k)
                shield_reins(r, t, -0.1 * k)
                carry(r, t, -0.15 * k)
            return death
        if name in ("Walk", "Run"):
            run = name == "Run"

            def ride(r, t):
                b = math.sin(4 * math.pi * t) * (0.025 if run else 0.012)
                seat(r, t, lean=10 if run else 5, bob=b)
                shield_reins(r, t)
                carry(r, t, lift=b)
            return ride

        def idle(r, t):
            b = math.sin(2 * math.pi * t) * 0.004
            seat(r, t, bob=b, pitch=-2)
            shield_reins(r, t)
            carry(r, t)
        return idle

    for action in [a for a in bpy.data.actions]:
        horse.animation_data.action = action
        try:
            horse.animation_data.action_slot = action.slots[0]
        except (AttributeError, IndexError):
            pass
        start, end = int(action.frame_range[0]), int(action.frame_range[1])
        pose = clip_pose(action.name)
        frames = max(1, end - start)
        for f in range(start, end + 1):
            pose(r, (f - start) / frames)
            r.key(f)
    horse.animation_data.action = None
