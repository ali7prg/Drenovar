extends Node3D

# Offline, synthetic audit fixtures. Uses the shipped renderer and presentation
# clock at wall-clock speed. No account, API client or network request exists here.
var cases: Array = []
var data: Dictionary
var stage: Node3D
var index := -1
var loading := false
var started := 0
var next_packet := -INF
var state := {}
var paused := false
var pause_at := 0
var title := Label.new()
var completed := 0
var soak := 0
var output := ""
var samples: Array[float] = []
var updates: Array[float] = []
var last_frame := 0
var report: Array = []
var captured := false
var selector := OptionButton.new()

static func load_game_data() -> Dictionary:
	var result: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	# Same manifest merge as the current main.gd entry (including levels VI–XI).
	var art: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://assets/city/architecture-v6/manifest.json"))
	for type: String in art.get("levels",{}):
		if not result.levelModels.has(type):result.levelModels[type]={}
		result.levelModels[type].merge(art.levels[type],false)
	for id: String in art.get("units",{}):result.unitModels[id]={"field":art.units[id].path,"drill":""}
	return result

func _ready() -> void:
	data = load_game_data()
	cases = JSON.parse_string(FileAccess.get_file_as_string("res://assets/combat-lab/cases.json"))
	cases.append_array(JSON.parse_string(FileAccess.get_file_as_string("res://assets/combat-lab/matrix.json")))
	cases.append_array(JSON.parse_string(FileAccess.get_file_as_string("res://assets/combat-lab/regressions.json")))
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--soak="): soak = int(arg.trim_prefix("--soak="))
		if arg.begins_with("--capture="): output = arg.trim_prefix("--capture=")
	if not output.is_empty(): DirAccess.make_dir_recursive_absolute(output)
	var canvas := CanvasLayer.new(); add_child(canvas)
	var panel := PanelContainer.new(); canvas.add_child(panel)
	var safe:=DisplayServer.get_display_safe_area()
	var screen_size:=Vector2(DisplayServer.screen_get_size())
	var ratio:=Vector2(get_viewport().size)/screen_size if screen_size.x>0 and screen_size.y>0 else Vector2.ONE
	var inset:=Vector2(maxf(12,safe.position.x*ratio.x),maxf(10,safe.position.y*ratio.y))
	panel.position=inset;panel.size=Vector2(get_viewport().size.x-inset.x*2,110)
	var column := VBoxContainer.new(); panel.add_child(column)
	column.add_child(title); title.add_theme_font_size_override("font_size",22)
	title.clip_text=true;title.text_overrun_behavior=TextServer.OVERRUN_TRIM_ELLIPSIS
	for c in cases:selector.add_item("%s · %s · %s"%[c.name,c.map,JSON.stringify(c.units)])
	selector.fit_to_longest_item=false;selector.custom_minimum_size.y=44;column.add_child(selector)
	selector.item_selected.connect(func(which):
		if not loading:begin(which)
	)
	var buttons := HBoxContainer.new(); column.add_child(buttons)
	for label in ["Предыдущий","Пауза","Следующий","Опоры","Звук"]:
		var button := Button.new(); button.text=label; button.custom_minimum_size=Vector2(130,48);button.size_flags_horizontal=Control.SIZE_EXPAND_FILL;buttons.add_child(button)
		button.pressed.connect(func():
			if loading: return
			match label:
				"Звук":
					stage.combat_audio.enabled=not stage.combat_audio.enabled
					button.text="Звук: вкл" if stage.combat_audio.enabled else "Звук: выкл"
				"Предыдущий": begin(posmod(index-1,cases.size()))
				"Следующий": begin((index+1)%cases.size())
				"Пауза":
					paused = not paused
					if paused: pause_at=Time.get_ticks_msec()
					else: started += Time.get_ticks_msec()-pause_at
				"Опоры":
					if stage.combat_debug == null:
						stage.combat_debug=load("res://src/combat_debug.gd").new();stage.add_child(stage.combat_debug)
					else: stage.combat_debug.visible=not stage.combat_debug.visible
		)
	begin(0)

func begin(which: int) -> void:
	loading=true;index=which;paused=false;captured=false
	selector.select(which)
	var c: Dictionary=cases[index]
	title.text="Загрузка · автономная лаборатория 1009"
	if stage == null or stage.map_name != c.map:
		if stage != null: stage.queue_free();await get_tree().process_frame
		stage=load("res://src/landscape.gd").new();add_child(stage)
		await stage.setup(data,c.snapshots[0].state,c.map,{})
	var initial: Dictionary=c.snapshots[0].state
	var rows: Array=initial.world.encounters if c.map=="world" else initial.encounters
	var target: Dictionary=rows.filter(func(e):return e.id==c.target)[0]
	stage.target=stage.ground_point(stage.point(target.position))+Vector3(-3,2,-3)
	stage.zoom=23.0 if c.map=="city" else 42.0;stage.update_camera(0,true)
	# Every new fixture has its own monotonic clock and event generation.
	stage.combat_view=load("res://src/combat_presentation.gd").new()
	started=Time.get_ticks_msec();next_packet=-INF;last_frame=0;samples.clear();updates.clear();loading=false

func packet(c: Dictionary, elapsed: float) -> Dictionary:
	var snapshot: Dictionary=c.snapshots[0]
	for s in c.snapshots:
		if float(s.elapsed)<=elapsed: snapshot=s
	var result: Dictionary=snapshot.state.duplicate(true)
	var container: Dictionary=result.world if c.map=="world" else result
	var first: Dictionary=c.snapshots[0].state
	var original: Dictionary=(first.world.armies if c.map=="world" else first.armies)[0]
	var army: Dictionary=container.armies[0] if not container.armies.is_empty() else original.duplicate(true)
	var start := float(original.battleAt)
	result.serverTime=start+elapsed
	var events: Array=[];var fallen := {}
	for sequence in c.events.size():
		var event: Dictionary=c.events[sequence].duplicate(true)
		if float(event.at)>elapsed: continue
		event.eventId="%s/%s/%d"%[army.id,start,sequence]
		event.memberId="%s/%s/%s"%[army.id,event.unitId,event.index]
		events.append(event)
		if event.get("hp",1)==0: fallen["%s:%s"%[event.unitId,event.index]]=true
	var survivors: Array=[]
	for id in original.units:
		for member in int(original.units[id]):
			if not fallen.has("%s:%s"%[id,member]): survivors.append({"unitId":id,"index":member})
	army.presentation={"version":1,"originalUnits":original.units,"events":events,"returnMembers":survivors}
	if elapsed<float(original.battleEndsAt)-start:
		army.status="fighting";army.battle={"events":events};army.units=original.units
	container.armies=[army]
	return result

func _process(delta: float) -> void:
	if loading or paused or stage==null: return
	var tick := Time.get_ticks_msec()
	var elapsed := float(tick-started)-1000.0
	var c: Dictionary=cases[index]
	var initial: Dictionary=c.snapshots[0].state
	var army: Dictionary=(initial.world.armies if c.map=="world" else initial.armies)[0]
	var now := float(army.battleAt)+elapsed
	if elapsed>=next_packet:
		state=packet(c,elapsed);next_packet=elapsed+800.0
	var t0 := Time.get_ticks_usec()
	var frame: Dictionary=stage.combat_view.frame(state,now,c.map)
	stage.present_armies(frame.state,frame.time);stage.present_creatures(frame.state,frame.time,delta)
	if stage.combat_debug!=null and stage.combat_debug.visible and tick%5==0: stage.combat_debug.sample(stage)
	updates.append((Time.get_ticks_usec()-t0)/1000.0)
	if last_frame>0: samples.append(float(tick-last_frame))
	last_frame=tick
	title.text="1009 · %s · %s · %.1f c · запись аудита / 1×"%[c.name,JSON.stringify(c.units),elapsed/1000.0]
	if not captured and elapsed>=float(c.first_hit)+1800.0 and not output.is_empty():
		captured=true;save_frame(c.name)
	var final_state: Dictionary=c.snapshots[-1].state
	var final_armies: Array=final_state.world.armies if c.map=="world" else final_state.armies
	var returned := float(army.battleEndsAt)
	if not final_armies.is_empty() and final_armies[0].get("returnsAt") != null: returned=maxf(returned,float(final_armies[0].returnsAt))
	var end := returned-float(army.battleAt)+7000.0
	if elapsed>end:
		finish_case(c)
		completed+=1
		if soak>0 and completed>=soak:
			if not output.is_empty(): FileAccess.open(output.path_join("soak.json"),FileAccess.WRITE).store_string(JSON.stringify(report,"  "))
			get_tree().quit()
		else: begin((index+1)%cases.size())

func save_frame(name: String) -> void:
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(output.path_join(name+".png"))

func finish_case(c: Dictionary) -> void:
	var sorted := samples.duplicate();sorted.sort();var cpu := updates.duplicate();cpu.sort()
	var row := {"case":c.name,"method":"continuous offline fixture, wall clock 1x, synthetic polling min 800ms sampled on rendered frames; Linux render, NOT iPhone acceptance", "viewport":get_viewport().size,"frames":samples.size(),"frame_ms_p50":sorted[sorted.size()/2],"frame_ms_p95":sorted[mini(sorted.size()-1,ceili(sorted.size()*0.95))],"update_ms_p95":cpu[mini(cpu.size()-1,ceili(cpu.size()*0.95))],"static_memory_bytes":OS.get_static_memory_usage(),"objects":Performance.get_monitor(Performance.OBJECT_COUNT),"nodes":get_tree().get_node_count(),"army_routes":stage.army_routes.size(),"fx_timelines":stage.fx_timelines.size(),"corpses":stage.fallen_bodies.size(),"fx_pool_sizes":{},"events":c.events.size()}
	for kind in stage.battle_fx.pools: row.fx_pool_sizes[kind]=stage.battle_fx.pools[kind].size()
	report.append(row);print("COMBAT_LAB ",JSON.stringify(row))
