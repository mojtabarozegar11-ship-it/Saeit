"""Tests for the missing 11 adapted Zomorod V11 agent roles (MojPlayWin-only)."""
import io
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from mpw_v91_port.site_health_v11 import (
    AGENT_PATHS,BASE,NoRedirect,audit_once,check_path,main,response_code,
)

class MainOnlySiteAgentTests(unittest.TestCase):
    def test_all_11_original_roles_represented_but_only_main_site_routes(self):
        self.assertEqual(len(AGENT_PATHS),11)
        self.assertEqual(set(AGENT_PATHS),{
            "master","content","seo","commerce","agriculture","research",
            "economic","weather","quality","media","security"
        })
        self.assertEqual(BASE,"https://mojplaywin.com")
        self.assertEqual(AGENT_PATHS["media"][0],"/newsletter/")
        self.assertEqual(AGENT_PATHS["security"][0],"/staff/command-center/")
        for path,description in AGENT_PATHS.values():
            self.assertTrue(path.startswith("/"))
            self.assertNotIn("//",path)
            self.assertNotIn("zomorod",path)
            self.assertNotIn("/farnaz/",path)
            self.assertNotIn("/saman/",path)

    def test_refuse_arbitrary_urls_and_redirects(self):
        with self.assertRaises(ValueError):
            response_code("https://zomorodmelal.ir")
        with self.assertRaises(ValueError):
            response_code("/farnaz/")
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,"",{},"https://evil.example"))

    def test_ok_and_warning_are_real_http_results(self):
        good=check_path("master",lambda path:200)
        self.assertEqual(good["status"],"ok")
        fail=check_path("commerce",lambda path:503)
        self.assertEqual(fail["status"],"warning")
        staff=check_path("security",lambda path:302)
        self.assertEqual(staff["status"],"ok")
        self.assertEqual(staff["http"],302)

    def test_genuine_private_record_without_network_or_public_site_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            folder.chmod(0o700)
            checked=[]
            def fake_probe(path):
                checked.append(path)
                return 200
            report=audit_once(folder,fake_probe)
            self.assertEqual(report["total_agents"],11)
            self.assertEqual(len(checked),11)
            self.assertEqual({r["code"] for r in report["runs"]},set(AGENT_PATHS))
            self.assertTrue((folder/"last_scan.json").is_file())
            self.assertEqual(len((folder/"history.jsonl").read_text().splitlines()),1)
            self.assertFalse(report["writes_to_public_site"])
            self.assertFalse(report["factory_connected"])
            self.assertFalse(report["automatic_publishing"])

    def test_check_path_never_returns_fabricated_success_on_exception(self):
        from urllib.error import URLError
        result=check_path("research",lambda path:(_ for _ in ()).throw(URLError("offline")))
        self.assertEqual(result["status"],"error")
        self.assertEqual(result["http"],0)

    def test_nonprivate_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            folder.chmod(0o755)
            with self.assertRaises(PermissionError):
                audit_once(folder,lambda path:200)
