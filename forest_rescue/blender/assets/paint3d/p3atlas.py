"""Shared foliage atlas (2048, RGBA) assembled from per-asset regions of painted tiles."""
import fcntl
import json
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
REGION_DIR = os.path.join(REPO, "forest_rescue", "blender", "textures", "forest", "atlas_v2")
RUNTIME = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "forest")
ATLAS = "lf_foliage_atlas.png"
SIZE = 2048

# fixed regions (x, y, w, h) in atlas pixels; tiles are scaled down automatically to fit
REGIONS = {
    # column A (x 0..1024)
    "golden_oak": (0, 0, 1024, 832),        # art/02 oak patches (hero v1)
    "oak_grove": (0, 832, 1024, 512),       # same oak patches, art/01/07 grove palette (grove variants)
    "willow": (0, 1344, 640, 512),          # art/02 willow strands (v1)
    "willow_green": (640, 1344, 384, 704),  # same strands, art/01 east-river green palette (v2/v3)
    "grass": (0, 1856, 640, 192),
    # column B (x 1024..1664)
    "oak_top": (1024, 0, 640, 384),         # hi-res art/07 rosettes: art/02-matched + original yellow
    "hollow_oak": (1024, 384, 640, 448),
    "birch": (1024, 832, 640, 576),
    "bramble": (1024, 1408, 640, 384),
    "groundcover": (1024, 1792, 640, 256),
    # column C (x 1664..2048)
    "rock_plants": (1664, 0, 384, 384),
    "dark_pine": (1664, 384, 384, 640),     # art/02 pine (hero v1)
    "pine_dark": (1664, 1024, 384, 640),    # pine tiles in the art/01 dark blue-green conifer palette
    "reed_fern": (1664, 1664, 384, 384),
}


def uv_rect(px_rect):
    """Atlas pixel rect (x0,y0,x1,y1) -> Blender UV (u0, v0_bottom, u1, v1_top)."""
    x0, y0, x1, y1 = px_rect
    return (x0 / SIZE, 1.0 - y1 / SIZE, x1 / SIZE, 1.0 - y0 / SIZE)


def save_region(key, region_img, meta=None):
    os.makedirs(REGION_DIR, exist_ok=True)
    a = (np.clip(region_img, 0, 1) * 255 + 0.5).astype(np.uint8)
    p = os.path.join(REGION_DIR, f"{key}.png")
    Image.fromarray(a, "RGBA").save(p + ".tmp.png")
    os.replace(p + ".tmp.png", p)
    if meta is not None:
        with open(os.path.join(REGION_DIR, f"{key}.json"), "w") as f:
            json.dump(meta, f)


def assemble(out_dir=RUNTIME):
    """Compose all saved regions into the shared atlas (file-locked)."""
    os.makedirs(REGION_DIR, exist_ok=True)
    lock = open(os.path.join(REGION_DIR, ".lock"), "w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        atlas = np.zeros((SIZE, SIZE, 4), np.uint8)
        for key, (x, y, w, h) in REGIONS.items():
            p = os.path.join(REGION_DIR, f"{key}.png")
            if os.path.exists(p):
                r = np.asarray(Image.open(p).convert("RGBA"))
                atlas[y:y + r.shape[0], x:x + r.shape[1]] = r[:h, :w]
        # colour-bleed into transparent texels (mip-safe): copy nearest opaque colour
        import cv2
        a = atlas[..., 3] > 8
        rgb = atlas[..., :3].astype(np.float32)
        small = rgb.copy()
        known = a.copy()
        for it in range(10):
            if known.all():
                break
            k = known.astype(np.float32)
            num = cv2.blur(small * k[..., None], (3, 3))
            den = cv2.blur(k, (3, 3))
            grow = (den > 0) & ~known
            small[grow] = num[grow] / den[grow][:, None]
            known |= grow
        atlas[..., :3] = np.clip(small, 0, 255).astype(np.uint8)
        path = os.path.join(out_dir, ATLAS)
        tmp = path + f".tmp{os.getpid()}.png"
        Image.fromarray(atlas, "RGBA").save(tmp, optimize=True)
        os.replace(tmp, path)          # atomic: readers never see a half-written atlas
        return path
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
