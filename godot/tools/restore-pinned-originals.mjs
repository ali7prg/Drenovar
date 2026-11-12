import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {dirname,join,resolve} from 'node:path';
import {createHash} from 'node:crypto';

// This importer copies ONLY identical, SHA256-verified binary originals.
// Upstream site scripts can change; never copy current unpinned game code.
const root=resolve(import.meta.dirname,'../project/assets');
const expected=JSON.parse(await readFile(join(root,'original-assets.json'),'utf8'));
const source=new URL('https://drenovar.pink-lyric-9420.chatgpt.site/');
const entries=Object.entries(expected).sort(([a],[b])=>a.localeCompare(b));
const outcome={matched:[],already_present:[],missing_or_changed:[],errors:[]};
let pos=0;
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');

async function work(){
  while(true){
    const entry=entries[pos++];
    if(!entry)return;
    const [path,sha256]=entry;
    if(path.startsWith('/')||path.startsWith('../')||path.includes('/../')||path.includes('\\')){
      outcome.errors.push({path,reason:'invalid path'});
      continue;
    }
    const dest=join(root,path);
    let old;
    try{old=await readFile(dest);}catch{}
    if(old&&hash(old)===sha256){
      outcome.already_present.push(path);
      continue;
    }
    const url=new URL(path,source);
    if(url.origin!==source.origin){
      outcome.errors.push({path,reason:'external URL'});
      continue;
    }
    try{
      const response=await fetch(url,{signal:AbortSignal.timeout(45000)});
      if(!response.ok){
        outcome.missing_or_changed.push({path,reason:'HTTP '+response.status});
        continue;
      }
      const bytes=Buffer.from(await response.arrayBuffer());
      if(hash(bytes)!==sha256){
        outcome.missing_or_changed.push({path,reason:'upstream hash differs'});
        continue;
      }
      await mkdir(dirname(dest),{recursive:true});
      await writeFile(dest,bytes);
      outcome.matched.push(path);
    }catch(e){outcome.errors.push({path,reason:String(e).slice(0,300)});}
  }
}

await Promise.all(Array.from({length:6},work));
for(const key of Object.keys(outcome))outcome[key].sort((a,b)=>String(a.path??a).localeCompare(String(b.path??b)));
const report={
  source:'DRENOVAR Godot 0.5.9 frozen original-assets.json',
  expected_original_files:entries.length,
  newly_recovered:outcome.matched.length,
  already_present:outcome.already_present.length,
  missing_or_changed:outcome.missing_or_changed,
  errors:outcome.errors,
  recovered_paths:outcome.matched,
  existing_paths:outcome.already_present
};
const reportPath=resolve(import.meta.dirname,'../../docs/UPSTREAM_ASSET_FETCH.json');
await mkdir(dirname(reportPath),{recursive:true});
await writeFile(reportPath,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({expected:entries.length,restored:outcome.matched.length,
 existing:outcome.already_present.length,unavailable:outcome.missing_or_changed.length,errors:outcome.errors.length}));
if(outcome.matched.length+outcome.already_present.length<2){
 throw new Error('No meaningful SHA256-verified upstream assets available; no commit should be made');
}
