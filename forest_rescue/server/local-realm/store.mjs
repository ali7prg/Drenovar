// Whole-realm JSON snapshot with revision CAS — the local stand-in for the v92 hosted.mjs
// D1 `UPDATE … WHERE revision=?`. A commit succeeds only if nobody committed since the
// snapshot was read; the caller then retries on the fresh snapshot (recomputing proofs,
// capacity and wallet from it). Persisted atomically (write temp file + rename).
import {readFileSync, writeFileSync, renameSync, existsSync, mkdirSync} from 'node:fs';
import {dirname} from 'node:path';

export const DB_FORMAT = 'drenovar-forest-rescue-local-realm';
export const DB_SCHEMA = 1;

export function emptyRealm() {
  return {format: DB_FORMAT, schema: DB_SCHEMA, revision: 0, clock: {simulated: null}, sequence: 0, logins: {}, players: {}, commands: {}};
}

export class SnapshotStore {
  constructor(path) {
    this.path = path;
    if (existsSync(path)) {
      // Never silently reset a damaged realm file.
      const data = JSON.parse(readFileSync(path, 'utf8'));
      if (data?.format !== DB_FORMAT || data.schema !== DB_SCHEMA || !Number.isSafeInteger(data.revision)) {
        throw Object.assign(new Error('REALM_DB_UNSUPPORTED: ' + path), {code: 'REALM_DB_UNSUPPORTED'});
      }
      this.data = data;
    } else {
      mkdirSync(dirname(path), {recursive: true});
      this.data = emptyRealm();
      this.persist();
    }
    this.commits = 0;
    this.conflicts = 0;
  }

  get revision() {
    return this.data.revision;
  }

  read() {
    return {revision: this.data.revision, data: structuredClone(this.data)};
  }

  /** Revision-checked commit; returns false on conflict (nothing written). */
  commit(expectedRevision, next) {
    if (this.data.revision !== expectedRevision) { this.conflicts++; return false; }
    next.revision = expectedRevision + 1;
    this.data = next;
    this.persist();
    this.commits++;
    return true;
  }

  persist() {
    const tmp = this.path + '.tmp-' + process.pid;
    writeFileSync(tmp, JSON.stringify(this.data));
    renameSync(tmp, this.path);
  }
}
