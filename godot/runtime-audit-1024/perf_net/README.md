# Build 1024, stage 5: optimisation, network, iPhone — evidence

"before" is commit abb2494e (a git worktree with its own user dir), "after" is this commit's tree. All runs
were made on the Linux QA container: 4 cores, the Godot 4.6.3 editor binary, headless (CPU only, no GPU).
The game talked only to LOCAL copies of the V6 Worker bundle, behind a test harness on 127.0.0.1. The harness
is the 1022/1023 one plus a chaos layer and is kept outside the repository. Production, staging and the
Cloudflare API were never contacted. Nothing here is an iPhone measurement. The iPhone checklist is in
ARCHITECTURE-V2.md («Build 1024: оптимизация, сеть, iPhone»).

| File | What |
|---|---|
| `chaos_before.json/.log`, `chaos_after.json/.log` | `qa_net_1024.gd`: 11 phases, about 17 min each, both builds side by side |
| `profile_before.json`, `profile_after.json` | `profile_1024.gd`: frame intervals of 16 scenes and 5 window openings |
| `memory_before.json`, `memory_after.json` | `tools/estimate_ios_memory.py`: what an iPhone loads, by asset group |
| `touch_after.json` | touch targets of the HUD, the menu, «Звук и музыка» and the construction strip |

## 1. Network chaos (`qa_net_1024.gd`)

Every phase runs in the same game scene, with polling and orders running as a player sees them:

| phase | duration | conditions |
|---|---|---|
| idle | 60 s | untouched for less than 90 s |
| rest | 60 s | untouched for more than 90 s |
| active | 60 s | an order every 5 s |
| mobile | 110 s | 300–800 ms added round trip; 3 % of answers one retransmission late |
| resets | 110 s | 8 % of connections reset before the answer, 8 % after it |
| errors | 94 s | 12 % 503, 8 % 429, 5 % 524 after the work was done |
| stalls | 150 s | 15 % of requests stall for 5–30 s |
| handoffs | 163 s | every 15 s every open connection goes silent; new ones work |
| background | 3 × 20 s | in the background while a poll hangs on a dead flow |
| outage | 35 s | the port refuses connections |
| restart | one cycle | every answer of an applied order is lost; the app is closed and opened; the same order is given again |

Every order is checked against the harness ledger by its Idempotency-Key. Result: before 4 failures, after 0
(25 checks). The "hint" is the new small «Связь…» notice; the build before had no such notice.

| phase | build | alarms | hint episodes / ms | alarm text | alarm after | time to the next 200/304 | polls 200+304 | poll KB/min raw / gzip |
|---|---|---|---|---|---|---|---|---|
| active | before | 0 | 0 / 0 ms | — | — | — | 11+4 (0 err) | 183.4 / 42.7 |
| active | after | 0 | 0 / 0 ms | — | — | — | 13+2 (0 err) | 214.4 / 50.2 |
| background | before | 0 | 0 / 0 ms | — | — | max 2 (p50 1) | 2+7 (3 err) | 27.6 / 6.0 |
| background | after | 0 | 0 / 0 ms | — | — | max 1 (p50 1) | 2+6 (3 err) | 27.6 / 6.0 |
| errors | before | 0 | 0 / 0 ms | — | — | — | 9+0 (5 err) | 166.0 / 36.2 |
| errors | after | 0 | 3 / 3153 ms | — | — | — | 8+0 (7 err) | 165.8 / 36.1 |
| handoffs | before | 0 | 0 / 0 ms | — | — | max 6212 (p50 5972) | 6+13 (6 err) | 68.4 / 15.0 |
| handoffs | after | 0 | 0 / 0 ms | — | — | max 6507 (p50 6249) | 6+13 (6 err) | 68.4 / 14.9 |
| idle | before | 0 | 0 / 0 ms | — | — | — | 3+12 (0 err) | 42.5 / 10.5 |
| idle | after | 0 | 0 / 0 ms | — | — | — | 3+12 (0 err) | 42.5 / 10.6 |
| mobile | before | 0 | 0 / 0 ms | — | — | — | 22+0 (1 err) | 270.6 / 58.9 |
| mobile | after | 0 | 0 / 0 ms | — | — | — | 23+0 (0 err) | 282.9 / 61.6 |
| outage | before | 1 | 0 / 0 ms | Нет связи · повторяем | 9778 | 310 | 0+0 (0 err) | 0.0 / 0.0 |
| outage | after | 1 | 1 / 11847 ms | Нет связи · повторяем | 15803 | 303 | 1+0 (0 err) | 26.7 / 5.8 |
| resets | before | 0 | 0 / 0 ms | — | — | — | 15+0 (1 err) | 277.0 / 60.1 |
| resets | after | 0 | 0 / 0 ms | — | — | — | 16+0 (0 err) | 295.5 / 64.3 |
| rest | before | 0 | 0 / 0 ms | — | — | — | 2+13 (0 err) | 28.4 / 7.1 |
| rest | after | 0 | 0 / 0 ms | — | — | — | 2+5 (0 err) | 28.4 / 7.1 |
| restart | before | 0 | 0 / 0 ms | — | — | — | 2+0 (0 err) | 433.4 / 92.9 |
| restart | after | 0 | 4 / 1883 ms | — | — | — | 5+2 (0 err) | 227.6 / 48.9 |
| stalls | before | 1 | 0 / 0 ms | Нет связи · повторяем | — | — | 16+7 (0 err) | 197.0 / 42.9 |
| stalls | after | 0 | 1 / 5161 ms | — | — | — | 18+6 (0 err) | 221.7 / 48.4 |

Orders across all phases (harness ledger):

| | before | after |
|---|---|---|
| orders | 79 | 83 |
| applied | 79 | 83 |
| confirmed | 78 | 83 |
| lost | 0 | 0 |
| doubled | 0 | 0 |
| max_keys_per_order | 2 | 1 |
| unconfirmed_but_applied | 1 | 0 |
| attempts | 95 | 103 |
| false_outage.episodes_while_up | 1 | 0 |
| false_outage.alarm_ms_while_up | 34 | 0 |
| false_outage.rate | 0.0001 | 0.0 |
| false_outage.up_ms | 663600 | 683400 |

What changed in the numbers:

- **False «Нет связи».** Before: one episode while the network was up (a server stall read as a lost
  network). After: none in 683 s of up-time.
  - A slow server now shows «Связь…» (small, dim) and, after 20 s, «Сервер не отвечает · повторяем».
  - «Нет связи · повторяем» appears only when the network itself has also been silent for 10 s.
- **A real 35 s outage.**
  - Before: the alarm after 9.8 s, with no earlier hint.
  - After: the hint after 4.0 s, the alarm after 15.8 s (20 s since the last answer).
  - Both builds were back within 0.3 s once the port answered.
- **Restart with the answer lost.**
  - Before: a new Idempotency-Key after the restart, so one order had 2 keys. The server refused the repeat
    as a second order («Очередь заполнена»).
  - After: the same key, 1 per order; the server replays the stored answer.
  - Orders applied but never confirmed: before 1, after 0. Lost 0 and doubled 0 in both builds.
- **Handoffs.** The next 200/304 came after 5.4–6.5 s in both builds (one poll interval plus the 3.5 s
  dead-flow hedge). There was never an alarm.
- **Polling.**
  - Left untouched for more than 90 s with nothing running: 7 instead of 15 requests a minute. The bytes are
    the same, because the 200s with the full state dominate at about 14 KB raw each (see the server
    proposals).
  - Active play: 183 vs 214 KB/min raw (43 vs 50 KB gzip). The after run applied more orders (83 vs 79), so
    more polls carried a new state.
- **Frames during the chaos.** No frame took over 33 ms in any phase, except at the boot of the restart phase
  and in the first seconds of idle (launch work, section 2).

The net suites were re-run on the after tree, and all pass:

| suite | checks |
|---|---|
| qa_api_pool | 58/58 |
| qa_idempotency | 7/7 |
| qa_network | 14/14 |
| qa_stability | 6/6 |
| qa_server_clock | 3/3 |
| qa_session_store | 11/11 |
| qa_speedups | 18/18 |
| qa_net_1022 | 48/48 |
| qa_http_304 | 15/15 |
| qa_net_1023 | 16/16 |

## 2. Frame times (`profile_1024.gd`, headless)

Each scene ran for 300 frames, with the camera drifting and the game's own loop and polling running. Both
builds ran at once on one machine.

Headless frames are paced at about 6.9 ms, the engine's idle floor. So the median says little; p99, max and
frames over 33 ms are the signal. "CPU" is the engine's process + physics time monitor. It is refreshed about
once a second, so its p99 covers only a handful of samples.

| scene | build | median | p95 | p99 | max | >33 ms | CPU median / p99 / max | nodes | static MB | townsfolk |
|---|---|---|---|---|---|---|---|---|---|---|
| city_hall1_default | before | 6.9 | 7.3 | 8.8 | 10.8 | 0 | 9.4 / 12.9 / 12.9 | 4002 | 712 | 8 |
| city_hall1_default | after | 6.9 | 7.3 | 9.4 | 10.9 | 0 | 8.1 / 11.1 / 11.1 | 4003 | 677 | 8 |
| city_hall1_close | before | 6.9 | 7.0 | 7.7 | 10.5 | 0 | 10.2 / 10.5 / 10.5 | 4012 | 712 | 8 |
| city_hall1_close | after | 6.9 | 6.9 | 7.3 | 7.5 | 0 | 7.6 / 8.5 / 8.5 | 4013 | 678 | 8 |
| city_hall3_default | before | 6.9 | 6.9 | 7.0 | 8.4 | 0 | 4.8 / 7.5 / 7.6 | 4014 | 715 | 8 |
| city_hall3_default | after | 6.9 | 6.9 | 7.0 | 13.3 | 0 | 6.6 / 13.3 / 13.3 | 4015 | 681 | 8 |
| city_hall3_close | before | 6.9 | 6.9 | 8.1 | 9.9 | 0 | 7.9 / 9.9 / 9.9 | 4016 | 715 | 8 |
| city_hall3_close | after | 6.9 | 7.0 | 8.5 | 10.6 | 0 | 9.0 / 13.3 / 13.3 | 4017 | 681 | 8 |
| city_hall5_default | before | 6.9 | 7.0 | 7.5 | 11.4 | 0 | 7.7 / 11.4 / 11.4 | 3987 | 718 | 5 |
| city_hall5_default | after | 6.9 | 7.5 | 8.2 | 9.3 | 0 | 9.3 / 9.4 / 9.4 | 3988 | 683 | 5 |
| city_hall5_close | before | 6.9 | 7.1 | 7.7 | 10.5 | 0 | 7.7 / 10.5 / 10.5 | 3987 | 718 | 5 |
| city_hall5_close | after | 6.9 | 7.0 | 9.0 | 10.4 | 0 | 9.0 / 10.4 / 10.4 | 3988 | 683 | 5 |
| owner_city_v_default | before | 6.9 | 6.9 | 7.2 | 10.7 | 0 | 7.0 / 8.1 / 8.1 | 3987 | 718 | 5 |
| owner_city_v_default | after | 6.9 | 7.7 | 9.1 | 10.6 | 0 | 10.3 / 10.6 / 10.6 | 3988 | 683 | 5 |
| owner_city_v_close | before | 6.9 | 7.4 | 8.8 | 11.2 | 0 | 10.7 / 11.2 / 11.2 | 3987 | 718 | 5 |
| owner_city_v_close | after | 6.9 | 6.9 | 7.7 | 9.0 | 0 | 9.0 / 10.6 / 10.6 | 3988 | 683 | 5 |
| construction_default | before | 6.9 | 6.9 | 7.1 | 9.9 | 0 | 10.0 / 11.8 / 11.8 | 4050 | 726 | 5 |
| construction_default | after | 6.9 | 6.9 | 7.4 | 9.5 | 0 | 9.6 / 11.6 / 11.6 | 4051 | 690 | 5 |
| construction_close | before | 6.9 | 6.9 | 7.2 | 8.6 | 0 | 9.7 / 10.0 / 10.0 | 4050 | 726 | 5 |
| construction_close | after | 6.9 | 6.9 | 7.0 | 8.6 | 0 | 8.6 / 9.6 / 9.6 | 4051 | 690 | 5 |
| forest_default | before | 6.9 | 7.0 | 7.4 | 13.6 | 0 | 13.6 / 16.5 / 16.5 | 4044 | 727 | 5 |
| forest_default | after | 6.9 | 6.9 | 8.4 | 9.9 | 0 | 9.9 / 12.6 / 12.6 | 4045 | 692 | 5 |
| forest_close | before | 6.9 | 6.9 | 7.0 | 7.3 | 0 | 8.0 / 13.6 / 13.6 | 4050 | 727 | 5 |
| forest_close | after | 6.9 | 7.3 | 7.9 | 9.4 | 0 | 9.6 / 9.9 / 9.9 | 4051 | 692 | 5 |
| world_default | before | 6.9 | 7.0 | 7.0 | 7.0 | 0 | 5.1 / 8.9 / 8.9 | 4107 | 732 | -1 |
| world_default | after | 6.9 | 7.0 | 7.0 | 9.2 | 0 | 6.0 / 6.1 / 6.1 | 4108 | 697 | -1 |
| world_march | before | 6.9 | 6.9 | 7.0 | 7.1 | 0 | 7.0 / 33.2 / 33.2 | 4621 | 761 | -1 |
| world_march | after | 6.9 | 6.9 | 7.0 | 7.0 | 0 | 6.1 / 30.1 / 30.1 | 4622 | 726 | -1 |
| world_march_close | before | 6.9 | 7.0 | 7.2 | 7.4 | 0 | 7.3 / 7.7 / 7.7 | 4621 | 762 | -1 |
| world_march_close | after | 6.9 | 7.0 | 7.0 | 7.0 | 0 | 5.7 / 6.0 / 6.0 | 4622 | 726 | -1 |
| battle | before | 6.9 | 7.0 | 7.0 | 7.0 | 0 | 5.5 / 7.7 / 7.7 | 4588 | 762 | -1 |
| battle | after | 6.9 | 7.0 | 7.0 | 7.2 | 0 | 7.2 / 7.6 / 7.6 | 4589 | 726 | -1 |

Window openings (the call and the next three frames):

| panel | build | call ms | next 3 frames ms | worst ms |
|---|---|---|---|---|
| build_strip | before | 4.9 | 14.7 / 4.6 / 12.9 | 19.5 |
| build_strip | after | 4.2 | 13.1 / 4.0 / 11.0 | 17.3 |
| build_strip_again | before | 3.5 | 6.5 / 5.5 / 5.2 | 10.0 |
| build_strip_again | after | 3.4 | 7.9 / 4.3 / 5.2 | 11.3 |
| recruitment | before | 3.3 | 10.9 / 9.6 / 7.3 | 14.2 |
| recruitment | after | 2.9 | 10.0 / 9.0 / 7.1 | 12.8 |
| sound_settings | before | 3.8 | 8.0 / 4.6 / 4.7 | 11.8 |
| sound_settings | after | 3.6 | 7.0 / 4.0 / 6.2 | 10.6 |
| menu | before | 3.6 | 8.2 / 4.5 / 4.6 | 11.8 |
| menu | after | 3.2 | 7.8 / 3.9 / 5.8 | 10.9 |

No scene and no window opening has a frame over 33 ms in either build.

The chaos runs did have frames over 33 ms, all in the first 5 s after the city becomes interactive, in both
builds. A frame probe that lists the nodes added in each slow frame traced them to:

- **120–160 ms right after the launch.** The city's tree layer is rebuilt from the first server state
  (72 nodes). The parade's first two unit models are instanced too: 11–13 ms each, because their first load
  is synchronous.
- **4 × 40–55 ms at 0.8–1.1 s.** Each is the first model of one kind of townsperson. 36 ms of each frame is
  `ActorRig.glb_uv2_materials` reading the raw .glb. That read happens only in the editor binary
  (`OS.has_feature("editor")`); an exported game reads the manifest instead. So these frames are an artefact
  of profiling with the editor.
- **30–45 ms at 3.6–5.0 s.** The forest world layer joins the city.

This launch-time work runs behind or just after the launch screen, and this stage did not change it. On a
device, `settle_first_frames`' window covers the first of these frames only partly. Spreading the tree rebuild
over several frames would change the order of the city's sync, which is not a safe change for a last stage.

launch_ms (`qa_instant_start.gd`, saved city, server unreachable, three runs each):

| build | runs | median |
|---|---|---|
| before | 1254, 1160, 1157 | 1160 |
| after | 1136, 1183, 1106 (and 1081 in the suite run) | 1136 |

## 3. Memory (`tools/estimate_ios_memory.py`)

The estimate counts:

- every texture as an iPhone loads it: the ASTC or ETC2 file, or a lossless texture as RGBA8 with mipmaps;
- Ogg audio as stored;
- meshes as imported.

It is an estimate from the imported files, not a device measurement.

| group | textures | GPU MB before | GPU MB after | lossless MB after | audio MB | mesh MB |
|---|---|---|---|---|---|---|
| army | 210 | 67.4 | 67.4 | 0.0 | 0.0 | 13.7 |
| audio | 0 | 0.0 | 0.0 | 0.0 | 17.3 | 0.0 |
| city | 70 | 36.1 | 36.1 | 0.0 | 0.0 | 19.9 |
| creature-assets37 | 36 | 8.0 | 8.0 | 0.0 | 0.0 | 13.8 |
| creatures-v2 | 108 | 36.2 | 36.2 | 7.9 | 0.0 | 4.7 |
| environment | 5 | 12.0 | 12.0 | 5.2 | 0.0 | 0.0 |
| forest_rescue | 190 | 337.9 | 301.9 | 2.0 | 0.3 | 24.2 |
| intro | 1 | 25.6 | 11.4 | 11.4 | 0.0 | 0.0 |
| ui | 86 | 47.1 | 47.1 | 47.1 | 0.0 | 0.0 |
| other (icons, creatures37, ground, scenery) | 4 | 2.7 | 2.7 | 2.7 | 0.0 | 9.2 |
| **total** | | **573.0** | **522.8** | 76.3 | 17.6 | 85.9 |

The 50 MB saving comes from two import changes:

- **The nine townsfolk / forest squad colour atlases** are imported at 1024² instead of 2048² ASTC
  (1.4 MB each instead of 5.3 MB). At the closest camera (orthographic size 24, the city's and the forest
  devices' minimum) a 1.8 m figure is about 47 px tall on the 1366 × 630 canvas, under 100 device pixels
  on any iPhone, so a 1024² atlas still has more texels than the screen shows.
- **The launch picture** (`intro/keep-wide.png`) is imported 2560 wide instead of lossless 3840 × 1747
  (11.4 MB instead of 25.6 MB as RGBA8). The widest iPhone screen is 2868 px, so the picture is upscaled by
  at most 1.12× there. The boot splash itself is the source PNG, which the export copies as it is.

Runtime memory (headless `Performance.MEMORY_STATIC`, the profile run above):

| scene | before | after |
|---|---|---|
| city and forest world loaded (profile `city_hall1`) | 712 MB | 677 MB |
| a march on the world map | 761 MB | 726 MB |

Without the forest adventure, the city alone takes about 357 MB. The forest world adds about 360 MB, of
which its mesh arrays are 42 MB. On a 3 GB iPhone the foreground memory limit is commonly reported at about 1.3–1.5 GB (not
measured here), so this leaves room. Still, the forest world is the first thing to check on a device (Xcode memory gauge).

## 4. Touch targets and safe area

At 1366 × 630 one viewport pixel is 0.624 pt on an iPhone 15 (852 × 393 pt) and 0.488 pt on an iPhone SE
(667 × 375 pt). The measurements are in `touch_after.json`; "before" is from abb2494e.

| control | before | after |
|---|---|---|
| menu «Звук», «Меньше движения» | 364 × 40 px (25 pt) | 52 px tall (32 pt) |
| menu «Громкость…» | 364 × 44 px, ending at y = 639 (9 px below the screen) | 150 × 52 px beside «Звук»; the column ends at y = 614 |
| «Звук и музыка» switches | 64 × 34 px (21 pt) | 64 × 50 px (31 pt), same look |
| «Звук и музыка» window | — | 736 × 570 px at y 30–600; all six rows and the credits fit without scrolling |
| HUD resource pills | 108 × 44 px (27 pt) | unchanged |
| window close «×» | 56 × 56 px (35 pt) | unchanged |
| bottom navigation, profile | 84 × 88 px (52 pt), 310 × 88 px | unchanged |

Most of the interface was drawn for a 1366-pixel canvas, where 44 pt is 71 px. The HUD pills (27 pt) and
the close buttons (35 pt) do not meet it. Enlarging them changes the HUD layout, so it is left for a design
pass (listed in the iPhone checklist). The switches now use their full row as the target, with no visual
change, because their styles are empty.

## 5. Settings changes

| setting | before | after | why |
|---|---|---|---|
| frame cap on a phone (`Engine.max_fps`, set after the launch) | none (the engine's Info.plist allows 120 Hz on ProMotion) | 60 | On 120 Hz iPhones: half the GPU work and heat for the same picture. The launch's frame-sliced loading still runs uncapped. |
| «Экономия заряда» (new, off by default, in «Плавность на устройстве») | — | 30 fps and `scaling_3d_scale` 0.75 (the interface stays sharp) | An opt-in for long sessions and older phones. Kept in `user://hud.cfg`. |
| `project.godot` | — | unchanged | Reviewed and kept: mobile renderer, Metal, MSAA 3D 2×, physics 60 Hz (no physics bodies run), audio session Ambient + mix with others. |
| low-processor mode | off | off | The city animates every frame (townsfolk, banners, water). It would save nothing while drawing and would delay input. |
| texture imports | 9 human colour atlases at 2048², keep-wide at 3840 | 1024², 2560 | Memory (section 3). |
| `tools/texture_import_policy.py` | `forest_rescue/ui/` checked as 3D | treated as 2D | The policy check reported the puzzle atlas of the forest windows as an uncompressed 3D texture. It is a UI picture and lossless on purpose. |

## 6. Suites on the after tree

| suite | result |
|---|---|
| qa_runtime | 21/21 |
| qa_instant_start | 12/12 (launch_ms 1081) |
| qa_optimization | 11 040 comparisons, 0 failures |
| qa_townsfolk | 91/91 |
| qa_city_works | 40/40 (its 10 s outage check now follows the 20 s rule, and an 11 s gap must not read as an outage) |
| qa_city_parity | 279/279 |
| qa_build_menu | 20/20 |
| qa_legacy_v6_plots | 16/16 |
| qa_forest_1024 | 161/161 (local forest harness) |
| qa_forest_e2e | 966/966 |
| qa_forest_flow | 166/166 |
| qa_audio_1024 | 313/313 (adds the switch sizes, the menu column and «Экономия заряда») |
| qa_combat_audio | 0 failures |
| qa_city_walls | the 4 known failures (defence and watchtower panels), the same 4 on abb2494e |
| net suites, qa_net_1024 | section 1 |
