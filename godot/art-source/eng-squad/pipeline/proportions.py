#!/usr/bin/env python3
"""Bind-pose proportions of the warrior GLBs (vertex level, model units = metres before x1.15).

top_of_head: max Y of vertices whose dominant joint is Head (helmet/hood/hair included,
weapons excluded because they are weighted to hands). shoulder_width: X extent of torso/arm
vertices in the shoulder band. Also overall bbox and weapon extents (hand-weighted vertices).
usage: python3 proportions.py <out.json> <model.glb> [<model.glb> ...]
"""
import json, sys, os, glob
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from glb_audit import read_glb, accessor


def analyse(path):
    j, binc, _, _ = read_glb(path)
    nodes = j["nodes"]
    pts = []  # (xyz, dominant joint name, material)
    for n in nodes:
        if "mesh" not in n or "skin" not in n:
            continue
        joints = [nodes[i]["name"] for i in j["skins"][n["skin"]]["joints"]]
        for p in j["meshes"][n["mesh"]]["primitives"]:
            pos = accessor(j, binc, p["attributes"]["POSITION"]).astype(np.float64)
            jo = accessor(j, binc, p["attributes"]["JOINTS_0"]).astype(int)
            we = accessor(j, binc, p["attributes"]["WEIGHTS_0"]).astype(np.float64)
            dom = jo[np.arange(len(jo)), we.argmax(1)]
            mat = j["materials"][p["material"]]["name"] if "material" in p else ""
            for k in range(len(pos)):
                pts.append((pos[k], joints[dom[k]], mat))
    P = np.array([q[0] for q in pts])
    J = np.array([q[1] for q in pts])
    M = np.array([q[2] for q in pts])
    res = {"file": os.path.basename(path), "bbox_min": P.min(0).round(4).tolist(), "bbox_max": P.max(0).round(4).tolist()}
    head = P[J == "Head"]
    if len(head):
        res["top_of_head"] = round(float(head[:, 1].max()), 4)
        res["head_width_x"] = round(float(np.ptp(head[:, 0])), 4)
        res["head_depth_z"] = round(float(np.ptp(head[:, 2])), 4)
    body_j = {"Hips", "Spine", "Chest", "Neck", "Head", "RightUpperArm", "LeftUpperArm", "RightForearm", "LeftForearm",
              "RightThigh", "LeftThigh", "RightShin", "LeftShin", "RightFoot", "LeftFoot", "RightToe", "LeftToe"}
    body = np.array([q in body_j for q in J])
    B = P[body]
    if "HorseRoot" not in J:
        res["body_bbox_min"] = B.min(0).round(4).tolist()
        res["body_bbox_max"] = B.max(0).round(4).tolist()
        # shoulder band: around the UpperArm joint height (1.425 rest) +/- 6 cm, torso+upper arms only
        sj = {"Chest", "RightUpperArm", "LeftUpperArm", "Neck"}
        sel = np.array([q in sj for q in J])
        S = P[sel]
        band = S[(S[:, 1] > 1.36) & (S[:, 1] < 1.48)]
        if len(band):
            res["shoulder_width"] = round(float(np.ptp(band[:, 0])), 4)
            res["shoulder_depth"] = round(float(np.ptp(band[:, 2])), 4)
        hipb = P[np.array([q in {"Hips", "RightThigh", "LeftThigh"} for q in J])]
        band = hipb[(hipb[:, 1] > 0.85) & (hipb[:, 1] < 0.98)]
        if len(band):
            res["hip_width"] = round(float(np.ptp(band[:, 0])), 4)
        foot = P[np.array([q in {"RightFoot", "LeftFoot", "RightToe", "LeftToe"} for q in J])]
        res["sole_y"] = round(float(foot[:, 1].min()), 4)
        res["foot_length"] = round(float(np.ptp(foot[foot[:, 0] > 0][:, 2])), 4)
    else:
        horse_j = {q for q in set(J) if q.startswith(("Horse", "Front", "Hind", "Tail"))}
        H = P[np.array([q in horse_j for q in J])]
        R = P[body]
        res["horse_bbox_min"] = H.min(0).round(4).tolist()
        res["horse_bbox_max"] = H.max(0).round(4).tolist()
        res["horse_length_z"] = round(float(np.ptp(H[:, 2])), 4)
        back = P[J == "HorseBack"]
        res["horseback_top_y"] = round(float(back[:, 1].max()), 4) if len(back) else None
        res["rider_bbox_min"] = R.min(0).round(4).tolist()
        res["rider_bbox_max"] = R.max(0).round(4).tolist()
        # withers: horse vertices above the front legs (z in [0.1, 0.5])
        w = H[(H[:, 2] > 0.1) & (H[:, 2] < 0.5) & np.array([True] * len(H))]
        res["withers_y_approx"] = round(float(w[:, 1].max()), 4) if len(w) else None
        sj = {"Chest", "RightUpperArm", "LeftUpperArm"}
        S = P[np.array([q in sj for q in J])]
        if len(S):
            res["rider_shoulder_width"] = round(float(np.ptp(S[:, 0])), 4)
    hands = P[np.array([q in {"RightHand", "LeftHand"} for q in J])]
    res["hand_items_bbox_min"] = hands.min(0).round(4).tolist()
    res["hand_items_bbox_max"] = hands.max(0).round(4).tolist()
    # per material extent of hand-weighted vertices (weapon geometry)
    items = {}
    for mat in sorted(set(M)):
        sel = (M == mat) & np.array([q in {"RightHand", "LeftHand"} for q in J])
        if sel.sum() > 0:
            Q = P[sel]
            items[mat] = {"count": int(sel.sum()), "min": Q.min(0).round(3).tolist(), "max": Q.max(0).round(3).tolist()}
    res["hand_items_by_material"] = items
    return res


if __name__ == "__main__":
    out = []
    for f in sys.argv[2:]:
        r = analyse(f)
        out.append(r)
        print(json.dumps({k: v for k, v in r.items() if k != "hand_items_by_material"}))
        for k, v in r["hand_items_by_material"].items():
            print("    ", k, v)
    json.dump(out, open(sys.argv[1], "w"), indent=1)
