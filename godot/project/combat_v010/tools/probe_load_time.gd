extends SceneTree
# Load time of the given resources (cold, headless desktop CPU).
func _init() -> void:
	for p in OS.get_cmdline_user_args():
		var t := Time.get_ticks_usec(); var r := ResourceLoader.load(p, "", ResourceLoader.CACHE_MODE_IGNORE)
		print("LOAD ", p, " ", (Time.get_ticks_usec()-t)/1000.0, " ms ", r != null)
	quit()
