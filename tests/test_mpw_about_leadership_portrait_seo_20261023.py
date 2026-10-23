"""No-network, no-host-write checks for the isolated MojPlayWin About repair."""
import importlib.util
import json
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "scripts/mpw_about_leadership_portrait_seo_20261023.py"
SPEC = importlib.util.spec_from_file_location("mpw_about_leadership_photo", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def source():
    about = {
        "@context": "https://schema.org",
        "@type": "AboutPage",
        "url": "https://mojplaywin.com/about/",
        "mainEntity": {
            "@type": "Organization",
            "name": "MojPlayWin",
            "founder": {"@type": "Person", "name": "Mojtaba Roozegar", "url": "https://mojplaywin.com/mojtaba.roozegar/"},
        },
    }
    return (
        '<!doctype html><html><head><link rel="canonical" href="https://mojplaywin.com/about/">'
        '<script type="application/ld+json">'
        + json.dumps({"@context": "https://schema.org", "@graph": [{"@type": "WebSite"}]})
        + '</script><script type="application/ld+json">'
        + json.dumps(about)
        + '</script></head><body><main><h1>About MojPlayWin</h1>'
        + '<section id="mpw-founder-spotlight-20261019"><img src="'
        + MODULE.PORTRAIT + '"></section>'
        + '<section class="mw-section mw-about-copy" id="leadership" aria-labelledby="leadership-title">'
        + '<span class="mw-kicker">07 / FOUNDER &amp; LEADERSHIP</span>'
        + '<h2 id="leadership-title">Mojtaba Roozegar</h2>'
        + '<p>Founder and CEO</p></section>'
        + '<div>' + 'class="mpw-profile-indicator"'*30 + '</div>'
        + '<div>' + 'class="mpw-seven-item"'*6 + '</div>'
        + '</main><!-- MPW_ABOUT_COMPANY_SEMANTIC_20261019_V2 --></body></html>'
    )


def test_official_photo_is_above_exact_section_seven_name():
    result = MODULE.compose(source())
    start, end = MODULE.leadership_span(result)
    leadership = result[start:end]
    assert leadership.index(MODULE.PORTRAIT) < leadership.index('id="leadership-title"')
    assert leadership.count('<img ') == 1
    assert 'max-width:360px' in result
    assert 'Mojtaba Roozegar' in leadership
    assert result.count('<h1>') == 1


def test_schema_preserves_brand_and_connects_aliases_to_existing_person():
    result = MODULE.compose(source())
    data = json.loads(result.split('<script type="application/ld+json">')[2].split('</script>')[0])
    assert data['mainEntity']['name'] == 'MojPlayWin'
    person = data['mainEntity']['founder']
    assert person['@id'] == MODULE.PERSON_ID
    assert person['image'].endswith(MODULE.PORTRAIT)
    assert {'مجتبی روزگار', 'روزگار', 'Roozegar', 'Dr.mojtaba.rozegar'} <= set(person['alternateName'])
    assert person['url'] == 'https://mojplaywin.com/mojtaba.roozegar/'
    assert result.count('rel="canonical"') == 1


def test_fails_closed_if_targets_missing_or_already_patched():
    base = source()
    for document, keyword in (
        (base.replace('https://mojplaywin.com/about/"', 'https://wrong.example/"', 1), 'canonical'),
        (base.replace('07 / FOUNDER', '08 / FOUNDER'), 'section 07'),
        (MODULE.compose(base), 'already installed'),
    ):
        try:
            MODULE.compose(document)
        except RuntimeError as exc:
            assert keyword in str(exc)
        else:
            raise AssertionError('Expected guarded failure: ' + keyword)


def test_no_unrelated_sections_or_links_changed():
    base = source()
    result = MODULE.compose(base)
    assert result.count('class="mpw-profile-indicator"') == base.count('class="mpw-profile-indicator"')
    assert result.count('class="mpw-seven-item"') == base.count('class="mpw-seven-item"')
    assert result.count('id="mpw-founder-spotlight-20261019"') == 1
    assert result.count('MPW_ABOUT_COMPANY_SEMANTIC_20261019_V2') == 1


class SmokeTests(unittest.TestCase):
    def test_photograph(self):
        test_official_photo_is_above_exact_section_seven_name()

    def test_identity(self):
        test_schema_preserves_brand_and_connects_aliases_to_existing_person()

    def test_guard(self):
        test_fails_closed_if_targets_missing_or_already_patched()

    def test_scope(self):
        test_no_unrelated_sections_or_links_changed()


if __name__ == '__main__':
    unittest.main()
