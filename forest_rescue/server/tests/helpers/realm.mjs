// Test harness: an in-process local realm (real HTTP on 127.0.0.1) that can be restarted
// from its persisted JSON snapshot at any moment, plus a small typed HTTP client.
import {mkdtempSync, rmSync, existsSync, readFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {startServer} from '../../local-realm/server.mjs';

export const START_TIME = 1794370000000; // same clock origin as godot/tools/starter-state.json
export const CAMPAIGN_ID = 'forest_rescue_v1';

export function tempDir(label = 'realm') {
  return mkdtempSync(join(tmpdir(), 'fr-' + label + '-'));
}

/** Deterministic player ids keep battle seeds (and therefore reports) reproducible. */
export function sequentialIds(prefix = 'player') {
  let n = 0;
  return () => prefix + '-' + String(++n).padStart(4, '0');
}

export class Realm {
  constructor({dir = tempDir(), idPrefix = 'player', hooks = {}, buildSeconds = 10} = {}) {
    this.dir = dir;
    this.dbPath = join(dir, 'realm.json');
    this.idPrefix = idPrefix;
    this.hooks = hooks;
    this.buildSeconds = buildSeconds;
    this.restarts = 0;
  }
  /** Deterministic ids that stay unique across restarts (counted from the persisted file). */
  idFactory() {
    let count = existsSync(this.dbPath) ? Object.keys(JSON.parse(readFileSync(this.dbPath, 'utf8')).players).length : 0;
    return () => this.idPrefix + '-' + String(++count).padStart(4, '0');
  }
  async start() {
    this.running = await startServer({port: 0, dbPath: this.dbPath, quiet: true, startTime: START_TIME, hooks: this.hooks,
      buildSeconds: this.buildSeconds, idFactory: this.idFactory()});
    this.url = this.running.url;
    return this;
  }
  /** Stop the HTTP server and the realm, then start a NEW realm instance from the JSON file. */
  async restart() {
    await this.running.close();
    await this.start();
    this.restarts++;
    return this;
  }
  get store() {
    return this.running.realm.store;
  }
  async stop() {
    await this.running?.close();
    this.running = null;
  }
  async destroy() {
    await this.stop();
    rmSync(this.dir, {recursive: true, force: true});
  }
  client(options) {
    return new Client(this, options);
  }
}

export class Client {
  constructor(realm, {login = null, player = null, keyPrefix = 'k'} = {}) {
    this.realm = realm;
    this.login = login;
    this.player = player;
    this.keyPrefix = keyPrefix;
    this.n = 0;
  }
  headers(extra = {}) {
    const h = {'content-type': 'application/json', ...extra};
    if (this.login) h['oai-authenticated-user-id'] = this.login;
    if (this.player) h['x-drenovar-player'] = this.player;
    return h;
  }
  async raw(method, path, {body, headers = {}} = {}) {
    const res = await fetch(this.realm.url + path, {method, headers: this.headers(headers), body: body === undefined ? undefined : typeof body === 'string' ? body : JSON.stringify(body)});
    const text = await res.text();
    return {status: res.status, body: text ? JSON.parse(text) : null};
  }
  async state() {
    const r = await this.raw('GET', '/api/state');
    if (r.status !== 200) throw new Error('state ' + r.status + ' ' + JSON.stringify(r.body));
    return r.body;
  }
  async session(body = {}) {
    const r = await this.raw('POST', '/api/session/new', {body});
    if (r.status === 201 || r.status === 200) this.player ??= r.body.playerId;
    return r;
  }
  nextKey(label = '') {
    return this.keyPrefix + '-' + (label ? label.replace(/[^-\w]/g, '_') + '-' : '') + String(++this.n).padStart(5, '0');
  }
  /** POST /api/command; returns {status, body, key}. */
  async send(body, {key = this.nextKey(body.action ?? body.kind), headers = {}} = {}) {
    const r = await this.raw('POST', '/api/command', {body, headers: key === null ? headers : {'idempotency-key': key, ...headers}});
    return {...r, key};
  }
  adv(action, extra = {}) {
    return {kind: 'adventure', campaignId: CAMPAIGN_ID, action, ...extra};
  }
  intro(action, extra = {}) {
    return {kind: 'adventure_intro', campaignId: CAMPAIGN_ID, action, ...extra};
  }
  /** Adventure command that must succeed. */
  async ok(action, extra = {}, options = {}) {
    const r = await this.send(this.adv(action, extra), options);
    if (r.status !== 200) throw new Error(action + ' ' + JSON.stringify(extra) + ' → ' + r.status + ' ' + JSON.stringify(r.body));
    return r.body;
  }
  async fails(action, extra, expectedStatus, expectedCode) {
    const r = await this.send(this.adv(action, extra));
    if (r.status !== expectedStatus || r.body?.error !== expectedCode) {
      throw new Error(action + ' expected ' + expectedStatus + ' ' + expectedCode + ' got ' + r.status + ' ' + JSON.stringify(r.body));
    }
    return r.body;
  }
  async clock(time) {
    const r = await this.raw('POST', '/test/clock?time=' + time);
    if (r.status !== 204) throw new Error('clock ' + r.status + ' ' + JSON.stringify(r.body));
  }
  async advanceTo(time) {
    const s = await this.state();
    if (time > s.serverTime) await this.clock(time);
    return this.state();
  }
  async advance(ms) {
    const s = await this.state();
    await this.clock(s.serverTime + ms);
    return this.state();
  }
  async hall(level) {
    const r = await this.raw('POST', '/test/hall?level=' + level);
    if (r.status !== 200) throw new Error('hall ' + r.status);
    return r.body;
  }
  async army(units, mode = 'add') {
    const r = await this.raw('POST', '/test/army', {body: {units, mode}});
    if (r.status !== 200) throw new Error('army ' + r.status + JSON.stringify(r.body));
    return r.body;
  }
  async wallet(values) {
    const r = await this.raw('POST', '/test/wallet', {body: values});
    if (r.status !== 200) throw new Error('wallet ' + r.status + JSON.stringify(r.body));
    return r.body;
  }
  async building(type, level) {
    const r = await this.raw('POST', '/test/building?type=' + type + '&level=' + level);
    if (r.status !== 200) throw new Error('building ' + r.status + JSON.stringify(r.body));
    return r.body;
  }
}

/** Fresh realm + first settlement for the default login. */
export async function freshRealm(options = {}) {
  const realm = await new Realm(options).start();
  const client = realm.client(options.client);
  const created = await client.session();
  if (created.status !== 201) throw new Error('session ' + created.status);
  return {realm, client, playerId: created.body.playerId};
}
