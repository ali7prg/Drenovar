"""Reproducible from-scratch build of lf_boss_ancient_maw («Пращур»).

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/boss/build_lf_boss_ancient_maw.py [--iter NN] [--no-videos]

Stages (all deterministic; intermediates in $MAW_CACHE, default <tmp>/maw_cache):
  maw_stage_mesh   reference masks -> SDF anatomy (trunk loft, two-lobe skull/mandible, limbs, osteoderms,
                   scar ridge) smoothly trimmed by the side/front visual hull -> marching cubes (1.6 cm)
  maw_stage_rig    LOD0 decimation, region-seam UVs, detail meshes (teeth, claws, eyes, tongue), 59-bone rig,
                   part-based skin weights, LOD1/LOD2 with merged small bones
  maw_stage_tex    high->low normal bake + AO bake + multi-view colour projection + procedural scales (4096 masters)
  maw_stage_anim   13 manifest clips (procedural keys, world-planted feet)
  maw_stage_export GLB + exact clip durations + markers extras + meta.json + packed master .blend
  maw_qa           ortho compares (IoU), head close-up, keypose matches (iterNN_* images)
  maw_stage_videos side + game-camera MP4s, contact sheets, foot-slide report
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:]
it = args[args.index("--iter") + 1] if "--iter" in args else "final"
stages = ["maw_stage_mesh.py --voxel 0.016 --no-lod", "maw_stage_rig.py", "maw_stage_tex.py --size 2048 --ao-samples 24",
          "maw_stage_anim.py", "maw_stage_export.py", f"maw_qa.py --iter {it} --what compare,head,keyposes"]
if "--no-videos" not in args:
    stages.append("maw_stage_videos.py")
sys.argv = [os.path.join(HERE, "maw_pipeline.py")] + stages
runpy.run_path(os.path.join(HERE, "maw_pipeline.py"), run_name="__main__")
