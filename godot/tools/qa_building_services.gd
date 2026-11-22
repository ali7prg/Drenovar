extends SceneTree
var game
var checks:=0
var cases:=[]
func check(ok: bool,label: String) -> bool:
	checks+=1
	if not ok:
		push_error(label)
		print(JSON.stringify({"status":"failed","checks":checks,"reason":label,"cases":cases.size()}))
		quit(1)
	return ok
func wait_for(test: Callable) -> bool:
	var end:=Time.get_ticks_msec()+20000
	while not test.call():
		if Time.get_ticks_msec()>end:
			return false
		await process_frame
	return true
func button(node: Node,label: String) -> Button:
	if node is Button and node.text==label:
		return node
	for child: Node in node.get_children():
		var found:=button(child,label)
		if found!=null:
			return found
	return null
func texts(node: Node) -> Array[String]:
	var out: Array[String]=[]
	if node is Label:
		out.append(node.text)
	for child: Node in node.get_children():
		out.append_array(texts(child))
	return out
func admin(path: String,body: Dictionary) -> Dictionary:
	var request:=HTTPRequest.new()
	root.add_child(request)
	request.request("http://127.0.0.1:8792/qa/"+path,["Content-Type: application/json"],HTTPClient.METHOD_POST,JSON.stringify(body))
	var result: Array=await request.request_completed
	request.queue_free()
	return JSON.parse_string(result[3].get_string_from_utf8())
func _initialize() -> void:
	call_deferred("run")
func run() -> void:
	root.size=Vector2i(844,390)
	game=load("res://main.tscn").instantiate()
	root.add_child(game)
	if not check(await wait_for(func():return not game.scene_loading and is_instance_valid(game.stage)),"scene ready"):return
	game.session="device."+"a".repeat(64)
	await game.sync_account()
	game.busy=true
	if not check(await game.v6_panels.load_catalogue(),"catalogue loads during another foreground action"):return
	if not check(game.busy,"catalogue query preserves other action's busy flag"):return
	game.busy=false
	await admin("case",{"type":"B05","level":1,"poor":true})
	await game.sync_account()
	await game.v6_panels.confirm({"kind":"construction","building":"B05","target":2})
	if not check(button(game.modal,"Начать")==null,"insufficient resources cannot start"):return
	if not check(texts(game.modal_body).has("Недостаточно ресурсов"),"real resource reason displayed"):return
	await admin("case",{"type":"B05","level":1})
	await game.sync_account()
	var current: Dictionary=game.state.city.buildings.filter(func(b):return b.conceptType=="B05")[0]
	game.state=game.data.demo.duplicate(true)
	game.showing_cached_state=true
	await game.inspect_building(current)
	if not check(game.v6_panels.enabled() and not game.showing_cached_state,"stale legacy cache refreshed before building action"):return
	if not check(button(game.modal_body,"Улучшить")!=null,"current inspector restored"):return
	await game.command({"kind":"kingdom","action":"upgrade","buildingId":current.id,"expectedLevel":1})
	if not check(button(game.modal_body,"Улучшить")!=null,"retained legacy callback opens current inspector"):return
	game.v6_panels.catalogue={}
	await admin("fault",{"kind":"v6catalog"})
	if not check(not await game.v6_panels.load_catalogue(),"temporary catalogue failure is not accepted"):return
	if not check(game.message.text=="Каталог временно недоступен. Повторите запрос.","real error preserved instead of false unsupported-server text"):return
	if not check(await game.v6_panels.load_catalogue(),"catalogue recovers on retry"):return
	for type: String in ["B11","B12","B13","B15","B16","B17"]:
		await admin("case",{"type":type,"level":11})
		await game.sync_account()
		await game.v6_panels.services(type)
		if type in ["B11","B12","B13","B17"]:
			# Training buildings open the recruitment window (ui_premium/STAGE2.md): «Обучить»
			# checks the server quote and sends that order in place; the running order and its
			# cancel (two taps) stay in the same window.
			var train: Button=game.modal.find_child("RecruitTrain",true,false)
			if not check(train!=null and not train.disabled,"training available "+type+str(texts(game.modal_body))):return
			train.pressed.emit()
			if not check(await wait_for(func():return not game.command_in_progress and not game.v6_panels.recruit.submitting and game.state.v6.orders.any(func(o):return o.status=="pending")),"training accepted "+type):return
			if not check(await wait_for(func():return game.modal.find_child("RecruitOrder",true,false)!=null),"order shown in the window "+type):return
			var stop: Button=game.modal.find_child("RecruitCancel",true,false)
			stop.pressed.emit()
			stop.pressed.emit()
			if not check(await wait_for(func():return not game.command_in_progress and not game.v6_panels.recruit.submitting and game.state.v6.orders.all(func(o):return o.status!="pending")),"training cancelled "+type):return
			cases.append({"service":type,"status":"passed","window":"recruitment"})
			continue
		# The academy and the infirmary (ui_premium/STAGE4A.md) name their first action
		# «ServiceAction»: the first family's «Исследовать», the infirmary's «Лечить».
		var selected: Button=game.modal_body.find_child("ServiceAction",true,false)
		if selected==null:
			for child: Node in game.modal_body.get_children():
				if child is Button:
					selected=child
					break
		if not check(selected!=null,"service action exists "+type):return
		selected.pressed.emit()
		if not check(await wait_for(func():return game.modal_title.text=="Подтвердить работу" and not game.busy and not texts(game.modal_body).has("Рассчитываем стоимость и время…")),"service quote "+type):return
		if not check(button(game.modal,"Начать")!=null,"service available "+type+str(texts(game.modal_body))):return
		button(game.modal,"Начать").pressed.emit()
		if not check(await wait_for(func():return not game.command_in_progress and game.modal_title.text=="Очереди поселения" and game.state.v6.orders.any(func(o):return o.status=="pending")),"service accepted "+type):return
		await game.v6_panels.queues()
		button(game.modal_body,"Отменить работу").pressed.emit()
		if not check(await wait_for(func():return not game.command_in_progress and game.modal_title.text=="Очереди поселения" and game.state.v6.orders.all(func(o):return o.status!="pending")),"service cancelled "+type):return
		cases.append({"service":type,"status":"passed"})
	await admin("case",{"type":"B05","level":11,"bounded":true})
	await game.sync_account()
	await game.v6_panels.trade()
	button(game.modal_body,"Купить Дерево").pressed.emit()
	if not check(await wait_for(func():return not game.command_in_progress and game.modal_title.text=="Очереди поселения"),"market trade accepted"):return
	await game.open_building_ring({"item":{"type":"SUP-03","wall":true},"position":Vector3.ZERO})
	if not check(texts(game.modal_body).has("XI — окончательный уровень."),"procedural wall entry uses actual V6 building"):return
	await game.inspect_plot({"id":"v1-4","x":0,"z":0})
	if not check(game.modal_title.text=="Строительство","empty plot opens current catalogue"):return
	await game.show_city_actions()
	if not check(button(game.modal_body,"Очереди и отмена")!=null,"city menu offers authoritative queues"):return
	var summary:=await admin("summary",{})
	if not check(int(summary.legacy)==0,"no legacy building commands reached server"):return
	var report:={"status":"passed","checks":checks,"states":cases.size(),"services":6,"market_trade":true,"fixture":"synthetic localhost; real Godot menus/buttons and authoritative HTTP server; no real account writes","cases":cases}
	var file:=FileAccess.open(OS.get_environment("DRENOVAR_QA_REPORT") if not OS.get_environment("DRENOVAR_QA_REPORT").is_empty() else "user://1006-native-edge-services.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(report))
	file.close()
	print(JSON.stringify({"status":"passed","states":cases.size(),"checks":checks}))
	game.release_inactive_scene()
	await wait_for(func():return game.prewarm_name.is_empty())
	await create_timer(1.0).timeout
	game.drain_retired_scenes(true)
	game.queue_free()
	await process_frame
	await process_frame
	quit()
