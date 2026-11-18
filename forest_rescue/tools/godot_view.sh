#!/usr/bin/env bash
# Usage: godot_view.sh <model.glb> <mode: shots|clip|turntable> <out_dir_or_mp4> [anim] [seconds] [extra viewer args...]
# Copies the viewer template to a private scratch dir (safe for parallel agents), imports, renders.
set -euo pipefail
GLB="$(readlink -f "$1")"; MODE="$2"; OUT="$3"; ANIM="${4:-all}"; SECS="${5:-6}"; shift 5 2>/dev/null || shift $#
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d /tmp/frviewer.XXXXXX)"
cp -r "$HERE/godot_viewer/." "$WORK/"
cp "$GLB" "$WORK/models/"
# copy sibling textures (if the GLB references external images)
for f in "$(dirname "$GLB")"/*.png "$(dirname "$GLB")"/*.jpg; do [ -f "$f" ] && cp "$f" "$WORK/models/" || true; done
NAME="$(basename "$GLB")"
timeout 600 godot --headless --path "$WORK" --import >/dev/null 2>&1 || true
XV=(xvfb-run -a -s "-screen 0 1280x720x24")
if [ "$MODE" = "shots" ]; then
  mkdir -p "$OUT"
  timeout 600 "${XV[@]}" godot --path "$WORK" --rendering-driver vulkan -- --model="res://models/$NAME" --mode=shots --out="$OUT" --anim="$ANIM" "$@" 2>&1 | grep -E "VIEWER|ERROR" || true
else
  FR=$(python3 -c "print(int(float('$SECS')*30))")
  mkdir -p "$(dirname "$OUT")"
  timeout 1200 "${XV[@]}" godot --path "$WORK" --rendering-driver vulkan --write-movie "$WORK/frames.png" --fixed-fps 30 --quit-after "$FR" -- --model="res://models/$NAME" --mode="$MODE" --anim="$ANIM" "$@" 2>&1 | grep -E "VIEWER|ERROR" || true
  ffmpeg -y -loglevel error -framerate 30 -i "$WORK/frames%08d.png" -c:v libx264 -pix_fmt yuv420p -crf 21 "$OUT"
  echo "VIDEO $OUT"
fi
rm -rf "$WORK"
