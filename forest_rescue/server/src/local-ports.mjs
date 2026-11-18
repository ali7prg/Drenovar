// Reference port implementation over the local-realm player shape
//   p = {id, city:{progress:{wood,xp}, demo:{wallet}, buildings, military:{owned}}, wounded, items, reports, ...}
// In drenovar-server v92 replace each port with the real function (INTEGRATION_V92.md).
import {hallLevel, capacity, integerWallet, credit, balance} from './city-rules.mjs';
import {creatureSpec} from './catalog.mjs';
import {normalizeUnits} from './util.mjs';

export const REPORT_LIMIT = 30;

export function healthyUnits(p) {
  const owned = p.city?.military?.owned ?? {};
  const wounded = p.wounded ?? {};
  const out = {};
  for (const [id, n] of Object.entries(owned)) {
    const h = (Number.isSafeInteger(n) ? n : 0) - (Number.isSafeInteger(wounded[id]) ? wounded[id] : 0);
    if (h > 0) out[id] = h;
  }
  return out;
}

export function createLocalPorts({reportLimit = REPORT_LIMIT} = {}) {
  return {
    hallLevel: p => hallLevel(p.city),
    capacity: p => capacity(p.city),
    integerWallet: p => integerWallet(p.city),
    credit: (p, resource, amount) => credit(p.city, resource, amount),
    healthyUnits,
    /** Like ordinary hunts: dead leave the army, wounded stay owned but not healthy. */
    applyLosses(p, {wounded, dead}) {
      const owned = p.city.military.owned;
      p.wounded ??= {};
      const applied = {wounded: {}, dead: {}};
      for (const id of new Set([...Object.keys(wounded), ...Object.keys(dead)])) {
        const healthy = Math.max(0, (owned[id] ?? 0) - (p.wounded[id] ?? 0));
        const d = Math.min(dead[id] ?? 0, healthy);
        const w = Math.min(wounded[id] ?? 0, healthy - d);
        if (d > 0) { owned[id] -= d; applied.dead[id] = d; }
        if (w > 0) { p.wounded[id] = (p.wounded[id] ?? 0) + w; applied.wounded[id] = w; }
        if (owned[id] === 0) delete owned[id];
      }
      p.city.military.owned = normalizeUnits(owned);
      p.wounded = normalizeUnits(p.wounded);
      return applied;
    },
    /** Ordinary first-victory loot: resources only up to free storage (overflow reported). */
    applyLoot(p, loot) {
      const out = {resources: {}, items: {}, xp: 0, overflow: {}};
      for (const [r, amount] of Object.entries(loot.resources ?? {})) {
        const free = Math.max(0, Math.floor(capacity(p.city) - balance(p.city, r)));
        const credited = Math.min(amount, free);
        if (credited > 0) { credit(p.city, r, credited); out.resources[r] = credited; }
        if (amount - credited > 0) out.overflow[r] = amount - credited;
      }
      p.items ??= {};
      for (const [k, n] of Object.entries(loot.items ?? {})) { p.items[k] = (p.items[k] ?? 0) + n; out.items[k] = n; }
      if (loot.xp > 0) { p.city.progress.xp = (p.city.progress.xp ?? 0) + loot.xp; out.xp = loot.xp; }
      return out;
    },
    pushReport(p, report) {
      p.reports ??= [];
      p.reports.push(report);
      if (p.reports.length > reportLimit) p.reports.splice(0, p.reports.length - reportLimit);
    },
    creatureSpec,
    protectedTownCells: () => [],
  };
}
