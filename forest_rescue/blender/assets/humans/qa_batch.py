"""Compare-only iteration for several characters in one limiter slot.
python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/humans/qa_batch.py <tag> <asset> [<asset> ...]"""
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import humans_make

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
tag = argv[0]
res = {}
for item in argv[1:]:
    asset, _, t = item.partition(":")
    try:
        r = humans_make.make(asset, tag=t or tag, clips=False, export=False)
        res[asset] = {k: r.get(k) for k in ("iou", "colour_error")}
    except Exception:
        traceback.print_exc()
        res[asset] = "FAILED"
    print("BATCH", asset, json.dumps(res[asset]), flush=True)
