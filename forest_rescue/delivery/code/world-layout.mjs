/** Engine-independent authored-atlas helpers. No player-state mutations. */
export const CHUNK_SIZE=56,MIN=-112,MAX=112;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
export function chunkIdAt(x,z){if(!Number.isFinite(x)||!Number.isFinite(z)||x<MIN||z<MIN||x>=MAX||z>=MAX)return null;return `lf_chunk_${Math.floor((x-MIN)/56)}_${Math.floor((z-MIN)/56)}`;}
export function allChunks(){return Array.from({length:16},(_,i)=>{const x=i%4,z=Math.floor(i/4);return{id:`lf_chunk_${x}_${z}`,minX:MIN+x*56,maxX:MIN+(x+1)*56,minZ:MIN+z*56,maxZ:MIN+(z+1)*56};});}
function hash(s){let h=2166136261;for(const ch of s)h=Math.imul(h^ch.charCodeAt(0),16777619);return h>>>0;}
function rng(seed){return()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};}
function segmentDistance(p,a,b){const dx=b.x-a.x,dz=b.z-a.z,t=clamp(((p.x-a.x)*dx+(p.z-a.z)*dz)/(dx*dx+dz*dz||1),0,1);return Math.hypot(p.x-a.x-t*dx,p.z-a.z-t*dz);}
function validMask(m){if(!m||typeof m!=='object')return false;if(m.type==='box')return [m.minX,m.maxX,m.minZ,m.maxZ].every(Number.isFinite)&&m.minX<=m.maxX&&m.minZ<=m.maxZ;if(m.type==='circle')return [m.x,m.z,m.radius].every(Number.isFinite)&&m.radius>0;if(m.type==='capsule')return !!m.a&&!!m.b&&[m.a.x,m.a.z,m.b.x,m.b.z,m.radius].every(Number.isFinite)&&m.radius>0;return false;}
export function insideMask(p,mask,margin=0){
 if(mask.type==='circle')return Math.hypot(p.x-mask.x,p.z-mask.z)<=mask.radius+margin;
 if(mask.type==='box')return p.x>=mask.minX-margin&&p.x<=mask.maxX+margin&&p.z>=mask.minZ-margin&&p.z<=mask.maxZ+margin;
 if(mask.type==='capsule')return segmentDistance(p,mask.a,mask.b)<=mask.radius+margin;
 throw Error('UNSUPPORTED_MASK');
}
export const SCATTER_COVERAGE=['playerBuildings','futurePlots','resources','pendingHarvest','armyRoutes','military','otherAdventures'];
export function generateScatter({chunkId,seed=1701,count=96,masks,maskRevision,coverage,terrain,zoneId='forest',species=['lf_tree_pine','lf_tree_birch','lf_fern_cluster']}={}){
 if(typeof maskRevision!=='string'||!maskRevision||!Array.isArray(masks)||SCATTER_COVERAGE.some(k=>coverage?.[k]!==true))throw Error('INCOMPLETE_RESERVE_MASKS');
 if(!masks.every(validMask))throw Error('INVALID_RESERVE_MASK');
 if(!Array.isArray(species)||!species.length||species.some(x=>typeof x!=='string'||!x))throw Error('INVALID_SPECIES');
 masks=[{type:'box',minX:-56,maxX:56,minZ:-56,maxZ:56},...masks];
 const chunk=allChunks().find(c=>c.id===chunkId);if(!chunk||typeof terrain!=='function'||!Number.isSafeInteger(count)||count<0||count>1000)throw Error('INVALID_SCATTER_INPUT');
 const r=rng(hash(`${seed}:${chunkId}:${zoneId}`)),result=[];let attempts=0;
 while(result.length<count&&attempts++<count*40){
  const x=chunk.minX+r()*56,z=chunk.minZ+r()*56,scale=.8+r()*.65,angle=r()*Math.PI*2;
  if(masks.some(m=>insideMask({x,z},m,1.3*scale)))continue;
  const sample=terrain(x,z);if(!sample||sample.dry!==true||!Number.isFinite(sample.y)||!Number.isFinite(sample.slope)||sample.slope>28)continue;
  if(result.some(p=>Math.hypot(p.x-x,p.z-z)<2.2))continue;
  result.push({id:`${chunkId}:ambient:${result.length}`,assetId:species[Math.floor(r()*species.length)],x,y:sample.y,z,scale,yaw:angle,ownership:'ambient',seed});
 }
 return {chunkId,requested:count,placed:result.length,exhausted:result.length<count,instances:result};
}
export function selectChunks({camera,viewRadius=65,pinnedPoints=[],isChunkExplored=()=>true,fullBudget=4,proxyBudget=8}={}){
 if(!camera||![camera.x,camera.z,viewRadius].every(Number.isFinite)||viewRadius<0||!Number.isSafeInteger(fullBudget)||fullBudget<1||fullBudget>16||!Number.isSafeInteger(proxyBudget)||proxyBudget<0||proxyBudget>16)throw Error('INVALID_STREAM_INPUT');
 const pinned=new Set(pinnedPoints.map(p=>chunkIdAt(p.x,p.z)));if(pinned.has(null))throw Error('INVALID_PIN');
 const chunks=allChunks().map(c=>({...c,distance:Math.hypot(camera.x-clamp(camera.x,c.minX,c.maxX),camera.z-clamp(camera.z,c.minZ,c.maxZ)),pinned:pinned.has(c.id),explored:isChunkExplored(c.id)===true}));
 chunks.sort((a,b)=>Number(b.pinned)-Number(a.pinned)||a.distance-b.distance||a.id.localeCompare(b.id));
 const full=[],proxy=[],fogOnly=[],unloaded=[];
 for(const c of chunks){if(c.pinned){full.push(c.id);continue;}if(c.distance>viewRadius+20){unloaded.push(c.id);continue;}if(!c.explored){fogOnly.push(c.id);continue;}if(c.distance<=viewRadius&&full.length<fullBudget)full.push(c.id);else if(proxy.length<proxyBudget)proxy.push(c.id);else unloaded.push(c.id);}
 return{full,proxy,fogOnly,unloaded,overflow:Math.max(0,full.length-fullBudget),policy:'Pinned authoritative actors stay loaded; overflow requires measured quality reduction, never gameplay pause.'};
}
