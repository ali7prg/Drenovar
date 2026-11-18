"""Editable Blender file of a built creature: imports <id>_lod<N>.glb into Blender 5.3 and saves one self-contained
<id>.blend (armature with every clip as an action, skinned meshes, PBR materials with their textures packed, the
idle clip active, 30 fps). The procedural scripts stay the source of truth for rebuilds; the .blend is for viewing
and hand edits.  Usage: python -I dcc_blend.py <glb> <out.blend>
"""
import os
import sys

import bpy

glb, out = sys.argv[1], sys.argv[2]
sid = os.path.basename(glb).split("_")[0]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 30
sc.render.fps_base = 1.0
bpy.ops.import_scene.gltf(filepath=glb, bone_heuristic="TEMPERANCE")
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
arm.name = f"{sid}_rig"
actions = sorted(a.name for a in bpy.data.actions)
idle = next((a for a in bpy.data.actions if a.name.startswith(f"{sid}__idle")), None)
arm.animation_data_create()
if arm.animation_data.nla_tracks:
    for t in list(arm.animation_data.nla_tracks):
        arm.animation_data.nla_tracks.remove(t)
if idle is not None:
    arm.animation_data.action = idle
    if getattr(idle, "slots", None) and len(idle.slots):
        arm.animation_data.action_slot = idle.slots[0]
    sc.frame_start, sc.frame_end = int(idle.frame_range[0]), int(idle.frame_range[1])
for a in bpy.data.actions:
    a.use_fake_user = True          # every clip is kept in the file, not only the active one
for img in bpy.data.images:
    if img.packed_file is None and img.source == "FILE":
        img.pack()
txt = bpy.data.texts.new("README")
txt.write(f"DRENOVAR creatures-v2: {sid}\n"
          f"Built by godot/art/creatures-v2 (procedural pipeline, Blender 5.3 as a Python module) and matched to\n"
          f"drenovar-server branch creature-references (manifest.json, model.png views, attack poses 01-04).\n"
          f"Units: metres, +Z up in Blender (+Y up in glTF), the creature faces +X. 30 fps.\n"
          f"Actions ({len(actions)}): {', '.join(actions)}\n"
          f"Rebuild: see godot/art/creatures-v2/README.md; edits made here are not read back by the pipeline.\n")
bpy.context.preferences.filepaths.save_version = 0      # no <name>.blend1 backup next to the file
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
print("BLEND", sid, out, os.path.getsize(out), "actions", len(actions),
      "meshes", len([o for o in bpy.data.objects if o.type == "MESH"]), "images", len(bpy.data.images))
