"""Merge the per-panel key-pose fits (best IoU of every run) into cache/keypose_fit.json + a fit sheet.
python mv2_posefit_merge.py <cache_dir> <out_png> [older_run_dir ...]"""
import glob
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mv2_refs as R  # noqa: E402

cache, out_png = sys.argv[1], sys.argv[2]
dirs = [cache] + sys.argv[3:]
best = {}
for d in dirs:
    for f in glob.glob(os.path.join(d, "keypose_fit_*.json")):
        if f.endswith("keypose_fit.json"):
            continue
        r = json.load(open(f))
        p = r["panel"]
        if p not in best or r["iou"] > best[p]["iou"]:
            r["_mask"] = os.path.join(d, f"keypose_fit_{p}_mask.npy")
            best[p] = r
json.dump({k: {kk: vv for kk, vv in v.items() if kk != "_mask"} for k, v in best.items()},
          open(os.path.join(cache, "keypose_fit.json"), "w"), indent=2)
order = list(R.KEYPOSE_PANELS)
tiles = []
for p in order:
    if p not in best:
        continue
    img = R.keypose_panel(p)
    ref = R.keypose_mask(img)
    mpath = best[p]["_mask"]
    m = np.load(mpath) if os.path.exists(mpath) else np.zeros_like(ref)
    ov = img.copy()
    ov[m & ~ref] = ov[m & ~ref] * 0.3 + np.array([0.15, 0.3, 0.9]) * 0.7
    ov[ref & ~m] = ov[ref & ~m] * 0.3 + np.array([0.85, 0.15, 0.15]) * 0.7
    ov[ref & m] = ov[ref & m] * 0.6 + np.array([0.15, 0.55, 0.15]) * 0.4
    a = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((360, 230))
    b = Image.fromarray((np.clip(ov, 0, 1) * 255).astype(np.uint8)).resize((360, 230))
    t = Image.new("RGB", (726, 230), (25, 25, 25))
    t.paste(a, (0, 0))
    t.paste(b, (366, 0))
    d = ImageDraw.Draw(t)
    d.rectangle([3, 3, 330, 18], fill=(20, 20, 20))
    d.text((6, 5), f"{p}: fitted pose IoU {best[p]['iou']:.3f}", fill=(255, 240, 200))
    tiles.append(t)
cols = 2
rows = (len(tiles) + 1) // cols
sheet = Image.new("RGB", (726 * cols + 8, 236 * rows), (25, 25, 25))
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % cols) * 734, (i // cols) * 236))
sheet.save(out_png)
print("MERGED", json.dumps({k: round(v["iou"], 3) for k, v in best.items()}))
