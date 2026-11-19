"""Run several Ancient Maw v2 stages in ONE Blender process (one limiter slot).

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/boss/v2/mv2_pipeline.py \
    mv2_stage_mesh.py mv2_stage_rig.py "mv2_preview.py <blend> <png> rest"
"""
import os
import runpy
import shlex
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for cmd in sys.argv[1:]:
    parts = shlex.split(cmd)
    t0 = time.time()
    print(f"[pipeline] >>> {cmd}", flush=True)
    sys.argv = [os.path.join(HERE, parts[0])] + parts[1:]
    runpy.run_path(os.path.join(HERE, parts[0]), run_name="__main__")
    print(f"[pipeline] <<< {parts[0]} {time.time() - t0:.1f}s", flush=True)
