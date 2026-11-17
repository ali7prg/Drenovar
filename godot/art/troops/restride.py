"""Author horse locomotion in the existing rig; never re-export or simplify meshes.

Input is the unmodified troops06 glTF + bin pair. Animation buffers are appended;
all original geometry, materials, skins and image references remain byte-identical.
Three-link legs use an analytic two-link solve above a controlled fetlock. Contact
intervals move hooves backwards at exactly the authored root speed. Run is a
four-beat gallop with suspension, Trot diagonal pairs, Walk four separate beats.

python restride.py --source-dir ORIGINAL_TROOPS06 --output-dir PROJECT_TROOPS06
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

GAITS = {
    "Walk": dict(duration=1.20, speed=1.55, stance=.60, lift=.15,
                 offsets=[0, .5, .75, .25]),
    "Trot": dict(duration=.78, speed=3.4, stance=.32, lift=.31,
                 offsets=[0, .5, .5, 0]),
    "Run": dict(duration=.72, speed=6.25, stance=.20, lift=.38,
                offsets=[0, .12, .38, .50]),
}
LEGS = [
    ["HindLHip", "HindLStifle", "HindLHock", "HindLHoof"],
    ["HindRHip", "HindRStifle", "HindRHock", "HindRHoof"],
    ["FrontLScapula", "FrontLUpper", "FrontLKnee", "FrontLHoof"],
    ["FrontRScapula", "FrontRUpper", "FrontRKnee", "FrontRHoof"],
]


def rotation_between(a, b):
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    cross = np.cross(a, b)
    if np.linalg.norm(cross) < 1e-10:
        return np.eye(3)
    return Rotation.from_rotvec(cross / np.linalg.norm(cross) * math.acos(np.clip(a @ b, -1, 1))).as_matrix()


def rest_pose(nodes):
    parents = {c: i for i, n in enumerate(nodes) for c in n.get("children", [])}
    matrices = {}
    def world(i):
        if i in matrices:
            return matrices[i]
        n = nodes[i]
        m = np.eye(4)
        m[:3, :3] = Rotation.from_quat(n.get("rotation", [0, 0, 0, 1])).as_matrix() @ np.diag(n.get("scale", [1, 1, 1]))
        m[:3, 3] = n.get("translation", [0, 0, 0])
        matrices[i] = (world(parents[i]) @ m) if i in parents else m
        return matrices[i]
    for i in range(len(nodes)):
        world(i)
    return parents, matrices


def author(source, output):
    doc = json.loads(source.read_text())
    blob = bytearray((source.parent / doc["buffers"][0]["uri"]).read_bytes())
    original_digest = hashlib.sha256(blob).hexdigest()
    nodes = doc["nodes"]
    ids = {n.get("name"): i for i, n in enumerate(nodes)}
    parents, rest = rest_pose(nodes)
    root = ids["HorseRoot"]
    report = {"file": source.name, "original_buffer_sha256": original_digest, "gaits": {}}
    originals = {a["name"]: a for a in doc["animations"]}

    def read_accessor(i):
        a = doc["accessors"][i]; v = doc["bufferViews"][a["bufferView"]]
        assert a["componentType"] == 5126 and not v.get("byteStride")
        size = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}[a["type"]]
        return np.frombuffer(blob, dtype='<f4', count=a["count"]*size,
                             offset=v.get("byteOffset", 0)+a.get("byteOffset", 0)).copy().reshape(-1, size)

    def append_accessor(values, kind):
        values = np.asarray(values, dtype='<f4')
        while len(blob) % 4:
            blob.append(0)
        view = len(doc["bufferViews"])
        doc["bufferViews"].append({"buffer": 0, "byteOffset": len(blob), "byteLength": values.nbytes})
        blob.extend(values.tobytes())
        index = len(doc["accessors"])
        a = {"bufferView": view, "componentType": 5126, "count": len(values), "type": kind}
        if kind == "SCALAR":
            a.update(min=[float(values.min())], max=[float(values.max())])
        doc["accessors"].append(a)
        return index

    for name, cfg in GAITS.items():
        # Existing rider, reins, stirrup and carried weapon channels stay in the
        # HorseBack frame. Only their cycle duration changes, not their geometry.
        animation = copy.deepcopy(originals["Walk" if name == "Walk" else "Run"])
        animation["name"] = name
        modified_nodes = {root, ids['HorseBack']} | {ids[n] for leg in LEGS for n in leg}
        animation["channels"] = [c for c in animation["channels"] if c["target"]["node"] not in modified_nodes]
        old_duration = max(float(read_accessor(s["input"])[-1, 0]) for s in animation["samplers"])
        times_map = {}
        for s in animation["samplers"]:
            old = s["input"]
            if old not in times_map:
                times_map[old] = append_accessor(read_accessor(old) * cfg["duration"] / old_duration, "SCALAR")
            s["input"] = times_map[old]
        # Contact boundaries are explicit samples as well as a 120 Hz authoring
        # grid. Thus resampling does not round touchdown to an arbitrary frame.
        phases = sorted(set([i / 120 for i in range(121)] +
                            [round((o + q) % 1, 8) for o in cfg["offsets"] for q in [0, cfg["stance"]]]))
        input_id = append_accessor(np.array(phases) * cfg["duration"], "SCALAR")
        tracks = {(root, "translation"): []}
        for leg in LEGS:
            for n in leg:
                tracks[ids[n], "rotation"] = []
        max_error = 0.
        for phase in phases:
            # Lower the centre of mass under load, rise through suspension.
            if name == "Run":
                suspension = max(0., math.sin(math.pi * np.clip((phase-.70)/.30, 0, 1)))
                bob = -.13 + .13*suspension
            elif name == "Trot":
                bob = -.17 + .035*(1-math.cos(4*math.pi*phase))
            else:
                bob = -.20 + .012*math.cos(4*math.pi*phase)
            root_translation = np.asarray(nodes[root].get("translation", [0, 0, 0]), dtype=float).copy()
            parent_rotation = rest[parents[root]][:3, :3] if root in parents else np.eye(3)
            root_translation += np.linalg.solve(parent_rotation, [0, bob, 0])
            tracks[root, "translation"].append(root_translation)
            for k, leg in enumerate(LEGS):
                chain = [ids[n] for n in leg]
                points = np.array([rest[i][:3, 3] for i in chain])
                lengths = np.linalg.norm(np.diff(points, axis=0), axis=1)
                local = (phase-cfg["offsets"][k]) % 1
                travel = cfg["speed"] * cfg["duration"] * cfg["stance"]
                if local <= cfg["stance"]:
                    z = travel/2 - cfg["speed"]*cfg["duration"]*local
                    lift = 0.
                else:
                    s = (local-cfg["stance"])/(1-cfg["stance"])
                    # Hermite swing: toe leaves backwards and meets the ground
                    # moving backwards; no low sine-wave skating interval.
                    z = (-travel/2)*(2*s**3-3*s*s+1) + (travel/2)*(-2*s**3+3*s*s) - .65*travel*(2*s**3-3*s*s+s)
                    lift = cfg["lift"]*math.sin(math.pi*s)
                target = points[-1].copy(); target[2] += z; target[1] += lift
                hip = points[0] + [0, bob, 0]
                # Three-link equine anatomy: a controlled lower segment, then a
                # two-link solve with the knee/stifle forward of its joint line.
                lower = np.array([0., -.98, .20 if k < 2 else -.12])
                lower = lower / np.linalg.norm(lower) * lengths[2]
                ankle = target-lower
                axis = ankle-hip; distance = np.linalg.norm(axis); axis /= distance
                reach = min(distance, lengths[0]+lengths[1]-.0001)
                if distance > reach:
                    ankle = hip + axis*reach
                    target = ankle+lower
                max_error = max(max_error, distance-reach)
                cosine = np.clip((lengths[0]**2+reach**2-lengths[1]**2)/(2*lengths[0]*reach), -1, 1)
                pole = np.array([0., 0., 1.]); pole -= axis*(pole@axis); pole /= np.linalg.norm(pole)
                knee = hip+axis*lengths[0]*cosine+pole*lengths[0]*math.sqrt(1-cosine*cosine)
                solved = [hip, knee, ankle, target]
                parent_rot = rest[parents[chain[0]]][:3, :3]
                for j, i in enumerate(chain):
                    global_rot = (rotation_between(points[j+1]-points[j], solved[j+1]-solved[j]) @ rest[i][:3, :3]
                                  if j < 3 else rest[i][:3, :3])
                    local_rot = np.linalg.solve(parent_rot, global_rot)
                    quat = Rotation.from_matrix(local_rot).as_quat()
                    track = tracks[i, "rotation"]
                    if track and np.dot(track[-1], quat) < 0:
                        quat = -quat
                    track.append(quat)
                    parent_rot = global_rot
        for (node, path), values in tracks.items():
            sampler = len(animation["samplers"])
            animation["samplers"].append({"input": input_id, "output": append_accessor(values, "VEC3" if path == "translation" else "VEC4"), "interpolation": "LINEAR"})
            animation["channels"].append({"sampler": sampler, "target": {"node": node, "path": path}})
        animation["extras"] = {"rootSpeed": cfg["speed"], "contacts": [
            {"bone": leg[-1], "phase": cfg["offsets"][k], "stance": cfg["stance"]} for k, leg in enumerate(LEGS)]}
        doc["animations"] = [a for a in doc["animations"] if a["name"] != name] + [animation]
        report["gaits"][name] = {**cfg, "unreachable_max_m": max_error, "samples": len(phases)}
    doc["buffers"][0]["byteLength"] = len(blob)
    output.mkdir(parents=True, exist_ok=True)
    (output / source.name).write_text(json.dumps(doc, separators=(',', ':'))+'\n')
    (output / doc["buffers"][0]["uri"]).write_bytes(blob)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--source-dir', type=Path, required=True); p.add_argument('--output-dir', type=Path, required=True)
    args = p.parse_args()
    reports = [author(args.source_dir / f'{unit}-lod{lod}.gltf', args.output_dir)
               for unit in ['ENG-05', 'ENG-06'] for lod in [1, 2]]
    print(json.dumps(reports, indent=2))
