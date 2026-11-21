// Embedded tables are cross-checked against the real sources available in this repo.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, existsSync} from 'node:fs';
import {TROOPS, creatureSpec, CREATURES} from '../src/catalog.mjs';
import {STORAGE_PER_LEVEL, VARIANT_BASE, HALL_UPGRADES, capacity, hallLevel, baseType, balance} from '../src/city-rules.mjs';
import {SITES, BOSS} from '../src/content.mjs';
import {data, campaignFsm} from '../src/vendor.mjs';
import {newPlayer} from '../local-realm/starter.mjs';

const repo = new URL('../../../', import.meta.url);
const readJson = path => JSON.parse(readFileSync(new URL(path, repo), 'utf8'));
const has = path => existsSync(new URL(path, repo));

test('troop stats mirror docs/06_TROOP_CATALOG.json (forest roster: the 5 live units)', {skip: !has('docs/06_TROOP_CATALOG.json')}, () => {
  const catalog = readJson('docs/06_TROOP_CATALOG.json').units.map(u => u.unit);
  // production roster 2026-11-21: only ENG-01/02/03/04/06 may join a forest squad
  assert.deepEqual(Object.keys(TROOPS).sort(), ['ENG-01', 'ENG-02', 'ENG-03', 'ENG-04', 'ENG-06']);
  for (const id of Object.keys(TROOPS)) {
    const t = TROOPS[id];
    const u = catalog.find(c => c.id === id);
    assert.ok(u, id);
    assert.deepEqual([t.name, t.unitClass, t.power, t.attack, t.defense, t.hp, t.speed], [u.name, u.unit_class, u.power, u.attack, u.defense, u.hp, u.speed], id);
  }
});

test('tenerys/velkor specs mirror the v92 specs exported to the client', {skip: !has('godot/tools/starter-state.json')}, () => {
  const starter = readJson('godot/tools/starter-state.json');
  const specs = [...starter.encounters, ...starter.world.encounters].map(e => e.spec);
  assert.equal(specs.length, 6);
  for (const s of specs) {
    const mine = creatureSpec(s.id, s.level);
    for (const k of ['name', 'strength', 'hp', 'attack', 'defense', 'speed', 'range', 'cooldown', 'ability', 'item', 'rare', 'xp', 'requiredHall']) {
      assert.equal(mine[k], s[k], s.id + s.level + '.' + k);
    }
    assert.deepEqual({...mine.rewards}, s.rewards);
  }
  // Every campaign guardian has a spec; candidates are labelled as such.
  for (const site of SITES) assert.ok(creatureSpec(site.guardian.species, site.guardian.level), site.id);
  assert.match(CREATURES.dragor.source, /CANDIDATE/);
  assert.match(CREATURES.kamneklyk.source, /CANDIDATE/);
  assert.deepEqual([creatureSpec('dragor', 3).hp, creatureSpec('dragor', 3).attack, creatureSpec('dragor', 3).defense], [39000, 570, 264]);
  assert.equal(creatureSpec('tenerys', 4), null);
  assert.equal(creatureSpec('ancient_maw', 1), null, 'the boss is not registered as an old species');
});

test('city rules mirror the client game data and the delivered economy figures', {skip: !has('godot/project/assets/game.json')}, () => {
  const game = readJson('godot/project/assets/game.json');
  for (const [type, terms] of Object.entries(game.buildingTerms)) {
    if (terms.storage && baseType(type) === type) assert.equal(STORAGE_PER_LEVEL[type], terms.storage, type);
  }
  for (const b of game.buildings) if (b.base !== b.id) assert.equal(VARIANT_BASE[b.id], b.base, b.id);
  assert.deepEqual(HALL_UPGRADES, game.buildingTerms['ECO-05'].upgrades);
  const city = newPlayer({id: 'x', login: 'l', now: 0}).city;
  assert.equal(capacity(city), data.economy.verifiedCapacityExamples.newKingdomEachResource);
  const fives = {...city, buildings: ['ECO-05', 'ECO-01', 'ECO-02', 'ECO-04'].map(type => ({type, level: 5}))};
  assert.equal(capacity(fives), data.economy.verifiedCapacityExamples.oneOfEachSupportedStorageAtLevel5EachResource);
  assert.equal(hallLevel(city), 1);
  assert.equal(hallLevel({buildings: [{type: 'ALT-13', level: 4}]}), 4, 'hall variant counts');
  assert.equal(hallLevel({buildings: [{type: 'ECO-05', level: '3'}]}), null, 'a string level is not a hall level');
  assert.equal(hallLevel({buildings: []}), null);
  assert.equal(balance(city, 'wood'), 500, 'wood lives in city.progress.wood');
  assert.equal(balance(city, 'food'), 400, 'food lives in city.demo.wallet');
});

test('content model matches the delivered campaign data and FSM', () => {
  for (const site of SITES) {
    assert.deepEqual({...site.guardian}, campaignFsm.guardianSpec(site.id));
    assert.equal(site.captives.length, 3);
    assert.deepEqual([...site.puzzle.symbols].sort(), [...site.puzzle.solution].sort());
  }
  assert.equal(SITES[0].guardian.species, 'tenerys');
  assert.equal(SITES[0].guardian.level, 1, 'first guardian is Tenerys I');
  assert.equal(SITES[0].captives[0].visual, 'miller', 'matches the CONTRACT example');
  assert.deepEqual(BOSS.stats, data.campaign.boss.candidateStats);
  assert.deepEqual(BOSS.phases.map(p => p.id), ['hunt', 'fury', 'last_stand']);
  assert.deepEqual(campaignFsm.campaignMaximumReward(), data.economy.totals);
});
