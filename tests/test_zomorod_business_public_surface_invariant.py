#!/usr/bin/env python3
"""Offline tests: homepage physical files and CSS/JS/images must remain untouched."""
import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts/zomorod_business_public_surface_invariant.py"
spec = importlib.util.spec_from_file_location("home_files", SRC)
assert spec and spec.loader
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class PublicSurfaceFingerprintContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="zm-public-invariant-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "public_html"
        (self.root / "assets").mkdir(parents=True)
        (self.root / "static" / "css").mkdir(parents=True)
        (self.root / "static" / "js").mkdir()
        (self.root / ".htaccess").write_text("RewriteEngine On\n", encoding="utf-8")
        (self.root / "index.html").write_text("<html>Site unchanged</html>\n", encoding="utf-8")
        (self.root / "assets" / "hero.svg").write_bytes(b"<svg>ORIGINAL</svg>")
        (self.root / "static" / "css" / "main.css").write_bytes(b"body{color:black}")
        (self.root / "static" / "js" / "main.js").write_bytes(b"console.log('stable')")
        self.baseline, self.count, self.bytes = guard.compute_fingerprint(self.root)

    def test_static_homepage_fixture_is_stable(self):
        second = guard.compute_fingerprint(self.root)
        self.assertEqual((self.baseline, self.count, self.bytes), second)
        self.assertEqual(self.count, 5)

    def test_changes_to_css_js_or_image_change_fingerprint(self):
        targets = [
            self.root / "static" / "css" / "main.css",
            self.root / "static" / "js" / "main.js",
            self.root / "assets" / "hero.svg",
            self.root / "index.html",
            self.root / ".htaccess",
        ]
        for target in targets:
            with self.subTest(asset=target.name):
                before = target.read_bytes()
                target.write_bytes(before + b"UPDATED")
                self.assertNotEqual(guard.compute_fingerprint(self.root)[0], self.baseline)
                target.write_bytes(before)

    def test_inserted_deleted_or_permission_changed_files_change_digest(self):
        extra = self.root / "static" / "css" / "new.css"
        extra.write_bytes(b"a{}")
        self.assertNotEqual(guard.compute_fingerprint(self.root)[0], self.baseline)
        extra.unlink()
        original = self.root / "static" / "js" / "main.js"
        perms = stat.S_IMODE(original.stat().st_mode)
        original.chmod(0o600 if perms != 0o600 else 0o644)
        self.assertNotEqual(guard.compute_fingerprint(self.root)[0], self.baseline)

    def test_root_level_favicon_logo_and_css_are_protected(self):
        for filename in ("favicon.ico", "logo.svg", "style.css", "runtime.js"):
            with self.subTest(asset=filename):
                p = self.root / filename
                p.write_bytes(b"baseline")
                first = guard.compute_fingerprint(self.root)[0]
                p.write_bytes(b"modified")
                self.assertNotEqual(first, guard.compute_fingerprint(self.root)[0])
                p.unlink()
        self.assertEqual(guard.compute_fingerprint(self.root)[0], self.baseline)

    def test_same_length_css_mutation_is_detected(self):
        css = self.root / "static" / "css" / "main.css"
        old = css.read_bytes()
        changed = old.replace(b"black", b"white")
        self.assertEqual(len(old), len(changed))
        css.write_bytes(changed)
        self.assertNotEqual(guard.compute_fingerprint(self.root)[0], self.baseline)

    def test_missing_homepage_entry_and_symlink_are_rejected(self):
        (self.root / "index.html").unlink()
        with self.assertRaises(guard.ScopeError):
            guard.compute_fingerprint(self.root)
        (self.root / "index.html").write_text("restored")
        (self.root / "static" / "images").symlink_to(self.root / "assets", target_is_directory=True)
        with self.assertRaises(guard.ScopeError):
            guard.compute_fingerprint(self.root)

    def test_excessive_asset_count_is_rejected(self):
        limit = guard.MAX_FILES
        try:
            guard.MAX_FILES = 4
            with self.assertRaises(guard.ScopeError):
                guard.compute_fingerprint(self.root)
        finally:
            guard.MAX_FILES = limit

    def test_guard_is_in_private_release_and_rolls_back_on_surface_drift(self):
        installer = (ROOT / "scripts/zomorod_business_genetics_guarded_install.sh").read_text()
        release = (ROOT / ".github/workflows/zomorod-business-update.yml").read_text()
        before = installer.index('surface_baseline="$(python3 -B "$stage/public-surface.py" capture)"')
        first_change = installer.index('mv -f "$private/.genetics-center.new-')
        after = installer.index('python3 -B "$stage/public-surface.py" verify "$surface_baseline"')
        clear = installer.index("trap - EXIT")
        self.assertLess(before, first_change)
        self.assertLess(first_change, after)
        self.assertLess(after, clear)
        self.assertIn("BUSINESS_GENETICS_ROLLBACK=verified", installer)
        self.assertIn("cat > '$stage/public-surface.py'", release)
        self.assertNotIn("cat > /home/zomorod2/public_html", release)
        self.assertNotIn("  push:\n", release)


if __name__ == "__main__":
    unittest.main()
