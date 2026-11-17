# Combat v0.1.0 troop library rebuild for the rig the game actually uses.
#
# The delivered package generator (package tools/build_troop_animations.gd) was
# authored against assets/army/assets/*27-lod1.glb (19-bone rig). Since 0.6.0 the
# game instantiates assets/army/troops06/ENG-XX-lod{1,2}.gltf (67-bone MakeHuman rig,
# 91 bones for riders with horse). Its libraries do not bind to those models
# (see reports/binding_audit_package.json). This is the same composition algorithm
# with a bone-role map; nothing in the models or textures is changed.
#
# godot --headless --path godot/project --script res://combat_v010/tools/build_troop_animations_troops06.gd
extends SceneTree

const SRC := "res://assets/army/troops06/"
const OUT := "res://combat_v010/animations/troops/"
# Same timings as the package (reports/troop_animation_metadata.json); event = server event.at.
const SPECS = {
 "ENG-01": {"source":"Attack", "length":1.7, "contact":0.64, "family":"spear"},
 "ENG-02": {"source":"Sword_Drill", "length":1.7, "contact":0.64, "family":"sword"},
 "ENG-03": {"source":"Bow_Draw", "length":2.0, "contact":0.86, "family":"bow"},
 "ENG-04": {"source":"Crossbow_Reload", "length":3.2, "contact":0.72, "family":"crossbow"},
 "ENG-05": {"source":"Attack", "length":1.7, "contact":0.68, "family":"mounted"},
 "ENG-06": {"source":"Attack", "length":1.7, "contact":0.68, "family":"mounted"},
 "ENG-07": {"source":"Sword_Drill", "length":1.7, "contact":0.68, "family":"sword"},
 "ENG-08": {"source":"Sword_Drill", "length":1.7, "contact":0.64, "family":"sword"},
 "ENG-09": {"source":"Sword_Drill", "length":1.7, "contact":0.72, "family":"heavy"},
 "ENG-10": {"source":"Javelin_Drill", "length":2.0, "contact":0.66, "family":"javelin"}
}
# Package rig role -> troops06 bone. Twist bones (upperleg02/lowerleg02) are rigid
# children of the solved bones and keep their guard rotation.
const ROLE := {"Hips":"root", "Spine":"spine03", "Chest":"spine01",
	"RightThigh":"upperleg01.R", "RightShin":"lowerleg01.R", "RightFoot":"foot.R",
	"LeftThigh":"upperleg01.L", "LeftShin":"lowerleg01.L", "LeftFoot":"foot.L"}
const LEG_PARTS := ["pelvis.", "upperleg", "lowerleg", "foot.", "toe"]
const SCALE_EPS := 0.0005

var report := {"package":"DRENOVAR-combat-v0.1.0", "rebuild":"troops06 rig port", "engine":Engine.get_version_info().string,
	"generator":"res://combat_v010/tools/build_troop_animations_troops06.gd", "models":[],
	"limitations":["Event time is authored pose timing; target surface contact requires per-instance staging.",
		"Bowstring, bolt and thrown weapon geometry lack independent animation controls.",
		"Package spear-aim correction measured on the 27-series rig is not ported; troops06 spear uses its own Attack direction.",
		"No physical iPhone or browser performance measurements.",
		"Inherited Hit/Death and locomotion retain original quality limitations."]}

func _initialize():
	call_deferred("build")

func build():
	DirAccess.make_dir_recursive_absolute(OUT)
	for id in SPECS:
		var spec: Dictionary = SPECS[id]
		var file: String = SRC + id + "-lod1.gltf"
		var model: Node3D = load(file).instantiate()
		root.add_child(model)
		await process_frame
		var player: AnimationPlayer = model.find_children("*","AnimationPlayer",true,false)[0]
		var skel: Skeleton3D = model.find_children("*","Skeleton3D",true,false)[0]
		var source: Animation = strip_scale(player.get_animation(spec.source))
		var idle_source: Animation = strip_scale(player.get_animation("Idle"))
		var library := AnimationLibrary.new()
		# Inherited clips (original quality, not new motion). Riders also have the
		# 0.6.0 Trot that the gait table selects between walk and run.
		for pair in [["Walk","walk"],["Run","run"],["Trot","trot"],["Hit","hit"],["Death","death"]]:
			if not player.has_animation(pair[0]):
				continue
			var copied: Animation = strip_scale(player.get_animation(pair[0]))
			copied.loop_mode = Animation.LOOP_LINEAR if pair[1] in ["walk","run","trot"] else Animation.LOOP_NONE
			library.add_animation(pair[1], copied)
		var idle: Animation = make_idle(source, idle_source, spec)
		library.add_animation("idle", idle)
		var max_foot_error := 0.0
		for variant in 2:
			var result: Dictionary = make_attack(source, idle, spec, skel, variant)
			library.add_animation("attack_a" if variant == 0 else "attack_b", result.animation)
			max_foot_error = maxf(max_foot_error, result.max_foot_error)
		var path: String = OUT + id + ".res"
		assert(ResourceSaver.save(library, path) == OK)
		var lod_report := []
		for lod in ["lod1", "lod2"]:
			var f: String = SRC + id + "-" + lod + ".gltf"
			var test: Node3D = load(f).instantiate()
			var missing := []
			for clip in library.get_animation_list():
				var a: Animation = library.get_animation(clip)
				for track in a.get_track_count():
					var p := a.track_get_path(track)
					var n := test.get_node_or_null(NodePath(p.get_concatenated_names()))
					if n == null or (p.get_subname_count() > 0 and (n as Skeleton3D).find_bone(str(p.get_subname(0))) < 0):
						missing.append(str(p))
			lod_report.append({"file": f, "sha256": FileAccess.get_sha256(f), "bin_sha256": FileAccess.get_sha256(f.replace(".gltf", ".bin")), "missing_bindings": missing})
			assert(missing.is_empty())
			test.free()
		report.models.append({"id":id, "file":file, "library":"animations/troops/"+id+".res",
			"source_sha256":FileAccess.get_sha256(file), "source_attack":spec.source, "family":spec.family,
			"length_s":spec.length, "contact_or_release_s":spec.contact,
			"event":"release" if spec.family in ["bow","crossbow","javelin"] else "contact",
			"clips":Array(library.get_animation_list()), "skeleton_path":str(model.get_path_to(skel)),
			"bone_count":skel.get_bone_count(), "lod_validation":lod_report,
			"baked_attack_max_foot_error_m":max_foot_error,
			"validation":"Godot load, exact node/bone path checks LOD1+2, foot lock for infantry attacks; aesthetic review pending"})
		model.queue_free()
		print("EXPORTED ", id, " ", path, " foot_err=", max_foot_error)
	var f := FileAccess.open(OUT + "manifest.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(report, "  "))
	f.close()
	quit()

# The troops06 clips carry identity scale tracks on every bone. They are dropped
# (acceptance: no bone scales); a non-identity key aborts the build.
func strip_scale(original: Animation) -> Animation:
	var a: Animation = original.duplicate(true)
	for i in range(a.get_track_count() - 1, -1, -1):
		if a.track_get_type(i) != Animation.TYPE_SCALE_3D:
			continue
		for k in a.track_get_key_count(i):
			var s: Vector3 = a.track_get_key_value(i, k)
			assert(s.distance_to(Vector3.ONE) < SCALE_EPS, "non-identity bone scale in %s" % a.track_get_path(i))
		a.remove_track(i)
	return a

func bone_of(path: NodePath) -> String:
	return str(path.get_subname(0))

func is_role(bone: String, role: String) -> bool:
	return ROLE.get(role, "") == bone

func is_leg(bone: String) -> bool:
	for part in LEG_PARTS:
		if bone.begins_with(part):
			return true
	return false

func get_value(a:Animation, track:int, t:float):
	match a.track_get_type(track):
		Animation.TYPE_POSITION_3D: return a.position_track_interpolate(track,t)
		Animation.TYPE_ROTATION_3D: return a.rotation_track_interpolate(track,t)
	return null

func mixed(a, b, w:float):
	if a is Quaternion: return a.slerp(b,w).normalized()
	return a.lerp(b,w)

func insert(a:Animation, track:int, t:float, v):
	if v != null: a.track_insert_key(track,t,v)

func empty_like(source:Animation, duration:float):
	var a := Animation.new()
	a.length = duration
	for i in source.get_track_count():
		a.add_track(source.track_get_type(i))
		a.track_set_path(i, source.track_get_path(i))
		a.track_set_interpolation_type(i, Animation.INTERPOLATION_LINEAR)
	return a

func make_idle(source:Animation, idle_source:Animation, spec:Dictionary):
	var a = empty_like(source, 3.6)
	a.loop_mode = Animation.LOOP_LINEAR
	for i in a.get_track_count():
		var si = idle_source.find_track(source.track_get_path(i), source.track_get_type(i))
		var ready = get_value(source, i, source.length * (0.18 if spec.family not in ["spear","mounted"] else 0.0))
		for frame in 109:
			var t = float(frame) / 30.0
			var v = ready
			if si >= 0:
				var iv = get_value(idle_source, si, fposmod(t / 3.6 * idle_source.length, idle_source.length))
				var strength = 0.42 if spec.family in ["sword","heavy","javelin"] else 0.72
				if spec.family == "mounted": strength = 0.0
				v = mixed(iv, ready, strength)
			insert(a, i, t, v)
	return a

func curve(t:float, keys:Array):
	for i in range(1, keys.size()):
		if t <= keys[i][0]:
			var x = clampf((t - keys[i-1][0]) / (keys[i][0] - keys[i-1][0]), 0.0, 1.0)
			return lerpf(keys[i-1][1], keys[i][1], x*x*(3.0-2.0*x))
	return keys[-1][1]

func make_attack(source:Animation, idle:Animation, spec:Dictionary, skel:Skeleton3D, variant:int):
	var a = empty_like(source, spec.length)
	var mounted: bool = spec.family == "mounted"
	var c: float = spec.contact
	var length: float = spec.length
	var pose_keys: Array
	if spec.family == "spear":
		pose_keys = [[0.0,0.0],[c-0.22,0.17],[c,0.4],[c+0.14,0.46],[length-0.28,0.70],[length,0.70]]
	elif mounted:
		pose_keys = [[0.0,0.0],[c-0.24,0.30],[c,0.47 if spec == SPECS["ENG-06"] else 0.43],[c+0.14,0.56],[length-0.2,0.92],[length,1.0]]
	elif spec.family == "crossbow":
		pose_keys = [[0.0,0.25],[c-0.15,0.35],[c,0.46],[c+0.14,0.52],[1.85,0.70],[2.50,0.80],[length,0.25]]
	elif spec.family == "bow":
		pose_keys = [[0.0,0.20],[0.48,0.40],[c-0.08,0.46],[c,0.50],[c+0.12,0.58],[length-0.3,0.70],[length,0.20]]
	else:
		pose_keys = [[0.0,0.18],[c-0.22,0.30],[c,0.43],[c+0.13,0.49],[length-0.30,0.64],[length,0.18]]
	var targets = {}
	for i in idle.get_track_count(): apply_track(skel, idle, i, get_value(idle, i, 0))
	skel.force_update_all_bone_transforms()
	if not mounted:
		for side in ["Right","Left"]: targets[side] = skel.get_bone_global_pose(skel.find_bone(ROLE[side+"Foot"]))
	var max_error := 0.0
	var n = int(ceil(length * 60.0))
	for frame in n + 1:
		var t = length * float(frame) / float(n)
		var source_t = curve(t, pose_keys) * source.length
		var envelope = smoothstep(0.0, 0.18, t) * (1.0 - smoothstep(length-0.30, length, t))
		for i in source.get_track_count():
			var v = mixed(get_value(idle, i, 0), get_value(source, i, source_t), envelope)
			var bone = bone_of(source.track_get_path(i))
			var type = source.track_get_type(i)
			if not mounted:
				if is_leg(bone):
					v = get_value(idle, i, 0)
				if type == Animation.TYPE_ROTATION_3D and (is_role(bone,"Chest") or is_role(bone,"Spine")) and spec.family not in ["bow","crossbow"]:
					var load_amount = curve(t, [[0.0,0.0],[c-0.22,-1.0],[c,1.0],[c+0.13,0.8],[length,0.0]])
					var angle = (0.10 if is_role(bone,"Chest") else 0.04) * load_amount
					if spec.family == "spear": angle *= 0.5
					v = (v * Quaternion(Vector3.UP, angle)).normalized()
				if type == Animation.TYPE_POSITION_3D and is_role(bone,"Hips"):
					var base: Vector3 = get_value(idle, i, 0)
					var shift = curve(t, [[0.0,0.0],[c-0.22,-0.5],[c,1.0],[c+0.16,0.7],[length,0.0]])
					v = base + Vector3(-0.014*shift, -0.009*absf(shift), 0.024*shift)
			if type == Animation.TYPE_ROTATION_3D and is_role(bone,"Chest"):
				if variant == 1 and t > c + 0.06:
					v = (v * Quaternion(Vector3.FORWARD, 0.025 * sin(PI * clampf((t-c-0.06)/(length-c-0.06), 0.0, 1.0)))).normalized()
				if spec.family == "crossbow" and t >= c and t <= c + 0.16:
					v = (v * Quaternion(Vector3.RIGHT, -0.02 * sin(PI * (t-c) / 0.16))).normalized()
			apply_track(skel, source, i, v)
		if not mounted:
			for side in targets:
				solve_leg(skel, side, targets[side].origin)
				var foot_id = skel.find_bone(ROLE[side+"Foot"])
				var parent_id = skel.get_bone_parent(foot_id)
				skel.force_update_all_bone_transforms()
				skel.set_bone_pose_rotation(foot_id, (skel.get_bone_global_pose(parent_id).basis.inverse() * targets[side].basis).get_rotation_quaternion())
				skel.force_update_all_bone_transforms()
				max_error = maxf(max_error, skel.get_bone_global_pose(foot_id).origin.distance_to(targets[side].origin))
		for i in source.get_track_count():
			var bone = skel.find_bone(bone_of(source.track_get_path(i)))
			match source.track_get_type(i):
				Animation.TYPE_POSITION_3D: insert(a, i, t, skel.get_bone_pose_position(bone))
				Animation.TYPE_ROTATION_3D: insert(a, i, t, skel.get_bone_pose_rotation(bone).normalized())
	return {"animation":a, "max_foot_error":max_error}

func apply_track(skel:Skeleton3D, a:Animation, i:int, v):
	var bone = skel.find_bone(bone_of(a.track_get_path(i)))
	assert(bone >= 0)
	match a.track_get_type(i):
		Animation.TYPE_POSITION_3D: skel.set_bone_pose_position(bone, v)
		Animation.TYPE_ROTATION_3D: skel.set_bone_pose_rotation(bone, v)

func solve_leg(s:Skeleton3D, side:String, target:Vector3):
	var hip = s.find_bone(ROLE[side+"Thigh"])
	var knee = s.find_bone(ROLE[side+"Shin"])
	var foot = s.find_bone(ROLE[side+"Foot"])
	s.force_update_all_bone_transforms()
	var h = s.get_bone_global_pose(hip).origin
	var k = s.get_bone_global_pose(knee).origin
	var f = s.get_bone_global_pose(foot).origin
	var l1 = h.distance_to(k)
	var l2 = k.distance_to(f)
	var direction = (target - h).normalized()
	var distance = clampf(h.distance_to(target), absf(l1-l2)+0.00001, l1+l2-0.00001)
	var projection = (l1*l1 - l2*l2 + distance*distance) / (2.0*distance)
	var height = sqrt(maxf(0.0, l1*l1 - projection*projection))
	var bend = Vector3.FORWARD - direction * Vector3.FORWARD.dot(direction)
	if (k-h-direction*(k-h).dot(direction)).length() > 0.001:
		bend = k-h-direction*(k-h).dot(direction)
	bend = bend.normalized()
	var desired_knee = h + direction*projection + bend*height
	align_bone(s, hip, k-h, desired_knee-h)
	s.force_update_all_bone_transforms()
	k = s.get_bone_global_pose(knee).origin
	f = s.get_bone_global_pose(foot).origin
	align_bone(s, knee, f-k, target-k)

func align_bone(s:Skeleton3D, bone:int, from:Vector3, to:Vector3):
	var parent = s.get_bone_parent(bone)
	var parent_basis = Basis.IDENTITY if parent < 0 else s.get_bone_global_pose(parent).basis.orthonormalized()
	var delta = Quaternion((parent_basis.inverse()*from).normalized(), (parent_basis.inverse()*to).normalized())
	s.set_bone_pose_rotation(bone, (delta * s.get_bone_pose_rotation(bone)).normalized())
