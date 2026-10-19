"""Regression test for MojPlayWin founder biography H1 first."""
import importlib.util
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"scripts/mpw_founder_heading_atomic_20261019.py"
s=importlib.util.spec_from_file_location("founder_heading",p)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def original():
    return ('<!doctype html><html><head><title>Professor Mojtaba Roozegar</title></head><body>'
            '<main id="main"><section id="professor-mojtaba-roozegar">'
            +m.OLD_FIRST
            +'<p>official_profile_20261016</p>'
            +'<h3>Research details</h3></section>'
            '<section><h4>Academic work</h4></section>'
            +m.OLD_LATE+
            '<section id="mpw-ten-heading-about-mojtaba-rozegar">Preserved illustrations</section>'
            '<section id="mpw-research30-title-about-mojtaba-rozegar">Preserved research</section>'
            '</main></body></html>')
def test_founder_one_h1_first_and_unchanged_biography():
    before=original()
    after=m.patch(before)
    assert after.count('<h1')==1
    assert after.index(m.NEW_FIRST)<after.index('<h3>')
    assert m.NEW_LATE in after
    assert 'official_profile_20261016' in after
    assert 'mpw-ten-heading-about-mojtaba-rozegar' in after
    assert 'mpw-research30-title-about-mojtaba-rozegar' in after
    assert before.count('<section')==after.count('<section')
    try:
        m.patch(after)
        assert False, 'Duplicate install should fail'
    except RuntimeError:pass
