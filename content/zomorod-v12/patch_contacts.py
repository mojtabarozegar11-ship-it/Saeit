#!/usr/bin/env python3
"""Add owner-confirmed company contact details to four main-domain HTML pages only.
The original HTML remains unchanged apart from one additive contact section
and Organization JSON-LD on three main corporate pages.
"""
from pathlib import Path
import sys,json,re,hashlib
PHONE='09022048691'
INTL='+989022048691'
ADDR='استان فارس، شهرستان مرودشت، خیابان قدس، کوچه ۹۲، ساختمان گل‌یخ'
NAME='شرکت کشت و صنعت زمرد ملل'
MARKER='zm-official-contact-details-20261018'
PAGES=('index.html','contact/index.html','company/index.html','about/index.html')
BLOCK='''<section id="zm-official-contact-details-20261018" class="zm-contact-verified" aria-label="اطلاعات رسمی تماس شرکت" style="direction:rtl;box-sizing:border-box;max-width:1050px;margin:38px auto;padding:22px 26px;background:#24472b;border:1px solid #d9ba78;border-radius:18px;color:#fff4dc;line-height:2;font-family:Tahoma,Arial,sans-serif"><h2 style="margin:0 0 10px;color:#f1d28c;font-size:clamp(19px,3vw,26px)">راه‌های ارتباط رسمی با شرکت کشت و صنعت زمرد ملل</h2><p style="margin:8px 0">تلفن شرکت برای ارتباطات فضای مجازی: <a href="tel:+989022048691" dir="ltr" style="color:#ffe19a;white-space:nowrap">۰۹۰۲۲۰۴۸۶۹۱</a></p><p style="margin:8px 0">نشانی دفتر شرکت: استان فارس، شهرستان مرودشت، خیابان قدس، کوچه ۹۲، ساختمان گل‌یخ</p><p style="margin:8px 0"><a href="/contact/" style="color:#ffe19a">صفحه تماس و درخواست همکاری</a></p></section>'''
ORG={'@context':'https://schema.org','@type':'Organization','@id':'https://zomorodmelal.ir/#organization','name':NAME,'alternateName':'Zomorod Mell','url':'https://zomorodmelal.ir/','telephone':INTL,'address':{'@type':'PostalAddress','addressCountry':'IR','addressRegion':'فارس','addressLocality':'مرودشت','streetAddress':'خیابان قدس، کوچه ۹۲، ساختمان گل‌یخ'},'contactPoint':{'@type':'ContactPoint','contactType':'customer service','telephone':INTL,'availableLanguage':['fa']}}
def prepare(root:Path,out:Path):
 assert root.is_dir() and not out.exists()
 out.mkdir(parents=True)
 manifest=[]
 for rel in PAGES:
  p=root/rel
  assert p.is_file() and not p.is_symlink(),rel
  old=p.read_text('utf8')
  assert MARKER not in old,'Already installed '+rel
  assert old.lower().count('</head>')==1 and len(old)>1200,rel
  assert re.search(r'<footer\b',old,re.I),'Footer not found '+rel
  new=re.sub(r'(<footer\b)',lambda m:BLOCK+m.group(1),old,count=1,flags=re.I)
  assert new.replace(BLOCK,'',1)==old
  if rel in ('index.html','company/index.html','about/index.html'):
   ld='<script type="application/ld+json" data-zm-official-contact="true">'+json.dumps(ORG,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+'</script>'
   new=new.replace('</head>',ld+'</head>',1)
   assert new.replace(ld,'',1).replace(BLOCK,'',1)==old
  assert new.count(MARKER)==1,rel
  target=out/rel;target.parent.mkdir(parents=True,exist_ok=True)
  target.write_text(new,'utf8')
  manifest.append({'path':rel,'original_sha256':hashlib.sha256(old.encode()).hexdigest(),'changed_sha256':hashlib.sha256(new.encode()).hexdigest()})
 (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
 print('OFFICIAL_CONTACT_PAGES_PREPARED='+str(len(manifest)))
if __name__=='__main__':
 assert len(sys.argv)==3
 prepare(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve())
