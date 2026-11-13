extends SceneTree

const Diagnostics = preload("res://src/session_diagnostics.gd")
var failures: Array[String] = []
var checks := 0

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error(detail)

func _initialize() -> void:
	call_deferred("run")

func launch(path: String, now: float) -> Diagnostics:
	var value := Diagnostics.new()
	value.path = path
	value.start("qa", now)
	return value

func run() -> void:
	var path := "user://qa-diagnostics.json"
	for candidate in [path, path + ".tmp"]:
		if FileAccess.file_exists(candidate):
			DirAccess.remove_absolute(candidate)
	var a := launch(path, 1000)
	check(a.previous_ending == "first_launch", "First launch misclassified: " + a.previous_ending)
	a.heartbeat("world", 312.5, 64, 1064, 10000)
	# Process dies in the foreground (crash or iOS jetsam) without any notification.
	var b := launch(path, 2000)
	check(b.previous_ending == "ended_unexpectedly", "Foreground termination not detected: " + b.previous_ending)
	check(b.previous_session.scene == "world" and int(b.previous_session.uptime_s) == 64, "Crash context lost")
	b.set_state("background", 2100)
	var c := launch(path, 3000)
	check(c.previous_ending == "terminated_in_background", "Background reclaim reported as crash: " + c.previous_ending)
	c.request_reload("test", 3010)
	var d := launch(path, 4000)
	check(d.previous_ending == "deliberate_reload", "Deliberate reload misclassified: " + d.previous_ending)
	d.set_state("exited", 4100)
	var e := launch(path, 5000)
	check(e.previous_ending == "clean_exit", "Clean exit misclassified: " + e.previous_ending)
	check(int(e.record.counters.ended_unexpectedly) == 1 and int(e.record.counters.terminated_in_background) == 1, "Counters wrong")
	# Network outage is logged once and its recovery once.
	var before: int = e.record.events.size()
	for i in 5:
		e.network_result(false, "timeout", 5100 + i, 1000 + i * 100)
	e.network_result(true, "", 5200, 3000)
	var kinds: Array = e.record.events.slice(before).map(func(event): return event.kind)
	check(kinds == ["network_error", "network_recovered"], "Network events not collapsed: " + str(kinds))
	check(int(e.record.events[-1].detail.failures) == 5 and int(e.record.events[-1].detail.down_ms) == 2000, "Outage detail wrong")
	for i in 100:
		e.log_event("spam", {}, 6000 + i)
	check(e.record.events.size() == Diagnostics.MAX_EVENTS, "Event log unbounded")
	check(e.summary().contains("Аварийных завершений: 1"), "Summary missing crash count")
	# Corrupted file must not break startup.
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_string("{not json")
	file.close()
	var f := launch(path, 7000)
	check(f.previous_ending == "first_launch" and f.record.session.state == "foreground", "Corrupted diagnostics broke startup")
	DirAccess.remove_absolute(path)
	print("QA_DIAGNOSTICS checks=", checks, " failures=", failures.size())
	quit(0 if failures.is_empty() else 1)
