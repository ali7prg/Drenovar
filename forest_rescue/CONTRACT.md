# «Лес потерянных» — server ↔ client contract (v1)

This is the single interface between the authoritative adventure module
(`forest_rescue/server`) and the Godot client (`godot/project/src/forest_rescue`).
Both sides MUST follow it. Extensions are allowed only additively and must be
recorded in the changelog at the bottom of this file.

Source of truth for content: `forest_rescue/delivery/data/*.json`
(campaign, economy, ui.ru, dialogue.ru, unlock-intro, world-atlas, persistence-contract).
All IDs below are the stable IDs from those files.

## 1. Transport

Existing DRENOVAR API, unchanged:

* `POST /api/command` — body is one command object (below). Header
  `Idempotency-Key: <uuid>` is mandatory for adventure commands; replaying the same
  key + identical body returns the current authoritative state without new effects;
  same key + different body → `409 {"error":"IDEMPOTENCY_BODY_MISMATCH"}`.
* `GET /api/state` — returns the public state. The adventure projection lives in
  `state.adventure` (section 3). A server that does not know the adventure omits the
  field; the client then shows the locked fog with the text
  «Приключение недоступно на этом сервере» and sends no adventure commands.
* Header `X-Drenovar-Player: <p.id>` selects the settlement/profile (existing rule).
  Every adventure namespace belongs to the selected `p.id`, never to the login.
* Responses to `/api/command` are the same public state as `/api/state` plus
  `"events": [...]` (section 4) describing what this command just committed.
  Errors: HTTP 4xx with `{"error":"<CODE>","message":"<ru text>"}`.

## 2. Commands (client → server)

The client never sends success flags, rewards, wallet, capacity, ownerId, playerId,
time, positions, revision, artifact counts or proofs. Unknown fields → `400 BAD_FIELDS`.

### 2.1 Intro (hall III unlock presentation)

```json
{"kind":"adventure_intro","campaignId":"forest_rescue_v1","action":"start_intro"}
```
`action` ∈ `start_intro | finish_intro | skip_intro | defer_intro`
(semantics: `delivery/code/adventure-access.mjs`, `docs/HALL3_UNLOCK_AND_INTRO_RU.md`).
Nothing is awarded by any intro action.

### 2.2 Adventure

```json
{"kind":"adventure","campaignId":"forest_rescue_v1","action":"<action>", ...}
```

| action | extra fields | meaning |
|---|---|---|
| `form_squad` | `units: {"<unitId>": n}` | choose which existing healthy units the squad represents (real army; counts are validated against healthy units and reserved, never created). |
| `move` | `targetId` | server plans a path on the adventure graph from the squad's committed node to `targetId` and starts a timed move. |
| `stop` | — | stop at the next graph node (server decides). |
| `discover_horse` | — | prologue: requires committed arrival at `lf_horse_origin`. |
| `attempt_task` | `siteId`, `taskId` | `taskId` ∈ `discover, recover_artifact, defeat_guardian, unlock_cage, escort_home`; the server builds all proofs from its own records. |
| `mechanism_input` | `siteId`, `symbol` | one input for the site's mechanism (`trail_cache`, `rune_lock`, `winch_sequence`, `paired_latch`). |
| `occupy_plates` | `siteId` | paired latch: server splits the present squad over both plates (needs ≥2 squad members present). |
| `engage_guardian` | `siteId` | server resolves the guardian battle with the squad's real units; produces a battle report. |
| `retreat` | — | leave an active battle (existing casualty rules). |
| `escort_start` | `siteId` | after `unlock_cage`, start escort of the exact three captives to `lf_home_reception`. |
| `begin_boss` | — | requires 36 rescued + hall V + arrival at `lf_boss_ancient_maw`. |
| `engage_boss` | — | resolve the boss battle (3 phases) with the squad. |
| `finish_boss` | — | asks the server to verify the final battle report. |
| `claim_rewards` | — | move `min(pending, capacity-wallet)` per resource from escrow to the real wallet. |
| `set_auto_refill` | `enabled: bool` | owner-scoped preference, default false. |
| `pause` / `resume` | — | campaign pause (does not pause the shared world). |

Targets (`targetId`): `lf_horse_origin`, `lf_site_NN` (glade centre / approach),
`lf_key_NN` (artifact spot), `lf_site_NN:cage`, `lf_site_NN:guardian`,
`lf_site_NN:plate_left`, `lf_site_NN:plate_right`, `lf_bridge_crossing`,
`lf_boss_ancient_maw`, `lf_home_reception` (north approach of the settlement,
x=-8, z=-55 region). Hidden/unrevealed targets → `404 TARGET_UNKNOWN` (no leak).

## 3. Public projection `state.adventure`

```jsonc
{
  "campaignId": "forest_rescue_v1",
  "schemaVersion": 1,
  "serverTime": 1794370000000,          // ms, same clock as state.serverTime
  "access": {"unlocked": false, "hallLevel": 2, "requiredHall": 3,
             "reason": "FOREST_LOCKED_HALL_LEVEL" },
  "intro": {"status": "pending|playing|acknowledged", "deferred": false,
            "offer": true },            // offer=true → client may present the intro now
  "fog": {"explorationLocked": true, "columns": 56, "rows": 56, "cellSize": 4,
          "origin": {"x": -112, "z": -112},
          "visibleBase64": "...",       // projection only (bit i = row*56+col, LSB first)
          "revision": 7,
          "entranceCorridor": {"from":{"x":-8,"z":-55},"to":{"x":-12,"z":-60},"radius":3,"transitionMs":1200}},
  "campaign": {"phase": "prologue|rescue|boss_unlocked|boss_active|completed",
               "paused": false, "revision": 12,
               "horseJoined": false,
               "sites": [{"id":"lf_site_01","step":0,"artifact":0,"act":1,
                          "available": true, "visible": true}],
               "rescuedIds": ["lf_captive_01_a"], "rescuedCount": 1,
               "actUnlocked": [true,false,false,false]},
  "escrow": {"earned":{"food":0,"wood":0,"stone":0,"iron":0,"coins":0},
             "claimed":{...}, "pending":{...}},
  "autoRefill": false,
  "squad": {"units": {"ENG-09": 5}, "members": 3,          // visual representatives (max 3)
            "node": "lf_horse_origin",                     // last committed graph node
            "move": null | {"path":[{"x":..,"y":..,"z":..}], "departAt": ms, "arriveAt": ms,
                            "targetId": "lf_site_01", "speed": 2.4},
            "busy": null | "battle" | "escort" | "mechanism"},
  "horse": {"visible": true, "node": "lf_horse_origin", "mood": "calm|alert|waiting",
            "move": null | {...same shape as squad.move...}},
  "pois": [ {"id":"lf_site_01","kind":"site","x":-20,"y":6.54,"z":-65,
             "variation":"trail_cache","cage":"oak|iron|root",
             "cagePose":"closed|open", "captives":[{"id":"lf_captive_01_a","name":"Лада",
             "role":"возница","visual":"miller","state":"caged|freed|escorted|home"}],
             "guardian": {"species":"tenerys","level":1,"modifier":null,
                          "state":"alive|engaged|defeated", "hp":1400, "hpMax":1400},
             "artifact": {"id":"lf_key_01","family":"stone_rune|bronze_seal|amber_crystal|bone_key",
                          "state":"hidden|found|in_socket"},
             "mechanism": {"kind":"trail_cache","progress":1,"length":3,"solved":false,
                           "symbols":["split_birch","white_moss","fallen_trunk", "..."],
                           "lastResult":"ok|wrong|null"} } ],
  "battle": null | {"reportId":"...","siteId":"lf_site_01","encounterId":"...",
                    "species":"tenerys","level":1,"startedAt":ms,"endsAt":ms,
                    "outcome":"victory|defeat|retreat|pending",
                    "timeline":[{"t":0.0,"type":"attack|hit|ability|death|telegraph|phase",
                                 "actor":"guardian|squad|boss","attack":"jaw_arc", ...}],
                    "losses":{"wounded":{},"dead":{}}, "loot": {...}},
  "escort": null | {"siteId":"lf_site_01","captiveIds":[...3],"move":{...},"state":"walking|home"},
  "boss": {"state":"locked|available|active|defeated","hp":78000,"hpMax":78000,
           "phase":"hunt|fury|last_stand","requiredHall":5},
  "nextTask": {"siteId":"lf_site_01","taskId":"discover"} | null
}
```

Rules: hidden POIs are absent (not flagged). Fog `visibleBase64` is a projection,
never the stored bitset. While `access.unlocked=false` → `pois=[]`, `horse.visible=false`,
`fog.explorationLocked=true` and the client renders the animated boundary fog only.

## 4. Events (in command responses)

`events` is a list of committed, deduplicated presentation cues:
`horse_joined`, `task_completed {siteId,taskId,reward}`, `reward_escrowed {resources}`,
`transfer_rewards {resources}`, `fog_revealed {cells}`, `mechanism_progress {siteId,ok}`,
`battle_report {reportId}`, `cage_opened {siteId}`, `escort_arrived {siteId}`,
`boss_unlocked`, `boss_started`, `boss_phase {phase}`, `campaign_completed`,
`intro_present`. The client dedups by `revision`+type; state, not events, decides poses
after reload.

## 5. Timing

All `move`/`battle`/`escort` objects carry server timestamps. The client interpolates
`position(t)` along `path` with `t = serverTime + (localNow - receivedAt)`. Arrival is
committed by the server lazily on the next request after `arriveAt` (settle); the client
re-polls `/api/state` at `arriveAt + 250 ms`. Animations never commit anything.
While a squad or escort move is under way the client also re-reads `/api/state` about every 1.2 s
(each read settles the committed traversal checkpoints, so `fog.visibleBase64` grows checkpoint by
checkpoint and the client dissolves each newly revealed cell; changelog v1.2).

## 6. Error codes

`FOREST_LOCKED_HALL_LEVEL`, `HALL_LEVEL_TOO_LOW`, `CAMPAIGN_PAUSED`, `TASK_OUT_OF_ORDER`,
`ACT_LOCKED`, `NOT_ARRIVED`, `TARGET_UNKNOWN`, `SQUAD_EMPTY`, `SQUAD_BUSY`,
`MECHANISM_NOT_READY`, `PLATES_NOT_OCCUPIED`, `NO_BATTLE_PROOF`, `ARTIFACT_MISSING`,
`ESCORT_NOT_ARRIVED`, `BOSS_LOCKED`, `IDEMPOTENCY_BODY_MISMATCH`, `BAD_FIELDS`,
`STATE_CORRUPT`, `SCHEMA_UNSUPPORTED`, `CAS_CONFLICT_RETRY`.

## Changelog

* v1 (2026-11-18): initial contract.
* v1.1 (2026-11-18, server — `forest_rescue/server`): **additive only**; every v1 field, command and code keeps its meaning.
  * **Requests.** Optional `requestId` in adventure/adventure_intro bodies; when present it MUST equal the
    `Idempotency-Key` header (it is part of the signed body), so Godot's `send_request` reuses it as the retry key.
    `finish_intro` takes optional `attempt` (default: the attempt currently `playing`); `start_intro` takes
    optional `reducedMotion: bool` (→ `intro_present.mode = "static_cards"`). Key format `[-\w]{8,128}`.
  * **Targets.** Trail-cache sites (01/05/09) add `lf_site_NN:landmark:<symbol>`; the artifact spot of those sites
    is reachable only along centre → landmark 1 → 2 → 3 → key (clue order). `:plate_left/right` exist only on
    paired-latch sites (04/08/12). `lf_home_reception` = (-8, 6.783, -52). Glade sub-targets (key/cage/guardian/
    plates/landmarks) are known only after `discover`; a site centre is a known target when its act is available
    or it is revealed; `lf_bridge_crossing` when act 4 is open or revealed; `lf_boss_ancient_maw` from
    `boss_unlocked` or when revealed. Everything else → `404 TARGET_UNKNOWN`. After `stop` the squad may rest on a
    fine graph node `"<wayId>#<index>"` (valid `squad.node`/`move.targetId`, not a valid `targetId` to send).
  * **Movement.** `move` while moving redirects from the next graph point (no stop needed). `stop` during an escort
    → `SQUAD_BUSY`. While paused only `move` to `lf_home_reception`, `stop`, `retreat`, `form_squad`, `claim_rewards`,
    `set_auto_refill`, `pause/resume` (and intro actions) are accepted. `form_squad` only while the squad stands at `lf_home_reception`.
    `move.path` is simplified for transport (≤5 cm deviation); interpolate by horizontal (XZ) arc-length fraction
    `(t-departAt)/(arriveAt-departAt)`. Squad speed = 0.6 × slowest troop speed (ENG-09 → 2.4); escort ≤ 1.6.
    The horse follows the same path and arrives up to 1.5 s earlier (`mood:"waiting"`).
  * **Projection additions.** `adventure.revision` (event dedup key), `adventure.recentEvents` (last 32 committed
    cues, `fog_revealed` there carries only `count`); `intro.invitation|continueRequired|attempt|acknowledgment`;
    `fog.boundaryFog`; `squad.position`, `move.kind|length`; `horse.position|joined`; POI extras: `name, number,
    act, step, available, discovered, targets{center,cage,guardian,key,plate_left,plate_right,landmarks[{id,x,y,z,
    symbol,observed}]}` (sub-targets after discover), `guardian.name|requiredHall|attempts`, `artifact.name|held`,
    `mechanism.clue|observed|plates{state:free|walking|held, readyAt}`; `captives` is `[]` until discovered;
    `symbols` is a stable shuffle of the solution. POI kinds: `home, horse_origin, site, bridge, boss_arena`.
    `battle.kind|active|units|hp|hpMax|phase|modifier`, `loot.overflow`; `escort.departAt|arriveAt|arrivedAt`;
    `boss.attempts|name`. `nextTask` uses `{"siteId":null,"taskId":"discover_horse"}` in the prologue and
    `{"siteId":"lf_boss_ancient_maw","taskId":"begin_boss|engage_boss|finish_boss"}` for the finale. On a corrupt or
    future-schema save `state.adventure` = `{campaignId, schemaVersion, serverTime, error:{error,message,detail},
    access:{unlocked:false,…}, pois:[], horse:{visible:false}, fog:{explorationLocked:true,…}}` (send no commands).
  * **Timeline.** Extra types `recovery` (boss, `until`) and `retreat`; events may carry `target, damage, hp,
    knocked{unitId:n}, survivors, attack, phase, shape, telegraphSeconds, activeSeconds, recoverySeconds, wave`.
    `t` is seconds from `startedAt`; the outcome is applied by the server at `endsAt` (settle), never by a clip.
  * **Events.** Every event has `seq` and `revision`. `fog_revealed {cells:[bit indices], count}`;
    `transfer_rewards {resources, capacity, storageFull, auto?}`; `task_completed.reward`; `battle_report
    {reportId, siteId, outcome[, endsAt]}`. New cues: `move_started, squad_arrived, squad_formed, landmark_observed,
    plates_occupied, plates_released, artifact_found, escort_started, boss_defeated, squad_returned_home,
    intro_deferred`. Command responses also carry the cues committed by the settle of the same transaction
    (arrivals, fog, battle results, boss phases); `GET /api/state` carries none (use `recentEvents`).
  * **Errors.** HTTP 400 `BAD_FIELDS`; 403 `FOREST_LOCKED_HALL_LEVEL`, `HALL_LEVEL_TOO_LOW` (`detail.requiredHall`);
    404 `TARGET_UNKNOWN`; 409 all others; 500 `INTERNAL_ERROR`. New codes: `GUARDIAN_DEFEATED`, `UNITS_UNAVAILABLE`,
    `INTRO_NOT_SAFE`, `INTRO_STALE_ATTEMPT`, `INTERNAL_ERROR`. Bodies may include `detail`.
  * **Session entry.** `POST /api/session/new` for a login that already has a settlement returns it (200) and
    counts as a new foreground entry (an interrupted `playing` intro becomes a deferred invitation); clients
    should call it once per app launch. Local realm only: body `{"additional":true}` creates another profile.
* v1.2 (2026-11-21, client timing note — no server or wire change): during squad/escort moves the Godot client
  polls `GET /api/state` every ~1.2 s of server time (previously only at `arriveAt + 250 ms` and the 5 s idle
  poll), so traversal fog reveals reach the client per checkpoint (every 4 units, radius 10) and dissolve
  gradually. Fog still opens only from server cells; the client never reveals by time or event.
* v1.3 (2026-11-21, atlas v2 — server data + save handling; wire format unchanged, every v1/v1.1 field, command
  and code keeps its meaning):
  * **World.** The server navigation graph is built from atlas v2 (`lost_forest_atlas_v2`,
    `forest_rescue/server/data/world-atlas.v2.json`, generated by `forest_rescue/tools/plan_atlas_v2.py` from the
    art/01 masterplan and the owner's zone notes): 12 site glades + the cage-less glade `lf_glade_el`, trail
    junctions `lf_junction_*`, landmark spots `lf_mark_*`, the bridge ends `lf_bridge_west/east`; 47 ways
    (`lf_trail_<from>__<to>`, bridge way `lf_route_bridge`). Unchanged: base ±56 and the city, fog spec (56×56 cells
    of 4, ±112, revealRadius 10, entrance corridor (-8,-55)→(-12,-60)), bridge at (90.48, 20), campaign data except
    site positions, `lf_home_reception`, every targetId format. The atlas v1 file stays delivered (content checks
    only). New site centres: 01 (-80,-14), 02 (-86,40), 03 (-72,74), 04 (-40,87), 05 (2,92), 06 (30,101),
    07 (57,90), 08 (98,85), 09 (84,47), 10 (96,-20), 11 (92,-52), 12 (42,-70); the boss arena at (18,-92),
    entrance yaw 72.9°.
  * **Graph nodes.** Junctions, landmark spots and `lf_glade_el` are `kind:"waypoint"`: they appear in `move.path`
    and as a resting `squad.node` after `stop`/redirects, never as a valid `targetId`. A trip never passes through
    another site's glade (cages stand on spurs): a glade node only carries the walk on when the trip starts or ends
    in that glade. `move.length`/durations follow the new trail lengths.
  * **Saves (graph re-bind).** `field.graphId` names the navigation graph a save was written on. On the first load
    with a different graph (atlas v1 → v2) the field is re-bound when nothing is in motion and `squad.node` is a
    named node of the new graph (home, horse origin, a site or its sub-targets: positions are node names, so they map
    1:1); otherwise the load fails closed with `NAV_GRAPH_MISMATCH` (no commands; state.adventure carries the error).
    On a re-bind the fog bits restart from the delivered default (`createFogState`: protected town only) because v1
    explored cells follow v1 trails; the squad re-reveals the forest as it walks. Campaign progress, rewards,
    mechanisms, intro and preferences are untouched. Local realm: profiles created before atlas v2 are not kept — the
    realm DB file (`DRENOVAR_FR_DB`, default `<tmpdir>/drenovar-forest-rescue-realm.json`) is deleted / a fresh
    path is used for every v2 run (evidence movies use a new DB per run); the Godot client fixtures
    (`godot/project/data/forest_rescue/game/fixtures/*.json`, 28 states) are re-recorded on atlas v2 with
    `forest_rescue/server/tools/record-fixtures.mjs`.
  * **Client.** No new client obligation: the Godot client reads the same projection; its world copy of the atlas
    (`godot/project/data/forest_rescue/world/world-atlas.json`) is the v2 file, so visual trails, glades and the
    arena match the server ways (WORLD_API v3.3).

