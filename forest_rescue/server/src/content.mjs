// Static, server-owned content model built ONLY from the delivered data files.
// Nothing here comes from a request body. Fails fast at import time when the delivered
// data and the delivered FSM constants disagree.
import {data, campaignFsm} from './vendor.mjs';
import {stableShuffle} from './util.mjs';

const {campaign, atlas, atlasV1} = data;
export const CAMPAIGN_ID = campaignFsm.CAMPAIGN_ID;
export const SITE_IDS = campaignFsm.SITE_IDS;
export const TASKS = campaignFsm.TASKS;
export const RESOURCES = campaignFsm.RESOURCES;

export const HOME_ID = 'lf_home_reception';
export const HORSE_ID = campaignFsm.HORSE_ID; // lf_horse_origin
export const BRIDGE_ID = 'lf_bridge_crossing';
export const BOSS_TARGET_ID = campaignFsm.BOSS_ID; // lf_boss_ancient_maw
export const BOSS_ENCOUNTER_ID = campaign.boss.encounterId;
export const BOSS_SPECIES = campaignFsm.BOSS_SPECIES;
export const BOSS_REQUIRED_HALL = campaign.boss.requiredHall;

// Presentation-only mappings (stable, documented in CONTRACT.md changelog v1.1).
const CAGE_VARIANTS = ['oak', 'iron', 'root'];
const FAMILY_BY_MECHANISM = Object.freeze({
  trail_cache: 'amber_crystal', rune_lock: 'stone_rune', winch_sequence: 'bronze_seal', paired_latch: 'bone_key',
});
const CIVILIAN_VISUALS = ['miller', 'herbalist', 'ferryman', 'courier', 'cooper', 'quarry_worker'];

function assert(condition, code) {
  if (!condition) throw Object.assign(new Error(code), {code});
}

assert(campaign.id === CAMPAIGN_ID && atlas.campaignId === CAMPAIGN_ID, 'CONTENT_CAMPAIGN_MISMATCH');
assert(campaign.sites.length === 12 && atlas.sites.length === 12, 'CONTENT_SITE_COUNT');

export const SITES = Object.freeze(campaign.sites.map((raw, index) => {
  const id = SITE_IDS[index];
  assert(raw.id === id, 'CONTENT_SITE_ORDER');
  const spec = campaignFsm.guardianSpec(id);
  assert(raw.guardian.species === spec.species && raw.guardian.level === spec.level &&
    (raw.guardian.modifier ?? null) === spec.modifier && raw.guardian.requiredHall === spec.requiredHall, 'CONTENT_GUARDIAN_MISMATCH');
  assert(raw.artifact.id === campaignFsm.artifactId(id), 'CONTENT_ARTIFACT_MISMATCH');
  const captiveIds = campaignFsm.captiveIds(id);
  assert(raw.captives.length === 3 && raw.captives.every((c, i) => c.id === captiveIds[i]), 'CONTENT_CAPTIVE_MISMATCH');
  // The delivered campaign references the delivered v1 layout; atlas v2 (owner decision, art/01
  // masterplan) moves the glades — the site ids, order and everything else stay as delivered.
  const v1 = atlasV1.sites.find(s => s.id === id);
  assert(v1 && v1.center.x === raw.layoutCenterXZReference[0] && v1.center.z === raw.layoutCenterXZReference[1], 'CONTENT_ATLAS_MISMATCH');
  const place = atlas.sites.find(s => s.id === id);
  assert(place, 'CONTENT_ATLAS_MISMATCH');
  const solution = Object.freeze([...raw.artifact.puzzle.solution]);
  return Object.freeze({
    id, number: raw.number, name: raw.name, act: raw.act, variation: raw.variation,
    multiplier: campaignFsm.siteMultiplier(id),
    guardian: Object.freeze({species: spec.species, level: spec.level, modifier: spec.modifier, requiredHall: spec.requiredHall}),
    artifact: Object.freeze({id: raw.artifact.id, name: raw.artifact.name, family: FAMILY_BY_MECHANISM[raw.variation]}),
    puzzle: Object.freeze({clue: raw.artifact.puzzle.clue, solution, symbols: Object.freeze(stableShuffle(solution, id))}),
    captives: Object.freeze(raw.captives.map((c, i) => Object.freeze({
      id: c.id, name: c.name, role: c.role, visual: CIVILIAN_VISUALS[(index * 3 + i) % CIVILIAN_VISUALS.length],
    }))),
    cage: CAGE_VARIANTS[index % CAGE_VARIANTS.length],
    center: Object.freeze({...place.center}),
    clearingRadius: place.clearingRadius,
    offsets: Object.freeze({
      cage: place.cageOffset, guardian: place.guardianOffset, artifact: place.artifactOffset, escape: place.escapeApproachOffset,
    }),
    tasks: Object.freeze(raw.tasks.map(t => Object.freeze({id: t.id, title: t.title, objective: t.objective, resultText: t.resultText}))),
    raw, // the authored definition handed to the delivered mechanisms.mjs
  });
}));

export const SITE_BY_ID = new Map(SITES.map(s => [s.id, s]));
export function siteDef(siteId) {
  const site = SITE_BY_ID.get(siteId);
  assert(site, 'UNKNOWN_SITE');
  return site;
}

export const BOSS = Object.freeze({
  encounterId: BOSS_ENCOUNTER_ID,
  species: BOSS_SPECIES,
  name: campaign.boss.displayName,
  requiredHall: BOSS_REQUIRED_HALL,
  stats: Object.freeze({...campaign.boss.candidateStats}),
  phases: Object.freeze(campaign.boss.phases.map(p => Object.freeze({id: p.id, hpAboveFraction: p.hpAboveFraction, attacks: Object.freeze([...p.attacks])}))),
  attacks: Object.freeze(Object.fromEntries(Object.entries(campaign.boss.attacks).map(([k, v]) => [k, Object.freeze({...v})]))),
  center: Object.freeze({...atlas.landmarks.find(l => l.id === 'lf_boss_arena').center}),
});
assert(BOSS.species === 'ancient_maw' && BOSS.encounterId === BOSS_TARGET_ID, 'CONTENT_BOSS_MISMATCH');

export function guardianEncounterId(siteId) {
  siteDef(siteId);
  return CAMPAIGN_ID + ':' + siteId + ':guardian';
}

export function actOfSite(siteId) {
  return siteDef(siteId).act;
}

/** Site -> act index 0..3; previous-act completion gates match forest-rescue.mjs. */
export function actUnlocked(campaignState) {
  if (campaignState.phase === 'prologue') return [false, false, false, false];
  const done = id => campaignState.sites[id].step === 5;
  return [0, 1, 2, 3].map(act => SITE_IDS.slice(0, act * 3).every(done));
}

export const TEXTS = Object.freeze({
  ui: data.uiRu.strings,
  intro: data.unlockIntro.texts,
});
