extends CanvasLayer

# Combat diagnostics for a phone (off by default; Плавность на устройстве →
# «Диагностика боя»). Shows frame time, render/combat CPU time, memory, counts and
# the state of one selected fighter, and keeps a bounded log of combat events:
# swings started / cut / finished, creature reactions, actors hidden, shown,
# removed or recreated, position jumps, clock holds, slow polls, pipeline
# compilations and frame stalls. «Скопировать отчёт» puts a JSON report on the
# clipboard and saves it under user://.
#
# Cost when on: one pass over the drawn soldiers and creatures per frame and a
# text update four times a second. The log holds LOG_LIMIT events; frame times a
# window of FRAME_WINDOW frames. Nothing here changes what the game shows or
# sends. A metric the platform does not report is printed as «н/д».

const SETTINGS := "user://drenovar-combat-diagnostics.cfg"
const REPORT_DIR := "user://combat-reports"
const LOG_LIMIT := 600
const FRAME_WINDOW := 1200
const JUMP_M := 1.5
const STALL_MS := 100.0

static func stored_enabled() -> bool:
	var config := ConfigFile.new()
	return config.load(SETTINGS) == OK and bool(config.get_value("combat", "enabled", false))

static func store_enabled(on: bool) -> void:
	var config := ConfigFile.new()
	config.load(SETTINGS)
	config.set_value("combat", "enabled", on)
	config.save(SETTINGS)

var game: Node
var log_rows: Array = []
var log_next := 0
var log_total := 0
var frame_ms := PackedFloat32Array()
var frame_next := 0
var frame_count := 0
var combat_ms := PackedFloat32Array()
var started_usec := 0
var last_usec := 0
var tracked := {}  # "army/unit" or "creature/id" -> state of the previous frame
var stage_id := 0
var counters := {}
var worst: Array = []  # slowest frames with context
var previous_pipelines: Array = []
var previous_delay := -1.0
var previous_held := 0.0
var previous_caught := 0.0
var previous_server_time := 0.0
var previous_failures := 0
var selected := 0
var next_text_ms := 0
var panel: PanelContainer
var text: Label
var compact := false
var last_dt := 0.0
var self_ms := PackedFloat32Array()
var self_next := 0
var self_count := 0

func _ready() -> void:
	layer = 90
	started_usec = Time.get_ticks_usec()
	frame_ms.resize(FRAME_WINDOW)
	combat_ms.resize(FRAME_WINDOW)
	self_ms.resize(FRAME_WINDOW)
	panel = PanelContainer.new()
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.03, 0.04, 0.03, 0.72)
	style.set_corner_radius_all(6)
	style.content_margin_left = 8; style.content_margin_right = 8
	style.content_margin_top = 4; style.content_margin_bottom = 4
	panel.add_theme_stylebox_override("panel", style)
	panel.position = Vector2(8, 150)
	add_child(panel)
	var column := VBoxContainer.new()
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(column)
	text = Label.new()
	text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	text.add_theme_font_size_override("font_size", 11)
	text.add_theme_color_override("font_color", Color("#e8f0d8"))
	column.add_child(text)
	var row := HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_child(row)
	for spec in [["◀", func(): selected -= 1], ["▶", func(): selected += 1], ["Отчёт", copy_report], ["–", func(): compact = not compact]]:
		var b := Button.new()
		b.text = spec[0]
		b.focus_mode = Control.FOCUS_NONE
		b.add_theme_font_size_override("font_size", 12)
		b.custom_minimum_size = Vector2(34, 26)
		b.pressed.connect(spec[1])
		row.add_child(b)
	RenderingServer.viewport_set_measure_render_time(get_viewport().get_viewport_rid(), true)
	note("diagnostics_on", {"version": str(ProjectSettings.get_setting("application/config/version")),
		"build": str(ProjectSettings.get_setting("application/config/build_number", ""))})

func _exit_tree() -> void:
	RenderingServer.viewport_set_measure_render_time(get_viewport().get_viewport_rid(), false)

func now_ms() -> int:
	return int((Time.get_ticks_usec() - started_usec) / 1000)

func note(kind: String, detail := {}) -> void:
	var row := {"t": now_ms(), "k": kind}
	row.merge(detail)
	if log_rows.size() < LOG_LIMIT:
		log_rows.append(row)
	else:
		log_rows[log_next] = row
	log_next = (log_next + 1) % LOG_LIMIT
	log_total += 1
	counters[kind] = int(counters.get(kind, 0)) + 1

func ordered_log() -> Array:
	if log_rows.size() < LOG_LIMIT:
		return log_rows.duplicate()
	return log_rows.slice(log_next) + log_rows.slice(0, log_next)

static func v3(p: Vector3) -> Array:
	return [snappedf(p.x, 0.01), snappedf(p.y, 0.01), snappedf(p.z, 0.01)]

func player_of(node: Node) -> AnimationPlayer:
	var players: Array = node.get_meta("animation_players", [])
	return players[0] if not players.is_empty() and is_instance_valid(players[0]) else null

# Called by main.gd once per frame after the battle has been presented.
func frame(owner: Node, combat_usec: int) -> void:
	game = owner
	var tick := Time.get_ticks_usec()
	var dt := (tick - last_usec) / 1000.0 if last_usec > 0 else 0.0
	last_usec = tick
	last_dt = dt
	if dt > 0.0:
		frame_ms[frame_next] = dt
		combat_ms[frame_next] = combat_usec / 1000.0
		frame_next = (frame_next + 1) % FRAME_WINDOW
		frame_count = mini(frame_count + 1, FRAME_WINDOW)
	var stage = game.stage
	if not is_instance_valid(stage):
		return
	if stage.get_instance_id() != stage_id:
		stage_id = stage.get_instance_id()
		tracked.clear()
		note("scene", {"map": str(game.map_name)})
	var fighting := false
	for row in (stage.combat_view.frame_state.get("world", {}).get("armies", []) if game.map_name == "world" else stage.combat_view.frame_state.get("armies", [])):
		if str(row.get("status", "")) == "fighting":
			fighting = true
	if dt > STALL_MS:
		var context := {"ms": snappedf(dt, 0.1), "combat_ms": snappedf(combat_usec / 1000.0, 0.1), "fight": fighting,
			"soldiers": count_soldiers(stage), "map": str(game.map_name)}
		note("stall", context)
		worst.append(context)
		worst.sort_custom(func(a, b): return a.ms > b.ms)
		if worst.size() > 12: worst.resize(12)
	sample_pipelines(fighting)
	sample_clock(stage)
	sample_network()
	sample_actors(stage)
	if Time.get_ticks_msec() >= next_text_ms:
		next_text_ms = Time.get_ticks_msec() + 250
		update_text(stage)
	# Own cost, so the report shows what the diagnostics add to a frame.
	self_ms[self_next] = (Time.get_ticks_usec() - tick) / 1000.0
	self_next = (self_next + 1) % FRAME_WINDOW
	self_count = mini(self_count + 1, FRAME_WINDOW)

func sample_pipelines(fighting: bool) -> void:
	var now := [Performance.get_monitor(Performance.PIPELINE_COMPILATIONS_DRAW), Performance.get_monitor(Performance.PIPELINE_COMPILATIONS_SURFACE),
		Performance.get_monitor(Performance.PIPELINE_COMPILATIONS_SPECIALIZATION), Performance.get_monitor(Performance.PIPELINE_COMPILATIONS_MESH),
		Performance.get_monitor(Performance.PIPELINE_COMPILATIONS_CANVAS)]
	if not previous_pipelines.is_empty():
		var delta := []
		var any := false
		for i in now.size():
			delta.append(int(now[i] - previous_pipelines[i]))
			any = any or delta[-1] > 0
		if any:
			note("pipelines", {"draw": delta[0], "surface": delta[1], "specialization": delta[2], "mesh": delta[3], "canvas": delta[4], "fight": fighting})
	previous_pipelines = now

func sample_clock(stage) -> void:
	var view = stage.combat_view
	if previous_delay >= 0.0 and absf(view.delay_ms - previous_delay) >= 1.0 and absf(view.delay_ms - view.delay_target) < 0.5:
		note("delay_settled", {"ms": snappedf(view.delay_ms, 1.0)})
	elif previous_delay >= 0.0 and absf(view.delay_target - view.delay_ms) >= 1.0 and absf(previous_delay - view.delay_ms) < 0.01:
		note("delay_slew", {"from": snappedf(view.delay_ms, 1.0), "to": snappedf(view.delay_target, 1.0)})
	previous_delay = view.delay_ms
	if view.held_ms - previous_held >= 250.0:
		note("clock_held", {"ms": snappedf(view.held_ms - previous_held, 1.0)})
		previous_held = view.held_ms
	if view.caught_up_ms - previous_caught >= 250.0:
		note("clock_caught_up", {"ms": snappedf(view.caught_up_ms - previous_caught, 1.0)})
		previous_caught = view.caught_up_ms

func sample_network() -> void:
	var server_time := float(game.state.get("serverTime", 0.0))
	if previous_server_time > 0.0 and server_time > previous_server_time:
		var gap := server_time - previous_server_time
		if gap > 2500.0:
			note("slow_poll", {"gap_ms": roundi(gap)})
	if server_time > previous_server_time:
		previous_server_time = server_time
	var failures := int(game.diagnostics.network_failures)
	if failures != previous_failures:
		note("network_failures", {"count": failures})
		previous_failures = failures

func count_soldiers(stage) -> int:
	var count := 0
	for army in stage.actors.get_children():
		if army is Node3D and army.visible:
			for unit in army.get_children():
				if unit is Node3D and unit.name != &"Ferry" and unit.visible:
					count += 1
	return count

# Transitions of every drawn fighter since the previous frame.
func sample_actors(stage) -> void:
	var seen := {}
	var fallen := {}
	for body in stage.fallen_bodies:
		if is_instance_valid(body.node):
			fallen[body.node.get_instance_id()] = true
	for army in stage.actors.get_children():
		if not army is Node3D:
			continue
		var army_key := "army/" + str(army.name)
		seen[army_key] = true
		var before: Dictionary = tracked.get(army_key, {})
		if not before.is_empty():
			if before.vis and not army.visible:
				note("army_hidden", {"army": short(army.name)})
			elif not before.vis and army.visible:
				note("army_shown", {"army": short(army.name)})
		elif not tracked.is_empty():
			note("army_created", {"army": short(army.name)})
		tracked[army_key] = {"vis": army.visible, "id": army.get_instance_id()}
		if not army.visible:
			for unit in army.get_children():
				seen["unit/%s/%s" % [army.name, unit.name]] = true
			continue
		for unit in army.get_children():
			if not unit is Node3D or unit.name == &"Ferry":
				continue
			track_fighter(unit, "unit/%s/%s" % [army.name, unit.name], "soldier", seen)
	for creature in stage.creatures.get_children():
		if creature is Node3D:
			track_fighter(creature, "creature/" + str(creature.name), "creature", seen)
	for key in tracked.keys():
		if seen.has(key):
			continue
		var gone: Dictionary = tracked[key]
		if key.begins_with("unit/"):
			var instance: Object = instance_from_id(int(gone.get("id", 0)))
			note("soldier_fallen" if instance != null and fallen.has(gone.get("id", 0)) else "soldier_removed",
				{"unit": key.get_slice("/", 2), "clip": gone.get("clip", ""), "on_screen": gone.get("scr", false)})
		elif key.begins_with("creature/"):
			note("creature_removed", {"id": short(key.get_slice("/", 1)), "clip": gone.get("clip", "")})
		elif key.begins_with("army/"):
			note("army_removed", {"army": short(key.get_slice("/", 1))})
		tracked.erase(key)

func track_fighter(node: Node3D, key: String, kind: String, seen: Dictionary) -> void:
	seen[key] = true
	var clip := str(node.get_meta("clip", ""))
	var vis := node.is_visible_in_tree()
	var position := node.global_position
	var camera: Camera3D = node.get_viewport().get_camera_3d()
	var on_screen := camera != null and camera.is_position_in_frustum(position + Vector3.UP)
	var player := player_of(node)
	var clip_at := player.current_animation_position if player != null else -1.0
	var strike: float = float(node.get_meta("v010_strike", -INF))
	var before: Dictionary = tracked.get(key, {})
	var name := str(node.name) if kind == "soldier" else short(node.name)
	if before.is_empty():
		if not tracked.is_empty():
			note(kind + "_created", {"who": name})
	else:
		if int(before.id) != node.get_instance_id():
			note(kind + "_recreated", {"who": name})
		if before.vis and not vis:
			note(kind + "_hidden", {"who": name, "on_screen": before.scr})
		elif not before.vis and vis:
			note(kind + "_shown", {"who": name})
		var attack := "attack" if kind == "soldier" else "Attack"
		if clip != before.clip:
			if clip == attack:
				# "ambient": a swing of the soldier's own fighting cadence (build 1020), no server blow.
				var ambient: float = float(node.get_meta("ambient_strike", -INF)) if strike == -INF else -INF
				note(kind + "_attack_start", {"who": name, "strike": strike if strike > -INF else null, "ambient": ambient if ambient > -INF else null, "on_screen": on_screen})
			elif before.clip == attack:
				var length := float(before.get("len", 0.0))
				var finished: bool = before.clip_at >= length - 0.25 or (clip in ["idle", "Idle", "walk", "Walk"] and before.clip_at >= length * 0.6)
				note(kind + ("_attack_end" if finished else "_attack_cut"), {"who": name, "to": clip, "at_s": snappedf(before.clip_at, 0.01)})
			if clip in ["death", "Death"]:
				note(kind + "_death", {"who": name})
			if clip == "block":
				note("soldier_block", {"who": name})
			if kind == "creature" and clip == "Hit":
				note("creature_reaction", {"who": name})
		elif kind == "soldier" and clip == attack and strike > -INF and before.strike > -INF and strike != before.strike:
			note("soldier_attack_next", {"who": name, "strike": strike, "previous_at_s": snappedf(before.clip_at, 0.01)})
		elif kind == "creature" and clip == "Hit" and clip_at + 0.02 < before.clip_at:
			note("creature_reaction", {"who": name})
		if vis and before.vis and clip != "death":
			var moved := position.distance_to(before.pos)
			if moved > JUMP_M:
				note(kind + "_jump", {"who": name, "m": snappedf(moved, 0.01), "clip": clip, "frame_ms": snappedf(last_dt, 0.1), "from": v3(before.pos), "to": v3(position)})
	tracked[key] = {"id": node.get_instance_id(), "vis": vis, "scr": on_screen, "clip": clip, "clip_at": clip_at, "pos": position, "strike": strike,
		"len": player.current_animation_length if player != null else 0.0}

static func short(name: Variant) -> String:
	var s := str(name)
	return s.substr(0, 8) if s.length() > 12 else s

func percentile(values: PackedFloat32Array, count: int, q: float) -> float:
	if count <= 0:
		return 0.0
	var sorted := values.slice(0, count)
	sorted.sort()
	return sorted[clampi(ceili(q * count) - 1, 0, count - 1)]

func frame_stats() -> Dictionary:
	var count := frame_count
	var over := [0, 0, 0]
	var total := 0.0
	for i in count:
		var ms := frame_ms[i]
		total += ms
		if ms > 25.0: over[0] += 1
		if ms > 50.0: over[1] += 1
		if ms > 100.0: over[2] += 1
	return {"frames": count, "fps_avg": snappedf(count * 1000.0 / maxf(1.0, total), 0.1),
		"p50": snappedf(percentile(frame_ms, count, 0.5), 0.1), "p95": snappedf(percentile(frame_ms, count, 0.95), 0.1),
		"p99": snappedf(percentile(frame_ms, count, 0.99), 0.1), "max": snappedf(percentile(frame_ms, count, 1.0), 0.1),
		"over_25ms": over[0], "over_50ms": over[1], "over_100ms": over[2],
		"combat_p95_ms": snappedf(percentile(combat_ms, count, 0.95), 0.01), "combat_max_ms": snappedf(percentile(combat_ms, count, 1.0), 0.01),
		"diagnostics_p95_ms": snappedf(percentile(self_ms, self_count, 0.95), 0.01), "diagnostics_max_ms": snappedf(percentile(self_ms, self_count, 1.0), 0.01)}

func participants(stage) -> Array:
	var list: Array = []
	for creature in stage.creatures.get_children():
		if creature is Node3D and creature.visible:
			list.append(creature)
	for army in stage.actors.get_children():
		if army is Node3D and army.visible:
			for unit in army.get_children():
				if unit is Node3D and unit.name != &"Ferry" and unit.visible:
					list.append(unit)
	return list

static func metric(value: float, unit := "мс") -> String:
	return "н/д" if value <= 0.0 else "%.1f %s" % [value, unit]

func update_text(stage) -> void:
	var stats := frame_stats()
	var viewport := get_viewport().get_viewport_rid()
	var gpu := RenderingServer.viewport_get_measured_render_time_gpu(viewport)
	var cpu := RenderingServer.viewport_get_measured_render_time_cpu(viewport)
	var lines: Array[String] = []
	lines.append("FPS %.0f · кадр p50 %.1f / p95 %.1f / p99 %.1f / макс %.1f мс" % [stats.fps_avg, stats.p50, stats.p95, stats.p99, stats.max])
	if compact:
		text.text = lines[0]
		return
	lines.append(">25 мс: %d · >50: %d · >100: %d (из %d кадров)" % [stats.over_25ms, stats.over_50ms, stats.over_100ms, stats.frames])
	lines.append("рендер CPU %s · GPU %s · бой (скрипт) p95 %.2f мс · диагностика p95 %.2f мс" % [metric(cpu), metric(gpu), stats.combat_p95_ms, stats.diagnostics_p95_ms])
	var static_mb := Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0
	lines.append("память: скрипты %s · видео %s · текстуры %s" % [metric(static_mb, "МБ"),
		metric(Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) / 1048576.0, "МБ"),
		metric(Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED) / 1048576.0, "МБ")])
	var fx := 0
	for kind in stage.battle_fx.used:
		fx += int(stage.battle_fx.used[kind])
	var armies := 0
	for army in stage.actors.get_children():
		if army is Node3D and army.visible: armies += 1
	var creatures := 0
	for creature in stage.creatures.get_children():
		if creature is Node3D and creature.visible: creatures += 1
	lines.append("отрядов %d · бойцов %d · зверей %d · эффектов %d · павших %d · узлов %d" % [armies, count_soldiers(stage), creatures, fx,
		stage.fallen_bodies.size(), Performance.get_monitor(Performance.OBJECT_NODE_COUNT)])
	var view = stage.combat_view
	lines.append("задержка показа %.0f → %.0f мс · стоял %.1f с · догонял %.1f с" % [view.delay_ms, view.delay_target, view.held_ms / 1000.0, view.caught_up_ms / 1000.0])
	lines.append("удары: начато %d · прервано %d · зверь атак %d · скачков %d · скрыто %d · удалено %d" % [
		int(counters.get("soldier_attack_start", 0)) + int(counters.get("soldier_attack_next", 0)), int(counters.get("soldier_attack_cut", 0)),
		int(counters.get("creature_attack_start", 0)), int(counters.get("soldier_jump", 0)) + int(counters.get("creature_jump", 0)),
		int(counters.get("army_hidden", 0)) + int(counters.get("soldier_hidden", 0)) + int(counters.get("creature_hidden", 0)),
		int(counters.get("soldier_removed", 0)) + int(counters.get("creature_removed", 0))])
	var list := participants(stage)
	if not list.is_empty():
		selected = posmod(selected, list.size())
		var who: Node3D = list[selected]
		var player := player_of(who)
		var camera: Camera3D = get_viewport().get_camera_3d()
		lines.append("[%d/%d] %s · клип %s · %s %.2f/%.2f с%s · %s" % [selected + 1, list.size(),
			short(who.name) if who.get_parent() == stage.creatures else str(who.name), str(who.get_meta("clip", "?")),
			str(player.assigned_animation).get_file() if player != null else "—",
			player.current_animation_position if player != null else 0.0, player.current_animation_length if player != null else 0.0,
			"" if player == null or player.is_playing() else " (пауза)",
			"в кадре" if camera != null and camera.is_position_in_frustum(who.global_position + Vector3.UP) else "вне кадра"])
	var recent := ordered_log().slice(-4)
	for row in recent:
		lines.append("· %.1f с %s %s" % [row.t / 1000.0, row.k, str(row.get("who", row.get("army", row.get("ms", ""))))])
	text.text = "\n".join(lines)

func report() -> Dictionary:
	var device_memory := OS.get_memory_info()
	var viewport := get_viewport()
	var stage = game.stage if game != null and is_instance_valid(game.stage) else null
	return {
		"kind": "drenovar-combat-diagnostics", "format": 1,
		"version": str(ProjectSettings.get_setting("application/config/version")),
		"build": str(ProjectSettings.get_setting("application/config/build_number", "")),
		"device": OS.get_model_name(), "os": "%s %s" % [OS.get_name(), OS.get_version()],
		"renderer": RenderingServer.get_current_rendering_method(), "gpu": RenderingServer.get_video_adapter_name(),
		"api": RenderingServer.get_video_adapter_api_version(),
		"screen": [DisplayServer.screen_get_size().x, DisplayServer.screen_get_size().y], "scale": DisplayServer.screen_get_scale(),
		"viewport": [viewport.get_visible_rect().size.x, viewport.get_visible_rect().size.y],
		# Drawn 3D pixels (the texture's get_size() includes the canvas_items stretch).
		"buffer": [viewport.get_window().size.x * viewport.scaling_3d_scale, viewport.get_window().size.y * viewport.scaling_3d_scale], "msaa_3d": viewport.msaa_3d,
		"uptime_s": roundi(now_ms() / 1000.0), "map": str(game.map_name) if game != null else "",
		"frames": frame_stats(), "worst_frames": worst,
		"render_ms": {"cpu": RenderingServer.viewport_get_measured_render_time_cpu(viewport.get_viewport_rid()),
			"gpu": RenderingServer.viewport_get_measured_render_time_gpu(viewport.get_viewport_rid())},
		"memory_mb": {"static": Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0,
			"video": Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) / 1048576.0,
			"textures": Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED) / 1048576.0,
			"device_physical": float(device_memory.get("physical", -1)) / 1048576.0,
			"device_available": float(device_memory.get("available", -1)) / 1048576.0},
		"objects": {"nodes": Performance.get_monitor(Performance.OBJECT_NODE_COUNT), "objects": Performance.get_monitor(Performance.OBJECT_COUNT),
			"orphans": Performance.get_monitor(Performance.OBJECT_ORPHAN_NODE_COUNT)},
		"pipelines_total": previous_pipelines,
		"clock": {"delay_ms": stage.combat_view.delay_ms if stage else null, "delay_target_ms": stage.combat_view.delay_target if stage else null,
			"held_ms": stage.combat_view.held_ms if stage else null, "caught_up_ms": stage.combat_view.caught_up_ms if stage else null},
		"counters": counters, "log_total": log_total, "log": ordered_log()}

func copy_report() -> void:
	var json := JSON.stringify(report())
	DisplayServer.clipboard_set(json)
	DirAccess.make_dir_recursive_absolute(REPORT_DIR)
	var stamp := Time.get_datetime_string_from_system(false, false).replace(":", "-")
	var file := FileAccess.open("%s/combat-%s.json" % [REPORT_DIR, stamp], FileAccess.WRITE)
	if file != null:
		file.store_string(json)
		file.close()
	# Keep the three newest reports.
	var names := DirAccess.get_files_at(REPORT_DIR)
	names.sort()
	for i in maxi(0, names.size() - 3):
		DirAccess.remove_absolute(REPORT_DIR + "/" + names[i])
	note("report_copied", {"bytes": json.length()})
	text.text = "Отчёт скопирован (%d КБ). Вставьте его в сообщение." % ceili(json.length() / 1024.0)
	next_text_ms = Time.get_ticks_msec() + 2500
