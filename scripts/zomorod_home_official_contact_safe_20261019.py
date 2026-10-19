#!/usr/bin/env python3
"""Atomic reversible home-only public contact section, preserving all existing bytes."""
from __future__ import annotations
import hashlib
import json
import os
import pwd
import re
import sys
import tempfile
from pathlib import Path

HOME=Path("/home/zomorod2/public_html/index.html")
BACKUPS=Path("/home/zomorod2/.backups/zomorod-official-contacts-20261019")
STYLE_ID="zm-official-contacts-glass-css-20261019"
PANEL_ID="zm-official-contacts-20261019"
SHELVES='id="orbit-shelves"'
FOOTER='id="site-footer"'
STYLE='''<style id="zm-official-contacts-glass-css-20261019">
/* Contact-only glass after the final shelf. No existing controls or cards touched. */
body #zm-official-contacts-20261019{
  box-sizing:border-box;
  width:min(1400px,calc(100% - 32px));
  margin:clamp(32px,5vw,70px) auto clamp(30px,4vw,58px);
  position:relative;
  isolation:isolate;
  direction:rtl;
  padding:clamp(22px,4vw,52px);
  border:2px solid rgba(250,217,142,.86);
  border-radius:clamp(22px,3.5vw,38px);
  outline:1px solid rgba(255,255,238,.35);
  outline-offset:-4px;
  background:radial-gradient(ellipse 100% 120% at 7% -28%,rgba(225,255,238,.29),transparent 67%),
    linear-gradient(142deg,rgba(67,145,110,.53),rgba(10,52,46,.83) 48%,rgba(4,27,35,.91))!important;
  box-shadow:inset 2px 2px 0 rgba(255,255,244,.5),
    inset -2px -3px 0 rgba(100,206,172,.23),
    0 22px 47px rgba(0,11,19,.4),0 38px 77px rgba(0,10,20,.27),
    0 0 23px rgba(237,196,105,.21);
  -webkit-backdrop-filter:blur(12px) saturate(1.18);
  backdrop-filter:blur(12px) saturate(1.18);
  color:#f8f4e7;
}
body #zm-official-contacts-20261019::before{
  content:"";pointer-events:none;position:absolute;inset:1px;border-radius:inherit;
  background:linear-gradient(132deg,rgba(255,255,247,.16),transparent 32%,transparent 73%,rgba(246,212,136,.055));
  z-index:-1;
}
body #zm-official-contacts-20261019 .zm-contact-heading{text-align:center;max-width:790px;margin:0 auto 30px;}
body #zm-official-contacts-20261019 .zm-contact-kicker{
  display:block;color:#f8d993;font-weight:750;letter-spacing:.12em;font-size:.8rem;
}
body #zm-official-contacts-20261019 h2{
  font-size:clamp(1.8rem,4vw,3rem);line-height:1.35;margin:10px 0;
  color:#fff1c8;text-shadow:0 2px 9px rgba(0,10,15,.7),0 0 20px rgba(247,208,127,.19);
}
body #zm-official-contacts-20261019 .zm-contact-heading p{
  color:#f4efdf;font-size:clamp(.94rem,1.3vw,1.06rem);line-height:2;margin:12px auto 0;
}
body #zm-official-contacts-20261019 .zm-contact-grid{
  display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:clamp(12px,2vw,22px);
}
body #zm-official-contacts-20261019 .zm-contact-card{
  display:flex;flex-direction:column;align-items:flex-start;gap:10px;
  min-width:0;padding:clamp(19px,2.5vw,30px);
  border:1.5px solid rgba(244,220,160,.69);border-radius:23px;
  background:linear-gradient(150deg,rgba(219,255,238,.16),rgba(9,43,41,.52) 60%,rgba(4,29,36,.63));
  box-shadow:inset 1px 1px 0 rgba(255,255,244,.38),
    inset -1px -1px 0 rgba(118,224,184,.18),0 15px 34px rgba(0,11,19,.30);
  -webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);
  transition:box-shadow .25s ease,border-color .25s ease;
}
body #zm-official-contacts-20261019 .zm-contact-symbol{
  display:inline-grid;place-items:center;width:46px;height:46px;
  border:1px solid rgba(255,225,149,.8);border-radius:16px;
  background:linear-gradient(145deg,rgba(254,233,180,.22),rgba(10,66,52,.25));
  color:#ffebaf;font-size:1.4rem;box-shadow:inset 1px 1px 0 rgba(255,255,240,.31);
}
body #zm-official-contacts-20261019 h3{font-size:clamp(1.16rem,1.6vw,1.38rem);color:#fff3d1;margin:4px 0;}
body #zm-official-contacts-20261019 .zm-contact-card p{
  color:#f1f2e9;line-height:1.95;margin:0;overflow-wrap:anywhere;
}
body #zm-official-contacts-20261019 .zm-contact-card a{
  margin-top:auto;display:inline-flex;gap:7px;align-items:center;
  color:#ffe3a0;font-weight:750;text-decoration:none;
  padding:10px 2px;text-underline-offset:5px;
}
body #zm-official-contacts-20261019 .zm-contact-card a:hover,
body #zm-official-contacts-20261019 .zm-contact-card a:focus-visible{text-decoration:underline;}
body #zm-official-contacts-20261019 .zm-contact-card a:focus-visible{
  outline:2px solid #ffdf95;outline-offset:3px;border-radius:4px;
}
body #zm-official-contacts-20261019 .zm-contact-footnote{
  text-align:center;color:#e6dfc9;font-size:.83rem;line-height:1.9;
  max-width:800px;margin:22px auto 0;
}
@media (hover:hover) and (pointer:fine){
  body #zm-official-contacts-20261019 .zm-contact-card:hover{
    border-color:rgba(255,238,187,.93);
    box-shadow:inset 1px 1px 0 rgba(255,255,247,.42),
               0 18px 43px rgba(0,10,18,.36),0 0 20px rgba(247,211,128,.19);
  }
}
@media(max-width:900px){
  body #zm-official-contacts-20261019 .zm-contact-grid{grid-template-columns:1fr;}
}
@media(max-width:600px){
  body #zm-official-contacts-20261019{
    width:calc(100% - 20px);padding:22px 16px;
    -webkit-backdrop-filter:blur(5px) saturate(1.08);
    backdrop-filter:blur(5px) saturate(1.08);
  }
  body #zm-official-contacts-20261019 .zm-contact-card{padding:20px;}
}
@media(prefers-reduced-motion:reduce){
  body #zm-official-contacts-20261019 .zm-contact-card{transition:none!important;}
}
</style>
'''
PANEL='''<section id="zm-official-contacts-20261019" aria-labelledby="zm-official-contacts-title">
  <div class="zm-contact-heading">
    <span class="zm-contact-kicker">ZOMOROD MELAL · OFFICIAL CONTACT</span>
    <h2 id="zm-official-contacts-title">راه‌های ارتباطی رسمی زمرد ملل</h2>
    <p>برای طرح موضوع پژوهشی، همکاری تخصصی و ارتباط با شرکت از مسیرهای رسمی زیر استفاده کنید.</p>
  </div>
  <div class="zm-contact-grid">
    <article class="zm-contact-card">
      <span class="zm-contact-symbol" aria-hidden="true">☎</span>
      <h3>تلفن ارتباطات فضای مجازی</h3>
      <p dir="ltr" lang="fa">۰۹۰۲۲۰۴۸۶۹۱</p>
      <a href="tel:+989022048691" aria-label="تماس با شماره رسمی شرکت زمرد ملل">تماس تلفنی <span aria-hidden="true">↗</span></a>
    </article>
    <article class="zm-contact-card">
      <span class="zm-contact-symbol" aria-hidden="true">⌖</span>
      <h3>نشانی دفتر شرکت</h3>
      <p>استان فارس، شهرستان مرودشت، خیابان قدس، کوچه ۹۲</p>
      <a href="https://zomorodmelal.ir/contact/" aria-label="مشاهده اطلاعات رسمی نشانی دفتر شرکت">مشاهده جزئیات نشانی <span aria-hidden="true">↗</span></a>
    </article>
    <article class="zm-contact-card">
      <span class="zm-contact-symbol" aria-hidden="true">✉</span>
      <h3>درگاه رسمی ارتباط و همکاری</h3>
      <p>اطلاعات حوزه‌های همکاری، پژوهش، تولید و مسیرهای ارتباط با شرکت.</p>
      <a href="https://zomorodmelal.ir/contact/" aria-label="ورود به صفحه رسمی تماس و همکاری شرکت">ورود به صفحه تماس و همکاری <span aria-hidden="true">↗</span></a>
    </article>
  </div>
  <p class="zm-contact-footnote">فقط اطلاعات منتشرشده در وب‌سایت رسمی شرکت نمایش داده شده‌اند؛ برای استعلام اطلاعات جدید به صفحه تماس مراجعه کنید.</p>
</section>
'''

def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()

def transform(original:bytes)->bytes:
    html=original.decode("utf-8")
    if len(original)<1500000 or html.count("</head>")!=1 or html.count("</body>")!=1:
        raise RuntimeError("Unexpected homepage HTML size or structure")
    if 'id="'+PANEL_ID+'"' in html or 'id="'+STYLE_ID+'"' in html:
        raise RuntimeError("Panel already exists")
    for required in (
      SHELVES, FOOTER,
      'id="zm-home-copy-cinematic-glass-20261019"',
      'id="zm-home-header-footer-glass-20261019"',
      'id="zm-glass-row-headers-20261018"',
      'id="zm-glass-floating-cards-20261018"',
      'id="zm-fixed-scientific-background-20261018"',
      'id="orbital-cards"', 'id="solar-stage"', 'ZOMOROD_ORBIT_DATA'
    ):
        if required not in html:raise RuntimeError("Protected live marker missing: "+required)
    shelves=list(re.finditer(r'<div\b[^>]*\bid="orbit-shelves"[^>]*>',html))
    footers=list(re.finditer(r'<footer\b[^>]*\bid="site-footer"[^>]*>',html))
    if len(shelves)!=1 or len(footers)!=1:
        raise RuntimeError("Non-unique homepage last-shelf or footer tag")
    shelf_index=shelves[0].start()
    foot_index=footers[0].start()
    if shelf_index>=foot_index:
        raise RuntimeError("Footer precedes last shelf; refusing deployment")
    footer_open=footers[0].group(0)
    after=html.replace("</head>",STYLE+"</head>",1).replace(footer_open,PANEL+footer_open,1).encode("utf-8")
    if after.replace(STYLE.encode(),b"",1).replace(PANEL.encode(),b"",1)!=original:
        raise RuntimeError("Existing content was modified")
    return after

def where(run:str)->Path:
    if not re.fullmatch(r"[0-9]{1,20}",run):raise RuntimeError("Invalid run ID")
    return BACKUPS/run

def safety():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":raise RuntimeError("Unexpected cPanel user")
    if not HOME.is_file() or HOME.is_symlink() or HOME.parent.is_symlink() or BACKUPS.is_symlink():
        raise RuntimeError("Unsafe target or backup directory")

def atomic(path:Path,data:bytes,mode:int):
    temp=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False,prefix=".zm-contact-panel-") as f:
            temp=Path(f.name);f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(temp,mode);os.replace(temp,path)
    finally:
        if temp is not None and temp.exists():temp.unlink()

def selftest():
    sample=('<html><head></head><body><div id="main-view">'
      '<div id="orbital-cards"></div><div id="solar-stage"></div>'
      +'<div class="orbit-shelves wrap" id="orbit-shelves"></div></div>'
      +'<footer class="footer" id="site-footer"></footer>'
      '<style id="zm-home-copy-cinematic-glass-20261019"></style>'
      '<style id="zm-home-header-footer-glass-20261019"></style>'
      '<style id="zm-glass-row-headers-20261018"></style>'
      '<style id="zm-glass-floating-cards-20261018"></style>'
      '<style id="zm-fixed-scientific-background-20261018"></style>'
      '<script>ZOMOROD_ORBIT_DATA</script></body></html>'
      +'x'*1600000).encode()
    result=transform(sample)
    assert result.replace(STYLE.encode(),b"",1).replace(PANEL.encode(),b"",1)==sample
    assert result.count(('id="'+PANEL_ID+'"').encode())==1
    assert result.index(SHELVES.encode())<result.index(('id="'+PANEL_ID+'"').encode())<result.index(FOOTER.encode())
    assert all(x in PANEL for x in ("tel:+989022048691", "https://zomorodmelal.ir/contact/", "راه‌های ارتباطی رسمی"))
    assert all(x in STYLE for x in ("backdrop-filter", "box-shadow", "prefers-reduced-motion", ".zm-contact-grid"))
    print("OFFICIAL_CONTACT_PANEL_SELFTEST=passed",flush=True)

def apply(run:str,expected:str):
    safety()
    if not re.fullmatch("[a-f0-9]{64}",expected):raise RuntimeError("Bad homepage digest")
    original=HOME.read_bytes()
    if sha(original)!=expected:raise RuntimeError("Concurrent homepage modification")
    after=transform(original)
    location=where(run)
    if location.exists() or location.is_symlink():raise RuntimeError("Backup already exists")
    location.mkdir(parents=True,mode=0o700)
    mode=HOME.stat().st_mode & 0o777
    atomic(location/"home.before.html",original,0o600)
    if sha((location/"home.before.html").read_bytes())!=expected:raise RuntimeError("Backup mismatch")
    manifest={"before":expected,"after":sha(after),"mode":mode}
    (location/"manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
    if sha(HOME.read_bytes())!=expected:raise RuntimeError("Concurrent change before install")
    atomic(HOME,after,mode)
    if sha(HOME.read_bytes())!=manifest["after"]:raise RuntimeError("Post-publish mismatch")
    print("OFFICIAL_CONTACT_PANEL_INSTALLED=yes",flush=True)

def verify(run:str):
    safety()
    location=where(run)
    data=json.loads((location/"manifest.json").read_text())
    original=(location/"home.before.html").read_bytes()
    current=HOME.read_bytes()
    if sha(original)!=data["before"] or sha(current)!=data["after"]:
        raise RuntimeError("Unexpected file digest")
    if current.replace(STYLE.encode(),b"",1).replace(PANEL.encode(),b"",1)!=original:
        raise RuntimeError("Original homepage changed")
    print("OFFICIAL_CONTACT_PANEL_ORIGINAL_PRESERVED=yes",flush=True)

def rollback(run:str):
    safety()
    location=where(run)
    if not (location/"manifest.json").is_file():
        print("OFFICIAL_CONTACT_PANEL_NOT_INSTALLED=yes",flush=True)
        return
    data=json.loads((location/"manifest.json").read_text())
    before=(location/"home.before.html").read_bytes()
    if sha(before)!=data["before"]:raise RuntimeError("Backup corrupt")
    current=sha(HOME.read_bytes())
    if current==data["before"]:return
    if current!=data["after"]:raise RuntimeError("Homepage changed; refusing unsafe rollback")
    atomic(HOME,before,data["mode"])
    if sha(HOME.read_bytes())!=data["before"]:raise RuntimeError("Rollback mismatch")
    print("OFFICIAL_CONTACT_PANEL_ROLLED_BACK=yes",flush=True)

if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif len(sys.argv)==4 and sys.argv[1]=="apply":apply(sys.argv[2],sys.argv[3])
    elif len(sys.argv)==3 and sys.argv[1]=="verify":verify(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:raise SystemExit("selftest|apply RUN SHA|verify RUN|rollback RUN")
