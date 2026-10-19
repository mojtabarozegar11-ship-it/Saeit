"""Synthetic, production-safe regression tests for a two-page static repair."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("mpw",ROOT/"scripts/mpw_about_company_consolidated_20261019.py")
mpw=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(mpw)
def about():
    head='''<!doctype html><html><head><title>About MojPlayWin</title><meta name="description" content="old description"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>'''
    founder='''<section id="mpw-founder-spotlight-20261019"><h2>Mojtaba Roozegar</h2></section>'''
    doc=('<main id="main"><div class="mpw-company-about"><header id="about-top"><h2>Our complete company profile</h2></header>'
          + founder
          + '<p>MPW_ABOUT_REMEDIATION_20261019_V1 MPW_COMPANY_FOUNDER_POLISH_20261019_V1</p>'
          + '<p>SPECIALISM 28 COMPLEMENTARY SPECIALISM 30 official_profile_20261016</p>'
          + ''.join('<section class="mpw-profile-indicator">Illustrative</section>' for _ in range(30))
          + ''.join('<li class="mpw-seven-item">Card</li>' for _ in range(6))
          + '<details id="mpw-advanced-research"><summary>Research</summary><p>Preserve</p></details>'
          + '<details id="mpw-complementary-details"><summary>Industry</summary><p>Preserve</p></details></div>'
          + '<section class="mpw-page-hero"><h1>About MojPlayWin</h1></section>'
          + '<p>'+'Unchanged research evidence '*4100+'</p></main>')
    return head+doc+'</body></html>'
def company():
    head='''<!doctype html><html><head><title>About MojPlayWin | MojPlayWin</title><meta name="description" content="A digital-first company bringing research, modern technology, games, and education into one growing destination."><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#103b2d"><link rel="canonical" href="https://mojplaywin.com/company/"></head><body class="site-standard-v2 mojplaywin-section">'''
    banner='''<section id="mpw-company-owner-crosslink-20261019"><h2 id="mpw-company-owner-title">A limited liability company owned and led by Mojtaba Roozegar</h2><p>MPW_COMPANY_FOUNDER_POLISH_20261019_V1</p></section>'''
    nav='''<header class="mw-site-nav"><img src="/design-preview-20261017/static/site/mojplaywin-atelier/official-coin-80.3ea52711f49d.webp" alt=""><nav><a href="/company/">About</a><h3>Discover</h3></nav></header>'''
    core='''<div class="mw-shell"><section class="mw-page-hero"><h1>About MojPlayWin</h1><img src="/static/site/heroes/platform-home.4dd3ab6a401d.webp" alt="About MojPlayWin"></section>'''+''.join('<div class="mpw-ten-card">Guide %s</div>'%i for i in range(10))+'</div>'
    return head+'<main id="main-content">'+banner+nav+core+'<p>'+'Full editorial research and case studies '*700+'</p></main></body></html>'

def test_two_pages_preserve_content_and_headings():
    a,b=mpw.compose(about(),company())
    outcome=mpw.validate_pair(a,b)
    assert outcome["about_headings_before_h1"]==0
    assert outcome["company_headings_before_h1"]==0
    assert a.index('<h1>About MojPlayWin</h1>') < a.index('id="mpw-founder-spotlight-20261019"')
    assert '<h2>MojPlayWin gaming and creative direction</h2>' in a
    assert 'Unchanged research evidence' in a
    assert 'id="mpw-business-contact-20261019"' in a and 'id="mpw-business-contact-20261019"' in b
    assert b.count('class="mpw-ten-card"')==10
    assert b.count('application/ld+json')==1
    assert 'Company Overview | MojPlayWin' in b
    assert '/static/site/mojplaywin-coin-logo.420e0d1f954b.png' in b
    assert 'theme-color" content="#050608"' in b
    assert 'width="1200" height="675"' in b
    assert 'About Us</a>' in b
    assert 'class="site-standard-v2 mojplaywin-section mpw-company-harmonized"' in b
    assert 'Business Partnership' in a and 'Business Partnership' in b

def test_repeated_patch_and_missing_evidence_fail_closed():
    a,b=mpw.compose(about(),company())
    for x,y in ((a,b),(about().replace("MPW_ABOUT_REMEDIATION_20261019_V1","lost"),company()),
                (about(),company().replace('class="mpw-ten-card"','class="changed"'))):
        try:
            mpw.compose(x,y)
            assert False,"Fail-closed check not enforced"
        except RuntimeError:
            pass

def test_existing_company_schema_is_preserved_and_not_duplicated():
    a=about()
    existing='<script type="application/ld+json" id="preexisting-company-schema">{"@context":"https://schema.org","@type":"Organization","name":"MojPlayWin"}</script>'
    b=company().replace("</head>",existing+"</head>")
    pa,pb=mpw.compose(a,b)
    mpw.validate_pair(pa,pb)
    assert existing in pb
    assert pb.count('type="application/ld+json"')==1
    assert "mpw-company-schema-20261019" not in pb
    assert 'property="og:description"' in pb
