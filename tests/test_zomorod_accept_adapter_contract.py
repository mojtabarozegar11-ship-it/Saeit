"""The encrypted cPanel accept adapter must return only the exact accepted ID."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "scripts" / "zomorod_private_accept_with_id.py"
WORKFLOW = ROOT / ".github" / "workflows" / "zomorod-private-command-dispatch.yml"


def test_adapter_binds_decrypted_id_to_successful_private_ingress_accept():
    text = ADAPTER.read_text(encoding="utf-8")
    ast.parse(text)
    assert "pwd.getpwuid(os.geteuid()).pw_name" in text
    assert "module.decrypt(raw, RECIPIENT, module.load_bridge())" in text
    assert "module.accept(raw, DATABASE, HMAC_KEY, RECIPIENT)" in text
    assert text.index("module.decrypt(") < text.index("module.accept(")
    assert 'if result != "ACCEPTED"' in text
    assert 'print("PRIVATE_COMMAND_ID=" + command_id)' in text
    assert 'raw = sys.stdin.buffer.read(24001)' in text
    assert "shell=True" not in text
    assert "print(raw)" not in text
    assert "print(task)" not in text


def test_workflow_never_echoes_plaintext_and_binds_worker_to_the_same_id():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'adapter_b64="$(base64 -w0 scripts/zomorod_private_accept_with_id.py)"' in text
    assert 'zomorod-sealed-command.txt" > "$d/receipt.txt"' in text
    assert 'command_id="$(sed -n \'s/^PRIVATE_COMMAND_ID=//p\' "$d/receipt.txt")"' in text
    assert '[[ "$command_id" =~ ^[0-9a-f]{32}$ ]]' in text
    assert "apply '$command_id'" in text
    assert 'test "$applied_id" = "$command_id"' in text
    assert "verify '$command_id'" in text
    assert "PRIVATE_POLICY_DURABILITY=INDEPENDENTLY_VERIFIED" in text
