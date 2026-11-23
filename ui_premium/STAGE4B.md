# DRENOVAR premium UI — stage 4b: menu, account, market, economy, objectives, world, forest, toasts

Stage 4b brings the rest of what the player touches to the premium kit:
- the menu (medallion tiles, the sound and less-motion switches);
- the account and profile windows, the pairing code, the confirmations;
- the market, the economy, the objectives (with the claim), the archive;
- the world map's windows: a creature, a settlement, a free place, a march, the hunt list, the
  cities, the directory, the map layers, and the march action;
- «Лес потерянных»: the adventure row, toasts, banner, invitation, intro card, locked card,
  battle header, mechanism panel, journal and reward reserve;
- one style for toasts, banners, errors and confirmations;
- the polish backlog of stage 4a: the army window, the chronicle's width, the ring's unfold,
  the «new parts» highlight, the «Скоро» card, the spearman's helmet, the first building window.

The look follows `ART_DIRECTION.md`: carved oak and bronze, linen, enamel, gold. The reference
game was used for the quality bar and composition only. Nothing from it is in the repository: no
frames, crops, traces or sheets. The side-by-side sheets stay in the session scratchpad.

`MAX_OPEN_BUILDING_LEVEL := 5` is unchanged.

## What the player sees

### Menu (`src/v6_menu.gd`, `open`)

A full window instead of a column of buttons:
- **Left: the oak profile column** (`KitMore.ProfileCard`): a gold medallion with the
  settlement's crest, its name, a pill with the hall level, a few figures. Under it, «Настройки»:
  two premium switches, «Звук» (the master bus; the forest follows) and «Меньше движения» (windows
  open without their settle, the ring without its unfold, the forest's own reduced motion).
- **Right: tiles in three groups** under rushnyk headings:
  - «Поселение»: settlement and building, queues, economy, objectives, army, chronicle;
  - «Карта и вид»: centre the city, world map, layers, rotate, zoom (the world's set on the map);
  - «Сведения»: account, the forest journal (when the adventure is on), smoothness, about.
- Each tile is one drawn Button (`KitMore.MenuTile`): a linen plate, a bronze medallion with a
  forged emblem, the caption under it, an enamel badge with a count. Badges: free builders
  (green), running orders (bronze), objectives ready to claim (green), unread reports (red).
  Touch-down shows at once: the plate darkens and the medallion sinks 2 px.

### Account and profile (`src/v6_menu.gd`, `main.gd`)

- **«Аккаунт»** (also the first launch): the oak profile column, then cards for what can be done
  here (sign in, the names and settlements, the archive, the pairing code, sign out); the version
  line at the foot.
- **«Имена и поселения»** (`profile`, with `main.add_name_fields`): the names as kit fields; one
  card per settlement of the account, the current one with a gold rim and the ribbon «Текущее»,
  the others with «Открыть» (through `confirm_profile_action` → `select_profile`).
- **«Код подключения»** (`pairing_code`): a small dialog; the code large on a carved oak plate
  (`KitMore.CodePlate`: groups of four in gold Philosopher figures, a lozenge between them), the
  time left, «Скопировать код» with a copy emblem and «Готово». The code is drawn and copied, never
  printed or logged.
- **Confirmations** (`confirm`, `confirm_profile_action`): a small dialog with a medallion, the
  question, «Отмена» and the action (cranberry when it cannot be undone).

### Market, economy, objectives, archive (`src/v6_economy.gd`)

- **«Рынок»**: the market's diorama in the hero; the day's turnover on a bar with the fee; one
  quantity for every deal (slider, field, quick amounts); a card per resource with the stock and
  what the chosen amount costs or brings in coins (an estimate from the balance's base prices and
  the fee; the server decides), «Продать» (lapis) and «Купить» (forest enamel).
- **«Экономика поселения»**: the hourly income on an oak band; a card per resource with its stock
  against the storage on a bar, the reserve, the rate (green) or why it stopped, and when the
  storage fills («Склад полон» ribbon and «Освободите место на складе» when it is full); workers
  and the army as bars; links.
- **«Цели поселения»**: the progress in the oak column; a quest card per objective (Roman
  number, what to do in the player's words, the reward as chips with icons, a ribbon «Получено» /
  «Готово» / «Сейчас» / «Впереди»). Only the current, finished objective offers «Получить
  награду»; the others offer «Как выполнить», which goes where it is done. A claim sends the same
  command as before (`starter71`) and the toast says «Готово: награда получена · …».
- **«Архив прежних зданий»**: a lead card, then a card per archived building with its diorama,
  level, former plot and the compensation with icons.

### World windows (`src/world_cards.gd`)

Every window starts with a head card (`KitMore.HeadCard`): a framed portrait (a creature) or a
crest (a settlement) on an ink wash, the name, a line and a kokoshnik badge with the level. Then
chips (distance from the player's city, coordinates, rewards with icons) and the facts. The main
action is a gilded button in the footer, the footer's first child as the march tests expect:
- a creature (`inspect_encounter`): in the city its live 3D preview in a carved frame; on the map
  the head card; tiers, a health card, the rewards, notes; «Атаковать» / «Собрать отряд»;
- the hunt list: a card per creature with its portrait, level and state, «Открыть»;
- a settlement (`inspect_settlement`): crest and banner colour, owner, distance; «Войти в город»
  or «Собрать отряд»;
- a free place (`inspect_world_plot`) and the relocation list;
- a march (`inspect_army`): the party's portraits in the head, a row per unit (since 1023 the whole
  unit on a portrait tile, `KitMore.Card` icon mode «figure»), the countdown, recall;
- the cities, the marches, the world directory (three columns of tiles with the worlds' emblems),
  the map layers (two premium switches on cards and the map's shortcuts).
A march's travel time comes from the server's route quote in the march window; nothing guesses it.

### «Лес потерянных» (`src/forest_rescue/game/`)

`hud_style.gd` keeps its function names and now returns kit surfaces, so every forest widget keeps
its structure, names and behaviour:
- **The adventure row** (`adventure_hud.gd`): «Конь без всадника · 0 / 3» on a linen task card
  (the forest banner, the title in ink, enamel progress gems, the count in bronze); the rewards
  «За спасение:» on a carved oak strip with a forged chest and gold amounts; «Маршрут» (pennant)
  and «Отряд» (shield) as bronze medallions drawn exactly like the city's HUD actions beside them
  (`draw_medal`: disc, emblem, outlined caption, a 2 px sink on touch); «Продолжить» on a gilded
  plate with dark chevrons (pale when it is closed). The caption Labels stay («Caption»).
- **Hint**: a dark oak pill.
- `hud_art.gd` is unchanged: its vector marks (the task banner with the tree sigil, the
  chevrons, the medallion over the banner and the cards) already matched the kit's gold and
  ink, and stay; the chest, pin and squad marks gave way to the kit's forged emblems.
- **Toasts**: the city's carved oak plate with the tone medallion at the left (`UiKit.draw_tone`,
  now shared with `main.gd`): a reward is good, an error a calm amber mark, a lost connection a
  wait. A short notice sits on a plate fitted to its words.
- **Banner** («Пленник освобождён»): forest enamel with a bronze rim, the title in the display face
  in gold, cranberry ribbon tails with bronze edges, the medallion above.
- **Locked card, intro card, mechanism panel**: dark oak in the windows' bronze corner frame
  (`hud_style.Layered`, a StyleBox that draws the tiled oak and the frame), titles in the display
  face, the kit's round close button.
- **Calls to action** («Открыть приключение», «Следовать за лошадью», «К ратуше», «Добыть»): the
  kit's gilded primary. Mechanism symbols and «Отступить»: the linen tertiary.
- **Battle header**: a slim carved oak strip, the name in gold, a thin red health bar in a bronze
  line.
- **Journal** («Дороги домой»): a carved oak band with the campaign's two counts (`StatBand`:
  «Заданий спасения», «Вернулись домой»), the actions, the two switches on their own row, the acts
  under rushnyk headings, a linen card per place (a gold rim once all five tasks are done,
  quotes in italic, the testimony in bronze).
- **Reward reserve**: one ledger card: the column captions once, a row per resource with its
  icon, earned and claimed in muted ink, what is left to take in bronze; «Пополнить все ресурсы»
  and the auto-refill switch under it.

### Toasts, banners, errors, confirmations

- One toast: the carved oak plate (`kit_strip`) with a tone medallion: good (a tick on green),
  warn (a calm amber mark, never red), wait (an hourglass), info (an «i» on lapis). The text eases
  in over 80 ms (none with less motion).
- Errors are calm (`main.calm_error`): the server's own words, a hint where the words alone
  leave the player stuck («Сервер сейчас недоступен. Мы повторим сами; можно продолжать играть.»),
  and the amber mark; the city's red is kept for losses and the danger buttons.
- The connection pill keeps its rule exactly: silent retries, shown only after a failure and
  10 s without an answer, hidden at the next answer. Only its plate and medallion changed.
- Confirmations are a small dialog with a medallion (see the account).

### Polish backlog

- **(a) Army window** (`src/v6_army.gd`): an oak `StatBand` at the top (warriors at home, the
  army's might as Σ count × power reference, wounded, on the march), a «Собрать отряд» entry
  (enabled when anyone is home) and larger unit cards (138 × 192). See decision 4 for the live
  stage.
- **(b) Chronicle**: the window uses the full width; a wide row shows the party's portraits with
  counts and the opponent's face on an ink wash at the right.
- **(c) The ring** (`src/action_ring.gd`): the medallions unfold from the building with a spring
  (170 ms, an 18 ms stagger, ease-back), glazed enamel discs (`kit_ring_disc`, `_on`). The unfold
  only changes how each medallion is drawn; its Control is at its place, full size and
  `MOUSE_FILTER_STOP` from the first frame, so a tap during the unfold runs its action. Less
  motion: no unfold.
- **(d) «New parts»** (`src/building_new_parts.gdshader`): the parts of the next level keep their
  own texture; a thin gold rim on the silhouette and a faint diagonal glint, instead of a flat gold
  wash.
- **(e) «Скоро»** (`building_stage.draw_soon`): the current building as a dark silhouette with a
  light halo in drifting mist, the carved «Скоро» plate and one line; the tile is not drawn, so no
  edge shows.
- **(f) Spearman's helmet** (`src/unit_stage.gd`, `stage_helmet`): on the UI stage only, a
  per-instance surface override makes the steel helmet darker and rougher (albedo × 0.56,
  roughness ≥ 0.74, metallic ≤ 0.28, specular 0.2), since the brim's underside turned white at a
  grazing angle to the stage's floor and sky. The battlefield and the city keep the shared
  material.
- **(g) The first building window**: the upgrade pair's turf tiles were built on the main thread in
  the frame after the window opened (about 15 ms per tile, two per window). Their mesh arithmetic
  now runs on a worker as the window opens; the meshes are kept for eight seeds; every task is
  waited for when the stage leaves the tree. The window scripts were already warm (stage 4a).

## Decisions

1. **Lazy views, warm-compiled after launch.** `v6_menu.gd`, `v6_economy.gd`, `world_cards.gd` and
   `kit_more.gd` are not preloaded by `main.gd`; `v6_panels.view(key)` loads them, and the stage-4a
   warm compile on a worker after launch now includes them. The forest scripts load with the
   forest layer, as before; the journal loads `kit_more.gd` when it opens.
2. **Drawn controls, real Buttons.** Tiles, cards, chips and bands draw themselves from cached text
   lines (`UiKit.KitText`); every action is still a Button with its `.text` (tests, screen readers,
   touch feedback). Labels that tests read (forest journal, rewards, captions) stay Labels.
3. **Tests protected:** `modal_footer.get_child(0)` stays «Атаковать» (city) or «Собрать отряд»
   (world); «Купить Дерево» still leads to «Очереди поселения»; «Аккаунт» stays the title the
   playable pack checks; the connection pill's visibility rule and `message.text` are untouched;
   the forest captions, task title, reward amounts and node names are unchanged.
4. **No live 3D in the army window.** The recruitment stage costs about 4–5 ms more per open plus
   a viewport render per frame while it shows; the baked portraits come from the same models. The
   army window keeps portraits and gets the summary band instead.
5. **Switch textures at half size.** A `PortableCompressedTexture2D`'s `size_override` is not what
   `get_size()` reports to a CheckButton, so `UiKit.HalfTexture` (a scripted Texture2D) reports
   64 × 34 and draws the 128 × 68 texels scaled: crisp on the phone, laid out in canvas units.
6. **Forest calls to action are gilded, not red.** The forest's art/18 red buttons became the kit's
   primary (gilded) so the whole game has one primary look; cranberry stays for actions that
   cannot be undone.
7. **Forest switches keep their meaning.** «Звуки леса» is the forest's own sound (not the master
   bus), «Меньше движения» the forest's reduced motion; the main menu's switches still sync the
   forest (`main.set_sound`, `main.set_reduced_motion`), as before.
8. **The forest row's widths.** The kit's oak strip keeps 18 units at each end for its lozenges; to
   keep the row inside the 1022 navigation's left edge (874 px of 1366) the compact progress gems
   are 22 units apart instead of 26. `qa_forest_flow`'s «bar does not overlap navigation» guards
   it.
9. **Tile meshes on a worker.** Only arrays are built off the main thread (no RenderingServer
   calls there); ArrayMeshes are made on the main thread when the tile is attached. Every task is
   waited for (`finish_tile`), since an unwaited WorkerThreadPool task aborts the engine at exit.
10. **Shot fixtures.** For the stills the scripts add display-only data that the synthetic fixture
    lacks (battle reports, an archive entry, a march and a creature on the world map); the forest
    stills drive its interface over the city with recorded realm states through a stub transport.
    None of it reaches a server.
11. **The first launch's «Аккаунт» compiles off the main thread.** As a lazy view, the account
    window would have compiled `kit_more.gd` and `v6_menu.gd` (about 70 ms here) on the main
    thread in the frame the launch screen starts to fade. When the launch is going to open it (a
    fresh install, or a login in progress, on the live server), `main.gd` asks
    `v6_panels.request_view("menu_view")` before the city's first frames are drawn, and the
    worker finishes it during those frames: in a rendered launch here the script was ready
    three frames before the account opened, which still opens in the same frame as before
    (`verify_playable_pack`'s «account entry» holds). Other launches are unchanged.

## Files

New:
- `src/v6_menu.gd`: the menu, «Поселение» tiles, the account, names and settlements, the
  pairing code, confirmations (a lazy view).
- `src/v6_economy.gd`: the market, the economy, the objectives with the claim, the archive (lazy).
- `src/world_cards.gd`: every world map window (lazy).
- `src/kit_more.gd`: drawn controls shared by them and the forest journal: `MenuTile`, `Card`,
  `ProfileCard`, `CodePlate`, `ChipRow`, `HeadCard`, `StatBand`, `Paint` helpers.
- `godot/tools/qa_stage4b.gd`: the stage's checks.
- `godot/project/qa_stage4b_shots.gd`, `qa_stage4b_forest.gd`: stills and open times.

Changed:
- `src/ui_kit.gd`: the switch textures in the theme (`switch_icon`, `HalfTexture`), the tone
  medallion (`draw_tone`), 19 new kit textures in the preload list.
- `src/main.gd`: world windows routed to `world_cards.gd`; toasts' tone medallion through
  `UiKit.draw_tone`; calm errors; the full-width chronicle (`modal_full_width`); the party and the
  opponent on report rows; the creature portraits warmed on a worker after launch; the ring's
  less-motion flag; the first launch's account script asked for early (decision 11).
- `src/v6_panels.gd`: the market, economy, objectives and archive call `economy_view`; the menu
  and account call `menu_view`; the three new view scripts in `VIEW_SCRIPTS` (warm compile);
  `request_view` (decision 11).
- `src/v6_army.gd`: the summary band, the compose entry, larger cards.
- `src/report_row.gd`: party portraits and the opponent on wide rows.
- `src/action_ring.gd`: the spring unfold (drawing only), glazed discs, less motion.
- `src/building_stage.gd`: tile meshes on a worker, the misty «Скоро».
- `src/building_new_parts.gdshader`: the rim and glint.
- `src/unit_stage.gd`: the stage-only helmet override.
- `src/forest_rescue/game/hud_style.gd`, `adventure_hud.gd`, `adventure_panels.gd`,
  `mechanism_ui.gd`, `intro_director.gd`: the forest on the kit.
- `godot/project/qa_runtime.gd`: looks for the menu's entries among the tiles (Buttons in the
  tile grids) instead of the old column; the same entries are required.
- `godot/art/ui/premium/paint_kit.py`: `stage4b_art` paints the new textures.

## Art

`paint_kit.stage4b_art` (procedural, like the rest of the kit; baked by `tools/bake_ui_kit.gd`
at 2 texels per canvas unit), 19 textures, 153 981 bytes in all:
- 15 forged emblems: `kit_emb_aim` (centre), `award` (objectives), `bell`, `chest`, `copy`,
  `exit` (sign out), `gauge` (smoothness), `globe` (shared world), `key` (account), `layers`,
  `next`, `rotate`, `tree` (the forest), `zoom_in`, `zoom_out`;
- the switch, on and off (`kit_switch_on` / `_off`, 128 × 68 texels, drawn at 64 × 34);
- the ring's glazed discs (`kit_ring_disc`, `kit_ring_disc_on`).
The forest restyle adds no texture: it uses the kit's (`kit_row`, `kit_strip`, `kit_pill`,
`kit_body_dark`, `kit_frame`, `kit_btn_*`, `kit_rail`, `kit_emb_march`, `kit_emb_shield`,
`kit_emb_chest`, `kit_card_frame`, `kit_stitch`, `kit_rosette`).

## Stills and polish passes

Stills in `ui_premium/shots/stage4b/` (JPEG, q 85, 79 files): `before_*` from the stage-4a head
(d724c23, a scratch copy of the project), `after_*` from this stage, both at 1366×630 and from the
same scripts (`qa_stage4b_shots.gd`, `qa_stage4b_forest.gd`), and one still rendered for
2532×1170 (`after_big_menu`; the game keeps its 1366:630 design aspect, `canvas_items` stretch
with the default «keep», and the still of a 2532×1170 window comes out 2532×1167, as in stages
2–4a).
The `after_*` stills are those of the final sweep (below):
- menu and account: `menu`, `world_menu`, `account`, `account_entry` (a fresh device),
  `pairing`, `confirm` (the sign-out question);
- `trade`, `economy`, `objectives`, `archive`;
- world: `world`, `encounter`, `hunts`, `settlement`, `settlement_rival`, `world_plot`, `march`,
  `cities`, `directory`, `map_layers`;
- toasts and the pill: `toast`, `toast_error`, `banner_offline`;
- polish: `army`, `reports`, `ring`, `ring_unfold` (held at 45 % of the unfold), `upgrade` (the new
  parts), `soon`, `recruit` (the spearman's helmet);
- forest: `forest_bar`, `forest_toast` (two toasts and the banner), `forest_battle`,
  `forest_journal`, `forest_rewards`, `forest_mech`, `forest_invite`, `forest_intro_card`,
  `forest_locked`.

Side-by-side sheets with the reference frames (19: the menu, account, market, economy,
objectives, army, recruitment, reports, ring, upgrade, «Скоро», toasts, the creature, the hunts,
a settlement, the world menu, the forest row, journal and rewards) were made in the session
scratchpad only.

**Pass 1** (after the first forest stills and the 1022 flow test):
- the journal's two switches shared one wrapping row with its three action buttons: they have
  their own row now (`JournalSettings`), under the actions;
- the oak reward strip and the linen task card made the forest row 824 units wide where the 1022
  navigation leaves 810, and `qa_forest_flow` failed «bar does not overlap navigation»: the strip
  keeps 18 units at its ends (22 before), the linen card's content inset is smaller, and the
  compact progress gems are 22 units apart (decision 8).

**Pass 2** (after the stills of every window):
- the menu and the world menu ran past the right edge and hid the close button: a tile's Button
  text (transparent; the caption is drawn in two lines) widened its tile to one line of it; it is
  clipped now;
- a long creature or settlement name was trimmed in the head card at once; it steps down 24, 21,
  19 units first;
- the spearman's brim underside still read as a white ring on the UI stage: rougher and less
  metallic there (polish f);
- the stills themselves: the sign-out confirmation as the account asks it (cranberry, the exit
  emblem), the offline pill set again just before its capture (the fixture's polls cleared it),
  the ring held mid-unfold (lavapipe drew it at rest).

## Measurements

All on this container (4 cores, Godot 4.6.3): headless for the main-thread times, lavapipe for
the rendered stills. The stage-4a head (d724c23) ran from a scratch copy of the project, the runs
alternating with this stage's. No phone figures.

**Window open, main thread.** Headless, on the buildings fixture's busy settlement, each window
opened nine times (`qa_stage4b_shots.gd --repeat=9`, `qa_stage4b_forest.gd --repeat=9`); the
figure is the median of opens 2–9 in ms inside the call, two runs each (ranges). The scripts wait
for the window scripts' warm compile after launch to finish first, as it does long before a
player's first tap. The forest's journal and reward reserve: eight more alternating pairs of
first opens.

| Window | Stage-4a head | Stage 4b | First open (head → 4b) |
|---|---|---|---|
| «Меню» (city) | 1.0–1.1 | 3.0 | 1.2–2.1 → 3.1–4.5 |
| «Меню» (world map) | 1.4–2.3 | 4.0 | 1.8–2.9 → 4.5–4.8 |
| «Аккаунт» | 2.7–3.0 | 2.8–3.2 | 3.3–4.0 → 4.3–5.1 |
| «Аккаунт» (a fresh device) | 2.2–3.4 | 2.8–2.9 | 4.9–5.4 → 5.7–6.2 |
| «Код подключения» | 0.2 | 0.2 | 0.2 → 0.2 |
| Confirmation | 1.2–1.4 | 1.3 | 1.3–1.6 → 2.2 |
| «Рынок» | 2.7 | 3.7–3.8 | 3.5 → 3.8–3.9 |
| «Экономика поселения» | 0.8–0.9 | 1.1–1.3 | 0.9–1.1 → 1.3–2.0 |
| «Цели поселения» | 1.9 | 0.9–1.0 | 1.9–2.7 → 1.1 |
| «Архив прежних зданий» | 1.8 | 0.4 | 1.9–2.0 → 0.7 |
| A creature (world) | 3.9–4.0 | 1.7–1.9 | 4.6–4.8 → 2.2 |
| Hunts | 0.8 | 1.2 | 0.8–1.2 → 1.2–1.5 |
| A settlement / a rival's | 1.1 / 1.2–1.4 | 1.2 / 1.2–1.3 | 1.2 / 1.5–1.6 → 1.5 / 1.1–1.4 |
| A free place | 0.8–0.9 | 0.8 | 1.0–1.1 → 0.7–1.8 |
| A march | 1.3–1.5 | 1.1 | 1.3–1.4 → 1.3–1.4 |
| Cities / directory / layers | 0.7 / 1.1 / 0.9 | 0.8 / 1.4–1.5 / 1.1 | 0.6 / 1.3–2.0 / 1.5 → 0.9–1.4 / 1.6 / 2.0–2.5 |
| «Армия и осада» | 1.7–1.8 | 2.2–3.7 | 2.2–2.4 → 2.8–3.8 |
| «Летопись сражений» | 0.8–0.9 | 0.9 | 1.7–1.9 → 1.8 |
| The ring | 0.9 | 0.8 | 0.8–1.0 → 1.0–3.5 |
| An upgrade (the new parts) | 2.7 | 2.6–3.4 | 5.2–6.9 → 4.4–4.8 |
| «Скоро» (a V building) | 1.7–1.9 | 1.8 | 2.7–3.0 → 2.9 |
| «Создать войско» (the helmet) | 3.8–7.5 | 4.0–4.1 | 4.9–6.3 → 6.4–6.8 |
| Forest journal | 8.9–11.0 | 9.0–9.4 | 16.3 → 18.1 (medians of 8 pairs) |
| Forest reward reserve | 3.4–4.1 | 3.7–4.0 | 4.9 → 4.9 (medians of 8 pairs) |
| Forest locked card / intro card | 0.3–0.5 / 0.1 | 0.4 / 0.1 | 0.4–0.7 / 0.1 → 0.4 / 0.1 |

Every window touched by this stage opens in about 4 ms or less on repeat except the forest journal
(about 9 ms, as before: sixty place cards of Labels). The richer ones cost a little more than
their plain lists: the menu (+2 ms: thirteen drawn tiles and the profile column instead of a
column of buttons), the world menu (+2 ms), the market (+1 ms), the army (+0.5–2 ms: the band and
larger cards). The objectives, the archive and the creature window got faster (cards instead of
row-and-label lists; the creature's portrait comes from a worker decode).
The journal's first open is 1.8 ms slower (median of eight pairs; repeat opens equal); a probe found
none of the new parts (the kit's script, the band, the textures, the italic face) above 0.1 ms,
so it is not one new part; it was not tracked further. `qa_panel_latency` (40 ms budget each):
see Tests.

Rendered (lavapipe, the first open during the stills, two stills runs, call only): account
4.4–4.5, the first-launch account 6.9–7.2, archive 1.1, army 4.0–5.0, cities 1.2–1.6, confirmation
2.9–3.0, directory 2.4–3.3, economy 1.9–2.3, creature 3.1–3.3, hunts 2.1, layers 2.7, march
1.9–2.5, menu 4.5–5.0, objectives 1.6–1.8, pairing 0.3, recruitment 7.7–13.8, chronicle 2.6, ring
3.2–3.3, settlement 1.8–1.9 / 2.0–2.4, «Скоро» 3.0–4.8, market 4.6–7.0, upgrade 4.3, world menu
3.8–6.5, free place 1.3–1.5 ms. Forest, head → 4b: journal 16.0 → 17.4–20.9, rewards 8.1 →
3.8–4.8, locked card 0.6 → 0.7–0.8, intro card 0.1 → 0.1–0.2 ms.

**Launch.**
- `main.tscn` load (the compile of every preloaded script), 8 alternating pairs: 977 ms median
  against 990 ms on the head. The three new window scripts and `kit_more.gd` are lazy views,
  outside it (decision 1).
- `qa_instant_start` (`launch_ms`, until the city is shown): first 6 and then 10 alternating
  pairs gave 1 432 against 1 375 ms and 1 543 against 1 460 ms (this stage against the head,
  medians), about 60–80 ms slower. The cause was the
  theme: it built the CheckButton switch icons, which took `kit_switch_on` / `_off` from the
  kit's worker decode during the launch, at the end of its queue, so the main thread waited for
  most of the kit's textures. The switch now takes its texture on its first draw
  (`UiKit.HalfTexture` holds a lookup). After the fix, 10 alternating pairs: 1 414 against
  1 406 ms (spreads 1 306–1 516 and 1 247–1 536), all 12 checks passing in every run.
- The first launch's «Аккаунт» (decision 11): compiling `kit_more.gd` and `v6_menu.gd` costs
  65–72 ms on the main thread here (three cold runs); in a rendered first launch their worker
  compile had finished three frames before the account opened, which it does in the same frame
  as on the head.

## Tests

Run on Godot 4.6.3, headless Linux, against the synthetic fixtures (the buildings fixture on
8792, the 1022 fixture, recorded forest states through a stub transport). No phone was used.

**New: `godot/tools/qa_stage4b.gd`** (60 checks, passed), against the buildings fixture:
- the menu: «Меню» opens with the three groups and the nine expected tiles of the
  settlement and «Сведения» groups; every tile
  is a Button at least 100 × 100 units; the objectives tile's badge equals the objectives ready to
  claim;
- the switches: both present, drawn at 64 × 34; «Звук» mutes and unmutes the master bus;
  «Меньше движения» reaches the ring; the economy tile opens «Экономика поселения» with its
  resource cards and income band;
- the objectives claim: after collecting, the current objective is ready; in «Цели поселения»
  only one claim button exists and it sits on the current quest card; the claim reaches the
  server (the objective is claimed), each reward resource reaches the stock (or the storage
  cap), the toast reads «Готово: награда получена…» in the good tone, and the card's ribbon reads
  «Получено»;
- toasts: a copy confirmation is good, a neutral notice info, a server error warn and calm
  («…недоступен… повторим…»), on the kit plate; the connection pill: hidden 3 s after a
  failure, shown after 10 s without an answer (the centre message untouched), gone at the next
  answer;
- the ring's unfold: `UNFOLD_SECONDS` ≤ 0.18; mid-unfold every medallion is a live Button at full
  scale with `MOUSE_FILTER_STOP` and its rect already at its slot (only the drawing moves); a tap
  injected during the unfold opens «Сведения»; every medallion is at rest after 250 ms; with less
  motion there is no unfold.

**Changed:**
- `qa_runtime` (in the windows commit): it looks for the menu's entries among the Buttons of the
  tile grids (`find_children`) instead of the menu's direct children; the same two entries are
  required.
- `qa_stage4b_shots.gd` and `qa_stage4b_forest.gd` (stills and timings, not tests) wait for the
  warm compile after launch before timing (see Measurements).

**Kept green** (the final run; the tests that open world windows ran again after the sweep's
chip-row fix, see the sweep):

| Test | Result |
|---|---|
| `qa_stage4b` | 60 checks (new) |
| `qa_building_actions` | 297 states, 2 984 checks |
| `qa_building_services` | 6 states, 42 checks |
| `qa_build_strip` | 15 cases, 697 checks |
| `qa_recruitment` | 56 checks (open 8.9 ms) |
| `qa_button_responsiveness` | 50 checks; touch round trips Меню 55, Армия 34, Строить 41, Отчёты 34 ms (it taps during the post-launch compile, as in stage 4a) |
| `qa_v6_panel_feedback` | 12 checks |
| `qa_stage4a` | 2 499 checks |
| `qa_speedups` | 18 checks |
| `qa_panel_latency` | 26 panels, 26 checks (40 ms budget each) |
| `qa_touch_buttons` | 11 checks |
| `qa_camera_hud` | 153 checks |
| `qa_action_ring` | 9 checks |
| `qa_reaction` | 100 same-frame reactions, no failures |
| `qa_troops06` | 122 checks |
| `qa_profile` | completes |
| `qa_runtime` | 21 checks |
| `qa_combat_1020` | 5 500 checks |
| `qa_build_menu` | 20 checks (its open 47–62 ms here, the head 47–51 ms in alternating runs; not a window of this stage) |
| `qa_legacy_build` | 22 checks |
| `qa_stability` (6), `qa_diagnostics` (14), `qa_city_works` (39), `qa_prewarm` (9) | pass |
| `qa_web_panels` | 37 checks, offline as the test intends |
| `qa_instant_start` | 12 checks |
| `qa_network` | 11 checks (a closed loopback port) |
| `qa_forest_flow` | 166 checks (the forest row clear of the 1022 navigation) |
| `qa_net_1022` | 48 checks |
| `qa_forest_v6` | 17 steps, 43 checks |
| `qa_forest_e2e` | 214 steps, 21 reloads, 966 checks (HUD «Продолжить», squad, mechanism, rewards) |
| `qa_march_refusal` (mode `refused`, the site realm) | 18 checks |

Every test above exits with code 0.

**Not green, and the same on the stage-4a head in this environment:**
- `qa_v6_account`: 16 checks, the same two failures on the head («supported login available»,
  «logout succeeds with supported V6 API»).
- `verify_playable_pack`: it stops at the siege ram's scene
  (`architecture-v6/units/SIEGE-RAM-01.tscn`, generated before export and git-ignored, absent
  from this checkout), on the head too. Its «account entry» check holds: a probe of the same
  start shows «Аккаунт» open when the scene is ready, on the head and here (decision 11).
- `qa_primary_account_screen`: asserts and then waits forever, on the head too.
- `qa_forest_v6`'s «guardian drawn with the creatures v2 model» failed three runs in a row earlier
  in this stage and passed the next three and the final run; turning off the stage's portrait warm
  did not change it. Stage 4a recorded the same flake on its head (an asynchronous model load
  timed against a frame count).
- The timing runs log 920 script errors per run, all from `landscape.gd` (`add_warrior` and
  `present_parade` meeting the siege ram's missing scene), the same count on the head.

## Consistency sweep

Every window of the stage was opened once more at the end, rendered
(`qa_stage4b_shots.gd`, `qa_stage4b_forest.gd` and the 2532×1170 menu on lavapipe: 40 windows
and HUD states, 16 minutes), nine times each headless in the timing runs, and once more by the
tests that open them. The final stills are the `after_*` set. Findings:
- **Errors:** none from the interface. The city runs log only `landscape.gd` meeting the siege
  ram's missing scene (as on the head); the forest runs log none.
- **One frame language:** every full window has the oak band with the display-face title, the
  eyebrow ribbon and the round bronze close; linen body; dark oak for the profile, army and
  objectives columns; the side windows of the map use the same band at their width. Buttons:
  gilded primary, linen tertiary, lapis for secondary actions (pairing, sale, a hunt's «Открыть»),
  forest green for a purchase, cranberry only where a step cannot be undone (sign out). The forest
  windows (intro, locked card, mechanism, journal, reserve) use the same rim and buttons.
- **One notice:** the city's toasts (a build, an error, «Действие выполнено»), the connection pill
  and the forest's toasts are the same carved plate with a tone medallion; the forest banner is
  the one enamel exception (an event, not a notice).
- **One switch:** the same 64 × 34 switch in the menu, the map layers and the forest journal.
- **Emblems:** the menu's, the map's and the account's tiles, the forest row's medallions and the
  world cards' chips draw from the same forged set.
- **Fixed in the sweep:** the world cards' chip row (`KitMore.ChipRow`) dropped a chip that did
  not fit its line, so the creature window never showed its distance («51 от города») after its
  three rewards. The row now wraps to a second line and takes the height it needs (`pills`,
  `fit`); open times unchanged (alternating runs with and without it: within 0.3 ms). The shot
  fixture's rival settlement stood on the player's own spot («0 от города»); it is placed apart.
  The world stills were rendered again, and `qa_stage4b`, `qa_button_responsiveness`,
  `qa_runtime`, `qa_panel_latency`, `qa_touch_buttons`, `qa_camera_hud`, `qa_action_ring`,
  `qa_net_1022` and `qa_march_refusal` were run again after it: all green, the same counts.
- **Left as found** (see below): in the building window's stills the oak band sits about 15 px to
  the right and its close button is cut by the screen edge, as in the before still; a layout probe
  of that window (headless and rendered) puts the close at 1300–1356 of 1366, so the cause in the
  stills was not found. The cities and free-place panels keep empty linen above their footer; the
  world menu's «Сведения» group starts below the fold (the window scrolls).

## Still below the reference

- **Icons.** The fifteen new emblems and the ring's glazed discs are painted procedurally like the
  rest of the kit: forged and legible at 50–70 units, but flatter than the reference's rendered,
  glossy icons, and several menu tiles share a family look (a key, a gauge, an «i»).
- **Menu tiles.** A linen plate with a medallion and a caption; the reference's tiles carry
  painted scenes and more depth. The world menu's third group starts below the fold (it
  scrolls).
- **«Скоро».** The silhouette in mist reads as a grey smudge beside the bright current building
  at 1366×630; a recognisable dark shape of the next level would be better, and it needs its own
  model or a better mask.
- **Army window.** No live 3D (decision 4): baked portraits on larger cards and a summary band. The
  reference's army screen stages its troops.
- **World cards.** No travel-time chip on the cards: the time comes only from the server's route
  quote in the march window, and the cards do not guess it. The distance is in map units («51 от
  города»), not a time. The cities and free-place panels leave empty linen between their actions
  and the footer.
- **Forest row.** The adventure row sits on the screen's bottom edge, lower than the city's
  medallion row beside it, and in compact mode the reward amounts are small (12 units, the
  caption 11).
  The forest's site cards are still text-heavy (quotes and testimony in lines).
- **Journal first open.** About 18 ms here (16 on the head), over one 60 Hz frame; repeat opens
  are 9 ms. The sixty place cards are Labels; a drawn card per place would cut it.
- **Toasts and banners.** One carved plate with a tone medallion and an 80 ms ease; the reference's
  notices are larger, animated banners with art.
- **Building window stills.** The oak band sits about 15 px right and the close button is cut by
  the screen edge (as on the stage-3 and 4a heads); not explained by its layout (see the sweep).
- **Not measured on a phone.** Every figure here is from this container (headless and lavapipe).
