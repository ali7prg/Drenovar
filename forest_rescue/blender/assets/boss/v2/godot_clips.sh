#!/usr/bin/env bash
# Every Ancient Maw clip in Godot 4.6.3 (game renderer) via forest_rescue/tools/godot_view.sh, plus one all-clips MP4.
# Usage: godot_clips.sh [glb]   (absolute paths throughout)
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../../../.." && pwd)"
GLB="${1:-$REPO/godot/project/assets/forest_rescue/boss/lf_boss_ancient_maw.glb}"
OUT="$REPO/forest_rescue/qa/video/lf_boss_ancient_maw"
VIEW="$REPO/forest_rescue/tools/godot_view.sh"
mkdir -p "$OUT"
declare -A DUR=( [lf_boss_idle]=5.0 [lf_boss_walk]=3.2 [lf_boss_turn_left]=1.3 [lf_boss_turn_right]=1.3 [lf_boss_awaken]=4.2
  [lf_boss_phase_roar]=2.8 [lf_boss_hit]=1.1 [lf_boss_stagger]=1.8 [lf_boss_death]=5.2 [lf_boss_jaw_arc]=4.25
  [lf_boss_tail_sweep]=5.45 [lf_boss_lane_charge]=5.9 [lf_boss_stomp_waves]=6.9 )
for c in "${!DUR[@]}"; do
  "$VIEW" "$GLB" clip "$OUT/godot_${c}.mp4" "$c" "${DUR[$c]}" --yaw=62 --pitch=12 --dist=1.0 --lod=0 2>&1 | grep -E "VIDEO|ERROR" | head -3
done
"$VIEW" "$GLB" clip "$OUT/godot_all_clips.mp4" all 51 --yaw=62 --pitch=12 --dist=1.0 --lod=0 2>&1 | grep -E "VIDEO|ERROR" | head -3
