#!/usr/bin/env python3
"""Phone-build readiness: share the arena's embedded textures instead of shipping (and uploading) one copy
per GLB. Each listed .glb gets its embedded images replaced by relative URIs to one canonical project file
with the same bytes (a forest kit texture, the texture a runtime part GLB extracts, or else the copy the
LOD0 GLB extracted), and its binary chunk is compacted. Godot's glTF importer then loads those textures as
ordinary shared resources, so LOD0 / LOD1 / LOD2 and the kit reference one CompressedTexture2D each.

    python3 forest_rescue/tools/dedupe_glb_textures.py [--dry-run]

Afterwards: re-import (godot --headless --path godot/project --import), check, then delete the stale
copies this script lists (the per-GLB extractions no import produces any more).
"""
import hashlib
import json
import os
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ASSETS = os.path.join(ROOT, "godot/project/assets")
ARENA = os.path.join(ASSETS, "forest_rescue/arena")
TARGETS = ["lf_boss_arena_assembled.glb", "lf_boss_arena_assembled_lod1.glb", "lf_boss_arena_assembled_lod2.glb"]
# canonical-file preference: kit textures, then textures extracted by GLBs that stay embedded and are used at
# runtime (banner, bones) or by the part GLBs, then the LOD0 extraction
PREFER = ["forest_rescue/forest/", "forest_rescue/arena/lf_arena_banner_", "forest_rescue/arena/lf_arena_bones_",
          "forest_rescue/arena/lf_arena_", "forest_rescue/arena/lf_boss_arena_assembled_lf_"]


def read_glb(path):
    b = open(path, "rb").read()
    magic, version, length = struct.unpack("<III", b[:12])
    assert magic == 0x46546C67 and version == 2
    jlen, jtype = struct.unpack("<II", b[12:20])
    js = json.loads(b[20:20 + jlen])
    rest = b[20 + jlen:]
    bin_ = b""
    if len(rest) >= 8:
        blen, btype = struct.unpack("<II", rest[:8])
        assert btype == 0x004E4942
        bin_ = rest[8:8 + blen]
    return js, bin_


def write_glb(path, js, bin_):
    jb = json.dumps(js, separators=(",", ":")).encode()
    jb += b" " * ((4 - len(jb) % 4) % 4)
    bb = bin_ + b"\0" * ((4 - len(bin_) % 4) % 4)
    total = 12 + 8 + len(jb) + (8 + len(bb) if bb else 0)
    out = struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(jb), 0x4E4F534A) + jb
    if bb:
        out += struct.pack("<II", len(bb), 0x004E4942) + bb
    open(path, "wb").write(out)


def project_textures():
    by_md5 = {}
    for root, _dirs, files in os.walk(ASSETS):
        for f in files:
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                p = os.path.join(root, f)
                by_md5.setdefault(hashlib.md5(open(p, "rb").read()).hexdigest(), []).append(os.path.relpath(p, ASSETS))
    return by_md5


def canonical(paths, banned):
    ok = [p for p in paths if p not in banned]
    for pref in PREFER:
        for p in sorted(ok):
            if p.startswith(pref):
                return p
    return sorted(ok)[0] if ok else None


def main():
    dry = "--dry-run" in sys.argv
    by_md5 = project_textures()
    # copies extracted by the LOD1 / LOD2 GLBs are never canonical (they go away)
    banned = {p for ps in by_md5.values() for p in ps
              if os.path.basename(p).startswith(("lf_boss_arena_assembled_lod1_", "lf_boss_arena_assembled_lod2_"))}
    saved = 0
    used = set()
    for name in TARGETS:
        path = os.path.join(ARENA, name)
        js, bin_ = read_glb(path)
        views = js["bufferViews"]
        image_views = set()
        for img in js.get("images", []):
            if "bufferView" not in img:
                continue
            v = views[img["bufferView"]]
            data = bin_[v.get("byteOffset", 0):v.get("byteOffset", 0) + v["byteLength"]]
            md5 = hashlib.md5(data).hexdigest()
            target = canonical(by_md5.get(md5, []), banned)
            if target is None:
                raise SystemExit("%s: image %s has no project copy" % (name, img.get("name")))
            used.add(target)
            image_views.add(img["bufferView"])
            del img["bufferView"]
            img["uri"] = os.path.relpath(os.path.join(ASSETS, target), ARENA).replace(os.sep, "/")
            saved += len(data)
        # compact the binary chunk: keep every bufferView index (accessors keep their references), copy the
        # non-image views, point the image views at the first byte (unreferenced now)
        out = bytearray()
        for i, v in enumerate(views):
            if i in image_views:
                v["byteOffset"] = 0
                v["byteLength"] = 1
                continue
            start = v.get("byteOffset", 0)
            chunk = bin_[start:start + v["byteLength"]]
            while len(out) % 4:
                out.append(0)
            v["byteOffset"] = len(out)
            out += chunk
        if not out:
            out = bytearray(4)
        js["buffers"][0]["byteLength"] = len(out)
        print("%s: %d images -> URIs, %.1f MB -> %.1f MB" % (name, len(image_views), len(bin_) / 1e6, len(out) / 1e6))
        if not dry:
            write_glb(path, js, bytes(out))
    stale = sorted(p for ps in by_md5.values() for p in ps
                   if os.path.basename(p).startswith("lf_boss_arena_assembled") and p not in used)
    print("embedded image bytes removed: %.1f MB; canonical files used: %d" % (saved / 1e6, len(used)))
    print("STALE (delete after re-import, with their .import):")
    for p in stale:
        print("  " + p)


if __name__ == "__main__":
    main()
