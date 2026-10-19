"""Root-only Apache output filter must not modify nested site, POST or routing."""
import importlib.util
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"scripts/mpw_home_footer_root_filter_20261019.py"
spec=importlib.util.spec_from_file_location("mpwhomelegal",p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_exact_one_line_contract_and_home_only_filter():
    m.selftest()
    assert m.LINE=="☆ All Rights Reserved. ☆ 2022. ☆ Mojtaba roozegar ☆"
    assert m.BLOCK.count('REQUEST_URI')==1
    assert 'm#^/$#' in m.BLOCK
    assert 'Substitute "s|</body>|<script src=' in m.BLOCK
    assert '/design-preview-20261017/static/site/mpw-home-legal-footer-20261019.js' in m.BLOCK
    assert 'RewriteRule' not in m.BLOCK
    for sub in ("farnaz","saman","picm","taniya","zahra"):
        assert sub not in m.BLOCK
    assert "if(matched.length!==1)return;" in m.JS
    assert "bar.replaceChildren(span)" in m.JS
    assert "span.textContent='"+m.LINE+"'" in m.JS

def test_home_js_has_no_remote_dependencies_or_other_page_mutation():
    assert "window.location.pathname!=='/'" in m.JS
    assert "mojplaywin" in m.JS
    assert "document.querySelectorAll('footer')" in m.JS
    assert ".mpx-bottom-bar" in m.JS
    assert "white-space:nowrap" in m.JS
    assert ".createElement('script')" not in m.JS
    assert "fetch(" not in m.JS and "XMLHttpRequest" not in m.JS
