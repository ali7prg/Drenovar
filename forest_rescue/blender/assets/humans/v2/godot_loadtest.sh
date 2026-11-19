#!/usr/bin/env bash
# Load test of the v2 humans through the game's actor_rig.gd in a private copy of the game scripts.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../../../.." && pwd)"
OUT="${1:-$REPO/forest_rescue/qa/compare/humans_v2_loadtest}"
mkdir -p "$OUT"
WORK="$(mktemp -d /tmp/frloadtest.XXXXXX)"
cp -r "$HERE/godot_loadtest/." "$WORK/"
mkdir -p "$WORK/src" "$WORK/assets/forest_rescue"
cp -r "$REPO/godot/project/src/forest_rescue" "$WORK/src/"
cp -r "$REPO/godot/project/assets/forest_rescue/humans" "$WORK/assets/forest_rescue/"
find "$WORK/assets" -name "*.import" -delete
timeout 900 godot --headless --path "$WORK" --import >/dev/null 2>&1 || true
timeout 900 xvfb-run -a -s "-screen 0 1280x720x24" godot --path "$WORK" --rendering-driver vulkan --fixed-fps 30 -- --out="$OUT" 2>&1 | grep -E "LOADTEST|ERROR|SCRIPT ERROR|Parse Error" | head -40 || true
rm -rf "$WORK"
