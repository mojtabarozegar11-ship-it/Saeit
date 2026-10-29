"""Safety contract for the exact-file, one-time owner SQLite mode hardener."""
from pathlib import Path
import ast

P = Path(__file__).resolve().parents[1]/".github/workflows/zomorod-owner-db-mode600-once.yml"

def _s():
    return P.read_text(encoding="utf-8")

def _live():
    s=_s()
    return s.split("      - name: Apply exact private SQLite mode 0600 with rollback on failure",1)[1].split("      - name: Remove private runner SSH material",1)[0]

def test_only_merge_to_main_can_execute_private_live_step():
    s=_s()
    assert "if: github.event_name == 'push' && github.ref == 'refs/heads/main'" in s
    assert "needs: offline-safety" in s
    assert "permissions:\n  contents: read" in s
    assert "  issue_comment:" not in s
    assert "  workflow_dispatch:" not in s
    assert "  pull_request:" in s
    assert "    branches: [main, 'fix/zomorod-owner-db-mode600-once-20261029']" in s

def test_strict_pinned_new_cpanel_route():
    s=_s()
    for part in (
        "HostName 178.239.147.150", "HostName 178.239.147.125",
        "ProxyJump saeit-vps", "StrictHostKeyChecking yes",
        "IdentitiesOnly yes", "ForwardAgent no",
        "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs",
        "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04",
        "case \"$COMMAND_HOST\" in saeit-cpanel|saeit-cpanel-direct)",
    ):
        assert part in s
    assert "ssh-keyscan" not in s
    assert "zohal.pws-dns.net" not in s

def test_no_database_records_or_other_site_files_changed():
    s=_live()
    for part in (
        'private="/home/zomorod2/.private/zomorod-business"',
        'db="$private/management.sqlite3"',
        'test "$(stat -c \'%a\' "$private")" = 700',
        'test "$(stat -c \'%a\' "$db")" = 644',
        'test "$(stat -c \'%u\' "$db")" = "$(id -u)"',
        'chmod 600 "$db"',
        'chmod 644 "$db" || true',
        "OWNER_DB_MODE_ROLLBACK=ATTEMPTED",
        "OWNER_DB_RECORDS_CHANGED=NO",
        "PRAGMA quick_check",
        "?mode=ro",
        "SELECT count(*) FROM users WHERE role='admin' AND active=1",
        "OWNER_LOGIN_POSTCHECK=FAILED",
    ):
        assert part in s
    for forbidden in (
        "UPDATE users", "INSERT INTO", "DELETE FROM", "DROP TABLE", "ALTER TABLE",
        "VACUUM", "rsync ", "scp ", "tar -xf", "cp -r", "rm -rf",
        "public_html/index", "mojplaywin", "PASSWORD=", "password_hash",
    ):
        assert forbidden not in s

def test_both_sqlite_heredocs_compile_and_rollback_is_armed_first():
    s=_live()
    lines=s.splitlines()
    needle="          python3 -B - <<'PY'"
    starts=[i for i,line in enumerate(lines) if line==needle]
    assert len(starts)==2
    for start in starts:
        body=[]
        for line in lines[start+1:]:
            if line=="          PY":break
            assert line.startswith("          ")
            body.append(line[10:])
        else: raise AssertionError("Missing Python marker")
        ast.parse("\n".join(body)+"\n")
    assert s.index("trap rollback EXIT") < s.index('chmod 600 "$db"')
    assert s.index("trap - EXIT") > s.index("OWNER_LOGIN_POSTCHECK=FAILED")
