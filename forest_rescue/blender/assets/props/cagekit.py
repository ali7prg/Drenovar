"""Shared cage logic: door node on the hinge axis (left jamb seen from outside, opens outward 95 deg),
latch bolt, socket plates (native + keyhole), clips lf_cage_unlock / lf_cage_gate_open / lf_cage_gate_settle,
exit corridor and meta.  Blender axes: front (door side) = -Y, which is glTF +Z.

Node tree (glTF names):
  <id>_LOD0/1/2                      static frame
  door_pivot                         empty exactly on the hinge axis (rotates about +Z (Blender) / +Y (glTF))
    <id>_door_LOD0/1/2
    latch_pivot -> <id>_latch_LOD*   bolt slides -X (Blender/glTF) by `latch_travel` to clear the keeper
    socket_pivot -> <id>_socket_LOD* native socket plate (circle / hex / diamond)
      socket_core -> <id>_socket_core_LOD*, key_slot   (presses +Y 6 mm on unlock)
    socket_keyhole_pivot (scale 0 by default) -> keyhole plate
      keyhole_core -> ..., key_slot_keyhole            (turns 90 deg about the key axis on unlock)
"""
import math

import numpy as np

import artifactkit as ak
import propkit as pk
from propkit import M4, Rx, Ry, Rz

OPEN_DEG = 95.0
FPS = 30


def node_spec(asset_id, hinge, latch_world, socket_world):
    return {
        "root": {},
        "door": {"pivot": hinge, "export_name": "door_pivot"},
        "latch": {"pivot": latch_world, "parent": "door", "export_name": "latch_pivot"},
        "socket": {"pivot": socket_world, "parent": "door", "export_name": "socket_pivot"},
        "socket_core": {"pivot": socket_world, "parent": "socket", "export_name": "socket_core"},
        "keyhole": {"pivot": socket_world, "parent": "door", "export_name": "socket_keyhole_pivot"},
        "keyhole_core": {"pivot": socket_world, "parent": "keyhole", "export_name": "keyhole_core"},
    }


def add_sockets(B, kind, socket_world, plate_cls, core_cls=None, keyhole_cls=None):
    """Native + keyhole socket plates at socket_world (recess floor centre), normal -Y."""
    M = M4(None, socket_world)
    ak.build_socket(B, "socket", kind, M=M, cls=plate_cls, prefix="sock_native", plate=True,
                    floor_cls=core_cls or plate_cls)
    # move the recess floor into the pressing core node
    if "socket" in B.nodes:
        keep, move = [], []
        for p in B.nodes["socket"]:
            (move if p.name.endswith("_floor") else keep).append(p)
        B.nodes["socket"] = keep
        B.nodes.setdefault("socket_core", []).extend(move)
    ak.build_socket(B, "keyhole", "keyhole", M=M, cls=keyhole_cls or plate_cls, prefix="sock_keyhole", plate=True)
    if "keyhole" in B.nodes:
        keep, move = [], []
        for p in B.nodes["keyhole"]:
            (move if p.name.endswith("_floor") else keep).append(p)
        B.nodes["keyhole"] = keep
        B.nodes.setdefault("keyhole_core", []).extend(move)


def hinge_set(B, axis_xy, z_list, strap_len, strap_w, door_face_y, jamb_face_y, cls="bronze", knuckle_r=0.028,
              knuckle_h=0.075, leaf="door", static="root", strap_motif=None, jamb_dir=-1):
    """Barrel hinges on a vertical axis: alternating knuckles (jamb, door, jamb), jamb leaf plate on the
    static jamb, decorative strap with scroll end on the door (extends +X across the leaf)."""
    ax, ay = axis_xy
    seg = B.seg(10, 7, 5)
    for i, zc in enumerate(z_list):
        for k in range(3):
            z0 = zc - 1.5 * knuckle_h + k * knuckle_h
            node = static if k != 1 else leaf
            kn = pk.rod((ax, ay, z0 + 0.003), (ax, ay, z0 + knuckle_h - 0.003), knuckle_r, seg)
            B.add(node, f"hinge{i}_knuckle_{'d' if node == leaf else 's'}", cls, kn)
        # pin caps
        for zz, nm in ((zc - 1.5 * knuckle_h - 0.012, "a"), (zc + 1.5 * knuckle_h, "b")):
            cap = pk.lathe(np.array([[knuckle_r * 0.75, 0], [knuckle_r * 0.8, 0.006], [knuckle_r * 0.5, 0.012], [0, 0.014]]), seg)
            B.add(static, f"hinge{i}_caps", cls, cap.transformed(M4(None, (ax, ay, zz))))
        # jamb leaf (static plate on the jamb face, toward -X)
        plate = pk.extrude(pk.rect(0.11, knuckle_h * 3.0, 0.012), 0.008, chamfer=0.002)
        Mj = M4(Rx(math.pi / 2), (ax - 0.075 * (-jamb_dir) * -1 - 0.055, jamb_face_y, zc))
        B.add(static, f"hinge{i}_jambleaf", cls, plate.transformed(Mj))
        # door strap: tapered scroll strap along +X on the door face
        L = strap_len
        w = strap_w
        pts = [(0.0, -w / 2), (L * 0.55, -w * 0.42), (L * 0.78, -w * 0.62), (L * 0.92, -w * 0.5), (L, 0.0),
               (L * 0.92, w * 0.5), (L * 0.78, w * 0.62), (L * 0.55, w * 0.42), (0.0, w / 2)]
        strap = pk.extrude(np.array(pts), 0.009, chamfer=0.0025)
        Ms = M4(Rx(math.pi / 2), (ax + knuckle_r * 0.6, door_face_y, zc))
        B.add(leaf, f"hinge{i}_strap", cls, strap.transformed(Ms), meta={"motif": strap_motif} if strap_motif else None)


def door_angle_open(f, frames):
    t = f / frames
    e = t * t * t * (t * (6 * t - 15) + 10)          # smootherstep
    lag = 0.04 * math.sin(math.pi * min(1.0, t * 2.2)) * (1 - t)   # unsticking hesitation
    return -math.radians(OPEN_DEG) * max(0.0, min(1.0, e - lag))


def add_cage_clips(A, latch_travel=0.12, press=0.006):
    n_unlock = 30
    n_open = 48
    n_settle = 12

    def ease(a, b, f):
        return float(pk.smoothstep(np.clip((f - a) / max(b - a, 1e-6), 0, 1)))

    pk.add_clip(A, "lf_cage_unlock", {
        "socket_core": lambda f: {"loc": (0, press * (ease(0, 7, f) - 0.5 * ease(22, 30, f)), 0)},
        "keyhole_core": lambda f: {"rot": (0, -math.radians(90) * ease(0, 10, f), 0)},
        "latch": lambda f: {"loc": (-latch_travel * ease(8, 21, f), 0, 0)},
    }, n_unlock, markers={"latch_clear": 0.7})
    pk.add_clip(A, "lf_cage_gate_open", {
        "door": lambda f: {"rot": (0, 0, door_angle_open(f, n_open))},
        "latch": lambda f: {"loc": (-latch_travel, 0, 0)},
    }, n_open, markers={"passage_clear": 1.2})
    tot = -math.radians(OPEN_DEG)

    def settle(f):
        t = f / n_settle * 0.4
        d = math.radians(2.6) * math.exp(-7.5 * t) * math.sin(2 * math.pi * t / 0.27)
        if f == n_settle:
            d = 0.0
        return {"rot": (0, 0, tot + d)}
    pk.add_clip(A, "lf_cage_gate_settle", {"door": settle, "latch": lambda f: {"loc": (-latch_travel, 0, 0)}},
                n_settle, markers={})


def corridor_points(door_x0, door_x1, front_y, floor_z):
    xc = (door_x0 + door_x1) / 2
    return [(xc, front_y + 1.0, floor_z), (xc, front_y, floor_z), (xc, front_y - 1.3, 0.0), (xc, front_y - 2.5, 0.0)]


def cage_meta(A, asset_id, kind, hinge, door_width, door_height, socket_world, latch_travel, corridor, interior,
              clear_height, notes, glb, extra=None):
    import json
    from frlib import core, paths
    st = pk.tri_stats(A)
    summ = pk.glb_summary(glb)
    mn, mx = core.bounds(A.lod0_objects())
    key_slot_native = np.asarray(socket_world, float)
    meta = {
        "id": asset_id,
        "tris": {f"LOD{l}": st[f"LOD{l}"]["total"] for l in (0, 1, 2)},
        "tris_by_node": {f"LOD{l}": st[f"LOD{l}"]["by_node"] for l in (0, 1, 2)},
        "budget": "cage LOD0 <= 6000 tris (all nodes incl. door, latch and both socket variants)",
        "bones": 0,
        "materials": [f"{asset_id}_mat"],
        "textures": {"baseColor": "2048 JPEG", "metallicRoughness": "1024 JPEG (G rough, B metal)", "normal": "2048 PNG"},
        "coordinate_space": "glTF (Y up, metres) relative to the GLB root; door side faces +Z (atlas escapeApproachOffset)",
        "bounds_m": {"min": pk.b2g(mn), "max": pk.b2g(mx)},
        "clips": {c: {"seconds": round(v["frames"] / FPS, 4), "loop": False, "frames": v["frames"],
                      "markers": v["markers"], "glb_seconds": summ["animations"].get(c, {}).get("seconds")}
                  for c, v in A.clips.items()},
        "sockets": {
            "hinge_axis": {"node": "door_pivot", "point": pk.b2g(hinge), "direction": [0.0, 1.0, 0.0],
                           "side": "left jamb seen from outside (glTF -X side of the opening)"},
            "door_open_deg": OPEN_DEG,
            "door_rotation": "door_pivot rotates about glTF +Y; open = -95 deg about Blender Z = rotation_y(-95deg) in glTF? see poses",
            "key_slot": {"node": "key_slot", "parent": "socket_core", "position_closed": pk.b2g(key_slot_native),
                         "normal": [0.0, 0.0, 1.0], "height_above_ground_m": round(float(socket_world[2]), 3),
                         "shape": kind, "fits_family": {"circle": "stone_rune", "hex": "bronze_seal",
                                                        "diamond": "amber_crystal"}[kind],
                         "insert": "parent the artifact variant node to key_slot with identity transform"},
            "key_slot_keyhole": {"node": "key_slot_keyhole", "parent": "keyhole_core", "position_closed": pk.b2g(key_slot_native),
                                 "normal": [0.0, 0.0, 1.0], "shape": "keyhole", "fits_family": "bone_key",
                                 "activate": "set socket_keyhole_pivot.scale=1 and socket_pivot.scale=0 (default is native)"},
            "latch": {"node": "latch_pivot", "travel_m": latch_travel, "axis": [-1.0, 0.0, 0.0]},
            "door": {"node": "door_pivot", "width_m": door_width, "clear_height_m": door_height},
            "exit_corridor": [pk.b2g(p) for p in corridor],
            "interior_footprint_m": interior, "interior_clear_height_m": clear_height,
        },
        "poses": {
            "closed": {"door_pivot": {"rotation_y_deg": 0.0}, "latch_pivot": {"translation_offset": [0, 0, 0]}},
            "open": {"door_pivot": {"rotation_y_deg": -OPEN_DEG,
                                    "note": "glTF rotation about +Y by -95 deg (Blender -95 deg about +Z)"},
                     "latch_pivot": {"translation_offset": [-latch_travel, 0, 0]}},
        },
        "glb_nodes": summ["nodes"],
        "glb_animations": {k: v["channels"] for k, v in summ["animations"].items()},
        "notes": notes,
    }
    if extra:
        meta.update(extra)
    core.write_json(paths.runtime(pk.GROUP, f"{asset_id}.meta.json"), meta)
    return meta
