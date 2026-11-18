"""Stage 4: author all 13 boss clips onto the rig (reads maw_tex.blend, writes maw_anim.blend).

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/boss/maw_stage_anim.py [--only id,id]
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maw_common as C  # noqa: E402
import bpy  # noqa: E402

import maw_anim as A  # noqa: E402

AID = C.ASSET_ID


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--src", default=C.cache("maw_tex.blend"))
    args = ap.parse_args(sys.argv[1:])
    bpy.ops.wm.open_mainfile(filepath=args.src)
    bpy.context.scene.render.fps = A.FPS
    arm = bpy.data.objects[f"{AID}_rig"]
    ids = args.only.split(",") if args.only else list(A.MANIFEST)
    for cid in ids:
        t0 = time.time()
        D, loop, _m = A.MANIFEST[cid]
        ts, frames = A.author_frames(arm, cid)
        A.write_clip(arm, cid, ts, frames, loop)
        print(f"[maw_anim] {cid} {D}s frames={len(ts)} {time.time() - t0:.1f}s", flush=True)
    arm.animation_data.action = bpy.data.actions["lf_boss_idle"] if "lf_boss_idle" in bpy.data.actions else None
    bpy.ops.wm.save_as_mainfile(filepath=C.cache("maw_anim.blend"), compress=True)
    print("[maw_anim] saved", flush=True)


if __name__ == "__main__":
    main()
