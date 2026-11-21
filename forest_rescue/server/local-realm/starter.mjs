// New settlement template for the local realm, shaped like godot/tools/starter-state.json
// (the v92 public state the client already renders).
import {creatureSpec} from '../src/catalog.mjs';

function spec(species, level, map, biome) {
  const s = creatureSpec(species, level);
  return {...s, map, biome, materials: [5, 15, 30], assetStatus: 'animated_v2_prototype_art_pending'};
}

const CITY_ENCOUNTERS = [
  {species: 'tenerys', level: 1, home: {x: -44, z: -44}, hp: 1400},
  {species: 'tenerys', level: 2, home: {x: 36, z: -44}, hp: 3500},
  {species: 'tenerys', level: 3, home: {x: -44, z: 36}, hp: 8400},
];

export function newPlayer({id, login, now, name = 'Английское поселение'}) {
  return {
    id, login, name, createdAt: now,
    city: {
      schema: 1, id: 'city-' + id, ownerId: id, worldSlotId: 'slot-0', name, createdAt: now, sceneVersion: 2,
      progress: {schema: 1, wood: 500, xp: 0, rev: 0, felled: [], cleared: [], sites: [], job: null},
      buildings: [
        {id: 'building-v1-0', type: 'ECO-05', plotId: 'v1-0', level: 1},
        {id: 'building-v1-1', type: 'RES-01', plotId: 'v1-1', level: 1},
        {id: 'building-v1-2', type: 'RES-04', plotId: 'v1-2', level: 1},
        {id: 'building-v1-3', type: 'MIL-01', plotId: 'v1-3', level: 1},
      ],
      demo: {unlimitedResources: false, wallet: {food: 400, stone: 0, iron: 0, coins: 400}},
      military: {schema: 1, serial: 0, owned: {'ENG-01': 5}, queues: {}, receipts: {}, garrison: null},
      kingdom: {schema: 1, revision: 0, lastAt: now, carry: {}, clearedPlots: ['v1-0', 'v1-1', 'v1-2', 'v1-3'], order: null, receipts: {},
        guide: {entered: false, collected: false, seen: {}, skipped: false}},
    },
    wounded: {}, healing: [], items: {}, reports: [],
    encounters: CITY_ENCOUNTERS.map((e, i) => ({
      id: id + '-tenerys-' + (i + 1), owner: id, species: e.species, level: e.level, map: 'city',
      patrol: [e.home, {x: e.home.x + 4, z: e.home.z}, {x: e.home.x + 4, z: e.home.z + 4}, {x: e.home.x, z: e.home.z + 4}, e.home],
      home: e.home, position: e.home, status: 'alive', hp: e.hp, respawnAt: 0, reservedBy: null, spawnedAt: now, behavior: 'idle',
      spec: spec(e.species, e.level, 'city', 'woodland'),
    })),
  };
}

/** Static world encounters (decor only: hunting is not part of the local adventure realm). */
export function worldEncounters() {
  return [
    {id: 'velkor-1', level: 1, position: {x: -0.3463220833800733, z: -60.12934748083353}},
    {id: 'velkor-2', level: 2, position: {x: 13.212685558434668, z: -6.9091741899474535}},
    {id: 'velkor-3', level: 3, position: {x: 14.46700602537021, z: -45.68362508993596}},
  ].map(e => ({...e, patrol: [e.position, {x: e.position.x + 2.4, z: e.position.z}], spec: spec('velkor', e.level, 'world', 'forest'),
    status: 'alive', hp: creatureSpec('velkor', e.level).hp, respawnAt: 0}));
}

export const WORLD_POSITION = Object.freeze({x: -40.969794794451445, z: -29.41184992529452, y: 6.972052095588263});
