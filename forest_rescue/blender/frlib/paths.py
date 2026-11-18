"""Repository paths used by every asset build script."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(HERE)                      # forest_rescue/blender
FR_DIR = os.path.dirname(BLENDER_DIR)                    # forest_rescue
REPO = os.path.dirname(FR_DIR)                           # repository root
DELIVERY = os.path.join(FR_DIR, "delivery")
ART = os.path.join(DELIVERY, "art")
DATA = os.path.join(DELIVERY, "data")
SOURCES = os.path.join(BLENDER_DIR, "sources")           # editable .blend masters
TEXTURE_SOURCES = os.path.join(BLENDER_DIR, "textures")  # full-resolution texture masters
QA = os.path.join(FR_DIR, "qa")
QA_COMPARE = os.path.join(QA, "compare")
QA_VIDEO = os.path.join(QA, "video")
GODOT_PROJECT = os.path.join(REPO, "godot", "project")
RUNTIME = os.path.join(GODOT_PROJECT, "assets", "forest_rescue")  # optimized game GLBs


def art(name):
    return os.path.join(ART, name)


def ensure(*parts):
    path = os.path.join(*parts)
    os.makedirs(path, exist_ok=True)
    return path


def runtime(group, name):
    return os.path.join(ensure(RUNTIME, group), name)


def source(group, name):
    return os.path.join(ensure(SOURCES, group), name)


def texture_master(group, name):
    return os.path.join(ensure(TEXTURE_SOURCES, group), name)


def compare(asset_id, name):
    return os.path.join(ensure(QA_COMPARE, asset_id), name)


def video(asset_id, name):
    return os.path.join(ensure(QA_VIDEO, asset_id), name)
