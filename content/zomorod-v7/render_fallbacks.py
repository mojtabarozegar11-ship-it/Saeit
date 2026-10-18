#!/usr/bin/env python3
"""Render substantive, non-transactional, static public pages from vetted repository copy.
Never writes to a live site; runner publishes only after origin checks.
"""
from __future__ import annotations
import json
import html
import importlib.util
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('zomorod_skin',HERE/'apply_skin.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
ROUTES=('economy','market','studio','agents','contact','blog','news','weather')
ESC=html.escape

def page(slug, content):
    canonical='https://zomorodmelal.ir/'+slug+'/'
    title=str(content['title'])
    heading=str(content.get('heading',title))
    intro=str(content['lead'])
    body=str(content['body'])
    cards=[]
    for item in content['items']:
        cards.append('<article class="zm-v7-content-card"><h2>'+ESC(item['title'])+'</h2><p>'+ESC(item['text'])+'</p></article>')
    links=[]
    for item in content['links']:
        href=item.get('url','')
        if href.startswith('/') and not href.startswith('//'):
            links.append('<a href="'+ESC(href,quote=True)+'">'+ESC(item['title'])+' ←</a>')
    content_markup='\n'.join(cards)
    h='''<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#203b23">'''
    h+='<title>'+ESC(title)+' | زمرد ملل</title><meta name="description" content="'+ESC(intro[:170],quote=True)+'"><link rel="canonical" href="'+canonical+'">'
    h+='''<style>
.zm-v7-information{max-width:1250px;margin:0 auto;padding:44px 23px 90px;font-family:Tahoma,Arial,sans-serif;direction:rtl;color:#f8eed6}
.zm-v7-information h1{font-size:clamp(28px,4vw,43px);color:#f1d58e;margin:15px 0}
.zm-v7-information .lead{font-size:17px;line-height:2.1;max-width:1000px}.zm-v7-information .summary{border-inline-start:4px solid #d3b06d;padding:16px 22px;font-size:16px;line-height:2.1;background:#29492f}
.zm-v7-content-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(255px,1fr));gap:18px;margin:40px 0}
.zm-v7-content-card{border:1px solid #d4b77c;border-radius:20px;background:#28472d;padding:22px;box-shadow:0 8px 20px #0004}
.zm-v7-content-card h2{color:#f1d58e;font-size:22px}.zm-v7-content-card p{color:#e5ecd9;font-size:15px;line-height:2}
.zm-v7-info-links{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}.zm-v7-info-links a{color:#f5dca6;text-decoration:none;border:1px solid #caa35d;border-radius:15px;padding:12px 16px;background:#315038}
@media(max-width:540px){.zm-v7-information{padding:25px 14px 65px}.zm-v7-content-grid{grid-template-columns:1fr}}
</style></head><body>'''
    h+='<main id="main"><section class="zm-v7-information"><p>زمرد ملل · شرکت کشت و صنعت</p><h1>'+ESC(heading)+'</h1><p class="lead">'+ESC(intro)+'</p>'
    h+='<p class="summary">'+ESC(body)+'</p><div class="zm-v7-content-grid">'+content_markup+'</div>'
    h+='<h2>مطالعه بیشتر در زمرد ملل</h2><div class="zm-v7-info-links">'+''.join(links)+'</div>'
    if slug in ('market','agents','weather','news','contact'):
        h+='<p class="summary">این صفحه برای معرفی و آموزش است. اطلاعات قیمت، سفارش، پیش‌بینی زنده یا انجام خدمات، تنها پس از اتصال و تأیید سامانه اجرایی معتبر خواهد بود.</p>'
    h+='</section></main><footer>زمرد ملل</footer></body></html>'
    patched=mod.patch(h.encode('utf-8'),Path(slug)/'index.html')
    assert b'zm-v7-header' in patched and b'zm-v7-footer-copyright' in patched
    assert b'company-logo.webp' in patched
    return patched

def main():
    if len(sys.argv)!=3:raise SystemExit('usage: render_fallbacks.py data.json output_dir')
    data=json.loads(Path(sys.argv[1]).read_text())
    assert set(data)==set(ROUTES)
    dest=Path(sys.argv[2]).resolve()
    assert not dest.exists(),dest
    dest.mkdir(parents=True)
    for route in ROUTES:
        d=data[route]
        assert len(d['items'])>=3 and all(len(x['text'])>20 for x in d['items'])
        assert len(d['lead'])>20 and len(d['body'])>40
        source=dest/route
        source.mkdir()
        p=source/'index.html'
        p.write_bytes(page(route,d))
        print('FALLBACK_RENDER',route,len(p.read_bytes()))
    print('FALLBACK_RENDER_ALL='+str(len(ROUTES)))

if __name__=='__main__':main()