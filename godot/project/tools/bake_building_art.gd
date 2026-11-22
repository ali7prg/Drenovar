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
##
## Framing (polish pass 4): the cards draw the building rising out of the card's top edge, so
## the picture is close on the building. Each type's tile shrinks to the building's footprint
## (with a margin of turf), the camera comes down to CARD_VIEW (about 23 degrees above the
## ground instead of 30, so the turf foreshortens and the building stands taller) and the view
## fits that tile and the building: the building fills as much of the picture as its yard
## allows and the tile is a base under it, not a lawn round it. The soil bottom sits at BOTTOM
## and the tile is centred across. The empty tile keeps the full-size framing of
## the live upgrade view (its placeholder there; src/building_stage.gd ART_SHARE).

const BuildingStage = preload("res://src/building_stage.gd")
const RENDER := Vector2i(1040, 1040)
## Framing shared by every card: the tile spans this share of the width, its soil bottom sits
## this far down the picture, and the view keeps room for a building this tall.
const SHARE := 0.94
const BOTTOM := 0.975
## Close framing: free space at each side and at the top (fractions of the picture), turf
## round the footprint (metres) and the smallest tile (fraction of the full one).
const SIDE_MARGIN := 0.035
const TOP_MARGIN := 0.02
const TURF := 1.1
const MIN_TILE := 0.4
const CARD_VIEW := Vector3(0.82, 0.55, 1.0)
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
	var shrink := 1.0
	var camera := Camera3D.new()
	holder.add_child(camera)
	camera.make_current()
	if scene != null:
		var model := BuildingStage.place_building(holder, scene, scale)
		height = BuildingStage.model_height(model)
		shrink = close_framing(camera, holder, tile, model)
		# The smaller view needs denser shadow maps.
		var key := holder.find_child("Key", true, false) as DirectionalLight3D
		if key != null:
			key.directional_shadow_max_distance = 60.0
			key.shadow_blur = 1.2
	else:
		BuildingStage.aim(camera, Vector3.ZERO, float(RENDER.x) / RENDER.y, SHARE, BOTTOM)
	for i in 6:
		await process_frame
	await RenderingServer.frame_post_draw
	var image := viewport.get_texture().get_image()
	image.save_png(out.path_join(type + ".png"))
	viewport.queue_free()
	await process_frame
	print("BAKED ", type, " height=", snappedf(height, 0.01), " tile=", snappedf(shrink, 0.01))
	return {"height": snappedf(height, 0.01), "tile": snappedf(shrink, 0.01)}

## Shrinks the tile to the building's footprint and aims the camera close (see the header).
## Returns the tile's scale.
func close_framing(camera: Camera3D, holder: Node3D, tile: Node3D, model: Node3D) -> float:
	var reach := 0.0
	for part: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		if part.mesh == null or not part.visible:
			continue
		var box: AABB = (holder.global_transform.affine_inverse() * part.global_transform) * part.get_aabb()
		for corner in 8:
			var p := box.get_endpoint(corner)
			# Parts on the ground count for the footprint; roofs overhang.
			reach = maxf(reach, Vector2(p.x, p.z).length() * (1.0 if p.y < 1.5 else 0.8))
	var shrink := clampf((reach + TURF) / (BuildingStage.TILE_HALF * 1.05), MIN_TILE, 1.0)
	tile.scale = Vector3(shrink, 0.45 + 0.55 * shrink, shrink)
	var direction := CARD_VIEW.normalized()
	var right := Vector3.UP.cross(direction).normalized()
	var basis := [right, direction.cross(right).normalized(), direction]
	var low := Vector2(INF, INF)
	var high := Vector2(-INF, -INF)
	for corner in 48:
		var angle := TAU * float(corner) / 48.0
		var r := BuildingStage.outline(angle, 0) * 1.01 * shrink
		for y: float in [0.0, (-BuildingStage.TILE_DEPTH - 0.3) * tile.scale.y]:
			var p := Vector3(cos(angle) * r, y, sin(angle) * r)
			var at := Vector2(p.dot(basis[0] as Vector3), p.dot(basis[1] as Vector3))
			low = low.min(at)
			high = high.max(at)
	for part: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		if part.mesh == null or not part.visible:
			continue
		var box: AABB = (holder.global_transform.affine_inverse() * part.global_transform) * part.get_aabb()
		for corner in 8:
			var p := box.get_endpoint(corner)
			var at := Vector2(p.dot(basis[0] as Vector3), p.dot(basis[1] as Vector3))
			low.x = minf(low.x, at.x)
			high = high.max(at)
	var half := maxf(-low.x, high.x)
	var view := maxf(2.0 * half / (1.0 - 2.0 * SIDE_MARGIN), (high.y - low.y) / (BOTTOM - TOP_MARGIN))
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.keep_aspect = Camera3D.KEEP_HEIGHT
	camera.size = view
	camera.near = 0.5
	camera.far = 400.0
	var target: Vector3 = (basis[1] as Vector3) * (low.y + (BOTTOM - 0.5) * view)
	camera.position = target + (basis[2] as Vector3) * 120.0
	camera.look_at(target, Vector3.UP)
	return shrink
