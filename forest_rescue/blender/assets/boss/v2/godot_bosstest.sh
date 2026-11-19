#!/usr/bin/env bash
# Ancient Maw v2: load test + game-camera shots through the game's actor loader in a private project copy.
# Usage: godot_bosstest.sh [out_dir]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../../../.." && pwd)"
OUT="${1:-$REPO/forest_rescue/qa/compare/lf_boss_ancient_maw/godot}"
mkdir -p "$OUT"
WORK="$(mktemp -d /tmp/frbosstest.XXXXXX)"
cp -r "$HERE/godot_bosstest/." "$WORK/"
mkdir -p "$WORK/src" "$WORK/assets/forest_rescue"
cp -r "$REPO/godot/project/src/forest_rescue" "$WORK/src/"
for g in boss arena humans horse; do cp -r "$REPO/godot/project/assets/forest_rescue/$g" "$WORK/assets/forest_rescue/"; done
find "$WORK/assets" -name "*.import" -delete
timeout 1200 godot --headless --path "$WORK" --import >/dev/null 2>&1 || true
timeout 1200 xvfb-run -a -s "-screen 0 1600x900x24" godot --path "$WORK" --rendering-driver vulkan --fixed-fps 30 -- --out="$OUT" 2>&1 | grep -E "BOSSTEST|ERROR|SCRIPT ERROR|Parse Error" | head -40 || true
rm -rf "$WORK"
