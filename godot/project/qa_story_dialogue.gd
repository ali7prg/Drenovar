extends SceneTree
## Story dialogue look check (QA, not shipped): the dialogue overlay over a still of the real map, one
## shot per speaker, at the window size (1366×630 or iPhone 12 landscape 2532×1170):
##   xvfb-run -s "-screen 0 2532x1170x24" godot --path . --rendering-driver vulkan --rendering-method mobile \
##     --resolution 2532x1170 -s qa_story_dialogue.gd -- --back=/abs/map_still.jpg --out=/abs/dir

const StoryDialogue = preload("res://src/story/story_dialogue.gd")
const StoryCast = preload("res://src/story/story_cast.gd")

var back_path := ""
var out_dir := ""

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--back="):
			back_path = arg.trim_prefix("--back=")
		elif arg.begins_with("--out="):
			out_dir = arg.trim_prefix("--out=")
	call_deferred("run")

func run() -> void:
	var canvas := Control.new()
	canvas.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(canvas)
	var back := TextureRect.new()
	back.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	back.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	back.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	var image := Image.load_from_file(back_path)
	if image != null:
		back.texture = ImageTexture.create_from_image(image)
	canvas.add_child(back)
	var dialogue := StoryDialogue.new()
	canvas.add_child(dialogue)
	StoryCast.add_portrait_speakers(dialogue, ["orc", "tenerys", "danko", "mitya", "ostap", "vesna"])
	var lines := [
		["orc", "They're running for the birch trail. It's the only way out. Close it!", "left"],
		["tenerys", "Not the trail. Through the ferns. I'll be there first.", "right"],
		["danko", "An orc keeps a cage in the birch clearing. The bars drain your strength.", "left"],
		["mitya", "Grandpa, look at his wrist. Bar marks.", "right"],
		["ostap", "How many?", "right"],
		["vesna", "I'll pack the bread.", "right"],
	]
	for line in lines:
		dialogue.show_line(line[0], line[1], line[2])
		for i in 150:
			dialogue.tick(1.0 / 30.0)
			await process_frame
		await RenderingServer.frame_post_draw
		DirAccess.make_dir_recursive_absolute(out_dir)
		root.get_texture().get_image().save_jpg(out_dir.path_join("dialogue_%s.jpg" % line[0]), 0.92)
		print("DIALOGUE shot ", line[0])
	quit()
