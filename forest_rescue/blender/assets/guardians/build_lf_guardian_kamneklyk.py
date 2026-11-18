"""Build lf_guardian_kamneklyk (model, rig, textures, LODs, clips, GLB, QA).

python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/guardians/build_lf_guardian_kamneklyk.py [--iter NN]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gpipe  # noqa: E402
import spec_kamneklyk  # noqa: E402

if __name__ == "__main__":
    gpipe.main(spec_kamneklyk)
