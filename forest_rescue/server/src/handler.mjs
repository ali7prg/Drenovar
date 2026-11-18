// Drop-in facade shaped for CoreGameServer.command / publicState / settle (v92).
//
//   const fr = createForestRescue({ports});
//   await fr.settle(p, now)                         // inside readyPlayer/settle (core.mjs:35)
//   fr.hallGate(p, body)                            // after readyPlayer62, BEFORE receipt SELECT (core.mjs:66)
//   await fr.command({p, body, key, now, receipts}) // inside the existing tx; caller INSERTs the receipt
//   state.adventure = fr.project(p, now)            // publicState (core.mjs:50)
//   await fr.afterVerifiedSpend(p, beforeWallet, now) // optional auto-refill after a real paid command
//   await fr.enter(p, now)                          // real new foreground session entry only
//
// `p` is the candidate (mutable copy) of the selected player inside the caller's
// transaction; nothing here performs I/O. All effects land on `p` and are committed by the
// caller's single revision-checked write together with the receipt.
import {access, reserveRefill} from './vendor.mjs';
import {navGraph} from './navgraph.mjs';
import {loadBundle, bundleChanged, writeBundle} from './namespaces.mjs';
import {settleBundle} from './settle.mjs';
import {parseCommand, executeCommand, ADVENTURE_KINDS, KEY_PATTERN} from './commands.mjs';
import {projectAdventure, projectError} from './projection.mjs';
import {EVENT_RING} from './field.mjs';
import {MIN_HALL_LEVEL_EXPORT} from './constants.mjs';
import {RESOURCES} from './content.mjs';
import {AdventureError, toAdventureError} from './errors.mjs';
import {isPlainObject} from './util.mjs';

const PORTS = ['hallLevel', 'capacity', 'integerWallet', 'credit', 'healthyUnits', 'applyLosses', 'applyLoot', 'pushReport', 'creatureSpec', 'protectedTownCells'];

function compactForRing(event) {
  if (event.type === 'fog_revealed') return {type: event.type, count: event.count, seq: event.seq, revision: event.revision};
  return event;
}

export function createForestRescue({ports, graph = navGraph()} = {}) {
  for (const name of PORTS) if (typeof ports?.[name] !== 'function') throw new Error('MISSING_PORT_' + name);

  function base(p, now) {
    const hall = ports.hallLevel(p);
    return {p, now, hall, unlocked: Number.isSafeInteger(hall) && hall >= MIN_HALL_LEVEL_EXPORT, graph, ports};
  }

  function makeCtx(p, now, bundle) {
    const events = [];
    return {...base(p, now), bundle, events, emit(type, payload = {}) { events.push({type, ...payload}); }};
  }

  function commit(ctx) {
    const changed = bundleChanged(ctx.bundle);
    const field = ctx.bundle.field;
    if (changed) {
      if (field.revision >= Number.MAX_SAFE_INTEGER - 1) throw new AdventureError('STATE_CORRUPT', {detail: {reason: 'REVISION_EXHAUSTED'}});
      field.revision += 1;
    }
    const events = ctx.events.map(e => ({...e, seq: changed ? ++field.serials.event : 0, revision: field.revision}));
    if (changed) {
      field.events = [...field.events, ...events.map(compactForRing)].slice(-EVENT_RING);
      writeBundle(ctx.p, ctx.bundle);
    }
    return {changed, events};
  }

  function load(p) {
    return loadBundle(p, graph);
  }

  /** Lazy settle. Never writes when a namespace is corrupt or nothing happened. */
  async function settle(p, now) {
    let bundle;
    try { bundle = load(p); } catch (error) { return {changed: false, events: [], error: toAdventureError(error)}; }
    const ctx = makeCtx(p, now, bundle);
    try {
      await settleBundle(ctx);
    } catch (error) {
      throw toAdventureError(error);
    }
    return commit(ctx);
  }

  function isAdventureKind(kind) {
    return ADVENTURE_KINDS.includes(kind);
  }

  /** Hall-III gate for kind adventure/adventure_intro; call BEFORE any receipt replay. */
  function hallGate(p, body) {
    if (!isPlainObject(body) || !isAdventureKind(body.kind)) return;
    const {hall, unlocked} = base(p, 0);
    if (!unlocked) throw new AdventureError('FOREST_LOCKED_HALL_LEVEL', {detail: {hallLevel: Number.isSafeInteger(hall) ? hall : 0, requiredHall: MIN_HALL_LEVEL_EXPORT}});
  }

  /**
   * Execute one adventure command on candidate p. `receipts.find(key)` reads the existing
   * command receipt of THIS player (v92: SELECT … FROM commands). On success returns
   * {receipt:{key,signature}} for the caller to INSERT in the same transaction.
   */
  async function command({p, body, key, now, receipts}) {
    if (!isPlainObject(body) || !isAdventureKind(body.kind)) throw new AdventureError('BAD_FIELDS', {detail: {reason: 'kind'}});
    hallGate(p, body); // before receipt replay: a locked settlement never replays/locks in effects
    if (typeof key !== 'string' || !KEY_PATTERN.test(key)) {
      throw new AdventureError('BAD_FIELDS', {message: 'Для команды приключения нужен заголовок Idempotency-Key (8–128 символов: буквы, цифры, «-», «_»).', detail: {reason: 'idempotency_key'}});
    }
    const signature = JSON.stringify(body);
    const previous = await receipts.find(key);
    if (previous) {
      if (previous.signature !== signature) throw new AdventureError('IDEMPOTENCY_BODY_MISMATCH');
      return {replayed: true, events: [], receipt: null};
    }
    const action = parseCommand(body, key);
    let bundle;
    try { bundle = load(p); } catch (error) { throw toAdventureError(error); }
    const ctx = makeCtx(p, now, bundle);
    try {
      await settleBundle(ctx); // idempotent: guarantees settle-before-command
      await executeCommand(ctx, action);
    } catch (error) {
      throw toAdventureError(error);
    }
    const {events} = commit(ctx);
    return {replayed: false, events, receipt: {key, signature, kind: body.kind, action: body.action}};
  }

  /** state.adventure; pure (does not mutate p). */
  function project(p, now) {
    let bundle;
    try { bundle = load(p); } catch (error) { return projectError(base(p, now), toAdventureError(error)); }
    return projectAdventure(makeCtx(p, now, bundle));
  }

  /** Real new foreground entry (not polling): interrupted intro → deferred invitation. */
  async function enter(p, now) {
    let bundle;
    try { bundle = load(p); } catch (error) { return {changed: false, events: [], error: toAdventureError(error)}; }
    const ctx = makeCtx(p, now, bundle);
    const hall = Number.isSafeInteger(ctx.hall) ? ctx.hall : 0;
    const out = access.reconcileIntroOnEntry(bundle.intro, {authenticatedPlayerId: p.id, hallLevel: hall});
    bundle.intro = out.state;
    if (out.changed) ctx.emit('intro_deferred', {attempt: out.state.attempts});
    return commit(ctx);
  }

  /**
   * Opt-in auto-refill inside the SAME transaction right after a genuinely successful paid
   * command (production settled before `beforeWallet` was taken). Never on polls/refunds.
   */
  async function afterVerifiedSpend(p, beforeWallet, now) {
    let bundle;
    try { bundle = load(p); } catch (error) { return {changed: false, events: [], skipped: toAdventureError(error).code}; }
    const ctx = makeCtx(p, now, bundle);
    const afterWallet = ports.integerWallet(p);
    const cap = Math.min(Number.MAX_SAFE_INTEGER, Math.floor(ports.capacity(p)));
    const out = reserveRefill.refillAfterVerifiedSpend(bundle.campaign, {
      authenticatedPlayerId: p.id, hallLevel: Number.isSafeInteger(ctx.hall) ? ctx.hall : 0,
      optedIn: bundle.prefs.autoRefill, beforeWallet, afterWallet,
      capacity: Object.fromEntries(RESOURCES.map(r => [r, cap])),
    });
    const transfer = Object.fromEntries(RESOURCES.map(r => [r, out.wallet[r] - afterWallet[r]]));
    if (out.changed) {
      bundle.campaign = out.state;
      for (const r of RESOURCES) ports.credit(p, r, transfer[r]);
      ctx.emit('transfer_rewards', {resources: transfer, auto: true});
    }
    const result = commit(ctx);
    return {...result, transfer};
  }

  return {isAdventureKind, hallGate, settle, command, project, enter, afterVerifiedSpend, graph, load};
}
