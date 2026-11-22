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
const UnitStage = preload("res://src/unit_stage.gd")
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
		var shape := UnitStage.figure(unit)
		var camera := Camera3D.new()
		holder.add_child(camera)
		var aspect := float(size.x) / float(size.y)
		if bust and warrior:
			# Head and shoulders (the rider, with the horse's neck below, for the knight).
			var mounted := drill == "Mounted_Drill"
			var head := {"top": shape.top + 0.02, "bottom": shape.top - (0.78 if mounted else 0.66),
				"box": AABB(Vector3(shape.box.get_center().x - 0.3, shape.top - 0.7, shape.box.get_center().z - 0.3), Vector3(0.6, 0.7, 0.6))}
			UnitStage.frame_camera(camera, head, aspect, 0.96, 0.5)
		elif bust:
			UnitStage.frame_camera(camera, shape, aspect, 1.0, 0.5, 1.02)
		else:
			UnitStage.frame_camera(camera, shape, aspect, 1.0 / 1.06, 0.5)
		camera.make_current()
		UnitStage.light_rig(holder)
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
