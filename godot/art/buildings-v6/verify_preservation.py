#!/usr/bin/env python3
"""Check untouched Claude art, 297 native states and all 270 visual transitions."""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ASSETS = ROOT / "godot/project/assets/city/architecture-v6"


def main() -> None:
    frozen = json.loads((HERE / "legacy-sha256.json").read_text())
    differences = [name for name, digest in frozen.items()
                   if not (ROOT / name).exists() or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
    assert not differences, "Legacy assets changed: " + repr(differences)
    manifest = json.loads((ASSETS / "manifest.json").read_text())
    rows = []
    transitions = []
    for runtime_type, levels in manifest["levels"].items():
        assert set(levels) == {str(x) for x in range(6, 12)}
        concept_id = levels["6"]["id"]
        for level in range(1, 12):
            if level <= 5:
                relative = f"godot/project/assets/city/architecture-v2/levels/{runtime_type}-{level}.tscn"
            else:
                relative = "godot/project/" + levels[str(level)]["path"].removeprefix("res://")
            file = ROOT / relative
            assert file.is_file(), f"Missing {concept_id}/{level}: {file}"
            rows.append({"building_id":concept_id,"runtime_type":runtime_type,"level":level,
                         "source":"13_BUILDING_PASSPORTS_RU.md", "native_scene":relative,
                         "sha256":hashlib.sha256(file.read_bytes()).hexdigest(),
                         "origin":"Claude preserved" if level <= 5 else "V6 ART1 authored",
                         "verification":"passed"})
            if level > 1:
                transitions.append({"building_id":concept_id,"from":level-1,"to":level,"status":"passed",
                                    "gate":level in (4,6,11)})
        assert not (ASSETS / "levels" / f"{runtime_type}-12.tscn").exists(), "Hidden XII"
    assert len(rows) == 297 and len(transitions) == 270
    assert sum(x["gate"] for x in transitions) == 81
    with (ASSETS / "native-coverage-297.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys(), lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
    report = {"status":"passed", "legacy_files_unchanged":len(frozen),"native_states":len(rows),
              "visual_transitions":len(transitions),"III_IV_V_VI_X_XI":81,
              "source":"DRENOVAR-V6-C1.0/13_BUILDING_PASSPORTS_RU.md",
              "transitions":transitions,
              "scope":"Asset existence/continuity only; authoritative gameplay transitions are tested separately"}
    (ASSETS / "preservation-validation.json").write_text(json.dumps(report,indent=2)+"\n")
    print(f"ART_PRESERVATION files={len(frozen)} states=297 transitions=270 gates=81 passed")


if __name__ == "__main__":
    main()
