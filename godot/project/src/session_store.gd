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

const KEY_PATH := "user://drenovar-session.key"

# v1 derived the key from OS.get_unique_id() (identifierForVendor on iOS), which iOS
# may change for a re-signed sideloaded app; the saved login then became unreadable.
# v2 uses a random per-install secret kept next to the session (both live in the
# app's private container). v1 files are still read once and re-saved as v2.
static func legacy_key() -> PackedByteArray:
	var device := OS.get_unique_id()
	if device.is_empty():
		return PackedByteArray()
	return ("DRENOVAR-iOS-session-v1:" + device).sha256_buffer()

static func key(create := false) -> PackedByteArray:
	if FileAccess.file_exists(KEY_PATH):
		var stored := FileAccess.get_file_as_bytes(KEY_PATH)
		if stored.size() == 32:
			return ("DRENOVAR-iOS-session-v2:" + stored.hex_encode()).sha256_buffer()
	if not create:
		return PackedByteArray()
	var secret := Crypto.new().generate_random_bytes(32)
	var file := FileAccess.open(KEY_PATH, FileAccess.WRITE)
	if file == null:
		return PackedByteArray()
	file.store_buffer(secret)
	file.close()
	return ("DRENOVAR-iOS-session-v2:" + secret.hex_encode()).sha256_buffer()

static func read_with(encryption_key: PackedByteArray) -> String:
	if encryption_key.is_empty() or not FileAccess.file_exists(SESSION_PATH):
		return ""
	var file := FileAccess.open_encrypted(SESSION_PATH, FileAccess.READ, encryption_key)
	if file == null or file.get_length() != TOKEN_LENGTH:
		return ""
	var token := file.get_as_text()
	return token if valid(token) else ""

static func read_session() -> String:
	var token := read_with(key())
	if token.is_empty():
		token = read_with(legacy_key())
		if not token.is_empty():
			save_session(token)
	return token

static func save_session(token: String) -> Error:
	if not valid(token):
		return ERR_INVALID_DATA
	var encryption_key := key(true)
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

# Last known game state of the signed-in account, encrypted with the same per-install
# key. It lets the app open the player's own city immediately at launch while the
# server is contacted in the background. It is bound to the session that wrote it:
# a different login never sees another account's city.
const STATE_PATH := "user://drenovar-state.bin"
const STATE_LIMIT := 16 * 1024 * 1024

static func save_state(token: String, game_state: Dictionary, clock_offset: float) -> Error:
	if not valid(token) or not game_state.has("city") or not game_state.has("world"):
		return ERR_INVALID_DATA
	var encryption_key := key(true)
	if encryption_key.is_empty():
		return ERR_UNAVAILABLE
	var record := JSON.stringify({"owner": token.sha256_text(), "offset": clock_offset,
		"savedAt": Time.get_unix_time_from_system(), "state": game_state})
	var temporary := STATE_PATH + ".tmp"
	var file := FileAccess.open_encrypted(temporary, FileAccess.WRITE, encryption_key)
	if file == null:
		return FileAccess.get_open_error()
	file.store_string(record)
	file.close()
	var result := DirAccess.rename_absolute(temporary, STATE_PATH)
	if result != OK:
		DirAccess.remove_absolute(temporary)
	return result

# Returns {"state": Dictionary, "offset": float, "savedAt": float} or {} when there is
# no usable copy for this session.
static func read_state(token: String) -> Dictionary:
	var encryption_key := key()
	if not valid(token) or encryption_key.is_empty() or not FileAccess.file_exists(STATE_PATH):
		return {}
	var file := FileAccess.open_encrypted(STATE_PATH, FileAccess.READ, encryption_key)
	if file == null or file.get_length() > STATE_LIMIT:
		return {}
	var parser := JSON.new()
	if parser.parse(file.get_as_text()) != OK or not parser.data is Dictionary:
		return {}
	var record: Dictionary = parser.data
	if record.get("owner", "") != token.sha256_text() or not record.get("state") is Dictionary:
		return {}
	var game_state: Dictionary = record.state
	if not game_state.has("city") or not game_state.has("world") or not game_state.has("playerId"):
		return {}
	return {"state": game_state, "offset": float(record.get("offset", 0.0)), "savedAt": float(record.get("savedAt", 0.0))}

static func forget_state() -> void:
	for path in [STATE_PATH, STATE_PATH + ".tmp"]:
		if FileAccess.file_exists(path):
			DirAccess.remove_absolute(path)

static func forget() -> void:
	forget_state()
	for path in [SESSION_PATH, SESSION_PATH + ".tmp", KEY_PATH]:
		if FileAccess.file_exists(path):
			DirAccess.remove_absolute(path)
