extends RefCounted
## Stable resource identities for CI outputs. Node unique IDs are editor-generated
## random values and are unnecessary for these name-addressed static mesh scenes.

static func uid(path: String) -> int:
	return ("DRENOVAR-V6-ART:" + path).sha256_text().substr(0,15).hex_to_int()

static func save_mesh(mesh: ArrayMesh, path: String) -> void:
	assert(ResourceSaver.save(mesh,path,ResourceSaver.FLAG_COMPRESS) == OK)
	assert(ResourceSaver.set_uid(path,uid(path)) == OK)

static func save_scene(scene: PackedScene, path: String) -> void:
	assert(ResourceSaver.save(scene,path) == OK)
	var text := FileAccess.get_file_as_string(path)
	var node_id := RegEx.new()
	node_id.compile(" unique_id=-?[0-9]+")
	text = node_id.sub(text,"",true)
	var resource_uid := RegEx.new()
	resource_uid.compile(" uid=\"[^\"]*\"")
	text = resource_uid.sub(text,"",true)
	var file := FileAccess.open(path,FileAccess.WRITE)
	file.store_string(text)
	file.close()
	assert(ResourceSaver.set_uid(path,uid(path)) == OK)
