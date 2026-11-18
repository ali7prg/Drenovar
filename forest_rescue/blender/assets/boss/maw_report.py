"""Write forest_rescue/qa/compare/lf_boss_ancient_maw/REPORT.md from the QA json files (no bpy).

python3 forest_rescue/blender/assets/boss/maw_report.py [extra_notes.md]
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
CMP = os.path.join(REPO, "forest_rescue", "qa", "compare", "lf_boss_ancient_maw")
VID = os.path.join(REPO, "forest_rescue", "qa", "video", "lf_boss_ancient_maw")
META = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "boss", "lf_boss_ancient_maw.meta.json")

import maw_iterations as IT  # noqa: E402


def load(p):
    try:
        return json.load(open(p))
    except Exception:
        return None


def main():
    extra = open(sys.argv[1]).read() if len(sys.argv) > 1 else ""
    L = ["# lf_boss_ancient_maw «Пращур» — production report", ""]
    meta = load(META) or {}
    L += ["## Deliverables", "",
          "| item | path |", "|---|---|",
          "| game GLB (LOD0/1/2, rig, 13 clips) | `godot/project/assets/forest_rescue/boss/lf_boss_ancient_maw.glb` |",
          "| sidecar | `godot/project/assets/forest_rescue/boss/lf_boss_ancient_maw.meta.json` |",
          "| editable master (.blend, packed) | `forest_rescue/blender/sources/boss/lf_boss_ancient_maw.blend` |",
          "| texture masters / runtime | `forest_rescue/blender/textures/boss/` (`runtime/` = 2048 GLB maps) |",
          "| build scripts | `forest_rescue/blender/assets/boss/` (entry: `build_lf_boss_ancient_maw.py`) |",
          "| QA images | `forest_rescue/qa/compare/lf_boss_ancient_maw/` |",
          "| QA videos | `forest_rescue/qa/video/lf_boss_ancient_maw/` |", ""]
    if meta:
        L += ["## Budgets (measured from the exported GLB)", "",
              f"* triangles: {meta.get('tris')} (targets 48000 / 24000 / 9000)",
              f"* deform bones in the skin: {meta.get('bones')} (target <= 80); bones actually weighted per LOD: "
              f"{meta.get('bonesUsedPerLOD')} (targets 80/50/28)",
              f"* materials: {meta.get('materials')}; images: {meta.get('images')}",
              f"* bounds (Blender metres, rest): {meta.get('bounds_m')}", ""]
    L += ["## Silhouette IoU per iteration (Cycles render vs the reference mask)", "",
          "`left` = sheet left view with the anatomically impossible third leg removed from the mask; "
          "`left_raw` = untouched mask (3 legs); `front` = front orthographic.", "",
          "| iteration | left | left_raw | front | mean abs colour error (left) |", "|---|---|---|---|---|"]
    for p in sorted(glob.glob(os.path.join(CMP, "iter*_metrics.json"))):
        m = load(p)
        tag = os.path.basename(p)[4:6]
        L.append(f"| {tag} | {m['left']['iou']} | {m['left_raw']['iou']} | {m['front']['iou']} | "
                 f"{m['left']['mean_abs_colour_error']} |")
    L += [""]
    L += ["## Compare -> fix iterations", ""]
    for it in IT.ITERATIONS:
        L += [f"### iter{it['iter']} — {it['build']}", "", "Differences seen:"]
        L += [f"* {d}" for d in it["diffs"]]
        L += ["", "Changed for the next iteration:"]
        L += [f"* {d}" for d in it["fixes"]]
        L += [""]
    kp = sorted(glob.glob(os.path.join(CMP, "iter*_keyposes.json")))
    if kp:
        k = load(kp[-1])
        L += [f"## Keypose matches (art/05), {os.path.basename(kp[-1])}", "",
              "bbox-aligned silhouette IoU is only indicative (panels are perspective drawings with varying limb "
              "lengths).", "", "| panel | clip @ time | aligned IoU |", "|---|---|---|"]
        for n, v in k.items():
            L.append(f"| {n} | {v['clip']} @ {v['time_s']} s | {v['aligned_iou']} |")
        L += [""]
    cr = load(os.path.join(VID, "clips_report.json"))
    if meta.get("clips"):
        L += ["## Clips (exact manifest ids / durations / markers)", "",
              "| clip | seconds | loop | markers | foot slide L/R (m, planted toe drift) | videos |", "|---|---|---|---|---|---|"]
        for cid, c in meta["clips"].items():
            fs = (cr or {}).get(cid, {}).get("foot_slide_m", {})
            vids = ", ".join(v for k2, v in (cr or {}).get(cid, {}).items() if k2 in ("side", "game"))
            L.append(f"| {cid} | {c['seconds']} (exported {c.get('exportedSeconds')}) | {c['loop']} | "
                     f"{c.get('markers') or '-'} | {fs.get('L', '-')} / {fs.get('R', '-')} | {vids} |")
        L += [""]
    L += [extra]
    open(os.path.join(CMP, "REPORT.md"), "w").write("\n".join(L) + "\n")
    print("REPORT written")


if __name__ == "__main__":
    main()
