#!/usr/bin/env bash
# Usage: godot_city_run.sh <out_dir> [godot args...]   (props v2 game-camera test; private project copy)
set -euo pipefail
OUT="$(readlink -f "$1")"; shift
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../../../.." && pwd)"
WORK="$(mktemp -d /tmp/pv2city.XXXXXX)"
cp -r "$HERE/godot_city/." "$WORK/"
mkdir -p "$WORK/models"
cp "$REPO/godot/project/assets/forest_rescue/props/"*.glb "$REPO/godot/project/assets/forest_rescue/props/"*.json "$WORK/models/"
for f in "$REPO/godot/project/assets/forest_rescue/props/"*_c.jpg "$REPO/godot/project/assets/forest_rescue/props/"*_n.png "$REPO/godot/project/assets/forest_rescue/props/"*_lod?_c.jpg; do [ -f "$f" ] && cp "$f" "$WORK/models/"; done
cp "$REPO/godot/project/assets/forest_rescue/humans/"lf_civilian_*.glb "$REPO/godot/project/assets/forest_rescue/humans/"lf_civilian_*.meta.json "$WORK/models/"
timeout 900 godot --headless --path "$WORK" --import > "$WORK/import.log" 2>&1 || true
grep -E "ERROR|WARNING" "$WORK/import.log" | grep -v -i vulkan | head -20 || true
mkdir -p "$OUT"
timeout 900 xvfb-run -a -s "-screen 0 1280x720x24" godot --path "$WORK" --rendering-driver vulkan -- --out="$OUT" "$@" 2>&1 | grep -E "CAGETEST|ERROR|SCRIPT" | head -20 || true
rm -rf "$WORK"
