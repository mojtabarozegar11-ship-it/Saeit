#!/usr/bin/env python3
"""Offline audit of a REDACTED buyer invoice/download HTML snapshot.
Never prints page content, customer data, tokens, query values or URLs.
UI regression aid only; NOT proof of payment or file delivery.
"""
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

class Audit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links=[];self.status=False;self.headings=0;self._anchor=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='h1':self.headings+=1
        if a.get('role')=='status' or a.get('aria-live') in ('polite','assertive'):self.status=True
        if tag=='a':self._anchor={'href':a.get('href','').strip(),'label':a.get('aria-label','').strip(),'text':'','hidden':('hidden' in a or a.get('aria-hidden')=='true' or a.get('tabindex')=='-1')}
    def handle_data(self,data):
        if self._anchor:self._anchor['text']+=data.strip()
    def handle_endtag(self,tag):
        if tag=='a' and self._anchor:self.links.append(self._anchor);self._anchor=None

def audit(html):
    p=Audit();p.feed(html);errors=[]
    if p.headings!=1:errors.append('H1_COUNT')
    if not p.status:errors.append('NO_ACCESSIBLE_STATUS')
    downloads=0
    for a in p.links:
        url=urlsplit(a['href']);path=url.path.lower()
        if any(word in path for word in ('invoice','download','receipt')):
            downloads+=1
            if url.scheme or url.netloc or not path.startswith('/') or a['href'].startswith('//'):errors.append('EXTERNAL_OR_RELATIVE_RECEIPT_LINK')
            if not (a['label'] or a['text']):errors.append('UNNAMED_RECEIPT_LINK')
            if a['hidden']:errors.append('HIDDEN_RECEIPT_LINK')
    if not downloads:errors.append('NO_RECEIPT_OR_DOWNLOAD_LINK')
    return sorted(set(errors))

def main():
    if len(sys.argv)!=2:raise SystemExit('usage: python g01_s01_invoice_download_a11y_r31.py REDACTED_SNAPSHOT.html')
    data=Path(sys.argv[1]).read_bytes()
    if len(data)>2_000_000:raise SystemExit('FAIL OVERSIZE_HTML')
    errors=audit(data.decode('utf-8'))
    print('FAIL '+','.join(errors) if errors else 'PASS offline accessibility structure only; NOT buyer-flow proof')
    raise SystemExit(bool(errors))

if __name__=='__main__':main()
