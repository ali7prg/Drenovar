// Single import point for the delivered, byte-identical reference modules and data.
// The files under ../vendor/delivery are verified against SHA256SUMS (and against the
// original forest_rescue/delivery package when present) by tests/vendor-integrity.test.mjs.
import {readFileSync} from 'node:fs';

export * as campaignFsm from '../vendor/delivery/code/forest-rescue.mjs';
export * as access from '../vendor/delivery/code/adventure-access.mjs';
export * as mechanisms from '../vendor/delivery/code/mechanisms.mjs';
export * as fog from '../vendor/delivery/code/fog.mjs';
export * as introMigration from '../vendor/delivery/code/intro-migration.mjs';
export * as reserveRefill from '../vendor/delivery/code/reserve-refill.mjs';

export const VENDOR_DIR = new URL('../vendor/delivery/', import.meta.url);

function readJson(name) {
  return JSON.parse(readFileSync(new URL('data/' + name, VENDOR_DIR), 'utf8'));
}

// World geography: atlas v2 (owner decision 2026-11-21: the layout follows the art/01 masterplan)
// is server-owned data next to the sources; the delivered v1 atlas stays vendored byte-identical.
const ATLAS_V2 = new URL('../data/world-atlas.v2.json', import.meta.url);

export const data = Object.freeze({
  campaign: readJson('campaign.json'),
  economy: readJson('economy.json'),
  atlas: JSON.parse(readFileSync(ATLAS_V2, 'utf8')),
  atlasV1: readJson('world-atlas.json'),
  unlockIntro: readJson('unlock-intro.json'),
  persistence: readJson('persistence-contract.json'),
  uiRu: readJson('ui.ru.json'),
});
