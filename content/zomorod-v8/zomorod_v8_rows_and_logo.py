#!/usr/bin/env python3
"""Site-root-only V8 patch: single official company logo; nine new carousels.

Requires the V6+V7 homepage. Does not modify other paths or databases.
Does not create live routes or pretend the topic illustrations are photographs.
Caller must back up and verify the original file before writing.
"""
import argparse
import base64
import hashlib
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

VERSION='zm-v8-26-rows-single-official-logo-20261018'
OFFICIAL='/static/site/zomorod-v7/company-logo.webp'
NEW_CATEGORIES=[
 ('ZM-R18','صنایع غذایی','food-industries','industrial-food','فرآوری مواد غذایی، توسعه محصول و کنترل کیفیت با توجه به مقررات و ایمنی مصرف‌کننده.', '/industry/', [
 ('طراحی محصول غذایی','food-product-design'),('تولید لبنیات','dairy-production'),('کارخانه آرد','flour-milling'),('صنایع نان و شیرینی','bakery-industry'),('کنسروسازی','canning'),('صنایع نوشیدنی','beverage-industry'),('فرآوری گوشت','meat-processing'),('فرآوری آبزیان','seafood-processing'),('خشکبار و آجیل','nuts-processing'),('تولید روغن خوراکی','edible-oils'),('صنایع شکلات','chocolate-production'),('فرآوری میوه','fruit-processing'),('سبزیجات آماده','vegetable-processing'),('انجماد سریع مواد غذایی','iqf-food'),('زنجیره سرد غذایی','food-cold-chain'),('آزمایشگاه ایمنی غذا','food-safety-lab'),('طراحی بسته‌بندی غذایی','food-packaging'),('کنترل کیفیت و ردیابی','food-traceability'),('فرمولاسیون محصولات','food-formulation'),('اقتصاد و بازار غذا','food-markets')]),
 ('ZM-R19','کارخانجات','factories','factories','طراحی، راه‌اندازی، بهره‌وری، نگهداری و ارزیابی اقتصادی کارخانه‌ها و خطوط تولید.', '/industry/', [
 ('مطالعات احداث کارخانه','plant-feasibility'),('طراحی چیدمان صنعتی','plant-layout'),('تجهیز خطوط تولید','production-lines'),('اتوماسیون کارخانه','factory-automation'),('کنترل فرایند','process-control'),('مدیریت تولید','manufacturing-management'),('برنامه‌ریزی ظرفیت','capacity-planning'),('تعمیرات و نگهداری','industrial-maintenance'),('تأمین قطعات صنعتی','industrial-parts'),('انرژی کارخانه','factory-energy'),('ایمنی و بهداشت صنعتی','industrial-hse'),('کنترل کیفیت صنعتی','industrial-quality'),('مدیریت انبار صنعتی','factory-warehousing'),('مدیریت زنجیره تأمین','supply-chain'),('صنایع بسته‌بندی','packaging-plants'),('صنایع فلزی','metal-manufacturing'),('صنایع پلیمری','polymer-manufacturing'),('ماشین‌سازی','machine-building'),('حمل‌ونقل کارخانه','industrial-logistics'),('بازسازی و نوسازی خطوط','plant-modernization')]),
 ('ZM-R20','عمران و صنعت ساختمان','construction','construction','دانش و خدمات فنی ساختمان، زیرساخت، طراحی، نظارت، تعمیر و مدیریت اجرای پروژه.', '/services/', [
 ('ساختمان‌سازی','building-construction'),('طراحی معماری','architecture-design'),('طراحی سازه','structural-design'),('پیمانکاری عمومی','general-contracting'),('بازسازی ساختمان','building-renovation'),('تأسیسات مکانیکی','mechanical-systems'),('تأسیسات برقی','electrical-systems'),('مدیریت پروژه عمرانی','construction-pm'),('متره و برآورد','quantity-surveying'),('کنترل هزینه پروژه','construction-cost-control'),('راه و محوطه‌سازی','road-landscaping'),('آب‌بندی و عایق','waterproofing'),('نما و مصالح','facades-materials'),('ساختمان هوشمند','smart-buildings'),('بهینه‌سازی انرژی','building-efficiency'),('نقشه‌برداری','surveying'),('ایمنی کارگاه','site-safety'),('کنترل کیفیت ساخت','construction-quality'),('نگهداری ساختمان','facility-maintenance'),('تحویل و مستندسازی','construction-handover')]),
 ('ZM-R21','املاک و مستغلات','real-estate','real-estate','شناخت بازار ملک، مطالعات سرمایه‌گذاری، ارزیابی و مدیریت دارایی‌های ملکی.', '/services/', [
 ('کارشناسی ارزش ملک','real-estate-valuation'),('مطالعات بازار مسکن','housing-market'),('مدیریت دارایی ملکی','property-asset-management'),('املاک مسکونی','residential-property'),('املاک تجاری','commercial-property'),('املاک اداری','office-property'),('املاک صنعتی','industrial-property'),('زمین و کاربری','land-use'),('ساخت و توسعه ملک','property-development'),('تحلیل بازده سرمایه','property-roi'),('قراردادهای ملکی','property-contracts'),('تحلیل اجاره','rental-analysis'),('مدیریت ساختمان','property-management'),('بازسازی برای فروش','renovate-to-sell'),('مشارکت در ساخت','joint-development'),('مجوزها و مقررات','building-permits'),('بازاریابی املاک','property-marketing'),('سرمایه‌گذاری ملکی','property-investment'),('ارزیابی ریسک ملک','property-risk'),('داده و نقشه املاک','property-gis')]),
 ('ZM-R22','طلا، جواهر و گوهرسنگ','gold-jewelry','jewelry','شناخت فلزات گران‌بها، گوهرسنگ، طراحی، ساخت، تجارت و مدیریت تخصصی کسب‌وکار جواهر.', '/tala/', [
 ('شناخت طلای خام','raw-gold'),('طلای آب‌شده','melted-gold'),('سکه‌های طلا','gold-coins'),('نقره و آلیاژها','silver-alloys'),('گوهرشناسی','gemology'),('الماس','diamonds'),('زمرد و یاقوت','emerald-ruby'),('طراحی جواهر','jewelry-design'),('ساخت طلا و جواهر','jewelry-manufacturing'),('عیارسنجی','gold-assaying'),('ارزش‌گذاری سنگ','gem-valuation'),('قیمت‌گذاری جواهر','jewelry-pricing'),('حسابداری طلافروشی','gold-accounting'),('مدیریت کارگاه طلا','jewelry-workshop'),('تعمیرات جواهر','jewelry-repair'),('خرید و فروش مجاز','regulated-gold-trade'),('بازار فلزات گران‌بها','precious-metal-markets'),('عکاسی محصول جواهر','jewelry-photography'),('اصالت‌سنجی','jewelry-authentication'),('ایمنی و نگهداری','gold-security')]),
 ('ZM-R23','فرش دستباف و صنایع دستی','handmade-carpets','carpets','فرش‌شناسی، بافت، مرمت، اصالت، ارزش‌گذاری و بازار صنایع دستی با رویکرد تخصصی.', '/services/', [
 ('فرش دستباف ایرانی','persian-handmade-carpet'),('شناخت گره و بافت','knots-and-weaves'),('نقشه و طرح فرش','carpet-patterns'),('رنگرزی طبیعی','natural-dyes'),('پشم و ابریشم','wool-silk'),('تراکم و رج‌شمار','carpet-knot-density'),('قالیچه و گلیم','kilims-rugs'),('فرش عشایری','tribal-carpets'),('فرش شهری','city-carpets'),('فرش ابریشم','silk-carpets'),('مرمت فرش','carpet-restoration'),('شست‌وشوی تخصصی','carpet-care'),('تشخیص اصالت','carpet-authenticity'),('ارزیابی قیمت','carpet-appraisal'),('تجارت فرش','carpet-trade'),('کلکسیون و نگهداری','carpet-collection'),('صنایع چوبی سنتی','woodcraft'),('سفال و سرامیک دست‌ساز','ceramics'),('پارچه‌های سنتی','traditional-textiles'),('بازاریابی صنایع دستی','handicraft-marketing')]),
 ('ZM-R24','رستوران، آشپزی و مهمان‌داری','hospitality','hospitality','آشپزی تخصصی، خدمات رستورانی، کنترل کیفیت غذا و مدیریت تجربه مشتری.', '/services/', [
 ('توسعه منوی رستوران','menu-development'),('آشپزی حرفه‌ای','professional-cooking'),('غذاهای ایرانی','iranian-cuisine'),('غذاهای بین‌المللی','international-cuisine'),('شیرینی و قنادی','pastry-confectionery'),('کافه و نوشیدنی','cafe-beverages'),('مدیریت آشپزخانه','kitchen-management'),('ایمنی مواد غذایی','kitchen-food-safety'),('کنترل بهای غذا','food-cost-control'),('تأمین مواد اولیه','restaurant-procurement'),('طراحی فضای رستوران','restaurant-design'),('بازاریابی رستوران','restaurant-marketing'),('پذیرایی و تشریفات','catering'),('برگزاری ضیافت','banquet-planning'),('آموزش کارکنان','hospitality-staff-training'),('کنترل کیفیت خدمات','hospitality-quality'),('تجربه مشتری','guest-experience'),('فروش و سفارش آنلاین','restaurant-online-ordering'),('بسته‌بندی غذای آماده','takeaway-packaging'),('مدیریت سودآوری','restaurant-profitability')]),
 ('ZM-R25','فناوری اطلاعات و خدمات دیجیتال','digital-services','digital','تحلیل، طراحی و تولید محصولات دیجیتال و سامانه‌های هوشمند برای کسب‌وکارها.', '/services/', [
 ('طراحی وب‌سایت','website-design'),('توسعه نرم‌افزار','software-development'),('اپلیکیشن موبایل','mobile-app-development'),('تجربه کاربری','ux-design'),('هوش مصنوعی کاربردی','applied-ai'),('اتوماسیون کسب‌وکار','business-automation'),('تحلیل داده','data-analytics'),('زیرساخت ابری','cloud-infrastructure'),('امنیت سایبری','cybersecurity'),('تجارت الکترونیک','ecommerce'),('ساخت محصولات دیجیتال','digital-products'),('بازی‌سازی','game-development'),('انیمیشن دیجیتال','digital-animation'),('تولید محتوای حرفه‌ای','professional-content'),('بهینه‌سازی موتور جست‌وجو','seo'),('مدیریت پروژه فناوری','tech-project-management'),('طراحی رابط برنامه‌نویسی','api-engineering'),('پشتیبان‌گیری و بازیابی','backup-recovery'),('آموزش فناوری','digital-training'),('مدیریت کیفیت نرم‌افزار','software-qa')]),
 ('ZM-R26','گردشگری، رویدادها و خدمات حرفه‌ای','tourism-events','tourism','مطالعات گردشگری، برنامه‌ریزی رویداد، خدمات حرفه‌ای و همکاری‌های غیرکشاورزی.', '/services/', [
 ('برنامه‌ریزی گردشگری','tourism-planning'),('گردشگری فرهنگی','cultural-tourism'),('گردشگری طبیعت','nature-tourism'),('توسعه مقصد','destination-development'),('هتلداری','hotel-management'),('خدمات اقامتی','accommodation'),('راهنمای سفر','travel-guidance'),('گردشگری شهری','urban-tourism'),('اقتصاد گردشگری','tourism-economics'),('گردشگری مسئولانه','responsible-tourism'),('طراحی نمایشگاه','exhibition-design'),('مدیریت همایش','conference-management'),('برنامه‌ریزی رویداد','event-planning'),('رویدادهای شرکتی','corporate-events'),('روابط عمومی','public-relations'),('برندسازی حرفه‌ای','professional-branding'),('خدمات پژوهشی','research-services'),('خدمات ترجمه تخصصی','technical-translation'),('مدیریت کسب‌وکار','business-advisory'),('همکاری بین‌المللی','international-collaboration')]),
]
assert len(NEW_CATEGORIES)==9
assert all(len(p[6])==20 for p in NEW_CATEGORIES)

def unique_image(row,card,kind):
    """Distinct, non-photographic vector illustrations, without photo claims."""
    label=escape(card[0]); slug=card[1]
    seed=int(hashlib.sha256(f'{row}:{slug}'.encode()).hexdigest()[:8],16)
    n=seed%360; a=65+seed%190; b=80+(seed//3)%160
    c1=f'hsl({n} 29% 31%)';c2=f'hsl({(n+28)%360} 35% 14%)'
    x=125+seed%245; yy=78+seed%75
    # Different motif families provide recognizable architectural silhouettes.
    motifs={
     'industrial-food':f'<path d="M68 260 V158 l55 -26 49 26 59 -29 47 26 55 -25 61 31 V260Z" fill="#f3e2c3" opacity=".55"/><g fill="#204728" opacity=".6"><rect x="112" y="167" width="36" height="64" rx="5"/><rect x="185" y="167" width="36" height="64" rx="5"/><rect x="277" y="166" width="36" height="64" rx="5"/></g>',
     'factories':f'<path d="M55 268V190l80 -49v47l81 -47v47l80 -47v127Z" fill="#f3e2c3" opacity=".66"/><rect x="332" y="106" width="30" height="164" fill="#d5b873"/><rect x="378" y="148" width="31" height="120" fill="#d5b873"/><g fill="#315a48"><rect x="97" y="220" width="29" height="27"/><rect x="179" y="220" width="29" height="27"/></g>',
     'construction':f'<g fill="#e6d4ae"><rect x="63" y="150" width="128" height="137" rx="3"/><rect x="204" y="114" width="130" height="171" rx="3"/><rect x="350" y="160" width="127" height="128" rx="3"/></g><path d="M225 114V57M165 57H350M168 57l-21 21" stroke="#f8d67b" stroke-width="10"/><g fill="#345747">'+''.join(f'<rect x="{p}" y="{q}" width="17" height="23"/>' for p in (84,128,228,280,372,420) for q in (175,222))+'</g>',
     'real-estate':f'<path d="M47 194l112 -100 109 100v100H47Z" fill="#f1dfbd"/><path d="M242 164l120 -104 121 104v130H242Z" fill="#d5c297"/><path d="M315 186h56v108h-56Z" fill="#3a694e"/><rect x="87" y="202" width="51" height="41" fill="#3a694e"/>',
     'jewelry':f'<path d="M278 76l114 64 -114 133 -114 -133Z" fill="#cfecdf" opacity=".92" stroke="#ffeab2" stroke-width="10"/><path d="M164 140h228M278 76l-47 64 47 133 47 -133  -47 -64" fill="none" stroke="#42805e" stroke-width="5"/><circle cx="413" cy="245" r="32" fill="none" stroke="#ffdb76" stroke-width="13"/>',
     'carpets':f'<rect x="89" y="44" width="376" height="256" rx="12" fill="#ead6a2"/><rect x="118" y="65" width="318" height="216" rx="6" fill="#244c43" stroke="#bd854c" stroke-width="13"/><path d="M278 89l85 87-85 83-85-83Z" fill="#a76e4b" stroke="#f8d284" stroke-width="12"/><circle cx="278" cy="177" r="37" fill="#e4c47d"/>',
     'hospitality':f'<ellipse cx="272" cy="236" rx="167" ry="42" fill="#f3e2c5"/><path d="M151 217C146 134 205 99 278 102s126 36 129 115Z" fill="#ffe0a1"/><circle cx="279" cy="104" r="14" fill="#f8d56f"/><rect x="122" y="223" width="306" height="14" rx="7" fill="#b88147"/><path d="M105 110v100M94 143h24M447 111v100" stroke="#efe2c3" stroke-width="10"/>',
     'digital':f'<rect x="100" y="73" width="354" height="203" rx="17" fill="#d3e5d2" stroke="#ffe6a0" stroke-width="10"/><rect x="118" y="94" width="318" height="151" rx="6" fill="#1c513c"/><path d="M227 145l-33 27 33 27M332 145l33 27-33 27M306 127l-47 91" fill="none" stroke="#eacf87" stroke-width="10" stroke-linecap="round"/>',
     'tourism':f'<path d="M59 268Q128 145 221 215T505 164V310H59Z" fill="#53896a"/><path d="M34 271Q139 224 257 261T528 240" stroke="#e5cc8a" stroke-width="18" fill="none"/><circle cx="396" cy="84" r="35" fill="#f7d47a"/><path d="M155 271l66-112 70 112" fill="#e6dcc6" stroke="#c6af7b" stroke-width="6"/>',
    }
    motif=motifs[kind]
    # Unique decorative markings by card; variation in placement and hue, no text/watermark.
    accents=''.join(f'<circle cx="{(seed//(k+1)+k*59)%530+10}" cy="{(seed//(k+4)+k*23)%230+25}" r="{3+((seed//(k+3))%8)}" fill="#fbe6ad" opacity=".35"/>' for k in range(6))
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 320" role="img" aria-label="تصویرسازی موضوع {label}"><defs><linearGradient id="g" x2=".8" y2="1"><stop stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient><radialGradient id="a"><stop stop-color="#f0d88b" stop-opacity=".7"/><stop offset="1" stop-color="#f0d88b" stop-opacity="0"/></radialGradient></defs><rect width="560" height="320" fill="url(#g)"/><circle cx="{x}" cy="{yy}" r="166" fill="url(#a)"/><path d="M0 286Q140 {200+seed%35} 280 257T560 245V320H0Z" fill="#173a29" opacity=".8"/>{motif}{accents}<path d="M15 305h530" stroke="#e3b35f" opacity=".7" stroke-width="3"/></svg>'
    return 'data:image/svg+xml;base64,'+base64.b64encode(svg.encode()).decode('ascii')

def new_row(p):
    rid,title,slug,kind,desc,dest,names=p
    num=int(rid[-2:])
    return dict(id=rid,index=num,title=title,slug=slug,icon='layers',target=f'orbit-{num:02}',description=desc,sectorPath=dest,orbital=False,cards=[dict(id=f'{rid}-C{i:02}',title=name,slug=short,image=unique_image(rid,(name,short),kind),imageStatus='unique_vector_illustration',canonicalUrl=None) for i,(name,short) in enumerate(names,1)])

def patch(source:str)->str:
    if VERSION in source:raise ValueError('Already V8; refuse duplicate modification')
    match=re.search(r'(window\.ZOMOROD_ORBIT_DATA=)(\{.*?\})(;</script>)',source,re.S)
    if not match:raise ValueError('Missing complete V6 manifest')
    data=json.loads(match.group(2))
    originals=data['rows']
    if len(originals)!=17 or any(len(r['cards'])!=20 for r in originals):raise ValueError('Must retain 17 original rows and 340 cards')
    expected=[f'ZM-R{i:02}' for i in range(1,18)]
    if [r['id'] for r in originals]!=expected:raise ValueError('Existing row identities changed unexpectedly')
    new=[new_row(x) for x in NEW_CATEGORIES]
    data['rows']=originals[:11]+new[:2]+originals[11:15]+new[2:]+originals[15:]
    data['version']='homepage-v8-26-shelves'
    data['note']='17 original orbital categories remain, 26 specialist shelves with 20 uniquely illustrated topics each. Informational category placeholders are not independent published pages.'
    output=source[:match.start(2)]+json.dumps(data,ensure_ascii=False,separators=(',',':'))+source[match.end(2):]
    begin="if(!config || config.rows?.length!==17 || config.rows.some(r=>r.cards?.length!==20))throw Error('17 × 20 content manifest required');"
    desired="if(!config || config.rows?.length!==26 || config.rows.some(r=>r.cards?.length!==20) || config.rows.filter(r=>r.index<=17).length!==17)throw Error('26 × 20 content manifest required');"
    if output.count(begin)!=1:raise ValueError('Cannot locate JS original counts')
    output=output.replace(begin,desired)
    searches={
      'config.rows.forEach((row,index)=>{':"config.rows.filter(row=>row.index<=17).forEach((row,index)=>{",
      'const dest=i===16?':"const dest=row.index===17?",
      'if(i===16)a.setAttribute(':"if(row.index===17)a.setAttribute(",
      "config.rows.find(r=>r.slug===parts[1]&&r.index<17)":"config.rows.find(r=>r.slug===parts[1]&&r.index!==17)",
      'const row=config.rows[16],topic=row.cards.find(c=>c.slug===parts[1]);':"const row=config.rows.find(r=>r.index===17),topic=row?.cards.find(c=>c.slug===parts[1]);",
      "officialSectorPaths[row.index-1]":"(row.sectorPath||officialSectorPaths[row.index-1]||'/services/')",
      "  drawSatellites();\n  const nodes=config.rows.map(buildShelf);": "  drawSatellites();\n  config.rows.filter(row=>row.index>17).forEach(row=>{if(jumpList)jumpList.append(el('a',{className:'jump-chip',href:'#'+row.target},row.title));});\n  const nodes=config.rows.map(buildShelf);",
    }
    for old,repl in searches.items():
        n=output.count(old)
        if n!=1:raise ValueError(f'Expected one JS replacement for {old!r}, found {n}')
        output=output.replace(old,repl)
    # V7 injector placed an extra floating official logo above the original obsolete logo.
    extralogo=r'<a class="zm-v7-home-logo"\s+href="/company/"[^>]*><img[^>]*></a>'
    if len(re.findall(extralogo,output,flags=re.I))!=1:
        raise ValueError('Expected one V7 duplicate floating logo; no changes made')
    output=re.sub(extralogo,'',output,count=1,flags=re.I)
    # Keep header's one logo slot, use the approved official logo instead of legacy mark.
    oldmark=r'(<span class="identity-mark"[^>]*>)\s*<img\b[^>]*>\s*(</span>)'
    if len(re.findall(oldmark,output,flags=re.I))!=1:raise ValueError('Expected one old company logo slot')
    output=re.sub(oldmark,lambda m: m.group(1)+f'<img src="{OFFICIAL}" alt="لوگوی رسمی شرکت کشت و صنعت زمرد ملل" width="76" height="76" loading="eager">'+m.group(2),output,count=1,flags=re.I)
    # Header retains the two existing lines of English branding unchanged; only replaces image.
    output=output.replace('</body>',f'<!-- {VERSION} --></body>',1)
    return output

def verify(original:str,updated:str):
    if not updated.strip().endswith('</html>'):raise ValueError('Missing document close')
    d=json.loads(re.search(r'window\.ZOMOROD_ORBIT_DATA=(\{.*?\});</script>',updated,re.S).group(1))
    assert len(d['rows'])==26
    assert sum(len(r['cards']) for r in d['rows'])==520
    assert sum(r['index']<=17 for r in d['rows'])==17
    assert [r['title'] for r in d['rows'][11:13]]==['صنایع غذایی','کارخانجات']
    assert d['rows'][16]['title']=='خدمات، پروژه‌ها و بازرگانی'
    assert len([r for r in d['rows'][17:24] if r['index']>17])==7
    assert d['rows'][-1]['title']=='اخبار شرکت'
    assert 'zm-v7-home-logo"' not in updated
    assert updated.count('src="'+OFFICIAL+'"')==1
    assert 'footer-copyright' in updated and 'zm-unified-v7-20261018' in updated
    allids=[r['id'] for r in d['rows']]
    assert len(allids)==len(set(allids))
    alltargets=[r['target'] for r in d['rows']]
    assert len(alltargets)==len(set(alltargets))
    imgs=[x['image'] for r in d['rows'] for x in r['cards'] if r['index']>17]
    assert len(imgs)==180 and len(set(imgs))==180
    for img in imgs:
        assert img.startswith('data:image/svg+xml;base64,')
        assert base64.b64decode(img.split(',',1)[1]).startswith(b'<svg')
    print('V8_VALIDATED: 26 rows, 520 topics, 17 orbit satellites, 180 unique new illustrations')
    print('V8_ORDER:', ' | '.join(r['title'] for r in d['rows']))
    print('V8_OFFICIAL_LOGO_ONLY=one header logo, old floating duplicate removed')

def main():
    a=argparse.ArgumentParser();a.add_argument('file',type=Path);a.add_argument('--write',action='store_true');a.add_argument('--output',type=Path)
    opt=a.parse_args();s=opt.file.read_text(encoding='utf-8');t=patch(s);verify(s,t)
    if opt.output:opt.output.write_text(t,encoding='utf8');print('PREVIEW_SAVED='+str(opt.output))
    if opt.write:
        tmp=opt.file.with_name('.index.html.v8-next')
        if tmp.exists():raise RuntimeError('Refuse preexisting next file')
        import os
        with tmp.open('x',encoding='utf8') as f:f.write(t);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,opt.file.stat().st_mode & 0o777)
        os.replace(tmp,opt.file)
        print('V8_ROOT_PUBLISHED=updated atomically')

if __name__=='__main__':main()