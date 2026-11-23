# DRENOVAR window inventory (premium UI, stages 1–4b)

Every window, modal, popup, toast and HUD panel in the Godot client, as of the stage-1 premium kit.
This is the checklist for later stages: 2 recruitment, 3 build + upgrade, 4 speed-ups, 5 everything
else, 6 performance, then the network fixes and build 1023.

How to read it:

- **Where**: function and line in the source. Line numbers are from the stage-1 head and will drift;
  search for the function name.
- **Layout**: the `open_modal` layout.
  - `full`: full-screen premium frame with the oak header band and the linen body.
  - `right` / `left` / `city_target`: docked panel with the bronze rim brackets.
  - `sheet`: bottom sheet.
  - `garrison`, `wide`, `profile`, `center`: large centred windows.
  - `result`: dark battle-result sheet.
- **V6**: whether a player on the production V6 server can reach the window.
  - `V6` means only the V6 path (`src/v6_panels.gd`).
  - `shared` means the same function runs on V6 and legacy servers.
  - `legacy` means the function is replaced by a V6 window when `is_v6_server()` is true, so only
    pre-V6 / offline test cities reach it.
- **Stage**: the stage that owns its in-depth redesign. Stage 1 applied the kit frame, fonts,
  buttons and colours to all of them.

All windows share one modal (`build_ui` in `src/main.gd`):

- vignette
- oak header band, which holds:
  - an eyebrow line
  - a Ruslan Display title
  - bronze flourishes (roomy layouts)
  - the close medallion
- linen body: optional hero art column, `modal_tools`, a `TouchScroll` body, `modal_status`, `modal_footer`
- bronze frame overlay (hidden on `full`)

`open_modal(title, layout, eyebrow, art)` resets it. `place_modal` and `arrange_modal` size it.

## V6 windows (src/v6_panels.gd) — production path

| Window | Where | Layout | Reached from | Content now | Stage |
|---|---|---|---|---|---|
| Строительство (construction strip) — stage 3 | `catalog` → `V6Build.open_strip` (src/v6_build.gd, src/build_strip.gd) | strip (whole screen over the blurred city) | HUD «Строить», city actions «Строить», plot tap, notifications | Title plate with builders and plots, rail of four category medallions with buildable counts, swipeable strip of carved cards in the lower part of the screen, the blurred city above (`src/build_card.gd`: diorama breaking out above the card, name, blurb, cost, time, «Построено x/1»; light silver with a plain caption «Больше строить нельзя» when built), placement on glowing plots with «Участок N · на опушке», a translucent ghost of the building and a floating confirm that keeps clear of the plot (`src/build_place.gd`) (`STAGE3.md`) | 3 (done) |
| Building inspect / upgrade — stage 3 | `inspect` (also `inspect_instance`) | full + live 3D pair | Building action ring «Улучшить/Сведения», strip card of a built type, requirement chips, defence (B18) | Live «Сейчас · ур. N» ➜ «После · ур. N+1» (src/building_stage.gd; the city's own level scenes, new parts lit, rendered on demand: still unless turning), at level V and above a veiled «Скоро» card with a disabled «Скоро» button (`main.MAX_OPEN_BUILDING_LEVEL`), effects with green deltas, «Улучшение до ур. X» cost strip, time pill with bonus + one main action «Улучшить» / «Построить» / «Сначала: X N» (in `modal_body`, where qa_building_actions looks for it), requirement chips (✓ / ✗, a missing one opens that building), plot list for an unbuilt type, wall strength (B18), links | 3 (done) |
| Подтвердить работу (quote) — stage 3 | `confirm` | full + live «После» hero | «Улучшить», plot list, research, heal, train | Eyebrow naming the work and plot (refused before any request past `MAX_OPEN_BUILDING_LEVEL`), «Рассчитываем…», then the server quote: «Что даст работа» (effects before/after with deltas), cost strip, time, base time and bonus, builders and workers, reserve; footer primary «Начать»; errors such as «Все строители заняты» | 3 (done) |
| Очереди поселения — stage 4a | `queues` → `V6Queues.open` (src/v6_queues.gd) | full + dark oak rail | HUD/city «Очереди», ring «Очередь», economy and catalogue links, notifications | Left rail of every queue by section (Строительство, Войска, Исследования, Лечение, Походы): drawn lanes with the order's portrait or emblem, bar, ticking time, «Свободно», «+N» waiting; right: timer band, «Быстрое использование» (least waste, applied one by one through the server), item rows I–V with painted art, escrow cost and «Отменить работу»; a free lane offers its work (`STAGE4A.md`) | 4a (done) |
| Ускорить работу — stage 4a | `speedups` → the same window focused on one order | full + rail | Ring «Ускорить», recruitment «Ускорить», queue lanes | The queues window opened on the order, «Вернуться к обучению» when it came from a window; «Закончено» and the way back when the job ends (`STAGE4A.md`) | 4a (done) |
| Recruitment (barracks, range, stables, siege workshop) — stage 2 | `services` → `V6Recruit.open` (src/v6_recruit.gd) | full + rail + 3D stage | Ring «Обучение», rail medallions, `open_recruitment` | Rail of training buildings, live unit on a dais (src/unit_stage.gd), tier cards, summary + «Подробнее», quantity/«Макс», cost strip, time, «Обучить», lock panel, running orders with «Ускорить»/«Отменить», completion banner (`STAGE2.md`) | 2 (done) |
| Академия, лазарет — stage 4a | `services` → `V6Services.research` / `hospital` (src/v6_services.gd) | full + diorama hero | Ring «Исследования» / «Лечение», army «Лазарет», `show_hospital` | Academy: one drawn card per family (emblem, rank I–XI as lozenges, next effect, cost with icons, time, «Исследовать» / «Нужна академия X» / a running bar and «Очередь»). Lazaret: chips (wounded, beds, batch), a row per wounded unit (portrait, slider and field), cost strip, time pill, «Лечить» (`STAGE4A.md`) | 4a (done) |
| Рынок — stage 4b | `trade` → `V6Economy.trade` (src/v6_economy.gd) | full + hero | Ring «Рынок», `show_trade` | Turnover bar with the fee, one quantity (slider, field, quick amounts), a card per resource (`Deal_<r>`) with stock and the coin estimate, «Продать X» (lapis), «Купить X» (forest enamel) (`STAGE4B.md`) | 4b (done) |
| Экономика поселения — stage 4b | `economy` → `V6Economy.economy` | full | HUD resource counters, city actions, menu | Income on an oak band; a card per resource (`Resource_<r>`): stock against storage on a bar, reserve, green rate or why it stopped, «Склад полон» ribbon, when the storage fills; workers and army bars; links (`STAGE4B.md`) | 4b (done) |
| Армия и осада — stage 4a | `army` → `V6Army.army` (src/v6_army.gd) | full + dark oak column | HUD «Армия», city actions | Oak column: capacity bar, march limit, parallel parties, beds, wounded, «Лазарет», «Показать плац»; right: tier cards of the troops at home with names (a card opens its building), rams, parties on the march with timers and recall, targets (`STAGE4A.md`) | 4a (done) |
| Поход: … (formation) — stage 4a | `formation` → `V6Army.formation` | full + dark oak column | Army window, march targets | Oak column with the target and the march capacity filling; «Все доступные», «Очистить»; a row per unit (portrait, slider, field); «Рассчитать поход» | 4a (done) |
| Отправить отряд — stage 4a | `V6Army.confirm_march` | center | Formation «Рассчитать поход» | Server preview: arrival, return, losses note, portraits of the party, «Отправить» | 4a (done) |
| Переместить здание | `move_building` :163 | full + hero | Ring «Переместить» | Suitable plots as buttons | 3 |
| Цели поселения — stage 4b | `objectives` → `V6Economy.objectives` | full + oak column | Menu (badge), economy link, `show_city_guide`, `show_starter_goals` | Progress in the oak column; quest cards (`Objective_<id>`): Roman number, what to do, reward chips, ribbon Получено / Готово / Сейчас / Впереди; «Получить награду» (`ClaimReward`) only on the current finished one, «Как выполнить» elsewhere (`STAGE4B.md`) | 4b (done) |
| Аккаунт — stage 4b | `account` → `V6Menu.account` (src/v6_menu.gd) | full + oak column | HUD «Профиль», `show_account`, `show_transfer_choice`, first launch | Profile card, cards for sign-in, names and settlements, archive, pairing code, sign out; version line (`STAGE4B.md`) | 4b (done) |
| Имена и поселения — stage 4b | `V6Menu.profile` (+ `main.add_name_fields`) | full + oak column | Account | Name fields; a card per settlement (current: gold rim, «Текущее»; others «Открыть» → confirmation → `select_profile`) | 4b (done) |
| Код подключения — stage 4b | `pairing_code` → `V6Menu.pairing` | dialog | Account «Получить код подключения» | Code large on a carved plate (`KitMore.CodePlate`, never logged), time left, «Скопировать код», «Готово» | 4b (done) |
| Подтверждение — stage 4b | `V6Menu.confirm`, `main.confirm_profile_action` | dialog | Sign out, open another settlement | Medallion, question, «Отмена», the action (cranberry when it cannot be undone) | 4b (done) |
| Архив прежних зданий — stage 4b | `archive` → `V6Economy.archive` | full | Account (COMPAT-P2 test realm only) | Lead card, a card per archived building with diorama, level, former plot, compensation chips | 4b (done) |

## Shared and legacy windows (src/main.gd)

| Window | Where | Layout | V6 | Reached from | Content now | Stage |
|---|---|---|---|---|---|---|
| Меню — stage 4b | `show_controls_menu` → `V6Menu.open` (src/v6_menu.gd) | full + oak column | shared | HUD «Меню» | Profile column with «Звук» and «Меньше движения» switches; medallion tiles (`KitMore.MenuTile`, `Tile_*`) in groups `MenuSettlement`, `MenuMap`, `MenuAbout` with enamel badges; forest journal tile (`STAGE4B.md`) | 4b (done) |
| Поселение (city actions) — stage 4b | `show_city_actions` → `V6Menu.city_actions` (V6) | right | shared (V6 branch) | City long-press / HUD | V6: a grid of medallion tiles (build, queues, economy, army, hunt, objectives) and builder / worker chips; legacy: works list | 4b (V6 done) |
| Первые шаги (guide) | `show_city_guide` :912 | right | legacy (V6 → objectives) | City guide marker | Guide steps | 5 |
| Приложение DRENOVAR | `show_application` :929 | center | shared | Menu | Version, links | 5 |
| Resource window | `show_economy` :939 | left | legacy (V6 → economy) | HUD counters | Economy cards (kit row cards) | 5 |
| Строительство (bottom sheet) | `show_build_menu` :1092 | sheet | legacy (V6 → catalog) | HUD «Строить» | Group tabs (primary on the selected one), horizontal card strip | 3 |
| Build details | `show_build_details` :1577 | wide | legacy | Sheet card | Art, cost row on a kit strip, why-not reason (WARN), place button | 3 |
| Строительство (works) | `show_construction` :1646 | right | legacy (V6 → catalog) | City actions | Construction list | 3 |
| Construction order | `inspect_construction_order` :1673 | center | legacy (V6 → queues) | Order marker | Timer, speed-up, cancel | 3 / 4 |
| Расчистка рощ | `show_clearings` :1681 / :1691 | right / center | legacy | City actions | Groves, clear buttons | 5 |
| Первые шаги (starter) | `show_starter_goals` :1706 | right | legacy (V6 → objectives) | Starter banner | Goals | 5 |
| Ускорение · очередь | `show_speedups` :1777, `wait_for_order` :1801 | center | legacy (V6 construction/training → speedups) | Order «Ускорить» | Items «N мин · в наличии K» (texts protected by qa_speedups) | 4 |
| Применить ускоритель? | `preview_speedup` :1827 | center | legacy | Speed-up item | «Осталось X → станет Y» preview, confirm | 4 |
| Рынок (legacy) | `show_trade` :1944 | right | legacy (V6 → trade) | Market | Offers | 5 |
| Лазарет | `show_hospital` :1992 / :2019 | right / center | legacy (V6 → services B16) | Hospital | Wounded, heal confirm | 2 |
| Армия наготове | `show_armies` :2044 | garrison | legacy (V6 → army) | HUD «Армия» | Garrison roster, «Готовые войска →» | 2 / 5 |
| Garrison unit / disband | `show_garrison_unit` :2081 / :2088 | center / garrison | legacy | Garrison row | Unit card, disband confirm | 2 |
| Ступени армии | `show_military_cultures` :2094 | garrison | legacy | Garrison | Tiers per culture | 2 |
| Военные здания | `show_training_buildings` :2107 | center | legacy (V6 → catalog) | Army | Training buildings | 2 |
| Building (legacy) | `inspect_building` :2841 | right | legacy (V6 → inspect) | Building tap | Upgrade preview (BRONZE / INK_MUTED / GOOD), actions; no upgrade past `MAX_OPEN_BUILDING_LEVEL` | 3 |
| Оборона поселения | `show_city_defence` :2965 | right | legacy (V6 → inspect B18) | Walls | Walls, towers (qa_city_walls texts) | 5 |
| Отменить обучение? | `confirm_cancel_training` :3006 | center | legacy | Recruitment | Confirm | 2 |
| Recruitment (legacy) | `show_recruitment` :3115 | garrison | legacy (V6 → services) | Barracks | Tabs (selected = primary), unit name / role, terms plate on a kit strip, train | 2 |
| Encounter / hunt target — stage 4b | `inspect_encounter` → `WorldCards.encounter` (src/world_cards.gd) | city_target / right | shared | Creature tap | City: live 3D preview in a carved frame; map: head card with portrait and level; tiers, health card, reward chips, notes; footer «Атаковать» / «Собрать отряд» first (`STAGE4B.md`) | 4b (done) |
| Цели охоты — stage 4b | `show_city_hunt` (garrison), `show_world_hunt` → `WorldCards.hunts` | — | shared | Hunt buttons, army «Собрать отряд» | A card per creature (`Hunt_<id>`): portrait, level, state, «Открыть» | 4b (done) |
| Создать войско / Сбор отряда | `compose_march` | wide / right | shared (V6 pvp → formation) | Attack, hunt | Stage 4a: «Состав отряда» header, tier-tinted portraits, kit rows, LABEL names, round −/+ buttons, styled «Все доступные», «Обучить ещё воинов», «Очистить»; structure unchanged (route tests) | 4a (restyled) |
| Твоё королевство | `show_account` :4391, `show_transfer_choice` :4686 | profile | legacy (V6 → account) | HUD «Профиль» | Kingdom profile, names, transfer (stage 4b: name fields as kit fields) | 5 |
| Подтверждение — stage 4b | `confirm_profile_action` → `V6Menu.confirm` | dialog | shared | Profile | Medallion, question, «Отмена», action | 4b (done) |
| Плавность на этом устройстве | `show_performance` :4526 | center | shared | Menu | Frame-time report (diagnostics) | 6 |
| Летопись сражений — stage 4a / 4b | `show_reports` (src/report_row.gd) | full (full width since 4b) | shared | HUD «Отчёты» | One drawn row per report, newest first: outcome medallion, enamel badge (Победа / Поражение / Разведка), opponent and level, «4 мин назад», losses, spoils with icons, unread dot; stage 4b: the full width, the party's portraits with counts and the opponent's face at the right | 4a / 4b (done) |
| Battle report — stage 4a | `show_report` | result | shared | Report row, result notice | Medallion with the outcome emblem, figure tiles, spoils on oak plates with icons (Label «Еда +N» kept), a per-unit table with portraits (в строю / ранены / погибли) | 4a (done) |
| Поход (march) — stage 4b | `inspect_army` → `WorldCards.army` | center | shared | March on the world map | Head card with the party's portraits, a row per unit, countdown, recall | 4b (done) |
| World map: layers, directory, cities, marches — stage 4b | `show_map_options`, `show_world_directory`, `show_world_cities`, `show_world_marches` → `WorldCards.map_options` / `directory` / `cities` / `marches` | right / center | shared | World map buttons, menu tiles | Layers: two premium switches on cards (`LayerResources`, `LayerDetails`) and shortcuts; directory: three columns of tiles (`World_<emblem>`); cities and marches: cards with crests, distance chips, «К общему миру» | 4b (done) |
| Environment catalogue | `show_environment_catalog`, `focus_environment`, `pick_world_feature` | right / center | shared (debug-ish) | World map | Lists of environment models | 5 |
| Settlement / free plot / relocation — stage 4b | `inspect_settlement`, `inspect_world_plot`, `show_relocation_list` → `WorldCards.settlement` / `world_plot` / `relocation_list`; `inspect_plot` (V6 → catalog) | right | shared (plot: legacy) | World map taps | Head card with crest and banner colour, chips, facts; footer «Войти в город» / «Собрать отряд» / move confirmation | 4b (done) |
| Tree / feature | `pick_tree` :6484 | center | shared | City tree tap | Info | 5 |

## Forest adventure windows (src/forest_rescue/game/adventure_panels.gd)

All of these are V6-reachable when the adventure is on (`qa_forest_v6`). Their text colours were
remapped to ink for the linen body. Stage 4b: the journal and the rewards are rebuilt on the kit;
the others take the kit's buttons and headings through `hud_style.gd` (`STAGE4B.md`).

| Window | Where | Layout | Content |
|---|---|---|---|
| Route | `open_route` :54 | left | Acts and sites |
| Squad | `open_squad` :91 | left | Squad members |
| Journal — stage 4b | `open_journal` | wide | Oak `StatBand` (tasks, people home), actions, two switches, acts under rushnyk headings, a linen card per place (`Site_<id>`, gold rim when done) (also reachable from the menu) — 4b (done) |
| Rewards — stage 4b | `open_rewards` | left | One ledger card (`EscrowLedger` / `EscrowGrid`: captions once, a row per resource, left-to-take in bronze), «Пополнить все ресурсы» (`ClaimRewards`), auto-refill switch (`AutoRefill`) — 4b (done) |
| Network retry | `offer_retry` :380 | center | Pending command, retry |
| Site | `open_site` :390 | left | Site card, fight, captives |
| Horse prologue | `open_horse` :408 | left | Story |
| Boss | `open_boss` :419 | left | Boss card |
| Battle result | `open_battle_result` :440 | result | Result, rewards |

## HUD, overlays, toasts (not modals)

| Element | Where | V6 | Content / note |
|---|---|---|---|
| Top bar: profile medallion — stage 4a | `build_ui` (`hud_action`, symbol `profile`) | shared | Gold medallion with a helm, the settlement name in gold and «Ратуша N» on an oak pill; opens account |
| Resource counters | `add_resource_button` | shared | Icon + short amount, plate-less by design (qa_camera_hud protects «no card background»); stage 4a lays one translucent oak ribbon behind the whole row (`draw_wallet_band`), not a plate per counter |
| Navigation rail: Город, Карта, Строить, Армия, Отчёты, Меню — stage 4a | `build_ui` | shared | `src/hud_action.gd`: bronze medallions with forged emblems and outlined captions; enamel badges: red unread reports («9+»), green free builders (`refresh_hud_badges`) |
| Message toast — stage 4b | `build_ui` (`message`), `show_toast_change`, `draw_toast_mark` | shared | Carved oak plate (`toast_plate`) with a tone medallion (`UiKit.draw_tone`: good / warn / wait / info), 80 ms ease-in, calm errors (`calm_error`) |
| Connection badge — stage 4b | `build_ui`, `update_connection_notice` | shared | Same plate, wait medallion; rule unchanged (silent retries, shown after a failure and 10 s without an answer) |
| Result notice | `build_ui` :591 | shared | Battle-result banner button |
| Placement bar | `build_ui` ~:1358 | shared | Place / cancel bar while placing a building |
| Action ring — stage 4a / 4b | `src/action_ring.gd` | shared | Bronze medallions with forged emblems (RingButton, one drawn node each), the main action on gold, «Скоро» ribbon at the open level, «Ускорить» with the time left over a busy building, oak name plate; stage 4b: glazed discs and a 170 ms spring unfold that never blocks taps (none with less motion) |
| Launch screen | `src/launch_screen.gd` (`_ready` ~:258 in main) | shared | Branded loading steps |
| Building plates / timers over the city | `src/building_plates.gd`, `src/city_works.gd` | shared | Level plates; stage 4a: an oak timer pill with an hourglass, gold time and a filling line over every busy V6 building (construction, training, research, healing) |
| Minimap | `src/minimap.gd` | shared | World minimap |
| March map | `src/march_map.gd` | shared | March routes |
| Forest HUD, intro, mechanism UI — stage 4b | `src/forest_rescue/game/adventure_hud.gd`, `hud_art.gd`, `intro_director.gd`, `mechanism_ui.gd` | V6 (adventure) | `hud_style.gd` on the kit: linen task card, oak reward strip, «Маршрут» / «Отряд» medallions, gilded «Продолжить», oak toasts with tone medallions, enamel banner, dark oak cards in the bronze frame, slim oak battle header (`STAGE4B.md`) |
| Combat diagnostics / debug | `src/combat_diagnostics.gd`, `src/combat_debug.gd` | shared (debug) | Developer overlays |
| Tooltip / popup menu | theme `TooltipPanel`, `PopupMenu` | shared | Kit toast style |

## Notes for the next stages

- Recruitment (stage 2, done; see `STAGE2.md`): training buildings open the recruitment window.
  - All full-screen windows now have the tall header with the player's resources and a 40 px title.
  - Unit portraits (`assets/ui/units`) replace the painted unit art everywhere a unit icon appears.
  - The legacy `show_recruitment` keeps its garrison layout (with the new portraits).
- Build / upgrade (stage 3, done; see `STAGE3.md`):
  - The strip, the building window and the quote are rebuilt; the legacy build sheet keeps its
    stage-1 look.
  - Building levels stop at V for now (`main.MAX_OPEN_BUILDING_LEVEL`). Raise the constant when the
    level-VI models are ready; `qa_build_strip` and `qa_building_actions` read it.
- Speed-ups, HUD, army, services and reports (stage 4a, done; see `STAGE4A.md`):
  - One queues window serves «Очереди» and «Ускорить»; quick use applies the least-waste set
    through the server one item at a time.
  - The legacy `show_speedups` keeps its texts «N мин · в наличии K» (`qa_speedups`,
    `qa_server_speedups`).
  - Stage 4b owns the menu, account/profile, trade, economy, objectives, archive, world-map
    windows, encounters, the forest panels and the toasts.
- Menu, account, market, economy, objectives, archive, world windows, forest, toasts and the
  4a polish backlog (stage 4b, done; see `STAGE4B.md`):
  - New windows are lazy views (`v6_panels.view`), warm-compiled on a worker after launch.
  - Left for stage 5: the legacy-only windows, route and squad in the forest, the site, horse and
    boss forest windows (kit buttons and headings only), the environment catalogue.
- Everything else (stage 5) has the kit frame, fonts and buttons, but most bodies are still plain rows.
