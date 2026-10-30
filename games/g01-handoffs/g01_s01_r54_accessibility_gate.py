#!/usr/bin/env python3
"""Read-only offline G->S release gate. No network, extraction, or deployment."""
import argparse, hashlib, json, sys, zipfile
from html.parser import HTMLParser

REQUIRED={'fire','pause','scope','reload','rocket','drone','interact','mapToggle'}
class Audit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids=set();self.duplicates=set();self.controls={};self.lang=None;self.viewport=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);i=a.get('id')
        if i:
            if i in self.ids:self.duplicates.add(i)
            self.ids.add(i)
        if tag=='html':self.lang=a.get('lang')
        if tag=='meta' and a.get('name')=='viewport':self.viewport=True
        if i in REQUIRED:self.controls[i]=(tag,a.get('aria-label',''))

def verify(path):
    errors=[]
    with zipfile.ZipFile(path) as z:
        names=z.namelist();name_set=set(names)
        if len(names)!=len(name_set):errors.append('DUPLICATE_ZIP_MEMBER')
        if any(n.startswith('/') or '..' in n.split('/') or chr(92) in n for n in names):errors.append('UNSAFE_PATH')
        base='ramadan-war/'
        manifest_name=base+'R54-MANIFEST-SHA256.json'
        if manifest_name not in name_set:raise ValueError('MISSING_R54_MANIFEST')
        manifest=json.loads(z.read(manifest_name))
        if manifest.get('release')!='R54' or manifest.get('factory_hold') is not True or manifest.get('moj1_live_payments') is not False:errors.append('POLICY_MANIFEST')
        expected=set(manifest.get('files',{}))
        actual={n[len(base):] for n in names if n.startswith(base) and n!=manifest_name}
        if expected!=actual:errors.append('MANIFEST_FILE_SET')
        for n,entry in manifest.get('files',{}).items():
            if n not in actual:continue
            data=z.read(base+n)
            if len(data)!=entry.get('bytes') or hashlib.sha256(data).hexdigest()!=entry.get('sha256'):errors.append('HASH_MISMATCH:'+n)
        html=Audit();html.feed(z.read(base+'index.html').decode('utf-8'))
        if html.duplicates:errors.append('DUPLICATE_HTML_IDS')
        if html.lang!='fa' or not html.viewport:errors.append('LOCALE_OR_VIEWPORT')
        for i in REQUIRED:
            tag,label=html.controls.get(i,(None,None))
            if tag!='button' or not label:errors.append('CONTROL_LABEL:'+i)
        css=z.read(base+'game.css').decode('utf-8')
        if 'touch-action:none' not in css or ':focus-visible' not in css:errors.append('TOUCH_OR_FOCUS_CSS')
        policy=z.read(base+'moj1-commerce-policy.mjs').decode('utf-8')
        for token in ['checkoutEnabled:false','ownerApproved:false','verifiedBackend:false','contractAddress:null']:
            if token not in policy:errors.append('MOJ1_HOLD:'+token)
    return errors

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('zip_file');args=ap.parse_args()
    try:issues=verify(args.zip_file)
    except Exception as exc:print('BLOCKED',type(exc).__name__,str(exc));sys.exit(2)
    if issues:print('BLOCKED',*issues,sep='\n');sys.exit(1)
    print('PASS R54 exact manifest, accessible controls, mobile focus CSS, MOJ1 HOLD (offline only)')
