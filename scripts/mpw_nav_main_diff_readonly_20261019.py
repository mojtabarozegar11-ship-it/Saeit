#!/usr/bin/env python3
"""Read-only exact main-content difference for the failed canonical-nav release."""
from pathlib import Path
import re,difflib,hashlib
root=Path("/home/zomorod2/mojplaywin.com/design-preview-20261017")
pages=root/"mpw-ten-editorials-20261018/pages"
home=(root/"production-home-20261017.html").read_text("utf8")
hdr_re=re.compile(r'<header\b(?=[^>]*\bclass=["\'](?:mw-site-nav|mpw-header)["\'])[^>]*>[\s\S]*?</header>',re.I)
header=hdr_re.search(home).group(0).replace("<header ","<header data-mpw-nav-harmonized-20261019=\"true\" ",1)
a="if(b){b.addEventListener('click',()=>{n.classList.toggle('open');b.setAttribute('aria-expanded',n.classList.contains('open'));});}"
b="n.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{n.classList.remove('open');b.setAttribute('aria-expanded','false');}));"
c="window.addEventListener('keydown',e=>{if(e.key==='Escape'){n.classList.remove('open');b.setAttribute('aria-expanded','false');}});"
pairs=[(a,a.replace("if(b){","if(b&&n){",1)),(b,"if(b&&n){"+b+"}"),(c,"if(b&&n){"+c+"}")]
main_re=re.compile(r'<main\b[^>]*>[\s\S]*?</main\s*>',re.I)
for slug in ("agents","research","knowledge","company","about","services"):
    original=(pages/(slug+".html")).read_text("utf8")
    nav=hdr_re.search(original)
    fixed=original[:nav.start()]+header+original[nav.end():]
    decl="const b=document.querySelector('.menu-toggle'),n=document.querySelector('.nav');"
    if decl in fixed and pairs[0][0] in fixed:
        for before,after in pairs:
            fixed=fixed.replace(before,after,1)
    orig=main_re.search(original).group(0)
    later=main_re.search(fixed).group(0)
    clean=later
    for before,after in pairs:clean=clean.replace(after,before,1)
    print("DIFF_PAGE",slug,"original_main_sha",hashlib.sha256(orig.encode()).hexdigest()[:15],"later_main_sha",hashlib.sha256(later.encode()).hexdigest()[:15],"restored_sha",hashlib.sha256(clean.encode()).hexdigest()[:15],"same_after_reversal",orig==clean,
          "original_guard_in_main",pairs[0][0] in orig,"new_guard_in_main",pairs[0][1] in later)
    count=0
    for tag,x1,x2,y1,y2 in difflib.SequenceMatcher(None,orig,later,autojunk=False).get_opcodes():
        if tag=="equal":continue
        print("DIFF_OPCODE",slug,tag,"pre",repr(orig[x1:x2][:160]),"post",repr(later[y1:y2][:160]))
        count+=1
        if count>=8:break
