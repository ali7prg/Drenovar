"""Combat styles: every clip the game uses, per weapon family.

Clip names consumed by the game: Idle, Walk, Run, Attack, Hit, Death,
Shield_Block (shield bearers), the unit's drill clip from game.json
(Spear_Drill, Sword_Drill, Bow_Draw, Crossbow_Reload, Javelin_Drill,
Mounted_Drill) and Recruit_Showcase for mounted units.
Attack peaks at ~49% of the clip: landscape.gd seeks attacks with the impact at
490 ms of a 1000 ms window.
"""
import math

from mathutils import Matrix, Vector

from anim import FPS, FWD, LEFT, UP, hold, lerp, quat_axis, smooth, walk_like


def chest_point(r, offset):
    """A point fixed to the upper chest (follows breathing, lean and sway)."""
    chest = r.sk.pose("spine02")
    rest = r.sk.rest["spine02"]
    return chest @ (rest.inverted() @ (rest.translation + Vector(offset)))


def chest_dir(r, direction):
    chest = r.sk.pose("spine02").to_3x3()
    rest = r.sk.rest["spine02"].to_3x3()
    return (chest @ (rest.inverted() @ Vector(direction))).normalized()


def hand_frame(r, side, along, palm):
    """Wrist rotation with the hand pointing `along` and the palm facing `palm`."""
    import gear
    rest = r.sk.rest
    rr = rest[f"wrist.{side}"].to_3x3()
    p_rest, _, hand_along = gear.palm_normal(lambda n: rest[n].translation.copy(), side)
    y_l = rr.inverted() @ hand_along
    p_l = rr.inverted() @ p_rest

    def basis(a, b):
        a = a.normalized()
        b = (b - a * b.dot(a)).normalized()
        return Matrix((a, b, a.cross(b))).transposed()
    return basis(along, palm) @ basis(y_l, p_l).inverted()


def shield_arm(r, side="L", hand=(-0.05, -0.31, -0.05), forearm=(-1.0, -0.15, 0.03), palm=(0.0, 1.0, -0.15), raise_=0.0,
               elbow=(0.55, -0.55, -0.6)):
    """Shield arm: elbow in front of the belly on the shield side, forearm horizontal across
    the body through the enarmes, palm towards the chest. hand/forearm are chest-relative."""
    pos = chest_point(r, (hand[0], hand[1], hand[2] + raise_))
    along = chest_dir(r, forearm)
    palm_dir = chest_dir(r, palm)
    m = hand_frame(r, side, along, palm_dir).to_4x4()
    m.translation = pos
    r.arm_to(side, m, chest_dir(r, elbow))
    r.fist(side)


def breathe(t, amount=1.0):
    return math.sin(2 * math.pi * t) * amount


def stance(r, crouch=0.02, spread=0.13, lead=0.07):
    r.foot("L", Vector((spread, -lead, r.ankle_height)), 0, -8)
    r.foot("R", Vector((-spread, lead, r.ankle_height)), 0, 10)


# ----------------------------------------------------------------- spear + shield

def spear_shield(r, info):
    grip_height = info.get("grip_from_butt", 1.05)

    def guard(r, t, raise_=0.0):
        shield_arm(r, raise_=raise_)

    def spear_upright(r, t, lift=0.0, sway=0.0):
        origin = chest_point(r, (-0.27, -0.16, -0.36 + lift))
        origin.z = max(origin.z, grip_height + lift)
        r.weapon_to("main", origin, Vector((sway, -0.07, 1.0)), FWD + LEFT * 0.25)

    def idle(r, t):
        b = breathe(t)
        r.body(bob=-0.012 + 0.004 * b, lean=2, spine_bend=-0.8 * b, head_pitch=-1 + 0.8 * b, head_yaw=4 * math.sin(2 * math.pi * t))
        stance(r)
        guard(r, t)
        spear_upright(r, t)
    hold(r, "Idle", 90, idle)

    def walk_arms(r, t):
        guard(r, t)
        spear_upright(r, t, lift=0.06 + 0.02 * math.sin(4 * math.pi * t), sway=0.03 * math.sin(2 * math.pi * t))
    walk_like(r, "Walk", 1.35, 1.1, 0.6, 0.1, walk_arms, lean=3)

    def run_arms(r, t):
        guard(r, t, raise_=0.04)
        origin = chest_point(r, (-0.25, -0.22, -0.28))
        r.weapon_to("main", origin, Vector((0.0, -1.0, 0.75)), UP + FWD * 0.2)
    walk_like(r, "Run", 3.4, 0.72, 0.36, 0.17, run_arms, bob_amp=0.035, lean=11)

    def thrust(r, t, cycles=1):
        local = (t * cycles) % 1.0
        windup = smooth(local / 0.35)
        strike = smooth((local - 0.35) / 0.14) if local > 0.35 else 0.0
        recover = smooth((local - 0.6) / 0.4) if local > 0.6 else 0.0
        drive = strike * (1 - recover)
        r.body(bob=-0.04 - 0.03 * drive, lean=4 + 12 * drive, spine_twist=-14 * windup * (1 - recover) + 22 * drive,
               pelvis_yaw=8 * drive, head_pitch=-6 * drive)
        r.foot("L", Vector((0.14, -0.1 - 0.22 * drive, r.ankle_height)), 0, -10)
        r.foot("R", Vector((-0.15, 0.14 + 0.05 * drive, r.ankle_height)), 0, 14, 0)
        shield_arm(r, raise_=0.06 * drive)
        back = chest_point(r, (-0.22, 0.1, 0.12))
        reach = chest_point(r, (-0.12, -0.6, 0.06))
        rest_pos = chest_point(r, (-0.27, -0.16, -0.36))
        pos = rest_pos.lerp(back, windup * (1 - strike)).lerp(reach, drive)
        pos = pos.lerp(rest_pos, recover * 0)
        direction = Vector((0, -1, 0.1)).lerp(Vector((0, -1, 0.0)), drive)
        up_pose = Vector((0.0, -0.07, 1.0))
        z_dir = up_pose.lerp(direction, smooth(min(1.0, local / 0.25)) * (1 - recover))
        r.weapon_to("main", pos, z_dir, UP * (1 - recover) + FWD * recover + LEFT * 0.2)
    hold(r, "Attack", 30, lambda r, t: thrust(r, t), loop=False)
    hold(r, info["drill"], 60, lambda r, t: thrust(r, t, 2), loop=True)

    def block(r, t):
        b = breathe(t, 0.5)
        r.body(bob=-0.06, crouch=0.02, lean=8, head_pitch=-4 + b)
        r.foot("L", Vector((0.15, -0.16, r.ankle_height)), 0, -10)
        r.foot("R", Vector((-0.16, 0.16, r.ankle_height)), 0, 14)
        shield_arm(r, hand=(-0.08, -0.36, 0.12), forearm=(-1.0, -0.1, 0.12), palm=(0.0, 1.0, -0.1))
        r.weapon_to("main", chest_point(r, (-0.25, -0.28, -0.05)), Vector((0, -1, 0.12)), UP + LEFT * 0.2)
    hold(r, "Shield_Block", 40, block)

    common_hit_death(r, idle_arms=lambda r, t: (guard(r, t), spear_upright(r, t)))


def common_hit_death(r, idle_arms):
    def hit(r, t):
        k = math.sin(math.pi * min(1.0, t * 1.4)) * (1 - smooth((t - 0.5) / 0.5))
        r.body(bob=-0.02 - 0.03 * k, lean=-10 * k, spine_bend=-8 * k, head_pitch=14 * k, side_bend=4 * k, spine_twist=6 * k)
        r.foot("L", Vector((0.13, -0.07 + 0.08 * k, r.ankle_height)), 0, -8)
        r.foot("R", Vector((-0.13, 0.07 + 0.05 * k, r.ankle_height)), 0, 10)
        idle_arms(r, t)
    hold(r, "Hit", 12, hit, loop=False)

    def death(r, t):
        fall = smooth(t / 0.75)
        land = smooth((t - 0.6) / 0.4)
        sk = r.sk
        r.body(bob=0.0, lean=-6 * fall, head_pitch=20 * fall - 12 * land)
        hip_h = sk.rest["root"].translation.z
        sk.root_offset = Vector((0.0, 0.42 * fall, -(hip_h - 0.13) * fall))
        sk.rotate_rest_frame("root", LEFT, -84 * fall)
        sk.dirty()
        for side, sign in (("L", 1), ("R", -1)):
            sk.rotate_rest_frame(f"upperleg01.{side}", LEFT, 22 * fall - 18 * land)
            sk.rotate_rest_frame(f"lowerleg01.{side}", LEFT, -40 * fall + 30 * land)
            sk.rotate_rest_frame(f"upperleg01.{side}", FWD, sign * 8 * land)
            sk.rotate_rest_frame(f"upperarm01.{side}", FWD, sign * (38 + 40 * fall))
            sk.rotate_rest_frame(f"upperarm01.{side}", LEFT, -30 * fall)
            sk.rotate_rest_frame(f"lowerarm01.{side}", LEFT, -25 * fall)
            r.fist(side, 0.6)
    hold(r, "Death", 36, death, loop=False)


# ----------------------------------------------------------------- sword + shield

def sword_shield(r, info):
    def guard(r, t, raise_=0.0):
        shield_arm(r, raise_=raise_)

    def low_guard(r, t, swing=0.0):
        origin = chest_point(r, (-0.27, -0.2, -0.36))
        r.weapon_to("main", origin, Vector((0.1 + swing, -0.55, -0.83)), Vector((-0.2, -1.0, 0.3)))

    def idle(r, t):
        b = breathe(t)
        r.body(bob=-0.012 + 0.004 * b, lean=2, spine_bend=-0.8 * b, head_pitch=-1 + 0.8 * b, head_yaw=4 * math.sin(2 * math.pi * t))
        stance(r)
        guard(r, t)
        low_guard(r, t)
    hold(r, "Idle", 90, idle)

    def walk_arms(r, t):
        guard(r, t)
        low_guard(r, t, 0.08 * math.sin(2 * math.pi * t))
    walk_like(r, "Walk", 1.35, 1.1, 0.6, 0.1, walk_arms, lean=3)

    def run_arms(r, t):
        guard(r, t, raise_=0.05)
        r.weapon_to("main", chest_point(r, (-0.26, -0.26, -0.22)), Vector((0.0, -0.6, 0.8)), Vector((-0.3, -1.0, -0.2)))
    walk_like(r, "Run", 3.4, 0.72, 0.36, 0.17, run_arms, bob_amp=0.035, lean=11)

    def slash(r, t, cycles=1, backhand=False):
        local = (t * cycles) % 1.0
        windup = smooth(local / 0.38)
        strike = smooth((local - 0.38) / 0.12) if local > 0.38 else 0.0
        recover = smooth((local - 0.62) / 0.38) if local > 0.62 else 0.0
        drive = strike * (1 - recover)
        r.body(bob=-0.04 - 0.03 * drive, lean=4 + 10 * drive, spine_twist=-25 * windup * (1 - strike) + 18 * drive,
               pelvis_yaw=-6 * windup * (1 - strike) + 8 * drive, head_pitch=-5 * drive)
        r.foot("L", Vector((0.14, -0.1 - 0.2 * drive, r.ankle_height)), 0, -10)
        r.foot("R", Vector((-0.15, 0.14 + 0.05 * drive, r.ankle_height)), 0, 14)
        shield_arm(r, raise_=0.08 * windup * (1 - recover))
        high = chest_point(r, (-0.26, 0.02, 0.5))
        low = chest_point(r, (0.12, -0.5, -0.12))
        rest_pos = chest_point(r, (-0.27, -0.2, -0.36))
        pos = rest_pos.lerp(high, windup * (1 - strike)).lerp(low, drive).lerp(rest_pos, recover)
        up_back = Vector((0.15, 0.6, 0.78))
        down_front = Vector((0.6, -0.6, -0.5))
        rest_dir = Vector((0.1, -0.55, -0.83))
        z_dir = rest_dir.lerp(up_back, windup * (1 - strike)).lerp(down_front, drive).lerp(rest_dir, recover)
        knuckles = Vector((-0.2, -1.0, 0.3)).lerp(Vector((0.0, 0.0, 1.0)), windup * (1 - recover))
        r.weapon_to("main", pos, z_dir, knuckles)
    hold(r, "Attack", 30, lambda r, t: slash(r, t), loop=False)
    hold(r, info["drill"], 60, lambda r, t: slash(r, t, 2), loop=True)

    def block(r, t):
        b = breathe(t, 0.5)
        r.body(bob=-0.06, crouch=0.02, lean=8, head_pitch=-4 + b)
        r.foot("L", Vector((0.15, -0.16, r.ankle_height)), 0, -10)
        r.foot("R", Vector((-0.16, 0.16, r.ankle_height)), 0, 14)
        shield_arm(r, hand=(-0.08, -0.36, 0.12), forearm=(-1.0, -0.1, 0.12), palm=(0.0, 1.0, -0.1))
        r.weapon_to("main", chest_point(r, (-0.24, -0.2, 0.1)), Vector((0.05, -0.5, 0.86)), Vector((-0.3, -1.0, 0.0)))
    hold(r, "Shield_Block", 40, block)
    common_hit_death(r, idle_arms=lambda r, t: (guard(r, t), low_guard(r, t)))


# ----------------------------------------------------------------- longbow

def longbow(r, info):
    def bow_low(r, t, swing=0.0):
        origin = chest_point(r, (0.27, -0.12, -0.36))
        r.weapon_to("main", origin, Vector((0.05, -0.15 + swing, 1.0)), LEFT + FWD * 0.3)

    def right_relaxed(r, t, forward=0.0):
        r.hand_free("R", forward=forward)

    def idle(r, t):
        b = breathe(t)
        r.body(bob=-0.012 + 0.004 * b, lean=1, spine_bend=-0.8 * b, head_yaw=5 * math.sin(2 * math.pi * t))
        stance(r)
        bow_low(r, t)
        right_relaxed(r, t)
    hold(r, "Idle", 90, idle)

    def walk_arms(r, t):
        bow_low(r, t, 0.1 * math.sin(2 * math.pi * t))
        right_relaxed(r, t, 18 * math.sin(2 * math.pi * t))
    walk_like(r, "Walk", 1.35, 1.1, 0.6, 0.1, walk_arms, lean=3)

    def run_arms(r, t):
        bow_low(r, t, 0.25)
        right_relaxed(r, t, 30 * math.sin(2 * math.pi * t))
    walk_like(r, "Run", 3.4, 0.72, 0.36, 0.17, run_arms, bob_amp=0.035, lean=11)

    def draw(r, t, cycles=1):
        local = (t * cycles) % 1.0
        raise_ = smooth(local / 0.2)
        pull = smooth((local - 0.18) / 0.28) if local > 0.18 else 0.0
        loose = 1.0 if local > 0.49 else 0.0
        lower = smooth((local - 0.7) / 0.3) if local > 0.7 else 0.0
        aim = raise_ * (1 - lower)
        r.body(bob=-0.02, pelvis_yaw=38 * aim, spine_twist=-8 * aim, lean=2, head_yaw=-34 * aim, side_bend=-3 * aim)
        r.foot("L", Vector((0.12, -0.14, r.ankle_height)), 0, 30 * aim)
        r.foot("R", Vector((-0.16, 0.12, r.ankle_height)), 0, 40 * aim)
        low = chest_point(r, (0.27, -0.12, -0.36))
        extended = chest_point(r, (0.12, -0.62, 0.33))
        bow_pos = low.lerp(extended, aim)
        bow_dir = Vector((0.05, -0.15, 1.0)).lerp(Vector((0.08, 0.0, 1.0)), aim)
        r.weapon_to("main", bow_pos, bow_dir, (LEFT + FWD * 0.3).lerp(LEFT + UP * 0.1, aim), chest_dir(r, (1.0, 0.0, -0.4)))
        # Drawing hand: from the string at the bow to the anchor under the jaw, flick back on release.
        string = extended + chest_dir(r, (0.0, 0.08, 0.0))
        anchor = chest_point(r, (-0.04, -0.12, 0.4))
        release = anchor + chest_dir(r, (-0.08, 0.1, 0.02)) * 0.8
        hand = string.lerp(anchor, pull).lerp(release, loose * (1 - lower))
        if aim < 0.05:
            r.hand_free("R")
        else:
            m = hand_frame(r, "R", chest_dir(r, (0.15, -1.0, 0.1)), chest_dir(r, (0.4, 0.0, -1.0))).to_4x4()
            m.translation = hand
            r.arm_to("R", m, chest_dir(r, (-1.0, 0.3, -0.1)))
            r.fist("R", 0.55)
    hold(r, "Attack", 30, lambda r, t: draw(r, t), loop=False)
    hold(r, info["drill"], 60, lambda r, t: draw(r, t, 1), loop=True)
    common_hit_death(r, idle_arms=lambda r, t: (bow_low(r, t), right_relaxed(r, t)))


# ----------------------------------------------------------------- crossbow

def crossbow(r, info):
    fore = Vector((0.0, 0.34, 0.03))   # forestock point in the weapon frame (authored stock along +Y)

    def carry(r, t, aim=0.0, nose_down=0.0, lift=0.0):
        hip = chest_point(r, (-0.18, -0.24, -0.3 + lift))
        shoulder = chest_point(r, (-0.12, -0.06, 0.22))
        pos = hip.lerp(shoulder, aim)
        stock = Vector((0.35, -1.0, 0.35)).lerp(Vector((0.04, -1.0, 0.0)), aim).lerp(Vector((0.0, -0.3, -1.0)), nose_down)
        up = Vector((0.0, 0.0, 1.0)).lerp(Vector((0.0, -1.0, 0.3)), nose_down)
        r.weapon_to("main", pos, up, -stock)
        side, offset = r.weapon_offsets["main"]
        frame = r.sk.pose("wrist.R") @ offset
        point = frame @ fore
        m = hand_frame(r, "L", (frame.to_3x3() @ Vector((0, 1, 0))).normalized(), (frame.to_3x3() @ Vector((0, 0, 1))).normalized()).to_4x4()
        m.translation = point - (frame.to_3x3() @ Vector((0, 0, 1))) * 0.045
        r.arm_to("L", m, chest_dir(r, (0.8, 0.3, -0.6)))
        r.fist("L", 0.8)

    def idle(r, t):
        b = breathe(t)
        r.body(bob=-0.012 + 0.004 * b, lean=2, spine_bend=-0.8 * b, head_yaw=4 * math.sin(2 * math.pi * t))
        stance(r)
        carry(r, t)
    hold(r, "Idle", 90, idle)
    walk_like(r, "Walk", 1.35, 1.1, 0.6, 0.1, lambda r, t: carry(r, t, lift=0.02 * math.sin(4 * math.pi * t)), lean=3)
    walk_like(r, "Run", 3.4, 0.72, 0.36, 0.17, lambda r, t: carry(r, t, lift=0.06), bob_amp=0.035, lean=11)

    def shoot(r, t):
        aim = smooth(t / 0.3) * (1 - smooth((t - 0.75) / 0.25))
        kick = math.exp(-((t - 0.52) / 0.05) ** 2) if t > 0.49 else 0.0
        r.body(bob=-0.03, pelvis_yaw=20 * aim, spine_twist=-12 * aim, lean=3 - 6 * kick, head_pitch=-6 * aim, head_yaw=-14 * aim)
        r.foot("L", Vector((0.13, -0.14, r.ankle_height)), 0, 15 * aim)
        r.foot("R", Vector((-0.16, 0.12, r.ankle_height)), 0, 25 * aim)
        carry(r, t, aim=aim, lift=0.03 * kick)
    hold(r, "Attack", 30, shoot, loop=False)

    def reload(r, t):
        down = smooth(t / 0.25) * (1 - smooth((t - 0.75) / 0.25))
        pull = smooth((t - 0.25) / 0.4) if t > 0.25 else 0.0
        r.body(bob=-0.03 - 0.12 * down, crouch=0.05 * down, lean=4 + 30 * down, head_pitch=-20 * down)
        r.foot("L", Vector((0.14, -0.06, r.ankle_height)), 0, -8)
        r.foot("R", Vector((-0.14, -0.28 * down + 0.06, r.ankle_height + 0.02 * down)), 0, 10)
        carry(r, t, nose_down=down, lift=-0.1 * down + 0.25 * pull * down)
    hold(r, info["drill"], 60, reload, loop=True)
    common_hit_death(r, idle_arms=lambda r, t: carry(r, t))


# ----------------------------------------------------------------- javelin + round shield

def javelin(r, info):
    def guard(r, t, raise_=0.0):
        shield_arm(r, hand=(-0.02, -0.3, -0.06), raise_=raise_)

    def upright(r, t, lift=0.0, sway=0.0):
        r.weapon_to("main", chest_point(r, (-0.27, -0.16, -0.24 + lift)), Vector((sway, -0.1, 1.0)), FWD + LEFT * 0.25)

    def idle(r, t):
        b = breathe(t)
        r.body(bob=-0.012 + 0.004 * b, lean=2, spine_bend=-0.8 * b, head_yaw=4 * math.sin(2 * math.pi * t))
        stance(r)
        guard(r, t)
        upright(r, t)
    hold(r, "Idle", 90, idle)
    walk_like(r, "Walk", 1.35, 1.1, 0.6, 0.1, lambda r, t: (guard(r, t), upright(r, t, 0.02 * math.sin(4 * math.pi * t), 0.04 * math.sin(2 * math.pi * t))), lean=3)
    walk_like(r, "Run", 3.4, 0.72, 0.36, 0.17, lambda r, t: (guard(r, t, 0.05), r.weapon_to("main", chest_point(r, (-0.22, -0.2, -0.1)), Vector((0.0, -1.0, 0.45)), UP)), bob_amp=0.035, lean=11)

    def throw(r, t, cycles=1):
        local = (t * cycles) % 1.0
        windup = smooth(local / 0.36)
        cast = smooth((local - 0.36) / 0.13) if local > 0.36 else 0.0
        recover = smooth((local - 0.62) / 0.38) if local > 0.62 else 0.0
        drive = cast * (1 - recover)
        back = windup * (1 - cast)
        r.body(bob=-0.03, pelvis_yaw=-24 * back + 14 * drive, spine_twist=-30 * back + 26 * drive, lean=-6 * back + 14 * drive,
               side_bend=6 * back, head_yaw=10 * back)
        r.foot("L", Vector((0.14, -0.12 - 0.12 * drive, r.ankle_height)), 0, -10)
        r.foot("R", Vector((-0.16, 0.16, r.ankle_height)), 0, 30 * back)
        guard(r, t, raise_=0.12 * back)
        rest_pos = chest_point(r, (-0.27, -0.16, -0.24))
        cocked = chest_point(r, (-0.3, 0.32, 0.42))
        released = chest_point(r, (-0.1, -0.62, 0.3))
        pos = rest_pos.lerp(cocked, back).lerp(released, drive).lerp(rest_pos, recover)
        z_dir = Vector((0.0, -0.1, 1.0)).lerp(Vector((0.0, -1.0, 0.3)), windup * (1 - recover))
        r.weapon_to("main", pos, z_dir, FWD.lerp(UP, windup * (1 - recover)) + LEFT * 0.2)
    hold(r, "Attack", 30, lambda r, t: throw(r, t), loop=False)
    hold(r, info["drill"], 60, lambda r, t: throw(r, t, 1), loop=True)
    common_hit_death(r, idle_arms=lambda r, t: (guard(r, t), upright(r, t)))


STYLES = {"spear_shield": spear_shield, "sword_shield": sword_shield, "longbow": longbow,
          "crossbow": crossbow, "javelin": javelin}
