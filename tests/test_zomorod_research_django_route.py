"""Django/Passenger research guide publication gates (no live deployment)."""

import hashlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.research_guide_views import research_guide, verified_guide_paths

RELEASE = "ZM-RESEARCH-GUIDES-TEST-R1"
SLUG = "guide-one"
SOURCE = b"# A reviewed original research guide\n\nIndependent public content.\n"
HTML = b"<!doctype html><html lang='fa'><main>Approved guide</main></html>"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ResearchGuideDjangoTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="zomorod-django-publication-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source_root = self.root / "source"
        self.web = self.root / "public_html"
        self.state = self.root / "state"
        self.source_file = self.source_root / "content" / "zomorod-research-guides" / "article.md"
        self.source_file.parent.mkdir(parents=True)
        self.source_file.write_bytes(SOURCE)
        self.html_file = self.web / "research" / "guides" / SLUG / "index.html"
        self.html_file.parent.mkdir(parents=True)
        self.html_file.write_bytes(HTML)
        self.journal = self.state / RELEASE / "journal.json"
        self.journal.parent.mkdir(parents=True)
        self.manifest = self.source_root / "content" / "zomorod-research-guides" / "publication-manifest-20261108.json"
        self.guide = {
            "id": "ONE",
            "status": "APPROVED_FOR_SITE",
            "desired_url": f"https://zomorodmelal.ir/research/guides/{SLUG}/",
            "source_path": "content/zomorod-research-guides/article.md",
            "approved_source_sha256": sha(SOURCE),
        }
        self.write_manifest()
        self.write_journal()
        self.settings_patch = override_settings(BASE_DIR=self.source_root, ALLOWED_HOSTS=["zomorodmelal.ir", "mojplaywin.com"])
        self.settings_patch.enable()
        self.addCleanup(self.settings_patch.disable)
        self.env_patch = patch.dict(os.environ, {
            "ZOMOROD_RESEARCH_GUIDES_WEB_ROOT": str(self.web),
            "ZOMOROD_RESEARCH_GUIDES_STATE_ROOT": str(self.state),
        })
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.factory = RequestFactory()

    def write_manifest(self):
        self.manifest.write_text(json.dumps({
            "site": "https://zomorodmelal.ir",
            "release_id": RELEASE,
            "production_status": "NOT_DEPLOYED",
            "guides": [self.guide],
        }), encoding="utf-8")

    def write_journal(self, state="installed_unverified", digest=None):
        self.journal.write_text(json.dumps({
            "release_id": RELEASE,
            "state": state,
            "created": {f"research/guides/{SLUG}/index.html": digest or sha(HTML)},
        }), encoding="utf-8")

    def request(self, host="zomorodmelal.ir"):
        return self.factory.get(f"/research/guides/{SLUG}/", HTTP_HOST=host)

    def test_approved_exact_bytes_are_served_pending_external_verification(self):
        resp = research_guide(self.request(), SLUG)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, HTML)
        self.assertEqual(resp["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(verified_guide_paths(), [])

    def test_verified_guide_is_indexable_and_sitemap_eligible(self):
        self.write_journal(state="live_verified")
        resp = research_guide(self.request(), SLUG)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("X-Robots-Tag", resp)
        self.assertEqual(verified_guide_paths(), [f"/research/guides/{SLUG}/"])

    def test_unapproved_guide_is_not_served(self):
        self.guide["status"] = "EDITORIAL_REVIEW_REQUIRED"
        self.write_manifest()
        with self.assertRaises(Http404):
            research_guide(self.request(), SLUG)

    def test_changed_source_invalidates_approval(self):
        self.source_file.write_bytes(SOURCE + b"undisclosed edit")
        with self.assertRaises(Http404):
            research_guide(self.request(), SLUG)

    def test_wrong_public_html_bytes_are_rejected(self):
        self.html_file.write_bytes(b"changed output")
        with self.assertRaises(Http404):
            research_guide(self.request(), SLUG)

    def test_wrong_journal_digest_is_rejected(self):
        self.write_journal(digest="0" * 64)
        with self.assertRaises(Http404):
            research_guide(self.request(), SLUG)

    def test_other_host_does_not_leak_zomorod_content(self):
        with self.assertRaises(Http404):
            research_guide(self.request(host="mojplaywin.com"), SLUG)

    def test_unknown_slug_is_not_fallback(self):
        with self.assertRaises(Http404):
            research_guide(self.request(), "unknown")

    def test_no_configured_web_root_is_fail_closed(self):
        with patch.dict(os.environ, {"ZOMOROD_RESEARCH_GUIDES_WEB_ROOT": ""}):
            with self.assertRaises(Http404):
                research_guide(self.request(), SLUG)

    def test_verified_index_reverts_when_journal_loses_verified_state(self):
        self.write_journal(state="live_verified")
        self.assertEqual(len(verified_guide_paths()), 1)
        self.write_journal(state="rolled_back")
        self.assertEqual(verified_guide_paths(), [])
