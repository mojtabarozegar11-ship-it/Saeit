#!/usr/bin/env python3
"""Publish precisely seven original illustrations after MojPlayWin senior advisors, without any other site writes."""
from pathlib import Path
import hashlib,json,os,re,stat,sys,tempfile
ROOT=Path('/home/zomorod2/mojplaywin.com')
PAGE=ROOT/'design-preview-20261017/mpw-ten-editorials-20261018/pages/about.html'
HTACCESS=ROOT/'.htaccess'
PARENT=PAGE.parent
MARKER='MPW_SEVEN_IMAGES_AFTER_ADVISORS_20261019'
SECTION='mpw-seven-gallery-20261019'
BEFORE='<!-- MPW_INTERNATIONAL_TEAM_ADDON_20261018 -->'
ADVISOR='<!-- MPW_SENIOR_ADVISORY_ADDON_20261018 -->'
FOUNDER='MPW_FOUNDER_SPOTLIGHT_ADDON_20261019'
NAMES=('Sophia','Isabella','Olivia','Camila','Valentina','Emma','Charlotte','Amelia','Luca','Noah')
FILES=[
('mpw-team-gallery-seven-01-20261019.webp','287e58749c39a6152997137a91167e9c6651a38006f21841fc2ae49a4fd32b24',227418),
('mpw-team-gallery-seven-02-20261019.webp','522fa3c5a6de725b1fe0660fac4263c5c4f7a37a4bc5c24169a183ab521d11d1',267264),
('mpw-team-gallery-seven-03-20261019.webp','5fc80738105abd63ad43e01d5fe599d49c7de8a4ab9c776f9acb34734555bc57',246978),
('mpw-team-gallery-seven-04-20261019.webp','e2ddcc071906d54188e506cb183749db09787f1ffba0df5921ef8e3a55f10e27',216460),
('mpw-team-gallery-seven-05-20261019.webp','5cebb8279a8fe033ee121fb444f823274255fc7cb6d1597d63e0b1faae6dfcc5',241834),
('mpw-team-gallery-seven-06-20261019.webp','7d288e2e1d0f4e352245b4d42f018243fb1d869e49d28d6534c8fbb2e9cdff58',226494),
('mpw-team-gallery-seven-07-20261019.webp','48c09f3b7d7588a80b9fed379ea00a008faf8af2f0999b2bafa23f9ad2dd3937',249136)]

def sha(d):return hashlib.sha256(d).hexdigest()
def fail(t):raise RuntimeError(t)
def paths(run):
 if not re.fullmatch(r'[0-9]{9,20}',run):fail('Unsafe run ID')
 h=ROOT.parent
 return (h/f'.mpw-seven-stage-{run}.html',
         [h/f'.mpw-seven-stage-{run}-{i:02}.webp' for i in range(1,8)],
         h/f'.mpw-seven-backup-{run}.html', h/f'.mpw-seven-manifest-{run}.json')

def atomic(path,data,mode):
 if path.is_symlink():fail('Unsafe output symlink')
 fd,temp=tempfile.mkstemp(prefix='.mpw-gallery7-',dir=path.parent)
 try:
  os.fchmod(fd,mode)
  with os.fdopen(fd,'wb') as stream:
   stream.write(data);stream.flush();os.fsync(stream.fileno())
  os.replace(temp,path)
 finally:
  if os.path.exists(temp):os.unlink(temp)

def guard():
 if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.resolve()!=ROOT:fail('Incorrect docroot')
 if not PAGE.is_file() or PAGE.is_symlink() or not HTACCESS.is_file() or HTACCESS.is_symlink():fail('Unsafe About path')
 if any(x.is_symlink() for x in [PARENT,PARENT.parent,PARENT.parent.parent]):fail('Unexpected parent symlink')
 routing=HTACCESS.read_text('utf-8',errors='replace')
 cond='RewriteCond %{REQUEST_URI} ^/about/$'
 rule='RewriteRule ^.*$ /design-preview-20261017/mpw-ten-editorials-20261018/pages/about.html [END,QSD]'
 if not all(x in routing for x in ('MPW_ILLUSTRATED_TEN_PER_PAGE_20261018',cond,rule)) or routing.index(cond)>routing.index(rule):fail('About priority rewrite changed')
 old=PAGE.read_bytes()
 if len(old)<60000 or len(old)>1600000:fail('About page unexpectedly sized')
 doc=old.decode('utf-8')
 for m in ('MPW_ABOUT_RESEARCH_80_20_V1','Original by Default','mpw-meet-team-20261018','mpw-senior-advisory-20261018','mpw-international-team-20261018',FOUNDER,ADVISOR,BEFORE):
  if m not in doc:fail('Existing About section missing: '+m)
 if SECTION in doc or MARKER in doc:fail('Seven gallery already installed; refusing duplicate')
 for tag,count in [('class="mpw-team-card"',10),('class="mpw-advisory-card"',10),('class="mpw-intl-card"',10)]:
  if doc.count(tag)!=count:fail('Existing profiles changed '+tag)
 if len(re.findall(r'<h1\b',doc,re.I))!=1:fail('About H1 count changed')
 if not doc.index(FOUNDER)<doc.index('mpw-meet-team-20261018')<doc.index(ADVISOR)<doc.index(BEFORE):fail('Founder and advisor order invalid')
 if doc.count(BEFORE)!=1 or doc.count(ADVISOR)!=1:fail('Nonunique section anchors')
 if not len(re.findall(r'<main\b',doc,re.I))==len(re.findall(r'</main\s*>',doc,re.I))==1:fail('Ambiguous main')
 for fn,digest,size in FILES:
  f=PARENT/fn
  if f.exists() or f.is_symlink():fail('Image destination unexpectedly occupied: '+fn)
 return old

def check_section(data):
 if not 5000<len(data)<20000:fail('Gallery source size invalid')
 text=data.decode('utf-8')
 if text.count('<section id="'+SECTION+'"')!=1 or text.count('class="mpw-seven-item"')!=7:fail('Wrong gallery count')
 if 'digitally generated portraits' not in text:fail('Missing illustration disclosure')
 if re.search(r'<script\b|<iframe\b|\{%|\{\{',text,re.I):fail('Executable content forbidden')
 for fn,_,_ in FILES:
  if text.count(fn)!=2:fail('Gallery source/image mismatch')
 return text

def compose(old,section):
 if SECTION in old or MARKER in old:fail('Already installed')
 idx=old.index(BEFORE)
 # The new gallery follows the fully closed advisors section, before International Management.
 between=old[old.index(ADVISOR):idx]
 if between.count('<section id="mpw-senior-advisory-20261018"')!=1 or not between.rstrip().endswith('</section>'):
  fail('Advisor section did not close before insertion point')
 addition='\n<!-- '+MARKER+' -->\n'+section+'\n'
 after=old[:idx]+addition+old[idx:]
 if after.replace(addition,'',1)!=old:fail('Patch not perfectly reversible')
 if any(after.count(x)!=old.count(x) for x in ('class="mpw-team-card"','class="mpw-advisory-card"','class="mpw-intl-card"',FOUNDER)):
  fail('Existing content modified')
 if not after.index(ADVISOR)<after.index(MARKER)<after.index(BEFORE):fail('Wrong layout position')
 if len(after.encode())>1700000:fail('About file too large')
 return after.encode('utf-8')

def install(run,html_sha):
 html_path,image_stages,backup,manifest=paths(run)
 if not re.fullmatch(r'[a-f0-9]{64}',html_sha):fail('Unsafe source SHA')
 if not html_path.is_file() or html_path.is_symlink():fail('Missing private gallery source')
 payload=html_path.read_bytes()
 if sha(payload)!=html_sha:fail('Gallery HTML SHA changed')
 section=check_section(payload)
 assets=[]
 for source,(filename,digest,size) in zip(image_stages,FILES):
  if not source.is_file() or source.is_symlink():fail('Missing image stage '+filename)
  data=source.read_bytes()
  if len(data)!=size or sha(data)!=digest or data[:4]!=b'RIFF' or data[8:12]!=b'WEBP':fail('Wrong image digest/format '+filename)
  assets.append((PARENT/filename,data,digest))
 before=guard();after=compose(before.decode('utf8'),section)
 if backup.exists() or backup.is_symlink() or manifest.exists() or manifest.is_symlink():fail('Backup already present')
 with backup.open('xb') as f:
  os.chmod(backup,0o600);f.write(before);f.flush();os.fsync(f.fileno())
 record={'run':run,'before':sha(before),'after':sha(after),'assets':{p.name:d for p,_,d in assets}}
 with manifest.open('x',encoding='utf8') as f:
  os.chmod(manifest,0o600);json.dump(record,f);f.flush();os.fsync(f.fileno())
 if sha(PAGE.read_bytes())!=record['before']:fail('Concurrent About modification')
 try:
  for target,content,digest in assets:
   atomic(target,content,0o644)
   if sha(target.read_bytes())!=digest:fail('Asset mismatch after write')
  atomic(PAGE,after,stat.S_IMODE(PAGE.stat().st_mode))
  if sha(PAGE.read_bytes())!=record['after']:fail('Page mismatch after write')
 except BaseException:
  if PAGE.is_file() and sha(PAGE.read_bytes())==record['after']:
   atomic(PAGE,before,stat.S_IMODE(PAGE.stat().st_mode))
  for target,_,digest in assets:
   if target.is_file() and not target.is_symlink() and sha(target.read_bytes())==digest:target.unlink()
  raise
 html_path.unlink()
 for stage in image_stages:stage.unlink()
 print(json.dumps({'result':'MPW_SEVEN_GALLERY_PUBLISHED','pictures':7,'position':'after_senior_advisors','previous_profiles':30,'founder_preserved':True,'page_before':record['before'],'page_after':record['after'],'passenger_restarted':False,'other_pages_modified':False,'rollback_prepared':True}))

def rollback(run):
 _,_,backup,manifest=paths(run)
 if not backup.is_file() or backup.is_symlink() or not manifest.is_file() or manifest.is_symlink():fail('Rollback evidence missing')
 record=json.loads(manifest.read_text('utf8'))
 prior=backup.read_bytes()
 if sha(prior)!=record['before']:fail('Backup mismatch')
 current=sha(PAGE.read_bytes())
 if current==record['after']:
  atomic(PAGE,prior,stat.S_IMODE(PAGE.stat().st_mode))
 elif current!=record['before']:fail('Newer edit present; refuse rollback')
 for name,digest in record['assets'].items():
  target=PARENT/name
  if target.is_file() and not target.is_symlink() and sha(target.read_bytes())==digest:
   target.unlink()
  elif target.exists() or target.is_symlink():fail('Asset changed; refuse deletion: '+name)
 print(json.dumps({'result':'MPW_SEVEN_GALLERY_ROLLBACK_COMPLETE','page_sha':sha(PAGE.read_bytes())}))

def status(run):
 _,_,backup,manifest=paths(run)
 record=json.loads(manifest.read_text('utf8')) if manifest.is_file() else {}
 now=sha(PAGE.read_bytes()) if PAGE.is_file() and not PAGE.is_symlink() else ''
 valid=bool(record) and now==record.get('after') and all((PARENT/n).is_file() and sha((PARENT/n).read_bytes())==d for n,d in record.get('assets',{}).items())
 print(json.dumps({'result':'MPW_SEVEN_GALLERY_READONLY_STATUS','installed':valid,'image_count':len(record.get('assets',{})),'backup_exists':backup.is_file(),'page_sha':now}))

if __name__=='__main__':
 if len(sys.argv)<3:fail('Usage: install|rollback|status RUN_ID [HTML_SHA]')
 mode,run=sys.argv[1:3]
 if mode=='install' and len(sys.argv)==4:install(run,sys.argv[3])
 elif mode=='rollback' and len(sys.argv)==3:rollback(run)
 elif mode=='status' and len(sys.argv)==3:status(run)
 else:fail('Unknown mode')