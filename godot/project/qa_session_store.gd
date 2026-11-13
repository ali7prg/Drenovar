extends SceneTree

# Saved login: v2 per-install key survives a changed device id, a v1 file is
# migrated, forget() removes everything.

const SessionStore = preload("res://src/session_store.gd")
var checks := 0
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, description: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(description)

func run() -> void:
	SessionStore.forget()
	var token := "a".repeat(64) + "." + "b".repeat(64)
	check(SessionStore.read_session().is_empty(), "Empty store returned a session")
	check(SessionStore.save_session(token) == OK, "Save failed")
	check(SessionStore.read_session() == token, "Saved session not read back")
	check(FileAccess.file_exists(SessionStore.KEY_PATH), "Per-install key missing")
	# A v1 file (device-id key) is migrated to v2 on first read.
	SessionStore.forget()
	var legacy := SessionStore.legacy_key()
	if not legacy.is_empty():
		var file := FileAccess.open_encrypted(SessionStore.SESSION_PATH, FileAccess.WRITE, legacy)
		file.store_string(token)
		file.close()
		check(SessionStore.read_session() == token, "v1 session not read")
		check(SessionStore.read_with(SessionStore.key()) == token, "v1 session not migrated to v2")
	SessionStore.forget()
	check(not FileAccess.file_exists(SessionStore.SESSION_PATH) and not FileAccess.file_exists(SessionStore.KEY_PATH), "Forget left files")
	print("QA_SESSION_STORE checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
