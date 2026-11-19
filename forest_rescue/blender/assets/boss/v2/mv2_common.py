"""Shared paths/constants for the Ancient Maw v2 stages."""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for p in (BLENDER_DIR, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from frlib import paths  # noqa: E402

ASSET_ID = "lf_boss_ancient_maw"
GROUP = "boss"
CACHE = os.environ.get("MAW2_CACHE", os.path.join(tempfile.gettempdir(), "maw2_cache"))
os.makedirs(CACHE, exist_ok=True)
VOXEL = float(os.environ.get("MAW2_VOXEL", "0.016"))
LOD_TRIS = (48000, 24000, 9000)
BODY_TRIS = (41000, 21200, 8000)
TEX = 2048
ITER = os.environ.get("MAW2_ITER", "01")


def cache(name):
    return os.path.join(CACHE, name)


def qa(name):
    return paths.compare(ASSET_ID, f"v2_iter{ITER}_{name}")


def qa_video(name):
    return paths.video(ASSET_ID, name)


def log(*a):
    print("[maw2]", *a, flush=True)
