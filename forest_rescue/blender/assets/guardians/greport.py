"""Write forest_rescue/qa/compare/<id>/REPORT.md from build outputs + the hand-written history.

python3 greport.py <asset_id> <history.md>
"""
import glob
import json
import os
import sys

REPO = "/home/user/Drenovar"


def load(p):
    try:
        return json.load(open(p))
    except Exception:
        return None


def main(aid, history):
    cdir = f"{REPO}/forest_rescue/qa/compare/{aid}"
    vdir = f"{REPO}/forest_rescue/qa/video/{aid}"
    meta = load(f"{REPO}/godot/project/assets/forest_rescue/guardians/{aid}.meta.json") or {}
    summ = load(f"{cdir}/build_summary.json") or {}
    iters = sorted(glob.glob(f"{cdir}/iter*_metrics.json"))
    L = [f"# {aid} — QA report", ""]
    L += [f"GLB: `godot/project/assets/forest_rescue/guardians/{aid}.glb` "
          f"({summ.get('glb_size_kb', '?')} KB) + `{aid}.meta.json`; source `forest_rescue/blender/sources/guardians/{aid}.blend`; "
          f"textures `forest_rescue/blender/textures/guardians/{aid}_*`.", ""]
    L += ["Rebuild: `python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/guardians/"
          f"build_{aid}.py --iter NN` (flags: `--fast`, `--no-anim`, `--no-export`, `--no-videos`, `--no-godot`).", ""]
    L += ["## Measured silhouette IoU per iteration (orthographic, LOD0, Cycles)", "",
          "| iteration | " + " | ".join(["side", "front", "rear"]) + " | colour err (side) |", "|---|---|---|---|---|"]
    for p in iters:
        m = load(p) or {}
        tag = os.path.basename(p).replace("_metrics.json", "")
        cells = [f"{m[v]['iou']:.3f}" if v in m else "–" for v in ("side", "front", "rear")]
        ce = f"{m['side']['mean_abs_colour_error']:.3f}" if "side" in m else "–"
        L.append(f"| {tag} | " + " | ".join(cells) + f" | {ce} |")
    L += ["", "Images: `iterNN_<view>.png` = [reference | render | IoU diff (green both, red sheet only, blue model only)].", ""]
    if os.path.exists(history):
        L += [open(history).read().rstrip(), ""]
    st = meta.get("glb_stats", {})
    if st:
        L += ["## Exported GLB (verified by parsing the file)", "", "| node | tris | joints used | max influences | hidden |",
              "|---|---|---|---|---|"]
        for n, m in st.get("meshes", {}).items():
            L.append(f"| {n} | {m['tris']} | {m['joints_used']} | {m['max_influences']} | {m['hidden']} |")
        L += ["", f"Skin joints: {st.get('skins')}; deform bones: {meta.get('bones')}; extensions: {st.get('extensionsUsed')}.",
              f"Bounds (glTF, m): {meta.get('bounds_m')}.", ""]
        L += ["## Clips", "", "| clip | s | loop | speed m/s | stride m | contact/markers | max stance slip cm | IK reach err cm | min z m |",
              "|---|---|---|---|---|---|---|---|---|"]
        for c, m in meta.get("clips", {}).items():
            slip = max(m.get("footSlip_cm_max", {}).values() or [0])
            L.append(f"| {c} | {m['seconds']} | {m['loop']} | {m.get('groundSpeed_mps', '')} | {m.get('strideLength_m', '')} | "
                     f"{m.get('markers', {})} | {slip} | {m.get('ikReachError_cm_max', '')} | {m.get('ground', {}).get('min_z_m', '')} |")
        L += ["", "Footfalls (touchdown/lift-off s) are in the meta (`clips.Walk.footfalls`).", ""]
    if summ.get("strip"):
        L += ["## Motion strip (Attack vs art/09 bottom strip)", ""]
        for k, v in summ["strip"].items():
            L.append(f"- {k}: Attack t={v['attack_time_s']} s, silhouette IoU {v['iou']:.3f} (camera scale fitted, "
                     f"{v['fitted_ppm']:.0f} px/m) — `strip_{k}.png`")
        L.append("")
    vids = sorted(glob.glob(f"{vdir}/*.mp4"))
    if vids:
        L += ["## Videos", ""] + [f"- `{os.path.relpath(v, REPO)}` (+ `_contact.png`)" for v in vids] + [""]
    if summ.get("godot"):
        L += ["## Godot 4.6 viewer (exported GLB)", "", "```"] + summ["godot"][:12] + ["```",
              "Shots: `godot/shot_yaw*.png`; old vs new: `old_vs_new.png`.", ""]
    L += ["## Level variants", "", "```json", json.dumps(meta.get("levels", {}), indent=1, ensure_ascii=False), "```", ""]
    L += ["## Notes", "", meta.get("notes", ""), ""]
    open(f"{cdir}/REPORT.md", "w").write("\n".join(L))
    print("wrote", f"{cdir}/REPORT.md")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
