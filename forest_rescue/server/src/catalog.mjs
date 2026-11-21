// Troop and creature stat tables used by the deterministic battle adapter.
//
// TROOPS: the forest squad roster live on production (2026-11-21: ENG-01/02/03/04/06 only); every entry mirrors
// docs/06_TROOP_CATALOG.json (cross-checked by tests/catalog.test.mjs).
// CREATURES: tenerys/velkor levels 1–3 mirror the v92 creature specs exported to the
// client (godot/project/assets/game.json, godot/tools/starter-state.json). The v92
// catalog.mjs (`creatureSpec`) was NOT available in this session, so kamneklyk and
// dragor values are LOCAL CANDIDATES (dragor III hp/attack/defense are the real values
// quoted in delivery/docs/CAMPAIGN_BIBLE_RU.md). In v92 inject the real `creatureSpec`
// through the `creatureSpec` port; see INTEGRATION_V92.md.

const unit = (id, name, unitClass, power, attack, defense, hp, speed) => Object.freeze({id, name, unitClass, power, attack, defense, hp, speed});

export const TROOPS = Object.freeze({
  'ENG-01': unit('ENG-01', 'Копейщик', 'Пехота', 87, 53, 70, 135, 4),
  'ENG-02': unit('ENG-02', 'Мечник со щитом', 'Пехота', 107, 77, 78, 156, 4),
  'ENG-03': unit('ENG-03', 'Английский длиннолучник', 'Дальний бой', 83, 98, 28, 95, 4),
  'ENG-04': unit('ENG-04', 'Арбалетчик', 'Дальний бой', 91, 116, 35, 98, 3),
  'ENG-06': unit('ENG-06', 'Конный рыцарь', 'Тяжёлая конница', 200, 150, 125, 250, 7),
});

const RANGED = new Set(['Дальний бой', 'Лёгкие стрелки']);
export function isFrontLine(troop) {
  return !RANGED.has(troop.unitClass);
}

export function troop(unitId) {
  return Object.hasOwn(TROOPS, unitId) ? TROOPS[unitId] : null;
}

const LEVEL_XP = [15, 40, 100];
const LEVEL_HALL = [1, 3, 5];
const LEVEL_REWARDS = [{hides: 10, material: 5, rareChance: 0}, {hides: 25, material: 15, rareChance: 0.08}, {hides: 60, material: 30, rareChance: 0.2}];

function species(id, base, levels) {
  return Object.freeze({id, ...base, levels: Object.freeze(levels.map(Object.freeze))});
}

export const CREATURES = Object.freeze({
  tenerys: species('tenerys', {name: 'Тенерис', ability: 'pounce', speed: 6, range: 2, cooldown: 1.8, item: 'claws', rare: 'dusk_crystal', food: [1500, 4000, 10000], source: 'v92 spec mirrored in godot/tools/starter-state.json'}, [
    {strength: 15000, hp: 1400, attack: 80, defense: 25},
    {strength: 35000, hp: 3500, attack: 136, defense: 38},
    {strength: 90000, hp: 8400, attack: 240, defense: 55},
  ]),
  velkor: species('velkor', {name: 'Лесной Велькор', ability: 'antler_charge', speed: 4, range: 2.5, cooldown: 2.2, item: 'antlers', rare: 'forest_crystal', food: [1000, 3000, 8000], source: 'v92 spec mirrored in godot/tools/starter-state.json'}, [
    {strength: 10000, hp: 1900, attack: 95, defense: 35},
    {strength: 25000, hp: 4750, attack: 162, defense: 53},
    {strength: 60000, hp: 11400, attack: 285, defense: 77},
  ]),
  kamneklyk: species('kamneklyk', {name: 'Камнеклык', ability: 'tusk_charge', speed: 3.5, range: 2.2, cooldown: 2.6, item: 'fangs', rare: 'stone_crystal', food: [1500, 4500, 11000], source: 'LOCAL CANDIDATE — replace with v92 catalog.mjs creatureSpec'}, [
    {strength: 20000, hp: 2600, attack: 105, defense: 45},
    {strength: 48000, hp: 6500, attack: 180, defense: 70},
    {strength: 120000, hp: 16000, attack: 330, defense: 105},
  ]),
  dragor: species('dragor', {name: 'Драгор', ability: 'shockwave', speed: 3, range: 3, cooldown: 3.2, item: 'scales', rare: 'ember_crystal', food: [3000, 8000, 20000], source: 'LOCAL CANDIDATE (level III hp/attack/defense from CAMPAIGN_BIBLE_RU.md) — replace with v92 catalog.mjs creatureSpec'}, [
    {strength: 40000, hp: 6000, attack: 200, defense: 90},
    {strength: 95000, hp: 16500, attack: 360, defense: 160},
    {strength: 210000, hp: 39000, attack: 570, defense: 264},
  ]),
});

/** Same shape as the v92 `spec` objects visible in public state encounters. */
export function creatureSpec(speciesId, level) {
  const s = Object.hasOwn(CREATURES, speciesId) ? CREATURES[speciesId] : null;
  if (!s || !Number.isSafeInteger(level) || level < 1 || level > 3) return null;
  const l = s.levels[level - 1], r = LEVEL_REWARDS[level - 1];
  return Object.freeze({
    id: speciesId, level, name: s.name, strength: l.strength, hp: l.hp, attack: l.attack, defense: l.defense,
    speed: s.speed, range: s.range, cooldown: s.cooldown, ability: s.ability, item: s.item, rare: s.rare,
    xp: LEVEL_XP[level - 1], requiredHall: LEVEL_HALL[level - 1],
    rewards: Object.freeze({food: s.food[level - 1], hides: r.hides, material: r.material, rareChance: r.rareChance}),
    source: s.source,
  });
}
