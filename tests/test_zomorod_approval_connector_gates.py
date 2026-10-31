"""Regression checks for owner and official connector issuer authorization."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / ".github").is_dir():
    ROOT = Path(__file__).resolve().parent
WORKFLOWS = [
    ROOT / ".github/workflows/zomorod-approval-sealed-handoff-20261031.yml",
    ROOT / ".github/workflows/zomorod-business-approval-private-install-20261031.yml",
]


def event_gate(source):
    lines = source.splitlines()
    start = next(i for i,x in enumerate(lines) if 'python3 - "$GITHUB_EVENT_PATH" <<' in x)
    indent = len(lines[start]) - len(lines[start].lstrip(" "))
    body = []
    for line in lines[start + 1:]:
        if line.strip() == "PY" and len(line) - len(line.lstrip(" ")) == indent:
            return "\n".join(body) + "\n"
        assert line.startswith(" " * indent), line
        body.append(line[indent:])
    raise AssertionError("Owner gate heredoc not closed")


def make_event(receive, *, app="chatgpt-codex-connector", author="mojtabarozegar11-ship-it"):
    if receive:
        obj = {
            "alg": "RSA-OAEP-SHA1+AES-256-GCM+GZIP",
            "ct": "A" * 1024,
            "ek": "A" * 512,
            "issued_at": 1793450000,
            "iv": "A" * 16,
            "plain_size": 52072,
            "purpose": "zomorod-approval-csv-import-20261031-v1",
            "sha256": "40c09b1aff17143cf315884177b61a35c6b1d62aa30a445056cfd8303deb3366",
            "tag": "A" * 24,
            "v": 1,
        }
        body = "ZMR-APPROVAL-SEALED-UPLOAD-V1\n" + json.dumps(obj, separators=(",",":"))
    else:
        body = "ZMR-APPROVAL-INSTALL-V1"
    return {
        "action": "created",
        "issue": {"number": 1600},
        "comment": {
            "user": {"login": author},
            "author_association": "OWNER",
            "performed_via_github_app": {"slug": app},
            "body": body,
        },
    }


def run_gate(source, event, actor):
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        path = folder / "event.json"
        path.write_text(json.dumps(event), encoding="utf-8")
        env = dict(os.environ)
        env.update({
            "GITHUB_EVENT_NAME": "issue_comment",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_ACTOR": actor,
            "RUNNER_TEMP": temporary,
        })
        return subprocess.run(
            [sys.executable, "-B", "-c", event_gate(source), str(path)],
            env=env, capture_output=True, text=True, check=False, timeout=7,
        )


class TestOwnerConnectorGates(unittest.TestCase):
    def test_official_connector_accepted_and_untrusted_rejected(self):
        for i,path in enumerate(WORKFLOWS):
            with self.subTest(workflow=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertIn("github.actor == 'chatgpt-codex-connector[bot]'", source)
                self.assertIn("OWNER_CONNECTOR_PROVENANCE_BLOCKED", source)
                self.assertIn("github.event.comment.author_association == 'OWNER'", source)
                self.assertNotIn("\n  push:", source.split("permissions:", 1)[0])
                event = make_event(receive=i==0)
                good = run_gate(source, event, "chatgpt-codex-connector[bot]")
                self.assertEqual(good.returncode, 0, good.stderr)
                bad = make_event(receive=i==0, app="untrusted-app")
                invalid = run_gate(source, bad, "chatgpt-codex-connector[bot]")
                self.assertNotEqual(invalid.returncode, 0)
                other = make_event(receive=i==0, author="unrelated-person")
                self.assertNotEqual(run_gate(source, other, "chatgpt-codex-connector[bot]").returncode, 0)
                direct = run_gate(source, event, "mojtabarozegar11-ship-it")
                self.assertEqual(direct.returncode, 0, direct.stderr)


if __name__ == "__main__":
    unittest.main()
