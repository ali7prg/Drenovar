extends SceneTree
# Delivered animal libraries (.tres, package v0.1.0) -> binary .res runtime copies.
# Content is unchanged: every track path, type, key time and value is compared after
# the round trip. Writes res://combat_v010/reports/animal_library_conversion.json.
const DIR := "res://combat_v010/animations/animals/"
func _init() -> void:
	var rows := []
	var failures := 0
	for f in DirAccess.get_files_at(DIR):
		if not f.ends_with(".tres"): continue
		var src := DIR + f
		var dst := DIR + f.get_basename() + ".res"
		var lib := ResourceLoader.load(src, "", ResourceLoader.CACHE_MODE_IGNORE) as AnimationLibrary
		assert(ResourceSaver.save(lib, dst, ResourceSaver.FLAG_COMPRESS) == OK)
		var back := ResourceLoader.load(dst, "", ResourceLoader.CACHE_MODE_IGNORE) as AnimationLibrary
		var diffs := compare(lib, back)
		failures += diffs
		rows.append({"delivered": src, "delivered_sha256": FileAccess.get_sha256(src), "runtime": dst, "runtime_sha256": FileAccess.get_sha256(dst), "differences": diffs})
		print("CONVERTED ", f, " diffs=", diffs)
	var out := FileAccess.open("res://combat_v010/reports/animal_library_conversion.json", FileAccess.WRITE)
	out.store_string(JSON.stringify({"libraries": rows, "failures": failures}, "  "))
	out.close()
	quit(1 if failures else 0)

static func compare(a: AnimationLibrary, b: AnimationLibrary) -> int:
	var d := 0
	if a.get_animation_list() != b.get_animation_list(): return 1
	for clip in a.get_animation_list():
		var x := a.get_animation(clip); var y := b.get_animation(clip)
		if x.length != y.length or x.loop_mode != y.loop_mode or x.get_track_count() != y.get_track_count(): d += 1; continue
		for i in x.get_track_count():
			if x.track_get_path(i) != y.track_get_path(i) or x.track_get_type(i) != y.track_get_type(i) or x.track_get_key_count(i) != y.track_get_key_count(i):
				d += 1; continue
			for k in x.track_get_key_count(i):
				if x.track_get_key_time(i, k) != y.track_get_key_time(i, k) or x.track_get_key_value(i, k) != y.track_get_key_value(i, k):
					d += 1
	return d
