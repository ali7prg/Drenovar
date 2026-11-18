// Corrupt / future-schema saves fail closed (explicit error, bytes untouched), only absent
// namespaces are lazily initialised, and a real OS-process restart keeps everything.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, writeFileSync, rmSync} from 'node:fs';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {adventurer} from './helpers/setup.mjs';
import {Realm, Client, START_TIME, tempDir} from './helpers/realm.mjs';

const CASES = [
  ['adventures', 'STATE_CORRUPT', ns => { ns.escrow.pending.food += 1; }],
  ['adventures', 'SCHEMA_UNSUPPORTED', ns => { ns.schemaVersion = 2; }],
  ['adventures', 'STATE_CORRUPT', ns => { ns.sites.lf_site_01.artifact = 1; }],
  ['adventureMechanisms', 'STATE_CORRUPT', ns => { ns.lf_site_02 = {schemaVersion: 1, siteId: 'lf_site_02', kind: 'rune_lock', progress: ['leaf'], solved: false, revision: 1}; }],
  ['adventureMechanisms', 'STATE_CORRUPT', ns => { ns.lf_site_02 = {schemaVersion: 2, siteId: 'lf_site_02', kind: 'rune_lock', progress: [], solved: false, revision: 0}; }],
  ['adventureFog', 'STATE_CORRUPT', ns => { ns.exploredBase64 = 'AAAA'; }],
  ['adventureFog', 'SCHEMA_UNSUPPORTED', ns => { ns.schemaVersion = 2; }],
  ['adventureAccess', 'STATE_CORRUPT', ns => { ns.status = 'bogus'; }],
  ['adventureAccess', 'SCHEMA_UNSUPPORTED', ns => { ns.schemaVersion = 7; }],
  ['rewardReservePrefs', 'STATE_CORRUPT', ns => { ns.autoRefill = 'yes'; }],
  ['adventureField', 'STATE_CORRUPT', ns => { ns.squad.units = {'ENG-99': 1}; }],
  ['adventureField', 'SCHEMA_UNSUPPORTED', ns => { ns.schemaVersion = 2; }],
  ['adventureField', 'STATE_CORRUPT', ns => { ns.squad.node = 'lf_atlantis'; }],
];

test('corrupt and future-schema namespaces → explicit error on read and write, never a silent reset', {timeout: 120000}, async () => {
  const {realm, client, journey, playerId} = await adventurer({idPrefix: 'corrupt'});
  try {
    await journey.moveTo('lf_site_01');
    await journey.task('lf_site_01', 'discover');
    await client.ok('set_auto_refill', {enabled: true});
    await realm.stop();
    const pristine = readFileSync(realm.dbPath, 'utf8');
    for (const [root, code, mutate] of CASES) {
      const db = JSON.parse(pristine);
      mutate(db.players[playerId][root].forest_rescue_v1);
      const damaged = JSON.stringify(db);
      writeFileSync(realm.dbPath, damaged);
      await realm.start();
      const s = await client.state();
      assert.equal(s.adventure.error?.error, code, root + ' ' + code);
      assert.equal(s.adventure.error.detail.namespace, 'p.' + root + '.forest_rescue_v1');
      assert.ok(s.adventure.error.message.length > 10);
      assert.deepEqual(s.adventure.pois, []);
      assert.equal(s.adventure.access.unlocked, false);
      assert.ok(s.city && s.healthy, 'the rest of the game state is still served');
      for (const body of [client.adv('claim_rewards'), client.adv('move', {targetId: 'lf_home_reception'}), client.intro('skip_intro')]) {
        const r = await client.send(body);
        assert.equal(r.status, 409, root + ' ' + JSON.stringify(body));
        assert.equal(r.body.error, code);
      }
      await realm.stop();
      assert.equal(JSON.stringify(JSON.parse(readFileSync(realm.dbPath, 'utf8')).players[playerId]), JSON.stringify(db.players[playerId]), 'bytes untouched: ' + root);
      writeFileSync(realm.dbPath, pristine);
    }
    await realm.start();
    assert.equal((await client.state()).adventure.error, undefined);
  } finally {
    await realm.destroy();
  }
});

test('only absent namespaces are lazily initialised; existing ones are kept verbatim', async () => {
  const {realm, client, journey, playerId} = await adventurer({idPrefix: 'lazy', prologue: false});
  try {
    const raw = () => JSON.parse(readFileSync(realm.dbPath, 'utf8')).players[playerId];
    assert.equal(raw().adventures, undefined);
    await (await client.state()); // reading does not materialise anything
    assert.equal(raw().adventureFog, undefined);
    await journey.prologue({'ENG-06': 100});
    const p = raw();
    for (const ns of ['adventures', 'adventureMechanisms', 'adventureFog', 'adventureAccess', 'rewardReservePrefs', 'adventureField']) assert.ok(p[ns]?.forest_rescue_v1, ns);
    assert.deepEqual(p.rewardReservePrefs.forest_rescue_v1, {autoRefill: false});
    assert.equal(p.adventures.forest_rescue_v1.phase, 'rescue');
    // dropping ONE namespace (e.g. a lost preference record) re-initialises just that one
    await realm.stop();
    const db = JSON.parse(readFileSync(realm.dbPath, 'utf8'));
    delete db.players[playerId].rewardReservePrefs;
    writeFileSync(realm.dbPath, JSON.stringify(db));
    await realm.start();
    const s = await client.state();
    assert.equal(s.adventure.autoRefill, false);
    assert.equal(s.adventure.campaign.phase, 'rescue');
  } finally {
    await realm.destroy();
  }
});

test('real process restart (SIGTERM) keeps fog, movement, progress and rewards', {timeout: 60000}, async () => {
  const dir = tempDir('process');
  const dbPath = dir + '/realm.json';
  const server = fileURLToPath(new URL('../local-realm/server.mjs', import.meta.url));
  const launch = () => new Promise((ok, fail) => {
    const child = spawn(process.execPath, [server], {env: {...process.env, DRENOVAR_FR_PORT: '0', DRENOVAR_FR_DB: dbPath, DRENOVAR_FR_START_TIME: String(START_TIME)}, stdio: ['ignore', 'pipe', 'inherit']});
    let out = '';
    child.stdout.on('data', d => { out += d; const m = /LISTENING (\d+)/.exec(out); if (m) ok({child, url: 'http://127.0.0.1:' + m[1]}); });
    child.on('exit', code => fail(new Error('realm exited ' + code)));
  });
  const stop = child => new Promise(ok => { child.removeAllListeners('exit'); child.on('exit', ok); child.kill('SIGTERM'); });
  let proc = await launch();
  const realm = Object.assign(new Realm({dir}), {url: proc.url});
  const client = new Client(realm);
  try {
    assert.equal((await client.session()).status, 201);
    await client.hall(3);
    await client.army({'ENG-06': 200});
    await client.ok('form_squad', {units: {'ENG-06': 200}});
    await client.ok('move', {targetId: 'lf_horse_origin'});
    await client.advance(5000);
    await client.ok('discover_horse');
    const moving = await client.ok('move', {targetId: 'lf_site_01'});
    await client.advance(2500); // mid-move: a traversal checkpoint revealed fog
    const before = await client.state();
    assert.ok(before.adventure.fog.revision > 0);
    await stop(proc.child);
    proc = await launch();
    realm.url = proc.url;
    const after = await client.state();
    assert.deepEqual(after, before);
    const arrived = await client.advanceTo(moving.adventure.squad.move.arriveAt + 1);
    assert.equal(arrived.adventure.squad.node, 'lf_site_01');
    assert.deepEqual(arrived.adventure.escrow.earned, {food: 5000, wood: 5000, stone: 0, iron: 0, coins: 0});
  } finally {
    await stop(proc.child);
    rmSync(dir, {recursive: true, force: true});
  }
});
