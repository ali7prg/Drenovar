// Records the client's CONTRACT §3 fixtures (godot/project/data/forest_rescue/game/fixtures/*.json)
// from a fresh local realm on the current atlas (v2: art/01 masterplan network). Every fixture is
// a full GET /api/state response at a named milestone of a normal, server-authoritative
// playthrough (same names and milestones as the v1 set the Godot QA and evidence scripts use).
//
//   node forest_rescue/server/tools/record-fixtures.mjs [out dir]
import {writeFileSync, mkdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {freshRealm} from '../tests/helpers/realm.mjs';
import {Journey, SITES} from '../tests/helpers/journey.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const out = process.argv[2] ?? path.resolve(here, '../../../godot/project/data/forest_rescue/game/fixtures');
mkdirSync(out, {recursive: true});
const ARMY = {'ENG-02': 30000, 'ENG-03': 30000, 'ENG-07': 30000};
const SQUAD = {'ENG-02': 25000, 'ENG-03': 25000, 'ENG-07': 25000};

const {realm, client} = await freshRealm({idPrefix: 'fixture'});
const journey = new Journey(realm, client);
const saved = [];
async function save(name, state = null) {
  const s = state ?? await client.state();
  writeFileSync(path.join(out, name + '.json'), JSON.stringify(s));
  saved.push(name);
  const a = s.adventure ?? {};
  console.log('FIXTURE', name.padEnd(24), 'phase', a.campaign?.phase, 'node', a.squad?.node, 'move', a.squad?.move?.targetId ?? '-', 'battle', a.battle?.outcome ?? '-');
}
const midMove = async (move, f = 0.45) => client.advanceTo(Math.round(move.departAt + (move.arriveAt - move.departAt) * f));

/** Rest of a site after its mechanism (rune lock / winch): optionally (re-)enter the solution. */
async function finishFromMechanism(siteId, inputs) {
  const site = SITES.find(s => s.id === siteId);
  if (inputs) {
    for (const symbol of site.artifact.puzzle.solution) {
      const r = await client.send(client.adv('mechanism_input', {siteId, symbol}));
      if (r.status !== 200) throw new Error('mechanism_input ' + symbol + ' ' + r.status + ' ' + JSON.stringify(r.body));
    }
  }
  await journey.moveTo(site.artifact.id);
  await journey.task(siteId, 'recover_artifact');
  await journey.moveTo(siteId + ':guardian');
  await journey.battle('engage_guardian', {siteId});
  await journey.task(siteId, 'defeat_guardian');
  await journey.moveTo(siteId + ':cage');
  await journey.task(siteId, 'unlock_cage');
  const esc = await client.ok('escort_start', {siteId});
  await client.advanceTo(esc.adventure.escort.arriveAt + 1);
  await journey.task(siteId, 'escort_home');
}

try {
  // ---- access and the hall III intro -----------------------------------------------------
  await client.hall(2);
  await save('locked_hall2');
  await client.hall(3);
  await client.army(ARMY);
  await save('intro_offer');
  const started = await client.send(client.intro('start_intro', {}));
  if (started.status !== 200) throw new Error('start_intro ' + started.status + ' ' + JSON.stringify(started.body));
  await save('intro_playing');
  const skipped = await client.send(client.intro('skip_intro', {}));
  if (skipped.status !== 200) throw new Error('skip_intro ' + skipped.status + ' ' + JSON.stringify(skipped.body));
  await save('prologue');
  // ---- prologue: the squad walks to the mare -------------------------------------------------
  await client.ok('form_squad', {units: SQUAD});
  const toHorse = await client.ok('move', {targetId: 'lf_horse_origin'});
  await save('prologue_moving', await midMove(toHorse.adventure.squad.move, 0.4));
  await client.advanceTo(toHorse.adventure.squad.move.arriveAt + 1);
  await client.ok('discover_horse');
  await save('horse_joined');
  // ---- site 01 (trail cache), step by step -------------------------------------------------
  const s1 = SITES.find(s => s.id === 'lf_site_01');
  await journey.moveTo('lf_site_01');
  await save('site01_arrived');
  await journey.task('lf_site_01', 'discover');
  await save('site01_discovered');
  const first = s1.artifact.puzzle.solution[0];
  await journey.moveTo('lf_site_01:landmark:' + first);
  await journey.input('lf_site_01', first);          // trail cache: the first mark entered at the mark (1 / 3)
  await save('site01_trail_1of3');
  await journey.moveTo(s1.artifact.id);
  for (const symbol of s1.artifact.puzzle.solution.slice(1)) await journey.input('lf_site_01', symbol);
  await journey.task('lf_site_01', 'recover_artifact');
  await save('site01_artifact_found');
  await journey.moveTo('lf_site_01:guardian');
  const fight = await client.ok('engage_guardian', {siteId: 'lf_site_01'});
  const b = fight.adventure.battle;
  await save('site01_battle_active', await client.advanceTo(Math.round(b.startedAt + (b.endsAt - b.startedAt) * 0.4)));
  await client.advanceTo(b.endsAt + 1);
  await save('site01_battle_victory');
  await journey.task('lf_site_01', 'defeat_guardian');
  await journey.moveTo('lf_site_01:cage');
  await journey.task('lf_site_01', 'unlock_cage');
  await save('site01_cage_open');
  const escort = await client.ok('escort_start', {siteId: 'lf_site_01'});
  await save('site01_escort_walking', await midMove(escort.adventure.escort, 0.35));
  await client.advanceTo(escort.adventure.escort.arriveAt + 1);
  await save('site01_escort_home');
  await journey.task('lf_site_01', 'escort_home');
  await save('site01_rescued');
  // ---- site 02 (rune lock): one correct, then a wrong input ----------------------------------
  await journey.completeSite('lf_site_02', {stopBefore: 'mechanism'});
  const s2 = SITES.find(s => s.id === 'lf_site_02');
  await journey.input('lf_site_02', s2.artifact.puzzle.solution[0]);
  await save('site02_rune_1of3');
  const wrong = s2.artifact.puzzle.symbols?.find?.(x => x !== s2.artifact.puzzle.solution[1]) ??
    ['mountain', 'waves', 'leaf', 'sun', 'moon'].find(x => x !== s2.artifact.puzzle.solution[1]);
  await client.send(client.adv('mechanism_input', {siteId: 'lf_site_02', symbol: wrong}));
  await save('site02_rune_wrong');
  await finishFromMechanism('lf_site_02', true);
  // ---- site 03 (winch) solved, site 04 (paired latch) plates held ------------------------------
  await journey.completeSite('lf_site_03', {stopBefore: 'mechanism'});
  const s3 = SITES.find(s => s.id === 'lf_site_03');
  for (const symbol of s3.artifact.puzzle.solution) await journey.input('lf_site_03', symbol);
  await save('site03_winch_solved');
  await finishFromMechanism('lf_site_03', false);
  await journey.completeSite('lf_site_04', {stopBefore: 'mechanism'});
  const plates = await client.ok('occupy_plates', {siteId: 'lf_site_04'});
  const poi4 = plates.adventure.pois.find(p => p.id === 'lf_site_04');
  await save('site04_plates_held', await client.advanceTo(poi4.mechanism.plates.readyAt + 1));
  const s4 = SITES.find(s => s.id === 'lf_site_04');
  for (const symbol of s4.artifact.puzzle.solution) await journey.input('lf_site_04', symbol);
  await journey.moveTo(s4.artifact.id);
  await journey.task('lf_site_04', 'recover_artifact');
  await journey.moveTo('lf_site_04:guardian');
  await journey.battle('engage_guardian', {siteId: 'lf_site_04'});
  await journey.task('lf_site_04', 'defeat_guardian');
  await journey.moveTo('lf_site_04:cage');
  await journey.task('lf_site_04', 'unlock_cage');
  const esc4 = await client.ok('escort_start', {siteId: 'lf_site_04'});
  await client.advanceTo(esc4.adventure.escort.arriveAt + 1);
  await journey.task('lf_site_04', 'escort_home');
  // ---- the rest of the campaign (hall V for act 3–4 and the boss) ----------------------------
  await client.hall(5);
  for (const site of SITES.slice(4)) await journey.completeSite(site.id);
  await save('boss_unlocked');
  await journey.formAtHome();
  const begin = await client.ok('move', {targetId: 'lf_boss_ancient_maw'});
  if (begin.adventure.squad.move) await client.advanceTo(begin.adventure.squad.move.arriveAt + 1);
  await client.ok('begin_boss');
  await save('boss_started');
  const boss = await client.ok('engage_boss');
  const bb = boss.adventure.battle;
  for (const pct of [10, 35, 60, 85]) {
    await save('boss_battle_' + pct, await client.advanceTo(Math.round(bb.startedAt + (bb.endsAt - bb.startedAt) * pct / 100)));
  }
  await client.advanceTo(bb.endsAt + 1);
  await client.ok('finish_boss');
  await save('completed');
  await client.ok('claim_rewards');
  await save('claimed');
  console.log('RECORDED', saved.length, 'fixtures →', out);
} finally {
  await realm.destroy();
}
