extends Node3D

# Bounded spatial voice pool. Marker consumers pass an immutable event/phase key;
# duplicates, reconnect history and contacts >300ms late never replay audio.
# Build 1024: recorded sounds (assets/audio/sfx/combat, voice; CREDITS.md) on the SFX and Voice
# buses, 2–6 variations each with pitch and level variation, per-family voice limits, and
# attenuation scaled to the camera's visible area (see Sound.view_extent).
const LIMIT := 8
## family -> sound stem (src/audio/sound_bank.gd)
const STEMS := {"foot": "combat/foot", "hoof": "combat/hoof", "bow": "combat/bow", "crossbow": "combat/crossbow",
	"javelin": "combat/javelin", "flesh": "combat/flesh", "armor": "combat/armor", "wood": "combat/wood", "fall": "combat/fall",
	"clash": "combat/clash", "shield": "combat/shield", "swing": "combat/swing", "arrow_hit": "combat/arrow_hit",
	"creature_hurt": "combat/creature_hurt", "creature_death": "combat/creature_death", "creature_roar": "combat/creature_roar",
	"horn": "combat/horn", "war_cry": "voice/war_cry", "soldier_hurt": "voice/soldier_hurt", "soldier_death": "voice/soldier_death"}
var voices: Array[AudioStreamPlayer3D] = []
var samples := {}
var seen := {}
var order: Array[String] = []
var trace: Array = []
var enabled := true

func _ready() -> void:
	for family in STEMS:
		samples[family] = STEMS[family]
	for i in LIMIT:
		var voice := AudioStreamPlayer3D.new()
		voice.bus = &"SFX"
		voice.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED
		voice.attenuation_filter_db = -8.0
		voice.attenuation_filter_cutoff_hz = 7000.0
		voice.panning_strength = 0.7
		add_child(voice)
		voices.append(voice)

func sound() -> Node:
	return get_node_or_null("/root/Sound")

func sample(family: String) -> AudioStream:
	var hub := sound()
	if hub == null:
		return null
	var path: String = hub.pick(STEMS[family])
	if path.is_empty():
		return null
	# Still on the loader thread only right after launch: then this one file is finished now.
	return hub.stream_now(path)

func cue(id: String, family: String, at: Vector3, priority: int, lateness := 0.0) -> void:
	if seen.has(id):return
	seen[id]=true;order.append(id)
	if order.size()>512:seen.erase(order.pop_front())
	if not enabled or lateness>300.0 or not samples.has(family):return
	var hub := sound()
	var stem: String = STEMS[family]
	var bus := "Voice" if stem.begins_with("voice/") else "SFX"
	if hub != null and not hub.audible(bus.to_lower()):return
	var same := 0
	for voice in voices:
		if voice.playing and voice.get_meta("family","")==family:same+=1
	var limit := int(hub.LIMIT.get(stem,3)) if hub != null else 3
	if same>=limit and priority<3:return
	var selected: AudioStreamPlayer3D
	for voice in voices:
		if not voice.playing:selected=voice;break
	if selected==null:
		for voice in voices:
			if int(voice.get_meta("priority",0))<priority:
				selected=voice;break
	if selected==null:return
	var value := sample(family)
	if value==null:return
	var extent: float = hub.view_extent() if hub != null else 60.0
	selected.stop();selected.global_position=at;selected.stream=value
	selected.bus=StringName(bus)
	selected.attenuation_model=AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE
	selected.unit_size=extent*0.55;selected.max_distance=extent*3.2
	selected.volume_db=(float(hub.LEVEL.get(stem,-6.0)) if hub != null else -8.0)+randf_range(-1.5,1.0)
	selected.pitch_scale=1.0+randf_range(-0.05,0.05)
	selected.set_meta("priority",priority);selected.set_meta("family",family);selected.play()
	if hub != null:
		hub.counts[stem]=int(hub.counts.get(stem,0))+1
		if hub.DUCK.has(stem):hub.duck(hub.DUCK[stem][0],hub.DUCK[stem][1])
	trace.append({"id":id,"family":family,"priority":priority,"lateness_ms":lateness})
	if trace.size()>512:trace.pop_front()

func consume(stage: Node3D) -> void:
	for marker in stage.combat_view.markers:
		var e: Dictionary=marker.event
		var position: Vector3=stage.target
		var actor:=stage.creatures.get_node_or_null(NodePath(str(marker.target))) as Node3D
		if actor!=null:position=actor.global_position
		var unit: String=str(e.get("unitId",""))
		var key: String=marker.id+"/"+marker.phase
		var roll:=posmod(key.hash(),12)
		if marker.phase=="release":
			cue(key,{"ENG-03":"bow","ENG-04":"crossbow"}.get(unit,"bow"),position,2,marker.lateness)
		elif e.kind=="soldier_attack":
			# Soldiers strike the creature: arrows land, blades clash and cut.
			if float(e.get("creatureHP",1))<=0:
				cue(key,"creature_death",position,3,marker.lateness)
				cue(key+"/fall","fall",position,3,marker.lateness)
				continue
			var family:="arrow_hit" if unit in ["ENG-03","ENG-04"] else "flesh" if unit=="ENG-01" else "clash" if roll%3!=0 else "flesh"
			cue(key,family,position,2,marker.lateness)
			if unit=="ENG-06":cue(key+"/b","flesh",position,2,marker.lateness)
			if roll%4==0:cue(key+"/hurt","creature_hurt",position,2,marker.lateness)
		else:
			# The creature strikes a soldier: shield, armour or a body.
			var member:="%s:%d"%[unit,int(e.get("index",0))]
			position=stage.army_routes.get(marker.army_id,{}).get("member_at",{}).get(member,position)
			if float(e.get("hp",1))<=0:
				cue(key,"fall",position,3,marker.lateness)
				cue(key+"/voice","soldier_death",position,3,marker.lateness)
				continue
			var family:="shield" if unit=="ENG-02" else "armor" if unit=="ENG-06" else "wood" if roll%2==0 else "flesh"
			cue(key,family,position,2,marker.lateness)
			if roll%3==0:cue(key+"/voice","soldier_hurt",position,1,marker.lateness)

## The army reaches the creature: its roar and the soldiers' war cry (once per fight).
func fight_begins(army_id: String, at: Vector3) -> void:
	cue("fight/%s/roar"%army_id,"creature_roar",at,3)
	cue("fight/%s/cry"%army_id,"war_cry",at+Vector3(2,0,2),2)
