# DRENOVAR window inventory (premium UI, stage 1)

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
| Строительство (catalogue) | `catalog` :180 | full | HUD «Строить», city actions «Строить», plot tap, notifications | Note line, 3-column grid of drawn card tiles (`UiKit.KitTile`: card art, name, «Уровень N» / green «Построить»), links «Все очереди», «Армия и осада», «Подключить другое устройство» | 3 |
| Building inspect / upgrade | `inspect` :218 (also `inspect_instance` :51) | full + hero art | Building action ring «Улучшить/Сведения», catalogue tile, defence (B18) | «Уровень II ➜ III» step (display face, drawn arrow), effect rows `KitLine` with green next values, section «Следующий уровень», cost strip (red if short), timer pill «Базовое время», requirements with drawn tick or lozenge, primary «Проверить улучшение», wall strength + bar (B18), links (works, market, production) | 3 |
| Подтвердить работу (quote) | `confirm` :286 | full + hero | «Проверить улучшение», plot picks, research, heal, train | «Рассчитываем…», then the server quote: cost, time, reserve; footer primary «Начать» / cancel; errors such as «Все строители заняты» | 3 |
| Очереди поселения | `queues` :385 | full | Economy link, catalogue link, ring «Очереди», notifications | Attack warnings, section «Работы»: order cards (icon tile, name, kind, timer pill, progress bar, reserve, danger «Отменить работу», secondary «Использовать ускоритель»), green claim buttons, section «Запасы поселения» + stock lines | 3 / 4 |
| Ускорить работу | `speedups` :634 | full | Queue card «Использовать ускоритель», `show_speedups` | Timer pill «До завершения», hint, item rows (hourglass tile, «Ускорение · N», what it shortens, «В наличии: N», secondary «Использовать»), loss warning | 4 |
| Building works (barracks, range, stables, academy, hospital, siege) | `services` :446 | full + hero | Ring «Работы здания», `open_recruitment`, `show_hospital` | Section «Количество» + slider/field (`UiKit.quantity`), section «Отряды»/«Исследования»/«Раненые», unit plates with portraits, research and heal buttons | 2 |
| Рынок | `trade` :491 | full + hero | Ring «Рынок», `show_trade` | Section «Сделка», slider/field, per resource: icon + name, green «Купить X», secondary «Продать X», stock lines | 5 |
| Экономика поселения | `economy` :154 | full | HUD resource counters, city actions | Section «Запасы и доход», resource lines (icon, name, stock / cap · reserve, green «+N/ч» or warning), workers, army, links | 5 |
| Армия и осада | `army` :697 | full | HUD «Армия», city actions | Army / march / parallel / beds stat lines, army capacity bar, ram note, links (plaza, wounded), section «Отряды в походе» | 5 |
| Поход: … (formation) | `formation` :731 | full | Army window, march targets | Unit pickers, totals, send | 5 |
| Отправить отряд | `formation` :754 | center | Formation «Отправить» | Confirmation | 5 |
| Переместить здание | `move_building` :163 | full + hero | Ring «Переместить» | Suitable plots as buttons | 3 |
| Цели поселения | `objectives` :625 | full | Economy link, `show_city_guide`, `show_starter_goals` | Objectives with claim buttons | 5 |
| Аккаунт | `account` :536 | full | HUD «Профиль», `show_account`, `show_transfer_choice` | Version, test-world note, open web version, pairing code request, code field, connect, sign out | 5 |
| Код подключения | `pairing_code` :614 | center | Account «Получить код подключения» | 16-character code, timer | 5 |
| Архив прежних зданий | `archive` :600 | full | Account (COMPAT-P2 test realm only) | Archived buildings | 5 |

## Shared and legacy windows (src/main.gd)

| Window | Where | Layout | V6 | Reached from | Content now | Stage |
|---|---|---|---|---|---|---|
| Меню | `show_controls_menu` :616 | left | shared | HUD «Меню» | Tertiary buttons: account, performance, application info, forest journal hook | 5 |
| Поселение (city actions) | `show_city_actions` :875 / :883 | right / center | shared (V6 branch :872) | City long-press / HUD | V6: build, queues, resources, army; legacy: works list | 5 |
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
| Building (legacy) | `inspect_building` :2841 | right | legacy (V6 → inspect) | Building tap | Upgrade preview (BRONZE / INK_MUTED / GOOD), actions | 3 |
| Оборона поселения | `show_city_defence` :2965 | right | legacy (V6 → inspect B18) | Walls | Walls, towers (qa_city_walls texts) | 5 |
| Отменить обучение? | `confirm_cancel_training` :3006 | center | legacy | Recruitment | Confirm | 2 |
| Recruitment (legacy) | `show_recruitment` :3115 | garrison | legacy (V6 → services) | Barracks | Tabs (selected = primary), unit name / role, terms plate on a kit strip, train | 2 |
| Encounter / hunt target | `inspect_encounter` :3701 | city_target / right | shared | Creature tap | Health bar (kit track + green fill), attack | 5 |
| Цели охоты | `show_city_hunt` :3807 (garrison), `show_world_hunt` :3812 (right) | — | shared | Hunt buttons | Targets | 5 |
| Создать войско / Сбор отряда | `compose_march` :3829 | wide / right | shared (V6 pvp → formation) | Attack, hunt | Formation entries (kit row panels), summary (BRONZE), badges | 5 |
| Твоё королевство | `show_account` :4391, `show_transfer_choice` :4686 | profile | legacy (V6 → account) | HUD «Профиль» | Kingdom profile, names, transfer | 5 |
| Подтверждение | `confirm_profile_action` :4518 | center | legacy | Profile | Confirm | 5 |
| Плавность на этом устройстве | `show_performance` :4526 | center | shared | Menu | Frame-time report (diagnostics) | 6 |
| Летопись сражений | `show_reports` :5009 | right | shared | HUD «Отчёты» | Battle report list or «Пока нет боевых отчётов» | 5 |
| Battle report | `show_report` :5049 | result | shared | Report row, result notice | Dark result sheet (kit_body_dark), outcome, losses | 5 |
| Поход (march) | `inspect_army` :6306 | center | shared | March on the world map | Route, recall | 5 |
| World map: layers, directory, cities, marches, environment | `show_map_options` :2444, `show_world_directory` :2455, `show_world_cities` :2467, `show_world_marches` :2476, `show_environment_catalog` :2488, `focus_environment` :2536, `pick_world_feature` :6339 | right / center | shared | World map buttons | Lists of cities, marches, layers, environment models | 5 |
| Settlement / free plot / relocation | `inspect_settlement` :6343, `inspect_world_plot` :6371, `show_relocation_list` :6410, `inspect_plot` :6431 (V6 → catalog) | right | shared (plot: legacy) | World map taps | Settlement info, relocate | 5 |
| Tree / feature | `pick_tree` :6484 | center | shared | City tree tap | Info | 5 |

## Forest adventure windows (src/forest_rescue/game/adventure_panels.gd)

All of these are V6-reachable when the adventure is on (`qa_forest_v6`). Their text colours were
remapped to ink for the linen body. The dark site box (lines ~229–291) and the result content keep
their own colours.

| Window | Where | Layout | Content |
|---|---|---|---|
| Route | `open_route` :54 | left | Acts and sites |
| Squad | `open_squad` :91 | left | Squad members |
| Journal | `open_journal` :150 | wide | Chapters (also reachable from the menu) |
| Rewards | `open_rewards` :296 | left | Rewards |
| Network retry | `offer_retry` :380 | center | Pending command, retry |
| Site | `open_site` :390 | left | Site card, fight, captives |
| Horse prologue | `open_horse` :408 | left | Story |
| Boss | `open_boss` :419 | left | Boss card |
| Battle result | `open_battle_result` :440 | result | Result, rewards |

## HUD, overlays, toasts (not modals)

| Element | Where | V6 | Content / note |
|---|---|---|---|
| Top bar: «Профиль» medallion | `build_ui` :404 (`hud_action`) | shared | Opens account |
| Resource counters | `add_resource_button` (~:646) | shared | Icon + amount, plate-less by design (qa_camera_hud protects «no card background»); outline + shadow carry legibility |
| Navigation rail: Город, Карта, Строить, Армия, Отчёты, Меню | `build_ui` :418–423 | shared | `src/hud_action.gd` medallions |
| Message toast | `build_ui` :447 (`message`) | shared | Kit oak pill (`UiKit.toast_style`), ivory Philosopher text, hidden when empty |
| Connection badge | `build_ui` :457 | shared | Kit oak pill, offline notice |
| Result notice | `build_ui` :591 | shared | Battle-result banner button |
| Placement bar | `build_ui` ~:1358 | shared | Place / cancel bar while placing a building |
| Action ring | `src/action_ring.gd` (`open` :43) | shared | Radial building actions (upgrade, queues, works, market, move) |
| Launch screen | `src/launch_screen.gd` (`_ready` ~:258 in main) | shared | Branded loading steps |
| Building plates / timers over the city | `src/building_plates.gd`, `src/city_works.gd` | shared | Level plates, work timers |
| Minimap | `src/minimap.gd` | shared | World minimap |
| March map | `src/march_map.gd` | shared | March routes |
| Forest HUD, intro, mechanism UI | `src/forest_rescue/game/adventure_hud.gd`, `hud_art.gd`, `intro_director.gd`, `mechanism_ui.gd` | V6 (adventure) | Own HUD style (`hud_style.gd`); not restyled in stage 1 |
| Combat diagnostics / debug | `src/combat_diagnostics.gd`, `src/combat_debug.gd` | shared (debug) | Developer overlays |
| Tooltip / popup menu | theme `TooltipPanel`, `PopupMenu` | shared | Kit toast style |

## Notes for the next stages

- Recruitment (stage 2): the V6 path is `services`.
  - Tier cards and rail buttons exist in the kit (`UiKit.tier_card`, `UiKit.rail_button`) but are not
    used yet.
  - The legacy `show_recruitment` keeps its garrison layout.
- Build / upgrade (stage 3):
  - `catalog` and `inspect` already use the kit.
  - The confirm window is still a plain list, and the server-quote layout needs a proper cost/time card.
- Speed-ups (stage 4): the V6 list uses kit rows. The legacy texts «N мин · в наличии K» are
  protected by `qa_speedups` / `qa_server_speedups`.
- Everything else (stage 5) has the kit frame, fonts and buttons, but most bodies are still plain rows.
