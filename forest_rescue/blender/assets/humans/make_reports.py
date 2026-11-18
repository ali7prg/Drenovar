"""Write qa/compare/<asset>/REPORT.md for the 9 humans and the two group reports
(qa/compare/humans_civilians/REPORT.md, qa/compare/humans_squad/REPORT.md).  Plain python."""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
QA = os.path.join(REPO, "forest_rescue", "qa")
RUNTIME = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "humans")
CIV = ["lf_civilian_miller", "lf_civilian_herbalist", "lf_civilian_ferryman", "lf_civilian_courier",
       "lf_civilian_cooper", "lf_civilian_quarry_worker"]
SQ = ["lf_squad_captain", "lf_squad_scout", "lf_squad_shield_guard"]
DEVIATIONS = json.load(open(os.path.join(HERE, "deviations.json"), encoding="utf-8")) \
    if os.path.exists(os.path.join(HERE, "deviations.json")) else {}


def jl(p, default=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return default


def asset_report(a):
    d = os.path.join(QA, "compare", a)
    meta = jl(os.path.join(RUNTIME, f"{a}.meta.json"), {})
    its = jl(os.path.join(d, "iterations.json"), [])
    final = its[-1] if its else {}
    L = [f"# {a} — QA report", ""]
    L.append(f"GLB: `godot/project/assets/forest_rescue/humans/{a}.glb` · master: "
             f"`forest_rescue/blender/sources/humans/{a}.blend` · build: "
             f"`python3 forest_rescue/blender/run_limited.py forest_rescue/blender/assets/humans/build_{a}.py final`")
    L.append("")
    if meta:
        L.append(f"* Triangles: LOD0 {meta['tris'].get('LOD0')} / LOD1 {meta['tris'].get('LOD1')} / LOD2 "
                 f"{meta['tris'].get('LOD2')} (budget {'14000/7000/2500' if a.startswith('lf_squad') else '12000/6000/2200'})")
        L.append(f"* Skeleton `human_shared`: {meta['bones']} bones (all deforming); bones carrying weights per LOD: "
                 f"{meta.get('deformBonesUsedByLOD')}; max 4 influences")
        L.append(f"* Materials: {', '.join(meta.get('materials', []))}; textures 1024² (albedo JPEG, ORM JPEG, normal PNG); "
                 f"masters 2048² in `forest_rescue/blender/textures/humans/`")
        L.append(f"* Optional parts: {', '.join(meta.get('optionalParts', [])) or '—'}")
        L.append(f"* Clips: {len(meta.get('clips', {}))} — " + ", ".join(
            f"{k} {v['seconds']}s{' loop' if v.get('loop') else ''}" for k, v in meta.get("clips", {}).items()))
        slides = {k: v.get("footSlide_cm") for k, v in meta.get("clips", {}).items() if v.get("footSlide_cm") is not None}
        if slides:
            L.append(f"* Measured stance-foot slide (max over stance, cm): {slides}")
    L.append("")
    L.append("## Reference comparison (orthographic, sheet panels)")
    L.append("")
    L.append("| iteration | IoU front | IoU back | colour err front | colour err back |")
    L.append("|---|---|---|---|---|")
    for e in its:
        m = e.get("metrics", {})
        f, b = m.get("front", {}), m.get("back", {})
        L.append(f"| {e['tag']} | {f.get('iou', '—')} | {b.get('iou', '—')} | {f.get('colour_error', '—')} | "
                 f"{b.get('colour_error', '—')} |")
    L.append("")
    L.append("Images: `iterNN_front.png`, `iterNN_back.png` ([reference | render | IoU diff]), `iterNN_views.png` "
             "(4 perspective views), `iterNN_face.png` (face close-up next to the sheet face / portrait), "
             "`godot_vs_sheet.png` (Godot Mobile renderer shots next to the sheet panels).")
    L.append("")
    L.append("## Iterations: what differed → what was changed")
    L.append("")
    for e in its:
        L.append(f"**{e['tag']}**")
        for x in e.get("differences", []):
            L.append(f"- differs: {x}")
        for x in e.get("changes_for_next", []):
            L.append(f"- changed: {x}")
        L.append("")
    L.append("## Known deviations (honest)")
    L.append("")
    for x in DEVIATIONS.get("_all", []) + DEVIATIONS.get(a, []):
        L.append(f"- {x}")
    L.append("")
    L.append("## Videos")
    L.append("")
    vids = sorted(glob.glob(os.path.join(QA, "video", a, "*.mp4")))
    for v in vids:
        L.append(f"- `{os.path.relpath(v, REPO)}`")
    open(os.path.join(d, "REPORT.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    return final


def group_report(name, assets, title):
    d = os.path.join(QA, "compare", name)
    os.makedirs(d, exist_ok=True)
    L = [f"# {title}", ""]
    L.append("| asset | LOD0/1/2 tris | bones | IoU front | IoU back | clips |")
    L.append("|---|---|---|---|---|---|")
    for a in assets:
        meta = jl(os.path.join(RUNTIME, f"{a}.meta.json"), {})
        its = jl(os.path.join(QA, "compare", a, "iterations.json"), [])
        m = its[-1]["metrics"] if its else {}
        t = meta.get("tris", {})
        L.append(f"| [{a}](../{a}/REPORT.md) | {t.get('LOD0')}/{t.get('LOD1')}/{t.get('LOD2')} | {meta.get('bones')} | "
                 f"{m.get('front', {}).get('iou')} | {m.get('back', {}).get('iou')} | {len(meta.get('clips', {}))} |")
    L.append("")
    extra = DEVIATIONS.get("_" + name, [])
    if extra:
        L.append("## Group notes")
        L += [f"- {x}" for x in extra]
    open(os.path.join(d, "REPORT.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    for a in CIV + SQ:
        asset_report(a)
    group_report("humans_civilians", CIV, "Civilian bases (6) — group report")
    group_report("humans_squad", SQ, "Expedition squad (3) — group report")
    print("reports written")
