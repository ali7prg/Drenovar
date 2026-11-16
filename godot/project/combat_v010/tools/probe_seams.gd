extends SceneTree
# Lists looping clips whose last rotation key differs from the first (loop seam) per library.
func _init() -> void:
	for path in OS.get_cmdline_user_args():
		var lib := load(path) as AnimationLibrary
		for clip in lib.get_animation_list():
			var a := lib.get_animation(clip)
			if a.loop_mode == Animation.LOOP_NONE: continue
			var worst := 0.0; var where := ""
			for i in a.get_track_count():
				if a.track_get_type(i) != Animation.TYPE_ROTATION_3D or a.track_get_key_count(i) < 2: continue
				var d: float = (a.track_get_key_value(i,0) as Quaternion).angle_to(a.track_get_key_value(i,a.track_get_key_count(i)-1))
				var last_t := a.track_get_key_time(i, a.track_get_key_count(i)-1)
				if d > worst: worst = d; where = "%s last_key_t=%.3f len=%.3f" % [a.track_get_path(i), last_t, a.length]
			print(path.get_file(), " ", clip, " seam=", snappedf(worst,0.001), " ", where)
	quit()
