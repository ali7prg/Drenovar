extends SceneTree
## Short in-engine movies of the gameplay layer from the DRENOVAR city camera.
## godot --path godot/project --rendering-driver vulkan --resolution 683x315 \
##   --write-movie /abs/out.avi --fixed-fps 15 -s qa_forest_flow_movie.gd -- --scenario=intro|rescue|boss|route
## (convert: ffmpeg -i out.avi -c:v libx264 -pix_fmt yuv420p out.mp4)

const FIXTURES := "res://data/forest_rescue/game/fixtures/"
const Capture = preload("res://qa_forest_flow_capture.gd")

var game: Node
var forest: Node
var stub: Node

func _initialize() -> void:
	call_deferred("run")

func fixture(name: String) -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(FIXTURES + name + ".json"))

func look(target: Vector3, zoom: float) -> void:
	game.stage.target = target
	game.stage.zoom = zoom
	game.stage.update_camera(0, true)

const FPS := 12.0

## Movie time, not wall time: --fixed-fps renders each frame as 1/FPS s whatever it costs.
func seconds(value: float) -> void:
	for i in int(value * FPS):
		if forest.client.manual_clock_ms >= 0.0:
			forest.client.manual_clock_ms += 1000.0 / FPS
		await process_frame

func fresh(name: String) -> void:
	forest.actors.on_stage_changed()
	forest.actors.first_state = true
	forest.client.adv = {}
	forest.client.primed = false
	var state := fixture(name)
	forest.client.manual_clock_ms = float(state.adventure.serverTime)
	game.accept(state)
	game.battle_results.pending.clear()
	game.result_notice.hide()
	game.close_modal()
	await process_frame

func run() -> void:
	var scenario := "intro"
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--scenario="):
			scenario = argument.trim_prefix("--scenario=")
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	forest = game.forest_game
	stub = Capture.StubHost.new()
	stub.main = game
	root.add_child(stub)
	forest.client.host = stub
	match scenario:
		"intro":
			look(Vector3(5, 0, -4), 70.0)
			stub.replies = [fixture("intro_playing").merged({"events":[{"type":"intro_present", "seq":9001, "revision":1}]})]
			game.accept(fixture("intro_offer"))
			await seconds(14.0)
		"route":
			await fresh("prologue_moving")
			look(Vector3(-12, 6, -59), 30.0)
			await seconds(7.0)
		"rescue":
			await fresh("site01_battle_victory")
			look(Vector3(-20, 6, -66), 22.0)
			await seconds(1.0)
			var opened := fixture("site01_cage_open")
			forest.client.manual_clock_ms = float(opened.adventure.serverTime)
			game.accept(opened)
			game.battle_results.pending.clear()
			game.result_notice.hide()
			game.close_modal()
			await seconds(9.0)
			await fresh("site01_escort_walking")
			look(Vector3(-14, 6, -59), 28.0)
			await seconds(5.0)
		"boss":
			await fresh("boss_battle_10")
			look(Vector3(75, 6, -84), 44.0)
			await seconds(14.0)
	quit(0)
