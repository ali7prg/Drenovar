// Loading/saving the six owner-scoped adventure namespaces of ONE selected player p.
//   p.adventures.forest_rescue_v1          strict campaign state (delivered forest-rescue.mjs)
//   p.adventureMechanisms.forest_rescue_v1 per-site mechanism states (delivered mechanisms.mjs)
//   p.adventureFog.forest_rescue_v1        persistent exploration (delivered fog.mjs)
//   p.adventureAccess.forest_rescue_v1     hall-III intro lifecycle (delivered adventure-access.mjs)
//   p.rewardReservePrefs.forest_rescue_v1  {autoRefill:boolean}, default false
//   p.adventureField.forest_rescue_v1      movement/battle/escort records (field.mjs)
// Only an ABSENT namespace is lazily initialised. Anything present but invalid or of an
// unknown version raises STATE_CORRUPT / SCHEMA_UNSUPPORTED and nothing is written.
import {campaignFsm, mechanisms as mech, fog as fogModule, introMigration} from './vendor.mjs';
import {SITE_BY_ID, CAMPAIGN_ID} from './content.mjs';
import {initialField, deriveFieldFromCampaign, validateField} from './field.mjs';
import {resolveRef} from './navgraph.mjs';
import {AdventureError} from './errors.mjs';
import {clone, isPlainObject, hasExactKeys} from './util.mjs';

export const NAMESPACES = Object.freeze({
  campaign: ['adventures', CAMPAIGN_ID],
  mechanisms: ['adventureMechanisms', CAMPAIGN_ID],
  fog: ['adventureFog', CAMPAIGN_ID],
  intro: ['adventureAccess', CAMPAIGN_ID],
  prefs: ['rewardReservePrefs', CAMPAIGN_ID],
  field: ['adventureField', CAMPAIGN_ID],
});
const NAMES = Object.keys(NAMESPACES);

function pathText(name) {
  return 'p.' + NAMESPACES[name].join('.');
}

function namespaceError(name, error) {
  if (error instanceof AdventureError) return error;
  const reason = error?.code ?? error?.message ?? 'INVALID';
  const code = /UNSUPPORTED/.test(reason) ? 'SCHEMA_UNSUPPORTED' : 'STATE_CORRUPT';
  return new AdventureError(code, {detail: {namespace: pathText(name), reason, ...(error?.reason ? {at: error.reason} : {})}});
}

function read(p, name) {
  const [root, key] = NAMESPACES[name];
  const container = p[root];
  if (container === undefined) return undefined;
  if (!isPlainObject(container)) throw namespaceError(name, {code: 'INVALID_NAMESPACE_CONTAINER'});
  return container[key];
}

function loadMechanisms(saved) {
  if (saved === undefined) return {};
  if (!isPlainObject(saved)) throw Object.assign(new Error('INVALID_MECHANISM_STATE'), {code: 'INVALID_MECHANISM_STATE'});
  const out = {};
  for (const [siteId, state] of Object.entries(saved)) {
    const site = SITE_BY_ID.get(siteId);
    if (!site) throw Object.assign(new Error('INVALID_MECHANISM_STATE'), {code: 'INVALID_MECHANISM_STATE'});
    out[siteId] = clone(mech.validateMechanism(state, site.raw));
  }
  return out;
}

function loadPrefs(saved) {
  if (saved === undefined) return {autoRefill: false};
  if (!hasExactKeys(saved, ['autoRefill']) || typeof saved.autoRefill !== 'boolean') throw Object.assign(new Error('INVALID_PREFERENCE_STATE'), {code: 'INVALID_PREFERENCE_STATE'});
  return {autoRefill: saved.autoRefill};
}

function loadField(saved, campaign, graph) {
  if (saved === undefined) return {field: deriveFieldFromCampaign(campaign, graph.graphId), migrated: campaign.phase !== 'prologue', rebound: false};
  const field = clone(validateField(saved));
  if (field.graphId !== graph.graphId) {
    // A different navigation graph (e.g. atlas v1 → v2) may only be re-bound while nothing is in
    // motion and the squad stands on a named node that still exists (home, horse origin, a site
    // or its sub-targets); positions are node names, so they map 1:1. Anything else fails closed.
    const walking = Object.values(field.escorts).some(e => e.state === 'walking');
    if (field.squad.move !== null || walking || !graph.nodes.has(field.squad.node)) {
      throw Object.assign(new Error('NAV_GRAPH_MISMATCH'), {code: 'NAV_GRAPH_MISMATCH'});
    }
    field.graphId = graph.graphId;
    return {field, migrated: false, rebound: true};
  }
  if (!resolveRef(graph, field.squad.node)) throw Object.assign(new Error('NAV_GRAPH_MISMATCH'), {code: 'NAV_GRAPH_MISMATCH'});
  return {field, migrated: false, rebound: false};
}

/** Load (and lazily initialise absent) namespaces; throws AdventureError on bad data. */
export function loadBundle(p, graph) {
  const raw = {};
  for (const name of NAMES) raw[name] = read(p, name);
  const bundle = {raw, absent: Object.fromEntries(NAMES.map(n => [n, raw[n] === undefined]))};
  const step = (name, fn) => { try { fn(); } catch (error) { throw namespaceError(name, error); } };
  step('campaign', () => { bundle.campaign = campaignFsm.loadState(raw.campaign); });
  step('mechanisms', () => { bundle.mechanisms = loadMechanisms(raw.mechanisms); });
  step('fog', () => {
    if (raw.fog === undefined) bundle.fog = fogModule.createFogState();
    else { fogModule.validateFogState(raw.fog); bundle.fog = clone(raw.fog); }
  });
  step('intro', () => {
    const r = introMigration.migrateIntroForExistingCampaign(raw.intro, raw.campaign);
    bundle.intro = r.state;
    bundle.introMigrated = r.migrated;
  });
  step('prefs', () => { bundle.prefs = loadPrefs(raw.prefs); });
  step('field', () => {
    const r = loadField(raw.field, bundle.campaign, graph);
    bundle.field = r.field;
    bundle.fieldMigrated = r.migrated;
    // Explored cells of another graph follow its trails, not this one's: on a re-bind the fog
    // starts again from the delivered default (protected town; the squad re-reveals as it walks).
    if (r.rebound) {
      bundle.fog = fogModule.createFogState();
      bundle.graphRebound = true;
    }
  });
  bundle.loadedJson = Object.fromEntries(NAMES.map(n => [n, JSON.stringify(bundle[n])]));
  return bundle;
}

export function bundleChanged(bundle) {
  return NAMES.some(n => JSON.stringify(bundle[n]) !== bundle.loadedJson[n]);
}

/** Materialise every namespace on p (only called when the transaction changed something). */
export function writeBundle(p, bundle) {
  for (const name of NAMES) {
    const [root, key] = NAMESPACES[name];
    if (p[root] === undefined) p[root] = {};
    p[root][key] = clone(bundle[name]);
  }
}
