"""Fail-closed static safety checks for the 30GB cPanel read-only inventory bridge."""
from pathlib import Path
import ast

SOURCE = Path(__file__).resolve().parents[1] / ".github/workflows/zomorod-v7-readonly-inventory.yml"


def test_verified_new_two_hop_relay_and_restricted_identity():
    s = SOURCE.read_text(encoding="utf-8")
    required = (
        "HostName 178.239.147.150",
        "HostName 178.239.147.125",
        "Port 1396",
        "ProxyJump saeit-vps",
        "StrictHostKeyChecking yes",
        "IdentitiesOnly yes",
        "ForwardAgent no",
        "PINNED_30GB_RELAY_AUTHENTICATED_ON_ATTEMPT",
        "PINNED_SESSION=AUTHENTICATED_VIA_VPS",
        "SHA256:AYdzF3K5uSwAXElE1w/dKo04iT2BbMGwHbRA2Cu4rrs",
        "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04",
        "case \"$COMMAND_HOST\" in saeit-cpanel|saeit-cpanel-direct)",
    )
    assert all(x in s for x in required)
    assert "ssh-keyscan" not in s
    assert "zohal.pws-dns.net" not in s
    assert "178.239.147.124" not in s


def test_only_readonly_live_sqlite_and_site_inspection():
    s = SOURCE.read_text(encoding="utf-8")
    live = s.split("      - name: Read only live HTML page and admin state inventory", 1)[1]
    live = live.split("      - name: Clean temporary runner keys", 1)[0]
    assert "mode=ro" in live
    assert "PRAGMA quick_check" in live
    assert "BUSINESS_DB_PRIVATE_PERMISSIONS" in live
    assert "BUSINESS_ADMIN_COUNT" in live
    assert "BUSINESS_DB_SIZE_BYTES" in live
    for forbidden in ("INSERT INTO", "UPDATE users", "DROP TABLE", "DELETE FROM", "VACUUM", "CREATE TABLE", "chmod ", "chown ", "rsync ", "scp ", "tar -xf"):
        assert forbidden not in live
    assert "mkdir -p" not in live
    assert "rm -rf" not in live


def test_embedded_inventory_python_is_valid_syntax():
    s = SOURCE.read_text(encoding="utf-8")
    lines = s.splitlines()
    markers = [i for i, line in enumerate(lines) if line.strip() == "python3 - <<'PY'"]
    assert len(markers) == 1
    start = markers[0]
    indent = len(lines[start]) - len(lines[start].lstrip())
    body = []
    for line in lines[start + 1:]:
        if line.strip() == "PY" and len(line) - len(line.lstrip()) == indent:
            break
        body.append(line[indent:])
    else:
        raise AssertionError("missing Python heredoc terminator")
    ast.parse("\n".join(body) + "\n")


def test_no_public_site_mutations_or_unintended_triggers():
    s = SOURCE.read_text(encoding="utf-8")
    assert "    branches: [main]" in s
    assert 'paths: [".github/workflows/zomorod-v7-readonly-inventory.yml"]' in s
    assert "  workflow_dispatch:" not in s
    assert "  issue_comment:" not in s
    assert "permissions:\n  contents: read" in s
    assert 'run: rm -rf "$RUNNER_TEMP/zomorod-command-channel"' in s
