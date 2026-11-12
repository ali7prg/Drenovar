extends RefCounted

const SESSION_PATH := "user://drenovar-session.bin"
const TOKEN_LENGTH := 129

static func valid(token: String) -> bool:
	if token.length() != TOKEN_LENGTH or token[64] != ".":
		return false
	for index in TOKEN_LENGTH:
		if index != 64 and not token[index] in "0123456789abcdef":
			return false
	return true

static func key() -> PackedByteArray:
	var device := OS.get_unique_id()
	if device.is_empty():
		return PackedByteArray()
	return ("DRENOVAR-iOS-session-v1:" + device).sha256_buffer()

static func read_session() -> String:
	var encryption_key := key()
	if encryption_key.is_empty() or not FileAccess.file_exists(SESSION_PATH):
		return ""
	var file := FileAccess.open_encrypted(SESSION_PATH, FileAccess.READ, encryption_key)
	if file == null or file.get_length() != TOKEN_LENGTH:
		return ""
	var token := file.get_as_text()
	return token if valid(token) else ""

static func save_session(token: String) -> Error:
	if not valid(token):
		return ERR_INVALID_DATA
	var encryption_key := key()
	if encryption_key.is_empty():
		return ERR_UNAVAILABLE
	var temporary := SESSION_PATH + ".tmp"
	var file := FileAccess.open_encrypted(temporary, FileAccess.WRITE, encryption_key)
	if file == null:
		return FileAccess.get_open_error()
	file.store_string(token)
	file.close()
	var result := DirAccess.rename_absolute(temporary, SESSION_PATH)
	if result != OK:
		DirAccess.remove_absolute(temporary)
	return result

static func forget() -> void:
	for path in [SESSION_PATH, SESSION_PATH + ".tmp"]:
		if FileAccess.file_exists(path):
			DirAccess.remove_absolute(path)
