extends SceneTree
## Run-cycle check (QA, not shipped): a story clip on a real game body, frame by frame. Prints the joint
## angles a running gait is judged by (knee, hip, ankle height, elbow, shoulder swing, hand path, pelvis
## height, trunk lean) and saves a side and a 3/4 shot of every sampled frame:
##   xvfb-run -s "-screen 0 900x900x24" godot --path . --rendering-driver vulkan --rendering-method mobile \
##     -s qa_story_run.gd -- --clip=lf_story_run --body=quarry_worker --out=/abs/dir [--every=1]

const Rig = preload("res://src/forest_rescue/game/actor_rig.gd")
const StoryCast = preload("res://src/story/story_cast.gd")
const HUMANS := "res://assets/forest_rescue/humans/"

var clip := "lf_story_run"
var body := "quarry_worker"
var out_dir := ""
var every := 1
var camera: Camera3D

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--clip="):
			clip = arg.trim_prefix("--clip=")
		elif arg.begins_with("--body="):
			body = arg.trim_prefix("--body=")
		elif arg.begins_with("--out="):
			out_dir = arg.trim_prefix("--out=")
		elif arg.begins_with("--every="):
			every = int(arg.trim_prefix("--every="))
	call_deferred("run")

func run() -> void:
	root.size = Vector2i(900, 900)
	var world := Node3D.new()
	root.add_child(world)
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color("#d8d2c4")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color("#cfc6b4")
	environment.ambient_light_energy = 0.8
	var we := WorldEnvironment.new()
	we.environment = environment
	world.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, 30, 0)
	sun.light_energy = 1.3
	sun.shadow_enabled = true
	world.add_child(sun)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(20, 20)
	ground.mesh = plane
	var ground_material := StandardMaterial3D.new()
	ground_material.albedo_color = Color("#b9ad94")
	ground.material_override = ground_material
	world.add_child(ground)
	# a 0.25 m grid on the ground (stride, foot placement)
	for i in range(-16, 17):
		for dir in [0, 1]:
			var line := MeshInstance3D.new()
			var box := BoxMesh.new()
			box.size = Vector3(0.006, 0.002, 8.0) if dir == 0 else Vector3(8.0, 0.002, 0.006)
			line.mesh = box
			line.position = Vector3(i * 0.25, 0.001, 0) if dir == 0 else Vector3(0, 0.001, i * 0.25)
			var m := StandardMaterial3D.new()
			m.albedo_color = Color(0.3, 0.27, 0.22, 1) if i % 4 == 0 else Color(0.55, 0.5, 0.42, 1)
			line.material_override = m
			world.add_child(line)
	var rig := Rig.new()
	rig.setup("qa_" + body, HUMANS + "lf_civilian_%s.glb" % body)
	world.add_child(rig)
	rig.poll_load(true)
	StoryCast.add_story_clips(rig)
	var name := rig.resolve([clip])
	if name.is_empty():
		print("RUN_QA no clip ", clip)
		quit(1)
		return
	var anim: Animation = rig.player.get_animation(name)
	var length := anim.length
	rig.player.play(name, 0.0)
	rig.player.pause()
	var skeleton: Skeleton3D = rig.model.find_children("*", "Skeleton3D", true, false)[0]
	camera = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 2.3
	world.add_child(camera)
	camera.current = true
	var frames := int(round(length * 30.0))
	print("RUN_QA clip=%s body=%s length=%.3f frames=%d" % [clip, body, length, frames])
	print("RUN_QA f   t    kneeL kneeR | thighL thighR | ankL_y ankR_y | elbL elbR | shL   shR  | handL_fwd handR_fwd handL_y handR_y handL_x handR_x | hips_y lean")
	for f in range(0, frames + 1, every):
		var t := minf(f / 30.0, length)
		rig.player.seek(t, true)
		await process_frame
		var g := func(bone: String) -> Vector3:
			return skeleton.global_transform * skeleton.get_bone_global_pose(skeleton.find_bone(bone)).origin
		var basis := skeleton.global_transform.basis
		var fwd := basis.z.normalized()
		var up := Vector3.UP
		var hips: Vector3 = g.call("Hips")
		var neck: Vector3 = g.call("Neck")
		var trunk := (neck - hips).normalized()
		var lean := rad_to_deg(atan2(trunk.dot(fwd), trunk.dot(up)))
		var row := {}
		for S in ["Left", "Right"]:
			var hip: Vector3 = g.call(S + "UpperLeg")
			var knee: Vector3 = g.call(S + "LowerLeg")
			var ankle: Vector3 = g.call(S + "Foot")
			var sh: Vector3 = g.call(S + "UpperArm")
			var el: Vector3 = g.call(S + "LowerArm")
			var wr: Vector3 = g.call(S + "Hand")
			row[S + "knee"] = 180.0 - rad_to_deg((hip - knee).angle_to(ankle - knee))
			var thigh := knee - hip
			row[S + "hip"] = rad_to_deg(atan2(thigh.dot(fwd), -thigh.dot(up)))          # thigh vs vertical (lab)
			row[S + "ank"] = ankle.y
			row[S + "elb"] = 180.0 - rad_to_deg((sh - el).angle_to(wr - el))
			var arm := el - sh
			row[S + "sh"] = rad_to_deg(atan2(arm.dot(fwd), -arm.dot(up))) + lean       # upper arm vs trunk
			row[S + "hf"] = (wr - hips).dot(fwd)
			row[S + "hy"] = wr.y
			row[S + "hx"] = (wr - hips).dot(basis.x.normalized())
		print("RUN_QA %2d %.3f %5.1f %5.1f | %5.1f %5.1f | %.3f %.3f | %5.1f %5.1f | %5.1f %5.1f | %6.3f %6.3f %.3f %.3f %6.3f %6.3f | %.3f %4.1f" % [
			f, t, row.Leftknee, row.Rightknee, row.Lefthip, row.Righthip, row.Leftank, row.Rightank,
			row.Leftelb, row.Rightelb, row.Leftsh, row.Rightsh, row.Lefthf, row.Righthf, row.Lefthy, row.Righthy,
			row.Lefthx, row.Righthx, hips.y, lean])
		if not out_dir.is_empty():
			DirAccess.make_dir_recursive_absolute(out_dir)
			for view in ["side", "q34"]:
				var target := Vector3(hips.x, 0.95, hips.z)
				var dir := basis.x.normalized() if view == "side" else (basis.x.normalized() + fwd * 1.2).normalized()
				camera.position = target + dir * 6.0 + Vector3(0, 0.35 if view == "q34" else 0.0, 0)
				camera.look_at(target, Vector3.UP)
				await RenderingServer.frame_post_draw
				await process_frame
				await RenderingServer.frame_post_draw
				root.get_texture().get_image().save_jpg(out_dir.path_join("%s_%s_%02d.jpg" % [clip, view, f]), 0.9)
	quit()
