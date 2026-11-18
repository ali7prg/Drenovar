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

## 6. Error codes

`FOREST_LOCKED_HALL_LEVEL`, `HALL_LEVEL_TOO_LOW`, `CAMPAIGN_PAUSED`, `TASK_OUT_OF_ORDER`,
`ACT_LOCKED`, `NOT_ARRIVED`, `TARGET_UNKNOWN`, `SQUAD_EMPTY`, `SQUAD_BUSY`,
`MECHANISM_NOT_READY`, `PLATES_NOT_OCCUPIED`, `NO_BATTLE_PROOF`, `ARTIFACT_MISSING`,
`ESCORT_NOT_ARRIVED`, `BOSS_LOCKED`, `IDEMPOTENCY_BODY_MISMATCH`, `BAD_FIELDS`,
`STATE_CORRUPT`, `SCHEMA_UNSUPPORTED`, `CAS_CONFLICT_RETRY`.

## Changelog

* v1 (2026-11-18): initial contract.
