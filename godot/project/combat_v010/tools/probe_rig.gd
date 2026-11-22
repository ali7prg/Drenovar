extends SceneTree
# Prints AnimationPlayer root, skeleton path, bone names/rests and clip list of the given models.
func _init() -> void:
	for path in OS.get_cmdline_user_args():
		var m := (load(path) as PackedScene).instantiate()
		var ap := m.find_children("*","AnimationPlayer",true,false)[0] as AnimationPlayer
		var root := ap.get_node(ap.root_node)
		print("== ", path, " root=", m.get_path_to(root), " clips=", ap.get_animation_list())
		for sk: Skeleton3D in m.find_children("*","Skeleton3D",true,false):
			var names := []
			for b in sk.get_bone_count():
				names.append("%s(%s)%s" % [sk.get_bone_name(b), sk.get_bone_parent(b), sk.get_bone_rest(b).origin.snappedf(0.001)])
			print("  skel ", root.get_path_to(sk), " n=", sk.get_bone_count(), " ", " ".join(names))
		m.free()
	quit()
