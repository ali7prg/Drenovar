"""Shared constants/paths for the Ancient Maw build stages."""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(os.path.dirname(HERE))
if BLENDER_DIR not in sys.path:
    sys.path.insert(0, BLENDER_DIR)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from frlib import paths  # noqa: E402

ASSET_ID = "lf_boss_ancient_maw"
GROUP = "boss"
CACHE = os.environ.get("MAW_CACHE", os.path.join(tempfile.gettempdir(), "maw_cache"))
os.makedirs(CACHE, exist_ok=True)

HIGH_VOXEL = float(os.environ.get("MAW_VOXEL", "0.016"))
LOD_TRIS = (48000, 24000, 9000)
BODY_TRIS_LOD0 = 41500          # body share of LOD0 (rest: teeth, claws, eyes, tongue)
TEX_MASTER = 2048   # 4096 was OOM-killed on the shared 15 GB box
TEX_RUNTIME = 2048


def cache(name):
    return os.path.join(CACHE, name)


def qa_compare(name):
    return paths.compare(ASSET_ID, name)


def qa_video(name):
    return paths.video(ASSET_ID, name)
