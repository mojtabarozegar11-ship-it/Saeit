"""Contact-only PHP review gates; avoid changing other shared-shell routes."""
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"scripts/mpw_dynamic_main_shell_20261019.php"
BASE="8751d8bfd47354ba18d1efe75166404127a5bb4a"

def test_new_contact_branch_is_scoped_and_does_not_modify_allowed_routes():
    new=SOURCE.read_text("utf-8")
    before=subprocess.run(
        ["git","show",BASE+":scripts/mpw_dynamic_main_shell_20261019.php"],
        cwd=ROOT,text=True,capture_output=True,check=True).stdout
    opening=new.split("function transformMain",1)[0]
    old_opening=before.split("function transformMain",1)[0]
    assert opening==old_opening,"Shared route inventory/header changed"
    assert "'contact' => '/contact/'" in opening
    for path in ('store','games','ai','privacy','terms','support','weather'):
        assert f"'{path}' => '/{path}/'" in opening
    assert new.count("if ($path==='/contact/')")==1
    assert new.count("mpw-contact-safe-business-20261019")==1
    assert new.count("'Business'=>[")==1 and new.count("'Press'=>[")==1
    assert 'mailto:' in new
    assert 'support@mojplaywin.com' in new
    assert "This is not a separately staffed business mailbox" in new
    assert "a dedicated press office or guaranteed reply is not claimed" in new
    assert "Coming soon" in new, "Only the original source and self-test may contain this label"
    assert "if ($path==='/education/')" in new
    assert "MPW_MAIN_ONLY_BRIDGE_SELFTEST=PASS" in new

def test_php_syntax_and_selftest():
    checks=[
        ["php","-l",str(SOURCE)],
        ["php",str(SOURCE),"selftest"],
    ]
    for command in checks:
        outcome=subprocess.run(command,text=True,capture_output=True,timeout=25)
        assert outcome.returncode==0,(outcome.stdout,outcome.stderr)
    assert "MPW_MAIN_ONLY_BRIDGE_SELFTEST=PASS" in outcome.stdout
