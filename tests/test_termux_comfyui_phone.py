"""Offline safety tests for ComfyUI key preparation on a simulated Termux home."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest

from termux_bridge.comfyui_phone import prepare_key, TERMUX_PREFIX
from termux_bridge.worker import validate_command, run_allowlisted
from datetime import datetime, timedelta, timezone
import json


@unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH required")
class PhoneKeyTests(unittest.TestCase):
    def test_non_termux_refused_without_changes(self):
        with tempfile.TemporaryDirectory() as td:
            out = prepare_key(home=td, prefix="/usr/local")
            self.assertEqual(out["code"], "comfyui_not_termux")
            self.assertFalse((Path(td) / ".saeit-comfyui-phone").exists())

    def test_private_stays_local_and_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            first = prepare_key(home=td, prefix=TERMUX_PREFIX)
            self.assertTrue(first["ok"], first)
            self.assertEqual(first["code"], "comfyui_public_key_ready")
            self.assertTrue(first["public_key"].startswith("ssh-ed25519 "))
            root = Path(td) / ".saeit-comfyui-phone"
            priv = root / "comfyui_ed25519"
            before = priv.read_bytes()
            self.assertNotIn(before.decode("ascii"), json.dumps(first))
            self.assertEqual(stat.S_IMODE(priv.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            second = prepare_key(home=td, prefix=TERMUX_PREFIX)
            self.assertEqual(first, second)
            self.assertEqual(before, priv.read_bytes())

    def test_rejects_symlink_no_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / ".saeit-comfyui-phone"
            root.mkdir()
            other = Path(td) / "unrelated"
            other.write_text("leave alone", encoding="utf-8")
            (root / "comfyui_ed25519").symlink_to(other)
            result = prepare_key(home=td, prefix=TERMUX_PREFIX)
            self.assertEqual(result["code"], "comfyui_unsafe_key_path")
            self.assertEqual(other.read_text(encoding="utf-8"), "leave alone")

    def test_mismatched_public_key_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            first = prepare_key(home=td, prefix=TERMUX_PREFIX)
            self.assertTrue(first["ok"])
            root = Path(td) / ".saeit-comfyui-phone"
            (root / "comfyui_ed25519.pub").write_text(
                first["public_key"].replace("saeit-comfyui-mobile-v1", "other") + "\n",
                encoding="utf-8")
            self.assertEqual(prepare_key(home=td, prefix=TERMUX_PREFIX)["code"],
                             "comfyui_invalid_key_pair")

    def test_allowlist_not_arbitrary_commands(self):
        now = datetime.now(timezone.utc)
        item = {"protocol_version": 1, "command_id": "comfyui-key-test",
                "action": "comfyui_key_prepare",
                "issued_at": (now-timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
                "expires_at": (now+timedelta(minutes=2)).isoformat().replace("+00:00", "Z")}
        self.assertEqual(validate_command(json.dumps(item).encode(), now)["action"],
                         "comfyui_key_prepare")
        for bad in ("comfyui_key_prepare && cat ~/.ssh/id_rsa", "ssh", "exec", "comfyui_tunnel_start"):
            item["action"] = bad
            with self.assertRaises(Exception):
                validate_command(json.dumps(item).encode(), now)


if __name__ == "__main__":
    unittest.main()
