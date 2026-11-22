import {readFile, writeFile, stat} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {dirname, resolve} from 'node:path';
import {createHash} from 'node:crypto';
import {MeshoptDecoder} from 'meshoptimizer';

// Decode every published compressed buffer and compare the actual saved data,
// independently from the compression writer. Geometry and shading stay float32.
await MeshoptDecoder.ready;
const here = dirname(fileURLToPath(import.meta.url));
const assets = resolve(here, '../../project/assets/city/architecture-v6');
const only = process.argv.find(a => a.startsWith('--only='))?.slice(7);
let manifestPath = resolve(assets, only ? `manifest-${only}.json` : 'manifest.json');
try { await stat(manifestPath); } catch { manifestPath = resolve(assets, 'manifest.json'); }
const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
const rows = [];
let bufferChecks = 0;
let componentChecks = 0;
const textures = new Set();
const fail = message => { throw new Error(message); };
const groups={...manifest.levels,...Object.fromEntries(Object.entries(manifest.units||{}).map(([id,row])=>[id,{unit:row}]))};
for (const [type, levels] of Object.entries(groups)) {
  if (only && type !== only) continue;
  for (const [level, row] of Object.entries(levels)) {
    const key = level === 'unit' ? type : `${type}-${level}`;
    const sourcePath = resolve(assets, 'web-staging', `${key}-shared.gltf`);
    const source = JSON.parse(await readFile(sourcePath, 'utf8'));
    const sourceBuffers = await Promise.all(source.buffers.map(b => readFile(resolve(dirname(sourcePath), decodeURIComponent(b.uri)))));
    const path = resolve(assets, 'web', key + '.glb');
    const file = await readFile(path);
    if (file.readUInt32LE(0) !== 0x46546c67 || file.readUInt32LE(4) !== 2 || file.readUInt32LE(8) !== file.length) fail(key + ': invalid GLB header');
    const jsonLength = file.readUInt32LE(12);
    const gltf = JSON.parse(file.subarray(20, 20 + jsonLength));
    const binary = file.subarray(28 + jsonLength);
    if (!gltf.extensionsRequired.includes('EXT_meshopt_compression')) fail(key + ': decoder requirement missing');
    if (gltf.bufferViews.length !== source.bufferViews.length) fail(key + ': buffer count differs');
    for (let i = 0; i < source.bufferViews.length; i++) {
      const src = source.bufferViews[i];
      const dst = gltf.bufferViews[i];
      const ext = dst.extensions.EXT_meshopt_compression;
      const packed = binary.subarray(ext.byteOffset, ext.byteOffset + ext.byteLength);
      const decoded = new Uint8Array(dst.byteLength);
      MeshoptDecoder.decodeGltfBuffer(decoded, ext.count, ext.byteStride, packed, ext.mode, ext.filter);
      let expected = sourceBuffers[src.buffer].subarray(src.byteOffset || 0, (src.byteOffset || 0) + src.byteLength);
      const srcAccessor = source.accessors.find(a => a.bufferView === i);
      const dstAccessor = gltf.accessors.find(a => a.bufferView === i);
      if (src.target === 34963 && srcAccessor.componentType === 5121) {
        const widened = Buffer.alloc(expected.length * 2);
        expected.forEach((n, j) => widened.writeUInt16LE(n, j * 2));
        expected = widened;
        if (dstAccessor.componentType !== 5123) fail(key + ': byte indices must be widened exactly');
      } else if (srcAccessor.componentType !== dstAccessor.componentType) fail(key + ': component precision changed');
      if (srcAccessor.count !== dstAccessor.count || srcAccessor.type !== dstAccessor.type) fail(key + ': accessor shape changed');
      if (!Buffer.from(decoded).equals(expected)) fail(key + ': decoded buffer differs at ' + i);
      bufferChecks++;
      componentChecks += srcAccessor.count;
    }
    let triangles = 0;
    for (const mesh of gltf.meshes) for (const primitive of mesh.primitives) {
      const count = gltf.accessors[primitive.indices].count;
      triangles += count / 3;
      for (const semantic of ['POSITION', 'NORMAL', 'TEXCOORD_0', 'TANGENT', 'COLOR_0']) {
        if (gltf.accessors[primitive.attributes[semantic]].componentType !== 5126) fail(key + ': not float32 ' + semantic);
      }
    }
    if (triangles !== row.triangles) fail(key + `: triangle loss ${triangles}/${row.triangles}`);
    for (const image of gltf.images) {
      const path = resolve(assets, 'web', decodeURIComponent(image.uri));
      const info = await stat(path);
      if (info.size < 8) fail(key + ': empty external texture');
      textures.add(path);
    }
    const expectedMaterials = row.materials;
    if (gltf.materials.some((m, i) => m.name !== expectedMaterials[i])) fail(key + ': material mapping mismatch');
    rows.push({key,kind:level === 'unit' ? 'unit' : 'building',status:'passed',triangles,bytes:file.length,sha256:createHash('sha256').update(file).digest('hex')});
    console.log(`WEB_QA ${key} buffers=${gltf.bufferViews.length} exact=true`);
  }
}
const output = {status:'passed',states:rows.filter(r=>r.kind==='building').length,units:rows.filter(r=>r.kind==='unit').length,models:rows.length,bufferChecks,componentChecks,textureFiles:textures.size,
  float32AttributesPreserved:true,indicesPreserved:true,geometrySimplification:false,textureResizing:false,
  decoder:'meshoptimizer 1.3.0; EXT_meshopt_compression v0 codec',files:rows,
  notMeasured:['Safari/iPhone 12 GPU frame time','Texture look in both running clients is separately reviewed']};
await writeFile(resolve(assets, only ? `web-validation-${only}.json` : 'web-validation.json'), JSON.stringify(output,null,2)+'\n');
