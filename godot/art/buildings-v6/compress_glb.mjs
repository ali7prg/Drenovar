import {readFile, writeFile} from 'node:fs/promises';
import {dirname, resolve} from 'node:path';
import {MeshoptEncoder, MeshoptDecoder} from 'meshoptimizer';

// No vertex reordering, quantization, simplification or filter conversion.
// Every accessor and every attribute component keeps its original bit pattern.
await Promise.all([MeshoptEncoder.ready, MeshoptDecoder.ready]);
const [sourcePath, outputPath] = process.argv.slice(2);
const doc = JSON.parse(await readFile(sourcePath, 'utf8'));
const sourceBuffers = await Promise.all(doc.buffers.map(b => readFile(resolve(dirname(sourcePath), decodeURIComponent(b.uri)))));
const chunks = [];
let offset = 0;
let fallbackLength = 0;
for (let i = 0; i < doc.bufferViews.length; i++) {
  const view = doc.bufferViews[i];
  let original = sourceBuffers[view.buffer].subarray(view.byteOffset || 0, (view.byteOffset || 0) + view.byteLength);
  const accessor = doc.accessors.find(a => a.bufferView === i);
  if (!accessor) throw new Error(`Unused buffer view ${i}`);
  const isIndex = view.target === 34963;
  // EXT_meshopt_compression requires 16/32-bit indices; widening uint8 is exact.
  if (isIndex && accessor.componentType === 5121) {
    const widened = Buffer.alloc(original.length * 2);
    for (let j = 0; j < original.length; j++) widened.writeUInt16LE(original[j], j * 2);
    original = widened;
    accessor.componentType = 5123;
    view.byteLength = widened.length;
  }
  const stride = view.byteStride || (isIndex ? ({5121:1,5123:2,5125:4})[accessor.componentType] : view.byteLength / accessor.count);
  const mode = isIndex ? 'INDICES' : 'ATTRIBUTES';
  const count = original.length / stride;
  if (!Number.isInteger(count)) throw new Error(`Invalid buffer stride ${i}`);
  const encoded = MeshoptEncoder.encodeGltfBuffer(original, count, stride, mode, 0);
  const decoded = new Uint8Array(original.length);
  MeshoptDecoder.decodeGltfBuffer(decoded, count, stride, encoded, mode);
  if (!Buffer.from(decoded).equals(original)) throw new Error(`Lossy buffer ${i}`);
  view.buffer = 1;
  view.byteOffset = fallbackLength;
  fallbackLength += original.length;
  const padding = (4 - fallbackLength % 4) % 4;
  fallbackLength += padding;
  view.extensions = {EXT_meshopt_compression: {buffer:0,byteOffset:offset,byteLength:encoded.length,byteStride:stride,count,mode}};
  chunks.push(Buffer.from(encoded));
  offset += encoded.length;
  const encodedPadding = (4 - offset % 4) % 4;
  if (encodedPadding) { chunks.push(Buffer.alloc(encodedPadding)); offset += encodedPadding; }
}
doc.buffers = [{byteLength:offset}, {byteLength:fallbackLength, extensions:{EXT_meshopt_compression:{fallback:true}}}];
doc.extensionsUsed = [...new Set([...(doc.extensionsUsed || []), 'EXT_meshopt_compression'])];
doc.extensionsRequired = [...new Set([...(doc.extensionsRequired || []), 'EXT_meshopt_compression'])];
doc.asset.extras = {economy:'DRENOVAR-V6-C1.0',art:'DRENOVAR-V6-C1.0-ART1',compression:'lossless float32, byte-for-byte verified'};
let json = Buffer.from(JSON.stringify(doc));
json = Buffer.concat([json, Buffer.alloc((4 - json.length % 4) % 4, 32)]);
const bin = Buffer.concat(chunks);
const header = Buffer.alloc(12);
header.writeUInt32LE(0x46546c67, 0); header.writeUInt32LE(2, 4); header.writeUInt32LE(12 + 8 + json.length + 8 + bin.length, 8);
const jsonHeader = Buffer.alloc(8); jsonHeader.writeUInt32LE(json.length, 0); jsonHeader.writeUInt32LE(0x4e4f534a, 4);
const binHeader = Buffer.alloc(8); binHeader.writeUInt32LE(bin.length, 0); binHeader.writeUInt32LE(0x004e4942, 4);
await writeFile(outputPath, Buffer.concat([header, jsonHeader, json, binHeader, bin]));
