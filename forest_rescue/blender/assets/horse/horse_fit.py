"""Fast silhouette check of the SDF body (no Blender): field -> 2-D silhouettes -> IoU overlays.

Usage: /opt/tools/blender-venv/bin/python horse_fit.py <out_dir> [voxel]
"""
import os
import sys
import time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import horse_refs as HR  # noqa: E402
import horse_body as HB  # noqa: E402
from frlib import sdf  # noqa: E402

LO = np.array([-0.46, -1.62, -0.01])
HI = np.array([0.46, 1.02, 2.10])


def build_field(voxel, parts, carves=(), proxies=()):
    F = sdf.Field(LO, HI, voxel)
    for p in parts:
        F.apply(p)
    for c in carves:
        F.apply(c, op="subtract")
    for p in proxies:
        F.apply(p, op="union", k=0.0)
    return F


def silhouettes(F):
    inside = F.d < 0
    side = inside.any(axis=0)      # (nY, nZ)
    front = inside.any(axis=1)     # (nX, nZ)
    v = F.voxel
    lo = F.lo
    hiY = lo[1] + (F.n[1] - 1) * v
    hiX = lo[0] + (F.n[0] - 1) * v
    return {
        "left": (side, (lo[1], lo[2])),
        "right": (side[::-1], (-hiY, lo[2])),
        "front": (front, (lo[0], lo[2])),
        "rear": (front[::-1], (-hiX, lo[2])),
    }


def overlay(view, rmask):
    ref = view.mask
    H, W = ref.shape
    im = (view.image * 0.45 + 0.5).clip(0, 1)
    both = ref & rmask
    im[both] = im[both] * 0.4 + np.array([0.2, 0.6, 0.2]) * 0.6
    im[ref & ~rmask] = (0.9, 0.15, 0.15)
    im[~ref & rmask] = (0.15, 0.3, 0.95)
    return im


def run(out_dir, voxel=0.012, with_proxies=True):
    os.makedirs(out_dir, exist_ok=True)
    t = time.time()
    views = HR.load_views()
    J = HB.skeleton()
    F = build_field(voxel, HB.body_parts(J), HB.carve_parts(J),
                    HB.hair_proxies(J) if with_proxies else ())
    sil = silhouettes(F)
    panels = []
    scores = {}
    for name in ("left", "front", "rear", "right"):
        v = views[name]
        s2, lo2 = sil[name]
        rm = HR.render_field_mask(v, s2, lo2, voxel)
        inter = (rm & v.mask).sum()
        uni = (rm | v.mask).sum()
        scores[name] = inter / uni
        panels.append(overlay(v, rm))
    H = max(p.shape[0] for p in panels)
    sheet = np.concatenate([np.pad(p, ((0, H - p.shape[0]), (0, 4), (0, 0)), constant_values=1)
                            for p in panels], axis=1)
    Image.fromarray((sheet * 255).astype(np.uint8)).save(os.path.join(out_dir, "fit.png"))
    print("IoU", {k: round(float(v), 4) for k, v in scores.items()}, f"{time.time() - t:.1f}s")
    return F, scores


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/horse_fit"
    vox = float(sys.argv[2]) if len(sys.argv) > 2 else 0.012
    run(out, vox)


def runs_table(view, rmask, zs=None, axis="rows"):
    """Print metric extents of reference vs model per height (rows) for quick tuning."""
    def runs(row):
        r = np.concatenate([[0], row.astype(int), [0]])
        d = np.diff(r)
        return list(zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]))
    zs = zs if zs is not None else np.arange(0.05, 2.06, 0.05)
    for z in zs:
        r = int(round(view.ay - z * view.ppm))
        if r < 0 or r >= view.mask.shape[0]:
            continue
        f = lambda c: (c - view.ax) / view.ppm  # noqa: E731
        a = " ".join(f"[{f(s):+.2f},{f(e):+.2f}]" for s, e in runs(view.mask[r]))
        b = " ".join(f"[{f(s):+.2f},{f(e):+.2f}]" for s, e in runs(rmask[r]))
        print(f"z={z:4.2f} ref {a:60s} | mdl {b}")


def mirrored_partner(views, name):
    """Partner view mask mirrored into `name`'s pixel grid (left<->right, front<->rear)."""
    partner = {"left": "right", "right": "left", "front": "rear", "rear": "front"}[name]
    a, b = views[name], views[partner]
    H, W = a.mask.shape
    out = np.zeros((H, W), bool)
    # world coordinate along a.right of column u: (u - a.ax)/ppm; partner.right = -a.right
    u = np.arange(W)
    ub = np.round(b.ax - (u - a.ax) * b.ppm / a.ppm).astype(int)
    ok = (ub >= 0) & (ub < b.mask.shape[1])
    out[:, ok] = b.mask[:H, ub[ok]]
    return out


def hull_views(views, mode="consensus"):
    """Views used for hull carving. consensus = union of each view and its mirrored partner."""
    import copy
    if mode == "primary":
        return [views["left"], views["front"]]
    if mode == "all":
        return [views[k] for k in ("left", "right", "front", "rear")]
    out = []
    for k in ("left", "front"):
        v = copy.copy(views[k])
        v.mask = views[k].mask | mirrored_partner(views, k)
        out.append(v)
    return out


def run_hull(out_dir, voxel=0.012, mode="consensus", k=0.015):
    os.makedirs(out_dir, exist_ok=True)
    views = HR.load_views()
    J = HB.skeleton()
    F = build_field(voxel, HB.body_parts(J), HB.carve_parts(J))
    if mode != "none":
        F.intersect(sdf.hull_sdf(F, hull_views(views, mode), dilate_px=1.0), k=k)
    for p in HB.hair_proxies(J):
        F.apply(p, op="union", k=0.0)
    sil = silhouettes(F)
    scores = {}
    panels = []
    for name in ("left", "front", "rear", "right"):
        v = views[name]
        s2, lo2 = sil[name]
        rm = HR.render_field_mask(v, s2, lo2, voxel)
        scores[name] = (rm & v.mask).sum() / (rm | v.mask).sum()
        panels.append(overlay(v, rm))
    H = max(p.shape[0] for p in panels)
    sheet = np.concatenate([np.pad(p, ((0, H - p.shape[0]), (0, 4), (0, 0)), constant_values=1)
                            for p in panels], axis=1)
    Image.fromarray((sheet * 255).astype(np.uint8)).save(os.path.join(out_dir, f"fit_hull_{mode}.png"))
    print(mode, "IoU", {kk: round(float(vv), 4) for kk, vv in scores.items()})
    return F, scores
