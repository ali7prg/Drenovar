"""Shared adult skeleton `human_shared` for all «Лес потерянных» humans (civilians + squad).

Bone names follow Godot's SkeletonProfileHumanoid (Root, Hips, Spine, Chest, UpperChest, Neck,
Head, Jaw, LeftShoulder, LeftUpperArm, LeftLowerArm, LeftHand, LeftThumbMetacarpal, ...,
LeftUpperLeg, LeftLowerLeg, LeftFoot, LeftToes) so Godot's BoneMap/retargeter maps them with no
manual work; the existing DRENOVAR army rigs use the same vocabulary (Hips/Spine/Chest/...).
Simplified fingers: thumb (2), index (2), "middle" (2, also drives ring + little finger).
Secondary bones: skirt/apron/tabard/dress (front 2, back 2, left, right), cape/cloak (2),
hood (1), bag/satchel (1) and two prop sockets (LeftProp/RightProp, children of the hands,
deforming so weapons/shields are skinned meshes).  48 deform bones, no twist bones.

Every character uses identical bone names, hierarchy and *canonical rest directions*; only the
joint positions (bone lengths, shoulder/hip widths) differ per character.  The mesh is modelled
in the reference sheet's drawing pose, bound there, and then re-rested onto the canonical
directions (`canonical_pose`) so local rotations are interchangeable between characters.

World: Blender Z up, metres, character faces -Y, left side = +X.
"""
import math

import numpy as np

SIDES = (("Left", 1.0), ("Right", -1.0))

# (name, parent, z_axis_hint) ; z_axis_hint chooses the bone roll (local Z ~ hint)
FWD = (0.0, -1.0, 0.0)
UP = (0.0, 0.0, 1.0)
BACK = (0.0, 1.0, 0.0)


def bone_table():
    t = [("Root", None, FWD), ("Hips", "Root", FWD), ("Spine", "Hips", FWD), ("Chest", "Spine", FWD),
         ("UpperChest", "Chest", FWD), ("Neck", "UpperChest", FWD), ("Head", "Neck", FWD),
         ("Jaw", "Head", UP)]
    for S, _s in SIDES:
        t += [(f"{S}Shoulder", "UpperChest", FWD), (f"{S}UpperArm", f"{S}Shoulder", FWD),
              (f"{S}LowerArm", f"{S}UpperArm", FWD), (f"{S}Hand", f"{S}LowerArm", "palm"),
              (f"{S}ThumbMetacarpal", f"{S}Hand", "palm"), (f"{S}ThumbProximal", f"{S}ThumbMetacarpal", "palm"),
              (f"{S}IndexProximal", f"{S}Hand", "palm"), (f"{S}IndexIntermediate", f"{S}IndexProximal", "palm"),
              (f"{S}MiddleProximal", f"{S}Hand", "palm"), (f"{S}MiddleIntermediate", f"{S}MiddleProximal", "palm"),
              (f"{S}Prop", f"{S}Hand", "palm")]
    for S, _s in SIDES:
        t += [(f"{S}UpperLeg", "Hips", FWD), (f"{S}LowerLeg", f"{S}UpperLeg", FWD),
              (f"{S}Foot", f"{S}LowerLeg", UP), (f"{S}Toes", f"{S}Foot", UP)]
    t += [("SkirtFront1", "Hips", FWD), ("SkirtFront2", "SkirtFront1", FWD),
          ("SkirtBack1", "Hips", BACK), ("SkirtBack2", "SkirtBack1", BACK),
          ("SkirtLeft", "Hips", (1.0, 0.0, 0.0)), ("SkirtRight", "Hips", (-1.0, 0.0, 0.0)),
          ("Cape1", "UpperChest", BACK), ("Cape2", "Cape1", BACK),
          ("Hood", "Neck", BACK), ("Bag", "Hips", FWD)]
    return t


BONES = [b[0] for b in bone_table()]
PARENT = {b[0]: b[1] for b in bone_table()}
HUMANOID = [b for b in BONES if not (b.startswith("Skirt") or b.startswith("Cape") or b in ("Hood", "Bag")
                                      or b.endswith("Prop"))]
SECONDARY = [b for b in BONES if b not in HUMANOID]

# Animation-LOD bone sets (mesh influences are folded into the nearest kept ancestor)
LOD1_KEEP = ["Root", "Hips", "Spine", "Chest", "UpperChest", "Neck", "Head",
             "LeftShoulder", "LeftUpperArm", "LeftLowerArm", "LeftHand", "LeftMiddleProximal",
             "RightShoulder", "RightUpperArm", "RightLowerArm", "RightHand", "RightMiddleProximal",
             "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "LeftToes",
             "RightUpperLeg", "RightLowerLeg", "RightFoot", "RightToes",
             "SkirtFront1", "SkirtBack1", "Cape1", "LeftProp", "RightProp"]      # 29 weighted (<=30)
LOD2_KEEP = ["Root", "Hips", "Spine", "Chest", "UpperChest", "Neck", "Head",
             "LeftUpperArm", "LeftLowerArm", "LeftHand", "RightUpperArm", "RightLowerArm", "RightHand",
             "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "RightUpperLeg", "RightLowerLeg", "RightFoot"]  # 18 weighted


def v3(*a):
    return np.array(a, dtype=float)


def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def rotate(v, axis, deg):
    """Rodrigues rotation of v about axis (degrees)."""
    axis = unit(axis)
    th = math.radians(deg)
    v = np.asarray(v, float)
    return (v * math.cos(th) + np.cross(axis, v) * math.sin(th)
            + axis * np.dot(axis, v) * (1 - math.cos(th)))


# --------------------------------------------------------------------------- hand layout

def palm_thumb(side, medial=0.55):
    """Default thumb direction of a relaxed hanging hand: forward and toward the midline."""
    return unit(np.array([-side * medial, -0.83, 0.0]))


def hand_frame(wrist, knuckle, side, thumb_fwd=None):
    if thumb_fwd is None:
        thumb_fwd = palm_thumb(side)
    """(d, t, n): d = wrist->middle knuckle, t = thumb side, n = palm normal (out of palm)."""
    d = unit(np.asarray(knuckle) - np.asarray(wrist))
    t = np.asarray(thumb_fwd, float)
    t = unit(t - np.dot(t, d) * d)
    n = unit(side * np.cross(d, t))
    return d, t, n


def finger_points(wrist, knuckle, side, scale=1.0, curl=(18.0, 22.0, 16.0), spread=4.0,
                  thumb_curl=12.0, thumb_fwd=None):
    """Joint chains for 5 fingers in the relaxed drawing pose: {name: [p0..p3]} + radii."""
    if thumb_fwd is None:
        thumb_fwd = palm_thumb(side)
    d, t, n = hand_frame(wrist, knuckle, side, thumb_fwd)
    w = np.asarray(wrist, float)
    s = scale
    spec = {  # knuckle offset (along d, along t), segment lengths, radius
        "index": (0.090, 0.026, (0.041, 0.025, 0.020), 0.0088, +spread),
        "middle": (0.095, 0.008, (0.045, 0.028, 0.021), 0.0090, +spread * 0.25),
        "ring": (0.090, -0.010, (0.043, 0.026, 0.020), 0.0085, -spread * 0.4),
        "little": (0.080, -0.026, (0.034, 0.020, 0.018), 0.0075, -spread),
    }
    out = {}
    for name, (od, ot, segs, rad, spr) in spec.items():
        p = w + (od * d + ot * t) * s
        dirv = rotate(d, n, spr * side)
        pts = [p]
        axis = unit(np.cross(dirv, n))  # flexion axis: rotates dir toward +n (palm side)
        for k, L in enumerate(segs):
            dirv = rotate(dirv, axis, curl[k])
            p = p + dirv * L * s
            pts.append(p)
        out[name] = (pts, rad * s)
    # thumb: CMC on the palmar/radial side, pointing toward t and forward
    cmc = w + (0.022 * d + 0.020 * t + 0.010 * n) * s
    tdir = unit(0.78 * d + 0.50 * t + 0.38 * n)
    pts = [cmc]
    p = cmc
    for k, L in enumerate((0.044, 0.031, 0.026)):
        if k:
            tdir = rotate(tdir, unit(np.cross(tdir, n)), thumb_curl)
        p = p + tdir * L * s
        pts.append(p)
    out["thumb"] = (pts, 0.0105 * s)
    return out


# --------------------------------------------------------------------------- joints from landmarks

def joints_from_landmarks(L):
    """Landmarks (metres, drawing pose, from the world-grid reading of the front panel):

    crown, eye, mouth, chin, neck (z) ; shoulder_l/r, elbow_l/r, wrist_l/r, hip_l/r, knee_l/r,
    ankle_l/r : (x, z) ; optional depth overrides *_y ; 'female' bool ; 'hand_len'.
    Returns dict of joint name -> np.array(3) (bone heads/tails).
    """
    S = L["crown"]
    k = S / 1.75
    J = {}
    J["Root"] = v3(0, 0, 0)
    J["Root_end"] = v3(0, 0, 0.12 * k)
    hipz = 0.5 * (L["hip_l"][1] + L["hip_r"][1])
    J["Hips"] = v3(0, L.get("hips_y", 0.012), hipz + 0.035 * k)
    neck = L["neck"]
    span = neck - J["Hips"][2]
    J["Spine"] = v3(0, L.get("spine_y", 0.018), J["Hips"][2] + 0.14 * span)
    J["Chest"] = v3(0, L.get("chest_y", 0.022), J["Hips"][2] + 0.42 * span)
    J["UpperChest"] = v3(0, L.get("upperchest_y", 0.020), J["Hips"][2] + 0.70 * span)
    J["Neck"] = v3(0, L.get("neck_y", 0.024), neck)
    J["Head"] = v3(0, L.get("head_y", 0.030), L["mouth"] + 0.012 * k)
    J["Head_end"] = v3(0, L.get("head_y", 0.030), S)
    J["Jaw"] = v3(0, 0.006 * k, 0.5 * (L["eye"] + L["mouth"]) - 0.004 * k)
    J["Jaw_end"] = v3(0, -0.075 * k, L["chin"] + 0.014 * k)
    for S_, s in SIDES:
        c = S_[0].lower()
        sh = L[f"shoulder_{c}"]
        el = L[f"elbow_{c}"]
        wr = L[f"wrist_{c}"]
        J[f"{S_}Shoulder"] = v3(s * 0.022 * k, L.get("clav_y", 0.0), neck - 0.030 * k)
        J[f"{S_}UpperArm"] = v3(sh[0], L.get("shoulder_y", 0.012), sh[1])
        J[f"{S_}LowerArm"] = v3(el[0], L.get("elbow_y", 0.030), el[1])
        J[f"{S_}Hand"] = v3(wr[0], L.get("wrist_y", -0.005), wr[1])
        fdir = unit(J[f"{S_}Hand"] - J[f"{S_}LowerArm"])
        # hand continues the forearm, slightly toward the thigh
        hdir = unit(fdir + v3(-s * 0.10, -0.05, 0.0))
        J[f"{S_}Hand_end"] = J[f"{S_}Hand"] + hdir * L.get("hand_len", 0.092) * k
        hp = L[f"hip_{c}"]
        kn = L[f"knee_{c}"]
        an = L[f"ankle_{c}"]
        J[f"{S_}UpperLeg"] = v3(hp[0], L.get("hipjoint_y", 0.008), hp[1])
        J[f"{S_}LowerLeg"] = v3(kn[0], L.get("knee_y", -0.012), kn[1])
        J[f"{S_}Foot"] = v3(an[0], L.get("ankle_y", 0.022), an[1])
        toe_out = math.radians(L.get("toe_out_deg", 7.0))
        fwd = v3(s * math.sin(toe_out), -math.cos(toe_out), 0.0)
        flen = L.get("foot_len", 0.255) * k
        ball = J[f"{S_}Foot"] + fwd * (0.555 * flen) + v3(0, 0, 0)
        ball[2] = 0.022 * k
        J[f"{S_}Toes"] = ball
        tip = J[f"{S_}Foot"] + fwd * (0.80 * flen)
        tip[2] = 0.018 * k
        J[f"{S_}Toes_end"] = tip
        J[f"{S_}Heel"] = J[f"{S_}Foot"] - fwd * (0.20 * flen) + v3(0, 0, -an[1] + 0.012 * k)
    return J


def build_bones(J, L, garments=None):
    """Bone dicts (name, head, tail, parent, z_hint) for frlib-style armature creation."""
    k = L["crown"] / 1.75
    garments = garments or {}
    B = {}

    def put(name, head, tail):
        B[name] = (np.asarray(head, float), np.asarray(tail, float))

    put("Root", J["Root"], J["Root_end"])
    put("Hips", J["Hips"], J["Spine"])
    put("Spine", J["Spine"], J["Chest"])
    put("Chest", J["Chest"], J["UpperChest"])
    put("UpperChest", J["UpperChest"], J["Neck"])
    put("Neck", J["Neck"], J["Head"])
    put("Head", J["Head"], J["Head_end"])
    put("Jaw", J["Jaw"], J["Jaw_end"])
    fingers = {}
    for S_, s in SIDES:
        put(f"{S_}Shoulder", J[f"{S_}Shoulder"], J[f"{S_}UpperArm"])
        put(f"{S_}UpperArm", J[f"{S_}UpperArm"], J[f"{S_}LowerArm"])
        put(f"{S_}LowerArm", J[f"{S_}LowerArm"], J[f"{S_}Hand"])
        put(f"{S_}Hand", J[f"{S_}Hand"], J[f"{S_}Hand_end"])
        fp = finger_points(J[f"{S_}Hand"], J[f"{S_}Hand_end"], s, scale=L.get("hand_scale", 1.0) * k,
                           curl=L.get("finger_curl", (16.0, 20.0, 14.0)))
        fingers[S_] = fp
        th = fp["thumb"][0]
        put(f"{S_}ThumbMetacarpal", th[0], th[1])
        put(f"{S_}ThumbProximal", th[1], th[3])
        ix = fp["index"][0]
        put(f"{S_}IndexProximal", ix[0], ix[1])
        put(f"{S_}IndexIntermediate", ix[1], ix[3])
        md = fp["middle"][0]
        put(f"{S_}MiddleProximal", md[0], md[1])
        put(f"{S_}MiddleIntermediate", md[1], md[3])
        # prop socket: grip centre in the curled palm, pointing along the fist's grip axis
        d, t, n = hand_frame(J[f"{S_}Hand"], J[f"{S_}Hand_end"], s)
        grip = J[f"{S_}Hand"] + d * 0.072 * k + n * 0.028 * k
        put(f"{S_}Prop", grip, grip + t * 0.10 * k)
        put(f"{S_}UpperLeg", J[f"{S_}UpperLeg"], J[f"{S_}LowerLeg"])
        put(f"{S_}LowerLeg", J[f"{S_}LowerLeg"], J[f"{S_}Foot"])
        put(f"{S_}Foot", J[f"{S_}Foot"], J[f"{S_}Toes"])
        put(f"{S_}Toes", J[f"{S_}Toes"], J[f"{S_}Toes_end"])
    # secondary cloth bones (positions depend on garment extents; defaults are generic)
    hz = J["Hips"][2]
    wz = garments.get("waist_z", hz + 0.06 * k)
    hem = garments.get("skirt_hem_z", 0.45 * k)
    fy = garments.get("front_y", -0.14 * k)
    by = garments.get("back_y", 0.14 * k)
    mid = 0.5 * (wz + hem)
    put("SkirtFront1", (0, fy, wz), (0, fy - 0.02 * k, mid))
    put("SkirtFront2", (0, fy - 0.02 * k, mid), (0, fy - 0.035 * k, hem))
    put("SkirtBack1", (0, by, wz), (0, by + 0.02 * k, mid))
    put("SkirtBack2", (0, by + 0.02 * k, mid), (0, by + 0.035 * k, hem))
    sx = garments.get("side_x", 0.17 * k)
    put("SkirtLeft", (sx, 0.0, wz), (sx + 0.03 * k, 0.0, hem))
    put("SkirtRight", (-sx, 0.0, wz), (-sx - 0.03 * k, 0.0, hem))
    cz0 = garments.get("cape_top_z", J["Neck"][2] - 0.02 * k)
    cz1 = garments.get("cape_hem_z", J["Hips"][2])
    cy = garments.get("cape_y", 0.13 * k)
    cmid = cz0 + 0.45 * (cz1 - cz0)
    put("Cape1", (0, cy, cz0), (0, cy + 0.03 * k, cmid))
    put("Cape2", (0, cy + 0.03 * k, cmid), (0, cy + 0.05 * k, cz1))
    hz0 = J["Neck"][2] + 0.02 * k
    put("Hood", (0, 0.07 * k, hz0), (0, 0.11 * k, hz0 + 0.14 * k))
    bag = garments.get("bag", ((0.17 * k, -0.02 * k, wz - 0.02 * k), (0.18 * k, -0.03 * k, wz - 0.20 * k)))
    put("Bag", bag[0], bag[1])
    return B, fingers


def z_hint(name, B, fingers_frames=None):
    for n, _p, h in bone_table():
        if n == name:
            return h
    return FWD


def create_armature(name, B, J, col=None):
    """Blender armature from bone dict; rolls from per-bone hints (palm bones use the palm normal)."""
    import bpy
    from mathutils import Vector
    from frlib import core
    arm = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, arm)
    core.link(obj, col)
    arm.display_type = "OCTAHEDRAL"
    core.select_only([obj])
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = {}
    for bname, parent, hint in bone_table():
        h, t = B[bname]
        eb = arm.edit_bones.new(bname)
        eb.head = Vector(h)
        eb.tail = Vector(t)
        if hint == "palm":
            side = 1.0 if bname.startswith("Left") else -1.0
            S_ = "Left" if side > 0 else "Right"
            _d, _t, n = hand_frame(J[f"{S_}Hand"], J[f"{S_}Hand_end"], side)
            eb.align_roll(Vector(n))
        else:
            eb.align_roll(Vector(hint))
        eb.use_deform = True
        ebs[bname] = eb
    for bname, parent, _h in bone_table():
        if parent:
            ebs[bname].parent = ebs[parent]
            ebs[bname].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in obj.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return obj


# --------------------------------------------------------------------------- canonical rest

CANON = {
    # unit directions (left side; right side mirrors X) for the shared rest pose
    "UpperArm": unit(v3(0.30, 0.04, -1.0)),     # ~17 deg abduction, slightly back
    "LowerArm": unit(v3(0.17, -0.20, -1.0)),    # elbow slightly flexed, forearm forward
    "Hand": unit(v3(0.05, -0.16, -1.0)),
    "UpperLeg": unit(v3(0.055, -0.02, -1.0)),
    "LowerLeg": unit(v3(0.025, 0.035, -1.0)),
}


def canonical_rotations(B):
    """Quaternions (armature space, as world-rotation deltas) moving each limb bone from the
    drawing pose onto the canonical rest directions; applied root-to-tip by the caller."""
    out = {}
    for S_, s in SIDES:
        for part, dirv in CANON.items():
            name = f"{S_}{part}"
            h, t = B[name]
            cur = unit(t - h)
            want = dirv.copy()
            want[0] *= s
            out[name] = (cur, unit(want))
    return out
