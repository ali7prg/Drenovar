// Keeps running the delivered 74 reference tests unchanged (from the delivery root).
import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {existsSync, readdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('../../delivery/', import.meta.url));

test('delivered reference suite: 74/74 pass unchanged', {skip: !existsSync(root) && 'delivery package not present', timeout: 120000}, () => {
  const files = readdirSync(root + 'tests').filter(f => f.endsWith('.test.mjs')).map(f => 'tests/' + f);
  const run = spawnSync(process.execPath, ['--test', ...files], {cwd: root, encoding: 'utf8', timeout: 110000});
  const out = run.stdout + run.stderr;
  const count = key => Number(new RegExp('^# ' + key + ' (\\d+)', 'm').exec(out)?.[1]);
  console.log('# delivered suite: tests', count('tests'), 'pass', count('pass'), 'fail', count('fail'));
  assert.equal(run.status, 0, out.slice(-2000));
  assert.equal(count('tests'), 74);
  assert.equal(count('pass'), 74);
  assert.equal(count('fail'), 0);
});
