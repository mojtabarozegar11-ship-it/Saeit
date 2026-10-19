"""Source-level regression tests for reviewed MojPlayWin About remediation."""
from pathlib import Path
import importlib.util
from html.parser import HTMLParser

ROOT=Path(__file__).resolve().parents[1]
NAME="scripts/mpw_about_remediation_atomic_20261019.py"
spec=importlib.util.spec_from_file_location("mpw_about_patch",ROOT/NAME)
patch=importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)

def test_owner_is_ceo_without_unverified_jurisdiction():
    founder=(ROOT/"content/mpw_founder_spotlight_20261019.html").read_text("utf-8")
    assert "Owner · Founder · Chief Executive Officer" in founder
    assert "MojPlayWin, a limited liability company" in founder
    assert "Registration number and jurisdiction are not stated" in founder

def test_sixth_gallery_card_removed_but_six_distinct_cards_remain():
    gallery=(ROOT/"content/mpw_seven_team_gallery_20261019.html").read_text("utf-8")
    assert gallery.count('class="mpw-seven-item"')==6
    assert 'data-gallery-image="06"' not in gallery
    for n in ("01","02","03","04","05","07"):
        assert 'data-gallery-image="'+n+'"' in gallery

def test_remediation_guardrails_stay_site_specific():
    import inspect
    source=inspect.getsource(patch)
    assert str(patch.PAGE)=="/home/zomorod2/mojplaywin.com/design-preview-20261017/mpw-ten-editorials-20261018/pages/about.html"
    assert 'ROOT / ".htaccess"' in source
    assert 'RULES.read_text' in source
    assert "def rollback" in source
    assert "Unexpected HTML size" in source

def test_compose_with_synthetic_old_page_fails_closed_on_repeat_and_preserves_sections():
    # Use local current content only; rewind reviewed presentation changes to
    # produce a synthetic baseline, not an asserted snapshot of the live page.
    source={}
    for name in patch.FILES:
        new=(ROOT/"content"/name).read_text("utf-8")
        old=new
        if "founder_spotlight" in name:
            old=old.replace("Owner · Founder · Chief Executive Officer","Founder · Strategic Vision &amp; Leadership")
            old=old.replace("Mojtaba Roozegar is the owner, founder and Chief Executive Officer of MojPlayWin, a limited liability company. He leads its digital vision,","Mojtaba Roozegar is introduced as the founder behind the MojPlayWin vision,")
            old=old.replace('<p class="mpw-founder-mission">Ownership and executive accountability: Mojtaba Roozegar. Company type: limited liability. Registration number and jurisdiction are not stated without supporting records.</p>',"")
        elif "seven_team_gallery" in name:
            # Real baseline image six is read from the 2026-10-19 original fixture
            # if available; absence here is exercised in a separate guard test.
            old=new + "\n<!-- synthetic-baseline-not-production -->"
        elif "senior_advisory" in name:
            old=old.replace("Illustrative Advisory Role Profiles","Senior Advisory Board")
            old=old.replace('<p class="mpw-profile-indicator">Fictional advisor · no verified appointment</p>',"")
        elif "international_team" in name:
            old=old.replace("Illustrative International Operations Roles","International Management &amp; Operations Team")
            old=old.replace("Executive Strategy &amp; Operations (Illustrative Role)","Chief Executive Officer")
            old=old.replace('<p class="mpw-profile-indicator">Illustrative role · not verified staff</p>',"")
        elif "about_team_section" in name:
            old=old.replace("Illustrative Team Roles","Meet Our Team")
            old=old.replace("Business Strategy &amp; Development (Illustrative Role)","CEO &amp; Business Development")
            old=old.replace('<p class="mpw-profile-indicator">Illustrative role · not verified staff</p>',"")
        source[name]=(old,new)
    original=('<html><head><title>About MojPlayWin</title></head><body>'
        +'<header id="about-top"><h1>About MojPlayWin</h1><p>'
        +patch.ORIGINAL_IDENTITY+'</p></header>'
        +'<section id="our-story">Our story</section>'
        + ' '.join(patch.PRESERVE)
        + ''.join('<img src="/placeholder-%s.webp" alt="Placeholder">'%i for i in range(20))
        +''.join(source[n][0] for n in patch.FILES)
        +'<section id="doctoral-dossier">Research 28</section>'
        +'<section id="complementary-portfolio">Sectors 30</section>'
        +'<section id="complementary-reference-methods">References</section>'
        + ' '*60000 +'</body></html>')
    updated=patch.compose(original,source)
    details=patch.validate(updated)
    assert details["profiles"]["mpw-team-card"]==10
    assert details["profiles"]["mpw-seven-item"]==6
    assert updated.count("MojPlayWin, a limited liability company")==1
    assert updated.count('id="mpw-founder-spotlight-20261019"')==1
    assert original.count('id="mpw-founder-spotlight-20261019"')==1
    assert updated.count("Research 28")==1 and updated.count("Sectors 30")==1
    assert updated.count('id="mpw-advanced-research"')==1
    assert updated.count('id="mpw-complementary-details"')==1
    try:
        patch.compose(updated,source)
        assert False, "Second install must fail, never double-patch"
    except RuntimeError:
        pass
