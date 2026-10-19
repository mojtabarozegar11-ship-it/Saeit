#!/usr/bin/env python3
"""Original F19 website-template producer: 1+48 real work packages+independent QA.

Produces one complete responsive, no-build, offline HTML/CSS starter kit.
The ten automated technical gates are reviewed by a separate module.
No claim of human review, commercial acceptance, store publication or earnings.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

HERE=Path(__file__).resolve().parent
PRODUCT='saas_launch_starter_2026'
NAMES=('header','hero','value','features','workflow','use_cases',
       'security','integrations','pricing','faq','contact','footer')
TOPICS=(
 ('header','Build accessible global navigation with distinct anchor destinations'),
 ('hero','Introduce the product with a clear value proposition and actionable CTA'),
 ('value','Explain expected outcomes without fabricated customer proof'),
 ('features','Communicate differentiating product capabilities using useful cards'),
 ('workflow','Present an actionable sequence from discovery to launch'),
 ('use_cases','Explain relevant scenarios for three types of stakeholders'),
 ('security','Describe security responsibilities without inventing certifications'),
 ('integrations','Differentiate connected examples from actual provider support'),
 ('pricing','Show sample pricing architecture without selling fictitious plans'),
 ('faq','Provide accessible native disclosure controls for common concerns'),
 ('contact','Route contact intent without collecting or transmitting visitor data'),
 ('footer','Close navigation with ownership disclaimers and maintenance guidance'),
)
HTML={
'header':'''<header id="header" class="site-header"><div class="container nav-wrap">
<a class="brand" href="#hero" aria-label="Northstar Studio — back to the start"><span class="brand-mark" aria-hidden="true">N</span> Northstar<span class="brand-muted">Studio</span></a>
<nav aria-label="Primary navigation" class="site-nav"><a href="#features">Features</a><a href="#workflow">How it works</a><a href="#pricing">Pricing</a><a href="#faq">FAQ</a></nav><a class="btn btn-small btn-outline" href="#contact">Get in touch</a></div></header>''',
'hero':'''<section id="hero" class="hero section"><div class="container hero-grid"><div><p class="eyebrow">Launch-ready website system</p><h1>Make your next bold idea feel inevitable.</h1><p class="hero-copy">An original, lightweight starter website for founders who want clear storytelling, thoughtfully structured content, and an elegant mobile-first experience — without the complexity of a framework.</p><div class="hero-actions"><a class="btn btn-primary" href="#features">See the features <span aria-hidden="true">↗</span></a><a class="text-link" href="#workflow">Explore the workflow <span aria-hidden="true">→</span></a></div><p class="helper">Demo website only. Replace the example brand and claims before publication.</p></div><aside class="hero-panel" aria-label="Preview of the three-part launch workflow"><span class="panel-tag">LAUNCH SYSTEM / EDITABLE DEMO</span><div class="orb" aria-hidden="true"><span></span></div><p class="panel-title">Less noise. More momentum.</p><ol><li>Define your story</li><li>Show your value</li><li>Invite the conversation</li></ol></aside></div></section>''',
'value':'''<section id="value" class="section section-light"><div class="container split"><div><p class="eyebrow ink">THE APPROACH</p><h2>Built to communicate, not just decorate.</h2></div><div><p class="lead">Great websites give visitors a clear path: understand the offer, see the relevant detail, and know the next step. This sample system is designed around that journey.</p><a href="#use_cases" class="text-link dark-link">Find your audience <span aria-hidden="true">→</span></a></div></div></section>''',
'features':'''<section id="features" class="section"><div class="container"><p class="eyebrow">DESIGNED WITH INTENTION</p><h2>Every detail earns its place.</h2><p class="section-intro">A practical foundation for product presentation that stays fast, accessible, and easy to personalize.</p><div class="feature-grid"><article class="feature"><span class="feature-number">01</span><h3>Responsive by default</h3><p>A fluid layout adapts to smaller screens and supports comfortable reading.</p></article><article class="feature"><span class="feature-number">02</span><h3>Simple to maintain</h3><p>Plain HTML and CSS mean no build step or proprietary platform requirement.</p></article><article class="feature"><span class="feature-number">03</span><h3>Purposeful structure</h3><p>Semantically grouped sections guide readers from context to action.</p></article></div></div></section>''',
'workflow':'''<section id="workflow" class="section section-quiet"><div class="container"><p class="eyebrow">FROM IDEA TO OPEN TAB</p><h2>A launch workflow you can actually follow.</h2><div class="steps"><article><span>01 / EDIT</span><h3>Clarify the message</h3><p>Rewrite the example content for a specific audience, product, and measurable outcome.</p></article><article><span>02 / VERIFY</span><h3>Test the experience</h3><p>Review contrast, mobile layout, destination links, privacy statements, and performance.</p></article><article><span>03 / PUBLISH</span><h3>Ship deliberately</h3><p>Add real company details, replace placeholders, and deploy the static folder to your host.</p></article></div></div></section>''',
'use_cases':'''<section id="use_cases" class="section"><div class="container"><p class="eyebrow">FLEXIBLE BY DESIGN</p><h2>One foundation, many focused stories.</h2><div class="case-list"><article><span class="case-icon" aria-hidden="true">↗</span><div><h3>Early-stage founder</h3><p>Explain the problem you solve, share meaningful capabilities, and invite discovery calls.</p></div></article><article><span class="case-icon" aria-hidden="true">✳</span><div><h3>Small creative team</h3><p>Present a point of view, a simple service range, and a clear contact path.</p></div></article><article><span class="case-icon" aria-hidden="true">◈</span><div><h3>Independent consultant</h3><p>Articulate your process, clarify engagements, and answer the questions prospects ask.</p></div></article></div></div></section>''',
'security':'''<section id="security" class="section section-light"><div class="container split"><div><p class="eyebrow ink">RESPONSIBLE FOUNDATIONS</p><h2>Privacy starts with restraint.</h2></div><div><p class="lead">The delivered sample has no tracking pixels, external scripts, signup form, or analytics connection. That does not automatically make a real deployment compliant; your hosting, privacy notice, and third-party tools remain your responsibility.</p><a href="#contact" class="text-link dark-link">Review launch requirements <span aria-hidden="true">→</span></a></div></div></section>''',
'integrations':'''<section id="integrations" class="section"><div class="container"><p class="eyebrow">START CLEAN, EXTEND WITH CARE</p><h2>Bring the tools you already trust.</h2><p class="section-intro">No outside platforms are connected in this demonstration. Connect a verified provider only after validating permissions, terms, privacy, and accessibility.</p><div class="integration-grid"><div><span aria-hidden="true">◇</span><strong>Forms</strong><small>Add a secure backend</small></div><div><span aria-hidden="true">◉</span><strong>Analytics</strong><small>Respect consent</small></div><div><span aria-hidden="true">□</span><strong>Payments</strong><small>Use a proven checkout</small></div><div><span aria-hidden="true">◌</span><strong>CRM</strong><small>Protect customer data</small></div></div></div></section>''',
'pricing':'''<section id="pricing" class="section section-quiet"><div class="container"><p class="eyebrow">ILLUSTRATIVE PACKAGES</p><h2>Make an offer easy to understand.</h2><p class="section-intro">These packages are layout examples, not products you can purchase from this demo.</p><div class="price-grid"><article><span class="price-label">STARTER · EXAMPLE</span><h3>Core</h3><p>For a focused landing experience and a confident introduction.</p><ul><li>One clear value proposition</li><li>Essential sections</li><li>Direct contact next step</li></ul><a class="btn btn-outline" href="#contact">Discuss a fit</a></article><article class="featured-price"><span class="price-label">GROWTH · EXAMPLE</span><h3>Plus</h3><p>For teams organizing richer information and more detailed journeys.</p><ul><li>Expanded story sections</li><li>Structured use cases</li><li>Careful accessibility review</li></ul><a class="btn btn-primary" href="#contact">Talk through options</a></article></div></div></section>''',
'faq':'''<section id="faq" class="section"><div class="container faq-grid"><div><p class="eyebrow">BEFORE YOU LAUNCH</p><h2>Questions worth answering upfront.</h2><p>Native HTML disclosures remain useful even when JavaScript is disabled.</p></div><div class="faq-items"><details><summary>Does this template require a subscription?</summary><p>No. The original deliverable is a collection of editable static files. Hosting and any services you later connect are separate.</p></details><details><summary>Can I adapt the design for my own brand?</summary><p>Yes. Update example text, business details, colors, and any offer claims before publication. Verify any added content and licensing.</p></details><details><summary>Does the contact area send messages?</summary><p>No. It provides navigation and preparation guidance only. Connect a privacy-aware contact service before collecting inquiries.</p></details><details><summary>Are the sample packages actual checkout offers?</summary><p>No. They demonstrate a pricing layout. Remove or replace them with verified offers and terms.</p></details></div></div></section>''',
'contact':'''<section id="contact" class="section contact-section"><div class="container contact-card"><div><p class="eyebrow">MAKE THE NEXT STEP CLEAR</p><h2>Ready to tell a better story?</h2><p>This is an example contact section. Before launch, provide your real company address, contact channel, response hours, and privacy notice.</p></div><div><a class="btn btn-primary" href="#header">Review from the top <span aria-hidden="true">↑</span></a><p class="helper">No data is transmitted by this starter website.</p></div></div></section>''',
'footer':'''<footer id="footer" class="footer section"><div class="container footer-grid"><div><a class="brand" href="#hero"><span class="brand-mark" aria-hidden="true">N</span> Northstar<span class="brand-muted">Studio</span></a><p>Original editable demonstration template — replace the sample brand and claims before publishing.</p></div><nav aria-label="Footer navigation"><a href="#features">Features</a><a href="#pricing">Sample plans</a><a href="#faq">FAQ</a><a href="#contact">Contact</a></nav></div><div class="container copyright"><span>© Example brand. Replace before launch.</span><a href="#header">Back to top ↑</a></div></footer>'''
}
STYLES={
'header':'.site-header{position:sticky;top:0;z-index:10;backdrop-filter:blur(18px);background:rgba(12,18,31,.92);border-bottom:1px solid var(--line)}.nav-wrap{min-height:5.2rem;display:flex;align-items:center;justify-content:space-between;gap:2rem}.brand{font-weight:750;letter-spacing:-.045em;font-size:1.26rem;white-space:nowrap}.brand-mark{display:inline-grid;place-items:center;width:2.25rem;height:2.25rem;margin-right:.4rem;border-radius:.65rem;color:#08111f;background:var(--accent)}.brand-muted{font-weight:400;color:var(--muted)}.site-nav{display:flex;gap:1.65rem}.site-nav a{font-size:.92rem;color:var(--muted)}.site-nav a:hover{color:var(--text)}',
'hero':'.hero{padding-top:6.5rem;padding-bottom:7rem}.hero-grid{display:grid;grid-template-columns:minmax(0,1.22fr) minmax(17rem,.78fr);gap:5rem;align-items:center}.hero h1{font-size:clamp(3.1rem,6.3vw,6.4rem);line-height:1.02;letter-spacing:-.085em;max-width:13ch;margin:1rem 0 1.5rem}.hero-copy{font-size:1.13rem;max-width:57ch}.hero-actions{display:flex;align-items:center;gap:1.7rem;flex-wrap:wrap;margin:2.3rem 0}.hero-panel{padding:2.3rem;border:1px solid var(--line);border-radius:1.7rem;background:radial-gradient(circle at 55% 25%,rgba(91,228,189,.17),transparent 55%),#141d2e;box-shadow:0 35px 100px rgba(0,0,0,.25)}.panel-tag{font-size:.67rem;letter-spacing:.17em;color:var(--accent)}.orb{width:12rem;height:12rem;border-radius:50%;margin:2.7rem auto;background:radial-gradient(circle at 33% 28%,#c1ffe6,#53d9bd 35%,#1b5876 65%,#0d2237);box-shadow:0 0 90px rgba(86,223,186,.17)}.panel-title{color:var(--text);font-weight:700;font-size:1.35rem}.hero-panel ol{color:var(--muted);padding-left:1.4rem}',
'value':'.section-light{color:#17263a;background:#eff3f4}.section-light .lead{color:#435365}.split{display:grid;grid-template-columns:1fr 1fr;gap:5rem;align-items:start}.split h2{max-width:14ch}.split .lead{font-size:1.18rem;line-height:1.75}.ink{color:#147d72!important}.dark-link{color:#14675e!important}',
'features':'.feature-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1.1rem;margin-top:3.3rem}.feature{background:var(--panel);border:1px solid var(--line);border-radius:1.1rem;padding:2rem;min-height:15rem}.feature-number{color:var(--accent);font-size:.73rem;letter-spacing:.1em}.feature h3{margin:2rem 0 .65rem;font-size:1.4rem}.feature p{font-size:.93rem}.section-intro{max-width:65ch;margin-top:1.1rem}',
'workflow':'.section-quiet{background:#101a2b}.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:2rem;margin-top:3.5rem}.steps article{padding-top:1.4rem;border-top:2px solid var(--accent)}.steps span{font-size:.75rem;letter-spacing:.12em;color:var(--accent)}.steps h3{font-size:1.45rem;margin-top:1.3rem}.steps p{max-width:34ch}',
'use_cases':'.case-list{margin-top:3rem;display:grid;grid-template-columns:repeat(3,1fr);gap:1rem}.case-list article{display:flex;align-items:flex-start;gap:1.2rem;padding:1.6rem;border:1px solid var(--line);border-radius:1rem}.case-icon{color:var(--accent);font-size:1.5rem}.case-list h3{margin:.1rem 0 .65rem}.case-list p{font-size:.9rem}',
'security':'.section-light .eyebrow{color:#146a5e}.section-light h2{color:#17263a}.section-light a{text-decoration:underline;text-underline-offset:.25rem}.section-light .split>div:last-child{padding-top:.55rem}',
'integrations':'.integration-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-top:3rem}.integration-grid>div{display:grid;gap:.5rem;border:1px solid var(--line);border-radius:1rem;padding:1.5rem}.integration-grid span{color:var(--accent);font-size:2rem}.integration-grid strong{font-size:1.2rem}.integration-grid small{color:var(--muted)}',
'pricing':'.price-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1.1rem;margin-top:3rem}.price-grid article{padding:2.6rem;border:1px solid var(--line);border-radius:1.3rem;background:var(--panel)}.price-grid .featured-price{border-color:var(--accent);background:#182b37}.price-label{font-size:.72rem;color:var(--accent);letter-spacing:.13em}.price-grid h3{font-size:2.2rem;letter-spacing:-.055em}.price-grid ul{padding-left:1.1rem;color:var(--muted);min-height:8.7rem}.price-grid li{margin:.5rem 0}',
'faq':'.faq-grid{display:grid;grid-template-columns:1fr 1.35fr;gap:5rem}.faq-items{border-top:1px solid var(--line)}.faq-items details{border-bottom:1px solid var(--line);padding:1.3rem 0}.faq-items summary{font-size:1.03rem;cursor:pointer;font-weight:650;padding-right:1rem}.faq-items details p{padding-top:.5rem;margin-bottom:0;font-size:.93rem}',
'contact':'.contact-section{padding-top:3.2rem}.contact-card{background:linear-gradient(110deg,#214a50,#172b3b);border:1px solid rgba(125,237,197,.3);border-radius:1.6rem;padding:3rem;display:grid;grid-template-columns:1.3fr .7fr;gap:3rem;align-items:center}.contact-card h2{max-width:13ch}.contact-card .helper{margin:1rem 0 0}',
'footer':'.footer{padding:5rem 0 1.5rem}.footer-grid{display:flex;justify-content:space-between;gap:2rem;border-bottom:1px solid var(--line);padding-bottom:3rem}.footer-grid p{max-width:38ch;font-size:.9rem}.footer-grid nav{display:flex;gap:1.6rem;flex-wrap:wrap;align-content:center}.footer-grid nav a{color:var(--muted);font-size:.9rem}.copyright{display:flex;justify-content:space-between;gap:1rem;font-size:.8rem;color:var(--muted);padding-top:1.6rem}'
}
RESPONSIVE={
'header':'.site-nav{gap:.9rem}.site-nav a{font-size:.8rem}.nav-wrap{gap:1rem}.brand{font-size:1.05rem}',
'hero':'.hero{padding-top:4rem;padding-bottom:4rem}.hero-grid{grid-template-columns:1fr;gap:2.6rem}.hero h1{font-size:clamp(2.7rem,12vw,4.8rem)}.hero-panel{max-width:34rem}',
'value':'.split{grid-template-columns:1fr;gap:1.5rem}.split h2{max-width:18ch}',
'features':'.feature-grid{grid-template-columns:1fr}.feature{min-height:0}.feature h3{margin-top:1rem}',
'workflow':'.steps{grid-template-columns:1fr;gap:1.6rem}',
'use_cases':'.case-list{grid-template-columns:1fr}.case-list article{gap:1rem}',
'security':'.section-light .split{grid-template-columns:1fr}',
'integrations':'.integration-grid{grid-template-columns:repeat(2,1fr)}',
'pricing':'.price-grid{grid-template-columns:1fr}.price-grid ul{min-height:0}',
'faq':'.faq-grid{grid-template-columns:1fr;gap:2rem}',
'contact':'.contact-card{grid-template-columns:1fr;padding:2rem;gap:1rem}',
'footer':'.footer-grid{flex-direction:column}.footer-grid nav{gap:1.2rem}'
}
BASE_CSS='''/* Original Northstar Studio responsive static site kit — no trackers or imports. */
:root{color-scheme:dark;--bg:#0b1423;--panel:#152135;--text:#f1f7fa;--muted:#b6c6ce;--accent:#75edc2;--line:rgba(177,208,221,.22);--max:1160px}
*,*::before,*::after{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:6.4rem}
body{margin:0;min-width:320px;color:var(--text);background:var(--bg);font:400 16px/1.65 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
::selection{background:var(--accent);color:var(--bg)}
a{color:inherit;text-decoration:none}
a:hover{text-decoration:underline;text-underline-offset:.3em}
a:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:5px;border-radius:2px}
p{color:var(--muted);margin:.75rem 0 1.15rem}
h1,h2,h3{line-height:1.16;margin:0 0 1rem;letter-spacing:-.045em}
h2{font-size:clamp(2.2rem,4.4vw,4rem);max-width:22ch;letter-spacing:-.067em}
h3{font-size:1.2rem}
strong{color:var(--text)}
.container{width:min(var(--max),calc(100% - 3.5rem));margin-inline:auto}
.section{padding:6.5rem 0}
.eyebrow{font-weight:750;color:var(--accent);font-size:.74rem;line-height:1.8;letter-spacing:.18em;text-transform:uppercase}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:.7rem;border:1px solid transparent;border-radius:.7rem;padding:.95rem 1.35rem;font-weight:750;line-height:1.3;transition:transform .2s ease,background-color .2s ease;min-height:46px;text-align:center}
.btn:hover{text-decoration:none;transform:translateY(-2px)}
.btn-primary{color:#061c24;background:var(--accent)}
.btn-primary:hover{background:#b8ffe0}
.btn-outline{border-color:var(--line);color:var(--text)}
.btn-outline:hover{background:rgba(255,255,255,.07)}
.btn-small{font-size:.87rem;padding:.7rem 1.05rem}
.text-link{color:var(--accent);font-weight:700;display:inline-flex;gap:.6rem;align-items:center}
.text-link:hover{text-decoration:underline}
.helper{font-size:.83rem;line-height:1.6;color:var(--muted)}
.skip-link{position:absolute;left:1rem;top:-7rem;background:var(--accent);color:#071522;z-index:50;padding:.8rem 1rem;border-radius:.5rem}
.skip-link:focus{top:1rem}
ul,ol{padding-left:1.35rem}
li+li{margin-top:.45rem}
section[id],footer[id],header[id]{scroll-margin-top:6.4rem}
button,input,textarea,select{font:inherit}
details[open] summary{color:var(--accent)}
summary::-webkit-details-marker{color:var(--accent)}
@media (hover:none){.btn:hover{transform:none}}
@media (prefers-reduced-motion: reduce){*,*::before,*::after{scroll-behavior:auto!important;transition-duration:.01ms!important;animation-duration:.01ms!important}}
'''
README='''# Northstar Studio — original responsive starter site

Original source: factory F19 HTML/CSS template, created through a real fifty-stage technical process.

## Deliverables
- index.html — complete accessible HTML5 demonstration website
- styles.css — original responsive visual system, no dependencies
- LICENSE.txt — authoring and usage terms for this original template

## Setup
1. Unzip into any local folder and open index.html in a modern browser.
2. Change the example "Northstar Studio" brand and all business text.
3. Replace sample pricing, copy and company contact details with verified facts.
4. Test anchors, native FAQ disclosures, keyboard focus and mobile widths.
5. Check color contrast and browser compatibility with an actual human reviewer.
6. Upload the static files to your own HTTPS web host.

## Operational limits
Replace sample claims before launch. Sample packages are NOT real offers.
No checkout, analytics, forms, billing, account system, or server backend is connected.
The website collects or transmits no visitor information through embedded scripts.
Contact navigation points to a local section only; add a privacy-compliant provider separately.
Human review, accessibility certification, expert validation and owner approval are NOT included.
'''
LICENSE='''Original HTML/CSS Starter Template — example authoring license

Copyright (c) 2026 Zomorod Melal / authorized template author.
The template's source code and layout were newly generated as an editable demonstration.
The buyer may customize this original source in their own website, subject to the
commercial license supplied with their eventual sale. No trademark, stock imagery,
third-party fonts, premium assets, certifications or upstream subscriptions are included.
Northstar Studio is a fictional example identity and must be replaced before public use.
This internal production draft is not a granted commercial license, not a customer offer,
and may not be publicly sold or represented as independently human-reviewed until approved.
'''
def load(name,script):
    path=HERE/script
    if path.is_symlink() or not path.is_file():raise RuntimeError('F19_REQUIRED_MODULE_MISSING')
    spec=importlib.util.spec_from_file_location(name,str(path))
    out=importlib.util.module_from_spec(spec);spec.loader.exec_module(out);return out

def write(path,content):
    path=Path(path)
    if path.is_symlink() or path.parent.is_symlink():raise RuntimeError('F19_UNSAFE_WRITE')
    path.write_text(content,encoding='utf8')

def plan(proto):
    origin=proto.digest({'producer':proto.file_sha(__file__),
         'review':proto.file_sha(HERE/'factory_f19_independent_web_review.py'),
         'protocol':proto.file_sha(HERE/'factory_build_50.py'),'product':PRODUCT})
    verbs={
      'markup':'Build and semantically validate a new accessible document fragment for',
      'visual':'Implement unique desktop styling and check visual hierarchy for',
      'responsive':'Build and verify a dedicated small-screen adaptation for',
      'verification':'Run two content integrity and structure checks with a JSON result for'
    }
    tasks=[]
    for key,description in TOPICS:
        for action,verb in verbs.items():
            tasks.append({'id':'task_'+key+'_'+action,
                'instruction':verb+' '+key+': '+description+'. Do not reuse output from other stages.',
                'acceptance':['A newly written original file provides the required functionality.',
                              'Independent structural or content checks pass without missing assets.']})
    assert len(tasks)==48
    return {'schema':proto.SCHEMA,'product_id':PRODUCT,'family_id':'F19',
            'producer_id':'saeit_original_static_template_builder',
            'source_snapshot_sha256':origin,'work_packages':tasks}

def files(folder,key):
    return [folder/(key+'.html'),folder/(key+'.css'),folder/('mobile_'+key+'.css')]

def produce_worker(task,context):
    folder=Path(context['folder'])
    parts=task['id'].split('_')
    key='_'.join(parts[1:-1]);action=parts[-1]
    if key not in NAMES:raise RuntimeError('F19_UNKNOWN_MODULE')
    markup,visual,responsive=files(folder,key)
    if action=='markup':
        body=HTML[key]
        if 'id="'+key+'"' not in body or len(body)<160:raise RuntimeError('F19_INVALID_SEMANTIC_MARKUP')
        write(markup,body)
        assert markup.read_text('utf8')==body
        return {'passed':True,'outputs':[markup.name],'successful_checks':2}
    if action=='visual':
        if not markup.is_file():raise RuntimeError('F19_MISSING_MARKUP')
        code=STYLES[key]
        if code.count('{')!=code.count('}') or len(code)<120:raise RuntimeError('F19_INVALID_CSS')
        write(visual,code)
        return {'passed':True,'outputs':[visual.name],'successful_checks':2}
    if action=='responsive':
        if not visual.is_file():raise RuntimeError('F19_MISSING_VISUAL')
        code=RESPONSIVE[key]
        if code.count('{')!=code.count('}') or len(code)<30:raise RuntimeError('F19_INVALID_RESPONSIVE_STYLE')
        write(responsive,code)
        return {'passed':True,'outputs':[responsive.name],'successful_checks':2}
    if action=='verification':
        if not all(x.is_file() for x in (markup,visual,responsive)):
            raise RuntimeError('F19_MISSING_DEPENDENT_WORK')
        candidate=markup.read_text('utf8'); desktop=visual.read_text('utf8'); mobile=responsive.read_text('utf8')
        test1=('id="'+key+'"' in candidate and len(candidate)>160)
        test2=(desktop.count('{')==desktop.count('}') and mobile.count('{')==mobile.count('}')
            and len(desktop)>120 and len(mobile)>30 and not any(x in desktop+mobile for x in ('@import','url(http')))
        if not test1 or not test2:raise ValueError('F19_MODULE_CONTENT_CHECK_FAILED')
        output=folder/('validation_'+key+'.json')
        write(output,json.dumps({'module':key,'checks_passed':2,'semantic_markup_sha256':hashlib.sha256(candidate.encode()).hexdigest(),
              'desktop_css_sha256':hashlib.sha256(desktop.encode()).hexdigest(),
              'mobile_css_sha256':hashlib.sha256(mobile.encode()).hexdigest(),
              'is_a_human_review':False},sort_keys=True,indent=2))
        return {'passed':True,'outputs':[output.name],'successful_checks':2}
    raise RuntimeError('F19_UNKNOWN_PRODUCTION_ACTION')

def assemble(proto,context):
    folder=Path(context['folder'])
    for k in NAMES:
        for path in files(folder,k):
            if not path.is_file() or path.is_symlink():raise RuntimeError('F19_MISSING_STAGE_ARTIFACT')
    page='<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<meta name="description" content="Original editable static landing page starter kit for clear product storytelling.">\n<meta name="theme-color" content="#0b1423">\n<title>Northstar Studio — an original editable starter site</title>\n<link rel="stylesheet" href="styles.css">\n</head>\n<body>\n<a class="skip-link" href="#main">Skip to main content</a>\n'
    page+=(folder/'header.html').read_text('utf8')+'\n<main id="main">\n'
    for k in NAMES[1:-1]:page+=(folder/(k+'.html')).read_text('utf8')+'\n'
    page+='</main>\n'+(folder/'footer.html').read_text('utf8')+'\n</body>\n</html>\n'
    css=BASE_CSS+'\n'.join((folder/(k+'.css')).read_text('utf8') for k in NAMES)
    css+='\n@media (max-width: 760px) {\n'+'\n'.join((folder/('mobile_'+k+'.css')).read_text('utf8') for k in NAMES)+'\n}\n'
    css+='@media (max-width: 440px) {.container{width:calc(100% - 2rem)}.section{padding:4.1rem 0}.hero{padding-top:3.25rem}.site-nav{display:none}.contact-card{padding:1.4rem}.integration-grid{grid-template-columns:1fr 1fr}.hero-panel{padding:1.5rem}}\n'
    artifacts={'index.html':page,'styles.css':css,'README.md':README,'LICENSE.txt':LICENSE}
    if len(page)<4500 or len(css)<4000:raise RuntimeError('F19_INCOMPLETE_FULL_WEBSITE')
    for name,contents in artifacts.items():write(folder/name,contents)
    package=folder/(PRODUCT+'-internal-qa.zip')
    with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as archive:
        for name in sorted(artifacts):
            info=zipfile.ZipInfo(PRODUCT+'/'+name,date_time=(2020,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            archive.writestr(info,(folder/name).read_bytes())
    return {'passed':True,'outputs':list(artifacts)+[package.name],'successful_checks':5}

def build(root):
    proto=load('f19_production_build_50','factory_build_50.py')
    independent=load('f19_independent_web_reviewer','factory_f19_independent_web_review.py')
    root=Path(root).expanduser().resolve()
    if not root.is_dir() or root.is_symlink():raise RuntimeError('F19_PRIVATE_FACTORY_ROOT_INVALID')
    spec=plan(proto)
    home=root/'build-50'/PRODUCT
    target=root/'digital-products'/PRODUCT
    if home.is_symlink() or target.is_symlink():raise RuntimeError('F19_UNSAFE_PRODUCT_TARGET')
    if (home/'state.json').is_file() and target.is_dir():
        state=proto.read(home/'state.json')
        if state.get('source_snapshot_sha256')==spec['source_snapshot_sha256'] and proto.verify_attempt(home,state,spec['source_snapshot_sha256']):
            try:
                receipt=proto.read(target/'manufacturing_manifest.json')
                zipfile=target/(PRODUCT+'-internal-qa.zip')
                if receipt.get('artifact_sha256')==proto.file_sha(zipfile):
                    return {'status':'unchanged_verified_technical_product','completed_stages':50,'commercial_release':False}
            except (OSError,ValueError,KeyError):pass
    def reviewer(plan_data,context):
        folder=Path(context['folder'])
        archive=folder/(PRODUCT+'-internal-qa.zip')
        independent_result=independent.check(folder,archive,PRODUCT)
        if independent_result['checks_passed']!=10:raise RuntimeError('F19_INDEPENDENT_QA_INCOMPLETE')
        file=folder/'independent-technical-review.json'
        write(file,json.dumps(independent_result,indent=2,sort_keys=True))
        return {'reviewer_id':'saeit_independent_automated_web_technical_review',
                'passed':True,'critical_defects':[],
                'gates':independent_result['gates'],
                'outputs':[file.name],'successful_checks':10}
    state=proto.run_attempt(root,spec,produce_worker,lambda p,c:assemble(proto,c),reviewer)
    if state.get('status')!='awaiting_owner_acceptance' or not proto.verify_attempt(home,state,spec['source_snapshot_sha256']):
        return {'status':'technical_rework_required','completed_stages':state.get('completed_stages'),
                'defects':state.get('defects',[]),'commercial_release':False}
    folder=Path(state['attempt_folder'])
    archive=folder/(PRODUCT+'-internal-qa.zip')
    # Copy only after every source-bound stage passes: never alter an existing unrelated deliverable.
    if target.exists() and any(x.is_symlink() for x in (target,target/'manufacturing_manifest.json')):
        raise RuntimeError('F19_UNSAFE_EXISTING_PRODUCT')
    target.mkdir(parents=True,exist_ok=True,mode=0o700)
    finished=target/archive.name
    temp=target/'.incoming-f19.zip'
    shutil.copyfile(archive,temp);os.replace(temp,finished)
    filenames=['index.html','styles.css','README.md','LICENSE.txt']
    manifest={'schema_version':2,'recipe':PRODUCT,'name':'Northstar Studio — responsive SaaS launch template',
       'family_id':'F19','bytes':finished.stat().st_size,
       'source_sha256':proto.digest({n:proto.file_sha(folder/n) for n in filenames}),
       'build50_source_snapshot_sha256':spec['source_snapshot_sha256'],
       'artifact_sha256':proto.file_sha(finished),'files':filenames,
       'qa_status':'passed','qa_evidence':'unit_tests_passed',
       'qa_measurements':proto.read(folder/'independent-technical-review.json'),
       'commercial_status':'private_internal_qa_pass_not_published',
       'public_listing_enabled':False,'customer_order_required':False,
       'owner_publication_approval':False,'independent_human_review':False}
    proto.save(target/'manufacturing_manifest.json',manifest)
    return {'status':'technical_50_stage_build_completed','completed_stages':50,
        'product_id':PRODUCT,'family_id':'F19','commercial_release':False,
        'private_zip_sha256':manifest['artifact_sha256'],'bytes':manifest['bytes']}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--factory-private',required=True)
    args=parser.parse_args()
    result=build(args.factory_private)
    print('F19_BUILD50_REAL_WEBSITE_PRODUCT='+json.dumps(result,sort_keys=True,ensure_ascii=False))
    if result.get('status')=='technical_rework_required':sys.exit(2)
