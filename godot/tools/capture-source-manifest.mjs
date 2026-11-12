// Record the public assets and JavaScript dependencies used by the native import.
import {readFileSync,writeFileSync} from 'node:fs';
import {join,posix,resolve} from 'node:path';
import {createHash} from 'node:crypto';

const source=resolve(process.argv[2]);
const result=JSON.parse(readFileSync(new URL('../project/assets/original-assets.json',import.meta.url)));
const generator=readFileSync(new URL('./import-web-assets.mjs',import.meta.url),'utf8');
const rootModules=[...generator.matchAll(/await load\('([^']+)'\)/g)].map(match=>match[1]);
const visited=new Set();
function visit(path) {
 if(visited.has(path))return;
 visited.add(path);
 const bytes=readFileSync(join(source,'dist',path));
 result[path]=createHash('sha256').update(bytes).digest('hex');
 if(!path.endsWith('.js'))return;
 for(const match of bytes.toString('utf8').matchAll(/\b(?:import|export)\s+(?:[^"'\n;]*?\sfrom\s*)?["'](\.{1,2}\/[^"']+)["']/g)){
  const dependency=posix.normalize(posix.join(posix.dirname(path),match[1].split(/[?#]/)[0]));
  if(dependency.startsWith('../'))throw new Error('Import escapes asset root: '+dependency);
  visit(dependency);
 }
}
for(const path of [...rootModules,'city/premium/manifest.json'])visit(path);
writeFileSync(new URL('./web84-sources.json',import.meta.url),JSON.stringify(Object.fromEntries(Object.entries(result).sort()),null,2)+'\n');
console.log('Pinned files:',Object.keys(result).length);
