#!/usr/bin/env python3
"""iPhone memory: every 3D texture under godot/project/assets/forest_rescue/** (albedo, normal, ORM / roughness,
atlases incl. the shipped impostor atlas; actors, props, kit, landmarks, arena) → VRAM Compressed, high quality
(BPTC on desktop, ASTC 4x4 on iOS), mipmaps on, normal maps with the normal-map setting. There are no 2D UI
textures in this tree (the forest UI draws its icons). Optional --keep=<substring,...> keeps matching files lossless.

    python3 forest_rescue/tools/forest_textures_vram.py [--dry-run] [--keep=a,b]
then re-import: godot --headless --path godot/project --import
"""
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "godot/project/assets/forest_rescue"))
NORMAL = re.compile(r"(_normal|_n)\.(png|jpe?g)$", re.I)


def main():
    dry = "--dry-run" in sys.argv
    keep = []
    for a in sys.argv[1:]:
        if a.startswith("--keep="):
            keep = [k for k in a[7:].split(",") if k]
    counts = {"vram": 0, "normal": 0, "kept": 0}
    for root, _dirs, files in os.walk(ROOT):
        for f in files:
            if not f.endswith(".import"):
                continue
            path = os.path.join(root, f)
            text = open(path).read()
            if 'importer="texture"' not in text:
                continue
            src = f[:-7]
            lossless = any(k in src for k in keep)
            normal = bool(NORMAL.search(src))
            params = {"compress/mode": "0" if lossless else "2", "compress/high_quality": "true",
                      "mipmaps/generate": "true", "compress/normal_map": "1" if normal else "0",
                      "detect_3d/compress_to": "0"}
            for k, v in params.items():
                text, n = re.subn(r"^%s=.*$" % re.escape(k), "%s=%s" % (k, v), text, flags=re.M)
                if n == 0:
                    text = text.replace("[params]\n", "[params]\n\n%s=%s\n" % (k, v), 1)
            counts["kept" if lossless else "vram"] += 1
            counts["normal"] += normal
            if not dry:
                open(path, "w").write(text)
    print(counts)


if __name__ == "__main__":
    main()
