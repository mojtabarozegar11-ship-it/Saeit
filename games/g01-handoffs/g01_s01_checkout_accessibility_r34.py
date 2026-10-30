#!/usr/bin/env python3
"""Offline-only static form accessibility preflight. Never makes HTTP requests or submits forms."""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path

class Audit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nodes=[]; self.stack=[]; self.form_depth=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        node={'tag':tag,'attrs':attrs,'text':'','parents':tuple(self.stack),'form':self.form_depth>0}
        self.nodes.append(node)
        if tag=='form': self.form_depth+=1
        if tag not in {'input','img','br','hr','meta','link','source','area','embed','wbr'}: self.stack.append(len(self.nodes)-1)
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if self.stack and self.nodes[self.stack[-1]]['tag']==tag:self.stack.pop()
    def handle_data(self,data):
        for index in self.stack:self.nodes[index]['text']+=data
    def handle_endtag(self,tag):
        for k in range(len(self.stack)-1,-1,-1):
            if self.nodes[self.stack[k]]['tag']==tag:
                del self.stack[k:];break
        if tag=='form':self.form_depth=max(0,self.form_depth-1)

def inspect(html):
    parser=Audit();parser.feed(html);nodes=parser.nodes
    ids={};labels={};duplicates=set()
    for n in nodes:
        identifier=n['attrs'].get('id')
        if identifier:
            if identifier in ids:duplicates.add(identifier)
            ids[identifier]=n
        if n['tag']=='label' and n['attrs'].get('for'):labels.setdefault(n['attrs']['for'],[]).append(n)
    issues=[];counts={'forms':0,'inputs':0,'buttons':0,'links':0}
    for i,n in enumerate(nodes):
        tag,a=n['tag'],n['attrs']
        if tag=='form':counts['forms']+=1
        if not n['form']:continue
        if tag=='input' and a.get('type','text').lower()=='hidden':continue
        if tag not in {'input','select','textarea','button','a'}:continue
        if tag=='a' and not a.get('href'):continue
        counts['inputs' if tag in {'input','select','textarea'} else 'buttons' if tag=='button' else 'links']+=1
        name=(a.get('aria-label') or '').strip()
        if not name and a.get('aria-labelledby'):name=' '.join(ids[j]['text'].strip() for j in a['aria-labelledby'].split() if j in ids).strip()
        if not name and tag in {'button','a'}:name=n['text'].strip()
        if not name and tag=='input' and a.get('type','').lower() in {'submit','button','reset'}:name=(a.get('value') or '').strip()
        if not name and a.get('id') in labels:name=' '.join(label['text'] for label in labels[a['id']]).strip()
        if not name:
            for parent in n['parents']:
                if nodes[parent]['tag']=='label':name=nodes[parent]['text'].strip();break
        if not name:issues.append({'code':'MISSING_ACCESSIBLE_NAME','tag':tag,'control_index':i})
    if duplicates:issues.append({'code':'DUPLICATE_IDS','count':len(duplicates)})
    return {'stage':'OFFLINE_STATIC_PREFLIGHT_ONLY','requests_made':0,'forms_submitted':0,'counts':counts,'issues':issues,'passed':not issues}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('saved_html',type=Path);a=ap.parse_args()
    report=inspect(a.saved_html.read_text(encoding='utf-8'))
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['passed'] else 2
if __name__=='__main__':raise SystemExit(main())
