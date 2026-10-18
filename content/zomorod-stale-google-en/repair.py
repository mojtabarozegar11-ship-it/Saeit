#!/usr/bin/env python3
"""Stage only: restore indexed English URLs and repair site-search normalization.
Does not touch production. The release workflow owns backup/rollback/health gates.
"""
from __future__ import annotations
import argparse
import html
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

ORIGIN='https://zomorodmelal.ir'
NS='http://www.sitemaps.org/schemas/sitemap/0.9'
BRAND='Zomorod Melal Agro-Industry Company'
LOGO='/static/site/zomorod-v7/company-logo.webp'
CSS=r"""
:root{color-scheme:dark;--background:#203b23;--card:#28472d;--gold:#edd08b;--text:#f2efd9;--muted:#d9e3cf;--stroke:#a88c52}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--background);color:var(--text);font:16px/1.8 system-ui,Arial,sans-serif}
a{color:var(--gold)}.container{width:min(1200px,calc(100% - 36px));margin:auto}
.skip{position:absolute;left:-200vw}.skip:focus{left:16px;top:12px;z-index:999}
.site-header{position:sticky;top:0;z-index:90;background:#17311e;border-bottom:3px double var(--gold);box-shadow:0 8px 28px #091b11a9}
.header-grid{display:flex;align-items:center;flex-wrap:wrap;gap:14px;padding:12px 0}
.brand{display:flex;align-items:center;gap:12px;text-decoration:none;font-weight:800;color:var(--gold);font-size:1rem}
.brand img{width:54px;height:54px;border:3px solid var(--gold);border-radius:50%;background:#f8f1dc;object-fit:cover}
.brand small{display:block;color:var(--muted);font-size:12px;font-weight:400}
nav{display:flex;gap:8px;flex-wrap:wrap;margin-left:auto}nav a{display:inline-flex;text-decoration:none;border:1px solid var(--stroke);border-radius:999px;padding:5px 12px;color:#f7deb0;font-size:13px;transition:background .2s}
nav a:hover,nav a:focus-visible{background:#4a6647}.hero{padding:66px 0 55px;border-bottom:1px solid var(--stroke)}
.eyebrow{letter-spacing:.12em;text-transform:uppercase;font-size:12px;color:var(--gold);font-weight:800}
h1{font-size:clamp(34px,5vw,62px);line-height:1.2;letter-spacing:-.025em;margin:10px 0 24px;max-width:970px;color:var(--gold)}
h2{font-size:clamp(22px,3vw,32px);line-height:1.35;color:var(--gold)}
.lead{font-size:clamp(16px,2vw,21px);max-width:890px;color:var(--muted)}
.pills{display:flex;flex-wrap:wrap;gap:12px;margin-top:30px}.pill{border:1px solid var(--gold);border-radius:999px;padding:9px 16px;color:var(--gold);text-decoration:none}
section.content{padding:36px 0 70px}.columns{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,270px),1fr));gap:16px}
.panel{padding:24px;border:1px solid var(--stroke);border-radius:20px;background:var(--card);box-shadow:0 8px 24px #0d261729}
.panel h2,.panel h3{margin-top:0}.panel p,.panel li{color:var(--muted)}.panel li{margin-bottom:9px}
.note{margin-top:26px;padding:22px;border-left:4px solid var(--gold);background:#294732;color:var(--muted)}
.related{display:flex;gap:10px;flex-wrap:wrap;margin-top:24px}.related a{padding:8px 12px;border:1px solid var(--stroke);border-radius:12px}
footer{background:#142c1a;padding:30px 0 22px;border-top:3px solid var(--gold);font-size:13px;color:var(--muted)}
footer a{color:var(--gold)}:focus-visible{outline:3px solid #ffdf89;outline-offset:3px}
@media(max-width:720px){.site-header{position:relative}.hero{padding:42px 0}.header-grid{align-items:flex-start}nav{margin-left:0}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
"""
TOPICS={
'agriculture':('Document land and water access, cropping history, crop suitability and available machinery.','Compare feasible options using actual costs, labour, weather and measured output.','Use soil and water testing and qualified local advice for field decisions.'),
'industry':('Define the product, input materials, target capacity and process boundaries.','Measure downtime, defects, energy use and the bottleneck before investing.','Verify safety, quality requirements and available maintenance resources.'),
'research':('Write a clear research question, primary outcome and scope exclusions.','Specify sampling, experimental controls, methods and uncertainty before interpreting evidence.','Record sources, reproducible procedures and ethical limitations.'),
'knowledge':('Identify what question a guide answers and who needs it.','Locate primary references, their publication dates and their method.','Explain uncertainty and link to related disciplines where appropriate.'),
'education':('Start from a measurable learning outcome and prerequisite knowledge.','Work through one concrete example, then complete a small independent exercise.','Evaluate the result against explicit criteria and revise based on feedback.'),
'economy':('Separate initial expenditure, running costs, financing and opportunity cost.','Use the same period, units and currency when comparing options.','Consider base, optimistic and adverse scenarios before committing funds.'),
'market':('Define the problem, essential product specifications and acceptance criteria.','Compare relevant quality indicators, authenticity evidence and delivery conditions.','Confirm stock, price and contractual terms before placing any order.'),
'news':('Identify the original publisher, event date and first-hand evidence.','Separate verified facts from interpretation, forecasts and opinion.','Confirm corrections and sources before republishing a claim.'),
'newsletter':('Document the original announcement and its approval status.','Label dates, sources and changes, and distinguish plans from completed work.','Provide a contact path for factual corrections.'),
'company':('Describe the request, expected result and constraints in writing.','Identify the people responsible for verification, budget and timeline.','Agree a documented scope before describing any partnership as active.'),
'about':('Review the research priorities, governance and stated areas of work.','Distinguish strategic intentions from validated facilities, equipment and outcomes.','Request project-specific documentation before relying on capability claims.'),
'agents':('Define inputs, allowed actions, outputs and acceptance tests.','Introduce human approval for sensitive decisions and log each run.','Evaluate reliability and audit failures rather than assuming automation succeeded.'),
'weather':('Check the location, forecast horizon, timestamp and original source.','Relate the forecast to the operation: irrigation, harvesting or transport.','Prepare for uncertainty, changing conditions and a contingency action.'),
'studio':('Write a brief specifying the audience, story and core interaction.','Build a small testable prototype and collect structured feedback.','Validate content rights, accessibility and production effort before scaling.'),
'marketing':('Define the intended audience, message and measurable objective.','Verify product claims, user consent and channel requirements.','Measure outcomes, costs and feedback instead of relying on impressions alone.'),
'gold':('Specify purity, weight, craftsmanship and documentation of authenticity.','Separate metal value, workmanship, taxes and other quoted costs.','Confirm the current price, seller and transaction terms independently.'),
'carpets':('Record materials, dimensions, technique, condition and provenance evidence.','Photograph representative details and distinguish fact from uncertainty.','Seek appropriate specialist review for valuation and authenticity.'),
'vehicles':('Define operating conditions, capacity, duty cycle and access to repairs.','Inspect technical condition, parts availability and maintenance records.','Estimate total cost of ownership, not only purchase price.'),
'real-estate':('List required use, access, services, budget and legal restrictions.','Inspect the property and request reliable ownership and compliance documents.','Have licensed professionals evaluate important legal or structural concerns.'),
'auctions':('Retrieve the official notice, specifications, terms and submission method.','Record deadlines, eligibility, guarantees and financial exposure.','Verify any opportunity is still open before submitting a bid.'),
'restaurant':('Record supplier specifications, storage conditions and stock movement.','Separate purchasing, preparation, sale, loss and customer feedback.','Apply food-safety requirements and measure the operational effect of changes.'),
'signals':('Identify the data source, timestamp, units and validation method.','Separate observations from forecasts and explicit investment recommendations.','Do not assume this section supplies live actionable trade signals.'),
'blog':('Choose a single concrete problem and target reader.','Support claims with examples, source references and practical limitations.','End with an action readers can evaluate independently.'),
'chain-stores':('Describe sourcing, quality assurance, logistics and traceability.','Separate proposed branch expansion from confirmed active inventory.','Verify supplier, stock and delivery terms before making commercial claims.'),
'company-gallery':('Identify what each image depicts and when it was created.','Differentiate illustration, branding and actual project documentation.','Publish only imagery with verified rights and accurate captions.'),
'contact':('Describe your question, location, timeframe and objective.','Include relevant non-sensitive documents and preferred contact method.','Wait for explicit written confirmation before assuming a delivery commitment.'),
'authors':('Distinguish a professional biography from independently verified credentials.','Link published work, research topics and supporting documentation.','Provide corrections when biographical details or appointments change.'),
}
NAV=[('Home','/en/'),('Company','/en/company/'),('About','/en/about/'),('Research','/en/research/'),('Agriculture','/en/agriculture/'),('Industry','/en/industry/'),('Knowledge','/en/knowledge/'),('Contact','/en/contact/')]
class ReadMain(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.ignore=0;self.depth=0;self.title_mode=False;self.heading=0;self.title=[];self.text=[];self.headings=[]
 def handle_starttag(self,tag,attrs):
  if tag in ('script','style','nav','footer','header','svg'):self.ignore+=1
  if tag=='title':self.title_mode=True
  if tag=='main':self.depth+=1
  if tag in ('h1','h2','h3') and self.depth:self.heading+=1
 def handle_endtag(self,tag):
  if tag in ('script','style','nav','footer','header','svg'):self.ignore=max(0,self.ignore-1)
  if tag=='title':self.title_mode=False
  if tag=='main':self.depth=max(0,self.depth-1)
  if tag in ('h1','h2','h3'):self.heading=max(0,self.heading-1)
 def handle_data(self,data):
  data=' '.join(data.split())
  if not data or self.ignore:return
  if self.title_mode:self.title.append(data)
  if self.depth:
   self.text.append(data)
   if self.heading:self.headings.append(data)
def key_for(path):
 p=[x for x in path.strip('/').split('/') if x]
 if 'guides' in p:return p[-1]
 if 'authors' in p:return 'authors'
 return p[-1] if p else 'company'
def site_shell(page):
 path,title,teaser=page['path'],page['title'],page['teaser']
 key=key_for(path)
 points=TOPICS.get(key,TOPICS['company'])
 topic='Guide' if '/guides/' in path else 'Company and research'
 if '/authors/' in path:topic='Research profile'
 if path=='/en/':
  teaser='Zomorod Melal connects scientific research, agricultural genetics, production planning and specialist services. Explore the company and independently review the scope, evidence and terms of each area of activity.'
 if teaser.endswith('…') or teaser.endswith('...'):teaser=teaser.rsplit(' ',1)[0].rstrip(' .')+'.'
 if len(teaser)<40:teaser='Explore '+title.lower()+' through practical evidence, scientific reasoning and relevant company resources.'
 nav=''.join(f'<a href="{html.escape(href,quote=True)}">{html.escape(label)}</a>' for label,href in NAV)
 primary=[
 f'<div class="panel"><h2>Plan and scope</h2><p>{html.escape(points[0])}</p><p>Define the intended user, desired outcome and constraints before moving to implementation.</p></div>',
 f'<div class="panel"><h2>Evidence and quality</h2><p>{html.escape(points[1])}</p><p>Keep source information, dates and assumptions with each material decision so that it can be reviewed.</p></div>',
 f'<div class="panel"><h2>Decision and next steps</h2><p>{html.escape(points[2])}</p><p>Choose a small, verifiable next action. Record what happened and revise the approach when new evidence becomes available.</p></div>',
 ]
 linkset= [('Company','/en/company/'),('Research','/en/research/'),('Contact','/en/contact/'),('Persian main website','/')]
 related=''.join(f'<a href="{href}">{label}</a>' for label,href in linkset if href!=path)
 t=html.escape(title)
 url=ORIGIN+path
 description=html.escape(teaser[:210],quote=True)
 return f'''<!doctype html>
<html lang="en" dir="ltr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="index,follow"><meta name="description" content="{description}">
<link rel="canonical" href="{html.escape(url,quote=True)}"><link rel="icon" href="/favicon.ico">
<meta property="og:type" content="website"><meta property="og:locale" content="en_US"><meta property="og:title" content="{t} | Zomorod Melal">
<meta property="og:url" content="{html.escape(url,quote=True)}">
<title>{t} | Zomorod Melal</title><style>{CSS}</style></head>
<body><a class="skip" href="#main">Skip to content</a>
<header class="site-header"><div class="container header-grid"><a class="brand" href="/en/"><img src="{LOGO}" width="54" height="54" alt="Zomorod Melal company logo">
<span>ZOMOROD MELAL<small>Scientific research · Agriculture · Industry</small></span></a><nav aria-label="Site navigation">{nav}<a href="/">فارسی</a></nav></div></header>
<main id="main"><div class="container"><section class="hero"><p class="eyebrow">{html.escape(topic)} · Zomorod Melal</p><h1>{t}</h1>
<p class="lead">{html.escape(teaser)}</p><div class="pills"><a class="pill" href="/en/research/">Scientific research</a><a class="pill" href="/en/about/">About the company</a><a class="pill" href="/en/contact/">Collaboration</a></div></section>
<section class="content" aria-label="Practical information"><div class="columns">{''.join(primary)}</div>
<div class="note"><strong>Scope and verification.</strong> This English information page is an editorial introduction. Named research fields, products, facilities or planned services do not by themselves establish operational availability, accreditation, inventory or contractual commitments. Verify current details with the company and appropriate official sources.</div>
<h2>Explore related sections</h2><div class="related">{related}</div></section></div></main>
<footer><div class="container"><p>© Zomorod Melal Agro-Industry Company — Scientific research, genetics and sustainable development.</p><p><a href="/">Persian website</a> · <a href="/en/about/">About us</a> · <a href="/en/contact/">Contact</a></p></div></footer>
</body></html>'''

def render(root:Path,out:Path,indexed:Path):
 root=root.resolve(strict=True)
 if out.exists():raise RuntimeError('Candidate already exists')
 assert (root/'index.html').is_file() and not (root/'en').exists(), 'English docroot already exists'
 for p in ('sitemap.xml','search/index.json','search/index.html'):
  assert (root/p).is_file() and not (root/p).is_symlink(),p
 source=json.loads(indexed.read_text('utf-8'))
 records=source['pages']
 assert 45<=len(records)<=60
 routes=[p['path'] for p in records]
 assert len(set(routes))==len(routes)
 assert '/en/' in routes and '/en/about/' in routes and '/en/guides/market/' in routes
 out.mkdir(parents=True,mode=0o700)
 for page in records:
  route=page['path']; assert re.fullmatch(r'/en/(?:[a-z0-9-]+/)*',route)
  path=out/route.lstrip('/')/'index.html'
  path.parent.mkdir(parents=True,exist_ok=True)
  source_html=site_shell(page)
  assert 'lang="en"' in source_html and ORIGIN+route in source_html
  path.write_text(source_html,encoding='utf-8')
 (out/'en/.htaccess').write_text('PassengerEnabled off\nDirectoryIndex index.html\nOptions -Indexes\n',encoding='utf-8')
 sroot=ET.parse(root/'sitemap.xml')
 xml=sroot.getroot()
 old=[n.text for n in xml.findall(f'{{{NS}}}url/{{{NS}}}loc')]
 assert len(old)==92 and len(set(old))==92,('unexpected original sitemap',len(old))
 new=sorted(ORIGIN+x for x in routes)
 for url in new:ET.SubElement(ET.SubElement(xml,f'{{{NS}}}url'),f'{{{NS}}}loc').text=url
 ET.register_namespace('',NS)
 content=ET.tostring(xml,encoding='utf-8',xml_declaration=True)
 (out/'sitemap.xml').write_bytes(content)
 assert len(ET.fromstring(content).findall(f'{{{NS}}}url'))==92+len(routes)
 sh=(root/'search/index.html').read_text('utf-8')
 old_expr=".replace(/\\s+/g,' ').trim()"
 assert sh.count(old_expr)==1,('missing JS normalization pattern',sh.count(old_expr))
 replaced=".replace(/[_-]+/g,' ').replace(/\\s+/g,' ').trim()"
 sh=sh.replace(old_expr,replaced,1)
 assert 'noindex,follow' in sh and 'zm-v7-header' in sh and 'data-zm-v10="shared-theme"' in sh
 (out/'search').mkdir(mode=0o700)
 (out/'search/index.html').write_text(sh,encoding='utf-8')
 rows=[]
 for url in old+new:
  route=url.removeprefix(ORIGIN)
  if url in new: f=out/route.lstrip('/')/'index.html'
  else:f=root/route.lstrip('/')/'index.html'
  assert f.is_file(),(url,str(f))
  parser=ReadMain();parser.feed(f.read_text('utf-8'))
  body=' '.join(parser.text)
  if len(body)<60:raise RuntimeError('Too little visible content: '+url)
  name=' '.join(parser.title).strip() or (' '.join(parser.headings[:1]) or route)
  row={'url':route,'title':name[:170],'headings':' · '.join(parser.headings[:15])[:550],
       'summary':body[:500],'content':body[:4500]}
  if route=='/': row['content'] += ' Zomorod Melal zomorod_melal Zomorod Mell زمرد ملل'
  rows.append(row)
 assert len(rows)==139 and len(set(x['url'] for x in rows))==139
 (out/'search/index.json').write_text(json.dumps({'version':2,'count':len(rows),'pages':rows},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
 matching=[row['url'] for row in rows if 'zomorod melal' in (row['title']+' '+row['headings']+' '+row['content']).lower().replace('_','-').replace('-',' ')]
 assert '/en/' in matching and '/' in matching, ('Missing brand aliases',matching[:5])
 manifest={'new_english_pages':len(records),'previous_canonicals':92,'total_canonicals':len(rows),'search_results_for_zomorod_melal':len(matching),
           'changed_existing':['sitemap.xml','search/index.html','search/index.json'],
           'english_routes':routes,
           'original_sha256':{k:hashlib.sha256((root/k).read_bytes()).hexdigest() for k in ('sitemap.xml','search/index.html','search/index.json')}}
 (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 print('ENGLISH_PAGES_STAGED',len(records))
 print('SITEMAP_OLD_NEW',92,len(rows))
 print('BRAND_QUERY_MATCH_COUNT',len(matching))
 print('STAGE_ONLY_READONLY_SOURCE=1')
 return manifest
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('output',type=Path);ap.add_argument('indexed',type=Path);a=ap.parse_args()
 render(a.root,a.output,a.indexed)
