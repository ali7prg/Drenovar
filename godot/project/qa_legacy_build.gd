extends SceneTree

# legacy-build: the build menu of an earlier-layout settlement on the new server
# (legacyUpgrades + server feature "legacyBuild") marks every purpose already
# present — variants included (Сад травника is a Лазарет) — as built, and offers
# only what the server accepts. Without the feature it stays free placement.
#   godot --headless --path . -s qa_legacy_build.gd
var checks := 0
var failures := 0

func check(condition: bool, description: String) -> void:
	checks += 1
	if condition:
		print("ok  ", description)
	else:
		failures += 1
		push_error(description)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var game = load("res://main.tscn").instantiate()
	root.add_child(game)
	var deadline := Time.get_ticks_msec() + 90000
	while (game.scene_loading or not is_instance_valid(game.stage)) and Time.get_ticks_msec() < deadline:
		await process_frame
	var types := ["ECO-05", "ECO-04", "RES-04", "RES-01", "ECO-01", "SUP-05", "ALT-15", "MIL-02", "MIL-01", "MIL-01", "MIL-03", "RES-02", "RES-03", "ALT-08", "SUP-04", "SUP-03", "ECO-03"]
	var buildings := []
	for i in types.size():
		buildings.append({"id": "b%d" % i, "type": types[i], "plotId": "plot-%d" % i, "level": 5})
	var city: Dictionary = game.state.city.duplicate(true)
	city.erase("kingdom")
	city.buildings = buildings
	city.legacyUpgrades = {"schema": 1, "order": null}
	game.state.city = city
	game.state.cityFeatures = ["moveBuilding", "legacyBuild"]
	var expect_built := ["RES-01", "RES-02", "RES-03", "RES-04", "ECO-01", "ECO-02", "ECO-03", "ECO-04", "MIL-01", "MIL-02", "MIL-03", "SUP-01", "SUP-03", "SUP-04", "SUP-05"]
	var expect_open := ["RES-05", "MIL-04", "MIL-05", "SUP-02"]
	check(game.paid_legacy_build(), "Settlement builds through the paid queue")
	for definition in game.data.buildings:
		if definition.variant != "core" or definition.base == "ECO-05" or not game.data.types.has(definition.id):
			continue
		var option: Dictionary = game.build_option(definition)
		if definition.id in expect_built:
			check(option.state == "built", "%s %s: built (%s)" % [definition.id, definition.ru, option.state])
		elif definition.id in expect_open:
			check(option.state in ["ready", "short"], "%s %s: can be built (%s)" % [definition.id, definition.ru, option.state])
	var reason: String = game.built_reason({"id": "SUP-01", "base": "SUP-01"})
	check(reason.contains("Сад травника"), "Лазарет card names the building that holds it: " + reason)
	game.state.cityFeatures = ["moveBuilding"]
	check(not game.paid_legacy_build() and game.build_option({"id": "SUP-01", "base": "SUP-01"}).state == "ready", "Without the server feature: free placement as before")
	print("QA_LEGACY_BUILD checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
