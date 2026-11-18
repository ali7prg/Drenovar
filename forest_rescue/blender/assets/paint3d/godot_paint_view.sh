#!/usr/bin/env bash
# Painted-light QA viewer (v2 kit): godot_paint_view.sh <model.glb> <out_dir> [viewer args...]
# e.g. --painted=0.4 --pitches=55,55,55,55,0 --yaws=0,90,180,270,0 --ground=1 --only=_v1_LOD0
set -euo pipefail
GLB="$(readlink -f "$1")"; OUT="$2"; shift 2
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d /tmp/frpaintviewer.XXXXXX)"
cp -r "$HERE/godot_paint_viewer/." "$WORK/"
mkdir -p "$WORK/models"; cp "$GLB" "$WORK/models/"
for f in "$(dirname "$GLB")"/*.png "$(dirname "$GLB")"/*.jpg; do [ -f "$f" ] && cp "$f" "$WORK/models/" || true; done
NAME="$(basename "$GLB")"
timeout 900 godot --headless --path "$WORK" --import >/dev/null 2>&1 || true
mkdir -p "$OUT"
timeout 600 xvfb-run -a -s "-screen 0 1280x720x24" godot --path "$WORK" --rendering-driver vulkan -- --model="res://models/$NAME" --mode=shots --out="$OUT" "$@" 2>&1 | grep -E "VIEWER|ERROR|SHADER" || true
rm -rf "$WORK"
