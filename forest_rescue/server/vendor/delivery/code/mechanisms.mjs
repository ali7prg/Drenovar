/** Pure authored mechanism helper. Definition/context are server-owned, not client JSON. */
import {assertAdventureAccess} from './adventure-access.mjs';
const kinds=['trail_cache','rune_lock','winch_sequence','paired_latch'];
const fail=code=>{const e=new Error(code);e.code=code;throw e;};
function definition(site){
  if(!site||typeof site.id!=='string'||!kinds.includes(site.variation)||!Array.isArray(site.artifact?.puzzle?.solution))fail('INVALID_MECHANISM_DEFINITION');
  const solution=site.artifact.puzzle.solution;
  if(solution.length!==3||new Set(solution).size!==3||solution.some(s=>typeof s!=='string'||!s))fail('INVALID_MECHANISM_DEFINITION');
  return solution;
}
export function initialMechanism(site){definition(site);return {schemaVersion:1,siteId:site.id,kind:site.variation,progress:[],solved:false,revision:0};}
export function validateMechanism(saved,site){
  const solution=definition(site),keys=['schemaVersion','siteId','kind','progress','solved','revision'];
  if(!saved||Object.keys(saved).length!==keys.length||keys.some(k=>!Object.hasOwn(saved,k))||saved.schemaVersion!==1||saved.siteId!==site.id||saved.kind!==site.variation||
    !Array.isArray(saved.progress)||saved.progress.length>3||new Set(saved.progress).size!==saved.progress.length||
    typeof saved.solved!=='boolean'||saved.solved!==(saved.progress.length===3)||!Number.isSafeInteger(saved.revision)||saved.revision<0)fail('INVALID_MECHANISM_STATE');
  if(!saved.progress.every((symbol,i)=>symbol===solution[i]))fail('INVALID_MECHANISM_STATE');
  return saved;
}
export function reduceMechanism(saved,input,site,trusted){
  assertAdventureAccess(trusted);
  validateMechanism(saved,site);const solution=definition(site);
  if(!input||Object.keys(input).length!==1||typeof input.symbol!=='string'||!solution.includes(input.symbol))fail('INVALID_MECHANISM_INPUT');
  if(!trusted||typeof trusted.authenticatedPlayerId!=='string'||!trusted.authenticatedPlayerId||trusted.siteAccessVerified!==true||trusted.siteDiscovered!==true)fail('MECHANISM_ACCESS_DENIED');
  if(trusted.campaignPaused===true)fail('CAMPAIGN_PAUSED');
  const state=structuredClone(saved),effects=[];
  if(!state.solved){
    if(site.variation==='trail_cache'&&trusted.observedLandmark!==input.symbol)fail('LANDMARK_NOT_REACHED');
    if(input.symbol!==solution[state.progress.length]){state.progress=[];effects.push({type:'mechanism_reset',siteId:site.id});}
    else{
      if(site.variation==='paired_latch'&&input.symbol===solution[2]){
        // Previously touching the plates is insufficient. Both must currently be held.
        if(trusted.occupancyServerVerified!==true||trusted.leftOccupied!==true||trusted.rightOccupied!==true)fail('PLATES_NOT_SIMULTANEOUS');
      }
      state.progress.push(input.symbol);state.solved=state.progress.length===3;
      effects.push({type:state.solved?'mechanism_solved':'mechanism_advanced',siteId:site.id});
    }
  }
  const changed=JSON.stringify(saved)!==JSON.stringify(state);
  if(changed){if(saved.revision===Number.MAX_SAFE_INTEGER)fail('REVISION_EXHAUSTED');state.revision++;}
  validateMechanism(state,site);return {state,effects,changed};
}
