extends SceneTree
const Clock = preload("res://src/combat_presentation.gd")
const Formation = preload("res://src/formations.gd")
var failures: Array[String] = []
var checks := 0
func check(ok: bool, message: String) -> void:
	checks += 1
	if not ok: failures.append(message); push_error(message)
func _initialize() -> void:
	for unit in ["ENG-03","ENG-04"]:
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
	# A small creature killed by the first volley (the live city shape: 18 blows
	# all at 0 ms, fight 200 ms): the blows are shown one after another across the
	# stretched fight, in server order, with the same HP after each blow; and a
	# later poll with the same step keeps every shown time (no replay).
	var volley := []
	for i in 18:
		volley.append({"at":0,"kind":"soldier_attack","unitId":"ENG-03","index":i,"damage":78,"creatureHP":maxi(0,1400-(i+1)*78)})
	var short := {"id":"volley","units":{"ENG-03":18},"startsAt":0,"arrivesAt":16000,"battleAt":16000,"battleEndsAt":16200,"presentation":{"events":volley}}
	var shown := short.duplicate(true); Clock.stretch(shown,{})
	var ats: Array = shown.presentation.events.map(func(e):return float(e.at))
	var sorted := ats.duplicate(); sorted.sort()
	check(ats == sorted and ats[0] == 0.0 and ats[-1] > 5000.0 and ats[-1] < Clock.MIN_FIGHT_MS,"one-step volley spread over the shown fight: "+str(ats))
	check(range(17).all(func(i):return float(ats[i+1])-float(ats[i]) > 250.0),"volley blows are apart: "+str(ats))
	check(shown.presentation.events.map(func(e):return e.creatureHP) == volley.map(func(e):return e.creatureHP),"volley HP sequence unchanged")
	# A walk long enough for the whole stretch (the walk home may at most double its speed).
	var kill := {"id":"kill","units":{"ENG-06":6},"startsAt":0,"arrivesAt":30000,"battleAt":30000,"battleEndsAt":30600,"returnStartsAt":30600,"presentation":{"events":[{"at":0,"kind":"soldier_attack","unitId":"ENG-03","index":0,"creatureHP":900},{"at":600,"kind":"soldier_attack","unitId":"ENG-05","index":0,"creatureHP":0}]}}
	Clock.stretch(kill,{})
	var shown_end := float(kill.battleEndsAt) - 30000.0
	check(shown_end >= Clock.MIN_FIGHT_MS and shown_end - float(kill.presentation.events[-1].at) >= 800.0,"killing blow at the battle end is shown inside the fight: %s / %s"%[kill.presentation.events[-1].at, shown_end])
	check(float(kill.returnStartsAt) == float(kill.battleEndsAt),"return starts at the shown fight end")
	var later: Array = volley + [{"at":200,"kind":"creature_attack","unitId":"ENG-03","index":0,"hp":10}]
	check(Clock.step_offsets(later,400.0).slice(0,18) == Clock.step_offsets(volley,200.0),"a step's spread does not depend on later steps")
	tail.frame(ended,7100,"world")
	check(tail.frame_state.world.armies.is_empty(),"map switch never carries city actors into world")
	print(JSON.stringify({"checks":checks,"failures":failures,"method":"headless presentation clock and identity; no device/render acceptance"}))
	quit(0 if failures.is_empty() else 1)
