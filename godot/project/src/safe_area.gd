extends RefCounted
## The display's safe area in canvas units (1023): what the notch, the rounded corners and the home
## indicator leave free. An iPhone 12 in landscape keeps 47 pt at each side and 21 pt at the bottom,
## about 76 units at the sides and 34 at the bottom of the 1366 × 630 canvas. The HUD, the windows'
## heads and close buttons, the construction strip and the forest row stay inside it; their 1022
## margins are kept wherever they are already larger, so a screen without a notch is unchanged.
## main.gd refreshes it; layouts read `insets` (left, top, right, bottom) and compare `revision`.

static var insets := Vector4.ZERO
static var revision := 0
## QA: -- --qa-safe-area=l,t,r,b in canvas units replaces what the display reports.
static var override := Vector4(-1, -1, -1, -1)

static func parse_args(args: PackedStringArray) -> void:
	for arg in args:
		if arg.begins_with("--qa-safe-area="):
			var parts := arg.trim_prefix("--qa-safe-area=").split(",")
			if parts.size() == 4:
				override = Vector4(maxf(0.0, float(parts[0])), maxf(0.0, float(parts[1])), maxf(0.0, float(parts[2])), maxf(0.0, float(parts[3])))

## The display's insets in canvas units for a viewport whose canvas is stretched (canvas_items,
## keep aspect) into the window; zero where the display reports no safe area (desktop windows,
## headless runs).
static func measure(viewport: Viewport) -> Vector4:
	if override.x >= 0.0:
		return override
	if viewport == null or DisplayServer.get_name() == "headless":
		return Vector4.ZERO
	var safe := Rect2(DisplayServer.get_display_safe_area())
	var window := Rect2(Vector2(DisplayServer.window_get_position()), Vector2(DisplayServer.window_get_size()))
	var visible := viewport.get_visible_rect().size
	if safe.size.x <= 0.0 or safe.size.y <= 0.0 or window.size.x <= 0.0 or visible.x <= 0.0 or visible.y <= 0.0:
		return Vector4.ZERO
	# The canvas is scaled uniformly and centred in the window (letterbox bars count as safe).
	var scale := minf(window.size.x / visible.x, window.size.y / visible.y)
	var canvas := Rect2(window.position + (window.size - visible * scale) * 0.5, visible * scale)
	var left := maxf(0.0, safe.position.x - canvas.position.x) / scale
	var top := maxf(0.0, safe.position.y - canvas.position.y) / scale
	var right := maxf(0.0, canvas.end.x - safe.end.x) / scale
	var bottom := maxf(0.0, canvas.end.y - safe.end.y) / scale
	# A safe area far smaller than the window is a desktop work area, not a notch.
	if left > visible.x * 0.2 or right > visible.x * 0.2 or top > visible.y * 0.2 or bottom > visible.y * 0.2:
		return Vector4.ZERO
	return Vector4(ceilf(left), ceilf(top), ceilf(right), ceilf(bottom))

## Re-reads the display; true when the insets changed (revision is bumped).
static func refresh(viewport: Viewport) -> bool:
	var next := measure(viewport)
	if next.is_equal_approx(insets):
		return false
	insets = next
	revision += 1
	return true

## A 1022 margin on one side, widened to the inset on that side when the inset is larger.
static func left(margin: float) -> float:
	return maxf(margin, insets.x)

static func top(margin: float) -> float:
	return maxf(margin, insets.y)

static func right(margin: float) -> float:
	return maxf(margin, insets.z)

static func bottom(margin: float) -> float:
	return maxf(margin, insets.w)
