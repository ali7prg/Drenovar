extends RefCounted

# Contact marker phases in the shipped cycles. Dust is emitted once on landing
# and on a verified stop, never continuously while the hoof is airborne.
const HORSE := {"walk":[0.0,0.5,0.75,0.25],"trot":[0.0,0.5,0.5,0.0],"run":[0.0,0.12,0.38,0.5]}
const HOOVES := ["HindLHoof","HindRHoof","FrontLHoof","FrontRHoof"]
var puffs: Array = []

func sample(stage: Node3D, actor: Node3D, clip: String, mounted: bool, now: float) -> void:
	var moving:=clip in ["walk","run","trot"]
	var previous: Dictionary=actor.get_meta("foot_marker",{})
	var players: Array=actor.get_meta("animation_players",[])
	if players.is_empty():return
	var player: AnimationPlayer=players[0]
	var duration:=player.current_animation_length
	var phase:=fposmod(player.current_animation_position/maxf(.001,duration),1.0)
	if moving and not previous.is_empty() and previous.clip==clip and now-previous.at<350.0:
		var offsets: Array=HORSE.get(clip,[0.0,0.5]) if mounted else [0.0,0.5]
		for k in offsets.size():
			var crossed: bool=(previous.phase<float(offsets[k]) and phase>=float(offsets[k])) if phase>=previous.phase else (previous.phase<float(offsets[k]) or phase>=float(offsets[k]))
			if not crossed:continue
			var bone_name: String=HOOVES[k] if mounted else "foot.L" if k==0 else "foot.R"
			var position:=actor.global_position
			for skeleton: Skeleton3D in actor.find_children("*","Skeleton3D",true,false):
				var bone:=skeleton.find_bone(bone_name)
				if bone>=0:position=(skeleton.global_transform*skeleton.get_bone_global_pose(bone)).origin;break
			var support: Vector3=stage.ground_point(position)
			# Reject airborne/terrain-mismatched contacts, including steep march
			# prefixes awaiting global route work. Do not hide them with dust.
			if absf(position.y-support.y)>.22 or not stage.dry_ground(position):continue
			var id:="step/%d/%d/%d"%[actor.get_instance_id(),roundi(now),k]
			emit(stage,id,support,now,mounted,false)
	elif not moving and not previous.is_empty() and previous.clip in ["walk","run","trot"] and clip!="death":
		var position:=actor.global_position
		if stage.dry_ground(position):emit(stage,"stop/%d/%d"%[actor.get_instance_id(),roundi(now)],stage.ground_point(position),now,mounted,true)
	actor.set_meta("foot_marker",{"clip":clip,"phase":phase,"at":now})

func emit(stage: Node3D, id: String, position: Vector3, now: float, mounted: bool, stop: bool) -> void:
	if puffs.size()<12:puffs.append({"position":position,"at":now,"duration":460.0 if mounted else 340.0,"size":.8 if mounted else .45,"seed":float(posmod(id.hash(),1000))*.001})
	stage.combat_audio.cue(id,"hoof" if mounted else "foot",position,1 if mounted or stop else 0)

func draw(stage: Node3D, now: float) -> void:
	puffs=puffs.filter(func(p):return now-p.at<p.duration and now>=p.at)
	for puff in puffs:stage.battle_fx.dust(puff.position,(now-puff.at)/puff.duration,puff.size,puff.seed)
