extends SceneTree
# Real main scene, real touch path and local HTTP. Fixture delays failed route
# previews 1200ms and commands 2500ms; two responses fail AFTER commit.
var game
var failures := []
var checks := 0
func _initialize() -> void: call_deferred("run")
func check(ok: bool, label: String) -> void:
 checks += 1
 if not ok: failures.append(label)
 print("RESPONSIVENESS ",label," ",ok)
func wait_until(test: Callable, seconds := 20.0) -> bool:
 var end := Time.get_ticks_msec()+int(seconds*1000)
 while not test.call():
  if Time.get_ticks_msec()>end:return false
  await process_frame
 return true
func find_button(node: Node,title: String) -> Button:
 if node is Button and node.text==title:return node
 for child in node.get_children():
  var value:=find_button(child,title)
  if value!=null:return value
 return null
func tap(node: Control) -> void:
 if node==null:check(false,"touch target exists");return
 var at:=node.get_global_rect().get_center()
 for pressed in [true,false]:
  var event:=InputEventScreenTouch.new();event.position=at;event.pressed=pressed;root.push_input(event,true)
  await process_frame
 await process_frame
func select_party(units: Dictionary) -> void:
 var roster: Array=game.data.englishRoster.filter(func(u):return int(game.state.healthy.get(u.id,0))>0)
 var spins: Array=game.modal_body.find_children("*","SpinBox",true,false)
 for i in spins.size():spins[i].value=0
 for i in spins.size():spins[i].value=units.get(roster[i].id,0)
func api_stat(key: String) -> int:
 var value: Variant=game.api.get(key)
 return int(value) if value!=null else 0
func run() -> void:
 root.size=Vector2i(1366,630)
 game=load("res://main.tscn").instantiate();game.single_scene=true;root.add_child(game)
 if not await wait_until(func():return not game.scene_loading and is_instance_valid(game.stage) and not game.busy,90):quit(2);return
 if not game.endpoint.begins_with("http://127.0.0.1:"):quit(2);return
 await game.device_login();await game.create_settlement();await game.sync_account();game.close_modal()
 var target: Dictionary=game.state.encounters.filter(func(e):return int(e.level)==3)[0]
 game.inspect_encounter(target);await process_frame;await process_frame
 await tap(find_button(game.modal_footer,"Атаковать"))
 check(await wait_until(func():return game.modal_title.text=="Создать войско",5),"Attack opens formation")
 select_party({"ENG-01":105,"ENG-02":95})
 await create_timer(.3).timeout
 # Change selection during a deliberately slow preview, then restore it.
 var spins: Array=game.modal_body.find_children("*","SpinBox",true,false)
 for i in 12:
  spins[0].value=104 if i%2==0 else 105
  await create_timer(.025).timeout
 await create_timer(.2).timeout
 check(game.api.threads.size()<=3,"preview slider changes do not flood workers")
 var send: Button=game.modal_footer.find_child("MarchSend",true,false)
 var quote: Label=game.modal_body.find_child("MarchQuote",true,false)
 var before: int=game.state.armies.size()
 var at:=Time.get_ticks_msec()
 await tap(send)
 check(send.disabled and send.text=="Отправляем…" and Time.get_ticks_msec()-at<100,"Send feedback within100ms of actual tap")
 check(find_button(game.modal_footer,"Очистить").disabled,"submitted roster locked")
 await tap(send)
 await create_timer(1.4).timeout
 check(quote.text=="Отправляем отряд…","late failed preview cannot replace Sending quote")
 check(game.diagnostics.network_failures==0,"cancelled preview is not offline")
 check(api_stat("requests_cancelled")>0,"obsolete active preview actually cancelled")
 await tap(find_button(game.modal_header,"×"))
 check(not game.modal.visible,"close works while command pending")
 game.open_modal("Другая панель")
 check(await wait_until(func():return not game.command_in_progress and not game.busy,20),"command settles after close and retries")
 check(game.modal.visible and game.modal_title.text=="Другая панель","late command does not close new panel")
 await game.poll_account_state(true)
 check(game.state.armies.size()==before+1,"double touch and retries create one army")
 var sent: Array=game.state.armies.filter(func(a):return a.target==target.id)
 check(sent.size()==1 and int(sent[0].units.get("ENG-01",0))==105 and int(sent[0].units.get("ENG-02",0))==95,"200-unit screenshot composition preserved")
 check(game.diagnostics.network_failures==0 and game.diagnostics.server_failures==0 and not game.connection_badge.visible,"network badge clears after confirmed response")
 # Second real command in the same scene/session; preview still fails.
 target=game.state.encounters.filter(func(e):return int(e.level)==1)[0]
 game.inspect_encounter(target);await process_frame;await process_frame;await tap(find_button(game.modal_footer,"Атаковать"))
 await wait_until(func():return game.modal_title.text=="Создать войско",5)
 select_party({"ENG-03":5,"ENG-06":2})
 await create_timer(1.6).timeout
 send=game.modal_footer.find_child("MarchSend",true,false)
 check(not send.disabled,"preview503 does not forbid authoritative command")
 await tap(send)
 check(await wait_until(func():return not game.command_in_progress and not game.busy,12),"second march finishes")
 check(game.state.armies.size()==before+2,"second target receives one army")
 check(api_stat("peak_active")<=4,"active HTTP workers bounded")
 print(JSON.stringify({"checks":checks,"failures":failures,"peak_http_workers":api_stat("peak_active"),"cancelled_requests":api_stat("requests_cancelled"),"method":"Linux Godot main scene, real touch, delayed loopback HTTP, 200-unit first army; no iPhone acceptance"}))
 await wait_until(func():return game.api.threads.is_empty() and game.old_api.threads.is_empty(),5)
 game.queue_free();await process_frame;await process_frame;await create_timer(.6).timeout
 quit(0 if failures.is_empty() else 1)
