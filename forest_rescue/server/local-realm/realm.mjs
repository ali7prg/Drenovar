// Local loopback realm: the transport/transaction shell around the adventure module, playing
// the role of v92 hosted.mjs (snapshot CAS) + CoreGameServer (readyPlayer → gate → receipt →
// branch → putPlayer + INSERT receipt) for a single machine. NOT a production server.
import {randomUUID} from 'node:crypto';
import {SnapshotStore} from './store.mjs';
import {newPlayer, worldEncounters, WORLD_POSITION} from './starter.mjs';
import {createForestRescue, createLocalPorts, healthyUnits, AdventureError, TROOPS} from '../src/index.mjs';
import {HALL_UPGRADES, baseType, hallLevel, balance, debit, integerWallet} from '../src/city-rules.mjs';
import {RESOURCES} from '../src/content.mjs';
import {isPlainObject, normalizeUnits, clone} from '../src/util.mjs';

export const DEFAULT_LOGIN = 'native-loopback-tester';
export const RECEIPT_LIMIT = 2000;
const MAX_ATTEMPTS = 8;

const UNSUPPORTED = 'Это действие недоступно в локальном мире приключения «Лес потерянных». Город, стройка и армия здесь упрощены.';

function httpError(status, code, message, detail) {
  return Object.assign(new Error(code), {httpStatus: status, body: {error: code, message, ...(detail ? {detail} : {})}});
}

const yieldTurn = () => new Promise(resolve => setImmediate(resolve));

export function createRealm({dbPath, idFactory = () => randomUUID(), buildSeconds = Number(process.env.DRENOVAR_FR_BUILD_SECONDS ?? 10), hooks = {}, startTime = null} = {}) {
  if (!dbPath) throw new Error('dbPath required');
  const store = new SnapshotStore(dbPath);
  if (startTime !== null && store.data.clock.simulated === null && store.revision === 0) {
    store.data.clock.simulated = startTime;
    store.persist();
  }
  const ports = createLocalPorts();
  const fr = createForestRescue({ports});

  const clock = data => data.clock.simulated ?? Date.now();

  /** Revision-checked transaction with retry on conflict (fresh snapshot each attempt). */
  async function transact(fn) {
    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
      const {revision, data} = store.read();
      const result = await fn(data, attempt);
      if (result?.noWrite) return result;
      await yieldTurn(); // lets concurrent requests interleave so CAS is really exercised
      if (hooks.beforeCommit) await hooks.beforeCommit({attempt, store});
      if (store.commit(revision, data)) return result;
    }
    throw new AdventureError('CAS_CONFLICT_RETRY');
  }

  function selectPlayer(data, login, selected, {required = true} = {}) {
    const ids = data.logins[login] ?? [];
    if (selected) {
      if (!data.players[selected]) throw httpError(404, 'PROFILE_UNKNOWN', 'Поселение не найдено.');
      if (!ids.includes(selected)) throw httpError(403, 'PROFILE_FORBIDDEN', 'Это поселение принадлежит другому аккаунту.');
      return data.players[selected];
    }
    if (!ids.length) {
      if (required) throw httpError(409, 'NEEDS_SETTLEMENT', 'Сначала основайте поселение.');
      return null;
    }
    return data.players[ids[0]];
  }

  /** Local stand-in for settleKingdom: completes a finished hall upgrade order. */
  function settleKingdom(p, now) {
    const order = p.city.kingdom?.order;
    if (!order || order.kind !== 'upgrade' || now < order.endsAt) return false;
    const building = p.city.buildings.find(b => b.id === order.buildingId);
    if (building) building.level = order.level; // the actual completed level the hall gate reads
    p.city.kingdom.order = null;
    p.city.kingdom.revision++;
    p.city.kingdom.lastAt = now;
    return true;
  }

  async function readyPlayer(p, now) {
    const kingdom = settleKingdom(p, now);
    const adventure = await fr.settle(p, now);
    return {changed: kingdom || adventure.changed, events: adventure.events};
  }

  function publicState(data, p, now) {
    const adventure = fr.project(p, now);
    const reserved = adventure.squad?.units ?? {};
    const healthy = {};
    for (const [id, n] of Object.entries(healthyUnits(p))) {
      const free = n - (reserved[id] ?? 0);
      if (free > 0) healthy[id] = free;
    }
    const hall = hallLevel(p.city) ?? 1;
    return {
      serverTime: now,
      playerId: p.id,
      starterEligible71: false,
      world: {
        cities: [{id: p.id, name: p.city.name, level: hall, slot: p.city.worldSlotId, position: {...WORLD_POSITION}, pvp: false, pvpReason: 'Локальный мир приключения'}],
        encounters: worldEncounters(),
        armies: [],
      },
      city: clone(p.city),
      healthy,
      wounded: clone(p.wounded ?? {}),
      healing: clone(p.healing ?? []),
      items: clone(p.items ?? {}),
      reports: clone(p.reports ?? []),
      encounters: clone(p.encounters ?? []),
      armies: [],
      profiles: (data.logins[p.login] ?? []).map(id => ({playerId: id, name: data.players[id].name})),
      adventure,
    };
  }

  function receiptsFor(data, p) {
    data.commands[p.id] ??= {};
    const table = data.commands[p.id];
    return {
      find: async key => (Object.hasOwn(table, key) ? table[key] : null),
      insert(receipt, now) {
        table[receipt.key] = {signature: receipt.signature, kind: receipt.kind, action: receipt.action ?? null, at: now};
        const keys = Object.keys(table);
        if (keys.length > RECEIPT_LIMIT) for (const k of keys.slice(0, keys.length - RECEIPT_LIMIT)) delete table[k];
      },
    };
  }

  // ------------------------------------------------------------------ HTTP-facing API
  async function getState({login = DEFAULT_LOGIN, selected = null}) {
    return transact(async data => {
      const p = selectPlayer(data, login, selected, {required: false});
      if (!p) return {noWrite: true, status: 200, body: {needsSettlement: true}};
      const now = clock(data);
      const ready = await readyPlayer(p, now);
      const body = publicState(data, p, now);
      return ready.changed ? {status: 200, body} : {noWrite: true, status: 200, body};
    });
  }

  async function sessionNew({login = DEFAULT_LOGIN, selected = null, body = {}}) {
    if (body !== null && !isPlainObject(body)) throw httpError(400, 'BAD_FIELDS', 'Неверный формат запроса.');
    const extra = Object.keys(body ?? {}).filter(k => !['additional', 'name'].includes(k));
    if (extra.length) throw httpError(400, 'BAD_FIELDS', 'Неверный формат запроса.', {fields: extra});
    return transact(async data => {
      const now = clock(data);
      const ids = data.logins[login] ?? [];
      if (!ids.length || body?.additional === true) {
        const id = idFactory();
        const p = newPlayer({id, login, now, name: typeof body?.name === 'string' && body.name.length <= 40 ? body.name : undefined});
        data.players[id] = p;
        data.logins[login] = [...ids, id];
        return {status: 201, body: {...publicState(data, p, now), created: true}};
      }
      // Existing settlement: a new foreground entry (intro reconciliation), no new profile.
      const p = selectPlayer(data, login, selected);
      await readyPlayer(p, now);
      const entry = await fr.enter(p, now);
      return {status: 200, body: {...publicState(data, p, now), created: false, events: entry.events}};
    });
  }

  async function command({login = DEFAULT_LOGIN, selected = null, key = null, body}) {
    if (!isPlainObject(body)) throw httpError(400, 'BAD_FIELDS', 'Неверный формат команды.');
    return transact(async data => {
      const p = selectPlayer(data, login, selected);
      const now = clock(data);
      await readyPlayer(p, now); // v92 readyPlayer62: settle with server now
      const receipts = receiptsFor(data, p);
      if (fr.isAdventureKind(body.kind)) {
        // fr.command applies the hall gate BEFORE the receipt lookup, then replay/409, then effects.
        const r = await fr.command({p, body, key, now, receipts});
        if (r.receipt) receipts.insert(r.receipt, now);
        return {status: 200, body: {...publicState(data, p, now), events: r.events, replayed: r.replayed}};
      }
      if (body.kind === 'kingdom') return kingdomCommand(data, p, now, key, body, receipts);
      throw httpError(400, 'UNSUPPORTED_IN_LOCAL_REALM', UNSUPPORTED, {kind: body.kind ?? null});
    });
  }

  async function kingdomCommand(data, p, now, key, body, receipts) {
    if (typeof key !== 'string' || !/^[-\w]{8,128}$/.test(key)) throw httpError(400, 'BAD_FIELDS', 'Нужен заголовок Idempotency-Key.');
    const signature = JSON.stringify(body);
    const previous = await receipts.find(key);
    if (previous) {
      if (previous.signature !== signature) throw httpError(409, 'IDEMPOTENCY_BODY_MISMATCH', 'Этот запрос уже использован для другого действия. Обновите состояние.');
      return {status: 200, body: {...publicState(data, p, now), events: [], replayed: true}};
    }
    const events = [];
    const kingdom = p.city.kingdom;
    if (body.action === 'enter' || body.action === 'skip') {
      if (Object.keys(body).some(k => !['kind', 'action', 'requestId'].includes(k))) throw httpError(400, 'BAD_FIELDS', 'Неверный формат команды.');
      if (body.action === 'enter') kingdom.guide.entered = true; else kingdom.guide.skipped = true;
    } else if (body.action === 'upgrade') {
      if (Object.keys(body).some(k => !['kind', 'action', 'buildingId', 'expectedLevel', 'requestId'].includes(k))) throw httpError(400, 'BAD_FIELDS', 'Неверный формат команды.');
      const building = p.city.buildings.find(b => b.id === body.buildingId);
      if (!building) throw httpError(404, 'BUILDING_UNKNOWN', 'Здание не найдено.');
      if (baseType(building.type) !== 'ECO-05') throw httpError(400, 'UNSUPPORTED_IN_LOCAL_REALM', UNSUPPORTED, {kind: 'kingdom.upgrade', type: building.type});
      if (building.level !== body.expectedLevel) throw httpError(409, 'STALE_LEVEL', 'Уровень здания уже изменился. Обновите состояние.');
      if (building.level >= 5) throw httpError(409, 'MAX_LEVEL', 'Достигнут максимальный уровень текущего этапа.');
      if (kingdom.order) throw httpError(409, 'CONSTRUCTION_BUSY', 'Уже идёт строительство. Дождитесь его окончания.');
      const terms = HALL_UPGRADES[building.level - 1];
      if (RESOURCES.some(r => balance(p.city, r) < terms.cost[r])) throw httpError(409, 'NOT_ENOUGH_RESOURCES', 'Недостаточно ресурсов для улучшения ратуши.', {cost: terms.cost});
      // Genuinely successful paid command: snapshot before/after the real spend for auto-refill.
      const before = integerWallet(p.city);
      for (const r of RESOURCES) debit(p.city, r, terms.cost[r]);
      kingdom.order = {id: 'order-' + key, kind: 'upgrade', requestId: key, buildingId: building.id, type: building.type, fromLevel: building.level, level: building.level + 1,
        cost: clone(terms.cost), startsAt: now, endsAt: now + Math.max(1, Math.round(buildSeconds * 1000)), nominalSeconds: terms.seconds};
      kingdom.revision++;
      const refill = await fr.afterVerifiedSpend(p, before, now);
      events.push(...refill.events);
    } else {
      throw httpError(400, 'UNSUPPORTED_IN_LOCAL_REALM', UNSUPPORTED, {kind: 'kingdom.' + body.action});
    }
    receipts.insert({key, signature, kind: 'kingdom', action: body.action}, now);
    return {status: 200, body: {...publicState(data, p, now), events, replayed: false}};
  }

  // ------------------------------------------------------------------ test helpers
  async function testClock({time, mode}) {
    return transact(async data => {
      const current = clock(data);
      if (mode === 'real') {
        if (Date.now() < current) throw httpError(400, 'CLOCK_NOT_MONOTONIC', 'Реальное время меньше симулированного.');
        data.clock.simulated = null;
        return {status: 204, body: null};
      }
      if (!Number.isSafeInteger(time) || time < current) throw httpError(400, 'CLOCK_NOT_MONOTONIC', 'Время можно только увеличивать.');
      data.clock.simulated = time;
      return {status: 204, body: null};
    });
  }

  async function testMutate({login = DEFAULT_LOGIN, selected = null}, mutate) {
    return transact(async data => {
      const p = selectPlayer(data, login, selected);
      const now = clock(data);
      const out = mutate(p, now);
      return {status: 200, body: {...publicState(data, p, now), test: out}};
    });
  }

  const testHall = (who, level) => testMutate(who, p => {
    if (!Number.isSafeInteger(level) || level < 0 || level > 5) throw httpError(400, 'BAD_FIELDS', 'level 0..5');
    const hall = p.city.buildings.find(b => baseType(b.type) === 'ECO-05');
    hall.level = level;
    if (p.city.kingdom.order?.buildingId === hall.id) p.city.kingdom.order = null;
    return {hallLevel: level};
  });

  const testArmy = (who, body) => testMutate(who, p => {
    const units = isPlainObject(body?.units) ? body.units : body;
    const mode = body?.mode === 'set' ? 'set' : 'add';
    if (!isPlainObject(units)) throw httpError(400, 'BAD_FIELDS', 'units map required');
    for (const [id, n] of Object.entries(units)) {
      if (id === 'mode' || id === 'units') continue;
      if (!Object.hasOwn(TROOPS, id) || !Number.isSafeInteger(n) || n < 0) throw httpError(400, 'BAD_FIELDS', 'unknown unit or count', {unitId: id});
      p.city.military.owned[id] = mode === 'set' ? n : (p.city.military.owned[id] ?? 0) + n;
    }
    p.city.military.owned = normalizeUnits(p.city.military.owned);
    if (body?.clearWounded === true) p.wounded = {};
    return {owned: clone(p.city.military.owned)};
  });

  const testWallet = (who, body) => testMutate(who, p => {
    if (!isPlainObject(body)) throw httpError(400, 'BAD_FIELDS', 'wallet map required');
    for (const [r, n] of Object.entries(body)) {
      if (!RESOURCES.includes(r) || !Number.isSafeInteger(n) || n < 0) throw httpError(400, 'BAD_FIELDS', 'resource/amount', {resource: r});
      if (r === 'wood') p.city.progress.wood = n; else p.city.demo.wallet[r] = n;
    }
    return {wallet: integerWallet(p.city)};
  });

  const testBuilding = (who, {type, level}) => testMutate(who, p => {
    if (typeof type !== 'string' || !/^[A-Z]{3}-\d{2}$/.test(type) || !Number.isSafeInteger(level) || level < 1 || level > 5) throw httpError(400, 'BAD_FIELDS', 'type/level');
    let b = p.city.buildings.find(x => x.type === type);
    if (!b) { b = {id: 'building-test-' + type, type, plotId: 'test-' + type, level}; p.city.buildings.push(b); }
    b.level = level;
    return {building: clone(b)};
  });

  return {store, fr, getState, sessionNew, command, testClock, testHall, testArmy, testWallet, testBuilding, clock: () => clock(store.data)};
}
