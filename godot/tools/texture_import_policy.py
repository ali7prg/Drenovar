#!/usr/bin/env python3
"""Sets the Godot import policy for 3D textures: VRAM compressed (ASTC/ETC2 on iOS,
BPTC/S3TC on desktop) at the original resolution, normal maps flagged as such.

Lossless (compress/mode=0) textures are uploaded as uncompressed RGBA8: four times the
GPU memory of ASTC 4x4. The editor only switches textures to VRAM compression after
detecting 3D use interactively, so headless/CI imports shipped them uncompressed.
2D interface art (ui, icons, intro, portraits, environment catalogue atlas) is left
lossless. Usage: python3 texture_import_policy.py <godot/project> [--check]
"""
import glob
import os
import re
import sys

THREE_D = ("army/", "city/", "city-details/", "city-ground/", "creature-assets37/", "world-ground/",
           "world-scenery/", "environment/surfaces20.png", "environment/forest60")
TWO_D = ("ui/", "icons/", "intro/", "creatures37/", "environment/atlas.webp")


def policy(project, check=False):
    changed, offenders = 0, []
    for path in glob.glob(os.path.join(project, "assets", "**", "*.import"), recursive=True):
        rel = os.path.relpath(path, os.path.join(project, "assets"))
        text = open(path).read()
        if 'importer="texture"' not in text:
            continue
        if rel.startswith(TWO_D) or not rel.startswith(THREE_D):
            continue
        normal = "normal" in os.path.basename(rel).lower()
        wanted = {"compress/mode": "2", "mipmaps/generate": "true", "compress/normal_map": "1" if normal else "0",
                  "detect_3d/compress_to": "0"}
        new = text
        for key, value in wanted.items():
            new = re.sub(rf"^{re.escape(key)}=.*$", f"{key}={value}", new, flags=re.M)
        if new != text:
            if check:
                offenders.append(rel)
            else:
                open(path, "w").write(new)
                changed += 1
    if check:
        print("UNCOMPRESSED_3D_TEXTURES", len(offenders))
        for o in offenders[:20]:
            print("  ", o)
        return 1 if offenders else 0
    print("TEXTURE_POLICY updated", changed)
    return 0


if __name__ == "__main__":
    sys.exit(policy(sys.argv[1], "--check" in sys.argv))
