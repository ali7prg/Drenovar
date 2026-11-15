"""Post-export step: converts a glTF's PNG textures to baseline JPEG (PIL) and rewrites the
image URIs. Godot imports PIL-written JPEGs; Blender's JPEG writer output is rejected by
Godot 4.6.3's importer (valid=false). Usage: python3 compress_textures.py <dir> [quality]"""
import glob
import json
import os
import sys

from PIL import Image


def main(directory, quality=90):
    os.chdir(directory)
    used = set()
    for path in sorted(glob.glob("*.gltf")):
        data = json.load(open(path))
        for image in data.get("images", []):
            uri = image.get("uri", "")
            stem, ext = os.path.splitext(uri)
            target = stem + ".jpg"
            if ext.lower() in (".png", ".jpg", ".jpeg") and os.path.exists(uri):
                if ext.lower() == ".png" or not getattr(main, "_seen", set()).__contains__(uri):
                    Image.open(uri).convert("RGB").save(target + ".tmp", "JPEG", quality=quality, subsampling=0)
                    os.replace(target + ".tmp", target)
                    main._seen = getattr(main, "_seen", set()) | {target}
            image["uri"] = target
            image["mimeType"] = "image/jpeg"
            used.add(target)
        json.dump(data, open(path, "w"), separators=(",", ":"))
    for png in glob.glob("*-textures/*.png"):
        if png not in used:
            os.remove(png)
    missing = [u for u in used if not os.path.exists(u)]
    print("TEXTURES", len(used), "missing", len(missing))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 90)
