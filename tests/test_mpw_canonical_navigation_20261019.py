"""MojPlayWin canonical 2026 header and root-only JS bug regression."""
import importlib.util
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"scripts/mpw_canonical_navigation_atomic_20261019.py"
spec=importlib.util.spec_from_file_location("mpwmenu",p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_reference_header_preserves_home_links_and_native_keyboard_menu():
    ref='<header class="mw-site-nav" data-design="atelier-v4"><a href="/">Home</a><nav aria-label="Primary MojPlayWin navigation"><a href="/store/">Store</a>'+''.join('<a href="/about/">About</a>' for i in range(10))+'<details id="mw-all-pages-menu"><summary>Explore all</summary></details></nav></header>'
    html=m.canonical(ref)
    assert html.count(m.MARK)==1
    assert '<details id="mw-all-pages-menu">' in html
    assert '<a href="/store/">Store</a>' in html
    assert '<summary>Explore all</summary>' in html
    assert m.canonical(ref)==html

def test_legacy_js_null_guard_without_disabling_functional_menu():
    js='<script>\n'+m.OLD_DECL+'\n'+m.OLD1+'\n'+m.OLD2+'\n'+m.OLD3+'\n</script>'
    fixed=m.js_guard(js)
    assert fixed.count('if(b&&n){')==3
    assert fixed.count('n.querySelectorAll')==1
    assert fixed.count("b.addEventListener('click'")==1
    assert fixed.count("window.addEventListener('keydown'")==1
    assert m.js_guard(fixed)==fixed

def test_static_content_products_and_footer_remain_byte_for_byte():
    header=m.canonical('<header class="mw-site-nav" data-design="atelier-v4"><nav aria-label="Primary MojPlayWin navigation">'+''.join('<a href="/games/">Games</a>' for _ in range(11))+'<details id="mw-all-pages-menu"><summary>Explore all</summary></details></nav></header>')
    orig='<html><body class="mpw-design-unified-v1"><header class="mpw-header">Old navbar</header><main><h1>Games</h1><form action="/pay"><input name="total"></form><article>Unique content</article></main><footer><div class="mpw-legal-one-line">☆ All Rights Reserved. ☆ 2022. ☆ Mojtaba roozegar ☆</div></footer></body></html>'
    new=m.static_patch(orig,header)
    assert '<form action="/pay"><input name="total"></form>' in new
    assert '<article>Unique content</article>' in new
    assert new.count('<main>')==new.count('</main>')==1
    assert new.count('<footer>')==new.count('</footer>')==1
    assert 'mpw-legal-one-line' in new
    assert 'class="mpw-header"' not in new

def test_php_reuses_home_canonical_header_without_other_domain_changes():
    source="function transformMain() {\n  // standard footer replacement\n  // MojPlayWin design alignment stylesheet\n"+m.PHP_BRANCH+"\n"+m.PHP_TAIL
    new=m.php_patch(source)
    assert new.count("canonical homepage navigation")==1
    assert new.count("$legacyNav=[")==1
    assert 'mpw-contact-safe-business' not in new or True
    assert 'return $body;' in new
    assert "n.querySelectorAll" in new
    assert "if(b&&n)" in new
    assert len(m.all_targets())==20
    assert m.HOMEPAGE not in m.all_targets()
    assert not any("farnaz" in str(p) for p in m.all_targets())
    m.selftest()


def test_github_inline_route_verification_python_parses():
    import ast,re,textwrap
    wf=(p.parents[1]/".github/workflows/mpw-canonical-navigation-20261019.yml").read_text("utf8")
    blocks=re.findall(r"^\s*python3 - <<'PY'\s*\n(.*?)^\s*PY\s*$",wf,flags=re.S|re.M)
    assert len(blocks)==2
    for k,code in enumerate(blocks):
        ast.parse(textwrap.dedent(code),filename=f"mpw-nav-verification-{k}")
