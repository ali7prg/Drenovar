extends SceneTree
const Store = preload("res://src/session_store.gd")
func _initialize() -> void:
	var token: String = "device." + "e".repeat(64)
	var state := {"city":{"name":"synthetic"},"world":{},"playerId":"synthetic"}
	assert(Store.save_state(token, state, 0.0, "https://staging.invalid") == OK)
	assert(not Store.read_state(token, "https://staging.invalid").is_empty())
	assert(Store.read_state(token, "https://primary.invalid").is_empty())
	assert(Store.save_state(token, state, 0.0, "https://primary.invalid") == OK)
	assert(not Store.read_state(token, "https://primary.invalid").is_empty())
	assert(Store.read_state(token, "https://staging.invalid").is_empty())
	Store.forget()
	print("SESSION_SERVER_BINDING_OK 6")
	quit()
