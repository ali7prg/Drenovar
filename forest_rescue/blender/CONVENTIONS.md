# «Лес потерянных» — 3D production conventions (all asset builders)

## Tools
* Blender 5.3 as a Python module: `/opt/tools/blender-venv/bin/python` (also numpy, scipy,
  scikit-image, opencv, Pillow, trimesh). Run heavy builds through the global limiter:
  `python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/<group>/build_x.py`
  (max 3 concurrent jobs across all agents, runs under Xvfb so Cycles/EEVEE/Workbench work).
* Shared library `forest_rescue/blender/frlib` (read `frlib/__init__.py` docstrings):
  `refs` (reference crops → silhouette masks → orthographic `View`), `sdf` (round cones,
  ellipsoids, boxes, smooth CSG, **visual-hull carving**, marching cubes, part-based skin
  weights), `texproj` (UV rasterizer, per-view z-buffer, projection of reference colours onto
  texels, pull-push fill, de-lighting, 3-D noise/voronoi, height→normal), `rig` (armature,
  bind, IK helpers, `capture_pose`/`write_action` dense clip writing, gait helpers), `render`
  (studio, ortho camera matching a `View`, `compare` → [reference | render | IoU diff] PNG +
  JSON, `render_clip` → MP4), `core` (mesh from numpy, materials wired for glTF, Cycles bake,
  decimate LODs, `export_glb`, `save_blend`).
* In-engine check (Godot 4.6.3 Mobile renderer, same as the game):
  `forest_rescue/tools/godot_view.sh <file.glb> shots <out_dir>` (6 yaw screenshots) and
  `forest_rescue/tools/godot_view.sh <file.glb> clip <out.mp4> <anim|all> <seconds>`.
  The script copies a private viewer project, so parallel use is safe. Never run Godot
  imports inside `godot/project` yourself (the integration agent owns that project cache).
* Pilot finding: a pure visual hull matches orthographic silhouettes (IoU≈0.98) but is boxy
  in 3/4 views. Build anatomy from rounded part SDFs (round cones/ellipsoids per bone) and
  only *smoothly intersect* with the hull (`Field.intersect(hull_sdf, k)`) to lock the
  silhouette. Clip reference masks at the ground line (`clip_below`) so painted ground
  shadows never become geometry. Model thin/detached details (manes, tails as hair cards,
  halters, straps, ribbons, teeth, claws, horns, antlers, belts, buckles, bags, hoods,
  weapons, rivets, hinges) as separate meshes, not via the hull.

## Axes, units, scale
* Blender Z-up, metres. Creatures/characters face **-Y** (exports to glTF +Z forward, +Y up).
  Feet/hooves on Z=0, root bone at the origin. Real-world sizes: adult human 1.70–1.85 m,
  horse (draft cob) withers ≈1.60 m, Ancient Maw 8.0 m long / hip 2.8 m / head 3.6 m, cages
  ≈2.6–3.2 m wide (must hold 3 people), bridge deck 27 × 4 m at structural height 1.1 m.
* Pivots at real rotation axes (door hinge, winch drum axle, lever pivot, socket centre).

## Naming & outputs (per asset id from `delivery/data/asset-production-plan.json`)
* Build script: `forest_rescue/blender/assets/<group>/build_<asset>.py` (reproducible from
  scratch; deterministic seeds). Group folders: `horse`, `boss`, `humans`, `props`,
  `forest`, `landmarks`, `arena`, `guardians`.
* Editable master: `forest_rescue/blender/sources/<group>/<asset_id>.blend` (packed textures,
  high-quality mesh + rig + all actions + LODs). Full-res texture masters:
  `forest_rescue/blender/textures/<group>/`.
* Game GLB: `godot/project/assets/forest_rescue/<group>/<asset_id>.glb` (embedded
  textures, JPEG for colour where no alpha, PNG for alpha/normal; mobile sizes 2048/1024/512
  by screen size). Mesh objects `<asset_id>_LOD0`, `_LOD1`, `_LOD2` (same materials/armature);
  armature `<asset_id>_rig`; actions named exactly as the clip ids in
  `delivery/data/animation_manifest.json` (e.g. `lf_horse_walk`; guardians use
  `Idle/Walk/Alert/Attack/Hit/Roar/Death`). Clips in place; loops have identical first/last
  frame; 30 fps.
* Sidecar `godot/project/assets/forest_rescue/<group>/<asset_id>.meta.json`:
  `{id, tris:{LOD0,LOD1,LOD2}, bones, materials, textures:{name:size}, bounds_m,
  clips:{id:{seconds, loop, groundSpeed_mps (locomotion), strideLength_m, markers:{name:sec}}},
  sockets:{name:[x,y,z]} (e.g. hand_r, key_slot, hinge, door_open_deg), notes}`.
* Budgets (animation_manifest): horse LOD0/1/2 16k/8k/3.2k tris, ≤64/38/24 deform bones;
  human soldier 14k/7k/2.5k, civilian 12k/6k/2.2k, ≤52 bones; guardian 18k/9k/3.5k ≤46 bones;
  boss 48k/24k/9k ≤80 bones; max 4 influences. Environment: whole visible forest ≤110k tris,
  so tree LOD0 ≈1.5–4k tris with alpha-tested leaf cards (shared atlas, alphaCutoff 0.5),
  LOD1 ≈40%, LOD2/impostor-card ≤300 tris; at least 3 silhouette variants per tree species.

## Quality bar and verification (mandatory, iterate until good)
1. Match the reference sheets: silhouettes, proportions, colours, materials and small
   details. For every orthographic/turnaround view render the model with
   `render.camera_for_view(view)` and `render.compare(...)` →
   `forest_rescue/qa/compare/<asset_id>/<view>.png/.json`. Target IoU ≥ 0.90 for clean
   orthographic views (state the real number). For 3/4 illustrations, pose a camera that
   reproduces the drawing angle and save a side-by-side. Look at every comparison image
   yourself, fix discrepancies, repeat.
2. Colour: use `texproj.project` from all available views (plus de-lighting) for painted
   colour fidelity, procedural PBR (roughness/normal) for material response. Bake to images
   (glTF cannot carry procedural nodes). Linear roughness/normal, sRGB colour.
3. Animation: real armature + skin weights (≤4 influences), natural motion: foot/hoof
   contacts without sliding (stride = groundSpeed × cycle), weight shift, follow-through on
   tails/manes/cloth, crossfade-friendly start/end poses. Render every clip to MP4 in
   `forest_rescue/qa/video/<asset_id>/<clip>.mp4` (Blender `render.render_clip` and/or
   in-engine `godot_view.sh ... clip`), make a contact sheet PNG, inspect it, fix, repeat.
4. Export GLB, check it in the Godot viewer (shots + clip), record triangle counts in meta.
5. Write `forest_rescue/qa/compare/<asset_id>/REPORT.md`: what matches, measured IoU/colour
   error per view, known deviations (honest), and the commands to rebuild.

Never substitute flat image planes for characters/trees/props (leaf/hair cards on real
branch/hair geometry are fine). Never claim a check you did not run.
