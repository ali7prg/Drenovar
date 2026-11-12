#!/usr/bin/env python3
"""Validate files against the exact Godot 0.5.9 handoff asset inventory."""
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ASSETS = ROOT / "godot" / "project" / "assets"

def collect_expected():
    chunks = []
    parts = sorted((ROOT / "docs").glob("04_ASSET_INVENTORY_PART_*.txt"))
    if not parts and (ROOT / "docs" / "04_ASSET_INVENTORY.json").is_file():
        j = json.loads((ROOT / "docs" / "04_ASSET_INVENTORY.json").read_text(encoding="utf-8"))
        return {item["resource_path"].removeprefix("res://assets/"): {"sha256": item["sha256"], "size": item["size_bytes"]} for item in j["assets"]}
    if len(parts) != 4:
        raise RuntimeError(f"Expected four inventory parts; found {len(parts)}")
    for part in parts:
        chunks.extend(re.split(r"\n={15,}\n", part.read_text(encoding="utf-8")))
    out = {}
    for chunk in chunks:
        path = re.search(r"^Путь ресурса:\s*res://assets/([^\r\n]+)", chunk, re.M)
        sha = re.search(r"^SHA-256:\s*([0-9a-f]{64})", chunk, re.M)
        size = re.search(r"^Точный размер:\s*(\d+) байт", chunk, re.M)
        if not (path and sha and size):
            continue
        rel = path.group(1)
        if rel in out:
            raise RuntimeError("Duplicate asset: " + rel)
        out[rel] = {"sha256": sha.group(1), "size": int(size.group(1))}
    if len(out) != 732:
        raise RuntimeError(f"Expected exactly 732 inventory assets, found {len(out)}")
    return out

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--minimum-present", type=int, default=0)
    parser.add_argument("--report", default="docs/ASSET_RESTORE_CHECK.json")
    args = parser.parse_args()
    expected = collect_expected()
    matched, missing, mismatched = [], [], []
    for rel, info in expected.items():
        file = ASSETS / rel
        if not file.is_file():
            missing.append(rel)
            continue
        data = file.read_bytes()
        if len(data) != info["size"] or hashlib.sha256(data).hexdigest() != info["sha256"]:
            mismatched.append(rel)
        else:
            matched.append(rel)
    report = {
        "source": "DRENOVAR-iOS-v0.5.9-source.zip",
        "expected_assets": 732,
        "verified_assets": len(matched),
        "missing_assets": len(missing),
        "mismatched_assets": len(mismatched),
        "verified_paths": sorted(matched),
        "missing_paths": sorted(missing),
        "mismatched_paths": sorted(mismatched),
    }
    print(json.dumps({k: v for k, v in report.items() if not k.endswith("_paths")}, indent=2))
    report_file = ROOT / args.report
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if mismatched:
        print("ERROR mismatched original assets:", mismatched[:20], file=sys.stderr)
        return 1
    if args.require_complete and missing:
        print("ERROR missing original assets:", missing[:20], file=sys.stderr)
        return 2
    if len(matched) < args.minimum_present:
        print(f"ERROR fewer than {args.minimum_present} originals verified", file=sys.stderr)
        return 3
    return 0

if __name__ == "__main__":
    sys.exit(main())
