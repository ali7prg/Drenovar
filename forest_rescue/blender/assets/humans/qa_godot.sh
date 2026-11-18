#!/usr/bin/env bash
# In-engine check of exported human GLBs: 6 yaw shots + clip video + side-by-side with the sheet.
# Usage: qa_godot.sh <asset_id> [idle_clip] [video_seconds]
set -uo pipefail
ASSET="$1"; IDLE="${2:-}"; SECS="${3:-40}"
REPO="$(cd "$(dirname "$0")/../../../.." && pwd)"
GLB="$REPO/godot/project/assets/forest_rescue/humans/$ASSET.glb"
OUT="$REPO/forest_rescue/qa/video/$ASSET"
CMP="$REPO/forest_rescue/qa/compare/$ASSET"
mkdir -p "$OUT/godot_shots" "$CMP"
if [ -z "$IDLE" ]; then
  case "$ASSET" in lf_squad_*) IDLE=lf_soldier_idle;; *) IDLE=lf_civilian_cage_stand;; esac
fi
"$REPO/forest_rescue/tools/godot_view.sh" "$GLB" shots "$OUT/godot_shots" "$IDLE" 6 --pitch=6 --dist=1.05
"$REPO/forest_rescue/tools/godot_view.sh" "$GLB" clip "$OUT/godot_all_clips.mp4" all "$SECS" --pitch=10 --yaw=30
/opt/tools/blender-venv/bin/python - "$ASSET" "$OUT/godot_shots" "$CMP/godot_vs_sheet.png" <<'PY'
import sys
sys.path.insert(0, sys.argv[0].rsplit('/', 1)[0] if '/' in sys.argv[0] else '.')
import numpy as np
from PIL import Image
asset, shots, out = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, '/home/user/Drenovar/forest_rescue/blender'); sys.path.insert(0, '/home/user/Drenovar/forest_rescue/blender/assets/humans')
import humans_refs as R
p = R.PANELS[asset]
sheet = Image.open('/home/user/Drenovar/forest_rescue/delivery/art/' + p['sheet']).convert('RGB')
H = 520
def fit(im):
    w, h = im.size
    return im.resize((int(w * H / h), H))
tiles = [fit(sheet.crop(p['front'])), fit(Image.open(f'{shots}/shot_yaw000.png').convert('RGB')),
         fit(sheet.crop(p['back'])), fit(Image.open(f'{shots}/shot_yaw180.png').convert('RGB')),
         fit(Image.open(f'{shots}/shot_yaw045.png').convert('RGB'))]
W = sum(t.size[0] for t in tiles) + 8 * len(tiles)
canvas = Image.new('RGB', (W, H), (30, 30, 30))
x = 0
for t in tiles:
    canvas.paste(t, (x, 0)); x += t.size[0] + 8
canvas.save(out)
print('SIDE_BY_SIDE', out)
PY
echo "GODOT_QA_DONE $ASSET"
