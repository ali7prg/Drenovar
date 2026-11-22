import {readFile,writeFile,stat} from 'node:fs/promises';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import validator from 'gltf-validator';
const here=dirname(fileURLToPath(import.meta.url));
const assets=resolve(here,'../../project/assets/city/architecture-v6');
const only=process.argv.find(a=>a.startsWith('--only='))?.slice(7);
let manifestPath=resolve(assets,only?`manifest-${only}.json`:'manifest.json');
try {await stat(manifestPath);} catch {manifestPath=resolve(assets,'manifest.json');}
const manifest=JSON.parse(await readFile(manifestPath,'utf8'));
const files=[];
const groups={...manifest.levels,...Object.fromEntries(Object.entries(manifest.units||{}).map(([id,row])=>[id,{unit:row}]))};
for(const [type,levels] of Object.entries(groups)){
  if(only&&type!==only)continue;
  for(const level of Object.keys(levels)){
    const key=level==='unit'?type:`${type}-${level}`;
    const path=resolve(assets,'web-staging',`${key}-shared.gltf`);
    const result=await validator.validateString(await readFile(path,'utf8'),{
      uri:key+'.gltf',maxIssues:100,
      externalResourceFunction:async uri=>new Uint8Array(await readFile(resolve(dirname(path),decodeURIComponent(uri))))
    });
    const {numErrors,numWarnings,messages}=result.issues;
    const information={};
    for(const issue of messages.filter(message=>message.severity>=2)) information[issue.code]=(information[issue.code]||0)+1;
    files.push({key,errors:numErrors,warnings:numWarnings,information,
      messages:messages.filter(message=>message.severity<2)});
    console.log(`GLTF_SPEC ${key} errors=${numErrors} warnings=${numWarnings}`);
  }
}
const errors=files.reduce((s,r)=>s+r.errors,0);
const warnings=files.reduce((s,r)=>s+r.warnings,0);
await writeFile(resolve(assets,only?`gltf-spec-validation-${only}.json`:'gltf-spec-validation.json'),JSON.stringify({status:errors?'error':'passed',validator:'Khronos gltf-validator 2.0.0-dev.3.10',errors,warnings,files},null,2)+'\n');
process.exitCode=errors?1:0;
