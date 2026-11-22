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
func cost_cards(node: Node) -> Array[String]:
	var out: Array[String]=[]
	if node is PanelContainer and not node.tooltip_text.is_empty():
		out.append(node.tooltip_text)
	for child: Node in node.get_children():out.append_array(cost_cards(child))
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
	var types: Array=[]
	for row: Dictionary in game.v6_panels.catalogue.buildings:
		if int(row.level)==1:types.append(str(row.building_id))
	# The market reproduces the owner's I -> II case first.
	types.erase("B05")
	types.push_front("B05")
	# Levels past main.gd MAX_OPEN_BUILDING_LEVEL are not offered yet (owner, stage 3): a building
	# at the open level or above shows «Скоро» and no entry point asks the server for a quote.
	var cap: int=game.MAX_OPEN_BUILDING_LEVEL
	var capped_states:=0
	for type: String in types:
		for level in range(1,12):
			var setup: Dictionary=await admin("case",{"type":type,"level":level})
			await game.sync_account()
			if not check(game.v6_panels.enabled(),"confirmed V6 state "+type):return
			var current: Dictionary=game.state.city.buildings.filter(func(b):return b.conceptType==type)[0]
			await game.open_building_ring({"item":current,"position":Vector3.ZERO})
			var action: Button=null
			var offered: bool=level<cap
			for item: Button in game.action_ring.buttons:
				if item.tooltip_text==("Улучшить" if offered else "Сведения"):action=item
			if not check(action!=null,"correct ring action "+type+str(level)):return
			action.pressed.emit()
			if not offered and level<11:
				if not check(await wait_for(func():return game.modal_body.find_child("SoonAction",true,false)!=null),"inspector «Скоро» "+type+str(level)):return
				var soon: Button=game.modal_body.find_child("SoonAction",true,false)
				if not check(soon.disabled and soon.text=="Скоро" and button(game.modal_body,"Улучшить")==null,"disabled «Скоро» instead of «Улучшить» "+type+str(level)):return
				if not check(cost_cards(game.modal_body).is_empty() and game.modal_body.find_child("KitRequirements",true,false)==null,"no level-"+str(level+1)+" cost or requirements "+type):return
				var sent: int=game.quotes_sent
				var refused: int=game.capped_requests
				soon.pressed.emit()
				await game.v6_panels.confirm({"kind":"construction","building":type,"target":level+1})
				var direct: Dictionary=await game.request("command",{"kind":"v6quote","intent":{"kind":"construction","building":type,"target":level+1,"economy_version":game.v6_panels.VERSION}})
				var ordered: bool=await game.command({"kind":"v6","intent":{"kind":"construction","building":type,"target":level+1,"economy_version":game.v6_panels.VERSION}})
				if not check(game.quotes_sent==sent and game.capped_requests==refused+3 and direct.get("capped",false) and not ordered,"no quote or order past the open level "+type+str(level)):return
				if not check(game.modal_title.text!="Подтвердить работу" and game.state.v6.orders.all(func(o):return o.status!="pending"),"nothing started "+type+str(level)):return
				capped_states+=1
				cases.append({"type":type,"level":level,"status":"passed","next":"soon"})
				continue
			if not check(await wait_for(func():return button(game.modal_body,"Улучшить")!=null if level<11 else texts(game.modal_body).has("XI — окончательный уровень.")),"inspector "+type+str(level)):return
			if level==11:
				if not check(button(game.modal_body,"Улучшить")==null,"no hidden XII "+type):return
				cases.append({"type":type,"level":level,"status":"passed"})
				continue
			button(game.modal_body,"Улучшить").pressed.emit()
			if not check(await wait_for(func():return game.modal_title.text=="Подтвердить работу" and not game.busy and not texts(game.modal_body).has("Рассчитываем стоимость и время…")),"quote response "+type+str(level)):return
			if not check(button(game.modal,"Начать")!=null,"upgrade available "+type+str(level)+" "+str(texts(game.modal_body))):return
			for resource: String in setup.expected.cost:
				if int(setup.expected.cost[resource]) > 0 and not check(cost_cards(game.modal_body).has(game.RESOURCE_NAMES[resource]+": "+str(int(setup.expected.cost[resource]))),"exact server cost "+type+resource):return
			button(game.modal,"Начать").pressed.emit()
			if not check(await wait_for(func():return not game.command_in_progress and game.modal_title.text=="Очереди поселения" and game.state.v6.orders.any(func(o):return o.status=="pending")),"accepted order "+type+str(level)):return
			var order: Dictionary=game.state.v6.orders.filter(func(o):return o.status=="pending")[0]
			if not check(order.building==type and int(order.target)==level+1,"correct target instance"):return
			await game.v6_panels.queues()
			button(game.modal_body,"Отменить работу").pressed.emit()
			if not check(await wait_for(func():return not game.command_in_progress and game.modal_title.text=="Очереди поселения" and game.state.v6.orders.all(func(o):return o.status!="pending")),"cancelled through UI"):return
			if not check(game.state.v6.stock==setup.source_stock,"exact refund"):return
			await game.v6_panels.confirm({"kind":"construction","building":type,"target":level+1})
			button(game.modal,"Начать").pressed.emit()
			if not check(await wait_for(func():return not game.command_in_progress and game.modal_title.text=="Очереди поселения" and game.state.v6.orders.any(func(o):return o.status=="pending")),"second accepted order"):return
			order=game.state.v6.orders.filter(func(o):return o.status=="pending")[0]
			if level in [3,cap-1]:
				await admin("time",{"now":int(order.ends_at)*1000-1})
				await game.sync_account()
				if not check(game.state.v6.orders.any(func(o):return o.id==order.id and o.status=="pending"),"boundary before completion"):return
			await admin("time",{"now":int(order.ends_at)*1000})
			await game.sync_account()
			if not check(int(game.v6_panels.building(type).level)==level+1,"server completion at boundary "+type+str(level)):return
			cases.append({"type":type,"level":level,"target":level+1,"cancel":"passed","completion":"passed","status":"passed"})
		print("BUILDING_UI_TYPE_OK "+type)
	var report:={"status":"passed","checks":checks,"states":cases.size(),"transitions":cases.size()-capped_states-types.size(),"capped_states":capped_states,"open_level":cap,"fixture":"synthetic localhost; real Godot menus/buttons and authoritative HTTP server; no real account writes","cases":cases}
	var file:=FileAccess.open(OS.get_environment("DRENOVAR_QA_REPORT") if not OS.get_environment("DRENOVAR_QA_REPORT").is_empty() else "user://1006-native-buildings.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(report))
	file.close()
	print(JSON.stringify({"status":"passed","states":cases.size(),"capped_states":capped_states,"checks":checks}))
	game.queue_free()
	await process_frame
	await process_frame
	quit()
