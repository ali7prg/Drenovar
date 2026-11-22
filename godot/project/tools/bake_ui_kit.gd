extends SceneTree
## Bakes the premium UI kit PNGs (godot/art/ui/premium/paint_kit.py) into lossless
## PortableCompressedTexture2D resources under res://assets/ui/premium/.
## Each PNG is painted at 2 texels per canvas unit; size_override halves the reported
## size, so StyleBoxTexture margins stay in canvas units while the pixels stay crisp
## on the phone (iPhone 12 canvas scale 1.86).
##   python3 godot/art/ui/premium/paint_kit.py /tmp/kit_png
##   godot --headless --path godot/project -s res://tools/bake_ui_kit.gd -- --src=/tmp/kit_png
## kit_splash.png is soft and painted at 1 texel per unit (no override).

const OUT := "res://assets/ui/premium"
const SCALE := 2.0
const ONE_TO_ONE := ["kit_splash"]

func _initialize() -> void:
	var src := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--src="):
			src = arg.trim_prefix("--src=")
	if src.is_empty():
		push_error("bake_ui_kit: pass -- --src=<folder of PNGs>")
		quit(1)
		return
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT))
	# Outside the editor the compressed data is dropped after upload unless kept.
	PortableCompressedTexture2D.set_keep_all_compressed_buffers(true)
	var count := 0
	var bytes := 0
	for file in DirAccess.get_files_at(src):
		if not file.ends_with(".png"):
			continue
		var image := Image.load_from_file(src.path_join(file))
		if image == null:
			push_error("bake_ui_kit: cannot read " + file)
			quit(1)
			return
		image.convert(Image.FORMAT_RGBA8)
		var texture := PortableCompressedTexture2D.new()
		texture.create_from_image(image, PortableCompressedTexture2D.COMPRESSION_MODE_LOSSLESS)
		var name := file.get_basename()
		if name not in ONE_TO_ONE:
			texture.size_override = Vector2(image.get_size()) / SCALE
		var path := OUT.path_join(name + ".res")
		var error := ResourceSaver.save(texture, path, ResourceSaver.FLAG_COMPRESS)
		if error != OK:
			push_error("bake_ui_kit: cannot save %s (%d)" % [path, error])
			quit(1)
			return
		count += 1
		bytes += FileAccess.get_file_as_bytes(path).size()
	print("BAKE_UI_KIT textures=%d bytes=%d" % [count, bytes])
	quit(0)
