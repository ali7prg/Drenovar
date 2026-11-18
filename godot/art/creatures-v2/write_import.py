"""Writes the Godot import settings for a creatures-v2 runtime GLB (before the first import).
Explicit LOD1/LOD2 meshes (no generated LODs), extracted textures, 30 fps clips.
Usage: python3 write_import.py <godot/project> <species> [...]"""
import os
import sys

TEMPLATE = """[remap]

importer="scene"
importer_version=1
type="PackedScene"

[deps]

source_file="res://assets/creatures-v2/{sid}/{sid}_runtime.gltf"

[params]

nodes/root_type=""
nodes/root_name=""
nodes/root_script=null
nodes/apply_root_scale=true
nodes/root_scale=1.0
nodes/import_as_skeleton_bones=false
nodes/use_name_suffixes=false
nodes/use_node_type_suffixes=true
meshes/ensure_tangents=true
meshes/generate_lods=false
meshes/create_shadow_meshes=true
meshes/light_baking=1
meshes/lightmap_texel_size=0.2
meshes/force_disable_compression=false
skins/use_named_skins=true
animation/import=true
animation/fps=30
animation/trimming=false
animation/remove_immutable_tracks=true
animation/import_rest_as_RESET=false
import_script/path=""
materials/extract=0
materials/extract_format=0
materials/extract_path=""
_subresources={{}}
gltf/naming_version=2
gltf/embedded_image_handling=1
"""

project = sys.argv[1]
for sid in sys.argv[2:]:
    path = os.path.join(project, "assets", "creatures-v2", sid, f"{sid}_runtime.gltf.import")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(TEMPLATE.format(sid=sid))
        print("wrote", path)
