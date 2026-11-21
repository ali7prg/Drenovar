extends SceneTree
# ENG squad pipeline · exercises the REAL landscape.gd::play_animation clip search on dummy clip
# sets (good names vs. names that hijack walk/idle/attack/hit, drill fallback = last match).
# usage: "$GODOT" --headless --path "$PROJECT" -s "$SQUAD/pipeline/godot_clip_search.gd"
const Landscape = preload("res://src/landscape.gd")
func make(names: Array) -> Node3D:
	var root := Node3D.new()
	var player := AnimationPlayer.new()
	var lib := AnimationLibrary.new()
	for n in names:
		var a := Animation.new()
		a.length = 1.0
		lib.add_animation(n, a)
	player.add_animation_library("", lib)
	root.add_child(player)
	get_root().add_child(root)
	return root
func pick(stage, names: Array, preferred: String, fallback := "") -> String:
	var m := make(names)
	stage.play_animation(m, preferred, fallback, 0.5)
	var p: AnimationPlayer = m.get_child(0)
	var r := String(p.assigned_animation)
	m.queue_free()
	return r
func _initialize() -> void:
	call_deferred("run")
func run() -> void:
	var stage = Landscape.new()
	get_root().add_child(stage)
	var cases := [
		[["Idle", "Walk", "Attack", "Hit", "Death", "Sword_Drill", "Walk_Start", "Idle_Ready", "Attack_Release", "Hit_Shield", "Death_Fall"], ["idle", "walk", "attack", "hit", "death"]],
		[["Idle", "Walk", "Combat_Idle", "Battle_Walk", "Attack", "Aim_Attack", "Block_Hit", "Hit", "Death"], ["idle", "walk", "attack", "hit"]],
		[["Idle", "Walk", "Bridle_Adjust", "Sidewalk", "Trot_To_Walk", "Hit", "Death"], ["idle", "walk"]],
		[["Idle", "Walk", "Hit", "Death", "Sword_Drill"], ["attack|Sword_Drill"]],
		[["Idle", "Walk", "Hit", "Death", "Sword_Drill", "Sword_Drill_Fast"], ["attack|Sword_Drill"]],
	]
	for c in cases:
		var line := []
		for q in c[1]:
			var bits: PackedStringArray = q.split("|")
			line.append("%s -> %s" % [q, pick(stage, c[0], bits[0], bits[1] if bits.size() > 1 else "")])
		print("CLIPS ", c[0], "\n   ", ", ".join(line))
	quit(0)
