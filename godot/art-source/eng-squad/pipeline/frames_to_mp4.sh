#!/usr/bin/env bash
# Encode qa_eng_squad_capture.gd frames into an H.264 MP4 (yuv420p, faststart).
#
# usage: frames_to_mp4.sh <capture_dir|frames_dir> <out.mp4> [fps] [width] [crf]
#   fps   default: telemetry.json fps / --every (falls back to 30)
#   width default: 1366 (height keeps aspect, even number)
#   crf   default: 23  (raise to 26-28 to stay under ~3 MB for 10 s clips)
set -euo pipefail
src="${1:?capture dir}"
out="${2:?output mp4}"
width="${4:-1366}"
crf="${5:-23}"
dir="$src"
[ -d "$src/frames" ] && dir="$src/frames"
fps="${3:-}"
if [ -z "$fps" ]; then
	tele="$(dirname "$dir")/telemetry.json"
	[ -f "$src/telemetry.json" ] && tele="$src/telemetry.json"
	if [ -f "$tele" ]; then
		fps="$(python3 -c 'import json,sys; h=json.load(open(sys.argv[1]))["header"]; o=h.get("options",{}); print(float(h.get("time",{}).get("fps",30))/max(1,int(o.get("every","1"))))' "$tele")"
	else
		fps=30
	fi
fi
ext=png
ls "$dir"/f_*.jpg >/dev/null 2>&1 && ext=jpg
count=$(ls "$dir"/f_*."$ext" 2>/dev/null | wc -l)
[ "$count" -gt 0 ] || { echo "no frames f_*.$ext in $dir" >&2; exit 1; }
mkdir -p "$(dirname "$out")"
ffmpeg -y -loglevel error -framerate "$fps" -pattern_type glob -i "$dir/f_*.$ext" \
	-vf "scale=${width}:-2:flags=lanczos,format=yuv420p" -c:v libx264 -preset slow -crf "$crf" \
	-movflags +faststart "$out"
echo "$out: $count frames @ ${fps} fps, $(du -h "$out" | cut -f1)"
