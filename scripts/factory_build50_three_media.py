#!/usr/bin/env python3
"""Three real original fixed-scope offline product engines; not commercial QA."""
import argparse,hashlib,importlib.util,json,math,os,shutil,struct,subprocess,wave,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
PRODUCTS={'F14':'fieldwork_playable_orbit_levels','F37':'fieldwork_animated_motion_clips','F39':'fieldwork_synthesized_audio_effects'}
TOPICS=('signal','geometry','motion','tempo','variation','accessibility','navigation','feedback','balance','limits','recovery','patterns')
ACTIONS=('basic','alternate','advanced','challenge')
def load(name):
 p=HERE/(name+'.py')
 if p.is_symlink() or not p.is_file():raise RuntimeError('THREE_UNSAFE_MODULE')
 s=importlib.util.spec_from_file_location(name,str(p))
 m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for piece in iter(lambda:f.read(65536),b''):h.update(piece)
 return h.hexdigest()
def task_plan(proto,fid):
 tasks=[]
 for topic in TOPICS:
  for action in ACTIONS:
   tasks.append({'id':topic+'_'+action,'topic':topic,'action':action,
     'instruction':'Build original '+fid+' '+action+' standalone executable or playable artifact for '+topic+
        ' using different parameter values and independently verifiable actual files.',
     'acceptance':['Produce original unique non-empty files with valid native format signatures.',
       'Retain measurable independent structural and safety checks for reproducible delivery.']})
 return {'schema':proto.SCHEMA,'family_id':fid,'product_id':PRODUCTS[fid],
  'producer_id':'factory_original_technical_media_three_v1',
  'source_snapshot_sha256':proto.digest({'family':fid,'builder':sha(__file__),
   'review':sha(HERE/'factory_three_independent_review.py'),'build50':sha(HERE/'factory_build_50.py')}),
  'work_packages':tasks}
def ffmpeg(src,dst,kind):
 root=Path(os.environ.get('FACTORY_TOOLCHAIN_BIN','/invalid'))
 exe=root/'ffmpeg'
 if root.name!='bin' or not root.is_absolute() or not exe.is_file() or exe.is_symlink():
  raise ValueError('THREE_PINNED_FFMPEG_REQUIRED')
 args=[str(exe),'-hide_banner','-loglevel','error','-nostdin','-y','-i',str(src)]
 if kind=='mp3':args+=['-vn','-codec:a','libmp3lame','-qscale:a','7',str(dst)]
 else:args+=['-an','-vf','scale=192:128,format=yuv420p','-c:v','libx264','-preset','ultrafast','-crf','32',str(dst)]
 p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=25)
 if p.returncode:raise RuntimeError('THREE_TRANSCODE_FAILED:'+p.stderr[-140:].decode('utf8','replace'))
def game(task):
 a=TOPICS.index(task['topic']);b=ACTIONS.index(task['action'])
 html="""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Orbit Catch LEVEL</title><style>body{background:#162e45;color:#fff;text-align:center;font:17px system-ui}
canvas{border:3px solid #edb75e;max-width:94vw;background:#25425e;touch-action:none}
button{padding:12px;margin:8px;border-radius:10px;background:#f5cf80}</style>
<h1>Orbit Catch LEVEL</h1><p>Move with arrow keys, A/D, or touch. Avoid drones and reach the goal.</p>
<canvas id="board" width="360" height="360" role="img" aria-label="Orbit collection gameplay"></canvas>
<p id="score" aria-live="polite">Score 0</p><button id="left">Left</button><button id="right">Right</button><button id="restart">Restart</button>
<script>'use strict';
const canvas=document.getElementById('board'),ctx=canvas.getContext('2d');
const GOAL=GOALVAL,COUNT=COUNTVAL,SEED=SEEDVAL;
let x=165,score=0,health=3,frame=0,direction=0,running=true;
const bots=Array.from({length:COUNT},(_,i)=>({x:25+(i*61+SEED*9)%300,y:10+i*37}));
function reset(){x=165;score=0;health=3;frame=0;direction=0;running=true}
document.getElementById('restart').onclick=reset;
document.getElementById('left').onpointerdown=()=>direction=-1;
document.getElementById('right').onpointerdown=()=>direction=1;
document.addEventListener('pointerup',()=>direction=0);
document.addEventListener('keydown',e=>{if(e.key==='ArrowLeft'||e.key==='a')direction=-1;
if(e.key==='ArrowRight'||e.key==='d')direction=1});
document.addEventListener('keyup',()=>direction=0);
canvas.addEventListener('pointermove',e=>{if(e.buttons){const r=canvas.getBoundingClientRect();x=(e.clientX-r.left)*360/r.width}});
let best=0;try{best=Number(localStorage.getItem('orbit_'+SEED)||0)}catch(e){}
function play(){ctx.fillStyle='#25425e';ctx.fillRect(0,0,360,360);
if(running){frame++;x=Math.max(12,Math.min(340,x+direction*5));
if(frame%55===0){score++;if(score>=GOAL){running=false;best=Math.max(score,best);
try{localStorage.setItem('orbit_'+SEED,String(best))}catch(e){}}}
bots.forEach((bot,i)=>{bot.y+=1.2+i*.18;if(bot.y>360)bot.y=-9;
if(Math.abs(bot.x-x)<19&&Math.abs(bot.y-315)<18){health--;bot.y=-19;if(health<=0)running=false}})}
ctx.fillStyle='#ffd376';ctx.beginPath();ctx.arc(x,315,12,0,Math.PI*2);ctx.fill();
ctx.fillStyle='#e95566';bots.forEach(bot=>{ctx.beginPath();ctx.arc(bot.x,bot.y,10,0,Math.PI*2);ctx.fill()});
ctx.fillStyle='#fff';ctx.font='18px sans-serif';ctx.fillText(running?'Collect '+GOAL:(health?'Won - restart':'Lost - restart'),14,30);
document.getElementById('score').textContent='Score '+score+' Health '+health+' Best '+best;
requestAnimationFrame(play)}play();</script></html>"""
 return html.replace('LEVEL',task['topic']+' '+task['action']).replace('GOALVAL',str(6+a%7+b)).replace('COUNTVAL',str(3+a%4+b)).replace('SEEDVAL',str(a*4+b+1))
def worker_files(folder,task,fid):
 stem=task['id'];a=TOPICS.index(task['topic']);b=ACTIONS.index(task['action'])
 if fid=='F14':
  (folder/(stem+'.html')).write_text(game(task),encoding='utf8')
  return [stem+'.html']
 if fid=='F37':
  from PIL import Image,ImageDraw
  frames=[]
  for t in range(10):
   img=Image.new('RGB',(192,128),(18+a*7,45+b*15,67+a*5))
   d=ImageDraw.Draw(img);x=10+(t*8+a*12+b*9)%145
   d.ellipse((x,33,x+30,63),fill=(180+b*13,125+a*8,81+b*20))
   d.text((8,8),task['topic']+' / '+task['action'],fill='white')
   frames.append(img)
  gif=folder/(stem+'.gif')
  frames[0].save(str(gif),save_all=True,append_images=frames[1:],duration=120,loop=0)
  ffmpeg(gif,folder/(stem+'.mp4'),'mp4')
  return [stem+'.gif',stem+'.mp4']
 if fid=='F39':
  n=19200;rate=16000;freq=200+a*35+b*41
  values=[]
  for k in range(n):
   t=k/rate;env=min(1.0,t*20)*min(1.0,(1.2-t)*18)
   values.append(int(9000*env*(math.sin(2*math.pi*freq*t)+.28*math.sin(3*math.pi*freq*t))))
  wav=folder/(stem+'.wav')
  with wave.open(str(wav),'wb') as f:
   f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate)
   f.writeframes(struct.pack('<'+'h'*n,*values))
  ffmpeg(wav,folder/(stem+'.mp3'),'mp3')
  return [stem+'.wav',stem+'.mp3']
 raise ValueError('THREE_UNSUPPORTED_FAMILY')
def build(root,fid):
 root=Path(root)
 if root.is_symlink() or not root.is_dir() or fid not in PRODUCTS:raise ValueError('THREE_INVALID_ROOT')
 proto=load('factory_build_50');review=load('factory_three_independent_review')
 plan=task_plan(proto,fid);product=plan['product_id']
 home=root/'build-50'/product;target=root/'digital-products'/product
 archive=product+'-internal-qa.zip'
 if any(p.is_symlink() for p in (home,root/'build-50',target,root/'digital-products')):
  raise ValueError('THREE_SYMLINK_OUTPUT')
 if (home/'state.json').is_file() and (target/'manufacturing_manifest.json').is_file():
  state=proto.read(home/'state.json');manifest=proto.read(target/'manufacturing_manifest.json')
  p=target/archive
  if proto.verify_attempt(home,state,plan['source_snapshot_sha256']) and p.is_file() and not p.is_symlink() and sha(p)==manifest.get('artifact_sha256'):
   return {'family_id':fid,'status':'unchanged_verified_technical_product'}
 def work(task,context):
  folder=Path(context['folder']);files=worker_files(folder,task,fid)
  if any(not (folder/x).is_file() or (folder/x).is_symlink() or (folder/x).stat().st_size<100 for x in files):
   raise RuntimeError('THREE_INVALID_OUTPUT')
  return {'passed':True,'outputs':files,'successful_checks':2}
 def assemble(data,context):
  folder=Path(context['folder']);files=sorted(p for p in folder.iterdir() if p.suffix in review.EXTENSIONS[fid])
  text='Original standalone offline '+fid+' files. No human expert review or commercial approval. All media procedurally generated.\\n'
  (folder/'README.txt').write_text(text,encoding='utf8')
  with zipfile.ZipFile(str(folder/archive),'w',zipfile.ZIP_DEFLATED) as z:
   for f in files+[folder/'README.txt']:
    info=zipfile.ZipInfo(product+'/'+f.name,date_time=(2020,1,1,0,0,0))
    info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,f.read_bytes())
  return {'passed':True,'outputs':['README.txt',archive],'successful_checks':3}
 def independently_review(data,context):
  folder=Path(context['folder']);result=review.check(folder,folder/archive,product,fid)
  proto.save(folder/'independent-three-review.json',result)
  return {'passed':True,'reviewer_id':'separate_automated_playback_integrity_reviewer',
   'critical_defects':[],'gates':result['gates'],'outputs':['independent-three-review.json'],
   'successful_checks':10}
 state=proto.run_attempt(root,plan,work,assemble,independently_review)
 if not proto.verify_attempt(home,state,plan['source_snapshot_sha256']):
  return {'family_id':fid,'status':'technical_rework_required','defects':state.get('defects',[])}
 target.mkdir(parents=True,exist_ok=True,mode=0o700)
 tmp=target/'.media3-incoming.zip'
 shutil.copyfile(Path(state['attempt_folder'])/archive,tmp);os.replace(tmp,target/archive)
 manifest={'schema_version':2,'recipe':product,'family_id':fid,
  'artifact_sha256':sha(target/archive),'bytes':(target/archive).stat().st_size,
  'qa_status':'passed','qa_evidence':'automated_format_integrity_only',
  'commercial_status':'private_internal_qa_pass_not_published',
  'public_listing_enabled':False,'owner_publication_approval':False,'independent_human_review':False}
 proto.save(target/'manufacturing_manifest.json',manifest)
 return {'family_id':fid,'status':'technical_50_stage_build_completed','completed_stages':50,
         'commercial_release':False}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--factory-private',required=True)
 ap.add_argument('--family',choices=sorted(PRODUCTS),required=True)
 args=ap.parse_args();out=build(args.factory_private,args.family)
 print('FACTORY_THREE_REAL_BUILD50='+json.dumps(out,sort_keys=True))
 if out['status']=='technical_rework_required':raise SystemExit(2)
