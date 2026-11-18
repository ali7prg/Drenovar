extends SceneTree

# Actual FK hoof displacement in world space, not a speed-table identity test.
# Explicit authored stance windows exclude only the interpolation boundary.
const GAITS := {"Walk":{"speed":1.55,"stance":0.60,"offsets":[0.0,0.5,0.75,0.25]},"Trot":{"speed":3.4,"stance":0.32,"offsets":[0.0,0.5,0.5,0.0]},"Run":{"speed":6.25,"stance":0.20,"offsets":[0.0,0.12,0.38,0.50]}}
const HOOVES := ["HindLHoof","HindRHoof","FrontLHoof","FrontRHoof"]
var failures := 0
var rows: Array = []

func soles(actor: Node3D, skeleton: Skeleton3D) -> Dictionary:
	var result: Dictionary={}
	for mesh: MeshInstance3D in actor.find_children("*","MeshInstance3D",true,false):
		if mesh.skin==null or mesh.mesh==null:continue
		for surface in mesh.mesh.get_surface_count():
			var arrays:=mesh.mesh.surface_get_arrays(surface)
			if arrays[Mesh.ARRAY_BONES]==null or arrays[Mesh.ARRAY_WEIGHTS]==null:continue
			var positions: PackedVector3Array=arrays[Mesh.ARRAY_VERTEX]
			var binds: PackedInt32Array=arrays[Mesh.ARRAY_BONES]
			var weights: PackedFloat32Array=arrays[Mesh.ARRAY_WEIGHTS]
			var per_vertex:=binds.size()/positions.size()
			for index in positions.size():
				for influence in per_vertex:
					var offset:=index*per_vertex+influence
					if weights[offset]<.95:continue
					var bind:=binds[offset]
					var name:=str(mesh.skin.get_bind_name(bind))
					var k:=HOOVES.find(name)
					if k<0:continue
					var point:={"vertex":positions[index],"skin":mesh.skin,"binds":[],"weights":[]}
					for j in per_vertex:
						point.binds.append(binds[index*per_vertex+j]);point.weights.append(weights[index*per_vertex+j])
					var p:=skin_point(point,skeleton)
					if not result.has(k) or p.y<result[k].rest_y:
						point.rest_y=p.y;result[k]=point
	return result

func skin_point(point: Dictionary, skeleton: Skeleton3D) -> Vector3:
	var p:=Vector3.ZERO
	for i in point.binds.size():
		var weight: float=point.weights[i]
		if weight<=0:continue
		var bind: int=point.binds[i]
		var bone:=skeleton.find_bone(point.skin.get_bind_name(bind))
		p+=(skeleton.get_bone_global_pose(bone)*point.skin.get_bind_pose(bind)*point.vertex)*weight
	return skeleton.global_transform*p

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var baseline := "--baseline" in OS.get_cmdline_user_args()
	var Landscape = load("res://src/landscape.gd")
	# Build 1021: riders are drawn at the city's field scale and at half size on the
	# world map (with its quicker run); both must keep their hooves planted.
	for scale in [Landscape.FIELD_UNIT_SCALE, Landscape.WORLD_UNIT_SCALE]:
		var run_max: float = Landscape.RUN_TEMPO.y if scale >= Landscape.FIELD_UNIT_SCALE else Landscape.WORLD_RUN_TEMPO
		for id in ["ENG-05","ENG-06"]:
			for lod in [1,2]:
				var actor: Node3D=load("res://assets/army/troops06/%s-lod%d.gltf"%[id,lod]).instantiate()
				root.add_child(actor);actor.scale=Vector3.ONE*scale
				var player: AnimationPlayer=actor.find_children("*","AnimationPlayer",true,false)[0]
				var skeleton: Skeleton3D=actor.find_children("*","Skeleton3D",true,false)[0]
				var sole_points:=soles(actor,skeleton)
				if sole_points.size()!=4:push_error("Four weighted hoof sole vertices required");failures+=1
				for clip in GAITS:
					if not player.has_animation(clip): continue
					var cfg: Dictionary=GAITS[clip]
					var length: float=player.get_animation(clip).length
					var speed: float = (8.0 if id=="ENG-05" else 7.0) if clip=="Run" else float(cfg.speed)*float(scale)
					var tempo: float = minf(1.6,speed/(1.4645*scale)) if baseline and clip=="Run" else Landscape.gait_for(id,speed,scale,run_max)[1]
					var dt := length/600.0/tempo
					var slips: Array[float]=[];var height_range:=0.0
					var previous := {};var heights := {};var anchors := {};var travel := 0.0
					for frame in range(601):
						var phase := frame/600.0
						player.play(clip);player.seek(minf(length-0.00001,phase*length),true)
						actor.position.z=speed*frame*dt
						for k in 4:
							var bone := skeleton.find_bone(HOOVES[k])
							var p: Vector3=skin_point(sole_points[k],skeleton) if sole_points.has(k) else (skeleton.global_transform*skeleton.get_bone_global_pose(bone)).origin
							var stance := fposmod(phase-float(cfg.offsets[k]),1.0)
							if stance>0.02 and stance<float(cfg.stance)-0.02 and previous.has(k):
								if not anchors.has(k):anchors[k]=p
								travel=maxf(travel,p.distance_to(anchors[k]))
								slips.append(p.distance_to(previous[k])/dt)
								if not heights.has(k): heights[k]=[p.y,p.y]
								heights[k]=[minf(heights[k][0],p.y),maxf(heights[k][1],p.y)]
							else:anchors.erase(k)
							previous[k]=p
					for h in heights.values():height_range=maxf(height_range,h[1]-h[0])
					slips.sort()
					var p95: float=slips[ceili((slips.size()-1)*0.95)]
					var row := {"unit":id,"lod":lod,"scale":scale,"clip":clip,"ground_speed":speed,"tempo":tempo,"samples":slips.size(),"hoof_world_speed_p95":p95,"stance_displacement_max_m":travel,"height_range_m":height_range,"sole_vertices":sole_points.size(),"method":"600 samples/cycle, actual skinned hoof sole vertices, runtime gait_for tempo and world root translation"}
					rows.append(row);print("HOOF ",JSON.stringify(row))
					# Audit criterion: stance drift <5% of the ~1.5m leg. Keep p95
					# instantaneous velocity in the evidence (interpolation is not exact IK).
					if not baseline and (travel>0.075*scale/1.15 or height_range>0.025*scale/1.15): failures+=1
				actor.free()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--output="): FileAccess.open(arg.trim_prefix("--output="),FileAccess.WRITE).store_string(JSON.stringify(rows,"  "))
	print("QA_HOOF failures=",failures)
	quit(0 if failures==0 else 1)
