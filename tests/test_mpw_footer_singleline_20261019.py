"""Regression for the MojPlayWin root-domain single-line rights bar."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/"scripts/mpw_footer_singleline_atomic_20261019.py"
spec=importlib.util.spec_from_file_location("mpwfooter",p)
foot=importlib.util.module_from_spec(spec)
spec.loader.exec_module(foot)
LINE="☆ All Rights Reserved. ☆ 2022. ☆ Mojtaba roozegar ☆"

def test_root_only_footer_source_and_no_regression_to_old_credit():
    template=(ROOT/"core/templates/mojplaywin/footer.html").read_text("utf-8")
    assert template.count(LINE)==1
    assert template.count('data-mpw-final-founder="true"')==1
    assert template.count('data-mpw-founder-source="Mojtaba Roozegar"')==1
    assert template.count('class="mpw-legal-one-line"')==1
    assert "white-space:nowrap" in template
    assert template.count("</footer>")==1
    assert "Privacy" in template and "Terms" in template and "Cookies" in template
    assert set(foot.STATIC)=={
       "about-mojtaba-rozegar","about","agents","company","economy","industry",
       "knowledge","market","research","services","studio",
       "ventures-agriculture","ventures-cafe-restaurant","ventures-carpets",
       "ventures-currency-crypto","ventures-ecommerce","ventures-fuel-station",
       "ventures-hospitality","ventures-jewelry-gold"}
    assert str(foot.TEMPLATE)=="/home/zomorod2/Saeit-staging/core/templates/mojplaywin/footer.html"
    assert len(foot.targets())==22
    assert str(foot.PHP_SHELL)=="/home/zomorod2/mojplaywin.com/design-preview-20261017/_mpw_dynamic_main_shell_20261019.php"
    assert str(foot.HOMEPAGE)=="/home/zomorod2/mojplaywin.com/design-preview-20261017/production-home-20261017.html"

def test_two_distinct_footer_types_keep_links_and_only_one_credit():
    foot.selftest()
    for f in (
      '<footer class="mw-site-footer"><div>MojPlayWin</div><nav><a href="/store/">Store</a></nav><div class="mpx-bottom-bar"><span>© 2022 MojPlayWin. All rights reserved.</span><span>Built for research</span><span class="mpw-copyright-founder">Mojtaba Roozegar</span></div></footer>',
      '<footer class="mpw-footer"><div><b>MojPlayWin</b></div><div><a href="/store/">Store</a></div><div><span>© MojPlayWin</span><a href="/privacy/">Privacy</a></div><span class="mpw-founder-footer-final" style="color:gold">Mojtaba Roozegar</span></footer>',
    ):
      edited=foot.patch(f)
      assert edited.count(LINE)==1
      assert '<a href="/store/">Store</a>' in edited
      assert 'mpw-founder-footer-final' not in edited
      assert edited.count('<footer')==1 and edited.count('</footer>')==1
      assert 'data-mpw-final-founder="true"' in edited
      assert "Mojtaba Roozegar</span>" not in edited
      try:
          foot.patch(edited)
          assert False, "Repeated publish must fail closed"
      except RuntimeError:
          pass

def test_real_production_home_is_patched_without_app_reload():
    import inspect
    assert foot.HOMEPAGE in foot.targets()
    src=inspect.getsource(foot.before_guard)
    assert 'production-home-20261017.html' in src
    assert 'def refresh_app(' not in inspect.getsource(foot)
    rollback=inspect.getsource(foot.rollback)
    assert 'restart.txt' not in rollback
    assert 'MPW_FOOTER_SINGLE_LINE_ROLLED_BACK=22' in rollback

def test_main_php_must_replace_existing_modern_footer_to_reflect_2022_rights():
    current=(ROOT/"scripts/mpw_dynamic_main_shell_20261019.php").read_text("utf-8")
    assert "standard footer replacement" in current
    previous=current.replace(foot.PHP_NEW_LINE,"",1)
    assert "standard footer replacement" not in previous
    assert foot.patch_php(previous)==current
    try:
        foot.patch_php(current)
        assert False, "Duplicate live PHP change must not be allowed"
    except RuntimeError:pass
    assert current.count("mpw-contact-safe-business-20261019")>=1
    assert current.count("function transformMain(")==1
