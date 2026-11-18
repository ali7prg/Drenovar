import {createHash} from 'node:crypto';

export const clone = structuredClone;

export function sha256Hex(text) {
  return createHash('sha256').update(text).digest('hex');
}

/** FNV-1a 32 bit; deterministic seed derivation (not a security primitive). */
export function fnv1a(text) {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

/** mulberry32 deterministic PRNG returning floats in [0,1). */
export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value) &&
    (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
}

export function hasExactKeys(value, keys) {
  if (!isPlainObject(value)) return false;
  const own = Object.keys(value);
  return own.length === keys.length && keys.every(k => Object.hasOwn(value, k));
}

export function isCount(n) {
  return Number.isSafeInteger(n) && n >= 0;
}

export function isTime(n) {
  return Number.isSafeInteger(n) && n >= 0;
}

export function round(x, digits = 3) {
  const f = 10 ** digits;
  return Math.round(x * f) / f;
}

export function sumUnits(units) {
  let total = 0;
  for (const n of Object.values(units ?? {})) total += n;
  return total;
}

/** Remove zero entries and sort keys for stable JSON. */
export function normalizeUnits(units) {
  const out = {};
  for (const key of Object.keys(units ?? {}).sort()) if (units[key] > 0) out[key] = units[key];
  return out;
}

export function addUnits(a, b) {
  const out = {...a};
  for (const [k, n] of Object.entries(b ?? {})) out[k] = (out[k] ?? 0) + n;
  return normalizeUnits(out);
}

export function stableShuffle(list, salt) {
  return [...list].sort((x, y) => (fnv1a(salt + ':' + x) - fnv1a(salt + ':' + y)) || (x < y ? -1 : x > y ? 1 : 0));
}
