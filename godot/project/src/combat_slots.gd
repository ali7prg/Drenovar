extends RefCounted

# Presentation-only local placement. A private physics space uses the actual
# nearby static triangle meshes, independent of camera culling and network paths.
# No navigation or combat-authority values are written here.
var stage: Node3D
var space: RID
var bodies: Array[RID] = []
var shapes: Array[Shape3D] = []
var obstacle_ids := {}
var occupied: Array = []
var diagnostics: Array = []
var centre := Vector3.ZERO
var target_face := Vector3.FORWARD
var target_body := Vector2.ZERO
var mesh_shapes := {}
var tree_proxies := {}
var debug_obstacles: Array = []
# Forest trees within this distance of the creature are cleared while the fight is
# shown (forest.gdshader battle_focus_core): no obstacle for the battle places.
var clear_radius := 0.0
var foot_shape := BoxShape3D.new()
var horse_shape := BoxShape3D.new()
const MARGIN := 0.10
# Size of the soldiers on this map relative to the layout of 1.15 (landscape.unit_k):
# the footprints, search steps and contact gaps below follow it.
var unit_k := 1.0
# Time slicing. 0 = run to completion in the calling frame (tests, lab tools).
# Otherwise the planner yields to the next frame after this many microseconds,
# so a departing march never stalls the game while contact places are prepared.
var slice_usec := 0
var slice_end := 0
# Bounded local A*: one detour search per member, later candidates must be
# reachable directly. Unbounded searches (320 sorted iterations of swept checks,
# up to 16 per archer) held the main thread for 14 s on a desktop CPU.
const ASTAR_ITERATIONS := 140
const ASTAR_MAX_COST := 24.0
const ASTAR_PER_MEMBER := 1
var astar_left := ASTAR_PER_MEMBER

func _init() -> void:
	set_unit_k(1.0)

func set_unit_k(k: float) -> void:
	unit_k=k
	foot_shape.size=Vector3(0.88,2.15,1.0)*k
	horse_shape.size=Vector3(1.3,3.4,3.6)*k

# Called inside the planner's loops: hands the frame back once the slice is used.
func pause() -> void:
	if slice_usec <= 0 or Time.get_ticks_usec() < slice_end:
		return
	await stage.get_tree().process_frame
	if not is_instance_valid(stage):
		release()
		return
	slice_end = Time.get_ticks_usec() + slice_usec

# Frees the private physics space once the plan is final. Diagnostics and the
# obstacle list stay for the debug overlay and QA reports.
func release() -> void:
	for body in bodies: PhysicsServer3D.free_rid(body)
	bodies.clear();shapes.clear();obstacle_ids.clear();mesh_shapes.clear();tree_proxies.clear()
	if space.is_valid(): PhysicsServer3D.free_rid(space)
	space=RID()

func clear() -> void:
	for body in bodies: PhysicsServer3D.free_rid(body)
	bodies.clear();shapes.clear();obstacle_ids.clear();occupied.clear();diagnostics.clear();mesh_shapes.clear();tree_proxies.clear();debug_obstacles.clear()
	if space.is_valid(): PhysicsServer3D.free_rid(space)
	space=RID()

func _notification(what: int) -> void:
	if what==NOTIFICATION_PREDELETE:
		for body in bodies: PhysicsServer3D.free_rid(body)
		if space.is_valid(): PhysicsServer3D.free_rid(space)

func prepare(owner_stage: Node3D, at: Vector3, face: Vector3, body: Vector2) -> void:
	clear();stage=owner_stage;centre=at;target_face=face;target_body=body
	slice_end=Time.get_ticks_usec()+slice_usec
	space=PhysicsServer3D.space_create();PhysicsServer3D.space_set_active(space,true)
	var near := AABB(at-Vector3(40,12,40),Vector3(80,36,80))
	for parent in [stage.buildings,stage.scenery,stage.town,stage.walls.node]:
		if not is_instance_valid(parent) or not parent is Node: continue
		for mesh: MeshInstance3D in parent.find_children("*","MeshInstance3D",true,false):
			await pause()
			if not space.is_valid() or not is_instance_valid(mesh): return
			if mesh.mesh==null or not near.intersects(mesh.global_transform*mesh.get_aabb()):continue
			# TownGround is a walkable 8cm surface overlay, not a wall. Its
			# coarse triangles are also alpha masked; query it as support only.
			add_mesh(mesh.mesh,mesh.global_transform,str(mesh.get_path()),mesh==stage.town.ground)
	# The city wall is drawn as MultiMesh parts (city_walls.gd), which the search above
	# never saw: up to build 1020 a charge or a battle place could cross the palisade.
	# Its footing and its towers stand on the ground; their boxes are obstacles.
	if is_instance_valid(stage.walls.node):
		for part in stage.walls.node.get_children():
			if not part is MultiMeshInstance3D or not String(part.name) in ["footing","tower_footing","tower_base_stone"]:continue
			var multi: MultiMesh=(part as MultiMeshInstance3D).multimesh
			var bounds: AABB=multi.mesh.get_aabb()
			for i in multi.instance_count:
				var placed:Transform3D=part.global_transform*multi.get_instance_transform(i)
				if not near.intersects(placed*bounds):continue
				await pause()
				if not space.is_valid():return
				# Physics boxes take no scale: the instance's scale goes into the box size.
				var box:=BoxShape3D.new();box.size=bounds.size*placed.basis.get_scale();shapes.append(box)
				add_shape(box,Transform3D(placed.basis.orthonormalized(),placed*bounds.get_center()),"wall:%s/%d"%[part.name,i])
	# Original placement buffers include offscreen instances; camera uploads are
	# deliberately not the collision source. Billboard/grass LODs have no volume.
	for batch in stage.render_batches:
		await pause()
		if not space.is_valid(): return
		if not is_instance_valid(batch.node): continue
		var layer: Dictionary=batch.layer
		if layer.get("silhouette",false) or layer.get("detail",false) or layer.get("resource",false): continue
		if int(layer.get("tree_lod",0))>int(layer.get("tree_best",0)): continue
		var mesh: Mesh=batch.node.multimesh.mesh
		if mesh is QuadMesh: continue
		for k in batch.clusters.size():
			if not near.intersects(AABB(batch.low[k],batch.high[k]-batch.low[k])):continue
			var buffer: PackedFloat32Array=batch.clusters[k]
			for offset in range(0,buffer.size(),12):
				var transform := Transform3D(Basis(Vector3(buffer[offset],buffer[offset+4],buffer[offset+8]),Vector3(buffer[offset+1],buffer[offset+5],buffer[offset+9]),Vector3(buffer[offset+2],buffer[offset+6],buffer[offset+10])),Vector3(buffer[offset+3],buffer[offset+7],buffer[offset+11]))
				transform=batch.node.global_transform*transform
				if not near.intersects(transform*mesh.get_aabb()):continue
				var material: Material=batch.node.material_override
				if material is ShaderMaterial and material.shader==stage.FOREST_SHADER:
					# The forest asset is an alpha-cutout card, not a solid wall.
					# Reserve its trunk footprint explicitly; do not report the
					# transparent billboard triangle as physical intersection.
					var key:=Vector2(transform.origin.x,transform.origin.z)
					if tree_proxies.has(key):continue
					if key.distance_to(Vector2(centre.x,centre.z))<clear_radius:continue
					tree_proxies[key]=true
					var shape:=CylinderShape3D.new();shape.radius=.22*transform.basis.x.length();shape.height=2.5
					shapes.append(shape)
					add_shape(shape,Transform3D(Basis.IDENTITY,transform.origin+Vector3.UP*1.25),"tree_footprint_proxy:%s"%key)
				else:add_mesh(mesh,transform,"mesh:%s/%d/%d"%[batch.node.name,k,offset/12])

func add_mesh(mesh: Mesh, transform: Transform3D, id: String, walkable := false) -> void:
	var key := mesh.get_instance_id()
	if not mesh_shapes.has(key):
		var shape := mesh.create_trimesh_shape()
		if shape==null:return
		shape.backface_collision=true;mesh_shapes[key]=shape;shapes.append(shape)
	add_shape(mesh_shapes[key],transform,id,2 if walkable else 1)

func add_shape(shape: Shape3D, transform: Transform3D, id: String, layer := 1) -> void:
	var body := PhysicsServer3D.body_create()
	PhysicsServer3D.body_set_mode(body,PhysicsServer3D.BODY_MODE_STATIC)
	PhysicsServer3D.body_add_shape(body,shape.get_rid())
	PhysicsServer3D.body_set_state(body,PhysicsServer3D.BODY_STATE_TRANSFORM,transform)
	PhysicsServer3D.body_set_space(body,space)
	PhysicsServer3D.body_set_collision_layer(body,layer)
	bodies.append(body);obstacle_ids[body]=id
	debug_obstacles.append({"id":id,"shape":shape,"transform":transform,"proxy":id.begins_with("tree_footprint_proxy:")})

func ground(p: Vector3) -> Vector3:
	p=stage.ground_point(p)
	if stage.map_name!="city" or not is_instance_valid(stage.town.ground):return p
	# Use the existing CPU mask; never read a GPU texture during placement.
	var mask: Image=stage.town_plan.mask
	var half: float=stage.town_plan.HALF
	var x:=floori((p.x+half)/(half*2)*mask.get_width())
	var y:=floori((p.z+half)/(half*2)*mask.get_height())
	if x<0 or y<0 or x>=mask.get_width() or y>=mask.get_height():return p
	var color:=mask.get_pixel(x,y)
	if maxf(color.r,color.g)<.75:return p
	var query:=PhysicsRayQueryParameters3D.create(p+Vector3.UP*.3,p-Vector3.UP*.1,2)
	var hit:=PhysicsServer3D.space_get_direct_state(space).intersect_ray(query)
	if not hit.is_empty():p=hit.position
	return p

func support(p: Vector3, yaw: float, mounted: bool) -> Dictionary:
	var half := (Vector2(0.65,1.8) if mounted else Vector2(0.44,0.5))*unit_k
	var basis := Basis(Vector3.UP,yaw)
	var points: Array[Vector3]=[]
	for x in [-half.x,half.x]:
		for z in [-half.y,half.y]:
			var q := p+basis*Vector3(x,0,z)
			if not stage.dry_ground(q): return {"valid":false,"reason":"water"}
			points.append(ground(q))
	var dx := ((points[2]-points[0])+(points[3]-points[1]))*0.5
	var dz := ((points[1]-points[0])+(points[3]-points[2]))*0.5
	var normal := dz.cross(dx).normalized()
	if normal.y<0:normal=-normal
	# Tilting the root can support a plane, but cannot bridge a terrain break.
	# Restrict whole-body lean to 12° on the horse, 18° on a standing soldier.
	if normal.dot(Vector3.UP)<cos(deg_to_rad(12.0 if mounted else 18.0)):
		return {"valid":false,"reason":"slope","normal":normal,"points":points}
	var average := Vector3.ZERO
	for q in points: average+=q*0.25
	var residual := 0.0
	for q in points:residual=maxf(residual,absf(normal.dot(q-average)))
	if residual>0.08*unit_k:return {"valid":false,"reason":"terrain_break","residual":residual,"points":points}
	var forward := basis.z.slide(normal).normalized()
	basis=Basis(normal.cross(forward).normalized(),normal,forward)
	p=ground(p)
	p.y=average.y+residual
	return {"valid":true,"position":p,"basis":basis,"normal":normal,"points":points,"residual":residual,"half":half}

func test(p: Vector3, yaw: float, mounted: bool, check_occupied := true, check_target := true) -> Dictionary:
	var result := support(p,yaw,mounted)
	if not result.valid:return result
	var shape: BoxShape3D=horse_shape if mounted else foot_shape
	var transform := Transform3D(result.basis,result.position+result.normal*(shape.size.y*0.5+0.10*unit_k))
	var query := PhysicsShapeQueryParameters3D.new();query.shape=shape;query.transform=transform;query.margin=MARGIN*unit_k
	query.collision_mask=1
	var hits := PhysicsServer3D.space_get_direct_state(space).intersect_shape(query,8)
	if not hits.is_empty():
		return {"valid":false,"reason":"mesh_intersection","obstacles":hits.map(func(h):return obstacle_ids.get(h.rid,"unknown"))}
	if check_occupied:
		var polygon := footprint(result.position,result.basis,result.half+Vector2.ONE*MARGIN*unit_k)
		for other in occupied:
			if not Geometry2D.intersect_polygons(polygon,other.polygon).is_empty():return {"valid":false,"reason":"occupied","neighbor":other.id}
	if check_target:
		var local := p-centre
		var across := Vector3(target_face.z,0,-target_face.x)
		# A convex ellipse reservation prevents the final approach cutting through
		# the target even before its asynchronously loaded mesh exists.
		var reach := (1.3 if mounted else .45)*unit_k
		var ratio := pow(local.dot(target_face)/(target_body.x+reach),2)+pow(local.dot(across)/(target_body.y+reach),2)
		if ratio<1.0:return {"valid":false,"reason":"target_body"}
	return result

static func footprint(p: Vector3, basis: Basis, half: Vector2) -> PackedVector2Array:
	var polygon := PackedVector2Array()
	for local in [Vector2(-half.x,-half.y),Vector2(half.x,-half.y),Vector2(half.x,half.y),Vector2(-half.x,half.y)]:
		var q := p+basis*Vector3(local.x,0,local.y);polygon.append(Vector2(q.x,q.z))
	return polygon

func segment_clear(a: Vector3, b: Vector3, mounted: bool) -> bool:
	var distance := Vector2(b.x-a.x,b.z-a.z).length()
	var yaw := atan2(b.x-a.x,b.z-a.z)
	var steps := maxi(1,ceili(distance/(0.65*unit_k)))
	for k in range(1,steps+1):
		if not test(a.lerp(b,float(k)/steps),yaw,mounted,false).valid:return false
	return true

func approach(a: Vector3, b: Vector3, mounted: bool) -> Array[Vector3]:
	if segment_clear(a,b,mounted):return [a,b]
	# This planner owns the final six metres, not the server's terrain-agnostic
	# march. An invalid earlier formation offset is recorded separately, and is
	# not used as a reason to select an unsafe fighting footprint.
	var original := a
	if a.distance_to(b)>6.0*unit_k:
		var entering := b+(a-b).normalized()*6.0*unit_k
		if support(entering,atan2(b.x-a.x,b.z-a.z),mounted).valid:a=entering
	if segment_clear(a,b,mounted):
		var direct: Array[Vector3]=[a,b]
		if original!=a:direct.push_front(original)
		return direct
	if astar_left <= 0:
		return []
	astar_left -= 1
	# Local deterministic A*: bounded search, never modifies the server path.
	var step := (1.3 if mounted else 1.0)*unit_k
	var start := Vector2i.ZERO
	var open := [start];var cost := {start:0.0};var previous := {};var validity := {}
	var in_open := {start:true}
	var points := {start:a};var end := Vector2(b.x,b.z)
	for iteration in ASTAR_ITERATIONS:
		if open.is_empty():break
		await pause()
		if not space.is_valid():return []
		# Linear minimum instead of re-sorting the whole open list each iteration.
		var best := 0
		var best_score := INF
		for k in open.size():
			var x: Vector2i=open[k]
			var score_x:=float(cost[x])+Vector2(points[x].x,points[x].z).distance_to(end)
			if score_x<best_score:best_score=score_x;best=k
		var cell: Vector2i=open[best];open.remove_at(best);in_open.erase(cell);var p: Vector3=points[cell]
		if p.distance_to(b)<step*2.2 and segment_clear(p,b,mounted):
			var path: Array[Vector3]=[p,b]
			while previous.has(cell):cell=previous[cell];path.push_front(points[cell])
			# String pulling reduces artificial grid turns, retaining swept checks.
			var reduced: Array[Vector3]=[path[0]];var cursor:=0
			while cursor<path.size()-1:
				var next:=path.size()-1
				while next>cursor+1 and not segment_clear(path[cursor],path[next],mounted):next-=1
				reduced.append(path[next]);cursor=next
			if original!=a:reduced.push_front(original)
			return reduced
		for d in [Vector2i(1,0),Vector2i(-1,0),Vector2i(0,1),Vector2i(0,-1),Vector2i(1,1),Vector2i(-1,-1),Vector2i(1,-1),Vector2i(-1,1)]:
			var n: Vector2i=cell+d;var q: Vector3=stage.ground_point(a+Vector3(n.x*step,0,n.y*step))
			var added:=p.distance_to(q);var score:=float(cost[cell])+added
			if score>=float(cost.get(n,INF)) or score>ASTAR_MAX_COST*unit_k:continue
			var edge:=str(cell)+":"+str(n)
			if not validity.has(edge):validity[edge]=segment_clear(p,q,mounted)
			if not validity[edge]:continue
			cost[n]=score;previous[n]=cell;points[n]=q
			if not in_open.has(n):open.append(n);in_open[n]=true
	return []

func choose(id: String, wanted: Vector3, from: Vector3, mounted: bool) -> Dictionary:
	astar_left = ASTAR_PER_MEMBER
	var offset:=wanted-centre
	var rejected := {}
	var across:=Vector3(target_face.z,0,-target_face.x)
	var direction:=offset.normalized()
	var radius:=1.0/sqrt(pow(direction.dot(target_face)/target_body.x,2)+pow(direction.dot(across)/target_body.y,2))
	var gap:=offset.length()-radius
	# Search the same contact arc before allowing a reserve row farther back.
	for reserve in range(3):
		for step in range(61):
			var turn:=ceili(step/2.0)*(1 if step%2 else -1)
			var ray:=direction.rotated(Vector3.UP,turn*deg_to_rad(6))
			var edge:=1.0/sqrt(pow(ray.dot(target_face)/target_body.x,2)+pow(ray.dot(across)/target_body.y,2))
			var q:=centre+ray*(edge+gap+reserve*1.7*unit_k)
			var yaw:=atan2(centre.x-q.x,centre.z-q.z)
			await pause()
			if not space.is_valid():return {}
			var result:=test(q,yaw,mounted)
			if not result.valid:
				rejected[result.reason]=int(rejected.get(result.reason,0))+1;continue
			var path: Array[Vector3]=await approach(from,result.position,mounted)
			if path.is_empty():rejected["approach"]=int(rejected.get("approach",0))+1;continue
			result.path=path;result.reserve=reserve>0;result.reserve_row=reserve;result.id=id;result.rejected=rejected
			result.march_prefix_verified=segment_clear(path[0],path[1],mounted)
			occupied.append({"id":id,"polygon":footprint(result.position,result.basis,result.half+Vector2.ONE*MARGIN*unit_k)})
			diagnostics.append(result);return result
	# A reserve must still have a valid footprint. Keep the unsupported upstream
	# march prefix explicit in diagnostics rather than parking on the bad slope.
	for radius_step in range(12):
		for angle_step in range(32):
			var ray:=Vector3(sin(angle_step*TAU/32),0,cos(angle_step*TAU/32))
			var q:=centre+ray*(8.0+radius_step*1.8)*unit_k
			var yaw:=atan2(centre.x-q.x,centre.z-q.z)
			await pause()
			if not space.is_valid():return {}
			var result:=test(q,yaw,mounted)
			if not result.valid:continue
			var entering: Vector3=result.position+(from-result.position).normalized()*2.0*unit_k
			if not segment_clear(entering,result.position,mounted):continue
			result.id=id;result.reserve=true;result.reserve_row=3;result.path=[from,entering,result.position]
			result.rejected=rejected;result.march_prefix_verified=segment_clear(from,entering,mounted)
			occupied.append({"id":id,"polygon":footprint(result.position,result.basis,result.half+Vector2.ONE*MARGIN*unit_k)})
			diagnostics.append(result);return result
	# No reachable reserve in the bounded search: expose the failure for review.
	var fallback:=support(from,atan2(centre.x-from.x,centre.z-from.z),mounted)
	fallback.id=id;fallback.reserve=true;fallback.reserve_row=4;fallback.path=[from];fallback.rejected=rejected
	fallback.position=stage.ground_point(from);fallback.basis=Basis(Vector3.UP,atan2(centre.x-from.x,centre.z-from.z))
	diagnostics.append(fallback);return fallback

static func along(path: Array, fraction: float) -> Vector3:
	var length:=0.0
	for i in range(1,path.size()):length+=path[i-1].distance_to(path[i])
	var left:=length*clampf(fraction,0,1)
	for i in range(1,path.size()):
		var span: float=path[i-1].distance_to(path[i])
		if left<=span:return path[i-1].lerp(path[i],left/maxf(.0001,span))
		left-=span
	return path[-1]
