extends SceneTree

# Real city geometry and recorded server events at the failed far-bank position.
# Requires a fresh synthetic playable-server.mjs with --server=http://127.0.0.1:PORT --hosted.
func _initialize():call_deferred("run")
func run():
 var game=load("res://main.tscn").instantiate();game.single_scene=true;root.add_child(game)
 while game.scene_loading or not is_instance_valid(game.stage) or game.busy:await process_frame
 if not game.endpoint.begins_with("http://127.0.0.1:"):quit(2);return
 await game.device_login();await game.create_settlement();await game.sync_account();game.close_modal()
 var fixture: Dictionary=JSON.parse_string(FileAccess.get_file_as_string(get_script().resource_path.get_base_dir().path_join("fixtures/city-bank-200.json")))
 var source: Dictionary=fixture.army
 var cache: Dictionary=game.stage.route_for(source.path,true)
 cache.bag=source.units;cache.slots=load("res://src/formations.gd").field_slots(source.units,game.data.englishRoster)
 var encounter: Dictionary=game.state.encounters.filter(func(e):return int(e.level)==2)[0].duplicate(true)
 encounter.position=source.path[-1]
 game.stage.engage_sync=true
 var plan: Dictionary=game.stage.engage_plan(cache,encounter)
 game.set_process(false)
 var army: Dictionary=source.duplicate(true)
 army.status="fighting";army.battleAt=army.arrivesAt;army.battle={"events":fixture.events}
 var state: Dictionary=game.state.duplicate(true)
 state.armies=[army]
 for e in state.encounters:
  if int(e.level)==2:e.position=encounter.position;e.id=army.target;e.status="fighting"
 var centre: Vector3=plan.beast
 game.stage.camera.position=centre+Vector3(15,24,18);game.stage.camera.look_at(centre)
 var attacks:=[]
 for n in 24:
  game.stage.present_armies(state,float(army.battleAt)+n*40.0)
  await process_frame
  var actor: Node=game.stage.actors.get_node_or_null(NodePath(army.id))
  if actor!=null:
   for unit in actor.get_children():
    if unit.get_meta("clip","")=="attack" and unit.name not in attacks:attacks.append(unit.name)
 print(JSON.stringify({"attack_members":attacks,"passed":not attacks.is_empty(),"valid_contact_members":plan.slot_solver.diagnostics.filter(func(d):return d.get("valid",false) and not d.reserve).map(func(d):return d.id),"original_member_ids":cache.slots.map(func(m):return "%s:%d"%[m.id,m.index]),"method":"recorded server events, exact failing far-bank path and city geometry; headless, not device acceptance"}))
 game.queue_free();await process_frame;quit(0 if not attacks.is_empty() else 1)
