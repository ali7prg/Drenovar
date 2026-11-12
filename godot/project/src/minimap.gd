extends Control

signal location_chosen(location: Vector2)

var terrain: ImageTexture
var map_layer := Control.new()
var cities: Array = []
var encounters: Array = []
var armies: Array = []
var player_id := ""
var focus := Vector2.ZERO

func setup(bytes: PackedByteArray) -> void:
	custom_minimum_size = Vector2(120, 96)
	terrain = ImageTexture.create_from_image(Image.create_from_data(260, 208, false, Image.FORMAT_RGBA8, bytes))
	mouse_filter = Control.MOUSE_FILTER_STOP
	map_layer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	map_layer.show_behind_parent = true
	add_child(map_layer)
	map_layer.draw.connect(draw_static_map)
	resized.connect(map_layer.queue_redraw)

func update_locations(next_cities: Array, next_encounters: Array, next_player: String) -> void:
	if cities == next_cities and encounters == next_encounters and player_id == next_player:
		return
	cities = next_cities
	encounters = next_encounters
	player_id = next_player
	map_layer.queue_redraw()

func on_map(p: Vector2) -> Vector2:
	return (p + Vector2(150, 120)) / Vector2(300, 240) * size

func draw_static_map() -> void:
	if terrain == null:
		return
	map_layer.draw_texture_rect(terrain, Rect2(Vector2.ZERO, size), false)
	for city in cities:
		var p := Vector2(city.position.x, city.position.z)
		map_layer.draw_circle(on_map(p), 2.4, Color("#f5d083") if city.id == player_id else Color("#dce9df"), true, -1, true)
	for encounter in encounters:
		if encounter.status != "defeated" and int(encounter.get("hp", 1)) > 0:
			map_layer.draw_circle(on_map(Vector2(encounter.position.x, encounter.position.z)), 1.6, Color("#e79979"))

func _draw() -> void:
	for army in armies:
		var p := Vector2(army.position.x, army.position.z)
		draw_circle(on_map(p), 2.0, Color("#bde6ff"))
	draw_arc(on_map(focus), 4.5, 0.0, TAU, 16, Color("#fff0c5"), 1.5, true)

func _gui_input(event: InputEvent) -> void:
	var pressed: bool = event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT
	pressed = pressed or (event is InputEventScreenTouch and event.pressed)
	if pressed:
		location_chosen.emit(event.position / size * Vector2(300, 240) - Vector2(150, 120))
		accept_event()
