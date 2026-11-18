extends RefCounted
## Network + state ingest for «Лес потерянных» (forest_rescue/CONTRACT.md §1–§5).
## * State arrives through main.accept() (polling and command responses) → ingest().
## * Commands go through main.request() with an explicit Idempotency-Key. An uncertain
##   outcome (transport failure, timeout, 5xx, CAS_CONFLICT_RETRY) is retried with the SAME
##   key and the SAME body, so the server can only apply it once.
## * Events of a command response are deduplicated by revision + type (+ identity fields).
## * The client never sends success flags, rewards, positions, time or revision.

signal state_changed(adv: Dictionary, previous: Dictionary)
signal events_arrived(events: Array)
signal network_status(status: String, detail: String)

const CAMPAIGN_ID := "forest_rescue_v1"
const SCHEMA_VERSION := 1
const RETRY_DELAYS := [0.6, 1.4, 2.8, 4.5]
const UNCERTAIN_HTTP := [408, 425, 429, 500, 502, 503, 504]
const TRANSPORT_ERRORS := ["Сервер недоступен", "Сервер не ответил вовремя. Проверь соединение и повтори.",
	"Не удалось установить защищённое соединение с сервером."]
const LOCAL_BUSY := "Подожди завершения предыдущего запроса."
const ERROR_STRINGS := {
	"FOREST_LOCKED_HALL_LEVEL":"error.forestLocked", "HALL_LEVEL_TOO_LOW":"error.forestLocked",
	"CAMPAIGN_PAUSED":"pause.note", "TASK_OUT_OF_ORDER":"error.invalidAction", "ACT_LOCKED":"act.locked",
	"NOT_ARRIVED":"error.invalidAction", "TARGET_UNKNOWN":"error.invalidAction",
	"SQUAD_EMPTY":"error.insufficientSquad", "SQUAD_BUSY":"error.insufficientSquad",
	"MECHANISM_NOT_READY":"error.invalidAction", "PLATES_NOT_OCCUPIED":"mechanism.paired",
	"NO_BATTLE_PROOF":"error.unverifiedBattle", "ARTIFACT_MISSING":"artifact.missing",
	"ESCORT_NOT_ARRIVED":"error.invalidAction", "BOSS_LOCKED":"boss.locked",
	"IDEMPOTENCY_BODY_MISMATCH":"error.replayConflict", "BAD_FIELDS":"error.invalidAction",
	"STATE_CORRUPT":"error.version", "SCHEMA_UNSUPPORTED":"error.version",
	"CAS_CONFLICT_RETRY":"network.pending"
}

var host: Node
var content
var adv: Dictionary = {}
var known := false
var supported := true
var received_ticks := 0
var received_server_ms := 0.0
var clock_ms := 0.0
var clock_ticks := 0
var seen: Dictionary = {}
var seen_queue: Array[String] = []
var primed := false
var in_flight := false
var pending: Dictionary = {}
var last_result: Dictionary = {}
## QA/diagnostics: every request actually handed to the transport: {key, body, attempt}.
var sent_log: Array[Dictionary] = []

func _init(main_node: Node, authored) -> void:
	host = main_node
	content = authored

## Called for every accepted public state (polling and command responses).
func ingest(state: Dictionary) -> void:
	var previous := adv
	var value: Variant = state.get("adventure")
	if value is Dictionary and String(value.get("campaignId", "")) == CAMPAIGN_ID:
		known = true
		supported = int(value.get("schemaVersion", 0)) == SCHEMA_VERSION
		adv = value if supported else {}
	else:
		known = false
		supported = true
		adv = {}
	received_ticks = Time.get_ticks_msec()
	received_server_ms = float(adv.get("serverTime", state.get("serverTime", 0)))
	# Lazily settled server events (arrivals, fog reveals, escort home) come through
	# recentEvents. On the first state after (re)load they are only marked as seen: poses
	# are restored from state, nothing is replayed.
	var recent: Array = adv.get("recentEvents", [])
	var fresh := []
	if previous.is_empty() or not primed:
		primed = not adv.is_empty()
		for event in recent:
			if event is Dictionary:
				remember(event_key(event, ""))
	else:
		fresh = dedupe(recent)
	state_changed.emit(adv, previous)
	if not fresh.is_empty():
		events_arrived.emit(fresh)

func available() -> bool:
	return known and supported

func unlocked() -> bool:
	return available() and bool(adv.get("access", {}).get("unlocked", false))

func hall_level() -> int:
	return int(adv.get("access", {}).get("hallLevel", 0))

func required_hall() -> int:
	return int(adv.get("access", {}).get("requiredHall", 3))

## CONTRACT §5: t = serverTime + (localNow - receivedAt). Monotonic, never jumps backwards.
func server_now() -> float:
	var target := received_server_ms + float(Time.get_ticks_msec() - received_ticks)
	var ticks := Time.get_ticks_msec()
	if clock_ticks == 0 or absf(target - clock_ms) > 1500.0:
		clock_ms = target
	else:
		var advanced := clock_ms + float(ticks - clock_ticks)
		clock_ms = maxf(clock_ms, advanced + (target - advanced) * 0.2)
	clock_ticks = ticks
	return clock_ms

func campaign() -> Dictionary:
	return adv.get("campaign", {})

func phase() -> String:
	return String(campaign().get("phase", "prologue"))

func revision() -> int:
	return int(campaign().get("revision", 0))

func poi(id: String) -> Dictionary:
	for entry in adv.get("pois", []):
		if String(entry.get("id", "")) == id:
			return entry
	return {}

func site_state(id: String) -> Dictionary:
	for entry in campaign().get("sites", []):
		if String(entry.get("id", "")) == id:
			return entry
	return {}

func squad() -> Dictionary:
	return adv.get("squad", {})

func battle() -> Dictionary:
	var value: Variant = adv.get("battle")
	return value if value is Dictionary else {}

func escort() -> Dictionary:
	var value: Variant = adv.get("escort")
	return value if value is Dictionary else {}

static func uuid4() -> String:
	var bytes := Crypto.new().generate_random_bytes(16)
	bytes[6] = (bytes[6] & 0x0f) | 0x40
	bytes[8] = (bytes[8] & 0x3f) | 0x80
	var hex := bytes.hex_encode()
	return "%s-%s-%s-%s-%s" % [hex.substr(0, 8), hex.substr(8, 4), hex.substr(12, 4), hex.substr(16, 4), hex.substr(20, 12)]

## Sends one adventure command. kind is "adventure" or "adventure_intro".
func send(action: String, fields: Dictionary = {}, kind := "adventure") -> Dictionary:
	if not available():
		return _fail("UNAVAILABLE", content.text("hud.unavailable"))
	if not unlocked():
		return _fail("FOREST_LOCKED_HALL_LEVEL", content.text("error.forestLocked"))
	if in_flight:
		return _fail("LOCAL_BUSY", content.text("network.pending"))
	var body := {"kind":kind, "campaignId":CAMPAIGN_ID, "action":action}
	for name in fields:
		body[name] = fields[name]
	pending = {"body":body, "key":uuid4(), "attempts":0}
	return await _deliver()

## Re-sends the last uncertain request with the same key and body.
func retry_pending() -> Dictionary:
	if pending.is_empty() or in_flight:
		return _fail("NOTHING_TO_RETRY", "")
	pending.attempts = 0
	return await _deliver()

func has_pending_retry() -> bool:
	return not pending.is_empty() and not in_flight

func _deliver() -> Dictionary:
	in_flight = true
	network_status.emit("pending", content.text("network.pending"))
	while true:
		var waited := 0
		while host.busy and waited < 600:
			await host.get_tree().process_frame
			waited += 1
		pending.attempts = int(pending.attempts) + 1
		sent_log.append({"key":pending.key, "body":pending.body.duplicate(true), "attempt":pending.attempts})
		var response: Dictionary = await host.request("command", pending.body, pending.key)
		var verdict := classify(response)
		if verdict == "ok":
			var body: Dictionary = pending.body
			pending = {}
			in_flight = false
			host.accept(response)
			var fresh := dedupe(response.get("events", []), String(body.get("action", "")))
			network_status.emit("idle", "")
			last_result = {"ok":true, "events":response.get("events", []), "fresh":fresh, "action":body.action}
			if not fresh.is_empty():
				events_arrived.emit(fresh)
			return last_result
		if verdict == "busy":
			pending.attempts = int(pending.attempts) - 1
			sent_log.pop_back()
			await host.get_tree().create_timer(0.25).timeout
			continue
		if verdict == "uncertain":
			if int(pending.attempts) > RETRY_DELAYS.size():
				in_flight = false
				network_status.emit("offline", content.text("network.offline"))
				last_result = {"ok":false, "error":"OFFLINE", "retry":true, "message":content.text("network.offline")}
				return last_result
			network_status.emit("retrying", content.text("network.pending"))
			await host.get_tree().create_timer(RETRY_DELAYS[int(pending.attempts) - 1]).timeout
			continue
		pending = {}
		in_flight = false
		var code := String(response.get("error", "ERROR"))
		var message := error_message(response)
		network_status.emit("error", message)
		last_result = {"ok":false, "error":code, "message":message, "httpStatus":int(response.get("httpStatus", 0))}
		return last_result
	return {}

func classify(response: Dictionary) -> String:
	if response.has("city") and response.has("world"):
		return "ok"
	var status := int(response.get("httpStatus", 0))
	var code := String(response.get("error", ""))
	if status > 0:
		if status in UNCERTAIN_HTTP or (status == 409 and code == "CAS_CONFLICT_RETRY"):
			return "uncertain"
		return "definitive"
	if code == LOCAL_BUSY:
		return "busy"
	if code in TRANSPORT_ERRORS or code.begins_with("Сервер вернул неожиданный ответ"):
		return "uncertain"
	return "definitive"

func error_message(response: Dictionary) -> String:
	var code := String(response.get("error", ""))
	# CONTRACT §1: errors carry a Russian «message» written for this exact case; the
	# authored ui.ru.json strings are the fallback when the server sends none.
	var server_text := String(response.get("message", ""))
	if not server_text.is_empty() and server_text != code:
		return server_text
	if ERROR_STRINGS.has(code):
		return content.text(ERROR_STRINGS[code])
	if code.length() > 0 and not code.to_upper() == code:
		return code
	return content.text("error.invalidAction")

func _fail(code: String, message: String) -> Dictionary:
	return {"ok":false, "error":code, "message":message}

func remember(key: String) -> void:
	if seen.has(key):
		return
	seen[key] = true
	seen_queue.append(key)

func event_key(event: Dictionary, action: String) -> String:
	var kind := String(event.get("type", ""))
	if event.has("seq"):
		return "seq:%s|%s" % [str(event.seq), kind]
	var rev: Variant = event.get("revision")
	if rev == null:
		if kind == "fog_revealed":
			rev = "fog" + str(int(adv.get("fog", {}).get("revision", 0)))
		elif kind == "intro_present":
			rev = "intro:" + str(pending.get("key", action)) + ":" + String(adv.get("intro", {}).get("status", ""))
		else:
			rev = revision()
	var identity: PackedStringArray = []
	for field in ["siteId", "taskId", "phase", "reportId"]:
		if event.has(field):
			identity.append(str(event[field]))
	return "%s|%s|%s" % [str(rev), kind, ",".join(identity)]

## Drops events already presented (same revision+type+identity), bounded memory.
func dedupe(events: Array, action := "") -> Array:
	var fresh := []
	for event in events:
		if not event is Dictionary:
			continue
		var key := event_key(event, action)
		if seen.has(key):
			continue
		remember(key)
		fresh.append(event)
	while seen_queue.size() > 256:
		seen.erase(seen_queue.pop_front())
	return fresh

## Earliest server time (ms) at which a timed object settles (arriveAt/endsAt); INF if none.
func next_settle_ms() -> float:
	var best := INF
	for movable in [squad().get("move"), adv.get("horse", {}).get("move"), escort().get("move")]:
		if movable is Dictionary and movable.has("arriveAt"):
			best = minf(best, float(movable.arriveAt))
	var fight := battle()
	if not fight.is_empty() and String(fight.get("outcome", "pending")) == "pending" and fight.has("endsAt"):
		best = minf(best, float(fight.endsAt))
	for entry in adv.get("pois", []):
		var plates: Variant = entry.get("mechanism", {}).get("plates")
		if plates is Dictionary and plates.get("readyAt") != null and String(plates.get("state", "")) != "held":
			best = minf(best, float(plates.readyAt))
	return best
