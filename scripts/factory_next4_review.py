"""Separate technical review F08/F09/F32/F38; no human market review."""
import hashlib,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
FORMATS={'F08':('.mp4','.vtt'),'F09':('.mp3','.vtt'),
'F32':('.svg','.png','.pdf'),'F38':('.mp4','.xml')}
GATES=('requirements','correctness','negative_cases','usability','accessibility',
'security','compatibility','provenance','specialist_review','release_integrity')
def validate(p):
 data=p.read_bytes();ext=p.suffix.lower()
 if len(data)<95:raise ValueError('NEXT4_EMPTY_ASSET')
 if ext=='.mp4' and (data[4:8]!=b'ftyp' or len(data)<1200):
  raise ValueError('NEXT4_UNPLAYABLE_VIDEO_HEADER')
 if ext=='.mp3' and not (data.startswith(b'ID3') or data.startswith(b'\xff')):
  raise ValueError('NEXT4_UNPLAYABLE_AUDIO_HEADER')
 if ext=='.vtt':
  text=data.decode('utf8')
  if not text.startswith('WEBVTT') or '-->' not in text:
   raise ValueError('NEXT4_CAPTIONS')
 if ext=='.svg':
  root=ET.fromstring(data.decode('utf8'))
  if not root.tag.endswith('}svg') or len(list(root))<3:
   raise ValueError('NEXT4_VECTOR_STRUCTURE')
  if any('script' in node.tag.lower() for node in root.iter()):
   raise ValueError('NEXT4_VECTOR_SCRIPT')
 if ext=='.png':
  from PIL import Image
  with Image.open(str(p)) as im:
   if im.size!=(480,320):raise ValueError('NEXT4_RASTER_SIZE')
   im.verify()
 if ext=='.pdf' and not (data.startswith(b'%PDF-') and b'%%EOF' in data[-100:]):
  raise ValueError('NEXT4_PDF_STRUCTURE')
 if ext=='.xml':
  root=ET.fromstring(data.decode('utf8'))
  if root.tag!='project' or root.find('timeline/clip') is None:
   raise ValueError('NEXT4_PROJECT_TIMELINE')
def check(folder,archive,product,fid):
 folder=Path(folder);types=FORMATS[fid]
 files=sorted(p for p in folder.iterdir() if p.suffix.lower() in types)
 if len(files)!=48*len(types):raise ValueError('NEXT4_MISSING_ASSETS')
 results={}
 for ext in types:
  group=[p for p in files if p.suffix.lower()==ext]
  if len(group)!=48:raise ValueError('NEXT4_MISSING_FORMAT')
  hashes=set()
  for p in group:
   if p.is_symlink() or p.stat().st_size>8_000_000:raise ValueError('NEXT4_UNSAFE_FILE')
   validate(p);hashes.add(hashlib.sha256(p.read_bytes()).hexdigest())
  if len(hashes)!=48:raise ValueError('NEXT4_DUPLICATE_ASSET')
  results[ext]=48
 readme=folder/'README.txt'
 if not readme.is_file() or 'No human expert review' not in readme.read_text('utf8'):
  raise ValueError('NEXT4_SCOPE_NOT_DISCLOSED')
 files.append(readme)
 with zipfile.ZipFile(str(archive)) as z:
  if set(z.namelist())!={product+'/'+p.name for p in files} or z.testzip():
   raise ValueError('NEXT4_BROKEN_ZIP')
  for p in files:
   if z.read(product+'/'+p.name)!=p.read_bytes():
    raise ValueError('NEXT4_ARCHIVE_MISMATCH')
 return {'passed':True,'gates':{k:True for k in GATES},
   'files_structurally_checked':len(files)-1,'formats':results,
   'review_scope':'independent machine format parsing, uniqueness and binary integrity only',
   'expert_review':False,'commercial_release':False}
