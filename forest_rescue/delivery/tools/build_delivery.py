#!/usr/bin/env python3
"""Build independently extractable semantic ZIPs; manifest self-hash is external."""
import csv,hashlib,io,json,pathlib,zipfile,argparse
ROOT=pathlib.Path(__file__).resolve().parents[1]
PREFIX='DRENOVAR_Forest_Rescue/'
MAX=30_000_000

def digest(b): return hashlib.sha256(b).hexdigest()
def writejson(p,o): p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
def excluded(p): return p.name in {'PACKAGE_MANIFEST.json','ASSET_REGISTRY.csv'} or p.suffix in {'.blend1','.log','.pyc'} or '__pycache__' in p.parts

def group(p):
 s=p.as_posix()
 if s in {'START_HERE_RU.md','CLAUDE_CODE_IMPLEMENTATION_BRIEF_RU.md','tools/verify_delivery.py','ASSET_REGISTRY.csv','PACKAGE_MANIFEST.json'}:return 'Start'
 if s.startswith('art/'):
  if p.name.startswith('18_'):return 'UnlockArt'
  if p.name.startswith(('03_','05_','09_','11_')):return 'CreatureArt'
  if p.name.startswith(('04_','12_','horse_','civilian_','rescue_animation')):return 'CharacterArt'
  return 'WorldArt'
 if s.startswith(('assets/audio/','sources/audio/')):return 'Audio'
 if s.startswith(('code/','tests/','tools/','qa/')):return 'Code'
 return 'Concept'

def status(p):
 s=p.as_posix()
 if s.startswith(('art/','previews/')):return 'visual_reference','Просмотр постановки; не импортировать как игровую геометрию'
 if s.startswith(('assets/models/','assets/audio/','assets/textures/')):return 'requires_engine_setup','Игровой ресурс; подключить к сцене/материалу/событию'
 if s.startswith('code/'):return 'requires_engine_setup','Проверенный самостоятельный модуль; адаптер проекта ещё не реализован'
 if s.startswith('sources/'):return 'ready_to_import','Редактируемый исходник/генератор; открыть в указанном инструменте'
 if s.startswith('assets/ui/'):return 'requires_engine_setup','Векторный значок интерфейса; связать с локализацией'
 if s.startswith('data/'):return 'requires_engine_setup','Авторские конфигурации; подключить адаптеры'
 return 'ready_to_import','Документ, проверка или инженерный инструмент; готов к чтению/запуску по инструкции'

def zipbytes(paths):
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in sorted(paths):
   info=zipfile.ZipInfo(PREFIX+p.as_posix(),date_time=(2026,11,17,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
   z.writestr(info,(ROOT/p).read_bytes())
 return out.getvalue()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('output',type=pathlib.Path);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 paths=sorted(p.relative_to(ROOT) for p in ROOT.rglob('*') if p.is_file() and not excluded(p))
 overs=[str(p) for p in paths if (ROOT/p).stat().st_size>MAX]
 if overs:raise RuntimeError('Oversize source; explicit lossless splitting required: '+repr(overs))
 with (ROOT/'ASSET_REGISTRY.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.writer(f);w.writerow(['asset_id','path','format','status','purpose','suggested_destination'])
  for p in paths:
   state,purpose=status(p)
   dest='dist/adventure/forest-rescue/'+str(p.relative_to('assets')) if p.parts[0]=='assets' else 'handoff/'+str(p)
   w.writerow([p.stem if p.suffix=='.glb' else str(p).replace('/','::'),str(p),p.suffix.lstrip('.') or 'text',state,purpose,dest])
 paths.append(pathlib.Path('ASSET_REGISTRY.csv'))
 names=['Start','Concept','WorldArt','CharacterArt','CreatureArt','Audio','Code','UnlockArt']; groups={g:[p for p in paths if group(p)==g] for g in names}
 entries=[];num=1
 for g in names[1:]:
  parts=[];current=[]
  for p in groups[g]:
   candidate=current+[p]
   if len(zipbytes(candidate))>28_500_000 and current: parts.append(current);current=[p]
   else:current=candidate
  if current:parts.append(current)
  for i,part in enumerate(parts):
   name=f'DRENOVAR_Forest_Rescue_{num:02d}_{g}'+(f'_{i+1}' if len(parts)>1 else '')+'.zip';blob=zipbytes(part)
   if len(blob)>MAX:raise RuntimeError('Archive exceeds limit: '+name)
   (a.output/name).write_bytes(blob)
   entries.append({'filename':name,'bytes':len(blob),'sha256':digest(blob),'depends_on':['DRENOVAR_Forest_Rescue_00_Start.zip'],'group':g,'files':[PREFIX+str(p) for p in sorted(part)]});num+=1
 for entry in entries:
  needed={'Code':['Concept'],'WorldArt':['Concept'],'CharacterArt':['Concept'],'CreatureArt':['Concept'],'Audio':['Concept'],'UnlockArt':['Concept']}.get(entry['group'],[])
  entry['depends_on'] += [e['filename'] for e in entries if e['group'] in needed]
 files=[]
 for p in sorted(paths):
  b=(ROOT/p).read_bytes();files.append({'path':PREFIX+str(p),'bytes':len(b),'sha256':digest(b)})
 manifest={'schemaVersion':1,'title':'DRENOVAR — Лес потерянных','contentVersion':'1.1.0','limit_bytes':MAX,'split_resources':[],
 'self_integrity':{'reason':'A ZIP cannot contain its own SHA-256. All exact ZIP sizes and hashes, including Start, are in external DELIVERY_INDEX.json. Manifest itself is covered by Start SHA-256.','external_index':'DELIVERY_INDEX.json'},
 'packages':[{'filename':'DRENOVAR_Forest_Rescue_00_Start.zip','bytes':None,'sha256':None,'integrity':'DELIVERY_INDEX.json','depends_on':[],'group':'Start'},*entries],
 'files':files,'external_project_dependencies':['authorized full DRENOVAR checkout at integration revision','480 baseline graphical files enumerated by original repository REQUIRED_WEB_ASSETS_480.json']}
 writejson(ROOT/'PACKAGE_MANIFEST.json',manifest)
 startpaths=groups['Start']+[pathlib.Path('PACKAGE_MANIFEST.json')];blob=zipbytes(startpaths)
 name='DRENOVAR_Forest_Rescue_00_Start.zip';(a.output/name).write_bytes(blob)
 entries.insert(0,{'filename':name,'bytes':len(blob),'sha256':digest(blob),'depends_on':[],'group':'Start','files':[PREFIX+str(p) for p in sorted(startpaths)]})
 writejson(a.output/'DELIVERY_INDEX.json',{'schemaVersion':1,'contentVersion':'1.1.0','limit_bytes':MAX,'packages':entries})
 for p in a.output.iterdir():
  if p.is_file() and p.stat().st_size>MAX:raise RuntimeError('Delivery file exceeds limit: '+str(p))
 print(json.dumps([{k:v for k,v in e.items() if k!='files'} for e in entries],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
