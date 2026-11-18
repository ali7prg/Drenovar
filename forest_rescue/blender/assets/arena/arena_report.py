"""Write forest_rescue/qa/compare/lf_boss_arena/REPORT.md (no bpy)."""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
CMP = os.path.join(REPO, "forest_rescue", "qa", "compare", "lf_boss_arena")
RT = os.path.join(REPO, "godot", "project", "assets", "forest_rescue", "arena")
import arena_iterations as IT  # noqa: E402


def main():
    extra = open(sys.argv[1]).read() if len(sys.argv) > 1 else ""
    L = ["# lf_boss_arena — production report", ""]
    asm = json.load(open(os.path.join(RT, "lf_boss_arena_assembled.meta.json")))
    L += ["## Deliverables (godot/project/assets/forest_rescue/arena/)", "", "| GLB | tris (LOD0 / LOD1) |", "|---|---|"]
    for p in sorted(glob.glob(os.path.join(RT, "*.meta.json"))):
        m = json.load(open(p))
        L.append(f"| `{m['id']}.glb` | {m.get('tris')} |")
    L += ["", f"Assembled preview LOD0 total: **{asm['tris']['LOD0_total']} tris** (budget 60000).", "",
          f"Entrance: {asm['entrance']}.", "",
          f"World placement: {asm['world_placement']}.", ""]
    L += ["## Compare -> fix iterations (3/4 render vs art/08, module call-outs)", ""]
    for it in IT.ITERATIONS:
        L += [f"### iter{it['iter']}", "", "Differences seen:"] + [f"* {d}" for d in it["diffs"]]
        L += ["", "Changed:"] + [f"* {d}" for d in it["fixes"]] + [""]
    L += [extra]
    open(os.path.join(CMP, "REPORT.md"), "w").write("\n".join(L) + "\n")
    print("arena REPORT written")


if __name__ == "__main__":
    main()
