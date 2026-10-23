"""Tests for six bounded tenant-only operational robots. No production write tests."""
from pathlib import Path
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]/"scripts/mpw_main_extended_robots.py"
spec=importlib.util.spec_from_file_location("mpw_extended_bot_unit",SOURCE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def static_home(title,canonical,description="A practical original educational guide to evaluating technology safely."):
    return ('<!doctype html><html><head><title>'+title+'</title>'
            '<meta name="description" content="'+description+'">'
            '<link rel="canonical" href="'+canonical+'">'
            '<meta http-equiv="Content-Security-Policy" content="default-src &apos;none&apos;">'
            '</head><body><h1>'+title+'</h1></body></html>')

def public_fixture(root):
    public=root/"mpw-editorial";(public/"agents/unique").mkdir(parents=True)
    file=public/"agents/unique/index.html"
    file.write_text(static_home("Unique AI guide",
        "https://mojplaywin.com/mpw-editorial/agents/unique/index.html"))
    (public/"index.html").write_text(static_home("MojPlayWin Knowledge & Insights",
        "https://mojplaywin.com/mpw-editorial/index.html"))
    owner={"tenant":"mojplaywin-main","scope":"mojplaywin-main-static-mpw-editorial-only",
           "content_fingerprints":{"unique":"a"*64},"published_articles":1}
    (public/".mpw-editorial-owner.json").write_text(json.dumps(owner))
    return public,owner,[public/"agents/unique/index.html",public/"index.html"]

class ExtendedRobotTests(unittest.TestCase):
    def test_six_distinct_roles(self):
        self.assertEqual(len(mod.NAMES),6)
        self.assertEqual(len(set(mod.NAMES)),6)

    def test_trusted_public_seo_and_security(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);public,manifest,files=public_fixture(root)
            owned,actual=mod.approved_pages(public)
            self.assertEqual(owned["published_articles"],1)
            self.assertEqual(len(actual),2)
            self.assertEqual(mod.seo_robot(files,public)["status"],"ok")
            self.assertEqual(mod.content_security_robot(files)["status"],"ok")

    def test_editorial_inventory_scales_to_twenty_two_pages(self):
        with tempfile.TemporaryDirectory() as td:
            public,manifest,files=public_fixture(Path(td))
            for number in range(20):
                child=public/"agents"/f"guide-{number}"/"index.html"
                child.parent.mkdir()
                child.write_text(static_home(
                    f"MojPlayWin Technical Guide {number}",
                    f"https://mojplaywin.com/mpw-editorial/agents/guide-{number}/index.html"))
            _,actual=mod.approved_pages(public)
            self.assertEqual(len(actual),22)
            self.assertEqual(mod.seo_robot(actual,public)["status"],"ok")

    def test_canonical_and_duplicate_seo_detection(self):
        with tempfile.TemporaryDirectory() as td:
            public,manifest,files=public_fixture(Path(td))
            target=files[0]
            target.write_text(static_home("MojPlayWin Knowledge & Insights",
                          "https://mojplaywin.com/mpw-editorial/agents/unique/"))
            bad=mod.seo_robot(files,public)
            self.assertEqual(bad["status"],"warning")
            self.assertGreaterEqual(len(bad["invalid_seo_documents"]),1)

    def test_source_host_denies_unsafe_domains(self):
        rows=[{"slug":"a","source_urls":["https://www.nist.gov/","https://www.w3.org/TR/WCAG22/"]}]
        self.assertEqual(mod.references_robot(rows)["status"],"ok")
        rows[0]["source_urls"][1]="https://evil.example/r"
        self.assertEqual(mod.references_robot(rows)["status"],"warning")

    def test_release_hash_reconciliation(self):
        with tempfile.TemporaryDirectory() as td:
            public,manifest,files=public_fixture(Path(td))
            expected=[{"slug":"unique","page_path":"/agents/","content_sha256":"a"*64}]
            correct=mod.reconcile_robot(expected,manifest,public)
            self.assertEqual(correct["status"],"ok")
            self.assertEqual(correct["manifest_articles"],1)
            wrong=[dict(expected[0],content_sha256="b"*64)]
            self.assertEqual(mod.reconcile_robot(wrong,manifest,public)["status"],"warning")

    def test_private_publication_worklist_is_not_approval(self):
        rows=[{"slug":"new","page_path":"/research/","title":"Research study",
               "content_sha256":"a"*64}]
        jobs=mod.worklist_robot(rows,{"content_fingerprints":{}})
        self.assertEqual(jobs["pending_count"],1)
        self.assertFalse(jobs["auto_published"])
        self.assertFalse(jobs["items"][0]["approved"])

    def test_storage_capacity_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            result=mod.capacity_robot(Path(td))
            self.assertIn(result["status"],("ok","warning"))
            self.assertFalse(result["cleanup_performed"])

    def test_output_cannot_escape_private_state(self):
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td);dest.chmod(0o700)
            with patch.object(mod,"STATE",dest):
                mod.private_write(dest/"allowed.json",{"tenant":"mojplaywin-main"})
                self.assertEqual((dest/"allowed.json").stat().st_mode & 0o077,0)
                with self.assertRaisesRegex(RuntimeError,"UNAUTHORIZED_ROBOT_WRITE"):
                    mod.private_write(dest/"outside/out.json",{})

    def test_cross_tenant_public_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            public,manifest,files=public_fixture(Path(td))
            manifest["tenant"]="other"
            (public/".mpw-editorial-owner.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError,"CROSS_TENANT"):
                mod.approved_pages(public)

if __name__=="__main__":
    unittest.main()
