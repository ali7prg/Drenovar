// Local mirror of the v92 city economy rules the adventure needs (dist/city/kingdom29.js:
// hallLevel/balance/capacity; dist/city/upgrade-v1.js storage). The v92 source was not
// available in this session: the numbers come from delivery/docs/ECONOMY_RU.md and the
// client's godot/project/assets/game.json (cross-checked in tests/catalog.test.mjs).
// In v92 these functions are replaced by the real imports (see INTEGRATION_V92.md).
import {RESOURCES} from './content.mjs';

export const BASE_CAPACITY = 1200;
export const STORAGE_PER_LEVEL = Object.freeze({'ECO-05': 800, 'ECO-01': 1800, 'ECO-02': 500, 'ECO-04': 200});
export const VARIANT_BASE = Object.freeze({
  'ALT-01': 'RES-01', 'ALT-02': 'RES-01', 'ALT-03': 'RES-02', 'ALT-04': 'RES-03', 'ALT-05': 'RES-04', 'ALT-06': 'RES-05',
  'ALT-07': 'RES-04', 'ALT-08': 'SUP-01', 'ALT-09': 'RES-02', 'ALT-10': 'MIL-04', 'ALT-11': 'ECO-03', 'ALT-12': 'ECO-01',
  'ALT-13': 'ECO-05', 'ALT-14': 'ECO-04', 'ALT-15': 'ECO-02', 'ALT-16': 'SUP-05',
});
export const HALL_UPGRADES = Object.freeze([
  {cost: {wood: 260, food: 140, stone: 0, iron: 0, coins: 25}, seconds: 90},
  {cost: {wood: 450, food: 230, stone: 160, iron: 0, coins: 40}, seconds: 240},
  {cost: {wood: 700, food: 400, stone: 360, iron: 110, coins: 80}, seconds: 600},
  {cost: {wood: 1150, food: 600, stone: 700, iron: 300, coins: 150}, seconds: 1320},
]);

export function baseType(type) {
  return Object.hasOwn(VARIANT_BASE, type) ? VARIANT_BASE[type] : type;
}

/**
 * Actual completed town-hall level: the ECO-05 building's `level` (kingdom29.js:14).
 * Returns null when absent or not a safe positive integer (callers treat null as locked).
 * Never reads a pending construction order or any client value.
 */
export function hallLevel(city) {
  const hall = (city?.buildings ?? []).find(b => baseType(b?.type) === 'ECO-05');
  return hall && Number.isSafeInteger(hall.level) && hall.level >= 0 ? hall.level : null;
}

export function capacity(city) {
  let cap = BASE_CAPACITY;
  for (const b of city?.buildings ?? []) {
    const per = STORAGE_PER_LEVEL[baseType(b?.type)];
    if (per && Number.isSafeInteger(b.level) && b.level > 0) cap += per * b.level;
  }
  return cap;
}

/** Resource mapping: wood -> city.progress.wood; others -> city.demo.wallet[r]. */
export function balance(city, resource) {
  const value = resource === 'wood' ? city?.progress?.wood : city?.demo?.wallet?.[resource];
  return Number.isFinite(value) && value > 0 ? value : 0;
}

export function wallet(city) {
  return Object.fromEntries(RESOURCES.map(r => [r, balance(city, r)]));
}

/** Integer view for the delivered reducers (they require non-negative safe integers). */
export function integerWallet(city) {
  return Object.fromEntries(RESOURCES.map(r => [r, Math.min(Number.MAX_SAFE_INTEGER, Math.floor(balance(city, r)))]));
}

export function credit(city, resource, amount) {
  if (!Number.isSafeInteger(amount) || amount < 0) throw Object.assign(new Error('INVALID_CREDIT'), {code: 'INVALID_CREDIT'});
  if (amount === 0) return;
  if (resource === 'wood') {
    city.progress.wood = balance(city, 'wood') + amount;
  } else {
    city.demo.wallet[resource] = balance(city, resource) + amount;
  }
}

export function debit(city, resource, amount) {
  const current = balance(city, resource);
  if (!Number.isSafeInteger(amount) || amount < 0 || amount > current) throw Object.assign(new Error('INSUFFICIENT_FUNDS'), {code: 'INSUFFICIENT_FUNDS'});
  if (resource === 'wood') city.progress.wood = current - amount;
  else city.demo.wallet[resource] = current - amount;
}
