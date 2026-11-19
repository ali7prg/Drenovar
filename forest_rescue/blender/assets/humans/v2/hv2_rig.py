"""Shared `human_shared` skeleton for all 9 v2 humans: identical bone names / hierarchy / roll
conventions, joint positions from each painting.  50 deform bones (civilian <= 50, soldier <= 52):

  Hips Spine Chest UpperChest Neck Head                                     6
  {Left,Right}{Shoulder,UpperArm,LowerArm,Hand,Thumb1,Thumb2,Index1,Index2,
              Middle1,Middle2,Ring1,Pinky1}                                24
  {Left,Right}{UpperLeg,LowerLeg,Foot,Toes}                                 8
  SkirtFront1/2 SkirtBack1/2 SkirtLeft SkirtRight (aprons, skirts, hems)    6
  Cloak1 Cloak2 (capes/cloaks/tabard back)  Hood  Bag (satchel/pouch)       4
  PropR PropL (weapons/shield; scale 0 = hidden)                            2
Non-deform: Root (parent of Hips) + IK controls IK_Foot_*, IK_Hand_*, Pole_Knee_*, Pole_Elbow_*.
"""
import math

import numpy as np

SIDES = (("Left", "l", 1.0), ("Right", "r", -1.0))
FINGERS = ["Thumb1", "Thumb2", "Index1", "Index2", "Middle1", "Middle2", "Ring1", "Pinky1"]
SECONDARY = ["SkirtFront1", "SkirtFront2", "SkirtBack1", "SkirtBack2", "SkirtLeft", "SkirtRight",
             "Cloak1", "Cloak2", "Hood", "Bag", "PropR", "PropL"]

LOD1_KEEP = (["Hips", "Spine", "Chest", "UpperChest", "Neck", "Head"]
             + [f"{S}{b}" for S in ("Left", "Right") for b in ("Shoulder", "UpperArm", "LowerArm", "Hand",
                                                               "UpperLeg", "LowerLeg", "Foot")]
             + ["SkirtFront1", "SkirtBack1", "Cloak1", "Bag", "PropR", "PropL"])            # 26
LOD2_KEEP = (["Hips", "Spine", "Chest", "Neck", "Head"]
             + [f"{S}{b}" for S in ("Left", "Right") for b in ("UpperArm", "LowerArm", "Hand", "UpperLeg",
                                                               "LowerLeg", "Foot")] + ["PropR"])   # 18


def parent_of(name):
    P = {"Hips": "Root", "Spine": "Hips", "Chest": "Spine", "UpperChest": "Chest", "Neck": "UpperChest",
         "Head": "Neck", "SkirtFront1": "Hips", "SkirtFront2": "SkirtFront1", "SkirtBack1": "Hips",
         "SkirtBack2": "SkirtBack1", "SkirtLeft": "Hips", "SkirtRight": "Hips", "Cloak1": "UpperChest",
         "Cloak2": "Cloak1", "Hood": "Neck", "Bag": "Hips", "PropR": "RightHand", "PropL": "LeftHand"}
    if name in P:
        return P[name]
    for S, _, _ in SIDES:
        if name.startswith(S):
            b = name[len(S):]
            return {"Shoulder": "UpperChest", "UpperArm": f"{S}Shoulder", "LowerArm": f"{S}UpperArm",
                    "Hand": f"{S}LowerArm", "Thumb1": f"{S}Hand", "Thumb2": f"{S}Thumb1",
                    "Index1": f"{S}Hand", "Index2": f"{S}Index1", "Middle1": f"{S}Hand",
                    "Middle2": f"{S}Middle1", "Ring1": f"{S}Hand", "Pinky1": f"{S}Hand",
                    "UpperLeg": "Hips", "LowerLeg": f"{S}UpperLeg", "Foot": f"{S}LowerLeg",
                    "Toes": f"{S}Foot"}[b]
    raise KeyError(name)


def deform_names():
    out = ["Hips", "Spine", "Chest", "UpperChest", "Neck", "Head"]
    for S, _, _ in SIDES:
        out += [f"{S}{b}" for b in ("Shoulder", "UpperArm", "LowerArm", "Hand")] + [f"{S}{f}" for f in FINGERS]
    for S, _, _ in SIDES:
        out += [f"{S}{b}" for b in ("UpperLeg", "LowerLeg", "Foot", "Toes")]
    return out + SECONDARY


def bone_specs(J, hand_bones, T, garment_info):
    """List of dicts {name, head, tail, parent, roll_z (desired local Z axis), deform}."""
    B = []

    def add(name, head, tail, zref, deform=True, parent="auto"):
        B.append(dict(name=name, head=np.asarray(head, float), tail=np.asarray(tail, float),
                      parent=parent_of(name) if parent == "auto" else parent, zref=np.asarray(zref, float),
                      deform=deform))
    fwd = np.array([0, -1.0, 0])
    add("Root", (0, 0, 0), (0, 0.25, 0), (0, 0, 1.0), deform=False, parent=None)
    add("Hips", J["Hips"], J["Spine"], fwd)
    add("Spine", J["Spine"], J["Chest"], fwd)
    add("Chest", J["Chest"], J["UpperChest"], fwd)
    add("UpperChest", J["UpperChest"], J["Neck"], fwd)
    add("Neck", J["Neck"], J["Head"], fwd)
    add("Head", J["Head"], J["HeadTop"], fwd)
    for S, s, sx in SIDES:
        add(f"{S}Shoulder", J[f"{S}Shoulder"], J[f"{S}UpperArm"], fwd)
        add(f"{S}UpperArm", J[f"{S}UpperArm"], J[f"{S}LowerArm"], fwd)
        add(f"{S}LowerArm", J[f"{S}LowerArm"], J[f"{S}Hand"], fwd)
        hb = hand_bones[S]
        d, t, n = hb["_frame"]
        add(f"{S}Hand", hb[f"{S}Hand"][0], hb[f"{S}Hand"][1], -n)
        for f in FINGERS:
            h, tl = hb[f"{S}{f}"]
            add(f"{S}{f}", h, tl, -n)
        add(f"{S}UpperLeg", J[f"{S}UpperLeg"], J[f"{S}LowerLeg"], fwd)
        add(f"{S}LowerLeg", J[f"{S}LowerLeg"], J[f"{S}Foot"], fwd)
        add(f"{S}Foot", J[f"{S}Foot"], J[f"{S}Toes"], (0, 0, 1.0))
        add(f"{S}Toes", J[f"{S}Toes"], J[f"{S}ToeTip"], (0, 0, 1.0))
    hz = J["Hips"][2]
    kz = 0.5 * (J["LeftLowerLeg"][2] + J["RightLowerLeg"][2])
    zt = garment_info.get("skirt_top", hz + 0.08)
    zh = garment_info.get("skirt_hem", kz)
    zm = 0.5 * (zt + zh)

    def at(phi, z, extra=0.02):
        r = float(T.hull(np.array([z]), np.array([phi]))[0]) + extra
        return np.array([T.cx + r * math.sin(phi), T.cy - r * math.cos(phi), z])
    add("SkirtFront1", at(0, zt), at(0, zm), (0, -1.0, 0))
    add("SkirtFront2", at(0, zm), at(0, zh), (0, -1.0, 0))
    add("SkirtBack1", at(math.pi, zt), at(math.pi, zm), (0, 1.0, 0))
    add("SkirtBack2", at(math.pi, zm), at(math.pi, zh), (0, 1.0, 0))
    add("SkirtLeft", at(math.pi / 2, zt), at(math.pi / 2, zh), (1.0, 0, 0))
    add("SkirtRight", at(-math.pi / 2, zt), at(-math.pi / 2, zh), (-1.0, 0, 0))
    uz = J["UpperChest"][2]
    cz = garment_info.get("cloak_hem", hz - 0.10)
    add("Cloak1", at(math.pi, uz + 0.05, 0.03), at(math.pi, 0.5 * (uz + cz), 0.05), (0, 1.0, 0))
    add("Cloak2", at(math.pi, 0.5 * (uz + cz), 0.05), at(math.pi, cz, 0.07), (0, 1.0, 0))
    add("Hood", J["Neck"] + np.array([0, 0.07, 0.03]), J["HeadTop"] + np.array([0, 0.10, -0.04]), (0, 1.0, 0))
    bag = np.asarray(garment_info.get("bag", (-0.12, -0.14, hz - 0.02)), float)
    add("Bag", bag + np.array([0, 0, 0.10]), bag - np.array([0, 0, 0.05]), (0, -1.0, 0))
    for S, P in (("Right", "PropR"), ("Left", "PropL")):
        hb = hand_bones[S]
        g = hb["_grip"]
        d, t, n = hb["_frame"]
        add(P, g, g + d * 0.10, -n)
    return B


def build_armature(name, specs):
    import bpy
    from mathutils import Vector
    from frlib import core
    arm = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, arm)
    core.link(obj)
    arm.display_type = "OCTAHEDRAL"
    core.select_only([obj])
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = {}
    for b in specs:
        eb = arm.edit_bones.new(b["name"])
        eb.head = Vector(b["head"])
        eb.tail = Vector(b["tail"])
        eb.align_roll(Vector(b["zref"]))
        eb.use_deform = b["deform"]
        ebs[b["name"]] = eb
    for b in specs:
        if b["parent"]:
            ebs[b["name"]].parent = ebs[b["parent"]]
            ebs[b["name"]].use_connect = False
    # IK controls (non-deform)
    for S, s, sx in SIDES:
        foot = ebs[f"{S}Foot"]
        e = arm.edit_bones.new(f"IK_Foot_{s.upper()}")
        e.head = foot.head.copy()
        e.tail = foot.head + Vector((0, -0.12, 0))
        e.parent = ebs["Root"]
        e.use_deform = False
        hand = ebs[f"{S}Hand"]
        e = arm.edit_bones.new(f"IK_Hand_{s.upper()}")
        e.head = hand.head.copy()
        e.tail = hand.head + Vector((0, 0, -0.08))
        e.parent = ebs["Root"]
        e.use_deform = False
        kn = ebs[f"{S}LowerLeg"].head
        e = arm.edit_bones.new(f"Pole_Knee_{s.upper()}")
        e.head = kn + Vector((0, -0.45, 0))
        e.tail = e.head + Vector((0, -0.05, 0))
        e.parent = ebs["Root"]
        e.use_deform = False
        el = ebs[f"{S}LowerArm"].head
        e = arm.edit_bones.new(f"Pole_Elbow_{s.upper()}")
        e.head = el + Vector((0, 0.40, 0))
        e.tail = e.head + Vector((0, 0.05, 0))
        e.parent = ebs["Root"]
        e.use_deform = False
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in obj.pose.bones:
        pb.rotation_mode = "QUATERNION"
    # IK constraints for editing (muted: the exported clips are baked FK; the targets are keyed
    # to the solved positions so unmuting reproduces the same motion)
    for S, s, sx in SIDES:
        for chain, tgt, pole in ((f"{S}LowerLeg", f"IK_Foot_{s.upper()}", f"Pole_Knee_{s.upper()}"),
                                 (f"{S}LowerArm", f"IK_Hand_{s.upper()}", f"Pole_Elbow_{s.upper()}")):
            c = obj.pose.bones[chain].constraints.new("IK")
            c.target = obj
            c.subtarget = tgt
            c.pole_target = obj
            c.pole_subtarget = pole
            c.pole_angle = math.radians(-90)
            c.chain_count = 2
            c.mute = True
    return obj


# --------------------------------------------------------------------------- weights

def body_weights(verts, parts, J, falloff=0.022):
    """Per-vertex bone weights of the SDF body: limb/head parts by relative distance, the torso
    stack split along the spine by height, shoulders and hips blended."""
    names = []
    cols = []
    dists = []
    torso = None
    for p in parts:
        if p.name == "torso":
            torso = p
            continue
        if p.bone is None:
            continue
        lo, hi = p.lo - 0.08, p.hi + 0.08
        d = np.full(len(verts), 9.0)
        sel = np.all((verts >= lo) & (verts <= hi), axis=1)
        if sel.any():
            d[sel] = p.fn(verts[sel])
        dists.append(d)
        names.append(p.bone)
    dt = torso.fn(verts) if torso is not None else np.full(len(verts), 9.0)
    D = np.stack(dists, 1)
    dmin = np.minimum(D.min(1), dt)
    W = {}
    for j, n in enumerate(names):
        w = np.exp(-np.maximum(D[:, j] - dmin, 0) / falloff)
        W[n] = np.maximum(W.get(n, 0), w)
    wt = np.exp(-np.maximum(dt - dmin, 0) / falloff)
    # spine split by height
    sp = [("Hips", J["Hips"][2] - 0.05), ("Spine", J["Spine"][2] + 0.02), ("Chest", J["Chest"][2] + 0.03),
          ("UpperChest", J["UpperChest"][2] + 0.04), ("Neck", J["Neck"][2] + 0.03)]
    z = verts[:, 2]
    zs = np.array([v for _, v in sp])
    for i, (n, z0) in enumerate(sp):
        lo = zs[i - 1] if i > 0 else -9
        hi = zs[i + 1] if i + 1 < len(sp) else 9
        up = np.clip((z - lo) / max(z0 - lo, 1e-3), 0, 1) if i > 0 else np.ones_like(z)
        dn = np.clip((hi - z) / max(hi - z0, 1e-3), 0, 1) if i + 1 < len(sp) else np.ones_like(z)
        w = np.where(z < z0, up, dn) * wt
        W[n] = np.maximum(W.get(n, 0), w)
    # shoulder (clavicle) bone on the upper torso near each shoulder joint
    for S, s, sx in SIDES:
        c = J[f"{S}UpperArm"]
        dd = np.linalg.norm(verts - c, axis=1)
        w = np.clip(1 - dd / 0.13, 0, 1) * (verts[:, 0] * sx > 0.06) * wt
        W[f"{S}Shoulder"] = np.maximum(W.get(f"{S}Shoulder", 0), w * 0.9)
        # hip blend: torso bottom near the thigh joint follows the thigh partly
        h = J[f"{S}UpperLeg"]
        dd = np.linalg.norm((verts - h) * np.array([1, 1, 1.4]), axis=1)
        w = np.clip(1 - dd / 0.14, 0, 1) * (verts[:, 2] < h[2] + 0.04) * (verts[:, 0] * sx > -0.01)
        W[f"{S}UpperLeg"] = np.maximum(W.get(f"{S}UpperLeg", 0), w * 0.8)
    return W


def normalize_top4(Wd, n, min_w=0.015):
    names = sorted(Wd)
    M = np.stack([np.broadcast_to(np.asarray(Wd[k], float), (n,)) for k in names], 1)
    M[M < 1e-4] = 0
    if M.shape[1] > 4:
        cut = np.argsort(-M, axis=1)[:, 4:]
        np.put_along_axis(M, cut, 0.0, axis=1)
    M[M < min_w] = 0
    s = M.sum(1, keepdims=True)
    bad = s[:, 0] <= 0
    M[bad, names.index("Hips") if "Hips" in names else 0] = 1.0
    M /= M.sum(1, keepdims=True)
    return names, M


def smooth_weights(names, M, faces, iters=3, factor=0.5, lock=None):
    from frlib import sdf
    A = sdf.adjacency_matrix(M.shape[0], faces)
    for _ in range(iters):
        M2 = A @ M
        M = (1 - factor) * M + factor * M2
        if lock is not None:
            pass
    return M


def assign_groups(obj, names, M):
    obj.vertex_groups.clear()
    for j, n in enumerate(names):
        idx = np.nonzero(M[:, j] > 0)[0]
        if len(idx) == 0:
            continue
        g = obj.vertex_groups.new(name=n)
        vals = np.round(M[idx, j], 4)
        order = np.argsort(vals)
        idx, vals = idx[order], vals[order]
        splits = np.nonzero(np.diff(vals))[0] + 1
        for ii, vv in zip(np.split(idx, splits), np.split(vals, splits)):
            g.add(ii.tolist(), float(vv[0]), "REPLACE")


def groups_from_dicts(obj, dicts):
    n = len(obj.data.vertices)
    keys = sorted({k for d in dicts for k in d})
    M = np.zeros((n, len(keys)))
    for i, d in enumerate(dicts[:n]):
        for k, v in d.items():
            M[i, keys.index(k)] = v
    s = M.sum(1, keepdims=True)
    s[s == 0] = 1
    assign_groups(obj, keys, M / s)


def read_groups(obj):
    names = [g.name for g in obj.vertex_groups]
    M = np.zeros((len(obj.data.vertices), len(names)))
    for v in obj.data.vertices:
        for ge in v.groups:
            M[v.index, ge.group] = ge.weight
    return names, M


def remap(names, M, keep):
    """Fold dropped bones into their nearest kept ancestor; re-limit to 4 + normalise."""
    out = {}
    for j, n in enumerate(names):
        b = n
        while b not in keep and b not in ("Root",):
            b = parent_of(b)
        if b == "Root":
            b = "Hips"
        out[b] = out.get(b, 0) + M[:, j]
    return normalize_top4(out, M.shape[0])
