# Forest (0.6.0, build 24)

Procedural trees for the city and the world map. No external art; everything is generated.

1. `python3 foliage_atlas.py ../../project/assets/environment/forest60.png` — needle sprigs, pine tufts,
   oak and birch leaf clusters, crown cap, two barks (2048x1024, dilated colour, hardened alpha).
2. `python3 trees.py ../../project/assets/city/forest60 ../../environment/forest60.png` — city variants
   0 Scots pine, 1 spruce, 2 tall pine, 3 oak, 4 birch, 5 lime; near and mid LOD as alpha-tested cards
   with volume normals and baked AO.
3. Bake impostors (needs a renderer):
   `xvfb-run godot --rendering-driver opengl3 --path ../../project -s ../art/forest/bake_impostors.gd -- $PWD/../../project/assets/environment/forest60-far.png`
   (copy the script into the project first if Godot refuses a path outside it).
4. Run step 2 again: far LOD becomes 3 crossed side views + 1 top view (16 triangles).
5. `python3 trees.py world ../../project/assets/game.json ../../project/assets/world-scenery/forest60 ../../environment/forest60.png`
   — world species: card crown near, impostor far, scaled by each species' canopy scale.

Import settings: `meshes/generate_lods=false` for every forest60 .glb (Godot's automatic LOD collapses
cards into spikes; that is what made the 0.5.9 trees look like blobs), atlases VRAM-compressed with
mipmaps (`tools/texture_import_policy.py`).
