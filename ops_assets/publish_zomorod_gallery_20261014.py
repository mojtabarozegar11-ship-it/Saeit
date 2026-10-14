#!/usr/bin/env python3
"""Owner-requested, idempotent Zomorod Melal gallery + six reports publication.

Narrow scope: exactly six media assets and six published report records.
Does not change project settings, credentials, installed apps or existing records.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import zipfile

APP = Path('/home/zomorod2/Saeit')
STAGE = Path('/home/zomorod2/Saeit-staging/gallery_publish_20261014')
ARCHIVE = STAGE / 'zomorod_gallery_6_images_6_posts_2026-10-14.zip'
ARCHIVE_SHA256 = 'a7c3390ffc1ba99bd72c4c10cdaa80bc6d541600258e7c861aa632a99fbc3f64'
BACKUP = APP / 'backups' / 'zomorod_gallery_20261014'
PRIVATE_MEDIA = APP / 'gallery' / '2026' / '10'
URLS = APP / 'config' / 'urls.py'
GALLERY_TEMPLATE = APP / 'templates' / 'modern' / 'pages' / 'company-gallery.html'
GALLERY_PARTIAL = APP / 'templates' / 'modern' / 'partials' / 'zomorod_gallery_20261014.html'
REPORT_TEMPLATE = APP / 'templates' / 'modern' / 'zomorod_report_20261014.html'
REPORT_MODULE = APP / 'moj' / 'gallery_reports_20261014.py'
TARGETS = (URLS, GALLERY_TEMPLATE, GALLERY_PARTIAL, REPORT_TEMPLATE, REPORT_MODULE)
MARK = 'ZOMOROD_GALLERY_20261014'
CATEGORY = 'gallery'
EXPECTED_SLUGS = (
    'gallery-digital-management',
    'gallery-growth-presentation',
    'gallery-smart-agriculture',
    'gallery-business-collaboration',
    'gallery-executive-portrait',
    'gallery-organizational-leadership',
)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def fail(message):
    raise RuntimeError(message)


def read_bundle():
    if not ARCHIVE.is_file():
        fail('Archive is absent from SSH staging')
    payload = ARCHIVE.read_bytes()
    if sha256_bytes(payload) != ARCHIVE_SHA256:
        fail('Archive SHA256 mismatch; no publishing')
    with zipfile.ZipFile(ARCHIVE, 'r') as bundle:
        members = set(bundle.namelist())
        if 'manifest.json' not in members:
            fail('Manifest missing')
        manifest = json.loads(bundle.read('manifest.json').decode('utf-8'))
        rows = manifest.get('gallery_items')
        if not isinstance(rows, list) or len(rows) != 6:
            fail('Manifest must contain exactly six items')
        if tuple(row.get('slug') for row in rows) != EXPECTED_SLUGS:
            fail('Unexpected manifest slugs/order')
        payloads = []
        for row in rows:
            img_name = row.get('image', '')
            post_name = row.get('article', '')
            if not re.fullmatch(r'images/zomorod-gallery-0[1-6]-[a-z-]+\.webp',img_name):
                fail('Invalid image name')
            if not re.fullmatch(r'posts/0[1-6]-[a-z-]+\.md',post_name):
                fail('Invalid article name')
            if img_name not in members or post_name not in members:
                fail('Image or post missing')
            image_bytes = bundle.read(img_name)
            if not (image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP'):
                fail('Image not a WebP file')
            if len(image_bytes) > 8 * 1024 * 1024 or len(image_bytes) < 1024:
                fail('Unexpected image size')
            article_text = bundle.read(post_name).decode('utf-8')
            if article_text.startswith('---\n'):
                parts = article_text.split('\n---\n',1)
                if len(parts)!=2:fail('Article metadata invalid')
                article_text = parts[1]
            lines=[]
            for line in article_text.strip().splitlines():
                if line.lstrip().startswith('# ') or line.startswith('!['):
                    continue
                line=line.replace('**','').replace('  ',' ')
                if line.strip(): lines.append(line.strip())
                else: lines.append('')
            body='\n'.join(lines).strip()
            if len(body) < 150:fail('Article body too short')
            row=dict(row)
            row['image_bytes']=image_bytes
            row['image_filename']=Path(img_name).name
            row['image_storage_name']='gallery/2026/10/'+Path(img_name).name
            row['body']=body
            row['summary']=(body.split('\n\n')[0][:290]).strip()
            payloads.append(row)
        return payloads


def setup_django():
    if str(APP) not in sys.path:sys.path.insert(0,str(APP))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
    import django
    django.setup()
    from django.conf import settings
    if settings.DATABASES.get('default',{}).get('ENGINE') != 'django.db.backends.sqlite3':
        fail('Unexpected production database engine')
    from portal.models import Article, GalleryPhoto
    needed = {'title','slug','summary','body','category','language','cover','state','publication_mode','published_at','sources'}
    actual = {field.name for field in Article._meta.fields}
    if not needed.issubset(actual): fail('Article schema does not match known production app')
    actual_photo = {field.name for field in GalleryPhoto._meta.fields}
    if not {'title','image','alt_text','is_approved'}.issubset(actual_photo):
        fail('GalleryPhoto schema mismatch')
    return settings, Article, GalleryPhoto


def preflight(rows):
    if not URLS.is_file() or not GALLERY_TEMPLATE.is_file():
        fail('Missing live route or gallery template')
    route_text = URLS.read_text(encoding='utf-8')
    if 'urlpatterns' not in route_text:fail('Live URL configuration unrecognized')
    if "path('company-gallery/'" not in route_text and 'company-gallery' not in route_text:
        fail('Live company gallery route not found')
    template_text=GALLERY_TEMPLATE.read_text(encoding='utf-8')
    if '<section class="wrap gallery-grid">' not in template_text and MARK not in template_text:
        fail('Existing company gallery anchor absent')
    settings, Article, GalleryPhoto = setup_django()
    existing_slugs=[]
    existing_media=[]
    for row in rows:
        art=Article.objects.filter(slug=row['slug']).first()
        if art is not None and (art.category != CATEGORY or art.title != row['title']):
            fail('Unrelated article already uses intended report slug: '+row['slug'])
        if art is not None:existing_slugs.append(row['slug'])
        img=GalleryPhoto.objects.filter(image=row['image_storage_name']).first()
        if img is not None and img.title != row['title']:
            fail('Unrelated image already uses gallery image path')
        if img is not None:existing_media.append(row['slug'])
        out=PRIVATE_MEDIA/row['image_filename']
        if out.is_symlink():fail('Gallery image path is a symbolic link')
        if out.exists() and sha256_bytes(out.read_bytes())!=sha256_bytes(row['image_bytes']):
            fail('Conflicting gallery media file')
    # Validate image-source URLs syntactically here. Live editorial validation
    # also requires an approved GalleryPhoto, created first in the atomic publish.
    from django.core.validators import URLValidator
    validate_https=URLValidator(schemes=['https'])
    for row in rows:
        validate_https('https://zomorodmelal.ir/company-gallery/photo/'+row['slug']+'/')
    print('SOURCE_URL_VALIDATION_OK',len(rows))
    from django.contrib.auth import get_user_model
    editor_qs=get_user_model().objects.filter(is_active=True,is_staff=True,is_superuser=True)
    if editor_qs.count() != 1:
        fail('A unique active owner-level Django administrator is required to record editorial approval')
    print('EDITORIAL_OWNER_APPROVER_AVAILABLE')
    for x in (GALLERY_PARTIAL,REPORT_TEMPLATE,REPORT_MODULE):
        if x.exists() and MARK not in x.read_text(encoding='utf-8'):
            fail('An unrelated file exists at the add-on path: '+x.name)
    print('PRECHECK_OK six_images six_reports expected_live_app')
    print('EXISTING_OWN_ARTICLES',len(existing_slugs),'EXISTING_OWN_MEDIA',len(existing_media))
    return settings, Article, GalleryPhoto


def generate_gallery_partial(rows):
    cards=[]
    for row in rows:
        slug=html.escape(row['slug'],quote=True)
        title=html.escape(row['title'])
        alt=html.escape(row['alt'],quote=True)
        desc=html.escape(row['meta_description'])
        cards.append('<article class="zmg-item"><a href="/company-gallery/report/'+slug+'/">'
            '<img src="/company-gallery/photo/'+slug+'/" loading="lazy" alt="'+alt+'">'
            '<div class="zmg-copy"><h3>'+title+'</h3><p>'+desc+'</p><span>مشاهده گزارش تصویری ←</span></div>'
            '</a></article>')
    return '''<!-- ZOMOROD_GALLERY_20261014: owner-requested gallery publications -->
<section class="wrap section-space zmg-section" id="managerial-gallery-20261014" aria-label="گزارش‌های تصویری زمرد ملل">
  <div class="section-heading"><div><span class="eyebrow">زمرد ملل / رسانه سازمانی</span><h2>گالری و گزارش‌های تصویری مدیریت</h2></div>
    <p>شش تصویر هویتی با گزارش توضیحی مستقل. این تصاویر، روایت بصری معرفی برند هستند و به‌تنهایی وقوع جلسه، قرارداد یا نتیجه مالی را اثبات نمی‌کنند.</p>
  </div>
  <div class="zmg-grid">'''+''.join(cards)+'''</div>
</section>
<style>
.zmg-section{padding-top:3rem;padding-bottom:3rem}.zmg-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1.25rem;margin-top:1.5rem}
.zmg-item{overflow:hidden;border:1px solid rgba(177,145,66,.28);border-radius:18px;background:#fff;box-shadow:0 9px 24px rgba(34,39,25,.08)}
.zmg-item a{color:inherit;display:block;text-decoration:none}.zmg-item img{display:block;width:100%;height:290px;object-fit:cover;object-position:top}
.zmg-copy{padding:1rem 1.1rem}.zmg-copy h3{font-size:1.05rem;margin:0 0 .45rem;color:#263c2d}.zmg-copy p{font-size:.9rem;line-height:1.8;margin:.3rem 0 .6rem;color:#62695c}.zmg-copy span{font-size:.87rem;color:#8a711c;font-weight:700}
@media(max-width:900px){.zmg-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.zmg-grid{grid-template-columns:1fr}.zmg-item img{height:auto;max-height:480px;object-fit:contain;background:#eeeae1}}
</style>
'''


def generate_report_module(rows):
    mappings={row['slug']:row['image_filename'] for row in rows}
    return '''# ZOMOROD_GALLERY_20261014 — isolated public routes for owner-approved reports
from pathlib import Path
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.utils.cache import patch_cache_control
from portal.models import GalleryPhoto, Article

ITEMS = '''+repr(mappings)+'''
MEDIA_ROOT = Path(__file__).resolve().parents[1] / "gallery" / "2026" / "10"

def gallery_photo_20261014(request, slug):
    filename = ITEMS.get(slug)
    if not filename: raise Http404('Not an approved gallery image')
    name = "gallery/2026/10/" + filename
    if not GalleryPhoto.objects.filter(image=name, is_approved=True).exists():
        raise Http404('Unapproved gallery image')
    p=MEDIA_ROOT / filename
    if p.is_symlink() or not p.is_file() or p.stat().st_size > 8*1024*1024:
        raise Http404('Gallery image missing')
    with p.open('rb') as check:
        header=check.read(12)
        if header[:4] != b'RIFF' or header[8:12] != b'WEBP':
            raise Http404('Invalid media type')
    result=FileResponse(p.open('rb'),content_type='image/webp')
    patch_cache_control(result,public=True,max_age=86400)
    result['X-Content-Type-Options']='nosniff'
    return result

def gallery_report_20261014(request, slug):
    if slug not in ITEMS:raise Http404('Unknown gallery report')
    report=get_object_or_404(Article,slug=slug,category='gallery',state='published',cover__is_approved=True)
    return render(request,'modern/zomorod_report_20261014.html',{
       'article':report,'image_url':'/company-gallery/photo/'+slug+'/',
       'other_articles':Article.objects.filter(slug__in=ITEMS.keys(),category='gallery',state='published').exclude(pk=report.pk).order_by('title')[:5]
    })
'''


def generate_report_template():
    return r'''<!-- ZOMOROD_GALLERY_20261014: report template -->
{% load static %}
<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ article.title }} | شرکت کشت و صنعت زمرد ملل</title>
<meta name="description" content="{{ article.summary|truncatechars:160 }}">
<link rel="canonical" href="https://zomorodmelal.ir/company-gallery/report/{{ article.slug }}/">
<meta property="og:type" content="article"><meta property="og:locale" content="fa_IR"><meta property="og:title" content="{{ article.title }}"><meta property="og:description" content="{{ article.summary|truncatechars:160 }}">
<meta property="og:image" content="https://zomorodmelal.ir{{ image_url }}"><meta property="og:url" content="https://zomorodmelal.ir/company-gallery/report/{{ article.slug }}/">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Article","headline":"{{ article.title|escapejs }}","description":"{{ article.summary|truncatechars:160|escapejs }}","image":"https://zomorodmelal.ir{{ image_url }}","datePublished":"{{ article.published_at|date:'c' }}","inLanguage":"fa","author":{"@type":"Organization","name":"شرکت کشت و صنعت زمرد ملل"},"publisher":{"@type":"Organization","name":"شرکت کشت و صنعت زمرد ملل","url":"https://zomorodmelal.ir/"},"mainEntityOfPage":"https://zomorodmelal.ir/company-gallery/report/{{ article.slug }}/"}</script>
<style>:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;font-family:Tahoma,Arial,sans-serif;color:#283629;background:#f7f5f1;line-height:2}a{color:#775f17;text-decoration:none}a:hover{text-decoration:underline}.top{background:#fff;border-bottom:1px solid #ded8c6}.topin{max-width:1120px;margin:auto;padding:14px 24px;display:flex;gap:1rem;justify-content:space-between;align-items:center;flex-wrap:wrap}.brand{font-weight:700;color:#203f2e;display:flex;align-items:center;gap:12px}.brand img{width:44px;height:44px;object-fit:contain}.nav{display:flex;gap:20px;flex-wrap:wrap}.nav a{color:#304235}.wrap{width:min(100% - 40px,1040px);margin:auto}.lead{padding:44px 0 24px}.label{color:#987a20;letter-spacing:.03em;font-size:13px}.lead h1{font-size:clamp(1.65rem,3.3vw,2.6rem);line-height:1.5;color:#203b2c;margin:12px 0}.summary{max-width:850px;font-size:1.03rem;color:#555b52}.article{background:#fff;border:1px solid #e1dbce;border-radius:20px;overflow:hidden;box-shadow:0 15px 35px rgba(48,55,34,.08)}.hero{display:block;width:100%;max-height:850px;object-fit:contain;background:linear-gradient(120deg,#efe8d8,#ecefea)}.article-body{padding:clamp(22px,4vw,55px);font-size:1.04rem}.article-body p{margin:0 0 1.5rem}.notice{background:#faf7ef;border-right:4px solid #b89d53;padding:14px 20px;border-radius:6px;color:#5c5c4b;font-size:.9rem}.related{padding:32px 0 65px}.related ul{padding-right:22px}footer{background:#243b2d;color:#f1ead8;text-align:center;padding:25px 15px;font-size:.85rem}footer a{color:#f3d993}@media(max-width:600px){.nav{gap:9px;font-size:13px}}</style>
</head><body>
<header class="top"><div class="topin"><a class="brand" href="/"><img src="{% static 'site/company/company-logo.png' %}" alt="نشان زمرد ملل">شرکت کشت و صنعت زمرد ملل</a><nav class="nav"><a href="/">خانه</a><a href="/company/">درباره شرکت</a><a href="/company-gallery/">گالری تصاویر</a><a href="/blog/">وبلاگ</a></nav></div></header>
<main class="wrap"><div class="lead"><div class="label">رسانه سازمانی / گزارش تصویری</div><h1>{{ article.title }}</h1><p class="summary">{{ article.summary }}</p><p><small>تاریخ انتشار: {{ article.published_at|date:'Y/m/d' }} · نویسنده: روابط عمومی زمرد ملل</small></p></div>
<article class="article"><img class="hero" src="{{ image_url }}" alt="{{ article.cover.alt_text }}" width="1100" loading="eager"><div class="article-body">{{ article.body|linebreaks }}<div class="notice">این تصویر برای معرفی بصری و هویت سازمانی منتشر شده است و به تنهایی سند وقوع رویداد، قرارداد، بازدید یا نتیجه اقتصادی نیست.</div></div></article>
<section class="related"><h2>گزارش‌های تصویری مرتبط</h2><ul>{% for item in other_articles %}<li><a href="/company-gallery/report/{{ item.slug }}/">{{ item.title }}</a></li>{% endfor %}</ul><a href="/company-gallery/">← بازگشت به گالری شرکت</a></section></main>
<footer>© شرکت کشت و صنعت زمرد ملل · <a href="/contact/">تماس با شرکت</a></footer>
</body></html>
'''


def write_atomic(path, contents):
    path.parent.mkdir(parents=True,exist_ok=True)
    descriptor,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=str(path.parent))
    try:
        with os.fdopen(descriptor,'wb') as f:
            f.write(contents if isinstance(contents,bytes) else contents.encode('utf-8'))
            f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o644)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def install_source(rows):
    old_url=URLS.read_text(encoding='utf-8')
    old_gallery=GALLERY_TEMPLATE.read_text(encoding='utf-8')
    route_add = '''\n# ZOMOROD_GALLERY_20261014: narrowly scoped photo reports (owner-approved)\nfrom moj.gallery_reports_20261014 import gallery_report_20261014, gallery_photo_20261014\nurlpatterns += [\n    path("company-gallery/report/<slug:slug>/",gallery_report_20261014,name="zm_gallery_report_20261014"),\n    path("company-gallery/photo/<slug:slug>/",gallery_photo_20261014,name="zm_gallery_photo_20261014"),\n]\n'''
    if MARK not in old_url:write_atomic(URLS,old_url+route_add)
    if MARK not in old_gallery:
        anchor='<section class="wrap gallery-grid">'
        if old_gallery.count(anchor)!=1:fail('Gallery injection anchor not unique')
        changed=old_gallery.replace(anchor,'{# ZOMOROD_GALLERY_20261014 #}\n{% include "modern/partials/zomorod_gallery_20261014.html" %}\n'+anchor,1)
        write_atomic(GALLERY_TEMPLATE,changed)
    write_atomic(GALLERY_PARTIAL,generate_gallery_partial(rows))
    write_atomic(REPORT_TEMPLATE,generate_report_template())
    write_atomic(REPORT_MODULE,generate_report_module(rows))
    compile(REPORT_MODULE.read_text(encoding='utf-8'),str(REPORT_MODULE),'exec')


def backup_live(settings):
    BACKUP.mkdir(parents=True,exist_ok=True)
    os.chmod(BACKUP,0o700)
    for original in (URLS,GALLERY_TEMPLATE):
        dest=BACKUP/(original.name+'.'+sha256_bytes(str(original).encode())[:12]+'.before')
        if not dest.exists():
            shutil.copy2(original,dest)
            os.chmod(dest,0o600)
    dbname=Path(settings.DATABASES['default']['NAME'])
    if not dbname.exists():fail('Database file missing')
    db_backup=BACKUP/'db-before-first-publish.sqlite3'
    if not db_backup.exists():
        src=sqlite3.connect('file:'+str(dbname)+'?mode=ro',uri=True)
        try:
            dst=sqlite3.connect(str(db_backup))
            try:src.backup(dst)
            finally:dst.close()
        finally:src.close()
        os.chmod(db_backup,0o600)
    print('BACKUP_SAFELY_CREATED')


def copy_media(rows):
    PRIVATE_MEDIA.mkdir(parents=True,exist_ok=True)
    for row in rows:
        p=PRIVATE_MEDIA/row['image_filename']
        if p.exists():continue
        descriptor,tmp=tempfile.mkstemp(prefix='.zm-gallery-',dir=str(PRIVATE_MEDIA))
        try:
            with os.fdopen(descriptor,'wb') as f:
                f.write(row['image_bytes']); f.flush();os.fsync(f.fileno())
            os.chmod(tmp,0o644)
            os.replace(tmp,p)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    print('MEDIA_COPIED',len(rows))


def save_database(rows,Article,GalleryPhoto):
    from django.db import transaction
    from django.utils import timezone
    from django.contrib.auth import get_user_model
    approver=get_user_model().objects.get(is_active=True,is_staff=True,is_superuser=True)
    created_articles=[]; created_photos=[]
    with transaction.atomic():
        for row in rows:
            photo = GalleryPhoto.objects.filter(image=row['image_storage_name']).first()
            if photo is None:
                photo=GalleryPhoto.objects.create(title=row['title'],image=row['image_storage_name'],alt_text=row['alt'],is_approved=True)
                created_photos.append(photo.pk)
            elif not photo.is_approved:
                photo.is_approved=True
                photo.save(update_fields=['is_approved'])
            article=Article.objects.filter(slug=row['slug']).first()
            if article is None:
                article=Article.objects.create(
                  title=row['title'],slug=row['slug'],summary=row['summary'],body=row['body'],
                  language='fa',category=CATEGORY,sources=['https://zomorodmelal.ir/company-gallery/photo/'+row['slug']+'/'],cover=photo,state='published',
                  publication_mode='human',approved_by=approver,published_at=timezone.now())
                created_articles.append(article.pk)
            elif article.state!='published' or article.cover_id!=photo.pk or article.approved_by_id is None:
                article.cover=photo;article.state='published';article.approved_by=approver
                if article.published_at is None:article.published_at=timezone.now()
                article.save(update_fields=['cover','state','approved_by','published_at'])
    print('DB_PUBLISHED_ARTICLES',Article.objects.filter(slug__in=EXPECTED_SLUGS,category=CATEGORY,state='published').count())
    print('DB_CREATED_NEW',len(created_articles),len(created_photos))
    return created_articles,created_photos


def smoke_test():
    snippet = """import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup();from django.test import Client;from portal.models import Article,GalleryPhoto;c=Client(HTTP_HOST='zomorodmelal.ir');r=c.get('/company-gallery/');assert r.status_code==200,('gallery',r.status_code);assert b'managerial-gallery-20261014' in r.content, 'gallery insertion missing';slugs=__SLUGS__;\nfor s in slugs:\n a=c.get('/company-gallery/report/'+s+'/');assert a.status_code==200,(s,a.status_code);assert s.encode() in a.content,(s,'not linked');im=c.get('/company-gallery/photo/'+s+'/');assert im.status_code==200,(s,im.status_code);assert im['Content-Type'].startswith('image/webp'),(s,'wrong mime');im.close()\nprint('ALL_SIX_REPORTS_AND_IMAGES_RENDER_OK')""".replace('__SLUGS__',repr(EXPECTED_SLUGS))
    cp=subprocess.run([sys.executable,'-c',snippet],cwd=APP,capture_output=True,text=True,timeout=75)
    if cp.returncode:
        print('SMOKE_STDOUT',cp.stdout[-500:])
        print('SMOKE_STDERR',cp.stderr[-1100:])
        fail('Internal Django smoke test failed')
    print(cp.stdout.strip())


def run_publish(rows):
    settings,Article,GalleryPhoto=preflight(rows)
    backup_live(settings)
    try:
        copy_media(rows)
        install_source(rows)
    except Exception:
        restore_source()
        raise
    check=subprocess.run([sys.executable,str(APP/'manage.py'),'check'],cwd=APP,capture_output=True,text=True,timeout=60)
    if check.returncode:
        print('CHECK_ERROR',check.stderr[-900:],check.stdout[-500:])
        restore_source()
        fail('Django check failed; previous source restored')
    try:
        created_articles, created_photos = save_database(rows,Article,GalleryPhoto)
        smoke_test()
    except Exception:
        restore_source()
        from django.db import transaction
        # Keep existing records untouched. Remove records created by this run if known.
        if 'created_articles' in locals():
            with transaction.atomic():
                Article.objects.filter(pk__in=created_articles).delete()
                GalleryPhoto.objects.filter(pk__in=created_photos).delete()
        raise
    os.utime(APP/'passenger_wsgi.py',None)
    print('PUBLICATION_SUCCESS images=6 reports=6 gallery=/company-gallery/')
    for slug in EXPECTED_SLUGS:print('PUBLIC_REPORT_URL=https://zomorodmelal.ir/company-gallery/report/'+slug+'/')


def restore_source():
    restored=0
    for original in (URLS,GALLERY_TEMPLATE):
        dest=BACKUP/(original.name+'.'+sha256_bytes(str(original).encode())[:12]+'.before')
        if dest.exists():
            shutil.copy2(dest,original)
            restored+=1
    for addon in (GALLERY_PARTIAL,REPORT_TEMPLATE,REPORT_MODULE):
        if addon.exists() and MARK in addon.read_text(encoding='utf-8'):
            addon.unlink()
    if (APP/'passenger_wsgi.py').exists():os.utime(APP/'passenger_wsgi.py',None)
    print('SOURCE_ROLLBACK_FILES',restored)

def rollback_publication():
    settings, Article, GalleryPhoto=setup_django()
    from django.db import transaction
    with transaction.atomic():
        Article.objects.filter(slug__in=EXPECTED_SLUGS,category=CATEGORY).update(state='draft')
        GalleryPhoto.objects.filter(image__in=['gallery/2026/10/zomorod-gallery-0'+str(i)+'-'+name+'.webp' for i,name in enumerate(['digital-management','growth-presentation','smart-agriculture','business-collaboration','executive-portrait','organizational-leadership'],1)]).update(is_approved=False)
    restore_source()
    print('PUBLISH_ROLLBACK_COMPLETE')


def main():
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight',action='store_true')
    mode.add_argument('--publish',action='store_true')
    mode.add_argument('--rollback',action='store_true')
    args=parser.parse_args()
    if args.rollback:
        rollback_publication()
        return
    rows=read_bundle()
    if args.preflight:
        preflight(rows)
    else:
        run_publish(rows)

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('PUBLICATION_FAILED',type(e).__name__,str(e)[:340],file=sys.stderr)
        sys.exit(1)