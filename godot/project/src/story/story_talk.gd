extends Node
## Chapter II talk (build 1025): plays once when the town hall reaches II (also when the upgrade
## finished while the player was away). Danko and grandpa Ostap at the hall talk over the settlement
## map, then the camera goes to the barracks, where the chapter's recruiting goal is done.
## Presentation only; story_flow sends story72 seen chapter2_talk when it ends.

signal finished

const Rig = preload("res://src/forest_rescue/game/actor_rig.gd")
const StoryDialogue = preload("res://src/story/story_dialogue.gd")
const StoryCast = preload("res://src/story/story_cast.gd")
const HUMANS := "res://assets/forest_rescue/humans/"
const VOICE := "res://assets/story/voice/"
## Where the two stand talk, from the hall's plan point, minus the 1.6 m step out below: in front of
## the hall II porch steps (centred on the +Z facade), a little to the east so the barracks across the
## forecourt stays out of the city camera's line.
const HALL_DOOR_OFFSET := Vector3(0.8, 0, 2.4)
const LINES := [
	[0.8, "danko", "c2_dan_dusk", "They moved the prisoners at dusk. I know which trail they took.", "left"],
	[5.6, "ostap", "c2_ost_show", "Show me. We'll need people for the gate and someone to bring the prisoners home.", "right"],
]
const LENGTH := 15.5

var game: Node
var stage: Node3D
var root: Node3D
var layer: CanvasLayer
var dialogue: StoryDialogue
var voice: AudioStreamPlayer
var cast: Dictionary = {}
var t := 0.0
var line_index := 0
var hide_at := -1.0
var running := false
var hall := Vector3.ZERO
var barracks := Vector3.INF
var start_target := Vector3.ZERO
var start_zoom := 68.0
var hud_was_visible := true

func begin(main: Node) -> void:
	game = main
	stage = main.stage
	start_target = stage.target
	start_zoom = stage.zoom
	for marker: Dictionary in stage.place_markers:
		if String(marker.get("kind", "")) != "building" or not marker.get("item") is Dictionary:
			continue
		var type := String(marker.item.get("type", ""))
		var at: Vector3 = marker.position - Vector3(0, 5, 0)
		if type.begins_with("ECO-05"):
			hall = at
		elif type.begins_with("MIL-01") and barracks == Vector3.INF:
			barracks = at
	root = Node3D.new()
	root.name = "StoryTalk"
	stage.add_child(root)
	layer = CanvasLayer.new()
	layer.layer = 30
	add_child(layer)
	var blocker := Control.new()
	blocker.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	blocker.mouse_filter = Control.MOUSE_FILTER_STOP
	blocker.gui_input.connect(func(event: InputEvent) -> void:
		if event is InputEventMouseButton and event.pressed and t > 1.0:
			skip_line())
	layer.add_child(blocker)
	dialogue = StoryDialogue.new()
	layer.add_child(dialogue)
	voice = AudioStreamPlayer.new()
	voice.bus = &"Voice"
	add_child(voice)
	StoryCast.add_portrait_speakers(dialogue, ["danko", "ostap"])
	var ground: Vector3 = stage.ground_point(hall + HALL_DOOR_OFFSET + Vector3(0, 0, 1.6))
	person("danko", "quarry_worker", ground + Vector3(-0.7, 0, 0), deg_to_rad(80.0),
		{"tint": {"cloth": [0.82, 0.86, 0.95], "hair": [0.55, 0.45, 0.4]}})
	person("ostap", "cooper", ground + Vector3(0.8, 0, 0.1), deg_to_rad(-100.0),
		{"tint": {"cloth": [0.9, 0.85, 0.78], "hair": [2.2, 2.2, 2.2]}})
	if "hud" in game and game.hud != null:
		hud_was_visible = game.hud.visible
		game.hud.visible = false
	running = true

func person(id: String, visual: String, at: Vector3, yaw: float, look: Dictionary) -> void:
	var actor := Rig.new()
	actor.variant = look
	actor.setup("talk_" + id, HUMANS + "lf_civilian_%s.glb" % visual)
	root.add_child(actor)
	actor.poll_load(true)
	StoryCast.add_story_clips(actor)
	actor.position = at
	actor.rotation.y = yaw
	actor.play(["lf_civilian_wait", "Idle"], 0.0)
	cast[id] = actor

func skip_line() -> void:
	if hide_at > 0.0:
		hide_at = t
	if line_index >= LINES.size() and t < LENGTH - 3.0:
		t = LENGTH - 3.0

func _process(delta: float) -> void:
	if not running:
		return
	t += delta
	if line_index < LINES.size() and t >= float(LINES[line_index][0]):
		var line: Array = LINES[line_index]
		line_index += 1
		dialogue.show_line(String(line[1]), String(line[3]), String(line[4]))
		(cast[String(line[1])] as Rig).play(["lf_story_talk", "lf_civilian_wait"], 0.3)
		var stream: AudioStream = load(VOICE + String(line[2]) + ".ogg") if ResourceLoader.exists(VOICE + String(line[2]) + ".ogg") else null
		var seconds := 3.5
		if stream != null:
			voice.stream = stream
			voice.play()
			seconds = stream.get_length()
		hide_at = t + seconds + 0.4
	if hide_at > 0.0 and t >= hide_at:
		hide_at = -1.0
		dialogue.hide_line()
		for id in cast:
			(cast[id] as Rig).play(["lf_civilian_wait", "Idle"], 0.3)
	dialogue.tick(delta)
	# Camera: the hall door (the two of them) → the barracks (where the squad is raised).
	var close := hall + HALL_DOOR_OFFSET + Vector3(0, 0, 1.6)
	var prep := barracks if barracks != Vector3.INF else hall
	var k := smoothstep(11.0, 14.5, t)
	var opening := smoothstep(0.0, 1.2, t)
	var target := start_target.lerp(close, opening).lerp(prep, k)
	var zoom := exp(lerpf(lerpf(log(start_zoom), log(12.0), opening), log(30.0), k))
	stage.target = Vector3(target.x, stage.target.y, target.z)
	stage.zoom = zoom
	stage.camera_target = stage.target
	stage.camera_zoom = zoom
	stage.apply_camera_pose()
	stage.refresh_camera_visibility(false)
	if t >= LENGTH:
		finish()

func finish() -> void:
	running = false
	if "hud" in game and game.hud != null:
		game.hud.visible = hud_was_visible
	if is_instance_valid(root):
		root.queue_free()
	finished.emit()
	queue_free()
