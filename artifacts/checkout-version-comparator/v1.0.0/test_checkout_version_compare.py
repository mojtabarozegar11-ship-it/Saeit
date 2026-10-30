import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("checkout_version_compare.py")
SPEC = importlib.util.spec_from_file_location("checkout_version_compare", MODULE_PATH)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


class CheckoutCompareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Fixture")
        (self.repo / "checkout").mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True).stdout.decode().strip()

    def commit(self, message):
        self.git("add", "--all")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def test_same_revision_has_no_changes(self):
        (self.repo / "checkout" / "route.py").write_text("route = '/checkout/'\n")
        sha = self.commit("initial")
        result = tool.compare(self.repo, sha, sha, "checkout")
        self.assertEqual(result["changed_file_count"], 0)

    def test_modified_file_reports_hashes_without_contents(self):
        file = self.repo / "checkout" / "route.py"
        file.write_text("route = '/checkout/'\n")
        base = self.commit("base")
        file.write_text("route = '/store/checkout/'\n")
        candidate = self.commit("candidate")
        change = tool.compare(self.repo, base, candidate, "checkout")["changes"][0]
        self.assertEqual(change["status"], "modified")
        self.assertNotIn("content", change)

    def test_added_file_is_reported(self):
        base = self.commit("empty checkout tree")
        (self.repo / "checkout" / "guard.py").write_text("safe = True\n")
        candidate = self.commit("add guard")
        self.assertEqual(tool.compare(self.repo, base, candidate, "checkout")["changes"][0]["status"], "added")

    def test_removed_file_is_reported(self):
        file = self.repo / "checkout" / "old.py"
        file.write_text("old = True\n")
        base = self.commit("old")
        file.unlink()
        candidate = self.commit("remove old")
        self.assertEqual(tool.compare(self.repo, base, candidate, "checkout")["changes"][0]["status"], "removed")

    def test_secret_named_files_are_omitted(self):
        (self.repo / "checkout" / "payment.py").write_text("payment = True\n")
        (self.repo / "checkout" / ".env.production").write_text("PRIVATE=value\n")
        sha = self.commit("fixtures")
        self.assertEqual(len(tool.compare(self.repo, sha, sha, "checkout")["changes"]), 0)
        self.assertNotIn(".env.production", tool.entries_at(self.repo, sha, "checkout"))

    def test_invalid_path_is_rejected(self):
        with self.assertRaises(tool.CompareError):
            tool.safe_repo_path("../checkout")

    def test_result_declares_read_only_behavior_and_version(self):
        (self.repo / "checkout" / "route.py").write_text("route = True\n")
        sha = self.commit("initial")
        result = tool.compare(self.repo, sha, sha, "checkout")
        self.assertEqual(result["tool_version"], "1.0.0")
        self.assertFalse(result["working_tree_modified"])
        self.assertFalse(result["network_used"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
