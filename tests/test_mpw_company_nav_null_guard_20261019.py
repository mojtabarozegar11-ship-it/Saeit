"""Verified Company-only fix of legacy JavaScript null navigation failure."""
import importlib.util
from pathlib import Path
source=Path(__file__).resolve().parents[1]/"scripts/mpw_company_nav_null_guard_atomic_20261019.py"
spec=importlib.util.spec_from_file_location("mpwcompanynav",source)
patcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(patcher)

def previous():
    return ('''<!doctype html><html><head><title>Company</title></head><body><main><h1>Company</h1>'''
      +'<section class="mpw-ten-card">Editorial guide</section>'*10
      +'<script>\n'+patcher.OLD_DECL+'\n'+patcher.OLD1+'\n'+patcher.OLD2+'\n'+patcher.OLD3+'\n</script>'
      +'<!-- MPW_ABOUT_COMPANY_SEMANTIC_20261019_V2 --></main></body></html>')

def test_guards_every_legacy_nav_usage_without_changing_company_content():
    before=previous()
    after=patcher.patch(before)
    assert after.count("if(b&&n){")==3
    assert patcher.OLD_DECL in after
    assert after.count('<section class="mpw-ten-card">Editorial guide</section>')==10
    assert after.count('<script>')==before.count('<script>')
    assert "MPW_COMPANY_NAV_NULL_GUARD_20261019" in after
    try:
        patcher.patch(after)
        assert False,"Duplicate patch must refuse to run"
    except RuntimeError:
        pass

def test_unexpected_existing_script_never_overwritten():
    for bad in (previous().replace(patcher.OLD2,"n?.querySelectorAll('a');"),
                previous().replace("MPW_ABOUT_COMPANY_SEMANTIC_20261019_V2","unknown")):
        try:
            patcher.patch(bad)
            assert False,"Unknown source must be rejected"
        except RuntimeError:
            pass
