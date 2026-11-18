#!/usr/bin/env bash
# Wind-shader variant of forest_rescue/tools/godot_view.sh (QA only; never touches godot/project).
# Usage: godot_wind_view.sh <model.glb> <shots|clip|turntable> <out_dir_or_mp4> [anim] [seconds] [viewer args...]
# Extra viewer args: --wind=0|1 --ortho=1 --yaws=0,45 --pitches=20,60 --only=_LOD0 --dist=1.1 --windk=1
set -euo pipefail
GLB="$(readlink -f "$1")"; MODE="$2"; OUT="$3"; ANIM="${4:-all}"; SECS="${5:-6}"; shift 5 2>/dev/null || shift $#
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d /tmp/frwindviewer.XXXXXX)"
cp -r "$HERE/godot_wind_viewer/." "$WORK/"
mkdir -p "$WORK/models"; cp "$GLB" "$WORK/models/"
for f in "$(dirname "$GLB")"/*.png "$(dirname "$GLB")"/*.jpg; do [ -f "$f" ] && cp "$f" "$WORK/models/" || true; done
NAME="$(basename "$GLB")"
timeout 900 godot --headless --path "$WORK" --import >/dev/null 2>&1 || true
XV=(xvfb-run -a -s "-screen 0 1280x720x24")
if [ "$MODE" = "shots" ]; then
  mkdir -p "$OUT"
  timeout 600 "${XV[@]}" godot --path "$WORK" --rendering-driver vulkan -- --model="res://models/$NAME" --mode=shots --out="$OUT" --anim="$ANIM" "$@" 2>&1 | grep -E "VIEWER|ERROR|SHADER" || true
else
  FR=$(python3 -c "print(int(float('$SECS')*30))")
  mkdir -p "$(dirname "$OUT")"
  timeout 1200 "${XV[@]}" godot --path "$WORK" --rendering-driver vulkan --write-movie "$WORK/frames.png" --fixed-fps 30 --quit-after "$FR" -- --model="res://models/$NAME" --mode="$MODE" --anim="$ANIM" "$@" 2>&1 | grep -E "VIEWER|ERROR|SHADER" || true
  ffmpeg -y -loglevel error -framerate 30 -i "$WORK/frames%08d.png" -c:v libx264 -pix_fmt yuv420p -crf 21 "$OUT"
  echo "VIDEO $OUT"
fi
rm -rf "$WORK"
