extends SceneTree

var failures: Array[String] = []
var checks := 0

func check(value: bool, detail: String) -> void:
	checks += 1
	if not value:
		failures.append(detail)
		push_error(detail)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	while not is_instance_valid(game.stage) or game.scene_loading:
		await process_frame
	game.set_process(false)
	check(game.profile_button.get_global_rect().position.x < 140, "Profile must be in upper-left corner")
	check(not game.nav_buttons.city.visible and game.nav_buttons.world.visible, "City has one world switch")
	game.show_controls_menu()
	var labels: Array = game.modal_body.get_children().map(func(n): return n.text if n is Button else "")
	check(labels.has("Поселение и строительство") and labels.has("Плавность на устройстве"), "Menu lost access to city actions or diagnostics")
	game.close_modal()
	var stage = game.stage
	var local_state: Dictionary = game.state.duplicate(true)
	check(not local_state.encounters.is_empty(), "Fixture needs creatures")
	var encounter: Dictionary = local_state.encounters[0]
	stage.target = stage.point(encounter.position)
	stage.zoom = 40
	stage.update_camera(0,true)
	for i in 4:
		stage.present_creatures(local_state,float(local_state.serverTime),.016)
	var creature = stage.creatures.get_node_or_null(NodePath(encounter.id))
	check(creature != null,"Creature not created")
	var identity: int = creature.get_instance_id()
	stage.camera_target = Vector3(1000,0,1000)
	stage.present_creatures(local_state,float(local_state.serverTime)+16,.016)
	check(is_instance_valid(creature) and not creature.visible and not creature.is_queued_for_deletion(),"Camera exit destroyed creature")
	check(creature.process_mode == Node.PROCESS_MODE_DISABLED,"Hidden creature still animates")
	stage.camera_target = stage.target
	stage.present_creatures(local_state,float(local_state.serverTime)+32,.016)
	check(creature.visible and creature.get_instance_id() == identity,"Re-entry rebuilt creature")
	encounter.status = "defeated"
	stage.present_creatures(local_state,float(local_state.serverTime)+48,.016)
	await process_frame
	check(not is_instance_valid(creature),"Defeated creature kept in cache")
	var army := {"id":"qa_runtime_march","status":"outbound","units":{"ENG-01":4},"path":[{"x":0,"z":0},{"x":10,"z":0}],"startsAt":0,"arrivesAt":10000}
	local_state.armies = [army]
	stage.target = Vector3.ZERO
	stage.zoom = 40
	stage.update_camera(0,true)
	stage.present_armies(local_state,5000)
	var group = stage.actors.get_node_or_null("qa_runtime_march")
	check(group != null and group.get_child_count() == 4,"March composition changed")
	var unit_id: int = group.get_child(0).get_instance_id()
	stage.target = Vector3(140,0,110)
	stage.update_camera(0,true)
	stage.present_armies(local_state,5016)
	check(not group.visible and not group.is_queued_for_deletion(),"Camera exit destroyed army")
	stage.target = Vector3.ZERO
	stage.update_camera(0,true)
	stage.present_armies(local_state,5032)
	check(group.visible and group.get_child(0).get_instance_id() == unit_id,"Re-entry rebuilt army")
	army.status = "returned"
	stage.present_armies(local_state,5048)
	await process_frame
	check(not is_instance_valid(group),"Returned army remained alive")
	# Bound hidden cache while preserving every visible actor.
	var parent := Node3D.new()
	stage.add_child(parent)
	var known := {}
	for i in 12:
		var actor := Node3D.new()
		actor.name = "cached"+str(i)
		actor.set_meta("last_visible_ticks",Time.get_ticks_msec())
		parent.add_child(actor)
		known[String(actor.name)] = true
	stage.retain_hidden_actors(parent,known,{},8)
	await process_frame
	check(parent.get_child_count() == 8,"Hidden cache exceeds cap")
	for child in parent.get_children():
		child.set_meta("last_visible_ticks",Time.get_ticks_msec()-11000)
	stage.retain_hidden_actors(parent,known,{},8)
	await process_frame
	check(parent.get_child_count() == 0,"Expired hidden cache retained")
	await game.show_scene("world")
	check(game.nav_buttons.city.visible and not game.nav_buttons.world.visible,"World has one city switch")
	var city = game.scene_cache.city
	game.smoke = true
	game.scene_switch_msec -= 5000
	game._process(1.0 / 60.0)
	check(game.scene_cache.get("city") == city, "City cache expired after a brief visit to the world")
	await game.show_scene("city")
	check(game.stage == city, "Returning to city rebuilt a cached scene")
	await game.show_scene("world")
	game.release_inactive_scene()
	check(is_instance_valid(city) and game.retired_nodes.size() > 48,"Scene was destroyed in one burst")
	var pending: int = game.retired_nodes.size()
	game.drain_retired_scenes()
	check(pending-game.retired_nodes.size() <= 48,"Disposal node budget exceeded")
	while not game.retired_nodes.is_empty():
		game.drain_retired_scenes()
	check(not is_instance_valid(city) and is_instance_valid(game.stage.camera),"Disposal freed active scene or leaked old scene")
	print("QA_RUNTIME checks=",checks," failures=",failures.size())
	quit(0 if failures.is_empty() else 1)
