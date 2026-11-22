extends SceneTree

# Market (ECO-03) captures in the running game for the drawing / game sheet (build 59):
# the market on its plot in a grown town, through the game's own state path (present).
#   xvfb-run -s "-screen 0 1100x760x24" godot --rendering-driver opengl3 --path . \
#     -s profile_market_views.gd -- --out=/abs/dir [--levels=3,4,5] [--tag=after]
# Views per level:
#   drawing  - the reference camera of the drawings: in front of the entrance (+Z),
#              about 28 degrees down, near-orthographic, plot filling the frame
#   close    - the city camera (45 degrees to the facade, 38 down) at zoom 30
#   game     - the city camera at the normal gameplay zoom (68)
#   top      - straight down, for the plan (round square, passages)

const PLOT := "v1-5"
const CLEAR_RADIUS := 24.0
const DRAWING_PITCH := 28.0

func _initialize() -> void:
	call_deferred("run")

func plot_at(data: Dictionary, id: String) -> Vector3:
	for plot in data.plots:
		if plot.id == id:
			return Vector3(float(plot.x), 0, float(plot.z))
	return Vector3.ZERO

func state_with(data: Dictionary, level: int) -> Dictionary:
	var state: Dictionary = data.demo.duplicate(true)
	var city: Dictionary = state.city
	city.buildings = [{"id": "building-hall", "type": "ECO-05", "plotId": "v1-0", "level": 5},
		{"id": "building-market", "type": "ECO-03", "plotId": PLOT, "level": level}]
	city.kingdom.clearedPlots = ["v1-0", PLOT]
	var at := plot_at(data, PLOT)
	var felled: Array = []
	for tree in data.woods:
		var p: Array = tree.p
		if Vector2(float(p[0]) - at.x, float(p[2]) - at.z).length() < CLEAR_RADIUS:
			felled.append(tree.id)
	city.progress.felled = felled
	return state

func frame(path: String, square := false) -> void:
	for i in 12:
		await process_frame
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	if square:
		var side := image.get_height()
		image = image.get_region(Rect2i((image.get_width() - side) / 2, 0, side, side))
	image.save_png(path)
	print("CAPTURE ", path)

static func drawing_camera(stage, at: Vector3, size: float, pitch := DRAWING_PITCH, yaw := 0.0) -> void:
	## Front camera of the reference drawings (orthographic like the city camera).
	var dir := Vector3(0, sin(deg_to_rad(pitch)), cos(deg_to_rad(pitch))).rotated(Vector3.UP, deg_to_rad(yaw))
	var look := at + Vector3(0, 2.0, 0.4)
	stage.camera.size = size
	stage.camera.position = look + dir * 120.0
	stage.camera.look_at(look, Vector3.UP)

func run() -> void:
	var out := "user://captures"
	var tag := "market"
	var levels := [4, 5]
	var views := ["drawing", "close", "game", "top"]
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out = arg.trim_prefix("--out=")
		elif arg.begins_with("--tag="):
			tag = arg.trim_prefix("--tag=")
		elif arg.begins_with("--levels="):
			levels = Array(arg.trim_prefix("--levels=").split(",")).map(func(v): return int(v))
		elif arg.begins_with("--views="):
			views = Array(arg.trim_prefix("--views=").split(","))
	DirAccess.make_dir_recursive_absolute(out)
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.smoke = true
	var stage = game.stage
	var at := plot_at(game.data, PLOT)
	for level in levels:
		game.state = state_with(game.data, level)
		stage.present(game.state)
		for view in views:
			# phone landscape (the project's 1366 x 630); the drawing views are cut square
			# from the middle of the frame (the drawings are square)
			DisplayServer.window_set_size(Vector2i(1366, 630))
			root.size = Vector2i(1366, 630)
			stage.target = at
			stage.zoom = 30.0 if view == "close" else 68.0
			stage.update_camera(0, true)
			stage.update_visible_batches()
			if view == "drawing":
				drawing_camera(stage, at, 14.0)
			elif view == "top":
				drawing_camera(stage, at, 16.5, 89.5)
			await frame("%s/%s_%s_L%d.png" % [out, tag, view, level], view in ["drawing", "top"])
	quit(0)
