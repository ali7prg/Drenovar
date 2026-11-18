// Shared fixtures: an unlocked settlement with a real army and the horse already joined.
import {freshRealm} from './realm.mjs';
import {Journey} from './journey.mjs';

export async function adventurer({idPrefix = 'p', hall = 3, army = {'ENG-06': 6000}, prologue = true, restartEachStep = false, hooks = {}} = {}) {
  const {realm, client, playerId} = await freshRealm({idPrefix, hooks});
  await client.hall(hall);
  if (army) await client.army(army);
  const journey = new Journey(realm, client, {restartEachStep});
  if (prologue) await journey.prologue(army);
  return {realm, client, playerId, journey};
}

/**
 * Commit barrier: once armed, the first transaction reaching its commit waits for a second
 * one, which commits first — so the first deterministically hits a revision conflict.
 */
export function commitBarrier() {
  const barrier = {armed: false, release: null, hits: 0};
  barrier.hooks = {beforeCommit: async () => {
    if (!barrier.armed) return;
    barrier.hits++;
    if (!barrier.release) {
      await Promise.race([new Promise(r => { barrier.release = r; }), new Promise(r => setTimeout(r, 1000))]);
      barrier.release = null;
      barrier.armed = false;
    } else {
      barrier.release();
    }
  }};
  return barrier;
}
