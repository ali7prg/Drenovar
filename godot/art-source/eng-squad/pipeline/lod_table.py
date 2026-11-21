#!/usr/bin/env python3
"""Triangles actually drawn per model at the game cameras, from Godot auto-LOD edge lengths.

Rule (validated against RenderingServer primitive counts for ENG-01 field, see lod_eng01.json):
  per surface, Godot draws the coarsest generated LOD whose edge_length * scale projected to the
  screen is <= mesh_lod_threshold (1 px, project default):
    perspective: edge * scale * W / (d * 2*tan(fovx/2)) <= 1   (d = camera-to-model distance)
    orthographic: edge * scale * W / (size * aspect) <= 1      (size = Camera3D.size = city zoom)
usage: python3 lod_table.py <godot_model_probe.json> <out.json>
"""
import json, math, sys

W, H = 1366, 630
ASPECT = W / H
FOVY = math.radians(43)
TANX = math.tan(FOVY / 2) * ASPECT
K_PERSP = W / (2 * TANX)          # px per metre at distance 1 m
K_ORTHO = W / ASPECT              # px per metre for size 1 (=H)


def tris_at(model, px_per_m, scale):
    total = 0
    levels = {}
    for mesh in model["meshes"]:
        for s in mesh["surfaces"]:
            tri = s["index_count"] // 3
            lvl = 0
            for i, l in enumerate(s["lods"]):
                if l["edge_length"] * scale * px_per_m <= 1.0:
                    tri = l["index_count"] // 3
                    lvl = i + 1
                else:
                    break
            total += tri
            levels[lvl] = levels.get(lvl, 0) + 1
    return total, levels


def switch_table(model, scale):
    """distance (perspective) / ortho size at which each surface LOD level becomes active."""
    rows = []
    for mesh in model["meshes"]:
        for s in mesh["surfaces"]:
            rows.append({"surface": s["material"], "tris": s["index_count"] // 3,
                         "lods": [{"level": i + 1, "tris": l["index_count"] // 3, "edge_m": round(l["edge_length"], 5),
                                   "world_distance_m": round(l["edge_length"] * scale * K_PERSP, 2),
                                   "city_size": round(l["edge_length"] * scale * K_ORTHO, 2)} for i, l in enumerate(s["lods"])]})
    return rows


def main():
    probe = json.load(open(sys.argv[1]))
    cams = {"world_d15": ("p", 15), "world_d30": ("p", 30), "world_d68": ("p", 68), "world_d132": ("p", 132),
            "city_z24": ("o", 24), "city_z70": ("o", 70), "city_z120": ("o", 120), "armory": ("armory", 0)}
    out = {}
    for key, m in probe["models"].items():
        role = key.split("/")[1]
        scale = 1.15 if role == "field" else 1.0
        row = {"base_tris": m["totals"]["triangles"], "base_vertices": m["totals"]["vertices"],
               "lod_levels": max(len(s["lods"]) for mm in m["meshes"] for s in mm["surfaces"]),
               "lod_totals": [m["totals"]["triangles"]] + [m["lod_triangles"][str(i)] for i in range(len(m["lod_triangles"]))]}
        drawn = {}
        for cname, (kind, v) in cams.items():
            if kind == "p":
                ppm = K_PERSP / v
            elif kind == "o":
                ppm = K_ORTHO / v
            else:
                continue
            t, lv = tris_at(m, ppm, scale)
            drawn[cname] = t
        row["drawn_tris"] = drawn
        row["switch"] = switch_table(m, scale)
        out[key] = row
    json.dump(out, open(sys.argv[2], "w"), indent=1)
    for key, r in out.items():
        print(f"{key:15s} base={r['base_tris']:6d} levels={r['lod_levels']} totals={r['lod_totals']} drawn={r['drawn_tris']}")


if __name__ == "__main__":
    main()
