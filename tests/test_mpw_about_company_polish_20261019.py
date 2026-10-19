"""Unit tests for isolated MojPlayWin photo and company-banner refinement."""
from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/"scripts/mpw_about_company_polish_atomic_20261019.py"
spec=importlib.util.spec_from_file_location("mpw_polish",path)
polish=importlib.util.module_from_spec(spec)
spec.loader.exec_module(polish)

def fixture():
    about=('<html><head></head><body><main><h1>About MojPlayWin</h1>'
           '<!-- MPW_ABOUT_REMEDIATION_20261019_V1 -->'
           '<section id="mpw-founder-spotlight-20261019">'
           '<img src="'+polish.OLD_IMAGE+'" alt="'+polish.OLD_ALT+'">'
           '</section></main></body></html>')
    company=('<html><head><title>About MojPlayWin</title></head><body>'
             '<main id="main"><h1>Company</h1><section id="mpw-ten-illustrated-20261018">'
             + '<article class="mpw-ten-card">Preserved</article>'*10
             +'</section></main></body></html>')
    return about,company

def test_owner_photo_and_company_banner_are_additive_and_scope_limited():
    source=fixture()
    updated=polish.compose(*source)
    assert updated[0].count(polish.OWNER_IMAGE)==1
    assert polish.OLD_IMAGE not in updated[0]
    assert "owner and Chief Executive Officer" in updated[0]
    assert updated[1].count('class="mpw-ten-card"')==10
    assert 'id="mpw-company-owner-crosslink-20261019"' in updated[1]
    assert 'href="/about/"' in updated[1]
    assert 'limited liability company' in updated[1]
    assert updated[0].count('MPW_ABOUT_REMEDIATION_20261019_V1')==1
    try:
        polish.compose(*updated)
        assert False, "A repeated installation must not duplicate content"
    except RuntimeError:
        pass

def test_polish_rejects_unexpected_images_or_missing_corporate_cards():
    about,company=fixture()
    for a,c in ((about.replace(polish.OLD_IMAGE,"/changed.webp"),company),
                (about,company.replace('class="mpw-ten-card"', 'class="mpw-other-card"',1))):
        try:
            polish.compose(a,c)
            assert False, "Unexpected live content must be refused"
        except RuntimeError:
            pass
