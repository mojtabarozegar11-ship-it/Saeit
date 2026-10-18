#!/usr/bin/env python3
"""Safely layer one V7 shell over main Zomorod HTML pages; do not erase source content.

Root orb design is only given a branded logo, inner pages receive the common
header/footer and CSS. Other sites, archives, admin, private data are excluded.
Runner MUST snapshot originals and atomically rollback on any failure.
"""
from __future__ import annotations
import argparse
import html
import os
import re
import sys
from pathlib import Path

MARKER='zm-unified-v7-20261018'
BANNED_TOP={
    'mohammad','ghanadi','amozeshgah','tala','education','business','site-heritage',
    'static','__pycache__','cgi-bin','wp-admin','admin','app','private','cgi',
}
NAV=(
    ('⌂','خانه','/'),('◈','شرکت','/company/'),('✦','درباره ما','/about/'),
    ('✧','خدمات','/services/'),('♧','کشاورزی','/agriculture/'),
    ('❀','ژنتیک','/agriculture/genetics/'),('⚙','صنعت','/industry/'),
    ('⌬','پژوهش','/research/'),('◆','دانشنامه','/knowledge/'),
    ('▣','حسابداری و مدیریت','/business/'),
)
LOGO='/static/site/zomorod-v7/company-logo.webp'
CSS='/static/site/zomorod-v7/inner-v7.css'
COPYRIGHT='تمام حقوق مادی و معنوی سایت برای شرکت کشت و صنعت زمرد ملل محفوظ است . آبان ۱۳۹۸ مجتبی روزگار'

def shell():
    parts=[]
    for i,(icon,title,url) in enumerate(NAV):
        parts.append(f'<a href="{html.escape(url)}" style="--v7delay:{i*140}ms"><span aria-hidden="true">{html.escape(icon)}</span>{html.escape(title)}</a>')
    nav=''.join(parts)
    header=(f'<!-- {MARKER} --><a href="#main" class="zm-v7-skip">رفتن به محتوای اصلی</a>'
            '<header class="zm-v7-header" role="banner"><div class="zm-v7-top">'
            f'<a class="zm-v7-identity" href="/"><span class="zm-v7-logo-frame"><img class="zm-v7-logo" src="{LOGO}" alt="نشان شرکت کشت و صنعت زمرد ملل" width="60" height="60" loading="eager"></span><span class="zm-v7-brand"><strong>شرکت کشت و صنعت زمرد ملل</strong><small>پژوهش‌های علمی، ژنتیک و فناوری کشاورزی</small></span></a>'
            f'<nav class="zm-v7-chain" aria-label="ناوبری اصلی زمرد ملل">{nav}</nav></div></header>')
    links=''.join(f'<a href="{html.escape(url)}">{html.escape(title)}</a>' for _,title,url in NAV)
    footer=('<footer class="zm-v7-footer" role="contentinfo"><div class="zm-v7-footer-grid">'
           f'<div><div class="zm-v7-footer-brand"><img src="{LOGO}" width="52" height="52" loading="lazy" alt="لوگوی زمرد ملل"><h2>زمرد ملل</h2></div><p>از پژوهش و مدیریت علمی تا کشاورزی، صنعت، ژنتیک، اقتصاد تولید و آموزش کاربردی.</p></div>'
           f'<div><h3>دسترسی سریع</h3><div class="zm-v7-footer-links">{links}</div></div>'
           '<div><h3>ارتباط و خدمات شرکت</h3><p>برای معرفی توانمندی‌ها، برنامه‌های پژوهشی و همکاری از بخش شرکت و خدمات استفاده کنید. اطلاعات مالی شرکت فقط برای کاربران مجاز قابل دسترسی است.</p>'
           '<div class="zm-v7-footer-links"><a href="/company/">معرفی شرکت</a><a href="/services/">خدمات</a></div></div>'
           '</div><p class="zm-v7-footer-copyright">'+COPYRIGHT+'</p></footer>')
    return header, footer

HEADER,FOOTER=shell()

def can_manage(rel:Path, root:bool=False)->bool:
    if rel.name.lower()!='index.html' and rel.parts!=('zm-specialist-library-2026.html',):return False
    if any(x.startswith('__') or x.startswith('.') for x in rel.parts):return False
    if rel.parts[0] in BANNED_TOP:return False
    if rel.parts[0].startswith('mojtaba') or rel.parts[0].startswith('farnaz'):return False
    return True

def find_targets(docroot:Path):
    for dirpath,dirs,files in os.walk(docroot,followlinks=False):
        parent=Path(dirpath)
        rel=parent.relative_to(docroot)
        dirs[:]=[d for d in dirs if d not in BANNED_TOP and not d.startswith('.') and not d.startswith('__') and not (parent/d).is_symlink()]
        if len(rel.parts)>5:dirs[:]=[];continue
        for name in files:
            f=parent/name
            relative=f.relative_to(docroot)
            if f.is_symlink() or not f.is_file() or not can_manage(relative):continue
            yield f,relative

def patch(data:bytes,rel:Path)->bytes:
    src=data.decode('utf-8')
    if MARKER in src:raise ValueError('already patched')
    if not re.search(r'<html\b[^>]*\blang\s*=\s*["\']fa["\']',src,re.I):raise ValueError('not verified Persian HTML')
    if src.lower().count('</head>')!=1 or src.lower().count('</body>')!=1 or src.lower().count('</html>')!=1:raise ValueError('bad HTML structure')
    b=re.search(r'<body\b[^>]*>',src,re.I)
    if not b:raise ValueError('missing body')
    css=f'<link rel="stylesheet" href="{CSS}?v=20261018" data-zm-v7="theme">'
    src=re.sub(r'</head>',css+'</head>',src,count=1,flags=re.I)
    b=re.search(r'<body\b[^>]*>',src,re.I)
    assert b
    root=rel.parts==('index.html',)
    if root:
        branded=f'<!-- {MARKER} --><a class="zm-v7-home-logo" href="/company/" aria-label="معرفی شرکت زمرد ملل"><img src="{LOGO}" width="64" height="64" alt="لوگوی زمرد ملل"></a>'
        src=src[:b.end()]+branded+src[b.end():]
    else:
        tag=b.group(0)
        if re.search(r'\bclass\s*=\s*["\']',tag,re.I):
            tag=re.sub(r'(\bclass\s*=\s*["\'])',r'\1zm-unified-v7 ',tag,count=1,flags=re.I)
        else:tag=tag[:-1]+' class="zm-unified-v7">'
        src=src[:b.start()]+tag+HEADER+src[b.end():]
        src=re.sub(r'</body>',FOOTER+'</body>',src,count=1,flags=re.I)
    if len(src.encode('utf-8'))<=len(data):raise ValueError('unanticipated size decrease')
    if not src.rstrip().lower().endswith('</html>'):raise ValueError('missing ending')
    return src.encode('utf-8')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('docroot',type=Path)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--manifest',type=Path)
    args=parser.parse_args()
    base=args.docroot.resolve(strict=True)
    assert (base/'index.html').is_file()
    planned=[]
    for p,rel in find_targets(base):
        data=p.read_bytes()
        out=patch(data,rel)
        planned.append((p,rel,data,out))
    assert 20<=len(planned)<=160,(len(planned),'suspicious scope')
    assert any(rel.parts==('index.html',) for _,rel,_,_ in planned)
    assert any(str(rel)=='company/index.html' for _,rel,_,_ in planned)
    assert any(str(rel)=='about/index.html' for _,rel,_,_ in planned)
    for _,rel,old,new in planned:
        print('UNIFY_PAGE',str(rel),'old',len(old),'new',len(new))
    if args.manifest:
        args.manifest.write_text('\n'.join(str(rel) for _,rel,_,_ in planned)+'\n',encoding='utf-8')
    if not args.apply:
        print('UNIFY_DRY_RUN_OK='+str(len(planned)));return
    for p,rel,old,new in planned:
        tmp=p.with_name('.index.html.v7-next')
        assert not tmp.exists()
        fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,mode=0o600)
        try:
            with os.fdopen(fd,'wb') as f:
                f.write(new);f.flush();os.fsync(f.fileno())
            os.chmod(tmp,p.stat().st_mode&0o777)
            os.replace(tmp,p)
        finally:
            if tmp.exists():tmp.unlink()
    print('UNIFY_APPLIED='+str(len(planned)))

if __name__=='__main__':
    main()