extends SceneTree
# Build 1021: dumps a city like the owner's (16 buildings at level V), its wall as the
# client sends it with a march (main.gd march_wall) and the creature positions, for
# the server's marchRoute (march-lane-routes.mjs).
#   cd godot/project && godot --headless --path . -s ../tools/dump_owner_city.gd -- /tmp/city.json
const OWNER_TYPES := ["ECO-05", "RES-01", "RES-02", "RES-03", "RES-04", "ECO-01", "ECO-02", "ECO-03", "ECO-04",
	"MIL-01", "MIL-02", "MIL-03", "SUP-01", "SUP-03", "SUP-04", "SUP-05"]
func _initialize() -> void:
	call_deferred("run")
func run() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/game.json"))
	var state: Dictionary = data.demo.duplicate(true)
	var buildings: Array = []
	for n in OWNER_TYPES.size():
		buildings.append({"id": "building-%d" % n, "type": OWNER_TYPES[n], "plotId": data.plots[n].id, "level": 5})
	state.city.buildings = buildings
	state.city.kingdom.clearedPlots = data.plots.slice(0, OWNER_TYPES.size()).map(func(p): return p.id)
	var stage = load("res://src/landscape.gd").new()
	root.add_child(stage)
	await stage.setup(data, state, "city", {})
	var walls = stage.walls
	var radii: Array = []
	for r in walls.radii: radii.append(snappedf(r, 0.1))
	var gates: Array = []
	for k in walls.gates.size(): gates.append([int(walls.gates[k]), int(walls.gate_half(k))])
	var wall := {"cx": snappedf(walls.center.x, 0.01), "cz": snappedf(walls.center.y, 0.01), "radii": radii, "gates": gates}
	var out := {"state": state, "wall": wall, "visible": walls.visible, "targets": state.encounters.map(func(e): return {"id": e.id, "x": float(e.position.x), "z": float(e.position.z)})}
	var f := FileAccess.open(OS.get_cmdline_user_args()[0], FileAccess.WRITE)
	f.store_string(JSON.stringify(out))
	f.close()
	print("DUMPED walls.visible=", walls.visible, " gates=", gates)
	quit()
