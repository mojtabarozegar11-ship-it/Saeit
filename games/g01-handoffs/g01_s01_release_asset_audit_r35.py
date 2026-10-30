#!/usr/bin/env python3
"""Read-only preflight of a local static game release directory; no network or writes."""
import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote

class Assets(HTMLParser):
    def __init__(self):
        super().__init__(); self.refs=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag in {'script','img','source'} and a.get('src'):
            self.refs.append(a['src'])
        if tag=='link' and 'stylesheet' in (a.get('rel') or '').lower() and a.get('href'):
            self.refs.append(a['href'])

def audit(root:Path):
    root=root.absolute()
    issues=[]; inspected=0; references=0
    if not root.is_dir(): return {'passed':False,'issues':['NOT_DIRECTORY'],'inspected':0,'references':0,'network_requests':0}
    for p in root.rglob('*'):
        if p.is_symlink():issues.append('SYMLINK:'+p.relative_to(root).as_posix())
    index=root/'index.html'
    if not index.is_file():issues.append('MISSING_ENTRYPOINT:index.html')
    for p in root.rglob('*'):
        if not p.is_file() or p.is_symlink() or p.suffix.lower() not in {'.html','.css','.js','.mjs'}:continue
        inspected+=1
        body=p.read_text(encoding='utf-8')
        refs=[]
        if p.suffix.lower()=='.html':
            parser=Assets();parser.feed(body);refs+=parser.refs
        if p.suffix.lower()=='.css':
            refs += [m.strip(' \t\"\'') for m in re.findall(r'url\(([^)]+)\)',body)]
        if p.suffix.lower() in {'.js','.mjs'}:
            refs += re.findall(r'\b(?:import|export)\s+(?:[^;]*?\s+from\s+)?[\"\'](\.[^\"\']+)[\"\']',body)
        for raw in refs:
            if not raw or raw.startswith(('data:','#')):continue
            references+=1
            u=urlsplit(raw)
            if u.scheme or u.netloc or raw.startswith('//'):
                issues.append('REMOTE_DEPENDENCY:'+p.relative_to(root).as_posix()+':'+raw[:120]);continue
            candidate=(p.parent/unquote(u.path)).resolve()
            if not candidate.is_relative_to(root):
                issues.append('PATH_ESCAPE:'+p.relative_to(root).as_posix()+':'+raw[:120]);continue
            if not candidate.is_file():issues.append('MISSING:'+p.relative_to(root).as_posix()+':'+raw[:120])
    return {'passed':not issues,'issues':issues,'inspected':inspected,'references':references,'network_requests':0,'mode':'OFFLINE_READ_ONLY'}

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('release_dir',type=Path)
    result=audit(a.parse_args().release_dir)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['passed'] else 2)
