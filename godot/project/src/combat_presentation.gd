extends RefCounted

# One clock for movement, clips, projectiles, HP and terminal transitions.
# Observe response cadence before a fight; never change its delay mid-fight (that
# would replay a contact). Nothing in this class writes authoritative state.
const PREPARE_MS := 760.0
const MIN_DELAY_MS := 1650.0 # Local measured p95 response gap 857 + 760 ms preparation, rounded up.
const MAX_DELAY_MS := 4500.0
var delay_ms := MIN_DELAY_MS
# The delay follows the measured response cadence, but never in one step: a poll
# that moved it by 1.5 s froze every marching army for 1.5 s (or ran it at 1.6x
# when it shrank). It slews at most this share of real time, so the shown clock
# runs at 0.85x..1.08x while it adapts and never stops. A fight on screen keeps
# its delay (see `fight_on_screen`).
const DELAY_SLEW_UP := 0.15
const DELAY_SLEW_DOWN := 0.08
var delay_target := MIN_DELAY_MS
var fight_on_screen := false
# Diagnostics: real milliseconds the shown clock stood still or ran ahead.
var held_ms := 0.0
var caught_up_ms := 0.0
var sample_gaps: Array[float] = []
var latest: Dictionary = {}
var armies := {}
var missing_since := {}
var previous_time := -INF
var seen := {}
var trace: Array = []
var markers: Array = []
var frame_state: Dictionary = {}
# Per army: the event list the markers were prepared from and the markers not yet
# reached. Rebuilt only when a poll brings a new list; each frame walks the
# pending ones. (Formatting an id string and allocating marker dictionaries for
# every event of every fight on every frame cost ~1 ms per 100 events.)
var marker_cache := {}
var frame_time := 0.0
var current_map := ""
# The server resolves a hunt in about one second (a 200-man fight measured on
# Cloudflare: 0.9 s), which on a phone read as "the army is suddenly walking
# back and the creature is dead". The fight is shown for at least this long:
# its events are spread over the longer span and the walk home is quickened by
# the same amount, so the army is still home at the server's returnsAt.
# 6.5 s (up to build 1019) showed one or two swings per soldier; the crowd now
# fights continuously (landscape.ambient_strike), shown for 9.5 s.
const MIN_FIGHT_MS := 9500.0
const FINAL_HOLD_MS := 900.0
# Shown fight end per authoritative battle end (report finishedAt).
var visual_ends := {}
# A hunt's battle exists only from the server's first answer after the army
# arrives (the server simulates it then), and an answer can take seconds. Up to
# build 1020 the crowd stood still at its places until it came: 3.5 s in the city
# and 6 s on the world map in the owner's recordings, and the first seconds of the
# fight were then skipped. Now the soldiers fight from the moment they reach the
# creature (landscape.ambient_strike), and the server's blows begin when the answer
# is there: per army, how late (shown ms) that was against the planned start. Fixed
# once known, so every later poll lays the blows out the same way (stretch).
var late_starts := {}
const MAX_LATE_MS := 9000.0
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
#
# `late` (ms): the server's blows start that much after the battle start (see
# late_starts). The return starts later by the same time when the walk home can
# give it back; otherwise the blows are shown a little faster, never faster than
# 1/MIN_PACE of the server, and only beyond that the first ones are not drawn.
const MIN_PACE := 0.75

static func stretch(a: Dictionary, ends: Dictionary, late := 0.0) -> void:
	var begin := time_value(a, "battleAt", time_value(a, "arrivesAt", INF))
	var finish := time_value(a, "battleEndsAt", time_value(a, "returnStartsAt", INF))
	if is_inf(begin) or is_inf(finish):
		return
	var span := finish - begin
	if span <= 0.0:
		return
	late = maxf(0.0, late)
	# The walk home may at most double its speed (estimated from the walk out,
	# so the stretch is the same before and after the server sends the return).
	var walk := time_value(a, "arrivesAt", 0.0) - time_value(a, "startsAt", 0.0)
	var longer := MIN_FIGHT_MS + FINAL_HOLD_MS - span if span < MIN_FIGHT_MS else 0.0
	var extra := minf(longer + late, maxf(0.0, walk) * 0.5)
	if extra < 250.0 and late <= 0.0:
		return
	# The server's last step (often the killing blow) is stamped at the battle end
	# itself; scaled alone it landed on the last shown frame, so the army turned
	# home mid-swing and the creature fell behind it. The blows end a little
	# earlier and the swing and the fall finish inside the fight.
	var hold := minf(FINAL_HOLD_MS, extra * 0.2)
	var lead := clampf(late, 0.0, maxf(0.0, span + extra - hold - span * MIN_PACE))
	var k := (span + extra - hold - lead) / span
	for holder in [a.get("battle"), a.get("presentation"), a]:
		if holder is Dictionary and holder.get("events") is Array:
			var scaled: Array = []
			var spread := step_offsets(holder.events, span)
			for n in holder.events.size():
				var e: Variant = holder.events[n]
				if e is Array and e.size() > 0:
					var row: Array = e.duplicate(); row[0] = lead + (float(row[0]) + spread[n]) * k; scaled.append(row)
				elif e is Dictionary and e.has("at"):
					var row: Dictionary = e.duplicate(); row.at = lead + (float(row.at) + spread[n]) * k; scaled.append(row)
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
	a.blows_from = lead

# The server resolves a fight in 200 ms steps and stamps every blow of a step
# with the step's start. Scaled alone, a step stays one instant: a small creature
# killed by the first volley (all 18 blows at 0 ms) was shown as one release and
# then 6 s of soldiers standing idle. Before scaling, the blows of a step are laid
# out across that step in server order (never past the battle end), so the
# stretched fight shows them one after another. Pure function of one step's
# blows: a step arrives whole in every poll, so a later poll never moves a blow
# already shown. Order, HP after each blow and the outcome are unchanged.
const STEP_MS := 200.0
static func step_offsets(events: Array, span: float) -> Array:
	var offsets: Array = []
	offsets.resize(events.size())
	offsets.fill(0.0)
	var groups := {}
	for n in events.size():
		var e: Variant = events[n]
		var at := float(e[0]) if e is Array and e.size() > 0 else float(e.get("at", 0.0)) if e is Dictionary else NAN
		if is_nan(at):
			continue
		if not groups.has(at):
			groups[at] = []
		groups[at].append(n)
	for at in groups:
		var members: Array = groups[at]
		var width := clampf(span - float(at), 0.0, STEP_MS)
		for j in members.size():
			offsets[members[j]] = width * j / members.size()
	return offsets

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
		latest = {}; armies.clear(); seen.clear(); missing_since.clear(); sample_gaps.clear(); previous_time = -INF; marker_cache.clear(); late_starts.clear()
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
		if not sample_gaps.is_empty():
			var sorted := sample_gaps.duplicate(); sorted.sort()
			delay_target = clampf(float(sorted[mini(sorted.size()-1,ceili(sorted.size()*0.95)-1)]) + PREPARE_MS,MIN_DELAY_MS,MAX_DELAY_MS)
		latest = state
		var rows: Array = state.get("world",{}).get("armies",[]) if map_name == "world" else state.get("armies",[])
		var present := {}
		for source in rows:
			present[str(source.id)] = true
			missing_since.erase(str(source.id))
			if source.status == "returned" and now-delay_ms >= display_until(source):
				continue
			var copy: Dictionary = source.duplicate(true)
			var old: Dictionary = armies.get(str(source.id),{})
			note_late_start(source, old, now)
			stretch(copy, visual_ends, float(late_starts.get(str(source.id), 0.0)))
			# A returned city row drops battle history; retain it only for the bounded
			# presentation tail. Full world history comes from the V6 projection.
			if copy.get("battle") == null and old.get("battle") is Dictionary:
				copy.battle = old.battle
			if copy.get("presentation") == null and old.get("presentation") is Dictionary:
				copy.presentation = old.presentation
			armies[str(source.id)] = copy
		for id in armies:
			if not present.has(id) and not missing_since.has(id): missing_since[id] = now
	var real_step := clampf(now - previous_now, 0.0, 250.0) if previous_now > -INF else 0.0
	if previous_time == -INF:
		delay_ms = delay_target
	elif not fight_on_screen and delay_ms != delay_target:
		delay_ms = move_toward(delay_ms, delay_target, real_step * (DELAY_SLEW_UP if delay_target > delay_ms else DELAY_SLEW_DOWN))
	var target := now - delay_ms
	if previous_time > -INF and previous_now > -INF and target - previous_time > 50.0:
		# Behind after a stalled frame: advance at most a normal frame's worth,
		# a little faster, so a fight is slowed down rather than skipped.
		var step := clampf(now - previous_now, 0.0, 100.0) * CATCH_UP
		target = maxf(minf(target, previous_time + maxf(step, 1.0)), target - MAX_LAG_MS)
	frame_time = maxf(previous_time, target)
	if previous_time > -INF and real_step > 0.0:
		var advanced := frame_time - previous_time
		if advanced < real_step * 0.5:
			held_ms += real_step
		elif advanced > real_step * 1.3 + 1.0:
			caught_up_ms += real_step
	previous_now = now
	var drawn: Array = []
	var fighting := {}
	for id in armies.keys():
		if missing_since.has(id) and now-float(missing_since[id]) > delay_ms+3200.0:
			armies.erase(id); missing_since.erase(id); marker_cache.erase(id); late_starts.erase(id)
			for key in seen.keys():
				if key.begins_with(str(id)+"/"): seen.erase(key)
			continue
		var a: Dictionary = armies[id].duplicate(false)
		var begin := time_value(a,"battleAt",time_value(a,"arrivesAt",INF))
		var ends := time_value(a,"returnStartsAt",time_value(a,"battleEndsAt",INF))
		var returned := display_until(a)
		if a.get("returnsAt") != null and frame_time >= returned:
			armies.erase(id); marker_cache.erase(id); late_starts.erase(id)
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
		var prepared: Dictionary = marker_cache.get(id, {})
		if not is_same(prepared.get("events"), events) or prepared.get("begin") != begin:
			var pending: Array = []
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
				var released: bool = kind == "soldier_attack" and unit_id in ["ENG-03","ENG-04"]
				var flags: Dictionary = seen[key]
				if not flags.contact or (released and not flags.release):
					pending.append([key, at, released, e])
			prepared = {"events": events, "begin": begin, "pending": pending}
			marker_cache[id] = prepared
		var waiting: Array = []
		for item in prepared.pending:
			var key: String = item[0]
			var at: float = item[1]
			var flags: Dictionary = seen.get(key, {"release":true,"contact":true})
			for phase in (["release", "contact"] if item[2] else ["contact"]):
				var time := at - 260.0 if phase == "release" else at
				if frame_time >= time and not flags[phase]:
					flags[phase] = true
					# A cold reconnect acknowledges old events without replaying FX/audio.
					if previous_time > -INF:
						var e: Variant = item[3]
						record({"id":key,"phase":phase,"at":at,"received":stamp,"shown":frame_time})
						var event: Dictionary=e if e is Dictionary else {"at":e[0],"kind":e[1],"unitId":e[2],"index":e[3],"hp":e[4] if e.size()>4 else 1,"creatureHP":e[4] if e.size()>4 else 1}
						markers.append({"id":key,"phase":phase,"event":event,"target":a.target,"army_id":a.id,"lateness":frame_time-time})
			if not flags.contact or (item[2] and not flags.release):
				waiting.append(item)
		prepared.pending = waiting
	frame_state = latest.duplicate(false)
	var container: Dictionary = latest.get("world",{}).duplicate(false) if map_name == "world" else frame_state
	container.armies = drawn
	container.encounters = []
	for source in (latest.get("world",{}).get("encounters",[]) if map_name == "world" else latest.get("encounters",[])):
		var e: Dictionary = source.duplicate(false)
		if fighting.has(str(e.id)): e.status = "fighting"
		container.encounters.append(e)
	if map_name == "world": frame_state.world = container
	fight_on_screen = not fighting.is_empty()
	previous_time = frame_time
	return {"state":frame_state,"time":frame_time}

# The first answer that carries an army's battle: how late it is against the
# planned start of the fight on the shown clock (0 when it came in time, or when
# the army was not drawn on its way there: the app opened mid-fight).
func note_late_start(source: Dictionary, old: Dictionary, now: float) -> void:
	var id := str(source.get("id", ""))
	if late_starts.has(id) or str(source.get("worldKind", "")) == "pvp":
		return
	var has_battle: bool = source.get("battle") is Dictionary or source.get("presentation") is Dictionary
	if not has_battle and str(source.get("status", "")) != "fighting":
		return
	var waited: bool = not old.is_empty() and not (old.get("battle") is Dictionary or old.get("presentation") is Dictionary) \
		and str(old.get("status", "")) == "outbound"
	var planned := time_value(source, "battleAt", time_value(source, "arrivesAt", INF)) - PREPARE_MS
	var shown := now - delay_ms
	if previous_time > -INF:
		shown = maxf(previous_time, shown)
	late_starts[id] = clampf(shown - planned, 0.0, MAX_LATE_MS) if waited and not is_inf(planned) else 0.0

func record(row: Dictionary) -> void:
	trace.append(row)
	if trace.size() > 512: trace.pop_front()
