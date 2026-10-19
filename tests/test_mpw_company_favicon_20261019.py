"""MojPlayWin Company favicon regression test."""
import importlib.util
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"scripts/mpw_company_favicon_atomic_20261019.py"
spec=importlib.util.spec_from_file_location("icon",p)
icon=importlib.util.module_from_spec(spec)
spec.loader.exec_module(icon)
def test_company_favicon_is_unique_and_no_content_is_deleted():
    original=('<html><head><link rel="icon" type="image/png" href="'+icon.PREVIOUS+'">'
              '</head><body><main><h1>Company</h1>'
              '<!-- MPW_ABOUT_COMPANY_SEMANTIC_20261019_V2 -->'
              +'<article class="mpw-ten-card">Preserved</article>'*10+'</main></body></html>')
    result=icon.patch(original)
    assert result.count(icon.CORRECT)==1
    assert icon.PREVIOUS not in result
    assert result.count('class="mpw-ten-card"')==10
    assert result.count(icon.MARK)==1
    try:
        icon.patch(result)
        assert False,"Reinstallation must not be possible"
    except RuntimeError:pass

def test_change_is_rejected_when_original_favicon_differs():
    for bad in ('<link rel="icon" href="/new-icon.png">',
                '<link rel="icon" href="/first.png"><link rel="icon" href="/second.png">'):
        document='<html><head>'+bad+'</head><body>MPW_ABOUT_COMPANY_SEMANTIC_20261019_V2</body></html>'
        try:
            icon.patch(document)
            assert False,"Unexpected favicon should refuse replacement"
        except RuntimeError:pass
