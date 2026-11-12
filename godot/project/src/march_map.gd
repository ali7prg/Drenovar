extends Control

var points := PackedVector2Array()

func set_path(path: Array) -> void:
	points.clear()
	for point in path:
		points.append(Vector2(point.x, point.z))
	visible = points.size() > 1
	queue_redraw()

func _draw() -> void:
	if points.size() < 2:
		return
	var bounds := Rect2(points[0], Vector2.ZERO)
	for point in points:
		bounds = bounds.expand(point)
	var inner_size := size - Vector2(22, 22)
	var scale_factor := minf(inner_size.x / maxf(bounds.size.x, 1), inner_size.y / maxf(bounds.size.y, 1))
	var line := PackedVector2Array()
	for point in points:
		line.append(size * 0.5 + (point - bounds.get_center()) * scale_factor)
	draw_style_box(get_theme_stylebox("normal", "LineEdit"), Rect2(Vector2.ZERO, size))
	draw_polyline(line, Color("#ebcc89"), 2.5, true)
	draw_circle(line[0], 4, Color("#ebcc89"), true, -1.0, true)
	draw_circle(line[-1], 6, Color("#d59978"), true, -1.0, true)
