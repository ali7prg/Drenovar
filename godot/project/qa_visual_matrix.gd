extends SceneTree
var stage: Node3D
var output:="/tmp/drenovar-visual-matrix"
func _initialize():
 for arg in OS.get_cmdline_user_args():
  if arg.begins_with("--output="):output=arg.trim_prefix("--output=")
 DirAccess.make_dir_recursive_absolute(output);call_deferred("run")
func run():
 root.size=Vector2i(844,390)
 var cases: Array=JSON.parse_string(FileAccess.get_file_as_string("res://assets/combat-lab/matrix.json"))
 var data: Dictionary=load("res://src/combat_lab.gd").load_game_data()
 var rows: Array=[]
 for c in cases:
  if stage==null or stage.map_name!=c.map:
   if stage!=null:stage.free()
   stage=load("res://src/landscape.gd").new();root.add_child(stage)
   await stage.setup(data,c.snapshots[0].state,c.map,{})
  for child in stage.actors.get_children():child.free()
  stage.army_routes.clear();stage.fx_timelines.clear();stage.fallen_bodies.clear()
  stage.combat_view=load("res://src/combat_presentation.gd").new()
  var state: Dictionary=c.snapshots[-1].state
  var source: Dictionary=c.snapshots[0].state
  var a: Dictionary=(source.world.armies if c.map=="world" else source.armies)[0]
  var now:=float(a.battleAt)+float(c.first_hit)+200.0
  var frame: Dictionary=stage.combat_view.frame(state,now+1650,c.map)
  var e: Dictionary=(source.world.encounters if c.map=="world" else source.encounters).filter(func(t):return t.id==c.target)[0]
  stage.target=stage.ground_point(stage.point(e.position))+Vector3(-3,2,-3)
  stage.zoom=23 if c.map=="city" else 42;stage.update_camera(0,true)
  for i in 4:
   stage.present_armies(frame.state,frame.time);stage.present_creatures(frame.state,frame.time,.1)
   await process_frame
  await RenderingServer.frame_post_draw
  root.get_texture().get_image().save_png(output.path_join(c.name+".png"))
  var count:=0;var clips:={};var reserve:=0
  for army in stage.actors.get_children():
   for unit in army.get_children():
    if unit.name==&"Ferry":continue
    count+=1;var clip: String=unit.get_meta("clip","");clips[clip]=int(clips.get(clip,0))+1
  for cache in stage.army_routes.values():
   for is_reserve in cache.get("engage",{}).get("reserves",{}).values():
    if is_reserve:reserve+=1
  rows.append({"case":c.name,"actors":count,"clips":clips,"reserve":reserve,"at":now,"method":"stopped current-code replay, contact+200ms; NOT continuous/device acceptance"})
  print("MATRIX ",c.name," ",count)
 FileAccess.open(output.path_join("matrix.json"),FileAccess.WRITE).store_string(JSON.stringify(rows,"  "))
 stage.free();quit()
