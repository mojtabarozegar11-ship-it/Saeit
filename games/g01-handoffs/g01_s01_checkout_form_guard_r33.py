#!/usr/bin/env python3
"""G-01 to S-01: offline read-only checkout form preflight. No network or form submissions."""
from __future__ import annotations
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urlsplit

class FormAudit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms=[]
        self.labels=set()
        self._label_depth=0
        self._current=None

    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='label':
            self._label_depth+=1
            if a.get('for'):self.labels.add(a['for'])
        if tag=='form':
            self._current={'method':(a.get('method') or 'get').lower(),'action':a.get('action') or '','inputs':[]}
            self.forms.append(self._current)
        if tag in {'input','select','textarea'} and self._current is not None:
            kind=(a.get('type') or 'text').lower() if tag=='input' else tag
            if kind in {'hidden','submit','button','reset','image'}:return
            self._current['inputs'].append({'kind':kind,'id':a.get('id'),
                'labelled':bool(a.get('aria-label') or a.get('aria-labelledby') or self._label_depth)})

    def handle_endtag(self,tag):
        if tag=='label':self._label_depth=max(0,self._label_depth-1)
        if tag=='form':self._current=None

    def audit(self):
        issues=[]
        for form in self.forms:
            method=form['method']
            parsed=urlsplit(form['action'].strip())
            if parsed.scheme.lower() in {'javascript','data','file'}:issues.append('UNSAFE_ACTION_SCHEME')
            elif parsed.scheme.lower()=='http':issues.append('INSECURE_HTTP_ACTION')
            elif parsed.netloc or parsed.scheme.lower()=='https':issues.append('EXTERNAL_ACTION_REQUIRES_OWNER_REVIEW')
            if method not in {'get','post'}:issues.append('UNSUPPORTED_METHOD')
            if method=='post':issues.append('POST_REQUIRES_AUTHENTICATED_STAGING_NO_SUBMIT')
            for field in form['inputs']:
                if not field['labelled'] and field['id'] not in self.labels:issues.append('UNLABELLED_FORM_CONTROL')
                if method=='get' and field['kind'] in {'password','email','tel'}:issues.append('SENSITIVE_FIELD_IN_GET_FORM')
        return {'forms':len(self.forms),'controls':sum(len(f['inputs']) for f in self.forms),
                'issue_counts':{k:issues.count(k) for k in sorted(set(issues))},
                'read_only':True,'submissions':0,'customer_values_captured':0}

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('saved_html',type=Path,help='Authorized saved HTML path, never a URL')
    args=ap.parse_args(argv)
    if not args.saved_html.is_file() or args.saved_html.stat().st_size>4_000_000:
        ap.error('Expected an existing saved HTML file <=4 MB')
    parser=FormAudit()
    parser.feed(args.saved_html.read_text(encoding='utf-8'))
    result=parser.audit()
    print(json.dumps(result,sort_keys=True))
    return 2 if result['issue_counts'] else 0

if __name__=='__main__':
    raise SystemExit(main())
