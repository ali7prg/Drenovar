// Deterministic, seeded battle resolution for campaign guardians and the 3-phase boss.
//
// Model (documented in README.md "Battle model"): the enemy's displayed `strength` is the
// calibration anchor — a squad of reference recruits (ENG-09) whose total power equals the
// strength breaks even. Troop stats then shape the fight: per-unit offence vs the enemy's
// defence is atk²/(atk+def); per-unit toughness vs the enemy's attack is hp·(A+def)/A.
// The enemy removes a constant toughness budget per second (spread over the front line
// first), the squad's volleys scale with its surviving offence. Every effect is placed on a
// timeline (attack / hit / telegraph / ability / phase / recovery / death) that the client
// animates; the server already knows the outcome and applies it at `endsAt` (settle).
// Boss attacks use the exact telegraph/active/recovery seconds from campaign.json; a phase
// cannot end before it has shown at least one complete telegraphed attack cycle.
import {TROOPS, isFrontLine} from './catalog.mjs';
import {rng, round} from './util.mjs';

export const BATTLE_TUNING = Object.freeze({
  refPower: 60, refAttack: 42, refDefense: 38, refHp: 100, // ENG-09 reference recruit
  volleyInterval: 1.5, firstVolley: 0.8, squadWindup: 0.3,
  jitter: 0.1,
  guardian: Object.freeze({T0: 15, firstHit: 1.4, windup: 0.35, abilityEvery: 3, abilityTelegraph: 0.8, abilityMultiplier: 1.5, maxVolleyFraction: 0.25, maxSeconds: 240, settleSeconds: 1.0}),
  boss: Object.freeze({T0: 75, maxSeconds: 900, settleSeconds: 1.5}),
  woundedShare: Object.freeze({victory: 0.6, defeat: 0.35, retreat: 0.35}),
});

const offense = (atk, def) => atk * atk / (atk + def);
const toughness = (hp, def, enemyAttack) => hp * (enemyAttack + def) / enemyAttack;

function makeStacks(units, enemyAttack, enemyDefense) {
  return Object.keys(units).sort().filter(id => units[id] > 0).map(id => {
    const t = TROOPS[id];
    if (!t) throw Object.assign(new Error('UNKNOWN_UNIT'), {code: 'UNKNOWN_UNIT'});
    return {id, alive: units[id], carry: 0, front: isFrontLine(t), tough: toughness(t.hp, t.defense, enemyAttack), off: offense(t.attack, enemyDefense)};
  });
}

const aliveTotal = stacks => stacks.reduce((n, s) => n + s.alive, 0);
const squadOffense = stacks => stacks.reduce((n, s) => n + s.alive * s.off, 0);

function applyPool(stacks, pool) {
  let targets = stacks.filter(s => s.front && s.alive > 0);
  if (!targets.length) targets = stacks.filter(s => s.alive > 0);
  const total = aliveTotal(targets), knocked = {};
  for (const s of targets) {
    s.carry += pool * s.alive / total;
    const k = Math.min(s.alive, Math.floor(s.carry / s.tough + 1e-9));
    s.carry -= k * s.tough;
    s.alive -= k;
    if (s.alive === 0) s.carry = 0;
    if (k > 0) knocked[s.id] = k;
  }
  return knocked;
}

function context({units, hp, attack, defense, strength, seed, T0}) {
  const R = rng(seed);
  const tuning = BATTLE_TUNING;
  const nRef = strength / tuning.refPower;
  return {
    R, jit: () => 1 + (R() * 2 - 1) * tuning.jitter,
    stacks: makeStacks(units, attack, defense),
    perVolleyBase: hp / (nRef * offense(tuning.refAttack, defense) * (T0 / tuning.volleyInterval)),
    poolPerSecond: nRef * toughness(tuning.refHp, tuning.refDefense, attack) / (2 * T0),
  };
}

function finish(timeline, knocks, end, hpMax, settleSeconds) {
  timeline.sort((a, b) => a.t - b.t || a.order - b.order);
  const out = timeline.map(({order, ...e}) => ({...e, t: round(e.t, 2)}));
  const totalKnocked = {};
  for (const k of knocks) for (const [id, n] of Object.entries(k.units)) totalKnocked[id] = (totalKnocked[id] ?? 0) + n;
  return {
    outcome: end.outcome, endReason: end.reason ?? null,
    durationMs: Math.round((end.t + settleSeconds) * 1000),
    timeline: out, knocks: knocks.map(k => ({t: round(k.t, 2), units: k.units})), totalKnocked, hpMax,
  };
}

/** Guardian (campaign creature) battle. */
export function simulateGuardian({units, spec, modifier = null, seed}) {
  const g = BATTLE_TUNING.guardian;
  const c = context({units, hp: spec.hp, attack: spec.attack, defense: spec.defense, strength: spec.strength, seed, T0: g.T0});
  const timeline = [], knocks = [];
  let order = 0;
  const push = e => timeline.push({...e, order: order++});
  let hp = spec.hp, tVolley = BATTLE_TUNING.firstVolley, tHit = g.firstHit, attacks = 0, end = null;
  // ancient_watch: harder, readable arena (every 2nd strike telegraphed) — no hidden HP/level.
  const telegraphEvery = modifier === 'ancient_watch' ? 2 : g.abilityEvery;
  push({t: 0, type: 'phase', actor: 'guardian', phase: 'engage'});
  while (!end) {
    const next = Math.min(tVolley, tHit);
    if (next > g.maxSeconds) { end = {t: g.maxSeconds, outcome: 'defeat', reason: 'timeout'}; push({t: g.maxSeconds, type: 'retreat', actor: 'squad'}); break; }
    if (tVolley <= tHit) {
      const alive = aliveTotal(c.stacks);
      let damage = Math.round(c.perVolleyBase * squadOffense(c.stacks) * c.jit());
      damage = Math.min(damage, Math.ceil(spec.hp * g.maxVolleyFraction), hp);
      push({t: tVolley - BATTLE_TUNING.squadWindup, type: 'attack', actor: 'squad', target: 'guardian', units: alive});
      hp -= damage;
      push({t: tVolley, type: 'hit', actor: 'squad', target: 'guardian', damage, hp});
      if (hp <= 0) { push({t: tVolley, type: 'death', actor: 'guardian'}); end = {t: tVolley, outcome: 'victory'}; break; }
      tVolley += BATTLE_TUNING.volleyInterval;
    } else {
      attacks++;
      // Signature ability: 2nd strike, then every `telegraphEvery` strikes (always shown once).
      const special = attacks === 2 || (attacks > 2 && (attacks - 2) % telegraphEvery === 0);
      if (special) push({t: Math.max(0, tHit - g.windup - g.abilityTelegraph), type: 'telegraph', actor: 'guardian', attack: spec.ability, telegraphSeconds: g.abilityTelegraph});
      push({t: tHit - g.windup, type: special ? 'ability' : 'attack', actor: 'guardian', attack: special ? spec.ability : 'strike', target: 'squad'});
      const pool = c.poolPerSecond * spec.cooldown * c.jit() * (special ? g.abilityMultiplier : 1);
      const knocked = applyPool(c.stacks, pool);
      const survivors = aliveTotal(c.stacks);
      push({t: tHit, type: 'hit', actor: 'guardian', target: 'squad', attack: special ? spec.ability : 'strike', knocked, survivors});
      if (Object.keys(knocked).length) knocks.push({t: tHit, units: knocked});
      if (survivors === 0) { push({t: tHit, type: 'death', actor: 'squad'}); end = {t: tHit, outcome: 'defeat'}; break; }
      tHit += spec.cooldown;
    }
  }
  return finish(timeline, knocks, end, spec.hp, g.settleSeconds);
}

/** Final boss `ancient_maw`: 3 phases, telegraphed attack cycles from campaign.json. */
export function simulateBoss({units, boss, seed}) {
  const b = BATTLE_TUNING.boss;
  const {hp: H, attack, defense, displayStrength} = boss.stats;
  const c = context({units, hp: H, attack, defense, strength: displayStrength, seed, T0: b.T0});
  const timeline = [], knocks = [];
  let order = 0;
  const push = e => timeline.push({...e, order: order++});
  const thresholds = boss.phases.map(p => p.hpAboveFraction * H);
  const lowerBound = i => i >= boss.phases.length ? 0 : Math.max(1, Math.floor(thresholds[i]) + 1);
  let hp = H, phase = 0, cyclesInPhase = 0, attackIndex = 0, end = null;
  let tVolley = BATTLE_TUNING.firstVolley;
  const queue = []; // boss effects: {t, kind:'hit'|'cycleEnd', pool?, attack}
  push({t: 0, type: 'phase', actor: 'boss', phase: boss.phases[0].id});

  function scheduleCycle(t0) {
    const attacks = boss.phases[phase].attacks;
    const name = attacks[attackIndex % attacks.length];
    attackIndex++;
    const a = boss.attacks[name];
    const waves = a.waveCount ?? 1;
    const active = a.waveActiveSeconds ?? a.activeSeconds;
    const interval = a.waveStartIntervalSeconds ?? 0;
    const activeEnd = t0 + a.telegraphSeconds + (waves - 1) * interval + active;
    const cycleEnd = activeEnd + a.recoverySeconds;
    const pool = c.poolPerSecond * (cycleEnd - t0) * c.jit();
    push({t: t0, type: 'telegraph', actor: 'boss', attack: name, phase: boss.phases[phase].id, shape: a.shape,
      telegraphSeconds: a.telegraphSeconds, activeSeconds: active, recoverySeconds: a.recoverySeconds, ...(waves > 1 ? {waveCount: waves, waveStartIntervalSeconds: interval} : {})});
    for (let w = 0; w < waves; w++) {
      const start = t0 + a.telegraphSeconds + w * interval;
      push({t: start, type: 'attack', actor: 'boss', attack: name, target: 'squad', ...(waves > 1 ? {wave: w + 1} : {}), activeSeconds: active});
      queue.push({t: start + active / 2, kind: 'hit', pool: pool / waves, attack: name, wave: waves > 1 ? w + 1 : null});
    }
    push({t: activeEnd, type: 'recovery', actor: 'boss', attack: name, until: round(cycleEnd, 2)});
    queue.push({t: cycleEnd, kind: 'cycleEnd', phase});
    queue.sort((x, y) => x.t - y.t);
  }
  scheduleCycle(0);

  while (!end) {
    const nextBoss = queue[0];
    if (Math.min(tVolley, nextBoss.t) > b.maxSeconds) { end = {t: b.maxSeconds, outcome: 'defeat', reason: 'timeout'}; push({t: b.maxSeconds, type: 'retreat', actor: 'squad'}); break; }
    if (tVolley <= nextBoss.t) {
      const alive = aliveTotal(c.stacks);
      let damage = Math.round(c.perVolleyBase * squadOffense(c.stacks) * c.jit());
      // Phase gate: hp stays inside the current phase until one full telegraphed cycle of it
      // has been shown; afterwards it may enter (at most) the next phase.
      const floor = lowerBound(cyclesInPhase >= 1 ? phase + 1 : phase);
      damage = Math.max(0, Math.min(damage, hp - Math.min(hp, floor)));
      push({t: tVolley - BATTLE_TUNING.squadWindup, type: 'attack', actor: 'squad', target: 'boss', units: alive});
      hp -= damage;
      push({t: tVolley, type: 'hit', actor: 'squad', target: 'boss', damage, hp});
      if (hp <= 0) { push({t: tVolley, type: 'death', actor: 'boss'}); end = {t: tVolley, outcome: 'victory'}; break; }
      while (phase < boss.phases.length - 1 && hp <= thresholds[phase]) {
        phase++; cyclesInPhase = 0; attackIndex = 0;
        push({t: tVolley, type: 'phase', actor: 'boss', phase: boss.phases[phase].id});
      }
      tVolley += BATTLE_TUNING.volleyInterval;
    } else {
      const e = queue.shift();
      // Only a cycle that started in the current phase counts towards its gate.
      if (e.kind === 'cycleEnd') { if (e.phase === phase) cyclesInPhase++; scheduleCycle(e.t); continue; }
      const knocked = applyPool(c.stacks, e.pool);
      const survivors = aliveTotal(c.stacks);
      push({t: e.t, type: 'hit', actor: 'boss', target: 'squad', attack: e.attack, ...(e.wave ? {wave: e.wave} : {}), knocked, survivors});
      if (Object.keys(knocked).length) knocks.push({t: e.t, units: knocked});
      if (survivors === 0) { push({t: e.t, type: 'death', actor: 'squad'}); end = {t: e.t, outcome: 'defeat'}; break; }
    }
  }
  // Drop boss presentation events scheduled after the end of the fight.
  const cut = timeline.filter(e => e.t <= end.t + 1e-9);
  return finish(cut, knocks, end, H, b.settleSeconds);
}

export function knockedUntil(knocks, tSeconds) {
  const out = {};
  for (const k of knocks) if (k.t <= tSeconds + 1e-9) for (const [id, n] of Object.entries(k.units)) out[id] = (out[id] ?? 0) + n;
  return out;
}

/** Split knocked-out units into wounded/dead (deterministic rounding per unit type). */
export function splitLosses(knocked, outcome) {
  const share = BATTLE_TUNING.woundedShare[outcome] ?? BATTLE_TUNING.woundedShare.defeat;
  const wounded = {}, dead = {};
  for (const id of Object.keys(knocked).sort()) {
    const k = knocked[id];
    if (!(k > 0)) continue;
    const w = Math.round(k * share);
    if (w > 0) wounded[id] = w;
    if (k - w > 0) dead[id] = k - w;
  }
  return {wounded, dead};
}

/** Remaining creature hp and current boss phase at elapsed seconds (projection). */
export function stateAt(timeline, hpMax, elapsedSeconds) {
  let hp = hpMax, phase = null;
  for (const e of timeline) {
    if (e.t > elapsedSeconds) break;
    if (e.type === 'hit' && (e.target === 'guardian' || e.target === 'boss')) hp = e.hp;
    if (e.type === 'phase') phase = e.phase;
  }
  return {hp, phase};
}
