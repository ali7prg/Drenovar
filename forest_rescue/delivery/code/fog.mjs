/** Server-owned exploration state. Never accept a client-supplied bitset or path. */
import {MIN_HALL_LEVEL} from './adventure-access.mjs';
export {MIN_HALL_LEVEL};
export const ENTRANCE_CORRIDOR=Object.freeze({from:Object.freeze({x:-8,z:-55}),to:Object.freeze({x:-12,z:-60}),radius:3,transitionMs:1200});
export const FOG_SPEC=Object.freeze({minimumHallLevel:MIN_HALL_LEVEL,schemaVersion:1,atlasId:'lost_forest_atlas_v1',minX:-112,minZ:-112,cellSize:4,columns:56,rows:56,revealRadius:10});
const byteLength=Math.ceil(FOG_SPEC.columns*FOG_SPEC.rows/8);
function encode(bytes){if(typeof Buffer!=='undefined')return Buffer.from(bytes).toString('base64');let s='';for(const n of bytes)s+=String.fromCharCode(n);return btoa(s);}
function decode(s){if(typeof s!=='string'||!/^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(s))throw Error('INVALID_FOG_ENCODING');let b=typeof Buffer!=='undefined'?new Uint8Array(Buffer.from(s,'base64')):Uint8Array.from(atob(s),c=>c.charCodeAt(0));if(b.length!==byteLength||encode(b)!==s)throw Error('INVALID_FOG_ENCODING');return b;}
function bytesFor(state){if(state?.schemaVersion!==1||state.atlasId!==FOG_SPEC.atlasId)throw Error('UNSUPPORTED_FOG_VERSION');if(!Number.isSafeInteger(state.revision)||state.revision<0||state.revision===Number.MAX_SAFE_INTEGER)throw Error('INVALID_FOG_REVISION');if(!state.cursors||typeof state.cursors!=='object'||Array.isArray(state.cursors)||Object.keys(state.cursors).length>64||Object.values(state.cursors).some(v=>!Number.isSafeInteger(v)||v<0))throw Error('INVALID_FOG_CURSOR');return decode(state.exploredBase64);}
function cellAt(x,z){const c=Math.floor((x-FOG_SPEC.minX)/FOG_SPEC.cellSize),r=Math.floor((z-FOG_SPEC.minZ)/FOG_SPEC.cellSize);return c<0||r<0||c>=56||r>=56?-1:r*56+c;}
function point(p){return p&&Number.isFinite(p.x)&&Number.isFinite(p.z)&&p.x>=-112&&p.x<112&&p.z>=-112&&p.z<112;}
function mark(bytes,x,z){const index=cellAt(x,z);if(index>=0)bytes[index>>3]|=1<<(index&7);}
function disc(bytes,p,radius=10){const minC=Math.max(0,Math.ceil((p.x-radius+110)/4)),maxC=Math.min(55,Math.floor((p.x+radius+110)/4)),minR=Math.max(0,Math.ceil((p.z-radius+110)/4)),maxR=Math.min(55,Math.floor((p.z+radius+110)/4));for(let r=minR;r<=maxR;r++)for(let c=minC;c<=maxC;c++){const x=-110+c*4,z=-110+r*4;if(Math.hypot(x-p.x,z-p.z)<=radius)mark(bytes,x,z);}}
export function createFogState(){const b=new Uint8Array(byteLength);for(let z=-54;z<=54;z+=4)for(let x=-54;x<=54;x+=4)mark(b,x,z);return{schemaVersion:1,atlasId:FOG_SPEC.atlasId,revision:0,exploredBase64:encode(b),cursors:{}};}
/** Server storage query only. Client rendering must use projectFogForClient. */
export function isExplored(state,x,z){const b=bytesFor(state),i=cellAt(x,z);return i>=0&&!!(b[i>>3]&(1<<(i&7)));}
export function exploredCellCount(state){return Array.from(bytesFor(state)).reduce((sum,v)=>{while(v){sum+=v&1;v>>=1;}return sum;},0);}
export function validateFogState(state){bytesFor(state);return true;}
function authenticated(auth){return !!auth&&typeof auth.authenticatedPlayerId==='string'&&!!auth.authenticatedPlayerId;}
export function forestUnlocked(auth){return authenticated(auth)&&Number.isSafeInteger(auth.hallLevel)&&auth.hallLevel>=MIN_HALL_LEVEL;}
/** Server-side projection. Never send the stored bitset/cursors directly to a client.
 * auth.hallLevel must come from the verified selected settlement's actual hall.
 * A lower/invalid hall hides legacy exploration without modifying it. POI inputs
 * are server-owned authored metadata, never request body coordinates.
 */
export function projectFogForClient(state,auth,{pois=[],protectedTownCells=[]}={}){
 const stored=bytesFor(state);
 if(!authenticated(auth))throw Error('AUTH_REQUIRED');
 if(!Array.isArray(pois)||pois.some(p=>!p||typeof p.id!=='string'||!point(p)))throw Error('INVALID_POI_METADATA');
 if(!Array.isArray(protectedTownCells)||protectedTownCells.length>3136||!protectedTownCells.every(point))throw Error('INVALID_TOWN_MASK');
 const unlocked=forestUnlocked(auth),visible=unlocked?stored:bytesFor(createFogState());
 // Derived solely from actual protected town/property footprints, never stored
 // exploration or client input. Existing property remains visible at every level.
 for(const p of protectedTownCells)mark(visible,p.x,p.z);
 if(unlocked){
  // Open only a short approach beyond the visible town. Actual squad movement
  // continues to reveal the route; unlocking never clears the entire forest.
  for(let i=0;i<=8;i++)disc(visible,{x:ENTRANCE_CORRIDOR.from.x+(ENTRANCE_CORRIDOR.to.x-ENTRANCE_CORRIDOR.from.x)*i/8,z:ENTRANCE_CORRIDOR.from.z+(ENTRANCE_CORRIDOR.to.z-ENTRANCE_CORRIDOR.from.z)*i/8},ENTRANCE_CORRIDOR.radius);
 }
 const visibleAt=p=>{const index=cellAt(p.x,p.z);return index>=0&&!!(visible[index>>3]&(1<<(index&7)));};
 return {schemaVersion:1,atlasId:FOG_SPEC.atlasId,storedFogRevision:state.revision,
  explorationLocked:!unlocked,minimumHallLevel:MIN_HALL_LEVEL,
  visibleTerrainBase64:encode(visible),visiblePoiIds:unlocked?pois.filter(visibleAt).map(p=>p.id):[],
  boundaryFog:{animated:true,coverage:unlocked?'unexplored outer forest':'entire outer forest',entranceTransitionMs:unlocked?ENTRANCE_CORRIDOR.transitionMs:0,reducedMotionTransitionMs:0},
  clockPolicy:'visual only; never advances exploration, fights or rewards'};
}
/**
 * resolveTraversal is a trusted SERVER adapter. It reads committed march/escort
 * progress for the authenticated selected settlement p.id (auth.authenticatedPlayerId) and returns only already traversed, nav-verified
 * positions. auth.hallLevel is read from the verified selected settlement hall,
 * never a request body, camera state, client save, or legacy explored mask.
 * The network command contains IDs, never coordinates, radius, or hallLevel.
 * Store resulting state by CAS with the same authoritative world transaction.
 */
export function createFogAuthority({resolveTraversal}){
 if(typeof resolveTraversal!=='function')throw Error('MISSING_TRAVERSAL_ADAPTER');
 return {async reveal(state,command,auth){
   const bytes=bytesFor(state);
   if(!authenticated(auth))throw Error('AUTH_REQUIRED');
   if(!forestUnlocked(auth))throw Error('FOREST_LOCKED_HALL_LEVEL');
   if(!command||Object.keys(command).sort().join(',')!=='actorId,routeId'||typeof command.actorId!=='string'||typeof command.routeId!=='string'||!command.actorId||!command.routeId||command.actorId.length>128||command.routeId.length>128)throw Error('INVALID_FOG_COMMAND');
   const tr=await resolveTraversal({authenticatedPlayerId:auth.authenticatedPlayerId,actorId:command.actorId,routeId:command.routeId});
   if(!tr||tr.ownerId!==auth.authenticatedPlayerId||tr.actorId!==command.actorId||tr.routeId!==command.routeId||tr.navigationChecked!==true||tr.committed!==true)throw Error('UNVERIFIED_TRAVERSAL');
   if(!Number.isSafeInteger(tr.sequence)||tr.sequence<0||!Array.isArray(tr.path)||!tr.path.length||tr.path.length>4096||!tr.path.every(point))throw Error('INVALID_TRAVERSAL');
   // JSON tuple avoids collisions between actor and route IDs.
   const key=JSON.stringify([command.actorId,command.routeId]);
   if(Object.hasOwn(state.cursors,key)&&state.cursors[key]>=tr.sequence)return structuredClone(state);
   if(!Object.hasOwn(state.cursors,key)&&Object.keys(state.cursors).length>=64)throw Error('CURSOR_COMPACTION_REQUIRED');
   for(let i=0;i<tr.path.length;i++){
     const a=tr.path[Math.max(0,i-1)],b=tr.path[i],len=Math.hypot(b.x-a.x,b.z-a.z);
     // Prevent an erroneously coarse path from revealing a straight shortcut.
     if(len>8.000001)throw Error('TRAVERSAL_NOT_DENSIFIED');
     const n=Math.max(1,Math.ceil(len/2));for(let j=0;j<=n;j++)disc(bytes,{x:a.x+(b.x-a.x)*j/n,z:a.z+(b.z-a.z)*j/n});
   }
   return{...structuredClone(state),revision:state.revision+1,exploredBase64:encode(bytes),cursors:{...state.cursors,[key]:tr.sequence}};
 }};
}
