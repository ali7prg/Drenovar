extends SceneTree

# Delayed transport fixture exercises the shipped V6 panel controller without
# touching a real settlement. Main scene networking has separate API-pool QA.
class FixtureUI extends Control:
	const Interface = preload("res://src/ui_theme.gd")
	const WebPanels = preload("res://src/web_panel_theme.gd")
	const UiKit = preload("res://src/ui_kit.gd")
	const TITLE_FONT = preload("res://assets/ui/NotoSerif-Regular.ttf")
	const RESOURCE_NAMES = {"wood":"Дерево","food":"Еда","stone":"Камень","iron":"Железо","coins":"Монеты"}
	# The open building level lives in main.gd only; the controller reads it from its UI.
	const Main = preload("res://src/main.gd")
	const MAX_OPEN_BUILDING_LEVEL = Main.MAX_OPEN_BUILDING_LEVEL
	const SOON_LINE = Main.SOON_LINE
	var capped_requests := 0
	var state := {"economy_version":"DRENOVAR-V6-C1.0","items":{"construction-1":3},"v6":{"buildings":[],"orders":[],"rewards":{},"stock":{},"capacities":{},"escrow":{},"production_per_hour":{},"production_stopped":{},"workforce":{"used":0,"capacity":5},"army_used":0,"army_capacity":100}}
	var modal_generation := 0
	var modal_body := VBoxContainer.new()
	var modal_footer := HBoxContainer.new()
	var modal_title := Label.new()
	var resource_icons := {}
	var request_count := 0
	var command_count := 0
	var ready_count := 0
	var fail_quote := false
	func _ready() -> void:
		for key: String in RESOURCE_NAMES:
			for bag: String in ["stock","capacities","escrow","production_per_hour","production_stopped"]:
				state.v6[bag][key] = 0
		theme = WebPanels.make_theme(Interface.make_theme())
		var sheet := PanelContainer.new()
		sheet.position = Vector2(400,24)
		sheet.size = Vector2(480,600)
		sheet.add_theme_stylebox_override("panel",WebPanels.gradient_style(Color("#30353b"),Color("#1d2025"),WebPanels.BRASS,18,14))
		add_child(sheet)
		var content := VBoxContainer.new()
		content.add_theme_constant_override("separation",12)
		sheet.add_child(content)
		modal_title.add_theme_font_override("font",TITLE_FONT)
		modal_title.add_theme_font_size_override("font_size",30)
		content.add_child(modal_title)
		content.add_child(modal_body)
		modal_body.add_theme_constant_override("separation",10)
		content.add_child(modal_footer)
	func ensure_v6_ready(_force := false) -> bool:
		ready_count += 1
		return true
	func request(_path: String,_body: Dictionary) -> Dictionary:
		request_count += 1
		await get_tree().create_timer(0.25).timeout
		if fail_quote:
			return {"error":"Нет соединения"}
		return {"ok":true,"quote":{"cost":{"wood":1870,"food":680,"stone":374,"iron":57,"coins":510},"base_seconds":7200,"duration_seconds":7200,"speed_bp":0}}
	func command(_order: Dictionary) -> bool:
		command_count += 1
		await get_tree().create_timer(0.25).timeout
		return true
	func v6_card(_type: String) -> Texture2D:return null
	func open_modal(title: String,_layout := "",_eyebrow := "",_art: Texture2D = null) -> void:
		modal_generation += 1
		modal_title.text = title
		empty(modal_body)
		empty(modal_footer)
	func empty(parent: Node) -> void:
		for child in parent.get_children():
			parent.remove_child(child)
			child.queue_free()
	func button(parent: Container,title: String,action: Callable) -> Button:
		var control := Button.new()
		control.text = title
		parent.add_child(control)
		if action.is_valid():control.pressed.connect(action)
		return control
	func row(parent: Container,text: String) -> void:
		var label := Label.new()
		label.text = text
		parent.add_child(label)
	func panel(_inset := 0) -> PanelContainer:return PanelContainer.new()
	func add_resource_icon(_parent: Container,_key: String,_pixels: int) -> void:pass
	func format_balance(value: int) -> String:return str(value)
	func timer_now() -> float:return Time.get_unix_time_from_system()*1000
	func bind_countdown(label: Label,_title: String,_ends: float) -> void:label.text="1 ч 59 мин"

var failures: Array[String] = []
func check(ok: bool,label: String) -> void:
	if not ok:failures.append(label);push_error(label)
func _initialize() -> void:call_deferred("run")
func run() -> void:
	root.size = Vector2i(1280,720)
	var ui := FixtureUI.new()
	root.add_child(ui)
	var panels = load("res://src/v6_panels.gd").new(ui)
	panels.confirm({"kind":"construction","building":"B05","target":5})
	check(ui.modal_title.text=="Подтвердить работу","quote panel opens synchronously")
	check(ui.modal_footer.get_child_count()==0,"cannot submit before authoritative quote")
	await create_timer(0.3).timeout
	check(ui.modal_body.find_children("KitCost","PanelContainer",true,false).size()==1,"cost cards rendered")
	check(ui.modal_footer.get_child_count()==1,"fixed primary action rendered")
	if OS.get_cmdline_user_args().has("--capture"):
		await process_frame
		await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("/workspace/releases/mobile-confirm.png")
	var start: Button=ui.modal_footer.get_child(0)
	start.pressed.emit()
	check(start.disabled and start.text=="Выполняем…","immediate disabled pending feedback")
	start.pressed.emit()
	check(ui.command_count==1,"double press sends exactly one command")
	await create_timer(0.3).timeout
	check(ui.request_count==1,"no second request after command success")
	panels.speedups({"kind":"construction","id":"fixture","ends_at":Time.get_unix_time_from_system()+7200})
	var uses: Array=ui.modal_body.find_children("*","Button",true,false).filter(func(b:Button):return b.text=="Использовать")
	check(uses.size()==1,"speedup cards use available stock")
	var use: Button=uses[0]
	use.pressed.emit();use.pressed.emit()
	check(ui.command_count==2,"speedup double press sends once")
	await create_timer(0.3).timeout
	check(ui.request_count==1,"speedup renders returned snapshot without refresh")
	ui.fail_quote=true
	panels.confirm({"kind":"construction"})
	await create_timer(0.3).timeout
	check(ui.modal_body.find_children("*","Button",true,false).size()==1,"failed quote offers retry")
	ui.fail_quote=false
	panels.confirm({"kind":"construction"})
	ui.open_modal("Another window")
	await create_timer(0.3).timeout
	check(ui.modal_title.text=="Another window" and ui.modal_footer.get_child_count()==0,"late quote cannot replace newer view")
	print("QA_V6_PANEL_FEEDBACK "+JSON.stringify({"passed":failures.is_empty(),"failures":failures,"checks":12}))
	ui.queue_free()
	await process_frame
	quit(0 if failures.is_empty() else 1)
