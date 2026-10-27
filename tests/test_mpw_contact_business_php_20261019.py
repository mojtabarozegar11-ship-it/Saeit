"""Contact-only PHP review gates; avoid changing other shared-shell routes."""
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"scripts/mpw_dynamic_main_shell_20261019.php"

def test_new_contact_branch_is_scoped_and_does_not_modify_allowed_routes():
    new=SOURCE.read_text("utf-8")
    opening=new.split("function transformMain",1)[0]
    # Verify the complete approved route inventory, independent of Git history.
    # The former fixed commit predated this PHP file, so git show always failed
    # on clean GitHub Actions checkouts despite correct, unchanged production code.
    allowed=re.search(r"\$allowed\s*=\s*\[(.*?)\];",opening,re.S)
    assert allowed,"Shared shell route inventory is missing"
    pairs=re.findall(r"'([a-z-]+)'\\s*=>\\s*'(/[^']*/)'",allowed.group(1))
    names=('store','games','ai','contact','support','privacy','terms','cookies',
           'products','blockchain','commerce','crypto-payments','global-business',
           'research-lab','canada-vision','agro-industry','agriculture',
           'education','weather')
    expected={name:f"/{name}/" for name in names}
    assert len(pairs)==len(expected),"Unexpected or duplicated shell routes"
    assert dict(pairs)==expected,"Approved shared shell routes changed"
    assert new.count("if ($path==='/contact/')")==1
    assert new.count("mpw-contact-safe-business-20261019")==2
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
