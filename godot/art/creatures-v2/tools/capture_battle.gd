extends "res://combat_v010/tools/record_battle.gd"
# Same recorder; saves a PNG of each rendered frame (for --times / --only stills).
var shot := 0
func _initialize() -> void:
	super._initialize()
	process_frame.connect(_save)
func _save() -> void:
	if not args.has("png"):
		return
	await RenderingServer.frame_post_draw
	var img := root.get_texture().get_image()
	if img != null and shot > 2:
		img.save_png("%s_%03d.png" % [args.png, shot])
	shot += 1
