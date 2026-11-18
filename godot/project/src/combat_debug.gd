extends Node3D

# Opt-in evidence, not collision physics: mesh AABBs are conservative bounds;
# bone origins are probes, not the soles of skinned meshes.
var rows: Array = []
var lines := MeshInstance3D.new()
var volumes := Node3D.new()
var volume_key := ""
func _ready() -> void:
	add_child(lines)
	add_child(volumes)
	lines.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.vertex_color_use_as_albedo = true
	material.no_depth_test = true
	lines.material_override = material

func bounds(node: Node3D) -> AABB:
	var box := AABB()
	var first := true
	for mesh: MeshInstance3D in node.find_children("*","MeshInstance3D",true,false):
		if mesh.name == &"Arrow" or mesh.mesh == null: continue
		var b: AABB = mesh.global_transform * mesh.get_aabb()
		box = b if first else box.merge(b); first = false
	return box

func sample(stage: Node3D) -> Array:
	rows.clear()
	var mesh := ImmediateMesh.new()
	mesh.surface_begin(Mesh.PRIMITIVE_LINES)
	var keys: Array = []
	var solvers: Array = []
	for cache in stage.army_routes.values():
		var solver=cache.get("engage",{}).get("slot_solver")
		if solver==null:continue
		keys.append(str(solver.space));solvers.append(solver)
		for slot in solver.diagnostics:
			var tint:=Color.ORANGE if slot.reserve else Color.LIME_GREEN
			var supports: Array=slot.get("points",[])
			for pair in [[0,1],[1,3],[3,2],[2,0]]:
				if supports.size()==4:line(mesh,supports[pair[0]]+Vector3.UP*.06,supports[pair[1]]+Vector3.UP*.06,tint)
			for p: Vector3 in supports:line(mesh,p,p+slot.get("normal",Vector3.UP)*.7,Color.CYAN)
			for i in range(1,slot.path.size()):
				line(mesh,slot.path[i-1]+Vector3.UP*.12,slot.path[i]+Vector3.UP*.12,Color.RED if i==1 and not slot.get("march_prefix_verified",false) else tint)
			rows.append({"member":slot.id,"kind":"planned_footprint","valid":slot.valid,"reserve":slot.reserve,"support_points":supports,"normal":slot.get("normal"),"march_prefix_verified":slot.get("march_prefix_verified",false),"approach":slot.path})
	var key:=str(keys)
	if key!=volume_key:
		volume_key=key
		for child in volumes.get_children():child.free()
		for solver in solvers:
			for obstacle in solver.debug_obstacles:
				if obstacle.transform.origin.distance_to(solver.centre)>22 or volumes.get_child_count()>=96:continue
				var shape:=MeshInstance3D.new();shape.mesh=obstacle.shape.get_debug_mesh();shape.transform=obstacle.transform
				var mat:=StandardMaterial3D.new();mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;mat.albedo_color=Color.MEDIUM_PURPLE if obstacle.proxy else Color.SALMON;mat.no_depth_test=true
				shape.material_override=mat;shape.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF;volumes.add_child(shape)
	var obstacles: Array = []
	for child in stage.buildings.get_children():
		if child is Node3D:
			var box := bounds(child)
			if box.size.length_squared()>0.01: obstacles.append({"id":str(child.name),"bounds":box})
	var occupied: Array = []
	for army in stage.actors.get_children():
		for unit in army.get_children():
			if not unit is Node3D or unit.name == &"Ferry": continue
			var box := bounds(unit)
			var points: Array = []
			var normals: Array = []
			var low := INF; var high := -INF
			for x in [box.position.x,box.end.x]:
				for z in [box.position.z,box.end.z]:
					var p: Vector3 = stage.ground_point(Vector3(x,0,z))
					var dx: Vector3 = stage.ground_point(p+Vector3(0.1,0,0))-stage.ground_point(p-Vector3(0.1,0,0))
					var dz: Vector3 = stage.ground_point(p+Vector3(0,0,0.1))-stage.ground_point(p-Vector3(0,0,0.1))
					var normal := dz.cross(dx).normalized()
					low=minf(low,p.y);high=maxf(high,p.y);points.append(p);normals.append(normal)
					line(mesh,p,p+normal,Color.CYAN)
			for pair in [[0,1],[1,3],[3,2],[2,0]]: line(mesh,points[pair[0]]+Vector3.UP*0.05,points[pair[1]]+Vector3.UP*0.05,Color.YELLOW)
			var probes: Array = []
			for skeleton: Skeleton3D in unit.find_children("*","Skeleton3D",true,false):
				for bone in skeleton.get_bone_count():
					var name := skeleton.get_bone_name(bone).to_lower()
					if not ("foot" in name or "hoof" in name): continue
					var p: Vector3 = (skeleton.global_transform*skeleton.get_bone_global_pose(bone)).origin
					var ground: Vector3 = stage.ground_point(p)
					line(mesh,p,ground,Color.RED if p.y<ground.y else Color.GREEN)
					probes.append({"bone":name,"position":[p.x,p.y,p.z],"ground_y":ground.y,"signed_height":p.y-ground.y})
			var overlaps: Array = []
			for obstacle in obstacles:
				if box.intersects(obstacle.bounds): overlaps.append(obstacle.id)
			var neighbors: Array = []
			for other in occupied:
				if box.intersects(other.bounds): neighbors.append(other.id)
			occupied.append({"id":str(unit.name),"bounds":box})
			rows.append({"member":str(unit.name),"instance_id":unit.get_instance_id(),"bounds":box,"support_height_range":high-low,"normals":normals,"bone_probes":probes,"conservative_obstacle_overlap":overlaps,"conservative_neighbor_overlap":neighbors})
	mesh.surface_end()
	lines.mesh=mesh
	return rows

func line(mesh: ImmediateMesh, a: Vector3, b: Vector3, tint: Color) -> void:
	mesh.surface_set_color(tint);mesh.surface_add_vertex(a);mesh.surface_add_vertex(b)
