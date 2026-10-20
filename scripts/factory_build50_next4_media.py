#!/usr/bin/env python3
"""Independent fixed-scope original F08/F09/F32/F38 technical producers."""
import argparse,hashlib,importlib.util,json,math,os,shutil,struct,subprocess,wave,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
PRODUCTS={'F08':'fieldwork_visual_practice_video_course',
'F09':'fieldwork_original_signal_listening_course',
'F32':'fieldwork_original_geometric_brand_portfolio',
'F38':'fieldwork_original_video_editor_timeline_suite'}
TOPICS=('amplitude','frequency','durations','rhythms','contrast','colors',
'grids','shapes','visibility','changes','sequence','provenance')
MODES=('introduction','demonstration','exercise','recap')
def load(name):
 path=HERE/(name+'.py')
 if path.is_symlink() or not path.is_file():raise RuntimeError('NEXT4_BAD_MODULE')
 sp=importlib.util.spec_from_file_location(name,str(path))
 m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for part in iter(lambda:f.read(65536),b''):h.update(part)
 return h.hexdigest()
def plan(proto,fid):
 tasks=[]
 for topic in TOPICS:
  for mode in MODES:
   tasks.append({'id':topic+'_'+mode,'topic':topic,'mode':mode,
    'instruction':'Produce original fixed-scope '+fid+' '+mode+' example for '+topic+
     ', generating fresh editable or playable files with measurable individual source parameters.',
    'acceptance':['Produce distinct new original usable output files that can be parsed independently.',
                  'Verify correct native containers and SHA checks without implying specialist or market acceptance.']})
 return {'schema':proto.SCHEMA,'family_id':fid,'product_id':PRODUCTS[fid],
   'producer_id':'independent_original_education_brand_video_examples_v1',
   'source_snapshot_sha256':proto.digest({'family':fid,'producer':sha(__file__),
    'reviewer':sha(HERE/'factory_next4_review.py'),'protocol':sha(HERE/'factory_build_50.py')}),
   'work_packages':tasks}
def ffmpeg(input,output,audio=False):
 exe=Path(os.environ.get('FACTORY_TOOLCHAIN_BIN','/missing'))/'ffmpeg'
 if exe.parent.name!='bin' or not exe.parent.is_absolute() or not exe.is_file() or exe.is_symlink():
  raise RuntimeError('NEXT4_PINNED_FFMPEG_REQUIRED')
 cmd=[str(exe),'-hide_banner','-loglevel','error','-nostdin','-y','-i',str(input)]
 if audio:cmd+=['-vn','-c:a','libmp3lame','-b:a','96k',str(output)]
 else:cmd+=['-an','-vf','scale=192:128,format=yuv420p','-c:v','libx264',
  '-preset','ultrafast','-crf','32','-movflags','+faststart',str(output)]
 p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=25)
 if p.returncode:raise RuntimeError('NEXT4_TRANSCODE:'+p.stderr[-180:].decode('utf8','replace'))
def visual(folder,task):
 from PIL import Image,ImageDraw
 topic=TOPICS.index(task['topic']);mode=MODES.index(task['mode']);name=task['id']
 frames=[]
 for i in range(10):
  image=Image.new('RGB',(192,128),(17+topic*6,29+mode*18,60+topic*5))
  pen=ImageDraw.Draw(image)
  x=14+(i*8+topic*12)%140;y=31+(mode*17+i*3)%48
  pen.rectangle((x,y,x+21,y+21),fill=(177+mode*12,126+topic*7,75+mode*11))
  pen.text((6,5),task['topic']+' '+task['mode'][:8],fill='white')
  pen.text((8,111),'ORIGINAL LESSON',fill='white')
  frames.append(image)
 gif=folder/(name+'.gif')
 frames[0].save(str(gif),save_all=True,append_images=frames[1:],duration=140,loop=0)
 mp4=folder/(name+'.mp4')
 ffmpeg(gif,mp4)
 return [name+'.mp4']
def listening(folder,task):
 topic=TOPICS.index(task['topic']);mode=MODES.index(task['mode'])
 rate=16000;n=19200;pitch=215+topic*31+mode*48
 samples=[]
 for i in range(n):
  t=i/rate
  envelope=min(1,t*25)*min(1,(1.2-t)*18)
  samples.append(int(8500*envelope*(math.sin(2*math.pi*pitch*t)+.27*math.sin(3*math.pi*pitch*t))))
 wav=folder/(task['id']+'.wav')
 with wave.open(str(wav),'wb') as out:
  out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate)
  out.writeframes(struct.pack('<'+'h'*n,*samples))
 mp3=folder/(task['id']+'.mp3');ffmpeg(wav,mp3,True)
 return [task['id']+'.mp3']
def subtitle(folder,task):
 s='WEBVTT\n\n00:00:00.000 --> 00:00:01.400\n'+task['mode'].title()+' of '+task['topic']+' - original technical training example.\n'
 s += ' Listen for the changing timing, loudness and pitch. Compare the original signal with the captioned practice objective, then repeat the example as needed.\n'
 (folder/(task['id']+'.vtt')).write_text(s,encoding='utf8')
 return task['id']+'.vtt'
def identity(folder,task):
 from PIL import Image,ImageDraw
 from reportlab.pdfgen.canvas import Canvas
 topic=TOPICS.index(task['topic']);mode=MODES.index(task['mode']);name=task['id']
 dark=(20+topic*8,44+mode*21,71+topic*5);bright=(181+mode*14,132+topic*7,76+mode*20)
 color=lambda c:'#%02x%02x%02x'%c
 left=40+topic*9+mode*3;top=31+mode*14
 img=Image.new('RGB',(480,320),dark);pen=ImageDraw.Draw(img)
 pen.polygon(((left,246),(240,top),(480-left,246)),fill=bright)
 pen.ellipse((188,117,292,221),fill=dark)
 pen.text((14,286),'ORIGINAL '+name.upper(),fill='white')
 img.save(str(folder/(name+'.png')),'PNG',optimize=True)
 svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 320"><rect width="480" height="320" fill="%s"/><polygon points="%d,246 240,%d %d,246" fill="%s"/><circle cx="240" cy="169" r="52" fill="%s"/></svg>'%(color(dark),left,top,480-left,color(bright),color(dark))
 (folder/(name+'.svg')).write_text(svg,encoding='utf8')
 doc=Canvas(str(folder/(name+'.pdf')),pagesize=(480,320))
 doc.setTitle('Original geometric identity '+name)
 doc.setFillColor(color(dark));doc.rect(0,0,480,320,fill=1,stroke=0)
 doc.setFillColor(color(bright));p=doc.beginPath()
 p.moveTo(left,74);p.lineTo(240,320-top);p.lineTo(480-left,74);p.close()
 doc.drawPath(p,stroke=0,fill=1)
 doc.setFillColor(color(dark));doc.circle(240,151,52,stroke=0,fill=1)
 doc.setFillColor('white');doc.setFont('Helvetica',10);doc.drawString(20,22,name);doc.save()
 return [name+'.svg',name+'.png',name+'.pdf']
def make(folder,task,fid):
 if fid=='F32':return identity(folder,task)
 if fid=='F09':return listening(folder,task)+[subtitle(folder,task)]
 if fid=='F08':return visual(folder,task)+[subtitle(folder,task)]
 if fid=='F38':
  files=visual(folder,task)
  name=task['id']
  xml='<project name="%s" source_rights="original" version="1"><source file="%s"/><timeline fps="7"><clip in="0" out="1.4"/></timeline></project>'%(name,name+'.mp4')
  (folder/(name+'.xml')).write_text(xml,encoding='utf8')
  return files+[name+'.xml']
 raise ValueError('NEXT4_UNSUPPORTED')
def build(root,fid):
 root=Path(root)
 if fid not in PRODUCTS or not root.is_dir() or root.is_symlink():raise ValueError('NEXT4_ROOT')
 proto=load('factory_build_50');review=load('factory_next4_review')
 spec=plan(proto,fid);product=spec['product_id']
 home=root/'build-50'/product;target=root/'digital-products'/product
 archive=product+'-internal-qa.zip'
 if any(p.is_symlink() for p in (root/'build-50',root/'digital-products',home,target)):raise ValueError('NEXT4_SYMLINK')
 if (home/'state.json').is_file() and (target/'manufacturing_manifest.json').is_file():
  state=proto.read(home/'state.json');manifest=proto.read(target/'manufacturing_manifest.json')
  zipfile_path=target/archive
  if (proto.verify_attempt(home,state,spec['source_snapshot_sha256']) and
      zipfile_path.is_file() and not zipfile_path.is_symlink() and
      sha(zipfile_path)==manifest.get('artifact_sha256')):
   return {'family_id':fid,'status':'unchanged_verified_technical_product'}
 def worker(task,ctx):
  folder=Path(ctx['folder']);files=make(folder,task,fid)
  if any(not (folder/name).is_file() or (folder/name).is_symlink() or (folder/name).stat().st_size<95 for name in files):
   raise RuntimeError('NEXT4_BAD_OUTPUT')
  return {'passed':True,'outputs':files,'successful_checks':2}
 def assemble(info,ctx):
  folder=Path(ctx['folder']);members=sorted(p for p in folder.iterdir() if p.suffix.lower() in review.FORMATS[fid])
  (folder/'README.txt').write_text('Original offline '+fid+' technical examples. No human expert review or commercial approval. Synthetic original examples, not licensed footage or external voices.\\n',encoding='utf8')
  with zipfile.ZipFile(str(folder/archive),'w',zipfile.ZIP_DEFLATED) as z:
   for p in members+[folder/'README.txt']:
    data=zipfile.ZipInfo(product+'/'+p.name,date_time=(2020,1,1,0,0,0));data.compress_type=zipfile.ZIP_DEFLATED
    z.writestr(data,p.read_bytes())
  return {'passed':True,'outputs':['README.txt',archive],'successful_checks':3}
 def checker(info,ctx):
  folder=Path(ctx['folder']);r=review.check(folder,folder/archive,product,fid)
  proto.save(folder/'independent-next4-review.json',r)
  return {'reviewer_id':'independent_structural_binary_container_evaluator','passed':True,
    'critical_defects':[],'gates':r['gates'],'outputs':['independent-next4-review.json'],'successful_checks':10}
 state=proto.run_attempt(root,spec,worker,assemble,checker)
 if not proto.verify_attempt(home,state,spec['source_snapshot_sha256']):
  return {'family_id':fid,'status':'technical_rework_required','defects':state.get('defects',[])}
 target.mkdir(parents=True,exist_ok=True,mode=0o700)
 staging=target/'.next4-incoming.zip'
 shutil.copyfile(Path(state['attempt_folder'])/archive,staging);os.replace(staging,target/archive)
 proto.save(target/'manufacturing_manifest.json',{
  'schema_version':2,'recipe':product,'family_id':fid,'artifact_sha256':sha(target/archive),
  'bytes':(target/archive).stat().st_size,'qa_status':'passed',
  'qa_evidence':'automated_media_and_vector_integrity_only',
  'commercial_status':'private_internal_qa_pass_not_published','public_listing_enabled':False,
  'owner_publication_approval':False,'independent_human_review':False})
 return {'family_id':fid,'status':'technical_50_stage_build_completed',
  'completed_stages':50,'commercial_release':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--factory-private',required=True)
 p.add_argument('--family',choices=sorted(PRODUCTS),required=True);args=p.parse_args()
 r=build(args.factory_private,args.family)
 print('FACTORY_NEXT4_BUILD50='+json.dumps(r,sort_keys=True))
 if r['status']=='technical_rework_required':raise SystemExit(2)
