extends SceneTree
const Slots=preload("res://src/combat_slots.gd")
var failures:=0
var results: Array=[]

func _initialize() -> void:call_deferred("run")

func run() -> void:
	var cases: Array=JSON.parse_string(FileAccess.get_file_as_string("res://assets/combat-lab/regressions.json"))
	var matrix: Array=JSON.parse_string(FileAccess.get_file_as_string("res://assets/combat-lab/matrix.json"))
	cases.append_array([matrix[0],matrix[1],matrix[4]])
	var data: Dictionary=load("res://src/combat_lab.gd").load_game_data()
	var stage=load("res://src/landscape.gd").new();root.add_child(stage)
	await stage.setup(data,cases[0].snapshots[0].state,"world",{})
	for c in cases:
		var state: Dictionary=c.snapshots[0].state
		if stage.map_name!=c.map:
			stage.free();stage=load("res://src/landscape.gd").new();root.add_child(stage);await stage.setup(data,state,c.map,{})
		var target: Dictionary=(state.world.encounters if c.map=="world" else state.encounters).filter(func(e):return e.id==c.target)[0]
		stage.target=stage.ground_point(stage.point(target.position));stage.zoom=42;stage.update_camera(0,true)
		var begin:=Time.get_ticks_usec()
		stage.present_armies(state,float(state.serverTime))
		var rows: Array=[]
		for cache in stage.army_routes.values():
			if not cache.has("engage"):continue
			var plan: Dictionary=cache.engage
			var solver=Slots.new();solver.prepare(stage,plan.beast,plan.face,plan.body)
			for slot in cache.slots:
				var key:="%s:%d"%[slot.id,slot.index]
				var position: Vector3=plan.places[key]
				var yaw:=atan2(plan.beast.x-position.x,plan.beast.z-position.z)
				var check: Dictionary=solver.test(position,yaw,bool(slot.mounted))
				if not check.valid:failures+=1
				else:solver.occupied.append({"id":key,"polygon":Slots.footprint(check.position,check.basis,check.half+Vector2.ONE*Slots.MARGIN)})
				var chosen: Dictionary={}
				if plan.has("slot_solver"):
					for row in plan.slot_solver.diagnostics:
						if row.id==key:chosen=row
				rows.append({"member":key,"valid":check.valid,"reason":check.get("reason","ok"),"obstacles":check.get("obstacles",[]),"position":[position.x,position.y,position.z],"slope_degrees":rad_to_deg(acos(clampf(check.get("normal",Vector3.UP).y,-1,1))),"plane_residual_m":check.get("residual"),"reserve":chosen.get("reserve"),"march_prefix_verified":chosen.get("march_prefix_verified"),"last_approach_verified":plan.slot_solver.segment_clear(chosen.path[-2],chosen.path[-1],bool(slot.mounted)) if chosen.get("path",[]).size()>1 else null})
			solver.clear()
		if c.map=="city" and rows.all(func(r):return r.reserve):failures+=1
		var report:={"case":c.name,"method":"footprint support + private 3D triangle collision space, original static geometry, alpha-card trees explicitly use trunk footprint proxies","ms":(Time.get_ticks_usec()-begin)/1000.0,"members":rows}
		results.append(report);print("SLOTS ",JSON.stringify(report))
		for child in stage.actors.get_children():child.free()
		stage.army_routes.clear()
		await process_frame
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--output="):FileAccess.open(arg.trim_prefix("--output="),FileAccess.WRITE).store_string(JSON.stringify(results,"  "))
	stage.free()
	print("QA_BATTLE_SLOTS failures=",failures)
	quit(0 if failures==0 else 1)
