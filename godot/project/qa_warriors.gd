extends SceneTree

const Warriors = preload("res://src/warrior_visual.gd")

var checks := 0
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, detail: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(detail)

func run() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	check(data.unitModels.size() == 10, "All ten warrior definitions are required")
	for id in data.unitModels:
		var visual: Dictionary = data.unitModels[id]
		for role in ["preview", "field"]:
			var packed := load(visual[role]) as PackedScene
			check(packed != null, "%s %s model missing" % [id, role])
			if packed == null:
				continue
			var actor := packed.instantiate() as Node3D
			Warriors.prepare(actor)
			var materials := {}
			for part: MeshInstance3D in actor.find_children("*", "MeshInstance3D", true, false):
				for surface in part.mesh.get_surface_count():
					var material := part.get_active_material(surface) as BaseMaterial3D
					if material != null:
						materials[material.get_instance_id()] = material
			check(not materials.is_empty(), "%s %s has no surfaces" % [id, role])
			check(materials.values().all(func(m): return m.has_meta("drenovar_warrior_surface")),
				"%s %s has untreated surfaces" % [id, role])
			var textured: int = materials.values().filter(func(m): return m.albedo_texture != null and m.normal_enabled).size()
			check(textured > 0, "%s %s has no textured PBR surfaces" % [id, role])
			var clips := PackedStringArray()
			for player: AnimationPlayer in actor.find_children("*", "AnimationPlayer", true, false):
				clips.append_array(player.get_animation_list())
			for required in ["Idle", "Walk", visual.drill]:
				check(clips.has(required), "%s %s misses %s" % [id, role, required])
			if role == "preview" and id in ["ENG-05", "ENG-06"]:
				check(clips.has("Recruit_Showcase"), id + " lacks mounted showcase")
			actor.free()
			print(id, " ", role, " · ", materials.size(), " materials, ", textured, " with albedo and normal maps")
			await process_frame
	print("QA_WARRIORS checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
