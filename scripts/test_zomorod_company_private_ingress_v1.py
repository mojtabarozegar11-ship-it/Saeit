"""Local crypto and task-queue regression for the encrypted private ingress."""
import base64
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).with_name("zomorod_company_private_ingress_v1.py")
spec = importlib.util.spec_from_file_location("private_ingress", SOURCE)
ingress = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ingress)

TASK = {
    "workstream": "operations",
    "priority": "normal",
    "risk": "read_only",
    "title": "Channel receipt verification",
    "detail": "Record a non-executing authenticated ingress receipt.",
    "deliverable": "Private task queue receipt",
    "acceptance": "Task is queued and not executed.",
}


def seal(public_key: Path, command_id: str, task: dict) -> bytes:
    session = os.urandom(64)
    aes_key, mac_key = session[:32], session[32:]
    iv = os.urandom(16)
    wrapped = subprocess.run(
        ["openssl", "pkeyutl", "-encrypt", "-pubin", "-inkey", str(public_key),
         "-pkeyopt", "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256"],
        input=session, capture_output=True, check=True, timeout=8,
    ).stdout
    plaintext = json.dumps({"v": 1, "id": command_id, "task": task},
                           sort_keys=True, ensure_ascii=False,
                           separators=(",", ":")).encode()
    ciphertext = subprocess.run(
        ["openssl", "enc", "-aes-256-cbc", "-nosalt", "-K", aes_key.hex(),
         "-iv", iv.hex()],
        input=plaintext, capture_output=True, check=True, timeout=8,
    ).stdout
    mac = hmac.new(mac_key, ingress.MAGIC + wrapped + iv + ciphertext,
                   hashlib.sha256).digest()
    return json.dumps({
        "v": 1,
        "alg": "RSA-OAEP-256+A256CBC-HS256",
        "ek": base64.b64encode(wrapped).decode(),
        "iv": base64.b64encode(iv).decode(),
        "ct": base64.b64encode(ciphertext).decode(),
        "mac": base64.b64encode(mac).decode(),
    }, sort_keys=True, separators=(",", ":")).encode()


class PrivateIngressTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="zm-private-ingress-")
        self.root = Path(self.tmp.name)
        os.chmod(self.root, 0o700)
        self.db = self.root / "command-center.sqlite3"
        import sqlite3
        con = sqlite3.connect(self.db)
        con.executescript("""
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY, request_key TEXT NOT NULL UNIQUE,
                source_key TEXT UNIQUE, workstream TEXT NOT NULL, title TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '', priority TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'queued', actor_id INTEGER NOT NULL
            );
            CREATE TABLE task_events (
                id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES tasks(id),
                actor_id INTEGER NOT NULL, kind TEXT NOT NULL, note TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE task_quality (
                task_id INTEGER PRIMARY KEY REFERENCES tasks(id), risk TEXT NOT NULL,
                deliverable TEXT NOT NULL, acceptance TEXT NOT NULL
            );
        """)
        con.close()
        os.chmod(self.db, 0o600)
        self.hmac_key = self.root / ".company-bridge.key"
        self.hmac_key.write_bytes(os.urandom(32))
        os.chmod(self.hmac_key, 0o600)
        self.recipient = self.root / ".chat-command-rsa.key"
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt",
             "rsa_keygen_bits:3072", "-out", str(self.recipient)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=True, timeout=30,
        )
        os.chmod(self.recipient, 0o600)
        self.public = self.root / "recipient.pub"
        self.public.write_bytes(ingress.public_key_pem(self.recipient))
        self.command_id = "0123456789abcdef0123456789abcdef"

    def tearDown(self):
        self.tmp.cleanup()

    def test_encrypted_command_is_hmac_signed_and_queued_without_execution(self):
        envelope = seal(self.public, self.command_id, TASK)
        result = ingress.accept(envelope, self.db, self.hmac_key, self.recipient, now=1_800_000_000)
        self.assertEqual(result, "ACCEPTED")
        import sqlite3
        con = sqlite3.connect(self.db)
        row = con.execute("SELECT workstream,title,actor_id,state FROM tasks").fetchone()
        event = con.execute("SELECT kind,note FROM task_events").fetchone()
        self.assertEqual(row, ("operations", TASK["title"], 0, "queued"))
        self.assertEqual(event[0], "bridge_signed_task")
        self.assertIn("not executed", event[1])
        self.assertNotEqual(self.recipient.read_bytes(), b"")
        self.assertEqual(self.recipient.stat().st_mode & 0o777, 0o600)
        con.close()

    def test_ciphertext_tampering_is_rejected_before_database_write(self):
        envelope = json.loads(seal(self.public, self.command_id, TASK))
        damaged = bytearray(base64.b64decode(envelope["ct"]))
        damaged[0] ^= 1
        envelope["ct"] = base64.b64encode(damaged).decode()
        with self.assertRaises(ingress.Reject):
            ingress.accept(json.dumps(envelope).encode(), self.db,
                           self.hmac_key, self.recipient, now=1_800_000_000)
        import sqlite3
        con = sqlite3.connect(self.db)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 0)
        con.close()


if __name__ == "__main__":
    unittest.main()
