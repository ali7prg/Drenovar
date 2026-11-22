extends SceneTree
## Bakes the card art of the construction strip (premium UI stage 3, ui_premium/STAGE3.md) from
## our own 3D models: for every V6 building type, the level-I scene the city draws, on the turf
## diorama tile, with the light rig and orthographic three-quarter camera of the live upgrade
## view (src/building_stage.gd), on a transparent background with 4x MSAA. Also bakes the
## empty tile (the placeholder of the live view while its scenes load).
##   VK_ICD_FILENAMES=/opt/lavapipe/lvp_icd.json xvfb-run -a -s "-screen 0 1280x1024x24" \
##     godot --path godot/project --rendering-driver vulkan --rendering-method mobile \
##     -s res://tools/bake_building_art.gd -- --out=/tmp/building_art [--only=B01,B02] [--level=1]
##   python3 godot/art/ui/buildings/finish_art.py /tmp/building_art godot/project/assets/ui/buildings/v6
## Renders at RENDER px; the finisher downsizes (premultiplied Lanczos) to the card size.

const BuildingStage = preload("res://src/building_stage.gd")
const RENDER := Vector2i(1040, 1040)
## Framing shared by every card: the tile spans this share of the width, its soil bottom sits
## this far down the picture, and the view keeps room for a building this tall.
const SHARE := 0.94
const BOTTOM := 0.975
var out := "/tmp/building_art"
var only: PackedStringArray = []
var level := 1

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out = arg.trim_prefix("--out=")
		elif arg.begins_with("--only="):
			only = arg.trim_prefix("--only=").split(",")
		elif arg.begins_with("--level="):
			level = int(arg.trim_prefix("--level="))
	call_deferred("run")

func run() -> void:
	DirAccess.make_dir_recursive_absolute(out)
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var v6: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://assets/city/architecture-v6/manifest.json"))
	if v6 is Dictionary:
		for type: String in v6.get("levels", {}):
			data.levelModels.get_or_add(type, {}).merge(v6.levels[type], false)
	var report := {}
	var types: Array = []
	for index in range(1, 28):
		types.append("B%02d" % index)
	if only.is_empty() or "tile" in only:
		await bake("tile", null, 1.0)
	for type: String in types:
		if not only.is_empty() and type not in only:
			continue
		var visual := BuildingStage.level_visual(data, BuildingStage.runtime_type(data, type), level)
		if visual.is_empty() or not ResourceLoader.exists(str(visual[0])):
			push_error("bake_building_art: no level scene for " + type)
			continue
		report[type] = await bake(type, load(str(visual[0])) as PackedScene, float(visual[1]))
	print("BAKE_BUILDING_ART ", out, " ", JSON.stringify(report))
	quit(0)

func bake(type: String, scene: PackedScene, scale: float) -> Dictionary:
	var viewport := SubViewport.new()
	viewport.size = RENDER
	viewport.own_world_3d = true
	viewport.transparent_bg = true
	viewport.msaa_3d = Viewport.MSAA_4X
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(viewport)
	var holder := Node3D.new()
	viewport.add_child(holder)
	BuildingStage.light_rig(holder)
	var tile := BuildingStage.make_tile(hash(type) % 97)
	holder.add_child(tile)
	var height := 0.0
	if scene != null:
		var model := BuildingStage.place_building(holder, scene, scale)
		height = BuildingStage.model_height(model)
	var camera := Camera3D.new()
	holder.add_child(camera)
	camera.make_current()
	BuildingStage.aim(camera, Vector3.ZERO, float(RENDER.x) / RENDER.y, SHARE, BOTTOM)
	for i in 6:
		await process_frame
	await RenderingServer.frame_post_draw
	var image := viewport.get_texture().get_image()
	image.save_png(out.path_join(type + ".png"))
	viewport.queue_free()
	await process_frame
	print("BAKED ", type, " height=", snappedf(height, 0.01))
	return {"height": snappedf(height, 0.01)}
