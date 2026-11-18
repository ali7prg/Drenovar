extends Node3D

# Bounded spatial voice pool. Marker consumers pass an immutable event/phase key;
# duplicates, reconnect history and contacts >300ms late never replay audio.
const LIMIT := 8
var voices: Array[AudioStreamPlayer3D] = []
var samples := {}
var seen := {}
var order: Array[String] = []
var trace: Array = []
var enabled := true

func _ready() -> void:
	for family in ["foot","hoof","bow","crossbow","javelin","flesh","armor","wood","fall"]:
		var variants: Array = []
		for i in 3:variants.append(load("res://assets/combat-audio/%s-%d.wav"%[family,i]))
		samples[family]=variants
	for i in LIMIT:
		var voice:=AudioStreamPlayer3D.new();voice.volume_db=-14;voice.unit_size=12;voice.max_distance=70;voice.max_db=-8
		add_child(voice);voices.append(voice)

func cue(id: String, family: String, at: Vector3, priority: int, lateness := 0.0) -> void:
	if seen.has(id):return
	seen[id]=true;order.append(id)
	if order.size()>512:seen.erase(order.pop_front())
	if not enabled or lateness>300.0 or not samples.has(family):return
	var selected: AudioStreamPlayer3D
	for voice in voices:
		if not voice.playing:selected=voice;break
	if selected==null:
		for voice in voices:
			if int(voice.get_meta("priority",0))<priority:
				selected=voice;break
	if selected==null:return
	selected.stop();selected.global_position=at;selected.stream=samples[family][posmod(id.hash(),3)]
	selected.set_meta("priority",priority);selected.play()
	trace.append({"id":id,"family":family,"priority":priority,"lateness_ms":lateness})
	if trace.size()>512:trace.pop_front()

func consume(stage: Node3D) -> void:
	for marker in stage.combat_view.markers:
		var e: Dictionary=marker.event
		var position: Vector3=stage.target
		var actor:=stage.creatures.get_node_or_null(NodePath(str(marker.target))) as Node3D
		if actor!=null:position=actor.global_position
		var family: String
		var priority:=2
		if marker.phase=="release":family={"ENG-03":"bow","ENG-04":"crossbow","ENG-10":"javelin"}.get(e.get("unitId"),"bow")
		elif e.kind=="soldier_attack":
			family="fall" if float(e.get("creatureHP",1))<=0 else "flesh"
			if family=="fall":priority=3
		else:
			var key:="%s:%d"%[e.get("unitId",""),int(e.get("index",0))]
			position=stage.army_routes.get(marker.army_id,{}).get("member_at",{}).get(key,position)
			family="fall" if float(e.get("hp",1))<=0 else "armor" if e.get("unitId") in ["ENG-06","ENG-07","ENG-09"] else "wood"
			if family=="fall":priority=3
		cue(marker.id+"/"+marker.phase,family,position,priority,marker.lateness)
