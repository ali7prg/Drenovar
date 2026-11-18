extends SceneTree
# Loop seam of the clips embedded in the given model scenes (source comparison).
func _init() -> void:
	for path in OS.get_cmdline_user_args():
		var m := (load(path) as PackedScene).instantiate()
		var ap := m.find_children("*","AnimationPlayer",true,false)[0] as AnimationPlayer
		for clip in ap.get_animation_list():
			var a := ap.get_animation(clip)
			var worst := 0.0; var where := ""
			for i in a.get_track_count():
				if a.track_get_type(i) != Animation.TYPE_ROTATION_3D or a.track_get_key_count(i) < 2: continue
				var d: float = (a.track_get_key_value(i,0) as Quaternion).angle_to(a.track_get_key_value(i,a.track_get_key_count(i)-1))
				if d > worst: worst = d; where = str(a.track_get_path(i))
			print(path.get_file(), " ", clip, " len=", a.length, " seam=", snappedf(worst,0.001), " ", where)
		m.free()
	quit()
