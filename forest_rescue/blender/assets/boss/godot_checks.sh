#!/usr/bin/env bash
# In-engine checks of the exported boss GLB (Godot 4.6 Mobile viewer): shots, all-clips video, reference sheets.
# usage: godot_checks.sh <iter> [cache_dir]
set -euo pipefail
IT="$1"; CACHE="${2:-${MAW_CACHE:-/tmp/maw_cache}}"
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
CMP="$ROOT/forest_rescue/qa/compare/lf_boss_ancient_maw"; VID="$ROOT/forest_rescue/qa/video/lf_boss_ancient_maw"
GV="$ROOT/forest_rescue/tools/godot_view.sh"
QA_GLB="$CACHE/lf_boss_ancient_maw_LOD0_qa.glb"
GAME_GLB="$ROOT/godot/project/assets/forest_rescue/boss/lf_boss_ancient_maw.glb"
mkdir -p "$CMP/godot_iter$IT" "$VID"
"$GV" "$QA_GLB" shots "$CMP/godot_iter$IT" lf_boss_idle 6 --pitch=12 --dist=1.05 | tail -3
"$GV" "$GAME_GLB" shots "$CMP/godot_iter${IT}_gameglb" lf_boss_idle 6 | tail -3
python3 "$ROOT/forest_rescue/blender/assets/boss/godot_compare.py" "$CMP/godot_iter$IT" "$CMP/iter${IT}_godot_vs_reference.png" \
  "$ROOT/forest_rescue/delivery/art/03_boss_ancient_maw_turnaround.png" "0,120,935,485:90" "918,95,1192,485:0" "1160,95,1536,485:135"
"$GV" "$QA_GLB" clip "$VID/godot_all_clips.mp4" all 95 | tail -2
