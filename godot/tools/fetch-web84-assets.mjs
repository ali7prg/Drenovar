import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {join,dirname,resolve} from 'node:path';
import {createHash} from 'node:crypto';

const source=resolve(process.argv[2]??'build/web84');
const manifest=JSON.parse(await readFile(new URL('./web84-sources.json',import.meta.url)));
const files=Object.entries(manifest);
const base=new URL('https://drenovar.pink-lyric-9420.chatgpt.site/');
await mkdir(source,{recursive:true});
await writeFile(join(source,'package.json'),'{"type":"module"}\n');
let next=0;
async function download(){
 for(;;){
  const item=files[next++];
  if(!item)return;
  const [path,hash]=item;
  const url=new URL(path,base);
  if(url.origin!==base.origin||path.startsWith('../'))throw new Error('Unsafe asset path');
  let bytes;
  try{bytes=await readFile(join(source,'dist',path));}catch{}
  if(bytes&&createHash('sha256').update(bytes).digest('hex')===hash)continue;
  const response=await fetch(url,{signal:AbortSignal.timeout(45000)});
  if(!response.ok)throw new Error(path+': '+response.status);
  bytes=Buffer.from(await response.arrayBuffer());
  if(createHash('sha256').update(bytes).digest('hex')!==hash)throw new Error(path+': content differs from the pinned web reference');
  const out=join(source,'dist',path);
  await mkdir(dirname(out),{recursive:true});
  await writeFile(out,bytes);
 }
}
await Promise.all(Array.from({length:6},download));
console.log('Verified original source files:',files.length);
