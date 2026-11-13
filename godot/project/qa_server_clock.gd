extends SceneTree

# Server clock under jittery network delays (50..600 ms per response, a response
# every ~0.8 s): game time never runs backward, never jumps, and converges on the
# least-delayed estimate. The old per-response offset jumped by up to 550 ms.

var checks := 0
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)

func run() -> void:
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while game.scene_loading or not is_instance_valid(game.stage):
		await process_frame
	game.set_process(false)
	var true_offset := 123456.0
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	var previous := -INF
	var worst_step := 0.0
	var backwards := 0
	var last_tick := Time.get_ticks_usec()
	var next_response := 0.0
	var elapsed := 0.0
	while elapsed < 12.0:
		await process_frame
		var now := Time.get_ticks_usec()
		var dt := (now - last_tick) / 1000000.0
		last_tick = now
		elapsed += dt
		if elapsed >= next_response:
			next_response = elapsed + 0.8
			var delay := rng.randf_range(50.0, 600.0)
			game.note_server_time(Time.get_unix_time_from_system() * 1000.0 + true_offset - delay)
		game.advance_server_clock(dt)
		var t: float = game.server_time()
		if previous > -INF:
			var step := t - previous - dt * 1000.0
			worst_step = maxf(worst_step, absf(step))
			if t < previous:
				backwards += 1
		previous = t
	var error: float = Time.get_unix_time_from_system() * 1000.0 + true_offset - game.server_time()
	check(backwards == 0, "Game time ran backward %d times" % backwards)
	check(worst_step < 25.0, "Clock jumped %.0f ms in one frame" % worst_step)
	check(error >= 0.0 and error < 120.0, "Clock is %.0f ms behind the server" % error)
	print("QA_SERVER_CLOCK worst_step_ms=", snappedf(worst_step, 0.1), " behind_ms=", snappedf(error, 1))
	print("QA_SERVER_CLOCK checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
