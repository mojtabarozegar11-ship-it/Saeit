#!/usr/bin/env python3
"""Build public-only Persian search index and HTML search UI from actual site HTML files."""
import json,re,sys,html
from pathlib import Path
from html.parser import HTMLParser

SKIP={'mohammad','ghanadi','amozeshgah','tala','business','site-heritage','admin','static','cgi-bin','education','_private','backups','search','store'}
class Parse(HTMLParser):
 def __init__(self):super().__init__();self.ignore=0;self.in_title=False;self.in_main=0;self.title='';self.text=[];self.headings=[];self.headmode=0
 def handle_starttag(self,tag,attrs):
  if tag in ('script','style','nav','footer','header','svg'):self.ignore+=1
  if tag=='title':self.in_title=True
  if tag=='main':self.in_main+=1
  if tag in ('h1','h2','h3') and self.in_main:self.headmode+=1
 def handle_endtag(self,tag):
  if tag in ('script','style','nav','footer','header','svg'):self.ignore=max(0,self.ignore-1)
  if tag=='title':self.in_title=False
  if tag=='main':self.in_main=max(0,self.in_main-1)
  if tag in ('h1','h2','h3'):self.headmode=max(0,self.headmode-1)
 def handle_data(self,data):
  t=' '.join(data.split())
  if not t or self.ignore:return
  if self.in_title:self.title+=t+' '
  if self.in_main:
   if self.headmode:self.headings.append(t)
   self.text.append(t)

def main(root,dest):
 assert root.is_dir() and not dest.exists(), 'Unsafe destination'
 rows=[];seen=set()
 for f in root.rglob('index.html'):
  p=f.relative_to(root)
  if f.is_symlink() or any(a in SKIP or a.startswith('.') or a.startswith('__') for a in p.parts):continue
  if len(p.parts)>7:continue
  if p.parts==('index.html',):url='/'
  else:url='/'+str(p.parent).replace('\\','/')+'/'
  if url in seen:continue
  try:s=f.read_text('utf-8');o=Parse();o.feed(s)
  except (OSError,UnicodeError):continue
  if len(' '.join(o.text))<90:continue
  title=(o.title.strip() or ' '.join(o.headings[:1]) or url)[:160]
  body=' '.join(o.text)
  body=re.sub(r'\s+',' ',body)
  row={'url':url,'title':title,'headings':' · '.join(o.headings[:12])[:420],'summary':body[:450],'content':body[:3500]}
  rows.append(row);seen.add(url)
 rows.sort(key=lambda r:r['url'])
 assert len(rows)>=34,len(rows)
 dest.mkdir(mode=0o755,parents=True)
 (dest/'index.json').write_text(json.dumps({'version':1,'count':len(rows),'pages':rows},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
 html_page='''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,follow"><title>جست‌وجو در سایت زمرد ملل | Zomorod Mell</title><link rel="icon" href="/favicon.ico"><style>:root{color-scheme:dark;font-family:Tahoma,Arial,sans-serif}body{margin:0;background:#203b23;color:#f0ead8;min-height:100vh}header,footer{padding:20px 5%;background:#193121;border-bottom:1px solid #ac914d}header img{width:52px;height:52px;vertical-align:middle;object-fit:contain}main{max-width:950px;padding:32px 16px;margin:auto}h1{color:#f1d48d}form{display:flex;gap:10px;flex-wrap:wrap}input{flex:1;min-width:230px;padding:15px;background:#fff;color:#202020;border:2px solid #c7aa66;border-radius:12px;font:inherit}button{padding:12px 25px;background:#e9c872;border:0;border-radius:11px;font:inherit;cursor:pointer}article{background:#284932;border:1px solid #a89559;border-radius:16px;padding:18px 22px;margin:12px 0}article a{color:#ffe49b;font-size:19px}p{line-height:1.9}a{color:#f5cf75}.muted{color:#c7ccb7}</style></head><body><header><a href="/" aria-label="صفحه اصلی"><img src="/static/site/zomorod-v7/company-logo.webp" alt="لوگوی شرکت"></a> شرکت کشت و صنعت زمرد ملل — جست‌وجوی سایت</header><main><h1>جست‌وجو در مطالب زمرد ملل</h1><form id="search" role="search"><label for="q" class="muted">عبارت جست‌وجو</label><input id="q" name="q" type="search" maxlength="100" placeholder="مثلاً: ژنتیک، اقتصاد، باغبانی" required><button>جست‌وجو</button></form><p id="status" class="muted" aria-live="polite">فهرست مطالب در حال بارگذاری است…</p><div id="results"></div></main><footer>تمام حقوق مادی و معنوی سایت برای شرکت کشت و صنعت زمرد ملل محفوظ است . آبان ۱۳۹۸ مجتبی روزگار</footer><script>const form=document.querySelector('#search'),input=document.querySelector('#q'),list=document.querySelector('#results'),status=document.querySelector('#status');let pages=[];const normalize=s=>String(s||'').toLowerCase().replace(/[يى]/g,'ی').replace(/ك/g,'ک').replace(/[\u200c\u064b-\u065f]/g,' ').replace(/\s+/g,' ').trim();fetch('./index.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('index unavailable');return r.json()}).then(j=>{pages=Array.isArray(j.pages)?j.pages:[];run()}).catch(()=>status.textContent='فهرست موقتاً در دسترس نیست.');function run(){const q=normalize(input.value),tokens=q.split(' ').filter(x=>x.length);const scored=pages.map(p=>{const title=normalize(p.title),h=normalize(p.headings),body=normalize(p.content);let points=0;if(tokens.length)for(const x of tokens){if(title.includes(x))points+=14;if(h.includes(x))points+=6;if(body.includes(x))points+=1;}return {p,points}}).filter(v=>tokens.length?tokens.every(t=>(normalize(v.p.title+' '+v.p.headings+' '+v.p.content)).includes(t)):false).sort((a,b)=>b.points-a.points).slice(0,40);list.replaceChildren();if(!tokens.length){status.textContent=pages.length+' صفحه قابل جست‌وجو؛ برای شروع عبارت بنویسید.';return;}status.textContent=scored.length+' نتیجه برای «'+input.value+'»';for(const {p} of scored){const card=document.createElement('article'),a=document.createElement('a'),paragraph=document.createElement('p');a.href=p.url;a.textContent=p.title;paragraph.textContent=p.summary.slice(0,250);card.append(a,paragraph);list.append(card)}}form.addEventListener('submit',e=>{e.preventDefault();history.replaceState(null,'','?q='+encodeURIComponent(input.value));run()});input.value=(new URLSearchParams(location.search).get('q')||'').slice(0,100);</script></body></html>'''
 (dest/'index.html').write_text(html_page,encoding='utf-8')
 print('SEARCH_READY',len(rows),'public pages only')
if __name__=='__main__':main(Path(sys.argv[1]),Path(sys.argv[2]))