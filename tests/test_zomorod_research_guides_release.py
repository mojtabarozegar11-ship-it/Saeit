"""Safety checks for the add-only Zomorod research guide publisher."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "zomorod_research_guides_release.py"
SPEC = importlib.util.spec_from_file_location("zomorod_release", SCRIPT)
release = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(release)


class GuardedPublicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="zm-research-guide-")
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.web = self.root / "web"
        self.state = self.root / "state"
        self.source.mkdir()
        (self.web / "research").mkdir(parents=True)
        self.template = self.web / "research" / "index.html"
        self.original = b'<html lang="fa"><head><title>Research</title><link rel="canonical" href="https://zomorodmelal.ir/research/"></head><body><header>Brand</header><main id="main"><h1>Original</h1></main><footer>End</footer></body></html>'
        self.template.write_bytes(self.original)
        folder = self.source / "content" / "zomorod-research-guides"
        folder.mkdir(parents=True)
        (folder / "guide.md").write_text(
            "# عنوان راهنما\n\nمقدمهٔ علمی با **متن مهم**.\n\n## تعریف\n\n"
            "- مورد نخست\n- مورد دوم\n\n## منبع\n\n"
            "[FAO](https://www.fao.org/)\n", encoding="utf-8")
        self.manifest = folder / "manifest.json"
        self.manifest.write_text(json.dumps({
            "release_id": "ZM-RESEARCH-GUIDES-TEST-R1",
            "production_status": "NOT_DEPLOYED",
            "site": "https://zomorodmelal.ir",
            "guides": [{
                "id": "ONE", "title_fa": "عنوان راهنما",
                "source_path": "content/zomorod-research-guides/guide.md",
                "desired_url": "https://zomorodmelal.ir/research/guides/guide-one/",
                "status": "EDITORIAL_REVIEW_REQUIRED",
                "live_verified": False,
            }],
        }), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def load(self):
        return release.load_release(self.source, self.web, self.manifest)

    def test_render_has_branded_shell_and_correct_canonical(self) -> None:
        _, _, pages = self.load()
        page = next(iter(pages.values())).decode("utf-8")
        self.assertIn("<header>Brand</header>", page)
        self.assertIn("<footer>End</footer>", page)
        self.assertIn("<h1>عنوان راهنما</h1>", page)
        self.assertIn('href="https://zomorodmelal.ir/research/guides/guide-one/"', page)
        self.assertEqual(page.count('rel="canonical"'), 1)

    def test_escaped_markup_does_not_become_executable_html(self) -> None:
        title, rendered = release.markdown_body(
            "# سند\n\nمتن <script>alert(1)</script>\n\n## بند یک\n\nسالم\n\n"
            "## بند دو\n\nادامه\n\n## بند سه\n\nمتن دیگر\n\n## بند چهار\n\nپایان\n")
        self.assertEqual(title, "سند")
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("<script>", rendered)

    def test_rejects_invalid_publication_url(self) -> None:
        m = json.loads(self.manifest.read_text())
        m["guides"][0]["desired_url"] = "https://wrong.example/research/guides/guide-one/"
        self.manifest.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, "INVALID_TARGET_URL"):
            self.load()

    def test_apply_is_add_only_and_rollback_is_hash_guarded(self) -> None:
        m, h, pages = self.load()
        release.apply_release(self.web, self.state, m["release_id"], h, h, pages)
        created = self.web / next(iter(pages))
        self.assertTrue(created.is_file())
        self.assertEqual(self.template.read_bytes(), self.original)
        with self.assertRaises(FileExistsError):
            release.preflight(self.web, pages)
        created.write_text("modified outside release", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "CHANGED_FILES_NOT_REMOVED"):
            release.rollback_release(self.web, self.state, m["release_id"])
        self.assertEqual(created.read_text(), "modified outside release")
        self.assertEqual(self.template.read_bytes(), self.original)

    def test_wrong_template_sha_fails_before_writes(self) -> None:
        m, h, pages = self.load()
        with self.assertRaisesRegex(ValueError, "LIVE_TEMPLATE_SHA_MISMATCH"):
            release.apply_release(self.web, self.state, m["release_id"], "0" * 64, h, pages)
        self.assertFalse((self.web / next(iter(pages))).exists())
        self.assertFalse(self.state.exists())

    def test_editorial_review_blocks_live_apply(self) -> None:
        _, template_hash, _ = self.load()
        args = [str(SCRIPT), "apply", "--source-root", str(self.source),
                "--web-root", str(self.web),
                "--manifest", "content/zomorod-research-guides/manifest.json",
                "--confirm-release-id", "ZM-RESEARCH-GUIDES-TEST-R1",
                "--expected-template-sha", template_hash]
        with patch.object(sys, "argv", args):
            with self.assertRaisesRegex(ValueError, "EDITORIAL_APPROVAL_REQUIRED"):
                release.main()
        self.assertFalse((self.web / "research" / "guides").exists())

    def test_symlink_parent_is_rejected(self) -> None:
        target = self.root / "outside"
        target.mkdir()
        (self.web / "research" / "guides").symlink_to(target, target_is_directory=True)
        _, _, pages = self.load()
        with self.assertRaisesRegex(ValueError, "UNSAFE_PARENT"):
            release.preflight(self.web, pages)


if __name__ == "__main__":
    unittest.main()
