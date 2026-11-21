#!/usr/bin/env bash
# Standard ENG squad capture set (stage 01 "before"; rerun later with --models=... for "after").
#
# usage: capture_squad_set.sh <out_dir> [set] [extra capture args...]
#   set: all (default) | units | mix | armory | city | video
#   extra args go to qa_eng_squad_capture.gd, e.g. --models=$SQUAD/pipeline/models_stage11.json
# Each capture writes <out_dir>/<name>/frames + telemetry.json and a line in <out_dir>/run.log.
# Then: python3 <work>/make_sheets.py-like composition, pipeline/frames_to_mp4.sh <out_dir>/VID_* out.mp4
set -u
. "$(dirname "$0")/env.sh"
OUT="${1:?out dir}"; shift
SET="${1:-all}"; [ $# -gt 0 ] && shift
EXTRA=("$@")
mkdir -p "$OUT"
LOG="$OUT/run.log"
cd "$PROJECT"
run() {
	local name="$1"; shift
	if [ -f "$OUT/$name/telemetry.json" ]; then echo "skip $name" >> "$LOG"; return; fi
	local t0=$(date +%s)
	godot_render 1366x630 --fixed-fps 30 -s qa_eng_squad_capture.gd -- --out="$OUT/$name" "$@" "${EXTRA[@]}" > "$OUT/$name.log" 2>&1
	echo "$name exit=$? $(( $(date +%s) - t0 ))s $(grep -o 'ENG_CAPTURE_OK.*' "$OUT/$name.log")" >> "$LOG"
}
MIX="ENG-01:3,ENG-02:3,ENG-03:3,ENG-04:3,ENG-06:2"
if [ "$SET" = all ] || [ "$SET" = units ]; then
	for u in ENG-01 ENG-02 ENG-03 ENG-04 ENG-06; do
		for cam in battle close; do
			run "U3_${u}_march_${cam}" --map=world --units="$u:3" --scenario=march --camera=$cam --heading=45 --turn=60 \
				--speed=1.2 --seconds=2 --every=20 --warmup=1
			run "U3_${u}_battle_${cam}" --map=world --units="$u:3" --scenario=battle --camera=$cam --heading=90 \
				--speed=1.2 --approach=0.5 --seconds=4 --every=10 --warmup=1
		done
	done
fi
if [ "$SET" = all ] || [ "$SET" = mix ]; then
	for cam in battle close; do
		run "MIX_march_${cam}" --map=world --units="$MIX" --scenario=march --camera=$cam --heading=90 --turn=60 --speed=1.2 --seconds=2 --every=20 --warmup=1
		run "MIX_battle_${cam}" --map=world --units="$MIX" --scenario=battle --camera=$cam --heading=90 --speed=1.2 --approach=0.5 --seconds=4 --every=10 --warmup=1
	done
fi
if [ "$SET" = all ] || [ "$SET" = armory ]; then
	run "armory" --scenario=armory --units=ENG-01:1,ENG-02:1,ENG-03:1,ENG-04:1,ENG-06:1 --phases=0,0.25,0.5,0.75
fi
if [ "$SET" = all ] || [ "$SET" = city ]; then
	run "MIX_city_battle_battle" --map=city --units="$MIX" --scenario=battle --camera=battle --speed=1.2 --approach=0.5 --seconds=3 --every=15 --warmup=1
	run "MIX_city_battle_close" --map=city --units="$MIX" --scenario=battle --camera=close --speed=1.2 --approach=0.5 --seconds=3 --every=15 --warmup=1
fi
if [ "$SET" = all ] || [ "$SET" = video ]; then
	run "VID_march_close" --map=world --units="$MIX" --scenario=march --camera=close --heading=90 --turn=60 --speed=1.2 --seconds=6 --every=1 --warmup=1 --format=jpg
	run "VID_battle_close" --map=world --units="$MIX" --scenario=battle --camera=close --heading=90 --speed=1.2 --approach=1.5 --seconds=6 --deaths=1 --every=1 --warmup=1 --format=jpg
fi
echo "SET $SET DONE" >> "$LOG"
