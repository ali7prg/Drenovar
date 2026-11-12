import {copyFileSync,existsSync,mkdirSync,readFileSync,writeFileSync} from 'node:fs';
import {dirname,join,normalize,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';

const source = resolve(process.argv[2] ?? '../drenovar-web84');
const out = resolve(import.meta.dirname,'../project/assets');
const dist = join(source,'dist');
const load = path => import(pathToFileURL(join(dist,path)));
const {terrainLots,cityRoads,scatterTerrain,tuftGeometry} = await load('city/terrain.js');
const {getCityPlots,cityPlots} = await load('city/state.js');
const {forestLayout,treeDefinition,CLEARINGS} = await load('city/woodland.js');
const {settlementHeight,riverWetEdge,WATER_LEVEL,forestFloor,rockWeight,landscapeProps} = await load('city/landform.js');
const {buildings} = await load('city/registry.js');
const {englishRoster} = await load('army/roster.js');
const {unitVisuals} = await load('army/unit-visuals.js');
const {trainingGroup} = await load('city/military.js');
const {militaryCultures} = await load('city/military-cultures.js');
const {baseType,buildingUnlock,buildingCost,buildingSeconds62,unitRequirements} = await load('city/kingdom29.js');
const {productionBase,productionFor,upgradeSupported,speedItems,upgradeTerms,storageFor} = await load('city/upgrade-v1.js');
const {prices62} = await load('city/trade62.js');
const {starterObjective71} = await load('city/starter71.js');
const {worldSites62} = await load('environment/world-sites62.js');
const {height,riverPaths} = await load('environment/world-field56.js');
const {buildWorldData56} = await load('environment/world-build56.js');
const {townBuildings} = await load('environment/world-towns.js');
const {atlasData} = await load('environment/atlas-data.js');
const {makeModel} = await load('environment/models.js');
const {canopySpec,canopyGeometry} = await load('environment/world-canopy.js');
const {understoryLayout} = await load('city/life.js');
const {upgradeDetailsGeometry,scaffoldGeometry} = await load('city/building-upgrade-visual.js');
const {meadowFlower75,meadowRock75} = await load('city/meadow75.js');
const THREE = await load('vendor/three.module.js');

const manifest = JSON.parse(readFileSync(join(dist,'city/premium/manifest.json'),'utf8'));
const cityFiles = new Set([...Object.values(manifest.types),manifest.starterHall,'garrison27',
 'Worker_Carrier','Worker_Farmer','Worker_Lumberjack','Worker_Smith']);
for (let i=0;i<6;i++) for (const suffix of ['', 'mid', 'far']) cityFiles.add('tree'+i+suffix);
const copied = new Set();
function asset(path) {
 const name=join(out,path);
 if (path.startsWith('../')) throw new Error('Asset reference escapes source directory: '+path);
 if (!copied.has(path)) {
  mkdirSync(dirname(name),{recursive:true});
  const input=join(dist,path);
  copyFileSync(path.startsWith('creature-assets37/')&&!existsSync(input)
   ?join(source,'gameplay37/assets',path.slice('creature-assets37/'.length)):input,name);
  copied.add(path);
  if (path.endsWith('.glb')) {
   const glb=readFileSync(name);
   const json=JSON.parse(glb.subarray(20,20+glb.readUInt32LE(12)));
   for (const dependency of [...(json.images??[]),...(json.buffers??[])]) {
    if (dependency.uri && !dependency.uri.startsWith('data:'))
     asset(normalize(join(dirname(path),decodeURIComponent(dependency.uri))));
   }
  }
 }
 return 'res://assets/'+path;
}
const models = {};
for (const id of cityFiles) {
 const {file,scale} = manifest.models[id];
 models[id]={path:asset('city/premium/'+file),scale};
}
const distantModels={};
for(const id of ['hall','house',...Array.from({length:6},(_,i)=>'tree'+i)]){
 const {sprite,scale}=manifest.models[id];
 distantModels[id]={path:asset('city/premium/'+sprite.file),anchor:sprite.anchor,size:sprite.worldSize/scale};
}
for (const kind of ['grass','grass20','path','soil','drill20']) {
 for (const [role,ext] of [['albedo','webp'],['normal','png'],['roughness','png']]) {
  asset('city/premium/surfaces07/'+kind+'-'+role+'.'+ext);
 }
}
const unitModels=Object.fromEntries(Object.entries(unitVisuals).map(([id,unit])=>[
 id,{preview:asset('army/assets/'+unit.file+'-lod1.glb'),field:asset('army/assets/'+unit.file+'-lod2.glb'),drill:unit.drill??unit.clip}
]));
const creatureModels=Object.fromEntries(['velkor','tenerys','kamneklyk','dragor'].map(id=>[
 id,[1,2,3].map(level=>asset(`creature-assets37/${id.toUpperCase()}_L${level}_RIGGED_ANIMATED.glb`))
]));
const portraits=[1,2,3].map(level=>asset('creatures37/velkor63-'+level+'.webp'));
asset('icons/drenovar_icon_512.png');
const environmentTexture = asset('environment/surfaces20.png');
const environmentAtlas = asset('environment/atlas.webp');
const stoneTexture = asset('city/premium/surfaces07/stone-albedo.jpg');

const demo = JSON.parse(readFileSync(join(import.meta.dirname,'starter-state.json'),'utf8'));
const city = demo.city;
const starterGoals = [];
const starterCity = structuredClone(city);
starterCity.kingdom.guide.starterClaims71 = {};
for (let goal = starterObjective71(starterCity); goal?.id; goal = starterObjective71(starterCity)) {
 const {id,title,reward} = goal;
 starterGoals.push({id,title,reward});
 starterCity.kingdom.guide.starterClaims71[id] = 1;
}
const plots = getCityPlots(city).map(p=>({...p,x:p.x*.82,z:p.z*.82}));
const lots = terrainLots(city,plots,manifest);
const cityHeight = settlementHeight(lots);
const sites = worldSites62().map((p,i)=>({...p,slot:'slot-'+i,kind:i%9===0?'fort':'city'}));
const world = buildWorldData56({settlements:sites});
const vector = (x,z,y) => [x,y,z];

function writeMesh(name, attributes, indices) {
 const views=[],accessors=[],chunks=[];
 let byteLength=0;
 function accessor(array,type,componentType,count,min,max,target) {
  const raw=Buffer.from(array.buffer,array.byteOffset,array.byteLength);
  const block=Buffer.alloc(Math.ceil(raw.length/4)*4);raw.copy(block);
  views.push({buffer:0,byteOffset:byteLength,byteLength:raw.length,target});
  chunks.push(block);byteLength+=block.length;
  accessors.push({bufferView:views.length-1,componentType,count,type,...(min?{min,max}:{})});
  return accessors.length-1;
 }
 const vertexCount=attributes.position.length/3;
 const min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];
 for(let i=0;i<attributes.position.length;i++) {
  const axis=i%3;min[axis]=Math.min(min[axis],attributes.position[i]);max[axis]=Math.max(max[axis],attributes.position[i]);
 }
 const semantics={
  POSITION:accessor(attributes.position,'VEC3',5126,vertexCount,min,max,34962),
  NORMAL:accessor(attributes.normal,'VEC3',5126,vertexCount,null,null,34962),
  TEXCOORD_0:accessor(attributes.uv,'VEC2',5126,vertexCount,null,null,34962)
 };
 if(attributes.color)semantics.COLOR_0=accessor(attributes.color,'VEC3',5126,vertexCount,null,null,34962);
 if(attributes.uv2)semantics.TEXCOORD_1=accessor(attributes.uv2,'VEC2',5126,vertexCount,null,null,34962);
 const index=accessor(indices,'SCALAR',indices instanceof Uint32Array?5125:5123,indices.length,null,null,34963);
 const bin=Buffer.concat(chunks);
 const json=Buffer.from(JSON.stringify({asset:{version:'2.0'},scene:0,scenes:[{nodes:[0]}],
  nodes:[{mesh:0,name}],meshes:[{primitives:[{attributes:semantics,indices:index}]}],accessors,bufferViews:views,buffers:[{byteLength:bin.length}]}));
 const padding=Buffer.alloc(Math.ceil(json.length/4)*4,32);json.copy(padding);
 const header=Buffer.alloc(12),jsonHeader=Buffer.alloc(8),binHeader=Buffer.alloc(8);
 header.write('glTF');header.writeUInt32LE(2,4);header.writeUInt32LE(28+padding.length+bin.length,8);
 jsonHeader.writeUInt32LE(padding.length);jsonHeader.write('JSON',4);
 binHeader.writeUInt32LE(bin.length);binHeader.write('BIN\0',4);
 writeFileSync(join(out,name+'.glb'),Buffer.concat([header,jsonHeader,padding,binHeader,bin]));
}

function generatedMesh(name,geometry) {
 const attributes=Object.fromEntries(Object.entries(geometry.attributes).map(([key,attribute])=>[key,attribute.array]));
 const count=geometry.attributes.position.count;
 if(!attributes.uv)attributes.uv=new Float32Array(count*2);
 const IndexArray=count>65535?Uint32Array:Uint16Array;
 writeMesh(name,attributes,geometry.index?.array??IndexArray.from({length:count},(_,index)=>index));
 geometry.dispose();
 return 'res://assets/'+name+'.glb';
}

const catalog=new Map(atlasData.assets.map(spec=>[spec.id,spec]));
const environmentModels={};
const environment=[];
mkdirSync(join(out,'world-scenery'),{recursive:true});
for(const p of world.environmentData){
 const spec=catalog.get(p.id);
 if(!spec)throw new Error('Unknown environment asset '+p.id);
 if(!environmentModels[p.id]){
  const canopy=canopySpec(p.id);
  const tree=!!canopy;
  environmentModels[p.id]={
   near:generatedMesh('world-scenery/'+p.id,tree?canopyGeometry(p.id,'mid'):makeModel(p.id)),
   far:generatedMesh('world-scenery/'+p.id+'-far',tree?canopyGeometry(p.id,'far'):makeModel(p.id,true)),
   tree,detail:/^(04_|07_|12_|13_)/.test(spec.category),resource:spec.category.startsWith('09_'),
   canopy,
   name:spec.name,category:spec.category
  };
 }
 environment.push({id:p.id,x:p.x,y:p.y,z:p.z,scale:p.scale,rotation:p.rotation});
}
const cityDetails={};
mkdirSync(join(out,'city-details'),{recursive:true});
for(const id of ['fern','round_bush','mossy_rocks','fallen_branches','berry_bush','tree_stump','tall_reeds']){
 cityDetails[id]=generatedMesh('city-details/'+id,makeModel(id));
}
const cityUnderstory=[...understoryLayout(lots,true),...landscapeProps()];
const meadow=Object.fromEntries(Object.entries({grass:tuftGeometry(),rocks:meadowRock75(),flowers:meadowFlower75()})
 .map(([key,geometry])=>[key,generatedMesh('city-details/meadow-'+key,geometry)]));
const groundCover=scatterTerrain(lots,cityRoads(city,plots),2500);
const architecture={};
for(const id of new Set(buildings.map(b=>baseType(b.id)).filter(upgradeSupported))){
 architecture[id]=Object.fromEntries([2,3,4,5].map(level=>[
  level,generatedMesh('city-details/'+id+'-'+level,upgradeDetailsGeometry(id,level))
 ]));
}
const scaffold=generatedMesh('city-details/scaffold',scaffoldGeometry());

const cityDetail = 192, borderDetail = 28, cityIntervals = cityDetail + 2 * borderDetail;
const cityCoordinate = index => {
 if (index < borderDetail) return -336 + 196 * index / borderDetail;
 if (index > borderDetail + cityDetail) return 140 + 196 * (index - borderDetail - cityDetail) / borderDetail;
 return -140 + 280 * (index - borderDetail) / cityDetail;
};
const cityGeometry = new THREE.PlaneGeometry(280,280,cityIntervals,cityIntervals).rotateX(-Math.PI/2);
const cityPosition = cityGeometry.attributes.position;
const shade = new Float32Array(cityPosition.count*3);
const cityWeights = new Float32Array(cityPosition.count*2);
for (let i=0;i<cityPosition.count;i++) {
 const x=cityCoordinate(i % (cityIntervals+1)),z=cityCoordinate(Math.floor(i/(cityIntervals+1)));
 cityPosition.setXYZ(i,x,cityHeight(x,z),z);
 cityGeometry.attributes.uv.setXY(i,x/6,z/6);
 const factor=Math.sin(x*.095+Math.sin(z*.13))*.065+Math.cos(z*.17-x*.07)*.035;
 shade.set([.94+factor,1.01+factor,.9+factor],i*3);
 cityWeights.set([forestFloor(x,z),rockWeight(x,z)],i*2);
}
cityGeometry.computeVertexNormals();
// Normals are calculated before splitting, so the shared tile borders are identical.
function terrainTiles(name, source, columns, rows, tileWidth, tileDepth) {
 const paths=[];
 mkdirSync(join(out,name),{recursive:true});
 for(let z=0;z<rows;z+=tileDepth) for(let x=0;x<columns;x+=tileWidth) {
  const width=Math.min(tileWidth,columns-x),depth=Math.min(tileDepth,rows-z);
  const attributes={};
  for(const [key,array] of Object.entries(source)) {
   const stride=key==='uv'||key==='uv2'?2:3;
   const tile=new Float32Array((width+1)*(depth+1)*stride);
   for(let row=0;row<=depth;row++) {
    const start=((z+row)*(columns+1)+x)*stride;
    tile.set(array.subarray(start,start+(width+1)*stride),row*(width+1)*stride);
   }
   attributes[key]=tile;
  }
  const indices=new Uint16Array(width*depth*6);
  for(let row=0;row<depth;row++) for(let col=0;col<width;col++) {
   const a=row*(width+1)+col, b=a+width+1;
   indices.set([a,b,a+1,b,b+1,a+1],(row*width+col)*6);
  }
  const path=name+'/'+x+'-'+z;
  writeMesh(path,attributes,indices);
  paths.push('res://assets/'+path+'.glb');
 }
 return paths;
}
const cityGround=terrainTiles('city-ground',{
 position:cityPosition.array,normal:cityGeometry.attributes.normal.array,uv:cityGeometry.attributes.uv.array,color:shade,uv2:cityWeights
},cityIntervals,cityIntervals,31,31);
const {biome,...worldAttributes}=world.terrain.attributes;
const uv2=new Float32Array(biome.length/3*2);
for(let i=0;i<biome.length/3;i++){uv2[i*2]=biome[i*3];uv2[i*2+1]=biome[i*3+1];}
const worldGround=terrainTiles('world-ground',{...worldAttributes,uv2},240,192,30,24);
const heights=new Float32Array(241*193);
for(let i=0;i<heights.length;i++)heights[i]=worldAttributes.position[i*3+1];
const worldHeights=Buffer.from(heights.buffer).toString('base64');

const water=[];
for(let z=-336;z<=336;z+=2)water.push([vector(riverWetEdge(z,-1),z,WATER_LEVEL),vector(riverWetEdge(z,1),z,WATER_LEVEL)]);
const roadPositions = [], roadUvs = [], roadIndices = [];
const roadEdges = new Set();
for (const [i, a] of sites.entries()) {
 const neighbors = sites.map((site, j) => ({site,j,distance:Math.hypot(site.x-a.x,site.z-a.z)}))
  .filter(({j}) => j!==i).sort((a,b) => a.distance-b.distance).slice(0,3);
 for (const {site:b,j,distance} of neighbors) {
  const key = [Math.min(i,j),Math.max(i,j)].join(':');
  if (distance>51 || roadEdges.has(key)) continue;
  roadEdges.add(key);
  const path = [[a.x,a.z]];
  for (let k=1;k<9;k++) {
   const t=k/9,bend=Math.sin(t*Math.PI)*Math.sin(i*3+j)*2;
   path.push([a.x+(b.x-a.x)*t+bend,a.z+(b.z-a.z)*t+bend*.6]);
  }
  path.push([b.x,b.z]);
  for (let k=1;k<path.length;k++) {
   const [x,z]=path[k-1],[nextX,nextZ]=path[k];
   const dx=nextX-x,dz=nextZ-z,length=Math.hypot(dx,dz);
   if (length===0) continue;
   const steps=Math.max(2,Math.ceil(length/.9));
   const offset = roadPositions.length / 3;
   for (let s=0;s<=steps;s++) {
    const t=s/steps;
    for (const side of [-1,1]) {
     const xx=x+dx*t+dz/length*.36*side,zz=z+dz*t-dx/length*.36*side;
     roadPositions.push(...vector(xx,zz,height(xx,zz)+.14));
     roadUvs.push(t*length/4,(side+1)/2);
    }
    if (s<steps) {
     const start=offset+s*2;
     roadIndices.push(start,start+1,start+2,start+1,start+3,start+2);
    }
   }
  }
 }
}
const roadGeometry = new THREE.BufferGeometry();
roadGeometry.setAttribute('position',new THREE.Float32BufferAttribute(roadPositions,3));
roadGeometry.setAttribute('uv',new THREE.Float32BufferAttribute(roadUvs,2));
roadGeometry.setIndex(roadIndices);
roadGeometry.computeVertexNormals();
writeMesh('world-roads',Object.fromEntries(Object.entries(roadGeometry.attributes).map(([k,v])=>[k,v.array])),roadGeometry.index.array);
const position = p=>vector(p.x,p.z,cityHeight(p.x,p.z));
const woods = forestLayout([],true).map(t=>({id:t.id,p:position(t),variant:t.variant,angle:t.angle,scale:t.scale,
 village:!!t.village,lod:t.lod,...treeDefinition(t)}));
const treePlots = Object.fromEntries(forestLayout([],true).map(t=>[t.id,{id:'site-'+t.id,x:t.x,z:t.z}]));
const data={
 demo,models,types:manifest.types,starterHall:manifest.starterHall,plots,lots,treePlots,
 legacyPlots:cityPlots.map(p=>({...p,x:p.x*.82,z:p.z*.82})),
 unlockLevels:Object.fromEntries(buildings.map(b=>[b.id,buildingUnlock(b.id)])),
 upgradeRequirements:{2:[['RES-01',1],['RES-04',1]],3:[['RES-02',1],['RES-04',2]],4:[['RES-03',1],['ECO-01',1]],5:[['MIL-02',1],['RES-02',3]]},
 buildingTerms:Object.fromEntries(buildings.map(b=>[b.id,{
  cost:buildingCost(city,b.id),seconds:buildingSeconds62(b.id),
  upgrades:[2,3,4,5].map(level=>upgradeTerms(baseType(b.id),level)),
  storage:storageFor(baseType(b.id),1),
  production:productionBase[baseType(b.id)]?.[0]??null,
  rates:[1,2,3,4,5].map(level=>productionFor(baseType(b.id),level))
 }])),
 unitRequirements,starterGoals,
 upgradable:buildings.filter(b=>upgradeSupported(baseType(b.id))).map(b=>b.id),
 producers:buildings.filter(b=>productionBase[baseType(b.id)]).map(b=>b.id),
 cityRoads:cityRoads(city,plots),cityGround,water,worldRivers:riverPaths,speedItems,tradePrices:prices62,clearings:CLEARINGS,
 woods,worldGround,worldHeights,cityUnderstory,cityDetails,architecture,scaffold,groundCover,meadow,
 environment,environmentModels,distantModels,environmentTexture,environmentAtlas,atlasData,stoneTexture,minimap:Buffer.from(world.minimap).toString('base64'),
 sites:sites.map(p=>({...p,parts:townBuildings(p,height)})),
 buildings,englishRoster:englishRoster.map(unit=>({...unit,legacyLevel:Number(unit.unlocks_at.match(/\d+/)?.[0]??1)})),
 militaryCultures,trainingGroups:Object.fromEntries(buildings.map(b=>[b.id,trainingGroup(b.id)]).filter(([,group])=>group)),unitModels,creatureModels,portraits,
 forestPool:forestLayout([],true).length
};
writeFileSync(join(out,'game.json'),JSON.stringify(data));
const files={};
for(const file of [...new Set(copied)].sort())files[file]=createHash('sha256').update(readFileSync(join(out,file))).digest('hex');
writeFileSync(join(out,'original-assets.json'),JSON.stringify(files,null,2)+'\n');
console.log(JSON.stringify({models:Object.keys(models).length,cityTrees:woods.length,worldObjects:environment.length,sites:sites.length,assets:Object.keys(files).length}));
