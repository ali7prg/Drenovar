#!/usr/bin/env python3
"""Deduplicate full-resolution images and losslessly compress all glTF buffers.

The original float32 positions, normals, UVs, colors and tangents are kept exactly.
Each compressed buffer is immediately decoded and compared byte for byte.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import unquote
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ASSETS = ROOT / "godot/project/assets/city/architecture-v6"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="optional existing runtime type, e.g. ECO-05")
    args = parser.parse_args()
    stage = ASSETS / "web-staging"
    target = ASSETS / "web"
    textures = ASSETS / "materials"
    target.mkdir(exist_ok=True)
    textures.mkdir(exist_ok=True)
    # These PNGs serve the browser. Native uses original architecture-v2 materials.
    (textures / ".gdignore").write_text("# Web PBR textures; native uses original surfaces07.\n")
    if not (HERE / "node_modules/meshoptimizer/meshopt_encoder.js").exists():
        raise SystemExit("Run npm ci in godot/art/buildings-v6 first")
    for source, name in [("meshopt_decoder.mjs", "meshopt_decoder.mjs"), ("LICENSE.md", "MESHOPTIMIZER-LICENSE.md")]:
        shutil.copyfile(HERE / "node_modules/meshoptimizer" / source, target / name)
    shutil.copyfile(HERE / "material_compat.mjs", target / "material_compat.mjs")
    manifest_name = "manifest.json"
    if args.only and (ASSETS / f"manifest-{args.only}.json").exists():
        manifest_name = f"manifest-{args.only}.json"
    manifest = json.loads((ASSETS / manifest_name).read_text())
    report = []
    used_images = set()
    converted_albedos = set()
    source_by_name = {}
    provenance = {}
    groups = dict(manifest["levels"])
    groups.update({unit_id:{"unit":row} for unit_id,row in manifest.get("units", {}).items()})
    for type_id, levels in groups.items():
        if args.only and type_id != args.only:
            continue
        for level in levels:
            key = type_id if level == "unit" else f"{type_id}-{level}"
            source = stage / f"{key}.gltf"
            doc = json.loads(source.read_text())
            # Godot 4.6 glTF writes unnamed JPEG albedos to the same textures/.png.
            # Resolve original material resources instead of publishing that export bug.
            material_names = levels[level]["materials"]
            if len(doc["materials"]) != len(material_names):
                raise AssertionError(f"{key}: glTF/native material order must stay one-to-one")
            for index, name in enumerate(material_names):
                mat = doc["materials"][index]
                mat["name"] = name
                pbr = mat.get("pbrMetallicRoughness", {})
                native_color = pbr.get("baseColorFactor", [1.0, 1.0, 1.0, 1.0])
                if any(component > 1.0 for component in native_color):
                    # glTF restricts baseColorFactor to [0,1]; Godot deliberately
                    # uses brighter oak/plank/drill tints. Preserve the precise
                    # linear factor for the web loader to restore, never discard it.
                    mat.setdefault("extras", {})["drenovarNativeBaseColor"] = native_color
                    pbr["baseColorFactor"] = [min(1.0, component) for component in native_color]
                if "baseColorTexture" not in pbr:
                    continue
                material_path = ASSETS.parent / "architecture-v2/materials" / (name + ".tres")
                material_text = material_path.read_text()
                resource_id = re.search(r'albedo_texture = ExtResource\("([^"]+)"\)', material_text).group(1)
                ext = re.search(r'\[ext_resource[^\n]+path="([^"]+)"[^\n]+id="' + re.escape(resource_id) + r'"\]', material_text)
                original = ROOT / "godot/project" / ext.group(1).removeprefix("res://")
                repaired = stage / "textures" / (original.stem + "-source.png")
                if original not in converted_albedos:
                    with Image.open(original) as image:
                        image.save(repaired)
                    converted_albedos.add(original)
                source_by_name[repaired.name] = original
                tex = doc["textures"][pbr["baseColorTexture"]["index"]]
                doc["images"][tex["source"]]["uri"] = "textures/" + repaired.name
            for image in doc.get("images", []):
                image_source = stage / unquote(image["uri"])
                # Prefer the exact native source when the stock-export staging area
                # still contains an older synthesized ORM or recompressed normal.
                native_source = ROOT / "godot/project/assets/city/premium/surfaces07" / image_source.name
                if image_source.name not in source_by_name and native_source.is_file():
                    image_source = native_source
                content = image_source.read_bytes()
                digest = hashlib.sha256(content).hexdigest()[:24]
                suffix = image_source.suffix or ".png"
                filename = digest + suffix
                image_target = textures / filename
                if not image_target.exists():
                    image_target.write_bytes(content)
                used_images.add(filename)
                original_texture = source_by_name.get(image_source.name)
                if original_texture is None:
                    candidate = ROOT / "godot/project/assets/city/premium/surfaces07" / image_source.name
                    if candidate.is_file():
                        original_texture = candidate
                if original_texture and filename not in provenance:
                    with Image.open(original_texture) as src, Image.open(image_target) as dst:
                        source_pixels = src.convert("RGBA").tobytes()
                        target_pixels = dst.convert("RGBA").tobytes()
                        assert src.size == dst.size and source_pixels == target_pixels, f"Texture quality changed: {original_texture}"
                        provenance[filename] = {"source":str(original_texture.relative_to(ROOT)),
                                                "source_sha256":hashlib.sha256(original_texture.read_bytes()).hexdigest(),
                                                "dimensions":list(src.size),
                                                "pixel_sha256":hashlib.sha256(source_pixels).hexdigest(),
                                                "same_pixels":True}
                image["uri"] = "../materials/" + filename
            prepared = stage / f"{key}-shared.gltf"
            prepared.write_text(json.dumps(doc, separators=(",", ":")) + "\n")
            output = target / f"{key}.glb"
            command = ["node", str(HERE / "compress_glb.mjs"), str(prepared), str(output)]
            completed = subprocess.run(command, capture_output=True, text=True)
            if completed.returncode:
                raise RuntimeError(f"{key}: {completed.stderr}")
            before = sum((stage / unquote(b["uri"])).stat().st_size for b in doc["buffers"])
            after = output.stat().st_size
            report.append({"key":key,"kind":"unit" if level == "unit" else "building", "raw_geometry_bytes":before, "compressed_glb_bytes":after,
                           "sha256":hashlib.sha256(output.read_bytes()).hexdigest()})
            print(f"WEB {key} {before} -> {after} bytes", flush=True)
    if not args.only:
        for unused in textures.iterdir():
            if unused.is_file() and unused.name != ".gdignore" and unused.name not in used_images:
                unused.unlink()
    result = {"version":"DRENOVAR-V6-C1.0-ART1", "states":sum(r["kind"] == "building" for r in report),
              "units":sum(r["kind"] == "unit" for r in report),"models":len(report),
              "method":"MeshoptEncoder 1.3.0, version0 codec, no filters; byte-for-byte decoder roundtrip",
              "quantization":False,"simplification":False,"texture_resizing":False,
              "decoder":"Three.js GLTFLoader.setMeshoptDecoder(MeshoptDecoder)",
              "material_compat":"restoreNativeMaterialProperties(gltf.scene) restores original HDR albedo factors from extras",
              "shared_texture_files":len(list(textures.glob("*.png"))),
              "shared_texture_bytes":sum(p.stat().st_size for p in textures.glob("*.png")),
              "raw_geometry_bytes":sum(r["raw_geometry_bytes"] for r in report),
              "compressed_geometry_bytes":sum(r["compressed_glb_bytes"] for r in report),
              "files":report}
    (ASSETS / ("web-pack-report.json" if not args.only else f"web-pack-report-{args.only}.json")).write_text(json.dumps(result,indent=2)+"\n")
    if not args.only:
        (ASSETS / "texture-provenance.json").write_text(json.dumps({"status":"passed","textures":provenance},indent=2)+"\n")


if __name__ == "__main__":
    main()
