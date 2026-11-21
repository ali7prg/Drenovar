# Source this file: `. godot/art-source/eng-squad/pipeline/env.sh`
# Paths can be overridden from the environment before sourcing.
#
# Tools used by the ENG squad pipeline:
#   * Godot 4.6.3 stable (official Linux build)  -> $GODOT
#   * Blender 5.3 as a Python module (pip install bpy==5.3.0, Python 3.13) -> $BPY
#
# Inside the cloud session the tools live in the session scratchpad:
#   $SCRATCH/tools/Godot_v4.6.3-stable_linux.x86_64
#   $SCRATCH/tools/bpyenv/bin/python
# On another machine set GODOT and BPY to local installs.

export DRENOVAR_REPO="${DRENOVAR_REPO:-/home/user/Drenovar}"
export SCRATCH="${SCRATCH:-/tmp/claude-0/-home-user-Drenovar/dc23197d-7c86-57a6-832d-f8df16e285f2/scratchpad}"
export GODOT="${GODOT:-$SCRATCH/tools/Godot_v4.6.3-stable_linux.x86_64}"
export BPY="${BPY:-$SCRATCH/tools/bpyenv/bin/python}"
export PROJECT="$DRENOVAR_REPO/godot/project"
export SQUAD="$DRENOVAR_REPO/godot/art-source/eng-squad"
export REFS="$SQUAD/references"
export WORK="${WORK:-$SCRATCH/work}"
mkdir -p "$WORK"

# Software Vulkan (Mesa lavapipe) for rendering Godot frames without a GPU.
godot_render() {
	# usage: godot_render <WxH> <script-or-args...>
	local res="$1"; shift
	env -u VK_DRIVER_FILES VK_ICD_FILENAMES=/opt/lavapipe/lvp_icd.json \
	GALLIVM_PERF=no_aos_sampling LP_PERF=no_rast_linear \
	xvfb-run -a -s "-screen 0 1920x1080x24" \
		"$GODOT" --path "$PROJECT" --rendering-driver vulkan --rendering-method mobile \
		--resolution "$res" --audio-driver Dummy "$@"
}

godot_headless() {
	"$GODOT" --headless --path "$PROJECT" --audio-driver Dummy "$@"
}

# Blender: always run with -I (isolated) and pass script arguments after "--".
#   "$BPY" -I path/to/script.py -- arg1 arg2
# Cycles CPU is the default preview/comparison renderer (about 1 s for 400x400 @16 spp).
# EEVEE also works through lavapipe (export VK_ICD_FILENAMES=/opt/lavapipe/lvp_icd.json), but is slow.
