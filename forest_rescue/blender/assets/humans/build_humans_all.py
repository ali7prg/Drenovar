"""Final build of the given humans (model+textures+compare+rig+clips+LODs+GLB+meta) and clip videos.
python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/humans/build_humans_all.py <tag> <asset>[:tag] ...
Add 'novideo' to skip the clip renders."""
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import humans_make

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
tag = argv[0]
video = "novideo" not in argv
done = []
for item in argv[1:]:
    if item == "novideo":
        continue
    asset, _, t = item.partition(":")
    try:
        r = humans_make.make(asset, tag=t or tag, clips=True, export=True)
        print("BUILT", asset, json.dumps({k: r.get(k) for k in ("iou", "tris", "bones_used")}), flush=True)
        done.append(asset)
    except Exception:
        traceback.print_exc()
        print("BUILD_FAILED", asset, flush=True)
if video:
    import qa_clips
    for asset in done:
        try:
            r = qa_clips.render_all_clips(asset)
            from frlib import core, paths
            core.write_json(paths.video(asset, "clips.json"), r)
            print("VIDEOS", asset, len(r), flush=True)
        except Exception:
            traceback.print_exc()
            print("VIDEO_FAILED", asset, flush=True)
