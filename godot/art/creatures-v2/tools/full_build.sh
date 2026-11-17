#!/bin/bash
# Full build of one species: geometry (3 LODs) -> textures -> export (GLB/glTF + manifests).
# Usage: PY=<python with bpy 5.3> WORK=<work dir> tools/full_build.sh <species>
set -e
S=$1
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PY=${PY:-python3}
WORK=${WORK:-/tmp/creatures-v2-work}
"$PY" -I "$HERE/build.py" --species "$S" --work "$WORK/$S" --stage all --lods 0,1,2
echo BUILD_DONE $S
