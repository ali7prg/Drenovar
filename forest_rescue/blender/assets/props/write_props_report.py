"""Assemble forest_rescue/qa/compare/props_REPORT.md from the QA metrics, metas and iteration notes.

Run: python3 forest_rescue/blender/assets/props/write_props_report.py
"""
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
FR = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
REPO = os.path.dirname(FR)
CMP = os.path.join(FR, "qa", "compare")
VID = os.path.join(FR, "qa", "video")
RT = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "props")
ASSETS = ["lf_cage_wood", "lf_cage_iron", "lf_cage_root", "lf_artifact_stone_rune", "lf_artifact_bronze_seal",
          "lf_artifact_amber_crystal", "lf_artifact_bone_key", "lf_props_supplies", "lf_mechanism_trail_cache",
          "lf_mechanism_rune_lock", "lf_mechanism_winch_sequence", "lf_mechanism_paired_latch"]


def rel(p):
    return os.path.relpath(p, os.path.join(FR, "qa", "compare"))


def load(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def main():
    notes = load(os.path.join(CMP, "props_notes", "iterations.json"), {})
    extra = load(os.path.join(CMP, "props_notes", "summary.json"), {})
    L = ["# Props REPORT - cages, artifacts, sockets, supplies, mechanisms", "",
         extra.get("intro", ""), ""]
    L += ["## Deliverables", "", "| asset | GLB | tris LOD0/1/2 | clips | notes |", "|---|---|---|---|---|"]
    for a in ASSETS:
        m = load(os.path.join(RT, f"{a}.meta.json"))
        if not m:
            L.append(f"| {a} | missing | | | |")
            continue
        t = m.get("tris", {})
        clips = ", ".join(f"{c} ({v['seconds']}s)" for c, v in m.get("clips", {}).items())
        if len(clips) > 300:
            clips = clips[:300] + " ..."
        glb = os.path.join(RT, f"{a}.glb")
        size = os.path.getsize(glb) // 1024 if os.path.exists(glb) else 0
        L.append(f"| {a} | `godot/project/assets/forest_rescue/props/{a}.glb` ({size} KB) | "
                 f"{t.get('LOD0')}/{t.get('LOD1')}/{t.get('LOD2')} | {clips} | {m.get('budget', '')} |")
    L.append("")
    for a in ASSETS:
        L += [f"## {a}", ""]
        n = notes.get(a, {})
        files = sorted(glob.glob(os.path.join(CMP, a, "iter*_*.json")))
        its = sorted(set(re.findall(r"iter(\d+)_", " ".join(os.path.basename(f) for f in files))))
        for it in its:
            L.append(f"### iter{it}")
            nn = n.get(f"iter{it}", {})
            if nn.get("approach"):
                L.append(f"* approach: {nn['approach']}")
            rows = []
            for f in sorted(glob.glob(os.path.join(CMP, a, f"iter{it}_*.json"))):
                if f.endswith("metrics.json"):
                    continue
                d = load(f, {})
                if "iou_filled" not in d:
                    continue
                rows.append(f"| {os.path.basename(f)[:-5]} | {d.get('iou_filled')} | {d.get('iou_raw')} | "
                            f"{d.get('mean_abs_colour_error')} | ![]({rel(f[:-5] + '.png')}) |")
            if rows:
                L += ["", "| view | IoU filled | IoU raw | mean abs colour err | image |", "|---|---|---|---|---|"] + rows + [""]
            for k in ("diffs", "fixes_next"):
                if nn.get(k):
                    L.append(f"* {'differences seen' if k == 'diffs' else 'changed for the next iteration'}:")
                    L += [f"  * {x}" for x in nn[k]]
            others = [os.path.basename(p) for p in sorted(glob.glob(os.path.join(CMP, a, f"iter{it}_*.png")))
                      if not os.path.exists(p[:-4] + ".json")]
            if others:
                L.append("* other images: " + ", ".join(f"[{o}]({a}/{o})" for o in others))
            L.append("")
        vids = sorted(glob.glob(os.path.join(VID, a, "*.mp4")))
        if vids:
            L.append("* videos: " + ", ".join(f"`qa/video/{a}/{os.path.basename(v)}`" for v in vids))
        m = load(os.path.join(RT, f"{a}.meta.json"))
        if m:
            if m.get("sockets"):
                L.append("* sockets/meta: `" + json.dumps(m["sockets"], ensure_ascii=False)[:900] + "`")
            if m.get("symbol_targets"):
                L.append("* symbol targets: `" + json.dumps(m["symbol_targets"], ensure_ascii=False)[:900] + "`")
        if n.get("deviations"):
            L.append("* remaining deviations:")
            L += [f"  * {x}" for x in n["deviations"]]
        L.append("")
    for sec in extra.get("sections", []):
        L += [f"## {sec['title']}", ""] + sec["lines"] + [""]
    out = os.path.join(CMP, "props_REPORT.md")
    open(out, "w", encoding="utf-8").write("\n".join(L))
    print("wrote", out)


if __name__ == "__main__":
    main()
