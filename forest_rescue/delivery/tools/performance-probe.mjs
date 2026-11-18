/** Opt-in synchronous CPU/submission diagnostics. No network, no new RAF loop. */
export class Distribution {
  constructor() { this.bins = new Uint32Array(4001); this.count=0; this.total=0; this.maximum=0; this.over50=0; this.over100=0; }
  add(ms) {
    if (!Number.isFinite(ms) || ms < 0) return;
    this.bins[Math.min(4000, Math.floor(ms*4))]++;
    this.count++; this.total+=ms; this.maximum=Math.max(this.maximum,ms);
    if(ms>50)this.over50++; if(ms>100)this.over100++;
  }
  report() {
    let cumulative=0,p50=null,p95=null;
    for(let i=0;i<this.bins.length;i++) {
      cumulative+=this.bins[i]; const edge=i===4000?'>=1000':(i+1)/4;
      if(this.count && p50===null && cumulative>=Math.ceil(this.count*.5))p50=edge;
      if(this.count && cumulative>=Math.ceil(this.count*.95)){p95=edge;break;}
    }
    return {count:this.count,meanMs:this.count?this.total/this.count:null,p50UpperMs:p50,p95UpperMs:p95,maxMs:this.count?this.maximum:null,over50:this.over50,over100:this.over100,resolutionMs:.25};
  }
}
export function createPerformanceProbe({now=()=>performance.now(),maxSeries=32}={}) {
  if(!Number.isInteger(maxSeries)||maxSeries<1||maxSeries>128)throw Error('Invalid maxSeries');
  const series=new Map(),restorers=[],frames=new Map(),counts=new Map();
  let closed=false,droppedSeries=0,segment=0;
  function add(name,value){if(closed)return;if(!series.has(name)){if(series.size>=maxSeries){droppedSeries++;return;}series.set(name,new Distribution());}series.get(name).add(value);}
  function boundary(){segment++;frames.clear();}
  function frame(name,at=now(),info=null){
    if(closed||!Number.isFinite(at))return;
    if(!frames.has(name)&&frames.size>=maxSeries){droppedSeries++;return;}
    if(!counts.has(name)&&counts.size>=maxSeries){droppedSeries++;return;}
    const previous=frames.get(name);if(previous!==undefined&&at>=previous)add(name+':submissionInterval',at-previous);
    frames.set(name,at);
    // renderer.info counts are object counts and submitted primitives, never GPU bytes.
    if(info){const old=counts.get(name)??{samples:0,maxCalls:0,maxTriangles:0,maxTextures:0,maxGeometries:0};old.samples++;
      for(const [key,value] of [['maxCalls',info.render?.calls],['maxTriangles',info.render?.triangles],['maxTextures',info.memory?.textures],['maxGeometries',info.memory?.geometries]])if(Number.isFinite(value))old[key]=Math.max(old[key],value);
      counts.set(name,old);
    }
  }
  function wrap(object,key,name,{after=null}={}){
    if(closed)throw Error('Probe disposed');
    if(!object||typeof object[key]!=='function')throw Error('Missing method: '+key);
    const previous=object[key];
    function measured(...args){
      if(closed)return previous.apply(this,args);
      const at=now();let succeeded=false,result;
      try{result=previous.apply(this,args);succeeded=true;return result;}
      finally{add(name,now()-at);if(succeeded&&after)after.call(this,result,args);}
    }
    object[key]=measured;
    const restore=()=>{if(object[key]===measured)object[key]=previous;};restorers.push(restore);return restore;
  }
  function measure(name,fn){const at=now();try{return fn();}finally{add(name,now()-at);}}
  function dispose(){if(closed)return;closed=true;for(const restore of restorers.reverse())restore();frames.clear();}
  function report(){return {format:'drenovar-rescue-probe-v1',segment,disposed:closed,droppedSeries,series:Object.fromEntries([...series].map(([k,v])=>[k,v.report()])),rendererCounts:Object.fromEntries(counts),limits:{cpu:'Inclusive synchronous JavaScript wall time; nested series must not be added together.',intervals:'Submission intervals during explicit active scenario, not display/GPU FPS. Call boundary on hide, scene change and idle scenario boundaries.',memory:'Object counts only; no claim of GPU bytes.',promises:'Wrapping an async method measures invocation only; await/network latency is excluded.'}};}
  return {add,frame,wrap,measure,boundary,dispose,report};
}
/** Must be installed on the actual live CityView after EncounterLayer attachment. */
export function attachCityProbe(view,options={}){
  const p=createPerformanceProbe(options);if(!view?.renderClock||!view?.premium)throw Error('CityView not ready');
  p.wrap(view.renderClock,'tick','city:wholeTick');
  p.wrap(view.premium,'update','city:premiumUpdate');
  if(view.premium.muster?.update)p.wrap(view.premium.muster,'update','city:musterUpdate');
  if(view.premium.life?.update)p.wrap(view.premium.life,'update','city:lifeUpdate');
  if(view.premium.updateForestLOD)p.wrap(view.premium,'updateForestLOD','city:forestLOD');
  p.wrap(view,'drawMarkers','city:markers');
  p.wrap(view,'draw','city:draw');
  // Only count a submitted render for THIS scene; shared world renderer also calls render.
  if(view.renderer?.render){p.wrap(view.renderer,'render','renderer:submitCPU',{after(_result,args){if(args[0]===view.scene)p.frame('city',undefined,this.info);}});}
  p.wrap(view,'suspend','city:suspend',{after(){p.boundary();}});
  p.wrap(view,'resume','city:resume',{after(){p.boundary();}});
  return p;
}
/** Hooks worldLoop.tick (VisibleFrameLoop) and existing phase objects passed by world.js. */
export function attachWorldProbe({worldLoop,renderer,scene,groundCover,townLayer,environmentLayer,nativeActors},options={}){
  const p=createPerformanceProbe(options);if(!worldLoop||!renderer||!scene)throw Error('World not ready');
  p.wrap(worldLoop,'tick','world:wholeTick');
  for(const [object,key,label] of [[groundCover,'update','groundCover'],[townLayer?.userData,'update','townLOD'],[environmentLayer,'update','environment'],[nativeActors,'draw','actors']])if(object?.[key])p.wrap(object,key,'world:'+label);
  p.wrap(renderer,'render','renderer:submitCPU',{after(_result,args){if(args[0]===scene)p.frame('world',undefined,this.info);}});
  return p;
}
