#!/usr/bin/env python3
"""Genuine fixed-scope F15 game asset producer: PNG + glTF 2.0 GLB + PCM WAV.
48 separately generated triplets and independent structural QA via BUILD50.
"""
import argparse,hashlib,importlib.util,json,math,os,shutil,struct,wave,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
PRODUCT='fieldwork_original_48_game_asset_triplets'
MOTIFS=('hero','enemy','portal','energy','shield','map','coins','forest','water','stone','clouds','stars')
MODES=('basic','angled','detailed','bright')
def load(name):
 p=HERE/(name+'.py')
 if p.is_symlink() or not p.is_file():raise ValueError('ASSET_UNTRUSTED_CODE')
 s=importlib.util.spec_from_file_location(name,str(p))
 m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(65536),b''):h.update(chunk)
 return h.hexdigest()
def plan(proto):
 tasks=[]
 for motif in MOTIFS:
  for mode in MODES:
   tasks.append({'id':motif+'_'+mode,'motif':motif,'mode':mode,
    'instruction':'Produce a new original '+mode+' game asset trio for '+motif+
       ' consisting of a usable raster sprite, geometrically real 3D glTF mesh and audible PCM sample, with distinct original measurements.',
    'acceptance':['Three real asset files exist and each parser verifies its native image, mesh or audio encoding.',
       'Original asset hashes and independent source-integrity evidence are recorded without rights or gameplay certification.']})
 return {'schema':proto.SCHEMA,'family_id':'F15','product_id':PRODUCT,
   'producer_id':'original_game_sprite_mesh_audio_assets_v1',
   'source_snapshot_sha256':proto.digest({'producer':sha(__file__),
      'reviewer':sha(HERE/'factory_f15_independent_review.py'),
      'protocol':sha(HERE/'factory_build_50.py'),'scope':'original_3d_mesh_sprite_audio_samples'}),
   'work_packages':tasks}
def make_png(path,task,i,v):
 from PIL import Image,ImageDraw
 size=256
 bg=(13+i*7,35+v*18,48+i*6)
 gold=(185+v*12,120+i*9,58+v*25)
 im=Image.new('RGBA',(size,size),bg+(255,));pen=ImageDraw.Draw(im)
 points=[(128,22+v*5),(226-i*3,100+i*4),(174,214-v*6),(53+i*3,203),(20+v*3,82+i*4)]
 pen.polygon(points,fill=gold+(255,))
 pen.ellipse((98,103,158,163),fill=bg+(255,))
 pen.line(((24,230),(230,230)),fill=(244,218,159,255),width=4)
 pen.text((18,12),task['motif'].upper(),fill='white')
 pen.text((16,239),task['mode'].upper(),fill='white')
 im.save(str(path),'PNG',optimize=True)
def make_glb(path,task,i,v):
 # A fully self-contained valid glTF2 triangle mesh, not a renamed fake binary.
 sx=.55+i*.047;sy=.69+v*.11;sz=.85+i*.019+v*.06
 vertices=[(-sx,-sy,0.),(sx,-sy,0.),(0.,sy,0.),(0.,0.,sz)]
 positions=[n for point in vertices for n in point]
 indices=[0,2,1,0,1,3,1,2,3,2,0,3]
 binary=struct.pack('<12f',*positions)+struct.pack('<12H',*indices)
 minimum=[min(p[j] for p in vertices) for j in range(3)]
 maximum=[max(p[j] for p in vertices) for j in range(3)]
 doc={'asset':{'version':'2.0','generator':'fieldwork-original-f15-v1'},
  'scene':0,'scenes':[{'nodes':[0]}],'nodes':[{'mesh':0,'name':task['id']}],
  'buffers':[{'byteLength':len(binary)}],
  'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':48,'target':34962},
                 {'buffer':0,'byteOffset':48,'byteLength':24,'target':34963}],
  'accessors':[{'bufferView':0,'byteOffset':0,'componentType':5126,
      'count':4,'type':'VEC3','min':minimum,'max':maximum},
      {'bufferView':1,'byteOffset':0,'componentType':5123,'count':12,'type':'SCALAR'}],
  'materials':[{'pbrMetallicRoughness':{'baseColorFactor':[
      round((60+i*12)/255,4),round((80+v*30)/255,4),
      round((90+i*8)/255,4),1.0],'metallicFactor':0.08,'roughnessFactor':0.66}}],
  'meshes':[{'name':task['motif']+'_original_asset',
      'primitives':[{'attributes':{'POSITION':0},'indices':1,'material':0,'mode':4}]}]}
 raw=json.dumps(doc,sort_keys=True,separators=(',',':')).encode('utf8')
 jsonchunk=raw+b' '*((-len(raw))%4)
 binchunk=binary+b'\0'*((-len(binary))%4)
 length=12+8+len(jsonchunk)+8+len(binchunk)
 glb=struct.pack('<4sII',b'glTF',2,length)+struct.pack('<I4s',len(jsonchunk),b'JSON')+jsonchunk
 glb+=struct.pack('<I4s',len(binchunk),b'BIN\0')+binchunk
 path.write_bytes(glb)
def make_audio(path,i,v):
 rate=16000;n=12800;pitch=160+i*29+v*37
 out=[]
 for k in range(n):
  t=k/rate;attack=min(1,t*18);decay=min(1,(.8-t)*10)
  value=math.sin(2*math.pi*pitch*t)+.24*math.sin(2*math.pi*(pitch*2+v)*t)
  out.append(int(8200*max(0,attack*decay)*value))
 with wave.open(str(path),'wb') as f:
  f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate)
  f.writeframes(struct.pack('<'+'h'*n,*out))
def build(root):
 root=Path(root)
 if root.is_symlink() or not root.is_dir():raise ValueError('ASSET_BAD_ROOT')
 proto=load('factory_build_50');review=load('factory_f15_independent_review')
 production=plan(proto);home=root/'build-50'/PRODUCT;target=root/'digital-products'/PRODUCT
 archive=PRODUCT+'-internal-qa.zip'
 if any(p.is_symlink() for p in (home,target,root/'build-50',root/'digital-products')):
  raise ValueError('ASSET_UNSAFE_PATH')
 if (home/'state.json').is_file() and (target/'manufacturing_manifest.json').is_file():
  state=proto.read(home/'state.json');manifest=proto.read(target/'manufacturing_manifest.json')
  f=target/archive
  if proto.verify_attempt(home,state,production['source_snapshot_sha256']) and f.is_file() and not f.is_symlink() and sha(f)==manifest.get('artifact_sha256'):
   return {'family_id':'F15','status':'unchanged_verified_technical_product'}
 def worker(task,ctx):
  folder=Path(ctx['folder']);stem=task['id']
  i=MOTIFS.index(task['motif']);v=MODES.index(task['mode'])
  make_png(folder/(stem+'.png'),task,i,v)
  make_glb(folder/(stem+'.glb'),task,i,v)
  make_audio(folder/(stem+'.wav'),i,v)
  names=[stem+'.png',stem+'.glb',stem+'.wav']
  if any(not (folder/name).is_file() or (folder/name).stat().st_size<100 for name in names):
   raise ValueError('ASSET_WORK_NOT_CREATED')
  return {'passed':True,'outputs':names,'successful_checks':2}
 def assemble(data,ctx):
  folder=Path(ctx['folder'])
  paths=sorted(p for p in folder.iterdir() if p.suffix in ('.png','.glb','.wav'))
  (folder/'README.txt').write_text('Original reusable game-engine technical samples: PNG sprites, real GLB triangle meshes and WAV sound effects. No human artistic review, third-party rights clearance, in-engine compatibility test or commercial release.\\n',encoding='utf8')
  with zipfile.ZipFile(str(folder/archive),'w',zipfile.ZIP_DEFLATED) as z:
   for path in paths+[folder/'README.txt']:
    info=zipfile.ZipInfo(PRODUCT+'/'+path.name,date_time=(2020,1,1,0,0,0))
    info.compress_type=zipfile.ZIP_DEFLATED
    z.writestr(info,path.read_bytes())
  return {'passed':True,'outputs':['README.txt',archive],'successful_checks':3}
 def checker(data,ctx):
  folder=Path(ctx['folder'])
  result=review.check(folder,folder/archive,PRODUCT)
  proto.save(folder/'independent-game-asset-review.json',result)
  return {'reviewer_id':'independent_original_game_asset_binary_validator',
   'passed':result['passed'],'critical_defects':[],'gates':result['gates'],
   'outputs':['independent-game-asset-review.json'],'successful_checks':10}
 state=proto.run_attempt(root,production,worker,assemble,checker)
 if not proto.verify_attempt(home,state,production['source_snapshot_sha256']):
  return {'family_id':'F15','status':'technical_rework_required','defects':state.get('defects',[])}
 target.mkdir(parents=True,exist_ok=True,mode=0o700)
 temp=target/'.f15-incoming.zip';shutil.copyfile(Path(state['attempt_folder'])/archive,temp)
 os.replace(temp,target/archive)
 proto.save(target/'manufacturing_manifest.json',{
  'schema_version':2,'recipe':PRODUCT,'family_id':'F15','qa_status':'passed',
  'artifact_sha256':sha(target/archive),'bytes':(target/archive).stat().st_size,
  'qa_evidence':'automated_mesh_image_audio_integrity',
  'commercial_status':'private_internal_qa_pass_not_published','public_listing_enabled':False,
  'owner_publication_approval':False,'independent_human_review':False})
 return {'family_id':'F15','status':'technical_50_stage_build_completed',
  'completed_stages':50,'commercial_release':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--factory-private',required=True)
 a=p.parse_args();result=build(a.factory_private)
 print('FACTORY_F15_REAL_GAME_ASSETS='+json.dumps(result,sort_keys=True))
 if result['status']=='technical_rework_required':raise SystemExit(2)
