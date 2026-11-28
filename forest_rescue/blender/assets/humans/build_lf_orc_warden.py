"""Build lf_orc_warden (orc captor of a forest cage) from scratch, deterministically.

    python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/humans/build_lf_orc_warden.py \
        [--stage geo|full] [--iter N] [--novideo]

geo : authored SDF body + garments/gear/staff (orc_geo), skinned pieces, UV atlas, Cycles AO bake, painted
      2048 atlas (orc_tex), QA stills in forest_rescue/qa/compare/lf_orc_warden/iterNN_*.png
rig : resume `full` from the cached pre-rig scene of the last geo/full run (clip iteration only)
full: geo + shared `human_shared` rig (hv2_rig), 10 clips (orc_clips), LOD1/LOD2, GLB + meta.json in
      godot/project/assets/forest_rescue/humans/, .blend master, clip videos + contact sheets.

No reference art exists for this character: no reference projection / IoU compare (see REPORT.md).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "v2"))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

import numpy as np  # noqa: E402

from frlib import core  # noqa: E402
import orc_build as OB  # noqa: E402
import orc_geo as G  # noqa: E402
import orc_qa as OQ  # noqa: E402
import spec_lf_orc_warden as SP  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
STAGE = ARGS[ARGS.index("--stage") + 1] if "--stage" in ARGS else "full"
ITER = int(ARGS[ARGS.index("--iter") + 1]) if "--iter" in ARGS else 1
VIDEO = "--novideo" not in ARGS


CACHE = os.path.join(__import__("tempfile").gettempdir(), f"{SP.ID}_prerig_cache")   # iteration cache, outside the repo


def resume():
    import pickle
    import bpy
    import orc_rig
    bpy.ops.wm.open_mainfile(filepath=os.path.join(CACHE, "prerig.blend"))
    with open(os.path.join(CACHE, "info.pkl"), "rb") as f:
        info, jpg = pickle.load(f)
    lo0 = bpy.data.objects[f"{SP.ID}_LOD0"]
    orc_rig.finish(lo0, info, jpg, ITER, video=VIDEO)


def cache(info, jpg):
    import pickle
    import bpy
    os.makedirs(CACHE, exist_ok=True)
    keep = {k: v for k, v in info.items() if k not in ("parts", "prof")}
    with open(os.path.join(CACHE, "info.pkl"), "wb") as f:
        pickle.dump((keep, jpg), f)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(CACHE, "prerig.blend"), copy=True)


def main():
    if STAGE == "rig":
        return resume()
    core.reset(fps=30)
    objs, info = OB.build()
    lo0 = OB.join(objs)
    OB.log("LOD0 joined", core.tri_count(lo0), "tris")
    OB.uv_layout(lo0)
    ao = OB.bake_ao(lo0)
    OB.log("AO baked")
    img = OB.paint_atlas(lo0, info, ao)
    master, jpg = OB.save_atlas(img)
    OB.log("atlas", master)
    qmats = OB.qa_materials(master)
    OB.assign(lo0, qmats)

    def q(n):
        return OQ.qa_path(f"iter{ITER:02d}_{n}.png")
    OQ.turnaround(q("turnaround_rest"), f"{SP.ID} iter{ITER:02d} rest pose, painted look (albedo x mix(1, lambert, 0.4))")
    clay = OB.clay_material()
    OQ.with_material([lo0], clay, lambda: OQ.turnaround(q("clay_rest"), f"{SP.ID} iter{ITER:02d} clay (geometry)"))
    o, s = G.head_frame()
    head_c = o + np.array([0.0, 0.0, -0.035])
    OQ.face(q("face"), f"{SP.ID} iter{ITER:02d} face", head_c)
    OQ.with_material([lo0], clay, lambda: OQ.face(q("face_clay"), f"{SP.ID} iter{ITER:02d} face clay", head_c))
    OB.log("QA stills written")
    cache(info, jpg)
    if STAGE == "full":
        import orc_rig
        orc_rig.finish(lo0, info, jpg, ITER, video=VIDEO)


if __name__ == "__main__":
    main()
