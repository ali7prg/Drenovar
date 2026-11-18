# Integrating «Лес потерянных» into drenovar-server v92

**Honesty first.** The authoritative server (`ali7prg/drenovar-server`, `DRENOVAR-Server-v92/`,
snapshot commit `365276cc169943adc48847c0e9d86ae23e77fb3e`) was **not accessible** in the session that
produced this module. Every v92 reference below comes from the delivery package
(`delivery/CLAUDE_CODE_IMPLEMENTATION_BRIEF_RU.md`, `docs/CODE_AND_PERSISTENCE_RU.md`) and from the file
manifest `docs/05_SERVER_FILES.txt` of this repository. The wiring was exercised only against a **stand-in
core** that follows the documented flow (`tests/core-adapter.test.mjs`) and against the local realm
(`local-realm/`). Nothing here has been run inside v92, against D1, or on a device.

## 0. Verify you are patching the same snapshot

| v92 file | bytes | sha256 (from docs/05_SERVER_FILES.txt) | used for |
|---|---:|---|---|
| gameplay37/server/core.mjs | 17111 | 2dc477f5bba2c190b7804b523bc94e4317bf37cd5219d49406aae01c77c94af4 | settle:35, publicState:50, readyPlayer62:51–54, command:66, putPlayer/INSERT:103 |
| gameplay37/server/hosted.mjs | 5520 | b68189e937f398f50949d25746f2c1dcfc87bf0ffb73f46eed76d688266669cf | handleGame snapshot CAS (lines 18–30) |
| dist/city/kingdom29.js | 13208 | 6eed71063f83c1c77f7b75f422b1bd41bd359f35759988e1590ac14b5c47a6cd | hallLevel:14, balance:20, capacity:21, settleKingdom:36 |
| gameplay37/server/accounts40.mjs | 4299 | ce73c41b2d08a3ab25b7666f5157395287940972ec13d4aa2e133a0bdd700083 | importLegacy |
| gameplay37/server/catalog.mjs | 2104 | 0c9a9971f8cc176c8885bfc2a5e6690ea0c1ce23d83667b20c796a9ba8e56a9f | creatureSpec |
| gameplay37/server/combat.mjs | 2583 | 918540ade91ed2878f4fbc2b4553fef85026fecf6475c26c1ecab650e8916715 | (not used; see §6) |
| gameplay37/server/native-session.mjs | 6470 | 90f2176aefd6acdbefa2571e95e1fb43b9e6d8482f20d986aed1f945d7f127e2 | new foreground entry |
| dist/city/upgrade-v1.js | 2263 | 873bcfd90a5b4ce8111176a57534d4cf91dae874a58796cb808622f8395996e8 | storage per level |

`sha256sum` these first. If any differs, re-read the current code and adapt the insertion points; do not
apply line numbers blindly.

## 1. Copy the module

Copy `forest_rescue/server/{src,vendor,integration}` into v92, e.g. `gameplay37/forest/` (keep the three
folders side by side; `src/vendor.mjs` loads `../vendor/delivery/...` relatively). Zero npm dependencies,
Node ≥ 22 (`structuredClone`, `node:crypto`). For the Cloudflare/Workers build check that
`node:fs`/`node:crypto` are available or replace `src/vendor.mjs`'s `readFileSync` JSON loading with JSON
imports and `src/util.mjs`'s `createHash` with an equivalent (only used for the nav-graph id).

## 2. Construct the adapter once (core.mjs, top level)

```js
import {createV92Adventure, sanitizeLegacyImport} from '../forest/integration/core-adapter.mjs';
import {hallLevel, balance, capacity} from '../../dist/city/kingdom29.js';
import {creatureSpec} from './catalog.mjs';

const adventure = createV92Adventure({
  hallLevel, balance, capacity,                 // kingdom29.js:14 / :20 / :21 — the REAL functions
  creatureSpec,                                 // replaces the local kamneklyk/dragor candidates
  healthyUnits: p => /* the exact computation publicState uses for `healthy` (owned − wounded − deployed) */,
  applyLosses: (p, {wounded, dead}, battle) => /* existing hunt casualty rule from settle; return what was applied */,
  applyLoot: (p, loot, battle) => /* existing first-victory reward rule (resources/items/xp); return applied */,
  pushReport: (p, report) => /* append to p.reports like settle does for ordinary hunts */,
  protectedTownCells: p => /* centres of 4×4 cells covered by property OUTSIDE ±56 (may start as []) */,
});
```

`capacity(city)` must return one cap that applies to each resource (as kingdom29 does); the adapter expands
it to five keys. Wallet writes follow ECONOMY_RU.md: **wood → `p.city.progress.wood`, everything else →
`p.city.demo.wallet[r]`** (never `demo.wallet.wood`); balances above cap are never cut.

## 3. settle — core.mjs:35

Right after `settleKingdom(...)` (so a just-completed hall III counts) add:

```js
const adventureSettle = await adventure.settle(p, now);   // async: the delivered fog authority is async
```

It commits, lazily and idempotently: battle results at `endsAt` (losses to the real army, ordinary loot,
one-time guardian defeat, `p.reports`), traversal checkpoints with fog reveal (only from the committed move
record), trail landmark observations, arrivals and escort arrivals. If v92's `settle` is synchronous, call
this from `readyPlayer62` (51–54) right after `settle(...)`. Keep `adventureSettle.events` for the command
response (step 4); they are also persisted in `state.adventure.recentEvents`. A corrupt adventure save makes
`settle` a no-op (it never rewrites bad bytes).

## 4. command — core.mjs:66 (inside the existing `this.tx`)

Insert **after `const p = await readyPlayer62(...)` and BEFORE the existing `SELECT … FROM commands`**:

```js
const handled = await adventure.command({
  p, b, key, now,
  selectReceipt: k => /* SAME query the legacy branch uses: SELECT signature FROM commands WHERE player=? AND key=? */,
});
if (handled) {                         // null for every non-adventure kind → legacy flow unchanged
  if (!handled.ok) throw httpError(handled.status, handled.body);   // roll the tx back, reply 4xx JSON
  if (handled.receipt) {
    // existing putPlayer(p) + INSERT INTO commands(player, key, signature=handled.receipt.signature) — line 103
  }
  return {...publicState(p), events: [...adventureSettle.events, ...handled.events]};
}
// … existing receipt SELECT and branches …
```

Inside `adventure.command` the order is exactly: **hall gate** (`hallLevel(p.city) ≥ 3`, read from the
settled selected player; 403 `FOREST_LOCKED_HALL_LEVEL`) → `selectReceipt(key)` (same key + same
`JSON.stringify(b)` → state without effects; different body → 409 `IDEMPOTENCY_BODY_MISMATCH`) → strict
allowlist → effects on the candidate `p`. The gate only applies to `kind: adventure | adventure_intro`;
ordinary commands are never gated. All effects (campaign, mechanisms, fog, intro, preferences, field,
real wallet fields, battle losses/loot) are written to `p`, so the single existing `putPlayer` + receipt
INSERT commits them atomically.

## 5. publicState — core.mjs:50

```js
state.adventure = adventure.publicState(p, now);   // pure; never the stored bitset, seeds or proofs
```

Behind a feature flag simply omit the field: the client then shows «Приключение недоступно на этом сервере».

## 6. hosted.mjs (18–30) — CAS

No change needed if `handleGame` re-runs the whole `command` on a fresh snapshot after a failed
`UPDATE … WHERE revision=?`: the adventure branch is a pure function of that snapshot, so the retry
recomputes the gate, arrival/battle/escort proofs, capacity and wallet from it (tested with the local
realm's identical revision CAS, `tests/cas-conflict.test.mjs`). If hosted.mjs instead returns the conflict
to the client, map it to 409 `CAS_CONFLICT_RETRY`; the client retries with the **same** key/body.
Never publish events before the CAS succeeded (the adapter only returns them; publishing is the caller's).

## 7. Paid branches → opt-in auto-refill

In each genuinely successful paid branch (build, upgrade, train, heal, …), after the existing production
settlement and immediately before the debit take `const before = integerWallet(p)` (floor of `balance`
for the five resources); after the debit succeeded call `await adventure.afterVerifiedSpend(p, before, now)`
in the same transaction. It is a no-op unless `p.rewardReservePrefs.forest_rescue_v1.autoRefill === true`,
hall ≥ III and something was really spent; it never runs on polls, refunds, cancellations or replays.

## 8. Other hooks

* **New foreground entry** (`native-session.mjs`, where a session is (re)established — not on polling):
  `await adventure.enter(p, now)` — an interrupted `playing` intro becomes a deferred invitation.
* **accounts40 `importLegacy`**: `imported = sanitizeLegacyImport(imported)` — legacy/browser saves can
  never create adventure progress, escrow or proofs.
* **Profiles**: every namespace lives on the selected `p` (header `X-Drenovar-Player`), never on the login.

## 9. Battle adapter

`gameplay37/server/combat.mjs` `simulate` has no `ancient_maw` profile and no phases, so the module keeps
its own deterministic battle (`src/battle.mjs`) for the 12 campaign guardians and the 3-phase boss: real
committed healthy units and troop stats, creature stats from the injected `creatureSpec`, enemy `strength`
as calibration anchor, exact boss telegraph/active/recovery timings from campaign.json, seeded by
`p.id|encounterId|attempt`. Results are stored as immutable reports and finalized at `endsAt` by settle;
losses go through **your** `applyLosses`, loot through **your** `applyLoot` (separate line, outside the
7 515 000 campaign total). If you prefer `combat.simulate` for guardians, keep the report contract
(`timeline`, `knocks`, `outcome`, `endsAt`) and the one-time guardian record.

## 10. What could not be verified here

* The real `CoreGameServer.command` code path, receipt table/columns and error helper names.
* Whether v92 `settle` is sync or async; the exact `healthy`/casualty/loot/report functions to inject.
* D1 CAS retry behaviour in `hosted.mjs`, Workers runtime support for `node:fs`/`node:crypto`.
* `catalog.mjs` stats for kamneklyk II/III and dragor II (local candidates are used until injected).
* Real terrain/collision of the atlas routes, the bridge geometry and ramps (graph uses atlas samples only).
* `protectedTownCells` from real footprints; existing army deployments counted in `healthyUnits`.
* Any client/device behaviour (Godot client is built separately against CONTRACT.md).
