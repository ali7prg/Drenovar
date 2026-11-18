"""Build all shared forest textures (deterministic).

Outputs (runtime, referenced by relative URI from every forest GLB):
  godot/project/assets/forest_rescue/forest/lf_foliage_atlas.png   2048² RGBA (alpha-tested cards)
  godot/project/assets/forest_rescue/forest/lf_bark_<kind>_{c.jpg,n.png,r.png}  1024² (kind: oak, pine,
      birch, hollow, willow, limestone)
Masters: forest_rescue/blender/textures/forest/ (same files + 16-bit height maps).
QA: forest_rescue/qa/compare/forest_bark/iterNN_swatches.png (+ json colour stats).

Run: python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/forest/build_textures.py [--iter N]
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
import ftex  # noqa: E402
import atlas  # noqa: E402
from frlib import paths  # noqa: E402

RUNTIME = paths.ensure(paths.RUNTIME, "forest")
MASTER = paths.ensure(paths.TEXTURE_SOURCES, "forest")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=int, default=1)
    ap.add_argument("--skip-atlas", action="store_true")
    a = ap.parse_args(sys.argv[1:] if "--" not in sys.argv else sys.argv[sys.argv.index("--") + 1:])
    t0 = time.time()
    stats = {}
    barks = {}
    import swatch
    for kind in list(ftex.BARKS) + ["limestone"]:
        if kind in ftex.BARK_SWATCH:
            alb, nrm, rough, hgt = swatch.bark_from_swatch(kind, 1024)       # painted art/02 swatch, quilted
            ref = ftex.load_swatch(kind)
            m1, s1 = ftex.colour_stats(ref)
            m2, s2 = ftex.colour_stats(alb)
            stats[kind] = {"ref_lab_mean": np.round(m1, 2).tolist(), "ref_lab_std": np.round(s1, 2).tolist(),
                           "tex_lab_mean": np.round(m2, 2).tolist(), "tex_lab_std": np.round(s2, 2).tolist(),
                           "deltaE_mean": round(ftex.delta_e(m1, m2), 2), "source": "art/02 swatch quilting"}
        else:
            alb, nrm, rough, hgt = swatch.limestone2(1024)
        d = {"height": hgt}
        barks[kind] = alb
        pre = "lf_rock_" if kind == "limestone" else "lf_bark_"
        for base, folder in ((RUNTIME, "rt"), (MASTER, "m")):
            ftex.save_rgb(os.path.join(base, f"{pre}{kind}_c.jpg"), alb, quality=90)
            ftex.save_rgb(os.path.join(base, f"{pre}{kind}_n.png"), nrm)
            ftex.save_rgb(os.path.join(base, f"{pre}{kind}_r.png"), rough)
        cv2.imwrite(os.path.join(MASTER, f"{pre}{kind}_height16.png"),
                    (np.clip(d["height"], 0, 1) * 65535).astype(np.uint16))
        print(f"[tex] {kind} {time.time() - t0:.1f}s", flush=True)
    if not a.skip_atlas:
        A = atlas.build_atlas(barks)
        A = atlas.dilate_colour(A)
        ftex.save_rgba(os.path.join(RUNTIME, "lf_foliage_atlas.png"), A)
        ftex.save_rgba(os.path.join(MASTER, "lf_foliage_atlas.png"), A)
        bg = np.array([0.87, 0.82, 0.78])
        prev = A[..., :3] * A[..., 3:4] + bg * (1 - A[..., 3:4])
        qa = paths.ensure(paths.QA_COMPARE, "forest_atlas")
        ftex.save_rgb(os.path.join(qa, f"iter{a.iter:02d}_atlas.png"), cv2.resize(prev, (1024, 1024), interpolation=cv2.INTER_AREA))
        with open(os.path.join(MASTER, "lf_foliage_atlas_layout.json"), "w") as f:
            json.dump({k: v for k, v in atlas.LAYOUT.items()}, f, indent=1)
        print(f"[tex] atlas {time.time() - t0:.1f}s", flush=True)
    # swatch sheet: reference | albedo | lit preview (normal) per kind
    rows = []
    for kind in ftex.BARK_SWATCH:
        ref = ftex.load_swatch(kind)
        h = 220
        r = cv2.resize(ref, (int(ref.shape[1] * h / ref.shape[0]), h), interpolation=cv2.INTER_AREA)
        alb = barks[kind][:512, :512]
        nrm = cv2.imread(os.path.join(RUNTIME, f"lf_bark_{kind}_n.png"))[..., ::-1][:512, :512] / 255.0
        N = nrm * 2 - 1
        L = np.array([-0.55, 0.55, 0.65])
        L /= np.linalg.norm(L)
        sh = np.clip((N * L).sum(-1), 0, 1) * 0.7 + 0.4
        lit = np.clip(alb * sh[..., None], 0, 1)
        rows.append(np.concatenate([r, np.ones((h, 6, 3)), cv2.resize(alb, (h, h)), cv2.resize(lit, (h, h))], 1))
    W = max(x.shape[1] for x in rows)
    rows = [np.pad(x, ((0, 4), (0, W - x.shape[1]), (0, 0)), constant_values=1) for x in rows]
    qa = paths.ensure(paths.QA_COMPARE, "forest_bark")
    ftex.save_rgb(os.path.join(qa, f"iter{a.iter:02d}_swatches.png"), np.concatenate(rows, 0))
    with open(os.path.join(qa, f"iter{a.iter:02d}_swatches.json"), "w") as f:
        json.dump(stats, f, indent=1)
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
