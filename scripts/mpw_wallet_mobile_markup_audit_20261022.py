#!/usr/bin/env python3
"""Read-only checkout wallet UX and CSS source audit. Suppresses wallet/credentials/private data."""
from pathlib import Path
import os,pwd,json,re,sys
APP=Path('/home/zomorod2/Saeit-staging')
SITE=Path('/home/zomorod2/mojplaywin.com')
FILE=APP/'mpw_commerce/templates/mpw_commerce/product_checkout.html'
if pwd.getpwuid(os.getuid()).pw_name!='zomorod2' or any(p.is_symlink() for p in (APP,SITE,FILE)): raise SystemExit('wrong identity')
if "APP='/home/zomorod2/Saeit-staging'" not in (SITE/'passenger_wsgi.py').read_text('utf8','replace'):raise SystemExit('Passenger mismatch')
s=FILE.read_text('utf8','replace'); lines=s.splitlines()
patterns=('ethereum','tronWeb','tronLink','window.tron','wallet','provider','no.*wallet','signature','connect','select','break-word','overflow','max-width','viewport','@media','direction','lang=', 'font-size', 'button')
indices={i for i,l in enumerate(lines) if any(re.search(x,l,re.I) for x in patterns)}
show=set()
for i in indices:
 for j in range(max(0,i-2),min(len(lines),i+3)):show.add(j)
def safe(line):
 if re.search(r'private[_ -]?key|mnemonic|secret|password|api[_ -]?key|seed[_ -]?phrase|authorization|Bearer|T[1-9A-HJ-NP-Za-km-z]{33}',line,re.I): return '[REDACTED]'
 return line[:240]
for i in sorted(show):
 print('MPW_WALLET_SOURCE_LINE %d %s'%(i+1,safe(lines[i])))
for i in range(150,min(len(lines),280)):
 print('MPW_JS_DETAIL %d %s'%(i+1,safe(lines[i])))
print('MPW_WALLET_AUDIT='+json.dumps({'lines':len(lines),'inline_scripts':len(re.findall('<script',s,re.I)),'inline_styles':len(re.findall('<style',s,re.I)),'viewport':bool(re.search('name=[\"\\\']viewport',s,re.I)),'audit_only':True}))
