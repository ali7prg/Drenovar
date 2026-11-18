// Wiring of the «Лес потерянных» module into drenovar-server v92 (gameplay37/server/core.mjs).
// The v92 source was NOT available in this session: this adapter is written against the
// line references verified by the delivery package (CoreGameServer.command:66, publicState:50,
// settle:35, readyPlayer62:51–54, hosted.mjs:18–30, kingdom29.js:14/20/21) and is exercised
// here by tests/core-adapter.test.mjs with a stand-in core that follows that documented flow.
// All v92 functions are injected; nothing below imports v92 paths directly.
import {createForestRescue} from '../src/handler.mjs';
import {AdventureError, toAdventureError} from '../src/errors.mjs';
import {RESOURCES} from '../src/content.mjs';
import {NAMESPACES} from '../src/namespaces.mjs';

/**
 * v92 ports. Required injections (v92 names in brackets):
 *   hallLevel(city)            [dist/city/kingdom29.js:14 hallLevel]
 *   balance(city, resource)    [dist/city/kingdom29.js:20 balance]
 *   capacity(city)             [dist/city/kingdom29.js:21 capacity] — one cap per resource
 *   creatureSpec(species, lvl) [gameplay37/server/catalog.mjs creatureSpec]
 *   healthyUnits(p)            [the same computation publicState uses for `healthy`]
 *   applyLosses(p, {wounded, dead}, battle) → applied   [the existing hunt casualty rule of settle]
 *   applyLoot(p, loot, battle) → applied                 [the existing first-victory reward rule]
 *   pushReport(p, report)                                [append to p.reports like settle does]
 * Optional: protectedTownCells(p) → [{x,z}] cells of real property outside the ±56 square.
 */
export function createV92Ports(v92) {
  for (const name of ['hallLevel', 'balance', 'capacity', 'creatureSpec', 'healthyUnits', 'applyLosses', 'applyLoot', 'pushReport']) {
    if (typeof v92?.[name] !== 'function') throw new Error('v92 dependency missing: ' + name);
  }
  return {
    hallLevel: p => { const level = v92.hallLevel(p.city); return Number.isSafeInteger(level) ? level : null; },
    capacity: p => v92.capacity(p.city),
    integerWallet: p => Object.fromEntries(RESOURCES.map(r => {
      const value = v92.balance(p.city, r);
      return [r, Number.isFinite(value) && value > 0 ? Math.min(Number.MAX_SAFE_INTEGER, Math.floor(value)) : 0];
    })),
    // Wallet mapping (ECONOMY_RU.md): wood → city.progress.wood; others → city.demo.wallet[r].
    credit(p, resource, amount) {
      if (!Number.isSafeInteger(amount) || amount < 0) throw new Error('INVALID_CREDIT');
      if (!amount) return;
      if (resource === 'wood') p.city.progress.wood = (p.city.progress.wood ?? 0) + amount;
      else p.city.demo.wallet[resource] = (p.city.demo.wallet[resource] ?? 0) + amount;
    },
    healthyUnits: v92.healthyUnits,
    applyLosses: v92.applyLosses,
    applyLoot: v92.applyLoot,
    pushReport: v92.pushReport,
    creatureSpec: (species, level) => v92.creatureSpec(species, level) ?? null,
    protectedTownCells: v92.protectedTownCells ?? (() => []),
  };
}

export function errorResponse(error) {
  const e = error instanceof AdventureError ? error : toAdventureError(error);
  return {status: e.status, body: e.toBody()};
}

/**
 * Insertion points (see INTEGRATION_V92.md for the literal patch):
 *   settle (core.mjs:35)        await adventure.settle(p, now)                after settleKingdom(...)
 *   command (core.mjs:66)       const handled = await adventure.command({p, b, key, now, selectReceipt})
 *                               right after readyPlayer62 and BEFORE the legacy receipt SELECT;
 *                               returns null for every non-adventure kind (legacy flow unchanged).
 *   publicState (core.mjs:50)   state.adventure = adventure.publicState(p, now)
 *   paid branches (train/build/upgrade):   await adventure.afterVerifiedSpend(p, before, now)
 *   native session entry:       await adventure.enter(p, now)
 *   accounts40 importLegacy:    sanitizeLegacyImport(imported)
 */
export function createV92Adventure(v92) {
  const fr = createForestRescue({ports: createV92Ports(v92)});
  return {
    fr,
    isAdventureKind: fr.isAdventureKind,
    settle: (p, now) => fr.settle(p, now),
    publicState: (p, now) => fr.project(p, now),
    afterVerifiedSpend: (p, before, now) => fr.afterVerifiedSpend(p, before, now),
    enter: (p, now) => fr.enter(p, now),
    /**
     * Adventure branch of CoreGameServer.command. Order: hall gate → receipt SELECT (via
     * selectReceipt(key) → {signature}|null) → strict parse → effects on candidate p.
     * Returns null for other kinds. On success the caller performs its usual putPlayer(p) and
     * INSERT INTO commands(key, signature) in the SAME tx, then responds with publicState + events.
     */
    async command({p, b, key, now, selectReceipt}) {
      if (!fr.isAdventureKind(b?.kind)) return null;
      try {
        const out = await fr.command({p, body: b, key, now, receipts: {find: async k => selectReceipt(k)}});
        return {ok: true, replayed: out.replayed, events: out.events, receipt: out.receipt};
      } catch (error) {
        return {ok: false, ...errorResponse(error)};
      }
    },
  };
}

/** accounts40 importLegacy: a browser/legacy save can never carry adventure progress. */
export function sanitizeLegacyImport(imported) {
  if (!imported || typeof imported !== 'object') return imported;
  const out = structuredClone(imported);
  const roots = Object.values(NAMESPACES).map(([root]) => root);
  for (const target of [out, out.city].filter(x => x && typeof x === 'object')) for (const root of roots) delete target[root];
  return out;
}
