extends SceneTree
const Clock = preload("res://src/combat_presentation.gd")
const Formation = preload("res://src/formations.gd")
var failures: Array[String] = []
var checks := 0
func check(ok: bool, message: String) -> void:
	checks += 1
	if not ok: failures.append(message); push_error(message)
func _initialize() -> void:
	for unit in ["ENG-03","ENG-04","ENG-10"]:
		for cadence in [200,800,1200]:
			var clock = Clock.new()
			var next := 0
			var state := {}
			for now in range(0,45000,20):
				if now >= next:
					next += cadence
					var events := []
					for i in 20:
						if 4000+i*2000 <= now:
							events.append({"at":i*2000,"kind":"soldier_attack","unitId":unit,"index":0,"damage":5,"creatureHP":100-(i+1)*5,"eventId":"army/4000/%d"%i})
					state = {"playerId":"synthetic","serverTime":now,"armies":[{"id":"army","target":"beast","status":"fighting" if now>=4000 else "outbound","units":{unit:1},"battleAt":4000,"battleEndsAt":44000,"arrivesAt":4000,"battle":{"events":events}}],"encounters":[{"id":"beast","status":"fighting"}]}
				clock.frame(state,now,"city")
			var releases := {}; var contacts := {}
			for event in clock.trace:
				if event.phase == "release": releases[event.id] = releases.get(event.id,0)+1
				if event.phase == "contact": contacts[event.id] = contacts.get(event.id,0)+1
			check(releases.size()==20 and contacts.size()==20,"20 release/contact %s cadence=%d got %d/%d"%[unit,cadence,releases.size(),contacts.size()])
			check(releases.values().all(func(n):return n==1) and contacts.values().all(func(n):return n==1),"unique markers")
			var before: float = clock.frame_time
			clock.frame({"playerId":"synthetic","serverTime":1,"armies":[],"encounters":[]},10000,"city")
			check(clock.frame_time>=before,"late response cannot rewind")
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var a := {"units":{"ENG-01":5},"returnUnits":{"ENG-01":2},"battle":{"events":[{"at":0,"kind":"creature_attack","unitId":"ENG-01","index":0,"hp":0},{"at":200,"kind":"creature_attack","unitId":"ENG-01","index":1,"hp":0},{"at":400,"kind":"creature_attack","unitId":"ENG-01","index":2,"hp":0}]}}
	var slots := Formation.returning_slots(a,data.englishRoster)
	check(slots.map(func(s):return s.index)==[3,4],"legacy city returns original survivors")
	a.erase("battle");a.presentation={"returnMembers":[{"unitId":"ENG-01","index":3},{"unitId":"ENG-01","index":4}]}
	check(Formation.returning_slots(a,data.englishRoster).map(func(s):return s.index)==[3,4],"cold reconnect uses server member IDs")
	var tail = Clock.new()
	var defeat := {"id":"dead-army","target":"beast","status":"returned","battleAt":1000,"battleEndsAt":2000,"returnStartsAt":2000,"returnsAt":2000,"returnUnits":{},"units":{"ENG-01":1},"presentation":{"originalUnits":{"ENG-01":1},"events":[{"at":1000,"kind":"creature_attack","unitId":"ENG-01","index":0,"hp":0}]}}
	var ended := {"playerId":"test","serverTime":2100,"armies":[defeat],"encounters":[{"id":"beast","status":"alive"}],"world":{"armies":[],"encounters":[]}}
	tail.frame(ended,4000,"city")
	check(tail.frame_state.armies.size()==1 and tail.frame_state.armies[0].status=="fighting","same-tick defeat retains terminal presentation")
	# Frames keep coming (60 Hz); a stall is caught up, not jumped over.
	var t := 4000.0
	while t < 7000.0:
		t += 16.0
		tail.frame(ended,t,"city")
	check(tail.frame_state.armies.is_empty(),"defeat tail is bounded")
	# A long gap (app in the background) leaves at most MAX_LAG_MS of catching up.
	var paused = Clock.new()
	paused.frame(ended,4000,"city")
	paused.frame(ended,60000,"city")
	check(60000.0 - paused.delay_ms - paused.frame_time <= paused.MAX_LAG_MS + 1.0,"background gap does not replay minutes")
	tail.frame(ended,7100,"world")
	check(tail.frame_state.world.armies.is_empty(),"map switch never carries city actors into world")
	print(JSON.stringify({"checks":checks,"failures":failures,"method":"headless presentation clock and identity; no device/render acceptance"}))
	quit(0 if failures.is_empty() else 1)
