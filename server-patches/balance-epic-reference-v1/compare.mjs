// Balance profile epic_reference_v1 (inactive) adapted to the server's combat scale, and its
// comparison with the live catalog on fixed parties, using the server's own simulate().
// Usage (Node 24.22.1): node compare.mjs <path to DRENOVAR-Server-v92> [out-dir]
// Nothing here is read by the game; activating a profile is a separate, reviewed change.
import {readFileSync, writeFileSync} from 'node:fs';
import {join, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
const here = dirname(fileURLToPath(import.meta.url));
const root = process.argv[2] ?? '../../../drenovar-server/DRENOVAR-Server-v92';
const out = process.argv[3] ?? here;
const {simulate} = await import(join(root, 'gameplay37/server/combat.mjs'));
const {creatureSpec, units} = await import(join(root, 'gameplay37/server/catalog.mjs'));
const poster = JSON.parse(readFileSync(join(here, 'reference_poster.json'), 'utf8'));

// Adaptation: the poster's absolute numbers (HP 18 000, attack 1 200 ...) are another scale than
// the server (Velkor I: 1 900 / 95 / 35). Level I stays anchored on the live values (first hunts,
// tutorial, existing players unchanged); levels II/III take the poster's progression
// (poster stat at level L / poster stat at level I). Rewards are mapped to existing keys only.
const KEYS = {velkor: 'antlers', kamneklyk: 'bones', tenerys: 'claws', dragor: 'armor_plates'};
const profile = {preset_id: 'epic_reference_v1', status: 'INACTIVE_PROPOSAL', auto_apply: false,
  method: 'level I = live catalog; level II/III = live level I x poster(level)/poster(level I); rewards on existing item keys',
  creatures: {}};
for (const c of poster.creatures) {
  const l1 = creatureSpec(c.id, 1), p1 = c.levels[0];
  profile.creatures[c.id] = c.levels.map(p => {
    const r = Object.fromEntries(p.guaranteed_rewards.map(x => [x.key, x.quantity]));
    const material = r[KEYS[c.id]] ?? r.mineral ?? null;
    return {level: p.level,
      hp: Math.round(l1.hp * p.hp / p1.hp), attack: Math.round(l1.attack * p.attack / p1.attack),
      defense: Math.round(l1.defense * p.defense / p1.defense),
      recommended_power_hint: p.recommended_power,
      rewards: {food: r.food, hides: r.hides, [KEYS[c.id]]: material},
      unmapped_rewards: p.guaranteed_rewards.filter(x => x.requires_catalog_mapping).map(x => ({key: x.key, name: x.display_name ?? x.key, quantity: x.quantity}))};
  });
}
// Fixed parties (same seed for both presets).
const PARTIES = {
  recruits_25: {'ENG-09': 25},
  recruits_60: {'ENG-09': 60},
  spears_swords_120: {'ENG-01': 60, 'ENG-02': 60},
  mixed_200: {'ENG-01': 60, 'ENG-02': 50, 'ENG-03': 50, 'ENG-05': 20, 'ENG-07': 20},
  army_400: {'ENG-01': 120, 'ENG-02': 100, 'ENG-03': 100, 'ENG-04': 30, 'ENG-06': 50},
};
const sum = b => Object.values(b ?? {}).reduce((n, q) => n + q, 0);
const rows = [];
for (const id of ['tenerys', 'velkor', 'kamneklyk', 'dragor']) for (const level of [1, 2, 3]) {
  const live = creatureSpec(id, level), a = profile.creatures[id][level - 1];
  const adapted = {...live, hp: a.hp, attack: a.attack, defense: a.defense};
  for (const [name, party] of Object.entries(PARTIES)) {
    const run = spec => { const r = simulate(party, spec, 0x5eed); return {outcome: r.outcome, duration_s: r.duration / 1000, dead: sum(r.dead), wounded: sum(r.wounded), surviving: sum(r.surviving)}; };
    rows.push({species: id, level, party: name, soldiers: sum(party), live: {hp: live.hp, attack: live.attack, defense: live.defense, ...run(live)},
      adapted: {hp: a.hp, attack: a.attack, defense: a.defense, ...run(adapted)}});
  }
}
writeFileSync(join(out, 'epic_reference_v1.adapted.json'), JSON.stringify(profile, null, 1) + '\n');
writeFileSync(join(out, 'comparison.json'), JSON.stringify({engine: 'gameplay37/server/combat.mjs simulate()', seed: 0x5eed, parties: PARTIES, rows}, null, 1) + '\n');
const md = ['| Вид | Ур. | Отряд | Живой баланс: HP/атака/защита → итог, с, погибли/ранены | Профиль: HP/атака/защита → итог, с, погибли/ранены |', '|---|---|---|---|---|'];
for (const r of rows) md.push(`| ${r.species} | ${r.level} | ${r.party} | ${r.live.hp}/${r.live.attack}/${r.live.defense} → ${r.live.outcome}, ${r.live.duration_s}, ${r.live.dead}/${r.live.wounded} | ${r.adapted.hp}/${r.adapted.attack}/${r.adapted.defense} → ${r.adapted.outcome}, ${r.adapted.duration_s}, ${r.adapted.dead}/${r.adapted.wounded} |`);
writeFileSync(join(out, 'comparison.md'), md.join('\n') + '\n');
console.log(`rows ${rows.length}; outcome changes ${rows.filter(r => r.live.outcome !== r.adapted.outcome).length}`);
