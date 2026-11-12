#!/usr/bin/env python3
"""Read-only structural, link and responsive checks for the Zomorod NEXUS release."""
import re
from pathlib import Path
from bs4 import BeautifulSoup
import tinycss2
ROOT=Path(__file__).resolve().parent
home=ROOT/'index.html'
css=ROOT/'assets/zm-nexus-v1.css'
assert home.is_file() and css.is_file()
h=home.read_text(encoding='utf-8')
c=css.read_text(encoding='utf-8')
s=BeautifulSoup(h,'html.parser')
assert s.html['lang']=='fa' and s.html['dir']=='rtl'
assert len(s.find_all('h1'))==1
assert not re.search(r'ونکوور|Vancouver|Canada|ساکن کانادا',h,re.I)
assert not re.search(r'ISO[ -]?9001|پروژه فعال:|رضایت مشتری|[٪%]\s*9[0-9]',h,re.I)
assert len(s.select('a[href]'))>=35
assert len(s.select('a[href^="/"]'))>=30
assert len(set(a.get('href') for a in s.select('a[href^="/"]')))>15
assert not s.select('a[href="javascript:void(0)"]')
assert not s.select('a[href="#"]')
assert len(s.select('img[alt]'))==len(s.select('img'))
assert len(s.select('img[width][height]'))==len(s.select('img'))
assert len(s.select('a[href="/ask-master/index.php?service=1"]'))>=2
assert s.select_one('link[rel="canonical"]')['href']=='https://zomorodmelal.ir/'
assert s.select_one('link[rel="stylesheet"]')['href']=='/assets/zm-nexus-v1.css'
assert '.domain-grid' in c and '.hero-grid' in c and '@media(max-width:640px)' in c
assert 'prefers-reduced-motion:reduce' in c
assert ':focus-visible' in c
assert 'body.zm-nexus-active' not in c
assert not re.search(r'@import\s*url',c,re.I)
assert not re.search(r'url\(\s*["\']?https?://',c,re.I)
# Parser errors in CSS:
errors=[x for x in tinycss2.parse_stylesheet(c,skip_comments=True,skip_whitespace=True) if x.type=='error']
assert not errors, errors
print('STRUCTURAL_VALIDATION=PASS')
print('INTERNAL_LINKS='+str(len(s.select('a[href^="/"]'))))
print('HOMEPAGE_MARKUP_BYTES='+str(len(h.encode())))
print('STYLESHEET_BYTES='+str(len(c.encode())))
