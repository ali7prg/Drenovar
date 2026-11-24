#!/usr/bin/env python3
"""Estimates the GPU and CPU memory of the shipped assets on an iPhone (build 1024, stage 5).

Reads the imported files in godot/project/.godot/imported (run the Godot import first) and the
.import files under godot/project/assets, keeps what the iOS export ships (export_presets.cfg
exclude_filter), and for every texture picks the variant an iPhone loads: the ASTC or ETC2 file
when the texture is VRAM-compressed, else the lossless one (decoded to RGBA8 on upload: Metal has
no 3-byte format). Bytes on the GPU = the compressed payload with its mipmaps, or w x h x 4 x 4/3
for a lossless texture with mipmaps. Audio: Ogg Vorbis streams stay compressed in memory (the file
size). Meshes and scenes: the imported .scn/.res/.mesh size (vertex data, a little more on the GPU).

Usage: python3 estimate_ios_memory.py <godot/project> [--json out.json] [--top N]
The groups are the top asset folders; the report also sums the groups a session can hold at once
(city + world + forest + interface + army + creatures). An estimate, not a device measurement.
"""
import fnmatch
import glob
import json
import os
import re
import struct
import sys

# Godot 4 Image.Format: bits per pixel of the compressed formats, bytes of the plain ones.
COMPRESSED_BPP = {17: 4, 18: 8, 19: 8, 20: 4, 21: 8, 22: 8, 23: 8, 24: 8, 25: 4, 26: 4, 27: 4, 28: 8, 29: 8,
                  30: 4, 31: 8, 32: 4, 33: 8, 34: 8, 35: 8, 36: 8, 37: 2, 38: 2}
PLAIN_BYTES = {0: 1, 1: 2, 2: 1, 3: 2, 4: 4, 5: 4, 6: 2, 7: 2, 8: 4, 9: 8, 10: 16, 11: 16, 12: 2, 13: 4, 14: 8, 15: 8, 16: 4}
FORMAT_NAMES = {4: "RGB8", 5: "RGBA8", 28: "ETC2_RG11", 30: "ETC2_RGB8", 31: "ETC2_RGBA8", 35: "ASTC_4x4", 37: "ASTC_8x8"}


def ctex_info(path):
    with open(path, "rb") as f:
        head = f.read(52)
    if len(head) < 52 or head[:4] != b"GST2":
        return None
    data_format, w, h, mipmaps, fmt = struct.unpack("<IHHII", head[36:52])
    size = os.path.getsize(path)
    if fmt in COMPRESSED_BPP:
        gpu = size - 52
    else:
        bpp = max(4, PLAIN_BYTES.get(fmt, 4))   # RGB8 and smaller formats go up as RGBA8 on Metal
        gpu = w * h * bpp * (4 / 3 if mipmaps > 0 else 1)
    return {"w": w, "h": h, "mipmaps": mipmaps, "format": FORMAT_NAMES.get(fmt, str(fmt)), "gpu": int(gpu),
            "compressed": fmt in COMPRESSED_BPP, "stored": "image" if data_format == 0 else ("webp" if data_format == 2 else "png")}


def export_excludes(project):
    text = open(os.path.join(project, "export_presets.cfg")).read()
    match = re.search(r'^exclude_filter="([^"]*)"', text, re.M)
    return [p.strip() for p in match.group(1).split(",")] if match else []


def excluded(rel, patterns):
    return any(fnmatch.fnmatch(rel, p) for p in patterns)


def main(project, out=None, top=12):
    patterns = export_excludes(project)
    groups = {}
    rows = []
    for imp in glob.glob(os.path.join(project, "assets", "**", "*.import"), recursive=True):
        rel = os.path.relpath(imp, project)[:-len(".import")]
        if excluded(rel, patterns):
            continue
        text = open(imp).read()
        dest = re.search(r"^dest_files=\[(.*)\]$", text, re.M)
        if not dest:
            continue
        files = [d.strip().strip('"').replace("res://", "") for d in dest.group(1).split(",") if d.strip()]
        files = [os.path.join(project, f) for f in files]
        importer = (re.search(r'^importer="([^"]+)"', text, re.M) or [None, ""])[1]
        group = rel.split("/")[1] if rel.count("/") >= 2 else "assets"
        g = groups.setdefault(group, {"textures": 0, "gpu_textures": 0, "uncompressed_textures": 0, "uncompressed_gpu": 0,
                                      "audio": 0, "audio_bytes": 0, "meshes": 0, "mesh_bytes": 0})
        if importer == "texture":
            pick = [f for f in files if f.endswith((".astc.ctex", ".etc2.ctex"))] or files
            pick = [f for f in pick if os.path.exists(f)]
            if not pick:
                continue
            info = ctex_info(pick[0])
            if info is None:
                continue
            g["textures"] += 1
            g["gpu_textures"] += info["gpu"]
            if not info["compressed"]:
                g["uncompressed_textures"] += 1
                g["uncompressed_gpu"] += info["gpu"]
            rows.append({"file": rel, **info})
        elif importer.startswith("ogg") or importer in ("wav", "mp3"):
            for f in files:
                if os.path.exists(f):
                    g["audio"] += 1
                    g["audio_bytes"] += os.path.getsize(f)
        elif importer in ("scene", "mesh") or text.find('type="PackedScene"') >= 0:
            for f in files:
                if os.path.exists(f):
                    g["meshes"] += 1
                    g["mesh_bytes"] += os.path.getsize(f)
    mb = lambda v: round(v / 1048576.0, 1)
    table = {k: {**v, "gpu_textures_mb": mb(v["gpu_textures"]), "uncompressed_gpu_mb": mb(v["uncompressed_gpu"]),
                 "audio_mb": mb(v["audio_bytes"]), "mesh_mb": mb(v["mesh_bytes"])} for k, v in sorted(groups.items())}
    total = {key: mb(sum(v[key] for v in groups.values())) for key in ("gpu_textures", "uncompressed_gpu", "audio_bytes", "mesh_bytes")}
    rows.sort(key=lambda r: -r["gpu"])
    result = {"groups": table, "total_mb": total, "largest_textures": [{**r, "gpu_mb": mb(r["gpu"])} for r in rows[:top]],
              "largest_uncompressed": [{**r, "gpu_mb": mb(r["gpu"])} for r in rows if not r["compressed"]][:top]}
    print("%-22s %6s %10s %8s %10s %6s %8s %7s %8s" % ("group", "tex", "GPU MB", "lossless", "lossl. MB", "audio", "audio MB", "meshes", "mesh MB"))
    for k, v in table.items():
        print("%-22s %6d %10.1f %8d %10.1f %6d %8.1f %7d %8.1f" % (k, v["textures"], v["gpu_textures_mb"], v["uncompressed_textures"], v["uncompressed_gpu_mb"],
                                                                v["audio"], v["audio_mb"], v["meshes"], v["mesh_mb"]))
    print("TOTAL", json.dumps(total))
    if out:
        with open(out, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    return result


if __name__ == "__main__":
    args = sys.argv[1:]
    out = args[args.index("--json") + 1] if "--json" in args else None
    top = int(args[args.index("--top") + 1]) if "--top" in args else 12
    main(args[0], out, top)
