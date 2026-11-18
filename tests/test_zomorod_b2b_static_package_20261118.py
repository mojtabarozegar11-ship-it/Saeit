"""Deterministic and deployment-free B2B source package contract."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts.zomorod_b2b_static_package_20261118 import (
    HERE, PAGES, _load_exact, archive_bytes, verify_archive,
)

SHA = "d23fddbcd1b4e284e748b55e224bb1fe3097ed9a"

class StaticPackageTests(unittest.TestCase):
    def test_real_sources_are_exactly_two_pages(self):
        pages = _load_exact(HERE)
        self.assertEqual(set(pages), set(PAGES))
        self.assertGreater(len(pages["b2b/index.html"]), 3000)

    def test_archive_deterministic_with_matching_manifest(self):
        a=archive_bytes(HERE,SHA)
        self.assertEqual(a, archive_bytes(HERE,SHA))
        m=verify_archive(a,SHA)
        self.assertFalse(m["production_deployed"])
        self.assertEqual(len(m["files"]),2)
        with zipfile.ZipFile(io.BytesIO(a)) as z:
            self.assertEqual(set(z.namelist()),{"MANIFEST.json",*PAGES})

    def test_invalid_source_commit_denied(self):
        with self.assertRaises(ValueError):
            archive_bytes(HERE,"main")
        with self.assertRaises(ValueError):
            verify_archive(archive_bytes(HERE,SHA),"x"*40)

    def test_modify_bytes_after_packaging_detected(self):
        a=archive_bytes(HERE,SHA)
        with zipfile.ZipFile(io.BytesIO(a)) as z:
            contents={k:z.read(k) for k in z.namelist()}
        contents["b2b/index.html"]=contents["b2b/index.html"]+b"tampered"
        out=io.BytesIO()
        with zipfile.ZipFile(out,"w") as z:
            for k,v in contents.items():
                z.writestr(k,v)
        with self.assertRaises(ValueError):
            verify_archive(out.getvalue(),SHA)

    def test_added_archive_member_denied(self):
        a=archive_bytes(HERE,SHA)
        out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(a)) as src,zipfile.ZipFile(out,"w") as dest:
            for name in src.namelist():
                dest.writestr(name,src.read(name))
            dest.writestr("b2b/evil.php",b"<?php ?>")
        with self.assertRaises(ValueError):
            verify_archive(out.getvalue(),SHA)

    def test_modified_but_well_formed_source_denied(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"public"/"b2b"/"privacy").mkdir(parents=True)
            for member,relative in PAGES.items():
                target=root/relative
                target.write_bytes((HERE/relative).read_bytes())
            target=root/"public"/"b2b"/"index.html"
            text=target.read_text(encoding="utf-8")
            target.write_text(text.replace("Official company contact channel","Other company contact channel"),encoding="utf-8")
            with self.assertRaises(ValueError):
                _load_exact(root)

    def test_symlinked_source_denied(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"public"/"b2b"/"privacy").mkdir(parents=True)
            for member,relative in PAGES.items():
                target=root/relative
                target.write_bytes((HERE/relative).read_bytes())
            (root/"public"/"b2b"/"index.html").unlink()
            (root/"public"/"b2b"/"index.html").symlink_to(HERE/"public"/"b2b"/"index.html")
            with self.assertRaises(ValueError):
                _load_exact(root)

    def test_email_only_no_hidden_payment_gate(self):
        for content in _load_exact(HERE).values():
            self.assertNotIn(b"<form", content.lower())
            self.assertNotIn(b"wallet",content.lower())
            self.assertNotIn(b"checkout",content.lower())

    def test_manifest_enforces_explicit_nonproduction(self):
        a=archive_bytes(HERE,SHA)
        with zipfile.ZipFile(io.BytesIO(a)) as z:
            manifest=json.loads(z.read("MANIFEST.json"))
        self.assertEqual(manifest["safe_scope"],"create-only-b2b-pages-no-homepage-overwrite")
        self.assertFalse(manifest["approved_for_payments"])

if __name__ == "__main__":
    unittest.main()
