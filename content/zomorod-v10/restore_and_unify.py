#!/usr/bin/env python3
"""Additively restore original archived content into current Zomorod Melal main site
and attach one shared inner-page design stylesheet. Independent child sites excluded.

This module only computes outputs unless explicitly called with --output-dir.
The Github Action owns backups, isolated candidate staging, atomic commits, rollback.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path

VERSION = 'zm-v10-restored-content-and-unified-internal-pages-20261018'
BANNED_TOP = {'mohammad','ghanadi','amozeshgah','tala','business','education','site-heritage','static','admin','cgi-bin','private','__pycache__','app','wp-admin'}
OLD_LOGO='/static/site/company/company-logo-transparent.png'
NEW_LOGO='/static/site/zomorod-v7/company-logo.webp'
STYLE='<link rel="stylesheet" href="/static/site/zomorod-v10/inner-v10.css?v=20261018" data-zm-v10="shared-theme">'
SOURCES={
 'knowledge/index.html': ('site-heritage/home-before-redesign/index.html','restored-earlier-specialist-content','مقالات، راهنماها و تصاویر آموزشی پیشین', 'نسخه پیش از بازطراحی'),
 'about/index.html': ('site-heritage/home-before-v6-20261018/index.html','restored-earlier-corporate-content','معرفی و حوزه‌های فعالیت در نسخه پیشین', 'معرفی قدیمی شرکت'),
}
ADD_LINKS={
 'agriculture/index.html': ('مجموعه کامل راهنماهای بازیابی‌شده کشاورزی، صنعت و پژوهش','/knowledge/#restored-earlier-specialist-content'),
 'research/index.html': ('راهنماهای پیشین پژوهش و تولید','/knowledge/#restored-earlier-specialist-content'),
 'blog/index.html': ('مطالب و تصاویر آموزشی آرشیوی بازگردانده‌شده','/knowledge/#restored-earlier-specialist-content'),
 'industry/index.html': ('راهنماهای قدیمی صنعت و تولید','/knowledge/#restored-earlier-specialist-content'),
}
class VisibleMain(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.depth=0;self.words=[];self.in_script=0
 def handle_starttag(self,tag,attrs):
  if tag=='main':self.depth+=1
  if tag in ('script','style'):self.in_script+=1
 def handle_endtag(self,tag):
  if tag=='main':self.depth=max(0,self.depth-1)
  if tag in ('script','style'):self.in_script=max(0,self.in_script-1)
 def handle_data(self,data):
  if self.depth and not self.in_script:
   t=' '.join(data.split())
   if t:self.words.append(t)
def visible_main(s):
 p=VisibleMain();p.feed(s);return ' '.join(p.words)

def find_targets(root:Path):
 result=[]
 for dp,dirs,files in os.walk(root,followlinks=False):
  parent=Path(dp);rel=parent.relative_to(root)
  dirs[:]=[d for d in dirs if d not in BANNED_TOP and not d.startswith('.') and not d.startswith('__') and not (parent/d).is_symlink()]
  if len(rel.parts)>5:dirs[:]=[];continue
  for name in files:
   candidate=parent/name
   parts=candidate.relative_to(root).parts
   if name!='index.html' and parts!=('zm-specialist-library-2026.html',):continue
   if len(parts)==1 and parts[0]=='index.html':continue # orbital homepage protected
   if any(part.startswith('.') or part.startswith('__') for part in parts):continue
   if candidate.is_symlink() or not candidate.is_file():continue
   s=candidate.read_text(encoding='utf-8')
   if 'zm-unified-v7-20261018' not in s:raise ValueError('Internal page has unrecognized theme: '+str(candidate))
   if VERSION in s:raise ValueError('Already modified, refuse repeat: '+str(candidate))
   if s.lower().count('</head>')!=1 or s.lower().count('</body>')!=1 or s.lower().count('</html>')!=1 or s.lower().count('</main>')!=1:raise ValueError('Unexpected page DOM: '+str(candidate))
   result.append((str(candidate.relative_to(root)),s))
 return sorted(result)

def archived_fragment(root:Path,relative:str):
 p=root/relative
 if not p.is_file() or p.is_symlink():raise ValueError('Missing historical source: '+relative)
 original=p.read_text(encoding='utf-8')
 matches=list(re.finditer(r'<main\b[^>]*>(.*?)</main\s*>',original,re.I|re.S))
 if len(matches)!=1:raise ValueError('Historical source has unexpected main sections: '+relative)
 fragment=matches[0].group(1)
 # Historic pages may contain obsolete inline mouse events. Remove only executable
 # attributes from the copied HTML; keep every visible word, image and link.
 before_visible=visible_main('<main>'+fragment+'</main>')
 old_images=len(re.findall(r'<img\b',fragment,re.I))
 old_links=len(re.findall(r'<a\b',fragment,re.I))
 def clean_tag(m):
  return re.sub(r"\s+on[a-z][\w-]*\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", '',m.group(0),flags=re.I)
 fragment=re.sub(r'<[^>]+>',clean_tag,fragment,flags=re.S)
 fragment=re.sub(r'\bhref\s*=\s*([\"\'])javascript:[^\"\']*\1','href="#"',fragment,flags=re.I)
 if any(re.search(pat,fragment,re.I) for pat in (r'<script\b',r'<style\b',r'<iframe\b',r'<form\b',r'<object\b',r'<embed\b',r'\bon\w+\s*=',r'javascript\s*:')):
  raise ValueError('Archived content still contains unsafe executable markup: '+relative)
 text=visible_main('<main>'+fragment+'</main>')
 if text!=before_visible or len(re.findall(r'<img\b',fragment,re.I))!=old_images or len(re.findall(r'<a\b',fragment,re.I))!=old_links:
  raise ValueError('Sanitization altered archived text, images or links: '+relative)
 if len(text)<1500:raise ValueError('Archived content unexpectedly empty: '+relative)
 img=len(re.findall(r'<img\b',fragment,re.I))
 link=len(re.findall(r'<a\b',fragment,re.I))
 return fragment,text,img,link

def patch(s:str,rel:str,fragments:dict):
 original=s
 assert s.count('</head>')==1
 s=s.replace('</head>',f'<!-- {VERSION} -->'+STYLE+'</head>',1)
 # Standardize only the *outdated brand image*; preserve all other source images and alt text.
 replaced=s.count(OLD_LOGO)
 if replaced:s=s.replace(OLD_LOGO,NEW_LOGO)
 if rel in SOURCES:
  source,anchor,title,note=SOURCES[rel]
  raw,plain,img,links=fragments[rel]
  section=(f'<!-- {VERSION} historical-source={source} -->'
           f'<section class="zm-v10-restored" id="{anchor}" aria-label="{title}">'
           f'<div class="zm-v10-restored-heading"><span>مجموعه تخصصی زمرد ملل</span><h2>{title}</h2>'
           f'<p>مطالعه مقالات، راهنماها و معرفی حوزه‌های تخصصی شرکت برای انتخاب مسیر پژوهش، تولید و همکاری.</p></div>'
           f'<div class="zm-v10-history-content">{raw}</div></section>')
  assert source in section
  s=s.replace('</main>',section+'</main>',1)
 if rel in ADD_LINKS:
  title,url=ADD_LINKS[rel]
  link=(f'<aside class="zm-v10-archive-entry"><a href="{url}">'
        f'<span aria-hidden="true">✦</span>{title} ←</a></aside>')
  s=s.replace('</main>',link+'</main>',1)
 assert original.count('<script')==s.count('<script')
 assert original.count('<main')==s.count('<main')
 assert original.count('</main>')==s.count('</main>')
 assert original.count('<footer')==s.count('<footer')
 assert original.count('<header')==s.count('<header')
 assert original.count('<img')+sum(x[2] for k,x in fragments.items() if k==rel)==s.count('<img')
 oldtext=visible_main(original)
 newtext=visible_main(s)
 if not newtext.startswith(oldtext):
  raise ValueError('Original visible editorial main content not preserved in order: '+rel)
 assert VERSION in s and STYLE in s
 assert len(s.encode('utf-8'))>=len(original.encode('utf-8'))
 return s,{'relative':rel,'before_bytes':len(original.encode()),'after_bytes':len(s.encode()),'old_main_chars':len(oldtext),'new_main_chars':len(newtext),'logo_replaced':replaced,'restored_source':SOURCES[rel][0] if rel in SOURCES else None}

def build(root:Path,dest:Path):
 roots=root.resolve(strict=True); dest=dest.resolve(strict=False)
 if dest.exists():raise ValueError('Staging directory exists, refusing overwrite: '+str(dest))
 pages=find_targets(roots)
 if not 42<=len(pages)<=75:raise ValueError('Unexpected main-page count '+str(len(pages)))
 names={rel for rel,_ in pages}
 must={'company/index.html','about/index.html','knowledge/index.html','agriculture/index.html','industry/index.html','research/index.html','blog/index.html','services/index.html','economy/index.html','market/index.html','weather/index.html','studio/index.html','zm-specialist-library-2026.html'}
 if not must.issubset(names):raise ValueError('Missing required pages: '+str(must-names))
 fragments={rel:archived_fragment(roots,source) for rel,(source,*_) in SOURCES.items()}
 target=[];info=[]
 for rel,s in pages:
  patched,metadata=patch(s,rel,fragments)
  target.append((rel,patched));info.append(metadata)
 dest.mkdir(parents=True,mode=0o700)
 for rel,patched in target:
  p=dest/rel;p.parent.mkdir(parents=True,exist_ok=True)
  p.write_text(patched,encoding='utf-8')
 result={
  'count':len(target),
  'restored':{rel:{'source':SOURCES[rel][0],'main_text_chars':len(v[1]),'images':v[2],'links':v[3],'sha256_of_html_fragment':hashlib.sha256(v[0].encode()).hexdigest()} for rel,v in fragments.items()},
  'pages':info
 }
 (dest/'V10_MANIFEST.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print('V10_STAGED_PAGES='+str(len(target)))
 for rel,z in result['restored'].items():print('V10_RESTORED',rel,json.dumps(z,ensure_ascii=False))
 print('V10_EDITS_PRESERVE_ORIGINAL_MAIN_TEXT=yes')
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('docroot',type=Path);p.add_argument('--output-dir',type=Path,required=True)
 a=p.parse_args();build(a.docroot,a.output_dir)
if __name__=='__main__':main()