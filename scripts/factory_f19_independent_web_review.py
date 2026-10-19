#!/usr/bin/env python3
"""Independent, source-aware technical review of an original offline HTML/CSS template.

This reviewer never edits producer outputs, authorizes payment, impersonates
a qualified human reviewer or claims a WCAG audit. All gates are evidence-bound.
"""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import zipfile

MODULES=('header','hero','value','features','workflow','use_cases',
         'security','integrations','pricing','faq','contact','footer')
GATES=('requirements','correctness','negative_cases','usability','accessibility',
       'security','compatibility','provenance','specialist_review','release_integrity')

class Structure(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids=set()
        self.duplicate_ids=set()
        self.links=[]
        self.tags=[]
        self.headings=[]
        self.labels=[]
        self.details=0
    def handle_starttag(self,tag,attrs):
        data=dict(attrs)
        self.tags.append(tag)
        if data.get('id'):
            if data['id'] in self.ids:self.duplicate_ids.add(data['id'])
            self.ids.add(data['id'])
        if tag=='a':self.links.append(data.get('href',''))
        if tag in ('h1','h2','h3'):self.headings.append(tag)
        if tag=='label':self.labels.append(data.get('for',''))
        if tag=='details':self.details+=1

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for data in iter(lambda:f.read(65536),b''):h.update(data)
    return h.hexdigest()

def check(folder,archive,product):
    folder=Path(folder)
    html=folder/'index.html'
    css=folder/'styles.css'
    guide=folder/'README.md'
    license_file=folder/'LICENSE.txt'
    for p in (html,css,guide,license_file,archive):
        if p.is_symlink() or not p.is_file() or p.stat().st_size < 150:
            raise ValueError('REVIEW_MISSING_REAL_ARTIFACT')
    h=html.read_text('utf8');c=css.read_text('utf8');readme=guide.read_text('utf8')
    s=Structure();s.feed(h);s.close()
    # Only self-contained, inert HTML. No external tracking, script tags or offsite submission.
    requirements=(h.startswith('<!doctype html>') and len(h)>4500 and len(c)>4000
                  and all('id="'+n+'"' in h for n in MODULES))
    correctness=(len(s.ids)>=12 and not s.duplicate_ids and
                 s.headings.count('h1')==1 and s.headings.count('h2')>=9
                 and all(x.startswith('#') and x[1:] in s.ids for x in s.links
                         if x.startswith('#')))
    negative_cases=('javascript:' not in h.lower() and '<script' not in h.lower()
                    and '<iframe' not in h.lower() and '<form' not in h.lower()
                    and 'onclick=' not in h.lower() and '@import' not in c)
    usability=(len(s.links)>=8 and all(x in h for x in
              ('Skip to main content','See the features','Explore the workflow'))
              and 'Replace sample claims' in readme)
    accessibility=('href="#main"' in h and 'id="main"' in h
                   and '<main' in h and '<nav' in h and '<footer' in h
                   and s.details>=3 and ':focus-visible' in c and
                   'prefers-reduced-motion' in c and 'aria-label=' in h)
    security=(all(not u.lower().startswith(('http:','https:','//','data:','javascript:'))
                  for u in s.links) and 'url(http' not in c.lower()
              and '<script' not in h.lower() and 'action=' not in h.lower())
    compatibility=('@media (max-width: 760px)' in c
                   and '@media (max-width: 440px)' in c
                   and c.count('{')==c.count('}') and
                   h.count('<html')==h.count('</html>')==1)
    provenance=('Original source' in readme and
                'factory F19' in readme and len(license_file.read_text('utf8'))>=150)
    # Separate review script from producer; content-level checks, not human signoff.
    specialist_review=(s.details>=3 and
                       all((folder/('validation_'+n+'.json')).is_file() for n in MODULES)
                       and all(json.loads((folder/('validation_'+n+'.json')).read_text('utf8')).get('checks_passed')==2 for n in MODULES))
    with zipfile.ZipFile(archive) as z:
        expected={product+'/'+n for n in ('index.html','styles.css','README.md','LICENSE.txt')}
        names=set(z.namelist())
        release_integrity=(names==expected and z.testzip() is None and
          all(hashlib.sha256(z.read(product+'/'+name)).hexdigest()==sha(folder/name)
          for name in ('index.html','styles.css','README.md','LICENSE.txt')))
    checks=dict(zip(GATES,(requirements,correctness,negative_cases,usability,accessibility,
                           security,compatibility,provenance,specialist_review,release_integrity)))
    if not all(checks.values()):
        raise ValueError('INDEPENDENT_WEB_TEMPLATE_REVIEW_FAIL:'+','.join(k for k,v in checks.items() if not v))
    return {'gates':checks,'checks_passed':sum(checks.values()),
            'critical_defects':[],'review_type':'independent_automated_technical_review',
            'human_professional_review_done':False,'owner_acceptance':False,
            'html_sha256':sha(html),'css_sha256':sha(css),
            'archive_sha256':sha(archive)}
