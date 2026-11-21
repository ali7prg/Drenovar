#!/usr/bin/env python3
"""Layout pass 3 checks on the v3 shot group.

1. City unchanged: same state, same camera, forest colour grade ("boost") off vs on (v3city_boost_off/on_z40/z68).
   Pixels whose ground point lies inside the base square (|x|, |z| <= 54) must not change; reports the max /
   mean absolute difference there and writes a diff heat map.
2. Fog edge: the four extreme reachable camera targets at zoom 120 (landscape.gd shift_camera_target clamps x to
   +-147 and z to +-118). For every pixel whose ground point lies outside +-112 the frame must show fog (or the
   inner fog shell), never the bare plane / river: reports the share of non-fog pixels out there.

    /opt/tools/blender-venv/bin/python forest_rescue/qa/ingame/integration/v3_checks.py <shots dir>
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image

OFFSET = np.array([75.0, 83.0, 75.0])


def ground_points(target, zoom, size, h=4.0):
    W, H = size
    f = -OFFSET / np.linalg.norm(OFFSET)
    r = np.cross(f, [0.0, 1.0, 0.0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    px, py = np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5)
    sx = (px - W / 2) / H * zoom
    sy = -(py - H / 2) / H * zoom
    cam = np.array([target[0], 0.0, target[1]]) + OFFSET
    O = cam[None, None, :] + r[None, None, :] * sx[..., None] + u[None, None, :] * sy[..., None]
    t = (h - O[..., 1]) / f[1]
    P = O + f[None, None, :] * t[..., None]
    return P[..., 0], P[..., 2]


def fog_like(a):
    a = a.astype(float) / 255.0
    mx, mn = a.max(-1), a.min(-1)
    s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0)
    lum = a @ np.array([0.299, 0.587, 0.114])
    return (s < 0.22) & (a[..., 2] >= a[..., 0] - 0.03) & (lum > 0.25)


def main():
    shots = sys.argv[1]
    report = {"city": {}, "fog_edge": {}}
    for z in (40, 68):
        p0 = os.path.join(shots, "v3city_boost_off_z%d.png" % z)
        p1 = os.path.join(shots, "v3city_boost_on_z%d.png" % z)
        if not (os.path.exists(p0) and os.path.exists(p1)):
            continue
        a = np.asarray(Image.open(p0).convert("RGB")).astype(int)
        b = np.asarray(Image.open(p1).convert("RGB")).astype(int)
        X, Z = ground_points((0.0, 0.0), float(z), (a.shape[1], a.shape[0]))
        core = (np.abs(X) <= 54) & (np.abs(Z) <= 54)
        # pixels animated between two captures with the same setting (wind, water, fog drift, fire) are not
        # evidence either way: the proof is on the static pixels (buildings, ground, roofs, walls)
        p2 = os.path.join(shots, "v3city_boost_on2_z%d.png" % z)
        if os.path.exists(p2):
            c = np.asarray(Image.open(p2).convert("RGB")).astype(int)
            static = np.abs(b - c).max(-1) <= 2
        else:
            static = np.ones(core.shape, bool)
        report["city"].setdefault("static_core_px_z%d" % z, int((core & static).sum()))
        core = core & static
        d = np.abs(a - b).max(-1)
        report["city"]["z%d" % z] = {"core_px": int(core.sum()), "core_max_abs_diff": int(d[core].max()) if core.any() else 0,
                                    "core_mean_abs_diff": float(d[core].mean()) if core.any() else 0.0,
                                    "core_changed_px": int((d[core] > 2).sum()),
                                    "outside_changed_px": int((d[~core] > 2).sum())}
        heat = np.zeros(a.shape, np.uint8)
        heat[..., 0] = np.clip(d * 8, 0, 255)
        heat[..., 1] = np.where(core, 60, 0)
        Image.fromarray(heat).save(os.path.join(shots, "v3city_diff_z%d.png" % z))
        print("city z%d: core px %d, max |diff| %d, changed (>2) %d; outside the base changed %d" % (
            z, core.sum(), report["city"]["z%d" % z]["core_max_abs_diff"], report["city"]["z%d" % z]["core_changed_px"],
            report["city"]["z%d" % z]["outside_changed_px"]))
    for name, target in (("ne", (147, -118)), ("se", (147, 118)), ("sw", (-147, 118)), ("nw", (-147, -118))):
        p = os.path.join(shots, "v3edge_%s_z120.png" % name)
        if not os.path.exists(p):
            continue
        a = np.asarray(Image.open(p).convert("RGB"))
        X, Z = ground_points(target, 120.0, (a.shape[1], a.shape[0]))
        outside = (np.abs(X) > 112) | (np.abs(Z) > 112)
        fog = fog_like(a)
        bare = outside & ~fog
        report["fog_edge"][name] = {"outside_px": int(outside.sum()), "outside_not_fog_px": int(bare.sum()),
                                    "outside_not_fog_pct": float(bare.sum()) * 100.0 / max(1, int(outside.sum()))}
        vis = a.copy()
        vis[bare] = [255, 0, 255]
        Image.fromarray(vis).save(os.path.join(shots, "v3edge_%s_check.png" % name))
        print("edge %s: outside +-112 px %d, not fog %d (%.2f%%)" % (name, outside.sum(), bare.sum(),
                                                                     report["fog_edge"][name]["outside_not_fog_pct"]))
    json.dump(report, open(os.path.join(shots, "v3_checks.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
