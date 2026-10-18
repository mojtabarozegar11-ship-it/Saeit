#!/usr/bin/env python3
"""Add one unique scientific editorial and Wikimedia photo to 10 *existing* pages.

The work is strictly additive. The original bytes must be exactly recoverable
by removing the inserted section. Avoids modification of current pictures,
navigation, products, payment gateways, Passenger, and original SEO fields.
"""
import argparse,hashlib,html,json,re
from pathlib import Path

MARK='zm-ten-unique-research-photo-editorials-20261018'
IMAGE_ROOT='/static/site/zomorod-ten-editorials/'
def esc(s):return html.escape(str(s),quote=True)
def make_fragment(p,asset):
    if p["id"]!=asset["id"]:
        raise ValueError("Mismatched photograph")
    title=esc(p["title"])
    src=esc(asset["url"])
    alt=esc(p["caption"])
    page=esc(asset["source"])
    credit=esc(asset["credit"])
    dims=asset["dimensions"]
    intro=(f'این بخش، روش‌شناسی تخصصی «{p["title"]}» را با معیارهای قابل سنجش، '
           'محدودیت استنتاج و اصول انتشار مسئولانه توضیح می‌دهد. تصاویر آرشیوی '
           'صرفاً برای آموزش استفاده شده‌اند و مستند فعالیت‌های شرکت نیستند.')
    sections=''.join(f'<article class="zm-ten-article"><h3>{esc(n)}</h3><p>{esc(t)}</p></article>' for n,t in p['sections'])
    return f'''<!-- {MARK} -->
<section class="zm-ten-editorial" aria-label="{title}" data-verified-image="{esc(asset["sha256"])}">
<style>
.zm-ten-editorial{{direction:rtl;max-width:1200px;margin:40px auto;padding:clamp(18px,3vw,34px);
background:linear-gradient(140deg,#0d2f24,#1e4933);color:#f7ead0;border:1px solid #e3bd7677;border-radius:24px;
font-family:Tahoma,Arial,sans-serif;line-height:2;box-shadow:0 14px 38px #09181060}}
.zm-ten-editorial *{{box-sizing:border-box}}.zm-ten-editorial h2,.zm-ten-editorial h3{{color:#f2d28f;line-height:1.55}}
.zm-ten-editorial h2{{font-size:clamp(22px,3vw,35px);margin:0 0 13px}}
.zm-ten-editorial h3{{font-size:19px;margin:0 0 10px}}
.zm-ten-editorial p{{color:#f1e9d7;line-height:2.1;margin:0 0 13px;font-size:clamp(14px,1.3vw,17px)}}
.zm-ten-editorial .zm-ten-hero{{display:grid;grid-template-columns:minmax(0,1fr) minmax(230px,.92fr);gap:25px;align-items:center}}
.zm-ten-editorial figure{{margin:0;min-width:0}}.zm-ten-editorial figure img{{display:block;width:100%;height:auto;aspect-ratio:16/10;
object-fit:cover;border-radius:16px;border:2px solid #dfc486;box-shadow:0 9px 24px #06120f66}}
.zm-ten-editorial figcaption{{font-size:12px;line-height:1.9;padding:10px 4px 0;color:#dcd3bd}}
.zm-ten-editorial .zm-ten-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin:24px 0}}
.zm-ten-editorial .zm-ten-article{{padding:20px;background:#28553c85;border:1px solid #a8996880;border-radius:16px}}
.zm-ten-editorial a{{color:#f7dc9f;text-decoration:underline;text-underline-offset:3px}}
.zm-ten-editorial .zm-ten-verified{{border-right:3px solid #e1bd76;padding:8px 16px;color:#ead8b4;font-size:13px}}
@media(max-width:750px){{.zm-ten-editorial .zm-ten-hero{{grid-template-columns:1fr}}}}
@media(prefers-reduced-motion:reduce){{.zm-ten-editorial *{{scroll-behavior:auto!important;animation:none!important}}}}
</style>
<div class="zm-ten-hero"><div>
<p style="font-size:12px;color:#dfc383">پژوهش و معرفی تخصصی | ZOMOROD MELAL</p>
<h2>{title}</h2><p>{esc(intro)}</p>
</div>
<figure><img src="{src}" alt="{alt}" width="{dims[0]}" height="{dims[1]}" loading="lazy" decoding="async">
<figcaption>{esc(p["caption"])}. منبع: <a href="{page}" rel="noopener noreferrer">Wikimedia Commons</a>؛
{credit}.</figcaption></figure></div>
<div class="zm-ten-grid">{sections}</div>
<p class="zm-ten-verified">ارزیابی هر برنامه، محصول، طرح پژوهشی و مجوز اجرایی باید با مستندات واقعی انجام شود؛
این محتوای آموزشی، گواه تأییدیه آزمایشگاه، انتشار مقاله یا عرضه خدمت نیست.</p>
<p><a href="/research/">آشنایی با چارچوب تحقیقات زمرد ملل</a> ·
<a href="/topics/">دانشنامه موضوعات تخصصی</a></p>
</section>'''
def patch(src, fragment, path):
    if MARK in src:
        raise ValueError("Already deployed to "+path)
    if src.lower().count("</main>")!=1:
        raise ValueError("Unexpected main container: "+path)
    if src.lower().count("</body>")!=1 or src.lower().count("</html>")!=1:
        raise ValueError("Unexpected original HTML structure")
    if "زمرد ملل" not in src:
        raise ValueError("Page identity mismatch")
    if len(src.encode('utf8'))<1500:
        raise ValueError("Suspiciously empty original")
    next_html=src.replace("</main>",fragment+"\n</main>",1)
    if next_html.replace(fragment+"\n","",1)!=src:
        raise ValueError("Existing contents not preserved exactly")
    if next_html.count(MARK)!=1 or not next_html.strip().endswith("</html>"):
        raise ValueError("Invalid result")
    return next_html

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--originals',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--catalog',type=Path,required=True)
    p.add_argument('--media',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():
        raise ValueError("Staging output already exists")
    rows=json.loads(a.catalog.read_text(encoding="utf8"))['pages']
    media=json.loads((a.media/'photo-manifest.json').read_text(encoding="utf8"))
    assets={m['id']:m for m in media}
    if len(rows)!=10 or len(assets)!=10 or len({r["path"] for r in rows})!=10:
        raise ValueError("Ten authorized pages/photos required")
    if any(x['path'].startswith(('tala/','admin/','mohammad/','ghanadi/')) for x in rows):
        raise ValueError("Protected subsite in scope")
    for row in rows:
        m=assets[row["id"]]
        b=(a.media/(row["id"]+'.webp')).read_bytes()
        if hashlib.sha256(b).hexdigest()!=m["sha256"] or not b.startswith(b'RIFF') or b[8:12]!=b'WEBP':
            raise ValueError("Image hash/header mismatch")
    a.output.mkdir(parents=True)
    for row in rows:
        path=row['path']
        if not re.fullmatch(r'[a-z0-9-]+(?:/[a-z0-9-]+)*/index\.html',path):
            raise ValueError("Unsafe document path: "+path)
        original=a.originals/path
        if not original.is_file() or original.is_symlink():
            raise ValueError("Missing or symlink original: "+path)
        src=original.read_text(encoding="utf8")
        fragment=make_fragment(row,assets[row["id"]])
        result=patch(src,fragment,path)
        out=a.output/path
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(result,encoding='utf8')
        print("TEN_SUBJECTS_STAGED",path,"old",len(src),"new",len(result))
    assert len(list(a.output.rglob('index.html')))==10
    print("TEN_EDITORIALS_NONDESTRUCTIVE=verified")
    print("TEN_SOURCE_VERIFIED_PHOTOS=verified")
if __name__=="__main__":main()
