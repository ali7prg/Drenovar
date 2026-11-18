"""frlib — shared Blender (bpy 5.x) production pipeline for DRENOVAR «Лес потерянных».

Modules
-------
paths    repository locations (delivery art, sources, runtime GLB output, QA output)
core     scene reset, numpy->mesh, materials, LOD decimation, GLB export, stats
refs     reference-sheet crops, background removal -> silhouette masks, view mapping
sdf      numpy signed-distance modelling, visual hull carving, marching cubes
texproj  multi-view projection texturing from orthographic reference views
rig      armature construction, part-based skin weights, IK rigs and baking
render   matched reference renders, side-by-side comparison with IoU, clip videos

Conventions (see forest_rescue/blender/CONVENTIONS.md):
Blender Z-up, metres, character forward = -Y (exports to glTF +Z forward, +Y up).
"""
