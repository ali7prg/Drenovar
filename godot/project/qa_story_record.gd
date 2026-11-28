extends SceneTree
## Records the story intro as the player sees it (QA, not shipped): boots the real game against a
## server (local V6 fixture with the story module), lets story_flow start the intro for the new
## settlement by itself, keeps recording a few seconds of the hand-off (quest flag on the town hall
## view) and quits. Run with Movie Maker for a frame-exact video with sound:
##   xvfb-run -s "-screen 0 2532x1170x24" godot --path . --rendering-driver vulkan --rendering-method mobile \
##     --resolution 2532x1170 --fixed-fps 30 --write-movie /abs/intro.avi -s qa_story_record.gd -- \
##     --server=http://127.0.0.1:8800 --marks=/abs/marks.txt
## marks.txt gets the drawn-frame numbers of the intro start/end (to trim the loading frames).

var game: Node
var marks_path := ""
var marks: PackedStringArray = []
var tail_frames := 150

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--marks="):
			marks_path = arg.trim_prefix("--marks=")
		elif arg.begins_with("--tail="):
			tail_frames = int(arg.trim_prefix("--tail="))
	call_deferred("run")

func mark(text: String) -> void:
	var line := "%s frame=%d" % [text, Engine.get_frames_drawn()]
	print("RECORD ", line)
	marks.append(line)
	if not marks_path.is_empty():
		var file := FileAccess.open(marks_path, FileAccess.WRITE)
		file.store_string("\n".join(marks) + "\n")

func run() -> void:
	game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 1800000
	while Time.get_ticks_msec() < deadline:
		var flow: Node = game.get("story_flow")
		if flow != null and flow.intro != null and is_instance_valid(flow.intro):
			break
		await process_frame
	var intro: Node = game.story_flow.intro if game.get("story_flow") != null else null
	if intro == null or not is_instance_valid(intro):
		mark("NO_INTRO")
		quit(1)
		return
	mark("intro_begin")
	while is_instance_valid(intro) and intro.t < 0.0:
		await process_frame
	mark("intro_t0")
	var finished := false
	intro.finished.connect(func(_skipped: bool) -> void: finished = true)
	while not finished:
		await process_frame
	mark("intro_end")
	for i in tail_frames:
		await process_frame
	mark("tail_end flag=%s title=%s" % [str(game.story_flow.flag.visible), game.story_flow.flag_title.text])
	quit(0)
