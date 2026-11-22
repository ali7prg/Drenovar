extends SceneTree
var folder := ""
var game
func _initialize():
 for arg in OS.get_cmdline_user_args():
  if arg.begins_with("--capture-dir="):folder=arg.trim_prefix("--capture-dir=")
 call_deferred("run")
func write_json(name: String,value: Variant):
 var f=FileAccess.open(folder.path_join(name),FileAccess.WRITE);f.store_string(JSON.stringify(value,"  "));f.close()
func run():
 root.size=Vector2i(1366,630)
 game=load("res://main.tscn").instantiate();game.single_scene=true;root.add_child(game)
 while game.scene_loading or not is_instance_valid(game.stage) or game.busy:await process_frame
 if not game.endpoint.begins_with("http://127.0.0.1:8826"):quit(2);return
 await game.device_login();await game.create_settlement();await game.sync_account();game.close_modal()
 var fixture: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("/workspace/drenovar-native-combat/godot/tools/fixtures/city-bank-200.json"))
 var source: Dictionary=fixture.army
 var cache: Dictionary=game.stage.route_for(source.path,true)
 cache.bag=source.units;cache.slots=load("res://src/formations.gd").field_slots(source.units,game.data.englishRoster)
 var encounter: Dictionary=game.state.encounters.filter(func(e):return int(e.level)==2)[0].duplicate(true)
 encounter.position=source.path[-1]
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
 game.stage.camera.size=33.0
 game.hud.hide()
 var overlay=CanvasLayer.new();root.add_child(overlay)
 var label=Label.new();label.position=Vector2(18,12);label.add_theme_font_size_override("font_size",20);label.add_theme_color_override("font_color",Color.WHITE);label.add_theme_color_override("font_outline_color",Color.BLACK);label.add_theme_constant_override("outline_size",6);overlay.add_child(label)
 var id_labels={}
 for id in ["ENG-02_0","ENG-02_5"]:
  var id_label=Label.new();id_label.text=id;id_label.add_theme_font_size_override("font_size",16);id_label.add_theme_color_override("font_color",Color.YELLOW);id_label.add_theme_color_override("font_outline_color",Color.BLACK);id_label.add_theme_constant_override("outline_size",4);overlay.add_child(id_label);id_labels[id]=id_label
 var captured=[];var all_attacks=[]
 for elapsed in range(-800,841,40):
  game.stage.present_armies(state,float(army.battleAt)+elapsed)
  game.stage.present_creatures(state,float(army.battleAt)+elapsed,.04)
  var actor: Node=game.stage.actors.get_node_or_null(NodePath(army.id));var attacks=[];var clips={}
  if actor!=null:
   for unit in actor.get_children():
    clips[str(unit.name)]=str(unit.get_meta("clip",""))
    if unit.get_meta("clip","")=="attack":
     attacks.append(str(unit.name))
     if str(unit.name) not in all_attacks:all_attacks.append(str(unit.name))
    if id_labels.has(str(unit.name)):
     id_labels[str(unit.name)].position=game.stage.camera.unproject_position(unit.global_position+Vector3.UP*2)
     id_labels[str(unit.name)].text=str(unit.name)+" "+str(unit.get_meta("clip",""))
  label.text="DRENOVAR build %s | exact bank fixture | t=%d ms\nAttack: %s\nLinux software OpenGL; deterministic rendered samples, NOT iPhone/FPS acceptance"%[ProjectSettings.get_setting("application/config/build_number"),elapsed,", ".join(attacks) if not attacks.is_empty() else "none"]
  await process_frame
  await RenderingServer.frame_post_draw
  if elapsed in [0,240,480,720]:
   var file="frame-%04d.png"%elapsed
   root.get_texture().get_image().save_png(folder.path_join(file));captured.append({"elapsed_ms":elapsed,"file":file,"attacks":attacks,"clips":clips});print("CAPTURE ",file," ",attacks)
 write_json("frames.json",{"build":ProjectSettings.get_setting("application/config/build_number"),"method":"same recorded authoritative server events and exact bank geometry; deterministic 40ms simulation steps; Godot4.6.3 Linux software OpenGL; no production or staging requests, local synthetic in-memory setup only; HUD hidden for capture; diagnostic labels overlay actor metadata; no device or realtime FPS claim","camera_position":str(game.stage.camera.position),"camera_size":game.stage.camera.size,"attacks":all_attacks,"frames":captured,"valid_contact_members":plan.slot_solver.diagnostics.filter(func(d):return d.get("valid",false) and not d.reserve).map(func(d):return d.id)})
 game.queue_free();await process_frame;await process_frame;quit(0)
