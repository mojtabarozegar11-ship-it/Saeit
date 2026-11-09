"""No-network, no-Django tests for newsroom static-route inventory."""

import tempfile
import unittest
from pathlib import Path

from deploy.newsroom_static_routes_audit import inspect_static_routes


class StaticRoutesAuditTests(unittest.TestCase):
    def test_existing_pages_report_hash_and_loader_without_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "news").mkdir()
            (root / "weather").mkdir()
            news = root / "news" / "index.html"
            weather = root / "weather" / "index.html"
            news.write_bytes(b"<html>News</html>")
            weather.write_bytes(b"<script data-zm-editorial-loader='yes' src='/zm-inpage-editorial-2026.js'></script>")
            originals = (news.read_bytes(), weather.read_bytes())
            report = inspect_static_routes(root)
            self.assertFalse(report["web_server_route_verified"])
            self.assertFalse(report["safe_to_deploy_automatically"])
            self.assertEqual([x["state"] for x in report["entries"]], ["static_index_present"] * 2)
            self.assertFalse(report["entries"][0]["mentions_direct_loader"])
            self.assertTrue(report["entries"][1]["mentions_direct_loader"])
            self.assertTrue(report["entries"][1]["mentions_inpage_loader"])
            self.assertEqual((news.read_bytes(), weather.read_bytes()), originals)

    def test_missing_route_is_not_claimed_to_be_dynamic(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "news").mkdir()
            self.assertEqual(
                [x["state"] for x in inspect_static_routes(root)["entries"]],
                ["no_static_index", "no_static_route_directory"],
            )

    def test_symlinks_and_filesystem_root_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "news").symlink_to(root / "missing")
            (root / "weather").mkdir()
            (root / "weather" / "index.html").symlink_to(root / "elsewhere")
            self.assertEqual(
                [x["state"] for x in inspect_static_routes(root)["entries"]],
                ["unsafe_symlink", "unsafe_symlink"],
            )
            with self.assertRaises(ValueError):
                inspect_static_routes(Path("/"))


if __name__ == "__main__":
    unittest.main()
