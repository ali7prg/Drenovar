extends SceneTree

# Bakes far-LOD impostor images of the six forest tree variants (mid LOD meshes):
# a side view (256x512) and a top view (256x256) per variant, unlit albedo with the
# baked vertex AO, on a transparent background. Output: forest60-far.png (1536x768).
#   xvfb-run godot --rendering-driver opengl3 --path godot/project -s ../art/forest/bake_impostors.gd -- OUT.png

const SIDE := Vector2i(256, 512)
const TOP := Vector2i(256, 256)

func _initialize() -> void:
	call_deferred("run")

func render(model: Node3D, size: Vector2i, top: bool, extent: Vector3) -> Image:
	var viewport := SubViewport.new()
	viewport.size = size * 2
	viewport.transparent_bg = true
	viewport.debug_draw = Viewport.DEBUG_DRAW_UNSHADED
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	viewport.msaa_3d = Viewport.MSAA_4X
	root.add_child(viewport)
	var holder := Node3D.new()
	viewport.add_child(holder)
	holder.add_child(model)
	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	holder.add_child(camera)
	if top:
		camera.size = extent.x * 2.0
		camera.position = Vector3(0, extent.y + 5, 0)
		camera.rotation_degrees = Vector3(-90, 0, 0)
	else:
		# The tile is 1:2, so the vertical size also has to fit the crown's full width.
		var frame := maxf(extent.y, extent.x * 4.0)
		camera.size = frame
		camera.position = Vector3(0, frame * 0.5, extent.x + 10)
	camera.current = true
	for i in 4:
		await process_frame
	await RenderingServer.frame_post_draw
	var image := viewport.get_texture().get_image()
	image.resize(size.x, size.y, Image.INTERPOLATE_LANCZOS)
	viewport.queue_free()
	return image

func run() -> void:
	var out: String = OS.get_cmdline_user_args()[0]
	var atlas := Image.create_empty(SIDE.x * 6, SIDE.y + TOP.y, false, Image.FORMAT_RGBA8)
	var sizes := {}
	for v in 6:
		var path := "res://assets/city/forest60/tree%dmid-v60.glb" % v
		var scene: PackedScene = load(path)
		var probe: Node3D = scene.instantiate()
		root.add_child(probe)
		var box := AABB()
		for mesh: MeshInstance3D in probe.find_children("*", "MeshInstance3D", true, false):
			box = mesh.get_aabb() if box.size == Vector3.ZERO else box.merge(mesh.get_aabb())
		probe.queue_free()
		# Square-ish horizontal extent, full height from the ground.
		var half := maxf(maxf(absf(box.position.x), absf(box.end.x)), maxf(absf(box.position.z), absf(box.end.z)))
		var extent := Vector3(half, maxf(box.end.y, half * 2.0), half)
		# [side card height (width is half of it), top card half-width]
		sizes[v] = [maxf(extent.y, half * 4.0), half]
		var side := await render(scene.instantiate(), SIDE, false, extent)
		atlas.blit_rect(side, Rect2i(Vector2i.ZERO, SIDE), Vector2i(v * SIDE.x, 0))
		var top := await render(scene.instantiate(), TOP, true, extent)
		atlas.blit_rect(top, Rect2i(Vector2i.ZERO, TOP), Vector2i(v * SIDE.x, SIDE.y))
	atlas.save_png(out)
	var info := FileAccess.open(out.get_basename() + ".json", FileAccess.WRITE)
	info.store_string(JSON.stringify(sizes))
	print("IMPOSTOR_SIZES ", JSON.stringify(sizes))
	quit()
