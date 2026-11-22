extends Control
## The city behind the construction strip (premium UI stage 3, ui_premium/STAGE3.md): the
## player's own settlement, blurred, dimmed and warmed, so the strip reads as a layer over the
## town rather than a separate screen.
##
## Cost rules: the blur is made once, not per frame.
## - On open, a small SubViewport (one sixth of the device resolution) renders the city once
##   from a copy of the city camera; a second one of the same size, which holds the first,
##   renders it once through a 7x7 Gaussian (nested viewports render before their parent, so
##   both are ready in the same frame).
## - On screen the result is one textured quad with a light grade and a warm vignette
##   (city_backdrop.gdshader), stretched with bilinear filtering. While the strip is up, the
##   window's root viewport skips the 3D pass of the city entirely (main.cover_city).
## - The viewports stay (a few hundred KiB) and are re-rendered on the next open.

const SHADER := preload("res://src/city_backdrop.gdshader")
const BLUR := preload("res://src/city_blur.gdshader")
## Snapshot resolution as a fraction of the device resolution.
const SCALE := 1.0 / 6.0

var soft: SubViewport
var snap: SubViewport
var snap_camera: Camera3D
var picture: TextureRect
var blur_rect: TextureRect
var fade: Tween
var ready_frames := 0
## Emitted once the blurred snapshot is on screen (the city's 3D pass may stop).
signal settled

func _ready() -> void:
	name = "CityBackdrop"
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	picture = TextureRect.new()
	picture.name = "Blurred"
	picture.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	picture.stretch_mode = TextureRect.STRETCH_SCALE
	picture.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	picture.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var grade := ShaderMaterial.new()
	grade.shader = SHADER
	picture.material = grade
	add_child(picture)
	hide()

func snapshot_size() -> Vector2i:
	var device := Vector2(get_viewport().get_visible_rect().size) * get_viewport().get_final_transform().get_scale()
	return Vector2i(maxi(64, roundi(device.x * SCALE)), maxi(32, roundi(device.y * SCALE)))

func build_viewports() -> void:
	soft = SubViewport.new()
	soft.name = "BlurViewport"
	soft.disable_3d = true
	soft.transparent_bg = false
	soft.render_target_update_mode = SubViewport.UPDATE_DISABLED
	add_child(soft)
	snap = SubViewport.new()
	snap.name = "CityViewport"
	snap.render_target_update_mode = SubViewport.UPDATE_DISABLED
	snap.msaa_3d = Viewport.MSAA_DISABLED
	snap.positional_shadow_atlas_size = 0
	soft.add_child(snap)
	snap_camera = Camera3D.new()
	snap_camera.name = "SnapCamera"
	snap.add_child(snap_camera)
	blur_rect = TextureRect.new()
	blur_rect.name = "Blur"
	blur_rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	blur_rect.stretch_mode = TextureRect.STRETCH_SCALE
	blur_rect.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	var blur := ShaderMaterial.new()
	blur.shader = BLUR
	blur_rect.material = blur
	soft.add_child(blur_rect)
	blur_rect.texture = snap.get_texture()
	picture.texture = soft.get_texture()

## Takes the snapshot from `camera` and fades the backdrop in (over the live city).
func open(camera: Camera3D, instant := false) -> void:
	if fade != null:
		fade.kill()
	show()
	picture.modulate.a = 0.0
	var live := is_instance_valid(camera) and camera.is_inside_tree() and DisplayServer.get_name() != "headless"
	(picture.material as ShaderMaterial).set_shader_parameter("plain", not live)
	if live:
		if soft == null:
			build_viewports()
		var pixels := snapshot_size()
		snap.size = pixels
		soft.size = pixels
		blur_rect.size = Vector2(pixels)
		snap.world_3d = camera.get_world_3d()
		snap_camera.projection = camera.projection
		snap_camera.fov = camera.fov
		snap_camera.size = camera.size
		snap_camera.keep_aspect = camera.keep_aspect
		snap_camera.near = camera.near
		snap_camera.far = camera.far
		snap_camera.h_offset = camera.h_offset
		snap_camera.v_offset = camera.v_offset
		snap_camera.cull_mask = camera.cull_mask
		snap_camera.environment = camera.environment
		snap_camera.attributes = camera.attributes
		snap_camera.global_transform = camera.global_transform
		snap_camera.current = true
		(blur_rect.material as ShaderMaterial).set_shader_parameter("texel", Vector2(1.0 / pixels.x, 1.0 / pixels.y))
		snap.render_target_update_mode = SubViewport.UPDATE_ONCE
		soft.render_target_update_mode = SubViewport.UPDATE_ONCE
		picture.texture = soft.get_texture()
		# Shown once the snapshot exists (the same frame's post-draw), so the fade never
		# starts from an old picture.
		await RenderingServer.frame_post_draw
		if not visible:
			return
	if instant:
		picture.modulate.a = 1.0
		settled.emit()
		return
	fade = create_tween()
	fade.tween_property(picture, "modulate:a", 1.0, 0.16).set_trans(Tween.TRANS_SINE)
	fade.finished.connect(func(): settled.emit())

## Fades out over the live city (the caller turns the city's 3D pass back on first).
func close(seconds := 0.0) -> void:
	if fade != null:
		fade.kill()
	if seconds <= 0.0 or not visible:
		hide()
		return
	fade = create_tween()
	fade.tween_property(picture, "modulate:a", 0.0, seconds).set_trans(Tween.TRANS_SINE)
	fade.finished.connect(hide)
