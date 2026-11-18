// The delivered reference modules/data are used UNMODIFIED: the vendored copies must be
// byte-identical to forest_rescue/delivery and to the hashes in its PACKAGE_MANIFEST.json.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, existsSync, readdirSync} from 'node:fs';
import {createHash} from 'node:crypto';

const vendor = new URL('../vendor/delivery/', import.meta.url);
const delivery = new URL('../../delivery/', import.meta.url);
const sha = buf => createHash('sha256').update(buf).digest('hex');
const sums = readFileSync(new URL('SHA256SUMS', vendor), 'utf8').trim().split('\n').map(line => {
  const [hash, path] = line.split(/\s+/);
  return {hash, path};
});

test('vendored files match SHA256SUMS', () => {
  assert.ok(sums.length >= 14);
  for (const {hash, path} of sums) assert.equal(sha(readFileSync(new URL(path, vendor))), hash, path);
  // every delivered code module is vendored
  const vendoredCode = readdirSync(new URL('code/', vendor)).sort();
  assert.deepEqual(vendoredCode, sums.filter(s => s.path.startsWith('code/')).map(s => s.path.slice(5)).sort());
});

test('vendored files are byte-identical to the delivery package and its manifest', {skip: !existsSync(delivery) && 'delivery package not present'}, () => {
  const manifest = JSON.parse(readFileSync(new URL('PACKAGE_MANIFEST.json', delivery), 'utf8'));
  const byPath = new Map(manifest.files.map(f => [f.path.replace('DRENOVAR_Forest_Rescue/', ''), f]));
  for (const {hash, path} of sums) {
    const original = readFileSync(new URL(path, delivery));
    assert.ok(original.equals(readFileSync(new URL(path, vendor))), 'byte-identical ' + path);
    assert.equal(byPath.get(path)?.sha256, hash, 'PACKAGE_MANIFEST hash ' + path);
    assert.equal(byPath.get(path)?.bytes, original.length, 'PACKAGE_MANIFEST size ' + path);
  }
  const deliveredCode = readdirSync(new URL('code/', delivery)).filter(f => f.endsWith('.mjs')).sort();
  assert.deepEqual(deliveredCode, readdirSync(new URL('code/', vendor)).sort());
});

test('server sources import the reference modules only through src/vendor.mjs', () => {
  const dir = new URL('../src/', import.meta.url);
  for (const file of readdirSync(dir)) {
    const text = readFileSync(new URL(file, dir), 'utf8');
    if (file === 'vendor.mjs') continue;
    assert.ok(!/vendor\/delivery|delivery\/code/.test(text), file + ' must import through vendor.mjs');
  }
});
