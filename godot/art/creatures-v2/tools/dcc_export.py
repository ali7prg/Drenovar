"""Editable DCC sources from a built creature: imports <id>_lod0.glb into Blender 5.3 and saves
<id>.blend (armature, meshes, materials, one action per clip; textures unpacked next to it) and
<id>.fbx (all clips baked). The procedural scripts stay the source of truth for rebuilds.
Usage: python -I dcc_export.py <glb> <out-dir>
"""
import os
import sys

import bpy

glb, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
sid = os.path.basename(glb).split("_")[0]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb, import_shading="NORMALS", bone_heuristic="TEMPERANCE")
actions = sorted(a.name for a in bpy.data.actions)
tex_dir = os.path.join(out, f"{sid}_blend_textures")
os.makedirs(tex_dir, exist_ok=True)
for img in bpy.data.images:
    if img.packed_file is not None:
        name = bpy.path.clean_name(img.name) + (".png" if img.file_format == "PNG" else ".jpg")
        img.filepath_raw = os.path.join(tex_dir, name)
        img.save()
        img.unpack(method="REMOVE") if img.packed_file else None
        img.filepath = "//" + os.path.relpath(os.path.join(tex_dir, name), out)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, f"{sid}.blend"), relative_remap=True, compress=True)
bpy.ops.export_scene.fbx(filepath=os.path.join(out, f"{sid}.fbx"), use_selection=False, bake_anim=True,
                         bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False, add_leaf_bones=False,
                         path_mode="RELATIVE", embed_textures=False)
print("DCC", sid, "actions", len(actions), "meshes", len([o for o in bpy.data.objects if o.type == "MESH"]),
      "armatures", len([o for o in bpy.data.objects if o.type == "ARMATURE"]))
