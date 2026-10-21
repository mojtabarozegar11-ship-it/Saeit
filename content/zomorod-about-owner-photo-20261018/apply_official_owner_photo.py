#!/usr/bin/env python3
"""Insert owner's authentic, approved portrait into the scientific About section only.

No old HTML is rewritten; source must already contain the official section.
Image is copied separately from the verified user-uploaded archive (not AI-generated).
"""
from pathlib import Path
import argparse

MARKER = '<!-- zm-about-owner-real-photo-20261018 -->'
IMAGE = '/static/site/zomorod-about/ceo-mojtaba-rozegar.webp'
ANCHOR = '<h2>شرکت کشت و صنعت زمرد ملل؛ مرکز تحقیقات علمی، آزمایشگاهی، ژنتیک و توسعه فناوری</h2>'
FRAGMENT = f'''{MARKER}
<div class="zm-owner-real-profile" aria-label="معرفی رسمی مجتبی روزگار">
<figure class="zm-owner-real-figure">
<img src="{IMAGE}" alt="Mojtaba Roozegar, also written Mojtaba Rozegar (مجتبی روزگار), researcher and CEO of Zomorod Melal" width="500" height="620" loading="eager" decoding="async">
<figcaption>مجتبی روزگار · محقق و پژوهشگر</figcaption>
</figure>
<div class="zm-owner-real-bio">
<p class="zm-owner-real-overline">RESEARCHER · SCIENTIFIC LEADERSHIP</p>
<h3>مجتبی روزگار</h3>
<p><strong>محقق، پژوهشگر و مدیرعامل شرکت کشت و صنعت زمرد ملل</strong></p>
<p lang="en">Mojtaba Roozegar · also written Mojtaba Rozegar · مجتبی روزگار</p>
<p>نقش محوری در جهت‌گیری پژوهش‌محور مجموعه، پیگیری تحقیقات علمی، ژنتیک و اصلاح نژاد و
تلاش برای استمرار فعالیت‌های پژوهشی. بر اساس اعلام شرکت، تأمین کسری منابع مالی پژوهش
در سال‌های گذشته از منابع شخصی او انجام شده است.</p>
<a href="/company/">آشنایی با ساختار و چشم‌انداز شرکت ←</a>
</div>
</div>
<style id="zm-owner-real-photo-style-20261018">
.zm-about-official-20261018 .zm-owner-real-profile{{display:grid;grid-template-columns:minmax(195px,315px) minmax(0,1fr);align-items:center;gap:clamp(19px,3.6vw,43px);margin:25px 0 30px;border:1px solid #caa86080;border-radius:23px;background:linear-gradient(130deg,#14382b,#204632);padding:clamp(16px,3vw,30px);box-shadow:0 13px 39px #071d1870}}
.zm-about-official-20261018 .zm-owner-real-figure{{margin:0;min-width:0}}
.zm-about-official-20261018 .zm-owner-real-figure img{{display:block;width:100%;height:auto;max-height:390px;aspect-ratio:4/5;object-fit:cover;object-position:50% 28%;border:3px solid #f2d38a;border-radius:17px;box-shadow:0 12px 31px #0005}}
.zm-about-official-20261018 .zm-owner-real-figure figcaption{{font-size:13px;color:#e7d5a8;text-align:center;line-height:1.8;padding-top:9px}}
.zm-about-official-20261018 .zm-owner-real-bio h3{{color:#f6d992;font-size:clamp(22px,3.3vw,36px);line-height:1.45;margin:0 0 12px}}
.zm-about-official-20261018 .zm-owner-real-bio p{{line-height:2.1}}
.zm-about-official-20261018 .zm-owner-real-bio .zm-owner-real-overline{{color:#dec17e;font-size:12px;letter-spacing:.09em}}
.zm-about-official-20261018 .zm-owner-real-bio a{{display:inline-block;margin-top:8px;border:1px solid #d8ba79;border-radius:13px;padding:8px 14px}}
@media(max-width:670px){{.zm-about-official-20261018 .zm-owner-real-profile{{grid-template-columns:1fr}}.zm-about-official-20261018 .zm-owner-real-figure{{width:min(100%,310px);margin:auto}}}}
</style>'''

def patch(source):
    if MARKER in source or 'zm-owner-real-photo-style-20261018' in source:
        raise ValueError('Already added authentic portrait')
    if source.count('<!-- zm-about-official-scientific-profile-20261018 -->') != 1:
        raise ValueError('Official scientific About section not found')
    if source.count(ANCHOR) != 1:
        raise ValueError('Official About headline mismatch; abort')
    if 'zm-unified-v7-20261018' not in source or 'ریشه در تجربه' not in source:
        raise ValueError('Cannot verify existing content')
    if '<!-- zm-about-owner-real-photo-20261018 -->' in source:
        raise ValueError('Portrait already installed')
    out = source.replace(ANCHOR, ANCHOR+'\n'+FRAGMENT,1)
    assert out.replace('\n'+FRAGMENT,'',1) == source
    assert out.count(MARKER) == 1
    assert out.count(IMAGE) == 1
    assert out.count('<!-- zm-about-official-scientific-profile-20261018 -->') == 1
    assert out.strip().endswith('</html>')
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    if args.output.exists():
        raise ValueError('Refusing to overwrite staging file')
    old=args.source.read_text(encoding='utf-8')
    new=patch(old)
    args.output.write_text(new,encoding='utf-8')
    print('REAL_OWNER_PORTRAIT_ADDED_TO_ABOUT_CANDIDATE=yes')
    print('ORIGINAL_HTML_REMAINS_BYTE_IDENTICAL_AFTER_REMOVING_INSERT=yes')
if __name__=='__main__':main()
