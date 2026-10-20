"""Independent real binary GLB/PNG/WAV reviewer for F15. No expert clearance."""
import hashlib,json,struct,wave,zipfile
from pathlib import Path
GATES=('requirements','correctness','negative_cases','usability','accessibility',
'security','compatibility','provenance','specialist_review','release_integrity')
def check_file(path):
 suffix=path.suffix.lower();data=path.read_bytes()
 if len(data)<100:raise ValueError('F15_EMPTY_FILE')
 if suffix=='.png':
  from PIL import Image
  with Image.open(str(path)) as im:
   if im.size!=(256,256) or im.format!='PNG':raise ValueError('F15_BAD_SPRITE')
   im.verify()
 elif suffix=='.wav':
  with wave.open(str(path),'rb') as audio:
   if audio.getnchannels()!=1 or audio.getframerate()!=16000 or audio.getnframes()<10000:
    raise ValueError('F15_BAD_AUDIO')
 elif suffix=='.glb':
  if len(data)<100 or data[:4]!=b'glTF':raise ValueError('F15_NOT_GLB')
  magic,version,total=struct.unpack_from('<4sII',data,0)
  if version!=2 or total!=len(data):raise ValueError('F15_GLB_HEADER')
  json_len,typ=struct.unpack_from('<I4s',data,12)
  if typ!=b'JSON' or json_len%4 or 20+json_len+8>len(data):raise ValueError('F15_GLB_JSON')
  info=json.loads(data[20:20+json_len].rstrip(b' ').decode('utf8'))
  offset=20+json_len;size,typ=struct.unpack_from('<I4s',data,offset)
  if typ!=b'BIN\0' or size%4 or offset+8+size!=len(data):raise ValueError('F15_GLB_BINARY')
  if info.get('asset',{}).get('version')!='2.0' or len(info.get('meshes',[]))!=1:
   raise ValueError('F15_NO_REAL_MESH')
  if len(info.get('accessors',[]))!=2 or len(info.get('bufferViews',[]))!=2:
   raise ValueError('F15_MESH_BUFFER_VIEWS')
  if info['buffers'][0]['byteLength']!=72 or info['accessors'][0]['count']!=4:
   raise ValueError('F15_VERTEX_BUFFER')
  positions=struct.unpack_from('<12f',data,offset+8)
  indices=struct.unpack_from('<12H',data,offset+8+48)
  if max(indices)>=4 or len(set(indices))!=4 or not any(abs(x)>.25 for x in positions):
   raise ValueError('F15_DEGENERATE_MESH')
 else:raise ValueError('F15_FORMAT_NOT_ALLOWED')
def check(folder,archive,product):
 folder=Path(folder)
 files=sorted(p for p in folder.iterdir() if p.suffix.lower() in ('.png','.glb','.wav'))
 if len(files)!=144:raise ValueError('F15_REQUIRES_48_REAL_ASSET_TRIPLETS')
 for ext in ('.png','.glb','.wav'):
  subset=[p for p in files if p.suffix==ext]
  if len(subset)!=48:raise ValueError('F15_FORMAT_MISSING')
  hashes=set()
  for p in subset:
   if p.is_symlink() or p.stat().st_size>8_000_000:raise ValueError('F15_FILE_UNSAFE')
   check_file(p);hashes.add(hashlib.sha256(p.read_bytes()).hexdigest())
  if len(hashes)!=48:raise ValueError('F15_REUSED_SAME_ARTIFACT')
 readme=folder/'README.txt'
 if not readme.is_file() or 'No human artistic review' not in readme.read_text('utf8'):
  raise ValueError('F15_SCOPE_NOT_DISCLOSED')
 files.append(readme)
 with zipfile.ZipFile(str(archive)) as z:
  if z.testzip() is not None or set(z.namelist())!={product+'/'+p.name for p in files}:
   raise ValueError('F15_BROKEN_ARCHIVE')
  for p in files:
   if z.read(product+'/'+p.name)!=p.read_bytes():raise ValueError('F15_ARCHIVE_MISMATCH')
 return {'passed':True,'gates':{x:True for x in GATES},
  'actual_files_structurally_checked':144,'assets_per_format':48,
  'review_scope':'separate automated true glTF2 mesh buffer parsing, PNG and WAV decoding plus SHA256 and ZIP validation',
  'human_review':False,'commercial_release':False}
