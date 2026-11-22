extends RefCounted
## Versioned feature flag for the «Лес потерянных» world layer.
##
## Resolution order (first match wins):
##   1. test override `set_override()` (QA scripts only),
##   2. command line user arg `--forest-rescue-v1=on|off` (after `--`),
##   3. user setting `[features] forest_rescue_v1` in user://drenovar-settings.cfg,
##   4. compiled default DEFAULT_ENABLED.
## OFF = rollback: landscape.gd builds the legacy city forest byte-identically and no
## ForestWorld node exists (stage.forest_world == null).

const FLAG_ID := "forest_rescue_v1"
const FLAG_VERSION := 1
const DEFAULT_ENABLED := true
const SETTINGS_PATH := "user://drenovar-settings.cfg"
const SECTION := "features"

static var _override := -1


static func enabled() -> bool:
	if _override >= 0:
		return _override == 1
	for arg in OS.get_cmdline_user_args():
		var value := ""
		if arg.begins_with("--forest-rescue-v1="):
			value = arg.trim_prefix("--forest-rescue-v1=")
		elif arg.begins_with("--forest_rescue_v1="):
			value = arg.trim_prefix("--forest_rescue_v1=")
		if value in ["off", "0", "false", "legacy"]:
			return false
		if value in ["on", "1", "true"]:
			return true
	var config := ConfigFile.new()
	if config.load(SETTINGS_PATH) == OK:
		return bool(config.get_value(SECTION, FLAG_ID, DEFAULT_ENABLED))
	return DEFAULT_ENABLED


## Persist the user's choice (takes effect the next time the city scene is built).
static func set_enabled(on: bool) -> void:
	var config := ConfigFile.new()
	config.load(SETTINGS_PATH)
	config.set_value(SECTION, FLAG_ID, on)
	config.set_value(SECTION, FLAG_ID + "_version", FLAG_VERSION)
	config.save(SETTINGS_PATH)


## -1 clears, 0 forces OFF, 1 forces ON. For QA scripts only.
static func set_override(value: int) -> void:
	_override = value


# ============================================================================================
# 1022: lazy forest layers. Neither layer is compiled with main.tscn any more (each costs about 0.3 s
# of GDScript compilation, which made the 1022 launch four times slower than 1021). main.gd creates
# the game layer and ForestGame attaches the world layer only after the city is interactive and only
# when the server projects state.adventure: with the adventure off nothing below is ever loaded.
# They load one resource per frame, leaves first, so no frame carries a whole layer's compilation.
# qa_forest_world checks that each list holds every resource its script preloads (transitively).

const GAME_LAYER_SCRIPT := "res://src/forest_rescue/game/forest_game.gd"
const WORLD_LAYER_SCRIPT := "res://src/forest_rescue/world/forest_world.gd"

const GAME_LAYER := [
	"res://src/forest_rescue/game/adventure_content.gd",
	"res://src/forest_rescue/game/adventure_client.gd",
	"res://assets/ui/NotoSerif-Regular.ttf",
	"res://src/forest_rescue/game/hud_style.gd",
	"res://src/forest_rescue/game/hud_art.gd",
	"res://src/forest_rescue/game/adventure_hud.gd",
	"res://src/forest_rescue/game/adventure_panels.gd",
	"res://src/forest_rescue/game/mechanism_ui.gd",
	"res://src/forest_rescue/game/intro_director.gd",
	"res://src/forest_rescue/world/forest_wind.gdshader",
	"res://src/forest_rescue/world/forest_wind_cutout.gdshader",
	"res://src/forest_rescue/world/forest_kit.gd",
	"res://src/creature_v2.gdshader",
	"res://src/creature_visuals.gd",
	"res://src/forest_rescue/game/actor_rig.gd",
	"res://src/forest_rescue/game/path_motion.gd",
	"res://src/forest_rescue/game/boss_telegraphs.gd",
	"res://src/forest_rescue/game/actor_director.gd",
	"res://src/forest_rescue/game/reward_fx.gd",
	"res://src/forest_rescue/game/adventure_audio.gd",
	GAME_LAYER_SCRIPT,
]

const WORLD_LAYER := [
	"res://src/forest_rescue/world/forest_masks.gd",
	"res://src/forest_rescue/world/forest_atlas.gd",
	"res://src/forest_rescue/world/forest_terrain.gd",
	"res://src/forest_rescue/world/forest_wind.gdshader",
	"res://src/forest_rescue/world/forest_wind_cutout.gdshader",
	"res://src/forest_rescue/world/forest_kit.gd",
	"res://src/forest_rescue/world/forest_canopy.gd",
	"res://src/forest_rescue/world/forest_fog.gdshader",
	"res://src/forest_rescue/world/forest_fog.gd",
	"res://src/forest_rescue/world/forest_landmarks.gd",
	"res://src/forest_rescue/world/forest_impostor.gdshader",
	"res://src/forest_rescue/world/forest_impostors.gd",
	"res://src/forest_rescue/world/forest_layout_rules.gd",
	"res://src/forest_rescue/world/forest_wind_fade.gdshader",
	"res://src/forest_rescue/world/forest_wind_cutout_fade.gdshader",
	"res://src/forest_rescue/world/forest_occluders.gd",
	"res://src/forest_rescue/world/forest_water.gdshader",
	"res://src/forest_rescue/world/forest_waterfall.gdshader",
	"res://src/forest_rescue/world/forest_water.gd",
	"res://src/forest_rescue/world/forest_quarry.gd",
	"res://src/forest_rescue/world/forest_ground.gdshader",
	"res://src/forest_rescue/world/forest_path.gdshader",
	"res://src/forest_rescue/world/forest_river.gdshader",
	WORLD_LAYER_SCRIPT,
]

static var _eager_override := -1
static var staged_last := ""   # entry probe: the resource load_staged() loaded last


## QA / capture tools only: `-- --forest-eager` (or set_eager(true)) builds both layers the 1021+forest
## way (game layer in main._ready, world layer inside the city build). Players never get it.
static func eager() -> bool:
	if _eager_override >= 0:
		return _eager_override == 1
	return "--forest-eager" in OS.get_cmdline_user_args()


static func set_eager(value: int) -> void:
	_eager_override = value


## Loads `paths` one per frame (already cached ones cost nothing and take no frame). With a gate (main's
## prewarm_may_continue: no finger down, camera still, a quiet moment) each load waits for the player to be idle.
static func load_staged(paths: Array, tree: SceneTree, gate := Callable()) -> void:
	for path in paths:
		if ResourceLoader.has_cached(path):
			continue
		while gate.is_valid() and not gate.call():
			await tree.process_frame
		staged_last = path
		load(path)
		await tree.process_frame
	staged_last = ""
