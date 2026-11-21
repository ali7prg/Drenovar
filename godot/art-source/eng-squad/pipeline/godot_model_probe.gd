extends SceneTree
# ENG squad pipeline · imported-scene probe (Godot 4.6.3, works headless).
# Writes JSON with node tree, skeleton, clips (in get_animation_list order), mesh surfaces,
# Godot-generated mesh LODs (edge lengths, index counts), materials/textures as imported and
# sampled bone tracks (model space) of every clip for gait analysis (gait_analysis.py).
# usage:
#   "$GODOT" --headless --path "$PROJECT" -s "$SQUAD/pipeline/godot_model_probe.gd" -- --out=/abs/probe.json \
#       [--ids=ENG-01,ENG-06] [--roles=preview,field] [--sample=ENG-01,ENG-06] [--hz=60] [--models=override.json]
#   --models uses the qa_eng_squad_capture.gd format {"ENG-01": {"field": "res://...", "preview": "res://..."}}
#   then: python3 lod_table.py probe.json lod.json ; python3 gait_analysis.py probe.json gait.json

var out_path := ""
var sample_ids := PackedStringArray(["ENG-01", "ENG-02", "ENG-03", "ENG-04", "ENG-06", "ENG-05", "ENG-07", "ENG-09"])
var hz := 60.0
var ids := PackedStringArray()
var roles := PackedStringArray(["preview", "field"])
var models_override := ""

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out_path = arg.trim_prefix("--out=")
		elif arg.begins_with("--sample="):
			sample_ids = arg.trim_prefix("--sample=").split(",")
		elif arg.begins_with("--hz="):
			hz = float(arg.trim_prefix("--hz="))
		elif arg.begins_with("--ids="):
			ids = arg.trim_prefix("--ids=").split(",")
		elif arg.begins_with("--roles="):
			roles = arg.trim_prefix("--roles=").split(",")
		elif arg.begins_with("--models="):
			models_override = arg.trim_prefix("--models=")
	call_deferred("run")

func v3(v: Vector3) -> Array:
	return [snappedf(v.x, 0.0001), snappedf(v.y, 0.0001), snappedf(v.z, 0.0001)]

func texture_info(t: Texture2D) -> Variant:
	if t == null:
		return null
	var info := {"class": t.get_class(), "path": t.resource_path, "width": t.get_width(), "height": t.get_height()}
	var img := t.get_image()
	if img != null:
		info.format = img.get_format()
		info.format_name = ["L8","LA8","R8","RG8","RGB8","RGBA8","RGBA4444","RGB565","RF","RGF","RGBF","RGBAF","RH","RGH","RGBH","RGBAH","RGBE9995","DXT1","DXT3","DXT5","RGTC_R","RGTC_RG","BPTC_RGBA","BPTC_RGBF","BPTC_RGBFU","ETC","ETC2_R11","ETC2_R11S","ETC2_RG11","ETC2_RG11S","ETC2_RGB8","ETC2_RGBA8","ETC2_RGB8A1","ETC2_RA_AS_RG","DXT5_RA_AS_RG","ASTC_4x4","ASTC_4x4_HDR","ASTC_8x8","ASTC_8x8_HDR"][img.get_format()] if img.get_format() < 39 else str(img.get_format())
		info.mipmaps = img.get_mipmap_count()
		info.bytes = img.get_data_size()
	return info

func material_info(m: Material) -> Dictionary:
	var info := {"class": m.get_class() if m else "null", "name": m.resource_name if m else ""}
	if m is BaseMaterial3D:
		var b := m as BaseMaterial3D
		info.transparency = b.transparency
		info.cull_mode = b.cull_mode
		info.shading_mode = b.shading_mode
		info.albedo_color = b.albedo_color.to_html()
		info.metallic = b.metallic
		info.roughness = b.roughness
		info.normal_enabled = b.normal_enabled
		info.albedo_texture = texture_info(b.albedo_texture)
		info.normal_texture = texture_info(b.normal_texture) if b.normal_enabled else null
		info.roughness_texture = texture_info(b.roughness_texture)
		info.metallic_texture = texture_info(b.metallic_texture)
		info.ao_enabled = b.ao_enabled
		info.vertex_color_use_as_albedo = b.vertex_color_use_as_albedo
	return info

func surface_lods(mesh: Mesh, surface: int) -> Dictionary:
	var res := {}
	var rid := mesh.get_rid()
	var d: Dictionary = RenderingServer.mesh_get_surface(rid, surface)
	res.keys = d.keys()
	res.vertex_count = int(d.get("vertex_count", -1))
	res.index_count = int(d.get("index_count", -1))
	var index_bytes := 2 if res.vertex_count <= 65535 else 4
	var lods: Array = []
	for lod in d.get("lods", []):
		if lod is Dictionary:
			lods.append({"edge_length": float(lod.get("edge_length", 0.0)), "index_count": (lod.get("index_data", PackedByteArray()) as PackedByteArray).size() / index_bytes})
	res.lods = lods
	if d.has("bone_aabbs"):
		res.bone_aabbs = (d.bone_aabbs as Array).size()
	res.format = int(d.get("format", 0))
	return res

func node_tree(n: Node, depth: int, rows: Array) -> void:
	var row := {"depth": depth, "name": String(n.name), "class": n.get_class()}
	if n is Skeleton3D:
		row.bones = (n as Skeleton3D).get_bone_count()
	if n is MeshInstance3D:
		var mi := n as MeshInstance3D
		row.skin = mi.skin != null
		row.skeleton = String(mi.skeleton)
	if n is BoneAttachment3D:
		row.bone = (n as BoneAttachment3D).bone_name
	rows.append(row)
	for c in n.get_children():
		node_tree(c, depth + 1, rows)

func run() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	if not models_override.is_empty():
		var text := models_override if models_override.begins_with("{") else FileAccess.get_file_as_string(models_override)
		var parsed: Dictionary = JSON.parse_string(text)
		for id in parsed:
			if not data.unitModels.has(id):
				data.unitModels[id] = {"preview": "", "field": "", "drill": "Idle"}
			for key in parsed[id]:
				data.unitModels[id][key] = parsed[id][key]
	var report := {"godot": Engine.get_version_info().string, "rendering": RenderingServer.get_current_rendering_method(), "adapter": RenderingServer.get_video_adapter_name(), "models": {}}
	for id in data.unitModels:
		if not ids.is_empty() and not (id in ids):
			continue
		for role in roles:
			var path: String = data.unitModels[id][role]
			var packed := load(path) as PackedScene
			var actor := packed.instantiate() as Node3D
			get_root().add_child(actor)
			var entry := {"id": id, "role": role, "path": path, "drill": data.unitModels[id].drill}
			var rows: Array = []
			node_tree(actor, 0, rows)
			entry.tree = rows
			entry.bone_attachments = actor.find_children("*", "BoneAttachment3D", true, false).size()
			var skeletons := actor.find_children("*", "Skeleton3D", true, false)
			var sk: Skeleton3D = skeletons[0] if not skeletons.is_empty() else null
			if sk:
				var bones: Array = []
				for b in sk.get_bone_count():
					bones.append({"name": sk.get_bone_name(b), "parent": sk.get_bone_parent(b), "rest_origin": v3(sk.get_bone_rest(b).origin), "global_rest": v3(sk.get_bone_global_rest(b).origin)})
				entry.skeleton = {"path": String(actor.get_path_to(sk)), "bones": bones, "transform_to_root": v3(sk.transform.origin), "basis_scale": v3(sk.global_transform.basis.get_scale())}
			var players := actor.find_children("*", "AnimationPlayer", true, false)
			var clips: Array = []
			for p: AnimationPlayer in players:
				entry.player = {"path": String(actor.get_path_to(p)), "root_node": String(p.root_node), "libraries": p.get_animation_library_list(), "default_blend": p.playback_default_blend_time}
				for name in p.get_animation_list():
					var a := p.get_animation(name)
					var tracks := {}
					for t in a.get_track_count():
						var tt := a.track_get_type(t)
						tracks[tt] = tracks.get(tt, 0) + 1
					clips.append({"name": name, "length": a.length, "loop_mode": a.loop_mode, "step": a.step, "tracks": a.get_track_count(), "track_types": tracks})
			entry.clips = clips
			var meshes: Array = []
			var totals := {"vertices": 0, "triangles": 0, "surfaces": 0}
			var lod_tris := {}
			var materials := {}
			for mi: MeshInstance3D in actor.find_children("*", "MeshInstance3D", true, false):
				if mi.mesh == null:
					continue
				var m := {"node": String(mi.name), "surfaces": [], "aabb": [v3(mi.get_aabb().position), v3(mi.get_aabb().size)], "shadow_mesh": mi.mesh.shadow_mesh != null if mi.mesh is ArrayMesh else false}
				for s in mi.mesh.get_surface_count():
					var info := surface_lods(mi.mesh, s)
					var mat := mi.get_active_material(s)
					info.material = mat.resource_name if mat else ""
					m.surfaces.append(info)
					totals.surfaces += 1
					totals.vertices += max(0, info.vertex_count)
					totals.triangles += max(0, info.index_count) / 3
					for k in info.lods.size():
						lod_tris[k] = lod_tris.get(k, 0) + int(info.lods[k].index_count) / 3
					if mat:
						materials[mat.get_instance_id()] = mat
				meshes.append(m)
			entry.meshes = meshes
			entry.totals = totals
			entry.lod_triangles = lod_tris
			var mats: Array = []
			var tex := {}
			for m in materials.values():
				var mi_info := material_info(m)
				mats.append(mi_info)
				for key in ["albedo_texture", "normal_texture", "roughness_texture", "metallic_texture"]:
					if mi_info.get(key) is Dictionary:
						tex[mi_info[key].path] = mi_info[key]
			entry.materials = mats
			entry.textures = tex.values()
			var tex_bytes := 0
			for t in tex.values():
				tex_bytes += int(t.get("bytes", 0))
			entry.texture_bytes = tex_bytes
			# bone tracks
			if sk and not players.is_empty() and (id in sample_ids) and role == "field":
				var p: AnimationPlayer = players[0]
				var watch := ["Hips", "Head", "Neck", "Chest", "LeftFoot", "RightFoot", "LeftToe", "RightToe", "LeftHand", "RightHand", "LeftUpperArm", "RightUpperArm",
					"HorseRoot", "HorseBack", "HorseHead", "FrontLHoof", "FrontRHoof", "HindLHoof", "HindRHoof"]
				var idx := {}
				for name in watch:
					var b := sk.find_bone(name)
					if b >= 0:
						idx[name] = b
				var samples := {}
				for clip in p.get_animation_list():
					if clip == "RESET":
						continue
					var a := p.get_animation(clip)
					p.play(clip)
					p.pause()
					var frames: Array = []
					var n := int(ceil(a.length * hz)) + 1
					for f in n:
						var t := minf(a.length, f / hz)
						p.seek(t, true)
						var row := {"t": snappedf(t, 0.0001)}
						for name in idx:
							var g: Transform3D = sk.global_transform * sk.get_bone_global_pose(idx[name])
							var local_g: Transform3D = actor.global_transform.affine_inverse() * g
							row[name] = v3(local_g.origin)
						frames.append(row)
					samples[clip] = {"length": a.length, "frames": frames}
				entry.samples = samples
			report.models["%s/%s" % [id, role]] = entry
			actor.queue_free()
			await process_frame
	var f := FileAccess.open(out_path, FileAccess.WRITE)
	f.store_string(JSON.stringify(report, " "))
	f.close()
	print("MODEL_PROBE_OK ", report.models.size(), " ", RenderingServer.get_current_rendering_method())
	quit(0)
