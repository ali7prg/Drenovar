extends SceneTree
## Bakes the unit portraits of the premium UI (ui_premium/STAGE2.md) from our own 3D models:
## the same preview meshes and materials the recruitment stage shows, one consistent 3/4
## camera, a three-point light (warm key, cool fill, rim), transparent background.
## Rendered at 2-3x the final size; godot/art/ui/units/finish_portraits.py downsizes them
## (premultiplied Lanczos) into res://assets/ui/units/<id>.webp (full figure, cards) and
## <id>-bust.webp (head and shoulders, queues, army, small slots).
##   VK_ICD_FILENAMES=/opt/lavapipe/lvp_icd.json xvfb-run -a -s "-screen 0 1280x1024x24" \
##     godot --path godot/project --rendering-driver vulkan --rendering-method mobile \
##     -s res://tools/bake_unit_portraits.gd -- --out=/tmp/unit_portraits
##   python3 godot/art/ui/units/finish_portraits.py /tmp/unit_portraits godot/project/assets/ui/units
## The ram scene is built by CI (godot/art/buildings-v6/build.gd --only=SIEGE-RAM-01); the bake
## builds its mesh from the same recipe when the scene is not on disk.

const WarriorVisual = preload("res://src/warrior_visual.gd")
const PORTRAIT := Vector2i(576, 704)   # final 288 x 352
const BUST := Vector2i(384, 384)       # final 128 x 128
var out := "/tmp/unit_portraits"

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out = arg.trim_prefix("--out=")
	call_deferred("run")

func run() -> void:
	DirAccess.make_dir_recursive_absolute(out)
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var ids: Array = data.unitModels.keys()
	ids.sort()
	for id: String in ids:
		await bake(id, load(str(data.unitModels[id].preview)) as PackedScene, str(data.unitModels[id].drill))
	await bake("SIEGE-RAM-01", ram_scene(), "")
	print("BAKE_UNIT_PORTRAITS ", out)
	quit(0)

func ram_scene() -> PackedScene:
	var path := "res://assets/city/architecture-v6/units/SIEGE-RAM-01.tscn"
	if ResourceLoader.exists(path):
		return load(path)
	var Kit = load("res://tools/architecture/arch_kit.gd")
	var Recipes = load("res://../art/buildings-v6/recipes.gd")
	var kit = Kit.new(hash("SIEGE-RAM-01"))
	Recipes.ram_display(kit, Vector3.ZERO)
	var root := Node3D.new()
	var visual := MeshInstance3D.new()
	visual.mesh = kit.bake()
	root.add_child(visual)
	visual.owner = root
	var scene := PackedScene.new()
	scene.pack(root)
	root.free()
	return scene

func bake(id: String, scene: PackedScene, drill: String) -> void:
	for bust: bool in [false, true]:
		var size := BUST if bust else PORTRAIT
		var viewport := SubViewport.new()
		viewport.size = size
		viewport.own_world_3d = true
		viewport.transparent_bg = true
		viewport.msaa_3d = Viewport.MSAA_4X
		viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		root.add_child(viewport)
		var holder := Node3D.new()
		viewport.add_child(holder)
		var unit := scene.instantiate() as Node3D
		var warrior := id.begins_with("ENG-")
		if warrior:
			WarriorVisual.prepare(unit)
		holder.add_child(unit)
		if not warrior:
			# The ram faces +Z like the troops; turned a little more to show its length.
			unit.rotation_degrees.y = -28.0
		pose(unit, "Recruit_Showcase" if drill == "Mounted_Drill" else "Idle")
		await process_frame
		var bounds := AABB()
		for part: MeshInstance3D in unit.find_children("*", "MeshInstance3D", true, false):
			var box := part.global_transform * part.get_aabb()
			bounds = box if not bounds.has_volume() else bounds.merge(box)
		var camera := Camera3D.new()
		holder.add_child(camera)
		# One 3/4 view for every unit: from the front-right, a little above the chest.
		var direction := Vector3(0.62, 0.2, 1.0).normalized()
		camera.fov = 24.0
		var aspect := float(size.x) / float(size.y)
		var target := bounds.get_center()
		var extent := bounds.size.y * 0.5
		if bust:
			# Head and shoulders (the rider and the horse's head for the knight).
			var height := bounds.size.y
			target = Vector3(bounds.get_center().x, bounds.position.y + height * (0.8 if warrior and drill != "Mounted_Drill" else 0.74), bounds.get_center().z)
			extent = height * (0.2 if drill != "Mounted_Drill" else 0.26)
			if not warrior:
				target = bounds.get_center()
				extent = bounds.size.y * 0.55
		else:
			extent = maxf(extent, maxf(bounds.size.x, bounds.size.z) * 0.5 / aspect) * 1.06
		var distance := extent / tan(deg_to_rad(camera.fov * 0.5))
		camera.position = target + direction * distance
		camera.look_at(target)
		camera.make_current()
		lights(holder)
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var image := viewport.get_texture().get_image()
		image.save_png(out.path_join(id + ("-bust" if bust else "") + ".png"))
		viewport.queue_free()
		await process_frame

func pose(unit: Node3D, clip: String) -> void:
	for player: AnimationPlayer in unit.find_children("*", "AnimationPlayer", true, false):
		var chosen := ""
		for name: String in player.get_animation_list():
			if clip.to_lower() in name.to_lower():
				chosen = name
		if chosen.is_empty():
			continue
		player.play(chosen)
		player.seek(player.get_animation(chosen).length * 0.25, true)
		player.pause()

# Warm key from the upper left, cool fill from the right, bright rim from behind.
func lights(parent: Node3D) -> void:
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-38, -32, 0)
	key.light_color = Color("#ffe7c7")
	key.light_energy = 1.75
	key.shadow_enabled = true
	key.shadow_blur = 1.5
	parent.add_child(key)
	var fill := DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-12, 62, 0)
	fill.light_color = Color("#c6d6ea")
	fill.light_energy = 0.42
	parent.add_child(fill)
	var rim := DirectionalLight3D.new()
	rim.rotation_degrees = Vector3(-22, 160, 0)
	rim.light_color = Color("#fff0d6")
	rim.light_energy = 1.35
	parent.add_child(rim)
	var world := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_CLEAR_COLOR
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("#d3d6d4")
	env.ambient_light_energy = 0.42
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = 1.0
	WarriorVisual.add_reflections(env, Color("#8b9874"))
	env.background_mode = Environment.BG_CLEAR_COLOR
	world.environment = env
	parent.add_child(world)
