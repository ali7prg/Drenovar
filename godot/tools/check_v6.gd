extends SceneTree
func _initialize() -> void:
	var failed := false
	for path: String in ["res://src/v6_panels.gd", "res://src/main.gd", "res://src/landscape.gd"]:
		var script: Script = load(path)
		if script == null or not script.can_instantiate():
			push_error("V6_SCRIPT_FAILED " + path)
			failed = true
	if not failed:
		print("V6_SCRIPTS_OK")
	quit(1 if failed else 0)
