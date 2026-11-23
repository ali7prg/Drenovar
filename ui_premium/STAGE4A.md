# DRENOVAR premium UI — stage 4a: speed-ups, the city HUD, the army, services and reports

Stage 4a rebuilds what the player touches between two constructions:
- the queues and speed-up window (`v6_panels.queues()` and `speedups()`), one window now;
- the city HUD: the resource row, the profile medallion, the bottom medallions with their
  badges, the action ring over a building and the timers over busy buildings;
- the army, the march formation and the hunt party window («Создать войско»);
- the academy (B15) and the lazaret (B16);
- the chronicle of battles and a single report.

The look follows `ART_DIRECTION.md`: carved oak and bronze, linen, enamel, gold. The reference game
was studied for composition only (a rail of queues at the left, a timer band, a quick-use row,
items by duration). Nothing from it is in the repository: no frames, crops, traces or sheets. The
side-by-side sheets stay in the session scratchpad.

Out of scope, left as they were (stage 4b): the menu, account and profile windows, trade, economy,
objectives, the archive, world-map windows, encounters and hunts, the forest panels, toasts.

## What the player sees

### Queues and speed-ups (`src/v6_queues.gd`)

One window, opened as «Очереди поселения» (HUD, city actions, the ring's «Очередь») or as
«Ускорить работу» on one order (the ring's «Ускорить», recruitment, a queue lane).

- **Left: the rail of every queue** on dark oak, in sections with a forged emblem on a band:
  - Строительство: one lane per builder of the town hall («Строитель 1», «Строитель 2»), busy
    ones with the building's diorama;
  - Войска: barracks, range, stables, siege workshop, each with the portrait of the unit in
    training;
  - Исследования (academy) and Лечение (lazaret);
  - Походы: the parties on the march.

  Each lane is one drawn node: a medallion with the portrait or emblem, the name, what runs
  («Копейщик × 30»), a gold bar with the ticking time, or «Свободно» on a free lane, and a «+N»
  badge when more orders wait. The selected lane glows; the rail scrolls by itself so the
  selected lane and its section band stay in view. It scrolls with the finger independently of
  the right side (`TouchScroll`, group `panel_scroll`); buttons in a list that scrolls act on
  release, so a drag never fires a lane.
- **Right: the timer band** on an oak strip: what runs, an hourglass, the time left, a thin bar.
  When the job ends the band pulses and reads «Закончено».
- **«Быстрое использование».** The owned items that finish the job with the least waste, as a
  warm row with the items stacked as tiles and «Применить». The plan:
  - minimise the total that still covers the time left, then the number of items;
  - if everything owned falls short, use all of it (the most it can shorten);
  - apply longest first; only the last item can outlast the job.

  «Применить» sends the uses one by one through the real API (`{"kind":"speedup", "queue",
  "item", "orderId", "expectedEndsAt", "confirmUnused"}`), each with the order's current end, so
  a repeat is idempotent and a changed order is refused, not double-spent. Only the last use can
  carry `confirmUnused`. The button reads «Применяем 2 из 3…», the bar jumps after each use, and
  the counts go down. Nothing is bought; only owned items are offered.
- **Item rows.** Painted items in five tiers by duration (I ≤ 1 min, II ≤ 5 min, III ≤ 15 min,
  IV ≤ 3 h, V longer), from the server catalogue (construction-1…4 and training-1…4 are 1, 5, 15
  and 60 minutes; the old client tier table that called training-4 «30 мин» is gone). Each row:
  the item tile with its duration on a plate, the name, «Сокращает на 15 мин», «В наличии: N»
  and «Использовать». A row with none is dimmed. An item longer than the time left asks a
  second tap («Остаток 4 мин пропадёт…»).
- **A free lane** offers its work instead: «Строить», «Обучить», «Исследовать», «Лечить».
- **An order that has not started** (queued behind another) shows where it stands. A march shows
  its route state and «Отозвать».
- **Footer.** The resources held for the job and «Отменить работу» (the server's cancel, then the
  window refreshes in place).
- **The way back.** Opened from recruitment, «Вернуться к обучению» returns to it; a finished
  job returns there by itself after «Закончено».

### City HUD

- **Resource row.** Live short values with their icons. The counters stay plate-less (the owner's
  rule in `ART_DIRECTION.md`, protected by `qa_camera_hud`); one translucent oak ribbon with a
  bronze foot line runs behind the whole row, so the numbers read over snow and grass. A tap
  opens the economy, as before.
- **Profile medallion.** A gold medallion with a helm, the settlement's name in gold and the hall
  level on an oak pill («Ратуша XI»).
- **Bottom medallions.** Город / Карта, Строить, Армия, Отчёты, Меню: bronze discs with forged
  emblems and outlined captions. Enamel badges:
  - a red count of unread reports on «Отчёты» («9+» past nine), cleared when the chronicle opens
    (the time of the newest report seen is kept in `user://hud.cfg`);
  - a green count of free builders on «Строить».

  Each medallion is one drawn node that redraws only when its state changes.
- **Action ring.** Bronze medallions with forged emblems around the building, the main action on
  a gold disc, captions under them and the building's name and level on an oak plate. They pop in
  one after the other. The actions:
  - «Сведения»;
  - «Улучшить» below the open level; at the open level V (`main.MAX_OPEN_BUILDING_LEVEL`) a dim
    «Скоро» under a small ribbon instead (it opens the building window, which explains);
  - the building's work: «Обучение», «Исследования», «Лечение», «Работы здания»;
  - over a busy building, «Ускорить» with the time left ticking on a plate (construction,
    training, siege), or «Очередь» for work no item speeds up (research, healing);
  - «Рынок», «Оборона», «Производство» where they apply, and «Переместить».
- **Timers over busy buildings.** An oak pill with an hourglass, the time in gold and a filling
  line, over every building with a running V6 job (construction, training, research, healing),
  not only the one under construction.

### Army and march (`src/v6_army.gd`)

- **«Армия и осада».** A dark oak column at the left: the army's capacity bar («191 / 14K»), the
  march limit, parties at once, beds, the wounded, «Лазарет» and «Показать плац в городе». At the
  right: the troops at home as tier cards with their portraits, counts and names (a card opens its
  training building), the rams, the parties on the march with their timers and «Отозвать» /
  «Отступить», and the targets.
- **«Поход: …».** The target on the oak column with the march capacity filling as troops are
  chosen; «Все доступные» and «Очистить»; a row per unit with its portrait, a slider and a field;
  «Рассчитать поход» asks the server's preview, then «Отправить отряд» (arrival, return, the
  party's portraits, «Отправить»).
- **«Создать войско»** (the hunt party, `main.compose_march`): restyled in place — «Состав отряда»
  header, tier-tinted portraits, kit rows, names in the label face, round «−» / «+», styled «Все
  доступные», «Обучить ещё воинов», «Очистить». Its structure is unchanged: the route tests
  (`qa_march_refusal`, `qa_web_panels`) drive it by its nodes.

### Academy and lazaret (`src/v6_services.gd`)

- **Academy (B15).** One drawn card per family: the family's emblem, its name, the rank as eleven
  lozenges (gold up to the current rank, the next one outlined) over the action, the next effect
  in green («Скорость строительства: +0% → +2.0%»), the cost with icons (red where short) and the
  time with the academy's speed. The action is «Исследовать»; «Нужна академия X» when the rank
  needs a higher academy (ranks are the server's: `required_academy` = rank, capped by
  `research_rank_cap`); a running family shows its bar and «Очередь»; «Академия занята другой
  ветвью» while another family runs; «ветвь изучена до конца» at the top.
- **Lazaret (B16).** Chips for the wounded, the beds and the batch; the running healing as a card
  with its bar; a row per wounded unit: its portrait on a tile of its tier, name, count, slider
  and field (filled up to the batch); the cost strip (food 5, coins 2 per warrior), the time
  (10 s per warrior with the healing bonus) and «Лечить».

### Reports (`src/report_row.gd`, `main.show_reports` / `show_report`)

- **«Летопись сражений».** One drawn row per report, newest first: the outcome medallion, an
  enamel badge (Победа green, Поражение red, Разведка blue), the opponent and level, how long ago
  («4 мин назад», «вчера»), the losses («62 в строю, 6 ранены, 2 погибли») and the spoils with
  resource icons. Unread reports carry a red dot.
- **A report.** The outcome emblem on a medallion, «Победа» / «Отряд потерпел поражение», three
  figure tiles (в строю, ранены, погибли), the spoils right under them on oak plates with icons
  («Еда +1 200», the label text the reward tests read), then a table of every unit with its
  portrait and its three counts, the wall bonus of a city attack, and «Продолжить».

## Decisions

1. **One queues window.** «Очереди» and «Ускорить» were two lists; now the speed-up is the queues
   window focused on one order. Every queue is one tap away, and the rail answers «what is idle?»
   at a glance (the free lanes read «Свободно»).
2. **Quick use through the real API, one item at a time.** The server has no batch use. Each use
   carries the order's current end (`expectedEndsAt`), so a repeat after a lost answer is refused
   instead of spending twice, and the window stops at the first refusal. Only the last item may
   outlast the job, so only it carries `confirmUnused`. Nothing is bought: only owned items.
3. **Least waste, then fewest items.** A bounded search (four steps below the greedy count per
   item size) matches an exhaustive search on 400 random inventories in `qa_stage4a`, and an
   independent DP on larger ones during development. It costs microseconds.
4. **The server catalogue decides the tiers.** Items come from `speed_catalog()`; the tier
   colour follows the duration.
5. **Plate-less counters stay.** The owner's rule keeps every counter's own stylebox transparent;
   the one ribbon behind the row is drawn by the row, so `qa_camera_hud` still finds no card
   behind any counter.
6. **«Скоро» on the ring instead of hiding «Улучшить».** At V the player sees why the upgrade is
   not there. `MAX_OPEN_BUILDING_LEVEL` is unchanged and still the only switch.
7. **Badges are local and cheap.** Unread reports compare `finishedAt` with the newest report seen
   (`user://hud.cfg`); free builders are the town hall's builders minus running constructions.
   They are computed in `refresh_hud`, never per frame.
8. **Drawn nodes for lists.** Lanes, item rows, research cards, report rows, the lazaret row heads
   and the ring medallions are each one node with `_draw` and cached text lines, so a window of
   twenty rows does not lay out sixty labels. Buttons stay real `Button`s (tests, screen readers,
   touch feedback).
9. **The hunt party window keeps its structure.** Its route logic is tested node by node; only
   its styles changed.
10. **The window scripts compile after launch.** As preloads, the four new window scripts (and
    the recruitment window's, which they sit beside) were compiled with `main.tscn` and made
    every launch about 200 ms longer here. `v6_panels` now makes each window on first use, and
    two frames after the launch screen starts to fade `main.warm_views_soon()` has a worker
    thread compile them and the chronicle's row, the way the kit textures and portraits are
    decoded. The fade (0.28 s; it takes no touches) lasts about as long as the compile does
    here; a window opened before it is done waits for its script once. Started any earlier, beside the city build, the
    compile made the launch about 100 ms longer again; started in the fade's first frame, it
    stalled that frame by about 25 ms (the main thread's own warm-ups wait for the script cache
    while a compile runs). On quit, a compile still running is waited for.
11. **Nothing painted per frame that can be painted once.** The plates' level badge is a texture
    painted on a worker thread (the pool task is waited for, so nothing is left for exit), and the
    plates skip whatever sits under the HUD or the open ring.

## Files

| File | What |
|---|---|
| `src/v6_queues.gd` (new) | Queues / speed-ups window, least waste, lanes, timer band, item rows |
| `src/v6_services.gd` (new) | Academy and lazaret |
| `src/v6_army.gd` (new) | «Армия и осада», «Поход», «Отправить отряд» |
| `src/report_row.gd` (new) | A row of the chronicle |
| `src/v6_panels.gd` | Routes queues, speed-ups, services, army and formation to the views (made on first use, compiled after launch); the new ring |
| `src/main.gd` | HUD badges and profile, resource ribbon, reports, report, compose march, legacy speed-up art |
| `src/hud_action.gd` | Medallions with emblems, badges, the profile medallion |
| `src/action_ring.gd` | RingButton medallions, «Скоро», the time on «Ускорить», pop-in |
| `src/building_plates.gd` | Timer pills over every busy V6 building; cached names, a painted level badge, clear of the HUD and the ring |
| `src/touch_scroll.gd` | A second scrolling list (the rail) beside the window's body |
| `src/ui_kit.gd` | The new textures |
| `art/ui/premium/paint_kit.py` | Painter of the items and the emblems |
| `assets/ui/premium/kit_item_*.res`, `kit_emb_*.res` | 10 items, 15 emblems |
| `qa_stage4a_shots.gd` | The stills of this stage |
| `tools/qa_stage4a.gd` (new) | Least waste, rail, badges, ring |

## Art

New painted textures, baked like the stage-1 kit (`tools/bake_ui_kit.gd`), decoded on worker
threads at launch with the rest of the kit:
- 10 speed-up items, five tiers each for construction and training: a bronze hourglass with a
  forge (construction) or an arrow (training) on a tier-coloured enamel tile, 17–19 KB each;
- 15 forged emblems for the HUD, the ring, the rail and the reports (book, heal, sheaf, sword,
  shield, march, map, scroll, menu, info, up, speed, move, trade, helm), 2–13 KB each.

All 25 together: 301 011 bytes.

## Stills and polish passes

Stills in `ui_premium/shots/stage4a/` (JPEG, q 85): `before_*` from the stage-3 head (84665f2),
`after_*` from this stage, at 1366×630, and one pair rendered for 2532×1170 (`*_big_speedups`;
the virtual X screen gives 2532×1167, as in stages 2 and 3).

Side-by-side sheets with the reference frames (queues, speed-ups, quick use, the city and the
ring) were made in the session scratchpad only.

**Pass 1** (after the first stills of the queues window, the HUD and the ring):
- the rail sat on the window's edge: it got its own dark oak backdrop and an inset, and the
  selected lane now pulls its section band into view with it;
- each item tile got its duration on a small plate under it (the reference's rows are told
  apart by the tile colour alone; ours say «15 мин» as well);
- «Быстрое использование» was one more row: it became a warm gold plate with the planned items
  stacked as tiles, so the main action of the window is the first thing the eye meets;
- the ring medallions were too close and too small for a thumb: 70 px, 112 px from the building,
  47° apart, captions outlined; the profile medallion got room for long settlement names.

**Pass 2** (after the stills of every window):
- academy: the eleven rank lozenges ran into long family names («Организация строительства»);
  they now sit over the action button, clear of the name;
- army: the cards had counts but no names; each card has its unit's name under it;
- report: the per-unit table pushed the spoils below the fold; the spoils come right after the
  figures, and the table has a header row (в строю, ранены, погибли);
- lazaret and formation: the portrait, name and count of a unit are one drawn head with a larger
  portrait on its tier's enamel (tier colours match the army cards and the recruitment window);
  this also halved the nodes per row;
- ring: «Скоро» was said twice (a ribbon on the medallion and the caption); the medallion now
  carries a small bronze padlock, the caption says «Скоро»;
- the building's own name plate no longer shows through its open ring (the ring's plate carries
  the name and level);
- name plates of buildings behind the bottom medallions and the resource row are skipped, so no
  «11» peeks between «Строить» and «Армия»;
- «Быстрое использование» with nothing owned was still the warm inviting plate; it is a plain row
  saying where the items come from;
- the building plates were redrawn every frame with four antialiased shapes per level badge and
  two text shapings per name: the badge is now one texture painted once on a worker thread, names
  and levels are cached lines (see Measurements).

## Measurements

All on this container (4 cores, Godot 4.6.3): headless for the main-thread times, lavapipe for
the rendered stills. The stage-3 head (84665f2) ran beside it from a scratch copy, the runs
alternating. No phone figures.

**Window open, main thread.** Headless, each window opened nine times on the fixture's busy
settlement; the figure is the median of opens 2–9 (ms inside the call; the next frame adds the
same ~7 ms of headless pacing to every window). Ranges over four runs (stage 4a) and two (head):

| Window | Stage-3 head | Stage 4a | First open (head → 4a) |
|---|---|---|---|
| «Очереди поселения» | 5.5–5.9 | 4.0–5.0 | 9.9–11.2 → 6.9–12.9 |
| «Ускорить работу» (training) | 4.7–4.8 | 3.3–4.5 | 4.3–4.9 → 3.5–5.2 |
| Quick use (an upgrade) | 4.2–4.6 | 4.0–5.5 (one run 8.6) | 5.4–6.2 → 3.1–4.0 |
| «Армия и осада» | 2.1–2.2 | 1.5–3.1 | 3.8–3.9 → 1.7–2.3 |
| «Поход» (formation) | 2.0–2.3 | 2.1–2.4 | 4.4–4.7 → 3.3–6.4 |
| «Создать войско» | 10.7–14.5 | 9.7–19.2 (median 10.9) | 24–29 → 18–23 |
| Academy (B15) | 7.4–8.1 | 1.9–2.5 | 6.9–7.7 → 2.1–4.4 |
| Lazaret (B16) | 1.3–1.7 | 3.0–3.1 | 1.5–1.6 → 3.0–6.4 |
| «Летопись сражений» | 1.2–1.6 | 1.1–2.5 | 1.8 → 1.3–2.0 |
| A report | 4.0–4.7 | 3.5–4.9 | 16.6–17.5 → 9.1–16.8 |

Rendered (lavapipe, first open during the stills, call only), head → 4a: queues 9.9 → 7.8,
speed-up 10.5 → 8.0, quick use 7.6 → 5.0, army 6.0 → 4.6, formation 5.8 → 6.1, compose
37.5 → 27.3, academy 8.5 → 3.4, lazaret 2.3 → 3.4, chronicle 1.5 → 1.6, report 276 → 8.0, the
ring at V 60 → 1.1.

Against stages 1–3 (build window 5.3–5.6 ms and inspector 5–6 ms in stage 1, strip 3.9 ms and
building window 4.5–6.8 ms in stage 3, recruitment 7.2–10.7 ms): every stage-4a window opens at
about 5 ms or less on repeat, except «Создать войско» (restyled only, and faster than before).
The lazaret is the one window slower than its plain list, by about 1.5 ms: the drawn unit heads
replaced a tile and two labels, and the row still holds the slider and field.
`qa_panel_latency` (26 panels, 40 ms budget each): all inside.

**HUD per frame.** Headless, 240 frames over the busy city (zoom 64; an upgrade, two trainings,
research and healing running):
- the building plates' `_draw`: 486–529 µs median (head: 644–670 µs, and the head draws no job
  timers); with the ring open 491–494 µs (head 645–657 µs);
- every other HUD control: 0 redraws per frame at rest; 0.01 per frame with the ring open (its
  «Ускорить» time ticks once a second);
- `refresh_hud` (on a state change, not per frame): 0.13 ms (head 0.09 ms; the badges);
- the level badge is painted once on a worker thread (about 1.5 ms there).

Before the plates were reworked (pass 2), lavapipe measured 3.52 ms of canvas CPU per frame with
the plates and 3.29 ms without them; the plates now cost about a fifth less than on the head.

**Launch.** The four window scripts as preloads made `main.tscn` load 1 190–1 220 ms against
985–997 ms on the head (the extra was their compile). With decision 10:
- `main.tscn` load, 10 alternating pairs: 995.5 ms median against 994.5 ms;
- `qa_instant_start` (`launch_ms`, until the city is shown), 8 alternating pairs, twice:
  1 500 against 1 458 ms and 1 479 against 1 455 ms (spreads 1 259–1 754 here, 1 244–1 526 on the head); a
  split probe over 7 pairs: 1 496 against 1 493 ms. Within the run-to-run spread;
- the first frame after launch: 58–71 ms against 45–86 ms on the head, and no other frame over
  33 ms in the next 600 ms;
- the window scripts are compiled by about 280 ms after the launch screen starts its 0.28 s
  fade.

**Touch round trips** (`qa_button_responsiveness`, touch-down to the window up). Headless has no
launch fade, so the test taps about 100 ms after launch, while the scripts are still compiling:
Меню 42–61 ms (head 30–32), Армия 59–147 ms (head 34), Строить 42–61 ms (head 56–61), Отчёты 34 ms
(34). Tapping once they are compiled (a scratch copy of the test that waits for them): 34, 34,
37–41 and 34 ms. On a device the fade, which takes no touches, covers that time.

## Tests

Run on Godot 4.6.3, headless Linux, against the synthetic fixtures (the buildings fixture on
8792, the 1022 fixture, the local test realm). No phone was used.

**New: `godot/tools/qa_stage4a.gd`** (2 499 checks, passed):
- `least_waste` against an exhaustive search on 400 random inventories of four item sizes
  (0–6 of each, 1 s to 2.5 h left): the same total and item count every time; the sequence is
  one use per item, longest first; a worked case (1 000 s with 60/300/900/3600-second items →
  900 + 60 + 60) and a short inventory (all of it);
- on the fixture, quick use on an upgrade with 1 000 s left: the live plan equals the exhaustive
  one (construction-3 + construction-2, 1 200 s), «Применить» runs, and the server's inventory
  goes down by exactly the planned items; the upgrade is finished;
- the queue rail: every lane (8 on the fixture) selects on a press, its lane glows, the band takes
  its title; a free lane offers its work, a running construction or training offers quick use;
- HUD badges: free builders (green) match the town hall; three unread reports read «3» (red); the
  chronicle lists them newest first with their spoils and clears the badge; a later report reads
  «1»; more than nine read «9+»; a report opens with its unit table;
- the ring: at V «Сведения» and a dim «Скоро», no «Улучшить»; below V «Улучшить» on the gold
  disc and no speed-up when idle; over a busy barracks «Ускорить» with a time in the future,
  which opens «Ускорить работу» on that barracks' order.

**Changed:**
- `qa_building_services`: it looks for the service window's main action by name
  (`ServiceAction`) first, then falls back to the first button, because the academy and the
  lazaret are now cards and rows with their own buttons.
- `qa_v6_panel_feedback` (in the queues commit): its stand-in for `main.gd` gained
  `modal_tools`, `modal_hero`, `speed_catalog()` and `command(order, after)` with a callback, which
  the queues window uses.

**Kept green:**

| Test | Result |
|---|---|
| `qa_building_actions` | 297 states, 2 984 checks |
| `qa_building_services` | 6 states, 42 checks |
| `qa_build_strip` | 15 cases, 697 checks |
| `qa_recruitment` | 56 checks (open 7.8 ms) |
| `qa_button_responsiveness` | 50 checks; round trips under Measurements (it taps during the post-launch compile) |
| `qa_v6_panel_feedback` | 12 checks |
| `qa_speedups` | 18 checks (the legacy texts are unchanged) |
| `qa_panel_latency` | 26 panels, 26 checks |
| `qa_touch_buttons` | 11 checks |
| `qa_web_panels` | 37 checks, offline as the test intends (it opens «Создать войско») |
| `qa_instant_start` | 12 checks |
| `qa_camera_hud` | 153 checks (counters still plate-less, no overlap) |
| `qa_action_ring` | 9 checks |
| `qa_reaction` | 100 same-frame reactions, no failures |
| `qa_troops06` | 122 checks |
| `qa_profile` | completes |
| `qa_runtime` | 21 checks |
| `qa_combat_1020` | 5 500 checks |
| `qa_net_1022` | 48 checks |
| `qa_forest_v6` | 43 checks (its guardian check failed in some earlier runs here, on the head too) |
| `qa_build_menu` | 20 checks |
| `qa_legacy_build` | 22 checks |
| `qa_stability`, `qa_diagnostics` (14), `qa_city_works` (39), `qa_prewarm` (9) | pass |
| `qa_march_refusal` (mode `refused`) | 18 checks, on the restyled «Создать войско» |

Every test above exits with code 0. (Pass 2 first left the badge's worker task unwaited, and
most tests then aborted at exit with a corrupted heap; the task is now waited for.)

**Not green, and the same on the stage-3 head (84665f2) in this environment:**
- `qa_battle_rewards`: the city battle passes (its popup shows «Еда +N», «Опыт +N», «Когти +N»
  in the restyled report); the world battle's six checks fail at «Result interrupted an open panel
  or hid the notice». The baseline fails the same six with both realm backends.
- `qa_march_refusal` with the v92 checkout as the realm backend: its fixture check «Tenerys I
  stands next to the building» fails on the baseline too; with the site backend it passes (above).
- `qa_web_panels` pointed at the 8792 fixture (instead of offline): 47 checks, 7 failures, as on
  the baseline. Its training commands also enter the fixture's request history, after which
  `qa_building_services` reports «legacy commands reached server» until the fixture restarts.

**Not run:** `qa_server_speedups` needs the `v92-speedups-v2` patch on a copy of the server; the
legacy speed-up texts it reads are unchanged (`qa_speedups` covers them client-side).

## Still below the reference

- **Items.** The reference offers eleven durations per queue with counts in the hundreds and a
  «buy and use» path; the server catalogue here has four per queue (1, 5, 15, 60 min) and the
  window never buys. The painted items are flat enamel tiles with an hourglass; the reference's
  are rendered objects with more depth.
- **Rail density.** The reference fits six or seven queues in the rail; ours shows four or five
  lanes at 1366×630 (78 px lanes, finger-sized). On an iPhone 12 in landscape it is about four.
- **Emblems.** Fifteen new emblems, but research families share them (a book, a sheaf, a sword,
  a shield…); the reference has a distinct icon per technology. At 70 px on the ring the
  emblems read, at 40 px (rail bands) they soften.
- **Ring.** Bronze medallions with captions; the reference's round icons are glossier and carry
  no captions. The ring's pop-in is a scale and fade, not the reference's springy unfold.
- **Timers over buildings** are flat pills over the 3D city; the reference floats icon bubbles
  (an anvil, a shield) with their own small animation.
- **HUD.** No event banners, chat, power figure or quest tracker (not in this game yet). The
  counters stay plate-less by the owner's rule, so the top bar is lighter than the reference's.
- **Army.** No live 3D unit in the army window (the recruitment window has it); the cards reuse the
  portraits. No troop power or upkeep panel.
- **Academy.** A list of family cards, not a tree with links between ranks.
- **Reports.** No battle replay, no mail tabs (battles / scouting / system), no hero section; items
  won show in the single report, not in the list row.
- **Lazaret.** No «heal all» shortcut beyond the slider defaults, no beds bar.
- **Open time.** The lazaret opens about 1.5 ms slower than the plain list it replaces (3.0 ms
  against 1.3–1.7 ms); «Создать войско» still takes about 10 ms. A tap in the first ~0.3 s after
  the launch screen starts to fade (only possible headless, where there is no fade) waits for the
  window scripts' compile: up to 147 ms for «Армия» in `qa_button_responsiveness`.
- **No phone.** Every figure is from headless Linux or lavapipe; nothing was measured on an
  iPhone.
