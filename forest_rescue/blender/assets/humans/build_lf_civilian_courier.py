"""Build lf_civilian_courier (model, textures, rig, clips, LODs, GLB, meta, QA compares).
python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/humans/build_lf_civilian_courier.py [tag] [noclips]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import humans_make

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
tag = argv[0] if argv else "final"
humans_make.make("lf_civilian_courier", tag=tag, clips="noclips" not in argv, export="noexport" not in argv)
