#!/usr/bin/env python3
import urllib.request, re, json, hashlib
url='https://zomorodmelal.ir/?__zm_game_inventory=20261019'
with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ZomorodFarmGameShelfReadOnly/1','Cache-Control':'no-cache'}),timeout=35) as r:
 raw=r.read(3_000_000)
 print('HTTP',r.status,'BYTES',len(raw),'SHA256',hashlib.sha256(raw).hexdigest())
 assert r.status==200
text=raw.decode('utf-8','replace')
print('VERSION_MARKERS',[x for x in ['zm-unified-v7-20261018','zomorod-v9','ZOMOROD_ORBIT_DATA','zm-priority-p0p3','ZM-R25'] if x in text])
m=re.search(r'window\.ZOMOROD_ORBIT_DATA=(\{.*?\});</script>',text,re.S)
print('MANIFEST_MATCH',bool(m))
if not m:
 for t in ['فناوری اطلاعات','بازی‌سازی','game-development']:
  i=text.find(t);print('TERM',t,'OFFSET',i,'CONTEXT',text[max(0,i-330):i+850])
 raise SystemExit(3)
data=json.loads(m.group(1))
rows=data['rows'];print('ROWS',len(rows),'CARDS',sum(len(r.get('cards',[])) for r in rows))
for row in rows:
 if any(term in row.get('title','') for term in ['فناوری','اطلاعات']) or row.get('id')=='ZM-R25':
  print('TARGET_ROW',row['id'],row['title'],'CARDCOUNT',len(row['cards']))
  print('TARGET_METADATA',{k:v for k,v in row.items() if k!='cards'})
  for i,c in enumerate(row['cards']):
   print('CARD',i, json.dumps(c,ensure_ascii=False)[:500])
  print('TARGET_ROW_CHECKSUM',hashlib.sha256(json.dumps(row,ensure_ascii=False,sort_keys=True).encode()).hexdigest())
print('BUILD_FUNCTION_SAMPLES')
for phrase in ["function buildShelf","function buildCard","const buildShelf","row.cards.map","card.href","card.url","card.slug","card.canonicalUrl"]:
 i=text.find(phrase)
 print('JS',phrase,'FOUND',i,'CONTEXT',text[max(0,i-160):i+520].replace('\n',' ')[:650])
