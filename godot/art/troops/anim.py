"""Procedural, deterministic soldier animation.

A small forward-kinematics evaluator over the rest matrices plus analytic
two-bone IK. Feet are planted by construction: during stance a foot target
moves backwards in a straight line at exactly the clip's ground speed, so the
in-place cycle has no foot slide (profile_gait.gd measures the result).
Hands follow the weapon: a desired weapon frame is turned into a wrist frame
through the rigid wrist->weapon offset captured at bind time.

Axes (armature space): +Z up, -Y forward, +X = soldier's left.
"""
import math

import bpy
from mathutils import Matrix, Quaternion, Vector

FPS = 30
UP = Vector((0, 0, 1))
FWD = Vector((0, -1, 0))
LEFT = Vector((1, 0, 0))


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def quat_axis(axis, degrees):
    return Quaternion(Vector(axis).normalized(), math.radians(degrees))


class Skeleton:
    def __init__(self, rig):
        self.rig = rig
        self.rest = {b.name: b.matrix_local.copy() for b in rig.data.bones}
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in rig.data.bones}
        self.order = [b.name for b in rig.data.bones]
        self.root_name = "root" if "root" in self.rest else self.order[0]
        self.reset()

    def reset(self):
        self.local = {name: Quaternion() for name in self.rest}
        self.root_offset = Vector()
        self._cache = {}

    def dirty(self):
        self._cache = {}

    def pose(self, name):
        """Armature-space pose matrix of a bone."""
        if name in self._cache:
            return self._cache[name]
        rest = self.rest[name]
        parent = self.parent[name]
        basis = self.local[name].to_matrix().to_4x4()
        if name == self.root_name:
            basis.translation = self.rest[name].to_3x3().inverted() @ self.root_offset
        if parent is None:
            m = rest @ basis
        else:
            m = self.pose(parent) @ (self.rest[parent].inverted() @ rest) @ basis
        self._cache[name] = m
        return m

    def head(self, name):
        return self.pose(name).translation.copy()

    def rotate_rest_frame(self, name, axis, degrees):
        """Rotate a bone relative to its parent about an axis given in the rest (armature) frame."""
        r = self.rest[name].to_3x3()
        q = (r.inverted() @ quat_axis(axis, degrees).to_matrix() @ r).to_quaternion()
        self.local[name] = q @ self.local[name]
        self.dirty()

    def set_world_rotation(self, name, rotation):
        """Sets the bone so its armature-space orientation equals rotation (3x3)."""
        parent = self.parent[name]
        if parent is None:
            frame = self.rest[name].to_3x3()
        else:
            frame = (self.pose(parent) @ (self.rest[parent].inverted() @ self.rest[name])).to_3x3()
        self.local[name] = (frame.inverted() @ rotation).to_quaternion()
        self.dirty()

    def aim(self, name, target_dir, from_point=None, to_point=None):
        """Rotates a bone (and its subtree) so the vector from_point->to_point (current pose) points along target_dir."""
        current = (to_point - from_point).normalized()
        delta = current.rotation_difference(target_dir.normalized())
        rotation = delta.to_matrix() @ self.pose(name).to_3x3()
        self.set_world_rotation(name, rotation)

    def two_bone(self, upper, lower, end, target, pole):
        """Analytic IK: upper's head stays, end's head reaches target, middle joint bends towards pole."""
        a = self.head(upper)
        b = self.head(lower)
        c = self.head(end)
        l1, l2 = (b - a).length, (c - b).length
        to_target = target - a
        dist = max(1e-4, min(to_target.length, (l1 + l2) * 0.9995))
        direction = to_target.normalized()
        cos_a = max(-1.0, min(1.0, (l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist)))
        bend_axis = direction.cross(pole).normalized()
        if bend_axis.length < 1e-6:
            bend_axis = direction.orthogonal().normalized()
        knee_dir = Quaternion(bend_axis, math.acos(cos_a)) @ direction
        knee = a + knee_dir * l1
        self.aim(upper, knee - a, a, b)
        b2 = self.head(lower)
        c2 = self.head(end)
        self.aim(lower, a + direction * dist - b2, b2, c2)

    def key(self, frame):
        rig = self.rig
        for name in self.order:
            pb = rig.pose.bones[name]
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = self.local[name]
            pb.keyframe_insert("rotation_quaternion", frame=frame, group=name)
        root = rig.pose.bones[self.root_name]
        root.location = self.rest[self.root_name].to_3x3().inverted() @ self.root_offset
        root.keyframe_insert("location", frame=frame, group=self.root_name)


class Rig:
    """Soldier-specific helpers on top of the skeleton."""

    def __init__(self, kit, weapon=None, weapon_side="R", offhand=None):
        self.kit = kit
        self.sk = Skeleton(kit.rig)
        self.weapon = weapon          # dict: grip offset of the main weapon
        self.offhand = offhand
        rest = self.sk.rest
        self.hip = {s: rest[f"upperleg01.{s}"].translation.copy() for s in "LR"}
        self.ankle_rest = {s: rest[f"foot.{s}"].translation.copy() for s in "LR"}
        self.ankle_height = self.ankle_rest["L"].z
        self.foot_rest = {s: rest[f"foot.{s}"].to_3x3() for s in "LR"}
        self.toe_rest = {s: rest[f"toe1-1.{s}"].to_3x3() for s in "LR"}
        self.wrist_rest = {s: rest[f"wrist.{s}"] for s in "LR"}
        self.weapon_offsets = {}

    # --- whole body -------------------------------------------------------
    def body(self, bob=0.0, sway=0.0, pelvis_yaw=0.0, pelvis_roll=0.0, lean=0.0, spine_twist=0.0,
             spine_bend=0.0, head_pitch=0.0, head_yaw=0.0, crouch=0.0, side_bend=0.0):
        sk = self.sk
        sk.reset()
        sk.root_offset = Vector((sway, 0.0, bob - crouch))
        sk.rotate_rest_frame("root", UP, pelvis_yaw)
        sk.rotate_rest_frame("root", FWD, pelvis_roll)
        sk.rotate_rest_frame("root", LEFT, lean * 0.4)
        per = spine_twist / 4.0
        for name in ("spine05", "spine04", "spine03", "spine02"):
            sk.rotate_rest_frame(name, UP, per - pelvis_yaw * 0.25)
            sk.rotate_rest_frame(name, LEFT, (lean * 0.6 + spine_bend) / 4.0)
            sk.rotate_rest_frame(name, FWD, side_bend / 4.0 - pelvis_roll * 0.25)
        sk.rotate_rest_frame("neck01", LEFT, head_pitch * 0.4 - lean * 0.3)
        sk.rotate_rest_frame("head", LEFT, head_pitch * 0.6)
        sk.rotate_rest_frame("head", UP, head_yaw)

    def foot(self, side, position, pitch=0.0, yaw=0.0, toe=0.0, knee_out=0.0):
        """Plants the ankle at position (armature space) with the foot pitched (deg, toe up positive)."""
        sk = self.sk
        pole = (FWD + LEFT * (knee_out if side == "L" else -knee_out)).normalized()
        sk.two_bone(f"upperleg01.{side}", f"lowerleg01.{side}", f"foot.{side}", position, pole)
        rot = quat_axis(UP, yaw).to_matrix() @ quat_axis(LEFT, pitch).to_matrix() @ self.foot_rest[side]
        sk.set_world_rotation(f"foot.{side}", rot)
        if toe:
            sk.rotate_rest_frame(f"toe1-1.{side}", LEFT, -toe)

    def arm_to(self, side, wrist_matrix, elbow_pole=None):
        """Places the wrist at a full armature-space matrix through arm IK."""
        sk = self.sk
        pole = elbow_pole or (Vector((0.35 if side == "L" else -0.35, 0.6, -0.6))).normalized()
        sk.two_bone(f"upperarm01.{side}", f"lowerarm01.{side}", f"wrist.{side}", wrist_matrix.translation, pole)
        # Forearm twist: turn the twist bone so the forearm's back follows the back of the hand
        # (anything rigid on the forearm, e.g. a shield, then keeps its intended facing).
        import gear
        rest = sk.rest
        palm_rest, _, _ = gear.palm_normal(lambda n: rest[n].translation.copy(), side)
        wrist_rest = rest[f"wrist.{side}"].to_3x3()
        desired = wrist_matrix.to_3x3() @ (wrist_rest.inverted() @ palm_rest)
        twist_bone = f"lowerarm02.{side}"
        frame = sk.pose(twist_bone).to_3x3()
        current = frame @ (rest[twist_bone].to_3x3().inverted() @ palm_rest)
        axis = (sk.head(f"wrist.{side}") - sk.head(twist_bone)).normalized()
        a = (current - axis * current.dot(axis)).normalized()
        b = (desired - axis * desired.dot(axis)).normalized()
        angle = math.atan2(a.cross(b).dot(axis), a.dot(b))
        sk.set_world_rotation(twist_bone, Quaternion(axis, angle).to_matrix() @ frame)
        sk.set_world_rotation(f"wrist.{side}", wrist_matrix.to_3x3())

    def hand_free(self, side, forward=0.0, out=0.0, bend=20.0):
        """Relaxed arm hanging beside the thigh, swung forward by `forward` degrees."""
        sk = self.sk
        sign = 1 if side == "L" else -1
        shoulder = sk.head(f"upperarm01.{side}")
        reach = 0.56
        swing = math.radians(forward)
        direction = Vector((sign * (0.18 + out * 0.004), -math.sin(swing) * 0.9 - 0.06, -math.cos(swing))).normalized()
        target = shoulder + direction * reach
        hand_dir = (direction + Vector((0, -0.25, 0))).normalized()
        palm = Vector((-sign, 0.15, 0.0))
        import poses
        m = poses.hand_frame(self, side, hand_dir, palm).to_4x4()
        m.translation = target
        self.arm_to(side, m, Vector((sign * 0.2, 0.8, -0.2)).normalized())
        self.fist(side, 0.35)

    def fist(self, side, amount=1.0):
        import gear
        sk = self.sk
        rest = sk.rest
        palm, across, along = gear.palm_normal(lambda n: rest[n].translation.copy(), side)
        # Curl about the knuckle line, choosing the sense that brings fingertips into the palm.
        axis = across
        tip = rest[f"finger3-3.{side}"].translation - rest[f"finger3-1.{side}"].translation
        if (quat_axis(axis, 30) @ tip).dot(palm) < tip.dot(palm):
            axis = -axis
        for finger, angles in ((2, (62, 78, 48)), (3, (66, 80, 50)), (4, (70, 80, 50)), (5, (74, 78, 46))):
            for k, a in enumerate(angles):
                sk.rotate_rest_frame(f"finger{finger}-{k + 1}.{side}", axis, a * amount)
        thumb_axis = along if (quat_axis(along, 30) @ (rest[f"finger1-3.{side}"].translation - rest[f"finger1-2.{side}"].translation)).dot(palm) > 0 else -along
        sk.rotate_rest_frame(f"finger1-2.{side}", thumb_axis, 30 * amount)
        sk.rotate_rest_frame(f"finger1-3.{side}", axis, 35 * amount)

    # --- weapons -------------------------------------------------------------
    def capture_weapon(self, key, side, grip_matrix):
        """Stores the rigid offset between the wrist and a weapon grip frame (rest pose)."""
        self.weapon_offsets[key] = (side, self.wrist_rest[side].inverted() @ grip_matrix)

    def weapon_to(self, key, origin, z_dir, knuckles, elbow_pole=None):
        """Moves a captured weapon so its grip frame sits at origin with +Z along z_dir and
        the knuckles of the holding hand facing `knuckles`."""
        side, offset = self.weapon_offsets[key]
        z = z_dir.normalized()
        y = -(knuckles - z * knuckles.dot(z)).normalized()
        x = y.cross(z).normalized()
        frame = Matrix((x, y, z)).transposed().to_4x4()
        frame.translation = origin
        wrist = frame @ offset.inverted()
        self.arm_to(side, wrist, elbow_pole)
        self.fist(side)

    def key(self, frame):
        self.sk.key(frame)


def new_action(rig, name, frames, loop=True):
    action = bpy.data.actions.new(name)
    if rig.animation_data is None:
        rig.animation_data_create()
    rig.animation_data.action = action
    action.frame_range = (0, frames)
    action.use_frame_range = True
    action.use_cyclic = loop
    return action


def finish_action(rig, action, loop):
    if loop:
        for fcurve in _fcurves(action):
            for kp in fcurve.keyframe_points:
                kp.interpolation = "LINEAR"
    track = rig.animation_data.nla_tracks.new()
    track.name = action.name
    strip = track.strips.new(action.name, int(action.frame_range[0]), action)
    strip.mute = True
    rig.animation_data.action = None


def _fcurves(action):
    try:
        return [fc for layer in action.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]
    except AttributeError:
        return list(action.fcurves)


# --------------------------------------------------------------- gait

def gait_feet(t, speed, cycle, stance=0.6, lift=0.11, width=0.11, toe_out=6):
    """Planted-foot trajectories for an in-place cycle. t in [0,1). Returns per side
    (position, pitch, toe) with stance feet moving backwards at `speed`."""
    # Ground covered while a foot is planted: it must travel backwards at exactly `speed`.
    stride = speed * cycle * stance
    out = {}
    for side, phase in (("L", 0.0), ("R", 0.5)):
        u = (t + phase) % 1.0
        x = width if side == "L" else -width
        if u < stance:
            s = u / stance
            y = -stride * 0.5 + stride * s          # forward is -Y; foot slides back towards +Y
            z = 0.0
            pitch = lerp(14, 0, smooth(s / 0.15)) if s < 0.15 else (lerp(0, -18, smooth((s - 0.7) / 0.3)) if s > 0.7 else 0)
            toe = 0 if s < 0.7 else lerp(0, 30, smooth((s - 0.7) / 0.3))
        else:
            s = (u - stance) / (1 - stance)
            y = stride * 0.5 - stride * smooth(s)
            z = lift * math.sin(math.pi * s) ** 1.2
            pitch = lerp(-18, 14, smooth(s))
            toe = lerp(30, 0, smooth(s * 2))
        out[side] = (Vector((x, y, z)), pitch, toe)
    return out


def walk_like(r, name, speed, cycle, stance, lift, arms, bob_amp=0.025, lean=4.0, frames=None):
    rig = r.kit.rig
    frames = frames or int(round(cycle * FPS))
    action = new_action(rig, name, frames)
    for f in range(frames + 1):
        t = (f / frames) % 1.0
        feet = gait_feet(t, speed, cycle, stance, lift)
        # Pelvis: low at contact, high mid-stance (twice per cycle); sway over the stance foot.
        bob = -bob_amp * math.cos(4 * math.pi * t) - bob_amp * 0.6
        sway = 0.02 * math.sin(2 * math.pi * t)
        yaw = 5 * math.sin(2 * math.pi * t)
        r.body(bob=bob, sway=sway, pelvis_yaw=yaw, pelvis_roll=-2.5 * math.sin(2 * math.pi * t), lean=lean,
               spine_twist=-yaw * 1.6, head_pitch=-lean * 0.5)
        for side in "LR":
            p, pitch, toe = feet[side]
            ankle = Vector((p.x, p.y, r.ankle_height + p.z))
            r.foot(side, ankle, pitch, 0, toe)
        arms(r, t)
        r.key(f)
    finish_action(rig, action, True)
    return action


def hold(r, name, frames, pose, loop=True):
    rig = r.kit.rig
    action = new_action(rig, name, frames, loop)
    for f in range(frames + 1):
        pose(r, f / frames)
        r.key(f)
    finish_action(rig, action, loop)
    return action


def stand_feet(r, t=0.0, spread=0.13, stagger=0.06, crouch=0.0):
    r.foot("L", Vector((spread, -stagger, r.ankle_height)), 0, -6)
    r.foot("R", Vector((-spread, stagger, r.ankle_height)), 0, 8)


def build_all(kit, info):
    """Builds every clip the game expects for this soldier."""
    import poses
    scene = bpy.context.scene
    scene.render.fps = FPS
    r = Rig(kit)
    for key, (side, matrix) in kit.grips.items():
        r.capture_weapon(key, side, matrix)
    style = poses.STYLES[info["style"]]
    style(r, info)
