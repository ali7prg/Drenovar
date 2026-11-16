extends RefCounted

# One clock for movement, clips, projectiles, HP and terminal transitions.
# Observe response cadence before a fight; never change its delay mid-fight (that
# would replay a contact). Nothing in this class writes authoritative state.
const PREPARE_MS := 760.0
const MIN_DELAY_MS := 1650.0 # Local measured p95 response gap 857 + 760 ms preparation, rounded up.
const MAX_DELAY_MS := 4500.0
var delay_ms := MIN_DELAY_MS
var sample_gaps: Array[float] = []
var latest: Dictionary = {}
var armies := {}
var missing_since := {}
var previous_time := -INF
var seen := {}
var trace: Array = []
var markers: Array = []
var frame_state: Dictionary = {}
var frame_time := 0.0
var current_map := ""
# The server resolves a hunt in about one second (a 200-man fight measured on
# Cloudflare: 0.9 s), which on a phone read as "the army is suddenly walking
# back and the creature is dead". The fight is shown for at least this long:
# its events are spread over the longer span and the walk home is quickened by
# the same amount, so the army is still home at the server's returnsAt.
const MIN_FIGHT_MS := 6500.0
# Shown fight end per authoritative battle end (report finishedAt).
var visual_ends := {}
# After a stall (asset upload, OS pause) the clock catches up gradually instead
# of jumping over a whole fight; the lag is never more than MAX_LAG_MS (an app
# returning from the background does not replay minutes of marching).
const CATCH_UP := 1.6
const MAX_LAG_MS := 4000.0
var previous_now := -INF

static func display_until(army: Dictionary) -> float:
	var returned := time_value(army,"returnsAt",INF)
	if army.get("returnUnits",{}).is_empty() and army.get("returnStartsAt") != null:
		return maxf(returned,time_value(army,"returnStartsAt",0)+3200.0)
	return returned

# Presentation copy only: spreads a short battle over MIN_FIGHT_MS. Battle
# events are offsets from battleAt and are scaled; the battle end and the start
# of the return move by the same extra time, returnsAt stays authoritative.
static func stretch(a: Dictionary, ends: Dictionary) -> void:
	var begin := time_value(a, "battleAt", time_value(a, "arrivesAt", INF))
	var finish := time_value(a, "battleEndsAt", time_value(a, "returnStartsAt", INF))
	if is_inf(begin) or is_inf(finish):
		return
	var span := finish - begin
	if span <= 0.0 or span >= MIN_FIGHT_MS:
		return
	# The walk home may at most double its speed (estimated from the walk out,
	# so the stretch is the same before and after the server sends the return).
	var walk := time_value(a, "arrivesAt", 0.0) - time_value(a, "startsAt", 0.0)
	var extra := minf(MIN_FIGHT_MS - span, maxf(0.0, walk) * 0.5)
	if extra < 250.0:
		return
	var k := (span + extra) / span
	for holder in [a.get("battle"), a.get("presentation"), a]:
		if holder is Dictionary and holder.get("events") is Array:
			var scaled: Array = []
			for e in holder.events:
				if e is Array and e.size() > 0:
					var row: Array = e.duplicate(); row[0] = float(row[0]) * k; scaled.append(row)
				elif e is Dictionary and e.has("at"):
					var row: Dictionary = e.duplicate(); row.at = float(row.at) * k; scaled.append(row)
				else:
					scaled.append(e)
			holder.events = scaled
	if a.get("battleEndsAt") != null: a.battleEndsAt = finish + extra
	if a.get("returnStartsAt") != null:
		a.returnStartsAt = float(a.returnStartsAt) + extra
		if a.get("returnsAt") != null and float(a.returnsAt) < float(a.returnStartsAt):
			a.returnsAt = a.returnStartsAt
	ends[str(finish)] = finish + extra
	a.stretched = k

# When the shown fight of a report ends (report.finishedAt = battle end).
func visual_end(finished_at: float) -> float:
	for key in visual_ends:
		if absf(float(key) - finished_at) < 1.0:
			return float(visual_ends[key])
	return finished_at

static func time_value(row: Dictionary, key: String, fallback: float) -> float:
	return fallback if row.get(key) == null else float(row[key])

static func event_id(army: Dictionary, event: Variant) -> String:
	if event is Dictionary and event.has("eventId"):
		return str(event.eventId)
	var e: Array = event if event is Array else [event.at,event.kind,event.unitId,event.index]
	return "%s/%s/%s/%s/%s/%s" % [army.id,army.get("battleAt",army.get("arrivesAt",0)),e[0],e[1],e[2],e[3]]

func frame(state: Dictionary, now: float, map_name: String) -> Dictionary:
	markers.clear()
	if latest.is_empty() or current_map != map_name or (str(state.get("playerId", "")) != str(latest.get("playerId", ""))):
		latest = {}; armies.clear(); seen.clear(); missing_since.clear(); sample_gaps.clear(); previous_time = -INF
		current_map = map_name
	var stamp := float(state.get("serverTime",now))
	if latest.is_empty() or stamp > float(latest.get("serverTime",-INF)):
		if not latest.is_empty():
			# Idle polling is slower; it must not inflate an active-fight buffer.
			var gap := stamp - float(latest.serverTime)
			# Rows already back home (kept for the report tail) do not make the
			# 5 s idle polling a fight cadence; it held every march 4.5 s behind.
			var moving := armies.values().any(func(a): return str(a.get("status", "")) != "returned")
			if gap <= 2000.0 or moving: sample_gaps.append(gap)
			if sample_gaps.size() > 32:
				sample_gaps.pop_front()
		var active := armies.values().any(func(a): return a.get("battleAt") != null and now < time_value(a,"returnsAt",INF))
		if not active and not sample_gaps.is_empty():
			var sorted := sample_gaps.duplicate(); sorted.sort()
			delay_ms = clampf(float(sorted[mini(sorted.size()-1,ceili(sorted.size()*0.95)-1)]) + PREPARE_MS,MIN_DELAY_MS,MAX_DELAY_MS)
		latest = state
		var rows: Array = state.get("world",{}).get("armies",[]) if map_name == "world" else state.get("armies",[])
		var present := {}
		for source in rows:
			present[str(source.id)] = true
			missing_since.erase(str(source.id))
			if source.status == "returned" and now-delay_ms >= display_until(source):
				continue
			var copy: Dictionary = source.duplicate(true)
			stretch(copy, visual_ends)
			var old: Dictionary = armies.get(str(source.id),{})
			# A returned city row drops battle history; retain it only for the bounded
			# presentation tail. Full world history comes from the V6 projection.
			if copy.get("battle") == null and old.get("battle") is Dictionary:
				copy.battle = old.battle
			if copy.get("presentation") == null and old.get("presentation") is Dictionary:
				copy.presentation = old.presentation
			armies[str(source.id)] = copy
		for id in armies:
			if not present.has(id) and not missing_since.has(id): missing_since[id] = now
	var target := now - delay_ms
	if previous_time > -INF and previous_now > -INF and target - previous_time > 50.0:
		# Behind after a stalled frame: advance at most a normal frame's worth,
		# a little faster, so a fight is slowed down rather than skipped.
		var step := clampf(now - previous_now, 0.0, 100.0) * CATCH_UP
		target = maxf(minf(target, previous_time + maxf(step, 1.0)), target - MAX_LAG_MS)
	frame_time = maxf(previous_time, target)
	previous_now = now
	var drawn: Array = []
	var fighting := {}
	for id in armies.keys():
		if missing_since.has(id) and now-float(missing_since[id]) > delay_ms+3200.0:
			armies.erase(id); missing_since.erase(id)
			for key in seen.keys():
				if key.begins_with(str(id)+"/"): seen.erase(key)
			continue
		var a: Dictionary = armies[id].duplicate(false)
		var begin := time_value(a,"battleAt",time_value(a,"arrivesAt",INF))
		var ends := time_value(a,"returnStartsAt",time_value(a,"battleEndsAt",INF))
		var returned := display_until(a)
		if a.get("returnsAt") != null and frame_time >= returned:
			armies.erase(id)
			for key in seen.keys():
				if key.begins_with(str(id)+"/"): seen.erase(key)
			continue
		var has_battle: bool = a.get("battle") is Dictionary or a.get("presentation") is Dictionary
		var defeat_tail: bool = a.get("returnUnits",{}).is_empty() and a.get("returnStartsAt") != null and frame_time < returned
		if has_battle and frame_time >= begin-PREPARE_MS and (frame_time < ends or defeat_tail):
			a.status = "fighting"
			fighting[str(a.target)] = true
		elif a.get("returnStartsAt") != null and frame_time >= ends:
			a.status = "returning"
		elif frame_time < begin:
			a.status = "outbound"
		# Restore the initial bag when rewinding a compact world's returning row.
		if a.get("presentation") is Dictionary and a.status != "returning":
			a.units = a.presentation.originalUnits
		drawn.append(a)
		var events: Array = a.get("presentation",{}).get("events",[]) if a.get("presentation") is Dictionary else a.get("battle",{}).get("events",[]) if a.get("battle") is Dictionary else a.get("events",[])
		for e in events:
			var key := event_id(a,e)
			var at := begin + (float(e[0]) if e is Array else float(e.at))
			if not seen.has(key):
				seen[key] = {"release":false,"contact":false}
				if at < previous_time:
					seen[key] = {"release":true,"contact":true}
					record({"id":key,"phase":"late-completion","at":at,"received":stamp,"shown":frame_time})
			var kind: String = str(e[1]) if e is Array else str(e.kind)
			var unit_id: String = str(e[2]) if e is Array else str(e.unitId)
			var action_markers: Array = [{"name":"contact","time":at}]
			if kind == "soldier_attack" and unit_id in ["ENG-03","ENG-04","ENG-10"]:
				action_markers.push_front({"name":"release","time":at-260.0})
			for marker in action_markers:
				if frame_time >= marker.time and not seen[key][marker.name]:
					seen[key][marker.name] = true
					# A cold reconnect acknowledges old events without replaying FX/audio.
					if previous_time > -INF:
						record({"id":key,"phase":marker.name,"at":at,"received":stamp,"shown":frame_time})
						var event: Dictionary=e if e is Dictionary else {"at":e[0],"kind":e[1],"unitId":e[2],"index":e[3],"hp":e[4] if e.size()>4 else 1,"creatureHP":e[4] if e.size()>4 else 1}
						markers.append({"id":key,"phase":marker.name,"event":event,"target":a.target,"army_id":a.id,"lateness":frame_time-float(marker.time)})
	frame_state = latest.duplicate(false)
	var container: Dictionary = latest.get("world",{}).duplicate(false) if map_name == "world" else frame_state
	container.armies = drawn
	container.encounters = []
	for source in (latest.get("world",{}).get("encounters",[]) if map_name == "world" else latest.get("encounters",[])):
		var e: Dictionary = source.duplicate(false)
		if fighting.has(str(e.id)): e.status = "fighting"
		container.encounters.append(e)
	if map_name == "world": frame_state.world = container
	previous_time = frame_time
	return {"state":frame_state,"time":frame_time}

func record(row: Dictionary) -> void:
	trace.append(row)
	if trace.size() > 512: trace.pop_front()
