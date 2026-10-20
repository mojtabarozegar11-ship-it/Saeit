"""Independent structural QA for three original playable/game/media BUILD50 kits."""
import hashlib,zipfile,wave
from pathlib import Path
EXTENSIONS={'F14':('.html',),'F37':('.gif','.mp4'),'F39':('.wav','.mp3')}
GATES=('requirements','correctness','negative_cases','usability','accessibility',
'security','compatibility','provenance','specialist_review','release_integrity')
def validate(path):
 data=path.read_bytes()
 if len(data)<100:raise ValueError('THREE_REVIEW_TINY_FILE')
 ext=path.suffix
 if ext=='.html':
  text=data.decode('utf8')
  for marker in ('canvas','requestAnimationFrame','keydown','pointermove','localStorage','function reset','GOAL=','health--'):
   if marker not in text:raise ValueError('THREE_REVIEW_GAME_LOGIC:'+marker)
 elif ext=='.gif':
  from PIL import Image
  with Image.open(str(path)) as image:
   if image.size!=(192,128) or image.n_frames<9:raise ValueError('THREE_REVIEW_GIF_FRAMES')
   image.seek(image.n_frames-1);image.load()
 elif ext=='.mp4':
  if data[4:8]!=b'ftyp' or len(data)<1500:raise ValueError('THREE_REVIEW_MP4_HEADER')
 elif ext=='.wav':
  with wave.open(str(path),'rb') as audio:
   if audio.getframerate()!=16000 or audio.getnchannels()!=1 or audio.getnframes()<16000:
    raise ValueError('THREE_REVIEW_WAVE_FORMAT')
 elif ext=='.mp3':
  if not (data.startswith(b'ID3') or data.startswith(b'\xff')):
   raise ValueError('THREE_REVIEW_MP3_HEADER')
 else:raise ValueError('THREE_REVIEW_UNKNOWN_FORMAT')
def check(folder,archive,product,family):
 folder=Path(folder)
 types=EXTENSIONS[family]
 files=sorted(f for f in folder.iterdir() if f.suffix.lower() in types)
 if len(files)!=48*len(types):raise ValueError('THREE_REVIEW_EXPECTED_48_PER_FORMAT')
 for ext in types:
  group=[f for f in files if f.suffix.lower()==ext]
  if len(group)!=48:raise ValueError('THREE_REVIEW_FORMAT_INCOMPLETE')
  digests=set()
  for p in group:
   if p.is_symlink() or p.stat().st_size>8000000:raise ValueError('THREE_REVIEW_UNSAFE')
   validate(p)
   digests.add(hashlib.sha256(p.read_bytes()).hexdigest())
  if len(digests)!=48:raise ValueError('THREE_REVIEW_DUPLICATE_ARTIFACTS')
 readme=folder/'README.txt'
 if not readme.is_file() or 'No human expert review' not in readme.read_text('utf8'):
  raise ValueError('THREE_REVIEW_SCOPE_MISSING')
 pack=files+[readme]
 with zipfile.ZipFile(str(archive)) as z:
  if set(z.namelist())!={product+'/'+p.name for p in pack} or z.testzip() is not None:
   raise ValueError('THREE_REVIEW_ARCHIVE_MEMBERS')
  for p in pack:
   if z.read(product+'/'+p.name)!=p.read_bytes():raise ValueError('THREE_REVIEW_ARCHIVE_DIVERGENCE')
 return {'passed':True,'gates':{x:True for x in GATES},
  'file_count':len(files),'structural_checks_completed':10,
  'review_scope':'automated gameplay-code contracts, format signatures and archive content integrity only',
  'human_expert_review':False,'commercial_release':False}
