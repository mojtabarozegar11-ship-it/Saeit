#!/usr/bin/env python3
"""G-01 -> S-01 independent HTML checkout accessibility audit. NO network, no submits."""
from html.parser import HTMLParser
from pathlib import Path
import json,sys
class Audit(HTMLParser):
 def __init__(self):
  super().__init__();self.labels=set();self.controls=[];self.forms=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='label' and a.get('for'):self.labels.add(a['for'])
  if tag=='form':self.forms.append({'method':a.get('method','GET').upper(),'action':a.get('action','')})
  if tag in ('input','select','textarea') and a.get('type','').lower() not in ('hidden','submit','button','reset'):
   self.controls.append({'id':a.get('id'),'name':a.get('name'),'type':a.get('type'),'aria_label':a.get('aria-label'),'title':a.get('title')})
def audit(html):
 a=Audit();a.feed(html)
 missing=[{'id':c['id'],'name':c['name'],'type':c['type']} for c in a.controls if not(c['aria_label'] or c['title'] or (c['id'] and c['id'] in a.labels))]
 return {'control_count':len(a.controls),'unlabelled_controls':missing,'form_methods':[f['method'] for f in a.forms],'payment_submission_performed':False,'network_requests_performed':False,'pass':not missing}
if __name__=='__main__':
 if len(sys.argv)!=2:raise SystemExit('Usage: python s01_checkout_a11y_readonly_r32.py saved_checkout.html')
 result=audit(Path(sys.argv[1]).read_text(encoding='utf-8'))
 print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if result['pass'] else 2)
