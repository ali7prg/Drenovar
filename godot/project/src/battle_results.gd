extends RefCounted

const PATH := "user://battle-results.cfg"
const ANNOUNCE_DELAY_MS := 1650

var storage := ConfigFile.new()
var profile := ""
var known := {}
var pending: Array[Dictionary] = []
var ready_at := 0

func _init() -> void:
	storage.load(PATH)

func observe(player: String, reports: Array) -> void:
	var first := 0
	if player != profile:
		reset()
		profile = player
		var last: String = storage.get_value("journal", profile, "")
		if last.is_empty():
			first = reports.size()
			if not reports.is_empty():
				remember(reports.back())
		else:
			var index := reports.find_custom(func(report): return report.get("id", "") == last)
			first = index + 1 if index >= 0 else reports.size()
	for index in reports.size():
		var report: Dictionary = reports[index]
		var id: String = report.get("id", "")
		if id.is_empty() or known.has(id):
			continue
		known[id] = true
		if index >= first:
			if pending.is_empty():
				ready_at = Time.get_ticks_msec() + ANNOUNCE_DELAY_MS
			pending.append(report)

func reset() -> void:
	profile = ""
	known.clear()
	pending.clear()
	ready_at = 0

func next() -> Dictionary:
	if pending.is_empty():
		return {}
	var report: Dictionary = pending.pop_front()
	remember(report)
	return report

func remember(report: Dictionary) -> void:
	var id: String = report.get("id", "")
	if not profile.is_empty() and not id.is_empty():
		storage.set_value("journal", profile, id)
		storage.save(PATH)
