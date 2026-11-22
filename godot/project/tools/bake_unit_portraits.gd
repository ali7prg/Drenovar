extends SceneTree
## Bakes the unit portraits of the premium UI (ui_premium/STAGE2.md) from our own 3D models:
## the same preview meshes and materials the recruitment stage shows, one consistent 3/4
## camera, the stage's light rig (warm key, cool fill, warm rim, cool kicker), transparent
## background. Rendered at 2-3x the final size; godot/art/ui/units/finish_portraits.py
## downsizes them (premultiplied Lanczos) into res://assets/ui/units/<id>.webp (full figure,
## cards) and <id>-bust.webp (head and shoulders, queues, army, small slots), and copies
## framing.json: each unit's silhouette in the camera plane, measured on the posed unit over
## its whole stage animation, weapons included (skinned meshes only report their rest pose,
## so the stage cannot measure a raised lance itself).
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
const MEASURE := Vector2i(320, 480)    # silhouette probe (orthographic)
const SAMPLES := 8
var out := "/tmp/unit_portraits"
var framing := {}

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
	var file := FileAccess.open(out.path_join("framing.json"), FileAccess.WRITE)
	file.store_string(JSON.stringify(framing, "\t", true))
	file.close()
	print("BAKE_UNIT_PORTRAITS ", out, " ", JSON.stringify(framing))
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

func stage_unit(id: String, scene: PackedScene, parent: Node3D) -> Node3D:
	var unit := scene.instantiate() as Node3D
	var warrior := id.begins_with("ENG-")
	if warrior:
		WarriorVisual.prepare(unit)
	UnitStage.stage_materials(unit)
	parent.add_child(unit)
	if not warrior:
		# The ram faces +Z like the troops; turned a little more to show its length.
		unit.rotation_degrees.y = -28.0
	return unit

## The posed silhouette over the stage animation (SAMPLES poses), seen along the stage view
## with an orthographic camera: metres in the camera plane from the centre of the feet.
func measure(id: String, scene: PackedScene, clip: String) -> Dictionary:
	var viewport := SubViewport.new()
	viewport.size = MEASURE
	viewport.own_world_3d = true
	viewport.transparent_bg = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(viewport)
	var holder := Node3D.new()
	viewport.add_child(holder)
	var unit := stage_unit(id, scene, holder)
	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	holder.add_child(camera)
	camera.make_current()
	var ambient := WorldEnvironment.new()
	ambient.environment = Environment.new()
	ambient.environment.background_mode = Environment.BG_CLEAR_COLOR
	ambient.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	ambient.environment.ambient_light_color = Color.WHITE
	holder.add_child(ambient)
	var axes := UnitStage.axes()
	var ext := {"up": [INF, -INF], "right": [INF, -INF]}
	var span := 9.0 if id == "SIEGE-RAM-01" else 6.0
	camera.size = span
	for sample in SAMPLES:
		pose(unit, clip, float(sample) / SAMPLES)
		await process_frame
		var shape := UnitStage.figure(unit)
		var feet := Vector3(shape.box.get_center().x, shape.bottom, shape.box.get_center().z)
		# The feet sit low in the frame so a raised lance stays inside.
		var target: Vector3 = feet + axes[1] * span * 0.3
		camera.position = target + axes[2] * 30.0
		camera.look_at(target)
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var image := viewport.get_texture().get_image()
		var used := image.get_used_rect()
		if used.size == Vector2i.ZERO:
			continue
		var metre := span / float(MEASURE.y)
		# Pixel -> metres from the feet (the frame centre is `target`, 0.3 span above them).
		var up_hi := (MEASURE.y * 0.5 - used.position.y) * metre + span * 0.3
		var up_lo := (MEASURE.y * 0.5 - used.end.y) * metre + span * 0.3
		var r_lo := (used.position.x - MEASURE.x * 0.5) * metre
		var r_hi := (used.end.x - MEASURE.x * 0.5) * metre
		ext.up = [minf(ext.up[0], up_lo), maxf(ext.up[1], up_hi)]
		ext.right = [minf(ext.right[0], r_lo), maxf(ext.right[1], r_hi)]
	viewport.queue_free()
	await process_frame
	for key: String in ext:
		ext[key] = [snappedf(ext[key][0], 0.01), snappedf(ext[key][1], 0.01)]
	return ext

func bake(id: String, scene: PackedScene, drill: String) -> void:
	var clip := "Recruit_Showcase" if drill == "Mounted_Drill" else "Idle"
	var ext := await measure(id, scene, clip)
	framing[id] = ext
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
		var unit := stage_unit(id, scene, holder)
		var warrior := id.begins_with("ENG-")
		pose(unit, clip, 0.25)
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
			# The card portrait: the stage's framing rule without the plinth, so the stage can
			# place it exactly where the live model will stand.
			# Cards keep the figure large: the silhouette is cut a little above the helmet, so
			# a raised lance leaves the card (the stage shows it whole).
			var feet := Vector3(shape.box.get_center().x, shape.bottom, shape.box.get_center().z)
			var card := {"up": [ext.up[0], minf(float(ext.up[1]), snappedf((shape.top - shape.bottom) * 0.985 + 0.1, 0.01))], "right": ext.right}
			framing[id]["card"] = card
			var visible_height := UnitStage.fit(card, aspect, UnitStage.PORTRAIT_TOP, UnitStage.PORTRAIT_FEET, UnitStage.PORTRAIT_WIDTH)
			UnitStage.aim(camera, feet, card, visible_height, UnitStage.PORTRAIT_FEET)
		camera.make_current()
		UnitStage.light_rig(holder)
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var image := viewport.get_texture().get_image()
		image.save_png(out.path_join(id + ("-bust" if bust else "") + ".png"))
		viewport.queue_free()
		await process_frame

func pose(unit: Node3D, clip: String, at := 0.25) -> void:
	for player: AnimationPlayer in unit.find_children("*", "AnimationPlayer", true, false):
		var chosen := ""
		for name: String in player.get_animation_list():
			if clip.to_lower() in name.to_lower():
				chosen = name
		if chosen.is_empty():
			continue
		player.play(chosen)
		player.seek(player.get_animation(chosen).length * at, true)
		player.pause()
