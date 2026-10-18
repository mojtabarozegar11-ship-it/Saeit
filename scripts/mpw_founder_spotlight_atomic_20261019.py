#!/usr/bin/env python3
"""Add one founder portrait above the existing team sections on MojPlayWin /about/.
Fail closed, reversible, no other-page or child-site mutation.
"""
from pathlib import Path
import hashlib,json,os,re,stat,sys,tempfile
ROOT=Path('/home/zomorod2/mojplaywin.com')
PAGE=ROOT/'design-preview-20261017/mpw-ten-editorials-20261018/pages/about.html'
IMG=PAGE.parent/'mpw-founder-portrait-20261019.webp'
HTACCESS=ROOT/'.htaccess'
MARKER='MPW_FOUNDER_SPOTLIGHT_ADDON_20261019'
SECTION_ID='mpw-founder-spotlight-20261019'
INSERT_BEFORE='<style id="mpw-team-gallery-style-20261018">'
IMG_SHA='df59ff545bc45af59141488a40132c8df384b5ceb6b134e1c6000645f2ddfc3a'
IMG_LENGTH=125006
IMG_PUBLIC='/design-preview-20261017/mpw-ten-editorials-20261018/pages/mpw-founder-portrait-20261019.webp'
PRESERVE=(
 'MPW_ABOUT_RESEARCH_80_20_V1','Original by Default','Mojtaba Roozegar',
 'MPW_TEAM_ADDON_V1','mpw-meet-team-20261018',
 'MPW_SENIOR_ADVISORY_ADDON_20261018','mpw-senior-advisory-20261018',
 'MPW_INTERNATIONAL_TEAM_ADDON_20261018','mpw-international-team-20261018',
 'mpw-team-gallery-hq-20261018.webp','mpw-senior-advisory-20261018.webp',
 'mpw-international-team-20261018.webp')

def digest(d):return hashlib.sha256(d).hexdigest()
def die(t):raise RuntimeError(t)
def paths(runid):
 if not re.fullmatch(r'[0-9]{9,20}',runid):die('Unsafe run identifier')
 base=ROOT.parent
 return (base/f'.mpw-founder-section-{runid}.html',base/f'.mpw-founder-image-{runid}.webp',base/f'.mpw-founder-backup-{runid}.html',base/f'.mpw-founder-manifest-{runid}.json')
def atomic(path,data,mode):
 if path.is_symlink():die('Symlink write prohibited')
 fd,temp=tempfile.mkstemp(prefix='.mpw-founder-',dir=path.parent)
 try:
  os.fchmod(fd,mode)
  with os.fdopen(fd,'wb') as f:
   f.write(data);f.flush();os.fsync(f.fileno())
  os.replace(temp,path)
 finally:
  if os.path.exists(temp):os.unlink(temp)
def validated_page():
 if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.resolve()!=ROOT:die('Unexpected site root')
 if not PAGE.is_file() or PAGE.is_symlink() or not HTACCESS.is_file() or HTACCESS.is_symlink():die('Unsafe page or route')
 if any(p.is_symlink() for p in (PAGE.parent,PAGE.parent.parent,PAGE.parent.parent.parent)):
  die('Unsafe parent directory symlink')
 rules=HTACCESS.read_text('utf-8',errors='replace')
 cond='RewriteCond %{REQUEST_URI} ^/about/$'
 rule='RewriteRule ^.*$ /design-preview-20261017/mpw-ten-editorials-20261018/pages/about.html [END,QSD]'
 legacy='RewriteRule ^about/$ /design-preview-20261017/complete-about-20261018.html [END,QSD]'
 if not all(x in rules for x in ('MPW_ILLUSTRATED_TEN_PER_PAGE_20261018',cond,rule,legacy)):
  die('About route unknown')
 if not rules.index(cond)<rules.index(rule)<rules.index(legacy):die('About route precedence changed')
 if IMG.exists() or IMG.is_symlink():die('Founder image path already exists: refuse duplicates')
 original=PAGE.read_bytes()
 if not 50000<len(original)<1550000:die('Unexpected About size')
 s=original.decode('utf-8')
 if MARKER in s or SECTION_ID in s or IMG_PUBLIC in s:die('Founder spotlight/image already present')
 if any(mark not in s for mark in PRESERVE):die('Existing company/team/advisor/international content changed')
 if s.count(INSERT_BEFORE)!=1:die('Original team start is not unique')
 if s.count('class="mpw-team-card"')!=10 or s.count('class="mpw-advisory-card"')!=10 or s.count('class="mpw-intl-card"')!=10:
  die('Expected three existing ten-profile groups')
 if len(re.findall(r'<h1\b',s,re.I))!=1:die('About H1 unexpected')
 if len(re.findall(r'<main\b',s,re.I))!=1 or len(re.findall(r'</main\s*>',s,re.I))!=1:die('About semantics changed')
 if s.index(INSERT_BEFORE)>s.index('<section id="mpw-meet-team-20261018"'):die('Team anchor unexpectedly precedes its styles')
 return original

def validate_snippet(raw):
 s=raw.decode('utf-8')
 if not 3300<=len(raw)<=8000:die('Founder snippet has wrong size')
 if s.count('<section id="'+SECTION_ID+'"')!=1 or s.count('id="mpw-founder-spotlight-style-20261019"')!=1:
  die('Founder section/style missing or duplicate')
 if s.count('src="'+IMG_PUBLIC+'"')!=1 or s.count('<img ' )!=1:die('Exactly one new founder photo required')
 if not all(k in s for k in ('Mojtaba Roozegar','Founder · Strategic Vision','Long-Term Growth')):
  die('Founding identity/overview missing')
 if any(k in s for k in ('Age: 45','Tehran','Professor','Doctor','Iran – Tehran')):
  die('Unverified ages, locations or degrees forbidden')
 if re.search(r'<script\b|<iframe\b|\{%|\{\{',s,re.I):die('Executable content forbidden')
 return s

def compose(existing,section):
 if MARKER in existing or SECTION_ID in existing or IMG_PUBLIC in existing:die('Duplicate section refused')
 if existing.count(INSERT_BEFORE)!=1:die('Cannot find unique insertion point')
 addon='\n<!-- '+MARKER+' -->\n'+section+'\n'
 output=existing.replace(INSERT_BEFORE,addon+INSERT_BEFORE,1)
 if output.replace(addon,'',1)!=existing:die('Insertion not reversible')
 if not output.index(SECTION_ID)<output.index('<section id="mpw-meet-team-20261018"'):die('Founder is not above first team')
 for key in PRESERVE:
  if key not in output:die('Existing content lost')
 for classn in ('mpw-team-card','mpw-advisory-card','mpw-intl-card'):
  if output.count('class="'+classn+'"')!=10:die('Existing profile count changed')
 if len(output.encode('utf-8'))>1550000:die('About file too large')
 return output

def install(runid,section_sha,image_sha):
 stage_html,stage_img,backup,manifest=paths(runid)
 if not re.fullmatch(r'[0-9a-f]{64}',section_sha) or image_sha!=IMG_SHA:die('Unrecognized input hashes')
 if not stage_html.is_file() or stage_html.is_symlink() or not stage_img.is_file() or stage_img.is_symlink():die('Staged source absent')
 section_bytes=stage_html.read_bytes();image=stage_img.read_bytes()
 if digest(section_bytes)!=section_sha:die('Snippet integrity failure')
 if digest(image)!=IMG_SHA or len(image)!=IMG_LENGTH or image[:4]!=b'RIFF' or image[8:12]!=b'WEBP':die('Portrait bytes do not match vetted asset')
 section=validate_snippet(section_bytes);before=validated_page();after=compose(before.decode('utf-8'),section).encode('utf-8')
 if backup.exists() or backup.is_symlink() or manifest.exists() or manifest.is_symlink():die('Existing backup/manifest; refusing overwrite')
 with backup.open('xb') as f:
  os.chmod(backup,0o600);f.write(before);f.flush();os.fsync(f.fileno())
 record={'before':digest(before),'after':digest(after),'image':IMG_SHA,'section':section_sha,'run':runid}
 with manifest.open('x',encoding='utf-8') as f:
  os.chmod(manifest,0o600);json.dump(record,f);f.flush();os.fsync(f.fileno())
 if digest(PAGE.read_bytes())!=record['before']:die('Concurrent About edit')
 try:
  atomic(IMG,image,0o644)
  if digest(IMG.read_bytes())!=IMG_SHA:die('Photo did not persist')
  atomic(PAGE,after,stat.S_IMODE(PAGE.stat().st_mode))
  if digest(PAGE.read_bytes())!=record['after']:die('Updated page did not persist')
 except BaseException:
  if PAGE.is_file() and not PAGE.is_symlink() and digest(PAGE.read_bytes())==record['after']:
   atomic(PAGE,before,stat.S_IMODE(PAGE.stat().st_mode))
  if IMG.is_file() and not IMG.is_symlink() and digest(IMG.read_bytes())==record['image']:IMG.unlink()
  raise
 stage_html.unlink();stage_img.unlink()
 print(json.dumps({'result':'MPW_FOUNDER_ABOVE_ALL_TEAMS_PUBLISHED','page_before_sha':record['before'],'page_after_sha':record['after'],'portrait_sha256':IMG_SHA,'new_founder_images':1,'team_groups_preserved':3,'total_existing_profiles_preserved':30,'passenger_restarted':False,'other_pages_edited':False,'rollback_saved':True}))
def rollback(runid):
 _,_,backup,manifest=paths(runid)
 if not backup.is_file() or backup.is_symlink() or not manifest.is_file() or manifest.is_symlink():die('Missing backup evidence')
 record=json.loads(manifest.read_text('utf-8'));before=backup.read_bytes()
 if digest(before)!=record['before']:die('Backup corrupted')
 if not PAGE.is_file() or PAGE.is_symlink():die('About disappeared')
 now=digest(PAGE.read_bytes())
 if now==record['after']:atomic(PAGE,before,stat.S_IMODE(PAGE.stat().st_mode))
 elif now!=record['before']:die('Newer edit exists: refuse rollback')
 if IMG.is_file() and not IMG.is_symlink() and digest(IMG.read_bytes())==record['image']:IMG.unlink()
 elif IMG.exists() or IMG.is_symlink():die('Portrait modified externally: refuse deletion')
 print(json.dumps({'result':'MPW_FOUNDER_ROLLED_BACK','page_sha':digest(PAGE.read_bytes())}))
def status(runid):
 _,_,backup,manifest=paths(runid)
 record=json.loads(manifest.read_text('utf-8')) if manifest.is_file() else {}
 now=digest(PAGE.read_bytes()) if PAGE.is_file() and not PAGE.is_symlink() else ''
 img=digest(IMG.read_bytes()) if IMG.is_file() and not IMG.is_symlink() else ''
 print(json.dumps({'result':'MPW_FOUNDER_RELEASE_STATUS','installed':bool(record) and now==record.get('after') and img==record.get('image'),'backup':backup.is_file(),'page_sha':now,'image_sha':img}))
if __name__=='__main__':
 if len(sys.argv)<3:die('Expected install|rollback|status runid [snippet_sha image_sha]')
 mode,runid=sys.argv[1:3]
 if mode=='install' and len(sys.argv)==5:install(runid,sys.argv[3],sys.argv[4])
 elif mode=='rollback' and len(sys.argv)==3:rollback(runid)
 elif mode=='status' and len(sys.argv)==3:status(runid)
 else:die('Invalid command')