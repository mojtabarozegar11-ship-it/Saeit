#!/usr/bin/env python3
"""G->S: inspect an already-rendered checkout HTML snapshot. No network, payment, or writes.
Usage: python g01_s01_checkout_focus_audit_r30.py snapshot.html --origin https://mojplaywin.com
Output is non-sensitive issue codes and counts; never prints page/customer content.
"""
import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import json
import sys

KEYWORDS=('checkout','purchase','buy now','pay now','order now','invoice')
LIMIT=2_000_000

class Controls(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]
        self.controls=[]
        self.duplicate_ids=set()
        self.ids=set()
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        ident=a.get('id')
        if ident:
            if ident in self.ids:self.duplicate_ids.add(ident)
            self.ids.add(ident)
        if tag in ('a','button'):
            self.controls.append({'tag':tag,'attrs':a,'text':''})
        self.stack.append((tag,len(self.controls)-1 if tag in ('a','button') else None))
    def handle_data(self,data):
        for _,idx in self.stack:
            if idx is not None:self.controls[idx]['text']+=data
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:
                del self.stack[i:]
                return

def audit(html,origin):
    p=Controls()
    p.feed(html)
    issues=[]
    checkout_count=0
    origin_parts=urlsplit(origin)
    if origin_parts.scheme!='https' or not origin_parts.netloc:
        raise ValueError('origin must be an absolute HTTPS URL')
    for i,c in enumerate(p.controls):
        a=c['attrs']
        label=' '.join((a.get('aria-label') or '',a.get('title') or '',c['text'])).strip()
        descriptor=' '.join((label,a.get('id') or '',a.get('class') or '',a.get('href') or '')).lower()
        if not any(term in descriptor for term in KEYWORDS):continue
        checkout_count+=1
        if a.get('aria-hidden')=='true' or 'hidden' in a:issues.append(f'CTA_{i}_HIDDEN')
        if not label.strip():issues.append(f'CTA_{i}_NO_ACCESSIBLE_TEXT')
        if c['tag']=='a':
            href=(a.get('href') or '').strip()
            if not href or href=='#' or href.lower().startswith(('javascript:','data:')):
                issues.append(f'CTA_{i}_PLACEHOLDER_LINK')
            else:
                dest=urlsplit(urljoin(origin,href))
                if (dest.scheme,dest.netloc)!=(origin_parts.scheme,origin_parts.netloc):
                    issues.append(f'CTA_{i}_EXTERNAL_NAVIGATION')
            if a.get('target')=='_blank' and 'noopener' not in (a.get('rel') or '').split():
                issues.append(f'CTA_{i}_NEW_TAB_WITHOUT_NOOPENER')
        else:
            # A submit control may override its form destination with formaction.
            # Reject external, insecure or script destinations in a read-only audit.
            if 'formaction' in a:
                action=(a.get('formaction') or '').strip()
                dest=urlsplit(urljoin(origin,action))
                if not action or (dest.scheme,dest.netloc)!=(origin_parts.scheme,origin_parts.netloc):
                    issues.append(f'CTA_{i}_FORM_ACTION_OFF_ORIGIN')
            if a.get('type','submit').lower()=='submit':
                issues.append(f'CTA_{i}_SUBMIT_REQUIRES_AUTHORIZED_STAGING_ONLY')
    if p.duplicate_ids:issues.append('DUPLICATE_HTML_IDS')
    if not checkout_count:issues.append('NO_CHECKOUT_CTA_IN_SNAPSHOT')
    return {'status':'REVIEW_REQUIRED' if issues else 'STATIC_SNAPSHOT_PASS',
            'checkout_controls':checkout_count,'issues':sorted(set(issues)),
            'scope':'offline snapshot only; no payment, navigation, entitlement or live verification'}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('html_file')
    ap.add_argument('--origin',default='https://mojplaywin.com')
    args=ap.parse_args()
    path=Path(args.html_file)
    if not path.is_file() or path.stat().st_size>LIMIT:
        print(json.dumps({'status':'BLOCKED','reason':'missing_or_oversized_snapshot'}))
        return 2
    try:result=audit(path.read_text(encoding='utf-8'),args.origin)
    except (UnicodeError,ValueError) as e:
        print(json.dumps({'status':'BLOCKED','reason':type(e).__name__}))
        return 2
    print(json.dumps(result,sort_keys=True))
    return 0 if result['status']=='STATIC_SNAPSHOT_PASS' else 1

if __name__=='__main__':sys.exit(main())
