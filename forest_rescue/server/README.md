# «Лес потерянных» (forest_rescue_v1) — authoritative server module + local realm

Server side of the DRENOVAR adventure, implementing `forest_rescue/CONTRACT.md` (v1 + additive v1.1).
Node ≥ 22, **zero npm dependencies**.

| Path | What |
|---|---|
| `src/` | Drop-in module: `createForestRescue({ports})` → `settle`, `hallGate`, `command`, `project`, `enter`, `afterVerifiedSpend` |
| `vendor/delivery/` | Byte-identical copies of `delivery/code/*.mjs` + data JSON, pinned by `SHA256SUMS` (= delivery `PACKAGE_MANIFEST.json`) |
| `local-realm/` | Loopback HTTP realm for the Godot client (`server.mjs`), revision-CAS JSON snapshot store |
| `integration/core-adapter.mjs` | Wiring for v92 `CoreGameServer` (see `INTEGRATION_V92.md`) |
| `tests/` | 46 node:test cases (+ the delivered 74 run unchanged); `tests/RESULTS.txt` is a real run |

## Run the local realm

```sh
node local-realm/server.mjs                      # http://127.0.0.1:8418
# env: DRENOVAR_FR_PORT (0 = random), DRENOVAR_FR_DB (default <tmpdir>/drenovar-forest-rescue-realm.json),
#      DRENOVAR_FR_BUILD_SECONDS (hall upgrade timer, default 10), DRENOVAR_FR_START_TIME (simulated clock),
#      DRENOVAR_FR_TEST_ENDPOINTS=0 (disable /test/*)
godot --path godot/project -- --server=http://127.0.0.1:8418    # client loopback mode
```

Endpoints: `GET /api/state`, `POST /api/session/new`, `POST /api/command` (`adventure`, `adventure_intro`,
`kingdom` `upgrade` of the ECO-05 town hall with a short real timer, `kingdom` `enter|skip`; other kinds →
`400 UNSUPPORTED_IN_LOCAL_REALM`), `POST /api/march-preview` (→ 404, hunting is not part of this realm).
Login = header `oai-authenticated-user-id` (default `native-loopback-tester`); profile = `X-Drenovar-Player`.
The progress persists in the DB file across restarts (atomic write, revision CAS, never silently reset).

Test helpers (loopback only):

```sh
curl -XPOST 'localhost:8418/test/hall?level=3'                                  # set ECO-05 level
curl -XPOST localhost:8418/test/army -d '{"units":{"ENG-06":6000}}'             # add healthy units ({"mode":"set"})
curl -XPOST localhost:8418/test/wallet -d '{"food":2000,"wood":2000}'           # set wallet values
curl -XPOST 'localhost:8418/test/building?type=RES-02&level=1'                  # add/set a building
curl -XPOST 'localhost:8418/test/clock?time=1794370600000'                      # simulated clock (monotonic); ?mode=real
```

Minimal play (bodies are `{"kind":"adventure","campaignId":"forest_rescue_v1","action":…}` with an
`Idempotency-Key` header): `form_squad {units}` → `move lf_horse_origin` → `discover_horse` → `move lf_site_01` →
`attempt_task discover` → (trail: `move lf_key_01`, then `mechanism_input` ×3) → `attempt_task recover_artifact` →
`move lf_site_01:guardian` → `engage_guardian` → (after `battle.endsAt`) `attempt_task defeat_guardian` →
`move lf_site_01:cage` → `attempt_task unlock_cage` → `escort_start` → (after `escort.arriveAt`)
`attempt_task escort_home` → `claim_rewards`. A starter squad of 5 recruits loses to Tenerys I (strength
15 000); seed an army first.

## Tests

```sh
node --test "tests/*.test.mjs"                       # 46 tests, ~17 s (includes the delivered suite)
(cd ../delivery && node --test "tests/*.test.mjs")   # delivered 74 alone
```

Highlights: full campaign over HTTP (12 sites, 4 mechanism kinds, real hall III→V upgrades, boss) with a
realm **restart after every one of 204 steps** and deep equality of the whole public state; exact total
7 515 000 (food 2 325 000, wood 2 385 000, stone 1 590 000, iron 1 025 000, coins 190 000; 62 awards);
CONTRACT §3 schema check at every step; lost-response replay; concurrent claims/cage opens; repeated
victory; second profile isolation; corrupt/future schema per namespace; full warehouse; auto-refill opt-in;
injected CAS conflicts; hall I/II lock (before receipt replay); entrance corridor; intro lifecycle and
migration; real OS-process restart; v92 wiring against a stand-in core.

## Design

**Namespaces** (owner = selected `p.id`): `p.adventures` (delivered strict campaign FSM),
`p.adventureMechanisms`, `p.adventureFog`, `p.adventureAccess`, `p.rewardReservePrefs` (as in the delivery
docs) and the new `p.adventureField.forest_rescue_v1` (movement, plates, battle reports, escorts, trail
observations, event ring, nav-graph binding). Only an absent namespace is initialised lazily (an absent field
namespace is derived from a validated existing campaign; an absent intro with progress → acknowledged
`existing_progress`); anything present but invalid / of another version → `STATE_CORRUPT` /
`SCHEMA_UNSUPPORTED`, read-only error projection, no write.

**Command flow** (mirrors `CoreGameServer.command`): settle → hall gate (`MIN_HALL_LEVEL=3` from
adventure-access.mjs, actual ECO-05 level) → receipt replay/409 → strict allowlist → server-built trusted
context → delivered reducers → one candidate snapshot committed with the receipt by revision CAS (retry
recomputes everything from the fresh snapshot). The client never sends proofs, positions, time or amounts.

**Navigation graph** (`src/navgraph.mjs`): the ways of atlas v2 (`data/world-atlas.v2.json`, the art/01
masterplan network: 47 trails between glades, junctions `lf_junction_*`, landmark spots `lf_mark_*`, the
cage-less glade `lf_glade_el`; samples ≤ 0.5, y from the samples; the delivered v1 atlas is kept for content
checks), a 3-unit spur to `lf_home_reception` (-8, -52), glade spokes to cage/guardian/key from the atlas
offsets, paired-latch plates (key ± 2.6 z) and trail-cache landmarks (the cache is reachable only past the three
landmarks in clue order). Water is allowed only on the approved deck of the bridge way (`lf_route_bridge`; v1
`lf_route_10_11`; deck y = 1.1, inserted `lf_bridge_crossing` junction); the build fails closed otherwise.
Dijkstra on junctions, never through another site's glade (a glade node only carries a trip on when the trip
starts or ends there); junctions / landmark spots are `waypoint`s (never targets). A stopped squad can rest on a
fine node `<way>#<index>`. A save written on another graph (`field.graphId`, e.g. atlas v1) is re-bound when
nothing moves and the squad stands on a named node (its fog restarts from the town default), else
`NAV_GRAPH_MISMATCH` (CONTRACT v1.3).

**Movement**: server-timed moves (`departAt/arriveAt`, speed 0.6 × slowest troop speed; escort ≤ 1.6;
horse leads ≤ 1.5 s ahead and waits). `settle(now)` commits traversal checkpoints every 4 units with a
monotonic sequence and reveals fog through the delivered `createFogAuthority` whose `resolveTraversal`
reads only the committed move record; finished moves archive their fog cursor (≤ 64 cursors).

**Mechanisms**: trail_cache — a symbol counts only if the committed path passed that landmark; rune_lock /
winch_sequence — squad present in the glade; paired_latch — `occupy_plates` sends two real squad members to
the plates (timed), the centre latch needs both held simultaneously at command time; moving releases them.

**Battle model** (`src/battle.mjs`): deterministic (seed = `p.id|encounterId|attempt`). The enemy's
`strength` anchors the calibration (a reference ENG-09 squad of equal power breaks even); troop stats shape
the fight: offence per unit `atk²/(atk+def_enemy)`, toughness `hp·(A+def)/A`, front line takes hits first.
Guardians show their ability (telegraphed) at least once, cannot be one-shot (≤ 25 % hp per volley).
The boss uses campaign.json's exact telegraph/active/recovery seconds (stomp waves 0.9 s apart), phases at
70 %/35 %, and each phase must show one full attack cycle before it can end. Reports are immutable;
losses (60/40 wounded/dead on victory, 35/65 otherwise) and ordinary first-victory loot are applied at
`endsAt` like a hunt; guardians are one-time; defeat/retreat never touch keys, people or rewards.

**Economy**: rewards go to escrow by the delivered FSM; `claim_rewards` moves `min(pending, cap − wallet)`
into `city.progress.wood` / `city.demo.wallet.*`; opt-in auto-refill after a real paid command.

## Known gaps

* v92 itself was not available: integration is specified and tested against a stand-in (`INTEGRATION_V92.md`).
* Battle balance is a calibrated model, not v92 `combat.mjs`; kamneklyk II/III and dragor II stats are local
  candidates until `catalog.creatureSpec` is injected. Numbers are untested by real players.
* Local realm city/army are simplified: no production ticks, training, healing, hunting or building
  prerequisites (hall upgrade only); `healthy` = owned − wounded − squad.
* Real terrain collision, bridge ramps and `protectedTownCells` from footprints are not modelled.
* "New entry" for intro reconciliation is explicit (`POST /api/session/new`); the client must call it.
