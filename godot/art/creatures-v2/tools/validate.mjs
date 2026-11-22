import {readFile, writeFile} from 'node:fs/promises';
import {basename} from 'node:path';
import validator from 'gltf-validator';
const files = process.argv.slice(3);
const out = process.argv[2];
const rows = [];
for (const f of files) {
  const data = new Uint8Array(await readFile(f));
  const r = await validator.validateBytes(data, {uri: basename(f), maxIssues: 200});
  const counts = {};
  for (const m of r.issues.messages) counts[`${['E','W','I','H'][m.severity]}:${m.code}`] = (counts[`${['E','W','I','H'][m.severity]}:${m.code}`] ?? 0) + 1;
  rows.push({file: basename(f), bytes: data.length, errors: r.issues.numErrors, warnings: r.issues.numWarnings,
    infos: r.issues.numInfos, hints: r.issues.numHints, codes: counts, animations: r.info?.animationCount,
    meshes: r.info?.meshCount, materials: r.info?.materialCount, tris: r.info?.totalTriangleCount,
    maxInfluences: r.info?.maxInfluences, extensions: r.info?.extensionsUsed ?? []});
  console.log(`${basename(f)} errors=${r.issues.numErrors} warnings=${r.issues.numWarnings} tris=${r.info?.totalTriangleCount} anims=${r.info?.animationCount}`);
}
await writeFile(out, JSON.stringify({validator: 'Khronos glTF-Validator 2.0.0-dev.3.10', files: rows}, null, 1));
