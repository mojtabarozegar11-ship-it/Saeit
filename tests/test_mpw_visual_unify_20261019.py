"""Synthetic mutation and provenance tests for MojPlayWin visual consistency."""
from pathlib import Path
import importlib.util
SRC=Path(__file__).resolve().parents[1]/"scripts/mpw_visual_unify_atomic_20261019.py"
spec=importlib.util.spec_from_file_location("mpw_vis",SRC)
x=importlib.util.module_from_spec(spec);spec.loader.exec_module(x)

def sample(kind="mw-site-nav",body='class="old page theme-green"'):
    return ('<!doctype html><html><head><title>Research</title>'
            '<meta name="theme-color" content="#103b2d"></head>'
            '<body '+body+'><header class="'+kind+'"><a href="/">Home</a>'
            '</header><main id="main"><h1>Research</h1><form action="/search/">'
            '<input type="text" name="q"></form><article>Original research content</article>'
            '</main><footer class="mw-site-footer"><div class="mpx-bottom-bar">'
            '<span class="mpw-legal-one-line">'
            '☆ All Rights Reserved. ☆ 2022. ☆ Mojtaba roozegar ☆'
            '</span></div></footer></body></html>')

def test_modern_and_legacy_additive_only_css():
    for kind in ("mw-site-nav","mpw-header"):
        before=sample(kind)
        after=x.static_patch(before)
        assert after.count(x.URL)==1
        assert after.count(x.MARK)==1
        assert 'content="#08090b"' in after
        assert '<h1>Research</h1>' in after
        assert '<form action="/search/">' in after
        assert 'Original research content' in after
        assert after.count('☆ All Rights Reserved. ☆ 2022. ☆ Mojtaba roozegar ☆')==1
        assert '<header class="'+kind+'">' in after
        assert 'class="old page theme-green '+x.MARK+'"' in after
        try:
            x.static_patch(after)
            assert False, "Patch must fail closed on a second installation"
        except RuntimeError:
            pass

def test_main_php_transformation_is_confined_to_existing_tail():
    prior=('<?php\nfunction transformMain($body){\n'
           '// standard footer replacement\n'
           '// mpw-contact-safe-business-20261019\n'
           +x.PHP_ANCHOR+'\n')
    outcome=x.php_patch(prior)
    assert outcome.startswith(prior[:prior.index(x.PHP_ANCHOR)])
    assert outcome.count('MojPlayWin design alignment stylesheet')==1
    assert outcome.count('preg_replace_callback')==2
    assert outcome.count(x.MARK)==3
    assert "return $body;" in outcome
    assert 'function layoutParts(): array {' in outcome
    assert "mpw-contact-safe-business-20261019" in outcome

def test_main_only_inventory_and_no_legacy_menu_visibility_override():
    assert len(x.STATIC)==19
    assert len(x.paths())==20
    assert str(x.HOMEPAGE).endswith('/production-home-20261017.html')
    assert x.HOMEPAGE not in x.paths()
    assert '/.htaccess' not in [str(q) for q in x.paths()]
    assert 'farnaz' not in '\n'.join(str(q) for q in x.paths())
    assert 'mpw-design-unified-v1' in x.CSS
    assert '.mpw-header .mpw-nav{display:flex' not in x.CSS
    assert 'mw-site-nav' in x.CSS
    assert 'mw-page-hero' in x.CSS
    assert 'prefers-reduced-motion' in x.CSS
    x.selftest()
