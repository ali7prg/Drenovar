extends RefCounted

# Distinguishes how the previous app session ended and keeps a short local log of
# stability events: crashes / OS terminations in the foreground, terminations
# while suspended, deliberate reloads, authentication resets and network outages.
# Contains no tokens or personal data; it stays on the device.

const PATH := "user://drenovar-diagnostics.json"
const MAX_EVENTS := 40
const HEARTBEAT_MSEC := 5000

var record: Dictionary = {}
var previous_ending := "first_launch"
var previous_session: Dictionary = {}
var next_heartbeat := 0
var network_failures := 0
var network_down_since := 0
var path := PATH

func start(version: String, now_unix: float) -> void:
	var stored: Variant = null
	if FileAccess.file_exists(path):
		var parser := JSON.new()
		if parser.parse(FileAccess.get_file_as_string(path)) == OK:
			stored = parser.data
	if stored is Dictionary:
		record = stored
	if not record.get("events") is Array:
		record.events = []
	var last: Variant = record.get("session")
	if last is Dictionary:
		previous_session = last
		previous_ending = classify(last)
		if previous_ending != "clean_exit":
			log_event("previous_session_" + previous_ending, {
				"version": last.get("version", ""), "scene": last.get("scene", ""),
				"uptime_s": int(last.get("uptime_s", 0)), "memory_mb": last.get("memory_mb", 0.0),
				"reload_requested": last.get("reload_requested", false)}, now_unix, false)
	var counters: Dictionary = record.get("counters", {})
	counters[previous_ending] = int(counters.get(previous_ending, 0)) + 1
	record.counters = counters
	record.session = {"version": version, "started": now_unix, "heartbeat": now_unix, "state": "foreground",
		"scene": "", "uptime_s": 0, "memory_mb": 0.0, "reload_requested": false}
	save()

static func classify(last: Dictionary) -> String:
	match String(last.get("state", "")):
		"exited":
			return "clean_exit"
		"background":
			# iOS may reclaim a suspended app; that is not a crash.
			return "terminated_in_background"
		_:
			return "deliberate_reload" if last.get("reload_requested", false) else "ended_unexpectedly"

func set_state(value: String, now_unix: float) -> void:
	if record.is_empty():
		return
	record.session.state = value
	record.session.heartbeat = now_unix
	save()

func heartbeat(scene: String, memory_mb: float, uptime_s: float, now_unix: float, now_msec: int) -> void:
	if record.is_empty() or now_msec < next_heartbeat:
		return
	next_heartbeat = now_msec + HEARTBEAT_MSEC
	record.session.scene = scene
	record.session.memory_mb = snappedf(memory_mb, 0.1)
	record.session.uptime_s = int(uptime_s)
	record.session.peak_mb = snappedf(maxf(float(record.session.get("peak_mb", 0.0)), memory_mb), 0.1)
	record.session.heartbeat = now_unix
	save()

func request_reload(reason: String, now_unix: float) -> void:
	if record.is_empty():
		return
	record.session.reload_requested = true
	log_event("deliberate_reload", {"reason": reason}, now_unix)

func network_result(ok: bool, kind: String, now_unix: float, now_msec: int) -> void:
	if ok:
		if network_failures > 0:
			log_event("network_recovered", {"failures": network_failures,
				"down_ms": now_msec - network_down_since}, now_unix)
		network_failures = 0
		return
	if network_failures == 0:
		network_down_since = now_msec
		log_event("network_error", {"kind": kind}, now_unix)
	network_failures += 1

func log_event(kind: String, detail: Dictionary, now_unix: float, persist := true) -> void:
	if not record.get("events") is Array:
		record.events = []
	record.events.append({"kind": kind, "at": int(now_unix), "detail": detail})
	while record.events.size() > MAX_EVENTS:
		record.events.pop_front()
	if persist:
		save()

func summary() -> String:
	var names := {
		"first_launch": "первый запуск", "clean_exit": "штатное закрытие",
		"terminated_in_background": "выгружено системой в фоне",
		"deliberate_reload": "намеренная перезагрузка", "ended_unexpectedly": "аварийное завершение или принудительная остановка"}
	var text := "Предыдущий сеанс: %s" % names.get(previous_ending, previous_ending)
	if not previous_session.is_empty() and previous_ending != "first_launch":
		text += " (сцена %s, %d с, %.0f МБ, пик %.0f МБ)" % [previous_session.get("scene", "?"),
			int(previous_session.get("uptime_s", 0)), float(previous_session.get("memory_mb", 0.0)),
			float(previous_session.get("peak_mb", 0.0))]
	var counters: Dictionary = record.get("counters", {})
	text += "\nАварийных завершений: %d · выгрузок в фоне: %d · штатных: %d" % [
		int(counters.get("ended_unexpectedly", 0)), int(counters.get("terminated_in_background", 0)),
		int(counters.get("clean_exit", 0))]
	var recent: Array = record.get("events", []).slice(-10)
	if not recent.is_empty():
		text += "\nПоследние события: " + ", ".join(recent.map(func(event):
			var detail: Dictionary = event.get("detail", {})
			return String(event.kind) + (("·" + str(detail.get("action", ""))) if detail.has("action") else "")))
	return text

func save() -> void:
	var temporary := path + ".tmp"
	var file := FileAccess.open(temporary, FileAccess.WRITE)
	if file == null:
		return
	file.store_string(JSON.stringify(record))
	file.close()
	DirAccess.rename_absolute(temporary, path)
