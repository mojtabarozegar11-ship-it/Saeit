#!/usr/bin/env python3
"""Build and validate ten Persian, source-led research reviews."""
import argparse, html, json, re, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
AUTHOR="مجتبی روزگار"
ROLE="پژوهشگر و مدیرعامل شرکت کشت و صنعت زمرد ملل"
DATE="2026-10-22"

def plain(md):
    x=re.sub(r'!\[([^]]*)\]\([^)]+\)',r'\1',md)
    x=re.sub(r'\[([^]]+)\]\((https?://[^)]+)\)',r'\1',x)
    x=re.sub(r'(?m)^#{1,6}\s*','',x)
    x=re.sub(r'(?m)^[-*+]\s*','',x)
    x=re.sub(r'(?m)^\s*>\s*','',x)
    return re.sub(r'\s+',' ',x).strip()
def words(md): return len(plain(md).split())
def inline(s):
    s=html.escape(s,quote=False)
    s=re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+)\)',r'<a href="\2" rel="nofollow noopener noreferrer">\1</a>',s)
    s=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',s)
    s=re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)',r'<em>\1</em>',s)
    return s
def markdown(md):
    out=[]; para=[]; ul=False
    def flush():
        nonlocal para
        if para:out.append('<p>'+inline(' '.join(para))+'</p>');para=[]
    for line in md.splitlines():
        s=line.strip()
        if not s:
            flush()
            if ul:out.append('</ul>');ul=False
        elif s.startswith('#'):
            flush()
            if ul:out.append('</ul>');ul=False
            n=min(len(s)-len(s.lstrip('#')),4)
            out.append(f'<h{n+1}>{inline(s[n:].strip())}</h{n+1}>')
        elif re.match(r'^[-*+]\s+',s):
            flush()
            if not ul:out.append('<ul>');ul=True
            out.append('<li>'+inline(re.sub(r'^[-*+]\s+','',s))+'</li>')
        else:
            if ul:out.append('</ul>');ul=False
            para.append(s)
    flush()
    if ul:out.append('</ul>')
    return '\n'.join(out)
def load():
    catalog=json.loads((ROOT/'catalog.json').read_text(encoding='utf8'))
    rows=catalog['articles']
    if len(rows)!=10 or len({x['slug'] for x in rows})!=10:raise ValueError('exactly ten unique articles required')
    if len({x['image'] for x in rows})!=10:raise ValueError('ten distinct images required')
    for x in rows:
        if not re.fullmatch(r'[a-z0-9-]+',x['slug']):raise ValueError('unsafe slug')
        if not x['doi'].startswith('10.'):raise ValueError('missing DOI')
        if not x['image'].startswith('/static/site/'):raise ValueError('image must use existing site asset')
        body=(ROOT/'articles'/(x['slug']+'.md')).read_text(encoding='utf8')
        n=words(body)
        if n<3000:raise ValueError(f'{x["slug"]}: {n} words, minimum 3000')
        if x['source_date'] not in body and x['source_date'] not in x['source_title']:
            raise ValueError(f'{x["slug"]}: source date absent from article')
        x['_body']=body;x['_word_count']=n
    return catalog,rows
CSS="""
<style>
*{box-sizing:border-box}body{margin:0;background:#f5f4ed;color:#24342a;font-family:Tahoma,Arial,sans-serif;line-height:2}
a{color:#286449;text-underline-offset:3px}header,main,footer{max-width:1080px;margin:auto;padding:clamp(18px,4vw,42px)}
header{padding-bottom:8px}.brand{font-size:13px;color:#6c795c}h1{font-size:clamp(27px,4.2vw,45px);line-height:1.6;color:#163c29}
h2{margin-top:42px;color:#194d32;border-bottom:1px solid #d1d7c9;padding-bottom:8px}h3{margin-top:32px;color:#31543c}
.meta{color:#536452;font-size:14px}.hero{display:grid;grid-template-columns:1.3fr 1fr;gap:24px;align-items:center}
.hero img{width:100%;height:auto;aspect-ratio:16/10;object-fit:cover;border-radius:18px;border:1px solid #d6dfd2}
figure{margin:0}figcaption{font-size:12px;color:#58665a}.evidence{background:#e9efe6;border-right:4px solid #718c57;padding:16px 20px;border-radius:8px}
.article{background:white;border:1px solid #e1e5da;border-radius:18px;padding:clamp(20px,4vw,44px);box-shadow:0 7px 25px #263b2910}
.cardgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:14px}.card{background:white;padding:19px;border:1px solid #e1e5da;border-radius:14px}
.card h2{font-size:19px;border:0;margin:0 0 8px}.small{font-size:13px;color:#657164}
@media(max-width:720px){.hero{grid-template-columns:1fr}.article{padding:20px}}@media print{body{background:white}.article,.card{box-shadow:none}}
</style>"""
def build():
    catalog,rows=load();out=ROOT/'build'
    if out.exists():shutil.rmtree(out)
    out.mkdir()
    (out/'.htaccess').write_text('PassengerEnabled off\nDirectoryIndex index.html\nOptions -Indexes\n',encoding='ascii')
    cards=[]
    for x in rows:
        title=html.escape(x['title']);desc=html.escape(x['description'],quote=True)
        slug=x['slug'];url=f'https://zomorodmelal.ir/research/library/{slug}/'
        body=markdown(x['_body']);image=html.escape(x['image'],quote=True)
        alt=html.escape(x['alt'],quote=True);credits=html.escape(x['image_credit'])
        image_source=html.escape(x['image_source'],quote=True)
        schema={"@context":"https://schema.org","@type":"Article","headline":x['title'],"description":x['description'],"datePublished":DATE,"dateModified":DATE,"author":{"@type":"Person","name":AUTHOR},"publisher":{"@type":"Organization","name":"شرکت کشت و صنعت زمرد ملل"},"mainEntityOfPage":url,"image":"https://zomorodmelal.ir"+x['image']}
        doc=f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | زمرد ملل</title><meta name="description" content="{desc}"><link rel="canonical" href="{url}">
<meta property="og:type" content="article"><meta property="og:title" content="{title}"><meta property="og:description" content="{desc}"><meta property="og:url" content="{url}"><meta property="og:image" content="https://zomorodmelal.ir{image}">
<meta name="author" content="{AUTHOR}"><meta name="article:published_time" content="{DATE}"><script type="application/ld+json">{json.dumps(schema,ensure_ascii=False)}</script>{CSS}</head>
<body><header><div class="brand">زمرد ملل · دانش و تحقیق کشاورزی</div><p><a href="/research/library/">بازگشت به کتابخانه پژوهش</a></p></header><main><div class="article">
<div class="hero"><div><h1>{title}</h1><p class="meta">نویسنده: {AUTHOR} · {ROLE} · انتشار: ۳۰ مهر ۱۴۰۵</p><p class="evidence">نوع مطلب: مرور تحلیلی پژوهش منتشرشده؛ این صفحه گزارش آزمایش مستقل یا نتیجه اجراشده در شرکت نیست.</p></div>
<figure><img src="{image}" alt="{alt}" loading="lazy" decoding="async"><figcaption>{alt} · تصویر آرشیوی: <a href="{image_source}" rel="noopener noreferrer">{credits}</a></figcaption></figure></div>
<p class="meta">پژوهش مبنا: <a href="https://doi.org/{html.escape(x['doi'])}" rel="noopener noreferrer">{html.escape(x['source_title'])}</a> · {html.escape(x['journal'])} · تاریخ انتشار: {html.escape(x['source_date'])}</p>{body}
<hr><p class="small">این تحلیل ثانویه بر اساس منبع علمی معرفی‌شده تهیه شده است. نتیجه یک پژوهش به‌تنهایی توصیه اجرایی عمومی یا تضمین عملکرد محصول نیست. پیش از اقدام، شرایط محلی، ایمنی، هزینه، مجوز و آزمون مستقل را بررسی کنید.</p></div></main>
<footer><p><a href="/research/">پژوهش و توسعه</a> · <a href="/agriculture/">کشاورزی</a> · <a href="/contact/">تماس با زمرد ملل</a></p></footer></body></html>'''
        d=out/slug;d.mkdir();(d/'index.html').write_text(doc,encoding='utf8')
        cards.append(f'<article class="card"><h2><a href="/research/library/{slug}/">{title}</a></h2><p>{html.escape(x["description"])}</p><p class="small">{html.escape(x["journal"])} · {html.escape(x["source_date"])} · {x["_word_count"]:,} واژه</p></article>')
    idx=f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>کتابخانه ده مرور پژوهشی کشاورزی | زمرد ملل</title><meta name="description" content="ده مرور تحلیلی پژوهش‌های تازه در ژنومیک، کشاورزی هوشمند، گلخانه، غذای کارکردی، طیور، آبزی‌پروری و اقتصاد کشاورزی."><link rel="canonical" href="https://zomorodmelal.ir/research/library/">{CSS}</head>
<body><header><div class="brand">زمرد ملل · کتابخانه علمی کشاورزی</div><p><a href="/research/">پژوهش و توسعه</a></p><h1>ده مرور تحلیلی پژوهش‌های کاربردی کشاورزی</h1><p>هر مرور، یافته پژوهش داوری‌شده، کیفیت شواهد، بازتولیدپذیری، محدودیت و مسیر آزمون عملی را توضیح می‌دهد.</p><p class="evidence">نویسنده: {AUTHOR}، {ROLE}. این مطالب مرور پژوهش‌های منتشرشده‌اند و آزمایش اختصاصی شرکت را ادعا نمی‌کنند.</p></header><main><div class="cardgrid">{''.join(cards)}</div></main><footer><a href="/research/">بخش پژوهش و توسعه</a></footer></body></html>'''
    (out/'index.html').write_text(idx,encoding='utf8')
    print('ARTICLES=10 MIN_WORDS='+str(min(x['_word_count'] for x in rows)))
    return out
def patch_index(source):
    marker='zm-science-library-20261022'
    if marker in source:raise ValueError('marker already present')
    if source.lower().count('</main>')!=1:raise ValueError('unexpected research page')
    snippet=f'''<!-- {marker} --><section id="{marker}" style="direction:rtl;margin:32px auto;max-width:1100px;padding:24px;background:#e9efe6;border:2px solid #859a62;border-radius:18px;font-family:Tahoma,Arial,sans-serif"><h2>کتابخانه مرورهای پژوهشی تازه</h2><p>ده تحلیل مستند از ژنومیک، هوش مصنوعی زیستی، گلخانه، غذاهای کارکردی، دام و طیور، آبزی‌پروری و اقتصاد کشاورزی؛ همراه با محدودیت شواهد و مسیر آزمون عملی.</p><a href="/research/library/">ورود به کتابخانه ده مرور علمی ←</a></section>'''
    result=source.replace('</main>',snippet+'</main>',1)
    if result.replace(snippet,'',1)!=source:raise ValueError('non-additive page change')
    return result
def main():
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');p.add_argument('--check',action='store_true');p.add_argument('--patch-index')
    a=p.parse_args();_,rows=load()
    if a.build or a.check:build()
    if a.patch_index:
        f=Path(a.patch_index);src=f.read_text(encoding='utf8');(Path(str(f)+'.patched')).write_text(patch_index(src),encoding='utf8')
    print('SOURCE_GROUNDED_REVIEWS=10')
if __name__=='__main__':main()
