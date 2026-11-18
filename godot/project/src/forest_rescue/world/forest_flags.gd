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
